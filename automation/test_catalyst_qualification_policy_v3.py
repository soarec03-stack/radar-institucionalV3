from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


VERSION = "3.4I.5A-B.2I.5A"

BASE_DIR = Path(__file__).resolve().parent

QUALIFICATION_POLICY = (
    BASE_DIR / "catalyst_qualification_policy_v3.json"
)
INTELLIGENCE_POLICY = (
    BASE_DIR / "catalyst_intelligence_policy_v3.json"
)
EVENT_CONTRACT = (
    BASE_DIR / "catalyst_event_contract_v3.json"
)
SOURCE_REGISTRY = (
    BASE_DIR / "source_registry_v3.json"
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

        if isinstance(source_id, str) and source_id.strip():
            result[source_id.strip()] = source

    return result


def main() -> int:
    print("=" * 72)
    print("CATALYST QUALIFICATION POLICY REGRESSION V3")
    print(f"Test version: {VERSION}")
    print("=" * 72)

    qualification = load_json(QUALIFICATION_POLICY)
    intelligence = load_json(INTELLIGENCE_POLICY)
    contract = load_json(EVENT_CONTRACT)
    registry = load_json(SOURCE_REGISTRY)

    sources = source_map(registry)

    authorized = set(
        qualification.get(
            "source_authorization",
            {},
        ).keys()
    )

    denied = set(
        qualification.get(
            "explicitly_not_authorized",
            [],
        )
    )

    registered = set(sources.keys())

    # --------------------------------------------------------------
    # 1. Policy identity
    # --------------------------------------------------------------

    check(
        qualification.get("policy_name")
        == "CATALYST_QUALIFICATION_POLICY",
        "Qualification policy identity is authoritative.",
    )

    check(
        qualification.get("policy_version")
        == "3.4I.5-B.2I.5",
        "Qualification policy version is B.2I.5.",
    )

    check(
        qualification.get("domain") == "catalysts",
        "Qualification policy uses catalysts domain.",
    )

    # --------------------------------------------------------------
    # 2. Fail-closed principles
    # --------------------------------------------------------------

    principles = qualification.get(
        "principles",
        {},
    )

    mandatory_principles = {
        "fail_closed",
        "registered_does_not_mean_authorized",
        "source_tier_alone_is_not_authorization",
        "source_domain_support_required",
        "event_type_authorization_required",
        "upstream_invalid_event_cannot_be_upgraded",
        "missing_confirmation_is_not_confirmation",
        "missing_reason_is_not_justification",
        "qualification_does_not_calculate_signal",
        "qualification_does_not_calculate_radar_score",
    }

    check(
        all(
            principles.get(key) is True
            for key in mandatory_principles
        ),
        "All qualification fail-closed principles are enabled.",
    )

    # --------------------------------------------------------------
    # 3. Complete source classification
    # --------------------------------------------------------------

    check(
        authorized == {
            "B3",
            "SEC",
            "COMPANY_IR",
            "REUTERS",
        },
        "Exactly four registered sources are catalyst-authorized.",
    )

    check(
        denied == {
            "FED",
            "FRED",
            "CME",
            "US_TREASURY",
            "INVESTING",
            "TRADINGVIEW",
            "YAHOO_FINANCE",
            "USER_PORTFOLIO",
            "RADAR_UNIVERSE",
        },
        "Exactly nine registered sources are explicitly unauthorized.",
    )

    check(
        authorized.isdisjoint(denied),
        "Authorized and denied source sets do not overlap.",
    )

    check(
        authorized | denied == registered,
        "Every registered source is explicitly classified for catalysts.",
    )

    check(
        authorized <= registered,
        "Every catalyst-authorized source exists in Source Registry.",
    )

    check(
        denied <= registered,
        "Every explicitly denied source exists in Source Registry.",
    )

    # --------------------------------------------------------------
    # 4. Critical source semantics
    # --------------------------------------------------------------

    check(
        sources["SEC"].get("tier") == "TIER_1",
        "SEC remains TIER_1 in Source Registry.",
    )

    check(
        "company_events"
        in sources["SEC"].get("supports", []),
        "SEC registry contract supports company_events.",
    )

    check(
        sources["COMPANY_IR"].get("tier") == "TIER_1",
        "COMPANY_IR remains TIER_1.",
    )

    check(
        "company_events"
        in sources["COMPANY_IR"].get(
            "supports",
            [],
        ),
        "COMPANY_IR registry contract supports company_events.",
    )

    check(
        sources["REUTERS"].get("tier") == "TIER_2",
        "REUTERS remains TIER_2.",
    )

    check(
        "company_events"
        in sources["REUTERS"].get(
            "supports",
            [],
        ),
        "REUTERS registry contract supports company_events.",
    )

    check(
        sources["B3"].get("tier") == "TIER_1",
        "B3 remains TIER_1.",
    )

    check(
        "corporate_actions"
        in sources["B3"].get(
            "supports",
            [],
        ),
        "B3 registry contract supports corporate_actions.",
    )

    # --------------------------------------------------------------
    # 5. Prevent tier-only authorization
    # --------------------------------------------------------------

    check(
        sources["USER_PORTFOLIO"].get("tier")
        == "TIER_1",
        "USER_PORTFOLIO remains TIER_1.",
    )

    check(
        "USER_PORTFOLIO" in denied,
        "USER_PORTFOLIO is denied as corporate catalyst evidence.",
    )

    check(
        "USER_PORTFOLIO" not in authorized,
        "TIER_1 does not automatically authorize USER_PORTFOLIO.",
    )

    check(
        sources["YAHOO_FINANCE"].get("tier")
        == "TIER_3",
        "YAHOO_FINANCE remains TIER_3.",
    )

    check(
        sources["YAHOO_FINANCE"].get(
            "publication_use"
        )
        == "RESEARCH_ONLY",
        "YAHOO_FINANCE remains RESEARCH_ONLY.",
    )

    check(
        "YAHOO_FINANCE" in denied,
        "YAHOO_FINANCE is denied as catalyst authority.",
    )

    check(
        "RADAR_UNIVERSE" in denied,
        "RADAR_UNIVERSE cannot establish a catalyst fact.",
    )

    # --------------------------------------------------------------
    # 6. Event-type authorization
    # --------------------------------------------------------------

    auth = qualification[
        "source_authorization"
    ]

    check(
        "CLINICAL"
        in auth["COMPANY_IR"]["allowed_event_types"],
        "COMPANY_IR may support CLINICAL events.",
    )

    check(
        "CLINICAL"
        in auth["REUTERS"]["allowed_event_types"],
        "REUTERS may support CLINICAL events.",
    )

    check(
        "CORPORATE_ACTION"
        in auth["B3"]["allowed_event_types"],
        "B3 may support CORPORATE_ACTION events.",
    )

    check(
        auth["B3"]["allowed_event_types"]
        == ["CORPORATE_ACTION"],
        "B3 catalyst authorization is restricted to CORPORATE_ACTION.",
    )

    check(
        auth["B3"].get(
            "market_scope_required"
        )
        is True,
        "B3 CORPORATE_ACTION authorization requires market scope.",
    )

    check(
        "EARNINGS"
        in auth["SEC"]["allowed_event_types"],
        "SEC may support EARNINGS events.",
    )

    check(
        "GUIDANCE"
        in auth["SEC"]["allowed_event_types"],
        "SEC may support GUIDANCE events.",
    )

    # --------------------------------------------------------------
    # 7. Policy / contract event vocabulary
    # --------------------------------------------------------------

    intelligence_types = set(
        intelligence.get(
            "event_types",
            {},
        ).keys()
    )

    contract_types = set(
        contract.get("event", {})
        .get("fields", {})
        .get("event_type", {})
        .get("values", [])
    )

    authorized_types = set()

    for source_policy in auth.values():
        authorized_types.update(
            source_policy.get(
                "allowed_event_types",
                []
            )
        )

    check(
        contract_types == intelligence_types,
        "Event contract and intelligence policy share event vocabulary.",
    )

    check(
        authorized_types <= contract_types,
        "All source-authorized event types exist in event contract.",
    )

    check(
        "OTHER" not in authorized_types,
        "Disabled OTHER event is not source-authorized.",
    )

    # --------------------------------------------------------------
    # 8. Direction qualification
    # --------------------------------------------------------------

    direction = qualification.get(
        "direction_qualification",
        {},
    )

    check(
        set(direction.get("eligible", []))
        == {
            "POSITIVE",
            "NEGATIVE",
            "NEUTRAL",
        },
        "Only deterministic directions are qualification-eligible.",
    )

    check(
        direction.get("blocked")
        == ["UNCERTAIN"],
        "UNCERTAIN direction is blocked.",
    )

    check(
        set(
            direction.get(
                "reason_required_for",
                [],
            )
        )
        == {
            "POSITIVE",
            "NEGATIVE",
            "NEUTRAL",
        },
        "Every eligible direction requires justification.",
    )

    # --------------------------------------------------------------
    # 9. Materiality qualification
    # --------------------------------------------------------------

    materiality = qualification.get(
        "materiality_qualification",
        {},
    )

    check(
        set(materiality.get("eligible", []))
        == {
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        },
        "Only MEDIUM/HIGH/CRITICAL materiality is eligible.",
    )

    check(
        materiality.get("suppressed")
        == ["LOW"],
        "LOW materiality is suppressed.",
    )

    check(
        materiality.get(
            "reason_required_for_eligible"
        )
        is True,
        "Eligible materiality requires justification.",
    )

    # --------------------------------------------------------------
    # 10. Event status qualification
    # --------------------------------------------------------------

    status = qualification.get(
        "status_qualification",
        {},
    )

    check(
        set(status.get("eligible", []))
        == {
            "SCHEDULED",
            "CONFIRMED",
            "COMPLETED",
        },
        "Scheduled/confirmed/completed statuses are eligible.",
    )

    check(
        status.get("suppressed")
        == ["CANCELLED"],
        "CANCELLED event is suppressed.",
    )

    check(
        status.get("blocked")
        == ["UNVERIFIED"],
        "UNVERIFIED event is blocked.",
    )

    # --------------------------------------------------------------
    # 11. Temporal qualification
    # --------------------------------------------------------------

    temporal = qualification.get(
        "temporal_qualification",
        {},
    )

    check(
        temporal.get(
            "future_scheduled_maximum_days"
        )
        == 90,
        "Future scheduled catalyst horizon is 90 days.",
    )

    check(
        temporal.get(
            "completed_default_maximum_age_days"
        )
        == 30,
        "Default completed catalyst age is 30 days.",
    )

    check(
        temporal.get(
            "completed_event_type_overrides"
        )
        == {
            "REGULATORY": 60,
            "CLINICAL": 60,
            "M_AND_A": 60,
            "CORPORATE_ACTION": 60,
        },
        "Long-cycle catalyst age overrides are fixed at 60 days.",
    )

    check(
        temporal.get(
            "future_non_scheduled_event"
        )
        == "BLOCKED",
        "Future non-scheduled event is blocked.",
    )

    check(
        temporal.get(
            "future_scheduled_beyond_horizon"
        )
        == "SUPPRESSED",
        "Scheduled event beyond horizon is suppressed.",
    )

    check(
        temporal.get(
            "stale_completed_event"
        )
        == "SUPPRESSED",
        "Stale completed event is suppressed.",
    )

    # --------------------------------------------------------------
    # 12. Tier / confirmation semantics
    # --------------------------------------------------------------

    tiers = qualification.get(
        "tier_qualification",
        {},
    )

    check(
        tiers["TIER_1"].get(
            "confirmation_required"
        )
        is False,
        "TIER_1 does not require independent confirmation.",
    )

    check(
        tiers["TIER_2"].get(
            "confirmation_required"
        )
        is False,
        "TIER_2 does not require independent confirmation.",
    )

    check(
        tiers["TIER_3"].get(
            "confirmation_required"
        )
        is True,
        "TIER_3 requires independent confirmation.",
    )

    check(
        tiers["TIER_4"].get(
            "score_eligible"
        )
        is False,
        "TIER_4 is not score eligible.",
    )

    confirmation = qualification.get(
        "confirmation",
        {},
    )

    check(
        confirmation.get(
            "secondary_source_must_be_registered"
        )
        is True,
        "Confirmation source must be registered.",
    )

    check(
        confirmation.get(
            "secondary_source_must_differ_from_primary"
        )
        is True,
        "Confirmation source must differ from primary.",
    )

    check(
        confirmation.get(
            "secondary_source_must_be_authorized_for_event_type"
        )
        is True,
        "Confirmation source must be authorized for event type.",
    )

    check(
        confirmation.get(
            "multiple_sources_do_not_create_multiple_events"
        )
        is True,
        "Multiple sources confirm rather than duplicate an event.",
    )

    # --------------------------------------------------------------
    # 13. Deduplication
    # --------------------------------------------------------------

    dedup = qualification.get(
        "deduplication",
        {},
    )

    check(
        dedup.get("identity_fields")
        == [
            "ticker",
            "event_type",
            "event_date",
            "event_key",
        ],
        "Catalyst deduplication identity is canonical.",
    )

    check(
        dedup.get(
            "duplicate_event_action"
        )
        == "SUPPRESSED",
        "Duplicate catalyst events are suppressed.",
    )

    # --------------------------------------------------------------
    # 14. Output boundary
    # --------------------------------------------------------------

    outcomes = qualification.get(
        "outcomes",
        {},
    )

    check(
        outcomes["ELIGIBLE"].get(
            "may_enter_metrics_composer"
        )
        is True,
        "Only ELIGIBLE outcome may enter metrics composer.",
    )

    check(
        all(
            outcomes[name].get(
                "may_enter_metrics_composer"
            )
            is False
            for name in (
                "SUPPRESSED",
                "BLOCKED",
                "UNAVAILABLE",
            )
        ),
        "Non-eligible outcomes cannot enter metrics composer.",
    )

    # --------------------------------------------------------------
    # 15. Forbidden behavior
    # --------------------------------------------------------------

    forbidden = set(
        qualification.get(
            "forbidden_behaviors",
            [],
        )
    )

    mandatory_forbidden = {
        "AUTHORIZE_SOURCE_BY_TIER_ONLY",
        "AUTHORIZE_SOURCE_BECAUSE_REGISTERED",
        "USE_USER_PORTFOLIO_AS_CORPORATE_EVENT_EVIDENCE",
        "USE_RADAR_UNIVERSE_AS_CORPORATE_EVENT_EVIDENCE",
        "USE_YAHOO_FINANCE_AS_CATALYST_AUTHORITY",
        "UPGRADE_INVALID_EVENT",
        "UPGRADE_UNVERIFIED_EVENT",
        "SCORE_LOW_MATERIALITY_EVENT",
        "SCORE_UNCERTAIN_DIRECTION",
        "DOUBLE_COUNT_DUPLICATE_EVENT",
        "CALCULATE_NORMALIZED_SCORE",
        "CALCULATE_RADAR_POINTS",
    }

    check(
        mandatory_forbidden <= forbidden,
        "All critical qualification forbidden behaviors are explicit.",
    )

    # --------------------------------------------------------------
    # Result
    # --------------------------------------------------------------

    total = passed + failed

    print()
    print("=" * 72)
    print("B.2I.5A QUALIFICATION POLICY RESULT")
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