import board
import adafruit_dht
from datetime import datetime, timezone

_BCM_TO_BOARD = {
    4: board.D4, 17: board.D17, 27: board.D27, 22: board.D22,
    5: board.D5, 6: board.D6, 13: board.D13, 19: board.D19,
    26: board.D26, 14: board.D14, 15: board.D15, 18: board.D18,
    23: board.D23, 24: board.D24, 25: board.D25, 8: board.D8,
    7: board.D7, 12: board.D12, 16: board.D16, 20: board.D20,
    21: board.D21,
}


class DHT22Reader:
    def __init__(self, factory_id: int, bcm_pin: int = 4):
        self.factory_id = factory_id
        board_pin = _BCM_TO_BOARD.get(bcm_pin)
        if board_pin is None:
            raise ValueError(f"지원하지 않는 BCM 핀: {bcm_pin}")
        self._device = adafruit_dht.DHT22(board_pin, use_pulseio=False)


    def read(self) -> dict | None:
        try:
            measured_at = datetime.now(timezone.utc).isoformat()
            temperature = self._device.temperature
            humidity = self._device.humidity
            if temperature is None or humidity is None:
                return None
            return {
                "temperature_c": round(temperature, 2),
                "humidity_pct": round(humidity, 2),
                "measured_at": measured_at,
            }
        except RuntimeError as e:
            print(f"[DHT22] 공장 {self.factory_id} 읽기 오류: {e}")
            return None

    def close(self):
        self._device.exit()
