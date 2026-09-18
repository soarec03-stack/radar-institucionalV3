from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


VERSION = "3.4D.2-B.2C.8F.1"

BASE_DIR = Path(__file__).resolve().parent.parent

POLICY_FILE = (
    BASE_DIR
    / "automation"
    / "short_interest_quality_policy_v3.json"
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
            "Policy root deve ser objeto."
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


def test_policy_identity() -> None:
    policy = read_json(POLICY_FILE)

    assert_equal(
        policy.get("policy_version"),
        VERSION,
        "policy_version invalida",
    )

    assert_equal(
        policy.get("policy_name"),
        "SHORT_INTEREST_QUALITY_GATE",
        "policy_name invalido",
    )


def test_fail_closed_principles() -> None:
    policy = read_json(POLICY_FILE)
    principles = policy["principles"]

    required_true = [
        "policy_before_code",
        "fail_closed_on_blocking_control",
        "missing_is_not_neutral",
        "missing_is_not_zero",
        "do_not_invent_data",
        "data_availability_is_not_quality",
        "upstream_blocked_cannot_be_upgraded",
        "upstream_unavailable_cannot_be_upgraded",
    ]

    for name in required_true:
        assert_true(
            principles.get(name),
            f"Principio obrigatorio ausente: {name}",
        )


def test_no_analytical_side_effects() -> None:
    policy = read_json(POLICY_FILE)
    principles = policy["principles"]

    required_true = [
        "quality_gate_does_not_reconcile",
        "quality_gate_does_not_collect",
        "quality_gate_does_not_assign_numeric_confidence",
        "quality_gate_does_not_generate_signal",
        "quality_gate_does_not_generate_score",
        "quality_gate_does_not_generate_decision",
    ]

    for name in required_true:
        assert_true(
            principles.get(name),
            f"Boundary analitico ausente: {name}",
        )


def test_metric_contract() -> None:
    policy = read_json(POLICY_FILE)
    metric = policy["metric"]

    assert_equal(
        metric.get("name"),
        "short_interest_change_pct",
        "Metrica invalida",
    )

    assert_equal(
        metric.get("source"),
        "FINRA",
        "Fonte invalida",
    )

    assert_equal(
        metric.get("required_source_tier"),
        "TIER_1",
        "Tier obrigatorio invalido",
    )

    assert_true(
        metric.get("raw_metric_preserved"),
        "Raw metric deve ser preservada",
    )

    assert_true(
        metric.get("previous_snapshot_preserved"),
        "Previous snapshot deve ser preservado",
    )

    assert_true(
        metric.get("current_snapshot_preserved"),
        "Current snapshot deve ser preservado",
    )


def test_blocking_controls() -> None:
    policy = read_json(POLICY_FILE)
    blocking = policy["blocking_controls"]

    required = [
        "require_boundary_reconciled",
        "require_reconciler_invoked",
        "require_reconciler_analytically_usable",
        "require_verified_identity_continuity",
        "require_exact_settlement_window",
        "require_two_distinct_settlement_dates",
        "require_positive_previous_short_interest",
        "require_nonnegative_current_short_interest",
        "require_tier_1_short_interest_provenance",
        "require_corporate_action_reconciliation_resolved",
        "require_adjustment_integrity",
        "require_raw_values_preserved",
        "require_metric_available",
    ]

    for name in required:
        assert_true(
            blocking.get(name),
            f"Blocking control ausente: {name}",
        )


def test_reconciliation_status_contract() -> None:
    policy = read_json(POLICY_FILE)

    allowed = set(
        policy["allowed_reconciliation_statuses"]
    )

    deferred = set(
        policy[
            "deferred_reconciliation_statuses"
        ]
    )

    blocked = set(
        policy["blocked_reconciliation_statuses"]
    )

    assert_equal(
        allowed,
        {
            "NO_ACTION",
            "VERIFIED_ACTION",
        },
        "Allowed reconciliation statuses invalidos",
    )

    assert_equal(
        deferred,
        {
            "SOURCE_ADJUSTED",
        },
        "Deferred reconciliation statuses invalidos",
    )

    assert_equal(
        blocked,
        {
            "NOT_CHECKED",
            "UNRESOLVED",
        },
        "Blocked reconciliation statuses invalidos",
    )

    assert_true(
        allowed.isdisjoint(blocked),
        "Allowed e blocked statuses devem ser disjuntos",
    )

    assert_true(
        allowed.isdisjoint(deferred),
        "Allowed e deferred statuses devem ser disjuntos",
    )

    assert_true(
        deferred.isdisjoint(blocked),
        "Deferred e blocked statuses devem ser disjuntos",
    )

def test_quality_statuses() -> None:
    policy = read_json(POLICY_FILE)
    statuses = policy["quality_statuses"]

    assert_equal(
        set(statuses),
        {
            "VERIFIED",
            "BLOCKED",
            "UNAVAILABLE",
        },
        "Quality statuses invalidos",
    )

    assert_true(
        statuses["VERIFIED"].get(
            "analytically_usable"
        ),
        "VERIFIED deve ser utilizavel",
    )

    assert_equal(
        statuses["BLOCKED"].get(
            "analytically_usable"
        ),
        False,
        "BLOCKED nao pode ser utilizavel",
    )

    assert_equal(
        statuses["UNAVAILABLE"].get(
            "analytically_usable"
        ),
        False,
        "UNAVAILABLE nao pode ser utilizavel",
    )


def test_status_precedence() -> None:
    policy = read_json(POLICY_FILE)

    assert_equal(
        policy.get("status_precedence"),
        [
            "UNAVAILABLE",
            "BLOCKED",
            "VERIFIED",
        ],
        "Precedencia de status invalida",
    )


def test_invariants() -> None:
    policy = read_json(POLICY_FILE)
    invariants = policy["invariants"]

    for name, value in invariants.items():
        assert_true(
            value,
            f"Invariante deve ser true: {name}",
        )


def test_downstream_boundary() -> None:
    policy = read_json(POLICY_FILE)
    downstream = policy["downstream_boundary"]

    assert_true(
        downstream.get(
            "verified_may_proceed_to_institutional_flow"
        ),
        "VERIFIED deve poder seguir downstream",
    )

    assert_equal(
        downstream.get(
            "blocked_may_proceed_to_institutional_flow"
        ),
        False,
        "BLOCKED nao pode seguir downstream",
    )

    assert_equal(
        downstream.get(
            "unavailable_may_proceed_to_institutional_flow"
        ),
        False,
        "UNAVAILABLE nao pode seguir downstream",
    )

    for name in [
        "quality_status_is_not_confidence",
        "quality_status_is_not_signal",
        "quality_status_is_not_score",
        "quality_status_is_not_decision",
    ]:
        assert_true(
            downstream.get(name),
            f"Separacao semantica ausente: {name}",
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
    print("QUALITY GATE POLICY")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    tests = [
        (
            "Policy identity",
            test_policy_identity,
        ),
        (
            "Fail closed principles",
            test_fail_closed_principles,
        ),
        (
            "No analytical side effects",
            test_no_analytical_side_effects,
        ),
        (
            "Metric contract",
            test_metric_contract,
        ),
        (
            "Blocking controls",
            test_blocking_controls,
        ),
        (
            "Reconciliation status contract",
            test_reconciliation_status_contract,
        ),
        (
            "Quality statuses",
            test_quality_statuses,
        ),
        (
            "Status precedence",
            test_status_precedence,
        ),
        (
            "Invariants",
            test_invariants,
        ),
        (
            "Downstream boundary",
            test_downstream_boundary,
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