"""
Two-layer chatbot:
  Layer A — deterministic query planner + executor (always runs)
  Layer B — LLM explanation of Layer A results (runs only when API key available)

LLM provider fallback: Gemini → Grok → HuggingFace
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.config import (
    DATASETS, ISO3_NAMES, ISIC_NAMES, active_llm_provider,
    GEMINI_MODEL, GROK_MODEL, HF_MODEL,
)
from src.query_engine import (
    filter_data, get_time_series, get_top_n, get_growth,
    get_mode_shares, compare_countries, get_sector_ranking,
    fuzzy_match, get_years, get_available_values,
)
from src.prompts import (
    SYSTEM_PROMPT, EXPLAIN_RESULT_TEMPLATE, EXPLAIN_GROWTH_TEMPLATE,
    EXPLAIN_TOP_N_TEMPLATE, EXPLAIN_MODE_SHARES_TEMPLATE,
    METADATA_DEFINITIONS, CLARIFICATION_TEMPLATE, DATASET_OVERVIEW_PROMPT,
)

log = logging.getLogger(__name__)

# ── intent vocabulary ─────────────────────────────────────────────────────────
_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("define",        ["what is", "what does", "what are", "define", "explain",
                       "meaning of", "definition", "tell me about",
                       "what kind", "what information", "what can i", "what data",
                       "what does this", "overview", "about this", "describe"]),
    ("sector",        ["which sector", "which sectors", "which industry",
                       "by sector", "by industry", "sector ranking",
                       "sector breakdown", "isic"]),
    ("mode_shares",   ["mode share", "mode breakdown", "share by mode",
                       "breakdown", "composition", "split by mode",
                       "proportion", "percentage by mode", "distribution by mode"]),
    ("compare",       ["compare", "versus", "vs", "difference between",
                       "against", "relative to"]),
    ("time_series",   ["trend", "over time", "time series", "evolution",
                       "history", "change over"]),
    ("growth",        ["grew", "growth", "increase", "decrease",
                       "rose", "fell", "doubled", "improved"]),
    ("top_n",         ["top", "highest", "largest", "biggest", "rank", "ranking",
                       "who leads", "leading", "best"]),
    ("bilateral",     ["bilateral", "partner", "exports to",
                       "imports from", "flow"]),
]

_DATASET_KEYWORDS: dict[str, list[str]] = {
    "dmst_va_in_frgn_dmnd":  ["domestic va", "domestic value", "exports", "foreign demand"],
    "frgn_va_in_dmst_dmnd":  ["foreign va", "foreign value", "imports", "domestic demand"],
    "gvc_participation":     ["gvc", "global value chain", "backward", "forward", "participation"],
    "va_in_mnf_export":      ["manufacturing", "mnf", "manufacturing export"],
    "mos3_to_xborder_ratio": ["ratio", "mode 3 ratio", "mos3", "cross-border ratio"],
}

_MODE_KEYWORDS: dict[str, list[str]] = {
    "Mode 1/4":                    ["mode 1", "mode 4", "mode 1/4", "cross-border", "digital"],
    "Mode 2":                      ["mode 2", "consumption abroad", "tourism"],
    "Mode 3":                      ["mode 3", "commercial presence", "foreign affiliates",
                                    "fdi", "subsidiary", "affiliates"],
    "Backward (Cross-border)":     ["backward cross-border", "backward xborder"],
    "Backward (Mode 3)":           ["backward mode 3"],
    "Forward (Cross-border)":      ["forward cross-border"],
    "Forward (Mode 3)":            ["forward mode 3"],
    "Domestic content":            ["domestic content"],
    "Foreign content (Mode 1/4)":  ["foreign content mode 1"],
    "Foreign content (Mode 3)":    ["foreign content mode 3"],
}


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class QueryPlan:
    intent: str = "unknown"
    dataset_name: str | None = None
    geo: str | list[str] | None = None
    mode_name: str | None = None
    isic_code: str | None = None
    year: int | None = None
    n: int = 10
    chart_type: str | None = None
    define_term: str | None = None
    clarification_needed: str | None = None
    raw_question: str = ""


@dataclass
class ChatResponse:
    answer: str = ""
    result_df: pd.DataFrame | None = None
    chart_type: str | None = None
    plan: QueryPlan | None = None
    error: str | None = None


# ── Layer A: deterministic entity extraction + query ─────────────────────────

def classify_intent(message: str) -> str:
    msg = message.lower()
    for intent, keywords in _INTENT_PATTERNS:
        if any(kw in msg for kw in keywords):
            return intent
    return "general"


def extract_dataset(message: str) -> str | None:
    msg = message.lower()
    for ds, kws in _DATASET_KEYWORDS.items():
        if any(kw in msg for kw in kws):
            return ds
    # Default to dmst_va when talking about "services exports"
    if any(w in msg for w in ["services export", "export"]):
        return "dmst_va_in_frgn_dmnd"
    if any(w in msg for w in ["services import", "import"]):
        return "frgn_va_in_dmst_dmnd"
    return None


def extract_geo(message: str) -> list[str]:
    """Return list of ISO-3 codes found or fuzzy-matched in message."""
    found: list[str] = []
    upper_tokens = re.findall(r"\b[A-Z]{2,3}\b", message)
    iso3_set = set(ISO3_NAMES.keys())
    for tok in upper_tokens:
        if tok in iso3_set:
            found.append(tok)

    # Fuzzy match on full country names
    name_to_iso = {v.lower(): k for k, v in ISO3_NAMES.items()}
    words = message.lower()
    for name, iso in name_to_iso.items():
        if name in words:
            if iso not in found:
                found.append(iso)

    # Fuzzy fallback for partial names
    if not found:
        matches = fuzzy_match(message, "geo", threshold=70)
        found = matches[:3]

    return found


def extract_mode(message: str) -> str | None:
    msg = message.lower()
    for mode, kws in _MODE_KEYWORDS.items():
        if any(kw in msg for kw in kws):
            return mode
    return None


_GENERIC_WORDS = {"services", "service", "trade", "export", "import", "data",
                  "economy", "economies", "country", "countries", "value", "mode"}

def extract_isic(message: str) -> str | None:
    msg = message.upper()
    # Direct ISIC code mention
    for code in ISIC_NAMES:
        if code in msg:
            return code
    # Sector name match (exact phrase only — not fuzzy on generic words)
    msg_lower = message.lower()
    # Strip generic words before sector name search
    tokens = set(msg_lower.split())
    if tokens.issubset(_GENERIC_WORDS):
        return None
    for code, name in ISIC_NAMES.items():
        if name.lower() in msg_lower:
            return code
    # Fuzzy only if message contains a sector-specific term (higher threshold)
    matches = fuzzy_match(message, "isic_code", threshold=80)
    return matches[0] if matches else None


def extract_year(message: str) -> int | None:
    years = re.findall(r"\b(20\d{2}|199\d)\b", message)
    if years:
        return int(years[-1])
    return None


def extract_n(message: str) -> int:
    match = re.search(r"\b(top|bottom)\s+(\d+)\b", message.lower())
    if match:
        return min(int(match.group(2)), 20)
    return 10


def build_query_plan(message: str) -> QueryPlan:
    intent = classify_intent(message)
    dataset = extract_dataset(message)
    geos = extract_geo(message)
    mode = extract_mode(message)
    isic = extract_isic(message)
    year = extract_year(message)
    n = extract_n(message)

    # If no dataset and it's about ratio/sector, use mos3
    if not dataset and isic:
        dataset = "mos3_to_xborder_ratio"

    # Default dataset
    if not dataset:
        dataset = "dmst_va_in_frgn_dmnd"

    # Detect define intent for terminology
    define_term = None
    if intent == "define":
        msg_lower = message.lower()
        for term in METADATA_DEFINITIONS:
            if term.lower() in msg_lower:
                define_term = term
                break

    # Detect if this is a compare intent (multiple countries)
    if len(geos) > 1:
        intent = "compare"

    # Chart type heuristic
    chart_map = {
        "time_series": "line",
        "growth": "line",
        "top_n": "bar",
        "mode_shares": "stacked_bar",
        "compare": "line",
        "sector": "bar",
        "bilateral": "bar",
    }
    chart_type = chart_map.get(intent, "bar")

    return QueryPlan(
        intent=intent,
        dataset_name=dataset,
        geo=geos if geos else None,
        mode_name=mode,
        isic_code=isic,
        year=year,
        n=n,
        chart_type=chart_type,
        define_term=define_term,
        raw_question=message,
    )


def execute_query_plan(plan: QueryPlan) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Execute plan; return (result_df, metadata_dict)."""
    meta: dict[str, Any] = {
        "dataset_label": DATASETS.get(plan.dataset_name or "", {}).get("label", plan.dataset_name),
        "geo_label": (
            ", ".join(ISO3_NAMES.get(g, g) for g in plan.geo)
            if isinstance(plan.geo, list) else ISO3_NAMES.get(plan.geo or "", plan.geo or "All")
        ),
        "mode_name": plan.mode_name or "All modes",
        "sector_label": ISIC_NAMES.get(plan.isic_code or "", plan.isic_code or "All sectors"),
        "years": str(plan.year) if plan.year else "All available years",
        "unit": DATASETS.get(plan.dataset_name or "", {}).get("unit", ""),
    }

    if plan.intent == "define" and plan.define_term:
        return pd.DataFrame(), meta

    if plan.intent in ("time_series", "growth"):
        geo_arg = plan.geo[0] if isinstance(plan.geo, list) and len(plan.geo) == 1 else (plan.geo or [])
        df = get_time_series(
            plan.dataset_name or "dmst_va_in_frgn_dmnd",
            geo_arg or get_available_values("geo")[:5],
            mode_name=plan.mode_name,
            isic_code=plan.isic_code,
        )
        return df, meta

    if plan.intent == "top_n":
        df = get_top_n(
            plan.dataset_name or "dmst_va_in_frgn_dmnd",
            year=plan.year,
            mode_name=plan.mode_name,
            isic_code=plan.isic_code,
            n=plan.n,
        )
        return df, meta

    if plan.intent == "mode_shares":
        df = get_mode_shares(
            plan.dataset_name or "dmst_va_in_frgn_dmnd",
            geo=plan.geo,
            year=plan.year,
            isic_code=plan.isic_code,
        )
        return df, meta

    if plan.intent == "compare":
        df = compare_countries(
            plan.dataset_name or "dmst_va_in_frgn_dmnd",
            geos=plan.geo if isinstance(plan.geo, list) else [plan.geo],
            mode_name=plan.mode_name,
            isic_code=plan.isic_code,
            year=plan.year,
        )
        return df, meta

    if plan.intent == "sector":
        df = get_sector_ranking(year=plan.year, geo=plan.geo, n=20)
        return df, meta

    # fallback: generic filter
    filters: dict[str, Any] = {"dataset_name": plan.dataset_name}
    if plan.geo:
        filters["geo"] = plan.geo
    if plan.mode_name:
        filters["mode_name"] = plan.mode_name
    if plan.isic_code:
        filters["isic_code"] = plan.isic_code
    if plan.year:
        filters["year"] = plan.year
    return filter_data(filters), meta


# ── Layer B: LLM explanation ──────────────────────────────────────────────────

def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
            ),
        )
        return resp.text.strip()
    except Exception as exc:
        log.warning("Gemini error: %s", exc)
        return ""


def _call_grok(prompt: str, api_key: str, model: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        log.warning("Grok error: %s", exc)
        return ""


def _call_huggingface(prompt: str, api_key: str, model: str) -> str:
    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(token=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        log.warning("HuggingFace error: %s", exc)
        return ""


def llm_explain(prompt: str) -> str:
    """Try all configured LLM providers in priority order; return first success."""
    from dotenv import load_dotenv
    from src.config import _base
    load_dotenv(_base / ".env", override=False)
    load_dotenv(_base / ".env.example", override=False)

    import os
    # Priority: HuggingFace (open-source inference) -> Grok -> Gemini
    candidates = []
    if os.getenv("HUGGINGFACE_API_KEY"):
        candidates.append(("huggingface",  os.getenv("HUGGINGFACE_API_KEY"), os.getenv("HF_MODEL",     "Qwen/Qwen2.5-72B-Instruct")))
    if os.getenv("GROK_API_KEY"):
        candidates.append(("grok",         os.getenv("GROK_API_KEY"),        os.getenv("GROK_MODEL",   "grok-3-mini")))
    if os.getenv("GEMINI_API_KEY"):
        candidates.append(("gemini",       os.getenv("GEMINI_API_KEY"),      os.getenv("GEMINI_MODEL", "gemini-2.5-flash")))

    dispatch = {"gemini": _call_gemini, "grok": _call_grok, "huggingface": _call_huggingface}

    for provider, api_key, model in candidates:
        result = dispatch[provider](prompt, api_key, model)
        if result:
            log.info("LLM answered via %s", provider)
            return result
        log.warning("%s failed or returned empty — trying next provider", provider)

    return ""


# ── main entry point ──────────────────────────────────────────────────────────

_OVERVIEW_TRIGGERS = {
    "what kind", "what information", "what can i", "what data",
    "what can you", "what questions", "what topics", "overview",
    "about this dataset", "about this data", "describe this",
    "what does this app", "what does this chatbot",
}

def _is_overview_question(message: str) -> bool:
    msg = message.lower()
    return any(t in msg for t in _OVERVIEW_TRIGGERS)


def _dataset_summary_text() -> str:
    lines = []
    for name, meta in DATASETS.items():
        lines.append(f"• {meta['label']}: {meta['description'][:120]}…")
    return "\n".join(lines)


def respond(message: str) -> ChatResponse:
    plan = build_query_plan(message)

    # ── dataset overview question ──────────────────────────────────────────
    if plan.intent == "define" and _is_overview_question(message):
        prompt = DATASET_OVERVIEW_PROMPT.format(
            question=message,
            dataset_summary=_dataset_summary_text(),
        )
        explanation = llm_explain(prompt) or (
            "This app lets you explore **5 TiVA-MoS indicators** from the OECD 2026 "
            "preliminary release across **82 economies**.\n\n"
            "**What you can ask:**\n"
            "- *Top 10 economies by Mode 3 services exports in 2023*\n"
            "- *Show mode shares for France*\n"
            "- *Which sectors have the highest Mode 3 to cross-border ratio?*\n"
            "- *Compare Germany, France and Italy for GVC participation*\n"
            "- *What does Mode 3 mean?*\n\n"
            "**Indicators available:** Domestic VA in Foreign Demand · Foreign VA in Domestic Demand · "
            "GVC Participation · VA in Manufacturing Export · Mode 3 / Cross-border Ratio by sector.\n\n"
            "**Modes of supply:** Mode 1/4 (cross-border), Mode 2 (consumption abroad), "
            "Mode 3 (commercial presence / foreign affiliates)."
        )
        return ChatResponse(answer=explanation, plan=plan)

    # ── define / terminology question ──────────────────────────────────────
    if plan.intent == "define":
        if plan.define_term:
            defn = METADATA_DEFINITIONS.get(plan.define_term, "")
            if defn:
                explanation = llm_explain(
                    f"User asked: {message}\n\nDefinition available:\n{defn}\n\n"
                    "Please explain this in 2-3 sentences in plain English."
                ) or defn
                return ChatResponse(answer=explanation, plan=plan)
        # Fall through to general LLM if no specific term matched
        explanation = llm_explain(message) or (
            "I could not find a specific definition in the dataset metadata. "
            "Please check the OECD TiVA-MoS documentation."
        )
        return ChatResponse(answer=explanation, plan=plan)

    # ── analytical query ───────────────────────────────────────────────────
    result_df, meta = execute_query_plan(plan)

    if result_df is None or result_df.empty:
        available_years = get_years(plan.dataset_name)
        available_geos = get_available_values("geo")[:10]
        answer = (
            f"No data found for your query.\n\n"
            f"**Dataset:** {meta['dataset_label']}\n"
            f"**Economy filter:** {meta['geo_label']}\n"
            f"**Year filter:** {meta['years']}\n\n"
            f"Available years: {available_years}\n"
            f"Sample economies: {', '.join(available_geos)}"
        )
        return ChatResponse(answer=answer, plan=plan)

    # Build result summary for LLM
    result_summary = result_df[["value"] + [c for c in
        ["country_name", "geo", "mode_name", "sector_name", "year"]
        if c in result_df.columns]].head(15).to_string(index=False)

    if plan.intent in ("time_series", "growth"):
        growth = get_growth(
            plan.dataset_name or "dmst_va_in_frgn_dmnd",
            geo=(plan.geo[0] if isinstance(plan.geo, list) else plan.geo) or "USA",
            mode_name=plan.mode_name,
            isic_code=plan.isic_code,
        )
        if growth["first_value"] is not None:
            prompt = EXPLAIN_GROWTH_TEMPLATE.format(
                question=message,
                dataset_label=meta["dataset_label"],
                geo_label=meta["geo_label"],
                mode_name=meta["mode_name"],
                **{k: v for k, v in growth.items() if k != "abs_change" or True},
                first_year=growth["first_year"],
                last_year=growth["last_year"],
                first_value=growth["first_value"] or 0,
                last_value=growth["last_value"] or 0,
                abs_change=growth["abs_change"] or 0,
                pct_change=growth["pct_change"] or 0,
            )
        else:
            prompt = EXPLAIN_RESULT_TEMPLATE.format(
                question=message, result_summary=result_summary, **meta
            )
    elif plan.intent == "top_n":
        ranking_text = result_df.head(plan.n).to_string(index=False)
        prompt = EXPLAIN_TOP_N_TEMPLATE.format(
            question=message,
            dataset_label=meta["dataset_label"],
            year=meta["years"],
            mode_name=meta["mode_name"],
            n=plan.n,
            unit=meta["unit"],
            ranking_text=ranking_text,
        )
    elif plan.intent == "mode_shares":
        shares_text = result_df[["mode_name", "value", "share_pct"]].to_string(index=False) \
            if "share_pct" in result_df.columns else result_df.to_string(index=False)
        prompt = EXPLAIN_MODE_SHARES_TEMPLATE.format(
            question=message,
            dataset_label=meta["dataset_label"],
            geo_label=meta["geo_label"],
            year=meta["years"],
            shares_text=shares_text,
        )
    else:
        prompt = EXPLAIN_RESULT_TEMPLATE.format(
            question=message, result_summary=result_summary, **meta
        )

    llm_text = llm_explain(prompt)

    if llm_text:
        answer = llm_text
    else:
        # Rule-based fallback answer
        top_row = result_df.iloc[0] if not result_df.empty else None
        if top_row is not None and "value" in top_row:
            val = f"{float(top_row['value']):.2f}"
            answer = (
                f"**{meta['dataset_label']}** — {meta['geo_label']}, "
                f"{meta['mode_name']}, {meta['years']}.\n\n"
                f"Top result: {val} {meta['unit']}. "
                f"Full results are shown in the table below.\n\n"
                f"*(LLM explanation unavailable — no API key configured.)*"
            )
        else:
            answer = (
                f"Query executed for **{meta['dataset_label']}**. "
                f"Results shown in the table below."
            )

    return ChatResponse(
        answer=answer,
        result_df=result_df,
        chart_type=plan.chart_type,
        plan=plan,
    )
