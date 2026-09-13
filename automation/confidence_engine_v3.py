import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = BASE_DIR / "automation" / "source_registry_v3.json"


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
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max(
        0.0,
        (now - dt.astimezone(timezone.utc)).total_seconds() / 3600.0
    )


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

    # Fonte primária pesa mais; demais ajudam na confirmação.
    primary_score = scores[0]
    corroboration = sum(scores[1:]) / max(1, len(scores[1:])) if len(scores) > 1 else 0

    final = min(1.0, primary_score * 0.8 + corroboration * 0.2)
    return final, f"{len(found)} fonte(s) registrada(s) considerada(s)."


def source_agreement_score(provenance, registry):
    attempted = provenance.get("sources_attempted") or []
    unique = list(dict.fromkeys(attempted))

    rules = registry.get("rules", {}).get("source_agreement", {})
    verified_min = int(rules.get("verified_minimum_sources", 2))
    partial_min = int(rules.get("partial_minimum_sources", 1))

    conflict = bool(provenance.get("conflict", False))
    conflict_penalty = float(rules.get("conflict_penalty", 0.25))

    count = len(unique)

    if count >= verified_min:
        score = 1.0
    elif count >= partial_min:
        score = 0.65
    else:
        score = 0.0

    if conflict:
        score = max(0.0, score - conflict_penalty)

    reason = f"{count} fonte(s) tentada(s)"
    if conflict:
        reason += "; conflito sinalizado"

    return score, reason


def freshness_score(provenance, category, freshness_hours):
    retrieved = parse_dt(provenance.get("retrieved_at"))
    if retrieved is None:
        return 0.0, "retrieved_at ausente ou inválido."

    hours = age_hours(retrieved)
    max_age = float(freshness_hours.get(category, freshness_hours.get("OTHER", 168)))

    if hours <= max_age:
        score = 1.0
    elif hours <= max_age * 2:
        score = 0.5
    else:
        score = 0.0

    return score, f"Idade={hours:.1f}h; limite={max_age:.0f}h."


def completeness_score(asset):
    required = [
        "ticker",
        "name",
        "asset_class",
        "sector",
        "theme",
        "score",
        "decision",
        "risk",
        "provenance",
    ]

    present = 0
    for field in required:
        value = asset.get(field)
        if value not in (None, "", [], {}):
            present += 1

    # price é crítico, mas pode estar indisponível em DRAFT.
    if asset.get("price") is not None:
        present += 1

    total = len(required) + 1
    score = present / total
    return score, f"{present}/{total} campos principais preenchidos."


def verification_score(provenance, registry):
    sources = source_map(registry)
    primary = provenance.get("primary_source")
    prov_status = provenance.get("status")

    if not primary or primary not in sources:
        return 0.0, "Fonte primária não registrada."

    source = sources[primary]
    can_verify = bool(source.get("can_verify_critical_data", False))

    if prov_status == "VERIFIED" and can_verify:
        return 1.0, "Fonte primária apta a verificar dado crítico."
    if can_verify:
        return 0.70, "Fonte apta, mas provenance ainda não VERIFIED."
    return 0.30, "Fonte não habilitada para verificação crítica."


def infer_category(asset, registry):
    provenance = asset.get("provenance") or {}
    primary = provenance.get("primary_source")
    sources = source_map(registry)

    if primary in sources:
        return sources[primary].get("category", "OTHER")

    asset_class = asset.get("asset_class")
    if asset_class in {
        "EQUITY", "ETF", "INDEX", "FUTURE", "FX",
        "RATE", "COMMODITY", "CRYPTO"
    }:
        return "MARKET"

    return "OTHER"


def calculate_asset_confidence(asset, registry, freshness_hours):
    weights = registry.get("scoring", {})

    provenance = asset.get("provenance") or {}
    category = infer_category(asset, registry)

    sq, sq_reason = source_quality_score(provenance, registry)
    sa, sa_reason = source_agreement_score(provenance, registry)
    fr, fr_reason = freshness_score(provenance, category, freshness_hours)
    co, co_reason = completeness_score(asset)
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

    reasons = {
        "source_quality": sq_reason,
        "source_agreement": sa_reason,
        "freshness": fr_reason,
        "completeness": co_reason,
        "verification": ve_reason,
    }

    return {
        "score": score,
        "status": confidence_status(score),
        "reason": (
            f"Calculado automaticamente pelo Confidence Engine V3. "
            f"SQ={components['source_quality']}, "
            f"SA={components['source_agreement']}, "
            f"FR={components['freshness']}, "
            f"CO={components['completeness']}, "
            f"VE={components['verification']}."
        ),
        "components": components,
        "details": reasons
    }


def apply_confidence_engine(data, registry, freshness_hours):
    changes = []

    for asset in data.get("assets", []):
        ticker = asset.get("ticker", "UNKNOWN")
        old_confidence = asset.get("confidence")

        calculated = calculate_asset_confidence(
            asset,
            registry,
            freshness_hours
        )

        # O schema atual aceita apenas score/status/reason.
        asset["confidence"] = {
            "score": calculated["score"],
            "status": calculated["status"],
            "reason": calculated["reason"]
        }

        changes.append({
            "ticker": ticker,
            "previous": old_confidence,
            "current": asset["confidence"],
            "components": calculated["components"],
            "details": calculated["details"]
        })

    return data, changes


def main():
    parser = argparse.ArgumentParser(
        description="Calcula confidence.score automaticamente no Radar Institucional V3."
    )
    parser.add_argument("radar", help="Arquivo radar_v3.json ou JSON de trabalho")
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="source_registry_v3.json"
    )
    parser.add_argument(
        "--policy",
        default=str(BASE_DIR / "automation" / "data_quality_policy_v3.json"),
        help="data_quality_policy_v3.json"
    )
    parser.add_argument(
        "--output",
        help="Arquivo de saída. Se omitido, apenas exibe os cálculos."
    )
    args = parser.parse_args()

    radar_path = Path(args.radar)
    registry_path = Path(args.registry)
    policy_path = Path(args.policy)

    if not radar_path.exists():
        print(f"ERRO: radar não encontrado: {radar_path}")
        return 2
    if not registry_path.exists():
        print(f"ERRO: registry não encontrado: {registry_path}")
        return 2
    if not policy_path.exists():
        print(f"ERRO: policy não encontrada: {policy_path}")
        return 2

    try:
        data = load_json(radar_path)
        registry = load_json(registry_path)
        policy = load_json(policy_path)
    except json.JSONDecodeError as exc:
        print(f"ERRO: JSON inválido: {exc}")
        return 2

    freshness = policy.get("freshness_hours", {})
    data, changes = apply_confidence_engine(data, registry, freshness)

    print("=" * 72)
    print("CONFIDENCE ENGINE V3 — RADAR INSTITUCIONAL")
    print("=" * 72)

    for item in changes:
        current = item["current"]
        print(
            f"{item['ticker']}: "
            f"{current['score']:.4f} / {current['status']}"
        )
        comps = item["components"]
        print(
            "  "
            f"SQ={comps['source_quality']:.2f} "
            f"SA={comps['source_agreement']:.2f} "
            f"FR={comps['freshness']:.2f} "
            f"CO={comps['completeness']:.2f} "
            f"VE={comps['verification']:.2f}"
        )

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nOK Arquivo gerado: {output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
