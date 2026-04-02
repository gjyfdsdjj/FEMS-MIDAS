# frontend/components/__init__.py
# 재사용 가능한 Streamlit 컴포넌트 모음
#
# - factory_card(factory_data)
#     공장 상태 카드: 온도 게이지, 습도, PWM, Andon 상태 배지
#
# - andon_badge(status)
#     상태에 따른 색상 배지 (NORMAL=초록 / WARNING=노랑 / EMERGENCY=빨강)
#
# - kpi_row(summary_data)
#     상단 KPI 지표 행 (st.columns + st.metric)
#
# - alert_panel(alerts)
#     미확인 알림 목록 (레벨별 색상, 확인 버튼)
#
# - schedule_gantt(factory_schedules)
#     Plotly Gantt 차트 (스케줄 블록 시각화)
#
# - api_get(path, params?) → dict
#     httpx.get() 래퍼, API_BASE_URL + Authorization 헤더 자동 처리
#     에러 시 st.error 표시
