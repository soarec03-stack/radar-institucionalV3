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

DEFAULT_SIGNAL_POLICY = Path(DEFAULT_POLICY).parent / "signal_policy_v3.json"
DEFAULT_SCORE_POLICY = Path(DEFAULT_POLICY).parent / "score_policy_v3.json"
DEFAULT_RISK_POLICY = Path(DEFAULT_POLICY).parent / "risk_policy_v3.json"
DEFAULT_PUBLICATION_POLICY = Path(DEFAULT_POLICY).parent / "publication_eligibility_policy_v3.json"

METRICS_LOADER_MODULE = Path(DEFAULT_POLICY).parent / "metrics_loader_v3.py"
SIGNAL_ENGINE_MODULE = Path(DEFAULT_POLICY).parent / "signal_engine_v3.py"
RISK_HISTORY_ADAPTER_MODULE = Path(DEFAULT_POLICY).parent / "risk_history_adapter_v3.py"
RISK_METRICS_CALCULATOR_MODULE = Path(DEFAULT_POLICY).parent / "risk_metrics_calculator_v3.py"
RISK_ENGINE_MODULE = Path(DEFAULT_POLICY).parent / "risk_engine_v3.py"
SCORE_ENGINE_MODULE = Path(DEFAULT_POLICY).parent / "score_engine_v3.py"
PUBLICATION_ELIGIBILITY_MODULE = Path(DEFAULT_POLICY).parent / "publication_eligibility_v3.py"
SCORE_PLACEHOLDER_MODULE = Path(DEFAULT_POLICY).parent / "score_placeholder_v3.py"
DEFAULT_REGISTRY = BASE_DIR / "automation" / "source_registry_v3.json"
DEFAULT_HISTORY_DIR = BASE_DIR / "data" / "history" / "raw-json"

VALIDATOR_PATH = BASE_DIR / "automation" / "validate_radar_v3.py"
DATA_QUALITY_PATH = BASE_DIR / "automation" / "data_quality_v3.py"
CONFIDENCE_ENGINE_PATH = BASE_DIR / "automation" / "confidence_engine_v3.py"
DATAPOINT_ENGINE_PATH = BASE_DIR / "automation" / "datapoint_provenance_v3.py"


def load_module(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar modulo: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module("validate_radar_v3", VALIDATOR_PATH)
data_quality = load_module("data_quality_v3", DATA_QUALITY_PATH)
confidence_engine = load_module("confidence_engine_v3", CONFIDENCE_ENGINE_PATH)
datapoint_engine = load_module("datapoint_provenance_v3", DATAPOINT_ENGINE_PATH)


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_json_from_text(text):
    """
    Extrai um objeto JSON de forma tolerante a:
    - UTF-8 BOM;
    - JSON puro;
    - bloco Markdown ```json ... ```;
    - bloco Markdown ``` ... ```;
    - texto antes/depois do objeto JSON.
    """
    text = text.lstrip("\ufeff").strip()

    if not text:
        raise ValueError("O arquivo de entrada esta vazio.")

    errors = []

    # 1. JSON puro
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        errors.append("JSON puro encontrado, mas a raiz nao e um objeto.")
    except json.JSONDecodeError as exc:
        errors.append(f"JSON puro: {exc}")

    # 2. Todos os blocos Markdown fenced
    import re

    fenced_blocks = re.findall(
        r"```(?:json)?\s*(.*?)```",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    for index, candidate in enumerate(fenced_blocks, start=1):
        candidate = candidate.lstrip("\ufeff").strip()
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
            errors.append(
                f"Bloco Markdown {index}: JSON valido, mas raiz nao e objeto."
            )
        except json.JSONDecodeError as exc:
            errors.append(f"Bloco Markdown {index}: {exc}")

    # 3. Procura um objeto JSON dentro de texto livre
    decoder = json.JSONDecoder()
    positions = [i for i, char in enumerate(text) if char == "{"]

    for pos in positions:
        candidate = text[pos:].lstrip()
        try:
            data, _ = decoder.raw_decode(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    detail = " | ".join(errors[:5])
    raise ValueError(
        "Nao foi possivel localizar um objeto JSON V3 valido no arquivo de entrada."
        + (f" Detalhes: {detail}" if detail else "")
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
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Registro oficial de fontes do Radar V3"
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

    parser.add_argument(
        "--metrics-input",
        default=None,
        help=(
            "Arquivo opcional de metricas para enriquecimento. "
            "Sem este argumento, o Metrics Loader nao e executado."
        ),
    )
    parser.add_argument(
        "--risk-history",
        default=None,
        help=(
            "Arquivo opcional de historico para Asset Risk. "
            "Sem este argumento, Risk enrichment nao e executado."
        ),
    )
    parser.add_argument(
        "--signal-policy",
        default=str(DEFAULT_SIGNAL_POLICY),
        help="Signal Policy V3",
    )
    parser.add_argument(
        "--score-policy",
        default=str(DEFAULT_SCORE_POLICY),
        help="Radar Score Policy V3",
    )
    parser.add_argument(
        "--risk-policy",
        default=str(DEFAULT_RISK_POLICY),
        help="Asset Risk Policy V3",
    )
    parser.add_argument(
        "--publication-policy",
        default=str(DEFAULT_PUBLICATION_POLICY),
        help="Publication Eligibility Policy V3",
    )

    args = parser.parse_args()

    score_placeholder_module = load_module(
        "score_placeholder_v3",
        SCORE_PLACEHOLDER_MODULE,
    )
    prepare_score_placeholders = (
        score_placeholder_module.prepare_score_placeholders
    )

    metrics_loader_module = load_module(
        "metrics_loader_v3",
        METRICS_LOADER_MODULE,
    )
    merge_metrics = metrics_loader_module.merge_metrics

    risk_history_adapter_module = load_module(
        "risk_history_adapter_v3",
        RISK_HISTORY_ADAPTER_MODULE,
    )
    prepare_risk_history = (
        risk_history_adapter_module.prepare_risk_history
    )

    risk_metrics_calculator_module = load_module(
        "risk_metrics_calculator_v3",
        RISK_METRICS_CALCULATOR_MODULE,
    )
    calculate_risk_metrics = (
        risk_metrics_calculator_module.calculate_risk_metrics
    )

    risk_engine_module = load_module(
        "risk_engine_v3",
        RISK_ENGINE_MODULE,
    )

    score_engine = load_module(
        "score_engine_v3",
        SCORE_ENGINE_MODULE,
    )

    publication_eligibility_module = load_module(
        "publication_eligibility_v3",
        PUBLICATION_ELIGIBILITY_MODULE,
    )
    calculate_asset_risk = (
        risk_engine_module.calculate_asset_risk
    )
    write_risk_to_asset = (
        risk_engine_module.write_risk_to_asset
    )

    signal_engine_module = load_module(
        "signal_engine_v3",
        SIGNAL_ENGINE_MODULE,
    )
    apply_signal_engine = (
        signal_engine_module.apply_signal_engine
    )


    input_path = Path(args.input)
    schema_path = Path(args.schema)
    output_path = Path(args.output)
    policy_path = Path(args.policy)
    registry_path = Path(args.registry)
    history_dir = Path(args.history_dir)

    print("=" * 72)
    print("GERADOR / NORMALIZADOR â€” RADAR INSTITUCIONAL V3")
    print("=" * 72)
    print(f"Entrada : {input_path}")
    print(f"Schema  : {schema_path}")
    print(f"Policy  : {policy_path}")
    print(f"Registry: {registry_path}")
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

    if not registry_path.exists():
        print(f"\nERRO: registro de fontes nao encontrado: {registry_path}")
        return 2

    if not DATAPOINT_ENGINE_PATH.exists():
        print(f"\nERRO: engine de data points nao encontrado: {DATAPOINT_ENGINE_PATH}")
        return 2

    try:
        raw_text = input_path.read_text(encoding="utf-8")
        data = extract_json_from_text(raw_text)
    except Exception as exc:
        print(f"\nERRO: falha ao extrair JSON da entrada: {exc}")
        return 2

    data = normalize_tickers(data)

    enrichment_requested = bool(
        args.metrics_input or args.risk_history
    )

    if enrichment_requested:
        data = prepare_score_placeholders(data)


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

    try:
        registry = load_json(registry_path)
    except json.JSONDecodeError as exc:
        print(f"\nERRO: registry JSON invalido: {exc}")
        return 2

    assets = data.get("assets")
    if not isinstance(assets, list) or len(assets) == 0:
        print("\n[PROTECAO DO PIPELINE]")
        print("  X EMPTY_ASSETS: assets[] nao pode estar vazio.")
        print("  X O radar_v3.json anterior sera preservado.")
        print("\nRESULTADO: REPROVADO â€” RADAR SEM ATIVOS")
        return 1

    schema_errors = validator.validate_schema(data, schema)
    business_errors, warnings = validator.validate_business_rules(data)

    print_validation_section(schema_errors, business_errors, warnings)

    if schema_errors or business_errors:
        print("\nRESULTADO: REPROVADO â€” radar_v3.json nao foi alterado.")
        return 1

    if warnings and not args.allow_warnings:
        print(
            "  ! Avisos de validacao nao bloqueiam o enriquecimento; "
            "serao considerados novamente no resultado final."
        )

    print("\n[DATA-POINT PROVENANCE]")
    data, datapoint_changes = datapoint_engine.apply(data)

    if not datapoint_changes:
        print("  X Nenhum ativo encontrado para criar data points.")
        print("\nRESULTADO: REPROVADO â€” DATA-POINT ENGINE SEM ATIVOS")
        return 1

    for ticker, points in datapoint_changes:
        points_text = ", ".join(points) if points else "nenhum"
        print(f"  OK {ticker}: {points_text}")

    datapoint_schema_errors = validator.validate_schema(data, schema)
    if datapoint_schema_errors:
        print("\n[ERROS APOS DATA-POINT PROVENANCE]")
        for err in datapoint_schema_errors:
            print(f"  X {err}")
        print("\nRESULTADO: REPROVADO APOS DATA-POINT PROVENANCE")
        return 1

    if args.metrics_input:
        print("\n[METRICS LOADER]")

        metrics_path = Path(args.metrics_input)

        if not metrics_path.exists():
            print(
                "  X Metrics input inexistente: "
                f"{metrics_path}"
            )
            print(
                "\nRESULTADO: REPROVADO ? "
                "metrics-input inexistente."
            )
            return 1

        try:
            metrics_input = load_json(metrics_path)
        except json.JSONDecodeError as exc:
            print(
                "  X Metrics input JSON invalido: "
                f"{exc}"
            )
            print(
                "\nRESULTADO: REPROVADO ? "
                "metrics-input JSON invalido."
            )
            return 1
        except OSError as exc:
            print(
                "  X Falha ao ler metrics-input: "
                f"{exc}"
            )
            print(
                "\nRESULTADO: REPROVADO ? "
                "falha de leitura do metrics-input."
            )
            return 1

        if not isinstance(metrics_input, dict):
            print(
                "  X Metrics input deve possuir "
                "objeto JSON na raiz."
            )
            print(
                "\nRESULTADO: REPROVADO ? "
                "metrics-input estruturalmente invalido."
            )
            return 1

        data, metrics_changes, metrics_warnings = (
            merge_metrics(
                data,
                metrics_input,
            )
        )

        print(
            f"  Alteracoes aplicadas : "
            f"{len(metrics_changes)}"
        )

        print(
            f"  Avisos do loader     : "
            f"{len(metrics_warnings)}"
        )

        for metrics_warning in metrics_warnings:
            print(
                f"  ! {metrics_warning}"
            )

    print("\n[CONFIDENCE ENGINE]")
    data, confidence_changes = confidence_engine.apply_confidence_engine(
        data,
        registry,
        policy.get("freshness_hours", {})
    )
    for item in confidence_changes:
        current = item["current"]
        comps = item["components"]
        print(
            f"  {item['ticker']}: ASSET {current['score']:.4f} / {current['status']} "
            f"(SQ={comps['source_quality']:.2f}, "
            f"SA={comps['source_agreement']:.2f}, "
            f"FR={comps['freshness']:.2f}, "
            f"CO={comps['completeness']:.2f}, "
            f"VE={comps['verification']:.2f})"
        )
        for point_name, point_result in sorted(item.get("data_points", {}).items()):
            point_conf = point_result["current"]
            point_comps = point_result["components"]
            print(
                f"    - {point_name}: {point_conf['score']:.4f} / "
                f"{point_conf['status']} "
                f"(SQ={point_comps['source_quality']:.2f}, "
                f"SA={point_comps['source_agreement']:.2f}, "
                f"FR={point_comps['freshness']:.2f}, "
                f"CO={point_comps['completeness']:.2f}, "
                f"VE={point_comps['verification']:.2f})"
            )

    # Revalida regras de negocio apÃ³s o cÃ¡lculo automÃ¡tico de confidence.
    print("\n[SIGNAL ENGINE]")

    signal_policy_path = Path(
        args.signal_policy
    )

    if not signal_policy_path.exists():
        print(
            "  X Signal Policy inexistente: "
            f"{signal_policy_path}"
        )
        print(
            "\nRESULTADO: REPROVADO - "
            "signal-policy inexistente."
        )
        return 1

    try:
        signal_policy = load_json(
            signal_policy_path
        )
    except json.JSONDecodeError as exc:
        print(
            "  X Signal Policy JSON invalido: "
            f"{exc}"
        )
        print(
            "\nRESULTADO: REPROVADO - "
            "signal-policy JSON invalido."
        )
        return 1
    except OSError as exc:
        print(
            "  X Falha ao ler Signal Policy: "
            f"{exc}"
        )
        print(
            "\nRESULTADO: REPROVADO - "
            "falha de leitura da signal-policy."
        )
        return 1

    if not isinstance(signal_policy, dict):
        print(
            "  X Signal Policy deve possuir "
            "objeto JSON na raiz."
        )
        print(
            "\nRESULTADO: REPROVADO - "
            "signal-policy estruturalmente invalida."
        )
        return 1

    if not isinstance(
        signal_policy.get("principles"),
        dict,
    ):
        print(
            "  X Signal Policy sem principles "
            "validos."
        )
        print(
            "\nRESULTADO: REPROVADO - "
            "signal-policy sem principles validos."
        )
        return 1

    if not isinstance(
        signal_policy.get("domains"),
        dict,
    ):
        print(
            "  X Signal Policy sem domains "
            "validos."
        )
        print(
            "\nRESULTADO: REPROVADO - "
            "signal-policy sem domains validos."
        )
        return 1

    data, signal_changes = apply_signal_engine(
        data,
        signal_policy,
    )

    print(
        f"  Alteracoes de sinal : "
        f"{len(signal_changes)}"
    )

    risk_source_context_by_ticker = {}

    if args.risk_history:
        print("\n[RISK PIPELINE]")

        risk_history_path = Path(
            args.risk_history
        )

        if not risk_history_path.exists():
            print(
                "RESULTADO: REPROVADO - "
                "risk-history inexistente."
            )
            return 1

        try:
            risk_history = load_json(
                risk_history_path
            )
        except json.JSONDecodeError as exc:
            print(
                "RESULTADO: REPROVADO - "
                "risk-history JSON invalido."
            )
            print(f"Detalhe: {exc}")
            return 1
        except OSError as exc:
            print(
                "RESULTADO: REPROVADO - "
                "falha ao ler risk-history."
            )
            print(f"Detalhe: {exc}")
            return 1

        if not isinstance(
            risk_history,
            dict,
        ):
            print(
                "RESULTADO: REPROVADO - "
                "risk-history estruturalmente invalido."
            )
            return 1

        history_assets = risk_history.get(
            "assets"
        )

        if not isinstance(
            history_assets,
            list,
        ):
            print(
                "RESULTADO: REPROVADO - "
                "risk-history sem assets validos."
            )
            return 1

        risk_policy_path = Path(
            args.risk_policy
        )

        if not risk_policy_path.exists():
            print(
                "RESULTADO: REPROVADO - "
                "risk-policy inexistente."
            )
            return 1

        try:
            risk_policy = load_json(
                risk_policy_path
            )
        except json.JSONDecodeError as exc:
            print(
                "RESULTADO: REPROVADO - "
                "risk-policy JSON invalido."
            )
            print(f"Detalhe: {exc}")
            return 1
        except OSError as exc:
            print(
                "RESULTADO: REPROVADO - "
                "falha ao ler risk-policy."
            )
            print(f"Detalhe: {exc}")
            return 1

        if not isinstance(
            risk_policy,
            dict,
        ):
            print(
                "RESULTADO: REPROVADO - "
                "risk-policy estruturalmente invalida."
            )
            return 1

        if not isinstance(
            risk_policy.get("components"),
            dict,
        ):
            print(
                "RESULTADO: REPROVADO - "
                "risk-policy sem components validos."
            )
            return 1

        if not isinstance(
            risk_policy.get("aggregation"),
            dict,
        ):
            print(
                "RESULTADO: REPROVADO - "
                "risk-policy sem aggregation valida."
            )
            return 1

        history_by_ticker = {
            item.get("ticker"): item
            for item in history_assets
            if (
                isinstance(item, dict)
                and isinstance(
                    item.get("ticker"),
                    str,
                )
            )
        }

        primary_source = risk_history.get(
            "source"
        )
        retrieved_at = risk_history.get(
            "generated_at"
        )
        publication_use = risk_history.get(
            "publication_use"
        )

        risk_changes = 0
        risk_warnings = []

        for asset in data.get(
            "assets",
            [],
        ):
            if not isinstance(
                asset,
                dict,
            ):
                continue

            ticker = asset.get(
                "ticker"
            )

            history_item = (
                history_by_ticker.get(
                    ticker
                )
            )

            if not isinstance(
                history_item,
                dict,
            ):
                risk_warnings.append(
                    f"{ticker}: "
                    "historico de risco ausente."
                )
                continue

            records = history_item.get(
                "records"
            )

            if not isinstance(
                records,
                list,
            ):
                risk_warnings.append(
                    f"{ticker}: "
                    "records de risco invalidos."
                )
                continue

            try:
                prepared = (
                    prepare_risk_history(
                        records
                    )
                )

                metrics = (
                    calculate_risk_metrics(
                        prepared["closes"]
                    )
                )

                analytical = (
                    calculate_asset_risk(
                        metrics,
                        risk_policy,
                    )
                )

                before_risk = asset.get(
                    "risk"
                )

                write_risk_to_asset(
                    asset,
                    analytical,
                )

                if asset.get(
                    "risk"
                ) != before_risk:
                    risk_changes += 1

            except (
                TypeError,
                ValueError,
                KeyError,
            ) as exc:
                risk_warnings.append(
                    f"{ticker}: "
                    f"Risk indisponivel: {exc}"
                )
                continue

            normalized_records = (
                prepared.get(
                    "records",
                    []
                )
            )

            market_dates = [
                record.get(
                    "market_date"
                )
                for record in normalized_records
                if (
                    isinstance(
                        record,
                        dict,
                    )
                    and record.get(
                        "market_date"
                    )
                )
            ]

            market_date = (
                market_dates[-1]
                if market_dates
                else None
            )

            if (
                ticker
                and market_date
                and primary_source
                and retrieved_at
            ):
                source_context = {
                    "primary_source":
                        primary_source,
                    "retrieved_at":
                        retrieved_at,
                }

                if publication_use is not None:
                    source_context[
                        "publication_use"
                    ] = publication_use

                risk_source_context_by_ticker[
                    ticker
                ] = {
                    "ticker": ticker,
                    "market_date":
                        market_date,
                    "source":
                        source_context,
                }

        print(
            "Alteracoes de risco : "
            f"{risk_changes}"
        )
        print(
            "Avisos de risco     : "
            f"{len(risk_warnings)}"
        )

        for warning in risk_warnings:
            print(f"  - {warning}")


    # --------------------------------------------------------
    # Radar Score Engine
    # --------------------------------------------------------
    if enrichment_requested:
        score_policy_path = Path(args.score_policy)

        if not score_policy_path.exists():
            print(
                f"[ERRO] Score Policy nao encontrada: "
                f"{score_policy_path}"
            )
            return 1

        try:
            score_policy = load_json(
                score_policy_path
            )
        except (
            json.JSONDecodeError,
            OSError,
            ValueError,
        ) as exc:
            print(
                f"[ERRO] Falha ao carregar "
                f"Score Policy: {exc}"
            )
            return 1

        if not isinstance(score_policy, dict):
            print(
                "[ERRO] Score Policy deve possuir "
                "objeto JSON na raiz."
            )
            return 1

        score_components = score_policy.get(
            "components"
        )

        score_coverage = score_policy.get(
            "coverage"
        )

        if not isinstance(
            score_components,
            dict,
        ):
            print(
                "[ERRO] Score Policy invalida: "
                "components deve ser objeto."
            )
            return 1

        if not isinstance(
            score_coverage,
            dict,
        ):
            print(
                "[ERRO] Score Policy invalida: "
                "coverage deve ser objeto."
            )
            return 1

        calculate_asset_score = getattr(
            score_engine,
            "calculate_asset_score",
        )

        write_score_to_asset = getattr(
            score_engine,
            "write_score_to_asset",
        )

        print(
            "[SCORE ENGINE] Calculando "
            "Radar Score..."
        )

        for asset in data.get("assets", []):
            if not isinstance(asset, dict):
                continue

            score_result = (
                calculate_asset_score(
                    asset,
                    score_policy,
                )
            )

            write_score_to_asset(
                asset,
                score_result,
            )

    # --------------------------------------------------------
    # Publication Eligibility
    # --------------------------------------------------------
    if enrichment_requested:
        publication_policy_path = Path(
            args.publication_policy
        )

        if not publication_policy_path.exists():
            print(
                "[ERRO] Publication Eligibility Policy "
                "nao encontrada: "
                f"{publication_policy_path}"
            )
            return 1

        try:
            publication_policy = load_json(
                publication_policy_path
            )
        except (
            json.JSONDecodeError,
            OSError,
            ValueError,
        ) as exc:
            print(
                "[ERRO] Falha ao carregar Publication "
                f"Eligibility Policy: {exc}"
            )
            return 1

        if not isinstance(publication_policy, dict):
            print(
                "[ERRO] Publication Eligibility Policy "
                "deve possuir objeto JSON na raiz."
            )
            return 1

        publication_principles = (
            publication_policy.get("principles")
        )
        publication_tier_policy = (
            publication_policy.get("tier_policy")
        )
        publication_use_policy = (
            publication_policy.get(
                "publication_use_policy"
            )
        )
        publication_components = (
            publication_policy.get("components")
        )

        required_publication_sections = (
            (
                "principles",
                publication_principles,
            ),
            (
                "tier_policy",
                publication_tier_policy,
            ),
            (
                "publication_use_policy",
                publication_use_policy,
            ),
            (
                "components",
                publication_components,
            ),
        )

        for (
            section_name,
            section_value,
        ) in required_publication_sections:
            if not isinstance(section_value, dict):
                print(
                    "[ERRO] Publication Eligibility "
                    "Policy invalida: "
                    f"{section_name} deve ser objeto."
                )
                return 1

        apply_publication_eligibility = getattr(
            publication_eligibility_module,
            "apply_publication_eligibility",
        )

        print(
            "[PUBLICATION ELIGIBILITY] "
            "Aplicando gate de publicacao..."
        )

        (
            data,
            publication_changes,
        ) = apply_publication_eligibility(
            data,
            registry,
            publication_policy,
            risk_source_context_by_ticker,
        )

        if publication_changes:
            print(
                "[PUBLICATION ELIGIBILITY] "
                f"{len(publication_changes)} "
                "asset(s) tiveram publishable "
                "restringido."
            )

    post_schema_errors = validator.validate_schema(data, schema)
    post_business_errors, post_warnings = validator.validate_business_rules(data)

    if post_schema_errors or post_business_errors:
        print("\nRESULTADO: REPROVADO APOS CONFIDENCE ENGINE.")
        for err in post_schema_errors:
            print(f"  X Schema: {err}")
        for err in post_business_errors:
            print(f"  X Regra de negocio: {err}")
        return 1

    issues, metrics, publish_allowed, blockers = data_quality.evaluate(data, policy)
    print_quality_section(data, issues, metrics, publish_allowed, blockers)

    status = (data.get("radar_run") or {}).get("status")
    quality_critical = metrics["critical_issues"] > 0

    # PUBLISHED: gate sempre rigido
    if status == "PUBLISHED" and not publish_allowed:
        print(
            "\nRESULTADO: BLOQUEADO PELO PUBLICATION GATE â€” "
            "radar_v3.json nao foi alterado."
        )
        return 1

    # DRAFT/VALIDATED: por padrao tambem bloqueia criticos.
    if quality_critical and not args.allow_quality_critical_in_draft:
        print(
            "\nRESULTADO: BLOQUEADO POR DATA QUALITY CRITICA â€” "
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
            f"â€” arquivo: {output_path}"
        )
    elif metrics["warnings"] > 0 or warnings:
        print(
            f"\nRESULTADO: APROVADO COM AVISOS â€” gerado: {output_path}"
        )
    else:
        print(f"\nRESULTADO: APROVADO â€” gerado: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
