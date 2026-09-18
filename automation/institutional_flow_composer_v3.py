import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2D.4"

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_POLICY = ROOT / "automation" / "institutional_flow_integration_policy_v3.json"
DEFAULT_HOLDINGS = ROOT / "input" / "metrics_institutional_holdings_test_v3.json"
DEFAULT_SHORT_INTEREST = ROOT / "input" / "short_interest_quality_v3.json"
DEFAULT_TECHNICAL = ROOT / "input" / "metrics_technical_test_v3.json"
DEFAULT_OUTPUT = ROOT / "input" / "institutional_flow_integration_v3.json"
DEFAULT_UNIVERSE = ROOT / "automation" / "asset_universe_v3.json"

def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be object: {path}")

    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            payload,
            f,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        f.write("\n")


def finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False

    if not isinstance(value, (int, float)):
        return False

    return math.isfinite(float(value))


def index_array_assets(payload: dict[str, Any], source_name: str) -> dict[str, dict[str, Any]]:
    assets = payload.get("assets")

    if not isinstance(assets, list):
        raise RuntimeError(
            f"{source_name}: assets must be an array."
        )

    result: dict[str, dict[str, Any]] = {}

    for asset in assets:
        if not isinstance(asset, dict):
            raise RuntimeError(
                f"{source_name}: asset must be object."
            )

        ticker = asset.get("ticker")

        if not isinstance(ticker, str) or not ticker.strip():
            raise RuntimeError(
                f"{source_name}: asset ticker missing."
            )

        ticker = ticker.strip().upper()

        if ticker in result:
            raise RuntimeError(
                f"{source_name}: duplicate ticker {ticker}."
            )

        result[ticker] = asset

    return result


def index_object_assets(payload: dict[str, Any], source_name: str) -> dict[str, dict[str, Any]]:
    assets = payload.get("assets")

    if not isinstance(assets, dict):
        raise RuntimeError(
            f"{source_name}: assets must be an object keyed by ticker."
        )

    result: dict[str, dict[str, Any]] = {}

    for key, asset in assets.items():
        if not isinstance(asset, dict):
            raise RuntimeError(
                f"{source_name}: asset {key} must be object."
            )

        ticker = asset.get("ticker")

        if not isinstance(ticker, str) or not ticker.strip():
            raise RuntimeError(
                f"{source_name}: ticker missing for key {key}."
            )

        ticker = ticker.strip().upper()

        if ticker != str(key).strip().upper():
            raise RuntimeError(
                f"{source_name}: ticker/key mismatch for {key}."
            )

        if ticker in result:
            raise RuntimeError(
                f"{source_name}: duplicate ticker {ticker}."
            )

        result[ticker] = asset

    return result

def index_master_universe(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    assets = payload.get("assets")

    if not isinstance(assets, dict) or not assets:
        raise RuntimeError(
            "MASTER_ASSET_UNIVERSE: assets must be a non-empty object."
        )

    result: dict[str, dict[str, Any]] = {}

    for key, asset in assets.items():
        if not isinstance(asset, dict):
            raise RuntimeError(
                f"MASTER_ASSET_UNIVERSE: asset {key} must be object."
            )

        ticker = asset.get("ticker")

        if not isinstance(ticker, str) or not ticker.strip():
            raise RuntimeError(
                f"MASTER_ASSET_UNIVERSE: ticker missing for {key}."
            )

        ticker = ticker.strip().upper()

        if ticker != str(key).strip().upper():
            raise RuntimeError(
                f"MASTER_ASSET_UNIVERSE: ticker/key mismatch for {key}."
            )

        if ticker in result:
            raise RuntimeError(
                f"MASTER_ASSET_UNIVERSE: duplicate ticker {ticker}."
            )

        result[ticker] = asset

    return result

def validate_asset_identity(
    ticker: str,
    universe_asset: dict[str, Any],
    holdings_asset: dict[str, Any] | None,
    short_interest_asset: dict[str, Any] | None,
) -> list[str]:
    diagnostics: list[str] = []

    expected_exchange = (
        (universe_asset.get("listing") or {}).get("exchange")
    )

    expected_cusip = (
        (universe_asset.get("identifiers") or {}).get("cusip")
    )

    if holdings_asset is not None:
        holdings_ticker = holdings_asset.get("ticker")
        holdings_cusip = holdings_asset.get("cusip")

        if holdings_ticker != ticker:
            diagnostics.append(
                "HOLDINGS_TICKER_IDENTITY_MISMATCH"
            )

        if (
            expected_cusip
            and holdings_cusip
            and holdings_cusip != expected_cusip
        ):
            diagnostics.append(
                "HOLDINGS_CUSIP_IDENTITY_MISMATCH"
            )

    if short_interest_asset is not None:
        raw_normalized = (
            short_interest_asset.get("raw_normalized_asset") or {}
        )

        identity = raw_normalized.get("identity") or {}

        si_ticker = identity.get("ticker")
        si_exchange = identity.get("listing_exchange")
        si_cusip = identity.get("cusip")

        if si_ticker and si_ticker != ticker:
            diagnostics.append(
                "SHORT_INTEREST_TICKER_IDENTITY_MISMATCH"
            )

        if (
            expected_exchange
            and si_exchange
            and si_exchange != expected_exchange
        ):
            diagnostics.append(
                "SHORT_INTEREST_EXCHANGE_IDENTITY_MISMATCH"
            )

        if (
            expected_cusip
            and si_cusip
            and si_cusip != expected_cusip
        ):
            diagnostics.append(
                "SHORT_INTEREST_CUSIP_IDENTITY_MISMATCH"
            )

    return diagnostics

def allowed_quality_state(
    quality_status: Any,
    analytically_usable: Any,
    allowed_states: list[dict[str, Any]],
) -> bool:
    for state in allowed_states:
        if (
            quality_status == state.get("quality_status")
            and analytically_usable is state.get("analytically_usable")
        ):
            return True

    return False


def evaluate_holdings(
    ticker: str,
    asset: dict[str, Any] | None,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    metric_name = "institutional_flow_pct"

    if asset is None:
        return {
            "metric": metric_name,
            "eligible": False,
            "value": None,
            "reason": "HOLDINGS_ASSET_MISSING",
            "dimension": cfg.get("institutional_dimension"),
            "counts_as_dimension": False,
            "signal_weight": cfg.get("signal_weight"),
            "quality_status": "UNAVAILABLE",
            "analytically_usable": False,
            "provenance": None,
            "raw_source_metric": None,
        }

    diagnostics = []

    source_metric = asset.get("metric")
    value = asset.get("value")
    quality_status = asset.get("quality_status")
    analytically_usable = asset.get("analytically_usable")
    provenance = asset.get("provenance") or {}

    if asset.get("ticker") != ticker:
        diagnostics.append("TICKER_MISMATCH")

    if source_metric != cfg.get("source_metric"):
        diagnostics.append("SOURCE_METRIC_MISMATCH")

    if not finite_number(value):
        diagnostics.append("METRIC_NOT_NUMERIC")

    if provenance.get("source") != cfg.get("source"):
        diagnostics.append("SOURCE_MISMATCH")

    if provenance.get("source_type") != cfg.get("source_type"):
        diagnostics.append("SOURCE_TYPE_MISMATCH")

    if provenance.get("tier") != cfg.get("required_source_tier"):
        diagnostics.append("SOURCE_TIER_MISMATCH")

    quality_allowed = allowed_quality_state(
        quality_status,
        analytically_usable,
        cfg.get("allowed_quality_states") or [],
    )

    if not quality_allowed:
        diagnostics.append("UPSTREAM_QUALITY_NOT_ELIGIBLE")

    eligible = not diagnostics

    return {
        "metric": metric_name,
        "eligible": eligible,
        "value": float(value) if eligible else None,
        "reason": "ELIGIBLE" if eligible else "HOLDINGS_NOT_ELIGIBLE",
        "dimension": cfg.get("institutional_dimension"),
        "counts_as_dimension": bool(
            eligible
            and cfg.get("counts_as_independent_institutional_dimension")
        ),
        "signal_weight": float(cfg.get("signal_weight", 0)),
        "quality_status": quality_status,
        "analytically_usable": analytically_usable,
        "provenance": copy.deepcopy(provenance),
        "raw_source_metric": {
            "name": source_metric,
            "value": copy.deepcopy(value),
        },
        "diagnostics": diagnostics,
    }


def evaluate_short_interest(
    ticker: str,
    asset: dict[str, Any] | None,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    metric_name = "short_interest_change_pct"

    if asset is None:
        return {
            "metric": metric_name,
            "eligible": False,
            "value": None,
            "reason": "SHORT_INTEREST_ASSET_MISSING",
            "dimension": cfg.get("institutional_dimension"),
            "counts_as_dimension": False,
            "signal_weight": cfg.get("signal_weight"),
            "quality_status": "UNAVAILABLE",
            "analytically_usable": False,
            "provenance": None,
            "raw_source_metric": None,
            "diagnostics": ["SHORT_INTEREST_ASSET_MISSING"],
        }

    diagnostics = []

    metric = asset.get("metric") or {}
    provenance = asset.get("provenance") or {}

    quality_status = asset.get("quality_status")
    analytically_usable = asset.get("analytically_usable")

    source_metric_name = metric.get("name")
    value = metric.get("value")

    if asset.get("ticker") != ticker:
        diagnostics.append("TICKER_MISMATCH")

    if source_metric_name != cfg.get("source_metric"):
        diagnostics.append("SOURCE_METRIC_MISMATCH")

    if not finite_number(value):
        diagnostics.append("METRIC_NOT_NUMERIC")

    if provenance.get("source") != cfg.get("source"):
        diagnostics.append("SOURCE_MISMATCH")

    if provenance.get("source_tier") != cfg.get("required_source_tier"):
        diagnostics.append("SOURCE_TIER_MISMATCH")

    quality_allowed = allowed_quality_state(
        quality_status,
        analytically_usable,
        cfg.get("allowed_quality_states") or [],
    )

    if not quality_allowed:
        diagnostics.append("UPSTREAM_QUALITY_NOT_ELIGIBLE")

    eligible = not diagnostics

    return {
        "metric": metric_name,
        "eligible": eligible,
        "value": float(value) if eligible else None,
        "reason": "ELIGIBLE" if eligible else "SHORT_INTEREST_NOT_ELIGIBLE",
        "dimension": cfg.get("institutional_dimension"),
        "counts_as_dimension": bool(
            eligible
            and cfg.get("counts_as_independent_institutional_dimension")
        ),
        "signal_weight": float(cfg.get("signal_weight", 0)),
        "quality_status": quality_status,
        "analytically_usable": analytically_usable,
        "provenance": copy.deepcopy(provenance),
        "raw_source_metric": copy.deepcopy(metric),
        "diagnostics": diagnostics,
    }


def evaluate_volume(
    ticker: str,
    asset: dict[str, Any] | None,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    metric_name = "volume_ratio"

    if asset is None:
        return {
            "metric": metric_name,
            "eligible": False,
            "value": None,
            "reason": "TECHNICAL_ASSET_MISSING",
            "dimension": None,
            "counts_as_dimension": False,
            "signal_weight": cfg.get("signal_weight"),
            "quality_status": "UNAVAILABLE",
            "analytically_usable": False,
            "provenance": None,
            "raw_source_metric": None,
            "diagnostics": ["TECHNICAL_ASSET_MISSING"],
        }

    diagnostics = []

    technical = asset.get("technical") or {}
    metrics = technical.get("metrics") or {}
    source = technical.get("source") or {}

    value = metrics.get("volume_ratio")

    if asset.get("ticker") != ticker:
        diagnostics.append("TICKER_MISMATCH")

    if not finite_number(value):
        diagnostics.append("METRIC_NOT_NUMERIC")

    # Volume is supporting market activity.
    # It is not promoted to institutional provenance.
    eligible = not diagnostics

    return {
        "metric": metric_name,
        "eligible": eligible,
        "value": float(value) if eligible else None,
        "reason": "ELIGIBLE_SUPPORTING_METRIC" if eligible else "VOLUME_NOT_ELIGIBLE",
        "dimension": None,
        "counts_as_dimension": False,
        "signal_weight": float(cfg.get("signal_weight", 0)),
        "quality_status": "AVAILABLE" if eligible else "UNAVAILABLE",
        "analytically_usable": eligible,
        "provenance": copy.deepcopy(source),
        "raw_source_metric": {
            "name": "volume_ratio",
            "value": copy.deepcopy(value),
        },
        "diagnostics": diagnostics,
    }


def evaluate_options(
    cfg: dict[str, Any],
) -> dict[str, Any]:
    return {
        "metric": "call_put_ratio",
        "eligible": False,
        "value": None,
        "reason": "OPTIONS_NOT_YET_HOMOLOGATED",
        "dimension": cfg.get("institutional_dimension"),
        "counts_as_dimension": False,
        "signal_weight": float(cfg.get("signal_weight", 0)),
        "quality_status": "NOT_HOMOLOGATED",
        "analytically_usable": False,
        "provenance": None,
        "raw_source_metric": None,
        "diagnostics": ["OPTIONS_NOT_YET_HOMOLOGATED"],
    }


def compose_asset(
    ticker: str,
    holdings_asset: dict[str, Any] | None,
    short_interest_asset: dict[str, Any] | None,
    technical_asset: dict[str, Any] | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    metrics_cfg = policy["metrics"]
    required = policy["eligibility"]["required_conditions"]

    evaluations = [
        evaluate_holdings(
            ticker,
            holdings_asset,
            metrics_cfg["institutional_flow_pct"],
        ),
        evaluate_short_interest(
            ticker,
            short_interest_asset,
            metrics_cfg["short_interest_change_pct"],
        ),
        evaluate_volume(
            ticker,
            technical_asset,
            metrics_cfg["volume_ratio"],
        ),
        evaluate_options(
            metrics_cfg["call_put_ratio"],
        ),
    ]

    eligible_metrics = [
        item for item in evaluations
        if item["eligible"]
    ]

    weighted_coverage = round(
        sum(float(item["signal_weight"]) for item in eligible_metrics),
        10,
    )

    dimensions = sorted({
        item["dimension"]
        for item in eligible_metrics
        if item["counts_as_dimension"] and item["dimension"]
    })

    dimension_count = len(dimensions)

    minimum_coverage = float(
        required["minimum_weighted_metric_coverage"]
    )
    minimum_dimensions = int(
        required["minimum_independent_institutional_dimensions"]
    )

    if not eligible_metrics:
        integration_status = "UNAVAILABLE"
        analytically_usable = False
        reason = "NO_ELIGIBLE_METRICS"

    elif dimension_count < minimum_dimensions:
        integration_status = "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS"
        analytically_usable = False
        reason = "MINIMUM_INSTITUTIONAL_DIMENSIONS_NOT_MET"

    elif weighted_coverage < minimum_coverage:
        integration_status = "INSUFFICIENT_WEIGHTED_COVERAGE"
        analytically_usable = False
        reason = "MINIMUM_WEIGHTED_COVERAGE_NOT_MET"

    else:
        integration_status = "ELIGIBLE"
        analytically_usable = True
        reason = "INTEGRATION_ELIGIBLE"

    integrated_values = {
        item["metric"]: item["value"]
        for item in eligible_metrics
    }

    integrated_metrics = [
        {
            "metric": item["metric"],
            "value": item["value"],
            "signal_weight": item["signal_weight"],
            "dimension": item["dimension"],
            "counts_as_dimension": item["counts_as_dimension"],
            "quality_status": item["quality_status"],
            "provenance": copy.deepcopy(item["provenance"]),
        }
        for item in eligible_metrics
    ]

    excluded_metrics = [
        {
            "metric": item["metric"],
            "reason": item["reason"],
            "quality_status": item["quality_status"],
            "analytically_usable": item["analytically_usable"],
            "diagnostics": copy.deepcopy(item.get("diagnostics") or []),
        }
        for item in evaluations
        if not item["eligible"]
    ]

    diagnostics = []

    if dimension_count < minimum_dimensions:
        diagnostics.append(
            "INSUFFICIENT_INDEPENDENT_INSTITUTIONAL_DIMENSIONS"
        )

    if weighted_coverage < minimum_coverage:
        diagnostics.append(
            "INSUFFICIENT_WEIGHTED_METRIC_COVERAGE"
        )

    data_point = None

    # Fail closed:
    # only an ELIGIBLE integration may be emitted as Signal Engine input.
    if analytically_usable:
        data_point = {
            "value": copy.deepcopy(integrated_values),
            "integration_status": integration_status,
            "weighted_metric_coverage": weighted_coverage,
            "institutional_dimension_count": dimension_count,
            "institutional_dimensions": copy.deepcopy(dimensions),
        }

    return {
        "ticker": ticker,
        "integration_status": integration_status,
        "analytically_usable": analytically_usable,
        "reason": reason,
        "weighted_metric_coverage": weighted_coverage,
        "institutional_dimension_count": dimension_count,
        "institutional_dimensions": dimensions,
        "integrated_metrics": integrated_metrics,
        "excluded_metrics": excluded_metrics,
        "data_point": data_point,
        "diagnostics": diagnostics,
        "raw_inputs": {
            "institutional_holdings": copy.deepcopy(holdings_asset),
            "short_interest_quality": copy.deepcopy(short_interest_asset),
            "technical_metrics": copy.deepcopy(technical_asset),
        },
    }


def run_composer(
    policy_payload: dict[str, Any],
    universe_payload: dict[str, Any],
    holdings_payload: dict[str, Any],
    short_interest_payload: dict[str, Any],
    technical_payload: dict[str, Any],
) -> dict[str, Any]:
    if policy_payload.get("policy_name") != "INSTITUTIONAL_FLOW_INTEGRATION":
        raise RuntimeError(
            "Invalid Institutional Flow Integration Policy."
        )

    universe = index_master_universe(
        universe_payload,
    )

    holdings = index_object_assets(
        holdings_payload,
        "INSTITUTIONAL_HOLDINGS",
    )

    short_interest = index_array_assets(
        short_interest_payload,
        "SHORT_INTEREST_QUALITY",
    )

    technical = index_array_assets(
        technical_payload,
        "TECHNICAL_METRICS",
    )

    universe_tickers = set(universe)
    holdings_tickers = set(holdings)
    short_interest_tickers = set(short_interest)
    technical_tickers = set(technical)

    orphan_assets = {
        "institutional_holdings": sorted(
            holdings_tickers - universe_tickers
        ),
        "short_interest": sorted(
            short_interest_tickers - universe_tickers
        ),
        "technical": sorted(
            technical_tickers - universe_tickers
        ),
    }

    if any(orphan_assets.values()):
        raise RuntimeError(
            "ORPHAN_ASSET_DETECTED: "
            + json.dumps(
                orphan_assets,
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    assets = []

    for ticker in sorted(universe):
        universe_asset = universe[ticker]

        if universe_asset.get("enabled") is not True:
            continue

        holdings_asset = holdings.get(ticker)
        short_interest_asset = short_interest.get(ticker)
        technical_asset = technical.get(ticker)

        identity_diagnostics = validate_asset_identity(
            ticker=ticker,
            universe_asset=universe_asset,
            holdings_asset=holdings_asset,
            short_interest_asset=short_interest_asset,
        )

        result = compose_asset(
            ticker=ticker,
            holdings_asset=holdings_asset,
            short_interest_asset=short_interest_asset,
            technical_asset=technical_asset,
            policy=policy_payload,
        )

        result["master_identity"] = {
            "ticker": ticker,
            "listing_exchange": (
                (universe_asset.get("listing") or {}).get("exchange")
            ),
            "cusip": (
                (universe_asset.get("identifiers") or {}).get("cusip")
            ),
            "sec_cik": (
                (universe_asset.get("identifiers") or {}).get("sec_cik")
            ),
        }

        result["identity_diagnostics"] = identity_diagnostics

        if identity_diagnostics:
            result["integration_status"] = "BLOCKED"
            result["analytically_usable"] = False
            result["reason"] = "ASSET_IDENTITY_MISMATCH"
            result["data_point"] = None

            result["diagnostics"] = (
                list(result.get("diagnostics") or [])
                + identity_diagnostics
            )

        assets.append(result)

    summary = {
        "total_assets": len(assets),

        "eligible": sum(
            1 for x in assets
            if x["integration_status"] == "ELIGIBLE"
        ),

        "blocked": sum(
            1 for x in assets
            if x["integration_status"] == "BLOCKED"
        ),

        "insufficient_institutional_dimensions": sum(
            1 for x in assets
            if x["integration_status"]
            == "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS"
        ),

        "insufficient_weighted_coverage": sum(
            1 for x in assets
            if x["integration_status"]
            == "INSUFFICIENT_WEIGHTED_COVERAGE"
        ),

        "unavailable": sum(
            1 for x in assets
            if x["integration_status"] == "UNAVAILABLE"
        ),

        "analytically_usable": sum(
            1 for x in assets
            if x["analytically_usable"]
        ),

        "orphan_assets": orphan_assets,
    }

    return {
        "version": VERSION,
        "domain": "institutional_flow",
        "policy_version": policy_payload.get("policy_version"),
        "universe_version": universe_payload.get("universe_version"),
        "universe_name": universe_payload.get("universe_name"),
        "summary": summary,
        "assets": assets,
    }

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Radar Institucional V3 - Institutional Flow Composer"
    )

    parser.add_argument(
        "--universe",
        type=Path,
        default=DEFAULT_UNIVERSE,
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY,
    )
    parser.add_argument(
        "--holdings",
        type=Path,
        default=DEFAULT_HOLDINGS,
    )
    parser.add_argument(
        "--short-interest",
        type=Path,
        default=DEFAULT_SHORT_INTEREST,
    )
    parser.add_argument(
        "--technical",
        type=Path,
        default=DEFAULT_TECHNICAL,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    args = parser.parse_args()

    policy = read_json(args.policy)
    universe = read_json(args.universe)
    holdings = read_json(args.holdings)
    short_interest = read_json(args.short_interest)
    technical = read_json(args.technical)

    result = run_composer(
        policy,
        universe,
        holdings,
        short_interest,
        technical,
    )

    write_json(args.output, result)

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("INSTITUTIONAL FLOW COMPOSER")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    for asset in result["assets"]:
        print("-" * 72)
        print(f"Ticker: {asset['ticker']}")
        print(f"Integration: {asset['integration_status']}")
        print(f"Analytically usable: {asset['analytically_usable']}")
        print(
            "Weighted coverage: "
            f"{asset['weighted_metric_coverage']:.2%}"
        )
        print(
            "Institutional dimensions: "
            f"{asset['institutional_dimension_count']}"
        )
        print(
            "Integrated metrics: "
            f"{[x['metric'] for x in asset['integrated_metrics']]}"
        )
        print(
            "Excluded metrics: "
            f"{[x['metric'] for x in asset['excluded_metrics']]}"
        )

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    for key, value in result["summary"].items():
        print(f"{key}: {value}")

    print(f"Output: {args.output.resolve()}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
