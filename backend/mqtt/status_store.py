from __future__ import annotations

from threading import Lock
from typing import Any, Optional


class MQTTStatusStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._peltier_status: dict[tuple[str, int], dict[str, Any]] = {}

    def update_peltier_status(self, node_id: str, factory_id: int, status: dict[str, Any]) -> None:
        key = (node_id, factory_id)
        merged = {
            "node_id": node_id,
            "factory_id": factory_id,
            **status,
        }
        with self._lock:
            self._peltier_status[key] = merged

    def get_peltier_status(self, node_id: str, factory_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            status = self._peltier_status.get((node_id, factory_id))
            return dict(status) if status is not None else None

    def get_peltier_status_by_factory(self, factory_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            for (_node_id, stored_factory_id), status in reversed(self._peltier_status.items()):
                if stored_factory_id == factory_id:
                    return dict(status)
        return None

    def get_factory_status(self, node_id: str, factory_id: int) -> dict[str, Any]:
        peltier = self.get_peltier_status(node_id, factory_id)
        components = {}
        if peltier is not None and peltier.get("available", False):
            components["peltier"] = peltier

        return {
            "node_id": node_id,
            "factory_id": factory_id,
            "components": components,
            "raw": {
                "peltier": peltier,
            },
        }


status_store = MQTTStatusStore()
