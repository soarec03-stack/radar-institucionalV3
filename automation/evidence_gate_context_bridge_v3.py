"""Radar Institucional V3 - Evidence Gate Context Bridge.

Transport-only runtime adapter.

This module does not evaluate evidence, calculate upstream
results, mutate source objects or write public output.
"""

from typing import Any, Dict, Optional


def build_evidence_gate_runtime_inputs(
    radar: Dict[str, Any],
    publication_context_by_ticker: Optional[Dict[str, Any]] = None,
    risk_source_context_by_ticker: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Prepare transient inputs for apply_evidence_gate().

    The bridge preserves upstream values and missing evidence.
    It does not manufacture ticker contexts or infer eligibility.

    References are transported without copying or mutation.
    Consumers must treat the returned objects as read-only.
    """

    if not isinstance(radar, dict):
        raise TypeError("radar must be a dictionary")

    if publication_context_by_ticker is None:
        publication_context_by_ticker = {}

    if risk_source_context_by_ticker is None:
        risk_source_context_by_ticker = {}

    if not isinstance(publication_context_by_ticker, dict):
        raise TypeError(
            "publication_context_by_ticker must be a dictionary"
        )

    if not isinstance(risk_source_context_by_ticker, dict):
        raise TypeError(
            "risk_source_context_by_ticker must be a dictionary"
        )

    return {
        "radar": radar,
        "publication_context_by_ticker": publication_context_by_ticker,
        "risk_source_context_by_ticker": risk_source_context_by_ticker,
    }
