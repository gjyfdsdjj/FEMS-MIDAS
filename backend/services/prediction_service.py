# backend/services/prediction_service.py
# Prophet / Isolation Forest 기반 예측 및 예지 보전 로직
#
# - predict_temperature(factory_id, horizon_hours)
#     sensor_logs에서 학습 데이터 로드
#     Prophet 모델 학습/추론 (캐시 활용)
#     반환: List[{timestamp, predicted_temperature_c, lower_bound_c, upper_bound_c}]
#
# - predict_solar(date)
#     과거 태양광 발전량 + 환경 가중치(w_solar) 기반 시간대별 예측
#     반환: List[{timestamp, predicted_solar_kwh}]
#
# - assess_maintenance(factory_id)
#     '전력 투입 대비 온도 하강 효율' 지표 계산
#     Isolation Forest로 이상치 탐지
#     Prophet 예측 범위 이탈 지속 여부 결합 판정
#     반환: health_score(0~1), maintenance_risk, reason, recommended_action
#
# - _load_prophet_model(factory_id) : 모델 파일 로드 또는 신규 학습
# - _save_prophet_model(factory_id, model) : 모델 파일 저장
#
# ※ predict_solar 는 현재 기상청 API허브 NWP(`nph_sun_nwp_txt`, DSWRFLX/TMP) 기반 구현이 추가됨.
#   Prophet·과거 발전량·w_solar 전용 경로는 미구현(후속).

from __future__ import annotations

import math
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import httpx

KST = timezone(timedelta(hours=9))
KMA_HUB_URL = "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph_sun_nwp_txt"

# 간단 1차 모델 상수: 필요 시 .env에서 조정
DEFAULT_CAPACITY_KWP = float(os.getenv("SOLAR_CAPACITY_KWP", "1.8"))
DEFAULT_PERFORMANCE_RATIO = float(os.getenv("SOLAR_PERFORMANCE_RATIO", "0.82"))
TEMP_COEFF_PER_C = float(os.getenv("SOLAR_TEMP_COEFF_PER_C", "-0.004"))
TEMP_REF_C = float(os.getenv("SOLAR_TEMP_REF_C", "25.0"))


def _parse_target_date(target_date: str | None) -> date:
    if not target_date:
        return (datetime.now(KST) + timedelta(days=1)).date()
    return datetime.strptime(target_date, "%Y%m%d").date()


def _latest_tm_utc(now_utc: datetime | None = None) -> str:
    now_utc = now_utc or datetime.now(timezone.utc)
    rounded_hour = (now_utc.hour // 6) * 6
    tm = now_utc.replace(hour=rounded_hour, minute=0, second=0, microsecond=0)
    return tm.strftime("%Y%m%d%H")


def _safe_float(raw: str) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value):
        return None
    return value


def _parse_nwp_table(text: str) -> list[tuple[datetime, float]]:
    """nph_sun_nwp_txt 텍스트 표를 (UTC시각, 값) 리스트로 파싱한다."""
    lines = text.splitlines()
    headers: list[str] = []
    values: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if set(stripped) <= {"|", "=", " "}:
            continue
        cols = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cols) < 5:
            continue
        if cols[0] == "TMFC":
            headers = cols[4:]
            continue
        # 첫 data row 사용 (지점 1건 요청 기준)
        if re.fullmatch(r"\d{10}", cols[0]):
            values = cols[4:]
            break

    parsed: list[tuple[datetime, float]] = []
    if not headers or not values:
        return parsed

    for ts_raw, value_raw in zip(headers, values):
        if not re.fullmatch(r"\d{10}", ts_raw):
            continue
        value = _safe_float(value_raw)
        if value is None:
            continue
        ts_utc = datetime.strptime(ts_raw, "%Y%m%d%H").replace(tzinfo=timezone.utc)
        parsed.append((ts_utc, value))
    return parsed


async def _fetch_nwp_var(
    *,
    auth_key: str,
    varn: str,
    target_date_kst: date,
    lat: float,
    lon: float,
    nwp_model: str = "KIMR",
    tm: str | None = None,
) -> list[tuple[datetime, float]]:
    start_kst = datetime.combine(target_date_kst, time.min, tzinfo=KST)
    end_kst = datetime.combine(target_date_kst, time.max, tzinfo=KST)
    start_utc = start_kst.astimezone(timezone.utc)
    end_utc = end_kst.astimezone(timezone.utc)

    params = {
        "authKey": auth_key,
        "nwp": nwp_model,
        "varn": varn,
        "tm": tm if tm is not None else _latest_tm_utc(),
        "tmef1": start_utc.strftime("%Y%m%d%H%M"),
        "tmef2": end_utc.strftime("%Y%m%d%H%M"),
        "int": "3",
        "lat": f"{lat:.4f}",
        "lon": f"{lon:.4f}",
        "help": "0",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(KMA_HUB_URL, params=params)
        response.raise_for_status()
    return _parse_nwp_table(response.text)


def _temp_factor(temp_c: float | None) -> float:
    if temp_c is None:
        return 1.0
    factor = 1.0 + TEMP_COEFF_PER_C * (temp_c - TEMP_REF_C)
    return max(0.7, min(1.1, factor))


def _interp_kwh_linear(series: list[tuple[datetime, float]], t_utc: datetime) -> float:
    """NWP 시계열 사이는 선형 보간, 첫 시각 이전·마지막 시각 이후는 0."""
    if not series:
        return 0.0
    if t_utc < series[0][0]:
        return 0.0
    if t_utc > series[-1][0]:
        return 0.0
    if len(series) == 1:
        t0, v0 = series[0]
        return max(0.0, v0) if t_utc == t0 else 0.0
    for i in range(len(series) - 1):
        t0, v0 = series[i]
        t1, v1 = series[i + 1]
        if t0 <= t_utc <= t1:
            span = (t1 - t0).total_seconds()
            if span <= 0:
                return max(0.0, v0)
            alpha = (t_utc - t0).total_seconds() / span
            return max(0.0, v0 + alpha * (v1 - v0))
    return 0.0


def _fallback_curve(target_date_kst: date) -> list[dict[str, Any]]:
    """API 실패 시 최소 동작 보장을 위한 단순 종형 곡선."""
    result: list[dict[str, Any]] = []
    for hour in range(24):
        ts = datetime.combine(target_date_kst, time(hour=hour), tzinfo=KST)
        if 6 <= hour <= 18:
            peak = math.sin(math.pi * (hour - 6) / 12)
            kwh = round(max(0.0, peak) * 1.2, 3)
        else:
            kwh = 0.0
        result.append({"timestamp": ts.isoformat(), "predicted_solar_kwh": kwh})
    return result


async def predict_solar(
    target_date: str | None = None,
    *,
    lat: float = 37.5,
    lon: float = 127.0,
    tm: str | None = None,
) -> list[dict[str, Any]]:
    """
    다음날 시간대별 태양광 예상 발전량(kWh)을 반환한다.

    반환 형식:
    [
      {"timestamp": "...+09:00", "predicted_solar_kwh": 0.123},
      ...
    ]
    tm: API `tm`(UTC 기준 YYYYmmddHH). None이면 현재 시각 기준 최근 6시간 단위 발표시각(기존 동작).
    """
    auth_key = os.getenv("KMA_APIHUB_AUTH_KEY")
    target_day = _parse_target_date(target_date)

    if not auth_key:
        return _fallback_curve(target_day)

    try:
        dswrflx_rows = await _fetch_nwp_var(
            auth_key=auth_key,
            varn="DSWRFLX",
            target_date_kst=target_day,
            lat=lat,
            lon=lon,
            tm=tm,
        )
        tmp_rows = await _fetch_nwp_var(
            auth_key=auth_key,
            varn="TMP",
            target_date_kst=target_day,
            lat=lat,
            lon=lon,
            tm=tm,
        )
    except Exception:
        return _fallback_curve(target_day)

    if not dswrflx_rows:
        return _fallback_curve(target_day)

    temp_by_ts = {ts: value for ts, value in tmp_rows}
    series_utc: list[tuple[datetime, float]] = []
    for ts_utc, dswrflx in dswrflx_rows:
        ts_kst = ts_utc.astimezone(KST)
        if ts_kst.date() != target_day:
            continue

        temp_c = temp_by_ts.get(ts_utc)
        # 단순 근사: DSWRFLX(W/m^2)를 1시간 평균으로 보고 kWh로 환산
        base_kwh = max(0.0, dswrflx) / 1000.0 * DEFAULT_CAPACITY_KWP * DEFAULT_PERFORMANCE_RATIO
        kwh = base_kwh * _temp_factor(temp_c)
        series_utc.append((ts_utc, kwh))

    series_utc.sort(key=lambda x: x[0])
    if not series_utc:
        return _fallback_curve(target_day)

    rows: list[dict[str, Any]] = []
    for hour in range(24):
        ts_kst = datetime.combine(target_day, time(hour=hour), tzinfo=KST)
        t_utc = ts_kst.astimezone(timezone.utc)
        kwh = round(_interp_kwh_linear(series_utc, t_utc), 3)
        rows.append({"timestamp": ts_kst.isoformat(), "predicted_solar_kwh": kwh})

    return rows


async def predict_solar_daily_total(
    target_date: str | None = None,
    *,
    lat: float = 37.5,
    lon: float = 127.0,
    tm: str | None = None,
) -> dict[str, Any]:
    """다음날 총 예상 발전량(kWh)만 필요할 때 사용하는 요약 함수."""
    hourly = await predict_solar(target_date=target_date, lat=lat, lon=lon, tm=tm)
    total_kwh = round(sum(float(r.get("predicted_solar_kwh", 0.0)) for r in hourly), 3)
    target_day = _parse_target_date(target_date).strftime("%Y%m%d")
    return {
        "date": target_day,
        "predicted_total_solar_kwh": total_kwh,
        "rows": hourly,
    }
