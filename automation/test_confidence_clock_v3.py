import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTO = ROOT / "automation"
FIX = AUTO / "fixtures" / "b2k_e2e"

PASS = 0
FAIL = 0


def check(condition, message, actual=None):
    global PASS, FAIL

    if condition:
        PASS += 1
        print(f"PASS | {message}")
    else:
        FAIL += 1
        print(f"FAIL | {message}")
        if actual is not None:
            print(f"       actual={actual!r}")


def load_json(path):
    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


confidence = load_module(
    "confidence_clock_test",
    AUTO / "confidence_engine_v3.py",
)

registry = load_json(
    AUTO / "source_registry_v3.json"
)

quality = load_json(
    AUTO / "data_quality_policy_v3.json"
)

metrics = load_json(
    FIX / "metrics.json"
)

freshness = quality["freshness_hours"]

reference_time = metrics["generated_at"]

technical_source = (
    metrics["assets"][0]["technical"]["source"]
)

retrieved_at = technical_source["retrieved_at"]


print("=" * 72)
print("B.2L.6G.4D.15 — CONFIDENCE CLOCK CONTRACT")
print("=" * 72)


# ------------------------------------------------------------
# 1. Legacy API remains callable
# ------------------------------------------------------------

check(
    callable(confidence.apply_confidence_engine),
    "apply_confidence_engine remains public",
)


# ------------------------------------------------------------
# 2. Reference time must be later than retrieved_at
# ------------------------------------------------------------

retrieved_dt = datetime.fromisoformat(
    retrieved_at.replace("Z", "+00:00")
)

reference_dt = datetime.fromisoformat(
    reference_time.replace("Z", "+00:00")
)

check(
    reference_dt >= retrieved_dt,
    "fixture reference time is not before Technical retrieval",
)

age = (
    reference_dt - retrieved_dt
).total_seconds() / 3600.0

check(
    0 <= age <= freshness["TECHNICAL"],
    "fixture reference time keeps Technical inside freshness window",
    age,
)


# ------------------------------------------------------------
# 3. age_hours must accept optional reference_time
# ------------------------------------------------------------

try:
    frozen_age = confidence.age_hours(
        retrieved_dt,
        reference_time=reference_dt,
    )

    check(
        abs(frozen_age - age) < 1e-9,
        "age_hours honors explicit reference_time",
        frozen_age,
    )

except TypeError as exc:
    check(
        False,
        "age_hours accepts optional reference_time",
        str(exc),
    )


# ------------------------------------------------------------
# 4. freshness_score must propagate reference_time
# ------------------------------------------------------------

provenance = {
    "retrieved_at": retrieved_at
}

try:
    score, _ = confidence.freshness_score(
        provenance,
        "TECHNICAL",
        freshness,
        reference_time=reference_dt,
    )

    check(
        score == 1.0,
        "Technical freshness is 1.0 at frozen fixture time",
        score,
    )

except TypeError as exc:
    check(
        False,
        "freshness_score accepts optional reference_time",
        str(exc),
    )


# ------------------------------------------------------------
# 5. Existing three-argument API must remain valid
# ------------------------------------------------------------

import inspect

signature = inspect.signature(
    confidence.apply_confidence_engine
)

params = signature.parameters

check(
    "reference_time" in params,
    "apply_confidence_engine exposes optional reference_time",
    str(signature),
)

if "reference_time" in params:
    check(
        params["reference_time"].default is None,
        "reference_time defaults to None",
        params["reference_time"].default,
    )


print()
print("=" * 72)
print("RESULT")
print("=" * 72)
print(f"PASS: {PASS}")
print(f"FAIL: {FAIL}")

if FAIL:
    print("RESULT: EXPECTED RED until clock injection is implemented.")
else:
    print("RESULT: APPROVED")
