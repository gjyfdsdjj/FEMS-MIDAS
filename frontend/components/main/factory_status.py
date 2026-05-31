import streamlit as st


def factory_status(
    get_maintenance_info,
    temp_pct,
    bar_color,
    status_color,
    status_bg,
    status_text,
    show_factory_detail,
    log_action,
    send_command=None,
):
    
    st.markdown("""
    <style>
    .st-key-recoverbtn_0 button,
    .st-key-recoverbtn_1 button,
    .st-key-recoverbtn_2 button,
    .st-key-recoverbtn_3 button {
        background: #1d9e75 !important;
        border-color: #1d9e75 !important;
        color: white !important;
        border: none !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    fc_cols = st.columns(4)

    for i, (col, f) in enumerate(zip(fc_cols, st.session_state.factories)):
        with col:
            cap = f.get("capacity_units") or 1
            stock = f.get("current_stock_units") or 0
            pct = min(100.0, stock / cap * 100)
            bclr = "#1d9e75" if pct >= 70 else ("#ba7517" if pct >= 30 else "#e24b4a")
            sc = status_color(f["status"])
            sb = status_bg(f["status"])
            st_txt = status_text(f["status"])

            with st.container(key=f"factory_card_{i}"):
                st.markdown(
                    f'<div class="factory-card-inner">'
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">'
                    f'<div>'
                    f'<div class="fc-name">{f["name"]}</div>'
                    f'</div>'
                    f'<span class="badge" style="background:{sb};color:{sc}">{st_txt}</span>'
                    f'</div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:4px">'
                    f'<div class="fc-metric-box">'
                    f'<div class="fc-metric-label">온도</div>'
                    f'<div style="text-align:left;padding-left:0;margin-left:0px">'
                    f'<div class="fc-metric-val">{f["temp"]:.1f}<span class="fc-metric-unit">°C</span></div>'
                    f'<div class="fc-target-text" style="margin-top:4px;text-align:left;margin-left:0px">목표 {round(f["target"], 1)}°C</div>'
                    f'</div>'
                    f'</div>'
                    f'<div class="fc-metric-box">'
                    f'<div class="fc-metric-label">습도</div>'
                    f'<div class="fc-metric-val">{f["hum"]}<span class="fc-metric-unit">%</span></div>'
                    f'</div>'
                    f'</div>'
                    f'<div class="fc-bar-wrap">'
                    f'<div style="height:4px;border-radius:2px;background:{bclr};width:{pct:.1f}%"></div>'
                    f'</div>'
                    f'<div class="fc-footer"><span>재고 <b>{f["current_stock_units"]}/{f["capacity_units"]}개</b></span></div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                bc1_, bc2_ = st.columns(2)

                with bc1_:
                    if st.button("상세 보기", key=f"fcbtn_{i}", use_container_width=True, type="secondary"):
                        show_factory_detail(st.session_state.factories[i])

                with bc2_:
                    is_stopped = st.session_state.factories[i].get("manual_stop", False)

                    button_text = "정지 복구" if is_stopped else "비상 정지"
                    button_key = f"recoverbtn_{i}" if is_stopped else f"stopbtn_{i}"


                    if st.button(button_text, key=button_key, width="stretch"):
                        fac = st.session_state.factories[i]
                        node_id = fac.get("node_id", "nodeA")
                        factory_id = fac["factory_id"]
                        if is_stopped:
                            st.session_state.factories[i]["manual_stop"] = False
                            st.session_state.factories[i]["status"] = "ok"
                            st.session_state.factories[i]["power"] = 75
                            log_action(f"{f['name']} 비상 정지 복구")
                            if send_command:
                                send_command(node_id, factory_id, "SET_TARGET_TEMP", {"value": -19.0, "reason": "비상 정지 복구"})
                        else:
                            st.session_state.factories[i]["manual_stop"] = True
                            st.session_state.factories[i]["status"] = "err"
                            st.session_state.factories[i]["power"] = 0
                            log_action(f"{f['name']} 비상 정지")
                            if send_command:
                                send_command(node_id, factory_id, "STOP", {"reason": "비상 정지"})

                        st.session_state.emergency = any(
                            fac.get("manual_stop", False)
                            for fac in st.session_state.factories
                        )

                        st.rerun()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)