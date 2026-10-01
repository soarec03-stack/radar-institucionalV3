"""
Radar Institucional V3
B.2K.9 — Permanent End-to-End Regression

Offline deterministic regression:

Fixture Radar
    -> Metrics Loader
    -> Confidence Engine
    -> Signal Engine
    -> Risk Engine
    -> Radar Score
    -> Coverage / Publication Gate

No collectors.
No network.
No API keys.
"""

import copy
import json
import math
import sys
from pathlib import Path


AUTOMATION_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AUTOMATION_DIR.parent
FIXTURE_DIR = AUTOMATION_DIR / "fixtures" / "b2k_e2e"

sys.path.insert(0, str(AUTOMATION_DIR))


from metrics_loader_v3 import merge_metrics
from confidence_engine_v3 import apply_confidence_engine
from signal_engine_v3 import apply_signal_engine
from risk_history_adapter_v3 import prepare_risk_history
from risk_metrics_calculator_v3 import calculate_risk_metrics
from risk_engine_v3 import calculate_asset_risk, write_risk_to_asset
from score_engine_v3 import calculate_asset_score, write_score_to_asset


RADAR_FIXTURE = FIXTURE_DIR / "radar_base.json"
METRICS_FIXTURE = FIXTURE_DIR / "metrics.json"
RISK_FIXTURE = FIXTURE_DIR / "risk_history.json"

SOURCE_REGISTRY = AUTOMATION_DIR / "source_registry_v3.json"
DATA_QUALITY_POLICY = AUTOMATION_DIR / "data_quality_policy_v3.json"
SIGNAL_POLICY = AUTOMATION_DIR / "signal_policy_v3.json"
SCORE_POLICY = AUTOMATION_DIR / "score_policy_v3.json"


failures = 0
passes = 0


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def check(name, condition, actual=None, expected=None):
    global failures, passes

    if condition:
        passes += 1
        print(f"PASS | {name}")
        return

    failures += 1

    print(f"FAIL | {name}")

    if actual is not None or expected is not None:
        print(f"       actual  = {actual!r}")
        print(f"       expected= {expected!r}")


def equal_number(actual, expected, tolerance=1e-9):
    if actual is None or expected is None:
        return actual is expected

    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual is expected

    try:
        return math.isclose(
            float(actual),
            float(expected),
            rel_tol=0.0,
            abs_tol=tolerance,
        )
    except (TypeError, ValueError):
        return False


print("=" * 78)
print("B.2K.9 — PERMANENT END-TO-END REGRESSION")
print("=" * 78)


# ----------------------------------------------------------------------
# 1. Required offline inputs
# ----------------------------------------------------------------------

print()
print("1. FIXTURE / POLICY PREFLIGHT")
print("-" * 78)

required_files = (
    RADAR_FIXTURE,
    METRICS_FIXTURE,
    RISK_FIXTURE,
    SOURCE_REGISTRY,
    DATA_QUALITY_POLICY,
    SIGNAL_POLICY,
    SCORE_POLICY,
)

for path in required_files:
    check(
        f"required file exists: {path.relative_to(PROJECT_DIR)}",
        path.exists(),
    )

if failures:
    print()
    print("STOP - required files missing")
    print("PASS:", passes)
    print("FAIL:", failures)
    sys.exit(1)


radar = load_json(RADAR_FIXTURE)
metrics_input = load_json(METRICS_FIXTURE)
risk_history = load_json(RISK_FIXTURE)

registry = load_json(SOURCE_REGISTRY)
quality_policy = load_json(DATA_QUALITY_POLICY)
signal_policy = load_json(SIGNAL_POLICY)
score_policy = load_json(SCORE_POLICY)


# Work only on an in-memory copy.
radar = copy.deepcopy(radar)


# ----------------------------------------------------------------------
# 2. Metrics Loader
# ----------------------------------------------------------------------

print()
print("2. METRICS LOADER")
print("-" * 78)

merged_result = merge_metrics(
    radar,
    metrics_input,
)

check(
    "merge_metrics returns 3-item contract",
    isinstance(merged_result, tuple)
    and len(merged_result) == 3,
)

if not (
    isinstance(merged_result, tuple)
    and len(merged_result) == 3
):
    print("STOP - unexpected merge_metrics contract")
    sys.exit(1)

radar, loader_changes, loader_warnings = merged_result

assets = {
    asset.get("ticker"): asset
    for asset in radar.get("assets", [])
    if isinstance(asset, dict)
}

check(
    "asset universe is exactly VRT/CRSP/ETON",
    set(assets) == {"VRT", "CRSP", "ETON"},
    actual=sorted(assets),
    expected=["CRSP", "ETON", "VRT"],
)

expected_loaded_metrics = {
    "VRT": {
        "fundamentals": 4,
        "technical": 8,
        "macro": 3,
    },
    "CRSP": {
        "fundamentals": 2,
        "technical": 8,
        "macro": 3,
    },
    "ETON": {
        "fundamentals": 2,
        "technical": 8,
        "macro": 3,
    },
}

for ticker, domains in expected_loaded_metrics.items():
    asset = assets[ticker]
    data_points = asset.get("data_points", {})

    for domain, expected_count in domains.items():
        point = data_points.get(domain, {})
        value = point.get("value")

        metrics_obj = (
            value
            if isinstance(value, dict)
            else {}
        )

        usable_count = sum(
            1
            for metric_value in metrics_obj.values()
            if metric_value is not None
        )

        check(
            f"{ticker} {domain} usable metrics = {expected_count}",
            usable_count == expected_count,
            actual=usable_count,
            expected=expected_count,
        )


# ----------------------------------------------------------------------
# 3. Confidence Engine
# ----------------------------------------------------------------------

print()
print("3. CONFIDENCE ENGINE")
print("-" * 78)

freshness_hours = quality_policy.get(
    "freshness_hours",
    quality_policy.get("freshness", {}),
)

confidence_result = apply_confidence_engine(
    radar,
    registry,
    freshness_hours,
)

check(
    "apply_confidence_engine returns 2-item contract",
    isinstance(confidence_result, tuple)
    and len(confidence_result) == 2,
)

if not (
    isinstance(confidence_result, tuple)
    and len(confidence_result) == 2
):
    print("STOP - unexpected confidence engine contract")
    sys.exit(1)

radar, confidence_changes = confidence_result

assets = {
    asset.get("ticker"): asset
    for asset in radar.get("assets", [])
}

expected_confidence = {
    "VRT": {
        "fundamentals": 0.8225,
        "technical": 0.6300,
        "macro": 0.8177,
    },
    "CRSP": {
        "fundamentals": 0.8225,
        "technical": 0.6300,
        "macro": 0.8177,
    },
    "ETON": {
        "fundamentals": 0.8225,
        "technical": 0.6300,
        "macro": 0.8177,
    },
}

for ticker, domains in expected_confidence.items():
    dp = assets[ticker].get("data_points", {})

    for domain, expected_value in domains.items():
        actual = (
            dp.get(domain, {})
            .get("confidence", {})
            .get("score")
        )

        check(
            f"{ticker} {domain} confidence",
            equal_number(actual, expected_value, 1e-4),
            actual=actual,
            expected=expected_value,
        )


# ----------------------------------------------------------------------
# 4. Signal Engine
# ----------------------------------------------------------------------

print()
print("4. SIGNAL ENGINE")
print("-" * 78)

signal_result = apply_signal_engine(
    radar,
    signal_policy,
)

check(
    "apply_signal_engine returns 2-item contract",
    isinstance(signal_result, tuple)
    and len(signal_result) == 2,
)

if not (
    isinstance(signal_result, tuple)
    and len(signal_result) == 2
):
    print("STOP - unexpected signal engine contract")
    sys.exit(1)

radar, signal_changes = signal_result

assets = {
    asset.get("ticker"): asset
    for asset in radar.get("assets", [])
}


def normalized_signal(asset, domain):
    value = (
        asset.get("data_points", {})
        .get(domain, {})
        .get("value")
    )

    if not isinstance(value, dict):
        return None

    return value.get("normalized_score")


def momentum_signal(asset):
    value = (
        asset.get("data_points", {})
        .get("technical", {})
        .get("value")
    )

    if not isinstance(value, dict):
        return None

    return value.get("momentum_score")


expected_signals = {
    "VRT": {
        "fundamentals": 84.7254,
        "technical": 30.9617,
        "momentum": 19.5398,
        "macro": 29.7384,
    },
    "CRSP": {
        "fundamentals": None,
        "technical": 52.6477,
        "momentum": 36.1422,
        "macro": 29.7384,
    },
    "ETON": {
        "fundamentals": None,
        "technical": 49.0005,
        "momentum": 35.2404,
        "macro": 29.7384,
    },
}

for ticker, expected in expected_signals.items():
    asset = assets[ticker]

    actual_values = {
        "fundamentals": normalized_signal(
            asset,
            "fundamentals",
        ),
        "technical": normalized_signal(
            asset,
            "technical",
        ),
        "momentum": momentum_signal(asset),
        "macro": normalized_signal(
            asset,
            "macro",
        ),
    }

    for domain, expected_value in expected.items():
        actual = actual_values[domain]

        check(
            f"{ticker} {domain} signal",
            equal_number(actual, expected_value, 1e-4),
            actual=actual,
            expected=expected_value,
        )


# ----------------------------------------------------------------------
# 5. Risk Pipeline
# ----------------------------------------------------------------------

print()
print("5. RISK PIPELINE")
print("-" * 78)

history_by_ticker = {
    item.get("ticker"): item
    for item in risk_history.get("assets", [])
    if isinstance(item, dict)
}

expected_risk = {
    "VRT": {
        "realized_volatility_20d_pct": 64.394346,
        "max_drawdown_60d_pct": 31.143497,
        "downside_return_20d_pct": 4.094277,
        "score": 57.39,
        "level": "HIGH",
    },
    "CRSP": {
        "realized_volatility_20d_pct": 50.109331,
        "max_drawdown_60d_pct": 17.394390,
        "downside_return_20d_pct": 2.073079,
        "score": 40.29,
        "level": "HIGH",
    },
    "ETON": {
        "realized_volatility_20d_pct": 63.472441,
        "max_drawdown_60d_pct": 20.083810,
        "downside_return_20d_pct": 15.837151,
        "score": 60.87,
        "level": "VERY_HIGH",
    },
}

for ticker, expected in expected_risk.items():
    source = history_by_ticker.get(ticker)

    check(
        f"{ticker} risk history available",
        isinstance(source, dict),
    )

    if not isinstance(source, dict):
        continue

    records = source.get("records", [])

    check(
        f"{ticker} risk fixture has 60 sessions",
        len(records) == 60,
        actual=len(records),
        expected=60,
    )

    prepared = prepare_risk_history(records)
    metrics = calculate_risk_metrics(
        prepared["closes"]
    )

    for metric_name in (
        "realized_volatility_20d_pct",
        "max_drawdown_60d_pct",
        "downside_return_20d_pct",
    ):
        actual = metrics.get(metric_name)
        expected_value = expected[metric_name]

        check(
            f"{ticker} {metric_name}",
            equal_number(
                actual,
                expected_value,
                1e-6,
            ),
            actual=actual,
            expected=expected_value,
        )

    analytical = calculate_asset_risk(metrics)

    check(
        f"{ticker} risk score",
        equal_number(
            analytical.get("score"),
            expected["score"],
            1e-2,
        ),
        actual=analytical.get("score"),
        expected=expected["score"],
    )

    check(
        f"{ticker} risk level",
        analytical.get("level")
        == expected["level"],
        actual=analytical.get("level"),
        expected=expected["level"],
    )

    write_risk_to_asset(
        assets[ticker],
        analytical,
    )


# ----------------------------------------------------------------------
# 6. Radar Score
# ----------------------------------------------------------------------

print()
print("6. RADAR SCORE")
print("-" * 78)

expected_scores = {
    "VRT": {
        "components": {
            "fundamental": 13.94,
            "technical": 3.90,
            "momentum": 1.85,
            "institutional_flow": 0.00,
            "catalysts": 0.00,
            "macro": 2.43,
            "risk": 2.13,
        },
        "raw_score": 24.25,
        "available_score": 70.0,
        "normalized_score": 34.64,
        "coverage": 0.70,
        "status": "PARTIAL",
        "analytically_usable": True,
        "publishable": False,
        "label": None,
    },
    "CRSP": {
        "components": {
            "fundamental": 0.00,
            "technical": 6.63,
            "momentum": 3.42,
            "institutional_flow": 0.00,
            "catalysts": 0.00,
            "macro": 2.43,
            "risk": 2.99,
        },
        "raw_score": 15.47,
        "available_score": 50.0,
        "normalized_score": None,
        "coverage": 0.50,
        "status": "INSUFFICIENT_DATA",
        "analytically_usable": False,
        "publishable": False,
        "label": None,
    },
    "ETON": {
        "components": {
            "fundamental": 0.00,
            "technical": 6.17,
            "momentum": 3.33,
            "institutional_flow": 0.00,
            "catalysts": 0.00,
            "macro": 2.43,
            "risk": 1.96,
        },
        "raw_score": 13.89,
        "available_score": 50.0,
        "normalized_score": None,
        "coverage": 0.50,
        "status": "INSUFFICIENT_DATA",
        "analytically_usable": False,
        "publishable": False,
        "label": None,
    },
}

for ticker, expected in expected_scores.items():
    asset = assets[ticker]

    result = calculate_asset_score(
        asset,
        score_policy,
    )

    write_score_to_asset(
        asset,
        result,
    )

    score = asset.get("score", {})

    for component, expected_value in (
        expected["components"].items()
    ):
        actual = score.get(component)

        check(
            f"{ticker} score component {component}",
            equal_number(
                actual,
                expected_value,
                1e-2,
            ),
            actual=actual,
            expected=expected_value,
        )

    scalar_fields = (
        "raw_score",
        "available_score",
        "normalized_score",
        "coverage",
    )

    for field in scalar_fields:
        actual = score.get(field)
        expected_value = expected[field]

        check(
            f"{ticker} {field}",
            equal_number(
                actual,
                expected_value,
                1e-2,
            ),
            actual=actual,
            expected=expected_value,
        )

    for field in (
        "status",
        "analytically_usable",
        "publishable",
        "label",
    ):
        actual = score.get(field)
        expected_value = expected[field]

        check(
            f"{ticker} {field}",
            actual == expected_value,
            actual=actual,
            expected=expected_value,
        )

    check(
        f"{ticker} transient radar_score absent",
        "radar_score" not in asset,
    )


# ----------------------------------------------------------------------
# 7. Publication Gate invariants
# ----------------------------------------------------------------------

print()
print("7. PUBLICATION GATE")
print("-" * 78)

check(
    "VRT remains non-publishable at 70% coverage",
    assets["VRT"]["score"].get("publishable")
    is False,
)

check(
    "VRT operational label remains blocked",
    assets["VRT"]["score"].get("label")
    is None,
)

for ticker in ("CRSP", "ETON"):
    check(
        f"{ticker} remains analytically unusable",
        assets[ticker]["score"].get(
            "analytically_usable"
        )
        is False,
    )

    check(
        f"{ticker} normalized score remains blocked",
        assets[ticker]["score"].get(
            "normalized_score"
        )
        is None,
    )

    check(
        f"{ticker} operational label remains blocked",
        assets[ticker]["score"].get(
            "label"
        )
        is None,
    )


# ----------------------------------------------------------------------
# Final
# ----------------------------------------------------------------------

print()
print("=" * 78)
print("B.2K.9 PERMANENT E2E RESULT")
print("=" * 78)
print("PASS:", passes)
print("FAIL:", failures)

if failures == 0:
    print(
        "RESULT: APPROVED — offline end-to-end "
        "contract preserved."
    )
else:
    print(
        "RESULT: FAILED — end-to-end regression "
        "detected."
    )

sys.exit(0 if failures == 0 else 1)
