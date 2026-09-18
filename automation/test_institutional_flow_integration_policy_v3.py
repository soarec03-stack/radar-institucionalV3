import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "automation" / "institutional_flow_integration_policy_v3.json"
SIGNAL_POLICY_PATH = ROOT / "automation" / "signal_policy_v3.json"


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def main():
    policy = load_json(POLICY_PATH)
    signal_policy = load_json(SIGNAL_POLICY_PATH)

    tests = []

    def check(name, condition):
        passed = bool(condition)
        tests.append((name, passed))
        print(f"{'PASS' if passed else 'FAIL'} - {name}")

    principles = policy["principles"]
    compatibility = policy["signal_compatibility"]
    metrics = policy["metrics"]
    eligibility = policy["eligibility"]

    signal_metrics = signal_policy["domains"]["institutional_flow"]["metrics"]
    signal_min_coverage = signal_policy["principles"]["minimum_metric_coverage"]

    check(
        "01 - Policy identity/version",
        policy["policy_name"] == "INSTITUTIONAL_FLOW_INTEGRATION"
        and policy["policy_version"] == "3.4D.2-B.2D.1"
    )

    check(
        "02 - Fail closed and missing not neutral",
        principles["fail_closed"] is True
        and principles["missing_is_not_neutral"] is True
        and principles["missing_is_not_zero"] is True
        and principles["do_not_invent_metrics"] is True
    )

    check(
        "03 - Integration does not calculate downstream analytics",
        principles["integration_does_not_assign_numeric_confidence"] is True
        and principles["integration_does_not_calculate_signal"] is True
        and principles["integration_does_not_calculate_radar_score"] is True
        and principles["integration_does_not_make_decisions"] is True
    )

    check(
        "04 - Weighted coverage matches Signal Policy",
        compatibility["minimum_weighted_metric_coverage"]
        == signal_min_coverage
        == 0.6
    )

    check(
        "05 - Integration weights match Signal Policy",
        all(
            name in signal_metrics
            and float(cfg["signal_weight"])
            == float(signal_metrics[name]["weight"])
            for name, cfg in metrics.items()
        )
    )

    holdings = metrics["institutional_flow_pct"]

    check(
        "06 - 13F explicit mapping preserves source metric",
        holdings["source_metric"] == "institutional_holdings_change_pct"
        and holdings["mapping"]["source_key"]
        == "institutional_holdings_change_pct"
        and holdings["mapping"]["signal_key"]
        == "institutional_flow_pct"
        and holdings["mapping"]["mapping_type"] == "EXPLICIT_ALIAS"
        and holdings["mapping"]["recalculation_allowed"] is False
    )

    check(
        "07 - 13F VERIFIED and PARTIAL analytically usable states allowed",
        {
            (x["quality_status"], x["analytically_usable"])
            for x in holdings["allowed_quality_states"]
        }
        == {
            ("VERIFIED", True),
            ("PARTIAL", True)
        }
    )

    short_interest = metrics["short_interest_change_pct"]

    check(
        "08 - Short Interest requires VERIFIED usable T1 FINRA",
        short_interest["source"] == "FINRA"
        and short_interest["required_source_tier"] == "TIER_1"
        and short_interest["allowed_quality_states"]
        == [
            {
                "quality_status": "VERIFIED",
                "analytically_usable": True
            }
        ]
    )

    volume = metrics["volume_ratio"]

    check(
        "09 - Volume cannot unlock institutional dimension requirement",
        volume["counts_as_independent_institutional_dimension"] is False
        and volume["institutional_eligibility_rule"][
            "may_contribute_to_weighted_metric_coverage"
        ] is True
        and volume["institutional_eligibility_rule"][
            "may_unlock_institutional_dimension_requirement"
        ] is False
    )

    options = metrics["call_put_ratio"]

    check(
        "10 - Options excluded until homologated",
        options["integration_status"] == "NOT_YET_HOMOLOGATED"
        and options["may_be_integrated"] is False
        and options["may_contribute_to_weighted_metric_coverage"] is False
        and options[
            "may_count_as_independent_institutional_dimension"
        ] is False
    )

    check(
        "11 - Two independent institutional dimensions required",
        eligibility["required_conditions"][
            "minimum_independent_institutional_dimensions"
        ] == 2
    )

    rules = eligibility["rules"]

    check(
        "12 - Blocked/unavailable metrics omitted instead of zeroed",
        rules["blocked_metric_is_omitted_not_zeroed"] is True
        and rules["unavailable_metric_is_omitted_not_zeroed"] is True
    )

    output_rules = policy["output_contract"]["data_point_rules"]

    check(
        "13 - Integration cannot create normalized score",
        output_rules[
            "normalized_score_must_not_be_created_by_integration_layer"
        ] is True
        and output_rules["source_metrics_must_not_be_recalculated"] is True
    )

    # Important semantic combinations.
    holdings_weight = float(metrics["institutional_flow_pct"]["signal_weight"])
    short_weight = float(metrics["short_interest_change_pct"]["signal_weight"])
    volume_weight = float(metrics["volume_ratio"]["signal_weight"])

    check(
        "14 - 13F plus volume reaches weight coverage but only one institutional dimension",
        round(holdings_weight + volume_weight, 10) == 0.6
        and 1 < eligibility["required_conditions"][
            "minimum_independent_institutional_dimensions"
        ]
    )

    check(
        "15 - 13F plus Short Interest reaches 60 percent and two dimensions",
        round(holdings_weight + short_weight, 10) == 0.6
        and eligibility["required_conditions"][
            "minimum_independent_institutional_dimensions"
        ] == 2
    )

    passed = sum(1 for _, ok in tests if ok)
    failed = len(tests) - passed

    print("=" * 72)
    print("INSTITUTIONAL FLOW INTEGRATION POLICY TEST")
    print("=" * 72)
    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")
    print(f"TOTAL: {len(tests)}")

    if failed:
        print("RESULTADO: REPROVADO")
        return 1

    print("RESULTADO: APROVADO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
