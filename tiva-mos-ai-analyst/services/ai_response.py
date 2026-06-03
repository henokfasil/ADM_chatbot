# -*- coding: utf-8 -*-
"""
AI response orchestrator — ties together query interpretation, data query,
chart generation, and policy interpretation into one AnalystResponse.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from services.data_loader import (
    load_combined, DATASETS, ISO3_NAMES, ISIC_NAMES, get_years,
)
from services.query_interpreter import QueryPlan, build_query_plan, get_indicator_meta
from services.chart_generator import smart_chart
from services.policy_interpreter import generate_response


@dataclass
class AnalystResponse:
    question: str = ""
    plan: QueryPlan | None = None
    answer: str = ""
    policy_interpretation: str = ""
    caveat: str = ""
    follow_up: list[str] = field(default_factory=list)
    df: pd.DataFrame | None = None
    fig: go.Figure | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    is_ambiguous: bool = False
    ambiguity_message: str = ""
    llm_used: str | None = None
    error: str | None = None


# ── data query ─────────────────────────────────────────────────────────────

def _execute(plan: QueryPlan) -> pd.DataFrame:
    df = load_combined()
    if df.empty:
        return df

    filters: dict[str, Any] = {"dataset_name": plan.dataset_name}
    if plan.geo:
        filters["geo"] = plan.geo
    if plan.mode_name:
        filters["mode_name"] = plan.mode_name
    if plan.isic_code:
        filters["isic_code"] = plan.isic_code

    # Year filter
    if plan.year_range:
        y0, y1 = plan.year_range
        for col, val in filters.items():
            if col not in df.columns:
                continue
            if isinstance(val, list):
                df = df[df[col].isin(val)]
            else:
                df = df[df[col] == val]
        df = df[(df["year"] >= y0) & (df["year"] <= y1)]
        return df.reset_index(drop=True)
    elif plan.year:
        filters["year"] = plan.year

    for col, val in filters.items():
        if col not in df.columns or val is None:
            continue
        if df[col].isna().all():
            continue
        if isinstance(val, list):
            df = df[df[col].isin(val)]
        else:
            df = df[df[col] == val]

    # For ranking, aggregate and sort
    if plan.intent == "rank":
        if "country_name" in df.columns:
            df = (df.groupby("country_name", as_index=False)["value"]
                  .mean()
                  .sort_values("value", ascending=False)
                  .head(plan.n))
        elif "sector_name" in df.columns:
            df = (df.groupby(["isic_code", "sector_name"], as_index=False)["value"]
                  .mean()
                  .sort_values("value", ascending=False)
                  .head(plan.n))

    return df.reset_index(drop=True)


def _build_evidence(plan: QueryPlan, df: pd.DataFrame | None) -> dict[str, Any]:
    ds_meta = DATASETS.get(plan.dataset_name or "", {})
    ind_meta = get_indicator_meta(plan.dataset_name or "")
    geo_labels = [ISO3_NAMES.get(g, g) for g in (plan.geo or [])]
    return {
        "Dataset": plan.dataset_name or "N/A",
        "Indicator": ds_meta.get("label", "N/A"),
        "Indicator code": ds_meta.get("code", "N/A"),
        "Year": str(plan.year or plan.year_range or "All available"),
        "Economies": ", ".join(geo_labels) if geo_labels else "All economies",
        "Mode of supply": plan.mode_name or "All modes",
        "Sector": ISIC_NAMES.get(plan.isic_code or "", plan.isic_code or "All sectors"),
        "Unit": ds_meta.get("unit", "N/A"),
        "Source": "OECD TiVA-MoS 2026 Preliminary Release",
        "Available years": str(get_years(plan.dataset_name)),
        "Rows returned": str(len(df)) if df is not None else "0",
        "Definition": (ind_meta.get("short_definition") or "")[:200] + "...",
        "Caveats": ind_meta.get("caveats", ""),
    }


# ── main entry point ───────────────────────────────────────────────────────

def analyse(question: str) -> AnalystResponse:
    plan = build_query_plan(question)

    # Return ambiguity clarification immediately
    if plan.is_ambiguous:
        return AnalystResponse(
            question=question,
            plan=plan,
            is_ambiguous=True,
            ambiguity_message=plan.ambiguity_message,
            answer=plan.ambiguity_message,
            evidence=_build_evidence(plan, None),
        )

    # Execute data query
    df = _execute(plan)
    df_for_response = df if not df.empty else None

    # Generate AI response
    response_dict = generate_response(plan, df_for_response)

    # Generate chart
    fig = smart_chart(df_for_response, plan.intent,
                      plan.dataset_name or "", plan.year)

    return AnalystResponse(
        question=question,
        plan=plan,
        answer=response_dict.get("answer", ""),
        policy_interpretation=response_dict.get("policy_interpretation", ""),
        caveat=response_dict.get("caveat", ""),
        follow_up=response_dict.get("follow_up", []),
        df=df_for_response,
        fig=fig,
        evidence=_build_evidence(plan, df_for_response),
        llm_used=response_dict.get("llm_used"),
    )
