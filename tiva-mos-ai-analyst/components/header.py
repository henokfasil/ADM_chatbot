# -*- coding: utf-8 -*-
"""Header component — institutional OECD-style banner."""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from services.policy_interpreter import get_provider_name


def inject_css() -> None:
    css_path = Path(__file__).parent.parent / "assets" / "theme.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_header() -> None:
    provider = get_provider_name()
    if provider:
        ai_badge = (
            f'<span class="hdr-badge ai-active">'
            f'&#9679; AI: {provider.upper()}</span>'
        )
    else:
        ai_badge = '<span class="hdr-badge ai-offline">&#9679; AI: Offline</span>'

    st.markdown(f"""
    <div class="tiva-header">
      <div class="hdr-inner">
        <div class="hdr-left">
          <div class="hdr-title">TiVA-MoS AI Analyst</div>
          <div class="hdr-subtitle">
            Trade in Value-Added &nbsp;&middot;&nbsp; Modes of Supply
            &nbsp;&middot;&nbsp; OECD 2026 Preliminary Release
          </div>
        </div>
        <div class="hdr-badges">
          <span class="hdr-badge">82 Economies</span>
          <span class="hdr-badge">2000 &ndash; 2023</span>
          <span class="hdr-badge">5 Indicators</span>
          <span class="hdr-badge">AI-assisted analytics</span>
          {ai_badge}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
