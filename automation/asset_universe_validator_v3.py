"""
RADAR INSTITUCIONAL V3
V3.4D.1C-A - MASTER ASSET UNIVERSE VALIDATOR

Responsabilidade
----------------
Validar a integridade estrutural e semântica do Master Asset Universe.

Este módulo NÃO:
- consulta APIs externas;
- coleta dados de mercado;
- calcula métricas;
- calcula Confidence;
- calcula Signal;
- calcula Radar Score;
- modifica radar_v3.json;
- modifica o universo recebido.

Princípio:
    INVALID IDENTITY -> FAIL CLOSED

Exit codes:
    0 = VALID
    1 = BLOCKED por erro de validação
    2 = erro operacional / arquivo / JSON
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


VALIDATOR_VERSION = "3.4D.1C-A"
EXPECTED_SCHEMA_VERSION = "3.0"

DEFAULT_UNIVERSE = Path("automation/asset_universe_v3.json")

REQUIRED_DOMAINS = {
    "INSTITUTIONAL_HOLDINGS_13F",
    "SHORT_INTEREST",
    "OPTIONS",
    "TECHNICAL",
    "FUNDAMENTALS",
    "MACRO",
}

REQUIRED_ASSET_FIELDS = {
    "enabled",
    "ticker",
    "issuer_name",
    "security_name",
    "security_type",
    "country_of_issuer",
    "listing",
    "identifiers",
    "domain_eligibility",
    "source_routing",
}

REQUIRED_LISTING_FIELDS = {
    "exchange",
    "exchange_group",
    "currency",
}

# CUSIP tradicional: 9 caracteres alfanuméricos.
# Nesta etapa validamos formato/duplicidade, não fazemos lookup externo.
CUSIP_PATTERN = re.compile(r"^[A-Z0-9]{9}$")

# Ticker deliberadamente conservador.
# Permite exemplos como BRK.B e BF-B sem vincular o sistema
# aos três ativos piloto.
TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")

COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    location: str
    message: str


def add_error(
    issues: list[ValidationIssue],
    code: str,
    location: str,
    message: str,
) -> None:
    issues.append(
        ValidationIssue(
            severity="ERROR",
            code=code,
            location=location,
            message=message,
        )
    )


def add_warning(
    issues: list[ValidationIssue],
    code: str,
    location: str,
    message: str,
) -> None:
    issues.append(
        ValidationIssue(
            severity="WARNING",
            code=code,
            location=location,
            message=message,
        )
    )


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Arquivo nao encontrado: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"JSON invalido em {path}: "
            f"linha {exc.lineno}, coluna {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Falha ao ler {path}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "O Master Asset Universe deve possuir um objeto JSON na raiz."
        )

    return payload


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_root(
    universe: dict[str, Any],
    issues: list[ValidationIssue],
) -> None:
    schema_version = universe.get("schema_version")

    if schema_version != EXPECTED_SCHEMA_VERSION:
        add_error(
            issues,
            "INVALID_SCHEMA_VERSION",
            "schema_version",
            (
                f"Esperado {EXPECTED_SCHEMA_VERSION!r}; "
                f"recebido {schema_version!r}."
            ),
        )

    if not is_non_empty_string(universe.get("universe_version")):
        add_error(
            issues,
            "MISSING_UNIVERSE_VERSION",
            "universe_version",
            "universe_version deve ser string nao vazia.",
        )

    if not is_non_empty_string(universe.get("universe_name")):
        add_error(
            issues,
            "MISSING_UNIVERSE_NAME",
            "universe_name",
            "universe_name deve ser string nao vazia.",
        )

    supported_domains = universe.get("supported_domains")

    if not isinstance(supported_domains, list):
        add_error(
            issues,
            "INVALID_SUPPORTED_DOMAINS",
            "supported_domains",
            "supported_domains deve ser uma lista.",
        )
    else:
        normalized_domains: set[str] = set()

        for index, domain in enumerate(supported_domains):
            if not is_non_empty_string(domain):
                add_error(
                    issues,
                    "INVALID_SUPPORTED_DOMAIN",
                    f"supported_domains[{index}]",
                    "Dominio deve ser string nao vazia.",
                )
                continue

            normalized_domains.add(domain.strip())

        missing_domains = REQUIRED_DOMAINS - normalized_domains

        for domain in sorted(missing_domains):
            add_error(
                issues,
                "REQUIRED_DOMAIN_NOT_DECLARED",
                "supported_domains",
                f"Dominio obrigatorio nao declarado: {domain}.",
            )

    assets = universe.get("assets")

    if not isinstance(assets, dict):
        add_error(
            issues,
            "INVALID_ASSETS_OBJECT",
            "assets",
            "assets deve ser um objeto JSON.",
        )
    elif not assets:
        add_error(
            issues,
            "EMPTY_ASSET_UNIVERSE",
            "assets",
            "Master Asset Universe nao pode estar vazio.",
        )


def validate_asset(
    asset_key: str,
    asset: Any,
    supported_domains: set[str],
    issues: list[ValidationIssue],
) -> None:
    base = f"assets.{asset_key}"

    if not isinstance(asset, dict):
        add_error(
            issues,
            "INVALID_ASSET_OBJECT",
            base,
            "Ativo deve ser um objeto JSON.",
        )
        return

    missing_fields = REQUIRED_ASSET_FIELDS - set(asset.keys())

    for field in sorted(missing_fields):
        add_error(
            issues,
            "MISSING_ASSET_FIELD",
            f"{base}.{field}",
            f"Campo obrigatorio ausente: {field}.",
        )

    ticker = asset.get("ticker")

    if not is_non_empty_string(ticker):
        add_error(
            issues,
            "MISSING_TICKER",
            f"{base}.ticker",
            "ticker deve ser string nao vazia.",
        )
    else:
        ticker = ticker.strip().upper()

        if asset_key != ticker:
            add_error(
                issues,
                "UNIVERSE_KEY_TICKER_MISMATCH",
                f"{base}.ticker",
                (
                    f"Chave do universo={asset_key!r}, "
                    f"ticker declarado={ticker!r}."
                ),
            )

        if not TICKER_PATTERN.fullmatch(ticker):
            add_error(
                issues,
                "INVALID_TICKER_FORMAT",
                f"{base}.ticker",
                f"Formato de ticker invalido: {ticker!r}.",
            )

    enabled = asset.get("enabled")

    if not isinstance(enabled, bool):
        add_error(
            issues,
            "INVALID_ENABLED_FLAG",
            f"{base}.enabled",
            "enabled deve ser booleano.",
        )

    for field in (
        "issuer_name",
        "security_name",
        "security_type",
    ):
        if not is_non_empty_string(asset.get(field)):
            add_error(
                issues,
                "INVALID_IDENTITY_FIELD",
                f"{base}.{field}",
                f"{field} deve ser string nao vazia.",
            )

    country = asset.get("country_of_issuer")

    if (
        not is_non_empty_string(country)
        or not COUNTRY_PATTERN.fullmatch(country.strip().upper())
    ):
        add_error(
            issues,
            "INVALID_COUNTRY_CODE",
            f"{base}.country_of_issuer",
            "country_of_issuer deve usar codigo ISO alpha-2.",
        )

    validate_listing(
        base=base,
        listing=asset.get("listing"),
        issues=issues,
    )

    validate_identifiers(
        base=base,
        identifiers=asset.get("identifiers"),
        issues=issues,
    )

    validate_domain_eligibility(
        base=base,
        eligibility=asset.get("domain_eligibility"),
        supported_domains=supported_domains,
        issues=issues,
    )

    validate_source_routing(
        base=base,
        routing=asset.get("source_routing"),
        issues=issues,
    )


def validate_listing(
    base: str,
    listing: Any,
    issues: list[ValidationIssue],
) -> None:
    location = f"{base}.listing"

    if not isinstance(listing, dict):
        add_error(
            issues,
            "INVALID_LISTING_OBJECT",
            location,
            "listing deve ser um objeto JSON.",
        )
        return

    for field in sorted(REQUIRED_LISTING_FIELDS):
        if field not in listing:
            add_error(
                issues,
                "MISSING_LISTING_FIELD",
                f"{location}.{field}",
                f"Campo de listing obrigatorio ausente: {field}.",
            )

    exchange = listing.get("exchange")
    exchange_group = listing.get("exchange_group")
    currency = listing.get("currency")

    if not is_non_empty_string(exchange):
        add_error(
            issues,
            "MISSING_LISTING_EXCHANGE",
            f"{location}.exchange",
            "exchange deve ser string nao vazia.",
        )

    if not is_non_empty_string(exchange_group):
        add_error(
            issues,
            "MISSING_EXCHANGE_GROUP",
            f"{location}.exchange_group",
            "exchange_group deve ser string nao vazia.",
        )

    if (
        not is_non_empty_string(currency)
        or not CURRENCY_PATTERN.fullmatch(currency.strip().upper())
    ):
        add_error(
            issues,
            "INVALID_CURRENCY",
            f"{location}.currency",
            "currency deve possuir codigo de 3 letras.",
        )


def validate_identifiers(
    base: str,
    identifiers: Any,
    issues: list[ValidationIssue],
) -> None:
    location = f"{base}.identifiers"

    if not isinstance(identifiers, dict):
        add_error(
            issues,
            "INVALID_IDENTIFIERS_OBJECT",
            location,
            "identifiers deve ser um objeto JSON.",
        )
        return

    cusip = identifiers.get("cusip")

    # CUSIP continua requerido para o universo piloto atual,
    # pois o domínio 13F homologado depende dele.
    if not is_non_empty_string(cusip):
        add_error(
            issues,
            "MISSING_CUSIP",
            f"{location}.cusip",
            "CUSIP obrigatorio para o contrato mestre atual.",
        )
        return

    normalized = cusip.strip().upper()

    if not CUSIP_PATTERN.fullmatch(normalized):
        add_error(
            issues,
            "INVALID_CUSIP_FORMAT",
            f"{location}.cusip",
            (
                "CUSIP deve possuir exatamente "
                "9 caracteres alfanumericos."
            ),
        )


def validate_domain_eligibility(
    base: str,
    eligibility: Any,
    supported_domains: set[str],
    issues: list[ValidationIssue],
) -> None:
    location = f"{base}.domain_eligibility"

    if not isinstance(eligibility, dict):
        add_error(
            issues,
            "INVALID_DOMAIN_ELIGIBILITY",
            location,
            "domain_eligibility deve ser um objeto JSON.",
        )
        return

    for domain in sorted(supported_domains):
        if domain not in eligibility:
            add_error(
                issues,
                "MISSING_DOMAIN_ELIGIBILITY",
                f"{location}.{domain}",
                (
                    f"Dominio {domain} deve ser explicitamente "
                    "true, false ou null."
                ),
            )
            continue

        value = eligibility.get(domain)

        if value is not None and not isinstance(value, bool):
            add_error(
                issues,
                "INVALID_DOMAIN_ELIGIBILITY_VALUE",
                f"{location}.{domain}",
                "Elegibilidade deve ser true, false ou null.",
            )


def validate_source_routing(
    base: str,
    routing: Any,
    issues: list[ValidationIssue],
) -> None:
    location = f"{base}.source_routing"

    if not isinstance(routing, dict):
        add_error(
            issues,
            "INVALID_SOURCE_ROUTING",
            location,
            "source_routing deve ser um objeto JSON.",
        )
        return

    # Nesta etapa o validator apenas verifica integridade básica.
    # A decisão específica de rota será responsabilidade do
    # short_interest_source_router_v3.py.
    for route_name, route in routing.items():
        route_location = f"{location}.{route_name}"

        if not isinstance(route, dict):
            add_error(
                issues,
                "INVALID_ROUTE_OBJECT",
                route_location,
                "Rota deve ser um objeto JSON.",
            )
            continue

        primary_source = route.get("primary_source")
        dataset = route.get("dataset")

        if not is_non_empty_string(primary_source):
            add_error(
                issues,
                "MISSING_PRIMARY_SOURCE",
                f"{route_location}.primary_source",
                "primary_source deve ser string nao vazia.",
            )

        if not is_non_empty_string(dataset):
            add_error(
                issues,
                "MISSING_DATASET",
                f"{route_location}.dataset",
                "dataset deve ser string nao vazia.",
            )


def validate_cross_asset_uniqueness(
    assets: dict[str, Any],
    issues: list[ValidationIssue],
) -> None:
    seen_tickers: dict[str, str] = {}
    seen_cusips: dict[str, str] = {}

    for asset_key, asset in assets.items():
        if not isinstance(asset, dict):
            continue

        ticker = asset.get("ticker")

        if is_non_empty_string(ticker):
            ticker_normalized = ticker.strip().upper()

            previous = seen_tickers.get(ticker_normalized)

            if previous is not None and previous != asset_key:
                add_error(
                    issues,
                    "DUPLICATE_TICKER",
                    f"assets.{asset_key}.ticker",
                    (
                        f"Ticker {ticker_normalized} tambem "
                        f"utilizado por {previous}."
                    ),
                )
            else:
                seen_tickers[ticker_normalized] = asset_key

        identifiers = asset.get("identifiers")

        if not isinstance(identifiers, dict):
            continue

        cusip = identifiers.get("cusip")

        if is_non_empty_string(cusip):
            cusip_normalized = cusip.strip().upper()

            previous = seen_cusips.get(cusip_normalized)

            if previous is not None and previous != asset_key:
                add_error(
                    issues,
                    "DUPLICATE_CUSIP",
                    f"assets.{asset_key}.identifiers.cusip",
                    (
                        f"CUSIP {cusip_normalized} tambem "
                        f"utilizado por {previous}."
                    ),
                )
            else:
                seen_cusips[cusip_normalized] = asset_key


def validate_universe(
    universe: dict[str, Any],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    validate_root(universe, issues)

    assets = universe.get("assets")

    if not isinstance(assets, dict) or not assets:
        return issues

    raw_supported_domains = universe.get("supported_domains", [])

    supported_domains = {
        item.strip()
        for item in raw_supported_domains
        if is_non_empty_string(item)
    }

    for asset_key, asset in assets.items():
        if not is_non_empty_string(asset_key):
            add_error(
                issues,
                "INVALID_ASSET_KEY",
                "assets",
                "Chave de ativo deve ser string nao vazia.",
            )
            continue

        normalized_key = asset_key.strip().upper()

        if asset_key != normalized_key:
            add_error(
                issues,
                "NON_CANONICAL_ASSET_KEY",
                f"assets.{asset_key}",
                (
                    "Chave do ativo deve estar normalizada "
                    "em maiusculas."
                ),
            )

        validate_asset(
            asset_key=asset_key,
            asset=asset,
            supported_domains=supported_domains,
            issues=issues,
        )

    validate_cross_asset_uniqueness(
        assets=assets,
        issues=issues,
    )

    return issues


def print_summary(
    universe_path: Path,
    universe: dict[str, Any],
    issues: list[ValidationIssue],
) -> None:
    errors = [
        issue for issue in issues
        if issue.severity == "ERROR"
    ]

    warnings = [
        issue for issue in issues
        if issue.severity == "WARNING"
    ]

    assets = universe.get("assets")

    asset_count = (
        len(assets)
        if isinstance(assets, dict)
        else 0
    )

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("MASTER ASSET UNIVERSE VALIDATOR")
    print(f"VERSION {VALIDATOR_VERSION}")
    print("=" * 72)
    print()
    print(f"Arquivo: {universe_path}")
    print(
        "Universe version:",
        universe.get("universe_version", "N/D"),
    )
    print(f"Assets encontrados: {asset_count}")
    print()

    if issues:
        print("[DIAGNOSTICOS]")

        for issue in issues:
            marker = "X" if issue.severity == "ERROR" else "!"

            print(
                f"  {marker} [{issue.severity}] "
                f"{issue.code}"
            )
            print(f"      Local: {issue.location}")
            print(f"      {issue.message}")

        print()

    print("[RESUMO]")
    print(f"  Errors:   {len(errors)}")
    print(f"  Warnings: {len(warnings)}")
    print()

    if errors:
        print("RESULTADO: BLOCKED")
        print(
            "Master Asset Universe NAO autorizado "
            "para consumo pelos collectors."
        )
    else:
        print("RESULTADO: VALID")
        print(
            "Master Asset Universe autorizado "
            "para consumo estrutural."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Radar Institucional V3 - "
            "Master Asset Universe Validator"
        )
    )

    parser.add_argument(
        "universe",
        nargs="?",
        default=str(DEFAULT_UNIVERSE),
        help=(
            "Arquivo JSON do Master Asset Universe. "
            "Default: automation/asset_universe_v3.json"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    universe_path = Path(args.universe)

    try:
        universe = load_json(universe_path)
    except RuntimeError as exc:
        print("=" * 72)
        print("RADAR INSTITUCIONAL V3")
        print("MASTER ASSET UNIVERSE VALIDATOR")
        print(f"VERSION {VALIDATOR_VERSION}")
        print("=" * 72)
        print()
        print(f"ERRO OPERACIONAL: {exc}")
        print()
        print("RESULTADO: BLOCKED")
        return 2

    issues = validate_universe(universe)

    print_summary(
        universe_path=universe_path,
        universe=universe,
        issues=issues,
    )

    has_errors = any(
        issue.severity == "ERROR"
        for issue in issues
    )

    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())