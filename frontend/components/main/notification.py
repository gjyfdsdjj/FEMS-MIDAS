import streamlit as st
import base64
import os
import requests
from pathlib import Path

_API = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


def _ack_all():
    try:
        requests.post(f"{_API}/api/v1/alerts/ack-all", timeout=10)
    except Exception:
        pass
    st.cache_data.clear()


def notification_popover(dummy_data, unacked):
    alert_count = len(unacked)

    noti_icon_path = Path(__file__).resolve().parents[2] / "assets" / "notification.png"

    with open(noti_icon_path, "rb") as img_file:
        noti_icon_base64 = base64.b64encode(img_file.read()).decode()

    st.markdown(f"""
    <style>
    .st-key-notification_popover_wrap div[data-testid="stPopover"] {{
        position: relative;
        transform: translate(110px, -5px);
    }}

    .st-key-notification_popover_wrap div[data-testid="stPopover"] button {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 8px !important;
        min-height: unset !important;
    }}

    .st-key-notification_popover_wrap div[data-testid="stPopover"] button:hover {{
        background: rgba(0, 0, 0, 0.07) !important;
        border-radius: 50% !important;
    }}

    .st-key-notification_popover_wrap div[data-testid="stPopover"] button svg,
    .st-key-notification_popover_wrap div[data-testid="stPopover"] button span:last-child {{
        display: none !important;
    }}

    .st-key-notification_popover_wrap div[data-testid="stPopover"] button::after {{
        content: "";
        display: block;
        width: 26px;
        height: 26px;
        background: url("data:image/png;base64,{noti_icon_base64}") center / contain no-repeat;
    }}

    .st-key-notification_popover_wrap div[data-testid="stPopover"]::before {{
        content: "{alert_count}";
        position: absolute;
        top: 2px;
        right: 2px;
        z-index: 999;
        background: #e24b4a;
        color: white;
        font-size: 10px;
        font-weight: 700;
        border-radius: 50%;
        min-width: 18px;
        height: 18px;
        display: {"flex" if alert_count > 0 else "none"};
        align-items: center;
        justify-content: center;
        border: 2px solid white;
        pointer-events: none;
    }}
    </style>
    """, unsafe_allow_html=True)

    with st.container(key="notification_popover_wrap"):
        with st.popover(""):
            st.html('<div style="font-size:20px;font-weight:700;color:#1a1a2e;margin-bottom:12px">경보 알림</div>')

            all_alerts = dummy_data.get("alerts", [])
            unacked_ids = [a["alert_id"] for a in all_alerts if not a.get("is_acknowledged")]

            if unacked_ids:
                if st.button("전체 확인", key="ack_all_btn", use_container_width=True):
                    _ack_all()
                    st.rerun()

            if not all_alerts:
                st.html('<div style="font-size:12px;color:#b4b2a9;padding:8px 0">활성 경보 없음</div>')
                return

            for a in sorted(all_alerts, key=lambda x: x["is_acknowledged"]):
                level = a["level"]
                is_acked = a["is_acknowledged"]

                if is_acked:
                    card_class = "acked"
                    dot_color = "#2f6fdd"
                    badge_class = "acked"
                    badge_text = "✓ 확인됨"
                else:
                    badge_class = "unacked"
                    badge_text = "● 미확인"

                    if level == "ERROR":
                        card_class = "unacked-err"
                        dot_color = "#e24b4a"
                    elif level == "WARNING":
                        card_class = "unacked-warn"
                        dot_color = "#f59f00"
                    else:
                        card_class = "unacked-info"
                        dot_color = "#2f6fdd"

                message = a["message"]

                if ". " in message:
                    first_msg, second_msg = message.split(". ", 1)
                    first_msg += "."
                else:
                    first_msg = message
                    second_msg = ""

                st.html(f"""
                <div class="alert-card {card_class}">
                    <div>
                        <div class="alert-title">
                            <span class="alert-dot" style="background:{dot_color}"></span>
                            <div>
                                <div>{first_msg}</div>
                                {f'<div class="alert-sub-message">{second_msg}</div>' if second_msg else ''}
                            </div>
                        </div>
                        <div class="alert-meta">
                            공장 F-{a['factory_id']:02d} &nbsp; | &nbsp;
                            {a['created_at'][11:16] if a['created_at'] else '--:--'} &nbsp; | &nbsp;
                            {a['level']}
                        </div>
                    </div>
                    <div class="alert-badge {badge_class}">
                        {badge_text}
                    </div>
                </div>
                """)