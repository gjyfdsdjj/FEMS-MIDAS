import streamlit as st
from datetime import datetime
from pathlib import Path
import sys
import os
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
sys.path.append(str(BASE_DIR))
load_dotenv(ROOT_DIR / ".env", override=False)


st.set_page_config(
    page_title="Peltier Readonly Status",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def load_css(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


CSS_PATH = BASE_DIR / "styles" / "qr.css"
load_css(CSS_PATH)


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


def _format_bool(value):
    if value is None:
        return "-"
    return "ON" if value else "OFF"


def _format_duty(value):
    if value is None:
        return "-"
    return f"{float(value):.1f}%"


def _format_time(value):
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%H:%M:%S")
    except ValueError:
        return str(value)


@st.cache_data(ttl=5)
def get_factory_data(token: str):
    url = f"{API_BASE_URL}/api/v1/readonly/{token}"

    response = requests.get(url, timeout=5)
    response.raise_for_status()

    result = response.json()

    if not result["success"]:
        raise Exception(result["error"]["message"])

    api_data = result["data"]
    peltier = api_data.get("peltier") or {}
    updated_raw = peltier.get("updated_at") or api_data.get("last_updated_at")

    return {
        "factory_id": api_data["factory_id"],
        "node_id": api_data.get("node_id"),
        "factory_name": api_data["factory_name"],
        "status": api_data["status"],
        "temp_now": api_data["temperature_c"],
        "humidity": api_data["humidity_pct"],
        "updated": _format_time(updated_raw) if updated_raw else "대기 중",
        "peltier": api_data.get("peltier"),
    }


token = st.query_params.get("token", "rdonly_test_1")

try:
    data = get_factory_data(token)
except Exception as e:
    st.error("데이터를 불러오지 못했습니다.")
    st.caption(str(e))
    st.stop()

factory_name = data["factory_name"]

status_map = {
    "NORMAL": "정상",
    "WARNING": "주의",
    "ERROR": "이상",
    "WAITING": "대기",
}

status_badge_map = {
    "NORMAL": "badge-on",
    "WARNING": "badge-warn",
    "ERROR": "badge-warn",
    "WAITING": "badge-off",
}

status_text = status_map.get(data["status"], data["status"])
status_badge = status_badge_map.get(data["status"], "badge-off")

st.markdown("""<meta http-equiv="refresh" content="30">""", unsafe_allow_html=True)

st.markdown(
    f"""
<div class="dashboard-title">
  {factory_name}
  <span class="badge {status_badge}" style="vertical-align:middle; margin-left:0.4rem;">
    {status_text}
  </span>
</div>
<div class="dashboard-sub">
  <span class="live-dot"></span>LIVE · {data['updated']}
</div>
""",
    unsafe_allow_html=True,
)

peltier = data.get("peltier")

if not peltier:
    st.markdown(
        f"""
<div class="card">
  <div class="card-label">Peltier Status</div>
  <div>
    <span class="card-value temp-ok" style="font-size:2.1rem;">WAITING</span>
  </div>
  <div style="font-family:var(--font-mono);font-size:0.72rem;color:var(--muted);margin-top:0.7rem;">
    NODE {data.get('node_id') or '-'} · FACTORY {data['factory_id']}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
else:
    state = str(peltier.get("state") or "-").upper()
    state_badge = "badge-warn" if state == "ERROR" else "badge-on" if peltier.get("running") else "badge-off"
    last_error = peltier.get("last_error")

    st.markdown(
        f"""
<div class="card">
  <div class="card-label">Peltier Status</div>
  <div style="display:flex;align-items:center;justify-content:space-between;gap:0.75rem;">
    <span class="card-value temp-ok" style="font-size:2.1rem;">{state}</span>
    <span class="badge {state_badge}">{'RUNNING' if peltier.get('running') else 'IDLE'}</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.65rem;margin-top:1rem;">
    <div>
      <div class="card-label" style="font-size:0.65rem;margin-bottom:0.25rem;">DUTY</div>
      <div style="font-family:var(--font-head);font-size:1.45rem;font-weight:800;">{_format_duty(peltier.get('duty'))}</div>
    </div>
    <div>
      <div class="card-label" style="font-size:0.65rem;margin-bottom:0.25rem;">DIRECTION</div>
      <div style="font-family:var(--font-head);font-size:1.45rem;font-weight:800;">{peltier.get('direction') or '-'}</div>
    </div>
    <div>
      <div class="card-label" style="font-size:0.65rem;margin-bottom:0.25rem;">FAN</div>
      <div style="font-family:var(--font-head);font-size:1.45rem;font-weight:800;">{_format_bool(peltier.get('fan_on'))}</div>
    </div>
    <div>
      <div class="card-label" style="font-size:0.65rem;margin-bottom:0.25rem;">BRIDGE</div>
      <div style="font-family:var(--font-head);font-size:1.45rem;font-weight:800;">{_format_bool(peltier.get('bridge_enabled'))}</div>
    </div>
  </div>
  <div style="font-family:var(--font-mono);font-size:0.72rem;color:var(--muted);margin-top:1rem;line-height:1.7;">
    ACTION {peltier.get('last_action') or '-'}<br>
    COMMAND {peltier.get('last_command_id') or '-'}<br>
    UPDATED {_format_time(peltier.get('updated_at'))}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if last_error:
        st.warning(last_error)


st.markdown(
    f"""
<div style="text-align:center;padding:1.5rem 0 0.5rem;font-family:'DM Mono',monospace;font-size:0.62rem;color:#a0b8cc;letter-spacing:0.1em;">
  {datetime.now().strftime('%Y')} · AUTO REFRESH 30s
</div>
""",
    unsafe_allow_html=True,
)
