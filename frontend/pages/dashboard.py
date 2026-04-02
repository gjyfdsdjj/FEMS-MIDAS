# frontend/pages/dashboard.py
# 메인 대시보드 페이지
#
# [데이터 로딩]
# - GET /api/v1/dashboard/overview 한 번 호출로 전체 데이터 수신
# - st.session_state + time.time() 비교로 30초 polling 간격 구현
#
# [상단 상태바]
# - GET /api/v1/system/status
# - 전체 제어 모드(AUTO/MANUAL), 통신 상태, 위험도 지수 표시
# - 위험도 80 초과 시 화면 배경 붉게 처리 (st.markdown custom CSS)
#
# [KPI 카드 행]  ← st.columns + st.metric
# - 가동 공장 수 / 생산 진행률 / 일간 절감액 / 탄소 감축량 / 현재 TOU 요금
#
# [공장 카드 4개]  ← st.columns(4)
# - 각 공장: 온도(게이지), 습도, PWM%, 상태 배지(Andon 색상)
# - 통신 상태 아이콘
#
# [스케줄 타임라인]
# - GET /api/v1/schedule/optimal
# - Plotly Gantt 차트로 공장별 ON/OFF/PRECOOL/COASTING 블록 표시
#
# [시간별 전력/비용 차트]
# - GET /api/v1/charts/hourly
# - Plotly 라인 차트: 최적화 전/후 비교 + 태양광 기여량
#
# [7일 시계열 차트]
# - GET /api/v1/charts/factory/{factory_id}
# - 공장 선택 selectbox + 지표 선택 (온도/습도/PWM)
#
# [절감액 누적 그래프]
# - GET /api/v1/charts/savings
# - 일간/월간 탭 전환
#
# [알림 패널]
# - GET /api/v1/alerts?is_acknowledged=false
# - 미확인 알림 목록, 레벨별 색상 구분
#
# [수동 제어 패널]  ← 관리자 로그인 시에만 표시
# - POST /api/v1/control/manual 호출 버튼
# - 긴급 전체 정지 / 전체 재가동 버튼
