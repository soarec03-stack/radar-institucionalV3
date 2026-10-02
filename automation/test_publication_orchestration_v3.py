from pathlib import Path
import ast
import sys


BASE_DIR = Path(__file__).resolve().parents[1]

GENERATOR = BASE_DIR / "automation" / "generate_radar_v3.py"
ENGINE = BASE_DIR / "automation" / "publication_eligibility_v3.py"
POLICY = BASE_DIR / "automation" / "publication_eligibility_policy_v3.json"


passed = 0
failed = 0


def check(name, condition):
    global passed, failed

    if condition:
        passed += 1
        print(f"PASS - {name}")
    else:
        failed += 1
        print(f"FAIL - {name}")


print("=" * 72)
print("B.2L.6G.5B - PUBLICATION ELIGIBILITY ORCHESTRATION CONTRACT")
print("=" * 72)

check("Generator exists", GENERATOR.exists())
check("Publication Eligibility Engine exists", ENGINE.exists())
check("Publication Eligibility Policy exists", POLICY.exists())

text = GENERATOR.read_text(encoding="utf-8-sig")

try:
    tree = ast.parse(text)
    syntax_ok = True
except SyntaxError:
    syntax_ok = False
    tree = None

check("Generator has valid Python syntax", syntax_ok)

check(
    "Generator references PUBLICATION_ELIGIBILITY_MODULE",
    "PUBLICATION_ELIGIBILITY_MODULE" in text,
)

check(
    "Generator references publication_eligibility_v3",
    "publication_eligibility_v3.py" in text,
)

check(
    "Generator exposes --publication-policy",
    '"--publication-policy"' in text,
)

check(
    "Generator consumes args.publication_policy",
    "args.publication_policy" in text,
)

check(
    "Publication Eligibility participates in runtime loading",
    (
        "PUBLICATION_ELIGIBILITY_MODULE" in text
        and text.count("PUBLICATION_ELIGIBILITY_MODULE") >= 2
        and "load_module(" in text
    ),
)

check(
    "Generator resolves apply_publication_eligibility",
    (
        "apply_publication_eligibility = getattr(" in text
        or "apply_publication_eligibility =" in text
    ),
)

check(
    "apply_publication_eligibility executes",
    "apply_publication_eligibility(" in text,
)

check(
    "Publication result and changes are unpacked",
    (
        "publication_result" in text
        or "publication_changes" in text
    ),
)

check(
    "Risk sidecar is passed to Publication Eligibility",
    "risk_source_context_by_ticker" in text
    and "apply_publication_eligibility(" in text,
)

score_position = text.find("write_score_to_asset(")
publication_position = text.find("apply_publication_eligibility(")
post_schema_position = text.find(
    "post_schema_errors = validator.validate_schema"
)

check(
    "Publication Eligibility executes after Score writer",
    (
        score_position >= 0
        and publication_position >= 0
        and publication_position > score_position
    ),
)

check(
    "Publication Eligibility executes before post-schema validation",
    (
        publication_position >= 0
        and post_schema_position >= 0
        and publication_position < post_schema_position
    ),
)

check(
    "Publication Eligibility receives data",
    (
        publication_position >= 0
        and "data" in text[
            publication_position:
            publication_position + 500
        ]
    ),
)

check(
    "Publication Eligibility receives registry",
    (
        publication_position >= 0
        and "registry" in text[
            publication_position:
            publication_position + 500
        ]
    ),
)

check(
    "Publication Eligibility receives loaded policy",
    (
        publication_position >= 0
        and "publication_policy" in text[
            publication_position:
            publication_position + 500
        ]
    ),
)

check(
    "Publication Eligibility receives Risk sidecar",
    (
        publication_position >= 0
        and "risk_source_context_by_ticker" in text[
            publication_position:
            publication_position + 700
        ]
    ),
)

check(
    "No production dependency on B2K metrics artifact",
    "metrics_real_B2K_v3.json" not in text,
)

check(
    "No production dependency on B2K risk artifact",
    "risk_history_real_B2K_v3.json" not in text,
)

check(
    "No production dependency on B2K fixture directory",
    "fixtures/b2k_e2e" not in text
    and "fixtures\\b2k_e2e" not in text,
)


print()
print("=" * 72)
print("RESULT")
print("=" * 72)
print(f"PASS: {passed}")
print(f"FAIL: {failed}")

if failed:
    print(
        "RESULT: EXPECTED RED UNTIL PUBLICATION "
        "ELIGIBILITY RUNTIME WIRING"
    )
    sys.exit(1)

print(
    "RESULT: PUBLICATION ELIGIBILITY "
    "ORCHESTRATION CONTRACT APPROVED"
)
