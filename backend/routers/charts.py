# backend/routers/charts.py
# 차트 데이터 엔드포인트
#
# GET /api/v1/charts/hourly
#   - 권한: viewer
#   - Query: date, type(cost|power|saving|solar)
#   - 시간대별 최적화 전/후 전력/비용 비교 + 태양광 기여량
#   - 응답: labels(시간), before_optimization / after_optimization / solar_contribution
#
# GET /api/v1/charts/factory/{factory_id}
#   - 권한: viewer
#   - Query: metric(temperature|humidity|pwm), days(기본 7)
#   - 공장별 N일 시계열 포인트 반환
#
# GET /api/v1/charts/savings
#   - 권한: viewer
#   - Query: range(daily|monthly), from, to
#   - 일간 또는 월간 절감액 누적 그래프용 데이터
