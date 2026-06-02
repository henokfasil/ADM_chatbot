# -*- coding: utf-8 -*-
"""
Reusable Streamlit UI building blocks - premium design.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import DATASETS, ISO3_NAMES, ISIC_NAMES, active_llm_provider
from src.query_engine import get_years, get_available_values, get_datasets

# ── icons map for datasets ────────────────────────────────────────────────────
_DS_ICONS = {
    "dmst_va_in_frgn_dmnd":  "[DVA]",
    "frgn_va_in_dmst_dmnd":  "[FVA]",
    "gvc_participation":     "[GVC]",
    "va_in_mnf_export":      "[MNF]",
    "mos3_to_xborder_ratio": "[M3]",
}

# ── CSS ───────────────────────────────────────────────────────────────────────
def inject_css() -> None:
    css_path = Path(__file__).parent.parent / "assets" / "theme.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ── header ────────────────────────────────────────────────────────────────────
def render_header() -> None:
    provider, _, model = active_llm_provider()

    if provider:
        llm_html = (
            f'<span class="tiva-badge llm-active">'
            f'<span class="dot"></span>{provider.upper()} · {model}</span>'
        )
    else:
        llm_html = (
            '<span class="tiva-badge llm-offline">'
            '<span class="dot"></span>Analytical mode</span>'
        )

    st.markdown(f"""
    <div class="tiva-header">
      <div class="tiva-header-inner">
        <div>
          <h1>TiVA-MoS Explorer</h1>
          <p class="tagline">
            Trade in Value-Added &nbsp;·&nbsp; Modes of Supply &nbsp;·&nbsp;
            OECD 2026 Preliminary Release
          </p>
        </div>
        <div class="header-badges">
          <span class="tiva-badge">82 Economies</span>
          <span class="tiva-badge">2000 &ndash; 2023</span>
          <span class="tiva-badge">5 Indicators</span>
          {llm_html}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── sidebar ───────────────────────────────────────────────────────────────────
def render_inline_filters() -> dict:
    """Compact filter bar rendered inside the dashboard column."""
    dataset_opts = {
        f"{_DS_ICONS.get(k, '')}  {DATASETS[k]['label']}": k
        for k in get_datasets()
    }
    ds_label = st.selectbox("Dataset", list(dataset_opts.keys()),
                            key="if_dataset", label_visibility="visible")
    dataset_name = dataset_opts[ds_label]

    c1, c2 = st.columns(2)
    with c1:
        years = get_years(dataset_name) or [2000, 2023]
        year = st.selectbox("Year", sorted(years, reverse=True), key="if_year")
    with c2:
        geo_opts = {ISO3_NAMES.get(g, g): g for g in get_available_values("geo")}
        geo_label = st.selectbox(
            "Economy", ["All economies"] + sorted(geo_opts.keys()), key="if_geo"
        )
        geo = geo_opts.get(geo_label) if geo_label != "All economies" else None

    c3, c4 = st.columns(2)
    with c3:
        mode_opts = get_available_values("mode_name", dataset_name)
        mode_raw = st.selectbox("Mode", ["All modes"] + mode_opts, key="if_mode")
        mode_name = mode_raw if mode_raw != "All modes" else None
    with c4:
        isic_opts = {ISIC_NAMES.get(i, i): i for i in get_available_values("isic_code") if i}
        if isic_opts:
            isic_label = st.selectbox(
                "Sector", ["All sectors"] + sorted(isic_opts.keys()), key="if_isic"
            )
            isic_code = isic_opts.get(isic_label) if isic_label != "All sectors" else None
        else:
            isic_code = None

    if st.button("Reset filters", key="if_reset", use_container_width=True):
        for k in ["if_dataset", "if_year", "if_geo", "if_mode", "if_isic"]:
            st.session_state.pop(k, None)
        st.rerun()

    return {
        "dataset_name": dataset_name,
        "year": year,
        "geo": geo,
        "mode_name": mode_name,
        "isic_code": isic_code,
    }


def render_sidebar() -> dict:
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-logo">
          <span>&#9889; TiVA-MoS Explorer</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<p class="sidebar-section">Dataset</p>', unsafe_allow_html=True)
        dataset_opts = {
            f"{_DS_ICONS.get(k, '')}  {DATASETS[k]['label']}": k
            for k in get_datasets()
        }
        ds_label = st.selectbox("", list(dataset_opts.keys()),
                                key="sb_dataset", label_visibility="collapsed")
        dataset_name = dataset_opts[ds_label]

        st.markdown('<p class="sidebar-section">Filters</p>', unsafe_allow_html=True)

        years = get_years(dataset_name) or [2000, 2023]
        year = st.selectbox("Year", sorted(years, reverse=True), key="sb_year")

        geo_opts = {ISO3_NAMES.get(g, g): g for g in get_available_values("geo")}
        geo_label = st.selectbox(
            "Economy", ["All economies"] + sorted(geo_opts.keys()), key="sb_geo"
        )
        geo = geo_opts.get(geo_label) if geo_label != "All economies" else None

        mode_opts = get_available_values("mode_name", dataset_name)
        mode_name = st.selectbox("Mode", ["All modes"] + mode_opts, key="sb_mode")
        mode_name = mode_name if mode_name != "All modes" else None

        isic_opts = {ISIC_NAMES.get(i, i): i for i in get_available_values("isic_code") if i}
        if isic_opts:
            isic_label = st.selectbox(
                "Sector", ["All sectors"] + sorted(isic_opts.keys()), key="sb_isic"
            )
            isic_code = isic_opts.get(isic_label) if isic_label != "All sectors" else None
        else:
            isic_code = None

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Reset all filters", key="sb_reset"):
            for k in ["sb_dataset", "sb_year", "sb_geo", "sb_mode", "sb_isic"]:
                st.session_state.pop(k, None)
            st.rerun()

        st.markdown("""
        <div style="margin-top:2rem;padding-top:1rem;
                    border-top:1px solid rgba(255,255,255,0.1);
                    font-size:0.68rem;color:rgba(255,255,255,0.3);line-height:1.6;">
          Source: OECD TiVA-MoS<br>2026 Preliminary Release
        </div>
        """, unsafe_allow_html=True)

    return {
        "dataset_name": dataset_name,
        "year": year,
        "geo": geo,
        "mode_name": mode_name,
        "isic_code": isic_code,
    }


# ── metric cards ──────────────────────────────────────────────────────────────
_MC_ICONS = {
    "Dataset": "", "Economy": "", "Latest value (avg)": "",
    "Change": "", "Year": "", "Mode": "",
}

def metric_card(label: str, value: str, sub: str = "",
                positive: bool | None = None, icon: str = "") -> str:
    cls = "positive" if positive is True else ("negative" if positive is False else "")
    ic = icon or _MC_ICONS.get(label, "")
    trend_html = ""
    if sub and sub not in ("N/A", ""):
        if "+" in sub:
            trend_html = f'<div class="mc-trend-up">▲ {sub}</div>'
        elif "-" in sub and "%" in sub:
            trend_html = f'<div class="mc-trend-down">▼ {sub}</div>'
        else:
            trend_html = f'<div class="mc-sub">{sub}</div>'
    return f"""
    <div class="metric-card {cls}">
      {"<span class='mc-icon'>" + ic + "</span>" if ic else ""}
      <div class="mc-label">{label}</div>
      <div class="mc-value">{value}</div>
      {trend_html}
    </div>
    """

def render_metric_row(metrics: list[tuple[str, str, str]]) -> None:
    cols = st.columns(len(metrics))
    for col, (label, value, sub) in zip(cols, metrics):
        positive = None
        if sub and "+" in sub:
            positive = True
        elif sub and ("-" in sub and "%" in sub):
            positive = False
        col.markdown(metric_card(label, value, sub, positive), unsafe_allow_html=True)


# ── filter chips ──────────────────────────────────────────────────────────────
def render_filter_chips(filters: dict) -> None:
    label_map = {
        "dataset_name": lambda v: DATASETS.get(v, {}).get("label", v),
        "geo":          lambda v: ISO3_NAMES.get(v, v),
        "mode_name":    lambda v: v,
        "isic_code":    lambda v: ISIC_NAMES.get(v, v),
        "year":         lambda v: str(v),
    }
    chips = [
        f'<span class="filter-chip">{label_map[k](v)}</span>'
        for k, v in filters.items()
        if v and k in label_map
    ]
    if chips:
        st.markdown(
            f'<div class="chip-row">{"".join(chips)}</div>',
            unsafe_allow_html=True,
        )


# ── table + download ──────────────────────────────────────────────────────────
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


# ── section title ─────────────────────────────────────────────────────────────
def section_title(text: str) -> None:
    st.markdown(f'<p class="section-title">{text}</p>', unsafe_allow_html=True)


# ── chart wrapper ─────────────────────────────────────────────────────────────
def chart_card(fig, key: str = "") -> None:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True, key=key or None)
    st.markdown('</div>', unsafe_allow_html=True)


# ── footnote ──────────────────────────────────────────────────────────────────
def render_footnote(dataset_name: str | None = None) -> None:
    base = (
        "Source: OECD TiVA-MoS 2026 preliminary release. "
        "Mode 3 (commercial presence) and cross-border supply should not be summed "
        "to avoid double-counting."
    )
    extra = ""
    if dataset_name:
        desc = DATASETS.get(dataset_name, {}).get("description", "")
        if desc:
            extra = f"  ·  {desc[:120]}…"
    st.markdown(f'<p class="footnote">{base}{extra}</p>', unsafe_allow_html=True)


# ── info / warn boxes ─────────────────────────────────────────────────────────
def no_data_message(context: str = "") -> None:
    msg = "No data found for the selected filters."
    if context:
        msg += f" ({context})"
    st.markdown(f'<div class="warn-box">&#9888; {msg}</div>', unsafe_allow_html=True)

def info_box(text: str) -> None:
    st.markdown(f'<div class="info-box">&#8505; {text}</div>', unsafe_allow_html=True)
