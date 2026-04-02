# backend/routers/control.py
# 수동 제어 엔드포인트 (admin 전용)
#
# POST /api/v1/control/manual
#   - 권한: admin
#   - action: START | STOP | RESET | SET_PWM | SET_TARGET_TEMP | SWITCH_AUTO | SWITCH_MANUAL
#   - STOP 시 manual_stop=True 플래그 설정 → 자동 스케줄러가 재가동 금지
#   - MQTT publisher로 command 발행
#   - control_logs 테이블 기록
#
# POST /api/v1/control/all-stop
#   - 권한: admin
#   - 전체 긴급 정지, 4개 공장 일괄 MQTT STOP 발행
#
# POST /api/v1/control/all-start
#   - 권한: admin
#   - manual_stop=True 공장은 제외하고 재가동
#
# GET /api/v1/control/logs
#   - 권한: admin
#   - Query: factory_id?, limit?, cursor?
#   - 수동 제어 이력 커서 페이지네이션
