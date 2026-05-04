import json
import asyncio
import os
import paho.mqtt.client as mqtt
from datetime import datetime
from database.connection import AsyncSessionLocal
from database.models import Factory, SensorLog
from mqtt.status_store import status_store


class MQTTSubscriber:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def start(self):
        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", 1883))
        self.client.connect(host, port)
        self.client.loop_start()
        print(f"MQTT 구독 시작: {host}:{port}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("MQTT 브로커 연결 성공")
            client.subscribe("factory/+/+/telemetry")
            client.subscribe("factory/+/+/peltier/status")
        else:
            print(f"MQTT 연결 실패: {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            if topic.endswith("/telemetry"):
                asyncio.run_coroutine_threadsafe(self._save(payload), self.loop)
            elif topic.endswith("/peltier/status"):
                self._save_peltier_status(topic, payload)
        except Exception as e:
            print(f"MQTT 메시지 처리 오류: {e}")

    def _save_peltier_status(self, topic: str, payload: dict):
        try:
            parts = topic.split("/")
            node_id = payload.get("node_id") or parts[1]
            factory_id = int(payload.get("factory_id") or parts[2])
            status_store.update_peltier_status(node_id, factory_id, payload)
            print(f"상태 저장: factory={factory_id}, component=peltier, state={payload.get('state')}")
        except Exception as e:
            print(f"상태 저장 오류: {e}")

    async def _save(self, payload):
        try:
            async with AsyncSessionLocal() as session:
                ts_raw = payload.get("timestamp")
                measured_at = datetime.fromisoformat(ts_raw) if ts_raw else None
                log = SensorLog(
                    factory_id=payload["factory_id"],
                    node_id=payload.get("node_id"),
                    temperature_c=payload.get("temperature_c"),
                    humidity_pct=payload.get("humidity_pct"),
                    measured_at=measured_at,
                )
                session.add(log)
                factory = await session.get(Factory, payload["factory_id"])
                if factory is None:
                    factory = Factory(factory_id=payload["factory_id"], name=f"Factory {payload['factory_id']}")
                    session.add(factory)
                factory.current_temp = payload.get("temperature_c")
                factory.current_humidity = payload.get("humidity_pct")
                factory.last_seen_at = measured_at
                await session.commit()
                print(f"저장 완료: factory={payload['factory_id']}, "
                      f"temp={payload.get('temperature_c')}°C, "
                      f"humidity={payload.get('humidity_pct')}%")
        except Exception as e:
            print(f"DB 저장 오류: {e}")
