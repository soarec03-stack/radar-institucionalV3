"""
RADAR INSTITUCIONAL V3
V3.4D.2-B.2C.1
TESTE DO CONTRATO DE CORPORATE ACTION RECONCILIATION

Valida a politica:
automation/short_interest_corporate_action_reconciliation_policy_v3.json

Nao acessa rede.
Nao modifica registry.
Nao modifica radar.
Nao modifica Signal, Confidence, Score ou Decision.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.1"

POLICY = Path(
    "automation/"
    "short_interest_corporate_action_reconciliation_policy_v3.json"
)


class TestFailure(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise TestFailure(
            f"Arquivo nao encontrado: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise TestFailure(
            f"JSON invalido: linha {exc.lineno}, coluna {exc.colno}"
        ) from exc

    if not isinstance(value, dict):
        raise TestFailure("Root da policy deve ser objeto JSON.")

    return value


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise TestFailure(message)


def nested(
    obj: dict[str, Any],
    *keys: str,
) -> Any:
    current: Any = obj

    for key in keys:
        require(
            isinstance(current, dict),
            f"Estrutura invalida antes de '{key}'.",
        )

        require(
            key in current,
            f"Campo obrigatorio ausente: {'.'.join(keys)}",
        )

        current = current[key]

    return current


def find_case(
    policy: dict[str, Any],
    case_name: str,
) -> dict[str, Any]:

    matrix = policy.get("decision_matrix")

    require(
        isinstance(matrix, list),
        "decision_matrix deve ser lista.",
    )

    matches = [
        item
        for item in matrix
        if isinstance(item, dict)
        and item.get("case") == case_name
    ]

    require(
        len(matches) == 1,
        (
            f"Case '{case_name}' deve existir exatamente "
            f"uma vez; encontrado: {len(matches)}."
        ),
    )

    return matches[0]


def assert_case(
    policy: dict[str, Any],
    case_name: str,
    reconciliation_status: str,
    adjustment_status: str,
    adjustment_authorized: bool,
    analytically_usable: bool,
) -> None:

    case = find_case(policy, case_name)

    require(
        case.get("reconciliation_status")
        == reconciliation_status,
        (
            f"{case_name}: reconciliation_status esperado "
            f"{reconciliation_status!r}, recebido "
            f"{case.get('reconciliation_status')!r}."
        ),
    )

    require(
        case.get("adjustment_status")
        == adjustment_status,
        (
            f"{case_name}: adjustment_status esperado "
            f"{adjustment_status!r}, recebido "
            f"{case.get('adjustment_status')!r}."
        ),
    )

    require(
        case.get("adjustment_authorized")
        is adjustment_authorized,
        (
            f"{case_name}: adjustment_authorized esperado "
            f"{adjustment_authorized!r}, recebido "
            f"{case.get('adjustment_authorized')!r}."
        ),
    )

    require(
        case.get("analytically_usable")
        is analytically_usable,
        (
            f"{case_name}: analytically_usable esperado "
            f"{analytically_usable!r}, recebido "
            f"{case.get('analytically_usable')!r}."
        ),
    )


def test_1_identity(policy: dict[str, Any]) -> None:
    require(
        policy.get("schema_version") == "3.0",
        "schema_version deve ser 3.0.",
    )

    require(
        policy.get("policy_version") == VERSION,
        (
            f"policy_version deve ser {VERSION}; "
            f"recebido {policy.get('policy_version')!r}."
        ),
    )

    require(
        policy.get("domain")
        == "SHORT_INTEREST_CORPORATE_ACTION_RECONCILIATION",
        "domain incorreto.",
    )


def test_2_fail_closed(policy: dict[str, Any]) -> None:
    require(
        nested(
            policy,
            "principles",
            "fail_closed",
        ) is True,
        "fail_closed deve ser true.",
    )

    require(
        nested(
            policy,
            "principles",
            "absence_of_evidence_is_not_no_action",
        ) is True,
        "Ausencia de evidencia nao pode significar NO_ACTION.",
    )

    require(
        nested(
            policy,
            "principles",
            "verified_action_required_for_adjustment",
        ) is True,
        "Ajuste exige corporate action verificada.",
    )

    require(
        nested(
            policy,
            "principles",
            "prevent_double_adjustment",
        ) is True,
        "Double adjustment deve ser proibido.",
    )


def test_3_no_action(policy: dict[str, Any]) -> None:
    rules = nested(
        policy,
        "no_action_requirements",
        "explicit_rules",
    )

    require(
        rules.get("zero_text_matches_is_sufficient")
        is False,
        "Zero text matches nao pode provar NO_ACTION.",
    )

    require(
        rules.get("zero_qualified_evidence_is_sufficient")
        is False,
        "Zero qualified evidence nao pode provar NO_ACTION.",
    )

    require(
        rules.get("resolver_status_resolved_is_sufficient")
        is False,
        "RESOLVED do Evidence Resolver nao pode provar NO_ACTION.",
    )

    require(
        rules.get("absence_of_sec_match_is_sufficient")
        is False,
        "Ausencia de SEC match nao pode provar NO_ACTION.",
    )

    require(
        rules.get("positive_window_review_required")
        is True,
        "NO_ACTION deve exigir positive window review.",
    )


def test_4_source_adjustment(policy: dict[str, Any]) -> None:
    rules = nested(
        policy,
        "source_adjusted_requirements",
        "rules",
    )

    require(
        rules.get("assume_source_adjusted")
        is False,
        "SOURCE_ADJUSTED nao pode ser presumido.",
    )

    require(
        rules.get(
            "infer_source_adjusted_from_numeric_continuity"
        ) is False,
        (
            "Continuidade numerica nao pode provar "
            "SOURCE_ADJUSTED."
        ),
    )

    require(
        rules.get(
            "infer_source_adjusted_from_finra_cross_check"
        ) is False,
        (
            "FINRA cross-check numerico nao pode provar "
            "SOURCE_ADJUSTED."
        ),
    )

    require(
        rules.get("double_adjustment_prohibited")
        is True,
        "Double adjustment deve permanecer proibido.",
    )


def test_5_adjustment_authorization(
    policy: dict[str, Any],
) -> None:

    adjustment = nested(
        policy,
        "adjustment_policy",
    )

    require(
        adjustment.get("default_adjustment_authorized")
        is False,
        "Ajuste deve ser bloqueado por default.",
    )

    rules = adjustment.get("rules")

    require(
        isinstance(rules, dict),
        "adjustment_policy.rules deve ser objeto.",
    )

    require(
        rules.get("no_action_authorizes_adjustment")
        is False,
        "NO_ACTION nao pode autorizar ajuste.",
    )

    require(
        rules.get(
            "source_adjusted_authorizes_additional_adjustment"
        ) is False,
        "SOURCE_ADJUSTED nao pode autorizar segundo ajuste.",
    )

    require(
        rules.get("unresolved_authorizes_adjustment")
        is False,
        "UNRESOLVED nao pode autorizar ajuste.",
    )

    require(
        rules.get("not_checked_authorizes_adjustment")
        is False,
        "NOT_CHECKED nao pode autorizar ajuste.",
    )


def test_6_identity_continuity(
    policy: dict[str, Any],
) -> None:

    identity = nested(
        policy,
        "identity_continuity",
    )

    require(
        identity.get("required") is True,
        "Identity continuity deve ser obrigatoria.",
    )

    rules = identity.get("rules")

    require(
        isinstance(rules, dict),
        "identity_continuity.rules deve ser objeto.",
    )

    require(
        rules.get("ticker_only_is_sufficient")
        is False,
        "Ticker isolado nao pode provar identidade.",
    )

    require(
        rules.get("cusip_change_requires_reconciliation")
        is True,
        "CUSIP change deve exigir reconciliation.",
    )

    require(
        rules.get(
            "unresolved_identity_change_blocks_analytical_use"
        ) is True,
        (
            "Identity change nao resolvida deve bloquear "
            "uso analitico."
        ),
    )


def test_7_conflict_policy(
    policy: dict[str, Any],
) -> None:

    conflict = nested(
        policy,
        "conflict_policy",
    )

    require(
        conflict.get("authoritative_conflict_status")
        == "UNRESOLVED",
        "Conflito autoritativo deve resultar em UNRESOLVED.",
    )

    rules = conflict.get("rules")

    require(
        isinstance(rules, dict),
        "conflict_policy.rules deve ser objeto.",
    )

    require(
        rules.get("do_not_choose_source_silently")
        is True,
        "Nao pode escolher fonte silenciosamente.",
    )

    require(
        rules.get("do_not_average_conflicting_values")
        is True,
        "Nao pode fazer media de valores conflitantes.",
    )

    require(
        rules.get(
            "do_not_use_supporting_source_to_break_tier_1_conflict"
        ) is True,
        (
            "Fonte de apoio nao pode resolver conflito "
            "entre fontes TIER_1."
        ),
    )


def test_8_decision_matrix(
    policy: dict[str, Any],
) -> None:

    assert_case(
        policy,
        "NO_ACTION_PROVEN",
        "NO_ACTION",
        "NOT_REQUIRED",
        False,
        True,
    )

    assert_case(
        policy,
        "VERIFIED_ACTION_ADJUSTMENT_REQUIRED",
        "VERIFIED_ACTION",
        "REQUIRED",
        True,
        True,
    )

    assert_case(
        policy,
        "VERIFIED_ACTION_SOURCE_ALREADY_ADJUSTED",
        "SOURCE_ADJUSTED",
        "SOURCE_ALREADY_ADJUSTED",
        False,
        True,
    )

    assert_case(
        policy,
        "INSUFFICIENT_EVIDENCE",
        "UNRESOLVED",
        "BLOCKED",
        False,
        False,
    )

    assert_case(
        policy,
        "IDENTITY_CONFLICT",
        "UNRESOLVED",
        "BLOCKED",
        False,
        False,
    )

    assert_case(
        policy,
        "AUTHORITATIVE_EVIDENCE_CONFLICT",
        "UNRESOLVED",
        "BLOCKED",
        False,
        False,
    )


def test_9_downstream_permissions(
    policy: dict[str, Any],
) -> None:

    permissions = nested(
        policy,
        "downstream_permissions",
    )

    forbidden = [
        "collector_may_assign_signal",
        "reconciler_may_assign_signal",
        "reconciler_may_assign_numeric_confidence",
        "reconciler_may_assign_radar_score",
        "reconciler_may_assign_decision",
    ]

    for field in forbidden:
        require(
            permissions.get(field) is False,
            f"{field} deve ser false.",
        )

    release = permissions.get(
        "analytical_metric_release"
    )

    require(
        isinstance(release, dict),
        "analytical_metric_release deve ser objeto.",
    )

    require(
        set(release.get("allowed_statuses", []))
        == {
            "NO_ACTION",
            "SOURCE_ADJUSTED",
            "VERIFIED_ACTION",
        },
        "Allowed statuses para release estao incorretos.",
    )

    require(
        set(release.get("blocked_statuses", []))
        == {
            "NOT_CHECKED",
            "UNRESOLVED",
        },
        "Blocked statuses para release estao incorretos.",
    )


def test_10_test_contract(
    policy: dict[str, Any],
) -> None:

    contract = nested(
        policy,
        "test_contract",
    )

    expected = {
        "NO_ACTION_PROVEN",
        "VERIFIED_ACTION_ADJUSTMENT_REQUIRED",
        "VERIFIED_ACTION_SOURCE_ALREADY_ADJUSTED",
        "UNRESOLVED_INSUFFICIENT_EVIDENCE",
        "UNRESOLVED_IDENTITY_CONFLICT",
        "UNRESOLVED_CONFLICTING_AUTHORITATIVE_EVIDENCE",
    }

    actual = set(
        contract.get("required_scenarios", [])
    )

    require(
        actual == expected,
        (
            "required_scenarios diferente do contrato "
            "homologado."
        ),
    )


def run_test(
    number: int,
    name: str,
    function,
    policy: dict[str, Any],
) -> bool:

    print("-" * 72)
    print(f"TESTE {number}: {name}")

    try:
        function(policy)
        print("RESULTADO: PASS")
        return True

    except TestFailure as exc:
        print("RESULTADO: FAIL")
        print(exc)
        return False


def main() -> int:
    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST CORPORATE ACTION RECONCILIATION")
    print(f"POLICY TEST {VERSION}")
    print("=" * 72)

    try:
        policy = read_json(POLICY)
    except TestFailure as exc:
        print("ERRO:", exc)
        return 2

    tests = [
        (
            1,
            "Policy identity and version",
            test_1_identity,
        ),
        (
            2,
            "Fail-closed principles",
            test_2_fail_closed,
        ),
        (
            3,
            "NO_ACTION positive evidence requirements",
            test_3_no_action,
        ),
        (
            4,
            "SOURCE_ADJUSTED safeguards",
            test_4_source_adjustment,
        ),
        (
            5,
            "Adjustment authorization",
            test_5_adjustment_authorization,
        ),
        (
            6,
            "Identity continuity",
            test_6_identity_continuity,
        ),
        (
            7,
            "Authoritative evidence conflicts",
            test_7_conflict_policy,
        ),
        (
            8,
            "Decision matrix",
            test_8_decision_matrix,
        ),
        (
            9,
            "Downstream permissions",
            test_9_downstream_permissions,
        ),
        (
            10,
            "Required controlled scenarios",
            test_10_test_contract,
        ),
    ]

    passed = 0
    failed = 0

    for number, name, function in tests:
        if run_test(
            number,
            name,
            function,
            policy,
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