import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Permite importar o validador que está na mesma pasta automation/ quando
# este arquivo for executado no projeto real.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from validate_radar_v3 import load_json, validate_schema, validate_business_rules
except ImportError as exc:
    print("ERRO: nao foi possivel importar validate_radar_v3.py")
    print(f"Detalhe: {exc}")
    sys.exit(2)


def extract_json_text(raw_text: str) -> str:
    """Extrai JSON puro ou o primeiro bloco ```json ... ``` de um texto."""
    stripped = raw_text.strip()

    # Caso mais simples: arquivo inteiro já é JSON.
    if stripped.startswith("{"):
        return stripped

    # Preferência por bloco markdown explicitamente marcado como json.
    match = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, flags=re.I | re.S)
    if match:
        return match.group(1).strip()

    # Fallback: primeiro objeto JSON balanceado encontrado no texto.
    start = raw_text.find("{")
    if start == -1:
        raise ValueError("Nenhum objeto JSON encontrado na entrada.")

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(raw_text)):
        ch = raw_text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw_text[start : i + 1]

    raise ValueError("Objeto JSON iniciado, mas nao foi fechado corretamente.")


def load_input(input_path: Path):
    raw = input_path.read_text(encoding="utf-8")
    json_text = extract_json_text(raw)
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON extraido e invalido: linha {exc.lineno}, coluna {exc.colno}: {exc.msg}"
        ) from exc


def normalize(data: dict) -> dict:
    """Normalizações seguras, sem inventar dados financeiros."""
    normalized = json.loads(json.dumps(data, ensure_ascii=False))

    # Tickers são identificadores: padronizamos caixa alta e espaços externos.
    for asset in normalized.get("assets", []):
        ticker = asset.get("ticker")
        if isinstance(ticker, str):
            asset["ticker"] = ticker.strip().upper()

    for position in normalized.get("portfolio", {}).get("positions", []):
        ticker = position.get("ticker")
        if isinstance(ticker, str):
            position["ticker"] = ticker.strip().upper()

    for scenario_key in ("bull", "base", "bear"):
        scenario = normalized.get("scenarios", {}).get(scenario_key, {})
        for impact in scenario.get("asset_impacts", []):
            ticker = impact.get("ticker")
            if isinstance(ticker, str):
                impact["ticker"] = ticker.strip().upper()

    # Remove espaços externos em identificadores básicos.
    run = normalized.get("radar_run", {})
    if isinstance(run.get("run_id"), str):
        run["run_id"] = run["run_id"].strip()

    return normalized


def backup_existing(output_path: Path, backup_dir: Path):
    if not output_path.exists():
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"radar_v3_{stamp}.json"
    shutil.copy2(output_path, backup_path)
    return backup_path


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Extrai, normaliza e valida o input bruto do Radar Institucional V3 "
            "antes de gerar radar_v3.json."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="input/radar_input_v3.txt",
        help="Arquivo de entrada bruto (padrao: input/radar_input_v3.txt)",
    )
    parser.add_argument(
        "--schema",
        default="automation/schema_v3.json",
        help="Schema V3 (padrao: automation/schema_v3.json)",
    )
    parser.add_argument(
        "--output",
        default="radar_v3.json",
        help="Arquivo final (padrao: radar_v3.json)",
    )
    parser.add_argument(
        "--backup-dir",
        default="data/history/raw-json",
        help="Pasta de backup do radar_v3.json anterior",
    )
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Permite gerar o arquivo quando existirem apenas avisos.",
    )

    args = parser.parse_args()
    input_path = Path(args.input)
    schema_path = Path(args.schema)
    output_path = Path(args.output)
    backup_dir = Path(args.backup_dir)

    print("=" * 72)
    print("GERADOR / NORMALIZADOR — RADAR INSTITUCIONAL V3")
    print("=" * 72)
    print(f"Entrada : {input_path}")
    print(f"Schema  : {schema_path}")
    print(f"Saida   : {output_path}")

    if not input_path.exists():
        print(f"\nERRO: arquivo de entrada nao encontrado: {input_path}")
        return 2

    if not schema_path.exists():
        print(f"\nERRO: schema nao encontrado: {schema_path}")
        return 2

    try:
        data = load_input(input_path)
    except (OSError, ValueError) as exc:
        print(f"\nERRO DE ENTRADA: {exc}")
        return 2

    if not isinstance(data, dict):
        print("\nERRO: a raiz do JSON V3 deve ser um objeto.")
        return 2

    normalized = normalize(data)

    try:
        schema = load_json(schema_path)
    except Exception as exc:
        print(f"\nERRO AO CARREGAR SCHEMA: {exc}")
        return 2

    schema_errors = validate_schema(normalized, schema)
    business_errors, warnings = validate_business_rules(normalized)

    if schema_errors:
        print("\n[ERROS DE SCHEMA]")
        for err in schema_errors:
            print(f"  X {err}")

    if business_errors:
        print("\n[ERROS DE NEGOCIO]")
        for err in business_errors:
            print(f"  X {err}")

    if warnings:
        print("\n[AVISOS]")
        for warning in warnings:
            print(f"  ! {warning}")

    if schema_errors or business_errors:
        print("\nRESULTADO: REPROVADO — radar_v3.json NAO foi alterado.")
        return 1

    if warnings and not args.allow_warnings:
        print(
            "\nRESULTADO: VALIDACAO SEM ERROS, MAS EXISTEM AVISOS. "
            "radar_v3.json NAO foi alterado."
        )
        print("Use --allow-warnings para gerar um DRAFT com avisos.")
        return 3

    backup_path = backup_existing(output_path, backup_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(output_path)

    print("\n[VALIDACAO]")
    print("  OK Schema V3 aprovado")
    print("  OK Regras de negocio aprovadas")
    if warnings:
        print(f"  OK Gerado com {len(warnings)} aviso(s) autorizado(s)")

    if backup_path:
        print(f"  OK Backup anterior: {backup_path}")

    print(f"\nRESULTADO: APROVADO — gerado: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
