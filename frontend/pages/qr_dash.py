import streamlit as st
from datetime import datetime
from pathlib import Path
import sys
import os
import requests
import json5
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
sys.path.append(str(BASE_DIR))
load_dotenv(ROOT_DIR / ".env", override=False)
MOCK_MODE = True
MOCK_DATA_PATH = ROOT_DIR / "backend" / "database" / "dummy_data.jsonc"


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
    if MOCK_MODE:
        with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
            mock = json5.load(f)

        factory = mock["factories"][0]

        return {
            "factory_id": factory["factory_id"],
            "node_id": factory.get("node_id"),
            "factory_name": factory["name"],
            "status": factory["status"],
            "temp_now": factory["temperature_c"],
            "humidity": factory["humidity_pct"],
            "updated": _format_time(factory.get("last_seen_at")),
            "peltier": {
                "state": factory["status"],
                "running": factory["pwm_pct"] > 0,
                "duty": factory["pwm_pct"],
                "direction": "COOL",
                "fan_on": factory["pwm_pct"] > 0,
                "bridge_enabled": factory["pwm_pct"] > 0,
                "last_action": "MOCK",
                "last_command_id": "mock_001",
                "updated_at": factory.get("last_seen_at"),
                "last_error": None,
            },
            "history": [
                {
                    "timestamp": row["timestamp"],
                    "temperature_c": row["temperature_c"],
                }
                for row in mock["sensor_logs"]
                if row["factory_id"] == factory["factory_id"]
            ],
        }

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
        "history": api_data.get("history", []),
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

# 온도/습도 카드
t = data.get("temp_now")
h = data.get("humidity")
tc = "temp-cold" if t is not None and t < -20 else "temp-ok" if t is not None and t < -16 else "temp-warn"
t_str = f"{t:.1f}" if t is not None else "-"
h_str = f"{h:.1f}" if h is not None else "-"

st.markdown(f"""
<div class="card">
  <div class="card-label">🌡 실시간 내부 온도</div>
  <div>
    <span class="card-value {tc}">{t_str}</span>
    <span class="card-unit">°C</span>
    &nbsp;&nbsp;
    <span style="font-family:var(--font-mono);font-size:1rem;color:var(--muted);">습도 {h_str}%</span>
  </div>
</div>
""", unsafe_allow_html=True)

# 24시간 온도 추이 차트
history = data.get("history", [])
times, temps = [], []
for row in history:
    try:
        times.append(datetime.fromisoformat(row["timestamp"]))
        temps.append(row["temperature_c"])
    except Exception:
        pass

if times and temps:
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_hline(y=-18, line_dash="dot", line_color="#c8d9ec",
                  annotation_text="-18°C 목표", annotation_position="bottom right",
                  annotation_font=dict(size=9, color="#6b8299"))
    fig.add_trace(go.Scatter(
        x=times, y=temps, mode="lines",
        line=dict(color="#0077cc", width=2.5, shape="spline"),
        fill="tozeroy", fillcolor="rgba(0,119,204,0.08)",
        hovertemplate="%{x|%H:%M}<br><b>%{y}°C</b><extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(l=10, r=10, t=10, b=10), height=220,
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=9, color="#6b8299")),
        yaxis=dict(showgrid=True, gridcolor="rgba(200,217,236,0.7)", zeroline=False,
                   tickfont=dict(size=9, color="#6b8299"), range=[-25, -5]),
    )
    chart_html = fig.to_html(include_plotlyjs="cdn", full_html=False, config={"displayModeBar": False})
    import streamlit.components.v1 as components
    components.html(f"""
<html><body style="margin:0;padding:0;background:white;">
<div style="background:white;border:1px solid #c8d9ec;border-radius:16px;padding:1.1rem 1.2rem;">
  <div style="font-family:monospace;font-size:0.8rem;color:#1a2b3c;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.5rem;">24시간 온도 추이</div>
  {chart_html}
</div>
</body></html>
""", height=290)

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
