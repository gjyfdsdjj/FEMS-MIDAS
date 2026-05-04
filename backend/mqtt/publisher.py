import json
import os
import uuid
import paho.mqtt.client as mqtt
from datetime import datetime, timezone


class MQTTPublisher:
    def __init__(self):
        self.client = mqtt.Client()

    def connect(self):
        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", 1883))
        self.client.connect(host, port)
        self.client.loop_start()

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
        self.client.publish(topic, json.dumps(message), qos=1)
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
