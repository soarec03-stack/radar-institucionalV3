"""
Radar Institucional V3
Evidence Gate Engine

Phase: D.3D.3B

Responsibilities:
- Consume homologated upstream evidence.
- Classify evidence according to the Evidence Gate policy.
- Return a transient sidecar.
- Preserve fail-closed semantics.

Non-responsibilities:
- No upstream recalculation.
- No numeric decision thresholds.
- No conflict resolution.
- No Decision State selection.
- No Actionable Authority creation.
- No decision_center write.
- No asset/radar mutation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


GATE_RESULTS = {
    "ADMISSIBLE",
    "RESTRICTED",
    "BLOCKED",
    "INSUFFICIENT",
    "UNKNOWN",
}

BUCKET_BY_RESULT = {
    "ADMISSIBLE": "admissible_evidence",
    "RESTRICTED": "restricted_evidence",
    "BLOCKED": "blocked_evidence",
    "INSUFFICIENT": "insufficient_evidence",
    "UNKNOWN": "unknown_evidence",
}

CONFIDENCE_STATUSES = {
    "VERIFIED",
    "PARTIAL",
    "LOW",
    "UNAVAILABLE",
}

SCORE_STATUSES = {
    "CALCULATED",
    "PARTIAL",
    "INSUFFICIENT_DATA",
}

SIGNAL_STATUSES = {
    "CALCULATED",
    "INSUFFICIENT_COVERAGE",
    "UNAVAILABLE",
}


def _new_result(ticker: str) -> Dict[str, Any]:
    return {
        "ticker": ticker,
        "gate_status": "UNKNOWN",
        "evidence_gate_passed": False,
        "admissible_evidence": [],
        "restricted_evidence": [],
        "blocked_evidence": [],
        "insufficient_evidence": [],
        "unknown_evidence": [],
        "reasons": [],
    }


def _evidence_item(
    evidence_id: str,
    domain: str,
    information_class: str,
    gate_result: str,
    reason_code: str,
    **details: Any,
) -> Dict[str, Any]:
    item = {
        "evidence_id": evidence_id,
        "domain": domain,
        "information_class": information_class,
        "gate_result": gate_result,
        "reason_code": reason_code,
    }

    for key, value in details.items():
        if value is not None:
            item[key] = value

    return item


def _append_evidence(
    result: Dict[str, Any],
    item: Dict[str, Any],
) -> None:
    gate_result = item.get("gate_result")

    if gate_result not in GATE_RESULTS:
        gate_result = "UNKNOWN"
        item = dict(item)
        item["gate_result"] = "UNKNOWN"
        item["reason_code"] = "UNKNOWN_GATE_RESULT"

    bucket = BUCKET_BY_RESULT[gate_result]
    result[bucket].append(item)

    result["reasons"].append(
        {
            "reason_code": item["reason_code"],
            "domain": item["domain"],
            "information_class": item["information_class"],
            "gate_result": item["gate_result"],
        }
    )


def _classify_score(
    asset: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    score = asset.get("score")

    if not isinstance(score, dict):
        _append_evidence(
            result,
            _evidence_item(
                "score",
                "RADAR_SCORE",
                "MODEL",
                "INSUFFICIENT",
                "REQUIRED_SCORE_MISSING",
            ),
        )
        return

    status = score.get("status")

    if status not in SCORE_STATUSES:
        _append_evidence(
            result,
            _evidence_item(
                "score",
                "RADAR_SCORE",
                "MODEL",
                "UNKNOWN",
                "UNKNOWN_SCORE_STATUS",
                upstream_status=status,
            ),
        )
        return

    if status == "INSUFFICIENT_DATA":
        gate_result = "INSUFFICIENT"
        reason = "SCORE_INSUFFICIENT_DATA"

    elif status == "PARTIAL":
        gate_result = "RESTRICTED"
        reason = "SCORE_PARTIAL"

    elif score.get("analytically_usable") is not True:
        gate_result = "RESTRICTED"
        reason = "SCORE_NOT_ANALYTICALLY_USABLE"

    elif score.get("publishable") is not True:
        gate_result = "RESTRICTED"
        reason = "SCORE_NOT_PUBLISHABLE"

    else:
        gate_result = "ADMISSIBLE"
        reason = "SCORE_UPSTREAM_USABLE"

    _append_evidence(
        result,
        _evidence_item(
            "score",
            "RADAR_SCORE",
            "MODEL",
            gate_result,
            reason,
            upstream_status=status,
        ),
    )


def _classify_coverage(
    asset: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    score = asset.get("score")

    if not isinstance(score, dict):
        _append_evidence(
            result,
            _evidence_item(
                "score_coverage",
                "COVERAGE",
                "MODEL",
                "INSUFFICIENT",
                "REQUIRED_COVERAGE_MISSING",
            ),
        )
        return

    if "coverage" not in score:
        _append_evidence(
            result,
            _evidence_item(
                "score_coverage",
                "COVERAGE",
                "MODEL",
                "INSUFFICIENT",
                "REQUIRED_COVERAGE_MISSING",
            ),
        )
        return

    status = score.get("status")

    if status not in SCORE_STATUSES:
        gate_result = "UNKNOWN"
        reason = "UNKNOWN_SCORE_STATUS_FOR_COVERAGE"

    elif status == "INSUFFICIENT_DATA":
        gate_result = "INSUFFICIENT"
        reason = "UPSTREAM_COVERAGE_INSUFFICIENT"

    elif status == "PARTIAL":
        gate_result = "RESTRICTED"
        reason = "UPSTREAM_COVERAGE_PARTIAL"

    else:
        gate_result = "ADMISSIBLE"
        reason = "UPSTREAM_COVERAGE_USABLE"

    _append_evidence(
        result,
        _evidence_item(
            "score_coverage",
            "COVERAGE",
            "MODEL",
            gate_result,
            reason,
            upstream_status=status,
        ),
    )


def _classify_confidence(
    asset: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    confidence = asset.get("confidence")

    if not isinstance(confidence, dict):
        _append_evidence(
            result,
            _evidence_item(
                "confidence",
                "CONFIDENCE",
                "MODEL",
                "INSUFFICIENT",
                "REQUIRED_CONFIDENCE_MISSING",
            ),
        )
        return

    status = confidence.get("status")

    if status not in CONFIDENCE_STATUSES:
        gate_result = "UNKNOWN"
        reason = "UNKNOWN_CONFIDENCE_STATUS"

    elif status == "UNAVAILABLE":
        gate_result = "INSUFFICIENT"
        reason = "CONFIDENCE_UNAVAILABLE"

    elif status == "LOW":
        gate_result = "RESTRICTED"
        reason = "CONFIDENCE_LOW"

    elif status == "PARTIAL":
        gate_result = "RESTRICTED"
        reason = "CONFIDENCE_PARTIAL"

    else:
        gate_result = "ADMISSIBLE"
        reason = "CONFIDENCE_VERIFIED"

    _append_evidence(
        result,
        _evidence_item(
            "confidence",
            "CONFIDENCE",
            "MODEL",
            gate_result,
            reason,
            upstream_status=status,
        ),
    )


def _classify_publication(
    publication_context: Optional[Dict[str, Any]],
    result: Dict[str, Any],
) -> None:
    if publication_context is None:
        _append_evidence(
            result,
            _evidence_item(
                "publication_eligibility",
                "PUBLICATION_ELIGIBILITY",
                "MODEL",
                "RESTRICTED",
                "PUBLICATION_CONTEXT_NOT_PROVIDED",
            ),
        )
        return

    if not isinstance(publication_context, dict):
        _append_evidence(
            result,
            _evidence_item(
                "publication_eligibility",
                "PUBLICATION_ELIGIBILITY",
                "MODEL",
                "UNKNOWN",
                "INVALID_PUBLICATION_CONTEXT",
            ),
        )
        return

    eligible = publication_context.get("eligible")
    status = publication_context.get("status")

    if eligible is False:
        gate_result = "BLOCKED"
        reason = "PUBLICATION_INELIGIBLE"

    elif eligible is True:
        gate_result = "ADMISSIBLE"
        reason = "PUBLICATION_ELIGIBLE"

    else:
        gate_result = "UNKNOWN"
        reason = "UNKNOWN_PUBLICATION_ELIGIBILITY"

    _append_evidence(
        result,
        _evidence_item(
            "publication_eligibility",
            "PUBLICATION_ELIGIBILITY",
            "MODEL",
            gate_result,
            reason,
            publication_status=status,
        ),
    )


def _classify_risk(
    asset: Dict[str, Any],
    risk_source_context: Optional[Dict[str, Any]],
    result: Dict[str, Any],
) -> None:
    risk = asset.get("risk")

    if not isinstance(risk, dict):
        _append_evidence(
            result,
            _evidence_item(
                "risk",
                "RISK",
                "MODEL",
                "INSUFFICIENT",
                "RISK_MISSING",
            ),
        )
        return

    status = risk.get("status")

    if status in {"UNAVAILABLE", "INSUFFICIENT_DATA"}:
        gate_result = "INSUFFICIENT"
        reason = "RISK_UPSTREAM_INSUFFICIENT"

    elif status is None:
        # Some homologated upstream risk payloads expose the calculated
        # result without a dedicated status. Presence is consumed, not
        # recalculated.
        gate_result = "ADMISSIBLE"
        reason = "RISK_RESULT_PRESENT"

    elif status == "CALCULATED":
        gate_result = "ADMISSIBLE"
        reason = "RISK_CALCULATED"

    else:
        gate_result = "UNKNOWN"
        reason = "UNKNOWN_RISK_STATUS"

    if (
        isinstance(risk_source_context, dict)
        and risk_source_context.get("publication_eligible") is False
    ):
        gate_result = "BLOCKED"
        reason = "RISK_SOURCE_PUBLICATION_INELIGIBLE"

    _append_evidence(
        result,
        _evidence_item(
            "risk",
            "RISK",
            "MODEL",
            gate_result,
            reason,
            upstream_status=status,
        ),
    )


def _classify_signals(
    asset: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    signals = asset.get("signals")

    if signals is None:
        # Signals are an authorized domain, but absence is preserved
        # rather than silently converted into neutral evidence.
        _append_evidence(
            result,
            _evidence_item(
                "signals",
                "DOMAIN_SIGNALS",
                "MODEL",
                "INSUFFICIENT",
                "SIGNALS_MISSING",
            ),
        )
        return

    if not isinstance(signals, dict):
        _append_evidence(
            result,
            _evidence_item(
                "signals",
                "DOMAIN_SIGNALS",
                "MODEL",
                "UNKNOWN",
                "INVALID_SIGNALS_CONTAINER",
            ),
        )
        return

    if not signals:
        _append_evidence(
            result,
            _evidence_item(
                "signals",
                "DOMAIN_SIGNALS",
                "MODEL",
                "INSUFFICIENT",
                "SIGNALS_EMPTY",
            ),
        )
        return

    for signal_name, signal in signals.items():
        evidence_id = f"signal:{signal_name}"

        if not isinstance(signal, dict):
            _append_evidence(
                result,
                _evidence_item(
                    evidence_id,
                    "DOMAIN_SIGNALS",
                    "MODEL",
                    "UNKNOWN",
                    "INVALID_SIGNAL_PAYLOAD",
                ),
            )
            continue

        status = signal.get("status")

        if status not in SIGNAL_STATUSES:
            gate_result = "UNKNOWN"
            reason = "UNKNOWN_SIGNAL_STATUS"

        elif status == "UNAVAILABLE":
            gate_result = "INSUFFICIENT"
            reason = "SIGNAL_UNAVAILABLE"

        elif status == "INSUFFICIENT_COVERAGE":
            gate_result = "INSUFFICIENT"
            reason = "SIGNAL_INSUFFICIENT_COVERAGE"

        else:
            gate_result = "ADMISSIBLE"
            reason = "SIGNAL_CALCULATED"

        _append_evidence(
            result,
            _evidence_item(
                evidence_id,
                "DOMAIN_SIGNALS",
                "MODEL",
                gate_result,
                reason,
                upstream_status=status,
            ),
        )


def _classify_provenance(
    asset: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    provenance = asset.get("provenance")

    if not isinstance(provenance, dict):
        _append_evidence(
            result,
            _evidence_item(
                "provenance",
                "RADAR_SCORE",
                "FACT",
                "INSUFFICIENT",
                "REQUIRED_PROVENANCE_MISSING",
            ),
        )
        return

    price = provenance.get("price")

    if not isinstance(price, dict):
        _append_evidence(
            result,
            _evidence_item(
                "provenance:price",
                "RADAR_SCORE",
                "FACT",
                "INSUFFICIENT",
                "REQUIRED_PRICE_PROVENANCE_MISSING",
            ),
        )
        return

    status = price.get("status")

    if status == "VERIFIED":
        gate_result = "ADMISSIBLE"
        reason = "PRICE_PROVENANCE_VERIFIED"

    elif status == "UNAVAILABLE":
        gate_result = "INSUFFICIENT"
        reason = "PRICE_PROVENANCE_UNAVAILABLE"

    elif status in {"INVALID", "BLOCKED"}:
        gate_result = "BLOCKED"
        reason = "PRICE_PROVENANCE_INVALID"

    elif status in {"PARTIAL", "LOW"}:
        gate_result = "RESTRICTED"
        reason = "PRICE_PROVENANCE_RESTRICTED"

    else:
        gate_result = "UNKNOWN"
        reason = "UNKNOWN_PRICE_PROVENANCE_STATUS"

    _append_evidence(
        result,
        _evidence_item(
            "provenance:price",
            "RADAR_SCORE",
            "FACT",
            gate_result,
            reason,
            provenance_status=status,
            source_reference=price.get("source_id"),
        ),
    )


def _finalize_result(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    if result["unknown_evidence"]:
        gate_status = "UNKNOWN"

    elif result["blocked_evidence"]:
        gate_status = "BLOCKED"

    elif result["insufficient_evidence"]:
        gate_status = "INSUFFICIENT"

    elif result["restricted_evidence"]:
        gate_status = "RESTRICTED"

    elif result["admissible_evidence"]:
        gate_status = "PASSED"

    else:
        gate_status = "UNKNOWN"

    result["gate_status"] = gate_status
    result["evidence_gate_passed"] = gate_status == "PASSED"

    return result


def evaluate_asset_evidence(
    asset: Dict[str, Any],
    evidence_gate_policy: Dict[str, Any],
    publication_context: Optional[Dict[str, Any]] = None,
    risk_source_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Classify evidence for one asset.

    The function is intentionally non-mutating and fail-closed.
    """

    if not isinstance(asset, dict):
        result = _new_result("")
        _append_evidence(
            result,
            _evidence_item(
                "asset",
                "RADAR_SCORE",
                "FACT",
                "UNKNOWN",
                "INVALID_ASSET_PAYLOAD",
            ),
        )
        return _finalize_result(result)

    ticker = asset.get("ticker")

    if not isinstance(ticker, str):
        ticker = ""

    result = _new_result(ticker)

    if not isinstance(evidence_gate_policy, dict):
        _append_evidence(
            result,
            _evidence_item(
                "evidence_gate_policy",
                "RADAR_SCORE",
                "MODEL",
                "UNKNOWN",
                "INVALID_EVIDENCE_GATE_POLICY",
            ),
        )
        return _finalize_result(result)

    if (
        evidence_gate_policy.get("policy_id")
        != "RADAR_V3_EVIDENCE_GATE_POLICY"
    ):
        _append_evidence(
            result,
            _evidence_item(
                "evidence_gate_policy",
                "RADAR_SCORE",
                "MODEL",
                "UNKNOWN",
                "UNKNOWN_EVIDENCE_GATE_POLICY",
            ),
        )
        return _finalize_result(result)

    _classify_score(asset, result)
    _classify_coverage(asset, result)
    _classify_confidence(asset, result)
    _classify_publication(publication_context, result)
    _classify_risk(asset, risk_source_context, result)
    _classify_signals(asset, result)
    _classify_provenance(asset, result)

    return _finalize_result(result)


def apply_evidence_gate(
    radar: Dict[str, Any],
    evidence_gate_policy: Dict[str, Any],
    publication_context_by_ticker: Optional[Dict[str, Any]] = None,
    risk_source_context_by_ticker: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Evaluate Radar assets and return a transient ticker-keyed sidecar.

    radar and its assets are never mutated.
    """

    publication_context_by_ticker = (
        publication_context_by_ticker
        if isinstance(publication_context_by_ticker, dict)
        else {}
    )

    risk_source_context_by_ticker = (
        risk_source_context_by_ticker
        if isinstance(risk_source_context_by_ticker, dict)
        else {}
    )

    if not isinstance(radar, dict):
        return {}

    assets = radar.get("assets")

    if not isinstance(assets, list):
        return {}

    context: Dict[str, Dict[str, Any]] = {}

    for asset in assets:
        if not isinstance(asset, dict):
            continue

        ticker = asset.get("ticker")

        if not isinstance(ticker, str) or not ticker:
            continue

        context[ticker] = evaluate_asset_evidence(
            asset,
            evidence_gate_policy,
            publication_context_by_ticker.get(ticker),
            risk_source_context_by_ticker.get(ticker),
        )

    return context
