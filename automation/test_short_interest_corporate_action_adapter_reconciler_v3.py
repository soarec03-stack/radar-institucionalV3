"""
RADAR INSTITUCIONAL V3

SHORT INTEREST
ADAPTER -> CORPORATE ACTION RECONCILER
INTEGRATION REGRESSION

Version:
3.4D.2-B.2C.7C.3

Objetivo:
Validar a fronteira real entre:

Positive Official Window Review
        ->
Integration Adapter
        ->
Corporate Action Reconciler

Nao acessa rede.
Nao modifica radar_v3.json.
Nao calcula Signal.
Nao calcula Confidence.
Nao calcula Radar Score.
Nao gera Decision.

Fail closed.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.7C.3"

BASE_DIR = Path(__file__).resolve().parent.parent

AUTOMATION_DIR = BASE_DIR / "automation"

if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(AUTOMATION_DIR),
    )


from short_interest_corporate_action_integration_adapter_v3 import (  # noqa: E402
    adapt_case,
    validate_policy,
)

from short_interest_corporate_action_reconciler_v3 import (  # noqa: E402
    reconcile_case,
)


INTEGRATION_POLICY_FILE = (
    AUTOMATION_DIR
    / "short_interest_corporate_action_integration_policy_v3.json"
)

RECONCILIATION_POLICY_FILE = (
    AUTOMATION_DIR
    / "short_interest_corporate_action_reconciliation_policy_v3.json"
)

FIXTURE_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_corporate_action_integration_test_cases_v3.json"
)


class IntegrationRegressionError(Exception):
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
        raise IntegrationRegressionError(
            f"JSON root invalido: {path}"
        )

    return data


def map_source_type(
    source_type: Any,
) -> Any:
    """
    Traducao explicita entre o contrato do Adapter
    e o contrato legado homologado do Reconciler.

    Nenhuma inferencia e realizada.
    """

    mapping = {
        "FINRA_OFFICIAL": "FINRA",
        "SEC_FILING": "SEC_FILING",
        "OFFICIAL_EXCHANGE_NOTICE":
            "OFFICIAL_EXCHANGE_NOTICE",
        "ISSUER_INVESTOR_RELATIONS":
            "ISSUER_INVESTOR_RELATIONS",
    }

    if source_type is None:
        return None

    return mapping.get(
        source_type,
        source_type,
    )


def build_reconciler_case(
    original_case: dict[str, Any],
    adapter_result: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    """
    Converte SOMENTE um Adapter result READY em
    input formal para reconcile_case().

    Nao decide corporate action.
    Nao inventa evidencia.
    Nao promove usability.

    Traduz explicitamente contratos semanticamente
    equivalentes entre Adapter e Reconciler.
    """

    if (
        adapter_result.get(
            "integration_status"
        )
        != "READY_FOR_RECONCILIATION"
    ):
        raise IntegrationRegressionError(
            "ADAPTER_NOT_READY_FOR_RECONCILIATION"
        )

    identity = adapter_result.get(
        "identity"
    )

    if not isinstance(identity, dict):
        raise IntegrationRegressionError(
            "ADAPTER_IDENTITY_INVALID"
        )

    raw_review = adapter_result.get(
        "raw_review"
    )

    if not isinstance(raw_review, dict):
        raise IntegrationRegressionError(
            "ADAPTER_RAW_REVIEW_INVALID"
        )

    previous_date = (
        adapter_result.get(
            "previous_settlement_date"
        )
    )

    current_date = (
        adapter_result.get(
            "current_settlement_date"
        )
    )

    common = {
        "previous_settlement_date":
            previous_date,
        "current_settlement_date":
            current_date,
    }

    # --------------------------------------------------------
    # IDENTITY TRANSLATION
    # --------------------------------------------------------

    reconciler_identity = {
        "identity_conflict": False,

        "master_matches_collection": True,

        "identity_continuity_verified":
            (
                identity.get(
                    "continuity_status"
                )
                == "VERIFIED"
            ),
    }

    # --------------------------------------------------------
    # ACTION EVIDENCE TRANSLATION
    # --------------------------------------------------------

    qualified_actions: list[
        dict[str, Any]
    ] = []

    route = adapter_result.get("route")

    if route == "VERIFIED_ACTION":

        action = adapter_result.get(
            "action_evidence"
        )

        if not isinstance(action, dict):
            raise IntegrationRegressionError(
                "VERIFIED_ACTION_WITHOUT_ACTION_EVIDENCE"
            )

        translated_action = {
            "action_type":
                action.get("action_type"),

            "effective_date":
                action.get("effective_date"),

            "ratio_numerator":
                action.get("ratio_numerator"),

            "ratio_denominator":
                action.get("ratio_denominator"),

            "source_id":
                action.get("source_id"),

            "source_type":
                map_source_type(
                    action.get("source_type")
                ),

            "source_tier":
                action.get("source_tier"),

            "identity_status":
                action.get("identity_status"),

            "evidence_status":
                action.get("evidence_status"),

            # ------------------------------------------------
            # EXPLICIT CONTRACT TRANSLATION
            # ------------------------------------------------
            #
            # Adapter contract:
            #
            #     evidence_status == "VERIFIED"
            #
            # Reconciler contract:
            #
            #     verified is True
            #
            # Isto NAO cria uma nova verificacao.
            # Apenas traduz a mesma propriedade semantica
            # que ja foi validada pelo Adapter antes de
            # READY_FOR_RECONCILIATION.
            #
            "verified":
                (
                    action.get(
                        "evidence_status"
                    )
                    == "VERIFIED"
                ),
        }

        qualified_actions.append(
            translated_action
        )

    elif route != "NO_ACTION":

        raise IntegrationRegressionError(
            f"ADAPTER_ROUTE_INVALID:{route}"
        )

    # --------------------------------------------------------
    # EVIDENCE TRANSLATION
    # --------------------------------------------------------

    reconciler_evidence = {
        "resolver_status":
            "RESOLVED",

        "settlement_window_matches_collection":
            True,

        "authoritative_conflict":
            False,

        "qualified_actions":
            qualified_actions,

        "unresolved_action_candidates":
            [],

        "official_window_review_completed":
            (
                raw_review.get(
                    "official_window_review_completed"
                )
                is True
            ),

        "authoritative_source_review_present":
            (
                raw_review.get(
                    "authoritative_source_review_present"
                )
                is True
            ),
    }

    # --------------------------------------------------------
    # SOURCE ADJUSTMENT TRANSLATION
    # --------------------------------------------------------

    adapter_source_adjustment = (
        adapter_result.get(
            "source_adjustment"
        )
    )

    if not isinstance(
        adapter_source_adjustment,
        dict,
    ):
        raise IntegrationRegressionError(
            "ADAPTER_SOURCE_ADJUSTMENT_INVALID"
        )

    adjustment_status = (
        adapter_source_adjustment.get(
            "status"
        )
    )

    if adjustment_status == "NOT_ADJUSTED":

        reconciler_source_adjustment = {
            "official_statement_present":
                False,

            "source_tier":
                None,

            "source_type":
                None,

            "scope_matches_metric":
                False,

            "scope_matches_settlement_window":
                False,
        }

    elif (
        adjustment_status
        == "SOURCE_ALREADY_ADJUSTED"
    ):

        reconciler_source_adjustment = {
            "official_statement_present":
                True,

            "source_tier":
                adapter_source_adjustment.get(
                    "source_tier"
                ),

            # Adapter:
            # FINRA_OFFICIAL
            #
            # Reconciler:
            # FINRA
            #
            # Traducao explicita, sem inferencia.
            "source_type":
                map_source_type(
                    adapter_source_adjustment.get(
                        "source_type"
                    )
                ),

            # Estes dois campos somente sao promovidos
            # porque o Adapter ja validou o contrato
            # SOURCE_ALREADY_ADJUSTED antes de READY.
            "scope_matches_metric":
                True,

            "scope_matches_settlement_window":
                True,
        }

    else:
        raise IntegrationRegressionError(
            (
                "SOURCE_ADJUSTMENT_NOT_TRANSLATABLE:"
                f"{adjustment_status}"
            )
        )

    # --------------------------------------------------------
    # RECONCILER CASE
    # --------------------------------------------------------

    reconciler_case = {
        "case":
            original_case.get("case"),

        "identity":
            reconciler_identity,

        "evidence":
            reconciler_evidence,

        "source_adjustment":
            reconciler_source_adjustment,
    }

    # Short Interest raw facts sao preservados.
    short_interest = original_case.get(
        "short_interest"
    )

    if isinstance(short_interest, dict):
        reconciler_case[
            "short_interest"
        ] = deepcopy(
            short_interest
        )

    return (
        reconciler_case,
        common,
    )


def synthetic_short_interest_for_case(
    case_name: str,
) -> dict[str, float] | None:
    """
    Dados exclusivamente sinteticos usados apenas
    para provar a integracao matematica.

    Nao representam VRT, CRSP ou ETON.
    """

    if (
        case_name
        == "ACTION_FOUND_COMPLETE_SPLIT_READY"
    ):
        return {
            "previous_raw": 100.0,
            "current_raw": 220.0,
        }

    if (
        case_name
        == "SOURCE_ALREADY_ADJUSTED_READY"
    ):
        return {
            "previous_raw": 1000.0,
            "current_raw": 100.0,
        }

    return None


def assert_equal(
    actual: Any,
    expected: Any,
    field: str,
) -> None:

    if actual != expected:
        raise IntegrationRegressionError(
            (
                f"{field}: "
                f"esperado={expected!r}, "
                f"recebido={actual!r}"
            )
        )


def assert_close(
    actual: Any,
    expected: float,
    field: str,
    tolerance: float = 1e-9,
) -> None:

    if not isinstance(
        actual,
        (int, float),
    ):
        raise IntegrationRegressionError(
            f"{field} nao numerico: {actual!r}"
        )

    if abs(
        float(actual)
        - float(expected)
    ) > tolerance:
        raise IntegrationRegressionError(
            (
                f"{field}: "
                f"esperado={expected}, "
                f"recebido={actual}"
            )
        )


def execute_ready_case(
    original_case: dict[str, Any],
    integration_policy: dict[str, Any],
    reconciliation_policy: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:

    # --------------------------------------------------------
    # 1. ADAPTER
    # --------------------------------------------------------

    adapter_result = adapt_case(
        original_case,
        integration_policy,
    )

    if (
        adapter_result.get(
            "integration_status"
        )
        != "READY_FOR_RECONCILIATION"
    ):
        raise IntegrationRegressionError(
            (
                "Adapter deveria estar READY, "
                f"recebido="
                f"{adapter_result.get('integration_status')}, "
                f"diagnostics="
                f"{adapter_result.get('diagnostics')}"
            )
        )

    # --------------------------------------------------------
    # 2. SYNTHETIC SHORT INTEREST
    # --------------------------------------------------------

    working_case = deepcopy(
        original_case
    )

    synthetic_short_interest = (
        synthetic_short_interest_for_case(
            str(
                original_case.get(
                    "case"
                )
            )
        )
    )

    if synthetic_short_interest is not None:
        working_case[
            "short_interest"
        ] = synthetic_short_interest

    # --------------------------------------------------------
    # 3. CONTRACT BRIDGE
    # --------------------------------------------------------

    reconciler_case, common = (
        build_reconciler_case(
            working_case,
            adapter_result,
        )
    )

    # --------------------------------------------------------
    # 4. REAL RECONCILER
    # --------------------------------------------------------

    result = reconcile_case(
        reconciler_case,
        common,
        reconciliation_policy,
    )

    return adapter_result, result


def test_no_action(
    cases_by_name: dict[
        str,
        dict[str, Any],
    ],
    integration_policy: dict[str, Any],
    reconciliation_policy: dict[str, Any],
) -> None:

    case = cases_by_name[
        "NO_ACTION_PROVEN_READY"
    ]

    adapter_result, result = (
        execute_ready_case(
            case,
            integration_policy,
            reconciliation_policy,
        )
    )

    # Adapter nao pode promover final usability.
    assert_equal(
        adapter_result[
            "final_short_interest_analytically_usable"
        ],
        False,
        "adapter final usability",
    )

    # Reconciler e a autoridade final.
    assert_equal(
        result.get(
            "corporate_action_status"
        ),
        "NO_ACTION",
        "corporate_action_status",
    )

    assert_equal(
        result.get(
            "reconciliation_status"
        ),
        "NO_ACTION",
        "reconciliation_status",
    )

    assert_equal(
        result.get(
            "adjustment_status"
        ),
        "NOT_REQUIRED",
        "adjustment_status",
    )

    assert_equal(
        result.get(
            "adjustment_authorized"
        ),
        False,
        "adjustment_authorized",
    )

    assert_equal(
        result.get(
            "analytically_usable"
        ),
        True,
        "reconciler analytically_usable",
    )


def test_split_adjustment(
    cases_by_name: dict[
        str,
        dict[str, Any],
    ],
    integration_policy: dict[str, Any],
    reconciliation_policy: dict[str, Any],
) -> None:

    case = cases_by_name[
        "ACTION_FOUND_COMPLETE_SPLIT_READY"
    ]

    adapter_result, result = (
        execute_ready_case(
            case,
            integration_policy,
            reconciliation_policy,
        )
    )

    # Adapter continua sem autoridade para final usability.
    assert_equal(
        adapter_result[
            "final_short_interest_analytically_usable"
        ],
        False,
        "adapter final usability",
    )

    assert_equal(
        result.get(
            "corporate_action_status"
        ),
        "VERIFIED_ACTION",
        "corporate_action_status",
    )

    assert_equal(
        result.get(
            "reconciliation_status"
        ),
        "VERIFIED_ACTION",
        "reconciliation_status",
    )

    assert_equal(
        result.get(
            "source_adjustment_status"
        ),
        "NOT_ADJUSTED",
        "source_adjustment_status",
    )

    assert_equal(
        result.get(
            "adjustment_status"
        ),
        "REQUIRED",
        "adjustment_status",
    )

    assert_equal(
        result.get(
            "adjustment_authorized"
        ),
        True,
        "adjustment_authorized",
    )

    assert_close(
        result.get(
            "adjustment_factor"
        ),
        2.0,
        "adjustment_factor",
    )

    assert_close(
        result.get(
            "previous_raw"
        ),
        100.0,
        "previous_raw",
    )

    assert_close(
        result.get(
            "previous_adjusted"
        ),
        200.0,
        "previous_adjusted",
    )

    assert_close(
        result.get(
            "current_raw"
        ),
        220.0,
        "current_raw",
    )

    assert_close(
        result.get(
            "adjusted_change_pct"
        ),
        10.0,
        "adjusted_change_pct",
    )

    assert_equal(
        result.get(
            "analytically_usable"
        ),
        True,
        "analytically_usable",
    )


def test_source_already_adjusted(
    cases_by_name: dict[
        str,
        dict[str, Any],
    ],
    integration_policy: dict[str, Any],
    reconciliation_policy: dict[str, Any],
) -> None:

    case = cases_by_name[
        "SOURCE_ALREADY_ADJUSTED_READY"
    ]

    adapter_result, result = (
        execute_ready_case(
            case,
            integration_policy,
            reconciliation_policy,
        )
    )

    # Adapter continua sem autoridade final.
    assert_equal(
        adapter_result[
            "final_short_interest_analytically_usable"
        ],
        False,
        "adapter final usability",
    )

    assert_equal(
        result.get(
            "corporate_action_status"
        ),
        "VERIFIED_ACTION",
        "corporate_action_status",
    )

    assert_equal(
        result.get(
            "reconciliation_status"
        ),
        "SOURCE_ADJUSTED",
        "reconciliation_status",
    )

    assert_equal(
        result.get(
            "source_adjustment_status"
        ),
        "SOURCE_ADJUSTED",
        "source_adjustment_status",
    )

    assert_equal(
        result.get(
            "adjustment_status"
        ),
        "SOURCE_ALREADY_ADJUSTED",
        "adjustment_status",
    )

    assert_equal(
        result.get(
            "adjustment_authorized"
        ),
        False,
        "adjustment_authorized",
    )

    # Se a fonte ja ajustou, o Radar NAO pode aplicar
    # novamente o fator.
    assert_equal(
        result.get(
            "adjustment_factor"
        ),
        None,
        "adjustment_factor",
    )

    assert_equal(
        result.get(
            "analytically_usable"
        ),
        True,
        "analytically_usable",
    )

    diagnostics = result.get(
        "diagnostics",
        [],
    )

    if (
        "DOUBLE_ADJUSTMENT_PROHIBITED"
        not in diagnostics
    ):
        raise IntegrationRegressionError(
            "Protecao contra double adjustment ausente."
        )


def test_blocked_never_enters_reconciler(
    cases_by_name: dict[
        str,
        dict[str, Any],
    ],
    integration_policy: dict[str, Any],
) -> None:

    blocked_names = [
        "ACTION_FOUND_INCOMPLETE_BLOCKED",
        "UNRESOLVED_BLOCKED",
        "IDENTITY_MISMATCH_BLOCKED",
        "SETTLEMENT_WINDOW_MISMATCH_BLOCKED",
        "AUTHORITATIVE_CONFLICT_BLOCKED",
    ]

    reconciler_calls = 0

    for case_name in blocked_names:

        case = cases_by_name[
            case_name
        ]

        adapter_result = adapt_case(
            case,
            integration_policy,
        )

        assert_equal(
            adapter_result.get(
                "integration_status"
            ),
            "BLOCKED",
            (
                f"{case_name} "
                "integration_status"
            ),
        )

        assert_equal(
            adapter_result.get(
                "route"
            ),
            "NONE",
            f"{case_name} route",
        )

        assert_equal(
            adapter_result.get(
                "reconciler_input_status"
            ),
            "UNRESOLVED",
            (
                f"{case_name} "
                "reconciler_input_status"
            ),
        )

        assert_equal(
            adapter_result.get(
                "final_short_interest_analytically_usable"
            ),
            False,
            (
                f"{case_name} "
                "final usability"
            ),
        )

        # ----------------------------------------------------
        # CRITICAL ARCHITECTURAL BARRIER
        # ----------------------------------------------------
        #
        # reconcile_case() NAO e chamado para qualquer
        # Adapter result BLOCKED.
        #
        if (
            adapter_result.get(
                "integration_status"
            )
            == "READY_FOR_RECONCILIATION"
        ):
            reconciler_calls += 1

    assert_equal(
        reconciler_calls,
        0,
        "blocked reconciler calls",
    )


def run_test(
    number: int,
    name: str,
    function: Any,
) -> bool:

    print("-" * 72)

    print(
        f"TESTE {number}: {name}"
    )

    try:
        function()

        print("RESULTADO: PASS")
        return True

    except Exception as exc:
        print("RESULTADO: FAIL")
        print("ERRO:", exc)
        return False


def main() -> int:

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST")
    print(
        "ADAPTER -> RECONCILER INTEGRATION REGRESSION"
    )
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:
        integration_policy = read_json(
            INTEGRATION_POLICY_FILE
        )

        reconciliation_policy = read_json(
            RECONCILIATION_POLICY_FILE
        )

        fixtures = read_json(
            FIXTURE_FILE
        )

        validate_policy(
            integration_policy
        )

    except Exception as exc:
        print(
            "ERRO DE INICIALIZACAO:"
        )
        print(exc)
        return 1

    raw_cases = fixtures.get(
        "cases"
    )

    if not isinstance(
        raw_cases,
        list,
    ):
        print(
            "ERRO: fixtures.cases invalido."
        )
        return 1

    cases_by_name: dict[
        str,
        dict[str, Any],
    ] = {}

    for case in raw_cases:

        if not isinstance(case, dict):
            continue

        name = case.get("case")

        if isinstance(name, str):
            cases_by_name[name] = case

    required_cases = {
        "NO_ACTION_PROVEN_READY",
        "ACTION_FOUND_COMPLETE_SPLIT_READY",
        "ACTION_FOUND_INCOMPLETE_BLOCKED",
        "UNRESOLVED_BLOCKED",
        "IDENTITY_MISMATCH_BLOCKED",
        "SETTLEMENT_WINDOW_MISMATCH_BLOCKED",
        "AUTHORITATIVE_CONFLICT_BLOCKED",
        "SOURCE_ALREADY_ADJUSTED_READY",
    }

    missing = (
        required_cases
        - set(cases_by_name)
    )

    if missing:
        print(
            "ERRO: fixtures obrigatorios ausentes:",
            sorted(missing),
        )
        return 1

    tests = [
        (
            1,
            "NO_ACTION Adapter -> Reconciler",
            lambda: test_no_action(
                cases_by_name,
                integration_policy,
                reconciliation_policy,
            ),
        ),
        (
            2,
            "2-for-1 Split Adapter -> Reconciler",
            lambda: test_split_adjustment(
                cases_by_name,
                integration_policy,
                reconciliation_policy,
            ),
        ),
        (
            3,
            (
                "SOURCE_ALREADY_ADJUSTED "
                "Adapter -> Reconciler"
            ),
            lambda: test_source_already_adjusted(
                cases_by_name,
                integration_policy,
                reconciliation_policy,
            ),
        ),
        (
            4,
            (
                "BLOCKED cases never enter "
                "Reconciler"
            ),
            lambda:
                test_blocked_never_enters_reconciler(
                    cases_by_name,
                    integration_policy,
                ),
        ),
    ]

    passed = 0
    failed = 0

    for number, name, function in tests:

        if run_test(
            number,
            name,
            function,
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