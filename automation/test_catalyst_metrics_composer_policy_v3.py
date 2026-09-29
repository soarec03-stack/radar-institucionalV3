from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


VERSION = "3.4I.6B-B.2I.6B"

BASE_DIR = Path(__file__).resolve().parent

COMPOSER_POLICY = (
    BASE_DIR / "catalyst_metrics_composer_policy_v3.json"
)

INTELLIGENCE_POLICY = (
    BASE_DIR / "catalyst_intelligence_policy_v3.json"
)

SOURCE_REGISTRY = (
    BASE_DIR / "source_registry_v3.json"
)

METRICS_CONTRACT = (
    BASE_DIR / "metrics_contract_v3.json"
)

SIGNAL_POLICY = (
    BASE_DIR / "signal_policy_v3.json"
)


passed = 0
failed = 0


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def check(condition: bool, description: str) -> None:
    global passed, failed

    if condition:
        passed += 1
        print(f"[PASS] {description}")
    else:
        failed += 1
        print(f"[FAIL] {description}")


def source_map(
    registry: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for source in registry.get("sources", []):
        if not isinstance(source, dict):
            continue

        source_id = source.get("id")

        if isinstance(source_id, str) and source_id:
            result[source_id] = source

    return result


def main() -> int:
    print("=" * 72)
    print("CATALYST METRICS COMPOSER POLICY REGRESSION V3")
    print(f"Test version: {VERSION}")
    print("=" * 72)

    policy = load_json(COMPOSER_POLICY)
    intelligence = load_json(INTELLIGENCE_POLICY)
    registry = load_json(SOURCE_REGISTRY)
    metrics = load_json(METRICS_CONTRACT)
    signal = load_json(SIGNAL_POLICY)

    sources = source_map(registry)

    # ----------------------------------------------------------
    # 1. Policy identity
    # ----------------------------------------------------------

    check(
        policy.get("policy_name")
        == "CATALYST_METRICS_COMPOSER_POLICY",
        "Composer policy identity is authoritative.",
    )

    check(
        policy.get("policy_version")
        == "3.4I.6A-B.2I.6A",
        "Composer policy version is B.2I.6A.",
    )

    check(
        policy.get("domain") == "catalysts",
        "Composer policy uses catalysts domain.",
    )

    # ----------------------------------------------------------
    # 2. Architectural principles
    # ----------------------------------------------------------

    principles = policy.get("principles", {})

    required_true = [
        "policy_before_code",
        "fail_closed",
        "eligible_events_only",
        "do_not_invent_probability",
        "do_not_invent_source_quality",
        "do_not_requalify_events",
        "do_not_calculate_normalized_score",
        "do_not_calculate_confidence",
        "do_not_calculate_radar_points",
        "signal_engine_remains_authoritative",
    ]

    check(
        all(
            principles.get(key) is True
            for key in required_true
        ),
        "All mandatory Composer principles are enabled.",
    )

    # ----------------------------------------------------------
    # 3. Input boundary
    # ----------------------------------------------------------

    input_policy = policy.get("input", {})

    check(
        input_policy.get(
            "required_qualification_status"
        )
        == "ELIGIBLE",
        "Composer accepts only ELIGIBLE qualified events.",
    )

    check(
        input_policy.get("event_contract")
        == "catalyst_event_contract_v3.json",
        "Composer references canonical Catalyst Event Contract.",
    )

    check(
        input_policy.get("qualification_policy")
        == "catalyst_qualification_policy_v3.json",
        "Composer references canonical qualification policy.",
    )

    # ----------------------------------------------------------
    # 4. Output contract
    # ----------------------------------------------------------

    output = policy.get("output", {})

    check(
        output.get("target_domain") == "catalysts",
        "Composer targets catalysts domain.",
    )

    expected_fields = {
        "description",
        "signed_impact",
        "probability",
        "source_quality",
        "horizon_days",
    }

    check(
        set(output.get("item_fields", []))
        == expected_fields,
        "Composer item fields exactly match structured Catalyst metrics.",
    )

    structure = output.get(
        "metrics_structure",
        {}
    ).get("items", {})

    check(
        structure.get("type") == "array"
        and structure.get("minimum_items") == 1,
        "Composer output requires at least one structured item.",
    )

    # ----------------------------------------------------------
    # 5. Metrics Contract compatibility
    # ----------------------------------------------------------

    catalyst_contract = (
        metrics.get("data_points", {})
        .get("catalysts", {})
    )

    catalyst_structure = catalyst_contract.get(
        "structure",
        {}
    )

    item_contract = catalyst_structure.get(
        "items",
        {}
    )

    check(
        isinstance(item_contract, dict)
        and item_contract.get("type") == "array",
        (
            "Metrics Contract defines "
            "data_points.catalysts.structure.items as array."
        ),
    )

    item_fields = item_contract.get(
        "item",
        {}
    )

    check(
        isinstance(item_fields, dict),
        "Catalyst item contract is structurally available.",
    )

    check(
        set(item_fields.keys())
        == {
            "description",
            "signed_impact",
            "probability",
            "source_quality",
            "horizon_days",
        },
        "Metrics Contract Catalyst item fields are canonical.",
    )

    check(
        item_fields.get(
            "signed_impact",
            {}
        ).get("min") == -100
        and item_fields.get(
            "signed_impact",
            {}
        ).get("max") == 100,
        "Metrics Contract signed_impact range is -100..100.",
    )

    check(
        item_fields.get(
            "probability",
            {}
        ).get("min") == 0
        and item_fields.get(
            "probability",
            {}
        ).get("max") == 1,
        "Metrics Contract probability range is 0..1.",
    )

    check(
        item_fields.get(
            "source_quality",
            {}
        ).get("min") == 0
        and item_fields.get(
            "source_quality",
            {}
        ).get("max") == 1,
        "Metrics Contract source_quality range is 0..1.",
    )

    check(
        item_fields.get(
            "horizon_days",
            {}
        ).get("min") == 0,
        "Metrics Contract horizon_days cannot be negative.",
    )

    # ----------------------------------------------------------
    # 6. Signal Policy compatibility
    # ----------------------------------------------------------

    catalyst_signal = (
        signal.get("domains", {})
        .get("catalysts", {})
    )

    signal_fields = set(
        catalyst_signal.get(
            "item_fields",
            {}
        ).values()
    )

    check(
        {
            "signed_impact",
            "probability",
            "source_quality",
            "horizon_days",
        }.issubset(signal_fields),
        "Composer numeric fields match Signal Engine contract.",
    )

    check(
        catalyst_signal.get(
            "horizon_decay_days"
        )
        == 180,
        "Signal Policy remains authoritative for 180-day decay.",
    )

    check(
        catalyst_signal.get("neutral") == 50,
        "Signal Policy retains Catalyst neutral reference at 50.",
    )

    # ----------------------------------------------------------
    # 7. Materiality source and exact weights
    # ----------------------------------------------------------

    materiality = intelligence.get(
        "materiality",
        {}
    )

    levels = materiality.get("levels", {})

    expected_weights = {
        "LOW": 0.25,
        "MEDIUM": 0.50,
        "HIGH": 0.75,
        "CRITICAL": 1.00,
    }

    actual_weights = {
        key: value.get("weight")
        for key, value in levels.items()
        if isinstance(value, dict)
    }

    check(
        actual_weights == expected_weights,
        "Canonical materiality weights remain unchanged.",
    )

    impact = policy.get("signed_impact", {})

    check(
        impact.get("materiality_source")
        == (
            "catalyst_intelligence_policy_v3.json."
            "materiality.levels"
        ),
        "Composer derives materiality from canonical policy.",
    )

    check(
        impact.get("direction_factor")
        == {
            "POSITIVE": 1,
            "NEUTRAL": 0,
            "NEGATIVE": -1,
        },
        "Direction factors are deterministic.",
    )

    check(
        impact.get("range") == [-100, 100],
        "signed_impact range matches existing metrics contract.",
    )

    expected_examples = {
        "POSITIVE_MEDIUM": 50,
        "POSITIVE_HIGH": 75,
        "POSITIVE_CRITICAL": 100,
        "NEUTRAL_MEDIUM": 0,
        "NEUTRAL_HIGH": 0,
        "NEUTRAL_CRITICAL": 0,
        "NEGATIVE_MEDIUM": -50,
        "NEGATIVE_HIGH": -75,
        "NEGATIVE_CRITICAL": -100,
    }

    check(
        impact.get("examples")
        == expected_examples,
        "signed_impact examples exactly encode direction x materiality.",
    )

    # ----------------------------------------------------------
    # 8. Probability semantics
    # ----------------------------------------------------------

    probability = policy.get(
        "probability",
        {}
    )

    check(
        probability.get("range") == [0, 1],
        "Probability range is 0..1.",
    )

    by_status = probability.get(
        "by_event_status",
        {}
    )

    check(
        by_status.get(
            "COMPLETED",
            {}
        ).get("value")
        == 1.0,
        "COMPLETED event probability is deterministic at 1.0.",
    )

    check(
        by_status.get(
            "CONFIRMED",
            {}
        ).get("value")
        == 1.0,
        "CONFIRMED event probability is deterministic at 1.0.",
    )

    scheduled = by_status.get(
        "SCHEDULED",
        {}
    )

    check(
        scheduled.get("value") is None,
        "SCHEDULED event has no invented default probability.",
    )

    check(
        scheduled.get("derivation")
        == "OBSERVABLE_EVENT_PROBABILITY_REQUIRED",
        "SCHEDULED probability requires observable evidence.",
    )

    check(
        scheduled.get("missing_action")
        == "SUPPRESS_FROM_METRICS",
        "SCHEDULED event without probability is suppressed.",
    )

    forbidden_probability = set(
        probability.get("forbidden", [])
    )

    check(
        {
            "DERIVE_FROM_SOURCE_TIER",
            "DERIVE_FROM_MATERIALITY",
            "DERIVE_FROM_DIRECTION",
            "ASSIGN_DEFAULT_TO_SCHEDULED",
        }.issubset(forbidden_probability),
        "Arbitrary probability derivations are explicitly forbidden.",
    )

    # ----------------------------------------------------------
    # 9. Source quality semantics
    # ----------------------------------------------------------

    source_quality = policy.get(
        "source_quality",
        {}
    )

    check(
        source_quality.get("range") == [0, 1],
        "Source quality range is 0..1.",
    )

    check(
        source_quality.get("registry")
        == "source_registry_v3.json",
        "Source quality uses canonical Source Registry.",
    )

    check(
        source_quality.get("field")
        == "authority_score",
        "Source quality derives from authority_score.",
    )

    check(
        source_quality.get("primary_source_only")
        is True,
        "Composer uses primary source for item source_quality.",
    )

    check(
        source_quality.get("missing_action")
        == "SUPPRESS_FROM_METRICS",
        "Missing source authority suppresses item.",
    )

    check(
        source_quality.get(
            "do_not_use_confidence_engine_score"
        )
        is True,
        "Composer does not reuse Confidence Engine score as source quality.",
    )

    expected_source_quality = {
        "B3": 1.00,
        "SEC": 1.00,
        "COMPANY_IR": 0.95,
        "REUTERS": 0.92,
    }

    actual_source_quality = {
        source_id: sources.get(
            source_id,
            {}
        ).get("authority_score")
        for source_id
        in expected_source_quality
    }

    check(
        actual_source_quality
        == expected_source_quality,
        "Authorized Catalyst source authority scores are deterministic.",
    )

    check(
        all(
            isinstance(value, (int, float))
            and 0 <= value <= 1
            for value
            in actual_source_quality.values()
        ),
        "Authorized Catalyst source quality values are valid 0..1.",
    )

    # ----------------------------------------------------------
    # 10. Horizon semantics
    # ----------------------------------------------------------

    horizon = policy.get(
        "horizon_days",
        {}
    )

    check(
        horizon.get("minimum") == 0,
        "horizon_days cannot be negative.",
    )

    check(
        horizon.get("reference")
        == "qualification_reference_date",
        "horizon_days is anchored to qualification reference date.",
    )

    horizon_rules = horizon.get(
        "rules",
        {}
    )

    check(
        horizon_rules.get("SCHEDULED")
        == "max(0, event_date - reference_date)",
        "SCHEDULED horizon is derived from event date.",
    )

    check(
        horizon_rules.get("CONFIRMED") == 0
        and horizon_rules.get("COMPLETED") == 0,
        "Confirmed/completed events have zero future horizon.",
    )

    check(
        horizon.get(
            "signal_engine_decay_authority"
        )
        == (
            "signal_policy_v3.json.domains."
            "catalysts.horizon_decay_days"
        ),
        "Composer delegates temporal decay to Signal Engine.",
    )

    # ----------------------------------------------------------
    # 11. Description semantics
    # ----------------------------------------------------------

    description = policy.get(
        "description",
        {}
    )

    check(
        description.get("source")
        == "event.title",
        "Catalyst item description uses event title.",
    )

    check(
        description.get("fallback")
        == "event.evidence.fact",
        "Evidence fact is the deterministic description fallback.",
    )

    check(
        description.get("must_not_invent_text")
        is True,
        "Composer cannot invent Catalyst description text.",
    )

    # ----------------------------------------------------------
    # 12. Aggregation boundary
    # ----------------------------------------------------------

    aggregation = policy.get(
        "aggregation",
        {}
    )

    check(
        aggregation.get(
            "one_eligible_event_produces_one_item"
        )
        is True,
        "Each eligible event maps to one structured item.",
    )

    check(
        aggregation.get(
            "do_not_preaggregate_signed_impact"
        )
        is True,
        "Composer cannot pre-aggregate signed impact.",
    )

    check(
        aggregation.get("do_not_average_events")
        is True,
        "Composer cannot average events.",
    )

    check(
        aggregation.get("do_not_apply_time_decay")
        is True,
        "Composer cannot apply time decay.",
    )

    check(
        aggregation.get(
            "do_not_apply_source_quality_weight"
        )
        is True,
        "Composer cannot pre-apply source-quality weighting.",
    )

    check(
        aggregation.get(
            "signal_engine_performs_weighting"
        )
        is True,
        "Signal Engine remains weighting authority.",
    )

    # ----------------------------------------------------------
    # 13. Boundary statuses
    # ----------------------------------------------------------

    boundary = policy.get("boundary", {})

    check(
        boundary.get("composer_statuses")
        == [
            "READY",
            "SUPPRESSED",
            "BLOCKED",
        ],
        "Composer boundary statuses are canonical.",
    )

    check(
        all(
            isinstance(boundary.get(status), str)
            and boundary.get(status)
            for status in (
                "READY",
                "SUPPRESSED",
                "BLOCKED",
            )
        ),
        "All Composer statuses have explicit semantics.",
    )

    # ----------------------------------------------------------
    # 14. Forbidden outputs
    # ----------------------------------------------------------

    forbidden_outputs = set(
        policy.get("forbidden_outputs", [])
    )

    check(
        forbidden_outputs
        == {
            "normalized_score",
            "confidence_score",
            "radar_score",
            "radar_points",
            "decision",
        },
        "Composer explicitly forbids downstream analytical outputs.",
    )

    # ----------------------------------------------------------
    # Final
    # ----------------------------------------------------------

    total = passed + failed

    print()
    print("=" * 72)
    print("B.2I.6B COMPOSER POLICY RESULT")
    print("=" * 72)
    print(f"Checks : {total}")
    print(f"Passed : {passed}")
    print(f"Failed : {failed}")
    print(
        "RESULT :",
        "PASS" if failed == 0 else "FAIL",
    )
    print("=" * 72)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())