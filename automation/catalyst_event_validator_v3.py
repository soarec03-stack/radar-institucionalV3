from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


VERSION = "3.4I.4-B.2I.4"

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_CONTRACT = BASE_DIR / "catalyst_event_contract_v3.json"
DEFAULT_POLICY = BASE_DIR / "catalyst_intelligence_policy_v3.json"
DEFAULT_UNIVERSE = BASE_DIR / "asset_universe_v3.json"
DEFAULT_SOURCE_REGISTRY = BASE_DIR / "source_registry_v3.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def extract_known_tickers(universe: Any) -> set[str]:
    """
    Extract canonical tickers from asset_universe_v3.json.

    Current authoritative V3 structure:

        {
            "assets": {
                "VRT": {...},
                "CRSP": {...},
                "ETON": {...}
            }
        }

    Dictionary keys are the canonical ticker identities.

    Limited compatibility with list-based representations is retained so
    this validator remains fail-safe if a controlled future migration
    introduces explicit ticker objects.
    """

    tickers: set[str] = set()

    if not isinstance(universe, dict):
        return tickers

    assets = universe.get("assets")

    if isinstance(assets, dict):
        for ticker in assets.keys():
            if is_nonempty_string(ticker):
                tickers.add(ticker.strip().upper())

        return tickers

    if isinstance(assets, list):
        for asset in assets:
            if isinstance(asset, str):
                if is_nonempty_string(asset):
                    tickers.add(asset.strip().upper())

            elif isinstance(asset, dict):
                ticker = asset.get("ticker")

                if is_nonempty_string(ticker):
                    tickers.add(ticker.strip().upper())

    return tickers


def extract_registered_sources(registry: Any) -> set[str]:
    """
    Extract registered source IDs from source_registry_v3.json.

    Current authoritative V3 structure:

        {
            "sources": [
                {
                    "id": "B3",
                    "tier": "TIER_1",
                    ...
                }
            ]
        }

    The canonical identifier is the "id" field.
    """

    sources: set[str] = set()

    if not isinstance(registry, dict):
        return sources

    raw_sources = registry.get("sources")

    if isinstance(raw_sources, list):
        for item in raw_sources:
            if not isinstance(item, dict):
                continue

            source_id = item.get("id")

            if is_nonempty_string(source_id):
                sources.add(source_id.strip())

        return sources

    if isinstance(raw_sources, dict):
        for source_id in raw_sources.keys():
            if is_nonempty_string(source_id):
                sources.add(source_id.strip())

    return sources


def enum_values(
    contract: dict[str, Any],
    field_name: str,
) -> set[str]:
    return set(
        contract.get("event", {})
        .get("fields", {})
        .get(field_name, {})
        .get("values", [])
    )


def validate_event(
    event: Any,
    contract: dict[str, Any],
    policy: dict[str, Any],
    known_tickers: set[str],
    registered_sources: set[str],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(event, dict):
        return {
            "valid": False,
            "errors": ["EVENT_NOT_OBJECT"],
            "warnings": [],
        }

    event_contract = contract.get("event", {})
    required_fields = event_contract.get("required", [])

    if not isinstance(required_fields, list):
        required_fields = []

    # --------------------------------------------------------------
    # Required top-level fields
    # --------------------------------------------------------------

    for field in required_fields:
        if field not in event or event.get(field) is None:
            errors.append(f"MISSING_REQUIRED_FIELD:{field}")

    # --------------------------------------------------------------
    # Required strings
    # --------------------------------------------------------------

    for field in ("event_id", "event_key", "ticker", "title"):
        if field in event and not is_nonempty_string(event.get(field)):
            errors.append(f"INVALID_STRING:{field}")

    # --------------------------------------------------------------
    # Canonical enums
    # --------------------------------------------------------------

    for field in (
        "event_type",
        "event_status",
        "direction",
        "materiality",
    ):
        value = event.get(field)

        if value is None:
            continue

        allowed = enum_values(contract, field)

        if value not in allowed:
            errors.append(f"INVALID_ENUM:{field}:{value}")

    # --------------------------------------------------------------
    # Event type must also be enabled by policy
    # --------------------------------------------------------------

    event_type = event.get("event_type")

    if is_nonempty_string(event_type):
        event_type_policy = (
            policy.get("event_types", {}).get(event_type)
        )

        if not isinstance(event_type_policy, dict):
            errors.append(
                f"UNKNOWN_POLICY_EVENT_TYPE:{event_type}"
            )
        elif event_type_policy.get("enabled") is not True:
            errors.append(
                f"DISABLED_EVENT_TYPE:{event_type}"
            )

    # --------------------------------------------------------------
    # Dates
    # --------------------------------------------------------------

    if "event_date" in event:
        if parse_date(event.get("event_date")) is None:
            errors.append("INVALID_DATE:event_date")

    announced_at = event.get("announced_at")

    if announced_at is not None:
        if parse_datetime(announced_at) is None:
            errors.append("INVALID_DATETIME:announced_at")

    # --------------------------------------------------------------
    # Asset identity
    # --------------------------------------------------------------

    ticker = event.get("ticker")

    if is_nonempty_string(ticker):
        canonical_ticker = ticker.strip().upper()

        if canonical_ticker not in known_tickers:
            errors.append(
                f"UNKNOWN_ASSET:{canonical_ticker}"
            )

    # --------------------------------------------------------------
    # Evidence
    # --------------------------------------------------------------

    evidence = event.get("evidence")

    if evidence is not None:
        if not isinstance(evidence, dict):
            errors.append("INVALID_OBJECT:evidence")
        else:
            if not is_nonempty_string(evidence.get("fact")):
                errors.append("MISSING_EVIDENCE_FACT")

    # --------------------------------------------------------------
    # Source
    # --------------------------------------------------------------

    source = event.get("source")

    if source is not None:
        if not isinstance(source, dict):
            errors.append("INVALID_OBJECT:source")
        else:
            primary_source = source.get("primary_source")

            if not is_nonempty_string(primary_source):
                errors.append("MISSING_SOURCE_PRIMARY")
            elif primary_source.strip() not in registered_sources:
                errors.append(
                    f"UNREGISTERED_SOURCE:"
                    f"{primary_source.strip()}"
                )

            retrieved_at = source.get("retrieved_at")

            if not is_nonempty_string(retrieved_at):
                errors.append(
                    "MISSING_SOURCE_RETRIEVED_AT"
                )
            elif parse_datetime(retrieved_at) is None:
                errors.append(
                    "INVALID_DATETIME:source.retrieved_at"
                )

            market_date = source.get("market_date")

            if market_date is not None:
                if parse_date(market_date) is None:
                    errors.append(
                        "INVALID_DATE:source.market_date"
                    )

            secondary_source = source.get(
                "secondary_source"
            )

            if secondary_source is not None:
                if not is_nonempty_string(secondary_source):
                    errors.append(
                        "INVALID_SOURCE_SECONDARY"
                    )
                elif (
                    secondary_source.strip()
                    not in registered_sources
                ):
                    errors.append(
                        "UNREGISTERED_SECONDARY_SOURCE:"
                        f"{secondary_source.strip()}"
                    )

    # --------------------------------------------------------------
    # Structural warnings only
    #
    # The future qualification layer remains authoritative for
    # direction/materiality eligibility.
    # --------------------------------------------------------------

    direction = event.get("direction")

    if direction in {
        "POSITIVE",
        "NEGATIVE",
        "NEUTRAL",
    }:
        if not is_nonempty_string(
            event.get("direction_reason")
        ):
            warnings.append(
                "MISSING_DIRECTION_REASON"
            )

    materiality = event.get("materiality")

    if materiality in {
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }:
        if not is_nonempty_string(
            event.get("materiality_reason")
        ):
            warnings.append(
                "MISSING_MATERIALITY_REASON"
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def validate_payload(
    payload: Any,
    contract: dict[str, Any],
    policy: dict[str, Any],
    known_tickers: set[str],
    registered_sources: set[str],
) -> dict[str, Any]:
    if isinstance(payload, list):
        events = payload

    elif (
        isinstance(payload, dict)
        and isinstance(payload.get("events"), list)
    ):
        events = payload["events"]

    elif isinstance(payload, dict):
        events = [payload]

    else:
        return {
            "validator_version": VERSION,
            "valid": False,
            "total_events": 0,
            "valid_events": 0,
            "invalid_events": 0,
            "results": [
                {
                    "index": None,
                    "event_id": None,
                    "ticker": None,
                    "valid": False,
                    "errors": ["INVALID_PAYLOAD"],
                    "warnings": [],
                }
            ],
        }

    results: list[dict[str, Any]] = []
    valid_count = 0

    for index, event in enumerate(events):
        result = validate_event(
            event=event,
            contract=contract,
            policy=policy,
            known_tickers=known_tickers,
            registered_sources=registered_sources,
        )

        if result["valid"]:
            valid_count += 1

        results.append(
            {
                "index": index,
                "event_id": (
                    event.get("event_id")
                    if isinstance(event, dict)
                    else None
                ),
                "ticker": (
                    event.get("ticker")
                    if isinstance(event, dict)
                    else None
                ),
                **result,
            }
        )

    invalid_count = len(events) - valid_count

    return {
        "validator_version": VERSION,
        "valid": invalid_count == 0,
        "total_events": len(events),
        "valid_events": valid_count,
        "invalid_events": invalid_count,
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Catalyst Event Contract V3 payloads."
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Catalyst event JSON file.",
    )

    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
    )

    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY,
    )

    parser.add_argument(
        "--universe",
        type=Path,
        default=DEFAULT_UNIVERSE,
    )

    parser.add_argument(
        "--source-registry",
        type=Path,
        default=DEFAULT_SOURCE_REGISTRY,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional validation-result JSON file.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        payload = load_json(args.input)
        contract = load_json(args.contract)
        policy = load_json(args.policy)
        universe = load_json(args.universe)
        registry = load_json(args.source_registry)
    except Exception as exc:
        print(
            f"[FATAL] Unable to load validator inputs: {exc}"
        )
        return 2

    known_tickers = extract_known_tickers(universe)
    registered_sources = extract_registered_sources(
        registry
    )

    if not known_tickers:
        print(
            "[FATAL] Asset universe produced zero known "
            "tickers."
        )
        return 2

    if not registered_sources:
        print(
            "[FATAL] Source registry produced zero "
            "registered sources."
        )
        return 2

    result = validate_payload(
        payload=payload,
        contract=contract,
        policy=policy,
        known_tickers=known_tickers,
        registered_sources=registered_sources,
    )

    print("=" * 72)
    print("CATALYST EVENT VALIDATOR V3")
    print(f"Validator version : {VERSION}")
    print(
        f"Known tickers     : "
        f"{', '.join(sorted(known_tickers))}"
    )
    print(
        f"Registered sources: "
        f"{len(registered_sources)}"
    )
    print(f"Total events      : {result['total_events']}")
    print(f"Valid events      : {result['valid_events']}")
    print(
        f"Invalid events    : "
        f"{result['invalid_events']}"
    )
    print(
        "RESULT            :",
        "PASS" if result["valid"] else "FAIL",
    )
    print("=" * 72)

    for item in result["results"]:
        status = "PASS" if item["valid"] else "FAIL"

        print(
            f"[{status}] index={item['index']} "
            f"event_id={item['event_id']} "
            f"ticker={item['ticker']}"
        )

        for error in item["errors"]:
            print(f"  ERROR   {error}")

        for warning in item["warnings"]:
            print(f"  WARNING {warning}")

    if args.output is not None:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with args.output.open(
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                result,
                f,
                ensure_ascii=False,
                indent=2,
            )
            f.write("\n")

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())