import streamlit as st
import random
import json5
import plotly.graph_objects as go
import time
import sys
import base64
import requests
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def issue_qr_token(factory_id):
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/readonly/tokens",
            json={
                "factory_id": factory_id,
                "expires_in_minutes": 60
            },
            timeout=8
        )

        if response.status_code != 200:
            return {
                "success": False,
                "message": f"status_code: {response.status_code}",
                "detail": response.text,
            }

        return response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": "request exception",
            "detail": str(e),
        }
    
sys.path.append(str(Path(__file__).resolve().parents[1]))

from components.main.factory_detail import factory_detail
from components.main.notification import notification_popover
from components.main.factory_status import factory_status
from components.main.energy_cost import energy_cost
from components.main.op_manage import operation_manage
from components.main.manual_control import manual_control
from components.main.data_helpers import (
    convert_status,
    control_log_text,
    get_factory_alarms,
    get_all_unacked_alerts,
    get_maintenance_info,
    get_temp_predictions,
    get_sensor_logs,
    get_door_events,
    make_equip,
)


st.set_page_config(
    page_title="MIDAS FEMS 대시보드",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def load_css(file_name):
    css_path = Path(__file__).parent.parent / "styles" / file_name
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("main.css")

DATA_PATH = Path(__file__).resolve().parents[2] / "backend" / "database" / "dummy_data.jsonc"

@st.cache_data
def load_dummy_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json5.load(f)

dummy_data = load_dummy_data()


def api_get(path: str, params: dict = None) -> Optional[dict]:
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


@st.cache_data(ttl=30)
def fetch_factories() -> list[dict]:
    result = api_get("/api/v1/factories")
    if result and result.get("success"):
        return result["data"]
    return []


@st.cache_data(ttl=30)
def fetch_alerts() -> list[dict]:
    result = api_get("/api/v1/alerts", {"limit": 100})
    if result and result.get("success"):
        return result["data"]
    return []


@st.cache_data(ttl=30)
def fetch_schedules() -> list[dict]:
    result = api_get("/api/v1/schedules")
    if result and result.get("success"):
        return result["data"]
    return []


@st.cache_data(ttl=5)
def fetch_live_sensors() -> list[dict]:
    result = api_get("/api/v1/sensors/live")
    if result and result.get("success"):
        return result["data"]
    return []


@st.cache_data(ttl=30)
def fetch_sensor_history_full(factory_id: int) -> list[dict]:
    """detail view용 — factory_id별 sensor_logs 형식 반환"""
    result = api_get("/api/v1/sensors/history", {"factory_id": factory_id, "metric": "temperature", "interval": "1m"})
    if not result or not result.get("data"):
        return []
    rows = []
    for p in result["data"]:
        rows.append({
            "factory_id": factory_id,
            "temperature_c": p["value"],
            "humidity_pct": None,
            "timestamp": p["timestamp"],
            "communication_status": "OK",
        })
    return rows


@st.cache_data(ttl=30)
def fetch_sensor_history(factory_id: int) -> list[float]:
    result = api_get("/api/v1/sensors/history", {"factory_id": factory_id, "metric": "temperature", "interval": "1m"})
    if result and result.get("data"):
        return [p["value"] for p in result["data"][-20:]]
    return []


@st.cache_data(ttl=120)
def fetch_temp_predict(factory_id: int) -> Optional[dict]:
    result = api_get(f"/api/v1/analytics/temperature-predict/{factory_id}")
    return result if result and result.get("predicted_temp") is not None else None


@st.cache_data(ttl=120)
def fetch_maintenance(factory_id: int) -> Optional[dict]:
    result = api_get(f"/api/v1/operations/maintenance/{factory_id}")
    return result if result else None


@st.cache_data(ttl=30)
def fetch_jobs() -> list[dict]:
    result = api_get("/api/v1/jobs")
    if result and result.get("success"):
        return result["data"]
    return []


@st.cache_data(ttl=10800)
def fetch_weather() -> Optional[dict]:
    result = api_get("/api/v1/weather/tomorrow")
    if not result or not result.get("forecasts"):
        return None
    forecasts = result["forecasts"]
    max_temp = max((f["temperature_c"] for f in forecasts), default=None)
    weather_strs = [f.get("weather", "") for f in forecasts]
    if any("비" in w or "소나기" in w for w in weather_strs):
        condition = "RAINY"
    elif any("흐림" in w or "구름" in w for w in weather_strs):
        condition = "CLOUDY"
    else:
        condition = "CLEAR"
    return {"weather_condition": condition, "max_temp_forecast_c": max_temp}


def status_color(s):
    return {"ok": "#3b6d11", "warn": "#854f0b", "err": "#a32d2d"}.get(s, "#888780")

def status_bg(s):
    return {"ok": "#eaf3de", "warn": "#faeeda", "err": "#fcebeb"}.get(s, "#f1efe8")

def status_text(s):
    return {"ok": "정상", "warn": "주의", "err": "경보"}.get(s, "-")

def bar_color(t, target):
    d = t - target
    if d < -2: return "#85b7eb"
    if d >  2: return "#e24b4a"
    return "#1d9e75"

def temp_pct(t, mn, mx):
    return max(0.0, min(100.0, (t - mn) / (mx - mn) * 100))

def badge_html(text, kind="ok"):
    return f'<span class="badge badge-{kind}">{text}</span>'

def hex_to_rgba(hex_color, alpha=0.08):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"rgba({r},{g},{b},{alpha})"

def log_action(action):
    ts = datetime.now().strftime("%H:%M")
    st.session_state.ctrl_log.insert(0, f"{ts}  {action}")


# API 데이터로 dummy_data 갱신 (UI 코드 변경 없이 실데이터 사용)
def _merge_api_data():
    _fids = [f["factory_id"] for f in dummy_data.get("factories", [])] or [1, 2, 3, 4]

    with ThreadPoolExecutor(max_workers=5 + len(_fids) * 2 + 1) as ex:
        f_future = ex.submit(fetch_factories)
        a_future = ex.submit(fetch_alerts)
        s_future = ex.submit(fetch_schedules)
        w_future = ex.submit(fetch_weather)
        l_future = ex.submit(fetch_live_sensors)
        j_future = ex.submit(fetch_jobs)
        tp_futures = {fid: ex.submit(fetch_temp_predict, fid) for fid in _fids}
        mt_futures = {fid: ex.submit(fetch_maintenance, fid) for fid in _fids}

        api_factories = f_future.result()
        api_alerts_data = a_future.result()
        api_schedules_data = s_future.result()
        api_weather = w_future.result()
        api_live = l_future.result()
        api_jobs = j_future.result()
        api_temp_predict = {fid: fut.result() for fid, fut in tp_futures.items()}
        api_maintenance = {fid: fut.result() for fid, fut in mt_futures.items()}

    # 보조 인덱스
    live_by_id = {s["factory_id"]: s for s in api_live}
    from datetime import timezone as _tz
    now_str = datetime.now(_tz.utc).isoformat()
    active_mode_by_id = {}
    for s in api_schedules_data:
        fid = s["factory_id"]
        start = s.get("start_at", "")
        end = s.get("end_at", "") or ""
        if start <= now_str and (not end or end >= now_str):
            active_mode_by_id[fid] = s.get("mode", "OFF")

    # factories
    if api_factories:
        merged = []
        dummy_by_id = {f["factory_id"]: f for f in dummy_data.get("factories", [])}
        for f in api_factories:
            fid = f["factory_id"]
            base = dict(dummy_by_id.get(fid, {}))
            live = live_by_id.get(fid, {})
            base.update({
                "factory_id": fid,
                "name": f.get("name", base.get("name")),
                "status": f.get("status", base.get("status", "stopped")),
                "temperature_c": f.get("current_temp", base.get("temperature_c")),
                "humidity_pct": f.get("current_humidity", base.get("humidity_pct")),
                "last_seen_at": f.get("last_seen_at"),
                "target_temp_c": f["target_temp_c"] if f.get("target_temp_c") is not None else base.get("target_temp_c", -18.0),
                "manual_stop": f["manual_stop"] if f.get("manual_stop") is not None else base.get("manual_stop", False),
                "current_stock_units": f["current_stock_units"] if f.get("current_stock_units") is not None else base.get("current_stock_units", 0),
                "capacity_units": f["max_quantity"] if f.get("max_quantity") is not None else base.get("capacity_units", 0),
                "control_mode": f["control_mode"] if f.get("control_mode") is not None else base.get("control_mode", "AUTO"),
                "node_id": f["node_id"] if f.get("node_id") is not None else (live.get("node_id") or base.get("node_id", "-")),
                "communication_status": live.get("communication", base.get("communication_status", "UNKNOWN")),
                "current_schedule_mode": active_mode_by_id.get(fid, base.get("current_schedule_mode", "OFF")),
            })
            merged.append(base)
        dummy_data["factories"] = merged

    # alerts
    if api_alerts_data:
        dummy_data["alerts"] = [
            {
                "alert_id": a["id"],
                "factory_id": a["factory_id"],
                "level": {"high": "ERROR", "medium": "WARNING", "low": "INFO"}.get(
                    (a.get("priority") or "low").lower(), "INFO"
                ),
                "type": "TEMP_DEVIATION",
                "message": a.get("message", ""),
                "created_at": a.get("triggered_at") or a.get("created_at"),
                "is_acknowledged": a.get("is_acknowledged", False),
                "acknowledged_by": None,
            }
            for a in api_alerts_data
        ]

    # schedules
    if api_schedules_data:
        dummy_data["schedules"] = [
            {
                "schedule_id": s["id"],
                "factory_id": s["factory_id"],
                "target_temp_c": s.get("target_temp"),
                "mode": s.get("mode"),
                "start_at": s.get("start_at"),
                "end_at": s.get("end_at"),
            }
            for s in api_schedules_data
        ]

    # weather → environment_weights 갱신
    if api_weather:
        ew = dummy_data.get("environment_weights", {})
        ew["weather_condition"] = api_weather["weather_condition"]
        if api_weather["max_temp_forecast_c"] is not None:
            ew["max_temp_forecast_c"] = api_weather["max_temp_forecast_c"]
        from datetime import datetime as _dt
        ew["updated_at"] = _dt.now().strftime("%Y-%m-%dT%H:%M")
        dummy_data["environment_weights"] = ew

    # sensor_logs → history 데이터로 교체 (공장별 병렬 조회)
    factory_ids = [f["factory_id"] for f in dummy_data.get("factories", [])]
    if factory_ids:
        with ThreadPoolExecutor(max_workers=len(factory_ids)) as ex:
            hist_futures = {fid: ex.submit(fetch_sensor_history_full, fid) for fid in factory_ids}
            all_history = []
            for fid, fut in hist_futures.items():
                all_history.extend(fut.result())
        if all_history:
            dummy_data["sensor_logs"] = all_history

    # predict_temperature — API 단일 예측값을 시계열로 변환
    from datetime import timedelta as _td
    _now = datetime.now()
    tp_list = []
    for fid, data in api_temp_predict.items():
        if data and data.get("predicted_temp") is not None:
            current = data.get("current_temp") or data["predicted_temp"]
            predicted = data["predicted_temp"]
            horizon = data.get("horizon_minutes", 60)
            steps = 4
            for i in range(steps + 1):
                t = _now + _td(minutes=horizon * i / steps)
                temp = round(current + (predicted - current) * i / steps, 2)
                tp_list.append({
                    "factory_id": fid,
                    "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S"),
                    "predicted_temperature_c": temp,
                    "lower_bound_c": round(temp - 0.5, 2),
                    "upper_bound_c": round(temp + 0.5, 2),
                })
    if tp_list:
        dummy_data["predict_temperature"] = tp_list

    # predict_maintenance
    mt_list = []
    for fid, data in api_maintenance.items():
        if data:
            rec = data.get("recommendation", "UNKNOWN")
            if rec == "UNKNOWN":
                continue
            risk = "LOW" if rec == "NORMAL" else "HIGH"
            mpd = data.get("minutes_per_degree")
            health = round(max(0.0, min(1.0, 1.0 - (mpd - 10) / 20)), 2) if mpd else 1.0
            mt_list.append({
                "factory_id": fid,
                "health_score": health,
                "maintenance_risk": risk,
                "reason": data.get("message", ""),
                "recommended_action": "이상 없음" if rec == "NORMAL" else "설비 점검 권고",
            })
    if mt_list:
        dummy_data["predict_maintenance"] = mt_list

    # jobs
    if api_jobs:
        dummy_data["jobs"] = [
            {
                "job_id": j["id"],
                "factory_id": j.get("factory_id"),
                "is_active": j.get("status") in ("pending", "in_progress"),
                "target_units": j.get("quantity") or 0,
                "produced_units": j.get("produced_units") or 0,
                "remaining_units": j.get("remaining_units") or 0,
                "progress_rate": j.get("progress_rate") or 0.0,
                "deadline_at": j.get("deadline_at"),
                "status": j.get("status"),
                "strategy": "BALANCED",
            }
            for j in api_jobs
        ]

_merge_api_data()

# 데이터
FACTORIES = [
    {
        "id": f"F-{f['factory_id']:02d}",
        "factory_id": f["factory_id"],
        "name": f["name"],
        "temp": f["temperature_c"],
        "hum": f["humidity_pct"],
        "power": 0,
        "status": convert_status(f["status"]),
        "raw_status": f["status"],
        "target": f["target_temp_c"],
        "max_temp": f["target_temp_c"] + 2,
        "min_temp": f["target_temp_c"] - 8,
        "equip": make_equip(f),
        "alarms": get_factory_alarms(dummy_data, f["factory_id"]),
        "manual_stop": f["manual_stop"],
        "current_stock_units": f["current_stock_units"],
        "capacity_units": f["capacity_units"],
    }
    for f in dummy_data["factories"]
]


# 세션 초기화
def init_state():
    defaults = {
        "ctrl_log": [],
        "emergency": False,
        "factories": [dict(f) for f in FACTORIES],
        "power_kw": 847.0,
        "solar_kw": 238.0,
        "last_tick": time.time(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# 실시간 센서 갱신 (5초 캐시 기반, 데이터 없으면 기존값 유지)
_live = {s["factory_id"]: s for s in fetch_live_sensors()}
for f in st.session_state.factories:
    live = _live.get(f["factory_id"])
    if live:
        if live.get("temperature_c") is not None:
            f["temp"] = live["temperature_c"]
        if live.get("humidity_pct") is not None:
            f["hum"] = live["humidity_pct"]


# 차트 함수
def sparkline_fig(data, color, height=50):
    y_min = min(data) - 0.2
    y_max = max(data) + 0.2
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=data, mode="lines",
        line=dict(color=color, width=1.8, shape="spline")))
    fig.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=height,
        paper_bgcolor="rgba(0,0,0,0)",  plot_bgcolor=hex_to_rgba(color, 0.08),
        xaxis=dict(visible=False), yaxis=dict(visible=False, range=[y_min, y_max]), showlegend=False)
    return fig

def temp_trend_fig(f, n=20):
    base = f["temp"]
    history = fetch_sensor_history(f["factory_id"])
    data = history if len(history) >= 2 else ([base] * n)
    n = len(data)
    clr  = bar_color(base, f["target"])
    fig  = go.Figure()
    fig.add_trace(go.Scatter(y=[f["target"]]*n, mode="lines",
        line=dict(color="#e0e3ea", width=1, dash="dash"), showlegend=False))
    fig.add_trace(go.Scatter(y=data, mode="lines+markers",
        line=dict(color=clr, width=2, shape="spline"),
        marker=dict(size=4, color=clr),
        fill="tozeroy", fillcolor=hex_to_rgba(clr, 0.08), showlegend=False))
    fig.update_layout(margin=dict(l=40,r=10,t=10,b=20), height=120,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickvals=[0, max(0, n-1)], ticktext=["1시간 전","현재"],
                   tickfont=dict(size=10,color="#b4b2a9"), gridcolor="rgba(0,0,0,0)"),
        yaxis=dict(tickfont=dict(size=10,color="#888780"), gridcolor="#f1efe8"))
    return fig

def temp_predict_fig(factory_id, current_temp):
    preds = get_temp_predictions(dummy_data, factory_id)
    if not preds: return None
    times     = [p["timestamp"][11:16] for p in preds]
    predicted = [p["predicted_temperature_c"] for p in preds]
    lower     = [p["lower_bound_c"] for p in preds]
    upper     = [p["upper_bound_c"] for p in preds]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=times+times[::-1], y=upper+lower[::-1],
        fill="toself", fillcolor="rgba(55,138,221,0.10)",
        line=dict(color="rgba(0,0,0,0)"), name="신뢰구간"))
    fig.add_trace(go.Scatter(x=times, y=predicted, mode="lines+markers",
        line=dict(color="#378add", width=2, dash="dash"),
        marker=dict(size=5), name="예측 온도"))
    fig.add_hline(y=-18.0, line_dash="dot", line_color="#e24b4a",
        annotation_text="목표 -18°C", annotation_font_size=10)
    fig.update_layout(margin=dict(l=40,r=10,t=10,b=20), height=140,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.2, font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(tickfont=dict(size=10,color="#888780"), gridcolor="rgba(0,0,0,0)"),
        yaxis=dict(tickfont=dict(size=10,color="#888780"), gridcolor="#f1efe8", ticksuffix="°C"))
    return fig

def schedule_fig(dummy_data):
    now_h = datetime.now().hour

    rows = ["공장 1", "공장 2", "공장 3", "공장 4", "요금대"]
    z = [[0 for _ in range(24)] for _ in rows]

    schedules = dummy_data.get("schedules", [])
    blocks = schedules[0].get("blocks", []) if schedules else []

    mode_map = {
        "ON": 1,
        "PRECOOL": 1,
        "COASTING": 2,
        "SOLAR_PRIORITY": 3,
        "OFF": 0,
    }

    for block in blocks:
        fid = block["factory_id"]
        row_idx = fid - 1

        start_h = int(block["start_at"][11:13])
        end_h = int(block["end_at"][11:13])
        mode = block["mode"]

        for h in range(start_h, end_h):
            if 0 <= h < 24:
                z[row_idx][h] = mode_map.get(mode, 0)

    pricing = dummy_data.get("pricing_tou", {}).get("slots", [])
    fee_row_idx = 4

    for slot in pricing:
        sh = slot["start_hour"]
        eh = slot["end_hour"]
        price = slot["price"]

        value = 2 if price >= 180 else 0

        if sh < eh:
            hours = range(sh, eh)
        else:
            hours = list(range(sh, 24)) + list(range(0, eh))

        for h in hours:
            z[fee_row_idx][h] = value

    colorscale = [
        [0.00, "#f1efe8"], [0.25, "#f1efe8"],
        [0.25, "#378add"], [0.50, "#378add"],
        [0.50, "#e24b4a"], [0.75, "#e24b4a"],
        [0.75, "#639922"], [1.00, "#639922"],
    ]        

    fig = go.Figure(go.Heatmap(z=z, x=[f"{h}h" for h in range(24)], y=rows,
        colorscale=colorscale, zmin=0, zmax=3, showscale=False, xgap=1, ygap=2))
    fig.add_vline(x=now_h-0.5, line_width=2, line_color="#1a1a2e", opacity=0.6)
    fig.update_layout(margin=dict(l=60,r=10,t=10,b=30), height=170,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickvals=[0,6,12,18,23], ticktext=["0h","6h","12h","18h","24h"],
                   tickfont=dict(size=10,color="#888780"), gridcolor="rgba(0,0,0,0)"),
        yaxis=dict(tickfont=dict(size=11,color="#888780"), gridcolor="rgba(0,0,0,0)"))
    return fig


# HTML 컴포넌트 함수
def kpi_card(label, value, unit, sub, pct, accent, delta_text="", delta_kind="ok"):
    bar = f'<div class="kpi-bar-wrap"><div class="kpi-bar-fill" style="width:{pct:.1f}%;background:{accent}"></div></div>'
    delta = f'<div class="delta-{delta_kind}">{delta_text}</div>' if delta_text else ""
    return f"""<div class="kpi-card" style="--accent:{accent}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}<span class="kpi-unit">{unit}</span></div>
      {bar}<div class="kpi-sub">{sub}</div>{delta}</div>"""

def env_weights_html():
    ew = dummy_data.get("environment_weights",{})
    icon = {"CLEAR":"☀️","CLOUDY":"⛅","RAINY":"🌧️"}.get(ew.get("weather_condition",""),"🌡️")
    items = [
        ("내일 날씨",   f"{icon} {ew.get('weather_condition','—')}"),
        ("최고 기온",   f"{ew.get('max_temp_forecast_c','—')}°C"),
        ("기온 가중치", f"w = {ew.get('w_temp','—')}"),
        ("태양광 가중치",f"w = {ew.get('w_solar','—')}"),
        ("갱신",        ew.get("updated_at","")[:16].replace("T"," ")),
    ]
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:0.5px solid #f1efe8">'
        f'<span style="font-size:14px;font-weight:500;color:#515151">{k}</span>'
        f'<span style="font-size:14px;color:#444441">{v}</span></div>'
        for k,v in items)
    return f'<div style="background:#fff;border:0.5px solid #e0e3ea;border-radius:8px;padding:10px">{rows}</div>'

def maintenance_html():
    items = dummy_data.get("predict_maintenance",[])
    rows  = []
    for m in items:
        sc    = m["health_score"]
        risk  = m["maintenance_risk"]
        color = "#1d9e75" if risk=="LOW" else ("#ba7517" if risk=="MEDIUM" else "#e24b4a")
        bg    = "#eaf3de" if risk=="LOW" else ("#faeeda" if risk=="MEDIUM" else "#fcebeb")
        rows.append(f"""<div style="padding:8px 10px;background:{bg};border-radius:6px;margin-bottom:6px">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
            <span style="font-size:15px;font-weight:500;color:#1a1a2e">공장 {m['factory_id']}</span>
            <span style="font-size:16px;font-weight:600;color:{color}">{sc:.2f}</span>
          </div>
          <div style="height:5px;background:rgba(255,255,255,.5);border-radius:3px;overflow:hidden;margin-bottom:5px">
            <div style="height:5px;width:{sc*100:.0f}%;background:{color};border-radius:3px"></div>
          </div>
          <div style="font-size:13px;color:#444441">{m['reason']}</div>
          <div style="font-size:13px;font-weight:500;color:{color};margin-top:3px"> - {m['recommended_action']}</div>
        </div>""")
    return f'<div style="font-size:13px;color:#515151;margin-bottom:8px">1.0: 정상,  0.6 ▼ :  주의,  0.4 ▼ :  교체 권고</div>{"".join(rows)}'


dash   = dummy_data.get("dashboard_summary",{})
pwr    = st.session_state.power_kw
sol    = st.session_state.solar_kw
risk   = dash.get("risk_index", 0)
rlevel = dash.get("risk_level","LOW")
risk_color = "#e24b4a" if risk>80 else ("#ba7517" if risk>40 else "#1d9e75")
daily_wan   = round(dash.get("estimated_daily_saving_krw",0)/10000)
monthly_wan = round(dash.get("estimated_monthly_saving_krw",0)/10000)
carbon      = dash.get("carbon_reduction_tco2_year",0)
unacked     = get_all_unacked_alerts(dummy_data)

warn_count = sum(1 for f in st.session_state.factories if f["status"] in ("warn","err"))

# 최상단 경보 메시지 배너
# if unacked:
#     alert_items = "".join(
#         f'<span style="display:inline-flex;align-items:center;gap:6px;'
#         f'padding:4px 12px;background:#faeeda;border:0.5px solid #fac775;'
#         f'border-radius:20px;font-size:11px;color:#854f0b;white-space:nowrap">'
#         f'⚠ {a["message"][:40]}{"…" if len(a["message"])>40 else ""}'
#         f'<span style="opacity:.6">{a["created_at"][11:16]}</span></span>'
#         for a in unacked
#     )
#     st.markdown(
#         f'<div style="display:flex;gap:8px;flex-wrap:wrap;padding:6px 0 10px">{alert_items}</div>',
#         unsafe_allow_html=True
#     )

warn_badge = badge_html(f"주의 {warn_count}건","warn") if warn_count or st.session_state.emergency else ""
emg_badge  = badge_html("비상 정지 활성화","err") if st.session_state.emergency else ""

header_left, header_right = st.columns([8, 1])

with header_left:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
      <div class="dash-logo"><span>냉동 공장</span></div>
      <span><span class="live-dot"></span><span style="font-size:12px;color:#888780">LIVE</span></span>
      {badge_html("시스템 정상","ok")}
      {warn_badge}
      {emg_badge}
      <span style="font-size:12px;color:#888780;letter-spacing:.5px;margin-left:4px">
        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
      </span>
    </div>
    """, unsafe_allow_html=True)

with header_right:
    notification_popover(dummy_data, unacked)

# KPI 카드 4개
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(kpi_card("현재 전력 소비", f"{pwr:.0f}", "kW",
        f"계약 한도 1,200 kW · {dash.get('running_factories',0)}/{dash.get('total_factories',0)}공장 가동",
        pwr/12, "#378add", "전일 대비 -12%", "ok"), unsafe_allow_html=True)
with k2:
    st.markdown(kpi_card("태양광 발전", f"{sol:.0f}", "kW",
        "이달 발전량 38,200 kWh",
        sol/3.6, "#639922", f"자가소비율 {sol/pwr*100:.1f}%", "ok"), unsafe_allow_html=True)
with k3:
    st.markdown(kpi_card("일일 절감액", f"{daily_wan}", "만원",
        f"이달 누적 {monthly_wan}만원",
        min(100, daily_wan/2), "#ba7517",
        f"연간 탄소 감축 {carbon}tCO₂", "ok"), unsafe_allow_html=True)
with k4:
    st.markdown(kpi_card("리스크 지수", f"{risk}", "",
        f"수준: {rlevel}  ·  통신: {dash.get('communication_status','')}",
        risk, risk_color,
        "즉각 조치 필요" if risk>80 else ""), unsafe_allow_html=True)

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)


main_col, side_col = st.columns([3.2, 1], gap="large")


# 우측
with side_col:

    # 설비 상태 분석
    st.markdown('<div class="card-title">설비 상태 분석</div>', unsafe_allow_html=True)
    st.markdown(maintenance_html(), unsafe_allow_html=True)
    st.markdown(
        "<hr style='margin:15px 0 8px 0; border:none; border-top:1px solid #e0e3ea;'>",
        unsafe_allow_html=True
    )

    # 환경 정보
    st.markdown('<div class="card-title">환경 정보</div>', unsafe_allow_html=True)
    st.markdown(env_weights_html(), unsafe_allow_html=True)


# tabs
with main_col:
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["공장 현황", "에너지 · 비용", "운영 관리", "수동 제어"])

    # 공장 현황
    with tab1:
        factory_status(
            lambda factory_id: get_maintenance_info(dummy_data, factory_id),
            temp_pct,
            bar_color,
            status_color,
            status_bg,
            status_text,
            lambda f: factory_detail(
                f,
                status_color,
                status_bg,
                status_text,
                lambda factory_id: get_maintenance_info(dummy_data, factory_id),
                lambda factory_id: get_sensor_logs(dummy_data, factory_id),
                lambda factory_id: get_door_events(dummy_data, factory_id),
                sparkline_fig,
                temp_predict_fig,
                temp_trend_fig,
                issue_qr_token,
            ),
            log_action,
            lambda node_id, factory_id, action, payload: requests.post(
                f"{API_BASE_URL}/api/v1/control/manual",
                json={
                    "node_id": node_id,
                    "factory_id": factory_id,
                    "action": action,
                    "reason": payload.get("reason", ""),
                    "allow_high_duty": False,
                    "max_duty": 100.0,
                    "requested_by": "manual",
                    **{k: v for k, v in payload.items() if k != "reason"},
                },
                timeout=5,
            ),
        )

    # 에너지 비용
    with tab2:
        energy_cost(dummy_data)

    # 운영 관리
    with tab3:
        operation_manage(dummy_data, schedule_fig)
    
    # 수동 제어 
    with tab4:
        manual_control(log_action)
        
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# 플로팅 마이크 버튼
mic_path = Path(__file__).resolve().parents[1] / "assets" / "mic.png"
mic_b64 = base64.b64encode(mic_path.read_bytes()).decode()

st.markdown(f"""
<style>
.st-key-floating_mic_btn {{
    position: fixed;
    bottom: 32px;
    right: 32px;
    z-index: 9999;
}}
.st-key-floating_mic_btn button {{
    width: 56px !important;
    height: 56px !important;
    border-radius: 50% !important;
    background: transparent !important;
    border: none !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.18) !important;
    padding: 0 !important;
    cursor: pointer !important;
    background-image: url("data:image/png;base64,{mic_b64}") !important;
    background-size: 60% !important;
    background-repeat: no-repeat !important;
    background-position: center !important;
    background-color: white !important;
}}
.st-key-floating_mic_btn button p {{ display: none !important; }}
</style>
""", unsafe_allow_html=True)

if st.button(" ", key="floating_mic_btn"):
    st.session_state["voice_dialog_open"] = True

@st.dialog("음성 제어")
def voice_dialog():
    mic_tab, text_tab = st.tabs(["마이크 입력", "텍스트 입력"])

    with mic_tab:
        audio = st.audio_input("마이크 버튼을 눌러 명령을 말하세요")
        if audio and st.button("분석", key="dlg_analyze_audio"):
            with st.spinner("음성 인식 중..."):
                try:
                    resp = requests.post(
                        f"{API_BASE_URL}/api/v1/nl-command/parse-audio",
                        files={"file": (audio.name, audio.getvalue(), audio.type)},
                        timeout=60.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    st.session_state["nl_transcript"] = data["transcript"]
                    st.session_state["nl_pending_command"] = data["command"]
                except Exception as exc:
                    st.error(str(exc))

    with text_tab:
        nl_text = st.text_area("명령을 입력하세요", placeholder="1번 공장 목표온도 -20도로 설정해줘")
        if st.button("분석", key="dlg_analyze_text"):
            with st.spinner("분석 중..."):
                try:
                    resp = requests.post(
                        f"{API_BASE_URL}/api/v1/nl-command/parse-text",
                        json={"text": nl_text},
                        timeout=15.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    st.session_state["nl_transcript"] = data["transcript"]
                    st.session_state["nl_pending_command"] = data["command"]
                except Exception as exc:
                    st.error(str(exc))

    if st.session_state.get("nl_pending_command"):
        cmd = st.session_state["nl_pending_command"]
        st.info(f"인식된 명령: {st.session_state.get('nl_transcript', '')}")
        st.caption(cmd.get("summary", ""))
        st.json(cmd)

        factory_options = {f["factory_id"]: f["name"] for f in st.session_state.get("factories", [])}
        if not factory_options:
            factory_options = {1: "공장 1", 2: "공장 2", 3: "공장 3", 4: "공장 4"}

        llm_fid = cmd.get("factory_id")
        default_fid = llm_fid if llm_fid in factory_options else list(factory_options.keys())[0]
        selected_fid = st.selectbox(
            "대상 공장",
            options=list(factory_options.keys()),
            format_func=lambda x: f"{x}번 - {factory_options[x]}",
            index=list(factory_options.keys()).index(default_fid),
        )

        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("실행하기", use_container_width=True, type="primary"):
                nl_body = {
                    "node_id": "nodeA",
                    "factory_id": selected_fid,
                    "action": cmd["action"],
                    "reason": f"음성 명령: {cmd.get('summary', '')}",
                    "allow_high_duty": False,
                    "max_duty": 100.0,
                    "requested_by": "voice",
                }
                if cmd.get("value") is not None:
                    nl_body["value"] = cmd["value"]
                if cmd.get("direction"):
                    nl_body["direction"] = cmd["direction"]
                if cmd.get("seconds") is not None:
                    nl_body["seconds"] = cmd["seconds"]
                if cmd.get("fan_cooldown_sec") is not None:
                    nl_body["fan_cooldown_seconds"] = cmd["fan_cooldown_sec"]
                try:
                    requests.post(f"{API_BASE_URL}/api/v1/control/manual", json=nl_body, timeout=5)
                    st.session_state["nl_pending_command"] = None
                    st.session_state["nl_show_success"] = True
                except Exception as exc:
                    st.error(str(exc))
        with cancel_col:
            if st.button("취소", use_container_width=True):
                st.session_state["nl_pending_command"] = None

    if st.session_state.get("nl_show_success"):
        st.success("명령 전송 완료")
        st.session_state["nl_show_success"] = False
        import time as _time
        _time.sleep(2)
        st.rerun()

if st.session_state.get("voice_dialog_open"):
    st.session_state["voice_dialog_open"] = False
    voice_dialog()
