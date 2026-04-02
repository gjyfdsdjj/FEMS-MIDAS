# backend/routers/predict.py
# 예측 엔드포인트
#
# GET /api/v1/predict/temperature
#   - 권한: viewer
#   - Query: factory_id, horizon_hours(기본 24)
#   - Prophet 모델로 온도 예측 (predicted / lower_bound / upper_bound)
#
# GET /api/v1/predict/solar
#   - 권한: viewer
#   - Query: date
#   - 날씨 가중치 기반 시간대별 태양광 발전량 예측
#
# GET /api/v1/predict/maintenance
#   - 권한: admin
#   - Query: factory_id
#   - Isolation Forest / Prophet 결합으로 펠티어 소자 노후화 판정
#   - 응답: health_score, maintenance_risk(LOW|MEDIUM|HIGH), reason, recommended_action
