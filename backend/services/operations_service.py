import math
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, String
from sqlalchemy import cast
from database.models import SensorLog, Factory, Schedule, Job

SENSOR_INTERVAL_SECONDS = 5
EFFICIENCY_THRESHOLD_MIN_PER_DEG = 15.0  # 도당 15분 이상이면 효율 저하로 판단


async def sensor_reliability(db: AsyncSession, factory_id: int, hours: int = 24) -> dict:
    """공장별 센서 수신 성공률. 5초 간격 기준 실제 수신 건수 / 기대 건수 × 100"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(func.count(SensorLog.id))
        .where(SensorLog.factory_id == factory_id)
        .where(SensorLog.measured_at >= since)
    )
    actual = result.scalar() or 0
    expected = int(hours * 3600 / SENSOR_INTERVAL_SECONDS)
    pct = round(min(actual / expected * 100, 100.0), 1) if expected > 0 else 0.0
    return {
        "factory_id": factory_id,
        "reliability_pct": pct,
        "actual_count": actual,
        "expected_count": expected,
        "period_hours": hours,
        "grade": "EXCELLENT" if pct >= 98 else "GOOD" if pct >= 90 else "POOR",
    }


async def temperature_stability(db: AsyncSession, factory_id: int, hours: int = 24) -> dict:
    """온도 표준편차 기반 안정성 지표. std_dev 낮을수록 안정적 (STABLE < 0.5 < MODERATE < 1.5 < UNSTABLE)"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(SensorLog.temperature_c)
        .where(SensorLog.factory_id == factory_id)
        .where(SensorLog.measured_at >= since)
    )
    temps = [float(r) for r in result.scalars().all()]
    if len(temps) < 2:
        return {"factory_id": factory_id, "std_dev": None, "message": "데이터 부족"}
    mean = sum(temps) / len(temps)
    std_dev = round(math.sqrt(sum((t - mean) ** 2 for t in temps) / len(temps)), 3)
    return {
        "factory_id": factory_id,
        "std_dev": std_dev,
        "avg_temp": round(mean, 2),
        "min_temp": round(min(temps), 2),
        "max_temp": round(max(temps), 2),
        "period_hours": hours,
        "grade": "STABLE" if std_dev < 0.5 else "MODERATE" if std_dev < 1.5 else "UNSTABLE",
    }


async def target_temp_adherence(db: AsyncSession, factory_id: int, hours: int = 24, tolerance: float = 2.0) -> dict:
    """스케줄 목표 온도 ± tolerance 범위 내로 유지된 비율. 스케줄이 없으면 null 반환"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    now = datetime.now(timezone.utc)
    sched_result = await db.execute(
        select(Schedule)
        .where(Schedule.factory_id == factory_id)
        .where(Schedule.end_at >= since)
        .where(Schedule.start_at <= now)
    )
    schedules = sched_result.scalars().all()
    if not schedules:
        return {"factory_id": factory_id, "adherence_pct": None, "message": "스케줄 없음"}
    total, within = 0, 0
    for sched in schedules:
        if sched.target_temp is None:
            continue
        s_start = max(sched.start_at, since) if sched.start_at else since
        s_end = min(sched.end_at, now) if sched.end_at else now
        result = await db.execute(
            select(SensorLog.temperature_c)
            .where(SensorLog.factory_id == factory_id)
            .where(SensorLog.measured_at >= s_start)
            .where(SensorLog.measured_at <= s_end)
        )
        for temp in result.scalars().all():
            total += 1
            if abs(float(temp) - sched.target_temp) <= tolerance:
                within += 1
    if total == 0:
        return {"factory_id": factory_id, "adherence_pct": None, "message": "스케줄 중 데이터 없음"}
    return {
        "factory_id": factory_id,
        "adherence_pct": round(within / total * 100, 1),
        "total_readings": total,
        "within_tolerance": within,
        "tolerance_c": tolerance,
        "period_hours": hours,
    }


async def operational_efficiency_score(db: AsyncSession, factory_id: int) -> dict:
    """운영 효율 종합 점수 (0~100). 센서신뢰도 30% + 온도안정성 30% + 목표온도유지율 40%"""
    rel = await sensor_reliability(db, factory_id, hours=24)
    stab = await temperature_stability(db, factory_id, hours=24)
    adh = await target_temp_adherence(db, factory_id, hours=24)
    rel_score = rel.get("reliability_pct", 0.0)
    std = stab.get("std_dev")
    stab_score = max(0.0, 100.0 - (std * 20)) if std is not None else 0.0
    adh_score = adh.get("adherence_pct") or 0.0
    total = round(rel_score * 0.3 + stab_score * 0.3 + adh_score * 0.4, 1)
    grade = "A" if total >= 90 else "B" if total >= 75 else "C" if total >= 60 else "D"
    return {
        "factory_id": factory_id,
        "total_score": total,
        "grade": grade,
        "breakdown": {
            "sensor_reliability": round(rel_score, 1),
            "temperature_stability": round(stab_score, 1),
            "target_adherence": round(adh_score, 1),
        },
        "weights": {"sensor_reliability": 0.3, "temperature_stability": 0.3, "target_adherence": 0.4},
    }


async def inventory_capacity(db: AsyncSession, factory_id: int) -> dict:
    """현재 진행 중인 작업(pending/in_progress) 수량 합계 / 공장 최대 용량으로 점유율 계산"""
    factory = await db.get(Factory, factory_id)
    if not factory or not factory.max_quantity:
        return {"factory_id": factory_id, "occupancy_pct": None, "message": "공장 정보 없음"}
    result = await db.execute(
        select(func.coalesce(func.sum(Job.quantity), 0))
        .where(Job.factory_id == factory_id)
        .where(cast(Job.status, String).in_(["pending", "in_progress"]))
    )
    current_qty = result.scalar() or 0
    pct = round(current_qty / factory.max_quantity * 100, 1)
    return {
        "factory_id": factory_id,
        "max_quantity": factory.max_quantity,
        "current_quantity": current_qty,
        "occupancy_pct": pct,
        "status": "FULL" if pct >= 95 else "HIGH" if pct >= 80 else "NORMAL",
    }


async def job_deadline_compliance(db: AsyncSession) -> dict:
    """마감이 지난 작업 중 completed/closed 상태인 비율. 작업 마감 준수율"""
    now = datetime.now(timezone.utc)
    result = await db.execute(select(Job).where(Job.deadline_at < now))
    past_jobs = result.scalars().all()
    if not past_jobs:
        return {"compliance_pct": None, "message": "마감 지난 작업 없음", "total": 0}
    completed = [j for j in past_jobs if j.status in ("completed", "closed")]
    pct = round(len(completed) / len(past_jobs) * 100, 1)
    return {
        "compliance_pct": pct,
        "completed_on_time": len(completed),
        "total_past_deadline": len(past_jobs),
        "failed": len(past_jobs) - len(completed),
    }


async def door_event_analysis(db: AsyncSession, factory_id: int, hours: int = 24) -> dict:
    """1분 내 1°C 이상 온도 급상승 구간을 도어 열림 이벤트로 추정. 5분 내 중복 제거"""
    factory = await db.get(Factory, factory_id)
    if not factory:
        return {"factory_id": factory_id, "message": "공장 없음"}
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(SensorLog.temperature_c, SensorLog.measured_at)
        .where(SensorLog.factory_id == factory_id)
        .where(SensorLog.measured_at >= since)
        .order_by(SensorLog.measured_at)
    )
    rows = result.all()
    window = 12
    events = []
    for i in range(window, len(rows)):
        rise = float(rows[i].temperature_c) - float(rows[i - window].temperature_c)
        if rise >= 1.0:
            t = rows[i].measured_at
            if hasattr(t, "tzinfo") and t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            events.append({"detected_at": t.isoformat(), "temp_rise": round(rise, 2)})
    deduped, last_t = [], None
    for e in events:
        et = datetime.fromisoformat(e["detected_at"])
        if last_t is None or (et - last_t).total_seconds() > 300:
            deduped.append(e)
            last_t = et
    avg_rise = round(sum(e["temp_rise"] for e in deduped) / len(deduped), 2) if deduped else 0
    return {
        "factory_id": factory_id,
        "is_door_open": factory.is_door_open,
        "door_open_count_total": factory.door_open_count,
        "estimated_events": len(deduped),
        "avg_temp_rise_per_event_c": avg_rise,
        "events": deduped[:10],
        "period_hours": hours,
    }


async def cooling_cycle_analysis(db: AsyncSession, factory_id: int, hours: int = 24) -> dict:
    """이동평균으로 노이즈 제거 후 온도 방향 전환 횟수로 냉각 ON/OFF 사이클 수 및 평균 시간 계산"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(SensorLog.temperature_c, SensorLog.measured_at)
        .where(SensorLog.factory_id == factory_id)
        .where(SensorLog.measured_at >= since)
        .order_by(SensorLog.measured_at)
    )
    rows = result.all()
    if len(rows) < 10:
        return {"factory_id": factory_id, "cycles": None, "message": "데이터 부족"}
    w = 6
    smoothed = []
    for i in range(len(rows)):
        s = max(0, i - w + 1)
        smoothed.append(sum(float(rows[j].temperature_c) for j in range(s, i + 1)) / (i - s + 1))
    changes, last_dir, cycle_times = 0, None, []
    for i in range(1, len(smoothed)):
        diff = smoothed[i] - smoothed[i - 1]
        cur = "up" if diff > 0.05 else "down" if diff < -0.05 else None
        if cur and cur != last_dir:
            if last_dir is not None:
                changes += 1
                t = rows[i].measured_at
                if hasattr(t, "tzinfo") and t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                cycle_times.append(t)
            last_dir = cur
    cycles = changes // 2
    avg_cycle_min = None
    if len(cycle_times) >= 2:
        gaps = [(cycle_times[i + 1] - cycle_times[i]).total_seconds()
                for i in range(0, len(cycle_times) - 1, 2) if i + 1 < len(cycle_times)]
        if gaps:
            avg_cycle_min = round(sum(gaps) / len(gaps) / 60, 1)
    return {
        "factory_id": factory_id,
        "cycles": cycles,
        "avg_cycle_minutes": avg_cycle_min,
        "period_hours": hours,
    }


async def human_presence_analysis(db: AsyncSession, factory_id: int, hours: int = 24) -> dict:
    """상위 10% 온도 구간을 인원 활동 기간으로 추정해 전체 평균 대비 온도 상승폭 계산"""
    factory = await db.get(Factory, factory_id)
    if not factory:
        return {"factory_id": factory_id, "message": "공장 없음"}
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(SensorLog.temperature_c)
        .where(SensorLog.factory_id == factory_id)
        .where(SensorLog.measured_at >= since)
    )
    temps = [float(r) for r in result.scalars().all()]
    if len(temps) < 10:
        return {"factory_id": factory_id, "message": "데이터 부족", "is_human_now": factory.is_human}
    mean = sum(temps) / len(temps)
    threshold = sorted(temps, reverse=True)[max(0, len(temps) // 10)]
    activity = [t for t in temps if t >= threshold]
    activity_avg = round(sum(activity) / len(activity), 2)
    return {
        "factory_id": factory_id,
        "is_human_now": factory.is_human,
        "overall_avg_temp": round(mean, 2),
        "activity_period_avg_temp": activity_avg,
        "temp_increase_during_activity": round(activity_avg - mean, 2),
        "period_hours": hours,
    }


async def maintenance_recommendation(db: AsyncSession, factory_id: int) -> dict:
    """냉각 효율(도당 소요 분)이 기준치(15분/도) 이상이면 설비 점검 권고"""
    from services.analytics_service import cooling_efficiency
    efficiency = await cooling_efficiency(db, factory_id, hours=24)
    mpd = efficiency.get("minutes_per_degree")
    if mpd is None:
        return {
            "factory_id": factory_id,
            "recommendation": "UNKNOWN",
            "message": efficiency.get("message", "데이터 없음"),
        }
    if mpd >= EFFICIENCY_THRESHOLD_MIN_PER_DEG:
        return {
            "factory_id": factory_id,
            "recommendation": "MAINTENANCE_REQUIRED",
            "minutes_per_degree": mpd,
            "threshold": EFFICIENCY_THRESHOLD_MIN_PER_DEG,
            "message": f"냉각 효율 저하 (도당 {mpd}분). 설비 점검 권고.",
        }
    return {
        "factory_id": factory_id,
        "recommendation": "NORMAL",
        "minutes_per_degree": mpd,
        "threshold": EFFICIENCY_THRESHOLD_MIN_PER_DEG,
        "message": "냉각 효율 정상",
    }
