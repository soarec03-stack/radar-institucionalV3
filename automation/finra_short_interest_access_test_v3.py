"""
RADAR INSTITUCIONAL V3
V3.4D.1A - FINRA CONSOLIDATED SHORT INTEREST ACCESS TEST

Objetivo:
- Validar autenticação OAuth2 FINRA.
- Validar acesso ao dataset consolidatedShortInterest.
- Testar cobertura do universo piloto.
- Não alterar radar_v3.json.
- Não calcular Signal, Confidence ou Radar Score.
- Não armazenar credenciais ou access tokens.

VRT, CRSP e ETON são somente universo piloto de homologação.
O código aceita qualquer conjunto de tickers informado via CLI.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from typing import Any

import requests


VERSION = "3.4D.1A"

TOKEN_URL = (
    "https://ews.fip.finra.org/"
    "fip/rest/ews/oauth2/access_token"
)

DATASET_URL = (
    "https://api.finra.org/"
    "data/group/otcMarket/name/consolidatedShortInterest"
)

DEFAULT_TICKERS = ["VRT", "CRSP", "ETON"]

TIMEOUT_SECONDS = 60


def get_credentials() -> tuple[str, str]:
    client_id = os.getenv("FINRA_CLIENT_ID")
    client_secret = os.getenv("FINRA_CLIENT_SECRET")

    if not client_id:
        raise RuntimeError(
            "Variavel FINRA_CLIENT_ID nao configurada."
        )

    if not client_secret:
        raise RuntimeError(
            "Variavel FINRA_CLIENT_SECRET nao configurada."
        )

    return client_id, client_secret


def get_access_token(
    client_id: str,
    client_secret: str,
) -> str:
    """
    Obtém token OAuth2 sem imprimir ou persistir credenciais/token.
    """

    raw_credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(
        raw_credentials.encode("utf-8")
    ).decode("ascii")

    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Accept": "application/json",
    }

    params = {
        "grant_type": "client_credentials",
    }

    response = requests.post(
        TOKEN_URL,
        headers=headers,
        params=params,
        timeout=TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Falha na autenticacao FINRA. "
            f"HTTP {response.status_code}. "
            "Credenciais e token nao foram exibidos."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Resposta OAuth FINRA nao retornou JSON valido."
        ) from exc

    token = payload.get("access_token")

    if not token:
        raise RuntimeError(
            "FINRA autenticou a requisicao, "
            "mas access_token nao foi encontrado."
        )

    return str(token)


def build_filter(ticker: str) -> dict[str, Any]:
    """
    Query API filter para symbolCode.

    Mantido isolado para facilitar eventual ajuste de contrato
    após o primeiro teste real da API.
    """

    return {
        "compareFilters": [
            {
                "compareType": "EQUAL",
                "fieldName": "symbolCode",
                "fieldValue": ticker.upper(),
            }
        ]
    }


def query_ticker(
    access_token: str,
    ticker: str,
) -> tuple[int, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    params = {
        "limit": 50,
    }

    payload = build_filter(ticker)

    response = requests.post(
        DATASET_URL,
        headers=headers,
        params=params,
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )

    try:
        body = response.json()
    except ValueError:
        body = {
            "_non_json_response": True,
            "_response_length": len(response.text),
        }

    return response.status_code, body


def extract_rows(payload: Any) -> list[dict[str, Any]]:
    """
    Aceita tanto lista direta quanto envelopes JSON comuns.
    """

    if isinstance(payload, list):
        return [
            row for row in payload
            if isinstance(row, dict)
        ]

    if not isinstance(payload, dict):
        return []

    for key in (
        "data",
        "results",
        "records",
        "items",
    ):
        candidate = payload.get(key)

        if isinstance(candidate, list):
            return [
                row for row in candidate
                if isinstance(row, dict)
            ]

    return []


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: str(
            row.get("settlementDate") or ""
        ),
        reverse=True,
    )


def safe_value(row: dict[str, Any], key: str) -> Any:
    value = row.get(key)

    if value in ("", None):
        return None

    return value


def print_ticker_result(
    ticker: str,
    status_code: int,
    payload: Any,
) -> None:
    print("-" * 68)
    print(f"TICKER: {ticker}")
    print(f"HTTP:   {status_code}")

    if status_code != 200:
        print("RESULTADO: FALHA DE ACESSO/CONSULTA")

        if isinstance(payload, dict):
            safe_keys = [
                key
                for key in payload.keys()
                if key.lower() not in {
                    "access_token",
                    "token",
                    "authorization",
                    "password",
                    "secret",
                }
            ]

            if safe_keys:
                print(
                    "Campos retornados:",
                    ", ".join(sorted(safe_keys)),
                )

        return

    rows = sort_rows(extract_rows(payload))

    print(f"Registros encontrados: {len(rows)}")

    if not rows:
        print("RESULTADO: TICKER NAO ENCONTRADO")
        return

    print("RESULTADO: TICKER ENCONTRADO")

    latest_rows = rows[:2]

    print()
    print("Ultimos registros retornados:")

    for index, row in enumerate(latest_rows, start=1):
        print(f"  Registro {index}:")
        print(
            "    settlementDate:",
            safe_value(row, "settlementDate"),
        )
        print(
            "    symbolCode:",
            safe_value(row, "symbolCode"),
        )
        print(
            "    currentShortPositionQuantity:",
            safe_value(
                row,
                "currentShortPositionQuantity",
            ),
        )
        print(
            "    previousShortPositionQuantity:",
            safe_value(
                row,
                "previousShortPositionQuantity",
            ),
        )
        print(
            "    changePreviousNumber:",
            safe_value(
                row,
                "changePreviousNumber",
            ),
        )
        print(
            "    changePercent:",
            safe_value(
                row,
                "changePercent",
            ),
        )
        print(
            "    averageDailyVolumeQuantity:",
            safe_value(
                row,
                "averageDailyVolumeQuantity",
            ),
        )
        print(
            "    daysToCoverQuantity:",
            safe_value(
                row,
                "daysToCoverQuantity",
            ),
        )

    settlement_dates = {
        str(row.get("settlementDate"))
        for row in rows
        if row.get("settlementDate")
    }

    print()
    print(
        "Settlement dates distintos:",
        len(settlement_dates),
    )

    if len(settlement_dates) >= 2:
        print(
            "Cobertura temporal minima: OK "
            "(>= 2 settlement dates)"
        )
    else:
        print(
            "Cobertura temporal minima: INSUFICIENTE"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Radar Institucional V3 - "
            "FINRA Short Interest Access Test"
        )
    )

    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help=(
            "Tickers para teste. "
            "Default: VRT CRSP ETON"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    tickers = list(
        dict.fromkeys(
            ticker.strip().upper()
            for ticker in args.tickers
            if ticker.strip()
        )
    )

    print("=" * 68)
    print("RADAR INSTITUCIONAL V3")
    print("FINRA CONSOLIDATED SHORT INTEREST ACCESS TEST")
    print(f"VERSION {VERSION}")
    print("=" * 68)

    print()
    print(
        "Universo de teste:",
        ", ".join(tickers),
    )

    try:
        client_id, client_secret = get_credentials()

        print("FINRA_CLIENT_ID: CONFIGURADO")
        print("FINRA_CLIENT_SECRET: CONFIGURADO")

        print()
        print("Obtendo token OAuth2 FINRA...")

        access_token = get_access_token(
            client_id,
            client_secret,
        )

        print("OAuth2: OK")
        print(
            "Token obtido em memoria "
            "(valor nao exibido)."
        )

    except Exception as exc:
        print()
        print(f"ERRO: {exc}")
        return 1

    print()
    print("Consultando consolidatedShortInterest...")

    failures = 0

    for ticker in tickers:
        try:
            status_code, payload = query_ticker(
                access_token,
                ticker,
            )

            print_ticker_result(
                ticker,
                status_code,
                payload,
            )

            if status_code != 200:
                failures += 1

        except requests.RequestException as exc:
            print("-" * 68)
            print(f"TICKER: {ticker}")
            print(
                "ERRO DE REDE:",
                type(exc).__name__,
            )
            failures += 1

    print("-" * 68)

    if failures:
        print(
            "TESTE CONCLUIDO COM FALHAS "
            f"DE CONSULTA: {failures}"
        )
        return 2

    print("TESTE DE ACESSO CONCLUIDO.")
    print(
        "Nenhuma credencial ou token foi "
        "gravado em arquivo."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())