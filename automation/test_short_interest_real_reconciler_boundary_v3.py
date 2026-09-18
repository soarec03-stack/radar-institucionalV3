from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch


VERSION = "3.4D.2-B.2C.8E.2"

BASE_DIR = Path(__file__).resolve().parent.parent
AUTOMATION_DIR = BASE_DIR / "automation"

if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))


import short_interest_real_reconciler_boundary_v3 as boundary  # noqa: E402


ADAPTER_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_real_integration_adapter_v3.json"
)

REVIEW_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_real_positive_official_review_v3.json"
)

BOUNDARY_POLICY_FILE = (
    AUTOMATION_DIR
    / "short_interest_real_reconciler_boundary_policy_v3.json"
)

SEMANTICS_POLICY_FILE = (
    AUTOMATION_DIR
    / "short_interest_authoritative_conflict_semantics_policy_v3.json"
)

RECONCILIATION_POLICY_FILE = (
    AUTOMATION_DIR
    / "short_interest_corporate_action_reconciliation_policy_v3.json"
)


class TestFailure(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        value = json.load(file)

    if not isinstance(value, dict):
        raise TestFailure(
            f"{path}: root deve ser objeto."
        )

    return value


def load_inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    return (
        read_json(ADAPTER_FILE),
        read_json(REVIEW_FILE),
        read_json(BOUNDARY_POLICY_FILE),
        read_json(SEMANTICS_POLICY_FILE),
        read_json(RECONCILIATION_POLICY_FILE),
    )


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


def assert_true(
    value: Any,
    message: str,
) -> None:
    if value is not True:
        raise TestFailure(message)


def find_asset(
    document: dict[str, Any],
    ticker: str,
) -> dict[str, Any]:
    assets = document.get("assets")

    if not isinstance(assets, list):
        raise TestFailure(
            "assets deve ser lista."
        )

    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and asset.get("ticker") == ticker
    ]

    if len(matches) != 1:
        raise TestFailure(
            f"{ticker}: esperado exatamente um asset."
        )

    return matches[0]


def run_with_counter(
    adapter_document: dict[str, Any],
    review_document: dict[str, Any],
    boundary_policy: dict[str, Any],
    semantics_policy: dict[str, Any],
    reconciliation_policy: dict[str, Any],
) -> tuple[dict[str, Any], int]:

    calls = 0

    def fake_reconcile_case(
        case: dict[str, Any],
        common: dict[str, Any],
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1

        return {
            "case": case.get("case"),
            "corporate_action_status": "NO_ACTION",
            "reconciliation_status": "NO_ACTION",
            "identity_continuity_status": "VERIFIED",
            "source_adjustment_status": "NOT_APPLICABLE",
            "adjustment_status": "NOT_REQUIRED",
            "adjustment_authorized": False,
            "adjustment_factor": None,
            "analytically_usable": True,
            "reason":
                "SYNTHETIC_BOUNDARY_TEST_RECONCILED",
            "evidence_summary": {},
            "diagnostics": [],
        }

    with patch.object(
        boundary,
        "reconcile_case",
        side_effect=fake_reconcile_case,
    ):
        output = boundary.run_boundary(
            adapter_document,
            review_document,
            boundary_policy,
            semantics_policy,
            reconciliation_policy,
        )

    return output, calls


def make_single_asset_documents(
    ticker: str = "CRSP",
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    (
        adapter_document,
        review_document,
        boundary_policy,
        semantics_policy,
        reconciliation_policy,
    ) = load_inputs()

    adapter_asset = deepcopy(
        find_asset(
            adapter_document,
            ticker,
        )
    )

    review_asset = deepcopy(
        find_asset(
            review_document,
            ticker,
        )
    )

    adapter_document = {
        **deepcopy(adapter_document),
        "assets": [adapter_asset],
    }

    review_document = {
        **deepcopy(review_document),
        "assets": [review_asset],
    }

    return (
        adapter_document,
        review_document,
        deepcopy(boundary_policy),
        deepcopy(semantics_policy),
        deepcopy(reconciliation_policy),
    )


def authorize_synthetic_no_action_path(
    adapter_asset: dict[str, Any],
    review_asset: dict[str, Any],
) -> None:

    adapter_result = adapter_asset[
        "adapter_result"
    ]

    adapter_result[
        "integration_status"
    ] = "READY_FOR_RECONCILIATION"

    adapter_result[
        "route"
    ] = "RECONCILER"

    adapter_result[
        "reconciler_input_status"
    ] = "READY"

    adapter_asset[
        "reconciler_invoked"
    ] = False

    review_result = review_asset[
        "review_result"
    ]

    review_result[
        "no_authoritative_evidence_conflict"
    ] = True

    review_result[
        "diagnostics"
    ] = []

    review_result[
        "review_status"
    ] = "NO_ACTION_PROVEN"

    review_result[
        "corporate_action_status"
    ] = "NO_ACTION"

    review_result[
        "reconciliation_eligible"
    ] = True

    review_result[
        "official_window_review_completed"
    ] = True

    review_result[
        "authoritative_source_review_present"
    ] = True

    review_result[
        "economic_window_reviewed"
    ] = True

    review_result[
        "minimum_authoritative_reviews_satisfied"
    ] = True

    adapter_case = adapter_asset[
        "adapter_case"
    ]

    adapter_case["review"] = deepcopy(
        review_result
    )

    adapter_result[
        "action_evidence"
    ] = {
        "resolver_status": "RESOLVED",
        "settlement_window_matches_collection": True,
        "authoritative_conflict": False,
        "qualified_actions": [],
        "unresolved_action_candidates": [],
        "official_window_review_completed": True,
        "authoritative_source_review_present": True,
    }

    adapter_result[
        "source_adjustment"
    ] = {
        "status": "NOT_APPLICABLE"
    }


def test_real_state_zero_invocations() -> None:
    (
        adapter_document,
        review_document,
        boundary_policy,
        semantics_policy,
        reconciliation_policy,
    ) = load_inputs()

    output, calls = run_with_counter(
        deepcopy(adapter_document),
        deepcopy(review_document),
        boundary_policy,
        semantics_policy,
        reconciliation_policy,
    )

    assert_equal(
        calls,
        0,
        "Estado real não pode chamar Reconciler",
    )

    assert_equal(
        output["summary"]["reconciler_invocations"],
        0,
        "Summary deve registrar zero invocações",
    )

    assert_equal(
        output["summary"]["blocked"],
        3,
        "Estado real deve manter três bloqueados",
    )


def test_not_established_never_invokes() -> None:
    data = make_single_asset_documents()

    output, calls = run_with_counter(*data)

    assert_equal(
        calls,
        0,
        "NOT_ESTABLISHED chamou Reconciler",
    )

    assert_equal(
        output["assets"][0]["boundary_status"],
        "BLOCKED",
        "NOT_ESTABLISHED deve bloquear",
    )


def test_conflict_detected_never_invokes() -> None:
    data = list(
        make_single_asset_documents()
    )

    review_asset = data[1]["assets"][0]

    review_asset[
        "review_result"
    ][
        "diagnostics"
    ] = [
        "AUTHORITATIVE_EVIDENCE_CONFLICT"
    ]

    review_asset[
        "review_result"
    ][
        "no_authoritative_evidence_conflict"
    ] = False

    output, calls = run_with_counter(*data)

    assert_equal(
        calls,
        0,
        "CONFLICT_DETECTED chamou Reconciler",
    )

    semantic = output["assets"][0][
        "authoritative_conflict_semantics"
    ]

    assert_equal(
        semantic["status"],
        "CONFLICT_DETECTED",
        "Semântica deveria detectar conflito",
    )


def test_adapter_blocked_never_invokes() -> None:
    data = list(
        make_single_asset_documents()
    )

    adapter_asset = data[0]["assets"][0]
    review_asset = data[1]["assets"][0]

    authorize_synthetic_no_action_path(
        adapter_asset,
        review_asset,
    )

    adapter_asset[
        "adapter_result"
    ][
        "integration_status"
    ] = "BLOCKED"

    output, calls = run_with_counter(*data)

    assert_equal(
        calls,
        0,
        "Adapter BLOCKED chamou Reconciler",
    )

    assert_equal(
        output["assets"][0]["boundary_status"],
        "BLOCKED",
        "Adapter BLOCKED deve permanecer bloqueado",
    )


def test_route_none_never_invokes() -> None:
    data = list(
        make_single_asset_documents()
    )

    adapter_asset = data[0]["assets"][0]
    review_asset = data[1]["assets"][0]

    authorize_synthetic_no_action_path(
        adapter_asset,
        review_asset,
    )

    adapter_asset[
        "adapter_result"
    ][
        "route"
    ] = "NONE"

    output, calls = run_with_counter(*data)

    assert_equal(
        calls,
        0,
        "Route NONE chamou Reconciler",
    )


def test_unresolved_input_never_invokes() -> None:
    data = list(
        make_single_asset_documents()
    )

    adapter_asset = data[0]["assets"][0]
    review_asset = data[1]["assets"][0]

    authorize_synthetic_no_action_path(
        adapter_asset,
        review_asset,
    )

    adapter_asset[
        "adapter_result"
    ][
        "reconciler_input_status"
    ] = "UNRESOLVED"

    output, calls = run_with_counter(*data)

    assert_equal(
        calls,
        0,
        "UNRESOLVED input chamou Reconciler",
    )


def test_identity_mismatch_never_invokes() -> None:
    data = list(
        make_single_asset_documents()
    )

    adapter_asset = data[0]["assets"][0]
    review_asset = data[1]["assets"][0]

    authorize_synthetic_no_action_path(
        adapter_asset,
        review_asset,
    )

    review_asset[
        "review_case"
    ][
        "identity"
    ][
        "security_identity"
    ] = "CUSIP:SYNTHETIC_MISMATCH"

    output, calls = run_with_counter(*data)

    assert_equal(
        calls,
        0,
        "Identity mismatch chamou Reconciler",
    )

    diagnostics = output["assets"][0][
        "diagnostics"
    ]

    assert_true(
        "BOUNDARY_IDENTITY_MISMATCH"
        in diagnostics,
        "Boundary não detectou identity mismatch",
    )


def test_window_mismatch_never_invokes() -> None:
    data = list(
        make_single_asset_documents()
    )

    adapter_asset = data[0]["assets"][0]
    review_asset = data[1]["assets"][0]

    authorize_synthetic_no_action_path(
        adapter_asset,
        review_asset,
    )

    review_asset[
        "review_case"
    ][
        "current_settlement_date"
    ] = "2026-09-01"

    output, calls = run_with_counter(*data)

    assert_equal(
        calls,
        0,
        "Window mismatch chamou Reconciler",
    )

    diagnostics = output["assets"][0][
        "diagnostics"
    ]

    assert_true(
        "BOUNDARY_SETTLEMENT_WINDOW_MISMATCH"
        in diagnostics,
        "Boundary não detectou window mismatch",
    )


def test_authorized_path_exactly_one_invocation() -> None:
    data = list(
        make_single_asset_documents()
    )

    adapter_asset = data[0]["assets"][0]
    review_asset = data[1]["assets"][0]

    authorize_synthetic_no_action_path(
        adapter_asset,
        review_asset,
    )

    output, calls = run_with_counter(*data)

    assert_equal(
        calls,
        1,
        "Caminho autorizado deve chamar exatamente uma vez",
    )

    asset = output["assets"][0]

    assert_equal(
        asset["boundary_status"],
        "RECONCILED",
        "Caminho autorizado deve reconciliar",
    )

    assert_true(
        asset["reconciler_invoked"],
        "reconciler_invoked deveria ser true",
    )

    assert_true(
        asset["analytically_usable"],
        "Resultado sintético deveria ser utilizável",
    )

    assert_equal(
        output["summary"]["reconciler_invocations"],
        1,
        "Summary deve registrar uma invocação",
    )


def test_inputs_not_mutated() -> None:
    data = list(
        make_single_asset_documents()
    )

    adapter_before = deepcopy(data[0])
    review_before = deepcopy(data[1])

    run_with_counter(*data)

    assert_equal(
        data[0],
        adapter_before,
        "Boundary alterou Adapter input",
    )

    assert_equal(
        data[1],
        review_before,
        "Boundary alterou Review input",
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
    print("REAL RECONCILER BOUNDARY REGRESSION")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    tests = [
        (
            "Real state zero invocations",
            test_real_state_zero_invocations,
        ),
        (
            "NOT_ESTABLISHED never invokes",
            test_not_established_never_invokes,
        ),
        (
            "CONFLICT_DETECTED never invokes",
            test_conflict_detected_never_invokes,
        ),
        (
            "Adapter BLOCKED never invokes",
            test_adapter_blocked_never_invokes,
        ),
        (
            "Route NONE never invokes",
            test_route_none_never_invokes,
        ),
        (
            "UNRESOLVED input never invokes",
            test_unresolved_input_never_invokes,
        ),
        (
            "Identity mismatch never invokes",
            test_identity_mismatch_never_invokes,
        ),
        (
            "Window mismatch never invokes",
            test_window_mismatch_never_invokes,
        ),
        (
            "Authorized path exactly one invocation",
            test_authorized_path_exactly_one_invocation,
        ),
        (
            "Inputs not mutated",
            test_inputs_not_mutated,
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
        print("RESULTADO FINAL: APROVADO")
        return 0

    print("RESULTADO FINAL: REPROVADO")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())