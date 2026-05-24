import streamlit as st
import plotly.graph_objects as go
from datetime import datetime


def energy_cost_fig(dummy_data):
    ch = dummy_data.get("charts", {}).get("hourly", {})
    labels = ch.get("labels", [str(h) for h in range(24)])
    before = ch.get("before_optimization", [])
    after = ch.get("after_optimization", [])
    solar = ch.get("solar_contribution", [])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=before, name="최적화 전", mode="lines",
        line=dict(color="#e24b4a", width=1.5, dash="dot"), opacity=0.7
    ))
    fig.add_trace(go.Bar(
        x=labels, y=solar, name="태양광 기여",
        marker_color="#639922", opacity=0.55
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=after, name="최적화 후", mode="lines+markers",
        line=dict(color="#378add", width=2), marker=dict(size=4),
        fill="tozeroy", fillcolor="rgba(55,138,221,0.06)"
    ))

    fig.add_vrect(
        x0="10", x1="16", fillcolor="#e24b4a", opacity=0.04,
        annotation_text="피크요금", annotation_position="top left",
        annotation_font=dict(size=10, color="#e24b4a")
    )

    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=30),
        height=200,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h", y=1.15, x=0,
            font=dict(size=12, color="#888780"),
            bgcolor="rgba(0,0,0,0)"
        ),
        xaxis=dict(tickfont=dict(size=12, color="#888780"), gridcolor="#f1efe8"),
        yaxis=dict(tickfont=dict(size=12, color="#888780"), gridcolor="#f1efe8"),
        barmode="overlay",
        hovermode="x unified"
    )
    return fig


def savings_fig(dummy_data, kind):
    if kind == "monthly":
        d = {
            "labels": ["1월", "2월", "3월"],
            "vals": [165, 172, 178],
            "max": 220
        }
    else:
        charts = dummy_data.get("charts", {}).get("savings_daily", {})
        raw_labels = charts.get(
            "labels",
            ["03-27", "03-28", "03-29", "03-30", "03-31", "04-01", "04-02"]
        )
        raw_vals = charts.get("values", [142, 138, 151, 148, 155, 149, 148])
        vals_wan = [round(v / 10000) for v in raw_vals]

        d = {
            "labels": raw_labels,
            "vals": vals_wan,
            "max": max(vals_wan) * 1.4
        }

    fig = go.Figure(go.Bar(
        x=d["vals"],
        y=d["labels"],
        orientation="h",
        marker_color="#378add",
        marker_line_width=0,
        text=[f"₩{v}만" for v in d["vals"]],
        textposition="outside",
        textfont=dict(size=12, color="#444441")
    ))

    fig.update_layout(
        margin=dict(l=10, r=60, t=10, b=10),
        height=180,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[0, d["max"] * 1.25]),
        yaxis=dict(
            tickfont=dict(size=13, color="#888780"),
            gridcolor="rgba(0,0,0,0)",
            categoryorder="array",
            categoryarray=d["labels"][::-1]
        ),
        showlegend=False
    )
    return fig


def solar_predict_fig(dummy_data):
    sd = dummy_data.get("predict_solar", [])
    times = [s["timestamp"][11:13] + "시" for s in sd]
    values = [s["predicted_solar_kwh"] for s in sd]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=times,
        y=values,
        mode="lines+markers",
        line=dict(color="#639922", width=2.5, shape="spline"),
        marker=dict(size=5, color="#639922"),
        fill="tozeroy",
        fillcolor="rgba(99,153,34,0.12)"
    ))

    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=30),
        height=150,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickfont=dict(size=12, color="#888780"), gridcolor="rgba(0,0,0,0)"),
        yaxis=dict(tickfont=dict(size=12, color="#888780"), gridcolor="#f1efe8", ticksuffix="kWh"),
        showlegend=False
    )
    return fig


def tou_status_html(dummy_data):
    pricing = dummy_data.get("pricing_tou", {})
    current = pricing.get("current_price_krw_per_kwh", 180)
    slots = pricing.get("slots", [])
    now_h = datetime.now().hour

    items = []

    for slot in slots:
        sh, eh = slot["start_hour"], slot["end_hour"]
        active = (sh <= now_h < eh) if sh < eh else (now_h >= sh or now_h < eh)
        price = slot["price"]

        color = "#e24b4a" if price >= 180 else ("#ba7517" if price >= 140 else "#378add")
        bg = "#fcebeb" if active and price >= 180 else ("#faeeda" if active else "#f8f8f6")
        border = f"1.5px solid {color}" if active else "1px solid #e0e3ea"

        current_badge = (
            f'<div style="font-size:10px;color:{color};font-weight:500;margin-top:2px">▶ 현재</div>'
            if active else ""
        )

        items.append(
            f'<div style="flex:1;padding:6px 8px;border-radius:6px;background:{bg};border:{border}">'
            f'<div style="font-size:13px;color:#888780">{sh:02d}~{eh:02d}시</div>'
            f'<div style="font-size:15px;font-weight:600;color:{color}">₩{price}</div>'
            f'{current_badge}'
            f'</div>'
        )

    return (
        f'<div style="background:#fff;border:0.5px solid #e0e3ea;border-radius:8px;padding:10px">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">'
        f'<span></span>'
        f'<span style="font-size:16px;font-weight:600;color:#e24b4a">₩{current}'
        f'<span style="font-size:12px;font-weight:400;color:#888780"> /kWh</span></span>'
        f'</div>'
        f'<div style="display:flex;gap:5px">'
        f'{"".join(items)}'
        f'</div>'
        f'</div>'
    )


def energy_cost(dummy_data):
    if "energy_sub_menu" not in st.session_state:
        st.session_state.energy_sub_menu = "전력 비용"

    menu_items = ["전력 비용", "태양광 발전", "누적 절감액", "TOU"]
    menu_keys = ["cost", "solar", "savings", "tou"]

    cols = st.columns([1, 1, 1, 1, 5], gap="small")

    for col, label, key in zip(cols, menu_items, menu_keys):
        with col:
            is_active = st.session_state.energy_sub_menu == label

            st.markdown(f"""
            <style>
            .st-key-energy_btn_{key} button {{
                background-color: {"#d8e5f3" if is_active else "#ffffff"} !important;
                color: {"#ffffff" if is_active else "#444441"} !important;
                border: 1px solid {"#aac7e7" if is_active else "#e0e3ea"} !important;
                border-radius: 8px !important;
                min-height: 33px !important;
                height: 33px !important;
                padding: 0 10px !important;
                margin-bottom: 10px !important;
                white-space: nowrap !important;
            }}

            .st-key-energy_btn_{key} button p {{
                font-size: 14px !important;
                font-weight: 500;
                line-height: 14px !important;
                white-space: nowrap !important;
                word-break: keep-all !important;
                color: {"#104f8e" if is_active else "#535350"} !important;
            }}
            </style>
            """, unsafe_allow_html=True)

            if st.button(label, key=f"energy_btn_{key}", use_container_width=True):
                st.session_state.energy_sub_menu = label
                st.rerun()

    selected = st.session_state.energy_sub_menu

    if selected == "전력 비용":
        st.markdown('<div class="card-title">시간대별 전력 비용 비교</div>', unsafe_allow_html=True)
        st.plotly_chart(energy_cost_fig(dummy_data), width="stretch", config={"displayModeBar": False})

        ch = dummy_data.get("charts", {}).get("hourly", {})
        b_sum = sum(ch.get("before_optimization", []))
        a_sum = sum(ch.get("after_optimization", []))
        s_sum = sum(ch.get("solar_contribution", []))
        spct = round((b_sum - a_sum) / b_sum * 100, 1) if b_sum else 0

        st.markdown(f"""
        <div style="display:flex;gap:16px;margin-top:-4px;flex-wrap:wrap">
            <span style="font-size:13px;color:#888780">절감율 <b style="color:#378add">{spct}%</b></span>
            <span style="font-size:13px;color:#888780">태양광 기여 <b style="color:#639922">₩{s_sum:,}</b></span>
            <span style="font-size:13px;color:#888780">일일 절감 <b style="color:#1d9e75">₩{b_sum - a_sum:,}</b></span>
        </div>
        """, unsafe_allow_html=True)

    elif selected == "태양광 발전":
        st.markdown('<div class="card-title">오늘 태양광 발전 예측</div>', unsafe_allow_html=True)
        st.plotly_chart(solar_predict_fig(dummy_data), width="stretch", config={"displayModeBar": False})

        sd = dummy_data.get("predict_solar", [])
        max_sol = max((s["predicted_solar_kwh"] for s in sd), default=0)
        total_sol = sum(s["predicted_solar_kwh"] for s in sd)

        st.markdown(f"""
        <div style="display:flex;gap:12px;margin-top:-4px;margin-bottom:12px">
            <span style="font-size:13px;color:#888780">최대 <b style="color:#639922">{max_sol}kWh</b></span>
            <span style="font-size:13px;color:#888780">일계 <b style="color:#639922">{total_sol:.1f}kWh</b></span>
        </div>
        """, unsafe_allow_html=True)

    elif selected == "누적 절감액":
        st.markdown('<div class="card-title">누적 절감액</div>', unsafe_allow_html=True)

        sm_, sd_ = st.tabs(["월별", "일별"])

        with sm_:
            st.plotly_chart(savings_fig(dummy_data, "monthly"), width="stretch", config={"displayModeBar": False})

        with sd_:
            st.plotly_chart(savings_fig(dummy_data, "daily"), width="stretch", config={"displayModeBar": False})

        st.markdown("""
        <div style="border-top:0.5px solid #e0e3ea;padding-top:8px;
            display:flex;justify-content:space-between;align-items:center">
            <span style="font-size:13px;color:#888780">연간 누적</span>
            <span style="font-size:16px;font-weight:500;color:#185fa5">₩1억 2,340만</span>
        </div>
        """, unsafe_allow_html=True)

    elif selected == "TOU":
        st.markdown('<div class="card-title">TOU 요금 현황</div>', unsafe_allow_html=True)
        st.markdown(tou_status_html(dummy_data), unsafe_allow_html=True)