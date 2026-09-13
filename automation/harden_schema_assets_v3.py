import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = BASE_DIR / "automation" / "schema_v3.json"


def main():
    schema_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SCHEMA

    if not schema_path.exists():
        print(f"ERRO: schema não encontrado: {schema_path}")
        return 2

    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    props = schema.get("properties", {})
    assets = props.get("assets")

    if not isinstance(assets, dict):
        print("ERRO: properties.assets não encontrado no schema.")
        return 2

    assets["minItems"] = 1

    with schema_path.open("w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("OK schema_v3.json endurecido.")
    print("assets[] agora exige minItems = 1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
