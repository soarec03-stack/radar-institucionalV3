from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent

ADAPTER_PATH = (
    BASE_DIR
    / "automation"
    / "institutional_flow_signal_integration_adapter_v3.py"
)

POLICY_PATH = (
    BASE_DIR
    / "automation"
    / "institutional_flow_signal_integration_policy_v3.json"
)

REAL_COMPOSER_PATH = (
    BASE_DIR
    / "input"
    / "institutional_flow_integration_v3.json"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_adapter():
    spec = importlib.util.spec_from_file_location(
        "institutional_flow_signal_integration_adapter_v3",
        ADAPTER_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Unable to load B.2E.2 adapter."
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
    counts: bool,
    quality: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "metric": metric,
        "value": value,
        "signal_weight": weight,
        "dimension": dimension,
        "counts_as_dimension": counts,
        "quality_status": quality,
        "provenance": copy.deepcopy(provenance),
    }


def eligible_asset(
    include_volume: bool = False,
) -> dict[str, Any]:
    metrics = [
        integrated_metric(
            metric="institutional_flow_pct",
            value=-2.5,
            weight=0.4,
            dimension="INSTITUTIONAL_HOLDINGS",
            counts=True,
            quality="VERIFIED",
            provenance=sec_provenance(),
        ),
        integrated_metric(
            metric="short_interest_change_pct",
            value=1.25,
            weight=0.2,
            dimension="SHORT_INTEREST",
            counts=True,
            quality="VERIFIED",
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
                counts=False,
                quality="AVAILABLE",
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
            "value": values,
            "integration_status": "ELIGIBLE",
            "weighted_metric_coverage": coverage,
            "institutional_dimension_count": 2,
            "institutional_dimensions": [
                "INSTITUTIONAL_HOLDINGS",
                "SHORT_INTEREST",
            ],
        },
        "diagnostics": [],
        "raw_inputs": {
            "institutional_holdings": {
                "audit_only": True,
            },
            "short_interest_quality": {
                "audit_only": True,
            },
            "technical_metrics": {
                "audit_only": True,
            },
        },
        "master_identity": {
            "ticker": "TEST",
            "listing_exchange": "NASDAQ",
            "cusip": "TESTCUSIP",
            "sec_cik": "0000000001",
        },
        "identity_diagnostics": [],
    }


def composer_payload(
    asset: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "3.0",
        "composer": "TEST_COMPOSER",
        "assets": [asset],
    }


def main() -> int:
    adapter = load_adapter()
    policy = load_json(POLICY_PATH)

    counters = {
        "checks": 0,
        "passed": 0,
        "failed": 0,
    }

    failures: list[str] = []

    # ---------------------------------------------------------
    # 01 - Positive: 13F + Short Interest
    # ---------------------------------------------------------
    result = adapter.adapt_payload(
        composer_payload(
            eligible_asset(
                include_volume=False
            )
        ),
        policy,
    )

    asset_result = result["assets"][0]

    check(
        "01 - ELIGIBLE becomes READY",
        asset_result["boundary_status"] == "READY",
        counters,
        failures,
    )

    check(
        "02 - READY publishes exactly authorized metrics",
        set(asset_result["metrics"].keys())
        == {
            "institutional_flow_pct",
            "short_interest_change_pct",
        },
        counters,
        failures,
    )

    check(
        "03 - READY produces loader-compatible domain block",
        asset_result["loader_payload"]["ticker"]
        == "TEST"
        and set(
            asset_result[
                "loader_payload"
            ]["institutional_flow"]["metrics"].keys()
        )
        == {
            "institutional_flow_pct",
            "short_interest_change_pct",
        }
        and isinstance(
            asset_result[
                "loader_payload"
            ]["institutional_flow"]["source"],
            dict,
        ),
        counters,
        failures,
    )

    check(
        "04 - normalized_score is absent before Signal Engine",
        "normalized_score"
        not in asset_result["metrics"],
        counters,
        failures,
    )

    check(
        "05 - metric provenance is preserved",
        len(asset_result["metric_provenance"]) == 2
        and {
            x["metric"]
            for x in asset_result["metric_provenance"]
        }
        == {
            "institutional_flow_pct",
            "short_interest_change_pct",
        },
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 02 - Positive with supporting volume
    # ---------------------------------------------------------
    result = adapter.adapt_payload(
        composer_payload(
            eligible_asset(
                include_volume=True
            )
        ),
        policy,
    )

    asset_result = result["assets"][0]

    check(
        "06 - ELIGIBLE with volume remains READY",
        asset_result["boundary_status"] == "READY"
        and set(asset_result["metrics"].keys())
        == {
            "institutional_flow_pct",
            "short_interest_change_pct",
            "volume_ratio",
        },
        counters,
        failures,
    )

    check(
        "07 - Yahoo provenance remains metric-level",
        any(
            x["metric"] == "volume_ratio"
            and (
                x["provenance"].get(
                    "primary_source"
                )
                == "YAHOO_FINANCE"
            )
            for x in asset_result[
                "metric_provenance"
            ]
        ),
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 03 - ELIGIBLE + usable false
    # ---------------------------------------------------------
    case = eligible_asset()
    case["analytically_usable"] = False

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "08 - ELIGIBLE plus usable false is BLOCKED",
        result["assets"][0]["boundary_status"]
        == "BLOCKED",
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 04 - ELIGIBLE + null data point
    # ---------------------------------------------------------
    case = eligible_asset()
    case["data_point"] = None

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "09 - ELIGIBLE plus null data_point is BLOCKED",
        result["assets"][0]["boundary_status"]
        == "BLOCKED",
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 05 - Noneligible with non-null data point
    # ---------------------------------------------------------
    case = eligible_asset()
    case["integration_status"] = (
        "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS"
    )
    case["analytically_usable"] = False

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "10 - Noneligible with data_point is BLOCKED",
        result["assets"][0]["boundary_status"]
        == "BLOCKED",
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 06 - Correct suppression
    # ---------------------------------------------------------
    case = eligible_asset()
    case["integration_status"] = (
        "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS"
    )
    case["analytically_usable"] = False
    case["data_point"] = None

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "11 - Correct noneligible contract is SUPPRESSED",
        result["assets"][0]["boundary_status"]
        == "SUPPRESSED"
        and result["assets"][0][
            "metrics_published"
        ]
        is False,
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 07 - Unknown metric
    # ---------------------------------------------------------
    case = eligible_asset()

    case["data_point"]["value"][
        "invented_metric"
    ] = 10.0

    case["integrated_metrics"].append(
        integrated_metric(
            metric="invented_metric",
            value=10.0,
            weight=0.1,
            dimension=None,
            counts=False,
            quality="AVAILABLE",
            provenance=sec_provenance(),
        )
    )

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "12 - Unknown metric is BLOCKED",
        result["assets"][0]["boundary_status"]
        == "BLOCKED",
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 08 - normalized_score upstream
    # ---------------------------------------------------------
    case = eligible_asset()

    case["data_point"]["value"][
        "normalized_score"
    ] = 55.0

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "13 - Upstream normalized_score is BLOCKED",
        result["assets"][0]["boundary_status"]
        == "BLOCKED",
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 09 - Invalid volume
    # ---------------------------------------------------------
    case = eligible_asset(
        include_volume=True
    )

    case["data_point"]["value"][
        "volume_ratio"
    ] = -1.0

    for item in case["integrated_metrics"]:
        if item["metric"] == "volume_ratio":
            item["value"] = -1.0

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "14 - Negative volume_ratio is BLOCKED",
        result["assets"][0]["boundary_status"]
        == "BLOCKED",
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 10 - Missing provenance
    # ---------------------------------------------------------
    case = eligible_asset()
    case["integrated_metrics"][0][
        "provenance"
    ] = {}

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "15 - Missing metric provenance is BLOCKED",
        result["assets"][0]["boundary_status"]
        == "BLOCKED",
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 11 - Value mismatch
    # ---------------------------------------------------------
    case = eligible_asset()

    case["integrated_metrics"][0][
        "value"
    ] = -99.0

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "16 - Composer value mismatch is BLOCKED",
        result["assets"][0]["boundary_status"]
        == "BLOCKED",
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 12 - Identity mismatch
    # ---------------------------------------------------------
    case = eligible_asset()

    case["master_identity"]["ticker"] = "OTHER"

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "17 - Identity mismatch is BLOCKED",
        result["assets"][0]["boundary_status"]
        == "BLOCKED",
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 13 - BLOCKED raw SI cannot leak
    # ---------------------------------------------------------
    case = eligible_asset()

    # Remove legitimate SI from authorized Composer output.
    case["integrated_metrics"] = [
        x
        for x in case["integrated_metrics"]
        if x["metric"]
        != "short_interest_change_pct"
    ]

    case["data_point"]["value"].pop(
        "short_interest_change_pct"
    )

    # Make asset noneligible, exactly as Composer should.
    case["integration_status"] = (
        "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS"
    )
    case["analytically_usable"] = False
    case["data_point"] = None

    # Raw blocked value exists only in audit.
    case["raw_inputs"][
        "short_interest_quality"
    ] = {
        "quality_status": "BLOCKED",
        "metric": {
            "value": None,
        },
        "raw_normalized_asset": {
            "short_interest": {
                "collector_calculated_change_pct": 9.99
            }
        },
    }

    case["excluded_metrics"].append(
        {
            "metric": "short_interest_change_pct",
            "reason": "SHORT_INTEREST_NOT_ELIGIBLE",
            "quality_status": "BLOCKED",
            "analytically_usable": False,
            "diagnostics": [
                "UPSTREAM_QUALITY_NOT_ELIGIBLE"
            ],
        }
    )

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    asset_result = result["assets"][0]

    check(
        "18 - BLOCKED raw Short Interest cannot leak",
        asset_result["boundary_status"]
        == "SUPPRESSED"
        and asset_result["metrics"] == {}
        and asset_result["loader_payload"] is None,
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 14 - Unknown Composer status
    # ---------------------------------------------------------
    case = eligible_asset()
    case["integration_status"] = "MYSTERY_STATUS"

    result = adapter.adapt_payload(
        composer_payload(case),
        policy,
    )

    check(
        "19 - Unknown Composer status is BLOCKED",
        result["assets"][0]["boundary_status"]
        == "BLOCKED",
        counters,
        failures,
    )

    # ---------------------------------------------------------
    # 15 - Real pipeline
    # ---------------------------------------------------------
    if REAL_COMPOSER_PATH.exists():
        real_payload = load_json(
            REAL_COMPOSER_PATH
        )

        real_result = adapter.adapt_payload(
            real_payload,
            policy,
        )

        by_ticker = {
            x["ticker"]: x
            for x in real_result["assets"]
        }

        real_expected = all(
            ticker in by_ticker
            and by_ticker[ticker][
                "boundary_status"
            ]
            == "SUPPRESSED"
            and by_ticker[ticker][
                "metrics_published"
            ]
            is False
            for ticker in (
                "CRSP",
                "ETON",
                "VRT",
            )
        )

        check(
            "20 - Real CRSP ETON VRT are SUPPRESSED",
            real_expected,
            counters,
            failures,
        )

        check(
            "21 - Real pipeline publishes zero metrics",
            real_result["summary"]["ready"] == 0
            and real_result["summary"][
                "suppressed"
            ]
            == 3
            and real_result["summary"][
                "blocked"
            ]
            == 0
            and real_result["summary"][
                "metrics_published"
            ]
            == 0
            and real_result[
                "metrics_loader_payload"
            ]["assets"]
            == [],
            counters,
            failures,
        )

    else:
        check(
            "20 - Real Composer artifact exists",
            False,
            counters,
            failures,
        )

        check(
            "21 - Real pipeline publishes zero metrics",
            False,
            counters,
            failures,
        )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------
    print()
    print(
        "=== B.2E.2 ADAPTER REGRESSION TEST ==="
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