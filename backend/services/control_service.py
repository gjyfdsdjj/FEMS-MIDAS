# backend/services/control_service.py
# 수동 제어 처리 로직
#
# - execute_manual_control(request: ManualControlRequest)
#     1. 공장 존재 여부 확인
#     2. action 유형별 처리:
#        STOP         → factories.manual_stop=True 플래그 설정
#        START        → manual_stop=False, 스케줄러 재트리거
#        SET_PWM      → value(0~100) 유효성 확인 후 MQTT 발행
#        SET_TARGET_TEMP → 온도 범위 검증 후 MQTT 발행
#        SWITCH_AUTO  → control_mode=AUTO 변경
#        SWITCH_MANUAL→ control_mode=MANUAL 변경
#        RESET        → 공장 상태 초기화
#     3. MQTT publisher.publish_command 호출
#     4. control_logs 기록
#
# - execute_all_stop(reason)
#     모든 공장에 STOP 일괄 처리
#
# - execute_all_start(reason)
#     manual_stop=True 공장 제외하고 START
#
# - get_control_logs(factory_id?, limit, cursor)
#     control_logs 커서 페이지네이션
