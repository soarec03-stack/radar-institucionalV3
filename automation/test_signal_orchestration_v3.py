from pathlib import Path
import ast


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

        if isinstance(func, ast.Name) and func.id == name:
            found.append(node)

        elif (
            isinstance(func, ast.Attribute)
            and func.attr == name
        ):
            found.append(node)

    return found


print("=" * 72)
print(
    "B.2L.6G.2B - SIGNAL ENGINE "
    "ORCHESTRATION CONTRACT"
)
print("=" * 72)


# 1. Production dependency.

check(
    "Generator references SIGNAL_ENGINE_MODULE",
    "SIGNAL_ENGINE_MODULE" in text,
)

check(
    "Generator references signal_engine_v3",
    "signal_engine_v3" in text,
)


# 2. Runtime loading.

check(
    "Signal Engine participates in runtime loading",
    text.count("SIGNAL_ENGINE_MODULE") >= 2,
)

check(
    "Generator resolves apply_signal_engine",
    "apply_signal_engine" in text,
)


# 3. Policy consumption.

check(
    "Generator references args.signal_policy",
    "args.signal_policy" in text,
)

signal_policy_path_use = (
    (
        "signal_policy_path = Path(" in text
        and "args.signal_policy" in text
    )
    or "Path(args.signal_policy)" in text
    or "load_json(args.signal_policy)" in text
    or "load_json(Path(args.signal_policy))" in text
)

check(
    "signal-policy is consumed as an input file",
    signal_policy_path_use,
)


# 4. Fail-closed policy handling.

check(
    "Generator has Signal Policy existence handling",
    "signal_policy_path.exists()" in text,
)

check(
    "Generator has Signal Policy JSON error handling",
    (
        "JSONDecodeError" in text
        and "signal_policy" in text
    ),
)


# 5. Canonical policy structure.

check(
    "Generator validates Signal Policy principles",
    (
        '"principles"' in text
        or "'principles'" in text
    ),
)

check(
    "Generator validates Signal Policy domains",
    (
        '"domains"' in text
        or "'domains'" in text
    ),
)


# 6. Engine execution.

signal_calls = calls_named(
    "apply_signal_engine"
)

check(
    "apply_signal_engine executes",
    len(signal_calls) >= 1,
)


# 7. Return contract: data, signal_changes.

two_value_unpack = False

for node in ast.walk(tree):
    if not isinstance(node, ast.Assign):
        continue

    if len(node.targets) != 1:
        continue

    target = node.targets[0]

    if not isinstance(target, ast.Tuple):
        continue

    if len(target.elts) != 2:
        continue

    value = node.value

    if not isinstance(value, ast.Call):
        continue

    func = value.func

    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    else:
        name = None

    if name != "apply_signal_engine":
        continue

    names = [
        elt.id
        for elt in target.elts
        if isinstance(elt, ast.Name)
    ]

    if (
        len(names) == 2
        and names[0] == "data"
        and "signal" in names[1].lower()
    ):
        two_value_unpack = True
        break


check(
    "Signal result and changes are unpacked",
    two_value_unpack,
)

check(
    "Generator has signal changes handling",
    "signal_changes" in text,
)


# 8. Ordering:
# Confidence -> Signal -> Data Quality.
#
# Locate the Data Quality section AFTER the confidence section,
# because the generator contains an earlier helper-level marker.

confidence_position = text.find(
    'print("\\n[CONFIDENCE ENGINE]")'
)

signal_position = text.find(
    "apply_signal_engine("
)

data_quality_position = text.find(
    "data_quality.evaluate(data, policy)",
    confidence_position + 1
)


check(
    "Signal executes after Confidence Engine",
    (
        confidence_position >= 0
        and signal_position > confidence_position
    ),
)

check(
    "Signal executes before Data Quality evaluation",
    (
        signal_position >= 0
        and data_quality_position >= 0
        and signal_position < data_quality_position
    ),
)


# 9. Policy reaches engine.

policy_passed_to_engine = False

for call in signal_calls:
    source = ast.get_source_segment(
        text,
        call,
    ) or ""

    if (
        "data" in source
        and "signal_policy" in source
    ):
        policy_passed_to_engine = True
        break


check(
    "Loaded Signal Policy is passed to engine",
    policy_passed_to_engine,
)


# 11. No B.2K production coupling.

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
        "UNTIL SIGNAL ENGINE IS WIRED"
    )
    raise SystemExit(1)

print(
    "RESULT: SIGNAL ENGINE "
    "ORCHESTRATION CONTRACT APPROVED"
)

raise SystemExit(0)
