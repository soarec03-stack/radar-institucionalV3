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


print("=" * 72)
print("B.2L.6F.4A ? GENERATOR PLACEHOLDER BOUNDARY")
print("=" * 72)


# ------------------------------------------------------------
# 1. Placeholder module must become a generator dependency.
# ------------------------------------------------------------

check(
    "Generator references score_placeholder_v3",
    "score_placeholder_v3" in text,
)

check(
    "Generator references prepare_score_placeholders",
    "prepare_score_placeholders" in text,
)


# ------------------------------------------------------------
# 2. Enrichment activation must be explicit.
#
# Metrics and Risk are the two production data inputs introduced
# by B.2L.6. Either one activates the new working-copy boundary.
# ------------------------------------------------------------

check(
    "Generator references args.metrics_input",
    "args.metrics_input" in text,
)

check(
    "Generator references args.risk_history",
    "args.risk_history" in text,
)


# ------------------------------------------------------------
# 3. Require an explicit enrichment activation expression.
# We accept either a named variable or direct conditional, but
# both CLI inputs must participate.
# ------------------------------------------------------------

enrichment_nodes = []

for node in ast.walk(tree):
    if isinstance(node, (ast.If, ast.Assign, ast.AnnAssign)):
        try:
            source = ast.get_source_segment(
                text,
                node,
            ) or ""
        except Exception:
            source = ""

        if (
            "args.metrics_input" in source
            and "args.risk_history" in source
        ):
            enrichment_nodes.append(node)

check(
    "Enrichment activation depends on metrics-input or risk-history",
    len(enrichment_nodes) >= 1,
)


# ------------------------------------------------------------
# 4. Placeholder call must actually execute.
# ------------------------------------------------------------

placeholder_calls = []

for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue

    func = node.func

    if (
        isinstance(func, ast.Name)
        and func.id == "prepare_score_placeholders"
    ):
        placeholder_calls.append(node)

    elif (
        isinstance(func, ast.Attribute)
        and func.attr == "prepare_score_placeholders"
    ):
        placeholder_calls.append(node)

check(
    "prepare_score_placeholders executes",
    len(placeholder_calls) >= 1,
)


# ------------------------------------------------------------
# 5. Placeholder must NOT be unconditional.
#
# At least one placeholder call must be nested inside an If whose
# condition is enrichment-dependent.
# ------------------------------------------------------------

parent = {}

for node in ast.walk(tree):
    for child in ast.iter_child_nodes(node):
        parent[child] = node


def ancestors(node):
    current = parent.get(node)

    while current is not None:
        yield current
        current = parent.get(current)


guarded = False

for call in placeholder_calls:
    for ancestor in ancestors(call):
        if not isinstance(ancestor, ast.If):
            continue

        condition = ast.get_source_segment(
            text,
            ancestor.test,
        ) or ""

        if (
            "enrichment" in condition
            or "args.metrics_input" in condition
            or "args.risk_history" in condition
        ):
            guarded = True
            break

    if guarded:
        break


check(
    "Placeholder execution is enrichment-guarded",
    guarded,
)


# ------------------------------------------------------------
# 6. Existing CLI defaults remain opt-in.
# ------------------------------------------------------------

check(
    "metrics-input CLI remains present",
    "--metrics-input" in text,
)

check(
    "risk-history CLI remains present",
    "--risk-history" in text,
)


# ------------------------------------------------------------
# 7. No B.2K production coupling.
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


print()
print("PASS:", passed)
print("FAIL:", failed)

if failed:
    print(
        "RESULT: EXPECTED TEST-FIRST FAILURE "
        "UNTIL PLACEHOLDER BOUNDARY IS WIRED"
    )
    raise SystemExit(1)

print(
    "RESULT: GENERATOR PLACEHOLDER BOUNDARY APPROVED"
)
raise SystemExit(0)
