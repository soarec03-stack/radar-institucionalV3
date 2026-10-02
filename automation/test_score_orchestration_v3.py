from pathlib import Path
import ast
import sys


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "automation" / "generate_radar_v3.py"

passes = 0
failures = 0


def check(description, condition):
    global passes, failures

    if condition:
        passes += 1
        print(f"PASS - {description}")
    else:
        failures += 1
        print(f"FAIL - {description}")


print("=" * 72)
print("B.2L.6G.4B - SCORE ENGINE ORCHESTRATION CONTRACT")
print("=" * 72)

check(
    "Generator exists",
    GENERATOR.exists(),
)

if not GENERATOR.exists():
    print()
    print("PASS:", passes)
    print("FAIL:", failures)
    sys.exit(1)


source = GENERATOR.read_text(
    encoding="utf-8-sig"
)

try:
    tree = ast.parse(source)
    syntax_ok = True
except SyntaxError:
    tree = None
    syntax_ok = False

check(
    "Generator has valid Python syntax",
    syntax_ok,
)

if tree is None:
    print()
    print("PASS:", passes)
    print("FAIL:", failures)
    sys.exit(1)


# ------------------------------------------------------------
# Static references
# ------------------------------------------------------------

check(
    "Generator references SCORE_ENGINE_MODULE",
    "SCORE_ENGINE_MODULE" in source,
)

check(
    "Generator references score_engine_v3",
    "score_engine_v3.py" in source,
)

check(
    "Generator references args.score_policy",
    "args.score_policy" in source,
)

check(
    "Generator exposes --score-policy",
    '"--score-policy"' in source
    or "'--score-policy'" in source,
)


# ------------------------------------------------------------
# AST helpers
# ------------------------------------------------------------

calls = []

for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        name = None

        if isinstance(node.func, ast.Name):
            name = node.func.id

        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr

        if name:
            calls.append(
                (
                    name,
                    getattr(node, "lineno", None),
                    node,
                )
            )


def call_lines(name):
    return [
        line
        for call_name, line, _ in calls
        if call_name == name
        and line is not None
    ]


def first_call_line(name):
    lines = call_lines(name)

    if not lines:
        return None

    return min(lines)


# ------------------------------------------------------------
# Runtime module loading
# ------------------------------------------------------------

score_module_runtime = False

for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue

    segment = ast.get_source_segment(
        source,
        node,
    )

    if not segment:
        continue

    if "SCORE_ENGINE_MODULE" in segment:
        score_module_runtime = True
        break

check(
    "Score Engine participates in runtime loading",
    score_module_runtime,
)


# ------------------------------------------------------------
# Score Policy runtime consumption
# ------------------------------------------------------------

score_policy_consumed = False

for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue

    segment = ast.get_source_segment(
        source,
        node,
    )

    if not segment:
        continue

    if "args.score_policy" in segment:
        score_policy_consumed = True
        break

check(
    "score-policy is consumed as runtime input",
    score_policy_consumed,
)


# ------------------------------------------------------------
# Engine execution
# ------------------------------------------------------------

calculate_lines = call_lines(
    "calculate_asset_score"
)

write_lines = call_lines(
    "write_score_to_asset"
)

check(
    "calculate_asset_score executes",
    bool(calculate_lines),
)

check(
    "write_score_to_asset executes",
    bool(write_lines),
)


# ------------------------------------------------------------
# Ordering
# ------------------------------------------------------------

signal_line = first_call_line(
    "apply_signal_engine"
)

risk_prepare_line = first_call_line(
    "prepare_risk_history"
)

risk_write_line = first_call_line(
    "write_risk_to_asset"
)

score_line = first_call_line(
    "calculate_asset_score"
)

score_write_line = first_call_line(
    "write_score_to_asset"
)

publication_line = first_call_line(
    "apply_publication_eligibility"
)


check(
    "Score executes after Signal Engine",
    signal_line is not None
    and score_line is not None
    and score_line > signal_line,
)

check(
    "Score executes after Risk writer when Risk is wired",
    risk_write_line is not None
    and score_line is not None
    and score_line > risk_write_line,
)

check(
    "Score writer executes after Score calculation",
    score_line is not None
    and score_write_line is not None
    and score_write_line > score_line,
)

check(
    "Publication Eligibility remains later than Score",
    (
        publication_line is None
        or (
            score_write_line is not None
            and publication_line > score_write_line
        )
    ),
)


# ------------------------------------------------------------
# Asset-level semantics
# ------------------------------------------------------------

score_uses_asset = False
score_uses_policy = False
writer_uses_asset = False
writer_uses_result = False

for call_name, _, node in calls:

    if call_name == "calculate_asset_score":
        segment = ast.get_source_segment(
            source,
            node,
        ) or ""

        if "asset" in segment:
            score_uses_asset = True

        if "score_policy" in segment:
            score_uses_policy = True

    if call_name == "write_score_to_asset":
        segment = ast.get_source_segment(
            source,
            node,
        ) or ""

        if "asset" in segment:
            writer_uses_asset = True

        if (
            "result" in segment
            or "score_result" in segment
        ):
            writer_uses_result = True


check(
    "Score calculation receives asset",
    score_uses_asset,
)

check(
    "Score calculation receives loaded Score Policy",
    score_uses_policy,
)

check(
    "Score writer receives asset",
    writer_uses_asset,
)

check(
    "Score writer receives calculated result",
    writer_uses_result,
)


# ------------------------------------------------------------
# Production isolation
# ------------------------------------------------------------

check(
    "No production dependency on B2K metrics artifact",
    "metrics_real_B2K_v3.json" not in source,
)

check(
    "No production dependency on B2K risk artifact",
    "risk_history_real_B2K_v3.json" not in source,
)

check(
    "No production dependency on B2K fixture directory",
    "fixtures/b2k_e2e" not in source.replace("\\", "/"),
)


# ------------------------------------------------------------
# Protected semantics
# ------------------------------------------------------------

check(
    "Score is not guarded exclusively by args.risk_history",
    not (
        score_line is not None
        and "if args.risk_history" in "\n".join(
            source.splitlines()[
                max(0, score_line - 15):
                score_line
            ]
        )
    ),
)


print()
print("=" * 72)
print("RESULT")
print("=" * 72)

print("PASS:", passes)
print("FAIL:", failures)

if failures:
    print(
        "RESULT: EXPECTED RED UNTIL SCORE RUNTIME WIRING IS IMPLEMENTED"
    )
    sys.exit(1)

print(
    "RESULT: SCORE ENGINE ORCHESTRATION CONTRACT APPROVED"
)
sys.exit(0)
