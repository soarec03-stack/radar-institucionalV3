import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = BASE_DIR / "automation" / "schema_v3.json"


def num(**kwargs):
    x = {"type": "number"}
    x.update(kwargs)
    return x


def object_schema(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def main():
    schema_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SCHEMA

    if not schema_path.exists():
        print(f"ERRO: schema não encontrado: {schema_path}")
        return 2

    original_text = schema_path.read_text(encoding="utf-8")
    schema = json.loads(original_text)

    backup_path = schema_path.with_suffix(
        schema_path.suffix + ".before_signal_metrics"
    )
    if not backup_path.exists():
        backup_path.write_text(original_text, encoding="utf-8")

    defs = schema.setdefault("$defs", {})

    defs["fundamentalMetrics"] = object_schema({
        "revenue_growth_pct": num(),
        "eps_growth_pct": num(),
        "fcf_margin_pct": num(),
        "debt_to_ebitda": num(),
        "earnings_revision_pct": num(),
        "valuation_percentile": num(minimum=0, maximum=100),
        "normalized_score": num(minimum=0, maximum=100),
    })

    defs["technicalMetrics"] = object_schema({
        "price_vs_sma50_pct": num(),
        "price_vs_sma200_pct": num(),
        "rsi_14": num(minimum=0, maximum=100),
        "macd_histogram_pct": num(),
        "relative_strength_20d_pct": num(),
        "volume_ratio": num(minimum=0),
        "return_20d_pct": num(),
        "return_60d_pct": num(),
        "normalized_score": num(minimum=0, maximum=100),
        "momentum_score": num(minimum=0, maximum=100),
    })

    defs["institutionalFlowMetrics"] = object_schema({
        "institutional_flow_pct": num(),
        "volume_ratio": num(minimum=0),
        "short_interest_change_pct": num(),
        "call_put_ratio": num(minimum=0),
        "normalized_score": num(minimum=0, maximum=100),
    })

    defs["macroMetrics"] = object_schema({
        "rates_change_20d_bps": num(),
        "dollar_change_20d_pct": num(),
        "liquidity_change_20d_pct": num(),
        "sector_macro_surprise_pct": num(),
        "normalized_score": num(minimum=0, maximum=100),
    })

    defs["catalystMetricItem"] = object_schema({
        "description": {"type": "string"},
        "signed_impact": num(minimum=-100, maximum=100),
        "probability": num(minimum=0, maximum=1),
        "source_quality": num(minimum=0, maximum=1),
        "horizon_days": num(minimum=0),
    }, required=[
        "signed_impact", "probability", "source_quality", "horizon_days"
    ])

    defs["catalystMetrics"] = object_schema({
        "items": {
            "type": "array",
            "items": {"$ref": "#/$defs/catalystMetricItem"},
            "minItems": 1,
        },
        "normalized_score": num(minimum=0, maximum=100),
    })

    asset_def = defs.get("asset")
    if not isinstance(asset_def, dict):
        print("ERRO: $defs.asset não encontrado.")
        return 2

    asset_props = asset_def.setdefault("properties", {})
    dp = asset_props.get("data_points")
    if not isinstance(dp, dict):
        print("ERRO: $defs.asset.properties.data_points não encontrado.")
        return 2

    dp_props = dp.setdefault("properties", {})

    # Somente data points ainda inexistentes no Radar atual são restringidos
    # nesta etapa. Catalysts permanece legado/compatível e será migrado depois.
    mappings = {
        "fundamentals": "#/$defs/fundamentalMetrics",
        "technical": "#/$defs/technicalMetrics",
        "institutional_flow": "#/$defs/institutionalFlowMetrics",
        "macro": "#/$defs/macroMetrics",
    }

    for point_name, metrics_ref in mappings.items():
        dp_props[point_name] = {
            "allOf": [
                {"$ref": "#/$defs/dataPoint"},
                {
                    "properties": {
                        "value": {
                            "oneOf": [
                                {"type": "null"},
                                {"$ref": metrics_ref}
                            ]
                        }
                    }
                }
            ]
        }

    schema_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("OK schema_v3.json atualizado com contrato de métricas do Signal Engine.")
    print(f"Backup original: {backup_path}")
    print("Estruturados agora:")
    for name in mappings:
        print(f"  - {name}")
    print("Catalysts: preservado no formato atual para compatibilidade.")
    print("Nenhum novo data point foi tornado obrigatório.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
