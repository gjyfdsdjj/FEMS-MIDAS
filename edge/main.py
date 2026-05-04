import os
import time
import signal
from dotenv import load_dotenv
from communication.mqtt_client import EdgeMQTTClient
from controllers.peltier_command_runner import build_peltier_runner_from_env

try:
    from sensors.dht22 import DHT22Reader
except Exception as exc:
    DHT22Reader = None
    DHT22_IMPORT_ERROR = exc

load_dotenv()

NODE_ID = os.getenv("NODE_ID", "node_A")
FACTORY_IDS = [int(x.strip()) for x in os.getenv("FACTORY_IDS", "1").split(",") if x.strip()]
if not FACTORY_IDS:
    FACTORY_IDS = [1]
INTERVAL = 5  # 센서 읽기 주기 (초)
PELTIER_ENABLED = os.getenv("PELTIER_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
PELTIER_FACTORY_ID = int(os.getenv("PELTIER_FACTORY_ID", FACTORY_IDS[0]))

running = True


def handle_signal(sig, frame):
    global running
    print("종료 신호 수신, 안전 종료 중...")
    running = False


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def main():
    print(f"Edge 노드 시작: {NODE_ID}, 공장: {FACTORY_IDS}")

    mqtt = EdgeMQTTClient(NODE_ID, FACTORY_IDS)
    mqtt.connect()
    time.sleep(1)

    peltier_runner = None
    peltier_unavailable_status = None
    if PELTIER_ENABLED:
        try:
            peltier_runner = build_peltier_runner_from_env(
                status_callback=lambda status: mqtt.publish_peltier_status(PELTIER_FACTORY_ID, status)
            )
            peltier_runner.start()
        except Exception as exc:
            print(f"[PELTIER] disabled after startup error: {exc}")
            peltier_unavailable_status = {
                "component": "peltier",
                "available": False,
                "state": "unavailable",
                "last_error": str(exc),
            }
            mqtt.publish_peltier_status(PELTIER_FACTORY_ID, peltier_unavailable_status)
            peltier_runner = None

    def handle_command(command):
        factory_id = command.get("factory_id")
        if factory_id != PELTIER_FACTORY_ID:
            return

        if peltier_runner is None:
            mqtt.publish_peltier_status(
                PELTIER_FACTORY_ID,
                {
                    "component": "peltier",
                    "available": False,
                    "state": "unavailable",
                    "last_action": command.get("action"),
                    "last_command_id": command.get("command_id"),
                    "last_error": "peltier runner is not available",
                },
            )
            return

        peltier_runner.submit(command)

    mqtt.command_handler = handle_command

    sensors = {}

    def publish_peltier_snapshot():
        try:
            if peltier_runner is not None:
                mqtt.publish_peltier_status(PELTIER_FACTORY_ID, peltier_runner.status_payload())
            elif peltier_unavailable_status is not None:
                mqtt.publish_peltier_status(PELTIER_FACTORY_ID, peltier_unavailable_status)
        except Exception as exc:
            print(f"[PELTIER] status snapshot publish failed: {exc}")

    try:
        if DHT22Reader is None:
            print(f"[DHT22] disabled after import error: {DHT22_IMPORT_ERROR}")
        else:
            for factory_id in FACTORY_IDS:
                try:
                    sensors[factory_id] = DHT22Reader(factory_id)
                except Exception as exc:
                    print(f"[DHT22] factory={factory_id} disabled after startup error: {exc}")

        while running:
            mqtt.reconnect_if_needed()
            publish_peltier_snapshot()
            for factory_id, sensor in sensors.items():
                data = sensor.read()
                if data:
                    mqtt.publish_telemetry(
                        factory_id,
                        data["temperature_c"],
                        data["humidity_pct"],
                        data["measured_at"],
                    )
                else:
                    print(f"공장 {factory_id} 센서 읽기 실패, 건너뜀")
            time.sleep(INTERVAL)
    finally:
        for sensor in sensors.values():
            sensor.close()
        if peltier_runner is not None:
            peltier_runner.shutdown()
        mqtt.disconnect()
        print("Edge 노드 종료 완료")


if __name__ == "__main__":
    main()
