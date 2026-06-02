"""
TiVA-MoS Explorer — split-pane layout: Chatbot (left) | Dashboard (right).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO)

from src.config import DATASETS, ISO3_NAMES, ISIC_NAMES
from src.data_loader import load_all, schema_report
from src.query_engine import (
    filter_data, get_time_series, get_top_n, get_growth,
    get_mode_shares, compare_countries, get_sector_ranking,
    get_years, get_available_values,
)
from src.charts import (
    plot_time_series, plot_stacked_bar, plot_top_n_bar,
    plot_heatmap, plot_indexed_change, plot_mode_shares_donut,
    plot_sector_ranking,
)
from src.chatbot import respond, ChatResponse
from src.ui_components import (
    inject_css, render_header, render_inline_filters,
    render_metric_row, render_filter_chips,
    render_table_with_download, render_footnote,
    no_data_message, info_box, section_title,
)

# ── page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TiVA-MoS Explorer",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

# ── data ───────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading TiVA-MoS data...")
def _load():
    return load_all()

datasets = _load()
if not datasets:
    st.error("No data files found. Check data directory configuration.")
    st.stop()

# ── header (full width) ────────────────────────────────────────────────────
render_header()

# ── split layout ───────────────────────────────────────────────────────────
col_chat, col_dash = st.columns([10, 12], gap="large")


# ══════════════════════════════════════════════════════════════════════════
# LEFT COLUMN — Chatbot
# ══════════════════════════════════════════════════════════════════════════
with col_chat:
    from src.config import active_llm_provider as _llm_prov
    _provider, _, _model = _llm_prov()

    _llm_status = (
        f"&#9989; &nbsp;<b>{_provider.upper()}</b> ({_model}) active &mdash; "
        "full natural-language explanations enabled."
        if _provider else
        "&#9881; &nbsp;Running in <b>analytical mode</b> &mdash; "
        "data queries and charts work without an LLM key."
    )

    st.markdown(f"""
    <div class="chat-intro">
      <h3>&#128172; Ask anything about TiVA-MoS data</h3>
      <p>
        Explore 82 economies, 4 modes of supply, 5 indicators.<br>
        Ask in plain English &mdash; I query the data and explain the results.<br>
        <span style="font-size:0.8rem;color:#6B7280;">{_llm_status}</span>
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Sample question buttons
    sample_qs = [
        "What kind of information can I get?",
        "Top 10 economies by Mode 3 in 2023",
        "Mode shares for France in 2023",
        "Sectors with highest Mode 3 ratio",
        "Compare Germany, France and Italy",
        "What does Mode 3 mean?",
    ]
    for i, q in enumerate(sample_qs):
        if st.button(q, key=f"sq_{i}", use_container_width=True):
            st.session_state["chat_input"] = q

    st.markdown("<br>", unsafe_allow_html=True)

    # Chat history state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Input form
    st.markdown("""
    <div class="chat-input-label">
      <span>&#128172; Type your question &mdash; press Enter or click Send</span>
    </div>
    """, unsafe_allow_html=True)

    prefill = st.session_state.pop("chat_input", "")
    with st.form("chat_form", clear_on_submit=True, border=False):
        col_q, col_btn = st.columns([10, 2])
        with col_q:
            user_input = st.text_input(
                "", value=prefill,
                placeholder="Ask about TiVA-MoS data...",
                label_visibility="collapsed",
                key="chat_text",
            )
        with col_btn:
            submitted = st.form_submit_button("Send", use_container_width=True)

    if submitted and user_input and user_input.strip():
        with st.spinner("Analysing..."):
            response: ChatResponse = respond(user_input.strip())
        st.session_state.chat_history.insert(0, {
            "id":       len(st.session_state.chat_history),
            "question": user_input.strip(),
            "answer":   response.answer,
            "df":       response.result_df,
            "plan":     response.plan,
        })
        st.rerun()

    # Chat history — newest at top
    if not st.session_state.chat_history:
        st.markdown("""
        <div style="text-align:center;padding:2.5rem 1rem;color:#9CA3AF;">
          <div style="font-size:2rem;margin-bottom:0.6rem;">&#128172;</div>
          <div style="font-weight:600;font-size:0.9rem;color:#6B7280;">
            Start the conversation above
          </div>
          <div style="font-size:0.8rem;margin-top:0.25rem;">
            Click a question or type your own
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for turn in st.session_state.chat_history:
            with st.chat_message("user"):
                st.markdown(f"**{turn['question']}**")
            with st.chat_message("assistant", avatar="assistant"):
                st.markdown(turn["answer"])

                df_turn = turn.get("df")
                plan    = turn.get("plan")

                if df_turn is not None and not df_turn.empty and plan:
                    _ds  = plan.dataset_name or "dmst_va_in_frgn_dmnd"
                    _fig = None
                    if plan.intent == "top_n" and "country_name" in df_turn.columns:
                        _fig = plot_top_n_bar(df_turn, dataset_name=_ds)
                    elif plan.intent == "sector" and "sector_name" in df_turn.columns:
                        _fig = plot_sector_ranking(df_turn)
                    elif plan.intent == "mode_shares" and "mode_name" in df_turn.columns:
                        _fig = plot_stacked_bar(df_turn, x="mode_name", y="value",
                                                color="mode_name", dataset_name=_ds,
                                                title="Mode breakdown")
                    elif plan.intent in ("time_series", "growth") and "year" in df_turn.columns:
                        _color = ("mode_name" if "mode_name" in df_turn.columns
                                  else "country_name" if "country_name" in df_turn.columns
                                  else None)
                        _fig = plot_time_series(df_turn, color=_color, dataset_name=_ds)
                    elif plan.intent == "compare" and "year" in df_turn.columns:
                        _fig = plot_time_series(df_turn, color="country_name",
                                                dataset_name=_ds, title="Country comparison")
                    if _fig:
                        st.plotly_chart(_fig, use_container_width=True,
                                        key=f"chart_{turn['id']}")

                if df_turn is not None and not df_turn.empty:
                    with st.expander("View data table"):
                        render_table_with_download(
                            df_turn, key=f"cdl_{turn['id']}",
                            filename="chat_result.csv",
                        )

        if st.button("Clear conversation", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# RIGHT COLUMN — Filters + Dashboard tabs
# ══════════════════════════════════════════════════════════════════════════
with col_dash:

    # Compact inline filter bar
    st.markdown("""
    <div style="background:white;border-radius:12px;padding:1rem 1.2rem 0.5rem 1.2rem;
                box-shadow:0 2px 10px rgba(0,0,0,0.06);border:1px solid #E5E7EB;
                margin-bottom:1rem;">
      <p style="font-size:0.72rem;font-weight:700;color:#9CA3AF;text-transform:uppercase;
                letter-spacing:0.08em;margin:0 0 0.6rem 0;">Dashboard Filters</p>
    """, unsafe_allow_html=True)
    filters = render_inline_filters()
    st.markdown("</div>", unsafe_allow_html=True)

    ds   = filters["dataset_name"]
    yr   = filters["year"]
    geo  = filters["geo"]
    mode = filters["mode_name"]
    isic = filters["isic_code"]

    active_filters: dict = {"dataset_name": ds}
    if geo:  active_filters["geo"]       = geo
    if mode: active_filters["mode_name"] = mode
    if isic: active_filters["isic_code"] = isic
    if yr:   active_filters["year"]      = yr

    # Dashboard tabs (no Chatbot tab here)
    tabs = st.tabs([
        "Executive Overview",
        "Indicator Explorer",
        "Country Comparison",
        "Mode of Supply",
        "Bilateral / Sector",
        "Data Dictionary",
    ])

    # ── Tab 1: Executive Overview ─────────────────────────────────────────
    with tabs[0]:
        section_title("Executive Overview")
        render_filter_chips(filters)

        df_filtered = filter_data(active_filters)
        if df_filtered.empty:
            no_data_message()
        else:
            latest_val  = df_filtered["value"].mean()
            n_economies = df_filtered["geo"].nunique()
            growth_data = get_growth(ds, geo, mode_name=mode, isic_code=isic) if geo else None

            chg_txt, chg_positive = "", None
            if growth_data and growth_data["pct_change"] is not None:
                v = growth_data["pct_change"]
                chg_txt      = f"{v:+.1f}% ({growth_data['first_year']} to {growth_data['last_year']})"
                chg_positive = v >= 0

            render_metric_row([
                ("Dataset",           DATASETS[ds]["label"],
                                       DATASETS[ds]["unit"]),
                ("Economy",            ISO3_NAMES.get(geo, geo) if geo
                                       else f"{n_economies} economies", ""),
                ("Latest value (avg)", f"{latest_val:.2f}", DATASETS[ds]["unit"]),
                ("Change",             chg_txt or "N/A", ""),
            ])

            st.markdown("")
            section_title("Trend by Mode")
            ts_df = filter_data({k: v for k, v in
                                  {"dataset_name": ds, "geo": geo, "isic_code": isic}.items()
                                  if v})
            if not ts_df.empty and "mode_name" in ts_df.columns:
                st.plotly_chart(plot_time_series(ts_df, color="mode_name", dataset_name=ds),
                                use_container_width=True)
            else:
                no_data_message("trend")

            section_title("Mode Shares")
            shares_df = get_mode_shares(ds, geo=geo, year=yr, isic_code=isic)
            if not shares_df.empty:
                st.plotly_chart(
                    plot_stacked_bar(shares_df, x="mode_name", y="value",
                                     color="mode_name", dataset_name=ds,
                                     title="Mode breakdown"),
                    use_container_width=True)
            else:
                no_data_message("mode shares")

            section_title("Top 10 Economies")
            top_df = get_top_n(ds, year=yr, mode_name=mode, isic_code=isic, n=10)
            if not top_df.empty:
                st.plotly_chart(plot_top_n_bar(top_df, dataset_name=ds),
                                use_container_width=True)
            else:
                no_data_message("top economies")

        render_footnote(ds)

    # ── Tab 2: Indicator Explorer ─────────────────────────────────────────
    with tabs[1]:
        section_title("Indicator Explorer")
        render_filter_chips(filters)

        df_exp = filter_data(active_filters)
        if df_exp.empty:
            no_data_message()
        else:
            fig = plot_time_series(
                df_exp,
                color="mode_name" if "mode_name" in df_exp.columns else None,
                dataset_name=ds,
            )
            st.plotly_chart(fig, use_container_width=True)

            if geo:
                growth = get_growth(ds, geo, mode_name=mode, isic_code=isic)
                if growth["first_value"] is not None:
                    info_box(
                        f"<b>{ISO3_NAMES.get(geo, geo)}</b> &nbsp;|&nbsp; "
                        f"{growth['first_year']}: {growth['first_value']:.2f} "
                        f"&rarr; {growth['last_year']}: {growth['last_value']:.2f} "
                        f"&nbsp; ({growth['pct_change']:+.1f}%)"
                    )

            section_title("Filtered Data")
            display_cols = [c for c in
                ["dataset_name", "year", "geo", "country_name",
                 "mode_name", "sector_name", "isic_code", "value"]
                if c in df_exp.columns]
            render_table_with_download(df_exp[display_cols],
                                       key="explorer", filename=f"{ds}_{yr}.csv")

        render_footnote(ds)

    # ── Tab 3: Country Comparison ─────────────────────────────────────────
    with tabs[2]:
        section_title("Country Comparison")

        country_opts  = {ISO3_NAMES.get(g, g): g for g in get_available_values("geo")}
        selected_names = st.multiselect(
            "Select economies to compare (2-6 recommended)",
            options=sorted(country_opts.keys()),
            default=[k for k in ["France", "Germany", "United States", "Japan"]
                     if k in country_opts][:4],
            key="cmp_geos",
        )
        selected_geos = [country_opts[n] for n in selected_names if n in country_opts]

        if len(selected_geos) < 2:
            info_box("Select at least 2 economies to compare.")
        else:
            cmp_df = compare_countries(ds, geos=selected_geos,
                                       mode_name=mode, isic_code=isic, year=yr)
            if cmp_df.empty:
                no_data_message()
            else:
                st.plotly_chart(
                    plot_time_series(cmp_df, color="country_name",
                                     title="Time series comparison", dataset_name=ds),
                    use_container_width=True)

                base_yr = min(get_years(ds)) if get_years(ds) else None
                st.plotly_chart(
                    plot_indexed_change(cmp_df, color="country_name",
                                        base_year=base_yr, dataset_name=ds),
                    use_container_width=True)

                yr_df = cmp_df[cmp_df["year"] == yr] if yr else cmp_df
                if not yr_df.empty:
                    section_title(f"Ranking ({yr})")
                    st.plotly_chart(
                        plot_top_n_bar(
                            yr_df.groupby("country_name", as_index=False)["value"].mean(),
                            dataset_name=ds),
                        use_container_width=True)

                render_table_with_download(cmp_df, key="cmp", filename="comparison.csv")

        render_footnote(ds)

    # ── Tab 4: Mode of Supply ─────────────────────────────────────────────
    with tabs[3]:
        section_title("Mode of Supply Breakdown")
        render_filter_chips(filters)

        mode_df = filter_data({k: v for k, v in
                                {"dataset_name": ds, "geo": geo, "isic_code": isic}.items()
                                if v})

        if mode_df.empty or "mode_name" not in mode_df.columns:
            no_data_message("mode breakdown")
        else:
            st.plotly_chart(
                plot_stacked_bar(mode_df, x="year", y="value", color="mode_name",
                                 dataset_name=ds, title="Absolute values by mode"),
                use_container_width=True)

            st.plotly_chart(
                plot_stacked_bar(mode_df, x="year", y="value", color="mode_name",
                                 dataset_name=ds, pct=True, title="100% share by mode"),
                use_container_width=True)

            if yr:
                yr_mode_df = mode_df[mode_df["year"] == yr]
                if not yr_mode_df.empty:
                    st.markdown(f"**Mode shares &mdash; {yr}**")
                    st.plotly_chart(
                        plot_mode_shares_donut(yr_mode_df, dataset_name=ds),
                        use_container_width=True)
                    shares = get_mode_shares(ds, geo=geo, year=yr, isic_code=isic)
                    if not shares.empty:
                        render_table_with_download(shares, key="mode_tbl",
                                                   filename="mode_shares.csv")

        info_box(
            "<b>Note:</b> Mode 3 and cross-border supply (Mode 1/4) should not be "
            "summed directly &mdash; they can overlap in some TiVA-MoS indicators."
        )
        render_footnote(ds)

    # ── Tab 5: Bilateral / Sector ─────────────────────────────────────────
    with tabs[4]:
        section_title("Bilateral Flow Explorer & Sector Analysis")

        sec_yr = st.selectbox(
            "Year (sector)", sorted(get_years("mos3_to_xborder_ratio"), reverse=True),
            key="sec_yr")
        sec_geo_label = st.selectbox(
            "Economy (sector)",
            ["World average"] + sorted(ISO3_NAMES.get(g, g) for g in get_available_values("geo")),
            key="sec_geo")
        geo_filter_sec = None
        if sec_geo_label != "World average":
            geo_filter_sec = {v: k for k, v in ISO3_NAMES.items()}.get(sec_geo_label, sec_geo_label)

        sec_df = get_sector_ranking(year=sec_yr, geo=geo_filter_sec, n=19)
        if not sec_df.empty:
            st.plotly_chart(
                plot_sector_ranking(sec_df,
                    title=f"Mode 3 / Cross-border ratio &mdash; {sec_geo_label} ({sec_yr})"),
                use_container_width=True)
        else:
            no_data_message("sector ranking")

        section_title("Heatmap: Economy x Mode")
        hm_df = filter_data({"dataset_name": ds, **({"year": yr} if yr else {})})
        if not hm_df.empty and "mode_name" in hm_df.columns:
            st.plotly_chart(
                plot_heatmap(hm_df, title=f"{DATASETS[ds]['label']} &mdash; {yr}",
                             dataset_name=ds),
                use_container_width=True)
        else:
            no_data_message("heatmap")

        section_title("Full Sector Table")
        sec_full = filter_data({
            "dataset_name": "mos3_to_xborder_ratio",
            "year": sec_yr,
            **({"geo": geo_filter_sec} if geo_filter_sec else {}),
        })
        if not sec_full.empty:
            render_table_with_download(sec_full, key="sec_full", filename="sectors.csv")

        render_footnote("mos3_to_xborder_ratio")

    # ── Tab 6: Data Dictionary ────────────────────────────────────────────
    with tabs[5]:
        section_title("Data Dictionary & Method Notes")

        st.markdown("#### Indicators")
        for name, meta in DATASETS.items():
            with st.expander(f"**{meta['label']}** &mdash; `{name}`"):
                st.markdown(f"**Unit:** {meta['unit']}")
                st.markdown(f"**Description:** {meta['description']}")
                st.markdown(f"**Mode columns:** {', '.join(meta['mode_cols'])}")
                st.markdown(f"**Sector dimension:** {'Yes' if meta['has_isic'] else 'No'}")

        st.markdown("#### Modes of Supply (GATS)")
        from src.prompts import METADATA_DEFINITIONS
        for term, defn in METADATA_DEFINITIONS.items():
            with st.expander(f"**{term}**"):
                st.markdown(defn)

        st.markdown("#### ISIC Sectors")
        st.dataframe(
            pd.DataFrame([{"Code": k, "Sector": v} for k, v in ISIC_NAMES.items()]),
            use_container_width=True, hide_index=True,
        )

        st.markdown("#### Schema Report")
        with st.expander("Show detected schema"):
            st.markdown(schema_report())

        render_footnote()
