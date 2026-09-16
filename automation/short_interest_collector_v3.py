"""
RADAR INSTITUCIONAL V3
V3.4D.2-A - SHORT INTEREST FACT COLLECTOR

Responsabilidade
----------------
Coletar fatos oficiais de Short Interest através das rotas
resolvidas pelo Master Asset Universe.

Nesta versão:
- Master Asset Universe deve ser válido;
- Source Router decide quais ativos estão READY;
- FINRA Consolidated Short Interest é a rota suportada;
- credenciais vêm exclusivamente de variáveis de ambiente;
- access token permanece somente em memória;
- os dois settlement dates mais recentes são preservados;
- o Radar recalcula change_shares e change_pct;
- valores calculados são comparados aos valores FINRA;
- provenance é preservada;
- nenhum Signal, Confidence, Score ou Decision é calculado;
- radar_v3.json NÃO é alterado.

Exit codes
----------
0 = coleta concluída sem ativos bloqueados
1 = pelo menos um ativo READY falhou/bloqueou na coleta
2 = erro global: universo, autenticação ou infraestrutura
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from asset_universe_validator_v3 import (
    load_json,
    validate_universe,
)

from short_interest_source_router_v3 import (
    resolve_routes,
)


COLLECTOR_VERSION = "3.4D.2-A"

DEFAULT_UNIVERSE = Path(
    "automation/asset_universe_v3.json"
)

DEFAULT_OUTPUT = Path(
    "input/short_interest_collection_v3.json"
)

TOKEN_URL = (
    "https://ews.fip.finra.org/"
    "fip/rest/ews/oauth2/access_token"
)

FINRA_DATASET_URL = (
    "https://api.finra.org/"
    "data/group/otcMarket/name/consolidatedShortInterest"
)

TIMEOUT_SECONDS = 60

# FINRA apresenta changePercent arredondado.
# O Radar preserva o cálculo de maior precisão.
PERCENT_CROSS_CHECK_TOLERANCE = 0.02


class CollectorError(RuntimeError):
    pass


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def get_credentials() -> tuple[str, str]:
    client_id = os.getenv("FINRA_CLIENT_ID")
    client_secret = os.getenv("FINRA_CLIENT_SECRET")

    if not client_id:
        raise CollectorError(
            "FINRA_CLIENT_ID nao configurada."
        )

    if not client_secret:
        raise CollectorError(
            "FINRA_CLIENT_SECRET nao configurada."
        )

    return client_id, client_secret


def get_access_token(
    client_id: str,
    client_secret: str,
) -> str:
    raw = f"{client_id}:{client_secret}"

    encoded = base64.b64encode(
        raw.encode("utf-8")
    ).decode("ascii")

    response = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
        },
        params={
            "grant_type": "client_credentials",
        },
        timeout=TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        raise CollectorError(
            "Falha global na autenticacao FINRA. "
            f"HTTP {response.status_code}."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise CollectorError(
            "Resposta OAuth FINRA nao e JSON valido."
        ) from exc

    token = payload.get("access_token")

    if not isinstance(token, str) or not token:
        raise CollectorError(
            "access_token ausente na resposta FINRA."
        )

    return token


def build_finra_filter(
    ticker: str,
) -> dict[str, Any]:
    return {
        "compareFilters": [
            {
                "compareType": "EQUAL",
                "fieldName": "symbolCode",
                "fieldValue": ticker,
            }
        ]
    }


def query_finra(
    token: str,
    ticker: str,
) -> list[dict[str, Any]]:
    response = requests.post(
        FINRA_DATASET_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        params={
            "limit": 50,
        },
        json=build_finra_filter(ticker),
        timeout=TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        raise CollectorError(
            f"FINRA query HTTP {response.status_code}."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise CollectorError(
            "Resposta FINRA nao e JSON valido."
        ) from exc

    if isinstance(payload, list):
        return [
            row
            for row in payload
            if isinstance(row, dict)
        ]

    if isinstance(payload, dict):
        for key in (
            "data",
            "results",
            "records",
            "items",
        ):
            candidate = payload.get(key)

            if isinstance(candidate, list):
                return [
                    row
                    for row in candidate
                    if isinstance(row, dict)
                ]

    return []


def to_int(
    value: Any,
    field_name: str,
) -> int:
    if value is None or value == "":
        raise CollectorError(
            f"{field_name} ausente."
        )

    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise CollectorError(
            f"{field_name} invalido: {value!r}."
        ) from exc

    return number


def to_float_or_none(
    value: Any,
) -> float | None:
    if value is None or value == "":
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def settlement_date(
    row: dict[str, Any],
) -> str:
    value = row.get("settlementDate")

    if not isinstance(value, str) or not value.strip():
        raise CollectorError(
            "settlementDate ausente."
        )

    return value.strip()


def select_latest_rows(
    rows: list[dict[str, Any]],
    ticker: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    matching: list[dict[str, Any]] = []

    for row in rows:
        symbol = str(
            row.get("symbolCode") or ""
        ).strip().upper()

        if symbol != ticker:
            continue

        if not row.get("settlementDate"):
            continue

        matching.append(row)

    matching.sort(
        key=lambda row: str(
            row.get("settlementDate")
        ),
        reverse=True,
    )

    # Proteção contra eventual duplicação de linhas
    # do mesmo settlement date.
    unique: list[dict[str, Any]] = []
    seen_dates: set[str] = set()

    for row in matching:
        date = str(row.get("settlementDate"))

        if date in seen_dates:
            continue

        seen_dates.add(date)
        unique.append(row)

    if len(unique) < 2:
        raise CollectorError(
            "Menos de dois settlement dates distintos."
        )

    return unique[0], unique[1]


def build_snapshot(
    row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "settlement_date": settlement_date(row),
        "symbol": str(
            row.get("symbolCode") or ""
        ).strip().upper(),
        "current_short_interest_shares": to_int(
            row.get(
                "currentShortPositionQuantity"
            ),
            "currentShortPositionQuantity",
        ),
        "previous_short_interest_shares": to_int(
            row.get(
                "previousShortPositionQuantity"
            ),
            "previousShortPositionQuantity",
        ),
        "finra_change_shares": to_int(
            row.get("changePreviousNumber"),
            "changePreviousNumber",
        ),
        "finra_change_pct": to_float_or_none(
            row.get("changePercent")
        ),
        "average_daily_volume_shares": to_float_or_none(
            row.get(
                "averageDailyVolumeQuantity"
            )
        ),
        "days_to_cover": to_float_or_none(
            row.get("daysToCoverQuantity")
        ),
    }


def calculate_change(
    current: int,
    previous: int,
) -> tuple[int, float]:
    if previous <= 0:
        raise CollectorError(
            "previous_short_interest_shares deve ser > 0."
        )

    change_shares = current - previous

    change_pct = (
        change_shares
        / previous
        * 100.0
    )

    return change_shares, change_pct


def cross_check(
    calculated_change_shares: int,
    calculated_change_pct: float,
    finra_change_shares: int,
    finra_change_pct: float | None,
) -> dict[str, Any]:
    shares_match = (
        calculated_change_shares
        == finra_change_shares
    )

    if finra_change_pct is None:
        percent_difference = None
        percent_within_tolerance = None
    else:
        percent_difference = abs(
            calculated_change_pct
            - finra_change_pct
        )

        percent_within_tolerance = (
            percent_difference
            <= PERCENT_CROSS_CHECK_TOLERANCE
        )

    return {
        "shares_match": shares_match,
        "percent_difference": (
            round(percent_difference, 8)
            if percent_difference is not None
            else None
        ),
        "percent_tolerance": (
            PERCENT_CROSS_CHECK_TOLERANCE
        ),
        "percent_within_tolerance": (
            percent_within_tolerance
        ),
    }


def continuity_check(
    latest: dict[str, Any],
    previous: dict[str, Any],
) -> dict[str, Any]:
    latest_previous = (
        latest[
            "previous_short_interest_shares"
        ]
    )

    prior_current = (
        previous[
            "current_short_interest_shares"
        ]
    )

    return {
        "latest_previous_equals_prior_current": (
            latest_previous == prior_current
        ),
        "latest_previous_short_interest_shares": (
            latest_previous
        ),
        "prior_current_short_interest_shares": (
            prior_current
        ),
    }


def collect_asset(
    token: str,
    decision: Any,
    retrieved_at: str,
) -> dict[str, Any]:
    ticker = decision.ticker

    rows = query_finra(
        token=token,
        ticker=ticker,
    )

    latest_row, previous_row = select_latest_rows(
        rows=rows,
        ticker=ticker,
    )

    latest = build_snapshot(latest_row)
    previous = build_snapshot(previous_row)

    change_shares, change_pct = calculate_change(
        current=latest[
            "current_short_interest_shares"
        ],
        previous=latest[
            "previous_short_interest_shares"
        ],
    )

    checks = cross_check(
        calculated_change_shares=change_shares,
        calculated_change_pct=change_pct,
        finra_change_shares=latest[
            "finra_change_shares"
        ],
        finra_change_pct=latest[
            "finra_change_pct"
        ],
    )

    continuity = continuity_check(
        latest=latest,
        previous=previous,
    )

    blocking_reasons: list[str] = []

    if not checks["shares_match"]:
        blocking_reasons.append(
            "FINRA_CHANGE_SHARES_MISMATCH"
        )

    if checks["percent_within_tolerance"] is False:
        blocking_reasons.append(
            "FINRA_CHANGE_PERCENT_MISMATCH"
        )

    if not continuity[
        "latest_previous_equals_prior_current"
    ]:
        blocking_reasons.append(
            "SETTLEMENT_CONTINUITY_MISMATCH"
        )

    if blocking_reasons:
        data_status = "AVAILABLE"
        quality_status = "BLOCKED"
        analytically_usable = False
    else:
        data_status = "AVAILABLE"
        quality_status = "PRELIMINARY_PASS"
        analytically_usable = False

    # analytically_usable permanece False nesta versão.
    # Corporate Action reconciliation ainda será adicionada
    # antes da homologação final do Quality Gate.

    return {
        "ticker": ticker,
        "identity": {
            "issuer_name": decision.issuer_name,
            "security_name": decision.security_name,
            "listing_exchange": (
                decision.listing_exchange
            ),
            "cusip": decision.cusip,
        },
        "route": {
            "primary_source": (
                decision.primary_source
            ),
            "dataset": decision.dataset,
            "route_status": decision.status,
        },
        "data_status": data_status,
        "quality_status": quality_status,
        "analytically_usable": (
            analytically_usable
        ),
        "metric": {
            "name": "short_interest_change_pct",
            "unit": "PERCENT",
            "settlement_date": latest[
                "settlement_date"
            ],
            "raw": {
                "current_short_interest_shares": (
                    latest[
                        "current_short_interest_shares"
                    ]
                ),
                "previous_short_interest_shares": (
                    latest[
                        "previous_short_interest_shares"
                    ]
                ),
                "finra_change_shares": (
                    latest[
                        "finra_change_shares"
                    ]
                ),
                "finra_change_pct": (
                    latest[
                        "finra_change_pct"
                    ]
                ),
                "average_daily_volume_shares": (
                    latest[
                        "average_daily_volume_shares"
                    ]
                ),
                "days_to_cover": (
                    latest["days_to_cover"]
                ),
            },
            "calculated": {
                "change_shares": change_shares,
                "change_pct": round(
                    change_pct,
                    8,
                ),
            },
            "cross_check": checks,
            "continuity_check": continuity,
        },
        "previous_settlement_snapshot": previous,
        "blocking_reasons": blocking_reasons,
        "provenance": {
            "source": "FINRA",
            "source_tier": "TIER_1",
            "dataset": (
                "CONSOLIDATED_SHORT_INTEREST"
            ),
            "retrieved_at": retrieved_at,
            "market_date": latest[
                "settlement_date"
            ],
            "verification_status": (
                "OFFICIAL_SOURCE"
            ),
        },
    }


def failed_asset(
    decision: Any,
    reason: str,
    retrieved_at: str,
) -> dict[str, Any]:
    return {
        "ticker": decision.ticker,
        "identity": {
            "issuer_name": decision.issuer_name,
            "security_name": decision.security_name,
            "listing_exchange": (
                decision.listing_exchange
            ),
            "cusip": decision.cusip,
        },
        "route": {
            "primary_source": (
                decision.primary_source
            ),
            "dataset": decision.dataset,
            "route_status": decision.status,
        },
        "data_status": "UNAVAILABLE",
        "quality_status": "BLOCKED",
        "analytically_usable": False,
        "metric": None,
        "previous_settlement_snapshot": None,
        "blocking_reasons": [reason],
        "provenance": {
            "source": (
                decision.primary_source
                or "UNKNOWN"
            ),
            "source_tier": (
                "TIER_1"
                if decision.primary_source == "FINRA"
                else None
            ),
            "dataset": decision.dataset,
            "retrieved_at": retrieved_at,
            "market_date": None,
            "verification_status": (
                "COLLECTION_FAILED"
            ),
        },
    }


def write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            ensure_ascii=False,
        )
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Radar Institucional V3 - "
            "Short Interest Fact Collector"
        )
    )

    parser.add_argument(
        "--universe",
        default=str(DEFAULT_UNIVERSE),
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    universe_path = Path(args.universe)
    output_path = Path(args.output)

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST FACT COLLECTOR")
    print(f"VERSION {COLLECTOR_VERSION}")
    print("=" * 72)
    print()

    try:
        universe = load_json(universe_path)
    except RuntimeError as exc:
        print(f"ERRO GLOBAL: {exc}")
        print("RESULTADO: BLOCKED")
        return 2

    issues = validate_universe(universe)

    errors = [
        issue
        for issue in issues
        if issue.severity == "ERROR"
    ]

    if errors:
        print(
            "ERRO GLOBAL: Master Asset Universe invalido."
        )

        for issue in errors:
            print(
                f"  X {issue.code} "
                f"({issue.location})"
            )

        print("RESULTADO: BLOCKED")
        return 2

    decisions = resolve_routes(universe)

    route_blocked = [
        decision
        for decision in decisions
        if decision.status.startswith(
            "BLOCKED_"
        )
    ]

    if route_blocked:
        print(
            "ERRO GLOBAL: existem rotas bloqueadas."
        )

        for decision in route_blocked:
            print(
                f"  X {decision.ticker}: "
                f"{decision.reason}"
            )

        print("RESULTADO: BLOCKED")
        return 2

    ready = [
        decision
        for decision in decisions
        if decision.status == "READY"
    ]

    skipped = [
        decision
        for decision in decisions
        if decision.status.startswith(
            "SKIP_"
        )
    ]

    print(
        f"Universe: {universe.get('universe_version')}"
    )
    print(f"Ready: {len(ready)}")
    print(f"Skipped: {len(skipped)}")
    print()

    if not ready:
        print(
            "ERRO GLOBAL: nenhum ativo READY "
            "para Short Interest."
        )
        print("RESULTADO: BLOCKED")
        return 2

    try:
        client_id, client_secret = (
            get_credentials()
        )

        print(
            "FINRA credentials: CONFIGURADAS"
        )
        print("Obtendo OAuth token...")

        token = get_access_token(
            client_id=client_id,
            client_secret=client_secret,
        )

        print(
            "OAuth: OK "
            "(token mantido somente em memoria)"
        )
        print()

    except CollectorError as exc:
        print(f"ERRO GLOBAL: {exc}")
        print("RESULTADO: BLOCKED")
        return 2
    except requests.RequestException as exc:
        print(
            "ERRO GLOBAL DE REDE:",
            type(exc).__name__,
        )
        print("RESULTADO: BLOCKED")
        return 2

    retrieved_at = utc_now_iso()

    collected: list[dict[str, Any]] = []
    failed_count = 0

    for decision in ready:
        print("-" * 72)
        print(f"TICKER: {decision.ticker}")

        try:
            result = collect_asset(
                token=token,
                decision=decision,
                retrieved_at=retrieved_at,
            )

            collected.append(result)

            metric = result["metric"]

            print(
                "Settlement:",
                metric["settlement_date"],
            )

            print(
                "Current SI:",
                metric["raw"][
                    "current_short_interest_shares"
                ],
            )

            print(
                "Previous SI:",
                metric["raw"][
                    "previous_short_interest_shares"
                ],
            )

            print(
                "FINRA change %:",
                metric["raw"][
                    "finra_change_pct"
                ],
            )

            print(
                "Radar change %:",
                metric["calculated"][
                    "change_pct"
                ],
            )

            print(
                "Shares cross-check:",
                metric["cross_check"][
                    "shares_match"
                ],
            )

            print(
                "Percent cross-check:",
                metric["cross_check"][
                    "percent_within_tolerance"
                ],
            )

            print(
                "Settlement continuity:",
                metric["continuity_check"][
                    "latest_previous_equals_prior_current"
                ],
            )

            print(
                "Quality:",
                result["quality_status"],
            )

        except (
            CollectorError,
            requests.RequestException,
        ) as exc:
            failed_count += 1

            reason = (
                f"{type(exc).__name__}: {exc}"
            )

            collected.append(
                failed_asset(
                    decision=decision,
                    reason=reason,
                    retrieved_at=retrieved_at,
                )
            )

            print("Collection: BLOCKED")
            print(f"Reason: {reason}")

    output = {
        "collector_version": (
            COLLECTOR_VERSION
        ),
        "universe_version": universe.get(
            "universe_version"
        ),
        "domain": "SHORT_INTEREST",
        "retrieved_at": retrieved_at,
        "source": {
            "name": "FINRA",
            "tier": "TIER_1",
            "dataset": (
                "CONSOLIDATED_SHORT_INTEREST"
            ),
        },
        "summary": {
            "ready_assets": len(ready),
            "skipped_assets": len(skipped),
            "collected_assets": (
                len(ready) - failed_count
            ),
            "failed_assets": failed_count,
        },
        "skipped": [
            {
                "ticker": decision.ticker,
                "status": decision.status,
                "reason": decision.reason,
            }
            for decision in skipped
        ],
        "assets": collected,
    }

    write_json(
        path=output_path,
        payload=output,
    )

    print("-" * 72)
    print()
    print(f"Output: {output_path}")
    print()
    print("[SUMMARY]")
    print(
        "Ready:",
        output["summary"]["ready_assets"],
    )
    print(
        "Collected:",
        output["summary"][
            "collected_assets"
        ],
    )
    print(
        "Failed:",
        output["summary"][
            "failed_assets"
        ],
    )
    print(
        "Skipped:",
        output["summary"][
            "skipped_assets"
        ],
    )
    print()

    if failed_count:
        print(
            "RESULTADO: COMPLETED_WITH_BLOCKED_ASSETS"
        )
        return 1

    print("RESULTADO: COLLECTION_COMPLETED")
    print(
        "Signal/Confidence/Score nao foram alterados."
    )
    print(
        "radar_v3.json nao foi alterado."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())