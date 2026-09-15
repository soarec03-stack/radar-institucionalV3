import argparse
import json
import math
import sys
from copy import deepcopy
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_POLICY = BASE_DIR / "automation" / "signal_policy_v3.json"


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(v)))


def linear_score(value, bad, good):
    value = float(value)
    bad = float(bad)
    good = float(good)
    if good == bad:
        return None
    ratio = (value - bad) / (good - bad)
    return clamp(ratio * 100.0)


def piecewise_score(value, points):
    value = float(value)
    pts = sorted((float(x), float(y)) for x, y in points)
    if value <= pts[0][0]:
        return clamp(pts[0][1])
    if value >= pts[-1][0]:
        return clamp(pts[-1][1])
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if x1 <= value <= x2:
            if x2 == x1:
                return clamp(y2)
            t = (value - x1) / (x2 - x1)
            return clamp(y1 + t * (y2 - y1))
    return None


def metric_score(value, rule):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    transform = rule.get("transform")
    if transform == "higher_better":
        return linear_score(value, rule["bad"], rule["good"])
    if transform == "lower_better":
        return linear_score(value, rule["bad"], rule["good"])
    if transform == "piecewise":
        return piecewise_score(value, rule["points"])
    return None


def weighted_domain_score(metrics, rules, minimum_coverage):
    total_weight = sum(float(r["weight"]) for r in rules.values())
    used_weight = 0.0
    weighted = 0.0
    details = {}

    for name, rule in rules.items():
        raw = metrics.get(name)
        score = metric_score(raw, rule)
        weight = float(rule["weight"])

        details[name] = {
            "raw": raw,
            "normalized": None if score is None else round(score, 4),
            "weight": weight,
            "used": score is not None,
        }

        if score is None:
            continue
        used_weight += weight
        weighted += score * weight

    coverage = used_weight / total_weight if total_weight else 0.0
    if coverage < minimum_coverage or used_weight == 0:
        return None, coverage, details

    # Renormalize only across available metric weights.
    score = weighted / used_weight
    return round(clamp(score), 4), round(coverage, 4), details


def catalyst_score(value, cfg, minimum_coverage):
    # Required contract:
    # value = {"items":[
    #   {"signed_impact": -100..100, "probability":0..1,
    #    "source_quality":0..1, "horizon_days":>=0}
    # ]}
    if not isinstance(value, dict):
        return None, 0.0, {"reason": "catalysts.value não é objeto estruturado."}

    items = value.get("items")
    if not isinstance(items, list) or len(items) < int(cfg.get("minimum_items", 1)):
        return None, 0.0, {"reason": "Lista estruturada de catalysts ausente."}

    decay_days = float(cfg.get("horizon_decay_days", 180))
    usable = []
    rejected = []

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            rejected.append(i)
            continue

        try:
            impact = float(item["signed_impact"])
            probability = float(item["probability"])
            source_quality = float(item["source_quality"])
            horizon = max(0.0, float(item["horizon_days"]))
        except (KeyError, TypeError, ValueError):
            rejected.append(i)
            continue

        impact = max(-100.0, min(100.0, impact))
        probability = max(0.0, min(1.0, probability))
        source_quality = max(0.0, min(1.0, source_quality))
        time_weight = math.exp(-horizon / decay_days) if decay_days > 0 else 1.0

        weight = probability * source_quality * time_weight
        usable.append({
            "index": i,
            "signed_impact": impact,
            "probability": probability,
            "source_quality": source_quality,
            "horizon_days": horizon,
            "weight": weight,
        })

    coverage = len(usable) / len(items) if items else 0.0
    if not usable or coverage < minimum_coverage:
        return None, round(coverage, 4), {
            "usable_items": usable,
            "rejected_indexes": rejected,
        }

    total_weight = sum(x["weight"] for x in usable)
    if total_weight <= 0:
        return None, round(coverage, 4), {
            "usable_items": usable,
            "rejected_indexes": rejected,
        }

    signed = sum(x["signed_impact"] * x["weight"] for x in usable) / total_weight
    score = clamp(50.0 + signed / 2.0)

    return round(score, 4), round(coverage, 4), {
        "signed_aggregate": round(signed, 4),
        "usable_items": usable,
        "rejected_indexes": rejected,
    }


def ensure_value_object(point):
    value = point.get("value")
    return value if isinstance(value, dict) else None


def apply_signal_engine(data, policy):
    min_coverage = float(policy["principles"]["minimum_metric_coverage"])
    domains = policy["domains"]
    changes = []

    for asset in data.get("assets", []):
        ticker = asset.get("ticker", "UNKNOWN")
        points = asset.get("data_points") or {}
        asset_changes = {}

        # Standard domains backed by matching data_points.
        for domain_name in ("fundamentals", "technical", "institutional_flow", "macro"):
            cfg = domains[domain_name]
            point = points.get(domain_name)
            if not isinstance(point, dict):
                asset_changes[domain_name] = {
                    "status": "UNAVAILABLE",
                    "score": None,
                    "coverage": 0.0,
                    "reason": f"data_points.{domain_name} ausente."
                }
                continue

            value = ensure_value_object(point)
            if value is None:
                asset_changes[domain_name] = {
                    "status": "UNAVAILABLE",
                    "score": None,
                    "coverage": 0.0,
                    "reason": f"data_points.{domain_name}.value não é objeto de métricas."
                }
                continue

            score, coverage, details = weighted_domain_score(
                value, cfg["metrics"], min_coverage
            )
            if score is not None:
                value[cfg["output_key"]] = score
                status = "CALCULATED"
                reason = "Sinal calculado deterministicamente a partir de métricas observáveis."
            else:
                status = "INSUFFICIENT_COVERAGE"
                reason = "Cobertura de métricas insuficiente para calcular o sinal."

            asset_changes[domain_name] = {
                "status": status,
                "score": score,
                "coverage": coverage,
                "reason": reason,
                "details": details,
            }

        # Momentum is derived from the technical data point, but from its own metrics.
        cfg = domains["momentum"]
        technical_point = points.get(cfg.get("source_domain", "technical"))
        if isinstance(technical_point, dict) and isinstance(technical_point.get("value"), dict):
            technical_value = technical_point["value"]
            score, coverage, details = weighted_domain_score(
                technical_value, cfg["metrics"], min_coverage
            )
            if score is not None:
                technical_value[cfg["output_key"]] = score
                status = "CALCULATED"
                reason = "Momentum calculado a partir das métricas técnicas de retorno/força relativa."
            else:
                status = "INSUFFICIENT_COVERAGE"
                reason = "Cobertura de métricas insuficiente para calcular momentum."
            asset_changes["momentum"] = {
                "status": status,
                "score": score,
                "coverage": coverage,
                "reason": reason,
                "details": details,
            }
        else:
            asset_changes["momentum"] = {
                "status": "UNAVAILABLE",
                "score": None,
                "coverage": 0.0,
                "reason": "data_points.technical ausente ou sem objeto de métricas."
            }

        # Catalysts require structured event items.
        cfg = domains["catalysts"]
        point = points.get("catalysts")
        if isinstance(point, dict):
            value = point.get("value")
            score, coverage, details = catalyst_score(value, cfg, min_coverage)
            if score is not None and isinstance(value, dict):
                value[cfg["output_key"]] = score
                status = "CALCULATED"
                reason = "Catalyst signal calculado a partir de impacto, probabilidade, fonte e horizonte."
            else:
                status = "INSUFFICIENT_COVERAGE"
                reason = "Catalysts sem estrutura suficiente para cálculo automático."
            asset_changes["catalysts"] = {
                "status": status,
                "score": score,
                "coverage": coverage,
                "reason": reason,
                "details": details,
            }
        else:
            asset_changes["catalysts"] = {
                "status": "UNAVAILABLE",
                "score": None,
                "coverage": 0.0,
                "reason": "data_points.catalysts ausente."
            }

        changes.append({
            "ticker": ticker,
            "signals": asset_changes,
        })

    return data, changes


def print_changes(changes):
    print("=" * 72)
    print("SIGNAL ENGINE V3 — NORMALIZAÇÃO 0–100")
    print("=" * 72)

    for asset in changes:
        print(asset["ticker"])
        for name, result in asset["signals"].items():
            score = result["score"]
            score_txt = "N/D" if score is None else f"{score:.2f}"
            print(
                f"  - {name}: {score_txt} "
                f"| coverage={result['coverage']:.0%} "
                f"| {result['status']}"
            )
            if result.get("reason"):
                print(f"      {result['reason']}")


def main():
    parser = argparse.ArgumentParser(
        description="Calcula sinais normalizados 0–100 a partir de métricas observáveis."
    )
    parser.add_argument("radar", nargs="?", default="radar_v3.json")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--output")
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

    data, changes = apply_signal_engine(deepcopy(data), policy)
    print_changes(changes)

    if args.output:
        save_json(args.output, data)
        print(f"\nOK Arquivo gerado: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
