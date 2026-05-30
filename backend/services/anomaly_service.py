# backend/services/anomaly_service.py
# 이상 감지 판단 로직 

# - check_temperature_range(factory_id, current_temp)
#   온도 범위 이탈 감지
#   정상 범위: -22°C ~ -16°C (추후 변경 가능)
#   범위를 벗어나면 TEMP_RANGE_OUT 이상으로 판단 
#
# - check_temperature_spike(current_sensor_log, old_sensor_log)
#   온도 급변 감지
#   현재 로그와 최근 5분 구간 내 이전 로그의 온도 변화량이 5°C 이상이면 TEMP_SPIKE 이상으로 판단 
#
# - check_communication_timeout(factory_id)
#   센서/통신 이상 감지
#   factories.last_seen_at 기준 일정 시간 이상 데이터 미수신 시 COMMUNICATION_TIMEOUT 판단
#
# - build_anomaly_result(factory_id, Level, anomaly_type, message)
#   alert_service.create_alert에서 사용할 수 있는 형태로 이상 감지 결과 생성
#

from datetime import datetime
from repositories.sensor_log_repository import get_latest_sensor_logs, get_sensor_logs_before_5_minutes
from repositories.factory_repository import get_factory_last_seen_times
from services.alert_service import create_alert
from sqlalchemy.ext.asyncio import AsyncSession

TEMP_MIN_C = -22.0
TEMP_MAX_C = -16.0
SPIKE_THRESHOLD_C = 5.0
COMMUNICATION_TIMEOUT_SEC = 180 # 임시 기준: 3분 

def build_anomaly_result(factory_id, priority, severity, anomaly_type, message):
    return{
        "factory_id": factory_id,
        "priority": priority,   # high, medium, low
        "severity": severity,   # critical, warning, info
        "alert_type": anomaly_type,
        "message": message
    }

def check_temperature_range(sensor_log):
    factory_id = sensor_log["factory_id"]
    current_temp = sensor_log["temperature_c"]

    if current_temp < TEMP_MIN_C:
        return build_anomaly_result(
            factory_id,
            "high",
            "critical",
            "TEMP_RANGE_OUT",
            f"⚠️ [CRITICAL] {factory_id}번 공장 온도가 너무 낮습니다. 현재 온도: {current_temp}°C"
        )
    if current_temp > TEMP_MAX_C:
        return build_anomaly_result(
            factory_id,
            "high",
            "critical",
            "TEMP_RANGE_OUT",
            f"⚠️ [CRITICAL] {factory_id}번 공장 온도가 너무 높습니다. 현재 온도: {current_temp}°C"
        )

    return None

def check_temperature_spike(current_sensor_log, old_sensor_log):
    if old_sensor_log is None:
        return None
    
    factory_id = current_sensor_log["factory_id"]
    current_temp = current_sensor_log["temperature_c"]
    old_temp = old_sensor_log["temperature_c"]

    diff = abs(current_temp - old_temp)

    if diff >= SPIKE_THRESHOLD_C:
        return build_anomaly_result(
            factory_id,
            "medium",
            "warning",
            "TEMP_SPIKE",
            f"⚠️ [WARNING] {factory_id}번 공장 온도가 최근 5분 구간 내 급변했습니다. "
            f"현재 온도: {current_temp}°C, "
            f"이전 온도: {old_temp}°C, "
            f"변화량: {diff:.2f}°C"
        )
    return None

def check_communication_timeout(factory):
    factory_id = factory["factory_id"]
    last_seen_at = factory.get("last_seen_at")

    if last_seen_at is None:
        return build_anomaly_result(
            factory_id,
            "low",
            "info",
            "COMMUNICATION_TIMEOUT",
            f"ℹ️ [INFO] {factory_id}번 공장의 최초 데이터 수신 대기 중입니다."
        )
    
    now = datetime.now(last_seen_at.tzinfo)
    elapsed_sec = (now - last_seen_at).total_seconds() # 경과 시간

    if elapsed_sec >= COMMUNICATION_TIMEOUT_SEC:
        return build_anomaly_result(
            factory_id,
            "high",
            "critical",
            "COMMUNICATION_TIMEOUT",
            f"⚠️ [CRITICAL] {factory_id}번 공장 센서 데이터가 {int(elapsed_sec)}초 동안 수신되지 않았습니다."
        )
    
    return None


async def run_anomaly_monitoring(db: AsyncSession) -> dict:
    '''
    Job C에서 1분마다 호출할 이상 감지 총괄 함수

    DB 데이터 기반으로 3가지 이상 현상 감지
    - TEMP_RANGE_OUT: 공장별 최신 센서 로그 기준 온도 범위 이탈
    - TEMP_SPIKE: 공장별 최신 로그와 5분 전 로그의 온도 차이
    - COMMUNICATION_TIMEOUT: factories.last_seen_at 기준 센서 수신 지연
    '''

    latest_sensor_logs = await get_latest_sensor_logs(db)
    sensor_logs_before_5_minutes = await get_sensor_logs_before_5_minutes(db)
    factory_last_seen_times = await get_factory_last_seen_times(db)

    sensor_logs_before_5_minutes_by_factory = {
        row["factory_id"]: row 
        for row in sensor_logs_before_5_minutes
    }

    detected_alerts = []

    for sensor_log in latest_sensor_logs:
        factory_id = sensor_log["factory_id"]

        # 온도 범위 이탈 체크
        range_result = check_temperature_range(sensor_log)
        if range_result:
            detected_alerts.append(range_result)
            # db 저장 및 텔레그램 발송 트리거 
            await create_alert(
                db=db,
                factory_id=range_result["factory_id"],
                priority=range_result["priority"],
                severity=range_result["severity"],
                alert_type=range_result["alert_type"],
                message=range_result["message"]
            )

        # 온도 급변 체크 
        sensor_log_before_5_minutes = sensor_logs_before_5_minutes_by_factory.get(factory_id)
        spike_result = check_temperature_spike(sensor_log, sensor_log_before_5_minutes)
        if spike_result:
            detected_alerts.append(spike_result)
            # db 저장 및 텔레그램 발송 트리거 
            await create_alert(
                db=db,
                factory_id=spike_result["factory_id"],
                priority=spike_result["priority"],
                severity=spike_result["severity"],
                alert_type=spike_result["alert_type"],
                message=spike_result["message"]
            )
    
    for factory_last_seen in factory_last_seen_times:
        # 통신 타임아웃 감지
        timeout_result = check_communication_timeout(factory_last_seen)
        if timeout_result:
            detected_alerts.append(timeout_result)
            # db 저장 및 텔레그램 발송 트리거 
            await create_alert(
                db=db,
                factory_id=timeout_result["factory_id"],
                priority=timeout_result["priority"],
                severity=timeout_result["severity"],
                alert_type=timeout_result["alert_type"],
                message=timeout_result["message"]
            )

    return {
        "success": True,
        "checked_count": len(latest_sensor_logs) + len(factory_last_seen_times),
        "alerts_created": len(detected_alerts),
        "alerts": detected_alerts,
        "message": "anomaly monitoring executed",
    }
