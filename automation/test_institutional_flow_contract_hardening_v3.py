import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AUTOMATION = ROOT / "automation"

sys.path.insert(0, str(AUTOMATION))

from institutional_flow_composer_v3 import (
    read_json,
    run_composer,
)


POLICY = read_json(
    AUTOMATION / "institutional_flow_integration_policy_v3.json"
)


def universe_asset(
    ticker="TEST",
    enabled=True,
    exchange="NASDAQ",
    cusip="123456789",
):
    return {
        "enabled": enabled,
        "ticker": ticker,
        "issuer_name": "Test Issuer",
        "security_name": "Common Stock",
        "security_type": "COMMON_STOCK",
        "country_of_issuer": "US",
        "listing": {
            "exchange": exchange,
            "exchange_group": exchange,
            "currency": "USD",
        },
        "identifiers": {
            "cusip": cusip,
            "sec_cik": "0000000001",
        },
        "domain_eligibility": {
            "INSTITUTIONAL_HOLDINGS_13F": True,
            "SHORT_INTEREST": True,
            "OPTIONS": None,
            "TECHNICAL": True,
            "FUNDAMENTALS": True,
            "MACRO": True,
        },
        "source_routing": {
            "institutional_holdings": {
                "primary_source": "SEC",
                "dataset": "FORM_13F_DATA_SET",
            },
            "short_interest": {
                "primary_source": "FINRA",
                "dataset": "CONSOLIDATED_SHORT_INTEREST",
                "listing_exchange_verification": exchange,
            },
        },
    }


def universe_payload(
    enabled=True,
    exchange="NASDAQ",
    cusip="123456789",
):
    return {
        "schema_version": "3.0",
        "universe_version": "TEST",
        "universe_name": "TEST_UNIVERSE",
        "assets": {
            "TEST": universe_asset(
                enabled=enabled,
                exchange=exchange,
                cusip=cusip,
            )
        },
    }


def holdings_asset(
    ticker="TEST",
    cusip="123456789",
    value=2.0,
):
    return {
        "ticker": ticker,
        "issuer_name": "Test Issuer",
        "cusip": cusip,
        "metric": "institutional_holdings_change_pct",
        "value": value,
        "quality_status": "VERIFIED",
        "analytically_usable": True,
        "provenance": {
            "source": "SEC",
            "source_type": "FORM_13F_DATA_SET",
            "tier": "TIER_1",
        },
    }


def holdings_payload(
    asset=None,
    key="TEST",
):
    if asset is None:
        asset = holdings_asset()

    return {
        "assets": {
            key: asset,
        }
    }


def short_interest_asset(
    ticker="TEST",
    exchange="NASDAQ",
    cusip="123456789",
    value=-2.0,
):
    return {
        "ticker": ticker,
        "quality_status": "VERIFIED",
        "analytically_usable": True,
        "metric": {
            "name": "short_interest_change_pct",
            "value": value,
        },
        "provenance": {
            "source": "FINRA",
            "source_tier": "TIER_1",
            "dataset": "CONSOLIDATED_SHORT_INTEREST",
        },
        "raw_normalized_asset": {
            "identity": {
                "ticker": ticker,
                "listing_exchange": exchange,
                "cusip": cusip,
            }
        },
    }


def short_interest_payload(asset=None):
    if asset is None:
        asset = short_interest_asset()

    return {
        "assets": [asset]
    }


def technical_asset(
    ticker="TEST",
    volume_ratio=1.2,
):
    return {
        "ticker": ticker,
        "technical": {
            "metrics": {
                "volume_ratio": volume_ratio,
            },
            "source": {
                "primary_source": "YAHOO_FINANCE",
                "market_date": "2026-09-11",
            },
        },
    }


def technical_payload(asset=None):
    if asset is None:
        asset = technical_asset()

    return {
        "assets": [asset]
    }


def run(
    universe=None,
    holdings=None,
    short_interest=None,
    technical=None,
):
    if universe is None:
        universe = universe_payload()

    if holdings is None:
        holdings = holdings_payload()

    if short_interest is None:
        short_interest = short_interest_payload()

    if technical is None:
        technical = technical_payload()

    return run_composer(
        POLICY,
        universe,
        holdings,
        short_interest,
        technical,
    )


def expect_runtime_error(fn, text):
    try:
        fn()
    except RuntimeError as exc:
        return text in str(exc)

    return False


def main():
    tests = []

    def check(name, condition):
        passed = bool(condition)
        tests.append((name, passed))

        print(
            f"{'PASS' if passed else 'FAIL'} - {name}"
        )

    # ------------------------------------------------------------
    # 01 - Happy path
    # ------------------------------------------------------------
    r = run()
    asset = r["assets"][0]

    check(
        "01 - Master Universe happy path",
        asset["ticker"] == "TEST"
        and asset["integration_status"] == "ELIGIBLE"
        and asset["analytically_usable"] is True
        and asset["identity_diagnostics"] == []
        and asset["master_identity"]["ticker"] == "TEST"
        and asset["master_identity"]["listing_exchange"] == "NASDAQ"
        and asset["master_identity"]["cusip"] == "123456789"
    )

    # ------------------------------------------------------------
    # 02 - Master ticker missing from holdings
    # ------------------------------------------------------------
    r = run(
        holdings={"assets": {}},
    )

    asset = r["assets"][0]

    check(
        "02 - Missing holdings is unavailable not zero",
        asset["ticker"] == "TEST"
        and asset["analytically_usable"] is False
        and asset["data_point"] is None
        and asset["weighted_metric_coverage"] == 0.4
        and asset["institutional_dimension_count"] == 1
        and any(
            x["metric"] == "institutional_flow_pct"
            for x in asset["excluded_metrics"]
        )
    )

    # ------------------------------------------------------------
    # 03 - Master ticker missing from Short Interest
    # ------------------------------------------------------------
    r = run(
        short_interest={"assets": []},
    )

    asset = r["assets"][0]

    check(
        "03 - Missing Short Interest is unavailable not zero",
        asset["integration_status"]
        == "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS"
        and asset["weighted_metric_coverage"] == 0.6
        and asset["institutional_dimension_count"] == 1
        and asset["data_point"] is None
    )

    # ------------------------------------------------------------
    # 04 - Master ticker missing from Technical
    # ------------------------------------------------------------
    r = run(
        technical={"assets": []},
    )

    asset = r["assets"][0]

    check(
        "04 - Missing Technical does not block valid institutional evidence",
        asset["integration_status"] == "ELIGIBLE"
        and asset["weighted_metric_coverage"] == 0.6
        and asset["institutional_dimension_count"] == 2
        and asset["analytically_usable"] is True
    )

    # ------------------------------------------------------------
    # 05 - Orphan Holdings
    # ------------------------------------------------------------
    orphan = holdings_asset(
        ticker="ORPHAN",
        cusip="999999999",
    )

    check(
        "05 - Orphan Holdings fails closed",
        expect_runtime_error(
            lambda: run(
                holdings={
                    "assets": {
                        "TEST": holdings_asset(),
                        "ORPHAN": orphan,
                    }
                }
            ),
            "ORPHAN_ASSET_DETECTED",
        )
    )

    # ------------------------------------------------------------
    # 06 - Orphan Short Interest
    # ------------------------------------------------------------
    orphan_si = short_interest_asset(
        ticker="ORPHAN",
        cusip="999999999",
    )

    check(
        "06 - Orphan Short Interest fails closed",
        expect_runtime_error(
            lambda: run(
                short_interest={
                    "assets": [
                        short_interest_asset(),
                        orphan_si,
                    ]
                }
            ),
            "ORPHAN_ASSET_DETECTED",
        )
    )

    # ------------------------------------------------------------
    # 07 - Orphan Technical
    # ------------------------------------------------------------
    orphan_technical = technical_asset(
        ticker="ORPHAN",
    )

    check(
        "07 - Orphan Technical fails closed",
        expect_runtime_error(
            lambda: run(
                technical={
                    "assets": [
                        technical_asset(),
                        orphan_technical,
                    ]
                }
            ),
            "ORPHAN_ASSET_DETECTED",
        )
    )

    # ------------------------------------------------------------
    # 08 - Holdings CUSIP mismatch
    # ------------------------------------------------------------
    r = run(
        holdings=holdings_payload(
            holdings_asset(
                cusip="999999999",
            )
        )
    )

    asset = r["assets"][0]

    check(
        "08 - Holdings CUSIP mismatch blocks integration",
        asset["integration_status"] == "BLOCKED"
        and asset["analytically_usable"] is False
        and asset["data_point"] is None
        and "HOLDINGS_CUSIP_IDENTITY_MISMATCH"
        in asset["identity_diagnostics"]
    )

    # ------------------------------------------------------------
    # 09 - Short Interest exchange mismatch
    # ------------------------------------------------------------
    r = run(
        short_interest=short_interest_payload(
            short_interest_asset(
                exchange="NYSE",
            )
        )
    )

    asset = r["assets"][0]

    check(
        "09 - Short Interest exchange mismatch blocks integration",
        asset["integration_status"] == "BLOCKED"
        and asset["analytically_usable"] is False
        and asset["data_point"] is None
        and "SHORT_INTEREST_EXCHANGE_IDENTITY_MISMATCH"
        in asset["identity_diagnostics"]
    )

    # ------------------------------------------------------------
    # 10 - Short Interest CUSIP mismatch
    # ------------------------------------------------------------
    r = run(
        short_interest=short_interest_payload(
            short_interest_asset(
                cusip="999999999",
            )
        )
    )

    asset = r["assets"][0]

    check(
        "10 - Short Interest CUSIP mismatch blocks integration",
        asset["integration_status"] == "BLOCKED"
        and asset["analytically_usable"] is False
        and asset["data_point"] is None
        and "SHORT_INTEREST_CUSIP_IDENTITY_MISMATCH"
        in asset["identity_diagnostics"]
    )

    # ------------------------------------------------------------
    # 11 - Disabled Master asset
    # ------------------------------------------------------------
    r = run(
        universe=universe_payload(
            enabled=False,
        )
    )

    check(
        "11 - Disabled Master asset is not processed",
        r["assets"] == []
        and r["summary"]["total_assets"] == 0
    )

    # ------------------------------------------------------------
    # 12 - Universe ticker/key mismatch
    # ------------------------------------------------------------
    bad_universe = universe_payload()

    bad_universe["assets"]["TEST"]["ticker"] = "OTHER"

    check(
        "12 - Master Universe ticker key mismatch fails closed",
        expect_runtime_error(
            lambda: run(
                universe=bad_universe,
            ),
            "ticker/key mismatch",
        )
    )

    # ------------------------------------------------------------
    # 13 - Duplicate Short Interest ticker
    # ------------------------------------------------------------
    duplicate_si = {
        "assets": [
            short_interest_asset(),
            copy.deepcopy(short_interest_asset()),
        ]
    }

    check(
        "13 - Duplicate Short Interest ticker fails closed",
        expect_runtime_error(
            lambda: run(
                short_interest=duplicate_si,
            ),
            "duplicate ticker TEST",
        )
    )

    # ------------------------------------------------------------
    # 14 - Empty Master Universe
    # ------------------------------------------------------------
    empty_universe = {
        "schema_version": "3.0",
        "universe_version": "TEST",
        "universe_name": "TEST_UNIVERSE",
        "assets": {},
    }

    check(
        "14 - Empty Master Universe fails closed",
        expect_runtime_error(
            lambda: run(
                universe=empty_universe,
            ),
            "non-empty object",
        )
    )

    # ------------------------------------------------------------
    # 15 - Hardening does not mutate inputs
    # ------------------------------------------------------------
    u = universe_payload()
    h = holdings_payload()
    s = short_interest_payload()
    t = technical_payload()

    u_before = copy.deepcopy(u)
    h_before = copy.deepcopy(h)
    s_before = copy.deepcopy(s)
    t_before = copy.deepcopy(t)

    run(
        universe=u,
        holdings=h,
        short_interest=s,
        technical=t,
    )

    check(
        "15 - Hardening does not mutate upstream contracts",
        u == u_before
        and h == h_before
        and s == s_before
        and t == t_before
    )

    print("=" * 72)
    print("INSTITUTIONAL FLOW CONTRACT HARDENING REGRESSION")
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
