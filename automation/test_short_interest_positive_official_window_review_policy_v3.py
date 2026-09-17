"""
RADAR INSTITUCIONAL V3

SHORT INTEREST
POSITIVE OFFICIAL WINDOW REVIEW POLICY TEST

Version:
3.4D.2-B.2C.7A

Valida somente o contrato estrutural/metodologico.

Nao acessa rede.
Nao acessa SEC.
Nao acessa FINRA.
Nao modifica arquivos.
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


VERSION = "3.4D.2-B.2C.7A"

BASE_DIR = Path(__file__).resolve().parent.parent

POLICY_FILE = (
    BASE_DIR
    / "automation"
    / "short_interest_positive_official_window_review_policy_v3.json"
)


class TestFailure(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
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
            "POSITIVE_OFFICIAL_WINDOW_REVIEW"
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


def test_fail_closed_principles(
    policy: dict[str, Any],
) -> None:

    principles = policy["principles"]

    required_true = [
        "fail_closed",
        "absence_of_evidence_is_not_no_action",
        "zero_sec_matches_is_not_no_action",
        "resolver_status_resolved_is_not_no_action",
        "positive_official_review_required",
        "authoritative_source_required",
        "identity_continuity_required",
        "economic_window_must_be_explicit",
        "raw_evidence_must_be_preserved",
        "no_inference_from_price_volume_or_short_interest",
        "missing_is_not_zero",
        "missing_is_not_neutral",
    ]

    for field in required_true:
        require(
            principles.get(field) is True,
            f"Principio obrigatorio ausente/falso: {field}",
        )


def test_economic_window(
    policy: dict[str, Any],
) -> None:

    window = policy["economic_window"]

    require(
        window.get("basis") == "SETTLEMENT_DATE",
        "Economic window deve usar settlement date.",
    )

    require(
        window.get("previous_boundary") == "EXCLUSIVE",
        "Previous boundary deve ser EXCLUSIVE.",
    )

    require(
        window.get("current_boundary") == "INCLUSIVE",
        "Current boundary deve ser INCLUSIVE.",
    )

    require(
        window.get("previous_settlement_date_required")
        is True,
        "Previous settlement date deve ser obrigatoria.",
    )

    require(
        window.get("current_settlement_date_required")
        is True,
        "Current settlement date deve ser obrigatoria.",
    )

    require(
        window.get("current_must_be_after_previous")
        is True,
        "Current deve ser posterior a previous.",
    )


def test_identity_requirements(
    policy: dict[str, Any],
) -> None:

    identity = policy["identity_requirements"]

    require(
        identity.get("required") is True,
        "Identity deve ser obrigatoria.",
    )

    require(
        identity.get("ticker_only_prohibited") is True,
        "Ticker-only deve ser proibido.",
    )

    required_fields = set(
        identity.get("required_fields", [])
    )

    for field in (
        "ticker",
        "listing_exchange",
        "security_identity",
    ):
        require(
            field in required_fields,
            f"Identity required field ausente: {field}",
        )

    require(
        identity.get("usable_status") == "VERIFIED",
        "Somente identity VERIFIED deve ser utilizavel.",
    )


def test_authoritative_sources(
    policy: dict[str, Any],
) -> None:

    sources = policy["authoritative_sources"]

    require(
        sources.get("minimum_tier") == "TIER_1",
        "Minimum authoritative tier deve ser TIER_1.",
    )

    allowed = set(
        sources.get(
            "allowed_primary_source_types",
            [],
        )
    )

    required_sources = {
        "SEC_FILING",
        "OFFICIAL_EXCHANGE_NOTICE",
        "ISSUER_INVESTOR_RELATIONS",
        "FINRA_OFFICIAL",
    }

    require(
        required_sources.issubset(allowed),
        "Fontes T1 obrigatorias ausentes.",
    )

    require(
        sources.get(
            "supporting_sources_can_prove_no_action"
        )
        is False,
        "Supporting source nao pode provar NO_ACTION.",
    )

    require(
        sources.get(
            "supporting_sources_can_override_tier_1_conflict"
        )
        is False,
        "Supporting source nao pode superar conflito T1.",
    )


def test_positive_review_requirements(
    policy: dict[str, Any],
) -> None:

    requirements = policy["review_requirements"]

    expected_fields = [
        "official_window_review_completed",
        "authoritative_source_review_present",
        "economic_window_reviewed",
        "identity_continuity_verified",
        "no_qualified_action_in_economic_window",
        "no_unresolved_action_candidate_affecting_window",
        "no_authoritative_evidence_conflict",
    ]

    for field in expected_fields:
        item = requirements.get(field)

        require(
            isinstance(item, dict),
            f"Review requirement ausente: {field}",
        )

        require(
            item.get("required") is True,
            f"{field} deve ser required.",
        )

        require(
            item.get("expected_value") is True,
            f"{field} deve exigir true.",
        )


def test_no_action_positive_evidence(
    policy: dict[str, Any],
) -> None:

    evidence = policy[
        "positive_no_action_evidence"
    ]

    require(
        evidence.get(
            "minimum_authoritative_reviews"
        )
        >= 1,
        "Deve existir pelo menos uma review T1.",
    )

    required_record_fields = set(
        evidence.get(
            "review_record_required_fields",
            [],
        )
    )

    for field in (
        "source_id",
        "source_type",
        "source_tier",
        "review_scope",
        "previous_settlement_date",
        "current_settlement_date",
        "reviewed_at",
        "result",
    ):
        require(
            field in required_record_fields,
            f"Review record field ausente: {field}",
        )

    require(
        evidence.get(
            "result_that_supports_no_action"
        )
        == "NO_RELEVANT_ACTION_FOUND",
        (
            "Resultado positivo de NO_ACTION "
            "deve ser NO_RELEVANT_ACTION_FOUND."
        ),
    )


def test_sec_resolver_not_sufficient(
    policy: dict[str, Any],
) -> None:

    relation = policy[
        "sec_resolver_relationship"
    ]

    require(
        relation.get("resolver_is_evidence_input")
        is True,
        "SEC resolver deve ser evidence input.",
    )

    require(
        relation.get(
            "resolver_is_not_positive_no_action_proof"
        )
        is True,
        "SEC resolver isolado nao pode provar NO_ACTION.",
    )

    require(
        relation["zero_raw_matches"].get(
            "sufficient_for_no_action"
        )
        is False,
        "Zero raw matches nao pode provar NO_ACTION.",
    )

    require(
        relation["zero_qualified_evidence"].get(
            "sufficient_for_no_action"
        )
        is False,
        (
            "Zero qualified evidence nao pode "
            "provar NO_ACTION."
        ),
    )

    require(
        relation[
            "resolved_without_qualified_evidence"
        ].get("sufficient_for_no_action")
        is False,
        (
            "RESOLVED sem qualified evidence "
            "nao pode provar NO_ACTION."
        ),
    )


def test_decision_logic(
    policy: dict[str, Any],
) -> None:

    logic = policy["decision_logic"]

    no_action = logic["NO_ACTION_PROVEN"]

    require(
        no_action["output"].get(
            "review_status"
        )
        == "NO_ACTION_PROVEN",
        "NO_ACTION_PROVEN review status incorreto.",
    )

    require(
        no_action["output"].get(
            "corporate_action_status"
        )
        == "NO_ACTION",
        "NO_ACTION_PROVEN deve produzir NO_ACTION.",
    )

    require(
        no_action["output"].get(
            "reconciliation_eligible"
        )
        is True,
        "NO_ACTION_PROVEN deve ser elegivel.",
    )

    require(
        no_action["output"].get(
            "analytically_usable"
        )
        is True,
        "NO_ACTION_PROVEN deve ser utilizavel.",
    )

    unresolved = logic["UNRESOLVED"]

    require(
        unresolved["output"].get(
            "reconciliation_eligible"
        )
        is False,
        "UNRESOLVED nao pode ser elegivel.",
    )

    require(
        unresolved["output"].get(
            "analytically_usable"
        )
        is False,
        "UNRESOLVED nao pode ser utilizavel.",
    )


def test_downstream_and_prohibitions(
    policy: dict[str, Any],
) -> None:

    downstream = policy[
        "downstream_permissions"
    ]

    require(
        downstream["NO_ACTION_PROVEN"].get(
            "may_enter_corporate_action_reconciler"
        )
        is True,
        "NO_ACTION_PROVEN deve poder entrar no reconciler.",
    )

    require(
        downstream["UNRESOLVED"].get(
            "may_enter_corporate_action_reconciler"
        )
        is False,
        "UNRESOLVED nao pode entrar no reconciler.",
    )

    prohibited = set(
        policy.get(
            "prohibited_behaviors",
            [],
        )
    )

    required_prohibitions = {
        "DECLARE_NO_ACTION_FROM_ZERO_SEC_MATCHES_ONLY",
        "DECLARE_NO_ACTION_FROM_ZERO_QUALIFIED_EVIDENCE_ONLY",
        "DECLARE_NO_ACTION_FROM_RESOLVER_RESOLVED_STATUS_ONLY",
        "DECLARE_NO_ACTION_FROM_PRICE_BEHAVIOR",
        "DECLARE_NO_ACTION_FROM_VOLUME_BEHAVIOR",
        "DECLARE_NO_ACTION_FROM_SHORT_INTEREST_BEHAVIOR",
        "USE_TIER_2_OR_TIER_3_AS_SOLE_NO_ACTION_PROOF",
        "ASSUME_MISSING_REVIEW_MEANS_NO_ACTION",
        "WRITE_DIRECTLY_TO_RADAR_SCORE",
        "WRITE_DIRECTLY_TO_DECISION_CENTER",
    }

    require(
        required_prohibitions.issubset(
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
    print("POSITIVE OFFICIAL WINDOW REVIEW POLICY TEST")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:
        policy = load_json(POLICY_FILE)

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
            "Fail-closed principles",
            test_fail_closed_principles,
        ),
        (
            3,
            "Economic window semantics",
            test_economic_window,
        ),
        (
            4,
            "Identity requirements",
            test_identity_requirements,
        ),
        (
            5,
            "Authoritative source requirements",
            test_authoritative_sources,
        ),
        (
            6,
            "Positive review requirements",
            test_positive_review_requirements,
        ),
        (
            7,
            "Positive NO_ACTION evidence",
            test_no_action_positive_evidence,
        ),
        (
            8,
            "SEC resolver is not sufficient",
            test_sec_resolver_not_sufficient,
        ),
        (
            9,
            "Decision logic",
            test_decision_logic,
        ),
        (
            10,
            "Downstream permissions and prohibitions",
            test_downstream_and_prohibitions,
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