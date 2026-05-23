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
from backend.repositories.sensor_log_repository import get_latest_sensor_logs, get_sensor_logs_before_5_minutes
from backend.repositories.factory_repository import get_factory_last_seen_times
from sqlalchemy.ext.asyncio import AsyncSession

TEMP_MIN_C = -22.0
TEMP_MAX_C = -16.0
SPIKE_THRESHOLD_C = 5.0
COMMUNICATION_TIMEOUT_SEC = 180 # 임시 기준: 3분 

def build_anomaly_result(factory_id, level, anomaly_type, message):
    return{
        "factory_id": factory_id,
        "level": level,
        "alert_type": anomaly_type,
        "message": message
    }

def check_temperature_range(sensor_log):
    factory_id = sensor_log["factory_id"]
    current_temp = sensor_log["temperature_c"]

    if current_temp < TEMP_MIN_C:
        return build_anomaly_result(
            factory_id,
            "WARNING",
            "TEMP_RANGE_OUT",
            f"{factory_id}번 공장 온도가 너무 낮습니다. 현재 온도: {current_temp}°C"
        )
    if current_temp > TEMP_MAX_C:
        return build_anomaly_result(
            factory_id,
            "WARNING",
            "TEMP_RANGE_OUT",
            f"{factory_id}번 공장 온도가 너무 높습니다. 현재 온도: {current_temp}°C"
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
            "WARNING",
            "TEMP_SPIKE",
            f"{factory_id}번 공장 온도가 최근 5분 구간 내 급변했습니다. "
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
            "CRITICAL",
            "COMMUNICATION_TIMEOUT",
            f"{factory_id}번 공장 센서 수신 시간이 없습니다."
        )
    
    now = datetime.now(last_seen_at.tzinfo)
    elapsed_sec = (now - last_seen_at).total_seconds() # 경과 시간

    if elapsed_sec >= COMMUNICATION_TIMEOUT_SEC:
        return build_anomaly_result(
            factory_id,
            "CRITICAL",
            "COMMUNICATION_TIMEOUT",
            f"{factory_id}번 공장 센서 데이터가 {int(elapsed_sec)}초 동안 수신되지 않았습니다."
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

        range_result = check_temperature_range(sensor_log)
        if range_result:
            detected_alerts.append(range_result)

        sensor_log_before_5_minutes = sensor_logs_before_5_minutes_by_factory.get(factory_id)

        spike_result = check_temperature_spike(sensor_log, sensor_log_before_5_minutes)
        if spike_result:
            detected_alerts.append(spike_result)
    
    for factory_last_seen in factory_last_seen_times:
        timeout_result = check_communication_timeout(factory_last_seen)
        if timeout_result:
            detected_alerts.append(timeout_result)

    return {
        "success": True,
        "checked_count": len(latest_sensor_logs) + len(factory_last_seen_times),
        "alerts_created": len(detected_alerts),
        "alerts": detected_alerts,
        "message": "anomaly monitoring executed",
    }
