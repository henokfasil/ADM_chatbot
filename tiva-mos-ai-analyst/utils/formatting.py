# -*- coding: utf-8 -*-
"""Formatting utilities."""
from __future__ import annotations


def fmt_value(v: float | None, unit: str = "") -> str:
    if v is None:
        return "N/A"
    return f"{v:.2f}{' ' + unit if unit else ''}"


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "N/A"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"


def truncate(text: str, max_chars: int = 120) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."
