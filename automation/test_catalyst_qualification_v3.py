from __future__ import annotations

import copy
import sys
from datetime import date
from pathlib import Path
from typing import Any


VERSION = "3.4I.5C-B.2I.5C"
REFERENCE_DATE = date(2026, 9, 27)

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import catalyst_event_validator_v3 as validator
import catalyst_qualification_v3 as qualification


passed = 0
failed = 0


def check(condition: bool, description: str) -> None:
    global passed, failed

    if condition:
        passed += 1
        print(f"[PASS] {description}")
    else:
        failed += 1
        print(f"[FAIL] {description}")


def has_reason(
    result: dict[str, Any],
    reason: str,
) -> bool:
    return reason in result.get("reasons", [])


def has_reason_prefix(
    result: dict[str, Any],
    prefix: str,
) -> bool:
    return any(
        isinstance(reason, str)
        and reason.startswith(prefix)
        for reason in result.get("reasons", [])
    )


def make_valid_event() -> dict[str, Any]:
    return {
        "event_id": "CAT-VRT-QUAL-001",
        "event_key": "vrt-guidance-20260927",
        "ticker": "VRT",
        "event_type": "GUIDANCE",
        "event_status": "CONFIRMED",
        "event_date": "2026-09-27",
        "announced_at": "2026-09-27T10:00:00-04:00",
        "direction": "POSITIVE",
        "direction_reason": (
            "Synthetic regression fixture with explicit "
            "direction justification."
        ),
        "materiality": "HIGH",
        "materiality_reason": (
            "Synthetic regression fixture with explicit "
            "materiality justification."
        ),
        "title": "Synthetic qualification regression event",
        "summary": (
            "Synthetic event used only for qualification tests."
        ),
        "evidence": {
            "fact": (
                "Synthetic confirmed guidance event used "
                "only for deterministic regression."
            ),
            "observed_value": 10.0,
            "expected_value": 8.0,
            "unit": "%"
        },
        "source": {
            "primary_source": "COMPANY_IR",
            "secondary_source": None,
            "source_url": None,
            "retrieved_at": "2026-09-27T10:05:00-04:00",
            "market_date": "2026-09-27"
        }
    }


def load_environment() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    set[str],
    set[str],
    dict[str, dict[str, Any]],
]:
    q_policy = qualification.load_json(
        qualification.DEFAULT_POLICY
    )

    event_policy = qualification.load_json(
        qualification.DEFAULT_EVENT_POLICY
    )

    contract = qualification.load_json(
        qualification.DEFAULT_CONTRACT
    )

    universe = qualification.load_json(
        qualification.DEFAULT_UNIVERSE
    )

    registry = qualification.load_json(
        qualification.DEFAULT_SOURCE_REGISTRY
    )

    known_tickers = validator.extract_known_tickers(
        universe
    )

    registered_sources = (
        validator.extract_registered_sources(
            registry
        )
    )

    sources = qualification.source_map(registry)

    return (
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )


def qualify(
    event: Any,
    q_policy: dict[str, Any],
    event_policy: dict[str, Any],
    contract: dict[str, Any],
    known_tickers: set[str],
    registered_sources: set[str],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return qualification.qualify_event(
        event=event,
        qualification_policy=q_policy,
        event_policy=event_policy,
        contract=contract,
        known_tickers=known_tickers,
        registered_sources=registered_sources,
        sources=sources,
        reference_date=REFERENCE_DATE,
    )


def main() -> int:
    print("=" * 72)
    print("CATALYST QUALIFICATION ENGINE REGRESSION V3")
    print(f"Test version  : {VERSION}")
    print(
        f"Reference date: "
        f"{REFERENCE_DATE.isoformat()}"
    )
    print("=" * 72)

    (
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    ) = load_environment()

    # ----------------------------------------------------------
    # 1. Environment bindings
    # ----------------------------------------------------------

    check(
        known_tickers == {"VRT", "CRSP", "ETON"},
        "Qualification engine uses canonical asset universe.",
    )

    check(
        len(registered_sources) == 13,
        "Qualification engine resolves all 13 registered sources.",
    )

    check(
        set(sources.keys()) == registered_sources,
        "Qualification source map matches validator registry binding.",
    )

    # ----------------------------------------------------------
    # 2. Canonical COMPANY_IR event
    # ----------------------------------------------------------

    base = make_valid_event()

    result = qualify(
        base,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "ELIGIBLE",
        "Canonical COMPANY_IR GUIDANCE event is ELIGIBLE.",
    )

    check(
        result["usable"] is True,
        "ELIGIBLE catalyst is usable.",
    )

    check(
        has_reason(
            result,
            "ALL_QUALIFICATION_GATES_PASSED",
        ),
        "Eligible catalyst records successful gate completion.",
    )

    # ----------------------------------------------------------
    # 3. Registered but unauthorized USER_PORTFOLIO
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["source"]["primary_source"] = "USER_PORTFOLIO"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "USER_PORTFOLIO catalyst evidence is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "PRIMARY_SOURCE_NOT_AUTHORIZED_FOR_EVENT_TYPE",
        ),
        "USER_PORTFOLIO is blocked by source authorization.",
    )

    # ----------------------------------------------------------
    # 4. YAHOO_FINANCE remains unauthorized
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["source"]["primary_source"] = "YAHOO_FINANCE"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "YAHOO_FINANCE catalyst evidence is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "PRIMARY_SOURCE_NOT_AUTHORIZED_FOR_EVENT_TYPE",
        ),
        "YAHOO_FINANCE is blocked before tier can imply authority.",
    )

    # ----------------------------------------------------------
    # 5. REUTERS TIER_2 is allowed
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["source"]["primary_source"] = "REUTERS"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "ELIGIBLE",
        "Authorized REUTERS TIER_2 event is ELIGIBLE.",
    )

    # ----------------------------------------------------------
    # 6. SEC authorized for GUIDANCE
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["source"]["primary_source"] = "SEC"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "ELIGIBLE",
        "Authorized SEC GUIDANCE event is ELIGIBLE.",
    )

    # ----------------------------------------------------------
    # 7. Source/event-type mismatch
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_type"] = "CLINICAL"
    event["source"]["primary_source"] = "SEC"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "SEC CLINICAL event is blocked by event-type authorization.",
    )

    check(
        has_reason(
            result,
            "PRIMARY_SOURCE_NOT_AUTHORIZED_FOR_EVENT_TYPE",
        ),
        "Source/event-type mismatch emits authorization reason.",
    )

    # ----------------------------------------------------------
    # 8. COMPANY_IR supports CLINICAL
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_type"] = "CLINICAL"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "ELIGIBLE",
        "COMPANY_IR CLINICAL event is ELIGIBLE.",
    )

    # ----------------------------------------------------------
    # 9. UNCERTAIN direction
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["direction"] = "UNCERTAIN"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "UNCERTAIN catalyst direction is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "DIRECTION_BLOCKED:UNCERTAIN",
        ),
        "UNCERTAIN direction emits canonical reason.",
    )

    # ----------------------------------------------------------
    # 10. Missing direction justification
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    del event["direction_reason"]

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "Missing direction justification is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "DIRECTION_REASON_REQUIRED",
        ),
        "Missing direction justification emits canonical reason.",
    )

    # ----------------------------------------------------------
    # 11. LOW materiality
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["materiality"] = "LOW"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "SUPPRESSED",
        "LOW materiality catalyst is SUPPRESSED.",
    )

    check(
        has_reason(
            result,
            "MATERIALITY_SUPPRESSED:LOW",
        ),
        "LOW materiality emits canonical suppression reason.",
    )

    # ----------------------------------------------------------
    # 12. Missing materiality justification
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    del event["materiality_reason"]

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "Missing materiality justification is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "MATERIALITY_REASON_REQUIRED",
        ),
        "Missing materiality justification emits canonical reason.",
    )

    # ----------------------------------------------------------
    # 13. CANCELLED status
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_status"] = "CANCELLED"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "SUPPRESSED",
        "CANCELLED catalyst is SUPPRESSED.",
    )

    check(
        has_reason(
            result,
            "EVENT_STATUS_SUPPRESSED:CANCELLED",
        ),
        "CANCELLED event emits canonical suppression reason.",
    )

    # ----------------------------------------------------------
    # 14. UNVERIFIED status
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_status"] = "UNVERIFIED"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "UNVERIFIED catalyst is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "EVENT_STATUS_BLOCKED:UNVERIFIED",
        ),
        "UNVERIFIED event emits canonical blocking reason.",
    )

    # ----------------------------------------------------------
    # 15. Future non-scheduled event
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_status"] = "CONFIRMED"
    event["event_date"] = "2026-09-28"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "Future non-scheduled catalyst is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "FUTURE_NON_SCHEDULED_EVENT",
        ),
        "Future non-scheduled event emits temporal reason.",
    )

    # ----------------------------------------------------------
    # 16. Scheduled event inside 90-day horizon
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_status"] = "SCHEDULED"
    event["event_date"] = "2026-12-20"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "ELIGIBLE",
        "Scheduled event inside 90-day horizon is ELIGIBLE.",
    )

    # ----------------------------------------------------------
    # 17. Scheduled event beyond 90 days
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_status"] = "SCHEDULED"
    event["event_date"] = "2027-01-15"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "SUPPRESSED",
        "Scheduled event beyond horizon is SUPPRESSED.",
    )

    check(
        has_reason(
            result,
            "FUTURE_SCHEDULED_BEYOND_HORIZON",
        ),
        "Beyond-horizon scheduled event emits temporal reason.",
    )

    # ----------------------------------------------------------
    # 18. Completed default event within 30 days
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_status"] = "COMPLETED"
    event["event_date"] = "2026-09-01"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "ELIGIBLE",
        "Completed default event inside 30 days is ELIGIBLE.",
    )

    # ----------------------------------------------------------
    # 19. Completed default event older than 30 days
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_status"] = "COMPLETED"
    event["event_date"] = "2026-08-20"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "SUPPRESSED",
        "Completed default event older than 30 days is SUPPRESSED.",
    )

    check(
        has_reason(
            result,
            "STALE_COMPLETED_EVENT",
        ),
        "Stale completed event emits canonical reason.",
    )

    # ----------------------------------------------------------
    # 20. Long-cycle CLINICAL within 60 days
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_type"] = "CLINICAL"
    event["event_status"] = "COMPLETED"
    event["event_date"] = "2026-08-15"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "ELIGIBLE",
        "CLINICAL completed event inside 60-day override is ELIGIBLE.",
    )

    # ----------------------------------------------------------
    # 21. Long-cycle CLINICAL beyond 60 days
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_type"] = "CLINICAL"
    event["event_status"] = "COMPLETED"
    event["event_date"] = "2026-07-20"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "SUPPRESSED",
        "CLINICAL event beyond 60-day override is SUPPRESSED.",
    )

    # ----------------------------------------------------------
    # 22. Structurally invalid event cannot be upgraded
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["ticker"] = "UNKNOWN"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "Structurally invalid event cannot be upgraded.",
    )

    check(
        has_reason_prefix(
            result,
            "UPSTREAM_VALIDATION:UNKNOWN_ASSET:",
        ),
        "Upstream validation failure is preserved in qualification.",
    )

    # ----------------------------------------------------------
    # 23. Unregistered source cannot be upgraded
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["source"]["primary_source"] = "FAKE_SOURCE"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "Unregistered source cannot be upgraded.",
    )

    check(
        has_reason_prefix(
            result,
            "UPSTREAM_VALIDATION:UNREGISTERED_SOURCE:",
        ),
        "Unregistered source failure is preserved.",
    )

    # ----------------------------------------------------------
    # 24. Duplicate event
    # ----------------------------------------------------------

    event_1 = copy.deepcopy(base)
    event_2 = copy.deepcopy(base)

    batch = qualification.qualify_events(
        events=[event_1, event_2],
        qualification_policy=q_policy,
        event_policy=event_policy,
        contract=contract,
        known_tickers=known_tickers,
        registered_sources=registered_sources,
        sources=sources,
        reference_date=REFERENCE_DATE,
    )

    check(
        batch["total_events"] == 2,
        "Duplicate batch retains two audit records.",
    )

    check(
        batch["eligible_events"] == 1,
        "First duplicate identity remains eligible.",
    )

    check(
        batch["suppressed_events"] == 1,
        "Second duplicate identity is suppressed.",
    )

    check(
        batch["results"][1]["status"]
        == "SUPPRESSED",
        "Duplicate event result is SUPPRESSED.",
    )

    check(
        has_reason(
            batch["results"][1],
            "DUPLICATE_EVENT",
        ),
        "Duplicate event emits canonical reason.",
    )

    # ----------------------------------------------------------
    # 25. Different event_key is not duplicate
    # ----------------------------------------------------------

    event_1 = copy.deepcopy(base)
    event_2 = copy.deepcopy(base)
    event_2["event_id"] = "CAT-VRT-QUAL-002"
    event_2["event_key"] = "vrt-guidance-20260927-b"

    batch = qualification.qualify_events(
        events=[event_1, event_2],
        qualification_policy=q_policy,
        event_policy=event_policy,
        contract=contract,
        known_tickers=known_tickers,
        registered_sources=registered_sources,
        sources=sources,
        reference_date=REFERENCE_DATE,
    )

    check(
        batch["eligible_events"] == 2,
        "Different event_key prevents false deduplication.",
    )

    check(
        batch["suppressed_events"] == 0,
        "Distinct event identities are not suppressed.",
    )

    # ----------------------------------------------------------
    # 26. B3 market-scope protection
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_type"] = "CORPORATE_ACTION"
    event["source"]["primary_source"] = "B3"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "B3 event without proven market scope is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "PRIMARY_SOURCE_MARKET_SCOPE_NOT_PROVEN",
        ),
        "B3 event requires explicit market scope.",
    )

    event["market_scope"] = "B3"

    result = qualify(
        event,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "ELIGIBLE",
        "B3 CORPORATE_ACTION with explicit B3 scope is ELIGIBLE.",
    )

    # ----------------------------------------------------------
    # 27. Synthetic TIER_3 confirmation semantics
    #
    # Current real TIER_3 source is intentionally unauthorized
    # for catalysts. We therefore mutate in-memory policy only,
    # without changing Source Registry or production policy.
    # ----------------------------------------------------------

    synthetic_policy = copy.deepcopy(q_policy)

    synthetic_policy[
        "source_authorization"
    ]["YAHOO_FINANCE"] = {
        "allowed_event_types": ["GUIDANCE"]
    }

    synthetic_policy[
        "explicitly_not_authorized"
    ] = [
        source_id
        for source_id in synthetic_policy.get(
            "explicitly_not_authorized",
            [],
        )
        if source_id != "YAHOO_FINANCE"
    ]

    event = copy.deepcopy(base)
    event["source"]["primary_source"] = "YAHOO_FINANCE"
    event["source"]["secondary_source"] = None

    result = qualify(
        event,
        synthetic_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "Synthetic authorized TIER_3 without confirmation is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "INDEPENDENT_CONFIRMATION_REQUIRED",
        ),
        "TIER_3 confirmation requirement is enforced.",
    )

    event["source"]["secondary_source"] = "COMPANY_IR"

    result = qualify(
        event,
        synthetic_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "ELIGIBLE",
        "Synthetic TIER_3 with authorized independent confirmation passes.",
    )

    # ----------------------------------------------------------
    # 28. Secondary source must differ
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["source"]["primary_source"] = "YAHOO_FINANCE"
    event["source"]["secondary_source"] = "YAHOO_FINANCE"

    result = qualify(
        event,
        synthetic_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "TIER_3 self-confirmation is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "SECONDARY_SOURCE_NOT_INDEPENDENT",
        ),
        "Self-confirmation emits independence failure.",
    )

    # ----------------------------------------------------------
    # 29. Secondary source must be authorized
    # ----------------------------------------------------------

    event = copy.deepcopy(base)
    event["source"]["primary_source"] = "YAHOO_FINANCE"
    event["source"]["secondary_source"] = "TRADINGVIEW"

    result = qualify(
        event,
        synthetic_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    check(
        result["status"] == "BLOCKED",
        "Unauthorized confirmation source is BLOCKED.",
    )

    check(
        has_reason(
            result,
            "SECONDARY_SOURCE_NOT_AUTHORIZED_FOR_EVENT_TYPE",
        ),
        "Unauthorized confirmation emits canonical reason.",
    )

    # ----------------------------------------------------------
    # 30. No score outputs
    # ----------------------------------------------------------

    result = qualify(
        base,
        q_policy,
        event_policy,
        contract,
        known_tickers,
        registered_sources,
        sources,
    )

    forbidden_outputs = {
        "normalized_score",
        "radar_score",
        "radar_points",
        "confidence_score",
        "decision",
    }

    check(
        forbidden_outputs.isdisjoint(
            result.keys()
        ),
        "Qualification output contains no score/confidence/decision fields.",
    )

    # ----------------------------------------------------------
    # Final
    # ----------------------------------------------------------

    total = passed + failed

    print()
    print("=" * 72)
    print("B.2I.5C QUALIFICATION ENGINE RESULT")
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