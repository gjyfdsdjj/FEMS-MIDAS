from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=False)

DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
DEFAULT_NODE_ID = os.getenv("NODE_ID", "node_A")
DEFAULT_FACTORY_IDS = [
    int(value.strip())
    for value in os.getenv("FACTORY_IDS", "1").split(",")
    if value.strip()
]

COMMANDS = ("START", "SET_PWM", "STOP", "FAN_ON", "FAN_OFF")
DIRECTIONS = ("forward", "reverse")


def init_state() -> None:
    st.session_state.setdefault("api_base_url", DEFAULT_API_BASE_URL)
    st.session_state.setdefault("node_id", DEFAULT_NODE_ID)
    st.session_state.setdefault("factory_id", DEFAULT_FACTORY_IDS[0] if DEFAULT_FACTORY_IDS else 1)
    st.session_state.setdefault("last_command", None)
    st.session_state.setdefault("command_log", [])


def post_json(path: str, body: dict[str, Any]) -> dict[str, Any]:
    api_base_url = st.session_state["api_base_url"].rstrip("/")
    with httpx.Client(timeout=5.0) as client:
        response = client.post(f"{api_base_url}{path}", json=body)
    response.raise_for_status()
    return response.json()


def get_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    api_base_url = st.session_state["api_base_url"].rstrip("/")
    with httpx.Client(timeout=3.0) as client:
        response = client.get(f"{api_base_url}{path}", params=params)
    response.raise_for_status()
    return response.json()


def build_manual_body(
    *,
    action: str,
    node_id: str,
    factory_id: int,
    duty: float,
    direction: str,
    seconds: float,
    max_duty: float,
    allow_high_duty: bool,
    keep_fan_running: bool,
    fan_active_low: bool,
    fan_spinup: float,
    fan_cooldown: float,
    reason: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "node_id": node_id,
        "factory_id": factory_id,
        "action": action,
        "reason": reason,
        "allow_high_duty": allow_high_duty,
        "max_duty": max_duty,
    }

    if action in {"SET_PWM", "START"}:
        body["value"] = duty
        body["direction"] = direction
        body["seconds"] = seconds
        body["keep_fan_running"] = keep_fan_running
        body["fan_spinup_seconds"] = fan_spinup
        body["fan_cooldown_seconds"] = fan_cooldown

    if action == "STOP":
        body["keep_fan_running"] = keep_fan_running
        body["fan_cooldown_seconds"] = fan_cooldown

    if action in {"START", "SET_PWM", "STOP", "FAN_ON", "FAN_OFF"}:
        body["fan_active_low"] = fan_active_low

    return body


def append_log(ok: bool, action: str, body: dict[str, Any], result: Any) -> None:
    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "ok": ok,
        "action": action,
        "body": body,
        "result": result,
    }
    st.session_state["last_command"] = entry
    st.session_state["command_log"] = [entry, *st.session_state["command_log"][:9]]


def load_control_status(node_id: str, factory_id: int) -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = get_json(
            "/api/v1/control/status",
            {"node_id": node_id, "factory_id": factory_id},
        )
    except Exception as exc:
        return None, str(exc)
    return result.get("data", {}), None


def load_optional(path: str, params: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return get_json(path, params), None
    except Exception as exc:
        return None, str(exc)


st.set_page_config(
    page_title="MIDAS Peltier Control",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_state()

st.markdown(
    """
<style>
  .block-container {
    max-width: 960px;
    padding-top: 1.5rem;
  }
  div[data-testid="stMetric"] {
    background: #f8fafc;
    border: 1px solid #d7e0ea;
    border-radius: 8px;
    padding: 0.75rem 1rem;
  }
  div[data-testid="stForm"] {
    border: 1px solid #d7e0ea;
    border-radius: 8px;
    padding: 1rem;
  }
</style>
""",
    unsafe_allow_html=True,
)

st.title("MIDAS Peltier Manual Control")

top_left, top_right = st.columns([2, 1])
with top_left:
    st.text_input("API Base URL", key="api_base_url")
with top_right:
    if st.button("Health Check", use_container_width=True):
        try:
            with httpx.Client(timeout=3.0) as client:
                health = client.get(f"{st.session_state['api_base_url'].rstrip('/')}/health")
            health.raise_for_status()
            st.success("OK")
            st.json(health.json())
        except Exception as exc:
            st.error(str(exc))

with st.form("manual_peltier_control", clear_on_submit=False):
    node_col, factory_col, action_col = st.columns(3)
    with node_col:
        node_id = st.text_input("Node ID", key="node_id")
    with factory_col:
        factory_id = st.number_input("Factory ID", min_value=1, max_value=99, step=1, key="factory_id")
    with action_col:
        action = st.selectbox("Action", COMMANDS, index=0)

    duty_col, direction_col, seconds_col = st.columns(3)
    with duty_col:
        allow_high_duty = st.checkbox("Allow high duty", value=False)
        max_duty = st.number_input("Max duty cap (%)", min_value=0.0, max_value=100.0, value=50.0, step=5.0)
        slider_max = 100 if allow_high_duty else int(max_duty)
        duty = st.slider("Duty (%)", min_value=0, max_value=max(0, slider_max), value=min(20, max(0, slider_max)))
    with direction_col:
        direction = st.radio("Direction", DIRECTIONS, horizontal=True)
    with seconds_col:
        seconds = st.number_input("Run seconds", min_value=0.0, max_value=86400.0, value=60.0, step=5.0)

    fan_col, timing_col, reason_col = st.columns(3)
    with fan_col:
        fan_active_low = st.checkbox("Fan active low", value=False)
        keep_fan_running = st.checkbox("Keep fan on after STOP", value=True)
    with timing_col:
        fan_spinup = st.number_input("Fan spin-up seconds", min_value=0.0, max_value=60.0, value=2.0, step=0.5)
        fan_cooldown = st.number_input("Fan cooldown seconds", min_value=0.0, max_value=300.0, value=30.0, step=5.0)
    with reason_col:
        reason = st.text_area("Reason", value="streamlit manual control", height=110)

    body = build_manual_body(
        action=action,
        node_id=node_id.strip(),
        factory_id=int(factory_id),
        duty=float(duty),
        direction=direction,
        seconds=float(seconds),
        max_duty=float(max_duty),
        allow_high_duty=allow_high_duty,
        keep_fan_running=keep_fan_running,
        fan_active_low=fan_active_low,
        fan_spinup=float(fan_spinup),
        fan_cooldown=float(fan_cooldown),
        reason=reason.strip(),
    )

    submitted = st.form_submit_button("Send Command", use_container_width=True)

if submitted:
    try:
        result = post_json("/api/v1/control/manual", body)
    except Exception as exc:
        append_log(False, action, body, str(exc))
        st.error(str(exc))
    else:
        append_log(True, action, body, result)
        st.success(result.get("message", "sent"))

status_data, status_error = load_control_status(
    st.session_state["node_id"].strip(),
    int(st.session_state["factory_id"]),
)
components = (status_data or {}).get("components", {})
peltier_status = components.get("peltier")
factory_id_value = int(st.session_state["factory_id"])
readonly_token = f"factory_{factory_id_value}"
readonly_url = f"/qr_dash?token={readonly_token}"

status_title_col, status_refresh_col = st.columns([3, 1])
with status_title_col:
    st.subheader("Control Status")
with status_refresh_col:
    st.button("Refresh Status", use_container_width=True)

status_cols = st.columns(4)
if peltier_status:
    status_cols[0].metric("Peltier", str(peltier_status.get("state", "-")).upper())
    status_cols[1].metric("Duty", f"{float(peltier_status.get('duty') or 0):.1f}%")
    status_cols[2].metric("Direction", peltier_status.get("direction") or "-")
    fan_value = peltier_status.get("fan_on")
    status_cols[3].metric("Fan", "-" if fan_value is None else "ON" if fan_value else "OFF")

    detail_cols = st.columns(3)
    detail_cols[0].caption(f"Last action: {peltier_status.get('last_action') or '-'}")
    detail_cols[1].caption(f"Command ID: {peltier_status.get('last_command_id') or '-'}")
    detail_cols[2].caption(f"Updated: {peltier_status.get('updated_at') or '-'}")

    if peltier_status.get("last_error"):
        st.warning(peltier_status["last_error"])
elif status_error:
    st.caption(f"Status unavailable: {status_error}")
else:
    st.caption("Waiting for connected hardware status.")

st.markdown(
    f"""
<a href="{readonly_url}" target="_self" style="
  display:block;
  margin: 0.75rem 0 1.25rem;
  padding: 0.85rem 1rem;
  border: 1px solid #d7e0ea;
  border-radius: 8px;
  background: #f8fafc;
  color: #0f172a;
  text-decoration: none;
">
  <strong>Factory {factory_id_value} Readonly Dashboard</strong>
  <span style="float:right;color:#2563eb;">Open</span>
</a>
""",
    unsafe_allow_html=True,
)

sensor_live, sensor_error = load_optional(
    "/api/v1/sensors/live",
    {"factory_id": factory_id_value},
)
sensor_rows = (sensor_live or {}).get("data", [])
sensor_now = sensor_rows[0] if sensor_rows else None

if sensor_now:
    st.subheader("Sensor Live")
    sensor_cols = st.columns(4)
    temp_value = sensor_now.get("temperature_c")
    humidity_value = sensor_now.get("humidity_pct")
    sensor_cols[0].metric("Temperature", "-" if temp_value is None else f"{temp_value:.2f} C")
    sensor_cols[1].metric("Humidity", "-" if humidity_value is None else f"{humidity_value:.2f}%")
    sensor_cols[2].metric("Comms", sensor_now.get("communication") or "-")
    sensor_cols[3].metric("Age", "-" if sensor_now.get("age_seconds") is None else f"{sensor_now['age_seconds']}s")
else:
    st.caption("No live sensor data yet.")

analytics_efficiency, _ = load_optional(
    f"/api/v1/analytics/cooling-efficiency/{factory_id_value}",
    {"hours": 24},
)
analytics_prediction, _ = load_optional(
    f"/api/v1/analytics/temperature-predict/{factory_id_value}",
    {"horizon_minutes": 60},
)
analytics_anomalies, _ = load_optional(
    f"/api/v1/analytics/anomalies/{factory_id_value}",
    {"minutes": 10},
)
energy_summary, _ = load_optional(
    "/api/v1/energy/summary",
    {"factory_id": factory_id_value, "hours": 24},
)
op_reliability, _ = load_optional(
    f"/api/v1/operations/sensor-reliability/{factory_id_value}",
    {"hours": 24},
)
op_stability, _ = load_optional(
    f"/api/v1/operations/temperature-stability/{factory_id_value}",
    {"hours": 24},
)
op_maintenance, _ = load_optional(
    f"/api/v1/operations/maintenance/{factory_id_value}",
    {},
)

with st.expander("Analytics", expanded=False):
    cols = st.columns(3)
    minutes_per_degree = (analytics_efficiency or {}).get("minutes_per_degree")
    predicted_temp = (analytics_prediction or {}).get("predicted_temp")
    anomalies = (analytics_anomalies or {}).get("anomalies")
    cols[0].metric("Cooling Efficiency", "-" if minutes_per_degree is None else f"{minutes_per_degree} min/C")
    cols[1].metric("Predicted Temp", "-" if predicted_temp is None else f"{predicted_temp} C")
    cols[2].metric("Anomalies", "-" if anomalies is None else len(anomalies))
    st.json(
        {
            "cooling_efficiency": analytics_efficiency,
            "temperature_prediction": analytics_prediction,
            "anomalies": analytics_anomalies,
        }
    )

with st.expander("Energy / Operations", expanded=False):
    energy = energy_summary or {}
    consumption = energy.get("consumption", {})
    savings = energy.get("savings", {})
    cols = st.columns(4)
    cols[0].metric("24h kWh", consumption.get("total_kwh", "-"))
    cols[1].metric("24h Cost", consumption.get("total_cost_krw", "-"))
    cols[2].metric("Saved Cost", savings.get("saved_cost_krw", "-"))
    cols[3].metric("Maintenance", (op_maintenance or {}).get("recommendation", "-"))

    ops_cols = st.columns(2)
    ops_cols[0].json({"sensor_reliability": op_reliability, "temperature_stability": op_stability})
    ops_cols[1].json({"energy_summary": energy_summary, "maintenance": op_maintenance})

state_cols = st.columns(3)
last = st.session_state["last_command"]
state_cols[0].metric("Last Action", last["action"] if last else "-")
state_cols[1].metric("Last Result", "OK" if last and last["ok"] else "-" if not last else "ERROR")
state_cols[2].metric("Log Count", len(st.session_state["command_log"]))

with st.expander("Payload Preview", expanded=True):
    st.json(body)

with st.expander("Command Log", expanded=False):
    for entry in st.session_state["command_log"]:
        st.write(f"{entry['time']} / {entry['action']} / {'OK' if entry['ok'] else 'ERROR'}")
        st.json({"body": entry["body"], "result": entry["result"]})
