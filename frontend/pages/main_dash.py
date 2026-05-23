import streamlit as st
import random
import json5
import plotly.graph_objects as go
import time
import sys
import base64
from pathlib import Path
from datetime import datetime

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


# 데이터
FACTORIES = [
    {
        "id": f"F-{f['factory_id']:02d}",
        "factory_id": f["factory_id"],
        "name": f["name"],
        "temp": f["temperature_c"],
        "hum": f["humidity_pct"],
        "power": f["pwm_pct"],
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
        "ctrl_log": [
            control_log_text(log)
            for log in dummy_data.get("control_logs", [])
        ],
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


# 실시간 시뮬레이션
now_t = time.time()
if now_t - st.session_state.last_tick > 3:
    st.session_state.power_kw = max(700, min(1050, st.session_state.power_kw + random.uniform(-8, 8)))
    st.session_state.solar_kw = max(180, min(360,  st.session_state.solar_kw + random.uniform(-3, 3)))
    for f in st.session_state.factories:
        f["temp"] = round(f["temp"] + random.uniform(-0.2, 0.2), 1)
    st.session_state.last_tick = now_t


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
    data = [round(base + random.uniform(-0.8, 0.8), 1) for _ in range(n-1)] + [base]
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
        xaxis=dict(tickvals=[0,n-1], ticktext=["1시간 전","현재"],
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
            ),
            log_action,
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

# 챗봇
mic_path = Path(__file__).resolve().parents[1] / "assets" / "mic.png"

st.markdown(f"""
<a class="floating-chat-btn" href="#">
    <img src="data:image/png;base64,{base64.b64encode(mic_path.read_bytes()).decode()}" />
</a>
""", unsafe_allow_html=True)