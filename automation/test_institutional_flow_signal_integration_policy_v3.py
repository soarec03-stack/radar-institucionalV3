import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
POLICY_PATH = BASE_DIR / "institutional_flow_signal_integration_policy_v3.json"

EXPECTED_POLICY_VERSION = "3.4D.2-B.2E.1"

EXPECTED_METRICS = {
    "institutional_flow_pct": {
        "weight": 0.4,
        "transform": "higher_better",
        "bad": -5,
        "good": 5,
    },
    "volume_ratio": {
        "weight": 0.2,
        "transform": "higher_better",
        "bad": 0.5,
        "good": 2.0,
    },
    "short_interest_change_pct": {
        "weight": 0.2,
        "transform": "lower_better",
        "bad": 10,
        "good": -10,
    },
    "call_put_ratio": {
        "weight": 0.2,
        "transform": "higher_better",
        "bad": 0.5,
        "good": 2.0,
    },
}


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def check(condition, name, failures, counters):
    counters["checks"] += 1

    if condition:
        counters["passed"] += 1
        print(f"[PASS] {name}")
        return

    counters["failed"] += 1
    print(f"[FAIL] {name}")
    failures.append(name)


def main():
    failures = []

    counters = {
        "checks": 0,
        "passed": 0,
        "failed": 0,
    }

    try:
        policy = load_json(POLICY_PATH)
    except Exception as exc:
        print(f"[FAIL] POLICY_LOAD: {exc}")
        return 1

    check(
        policy.get("policy_version") == EXPECTED_POLICY_VERSION,
        "POLICY_VERSION",
        failures,
        counters,
    )

    principles = policy.get("principles", {})

    check(
        principles.get("policy_before_code") is True
        and principles.get("fail_closed") is True
        and principles.get("missing_is_not_neutral") is True
        and principles.get("missing_is_not_zero") is True
        and principles.get("do_not_invent_metrics") is True,
        "CORE_FAIL_CLOSED_PRINCIPLES",
        failures,
        counters,
    )

    check(
        principles.get(
            "composer_is_authoritative_for_institutional_eligibility"
        )
        is True
        and principles.get(
            "integration_does_not_recalculate_composer_eligibility"
        )
        is True,
        "COMPOSER_ELIGIBILITY_AUTHORITY",
        failures,
        counters,
    )

    check(
        principles.get(
            "metrics_loader_remains_authoritative_for_data_point_construction"
        )
        is True,
        "METRICS_LOADER_AUTHORITY",
        failures,
        counters,
    )

    check(
        principles.get(
            "signal_engine_remains_authoritative_for_normalized_score"
        )
        is True
        and principles.get(
            "integration_does_not_calculate_normalized_score"
        )
        is True,
        "SIGNAL_ENGINE_AUTHORITY",
        failures,
        counters,
    )

    upstream = policy.get("upstream_contract", {})
    eligibility = (
        upstream
        .get("eligibility_rule", {})
        .get("all_required", [])
    )

    eligibility_map = {
        item.get("field"): item
        for item in eligibility
        if isinstance(item, dict)
    }

    check(
        upstream.get("eligible_status") == "ELIGIBLE"
        and eligibility_map.get(
            "integration_status", {}
        ).get("value") == "ELIGIBLE"
        and eligibility_map.get(
            "analytically_usable", {}
        ).get("value") is True
        and eligibility_map.get(
            "data_point", {}
        ).get("operator") == "IS_NON_NULL_OBJECT",
        "ELIGIBILITY_TRIPLE_GATE",
        failures,
        counters,
    )

    non_eligible = upstream.get("non_eligible_rule", {})

    check(
        non_eligible.get("publish_metrics") is False
        and non_eligible.get(
            "recover_metrics_from_audit_paths"
        ) is False
        and non_eligible.get(
            "convert_missing_to_zero"
        ) is False
        and non_eligible.get(
            "convert_missing_to_neutral"
        ) is False,
        "NON_ELIGIBLE_SUPPRESSION",
        failures,
        counters,
    )

    signal_contract = policy.get("signal_contract", {})
    allowed_metrics = signal_contract.get(
        "allowed_metrics", {}
    )

    check(
        set(allowed_metrics.keys())
        == set(EXPECTED_METRICS.keys()),
        "SIGNAL_METRIC_SET",
        failures,
        counters,
    )

    signal_semantics_ok = True

    for metric_name, expected in EXPECTED_METRICS.items():
        actual = allowed_metrics.get(metric_name, {})

        if (
            actual.get("signal_weight") != expected["weight"]
            or actual.get("transform") != expected["transform"]
            or actual.get("bad") != expected["bad"]
            or actual.get("good") != expected["good"]
        ):
            signal_semantics_ok = False
            break

    check(
        signal_semantics_ok,
        "SIGNAL_POLICY_SEMANTICS",
        failures,
        counters,
    )

    normalized = signal_contract.get(
        "normalized_score", {}
    )

    check(
        signal_contract.get("engine_output_key")
        == "normalized_score"
        and normalized.get("produced_by")
        == "SIGNAL_ENGINE"
        and normalized.get(
            "adapter_must_not_produce"
        ) is True
        and normalized.get(
            "adapter_must_not_copy_from_upstream"
        ) is True,
        "NORMALIZED_SCORE_BOUNDARY",
        failures,
        counters,
    )

    metric_semantics = policy.get(
        "metric_semantics", {}
    )

    holdings = metric_semantics.get(
        "institutional_flow_pct", {}
    )

    short_interest = metric_semantics.get(
        "short_interest_change_pct", {}
    )

    volume = metric_semantics.get(
        "volume_ratio", {}
    )

    options = metric_semantics.get(
        "call_put_ratio", {}
    )

    check(
        holdings.get("source_metric")
        == "institutional_holdings_change_pct"
        and holdings.get("mapping_type")
        == "EXPLICIT_ALIAS"
        and holdings.get(
            "institutional_dimension"
        ) == "INSTITUTIONAL_HOLDINGS"
        and holdings.get(
            "counts_as_independent_institutional_dimension"
        ) is True,
        "HOLDINGS_MAPPING_SEMANTICS",
        failures,
        counters,
    )

    check(
        short_interest.get("source_metric")
        == "short_interest_change_pct"
        and short_interest.get("mapping_type")
        == "DIRECT"
        and short_interest.get(
            "institutional_dimension"
        ) == "SHORT_INTEREST"
        and short_interest.get(
            "counts_as_independent_institutional_dimension"
        ) is True,
        "SHORT_INTEREST_MAPPING_SEMANTICS",
        failures,
        counters,
    )

    check(
        volume.get("source_metric")
        == "volume_ratio"
        and volume.get(
            "institutional_classification"
        ) == "SUPPORTING_MARKET_ACTIVITY"
        and volume.get(
            "institutional_dimension"
        ) is None
        and volume.get(
            "counts_as_independent_institutional_dimension"
        ) is False,
        "VOLUME_SUPPORTING_ONLY",
        failures,
        counters,
    )

    check(
        options.get(
            "upstream_integration_status"
        ) == "NOT_YET_HOMOLOGATED"
        and options.get(
            "adapter_must_not_enable_if_not_integrated_by_composer"
        ) is True,
        "OPTIONS_NOT_YET_HOMOLOGATED",
        failures,
        counters,
    )

    forbidden_paths = set(
        policy.get(
            "forbidden_recovery_paths", []
        )
    )

    check(
        {
            "raw_inputs",
            "raw_normalized_asset",
            "raw_boundary_asset",
            "technical_metrics",
            "raw_upstream",
            "excluded_metrics",
        }.issubset(forbidden_paths),
        "RAW_RECOVERY_PATHS_FORBIDDEN",
        failures,
        counters,
    )

    forbidden_behaviors = set(
        policy.get(
            "forbidden_behaviors", []
        )
    )

    check(
        {
            "RECALCULATE_COMPOSER_ELIGIBILITY",
            "RECALCULATE_INSTITUTIONAL_DIMENSION_COUNT",
            "RECOVER_BLOCKED_SHORT_INTEREST_METRIC",
            "USE_RAW_AUDIT_VALUE_AS_SIGNAL_INPUT",
            "CALCULATE_NORMALIZED_SCORE",
            "ASSIGN_NUMERIC_CONFIDENCE",
            "CALCULATE_RADAR_SCORE",
            "MAKE_INVESTMENT_DECISION",
        }.issubset(forbidden_behaviors),
        "FORBIDDEN_BEHAVIORS",
        failures,
        counters,
    )

    loader_contract = policy.get(
        "metrics_loader_payload_contract", {}
    )

    loader_metrics = loader_contract.get(
        "metrics", {}
    )

    check(
        loader_metrics.get(
            "must_be_non_empty"
        ) is True
        and loader_metrics.get(
            "normalized_score_forbidden"
        ) is True
        and set(
            loader_metrics.get(
                "allowed_keys", []
            )
        ) == set(EXPECTED_METRICS.keys()),
        "METRICS_LOADER_PAYLOAD_CONTRACT",
        failures,
        counters,
    )

    fail_closed = policy.get(
        "fail_closed_rules", {}
    )

    required_blocks = {
        "unknown_integration_status",
        "missing_ticker",
        "identity_mismatch",
        "missing_analytically_usable",
        "eligible_with_analytically_usable_false",
        "eligible_with_null_data_point",
        "eligible_with_empty_metrics",
        "eligible_with_unknown_metric",
        "eligible_with_invalid_metric_type",
        "eligible_with_invalid_metric_bounds",
        "missing_required_provenance",
        "non_eligible_with_non_null_data_point",
        "normalized_score_received_from_upstream",
    }

    check(
        required_blocks.issubset(
            set(fail_closed.keys())
        )
        and all(
            fail_closed.get(key) == "BLOCK"
            for key in required_blocks
        ),
        "FAIL_CLOSED_RULES",
        failures,
        counters,
    )

    real_expectation = policy.get(
        "current_real_pipeline_expectation", {}
    )

    real_assets = real_expectation.get(
        "expected_assets", {}
    )

    real_pipeline_ok = True

    for ticker in ("CRSP", "ETON", "VRT"):
        asset = real_assets.get(ticker, {})

        if not (
            asset.get("composer_status")
            == "INSUFFICIENT_INSTITUTIONAL_DIMENSIONS"
            and asset.get(
                "composer_analytically_usable"
            ) is False
            and asset.get(
                "composer_data_point"
            ) is None
            and asset.get(
                "expected_boundary_status"
            ) == "SUPPRESSED"
            and asset.get(
                "expected_metrics_published"
            ) is False
        ):
            real_pipeline_ok = False
            break

    check(
        real_pipeline_ok,
        "CURRENT_REAL_PIPELINE_EXPECTATION",
        failures,
        counters,
    )

    regression = policy.get(
        "regression_requirements", {}
    )

    check(
        len(
            regression.get(
                "negative_cases", []
            )
        ) >= 10
        and len(
            regression.get(
                "positive_cases", []
            )
        ) >= 2,
        "REGRESSION_REQUIREMENTS",
        failures,
        counters,
    )

    print()
    print("=== B.2E.1 POLICY STRUCTURAL TEST ===")
    print(f"Checks: {counters['checks']}")
    print(f"Passed: {counters['passed']}")
    print(f"Failed: {counters['failed']}")

    if failures:
        print()
        print("Falhas:")

        for failure in failures:
            print(f" - {failure}")

        print()
        print("RESULTADO: FAIL")
        return 1

    print()
    print("RESULTADO: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())