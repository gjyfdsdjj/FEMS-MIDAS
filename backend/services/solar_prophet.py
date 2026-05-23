"""태양광 일별 α 시계열 Prophet 예측 (③ 3a · D1=α 축만).

설계 결정 근거: ``My/MD/태양광발전량예측/보정-3단계-구현계획.md`` §D1~D7,
구현 스펙: ``My/MD/full/solar_prophet.md``.

개요:
- 입력: ``daily_alpha_series = [{"date": "YYYY-MM-DD", "alpha": float}, ...]``
  (``solar_calibration.daily_alpha_series``로 만든 일별 ``actual/nwp`` 비율)
- 출력: ``forecast_alpha_for_date(...)`` 가 ``alpha_forecast`` 와 메타를 반환.
  Job A 보정 경로는 이 값을 ``apply_solar_calibration(alpha_override=...)`` 로 전달해
  rolling mean α 대신 사용한다.

Fallback 정책 (D6):
- ``prophet`` / ``pandas`` 미설치 또는 학습·추론 예외 → rolling mean α (= 최근 window 일 평균)
- 학습 가능한 행 수 < ``min_rows`` → rolling mean (또는 데이터가 전혀 없으면 ``None``)
- 운영은 Job A를 절대 막지 않도록 항상 안전한 alpha를 시도한다.

캐시 정책 (D7):
- 모듈 메모리에 ``(forecast_date, window, last_date, len)`` 키로 결과를 보관.
- 같은 시계열·같은 예측일이면 Prophet 학습을 다시 하지 않음.
- 테스트에서는 ``clear_cache()`` 로 초기화.

본 모듈은 Prophet/pandas를 **optional import** 로만 의존한다. 미설치 환경에서도
import 자체가 실패하지 않아야 한다(Job A 회귀 방지).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

KST = timezone(timedelta(hours=9))

DEFAULT_WINDOW_DAYS = 30
DEFAULT_MIN_ROWS = 14

# (forecast_date_iso, window_days, last_series_date_iso, len(series)) -> meta dict
_FORECAST_CACHE: dict[tuple[str, int, str, int], dict[str, Any]] = {}


def _parse_iso_date(value: Any) -> date | None:
    """``YYYY-MM-DD`` 문자열을 ``date``로 변환한다. 실패 시 ``None``."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _filtered_series(series: list[dict[str, Any]]) -> list[tuple[date, float]]:
    """series에서 ``(date, alpha)`` 튜플 중 유효·양수만 추출해 날짜 오름차순 정렬."""
    pairs: list[tuple[date, float]] = []
    for row in series or []:
        if not isinstance(row, dict):
            continue
        d = _parse_iso_date(row.get("date"))
        if d is None:
            continue
        try:
            a = float(row.get("alpha"))
        except (TypeError, ValueError):
            continue
        if a <= 0.0:
            continue
        pairs.append((d, a))
    pairs.sort(key=lambda x: x[0])
    return pairs


def _resolve_forecast_date(pairs: list[tuple[date, float]], forecast_date: str | None) -> date:
    """예측 대상 일자 결정. 명시 없으면 series의 마지막 날 + 1일(KST)."""
    parsed = _parse_iso_date(forecast_date)
    if parsed is not None:
        return parsed
    if pairs:
        return pairs[-1][0] + timedelta(days=1)
    return datetime.now(KST).date() + timedelta(days=1)


def _tail_window(pairs: list[tuple[date, float]], window_days: int) -> list[tuple[date, float]]:
    """최근 ``window_days``일만 남긴다 (정렬 가정)."""
    if window_days > 0 and len(pairs) > window_days:
        return pairs[-window_days:]
    return pairs


def _rolling_mean(pairs: list[tuple[date, float]]) -> float | None:
    """``window`` 평균. 비어 있으면 ``None``."""
    if not pairs:
        return None
    return sum(a for _, a in pairs) / len(pairs)


def _build_meta(
    *,
    alpha_forecast: float | None,
    source: str,
    forecast_date: date,
    training_rows: int,
    window_days: int,
    error: str | None = None,
) -> dict[str, Any]:
    """``forecast_alpha_for_date`` 반환 스키마를 통일한다."""
    return {
        "alpha_forecast": (float(alpha_forecast) if alpha_forecast is not None else None),
        "source": source,
        "forecast_date": forecast_date.isoformat(),
        "training_rows": int(training_rows),
        "window_days": int(window_days),
        "error": error,
        "computed_at": datetime.now(KST).isoformat(),
    }


def _try_prophet(
    pairs: list[tuple[date, float]],
    forecast_date: date,
) -> tuple[float | None, str | None]:
    """Prophet으로 ``forecast_date``의 α를 예측. 실패 시 ``(None, error_msg)``."""
    try:
        import pandas as pd  # type: ignore
        from prophet import Prophet  # type: ignore
    except Exception as exc:  # pragma: no cover - 환경 의존
        return None, f"prophet_unavailable: {exc.__class__.__name__}"

    try:
        # Prophet/Stan 진단 로그는 운영에서는 잡음 → WARNING으로 끌어올린다.
        try:
            import logging

            logging.getLogger("prophet").setLevel(logging.WARNING)
            logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
        except Exception:
            pass

        df = pd.DataFrame(
            [{"ds": pd.Timestamp(d), "y": float(a)} for d, a in pairs]
        )
        if df.empty:
            return None, "empty_dataframe"

        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            interval_width=0.8,
        )
        model.fit(df)

        last_day = pairs[-1][0]
        gap_days = (forecast_date - last_day).days
        periods = max(1, gap_days)
        future = model.make_future_dataframe(periods=periods, freq="D")
        forecast = model.predict(future)

        target_ts = pd.Timestamp(forecast_date)
        row = forecast.loc[forecast["ds"] == target_ts]
        if row.empty:
            row = forecast.iloc[[-1]]
        alpha_pred = float(row["yhat"].iloc[0])

        # 음수/NaN은 α 의미상 무효 → fallback 신호
        if not (alpha_pred == alpha_pred) or alpha_pred <= 0.0:
            return None, "non_positive_or_nan"
        return alpha_pred, None
    except Exception as exc:  # pragma: no cover - 학습/추론 예외 경로
        return None, f"prophet_error: {exc.__class__.__name__}: {exc}"


def forecast_alpha_for_date(
    daily_alpha_series: list[dict[str, Any]],
    *,
    forecast_date: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_rows: int = DEFAULT_MIN_ROWS,
    use_cache: bool = True,
) -> dict[str, Any]:
    """daily α 시계열을 학습해 ``forecast_date``(KST)의 α를 예측한다.

    Parameters
    ----------
    daily_alpha_series
        ``[{"date": "YYYY-MM-DD", "alpha": float}, ...]`` 형식.
        ``solar_calibration.daily_alpha_series(actual, nwp)`` 결과를 그대로 전달.
    forecast_date
        예측 대상 KST 일자(``YYYY-MM-DD``). ``None``이면 series 마지막 날 + 1일.
    window_days
        Prophet 학습·rolling mean에 사용하는 최근 일수. 양수만 의미 있음.
    min_rows
        Prophet 학습을 시도하기 위한 최소 행 수. 부족하면 rolling mean으로 fallback.
    use_cache
        모듈 메모리 캐시 사용 여부. 같은 키면 재학습/재추론 생략.

    Returns
    -------
    dict
        스키마는 ``_build_meta`` 참조::

            {
              "alpha_forecast": float | None,
              "source": "prophet" | "rolling_mean" | "insufficient_data" | "no_data",
              "forecast_date": "YYYY-MM-DD",
              "training_rows": int,
              "window_days": int,
              "error": str | None,
              "computed_at": "ISO+09:00",
            }
    """
    # 입력 정규화 (음수·0 등 비정상 값 방어)
    try:
        window_days = int(window_days)
    except (TypeError, ValueError):
        window_days = DEFAULT_WINDOW_DAYS
    if window_days <= 0:
        window_days = DEFAULT_WINDOW_DAYS
    try:
        min_rows = int(min_rows)
    except (TypeError, ValueError):
        min_rows = DEFAULT_MIN_ROWS
    if min_rows < 0:
        min_rows = 0

    pairs_all = _filtered_series(daily_alpha_series or [])
    target_date = _resolve_forecast_date(pairs_all, forecast_date)
    window_pairs = _tail_window(pairs_all, window_days)

    cache_key: tuple[str, int, str, int] = (
        target_date.isoformat(),
        window_days,
        window_pairs[-1][0].isoformat() if window_pairs else "",
        len(window_pairs),
    )
    if use_cache and cache_key in _FORECAST_CACHE:
        return dict(_FORECAST_CACHE[cache_key])

    # 데이터 부족: Prophet 학습 자체를 시도하지 않는다.
    if len(window_pairs) < min_rows:
        rolling = _rolling_mean(window_pairs)
        meta = _build_meta(
            alpha_forecast=rolling,
            source="insufficient_data" if rolling is not None else "no_data",
            forecast_date=target_date,
            training_rows=len(window_pairs),
            window_days=window_days,
            error=f"rows<{min_rows}",
        )
        if use_cache:
            _FORECAST_CACHE[cache_key] = dict(meta)
        return meta

    alpha_pred, error = _try_prophet(window_pairs, target_date)
    if alpha_pred is not None:
        meta = _build_meta(
            alpha_forecast=alpha_pred,
            source="prophet",
            forecast_date=target_date,
            training_rows=len(window_pairs),
            window_days=window_days,
        )
        if use_cache:
            _FORECAST_CACHE[cache_key] = dict(meta)
        return meta

    # Prophet 실패 → rolling mean fallback (Job A를 절대 막지 않음)
    rolling = _rolling_mean(window_pairs)
    meta = _build_meta(
        alpha_forecast=rolling,
        source="rolling_mean",
        forecast_date=target_date,
        training_rows=len(window_pairs),
        window_days=window_days,
        error=error,
    )
    if use_cache:
        _FORECAST_CACHE[cache_key] = dict(meta)
    return meta


def clear_cache() -> None:
    """프로세스 메모리 캐시 초기화 (테스트·재학습 강제 시 호출)."""
    _FORECAST_CACHE.clear()


def cache_size() -> int:
    """현재 캐시된 항목 수 (디버깅·테스트용)."""
    return len(_FORECAST_CACHE)
