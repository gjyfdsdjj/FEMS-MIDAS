import json
import os
import time
import uuid
import paho.mqtt.client as mqtt
from datetime import datetime, timezone


class MQTTPublisher:
    def __init__(self):
        self._connected = False
        self.client = mqtt.Client(client_id=f"midas-backend-{uuid.uuid4().hex[:8]}", clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            print("✅ MQTT publisher 브로커 연결 완료")
        else:
            self._connected = False
            print(f"⚠️ MQTT publisher 연결 실패: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False

    def connect(self):
        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", 1883))
        print(f"[Publisher] 연결 시도: {host}:{port}")
        self.client.connect(host, port)
        self.client.loop_start()
        # CONNACK 수신까지 최대 5초 대기
        for _ in range(50):
            if self._connected:
                break
            time.sleep(0.1)
        if not self._connected:
            print(f"⚠️ MQTT publisher 연결 대기 시간 초과 ({host}:{port})")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish_command(self, node_id: str, factory_id: int, action: str, payload: dict = {}):
        message = {
            "command_id": str(uuid.uuid4()),
            "action": action,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        topic = f"factory/{node_id}/{factory_id}/command"
        self.client.publish(topic, json.dumps(message), qos=0)
        print(f"명령 발행: {topic} → {action} {payload}")

    def publish_all_stop(self, node_ids: list, reason: str = ""):
        for node_id in node_ids:
            for factory_id in range(1, 5):
                self.publish_command(node_id, factory_id, "STOP", {"reason": reason})

    def publish_all_start(self, node_ids: list, reason: str = ""):
        for node_id in node_ids:
            for factory_id in range(1, 5):
                self.publish_command(node_id, factory_id, "START", {"reason": reason})


publisher = MQTTPublisher()
