import json
import math
from copy import deepcopy
from pathlib import Path


ENGINE_VERSION = "3.4J.5A-B.2J.5A"

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_POLICY_PATH = BASE_DIR / "risk_policy_v3.json"

STATUS_CALCULATED = "CALCULATED"
STATUS_UNAVAILABLE = "UNAVAILABLE"


def load_policy(path=None):
    policy_path = Path(path) if path else DEFAULT_POLICY_PATH

    with policy_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_valid_number(value):
    """
    Accepts finite int/float values.
    bool is rejected because bool is a subclass of int in Python.
    """
    if isinstance(value, bool):
        return False

    if not isinstance(value, (int, float)):
        return False

    return math.isfinite(float(value))


def clamp(value, minimum=0.0, maximum=100.0):
    return max(minimum, min(maximum, value))


def normalize_piecewise(value, normalization):
    """
    Piecewise-linear normalization driven exclusively by policy.

    Expected policy shape:

        {
            "mode": "PIECEWISE_LINEAR",
            "points": [
                [input_value, normalized_risk],
                ...
            ],
            "below_first": 0,
            "above_last": 100
        }

    Returns None when the input or normalization policy is unusable.
    """
    if not is_valid_number(value):
        return None

    if not isinstance(normalization, dict):
        return None

    if normalization.get("mode") != "PIECEWISE_LINEAR":
        return None

    points = normalization.get("points")

    if not isinstance(points, list) or len(points) < 2:
        return None

    parsed_points = []

    for point in points:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or not is_valid_number(point[0])
            or not is_valid_number(point[1])
        ):
            return None

        parsed_points.append(
            (float(point[0]), float(point[1]))
        )

    for index in range(len(parsed_points) - 1):
        if parsed_points[index][0] >= parsed_points[index + 1][0]:
            return None

    numeric_value = float(value)

    first_x, first_y = parsed_points[0]
    last_x, last_y = parsed_points[-1]

    if numeric_value < first_x:
        below_first = normalization.get("below_first")

        if not is_valid_number(below_first):
            return None

        return clamp(float(below_first))

    if numeric_value > last_x:
        above_last = normalization.get("above_last")

        if not is_valid_number(above_last):
            return None

        return clamp(float(above_last))

    if numeric_value == first_x:
        return clamp(first_y)

    if numeric_value == last_x:
        return clamp(last_y)

    for index in range(len(parsed_points) - 1):
        x0, y0 = parsed_points[index]
        x1, y1 = parsed_points[index + 1]

        if numeric_value == x0:
            return clamp(y0)

        if numeric_value == x1:
            return clamp(y1)

        if x0 < numeric_value < x1:
            fraction = (
                (numeric_value - x0)
                / (x1 - x0)
            )

            normalized = y0 + fraction * (y1 - y0)

            return clamp(normalized)

    return None


def resolve_risk_level(score, policy):
    """
    Resolves the public Risk level from policy-defined intervals.
    """
    if not is_valid_number(score):
        return None

    levels = policy.get("levels", [])

    if not isinstance(levels, list):
        return None

    numeric_score = float(score)

    for level in levels:
        if not isinstance(level, dict):
            continue

        minimum = level.get("minimum")
        maximum = level.get("maximum")
        label = level.get("label")

        if (
            not is_valid_number(minimum)
            or not is_valid_number(maximum)
            or not isinstance(label, str)
        ):
            continue

        if float(minimum) <= numeric_score <= float(maximum):
            return label

    return None


def calculate_component(component_name, component_policy, metrics):
    """
    Converts one raw Risk metric into normalized Risk 0-100.

    No aggregation occurs here.
    """
    result = {
        "component": component_name,
        "metric": None,
        "metric_value": None,
        "normalized_risk": None,
        "weight": None,
        "effective_weight": None,
        "contribution": None,
        "available": False,
    }

    if not isinstance(component_policy, dict):
        return result

    metric_name = component_policy.get("metric")
    weight = component_policy.get("weight")

    result["metric"] = metric_name

    if is_valid_number(weight):
        result["weight"] = float(weight)

    if component_policy.get("enabled") is not True:
        return result

    if not isinstance(metric_name, str):
        return result

    if not isinstance(metrics, dict):
        return result

    metric_value = metrics.get(metric_name)

    if not is_valid_number(metric_value):
        return result

    metric_value = float(metric_value)

    # All current B.2J.4A metrics are non-negative.
    # Negative raw values are invalid rather than low-risk observations.
    if metric_value < 0.0:
        return result

    normalized = normalize_piecewise(
        metric_value,
        component_policy.get("normalization", {}),
    )

    if normalized is None:
        return result

    if not is_valid_number(weight) or float(weight) <= 0.0:
        return result

    result["metric_value"] = metric_value
    result["normalized_risk"] = normalized
    result["available"] = True

    return result


def build_driver(component_result):
    """
    Builds a deterministic, human-readable Risk driver from an available
    component. It contains only facts already present in the analytical
    result and does not invent narrative causes.
    """
    if not isinstance(component_result, dict):
        return None

    if component_result.get("available") is not True:
        return None

    component = component_result.get("component")
    metric = component_result.get("metric")
    metric_value = component_result.get("metric_value")
    normalized_risk = component_result.get("normalized_risk")

    if (
        not isinstance(component, str)
        or not isinstance(metric, str)
        or not is_valid_number(metric_value)
        or not is_valid_number(normalized_risk)
    ):
        return None

    return (
        f"{component}: "
        f"{metric}={float(metric_value):.6f}; "
        f"normalized_risk={float(normalized_risk):.2f}"
    )


def calculate_asset_risk(metrics, policy=None):
    """
    Calculates the internal analytical Risk result.

    This result intentionally contains fields that MUST NOT be written
    directly into asset.risk, because schema_v3.json allows only:

        score
        level
        drivers

    Missing metrics:
    - do not become neutral;
    - do not receive zero risk;
    - do not contribute weight;
    - reduce coverage.

    If coverage is sufficient, available weights are renormalized.
    """
    if policy is None:
        policy = load_policy()

    if not isinstance(policy, dict):
        return {
            "status": STATUS_UNAVAILABLE,
            "score": None,
            "level": None,
            "coverage": 0.0,
            "available_components": 0,
            "total_components": 0,
            "components": {},
            "drivers": [],
        }

    components_policy = policy.get("components", {})
    aggregation = policy.get("aggregation", {})

    if not isinstance(components_policy, dict):
        components_policy = {}

    enabled_components = {
        name: component
        for name, component in components_policy.items()
        if isinstance(component, dict)
        and component.get("enabled") is True
    }

    total_components = len(enabled_components)

    component_results = {}

    for component_name, component_policy in enabled_components.items():
        component_results[component_name] = calculate_component(
            component_name,
            component_policy,
            metrics,
        )

    available_names = [
        name
        for name, result in component_results.items()
        if result.get("available") is True
    ]

    available_components = len(available_names)

    if total_components == 0:
        coverage = 0.0
    else:
        coverage = available_components / total_components

    minimum_coverage = aggregation.get(
        "minimum_metric_coverage",
        1.0,
    )

    if not is_valid_number(minimum_coverage):
        minimum_coverage = 1.0

    minimum_coverage = float(minimum_coverage)

    insufficient_action = aggregation.get(
        "insufficient_data_action"
    )

    minimum_components_required = math.ceil(
        (minimum_coverage * total_components) - 1e-9
    )

    if (
        available_components < minimum_components_required
        or available_components == 0
    ):
        return {
            "status": (
                STATUS_UNAVAILABLE
                if insufficient_action == "UNAVAILABLE"
                else STATUS_UNAVAILABLE
            ),
            "score": None,
            "level": None,
            "coverage": round(coverage, 10),
            "available_components": available_components,
            "total_components": total_components,
            "components": component_results,
            "drivers": [],
        }

    renormalize = (
        aggregation.get("renormalize_available_weights")
        is True
    )

    available_weight_sum = sum(
        component_results[name]["weight"]
        for name in available_names
        if is_valid_number(component_results[name].get("weight"))
    )

    if available_weight_sum <= 0.0:
        return {
            "status": STATUS_UNAVAILABLE,
            "score": None,
            "level": None,
            "coverage": round(coverage, 10),
            "available_components": available_components,
            "total_components": total_components,
            "components": component_results,
            "drivers": [],
        }

    score = 0.0

    for name in available_names:
        component = component_results[name]

        base_weight = float(component["weight"])

        if renormalize:
            effective_weight = (
                base_weight / available_weight_sum
            )
        else:
            effective_weight = base_weight

        contribution = (
            float(component["normalized_risk"])
            * effective_weight
        )

        component["effective_weight"] = effective_weight
        component["contribution"] = contribution

        score += contribution

    score = clamp(score, 0.0, 100.0)
    score = round(score, 2)

    level = resolve_risk_level(score, policy)

    if level is None:
        return {
            "status": STATUS_UNAVAILABLE,
            "score": None,
            "level": None,
            "coverage": round(coverage, 10),
            "available_components": available_components,
            "total_components": total_components,
            "components": component_results,
            "drivers": [],
        }

    ranked_components = sorted(
        (
            component_results[name]
            for name in available_names
        ),
        key=lambda item: (
            item.get("contribution")
            if is_valid_number(item.get("contribution"))
            else -1.0
        ),
        reverse=True,
    )

    drivers = []

    for component in ranked_components:
        driver = build_driver(component)

        if driver is not None:
            drivers.append(driver)

    return {
        "status": STATUS_CALCULATED,
        "score": score,
        "level": level,
        "coverage": round(coverage, 10),
        "available_components": available_components,
        "total_components": total_components,
        "components": component_results,
        "drivers": drivers,
    }


def build_public_risk(analytical_result):
    """
    Converts the analytical result into the stable public Schema V3
    asset.risk contract.

    Returns None when Risk is analytically unavailable.
    """
    if not isinstance(analytical_result, dict):
        return None

    if analytical_result.get("status") != STATUS_CALCULATED:
        return None

    score = analytical_result.get("score")
    level = analytical_result.get("level")
    drivers = analytical_result.get("drivers")

    if not is_valid_number(score):
        return None

    if not isinstance(level, str):
        return None

    if not isinstance(drivers, list):
        return None

    return {
        "score": float(score),
        "level": level,
        "drivers": deepcopy(drivers),
    }


def write_risk_to_asset(asset, analytical_result):
    """
    Writes only the stable public Risk contract to asset.risk.

    Analytical metadata such as coverage, components, weights and
    contributions is intentionally excluded from asset.risk.

    If Risk is unavailable, an existing asset.risk is removed rather
    than allowing a stale Risk score to survive.
    """
    if not isinstance(asset, dict):
        return asset

    public_risk = build_public_risk(analytical_result)

    if public_risk is None:
        asset.pop("risk", None)
        return asset

    asset["risk"] = public_risk

    return asset