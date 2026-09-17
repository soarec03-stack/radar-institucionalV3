"""
RADAR INSTITUCIONAL V3

SHORT INTEREST
POSITIVE OFFICIAL WINDOW REVIEW ENGINE

Version:
3.4D.2-B.2C.7B

Objetivo:
avaliar evidencia positiva oficial para determinar se a janela
economica entre dois settlements de Short Interest pode ser
classificada como NO_ACTION_PROVEN.

Nesta versao:
- usa somente fixtures sinteticos;
- nao acessa rede;
- nao acessa SEC;
- nao acessa FINRA;
- nao altera radar;
- nao gera Signal;
- nao gera Confidence;
- nao gera Score;
- nao gera Decision.

Fail closed.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.7B"

BASE_DIR = Path(__file__).resolve().parent.parent

POLICY_FILE = (
    BASE_DIR
    / "automation"
    / "short_interest_positive_official_window_review_policy_v3.json"
)

FIXTURE_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_positive_official_window_review_test_cases_v3.json"
)


class ReviewError(Exception):
    pass


class TestFailure(Exception):
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
        raise ReviewError(
            f"JSON root invalido: {path}"
        )

    return data


def parse_date(
    value: Any,
) -> date:

    if not isinstance(value, str):
        raise ReviewError(
            "Settlement date deve ser string ISO."
        )

    try:
        return date.fromisoformat(value)

    except ValueError as exc:
        raise ReviewError(
            f"Data ISO invalida: {value}"
        ) from exc


def unresolved_result(
    case: dict[str, Any],
    diagnostics: list[str],
    *,
    official_window_review_completed: bool = False,
    authoritative_source_review_present: bool = False,
    economic_window_reviewed: bool = False,
    identity_continuity_verified: bool = False,
    no_qualified_action_in_economic_window: bool = False,
    no_unresolved_action_candidate_affecting_window: bool = False,
    no_authoritative_evidence_conflict: bool = False,
    minimum_authoritative_reviews_satisfied: bool = False,
) -> dict[str, Any]:

    return {
        "case": case.get("case"),
        "ticker": case.get("ticker"),

        "previous_settlement_date":
            case.get("previous_settlement_date"),

        "current_settlement_date":
            case.get("current_settlement_date"),

        "economic_window": {
            "previous_exclusive":
                case.get("previous_settlement_date"),
            "current_inclusive":
                case.get("current_settlement_date"),
        },

        "identity_continuity_status":
            (
                case.get("identity", {})
                .get("continuity_status", "UNRESOLVED")
            ),

        "official_window_review_completed":
            official_window_review_completed,

        "authoritative_source_review_present":
            authoritative_source_review_present,

        "economic_window_reviewed":
            economic_window_reviewed,

        "identity_continuity_verified":
            identity_continuity_verified,

        "no_qualified_action_in_economic_window":
            no_qualified_action_in_economic_window,

        "no_unresolved_action_candidate_affecting_window":
            no_unresolved_action_candidate_affecting_window,

        "no_authoritative_evidence_conflict":
            no_authoritative_evidence_conflict,

        "minimum_authoritative_reviews_satisfied":
            minimum_authoritative_reviews_satisfied,

        "review_status": "UNRESOLVED",
        "corporate_action_status": "UNRESOLVED",
        "reconciliation_eligible": False,
        "analytically_usable": False,

        "authoritative_reviews":
            case.get("authoritative_reviews", []),

        "evidence_summary": {
            "sec_resolver":
                case.get("sec_resolver", {})
        },

        "diagnostics": diagnostics,
    }


def validate_identity(
    case: dict[str, Any],
) -> bool:

    identity = case.get("identity")

    if not isinstance(identity, dict):
        return False

    ticker = identity.get("ticker")
    exchange = identity.get("listing_exchange")
    security_identity = identity.get(
        "security_identity"
    )

    if not all(
        isinstance(value, str)
        and value.strip()
        for value in (
            ticker,
            exchange,
            security_identity,
        )
    ):
        return False

    if ticker != case.get("ticker"):
        return False

    return (
        identity.get("continuity_status")
        == "VERIFIED"
    )


def review_matches_window(
    review: dict[str, Any],
    previous: str,
    current: str,
) -> bool:

    return (
        review.get("previous_settlement_date")
        == previous
        and
        review.get("current_settlement_date")
        == current
    )


def is_authoritative_review(
    review: dict[str, Any],
    policy: dict[str, Any],
) -> bool:

    if review.get("source_tier") != "TIER_1":
        return False

    allowed = set(
        policy[
            "authoritative_sources"
        ][
            "allowed_primary_source_types"
        ]
    )

    if review.get("source_type") not in allowed:
        return False

    required_fields = (
        policy[
            "positive_no_action_evidence"
        ][
            "review_record_required_fields"
        ]
    )

    for field in required_fields:
        value = review.get(field)

        if value is None:
            return False

        if (
            isinstance(value, str)
            and not value.strip()
        ):
            return False

    return True


def evaluate_case(
    case: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:

    diagnostics: list[str] = []

    # --------------------------------------------------------
    # 1. Settlement window
    # --------------------------------------------------------

    previous_value = case.get(
        "previous_settlement_date"
    )

    current_value = case.get(
        "current_settlement_date"
    )

    try:
        previous_date = parse_date(
            previous_value
        )
        current_date = parse_date(
            current_value
        )

    except ReviewError as exc:
        return unresolved_result(
            case,
            [str(exc)],
        )

    if current_date <= previous_date:
        return unresolved_result(
            case,
            [
                "CURRENT_SETTLEMENT_NOT_AFTER_PREVIOUS"
            ],
        )

    # --------------------------------------------------------
    # 2. Identity
    # --------------------------------------------------------

    identity_verified = validate_identity(
        case
    )

    if not identity_verified:
        return unresolved_result(
            case,
            ["IDENTITY_NOT_VERIFIED"],
            identity_continuity_verified=False,
        )

    # --------------------------------------------------------
    # 3. SEC resolver evidence
    # --------------------------------------------------------

    resolver = case.get("sec_resolver")

    if not isinstance(resolver, dict):
        return unresolved_result(
            case,
            ["SEC_RESOLVER_INPUT_MISSING"],
            identity_continuity_verified=True,
        )

    qualified_count = resolver.get(
        "qualified_evidence_count"
    )

    unresolved_count = resolver.get(
        "unresolved_candidate_count"
    )

    if (
        not isinstance(qualified_count, int)
        or isinstance(qualified_count, bool)
        or qualified_count < 0
    ):
        return unresolved_result(
            case,
            [
                "INVALID_QUALIFIED_EVIDENCE_COUNT"
            ],
            identity_continuity_verified=True,
        )

    if (
        not isinstance(unresolved_count, int)
        or isinstance(unresolved_count, bool)
        or unresolved_count < 0
    ):
        return unresolved_result(
            case,
            [
                "INVALID_UNRESOLVED_CANDIDATE_COUNT"
            ],
            identity_continuity_verified=True,
        )

    no_qualified_action = (
        qualified_count == 0
    )

    no_unresolved_candidate = (
        unresolved_count == 0
    )

    # --------------------------------------------------------
    # 4. Review records
    # --------------------------------------------------------

    reviews = case.get(
        "authoritative_reviews"
    )

    if not isinstance(reviews, list):
        return unresolved_result(
            case,
            ["AUTHORITATIVE_REVIEWS_INVALID"],
            identity_continuity_verified=True,
            no_qualified_action_in_economic_window=
                no_qualified_action,
            no_unresolved_action_candidate_affecting_window=
                no_unresolved_candidate,
        )

    authoritative_reviews = [
        review
        for review in reviews
        if isinstance(review, dict)
        and is_authoritative_review(
            review,
            policy,
        )
    ]

    authoritative_present = bool(
        authoritative_reviews
    )

    window_reviews = [
        review
        for review in authoritative_reviews
        if review_matches_window(
            review,
            previous_value,
            current_value,
        )
    ]

    economic_window_reviewed = bool(
        window_reviews
    )

    minimum_required = int(
        policy[
            "positive_no_action_evidence"
        ][
            "minimum_authoritative_reviews"
        ]
    )

    minimum_satisfied = (
        len(window_reviews)
        >= minimum_required
    )

    if not authoritative_present:
        return unresolved_result(
            case,
            ["MISSING_AUTHORITATIVE_SOURCE"],
            identity_continuity_verified=True,
            no_qualified_action_in_economic_window=
                no_qualified_action,
            no_unresolved_action_candidate_affecting_window=
                no_unresolved_candidate,
        )

    if not economic_window_reviewed:
        return unresolved_result(
            case,
            ["ECONOMIC_WINDOW_NOT_REVIEWED"],
            authoritative_source_review_present=True,
            identity_continuity_verified=True,
            no_qualified_action_in_economic_window=
                no_qualified_action,
            no_unresolved_action_candidate_affecting_window=
                no_unresolved_candidate,
        )

    # --------------------------------------------------------
    # 5. Review results / conflicts
    # --------------------------------------------------------

    allowed_results = set(
        policy[
            "positive_no_action_evidence"
        ][
            "allowed_review_results"
        ]
    )

    results: list[str] = []

    for review in window_reviews:
        result = review.get("result")

        if result not in allowed_results:
            return unresolved_result(
                case,
                ["INVALID_REVIEW_RESULT"],
                official_window_review_completed=True,
                authoritative_source_review_present=True,
                economic_window_reviewed=True,
                identity_continuity_verified=True,
                no_qualified_action_in_economic_window=
                    no_qualified_action,
                no_unresolved_action_candidate_affecting_window=
                    no_unresolved_candidate,
                minimum_authoritative_reviews_satisfied=
                    minimum_satisfied,
            )

        results.append(result)

    unique_results = set(results)

    has_no_action_review = (
        "NO_RELEVANT_ACTION_FOUND"
        in unique_results
    )

    has_action_review = (
        "RELEVANT_ACTION_FOUND"
        in unique_results
    )

    has_unresolved_review = bool(
        unique_results.intersection(
            {
                "UNRESOLVED",
                "SOURCE_UNAVAILABLE",
                "CONFLICT",
            }
        )
    )

    authoritative_conflict = (
        has_no_action_review
        and has_action_review
    ) or (
        "CONFLICT" in unique_results
    )

    no_authoritative_conflict = (
        not authoritative_conflict
    )

    # --------------------------------------------------------
    # 6. Conflict always fails closed
    # --------------------------------------------------------

    if authoritative_conflict:
        return unresolved_result(
            case,
            [
                "AUTHORITATIVE_EVIDENCE_CONFLICT"
            ],
            official_window_review_completed=True,
            authoritative_source_review_present=True,
            economic_window_reviewed=True,
            identity_continuity_verified=True,
            no_qualified_action_in_economic_window=
                no_qualified_action,
            no_unresolved_action_candidate_affecting_window=
                no_unresolved_candidate,
            no_authoritative_evidence_conflict=False,
            minimum_authoritative_reviews_satisfied=
                minimum_satisfied,
        )

    # --------------------------------------------------------
    # 7. Unresolved candidate/review fails closed
    # --------------------------------------------------------

    if (
        not no_unresolved_candidate
        or has_unresolved_review
    ):
        return unresolved_result(
            case,
            ["UNRESOLVED_ACTION_CANDIDATE"],
            official_window_review_completed=True,
            authoritative_source_review_present=True,
            economic_window_reviewed=True,
            identity_continuity_verified=True,
            no_qualified_action_in_economic_window=
                no_qualified_action,
            no_unresolved_action_candidate_affecting_window=False,
            no_authoritative_evidence_conflict=
                no_authoritative_conflict,
            minimum_authoritative_reviews_satisfied=
                minimum_satisfied,
        )

    # --------------------------------------------------------
    # 8. Action found
    # --------------------------------------------------------

    if (
        qualified_count > 0
        or has_action_review
    ):

        return {
            "case": case.get("case"),
            "ticker": case.get("ticker"),

            "previous_settlement_date":
                previous_value,

            "current_settlement_date":
                current_value,

            "economic_window": {
                "previous_exclusive":
                    previous_value,
                "current_inclusive":
                    current_value,
            },

            "identity_continuity_status":
                case["identity"][
                    "continuity_status"
                ],

            "official_window_review_completed":
                True,

            "authoritative_source_review_present":
                True,

            "economic_window_reviewed":
                True,

            "identity_continuity_verified":
                True,

            "no_qualified_action_in_economic_window":
                False,

            "no_unresolved_action_candidate_affecting_window":
                True,

            "no_authoritative_evidence_conflict":
                True,

            "minimum_authoritative_reviews_satisfied":
                minimum_satisfied,

            "review_status":
                "ACTION_FOUND",

            "corporate_action_status":
                "VERIFIED_ACTION",

            "reconciliation_eligible":
                True,

            "analytically_usable":
                False,

            "authoritative_reviews":
                window_reviews,

            "evidence_summary": {
                "sec_resolver": resolver,
                "authoritative_review_count":
                    len(window_reviews),
            },

            "diagnostics": [
                "QUALIFIED_SHARE_ADJUSTING_ACTION_FOUND"
            ],
        }

    # --------------------------------------------------------
    # 9. Positive NO_ACTION proof
    # --------------------------------------------------------

    if (
        has_no_action_review
        and no_qualified_action
        and no_unresolved_candidate
        and no_authoritative_conflict
        and minimum_satisfied
    ):

        return {
            "case": case.get("case"),
            "ticker": case.get("ticker"),

            "previous_settlement_date":
                previous_value,

            "current_settlement_date":
                current_value,

            "economic_window": {
                "previous_exclusive":
                    previous_value,
                "current_inclusive":
                    current_value,
            },

            "identity_continuity_status":
                case["identity"][
                    "continuity_status"
                ],

            "official_window_review_completed":
                True,

            "authoritative_source_review_present":
                True,

            "economic_window_reviewed":
                True,

            "identity_continuity_verified":
                True,

            "no_qualified_action_in_economic_window":
                True,

            "no_unresolved_action_candidate_affecting_window":
                True,

            "no_authoritative_evidence_conflict":
                True,

            "minimum_authoritative_reviews_satisfied":
                True,

            "review_status":
                "NO_ACTION_PROVEN",

            "corporate_action_status":
                "NO_ACTION",

            "reconciliation_eligible":
                True,

            "analytically_usable":
                True,

            "authoritative_reviews":
                window_reviews,

            "evidence_summary": {
                "sec_resolver": resolver,
                "authoritative_review_count":
                    len(window_reviews),
            },

            "diagnostics": [],
        }

    # --------------------------------------------------------
    # 10. Everything else fails closed
    # --------------------------------------------------------

    diagnostics.append(
        "INSUFFICIENT_POSITIVE_EVIDENCE"
    )

    return unresolved_result(
        case,
        diagnostics,
        official_window_review_completed=True,
        authoritative_source_review_present=True,
        economic_window_reviewed=True,
        identity_continuity_verified=True,
        no_qualified_action_in_economic_window=
            no_qualified_action,
        no_unresolved_action_candidate_affecting_window=
            no_unresolved_candidate,
        no_authoritative_evidence_conflict=
            no_authoritative_conflict,
        minimum_authoritative_reviews_satisfied=
            minimum_satisfied,
    )


def values_equal(
    actual: Any,
    expected: Any,
) -> bool:

    return actual == expected


def validate_expected(
    result: dict[str, Any],
    expected: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    for field, expected_value in expected.items():

        actual_value = result.get(field)

        if not values_equal(
            actual_value,
            expected_value,
        ):
            errors.append(
                (
                    f"{field}: esperado="
                    f"{expected_value!r}, "
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
        raise ReviewError(
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
            result = evaluate_case(
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

            failed += 1
            continue

        print("RESULTADO: PASS")
        print(
            "Review status:",
            result["review_status"],
        )
        print(
            "Corporate action:",
            result["corporate_action_status"],
        )
        print(
            "Reconciliation eligible:",
            result["reconciliation_eligible"],
        )
        print(
            "Analytically usable:",
            result["analytically_usable"],
        )

        passed += 1

    return passed, failed


def main() -> int:

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST")
    print("POSITIVE OFFICIAL WINDOW REVIEW ENGINE")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:
        policy = read_json(
            POLICY_FILE
        )

        fixtures = read_json(
            FIXTURE_FILE
        )

    except (
        OSError,
        json.JSONDecodeError,
        ReviewError,
    ) as exc:

        print("ERRO DE INICIALIZACAO:")
        print(exc)
        return 1

    if (
        policy.get("version")
        != "3.4D.2-B.2C.7A"
    ):
        print(
            "ERRO: policy version incompatível."
        )
        return 1

    if (
        fixtures.get("contract_version")
        != VERSION
    ):
        print(
            "ERRO: fixture contract version incompatível."
        )
        return 1

    try:
        passed, failed = run_cases(
            fixtures,
            policy,
        )

    except ReviewError as exc:
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
        print("RESULTADO FINAL: REPROVADO")
        return 1

    print("RESULTADO FINAL: APROVADO")
    return 0


if __name__ == "__main__":
    sys.exit(main())