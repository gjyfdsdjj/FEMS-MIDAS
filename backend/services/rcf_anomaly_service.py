from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from repositories.sensor_log_archive_repository import get_recent_archive_sensor_logs
from repositories.alert_repository import check_duplicate_alert
from services.alert_service import create_alert

import rrcf


RCF_SCORE_THRESHOLD = 20.0
RCF_ALERT_THRESHOLD = 40.0


def calculate_rcf_score(values: list[float]) -> list[float]:
    if not values:
        return []

    tree = rrcf.RCTree()
    scores = []

    for index, value in enumerate(values):
        point = [value]
        tree.insert_point(point, index=index)

        if len(tree.leaves) < 10:
            scores.append(0.0)
            continue

        score = tree.codisp(index)
        scores.append(float(score))

    return scores


async def run_rcf_temperature_analysis(
    db: AsyncSession,
    factory_id: int,
    limit: int = 100,
) -> dict:

    logs = await get_recent_archive_sensor_logs(
        db=db,
        factory_id=factory_id,
        limit=limit,
    )

    valid_logs = [
        log for log in logs
        if log["temperature_c"] is not None
    ]

    temperatures = [
        float(log["temperature_c"])
        for log in valid_logs
    ]

    scores = calculate_rcf_score(temperatures)
    results = []

    for log, score in zip(valid_logs, scores):
        is_anomaly = score >= RCF_SCORE_THRESHOLD

        results.append({
            "id": log["id"],
            "factory_id": log["factory_id"],
            "node_id": log["node_id"],
            "temperature_c": float(log["temperature_c"]),
            "humidity_pct": float(log["humidity_pct"]) if log["humidity_pct"] is not None else None,
            "measured_at": log["measured_at"],
            "rcf_score": round(score, 3),
            "is_anomaly": is_anomaly,
        })

    anomaly_results = [
        row for row in results
        if row["is_anomaly"]
    ]

    saved_alerts = []

    max_score = max(
        [row["rcf_score"] for row in anomaly_results],
        default=0.0,
    )

    if anomaly_results and max_score >= RCF_ALERT_THRESHOLD:
        time_limit = datetime.now(timezone.utc) - timedelta(seconds=300)

        has_recent_rule_alert = await check_duplicate_alert(
            db=db,
            factory_id=factory_id,
            alert_type="TEMP_RANGE_OUT",
            time_limit=time_limit,
        )

        if not has_recent_rule_alert:
            saved_alert = await create_alert(
                db=db,
                factory_id=factory_id,
                priority="high",
                severity="warning",
                alert_type="RCF_TEMPERATURE_PATTERN",
                message=f"RCF 기반 온도 패턴 이상 감지: 최대 score={max_score}",
            )

            if saved_alert is not None:
                saved_alerts.append(saved_alert)

    return {
        "success": True,
        "factory_id": factory_id,
        "checked_count": len(results),
        "anomaly_count": len(anomaly_results),
        "saved_alert_count": len(saved_alerts),
        "threshold": RCF_SCORE_THRESHOLD,
        "anomalies": anomaly_results,
        "saved_alerts": saved_alerts,
        "alert_threshold": RCF_ALERT_THRESHOLD,
        "max_score": max_score,
        "results": results,
        "message": "RCF 기반 온도 이상 분석이 완료되었습니다.",
    }