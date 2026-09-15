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

def upgrade(schema):
    defs = schema.setdefault("$defs", {})
    if "asset" not in defs:
        raise KeyError("$defs.asset nao encontrado em schema_v3.json")

    if "dataPoint" not in defs:
        defs["dataPoint"] = {
            "type": "object",
            "required": ["value", "confidence", "provenance"],
            "properties": {
                "value": {},
                "confidence": {"$ref": "#/$defs/confidence"},
                "provenance": {"$ref": "#/$defs/provenance"}
            },
            "additionalProperties": False
        }

    asset = defs["asset"]
    props = asset.setdefault("properties", {})
    props["data_points"] = {
        "type": "object",
        "description": "Valor, confidence e provenance por ponto de dado.",
        "properties": {
            "price": {"$ref": "#/$defs/dataPoint"},
            "volume": {"$ref": "#/$defs/dataPoint"},
            "technical": {"$ref": "#/$defs/dataPoint"},
            "fundamentals": {"$ref": "#/$defs/dataPoint"},
            "catalysts": {"$ref": "#/$defs/dataPoint"},
            "institutional_flow": {"$ref": "#/$defs/dataPoint"},
            "macro": {"$ref": "#/$defs/dataPoint"}
        },
        "additionalProperties": False
    }
    return schema

def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SCHEMA
    if not path.exists():
        print(f"ERRO: schema nao encontrado: {path}")
        return 2
    schema = load_json(path)
    backup = path.with_suffix(path.suffix + ".before_datapoints")
    if not backup.exists():
        save_json(backup, schema)
    save_json(path, upgrade(schema))
    print("OK schema_v3.json atualizado para provenance por data point.")
    print(f"Schema : {path}")
    print(f"Backup : {backup}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
