# -*- coding: utf-8 -*-
"""
Dashboard tabs — Executive Summary, Indicator Explorer, Compare, Mode & Sector.
Accepts a filters dict from sidebar_filters.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from services.data_loader import (
    load_combined, DATASETS, ISO3_NAMES, ISIC_NAMES,
    get_available_values, get_years,
)
from services.chart_generator import (
    plot_top_n_bar, plot_time_series, plot_stacked_bar,
    plot_heatmap, plot_sector_bar,
)


# ── query helpers ──────────────────────────────────────────────────────────

def _filter(filters: dict[str, Any]) -> pd.DataFrame:
    df = load_combined()
    if df.empty:
        return df
    for col, val in filters.items():
        if col not in df.columns or val is None:
            continue
        if df[col].isna().all():
            continue
        if isinstance(val, list):
            df = df[df[col].isin(val)]
        else:
            df = df[df[col] == val]
    return df.reset_index(drop=True)


def _top_n(ds: str, year: int | None, mode: str | None,
           isic: str | None, n: int = 10) -> pd.DataFrame:
    f: dict[str, Any] = {"dataset_name": ds}
    if year:
        f["year"] = year
    if mode:
        f["mode_name"] = mode
    if isic:
        f["isic_code"] = isic
    df = _filter(f)
    if df.empty:
        return df
    return (df.groupby("country_name", as_index=False)["value"]
            .mean()
            .sort_values("value", ascending=False)
            .head(n)
            .reset_index(drop=True))


def _growth(ds: str, geo: str, mode: str | None, isic: str | None) -> dict | None:
    f: dict[str, Any] = {"dataset_name": ds, "geo": geo}
    if mode:
        f["mode_name"] = mode
    if isic:
        f["isic_code"] = isic
    df = _filter(f)
    if df.empty or df["value"].isna().all():
        return None
    df = df.dropna(subset=["value"])
    first = df.loc[df["year"].idxmin()]
    last = df.loc[df["year"].idxmax()]
    v0, v1 = float(first["value"]), float(last["value"])
    pct = (v1 - v0) / v0 * 100 if v0 != 0 else None
    return {
        "first_year": int(first["year"]),
        "last_year": int(last["year"]),
        "first_value": v0, "last_value": v1,
        "abs_change": v1 - v0, "pct_change": pct,
    }


def _mode_shares(ds: str, geo: str | None, year: int | None,
                 isic: str | None) -> pd.DataFrame:
    f: dict[str, Any] = {"dataset_name": ds}
    if geo:
        f["geo"] = geo
    if year:
        f["year"] = year
    if isic:
        f["isic_code"] = isic
    df = _filter(f)
    if df.empty or "mode_name" not in df.columns:
        return pd.DataFrame()
    agg = df.groupby("mode_name", as_index=False)["value"].mean()
    total = agg["value"].sum()
    agg["share_pct"] = (agg["value"] / total * 100).round(2) if total else 0.0
    return agg.sort_values("value", ascending=False).reset_index(drop=True)


# ── shared UI helpers ──────────────────────────────────────────────────────

def _section(text: str) -> None:
    st.markdown(f'<p class="section-title">{text}</p>', unsafe_allow_html=True)


def _no_data(ctx: str = "") -> None:
    st.markdown(
        f'<div class="warn-box">No data for the selected filters{f" ({ctx})" if ctx else ""}.</div>',
        unsafe_allow_html=True)


def _metric_card(label: str, value: str, sub: str = "") -> str:
    return f"""
    <div class="metric-card">
      <div class="mc-label">{label}</div>
      <div class="mc-value">{value}</div>
      {"<div class='mc-sub'>" + sub + "</div>" if sub else ""}
    </div>"""


def _chips(filters: dict) -> None:
    parts = []
    for k, v in filters.items():
        if not v:
            continue
        if k == "dataset_name":
            parts.append(DATASETS.get(v, {}).get("label", v))
        elif k == "geo":
            parts.append(ISO3_NAMES.get(v, v))
        elif k in ("mode_name", "year"):
            parts.append(str(v))
        elif k == "isic_code":
            parts.append(ISIC_NAMES.get(v, v))
    if parts:
        chips = " ".join(f'<span class="filter-chip">{p}</span>' for p in parts)
        st.markdown(chips, unsafe_allow_html=True)


# ── tab renderers ──────────────────────────────────────────────────────────

def render_executive_summary(filters: dict) -> None:
    ds = filters["dataset_name"]
    yr = filters["year"]
    geo = filters["geo"]
    mode = filters["mode_name"]
    isic = filters["isic_code"]

    _chips(filters)

    active = {"dataset_name": ds}
    if geo:   active["geo"] = geo
    if mode:  active["mode_name"] = mode
    if isic:  active["isic_code"] = isic
    if yr:    active["year"] = yr

    df = _filter(active)
    if df.empty:
        _no_data()
        return

    latest = df["value"].mean()
    n_eco = df["geo"].nunique()
    growth = _growth(ds, geo, mode, isic) if geo else None
    chg = ""
    if growth and growth["pct_change"] is not None:
        chg = f"{growth['pct_change']:+.1f}% ({growth['first_year']} to {growth['last_year']})"

    cards = "".join([
        _metric_card("Indicator", DATASETS[ds]["label"], DATASETS[ds]["unit"]),
        _metric_card("Economy", ISO3_NAMES.get(geo, geo) if geo else f"{n_eco} economies"),
        _metric_card("Latest value (avg)", f"{latest:.2f}", DATASETS[ds]["unit"]),
        _metric_card("Change", chg or "N/A"),
    ])
    st.markdown(f'<div class="metric-row">{cards}</div>', unsafe_allow_html=True)
    st.markdown("")

    c1, c2 = st.columns(2)
    with c1:
        _section("Trend by Mode")
        ts_df = _filter({k: v for k, v in {
            "dataset_name": ds, "geo": geo, "isic_code": isic}.items() if v})
        if not ts_df.empty and "mode_name" in ts_df.columns:
            st.plotly_chart(plot_time_series(ts_df, ds, color="mode_name"),
                            use_container_width=True)
        else:
            _no_data("trend")

    with c2:
        _section("Mode Shares")
        sh = _mode_shares(ds, geo, yr, isic)
        if not sh.empty:
            st.plotly_chart(plot_stacked_bar(sh, ds, x="mode_name",
                                             title="Mode breakdown"),
                            use_container_width=True)
        else:
            _no_data("mode shares")

    _section("Top 10 Economies")
    top = _top_n(ds, yr, mode, isic)
    if not top.empty:
        st.plotly_chart(plot_top_n_bar(top, ds), use_container_width=True)
    else:
        _no_data("top economies")


def render_indicator_explorer(filters: dict) -> None:
    ds = filters["dataset_name"]
    yr = filters["year"]
    geo = filters["geo"]
    mode = filters["mode_name"]
    isic = filters["isic_code"]

    _chips(filters)

    active = {"dataset_name": ds}
    if geo:   active["geo"] = geo
    if mode:  active["mode_name"] = mode
    if isic:  active["isic_code"] = isic
    if yr:    active["year"] = yr

    df = _filter(active)
    if df.empty:
        _no_data()
        return

    color = "mode_name" if "mode_name" in df.columns else None
    st.plotly_chart(plot_time_series(df, ds, color=color),
                    use_container_width=True)

    if geo:
        g = _growth(ds, geo, mode, isic)
        if g and g["first_value"] is not None:
            st.markdown(f"""
            <div class="info-box">
              <b>{ISO3_NAMES.get(geo, geo)}</b> &mdash;
              {g['first_year']}: {g['first_value']:.2f} &rarr;
              {g['last_year']}: {g['last_value']:.2f}
              ({g['pct_change']:+.1f}%)
            </div>""", unsafe_allow_html=True)

    _section("Filtered Data")
    display_cols = [c for c in
        ["dataset_name", "year", "geo", "country_name", "mode_name",
         "sector_name", "isic_code", "value"]
        if c in df.columns]
    st.dataframe(df[display_cols], height=320, use_container_width=True)
    st.download_button("Download CSV",
                       data=df.to_csv(index=False).encode("utf-8"),
                       file_name=f"{ds}_{yr}.csv", mime="text/csv",
                       key="dl_explorer")


def render_compare_economies(filters: dict) -> None:
    ds = filters["dataset_name"]
    yr = filters["year"]
    mode = filters["mode_name"]
    isic = filters["isic_code"]

    geo_opts = {ISO3_NAMES.get(g, g): g for g in get_available_values("geo")}
    selected = st.multiselect(
        "Select economies (2-6 recommended)",
        options=sorted(geo_opts.keys()),
        default=[k for k in ["France", "Germany", "United States", "Japan"]
                 if k in geo_opts][:4],
        key="cmp_geos",
    )
    geos = [geo_opts[n] for n in selected if n in geo_opts]

    if len(geos) < 2:
        st.info("Select at least 2 economies.")
        return

    active = {"dataset_name": ds, "geo": geos}
    if mode:  active["mode_name"] = mode
    if isic:  active["isic_code"] = isic
    if yr:    active["year"] = yr

    cmp_df = _filter(active)
    if cmp_df.empty:
        _no_data()
        return

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            plot_time_series(cmp_df, ds, color="country_name",
                             title="Time series comparison"),
            use_container_width=True)
    with c2:
        yr_df = cmp_df[cmp_df["year"] == yr] if yr else cmp_df
        if not yr_df.empty:
            agg = yr_df.groupby("country_name", as_index=False)["value"].mean()
            st.plotly_chart(plot_top_n_bar(agg, ds, title=f"Ranking {yr}"),
                            use_container_width=True)

    st.dataframe(cmp_df, height=280, use_container_width=True)
    st.download_button("Download CSV",
                       data=cmp_df.to_csv(index=False).encode("utf-8"),
                       file_name="comparison.csv", mime="text/csv",
                       key="dl_cmp")


def render_mode_sector(filters: dict) -> None:
    ds = filters["dataset_name"]
    yr = filters["year"]
    geo = filters["geo"]
    isic = filters["isic_code"]

    active = {"dataset_name": ds}
    if geo:  active["geo"] = geo
    if isic: active["isic_code"] = isic

    mode_df = _filter(active)
    if not mode_df.empty and "mode_name" in mode_df.columns:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(plot_stacked_bar(mode_df, ds, x="year",
                                             title="Absolute values by mode"),
                            use_container_width=True)
        with c2:
            st.plotly_chart(plot_stacked_bar(mode_df, ds, x="year", pct=True,
                                             title="100% share by mode"),
                            use_container_width=True)
    else:
        _no_data("mode chart")

    _section("Mode 3 / Cross-border Ratio by Sector")
    sec_yr = st.selectbox("Year (sector)",
                          sorted(get_years("mos3_to_xborder_ratio"), reverse=True),
                          key="ms_sec_yr")
    sec_geo_label = st.selectbox(
        "Economy (sector)",
        ["World average"] + sorted(ISO3_NAMES.get(g, g)
                                   for g in get_available_values("geo")),
        key="ms_sec_geo")
    geo_sec = None
    if sec_geo_label != "World average":
        geo_sec = {v: k for k, v in ISO3_NAMES.items()}.get(sec_geo_label, sec_geo_label)

    sec_f: dict[str, Any] = {"dataset_name": "mos3_to_xborder_ratio", "year": sec_yr}
    if geo_sec:
        sec_f["geo"] = geo_sec
    sec_df = _filter(sec_f)
    if not sec_df.empty:
        agg_sec = (sec_df.groupby(["isic_code", "sector_name"], as_index=False)["value"]
                   .mean()
                   .sort_values("value", ascending=False)
                   .head(19))
        st.plotly_chart(plot_sector_bar(agg_sec,
                        title=f"Mode 3 ratio — {sec_geo_label} ({sec_yr})"),
                        use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        _section("Heatmap: Economy x Mode")
        hm_f: dict[str, Any] = {"dataset_name": ds}
        if yr: hm_f["year"] = yr
        hm_df = _filter(hm_f)
        if not hm_df.empty and "mode_name" in hm_df.columns:
            st.plotly_chart(plot_heatmap(hm_df, ds, title=f"Heatmap — {yr}"),
                            use_container_width=True)
