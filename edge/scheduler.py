# edge/scheduler.py
# Edge 로컬 스케줄 실행기
#
# - EdgeScheduler(factory_id, pwm_controller) 클래스
#
# - load_schedule(blocks)
#     MQTT로 수신한 ScheduleBlock 리스트 로컬 저장
#     SQLite에도 백업 (통신 단절 후 재부팅 시 복구용)
#
# - tick()  ← 메인 루프에서 매 분 호출
#     현재 시각에 해당하는 블록 탐색
#     모드별 동작:
#       ON            → 목표 온도까지 냉각 (PWM 자동 조절)
#       OFF           → PWM 0%
#       PRECOOL       → 설정 온도보다 낮게 과냉각
#       COASTING      → 냉각 최소화, 온도 감시만
#       SOLAR_PRIORITY→ 태양광 발전 상태 확인 후 PWM 조절
#
# - _adjust_pwm_by_temp(current_temp, target_temp)
#     간단한 P 제어 (비례 제어)로 PWM 듀티 계산
#     온도 이탈 시 alert 발행
#
# - fallback_mode()
#     클라우드 명령 수신 없을 때 독립 제어 모드 전환
#     목표 온도 -18°C 유지 최우선
