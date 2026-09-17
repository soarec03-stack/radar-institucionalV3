"""
RADAR INSTITUCIONAL V3
SHORT INTEREST CORPORATE ACTION ADJUSTMENT
PRODUCTION REGRESSION TEST

Version:
3.4D.2-B.2C.6

Objetivo:
validar a matematica de ajuste usando diretamente
as funcoes implementadas no reconciliador oficial.

Nao duplica a implementacao matematica.

Nao acessa rede.
Nao acessa SEC.
Nao acessa FINRA.
Nao modifica registry.
Nao modifica radar.
Nao modifica Signal, Confidence, Score ou Decision.
"""

from __future__ import annotations

import math
import sys
from typing import Any

from short_interest_corporate_action_reconciler_v3 import (
    ReconciliationError,
    deterministic_adjustment_factor,
    adjust_previous_to_current_basis,
    calculate_adjusted_change_pct,
)


VERSION = "3.4D.2-B.2C.6"


class TestFailure(Exception):
    pass


def assert_close(
    actual: float,
    expected: float,
    field: str,
) -> None:

    if not math.isclose(
        float(actual),
        float(expected),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise TestFailure(
            f"{field}: esperado {expected}, "
            f"recebido {actual}."
        )


def execute_case(
    name: str,
    previous_raw: float,
    current_raw: float,
    ratio_numerator: float,
    ratio_denominator: float,
    expected_factor: float,
    expected_previous_adjusted: float,
    expected_change_pct: float,
) -> dict[str, Any]:

    action = {
        "ratio_numerator": ratio_numerator,
        "ratio_denominator": ratio_denominator,
    }

    factor = deterministic_adjustment_factor(action)

    if factor is None:
        raise TestFailure(
            "Reconciler retornou adjustment_factor None."
        )

    previous_adjusted = (
        adjust_previous_to_current_basis(
            previous_raw,
            factor,
        )
    )

    adjusted_change_pct = (
        calculate_adjusted_change_pct(
            previous_adjusted,
            current_raw,
        )
    )

    assert_close(
        factor,
        expected_factor,
        "adjustment_factor",
    )

    assert_close(
        previous_adjusted,
        expected_previous_adjusted,
        "previous_adjusted",
    )

    assert_close(
        adjusted_change_pct,
        expected_change_pct,
        "adjusted_change_pct",
    )

    return {
        "case": name,
        "previous_raw": previous_raw,
        "current_raw": current_raw,
        "factor": factor,
        "previous_adjusted": previous_adjusted,
        "adjusted_change_pct": adjusted_change_pct,
    }


def test_stock_split_neutral() -> dict[str, Any]:

    return execute_case(
        name="STOCK_SPLIT_2_FOR_1_NEUTRAL",
        previous_raw=100.0,
        current_raw=200.0,
        ratio_numerator=2.0,
        ratio_denominator=1.0,
        expected_factor=2.0,
        expected_previous_adjusted=200.0,
        expected_change_pct=0.0,
    )


def test_reverse_split_neutral() -> dict[str, Any]:

    return execute_case(
        name="REVERSE_SPLIT_1_FOR_10_NEUTRAL",
        previous_raw=1000.0,
        current_raw=100.0,
        ratio_numerator=1.0,
        ratio_denominator=10.0,
        expected_factor=0.1,
        expected_previous_adjusted=100.0,
        expected_change_pct=0.0,
    )


def test_stock_split_real_change() -> dict[str, Any]:

    return execute_case(
        name="STOCK_SPLIT_2_FOR_1_WITH_REAL_CHANGE",
        previous_raw=100.0,
        current_raw=220.0,
        ratio_numerator=2.0,
        ratio_denominator=1.0,
        expected_factor=2.0,
        expected_previous_adjusted=200.0,
        expected_change_pct=10.0,
    )


def test_previous_adjusted_zero_blocks() -> None:

    try:
        calculate_adjusted_change_pct(
            0.0,
            100.0,
        )

    except ReconciliationError:
        return

    raise TestFailure(
        "previous_adjusted=0 deveria bloquear "
        "o calculo percentual."
    )


def test_invalid_ratio_blocks() -> None:

    action = {
        "ratio_numerator": 2.0,
        "ratio_denominator": 0.0,
    }

    factor = deterministic_adjustment_factor(action)

    if factor is not None:
        raise TestFailure(
            "Ratio com denominator=0 deveria "
            "retornar adjustment_factor None."
        )


def run_test(
    number: int,
    name: str,
    function,
) -> bool:

    print("-" * 72)
    print(f"TESTE {number}: {name}")

    try:
        result = function()

        print("RESULTADO: PASS")

        if isinstance(result, dict):
            print(
                "Previous raw:",
                result["previous_raw"],
            )
            print(
                "Current raw:",
                result["current_raw"],
            )
            print(
                "Factor:",
                result["factor"],
            )
            print(
                "Previous adjusted:",
                result["previous_adjusted"],
            )
            print(
                "Adjusted change:",
                f"{result['adjusted_change_pct']:.6f}%",
            )

        return True

    except (
        TestFailure,
        ReconciliationError,
    ) as exc:

        print("RESULTADO: FAIL")
        print("ERRO:", exc)
        return False


def main() -> int:

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST CORPORATE ACTION")
    print("PRODUCTION ADJUSTMENT REGRESSION TEST")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    tests = [
        (
            1,
            "2-for-1 stock split - neutral",
            test_stock_split_neutral,
        ),
        (
            2,
            "1-for-10 reverse split - neutral",
            test_reverse_split_neutral,
        ),
        (
            3,
            "2-for-1 stock split - real +10% change",
            test_stock_split_real_change,
        ),
        (
            4,
            "previous adjusted zero blocks percentage",
            test_previous_adjusted_zero_blocks,
        ),
        (
            5,
            "invalid split ratio blocks adjustment",
            test_invalid_ratio_blocks,
        ),
    ]

    passed = 0
    failed = 0

    for number, name, function in tests:
        if run_test(
            number,
            name,
            function,
        ):
            passed += 1
        else:
            failed += 1

    print("=" * 72)
    print("RESUMO")
    print("=" * 72)
    print("Total :", len(tests))
    print("PASS  :", passed)
    print("FAIL  :", failed)

    if failed:
        print("RESULTADO FINAL: REPROVADO")
        return 1

    print("RESULTADO FINAL: APROVADO")
    return 0


if __name__ == "__main__":
    sys.exit(main())