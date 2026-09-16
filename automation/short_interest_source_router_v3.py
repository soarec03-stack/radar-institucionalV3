"""
RADAR INSTITUCIONAL V3
V3.4D.1C-B - SHORT INTEREST SOURCE ROUTER

Responsabilidade
----------------
Resolver dinamicamente a rota oficial de Short Interest para os ativos
do Master Asset Universe.

Este módulo:
- valida primeiro o Master Asset Universe;
- seleciona ativos dinamicamente;
- respeita enabled;
- respeita SHORT_INTEREST true / false / null;
- valida identidade mínima necessária ao domínio;
- resolve a fonte configurada no próprio universo;
- produz decisão de roteamento auditável.

Este módulo NÃO:
- chama FINRA;
- chama Nasdaq;
- chama NYSE;
- coleta Short Interest;
- calcula short_interest_change_pct;
- calcula Confidence;
- calcula Signal;
- calcula Radar Score;
- modifica radar_v3.json.

Princípio:
    INVALID UNIVERSE -> FAIL CLOSED
    INVALID IDENTITY -> FAIL CLOSED
    INVALID ROUTE    -> FAIL CLOSED

Exit codes:
    0 = roteamento concluído sem BLOCKED
    1 = pelo menos um ativo BLOCKED
    2 = erro operacional / universo global inválido
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from asset_universe_validator_v3 import (
    load_json,
    validate_universe,
)


ROUTER_VERSION = "3.4D.1C-B"

DEFAULT_UNIVERSE = Path(
    "automation/asset_universe_v3.json"
)

DOMAIN = "SHORT_INTEREST"

SUPPORTED_PRIMARY_ROUTES = {
    ("FINRA", "CONSOLIDATED_SHORT_INTEREST"),
}


@dataclass
class RouteDecision:
    ticker: str
    status: str
    reason: str

    enabled: bool | None
    short_interest_eligible: bool | None

    issuer_name: str | None
    security_name: str | None
    listing_exchange: str | None
    exchange_group: str | None
    cusip: str | None

    primary_source: str | None
    dataset: str | None
    listing_exchange_verification: str | None


def text_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    value = value.strip()

    return value if value else None


def normalize_text(value: Any) -> str | None:
    value = text_or_none(value)

    if value is None:
        return None

    return value.upper()


def blocked_decision(
    ticker: str,
    reason: str,
    asset: dict[str, Any] | None = None,
) -> RouteDecision:
    asset = asset or {}

    listing = asset.get("listing")
    if not isinstance(listing, dict):
        listing = {}

    identifiers = asset.get("identifiers")
    if not isinstance(identifiers, dict):
        identifiers = {}

    eligibility = asset.get("domain_eligibility")
    if not isinstance(eligibility, dict):
        eligibility = {}

    routing = asset.get("source_routing")
    if not isinstance(routing, dict):
        routing = {}

    short_route = routing.get("short_interest")
    if not isinstance(short_route, dict):
        short_route = {}

    return RouteDecision(
        ticker=ticker,
        status="BLOCKED_ROUTE",
        reason=reason,
        enabled=(
            asset.get("enabled")
            if isinstance(asset.get("enabled"), bool)
            else None
        ),
        short_interest_eligible=eligibility.get(DOMAIN),
        issuer_name=text_or_none(asset.get("issuer_name")),
        security_name=text_or_none(asset.get("security_name")),
        listing_exchange=normalize_text(
            listing.get("exchange")
        ),
        exchange_group=normalize_text(
            listing.get("exchange_group")
        ),
        cusip=normalize_text(
            identifiers.get("cusip")
        ),
        primary_source=normalize_text(
            short_route.get("primary_source")
        ),
        dataset=normalize_text(
            short_route.get("dataset")
        ),
        listing_exchange_verification=normalize_text(
            short_route.get(
                "listing_exchange_verification"
            )
        ),
    )


def resolve_asset(
    asset_key: str,
    asset: dict[str, Any],
) -> RouteDecision:
    ticker = normalize_text(asset.get("ticker")) or asset_key

    enabled = asset.get("enabled")

    eligibility = asset.get("domain_eligibility", {})
    if not isinstance(eligibility, dict):
        eligibility = {}

    short_interest_eligible = eligibility.get(DOMAIN)

    listing = asset.get("listing", {})
    if not isinstance(listing, dict):
        listing = {}

    identifiers = asset.get("identifiers", {})
    if not isinstance(identifiers, dict):
        identifiers = {}

    issuer_name = text_or_none(asset.get("issuer_name"))
    security_name = text_or_none(asset.get("security_name"))

    listing_exchange = normalize_text(
        listing.get("exchange")
    )

    exchange_group = normalize_text(
        listing.get("exchange_group")
    )

    cusip = normalize_text(
        identifiers.get("cusip")
    )

    base = {
        "ticker": ticker,
        "enabled": enabled,
        "short_interest_eligible": short_interest_eligible,
        "issuer_name": issuer_name,
        "security_name": security_name,
        "listing_exchange": listing_exchange,
        "exchange_group": exchange_group,
        "cusip": cusip,
    }

    if enabled is False:
        return RouteDecision(
            **base,
            status="SKIP_DISABLED",
            reason="ASSET_DISABLED",
            primary_source=None,
            dataset=None,
            listing_exchange_verification=None,
        )

    if short_interest_eligible is False:
        return RouteDecision(
            **base,
            status="SKIP_NOT_ELIGIBLE",
            reason="SHORT_INTEREST_NOT_ELIGIBLE",
            primary_source=None,
            dataset=None,
            listing_exchange_verification=None,
        )

    if short_interest_eligible is None:
        return RouteDecision(
            **base,
            status="SKIP_ELIGIBILITY_NOT_ASSESSED",
            reason="SHORT_INTEREST_ELIGIBILITY_NOT_ASSESSED",
            primary_source=None,
            dataset=None,
            listing_exchange_verification=None,
        )

    # O Master Universe Validator já protege a estrutura global.
    # Aqui fazemos os requisitos específicos de identidade
    # necessários ao Short Interest.

    if not ticker:
        decision = blocked_decision(
            asset_key,
            "SHORT_INTEREST_IDENTITY_MISSING_TICKER",
            asset,
        )
        decision.status = "BLOCKED_IDENTITY"
        return decision

    if not issuer_name:
        decision = blocked_decision(
            ticker,
            "SHORT_INTEREST_IDENTITY_MISSING_ISSUER",
            asset,
        )
        decision.status = "BLOCKED_IDENTITY"
        return decision

    if not security_name:
        decision = blocked_decision(
            ticker,
            "SHORT_INTEREST_IDENTITY_MISSING_SECURITY",
            asset,
        )
        decision.status = "BLOCKED_IDENTITY"
        return decision

    if not listing_exchange:
        decision = blocked_decision(
            ticker,
            "SHORT_INTEREST_IDENTITY_MISSING_EXCHANGE",
            asset,
        )
        decision.status = "BLOCKED_IDENTITY"
        return decision

    routing = asset.get("source_routing")

    if not isinstance(routing, dict):
        return blocked_decision(
            ticker,
            "SOURCE_ROUTING_MISSING",
            asset,
        )

    short_route = routing.get("short_interest")

    if not isinstance(short_route, dict):
        return blocked_decision(
            ticker,
            "SHORT_INTEREST_ROUTE_MISSING",
            asset,
        )

    primary_source = normalize_text(
        short_route.get("primary_source")
    )

    dataset = normalize_text(
        short_route.get("dataset")
    )

    exchange_verification = normalize_text(
        short_route.get(
            "listing_exchange_verification"
        )
    )

    if not primary_source:
        return blocked_decision(
            ticker,
            "SHORT_INTEREST_PRIMARY_SOURCE_MISSING",
            asset,
        )

    if not dataset:
        return blocked_decision(
            ticker,
            "SHORT_INTEREST_DATASET_MISSING",
            asset,
        )

    if (
        primary_source,
        dataset,
    ) not in SUPPORTED_PRIMARY_ROUTES:
        return blocked_decision(
            ticker,
            "SHORT_INTEREST_ROUTE_NOT_SUPPORTED",
            asset,
        )

    if not exchange_verification:
        return blocked_decision(
            ticker,
            "LISTING_EXCHANGE_VERIFICATION_MISSING",
            asset,
        )

    if exchange_verification != listing_exchange:
        return blocked_decision(
            ticker,
            "LISTING_EXCHANGE_ROUTE_MISMATCH",
            asset,
        )

    return RouteDecision(
        **base,
        status="READY",
        reason="PRIMARY_ROUTE_RESOLVED",
        primary_source=primary_source,
        dataset=dataset,
        listing_exchange_verification=exchange_verification,
    )


def resolve_routes(
    universe: dict[str, Any],
) -> list[RouteDecision]:
    assets = universe["assets"]

    decisions: list[RouteDecision] = []

    for asset_key in sorted(assets):
        asset = assets[asset_key]

        decisions.append(
            resolve_asset(
                asset_key=asset_key,
                asset=asset,
            )
        )

    return decisions


def print_decision(
    decision: RouteDecision,
) -> None:
    print("-" * 72)
    print(f"TICKER: {decision.ticker}")
    print(f"Status: {decision.status}")
    print(f"Reason: {decision.reason}")

    print(
        "Enabled:",
        decision.enabled,
    )

    print(
        "Short Interest eligible:",
        decision.short_interest_eligible,
    )

    print(
        "Exchange:",
        decision.listing_exchange or "N/D",
    )

    print(
        "CUSIP:",
        decision.cusip or "N/D",
    )

    print(
        "Primary source:",
        decision.primary_source or "N/D",
    )

    print(
        "Dataset:",
        decision.dataset or "N/D",
    )

    print(
        "Exchange verification:",
        decision.listing_exchange_verification or "N/D",
    )


def build_output(
    universe: dict[str, Any],
    decisions: list[RouteDecision],
) -> dict[str, Any]:
    ready = sum(
        1 for item in decisions
        if item.status == "READY"
    )

    skipped = sum(
        1 for item in decisions
        if item.status.startswith("SKIP_")
    )

    blocked = sum(
        1 for item in decisions
        if item.status.startswith("BLOCKED_")
    )

    return {
        "router_version": ROUTER_VERSION,
        "universe_version": universe.get(
            "universe_version"
        ),
        "domain": DOMAIN,
        "summary": {
            "total_assets": len(decisions),
            "ready": ready,
            "skipped": skipped,
            "blocked": blocked,
        },
        "routes": [
            asdict(decision)
            for decision in decisions
        ],
    }


def write_output(
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
            "Short Interest Source Router"
        )
    )

    parser.add_argument(
        "--universe",
        default=str(DEFAULT_UNIVERSE),
        help=(
            "Master Asset Universe. "
            "Default: automation/asset_universe_v3.json"
        ),
    )

    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Opcional: grava resultado de roteamento "
            "em JSON."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    universe_path = Path(args.universe)

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST SOURCE ROUTER")
    print(f"VERSION {ROUTER_VERSION}")
    print("=" * 72)
    print()
    print(f"Universe: {universe_path}")
    print()

    try:
        universe = load_json(universe_path)
    except RuntimeError as exc:
        print(f"ERRO OPERACIONAL: {exc}")
        print()
        print("RESULTADO: BLOCKED")
        return 2

    issues = validate_universe(universe)

    validation_errors = [
        issue
        for issue in issues
        if issue.severity == "ERROR"
    ]

    if validation_errors:
        print("[UNIVERSE VALIDATION]")
        print(
            f"Errors: {len(validation_errors)}"
        )

        for issue in validation_errors:
            print(
                f"  X {issue.code} "
                f"({issue.location})"
            )

        print()
        print("RESULTADO: BLOCKED")
        print(
            "Source Router nao executado porque "
            "o Master Asset Universe e invalido."
        )

        return 2

    print("[UNIVERSE VALIDATION]")
    print("Status: VALID")
    print()

    decisions = resolve_routes(universe)

    for decision in decisions:
        print_decision(decision)

    ready = sum(
        1 for item in decisions
        if item.status == "READY"
    )

    skipped = sum(
        1 for item in decisions
        if item.status.startswith("SKIP_")
    )

    blocked = sum(
        1 for item in decisions
        if item.status.startswith("BLOCKED_")
    )

    print("-" * 72)
    print()
    print("[SUMMARY]")
    print(f"Total:   {len(decisions)}")
    print(f"Ready:   {ready}")
    print(f"Skipped: {skipped}")
    print(f"Blocked: {blocked}")
    print()

    output_payload = build_output(
        universe=universe,
        decisions=decisions,
    )

    if args.output:
        output_path = Path(args.output)

        write_output(
            path=output_path,
            payload=output_payload,
        )

        print(f"Output: {output_path}")
        print()

    if blocked:
        print("RESULTADO: BLOCKED")
        print(
            "Existe pelo menos uma rota bloqueada."
        )
        return 1

    print("RESULTADO: ROUTES_RESOLVED")
    print(
        "Nenhuma API externa foi consultada."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())