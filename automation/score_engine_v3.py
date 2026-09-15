import argparse
import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_POLICY = BASE_DIR / "automation" / "score_policy_v3.json"

DEFAULT_COMPONENTS = {
    "fundamental": {
        "max_points": 20,
        "source_path": "data_points.fundamentals",
        "signal_keys": ["normalized_score", "score", "fundamental_score"],
    },
    "technical": {
        "max_points": 20,
        "source_path": "data_points.technical",
        "signal_keys": ["normalized_score", "score", "technical_score"],
    },
    "momentum": {
        "max_points": 15,
        "source_path": "data_points.technical",
        "signal_keys": ["momentum_score"],
    },
    "institutional_flow": {
        "max_points": 15,
        "source_path": "data_points.institutional_flow",
        "signal_keys": ["normalized_score", "score", "institutional_flow_score"],
    },
    "catalysts": {
        "max_points": 15,
        "source_path": "data_points.catalysts",
        "signal_keys": ["normalized_score", "score", "catalyst_score"],
    },
    "macro": {
        "max_points": 10,
        "source_path": "data_points.macro",
        "signal_keys": ["normalized_score", "score", "macro_score"],
    },
    "risk": {
        "max_points": 5,
        "source_path": "risk.score",
        "signal_keys": ["score"],
        "inverse": True,
    },
}


def load_json(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def get_by_path(obj, path):
    current = obj
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        if part not in current:
            return None
        current = current[part]
    return current


def get_component_policy(policy, component_name):
    defaults = DEFAULT_COMPONENTS[component_name]
    components = policy.get("components", {})
    component = components.get(component_name, {}) if isinstance(components, dict) else {}
    if not isinstance(component, dict):
        component = {}

    max_points = (
        component.get("max_points")
        or component.get("weight")
        or component.get("max_score")
        or defaults["max_points"]
    )
    source_path = (
        component.get("source_path")
        or component.get("source")
        or defaults["source_path"]
    )
    signal_keys = (
        component.get("signal_keys")
        or component.get("normalized_keys")
        or component.get("score_keys")
        or defaults["signal_keys"]
    )
    inverse = component.get("inverse", defaults.get("inverse", False))

    return {
        "max_points": float(max_points),
        "source_path": source_path,
        "signal_keys": signal_keys,
        "inverse": bool(inverse),
    }


def resolve_confidence_multiplier(data_point, policy):
    if not isinstance(data_point, dict):
        return 0.0

    confidence = data_point.get("confidence")
    if not isinstance(confidence, dict):
        return 0.0

    raw_score = confidence.get("score")
    try:
        numeric_score = float(raw_score)
        if 0.0 <= numeric_score <= 1.0:
            return numeric_score
    except (TypeError, ValueError):
        pass

    status = str(confidence.get("status", "UNAVAILABLE")).upper()
    confidence_policy = policy.get("confidence_adjustment", {})
    if not isinstance(confidence_policy, dict):
        confidence_policy = {}

    status_multipliers = (
        confidence_policy.get("status_multipliers")
        or confidence_policy.get("multipliers")
        or confidence_policy
    )
    if not isinstance(status_multipliers, dict):
        status_multipliers = {}

    defaults = {
        "VERIFIED": 1.00,
        "PARTIAL": 0.85,
        "LOW": 0.50,
        "UNAVAILABLE": 0.00,
    }

    fallback = status_multipliers.get(status, defaults.get(status, 0.0))
    try:
        fallback = float(fallback)
    except (TypeError, ValueError):
        fallback = defaults.get(status, 0.0)

    return clamp(fallback, 0.0, 1.0)


def extract_signal(data_point, signal_keys):
    if not isinstance(data_point, dict):
        return None, "data point ausente."

    value = data_point.get("value")
    if value is None:
        return None, "data point sem value."

    if isinstance(value, (int, float)):
        signal = float(value)
        if 0.0 <= signal <= 100.0:
            return signal, None
        return None, "value numérico fora do intervalo 0–100."

    if not isinstance(value, dict):
        return None, "data point value não contém objeto de sinais."

    for key in signal_keys:
        raw = value.get(key)
        if raw is None:
            continue
        try:
            signal = float(raw)
        except (TypeError, ValueError):
            continue
        if 0.0 <= signal <= 100.0:
            return signal, None

    keys_text = ", ".join(signal_keys)
    return None, (
        f"data point value não contém sinal normalizado 0–100 ({keys_text})."
    )


def extract_risk_signal(source_obj):
    """
    Aceita dois formatos:
      1) source_path = risk.score  -> source_obj é número
      2) source_path = risk        -> source_obj é dict com score
    """
    if isinstance(source_obj, (int, float)):
        risk_score = float(source_obj)

    elif isinstance(source_obj, dict):
        raw = source_obj.get("score")
        try:
            risk_score = float(raw)
        except (TypeError, ValueError):
            return None, "risk.score ausente ou inválido."

    else:
        return None, "risk ausente."

    if not 0.0 <= risk_score <= 100.0:
        return None, "risk.score fora do intervalo 0–100."

    favorable_signal = 100.0 - risk_score
    return favorable_signal, (
        "Risk score invertido: menor risco gera maior contribuição."
    )


def calculate_component(asset, component_name, policy):
    component_policy = get_component_policy(policy, component_name)

    max_points = component_policy["max_points"]
    source_path = component_policy["source_path"]
    signal_keys = component_policy["signal_keys"]

    source_obj = get_by_path(asset, source_path)

    if source_obj is None:
        return {
            "name": component_name,
            "points": 0.0,
            "max_points": max_points,
            "signal": None,
            "confidence_multiplier": 0.0,
            "available": False,
            "reason": f"{source_path} ausente.",
        }

    if component_name == "risk":
        signal, reason = extract_risk_signal(source_obj)

        if signal is None:
            return {
                "name": component_name,
                "points": 0.0,
                "max_points": max_points,
                "signal": None,
                "confidence_multiplier": 1.0,
                "available": False,
                "reason": reason,
            }

        points = (signal / 100.0) * max_points

        return {
            "name": component_name,
            "points": round(points, 4),
            "max_points": max_points,
            "signal": round(signal, 4),
            "confidence_multiplier": 1.0,
            "available": True,
            "reason": reason,
        }

    signal, signal_reason = extract_signal(source_obj, signal_keys)

    if signal is None:
        return {
            "name": component_name,
            "points": 0.0,
            "max_points": max_points,
            "signal": None,
            "confidence_multiplier": resolve_confidence_multiplier(source_obj, policy),
            "available": False,
            "reason": signal_reason,
        }

    confidence_multiplier = resolve_confidence_multiplier(source_obj, policy)

    if confidence_multiplier <= 0:
        return {
            "name": component_name,
            "points": 0.0,
            "max_points": max_points,
            "signal": round(signal, 4),
            "confidence_multiplier": confidence_multiplier,
            "available": False,
            "reason": "Sinal disponível, porém confidence indisponível ou igual a zero.",
        }

    raw_points = (signal / 100.0) * max_points
    adjusted_points = raw_points * confidence_multiplier

    return {
        "name": component_name,
        "points": round(adjusted_points, 4),
        "max_points": max_points,
        "signal": round(signal, 4),
        "confidence_multiplier": round(confidence_multiplier, 4),
        "available": True,
        "reason": (
            "Sinal normalizado e ajustado pela confidence numérica "
            f"do data point ({confidence_multiplier:.4f})."
        ),
    }


def score_label(score):
    if score >= 85:
        return "STRONG_BUY"
    if score >= 75:
        return "BUY"
    if score >= 65:
        return "WATCH_ACCUMULATE"
    if score >= 50:
        return "HOLD"
    if score >= 35:
        return "CAUTION"
    return "AVOID"


def get_coverage_threshold(policy, key, default):
    coverage = policy.get("coverage", {})
    if not isinstance(coverage, dict):
        return default

    value = coverage.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_asset_score(asset, policy):
    components = {}
    raw_score = 0.0
    available_score = 0.0
    total_weight = 0.0

    for component_name in DEFAULT_COMPONENTS:
        result = calculate_component(asset, component_name, policy)
        components[component_name] = result

        total_weight += result["max_points"]

        if result["available"]:
            available_score += result["max_points"]

        raw_score += result["points"]

    coverage = available_score / total_weight if total_weight > 0 else 0.0

    minimum_reliable = get_coverage_threshold(
        policy, "minimum_reliable_score", 0.70
    )
    minimum_publication = get_coverage_threshold(
        policy, "minimum_publication", 0.85
    )

    analytically_usable = coverage >= minimum_reliable
    publishable = coverage >= minimum_publication

    raw_score = round(raw_score, 2)
    available_score = round(available_score, 2)

    normalized_score = None
    if analytically_usable and available_score > 0:
        normalized_score = round(
            clamp((raw_score / available_score) * 100.0, 0.0, 100.0),
            2,
        )

    if publishable:
        status = "CALCULATED"
        label = score_label(normalized_score)
    elif analytically_usable:
        status = "PARTIAL"
        label = None
    else:
        status = "INSUFFICIENT_DATA"
        label = None

    return {
        "status": status,
        "total": raw_score,  # compatibilidade: total = contribuição bruta
        "raw_score": raw_score,
        "available_score": available_score,
        "normalized_score": normalized_score,
        "label": label,
        "coverage": round(coverage, 4),
        "analytically_usable": analytically_usable,
        "publishable": publishable,
        "components": components,
    }

def write_score_to_asset(asset, result):
    # O schema V3 define o campo oficial como asset["score"].
    radar_score = asset.get("score")
    if not isinstance(radar_score, dict):
        radar_score = {}
        asset["score"] = radar_score

    # Remove campo transitório antigo, caso tenha sido criado por versões de teste.
    asset.pop("radar_score", None)

    radar_score["total"] = result["total"]
    radar_score["status"] = result["status"]
    radar_score["raw_score"] = result["raw_score"]
    radar_score["available_score"] = result["available_score"]
    radar_score["normalized_score"] = result["normalized_score"]
    radar_score["coverage"] = result["coverage"]
    radar_score["analytically_usable"] = result["analytically_usable"]
    radar_score["publishable"] = result["publishable"]

    # Label operacional só existe quando o score é publicável.
    if result["label"] is None:
        radar_score.pop("label", None)
    else:
        radar_score["label"] = result["label"]

    # Preserva o contrato legado dos sete componentes no nível do score.
    for name, component in result["components"].items():
        radar_score[name] = round(component["points"], 2)

def format_signal(signal):
    return "N/D" if signal is None else f"{signal:.1f}"


def print_asset_result(ticker, result):
    normalized = (
        "N/D"
        if result["normalized_score"] is None
        else f"{result['normalized_score']:.2f}"
    )
    label = result["label"] or "N/D"

    print(
        f"{ticker}: status={result['status']} | "
        f"raw={result['raw_score']:.2f}/100 | "
        f"available={result['available_score']:.2f}/100 | "
        f"normalized={normalized}/100 | "
        f"coverage={result['coverage']:.0%} | "
        f"analytically_usable={'SIM' if result['analytically_usable'] else 'NAO'} | "
        f"publishable={'SIM' if result['publishable'] else 'NAO'} | "
        f"label={label}"
    )

    for name, component in result["components"].items():
        signal_text = format_signal(component["signal"])
        print(
            f"  - {name}: "
            f"{component['points']:.2f}/{component['max_points']:.0f} | "
            f"signal={signal_text} | "
            f"{component['reason']}"
        )

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Calcula Radar Score V3 com sinais normalizados, pesos "
            "e confidence.score numérico."
        )
    )

    parser.add_argument("input", help="Arquivo Radar V3 de entrada.")
    parser.add_argument("--output", required=True, help="Arquivo de saída.")
    parser.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY),
        help="score_policy_v3.json."
    )

    args = parser.parse_args()

    try:
        radar = load_json(args.input)
        policy = load_json(args.policy)
    except Exception as exc:
        print(f"ERRO: {exc}")
        return 2

    assets = radar.get("assets", [])

    if not isinstance(assets, list) or not assets:
        print("ERRO: radar sem assets.")
        return 2

    print("=" * 72)
    print("SCORE ENGINE V3 — RADAR SCORE 0–100")
    print("=" * 72)

    results = []

    for asset in assets:
        ticker = asset.get("ticker", "N/D")
        result = calculate_asset_score(asset, policy)

        write_score_to_asset(asset, result)
        results.append((ticker, result))
        print_asset_result(ticker, result)

    not_publishable = [
        ticker
        for ticker, result in results
        if not result["publishable"]
    ]

    if not_publishable:
        print()
        print(
            "AVISO: label operacional bloqueado enquanto coverage estiver "
            "abaixo do mínimo de publicação."
        )

    try:
        save_json(args.output, radar)
    except Exception as exc:
        print(f"ERRO ao salvar saída: {exc}")
        return 2

    print()
    print(f"OK Arquivo gerado: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
