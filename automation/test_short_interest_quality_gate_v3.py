from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


VERSION = "3.4D.2-B.2C.8F.3"

BASE_DIR = Path(__file__).resolve().parent.parent
AUTOMATION_DIR = BASE_DIR / "automation"

if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))

from short_interest_quality_gate_v3 import (  # noqa: E402
    evaluate_quality,
    run_quality_gate,
)


POLICY_FILE = (
    AUTOMATION_DIR
    / "short_interest_quality_policy_v3.json"
)


class TestFailure(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        value = json.load(file)

    if not isinstance(value, dict):
        raise TestFailure(
            f"{path}: root deve ser objeto."
        )

    return value


def assert_true(
    value: Any,
    message: str,
) -> None:
    if value is not True:
        raise TestFailure(message)


def assert_equal(
    actual: Any,
    expected: Any,
    message: str,
) -> None:
    if actual != expected:
        raise TestFailure(
            f"{message}. "
            f"Esperado={expected!r}; "
            f"Obtido={actual!r}"
        )


def assert_close(
    actual: Any,
    expected: float,
    message: str,
    tolerance: float = 1e-9,
) -> None:
    if (
        not isinstance(actual, (int, float))
        or isinstance(actual, bool)
        or abs(float(actual) - expected)
        > tolerance
    ):
        raise TestFailure(
            f"{message}. "
            f"Esperado={expected!r}; "
            f"Obtido={actual!r}"
        )


def build_normalized_asset(
    ticker: str = "TEST",
    listing_exchange: str = "NASDAQ",
    cusip: str = "123456789",
    previous_date: str = "2026-08-14",
    current_date: str = "2026-08-31",
    previous_shares: int = 100,
    current_shares: int = 110,
    calculated_change_pct: float = 10.0,
    source: str = "FINRA",
    source_tier: str = "TIER_1",
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "normalization_status": "NORMALIZED",
        "structurally_compatible": True,
        "identity": {
            "ticker": ticker,
            "listing_exchange":
                listing_exchange,
            "issuer_name": "Synthetic Issuer",
            "security_identity": {
                "type": "CUSIP",
                "value": cusip,
            },
            "cusip": cusip,
            "sec_cik": "0000000001",
            "identity_continuity_status":
                "VERIFIED",
        },
        "settlement_window": {
            "previous_settlement_date":
                previous_date,
            "current_settlement_date":
                current_date,
        },
        "short_interest": {
            "metric_name":
                "short_interest_change_pct",
            "unit": "PERCENT",
            "previous_short_interest_shares":
                previous_shares,
            "current_short_interest_shares":
                current_shares,
            "collector_calculated_change_shares":
                current_shares - previous_shares,
            "collector_calculated_change_pct":
                calculated_change_pct,
            "source_reported_change_shares":
                current_shares - previous_shares,
            "source_reported_change_pct":
                calculated_change_pct,
        },
        "sources": {
            "short_interest": {
                "source": source,
                "source_tier": source_tier,
                "dataset":
                    "CONSOLIDATED_SHORT_INTEREST",
                "retrieved_at":
                    "2026-09-16T21:52:29Z",
                "market_date":
                    current_date,
                "verification_status":
                    "OFFICIAL_SOURCE",
            }
        },
        "raw_upstream": {
            "short_interest_collection": {
                "ticker": ticker,
                "provenance": {
                    "source": source,
                    "source_tier": source_tier,
                    "dataset":
                        "CONSOLIDATED_SHORT_INTEREST",
                },
            },
            "corporate_action_evidence": {
                "ticker": ticker,
            },
        },
    }


def build_boundary_asset(
    ticker: str = "TEST",
    listing_exchange: str = "NASDAQ",
    cusip: str = "123456789",
    previous_date: str = "2026-08-14",
    current_date: str = "2026-08-31",
    boundary_status: str = "RECONCILED",
    reconciler_invoked: bool = True,
    reconciliation_status: str = "NO_ACTION",
    previous_shares: int = 100,
    current_shares: int = 110,
    adjusted_change_pct: float | None = None,
    adjustment_factor: float | None = None,
) -> dict[str, Any]:
    review_result = {
        "previous_settlement_date":
            previous_date,
        "current_settlement_date":
            current_date,
        "review_status": "VERIFIED",
    }

    adapter_case = {
        "case": ticker,
        "ticker": ticker,
        "identity": {
            "ticker": ticker,
            "listing_exchange":
                listing_exchange,
            "security_identity":
                f"CUSIP:{cusip}",
            "continuity_status":
                "VERIFIED",
        },
        "previous_settlement_date":
            previous_date,
        "current_settlement_date":
            current_date,
    }

    if boundary_status != "RECONCILED":
        reconciler_result = None
        analytically_usable = False
        reconciler_invoked = False
    elif reconciliation_status == "NO_ACTION":
        reconciler_result = {
            "case": ticker,
            "corporate_action_status":
                "NO_ACTION",
            "reconciliation_status":
                "NO_ACTION",
            "identity_continuity_status":
                "VERIFIED",
            "source_adjustment_status":
                "NOT_APPLICABLE",
            "adjustment_status":
                "NOT_REQUIRED",
            "adjustment_authorized": False,
            "adjustment_factor": None,
            "analytically_usable": True,
            "reason":
                "NO_APPLICABLE_CORPORATE_ACTION_CONFIRMED",
            "evidence_summary": {
                "official_window_review_completed":
                    True,
                "authoritative_source_review_present":
                    True,
            },
            "diagnostics": [],
        }
        analytically_usable = True
    elif (
        reconciliation_status
        == "VERIFIED_ACTION"
    ):
        factor = (
            adjustment_factor
            if adjustment_factor is not None
            else 2.0
        )
        previous_adjusted = (
            previous_shares * factor
        )
        metric = (
            adjusted_change_pct
            if adjusted_change_pct is not None
            else (
                (
                    current_shares
                    - previous_adjusted
                )
                / previous_adjusted
                * 100.0
            )
        )
        reconciler_result = {
            "case": ticker,
            "corporate_action_status":
                "VERIFIED_ACTION",
            "reconciliation_status":
                "VERIFIED_ACTION",
            "identity_continuity_status":
                "VERIFIED",
            "source_adjustment_status":
                "NOT_ADJUSTED",
            "adjustment_status":
                "REQUIRED",
            "adjustment_authorized": True,
            "adjustment_factor": factor,
            "previous_raw":
                float(previous_shares),
            "previous_adjusted":
                float(previous_adjusted),
            "current_raw":
                float(current_shares),
            "adjusted_change_pct":
                float(metric),
            "analytically_usable": True,
            "reason":
                "VERIFIED_ACTION_REQUIRES_DETERMINISTIC_ADJUSTMENT",
            "evidence_summary": {
                "adjustment_basis":
                    "CURRENT_SETTLEMENT_BASIS",
                "adjusted_snapshot":
                    "PREVIOUS_SETTLEMENT",
            },
            "diagnostics": [],
        }
        analytically_usable = True
    elif (
        reconciliation_status
        == "SOURCE_ADJUSTED"
    ):
        reconciler_result = {
            "case": ticker,
            "corporate_action_status":
                "VERIFIED_ACTION",
            "reconciliation_status":
                "SOURCE_ADJUSTED",
            "identity_continuity_status":
                "VERIFIED",
            "source_adjustment_status":
                "SOURCE_ADJUSTED",
            "adjustment_status":
                "SOURCE_ALREADY_ADJUSTED",
            "adjustment_authorized": False,
            "adjustment_factor": None,
            "analytically_usable": True,
            "reason":
                "VERIFIED_ACTION_ALREADY_ADJUSTED_BY_AUTHORITATIVE_SOURCE",
            "evidence_summary": {
                "applicable_action_count": 1,
            },
            "diagnostics": [
                "DOUBLE_ADJUSTMENT_PROHIBITED"
            ],
        }
        analytically_usable = True
    else:
        reconciler_result = {
            "case": ticker,
            "corporate_action_status":
                "UNRESOLVED",
            "reconciliation_status":
                reconciliation_status,
            "identity_continuity_status":
                "VERIFIED",
            "adjustment_status": "BLOCKED",
            "adjustment_authorized": False,
            "adjustment_factor": None,
            "analytically_usable": False,
            "diagnostics": [],
        }
        analytically_usable = False

    return {
        "ticker": ticker,
        "boundary_version":
            "3.4D.2-B.2C.8E.1",
        "boundary_status":
            boundary_status,
        "reconciler_invoked":
            reconciler_invoked,
        "reconciler_result":
            reconciler_result,
        "analytically_usable":
            analytically_usable,
        "authoritative_conflict_semantics": {
            "status": "VERIFIED_NO_CONFLICT",
        },
        "diagnostics": [],
        "raw_adapter_asset": {
            "ticker": ticker,
            "adapter_case": adapter_case,
            "adapter_result": {
                "integration_status":
                    (
                        "READY"
                        if boundary_status
                        == "RECONCILED"
                        else "BLOCKED"
                    ),
                "route":
                    (
                        "RECONCILER"
                        if boundary_status
                        == "RECONCILED"
                        else "NONE"
                    ),
            },
        },
        "raw_review_asset": {
            "ticker": ticker,
            "review_case": {
                "ticker": ticker,
                "identity":
                    deepcopy(
                        adapter_case["identity"]
                    ),
                "previous_settlement_date":
                    previous_date,
                "current_settlement_date":
                    current_date,
            },
            "review_result":
                review_result,
        },
    }


def test_fact_absent_unavailable() -> None:
    policy = read_json(POLICY_FILE)
    boundary = build_boundary_asset()

    result = evaluate_quality(
        boundary,
        None,
        policy,
    )

    assert_equal(
        result["quality_status"],
        "UNAVAILABLE",
        "Fact ausente deve ser UNAVAILABLE",
    )
    assert_equal(
        result["analytically_usable"],
        False,
        "UNAVAILABLE nao pode ser utilizavel",
    )


def test_fact_present_boundary_blocked() -> None:
    policy = read_json(POLICY_FILE)
    normalized = build_normalized_asset()
    boundary = build_boundary_asset(
        boundary_status="BLOCKED",
    )

    result = evaluate_quality(
        boundary,
        normalized,
        policy,
    )

    assert_equal(
        result["quality_status"],
        "BLOCKED",
        "Fact presente com Boundary bloqueado deve ser BLOCKED",
    )

    for name in [
        "BOUNDARY_RECONCILED",
        "RECONCILER_INVOKED",
        "RECONCILER_ANALYTICALLY_USABLE",
    ]:
        assert_true(
            name
            in result[
                "failed_blocking_controls"
            ],
            f"Controle esperado nao falhou: {name}",
        )


def test_no_action_verified() -> None:
    policy = read_json(POLICY_FILE)
    normalized = build_normalized_asset(
        previous_shares=100,
        current_shares=110,
        calculated_change_pct=10.0,
    )
    boundary = build_boundary_asset(
        reconciliation_status="NO_ACTION",
        previous_shares=100,
        current_shares=110,
    )

    result = evaluate_quality(
        boundary,
        normalized,
        policy,
    )

    assert_equal(
        result["quality_status"],
        "VERIFIED",
        "NO_ACTION valido deve ser VERIFIED",
    )
    assert_equal(
        result["metric"]["metric_source"],
        "NORMALIZED_FINRA_FACT",
        "NO_ACTION deve usar Normalizer",
    )
    assert_close(
        result["metric"]["value"],
        10.0,
        "Metrica NO_ACTION incorreta",
    )


def test_verified_action_uses_adjusted_metric() -> None:
    policy = read_json(POLICY_FILE)

    normalized = build_normalized_asset(
        previous_shares=100,
        current_shares=220,
        calculated_change_pct=120.0,
    )
    boundary = build_boundary_asset(
        reconciliation_status=
            "VERIFIED_ACTION",
        previous_shares=100,
        current_shares=220,
        adjustment_factor=2.0,
        adjusted_change_pct=10.0,
    )

    result = evaluate_quality(
        boundary,
        normalized,
        policy,
    )

    assert_equal(
        result["quality_status"],
        "VERIFIED",
        "VERIFIED_ACTION valido deve ser VERIFIED",
    )
    assert_equal(
        result["metric"]["metric_source"],
        "RECONCILER",
        "VERIFIED_ACTION deve usar Reconciler",
    )
    assert_close(
        result["metric"]["value"],
        10.0,
        "Deve usar adjusted_change_pct",
    )

    if result["metric"]["value"] == 120.0:
        raise TestFailure(
            "Quality Gate usou metrica nao ajustada do Normalizer."
        )


def test_source_adjusted_deferred_blocked() -> None:
    policy = read_json(POLICY_FILE)
    normalized = build_normalized_asset(
        previous_shares=1000,
        current_shares=100,
        calculated_change_pct=-90.0,
    )
    boundary = build_boundary_asset(
        reconciliation_status=
            "SOURCE_ADJUSTED",
        previous_shares=1000,
        current_shares=100,
    )

    result = evaluate_quality(
        boundary,
        normalized,
        policy,
    )

    assert_equal(
        result["quality_status"],
        "BLOCKED",
        "SOURCE_ADJUSTED deve permanecer BLOCKED",
    )
    assert_equal(
        result["reason"],
        "DEFERRED_RECONCILIATION_METRIC_CONTRACT",
        "Reason SOURCE_ADJUSTED invalido",
    )
    assert_equal(
        result["metric"]["value"],
        None,
        "SOURCE_ADJUSTED nao pode inventar metrica",
    )
    assert_true(
        "DEFERRED_RECONCILIATION_STATUS"
        in result["failed_blocking_controls"],
        "Deferred status deve bloquear",
    )


def test_ticker_mismatch_blocked() -> None:
    policy = read_json(POLICY_FILE)
    normalized = build_normalized_asset(
        ticker="OTHER",
    )
    boundary = build_boundary_asset(
        ticker="TEST",
    )

    result = evaluate_quality(
        boundary,
        normalized,
        policy,
    )

    assert_equal(
        result["quality_status"],
        "BLOCKED",
        "Ticker mismatch deve bloquear",
    )
    assert_true(
        "TICKER_CONSISTENCY"
        in result["failed_blocking_controls"],
        "Ticker consistency deve falhar",
    )


def test_identity_mismatch_blocked() -> None:
    policy = read_json(POLICY_FILE)
    normalized = build_normalized_asset(
        cusip="123456789",
    )
    boundary = build_boundary_asset(
        cusip="987654321",
    )

    result = evaluate_quality(
        boundary,
        normalized,
        policy,
    )

    assert_equal(
        result["quality_status"],
        "BLOCKED",
        "Identity mismatch deve bloquear",
    )
    assert_true(
        "IDENTITY_CONSISTENCY"
        in result["failed_blocking_controls"],
        "Identity consistency deve falhar",
    )


def test_window_mismatch_blocked() -> None:
    policy = read_json(POLICY_FILE)
    normalized = build_normalized_asset(
        previous_date="2026-08-14",
        current_date="2026-08-31",
    )
    boundary = build_boundary_asset(
        previous_date="2026-08-15",
        current_date="2026-08-31",
    )

    result = evaluate_quality(
        boundary,
        normalized,
        policy,
    )

    assert_equal(
        result["quality_status"],
        "BLOCKED",
        "Settlement window mismatch deve bloquear",
    )
    assert_true(
        "EXACT_SETTLEMENT_WINDOW"
        in result["failed_blocking_controls"],
        "Exact settlement window deve falhar",
    )


def test_non_tier1_provenance_blocked() -> None:
    policy = read_json(POLICY_FILE)
    normalized = build_normalized_asset(
        source_tier="TIER_2",
    )
    boundary = build_boundary_asset()

    result = evaluate_quality(
        boundary,
        normalized,
        policy,
    )

    assert_equal(
        result["quality_status"],
        "BLOCKED",
        "Provenance nao TIER_1 deve bloquear",
    )
    assert_true(
        "TIER_1_SHORT_INTEREST_PROVENANCE"
        in result["failed_blocking_controls"],
        "TIER_1 provenance deve falhar",
    )


def test_zero_previous_blocked() -> None:
    policy = read_json(POLICY_FILE)
    normalized = build_normalized_asset(
        previous_shares=0,
        current_shares=10,
        calculated_change_pct=0.0,
    )
    boundary = build_boundary_asset(
        previous_shares=0,
        current_shares=10,
    )

    result = evaluate_quality(
        boundary,
        normalized,
        policy,
    )

    assert_equal(
        result["quality_status"],
        "BLOCKED",
        "Previous zero deve bloquear",
    )
    assert_true(
        "POSITIVE_PREVIOUS_SHORT_INTEREST"
        in result["failed_blocking_controls"],
        "Positive previous deve falhar",
    )


def test_inputs_immutable() -> None:
    policy = read_json(POLICY_FILE)
    normalized = build_normalized_asset()
    boundary = build_boundary_asset()

    normalized_before = deepcopy(normalized)
    boundary_before = deepcopy(boundary)

    evaluate_quality(
        boundary,
        normalized,
        policy,
    )

    assert_equal(
        normalized,
        normalized_before,
        "Normalized input foi mutado",
    )
    assert_equal(
        boundary,
        boundary_before,
        "Boundary input foi mutado",
    )


def test_run_gate_no_upstream_invocation() -> None:
    """
    O Quality Gate recebe documentos prontos.
    Este teste prova que run_quality_gate opera apenas
    sobre os contratos fornecidos e preserva os inputs.
    Nenhum Collector, Review ou Reconciler e passado ou
    invocado por esta interface.
    """

    policy = read_json(POLICY_FILE)

    normalized_document = {
        "version":
            "3.4D.2-B.2C.8B",
        "assets": [
            build_normalized_asset()
        ],
    }
    boundary_document = {
        "version":
            "3.4D.2-B.2C.8E.1",
        "assets": [
            build_boundary_asset()
        ],
    }

    normalized_before = deepcopy(
        normalized_document
    )
    boundary_before = deepcopy(
        boundary_document
    )

    output = run_quality_gate(
        boundary_document,
        normalized_document,
        policy,
    )

    assert_equal(
        output["summary"]["verified"],
        1,
        "Run gate deveria verificar fixture valida",
    )
    assert_equal(
        normalized_document,
        normalized_before,
        "Run gate mutou Normalized",
    )
    assert_equal(
        boundary_document,
        boundary_before,
        "Run gate mutou Boundary",
    )


def run_test(
    number: int,
    name: str,
    fn: Callable[[], None],
) -> bool:
    print("-" * 72)
    print(f"TESTE {number}: {name}")

    try:
        fn()
    except Exception as exc:
        print("RESULTADO: FAIL")
        print(
            f"ERRO: {type(exc).__name__}: {exc}"
        )
        return False

    print("RESULTADO: PASS")
    return True


def main() -> int:
    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST")
    print("QUALITY GATE REGRESSION")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    tests = [
        (
            "Fact absent -> UNAVAILABLE",
            test_fact_absent_unavailable,
        ),
        (
            "Fact present + Boundary blocked",
            test_fact_present_boundary_blocked,
        ),
        (
            "NO_ACTION -> VERIFIED",
            test_no_action_verified,
        ),
        (
            "VERIFIED_ACTION adjusted metric",
            test_verified_action_uses_adjusted_metric,
        ),
        (
            "SOURCE_ADJUSTED deferred",
            test_source_adjusted_deferred_blocked,
        ),
        (
            "Ticker mismatch",
            test_ticker_mismatch_blocked,
        ),
        (
            "Identity mismatch",
            test_identity_mismatch_blocked,
        ),
        (
            "Settlement window mismatch",
            test_window_mismatch_blocked,
        ),
        (
            "Non TIER_1 provenance",
            test_non_tier1_provenance_blocked,
        ),
        (
            "Previous short interest zero",
            test_zero_previous_blocked,
        ),
        (
            "Input immutability",
            test_inputs_immutable,
        ),
        (
            "Run gate isolated from upstream",
            test_run_gate_no_upstream_invocation,
        ),
    ]

    passed = 0

    for index, (name, fn) in enumerate(
        tests,
        start=1,
    ):
        if run_test(index, name, fn):
            passed += 1

    total = len(tests)
    failed = total - passed

    print("=" * 72)
    print("RESUMO")
    print("=" * 72)
    print(f"Total : {total}")
    print(f"PASS  : {passed}")
    print(f"FAIL  : {failed}")

    if failed == 0:
        print("RESULTADO FINAL: APROVADO")
        return 0

    print("RESULTADO FINAL: REPROVADO")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
