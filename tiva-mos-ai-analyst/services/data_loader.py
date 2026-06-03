# -*- coding: utf-8 -*-
"""
Data loader service — reads TiVA-MoS CSVs, melts to canonical long format,
registers DuckDB views. Reuses the proven logic from the prototype.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv

log = logging.getLogger(__name__)

# ── paths ──────────────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE / ".env", override=False)
load_dotenv(_BASE / ".env.example", override=False)
load_dotenv(_BASE.parent / "tiva-mos-chatbot" / ".env", override=False)

TIVA_SOURCE = Path(os.getenv(
    "TIVA_DATA_DIR",
    str(_BASE.parent / "TiVA_indicators" / "2026_prel_update"),
))

# ── static lookups ─────────────────────────────────────────────────────────
ISO3_NAMES: dict[str, str] = {
    "AGO": "Angola", "ARE": "United Arab Emirates", "ARG": "Argentina",
    "AUS": "Australia", "AUT": "Austria", "BEL": "Belgium",
    "BGD": "Bangladesh", "BGR": "Bulgaria", "BLR": "Belarus",
    "BRA": "Brazil", "BRN": "Brunei Darussalam", "CAN": "Canada",
    "CHE": "Switzerland", "CHL": "Chile", "CHN": "China",
    "CIV": "Cote d'Ivoire", "CMR": "Cameroon", "COD": "Congo Dem. Rep.",
    "COL": "Colombia", "CRI": "Costa Rica", "CYP": "Cyprus",
    "CZE": "Czech Republic", "DEU": "Germany", "DNK": "Denmark",
    "EGY": "Egypt", "ESP": "Spain", "EST": "Estonia",
    "EU27": "European Union (27)", "FIN": "Finland", "FRA": "France",
    "GBR": "United Kingdom", "GRC": "Greece", "HKG": "Hong Kong SAR",
    "HRV": "Croatia", "HUN": "Hungary", "IDN": "Indonesia",
    "IND": "India", "IRL": "Ireland", "ISL": "Iceland",
    "ISR": "Israel", "ITA": "Italy", "JOR": "Jordan",
    "JPN": "Japan", "KAZ": "Kazakhstan", "KHM": "Cambodia",
    "KOR": "Korea", "LAO": "Lao PDR", "LTU": "Lithuania",
    "LUX": "Luxembourg", "LVA": "Latvia", "MAR": "Morocco",
    "MEX": "Mexico", "MLT": "Malta", "MMR": "Myanmar",
    "MYS": "Malaysia", "NGA": "Nigeria", "NLD": "Netherlands",
    "NOR": "Norway", "NZL": "New Zealand", "PAK": "Pakistan",
    "PER": "Peru", "PHL": "Philippines", "POL": "Poland",
    "PRT": "Portugal", "ROU": "Romania", "ROW": "Rest of World",
    "RUS": "Russia", "SAU": "Saudi Arabia", "SEN": "Senegal",
    "SGP": "Singapore", "STP": "Sao Tome and Principe", "SVK": "Slovak Republic",
    "SVN": "Slovenia", "SWE": "Sweden", "THA": "Thailand",
    "TUN": "Tunisia", "TUR": "Turkiye", "TWN": "Chinese Taipei",
    "UKR": "Ukraine", "USA": "United States", "VNM": "Viet Nam",
    "ZAF": "South Africa",
}

ISIC_NAMES: dict[str, str] = {
    "F41T43": "Construction",
    "G45T47": "Wholesale & retail trade",
    "H49": "Land transport",
    "H50": "Water transport",
    "H51": "Air transport",
    "H52": "Warehousing & logistics",
    "H53": "Postal & courier",
    "I55T56": "Accommodation & food services",
    "J58T60": "Publishing & broadcasting",
    "J61": "Telecommunications",
    "J62T63": "IT & computer services",
    "K64T66": "Financial & insurance services",
    "L68": "Real estate",
    "M69T75": "Professional & business services",
    "N77T82": "Administrative & support services",
    "P85": "Education",
    "Q86T88": "Health & social work",
    "R90T93": "Arts, entertainment & recreation",
    "S94T96": "Other personal services",
}

DATASETS: dict[str, dict] = {
    "dmst_va_in_frgn_dmnd": {
        "label": "Domestic VA in Foreign Demand",
        "code": "DVAFFD",
        "unit": "% of total services exports",
        "mode_cols": ["Mode 1/4", "Mode 2", "Mode 3"],
        "has_isic": False,
    },
    "frgn_va_in_dmst_dmnd": {
        "label": "Foreign VA in Domestic Demand",
        "code": "FVADD",
        "unit": "% of total services imports",
        "mode_cols": ["Mode 1/4", "Mode 2", "Mode 3"],
        "has_isic": False,
    },
    "gvc_participation": {
        "label": "GVC Participation",
        "code": "GVCPART",
        "unit": "% of gross exports",
        "mode_cols": [
            "Backward (Cross-border)", "Backward (Mode 3)",
            "Forward (Cross-border)", "Forward (Mode 3)",
        ],
        "has_isic": False,
    },
    "va_in_mnf_export": {
        "label": "VA in Manufacturing Export",
        "code": "VAMFG",
        "unit": "% of manufacturing exports",
        "mode_cols": [
            "Domestic content",
            "Foreign content (Mode 1/4)",
            "Foreign content (Mode 3)",
        ],
        "has_isic": False,
    },
    "mos3_to_xborder_ratio": {
        "label": "Mode 3 / Cross-border Ratio",
        "code": "M3RATIO",
        "unit": "ratio",
        "mode_cols": ["MOS3_to_xborder"],
        "has_isic": True,
    },
}


# ── helpers ────────────────────────────────────────────────────────────────
def _read_csv(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        return df
    except Exception as exc:
        log.warning("Cannot read %s: %s", path, exc)
        return None


def _melt(df: pd.DataFrame, name: str, mode_cols: list[str]) -> pd.DataFrame:
    id_vars = [c for c in df.columns if c not in mode_cols]
    long = df.melt(id_vars=id_vars, value_vars=mode_cols,
                   var_name="mode_name", value_name="value")
    long["dataset_name"] = name
    long["isic_code"] = None
    return long


def _load_mos3(df: pd.DataFrame, name: str) -> pd.DataFrame:
    out = df.rename(columns={"isic": "isic_code", "MOS3_to_xborder": "value"})
    out["dataset_name"] = name
    out["mode_name"] = "Mode 3 / Cross-border"
    return out


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    df["country_name"] = df["geo"].map(ISO3_NAMES).fillna(df["geo"])
    if "isic_code" in df.columns:
        df["sector_name"] = df["isic_code"].map(ISIC_NAMES).fillna(df["isic_code"])
    else:
        df["sector_name"] = None
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


# ── public API ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def load_all(source_dir: str | None = None) -> dict[str, pd.DataFrame]:
    src = Path(source_dir) if source_dir else TIVA_SOURCE
    frames: dict[str, pd.DataFrame] = {}
    for name, meta in DATASETS.items():
        path = src / f"{name}.csv"
        if not path.exists():
            log.warning("File not found: %s", path)
            continue
        raw = _read_csv(path)
        if raw is None or raw.empty:
            continue
        long = _load_mos3(raw, name) if meta["has_isic"] else _melt(raw, name, meta["mode_cols"])
        long = _enrich(long)
        frames[name] = long
        log.info("Loaded %s: %d rows", name, len(long))
    return frames


@lru_cache(maxsize=1)
def load_combined(source_dir: str | None = None) -> pd.DataFrame:
    frames = load_all(source_dir)
    if not frames:
        return pd.DataFrame()
    cols = ["dataset_name", "year", "geo", "country_name",
            "isic_code", "sector_name", "mode_name", "value"]
    parts = []
    for df in frames.values():
        for c in cols:
            if c not in df.columns:
                df[c] = None
        parts.append(df[cols])
    combined = pd.concat(parts, ignore_index=True)
    combined["year"] = combined["year"].astype("Int64")
    combined["value"] = pd.to_numeric(combined["value"], errors="coerce")
    return combined


_db: duckdb.DuckDBPyConnection | None = None


def get_db() -> duckdb.DuckDBPyConnection:
    global _db
    if _db is not None:
        return _db
    _db = duckdb.connect(":memory:")
    for name, df in load_all().items():
        _db.register(name, df)
    combined = load_combined()
    if not combined.empty:
        _db.register("tiva_all", combined)
    return _db


def is_data_available() -> bool:
    return bool(load_all())


def get_available_values(dimension: str, dataset_name: str | None = None) -> list:
    df = load_combined()
    if df.empty:
        return []
    if dataset_name:
        df = df[df["dataset_name"] == dataset_name]
    if dimension not in df.columns:
        return []
    return sorted(df[dimension].dropna().unique().tolist())


def get_years(dataset_name: str | None = None) -> list[int]:
    vals = get_available_values("year", dataset_name)
    return sorted([int(v) for v in vals if v is not None])
