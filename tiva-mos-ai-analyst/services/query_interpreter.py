# -*- coding: utf-8 -*-
"""
Query interpreter — resolves natural language to structured analytical intent.
Uses YAML metadata for synonym resolution and intent detection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rapidfuzz import fuzz, process

from services.data_loader import ISO3_NAMES, ISIC_NAMES, DATASETS, get_available_values

# ── load metadata ──────────────────────────────────────────────────────────
_META_DIR = Path(__file__).parent.parent / "metadata"


def _load_yaml(name: str) -> dict:
    try:
        with open(_META_DIR / name, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


_SYNONYMS = _load_yaml("synonyms.yml")
_INDICATORS_META = _load_yaml("indicators.yml").get("indicators", {})


# ── structured query plan ──────────────────────────────────────────────────
@dataclass
class QueryPlan:
    raw_question: str = ""
    intent: str = "general"           # explain|rank|compare|trend|mode_shares|sector|policy|export|general
    dataset_name: str | None = None
    geo: list[str] = field(default_factory=list)
    mode_name: str | None = None
    isic_code: str | None = None
    year: int | None = None
    year_range: tuple[int, int] | None = None
    n: int = 10
    chart_type: str = "bar"
    is_ambiguous: bool = False
    ambiguity_message: str = ""
    define_term: str | None = None
    needs_policy: bool = False


# ── intent detection ───────────────────────────────────────────────────────
_INTENT_GROUPS: dict[str, list[str]] = _SYNONYMS.get("intents", {})

_POLICY_TERMS = {"policy", "implication", "interpret", "significance", "relevance",
                 "what does this mean", "why does this matter", "implications"}

_DEFINE_TERMS = {
    "mode 3": "Mode 3", "mode 1": "Mode 1/4", "mode 2": "Mode 2",
    "mode 4": "Mode 1/4", "mode 1/4": "Mode 1/4",
    "gats": "GATS", "tiva": "TiVA", "tiva-mos": "TiVA-MoS",
    "gvc": "GVC", "commercial presence": "Mode 3",
    "cross-border": "Mode 1/4", "consumption abroad": "Mode 2",
}


def classify_intent(message: str) -> str:
    msg = message.lower()
    # Check structured intent groups from YAML
    for intent, keywords in _INTENT_GROUPS.items():
        if any(kw in msg for kw in keywords):
            return intent
    return "general"


def detect_policy_request(message: str) -> bool:
    msg = message.lower()
    return any(t in msg for t in _POLICY_TERMS)


def detect_define_term(message: str) -> str | None:
    msg = message.lower()
    for term, canonical in _DEFINE_TERMS.items():
        if term in msg:
            return canonical
    return None


# ── entity extraction ──────────────────────────────────────────────────────

def resolve_indicator(message: str) -> str | None:
    msg = message.lower()
    syn_map: dict[str, str] = _SYNONYMS.get("indicators", {})
    for phrase, ds_name in syn_map.items():
        if phrase in msg:
            return ds_name
    # Fallback: check if any dataset label is mentioned
    for name, meta in DATASETS.items():
        if meta["label"].lower() in msg:
            return name
    # Default based on keywords
    if any(w in msg for w in ["export", "domestic va", "dva"]):
        return "dmst_va_in_frgn_dmnd"
    if any(w in msg for w in ["import", "foreign va", "fva"]):
        return "frgn_va_in_dmst_dmnd"
    return None


def resolve_geos(message: str) -> list[str]:
    found: list[str] = []
    # Direct ISO-3 codes
    upper = message.upper()
    for code in ISO3_NAMES:
        if re.search(rf"\b{code}\b", upper):
            found.append(code)
    # Full country name lookup
    name_to_iso = {v.lower(): k for k, v in ISO3_NAMES.items()}
    msg_lower = message.lower()
    for name, iso in name_to_iso.items():
        if name in msg_lower and iso not in found:
            found.append(iso)
    # Fuzzy fallback for partial names
    if not found:
        candidates = list(name_to_iso.keys())
        hits = process.extract(message.lower(), candidates,
                               scorer=fuzz.WRatio, limit=3, score_cutoff=75)
        for match_text, _score, _ in hits:
            iso = name_to_iso.get(match_text)
            if iso and iso not in found:
                found.append(iso)
    return found[:6]


def resolve_mode(message: str) -> str | None:
    msg = message.lower()
    mode_map: dict[str, str] = _SYNONYMS.get("modes", {})
    for phrase, canonical in mode_map.items():
        if phrase in msg:
            return canonical
    return None


def resolve_sector(message: str) -> str | None:
    msg = message.lower()
    sector_map: dict[str, str] = _SYNONYMS.get("sectors", {})
    for phrase, code in sector_map.items():
        if phrase in msg:
            return code
    # Direct ISIC code
    for code in ISIC_NAMES:
        if code.lower() in msg.upper():
            return code
    return None


def resolve_year(message: str) -> int | None:
    years = re.findall(r"\b(20\d{2}|199\d)\b", message)
    if years:
        return int(years[-1])
    return None


def resolve_year_range(message: str) -> tuple[int, int] | None:
    years = re.findall(r"\b(20\d{2}|199\d)\b", message)
    if len(years) >= 2:
        return int(years[0]), int(years[-1])
    return None


def resolve_n(message: str) -> int:
    match = re.search(r"\b(?:top|bottom)\s+(\d+)\b", message.lower())
    if match:
        return min(int(match.group(1)), 20)
    return 10


# ── chart type heuristics ──────────────────────────────────────────────────
_CHART_MAP = {
    "rank": "bar",
    "compare": "line",
    "trend": "line",
    "mode_shares": "stacked_bar",
    "sector": "bar",
    "policy": None,
    "explain": None,
    "export": None,
    "general": "bar",
}


# ── ambiguity detection ────────────────────────────────────────────────────
_VAGUE_PATTERNS = [
    (r"\bservices trade\b", "Do you mean services exports (Domestic VA in Foreign Demand), "
     "services imports (Foreign VA in Domestic Demand), or GVC participation?"),
    (r"\bservices\b(?!.*mode)(?!.*export)(?!.*import)", "Which aspect of services trade are you interested in? "
     "Exports, imports, value chain participation, or sector-level ratios?"),
    (r"\bshow.*data\b", "What data would you like to see? "
     "Please specify a country, mode, or indicator."),
]


def detect_ambiguity(message: str) -> tuple[bool, str]:
    msg = message.lower()
    # Ambiguous if no geo, no indicator, no mode
    geos = resolve_geos(message)
    indicator = resolve_indicator(message)
    mode = resolve_mode(message)
    intent = classify_intent(message)
    # Very short or very vague
    if len(msg.split()) <= 3 and intent == "general":
        return True, "Could you be more specific? For example: which indicator, country, year, or mode of supply?"
    for pattern, suggestion in _VAGUE_PATTERNS:
        if re.search(pattern, msg) and not indicator and not mode:
            return True, suggestion
    return False, ""


# ── main entry point ───────────────────────────────────────────────────────
def build_query_plan(message: str) -> QueryPlan:
    intent = classify_intent(message)
    dataset = resolve_indicator(message)
    geos = resolve_geos(message)
    mode = resolve_mode(message)
    isic = resolve_sector(message)
    year = resolve_year(message)
    year_range = resolve_year_range(message)
    n = resolve_n(message)
    define_term = detect_define_term(message)
    needs_policy = detect_policy_request(message)
    is_ambiguous, ambiguity_msg = detect_ambiguity(message)

    # Refine intent
    if define_term and intent not in ("rank", "compare", "trend"):
        intent = "explain"
    if len(geos) > 1 and intent not in ("trend",):
        intent = "compare"
    if isic and not dataset:
        dataset = "mos3_to_xborder_ratio"
    if not dataset:
        dataset = "dmst_va_in_frgn_dmnd"

    chart_type = _CHART_MAP.get(intent, "bar") or "bar"

    return QueryPlan(
        raw_question=message,
        intent=intent,
        dataset_name=dataset,
        geo=geos,
        mode_name=mode,
        isic_code=isic,
        year=year,
        year_range=year_range,
        n=n,
        chart_type=chart_type,
        is_ambiguous=is_ambiguous,
        ambiguity_message=ambiguity_msg,
        define_term=define_term,
        needs_policy=needs_policy or intent == "policy",
    )


def get_indicator_meta(dataset_name: str) -> dict:
    return _INDICATORS_META.get(dataset_name, {})
