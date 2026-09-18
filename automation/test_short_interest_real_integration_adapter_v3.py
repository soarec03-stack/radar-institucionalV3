from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


VERSION = "3.4D.2-B.2C.8D.1"

BASE_DIR = Path(__file__).resolve().parent.parent
AUTOMATION_DIR = BASE_DIR / "automation"

if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))


from short_interest_real_integration_adapter_v3 import (  # noqa: E402
    INPUT_FILE,
    POLICY_FILE,
    RealIntegrationAdapterError,
    build_adapter_case,
    read_json,
    run_real_adapter,
)


class TestFailure(Exception):
    pass


def assert_true(
    condition: bool,
    message: str,
) -> None:
    if not condition:
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


def assert_raises(
    exception_type: type[BaseException],
    fn: Callable[[], Any],
    message: str,
) -> None:
    try:
        fn()
    except exception_type:
        return
    except Exception as exc:
        raise TestFailure(
            f"{message}. "
            f"Exceção inesperada: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    raise TestFailure(
        f"{message}. "
        f"Exceção {exception_type.__name__} "
        "não foi lançada."
    )


def get_real_inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    return (
        read_json(INPUT_FILE),
        read_json(POLICY_FILE),
    )


def get_asset(
    data: dict[str, Any],
    ticker: str,
) -> dict[str, Any]:
    assets = data.get("assets")

    if not isinstance(assets, list):
        raise TestFailure(
            "Input real não contém assets válidos."
        )

    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and asset.get("ticker") == ticker
    ]

    if len(matches) != 1:
        raise TestFailure(
            f"Esperado exatamente um asset {ticker}; "
            f"encontrados={len(matches)}."
        )

    return matches[0]


# ----------------------------------------------------------------------
# TEST 1
# ----------------------------------------------------------------------

def test_real_state_all_blocked() -> None:
    data, policy = get_real_inputs()

    result = run_real_adapter(
        deepcopy(data),
        deepcopy(policy),
    )

    expected_summary = {
        "total_assets": 3,
        "blocked": 3,
        "ready_for_reconciliation": 0,
        "reconciler_invocations": 0,
        "analytically_usable": 0,
    }

    assert_equal(
        result["summary"],
        expected_summary,
        "Resumo real inesperado",
    )

    tickers = sorted(
        asset["ticker"]
        for asset in result["assets"]
    )

    assert_equal(
        tickers,
        ["CRSP", "ETON", "VRT"],
        "Universo real inesperado",
    )


# ----------------------------------------------------------------------
# TEST 2
# ----------------------------------------------------------------------

def test_unresolved_never_reaches_reconciler() -> None:
    data, policy = get_real_inputs()

    result = run_real_adapter(
        deepcopy(data),
        deepcopy(policy),
    )

    for asset in result["assets"]:
        adapter_result = asset["adapter_result"]

        assert_equal(
            adapter_result["review_status"],
            "UNRESOLVED",
            f"{asset['ticker']}: review deveria "
            "permanecer UNRESOLVED",
        )

        assert_equal(
            adapter_result["integration_status"],
            "BLOCKED",
            f"{asset['ticker']}: UNRESOLVED "
            "deveria bloquear integração",
        )

        assert_equal(
            adapter_result["route"],
            "NONE",
            f"{asset['ticker']}: route deveria "
            "ser NONE",
        )

        assert_equal(
            adapter_result[
                "reconciler_input_status"
            ],
            "UNRESOLVED",
            f"{asset['ticker']}: status para "
            "Reconciler deveria ser UNRESOLVED",
        )

        assert_equal(
            asset["reconciler_invoked"],
            False,
            f"{asset['ticker']}: Reconciler "
            "não pode ser invocado",
        )

        assert_equal(
            asset["analytically_usable"],
            False,
            f"{asset['ticker']}: não pode "
            "ser analytically usable",
        )


# ----------------------------------------------------------------------
# TEST 3
# ----------------------------------------------------------------------

def test_real_diagnostic_preserved() -> None:
    data, policy = get_real_inputs()

    result = run_real_adapter(
        deepcopy(data),
        deepcopy(policy),
    )

    for asset in result["assets"]:
        diagnostics = (
            asset["adapter_result"]
            .get("diagnostics", [])
        )

        assert_equal(
            diagnostics,
            ["AUTHORITATIVE_EVIDENCE_CONFLICT"],
            f"{asset['ticker']}: diagnóstico "
            "real inesperado",
        )


# ----------------------------------------------------------------------
# TEST 4
# ----------------------------------------------------------------------

def test_bridge_does_not_invent_action_evidence() -> None:
    data, _ = get_real_inputs()

    for ticker in ["CRSP", "ETON", "VRT"]:
        asset = get_asset(
            data,
            ticker,
        )

        case = build_adapter_case(
            deepcopy(asset)
        )

        assert_equal(
            case["action_evidence"],
            None,
            f"{ticker}: bridge não pode "
            "inventar action_evidence",
        )


# ----------------------------------------------------------------------
# TEST 5
# ----------------------------------------------------------------------

def test_unresolved_source_adjustment_remains_unresolved() -> None:
    data, _ = get_real_inputs()

    for ticker in ["CRSP", "ETON", "VRT"]:
        asset = get_asset(
            data,
            ticker,
        )

        case = build_adapter_case(
            deepcopy(asset)
        )

        assert_equal(
            case["source_adjustment"],
            {"status": "UNRESOLVED"},
            f"{ticker}: source adjustment "
            "não pode ser inferido",
        )


# ----------------------------------------------------------------------
# TEST 6
# ----------------------------------------------------------------------

def test_identity_mismatch_blocks_bridge() -> None:
    data, _ = get_real_inputs()

    asset = deepcopy(
        get_asset(data, "CRSP")
    )

    asset["review_case"]["identity"][
        "ticker"
    ] = "WRONG"

    assert_raises(
        RealIntegrationAdapterError,
        lambda: build_adapter_case(asset),
        "Identity mismatch deveria bloquear",
    )


# ----------------------------------------------------------------------
# TEST 7
# ----------------------------------------------------------------------

def test_settlement_window_mismatch_blocks_bridge() -> None:
    data, _ = get_real_inputs()

    asset = deepcopy(
        get_asset(data, "ETON")
    )

    asset["review_result"][
        "current_settlement_date"
    ] = "2026-09-01"

    assert_raises(
        RealIntegrationAdapterError,
        lambda: build_adapter_case(asset),
        "Settlement mismatch deveria bloquear",
    )


# ----------------------------------------------------------------------
# TEST 8
# ----------------------------------------------------------------------

def test_invalid_review_status_blocks_bridge() -> None:
    data, _ = get_real_inputs()

    asset = deepcopy(
        get_asset(data, "VRT")
    )

    asset["review_result"][
        "review_status"
    ] = "NO_ACTION"

    assert_raises(
        RealIntegrationAdapterError,
        lambda: build_adapter_case(asset),
        "Review status inválido deveria bloquear",
    )


# ----------------------------------------------------------------------
# TEST 9
# ----------------------------------------------------------------------

def test_duplicate_ticker_blocks_pipeline() -> None:
    data, policy = get_real_inputs()

    mutated = deepcopy(data)

    mutated["assets"].append(
        deepcopy(mutated["assets"][0])
    )

    assert_raises(
        RealIntegrationAdapterError,
        lambda: run_real_adapter(
            mutated,
            deepcopy(policy),
        ),
        "Ticker duplicado deveria bloquear pipeline",
    )


# ----------------------------------------------------------------------
# TEST 10
# ----------------------------------------------------------------------

def test_inputs_are_not_mutated() -> None:
    data, policy = get_real_inputs()

    original_data = deepcopy(data)
    original_policy = deepcopy(policy)

    run_real_adapter(
        data,
        policy,
    )

    assert_equal(
        data,
        original_data,
        "Input real foi mutado",
    )

    assert_equal(
        policy,
        original_policy,
        "Policy foi mutada",
    )


def run_test(
    number: int,
    name: str,
    fn: Callable[[], None],
) -> bool:
    print("-" * 72)
    print(
        f"TESTE {number}: {name}"
    )

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
    print("REAL INTEGRATION ADAPTER")
    print("REGRESSION TEST")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    tests = [
        (
            "Real current state all blocked",
            test_real_state_all_blocked,
        ),
        (
            "UNRESOLVED never reaches Reconciler",
            test_unresolved_never_reaches_reconciler,
        ),
        (
            "Real diagnostic is preserved",
            test_real_diagnostic_preserved,
        ),
        (
            "Bridge never invents action evidence",
            test_bridge_does_not_invent_action_evidence,
        ),
        (
            "UNRESOLVED source adjustment stays unresolved",
            test_unresolved_source_adjustment_remains_unresolved,
        ),
        (
            "Identity mismatch blocks bridge",
            test_identity_mismatch_blocks_bridge,
        ),
        (
            "Settlement window mismatch blocks bridge",
            test_settlement_window_mismatch_blocks_bridge,
        ),
        (
            "Invalid review status blocks bridge",
            test_invalid_review_status_blocks_bridge,
        ),
        (
            "Duplicate ticker blocks pipeline",
            test_duplicate_ticker_blocks_pipeline,
        ),
        (
            "Inputs are not mutated",
            test_inputs_are_not_mutated,
        ),
    ]

    passed = 0

    for index, (name, fn) in enumerate(
        tests,
        start=1,
    ):
        if run_test(
            index,
            name,
            fn,
        ):
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
        print(
            "RESULTADO FINAL: APROVADO"
        )
        return 0

    print(
        "RESULTADO FINAL: REPROVADO"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())