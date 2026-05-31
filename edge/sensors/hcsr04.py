import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

load_dotenv()

DETECT_DISTANCE_CM = 20

_DEFAULT_PINS = {
    1: (5, 22),
    2: (24, 25),
}


class HCSR04Reader:
    def __init__(self, factory_id: int = 1, trig: int = None, echo: int = None):
        self.factory_id = factory_id
        default_trig, default_echo = _DEFAULT_PINS.get(factory_id, (5, 22))
        self.trig = trig if trig is not None else int(os.getenv(f"FACTORY_{factory_id}_HCSR04_TRIG", default_trig))
        self.echo = echo if echo is not None else int(os.getenv(f"FACTORY_{factory_id}_HCSR04_ECHO", default_echo))
        self._setup_done = False

    def setup(self) -> None:
        if GPIO is None:
            raise RuntimeError("RPi.GPIO is not installed.")
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.trig, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.echo, GPIO.IN)
        self._setup_done = True

    def read_distance_cm(self) -> float | None:
        if not self._setup_done:
            return None
        GPIO.output(self.trig, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(self.trig, GPIO.LOW)

        timeout = time.time() + 0.05
        while GPIO.input(self.echo) == 0:
            if time.time() > timeout:
                return None
        pulse_start = time.time()

        timeout = time.time() + 0.05
        while GPIO.input(self.echo) == 1:
            if time.time() > timeout:
                return None
        pulse_end = time.time()

        distance = (pulse_end - pulse_start) * 17150
        return round(distance, 2)

    def check_and_log(self) -> None:
        distance = self.read_distance_cm()
        if distance is None:
            return
        if distance <= DETECT_DISTANCE_CM:
            print(f"[HC-SR04] factory={self.factory_id} 물체 감지: {distance}cm (기준 {DETECT_DISTANCE_CM}cm 이내) @ {datetime.now(timezone.utc).isoformat()}")

    def cleanup(self) -> None:
        if not self._setup_done:
            return
        GPIO.cleanup([self.trig, self.echo])
        self._setup_done = False
