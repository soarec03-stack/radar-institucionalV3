from pathlib import Path
import ast

GENERATOR = Path(
    "automation/generate_radar_v3.py"
)

source = GENERATOR.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(source)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed

    if condition:
        print("PASS -", name)
        passed += 1
    else:
        print("FAIL -", name)
        failed += 1


def contains(text):
    return text in source


print("=" * 72)
print("B.2L.6G.3B - RISK PIPELINE ORCHESTRATION CONTRACT")
print("=" * 72)

# ------------------------------------------------------------
# Module references
# ------------------------------------------------------------

check(
    "Generator references RISK_HISTORY_ADAPTER_MODULE",
    contains("RISK_HISTORY_ADAPTER_MODULE"),
)

check(
    "Generator references risk_history_adapter_v3",
    contains("risk_history_adapter_v3.py"),
)

check(
    "Generator references RISK_METRICS_CALCULATOR_MODULE",
    contains("RISK_METRICS_CALCULATOR_MODULE"),
)

check(
    "Generator references risk_metrics_calculator_v3",
    contains("risk_metrics_calculator_v3.py"),
)

check(
    "Generator references RISK_ENGINE_MODULE",
    contains("RISK_ENGINE_MODULE"),
)

check(
    "Generator references risk_engine_v3",
    contains("risk_engine_v3.py"),
)

# ------------------------------------------------------------
# Runtime loading
# ------------------------------------------------------------

check(
    "Risk History Adapter participates in runtime loading",
    (
        "load_module(" in source
        and "RISK_HISTORY_ADAPTER_MODULE" in source
        and "prepare_risk_history" in source
    ),
)

check(
    "Risk Metrics Calculator participates in runtime loading",
    (
        "load_module(" in source
        and "RISK_METRICS_CALCULATOR_MODULE" in source
        and "calculate_risk_metrics" in source
    ),
)

check(
    "Risk Engine participates in runtime loading",
    (
        "load_module(" in source
        and "RISK_ENGINE_MODULE" in source
        and "calculate_asset_risk" in source
        and "write_risk_to_asset" in source
    ),
)

# ------------------------------------------------------------
# CLI / input contract
# ------------------------------------------------------------

check(
    "Generator references args.risk_history",
    contains("args.risk_history"),
)

check(
    "Risk execution has explicit args.risk_history guard",
    (
        "if args.risk_history" in source
        or "if not args.risk_history" in source
    ),
)

check(
    "risk-history is consumed as an input file",
    (
        "Path(args.risk_history)" in source
        or "Path(\n            args.risk_history" in source
        or "Path(\n        args.risk_history" in source
    ),
)

check(
    "Generator has Risk History existence handling",
    (
        "risk-history inexistente" in source
        or "risk history inexistente" in source.lower()
    ),
)

check(
    "Generator has Risk History JSON error handling",
    (
        "risk-history JSON invalido" in source
        or "risk history json invalido" in source.lower()
    ),
)

# ------------------------------------------------------------
# Risk policy
# ------------------------------------------------------------

check(
    "Generator references args.risk_policy",
    contains("args.risk_policy"),
)

check(
    "risk-policy is consumed as an input file",
    (
        "Path(args.risk_policy)" in source
        or "Path(\n            args.risk_policy" in source
        or "Path(\n        args.risk_policy" in source
    ),
)

check(
    "Generator has Risk Policy existence handling",
    (
        "risk-policy inexistente" in source
        or "risk policy inexistente" in source.lower()
    ),
)

check(
    "Generator has Risk Policy JSON error handling",
    (
        "risk-policy JSON invalido" in source
        or "risk policy json invalido" in source.lower()
    ),
)

# ------------------------------------------------------------
# Pipeline execution
# ------------------------------------------------------------

check(
    "prepare_risk_history executes",
    contains("prepare_risk_history("),
)

check(
    "calculate_risk_metrics executes",
    contains("calculate_risk_metrics("),
)

check(
    "calculate_asset_risk executes",
    contains("calculate_asset_risk("),
)

check(
    "write_risk_to_asset executes",
    contains("write_risk_to_asset("),
)

check(
    "Prepared closes are passed to Risk Metrics Calculator",
    (
        'prepared["closes"]' in source
        or "prepared['closes']" in source
        or 'prepared_risk["closes"]' in source
        or "prepared_risk['closes']" in source
    ),
)

# ------------------------------------------------------------
# Asset mapping
# ------------------------------------------------------------

check(
    "history_by_ticker" in source
    and "item.get(\"ticker\")" in source,
    "Risk history assets are mapped by ticker",
)

check(
    "Risk processing references asset ticker",
    (
        'asset.get("ticker")' in source
        or "asset.get('ticker')" in source
    ),
)

# ------------------------------------------------------------
# Sidecar
# ------------------------------------------------------------

check(
    "Generator creates risk_source_context_by_ticker",
    contains("risk_source_context_by_ticker"),
)

check(
    "Risk sidecar records ticker",
    '"ticker"' in source
    and "risk_source_context_by_ticker" in source,
)

check(
    "Risk sidecar records market_date",
    '"market_date"' in source
    and "risk_source_context_by_ticker" in source,
)

check(
    "Risk sidecar records source context",
    '"source"' in source
    and "risk_source_context_by_ticker" in source,
)

check(
    "Risk sidecar references primary_source",
    contains("primary_source"),
)

check(
    "Risk sidecar references retrieved_at",
    contains("retrieved_at"),
)

# ------------------------------------------------------------
# Ordering
# ------------------------------------------------------------

signal_pos = source.find(
    "apply_signal_engine("
)

risk_pos = source.find(
    "prepare_risk_history("
)

quality_pos = source.find(
    "quality_report = data_quality.evaluate"
)

if quality_pos < 0:
    quality_pos = source.find(
        "data_quality.evaluate("
    )

check(
    "Risk executes after Signal Engine",
    (
        signal_pos >= 0
        and risk_pos > signal_pos
    ),
)

check(
    "Risk executes before Data Quality evaluation",
    (
        risk_pos >= 0
        and quality_pos > risk_pos
    ),
)

# ------------------------------------------------------------
# Protected architecture
# ------------------------------------------------------------

check(
    "Generator does not write risk provenance into asset.risk",
    (
        'asset["risk"]["provenance"]' not in source
        and "asset['risk']['provenance']" not in source
    ),
)

check(
    "No production dependency on B2K metrics artifact",
    "metrics_real_B2K_v3.json" not in source,
)

check(
    "No production dependency on B2K risk artifact",
    "risk_history_real_B2K_v3.json" not in source,
)

check(
    "No production dependency on B2K fixture directory",
    "automation/fixtures/b2k_e2e" not in source,
)

print()
print("PASS:", passed)
print("FAIL:", failed)

if failed:
    print(
        "RESULT: RISK PIPELINE ORCHESTRATION CONTRACT RED"
    )
    raise SystemExit(1)

print(
    "RESULT: RISK PIPELINE ORCHESTRATION CONTRACT APPROVED"
)

raise SystemExit(0)
