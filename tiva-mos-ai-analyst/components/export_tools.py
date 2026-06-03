# -*- coding: utf-8 -*-
"""Export Center tab — download data, answers, policy notes."""
from __future__ import annotations

from datetime import date
import streamlit as st
import pandas as pd

from services.data_loader import load_combined, DATASETS
from services.export_service import export_csv, export_answer_text, export_policy_note
from services.ai_response import AnalystResponse


def render_export_center(filters: dict) -> None:
    st.markdown("""
    <div class="dict-header">
      <div class="dict-title">Export Center</div>
      <div class="dict-sub">
        Download data, analytical results, and policy notes.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Data export ─────────────────────────────────────────────────────
    st.markdown("### Export Filtered Data")
    ds = filters["dataset_name"]
    yr = filters["year"]
    geo = filters["geo"]
    mode = filters["mode_name"]
    isic = filters["isic_code"]

    df = load_combined()
    if not df.empty:
        active = {"dataset_name": ds}
        if geo:  active["geo"] = geo
        if mode: active["mode_name"] = mode
        if isic: active["isic_code"] = isic
        if yr:   active["year"] = yr

        for col, val in active.items():
            if col not in df.columns or val is None:
                continue
            if isinstance(val, list):
                df = df[df[col].isin(val)]
            else:
                df = df[df[col] == val]

        st.write(f"**{len(df):,} rows** matching current filters")
        st.dataframe(df.head(100), height=280, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download as CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=f"tiva_mos_{ds}_{yr or 'all'}.csv",
                mime="text/csv", key="exp_csv",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "Download as Excel (CSV format)",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=f"tiva_mos_{ds}_{yr or 'all'}.csv",
                mime="text/csv", key="exp_xls",
                use_container_width=True,
            )

    # ── AI results export ───────────────────────────────────────────────
    st.markdown("### Export from AI Analyst")
    history = st.session_state.get("analyst_history", [])

    if not history:
        st.info("No AI Analyst results yet. Ask a question in the AI Analyst tab first.")
        return

    st.write(f"{len(history)} question(s) in history.")
    selected_idx = st.selectbox(
        "Select a result to export",
        options=list(range(len(history))),
        format_func=lambda i: f"Q{i+1}: {history[i]['question'][:60]}...",
        key="exp_select",
    )

    if selected_idx is not None:
        resp: AnalystResponse = history[selected_idx]["response"]

        c1, c2, c3 = st.columns(3)
        with c1:
            if resp.df is not None and not resp.df.empty:
                st.download_button(
                    "Export Result CSV",
                    data=export_csv(resp.df),
                    file_name="analyst_result.csv",
                    mime="text/csv",
                    key="exp_res_csv",
                    use_container_width=True,
                )
        with c2:
            st.download_button(
                "Export Answer (TXT)",
                data=export_answer_text(resp).encode("utf-8"),
                file_name=f"analyst_answer_{date.today()}.txt",
                mime="text/plain",
                key="exp_answer",
                use_container_width=True,
            )
        with c3:
            st.download_button(
                "One-Page Policy Note",
                data=export_policy_note(resp).encode("utf-8"),
                file_name=f"policy_note_{date.today()}.txt",
                mime="text/plain",
                key="exp_note",
                use_container_width=True,
            )

        # Preview the policy note
        with st.expander("Preview policy note"):
            st.text(export_policy_note(resp))
