# backend/routers/schedule.py
# 스케줄 최적화 엔드포인트
#
# POST /api/v1/schedule/compute
#   - 권한: admin
#   - 즉시 최적화 계산 실행 (optimization_service 호출)
#   - apply_immediately=true 면 MQTT 명령 발행까지 수행
#   - 응답: schedule_id, computed_at, 예상 절감액, applied 여부
#
# GET /api/v1/schedule/optimal
#   - 권한: viewer
#   - Query: job_id?, factory_id?, horizon_hours?(기본 24)
#   - 현재 적용 중인 최신 스케줄 블록 반환
#
# GET /api/v1/schedule/logs
#   - 권한: admin
#   - 스케줄 변경 이력 (변경 시각, 이유, 예상 절감액) 커서 페이지네이션
