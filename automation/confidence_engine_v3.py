import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = BASE_DIR / "automation" / "source_registry_v3.json"

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
    with Path(path).open("r", encoding="utf-8") as f:
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
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max(0.0, (now - dt.astimezone(timezone.utc)).total_seconds() / 3600.0)


def source_map(registry):
    return {s["id"]: s for s in registry.get("sources", [])}


def confidence_status(score):
    if score >= 0.85:
        return "VERIFIED"
    if score >= 0.60:
        return "PARTIAL"
    if score > 0:
        return "LOW"
    return "UNAVAILABLE"


def source_quality_score(provenance, registry):
    sources = source_map(registry)
    attempted = provenance.get("sources_attempted") or []

    ids = []
    primary = provenance.get("primary_source")
    secondary = provenance.get("secondary_source")

    if primary:
        ids.append(primary)
    if secondary:
        ids.append(secondary)
    for source_id in attempted:
        if source_id not in ids:
            ids.append(source_id)

    found = [sources[sid] for sid in ids if sid in sources]
    if not found:
        return 0.0, "Nenhuma fonte registrada encontrada."

    scores = [float(s.get("authority_score", 0)) for s in found]
    primary_score = scores[0]
    corroboration = (
        sum(scores[1:]) / len(scores[1:])
        if len(scores) > 1 else 0.0
    )

    final = min(1.0, primary_score * 0.8 + corroboration * 0.2)
    return final, f"{len(found)} fonte(s) registrada(s) considerada(s)."


def source_agreement_score(provenance, registry):
    attempted = provenance.get("sources_attempted") or []
    unique = list(dict.fromkeys(attempted))

    rules = registry.get("rules", {}).get("source_agreement", {})
    verified_min = int(rules.get("verified_minimum_sources", 2))
    partial_min = int(rules.get("partial_minimum_sources", 1))
    conflict_penalty = float(rules.get("conflict_penalty", 0.25))

    count = len(unique)
    if count >= verified_min:
        score = 1.0
    elif count >= partial_min:
        score = 0.65
    else:
        score = 0.0

    if provenance.get("conflict", False):
        score = max(0.0, score - conflict_penalty)

    return score, f"{count} fonte(s) tentada(s)."


def freshness_score(provenance, category, freshness_hours):
    retrieved = parse_dt(provenance.get("retrieved_at"))
    if retrieved is None:
        return 0.0, "retrieved_at ausente ou invalido."

    hours = age_hours(retrieved)
    max_age = float(freshness_hours.get(category, freshness_hours.get("OTHER", 168)))

    if hours <= max_age:
        score = 1.0
    elif hours <= max_age * 2:
        score = 0.5
    else:
        score = 0.0

    return score, f"Idade={hours:.1f}h; limite={max_age:.0f}h."


def verification_score(provenance, registry):
    sources = source_map(registry)
    primary = provenance.get("primary_source")
    prov_status = provenance.get("status")

    if not primary or primary not in sources:
        return 0.0, "Fonte primaria nao registrada."

    source = sources[primary]
    can_verify = bool(source.get("can_verify_critical_data", False))

    if prov_status == "VERIFIED" and can_verify:
        return 1.0, "Fonte primaria apta e provenance VERIFIED."
    if can_verify:
        return 0.70, "Fonte apta, mas provenance ainda nao VERIFIED."
    return 0.30, "Fonte nao habilitada para verificacao critica."


def infer_asset_category(asset, registry):
    provenance = asset.get("provenance") or {}
    primary = provenance.get("primary_source")
    sources = source_map(registry)

    if primary in sources:
        return sources[primary].get("category", "OTHER")

    if asset.get("asset_class") in {
        "EQUITY", "ETF", "INDEX", "FUTURE", "FX",
        "RATE", "COMMODITY", "CRYPTO"
    }:
        return "MARKET"
    return "OTHER"


def asset_completeness_score(asset):
    required = [
        "ticker", "name", "asset_class", "sector", "theme",
        "score", "decision", "risk", "provenance",
    ]
    present = sum(
        1 for field in required
        if asset.get(field) not in (None, "", [], {})
    )
    if asset.get("price") is not None:
        present += 1
    total = len(required) + 1
    return present / total, f"{present}/{total} campos principais preenchidos."


def datapoint_completeness_score(point):
    value = point.get("value")
    if value in (None, "", [], {}):
        return 0.0, "Data point sem valor utilizavel."
    return 1.0, "Data point possui valor utilizavel."


def weighted_confidence(provenance, category, completeness, registry, freshness_hours):
    weights = registry.get("scoring", {})

    sq, sq_reason = source_quality_score(provenance, registry)
    sa, sa_reason = source_agreement_score(provenance, registry)
    fr, fr_reason = freshness_score(provenance, category, freshness_hours)
    co, co_reason = completeness
    ve, ve_reason = verification_score(provenance, registry)

    score = (
        sq * float(weights.get("source_quality_weight", 0.30))
        + sa * float(weights.get("source_agreement_weight", 0.25))
        + fr * float(weights.get("freshness_weight", 0.20))
        + co * float(weights.get("completeness_weight", 0.15))
        + ve * float(weights.get("verification_weight", 0.10))
    )
    score = round(max(0.0, min(1.0, score)), 4)

    components = {
        "source_quality": round(sq, 4),
        "source_agreement": round(sa, 4),
        "freshness": round(fr, 4),
        "completeness": round(co, 4),
        "verification": round(ve, 4),
    }
    details = {
        "source_quality": sq_reason,
        "source_agreement": sa_reason,
        "freshness": fr_reason,
        "completeness": co_reason,
        "verification": ve_reason,
    }
    return score, components, details


def calculate_asset_confidence(asset, registry, freshness_hours):
    provenance = asset.get("provenance") or {}
    category = infer_asset_category(asset, registry)

    score, components, details = weighted_confidence(
        provenance,
        category,
        asset_completeness_score(asset),
        registry,
        freshness_hours,
    )

    return {
        "score": score,
        "status": confidence_status(score),
        "reason": (
            "Calculado automaticamente pelo Confidence Engine V3 "
            f"(asset-level). SQ={components['source_quality']}, "
            f"SA={components['source_agreement']}, "
            f"FR={components['freshness']}, "
            f"CO={components['completeness']}, "
            f"VE={components['verification']}."
        ),
        "components": components,
        "details": details,
    }


def calculate_datapoint_confidence(point_name, point, registry, freshness_hours):
    value = point.get("value")
    provenance = point.get("provenance") or {}
    prov_status = provenance.get("status")

    # Regra fundamental: ausencia de valor real nao pode receber confianca positiva.
    if value in (None, "", [], {}) or prov_status == "UNAVAILABLE":
        zero = {
            "source_quality": 0.0,
            "source_agreement": 0.0,
            "freshness": 0.0,
            "completeness": 0.0,
            "verification": 0.0,
        }
        return {
            "score": 0.0,
            "status": "UNAVAILABLE",
            "reason": (
                f"{point_name}: dado indisponivel; confidence fixada em 0.00."
            ),
            "components": zero,
            "details": {"rule": "UNAVAILABLE_OR_EMPTY_VALUE"},
        }

    category = DATA_POINT_CATEGORY.get(point_name, "OTHER")
    score, components, details = weighted_confidence(
        provenance,
        category,
        datapoint_completeness_score(point),
        registry,
        freshness_hours,
    )

    return {
        "score": score,
        "status": confidence_status(score),
        "reason": (
            f"{point_name}: confidence calculada automaticamente. "
            f"SQ={components['source_quality']}, "
            f"SA={components['source_agreement']}, "
            f"FR={components['freshness']}, "
            f"CO={components['completeness']}, "
            f"VE={components['verification']}."
        ),
        "components": components,
        "details": details,
    }


def apply_confidence_engine(data, registry, freshness_hours):
    changes = []

    for asset in data.get("assets", []):
        ticker = asset.get("ticker", "UNKNOWN")
        old_confidence = asset.get("confidence")

        asset_calc = calculate_asset_confidence(asset, registry, freshness_hours)
        asset["confidence"] = {
            "score": asset_calc["score"],
            "status": asset_calc["status"],
            "reason": asset_calc["reason"],
        }

        datapoint_results = {}
        for point_name, point in (asset.get("data_points") or {}).items():
            if not isinstance(point, dict):
                continue

            calc = calculate_datapoint_confidence(
                point_name,
                point,
                registry,
                freshness_hours,
            )

            point["confidence"] = {
                "score": calc["score"],
                "status": calc["status"],
                "reason": calc["reason"],
            }

            datapoint_results[point_name] = {
                "current": point["confidence"],
                "components": calc["components"],
                "details": calc["details"],
            }

        changes.append({
            "ticker": ticker,
            "previous": old_confidence,
            "current": asset["confidence"],
            "components": asset_calc["components"],
            "details": asset_calc["details"],
            "data_points": datapoint_results,
        })

    return data, changes


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Calcula confidence automaticamente no nivel do ativo "
            "e de cada data point do Radar Institucional V3."
        )
    )
    parser.add_argument("radar")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument(
        "--policy",
        default=str(BASE_DIR / "automation" / "data_quality_policy_v3.json")
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    radar_path = Path(args.radar)
    registry_path = Path(args.registry)
    policy_path = Path(args.policy)

    for path, label in [
        (radar_path, "radar"),
        (registry_path, "registry"),
        (policy_path, "policy"),
    ]:
        if not path.exists():
            print(f"ERRO: {label} nao encontrado: {path}")
            return 2

    try:
        data = load_json(radar_path)
        registry = load_json(registry_path)
        policy = load_json(policy_path)
    except json.JSONDecodeError as exc:
        print(f"ERRO: JSON invalido: {exc}")
        return 2

    data, changes = apply_confidence_engine(
        data,
        registry,
        policy.get("freshness_hours", {}),
    )

    print("=" * 72)
    print("CONFIDENCE ENGINE V3 — ASSET + DATA POINTS")
    print("=" * 72)

    for item in changes:
        current = item["current"]
        print(f"{item['ticker']}: ASSET {current['score']:.4f} / {current['status']}")
        for point_name, result in sorted(item["data_points"].items()):
            pc = result["current"]
            print(f"  {point_name}: {pc['score']:.4f} / {pc['status']}")

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"\nOK Arquivo gerado: {output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
