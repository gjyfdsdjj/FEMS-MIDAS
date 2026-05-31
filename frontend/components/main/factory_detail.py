import streamlit as st
import plotly.graph_objects as go
import random
import base64
from pathlib import Path


@st.dialog("공장 상세 정보", width="large")
def factory_detail(
    f,
    status_color,
    status_bg,
    status_text,
    get_maintenance_info,
    get_sensor_logs,
    get_door_events,
    sparkline_fig,
    temp_predict_fig,
    temp_trend_fig,
    issue_qr_token,
):
    sc = status_color(f["status"])
    sb = status_bg(f["status"])
    st_txt = status_text(f["status"])
    maint = get_maintenance_info(f["factory_id"])
    qr_icon_path = Path(__file__).resolve().parents[2] / "assets" / "qr.png"
    qr_icon_base64 = base64.b64encode(qr_icon_path.read_bytes()).decode()

    title_col, qr_col = st.columns([8, 1])

    with title_col:
        st.markdown(f"""
        <div style="display:flex;align-items:center; gap:15px; margin-bottom:-10px">
            <div style="font-size:20px;font-weight:500;color:#1a1a2e">
                {f['name']}
                <span style="font-size:13px;color:#888780;font-weight:400">&nbsp;{f['id']}</span>
            </div>
            <span class="badge" style="background:{sb};color:{sc};font-size:13px;padding:5px 14px;">
                {st_txt}
            </span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    .st-key-qr_popover_wrap {
        display: flex;
        justify-content: flex-end;
        margin-top: -6px;
    }

    .st-key-qr_popover_wrap div[data-testid="stPopover"] button {
        white-space: nowrap !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    with qr_col:
        if f["factory_id"] == 1:
            with st.container(key="qr_popover_wrap"):
                with st.popover("QR 코드"):
                    qr_key = f"qr_data_{f['factory_id']}"
                    qr_data = st.session_state.get(qr_key)

                    button_area = st.empty()

                    if not qr_data:
                        with button_area:
                            clicked = st.button("QR 코드 발급", key=f"qr_issue_{f['factory_id']}")

                        if clicked:
                            with st.spinner(""):
                                result = issue_qr_token(f["factory_id"])

                            if result and result.get("success"):
                                st.session_state[qr_key] = result["data"]
                                qr_data = result["data"]
                                button_area.empty()
                            else:
                                st.error("QR 발급에 실패했습니다.")
                                st.write(result)

                    if qr_data:
                        st.success("발급 완료")
                        st.image(qr_data["qr_code_base64"], width=160)
                        st.markdown(f"""
                        <div style="
                            width: 280px;
                            font-size: 15px;
                            word-break: break-all;
                            line-height: 1.5;
                            background: #f8f8f6;
                            border: 1px solid #e0e3ea;
                            border-radius: 6px;
                            padding: 8px;
                        ">
                            {qr_data["readonly_url"]}
                        </div>
                        """, unsafe_allow_html=True)
                        st.caption(f"만료 시간: {qr_data['expires_at']}")
    st.markdown(
    "<hr style='margin:-20px 0 20px 0; border:none; border-top:1px solid #e0e3ea;'>",
    unsafe_allow_html=True
)

    dm1, dm2, dm3, dm4 = st.columns(4)

    sensor_logs = get_sensor_logs(f["factory_id"])

    hdata = [log["temperature_c"] for log in sensor_logs if log.get("temperature_c") is not None]
    phdata = [log["humidity_pct"] for log in sensor_logs if log.get("humidity_pct") is not None]

    if not hdata:
        hdata = [f["temp"]]
    if not phdata:
        phdata = [f["hum"]]

    stock_pct = round(f["current_stock_units"] / f["capacity_units"] * 100) if f.get("capacity_units") else 0

    for idx, (col, label, val, unit, sub, clr, spark) in enumerate([
        (dm1, "현재 온도", f"{f['temp']:.1f}", "°C", f"목표 {round(f['target'], 1)}°C", sc, hdata),
        (dm2, "현재 습도", f"{f['hum']}", "%RH", "기준 60~75%", "#1d9e75", phdata),
        (dm3, "재고", f"{f['current_stock_units']}", "개", f"용량 {f['capacity_units']}개", "#ba7517", hdata),
    ]):
        with col:
            st.markdown(f"""
            <div class="metric-box">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                    <div class="metric-box-label" style="margin-bottom:0">{label}</div>
                    <div class="metric-box-trend" style="color:{clr};margin-top:0">{sub}</div>
                </div>
                <div class="metric-box-val">{val}<span class="metric-box-unit">{unit}</span></div>
            </div>
            """, unsafe_allow_html=True)

            with st.container(key=f"detail_metric_chart_{idx}"):
                st.plotly_chart(
                    sparkline_fig(spark, clr, 50),
                    use_container_width=True,
                    config={"displayModeBar": False}
                )

    with dm4:
        st.markdown(f"""
        <div class="stock-box">
            <div class="metric-box-label">재고 현황</div>
            <div class="metric-box-val">
                {f['current_stock_units']}<span class="metric-box-unit">/{f['capacity_units']}</span>
            </div>
            <div style="height:5px;background:#f1efe8;border-radius:3px;margin-top:10px;overflow:hidden">
                <div style="width:{stock_pct}%;height:5px;background:#ba7517;border-radius:3px"></div>
            </div>
            <div class="metric-box-trend" style="color:#854f0b">용량 대비 {stock_pct}%</div>
        </div>
        """, unsafe_allow_html=True)

    tab_temp, tab_equip, tab_alarm = st.tabs(["온도", "설비 상태", "경보 · 문열림"])

    # 온도
    with tab_temp:
        row1_left, row1_right = st.columns([1, 1], gap="large")

        with row1_left:
            pred_fig = temp_predict_fig(f["factory_id"], f["temp"])

            st.markdown(
                '<div class="section-label" style="margin-top:10px">온도 예측 (향후 4시간)</div>',
                unsafe_allow_html=True
            )

            if pred_fig:
                st.plotly_chart(pred_fig, use_container_width=True, config={"displayModeBar": False})
            else:
                st.markdown(
                    '<div style="font-size:12px;color:#6e6e6e;padding:4px 0 10px">온도 예측 데이터 없음</div>',
                    unsafe_allow_html=True
                )

        with row1_right:
            st.markdown(
                '<div class="section-label" style="margin-top:10px">온도 추이 (최근 1시간)</div>',
                unsafe_allow_html=True
            )
            st.plotly_chart(temp_trend_fig(f), use_container_width=True, config={"displayModeBar": False})

    # 설비 상태
    with tab_equip:
        row2_left, row2_right = st.columns([1, 1], gap="large")

        with row2_left:
            st.markdown(
                '<div class="section-label" style="margin-top:10px">설비 상태</div>',
                unsafe_allow_html=True
            )

            eq_cols = st.columns(3)

            for j, eq in enumerate(f["equip"]):
                with eq_cols[j % 3]:
                    ec = status_color(eq["s"])

                    st.markdown(f"""
                    <div class="equip-item" style="margin-bottom:6px">
                        <div class="equip-name">{eq['n']}</div>
                        <div class="equip-val">{eq['v']}</div>
                        <div style="font-size:10px;color:{ec};margin-top:2px">
                            {status_text(eq['s'])}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        with row2_right:
            st.markdown(
                '<div class="section-label" style="margin-top:10px">설비 상태 분석</div>',
                unsafe_allow_html=True
            )

            if maint:
                ms = maint["health_score"]
                risk = maint["maintenance_risk"]

                color = "#1d9e75" if risk == "LOW" else ("#ba7517" if risk == "MEDIUM" else "#e24b4a")
                bg = "#eaf3de" if risk == "LOW" else ("#faeeda" if risk == "MEDIUM" else "#fcebeb")

                st.markdown(f"""
                <div style="padding:8px;background:{bg};border-radius:6px;margin-top:4px">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                        <span style="font-size:11px;color:{color};font-weight:500">건강 점수</span>
                        <span style="font-size:14px;font-weight:600;color:{color}">{ms:.2f}</span>
                    </div>
                    <div style="height:5px;background:rgba(255,255,255,.5);border-radius:3px;overflow:hidden;margin-bottom:6px">
                        <div style="height:5px;width:{ms * 100:.0f}%;background:{color};border-radius:3px"></div>
                    </div>
                    <div style="font-size:11px;color:#444441">{maint['reason']}</div>
                    <div style="font-size:11px;font-weight:500;color:{color};margin-top:4px">
                        → {maint['recommended_action']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="font-size:12px;color:#b4b2a9;padding:4px 0 10px">설비 분석 데이터 없음</div>',
                    unsafe_allow_html=True
                )

    # 경보, 문열림
    with tab_alarm:
        row3_left, row3_right = st.columns([1, 1], gap="large")

        with row3_left:
            st.markdown(
                '<div class="section-label" style="margin-top:10px">경보 현황</div>',
                unsafe_allow_html=True
            )

            if not f["alarms"]:
                st.markdown(
                    '<div style="font-size:12px;color:#6e6e6e;padding:4px 0 10px">활성 경보 없음</div>',
                    unsafe_allow_html=True
                )
            else:
                show_all_key = f"alarm_show_all_{f['factory_id']}"
                if show_all_key not in st.session_state:
                    st.session_state[show_all_key] = False

                alarms = f["alarms"]
                visible = alarms if st.session_state[show_all_key] else alarms[:5]

                for alarm in visible:
                    lc = "#854f0b" if alarm["level"] == "WARNING" else "#185fa5"
                    lb = "#faeeda" if alarm["level"] == "WARNING" else "#dbeeff"

                    st.markdown(f"""
                    <div class="alarm-item" style="background:{lb};margin-bottom:4px">
                        <div style="font-weight:500;color:{lc};font-size:12px">
                            {alarm['msg']}{"  ✓" if alarm["acknowledged"] else ""}
                        </div>
                        <div style="color:{lc};opacity:.7;font-size:11px;margin-top:2px">
                            {alarm['time']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                if len(alarms) > 5:
                    if st.session_state[show_all_key]:
                        if st.button("접기", key=f"alarm_fold_{f['factory_id']}"):
                            st.session_state[show_all_key] = False
                    else:
                        if st.button(f"더보기 ({len(alarms) - 5}개 더)", key=f"alarm_more_{f['factory_id']}"):
                            st.session_state[show_all_key] = True

        with row3_right:
            st.markdown(
                '<div class="section-label" style="margin-top:10px">문열림 이벤트</div>',
                unsafe_allow_html=True
            )

            door_events = get_door_events(f["factory_id"])

            if not door_events:
                st.markdown(
                    '<div style="font-size:12px;color:#b4b2a9;padding:4px 0 10px">최근 문열림 이벤트 없음</div>',
                    unsafe_allow_html=True
                )
            else:
                total_duration = sum(event["duration_sec"] for event in door_events)
                estimated_loss = len(door_events) * 0.22

                st.markdown(f"""
                <div style="background:#f8f8f6;border:0.5px solid #e0e3ea;border-radius:6px;
                    padding:8px;margin-bottom:6px">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                        <span style="font-size:11px;color:#888780">총 문열림</span>
                        <span style="font-size:12px;font-weight:600;color:#1a1a2e">{len(door_events)}회</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                        <span style="font-size:11px;color:#888780">누적 시간</span>
                        <span style="font-size:12px;font-weight:600;color:#1a1a2e">{total_duration}초</span>
                    </div>
                    <div style="display:flex;justify-content:space-between">
                        <span style="font-size:11px;color:#888780">냉기 손실 추정</span>
                        <span style="font-size:12px;font-weight:600;color:#e24b4a">+{estimated_loss:.2f}°C</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                for event in door_events[-3:]:
                    st.markdown(f"""
                    <div style="font-size:11px;color:#444441;padding:4px 0;
                        border-bottom:0.5px solid #f1efe8">
                        {event["timestamp"][11:16]} · {event["duration_sec"]}초 열림
                    </div>
                    """, unsafe_allow_html=True)