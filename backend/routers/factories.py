# backend/routers/factories.py
# 공장 조회 엔드포인트
#
# GET /api/v1/factories
#   - 권한: viewer
#   - 4개 공장 전체 FactorySummary 목록 반환
#
# GET /api/v1/factories/{factory_id}
#   - 권한: viewer
#   - 공장 단건 상세 (target_temp_c, current_schedule_mode 추가 포함)
#   - factory_id 1~4 범위 벗어나면 404
