# -*- coding: utf-8 -*-
"""
Policy interpreter — generates structured policy interpretation for analytical results.
Uses the LLM with a tightly constrained prompt to avoid hallucination.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from services.query_interpreter import QueryPlan, get_indicator_meta
from services.data_loader import ISO3_NAMES, ISIC_NAMES, DATASETS

log = logging.getLogger(__name__)

_BASE = Path(__file__).parent.parent
load_dotenv(_BASE / ".env", override=False)
load_dotenv(_BASE.parent / "tiva-mos-chatbot" / ".env", override=False)

SYSTEM_PROMPT = """You are a junior OECD trade data analyst specialising in
Trade in Value-Added (TiVA) and GATS Modes of Supply.

STRICT RULES:
1. Only interpret data results provided to you. Never invent values.
2. Always cite the indicator, year, mode, and economies used.
3. Keep answers concise — 3 to 5 sentences per section.
4. Do not make unsupported policy claims.
5. Clearly distinguish descriptive findings from policy interpretation.
6. If data is ambiguous or limited, say so explicitly.
7. Mode 3 = Commercial presence / foreign affiliates.
   Mode 1/4 = Cross-border + presence of natural persons.
   Mode 2 = Consumption abroad.
"""

ANSWER_TEMPLATE = """
User question: {question}

Data summary:
{data_summary}

Indicator: {indicator_name} ({indicator_code})
Filters used: Year={year}, Economies={economies}, Mode={mode}, Unit={unit}

Please respond in this EXACT structure:

ANSWER:
[2-4 sentences. Direct answer to the question based only on the data provided.]

POLICY_INTERPRETATION:
[2-3 sentences. What this result may imply for trade policy, services trade, or investment.]

CAVEAT:
[1-2 sentences. Limitations of this data or result.]

FOLLOW_UP:
[3 short follow-up question suggestions, one per line, starting with "-"]
"""

DEFINITION_TEMPLATE = """
User asked: {question}

Definition available:
{definition}

Please explain this concept in 3-5 sentences in plain English suitable for
a non-specialist policy audience. Avoid jargon. If relevant, mention how it
relates to GATS modes of supply.
"""


def _active_llm():
    load_dotenv(_BASE / ".env", override=False)
    load_dotenv(_BASE.parent / "tiva-mos-chatbot" / ".env", override=False)
    providers = []
    if os.getenv("HUGGINGFACE_API_KEY"):
        providers.append(("huggingface", os.getenv("HUGGINGFACE_API_KEY"),
                          os.getenv("HF_MODEL", "Qwen/Qwen2.5-72B-Instruct")))
    if os.getenv("GROK_API_KEY"):
        providers.append(("grok", os.getenv("GROK_API_KEY"),
                          os.getenv("GROK_MODEL", "grok-3-mini")))
    if os.getenv("GEMINI_API_KEY"):
        providers.append(("gemini", os.getenv("GEMINI_API_KEY"),
                          os.getenv("GEMINI_MODEL", "gemini-2.5-flash")))
    return providers


def _call_hf(prompt: str, key: str, model: str) -> str:
    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(token=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user",   "content": prompt}],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        log.warning("HF error: %s", exc)
        return ""


def _call_grok(prompt: str, key: str, model: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.x.ai/v1")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user",   "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        log.warning("Grok error: %s", exc)
        return ""


def _call_gemini(prompt: str, key: str, model: str) -> str:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model=model, contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, temperature=0.3),
        )
        return resp.text.strip()
    except Exception as exc:
        log.warning("Gemini error: %s", exc)
        return ""


def llm_call(prompt: str) -> str:
    dispatch = {"huggingface": _call_hf, "grok": _call_grok, "gemini": _call_gemini}
    for provider, key, model in _active_llm():
        result = dispatch[provider](prompt, key, model)
        if result:
            log.info("LLM answered via %s", provider)
            return result
        log.warning("%s failed, trying next", provider)
    return ""


def get_provider_name() -> str | None:
    providers = _active_llm()
    return providers[0][0] if providers else None


def parse_llm_response(raw: str) -> dict[str, str]:
    """Parse structured LLM response into components."""
    sections = {"answer": "", "policy_interpretation": "",
                "caveat": "", "follow_up": []}
    current = None
    lines = raw.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("ANSWER:"):
            current = "answer"
            rest = stripped[7:].strip()
            if rest:
                sections["answer"] += rest + " "
        elif stripped.startswith("POLICY_INTERPRETATION:"):
            current = "policy_interpretation"
            rest = stripped[22:].strip()
            if rest:
                sections["policy_interpretation"] += rest + " "
        elif stripped.startswith("CAVEAT:"):
            current = "caveat"
            rest = stripped[7:].strip()
            if rest:
                sections["caveat"] += rest + " "
        elif stripped.startswith("FOLLOW_UP:"):
            current = "follow_up"
        elif stripped.startswith("- ") and current == "follow_up":
            sections["follow_up"].append(stripped[2:])
        elif stripped and current and current != "follow_up":
            sections[current] += stripped + " "
    # Clean up
    for k in ("answer", "policy_interpretation", "caveat"):
        sections[k] = sections[k].strip()
    return sections


def generate_response(plan: QueryPlan, df: pd.DataFrame | None) -> dict:
    """
    Full AI response for a query plan + data.
    Returns dict with keys: answer, policy_interpretation, caveat,
    follow_up, raw_llm, llm_used.
    """
    meta = get_indicator_meta(plan.dataset_name or "")
    indicator_name = DATASETS.get(plan.dataset_name or "", {}).get("label", "")
    indicator_code = DATASETS.get(plan.dataset_name or "", {}).get("code", "")
    unit = DATASETS.get(plan.dataset_name or "", {}).get("unit", "")
    geo_labels = [ISO3_NAMES.get(g, g) for g in (plan.geo or [])]
    mode_label = plan.mode_name or "All modes"
    year_label = str(plan.year) if plan.year else "All available years"

    # Build data summary for LLM
    data_summary = ""
    if df is not None and not df.empty:
        top = df.head(10)[["value"] + [c for c in
              ["country_name", "mode_name", "sector_name", "year"]
              if c in df.columns]].to_string(index=False)
        data_summary = f"Top rows:\n{top}"
    else:
        data_summary = "No data returned for these filters."

    # Definition questions
    if plan.intent == "explain" and plan.define_term:
        defn = meta.get("long_definition") or meta.get("short_definition", "")
        if not defn:
            from services.query_interpreter import _INDICATORS_META
            # Try term-based lookup
            defn = f"{plan.define_term} is a GATS Mode of Supply concept."
        prompt = DEFINITION_TEMPLATE.format(
            question=plan.raw_question, definition=defn)
        raw = llm_call(prompt)
        return {
            "answer": raw or defn,
            "policy_interpretation": "",
            "caveat": "",
            "follow_up": [],
            "raw_llm": raw,
            "llm_used": get_provider_name(),
        }

    # Analytical questions
    prompt = ANSWER_TEMPLATE.format(
        question=plan.raw_question,
        data_summary=data_summary,
        indicator_name=indicator_name,
        indicator_code=indicator_code,
        year=year_label,
        economies=", ".join(geo_labels) if geo_labels else "All economies",
        mode=mode_label,
        unit=unit,
    )
    raw = llm_call(prompt)
    parsed = parse_llm_response(raw) if raw else {}

    return {
        "answer": parsed.get("answer") or (
            f"Based on the {indicator_name} data for "
            f"{', '.join(geo_labels) or 'all economies'}, "
            f"year {year_label}, mode {mode_label}. "
            "See chart and table below."
        ),
        "policy_interpretation": parsed.get("policy_interpretation", ""),
        "caveat": parsed.get("caveat") or (
            meta.get("caveats", "") if meta else ""),
        "follow_up": parsed.get("follow_up", []),
        "raw_llm": raw,
        "llm_used": get_provider_name(),
    }
