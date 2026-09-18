import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AUTOMATION = ROOT / "automation"

sys.path.insert(0, str(AUTOMATION))

from institutional_flow_composer_v3 import compose_asset, read_json


POLICY = read_json(
    AUTOMATION / "institutional_flow_integration_policy_v3.json"
)


def holdings(
    quality="VERIFIED",
    usable=True,
    value=-2.5,
    tier="TIER_1",
):
    return {
        "ticker": "TEST",
        "metric": "institutional_holdings_change_pct",
        "value": value,
        "quality_status": quality,
        "analytically_usable": usable,
        "provenance": {
            "source": "SEC",
            "source_type": "FORM_13F_DATA_SET",
            "tier": tier,
        },
    }


def short_interest(
    quality="VERIFIED",
    usable=True,
    value=3.0,
    tier="TIER_1",
):
    return {
        "ticker": "TEST",
        "quality_status": quality,
        "analytically_usable": usable,
        "metric": {
            "name": "short_interest_change_pct",
            "value": value,
        },
        "provenance": {
            "source": "FINRA",
            "source_tier": tier,
            "dataset": "CONSOLIDATED_SHORT_INTEREST",
        },
    }


def volume(value=1.2):
    return {
        "ticker": "TEST",
        "technical": {
            "metrics": {
                "volume_ratio": value,
            },
            "source": {
                "primary_source": "YAHOO_FINANCE",
                "market_date": "2026-09-11",
            },
        },
    }


def compose(h=None, s=None, v=None):
    return compose_asset(
        ticker="TEST",
        holdings_asset=h,
        short_interest_asset=s,
        technical_asset=v,
        policy=POLICY,
    )


def metric_names(result):
    return {
        x["metric"]
        for x in result["integrated_metrics"]
    }


def excluded_names(result):
    return {
        x["metric"]
        for x in result["excluded_metrics"]
    }


def main():
    tests = []

    def check(name, condition):
        passed = bool(condition)
        tests.append((name, passed))
        print(f"{'PASS' if passed else 'FAIL'} - {name}")

    # ------------------------------------------------------------
    # 01 - 13F alone
    # ------------------------------------------------------------
    r = compose(
        h=holdings(),
        s=None,
        v=None,
    )

    check(
        "01 - 13F alone insufficient coverage and dimensions",
        r["integration_status"]
        == "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS"
        and r["weighted_metric_coverage"] == 0.4
        and r["institutional_dimension_count"] == 1
        and r["analytically_usable"] is False
        and r["data_point"] is None
    )

    # ------------------------------------------------------------
    # 02 - 13F + volume
    # ------------------------------------------------------------
    r = compose(
        h=holdings(),
        s=None,
        v=volume(),
    )

    check(
        "02 - 13F plus volume cannot unlock second dimension",
        r["integration_status"]
        == "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS"
        and r["weighted_metric_coverage"] == 0.6
        and r["institutional_dimension_count"] == 1
        and r["data_point"] is None
    )

    # ------------------------------------------------------------
    # 03 - 13F + Short Interest
    # ------------------------------------------------------------
    r = compose(
        h=holdings(),
        s=short_interest(),
        v=None,
    )

    check(
        "03 - 13F plus Short Interest is eligible",
        r["integration_status"] == "ELIGIBLE"
        and r["weighted_metric_coverage"] == 0.6
        and r["institutional_dimension_count"] == 2
        and r["analytically_usable"] is True
        and r["data_point"] is not None
        and metric_names(r)
        == {
            "institutional_flow_pct",
            "short_interest_change_pct",
        }
    )

    # ------------------------------------------------------------
    # 04 - 13F + Short Interest + volume
    # ------------------------------------------------------------
    r = compose(
        h=holdings(),
        s=short_interest(),
        v=volume(),
    )

    check(
        "04 - Two institutional dimensions plus volume gives 80 percent",
        r["integration_status"] == "ELIGIBLE"
        and r["weighted_metric_coverage"] == 0.8
        and r["institutional_dimension_count"] == 2
        and metric_names(r)
        == {
            "institutional_flow_pct",
            "short_interest_change_pct",
            "volume_ratio",
        }
    )

    # ------------------------------------------------------------
    # 05 - PARTIAL usable 13F is allowed
    # ------------------------------------------------------------
    r = compose(
        h=holdings(
            quality="PARTIAL",
            usable=True,
        ),
        s=short_interest(),
        v=None,
    )

    check(
        "05 - PARTIAL usable 13F remains eligible",
        r["integration_status"] == "ELIGIBLE"
        and r["institutional_dimension_count"] == 2
        and r["weighted_metric_coverage"] == 0.6
    )

    # ------------------------------------------------------------
    # 06 - BLOCKED 13F cannot contribute
    # ------------------------------------------------------------
    r = compose(
        h=holdings(
            quality="BLOCKED",
            usable=False,
        ),
        s=short_interest(),
        v=volume(),
    )

    check(
        "06 - BLOCKED 13F is omitted not zeroed",
        "institutional_flow_pct" not in metric_names(r)
        and "institutional_flow_pct" in excluded_names(r)
        and r["weighted_metric_coverage"] == 0.4
        and r["institutional_dimension_count"] == 1
        and r["data_point"] is None
    )

    # ------------------------------------------------------------
    # 07 - BLOCKED Short Interest cannot use raw value
    # ------------------------------------------------------------
    blocked_si = short_interest(
        quality="BLOCKED",
        usable=False,
        value=None,
    )

    blocked_si["raw_normalized_asset"] = {
        "short_interest": {
            "collector_calculated_change_pct": 99.99
        }
    }

    r = compose(
        h=holdings(),
        s=blocked_si,
        v=volume(),
    )

    check(
        "07 - BLOCKED Short Interest raw value cannot leak",
        "short_interest_change_pct" not in metric_names(r)
        and "short_interest_change_pct" in excluded_names(r)
        and r["weighted_metric_coverage"] == 0.6
        and r["institutional_dimension_count"] == 1
        and r["data_point"] is None
    )

    # ------------------------------------------------------------
    # 08 - T1 provenance required for 13F
    # ------------------------------------------------------------
    r = compose(
        h=holdings(tier="TIER_2"),
        s=short_interest(),
        v=volume(),
    )

    check(
        "08 - Non T1 holdings provenance is rejected",
        "institutional_flow_pct" not in metric_names(r)
        and r["institutional_dimension_count"] == 1
        and r["data_point"] is None
    )

    # ------------------------------------------------------------
    # 09 - T1 provenance required for Short Interest
    # ------------------------------------------------------------
    r = compose(
        h=holdings(),
        s=short_interest(tier="TIER_2"),
        v=volume(),
    )

    check(
        "09 - Non T1 Short Interest provenance is rejected",
        "short_interest_change_pct" not in metric_names(r)
        and r["institutional_dimension_count"] == 1
        and r["data_point"] is None
    )

    # ------------------------------------------------------------
    # 10 - Missing is not zero
    # ------------------------------------------------------------
    r = compose(
        h=None,
        s=None,
        v=None,
    )

    check(
        "10 - Missing metrics are not converted to zero",
        r["integration_status"] == "UNAVAILABLE"
        and r["weighted_metric_coverage"] == 0
        and r["institutional_dimension_count"] == 0
        and r["integrated_metrics"] == []
        and r["data_point"] is None
    )

    # ------------------------------------------------------------
    # 11 - Options cannot contribute before homologation
    # ------------------------------------------------------------
    r = compose(
        h=holdings(),
        s=None,
        v=None,
    )

    check(
        "11 - Options excluded before homologation",
        "call_put_ratio" not in metric_names(r)
        and "call_put_ratio" in excluded_names(r)
    )

    # ------------------------------------------------------------
    # 12 - Explicit 13F alias preserves value
    # ------------------------------------------------------------
    r = compose(
        h=holdings(value=-2.436292),
        s=short_interest(value=0.1341168),
        v=None,
    )

    values = r["data_point"]["value"]

    check(
        "12 - Explicit 13F alias preserves source value",
        values["institutional_flow_pct"] == -2.436292
        and values["short_interest_change_pct"] == 0.1341168
    )

    # ------------------------------------------------------------
    # 13 - Input immutability
    # ------------------------------------------------------------
    h = holdings()
    s = short_interest()
    v = volume()

    h_before = copy.deepcopy(h)
    s_before = copy.deepcopy(s)
    v_before = copy.deepcopy(v)

    compose(h=h, s=s, v=v)

    check(
        "13 - Composer does not mutate upstream inputs",
        h == h_before
        and s == s_before
        and v == v_before
    )

    # ------------------------------------------------------------
    # 14 - No normalized score in integration data point
    # ------------------------------------------------------------
    r = compose(
        h=holdings(),
        s=short_interest(),
        v=volume(),
    )

    check(
        "14 - Composer does not calculate normalized score",
        r["data_point"] is not None
        and "normalized_score" not in r["data_point"]
    )

    # ------------------------------------------------------------
    # 15 - Supporting volume never counts as dimension
    # ------------------------------------------------------------
    r = compose(
        h=None,
        s=None,
        v=volume(),
    )

    check(
        "15 - Volume is supporting metric only",
        r["weighted_metric_coverage"] == 0.2
        and r["institutional_dimension_count"] == 0
        and "volume_ratio" in metric_names(r)
        and r["data_point"] is None
    )

    print("=" * 72)
    print("INSTITUTIONAL FLOW COMPOSER REGRESSION")
    print("=" * 72)

    passed = sum(
        1 for _, ok in tests
        if ok
    )
    failed = len(tests) - passed

    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")
    print(f"TOTAL: {len(tests)}")

    if failed:
        print("RESULTADO: REPROVADO")
        return 1

    print("RESULTADO: APROVADO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
