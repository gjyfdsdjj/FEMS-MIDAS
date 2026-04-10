"""
HC-SR04 초음파센서 + LED 제어 (Raspberry Pi 4)
===============================================
배선:
  HC-SR04 VCC  → RPi 5V (핀2)
  HC-SR04 GND  → RPi GND (핀6)
  HC-SR04 TRIG → GPIO23 (핀16)
  HC-SR04 ECHO → 전압분배기(1kΩ+2kΩ) → GPIO24 (핀18)
  LED Anode    → 330Ω → GPIO18 (핀12)
  LED Cathode  → GND (핀14)

설치:
  sudo apt install -y python3-rpi.gpio
"""

import RPi.GPIO as GPIO
import time

# ── 설정 ─────────────────────────────────────────────────
TRIG_PIN       = 23     # GPIO23
ECHO_PIN       = 24     # GPIO24 (전압분배기 경유)
LED_PIN        = 18     # GPIO18
THRESHOLD_CM   = 20.0   # 감지 거리 (cm)
MEASURE_DELAY  = 0.1    # 측정 간격 (초)
ECHO_TIMEOUT   = 0.03   # ECHO 타임아웃 (초)
SPEED_OF_SOUND = 34300  # 음속 (cm/s)

# ── GPIO 초기화 ───────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(TRIG_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)
GPIO.setup(LED_PIN,  GPIO.OUT)
GPIO.output(TRIG_PIN, False)
GPIO.output(LED_PIN,  False)

print(f"[INFO] 감지 임계 거리: {THRESHOLD_CM} cm")
print(f"[INFO] Ctrl+C로 종료\n")
time.sleep(0.5)  # 센서 안정화

# ── 거리 측정 ─────────────────────────────────────────────
def measure_distance():
    # TRIG 10µs 펄스
    GPIO.output(TRIG_PIN, False)
    time.sleep(0.000002)
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, False)

    # ECHO HIGH 대기
    deadline = time.monotonic() + ECHO_TIMEOUT
    while GPIO.input(ECHO_PIN) == 0:
        if time.monotonic() > deadline:
            return None
    start = time.monotonic()

    # ECHO LOW 대기
    deadline = time.monotonic() + ECHO_TIMEOUT
    while GPIO.input(ECHO_PIN) == 1:
        if time.monotonic() > deadline:
            return None
    end = time.monotonic()

    return (end - start) * SPEED_OF_SOUND / 2.0

# ── 메인 루프 ─────────────────────────────────────────────
try:
    while True:
        dist = measure_distance()

        if dist is None:
            GPIO.output(LED_PIN, False)
            print("[----] 측정 실패")
        elif dist < THRESHOLD_CM:
            GPIO.output(LED_PIN, True)
            print(f"[DETECT] 거리: {dist:5.1f} cm  → LED ON  ●")
        else:
            GPIO.output(LED_PIN, False)
            print(f"[------] 거리: {dist:5.1f} cm  → LED OFF ○")

        time.sleep(MEASURE_DELAY)

except KeyboardInterrupt:
    print("\n[INFO] 종료")
finally:
    GPIO.output(LED_PIN, False)
    GPIO.cleanup()