import argparse
import importlib.util
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = BASE_DIR / "input" / "radar_input_v3.txt"
DEFAULT_SCHEMA = BASE_DIR / "automation" / "schema_v3.json"
DEFAULT_OUTPUT = BASE_DIR / "radar_v3.json"
DEFAULT_POLICY = BASE_DIR / "automation" / "data_quality_policy_v3.json"
DEFAULT_HISTORY_DIR = BASE_DIR / "data" / "history" / "raw-json"

VALIDATOR_PATH = BASE_DIR / "automation" / "validate_radar_v3.py"
DATA_QUALITY_PATH = BASE_DIR / "automation" / "data_quality_v3.py"


def load_module(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar modulo: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module("validate_radar_v3", VALIDATOR_PATH)
data_quality = load_module("data_quality_v3", DATA_QUALITY_PATH)


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_json_from_text(text):
    text = text.strip()

    # JSON puro
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # bloco ```json ... ```
    lower = text.lower()
    start = lower.find("```json")
    if start != -1:
        start += len("```json")
        end = text.find("```", start)
        if end != -1:
            candidate = text[start:end].strip()
            return json.loads(candidate)

    # bloco ``` ... ```
    start = text.find("```")
    if start != -1:
        start += 3
        end = text.find("```", start)
        if end != -1:
            candidate = text[start:end].strip()
            return json.loads(candidate)

    raise ValueError(
        "Nao foi encontrado JSON puro nem bloco ```json``` valido no arquivo de entrada."
    )


def normalize_tickers(data):
    assets = data.get("assets", [])
    for asset in assets:
        ticker = asset.get("ticker")
        if isinstance(ticker, str):
            asset["ticker"] = ticker.strip().upper()

    portfolio = data.get("portfolio", {})
    for position in portfolio.get("positions", []):
        ticker = position.get("ticker")
        if isinstance(ticker, str):
            position["ticker"] = ticker.strip().upper()

    scenarios = data.get("scenarios", {})
    for key in ("bull", "base", "bear"):
        for impact in scenarios.get(key, {}).get("asset_impacts", []):
            ticker = impact.get("ticker")
            if isinstance(ticker, str):
                impact["ticker"] = ticker.strip().upper()

    alerts = data.get("alerts", [])
    for alert in alerts:
        ticker = alert.get("ticker")
        if isinstance(ticker, str):
            alert["ticker"] = ticker.strip().upper()

    return data


def backup_existing(output_path, history_dir):
    output_path = Path(output_path)
    if not output_path.exists():
        return None

    history_dir = Path(history_dir)
    history_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = history_dir / f"radar_v3_{stamp}.json"
    shutil.copy2(output_path, backup)
    return backup


def print_validation_section(schema_errors, business_errors, warnings):
    print("\n[VALIDACAO]")

    if schema_errors:
        for err in schema_errors:
            print(f"  X Schema: {err}")
    else:
        print("  OK Schema V3 aprovado")

    if business_errors:
        for err in business_errors:
            print(f"  X Regra de negocio: {err}")
    else:
        print("  OK Regras de negocio aprovadas")

    if warnings:
        for warning in warnings:
            print(f"  ! Aviso: {warning}")


def print_quality_section(data, issues, metrics, publish_allowed, blockers):
    print("\n[DATA QUALITY]")

    print(f"  Ativos totais       : {metrics['assets_total']}")
    print(f"  Ativos com preco    : {metrics['assets_with_price']}")
    print(f"  Provenance VERIFIED : {metrics['assets_verified']}")
    print(f"  Dados stale         : {metrics['assets_stale']}")
    print(f"  Criticos            : {metrics['critical_issues']}")
    print(f"  Avisos              : {metrics['warnings']}")

    for issue in issues:
        mark = "X" if issue["severity"] == "CRITICAL" else "!"
        print(
            f"  {mark} [{issue['severity']}] "
            f"{issue['entity']} / {issue['code']}: {issue['message']}"
        )

    status = (data.get("radar_run") or {}).get("status")
    if status == "PUBLISHED":
        print(f"  Publication Gate    : {'APROVADO' if publish_allowed else 'BLOQUEADO'}")
        for blocker in blockers:
            print(f"  X {blocker}")
    else:
        print("  Publication Gate    : informativo em DRAFT/VALIDATED")


def write_output(data, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Gera, normaliza, valida e aplica Data Quality ao Radar Institucional V3."
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Arquivo de entrada Raw Analysis"
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA),
        help="Schema V3"
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Arquivo radar_v3.json"
    )
    parser.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY),
        help="Politica Data Quality V3"
    )
    parser.add_argument(
        "--history-dir",
        default=str(DEFAULT_HISTORY_DIR),
        help="Diretorio de backup historico"
    )
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Permite gerar arquivo com avisos de validacao/regra de negocio."
    )
    parser.add_argument(
        "--allow-quality-critical-in-draft",
        action="store_true",
        help=(
            "Permite gerar DRAFT/VALIDATED mesmo com issues CRITICAL de Data Quality. "
            "Nunca ignora bloqueio de PUBLISHED."
        )
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    schema_path = Path(args.schema)
    output_path = Path(args.output)
    policy_path = Path(args.policy)
    history_dir = Path(args.history_dir)

    print("=" * 72)
    print("GERADOR / NORMALIZADOR — RADAR INSTITUCIONAL V3")
    print("=" * 72)
    print(f"Entrada : {input_path}")
    print(f"Schema  : {schema_path}")
    print(f"Policy  : {policy_path}")
    print(f"Saida   : {output_path}")

    if not input_path.exists():
        print(f"\nERRO: arquivo de entrada nao encontrado: {input_path}")
        return 2

    if not schema_path.exists():
        print(f"\nERRO: schema nao encontrado: {schema_path}")
        return 2

    if not policy_path.exists():
        print(f"\nERRO: politica de qualidade nao encontrada: {policy_path}")
        return 2

    try:
        raw_text = input_path.read_text(encoding="utf-8")
        data = extract_json_from_text(raw_text)
    except Exception as exc:
        print(f"\nERRO: falha ao extrair JSON da entrada: {exc}")
        return 2

    data = normalize_tickers(data)

    try:
        schema = load_json(schema_path)
    except json.JSONDecodeError as exc:
        print(f"\nERRO: schema JSON invalido: {exc}")
        return 2

    try:
        policy = load_json(policy_path)
    except json.JSONDecodeError as exc:
        print(f"\nERRO: policy JSON invalida: {exc}")
        return 2

    schema_errors = validator.validate_schema(data, schema)
    business_errors, warnings = validator.validate_business_rules(data)

    print_validation_section(schema_errors, business_errors, warnings)

    if schema_errors or business_errors:
        print("\nRESULTADO: REPROVADO — radar_v3.json nao foi alterado.")
        return 1

    if warnings and not args.allow_warnings:
        print(
            "\nRESULTADO: BLOQUEADO POR AVISOS — "
            "use --allow-warnings se quiser gerar conscientemente."
        )
        return 1

    issues, metrics, publish_allowed, blockers = data_quality.evaluate(data, policy)
    print_quality_section(data, issues, metrics, publish_allowed, blockers)

    status = (data.get("radar_run") or {}).get("status")
    quality_critical = metrics["critical_issues"] > 0

    # PUBLISHED: gate sempre rigido
    if status == "PUBLISHED" and not publish_allowed:
        print(
            "\nRESULTADO: BLOQUEADO PELO PUBLICATION GATE — "
            "radar_v3.json nao foi alterado."
        )
        return 1

    # DRAFT/VALIDATED: por padrao tambem bloqueia criticos.
    if quality_critical and not args.allow_quality_critical_in_draft:
        print(
            "\nRESULTADO: BLOQUEADO POR DATA QUALITY CRITICA — "
            "radar_v3.json nao foi alterado."
        )
        print(
            "Para um DRAFT/VALIDATED conscientemente incompleto, use "
            "--allow-quality-critical-in-draft."
        )
        return 1

    backup = backup_existing(output_path, history_dir)
    if backup:
        print(f"\n  OK Backup anterior: {backup}")

    write_output(data, output_path)

    if quality_critical:
        print(
            f"\nRESULTADO: GERADO COMO {status} COM DATA QUALITY CRITICA AUTORIZADA "
            f"— arquivo: {output_path}"
        )
    elif metrics["warnings"] > 0 or warnings:
        print(
            f"\nRESULTADO: APROVADO COM AVISOS — gerado: {output_path}"
        )
    else:
        print(f"\nRESULTADO: APROVADO — gerado: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
