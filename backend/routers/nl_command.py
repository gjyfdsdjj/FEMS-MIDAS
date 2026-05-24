import logging
import traceback
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from services.nl_command_service import parse_command, transcribe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/nl-command", tags=["nl-command"])


class TextParseRequest(BaseModel):
    text: str


@router.post("/parse-text")
async def parse_text(req: TextParseRequest):
    try:
        command = parse_command(req.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"transcript": req.text, "command": command}


@router.post("/parse-audio")
async def parse_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    try:
        transcript = transcribe(audio_bytes, suffix)
        command = parse_command(transcript)
    except Exception as e:
        logger.error("parse-audio 실패: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    return {"transcript": transcript, "command": command}
