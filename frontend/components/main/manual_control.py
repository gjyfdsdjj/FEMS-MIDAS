# tab4 수동제어

import streamlit as st
import requests
import os

_API = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


def _send_to_all(action, payload=None):
    for fac in st.session_state.get("factories", []):
        try:
            requests.post(f"{_API}/api/v1/control/manual", json={
                "node_id": fac.get("node_id", "nodeA"),
                "factory_id": fac["factory_id"],
                "action": action,
                "allow_high_duty": False,
                "max_duty": 100.0,
                "requested_by": "manual",
                **(payload or {}),
            }, timeout=5)
        except Exception:
            pass


def manual_control(log_action):
    st.markdown('<div class="card-title">수동 제어</div>', unsafe_allow_html=True)

    manual_stop_color = (
        "#24a05c"
        if st.session_state.get("manual_stop_active", False)
        else "#e24b4a"
    )

    st.markdown(f"""
    <style>
    .st-key-btn_manual_stop_active button {{
        background: {manual_stop_color} !important;
        border-color: {manual_stop_color} !important;
        color: white !important;
        border: none !important;
    }}

    .st-key-btn_force_cool_active button,
    .st-key-btn_defrost_heat_active button {{
        background: #f8f8f6 !important;
        color: #444441 !important;
        border: 1px solid #e0e3ea !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#faeeda;border:0.5px solid #fac775;border-radius:6px;
        padding:7px 10px;font-size:14px;color:#854f0b;margin-bottom:10px">
      수동 제어 시 자동 스케줄이 일시 중지됩니다.
    </div>
    """, unsafe_allow_html=True)

    control_defaults = {
        "manual_stop_active": False,
        "force_cool_active": False,
        "defrost_heat_active": False,
    }

    for key, value in control_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    controls = [
        ("manual_stop_active", "비상 정지"),
        ("force_cool_active", "강제 냉각"),
        ("defrost_heat_active", "제상 히팅"),
    ]

    cb1, cb2, cb3 = st.columns(3)

    for col, (state_key, label) in zip([cb1, cb2, cb3], controls):
        is_active = st.session_state[state_key]
        button_text = "복구" if is_active else label

        with col:
            if st.button(button_text, key=f"btn_{state_key}", width="stretch"):
                if is_active:
                    st.session_state[state_key] = False

                    if state_key == "manual_stop_active":
                        st.session_state.emergency = False

                        for fac in st.session_state.factories:
                            fac["manual_stop"] = False
                            fac["status"] = "ok"
                            fac["power"] = 75

                        log_action("전체 공장 비상 정지 복구")
                    else:
                        log_action(f"{label} 복구")
                else:
                    for reset_key, _ in controls:
                        st.session_state[reset_key] = False

                    st.session_state[state_key] = True

                    if state_key == "manual_stop_active":
                        st.session_state.emergency = True
                        for fac in st.session_state.factories:
                            fac["manual_stop"] = True
                            fac["status"] = "err"
                            fac["power"] = 0
                        _send_to_all("STOP", {"reason": "전체 비상 정지"})
                        log_action("전체 공장 비상 정지")
                    elif state_key == "force_cool_active":
                        _send_to_all("SET_TARGET_TEMP", {"value": -19.0, "reason": "강제 냉각"})
                        log_action(label)
                    elif state_key == "defrost_heat_active":
                        _send_to_all("START", {"value": 30.0, "direction": "reverse", "seconds": 300.0, "reason": "제상 히팅"})
                        log_action(label)

                st.rerun()

    if st.session_state.emergency:
        st.markdown('<div class="emg-banner">비상 정지 활성화</div>', unsafe_allow_html=True)

    st.markdown(
        '<div style="margin-top:10px;font-size:17px;font-weight:500;color:#1a1a2e;margin-bottom:4px">제어 내역</div>',
        unsafe_allow_html=True
    )

    log_html = "".join(
        f'<div><span class="log-time">{line.split("  ")[0]}</span>'
        f'{("  ".join(line.split("  ")[1:]) if "  " in line else line)}</div>'
        for line in st.session_state.ctrl_log
    )

    st.markdown(f'<div class="log-box">{log_html}</div>', unsafe_allow_html=True)