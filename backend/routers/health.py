# backend/routers/health.py
# GET /api/v1/health
#
# - 권한: public
# - DB ping, MQTT 연결 상태, APScheduler 상태 확인
# - 응답: status / api / db / mqtt / scheduler / timestamp
