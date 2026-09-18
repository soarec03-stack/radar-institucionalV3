from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.8F.2A"

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_BOUNDARY_INPUT = (
    BASE_DIR
    / "input"
    / "short_interest_real_reconciler_boundary_v3.json"
)

DEFAULT_NORMALIZED_INPUT = (
    BASE_DIR
    / "input"
    / "short_interest_real_normalized_v3.json"
)

DEFAULT_POLICY = (
    BASE_DIR
    / "automation"
    / "short_interest_quality_policy_v3.json"
)

DEFAULT_OUTPUT = (
    BASE_DIR
    / "input"
    / "short_interest_quality_v3.json"
)

QUALITY_STATUSES = {
    "VERIFIED",
    "BLOCKED",
    "UNAVAILABLE",
}


class QualityGateError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        value = json.load(file)

    if not isinstance(value, dict):
        raise QualityGateError(
            f"{path}: root deve ser objeto."
        )

    return value


def write_json(
    path: Path,
    value: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            value,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
    )


def positive_number(value: Any) -> bool:
    return valid_number(value) and value > 0


def nonnegative_number(value: Any) -> bool:
    return valid_number(value) and value >= 0


def quality_check(
    name: str,
    required: bool,
    passed: bool,
    observed: Any,
    expected: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "required": required,
        "passed": bool(passed),
        "observed": deepcopy(observed),
        "expected": deepcopy(expected),
    }


def validate_policy(policy: dict[str, Any]) -> None:
    if (
        policy.get("policy_name")
        != "SHORT_INTEREST_QUALITY_GATE"
    ):
        raise QualityGateError(
            "Quality Policy invalida: policy_name."
        )

    blocking = policy.get("blocking_controls")
    if not isinstance(blocking, dict):
        raise QualityGateError(
            "Quality Policy sem blocking_controls."
        )

    statuses = policy.get("quality_statuses")
    if not isinstance(statuses, dict):
        raise QualityGateError(
            "Quality Policy sem quality_statuses."
        )

    if set(statuses) != QUALITY_STATUSES:
        raise QualityGateError(
            "Quality Policy com statuses invalidos."
        )

    allowed = policy.get(
        "allowed_reconciliation_statuses"
    )
    deferred = policy.get(
        "deferred_reconciliation_statuses"
    )
    blocked = policy.get(
        "blocked_reconciliation_statuses"
    )
    metric_selection = policy.get("metric_selection")

    if not isinstance(allowed, list):
        raise QualityGateError(
            "Quality Policy sem allowed_reconciliation_statuses."
        )

    if not isinstance(deferred, list):
        raise QualityGateError(
            "Quality Policy sem deferred_reconciliation_statuses."
        )

    if not isinstance(blocked, list):
        raise QualityGateError(
            "Quality Policy sem blocked_reconciliation_statuses."
        )

    if not isinstance(metric_selection, dict):
        raise QualityGateError(
            "Quality Policy sem metric_selection."
        )


def extract_adapter_case(
    boundary_asset: dict[str, Any],
) -> dict[str, Any] | None:
    raw_adapter_asset = boundary_asset.get(
        "raw_adapter_asset"
    )
    if not isinstance(raw_adapter_asset, dict):
        return None

    adapter_case = raw_adapter_asset.get(
        "adapter_case"
    )
    if not isinstance(adapter_case, dict):
        return None

    return adapter_case


def extract_review_result(
    boundary_asset: dict[str, Any],
) -> dict[str, Any] | None:
    raw_review_asset = boundary_asset.get(
        "raw_review_asset"
    )
    if not isinstance(raw_review_asset, dict):
        return None

    review_result = raw_review_asset.get(
        "review_result"
    )
    if not isinstance(review_result, dict):
        return None

    return review_result


def normalized_identity_key(
    normalized_asset: dict[str, Any],
) -> tuple[Any, Any, Any]:
    identity = normalized_asset.get("identity")
    if not isinstance(identity, dict):
        return None, None, None

    security_identity = identity.get(
        "security_identity"
    )
    security_identity_string = None

    if isinstance(security_identity, dict):
        identity_type = security_identity.get("type")
        identity_value = security_identity.get("value")
        if (
            non_empty_string(identity_type)
            and non_empty_string(identity_value)
        ):
            security_identity_string = (
                f"{identity_type}:{identity_value}"
            )
    elif non_empty_string(security_identity):
        security_identity_string = security_identity

    return (
        identity.get("ticker"),
        identity.get("listing_exchange"),
        security_identity_string,
    )


def boundary_identity_key(
    boundary_asset: dict[str, Any],
) -> tuple[Any, Any, Any]:
    adapter_case = extract_adapter_case(
        boundary_asset
    )
    if not isinstance(adapter_case, dict):
        return None, None, None

    identity = adapter_case.get("identity")
    if not isinstance(identity, dict):
        return None, None, None

    return (
        identity.get("ticker"),
        identity.get("listing_exchange"),
        identity.get("security_identity"),
    )


def normalized_window(
    normalized_asset: dict[str, Any],
) -> tuple[Any, Any]:
    window = normalized_asset.get(
        "settlement_window"
    )
    if not isinstance(window, dict):
        return None, None

    return (
        window.get("previous_settlement_date"),
        window.get("current_settlement_date"),
    )


def boundary_window(
    boundary_asset: dict[str, Any],
) -> tuple[Any, Any]:
    adapter_case = extract_adapter_case(
        boundary_asset
    )
    if not isinstance(adapter_case, dict):
        return None, None

    return (
        adapter_case.get("previous_settlement_date"),
        adapter_case.get("current_settlement_date"),
    )


def normalized_fact(
    normalized_asset: dict[str, Any],
) -> dict[str, Any] | None:
    fact = normalized_asset.get("short_interest")
    if not isinstance(fact, dict):
        return None
    return fact


def normalized_provenance(
    normalized_asset: dict[str, Any],
) -> dict[str, Any] | None:
    sources = normalized_asset.get("sources")
    if not isinstance(sources, dict):
        return None

    provenance = sources.get("short_interest")
    if not isinstance(provenance, dict):
        return None

    return provenance


def fact_is_available(
    normalized_asset: dict[str, Any] | None,
) -> bool:
    if not isinstance(normalized_asset, dict):
        return False

    fact = normalized_fact(normalized_asset)
    if not isinstance(fact, dict):
        return False

    previous_value = fact.get(
        "previous_short_interest_shares"
    )
    current_value = fact.get(
        "current_short_interest_shares"
    )

    return (
        previous_value is not None
        and current_value is not None
    )


def select_metric(
    normalized_asset: dict[str, Any],
    reconciler_result: dict[str, Any] | None,
    reconciliation_status: Any,
) -> tuple[Any, str | None, list[str]]:
    """
    Seleciona a metrica sem inferencia.

    NO_ACTION:
      usa o calculo Radar/Normalizer sobre os dois snapshots FINRA.

    VERIFIED_ACTION:
      usa exclusivamente adjusted_change_pct do Reconciler.

    SOURCE_ADJUSTED:
      permanece sem metrica final nesta versao. O Reconciler comprova
      que a fonte ajustou, mas nao transporta explicitamente o valor
      ajustado. O Quality Gate nao pode inventa-lo.
    """

    diagnostics: list[str] = []

    fact = normalized_fact(normalized_asset)
    if not isinstance(fact, dict):
        return None, None, [
            "NORMALIZED_SHORT_INTEREST_FACT_MISSING"
        ]

    if reconciliation_status == "NO_ACTION":
        metric = fact.get(
            "collector_calculated_change_pct"
        )
        if not valid_number(metric):
            diagnostics.append(
                "NORMALIZED_CALCULATED_METRIC_MISSING"
            )
        return (
            metric,
            "NORMALIZED_FINRA_FACT",
            diagnostics,
        )

    if reconciliation_status == "VERIFIED_ACTION":
        if not isinstance(reconciler_result, dict):
            return None, None, [
                "RECONCILER_RESULT_MISSING"
            ]

        metric = reconciler_result.get(
            "adjusted_change_pct"
        )
        if not valid_number(metric):
            diagnostics.append(
                "RECONCILER_ADJUSTED_METRIC_MISSING"
            )
        return (
            metric,
            "RECONCILER",
            diagnostics,
        )

    if reconciliation_status == "SOURCE_ADJUSTED":
        return None, None, [
            "SOURCE_ADJUSTED_METRIC_CONTRACT_DEFERRED"
        ]

    return None, None, [
        "RECONCILIATION_STATUS_NOT_METRIC_ELIGIBLE"
    ]


def evaluate_quality(
    boundary_asset: dict[str, Any],
    normalized_asset: dict[str, Any] | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    validate_policy(policy)

    ticker = boundary_asset.get("ticker")
    if not non_empty_string(ticker):
        raise QualityGateError(
            "Boundary asset sem ticker."
        )

    if not fact_is_available(normalized_asset):
        return {
            "quality_gate_version": VERSION,
            "policy_version": policy.get(
                "policy_version"
            ),
            "ticker": ticker,
            "quality_status": "UNAVAILABLE",
            "analytically_usable": False,
            "reason":
                "REQUIRED_SHORT_INTEREST_FACT_NOT_AVAILABLE",
            "blocking_controls_passed": False,
            "failed_blocking_controls": [
                "UPSTREAM_AVAILABILITY"
            ],
            "metric": None,
            "checks": [],
            "raw_normalized_asset":
                deepcopy(normalized_asset),
            "raw_boundary_asset":
                deepcopy(boundary_asset),
        }

    assert isinstance(normalized_asset, dict)

    blocking = policy["blocking_controls"]
    allowed_reconciliation = set(
        policy["allowed_reconciliation_statuses"]
    )
    deferred_reconciliation = set(
        policy["deferred_reconciliation_statuses"]
    )

    fact = normalized_fact(normalized_asset)
    assert isinstance(fact, dict)

    provenance = normalized_provenance(
        normalized_asset
    )

    previous_value = fact.get(
        "previous_short_interest_shares"
    )
    current_value = fact.get(
        "current_short_interest_shares"
    )

    normalized_previous, normalized_current = (
        normalized_window(normalized_asset)
    )
    boundary_previous, boundary_current = (
        boundary_window(boundary_asset)
    )

    review_result = extract_review_result(
        boundary_asset
    )
    review_previous = (
        review_result.get(
            "previous_settlement_date"
        )
        if isinstance(review_result, dict)
        else None
    )
    review_current = (
        review_result.get(
            "current_settlement_date"
        )
        if isinstance(review_result, dict)
        else None
    )

    normalized_identity = normalized_identity_key(
        normalized_asset
    )
    boundary_identity = boundary_identity_key(
        boundary_asset
    )

    identity_continuity = (
        normalized_asset.get("identity", {}).get(
            "identity_continuity_status"
        )
        if isinstance(
            normalized_asset.get("identity"),
            dict,
        )
        else None
    )

    reconciler_result = boundary_asset.get(
        "reconciler_result"
    )
    reconciler_is_dict = isinstance(
        reconciler_result,
        dict,
    )

    reconciliation_status = (
        reconciler_result.get(
            "reconciliation_status"
        )
        if reconciler_is_dict
        else None
    )

    reconciliation_resolved = (
        reconciliation_status
        in allowed_reconciliation
    )

    reconciliation_deferred = (
        reconciliation_status
        in deferred_reconciliation
    )

    metric, metric_source, metric_diagnostics = (
        select_metric(
            normalized_asset,
            reconciler_result
            if reconciler_is_dict
            else None,
            reconciliation_status,
        )
    )

    adjustment_authorized = (
        reconciler_result.get(
            "adjustment_authorized"
        )
        if reconciler_is_dict
        else None
    )
    adjustment_factor = (
        reconciler_result.get(
            "adjustment_factor"
        )
        if reconciler_is_dict
        else None
    )
    adjustment_status = (
        reconciler_result.get(
            "adjustment_status"
        )
        if reconciler_is_dict
        else None
    )

    adjustment_integrity = False

    if reconciliation_status == "NO_ACTION":
        adjustment_integrity = (
            adjustment_authorized is False
            and adjustment_factor is None
            and adjustment_status
            == "NOT_REQUIRED"
        )

    elif reconciliation_status == "VERIFIED_ACTION":
        previous_raw = (
            reconciler_result.get("previous_raw")
            if reconciler_is_dict
            else None
        )
        current_raw = (
            reconciler_result.get("current_raw")
            if reconciler_is_dict
            else None
        )
        previous_adjusted = (
            reconciler_result.get(
                "previous_adjusted"
            )
            if reconciler_is_dict
            else None
        )

        adjustment_integrity = (
            adjustment_authorized is True
            and positive_number(adjustment_factor)
            and positive_number(previous_raw)
            and nonnegative_number(current_raw)
            and positive_number(previous_adjusted)
            and float(previous_raw)
            == float(previous_value)
            and float(current_raw)
            == float(current_value)
            and valid_number(metric)
        )

    # SOURCE_ADJUSTED e deliberadamente deferred nesta versao.
    elif reconciliation_status == "SOURCE_ADJUSTED":
        adjustment_integrity = False

    source_name = (
        provenance.get("source")
        if isinstance(provenance, dict)
        else None
    )
    source_tier = (
        provenance.get("source_tier")
        if isinstance(provenance, dict)
        else None
    )
    source_dataset = (
        provenance.get("dataset")
        if isinstance(provenance, dict)
        else None
    )

    provenance_pass = (
        source_name
        == policy["metric"]["source"]
        and source_tier
        == policy["metric"][
            "required_source_tier"
        ]
    )

    ticker_consistent = (
        normalized_asset.get("ticker")
        == ticker
    )

    identity_consistent = (
        all(
            non_empty_string(value)
            for value in normalized_identity
        )
        and normalized_identity
        == boundary_identity
    )

    window_consistent = (
        non_empty_string(normalized_previous)
        and non_empty_string(normalized_current)
        and normalized_previous
        == boundary_previous
        == review_previous
        and normalized_current
        == boundary_current
        == review_current
    )

    raw_values_preserved = (
        isinstance(
            normalized_asset.get("raw_upstream"),
            dict,
        )
        and isinstance(
            boundary_asset.get("raw_adapter_asset"),
            dict,
        )
        and isinstance(
            boundary_asset.get("raw_review_asset"),
            dict,
        )
    )

    checks = [
        quality_check(
            "TICKER_CONSISTENCY",
            True,
            ticker_consistent,
            {
                "normalized":
                    normalized_asset.get("ticker"),
                "boundary": ticker,
            },
            "EXACT_MATCH",
        ),
        quality_check(
            "IDENTITY_CONSISTENCY",
            True,
            identity_consistent,
            {
                "normalized":
                    normalized_identity,
                "boundary":
                    boundary_identity,
            },
            "EXACT_MATCH",
        ),
        quality_check(
            "BOUNDARY_RECONCILED",
            blocking.get(
                "require_boundary_reconciled"
            ) is True,
            boundary_asset.get(
                "boundary_status"
            ) == "RECONCILED",
            boundary_asset.get(
                "boundary_status"
            ),
            "RECONCILED",
        ),
        quality_check(
            "RECONCILER_INVOKED",
            blocking.get(
                "require_reconciler_invoked"
            ) is True,
            boundary_asset.get(
                "reconciler_invoked"
            ) is True,
            boundary_asset.get(
                "reconciler_invoked"
            ),
            True,
        ),
        quality_check(
            "RECONCILER_ANALYTICALLY_USABLE",
            blocking.get(
                "require_reconciler_analytically_usable"
            ) is True,
            (
                reconciler_is_dict
                and reconciler_result.get(
                    "analytically_usable"
                ) is True
            ),
            (
                reconciler_result.get(
                    "analytically_usable"
                )
                if reconciler_is_dict
                else None
            ),
            True,
        ),
        quality_check(
            "VERIFIED_IDENTITY_CONTINUITY",
            blocking.get(
                "require_verified_identity_continuity"
            ) is True,
            identity_continuity == "VERIFIED",
            identity_continuity,
            "VERIFIED",
        ),
        quality_check(
            "EXACT_SETTLEMENT_WINDOW",
            blocking.get(
                "require_exact_settlement_window"
            ) is True,
            window_consistent,
            {
                "normalized_previous":
                    normalized_previous,
                "normalized_current":
                    normalized_current,
                "boundary_previous":
                    boundary_previous,
                "boundary_current":
                    boundary_current,
                "review_previous":
                    review_previous,
                "review_current":
                    review_current,
            },
            "EXACT_MATCH",
        ),
        quality_check(
            "TWO_DISTINCT_SETTLEMENT_DATES",
            blocking.get(
                "require_two_distinct_settlement_dates"
            ) is True,
            (
                non_empty_string(normalized_previous)
                and non_empty_string(normalized_current)
                and normalized_previous
                != normalized_current
            ),
            {
                "previous":
                    normalized_previous,
                "current":
                    normalized_current,
            },
            "TWO_DISTINCT_DATES",
        ),
        quality_check(
            "POSITIVE_PREVIOUS_SHORT_INTEREST",
            blocking.get(
                "require_positive_previous_short_interest"
            ) is True,
            positive_number(previous_value),
            previous_value,
            "> 0",
        ),
        quality_check(
            "NONNEGATIVE_CURRENT_SHORT_INTEREST",
            blocking.get(
                "require_nonnegative_current_short_interest"
            ) is True,
            nonnegative_number(current_value),
            current_value,
            ">= 0",
        ),
        quality_check(
            "TIER_1_SHORT_INTEREST_PROVENANCE",
            blocking.get(
                "require_tier_1_short_interest_provenance"
            ) is True,
            provenance_pass,
            {
                "source": source_name,
                "tier": source_tier,
                "dataset": source_dataset,
            },
            {
                "source":
                    policy["metric"]["source"],
                "tier":
                    policy["metric"][
                        "required_source_tier"
                    ],
            },
        ),
        quality_check(
            "CORPORATE_ACTION_RECONCILIATION_RESOLVED",
            blocking.get(
                "require_corporate_action_reconciliation_resolved"
            ) is True,
            reconciliation_resolved,
            reconciliation_status,
            sorted(allowed_reconciliation),
        ),
        quality_check(
            "ADJUSTMENT_INTEGRITY",
            blocking.get(
                "require_adjustment_integrity"
            ) is True,
            adjustment_integrity,
            {
                "reconciliation_status":
                    reconciliation_status,
                "adjustment_status":
                    adjustment_status,
                "adjustment_authorized":
                    adjustment_authorized,
                "adjustment_factor":
                    adjustment_factor,
            },
            "CONSISTENT_WITH_RECONCILIATION_STATUS",
        ),
        quality_check(
            "RAW_VALUES_PRESERVED",
            blocking.get(
                "require_raw_values_preserved"
            ) is True,
            raw_values_preserved,
            raw_values_preserved,
            True,
        ),
        quality_check(
            "METRIC_AVAILABLE",
            blocking.get(
                "require_metric_available"
            ) is True,
            (
                valid_number(metric)
                and not reconciliation_deferred
            ),
            {
                "value": metric,
                "source": metric_source,
                "diagnostics":
                    metric_diagnostics,
            },
            "NUMERIC_NON_DEFERRED_METRIC",
        ),
    ]

    failed = [
        check["name"]
        for check in checks
        if check["required"]
        and not check["passed"]
    ]

    # Ticker/identity consistency are always fail-closed,
    # independent of policy toggles.
    for mandatory_name in (
        "TICKER_CONSISTENCY",
        "IDENTITY_CONSISTENCY",
    ):
        check = next(
            item
            for item in checks
            if item["name"] == mandatory_name
        )
        if (
            not check["passed"]
            and mandatory_name not in failed
        ):
            failed.append(mandatory_name)

    if reconciliation_deferred:
        if (
            "DEFERRED_RECONCILIATION_STATUS"
            not in failed
        ):
            failed.append(
                "DEFERRED_RECONCILIATION_STATUS"
            )

    if failed:
        quality_status = "BLOCKED"
        analytically_usable = False
        reason = (
            "DEFERRED_RECONCILIATION_METRIC_CONTRACT"
            if reconciliation_deferred
            else "BLOCKING_CONTROL_FAILED"
        )
    else:
        quality_status = "VERIFIED"
        analytically_usable = True
        reason = "QUALITY_GATE_VERIFIED"

    return {
        "quality_gate_version": VERSION,
        "policy_version": policy.get(
            "policy_version"
        ),
        "ticker": ticker,
        "quality_status": quality_status,
        "analytically_usable":
            analytically_usable,
        "reason": reason,
        "blocking_controls_passed":
            not failed,
        "failed_blocking_controls":
            failed,
        "metric": {
            "name":
                policy["metric"]["name"],
            "value": metric,
            "metric_source": metric_source,
            "previous_short_interest_shares":
                previous_value,
            "current_short_interest_shares":
                current_value,
            "reconciliation_status":
                reconciliation_status,
        },
        "provenance": deepcopy(provenance),
        "checks": checks,
        "raw_normalized_asset":
            deepcopy(normalized_asset),
        "raw_boundary_asset":
            deepcopy(boundary_asset),
    }


def index_assets(
    document: dict[str, Any],
    document_name: str,
) -> dict[str, dict[str, Any]]:
    assets = document.get("assets")

    if not isinstance(assets, list):
        raise QualityGateError(
            f"{document_name} sem assets."
        )

    indexed: dict[str, dict[str, Any]] = {}

    for asset in assets:
        if not isinstance(asset, dict):
            raise QualityGateError(
                f"{document_name}: asset invalido."
            )

        ticker = asset.get("ticker")
        if not non_empty_string(ticker):
            raise QualityGateError(
                f"{document_name}: asset sem ticker."
            )

        if ticker in indexed:
            raise QualityGateError(
                f"{document_name}: ticker duplicado: {ticker}"
            )

        indexed[ticker] = asset

    return indexed


def run_quality_gate(
    boundary_document: dict[str, Any],
    normalized_document: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    validate_policy(policy)

    boundary_assets = index_assets(
        boundary_document,
        "Boundary document",
    )
    normalized_assets = index_assets(
        normalized_document,
        "Normalized document",
    )

    # Boundary define o universo avaliado. Ausencia do fato
    # correspondente no Normalizer sera UNAVAILABLE.
    results: list[dict[str, Any]] = []

    for ticker, boundary_asset in (
        boundary_assets.items()
    ):
        results.append(
            evaluate_quality(
                boundary_asset,
                normalized_assets.get(ticker),
                policy,
            )
        )

    summary = {
        "total_assets": len(results),
        "verified": sum(
            1
            for result in results
            if result["quality_status"]
            == "VERIFIED"
        ),
        "blocked": sum(
            1
            for result in results
            if result["quality_status"]
            == "BLOCKED"
        ),
        "unavailable": sum(
            1
            for result in results
            if result["quality_status"]
            == "UNAVAILABLE"
        ),
        "analytically_usable": sum(
            1
            for result in results
            if result["analytically_usable"]
        ),
    }

    return {
        "version": VERSION,
        "domain": "SHORT_INTEREST",
        "policy_version":
            policy.get("policy_version"),
        "summary": summary,
        "assets": results,
    }


def main() -> int:
    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST")
    print("QUALITY GATE")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:
        boundary_document = read_json(
            DEFAULT_BOUNDARY_INPUT
        )
        normalized_document = read_json(
            DEFAULT_NORMALIZED_INPUT
        )
        policy = read_json(
            DEFAULT_POLICY
        )

        output = run_quality_gate(
            boundary_document,
            normalized_document,
            policy,
        )

        write_json(
            DEFAULT_OUTPUT,
            output,
        )

    except Exception as exc:
        print(
            f"ERRO: {type(exc).__name__}: {exc}"
        )
        return 1

    for asset in output["assets"]:
        print("-" * 72)
        print(f"Ticker: {asset['ticker']}")
        print(
            "Quality:",
            asset["quality_status"],
        )
        print(
            "Analytically usable:",
            asset["analytically_usable"],
        )
        print(
            "Reason:",
            asset["reason"],
        )
        print(
            "Failed controls:",
            asset[
                "failed_blocking_controls"
            ],
        )

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    for key, value in output["summary"].items():
        print(f"{key}: {value}")

    print(f"Output: {DEFAULT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
