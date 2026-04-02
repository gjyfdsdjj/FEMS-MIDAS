# backend/services/prediction_service.py
# Prophet / Isolation Forest 기반 예측 및 예지 보전 로직
#
# - predict_temperature(factory_id, horizon_hours)
#     sensor_logs에서 학습 데이터 로드
#     Prophet 모델 학습/추론 (캐시 활용)
#     반환: List[{timestamp, predicted_temperature_c, lower_bound_c, upper_bound_c}]
#
# - predict_solar(date)
#     과거 태양광 발전량 + 환경 가중치(w_solar) 기반 시간대별 예측
#     반환: List[{timestamp, predicted_solar_kwh}]
#
# - assess_maintenance(factory_id)
#     '전력 투입 대비 온도 하강 효율' 지표 계산
#     Isolation Forest로 이상치 탐지
#     Prophet 예측 범위 이탈 지속 여부 결합 판정
#     반환: health_score(0~1), maintenance_risk, reason, recommended_action
#
# - _load_prophet_model(factory_id) : 모델 파일 로드 또는 신규 학습
# - _save_prophet_model(factory_id, model) : 모델 파일 저장
