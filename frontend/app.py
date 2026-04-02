# frontend/app.py
# Streamlit 앱 진입점
#
# - st.set_page_config: 레이아웃 wide, 타이틀 설정
# - 사이드바: 페이지 네비게이션 (대시보드 / 모바일 뷰)
# - URL 파라미터 확인:
#     ?view_mode=readonly&factory_id=X → pages/mobile_view.py 렌더
#     그 외 → pages/dashboard.py 렌더
# - API_BASE_URL 환경변수 로드 (백엔드 주소)
# - 세션 상태 초기화 (access_token, last_refresh_at 등)
#
# [절대 원칙]
# - 스케줄러, 백그라운드 작업 절대 금지 (Streamlit은 매번 전체 재실행됨)
# - 모든 데이터는 FastAPI 호출 결과만 사용
# - httpx.get() 으로 동기 호출 (Streamlit은 동기 환경)
