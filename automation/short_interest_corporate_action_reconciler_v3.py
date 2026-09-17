"""
RADAR INSTITUCIONAL V3
SHORT INTEREST CORPORATE ACTION RECONCILER

Version:
3.4D.2-B.2C.2

Primeira implementacao controlada do reconciliador.

Nesta etapa:
- opera somente sobre fixtures sinteticos;
- nao acessa rede;
- nao acessa SEC;
- nao acessa FINRA;
- nao modifica registry oficial;
- nao modifica radar_v3.json;
- nao modifica Signal;
- nao modifica Confidence;
- nao modifica Score;
- nao modifica Decision.

Objetivo:
implementar deterministicamente o contrato definido em
short_interest_corporate_action_reconciliation_policy_v3.json.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.5"

DEFAULT_POLICY = Path(
    "automation/"
    "short_interest_corporate_action_reconciliation_policy_v3.json"
)

DEFAULT_CASES = Path(
    "input/"
    "short_interest_corporate_action_reconciliation_test_cases_v3.json"
)


class ReconciliationError(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ReconciliationError(
            f"Arquivo nao encontrado: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ReconciliationError(
            f"JSON invalido em {path}: "
            f"linha {exc.lineno}, coluna {exc.colno}"
        ) from exc

    if not isinstance(value, dict):
        raise ReconciliationError(
            f"Root JSON deve ser objeto: {path}"
        )

    return value


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def valid_positive_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False

    if not isinstance(value, (int, float)):
        return False

    return math.isfinite(float(value)) and float(value) > 0


def action_in_economic_window(
    action: dict[str, Any],
    previous_settlement_date: str,
    current_settlement_date: str,
) -> bool:

    effective = parse_date(action.get("effective_date"))
    previous = parse_date(previous_settlement_date)
    current = parse_date(current_settlement_date)

    if effective is None or previous is None or current is None:
        return False

    return previous < effective <= current


def action_is_authoritative(
    action: dict[str, Any],
) -> bool:

    return (
        action.get("verified") is True
        and action.get("source_tier") == "TIER_1"
        and action.get("source_type")
        in {
            "SEC_FILING",
            "OFFICIAL_EXCHANGE_NOTICE",
            "ISSUER_INVESTOR_RELATIONS",
            "FINRA",
        }
    )


def supported_share_adjusting_action(
    action: dict[str, Any],
) -> bool:

    return action.get("action_type") in {
        "STOCK_SPLIT",
        "REVERSE_STOCK_SPLIT",
    }


def deterministic_adjustment_factor(
    action: dict[str, Any],
) -> float | None:

    numerator = action.get("ratio_numerator")
    denominator = action.get("ratio_denominator")

    if not valid_positive_number(numerator):
        return None

    if not valid_positive_number(denominator):
        return None

    return float(numerator) / float(denominator)

def adjust_previous_to_current_basis(
    previous_raw: Any,
    factor: Any,
) -> float:

    if isinstance(previous_raw, bool):
        raise ReconciliationError(
            "previous_raw invalido."
        )

    if not isinstance(previous_raw, (int, float)):
        raise ReconciliationError(
            "previous_raw deve ser numerico."
        )

    if not math.isfinite(float(previous_raw)):
        raise ReconciliationError(
            "previous_raw deve ser finito."
        )

    if float(previous_raw) < 0:
        raise ReconciliationError(
            "previous_raw nao pode ser negativo."
        )

    if not valid_positive_number(factor):
        raise ReconciliationError(
            "adjustment_factor deve ser positivo."
        )

    return float(previous_raw) * float(factor)


def calculate_adjusted_change_pct(
    previous_adjusted: Any,
    current_raw: Any,
) -> float:

    if not valid_positive_number(previous_adjusted):
        raise ReconciliationError(
            "previous_adjusted deve ser maior que zero."
        )

    if isinstance(current_raw, bool):
        raise ReconciliationError(
            "current_raw invalido."
        )

    if not isinstance(current_raw, (int, float)):
        raise ReconciliationError(
            "current_raw deve ser numerico."
        )

    if not math.isfinite(float(current_raw)):
        raise ReconciliationError(
            "current_raw deve ser finito."
        )

    if float(current_raw) < 0:
        raise ReconciliationError(
            "current_raw nao pode ser negativo."
        )

    return (
        (
            float(current_raw)
            - float(previous_adjusted)
        )
        / float(previous_adjusted)
    ) * 100.0

def blocked_result(
    case_name: str,
    reason: str,
    identity_status: str,
    diagnostics: list[str],
) -> dict[str, Any]:

    return {
        "case": case_name,
        "corporate_action_status": "UNRESOLVED",
        "reconciliation_status": "UNRESOLVED",
        "identity_continuity_status": identity_status,
        "source_adjustment_status": "UNRESOLVED",
        "adjustment_status": "BLOCKED",
        "adjustment_authorized": False,
        "adjustment_factor": None,
        "analytically_usable": False,
        "reason": reason,
        "evidence_summary": {
            "qualified_action_count": 0,
            "applicable_action_count": 0,
        },
        "diagnostics": diagnostics,
    }


def reconcile_case(
    case: dict[str, Any],
    common: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:

    case_name = str(case.get("case") or "UNKNOWN")

    identity = case.get("identity")
    evidence = case.get("evidence")
    source_adjustment = case.get("source_adjustment")

    if not isinstance(identity, dict):
        return blocked_result(
            case_name,
            "IDENTITY_DATA_INVALID",
            "UNRESOLVED",
            ["IDENTITY_DATA_MISSING_OR_INVALID"],
        )

    if not isinstance(evidence, dict):
        return blocked_result(
            case_name,
            "EVIDENCE_DATA_INVALID",
            "UNRESOLVED",
            ["EVIDENCE_DATA_MISSING_OR_INVALID"],
        )

    if not isinstance(source_adjustment, dict):
        return blocked_result(
            case_name,
            "SOURCE_ADJUSTMENT_DATA_INVALID",
            "UNRESOLVED",
            ["SOURCE_ADJUSTMENT_DATA_MISSING_OR_INVALID"],
        )

    previous_date = common.get("previous_settlement_date")
    current_date = common.get("current_settlement_date")

    if parse_date(previous_date) is None:
        return blocked_result(
            case_name,
            "SETTLEMENT_WINDOW_INVALID",
            "UNRESOLVED",
            ["PREVIOUS_SETTLEMENT_DATE_INVALID"],
        )

    if parse_date(current_date) is None:
        return blocked_result(
            case_name,
            "SETTLEMENT_WINDOW_INVALID",
            "UNRESOLVED",
            ["CURRENT_SETTLEMENT_DATE_INVALID"],
        )

    if parse_date(previous_date) >= parse_date(current_date):
        return blocked_result(
            case_name,
            "SETTLEMENT_WINDOW_INVALID",
            "UNRESOLVED",
            ["SETTLEMENT_WINDOW_NOT_INCREASING"],
        )

    # ------------------------------------------------------------
    # 1. IDENTITY
    # ------------------------------------------------------------

    if identity.get("identity_conflict") is True:
        return blocked_result(
            case_name,
            "IDENTITY_CONTINUITY_CONFLICT",
            "CONFLICT",
            ["IDENTITY_CONFLICT"],
        )

    if identity.get("master_matches_collection") is not True:
        return blocked_result(
            case_name,
            "IDENTITY_CONTINUITY_CONFLICT",
            "CONFLICT",
            ["MASTER_IDENTITY_MISMATCH"],
        )

    if identity.get("identity_continuity_verified") is not True:
        return blocked_result(
            case_name,
            "IDENTITY_CONTINUITY_UNRESOLVED",
            "UNRESOLVED",
            ["IDENTITY_CONTINUITY_NOT_VERIFIED"],
        )

    identity_status = "VERIFIED"

    # ------------------------------------------------------------
    # 2. EVIDENCE RESOLVER / WINDOW
    # ------------------------------------------------------------

    if evidence.get("resolver_status") != "RESOLVED":
        return blocked_result(
            case_name,
            "EVIDENCE_RESOLVER_NOT_RESOLVED",
            identity_status,
            ["EVIDENCE_RESOLVER_PARTIAL_OR_BLOCKED"],
        )

    if evidence.get(
        "settlement_window_matches_collection"
    ) is not True:
        return blocked_result(
            case_name,
            "SETTLEMENT_WINDOW_MISMATCH",
            identity_status,
            ["SETTLEMENT_WINDOW_MISMATCH"],
        )

    # ------------------------------------------------------------
    # 3. AUTHORITATIVE CONFLICT
    # ------------------------------------------------------------

    if evidence.get("authoritative_conflict") is True:
        return blocked_result(
            case_name,
            "CONFLICTING_AUTHORITATIVE_EVIDENCE",
            identity_status,
            ["AUTHORITATIVE_EVIDENCE_CONFLICT"],
        )

    qualified_actions = evidence.get("qualified_actions", [])

    if not isinstance(qualified_actions, list):
        return blocked_result(
            case_name,
            "EVIDENCE_DATA_INVALID",
            identity_status,
            ["QUALIFIED_ACTIONS_NOT_LIST"],
        )

    unresolved_candidates = evidence.get(
        "unresolved_action_candidates",
        [],
    )

    if not isinstance(unresolved_candidates, list):
        return blocked_result(
            case_name,
            "EVIDENCE_DATA_INVALID",
            identity_status,
            ["UNRESOLVED_ACTION_CANDIDATES_NOT_LIST"],
        )

    if unresolved_candidates:
        return blocked_result(
            case_name,
            "UNRESOLVED_ACTION_CANDIDATE",
            identity_status,
            ["POTENTIALLY_APPLICABLE_ACTION_UNRESOLVED"],
        )

    authoritative_actions = [
        action
        for action in qualified_actions
        if isinstance(action, dict)
        and action_is_authoritative(action)
    ]

    applicable_actions = [
        action
        for action in authoritative_actions
        if action_in_economic_window(
            action,
            previous_date,
            current_date,
        )
    ]

    # Se existem qualified actions, mas nenhuma delas satisfaz
    # autoridade/verificacao necessaria, nao podemos silenciosamente
    # converter isso em NO_ACTION.
    if qualified_actions and not authoritative_actions:
        return blocked_result(
            case_name,
            "INSUFFICIENT_AUTHORITATIVE_EVIDENCE",
            identity_status,
            ["QUALIFIED_ACTION_NOT_AUTHORITATIVE"],
        )

    # ------------------------------------------------------------
    # 4. NO APPLICABLE ACTION
    # ------------------------------------------------------------

    if not applicable_actions:

        positive_review = (
            evidence.get("official_window_review_completed")
            is True
            and evidence.get(
                "authoritative_source_review_present"
            )
            is True
        )

        if not positive_review:
            return blocked_result(
                case_name,
                "INSUFFICIENT_AUTHORITATIVE_EVIDENCE",
                identity_status,
                [
                    "POSITIVE_OFFICIAL_WINDOW_REVIEW_REQUIRED"
                ],
            )

        return {
            "case": case_name,
            "corporate_action_status": "NO_ACTION",
            "reconciliation_status": "NO_ACTION",
            "identity_continuity_status": identity_status,
            "source_adjustment_status": "NOT_APPLICABLE",
            "adjustment_status": "NOT_REQUIRED",
            "adjustment_authorized": False,
            "adjustment_factor": None,
            "analytically_usable": True,
            "reason":
                "NO_APPLICABLE_CORPORATE_ACTION_CONFIRMED",
            "evidence_summary": {
                "qualified_action_count":
                    len(qualified_actions),
                "authoritative_action_count":
                    len(authoritative_actions),
                "applicable_action_count": 0,
                "official_window_review_completed": True,
                "authoritative_source_review_present": True,
            },
            "diagnostics": [],
        }

    # ------------------------------------------------------------
    # 5. MULTIPLE APPLICABLE ACTIONS
    # ------------------------------------------------------------

    if len(applicable_actions) != 1:
        return blocked_result(
            case_name,
            "CONFLICTING_AUTHORITATIVE_EVIDENCE",
            identity_status,
            ["MULTIPLE_APPLICABLE_ACTIONS_REQUIRE_REVIEW"],
        )

    action = applicable_actions[0]

    # ------------------------------------------------------------
    # 6. SUPPORTED ACTION
    # ------------------------------------------------------------

    if not supported_share_adjusting_action(action):
        return blocked_result(
            case_name,
            "ACTION_REQUIRES_IDENTITY_RECONCILIATION",
            identity_status,
            ["ACTION_TYPE_NOT_DETERMINISTICALLY_ADJUSTABLE"],
        )

    factor = deterministic_adjustment_factor(action)

    if factor is None:
        return blocked_result(
            case_name,
            "QUALIFIED_ACTION_MISSING_REQUIRED_PARAMETERS",
            identity_status,
            ["VERIFIED_SPLIT_RATIO_REQUIRED"],
        )

    # ------------------------------------------------------------
    # 7. SOURCE ALREADY ADJUSTED?
    # ------------------------------------------------------------

    source_adjusted = (
        source_adjustment.get("official_statement_present")
        is True
        and source_adjustment.get("source_tier")
        == "TIER_1"
        and source_adjustment.get("source_type")
        in {
            "FINRA",
            "SEC_FILING",
            "OFFICIAL_EXCHANGE_NOTICE",
            "ISSUER_INVESTOR_RELATIONS",
        }
        and source_adjustment.get(
            "scope_matches_metric"
        )
        is True
        and source_adjustment.get(
            "scope_matches_settlement_window"
        )
        is True
    )

    if source_adjusted:
        return {
            "case": case_name,
            "corporate_action_status": "VERIFIED_ACTION",
            "reconciliation_status": "SOURCE_ADJUSTED",
            "identity_continuity_status": identity_status,
            "source_adjustment_status": "SOURCE_ADJUSTED",
            "adjustment_status":
                "SOURCE_ALREADY_ADJUSTED",
            "adjustment_authorized": False,
            "adjustment_factor": None,
            "analytically_usable": True,
            "reason":
                "VERIFIED_ACTION_ALREADY_ADJUSTED_BY_AUTHORITATIVE_SOURCE",
            "evidence_summary": {
                "qualified_action_count":
                    len(qualified_actions),
                "authoritative_action_count":
                    len(authoritative_actions),
                "applicable_action_count": 1,
                "action_type": action.get("action_type"),
                "effective_date":
                    action.get("effective_date"),
                "ratio_numerator":
                    action.get("ratio_numerator"),
                "ratio_denominator":
                    action.get("ratio_denominator"),
            },
            "diagnostics": [
                "DOUBLE_ADJUSTMENT_PROHIBITED"
            ],
        }

    # Se existe qualquer alegacao de source adjustment incompleta,
    # nao podemos interpretar silenciosamente como NOT_ADJUSTED.
    any_adjustment_claim = any(
        [
            source_adjustment.get(
                "official_statement_present"
            )
            is True,
            source_adjustment.get(
                "scope_matches_metric"
            )
            is True,
            source_adjustment.get(
                "scope_matches_settlement_window"
            )
            is True,
            bool(source_adjustment.get("source_type")),
            bool(source_adjustment.get("source_tier")),
        ]
    )

    if any_adjustment_claim:
        return blocked_result(
            case_name,
            "SOURCE_ADJUSTMENT_STATUS_UNRESOLVED",
            identity_status,
            ["INCOMPLETE_SOURCE_ADJUSTMENT_EVIDENCE"],
        )

    # ------------------------------------------------------------
    # 8. VERIFIED ACTION — ADJUSTMENT REQUIRED
    # ------------------------------------------------------------

    # ------------------------------------------------------------
    # 8. VERIFIED ACTION — ADJUSTMENT REQUIRED
    # ------------------------------------------------------------

    short_interest = case.get("short_interest")

    if not isinstance(short_interest, dict):
        return blocked_result(
            case_name,
            "SHORT_INTEREST_VALUES_REQUIRED_FOR_ADJUSTMENT",
            identity_status,
            ["SHORT_INTEREST_DATA_MISSING_OR_INVALID"],
        )

    previous_raw = short_interest.get("previous_raw")
    current_raw = short_interest.get("current_raw")

    try:
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

    except ReconciliationError as exc:
        return blocked_result(
            case_name,
            "SHORT_INTEREST_ADJUSTMENT_CALCULATION_BLOCKED",
            identity_status,
            [str(exc)],
        )

    return {
        "case": case_name,
        "corporate_action_status": "VERIFIED_ACTION",
        "reconciliation_status": "VERIFIED_ACTION",
        "identity_continuity_status": identity_status,
        "source_adjustment_status": "NOT_ADJUSTED",
        "adjustment_status": "REQUIRED",
        "adjustment_authorized": True,
        "adjustment_factor": factor,

        # Raw facts are preserved.
        "previous_raw": float(previous_raw),
        "previous_adjusted": previous_adjusted,
        "current_raw": float(current_raw),
        "adjusted_change_pct": adjusted_change_pct,

        "analytically_usable": True,
        "reason":
            "VERIFIED_ACTION_REQUIRES_DETERMINISTIC_ADJUSTMENT",

        "evidence_summary": {
            "qualified_action_count":
                len(qualified_actions),
            "authoritative_action_count":
                len(authoritative_actions),
            "applicable_action_count": 1,
            "action_type": action.get("action_type"),
            "effective_date":
                action.get("effective_date"),
            "ratio_numerator":
                action.get("ratio_numerator"),
            "ratio_denominator":
                action.get("ratio_denominator"),
            "adjustment_basis":
                "CURRENT_SETTLEMENT_BASIS",
            "adjusted_snapshot":
                "PREVIOUS_SETTLEMENT",
        },

        "diagnostics": [],
    }

def compare_value(
    field: str,
    actual: Any,
    expected: Any,
) -> str | None:

    if isinstance(expected, float):
        if not isinstance(actual, (int, float)):
            return (
                f"{field}: esperado {expected!r}, "
                f"recebido {actual!r}"
            )

        if not math.isclose(
            float(actual),
            expected,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            return (
                f"{field}: esperado {expected!r}, "
                f"recebido {actual!r}"
            )

        return None

    if actual != expected:
        return (
            f"{field}: esperado {expected!r}, "
            f"recebido {actual!r}"
        )

    return None


def validate_expected(
    result: dict[str, Any],
    expected: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    fields = [
    "corporate_action_status",
    "reconciliation_status",
    "identity_continuity_status",
    "source_adjustment_status",
    "adjustment_status",
    "adjustment_authorized",
    "adjustment_factor",
    "previous_raw",
    "previous_adjusted",
    "current_raw",
    "adjusted_change_pct",
    "analytically_usable",
    "reason",
]

    for field in fields:
        error = compare_value(
            field,
            result.get(field),
            expected.get(field),
        )

        if error:
            errors.append(error)

    return errors


def run_cases(
    policy: dict[str, Any],
    fixture: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:

    common = fixture.get("common")
    cases = fixture.get("cases")

    if not isinstance(common, dict):
        raise ReconciliationError(
            "Fixtures: common deve ser objeto."
        )

    if not isinstance(cases, list):
        raise ReconciliationError(
            "Fixtures: cases deve ser lista."
        )

    results: list[dict[str, Any]] = []
    failures = 0

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST CORPORATE ACTION RECONCILER")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    for index, case in enumerate(cases, start=1):

        if not isinstance(case, dict):
            failures += 1
            print("-" * 72)
            print(f"TESTE {index}: INVALID_CASE")
            print("RESULTADO: FAIL")
            continue

        case_name = str(case.get("case") or "UNKNOWN")

        print("-" * 72)
        print(f"TESTE {index}: {case_name}")

        result = reconcile_case(
            case,
            common,
            policy,
        )

        expected = case.get("expected")

        if not isinstance(expected, dict):
            errors = ["expected ausente ou invalido"]
        else:
            errors = validate_expected(
                result,
                expected,
            )

        result["test_passed"] = not errors
        result["test_errors"] = errors

        results.append(result)

        if errors:
            failures += 1
            print("RESULTADO: FAIL")

            for error in errors:
                print("  -", error)

        else:
            print("RESULTADO: PASS")

        print(
            "Reconciliation:",
            result.get("reconciliation_status"),
        )
        print(
            "Adjustment:",
            result.get("adjustment_status"),
        )
        print(
            "Authorized:",
            result.get("adjustment_authorized"),
        )
        print(
            "Factor:",
            result.get("adjustment_factor"),
        )
        print(
            "Usable:",
            result.get("analytically_usable"),
        )

    return results, failures


def validate_contract_versions(
    policy: dict[str, Any],
    fixture: dict[str, Any],
) -> None:

    if policy.get("policy_version") != "3.4D.2-B.2C.1":
        raise ReconciliationError(
            "Policy version inesperada: "
            f"{policy.get('policy_version')!r}"
        )

    if (
        fixture.get("test_contract_version")
        != "3.4D.2-B.2C.1"
    ):
        raise ReconciliationError(
            "Fixture contract version inesperada: "
            f"{fixture.get('test_contract_version')!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Executa reconciliacao controlada de "
            "Corporate Actions para Short Interest."
        )
    )

    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY,
    )

    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES,
    )

    args = parser.parse_args()

    try:
        policy = read_json(args.policy)
        fixture = read_json(args.cases)

        validate_contract_versions(
            policy,
            fixture,
        )

        results, failures = run_cases(
            policy,
            fixture,
        )

    except ReconciliationError as exc:
        print("ERRO OPERACIONAL:", exc)
        return 2

    print("=" * 72)
    print("RESUMO")
    print("=" * 72)
    print("Total :", len(results))
    print("PASS  :", len(results) - failures)
    print("FAIL  :", failures)

    if failures:
        print("RESULTADO FINAL: REPROVADO")
        return 1

    print("RESULTADO FINAL: APROVADO")
    return 0


if __name__ == "__main__":
    sys.exit(main())