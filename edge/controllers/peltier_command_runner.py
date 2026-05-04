from __future__ import annotations

import os
import queue
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from analytics.peltier_manual import Direction, PeltierController, Pins


Command = dict[str, Any]
TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_UNSET = object()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _env_optional_pin(name: str, default: int) -> Optional[int]:
    pin = _env_int(name, default)
    return None if pin < 0 else pin


def _payload_float(payload: dict[str, Any], key: str, default: float) -> float:
    value = payload.get(key, default)
    return float(value)


def _payload_bool(payload: dict[str, Any], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in TRUE_VALUES
    return bool(value)


def _payload_direction(payload: dict[str, Any]) -> Direction:
    direction = str(payload.get("direction", "forward"))
    if direction not in ("forward", "reverse"):
        raise ValueError("direction must be forward or reverse")
    return direction


class PeltierCommandRunner:
    def __init__(
        self,
        controller: PeltierController,
        default_max_duty: float = 50.0,
        status_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        self.controller = controller
        self.default_max_duty = default_max_duty
        self.status_callback = status_callback
        self._queue: queue.Queue[Optional[Command]] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="peltier-command-runner", daemon=True)
        self._stop_timer: Optional[threading.Timer] = None
        self._started = False
        self._state = "offline"
        self._fan_on = False
        self._bridge_enabled = False
        self._last_action: Optional[str] = None
        self._last_command_id: Optional[str] = None
        self._last_error: Optional[str] = None

    def start(self) -> None:
        self.controller.setup()
        self._started = True
        self._thread.start()
        self._state = "ready"
        self._emit_status()
        print("[PELTIER] command runner started")

    def submit(self, command: Command) -> None:
        if not self._started:
            print("[PELTIER] command ignored because runner is not started")
            return
        self._last_command_id = command.get("command_id")
        self._last_action = str(command.get("action", "")).upper()
        self._emit_status(state="queued", last_error=None)
        self._queue.put(command)

    def shutdown(self) -> None:
        if not self._started:
            return

        self._cancel_stop_timer()
        self._queue.put(None)
        self._thread.join()
        try:
            was_driving = getattr(self.controller, "_duty", 0.0) > 0
            self.controller.stop(keep_fan_running=was_driving)
            self._fan_on = False
            self._bridge_enabled = False
            self._state = "stopped"
        finally:
            self.controller.cleanup()
            self._started = False
            self._state = "offline"
            self._emit_status()
            print("[PELTIER] command runner stopped")

    def _run(self) -> None:
        while True:
            command = self._queue.get()
            try:
                if command is None:
                    return
                self._handle(command)
            except Exception as exc:
                self._last_error = str(exc)
                self._state = "error"
                self._emit_status()
                print(f"[PELTIER] command error: {exc}")
            finally:
                self._queue.task_done()

    def _handle(self, command: Command) -> None:
        action = str(command.get("action", "")).upper()
        self._last_action = action
        self._last_command_id = command.get("command_id")
        self._emit_status(state="processing", last_error=None)
        payload = command.get("payload") or {}
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")

        self._apply_config_payload(payload)

        if action == "START":
            duty = self._validated_duty(payload)
            direction = _payload_direction(payload)
            self._cancel_stop_timer()
            self.controller.start(duty, direction)
            self._fan_on = True
            self._bridge_enabled = True
            self._state = "running" if duty > 0 else "ready"
            self._schedule_stop(payload)
            self._emit_status(last_error=None)
            print(f"[PELTIER] START duty={duty:.1f} direction={direction}")
            return

        if action == "SET_PWM":
            duty = self._validated_duty(payload)
            direction = _payload_direction(payload)
            self._cancel_stop_timer()
            if getattr(self.controller, "_duty", 0.0) > 0:
                self.controller.set_drive(duty, direction)
            else:
                self.controller.start(duty, direction)
                self._fan_on = True
                self._bridge_enabled = True
            self._state = "running" if duty > 0 else "ready"
            self._schedule_stop(payload)
            self._emit_status(last_error=None)
            print(f"[PELTIER] SET_PWM duty={duty:.1f} direction={direction}")
            return

        if action == "STOP":
            self._cancel_stop_timer()
            keep_fan_running = _payload_bool(payload, "keep_fan_running", True)
            self.controller.stop(keep_fan_running=keep_fan_running)
            self._fan_on = False
            self._bridge_enabled = False
            self._state = "stopped"
            self._emit_status(last_error=None)
            print("[PELTIER] STOP")
            return

        if action == "FAN_ON":
            self.controller.set_fan(True)
            self._fan_on = True
            self._state = "fan_on"
            self._emit_status(last_error=None)
            print("[PELTIER] FAN_ON")
            return

        if action == "FAN_OFF":
            self.controller.set_fan(False)
            self._fan_on = False
            self._state = "ready" if getattr(self.controller, "_duty", 0.0) <= 0 else "running"
            self._emit_status(last_error=None)
            print("[PELTIER] FAN_OFF")
            return

        raise ValueError(f"unsupported action: {action}")

    def _apply_config_payload(self, payload: dict[str, Any]) -> None:
        if "fan_active_low" in payload:
            self.controller.fan_active_low = _payload_bool(payload, "fan_active_low", self.controller.fan_active_low)
        if "fan_spinup_seconds" in payload:
            self.controller.fan_spinup_seconds = _payload_float(payload, "fan_spinup_seconds", self.controller.fan_spinup_seconds)
        if "fan_cooldown_seconds" in payload:
            self.controller.fan_cooldown_seconds = _payload_float(payload, "fan_cooldown_seconds", self.controller.fan_cooldown_seconds)

    def _validated_duty(self, payload: dict[str, Any]) -> float:
        duty = _payload_float(payload, "value", 0.0)
        max_duty = _payload_float(payload, "max_duty", self.default_max_duty)
        allow_high_duty = _payload_bool(payload, "allow_high_duty", False)

        if not 0 <= duty <= 100:
            raise ValueError("value must be between 0 and 100")
        if not 0 <= max_duty <= 100:
            raise ValueError("max_duty must be between 0 and 100")
        if duty > max_duty and not allow_high_duty:
            raise ValueError(f"value {duty:.1f} exceeds max_duty {max_duty:.1f}")
        return duty

    def _schedule_stop(self, payload: dict[str, Any]) -> None:
        seconds = _payload_float(payload, "seconds", 0.0)
        if seconds <= 0:
            return

        stop_payload = {
            "keep_fan_running": _payload_bool(payload, "keep_fan_running", True),
            "fan_cooldown_seconds": self.controller.fan_cooldown_seconds,
            "reason": "timer",
        }
        timer = threading.Timer(seconds, lambda: self.submit({"action": "STOP", "payload": stop_payload}))
        timer.daemon = True
        self._stop_timer = timer
        timer.start()

    def _cancel_stop_timer(self) -> None:
        if self._stop_timer is not None:
            self._stop_timer.cancel()
            self._stop_timer = None

    def _emit_status(self, state: Optional[str] = None, last_error: Any = _UNSET) -> None:
        if state is not None:
            self._state = state
        if last_error is not _UNSET:
            self._last_error = last_error

        if self.status_callback is None:
            return

        try:
            self.status_callback(self.status_payload())
        except Exception as exc:
            print(f"[PELTIER] status publish error: {exc}")

    def status_payload(self) -> dict[str, Any]:
        pins = getattr(self.controller, "pins", None)
        duty = float(getattr(self.controller, "_duty", 0.0))
        direction = getattr(self.controller, "_direction", "forward")
        fan_pin = getattr(pins, "fan", None)

        return {
            "component": "peltier",
            "available": self._started,
            "state": self._state,
            "running": duty > 0,
            "duty": duty,
            "direction": direction,
            "fan_on": self._fan_on if fan_pin is not None else None,
            "bridge_enabled": self._bridge_enabled,
            "last_action": self._last_action,
            "last_command_id": self._last_command_id,
            "last_error": self._last_error,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "capabilities": {
                "peltier_pwm": True,
                "direction": True,
                "fan": fan_pin is not None,
            },
        }


def build_peltier_runner_from_env(
    status_callback: Optional[Callable[[dict[str, Any]], None]] = None,
) -> PeltierCommandRunner:
    pins = Pins(
        rpwm=_env_int("PELTIER_RPWM_PIN", 18),
        lpwm=_env_int("PELTIER_LPWM_PIN", 19),
        r_en=_env_int("PELTIER_REN_PIN", 20),
        l_en=_env_int("PELTIER_LEN_PIN", 21),
        fan=_env_optional_pin("PELTIER_FAN_PIN", 23),
    )
    controller = PeltierController(
        pins=pins,
        pwm_hz=_env_int("PELTIER_PWM_HZ", 1000),
        fan_active_low=_env_bool("PELTIER_FAN_ACTIVE_LOW", False),
        fan_spinup_seconds=_env_float("PELTIER_FAN_SPINUP_SECONDS", 2.0),
        fan_cooldown_seconds=_env_float("PELTIER_FAN_COOLDOWN_SECONDS", 30.0),
    )
    return PeltierCommandRunner(
        controller=controller,
        default_max_duty=_env_float("PELTIER_MAX_DUTY", 50.0),
        status_callback=status_callback,
    )
