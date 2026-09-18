from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


VERSION = "3.4D.2-B.2C.8D.2.1"

BASE_DIR = Path(__file__).resolve().parent.parent
AUTOMATION_DIR = BASE_DIR / "automation"

if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))


from short_interest_authoritative_conflict_semantics_v3 import (  # noqa: E402
    POLICY_FILE,
    ConflictSemanticsError,
    classify_authoritative_conflict,
    read_json,
)


class TestFailure(Exception):
    pass


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
            f"{message}. Exceção inesperada: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    raise TestFailure(
        f"{message}. "
        f"{exception_type.__name__} não foi lançada."
    )


def policy() -> dict[str, Any]:
    return read_json(POLICY_FILE)


def review(
    *,
    raw_flag: bool,
    diagnostics: list[str],
) -> dict[str, Any]:
    return {
        "review_status": "UNRESOLVED",
        "no_authoritative_evidence_conflict":
            raw_flag,
        "diagnostics": deepcopy(diagnostics),
    }


# ----------------------------------------------------------------------
# TEST 1
# Explicit authoritative conflict
# ----------------------------------------------------------------------

def test_explicit_conflict() -> None:
    result = classify_authoritative_conflict(
        review(
            raw_flag=False,
            diagnostics=[
                "AUTHORITATIVE_EVIDENCE_CONFLICT"
            ],
        ),
        policy(),
    )

    assert_equal(
        result["status"],
        "CONFLICT_DETECTED",
        "Conflito explícito deve ser detectado",
    )

    assert_equal(
        result["reconciliation_allowed_by_semantics"],
        False,
        "Conflito explícito deve bloquear",
    )


# ----------------------------------------------------------------------
# TEST 2
# Explicit upstream no-conflict
# ----------------------------------------------------------------------

def test_verified_no_conflict() -> None:
    result = classify_authoritative_conflict(
        review(
            raw_flag=True,
            diagnostics=[],
        ),
        policy(),
    )

    assert_equal(
        result["status"],
        "VERIFIED_NO_CONFLICT",
        "True explícito deve significar "
        "VERIFIED_NO_CONFLICT",
    )

    assert_equal(
        result["reconciliation_allowed_by_semantics"],
        None,
        "Semântica não deve autorizar reconciliação "
        "por conta própria",
    )


# ----------------------------------------------------------------------
# TEST 3
# False without conflict diagnostic
# ----------------------------------------------------------------------

def test_false_without_conflict_is_not_established() -> None:
    result = classify_authoritative_conflict(
        review(
            raw_flag=False,
            diagnostics=[
                "MISSING_AUTHORITATIVE_SOURCE"
            ],
        ),
        policy(),
    )

    assert_equal(
        result["status"],
        "NOT_ESTABLISHED",
        "False sem diagnóstico de conflito "
        "não pode significar conflito",
    )

    assert_equal(
        result["reconciliation_allowed_by_semantics"],
        False,
        "NOT_ESTABLISHED deve permanecer fail closed",
    )


# ----------------------------------------------------------------------
# TEST 4
# Missing authoritative source is never conflict
# ----------------------------------------------------------------------

def test_missing_source_never_means_conflict() -> None:
    result = classify_authoritative_conflict(
        review(
            raw_flag=False,
            diagnostics=[
                "MISSING_AUTHORITATIVE_SOURCE"
            ],
        ),
        policy(),
    )

    assert_equal(
        result["explicit_conflict_diagnostic"],
        False,
        "Missing source não é conflito explícito",
    )

    assert_equal(
        result["status"],
        "NOT_ESTABLISHED",
        "Missing source deve permanecer "
        "NOT_ESTABLISHED",
    )


# ----------------------------------------------------------------------
# TEST 5
# Explicit conflict diagnostic has precedence
# ----------------------------------------------------------------------

def test_conflict_diagnostic_has_precedence() -> None:
    result = classify_authoritative_conflict(
        review(
            raw_flag=True,
            diagnostics=[
                "AUTHORITATIVE_EVIDENCE_CONFLICT"
            ],
        ),
        policy(),
    )

    assert_equal(
        result["status"],
        "CONFLICT_DETECTED",
        "Diagnóstico explícito de conflito "
        "deve ter precedência",
    )


# ----------------------------------------------------------------------
# TEST 6
# Invalid raw boolean
# ----------------------------------------------------------------------

def test_invalid_raw_flag_blocks() -> None:
    invalid_review = {
        "review_status": "UNRESOLVED",
        "no_authoritative_evidence_conflict":
            None,
        "diagnostics": [],
    }

    assert_raises(
        ConflictSemanticsError,
        lambda: classify_authoritative_conflict(
            invalid_review,
            policy(),
        ),
        "Raw flag não booleano deve bloquear",
    )


# ----------------------------------------------------------------------
# TEST 7
# Missing diagnostics
# ----------------------------------------------------------------------

def test_missing_diagnostics_blocks() -> None:
    invalid_review = {
        "review_status": "UNRESOLVED",
        "no_authoritative_evidence_conflict":
            False,
    }

    assert_raises(
        ConflictSemanticsError,
        lambda: classify_authoritative_conflict(
            invalid_review,
            policy(),
        ),
        "Diagnostics ausente deve bloquear",
    )


# ----------------------------------------------------------------------
# TEST 8
# Invalid diagnostics item
# ----------------------------------------------------------------------

def test_invalid_diagnostic_item_blocks() -> None:
    invalid_review = {
        "review_status": "UNRESOLVED",
        "no_authoritative_evidence_conflict":
            False,
        "diagnostics": [
            "MISSING_AUTHORITATIVE_SOURCE",
            123,
        ],
    }

    assert_raises(
        ConflictSemanticsError,
        lambda: classify_authoritative_conflict(
            invalid_review,
            policy(),
        ),
        "Diagnostic não string deve bloquear",
    )


# ----------------------------------------------------------------------
# TEST 9
# Input must not be mutated
# ----------------------------------------------------------------------

def test_input_not_mutated() -> None:
    source_review = review(
        raw_flag=False,
        diagnostics=[
            "MISSING_AUTHORITATIVE_SOURCE"
        ],
    )

    original = deepcopy(source_review)

    classify_authoritative_conflict(
        source_review,
        policy(),
    )

    assert_equal(
        source_review,
        original,
        "Review upstream não pode ser mutado",
    )


# ----------------------------------------------------------------------
# TEST 10
# Current real state
# ----------------------------------------------------------------------

def test_current_real_state() -> None:
    input_file = (
        BASE_DIR
        / "input"
        / "short_interest_real_positive_official_review_v3.json"
    )

    data = read_json(input_file)

    assets = data.get("assets")

    if not isinstance(assets, list):
        raise TestFailure(
            "Input real sem assets."
        )

    results = {}

    for asset in assets:
        ticker = asset.get("ticker")
        review_result = asset.get(
            "review_result"
        )

        result = classify_authoritative_conflict(
            review_result,
            policy(),
        )

        results[ticker] = result["status"]

    assert_equal(
        results,
        {
            "CRSP": "NOT_ESTABLISHED",
            "ETON": "NOT_ESTABLISHED",
            "VRT": "NOT_ESTABLISHED",
        },
        "Estado semântico real inesperado",
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
    print("AUTHORITATIVE CONFLICT SEMANTICS")
    print("REGRESSION TEST")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    tests = [
        (
            "Explicit conflict",
            test_explicit_conflict,
        ),
        (
            "Verified no conflict",
            test_verified_no_conflict,
        ),
        (
            "False without conflict is NOT_ESTABLISHED",
            test_false_without_conflict_is_not_established,
        ),
        (
            "Missing source never means conflict",
            test_missing_source_never_means_conflict,
        ),
        (
            "Conflict diagnostic has precedence",
            test_conflict_diagnostic_has_precedence,
        ),
        (
            "Invalid raw flag blocks",
            test_invalid_raw_flag_blocks,
        ),
        (
            "Missing diagnostics blocks",
            test_missing_diagnostics_blocks,
        ),
        (
            "Invalid diagnostic item blocks",
            test_invalid_diagnostic_item_blocks,
        ),
        (
            "Input is not mutated",
            test_input_not_mutated,
        ),
        (
            "Current real state",
            test_current_real_state,
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