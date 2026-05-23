#!/usr/bin/env python3
"""
Manual controller for:
- Raspberry Pi 4
- BTS7960 H-bridge driver
- TEC1-12706 / JK-A-CH1 Peltier
- AO3406 MOSFET driver for two fans

Default wiring, BCM numbering:
GPIO18 -> BTS7960 RPWM
GPIO19 -> BTS7960 LPWM
GPIO20 -> BTS7960 R_EN
GPIO21 -> BTS7960 L_EN
GPIO23 -> AO3406 IN

Run examples:
sudo python3 edge/peltier_bts7960_manual.py --duty 0 --seconds 5
sudo python3 edge/peltier_bts7960_manual.py --duty 10 --seconds 30
sudo python3 edge/peltier_bts7960_manual.py --duty 20 --seconds 60
sudo python3 edge/peltier_bts7960_manual.py --duty 30 --seconds 300
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from dataclasses import dataclass
from typing import Literal, Optional

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None


Direction = Literal["forward", "reverse"]
running = True


@dataclass(frozen=True)
class Pins:
    rpwm: int = 18
    lpwm: int = 19
    r_en: int = 20
    l_en: int = 21
    fan: Optional[int] = 23


class PeltierController:
    def __init__(
        self,
        pins: Pins,
        pwm_hz: int = 1000,
        fan_active_low: bool = False,
        fan_spinup_seconds: float = 2.0,
        fan_cooldown_seconds: float = 30.0,
        reverse_settle_seconds: float = 0.2,
    ) -> None:
        if GPIO is None:
            raise RuntimeError("RPi.GPIO is not installed. Run this on Raspberry Pi OS.")

        self.pins = pins
        self.pwm_hz = pwm_hz
        self.fan_active_low = fan_active_low
        self.fan_spinup_seconds = fan_spinup_seconds
        self.fan_cooldown_seconds = fan_cooldown_seconds
        self.reverse_settle_seconds = reverse_settle_seconds

        self._rpwm = None
        self._lpwm = None
        self._setup_done = False
        self._direction: Direction = "forward"
        self._duty = 0.0

    def setup(self) -> None:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # BTS7960 control pins
        for pin in [self.pins.rpwm, self.pins.lpwm, self.pins.r_en, self.pins.l_en]:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

        # Fan MOSFET pin
        if self.pins.fan is not None:
            GPIO.setup(self.pins.fan, GPIO.OUT, initial=self._fan_level(False))

        self._rpwm = GPIO.PWM(self.pins.rpwm, self.pwm_hz)
        self._lpwm = GPIO.PWM(self.pins.lpwm, self.pwm_hz)
        self._rpwm.start(0)
        self._lpwm.start(0)

        self._setup_done = True
        print("[SETUP] GPIO initialized.")

    def start(self, duty: float, direction: Direction) -> None:
        self._require_setup()

        print("[START] Fan ON")
        self.set_fan(True)

        if self.fan_spinup_seconds > 0:
            print(f"[START] Waiting {self.fan_spinup_seconds:.1f}s for fan spin-up...")
            time.sleep(self.fan_spinup_seconds)

        print("[START] BTS7960 enable")
        self.enable_bridge(True)

        print(f"[START] Peltier PWM {duty:.1f}% / direction={direction}")
        self.set_drive(duty, direction)

    def stop(self, keep_fan_running: bool = True) -> None:
        if not self._setup_done:
            return

        print("[STOP] Peltier PWM 0")
        self.set_drive(0, self._direction)

        print("[STOP] BTS7960 disable")
        self.enable_bridge(False)

        if keep_fan_running and self.pins.fan is not None and self.fan_cooldown_seconds > 0:
            print(f"[STOP] Fan cooldown {self.fan_cooldown_seconds:.1f}s...")
            time.sleep(self.fan_cooldown_seconds)

        print("[STOP] Fan OFF")
        self.set_fan(False)

    def cleanup(self) -> None:
        if not self._setup_done:
            return

        try:
            self.set_drive(0, self._direction)
            self.enable_bridge(False)
            self.set_fan(False)
        finally:
            if self._rpwm is not None:
                self._rpwm.stop()
            if self._lpwm is not None:
                self._lpwm.stop()

            pins_to_cleanup = [
                self.pins.rpwm,
                self.pins.lpwm,
                self.pins.r_en,
                self.pins.l_en,
            ]
            if self.pins.fan is not None:
                pins_to_cleanup.append(self.pins.fan)

            GPIO.cleanup(pins_to_cleanup)
            self._setup_done = False
            print("[CLEANUP] GPIO cleaned up.")

    def set_drive(self, duty: float, direction: Direction) -> None:
        self._require_setup()

        if direction not in ("forward", "reverse"):
            raise ValueError("direction must be 'forward' or 'reverse'")

        duty = max(0.0, min(100.0, float(duty)))

        if self._rpwm is None or self._lpwm is None:
            raise RuntimeError("PWM is not initialized.")

        # If direction changes while running, stop both sides briefly.
        if direction != self._direction and self._duty > 0:
            self._rpwm.ChangeDutyCycle(0)
            self._lpwm.ChangeDutyCycle(0)
            time.sleep(self.reverse_settle_seconds)

        if direction == "forward":
            self._lpwm.ChangeDutyCycle(0)
            self._rpwm.ChangeDutyCycle(duty)
        else:
            self._rpwm.ChangeDutyCycle(0)
            self._lpwm.ChangeDutyCycle(duty)

        self._duty = duty
        self._direction = direction

    def enable_bridge(self, enabled: bool) -> None:
        self._require_setup()
        level = GPIO.HIGH if enabled else GPIO.LOW
        GPIO.output(self.pins.r_en, level)
        GPIO.output(self.pins.l_en, level)

    def set_fan(self, enabled: bool) -> None:
        self._require_setup()
        if self.pins.fan is None:
            return
        GPIO.output(self.pins.fan, self._fan_level(enabled))

    def _fan_level(self, enabled: bool) -> int:
        if self.fan_active_low:
            return GPIO.LOW if enabled else GPIO.HIGH
        return GPIO.HIGH if enabled else GPIO.LOW

    def _require_setup(self) -> None:
        if not self._setup_done:
            raise RuntimeError("Call setup() first.")


def handle_signal(signum, frame) -> None:
    global running
    running = False
    print("\n[SIGNAL] Stop requested.")


def optional_pin(value: str) -> Optional[int]:
    pin = int(value)
    return None if pin < 0 else pin


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BTS7960 + AO3406 Peltier manual test")

    parser.add_argument("--duty", type=float, default=20.0, help="Peltier PWM duty, 0-100")
    parser.add_argument("--seconds", type=float, default=60.0, help="Run seconds. 0 means until Ctrl+C.")
    parser.add_argument("--direction", choices=["forward", "reverse"], default="forward")

    parser.add_argument("--rpwm-pin", type=int, default=18)
    parser.add_argument("--lpwm-pin", type=int, default=19)
    parser.add_argument("--ren-pin", type=int, default=20)
    parser.add_argument("--len-pin", type=int, default=21)
    parser.add_argument("--fan-pin", type=optional_pin, default=23, help="AO3406 IN pin. Use -1 to disable.")

    parser.add_argument("--pwm-hz", type=int, default=1000)
    parser.add_argument("--fan-active-low", action="store_true")
    parser.add_argument("--fan-spinup", type=float, default=2.0)
    parser.add_argument("--fan-cooldown", type=float, default=30.0)

    parser.add_argument(
        "--max-duty",
        type=float,
        default=50.0,
        help="Safety cap. Default prevents accidental high duty.",
    )
    parser.add_argument(
        "--allow-high-duty",
        action="store_true",
        help="Allow duty above --max-duty.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.duty < 0 or args.duty > 100:
        print("[ERROR] --duty must be between 0 and 100.")
        return 2

    if args.duty > args.max_duty and not args.allow_high_duty:
        print(
            f"[ERROR] Requested duty {args.duty:.1f}% exceeds safety cap {args.max_duty:.1f}%.\n"
            f"        Use --allow-high-duty only after low-duty tests are stable."
        )
        return 2

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    pins = Pins(
        rpwm=args.rpwm_pin,
        lpwm=args.lpwm_pin,
        r_en=args.ren_pin,
        l_en=args.len_pin,
        fan=args.fan_pin,
    )

    controller = PeltierController(
        pins=pins,
        pwm_hz=args.pwm_hz,
        fan_active_low=args.fan_active_low,
        fan_spinup_seconds=args.fan_spinup,
        fan_cooldown_seconds=args.fan_cooldown,
    )

    print("========================================")
    print("BTS7960 + AO3406 Peltier Manual Control")
    print("========================================")
    print(f"RPWM GPIO{pins.rpwm}")
    print(f"LPWM GPIO{pins.lpwm}")
    print(f"R_EN GPIO{pins.r_en}")
    print(f"L_EN GPIO{pins.l_en}")
    print(f"Fan  GPIO{pins.fan if pins.fan is not None else 'disabled'}")
    print(f"Duty {args.duty:.1f}%")
    print(f"Direction {args.direction}")
    print(f"Seconds {args.seconds}")
    print("----------------------------------------")

    try:
        controller.setup()
        controller.start(args.duty, args.direction)

        started_at = time.monotonic()

        while running:
            elapsed = time.monotonic() - started_at

            if args.seconds > 0 and elapsed >= args.seconds:
                print("[TIMER] Requested run time reached.")
                break

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[KEYBOARD] Ctrl+C received.")

    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    finally:
        try:
            controller.stop(keep_fan_running=True)
        finally:
            controller.cleanup()

    print("[DONE] Safe stop complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
