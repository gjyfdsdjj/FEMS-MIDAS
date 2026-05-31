from sqlalchemy.ext.asyncio import AsyncSession
from repositories.sensor_log_archive_repository import get_recent_archive_sensor_logs
from datetime import datetime, timedelta, timezone
from repositories.alert_repository import check_duplicate_alert, insert_alert

import rrcf

RCF_SCORE_THRESHOLD = 20.0 # 몇 점 이상이면 이상으로 볼 것인가

'''
Random Cut Forest 기반 이상 점수 계산
    - 온도값 1개를 1차원 포인트로 사용
    - codisp 값이 높을수록 이상 가능성이 높음
'''
def calculate_rcf_score(values: list[float]) -> list[float]:

    if not values:
        return []

    tree = rrcf.RCTree()
    scores = []

    for index, value in enumerate(values):
        point = [value]

        tree.insert_point(point, index=index) # 온도 데이터를 하나씩 트리에 삽입

        if len(tree.leaves) < 10:
            scores.append(0.0)
            continue

        score = tree.codisp(index) # 방금 넣은 값이 얼마나 이상한지 점수 
        scores.append(float(score)) # 이상 점수는 리스트에 저장

    return scores

# sensor_logs_archive 데이터를 기반으로 온도 이상 패턴 분석
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

    if anomaly_results:
        alert_type = "RCF_TEMPERATURE_ANOMALY"
        time_limit = datetime.now(timezone.utc) - timedelta(seconds=300)

        is_duplicate = await check_duplicate_alert(
            db=db,
            factory_id=factory_id,
            alert_type=alert_type,
            time_limit=time_limit,
        )

        if not is_duplicate:
            saved_alert = await insert_alert(
                db=db,
                factory_id=factory_id,
                priority="high",
                severity="warning",
                alert_type=alert_type,
                message=f"RCF 온도 이상 감지: 이상 데이터 {len(anomaly_results)}건 발견",
            )
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
        "results": results,
        "message": "RCF 기반 온도 이상 분석이 완료되었습니다.",
    }

    