from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


from risk_history_adapter_v3 import (
    ADAPTER_VERSION,
    prepare_risk_history,
)

from risk_metrics_calculator_v3 import (
    CALCULATOR_VERSION,
    calculate_risk_metrics,
)

from risk_engine_v3 import (
    ENGINE_VERSION,
    STATUS_CALCULATED,
    calculate_asset_risk,
    load_policy as load_risk_policy,
    write_risk_to_asset,
)

from score_engine_v3 import (
    calculate_component,
    calculate_asset_score,
)


TEST_VERSION = "3.4J.6A-B.2J.6A"

EXPECTED_ADAPTER_VERSION = "3.4J.5C-B.2J.5C"
EXPECTED_CALCULATOR_VERSION = "3.4J.4B-B.2J.4B"
EXPECTED_RISK_ENGINE_VERSION = "3.4J.5A-B.2J.5A"

SCORE_POLICY_PATH = BASE_DIR / "score_policy_v3.json"

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

    return abs(float(actual) - float(expected)) <= tolerance


def load_json(path):
    import json

    with Path(path).open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def build_asset_with_risk(risk_score):
    """
    Minimal asset shape required to test the Risk component in isolation.

    level/drivers are included because this mirrors the stable public
    asset.risk contract, although Radar Score must consume risk.score only.
    """
    return {
        "ticker": "TEST",
        "risk": {
            "score": risk_score,
            "level": "LOW",
            "drivers": [
                "TEST_DRIVER"
            ],
        },
    }


def build_history(
    count,
    start_date=date(2026, 1, 1),
):
    """
    Deterministic synthetic history.

    The pattern intentionally produces non-zero market Risk while
    remaining independent from external data/network availability.
    """
    records = []
    price = 100.0

    for index in range(count):
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

        current_date = (
            start_date
            + timedelta(days=index)
        )

        records.append(
            {
                "market_date": current_date.isoformat(),
                "Close": price,
            }
        )

    return records


print("=" * 72)
print("B.2J.6A RISK -> RADAR SCORE INTEGRATION")
print(f"Test:       {TEST_VERSION}")
print(f"Adapter:    {EXPECTED_ADAPTER_VERSION}")
print(f"Calculator: {EXPECTED_CALCULATOR_VERSION}")
print(f"RiskEngine: {EXPECTED_RISK_ENGINE_VERSION}")
print("=" * 72)


risk_policy = load_risk_policy()
score_policy = load_json(
    SCORE_POLICY_PATH
)


# ---------------------------------------------------------------------
# VERSION BOUNDARY
# ---------------------------------------------------------------------

check(
    ADAPTER_VERSION == EXPECTED_ADAPTER_VERSION,
    "Integration consumes homologated B.2J.5C History Adapter."
)

check(
    CALCULATOR_VERSION == EXPECTED_CALCULATOR_VERSION,
    "Integration consumes homologated B.2J.4B Risk Calculator."
)

check(
    ENGINE_VERSION == EXPECTED_RISK_ENGINE_VERSION,
    "Integration consumes homologated B.2J.5A Risk Engine."
)


# ---------------------------------------------------------------------
# SCORE POLICY CONTRACT
# ---------------------------------------------------------------------

score_components = score_policy.get(
    "components",
    {}
)

risk_component_policy = score_components.get(
    "risk"
)

check(
    isinstance(
        risk_component_policy,
        dict,
    ),
    "Score Policy declares Risk component."
)

check(
    risk_component_policy.get(
        "max_points"
    ) == 5,
    "Radar Score Risk component has maximum 5 points."
)

risk_source = risk_component_policy.get(
    "source_path",
    risk_component_policy.get("source"),
)

check(
    risk_source == "risk.score",
    "Radar Score Risk component consumes risk.score."
)

check(
    risk_component_policy.get(
        "mode"
    ) == "inverse_0_100",
    "Radar Score Risk component uses inverse_0_100 mode."
)


# ---------------------------------------------------------------------
# DIRECT RISK COMPONENT ANCHORS
#
# Risk 0   -> Radar 5.00
# Risk 25  -> Radar 3.75
# Risk 50  -> Radar 2.50
# Risk 75  -> Radar 1.25
# Risk 100 -> Radar 0.00
# ---------------------------------------------------------------------

anchor_cases = (
    (0.0, 5.00),
    (25.0, 3.75),
    (50.0, 2.50),
    (75.0, 1.25),
    (100.0, 0.00),
)

for risk_score, expected_points in anchor_cases:
    asset = build_asset_with_risk(
        risk_score
    )

    component = calculate_component(
        asset,
        "risk",
        score_policy,
    )

    check(
        component["available"] is True,
        (
            f"Risk {risk_score:.0f} is available "
            "to Radar Score."
        ),
    )

    check(
        close_enough(
            component["max_points"],
            5.0,
        ),
        (
            f"Risk {risk_score:.0f} preserves "
            "maximum 5 Radar points."
        ),
    )

    check(
        close_enough(
            component["signal"],
            100.0 - risk_score,
        ),
        (
            f"Risk {risk_score:.0f} is inverted "
            "to canonical Radar signal."
        ),
    )

    check(
        close_enough(
            component["points"],
            expected_points,
        ),
        (
            f"Risk {risk_score:.0f} produces "
            f"{expected_points:.2f} Radar points."
        ),
    )


# ---------------------------------------------------------------------
# ZERO IS VALID DATA, NOT MISSING
# ---------------------------------------------------------------------

zero_component = calculate_component(
    build_asset_with_risk(0.0),
    "risk",
    score_policy,
)

check(
    zero_component["available"] is True,
    "Risk score 0 remains available rather than being treated as missing."
)

check(
    close_enough(
        zero_component["points"],
        5.0,
    ),
    "Minimum measured Risk earns full 5 Radar points."
)


# ---------------------------------------------------------------------
# MISSING risk.score
# ---------------------------------------------------------------------

missing_score_asset = {
    "ticker": "TEST",
    "risk": {
        "level": "HIGH",
        "drivers": [
            "OBSERVED_DRIVER"
        ],
    },
}

missing_component = calculate_component(
    missing_score_asset,
    "risk",
    score_policy,
)

check(
    missing_component["available"] is False,
    "Missing risk.score makes Radar Risk component unavailable."
)

check(
    close_enough(
        missing_component["points"],
        0.0,
    ),
    "Missing risk.score earns zero Radar points."
)


# ---------------------------------------------------------------------
# MISSING risk OBJECT
# ---------------------------------------------------------------------

missing_risk_asset = {
    "ticker": "TEST",
}

missing_risk_component = calculate_component(
    missing_risk_asset,
    "risk",
    score_policy,
)

check(
    missing_risk_component["available"] is False,
    "Missing asset.risk makes Radar Risk component unavailable."
)

check(
    close_enough(
        missing_risk_component["points"],
        0.0,
    ),
    "Missing asset.risk earns zero Radar points."
)


# ---------------------------------------------------------------------
# INVALID RISK VALUES
# ---------------------------------------------------------------------

invalid_cases = (
    None,
    "50",
    True,
    -1.0,
    101.0,
)

for invalid_value in invalid_cases:
    asset = build_asset_with_risk(
        invalid_value
    )

    component = calculate_component(
        asset,
        "risk",
        score_policy,
    )

    check(
        component["available"] is False,
        (
            f"Invalid risk.score {invalid_value!r} "
            "is unavailable to Radar Score."
        ),
    )


# ---------------------------------------------------------------------
# Radar Score aggregate coverage semantics
#
# We intentionally create an asset where only Risk is available.
# The complete Radar Score must therefore remain analytically
# insufficient, but Risk must still be counted as available_score = 5.
# ---------------------------------------------------------------------

risk_only_asset = {
    "ticker": "TEST_RISK_ONLY",
    "data_points": {},
    "risk": {
        "score": 50.0,
        "level": "HIGH",
        "drivers": [
            "TEST_DRIVER"
        ],
    },
}

risk_only_score = calculate_asset_score(
    risk_only_asset,
    score_policy,
)

check(
    close_enough(
        risk_only_score["available_score"],
        5.0,
    ),
    "Risk-only asset contributes 5 points to available_score denominator."
)

check(
    close_enough(
        risk_only_score["raw_score"],
        2.5,
    ),
    "Risk-only asset earns 2.5 raw Radar points at Risk 50."
)

check(
    close_enough(
        risk_only_score["coverage"],
        0.05,
    ),
    "Risk-only asset produces Radar Score coverage 5 percent."
)

check(
    risk_only_score["normalized_score"] is None,
    "Risk-only asset remains below minimum reliable Radar coverage."
)


# ---------------------------------------------------------------------
# Missing Risk must reduce Radar coverage rather than becoming
# neutral Risk.
# ---------------------------------------------------------------------

no_risk_asset = {
    "ticker": "TEST_NO_RISK",
    "data_points": {},
}

no_risk_score = calculate_asset_score(
    no_risk_asset,
    score_policy,
)

check(
    close_enough(
        no_risk_score["available_score"],
        0.0,
    ),
    "Missing Risk contributes nothing to available_score."
)

check(
    close_enough(
        no_risk_score["raw_score"],
        0.0,
    ),
    "Missing Risk does not fabricate Radar points."
)

check(
    close_enough(
        no_risk_score["coverage"],
        0.0,
    ),
    "Missing Risk does not fabricate Radar Score coverage."
)


# ---------------------------------------------------------------------
# level / drivers MUST NOT alter Radar Risk points
# ---------------------------------------------------------------------

base_asset = {
    "ticker": "TEST_METADATA_A",
    "risk": {
        "score": 50.0,
        "level": "LOW",
        "drivers": [
            "DRIVER_A"
        ],
    },
}

different_metadata_asset = {
    "ticker": "TEST_METADATA_B",
    "risk": {
        "score": 50.0,
        "level": "CRITICAL",
        "drivers": [
            "DRIVER_X",
            "DRIVER_Y",
            "DRIVER_Z",
        ],
    },
}

base_component = calculate_component(
    base_asset,
    "risk",
    score_policy,
)

metadata_component = calculate_component(
    different_metadata_asset,
    "risk",
    score_policy,
)

check(
    close_enough(
        base_component["points"],
        metadata_component["points"],
    ),
    "Risk level and drivers do not alter Radar Risk contribution."
)

check(
    close_enough(
        base_component["points"],
        2.5,
    ),
    "Radar Score consumes risk.score rather than Risk metadata."
)


# =====================================================================
# END-TO-END:
#
# market_date + Close
#       ↓
# History Adapter
#       ↓
# Risk Calculator
#       ↓
# Risk Engine
#       ↓
# asset.risk
#       ↓
# Radar Score Risk component
# =====================================================================

history = build_history(
    60
)

# Reverse deliberately. The Adapter must restore chronology.
history_reversed = list(
    reversed(history)
)

prepared_history = prepare_risk_history(
    history_reversed
)

check(
    prepared_history[
        "valid_close_observations"
    ] == 60,
    "End-to-end history contains 60 validated Close observations."
)

check(
    prepared_history["records"][0]["market_date"]
    < prepared_history["records"][-1]["market_date"],
    "End-to-end History Adapter restores chronological ordering."
)

risk_metrics = calculate_risk_metrics(
    prepared_history["closes"]
)

check(
    all(
        risk_metrics[key] is not None
        for key in (
            "realized_volatility_20d_pct",
            "max_drawdown_60d_pct",
            "downside_return_20d_pct",
        )
    ),
    "End-to-end Calculator produces all three Risk metrics."
)

analytical_risk = calculate_asset_risk(
    risk_metrics,
    risk_policy,
)

check(
    analytical_risk["status"]
    == STATUS_CALCULATED,
    "End-to-end Risk Engine produces CALCULATED Risk."
)

check(
    analytical_risk["coverage"] == 1.0,
    "End-to-end Risk Engine has full metric coverage."
)

asset_before_writer = {
    "ticker": "TEST_END_TO_END",
    "data_points": {},
}

asset_with_risk = write_risk_to_asset(
    deepcopy(asset_before_writer),
    analytical_risk,
)

check(
    "risk" in asset_with_risk,
    "End-to-end Risk writer creates asset.risk."
)

check(
    set(asset_with_risk["risk"].keys())
    == {
        "score",
        "level",
        "drivers",
    },
    "End-to-end writer preserves public asset.risk contract."
)

public_risk_score = asset_with_risk[
    "risk"
]["score"]

check(
    0.0 <= public_risk_score <= 100.0,
    "End-to-end public Risk score remains within 0-100."
)

radar_risk_component = calculate_component(
    asset_with_risk,
    "risk",
    score_policy,
)

expected_radar_signal = (
    100.0 - public_risk_score
)

expected_radar_points = (
    expected_radar_signal
    / 100.0
    * 5.0
)

check(
    radar_risk_component["available"] is True,
    "End-to-end asset.risk is available to Radar Score."
)

check(
    close_enough(
        radar_risk_component["signal"],
        expected_radar_signal,
    ),
    "End-to-end Radar Score correctly inverts Risk 0-100."
)

check(
    close_enough(
        radar_risk_component["points"],
        expected_radar_points,
        tolerance=1e-4,
    ),
    "End-to-end Radar Risk points match independent inverse formula."
)


# ---------------------------------------------------------------------
# FULL SCORE ENGINE MUST SEE THE SAME RISK CONTRIBUTION
# ---------------------------------------------------------------------

full_score_result = calculate_asset_score(
    asset_with_risk,
    score_policy,
)

check(
    close_enough(
        full_score_result["available_score"],
        5.0,
    ),
    "Full Score Engine recognizes Risk as the only available component."
)

check(
    close_enough(
        full_score_result["raw_score"],
        radar_risk_component["points"],
        tolerance=1e-2,
    ),
    "Full Score Engine preserves calculated Risk contribution."
)

check(
    close_enough(
        full_score_result["coverage"],
        0.05,
    ),
    "End-to-end Risk-only Radar coverage is exactly 5 percent."
)

check(
    full_score_result["normalized_score"] is None,
    "Risk-only end-to-end asset cannot fabricate full Radar Score."
)


# ---------------------------------------------------------------------
# IMMUTABILITY
# ---------------------------------------------------------------------

asset_before = deepcopy(
    asset_with_risk
)

calculate_component(
    asset_with_risk,
    "risk",
    score_policy,
)

check(
    asset_with_risk == asset_before,
    "Radar Risk component calculation does not mutate asset."
)

policy_before = deepcopy(
    score_policy
)

calculate_asset_score(
    asset_with_risk,
    score_policy,
)

check(
    score_policy == policy_before,
    "Radar Score calculation does not mutate Score Policy."
)


# ---------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------

print()
print("=" * 72)
print("B.2J.6A SUMMARY")
print(f"Checks: {passed + failed}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print("=" * 72)

if failed:
    print("RESULTADO: FAIL")
    raise SystemExit(1)

print("RESULTADO: PASS")