# frontend/pages/mobile_view.py
# QR 모바일 읽기 전용 페이지
#
# - URL 파라미터에서 token 추출
#   (?view_mode=readonly&factory_id=X 방식이 아닌 readonly token 방식 사용)
# - GET /api/v1/readonly/{token} 호출
#   토큰 만료 or 유효하지 않으면 에러 메시지 표시 후 종료
#
# [표시 내용 - 모바일 최적화 레이아웃]
# - 공장명 / 현재 상태 배지
# - 현재 온도 (대형 숫자 + 게이지)
# - 현재 스케줄 모드
# - 다음 스케줄 블록 (시작/종료 시각, 모드)
# - 마지막 업데이트 시각
#
# [제어 기능 전면 비활성화]
# - 버튼, 입력 위젯 일절 없음
# - 30초 자동 새로고침 (st.rerun + time.sleep 또는 meta refresh)
