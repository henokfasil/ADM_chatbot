# -*- coding: utf-8 -*-
"""Export service — CSV, text, policy note generation."""
from __future__ import annotations

import io
import textwrap
from datetime import date

import pandas as pd

from services.ai_response import AnalystResponse
from services.data_loader import DATASETS


def export_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def export_answer_text(resp: AnalystResponse) -> str:
    lines = [
        "TiVA-MoS AI Analyst — Analytical Output",
        f"Date: {date.today().isoformat()}",
        "=" * 60,
        "",
        f"QUESTION: {resp.question}",
        "",
        "ANSWER",
        "-" * 40,
        resp.answer,
        "",
    ]
    if resp.policy_interpretation:
        lines += ["POLICY INTERPRETATION", "-" * 40, resp.policy_interpretation, ""]
    if resp.caveat:
        lines += ["CAVEAT", "-" * 40, resp.caveat, ""]
    if resp.evidence:
        lines += ["EVIDENCE & FILTERS", "-" * 40]
        for k, v in resp.evidence.items():
            if v and v != "N/A" and v != "0":
                lines.append(f"  {k}: {v}")
        lines.append("")
    if resp.follow_up:
        lines += ["FOLLOW-UP QUESTIONS", "-" * 40]
        for q in resp.follow_up:
            lines.append(f"  - {q}")
        lines.append("")
    lines += ["=" * 60, "Source: OECD TiVA-MoS 2026 Preliminary Release"]
    return "\n".join(lines)


def export_policy_note(resp: AnalystResponse) -> str:
    ds_label = DATASETS.get(
        (resp.plan.dataset_name or "") if resp.plan else "", {}
    ).get("label", "TiVA-MoS Indicator")

    ev = resp.evidence or {}
    geo = ev.get("Economies", "N/A")
    year = ev.get("Year", "N/A")
    mode = ev.get("Mode of supply", "All modes")
    unit = ev.get("Unit", "N/A")

    # Wrap answer text
    answer_wrapped = textwrap.fill(resp.answer, width=80) if resp.answer else "N/A"
    policy_wrapped = textwrap.fill(resp.policy_interpretation, width=80) if resp.policy_interpretation else ""
    caveat_wrapped = textwrap.fill(resp.caveat, width=80) if resp.caveat else ""

    note = f"""
================================================================================
                         POLICY NOTE — TiVA-MoS AI ANALYST
================================================================================

Title:    {ds_label} — Analytical Note
Date:     {date.today().isoformat()}
Prepared: TiVA-MoS AI Analyst (OECD TiVA-MoS 2026 Preliminary Release)

--------------------------------------------------------------------------------
QUESTION
--------------------------------------------------------------------------------
{resp.question}

--------------------------------------------------------------------------------
KEY FINDING
--------------------------------------------------------------------------------
{answer_wrapped}

--------------------------------------------------------------------------------
CHART / DATA
--------------------------------------------------------------------------------
[Chart available in the app. Export data table separately as CSV.]

Economies: {geo}
Year:      {year}
Mode:      {mode}
Unit:      {unit}

--------------------------------------------------------------------------------
POLICY INTERPRETATION
--------------------------------------------------------------------------------
{policy_wrapped or "Not generated for this query type."}

--------------------------------------------------------------------------------
DATA SOURCE & FILTERS
--------------------------------------------------------------------------------
"""
    for k, v in ev.items():
        if v and v not in ("N/A", "0"):
            note += f"  {k}: {v}\n"

    note += f"""
--------------------------------------------------------------------------------
CAVEAT
--------------------------------------------------------------------------------
{caveat_wrapped or "See dataset documentation for full methodological notes."}

--------------------------------------------------------------------------------
DISCLAIMER
--------------------------------------------------------------------------------
This note was generated automatically by TiVA-MoS AI Analyst.
Values are from the OECD TiVA-MoS 2026 Preliminary Release.
Results should be verified against the full dataset before publication.

================================================================================
"""
    return note.strip()
