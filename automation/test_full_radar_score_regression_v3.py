import importlib.util
import json
import math
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ENGINE_PATH = BASE_DIR / "automation" / "score_engine_v3.py"
POLICY_PATH = BASE_DIR / "automation" / "score_policy_v3.json"

TEST_VERSION = "3.4D.2-B.2G.4"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Não foi possível carregar módulo: {path}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def close_enough(left, right, tolerance=1e-9):
    return math.isclose(
        float(left),
        float(right),
        rel_tol=tolerance,
        abs_tol=tolerance,
    )


def datapoint(
    normalized_score=100.0,
    confidence=1.0,
    momentum_score=None,
):
    value = {
        "normalized_score": normalized_score,
    }

    if momentum_score is not None:
        value["momentum_score"] = momentum_score

    return {
        "value": value,
        "confidence": {
            "score": confidence,
            "status": "VERIFIED",
        },
    }


def full_asset(signal=100.0, confidence=1.0, risk_score=0.0):
    return {
        "ticker": "TEST",
        "data_points": {
            "fundamentals": datapoint(
                signal,
                confidence,
            ),
            "technical": datapoint(
                signal,
                confidence,
                momentum_score=signal,
            ),
            "institutional_flow": datapoint(
                signal,
                confidence,
            ),
            "catalysts": datapoint(
                signal,
                confidence,
            ),
            "macro": datapoint(
                signal,
                confidence,
            ),
        },
        "risk": {
            "score": risk_score,
        },
    }


def main():
    engine = load_module(
        "score_engine_b2g4",
        ENGINE_PATH,
    )

    policy = load_json(POLICY_PATH)

    checks = []

    def check(name, condition, detail=None):
        passed = bool(condition)
        checks.append((name, passed))

        suffix = f" | {detail}" if detail else ""

        print(
            f"[{'PASS' if passed else 'FAIL'}] "
            f"{name}{suffix}"
        )

    # --------------------------------------------------
    # 1. Component weights
    # --------------------------------------------------

    expected_weights = {
        "fundamental": 20.0,
        "technical": 20.0,
        "momentum": 15.0,
        "institutional_flow": 15.0,
        "catalysts": 15.0,
        "macro": 10.0,
        "risk": 5.0,
    }

    for component, expected in expected_weights.items():
        actual = engine.get_component_policy(
            policy,
            component,
        )["max_points"]

        check(
            f"Weight {component} = {expected}",
            close_enough(actual, expected),
            f"actual={actual}",
        )

    # --------------------------------------------------
    # 2. Risk inverse semantics
    # --------------------------------------------------

    risk_cases = [
        (0.0, 5.0),
        (25.0, 3.75),
        (50.0, 2.5),
        (75.0, 1.25),
        (100.0, 0.0),
    ]

    for risk_score, expected_points in risk_cases:
        asset = {
            "ticker": "TEST",
            "data_points": {},
            "risk": {
                "score": risk_score,
            },
        }

        result = engine.calculate_component(
            asset,
            "risk",
            policy,
        )

        check(
            f"Risk {risk_score} inverse points",
            result["available"] is True
            and close_enough(
                result["points"],
                expected_points,
            ),
            (
                f"expected={expected_points}, "
                f"actual={result['points']}"
            ),
        )

    for invalid_risk in (-1.0, 101.0):
        asset = {
            "ticker": "TEST",
            "data_points": {},
            "risk": {
                "score": invalid_risk,
            },
        }

        result = engine.calculate_component(
            asset,
            "risk",
            policy,
        )

        check(
            f"Risk {invalid_risk} is unavailable",
            result["available"] is False
            and close_enough(
                result["points"],
                0.0,
            ),
        )

    # --------------------------------------------------
    # 3. Full model extremes
    # --------------------------------------------------

    best = engine.calculate_asset_score(
        full_asset(
            signal=100.0,
            confidence=1.0,
            risk_score=0.0,
        ),
        policy,
    )

    check(
        "Best full model raw_score = 100",
        close_enough(best["raw_score"], 100.0),
        f"actual={best['raw_score']}",
    )

    check(
        "Best full model normalized_score = 100",
        close_enough(
            best["normalized_score"],
            100.0,
        ),
        f"actual={best['normalized_score']}",
    )

    check(
        "Best full model label = STRONG_BUY",
        best["label"] == "STRONG_BUY",
        f"actual={best['label']}",
    )

    worst = engine.calculate_asset_score(
        full_asset(
            signal=0.0,
            confidence=1.0,
            risk_score=100.0,
        ),
        policy,
    )

    check(
        "Worst full model raw_score = 0",
        close_enough(worst["raw_score"], 0.0),
        f"actual={worst['raw_score']}",
    )

    check(
        "Worst full model normalized_score = 0",
        close_enough(
            worst["normalized_score"],
            0.0,
        ),
        f"actual={worst['normalized_score']}",
    )

    check(
        "Worst full model label = AVOID",
        worst["label"] == "AVOID",
        f"actual={worst['label']}",
    )

    # --------------------------------------------------
    # 4. Label boundaries
    # --------------------------------------------------

    label_cases = [
        (0.0, "AVOID"),
        (34.9999, "AVOID"),
        (35.0, "CAUTION"),
        (49.9999, "CAUTION"),
        (50.0, "HOLD"),
        (64.9999, "HOLD"),
        (65.0, "WATCH_ACCUMULATE"),
        (74.9999, "WATCH_ACCUMULATE"),
        (75.0, "BUY"),
        (84.9999, "BUY"),
        (85.0, "STRONG_BUY"),
        (100.0, "STRONG_BUY"),
    ]

    for value, expected_label in label_cases:
        actual_label = engine.score_label(value)

        check(
            f"Label boundary {value} = {expected_label}",
            actual_label == expected_label,
            f"actual={actual_label}",
        )

    # --------------------------------------------------
    # 5. Confidence boundary across full model
    # --------------------------------------------------

    at_threshold = engine.calculate_asset_score(
        full_asset(
            signal=100.0,
            confidence=0.60,
            risk_score=0.0,
        ),
        policy,
    )

    check(
        "Full model confidence 0.60 coverage = 1.0",
        close_enough(
            at_threshold["coverage"],
            1.0,
        ),
        f"actual={at_threshold['coverage']}",
    )

    check(
        "Full model confidence 0.60 raw_score = 62",
        close_enough(
            at_threshold["raw_score"],
            62.0,
        ),
        f"actual={at_threshold['raw_score']}",
    )

    check(
        "Full model confidence 0.60 normalized_score = 62",
        close_enough(
            at_threshold["normalized_score"],
            62.0,
        ),
        f"actual={at_threshold['normalized_score']}",
    )

    check(
        "Full model confidence 0.60 label = HOLD",
        at_threshold["label"] == "HOLD",
        f"actual={at_threshold['label']}",
    )

    below_threshold = engine.calculate_asset_score(
        full_asset(
            signal=100.0,
            confidence=0.59,
            risk_score=0.0,
        ),
        policy,
    )

    check(
        "Full model confidence 0.59 available_score = 5",
        close_enough(
            below_threshold["available_score"],
            5.0,
        ),
        f"actual={below_threshold['available_score']}",
    )

    check(
        "Full model confidence 0.59 coverage = 0.05",
        close_enough(
            below_threshold["coverage"],
            0.05,
        ),
        f"actual={below_threshold['coverage']}",
    )

    check(
        "Full model confidence 0.59 is INSUFFICIENT_DATA",
        below_threshold["status"] == "INSUFFICIENT_DATA",
        f"actual={below_threshold['status']}",
    )

    check(
        "Insufficient model cannot receive label",
        below_threshold["label"] is None,
        f"actual={below_threshold['label']}",
    )

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    passed = sum(
        1
        for _, result in checks
        if result
    )

    failed = len(checks) - passed

    print()
    print(
        "=== B.2G.4 FULL RADAR SCORE "
        "0-100 REGRESSION ==="
    )
    print(f"Version: {TEST_VERSION}")
    print(f"Checks: {len(checks)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()
    print(
        "RESULTADO: "
        + ("PASS" if failed == 0 else "FAIL")
    )

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
