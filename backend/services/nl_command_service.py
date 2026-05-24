import os
import tempfile

from openai import OpenAI

_whisper_model = None
_openai_client = None

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_control_command",
            "description": "사용자의 자연어를 펠티어/팬 제어 명령 JSON으로 변환합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "제어 명령. START, STOP, SET_PWM, SET_TARGET_TEMP, FAN_ON, FAN_OFF 중 하나",
                    },
                    "value": {
                        "type": "number",
                        "description": "START/SET_PWM이면 duty(0~100%), SET_TARGET_TEMP이면 목표온도(°C)",
                    },
                    "direction": {
                        "type": "string",
                        "description": "forward(냉각) 또는 reverse(가열)",
                    },
                    "seconds": {"type": "number", "description": "동작 시간(초)"},
                    "fan_cooldown_sec": {"type": "number", "description": "정지 후 팬 냉각 유지 시간(초)"},
                    "keep_fan_running": {"type": "boolean"},
                    "requires_confirmation": {"type": "boolean"},
                    "summary": {"type": "string", "description": "한국어 명령 요약 (UI 표시용)"},
                },
                "required": ["action", "requires_confirmation", "summary"],
            },
        },
    }
]

_SYSTEM = (
    "당신은 냉장 공장 펠티어 제어 시스템의 명령 해석기입니다. "
    "사용자의 자연어를 제어 명령으로 변환하세요. "
    "requires_confirmation은 항상 true로 설정하세요. "
    "명시되지 않은 파라미터는 생략하세요."
)


def _whisper():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model("small")
    return _whisper_model


def _client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=os.environ["MINDLOGIC_API_KEY"],
            base_url=os.environ["MINDLOGIC_BASE_URL"],
        )
    return _openai_client


def transcribe(audio_bytes: bytes, suffix: str = ".wav") -> str:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        result = _whisper().transcribe(tmp_path, language="ko")
        return result["text"].strip()
    finally:
        os.unlink(tmp_path)


def parse_command(text: str) -> dict:
    response = _client().chat.completions.create(
        model="gpt-5.4-mini",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
        tools=_TOOLS,
        tool_choice={"type": "function", "function": {"name": "create_control_command"}},
    )
    msg = response.choices[0].message
    if msg.tool_calls:
        import json
        return json.loads(msg.tool_calls[0].function.arguments)
    raise ValueError("모델이 명령을 생성하지 못했습니다.")
