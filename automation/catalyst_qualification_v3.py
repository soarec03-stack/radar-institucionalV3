from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


VERSION = "3.4I.5B-B.2I.5B"

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_POLICY = (
    BASE_DIR / "catalyst_qualification_policy_v3.json"
)
DEFAULT_EVENT_POLICY = (
    BASE_DIR / "catalyst_intelligence_policy_v3.json"
)
DEFAULT_CONTRACT = (
    BASE_DIR / "catalyst_event_contract_v3.json"
)
DEFAULT_UNIVERSE = (
    BASE_DIR / "asset_universe_v3.json"
)
DEFAULT_SOURCE_REGISTRY = (
    BASE_DIR / "source_registry_v3.json"
)

sys.path.insert(0, str(BASE_DIR))

import catalyst_event_validator_v3 as event_validator


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            value,
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.write("\n")


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_date(value: Any) -> date | None:
    if not is_nonempty_string(value):
        return None

    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    if not is_nonempty_string(value):
        return None

    candidate = value.strip()

    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def source_map(
    registry: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for source in registry.get("sources", []):
        if not isinstance(source, dict):
            continue

        source_id = source.get("id")

        if is_nonempty_string(source_id):
            result[source_id.strip()] = source

    return result


def dedup_identity(
    event: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[Any, ...]:
    fields = (
        policy.get("deduplication", {})
        .get("identity_fields", [])
    )

    return tuple(event.get(field) for field in fields)


def source_is_authorized(
    source_id: str,
    event_type: str,
    policy: dict[str, Any],
) -> bool:
    authorization = policy.get(
        "source_authorization",
        {},
    )

    source_policy = authorization.get(source_id)

    if not isinstance(source_policy, dict):
        return False

    allowed = source_policy.get(
        "allowed_event_types",
        [],
    )

    return event_type in allowed


def source_tier(
    source_id: str,
    sources: dict[str, dict[str, Any]],
) -> str | None:
    source = sources.get(source_id)

    if not isinstance(source, dict):
        return None

    tier = source.get("tier")

    if not is_nonempty_string(tier):
        return None

    return tier.strip()


def temporal_result(
    event: dict[str, Any],
    policy: dict[str, Any],
    reference_date: date,
) -> tuple[str | None, str | None]:
    event_date = parse_date(event.get("event_date"))

    if event_date is None:
        return "BLOCKED", "INVALID_EVENT_DATE"

    status = event.get("event_status")
    event_type = event.get("event_type")

    delta_days = (event_date - reference_date).days

    temporal = policy.get(
        "temporal_qualification",
        {},
    )

    if delta_days > 0:
        if status != "SCHEDULED":
            return (
                temporal.get(
                    "future_non_scheduled_event",
                    "BLOCKED",
                ),
                "FUTURE_NON_SCHEDULED_EVENT",
            )

        maximum = temporal.get(
            "future_scheduled_maximum_days",
            90,
        )

        if delta_days > maximum:
            return (
                temporal.get(
                    "future_scheduled_beyond_horizon",
                    "SUPPRESSED",
                ),
                "FUTURE_SCHEDULED_BEYOND_HORIZON",
            )

        return None, None

    if status == "COMPLETED":
        age_days = abs(delta_days)

        maximum_age = temporal.get(
            "completed_default_maximum_age_days",
            30,
        )

        overrides = temporal.get(
            "completed_event_type_overrides",
            {},
        )

        maximum_age = overrides.get(
            event_type,
            maximum_age,
        )

        if age_days > maximum_age:
            return (
                temporal.get(
                    "stale_completed_event",
                    "SUPPRESSED",
                ),
                "STALE_COMPLETED_EVENT",
            )

    return None, None


def qualification_result(
    status: str,
    reasons: list[str],
    event: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "event_key": event.get("event_key"),
        "ticker": event.get("ticker"),
        "event_type": event.get("event_type"),
        "status": status,
        "usable": status == "ELIGIBLE",
        "reasons": reasons,
    }


def qualify_event(
    event: Any,
    qualification_policy: dict[str, Any],
    event_policy: dict[str, Any],
    contract: dict[str, Any],
    known_tickers: set[str],
    registered_sources: set[str],
    sources: dict[str, dict[str, Any]],
    reference_date: date,
) -> dict[str, Any]:
    validation = event_validator.validate_event(
        event=event,
        contract=contract,
        policy=event_policy,
        known_tickers=known_tickers,
        registered_sources=registered_sources,
    )

    if not validation.get("valid"):
        event_obj = event if isinstance(event, dict) else {}

        reasons = [
            f"UPSTREAM_VALIDATION:{error}"
            for error in validation.get("errors", [])
        ]

        if not reasons:
            reasons = ["UPSTREAM_VALIDATION_FAILED"]

        return qualification_result(
            "BLOCKED",
            reasons,
            event_obj,
        )

    assert isinstance(event, dict)

    event_type = event["event_type"]
    event_status = event["event_status"]
    direction = event["direction"]
    materiality = event["materiality"]

    source = event["source"]
    primary_source = source["primary_source"]

    # ----------------------------------------------------------
    # Source authorization
    # ----------------------------------------------------------

    if not source_is_authorized(
        primary_source,
        event_type,
        qualification_policy,
    ):
        return qualification_result(
            "BLOCKED",
            [
                "PRIMARY_SOURCE_NOT_AUTHORIZED_FOR_EVENT_TYPE"
            ],
            event,
        )

    # ----------------------------------------------------------
    # B3 market scope
    #
    # B3 is registered for corporate actions, but Catalyst
    # qualification must fail closed unless the event explicitly
    # demonstrates that B3 is within the event's market scope.
    # ----------------------------------------------------------

    primary_policy = (
        qualification_policy
        .get("source_authorization", {})
        .get(primary_source, {})
    )

    if primary_policy.get(
        "market_scope_required"
    ) is True:
        market_scope = event.get("market_scope")

        if market_scope != "B3":
            return qualification_result(
                "BLOCKED",
                ["PRIMARY_SOURCE_MARKET_SCOPE_NOT_PROVEN"],
                event,
            )

    # ----------------------------------------------------------
    # Tier
    # ----------------------------------------------------------

    tier = source_tier(
        primary_source,
        sources,
    )

    if tier is None:
        return qualification_result(
            "BLOCKED",
            ["PRIMARY_SOURCE_TIER_UNAVAILABLE"],
            event,
        )

    tier_policy = (
        qualification_policy
        .get("tier_qualification", {})
        .get(tier)
    )

    if not isinstance(tier_policy, dict):
        return qualification_result(
            "BLOCKED",
            ["PRIMARY_SOURCE_TIER_NOT_SUPPORTED"],
            event,
        )

    if tier_policy.get("score_eligible") is False:
        return qualification_result(
            "BLOCKED",
            ["PRIMARY_SOURCE_TIER_NOT_SCORE_ELIGIBLE"],
            event,
        )

    # ----------------------------------------------------------
    # Event status
    # ----------------------------------------------------------

    status_policy = qualification_policy.get(
        "status_qualification",
        {},
    )

    if event_status in status_policy.get(
        "blocked",
        [],
    ):
        return qualification_result(
            "BLOCKED",
            [f"EVENT_STATUS_BLOCKED:{event_status}"],
            event,
        )

    if event_status in status_policy.get(
        "suppressed",
        [],
    ):
        return qualification_result(
            "SUPPRESSED",
            [f"EVENT_STATUS_SUPPRESSED:{event_status}"],
            event,
        )

    if event_status not in status_policy.get(
        "eligible",
        [],
    ):
        return qualification_result(
            "BLOCKED",
            [f"EVENT_STATUS_NOT_ELIGIBLE:{event_status}"],
            event,
        )

    # ----------------------------------------------------------
    # Direction
    # ----------------------------------------------------------

    direction_policy = qualification_policy.get(
        "direction_qualification",
        {},
    )

    if direction in direction_policy.get(
        "blocked",
        [],
    ):
        return qualification_result(
            "BLOCKED",
            [f"DIRECTION_BLOCKED:{direction}"],
            event,
        )

    if direction not in direction_policy.get(
        "eligible",
        [],
    ):
        return qualification_result(
            "BLOCKED",
            [f"DIRECTION_NOT_ELIGIBLE:{direction}"],
            event,
        )

    if direction in direction_policy.get(
        "reason_required_for",
        [],
    ):
        if not is_nonempty_string(
            event.get("direction_reason")
        ):
            return qualification_result(
                "BLOCKED",
                ["DIRECTION_REASON_REQUIRED"],
                event,
            )

    # ----------------------------------------------------------
    # Materiality
    # ----------------------------------------------------------

    materiality_policy = qualification_policy.get(
        "materiality_qualification",
        {},
    )

    if materiality in materiality_policy.get(
        "suppressed",
        [],
    ):
        return qualification_result(
            "SUPPRESSED",
            [
                f"MATERIALITY_SUPPRESSED:"
                f"{materiality}"
            ],
            event,
        )

    if materiality not in materiality_policy.get(
        "eligible",
        [],
    ):
        return qualification_result(
            "BLOCKED",
            [
                f"MATERIALITY_NOT_ELIGIBLE:"
                f"{materiality}"
            ],
            event,
        )

    if materiality_policy.get(
        "reason_required_for_eligible"
    ) is True:
        if not is_nonempty_string(
            event.get("materiality_reason")
        ):
            return qualification_result(
                "BLOCKED",
                ["MATERIALITY_REASON_REQUIRED"],
                event,
            )

    # ----------------------------------------------------------
    # Temporal qualification
    # ----------------------------------------------------------

    temporal_status, temporal_reason = (
        temporal_result(
            event,
            qualification_policy,
            reference_date,
        )
    )

    if temporal_status is not None:
        return qualification_result(
            temporal_status,
            [temporal_reason or "TEMPORAL_FAILURE"],
            event,
        )

    # ----------------------------------------------------------
    # Independent confirmation when tier requires it
    # ----------------------------------------------------------

    if tier_policy.get(
        "confirmation_required"
    ) is True:
        secondary = source.get("secondary_source")

        if not is_nonempty_string(secondary):
            return qualification_result(
                "BLOCKED",
                ["INDEPENDENT_CONFIRMATION_REQUIRED"],
                event,
            )

        secondary = secondary.strip()

        if secondary == primary_source:
            return qualification_result(
                "BLOCKED",
                [
                    "SECONDARY_SOURCE_NOT_INDEPENDENT"
                ],
                event,
            )

        if secondary not in registered_sources:
            return qualification_result(
                "BLOCKED",
                [
                    "SECONDARY_SOURCE_NOT_REGISTERED"
                ],
                event,
            )

        if not source_is_authorized(
            secondary,
            event_type,
            qualification_policy,
        ):
            return qualification_result(
                "BLOCKED",
                [
                    "SECONDARY_SOURCE_NOT_AUTHORIZED_FOR_EVENT_TYPE"
                ],
                event,
            )

    return qualification_result(
        "ELIGIBLE",
        ["ALL_QUALIFICATION_GATES_PASSED"],
        event,
    )


def qualify_events(
    events: list[Any],
    qualification_policy: dict[str, Any],
    event_policy: dict[str, Any],
    contract: dict[str, Any],
    known_tickers: set[str],
    registered_sources: set[str],
    sources: dict[str, dict[str, Any]],
    reference_date: date,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for event in events:
        if isinstance(event, dict):
            identity = dedup_identity(
                event,
                qualification_policy,
            )

            if identity in seen:
                results.append(
                    qualification_result(
                        "SUPPRESSED",
                        ["DUPLICATE_EVENT"],
                        event,
                    )
                )
                continue

            seen.add(identity)

        result = qualify_event(
            event=event,
            qualification_policy=qualification_policy,
            event_policy=event_policy,
            contract=contract,
            known_tickers=known_tickers,
            registered_sources=registered_sources,
            sources=sources,
            reference_date=reference_date,
        )

        results.append(result)

    counts = {
        "ELIGIBLE": 0,
        "SUPPRESSED": 0,
        "BLOCKED": 0,
        "UNAVAILABLE": 0,
    }

    for result in results:
        status = result.get("status")

        if status in counts:
            counts[status] += 1

    return {
        "qualification_version": VERSION,
        "reference_date": reference_date.isoformat(),
        "total_events": len(results),
        "eligible_events": counts["ELIGIBLE"],
        "suppressed_events": counts["SUPPRESSED"],
        "blocked_events": counts["BLOCKED"],
        "unavailable_events": counts["UNAVAILABLE"],
        "results": results,
    }


def normalize_payload(payload: Any) -> list[Any] | None:
    if isinstance(payload, list):
        return payload

    if (
        isinstance(payload, dict)
        and isinstance(payload.get("events"), list)
    ):
        return payload["events"]

    if isinstance(payload, dict):
        return [payload]

    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify structurally valid Catalyst Event V3 "
            "records."
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Catalyst event JSON payload.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )

    parser.add_argument(
        "--reference-date",
        type=str,
        default=None,
        help=(
            "Qualification reference date YYYY-MM-DD. "
            "Defaults to current local date."
        ),
    )

    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY,
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        payload = load_json(args.input)
        qualification_policy = load_json(args.policy)
        event_policy = load_json(
            DEFAULT_EVENT_POLICY
        )
        contract = load_json(DEFAULT_CONTRACT)
        universe = load_json(DEFAULT_UNIVERSE)
        registry = load_json(
            DEFAULT_SOURCE_REGISTRY
        )
    except Exception as exc:
        print(
            f"[FATAL] Unable to load qualification "
            f"inputs: {exc}"
        )
        return 2

    events = normalize_payload(payload)

    if events is None:
        print("[FATAL] Invalid catalyst payload.")
        return 2

    if args.reference_date is None:
        reference_date = date.today()
    else:
        reference_date = parse_date(
            args.reference_date
        )

        if reference_date is None:
            print(
                "[FATAL] Invalid --reference-date. "
                "Expected YYYY-MM-DD."
            )
            return 2

    known_tickers = (
        event_validator.extract_known_tickers(
            universe
        )
    )

    registered_sources = (
        event_validator.extract_registered_sources(
            registry
        )
    )

    sources = source_map(registry)

    if not known_tickers:
        print(
            "[FATAL] Asset universe produced zero "
            "known tickers."
        )
        return 2

    if not registered_sources:
        print(
            "[FATAL] Source registry produced zero "
            "registered sources."
        )
        return 2

    result = qualify_events(
        events=events,
        qualification_policy=qualification_policy,
        event_policy=event_policy,
        contract=contract,
        known_tickers=known_tickers,
        registered_sources=registered_sources,
        sources=sources,
        reference_date=reference_date,
    )

    print("=" * 72)
    print("CATALYST QUALIFICATION V3")
    print(f"Version      : {VERSION}")
    print(
        f"Reference    : "
        f"{result['reference_date']}"
    )
    print(
        f"Total        : "
        f"{result['total_events']}"
    )
    print(
        f"ELIGIBLE     : "
        f"{result['eligible_events']}"
    )
    print(
        f"SUPPRESSED   : "
        f"{result['suppressed_events']}"
    )
    print(
        f"BLOCKED      : "
        f"{result['blocked_events']}"
    )
    print(
        f"UNAVAILABLE  : "
        f"{result['unavailable_events']}"
    )
    print("=" * 72)

    for item in result["results"]:
        print(
            f"[{item['status']}] "
            f"{item.get('ticker')} "
            f"{item.get('event_type')} "
            f"{item.get('event_id')} "
            f"| {', '.join(item['reasons'])}"
        )

    if args.output is not None:
        save_json(args.output, result)

    # Qualification execution itself succeeds even when
    # individual events are blocked/suppressed.
    return 0


if __name__ == "__main__":
    sys.exit(main())