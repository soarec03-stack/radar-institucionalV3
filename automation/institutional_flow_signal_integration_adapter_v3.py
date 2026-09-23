from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ADAPTER_VERSION = "3.4D.2-B.2E.2"

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_POLICY_PATH = (
    BASE_DIR
    / "automation"
    / "institutional_flow_signal_integration_policy_v3.json"
)

DEFAULT_COMPOSER_PATH = (
    BASE_DIR
    / "input"
    / "institutional_flow_integration_v3.json"
)

DEFAULT_OUTPUT_PATH = (
    BASE_DIR
    / "input"
    / "institutional_flow_signal_integration_v3.json"
)


ALLOWED_METRICS = {
    "institutional_flow_pct",
    "volume_ratio",
    "short_interest_change_pct",
    "call_put_ratio",
}

KNOWN_NON_ELIGIBLE_STATUSES = {
    "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS",
    "INSUFFICIENT_WEIGHTED_COVERAGE",
    "UNAVAILABLE",
}

FORBIDDEN_RECOVERY_PATHS = {
    "raw_inputs",
    "raw_normalized_asset",
    "raw_boundary_asset",
    "raw_upstream",
    "excluded_metrics",
    "technical_metrics",
}

FORBIDDEN_UPSTREAM_METRIC_KEYS = {
    "normalized_score",
}


class IntegrationError(RuntimeError):
    pass


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise IntegrationError(
            f"JSON root must be an object: {path}"
        )

    return payload


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")


def is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def normalize_source_name(provenance: dict[str, Any]) -> str | None:
    primary = provenance.get("primary_source")

    if isinstance(primary, str) and primary.strip():
        return primary.strip()

    source = provenance.get("source")

    if isinstance(source, str) and source.strip():
        return source.strip()

    return None


def normalize_source_url(
    provenance: dict[str, Any],
) -> str | None:
    value = provenance.get("source_url")

    if isinstance(value, str) and value.strip():
        return value.strip()

    return None


def normalize_retrieved_at(
    provenance: dict[str, Any],
) -> str | None:
    value = provenance.get("retrieved_at")

    if isinstance(value, str) and value.strip():
        return value.strip()

    return None


def normalize_market_date(
    provenance: dict[str, Any],
) -> str | None:
    value = provenance.get("market_date")

    if isinstance(value, str) and value.strip():
        return value.strip()

    return None


def normalize_sources_attempted(
    provenance: dict[str, Any],
) -> list[str]:
    attempted = provenance.get("sources_attempted")

    result: list[str] = []

    if isinstance(attempted, list):
        for item in attempted:
            if (
                isinstance(item, str)
                and item.strip()
                and item.strip() not in result
            ):
                result.append(item.strip())

    primary = normalize_source_name(provenance)

    if primary and primary not in result:
        result.insert(0, primary)

    secondary = provenance.get("secondary_source")

    if (
        isinstance(secondary, str)
        and secondary.strip()
        and secondary.strip() not in result
    ):
        result.append(secondary.strip())

    return result


def metric_bounds_valid(
    metric_name: str,
    value: float,
) -> bool:
    if metric_name in {
        "volume_ratio",
        "call_put_ratio",
    }:
        return value >= 0.0

    return True


def extract_data_point_values(
    data_point: dict[str, Any],
) -> dict[str, Any]:
    value = data_point.get("value")

    if not isinstance(value, dict):
        raise IntegrationError(
            "ELIGIBLE data_point.value must be an object."
        )

    if not value:
        raise IntegrationError(
            "ELIGIBLE data_point.value cannot be empty."
        )

    return copy.deepcopy(value)


def build_metric_index(
    integrated_metrics: Any,
) -> dict[str, dict[str, Any]]:
    if not isinstance(integrated_metrics, list):
        raise IntegrationError(
            "integrated_metrics must be an array."
        )

    index: dict[str, dict[str, Any]] = {}

    for item in integrated_metrics:
        if not isinstance(item, dict):
            raise IntegrationError(
                "integrated_metrics contains a non-object item."
            )

        metric_name = item.get("metric")

        if (
            not isinstance(metric_name, str)
            or not metric_name.strip()
        ):
            raise IntegrationError(
                "integrated metric without valid metric name."
            )

        metric_name = metric_name.strip()

        if metric_name in index:
            raise IntegrationError(
                f"duplicate integrated metric: {metric_name}"
            )

        index[metric_name] = item

    return index


def validate_identity(asset: dict[str, Any]) -> None:
    ticker = asset.get("ticker")
    master_identity = asset.get("master_identity")
    diagnostics = asset.get("identity_diagnostics")

    if not isinstance(ticker, str) or not ticker.strip():
        raise IntegrationError(
            "asset ticker is missing."
        )

    if diagnostics:
        raise IntegrationError(
            f"{ticker}: identity_diagnostics is not empty."
        )

    if master_identity is None:
        return

    if not isinstance(master_identity, dict):
        raise IntegrationError(
            f"{ticker}: master_identity must be an object."
        )

    master_ticker = master_identity.get("ticker")

    if (
        isinstance(master_ticker, str)
        and master_ticker.strip()
        and master_ticker.strip() != ticker.strip()
    ):
        raise IntegrationError(
            f"{ticker}: master identity ticker mismatch."
        )


def validate_policy(policy: dict[str, Any]) -> None:
    if (
        policy.get("policy_version")
        != "3.4D.2-B.2E.1"
    ):
        raise IntegrationError(
            "Unsupported B.2E.1 policy version."
        )

    principles = policy.get("principles")

    if not isinstance(principles, dict):
        raise IntegrationError(
            "Policy principles are missing."
        )

    required_true = {
        "policy_before_code",
        "fail_closed",
        "missing_is_not_neutral",
        "missing_is_not_zero",
        "do_not_invent_metrics",
        "composer_is_authoritative_for_institutional_eligibility",
        "integration_does_not_recalculate_composer_eligibility",
        "metrics_loader_remains_authoritative_for_data_point_construction",
        "signal_engine_remains_authoritative_for_normalized_score",
        "integration_does_not_calculate_normalized_score",
    }

    for key in required_true:
        if principles.get(key) is not True:
            raise IntegrationError(
                f"Required policy principle not enabled: {key}"
            )


def validate_ready_asset(
    asset: dict[str, Any],
) -> tuple[
    dict[str, float],
    list[dict[str, Any]],
]:
    ticker = asset["ticker"]

    if asset.get("integration_status") != "ELIGIBLE":
        raise IntegrationError(
            f"{ticker}: READY validation requires ELIGIBLE."
        )

    if asset.get("analytically_usable") is not True:
        raise IntegrationError(
            f"{ticker}: ELIGIBLE asset is not analytically usable."
        )

    data_point = asset.get("data_point")

    if not isinstance(data_point, dict):
        raise IntegrationError(
            f"{ticker}: ELIGIBLE asset has null/invalid data_point."
        )

    if (
        data_point.get("integration_status")
        != "ELIGIBLE"
    ):
        raise IntegrationError(
            f"{ticker}: data_point integration status mismatch."
        )

    values = extract_data_point_values(data_point)

    forbidden_in_values = (
        set(values.keys())
        & FORBIDDEN_UPSTREAM_METRIC_KEYS
    )

    if forbidden_in_values:
        raise IntegrationError(
            f"{ticker}: forbidden upstream engine output: "
            f"{sorted(forbidden_in_values)}"
        )

    unknown_metrics = (
        set(values.keys()) - ALLOWED_METRICS
    )

    if unknown_metrics:
        raise IntegrationError(
            f"{ticker}: unknown metrics in data_point: "
            f"{sorted(unknown_metrics)}"
        )

    metric_index = build_metric_index(
        asset.get("integrated_metrics")
    )

    if set(metric_index.keys()) != set(values.keys()):
        raise IntegrationError(
            f"{ticker}: data_point.value and integrated_metrics "
            "do not contain the same authorized metrics."
        )

    clean_values: dict[str, float] = {}
    metric_audit: list[dict[str, Any]] = []

    for metric_name, raw_value in values.items():
        if not is_number(raw_value):
            raise IntegrationError(
                f"{ticker}: metric {metric_name} "
                "is not a finite numeric value."
            )

        numeric_value = float(raw_value)

        if not metric_bounds_valid(
            metric_name,
            numeric_value,
        ):
            raise IntegrationError(
                f"{ticker}: invalid bounds for "
                f"{metric_name}: {numeric_value}"
            )

        item = metric_index[metric_name]

        integrated_value = item.get("value")

        if not is_number(integrated_value):
            raise IntegrationError(
                f"{ticker}: integrated metric "
                f"{metric_name} has invalid value."
            )

        if not math.isclose(
            numeric_value,
            float(integrated_value),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise IntegrationError(
                f"{ticker}: value mismatch for "
                f"{metric_name}."
            )

        provenance = item.get("provenance")

        if not isinstance(provenance, dict):
            raise IntegrationError(
                f"{ticker}: provenance missing for "
                f"{metric_name}."
            )

        source_name = normalize_source_name(
            provenance
        )
        retrieved_at = normalize_retrieved_at(
            provenance
        )

        if not source_name or not retrieved_at:
            raise IntegrationError(
                f"{ticker}: provenance unusable for "
                f"{metric_name}."
            )

        clean_values[metric_name] = numeric_value

        metric_audit.append(
            {
                "metric": metric_name,
                "value": numeric_value,
                "signal_weight": item.get(
                    "signal_weight"
                ),
                "dimension": item.get(
                    "dimension"
                ),
                "counts_as_dimension": item.get(
                    "counts_as_dimension"
                ),
                "quality_status": item.get(
                    "quality_status"
                ),
                "provenance": copy.deepcopy(
                    provenance
                ),
            }
        )

    if not clean_values:
        raise IntegrationError(
            f"{ticker}: no metrics available after validation."
        )

    return clean_values, metric_audit


def build_loader_source(
    metric_audit: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Metrics Loader currently accepts one source object per domain.

    Institutional Flow is a composite domain, so this adapter does NOT
    pretend that SEC, FINRA or Yahoo is the sole source.

    The Loader-facing source is therefore explicitly identified as the
    homologated B.2D Composer boundary. Original metric-level provenance
    remains preserved in metric_provenance in the adapter output.

    No source tier is upgraded or invented.
    """

    if not metric_audit:
        raise IntegrationError(
            "Cannot build Loader source without metric audit."
        )

    retrieved_values: list[str] = []
    market_dates: list[str] = []
    attempted: list[str] = []

    for item in metric_audit:
        provenance = item["provenance"]

        retrieved_at = normalize_retrieved_at(
            provenance
        )

        market_date = normalize_market_date(
            provenance
        )

        if retrieved_at:
            retrieved_values.append(
                retrieved_at
            )

        if market_date:
            market_dates.append(
                market_date
            )

        for source_name in normalize_sources_attempted(
            provenance
        ):
            if source_name not in attempted:
                attempted.append(source_name)

    if not retrieved_values:
        raise IntegrationError(
            "Composite provenance has no retrieved_at."
        )

    # Conservative boundary timestamp:
    # use the oldest retrieval timestamp among the contributing metrics.
    composite_retrieved_at = min(retrieved_values)

    # Institutional metrics can legitimately have different market dates
    # (13F quarter-end, SI settlement, market-volume date).
    # Do not fabricate one canonical market date.
    composite_market_date = (
        market_dates[0]
        if len(set(market_dates)) == 1
        else None
    )

    source = {
        "primary_source": "INSTITUTIONAL_FLOW_COMPOSER_V3",
        "secondary_source": None,
        "source_url": None,
        "retrieved_at": composite_retrieved_at,
        "market_date": composite_market_date,
        "sources_attempted": (
            ["INSTITUTIONAL_FLOW_COMPOSER_V3"]
            + [
                name
                for name in attempted
                if name
                != "INSTITUTIONAL_FLOW_COMPOSER_V3"
            ]
        ),
    }

    return source


def suppressed_result(
    asset: dict[str, Any],
) -> dict[str, Any]:
    ticker = asset.get("ticker")

    return {
        "ticker": ticker,
        "boundary_status": "SUPPRESSED",
        "composer_integration_status": asset.get(
            "integration_status"
        ),
        "composer_analytically_usable": asset.get(
            "analytically_usable"
        ),
        "reason": (
            "COMPOSER_NOT_ELIGIBLE_FOR_SIGNAL_INTEGRATION"
        ),
        "metrics_published": False,
        "metrics": {},
        "loader_payload": None,
        "metric_provenance": [],
        "diagnostics": copy.deepcopy(
            asset.get("diagnostics") or []
        ),
    }


def blocked_result(
    asset: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "ticker": asset.get("ticker"),
        "boundary_status": "BLOCKED",
        "composer_integration_status": asset.get(
            "integration_status"
        ),
        "composer_analytically_usable": asset.get(
            "analytically_usable"
        ),
        "reason": reason,
        "metrics_published": False,
        "metrics": {},
        "loader_payload": None,
        "metric_provenance": [],
        "diagnostics": [reason],
    }


def adapt_asset(
    asset: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(asset, dict):
        return blocked_result(
            {},
            "ASSET_NOT_OBJECT",
        )

    try:
        validate_identity(asset)

        ticker = asset["ticker"]
        status = asset.get("integration_status")
        usable = asset.get("analytically_usable")
        data_point = asset.get("data_point")

        if status == "ELIGIBLE":
            if usable is not True:
                raise IntegrationError(
                    "ELIGIBLE_WITH_ANALYTICALLY_USABLE_FALSE"
                )

            if not isinstance(data_point, dict):
                raise IntegrationError(
                    "ELIGIBLE_WITH_NULL_DATA_POINT"
                )

            metrics, metric_audit = (
                validate_ready_asset(asset)
            )

            loader_source = build_loader_source(
                metric_audit
            )

            loader_payload = {
                "ticker": ticker,
                "institutional_flow": {
                    "metrics": copy.deepcopy(
                        metrics
                    ),
                    "source": loader_source,
                },
            }

            return {
                "ticker": ticker,
                "boundary_status": "READY",
                "composer_integration_status": status,
                "composer_analytically_usable": True,
                "reason": (
                    "COMPOSER_ELIGIBLE_CONTRACT_VALID"
                ),
                "metrics_published": True,
                "metrics": copy.deepcopy(metrics),
                "loader_payload": loader_payload,
                "metric_provenance": metric_audit,
                "diagnostics": [],
            }

        if status == "BLOCKED":
            if data_point is not None:
                raise IntegrationError(
                    "BLOCKED_WITH_NON_NULL_DATA_POINT"
                )

            return blocked_result(
                asset,
                "COMPOSER_BLOCKED",
            )

        if status in KNOWN_NON_ELIGIBLE_STATUSES:
            if data_point is not None:
                raise IntegrationError(
                    "NON_ELIGIBLE_WITH_NON_NULL_DATA_POINT"
                )

            if usable is True:
                raise IntegrationError(
                    "NON_ELIGIBLE_WITH_ANALYTICALLY_USABLE_TRUE"
                )

            return suppressed_result(asset)

        raise IntegrationError(
            "UNKNOWN_COMPOSER_INTEGRATION_STATUS"
        )

    except IntegrationError as exc:
        return blocked_result(
            asset,
            str(exc),
        )


def build_metrics_loader_payload(
    asset_results: list[dict[str, Any]],
) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []

    for result in asset_results:
        if result.get("boundary_status") != "READY":
            continue

        payload = result.get("loader_payload")

        if not isinstance(payload, dict):
            raise IntegrationError(
                "READY result without loader payload."
            )

        assets.append(copy.deepcopy(payload))

    return {
        "schema_version": "3.0",
        "collector": (
            "INSTITUTIONAL_FLOW_SIGNAL_INTEGRATION_ADAPTER"
        ),
        "collector_version": ADAPTER_VERSION,
        "generated_at": utc_now_iso(),
        "assets": assets,
    }


def adapt_payload(
    composer_payload: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    validate_policy(policy)

    assets = composer_payload.get("assets")

    if not isinstance(assets, list):
        raise IntegrationError(
            "Composer payload assets must be an array."
        )

    results: list[dict[str, Any]] = []

    seen_tickers: set[str] = set()

    for asset in assets:
        result = adapt_asset(asset)

        ticker = result.get("ticker")

        if (
            isinstance(ticker, str)
            and ticker.strip()
        ):
            if ticker in seen_tickers:
                result = blocked_result(
                    asset,
                    "DUPLICATE_TICKER",
                )
            else:
                seen_tickers.add(ticker)

        results.append(result)

    loader_payload = build_metrics_loader_payload(
        results
    )

    ready = sum(
        1
        for result in results
        if result["boundary_status"] == "READY"
    )

    suppressed = sum(
        1
        for result in results
        if result["boundary_status"] == "SUPPRESSED"
    )

    blocked = sum(
        1
        for result in results
        if result["boundary_status"] == "BLOCKED"
    )

    metrics_published = sum(
        len(result.get("metrics") or {})
        for result in results
        if result["boundary_status"] == "READY"
    )

    return {
        "schema_version": "3.0",
        "adapter": (
            "INSTITUTIONAL_FLOW_SIGNAL_INTEGRATION_ADAPTER"
        ),
        "adapter_version": ADAPTER_VERSION,
        "policy_version": policy.get(
            "policy_version"
        ),
        "generated_at": utc_now_iso(),
        "source_boundary": "B.2D_COMPOSER",
        "target_boundary": "METRICS_LOADER_V3",
        "summary": {
            "total_assets": len(results),
            "ready": ready,
            "suppressed": suppressed,
            "blocked": blocked,
            "metrics_published": metrics_published,
        },
        "assets": results,
        "metrics_loader_payload": loader_payload,
    }


def print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]

    print()
    print("=== B.2E.2 INSTITUTIONAL FLOW SIGNAL INTEGRATION ===")
    print(f"Adapter: {ADAPTER_VERSION}")
    print(f"Assets: {summary['total_assets']}")
    print(f"READY: {summary['ready']}")
    print(f"SUPPRESSED: {summary['suppressed']}")
    print(f"BLOCKED: {summary['blocked']}")
    print(
        "Metrics published: "
        f"{summary['metrics_published']}"
    )
    print()

    for asset in result["assets"]:
        print(
            f"{asset.get('ticker', 'UNKNOWN')}: "
            f"{asset['boundary_status']} "
            f"({asset['reason']})"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "B.2E.2 Institutional Flow Signal "
            "Integration Adapter V3"
        )
    )

    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY_PATH,
    )

    parser.add_argument(
        "--composer",
        type=Path,
        default=DEFAULT_COMPOSER_PATH,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        policy = load_json(args.policy)
        composer = load_json(args.composer)

        result = adapt_payload(
            composer,
            policy,
        )

        save_json(
            args.output,
            result,
        )

        print_summary(result)

        print()
        print(f"Output: {args.output}")

        # A BLOCKED asset means a contract inconsistency or an
        # upstream block that must remain visible.
        # The artifact is still written for audit.
        if result["summary"]["blocked"] > 0:
            print()
            print(
                "RESULTADO: BLOCKED "
                "(fail-closed; revisar diagnostics)"
            )
            return 2

        print()
        print("RESULTADO: PASS")
        return 0

    except Exception as exc:
        print(
            f"ERRO B.2E.2: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())