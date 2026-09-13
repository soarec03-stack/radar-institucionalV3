import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = BASE_DIR / "automation" / "schema_v3.json"

def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SCHEMA
    if not path.exists():
        print(f"ERRO: schema nao encontrado: {path}")
        return 2

    schema = load_json(path)
    defs = schema.get("$defs", {})
    provenance = defs.get("provenance")

    if not provenance:
        print("ERRO: $defs.provenance nao encontrado.")
        return 2

    props = provenance.setdefault("properties", {})

    # UNAVAILABLE pode legitimamente nao ter data de recuperacao.
    props["retrieved_at"] = {
        "type": ["string", "null"],
        "format": "date-time"
    }

    # Mantemos market_date opcional/nullable caso ainda nao esteja assim.
    if "market_date" in props:
        props["market_date"] = {
            "type": ["string", "null"],
            "format": "date"
        }

    # Campos auxiliares tambem podem ser nulos.
    if "secondary_source" in props:
        props["secondary_source"] = {
            "type": ["string", "null"]
        }

    if "source_url" in props:
        props["source_url"] = {
            "type": ["string", "null"],
            "format": "uri"
        }

    save_json(path, schema)

    print("OK schema_v3.json ajustado para provenance UNAVAILABLE.")
    print("retrieved_at agora aceita string date-time ou null.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
