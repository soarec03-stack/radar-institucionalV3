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
    found = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if (
            isinstance(func, ast.Name)
            and func.id == name
        ):
            found.append(node)

        elif (
            isinstance(func, ast.Attribute)
            and func.attr == name
        ):
            found.append(node)

    return found


print("=" * 72)
print("B.2L.6G.1B ? METRICS LOADER ORCHESTRATION CONTRACT")
print("=" * 72)


# ------------------------------------------------------------
# 1. Production dependency exists.
# ------------------------------------------------------------

check(
    "Generator references METRICS_LOADER_MODULE",
    "METRICS_LOADER_MODULE" in text,
)

check(
    "Generator references metrics_loader_v3",
    "metrics_loader_v3" in text,
)


# ------------------------------------------------------------
# 2. Runtime module loading.
# ------------------------------------------------------------

check(
    "Metrics Loader participates in runtime loading",
    text.count("METRICS_LOADER_MODULE") >= 2,
)

check(
    "Generator resolves merge_metrics",
    "merge_metrics" in text,
)


# ------------------------------------------------------------
# 3. Explicit opt-in guard.
# ------------------------------------------------------------

check(
    "Generator references args.metrics_input",
    "args.metrics_input" in text,
)

metrics_guard = False

for node in ast.walk(tree):
    if not isinstance(node, ast.If):
        continue

    condition = ast.get_source_segment(
        text,
        node.test,
    ) or ""

    if "args.metrics_input" in condition:
        metrics_guard = True
        break

check(
    "Metrics execution has explicit args.metrics_input guard",
    metrics_guard,
)


# ------------------------------------------------------------
# 4. Metrics input must actually be consumed.
# ------------------------------------------------------------

metrics_path_use = (
    "Path(args.metrics_input)" in text
    or "args.metrics_input.read_text" in text
    or "load_json(args.metrics_input)" in text
    or "load_json(Path(args.metrics_input))" in text
)

check(
    "metrics-input is consumed as an input file",
    metrics_path_use,
)


# ------------------------------------------------------------
# 5. merge_metrics must execute.
# ------------------------------------------------------------

merge_calls = calls_named("merge_metrics")

check(
    "merge_metrics executes",
    len(merge_calls) >= 1,
)


# ------------------------------------------------------------
# 6. Return contract must be unpacked:
#    result, changes, warnings.
# ------------------------------------------------------------

three_value_unpack = False

for node in ast.walk(tree):
    if not isinstance(node, ast.Assign):
        continue

    if len(node.targets) != 1:
        continue

    target = node.targets[0]

    if not isinstance(target, ast.Tuple):
        continue

    if len(target.elts) != 3:
        continue

    value = node.value

    if not isinstance(value, ast.Call):
        continue

    func = value.func

    name = None

    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr

    if name == "merge_metrics":
        three_value_unpack = True
        break

check(
    "merge_metrics result/changes/warnings are unpacked",
    three_value_unpack,
)


# ------------------------------------------------------------
# 7. Working data must receive merged result.
# ------------------------------------------------------------

merged_result_used = False

for node in ast.walk(tree):
    if not isinstance(node, ast.Assign):
        continue

    source = ast.get_source_segment(
        text,
        node,
    ) or ""

    if (
        "merge_metrics" in source
        and "data" in source
    ):
        merged_result_used = True
        break

check(
    "Merged result replaces or updates working data",
    merged_result_used,
)


# ------------------------------------------------------------
# 8. changes and warnings must not disappear silently.
# ------------------------------------------------------------

check(
    "Generator has metrics changes handling",
    (
        "metrics_changes" in text
        or "loader_changes" in text
    ),
)

check(
    "Generator has metrics warnings handling",
    (
        "metrics_warnings" in text
        or "loader_warnings" in text
    ),
)


# ------------------------------------------------------------
# 9. Fail-closed file/JSON handling clues.
# ------------------------------------------------------------

check(
    "Generator has metrics input existence handling",
    (
        ".exists()" in text
        and "metrics" in text.lower()
    ),
)

check(
    "Generator has metrics JSON load error handling",
    (
        "JSONDecodeError" in text
        or "json.JSONDecodeError" in text
        or "except" in text
        and "metrics" in text.lower()
    ),
)


# ------------------------------------------------------------
# 10. No test artifact coupling.
# ------------------------------------------------------------

for forbidden in (
    "metrics_real_B2K_v3.json",
    "risk_history_real_B2K_v3.json",
    "automation/fixtures/b2k_e2e",
):
    check(
        f"No production dependency on {forbidden}",
        forbidden not in text,
    )


print()
print("PASS:", passed)
print("FAIL:", failed)

if failed:
    print(
        "RESULT: EXPECTED TEST-FIRST FAILURE "
        "UNTIL METRICS LOADER IS WIRED"
    )
    raise SystemExit(1)

print(
    "RESULT: METRICS LOADER ORCHESTRATION CONTRACT APPROVED"
)
raise SystemExit(0)
