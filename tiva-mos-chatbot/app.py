# -*- coding: utf-8 -*-
"""
TiVA-MoS Explorer
Layout: Chatbot assistant (25%) | Dashboard (75%)
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
    filter_data, get_top_n, get_growth,
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
    inject_css, render_header,
    render_metric_row, render_filter_chips,
    render_table_with_download, render_footnote,
    no_data_message, info_box, section_title,
)

# ── page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TiVA-MoS Chat & Vizboard",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

# ── load data ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading data...")
def _load():
    return load_all()

datasets = _load()
if not datasets:
    st.error("No data files found. Check data directory configuration.")
    st.stop()

# ── header ─────────────────────────────────────────────────────────────────
render_header()

# ── split: 25% chatbot | 75% dashboard ────────────────────────────────────
col_chat, col_dash = st.columns([5, 15], gap="large")


# ══════════════════════════════════════════════════════════════════════════
# LEFT — Chatbot assistant (25%)
# ══════════════════════════════════════════════════════════════════════════
with col_chat:
    from src.config import active_llm_provider as _llm_prov
    _provider, _, _model = _llm_prov()

    # Panel header
    _llm_dot = "&#128994;" if _provider else "&#128308;"   # green / red dot
    _llm_tip = _provider.upper() if _provider else "Offline"
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:0.5rem;
                padding:0.6rem 0 0.8rem 0;
                border-bottom:2px solid #003087;margin-bottom:0.9rem;">
      <span style="font-size:1rem;font-weight:700;color:#0D1B4B;">
        &#128172; Chatbot
      </span>
      <span style="font-size:0.7rem;background:#EFF6FF;color:#1D4ED8;
                   padding:0.15rem 0.55rem;border-radius:10px;font-weight:600;">
        {_llm_dot} {_llm_tip}
      </span>
    </div>
    """, unsafe_allow_html=True)

    # ── input form ─────────────────────────────────────────────────────────
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    prefill = st.session_state.pop("chat_input", "")
    with st.form("chat_form", clear_on_submit=True, border=False):
        user_input = st.text_input(
            "", value=prefill,
            placeholder="Ask about anything...",
            label_visibility="collapsed",
            key="chat_text",
        )
        submitted = st.form_submit_button("Send", use_container_width=True)

    if submitted and user_input and user_input.strip():
        with st.spinner("Thinking..."):
            response: ChatResponse = respond(user_input.strip())
        st.session_state.chat_history.insert(0, {
            "id":       len(st.session_state.chat_history),
            "question": user_input.strip(),
            "answer":   response.answer,
            "df":       response.result_df,
            "plan":     response.plan,
        })
        st.rerun()

    # ── chat history (BEFORE sample questions) ─────────────────────────────
    if not st.session_state.chat_history:
        st.markdown("""
        <div style="text-align:center;padding:1.5rem 0.5rem;color:#9CA3AF;">
          <div style="font-size:1.6rem;margin-bottom:0.4rem;">&#128172;</div>
          <div style="font-size:0.8rem;color:#6B7280;font-weight:600;">
            Ask a question above
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for turn in st.session_state.chat_history:
            # User bubble
            st.markdown(f"""
            <div style="background:#EFF6FF;border-radius:10px 10px 2px 10px;
                        padding:0.5rem 0.7rem;margin:0.3rem 0;
                        font-size:0.8rem;font-weight:600;color:#1D4ED8;">
              {turn['question']}
            </div>
            """, unsafe_allow_html=True)

            # Assistant answer
            st.markdown(f"""
            <div style="background:white;border:1px solid #E5E7EB;
                        border-radius:2px 10px 10px 10px;
                        padding:0.6rem 0.7rem;margin:0.2rem 0 0.6rem 0;
                        font-size:0.82rem;color:#374151;
                        box-shadow:0 1px 4px rgba(0,0,0,0.05);">
              {turn['answer']}
            </div>
            """, unsafe_allow_html=True)

            # Chart (compact, fits narrow column)
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
                                            dataset_name=_ds, title="Comparison")
                if _fig:
                    _fig.update_layout(height=260, margin=dict(t=30, b=20, l=10, r=10))
                    st.plotly_chart(_fig, use_container_width=True,
                                    key=f"chart_{turn['id']}")

            if df_turn is not None and not df_turn.empty:
                with st.expander("Data table"):
                    render_table_with_download(df_turn, key=f"cdl_{turn['id']}",
                                               filename="result.csv", height=200)

        if st.button("Clear chat", key="clear_chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    # ── sample questions (AFTER chat history) ──────────────────────────────
    st.markdown("<hr style='margin:0.8rem 0;border-color:#E5E7EB;'>",
                unsafe_allow_html=True)
    st.markdown("""
    <p style="font-size:0.7rem;font-weight:700;color:#9CA3AF;
              text-transform:uppercase;letter-spacing:0.07em;
              margin:0 0 0.5rem 0;">Try asking:</p>
    """, unsafe_allow_html=True)
    sample_qs = [
        "What kind of info can I get?",
        "Top 10 Mode 3 economies 2023",
        "Mode shares for France",
        "Highest Mode 3 sectors",
        "Compare DEU, FRA, ITA",
        "What is Mode 3?",
    ]
    sc1, sc2 = st.columns(2)
    for i, q in enumerate(sample_qs):
        col = sc1 if i % 2 == 0 else sc2
        if col.button(q, key=f"sq_{i}", use_container_width=True):
            st.session_state["chat_input"] = q
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# RIGHT — TiVA-MoS Dashboard (75%)
# ══════════════════════════════════════════════════════════════════════════
with col_dash:

    # Dashboard: tabs main area (left 80%) + vertical filters (right 20%)
    dash_main, dash_filt = st.columns([4, 1], gap="medium")

    # ── vertical filter panel (right) ───────────────────────────────────────
    with dash_filt:
        st.markdown("""
        <div style="background:#F8FAFC;border:1px solid #E5E7EB;border-radius:12px;
                    padding:1rem 0.9rem;">
          <p style="font-size:0.68rem;font-weight:700;color:#9CA3AF;
                    text-transform:uppercase;letter-spacing:0.08em;margin:0 0 0.8rem 0;">
            Filters
          </p>
        """, unsafe_allow_html=True)

        ds_opts = {DATASETS[k]["label"]: k for k in DATASETS}
        ds_label = st.selectbox("Dataset", list(ds_opts.keys()), key="ds_sel")
        ds = ds_opts[ds_label]

        years = get_years(ds) or [2000, 2023]
        yr = st.selectbox("Year", sorted(years, reverse=True), key="yr_sel")

        geo_opts = {ISO3_NAMES.get(g, g): g for g in get_available_values("geo")}
        geo_label = st.selectbox("Economy", ["All"] + sorted(geo_opts.keys()),
                                 key="geo_sel")
        geo = geo_opts.get(geo_label) if geo_label != "All" else None

        mode_opts = get_available_values("mode_name", ds)
        mode_raw = st.selectbox("Mode", ["All"] + mode_opts, key="mode_sel")
        mode = mode_raw if mode_raw != "All" else None

        isic_opts = {ISIC_NAMES.get(i, i): i for i in get_available_values("isic_code") if i}
        if isic_opts:
            isic_label = st.selectbox("Sector", ["All"] + sorted(isic_opts.keys()),
                                      key="isic_sel")
            isic = isic_opts.get(isic_label) if isic_label != "All" else None
        else:
            isic = None

        st.markdown("</div>", unsafe_allow_html=True)

        if st.button("Reset", key="dash_reset", use_container_width=True):
            for k in ["ds_sel", "yr_sel", "mode_sel", "geo_sel", "isic_sel"]:
                st.session_state.pop(k, None)
            st.rerun()

    filters = {"dataset_name": ds, "year": yr, "geo": geo,
               "mode_name": mode, "isic_code": isic}
    active_filters: dict = {"dataset_name": ds}
    if geo:  active_filters["geo"]       = geo
    if mode: active_filters["mode_name"] = mode
    if isic: active_filters["isic_code"] = isic
    if yr:   active_filters["year"]      = yr

    # ── dashboard tabs (left main area) ────────────────────────────────────
    with dash_main:
      st.markdown("""
      <div style="border-bottom:2px solid #003087;padding-bottom:0.4rem;
                  margin-bottom:0.8rem;">
        <span style="font-size:1rem;font-weight:700;color:#0D1B4B;">
          TiVA-MoS Dashboard
        </span>
      </div>
      """, unsafe_allow_html=True)

      tabs = st.tabs([
        "Exec. Summary",
        "Indicator Explorer",
        "Country Comparison",
        "Mode of Supply",
        "Bilateral / Sector",
        "Data Dictionary",
    ])

    # -- Exec. Summary -------------------------------------------------------
    with tabs[0]:
        render_filter_chips(filters)
        df_filtered = filter_data(active_filters)
        if df_filtered.empty:
            no_data_message()
        else:
            latest_val  = df_filtered["value"].mean()
            n_economies = df_filtered["geo"].nunique()
            growth_data = get_growth(ds, geo, mode_name=mode, isic_code=isic) if geo else None
            chg_txt, chg_pos = "", None
            if growth_data and growth_data["pct_change"] is not None:
                v = growth_data["pct_change"]
                chg_txt = f"{v:+.1f}% ({growth_data['first_year']} to {growth_data['last_year']})"
                chg_pos = v >= 0
            render_metric_row([
                ("Dataset",           DATASETS[ds]["label"], DATASETS[ds]["unit"]),
                ("Economy",            ISO3_NAMES.get(geo, geo) if geo else f"{n_economies} economies", ""),
                ("Latest value (avg)", f"{latest_val:.2f}", DATASETS[ds]["unit"]),
                ("Change",             chg_txt or "N/A", ""),
            ])
            c1, c2 = st.columns(2)
            with c1:
                section_title("Trend by Mode")
                ts_df = filter_data({k: v for k, v in
                    {"dataset_name": ds, "geo": geo, "isic_code": isic}.items() if v})
                if not ts_df.empty and "mode_name" in ts_df.columns:
                    st.plotly_chart(plot_time_series(ts_df, color="mode_name",
                                    dataset_name=ds), use_container_width=True)
                else:
                    no_data_message("trend")
            with c2:
                section_title("Mode Shares")
                shares_df = get_mode_shares(ds, geo=geo, year=yr, isic_code=isic)
                if not shares_df.empty:
                    st.plotly_chart(plot_stacked_bar(shares_df, x="mode_name",
                                    y="value", color="mode_name", dataset_name=ds,
                                    title="Mode breakdown"), use_container_width=True)
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

    # -- Indicator Explorer --------------------------------------------------
    with tabs[1]:
        render_filter_chips(filters)
        df_exp = filter_data(active_filters)
        if df_exp.empty:
            no_data_message()
        else:
            st.plotly_chart(plot_time_series(
                df_exp,
                color="mode_name" if "mode_name" in df_exp.columns else None,
                dataset_name=ds), use_container_width=True)
            if geo:
                growth = get_growth(ds, geo, mode_name=mode, isic_code=isic)
                if growth["first_value"] is not None:
                    info_box(
                        f"<b>{ISO3_NAMES.get(geo, geo)}</b> &nbsp;|&nbsp; "
                        f"{growth['first_year']}: {growth['first_value']:.2f} "
                        f"&rarr; {growth['last_year']}: {growth['last_value']:.2f} "
                        f"({growth['pct_change']:+.1f}%)"
                    )
            section_title("Filtered Data")
            display_cols = [c for c in ["dataset_name", "year", "geo", "country_name",
                            "mode_name", "sector_name", "isic_code", "value"]
                            if c in df_exp.columns]
            render_table_with_download(df_exp[display_cols], key="explorer",
                                       filename=f"{ds}_{yr}.csv")
        render_footnote(ds)

    # -- Country Comparison --------------------------------------------------
    with tabs[2]:
        country_opts = {ISO3_NAMES.get(g, g): g for g in get_available_values("geo")}
        selected_names = st.multiselect(
            "Select economies (2-6)",
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
                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(plot_time_series(cmp_df, color="country_name",
                                    title="Time series", dataset_name=ds),
                                    use_container_width=True)
                with c2:
                    base_yr = min(get_years(ds)) if get_years(ds) else None
                    st.plotly_chart(plot_indexed_change(cmp_df, color="country_name",
                                    base_year=base_yr, dataset_name=ds),
                                    use_container_width=True)
                yr_df = cmp_df[cmp_df["year"] == yr] if yr else cmp_df
                if not yr_df.empty:
                    section_title(f"Ranking ({yr})")
                    st.plotly_chart(plot_top_n_bar(
                        yr_df.groupby("country_name", as_index=False)["value"].mean(),
                        dataset_name=ds), use_container_width=True)
                render_table_with_download(cmp_df, key="cmp", filename="comparison.csv")
        render_footnote(ds)

    # -- Mode of Supply ------------------------------------------------------
    with tabs[3]:
        render_filter_chips(filters)
        mode_df = filter_data({k: v for k, v in
            {"dataset_name": ds, "geo": geo, "isic_code": isic}.items() if v})
        if mode_df.empty or "mode_name" not in mode_df.columns:
            no_data_message("mode breakdown")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(plot_stacked_bar(mode_df, x="year", y="value",
                                color="mode_name", dataset_name=ds,
                                title="Absolute values"), use_container_width=True)
            with c2:
                st.plotly_chart(plot_stacked_bar(mode_df, x="year", y="value",
                                color="mode_name", dataset_name=ds,
                                pct=True, title="100% share"), use_container_width=True)
            if yr:
                yr_mode_df = mode_df[mode_df["year"] == yr]
                if not yr_mode_df.empty:
                    c3, c4 = st.columns(2)
                    with c3:
                        st.plotly_chart(plot_mode_shares_donut(yr_mode_df,
                                        dataset_name=ds), use_container_width=True)
                    with c4:
                        shares = get_mode_shares(ds, geo=geo, year=yr, isic_code=isic)
                        if not shares.empty:
                            render_table_with_download(shares, key="mode_tbl",
                                                       filename="mode_shares.csv")
        info_box("Mode 3 and Mode 1/4 should not be summed directly in some indicators.")
        render_footnote(ds)

    # -- Bilateral / Sector --------------------------------------------------
    with tabs[4]:
        c1, c2 = st.columns(2)
        with c1:
            section_title("Mode 3 / Cross-border Ratio by Sector")
            sec_yr = st.selectbox("Year",
                sorted(get_years("mos3_to_xborder_ratio"), reverse=True), key="sec_yr")
            sec_geo_label = st.selectbox("Economy",
                ["World average"] + sorted(ISO3_NAMES.get(g, g)
                for g in get_available_values("geo")), key="sec_geo")
            geo_filter_sec = None
            if sec_geo_label != "World average":
                geo_filter_sec = {v: k for k, v in ISO3_NAMES.items()}.get(
                    sec_geo_label, sec_geo_label)
            sec_df = get_sector_ranking(year=sec_yr, geo=geo_filter_sec, n=19)
            if not sec_df.empty:
                st.plotly_chart(plot_sector_ranking(sec_df,
                    title=f"Mode 3 ratio - {sec_geo_label} ({sec_yr})"),
                    use_container_width=True)
            else:
                no_data_message("sector ranking")
        with c2:
            section_title("Heatmap: Economy x Mode")
            hm_df = filter_data({"dataset_name": ds, **({"year": yr} if yr else {})})
            if not hm_df.empty and "mode_name" in hm_df.columns:
                st.plotly_chart(plot_heatmap(hm_df,
                    title=f"{DATASETS[ds]['label']} - {yr}", dataset_name=ds),
                    use_container_width=True)
            else:
                no_data_message("heatmap")
        section_title("Full Sector Table")
        sec_full = filter_data({"dataset_name": "mos3_to_xborder_ratio",
                                "year": sec_yr,
                                **({"geo": geo_filter_sec} if geo_filter_sec else {})})
        if not sec_full.empty:
            render_table_with_download(sec_full, key="sec_full", filename="sectors.csv")
        render_footnote("mos3_to_xborder_ratio")

    # -- Data Dictionary -----------------------------------------------------
    with tabs[5]:
        section_title("Indicators")
        for name, meta in DATASETS.items():
            with st.expander(f"**{meta['label']}** - `{name}`"):
                st.markdown(f"**Unit:** {meta['unit']}")
                st.markdown(f"**Description:** {meta['description']}")
                st.markdown(f"**Modes:** {', '.join(meta['mode_cols'])}")
        section_title("Modes of Supply (GATS)")
        from src.prompts import METADATA_DEFINITIONS
        for term, defn in METADATA_DEFINITIONS.items():
            with st.expander(f"**{term}**"):
                st.markdown(defn)
        section_title("ISIC Sectors")
        st.dataframe(
            pd.DataFrame([{"Code": k, "Sector": v} for k, v in ISIC_NAMES.items()]),
            use_container_width=True, hide_index=True)
        with st.expander("Schema report"):
            st.markdown(schema_report())
        render_footnote()
