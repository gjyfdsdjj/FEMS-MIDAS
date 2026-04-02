# edge/sensors/dht22.py
# DHT22 온습도 센서 읽기
#
# - DHT22Reader(gpio_pin) 클래스
#     read() → {temperature_c, humidity_pct, timestamp}
#     실패 시 최대 3회 재시도
#     연속 실패 시 None 반환 (상위에서 통신 이상 처리)
#
# - 공장별 GPIO 핀 매핑 (NODE_A 기준)
#     공장 1: GPIO 4  (Pin 7)
#     공장 2: GPIO 5  (Pin 29)
#   NODE_B 기준:
#     공장 3: GPIO 4  (Pin 7)
#     공장 4: GPIO 5  (Pin 29)
#
# - 라이브러리: Adafruit_DHT (adafruit-circuitpython-dht 또는 legacy adafruit_dht)
