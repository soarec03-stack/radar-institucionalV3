from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


VERSION = "3.4I.6C-B.2I.6C"

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_COMPOSER_POLICY = (
    BASE_DIR / "catalyst_metrics_composer_policy_v3.json"
)

DEFAULT_INTELLIGENCE_POLICY = (
    BASE_DIR / "catalyst_intelligence_policy_v3.json"
)

DEFAULT_SOURCE_REGISTRY = (
    BASE_DIR / "source_registry_v3.json"
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            payload,
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


def source_map(
    registry: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for source in registry.get("sources", []):
        if not isinstance(source, dict):
            continue

        source_id = source.get("id")

        if is_nonempty_string(source_id):
            result[source_id] = source

    return result


def materiality_weights(
    intelligence_policy: dict[str, Any],
) -> dict[str, float]:
    result: dict[str, float] = {}

    levels = (
        intelligence_policy
        .get("materiality", {})
        .get("levels", {})
    )

    if not isinstance(levels, dict):
        return result

    for level, config in levels.items():
        if not isinstance(config, dict):
            continue

        weight = config.get("weight")

        if (
            isinstance(weight, (int, float))
            and not isinstance(weight, bool)
        ):
            result[str(level)] = float(weight)

    return result


def qualification_status(
    record: dict[str, Any],
) -> str | None:
    """
    Resolve the qualification outcome without silently
    upgrading raw events.

    Canonical qualification output currently exposes status.
    The secondary key is accepted only as a compatibility
    boundary for explicitly wrapped qualification records.
    """

    value = record.get("status")

    if is_nonempty_string(value):
        return value.strip().upper()

    value = record.get("qualification_status")

    if is_nonempty_string(value):
        return value.strip().upper()

    qualification = record.get("qualification")

    if isinstance(qualification, dict):
        value = qualification.get("status")

        if is_nonempty_string(value):
            return value.strip().upper()

    return None


def resolve_event(
    record: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Qualification records may either preserve the raw event
    under `event` or expose the event fields on the same object.
    No missing event field is synthesized here.
    """

    event = record.get("event")

    if isinstance(event, dict):
        return event

    return record


def event_description(
    event: dict[str, Any],
) -> str | None:
    title = event.get("title")

    if is_nonempty_string(title):
        return title.strip()

    evidence = event.get("evidence")

    if isinstance(evidence, dict):
        fact = evidence.get("fact")

        if is_nonempty_string(fact):
            return fact.strip()

    return None


def derive_signed_impact(
    event: dict[str, Any],
    composer_policy: dict[str, Any],
    intelligence_policy: dict[str, Any],
) -> float | None:
    direction = event.get("direction")
    materiality = event.get("materiality")

    if not (
        is_nonempty_string(direction)
        and is_nonempty_string(materiality)
    ):
        return None

    direction_key = direction.strip().upper()
    materiality_key = materiality.strip().upper()

    direction_factors = (
        composer_policy
        .get("signed_impact", {})
        .get("direction_factor", {})
    )

    factor = direction_factors.get(direction_key)

    weights = materiality_weights(
        intelligence_policy
    )

    weight = weights.get(materiality_key)

    if (
        not isinstance(factor, (int, float))
        or isinstance(factor, bool)
        or not isinstance(weight, (int, float))
        or isinstance(weight, bool)
    ):
        return None

    signed = float(factor) * float(weight) * 100.0

    minimum, maximum = (
        composer_policy
        .get("signed_impact", {})
        .get("range", [-100, 100])
    )

    if signed < float(minimum) or signed > float(maximum):
        return None

    if signed == 0:
        return 0.0

    return signed


def derive_probability(
    event: dict[str, Any],
    composer_policy: dict[str, Any],
) -> float | None:
    status = event.get("event_status")

    if not is_nonempty_string(status):
        return None

    status_key = status.strip().upper()

    status_policy = (
        composer_policy
        .get("probability", {})
        .get("by_event_status", {})
        .get(status_key)
    )

    if not isinstance(status_policy, dict):
        return None

    configured_value = status_policy.get("value")

    if (
        isinstance(configured_value, (int, float))
        and not isinstance(configured_value, bool)
    ):
        value = float(configured_value)

        if 0.0 <= value <= 1.0:
            return value

        return None

    # SCHEDULED intentionally has no default probability.
    # If an observable probability has been explicitly supplied
    # by an upstream evidence-producing process, it may be used.
    #
    # The Composer never creates a probability itself.
    observable = event.get("probability")

    if (
        isinstance(observable, (int, float))
        and not isinstance(observable, bool)
    ):
        value = float(observable)

        if 0.0 <= value <= 1.0:
            return value

    return None


def derive_source_quality(
    event: dict[str, Any],
    sources: dict[str, dict[str, Any]],
) -> float | None:
    source = event.get("source")

    if not isinstance(source, dict):
        return None

    primary_source = source.get("primary_source")

    if not is_nonempty_string(primary_source):
        return None

    source_record = sources.get(
        primary_source.strip()
    )

    if not isinstance(source_record, dict):
        return None

    authority = source_record.get("authority_score")

    if (
        not isinstance(authority, (int, float))
        or isinstance(authority, bool)
    ):
        return None

    value = float(authority)

    if not 0.0 <= value <= 1.0:
        return None

    return value


def derive_horizon_days(
    event: dict[str, Any],
    reference_date: date,
) -> float | None:
    status = event.get("event_status")

    if not is_nonempty_string(status):
        return None

    status_key = status.strip().upper()

    if status_key in {"CONFIRMED", "COMPLETED"}:
        return 0.0

    if status_key != "SCHEDULED":
        return None

    event_date = parse_date(
        event.get("event_date")
    )

    if event_date is None:
        return None

    delta = (event_date - reference_date).days

    return float(max(0, delta))


def build_item(
    record: dict[str, Any],
    reference_date: date,
    composer_policy: dict[str, Any],
    intelligence_policy: dict[str, Any],
    sources: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    required_status = (
        composer_policy
        .get("input", {})
        .get(
            "required_qualification_status",
            "ELIGIBLE",
        )
    )

    status = qualification_status(record)

    if status != required_status:
        return (
            None,
            "QUALIFICATION_STATUS_NOT_ELIGIBLE",
        )

    event = resolve_event(record)

    if not isinstance(event, dict):
        return None, "EVENT_NOT_AVAILABLE"

    description = event_description(event)

    if description is None:
        return None, "DESCRIPTION_NOT_DERIVABLE"

    signed_impact = derive_signed_impact(
        event,
        composer_policy,
        intelligence_policy,
    )

    if signed_impact is None:
        return None, "SIGNED_IMPACT_NOT_DERIVABLE"

    probability = derive_probability(
        event,
        composer_policy,
    )

    if probability is None:
        return None, "PROBABILITY_NOT_DERIVABLE"

    source_quality = derive_source_quality(
        event,
        sources,
    )

    if source_quality is None:
        return None, "SOURCE_QUALITY_NOT_DERIVABLE"

    horizon_days = derive_horizon_days(
        event,
        reference_date,
    )

    if horizon_days is None:
        return None, "HORIZON_NOT_DERIVABLE"

    item = {
        "description": description,
        "signed_impact": signed_impact,
        "probability": probability,
        "source_quality": source_quality,
        "horizon_days": horizon_days,
    }

    return item, None


def compose_metrics(
    records: list[Any],
    reference_date: date,
    composer_policy: dict[str, Any],
    intelligence_policy: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    sources = source_map(registry)

    items: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []

    blocked_count = 0
    suppressed_count = 0

    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            blocked_count += 1

            audit.append(
                {
                    "index": index,
                    "status": "BLOCKED",
                    "reason": "RECORD_NOT_OBJECT",
                }
            )
            continue

        q_status = qualification_status(
            raw_record
        )

        if q_status != "ELIGIBLE":
            blocked_count += 1

            audit.append(
                {
                    "index": index,
                    "status": "BLOCKED",
                    "reason": (
                        "QUALIFICATION_STATUS_NOT_ELIGIBLE"
                    ),
                }
            )
            continue

        item, reason = build_item(
            raw_record,
            reference_date,
            composer_policy,
            intelligence_policy,
            sources,
        )

        if item is None:
            suppressed_count += 1

            audit.append(
                {
                    "index": index,
                    "status": "SUPPRESSED",
                    "reason": reason,
                }
            )
            continue

        items.append(item)

        audit.append(
            {
                "index": index,
                "status": "READY",
                "reason": "ITEM_COMPOSED",
            }
        )

    if items:
        overall_status = "READY"
    elif blocked_count > 0:
        overall_status = "BLOCKED"
    else:
        overall_status = "SUPPRESSED"

    return {
        "composer_version": VERSION,
        "status": overall_status,
        "reference_date": reference_date.isoformat(),
        "metrics": {
            "items": items,
        },
        "summary": {
            "input_records": len(records),
            "ready_items": len(items),
            "suppressed_records": suppressed_count,
            "blocked_records": blocked_count,
        },
        "audit": audit,
    }


def normalize_payload(
    payload: Any,
) -> list[Any]:
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return [payload]

    for key in (
        "qualified_events",
        "results",
        "events",
    ):
        value = payload.get(key)

        if isinstance(value, list):
            return value

    # Allow a single qualification record.
    return [payload]


def parse_reference_date(
    value: str | None,
) -> date:
    if value is None:
        return date.today()

    parsed = parse_date(value)

    if parsed is None:
        raise ValueError(
            "reference-date must be YYYY-MM-DD"
        )

    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compose qualified Catalyst Events into "
            "structured catalyst metrics."
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help=(
            "JSON containing qualification records."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output JSON path.",
    )

    parser.add_argument(
        "--reference-date",
        default=None,
        help=(
            "Qualification reference date YYYY-MM-DD. "
            "Defaults to local current date."
        ),
    )

    parser.add_argument(
        "--composer-policy",
        type=Path,
        default=DEFAULT_COMPOSER_POLICY,
    )

    parser.add_argument(
        "--intelligence-policy",
        type=Path,
        default=DEFAULT_INTELLIGENCE_POLICY,
    )

    parser.add_argument(
        "--source-registry",
        type=Path,
        default=DEFAULT_SOURCE_REGISTRY,
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        reference_date = parse_reference_date(
            args.reference_date
        )

        payload = load_json(args.input)

        composer_policy = load_json(
            args.composer_policy
        )

        intelligence_policy = load_json(
            args.intelligence_policy
        )

        registry = load_json(
            args.source_registry
        )

        records = normalize_payload(payload)

        result = compose_metrics(
            records,
            reference_date,
            composer_policy,
            intelligence_policy,
            registry,
        )

        if args.output is not None:
            save_json(
                args.output,
                result,
            )
        else:
            print(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

        return 0

    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
    ) as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())