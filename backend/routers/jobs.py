# backend/routers/jobs.py
# 작업(생산 주문) 엔드포인트
#
# POST /api/v1/jobs
#   - 권한: admin
#   - 검증: target_units > 0, deadline_at > 현재 시각, 활성 job 중복 금지
#   - 등록 후 initial_required_factories 계산 (Q 기준 L1 로직)
#   - Job A 스케줄러 즉시 트리거
#
# GET /api/v1/jobs/current
#   - 권한: viewer
#   - 현재 활성 job 1건 반환 (없으면 404)
#
# PATCH /api/v1/jobs/{job_id}
#   - 권한: admin
#   - target_units / deadline_at / strategy 부분 수정
#   - 수정 후 스케줄 재계산 트리거
#
# POST /api/v1/jobs/{job_id}/close
#   - 권한: admin
#   - job 상태를 CLOSED로 변경, closed_at 기록
