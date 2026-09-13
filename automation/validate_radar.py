#!/usr/bin/env python3
"""
Radar Institucional V2.1
Fluxo: texto/JSON de entrada -> validação -> radar.json

Uso:
  python automation/validate_radar.py input/radar_input.txt
  python automation/validate_radar.py input/radar_input.txt --output radar.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REQUIRED_TOP_LEVEL = [
    "schema_version", "radar", "global_market", "macro", "brazil",
    "foreign_flow", "futures", "sectors", "power_data_center",
    "nuclear", "swing_trades", "penny_stocks", "portfolio",
    "broker_recommendations", "fundamental_analysis",
    "technical_analysis", "catalysts", "alerts", "ranking",
    "operational_conclusion", "sources",
]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def fail(errors, message):
    errors.append(message)

def extract_json(text: str):
    # Prefer the automation delimiters when present.
    m = re.search(
        r"===\s*RADAR_JSON_START\s*===\s*(.*?)\s*===\s*RADAR_JSON_END\s*===",
        text, re.S | re.I
    )
    candidate = m.group(1) if m else text

    first = candidate.find("{")
    if first < 0:
        raise ValueError("Nenhum objeto JSON foi encontrado.")

    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(candidate[first:])
    return obj

def validate(data):
    errors = []
    warnings = []

    if not isinstance(data, dict):
        fail(errors, "A raiz do documento precisa ser um objeto JSON.")
        return errors, warnings

    missing = [k for k in REQUIRED_TOP_LEVEL if k not in data]
    if missing:
        fail(errors, "Campos obrigatórios ausentes: " + ", ".join(missing))

    if data.get("schema_version") != "2.1":
        fail(errors, "schema_version deve ser exatamente '2.1'.")

    radar = data.get("radar")
    if not isinstance(radar, dict):
        fail(errors, "radar deve ser um objeto.")
    else:
        for k in ["date", "generated_at", "timezone", "status",
                  "market_regime", "institutional_sentiment",
                  "daily_bias", "risk_level", "summary"]:
            if k not in radar:
                fail(errors, f"radar.{k} ausente.")
        if "date" in radar and (
            not isinstance(radar["date"], str) or not DATE_RE.match(radar["date"])
        ):
            fail(errors, "radar.date deve estar no formato YYYY-MM-DD.")

        if "generated_at" in radar:
            try:
                datetime.fromisoformat(radar["generated_at"].replace("Z", "+00:00"))
            except Exception:
                fail(errors, "radar.generated_at deve ser ISO 8601.")

    array_fields = [
        "macro", "sectors", "power_data_center", "nuclear",
        "swing_trades", "penny_stocks", "portfolio",
        "fundamental_analysis", "technical_analysis",
        "catalysts", "alerts", "ranking", "sources"
    ]
    for field in array_fields:
        if field in data and not isinstance(data[field], list):
            fail(errors, f"{field} deve ser uma lista.")

    # Ranking integrity: if present, enforce 1..10 without duplicates.
    ranking = data.get("ranking")
    if isinstance(ranking, list):
        if len(ranking) != 10:
            fail(errors, f"ranking deve conter 10 posições; encontrado: {len(ranking)}.")
        ranks = [x.get("rank") for x in ranking if isinstance(x, dict)]
        if ranks != list(range(1, 11)):
            fail(errors, "ranking deve conter ranks exatamente de 1 a 10, na ordem.")
        tickers = [x.get("ticker") for x in ranking if isinstance(x, dict)]
        if any(not t for t in tickers):
            fail(errors, "Todos os itens do ranking precisam ter ticker.")
        if len(tickers) != len(set(tickers)):
            fail(errors, "Há ticker duplicado no ranking.")

    # Minimum integrity for source records.
    sources = data.get("sources")
    if isinstance(sources, list):
        for i, item in enumerate(sources):
            if not isinstance(item, dict):
                fail(errors, f"sources[{i}] deve ser objeto.")
            elif not item.get("name"):
                fail(errors, f"sources[{i}].name ausente.")

    # Useful consistency warnings (not hard failures).
    if isinstance(data.get("penny_stocks"), list) and len(data["penny_stocks"]) < 1:
        warnings.append("penny_stocks está vazio.")

    if isinstance(data.get("sectors"), list) and len(data["sectors"]) < 1:
        warnings.append("sectors está vazio.")

    return errors, warnings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Arquivo de texto contendo o Radar/JSON")
    parser.add_argument("--output", default="radar.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERRO: arquivo não encontrado: {input_path}")
        return 2

    try:
        text = input_path.read_text(encoding="utf-8")
        data = extract_json(text)
    except Exception as exc:
        print(f"ERRO: JSON inválido ou não encontrado: {exc}")
        return 2

    errors, warnings = validate(data)

    print("=== VALIDAÇÃO RADAR INSTITUCIONAL V2.1 ===")
    print(f"Entrada: {input_path}")

    for warning in warnings:
        print(f"AVISO: {warning}")

    if errors:
        for error in errors:
            print(f"ERRO: {error}")
        print("RESULTADO: REJEITADO")
        print(f"{output_path} NÃO foi atualizado.")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("✓ JSON válido")
    print("✓ Estrutura V2.1 válida")
    print("✓ Ranking 1–10 válido")
    print("RESULTADO: APROVADO")
    print(f"Gerado: {output_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
