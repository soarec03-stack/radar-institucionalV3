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

INTEGRATION_POLICY_PATH = (
    BASE_DIR
    / "automation"
    / "institutional_flow_score_integration_policy_v3.json"
)

TEST_VERSION = "3.4D.2-B.2F.2"


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


def build_asset(
    signal=100.0,
    confidence_score=1.0,
    confidence_status="PARTIAL",
):
    return {
        "ticker": "TEST",
        "data_points": {
            "institutional_flow": {
                "value": {
                    "normalized_score": signal,
                },
                "confidence": {
                    "score": confidence_score,
                    "status": confidence_status,
                },
            }
        },
    }


def calculate_component(
    score_engine,
    score_policy,
    signal,
    confidence,
):
    asset = build_asset(
        signal=signal,
        confidence_score=confidence,
    )

    return score_engine.calculate_component(
        asset,
        "institutional_flow",
        score_policy,
    )


def main():
    score_engine = load_module(
        "score_engine_b2f2",
        SCORE_ENGINE_PATH,
    )

    score_policy = load_json(SCORE_POLICY_PATH)
    integration_policy = load_json(
        INTEGRATION_POLICY_PATH
    )

    checks = []

    def check(name, condition, detail=None):
        passed = bool(condition)
        checks.append((name, passed))

        suffix = ""

        if detail:
            suffix = f" | {detail}"

        print(
            f"[{'PASS' if passed else 'FAIL'}] "
            f"{name}{suffix}"
        )

    component_contract = integration_policy["component"]
    confidence_contract = integration_policy[
        "confidence_contract"
    ]

    threshold = float(
        confidence_contract[
            "minimum_usable_confidence"
        ]
    )

    component_policy = score_engine.get_component_policy(
        score_policy,
        "institutional_flow",
    )

    check(
        "01 - Institutional Flow max_points is 15",
        close_enough(
            component_policy["max_points"],
            15.0,
        ),
        (
            f"actual="
            f"{component_policy['max_points']}"
        ),
    )

    check(
        "02 - Institutional Flow source path is canonical",
        component_policy["source_path"]
        == "data_points.institutional_flow",
        (
            f"actual="
            f"{component_policy['source_path']}"
        ),
    )

    check(
        "03 - normalized_score is accepted signal key",
        "normalized_score"
        in component_policy["signal_keys"],
    )

    check(
        "04 - Integration policy threshold is 0.60",
        close_enough(threshold, 0.60),
        f"actual={threshold}",
    )

    cases = [
        (0.00, False, 0.0),
        (0.40, False, 0.0),
        (0.59, False, 0.0),
        (0.60, True, 9.0),
        (0.85, True, 12.75),
        (1.00, True, 15.0),
    ]

    results = {}

    for confidence, expected_available, expected_points in cases:
        result = calculate_component(
            score_engine,
            score_policy,
            signal=100.0,
            confidence=confidence,
        )

        results[confidence] = result

        check(
            (
                f"05.{confidence:.2f} - "
                f"availability respects threshold"
            ),
            result["available"]
            is expected_available,
            (
                f"expected={expected_available}, "
                f"actual={result['available']}"
            ),
        )

        check(
            (
                f"06.{confidence:.2f} - "
                f"points respect threshold"
            ),
            close_enough(
                result["points"],
                expected_points,
            ),
            (
                f"expected={expected_points}, "
                f"actual={result['points']}"
            ),
        )

    below_result = results[0.59]
    threshold_result = results[0.60]

    check(
        "07 - 0.59 is unavailable",
        below_result["available"] is False,
        (
            f"actual="
            f"{below_result['available']}"
        ),
    )

    check(
        "08 - 0.59 awards zero points",
        close_enough(
            below_result["points"],
            0.0,
        ),
        f"actual={below_result['points']}",
    )

    check(
        "09 - 0.60 is available",
        threshold_result["available"] is True,
        (
            f"actual="
            f"{threshold_result['available']}"
        ),
    )

    check(
        "10 - 0.60 awards exactly 9 points at signal 100",
        close_enough(
            threshold_result["points"],
            9.0,
        ),
        f"actual={threshold_result['points']}",
    )

    real_fixture = calculate_component(
        score_engine,
        score_policy,
        signal=31.25,
        confidence=0.64,
    )

    check(
        "11 - Signal 31.25 with confidence 0.64 is available",
        real_fixture["available"] is True,
        (
            f"actual="
            f"{real_fixture['available']}"
        ),
    )

    check(
        "12 - Signal 31.25 with confidence 0.64 yields 3 points",
        close_enough(
            real_fixture["points"],
            3.0,
        ),
        f"actual={real_fixture['points']}",
    )

    missing_asset = {
        "ticker": "TEST",
        "data_points": {},
    }

    missing_result = score_engine.calculate_component(
        missing_asset,
        "institutional_flow",
        score_policy,
    )

    check(
        "13 - Missing Institutional Flow is unavailable",
        missing_result["available"] is False,
        (
            f"actual="
            f"{missing_result['available']}"
        ),
    )

    check(
        "14 - Missing Institutional Flow awards zero points",
        close_enough(
            missing_result["points"],
            0.0,
        ),
        f"actual={missing_result['points']}",
    )

    check(
        "15 - Missing Institutional Flow has no signal",
        missing_result["signal"] is None,
        f"actual={missing_result['signal']}",
    )

    no_signal_asset = build_asset(
        signal=100.0,
        confidence_score=0.85,
    )

    no_signal_asset[
        "data_points"
    ][
        "institutional_flow"
    ][
        "value"
    ].pop("normalized_score")

    no_signal_result = score_engine.calculate_component(
        no_signal_asset,
        "institutional_flow",
        score_policy,
    )

    check(
        "16 - Missing normalized_score is unavailable",
        no_signal_result["available"] is False,
        (
            f"actual="
            f"{no_signal_result['available']}"
        ),
    )

    no_confidence_asset = build_asset(
        signal=100.0,
        confidence_score=0.85,
    )

    no_confidence_asset[
        "data_points"
    ][
        "institutional_flow"
    ].pop("confidence")

    no_confidence_result = (
        score_engine.calculate_component(
            no_confidence_asset,
            "institutional_flow",
            score_policy,
        )
    )

    check(
        "17 - Missing confidence is unavailable",
        no_confidence_result["available"] is False,
        (
            f"actual="
            f"{no_confidence_result['available']}"
        ),
    )

    maximum_result = calculate_component(
        score_engine,
        score_policy,
        signal=100.0,
        confidence=1.0,
    )

    check(
        "18 - Institutional Flow maximum is 15 points",
        close_enough(
            maximum_result["points"],
            component_contract["max_points"],
        ),
        f"actual={maximum_result['points']}",
    )

    asset_score_fixture = {
        "ticker": "TEST",
        "data_points": {
            "institutional_flow": {
                "value": {
                    "normalized_score": 100.0,
                },
                "confidence": {
                    "score": 0.59,
                    "status": "LOW",
                },
            }
        },
    }

    asset_score_result = (
        score_engine.calculate_asset_score(
            asset_score_fixture,
            score_policy,
        )
    )

    institutional_component = (
        asset_score_result[
            "components"
        ][
            "institutional_flow"
        ]
    )

    check(
        "19 - Below-threshold component stays unavailable in asset score",
        institutional_component["available"] is False,
        (
            f"actual="
            f"{institutional_component['available']}"
        ),
    )

    check(
        "20 - Below-threshold Institutional Flow adds zero available_score",
        close_enough(
            asset_score_result["available_score"],
            0.0,
        ),
        (
            f"actual="
            f"{asset_score_result['available_score']}"
        ),
    )

    check(
        "21 - Below-threshold Institutional Flow adds zero raw score",
        close_enough(
            asset_score_result["raw_score"],
            0.0,
        ),
        (
            f"actual="
            f"{asset_score_result['raw_score']}"
        ),
    )

    usable_asset_fixture = {
        "ticker": "TEST",
        "data_points": {
            "institutional_flow": {
                "value": {
                    "normalized_score": 100.0,
                },
                "confidence": {
                    "score": 0.60,
                    "status": "PARTIAL",
                },
            }
        },
    }

    usable_asset_result = (
        score_engine.calculate_asset_score(
            usable_asset_fixture,
            score_policy,
        )
    )

    usable_component = (
        usable_asset_result[
            "components"
        ][
            "institutional_flow"
        ]
    )

    check(
        "22 - Threshold Institutional Flow is available in asset score",
        usable_component["available"] is True,
        (
            f"actual="
            f"{usable_component['available']}"
        ),
    )

    check(
        "23 - Usable Institutional Flow adds full 15 to available_score",
        close_enough(
            usable_asset_result["available_score"],
            15.0,
        ),
        (
            f"actual="
            f"{usable_asset_result['available_score']}"
        ),
    )

    check(
        "24 - Confidence reduces points but not usable component weight",
        close_enough(
            usable_asset_result["raw_score"],
            9.0,
        )
        and close_enough(
            usable_asset_result["available_score"],
            15.0,
        ),
        (
            f"raw="
            f"{usable_asset_result['raw_score']}, "
            f"available="
            f"{usable_asset_result['available_score']}"
        ),
    )

    passed = sum(
        1
        for _, result in checks
        if result
    )

    failed = len(checks) - passed

    print()
    print(
        "=== B.2F.2 INSTITUTIONAL FLOW "
        "SCORE THRESHOLD REGRESSION ==="
    )
    print(f"Version: {TEST_VERSION}")
    print(f"Checks: {len(checks)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed:
        print()
        print(
            "RESULTADO: FAIL — comportamento atual "
            "diverge do contrato B.2F.1."
        )
        print(
            "Isto é esperado antes da correção mínima "
            "do Score Engine quando confidence < 0.60."
        )
        return 1

    print()
    print("RESULTADO: PASS")

    return 0


if __name__ == "__main__":
    sys.exit(main())