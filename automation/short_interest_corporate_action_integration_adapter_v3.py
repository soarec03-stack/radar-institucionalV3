"""
RADAR INSTITUCIONAL V3

SHORT INTEREST
CORPORATE ACTION INTEGRATION ADAPTER

Version:
3.4D.2-B.2C.7C.2

Responsabilidade:

Positive Official Window Review
        ->
Integration Adapter
        ->
Corporate Action Reconciler

O Adapter:
- valida o contrato upstream;
- valida identidade;
- valida settlement window;
- valida Action Evidence;
- valida Source Adjustment;
- preserva raw review;
- produz input controlado para o Reconciler.

O Adapter NAO:
- coleta dados;
- inventa evidencia;
- infere corporate actions;
- infere split ratio;
- calcula ajuste de Short Interest;
- declara comparabilidade final;
- libera analytical usability final;
- calcula Signal;
- calcula Confidence;
- calcula Radar Score;
- gera Decision;
- altera radar_v3.json.

Fail closed.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.7C.2"

EXPECTED_POLICY_VERSION = "3.4D.2-B.2C.7C.1"

BASE_DIR = Path(__file__).resolve().parent.parent

POLICY_FILE = (
    BASE_DIR
    / "automation"
    / "short_interest_corporate_action_integration_policy_v3.json"
)

FIXTURE_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_corporate_action_integration_test_cases_v3.json"
)


class IntegrationError(Exception):
    pass


def read_json(
    path: Path,
) -> dict[str, Any]:

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise IntegrationError(
            f"JSON root invalido: {path}"
        )

    return data


def parse_iso_date(
    value: Any,
) -> date:

    if not isinstance(value, str):
        raise IntegrationError(
            "Data deve ser string ISO."
        )

    try:
        return date.fromisoformat(value)

    except ValueError as exc:
        raise IntegrationError(
            f"Data ISO invalida: {value}"
        ) from exc


def non_empty_string(
    value: Any,
) -> bool:

    return (
        isinstance(value, str)
        and bool(value.strip())
    )


def valid_positive_number(
    value: Any,
) -> bool:

    if isinstance(value, bool):
        return False

    if not isinstance(
        value,
        (int, float),
    ):
        return False

    return value > 0


def blocked_result(
    case: dict[str, Any],
    diagnostics: list[str],
) -> dict[str, Any]:

    return {
        "adapter_version": VERSION,

        "case": case.get("case"),
        "ticker": case.get("ticker"),

        "previous_settlement_date":
            case.get("previous_settlement_date"),

        "current_settlement_date":
            case.get("current_settlement_date"),

        "identity": deepcopy(
            case.get("identity")
        ),

        "review_status": (
            case.get("review", {})
            .get("review_status")
            if isinstance(
                case.get("review"),
                dict,
            )
            else None
        ),

        "integration_status":
            "BLOCKED",

        "route":
            "NONE",

        "reconciler_input_status":
            "UNRESOLVED",

        "action_evidence": deepcopy(
            case.get("action_evidence")
        ),

        "source_adjustment": deepcopy(
            case.get("source_adjustment")
        ),

        "raw_review": deepcopy(
            case.get("review")
        ),

        "final_short_interest_analytically_usable":
            False,

        "diagnostics": diagnostics,
    }


def ready_result(
    case: dict[str, Any],
    *,
    route: str,
    reconciler_input_status: str,
    diagnostics: list[str] | None = None,
) -> dict[str, Any]:

    return {
        "adapter_version": VERSION,

        "case": case.get("case"),
        "ticker": case.get("ticker"),

        "previous_settlement_date":
            case.get("previous_settlement_date"),

        "current_settlement_date":
            case.get("current_settlement_date"),

        "identity": deepcopy(
            case.get("identity")
        ),

        "review_status": (
            case["review"]["review_status"]
        ),

        "integration_status":
            "READY_FOR_RECONCILIATION",

        "route":
            route,

        "reconciler_input_status":
            reconciler_input_status,

        "action_evidence": deepcopy(
            case.get("action_evidence")
        ),

        "source_adjustment": deepcopy(
            case.get("source_adjustment")
        ),

        "raw_review": deepcopy(
            case.get("review")
        ),

        # Regra crítica:
        # o Adapter NUNCA promove usability final.
        "final_short_interest_analytically_usable":
            False,

        "diagnostics":
            diagnostics or [],
    }


def validate_identity(
    case: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[bool, str | None]:

    identity = case.get("identity")

    if not isinstance(identity, dict):
        return False, "IDENTITY_MISSING"

    required_fields = (
        policy[
            "identity_contract"
        ][
            "required_fields"
        ]
    )

    for field in required_fields:

        if not non_empty_string(
            identity.get(field)
        ):
            return (
                False,
                f"IDENTITY_FIELD_MISSING:{field}",
            )

    if (
        identity.get("ticker")
        != case.get("ticker")
    ):
        return (
            False,
            "IDENTITY_TICKER_MISMATCH",
        )

    required_status = (
        policy[
            "identity_contract"
        ][
            "required_continuity_status"
        ]
    )

    if (
        identity.get("continuity_status")
        != required_status
    ):
        return (
            False,
            "IDENTITY_CONTINUITY_NOT_VERIFIED",
        )

    return True, None


def validate_settlement_window(
    case: dict[str, Any],
) -> tuple[bool, str | None]:

    previous_value = case.get(
        "previous_settlement_date"
    )

    current_value = case.get(
        "current_settlement_date"
    )

    try:
        previous_date = parse_iso_date(
            previous_value
        )

        current_date = parse_iso_date(
            current_value
        )

    except IntegrationError:
        return (
            False,
            "INVALID_SETTLEMENT_DATE",
        )

    if current_date <= previous_date:
        return (
            False,
            "INVALID_SETTLEMENT_WINDOW",
        )

    review = case.get("review")

    if not isinstance(review, dict):
        return (
            False,
            "REVIEW_MISSING",
        )

    if (
        review.get(
            "previous_settlement_date"
        )
        != previous_value
        or
        review.get(
            "current_settlement_date"
        )
        != current_value
    ):
        return (
            False,
            "SETTLEMENT_WINDOW_MISMATCH",
        )

    return True, None


def validate_required_upstream(
    review: dict[str, Any],
    requirements: dict[str, Any],
) -> tuple[bool, str | None]:

    for field, expected in requirements.items():

        actual = review.get(field)

        if actual != expected:
            return (
                False,
                (
                    "UPSTREAM_CONTRACT_MISMATCH:"
                    f"{field}"
                ),
            )

    return True, None


def validate_action_evidence(
    case: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[bool, str | None]:

    evidence = case.get(
        "action_evidence"
    )

    if not isinstance(evidence, dict):
        return (
            False,
            "ACTION_EVIDENCE_MISSING",
        )

    contract = policy[
        "action_evidence_contract"
    ]

    for field in contract[
        "required_fields"
    ]:

        if field not in evidence:
            return (
                False,
                f"ACTION_EVIDENCE_FIELD_MISSING:{field}",
            )

        value = evidence.get(field)

        if value is None:
            return (
                False,
                f"ACTION_EVIDENCE_FIELD_NULL:{field}",
            )

        if (
            isinstance(value, str)
            and not value.strip()
        ):
            return (
                False,
                f"ACTION_EVIDENCE_FIELD_EMPTY:{field}",
            )

    action_type = evidence.get(
        "action_type"
    )

    if (
        action_type
        not in contract[
            "allowed_action_types"
        ]
    ):
        return (
            False,
            "ACTION_TYPE_NOT_ALLOWED",
        )

    if (
        evidence.get("source_tier")
        != contract[
            "required_source_tier"
        ]
    ):
        return (
            False,
            "ACTION_SOURCE_NOT_TIER_1",
        )

    if (
        evidence.get("identity_status")
        != contract[
            "required_identity_status"
        ]
    ):
        return (
            False,
            "ACTION_IDENTITY_NOT_VERIFIED",
        )

    if (
        evidence.get("evidence_status")
        != contract[
            "required_evidence_status"
        ]
    ):
        return (
            False,
            "ACTION_EVIDENCE_NOT_VERIFIED",
        )

    try:
        effective_date = parse_iso_date(
            evidence.get("effective_date")
        )

        previous_date = parse_iso_date(
            case.get(
                "previous_settlement_date"
            )
        )

        current_date = parse_iso_date(
            case.get(
                "current_settlement_date"
            )
        )

    except IntegrationError:
        return (
            False,
            "INVALID_ACTION_EFFECTIVE_DATE",
        )

    # Economic window:
    # previous EXCLUSIVE
    # current INCLUSIVE
    if not (
        effective_date > previous_date
        and effective_date <= current_date
    ):
        return (
            False,
            "ACTION_OUTSIDE_ECONOMIC_WINDOW",
        )

    if (
        action_type
        in contract[
            "ratio_required_for"
        ]
    ):

        numerator = evidence.get(
            "ratio_numerator"
        )

        denominator = evidence.get(
            "ratio_denominator"
        )

        if not valid_positive_number(
            numerator
        ):
            return (
                False,
                "INVALID_OR_MISSING_RATIO_NUMERATOR",
            )

        if not valid_positive_number(
            denominator
        ):
            return (
                False,
                "INVALID_OR_MISSING_RATIO_DENOMINATOR",
            )

    return True, None


def validate_source_adjustment(
    case: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[bool, str | None]:

    adjustment = case.get(
        "source_adjustment"
    )

    if not isinstance(adjustment, dict):
        return (
            False,
            "SOURCE_ADJUSTMENT_MISSING",
        )

    contract = policy[
        "source_adjustment_contract"
    ]

    status = adjustment.get("status")

    if (
        status
        not in contract[
            "allowed_statuses"
        ]
    ):
        return (
            False,
            "SOURCE_ADJUSTMENT_STATUS_INVALID",
        )

    if status == "UNRESOLVED":
        return (
            False,
            "SOURCE_ADJUSTMENT_UNRESOLVED",
        )

    if status == "NOT_ADJUSTED":
        return True, None

    if status == "SOURCE_ALREADY_ADJUSTED":

        requirements = contract[
            "SOURCE_ALREADY_ADJUSTED"
        ]

        for field in requirements[
            "required_fields"
        ]:

            value = adjustment.get(field)

            if value is None:
                return (
                    False,
                    (
                        "SOURCE_ADJUSTMENT_FIELD_MISSING:"
                        f"{field}"
                    ),
                )

            if (
                isinstance(value, str)
                and not value.strip()
            ):
                return (
                    False,
                    (
                        "SOURCE_ADJUSTMENT_FIELD_EMPTY:"
                        f"{field}"
                    ),
                )

        if (
            adjustment.get("source_tier")
            != requirements[
                "required_source_tier"
            ]
        ):
            return (
                False,
                "SOURCE_ADJUSTMENT_NOT_TIER_1",
            )

        if (
            adjustment.get("evidence_status")
            != requirements[
                "required_evidence_status"
            ]
        ):
            return (
                False,
                "SOURCE_ADJUSTMENT_NOT_VERIFIED",
            )

        return True, None

    return (
        False,
        "SOURCE_ADJUSTMENT_FAIL_CLOSED",
    )


def adapt_case(
    case: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:

    # --------------------------------------------------------
    # 1. Root input
    # --------------------------------------------------------

    if not isinstance(case, dict):
        raise IntegrationError(
            "Case deve ser objeto."
        )

    ticker = case.get("ticker")

    if not non_empty_string(ticker):
        return blocked_result(
            case,
            ["TICKER_MISSING"],
        )

    # --------------------------------------------------------
    # 2. Identity
    # --------------------------------------------------------

    identity_ok, identity_error = (
        validate_identity(
            case,
            policy,
        )
    )

    if not identity_ok:
        return blocked_result(
            case,
            [identity_error or "IDENTITY_BLOCKED"],
        )

    # --------------------------------------------------------
    # 3. Settlement window
    # --------------------------------------------------------

    window_ok, window_error = (
        validate_settlement_window(
            case
        )
    )

    if not window_ok:
        return blocked_result(
            case,
            [window_error or "WINDOW_BLOCKED"],
        )

    # --------------------------------------------------------
    # 4. Review
    # --------------------------------------------------------

    review = case.get("review")

    if not isinstance(review, dict):
        return blocked_result(
            case,
            ["REVIEW_MISSING"],
        )

    review_status = review.get(
        "review_status"
    )

    review_contract = policy[
        "review_status_contract"
    ]

    if (
        review_status
        not in review_contract[
            "allowed_statuses"
        ]
    ):
        return blocked_result(
            case,
            ["REVIEW_STATUS_INVALID"],
        )

    # --------------------------------------------------------
    # 5. Authoritative conflict is always blocking
    # --------------------------------------------------------

    if (
        review.get(
            "no_authoritative_evidence_conflict"
        )
        is not True
    ):
        return blocked_result(
            case,
            ["AUTHORITATIVE_EVIDENCE_CONFLICT"],
        )

    # --------------------------------------------------------
    # 6. UNRESOLVED never enters Reconciler
    # --------------------------------------------------------

    if review_status == "UNRESOLVED":
        return blocked_result(
            case,
            ["UPSTREAM_REVIEW_UNRESOLVED"],
        )

    # --------------------------------------------------------
    # 7. NO_ACTION_PROVEN
    # --------------------------------------------------------

    if review_status == "NO_ACTION_PROVEN":

        requirements = (
            review_contract[
                "NO_ACTION_PROVEN"
            ][
                "required_upstream"
            ]
        )

        upstream_ok, upstream_error = (
            validate_required_upstream(
                review,
                requirements,
            )
        )

        if not upstream_ok:
            return blocked_result(
                case,
                [
                    upstream_error
                    or
                    "NO_ACTION_UPSTREAM_INVALID"
                ],
            )

        source_ok, source_error = (
            validate_source_adjustment(
                case,
                policy,
            )
        )

        if not source_ok:
            return blocked_result(
                case,
                [
                    source_error
                    or
                    "SOURCE_ADJUSTMENT_BLOCKED"
                ],
            )

        # Para NO_ACTION não faz sentido transportar
        # SOURCE_ALREADY_ADJUSTED como justificativa de
        # uma corporate action inexistente.
        if (
            case.get(
                "source_adjustment",
                {},
            ).get("status")
            == "SOURCE_ALREADY_ADJUSTED"
        ):
            return blocked_result(
                case,
                [
                    "SOURCE_ADJUSTED_WITH_NO_ACTION"
                ],
            )

        return ready_result(
            case,
            route="NO_ACTION",
            reconciler_input_status=
                "NO_ACTION_PROVEN",
        )

    # --------------------------------------------------------
    # 8. ACTION_FOUND
    # --------------------------------------------------------

    if review_status == "ACTION_FOUND":

        requirements = (
            review_contract[
                "ACTION_FOUND"
            ][
                "required_upstream"
            ]
        )

        upstream_ok, upstream_error = (
            validate_required_upstream(
                review,
                requirements,
            )
        )

        if not upstream_ok:
            return blocked_result(
                case,
                [
                    upstream_error
                    or
                    "ACTION_UPSTREAM_INVALID"
                ],
            )

        evidence_ok, evidence_error = (
            validate_action_evidence(
                case,
                policy,
            )
        )

        if not evidence_ok:
            return blocked_result(
                case,
                [
                    evidence_error
                    or
                    "ACTION_EVIDENCE_BLOCKED"
                ],
            )

        source_ok, source_error = (
            validate_source_adjustment(
                case,
                policy,
            )
        )

        if not source_ok:
            return blocked_result(
                case,
                [
                    source_error
                    or
                    "SOURCE_ADJUSTMENT_BLOCKED"
                ],
            )

        return ready_result(
            case,
            route="VERIFIED_ACTION",
            reconciler_input_status=
                "VERIFIED_ACTION",
        )

    # --------------------------------------------------------
    # 9. Fail closed
    # --------------------------------------------------------

    return blocked_result(
        case,
        ["UNHANDLED_REVIEW_STATUS"],
    )


def validate_expected(
    result: dict[str, Any],
    expected: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    for field, expected_value in (
        expected.items()
    ):

        actual_value = result.get(field)

        if actual_value != expected_value:
            errors.append(
                (
                    f"{field}: "
                    f"esperado={expected_value!r}, "
                    f"recebido={actual_value!r}"
                )
            )

    return errors


def run_cases(
    fixtures: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[int, int]:

    cases = fixtures.get("cases")

    if not isinstance(cases, list):
        raise IntegrationError(
            "fixtures.cases deve ser lista."
        )

    passed = 0
    failed = 0

    for index, case in enumerate(
        cases,
        start=1,
    ):

        print("-" * 72)

        if not isinstance(case, dict):
            print(
                f"TESTE {index}: INVALID_CASE"
            )
            print("RESULTADO: FAIL")
            failed += 1
            continue

        case_name = case.get(
            "case",
            f"CASE_{index}",
        )

        print(
            f"TESTE {index}: {case_name}"
        )

        expected = case.get("expected")

        if not isinstance(expected, dict):
            print("RESULTADO: FAIL")
            print(
                "ERRO: expected ausente/invalido."
            )
            failed += 1
            continue

        try:
            result = adapt_case(
                case,
                policy,
            )

            errors = validate_expected(
                result,
                expected,
            )

        except Exception as exc:
            print("RESULTADO: FAIL")
            print(
                "ERRO NA EXECUCAO:",
                exc,
            )
            failed += 1
            continue

        if errors:
            print("RESULTADO: FAIL")

            for error in errors:
                print("ERRO:", error)

            print(
                "Diagnostics:",
                result.get(
                    "diagnostics"
                ),
            )

            failed += 1
            continue

        print("RESULTADO: PASS")
        print(
            "Integration:",
            result[
                "integration_status"
            ],
        )
        print(
            "Route:",
            result["route"],
        )
        print(
            "Reconciler input:",
            result[
                "reconciler_input_status"
            ],
        )
        print(
            "Final SI usable:",
            result[
                "final_short_interest_analytically_usable"
            ],
        )

        if result["diagnostics"]:
            print(
                "Diagnostics:",
                result["diagnostics"],
            )

        passed += 1

    return passed, failed


def validate_policy(
    policy: dict[str, Any],
) -> None:

    if (
        policy.get("version")
        != EXPECTED_POLICY_VERSION
    ):
        raise IntegrationError(
            (
                "Integration Policy version "
                "incompativel. "
                f"Esperado={EXPECTED_POLICY_VERSION}, "
                f"recebido={policy.get('version')}"
            )
        )

    if (
        policy.get("status")
        != "ACTIVE"
    ):
        raise IntegrationError(
            "Integration Policy nao esta ACTIVE."
        )

    principles = policy.get(
        "principles"
    )

    if not isinstance(principles, dict):
        raise IntegrationError(
            "Policy principles ausente."
        )

    required_principles = [
        "fail_closed",
        "adapter_must_not_invent_evidence",
        "adapter_must_not_infer_action_parameters",
        "adapter_must_not_infer_source_adjustment",
        "adapter_must_preserve_raw_evidence",
        "review_analytically_usable_is_not_final_short_interest_usable",
        "final_analytical_usability_belongs_to_reconciler",
    ]

    for principle in required_principles:

        if principles.get(principle) is not True:
            raise IntegrationError(
                (
                    "Principio obrigatorio "
                    f"ausente/falso: {principle}"
                )
            )


def main() -> int:

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST")
    print("CORPORATE ACTION INTEGRATION ADAPTER")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:
        policy = read_json(
            POLICY_FILE
        )

        fixtures = read_json(
            FIXTURE_FILE
        )

        validate_policy(
            policy
        )

    except (
        OSError,
        json.JSONDecodeError,
        IntegrationError,
    ) as exc:

        print("ERRO DE INICIALIZACAO:")
        print(exc)
        return 1

    if (
        fixtures.get(
            "contract_version"
        )
        != VERSION
    ):
        print(
            "ERRO: fixture contract version "
            "incompativel."
        )
        return 1

    try:
        passed, failed = run_cases(
            fixtures,
            policy,
        )

    except IntegrationError as exc:
        print("ERRO:")
        print(exc)
        return 1

    total = passed + failed

    print("=" * 72)
    print("RESUMO")
    print("=" * 72)
    print("Total :", total)
    print("PASS  :", passed)
    print("FAIL  :", failed)

    if failed:
        print(
            "RESULTADO FINAL: REPROVADO"
        )
        return 1

    print(
        "RESULTADO FINAL: APROVADO"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())