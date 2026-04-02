# backend/routers/dashboard.py
# 대시보드용 집계 엔드포인트
#
# GET /api/v1/dashboard/summary
#   - 권한: viewer
#   - 상단 KPI 카드용: 가동 공장 수, 목표/생산/잔여 수량, 진행률
#     현재 TOU 요금, 일간/월간 절감액, 탄소 감축량, 위험도 지수
#
# GET /api/v1/dashboard/overview
#   - 권한: viewer
#   - 프론트 첫 로딩용 묶음 응답
#     summary + factories 목록 + current_job + schedule_preview + 미확인 alerts
