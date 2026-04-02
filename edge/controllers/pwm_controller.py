# edge/controllers/pwm_controller.py
# BTS7960 모터 드라이버 PWM 제어 (펠티어 소자)
#
# - PWMController(gpio_pin, factory_id) 클래스
#     setup()    : GPIO 핀 출력 모드 설정, PWM 인스턴스 생성 (주파수 1kHz)
#     cleanup()  : GPIO 해제
#
# - set_duty_cycle(pct: int)
#     pct 0~100 유효성 검증
#     RPWM 핀에 PWM 듀티 사이클 적용
#     LPWM 핀은 항상 0 (단방향 냉각, 역방향 방지)
#
# - stop()   : 듀티 사이클 0% (펠티어 정지)
# - start()  : 마지막 설정 듀티 사이클로 재가동
#
# - 공장별 GPIO 핀 매핑 (NODE_A 기준)
#     공장 1: GPIO 18 (Pin 12, PWM0)
#     공장 2: GPIO 19 (Pin 35, PWM1)
#   NODE_B 기준:
#     공장 3: GPIO 18
#     공장 4: GPIO 19
