import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


DATA_POINT_CATEGORY = {
    "price": "MARKET",
    "volume": "MARKET",
    "technical": "TECHNICAL",
    "fundamentals": "COMPANY",
    "catalysts": "NEWS",
    "institutional_flow": "INSTITUTIONAL",
    "macro": "MACRO",
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def age_hours(dt):
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(
        0.0,
        (now - dt.astimezone(timezone.utc)).total_seconds() / 3600
    )


def confidence_band(score, policy):
    bands = policy["confidence_bands"]
    for name, limits in bands.items():
        if limits["min"] <= score <= limits["max"]:
            return name
    return None


def infer_source_category(asset):
    asset_class = asset.get("asset_class")
    if asset_class in {
        "EQUITY", "ETF", "INDEX", "FUTURE", "FX",
        "RATE", "COMMODITY", "CRYPTO"
    }:
        return "MARKET"
    return "OTHER"


def add_issue(issues, severity, code, entity, message):
    issues.append({
        "severity": severity,
        "code": code,
        "entity": entity,
        "message": message
    })


def _check_confidence(
    issues,
    entity,
    conf,
    policy,
    minimum=None,
    low_severity="WARNING",
):
    score = conf.get("score")
    status = conf.get("status")

    if score is None:
        add_issue(
            issues, "CRITICAL", "CONFIDENCE_MISSING", entity,
            "confidence.score ausente."
        )
        return None

    expected = confidence_band(score, policy)

    if expected is None:
        add_issue(
            issues, "CRITICAL", "CONFIDENCE_OUT_OF_RANGE", entity,
            f"confidence.score={score} fora das faixas da política."
        )
    elif status != expected:
        add_issue(
            issues, "WARNING", "CONFIDENCE_STATUS_MISMATCH", entity,
            f"confidence.status='{status}' deveria ser '{expected}' "
            f"para score={score}."
        )

    if minimum is not None and score < minimum:
        add_issue(
            issues, low_severity, "LOW_PUBLICATION_CONFIDENCE", entity,
            f"Confiança {score:.2f} abaixo do mínimo {minimum:.2f}."
        )

    return score


def _evaluate_provenance_freshness(
    issues,
    metrics,
    entity,
    provenance,
    category,
    policy,
    require_verified=False,
    unavailable=False,
):
    prov_status = provenance.get("status")

    if prov_status == "VERIFIED":
        metrics["data_points_verified"] += 1

    # Em UNAVAILABLE, retrieved_at=null é correto e não é erro adicional.
    if unavailable or prov_status == "UNAVAILABLE":
        return

    primary = provenance.get("primary_source")
    if not primary:
        add_issue(
            issues, "CRITICAL", "PRIMARY_SOURCE_MISSING", entity,
            "Fonte primária ausente."
        )

    retrieved_at = parse_dt(provenance.get("retrieved_at"))
    if retrieved_at is None:
        add_issue(
            issues, "CRITICAL", "RETRIEVED_AT_INVALID", entity,
            "provenance.retrieved_at ausente ou inválido."
        )
    else:
        max_age = policy["freshness_hours"].get(category, 168)
        hours = age_hours(retrieved_at)
        if hours is not None and hours > max_age:
            metrics["data_points_stale"] += 1
            add_issue(
                issues, "WARNING", "STALE_DATA", entity,
                f"Dado com {hours:.1f}h; limite para {category} é {max_age}h."
            )

    if require_verified and prov_status != "VERIFIED":
        add_issue(
            issues, "WARNING", "PROVENANCE_NOT_VERIFIED", entity,
            "Data point presente, mas provenance.status não é VERIFIED."
        )

    attempts = provenance.get("attempts")
    attempted_sources = provenance.get("sources_attempted", [])

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


def evaluate(data, policy):
    issues = []
    metrics = {
        "assets_total": 0,
        "assets_with_price": 0,
        "assets_verified": 0,
        "assets_stale": 0,
        "critical_issues": 0,
        "warnings": 0,
        "data_points_total": 0,
        "data_points_available": 0,
        "data_points_unavailable": 0,
        "data_points_verified": 0,
        "data_points_stale": 0,
        "data_points_low_confidence": 0,
    }

    assets = data.get("assets", [])
    metrics["assets_total"] = len(assets)

    min_asset_conf = policy["publication"]["minimum_asset_confidence"]
    dp_policy = policy.get("data_points", {})
    required_points = set(dp_policy.get("required_for_publication", ["price"]))
    min_conf = dp_policy.get("minimum_confidence", {})
    require_verified = dp_policy.get("require_verified_provenance", {})
    optional_unavailable_severity = dp_policy.get(
        "unavailable_optional_severity", "WARNING"
    )
    optional_low_severity = dp_policy.get(
        "low_confidence_optional_severity", "WARNING"
    )

    for asset in assets:
        ticker = asset.get("ticker", "UNKNOWN")
        entity = f"asset:{ticker}"
        price = asset.get("price")
        conf = asset.get("confidence") or {}
        prov = asset.get("provenance") or {}

        # Compatibilidade com a camada agregada existente.
        # Se data_points.price existir, a qualidade do preço será auditada
        # no nível canônico do data point para evitar dupla contagem.
        points = asset.get("data_points") or {}
        has_price_datapoint = isinstance(points.get("price"), dict)

        if price is None:
            if not has_price_datapoint:
                add_issue(
                    issues, "CRITICAL", "PRICE_UNAVAILABLE", entity,
                    "Preço atual indisponível."
                )
        else:
            metrics["assets_with_price"] += 1

        _check_confidence(
            issues,
            entity,
            conf,
            policy,
            minimum=min_asset_conf,
            low_severity="WARNING",
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
            # Mantemos compatibilidade: asset-level provenance continua requerido.
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

        # Nova auditoria por data point.
        for required_name in sorted(required_points):
            if required_name not in points:
                add_issue(
                    issues,
                    "CRITICAL",
                    "REQUIRED_DATA_POINT_MISSING",
                    f"{entity}.data_points.{required_name}",
                    f"Data point obrigatório '{required_name}' ausente."
                )

        for point_name, point in points.items():
            if not isinstance(point, dict):
                add_issue(
                    issues,
                    "CRITICAL",
                    "INVALID_DATA_POINT",
                    f"{entity}.data_points.{point_name}",
                    "Data point deve ser um objeto."
                )
                continue

            metrics["data_points_total"] += 1
            point_entity = f"{entity}.data_points.{point_name}"
            value = point.get("value")
            point_conf = point.get("confidence") or {}
            point_prov = point.get("provenance") or {}
            unavailable = (
                value in (None, "", [], {})
                or point_conf.get("status") == "UNAVAILABLE"
                or point_prov.get("status") == "UNAVAILABLE"
            )

            is_required = point_name in required_points
            minimum = min_conf.get(point_name)
            low_severity = (
                "CRITICAL" if is_required else optional_low_severity
            )

            score = _check_confidence(
                issues,
                point_entity,
                point_conf,
                policy,
                minimum=minimum,
                low_severity=low_severity,
            )

            if score is not None and minimum is not None and score < minimum:
                metrics["data_points_low_confidence"] += 1

            if unavailable:
                metrics["data_points_unavailable"] += 1
                severity = (
                    "CRITICAL"
                    if is_required
                    else optional_unavailable_severity
                )
                add_issue(
                    issues,
                    severity,
                    "DATA_POINT_UNAVAILABLE",
                    point_entity,
                    f"Data point '{point_name}' indisponível."
                )
            else:
                metrics["data_points_available"] += 1

            category = DATA_POINT_CATEGORY.get(point_name, "OTHER")
            _evaluate_provenance_freshness(
                issues,
                metrics,
                point_entity,
                point_prov,
                category,
                policy,
                require_verified=bool(require_verified.get(point_name, False)),
                unavailable=unavailable,
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
            f"Confiança do regime {regime_score:.2f} abaixo do mínimo "
            f"{min_regime:.2f}."
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
        if (
            policy["publication"]["block_on_critical_issues"]
            and metrics["critical_issues"] > 0
        ):
            publish_allowed = False
            blockers.append("Existem problemas críticos de qualidade.")

        if policy["publication"]["block_on_unavailable_price"]:
            missing_prices = [
                a.get("ticker")
                for a in assets
                if a.get("price") is None
            ]
            if missing_prices:
                publish_allowed = False
                blockers.append(
                    "Ativos sem preço: "
                    + ", ".join(str(x) for x in missing_prices)
                )

        low_conf_assets = [
            a.get("ticker")
            for a in assets
            if (a.get("confidence") or {}).get("score", 0) < min_asset_conf
        ]
        if low_conf_assets:
            publish_allowed = False
            blockers.append(
                "Ativos abaixo do confidence mínimo: "
                + ", ".join(str(x) for x in low_conf_assets)
            )

        for asset in assets:
            ticker = asset.get("ticker", "UNKNOWN")
            points = asset.get("data_points") or {}

            for required_name in sorted(required_points):
                point = points.get(required_name)

                if not isinstance(point, dict):
                    publish_allowed = False
                    blockers.append(
                        f"{ticker}.{required_name} obrigatório está ausente."
                    )
                    continue

                point_conf = point.get("confidence") or {}
                point_prov = point.get("provenance") or {}
                value = point.get("value")
                threshold = min_conf.get(required_name, 0)

                if value in (None, "", [], {}):
                    publish_allowed = False
                    blockers.append(
                        f"{ticker}.{required_name} está indisponível."
                    )

                if point_conf.get("score", 0) < threshold:
                    publish_allowed = False
                    blockers.append(
                        f"{ticker}.{required_name} abaixo do confidence mínimo "
                        f"{threshold:.2f}."
                    )

                if (
                    require_verified.get(required_name, False)
                    and point_prov.get("status") != "VERIFIED"
                ):
                    publish_allowed = False
                    blockers.append(
                        f"{ticker}.{required_name} sem provenance VERIFIED."
                    )

        if regime_score is None or regime_score < min_regime:
            publish_allowed = False
            blockers.append(
                "Market regime abaixo do confidence mínimo."
            )

    return issues, metrics, publish_allowed, blockers


def print_report(data, issues, metrics, publish_allowed, blockers):
    print("=" * 72)
    print("DATA QUALITY + SOURCE CONFIDENCE — RADAR INSTITUCIONAL V3")
    print("=" * 72)

    print("\n[COBERTURA]")
    print(f"  Ativos totais          : {metrics['assets_total']}")
    print(f"  Com preço              : {metrics['assets_with_price']}")
    print(f"  Asset provenance verif.: {metrics['assets_verified']}")
    print(f"  Asset stale            : {metrics['assets_stale']}")
    print(f"  Data points totais     : {metrics['data_points_total']}")
    print(f"  Data points disponíveis: {metrics['data_points_available']}")
    print(f"  Data points unavailable: {metrics['data_points_unavailable']}")
    print(f"  Data points VERIFIED   : {metrics['data_points_verified']}")
    print(f"  Data points stale      : {metrics['data_points_stale']}")
    print(f"  Data points low conf.  : {metrics['data_points_low_confidence']}")

    print("\n[QUALIDADE]")
    print(f"  Problemas críticos     : {metrics['critical_issues']}")
    print(f"  Avisos                 : {metrics['warnings']}")

    if issues:
        print("\n[ISSUES]")
        for issue in issues:
            mark = "X" if issue["severity"] == "CRITICAL" else "!"
            print(
                f"  {mark} [{issue['severity']}] "
                f"{issue['entity']} / {issue['code']}"
            )
            print(f"      {issue['message']}")
    else:
        print("\n[ISSUES]")
        print("  OK Nenhum problema de qualidade detectado.")

    status = (data.get("radar_run") or {}).get("status")
    print("\n[PUBLICATION GATE]")
    print(f"  radar_run.status       : {status}")
    if status == "PUBLISHED":
        print(
            f"  Publicação permitida   : "
            f"{'SIM' if publish_allowed else 'NAO'}"
        )
        for blocker in blockers:
            print(f"  X {blocker}")
    else:
        print(
            "  Modo DRAFT/VALIDATED: relatório informativo; "
            "gate rígido será aplicado em PUBLISHED."
        )

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
        description=(
            "Avalia qualidade, confidence, provenance por ativo e por "
            "data point, freshness e publication gate do Radar V3."
        )
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
        print(f"ERRO: policy não encontrada: {policy_path}")
        return 2

    try:
        data = load_json(radar_path)
        policy = load_json(policy_path)
    except json.JSONDecodeError as exc:
        print(f"ERRO: JSON inválido: {exc}")
        return 2

    issues, metrics, publish_allowed, blockers = evaluate(data, policy)
    return print_report(
        data, issues, metrics, publish_allowed, blockers
    )


if __name__ == "__main__":
    sys.exit(main())
