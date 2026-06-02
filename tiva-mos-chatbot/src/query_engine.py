"""
All analytical queries against the TiVA-MoS data.
Every function returns a plain pandas DataFrame — no Streamlit dependencies.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from rapidfuzz import process, fuzz

from src.data_loader import load_all, load_combined
from src.config import DATASETS, ISO3_NAMES, ISIC_NAMES


# ── dimension helpers ─────────────────────────────────────────────────────────

def get_available_values(dimension: str, dataset_name: str | None = None) -> list[str]:
    """Return sorted unique values for a dimension across (optionally one) dataset."""
    combined = load_combined()
    if combined.empty:
        return []
    df = combined if dataset_name is None else combined[combined["dataset_name"] == dataset_name]
    if dimension not in df.columns:
        return []
    return sorted(df[dimension].dropna().unique().tolist())


def get_datasets() -> list[str]:
    return list(DATASETS.keys())


def get_countries() -> list[tuple[str, str]]:
    """Return list of (iso3, country_name) pairs present in loaded data."""
    geos = get_available_values("geo")
    return [(g, ISO3_NAMES.get(g, g)) for g in geos]


def get_sectors() -> list[tuple[str, str]]:
    isics = get_available_values("isic_code")
    return [(i, ISIC_NAMES.get(i, i)) for i in isics if i]


def get_modes(dataset_name: str | None = None) -> list[str]:
    return get_available_values("mode_name", dataset_name)


def get_years(dataset_name: str | None = None) -> list[int]:
    vals = get_available_values("year", dataset_name)
    return sorted([int(y) for y in vals if y is not None])


# ── filter validation ─────────────────────────────────────────────────────────

def validate_filters(filters: dict[str, Any]) -> dict[str, list[str]]:
    """
    Check that filter values exist in the data.
    Returns dict of dimension -> list of invalid values.
    """
    issues: dict[str, list[str]] = {}
    col_map = {
        "dataset_name": get_datasets(),
        "geo": get_available_values("geo"),
        "mode_name": get_available_values("mode_name"),
        "isic_code": get_available_values("isic_code"),
    }
    for key, valid in col_map.items():
        val = filters.get(key)
        if val is None:
            continue
        vals = [val] if isinstance(val, str) else val
        bad = [v for v in vals if v not in valid]
        if bad:
            issues[key] = bad
    return issues


# ── core filter ───────────────────────────────────────────────────────────────

def filter_data(filters: dict[str, Any]) -> pd.DataFrame:
    """
    Apply arbitrary filters to the combined dataset.
    Each key matches a column; values can be scalar or list.
    Skips a filter if the column has no non-null values (e.g. isic_code on non-sector datasets).
    """
    df = load_combined()
    if df.empty:
        return df

    for col, val in filters.items():
        if col not in df.columns or val is None:
            continue
        # Skip filter if column is entirely null for the current slice
        if df[col].isna().all():
            continue
        if isinstance(val, list):
            df = df[df[col].isin(val)]
        else:
            df = df[df[col] == val]
    return df.reset_index(drop=True)


# ── analytical queries ────────────────────────────────────────────────────────

def get_time_series(
    dataset_name: str,
    geo: str | list[str],
    mode_name: str | None = None,
    isic_code: str | None = None,
) -> pd.DataFrame:
    """Time-ordered values for one or more economies."""
    filters: dict[str, Any] = {"dataset_name": dataset_name, "geo": geo}
    if mode_name:
        filters["mode_name"] = mode_name
    if isic_code:
        filters["isic_code"] = isic_code
    df = filter_data(filters)
    return df.sort_values(["geo", "year"]).reset_index(drop=True)


def get_latest_value(
    dataset_name: str,
    geo: str,
    mode_name: str | None = None,
    isic_code: str | None = None,
) -> float | None:
    ts = get_time_series(dataset_name, geo, mode_name, isic_code)
    if ts.empty:
        return None
    latest_year = ts["year"].max()
    row = ts[ts["year"] == latest_year]
    return float(row["value"].iloc[0]) if not row.empty else None


def get_growth(
    dataset_name: str,
    geo: str,
    mode_name: str | None = None,
    isic_code: str | None = None,
) -> dict[str, float | None]:
    """
    Return absolute change and % change between first and last available years.
    """
    ts = get_time_series(dataset_name, geo, mode_name, isic_code)
    if ts.empty or ts["value"].isna().all():
        return {"first_year": None, "last_year": None, "first_value": None,
                "last_value": None, "abs_change": None, "pct_change": None}
    ts = ts.dropna(subset=["value"])
    first = ts.loc[ts["year"].idxmin()]
    last = ts.loc[ts["year"].idxmax()]
    v0, v1 = float(first["value"]), float(last["value"])
    abs_ch = v1 - v0
    pct_ch = (abs_ch / v0 * 100) if v0 != 0 else None
    return {
        "first_year": int(first["year"]),
        "last_year": int(last["year"]),
        "first_value": v0,
        "last_value": v1,
        "abs_change": abs_ch,
        "pct_change": pct_ch,
    }


def get_top_n(
    dataset_name: str,
    year: int | None = None,
    mode_name: str | None = None,
    isic_code: str | None = None,
    group_by: str = "geo",
    n: int = 10,
    ascending: bool = False,
) -> pd.DataFrame:
    """Rank economies (or sectors) by value for a given year/mode."""
    filters: dict[str, Any] = {"dataset_name": dataset_name}
    if year:
        filters["year"] = year
    if mode_name:
        filters["mode_name"] = mode_name
    if isic_code:
        filters["isic_code"] = isic_code
    df = filter_data(filters)
    if df.empty:
        return df

    agg_col = "country_name" if group_by == "geo" else group_by
    ranked = (
        df.groupby(agg_col, as_index=False)["value"]
        .mean()
        .sort_values("value", ascending=ascending)
    )
    return ranked.head(n).reset_index(drop=True)


def get_mode_shares(
    dataset_name: str,
    geo: str | list[str] | None = None,
    year: int | None = None,
    isic_code: str | None = None,
) -> pd.DataFrame:
    """
    Return value + share (%) of each mode for given geo/year.
    """
    filters: dict[str, Any] = {"dataset_name": dataset_name}
    if geo:
        filters["geo"] = geo
    if year:
        filters["year"] = year
    if isic_code:
        filters["isic_code"] = isic_code
    df = filter_data(filters)
    if df.empty:
        return df

    agg = df.groupby("mode_name", as_index=False)["value"].mean()
    total = agg["value"].sum()
    agg["share_pct"] = (agg["value"] / total * 100).round(2) if total else 0.0
    return agg.sort_values("value", ascending=False).reset_index(drop=True)


def compare_countries(
    dataset_name: str,
    geos: list[str],
    mode_name: str | None = None,
    isic_code: str | None = None,
    year: int | None = None,
) -> pd.DataFrame:
    """Return a side-by-side DataFrame for multiple economies."""
    filters: dict[str, Any] = {"dataset_name": dataset_name, "geo": geos}
    if mode_name:
        filters["mode_name"] = mode_name
    if isic_code:
        filters["isic_code"] = isic_code
    if year:
        filters["year"] = year
    df = filter_data(filters)
    return df.sort_values(["year", "geo"]).reset_index(drop=True)


def make_bilateral_matrix(
    dataset_name: str,
    year: int | None = None,
    mode_name: str | None = None,
) -> pd.DataFrame:
    """
    Pivot geo × mode into a matrix (geo rows, mode columns).
    Useful for heatmap rendering.
    """
    filters: dict[str, Any] = {"dataset_name": dataset_name}
    if year:
        filters["year"] = year
    if mode_name:
        filters["mode_name"] = mode_name
    df = filter_data(filters)
    if df.empty or "mode_name" not in df.columns:
        return df

    pivot = df.pivot_table(
        index="country_name", columns="mode_name", values="value", aggfunc="mean"
    ).reset_index()
    return pivot


def get_sector_ranking(
    year: int | None = None,
    geo: str | list[str] | None = None,
    n: int = 19,
    ascending: bool = False,
) -> pd.DataFrame:
    """Rank sectors by Mode 3 / cross-border ratio (mos3 dataset)."""
    filters: dict[str, Any] = {"dataset_name": "mos3_to_xborder_ratio"}
    if year:
        filters["year"] = year
    if geo:
        filters["geo"] = geo
    df = filter_data(filters)
    if df.empty:
        return df
    ranked = (
        df.groupby(["isic_code", "sector_name"], as_index=False)["value"]
        .mean()
        .sort_values("value", ascending=ascending)
    )
    return ranked.head(n).reset_index(drop=True)


# ── fuzzy matching ────────────────────────────────────────────────────────────

def fuzzy_match(user_text: str, dimension: str, threshold: int = 60) -> list[str]:
    """
    Return up to 5 dimension values that best match user_text.
    Searches both codes and display names.
    """
    candidates = get_available_values(dimension)
    if not candidates:
        return []

    # Build a combined lookup: display name -> code
    if dimension == "geo":
        lookup = {ISO3_NAMES.get(c, c): c for c in candidates}
    elif dimension == "isic_code":
        lookup = {ISIC_NAMES.get(c, c): c for c in candidates}
    else:
        lookup = {c: c for c in candidates}

    search_pool = list(lookup.keys()) + candidates
    matches = process.extract(user_text, search_pool, scorer=fuzz.WRatio,
                              limit=5, score_cutoff=threshold)
    seen: list[str] = []
    for match_text, _score, _ in matches:
        code = lookup.get(match_text, match_text)
        if code not in seen:
            seen.append(code)
    return seen
