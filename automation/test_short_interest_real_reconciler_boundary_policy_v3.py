from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable


VERSION = "3.4D.2-B.2C.8E"

BASE_DIR = Path(__file__).resolve().parent.parent

POLICY_FILE = (
    BASE_DIR
    / "automation"
    / "short_interest_real_reconciler_boundary_policy_v3.json"
)


class TestFailure(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            value = json.load(f)
    except Exception as exc:
        raise TestFailure(
            f"Falha lendo policy: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise TestFailure(
            "Policy root deve ser objeto."
        )

    return value


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


def test_version() -> None:
    policy = read_json(POLICY_FILE)

    assert_equal(
        policy.get("policy_version"),
        VERSION,
        "policy_version incorreta",
    )


def test_fail_closed() -> None:
    policy = read_json(POLICY_FILE)

    assert_true(
        policy["principles"]["fail_closed"],
        "Boundary deve ser fail closed",
    )


def test_blocked_never_invokes() -> None:
    policy = read_json(POLICY_FILE)

    assert_true(
        policy["principles"][
            "blocked_never_invokes_reconciler"
        ],
        "BLOCKED nunca pode chamar Reconciler",
    )


def test_required_adapter_state() -> None:
    policy = read_json(POLICY_FILE)

    expected = {
        "integration_status":
            "READY_FOR_RECONCILIATION",
        "route":
            "RECONCILER",
        "reconciler_input_status":
            "READY",
        "reconciler_invoked_before_boundary":
            False,
    }

    assert_equal(
        policy.get(
            "required_adapter_state_for_invocation"
        ),
        expected,
        "Estado obrigatório do Adapter incorreto",
    )


def test_semantic_allowlist() -> None:
    policy = read_json(POLICY_FILE)

    assert_equal(
        policy.get(
            "allowed_semantic_status_for_invocation"
        ),
        ["VERIFIED_NO_CONFLICT"],
        "Allowlist semântica incorreta",
    )


def test_semantic_blocklist() -> None:
    policy = read_json(POLICY_FILE)

    assert_equal(
        set(
            policy.get(
                "blocking_semantic_statuses",
                [],
            )
        ),
        {
            "NOT_ESTABLISHED",
            "CONFLICT_DETECTED",
        },
        "Blocklist semântica incorreta",
    )


def test_verified_no_conflict_not_sufficient() -> None:
    policy = read_json(POLICY_FILE)

    assert_true(
        policy["principles"][
            "verified_no_conflict_does_not_authorize_alone"
        ],
        "VERIFIED_NO_CONFLICT não pode autorizar sozinho",
    )


def test_identity_and_window_exact() -> None:
    policy = read_json(POLICY_FILE)

    assert_true(
        policy["principles"][
            "identity_must_match_exactly"
        ],
        "Identity deve ser exata",
    )

    assert_true(
        policy["principles"][
            "settlement_window_must_match_exactly"
        ],
        "Settlement window deve ser exata",
    )


def test_no_analytical_side_effects() -> None:
    policy = read_json(POLICY_FILE)

    principles = policy["principles"]

    fields = [
        "no_signal_generation",
        "no_confidence_generation",
        "no_score_generation",
        "no_decision_generation",
        "no_radar_mutation",
    ]

    for field in fields:
        assert_true(
            principles.get(field),
            f"{field} deve ser true",
        )


def test_invariants() -> None:
    policy = read_json(POLICY_FILE)

    invariants = set(
        policy.get("invariants", [])
    )

    required = {
        "ADAPTER_BLOCKED_NEVER_REACHES_RECONCILER",
        "ROUTE_NONE_NEVER_REACHES_RECONCILER",
        "UNRESOLVED_RECONCILER_INPUT_NEVER_REACHES_RECONCILER",
        "NOT_ESTABLISHED_NEVER_REACHES_RECONCILER",
        "CONFLICT_DETECTED_NEVER_REACHES_RECONCILER",
        "VERIFIED_NO_CONFLICT_ALONE_NEVER_AUTHORIZES_RECONCILIATION",
        "RECONCILER_INVOCATION_REQUIRES_ALL_BOUNDARY_CONDITIONS",
        "RAW_ADAPTER_RESULT_MUST_BE_PRESERVED",
        "RAW_REVIEW_RESULT_MUST_BE_PRESERVED",
        "BLOCKED_RESULT_MUST_REMAIN_ANALYTICALLY_UNUSABLE",
    }

    missing = required - invariants

    if missing:
        raise TestFailure(
            "Invariants ausentes: "
            + ", ".join(sorted(missing))
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
    print("REAL RECONCILER BOUNDARY POLICY")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    tests = [
        ("Policy version", test_version),
        ("Fail closed", test_fail_closed),
        (
            "Blocked never invokes",
            test_blocked_never_invokes,
        ),
        (
            "Required Adapter state",
            test_required_adapter_state,
        ),
        (
            "Semantic allowlist",
            test_semantic_allowlist,
        ),
        (
            "Semantic blocklist",
            test_semantic_blocklist,
        ),
        (
            "Verified no conflict not sufficient",
            test_verified_no_conflict_not_sufficient,
        ),
        (
            "Identity and window exact",
            test_identity_and_window_exact,
        ),
        (
            "No analytical side effects",
            test_no_analytical_side_effects,
        ),
        (
            "Required invariants",
            test_invariants,
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