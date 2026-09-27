import importlib.util
import json
import math
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ENGINE_PATH = BASE_DIR / "automation" / "score_engine_v3.py"
POLICY_PATH = BASE_DIR / "automation" / "score_policy_v3.json"

TEST_VERSION = "3.4D.2-B.2G.3"


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
    normalized_score=None,
    confidence=1.0,
    momentum_score=None,
):
    value = {}

    if normalized_score is not None:
        value["normalized_score"] = normalized_score

    if momentum_score is not None:
        value["momentum_score"] = momentum_score

    return {
        "value": value,
        "confidence": {
            "score": confidence,
            "status": "PARTIAL",
        },
    }


def build_asset(
    fundamental=None,
    technical=None,
    momentum=None,
    institutional=None,
    catalysts=None,
    macro=None,
    risk=None,
    confidence=1.0,
):
    asset = {
        "ticker": "TEST",
        "data_points": {},
    }

    if fundamental is not None:
        asset["data_points"]["fundamentals"] = datapoint(
            normalized_score=fundamental,
            confidence=confidence,
        )

    if technical is not None or momentum is not None:
        asset["data_points"]["technical"] = datapoint(
            normalized_score=technical,
            momentum_score=momentum,
            confidence=confidence,
        )

    if institutional is not None:
        asset["data_points"]["institutional_flow"] = datapoint(
            normalized_score=institutional,
            confidence=confidence,
        )

    if catalysts is not None:
        asset["data_points"]["catalysts"] = datapoint(
            normalized_score=catalysts,
            confidence=confidence,
        )

    if macro is not None:
        asset["data_points"]["macro"] = datapoint(
            normalized_score=macro,
            confidence=confidence,
        )

    if risk is not None:
        asset["risk"] = {
            "score": risk,
        }

    return asset


def main():
    engine = load_module(
        "score_engine_b2g3",
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

    coverage_policy = policy.get("coverage", {})

    check(
        "01 - Policy reliable threshold is 0.70",
        close_enough(
            coverage_policy.get(
                "minimum_for_reliable_score"
            ),
            0.70,
        ),
    )

    check(
        "02 - Policy publication threshold is 0.85",
        close_enough(
            coverage_policy.get(
                "minimum_for_publication"
            ),
            0.85,
        ),
    )

    # 65% available:
    # Fundamental 20
    # Technical 20
    # Momentum 15
    # Macro 10
    asset_65 = build_asset(
        fundamental=100,
        technical=100,
        momentum=100,
        macro=100,
    )

    result_65 = engine.calculate_asset_score(
        asset_65,
        policy,
    )

    check(
        "03 - 65 percent model has available_score 65",
        close_enough(
            result_65["available_score"],
            65.0,
        ),
        f"actual={result_65['available_score']}",
    )

    check(
        "04 - 65 percent model has coverage 0.65",
        close_enough(
            result_65["coverage"],
            0.65,
        ),
        f"actual={result_65['coverage']}",
    )

    check(
        "05 - Coverage below 0.70 is INSUFFICIENT_DATA",
        result_65["status"] == "INSUFFICIENT_DATA",
        f"actual={result_65['status']}",
    )

    check(
        "06 - Insufficient model has no normalized_score",
        result_65["normalized_score"] is None,
        f"actual={result_65['normalized_score']}",
    )

    check(
        "07 - Insufficient model has no label",
        result_65["label"] is None,
        f"actual={result_65['label']}",
    )

    # Exactly 70%:
    # Fundamental 20
    # Technical 20
    # Momentum 15
    # Macro 10
    # Risk 5
    asset_70 = build_asset(
        fundamental=100,
        technical=100,
        momentum=100,
        macro=100,
        risk=0,
    )

    result_70 = engine.calculate_asset_score(
        asset_70,
        policy,
    )

    check(
        "08 - Threshold model has available_score 70",
        close_enough(
            result_70["available_score"],
            70.0,
        ),
        f"actual={result_70['available_score']}",
    )

    check(
        "09 - Threshold model has coverage 0.70",
        close_enough(
            result_70["coverage"],
            0.70,
        ),
        f"actual={result_70['coverage']}",
    )

    check(
        "10 - Coverage 0.70 is PARTIAL",
        result_70["status"] == "PARTIAL",
        f"actual={result_70['status']}",
    )

    check(
        "11 - Partial model has normalized_score",
        result_70["normalized_score"] is not None,
        f"actual={result_70['normalized_score']}",
    )

    check(
        "12 - Partial model has no operational label",
        result_70["label"] is None,
        f"actual={result_70['label']}",
    )

    # Exactly 85%:
    # Fundamental 20
    # Technical 20
    # Momentum 15
    # Institutional 15
    # Catalysts 15
    asset_85 = build_asset(
        fundamental=100,
        technical=100,
        momentum=100,
        institutional=100,
        catalysts=100,
    )

    result_85 = engine.calculate_asset_score(
        asset_85,
        policy,
    )

    check(
        "13 - Publication model has available_score 85",
        close_enough(
            result_85["available_score"],
            85.0,
        ),
        f"actual={result_85['available_score']}",
    )

    check(
        "14 - Publication model has coverage 0.85",
        close_enough(
            result_85["coverage"],
            0.85,
        ),
        f"actual={result_85['coverage']}",
    )

    check(
        "15 - Coverage 0.85 is CALCULATED",
        result_85["status"] == "CALCULATED",
        f"actual={result_85['status']}",
    )

    check(
        "16 - Publishable model receives label",
        result_85["label"] is not None,
        f"actual={result_85['label']}",
    )

    # Confidence 0.60:
    # all seven components remain available.
    asset_conf_60 = build_asset(
        fundamental=100,
        technical=100,
        momentum=100,
        institutional=100,
        catalysts=100,
        macro=100,
        risk=0,
        confidence=0.60,
    )

    result_conf_60 = engine.calculate_asset_score(
        asset_conf_60,
        policy,
    )

    check(
        "17 - Usable confidence preserves available_score 100",
        close_enough(
            result_conf_60["available_score"],
            100.0,
        ),
        f"actual={result_conf_60['available_score']}",
    )

    check(
        "18 - Usable confidence preserves coverage 1.0",
        close_enough(
            result_conf_60["coverage"],
            1.0,
        ),
        f"actual={result_conf_60['coverage']}",
    )

    # Six confidence-adjusted data-point components:
    # 95 max points * 0.60 = 57
    # Risk = 5
    # raw_score = 62
    check(
        "19 - Confidence reduces points, not available weight",
        close_enough(
            result_conf_60["raw_score"],
            62.0,
        ),
        f"actual={result_conf_60['raw_score']}",
    )

    check(
        "20 - Normalized score reflects confidence-adjusted points",
        close_enough(
            result_conf_60["normalized_score"],
            62.0,
        ),
        f"actual={result_conf_60['normalized_score']}",
    )

    # Confidence 0.59:
    # all six data-point components become unavailable.
    # Risk remains the only available component.
    asset_conf_59 = build_asset(
        fundamental=100,
        technical=100,
        momentum=100,
        institutional=100,
        catalysts=100,
        macro=100,
        risk=0,
        confidence=0.59,
    )

    result_conf_59 = engine.calculate_asset_score(
        asset_conf_59,
        policy,
    )

    check(
        "21 - Below-threshold data points leave only Risk available",
        close_enough(
            result_conf_59["available_score"],
            5.0,
        ),
        f"actual={result_conf_59['available_score']}",
    )

    check(
        "22 - Below-threshold model coverage becomes 0.05",
        close_enough(
            result_conf_59["coverage"],
            0.05,
        ),
        f"actual={result_conf_59['coverage']}",
    )

    check(
        "23 - Below-threshold aggregate is INSUFFICIENT_DATA",
        result_conf_59["status"] == "INSUFFICIENT_DATA",
        f"actual={result_conf_59['status']}",
    )

    check(
        "24 - Below-threshold aggregate has no normalized score",
        result_conf_59["normalized_score"] is None,
        f"actual={result_conf_59['normalized_score']}",
    )

    passed = sum(
        1
        for _, result in checks
        if result
    )

    failed = len(checks) - passed

    print()
    print(
        "=== B.2G.3 RADAR SCORE "
        "COVERAGE AND NORMALIZATION ==="
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
