import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_hours(dt):
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt.astimezone(timezone.utc)).total_seconds() / 3600


def confidence_band(score, policy):
    bands = policy["confidence_bands"]
    for name, limits in bands.items():
        if limits["min"] <= score <= limits["max"]:
            return name
    return None


def infer_source_category(asset):
    asset_class = asset.get("asset_class")
    if asset_class in {"EQUITY", "ETF", "INDEX", "FUTURE", "FX", "RATE", "COMMODITY", "CRYPTO"}:
        return "MARKET"
    return "OTHER"


def add_issue(issues, severity, code, entity, message):
    issues.append({
        "severity": severity,
        "code": code,
        "entity": entity,
        "message": message
    })


def evaluate(data, policy):
    issues = []
    metrics = {
        "assets_total": 0,
        "assets_with_price": 0,
        "assets_verified": 0,
        "assets_stale": 0,
        "critical_issues": 0,
        "warnings": 0
    }

    assets = data.get("assets", [])
    metrics["assets_total"] = len(assets)

    min_asset_conf = policy["publication"]["minimum_asset_confidence"]

    for asset in assets:
        ticker = asset.get("ticker", "UNKNOWN")
        entity = f"asset:{ticker}"
        price = asset.get("price")
        conf = asset.get("confidence") or {}
        prov = asset.get("provenance") or {}

        if price is None:
            add_issue(
                issues, "CRITICAL", "PRICE_UNAVAILABLE", entity,
                "Preço atual indisponível."
            )
        else:
            metrics["assets_with_price"] += 1

        score = conf.get("score")
        status = conf.get("status")

        if score is None:
            add_issue(
                issues, "CRITICAL", "CONFIDENCE_MISSING", entity,
                "confidence.score ausente."
            )
        else:
            expected = confidence_band(score, policy)
            if expected is None:
                add_issue(
                    issues, "CRITICAL", "CONFIDENCE_OUT_OF_RANGE", entity,
                    f"confidence.score={score} fora das faixas da política."
                )
            elif status != expected:
                add_issue(
                    issues, "WARNING", "CONFIDENCE_STATUS_MISMATCH", entity,
                    f"confidence.status='{status}' deveria ser '{expected}' para score={score}."
                )

            if score < min_asset_conf:
                add_issue(
                    issues, "WARNING", "LOW_PUBLICATION_CONFIDENCE", entity,
                    f"Confiança {score:.2f} abaixo do mínimo de publicação {min_asset_conf:.2f}."
                )

        prov_status = prov.get("status")
        if prov_status == "VERIFIED":
            metrics["assets_verified"] += 1

        source = prov.get("primary_source")
        if not source:
            add_issue(
                issues, "CRITICAL", "PRIMARY_SOURCE_MISSING", entity,
                "Fonte primária ausente."
            )

        retrieved_at = parse_dt(prov.get("retrieved_at"))
        if retrieved_at is None:
            add_issue(
                issues, "CRITICAL", "RETRIEVED_AT_INVALID", entity,
                "provenance.retrieved_at ausente ou inválido."
            )
        else:
            category = infer_source_category(asset)
            max_age = policy["freshness_hours"].get(category, 168)
            hours = age_hours(retrieved_at)
            if hours is not None and hours > max_age:
                metrics["assets_stale"] += 1
                add_issue(
                    issues, "WARNING", "STALE_DATA", entity,
                    f"Dado com {hours:.1f}h; limite para {category} é {max_age}h."
                )

        if (
            policy["publication"]["require_verified_price_provenance"]
            and price is not None
            and prov_status != "VERIFIED"
        ):
            add_issue(
                issues, "WARNING", "PRICE_NOT_VERIFIED", entity,
                "Preço presente, mas provenance.status não é VERIFIED."
            )

        attempts = prov.get("attempts")
        attempted_sources = prov.get("sources_attempted", [])
        if attempts is not None and attempts < 1:
            add_issue(
                issues, "WARNING", "INVALID_ATTEMPTS", entity,
                "provenance.attempts deve ser >= 1."
            )
        if attempts and attempted_sources and attempts > len(attempted_sources):
            add_issue(
                issues, "WARNING", "ATTEMPTS_SOURCE_MISMATCH", entity,
                "Número de tentativas maior que a lista de fontes tentadas."
            )

    regime_conf = (data.get("market_regime") or {}).get("confidence") or {}
    regime_score = regime_conf.get("score")
    min_regime = policy["publication"]["minimum_market_regime_confidence"]
    if regime_score is None:
        add_issue(
            issues, "CRITICAL", "REGIME_CONFIDENCE_MISSING", "market_regime",
            "market_regime.confidence.score ausente."
        )
    elif regime_score < min_regime:
        add_issue(
            issues, "WARNING", "LOW_REGIME_CONFIDENCE", "market_regime",
            f"Confiança do regime {regime_score:.2f} abaixo do mínimo {min_regime:.2f}."
        )

    for issue in issues:
        if issue["severity"] == "CRITICAL":
            metrics["critical_issues"] += 1
        elif issue["severity"] == "WARNING":
            metrics["warnings"] += 1

    run_status = (data.get("radar_run") or {}).get("status")
    publish_allowed = True
    blockers = []

    if run_status == "PUBLISHED":
        if policy["publication"]["block_on_critical_issues"] and metrics["critical_issues"] > 0:
            publish_allowed = False
            blockers.append("Existem problemas críticos de qualidade.")

        if policy["publication"]["block_on_unavailable_price"]:
            missing_prices = [a.get("ticker") for a in assets if a.get("price") is None]
            if missing_prices:
                publish_allowed = False
                blockers.append(
                    "Ativos sem preço: " + ", ".join(str(x) for x in missing_prices)
                )

        low_conf = [
            a.get("ticker")
            for a in assets
            if (a.get("confidence") or {}).get("score", 0) < min_asset_conf
        ]
        if low_conf:
            publish_allowed = False
            blockers.append(
                "Ativos abaixo do confidence mínimo: " + ", ".join(str(x) for x in low_conf)
            )

        if regime_score is None or regime_score < min_regime:
            publish_allowed = False
            blockers.append("Market regime abaixo do confidence mínimo.")

    return issues, metrics, publish_allowed, blockers


def print_report(data, issues, metrics, publish_allowed, blockers):
    print("=" * 72)
    print("DATA QUALITY + SOURCE CONFIDENCE — RADAR INSTITUCIONAL V3")
    print("=" * 72)

    print("\n[COBERTURA]")
    print(f"  Ativos totais          : {metrics['assets_total']}")
    print(f"  Com preço              : {metrics['assets_with_price']}")
    print(f"  Provenance VERIFIED    : {metrics['assets_verified']}")
    print(f"  Dados stale            : {metrics['assets_stale']}")

    print("\n[QUALIDADE]")
    print(f"  Problemas críticos     : {metrics['critical_issues']}")
    print(f"  Avisos                 : {metrics['warnings']}")

    if issues:
        print("\n[ISSUES]")
        for i in issues:
            mark = "X" if i["severity"] == "CRITICAL" else "!"
            print(f"  {mark} [{i['severity']}] {i['entity']} / {i['code']}")
            print(f"      {i['message']}")
    else:
        print("\n[ISSUES]")
        print("  OK Nenhum problema de qualidade detectado.")

    status = (data.get("radar_run") or {}).get("status")
    print("\n[PUBLICATION GATE]")
    print(f"  radar_run.status       : {status}")
    if status == "PUBLISHED":
        print(f"  Publicação permitida   : {'SIM' if publish_allowed else 'NAO'}")
        for blocker in blockers:
            print(f"  X {blocker}")
    else:
        print("  Modo DRAFT/VALIDATED: relatório informativo; gate rígido será aplicado em PUBLISHED.")

    print("\n" + "-" * 72)

    if metrics["critical_issues"] > 0:
        print("RESULTADO DATA QUALITY: REPROVADO")
        return 1
    elif metrics["warnings"] > 0:
        print("RESULTADO DATA QUALITY: APROVADO COM AVISOS")
        return 0
    else:
        print("RESULTADO DATA QUALITY: APROVADO")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Avalia qualidade, confidence, provenance e publication gate do Radar V3."
    )
    parser.add_argument(
        "radar",
        nargs="?",
        default="radar_v3.json",
        help="Arquivo radar_v3.json"
    )
    parser.add_argument(
        "--policy",
        default="automation/data_quality_policy_v3.json",
        help="Política de qualidade V3"
    )
    args = parser.parse_args()

    radar_path = Path(args.radar)
    policy_path = Path(args.policy)

    if not radar_path.exists():
        print(f"ERRO: radar não encontrado: {radar_path}")
        return 2
    if not policy_path.exists():
        print(f"ERRO: política não encontrada: {policy_path}")
        return 2

    try:
        data = load_json(radar_path)
        policy = load_json(policy_path)
    except json.JSONDecodeError as exc:
        print(f"ERRO: JSON inválido: {exc}")
        return 2

    issues, metrics, publish_allowed, blockers = evaluate(data, policy)
    return print_report(data, issues, metrics, publish_allowed, blockers)


if __name__ == "__main__":
    sys.exit(main())
