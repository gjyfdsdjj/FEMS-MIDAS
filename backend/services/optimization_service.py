# backend/services/optimization_service.py
# PuLP 기반 스케줄 최적화 로직
#
# - run_optimization(job, sensor_states, tou_prices, env_weights, solar_forecast)
#     반환: List[ScheduleBlock] (공장별 블록 리스트)
#
#   [목적함수]
#     Minimize Σ(Grid_Power[t] × TOU_Price[t]) - (Solar_Predicted[t] × w_solar)
#
#   [제약 조건]
#     1. 식품 안전 온도: T_in[t] <= -18°C 항상 유지
#     2. 열 손실 방정식: T_in[t+1] = T_in[t] + (BaseLeakage × w_temp) - Cooling[t]
#     3. Short Cycle 방지: 가동/정지 전환 간격 최소 30분
#     4. 생산량 보장: 남은 시간 내 R 단위 이상 생산
#     5. 수동 정지 공장(manual_stop=True)은 변수에서 제외
#
#   [운영 전략 적용]
#     심야(저렴): 목표 온도를 -25°C ~ -27°C 로 과냉각 (축냉)
#     주간(비쌈): Coasting 모드 — 냉각 장치 최소화, 축적된 냉기로 유지
#
# - calculate_required_factories(remaining_units, remaining_time_hours)
#     L1 로직: Q 비율에 따라 필요 공장 수(1~4) 반환
#
# - estimate_savings(schedule_blocks, baseline_kwh, tou_prices)
#     최적화 전/후 전력 비용 차액 계산 → 일간/월간 절감액 반환
