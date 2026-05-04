import json
import os
from typing import Callable, Optional

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from storage.local_buffer import LocalBuffer

load_dotenv()


class EdgeMQTTClient:
    def __init__(
        self,
        node_id: str,
        factory_ids: list,
        command_handler: Optional[Callable[[dict], None]] = None,
    ):
        self.node_id = node_id
        self.factory_ids = factory_ids
        self.command_handler = command_handler
        self._connected = False
        self._buffer = LocalBuffer()
        self._pending_acks = {}  # mid → db_id
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish

    def connect(self):
        self._host = os.getenv("MQTT_HOST", "localhost")
        self._port = int(os.getenv("MQTT_PORT", 1883))
        self.client.loop_start()
        try:
            self.client.connect(self._host, self._port)
            print(f"MQTT 브로커 연결 중: {self._host}:{self._port}")
        except Exception as e:
            print(f"브로커 초기 연결 실패: {e}, 버퍼링 모드로 시작")

    def reconnect_if_needed(self):
        if not self._connected:
            try:
                self.client.reconnect()
            except Exception:
                pass

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            print("브로커 연결 성공")
            for factory_id in self.factory_ids:
                topic = f"factory/{self.node_id}/{factory_id}/command"
                client.subscribe(topic)
                print(f"구독: {topic}")
            self._flush_buffer()
        else:
            self._connected = False
            print(f"브로커 연결 실패: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            print(f"브로커 연결 끊김 (rc={rc}), 버퍼링 모드 전환")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"명령 수신: {msg.topic} → {payload}")
            if self.command_handler is not None:
                payload = self._with_topic_metadata(msg.topic, payload)
                self.command_handler(payload)
        except Exception as e:
            print(f"명령 처리 오류: {e}")

    def _with_topic_metadata(self, topic: str, payload: dict) -> dict:
        parts = topic.split("/")
        if len(parts) >= 4 and parts[0] == "factory":
            payload.setdefault("node_id", parts[1])
            payload.setdefault("factory_id", int(parts[2]))
        return payload

    def _on_publish(self, client, userdata, mid):
        db_id = self._pending_acks.pop(mid, None)
        if db_id is not None:
            self._buffer.delete([db_id])

    def _flush_buffer(self):
        records = self._buffer.get_all()
        if not records:
            return
        print(f"버퍼 플러시: {len(records)}건 전송 시작")
        for rec in records:
            topic = f"factory/{rec['node_id']}/{rec['factory_id']}/telemetry"
            payload = {k: v for k, v in rec.items() if k != "_id"}
            result = self.client.publish(topic, json.dumps(payload), qos=1)
            self._pending_acks[result.mid] = rec["_id"]
            print(f"  └ factory={rec['factory_id']} temp={rec['temperature_c']}°C humidity={rec['humidity_pct']}% @ {rec['timestamp']}")
        print(f"버퍼 플러시 완료: {len(records)}건 전송 요청, ACK 대기 중")

    def publish_telemetry(self, factory_id: int, temperature_c: float, humidity_pct: float, measured_at: str):
        payload = {
            "factory_id": factory_id,
            "node_id": self.node_id,
            "temperature_c": round(temperature_c, 2),
            "humidity_pct": round(humidity_pct, 2),
            "timestamp": measured_at,
        }
        if not self._connected:
            self._buffer.save(payload)
            print(f"오프라인 버퍼 저장: factory={factory_id}, temp={temperature_c}°C humidity={humidity_pct}% (버퍼={self._buffer.count()}건)")
            return
        topic = f"factory/{self.node_id}/{factory_id}/telemetry"
        self.client.publish(topic, json.dumps(payload), qos=1)
        print(f"발행: {topic} → temp={temperature_c}°C, humidity={humidity_pct}%")

    def publish_peltier_status(self, factory_id: int, status: dict):
        payload = {
            "node_id": self.node_id,
            "factory_id": factory_id,
            **status,
        }
        topic = f"factory/{self.node_id}/{factory_id}/peltier/status"
        self.client.publish(topic, json.dumps(payload), qos=1)
        print(f"상태 발행: {topic} → {payload.get('state')}")
