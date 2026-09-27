import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

POLICY_PATH = (
    BASE_DIR
    / "automation"
    / "institutional_flow_score_integration_policy_v3.json"
)

EXPECTED_VERSION = "3.4D.2-B.2F.1"


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    policy = load_json(POLICY_PATH)

    checks = []

    def check(name, condition):
        passed = bool(condition)
        checks.append((name, passed))
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")

    principles = policy.get("principles", {})
    authorities = policy.get("authorities", {})
    component = policy.get("component", {})
    confidence = policy.get("confidence_contract", {})
    score = policy.get("score_contract", {})
    missing = policy.get("missing_component_contract", {})
    coverage = policy.get("coverage_contract", {})
    forbidden = policy.get("forbidden_behaviors", [])
    cases = policy.get("boundary_cases", {})
    regression = policy.get("regression_requirements", {})

    check(
        "POLICY_VERSION",
        policy.get("policy_version") == EXPECTED_VERSION,
    )

    check(
        "FAIL_CLOSED_PRINCIPLES",
        principles.get("policy_before_code") is True
        and principles.get("fail_closed") is True
        and principles.get("missing_is_not_neutral") is True
        and principles.get("missing_is_not_zero_signal") is True
        and principles.get("do_not_invent_metrics") is True
        and principles.get("do_not_invent_confidence") is True
        and principles.get("do_not_invent_signal") is True,
    )

    check(
        "UPSTREAM_AUTHORITIES",
        authorities.get("institutional_eligibility")
        == "institutional_flow_composer_v3"
        and authorities.get("signal_boundary")
        == "institutional_flow_signal_integration_adapter_v3"
        and authorities.get("data_point_construction")
        == "metrics_loader_v3"
        and authorities.get("confidence")
        == "confidence_engine_v3"
        and authorities.get("normalized_signal")
        == "signal_engine_v3"
        and authorities.get("radar_score")
        == "score_engine_v3",
    )

    check(
        "INSTITUTIONAL_FLOW_COMPONENT",
        component.get("name") == "institutional_flow"
        and component.get("source_path")
        == "data_points.institutional_flow"
        and component.get("signal_key") == "normalized_score"
        and float(component.get("max_points", -1)) == 15.0,
    )

    check(
        "MINIMUM_USABLE_CONFIDENCE",
        float(confidence.get("minimum_usable_confidence", -1))
        == 0.60
        and confidence.get("minimum_inclusive") is True,
    )

    below = confidence.get("below_minimum_behavior", {})

    check(
        "BELOW_THRESHOLD_FAILS_CLOSED",
        below.get("available") is False
        and float(below.get("points", -1)) == 0.0
        and below.get(
            "include_max_points_in_available_score"
        ) is False,
    )

    usable = confidence.get(
        "at_or_above_minimum_behavior",
        {},
    )

    check(
        "AT_THRESHOLD_IS_USABLE",
        usable.get("available") is True
        and usable.get(
            "include_max_points_in_available_score"
        ) is True
        and usable.get(
            "apply_numeric_confidence_multiplier"
        ) is True,
    )

    zero = confidence.get(
        "zero_or_unavailable_behavior",
        {},
    )

    check(
        "ZERO_OR_UNAVAILABLE_FAILS_CLOSED",
        zero.get("available") is False
        and float(zero.get("points", -1)) == 0.0
        and zero.get(
            "include_max_points_in_available_score"
        ) is False,
    )

    check(
        "SCORE_FORMULA",
        score.get("formula")
        == (
            "(normalized_score / 100.0) * "
            "max_points * confidence_score"
        )
        and score.get("confidence_adjustment_required") is True,
    )

    check(
        "SIGNAL_RANGE",
        float(score.get("signal_min", -1)) == 0.0
        and float(score.get("signal_max", -1)) == 100.0,
    )

    check(
        "POINTS_RANGE",
        float(score.get("points_min", -1)) == 0.0
        and float(score.get("points_max", -1)) == 15.0,
    )

    absent_point = missing.get("data_point_absent", {})

    check(
        "MISSING_DATA_POINT_NOT_AVAILABLE",
        absent_point.get("available") is False
        and float(absent_point.get("points", -1)) == 0.0
        and absent_point.get("signal") is None
        and absent_point.get(
            "include_max_points_in_available_score"
        ) is False,
    )

    absent_signal = missing.get(
        "normalized_score_absent",
        {},
    )

    check(
        "MISSING_SIGNAL_NOT_AVAILABLE",
        absent_signal.get("available") is False
        and float(absent_signal.get("points", -1)) == 0.0
        and absent_signal.get(
            "include_max_points_in_available_score"
        ) is False,
    )

    absent_confidence = missing.get(
        "confidence_absent",
        {},
    )

    check(
        "MISSING_CONFIDENCE_NOT_AVAILABLE",
        absent_confidence.get("available") is False
        and float(absent_confidence.get("points", -1)) == 0.0
        and absent_confidence.get(
            "include_max_points_in_available_score"
        ) is False,
    )

    check(
        "COVERAGE_WEIGHT",
        float(
            coverage.get(
                "total_radar_score_weight",
                -1,
            )
        )
        == 100.0
        and float(
            coverage.get(
                "institutional_flow_weight",
                -1,
            )
        )
        == 15.0,
    )

    check(
        "AVAILABLE_SCORE_SEMANTICS",
        coverage.get(
            "available_component_adds_full_max_points"
        )
        is True
        and coverage.get(
            "unavailable_component_adds_zero_to_available_score"
        )
        is True
        and coverage.get(
            "confidence_reduces_points_not_component_weight_when_usable"
        )
        is True,
    )

    required_forbidden = [
        "Treat confidence below 0.60 as analytically available.",
        "Award Institutional Flow points when confidence is below 0.60.",
        (
            "Add 15 Institutional Flow points to available_score "
            "when confidence is below 0.60."
        ),
        "Treat missing Institutional Flow as a neutral signal.",
        (
            "Treat missing Institutional Flow as "
            "normalized_score zero."
        ),
        (
            "Invent normalized_score when Signal Engine "
            "did not produce one."
        ),
        (
            "Recalculate Institutional Flow metrics "
            "inside Score Engine."
        ),
        (
            "Recalculate Institutional Flow confidence "
            "inside Score Engine."
        ),
        (
            "Recover blocked or suppressed upstream "
            "Institutional Flow facts."
        ),
        "Exceed 15 points for Institutional Flow.",
    ]

    check(
        "FORBIDDEN_BEHAVIORS",
        all(item in forbidden for item in required_forbidden),
    )

    expected_cases = {
        "confidence_0_00": (False, 0.0),
        "confidence_0_40": (False, 0.0),
        "confidence_0_59": (False, 0.0),
        "confidence_0_60": (True, 9.0),
        "confidence_0_85": (True, 12.75),
        "confidence_1_00": (True, 15.0),
    }

    boundary_ok = True

    for key, (available, points) in expected_cases.items():
        case = cases.get(key, {})

        if (
            case.get("expected_available") is not available
            or float(
                case.get(
                    "expected_points_for_signal_100",
                    -1,
                )
            )
            != points
        ):
            boundary_ok = False

    check(
        "BOUNDARY_CASES",
        boundary_ok,
    )

    check(
        "REGRESSION_REQUIREMENTS",
        regression.get(
            "below_threshold_must_be_unavailable"
        )
        is True
        and regression.get("threshold_is_inclusive") is True
        and regression.get(
            "maximum_points_must_be_enforced"
        )
        is True
        and regression.get(
            "missing_component_must_reduce_available_score"
        )
        is True
        and regression.get(
            "confidence_must_not_change_available_score_when_usable"
        )
        is True
        and regression.get(
            "signal_engine_remains_normalized_score_authority"
        )
        is True,
    )

    passed = sum(1 for _, result in checks if result)
    failed = len(checks) - passed

    print()
    print(
        "=== B.2F.1 INSTITUTIONAL FLOW SCORE "
        "INTEGRATION POLICY ==="
    )
    print(f"Version: {EXPECTED_VERSION}")
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