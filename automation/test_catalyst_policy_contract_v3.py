from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


VERSION = "3.4I.3-B.2I.3"

BASE_DIR = Path(__file__).resolve().parent
POLICY_PATH = BASE_DIR / "catalyst_intelligence_policy_v3.json"
CONTRACT_PATH = BASE_DIR / "catalyst_event_contract_v3.json"


passed = 0
failed = 0


def load_json(path: Path) -> dict[str, Any]:
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


def main() -> int:
    print("=" * 72)
    print("CATALYST POLICY / CONTRACT REGRESSION V3")
    print(f"Test version: {VERSION}")
    print("=" * 72)

    try:
        policy = load_json(POLICY_PATH)
        contract = load_json(CONTRACT_PATH)
    except Exception as exc:
        print(f"[FATAL] Unable to load policy/contract: {exc}")
        return 2

    # ------------------------------------------------------------------
    # 1. Identity / version
    # ------------------------------------------------------------------

    check(
        policy.get("policy_name") == "CATALYST_INTELLIGENCE_POLICY",
        "Policy identity is authoritative.",
    )

    check(
        policy.get("policy_version") == "3.4I.1-B.2I.1",
        "Policy version is B.2I.1.",
    )

    check(
        contract.get("contract_name") == "CATALYST_EVENT_CONTRACT",
        "Contract identity is authoritative.",
    )

    check(
        contract.get("contract_version") == "3.4I.9B-B.2I.9B",
        "Contract version is B.2I.9B.",
    )

    check(
        policy.get("domain") == "catalysts"
        and contract.get("domain") == "catalysts",
        "Policy and contract use catalysts domain.",
    )

    # ------------------------------------------------------------------
    # 2. Core fail-closed principles
    # ------------------------------------------------------------------

    principles = policy.get("principles", {})

    required_true_principles = [
        "policy_before_code",
        "fail_closed",
        "missing_is_not_neutral",
        "missing_is_not_zero",
        "do_not_invent_events",
        "do_not_infer_unverified_facts",
        "headline_alone_is_not_sufficient",
        "narrative_alone_is_not_a_metric",
        "asset_specific_evidence_required",
        "source_provenance_required",
        "event_date_required",
        "future_event_must_be_explicitly_scheduled",
        "duplicate_events_must_not_double_count",
        "rumor_must_not_be_treated_as_verified_fact",
    ]

    check(
        all(principles.get(key) is True for key in required_true_principles),
        "All mandatory fail-closed principles are enabled.",
    )

    # ------------------------------------------------------------------
    # 3. Event types
    # ------------------------------------------------------------------

    event_types = policy.get("event_types", {})

    required_event_types = {
        "EARNINGS",
        "GUIDANCE",
        "REGULATORY",
        "CLINICAL",
        "PRODUCT",
        "CONTRACT",
        "PARTNERSHIP",
        "M_AND_A",
        "CAPITAL_ALLOCATION",
        "FINANCING",
        "LEGAL",
        "MANAGEMENT",
        "OPERATIONS",
        "CORPORATE_ACTION",
        "OTHER",
    }

    check(
        set(event_types.keys()) == required_event_types,
        "Policy defines exactly the canonical catalyst event types.",
    )

    check(
        event_types.get("OTHER", {}).get("enabled") is False,
        "OTHER event type is fail-closed by default.",
    )

    check(
        all(
            event_types.get(event_type, {}).get("enabled") is True
            for event_type in required_event_types
            if event_type != "OTHER"
        ),
        "All explicit canonical event types are enabled.",
    )

    # ------------------------------------------------------------------
    # 4. Direction semantics
    # ------------------------------------------------------------------

    direction = policy.get("direction", {})

    check(
        set(direction.get("allowed", []))
        == {"POSITIVE", "NEGATIVE", "NEUTRAL", "UNCERTAIN"},
        "Direction vocabulary is canonical.",
    )

    check(
        set(direction.get("score_eligible", []))
        == {"POSITIVE", "NEGATIVE", "NEUTRAL"},
        "Only deterministic directions are score eligible.",
    )

    check(
        direction.get("uncertain_is_score_eligible") is False,
        "UNCERTAIN direction is not score eligible.",
    )

    check(
        direction.get("direction_must_be_evidence_based") is True,
        "Direction must be evidence based.",
    )

    # ------------------------------------------------------------------
    # 5. Materiality
    # ------------------------------------------------------------------

    materiality = policy.get("materiality", {})
    levels = materiality.get("levels", {})

    expected_materiality_weights = {
        "LOW": 0.25,
        "MEDIUM": 0.50,
        "HIGH": 0.75,
        "CRITICAL": 1.00,
    }

    check(
        all(
            levels.get(level, {}).get("weight") == weight
            for level, weight in expected_materiality_weights.items()
        ),
        "Materiality weights are LOW=.25, MEDIUM=.50, HIGH=.75, CRITICAL=1.00.",
    )

    check(
        materiality.get("minimum_score_eligible") == "MEDIUM",
        "Minimum score-eligible materiality is MEDIUM.",
    )

    check(
        materiality.get("materiality_must_be_justified") is True,
        "Materiality must be justified.",
    )

    check(
        materiality.get("default_materiality_is_not_final_materiality") is True,
        "Default materiality cannot silently become final materiality.",
    )

    # ------------------------------------------------------------------
    # 6. Event status
    # ------------------------------------------------------------------

    event_status = policy.get("event_status", {})

    check(
        set(event_status.get("allowed", []))
        == {
            "SCHEDULED",
            "CONFIRMED",
            "COMPLETED",
            "CANCELLED",
            "UNVERIFIED",
        },
        "Event-status vocabulary is canonical.",
    )

    check(
        set(event_status.get("score_eligible", []))
        == {"SCHEDULED", "CONFIRMED", "COMPLETED"},
        "Only scheduled/confirmed/completed events may be score eligible.",
    )

    check(
        event_status.get("cancelled_is_score_eligible") is False
        and event_status.get("unverified_is_score_eligible") is False,
        "CANCELLED and UNVERIFIED events are fail-closed.",
    )

    # ------------------------------------------------------------------
    # 7. Source policy
    # ------------------------------------------------------------------

    source_policy = policy.get("source_policy", {})

    check(
        set(source_policy.get("allowed_registry_tiers", []))
        == {"TIER_1", "TIER_2", "TIER_3"},
        "Only TIER_1/TIER_2/TIER_3 are potentially usable.",
    )

    check(
        source_policy.get("tier_1", {}).get("score_eligible") is True
        and source_policy.get("tier_1", {}).get(
            "independent_confirmation_required"
        )
        is False,
        "TIER_1 is score eligible without mandatory independent confirmation.",
    )

    check(
        source_policy.get("tier_2", {}).get("score_eligible") is True
        and source_policy.get("tier_2", {}).get(
            "independent_confirmation_required"
        )
        is False,
        "TIER_2 is score eligible without mandatory independent confirmation.",
    )

    check(
        source_policy.get("tier_3", {}).get("score_eligible") is True
        and source_policy.get("tier_3", {}).get(
            "independent_confirmation_required"
        )
        is True,
        "TIER_3 requires independent confirmation.",
    )

    check(
        source_policy.get("tier_4", {}).get("score_eligible") is False,
        "TIER_4 is not score eligible.",
    )

    check(
        source_policy.get("unknown_source", {}).get("score_eligible")
        is False,
        "Unknown source is not score eligible.",
    )

    # ------------------------------------------------------------------
    # 8. Freshness
    # ------------------------------------------------------------------

    freshness = policy.get("freshness", {})

    check(
        freshness.get("reference") == "event_date",
        "Freshness is anchored to event_date.",
    )

    check(
        freshness.get("future_scheduled_events", {}).get(
            "maximum_days_ahead"
        )
        == 90,
        "Scheduled-event horizon is 90 days.",
    )

    check(
        freshness.get("completed_events", {}).get("maximum_age_days")
        == 30,
        "Default completed-event age is 30 days.",
    )

    overrides = freshness.get("event_type_overrides", {})

    check(
        all(
            overrides.get(event_type, {}).get("maximum_age_days") == 60
            for event_type in [
                "REGULATORY",
                "CLINICAL",
                "M_AND_A",
                "CORPORATE_ACTION",
            ]
        ),
        "Long-cycle catalyst overrides use 60-day validity.",
    )

    check(
        freshness.get("stale_event_is_score_eligible") is False,
        "Stale events are not score eligible.",
    )

    # ------------------------------------------------------------------
    # 9. Deduplication
    # ------------------------------------------------------------------

    dedup = policy.get("deduplication", {})

    check(
        dedup.get("enabled") is True
        and dedup.get("same_event_must_not_double_count") is True,
        "Catalyst deduplication is mandatory.",
    )

    check(
        dedup.get("identity_fields")
        == ["ticker", "event_type", "event_date", "event_key"],
        "Canonical deduplication identity fields are fixed.",
    )

    check(
        dedup.get(
            "multiple_sources_for_same_event_are_confirmation_not_new_events"
        )
        is True,
        "Multiple sources confirm one event rather than create new events.",
    )

    # ------------------------------------------------------------------
    # 10. Eligibility
    # ------------------------------------------------------------------

    eligibility = policy.get("eligibility", {})

    required_policy_fields = {
        "event_id",
        "ticker",
        "event_type",
        "event_status",
        "event_date",
        "direction",
        "materiality",
        "title",
        "evidence",
        "source",
    }

    check(
        set(eligibility.get("required_fields", []))
        == required_policy_fields,
        "Policy eligibility requires the canonical minimum fields.",
    )

    check(
        eligibility.get("minimum_materiality") == "MEDIUM",
        "Eligibility minimum materiality is MEDIUM.",
    )

    check(
        all(
            eligibility.get(key) is True
            for key in [
                "require_known_asset",
                "require_registered_source",
                "require_usable_source_quality",
                "require_temporal_validity",
                "require_direction_eligibility",
                "require_event_status_eligibility",
            ]
        ),
        "All catalyst eligibility gates are mandatory.",
    )

    # ------------------------------------------------------------------
    # 11. Output semantics
    # ------------------------------------------------------------------

    output = policy.get("output", {})

    check(
        output.get("eligible_status") == "ELIGIBLE"
        and output.get("suppressed_status") == "SUPPRESSED"
        and output.get("blocked_status") == "BLOCKED"
        and output.get("unavailable_status") == "UNAVAILABLE",
        "Output quality statuses are canonical.",
    )

    check(
        output.get("score_eligible_only_when_status") == "ELIGIBLE",
        "Only ELIGIBLE catalyst output may influence score.",
    )

    check(
        output.get("target_data_point") == "data_points.catalysts",
        "Catalyst target data point is data_points.catalysts.",
    )

    # ------------------------------------------------------------------
    # 12. Contract required fields
    # ------------------------------------------------------------------

    event_contract = contract.get("event", {})
    contract_required = set(event_contract.get("required", []))

    expected_contract_required = {
        "event_id",
        "event_key",
        "ticker",
        "event_type",
        "event_status",
        "event_date",
        "direction",
        "materiality",
        "title",
        "evidence",
        "source",
    }

    check(
        contract_required == expected_contract_required,
        "Event contract requires canonical raw-event fields.",
    )

    # Important cross-contract assertion:
    # event_key is mandatory in the canonical event contract because it is
    # required for deduplication, even though policy eligibility evaluates
    # the post-validation event.
    check(
        "event_key" in contract_required
        and "event_key" in dedup.get("identity_fields", []),
        "event_key is contract-required and participates in deduplication.",
    )

    # ------------------------------------------------------------------
    # 13. Contract enumerations match policy
    # ------------------------------------------------------------------

    fields = event_contract.get("fields", {})

    contract_event_types = set(
        fields.get("event_type", {}).get("values", [])
    )

    check(
        contract_event_types == required_event_types,
        "Contract event types match policy event types.",
    )

    check(
        set(fields.get("event_status", {}).get("values", []))
        == set(event_status.get("allowed", [])),
        "Contract event statuses match policy.",
    )

    check(
        set(fields.get("direction", {}).get("values", []))
        == set(direction.get("allowed", [])),
        "Contract directions match policy.",
    )

    check(
        set(fields.get("materiality", {}).get("values", []))
        == set(levels.keys()),
        "Contract materiality vocabulary matches policy.",
    )

    # ------------------------------------------------------------------
    # 14. Evidence / source contract
    # ------------------------------------------------------------------

    evidence = fields.get("evidence", {})

    check(
        evidence.get("nullable") is False
        and "fact" in evidence.get("required", []),
        "Evidence object is mandatory and requires a fact.",
    )

    source = fields.get("source", {})

    check(
        source.get("nullable") is False
        and set(source.get("required", []))
        == {"primary_source", "retrieved_at"},
        "Source object requires primary_source and retrieved_at.",
    )

    # ------------------------------------------------------------------
    # 15. Separation of responsibilities
    # ------------------------------------------------------------------

    responsibilities = contract.get(
        "separation_of_responsibilities", {}
    )

    check(
        "CALCULATE_NORMALIZED_CATALYST_SIGNAL"
        in responsibilities.get("signal_engine", []),
        "Signal Engine is authoritative for normalized catalyst signal.",
    )

    check(
        "CALCULATE_CATALYST_RADAR_POINTS"
        in responsibilities.get("score_engine", []),
        "Score Engine is authoritative for catalyst Radar points.",
    )

    forbidden_raw = set(
        contract.get("forbidden_raw_collector_outputs", [])
    )

    check(
        {
            "normalized_score",
            "radar_score",
            "radar_points",
            "confidence_score",
            "decision",
        }.issubset(forbidden_raw),
        "Raw collector cannot emit score/confidence/decision outputs.",
    )

    # ------------------------------------------------------------------
    # 16. Forbidden policy behavior
    # ------------------------------------------------------------------

    forbidden = set(policy.get("forbidden_behaviors", []))

    required_forbidden = {
        "INVENT_CATALYST",
        "CONVERT_HEADLINE_DIRECTLY_TO_SCORE",
        "TREAT_RUMOR_AS_VERIFIED_FACT",
        "USE_UNKNOWN_SOURCE_FOR_SCORE",
        "DOUBLE_COUNT_SAME_EVENT",
        "USE_STALE_EVENT_FOR_SCORE",
        "ASSUME_DIRECTION_WITHOUT_EVIDENCE",
        "ASSUME_MATERIALITY_WITHOUT_JUSTIFICATION",
        "CONVERT_MISSING_EVENT_TO_NEUTRAL",
        "CONVERT_MISSING_EVENT_TO_ZERO",
        "BYPASS_CONFIDENCE_ENGINE",
        "BYPASS_SIGNAL_ENGINE",
        "WRITE_RADAR_SCORE_DIRECTLY",
    }

    check(
        required_forbidden.issubset(forbidden),
        "All critical forbidden catalyst behaviors are explicitly blocked.",
    )

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    total = passed + failed

    print()
    print("=" * 72)
    print("B.2I.3 RESULT")
    print("=" * 72)
    print(f"Checks : {total}")
    print(f"Passed : {passed}")
    print(f"Failed : {failed}")
    print("RESULT :", "PASS" if failed == 0 else "FAIL")
    print("=" * 72)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

