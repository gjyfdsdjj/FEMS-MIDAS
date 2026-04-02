# backend/scheduler/jobs.py
# APScheduler 백그라운드 작업 정의
#
# - get_scheduler() : BackgroundScheduler 인스턴스 반환 (싱글턴)
#
# [Job A] 30분 주기 최적화  (cron: */30 * * * *)
#   1. 현재 활성 job 조회 (없으면 skip)
#   2. 잔여 생산량 R = Q_total - Q_completed 계산
#   3. 현재 TOU 요금 조회
#   4. 공장별 센서 상태 조회 (manual_stop 공장 제외)
#   5. 태양광 예측값 + 환경 가중치(w_solar) 반영
#   6. PuLP 선형 계획법으로 스케줄 최적화 (optimization_service)
#      - 목적함수: Minimize Σ(Grid_Power[t] × TOU_Price[t]) - (Solar_Predicted[t] × w_solar)
#      - 제약: 내부 온도 -18°C 초과 금지, Short Cycle 30분 준수, 생산량 마감 보장
#   7. schedules 테이블 저장
#   8. MQTT 명령 발행 (publisher.publish_schedule)
#   9. schedule_logs 기록
#
# [Job B] 매일 18시 환경 가중치 갱신  (cron: 0 18 * * *)
#   1. 기상청 API 호출 (httpx.AsyncClient) → 다음날 최고기온 / 일사량
#   2. w_temp = f(최고기온) : 폭염이면 1.2, 평년이면 1.0
#   3. w_solar = f(날씨코드) : 맑음 1.0 / 흐림 0.5 / 비 0.2
#   4. environment_weights 테이블 저장
#   5. 야간 축냉 목표 온도 재계산 (폭염 → -27°C, 평년 → -25°C)
#
# [Job C] 1분 주기 알림 감시  (cron: */1 * * * *)
#   1. 최신 sensor_logs에서 온도 이탈 감지 (임계값 ±2°C)
#   2. last_seen_at 기준 통신 timeout 감지 (30초 초과 시 DISCONNECTED)
#   3. 중복 알림 window 확인 (300초 내 동일 factory + type 중복 차단)
#   4. Telegram 발송 (alert_service.send_telegram)
#   5. alerts 테이블 기록
