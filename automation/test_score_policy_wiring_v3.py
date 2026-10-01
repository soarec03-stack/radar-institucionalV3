import copy
import sys

sys.path.insert(0, r".\automation")

from score_engine_v3 import (
    calculate_asset_score,
    resolve_confidence_multiplier,
)


passed = 0
failed = 0


def check(condition, description, actual=None):
    global passed, failed

    if condition:
        passed += 1
        print("PASS:", description)
    else:
        failed += 1
        print("FAIL:", description)
        if actual is not None:
            print("      actual =", actual)


print("=" * 72)
print("B.2G.5 — SCORE POLICY WIRING REGRESSION")
print("=" * 72)


# ----------------------------------------------------------------------
# 1. CONFIDENCE STATUS MULTIPLIER MUST COME FROM POLICY
# ----------------------------------------------------------------------

confidence_policy = {
    "confidence_adjustment": {
        "enabled": True,
        "minimum_usable_confidence": 0.60,
        "verified_multiplier": 0.91,
        "partial_multiplier": 0.73,
        "low_multiplier": 0.31,
        "unavailable_multiplier": 0.07,
    }
}

cases = [
    ("VERIFIED", 0.91),
    ("PARTIAL", 0.73),
    ("LOW", 0.31),
    ("UNAVAILABLE", 0.07),
]

for status, expected in cases:
    point = {
        "confidence": {
            "score": None,
            "status": status,
        }
    }

    actual = resolve_confidence_multiplier(point, confidence_policy)

    check(
        abs(actual - expected) < 1e-12,
        f"confidence status {status} obeys configured policy multiplier",
        actual,
    )


# ----------------------------------------------------------------------
# 2. VALID NUMERIC CONFIDENCE SCORE RETAINS PRECEDENCE
# ----------------------------------------------------------------------

point_numeric = {
    "confidence": {
        "score": 0.81,
        "status": "PARTIAL",
    }
}

actual_numeric = resolve_confidence_multiplier(
    point_numeric,
    confidence_policy,
)

check(
    abs(actual_numeric - 0.81) < 1e-12,
    "valid numeric confidence.score retains precedence over status multiplier",
    actual_numeric,
)


# ----------------------------------------------------------------------
# 3. COVERAGE THRESHOLDS MUST COME FROM POLICY
#
# Build a 65% available model:
# fundamental 20
# technical   20
# momentum    15
# macro       10
# ----------------
# available   65
#
# Policy is deliberately changed to:
# reliable    0.60
# publication 0.65
#
# Correct wiring => coverage 0.65 must become CALCULATED.
# Old hardcoded/default wiring (.70/.85) => INSUFFICIENT_DATA.
# ----------------------------------------------------------------------

coverage_policy = {
    "coverage": {
        "minimum_for_reliable_score": 0.60,
        "minimum_for_publication": 0.65,
    },
    "confidence_adjustment": {
        "enabled": True,
        "minimum_usable_confidence": 0.60,
        "verified_multiplier": 1.0,
        "partial_multiplier": 0.85,
        "low_multiplier": 0.50,
        "unavailable_multiplier": 0.0,
    },
    "components": {
        "fundamental": {
            "max_points": 20,
            "source": "data_points.fundamentals",
            "signal_keys": ["normalized_score"],
        },
        "technical": {
            "max_points": 20,
            "source": "data_points.technical",
            "signal_keys": ["normalized_score"],
        },
        "momentum": {
            "max_points": 15,
            "source": "data_points.technical",
            "signal_keys": ["momentum_score"],
        },
        "institutional_flow": {
            "max_points": 15,
            "source": "data_points.institutional_flow",
            "signal_keys": ["normalized_score"],
        },
        "catalysts": {
            "max_points": 15,
            "source": "data_points.catalysts",
            "signal_keys": ["normalized_score"],
        },
        "macro": {
            "max_points": 10,
            "source": "data_points.macro",
            "signal_keys": ["normalized_score"],
        },
        "risk": {
            "max_points": 5,
            "source": "risk.score",
            "mode": "inverse_0_100",
        },
    },
}


def point(value):
    return {
        "value": value,
        "confidence": {
            "score": 1.0,
            "status": "VERIFIED",
        },
    }


asset_65 = {
    "ticker": "TEST65",
    "data_points": {
        "fundamentals": point({
            "normalized_score": 80.0,
        }),
        "technical": point({
            "normalized_score": 70.0,
            "momentum_score": 60.0,
        }),
        "macro": point({
            "normalized_score": 50.0,
        }),
    },
}


result_65 = calculate_asset_score(
    copy.deepcopy(asset_65),
    coverage_policy,
)

check(
    abs(result_65["coverage"] - 0.65) < 1e-12,
    "constructed model has exactly 65 percent coverage",
    result_65["coverage"],
)

check(
    result_65["status"] == "CALCULATED",
    "65 percent coverage obeys configured publication threshold of 0.65",
    result_65["status"],
)

check(
    result_65["normalized_score"] is not None,
    "configured publication threshold allows normalized score",
    result_65["normalized_score"],
)

check(
    result_65["label"] is not None,
    "configured publication threshold allows score label",
    result_65["label"],
)


print()
print("=" * 72)
print("RESULT")
print("=" * 72)
print("PASS:", passed)
print("FAIL:", failed)

if failed:
    sys.exit(1)

sys.exit(0)
