from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from mqtt.publisher import publisher
from mqtt.status_store import status_store


router = APIRouter(prefix="/api/v1/control", tags=["control"])

ALLOWED_ACTIONS = {"START", "STOP", "SET_PWM", "FAN_ON", "FAN_OFF"}
DRIVE_ACTIONS = {"START", "SET_PWM"}


class ManualControlRequest(BaseModel):
    node_id: str
    factory_id: int
    action: str
    value: Optional[float] = None
    direction: Optional[str] = None
    seconds: Optional[float] = None
    max_duty: Optional[float] = 50.0
    allow_high_duty: bool = False
    keep_fan_running: bool = True
    fan_active_low: bool = False
    fan_spinup_seconds: Optional[float] = None
    fan_cooldown_seconds: Optional[float] = None
    reason: Optional[str] = ""


class AllStopRequest(BaseModel):
    node_ids: list[str]
    reason: Optional[str] = ""


@router.post("/manual")
async def manual_control(req: ManualControlRequest):
    action = req.action.upper()
    if action not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {req.action}")

    node_id = req.node_id.strip()
    if not node_id:
        raise HTTPException(status_code=400, detail="node_id is required")

    if req.factory_id < 1:
        raise HTTPException(status_code=400, detail="factory_id must be greater than 0")

    if req.direction is not None and req.direction not in ("forward", "reverse"):
        raise HTTPException(status_code=400, detail="direction must be forward or reverse")

    if req.value is not None and not 0 <= req.value <= 100:
        raise HTTPException(status_code=400, detail="value must be between 0 and 100")

    if action in DRIVE_ACTIONS and req.value is None:
        raise HTTPException(status_code=400, detail=f"{action} requires value")

    if (
        req.value is not None
        and req.max_duty is not None
        and req.value > req.max_duty
        and not req.allow_high_duty
    ):
        raise HTTPException(status_code=400, detail="value exceeds max_duty")

    if req.seconds is not None and req.seconds < 0:
        raise HTTPException(status_code=400, detail="seconds must be greater than or equal to 0")

    if req.max_duty is not None and not 0 <= req.max_duty <= 100:
        raise HTTPException(status_code=400, detail="max_duty must be between 0 and 100")

    if req.fan_spinup_seconds is not None and req.fan_spinup_seconds < 0:
        raise HTTPException(status_code=400, detail="fan_spinup_seconds must be greater than or equal to 0")

    if req.fan_cooldown_seconds is not None and req.fan_cooldown_seconds < 0:
        raise HTTPException(status_code=400, detail="fan_cooldown_seconds must be greater than or equal to 0")

    payload = {}
    if req.value is not None:
        payload["value"] = req.value
    if action in DRIVE_ACTIONS:
        payload["direction"] = req.direction or "forward"
    if req.seconds is not None:
        payload["seconds"] = req.seconds
    if req.max_duty is not None:
        payload["max_duty"] = req.max_duty
    if req.fan_spinup_seconds is not None:
        payload["fan_spinup_seconds"] = req.fan_spinup_seconds
    if req.fan_cooldown_seconds is not None:
        payload["fan_cooldown_seconds"] = req.fan_cooldown_seconds

    payload["allow_high_duty"] = req.allow_high_duty
    payload["keep_fan_running"] = req.keep_fan_running
    payload["fan_active_low"] = req.fan_active_low

    if req.reason:
        payload["reason"] = req.reason

    command = publisher.publish_command(node_id, req.factory_id, action, payload)
    return {
        "success": True,
        "message": f"{action} command published",
        "command_id": command["command_id"],
        "topic": command["topic"],
        "payload": payload,
    }


@router.get("/status")
async def get_control_status(
    node_id: str = Query(...),
    factory_id: int = Query(..., ge=1),
):
    return {
        "success": True,
        "data": status_store.get_factory_status(node_id.strip(), factory_id),
    }


@router.post("/all-stop")
async def all_stop(req: AllStopRequest):
    publisher.publish_all_stop(req.node_ids, req.reason)
    return {"success": True, "message": "All stop commands published"}


@router.post("/all-start")
async def all_start(req: AllStopRequest):
    publisher.publish_all_start(req.node_ids, req.reason)
    return {"success": True, "message": "All start commands published"}
