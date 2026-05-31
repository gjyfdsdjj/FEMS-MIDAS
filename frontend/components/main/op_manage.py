# tab3 운영 관리

import streamlit as st
from datetime import datetime, timezone, timedelta


def _fmt_deadline(deadline_at: str) -> str:
    if not deadline_at:
        return "-"
    try:
        dt = datetime.fromisoformat(deadline_at.replace("Z", "+00:00"))
        kst = dt.astimezone(timezone(timedelta(hours=9)))
        return kst.strftime("%m/%d %H:%M")
    except Exception:
        return deadline_at[:16].replace("T", " ")


def operation_manage(dummy_data, schedule_fig):
    oc1, oc2 = st.columns([1, 1.2], gap="large")

    with oc1:
        st.markdown(
            '<div class="card-title">작업 현황 및 분배 계획</div>',
            unsafe_allow_html=True
        )
        st.html(job_status_html(dummy_data))

    with oc2:
        st.markdown(
            '<div class="card-title">가동 스케줄 (24시간)</div>',
            unsafe_allow_html=True
        )
        st.plotly_chart(
            schedule_fig(dummy_data),
            use_container_width=True,
            config={"displayModeBar": False}
        )

        st.markdown("""
        <div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:-8px">
          <div style="display:flex;align-items:center;gap:5px;font-size:12px;color:#888780">
            <span style="width:12px;height:8px;background:#378add;border-radius:2px;display:inline-block"></span>가동
          </div>
          <div style="display:flex;align-items:center;gap:5px;font-size:12px;color:#888780">
            <span style="width:12px;height:8px;background:#e24b4a;border-radius:2px;display:inline-block"></span>피크요금
          </div>
          <div style="display:flex;align-items:center;gap:5px;font-size:12px;color:#888780">
            <span style="width:12px;height:8px;background:#639922;border-radius:2px;display:inline-block"></span>태양광
          </div>
          <div style="display:flex;align-items:center;gap:5px;font-size:12px;color:#888780">
            <span style="width:12px;height:8px;background:#f1efe8;border:0.5px solid #e0e3ea;border-radius:2px;display:inline-block"></span>대기
          </div>
        </div>
        """, unsafe_allow_html=True)

        schedules = dummy_data.get("schedules", [])

        if schedules:
            sch = schedules[0]
            est_d = round(sch.get("estimated_daily_saving_krw", 0) / 10000)
            est_m = round(sch.get("estimated_monthly_saving_krw", 0) / 10000)
            comp = sch.get("computed_at", "")[:16].replace("T", " ")

            st.html(f"""
            <div style="margin-top:12px;padding:10px 14px;
                background:#eaf3de;border-radius:8px;border:0.5px solid #c6dba0">
              <div style="font-size:12px;font-weight:500;color:#3b6d11;margin-bottom:6px">
                최적화 스케줄 적용 중
              </div>
              <div style="display:flex;gap:16px;flex-wrap:wrap">
                <span style="font-size:12px;color:#444441">
                  일 절감 예상 <b style="color:#3b6d11">₩{est_d}만</b>
                </span>
                <span style="font-size:12px;color:#444441">
                  월 절감 예상 <b style="color:#3b6d11">₩{est_m}만</b>
                </span>
                <span style="font-size:12px;color:#888780">계산: {comp}</span>
              </div>
            </div>
            """)


def job_status_html(dummy_data):
    jobs = dummy_data.get("jobs", [])

    if not jobs:
        return '<div style="font-size:12px;color:#b4b2a9">진행 중인 작업 없음</div>'

    strategy_map = {
        "COST_MIN": "비용 최소",
        "SAFETY_FIRST": "안전 우선",
        "BALANCED": "균형",
    }

    prod_allocs = dummy_data.get("production_allocations", [])
    ship_allocs = dummy_data.get("shipment_allocations", [])

    cards = []
    for job in reversed(jobs):
        pct = (job.get("progress_rate") or 0) * 100
        deadline = _fmt_deadline(job.get("deadline_at", ""))
        strat = strategy_map.get(job.get("strategy", "BALANCED"), job.get("strategy", "BALANCED"))
        bar_clr = "#378add" if pct < 80 else ("#ba7517" if pct < 100 else "#1d9e75")

        cards.append(f"""
    <div style="margin-bottom:12px;padding-bottom:12px;border-bottom:0.5px solid #e0e3ea">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
        <div>
          <div style="font-size:13px;font-weight:500;color:#1a1a2e">{job['job_id']}</div>
          <div style="font-size:12px;color:#888780;margin-top:2px">
            마감 {deadline} (KST) · 전략: {strat}
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-size:22px;font-weight:600;color:#1a1a2e">
            {job['produced_units']}
            <span style="font-size:12px;font-weight:400;color:#888780">/{job['target_units']}개</span>
          </div>
          <div style="font-size:12px;color:#888780">잔여 {job['remaining_units']}개</div>
        </div>
      </div>
      <div style="height:11px;background:#f1efe8;border-radius:5px;overflow:hidden;margin-bottom:4px">
        <div style="height:10px;width:{pct:.1f}%;background:{bar_clr};border-radius:5px;transition:width .3s"></div>
      </div>
      <div style="font-size:11px;color:{bar_clr};text-align:right;margin-bottom:4px">
        {pct:.0f}% 완료
      </div>
    </div>
    """)

    # 공장별 입고/출고 분배 통합 테이블
    all_fids = sorted({job.get("factory_id") for job in jobs if job.get("factory_id")})
    if not all_fids:
        all_fids = [1, 2, 3, 4]

    alloc_rows = []
    for fid in all_fids:
        pa = next((p for p in prod_allocs if p["factory_id"] == fid), None)
        sa = next((s for s in ship_allocs if s["factory_id"] == fid), None)
        inbound = pa["planned_inbound_units_until_deadline"] if pa else 0
        shipment = sa["planned_shipment_units_until_deadline"] if sa else 0
        excluded = pa and pa.get("source") == "MANUAL_STOP_EXCLUDE"
        row_bg = "#f8f5f0" if excluded else "transparent"
        alloc_rows.append(
            f'<tr style="background:{row_bg}">'
            f'<td style="padding:4px 8px;font-size:12px;color:#444441">공장 {fid}</td>'
            f'<td style="padding:4px 8px;font-size:12px;color:#378add;text-align:right">{inbound}개</td>'
            f'<td style="padding:4px 8px;font-size:12px;color:#ba7517;text-align:right">{shipment}개</td>'
            f'<td style="padding:4px 8px;font-size:11px;color:#b4b2a9">{"정지 제외" if excluded else ""}</td>'
            f'</tr>'
        )

    alloc_table = f"""
    <div style="margin-top:4px">
      <div style="font-size:13px;font-weight:500;color:#888780;margin-bottom:6px">공장별 입고 / 출고 분배</div>
      <table style="width:100%;border-collapse:collapse;border:0.5px solid #e0e3ea;border-radius:6px;overflow:hidden">
        <thead style="background:#f8f8f6">
          <tr>
            <th style="font-size:12px;color:#888780;font-weight:500;text-align:left;padding:5px 8px">공장</th>
            <th style="font-size:12px;color:#378add;font-weight:500;text-align:right;padding:5px 8px">입고 예정</th>
            <th style="font-size:12px;color:#ba7517;font-weight:500;text-align:right;padding:5px 8px">출고 예정</th>
            <th style="font-size:12px;color:#888780;font-weight:500;padding:5px 8px">비고</th>
          </tr>
        </thead>
        <tbody>{''.join(alloc_rows)}</tbody>
      </table>
    </div>
    """

    return f'<div>{"".join(cards)}{alloc_table}</div>'