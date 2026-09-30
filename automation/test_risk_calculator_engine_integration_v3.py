from copy import deepcopy
from pathlib import Path
import math
import sys


BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


from risk_metrics_calculator_v3 import (
    CALCULATOR_VERSION,
    calculate_risk_metrics,
)

from risk_engine_v3 import (
    ENGINE_VERSION,
    STATUS_CALCULATED,
    STATUS_UNAVAILABLE,
    calculate_asset_risk,
    load_policy,
    write_risk_to_asset,
)


TEST_VERSION = "3.4J.5B-B.2J.5B"

EXPECTED_CALCULATOR_VERSION = "3.4J.4B-B.2J.4B"
EXPECTED_ENGINE_VERSION = "3.4J.5A-B.2J.5A"
EXPECTED_POLICY_VERSION = "3.4J.3B-B.2J.3B"

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


def manual_piecewise(value, points, below_first, above_last):
    """
    Independent piecewise-linear reference used by this integration test.

    It intentionally does NOT call risk_engine_v3.normalize_piecewise().
    """
    if value < points[0][0]:
        return float(below_first)

    if value > points[-1][0]:
        return float(above_last)

    for index in range(len(points) - 1):
        x0, y0 = points[index]
        x1, y1 = points[index + 1]

        if value == x0:
            return float(y0)

        if value == x1:
            return float(y1)

        if x0 < value < x1:
            fraction = (value - x0) / (x1 - x0)
            return float(y0) + fraction * (
                float(y1) - float(y0)
            )

    if value == points[-1][0]:
        return float(points[-1][1])

    raise AssertionError(
        f"Could not independently normalize value {value}"
    )


def manual_sample_std(values):
    """
    Independent ddof=1 standard deviation reference.
    """
    mean_value = sum(values) / len(values)

    variance = sum(
        (value - mean_value) ** 2
        for value in values
    ) / (len(values) - 1)

    return math.sqrt(variance)


print("=" * 72)
print("B.2J.5B RISK CALCULATOR -> ENGINE INTEGRATION")
print(f"Test:       {TEST_VERSION}")
print(f"Calculator: {EXPECTED_CALCULATOR_VERSION}")
print(f"Engine:     {EXPECTED_ENGINE_VERSION}")
print(f"Policy:     {EXPECTED_POLICY_VERSION}")
print("=" * 72)


policy = load_policy()


# ---------------------------------------------------------------------
# VERSION / CONTRACT BOUNDARY
# ---------------------------------------------------------------------

check(
    CALCULATOR_VERSION == EXPECTED_CALCULATOR_VERSION,
    "Integration consumes the homologated B.2J.4B Calculator."
)

check(
    ENGINE_VERSION == EXPECTED_ENGINE_VERSION,
    "Integration consumes the homologated B.2J.5A Risk Engine."
)

check(
    policy.get("policy_version") == EXPECTED_POLICY_VERSION,
    "Integration consumes the homologated B.2J.3B Risk Policy."
)


# =====================================================================
# SCENARIO 1
# 60 CONSTANT CLOSES
#
# Full metric coverage:
#   volatility = 0
#   drawdown   = 0
#   downside   = 0
#
# Expected:
#   Risk = 0
#   Level = LOW
#   public asset.risk exists
# =====================================================================

constant_60 = [100.0] * 60

metrics_constant = calculate_risk_metrics(constant_60)

check(
    metrics_constant["realized_volatility_20d_pct"] == 0.0,
    "60 constant closes produce zero realized volatility."
)

check(
    metrics_constant["max_drawdown_60d_pct"] == 0.0,
    "60 constant closes produce zero max drawdown."
)

check(
    metrics_constant["downside_return_20d_pct"] == 0.0,
    "60 constant closes produce zero downside return."
)

risk_constant = calculate_asset_risk(
    metrics_constant,
    policy,
)

check(
    risk_constant["status"] == STATUS_CALCULATED,
    "Full constant history produces CALCULATED Risk."
)

check(
    risk_constant["coverage"] == 1.0,
    "60 valid closes produce full Risk metric coverage."
)

check(
    risk_constant["available_components"] == 3,
    "All three Risk components are available."
)

check(
    risk_constant["score"] == 0.0,
    "Zero-risk metrics produce Risk score 0."
)

check(
    risk_constant["level"] == "LOW",
    "Risk score 0 produces LOW level."
)

asset_constant = {
    "ticker": "TEST_CONSTANT",
    "name": "Synthetic Constant Asset",
}

written_constant = write_risk_to_asset(
    deepcopy(asset_constant),
    risk_constant,
)

check(
    "risk" in written_constant,
    "Calculated full-coverage Risk creates asset.risk."
)

check(
    set(written_constant["risk"].keys())
    == {
        "score",
        "level",
        "drivers",
    },
    "Integrated public asset.risk preserves strict Schema V3 shape."
)

check(
    written_constant["risk"]["score"] == 0.0,
    "Integrated asset.risk preserves Risk score 0."
)

check(
    written_constant["risk"]["level"] == "LOW",
    "Integrated asset.risk preserves LOW Risk level."
)


# =====================================================================
# SCENARIO 2
# 21 CONSTANT CLOSES
#
# Available:
#   volatility
#   downside
#
# Unavailable:
#   60d drawdown
#
# Coverage = 2/3
#
# Expected:
#   CALCULATED
#   weights renormalized
#   Risk = 0
# =====================================================================

constant_21 = [100.0] * 21

metrics_21 = calculate_risk_metrics(constant_21)

check(
    metrics_21["realized_volatility_20d_pct"] == 0.0,
    "21 closes make realized volatility available."
)

check(
    metrics_21["downside_return_20d_pct"] == 0.0,
    "21 closes make downside return available."
)

check(
    metrics_21["max_drawdown_60d_pct"] is None,
    "21 closes keep 60-day drawdown unavailable."
)

risk_21 = calculate_asset_risk(
    metrics_21,
    policy,
)

check(
    risk_21["status"] == STATUS_CALCULATED,
    "Two of three calculated metrics produce CALCULATED Risk."
)

check(
    close_enough(
        risk_21["coverage"],
        2.0 / 3.0,
    ),
    "21-close integration produces two-thirds Risk coverage."
)

check(
    risk_21["available_components"] == 2,
    "21-close integration reports two available Risk components."
)

check(
    risk_21["score"] == 0.0,
    "Two observed zero-risk metrics produce Risk score 0."
)

check(
    risk_21["level"] == "LOW",
    "Partial but sufficient zero-risk coverage produces LOW."
)

vol_component_21 = (
    risk_21["components"]["realized_volatility"]
)

downside_component_21 = (
    risk_21["components"]["downside_return"]
)

drawdown_component_21 = (
    risk_21["components"]["max_drawdown"]
)

check(
    close_enough(
        vol_component_21["effective_weight"],
        0.40 / (0.40 + 0.25),
    ),
    "Volatility weight is renormalized in 21-close integration."
)

check(
    close_enough(
        downside_component_21["effective_weight"],
        0.25 / (0.40 + 0.25),
    ),
    "Downside weight is renormalized in 21-close integration."
)

check(
    drawdown_component_21["available"] is False,
    "Unavailable drawdown does not enter partial Risk aggregation."
)

asset_21 = {
    "ticker": "TEST_21",
}

written_21 = write_risk_to_asset(
    deepcopy(asset_21),
    risk_21,
)

check(
    "risk" in written_21,
    "Sufficient two-thirds coverage creates public asset.risk."
)

check(
    written_21["risk"]["score"] == 0.0,
    "Partial-coverage public Risk preserves calculated score."
)


# =====================================================================
# SCENARIO 3
# 20 CLOSES
#
# All three metrics unavailable:
# - volatility needs 21
# - downside needs 21
# - drawdown needs 60
#
# Expected:
#   UNAVAILABLE
#   no fabricated public Risk
# =====================================================================

constant_20 = [100.0] * 20

metrics_20 = calculate_risk_metrics(constant_20)

check(
    metrics_20["realized_volatility_20d_pct"] is None,
    "20 closes leave realized volatility unavailable."
)

check(
    metrics_20["downside_return_20d_pct"] is None,
    "20 closes leave downside return unavailable."
)

check(
    metrics_20["max_drawdown_60d_pct"] is None,
    "20 closes leave max drawdown unavailable."
)

risk_20 = calculate_asset_risk(
    metrics_20,
    policy,
)

check(
    risk_20["status"] == STATUS_UNAVAILABLE,
    "Insufficient integrated metrics produce UNAVAILABLE Risk."
)

check(
    risk_20["coverage"] == 0.0,
    "No available Risk metrics produce zero coverage."
)

check(
    risk_20["score"] is None,
    "Unavailable integrated Risk has no score."
)

check(
    risk_20["level"] is None,
    "Unavailable integrated Risk has no level."
)

asset_20 = {
    "ticker": "TEST_20",
}

written_20 = write_risk_to_asset(
    deepcopy(asset_20),
    risk_20,
)

check(
    "risk" not in written_20,
    "Unavailable integrated Risk does not fabricate asset.risk."
)


# =====================================================================
# SCENARIO 4
# STALE RISK REMOVAL
# =====================================================================

stale_asset = {
    "ticker": "TEST_STALE",
    "risk": {
        "score": 88.0,
        "level": "CRITICAL",
        "drivers": [
            "STALE_RISK"
        ],
    },
}

cleaned_asset = write_risk_to_asset(
    deepcopy(stale_asset),
    risk_20,
)

check(
    "risk" not in cleaned_asset,
    "Unavailable integrated Risk removes stale asset.risk."
)


# =====================================================================
# SCENARIO 5
# NONTRIVIAL END-TO-END MATHEMATICAL REFERENCE
#
# We intentionally calculate the expected result independently from
# production functions.
#
# History:
# - 60 closes
# - deterministic changing path
#
# We independently calculate:
# - volatility
# - drawdown
# - downside
# - piecewise normalization
# - weighted Risk score
#
# Then compare against Calculator -> Engine.
# =====================================================================

nontrivial_closes = []

price = 100.0

for index in range(60):
    if index % 5 == 0:
        price *= 1.025
    elif index % 5 == 1:
        price *= 0.985
    elif index % 5 == 2:
        price *= 1.010
    elif index % 5 == 3:
        price *= 0.970
    else:
        price *= 1.005

    nontrivial_closes.append(price)


check(
    len(nontrivial_closes) == 60,
    "Nontrivial synthetic history contains exactly 60 closes."
)


# ---------------------------------------------------------------------
# Independent realized volatility reference
# ---------------------------------------------------------------------

last_21 = nontrivial_closes[-21:]

manual_returns = [
    last_21[index] / last_21[index - 1] - 1.0
    for index in range(1, len(last_21))
]

manual_volatility = (
    manual_sample_std(manual_returns)
    * math.sqrt(252)
    * 100.0
)

manual_volatility = round(
    manual_volatility,
    6,
)


# ---------------------------------------------------------------------
# Independent max drawdown reference
# ---------------------------------------------------------------------

last_60 = nontrivial_closes[-60:]

running_peak = last_60[0]
minimum_drawdown = 0.0

for close in last_60:
    running_peak = max(
        running_peak,
        close,
    )

    drawdown = (
        close / running_peak - 1.0
    )

    minimum_drawdown = min(
        minimum_drawdown,
        drawdown,
    )

manual_drawdown = round(
    abs(minimum_drawdown) * 100.0,
    6,
)


# ---------------------------------------------------------------------
# Independent downside reference
# ---------------------------------------------------------------------

manual_return_20d_pct = (
    last_21[-1] / last_21[0] - 1.0
) * 100.0

manual_downside = round(
    max(
        0.0,
        -manual_return_20d_pct,
    ),
    6,
)


metrics_nontrivial = calculate_risk_metrics(
    nontrivial_closes
)

check(
    metrics_nontrivial["realized_volatility_20d_pct"]
    == manual_volatility,
    "Calculator volatility matches independent integration reference."
)

check(
    metrics_nontrivial["max_drawdown_60d_pct"]
    == manual_drawdown,
    "Calculator drawdown matches independent integration reference."
)

check(
    metrics_nontrivial["downside_return_20d_pct"]
    == manual_downside,
    "Calculator downside matches independent integration reference."
)


# ---------------------------------------------------------------------
# Independent policy normalization reference
# ---------------------------------------------------------------------

policy_components = policy["components"]

vol_policy = (
    policy_components["realized_volatility"]["normalization"]
)

drawdown_policy = (
    policy_components["max_drawdown"]["normalization"]
)

downside_policy = (
    policy_components["downside_return"]["normalization"]
)

manual_normalized_vol = manual_piecewise(
    manual_volatility,
    vol_policy["points"],
    vol_policy["below_first"],
    vol_policy["above_last"],
)

manual_normalized_drawdown = manual_piecewise(
    manual_drawdown,
    drawdown_policy["points"],
    drawdown_policy["below_first"],
    drawdown_policy["above_last"],
)

manual_normalized_downside = manual_piecewise(
    manual_downside,
    downside_policy["points"],
    downside_policy["below_first"],
    downside_policy["above_last"],
)


manual_risk_score = (
    manual_normalized_vol * 0.40
    + manual_normalized_drawdown * 0.35
    + manual_normalized_downside * 0.25
)

manual_risk_score = round(
    manual_risk_score,
    2,
)


risk_nontrivial = calculate_asset_risk(
    metrics_nontrivial,
    policy,
)

check(
    risk_nontrivial["status"] == STATUS_CALCULATED,
    "Nontrivial full history produces CALCULATED Risk."
)

check(
    risk_nontrivial["coverage"] == 1.0,
    "Nontrivial 60-close history has full Risk coverage."
)

check(
    risk_nontrivial["score"] == manual_risk_score,
    "End-to-end Risk score matches independent mathematical reference."
)


# ---------------------------------------------------------------------
# Component-level independent comparison
# ---------------------------------------------------------------------

check(
    close_enough(
        risk_nontrivial["components"][
            "realized_volatility"
        ]["normalized_risk"],
        manual_normalized_vol,
    ),
    "Engine volatility normalization matches independent reference."
)

check(
    close_enough(
        risk_nontrivial["components"][
            "max_drawdown"
        ]["normalized_risk"],
        manual_normalized_drawdown,
    ),
    "Engine drawdown normalization matches independent reference."
)

check(
    close_enough(
        risk_nontrivial["components"][
            "downside_return"
        ]["normalized_risk"],
        manual_normalized_downside,
    ),
    "Engine downside normalization matches independent reference."
)


# ---------------------------------------------------------------------
# Public writer boundary
# ---------------------------------------------------------------------

asset_nontrivial = {
    "ticker": "TEST_NONTRIVIAL",
    "name": "Synthetic Nontrivial Asset",
}

written_nontrivial = write_risk_to_asset(
    deepcopy(asset_nontrivial),
    risk_nontrivial,
)

check(
    "risk" in written_nontrivial,
    "Nontrivial calculated Risk creates public asset.risk."
)

check(
    set(written_nontrivial["risk"].keys())
    == {
        "score",
        "level",
        "drivers",
    },
    "Nontrivial public Risk exposes only Schema V3 fields."
)

check(
    written_nontrivial["risk"]["score"]
    == manual_risk_score,
    "Public Risk preserves independently verified Risk score."
)

check(
    isinstance(
        written_nontrivial["risk"]["drivers"],
        list,
    ),
    "Public Risk drivers remain a list."
)

check(
    len(
        written_nontrivial["risk"]["drivers"]
    ) == 3,
    "Full nontrivial Risk contains three observable metric drivers."
)


# =====================================================================
# INPUT IMMUTABILITY
# =====================================================================

history_before = deepcopy(nontrivial_closes)

metrics_for_immutability = calculate_risk_metrics(
    nontrivial_closes
)

check(
    nontrivial_closes == history_before,
    "Calculator does not mutate historical Close input."
)

metrics_before = deepcopy(
    metrics_for_immutability
)

calculate_asset_risk(
    metrics_for_immutability,
    policy,
)

check(
    metrics_for_immutability == metrics_before,
    "Risk Engine does not mutate Calculator output."
)


# =====================================================================
# SUMMARY
# =====================================================================

print()
print("=" * 72)
print("B.2J.5B SUMMARY")
print(f"Checks: {passed + failed}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print("=" * 72)

if failed:
    print("RESULTADO: FAIL")
    raise SystemExit(1)

print("RESULTADO: PASS")