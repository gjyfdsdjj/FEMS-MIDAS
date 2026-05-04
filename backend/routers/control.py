from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from mqtt.publisher import publisher

router = APIRouter(prefix="/api/v1/control", tags=["control"])


class ManualControlRequest(BaseModel):
    node_id: str
    factory_id: int
    action: str  # START | STOP | SET_PWM | SET_TARGET_TEMP | SWITCH_AUTO | SWITCH_MANUAL
    value: Optional[float] = None
    reason: Optional[str] = ""


class AllStopRequest(BaseModel):
    node_ids: list[str]
    reason: Optional[str] = ""


@router.post("/manual")
async def manual_control(req: ManualControlRequest):
    payload = {}
    if req.value is not None:
        payload["value"] = req.value
    if req.reason:
        payload["reason"] = req.reason

    publisher.publish_command(req.node_id, req.factory_id, req.action, payload)
    return {"success": True, "message": f"{req.action} 명령 발행 완료"}


@router.post("/all-stop")
async def all_stop(req: AllStopRequest):
    publisher.publish_all_stop(req.node_ids, req.reason)
    return {"success": True, "message": "전체 긴급 정지 명령 발행 완료"}


@router.post("/all-start")
async def all_start(req: AllStopRequest):
    publisher.publish_all_start(req.node_ids, req.reason)
    return {"success": True, "message": "전체 재가동 명령 발행 완료"}
