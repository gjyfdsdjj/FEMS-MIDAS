# backend/routers/sensors.py
# 센서 데이터 엔드포인트
#
# GET /api/v1/sensors/live
#   - 권한: viewer
#   - Query: factory_id? (없으면 전체)
#   - 각 공장 최신 telemetry 1건 반환
#
# GET /api/v1/sensors/history
#   - 권한: viewer
#   - Query: factory_id, metric(temperature|humidity|pwm), from, to, interval(1m|5m|30m|1h)
#   - sensor_logs 시계열 조회 후 interval 단위로 집계(평균) 반환
