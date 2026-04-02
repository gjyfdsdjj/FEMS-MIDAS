# edge/main.py
# Edge 노드 (RPi4) 진입점
#
# - 환경변수 로드 (.env): NODE_ID(node_A or node_B), 담당 FACTORY_IDS([1,2] or [3,4])
# - 담당 공장 수만큼 센서/PWM 제어 인스턴스 초기화
# - MQTT 클라이언트 시작 (연결 + 구독)
# - APScheduler (또는 asyncio loop):
#     5초마다 sensor_reader 실행 → telemetry publish
# - Watchdog 타이머 피드 (정상 루프 유지 확인)
# - 예외 발생 시 SQLite 로컬 캐시에 데이터 저장
# - SIGTERM/SIGINT 핸들러: 안전 종료 (PWM 0% 후 연결 해제)
