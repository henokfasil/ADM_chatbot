"""Tests for data loading and canonical schema."""
import pytest
import pandas as pd
from pathlib import Path

from src.data_loader import load_all, load_combined, schema_report
from src.config import TIVA_SOURCE


def test_source_dir_exists():
    assert TIVA_SOURCE.exists(), f"Data directory not found: {TIVA_SOURCE}"


def test_load_all_returns_dict():
    result = load_all()
    assert isinstance(result, dict)


def test_load_all_nonempty():
    result = load_all()
    assert len(result) > 0, "No datasets loaded — check TIVA_SOURCE path"


def test_canonical_columns_present():
    combined = load_combined()
    required = {"dataset_name", "year", "geo", "country_name", "value"}
    assert required.issubset(set(combined.columns)), (
        f"Missing columns: {required - set(combined.columns)}"
    )


def test_year_is_integer():
    combined = load_combined()
    assert pd.api.types.is_integer_dtype(combined["year"].dtype) or \
           combined["year"].dropna().apply(lambda x: float(x).is_integer()).all()


def test_value_is_numeric():
    combined = load_combined()
    assert pd.api.types.is_numeric_dtype(combined["value"])


def test_no_all_null_values():
    combined = load_combined()
    assert combined["value"].notna().any(), "All values are null"


def test_geo_codes_recognised():
    combined = load_combined()
    from src.config import ISO3_NAMES
    unknown = set(combined["geo"].unique()) - set(ISO3_NAMES.keys())
    assert len(unknown) == 0, f"Unrecognised geo codes: {unknown}"


def test_mos3_has_isic():
    frames = load_all()
    if "mos3_to_xborder_ratio" in frames:
        df = frames["mos3_to_xborder_ratio"]
        assert df["isic_code"].notna().any()


def test_wide_files_melted():
    """Wide files should have a mode_name column after melting."""
    frames = load_all()
    for name in ["dmst_va_in_frgn_dmnd", "frgn_va_in_dmst_dmnd"]:
        if name in frames:
            assert "mode_name" in frames[name].columns, f"{name} not melted"


def test_schema_report_runs():
    report = schema_report()
    assert isinstance(report, str)
    assert len(report) > 0
