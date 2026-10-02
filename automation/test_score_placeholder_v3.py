import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

try:
    from score_placeholder_v3 import (
        prepare_score_placeholders,
        build_score_placeholder,
        is_complete_v3_score,
    )
    IMPORT_OK = True
    IMPORT_ERROR = None
except Exception as exc:
    IMPORT_OK = False
    IMPORT_ERROR = exc


ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / "automation"

input_path = ROOT / "input" / "radar_input_v3.txt"
schema_path = AUTO / "schema_v3.json"

data = json.loads(
    input_path.read_text(encoding="utf-8-sig")
)

schema = json.loads(
    schema_path.read_text(encoding="utf-8-sig")
)

validator = Draft202012Validator(schema)

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
print("B.2L.6F.3A ? SCORE PLACEHOLDER CONTRACT")
print("=" * 72)

check(
    "score_placeholder_v3 imports",
    IMPORT_OK,
)

if not IMPORT_OK:
    print("Import error:", repr(IMPORT_ERROR))
    print()
    print("PASS:", passed)
    print("FAIL:", failed)
    print(
        "RESULT: EXPECTED TEST-FIRST FAILURE "
        "UNTIL SCORE PLACEHOLDER MODULE EXISTS"
    )
    raise SystemExit(1)


# ------------------------------------------------------------
# Placeholder construction
# ------------------------------------------------------------

placeholder = build_score_placeholder()

check(
    "Placeholder status is INSUFFICIENT_DATA",
    placeholder.get("status")
    == "INSUFFICIENT_DATA",
)

check(
    "Placeholder normalized_score is null",
    placeholder.get("normalized_score") is None,
)

check(
    "Placeholder coverage is zero",
    placeholder.get("coverage") == 0,
)

check(
    "Placeholder analytically_usable is false",
    placeholder.get("analytically_usable") is False,
)

check(
    "Placeholder publishable is false",
    placeholder.get("publishable") is False,
)

check(
    "Placeholder has no label",
    "label" not in placeholder,
)

for component in (
    "total",
    "fundamental",
    "technical",
    "momentum",
    "institutional_flow",
    "catalysts",
    "macro",
    "risk",
    "raw_score",
    "available_score",
):
    check(
        f"Placeholder {component} is zero",
        placeholder.get(component) == 0,
    )


# ------------------------------------------------------------
# Existing legacy score must be recognized as incomplete.
# ------------------------------------------------------------

for asset in data.get("assets", []):
    ticker = asset.get("ticker")
    score = asset.get("score")

    check(
        f"{ticker} current input score is incomplete V3",
        not is_complete_v3_score(score),
    )


# ------------------------------------------------------------
# Preparation must not mutate caller input.
# ------------------------------------------------------------

original = copy.deepcopy(data)

working = prepare_score_placeholders(data)

check(
    "prepare_score_placeholders returns new root object",
    working is not data,
)

check(
    "Original input object remains unchanged",
    data == original,
)


# ------------------------------------------------------------
# Current legacy scores must become conservative placeholders.
# ------------------------------------------------------------

for asset in working.get("assets", []):
    ticker = asset.get("ticker")
    score = asset.get("score", {})

    check(
        f"{ticker} prepared score is complete V3",
        is_complete_v3_score(score),
    )

    check(
        f"{ticker} prepared status is INSUFFICIENT_DATA",
        score.get("status")
        == "INSUFFICIENT_DATA",
    )

    check(
        f"{ticker} prepared publishable is false",
        score.get("publishable") is False,
    )

    check(
        f"{ticker} prepared has no label",
        "label" not in score,
    )


# ------------------------------------------------------------
# Working copy must pass the complete official Schema V3.
# ------------------------------------------------------------

errors = list(
    validator.iter_errors(working)
)

check(
    "Prepared working copy passes full Schema V3",
    len(errors) == 0,
)

if errors:
    for error in errors:
        path = ".".join(
            str(part)
            for part in error.absolute_path
        )

        print(
            "SCHEMA ERROR:",
            path or "<root>",
            error.message,
        )


# ------------------------------------------------------------
# A valid complete V3 score must NOT be destroyed by boundary.
# ------------------------------------------------------------

complete_score = build_score_placeholder()
complete_score["raw_score"] = 12.34
complete_score["available_score"] = 50
complete_score["normalized_score"] = None
complete_score["coverage"] = 0.5
complete_score["status"] = "INSUFFICIENT_DATA"

synthetic = copy.deepcopy(working)

synthetic["assets"][0]["score"] = copy.deepcopy(
    complete_score
)

before = copy.deepcopy(
    synthetic["assets"][0]["score"]
)

after = prepare_score_placeholders(
    synthetic
)

check(
    "Complete V3 score is recognized as complete",
    is_complete_v3_score(complete_score),
)

check(
    "Complete V3 score is preserved exactly",
    after["assets"][0]["score"] == before,
)


# ------------------------------------------------------------
# Missing score must receive placeholder because score is
# required by Schema V3.
# ------------------------------------------------------------

missing = copy.deepcopy(working)
missing["assets"][0].pop("score", None)

prepared_missing = prepare_score_placeholders(
    missing
)

check(
    "Missing score receives complete placeholder",
    is_complete_v3_score(
        prepared_missing["assets"][0].get("score")
    ),
)


print()
print("PASS:", passed)
print("FAIL:", failed)

if failed:
    print(
        "RESULT: SCORE PLACEHOLDER CONTRACT FAILED"
    )
    raise SystemExit(1)

print(
    "RESULT: SCORE PLACEHOLDER CONTRACT APPROVED"
)
raise SystemExit(0)
