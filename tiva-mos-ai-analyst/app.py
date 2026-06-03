# -*- coding: utf-8 -*-
"""
TiVA-MoS AI Analyst
An AI-assisted analytical workspace for OECD Trade in Value-Added indicators
by Mode of Supply.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO)

from components.header import inject_css, render_header
from components.ai_analyst import render_ai_analyst_tab
from components.dashboard_tabs import (
    render_executive_summary,
    render_indicator_explorer,
    render_compare_economies,
    render_mode_sector,
)
from components.data_dictionary import render_data_dictionary
from components.export_tools import render_export_center
from services.data_loader import (
    load_all, DATASETS, ISO3_NAMES, ISIC_NAMES,
    get_available_values, get_years, is_data_available,
)

# ── page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TiVA-MoS AI Analyst",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ── load data ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading TiVA-MoS data...")
def _load():
    return load_all()

_load()

if not is_data_available():
    st.error(
        "No data files found. Please ensure the TiVA_indicators/2026_prel_update "
        "folder is accessible. See README for setup."
    )
    st.stop()

# ── header ─────────────────────────────────────────────────────────────────
render_header()

# ── sidebar filters ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">&#9889; TiVA-MoS AI Analyst</div>
    """, unsafe_allow_html=True)

    st.markdown("**Dataset**")
    ds_opts = {DATASETS[k]["label"]: k for k in DATASETS}
    ds_label = st.selectbox("", list(ds_opts.keys()),
                            key="ds", label_visibility="collapsed")
    ds = ds_opts[ds_label]

    st.markdown("**Year**")
    years = get_years(ds) or [2000, 2023]
    yr = st.selectbox("", sorted(years, reverse=True),
                      key="yr", label_visibility="collapsed")

    st.markdown("**Economy**")
    geo_opts = {ISO3_NAMES.get(g, g): g for g in get_available_values("geo")}
    geo_label = st.selectbox("", ["All economies"] + sorted(geo_opts.keys()),
                             key="geo", label_visibility="collapsed")
    geo = geo_opts.get(geo_label) if geo_label != "All economies" else None

    st.markdown("**Mode**")
    mode_opts = get_available_values("mode_name", ds)
    mode_raw = st.selectbox("", ["All modes"] + mode_opts,
                            key="mode", label_visibility="collapsed")
    mode = mode_raw if mode_raw != "All modes" else None

    st.markdown("**Sector**")
    isic_opts = {ISIC_NAMES.get(i, i): i for i in get_available_values("isic_code") if i}
    if isic_opts:
        isic_label = st.selectbox("", ["All sectors"] + sorted(isic_opts.keys()),
                                  key="isic", label_visibility="collapsed")
        isic = isic_opts.get(isic_label) if isic_label != "All sectors" else None
    else:
        isic = None

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Reset all filters", key="reset", use_container_width=True):
        for k in ["ds", "yr", "geo", "mode", "isic"]:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown("""
    <div style="margin-top:2rem;padding-top:1rem;
                border-top:1px solid rgba(255,255,255,0.1);
                font-size:0.68rem;color:rgba(255,255,255,0.3);line-height:1.6;">
      Source: OECD TiVA-MoS<br>2026 Preliminary Release<br>
      <br>Filters apply to all dashboard tabs.<br>
      AI Analyst uses its own context.
    </div>
    """, unsafe_allow_html=True)

filters = {
    "dataset_name": ds,
    "year": yr,
    "geo": geo,
    "mode_name": mode,
    "isic_code": isic,
}

# ── main navigation tabs ───────────────────────────────────────────────────
tabs = st.tabs([
    "&#129302; AI Analyst",
    "&#128202; Executive Summary",
    "&#128270; Indicator Explorer",
    "&#127757; Compare Economies",
    "&#127760; Mode & Sector",
    "&#128218; Data Dictionary",
    "&#128229; Export Center",
])

with tabs[0]:
    render_ai_analyst_tab()

with tabs[1]:
    render_executive_summary(filters)

with tabs[2]:
    render_indicator_explorer(filters)

with tabs[3]:
    render_compare_economies(filters)

with tabs[4]:
    render_mode_sector(filters)

with tabs[5]:
    render_data_dictionary()

with tabs[6]:
    render_export_center(filters)
