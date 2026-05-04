"""전력 소비 추정, 절감액 계산, 피크 분석, 탄소 배출량 추정.

USE_REAL_POWER_SENSOR (환경변수, 기본 false):
  false → 스케줄 ON 구간 × 정격 전력으로 추정
  true  → power_logs 테이블 실측값 사용 (전류 센서 장착 후)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import SensorLog, Schedule, PowerLog
from services.tou_service import get_tou_price_krw_per_kwh

KOREA_CARBON_FACTOR = 0.4599  # kgCO2/kWh (2023 한국 전력 배출계수)
COMPRESSOR_RATED_KW = 3.5     # 추정 모드 정격 전력 (kW)
SLOT_MINUTES = 30
TARGET_TEMP_C = -20.0


def _use_real_sensor() -> bool:
    return os.getenv("USE_REAL_POWER_SENSOR", "false").lower() == "true"


async def _kwh_from_real_sensor(
    db: AsyncSession, factory_id: int, since: datetime, now: datetime
) -> tuple[float, float]:
    """power_logs 실측값으로 kWh·요금 계산."""
    result = await db.execute(
        select(PowerLog.power_w, PowerLog.measured_at)
        .where(PowerLog.factory_id == factory_id)
        .where(PowerLog.measured_at >= since)
        .where(PowerLog.measured_at <= now)
        .order_by(PowerLog.measured_at)
    )
    rows = result.all()

    total_kwh = 0.0
    total_cost = 0.0
    for i in range(1, len(rows)):
        t0 = rows[i - 1].measured_at
        t1 = rows[i].measured_at
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=timezone.utc)
        if t1.tzinfo is None:
            t1 = t1.replace(tzinfo=timezone.utc)
        duration_h = (t1 - t0).total_seconds() / 3600
        avg_w = (float(rows[i - 1].power_w) + float(rows[i].power_w)) / 2
        kwh = avg_w / 1000 * duration_h
        rate = get_tou_price_krw_per_kwh(t0)
        total_kwh += kwh
        total_cost += kwh * rate

    return total_kwh, total_cost


async def _kwh_from_schedule(
    db: AsyncSession, factory_id: int, since: datetime, now: datetime
) -> tuple[float, float]:
    """스케줄 ON 구간 × 정격 전력으로 추정."""
    sched_result = await db.execute(
        select(Schedule)
        .where(Schedule.factory_id == factory_id)
        .where(Schedule.end_at >= since)
        .where(Schedule.start_at <= now)
        .order_by(Schedule.start_at)
    )
    schedules = sched_result.scalars().all()

    total_kwh = 0.0
    total_cost = 0.0

    if schedules:
        for sched in schedules:
            if sched.mode not in ("ON", "COOLING"):
                continue
            seg_start = max(sched.start_at, since)
            seg_end = min(sched.end_at, now)
            if seg_start >= seg_end:
                continue
            duration_h = (seg_end - seg_start).total_seconds() / 3600
            mid = seg_start + (seg_end - seg_start) / 2
            rate = get_tou_price_krw_per_kwh(mid)
            kwh = COMPRESSOR_RATED_KW * duration_h
            total_kwh += kwh
            total_cost += kwh * rate
    else:
        # 스케줄 없으면 온도 하강 구간 = 압축기 가동으로 추정
        log_result = await db.execute(
            select(SensorLog.temperature_c, SensorLog.measured_at)
            .where(SensorLog.factory_id == factory_id)
            .where(SensorLog.measured_at >= since)
            .order_by(SensorLog.measured_at)
        )
        rows = log_result.all()
        for i in range(1, len(rows)):
            if float(rows[i].temperature_c) >= float(rows[i - 1].temperature_c):
                continue
            t0 = rows[i - 1].measured_at
            t1 = rows[i].measured_at
            if t0.tzinfo is None:
                t0 = t0.replace(tzinfo=timezone.utc)
            if t1.tzinfo is None:
                t1 = t1.replace(tzinfo=timezone.utc)
            duration_h = (t1 - t0).total_seconds() / 3600
            mid = t0 + (t1 - t0) / 2
            rate = get_tou_price_krw_per_kwh(mid)
            kwh = COMPRESSOR_RATED_KW * duration_h
            total_kwh += kwh
            total_cost += kwh * rate

    return total_kwh, total_cost


async def estimate_consumption(
    db: AsyncSession, factory_id: int, hours: int = 24
) -> dict:
    """운전 시간 기반 kWh 소비량 및 전기요금 추정."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    now = datetime.now(timezone.utc)
    real = _use_real_sensor()

    if real:
        total_kwh, total_cost = await _kwh_from_real_sensor(db, factory_id, since, now)
    else:
        total_kwh, total_cost = await _kwh_from_schedule(db, factory_id, since, now)

    on_minutes = round(total_kwh / COMPRESSOR_RATED_KW * 60, 1)

    return {
        "factory_id": factory_id,
        "period_hours": hours,
        "source": "real_sensor" if real else "estimated",
        "total_kwh": round(total_kwh, 2),
        "total_cost_krw": round(total_cost),
        "compressor_on_minutes": on_minutes,
        "avg_power_kw": round(total_kwh / hours, 2) if hours > 0 else 0,
    }


async def estimate_savings(
    db: AsyncSession, factory_id: int, hours: int = 24
) -> dict:
    """최적화 스케줄 vs 무최적화(항상 ON) 기준선 비교 절감액."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    now = datetime.now(timezone.utc)

    # 기준선: 전 슬롯 항상 ON
    slot_h = SLOT_MINUTES / 60
    total_slots = int(hours * 60 / SLOT_MINUTES)
    baseline_kwh = COMPRESSOR_RATED_KW * hours
    baseline_cost = 0.0
    for i in range(total_slots):
        slot_mid = since + timedelta(minutes=i * SLOT_MINUTES + SLOT_MINUTES / 2)
        rate = get_tou_price_krw_per_kwh(slot_mid)
        baseline_cost += COMPRESSOR_RATED_KW * slot_h * rate

    # 최적화 실적
    if _use_real_sensor():
        optimized_kwh, optimized_cost = await _kwh_from_real_sensor(db, factory_id, since, now)
    else:
        optimized_kwh, optimized_cost = await _kwh_from_schedule(db, factory_id, since, now)

    saved_kwh = max(baseline_kwh - optimized_kwh, 0.0)
    saved_cost = max(baseline_cost - optimized_cost, 0.0)

    return {
        "factory_id": factory_id,
        "period_hours": hours,
        "source": "real_sensor" if _use_real_sensor() else "estimated",
        "baseline_kwh": round(baseline_kwh, 2),
        "baseline_cost_krw": round(baseline_cost),
        "optimized_kwh": round(optimized_kwh, 2),
        "optimized_cost_krw": round(optimized_cost),
        "saved_kwh": round(saved_kwh, 2),
        "saved_cost_krw": round(saved_cost),
        "saving_rate_pct": round(saved_cost / baseline_cost * 100, 1) if baseline_cost > 0 else 0.0,
        "carbon_saved_kg": round(saved_kwh * KOREA_CARBON_FACTOR, 2),
    }


async def peak_analysis(
    db: AsyncSession, factory_id: int, hours: int = 24
) -> dict:
    """시간대별 냉각 부하 피크 분석 (내부온도 기준)."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    log_result = await db.execute(
        select(SensorLog.temperature_c, SensorLog.measured_at)
        .where(SensorLog.factory_id == factory_id)
        .where(SensorLog.measured_at >= since)
        .order_by(SensorLog.measured_at)
    )
    rows = log_result.all()

    if not rows:
        return {
            "factory_id": factory_id,
            "period_hours": hours,
            "peak_hour_kst": None,
            "peak_label": None,
            "hourly_avg_temp_c": {},
            "hourly_cooling_load_pct": {},
            "message": "데이터 없음",
        }

    hourly: dict[int, list[float]] = {h: [] for h in range(24)}
    for row in rows:
        t = row.measured_at
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        kst_hour = (t.hour + 9) % 24
        hourly[kst_hour].append(float(row.temperature_c))

    hourly_avg = {h: round(sum(v) / len(v), 2) for h, v in hourly.items() if v}
    hourly_load = {h: max(round(t - TARGET_TEMP_C, 2), 0.0) for h, t in hourly_avg.items()}
    max_load = max(hourly_load.values(), default=1)
    hourly_load_pct = {h: round(v / max_load * 100, 1) for h, v in hourly_load.items()}
    peak_hour = max(hourly_load, key=lambda h: hourly_load[h])

    return {
        "factory_id": factory_id,
        "period_hours": hours,
        "peak_hour_kst": peak_hour,
        "peak_label": f"{peak_hour:02d}:00 ~ {(peak_hour + 1) % 24:02d}:00",
        "hourly_avg_temp_c": hourly_avg,
        "hourly_cooling_load_pct": hourly_load_pct,
        "data_points": len(rows),
    }


def carbon_emission(kwh: float) -> dict:
    """kWh → CO2 배출량 (한국 2023 배출계수 0.4599 kgCO2/kWh)."""
    return {
        "kwh": round(kwh, 2),
        "carbon_kg": round(kwh * KOREA_CARBON_FACTOR, 3),
        "carbon_factor": KOREA_CARBON_FACTOR,
        "standard": "한국 2023년 전력 배출계수 (0.4599 kgCO2/kWh)",
    }
