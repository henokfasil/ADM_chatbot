# -*- coding: utf-8 -*-
"""Export Center tab — download data, answers, policy notes."""
from __future__ import annotations

from datetime import date
import streamlit as st
import pandas as pd

from services.data_loader import load_combined, DATASETS, ISO3_NAMES, ISIC_NAMES
from services.export_service import export_csv, export_answer_text, export_policy_note
from services.ai_response import AnalystResponse


def _apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply sidebar filters, skipping dimensions not present in the dataset."""
    ds   = filters.get("dataset_name")
    yr   = filters.get("year")
    geo  = filters.get("geo")
    mode = filters.get("mode_name")
    isic = filters.get("isic_code")

    active = {"dataset_name": ds}
    if geo:  active["geo"]       = geo
    if mode: active["mode_name"] = mode
    if isic: active["isic_code"] = isic
    if yr:   active["year"]      = yr

    for col, val in active.items():
        if col not in df.columns or val is None:
            continue
        # Skip filter if column is entirely null for this dataset slice
        # (e.g. isic_code on a dataset that has no sector dimension)
        if df[col].isna().all():
            continue
        if isinstance(val, list):
            df = df[df[col].isin(val)]
        else:
            df = df[df[col] == val]
    return df.reset_index(drop=True)


def render_export_center(filters: dict) -> None:
    ds   = filters.get("dataset_name", "")
    yr   = filters.get("year")
    geo  = filters.get("geo")
    mode = filters.get("mode_name")
    isic = filters.get("isic_code")

    # ── Role explanation ───────────────────────────────────────────────────
    st.markdown("## Export Center")
    st.markdown("""
    This tab has **two purposes**:

    **1. Export filtered data** — use the sidebar filters (dataset, year, economy, mode, sector)
    to slice the dataset, then download the result as CSV.

    **2. Export AI Analyst results** — after asking questions in the AI Analyst tab,
    come here to download your answers, charts data, and one-page policy notes.
    """)

    # Active filter summary
    filter_parts = []
    if ds:   filter_parts.append(f"Dataset: **{DATASETS.get(ds, {}).get('label', ds)}**")
    if yr:   filter_parts.append(f"Year: **{yr}**")
    if geo:  filter_parts.append(f"Economy: **{ISO3_NAMES.get(geo, geo)}**")
    if mode: filter_parts.append(f"Mode: **{mode}**")
    if isic: filter_parts.append(f"Sector: **{ISIC_NAMES.get(isic, isic)}**")

    if filter_parts:
        st.info("Active filters: " + " | ".join(filter_parts))

    st.divider()

    # ── Section 1: Filtered data export ───────────────────────────────────
    st.markdown("### 1. Export Filtered Data")

    df_all = load_combined()
    if df_all.empty:
        st.error("No data loaded.")
        return

    df = _apply_filters(df_all.copy(), filters)

    if df.empty:
        st.warning(
            "No rows match the current filter combination. "
            "This usually means the selected **Sector** filter does not apply "
            f"to the **{DATASETS.get(ds, {}).get('label', ds)}** dataset "
            "(only the Mode 3/Cross-border Ratio indicator has sector data). "
            "Try setting Sector to 'All sectors'."
        )
        # Show all data for the dataset without sector filter
        df_no_isic = _apply_filters(df_all.copy(), {**filters, "isic_code": None})
        if not df_no_isic.empty:
            st.markdown(f"Showing **{len(df_no_isic):,} rows** without sector filter:")
            df = df_no_isic
        else:
            return
    else:
        st.markdown(f"**{len(df):,} rows** matching current filters")

    # Display columns
    show_cols = [c for c in
        ["dataset_name", "year", "geo", "country_name",
         "mode_name", "sector_name", "isic_code", "value"]
        if c in df.columns]
    st.dataframe(df[show_cols].head(200), height=300, use_container_width=True)

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
        # Full dataset for this indicator (no filters)
        df_full = df_all[df_all["dataset_name"] == ds] if ds else df_all
        st.download_button(
            "Download Full Dataset (no filters)",
            data=df_full.to_csv(index=False).encode("utf-8"),
            file_name=f"tiva_mos_{ds}_full.csv",
            mime="text/csv", key="exp_full",
            use_container_width=True,
        )

    st.divider()

    # ── Section 2: AI Analyst results export ──────────────────────────────
    st.markdown("### 2. Export AI Analyst Results")

    history = st.session_state.get("analyst_history", [])

    if not history:
        st.info(
            "No AI Analyst results yet. "
            "Go to the **AI Analyst** tab, ask a question, then come back here to export."
        )
        return

    st.markdown(f"You have **{len(history)}** result(s) from the AI Analyst session.")

    selected_idx = st.selectbox(
        "Select a result to export",
        options=list(range(len(history))),
        format_func=lambda i: f"Q{i+1}: {history[i]['question'][:70]}",
        key="exp_select",
    )

    if selected_idx is not None:
        resp: AnalystResponse = history[selected_idx]["response"]

        # Show preview of the answer
        if resp.answer:
            with st.expander("Preview answer", expanded=True):
                st.markdown(resp.answer)
                if resp.policy_interpretation:
                    st.markdown(f"**Policy interpretation:** {resp.policy_interpretation}")

        c1, c2, c3 = st.columns(3)
        with c1:
            if resp.df is not None and not resp.df.empty:
                st.download_button(
                    "Result data (CSV)",
                    data=export_csv(resp.df),
                    file_name="analyst_result.csv",
                    mime="text/csv",
                    key="exp_res_csv",
                    use_container_width=True,
                )
            else:
                st.caption("No data table for this result.")
        with c2:
            st.download_button(
                "Answer (TXT)",
                data=export_answer_text(resp).encode("utf-8"),
                file_name=f"analyst_answer_{date.today()}.txt",
                mime="text/plain",
                key="exp_answer",
                use_container_width=True,
            )
        with c3:
            st.download_button(
                "Policy Note (TXT)",
                data=export_policy_note(resp).encode("utf-8"),
                file_name=f"policy_note_{date.today()}.txt",
                mime="text/plain",
                key="exp_note",
                use_container_width=True,
            )

        with st.expander("Preview policy note"):
            st.text(export_policy_note(resp))
