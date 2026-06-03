# -*- coding: utf-8 -*-
"""
Chart generator — creates Plotly figures from query results.
Always tries to produce the best chart for the data shape.
"""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from services.data_loader import DATASETS

OECD_BLUE = "#003087"
OECD_BLUE2 = "#0055A5"
OECD_LIGHT = "#00A3E0"
OECD_GREY = "#6D6E71"

_MODE_COLORS = {
    "Mode 1/4": "#003087", "Mode 2": "#0070C0", "Mode 3": "#00B0F0",
    "Backward (Cross-border)": "#003087", "Backward (Mode 3)": "#0070C0",
    "Forward (Cross-border)": "#6D6E71", "Forward (Mode 3)": "#00B0F0",
    "Domestic content": "#003087",
    "Foreign content (Mode 1/4)": "#0070C0",
    "Foreign content (Mode 3)": "#00B0F0",
    "Mode 3 / Cross-border": "#003087",
}
_SEQ = ["#003087", "#0070C0", "#00B0F0", "#6D6E71", "#9DC3E6",
        "#2E75B6", "#1F4E79", "#BDD7EE"]

_LAYOUT = dict(
    font_family="Inter, Arial, sans-serif",
    font_color="#333",
    paper_bgcolor="white",
    plot_bgcolor="white",
    title_font_size=13,
    title_font_color=OECD_BLUE,
    legend_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=50, b=40, l=50, r=20),
)


def _empty(msg: str = "No data for the selected filters.") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, xref="paper", yref="paper",
                       x=0.5, y=0.5, showarrow=False,
                       font=dict(size=13, color=OECD_GREY))
    fig.update_layout(paper_bgcolor="#F8FAFC", plot_bgcolor="#F8FAFC",
                      xaxis_visible=False, yaxis_visible=False, height=260)
    return fig


def _unit(dataset_name: str) -> str:
    return DATASETS.get(dataset_name, {}).get("unit", "")


def plot_top_n_bar(df: pd.DataFrame, dataset_name: str = "",
                   title: str = "", n: int = 15) -> go.Figure:
    if df is None or df.empty:
        return _empty()
    plot_df = df.head(n).sort_values("value", ascending=True)
    unt = _unit(dataset_name)
    fig = px.bar(plot_df, x="value", y="country_name", orientation="h",
                 color_discrete_sequence=[OECD_BLUE],
                 labels={"value": unt, "country_name": ""},
                 title=title or f"Top economies — {DATASETS.get(dataset_name, {}).get('label', '')}")
    fig.update_layout(**_LAYOUT, xaxis_title=unt,
                      height=max(300, len(plot_df) * 30 + 80))
    fig.update_traces(marker_color=OECD_BLUE)
    return fig


def plot_time_series(df: pd.DataFrame, dataset_name: str = "",
                     color: str | None = "mode_name", title: str = "") -> go.Figure:
    if df is None or df.empty:
        return _empty()
    unt = _unit(dataset_name)
    color_map = _MODE_COLORS if color == "mode_name" else {}
    fig = px.line(df, x="year", y="value", color=color,
                  color_discrete_map=color_map or None,
                  markers=True,
                  labels={"value": unt, "year": "Year", color or "": ""},
                  title=title or DATASETS.get(dataset_name, {}).get("label", ""))
    fig.update_traces(line_width=2.2)
    fig.update_layout(**_LAYOUT, yaxis_title=unt)
    return fig


def plot_stacked_bar(df: pd.DataFrame, dataset_name: str = "",
                     x: str = "year", pct: bool = False,
                     title: str = "") -> go.Figure:
    if df is None or df.empty:
        return _empty()
    unt = "Share (%)" if pct else _unit(dataset_name)
    plot_df = df.copy()
    if pct:
        tots = plot_df.groupby(x)["value"].transform("sum")
        plot_df["value"] = plot_df["value"] / tots * 100
    fig = px.bar(plot_df, x=x, y="value", color="mode_name",
                 color_discrete_map=_MODE_COLORS,
                 barmode="stack",
                 labels={"value": unt, x: "", "mode_name": ""},
                 title=title or ("100% share by mode" if pct else "Absolute values by mode"))
    fig.update_layout(**_LAYOUT, yaxis_title=unt)
    return fig


def plot_heatmap(df: pd.DataFrame, dataset_name: str = "",
                 title: str = "") -> go.Figure:
    if df is None or df.empty or "mode_name" not in df.columns:
        return _empty()
    pivot = df.pivot_table(index="country_name", columns="mode_name",
                           values="value", aggfunc="mean")
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale=[[0, "white"], [1, OECD_BLUE]],
        hoverongaps=False,
        colorbar=dict(title=_unit(dataset_name)),
    ))
    fig.update_layout(**_LAYOUT, title=title or "Heatmap",
                      height=max(400, len(pivot) * 20 + 100),
                      yaxis_autorange="reversed")
    return fig


def plot_sector_bar(df: pd.DataFrame, title: str = "") -> go.Figure:
    if df is None or df.empty:
        return _empty()
    plot_df = df.sort_values("value", ascending=True)
    fig = px.bar(plot_df, x="value", y="sector_name", orientation="h",
                 color="value", color_continuous_scale=[[0, "#BDD7EE"], [1, OECD_BLUE]],
                 labels={"value": "ratio", "sector_name": ""},
                 title=title or "Mode 3 / Cross-border Ratio by Sector")
    fig.update_layout(**_LAYOUT, coloraxis_showscale=False,
                      height=max(300, len(plot_df) * 30 + 80))
    fig.add_vline(x=1, line_dash="dash", line_color=OECD_GREY,
                  annotation_text="Mode 3 = Cross-border")
    return fig


def plot_comparison_bar(df: pd.DataFrame, dataset_name: str = "",
                        year: int | None = None, title: str = "") -> go.Figure:
    if df is None or df.empty:
        return _empty()
    agg = df.groupby("country_name", as_index=False)["value"].mean()
    agg = agg.sort_values("value", ascending=True)
    unt = _unit(dataset_name)
    fig = px.bar(agg, x="value", y="country_name", orientation="h",
                 color_discrete_sequence=[OECD_BLUE],
                 labels={"value": unt, "country_name": ""},
                 title=title or f"Comparison{f' — {year}' if year else ''}")
    fig.update_layout(**_LAYOUT, xaxis_title=unt,
                      height=max(300, len(agg) * 32 + 80))
    return fig


def smart_chart(df: pd.DataFrame, intent: str, dataset_name: str,
                year: int | None = None) -> go.Figure | None:
    """
    Choose the best chart type automatically based on data shape and intent.
    Returns None only if df is genuinely empty.
    """
    if df is None or df.empty:
        return None

    if intent == "rank" and "country_name" in df.columns:
        return plot_top_n_bar(df, dataset_name)

    if intent == "sector" and "sector_name" in df.columns:
        return plot_sector_bar(df)

    if intent == "mode_shares" and "mode_name" in df.columns:
        return plot_stacked_bar(df, dataset_name, x="mode_name")

    if intent in ("trend",) and "year" in df.columns:
        color = "mode_name" if "mode_name" in df.columns else (
            "country_name" if "country_name" in df.columns else None)
        return plot_time_series(df, dataset_name, color=color)

    if intent == "compare":
        if "year" in df.columns and df["year"].nunique() > 1:
            color = "country_name" if "country_name" in df.columns else "mode_name"
            return plot_time_series(df, dataset_name, color=color, title="Comparison")
        return plot_comparison_bar(df, dataset_name, year)

    # Fallback — pick best chart based on columns present
    if "country_name" in df.columns and "value" in df.columns:
        return plot_top_n_bar(df, dataset_name)
    if "sector_name" in df.columns and "value" in df.columns:
        return plot_sector_bar(df)
    if "mode_name" in df.columns and "value" in df.columns:
        return plot_stacked_bar(df, dataset_name, x="mode_name")
    if "year" in df.columns and "value" in df.columns:
        color = "mode_name" if "mode_name" in df.columns else (
            "country_name" if "country_name" in df.columns else None)
        return plot_time_series(df, dataset_name, color=color)

    return None
