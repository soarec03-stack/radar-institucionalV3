from __future__ import annotations

import copy
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


VERSION = "3.4I.7A-B.2I.7A"
REFERENCE_DATE = date(2026, 9, 27)

BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR))

import catalyst_metrics_composer_v3 as composer
import metrics_loader_v3 as loader
import confidence_engine_v3 as confidence
import signal_engine_v3 as signal


COMPOSER_POLICY = composer.load_json(
    BASE_DIR / "catalyst_metrics_composer_policy_v3.json"
)

INTELLIGENCE_POLICY = composer.load_json(
    BASE_DIR / "catalyst_intelligence_policy_v3.json"
)

SOURCE_REGISTRY = composer.load_json(
    BASE_DIR / "source_registry_v3.json"
)

SIGNAL_POLICY = signal.load_json(
    BASE_DIR / "signal_policy_v3.json"
)


passed = 0
failed = 0


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
        "event_id": "CAT-INTEGRATION-001",
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
            "market_date": "2026-09-27",
        },
    }


def qualified_record(
    event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "ELIGIBLE",
        "event": (
            copy.deepcopy(event)
            if event is not None
            else canonical_event()
        ),
    }


def empty_radar() -> dict[str, Any]:
    return {
        "schema_version": "3.0",
        "radar_run": {},
        "market_regime": {},
        "decision_center": {},
        "assets": [
            {
                "ticker": "VRT",
                "data_points": {},
            }
        ],
        "portfolio": {},
        "scenarios": [],
        "changes": [],
        "sources": [],
    }


def compose_catalyst(
    event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return composer.compose_metrics(
        records=[
            qualified_record(event)
        ],
        reference_date=REFERENCE_DATE,
        composer_policy=COMPOSER_POLICY,
        intelligence_policy=INTELLIGENCE_POLICY,
        registry=SOURCE_REGISTRY,
    )


def build_metrics_input(
    composed: dict[str, Any],
    primary_source: str = "COMPANY_IR",
) -> dict[str, Any]:
    return {
        "assets": [
            {
                "ticker": "VRT",
                "catalysts": {
                    "metrics": copy.deepcopy(
                        composed["metrics"]
                    ),
                    "source": {
                        "primary_source": (
                            primary_source
                        ),
                        "secondary_source": None,
                        "source_url": None,
                        "retrieved_at": (
                            "2026-09-27T12:00:00Z"
                        ),
                        "market_date": (
                            "2026-09-27"
                        ),
                        "sources_attempted": [
                            primary_source
                        ],
                    },
                },
            }
        ]
    }


def get_asset(
    radar: dict[str, Any],
) -> dict[str, Any]:
    return radar["assets"][0]


def get_catalyst_point(
    radar: dict[str, Any],
) -> dict[str, Any]:
    return (
        get_asset(radar)
        ["data_points"]
        ["catalysts"]
    )


def contains_key(
    value: Any,
    key_name: str,
) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == key_name:
                return True

            if contains_key(child, key_name):
                return True

    elif isinstance(value, list):
        for child in value:
            if contains_key(child, key_name):
                return True

    return False


def main() -> int:
    print("=" * 72)
    print(
        "CATALYST LOADER / CONFIDENCE / "
        "SIGNAL INTEGRATION V3"
    )
    print(f"Test version  : {VERSION}")
    print(
        "Reference date: "
        f"{REFERENCE_DATE.isoformat()}"
    )
    print("=" * 72)

    # ----------------------------------------------------------
    # 1. Composer
    # ----------------------------------------------------------

    composed = compose_catalyst()

    check(
        composed["status"] == "READY",
        "Composer produces READY Catalyst metrics.",
    )

    check(
        composed["summary"]["ready_items"] == 1,
        "Composer produces exactly one Catalyst item.",
    )

    composed_item = (
        composed["metrics"]["items"][0]
    )

    check(
        composed_item["signed_impact"] == 75.0,
        "Composer preserves HIGH POSITIVE as +75.",
    )

    check(
        composed_item["probability"] == 1.0,
        "Composer preserves COMPLETED probability 1.0.",
    )

    check(
        composed_item["source_quality"] == 0.95,
        "Composer preserves COMPANY_IR source quality 0.95.",
    )

    check(
        composed_item["horizon_days"] == 0.0,
        "Composer preserves zero completed-event horizon.",
    )

    check(
        "normalized_score"
        not in composed["metrics"],
        "Composer does not precompute normalized_score.",
    )

    # ----------------------------------------------------------
    # 2. Metrics Loader
    # ----------------------------------------------------------

    radar = empty_radar()

    metrics_input = build_metrics_input(
        composed
    )

    loaded, changes, warnings = loader.merge_metrics(
        radar,
        metrics_input,
    )

    point = get_catalyst_point(
        loaded
    )

    check(
        isinstance(point, dict),
        "Loader creates catalysts data point.",
    )

    check(
        point["value"]
        == composed["metrics"],
        "Loader preserves Composer metrics without semantic transformation.",
    )

    check(
        isinstance(
            point.get("value", {}).get(
                "items"
            ),
            list,
        )
        and len(
            point["value"]["items"]
        ) == 1,
        "Loader preserves structured Catalyst items.",
    )

    check(
        point["provenance"][
            "primary_source"
        ] == "COMPANY_IR",
        "Loader preserves COMPANY_IR primary provenance.",
    )

    check(
        point["provenance"]["status"]
        == "PARTIAL",
        "Loader creates initial PARTIAL provenance.",
    )

    check(
        point["confidence"]["score"]
        == 0.60,
        "Loader confidence remains initial 0.60 placeholder.",
    )

    check(
        point["confidence"]["status"]
        == "PARTIAL",
        "Loader initial confidence status is PARTIAL.",
    )

    check(
        "normalized_score"
        not in point["value"],
        "Loader does not invent normalized Catalyst score.",
    )

    # ----------------------------------------------------------
    # 3. Confidence Engine
    # ----------------------------------------------------------

    before_confidence_value = copy.deepcopy(
        point["value"]
    )

    freshness_hours = {
        "MARKET": 24,
        "TECHNICAL": 24,
        "FUNDAMENTAL": 720,
        "CATALYST": 720,
        "INSTITUTIONAL": 720,
        "MACRO": 168,
    }

    with_confidence, confidence_changes = (
        confidence.apply_confidence_engine(
            copy.deepcopy(loaded),
            SOURCE_REGISTRY,
            freshness_hours,
        )
    )

    confidence_point = get_catalyst_point(
        with_confidence
    )

    check(
        confidence_point["value"]
        == before_confidence_value,
        "Confidence Engine does not alter Catalyst metrics.",
    )

    confidence_object = (
        confidence_point["confidence"]
    )

    check(
        isinstance(
            confidence_object.get("score"),
            (int, float),
        ),
        "Confidence Engine recalculates numeric Catalyst confidence.",
    )

    check(
        0.0
        <= confidence_object["score"]
        <= 1.0,
        "Catalyst confidence remains bounded 0..1.",
    )

    check(
        confidence_object["status"]
        in {
            "VERIFIED",
            "PARTIAL",
            "LOW",
            "UNAVAILABLE",
        },
        "Catalyst confidence receives canonical status.",
    )

    check(
        confidence_object["score"]
        != 0.60
        or confidence_object.get(
            "details"
        ),
        "Confidence Engine replaces or substantiates Loader placeholder.",
    )

    check(
        "normalized_score"
        not in confidence_point["value"],
        "Confidence Engine does not calculate Catalyst signal.",
    )

    # ----------------------------------------------------------
    # 4. Signal Engine
    # ----------------------------------------------------------

    before_signal_confidence = (
        copy.deepcopy(
            confidence_point["confidence"]
        )
    )

    with_signal, signal_changes = (
        signal.apply_signal_engine(
            copy.deepcopy(
                with_confidence
            ),
            SIGNAL_POLICY,
        )
    )

    signal_point = get_catalyst_point(
        with_signal
    )

    check(
        "normalized_score"
        in signal_point["value"],
        "Signal Engine creates Catalyst normalized_score.",
    )

    normalized_score = (
        signal_point["value"][
            "normalized_score"
        ]
    )

    check(
        isinstance(
            normalized_score,
            (int, float),
        ),
        "Catalyst normalized_score is numeric.",
    )

    check(
        0.0
        <= normalized_score
        <= 100.0,
        "Catalyst normalized_score is bounded 0..100.",
    )

    # For one completed HIGH POSITIVE event:
    #
    # signed impact = +75
    # probability = 1
    # source quality = .95
    # horizon = 0
    #
    # With one usable event the relative weight
    # cancels in the weighted signed mean.
    #
    # signed = +75
    # score = 50 + 75/2 = 87.5
    check(
        abs(
            normalized_score - 87.5
        ) < 1e-9,
        "Single HIGH POSITIVE Catalyst produces normalized_score 87.5.",
    )

    check(
        signal_point["confidence"]
        == before_signal_confidence,
        "Signal Engine preserves Confidence Engine result.",
    )

    check(
        signal_point["value"]["items"]
        == before_confidence_value[
            "items"
        ],
        "Signal Engine preserves original Catalyst items.",
    )

    # ----------------------------------------------------------
    # 5. Authority boundaries
    # ----------------------------------------------------------

    check(
        not contains_key(
            composed,
            "normalized_score",
        ),
        "normalized_score does not exist before Signal Engine.",
    )

    check(
        not contains_key(
            loaded,
            "radar_score",
        ),
        "Loader does not calculate Radar Score.",
    )

    check(
        not contains_key(
            with_confidence,
            "radar_score",
        ),
        "Confidence Engine does not calculate Radar Score.",
    )

    check(
        not contains_key(
            with_signal,
            "radar_score",
        ),
        "Signal Engine does not calculate Radar Score.",
    )

    check(
        not contains_key(
            with_signal,
            "decision",
        ),
        "Catalyst integration does not create Decision output.",
    )

    # ----------------------------------------------------------
    # 6. Negative Catalyst path
    # ----------------------------------------------------------

    negative_event = canonical_event()
    negative_event["direction"] = "NEGATIVE"
    negative_event["materiality"] = "CRITICAL"
    negative_event["source"][
        "primary_source"
    ] = "SEC"

    negative_composed = compose_catalyst(
        negative_event
    )

    negative_input = build_metrics_input(
        negative_composed,
        primary_source="SEC",
    )

    negative_loaded, negative_changes, negative_warnings = loader.merge_metrics(
        empty_radar(),
        negative_input,
    )

    negative_confidence, negative_confidence_changes = (
        confidence.apply_confidence_engine(
            copy.deepcopy(
                negative_loaded
            ),
            SOURCE_REGISTRY,
            freshness_hours,
        )
    )

    negative_signal, negative_signal_changes = (
        signal.apply_signal_engine(
            copy.deepcopy(
                negative_confidence
            ),
            SIGNAL_POLICY,
        )
    )

    negative_point = get_catalyst_point(
        negative_signal
    )

    check(
        negative_point[
            "value"
        ]["items"][0][
            "signed_impact"
        ] == -100.0,
        "CRITICAL NEGATIVE Catalyst survives integration as -100.",
    )

    check(
        abs(
            negative_point[
                "value"
            ]["normalized_score"]
            - 0.0
        ) < 1e-9,
        "Single CRITICAL NEGATIVE Catalyst produces normalized_score 0.",
    )

    # ----------------------------------------------------------
    # 7. Neutral Catalyst path
    # ----------------------------------------------------------

    neutral_event = canonical_event()
    neutral_event["direction"] = "NEUTRAL"

    neutral_composed = compose_catalyst(
        neutral_event
    )

    neutral_loaded, neutral_changes, neutral_warnings = loader.merge_metrics(
        empty_radar(),
        build_metrics_input(
            neutral_composed
        ),
    )

    neutral_confidence, neutral_confidence_changes = (
        confidence.apply_confidence_engine(
            copy.deepcopy(
                neutral_loaded
            ),
            SOURCE_REGISTRY,
            freshness_hours,
        )
    )

    neutral_signal, neutral_signal_changes = (
        signal.apply_signal_engine(
            copy.deepcopy(
                neutral_confidence
            ),
            SIGNAL_POLICY,
        )
    )

    neutral_score = (
        get_catalyst_point(
            neutral_signal
        )["value"]["normalized_score"]
    )

    check(
        abs(
            neutral_score - 50.0
        ) < 1e-9,
        "Single NEUTRAL Catalyst produces normalized_score 50.",
    )

    # ----------------------------------------------------------
    # 8. Input immutability
    # ----------------------------------------------------------

    original_composed = compose_catalyst()
    original_copy = copy.deepcopy(
        original_composed
    )

    loader.merge_metrics(
        empty_radar(),
        build_metrics_input(
            original_composed
        ),
    )

    check(
        original_composed
        == original_copy,
        "Loader integration does not mutate Composer output.",
    )

    # ----------------------------------------------------------
    # Final
    # ----------------------------------------------------------

    total = passed + failed

    print()
    print("=" * 72)
    print(
        "B.2I.7A CATALYST INTEGRATION RESULT"
    )
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