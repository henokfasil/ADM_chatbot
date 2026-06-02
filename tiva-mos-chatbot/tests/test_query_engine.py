"""Tests for query engine functions."""
import pytest
import pandas as pd

from src.query_engine import (
    filter_data, get_time_series, get_top_n, get_growth,
    get_mode_shares, compare_countries, get_sector_ranking,
    fuzzy_match, get_years, get_available_values,
)


def test_filter_data_empty_filters():
    df = filter_data({})
    assert isinstance(df, pd.DataFrame)


def test_filter_data_by_dataset():
    df = filter_data({"dataset_name": "dmst_va_in_frgn_dmnd"})
    if not df.empty:
        assert (df["dataset_name"] == "dmst_va_in_frgn_dmnd").all()


def test_filter_data_unknown_returns_empty():
    df = filter_data({"dataset_name": "nonexistent_dataset_xyz"})
    assert df.empty


def test_filter_data_by_geo():
    df = filter_data({"dataset_name": "dmst_va_in_frgn_dmnd", "geo": "USA"})
    if not df.empty:
        assert (df["geo"] == "USA").all()


def test_get_top_n_returns_correct_size():
    df = get_top_n("dmst_va_in_frgn_dmnd", n=5)
    assert len(df) <= 5


def test_get_top_n_sorted_descending():
    df = get_top_n("dmst_va_in_frgn_dmnd", n=10)
    if len(df) > 1:
        assert df["value"].iloc[0] >= df["value"].iloc[-1]


def test_get_growth_structure():
    result = get_growth("dmst_va_in_frgn_dmnd", "USA")
    assert isinstance(result, dict)
    assert "first_year" in result
    assert "pct_change" in result


def test_get_growth_empty_geo():
    result = get_growth("dmst_va_in_frgn_dmnd", "ZZZ_NONEXISTENT")
    assert result["first_value"] is None


def test_get_mode_shares_has_share_col():
    df = get_mode_shares("dmst_va_in_frgn_dmnd", geo="FRA")
    if not df.empty:
        assert "share_pct" in df.columns
        assert abs(df["share_pct"].sum() - 100) < 0.5


def test_compare_countries_multiple_geos():
    df = compare_countries("dmst_va_in_frgn_dmnd", geos=["USA", "DEU", "FRA"])
    if not df.empty:
        assert df["geo"].nunique() >= 1


def test_get_sector_ranking():
    df = get_sector_ranking()
    assert isinstance(df, pd.DataFrame)


def test_fuzzy_match_country():
    results = fuzzy_match("United States", "geo")
    assert "USA" in results


def test_fuzzy_match_sector():
    results = fuzzy_match("telecom", "isic_code")
    assert "J61" in results


def test_get_years_returns_list():
    years = get_years()
    assert isinstance(years, list)
    assert all(isinstance(y, int) for y in years)


def test_available_values_geo():
    geos = get_available_values("geo")
    assert "USA" in geos
    assert "FRA" in geos
