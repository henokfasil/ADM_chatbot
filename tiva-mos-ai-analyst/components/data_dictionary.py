# -*- coding: utf-8 -*-
"""Searchable data dictionary component."""
from __future__ import annotations

from pathlib import Path
import yaml
import streamlit as st
import pandas as pd

from services.data_loader import DATASETS, ISIC_NAMES

_META_DIR = Path(__file__).parent.parent / "metadata"


def _load_indicators() -> dict:
    try:
        with open(_META_DIR / "indicators.yml", encoding="utf-8") as f:
            return yaml.safe_load(f).get("indicators", {})
    except Exception:
        return {}


def render_data_dictionary() -> None:
    ind_meta = _load_indicators()

    st.markdown("""
    <div class="dict-header">
      <div class="dict-title">Data Dictionary</div>
      <div class="dict-sub">
        Definitions, units, caveats, and policy context for all TiVA-MoS indicators.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Search
    search = st.text_input("Search indicators, definitions, or modes...",
                           placeholder="e.g. Mode 3, commercial presence, GVC...",
                           key="dict_search")

    st.markdown("### Indicators")
    for ds_name, meta in ind_meta.items():
        label = DATASETS.get(ds_name, {}).get("label", ds_name)
        code = meta.get("code", "")
        if search and search.lower() not in (
            label.lower() + " " +
            meta.get("short_definition", "").lower() + " " +
            " ".join(meta.get("synonyms", [])).lower()
        ):
            continue
        with st.expander(f"**{label}** &nbsp; `{code}`"):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown(f"**Short definition:** {meta.get('short_definition', 'N/A')}")
                st.markdown(f"**Long definition:** {meta.get('long_definition', 'N/A')}")
                st.markdown(f"**Policy context:** {meta.get('policy_context', 'N/A')}")
            with c2:
                st.markdown(f"**Code:** `{code}`")
                st.markdown(f"**Unit:** {DATASETS.get(ds_name, {}).get('unit', 'N/A')}")
                yrs = meta.get("valid_years", [])
                yr_range = f"{min(yrs)} - {max(yrs)}" if yrs else "N/A"
                st.markdown(f"**Years:** {yr_range}")
                st.markdown(f"**Has sectors:** {'Yes' if meta.get('has_sectors') else 'No'}")
                st.markdown(f"**Caveats:** {meta.get('caveats', 'N/A')}")

            st.markdown("**Synonyms accepted:**")
            syns = meta.get("synonyms", [])
            if syns:
                st.markdown(" &nbsp;·&nbsp; ".join(f"`{s}`" for s in syns))

            st.markdown("**Example questions:**")
            ex_qs = [
                f"Top 10 economies by {label} in 2023",
                f"Show trend for France — {label}",
                f"What is {code}?",
                f"Compare Germany and France for {label}",
            ]
            for q in ex_qs:
                if st.button(q, key=f"dd_q_{hash(q)}", use_container_width=False):
                    st.session_state["ai_question"] = q
                    st.info(f"Question loaded: '{q}' — go to the AI Analyst tab.")

    st.markdown("### Modes of Supply (GATS)")
    modes_info = {
        "Mode 1/4": (
            "Cross-border supply + Presence of natural persons. "
            "Services delivered remotely (e.g. online consulting, call centres) "
            "or by individuals temporarily in the importing country."
        ),
        "Mode 2": (
            "Consumption abroad. The consumer travels to the supplier's country "
            "(e.g. tourism, medical treatment abroad, studying abroad)."
        ),
        "Mode 3": (
            "Commercial presence. A foreign firm establishes a subsidiary, branch, "
            "or affiliate in another country (e.g. foreign bank branches, retail chains, "
            "insurance subsidiaries). Typically the largest mode for OECD economies."
        ),
    }
    for mode, desc in modes_info.items():
        with st.expander(f"**{mode}**"):
            st.markdown(desc)

    st.markdown("### ISIC Sectors")
    st.markdown("The Mode 3 / Cross-border Ratio is available for these 19 ISIC Rev. 4 sectors:")
    st.dataframe(
        pd.DataFrame([{"Code": k, "Sector": v} for k, v in ISIC_NAMES.items()]),
        use_container_width=True, hide_index=True, height=400,
    )
