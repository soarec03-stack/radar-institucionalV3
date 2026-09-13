import argparse
import copy
import json
from pathlib import Path

def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def unavailable_confidence(reason):
    return {"score": 0.0, "status": "UNAVAILABLE", "reason": reason}

def unavailable_provenance():
    return {
        "primary_source": "RADAR_UNIVERSE",
        "secondary_source": None,
        "source_url": None,
        "market_date": None,
        "retrieved_at": None,
        "status": "UNAVAILABLE",
        "attempts": 1,
        "sources_attempted": ["RADAR_UNIVERSE"]
    }

def point(value, confidence, provenance):
    return {
        "value": value,
        "confidence": copy.deepcopy(confidence),
        "provenance": copy.deepcopy(provenance)
    }

def apply(data):
    changed = []
    for asset in data.get("assets", []):
        ticker = asset.get("ticker", "UNKNOWN")
        conf = asset.get("confidence") or unavailable_confidence("Confidence ausente.")
        prov = asset.get("provenance") or unavailable_provenance()
        points = copy.deepcopy(asset.get("data_points") or {})

        if "price" not in points:
            if asset.get("price") is None:
                points["price"] = point(
                    None,
                    unavailable_confidence("Preco ainda nao disponivel."),
                    unavailable_provenance()
                )
            else:
                points["price"] = point(asset.get("price"), conf, prov)

        if "catalysts" not in points and "catalysts" in asset:
            catalysts = asset.get("catalysts")
            points["catalysts"] = point(
                catalysts,
                conf if catalysts else unavailable_confidence("Catalisadores nao informados."),
                prov if catalysts else unavailable_provenance()
            )

        for field in ("volume", "technical", "fundamentals", "institutional_flow", "macro"):
            if field not in points and field in asset:
                value = asset.get(field)
                points[field] = point(
                    value,
                    conf if value is not None else unavailable_confidence(f"{field} indisponivel."),
                    prov if value is not None else unavailable_provenance()
                )

        asset["data_points"] = points
        changed.append((ticker, sorted(points.keys())))

    return data, changed

def main():
    parser = argparse.ArgumentParser(description="Provenance por data point no Radar V3.")
    parser.add_argument("radar")
    parser.add_argument("--output", default="radar_v3_datapoints_test.json")
    args = parser.parse_args()

    data = load_json(args.radar)
    data, changed = apply(data)
    save_json(args.output, data)

    print("=" * 72)
    print("DATA-POINT PROVENANCE ENGINE V3")
    print("=" * 72)
    if not changed:
        print("AVISO: nenhum ativo encontrado em assets[].")
    else:
        for ticker, points in changed:
            print(f"{ticker}: {', '.join(points)}")
    print(f"\nOK Arquivo gerado: {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
