import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RADAR = BASE_DIR / "radar_v3.json"
DEFAULT_METRICS = BASE_DIR / "input" / "metrics_input_v3.json"

DOMAINS = ("fundamentals", "technical", "institutional_flow", "macro")


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def clean_metrics(metrics):
    if not isinstance(metrics, dict):
        return {}
    return {
        key: value
        for key, value in metrics.items()
        if value is not None
    }


def build_provenance(source):
    source = source or {}
    attempted = source.get("sources_attempted") or []
    primary = source.get("primary_source")
    secondary = source.get("secondary_source")
    retrieved_at = source.get("retrieved_at")
    market_date = source.get("market_date")
    source_url = source.get("source_url")

    if primary and primary not in attempted:
        attempted = [primary] + attempted
    if secondary and secondary not in attempted:
        attempted.append(secondary)

    has_data_source = bool(primary)
    has_timestamp = bool(retrieved_at)

    if has_data_source and has_timestamp:
        status = "PARTIAL"
    else:
        status = "UNAVAILABLE"

    return {
        "primary_source": primary or "RADAR_UNIVERSE",
        "secondary_source": secondary,
        "source_url": source_url,
        "market_date": market_date,
        "retrieved_at": retrieved_at,
        "status": status,
        "attempts": max(1, len(attempted)),
        "sources_attempted": attempted or ["RADAR_UNIVERSE"],
    }


def build_confidence(metrics, provenance):
    if not metrics:
        return {
            "score": 0.0,
            "status": "UNAVAILABLE",
            "reason": "Nenhuma métrica observável disponível."
        }

    # Confidence definitiva será recalculada pelo confidence_engine_v3.py.
    # Aqui registramos apenas um estado inicial conservador.
    if provenance.get("status") == "UNAVAILABLE":
        return {
            "score": 0.0,
            "status": "UNAVAILABLE",
            "reason": "Métricas presentes sem provenance utilizável."
        }

    return {
        "score": 0.60,
        "status": "PARTIAL",
        "reason": "Confidence inicial; recalcular pelo Confidence Engine V3."
    }


def merge_metrics(radar, metrics_input):
    result = deepcopy(radar)
    assets_by_ticker = {
        a.get("ticker"): a
        for a in result.get("assets", [])
        if a.get("ticker")
    }

    changes = []
    warnings = []

    for incoming in metrics_input.get("assets", []):
        ticker = incoming.get("ticker")
        asset = assets_by_ticker.get(ticker)

        if not asset:
            warnings.append(
                f"Ticker {ticker} ignorado: não existe em radar_v3.assets[]."
            )
            continue

        data_points = asset.setdefault("data_points", {})

        for domain in DOMAINS:
            block = incoming.get(domain)
            if not isinstance(block, dict):
                continue

            metrics = clean_metrics(block.get("metrics"))
            source = block.get("source") or {}

            # Não cria data point vazio.
            if not metrics:
                continue

            provenance = build_provenance(source)
            confidence = build_confidence(metrics, provenance)

            previous = deepcopy(data_points.get(domain))

            data_points[domain] = {
                "value": metrics,
                "confidence": confidence,
                "provenance": provenance
            }

            changes.append({
                "ticker": ticker,
                "domain": domain,
                "metrics_count": len(metrics),
                "previous": previous,
                "current": deepcopy(data_points[domain])
            })

    return result, changes, warnings


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Carrega métricas observáveis no Radar V3 sem calcular sinais "
            "ou scores."
        )
    )
    parser.add_argument(
        "--radar",
        default=str(DEFAULT_RADAR),
        help="Radar V3 de origem."
    )
    parser.add_argument(
        "--metrics",
        default=str(DEFAULT_METRICS),
        help="Arquivo de métricas observáveis."
    )
    parser.add_argument(
        "--output",
        default="radar_v3_metrics_test.json",
        help="Arquivo de saída."
    )
    args = parser.parse_args()

    radar_path = Path(args.radar)
    metrics_path = Path(args.metrics)
    output_path = Path(args.output)

    if not radar_path.exists():
        print(f"ERRO: radar não encontrado: {radar_path}")
        return 2
    if not metrics_path.exists():
        print(f"ERRO: métricas não encontradas: {metrics_path}")
        return 2

    try:
        radar = load_json(radar_path)
        metrics_input = load_json(metrics_path)
    except json.JSONDecodeError as exc:
        print(f"ERRO: JSON inválido: {exc}")
        return 2

    result, changes, warnings = merge_metrics(radar, metrics_input)

    print("=" * 72)
    print("METRICS LOADER V3 — MÉTRICAS OBSERVÁVEIS")
    print("=" * 72)

    if changes:
        for item in changes:
            print(
                f"OK {item['ticker']} / {item['domain']}: "
                f"{item['metrics_count']} métrica(s) carregada(s)"
            )
    else:
        print("AVISO: nenhuma métrica não-nula foi carregada.")

    for warning in warnings:
        print(f"! {warning}")

    save_json(output_path, result)
    print(f"\nOK Arquivo gerado: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
