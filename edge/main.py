import os
import time
import signal
import threading
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from communication.mqtt_client import EdgeMQTTClient
from sensors.dht22 import DHT22Reader
from analytics.peltier_manual import PeltierController, Pins

load_dotenv()

NODE_ID = os.getenv("NODE_ID", "node_A")
FACTORY_IDS = [int(x) for x in os.getenv("FACTORY_IDS", "1,2").split(",")]
INTERVAL = 5  # 센서 읽기 주기 (초)
PELTIER_DUTY = float(os.getenv("PELTIER_DUTY", "30.0"))
PELTIER_CHECK_INTERVAL = 5  # 냉각 중 센서 확인 주기 (초)

running = True
_cooling_threads: dict[int, threading.Thread] = {}
_cooling_stop_events: dict[int, threading.Event] = {}


def handle_signal(sig, frame):
    global running
    print("종료 신호 수신, 안전 종료 중...")
    running = False
    for event in _cooling_stop_events.values():
        event.set()


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def _update_schedule_end_at(factory_id: int, end_at: datetime) -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print(f"[DB] DATABASE_URL 없음, end_at 업데이트 생략")
        return
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE schedules SET end_at = :end_at "
                    "WHERE factory_id = :factory_id AND end_at IS NULL "
                    "ORDER BY start_at DESC LIMIT 1"
                ),
                {"end_at": end_at, "factory_id": factory_id},
            )
            conn.commit()
        print(f"[DB] factory={factory_id} schedules.end_at 업데이트 완료: {end_at.isoformat()}")
    except Exception as e:
        print(f"[DB] end_at 업데이트 실패: {e}")


def _cool_to_target(factory_id: int, target_temp: float, sensor: DHT22Reader, stop_event: threading.Event):
    controller = PeltierController(pins=Pins())
    print(f"[Peltier] factory={factory_id} 목표온도 {target_temp}°C 까지 냉각 시작")
    end_at_recorded = False
    try:
        controller.setup()
        controller.start(duty=PELTIER_DUTY, direction="forward")
        while not stop_event.is_set():
            data = sensor.read()
            if data is None:
                time.sleep(PELTIER_CHECK_INTERVAL)
                continue
            current = data["temperature_c"]
            print(f"[Peltier] factory={factory_id} 현재={current}°C 목표={target_temp}°C")
            if current <= target_temp:
                print(f"[Peltier] factory={factory_id} 목표온도 도달, 정지")
                _update_schedule_end_at(factory_id, datetime.now(timezone.utc))
                end_at_recorded = True
                break
            time.sleep(PELTIER_CHECK_INTERVAL)
    except Exception as e:
        print(f"[Peltier] factory={factory_id} 오류: {e}")
    finally:
        if not end_at_recorded:
            _update_schedule_end_at(factory_id, datetime.now(timezone.utc))
        try:
            controller.stop()
            controller.cleanup()
        except Exception:
            pass


def make_command_handler(sensors: dict[int, DHT22Reader]):
    def handle_command(factory_id: int, action: str, payload: dict):
        if action != "SET_TARGET_TEMP":
            print(f"[CMD] 미지원 명령: {action}")
            return

        target_temp = float(payload.get("value", -18.0))
        print(f"[CMD] 스케줄 수신 ✓ factory={factory_id}, 목표온도={target_temp}°C")
        sensor = sensors.get(factory_id)
        if sensor is None:
            print(f"[CMD] factory={factory_id} 센서 없음, 무시")
            return

        # 기존 냉각 중이면 중단 후 대기
        if factory_id in _cooling_stop_events:
            _cooling_stop_events[factory_id].set()
        if factory_id in _cooling_threads:
            _cooling_threads[factory_id].join(timeout=10)

        stop_event = threading.Event()
        _cooling_stop_events[factory_id] = stop_event
        t = threading.Thread(
            target=_cool_to_target,
            args=(factory_id, target_temp, sensor, stop_event),
            daemon=True,
        )
        _cooling_threads[factory_id] = t
        t.start()

    return handle_command


def main():
    print(f"Edge 노드 시작: {NODE_ID}, 공장: {FACTORY_IDS}")

    mqtt = EdgeMQTTClient(NODE_ID, FACTORY_IDS)
    mqtt.connect()
    time.sleep(1)

    sensors = {fid: DHT22Reader(fid) for fid in FACTORY_IDS}
    mqtt.on_command = make_command_handler(sensors)

    try:
        while running:
            mqtt.reconnect_if_needed()
            for factory_id in FACTORY_IDS:
                data = sensors[factory_id].read()
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
        for event in _cooling_stop_events.values():
            event.set()
        for sensor in sensors.values():
            sensor.close()
        mqtt.disconnect()
        print("Edge 노드 종료 완료")


if __name__ == "__main__":
    main()
