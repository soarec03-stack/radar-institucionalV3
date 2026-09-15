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

    # 3. Score V3 — semantica, cobertura e arredondamento
    score_components = [
        "fundamental",
        "technical",
        "momentum",
        "institutional_flow",
        "catalysts",
        "macro",
        "risk",
    ]

    SCORE_ROUNDING_TOLERANCE = 0.02
    SCORE_VALUE_TOLERANCE = 0.011
    COVERAGE_TOLERANCE = 0.0001
    MINIMUM_ANALYTIC_COVERAGE = 0.70
    MINIMUM_PUBLICATION_COVERAGE = 0.85

    for i, asset in enumerate(assets):
        ticker = asset.get("ticker", f"assets[{i}]")
        score = asset.get("score", {})

        missing = [name for name in score_components if name not in score]
        if missing:
            errors.append(
                f"{ticker}: componentes de score ausentes: {', '.join(missing)}"
            )
            continue

        calculated_components = sum(score[name] for name in score_components)
        declared_total = score.get("total")
        raw_score = score.get("raw_score")
        available_score = score.get("available_score")
        normalized_score = score.get("normalized_score")
        coverage = score.get("coverage")
        status = score.get("status")
        analytically_usable = score.get("analytically_usable")
        publishable = score.get("publishable")
        label = score.get("label")

        # 3.1 total representa a contribuicao bruta e deve acompanhar os
        # componentes. Aceita pequena diferenca causada pelo arredondamento
        # individual dos sete componentes para duas casas decimais.
        if declared_total is None:
            errors.append(f"{ticker}: score.total ausente.")
        elif abs(calculated_components - declared_total) > SCORE_ROUNDING_TOLERANCE:
            errors.append(
                f"{ticker}: score.total={declared_total} mas soma dos "
                f"componentes={calculated_components:.2f}; tolerancia="
                f"{SCORE_ROUNDING_TOLERANCE:.2f}."
            )

        # 3.2 raw_score e total sao semanticamente equivalentes.
        if declared_total is not None and raw_score is not None:
            if abs(float(raw_score) - float(declared_total)) > SCORE_VALUE_TOLERANCE:
                errors.append(
                    f"{ticker}: score.raw_score={raw_score} deve ser igual "
                    f"a score.total={declared_total}."
                )

        # 3.3 coverage deriva do available_score sobre o modelo total de 100 pontos.
        if available_score is not None and coverage is not None:
            expected_coverage = float(available_score) / 100.0
            if abs(float(coverage) - expected_coverage) > COVERAGE_TOLERANCE:
                errors.append(
                    f"{ticker}: score.coverage={coverage} incoerente com "
                    f"available_score={available_score}; esperado "
                    f"{expected_coverage:.4f}."
                )

        # 3.4 Estado semantico do score.
        if coverage is not None:
            coverage_value = float(coverage)

            if coverage_value < MINIMUM_ANALYTIC_COVERAGE:
                expected_status = "INSUFFICIENT_DATA"
                expected_usable = False
                expected_publishable = False
            elif coverage_value < MINIMUM_PUBLICATION_COVERAGE:
                expected_status = "PARTIAL"
                expected_usable = True
                expected_publishable = False
            else:
                expected_status = "CALCULATED"
                expected_usable = True
                expected_publishable = True

            if status != expected_status:
                errors.append(
                    f"{ticker}: score.status='{status}' incoerente com "
                    f"coverage={coverage_value:.0%}. Esperado: "
                    f"'{expected_status}'."
                )

            if analytically_usable is not expected_usable:
                errors.append(
                    f"{ticker}: score.analytically_usable="
                    f"{analytically_usable!r}; esperado "
                    f"{expected_usable!r} para coverage={coverage_value:.0%}."
                )

            if publishable is not expected_publishable:
                errors.append(
                    f"{ticker}: score.publishable={publishable!r}; esperado "
                    f"{expected_publishable!r} para coverage={coverage_value:.0%}."
                )

        # 3.5 normalized_score somente existe a partir da cobertura analitica.
        if status == "INSUFFICIENT_DATA":
            if normalized_score is not None:
                errors.append(
                    f"{ticker}: normalized_score deve ser null quando "
                    "status='INSUFFICIENT_DATA'."
                )
            if label is not None:
                errors.append(
                    f"{ticker}: score.label deve estar ausente quando "
                    "status='INSUFFICIENT_DATA'."
                )

        elif status in {"PARTIAL", "CALCULATED"}:
            if available_score is None or float(available_score) <= 0:
                errors.append(
                    f"{ticker}: available_score deve ser > 0 para status='{status}'."
                )
            elif raw_score is None:
                errors.append(
                    f"{ticker}: raw_score ausente para status='{status}'."
                )
            else:
                expected_normalized = round(
                    (float(raw_score) / float(available_score)) * 100.0, 2
                )
                expected_normalized = max(0.0, min(100.0, expected_normalized))

                if normalized_score is None:
                    errors.append(
                        f"{ticker}: normalized_score ausente para status='{status}'."
                    )
                elif abs(
                    float(normalized_score) - expected_normalized
                ) > SCORE_VALUE_TOLERANCE:
                    errors.append(
                        f"{ticker}: normalized_score={normalized_score} "
                        f"incoerente; esperado {expected_normalized:.2f}."
                    )

            # PARTIAL pode ser analisado, mas nao recebe label operacional.
            if status == "PARTIAL" and label is not None:
                errors.append(
                    f"{ticker}: score.label deve estar ausente enquanto "
                    "status='PARTIAL'."
                )

            # CALCULATED/publicavel recebe label sobre normalized_score,
            # nunca sobre raw_score.
            if status == "CALCULATED":
                if normalized_score is not None:
                    expected = expected_score_label(float(normalized_score))
                    if label != expected:
                        errors.append(
                            f"{ticker}: score.label='{label}' incoerente com "
                            f"normalized_score={normalized_score}. "
                            f"Esperado: '{expected}'."
                        )

                # decision.action so e comparada ao score quando existe
                # label operacional publicavel.
                decision = asset.get("decision", {})
                action = decision.get("action")
                if label in DECISION_ACTIONS_BY_SCORE_LABEL and action:
                    allowed = DECISION_ACTIONS_BY_SCORE_LABEL[label]
                    if action not in allowed:
                        warnings.append(
                            f"{ticker}: decision.action='{action}' e "
                            f"score.label='{label}' formam uma combinacao "
                            f"atipica. Permitidos/recomendados: "
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
