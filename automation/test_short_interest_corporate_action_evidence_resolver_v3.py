"""
RADAR INSTITUCIONAL V3
TESTE DE REGRESSAO
SEC CORPORATE ACTION EVIDENCE RESOLVER

Testa exclusivamente a classificacao semantica do resolver B.2B-R1.

NAO acessa:
- SEC
- FINRA
- Internet

NAO modifica:
- radar_v3.json
- Corporate Action Registry
- Short Interest Collection
- Signal
- Confidence
- Score
- Decision
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path


# Permite executar diretamente a partir da raiz do projeto:
#
# python automation/test_short_interest_corporate_action_evidence_resolver_v3.py
#
AUTOMATION_DIR = Path(__file__).resolve().parent

if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))


from short_interest_corporate_action_evidence_resolver_v3 import classify


PREVIOUS_SETTLEMENT = date(2026, 8, 14)
CURRENT_SETTLEMENT = date(2026, 8, 31)


def fail(message: str) -> None:
    raise AssertionError(message)


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        fail(
            f"{message}\n"
            f"  esperado: {expected!r}\n"
            f"  recebido: {actual!r}"
        )


def assert_true(value, message: str) -> None:
    if value is not True:
        fail(
            f"{message}\n"
            f"  esperado: True\n"
            f"  recebido: {value!r}"
        )


def assert_false(value, message: str) -> None:
    if value is not False:
        fail(
            f"{message}\n"
            f"  esperado: False\n"
            f"  recebido: {value!r}"
        )


def first_match(result: dict) -> dict:
    matches = result.get("text_matches", [])

    if not matches:
        fail("Era esperado pelo menos um text_match.")

    return matches[0]


def run_test(
    number: int,
    name: str,
    function,
) -> bool:

    print("-" * 72)
    print(f"TESTE {number}: {name}")

    try:
        function()

        print("RESULTADO: PASS")
        return True

    except AssertionError as exc:

        print("RESULTADO: FAIL")
        print(exc)
        return False


# ======================================================================
# TESTE 1
#
# Palavra "reclassification" generica.
#
# Nao esta ligada semanticamente a common stock, shares etc.
#
# Esperado:
#
# text_matches_count = 0
# qualified_evidence_count = 0
# ======================================================================

def test_1_generic_reclassification_not_detected() -> None:

    text = (
        "Certain prior period amounts were subject to reclassification "
        "for presentation purposes and had no effect on total revenue."
    )

    result = classify(
        text,
        PREVIOUS_SETTLEMENT,
        CURRENT_SETTLEMENT,
    )

    assert_equal(
        result["text_matches_count"],
        0,
        "Reclassification contabil generica nao deve gerar text match.",
    )

    assert_equal(
        result["qualified_evidence_count"],
        0,
        "Reclassification contabil generica nao pode gerar evidencia qualificada.",
    )


# ======================================================================
# TESTE 2
#
# Reclassification explicitamente ligada a common stock,
# mas sem effective date.
#
# Esperado:
#
# text match = 1
# effective date = None
# economic relation = UNRESOLVED
# qualification = UNRESOLVED_EFFECTIVE_DATE
# qualified = False
# ======================================================================

def test_2_stock_reclassification_without_effective_date() -> None:

    text = (
        "The company approved a reclassification of its common stock "
        "in connection with the transaction."
    )

    result = classify(
        text,
        PREVIOUS_SETTLEMENT,
        CURRENT_SETTLEMENT,
    )

    assert_equal(
        result["text_matches_count"],
        1,
        "Reclassification de common stock deveria ser detectada.",
    )

    assert_equal(
        result["qualified_evidence_count"],
        0,
        "Sem effective date a evidencia nao pode ser qualificada.",
    )

    match = first_match(result)

    assert_equal(
        match["category"],
        "RECLASSIFICATION",
        "Categoria incorreta.",
    )

    assert_equal(
        match["candidate_action_type"],
        "RECLASSIFICATION",
        "Candidate action incorreta.",
    )

    assert_equal(
        match["effective_date_candidate"],
        None,
        "Nao deveria existir effective date.",
    )

    assert_equal(
        match["economic_temporal_relation"],
        "UNRESOLVED",
        "Sem effective date a relacao economica deve ser UNRESOLVED.",
    )

    assert_equal(
        match["qualification_status"],
        "UNRESOLVED_EFFECTIVE_DATE",
        "Status de qualificacao incorreto.",
    )

    assert_false(
        match["qualified_for_current_reconciliation"],
        "Match sem effective date nao pode ser qualificado.",
    )


# ======================================================================
# TESTE 3
#
# Stock split com effective date dentro da janela:
#
# 14/08/2026 -> 31/08/2026
#
# Effective: 20/08/2026
#
# Esperado:
#
# IN_ECONOMIC_WINDOW
# qualified = True
# ======================================================================

def test_3_stock_split_inside_window() -> None:

    text = (
        "The Board approved a 2-for-1 stock split. "
        "The stock split will become effective on August 20, 2026."
    )

    result = classify(
        text,
        PREVIOUS_SETTLEMENT,
        CURRENT_SETTLEMENT,
    )

    assert_true(
        result["text_matches_count"] >= 1,
        "Stock split deveria gerar text match.",
    )

    assert_true(
        result["qualified_evidence_count"] >= 1,
        "Stock split dentro da janela deveria gerar evidencia qualificada.",
    )

    match = first_match(result)

    assert_equal(
        match["candidate_action_type"],
        "STOCK_SPLIT",
        "Action type deveria ser STOCK_SPLIT.",
    )

    assert_equal(
        match["effective_date_candidate"],
        "2026-08-20",
        "Effective date incorreta.",
    )

    assert_equal(
        match["economic_temporal_relation"],
        "IN_ECONOMIC_WINDOW",
        "A acao deveria estar dentro da janela economica.",
    )

    assert_equal(
        match["qualification_status"],
        "QUALIFIED_IN_ECONOMIC_WINDOW",
        "Qualification status incorreto.",
    )

    assert_true(
        match["qualified_for_current_reconciliation"],
        "Stock split dentro da janela deveria ser qualificado.",
    )


# ======================================================================
# TESTE 4
#
# Reverse split historico.
#
# Effective: 01/09/2025
#
# Janela:
#
# 14/08/2026 -> 31/08/2026
#
# Esperado:
#
# BEFORE_ECONOMIC_WINDOW
# OUTSIDE_ECONOMIC_WINDOW
# qualified = False
#
# Esse caso reproduz semanticamente o problema observado no ETON.
# ======================================================================

def test_4_historical_reverse_split() -> None:

    text = (
        "The company completed a reverse stock split "
        "which became effective on September 1, 2025."
    )

    result = classify(
        text,
        PREVIOUS_SETTLEMENT,
        CURRENT_SETTLEMENT,
    )

    assert_true(
        result["text_matches_count"] >= 1,
        "Reverse stock split deveria ser detectado.",
    )

    assert_equal(
        result["qualified_evidence_count"],
        0,
        "Acao historica nao pode ser evidencia qualificada da janela atual.",
    )

    match = first_match(result)

    assert_equal(
        match["candidate_action_type"],
        "REVERSE_STOCK_SPLIT",
        "Action type deveria ser REVERSE_STOCK_SPLIT.",
    )

    assert_equal(
        match["effective_date_candidate"],
        "2025-09-01",
        "Effective date historica incorreta.",
    )

    assert_equal(
        match["economic_temporal_relation"],
        "BEFORE_ECONOMIC_WINDOW",
        "Acao historica deveria estar BEFORE_ECONOMIC_WINDOW.",
    )

    assert_equal(
        match["qualification_status"],
        "OUTSIDE_ECONOMIC_WINDOW",
        "Acao historica deveria ser OUTSIDE_ECONOMIC_WINDOW.",
    )

    assert_false(
        match["qualified_for_current_reconciliation"],
        "Acao historica nao pode ser qualificada.",
    )


# ======================================================================
# TESTE 5
#
# O filing poderia ter ocorrido antes da janela, mas a classificacao
# semantica recebe o texto do filing e deve usar a EFFECTIVE DATE.
#
# Effective: 20/08/2026
#
# Isso prova que filing_date NAO governa a janela economica.
#
# A funcao classify() deliberadamente nao recebe filing_date.
# ======================================================================

def test_5_effective_date_has_precedence() -> None:

    text = (
        "The company announced that a 3-for-1 stock split "
        "will become effective on August 20, 2026."
    )

    result = classify(
        text,
        PREVIOUS_SETTLEMENT,
        CURRENT_SETTLEMENT,
    )

    assert_true(
        result["qualified_evidence_count"] >= 1,
        "Effective date dentro da janela deve prevalecer.",
    )

    match = first_match(result)

    assert_equal(
        match["effective_date_candidate"],
        "2026-08-20",
        "Effective date incorreta.",
    )

    assert_equal(
        match["economic_temporal_relation"],
        "IN_ECONOMIC_WINDOW",
        "Effective date deveria determinar IN_ECONOMIC_WINDOW.",
    )

    assert_true(
        match["qualified_for_current_reconciliation"],
        "Filing anterior nao deve impedir qualificacao quando "
        "effective date esta dentro da janela.",
    )


# ======================================================================
# TESTE 6
#
# Corporate action efetiva depois do current settlement.
#
# Effective: 05/09/2026
#
# Esperado:
#
# AFTER_ECONOMIC_WINDOW
# OUTSIDE_ECONOMIC_WINDOW
# qualified = False
# ======================================================================

def test_6_action_after_window() -> None:

    text = (
        "The Board approved a reverse stock split "
        "that will become effective on September 5, 2026."
    )

    result = classify(
        text,
        PREVIOUS_SETTLEMENT,
        CURRENT_SETTLEMENT,
    )

    assert_true(
        result["text_matches_count"] >= 1,
        "Corporate action deveria ser detectada.",
    )

    assert_equal(
        result["qualified_evidence_count"],
        0,
        "Acao posterior a janela nao pode ser evidencia qualificada.",
    )

    match = first_match(result)

    assert_equal(
        match["effective_date_candidate"],
        "2026-09-05",
        "Effective date incorreta.",
    )

    assert_equal(
        match["economic_temporal_relation"],
        "AFTER_ECONOMIC_WINDOW",
        "Acao deveria estar AFTER_ECONOMIC_WINDOW.",
    )

    assert_equal(
        match["qualification_status"],
        "OUTSIDE_ECONOMIC_WINDOW",
        "Qualification deveria ser OUTSIDE_ECONOMIC_WINDOW.",
    )

    assert_false(
        match["qualified_for_current_reconciliation"],
        "Acao posterior nao pode ser qualificada.",
    )


def main() -> int:

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SEC CORPORATE ACTION EVIDENCE RESOLVER")
    print("TESTE DE REGRESSAO SEMANTICA")
    print("=" * 72)

    tests = [
        (
            1,
            "Generic reclassification must not be detected",
            test_1_generic_reclassification_not_detected,
        ),
        (
            2,
            "Stock reclassification without effective date",
            test_2_stock_reclassification_without_effective_date,
        ),
        (
            3,
            "Stock split inside economic window",
            test_3_stock_split_inside_window,
        ),
        (
            4,
            "Historical reverse split outside economic window",
            test_4_historical_reverse_split,
        ),
        (
            5,
            "Effective date has precedence over filing date",
            test_5_effective_date_has_precedence,
        ),
        (
            6,
            "Corporate action after economic window",
            test_6_action_after_window,
        ),
    ]

    passed = 0
    failed = 0

    for number, name, function in tests:

        if run_test(number, name, function):
            passed += 1
        else:
            failed += 1

    print("=" * 72)
    print("RESUMO")
    print("=" * 72)
    print("Total :", len(tests))
    print("PASS  :", passed)
    print("FAIL  :", failed)

    if failed == 0:
        print("RESULTADO FINAL: APROVADO")
        return 0

    print("RESULTADO FINAL: REPROVADO")
    return 1


if __name__ == "__main__":
    sys.exit(main())