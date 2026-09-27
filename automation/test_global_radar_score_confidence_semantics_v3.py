import importlib.util
import json
import math
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SCORE_ENGINE_PATH = (
    BASE_DIR / "automation" / "score_engine_v3.py"
)

SCORE_POLICY_PATH = (
    BASE_DIR / "automation" / "score_policy_v3.json"
)

TEST_VERSION = "3.4D.2-B.2G.2"


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


def datapoint(signal, confidence, signal_key="normalized_score"):
    return {
        "value": {
            signal_key: signal,
        },
        "confidence": {
            "score": confidence,
            "status": "PARTIAL",
        },
    }


def build_asset(component, confidence):
    asset = {
        "ticker": "TEST",
        "data_points": {},
    }

    if component == "fundamental":
        asset["data_points"]["fundamentals"] = datapoint(
            100.0,
            confidence,
        )

    elif component == "technical":
        asset["data_points"]["technical"] = datapoint(
            100.0,
            confidence,
        )

    elif component == "momentum":
        asset["data_points"]["technical"] = datapoint(
            100.0,
            confidence,
            "momentum_score",
        )

    elif component == "institutional_flow":
        asset["data_points"]["institutional_flow"] = datapoint(
            100.0,
            confidence,
        )

    elif component == "catalysts":
        asset["data_points"]["catalysts"] = datapoint(
            100.0,
            confidence,
        )

    elif component == "macro":
        asset["data_points"]["macro"] = datapoint(
            100.0,
            confidence,
        )

    return asset


def main():
    engine = load_module(
        "score_engine_b2g2",
        SCORE_ENGINE_PATH,
    )

    policy = load_json(SCORE_POLICY_PATH)

    checks = []

    def check(name, condition, detail=None):
        passed = bool(condition)
        checks.append((name, passed))

        suffix = f" | {detail}" if detail else ""

        print(
            f"[{'PASS' if passed else 'FAIL'}] "
            f"{name}{suffix}"
        )

    data_components = {
        "fundamental": 20.0,
        "technical": 20.0,
        "momentum": 15.0,
        "institutional_flow": 15.0,
        "catalysts": 15.0,
        "macro": 10.0,
    }

    total_weight = sum(
        engine.get_component_policy(
            policy,
            component,
        )["max_points"]
        for component in engine.DEFAULT_COMPONENTS
    )

    check(
        "01 - Radar Score total weight is 100",
        close_enough(total_weight, 100.0),
        f"actual={total_weight}",
    )

    threshold = engine.get_minimum_usable_confidence(
        policy
    )

    check(
        "02 - Global minimum usable confidence is 0.60",
        close_enough(threshold, 0.60),
        f"actual={threshold}",
    )

    for component, max_points in data_components.items():
        below_asset = build_asset(
            component,
            0.59,
        )

        below = engine.calculate_component(
            below_asset,
            component,
            policy,
        )

        check(
            f"{component} - 0.59 is unavailable",
            below["available"] is False,
        )

        check(
            f"{component} - 0.59 awards zero points",
            close_enough(below["points"], 0.0),
            f"actual={below['points']}",
        )

        threshold_asset = build_asset(
            component,
            0.60,
        )

        usable = engine.calculate_component(
            threshold_asset,
            component,
            policy,
        )

        expected_points = max_points * 0.60

        check(
            f"{component} - 0.60 is available",
            usable["available"] is True,
        )

        check(
            f"{component} - 0.60 applies numeric confidence",
            close_enough(
                usable["points"],
                expected_points,
            ),
            (
                f"expected={expected_points}, "
                f"actual={usable['points']}"
            ),
        )

    technical_asset = {
        "ticker": "TEST",
        "data_points": {
            "technical": {
                "value": {
                    "normalized_score": 100.0,
                    "momentum_score": 100.0,
                },
                "confidence": {
                    "score": 0.60,
                    "status": "PARTIAL",
                },
            }
        },
    }

    technical = engine.calculate_component(
        technical_asset,
        "technical",
        policy,
    )

    momentum = engine.calculate_component(
        technical_asset,
        "momentum",
        policy,
    )

    check(
        "Technical and Momentum share technical confidence",
        close_enough(
            technical["confidence_multiplier"],
            0.60,
        )
        and close_enough(
            momentum["confidence_multiplier"],
            0.60,
        ),
    )

    risk_asset = {
        "ticker": "TEST",
        "data_points": {},
        "risk": {
            "score": 0.0,
        },
    }

    risk = engine.calculate_component(
        risk_asset,
        "risk",
        policy,
    )

    check(
        "Risk valid score is available",
        risk["available"] is True,
    )

    check(
        "Risk uses inverse 0-100 semantics",
        close_enough(risk["signal"], 100.0)
        and close_enough(risk["points"], 5.0),
    )

    check(
        "Risk does not use data-point confidence multiplier",
        close_enough(
            risk["confidence_multiplier"],
            1.0,
        ),
    )

    missing_risk = engine.calculate_component(
        {
            "ticker": "TEST",
            "data_points": {},
        },
        "risk",
        policy,
    )

    check(
        "Missing Risk is unavailable",
        missing_risk["available"] is False,
    )

    check(
        "Missing Risk awards zero points",
        close_enough(
            missing_risk["points"],
            0.0,
        ),
    )

    all_available_asset = {
        "ticker": "TEST",
        "data_points": {
            "fundamentals": datapoint(100.0, 1.0),
            "technical": {
                "value": {
                    "normalized_score": 100.0,
                    "momentum_score": 100.0,
                },
                "confidence": {
                    "score": 1.0,
                    "status": "VERIFIED",
                },
            },
            "institutional_flow": datapoint(100.0, 1.0),
            "catalysts": datapoint(100.0, 1.0),
            "macro": datapoint(100.0, 1.0),
        },
        "risk": {
            "score": 0.0,
        },
    }

    full_score = engine.calculate_asset_score(
        all_available_asset,
        policy,
    )

    check(
        "Full model available_score is 100",
        close_enough(
            full_score["available_score"],
            100.0,
        ),
        f"actual={full_score['available_score']}",
    )

    check(
        "Full favorable model raw_score is 100",
        close_enough(
            full_score["raw_score"],
            100.0,
        ),
        f"actual={full_score['raw_score']}",
    )

    check(
        "Full favorable model coverage is 1.0",
        close_enough(
            full_score["coverage"],
            1.0,
        ),
        f"actual={full_score['coverage']}",
    )

    passed = sum(
        1
        for _, result in checks
        if result
    )

    failed = len(checks) - passed

    print()
    print(
        "=== B.2G.2 GLOBAL RADAR SCORE "
        "CONFIDENCE SEMANTICS ==="
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
