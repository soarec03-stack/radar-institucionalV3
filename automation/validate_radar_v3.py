import argparse
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    print("ERRO: dependencia 'jsonschema' nao instalada.")
    print("Instale com: python -m pip install jsonschema")
    sys.exit(2)


SCORE_LABEL_RULES = [
    (85, 100, "STRONG_BUY"),
    (75, 84.999999, "BUY"),
    (65, 74.999999, "WATCH_ACCUMULATE"),
    (50, 64.999999, "HOLD"),
    (35, 49.999999, "CAUTION"),
    (0, 34.999999, "AVOID"),
]

DECISION_ACTIONS_BY_SCORE_LABEL = {
    "STRONG_BUY": {"STRONG_BUY", "BUY", "ACCUMULATE"},
    "BUY": {"BUY", "ACCUMULATE", "HOLD"},
    "WATCH_ACCUMULATE": {"ACCUMULATE", "WATCH", "HOLD"},
    "HOLD": {"WATCH", "HOLD", "REDUCE"},
    "CAUTION": {"HOLD", "REDUCE", "SELL", "AVOID"},
    "AVOID": {"REDUCE", "SELL", "AVOID"},
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def format_jsonschema_error(error):
    path = ".".join(str(p) for p in error.absolute_path)
    if path:
        return f"{path}: {error.message}"
    return error.message


def expected_score_label(total):
    for low, high, label in SCORE_LABEL_RULES:
        if low <= total <= high:
            return label
    return None


def validate_schema(data, schema):
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(data),
        key=lambda e: list(e.absolute_path)
    )
    return [format_jsonschema_error(e) for e in errors]


def validate_business_rules(data):
    errors = []
    warnings = []

    # 1. schema_version
    if data.get("schema_version") != "3.0":
        errors.append(
            f"schema_version deve ser '3.0', recebido: {data.get('schema_version')!r}"
        )

    assets = data.get("assets", [])
    portfolio = data.get("portfolio", {})
    positions = portfolio.get("positions", [])

    # 2. Tickers duplicados em assets
    asset_tickers = []
    seen = set()
    duplicates = set()

    for asset in assets:
        ticker = asset.get("ticker")
        if ticker:
            asset_tickers.append(ticker)
            if ticker in seen:
                duplicates.add(ticker)
            seen.add(ticker)

    if duplicates:
        errors.append(
            "Tickers duplicados em assets: " + ", ".join(sorted(duplicates))
        )

    asset_ticker_set = set(asset_tickers)

    # 3. score.total = soma dos componentes
    score_components = [
        "fundamental",
        "technical",
        "momentum",
        "institutional_flow",
        "catalysts",
        "macro",
        "risk",
    ]

    for i, asset in enumerate(assets):
        ticker = asset.get("ticker", f"assets[{i}]")
        score = asset.get("score", {})

        missing = [name for name in score_components if name not in score]
        if missing:
            errors.append(
                f"{ticker}: componentes de score ausentes: {', '.join(missing)}"
            )
            continue

        calculated = sum(score[name] for name in score_components)
        declared = score.get("total")

        if declared is None:
            errors.append(f"{ticker}: score.total ausente.")
        elif abs(calculated - declared) > 1e-9:
            errors.append(
                f"{ticker}: score.total={declared} mas soma dos componentes={calculated}."
            )

        # 4. label deve bater com score total
        if declared is not None:
            expected = expected_score_label(declared)
            actual = score.get("label")
            if expected and actual != expected:
                errors.append(
                    f"{ticker}: score.label='{actual}' incoerente com total={declared}. "
                    f"Esperado: '{expected}'."
                )

            # 5. decision.action coerente com faixa de score
            decision = asset.get("decision", {})
            action = decision.get("action")
            if actual in DECISION_ACTIONS_BY_SCORE_LABEL and action:
                allowed = DECISION_ACTIONS_BY_SCORE_LABEL[actual]
                if action not in allowed:
                    warnings.append(
                        f"{ticker}: decision.action='{action}' e score.label='{actual}' "
                        f"formam uma combinacao atipica. Permitidos/recomendados: "
                        f"{', '.join(sorted(allowed))}."
                    )

    # 6. tickers da carteira devem existir em assets
    for i, position in enumerate(positions):
        ticker = position.get("ticker")
        if ticker and ticker not in asset_ticker_set:
            errors.append(
                f"portfolio.positions[{i}].ticker='{ticker}' nao existe em assets[]."
            )

    # 7. Probabilidades dos cenarios
    scenarios = data.get("scenarios", {})
    scenario_keys = ["bull", "base", "bear"]

    probabilities = []
    for key in scenario_keys:
        scenario = scenarios.get(key)
        if scenario is None:
            errors.append(f"scenarios.{key} ausente.")
            continue

        probability = scenario.get("probability")
        if probability is None:
            errors.append(f"scenarios.{key}.probability ausente.")
            continue

        if not 0 <= probability <= 100:
            errors.append(
                f"scenarios.{key}.probability deve estar entre 0 e 100."
            )

        probabilities.append(probability)

        expected_name = key.upper()
        actual_name = scenario.get("name")
        if actual_name != expected_name:
            errors.append(
                f"scenarios.{key}.name deve ser '{expected_name}', recebido '{actual_name}'."
            )

    if len(probabilities) == 3:
        total_probability = sum(probabilities)
        if abs(total_probability - 100) > 1e-9:
            errors.append(
                f"Bull + Base + Bear devem somar 100%. Soma atual: {total_probability}%."
            )

    # 8. Tickers citados em asset_impacts devem existir em assets
    for key in scenario_keys:
        scenario = scenarios.get(key, {})
        for j, impact in enumerate(scenario.get("asset_impacts", [])):
            ticker = impact.get("ticker")
            if ticker and ticker not in asset_ticker_set:
                errors.append(
                    f"scenarios.{key}.asset_impacts[{j}].ticker='{ticker}' "
                    f"nao existe em assets[]."
                )

    # 9. Portfolio risk coerente com positions
    portfolio_risk = portfolio.get("risk", {})
    if positions and not portfolio_risk:
        errors.append(
            "portfolio possui positions, mas portfolio.risk esta ausente."
        )

    # 10. DRAFT x dados indisponiveis
    run_status = data.get("radar_run", {}).get("status")
    unavailable_assets = [
        a.get("ticker")
        for a in assets
        if a.get("price") is None
        or a.get("confidence", {}).get("status") == "UNAVAILABLE"
    ]

    if unavailable_assets and run_status == "PUBLISHED":
        errors.append(
            "radar_run.status='PUBLISHED' com ativos sem preco ou indisponiveis: "
            + ", ".join(str(t) for t in unavailable_assets)
        )
    elif unavailable_assets:
        warnings.append(
            "Ativos ainda sem preco confirmado: "
            + ", ".join(str(t) for t in unavailable_assets)
        )

    # 11. Ranking opcional futuro
    ranking = data.get("ranking")
    if ranking is not None:
        if not isinstance(ranking, list):
            errors.append("ranking deve ser um array quando presente.")
        else:
            ranks = []
            tickers = []
            for i, item in enumerate(ranking):
                rank = item.get("rank")
                ticker = item.get("ticker")

                if rank is not None:
                    ranks.append(rank)
                if ticker:
                    tickers.append(ticker)

                if ticker and ticker not in asset_ticker_set:
                    errors.append(
                        f"ranking[{i}].ticker='{ticker}' nao existe em assets[]."
                    )

            if ranks:
                expected_ranks = list(range(1, len(ranks) + 1))
                if sorted(ranks) != expected_ranks:
                    errors.append(
                        f"ranking.rank deve ser sequencial de 1 a {len(ranks)}."
                    )

            if len(tickers) != len(set(tickers)):
                errors.append("ranking contem tickers duplicados.")

    return errors, warnings


def print_result(schema_errors, business_errors, warnings):
    print("=" * 68)
    print("VALIDACAO RADAR INSTITUCIONAL V3")
    print("=" * 68)

    if schema_errors:
        print("\n[ERROS DE SCHEMA]")
        for err in schema_errors:
            print(f"  X {err}")
    else:
        print("\n[SCHEMA]")
        print("  OK Estrutura compativel com schema_v3.json")

    if business_errors:
        print("\n[ERROS DE NEGOCIO]")
        for err in business_errors:
            print(f"  X {err}")
    else:
        print("\n[REGRAS DE NEGOCIO]")
        print("  OK Regras obrigatorias aprovadas")

    if warnings:
        print("\n[AVISOS]")
        for warning in warnings:
            print(f"  ! {warning}")

    print("\n" + "-" * 68)

    if schema_errors or business_errors:
        print("RESULTADO: REPROVADO")
        return 1

    if warnings:
        print("RESULTADO: APROVADO COM AVISOS")
    else:
        print("RESULTADO: APROVADO")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Valida o radar_v3.json contra schema_v3.json e regras de negocio."
    )
    parser.add_argument(
        "radar",
        nargs="?",
        default="radar_v3.json",
        help="Caminho para radar_v3.json"
    )
    parser.add_argument(
        "--schema",
        default="automation/schema_v3.json",
        help="Caminho para schema_v3.json"
    )

    args = parser.parse_args()

    radar_path = Path(args.radar)
    schema_path = Path(args.schema)

    if not radar_path.exists():
        print(f"ERRO: arquivo nao encontrado: {radar_path}")
        return 2

    if not schema_path.exists():
        print(f"ERRO: schema nao encontrado: {schema_path}")
        return 2

    try:
        data = load_json(radar_path)
    except json.JSONDecodeError as exc:
        print(f"ERRO: radar JSON invalido: {exc}")
        return 2

    try:
        schema = load_json(schema_path)
    except json.JSONDecodeError as exc:
        print(f"ERRO: schema JSON invalido: {exc}")
        return 2

    schema_errors = validate_schema(data, schema)
    business_errors, warnings = validate_business_rules(data)

    return print_result(schema_errors, business_errors, warnings)


if __name__ == "__main__":
    sys.exit(main())
