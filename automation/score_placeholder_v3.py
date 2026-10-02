"""
Radar Institucional V3
Score Placeholder ? pre-enrichment validation boundary.

This module does NOT calculate Radar Score.

Its only responsibility is to provide a conservative,
schema-compatible transient score when an asset contains a
missing or incomplete V3 score before enrichment.

A complete V3 score is preserved exactly.
"""

from __future__ import annotations

import copy
from typing import Any, Dict


REQUIRED_V3_SCORE_FIELDS = frozenset(
    {
        "total",
        "fundamental",
        "technical",
        "momentum",
        "institutional_flow",
        "catalysts",
        "macro",
        "risk",
        "status",
        "raw_score",
        "available_score",
        "normalized_score",
        "coverage",
        "analytically_usable",
        "publishable",
    }
)


def build_score_placeholder() -> Dict[str, Any]:
    """
    Return a conservative schema-compatible transient score.

    Zero values here do not represent analytical neutral values.
    The placeholder explicitly declares INSUFFICIENT_DATA,
    zero coverage, non-usable and non-publishable state.
    """

    return {
        "total": 0,
        "fundamental": 0,
        "technical": 0,
        "momentum": 0,
        "institutional_flow": 0,
        "catalysts": 0,
        "macro": 0,
        "risk": 0,
        "status": "INSUFFICIENT_DATA",
        "raw_score": 0,
        "available_score": 0,
        "normalized_score": None,
        "coverage": 0,
        "analytically_usable": False,
        "publishable": False,
    }


def is_complete_v3_score(score: Any) -> bool:
    """
    Return True only when score contains every required V3 field.

    This is a structural completeness check, not a semantic or
    schema validation replacement.
    """

    if not isinstance(score, dict):
        return False

    return REQUIRED_V3_SCORE_FIELDS.issubset(
        score.keys()
    )


def prepare_score_placeholders(
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Return a deep-copied working document.

    Missing/incomplete asset scores are replaced with the
    conservative placeholder.

    Complete V3 scores are preserved exactly.

    The caller's input object is never mutated.
    """

    working = copy.deepcopy(data)

    assets = working.get("assets")

    if not isinstance(assets, list):
        return working

    for asset in assets:
        if not isinstance(asset, dict):
            continue

        score = asset.get("score")

        if is_complete_v3_score(score):
            continue

        asset["score"] = build_score_placeholder()

    return working
