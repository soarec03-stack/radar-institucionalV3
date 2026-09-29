from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any


VERSION = "3.4I.4-TEST"

BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR))

import catalyst_event_validator_v3 as validator


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


def has_error(
    result: dict[str, Any],
    expected: str,
) -> bool:
    return expected in result.get("errors", [])


def has_error_prefix(
    result: dict[str, Any],
    prefix: str,
) -> bool:
    return any(
        isinstance(error, str) and error.startswith(prefix)
        for error in result.get("errors", [])
    )


def make_valid_event() -> dict[str, Any]:
    return {
        "event_id": "CAT-VRT-TEST-001",
        "event_key": "vrt-test-guidance-001",
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
        "title": "Synthetic catalyst validator regression event",
        "summary": (
            "Synthetic event used only to test the validator."
        ),
        "evidence": {
            "fact": (
                "Synthetic confirmed guidance event for "
                "validator regression."
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


def validate(
    event: Any,
    contract: dict[str, Any],
    policy: dict[str, Any],
    known_tickers: set[str],
    registered_sources: set[str],
) -> dict[str, Any]:
    return validator.validate_event(
        event=event,
        contract=contract,
        policy=policy,
        known_tickers=known_tickers,
        registered_sources=registered_sources,
    )


def main() -> int:
    print("=" * 72)
    print("CATALYST EVENT VALIDATOR REGRESSION V3")
    print(f"Test version: {VERSION}")
    print("=" * 72)

    contract = validator.load_json(
        validator.DEFAULT_CONTRACT
    )
    policy = validator.load_json(
        validator.DEFAULT_POLICY
    )
    universe = validator.load_json(
        validator.DEFAULT_UNIVERSE
    )
    registry = validator.load_json(
        validator.DEFAULT_SOURCE_REGISTRY
    )

    known_tickers = validator.extract_known_tickers(
        universe
    )
    registered_sources = (
        validator.extract_registered_sources(
            registry
        )
    )

    # --------------------------------------------------------------
    # 1. Real repository bindings
    # --------------------------------------------------------------

    check(
        known_tickers == {"VRT", "CRSP", "ETON"},
        "Asset-universe binding resolves VRT/CRSP/ETON.",
    )

    check(
        len(registered_sources) == 13,
        "Source-registry binding resolves 13 sources.",
    )

    check(
        {
            "B3",
            "SEC",
            "COMPANY_IR",
            "REUTERS",
            "YAHOO_FINANCE",
        }.issubset(registered_sources),
        "Expected representative source IDs are registered.",
    )

    check(
        None not in registered_sources,
        "Registered source set contains no None identifier.",
    )

    # --------------------------------------------------------------
    # 2. Canonical valid event
    # --------------------------------------------------------------

    base = make_valid_event()

    result = validate(
        base,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is True,
        "Canonical catalyst event passes structural validation.",
    )

    check(
        result["errors"] == [],
        "Canonical catalyst event produces zero errors.",
    )

    check(
        result["warnings"] == [],
        "Canonical fully justified event produces zero warnings.",
    )

    # --------------------------------------------------------------
    # 3. Unknown asset
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    event["ticker"] = "UNKNOWN"

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Unknown asset fails validation.",
    )

    check(
        has_error(result, "UNKNOWN_ASSET:UNKNOWN"),
        "Unknown asset emits canonical UNKNOWN_ASSET error.",
    )

    # --------------------------------------------------------------
    # 4. Unregistered primary source
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    event["source"]["primary_source"] = "FAKE_SOURCE"

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Unregistered primary source fails validation.",
    )

    check(
        has_error(
            result,
            "UNREGISTERED_SOURCE:FAKE_SOURCE",
        ),
        "Unregistered primary source emits canonical error.",
    )

    # --------------------------------------------------------------
    # 5. Disabled OTHER event type
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_type"] = "OTHER"

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Policy-disabled OTHER event fails validation.",
    )

    check(
        has_error(
            result,
            "DISABLED_EVENT_TYPE:OTHER",
        ),
        "Disabled OTHER event emits canonical error.",
    )

    # --------------------------------------------------------------
    # 6. Unknown event type
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_type"] = "MAGIC_EVENT"

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Unknown event type fails validation.",
    )

    check(
        has_error_prefix(
            result,
            "INVALID_ENUM:event_type:",
        ),
        "Unknown event type violates contract enum.",
    )

    check(
        has_error(
            result,
            "UNKNOWN_POLICY_EVENT_TYPE:MAGIC_EVENT",
        ),
        "Unknown event type also violates policy.",
    )

    # --------------------------------------------------------------
    # 7. Invalid event date
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    event["event_date"] = "2026-99-99"

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Invalid event_date fails validation.",
    )

    check(
        has_error(
            result,
            "INVALID_DATE:event_date",
        ),
        "Invalid event_date emits canonical error.",
    )

    # --------------------------------------------------------------
    # 8. Missing evidence.fact
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    event["evidence"] = {}

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Missing evidence.fact fails validation.",
    )

    check(
        has_error(
            result,
            "MISSING_EVIDENCE_FACT",
        ),
        "Missing evidence.fact emits canonical error.",
    )

    # --------------------------------------------------------------
    # 9. Invalid retrieved_at
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    event["source"]["retrieved_at"] = "not-a-datetime"

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Invalid source.retrieved_at fails validation.",
    )

    check(
        has_error(
            result,
            "INVALID_DATETIME:source.retrieved_at",
        ),
        "Invalid retrieved_at emits canonical error.",
    )

    # --------------------------------------------------------------
    # 10. Invalid direction enum
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    event["direction"] = "VERY_POSITIVE"

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Invalid direction enum fails validation.",
    )

    check(
        has_error(
            result,
            "INVALID_ENUM:direction:VERY_POSITIVE",
        ),
        "Invalid direction emits canonical enum error.",
    )

    # --------------------------------------------------------------
    # 11. Invalid materiality enum
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    event["materiality"] = "EXTREME"

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Invalid materiality enum fails validation.",
    )

    check(
        has_error(
            result,
            "INVALID_ENUM:materiality:EXTREME",
        ),
        "Invalid materiality emits canonical enum error.",
    )

    # --------------------------------------------------------------
    # 12. Unknown secondary source
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    event["source"]["secondary_source"] = (
        "UNKNOWN_SECONDARY"
    )

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Unknown secondary source fails validation.",
    )

    check(
        has_error(
            result,
            "UNREGISTERED_SECONDARY_SOURCE:"
            "UNKNOWN_SECONDARY",
        ),
        "Unknown secondary source emits canonical error.",
    )

    # --------------------------------------------------------------
    # 13. Missing required event_key
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    del event["event_key"]

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Missing event_key fails validation.",
    )

    check(
        has_error(
            result,
            "MISSING_REQUIRED_FIELD:event_key",
        ),
        "Missing event_key emits required-field error.",
    )

    # --------------------------------------------------------------
    # 14. Missing title
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    del event["title"]

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Missing title fails validation.",
    )

    check(
        has_error(
            result,
            "MISSING_REQUIRED_FIELD:title",
        ),
        "Missing title emits required-field error.",
    )

    # --------------------------------------------------------------
    # 15. Missing primary source
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    del event["source"]["primary_source"]

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Missing primary source fails validation.",
    )

    check(
        has_error(
            result,
            "MISSING_SOURCE_PRIMARY",
        ),
        "Missing primary source emits canonical error.",
    )

    # --------------------------------------------------------------
    # 16. Missing retrieved_at
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    del event["source"]["retrieved_at"]

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Missing source.retrieved_at fails validation.",
    )

    check(
        has_error(
            result,
            "MISSING_SOURCE_RETRIEVED_AT",
        ),
        "Missing retrieved_at emits canonical error.",
    )

    # --------------------------------------------------------------
    # 17. Warning semantics
    # --------------------------------------------------------------

    event = copy.deepcopy(base)
    del event["direction_reason"]

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is True,
        "Missing direction_reason is structural warning, not error.",
    )

    check(
        "MISSING_DIRECTION_REASON"
        in result["warnings"],
        "Missing direction_reason emits warning.",
    )

    event = copy.deepcopy(base)
    del event["materiality_reason"]

    result = validate(
        event,
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is True,
        "Missing materiality_reason is structural warning, not error.",
    )

    check(
        "MISSING_MATERIALITY_REASON"
        in result["warnings"],
        "Missing materiality_reason emits warning.",
    )

    # --------------------------------------------------------------
    # 18. Payload semantics
    # --------------------------------------------------------------

    payload_result = validator.validate_payload(
        payload=[
            copy.deepcopy(base),
            {
                **copy.deepcopy(base),
                "ticker": "UNKNOWN",
                "event_id": "CAT-INVALID-001",
            },
        ],
        contract=contract,
        policy=policy,
        known_tickers=known_tickers,
        registered_sources=registered_sources,
    )

    check(
        payload_result["total_events"] == 2,
        "Payload validator counts two events.",
    )

    check(
        payload_result["valid_events"] == 1,
        "Payload validator counts one valid event.",
    )

    check(
        payload_result["invalid_events"] == 1,
        "Payload validator counts one invalid event.",
    )

    check(
        payload_result["valid"] is False,
        "Mixed valid/invalid payload fails closed.",
    )

    # --------------------------------------------------------------
    # 19. Non-object event
    # --------------------------------------------------------------

    result = validate(
        "not-an-object",
        contract,
        policy,
        known_tickers,
        registered_sources,
    )

    check(
        result["valid"] is False,
        "Non-object event fails validation.",
    )

    check(
        has_error(
            result,
            "EVENT_NOT_OBJECT",
        ),
        "Non-object event emits EVENT_NOT_OBJECT.",
    )

    # --------------------------------------------------------------
    # Result
    # --------------------------------------------------------------

    total = passed + failed

    print()
    print("=" * 72)
    print("B.2I.4 VALIDATOR REGRESSION RESULT")
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