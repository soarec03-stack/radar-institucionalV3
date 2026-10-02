import ast
from pathlib import Path

GENERATOR = Path(__file__).with_name("generate_radar_v3.py")

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


text = GENERATOR.read_text(encoding="utf-8-sig")
tree = ast.parse(text)

# ------------------------------------------------------------
# Discover argparse option strings without executing generator.
# ------------------------------------------------------------

options = set()

for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue

    func = node.func

    if not (
        isinstance(func, ast.Attribute)
        and func.attr == "add_argument"
    ):
        continue

    for arg in node.args:
        if (
            isinstance(arg, ast.Constant)
            and isinstance(arg.value, str)
            and arg.value.startswith("--")
        ):
            options.add(arg.value)


required_new_options = {
    "--metrics-input",
    "--risk-history",
    "--signal-policy",
    "--score-policy",
    "--risk-policy",
    "--publication-policy",
}

legacy_options = {
    "--input",
    "--schema",
    "--output",
    "--policy",
    "--registry",
    "--history-dir",
    "--allow-warnings",
    "--allow-quality-critical-in-draft",
}


print("=" * 72)
print("B.2L.6C ? PRODUCTION ORCHESTRATION INPUT CONTRACT")
print("=" * 72)

for option in sorted(legacy_options):
    check(
        f"Legacy CLI preserved: {option}",
        option in options,
    )

for option in sorted(required_new_options):
    check(
        f"Production CLI exists: {option}",
        option in options,
    )


# ------------------------------------------------------------
# Contract constants
# ------------------------------------------------------------

assignments = {}

for node in tree.body:
    if not isinstance(
        node,
        (ast.Assign, ast.AnnAssign),
    ):
        continue

    targets = []

    if isinstance(node, ast.Assign):
        targets = node.targets
        value = node.value
    else:
        targets = [node.target]
        value = node.value

    for target in targets:
        if isinstance(target, ast.Name):
            assignments[target.id] = value


for name in (
    "DEFAULT_SIGNAL_POLICY",
    "DEFAULT_SCORE_POLICY",
    "DEFAULT_RISK_POLICY",
    "DEFAULT_PUBLICATION_POLICY",
):
    check(
        f"Policy default declared: {name}",
        name in assignments,
    )


# ------------------------------------------------------------
# Metrics and Risk must NOT have hidden production data defaults.
#
# Their CLI arguments may default to None, but must not silently
# point to B.2K/test fixture files.
# ------------------------------------------------------------

for forbidden in (
    "metrics_real_B2K_v3.json",
    "risk_history_real_B2K_v3.json",
    "automation/fixtures/b2k_e2e",
):
    check(
        f"No production dependency on test artifact: {forbidden}",
        forbidden not in text,
    )


# ------------------------------------------------------------
# Required orchestration modules must become explicit generator
# dependencies. This is intentionally RED before implementation.
# ------------------------------------------------------------

required_modules = {
    "metrics_loader_v3",
    "signal_engine_v3",
    "risk_history_adapter_v3",
    "risk_metrics_calculator_v3",
    "risk_engine_v3",
    "score_engine_v3",
    "publication_eligibility_v3",
}

referenced_modules = set()

for node in ast.walk(tree):
    if isinstance(node, ast.Constant):
        value = node.value

        if isinstance(value, str):
            for module in required_modules:
                if module in value:
                    referenced_modules.add(module)

    elif isinstance(node, ast.ImportFrom):
        if node.module:
            for module in required_modules:
                if module in node.module:
                    referenced_modules.add(module)

    elif isinstance(node, ast.Import):
        for alias in node.names:
            for module in required_modules:
                if module in alias.name:
                    referenced_modules.add(module)


for module in sorted(required_modules):
    check(
        f"Generator references orchestration module: {module}",
        module in referenced_modules,
    )


print()
print("PASS:", passed)
print("FAIL:", failed)

if failed:
    print(
        "RESULT: EXPECTED TEST-FIRST FAILURE "
        "UNTIL PRODUCTION ORCHESTRATION IS IMPLEMENTED"
    )
    raise SystemExit(1)

print("RESULT: PRODUCTION INPUT CONTRACT APPROVED")
raise SystemExit(0)
