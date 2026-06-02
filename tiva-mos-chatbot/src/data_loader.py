"""
Loads TiVA-MoS CSVs from 2026_prel_update, melts wide files to canonical
long format, enriches with country/sector names, and registers DuckDB views.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd

from src.config import (
    DATASETS,
    ISIC_NAMES,
    ISO3_NAMES,
    TIVA_SOURCE,
)

log = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _read_csv(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        return df
    except Exception as exc:
        log.warning("Could not read %s: %s", path, exc)
        return None


def _melt_wide(df: pd.DataFrame, dataset_name: str, mode_cols: list[str]) -> pd.DataFrame:
    """Melt wide-format file; return canonical long DataFrame."""
    id_vars = [c for c in df.columns if c not in mode_cols]
    long = df.melt(id_vars=id_vars, value_vars=mode_cols,
                   var_name="mode_name", value_name="value")
    long["dataset_name"] = dataset_name
    long["isic_code"] = None
    return long


def _load_mos3(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    """mos3_to_xborder_ratio is already long; standardise column names."""
    out = df.rename(columns={"isic": "isic_code", "MOS3_to_xborder": "value"})
    out["dataset_name"] = dataset_name
    out["mode_name"] = "Mode 3 / Cross-border"
    return out


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Add human-readable country and sector name columns."""
    df["country_name"] = df["geo"].map(ISO3_NAMES).fillna(df["geo"])
    if "isic_code" in df.columns:
        df["sector_name"] = df["isic_code"].map(ISIC_NAMES).fillna(df["isic_code"])
    else:
        df["sector_name"] = None
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


# ── public API ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_all(source_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """
    Load all datasets from source_dir (defaults to TIVA_SOURCE).
    Returns dict: dataset_name -> canonical long DataFrame.
    """
    src = Path(source_dir) if source_dir else TIVA_SOURCE

    frames: dict[str, pd.DataFrame] = {}
    for name, meta in DATASETS.items():
        path = src / f"{name}.csv"
        if not path.exists():
            log.warning("File not found, skipping: %s", path)
            continue

        raw = _read_csv(path)
        if raw is None or raw.empty:
            log.warning("Empty or unreadable: %s", path)
            continue

        if meta["has_isic"]:
            long = _load_mos3(raw, name)
        else:
            long = _melt_wide(raw, name, meta["mode_cols"])

        long = _enrich(long)
        frames[name] = long
        log.info("Loaded %s: %d rows", name, len(long))

    return frames


@lru_cache(maxsize=1)
def load_combined(source_dir: Path | None = None) -> pd.DataFrame:
    """
    Stack all datasets into one canonical DataFrame.
    Columns: dataset_name, year, geo, country_name, isic_code, sector_name,
             mode_name, value
    """
    frames = load_all(source_dir)
    if not frames:
        return _empty_canonical()

    canonical_cols = [
        "dataset_name", "year", "geo", "country_name",
        "isic_code", "sector_name", "mode_name", "value",
    ]
    parts = []
    for df in frames.values():
        for col in canonical_cols:
            if col not in df.columns:
                df[col] = None
        parts.append(df[canonical_cols])

    combined = pd.concat(parts, ignore_index=True)
    combined["year"] = combined["year"].astype("Int64")
    combined["value"] = pd.to_numeric(combined["value"], errors="coerce")
    return combined


def _empty_canonical() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "dataset_name", "year", "geo", "country_name",
        "isic_code", "sector_name", "mode_name", "value",
    ])


# ── DuckDB registration ───────────────────────────────────────────────────────

_con: duckdb.DuckDBPyConnection | None = None


def get_db(source_dir: Path | None = None) -> duckdb.DuckDBPyConnection:
    """
    Return a shared in-memory DuckDB connection with all dataset views registered.
    """
    global _con
    if _con is not None:
        return _con

    _con = duckdb.connect(":memory:")
    frames = load_all(source_dir)

    for name, df in frames.items():
        _con.register(name, df)
        log.info("Registered DuckDB view: %s", name)

    combined = load_combined(source_dir)
    if not combined.empty:
        _con.register("tiva_all", combined)
        log.info("Registered DuckDB view: tiva_all (%d rows)", len(combined))

    return _con


# ── schema report ─────────────────────────────────────────────────────────────

def schema_report(source_dir: Path | None = None) -> str:
    """Return a human-readable schema summary."""
    frames = load_all(source_dir)
    if not frames:
        return "No data loaded. Check that data files exist at: " + str(
            source_dir or TIVA_SOURCE
        )

    lines = ["## TiVA-MoS Data Schema Report\n"]
    for name, df in frames.items():
        meta = DATASETS.get(name, {})
        years = sorted(df["year"].dropna().unique().tolist())
        geos = sorted(df["geo"].dropna().unique().tolist())
        modes = (
            sorted(df["mode_name"].dropna().unique().tolist())
            if "mode_name" in df.columns else []
        )
        isics = (
            sorted(df["isic_code"].dropna().unique().tolist())
            if "isic_code" in df.columns and df["isic_code"].notna().any() else []
        )
        lines += [
            f"### {meta.get('label', name)} (`{name}`)",
            f"- Rows: {len(df):,}",
            f"- Years: {years}",
            f"- Economies: {len(geos)} ({', '.join(geos[:5])}{'...' if len(geos) > 5 else ''})",
            f"- Modes/components: {modes}",
        ]
        if isics:
            lines.append(f"- ISIC sectors: {len(isics)} ({', '.join(isics[:5])}...)")
        lines.append(
            f"- Missing values: {df['value'].isna().sum():,} / {len(df):,}\n"
        )

    return "\n".join(lines)
