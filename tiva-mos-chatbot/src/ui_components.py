"""
Reusable Streamlit UI building blocks.
No business logic here — only layout helpers.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import DATASETS, ISO3_NAMES, ISIC_NAMES, active_llm_provider
from src.query_engine import get_years, get_available_values, get_datasets


# ── theme ─────────────────────────────────────────────────────────────────────

def inject_css() -> None:
    css_path = Path(__file__).parent.parent / "assets" / "theme.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ── header ────────────────────────────────────────────────────────────────────

def render_header() -> None:
    provider, _, model = active_llm_provider()
    llm_badge = (
        f'<span style="font-size:0.78rem;opacity:0.8;">LLM: {provider} / {model}</span>'
        if provider else
        '<span style="font-size:0.78rem;opacity:0.8;">LLM: offline — analytical mode</span>'
    )
    st.markdown(f"""
    <div class="tiva-header">
        <h1>TiVA-MoS Explorer</h1>
        <p>Trade in Value-Added indicators for services by Mode of Supply &nbsp;|&nbsp;
           OECD 2026 preliminary &nbsp;|&nbsp; {llm_badge}</p>
    </div>
    """, unsafe_allow_html=True)


# ── sidebar filters ───────────────────────────────────────────────────────────

def render_sidebar() -> dict:
    """Render sidebar filters; return selected values dict."""
    with st.sidebar:
        st.markdown('<p class="sidebar-title">Filters</p>', unsafe_allow_html=True)

        dataset_opts = {DATASETS[k]["label"]: k for k in get_datasets()}
        ds_label = st.selectbox("Dataset", list(dataset_opts.keys()), key="sb_dataset")
        dataset_name = dataset_opts[ds_label]

        years = get_years(dataset_name)
        if not years:
            years = [2000, 2023]
        year = st.selectbox("Year", sorted(years, reverse=True), key="sb_year")

        geo_opts = {ISO3_NAMES.get(g, g): g for g in get_available_values("geo")}
        geo_label = st.selectbox(
            "Economy", ["(All)"] + sorted(geo_opts.keys()), key="sb_geo"
        )
        geo = geo_opts.get(geo_label) if geo_label != "(All)" else None

        mode_opts = get_available_values("mode_name", dataset_name)
        mode_name = st.selectbox(
            "Mode", ["(All)"] + mode_opts, key="sb_mode"
        )
        mode_name = mode_name if mode_name != "(All)" else None

        isic_opts = {ISIC_NAMES.get(i, i): i for i in get_available_values("isic_code") if i}
        if isic_opts:
            isic_label = st.selectbox(
                "Sector", ["(All)"] + sorted(isic_opts.keys()), key="sb_isic"
            )
            isic_code = isic_opts.get(isic_label) if isic_label != "(All)" else None
        else:
            isic_code = None

        if st.button("Reset filters", key="sb_reset"):
            for key in ["sb_dataset", "sb_year", "sb_geo", "sb_mode", "sb_isic"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    return {
        "dataset_name": dataset_name,
        "year": year,
        "geo": geo,
        "mode_name": mode_name,
        "isic_code": isic_code,
    }


# ── metric cards ──────────────────────────────────────────────────────────────

def metric_card(label: str, value: str, sub: str = "", positive: bool | None = None) -> str:
    cls = ""
    if positive is True:
        cls = "metric-positive"
    elif positive is False:
        cls = "metric-negative"
    return f"""
    <div class="metric-card {cls}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {"<div class='metric-sub'>" + sub + "</div>" if sub else ""}
    </div>
    """


def render_metric_row(metrics: list[tuple[str, str, str]]) -> None:
    """metrics: list of (label, value, sub_text)"""
    cols = st.columns(len(metrics))
    for col, (label, value, sub) in zip(cols, metrics):
        col.markdown(metric_card(label, value, sub), unsafe_allow_html=True)


# ── filter chips ──────────────────────────────────────────────────────────────

def render_filter_chips(filters: dict) -> None:
    chips = []
    label_map = {
        "dataset_name": lambda v: DATASETS.get(v, {}).get("label", v),
        "geo": lambda v: ISO3_NAMES.get(v, v),
        "mode_name": lambda v: v,
        "isic_code": lambda v: ISIC_NAMES.get(v, v),
        "year": lambda v: str(v),
    }
    for k, v in filters.items():
        if v and k in label_map:
            chips.append(f'<span class="filter-chip">{label_map[k](v)}</span>')
    if chips:
        st.markdown(" ".join(chips), unsafe_allow_html=True)


# ── data table with download ──────────────────────────────────────────────────

def render_table_with_download(
    df: pd.DataFrame,
    key: str = "dl",
    filename: str = "tiva_mos_data.csv",
    height: int = 350,
) -> None:
    if df is None or df.empty:
        st.info("No data to display.")
        return
    st.dataframe(df, height=height)
    st.download_button(
        "Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=f"dl_{key}",
    )


# ── footnote ──────────────────────────────────────────────────────────────────

def render_footnote(dataset_name: str | None = None) -> None:
    base = (
        "Source: OECD TiVA-MoS 2026 preliminary release. "
        "Values reflect services trade decomposed by GATS mode of supply. "
        "Mode 3 (commercial presence) and cross-border trade should not be summed "
        "to avoid double-counting."
    )
    extra = ""
    if dataset_name:
        desc = DATASETS.get(dataset_name, {}).get("description", "")
        if desc:
            extra = f" | {desc}"
    st.markdown(f'<p class="footnote">{base}{extra}</p>', unsafe_allow_html=True)


# ── empty state ───────────────────────────────────────────────────────────────

def no_data_message(context: str = "") -> None:
    msg = "No data found for the selected filters."
    if context:
        msg += f" ({context})"
    st.markdown(f'<div class="warn-box">{msg}</div>', unsafe_allow_html=True)


# ── info box ──────────────────────────────────────────────────────────────────

def info_box(text: str) -> None:
    st.markdown(f'<div class="info-box">{text}</div>', unsafe_allow_html=True)
