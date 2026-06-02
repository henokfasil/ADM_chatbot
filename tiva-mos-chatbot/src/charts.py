"""
Reusable Plotly chart functions.  All functions:
- accept a pandas DataFrame
- return a plotly Figure (or None if data is empty)
- use OECD colour palette
- handle empty data gracefully
"""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from src.config import (
    OECD_BLUE, OECD_LIGHT_BLUE, OECD_GREY, OECD_LIGHT_GREY, DATASETS
)

# ── palette ───────────────────────────────────────────────────────────────────
_MODE_COLORS = {
    "Mode 1/4":               "#003087",
    "Mode 2":                 "#0070C0",
    "Mode 3":                 "#00B0F0",
    "Backward (Cross-border)":"#003087",
    "Backward (Mode 3)":      "#0070C0",
    "Forward (Cross-border)": "#6D6E71",
    "Forward (Mode 3)":       "#00B0F0",
    "Domestic content":       "#003087",
    "Foreign content (Mode 1/4)":"#0070C0",
    "Foreign content (Mode 3)":"#00B0F0",
    "Mode 3 / Cross-border":  "#003087",
}
_SEQ_PALETTE = [
    "#003087", "#0070C0", "#00B0F0", "#6D6E71",
    "#9DC3E6", "#2E75B6", "#1F4E79", "#BDD7EE",
]

_LAYOUT = dict(
    font_family="Arial, sans-serif",
    font_color="#333333",
    paper_bgcolor="white",
    plot_bgcolor="white",
    title_font_size=15,
    title_font_color=OECD_BLUE,
    legend_bgcolor="rgba(0,0,0,0)",
    legend_bordercolor="rgba(0,0,0,0)",
    margin=dict(t=60, b=50, l=60, r=30),
)


def _empty_fig(message: str = "No data available for the selected filters.") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message, xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color=OECD_GREY),
    )
    fig.update_layout(paper_bgcolor="white", plot_bgcolor=OECD_LIGHT_GREY,
                      xaxis_visible=False, yaxis_visible=False, height=300)
    return fig


def _dataset_label(dataset_name: str) -> str:
    return DATASETS.get(dataset_name, {}).get("label", dataset_name)


def _dataset_unit(dataset_name: str) -> str:
    return DATASETS.get(dataset_name, {}).get("unit", "")


# ── chart functions ───────────────────────────────────────────────────────────

def plot_time_series(
    df: pd.DataFrame,
    x: str = "year",
    y: str = "value",
    color: str | None = "mode_name",
    title: str = "",
    unit: str = "",
    dataset_name: str = "",
) -> go.Figure:
    if df is None or df.empty:
        return _empty_fig()

    lbl = title or _dataset_label(dataset_name)
    unt = unit or _dataset_unit(dataset_name)
    color_map = _MODE_COLORS if color == "mode_name" else {}

    fig = px.line(
        df, x=x, y=y, color=color,
        color_discrete_map=color_map or None,
        markers=True,
        labels={y: unt, x: "Year", color or "": ""},
        title=lbl,
    )
    fig.update_traces(line_width=2.2)
    fig.update_layout(**_LAYOUT, yaxis_title=unt)
    return fig


def plot_stacked_bar(
    df: pd.DataFrame,
    x: str = "country_name",
    y: str = "value",
    color: str = "mode_name",
    title: str = "",
    unit: str = "",
    dataset_name: str = "",
    pct: bool = False,
) -> go.Figure:
    if df is None or df.empty:
        return _empty_fig()

    lbl = title or _dataset_label(dataset_name)
    unt = (unit or _dataset_unit(dataset_name)) if not pct else "Share (%)"
    barmode = "relative" if pct else "stack"

    plot_df = df.copy()
    if pct:
        totals = plot_df.groupby(x)[y].transform("sum")
        plot_df[y] = plot_df[y] / totals * 100

    fig = px.bar(
        plot_df, x=x, y=y, color=color,
        color_discrete_map=_MODE_COLORS,
        barmode=barmode,
        labels={y: unt, x: "", color: ""},
        title=lbl,
    )
    fig.update_layout(**_LAYOUT, yaxis_title=unt)
    return fig


def plot_top_n_bar(
    df: pd.DataFrame,
    x: str = "value",
    y: str = "country_name",
    title: str = "",
    unit: str = "",
    dataset_name: str = "",
    color_col: str | None = None,
) -> go.Figure:
    if df is None or df.empty:
        return _empty_fig()

    lbl = title or _dataset_label(dataset_name)
    unt = unit or _dataset_unit(dataset_name)
    plot_df = df.sort_values(x, ascending=True)

    fig = px.bar(
        plot_df, x=x, y=y, orientation="h",
        color=color_col,
        color_discrete_sequence=_SEQ_PALETTE,
        labels={x: unt, y: ""},
        title=lbl,
    )
    fig.update_layout(**_LAYOUT, xaxis_title=unt, height=max(300, len(df) * 32 + 80))
    fig.update_traces(marker_color=OECD_BLUE)
    return fig


def plot_heatmap(
    df: pd.DataFrame,
    x_col: str = "mode_name",
    y_col: str = "country_name",
    z_col: str = "value",
    title: str = "",
    unit: str = "",
    dataset_name: str = "",
) -> go.Figure:
    if df is None or df.empty:
        return _empty_fig()

    lbl = title or _dataset_label(dataset_name)
    unt = unit or _dataset_unit(dataset_name)
    pivot = df.pivot_table(index=y_col, columns=x_col, values=z_col, aggfunc="mean")

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[[0, "white"], [1, OECD_BLUE]],
        hoverongaps=False,
        colorbar=dict(title=unt),
    ))
    fig.update_layout(
        **_LAYOUT,
        title=lbl,
        height=max(400, len(pivot) * 22 + 100),
        xaxis_title="",
        yaxis_title="",
        yaxis_autorange="reversed",
    )
    return fig


def plot_indexed_change(
    df: pd.DataFrame,
    x: str = "year",
    y: str = "value",
    color: str = "country_name",
    base_year: int | None = None,
    title: str = "",
    dataset_name: str = "",
) -> go.Figure:
    """Index all series to base_year = 100."""
    if df is None or df.empty:
        return _empty_fig()

    lbl = title or f"Indexed change — {_dataset_label(dataset_name)}"
    if base_year is None:
        base_year = int(df[x].min())

    groups = df.groupby(color)
    traces = []
    for name, grp in groups:
        grp = grp.sort_values(x)
        base_val = grp.loc[grp[x] == base_year, y]
        if base_val.empty or float(base_val.iloc[0]) == 0:
            continue
        indexed = grp[y] / float(base_val.iloc[0]) * 100
        traces.append(go.Scatter(
            x=grp[x], y=indexed, mode="lines+markers", name=str(name),
            line=dict(width=2),
        ))

    if not traces:
        return _empty_fig()

    fig = go.Figure(traces)
    fig.add_hline(y=100, line_dash="dot", line_color=OECD_GREY,
                  annotation_text=f"Base {base_year}=100")
    fig.update_layout(**_LAYOUT, title=lbl, yaxis_title=f"Index ({base_year}=100)")
    return fig


def plot_mode_shares_donut(
    df: pd.DataFrame,
    names_col: str = "mode_name",
    values_col: str = "value",
    title: str = "",
    dataset_name: str = "",
) -> go.Figure:
    """Only use when ≤5 slices; otherwise prefer stacked bar."""
    if df is None or df.empty:
        return _empty_fig()

    lbl = title or _dataset_label(dataset_name)
    agg = df.groupby(names_col)[values_col].sum().reset_index()
    if len(agg) > 6:
        return _empty_fig("Too many categories for a donut chart. Use stacked bar instead.")

    colors = [_MODE_COLORS.get(m, _SEQ_PALETTE[i % len(_SEQ_PALETTE)])
              for i, m in enumerate(agg[names_col])]
    fig = go.Figure(go.Pie(
        labels=agg[names_col], values=agg[values_col],
        hole=0.45, marker_colors=colors,
        textinfo="label+percent",
    ))
    fig.update_layout(**_LAYOUT, title=lbl, showlegend=True)
    return fig


def plot_sector_ranking(
    df: pd.DataFrame,
    x: str = "value",
    y: str = "sector_name",
    title: str = "Mode 3 to Cross-border Ratio by Sector",
    unit: str = "ratio",
) -> go.Figure:
    if df is None or df.empty:
        return _empty_fig()
    plot_df = df.sort_values(x, ascending=True)
    fig = px.bar(
        plot_df, x=x, y=y, orientation="h",
        color=x, color_continuous_scale=[[0, "#BDD7EE"], [1, OECD_BLUE]],
        labels={x: unit, y: ""},
        title=title,
    )
    fig.update_layout(**_LAYOUT, xaxis_title=unit,
                      height=max(300, len(df) * 32 + 80),
                      coloraxis_showscale=False)
    fig.add_vline(x=1, line_dash="dash", line_color=OECD_GREY,
                  annotation_text="Mode 3 = Cross-border")
    return fig
