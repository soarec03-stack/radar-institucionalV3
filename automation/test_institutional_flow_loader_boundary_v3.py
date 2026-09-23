from __future__ import annotations

import copy
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any


TEST_VERSION = "3.4D.2-B.2E.3"

BASE_DIR = Path(__file__).resolve().parent.parent

ADAPTER_PATH = (
    BASE_DIR
    / "automation"
    / "institutional_flow_signal_integration_adapter_v3.py"
)

LOADER_PATH = (
    BASE_DIR
    / "automation"
    / "metrics_loader_v3.py"
)

SIGNAL_ENGINE_PATH = (
    BASE_DIR
    / "automation"
    / "signal_engine_v3.py"
)

POLICY_PATH = (
    BASE_DIR
    / "automation"
    / "institutional_flow_signal_integration_policy_v3.json"
)

SIGNAL_POLICY_PATH = (
    BASE_DIR
    / "automation"
    / "signal_policy_v3.json"
)

REAL_COMPOSER_PATH = (
    BASE_DIR
    / "input"
    / "institutional_flow_integration_v3.json"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise RuntimeError(
            f"JSON root must be object: {path}"
        )

    return payload


def load_module(
    module_name: str,
    path: Path,
):
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Unable to load module: {path}"
        )

    module = importlib.util.module_from_spec(spec)

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def check(
    name: str,
    condition: bool,
    counters: dict[str, int],
    failures: list[str],
) -> None:
    counters["checks"] += 1

    if condition:
        counters["passed"] += 1
        print(f"[PASS] {name}")
        return

    counters["failed"] += 1
    failures.append(name)
    print(f"[FAIL] {name}")


def sec_provenance() -> dict[str, Any]:
    return {
        "source": "SEC",
        "source_type": "FORM_13F_DATA_SET",
        "tier": "TIER_1",
        "status": "VERIFIED",
        "retrieved_at": "2026-09-16T17:49:25Z",
        "market_date": "30-JUN-2026",
        "previous_market_date": "31-MAR-2026",
        "cusip": "TESTCUSIP",
    }


def finra_provenance() -> dict[str, Any]:
    return {
        "source": "FINRA",
        "source_tier": "TIER_1",
        "dataset": "CONSOLIDATED_SHORT_INTEREST",
        "retrieved_at": "2026-09-16T21:52:29Z",
        "market_date": "2026-08-31",
        "verification_status": "OFFICIAL_SOURCE",
    }


def yahoo_provenance() -> dict[str, Any]:
    return {
        "primary_source": "YAHOO_FINANCE",
        "secondary_source": "SPY",
        "source_url": (
            "https://finance.yahoo.com/quote/TEST/history/"
        ),
        "retrieved_at": "2026-09-13T22:53:01Z",
        "market_date": "2026-09-11",
        "sources_attempted": [
            "YAHOO_FINANCE",
        ],
    }


def integrated_metric(
    metric: str,
    value: float,
    weight: float,
    dimension: str | None,
    counts_as_dimension: bool,
    quality_status: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "metric": metric,
        "value": value,
        "signal_weight": weight,
        "dimension": dimension,
        "counts_as_dimension": counts_as_dimension,
        "quality_status": quality_status,
        "provenance": copy.deepcopy(provenance),
    }


def build_eligible_asset(
    include_volume: bool = False,
) -> dict[str, Any]:
    """
    Positive synthetic Composer fixture.

    Homologated positive case:
      13F + Short Interest
      0.40 + 0.20 = 0.60 weighted coverage
      2 independent institutional dimensions

    volume_ratio can optionally be included as supporting
    market activity.
    """

    metrics = [
        integrated_metric(
            metric="institutional_flow_pct",
            value=-2.5,
            weight=0.4,
            dimension="INSTITUTIONAL_HOLDINGS",
            counts_as_dimension=True,
            quality_status="VERIFIED",
            provenance=sec_provenance(),
        ),
        integrated_metric(
            metric="short_interest_change_pct",
            value=1.25,
            weight=0.2,
            dimension="SHORT_INTEREST",
            counts_as_dimension=True,
            quality_status="VERIFIED",
            provenance=finra_provenance(),
        ),
    ]

    values = {
        "institutional_flow_pct": -2.5,
        "short_interest_change_pct": 1.25,
    }

    coverage = 0.6

    if include_volume:
        metrics.append(
            integrated_metric(
                metric="volume_ratio",
                value=1.2,
                weight=0.2,
                dimension=None,
                counts_as_dimension=False,
                quality_status="AVAILABLE",
                provenance=yahoo_provenance(),
            )
        )

        values["volume_ratio"] = 1.2
        coverage = 0.8

    return {
        "ticker": "TEST",
        "integration_status": "ELIGIBLE",
        "analytically_usable": True,
        "reason": "ELIGIBLE_FOR_SIGNAL_INTEGRATION",
        "weighted_metric_coverage": coverage,
        "institutional_dimension_count": 2,
        "institutional_dimensions": [
            "INSTITUTIONAL_HOLDINGS",
            "SHORT_INTEREST",
        ],
        "integrated_metrics": metrics,
        "excluded_metrics": [
            {
                "metric": "call_put_ratio",
                "reason": "OPTIONS_NOT_YET_HOMOLOGATED",
                "quality_status": "NOT_HOMOLOGATED",
                "analytically_usable": False,
                "diagnostics": [
                    "OPTIONS_NOT_YET_HOMOLOGATED"
                ],
            }
        ],
        "data_point": {
            "value": copy.deepcopy(values),
            "integration_status": "ELIGIBLE",
            "weighted_metric_coverage": coverage,
            "institutional_dimension_count": 2,
            "institutional_dimensions": [
                "INSTITUTIONAL_HOLDINGS",
                "SHORT_INTEREST",
            ],
        },
        "diagnostics": [],
        "raw_inputs": {},
        "master_identity": {
            "ticker": "TEST",
            "listing_exchange": "NASDAQ",
            "cusip": "TESTCUSIP",
            "sec_cik": "0000000001",
        },
        "identity_diagnostics": [],
    }


def build_composer_payload(
    asset: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "3.0",
        "composer": "B.2E.3_SYNTHETIC_FIXTURE",
        "assets": [
            copy.deepcopy(asset)
        ],
    }


def build_radar_fixture() -> dict[str, Any]:
    """
    Minimal structure required by metrics_loader_v3.merge_metrics().

    This test intentionally does not use radar_v3.json.
    """

    return {
        "schema_version": "3.0",
        "assets": [
            {
                "ticker": "TEST",
                "data_points": {},
            }
        ],
    }


def get_asset(
    radar: dict[str, Any],
    ticker: str,
) -> dict[str, Any] | None:
    for asset in radar.get("assets", []):
        if asset.get("ticker") == ticker:
            return asset

    return None


def expected_signal_score(
    signal_engine,
    signal_policy: dict[str, Any],
    metrics: dict[str, Any],
) -> tuple[float | None, float, Any]:
    domain = signal_policy[
        "domains"
    ]["institutional_flow"]

    minimum_coverage = float(
        signal_policy[
            "principles"
        ]["minimum_metric_coverage"]
    )

    return signal_engine.weighted_domain_score(
        metrics,
        domain["metrics"],
        minimum_coverage,
    )


def main() -> int:
    adapter = load_module(
        "institutional_flow_signal_integration_adapter_v3_b2e3",
        ADAPTER_PATH,
    )

    loader = load_module(
        "metrics_loader_v3_b2e3",
        LOADER_PATH,
    )

    signal_engine = load_module(
        "signal_engine_v3_b2e3",
        SIGNAL_ENGINE_PATH,
    )

    integration_policy = load_json(
        POLICY_PATH
    )

    signal_policy = load_json(
        SIGNAL_POLICY_PATH
    )

    counters = {
        "checks": 0,
        "passed": 0,
        "failed": 0,
    }

    failures: list[str] = []

    # =========================================================
    # POSITIVE PATH A
    # 13F + Short Interest
    # Composer -> Adapter -> Loader
    # =========================================================

    composer = build_composer_payload(
        build_eligible_asset(
            include_volume=False
        )
    )

    adapter_result = adapter.adapt_payload(
        composer,
        integration_policy,
    )

    boundary_asset = adapter_result["assets"][0]

    check(
        "01 - Positive Composer asset becomes READY",
        boundary_asset["boundary_status"] == "READY",
        counters,
        failures,
    )

    loader_payload = adapter_result[
        "metrics_loader_payload"
    ]

    check(
        "02 - READY asset reaches Loader payload",
        len(loader_payload["assets"]) == 1
        and loader_payload["assets"][0]["ticker"]
        == "TEST",
        counters,
        failures,
    )

    loader_metrics = (
        loader_payload["assets"][0]
        ["institutional_flow"]["metrics"]
    )

    check(
        "03 - Loader payload contains only authorized metrics",
        set(loader_metrics.keys())
        == {
            "institutional_flow_pct",
            "short_interest_change_pct",
        },
        counters,
        failures,
    )

    check(
        "04 - normalized_score absent before Loader",
        "normalized_score"
        not in loader_metrics,
        counters,
        failures,
    )

    radar_fixture = build_radar_fixture()

    loaded_radar, changes, warnings = (
        loader.merge_metrics(
            radar_fixture,
            loader_payload,
        )
    )

    check(
        "05 - Metrics Loader accepts Adapter payload",
        isinstance(loaded_radar, dict)
        and isinstance(changes, list)
        and isinstance(warnings, list),
        counters,
        failures,
    )

    check(
        "06 - Metrics Loader reports no warning",
        warnings == [],
        counters,
        failures,
    )

    loaded_asset = get_asset(
        loaded_radar,
        "TEST",
    )

    check(
        "07 - TEST asset remains present after Loader",
        isinstance(loaded_asset, dict),
        counters,
        failures,
    )

    institutional_point = (
        loaded_asset
        .get("data_points", {})
        .get("institutional_flow")
        if isinstance(loaded_asset, dict)
        else None
    )

    check(
        "08 - Loader creates institutional_flow data point",
        isinstance(institutional_point, dict),
        counters,
        failures,
    )

    loaded_values = (
        institutional_point.get("value", {})
        if isinstance(institutional_point, dict)
        else {}
    )

    check(
        "09 - Loader preserves authorized metric values",
        loaded_values.get(
            "institutional_flow_pct"
        )
        == -2.5
        and loaded_values.get(
            "short_interest_change_pct"
        )
        == 1.25,
        counters,
        failures,
    )

    check(
        "10 - Loader does not create normalized_score",
        "normalized_score"
        not in loaded_values,
        counters,
        failures,
    )

    loader_provenance = (
        institutional_point.get(
            "provenance"
        )
        if isinstance(
            institutional_point,
            dict,
        )
        else None
    )

    check(
        "11 - Loader creates usable provenance",
        isinstance(loader_provenance, dict)
        and loader_provenance.get(
            "primary_source"
        )
        == "INSTITUTIONAL_FLOW_COMPOSER_V3"
        and loader_provenance.get(
            "status"
        )
        == "PARTIAL",
        counters,
        failures,
    )

    loader_confidence = (
        institutional_point.get(
            "confidence"
        )
        if isinstance(
            institutional_point,
            dict,
        )
        else None
    )

    check(
        "12 - Loader creates conservative initial confidence",
        isinstance(loader_confidence, dict)
        and math.isclose(
            float(
                loader_confidence.get(
                    "score",
                    -1,
                )
            ),
            0.60,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        and loader_confidence.get(
            "status"
        )
        == "PARTIAL",
        counters,
        failures,
    )

    check(
        "13 - Loader records institutional_flow change",
        any(
            change.get("ticker") == "TEST"
            and change.get("domain")
            == "institutional_flow"
            for change in changes
        ),
        counters,
        failures,
    )

    # =========================================================
    # SIGNAL ENGINE AUTHORITY
    # =========================================================

    expected_score, expected_coverage, _ = (
        expected_signal_score(
            signal_engine,
            signal_policy,
            loaded_values,
        )
    )

    check(
        "14 - Positive metrics satisfy Signal Engine coverage",
        expected_score is not None
        and math.isclose(
            float(expected_coverage),
            0.60,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        counters,
        failures,
    )

    # IMPORTANT:
    # apply_signal_engine() returns:
    #
    #   (updated_radar, signal_changes)
    #
    # It does not mutate-only and it does not return only changes.
    signal_radar, signal_changes = (
        signal_engine.apply_signal_engine(
            copy.deepcopy(loaded_radar),
            signal_policy,
        )
    )

    signal_asset = get_asset(
        signal_radar,
        "TEST",
    )

    signal_point = (
        signal_asset
        .get("data_points", {})
        .get("institutional_flow")
        if isinstance(signal_asset, dict)
        else None
    )

    signal_values = (
        signal_point.get("value", {})
        if isinstance(signal_point, dict)
        else {}
    )

    check(
        "15 - Signal Engine creates normalized_score",
        "normalized_score"
        in signal_values
        and isinstance(
            signal_values.get(
                "normalized_score"
            ),
            (int, float),
        ),
        counters,
        failures,
    )

    check(
        "16 - Signal Engine normalized_score matches engine calculation",
        expected_score is not None
        and math.isclose(
            float(
                signal_values[
                    "normalized_score"
                ]
            ),
            float(expected_score),
            rel_tol=0.0,
            abs_tol=1e-9,
        ),
        counters,
        failures,
    )

    check(
        "17 - Signal Engine reports institutional_flow CALCULATED",
        isinstance(signal_changes, list)
        and any(
            isinstance(change, dict)
            and change.get("ticker") == "TEST"
            and isinstance(
                change.get("signals"),
                dict,
            )
            and (
                change["signals"]
                .get(
                    "institutional_flow",
                    {}
                )
                .get("status")
                == "CALCULATED"
            )
            for change in signal_changes
        ),
        counters,
        failures,
    )

    # =========================================================
    # POSITIVE PATH B
    # 13F + SI + supporting volume
    # =========================================================

    composer_volume = build_composer_payload(
        build_eligible_asset(
            include_volume=True
        )
    )

    adapter_volume = adapter.adapt_payload(
        composer_volume,
        integration_policy,
    )

    volume_boundary_asset = (
        adapter_volume["assets"][0]
    )

    check(
        "18 - Positive case with volume becomes READY",
        volume_boundary_asset[
            "boundary_status"
        ]
        == "READY",
        counters,
        failures,
    )

    volume_loader_payload = (
        adapter_volume[
            "metrics_loader_payload"
        ]
    )

    volume_radar, volume_changes, volume_warnings = (
        loader.merge_metrics(
            build_radar_fixture(),
            volume_loader_payload,
        )
    )

    volume_asset = get_asset(
        volume_radar,
        "TEST",
    )

    volume_point = (
        volume_asset
        .get("data_points", {})
        .get("institutional_flow")
        if isinstance(volume_asset, dict)
        else None
    )

    volume_values = (
        volume_point.get("value", {})
        if isinstance(volume_point, dict)
        else {}
    )

    check(
        "19 - Loader preserves supporting volume_ratio",
        volume_warnings == []
        and volume_values.get(
            "volume_ratio"
        )
        == 1.2,
        counters,
        failures,
    )

    volume_expected_score, volume_coverage, _ = (
        expected_signal_score(
            signal_engine,
            signal_policy,
            volume_values,
        )
    )

    check(
        "20 - Signal mathematical coverage becomes 0.80",
        volume_expected_score is not None
        and math.isclose(
            float(volume_coverage),
            0.80,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        counters,
        failures,
    )

    # =========================================================
    # NEGATIVE PATH
    # SUPPRESSED must never reach Loader
    # =========================================================

    suppressed_asset = build_eligible_asset(
        include_volume=True
    )

    # Models the current real condition:
    #
    # 13F + volume can provide 0.60 mathematical weight,
    # but there is only one independent institutional dimension.
    suppressed_asset[
        "integration_status"
    ] = (
        "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS"
    )

    suppressed_asset[
        "analytically_usable"
    ] = False

    suppressed_asset[
        "institutional_dimension_count"
    ] = 1

    suppressed_asset[
        "institutional_dimensions"
    ] = [
        "INSTITUTIONAL_HOLDINGS"
    ]

    suppressed_asset[
        "integrated_metrics"
    ] = [
        metric
        for metric in suppressed_asset[
            "integrated_metrics"
        ]
        if metric["metric"]
        != "short_interest_change_pct"
    ]

    suppressed_asset["data_point"] = None

    suppressed_result = adapter.adapt_payload(
        build_composer_payload(
            suppressed_asset
        ),
        integration_policy,
    )

    check(
        "21 - Noneligible institutional asset is SUPPRESSED",
        suppressed_result[
            "assets"
        ][0]["boundary_status"]
        == "SUPPRESSED",
        counters,
        failures,
    )

    check(
        "22 - SUPPRESSED asset never reaches Loader payload",
        suppressed_result[
            "metrics_loader_payload"
        ]["assets"]
        == [],
        counters,
        failures,
    )

    suppressed_radar, suppressed_changes, suppressed_warnings = (
        loader.merge_metrics(
            build_radar_fixture(),
            suppressed_result[
                "metrics_loader_payload"
            ],
        )
    )

    suppressed_loaded_asset = get_asset(
        suppressed_radar,
        "TEST",
    )

    suppressed_points = (
        suppressed_loaded_asset.get(
            "data_points",
            {},
        )
        if isinstance(
            suppressed_loaded_asset,
            dict,
        )
        else {}
    )

    check(
        "23 - Loader cannot create institutional_flow from SUPPRESSED asset",
        "institutional_flow"
        not in suppressed_points
        and suppressed_changes == []
        and suppressed_warnings == [],
        counters,
        failures,
    )

    # =========================================================
    # RAW BLOCKED SHORT INTEREST LEAKAGE
    # =========================================================

    raw_blocked = copy.deepcopy(
        suppressed_asset
    )

    raw_blocked["raw_inputs"] = {
        "short_interest_quality": {
            "quality_status": "BLOCKED",
            "analytically_usable": False,
            "metric": {
                "value": None,
            },
            "raw_normalized_asset": {
                "short_interest": {
                    "collector_calculated_change_pct": 99.99
                }
            },
        }
    }

    raw_blocked["excluded_metrics"] = [
        {
            "metric": "short_interest_change_pct",
            "reason": "SHORT_INTEREST_NOT_ELIGIBLE",
            "quality_status": "BLOCKED",
            "analytically_usable": False,
            "diagnostics": [
                "UPSTREAM_QUALITY_NOT_ELIGIBLE"
            ],
        }
    ]

    raw_result = adapter.adapt_payload(
        build_composer_payload(
            raw_blocked
        ),
        integration_policy,
    )

    raw_loader_payload = raw_result[
        "metrics_loader_payload"
    ]

    check(
        "24 - Raw BLOCKED Short Interest cannot enter Loader payload",
        raw_result["assets"][0][
            "boundary_status"
        ]
        == "SUPPRESSED"
        and raw_loader_payload["assets"]
        == [],
        counters,
        failures,
    )

    # =========================================================
    # REAL CURRENT PIPELINE
    # =========================================================

    if REAL_COMPOSER_PATH.exists():
        real_composer = load_json(
            REAL_COMPOSER_PATH
        )

        real_adapter = adapter.adapt_payload(
            real_composer,
            integration_policy,
        )

        real_loader_payload = real_adapter[
            "metrics_loader_payload"
        ]

        check(
            "25 - Real pipeline has zero READY Loader assets",
            real_adapter["summary"]["ready"]
            == 0
            and real_adapter["summary"][
                "suppressed"
            ]
            == 3
            and real_adapter["summary"][
                "blocked"
            ]
            == 0
            and real_loader_payload[
                "assets"
            ]
            == [],
            counters,
            failures,
        )

    else:
        check(
            "25 - Real Composer artifact exists",
            False,
            counters,
            failures,
        )

    # =========================================================
    # SOURCE / PROVENANCE SEMANTICS
    # =========================================================

    adapter_source = (
        loader_payload["assets"][0]
        ["institutional_flow"]["source"]
    )

    attempted_sources = (
        adapter_source.get(
            "sources_attempted"
        )
        or []
    )

    check(
        "26 - Composite Loader source does not relabel SEC or FINRA as sole source",
        adapter_source.get(
            "primary_source"
        )
        == "INSTITUTIONAL_FLOW_COMPOSER_V3"
        and "SEC" in attempted_sources
        and "FINRA" in attempted_sources,
        counters,
        failures,
    )

    metric_provenance = (
        boundary_asset[
            "metric_provenance"
        ]
    )

    check(
        "27 - Original SEC and FINRA provenance remains auditable",
        any(
            item["metric"]
            == "institutional_flow_pct"
            and item["provenance"].get(
                "source"
            )
            == "SEC"
            for item in metric_provenance
        )
        and any(
            item["metric"]
            == "short_interest_change_pct"
            and item["provenance"].get(
                "source"
            )
            == "FINRA"
            for item in metric_provenance
        ),
        counters,
        failures,
    )

    check(
        "28 - Different market dates are not collapsed into invented date",
        adapter_source.get(
            "market_date"
        )
        is None,
        counters,
        failures,
    )

    # =========================================================
    # FINAL AUTHORITY CHECK
    # =========================================================

    check(
        "29 - Only Signal Engine added normalized_score",
        "normalized_score"
        not in loader_metrics
        and "normalized_score"
        not in loaded_values
        and "normalized_score"
        in signal_values,
        counters,
        failures,
    )

    # =========================================================
    # SUMMARY
    # =========================================================

    print()
    print(
        "=== B.2E.3 ADAPTER -> METRICS LOADER BOUNDARY ==="
    )
    print(
        f"Version: {TEST_VERSION}"
    )
    print(
        f"Checks: {counters['checks']}"
    )
    print(
        f"Passed: {counters['passed']}"
    )
    print(
        f"Failed: {counters['failed']}"
    )

    if failures:
        print()
        print("Falhas:")

        for failure in failures:
            print(f" - {failure}")

        print()
        print("RESULTADO: FAIL")
        return 1

    print()
    print("RESULTADO: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())