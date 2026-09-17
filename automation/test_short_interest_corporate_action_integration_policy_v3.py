"""
RADAR INSTITUCIONAL V3

SHORT INTEREST
CORPORATE ACTION INTEGRATION POLICY TEST

Version:
3.4D.2-B.2C.7C.1

Valida exclusivamente o contrato de integracao entre:

Positive Official Window Review
        ->
Integration Adapter
        ->
Corporate Action Reconciler

Nao acessa rede.
Nao modifica dados.
Nao calcula Signal.
Nao calcula Confidence.
Nao calcula Radar Score.
Nao gera Decision.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable


VERSION = "3.4D.2-B.2C.7C.1"

BASE_DIR = Path(__file__).resolve().parent.parent

POLICY_FILE = (
    BASE_DIR
    / "automation"
    / "short_interest_corporate_action_integration_policy_v3.json"
)


class TestFailure(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise TestFailure(
            "Policy root deve ser objeto JSON."
        )

    return data


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise TestFailure(message)


def test_identity_and_version(
    policy: dict[str, Any],
) -> None:

    require(
        policy.get("policy_id")
        == (
            "RADAR_INSTITUCIONAL_V3_SHORT_INTEREST_"
            "CORPORATE_ACTION_INTEGRATION"
        ),
        "policy_id incorreto.",
    )

    require(
        policy.get("version") == VERSION,
        "version incorreta.",
    )

    require(
        policy.get("status") == "ACTIVE",
        "Policy deve estar ACTIVE.",
    )


def test_architecture(
    policy: dict[str, Any],
) -> None:

    architecture = policy["architecture"]

    require(
        architecture.get("upstream_component")
        == "POSITIVE_OFFICIAL_WINDOW_REVIEW",
        "Upstream incorreto.",
    )

    require(
        architecture.get("integration_component")
        == "CORPORATE_ACTION_INTEGRATION_ADAPTER",
        "Integration component incorreto.",
    )

    require(
        architecture.get("downstream_component")
        == "CORPORATE_ACTION_RECONCILER",
        "Downstream incorreto.",
    )

    expected_flow = [
        "POSITIVE_OFFICIAL_WINDOW_REVIEW",
        "CORPORATE_ACTION_INTEGRATION_ADAPTER",
        "CORPORATE_ACTION_RECONCILER",
    ]

    require(
        architecture.get("flow") == expected_flow,
        "Fluxo de integracao incorreto.",
    )


def test_fail_closed_principles(
    policy: dict[str, Any],
) -> None:

    principles = policy["principles"]

    required_true = [
        "fail_closed",
        "adapter_must_not_invent_evidence",
        "adapter_must_not_infer_action_parameters",
        "adapter_must_not_infer_source_adjustment",
        "adapter_must_not_override_authoritative_conflict",
        "adapter_must_preserve_raw_evidence",
        "adapter_must_preserve_identity",
        "adapter_must_preserve_settlement_window",
        "ticker_only_identity_prohibited",
        "missing_is_not_zero",
        "missing_is_not_neutral",
        "review_analytically_usable_is_not_final_short_interest_usable",
        "final_analytical_usability_belongs_to_reconciler",
        "no_direct_write_to_radar",
    ]

    for field in required_true:
        require(
            principles.get(field) is True,
            f"Principio obrigatorio ausente/falso: {field}",
        )


def test_versions(
    policy: dict[str, Any],
) -> None:

    versions = policy[
        "accepted_upstream_versions"
    ]

    require(
        "3.4D.2-B.2C.7A"
        in versions[
            "positive_official_window_review_policy"
        ],
        "Review policy version ausente.",
    )

    require(
        "3.4D.2-B.2C.7B"
        in versions[
            "positive_official_window_review_engine"
        ],
        "Review engine version ausente.",
    )

    require(
        "3.4D.2-B.2C.1"
        in versions[
            "corporate_action_reconciliation_policy"
        ],
        "Reconciliation policy version ausente.",
    )

    require(
        "3.4D.2-B.2C.5"
        in versions[
            "corporate_action_reconciler"
        ],
        "Reconciler version ausente.",
    )


def test_identity_and_window_contract(
    policy: dict[str, Any],
) -> None:

    identity = policy["identity_contract"]

    require(
        identity.get("required") is True,
        "Identity deve ser obrigatoria.",
    )

    require(
        identity.get("ticker_only_prohibited")
        is True,
        "Ticker-only deve ser proibido.",
    )

    required_identity = set(
        identity.get("required_fields", [])
    )

    for field in (
        "ticker",
        "listing_exchange",
        "security_identity",
    ):
        require(
            field in required_identity,
            f"Identity field ausente: {field}",
        )

    require(
        identity.get(
            "required_continuity_status"
        )
        == "VERIFIED",
        "Identity continuity deve exigir VERIFIED.",
    )

    window = policy[
        "settlement_window_contract"
    ]

    require(
        window.get("basis")
        == "SETTLEMENT_DATE",
        "Window deve usar SETTLEMENT_DATE.",
    )

    require(
        window.get("previous_boundary")
        == "EXCLUSIVE",
        "Previous boundary incorreto.",
    )

    require(
        window.get("current_boundary")
        == "INCLUSIVE",
        "Current boundary incorreto.",
    )

    require(
        window.get(
            "adapter_must_not_change_window"
        )
        is True,
        "Adapter nao pode alterar window.",
    )

    require(
        window.get(
            "review_and_reconciliation_windows_must_match"
        )
        is True,
        "Review/reconciliation windows devem coincidir.",
    )


def test_review_routes(
    policy: dict[str, Any],
) -> None:

    contract = policy[
        "review_status_contract"
    ]

    allowed = set(
        contract["allowed_statuses"]
    )

    require(
        allowed
        == {
            "NO_ACTION_PROVEN",
            "ACTION_FOUND",
            "UNRESOLVED",
        },
        "Review statuses incorretos.",
    )

    no_action = contract[
        "NO_ACTION_PROVEN"
    ]

    require(
        no_action["adapter_output"][
            "integration_status"
        ]
        == "READY_FOR_RECONCILIATION",
        "NO_ACTION_PROVEN deve ficar READY.",
    )

    require(
        no_action["adapter_output"]["route"]
        == "NO_ACTION",
        "NO_ACTION_PROVEN route incorreta.",
    )

    require(
        no_action.get(
            "action_evidence_required"
        )
        is False,
        "NO_ACTION nao deve exigir action evidence.",
    )

    action = contract["ACTION_FOUND"]

    require(
        action.get(
            "action_evidence_required"
        )
        is True,
        "ACTION_FOUND deve exigir action evidence.",
    )

    require(
        action[
            "adapter_output_when_incomplete"
        ][
            "integration_status"
        ]
        == "BLOCKED",
        "ACTION_FOUND incompleto deve bloquear.",
    )

    unresolved = contract["UNRESOLVED"]

    require(
        unresolved[
            "adapter_output"
        ][
            "integration_status"
        ]
        == "BLOCKED",
        "UNRESOLVED deve bloquear.",
    )

    require(
        unresolved.get(
            "may_enter_reconciler"
        )
        is False,
        "UNRESOLVED nao pode entrar no reconciler.",
    )


def test_action_evidence(
    policy: dict[str, Any],
) -> None:

    contract = policy[
        "action_evidence_contract"
    ]

    require(
        contract.get(
            "required_for_review_status"
        )
        == "ACTION_FOUND",
        "Action evidence deve ser exigida para ACTION_FOUND.",
    )

    required = set(
        contract.get("required_fields", [])
    )

    for field in (
        "action_type",
        "effective_date",
        "source_id",
        "source_type",
        "source_tier",
        "identity_status",
        "evidence_status",
    ):
        require(
            field in required,
            f"Action evidence field ausente: {field}",
        )

    require(
        contract.get(
            "required_source_tier"
        )
        == "TIER_1",
        "Action evidence deve exigir TIER_1.",
    )

    require(
        contract.get(
            "required_identity_status"
        )
        == "VERIFIED",
        "Action identity deve ser VERIFIED.",
    )

    require(
        contract.get(
            "required_evidence_status"
        )
        == "VERIFIED",
        "Action evidence deve ser VERIFIED.",
    )

    ratio_required = set(
        contract.get(
            "ratio_required_for",
            [],
        )
    )

    require(
        {
            "STOCK_SPLIT",
            "REVERSE_STOCK_SPLIT",
        }.issubset(ratio_required),
        "Split/reverse split devem exigir ratio.",
    )

    ratio_rules = contract[
        "ratio_rules"
    ]

    require(
        ratio_rules.get(
            "adapter_must_not_infer_missing_ratio"
        )
        is True,
        "Adapter nao pode inferir ratio.",
    )


def test_source_adjustment(
    policy: dict[str, Any],
) -> None:

    contract = policy[
        "source_adjustment_contract"
    ]

    source_adjusted = contract[
        "SOURCE_ALREADY_ADJUSTED"
    ]

    require(
        source_adjusted.get(
            "requires_positive_official_statement"
        )
        is True,
        "SOURCE_ALREADY_ADJUSTED exige statement positivo.",
    )

    require(
        source_adjusted.get(
            "required_source_tier"
        )
        == "TIER_1",
        "Source adjustment deve exigir TIER_1.",
    )

    require(
        source_adjusted.get(
            "adapter_must_not_infer_from_numbers"
        )
        is True,
        "Nao pode inferir source adjustment de numeros.",
    )

    require(
        source_adjusted.get(
            "adapter_must_not_apply_second_adjustment"
        )
        is True,
        "Double adjustment deve ser proibido.",
    )

    require(
        contract["UNRESOLVED"][
            "integration_status"
        ]
        == "BLOCKED",
        "Source adjustment UNRESOLVED deve bloquear.",
    )


def test_usability_and_permissions(
    policy: dict[str, Any],
) -> None:

    usability = policy[
        "analytical_usability_contract"
    ]

    require(
        usability.get(
            "upstream_review_analytically_usable_is_advisory_only"
        )
        is True,
        "Review usability deve ser advisory only.",
    )

    require(
        usability.get(
            "adapter_cannot_set_final_short_interest_analytically_usable_true"
        )
        is True,
        "Adapter nao pode liberar usability final.",
    )

    require(
        usability.get("final_authority")
        == "CORPORATE_ACTION_RECONCILER",
        "Autoridade final deve ser Reconciler.",
    )

    permissions = policy[
        "downstream_permissions"
    ]

    ready = permissions[
        "READY_FOR_RECONCILIATION"
    ]

    require(
        ready.get("may_enter_reconciler")
        is True,
        "READY deve poder entrar no reconciler.",
    )

    for field in (
        "may_write_final_short_interest_metric",
        "may_write_signal",
        "may_write_confidence",
        "may_write_radar_score",
        "may_write_decision",
    ):
        require(
            ready.get(field) is False,
            f"READY nao pode liberar {field}.",
        )

    blocked = permissions["BLOCKED"]

    require(
        blocked.get("may_enter_reconciler")
        is False,
        "BLOCKED nao pode entrar no reconciler.",
    )


def test_scenarios_and_prohibitions(
    policy: dict[str, Any],
) -> None:

    scenarios = set(
        policy.get(
            "required_controlled_scenarios",
            [],
        )
    )

    expected_scenarios = {
        "NO_ACTION_PROVEN_READY",
        "ACTION_FOUND_COMPLETE_SPLIT_READY",
        "ACTION_FOUND_INCOMPLETE_BLOCKED",
        "UNRESOLVED_BLOCKED",
        "IDENTITY_MISMATCH_BLOCKED",
        "SETTLEMENT_WINDOW_MISMATCH_BLOCKED",
        "AUTHORITATIVE_CONFLICT_BLOCKED",
        "SOURCE_ALREADY_ADJUSTED_READY",
    }

    require(
        expected_scenarios.issubset(
            scenarios
        ),
        "Controlled scenarios obrigatorios ausentes.",
    )

    prohibited = set(
        policy.get(
            "prohibited_behaviors",
            [],
        )
    )

    expected_prohibited = {
        "COPY_REVIEW_ANALYTICALLY_USABLE_TO_FINAL_SHORT_INTEREST",
        "INVENT_ACTION_TYPE",
        "INVENT_EFFECTIVE_DATE",
        "INVENT_SPLIT_RATIO",
        "INFER_SOURCE_ADJUSTMENT_FROM_NUMBERS",
        "DOUBLE_ADJUST_SOURCE_ADJUSTED_DATA",
        "ROUTE_UNRESOLVED_TO_RECONCILER",
        "WRITE_DIRECTLY_TO_RADAR_JSON",
        "WRITE_DIRECTLY_TO_SIGNAL",
        "WRITE_DIRECTLY_TO_CONFIDENCE",
        "WRITE_DIRECTLY_TO_RADAR_SCORE",
        "WRITE_DIRECTLY_TO_DECISION_CENTER",
    }

    require(
        expected_prohibited.issubset(
            prohibited
        ),
        "Proibicoes obrigatorias ausentes.",
    )


def run_test(
    number: int,
    name: str,
    function: Callable[
        [dict[str, Any]],
        None,
    ],
    policy: dict[str, Any],
) -> bool:

    print("-" * 72)
    print(f"TESTE {number}: {name}")

    try:
        function(policy)

        print("RESULTADO: PASS")
        return True

    except (
        TestFailure,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:

        print("RESULTADO: FAIL")
        print("ERRO:", exc)
        return False


def main() -> int:

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST")
    print("CORPORATE ACTION INTEGRATION POLICY TEST")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:
        policy = load_json(
            POLICY_FILE
        )

    except (
        OSError,
        json.JSONDecodeError,
        TestFailure,
    ) as exc:

        print("ERRO AO CARREGAR POLICY:")
        print(exc)
        return 1

    tests = [
        (
            1,
            "Policy identity and version",
            test_identity_and_version,
        ),
        (
            2,
            "Integration architecture",
            test_architecture,
        ),
        (
            3,
            "Fail-closed principles",
            test_fail_closed_principles,
        ),
        (
            4,
            "Accepted component versions",
            test_versions,
        ),
        (
            5,
            "Identity and settlement window",
            test_identity_and_window_contract,
        ),
        (
            6,
            "Review status routes",
            test_review_routes,
        ),
        (
            7,
            "Action evidence contract",
            test_action_evidence,
        ),
        (
            8,
            "Source adjustment contract",
            test_source_adjustment,
        ),
        (
            9,
            "Analytical usability and permissions",
            test_usability_and_permissions,
        ),
        (
            10,
            "Controlled scenarios and prohibitions",
            test_scenarios_and_prohibitions,
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