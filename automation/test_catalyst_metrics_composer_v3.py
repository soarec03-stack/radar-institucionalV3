from __future__ import annotations

import copy
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


VERSION = "3.4I.6D-B.2I.6D"
REFERENCE_DATE = date(2026, 9, 27)

BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR))

import catalyst_metrics_composer_v3 as composer


COMPOSER_POLICY_PATH = (
    BASE_DIR / "catalyst_metrics_composer_policy_v3.json"
)

INTELLIGENCE_POLICY_PATH = (
    BASE_DIR / "catalyst_intelligence_policy_v3.json"
)

SOURCE_REGISTRY_PATH = (
    BASE_DIR / "source_registry_v3.json"
)


passed = 0
failed = 0


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


COMPOSER_POLICY = load_json(
    COMPOSER_POLICY_PATH
)

INTELLIGENCE_POLICY = load_json(
    INTELLIGENCE_POLICY_PATH
)

SOURCE_REGISTRY = load_json(
    SOURCE_REGISTRY_PATH
)

SOURCES = composer.source_map(
    SOURCE_REGISTRY
)


def check(
    condition: bool,
    description: str,
) -> None:
    global passed, failed

    if condition:
        passed += 1
        print(f"[PASS] {description}")
    else:
        failed += 1
        print(f"[FAIL] {description}")


def canonical_event() -> dict[str, Any]:
    return {
        "event_id": "CAT-TEST-001",
        "event_key": "guidance-2026-q3",
        "ticker": "VRT",
        "event_type": "GUIDANCE",
        "event_status": "COMPLETED",
        "event_date": "2026-09-27",
        "direction": "POSITIVE",
        "direction_reason": (
            "Official guidance evidence."
        ),
        "materiality": "HIGH",
        "materiality_reason": (
            "Material operating impact."
        ),
        "title": "Company updates guidance",
        "evidence": {
            "fact": "Official guidance was updated."
        },
        "source": {
            "primary_source": "COMPANY_IR",
            "retrieved_at": (
                "2026-09-27T12:00:00Z"
            ),
        },
    }


def qualified_record(
    event: dict[str, Any] | None = None,
    status: str = "ELIGIBLE",
) -> dict[str, Any]:
    return {
        "status": status,
        "event": (
            copy.deepcopy(event)
            if event is not None
            else canonical_event()
        ),
    }


def compose(
    records: list[Any],
) -> dict[str, Any]:
    return composer.compose_metrics(
        records=records,
        reference_date=REFERENCE_DATE,
        composer_policy=COMPOSER_POLICY,
        intelligence_policy=(
            INTELLIGENCE_POLICY
        ),
        registry=SOURCE_REGISTRY,
    )


def first_item(
    result: dict[str, Any],
) -> dict[str, Any]:
    return result["metrics"]["items"][0]


def contains_forbidden_key(
    value: Any,
) -> bool:
    forbidden = {
        "normalized_score",
        "confidence_score",
        "radar_score",
        "radar_points",
        "decision",
    }

    if isinstance(value, dict):
        for key, child in value.items():
            if key in forbidden:
                return True

            if contains_forbidden_key(child):
                return True

    elif isinstance(value, list):
        for child in value:
            if contains_forbidden_key(child):
                return True

    return False


def main() -> int:
    print("=" * 72)
    print("CATALYST METRICS COMPOSER REGRESSION V3")
    print(f"Test version  : {VERSION}")
    print(
        f"Reference date: "
        f"{REFERENCE_DATE.isoformat()}"
    )
    print("=" * 72)

    # ----------------------------------------------------------
    # 1. Canonical bindings
    # ----------------------------------------------------------

    check(
        composer.VERSION
        == "3.4I.6C-B.2I.6C",
        "Composer implementation version is canonical.",
    )

    check(
        {
            "B3",
            "SEC",
            "COMPANY_IR",
            "REUTERS",
        }.issubset(SOURCES),
        "Composer resolves all Catalyst-authorized sources.",
    )

    # ----------------------------------------------------------
    # 2. Canonical positive event
    # ----------------------------------------------------------

    result = compose(
        [qualified_record()]
    )

    check(
        result["status"] == "READY",
        "Canonical eligible event produces READY output.",
    )

    check(
        result["summary"]["input_records"] == 1
        and result["summary"]["ready_items"] == 1
        and result["summary"][
            "suppressed_records"
        ] == 0
        and result["summary"][
            "blocked_records"
        ] == 0,
        "Canonical event summary is deterministic.",
    )

    item = first_item(result)

    check(
        set(item.keys())
        == {
            "description",
            "signed_impact",
            "probability",
            "source_quality",
            "horizon_days",
        },
        "Composer emits exactly the Catalyst metrics item contract.",
    )

    check(
        item["description"]
        == "Company updates guidance",
        "Composer uses event.title as description.",
    )

    check(
        item["signed_impact"] == 75.0,
        "HIGH POSITIVE maps deterministically to +75.",
    )

    check(
        item["probability"] == 1.0,
        "COMPLETED maps deterministically to probability 1.0.",
    )

    check(
        item["source_quality"] == 0.95,
        "COMPANY_IR maps to authority_score 0.95.",
    )

    check(
        item["horizon_days"] == 0.0,
        "COMPLETED event has zero future horizon.",
    )

    # ----------------------------------------------------------
    # 3. signed_impact mapping
    # ----------------------------------------------------------

    event = canonical_event()
    event["materiality"] = "MEDIUM"

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "signed_impact"
        ] == 50.0,
        "MEDIUM POSITIVE maps to +50.",
    )

    event = canonical_event()
    event["materiality"] = "CRITICAL"

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "signed_impact"
        ] == 100.0,
        "CRITICAL POSITIVE maps to +100.",
    )

    event = canonical_event()
    event["direction"] = "NEGATIVE"
    event["materiality"] = "MEDIUM"

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "signed_impact"
        ] == -50.0,
        "MEDIUM NEGATIVE maps to -50.",
    )

    event = canonical_event()
    event["direction"] = "NEGATIVE"
    event["materiality"] = "HIGH"

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "signed_impact"
        ] == -75.0,
        "HIGH NEGATIVE maps to -75.",
    )

    event = canonical_event()
    event["direction"] = "NEGATIVE"
    event["materiality"] = "CRITICAL"

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "signed_impact"
        ] == -100.0,
        "CRITICAL NEGATIVE maps to -100.",
    )

    event = canonical_event()
    event["direction"] = "NEUTRAL"

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "signed_impact"
        ] == 0.0,
        "NEUTRAL catalyst maps to zero signed impact.",
    )

    # ----------------------------------------------------------
    # 4. Source quality mapping
    # ----------------------------------------------------------

    event = canonical_event()
    event["source"][
        "primary_source"
    ] = "SEC"

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "source_quality"
        ] == 1.0,
        "SEC maps to source_quality 1.0.",
    )

    event = canonical_event()
    event["source"][
        "primary_source"
    ] = "REUTERS"

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "source_quality"
        ] == 0.92,
        "REUTERS maps to source_quality 0.92.",
    )

    event = canonical_event()
    event["source"][
        "primary_source"
    ] = "B3"

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "source_quality"
        ] == 1.0,
        "B3 maps to source_quality 1.0.",
    )

    # ----------------------------------------------------------
    # 5. CONFIRMED probability
    # ----------------------------------------------------------

    event = canonical_event()
    event["event_status"] = "CONFIRMED"

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "probability"
        ] == 1.0,
        "CONFIRMED maps deterministically to probability 1.0.",
    )

    check(
        first_item(result)[
            "horizon_days"
        ] == 0.0,
        "CONFIRMED event has zero future horizon.",
    )

    # Upstream value cannot override policy.
    event["probability"] = 0.20

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "probability"
        ] == 1.0,
        "CONFIRMED cannot override policy probability 1.0.",
    )

    event = canonical_event()
    event["probability"] = 0.10

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "probability"
        ] == 1.0,
        "COMPLETED cannot override policy probability 1.0.",
    )

    # ----------------------------------------------------------
    # 6. SCHEDULED probability and horizon
    # ----------------------------------------------------------

    event = canonical_event()
    event["event_status"] = "SCHEDULED"
    event["event_date"] = "2026-10-07"

    result = compose(
        [qualified_record(event)]
    )

    check(
        result["status"] == "SUPPRESSED",
        "SCHEDULED without observable probability is suppressed.",
    )

    check(
        result["summary"][
            "ready_items"
        ] == 0
        and result["summary"][
            "suppressed_records"
        ] == 1,
        "Suppressed scheduled event emits no metrics item.",
    )

    check(
        result["audit"][0]["reason"]
        == "PROBABILITY_NOT_DERIVABLE",
        "Missing scheduled probability has canonical suppression reason.",
    )

    event["probability"] = 0.70

    result = compose(
        [qualified_record(event)]
    )

    item = first_item(result)

    check(
        result["status"] == "READY",
        "SCHEDULED with explicit observable probability becomes READY.",
    )

    check(
        item["probability"] == 0.70,
        "Explicit scheduled probability is preserved.",
    )

    check(
        item["horizon_days"] == 10.0,
        "Scheduled event derives ten-day horizon correctly.",
    )

    # Composer must not apply decay itself.
    check(
        item["signed_impact"] == 75.0
        and item["source_quality"] == 0.95,
        "Composer does not pre-apply horizon decay or source weighting.",
    )

    # ----------------------------------------------------------
    # 7. Probability boundaries
    # ----------------------------------------------------------

    event = canonical_event()
    event["event_status"] = "SCHEDULED"
    event["event_date"] = "2026-10-01"
    event["probability"] = 0.0

    result = compose(
        [qualified_record(event)]
    )

    check(
        result["status"] == "READY"
        and first_item(result)[
            "probability"
        ] == 0.0,
        "Explicit scheduled probability 0.0 remains valid metric input.",
    )

    event["probability"] = 1.0

    result = compose(
        [qualified_record(event)]
    )

    check(
        result["status"] == "READY"
        and first_item(result)[
            "probability"
        ] == 1.0,
        "Explicit scheduled probability 1.0 remains valid.",
    )

    event["probability"] = 1.01

    result = compose(
        [qualified_record(event)]
    )

    check(
        result["status"] == "SUPPRESSED"
        and result["audit"][0][
            "reason"
        ] == "PROBABILITY_NOT_DERIVABLE",
        "Scheduled probability above 1 fails closed.",
    )

    event["probability"] = -0.01

    result = compose(
        [qualified_record(event)]
    )

    check(
        result["status"] == "SUPPRESSED"
        and result["audit"][0][
            "reason"
        ] == "PROBABILITY_NOT_DERIVABLE",
        "Negative scheduled probability fails closed.",
    )

    # ----------------------------------------------------------
    # 8. Description fallback
    # ----------------------------------------------------------

    event = canonical_event()
    event["title"] = ""

    result = compose(
        [qualified_record(event)]
    )

    check(
        first_item(result)[
            "description"
        ]
        == "Official guidance was updated.",
        "Evidence fact is deterministic description fallback.",
    )

    event["evidence"]["fact"] = ""

    result = compose(
        [qualified_record(event)]
    )

    check(
        result["status"] == "SUPPRESSED"
        and result["audit"][0][
            "reason"
        ] == "DESCRIPTION_NOT_DERIVABLE",
        "Composer never invents missing description.",
    )

    # ----------------------------------------------------------
    # 9. Missing/invalid source quality
    # ----------------------------------------------------------

    event = canonical_event()
    event["source"][
        "primary_source"
    ] = "UNKNOWN_SOURCE"

    result = compose(
        [qualified_record(event)]
    )

    check(
        result["status"] == "SUPPRESSED"
        and result["audit"][0][
            "reason"
        ] == "SOURCE_QUALITY_NOT_DERIVABLE",
        "Unknown primary source cannot produce source_quality.",
    )

    registry = copy.deepcopy(
        SOURCE_REGISTRY
    )

    for source in registry["sources"]:
        if source.get("id") == "COMPANY_IR":
            source.pop(
                "authority_score",
                None,
            )

    result = composer.compose_metrics(
        records=[qualified_record()],
        reference_date=REFERENCE_DATE,
        composer_policy=COMPOSER_POLICY,
        intelligence_policy=(
            INTELLIGENCE_POLICY
        ),
        registry=registry,
    )

    check(
        result["status"] == "SUPPRESSED"
        and result["audit"][0][
            "reason"
        ] == "SOURCE_QUALITY_NOT_DERIVABLE",
        "Missing authority_score suppresses metrics item.",
    )

    # ----------------------------------------------------------
    # 10. Qualification boundary
    # ----------------------------------------------------------

    for q_status in (
        "SUPPRESSED",
        "BLOCKED",
        "UNAVAILABLE",
    ):
        result = compose(
            [
                qualified_record(
                    status=q_status,
                )
            ]
        )

        check(
            result["status"] == "BLOCKED"
            and result["summary"][
                "ready_items"
            ] == 0,
            (
                f"{q_status} qualification cannot "
                f"enter Composer metrics."
            ),
        )

    result = compose(
        [canonical_event()]
    )

    check(
        result["status"] == "BLOCKED",
        "Raw unqualified event cannot be silently upgraded.",
    )

    check(
        result["audit"][0]["reason"]
        == "QUALIFICATION_STATUS_NOT_ELIGIBLE",
        "Raw event fails with qualification boundary reason.",
    )

    result = compose(
        ["not-an-object"]
    )

    check(
        result["status"] == "BLOCKED"
        and result["audit"][0][
            "reason"
        ] == "RECORD_NOT_OBJECT",
        "Non-object record fails closed.",
    )

    # ----------------------------------------------------------
    # 11. Missing derivation inputs
    # ----------------------------------------------------------

    event = canonical_event()
    event.pop("direction")

    result = compose(
        [qualified_record(event)]
    )

    check(
        result["status"] == "SUPPRESSED"
        and result["audit"][0][
            "reason"
        ] == "SIGNED_IMPACT_NOT_DERIVABLE",
        "Missing direction suppresses signed impact derivation.",
    )

    event = canonical_event()
    event.pop("materiality")

    result = compose(
        [qualified_record(event)]
    )

    check(
        result["status"] == "SUPPRESSED"
        and result["audit"][0][
            "reason"
        ] == "SIGNED_IMPACT_NOT_DERIVABLE",
        "Missing materiality suppresses signed impact derivation.",
    )

    event = canonical_event()
    event["event_status"] = "SCHEDULED"
    event["probability"] = 0.8
    event["event_date"] = "invalid-date"

    result = compose(
        [qualified_record(event)]
    )

    check(
        result["status"] == "SUPPRESSED"
        and result["audit"][0][
            "reason"
        ] == "HORIZON_NOT_DERIVABLE",
        "Invalid scheduled event date fails horizon derivation.",
    )

    # ----------------------------------------------------------
    # 12. Multiple records
    # ----------------------------------------------------------

    positive = canonical_event()

    negative = canonical_event()
    negative["event_id"] = "CAT-TEST-002"
    negative["event_key"] = "regulatory-002"
    negative["direction"] = "NEGATIVE"
    negative["materiality"] = "CRITICAL"
    negative["source"][
        "primary_source"
    ] = "SEC"

    result = compose(
        [
            qualified_record(positive),
            qualified_record(negative),
        ]
    )

    check(
        result["status"] == "READY"
        and result["summary"][
            "ready_items"
        ] == 2,
        "Two eligible events produce two independent metrics items.",
    )

    check(
        len(result["metrics"]["items"]) == 2,
        "Composer does not pre-aggregate multiple events.",
    )

    check(
        result["metrics"]["items"][0][
            "signed_impact"
        ] == 75.0
        and result["metrics"]["items"][1][
            "signed_impact"
        ] == -100.0,
        "Multiple event signed impacts remain independent.",
    )

    # ----------------------------------------------------------
    # 13. Mixed READY / suppressed / blocked
    # ----------------------------------------------------------

    scheduled_missing_probability = (
        canonical_event()
    )
    scheduled_missing_probability[
        "event_status"
    ] = "SCHEDULED"
    scheduled_missing_probability[
        "event_date"
    ] = "2026-10-05"

    result = compose(
        [
            qualified_record(),
            qualified_record(
                scheduled_missing_probability
            ),
            qualified_record(
                status="BLOCKED"
            ),
        ]
    )

    check(
        result["status"] == "READY",
        "At least one composed item makes batch READY.",
    )

    check(
        result["summary"][
            "ready_items"
        ] == 1
        and result["summary"][
            "suppressed_records"
        ] == 1
        and result["summary"][
            "blocked_records"
        ] == 1,
        "Mixed batch summary preserves READY/SUPPRESSED/BLOCKED counts.",
    )

    # ----------------------------------------------------------
    # 14. Empty batch
    # ----------------------------------------------------------

    result = compose([])

    check(
        result["status"] == "SUPPRESSED",
        "Empty batch produces no invented Catalyst metrics.",
    )

    check(
        result["metrics"]["items"] == [],
        "Empty batch contains zero metrics items.",
    )

    # ----------------------------------------------------------
    # 15. Forbidden downstream outputs
    # ----------------------------------------------------------

    result = compose(
        [qualified_record()]
    )

    check(
        not contains_forbidden_key(result),
        "Composer emits no score/confidence/decision outputs.",
    )

    item = first_item(result)

    check(
        "weight" not in item
        and "time_weight" not in item,
        "Composer emits no Signal Engine weighting fields.",
    )

    check(
        "normalized_score" not in item,
        "Composer does not calculate normalized Catalyst score.",
    )

    # ----------------------------------------------------------
    # 16. Input immutability
    # ----------------------------------------------------------

    record = qualified_record()
    original = copy.deepcopy(record)

    compose([record])

    check(
        record == original,
        "Composer does not mutate qualification input.",
    )

    # ----------------------------------------------------------
    # Final
    # ----------------------------------------------------------

    total = passed + failed

    print()
    print("=" * 72)
    print("B.2I.6D CATALYST METRICS COMPOSER RESULT")
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