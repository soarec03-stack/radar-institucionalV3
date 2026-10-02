"""
Radar Institucional V3
Publication Eligibility Engine

Purpose
-------
Evaluate whether an analytically calculated Radar Score may be treated as
publication-eligible according to source governance.

This engine does not calculate Radar Score and does not promote analytical
publishability. It may only tighten an existing publishable=True state to
False.

Risk provenance is supplied as SIDECAR context and is never written into
asset.risk.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parent
    / "publication_eligibility_policy_v3.json"
)


def _load_default_policy() -> Dict[str, Any]:
    return json.loads(
        DEFAULT_POLICY_PATH.read_text(
            encoding="utf-8-sig"
        )
    )


def _registry_index(
    registry: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    return {
        item.get("id"): item
        for item in registry.get("sources", [])
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
    }


def _get_path(
    obj: Dict[str, Any],
    dotted_path: str,
) -> Any:
    current: Any = obj

    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

    return current


def _blocked(reason: str) -> Dict[str, Any]:
    return {
        "eligible": False,
        "reason": reason,
    }


def _allowed(
    source_id: str,
) -> Dict[str, Any]:
    return {
        "eligible": True,
        "reason": "ELIGIBLE",
        "source": source_id,
    }


def _source_eligibility(
    source_id: Any,
    registry_index: Dict[str, Dict[str, Any]],
    policy: Dict[str, Any],
    allowed_supports: Optional[list] = None,
    explicit_publication_use: Optional[str] = None,
) -> Dict[str, Any]:

    if not isinstance(source_id, str) or not source_id:
        return _blocked("MISSING_SOURCE")

    source = registry_index.get(source_id)

    if not isinstance(source, dict):
        return _blocked("UNKNOWN_SOURCE")

    publication_use = explicit_publication_use

    if publication_use is None:
        publication_use = source.get("publication_use")

    publication_use_policy = policy.get(
        "publication_use_policy",
        {},
    )

    if publication_use is not None:
        if publication_use not in publication_use_policy:
            return _blocked(
                f"UNKNOWN_PUBLICATION_USE_{publication_use}"
            )

        publication_action = publication_use_policy.get(
            publication_use
        )

        if publication_action != "ALLOW":
            return _blocked(
                f"PUBLICATION_USE_{publication_use}"
            )

    tier = source.get("tier")

    tier_action = (
        policy.get("tier_policy", {})
        .get(tier)
    )

    if tier_action != "ALLOW":
        return _blocked(
            f"TIER_NOT_ALLOWED_{tier}"
        )

    if allowed_supports:
        supported = set(source.get("supports", []))

        if not supported.intersection(
            set(allowed_supports)
        ):
            return _blocked(
                "UNSUPPORTED_COMPONENT_CAPABILITY"
            )

    return _allowed(source_id)


def _evaluate_data_component(
    asset: Dict[str, Any],
    component_policy: Dict[str, Any],
    registry_index: Dict[str, Dict[str, Any]],
    policy: Dict[str, Any],
) -> Dict[str, Any]:

    path = component_policy.get("data_path")

    if not isinstance(path, str):
        return _blocked("MISSING_DATA_PATH")

    point = _get_path(asset, path)

    if not isinstance(point, dict):
        return _blocked("MISSING_DATA_POINT")

    provenance = point.get("provenance")

    if not isinstance(provenance, dict):
        return _blocked("MISSING_PROVENANCE")

    if provenance.get("status") == "UNAVAILABLE":
        return _blocked("PROVENANCE_UNAVAILABLE")

    source_id = provenance.get("primary_source")

    return _source_eligibility(
        source_id,
        registry_index,
        policy,
        allowed_supports=component_policy.get(
            "allowed_supports"
        ),
    )


def _evaluate_risk(
    asset: Dict[str, Any],
    component_policy: Dict[str, Any],
    registry_index: Dict[str, Dict[str, Any]],
    policy: Dict[str, Any],
    risk_source_context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:

    risk = _get_path(
        asset,
        component_policy.get("data_path", "risk"),
    )

    if not isinstance(risk, dict):
        return _blocked("MISSING_RISK")

    if risk.get("score") is None:
        return _blocked("MISSING_RISK_SCORE")

    if not isinstance(risk_source_context, dict):
        return _blocked(
            "MISSING_RISK_SOURCE_CONTEXT"
        )

    source_context_policy = (
        component_policy.get("source_context", {})
    )

    required_context = (
        source_context_policy.get(
            "required_context",
            [],
        )
    )

    for field in required_context:
        if field not in risk_source_context:
            return _blocked(
                f"MISSING_RISK_CONTEXT_{field.upper()}"
            )

    ticker = risk_source_context.get("ticker")

    if ticker != asset.get("ticker"):
        return _blocked("RISK_TICKER_MISMATCH")

    source_context = risk_source_context.get("source")

    if not isinstance(source_context, dict):
        return _blocked(
            "INVALID_RISK_SOURCE_CONTEXT"
        )

    required_source_fields = (
        source_context_policy.get(
            "source_required_fields",
            [],
        )
    )

    for field in required_source_fields:
        value = source_context.get(field)

        if value is None or value == "":
            return _blocked(
                f"MISSING_RISK_SOURCE_{field.upper()}"
            )

    return _source_eligibility(
        source_context.get("primary_source"),
        registry_index,
        policy,
        explicit_publication_use=(
            source_context.get("publication_use")
        ),
    )


def evaluate_asset_publication(
    asset: Dict[str, Any],
    registry: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
    risk_source_context: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:

    if policy is None:
        policy = _load_default_policy()

    registry_index = _registry_index(registry)

    components_policy = policy.get(
        "components",
        {},
    )

    results: Dict[str, Dict[str, Any]] = {}

    for component_name in (
        "fundamental",
        "technical",
        "institutional_flow",
        "catalysts",
        "macro",
    ):
        component_policy = components_policy.get(
            component_name,
            {},
        )

        results[component_name] = (
            _evaluate_data_component(
                asset,
                component_policy,
                registry_index,
                policy,
            )
        )

    momentum_policy = components_policy.get(
        "momentum",
        {},
    )

    inherited = momentum_policy.get(
        "inherits_publication_from"
    )

    if inherited in results:
        results["momentum"] = copy.deepcopy(
            results[inherited]
        )
        results["momentum"][
            "inherited_from"
        ] = inherited
    else:
        results["momentum"] = _blocked(
            "INVALID_INHERITANCE"
        )

    results["risk"] = _evaluate_risk(
        asset,
        components_policy.get("risk", {}),
        registry_index,
        policy,
        risk_source_context,
    )

    eligible = all(
        result.get("eligible") is True
        for result in results.values()
    )

    return {
        "eligible": eligible,
        "components": results,
    }


def apply_publication_eligibility(
    data: Dict[str, Any],
    registry: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
    risk_source_context_by_ticker: Optional[
        Dict[str, Dict[str, Any]]
    ] = None,
):
    """
    Apply publication eligibility without promoting analytical state.

    Returns
    -------
    tuple
        (updated_data, changes)
    """

    if policy is None:
        policy = _load_default_policy()

    if risk_source_context_by_ticker is None:
        risk_source_context_by_ticker = {}

    changes = []

    for asset in data.get("assets", []):
        if not isinstance(asset, dict):
            continue

        ticker = asset.get("ticker")

        evaluation = evaluate_asset_publication(
            asset,
            registry,
            policy,
            risk_source_context=(
                risk_source_context_by_ticker.get(
                    ticker
                )
            ),
        )

        score = asset.get("score")

        if not isinstance(score, dict):
            continue

        previous_publishable = (
            score.get("publishable") is True
        )

        final_publishable = (
            previous_publishable
            and evaluation.get("eligible") is True
        )

        if previous_publishable != final_publishable:
            score["publishable"] = final_publishable

            if not final_publishable:
                score.pop("label", None)

            changes.append(
                {
                    "ticker": ticker,
                    "previous_publishable":
                        previous_publishable,
                    "publishable":
                        final_publishable,
                    "publication_eligibility":
                        evaluation,
                }
            )

    return data, changes
