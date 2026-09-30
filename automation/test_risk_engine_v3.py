from copy import deepcopy
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


from risk_engine_v3 import (
    ENGINE_VERSION,
    STATUS_CALCULATED,
    STATUS_UNAVAILABLE,
    build_public_risk,
    calculate_asset_risk,
    calculate_component,
    load_policy,
    normalize_piecewise,
    resolve_risk_level,
    write_risk_to_asset,
)


EXPECTED_VERSION = "3.4J.5A-B.2J.5A"

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


def close_enough(actual, expected, tolerance=1e-9):
    if actual is None:
        return False

    return abs(actual - expected) <= tolerance


print("=" * 72)
print("B.2J.5A ASSET RISK ENGINE")
print(f"Engine: {EXPECTED_VERSION}")
print("=" * 72)

policy = load_policy()
components = policy["components"]


# ---------------------------------------------------------------------
# VERSION / POLICY
# ---------------------------------------------------------------------

check(
    ENGINE_VERSION == EXPECTED_VERSION,
    "Risk Engine version is B.2J.5A."
)

check(
    policy.get("policy_version") == "3.4J.3B-B.2J.3B",
    "Risk Engine consumes the homologated B.2J.3B Policy."
)


# ---------------------------------------------------------------------
# PIECEWISE-LINEAR NORMALIZATION
# ---------------------------------------------------------------------

vol_norm = components["realized_volatility"]["normalization"]

check(
    normalize_piecewise(10.0, vol_norm) == 0.0,
    "Volatility exact first anchor maps to Risk 0."
)

check(
    normalize_piecewise(20.0, vol_norm) == 20.0,
    "Volatility exact second anchor maps to Risk 20."
)

check(
    normalize_piecewise(30.0, vol_norm) == 40.0,
    "Volatility exact third anchor maps to Risk 40."
)

check(
    normalize_piecewise(45.0, vol_norm) == 60.0,
    "Volatility exact fourth anchor maps to Risk 60."
)

check(
    normalize_piecewise(65.0, vol_norm) == 80.0,
    "Volatility exact fifth anchor maps to Risk 80."
)

check(
    normalize_piecewise(90.0, vol_norm) == 100.0,
    "Volatility exact final anchor maps to Risk 100."
)

check(
    normalize_piecewise(15.0, vol_norm) == 10.0,
    "Volatility interpolation between 10 and 20 is linear."
)

check(
    normalize_piecewise(37.5, vol_norm) == 50.0,
    "Volatility interpolation between 30 and 45 is linear."
)

check(
    normalize_piecewise(0.0, vol_norm) == 0.0,
    "Volatility below first anchor clamps to Risk 0."
)

check(
    normalize_piecewise(150.0, vol_norm) == 100.0,
    "Volatility above final anchor clamps to Risk 100."
)


# ---------------------------------------------------------------------
# OTHER COMPONENT ANCHORS
# ---------------------------------------------------------------------

drawdown_norm = components["max_drawdown"]["normalization"]

check(
    normalize_piecewise(5.0, drawdown_norm) == 0.0,
    "Drawdown first anchor maps to Risk 0."
)

check(
    normalize_piecewise(20.0, drawdown_norm) == 40.0,
    "Drawdown 20 percent maps to Risk 40."
)

check(
    normalize_piecewise(60.0, drawdown_norm) == 100.0,
    "Drawdown final anchor maps to Risk 100."
)

check(
    normalize_piecewise(100.0, drawdown_norm) == 100.0,
    "Drawdown above final anchor clamps to Risk 100."
)

downside_norm = components["downside_return"]["normalization"]

check(
    normalize_piecewise(0.0, downside_norm) == 0.0,
    "Downside zero maps to Risk 0."
)

check(
    normalize_piecewise(10.0, downside_norm) == 40.0,
    "Downside 10 percent maps to Risk 40."
)

check(
    normalize_piecewise(40.0, downside_norm) == 100.0,
    "Downside final anchor maps to Risk 100."
)

check(
    normalize_piecewise(80.0, downside_norm) == 100.0,
    "Downside above final anchor clamps to Risk 100."
)


# ---------------------------------------------------------------------
# INVALID NORMALIZATION INPUT
# ---------------------------------------------------------------------

check(
    normalize_piecewise(None, vol_norm) is None,
    "Missing metric cannot be normalized."
)

check(
    normalize_piecewise("20", vol_norm) is None,
    "String metric cannot be normalized."
)

check(
    normalize_piecewise(True, vol_norm) is None,
    "Boolean metric cannot be normalized."
)


# ---------------------------------------------------------------------
# COMPONENT CALCULATION
# ---------------------------------------------------------------------

component_result = calculate_component(
    "realized_volatility",
    components["realized_volatility"],
    {
        "realized_volatility_20d_pct": 30.0
    },
)

check(
    component_result["available"] is True,
    "Observed Risk metric makes component available."
)

check(
    component_result["normalized_risk"] == 40.0,
    "Component stores policy-normalized Risk."
)

check(
    component_result["weight"] == 0.40,
    "Component weight comes from Risk Policy."
)

missing_component = calculate_component(
    "realized_volatility",
    components["realized_volatility"],
    {
        "realized_volatility_20d_pct": None
    },
)

check(
    missing_component["available"] is False,
    "Missing metric makes component unavailable."
)

check(
    missing_component["normalized_risk"] is None,
    "Missing metric does not become neutral Risk."
)

negative_component = calculate_component(
    "realized_volatility",
    components["realized_volatility"],
    {
        "realized_volatility_20d_pct": -1.0
    },
)

check(
    negative_component["available"] is False,
    "Negative Risk metric is rejected."
)


# ---------------------------------------------------------------------
# FULL MODEL / WEIGHTS 40-35-25
# ---------------------------------------------------------------------

full_metrics = {
    # exact normalized Risk = 40
    "realized_volatility_20d_pct": 30.0,

    # exact normalized Risk = 40
    "max_drawdown_60d_pct": 20.0,

    # exact normalized Risk = 40
    "downside_return_20d_pct": 10.0,
}

full_result = calculate_asset_risk(full_metrics, policy)

check(
    full_result["status"] == STATUS_CALCULATED,
    "Three available Risk metrics produce CALCULATED status."
)

check(
    full_result["coverage"] == 1.0,
    "Three of three Risk metrics produce coverage 1.0."
)

check(
    full_result["available_components"] == 3,
    "Full Risk model has three available components."
)

check(
    full_result["total_components"] == 3,
    "Risk model has three enabled components."
)

check(
    full_result["score"] == 40.0,
    "Equal normalized component Risk 40 produces aggregate Risk 40."
)

check(
    full_result["level"] == "HIGH",
    "Risk score 40 maps to HIGH."
)

check(
    close_enough(
        full_result["components"]["realized_volatility"]["effective_weight"],
        0.40,
    ),
    "Full model preserves volatility weight 0.40."
)

check(
    close_enough(
        full_result["components"]["max_drawdown"]["effective_weight"],
        0.35,
    ),
    "Full model preserves drawdown weight 0.35."
)

check(
    close_enough(
        full_result["components"]["downside_return"]["effective_weight"],
        0.25,
    ),
    "Full model preserves downside weight 0.25."
)

check(
    close_enough(
        full_result["components"]["realized_volatility"]["contribution"],
        16.0,
    ),
    "Volatility contribution is 40 x 0.40 = 16."
)

check(
    close_enough(
        full_result["components"]["max_drawdown"]["contribution"],
        14.0,
    ),
    "Drawdown contribution is 40 x 0.35 = 14."
)

check(
    close_enough(
        full_result["components"]["downside_return"]["contribution"],
        10.0,
    ),
    "Downside contribution is 40 x 0.25 = 10."
)


# ---------------------------------------------------------------------
# TWO OF THREE / WEIGHT RENORMALIZATION
# ---------------------------------------------------------------------

two_metric_result = calculate_asset_risk(
    {
        # normalized 40
        "realized_volatility_20d_pct": 30.0,

        # normalized 40
        "max_drawdown_60d_pct": 20.0,

        "downside_return_20d_pct": None,
    },
    policy,
)

check(
    two_metric_result["status"] == STATUS_CALCULATED,
    "Two of three Risk metrics satisfy minimum coverage."
)

check(
    close_enough(
        two_metric_result["coverage"],
        2.0 / 3.0,
        tolerance=1e-9,
    ),
    "Two available metrics produce two-thirds coverage."
)

check(
    two_metric_result["available_components"] == 2,
    "Two-metric model reports two available components."
)

expected_vol_weight = 0.40 / 0.75
expected_dd_weight = 0.35 / 0.75

check(
    close_enough(
        two_metric_result["components"]["realized_volatility"][
            "effective_weight"
        ],
        expected_vol_weight,
    ),
    "Volatility weight is renormalized over available weight."
)

check(
    close_enough(
        two_metric_result["components"]["max_drawdown"][
            "effective_weight"
        ],
        expected_dd_weight,
    ),
    "Drawdown weight is renormalized over available weight."
)

check(
    two_metric_result["score"] == 40.0,
    "Equal normalized Risk remains 40 after two-component renormalization."
)


# ---------------------------------------------------------------------
# ONE OF THREE / INSUFFICIENT COVERAGE
# ---------------------------------------------------------------------

one_metric_result = calculate_asset_risk(
    {
        "realized_volatility_20d_pct": 30.0,
        "max_drawdown_60d_pct": None,
        "downside_return_20d_pct": None,
    },
    policy,
)

check(
    one_metric_result["status"] == STATUS_UNAVAILABLE,
    "One of three Risk metrics is insufficient."
)

check(
    close_enough(
        one_metric_result["coverage"],
        1.0 / 3.0,
        tolerance=1e-9,
    ),
    "One available metric produces one-third coverage."
)

check(
    one_metric_result["score"] is None,
    "Insufficient Risk coverage has no score."
)

check(
    one_metric_result["level"] is None,
    "Insufficient Risk coverage has no level."
)

check(
    one_metric_result["drivers"] == [],
    "Insufficient Risk coverage has no public drivers."
)


# ---------------------------------------------------------------------
# ZERO IS OBSERVED DATA, NOT MISSING
# ---------------------------------------------------------------------

zero_result = calculate_asset_risk(
    {
        "realized_volatility_20d_pct": 0.0,
        "max_drawdown_60d_pct": 0.0,
        "downside_return_20d_pct": 0.0,
    },
    policy,
)

check(
    zero_result["status"] == STATUS_CALCULATED,
    "Observed zero Risk metrics remain analytically available."
)

check(
    zero_result["score"] == 0.0,
    "Observed zero Risk metrics produce Risk score 0."
)

check(
    zero_result["level"] == "LOW",
    "Risk score 0 maps to LOW."
)


# ---------------------------------------------------------------------
# MAXIMUM RISK
# ---------------------------------------------------------------------

maximum_result = calculate_asset_risk(
    {
        "realized_volatility_20d_pct": 200.0,
        "max_drawdown_60d_pct": 100.0,
        "downside_return_20d_pct": 100.0,
    },
    policy,
)

check(
    maximum_result["score"] == 100.0,
    "All components above final anchors produce Risk score 100."
)

check(
    maximum_result["level"] == "CRITICAL",
    "Risk score 100 maps to CRITICAL."
)


# ---------------------------------------------------------------------
# RISK LEVEL BOUNDARIES
# ---------------------------------------------------------------------

level_cases = (
    (0.0, "LOW"),
    (19.999999, "LOW"),
    (20.0, "MODERATE"),
    (39.999999, "MODERATE"),
    (40.0, "HIGH"),
    (59.999999, "HIGH"),
    (60.0, "VERY_HIGH"),
    (79.999999, "VERY_HIGH"),
    (80.0, "CRITICAL"),
    (100.0, "CRITICAL"),
)

for score, expected_level in level_cases:
    actual_level = resolve_risk_level(score, policy)

    check(
        actual_level == expected_level,
        f"Risk level boundary {score} = {expected_level}."
    )


# ---------------------------------------------------------------------
# DRIVERS
# ---------------------------------------------------------------------

check(
    len(full_result["drivers"]) == 3,
    "Full Risk result contains one driver per available component."
)

check(
    all(
        isinstance(driver, str)
        for driver in full_result["drivers"]
    ),
    "Risk drivers are strings compatible with Schema V3."
)

check(
    any(
        driver.startswith("realized_volatility:")
        for driver in full_result["drivers"]
    ),
    "Volatility appears in Risk drivers."
)

check(
    any(
        driver.startswith("max_drawdown:")
        for driver in full_result["drivers"]
    ),
    "Drawdown appears in Risk drivers."
)

check(
    any(
        driver.startswith("downside_return:")
        for driver in full_result["drivers"]
    ),
    "Downside return appears in Risk drivers."
)


# ---------------------------------------------------------------------
# ANALYTICAL RESULT VS PUBLIC asset.risk
# ---------------------------------------------------------------------

public_risk = build_public_risk(full_result)

check(
    set(public_risk.keys()) == {
        "score",
        "level",
        "drivers",
    },
    "Public Risk contains only Schema V3 fields."
)

check(
    "coverage" not in public_risk,
    "Coverage is not leaked into public asset.risk."
)

check(
    "components" not in public_risk,
    "Component analytics are not leaked into public asset.risk."
)

check(
    "status" not in public_risk,
    "Analytical status is not leaked into public asset.risk."
)

check(
    build_public_risk(one_metric_result) is None,
    "Unavailable analytical Risk cannot create public asset.risk."
)


# ---------------------------------------------------------------------
# WRITER
# ---------------------------------------------------------------------

asset = {
    "ticker": "TEST",
    "name": "Test Asset",
}

written_asset = write_risk_to_asset(
    deepcopy(asset),
    full_result,
)

check(
    "risk" in written_asset,
    "Risk writer creates asset.risk for calculated result."
)

check(
    set(written_asset["risk"].keys())
    == {
        "score",
        "level",
        "drivers",
    },
    "Risk writer preserves strict public Schema V3 shape."
)

check(
    written_asset["risk"]["score"] == 40.0,
    "Risk writer preserves calculated score."
)

check(
    written_asset["risk"]["level"] == "HIGH",
    "Risk writer preserves calculated level."
)

stale_asset = {
    "ticker": "TEST",
    "risk": {
        "score": 99.0,
        "level": "CRITICAL",
        "drivers": ["STALE"],
    },
}

cleaned_asset = write_risk_to_asset(
    deepcopy(stale_asset),
    one_metric_result,
)

check(
    "risk" not in cleaned_asset,
    "Unavailable Risk removes stale asset.risk."
)


# ---------------------------------------------------------------------
# POLICY IMMUTABILITY
# ---------------------------------------------------------------------

policy_before = deepcopy(policy)

calculate_asset_risk(full_metrics, policy)

check(
    policy == policy_before,
    "Risk Engine does not mutate Risk Policy."
)


# ---------------------------------------------------------------------
# INPUT IMMUTABILITY
# ---------------------------------------------------------------------

metrics_before = deepcopy(full_metrics)

calculate_asset_risk(full_metrics, policy)

check(
    full_metrics == metrics_before,
    "Risk Engine does not mutate Risk metrics input."
)


# ---------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------

print()
print("=" * 72)
print("B.2J.5A SUMMARY")
print(f"Checks: {passed + failed}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print("=" * 72)

if failed:
    print("RESULTADO: FAIL")
    raise SystemExit(1)

print("RESULTADO: PASS")