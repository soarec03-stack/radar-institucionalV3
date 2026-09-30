import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONTRACT_PATH = BASE_DIR / "risk_metrics_contract_v3.json"
POLICY_PATH = BASE_DIR / "risk_policy_v3.json"

EXPECTED_CONTRACT_VERSION = "3.4J.4A-B.2J.4A"
EXPECTED_POLICY_VERSION = "3.4J.3B-B.2J.3B"

passed = 0
failed = 0


def check(condition, description):
    global passed, failed

    if condition:
        passed += 1
        print(f"[PASS] {description}")
    else:
        failed += 1
        print(f"[FAIL] {description}")


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


print("=" * 72)
print("B.2J.3B RISK POLICY AND METRICS CONTRACT REGRESSION")
print(f"Contract: {EXPECTED_CONTRACT_VERSION}")
print(f"Policy:   {EXPECTED_POLICY_VERSION}")
print("=" * 72)

contract = load_json(CONTRACT_PATH)
policy = load_json(POLICY_PATH)


# ---------------------------------------------------------------------
# RISK METRICS CONTRACT
# ---------------------------------------------------------------------

check(
    contract.get("contract_name")
    == "RADAR_INSTITUCIONAL_RISK_METRICS_V3",
    "Risk Metrics Contract has canonical name."
)

check(
    contract.get("contract_version") == EXPECTED_CONTRACT_VERSION,
    "Risk Metrics Contract version is B.2J.4A."
)

principles = contract.get("principles", {})

check(
    principles.get("no_invented_metrics") is True,
    "Risk Metrics Contract forbids invented metrics."
)

check(
    principles.get("missing_metric") is None,
    "Missing metric is represented by null."
)

check(
    principles.get("missing_is_not_neutral") is True,
    "Missing Risk metric is not neutral."
)

check(
    principles.get("risk_score_is_engine_output") is True,
    "Risk score is engine output, not raw input."
)

check(
    principles.get("research_only_source_cannot_authorize_publication")
    is True,
    "Research-only source cannot authorize official Risk publication."
)


# ---------------------------------------------------------------------
# DECLARED METRICS
# ---------------------------------------------------------------------

metrics = contract.get("metrics", {})

expected_metrics = {
    "realized_volatility_20d_pct",
    "max_drawdown_60d_pct",
    "downside_return_20d_pct",
}

check(
    set(metrics.keys()) == expected_metrics,
    "Contract contains exactly the three B.2J.3A Risk metrics."
)

for metric_name in sorted(expected_metrics):
    metric = metrics.get(metric_name, {})

    check(
        metric.get("type") == "number",
        f"{metric_name} is numeric."
    )

    check(
        metric.get("minimum") == 0,
        f"{metric_name} cannot be negative."
    )

    check(
        metric.get("direction") == "HIGHER_IS_RISKIER",
        f"{metric_name} uses higher-is-riskier semantics."
    )

check(
    metrics.get("max_drawdown_60d_pct", {}).get("maximum") == 100,
    "Maximum drawdown is bounded at 100 percent."
)


# ---------------------------------------------------------------------
# REQUIRED CONTEXT
# ---------------------------------------------------------------------

required_context = contract.get("required_context", {})

check(
    set(required_context.keys()) == {
        "ticker",
        "market_date",
        "source",
    },
    "Risk Metrics Contract requires ticker, market_date and source context."
)

check(
    required_context.get("ticker", {}).get("type") == "string",
    "Risk ticker context is a string."
)

check(
    required_context.get("market_date", {}).get("format") == "date",
    "Risk market_date uses date format."
)

source_context = required_context.get("source", {})

check(
    source_context.get("type") == "object",
    "Risk source context is an object."
)

check(
    source_context.get("required")
    == ["primary_source", "retrieved_at"],
    "Risk source context requires primary_source and retrieved_at."
)


# ---------------------------------------------------------------------
# FORBIDDEN ENGINE OUTPUTS IN RAW INPUT
# ---------------------------------------------------------------------

forbidden = set(
    contract.get("engine_output_forbidden_in_input", [])
)

expected_forbidden = {
    "risk_score",
    "risk_level",
    "normalized_risk_score",
    "radar_points",
    "decision",
}

check(
    forbidden == expected_forbidden,
    "Raw Risk Metrics input forbids exactly the declared engine outputs."
)

for field in sorted(expected_forbidden):
    check(
        field in forbidden,
        f"{field} is forbidden in raw Risk Metrics input."
    )


# ---------------------------------------------------------------------
# RISK POLICY IDENTITY
# ---------------------------------------------------------------------

check(
    policy.get("policy_name")
    == "RADAR_INSTITUCIONAL_ASSET_RISK_POLICY_V3",
    "Risk Policy has canonical name."
)

check(
    policy.get("policy_version") == EXPECTED_POLICY_VERSION,
    "Risk Policy version is B.2J.3B."
)

check(
    policy.get("enabled") is True,
    "Risk Policy is enabled."
)


# ---------------------------------------------------------------------
# RISK SEMANTICS
# ---------------------------------------------------------------------

semantics = policy.get("semantics", {})

check(
    semantics.get("risk_score_range") == [0, 100],
    "Risk score range is 0-100."
)

check(
    semantics.get("zero_means") == "MINIMUM_MEASURED_RISK",
    "Risk score zero means minimum measured risk."
)

check(
    semantics.get("hundred_means") == "MAXIMUM_MEASURED_RISK",
    "Risk score 100 means maximum measured risk."
)

check(
    semantics.get("higher_is_riskier") is True,
    "Higher Risk score means higher measured risk."
)

check(
    semantics.get("missing_is_not_neutral") is True,
    "Risk Policy does not treat missing data as neutral."
)


# ---------------------------------------------------------------------
# COMPONENT DEFINITIONS
# ---------------------------------------------------------------------

components = policy.get("components", {})

expected_components = {
    "realized_volatility",
    "max_drawdown",
    "downside_return",
}

check(
    set(components.keys()) == expected_components,
    "Policy contains exactly three initial Risk components."
)

expected_component_metrics = {
    "realized_volatility": "realized_volatility_20d_pct",
    "max_drawdown": "max_drawdown_60d_pct",
    "downside_return": "downside_return_20d_pct",
}

expected_weights = {
    "realized_volatility": 0.40,
    "max_drawdown": 0.35,
    "downside_return": 0.25,
}

for component_name in sorted(expected_components):
    component = components.get(component_name, {})

    check(
        component.get("enabled") is True,
        f"{component_name} is enabled."
    )

    check(
        component.get("metric")
        == expected_component_metrics[component_name],
        f"{component_name} references its canonical Risk metric."
    )

    check(
        isinstance(component.get("weight"), (int, float)),
        f"{component_name} has numeric weight."
    )

    check(
        component.get("weight")
        == expected_weights[component_name],
        f"{component_name} has expected model weight."
    )


# ---------------------------------------------------------------------
# WEIGHT CONSISTENCY
# ---------------------------------------------------------------------

weights = [
    component.get("weight")
    for component in components.values()
    if component.get("enabled") is True
]

check(
    all(isinstance(weight, (int, float)) for weight in weights),
    "All enabled Risk components have numeric weights."
)

check(
    abs(sum(weights) - 1.0) < 1e-12,
    "Risk component weights sum to 1.0."
)


# ---------------------------------------------------------------------
# NORMALIZATION CONTRACT
# ---------------------------------------------------------------------

for component_name in sorted(expected_components):
    component = components.get(component_name, {})
    normalization = component.get("normalization", {})
    points = normalization.get("points", [])

    check(
        normalization.get("mode") == "PIECEWISE_LINEAR",
        f"{component_name} uses piecewise-linear normalization."
    )

    check(
        len(points) >= 2,
        f"{component_name} has at least two normalization anchors."
    )

    valid_point_shapes = all(
        isinstance(point, list)
        and len(point) == 2
        and isinstance(point[0], (int, float))
        and isinstance(point[1], (int, float))
        for point in points
    )

    check(
        valid_point_shapes,
        f"{component_name} normalization anchors are numeric [input, risk] pairs."
    )

    if valid_point_shapes:
        x_values = [point[0] for point in points]
        y_values = [point[1] for point in points]

        check(
            all(
                x_values[index] < x_values[index + 1]
                for index in range(len(x_values) - 1)
            ),
            f"{component_name} normalization inputs are strictly increasing."
        )

        check(
            all(
                y_values[index] <= y_values[index + 1]
                for index in range(len(y_values) - 1)
            ),
            f"{component_name} normalized Risk outputs are monotonic."
        )

        check(
            all(0 <= value <= 100 for value in y_values),
            f"{component_name} normalized Risk anchors remain within 0-100."
        )
    else:
        check(
            False,
            f"{component_name} normalization inputs are strictly increasing."
        )
        check(
            False,
            f"{component_name} normalized Risk outputs are monotonic."
        )
        check(
            False,
            f"{component_name} normalized Risk anchors remain within 0-100."
        )

    check(
        normalization.get("below_first") == 0,
        f"{component_name} clamps values below first anchor to Risk 0."
    )

    check(
        normalization.get("above_last") == 100,
        f"{component_name} clamps values above last anchor to Risk 100."
    )


# ---------------------------------------------------------------------
# AGGREGATION / MISSING-DATA SEMANTICS
# ---------------------------------------------------------------------

aggregation = policy.get("aggregation", {})

check(
    aggregation.get("mode")
    == "WEIGHTED_AVAILABLE_COMPONENTS",
    "Aggregation uses available Risk components."
)

check(
    abs(
        aggregation.get("minimum_metric_coverage", -1)
        - 0.6666666667
    ) < 1e-12,
    "Minimum metric coverage requires two of three components."
)

check(
    aggregation.get("coverage_basis")
    == "ENABLED_COMPONENT_COUNT",
    "Risk coverage uses enabled component count."
)

check(
    aggregation.get("renormalize_available_weights") is True,
    "Available Risk component weights are renormalized."
)

check(
    aggregation.get("insufficient_data_action") == "UNAVAILABLE",
    "Insufficient Risk data becomes UNAVAILABLE."
)

check(
    aggregation.get("do_not_impute_missing_metrics") is True,
    "Missing Risk metrics cannot be imputed."
)


# ---------------------------------------------------------------------
# RISK LEVELS
# ---------------------------------------------------------------------

levels = policy.get("levels", [])

expected_level_labels = [
    "LOW",
    "MODERATE",
    "HIGH",
    "VERY_HIGH",
    "CRITICAL",
]

check(
    [level.get("label") for level in levels]
    == expected_level_labels,
    "Risk score levels are ordered LOW through CRITICAL."
)

check(
    len(levels) == 5,
    "Risk Policy declares exactly five Risk levels."
)

if len(levels) == 5:
    check(
        levels[0].get("minimum") == 0,
        "LOW Risk begins at score 0."
    )

    check(
        levels[-1].get("maximum") == 100,
        "CRITICAL Risk ends at score 100."
    )

    level_ranges_valid = all(
        isinstance(level.get("minimum"), (int, float))
        and isinstance(level.get("maximum"), (int, float))
        and level.get("minimum") <= level.get("maximum")
        for level in levels
    )

    check(
        level_ranges_valid,
        "Every Risk level has a valid numeric interval."
    )

    ordered_levels = all(
        levels[index].get("maximum")
        < levels[index + 1].get("minimum")
        for index in range(len(levels) - 1)
    )

    check(
        ordered_levels,
        "Risk level intervals are strictly ordered."
    )
else:
    check(False, "LOW Risk begins at score 0.")
    check(False, "CRITICAL Risk ends at score 100.")
    check(False, "Every Risk level has a valid numeric interval.")
    check(False, "Risk level intervals are strictly ordered.")


# ---------------------------------------------------------------------
# PUBLICATION GOVERNANCE
# ---------------------------------------------------------------------

publication = policy.get("publication", {})

check(
    publication.get("require_publication_eligible_source") is True,
    "Published Risk requires publication-eligible source."
)

check(
    publication.get(
        "research_only_allowed_for_methodology_testing"
    ) is True,
    "Research-only source is allowed for methodology testing."
)

check(
    publication.get("research_only_can_publish") is False,
    "Research-only source cannot publish official Risk."
)


# ---------------------------------------------------------------------
# PUBLIC OUTPUT CONTRACT
# ---------------------------------------------------------------------

output = policy.get("output", {})

check(
    output.get("schema_target") == "asset.risk",
    "Risk Engine targets asset.risk."
)

check(
    output.get("fields") == ["score", "level", "drivers"],
    "Risk output preserves existing Schema V3 fields."
)

check(
    output.get("levels") == expected_level_labels,
    "Risk output levels preserve existing Schema V3 enum."
)


# ---------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------

print()
print("=" * 72)
print("B.2J.3B SUMMARY")
print(f"Checks: {passed + failed}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print("=" * 72)

if failed:
    print("RESULTADO: FAIL")
    raise SystemExit(1)

print("RESULTADO: PASS")