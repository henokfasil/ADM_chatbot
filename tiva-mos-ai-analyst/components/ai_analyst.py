# -*- coding: utf-8 -*-
"""
AI Analyst tab — the main analytical experience.
3-column layout: Control | Output Canvas | Context & Provenance
"""
from __future__ import annotations

import streamlit as st

from services.ai_response import analyse, AnalystResponse
from services.export_service import export_csv, export_answer_text, export_policy_note
from services.data_loader import DATASETS


# ── suggested prompts grouped by task ────────────────────────────────────
PROMPT_GROUPS = {
    "&#128218; Explain": [
        "What is Mode 3?",
        "What does Domestic VA in Foreign Demand mean?",
        "Explain GVC participation in simple terms.",
    ],
    "&#127942; Rank": [
        "Top 10 economies by Mode 3 in 2023",
        "Which economies have the highest services value-added exposure?",
        "Rank economies by GVC participation in 2023",
    ],
    "&#9878; Compare": [
        "Compare France, Germany and Italy in 2023",
        "Compare USA, China and Japan for Mode 3",
        "Compare OECD and emerging economies",
    ],
    "&#128200; Trend": [
        "Show France from 2000 to 2023",
        "Which economies changed most since 2000?",
        "Show Mode 3 trend for Germany",
    ],
    "&#128203; Policy": [
        "What does this result imply for services trade?",
        "Which economies rely most on commercial presence?",
        "Give a policy interpretation of Mode 3 dominance",
    ],
}


def _render_evidence_box(evidence: dict) -> None:
    if not evidence:
        return
    rows = "".join(
        f'<tr><td class="ev-key">{k}</td><td class="ev-val">{v}</td></tr>'
        for k, v in evidence.items()
        if v and str(v) not in ("N/A", "0", "")
    )
    st.markdown(f"""
    <div class="evidence-box">
      <div class="ev-title">&#128203; Evidence &amp; Provenance</div>
      <table class="ev-table">{rows}</table>
    </div>
    """, unsafe_allow_html=True)


def _render_policy_box(policy: str, caveat: str) -> None:
    if not policy and not caveat:
        return
    content = ""
    if policy:
        content += f'<div class="pol-section"><b>Policy interpretation</b><br>{policy}</div>'
    if caveat:
        content += f'<div class="pol-caveat"><b>&#9888; Caveat</b><br>{caveat}</div>'
    st.markdown(f'<div class="policy-box">{content}</div>',
                unsafe_allow_html=True)


def _render_follow_up(questions: list[str], history_key: str) -> None:
    if not questions:
        return
    st.markdown('<div class="followup-label">Suggested follow-up questions:</div>',
                unsafe_allow_html=True)
    for i, q in enumerate(questions[:3]):
        if st.button(q, key=f"fu_{history_key}_{i}", use_container_width=False):
            st.session_state["pending_question"] = q
            st.rerun()


def _render_export_buttons(resp: AnalystResponse, turn_id: int) -> None:
    st.markdown('<div class="export-row">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if resp.df is not None and not resp.df.empty:
            st.download_button(
                "Export CSV", data=export_csv(resp.df),
                file_name="tiva_result.csv", mime="text/csv",
                key=f"dl_csv_{turn_id}", use_container_width=True,
            )
    with c2:
        st.download_button(
            "Export Answer", data=export_answer_text(resp).encode("utf-8"),
            file_name="analyst_answer.txt", mime="text/plain",
            key=f"dl_txt_{turn_id}", use_container_width=True,
        )
    with c3:
        st.download_button(
            "Policy Note", data=export_policy_note(resp).encode("utf-8"),
            file_name="policy_note.txt", mime="text/plain",
            key=f"dl_note_{turn_id}", use_container_width=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


def render_ai_analyst_tab() -> None:
    # ── session state ──────────────────────────────────────────────────────
    if "analyst_history" not in st.session_state:
        st.session_state.analyst_history = []

    # ── 3-column layout (created first so thinking card goes into col_out) ──
    col_ctrl, col_out, col_ctx = st.columns([3, 6, 3], gap="medium")

    # ── execute any pending question — thinking card renders in col_out ────
    if "pending_question" in st.session_state:
        pending = st.session_state.pop("pending_question")

        with col_out:
            thinking = st.empty()
            thinking.markdown(f"""
            <div class="ai-thinking-card">
              <div class="ai-thinking-star">&#10022;</div>
              <div class="ai-thinking-text">
                <div class="ai-thinking-title">AI Analyst is working&hellip;</div>
                <div class="ai-thinking-steps">
                  &#10003; Parsing: <i>{pending[:70]}</i><br>
                  &#8250; Querying TiVA-MoS data &nbsp;
                  &#8250; Calling Qwen 72B &nbsp;
                  &#8250; Building chart &nbsp;
                  &#8250; Generating policy note
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        _resp = analyse(pending)

        with col_out:
            thinking.empty()

        st.session_state.analyst_history.insert(0, {
            "id":       len(st.session_state.analyst_history),
            "question": pending,
            "response": _resp,
        })
        st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # LEFT — Control Panel
    # ══════════════════════════════════════════════════════════════════════
    with col_ctrl:
        st.markdown("""
        <div class="panel-header">&#128161; Ask the AI Analyst</div>
        """, unsafe_allow_html=True)

        prefill = st.session_state.pop("ai_question", "")
        with st.form("analyst_form", clear_on_submit=True, border=False):
            question = st.text_input(
                "", value=prefill,
                placeholder="Ask a question about TiVA-MoS indicators...",
                label_visibility="collapsed",
                key="analyst_q",
            )
            submitted = st.form_submit_button(
                "Analyse", use_container_width=True)

        if submitted and question and question.strip():
            st.session_state["pending_question"] = question.strip()
            st.rerun()

        # Grouped suggested prompts
        for group_label, prompts in PROMPT_GROUPS.items():
            st.markdown(f"""
            <div class="prompt-group-label">{group_label}</div>
            """, unsafe_allow_html=True)
            for prompt in prompts:
                if st.button(prompt, key=f"pg_{hash(prompt)}",
                             use_container_width=True):
                    st.session_state["pending_question"] = prompt
                    st.rerun()

        if st.session_state.analyst_history:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Clear history", key="clear_analyst",
                         use_container_width=True):
                st.session_state.analyst_history = []
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # CENTER — Output Canvas
    # ══════════════════════════════════════════════════════════════════════
    with col_out:
        if not st.session_state.analyst_history:
            st.markdown("""
            <div class="empty-canvas">
              <div class="empty-icon">&#128202;</div>
              <div class="empty-title">Your analytical workspace</div>
              <div class="empty-sub">
                Ask a question on the left, or click a suggested prompt.<br>
                The AI will answer, generate a chart, interpret the result,<br>
                and show you the data provenance.
              </div>
              <div class="empty-examples">
                <b>Example questions:</b><br>
                Compare France, Germany and Italy for Mode 3 in 2023<br>
                Top 10 economies by Domestic VA in Foreign Demand<br>
                Show Mode 3 trend for Japan from 2000 to 2023<br>
                Which sectors have the highest Mode 3 ratio?
              </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for turn in st.session_state.analyst_history:
                resp: AnalystResponse = turn["response"]
                turn_id = turn["id"]

                # Question bubble
                st.markdown(f"""
                <div class="q-bubble">
                  <span class="q-icon">&#128100;</span>
                  <span class="q-text">{resp.question}</span>
                </div>
                """, unsafe_allow_html=True)

                # Ambiguity clarification
                if resp.is_ambiguous:
                    st.markdown(f"""
                    <div class="ambiguity-box">
                      <b>&#10067; Clarification needed</b><br>
                      {resp.ambiguity_message}
                    </div>
                    """, unsafe_allow_html=True)
                    continue

                # Answer
                if resp.answer:
                    st.markdown(f"""
                    <div class="answer-box">
                      <div class="answer-label">&#129302; AI Analyst</div>
                      <div class="answer-text">{resp.answer}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Chart
                if resp.fig:
                    st.plotly_chart(resp.fig, use_container_width=True,
                                    key=f"fig_{turn_id}")

                # Data table (collapsed)
                if resp.df is not None and not resp.df.empty:
                    with st.expander("View data table"):
                        st.dataframe(resp.df, height=250, use_container_width=True)

                # Policy interpretation
                _render_policy_box(resp.policy_interpretation, resp.caveat)

                # Export buttons
                _render_export_buttons(resp, turn_id)

                # Follow-up suggestions
                _render_follow_up(resp.follow_up, str(turn_id))

                st.markdown("<hr class='turn-divider'>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # RIGHT — Context & Provenance
    # ══════════════════════════════════════════════════════════════════════
    with col_ctx:
        st.markdown("""
        <div class="panel-header">&#128203; Context &amp; Provenance</div>
        """, unsafe_allow_html=True)

        if st.session_state.analyst_history:
            latest = st.session_state.analyst_history[0]
            resp = latest["response"]
            _render_evidence_box(resp.evidence)

            # Dataset definition — use separate st calls to avoid HTML injection issues
            if resp.plan and resp.plan.dataset_name:
                from services.query_interpreter import get_indicator_meta
                meta = get_indicator_meta(resp.plan.dataset_name)
                if meta:
                    short_def = meta.get("short_definition", "").strip()
                    policy_ctx = meta.get("policy_context", "").strip()
                    st.markdown('<div class="def-box">', unsafe_allow_html=True)
                    st.markdown(
                        '<div class="def-title">Indicator definition</div>',
                        unsafe_allow_html=True)
                    if short_def:
                        st.markdown(
                            f'<div class="def-text">{short_def}</div>',
                            unsafe_allow_html=True)
                    if policy_ctx:
                        st.markdown(
                            f'<div class="def-policy">{policy_ctx}</div>',
                            unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="ctx-empty">
              Evidence, filters, and indicator definitions will appear here
              after your first query.
            </div>
            """, unsafe_allow_html=True)
