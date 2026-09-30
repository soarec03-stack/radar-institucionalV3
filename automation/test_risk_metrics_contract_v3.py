import json
import math
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONTRACT_PATH = BASE_DIR / "risk_metrics_contract_v3.json"

EXPECTED_CONTRACT_VERSION = "3.4J.4A-B.2J.4A"

passed = 0
failed = 0


def check(condition, description):
    global passed, failed

    if condition:
        passed += 1
        print(f"[PASS] {description}")
    else:
        failed += 1
        print(f"[FAIL] {description}")


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


print("=" * 72)
print("B.2J.4A RISK METRICS MATHEMATICAL CONTRACT")
print(f"Contract: {EXPECTED_CONTRACT_VERSION}")
print("=" * 72)

contract = load_json(CONTRACT_PATH)


# ---------------------------------------------------------------------
# CONTRACT IDENTITY
# ---------------------------------------------------------------------

check(
    contract.get("contract_name")
    == "RADAR_INSTITUCIONAL_RISK_METRICS_V3",
    "Risk Metrics Contract has canonical name."
)

check(
    contract.get("contract_version") == EXPECTED_CONTRACT_VERSION,
    "Risk Metrics Contract version is B.2J.4A."
)


# ---------------------------------------------------------------------
# GLOBAL PRINCIPLES
# ---------------------------------------------------------------------

principles = contract.get("principles", {})

check(
    principles.get("no_invented_metrics") is True,
    "Risk Metrics Contract forbids invented metrics."
)

check(
    principles.get("missing_metric") is None,
    "Missing Risk metric is represented by null."
)

check(
    principles.get("missing_is_not_neutral") is True,
    "Missing Risk metric is not neutral."
)

check(
    principles.get("risk_score_is_engine_output") is True,
    "Risk score remains an engine output."
)

check(
    principles.get("research_only_source_cannot_authorize_publication")
    is True,
    "Research-only source cannot authorize official publication."
)

check(
    principles.get("deterministic_derivation_required") is True,
    "Risk metric derivation must be deterministic."
)

check(
    principles.get("insufficient_observations_produce_null") is True,
    "Insufficient observations produce null."
)


# ---------------------------------------------------------------------
# MARKET DATA INPUT
# ---------------------------------------------------------------------

market_data = contract.get("market_data_input", {})

check(
    market_data.get("required_field") == "Close",
    "Close is the required market-data field."
)

check(
    market_data.get("frequency") == "1d",
    "Risk metrics use daily market data."
)

check(
    market_data.get("ordering") == "ASCENDING_BY_MARKET_DATE",
    "Risk market data must be ordered ascending by market date."
)

valid_observation = market_data.get("valid_observation", {})

check(
    valid_observation.get("type") == "number",
    "Valid Close observation must be numeric."
)

check(
    valid_observation.get("strictly_positive") is True,
    "Valid Close observation must be strictly positive."
)

check(
    market_data.get("missing_close_policy")
    == "DROP_BEFORE_CALCULATION",
    "Missing Close observations are dropped before calculation."
)

check(
    market_data.get("duplicate_market_date_policy") == "REJECT",
    "Duplicate market dates are rejected."
)

check(
    market_data.get("minimum_history_observations") == 60,
    "Full Risk metric set requires at least 60 valid Close observations."
)


# ---------------------------------------------------------------------
# METRIC SET
# ---------------------------------------------------------------------

metrics = contract.get("metrics", {})

expected_metrics = {
    "realized_volatility_20d_pct",
    "max_drawdown_60d_pct",
    "downside_return_20d_pct",
}

check(
    set(metrics.keys()) == expected_metrics,
    "Contract declares exactly the three canonical Risk metrics."
)


# ---------------------------------------------------------------------
# REALIZED VOLATILITY
# ---------------------------------------------------------------------

volatility = metrics.get("realized_volatility_20d_pct", {})

check(
    volatility.get("type") == "number",
    "Realized volatility output is numeric."
)

check(
    volatility.get("minimum") == 0,
    "Realized volatility cannot be negative."
)

check(
    volatility.get("unit") == "%",
    "Realized volatility output unit is percent."
)

check(
    volatility.get("direction") == "HIGHER_IS_RISKIER",
    "Higher realized volatility means higher measured risk."
)

check(
    volatility.get("derivation")
    == "STD_DAILY_RETURNS_20D_ANNUALIZED_SQRT_252",
    "Realized volatility derivation is explicitly declared."
)

vol_window = volatility.get("window", {})

check(
    vol_window.get("return_observations") == 20,
    "Realized volatility uses exactly 20 daily returns."
)

check(
    vol_window.get("close_observations_required") == 21,
    "Realized volatility requires 21 valid Close observations."
)

check(
    volatility.get("daily_return_formula")
    == "close_t / close_t_minus_1 - 1",
    "Daily return formula is explicitly declared."
)

std_policy = volatility.get("standard_deviation", {})

check(
    std_policy.get("mode") == "SAMPLE",
    "Realized volatility uses sample standard deviation."
)

check(
    std_policy.get("ddof") == 1,
    "Realized volatility uses ddof=1."
)

annualization = volatility.get("annualization", {})

check(
    annualization.get("trading_periods_per_year") == 252,
    "Volatility annualization uses 252 trading periods."
)

check(
    annualization.get("factor") == "SQRT_252",
    "Volatility annualization factor is sqrt(252)."
)

check(
    math.isclose(math.sqrt(252), 15.874507866387544),
    "sqrt(252) mathematical reference is stable."
)

vol_rounding = volatility.get("rounding", {})

check(
    vol_rounding.get("calculation") == "NO_INTERMEDIATE_ROUNDING",
    "Volatility calculation forbids intermediate rounding."
)

check(
    vol_rounding.get("output_decimals") == 6,
    "Volatility output uses six decimal places."
)

check(
    volatility.get("insufficient_data_output") is None,
    "Insufficient volatility history produces null."
)


# ---------------------------------------------------------------------
# MAX DRAWDOWN
# ---------------------------------------------------------------------

drawdown = metrics.get("max_drawdown_60d_pct", {})

check(
    drawdown.get("type") == "number",
    "Max drawdown output is numeric."
)

check(
    drawdown.get("minimum") == 0,
    "Max drawdown cannot be negative."
)

check(
    drawdown.get("maximum") == 100,
    "Max drawdown cannot exceed 100 percent."
)

check(
    drawdown.get("unit") == "%",
    "Max drawdown output unit is percent."
)

check(
    drawdown.get("direction") == "HIGHER_IS_RISKIER",
    "Higher max drawdown means higher measured risk."
)

check(
    drawdown.get("derivation")
    == "ABS_MAX_PEAK_TO_TROUGH_DRAWDOWN_WITHIN_60D_WINDOW",
    "Max drawdown derivation is explicitly declared."
)

dd_window = drawdown.get("window", {})

check(
    dd_window.get("close_observations") == 60,
    "Max drawdown uses exactly 60 valid Close observations."
)

check(
    dd_window.get("scope") == "LAST_60_VALID_CLOSE_OBSERVATIONS",
    "Max drawdown operates on the last 60 valid closes."
)

check(
    dd_window.get("peak_scope") == "WITHIN_WINDOW_ONLY",
    "Drawdown running peak is restricted to the 60-day window."
)

check(
    drawdown.get("running_peak_formula")
    == "max(close_window_0_through_t)",
    "Drawdown running-peak formula is explicitly declared."
)

check(
    drawdown.get("drawdown_formula")
    == "close_t / running_peak_t - 1",
    "Drawdown formula is explicitly declared."
)

check(
    drawdown.get("pre_window_peak_allowed") is False,
    "Pre-window historical peak is forbidden."
)

dd_rounding = drawdown.get("rounding", {})

check(
    dd_rounding.get("calculation") == "NO_INTERMEDIATE_ROUNDING",
    "Drawdown calculation forbids intermediate rounding."
)

check(
    dd_rounding.get("output_decimals") == 6,
    "Drawdown output uses six decimal places."
)

check(
    drawdown.get("insufficient_data_output") is None,
    "Insufficient drawdown history produces null."
)


# ---------------------------------------------------------------------
# DOWNSIDE RETURN
# ---------------------------------------------------------------------

downside = metrics.get("downside_return_20d_pct", {})

check(
    downside.get("type") == "number",
    "Downside return output is numeric."
)

check(
    downside.get("minimum") == 0,
    "Downside return cannot be negative."
)

check(
    downside.get("unit") == "%",
    "Downside return output unit is percent."
)

check(
    downside.get("direction") == "HIGHER_IS_RISKIER",
    "Higher downside return means higher measured risk."
)

check(
    downside.get("derivation")
    == "NEGATIVE_PART_OF_20D_CLOSE_TO_CLOSE_RETURN",
    "Downside return derivation is explicitly declared."
)

downside_window = downside.get("window", {})

check(
    downside_window.get("return_sessions") == 20,
    "Downside return measures exactly 20 sessions."
)

check(
    downside_window.get("close_observations_required") == 21,
    "Downside return requires 21 valid Close observations."
)

check(
    downside.get("return_formula")
    == "(latest_close / close_20_sessions_ago - 1) * 100",
    "20-day close-to-close return formula is explicitly declared."
)

check(
    downside.get("output_formula")
    == "max(0, -return_20d_pct)",
    "Downside output uses only the negative part of 20-day return."
)

check(
    downside.get("positive_return_output") == 0,
    "Positive 20-day return produces zero downside risk."
)

downside_rounding = downside.get("rounding", {})

check(
    downside_rounding.get("calculation")
    == "NO_INTERMEDIATE_ROUNDING",
    "Downside calculation forbids intermediate rounding."
)

check(
    downside_rounding.get("output_decimals") == 6,
    "Downside output uses six decimal places."
)

check(
    downside.get("insufficient_data_output") is None,
    "Insufficient downside-return history produces null."
)


# ---------------------------------------------------------------------
# CONTEXT
# ---------------------------------------------------------------------

required_context = contract.get("required_context", {})

check(
    set(required_context.keys()) == {
        "ticker",
        "market_date",
        "source",
    },
    "Risk Metrics Contract requires ticker, market_date and source."
)

check(
    required_context.get("ticker", {}).get("type") == "string",
    "Ticker context is a string."
)

check(
    required_context.get("market_date", {}).get("format") == "date",
    "Market date uses date format."
)

source_context = required_context.get("source", {})

check(
    source_context.get("type") == "object",
    "Source context is an object."
)

check(
    source_context.get("required")
    == ["primary_source", "retrieved_at"],
    "Source context requires primary_source and retrieved_at."
)


# ---------------------------------------------------------------------
# SOURCE GOVERNANCE
# ---------------------------------------------------------------------

source_governance = contract.get("source_governance", {})

check(
    source_governance.get("source_must_be_registered") is True,
    "Risk metric source must be registered."
)

check(
    source_governance.get(
        "source_publication_eligibility_evaluated_separately"
    ) is True,
    "Source publication eligibility is evaluated separately."
)

check(
    source_governance.get(
        "research_only_source_may_produce_metrics_for_methodology_testing"
    ) is True,
    "Research-only source may produce methodology-test Risk metrics."
)

check(
    source_governance.get(
        "research_only_source_may_authorize_official_publication"
    ) is False,
    "Research-only source cannot authorize official Risk publication."
)


# ---------------------------------------------------------------------
# ENGINE OUTPUT BOUNDARY
# ---------------------------------------------------------------------

forbidden = set(
    contract.get("engine_output_forbidden_in_input", [])
)

expected_forbidden = {
    "risk_score",
    "risk_level",
    "normalized_risk_score",
    "radar_points",
    "decision",
}

check(
    forbidden == expected_forbidden,
    "Risk metric input forbids exactly the declared engine outputs."
)


# ---------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------

print()
print("=" * 72)
print("B.2J.4A SUMMARY")
print(f"Checks: {passed + failed}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print("=" * 72)

if failed:
    print("RESULTADO: FAIL")
    raise SystemExit(1)

print("RESULTADO: PASS")