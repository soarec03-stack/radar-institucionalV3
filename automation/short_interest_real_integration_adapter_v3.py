from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.8D"

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_real_positive_official_review_v3.json"
)

POLICY_FILE = (
    BASE_DIR
    / "automation"
    / "short_interest_corporate_action_integration_policy_v3.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_real_integration_adapter_v3.json"
)


class RealIntegrationAdapterError(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RealIntegrationAdapterError(
            f"Arquivo não encontrado: {path}"
        )

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise RealIntegrationAdapterError(
            f"JSON inválido em {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise RealIntegrationAdapterError(
            f"Root JSON deve ser objeto: {path}"
        )

    return data


def write_json(
    path: Path,
    data: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")


def non_empty_string(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
    )


def build_adapter_case(
    asset: dict[str, Any],
) -> dict[str, Any]:
    """
    Traduz a saída real da B.2C.8C para o contrato
    homologado do Integration Adapter B.2C.7C.2.

    Nenhuma inferência de corporate action é realizada.
    """

    if not isinstance(asset, dict):
        raise RealIntegrationAdapterError(
            "Asset deve ser objeto."
        )

    ticker = asset.get("ticker")

    if not non_empty_string(ticker):
        raise RealIntegrationAdapterError(
            "Ticker ausente ou inválido."
        )

    review_case = asset.get("review_case")
    review_result = asset.get("review_result")

    if not isinstance(review_case, dict):
        raise RealIntegrationAdapterError(
            f"{ticker}: review_case ausente ou inválido."
        )

    if not isinstance(review_result, dict):
        raise RealIntegrationAdapterError(
            f"{ticker}: review_result ausente ou inválido."
        )

    identity = review_case.get("identity")

    if not isinstance(identity, dict):
        raise RealIntegrationAdapterError(
            f"{ticker}: identity ausente ou inválida."
        )

    if identity.get("ticker") != ticker:
        raise RealIntegrationAdapterError(
            f"{ticker}: ticker inconsistente em identity."
        )

    previous_date = review_case.get(
        "previous_settlement_date"
    )
    current_date = review_case.get(
        "current_settlement_date"
    )

    if not non_empty_string(previous_date):
        raise RealIntegrationAdapterError(
            f"{ticker}: previous_settlement_date inválida."
        )

    if not non_empty_string(current_date):
        raise RealIntegrationAdapterError(
            f"{ticker}: current_settlement_date inválida."
        )

    if (
        review_result.get(
            "previous_settlement_date"
        )
        != previous_date
    ):
        raise RealIntegrationAdapterError(
            f"{ticker}: previous settlement mismatch "
            "entre review_case e review_result."
        )

    if (
        review_result.get(
            "current_settlement_date"
        )
        != current_date
    ):
        raise RealIntegrationAdapterError(
            f"{ticker}: current settlement mismatch "
            "entre review_case e review_result."
        )

    if review_result.get("ticker") != ticker:
        raise RealIntegrationAdapterError(
            f"{ticker}: ticker inconsistente em review_result."
        )

    review_status = review_result.get(
        "review_status"
    )

    if review_status not in {
        "NO_ACTION_PROVEN",
        "ACTION_FOUND",
        "UNRESOLVED",
    }:
        raise RealIntegrationAdapterError(
            f"{ticker}: review_status inválido: "
            f"{review_status}"
        )

    #
    # Estado atual real:
    #
    # B.2C.8C ainda não produz action_evidence
    # homologada nem declaração oficial de source
    # adjustment.
    #
    # Portanto:
    # - UNRESOLVED -> source_adjustment UNRESOLVED
    # - NO_ACTION_PROVEN -> NOT_ADJUSTED
    # - ACTION_FOUND -> permanece UNRESOLVED até
    #   existir evidência real adequada para a rota
    #   de ação.
    #
    # Não inventar SOURCE_ALREADY_ADJUSTED.
    #

    if review_status == "NO_ACTION_PROVEN":
        source_adjustment = {
            "status": "NOT_ADJUSTED"
        }
    else:
        source_adjustment = {
            "status": "UNRESOLVED"
        }

    return {
        "case": f"REAL_{ticker}",
        "ticker": ticker,
        "identity": deepcopy(identity),
        "previous_settlement_date":
            previous_date,
        "current_settlement_date":
            current_date,
        "review": deepcopy(review_result),
        "action_evidence": None,
        "source_adjustment":
            source_adjustment,
    }


def run_real_adapter(
    input_data: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """
    Executa exclusivamente a adaptação real.

    O Reconciler NÃO é chamado neste estágio.
    """

    try:
        from short_interest_corporate_action_integration_adapter_v3 import (
            adapt_case,
            validate_policy,
        )
    except ImportError as exc:
        raise RealIntegrationAdapterError(
            "Não foi possível importar o Integration "
            "Adapter homologado B.2C.7C.2."
        ) from exc

    validate_policy(policy)

    assets = input_data.get("assets")

    if not isinstance(assets, list):
        raise RealIntegrationAdapterError(
            "Campo assets ausente ou inválido."
        )

    if not assets:
        raise RealIntegrationAdapterError(
            "Lista assets não pode estar vazia."
        )

    seen: set[str] = set()

    results: list[dict[str, Any]] = []

    blocked = 0
    ready = 0
    reconciler_invocations = 0
    analytically_usable = 0

    for asset in assets:
        adapter_case = build_adapter_case(
            asset
        )

        ticker = adapter_case["ticker"]

        if ticker in seen:
            raise RealIntegrationAdapterError(
                f"Ticker duplicado: {ticker}"
            )

        seen.add(ticker)

        result = adapt_case(
            deepcopy(adapter_case),
            policy,
        )

        integration_status = result.get(
            "integration_status"
        )

        if integration_status == "BLOCKED":
            blocked += 1

        elif integration_status == (
            "READY_FOR_RECONCILIATION"
        ):
            ready += 1

        else:
            raise RealIntegrationAdapterError(
                f"{ticker}: integration_status "
                f"inesperado: {integration_status}"
            )

        #
        # IMPORTANTE:
        #
        # B.2C.8D termina na fronteira do Adapter.
        # Mesmo um READY não chama o Reconciler aqui.
        #
        # A chamada real ao Reconciler será objeto
        # de etapa própria.
        #
        reconciler_invoked = False

        if reconciler_invoked:
            reconciler_invocations += 1

        final_usable = (
            result.get(
                "final_short_interest_analytically_usable"
            )
            is True
        )

        if final_usable:
            analytically_usable += 1

        results.append(
            {
                "ticker": ticker,
                "adapter_case":
                    deepcopy(adapter_case),
                "adapter_result":
                    deepcopy(result),
                "reconciler_invoked":
                    reconciler_invoked,
                "analytically_usable":
                    final_usable,
            }
        )

    return {
        "pipeline_version": VERSION,
        "domain":
            "SHORT_INTEREST_REAL_INTEGRATION_ADAPTER",
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "source_input":
            str(INPUT_FILE),
        "integration_policy":
            str(POLICY_FILE),
        "execution_scope": {
            "network_collection": False,
            "corporate_action_inference": False,
            "no_action_inference": False,
            "reconciler_execution": False,
            "signal_generation": False,
            "confidence_generation": False,
            "score_generation": False,
            "decision_generation": False,
            "radar_mutation": False,
        },
        "summary": {
            "total_assets":
                len(results),
            "blocked":
                blocked,
            "ready_for_reconciliation":
                ready,
            "reconciler_invocations":
                reconciler_invocations,
            "analytically_usable":
                analytically_usable,
        },
        "assets": results,
    }


def main() -> int:
    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST")
    print("REAL INTEGRATION ADAPTER")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:
        input_data = read_json(
            INPUT_FILE
        )
        policy = read_json(
            POLICY_FILE
        )

        output = run_real_adapter(
            input_data,
            policy,
        )

        write_json(
            OUTPUT_FILE,
            output,
        )

        for asset in output["assets"]:
            result = asset[
                "adapter_result"
            ]

            print("-" * 72)
            print(
                "Ticker:",
                asset["ticker"],
            )
            print(
                "Review:",
                result.get(
                    "review_status"
                ),
            )
            print(
                "Integration:",
                result.get(
                    "integration_status"
                ),
            )
            print(
                "Route:",
                result.get(
                    "route"
                ),
            )
            print(
                "Reconciler input:",
                result.get(
                    "reconciler_input_status"
                ),
            )
            print(
                "Reconciler invoked:",
                asset[
                    "reconciler_invoked"
                ],
            )
            print(
                "Analytically usable:",
                asset[
                    "analytically_usable"
                ],
            )
            print(
                "Diagnostics:",
                result.get(
                    "diagnostics"
                ),
            )

        print("=" * 72)
        print("SUMMARY")
        print("=" * 72)

        for key, value in (
            output["summary"].items()
        ):
            print(
                f"{key}: {value}"
            )

        print("=" * 72)
        print(
            "Output:",
            OUTPUT_FILE,
        )

        return 0

    except Exception as exc:
        print(
            f"ERRO: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())