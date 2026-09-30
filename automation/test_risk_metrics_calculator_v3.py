import math
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


from risk_metrics_calculator_v3 import (
    CALCULATOR_VERSION,
    calculate_daily_returns,
    calculate_downside_return_20d_pct,
    calculate_max_drawdown_60d_pct,
    calculate_realized_volatility_20d_pct,
    calculate_risk_metrics,
    is_valid_close,
    normalize_closes,
)


EXPECTED_VERSION = "3.4J.4B-B.2J.4B"

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


def close_enough(actual, expected, tolerance=1e-6):
    if actual is None:
        return False

    return abs(actual - expected) <= tolerance


print("=" * 72)
print("B.2J.4B RISK METRICS CALCULATOR")
print(f"Calculator: {EXPECTED_VERSION}")
print("=" * 72)


# ---------------------------------------------------------------------
# VERSION
# ---------------------------------------------------------------------

check(
    CALCULATOR_VERSION == EXPECTED_VERSION,
    "Risk Metrics Calculator version is B.2J.4B."
)


# ---------------------------------------------------------------------
# CLOSE VALIDATION
# ---------------------------------------------------------------------

check(
    is_valid_close(100) is True,
    "Positive integer Close is valid."
)

check(
    is_valid_close(100.5) is True,
    "Positive float Close is valid."
)

check(
    is_valid_close(0) is False,
    "Zero Close is invalid."
)

check(
    is_valid_close(-1) is False,
    "Negative Close is invalid."
)

check(
    is_valid_close(None) is False,
    "Null Close is invalid."
)

check(
    is_valid_close("100") is False,
    "String Close is invalid."
)

check(
    is_valid_close(True) is False,
    "Boolean Close is invalid."
)

check(
    is_valid_close(float("nan")) is False,
    "NaN Close is invalid."
)

check(
    is_valid_close(float("inf")) is False,
    "Infinite Close is invalid."
)


# ---------------------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------------------

normalized = normalize_closes(
    [100, None, 101, 0, -5, 102.5, "103", float("nan")]
)

check(
    normalized == [100.0, 101.0, 102.5],
    "Invalid/missing Close observations are dropped."
)

check(
    normalize_closes(None) == [],
    "Null Close collection normalizes to empty history."
)


# ---------------------------------------------------------------------
# DAILY RETURNS
# ---------------------------------------------------------------------

returns = calculate_daily_returns([100, 110, 99])

check(
    len(returns) == 2,
    "Three closes produce two daily returns."
)

check(
    close_enough(returns[0], 0.10),
    "First daily return is calculated correctly."
)

check(
    close_enough(returns[1], -0.10),
    "Second daily return is calculated correctly."
)


# ---------------------------------------------------------------------
# INSUFFICIENT HISTORY BOUNDARIES
# ---------------------------------------------------------------------

check(
    calculate_realized_volatility_20d_pct([100.0] * 20) is None,
    "20 closes are insufficient for 20-day realized volatility."
)

check(
    calculate_downside_return_20d_pct([100.0] * 20) is None,
    "20 closes are insufficient for 20-day downside return."
)

check(
    calculate_max_drawdown_60d_pct([100.0] * 59) is None,
    "59 closes are insufficient for 60-day max drawdown."
)


# ---------------------------------------------------------------------
# EXACT HISTORY BOUNDARIES
# ---------------------------------------------------------------------

check(
    calculate_realized_volatility_20d_pct([100.0] * 21) == 0.0,
    "21 constant closes produce zero realized volatility."
)

check(
    calculate_downside_return_20d_pct([100.0] * 21) == 0.0,
    "21 constant closes produce zero downside return."
)

check(
    calculate_max_drawdown_60d_pct([100.0] * 60) == 0.0,
    "60 constant closes produce zero max drawdown."
)


# ---------------------------------------------------------------------
# POSITIVE TREND
# ---------------------------------------------------------------------

increasing_21 = [100.0 + index for index in range(21)]

check(
    calculate_downside_return_20d_pct(increasing_21) == 0.0,
    "Positive 20-session return produces zero downside risk."
)


# ---------------------------------------------------------------------
# KNOWN DOWNSIDE RETURN
# ---------------------------------------------------------------------

downside_history = [100.0] + [100.0] * 19 + [80.0]

check(
    calculate_downside_return_20d_pct(downside_history) == 20.0,
    "100 to 80 over 20 sessions produces 20 percent downside."
)


# ---------------------------------------------------------------------
# KNOWN MAX DRAWDOWN
# ---------------------------------------------------------------------

drawdown_history = [100.0] * 10 + [120.0] + [90.0] + [90.0] * 48

check(
    len(drawdown_history) == 60,
    "Synthetic drawdown history contains exactly 60 closes."
)

check(
    calculate_max_drawdown_60d_pct(drawdown_history) == 25.0,
    "120 peak to 90 trough produces 25 percent max drawdown."
)


# ---------------------------------------------------------------------
# PRE-WINDOW PEAK MUST NOT AFFECT DRAWDOWN
# ---------------------------------------------------------------------

pre_window_peak_history = [200.0] + [100.0] * 60

check(
    calculate_max_drawdown_60d_pct(pre_window_peak_history) == 0.0,
    "Pre-window historical peak does not affect 60-day drawdown."
)


# ---------------------------------------------------------------------
# LAST WINDOW ONLY
# ---------------------------------------------------------------------

old_volatility = [
    100.0,
    150.0,
    75.0,
    140.0,
    80.0,
]

constant_tail = [100.0] * 21

check(
    calculate_realized_volatility_20d_pct(
        old_volatility + constant_tail
    ) == 0.0,
    "Realized volatility uses only the last 21 valid closes."
)


# ---------------------------------------------------------------------
# SAMPLE STANDARD DEVIATION / DDOF=1
# ---------------------------------------------------------------------

alternating_closes = [100.0]

for index in range(20):
    if index % 2 == 0:
        alternating_closes.append(
            alternating_closes[-1] * 1.01
        )
    else:
        alternating_closes.append(
            alternating_closes[-1] * 0.99
        )

manual_returns = [
    alternating_closes[index]
    / alternating_closes[index - 1]
    - 1.0
    for index in range(1, len(alternating_closes))
]

mean_return = sum(manual_returns) / len(manual_returns)

sample_variance = sum(
    (value - mean_return) ** 2
    for value in manual_returns
) / (len(manual_returns) - 1)

expected_volatility = (
    math.sqrt(sample_variance)
    * math.sqrt(252)
    * 100.0
)

expected_volatility = round(expected_volatility, 6)

actual_volatility = calculate_realized_volatility_20d_pct(
    alternating_closes
)

check(
    actual_volatility == expected_volatility,
    "Realized volatility matches independent ddof=1 calculation."
)


# ---------------------------------------------------------------------
# OUTPUT ROUNDING
# ---------------------------------------------------------------------

check(
    actual_volatility
    == round(actual_volatility, 6),
    "Realized volatility output is rounded to six decimals."
)


# ---------------------------------------------------------------------
# AGGREGATE METRICS FUNCTION
# ---------------------------------------------------------------------

full_constant_history = [100.0] * 60

metrics = calculate_risk_metrics(full_constant_history)

check(
    set(metrics.keys())
    == {
        "realized_volatility_20d_pct",
        "max_drawdown_60d_pct",
        "downside_return_20d_pct",
    },
    "Calculator emits exactly the three canonical Risk metrics."
)

check(
    metrics["realized_volatility_20d_pct"] == 0.0,
    "Aggregate calculator emits zero volatility for constant prices."
)

check(
    metrics["max_drawdown_60d_pct"] == 0.0,
    "Aggregate calculator emits zero drawdown for constant prices."
)

check(
    metrics["downside_return_20d_pct"] == 0.0,
    "Aggregate calculator emits zero downside for constant prices."
)


# ---------------------------------------------------------------------
# PARTIAL HISTORY MUST REMAIN PARTIAL
# ---------------------------------------------------------------------

partial_metrics = calculate_risk_metrics([100.0] * 21)

check(
    partial_metrics["realized_volatility_20d_pct"] == 0.0,
    "21 closes make realized volatility available."
)

check(
    partial_metrics["downside_return_20d_pct"] == 0.0,
    "21 closes make downside return available."
)

check(
    partial_metrics["max_drawdown_60d_pct"] is None,
    "21 closes do not fabricate 60-day drawdown."
)


# ---------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------

print()
print("=" * 72)
print("B.2J.4B SUMMARY")
print(f"Checks: {passed + failed}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print("=" * 72)

if failed:
    print("RESULTADO: FAIL")
    raise SystemExit(1)

print("RESULTADO: PASS")