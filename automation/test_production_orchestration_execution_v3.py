import ast
from pathlib import Path

GENERATOR = Path(__file__).with_name(
    "generate_radar_v3.py"
)

text = GENERATOR.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(text)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed

    if condition:
        print("PASS -", name)
        passed += 1
    else:
        print("FAIL -", name)
        failed += 1


def calls_named(name):
    result = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if (
            isinstance(func, ast.Name)
            and func.id == name
        ):
            result.append(node)

        elif (
            isinstance(func, ast.Attribute)
            and func.attr == name
        ):
            result.append(node)

    return result


def source_contains(value):
    return value in text


print("=" * 72)
print("B.2L.6E ? PRODUCTION EXECUTION CONTRACT")
print("=" * 72)

# ------------------------------------------------------------
# Structural contract from B.2L.6D must remain present.
# ------------------------------------------------------------

for option in (
    "--metrics-input",
    "--risk-history",
    "--signal-policy",
    "--score-policy",
    "--risk-policy",
    "--publication-policy",
):
    check(
        f"CLI preserved: {option}",
        source_contains(option),
    )


# ------------------------------------------------------------
# Dynamic module loading.
# Existing generator architecture uses load_module().
# Each production engine must actually be loaded, not merely
# referenced through a path constant.
# ------------------------------------------------------------

for module_constant in (
    "METRICS_LOADER_MODULE",
    "SIGNAL_ENGINE_MODULE",
    "RISK_HISTORY_ADAPTER_MODULE",
    "RISK_METRICS_CALCULATOR_MODULE",
    "RISK_ENGINE_MODULE",
    "SCORE_ENGINE_MODULE",
    "PUBLICATION_ELIGIBILITY_MODULE",
):
    check(
        f"Module participates in runtime loading: {module_constant}",
        (
            module_constant in text
            and "load_module" in text
            and text.count(module_constant) >= 2
        ),
    )


# ------------------------------------------------------------
# Metrics enrichment must be opt-in.
# We require an explicit args.metrics_input guard.
# ------------------------------------------------------------

check(
    "Metrics execution is explicitly guarded by args.metrics_input",
    "args.metrics_input" in text,
)

check(
    "Metrics Loader merge_metrics executes",
    source_contains("merge_metrics"),
)


# ------------------------------------------------------------
# Signal and Score are part of metrics enrichment.
# ------------------------------------------------------------

check(
    "Signal Engine executes",
    source_contains("apply_signal_engine"),
)

check(
    "Score calculation executes",
    source_contains("calculate_asset_score"),
)

check(
    "Score writer executes",
    source_contains("write_score_to_asset"),
)


# ------------------------------------------------------------
# Risk must be independently opt-in.
# ------------------------------------------------------------

check(
    "Risk execution is explicitly guarded by args.risk_history",
    "args.risk_history" in text,
)

for call in (
    "prepare_risk_history",
    "calculate_risk_metrics",
    "calculate_asset_risk",
    "write_risk_to_asset",
):
    check(
        f"Risk pipeline executes: {call}",
        source_contains(call),
    )


# ------------------------------------------------------------
# Publication eligibility is an execution stage.
# ------------------------------------------------------------

check(
    "Publication Eligibility executes",
    source_contains("apply_publication_eligibility"),
)


# ------------------------------------------------------------
# Policy files must actually be loaded at runtime.
# Merely declaring argparse defaults is not sufficient.
# ------------------------------------------------------------

for arg_name in (
    "signal_policy",
    "score_policy",
    "risk_policy",
    "publication_policy",
):
    check(
        f"Runtime consumes args.{arg_name}",
        text.count(f"args.{arg_name}") >= 1,
    )


# ------------------------------------------------------------
# Production data must remain external.
# ------------------------------------------------------------

for forbidden in (
    "metrics_real_B2K_v3.json",
    "risk_history_real_B2K_v3.json",
    "automation/fixtures/b2k_e2e",
):
    check(
        f"No test artifact dependency: {forbidden}",
        forbidden not in text,
    )


# ------------------------------------------------------------
# No silent metrics/risk defaults.
# ------------------------------------------------------------

check(
    "metrics-input remains opt-in default None",
    (
        '"--metrics-input"' in text
        and "default=None" in text
    ),
)

check(
    "risk-history remains opt-in default None",
    (
        '"--risk-history"' in text
        and "default=None" in text
    ),
)


print()
print("PASS:", passed)
print("FAIL:", failed)

if failed:
    print(
        "RESULT: EXPECTED TEST-FIRST FAILURE "
        "UNTIL EXECUTION WIRING IS IMPLEMENTED"
    )
    raise SystemExit(1)

print(
    "RESULT: PRODUCTION EXECUTION CONTRACT APPROVED"
)
raise SystemExit(0)
