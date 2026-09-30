from copy import deepcopy
from pathlib import Path
import json
import sys


BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


from score_engine_v3 import (
    calculate_component,
    extract_risk_signal,
    extract_signal,
    resolve_confidence_multiplier,
)


TEST_VERSION = "3.4J.6B-B.2J.6B"

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

    try:
        return abs(float(actual) - float(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


def load_json(path):
    with Path(path).open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def make_data_point(
    value,
    confidence_score=1.0,
    confidence_status="VERIFIED",
):
    return {
        "value": value,
        "confidence": {
            "score": confidence_score,
            "status": confidence_status,
        },
    }


def make_asset_with_fundamental(
    value,
    confidence_score=1.0,
    confidence_status="VERIFIED",
):
    return {
        "ticker": "TEST",
        "data_points": {
            "fundamentals": make_data_point(
                value=value,
                confidence_score=confidence_score,
                confidence_status=confidence_status,
            ),
        },
    }


score_policy = load_json(
    SCORE_POLICY_PATH
)


print("=" * 72)
print("B.2J.6B SCORE ENGINE NUMERIC TYPE SAFETY")
print(f"Test: {TEST_VERSION}")
print("=" * 72)


# =====================================================================
# 1. DIRECT NUMERIC SIGNAL
#
# bool is a subclass of int in Python.
# Score Engine must reject bool explicitly rather than treating:
#
# True  -> 1
# False -> 0
# =====================================================================

for boolean_value in (
    True,
    False,
):
    signal, reason = extract_signal(
        {
            "value": boolean_value,
        },
        [
            "normalized_score",
        ],
    )

    check(
        signal is None,
        (
            f"Direct signal value={boolean_value!r} "
            "is rejected as non-numeric semantic input."
        ),
    )

    check(
        isinstance(reason, str)
        and len(reason) > 0,
        (
            f"Rejected direct boolean {boolean_value!r} "
            "returns diagnostic reason."
        ),
    )


# ---------------------------------------------------------------------
# Valid numeric zero must remain valid.
# ---------------------------------------------------------------------

for numeric_zero in (
    0,
    0.0,
):
    signal, reason = extract_signal(
        {
            "value": numeric_zero,
        },
        [
            "normalized_score",
        ],
    )

    check(
        signal == 0.0,
        (
            f"Numeric zero {numeric_zero!r} remains "
            "a valid normalized signal."
        ),
    )

    check(
        reason is None,
        (
            f"Valid numeric zero {numeric_zero!r} "
            "has no rejection reason."
        ),
    )


# ---------------------------------------------------------------------
# Other canonical numeric values must remain valid.
# ---------------------------------------------------------------------

for numeric_value in (
    1,
    1.0,
    50,
    50.0,
    100,
    100.0,
):
    signal, reason = extract_signal(
        {
            "value": numeric_value,
        },
        [
            "normalized_score",
        ],
    )

    check(
        close_enough(
            signal,
            numeric_value,
        ),
        (
            f"Numeric direct signal {numeric_value!r} "
            "remains valid."
        ),
    )

    check(
        reason is None,
        (
            f"Valid numeric direct signal {numeric_value!r} "
            "has no rejection reason."
        ),
    )


# =====================================================================
# 2. NESTED NORMALIZED SIGNAL
#
# data_point.value may be an object containing normalized_score.
# bool inside that object must also be rejected.
# =====================================================================

for boolean_value in (
    True,
    False,
):
    signal, reason = extract_signal(
        {
            "value": {
                "normalized_score": boolean_value,
            },
        },
        [
            "normalized_score",
        ],
    )

    check(
        signal is None,
        (
            f"Nested normalized_score={boolean_value!r} "
            "is rejected."
        ),
    )

    check(
        isinstance(reason, str)
        and len(reason) > 0,
        (
            f"Rejected nested boolean {boolean_value!r} "
            "returns diagnostic reason."
        ),
    )


# ---------------------------------------------------------------------
# Nested numeric zero remains valid.
# ---------------------------------------------------------------------

for numeric_zero in (
    0,
    0.0,
):
    signal, reason = extract_signal(
        {
            "value": {
                "normalized_score": numeric_zero,
            },
        },
        [
            "normalized_score",
        ],
    )

    check(
        signal == 0.0,
        (
            f"Nested numeric zero {numeric_zero!r} "
            "remains valid."
        ),
    )

    check(
        reason is None,
        (
            f"Nested numeric zero {numeric_zero!r} "
            "has no rejection reason."
        ),
    )


# ---------------------------------------------------------------------
# Nested canonical numeric values remain valid.
# ---------------------------------------------------------------------

for numeric_value in (
    1,
    1.0,
    50,
    50.0,
    100,
    100.0,
):
    signal, reason = extract_signal(
        {
            "value": {
                "normalized_score": numeric_value,
            },
        },
        [
            "normalized_score",
        ],
    )

    check(
        close_enough(
            signal,
            numeric_value,
        ),
        (
            f"Nested numeric normalized_score "
            f"{numeric_value!r} remains valid."
        ),
    )

    check(
        reason is None,
        (
            f"Nested numeric normalized_score "
            f"{numeric_value!r} has no rejection reason."
        ),
    )


# =====================================================================
# 3. DIRECT RISK SIGNAL
#
# source_path = risk.score means extract_risk_signal normally receives
# the scalar score directly.
# =====================================================================

for boolean_value in (
    True,
    False,
):
    signal, reason = extract_risk_signal(
        boolean_value
    )

    check(
        signal is None,
        (
            f"Direct risk.score={boolean_value!r} "
            "is rejected."
        ),
    )

    check(
        isinstance(reason, str)
        and len(reason) > 0,
        (
            f"Rejected direct Risk boolean {boolean_value!r} "
            "returns diagnostic reason."
        ),
    )


# ---------------------------------------------------------------------
# Risk zero is valid and means maximum favorable contribution.
# ---------------------------------------------------------------------

for numeric_zero in (
    0,
    0.0,
):
    signal, reason = extract_risk_signal(
        numeric_zero
    )

    check(
        signal == 100.0,
        (
            f"Numeric risk.score={numeric_zero!r} "
            "remains valid and inverts to signal 100."
        ),
    )

    check(
        isinstance(reason, str)
        and len(reason) > 0,
        (
            f"Valid Risk zero {numeric_zero!r} "
            "returns explanatory inversion reason."
        ),
    )


# ---------------------------------------------------------------------
# Canonical Risk numeric anchors.
# ---------------------------------------------------------------------

risk_numeric_cases = (
    (1, 99.0),
    (1.0, 99.0),
    (50, 50.0),
    (50.0, 50.0),
    (100, 0.0),
    (100.0, 0.0),
)

for risk_score, expected_signal in risk_numeric_cases:
    signal, reason = extract_risk_signal(
        risk_score
    )

    check(
        close_enough(
            signal,
            expected_signal,
        ),
        (
            f"Numeric risk.score={risk_score!r} "
            "preserves inverse_0_100 semantics."
        ),
    )

    check(
        isinstance(reason, str)
        and len(reason) > 0,
        (
            f"Valid Risk score {risk_score!r} "
            "returns explanatory inversion reason."
        ),
    )


# =====================================================================
# 4. DICT RISK FORMAT
#
# extract_risk_signal also explicitly supports:
#
# {"score": ...}
#
# That path must have identical boolean protection.
# =====================================================================

for boolean_value in (
    True,
    False,
):
    signal, reason = extract_risk_signal(
        {
            "score": boolean_value,
        }
    )

    check(
        signal is None,
        (
            f"Dictionary risk.score={boolean_value!r} "
            "is rejected."
        ),
    )

    check(
        isinstance(reason, str)
        and len(reason) > 0,
        (
            f"Rejected dictionary Risk boolean "
            f"{boolean_value!r} returns diagnostic reason."
        ),
    )


for numeric_value, expected_signal in (
    (0, 100.0),
    (0.0, 100.0),
    (1, 99.0),
    (1.0, 99.0),
    (50, 50.0),
    (50.0, 50.0),
    (100, 0.0),
    (100.0, 0.0),
):
    signal, reason = extract_risk_signal(
        {
            "score": numeric_value,
        }
    )

    check(
        close_enough(
            signal,
            expected_signal,
        ),
        (
            f"Dictionary numeric risk.score={numeric_value!r} "
            "remains valid."
        ),
    )

    check(
        isinstance(reason, str)
        and len(reason) > 0,
        (
            f"Dictionary Risk score {numeric_value!r} "
            "returns explanatory inversion reason."
        ),
    )


# =====================================================================
# 5. COMPONENT-LEVEL BOOLEAN PROTECTION
#
# This proves the production calculate_component path rather than only
# testing helper functions.
# =====================================================================

for boolean_value in (
    True,
    False,
):
    fundamental_asset = make_asset_with_fundamental(
        value=boolean_value,
        confidence_score=1.0,
    )

    component = calculate_component(
        fundamental_asset,
        "fundamental",
        score_policy,
    )

    check(
        component["available"] is False,
        (
            f"Fundamental value={boolean_value!r} "
            "is unavailable at calculate_component boundary."
        ),
    )

    check(
        close_enough(
            component["points"],
            0.0,
        ),
        (
            f"Fundamental boolean {boolean_value!r} "
            "cannot generate Radar points."
        ),
    )


for boolean_value in (
    True,
    False,
):
    fundamental_asset = make_asset_with_fundamental(
        value={
            "normalized_score": boolean_value,
        },
        confidence_score=1.0,
    )

    component = calculate_component(
        fundamental_asset,
        "fundamental",
        score_policy,
    )

    check(
        component["available"] is False,
        (
            f"Nested Fundamental normalized_score="
            f"{boolean_value!r} is unavailable."
        ),
    )

    check(
        close_enough(
            component["points"],
            0.0,
        ),
        (
            f"Nested Fundamental boolean {boolean_value!r} "
            "cannot generate Radar points."
        ),
    )


# ---------------------------------------------------------------------
# Valid zero signal must remain analytically available when confidence
# is valid. Zero signal means zero earned points, not missing data.
# ---------------------------------------------------------------------

zero_fundamental_asset = make_asset_with_fundamental(
    value=0.0,
    confidence_score=1.0,
)

zero_fundamental_component = calculate_component(
    zero_fundamental_asset,
    "fundamental",
    score_policy,
)

check(
    zero_fundamental_component["available"] is True,
    "Fundamental numeric signal 0 remains analytically available."
)

check(
    close_enough(
        zero_fundamental_component["signal"],
        0.0,
    ),
    "Fundamental numeric signal 0 is preserved."
)

check(
    close_enough(
        zero_fundamental_component["points"],
        0.0,
    ),
    "Available Fundamental signal 0 correctly earns zero points."
)


# =====================================================================
# 6. RISK COMPONENT PRODUCTION PATH
# =====================================================================

for boolean_value in (
    True,
    False,
):
    risk_asset = {
        "ticker": "TEST",
        "risk": {
            "score": boolean_value,
            "level": "LOW",
            "drivers": [],
        },
    }

    component = calculate_component(
        risk_asset,
        "risk",
        score_policy,
    )

    check(
        component["available"] is False,
        (
            f"Production Risk component rejects "
            f"risk.score={boolean_value!r}."
        ),
    )

    check(
        close_enough(
            component["points"],
            0.0,
        ),
        (
            f"Production Risk boolean {boolean_value!r} "
            "cannot generate Radar points."
        ),
    )


# =====================================================================
# 7. CONFIDENCE NUMERIC TYPE SAFETY
#
# This section is intentionally diagnostic.
#
# A boolean confidence.score must NOT become:
#
# True  -> 1.0
# False -> 0.0
#
# If this section fails, the test has found a separate Score Engine
# boundary defect. Do NOT change the test to make it pass.
# =====================================================================

for boolean_value in (
    True,
    False,
):
    data_point = {
        "value": 50.0,
        "confidence": {
            "score": boolean_value,
            "status": "UNAVAILABLE",
        },
    }

    multiplier = resolve_confidence_multiplier(
        data_point,
        score_policy,
    )

    check(
        close_enough(
            multiplier,
            0.0,
        ),
        (
            f"Boolean confidence.score={boolean_value!r} "
            "is rejected rather than converted numerically."
        ),
    )


# ---------------------------------------------------------------------
# Valid confidence numeric boundaries remain valid.
# ---------------------------------------------------------------------

for confidence_value in (
    0,
    0.0,
    0.5,
    1,
    1.0,
):
    data_point = {
        "value": 50.0,
        "confidence": {
            "score": confidence_value,
            "status": "UNAVAILABLE",
        },
    }

    multiplier = resolve_confidence_multiplier(
        data_point,
        score_policy,
    )

    check(
        close_enough(
            multiplier,
            confidence_value,
        ),
        (
            f"Numeric confidence.score={confidence_value!r} "
            "remains valid."
        ),
    )


# =====================================================================
# 8. COMPONENT CONFIDENCE BOOLEAN PROTECTION
#
# This proves whether the boolean confidence behavior propagates into
# actual Radar points.
# =====================================================================

for boolean_value in (
    True,
    False,
):
    asset = make_asset_with_fundamental(
        value=100.0,
        confidence_score=boolean_value,
        confidence_status="UNAVAILABLE",
    )

    component = calculate_component(
        asset,
        "fundamental",
        score_policy,
    )

    check(
        component["available"] is False,
        (
            f"Fundamental confidence.score={boolean_value!r} "
            "cannot make component available."
        ),
    )

    check(
        close_enough(
            component["points"],
            0.0,
        ),
        (
            f"Fundamental confidence boolean {boolean_value!r} "
            "cannot generate Radar points."
        ),
    )


# =====================================================================
# 9. IMMUTABILITY
# =====================================================================

immutability_asset = make_asset_with_fundamental(
    value={
        "normalized_score": 50.0,
    },
    confidence_score=1.0,
)

asset_before = deepcopy(
    immutability_asset
)

calculate_component(
    immutability_asset,
    "fundamental",
    score_policy,
)

check(
    immutability_asset == asset_before,
    "Numeric type-safety calculation does not mutate asset."
)


policy_before = deepcopy(
    score_policy
)

calculate_component(
    immutability_asset,
    "fundamental",
    score_policy,
)

check(
    score_policy == policy_before,
    "Numeric type-safety calculation does not mutate Score Policy."
)


# =====================================================================
# SUMMARY
# =====================================================================

print()
print("=" * 72)
print("B.2J.6B SUMMARY")
print(f"Checks: {passed + failed}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print("=" * 72)

if failed:
    print("RESULTADO: FAIL")
    raise SystemExit(1)

print("RESULTADO: PASS")