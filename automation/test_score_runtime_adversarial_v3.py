from pathlib import Path
import json
import math
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]

GENERATOR = ROOT / "automation" / "generate_radar_v3.py"

FIXTURE_DIR = (
    ROOT / "automation" / "fixtures" / "b2k_e2e"
)

BASE = FIXTURE_DIR / "radar_base.json"
METRICS = FIXTURE_DIR / "metrics.json"
RISK_HISTORY = FIXTURE_DIR / "risk_history.json"

SCHEMA = ROOT / "automation" / "schema_v3.json"
QUALITY_POLICY = (
    ROOT / "automation" / "data_quality_policy_v3.json"
)
REGISTRY = (
    ROOT / "automation" / "source_registry_v3.json"
)
SIGNAL_POLICY = (
    ROOT / "automation" / "signal_policy_v3.json"
)
SCORE_POLICY = (
    ROOT / "automation" / "score_policy_v3.json"
)
RISK_POLICY = (
    ROOT / "automation" / "risk_policy_v3.json"
)


passes = 0
failures = 0


def check(description, condition, detail=None):
    global passes, failures

    if condition:
        passes += 1
        print(f"PASS - {description}")
    else:
        failures += 1
        print(f"FAIL - {description}")

        if detail is not None:
            print(f"       {detail}")


def load_json(path):
    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )


def build_rebased_metrics_fixture(
    source_path,
    destination_path,
):
    """
    Create a temporary copy of the historical B2K metrics fixture
    whose timestamp topology is shifted to the current UTC clock.

    Financial values and relative timestamp differences are preserved.
    The permanent fixture is never modified.
    """
    data = load_json(source_path)

    generated_at_raw = data.get("generated_at")

    if not isinstance(generated_at_raw, str):
        raise RuntimeError(
            "Metrics fixture requires generated_at "
            "for temporal rebase."
        )

    original_reference = datetime.fromisoformat(
        generated_at_raw.replace("Z", "+00:00")
    )

    if original_reference.tzinfo is None:
        original_reference = original_reference.replace(
            tzinfo=timezone.utc
        )

    current_reference = datetime.now(timezone.utc)

    delta = current_reference - original_reference

    timestamp_keys = {
        "generated_at",
        "retrieved_at",
        "observed_at",
        "as_of",
        "timestamp",
    }

    def shift(value):
        if isinstance(value, dict):
            result = {}

            for key, child in value.items():
                if (
                    key in timestamp_keys
                    and isinstance(child, str)
                ):
                    try:
                        parsed = datetime.fromisoformat(
                            child.replace("Z", "+00:00")
                        )
                    except ValueError:
                        result[key] = child
                        continue

                    if parsed.tzinfo is None:
                        parsed = parsed.replace(
                            tzinfo=timezone.utc
                        )

                    shifted = parsed + delta

                    result[key] = (
                        shifted
                        .astimezone(timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
                else:
                    result[key] = shift(child)

            return result

        if isinstance(value, list):
            return [
                shift(item)
                for item in value
            ]

        return value

    rebased = shift(data)

    destination_path.write_text(
        json.dumps(
            rebased,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return destination_path


def run_generator(
    temp_dir,
    *,
    metrics_input=None,
    risk_history=None,
    score_policy=None,
):
    output = temp_dir / "output.json"
    history = temp_dir / "history"

    command = [
        sys.executable,
        str(GENERATOR),
        "--input",
        str(BASE),
        "--schema",
        str(SCHEMA),
        "--output",
        str(output),
        "--policy",
        str(QUALITY_POLICY),
        "--registry",
        str(REGISTRY),
        "--history-dir",
        str(history),
        "--signal-policy",
        str(SIGNAL_POLICY),
        "--score-policy",
        str(
            score_policy
            if score_policy is not None
            else SCORE_POLICY
        ),
        "--risk-policy",
        str(RISK_POLICY),
        "--allow-quality-critical-in-draft",
    ]

    if metrics_input is not None:
        command.extend(
            [
                "--metrics-input",
                str(metrics_input),
            ]
        )

    if risk_history is not None:
        command.extend(
            [
                "--risk-history",
                str(risk_history),
            ]
        )

    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    return result, output


def assets_by_ticker(data):
    return {
        asset["ticker"]: asset
        for asset in data.get("assets", [])
        if isinstance(asset, dict)
        and isinstance(asset.get("ticker"), str)
    }


def close(actual, expected, tolerance=1e-9):
    if actual is None or expected is None:
        return actual is expected

    try:
        return math.isclose(
            float(actual),
            float(expected),
            rel_tol=tolerance,
            abs_tol=tolerance,
        )
    except (TypeError, ValueError):
        return False


print("=" * 72)
print("B.2L.6G.4D - SCORE RUNTIME ADVERSARIAL")
print("=" * 72)


# ------------------------------------------------------------
# Preconditions
# ------------------------------------------------------------

for path in (
    GENERATOR,
    BASE,
    METRICS,
    RISK_HISTORY,
    SCHEMA,
    QUALITY_POLICY,
    REGISTRY,
    SIGNAL_POLICY,
    SCORE_POLICY,
    RISK_POLICY,
):
    check(
        f"Required file exists: {path.name}",
        path.exists(),
    )


base_data = load_json(BASE)
base_assets = assets_by_ticker(base_data)

check(
    "Base fixture contains exactly VRT/CRSP/ETON",
    set(base_assets) == {"VRT", "CRSP", "ETON"},
)


# ------------------------------------------------------------
# CASE A
# Metrics + Risk: complete B2K production-style enrichment.
# ------------------------------------------------------------

print()
print("CASE A - METRICS + RISK")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    rebased_metrics = build_rebased_metrics_fixture(
        METRICS,
        temp_dir / "metrics_rebased.json",
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=rebased_metrics,
        risk_history=RISK_HISTORY,
    )

    check(
        "A generator exits successfully",
        result.returncode == 0,
        result.stdout + result.stderr,
    )

    check(
        "A output is created",
        output.exists(),
    )

    if output.exists():
        data = load_json(output)
        assets = assets_by_ticker(data)

        check(
            "A output contains VRT/CRSP/ETON",
            set(assets) == {"VRT", "CRSP", "ETON"},
        )

        expected = {
            "VRT": {
                "raw_score": 24.25,
                "available_score": 70.0,
                "normalized_score": 34.64,
                "coverage": 0.70,
                "publishable": False,
                "analytically_usable": True,
                "status": "PARTIAL",
            },
            "CRSP": {
                "raw_score": 15.47,
                "available_score": 50.0,
                "normalized_score": None,
                "coverage": 0.50,
                "publishable": False,
                "analytically_usable": False,
                "status": "INSUFFICIENT_DATA",
            },
            "ETON": {
                "raw_score": 13.89,
                "available_score": 50.0,
                "normalized_score": None,
                "coverage": 0.50,
                "publishable": False,
                "analytically_usable": False,
                "status": "INSUFFICIENT_DATA",
            },
        }

        for ticker, exp in expected.items():
            score = assets[ticker].get("score") or {}

            check(
                f"A {ticker} score has complete V3 fields",
                all(
                    key in score
                    for key in (
                        "status",
                        "raw_score",
                        "available_score",
                        "normalized_score",
                        "coverage",
                        "analytically_usable",
                        "publishable",
                    )
                ),
            )

            for key in (
                "raw_score",
                "available_score",
                "coverage",
            ):
                check(
                    f"A {ticker} {key} matches B2K",
                    close(score.get(key), exp[key]),
                    (
                        f"actual={score.get(key)!r} "
                        f"expected={exp[key]!r}"
                    ),
                )

            check(
                f"A {ticker} normalized_score matches B2K",
                (
                    score.get("normalized_score")
                    is exp["normalized_score"]
                    if exp["normalized_score"] is None
                    else close(
                        score.get("normalized_score"),
                        exp["normalized_score"],
                    )
                ),
                (
                    f"actual={score.get('normalized_score')!r} "
                    f"expected={exp['normalized_score']!r}"
                ),
            )

            for key in (
                "publishable",
                "analytically_usable",
                "status",
            ):
                check(
                    f"A {ticker} {key} matches B2K",
                    score.get(key) == exp[key],
                    (
                        f"actual={score.get(key)!r} "
                        f"expected={exp[key]!r}"
                    ),
                )

            check(
                f"A {ticker} has no operational label",
                "label" not in score,
            )

            old_score = base_assets[ticker].get("score") or {}

            check(
                f"A {ticker} stale base score was replaced",
                (
                    score.get("total")
                    != old_score.get("total")
                    or score.get("raw_score") is not None
                ),
            )


# ------------------------------------------------------------
# CASE B
# Metrics only.
# Score must still execute.
# Risk is optional and must not be required to activate Score.
# ------------------------------------------------------------

print()
print("CASE B - METRICS ONLY")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    rebased_metrics = build_rebased_metrics_fixture(
        METRICS,
        temp_dir / "metrics_rebased.json",
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=rebased_metrics,
    )

    check(
        "B generator exits successfully",
        result.returncode == 0,
        result.stdout + result.stderr,
    )

    check(
        "B output is created",
        output.exists(),
    )

    if output.exists():
        data = load_json(output)
        assets = assets_by_ticker(data)

        for ticker in ("VRT", "CRSP", "ETON"):
            score = assets[ticker].get("score") or {}

            check(
                f"B {ticker} Score Engine executed",
                "raw_score" in score
                and "coverage" in score
                and "status" in score,
            )

            check(
                f"B {ticker} transient placeholder overwritten",
                not (
                    score.get("raw_score") == 0
                    and score.get("available_score") == 0
                    and score.get("coverage") == 0
                    and score.get("status")
                    == "INSUFFICIENT_DATA"
                ),
            )


# ------------------------------------------------------------
# CASE C
# Missing Score Policy must fail closed.
# ------------------------------------------------------------

print()
print("CASE C - MISSING SCORE POLICY")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    missing_policy = (
        temp_dir / "missing_score_policy.json"
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=METRICS,
        score_policy=missing_policy,
    )

    check(
        "C generator fails closed",
        result.returncode != 0,
    )

    check(
        "C output is not created",
        not output.exists(),
    )

    check(
        "C error references Score Policy",
        "Score Policy" in (
            result.stdout + result.stderr
        ),
    )


# ------------------------------------------------------------
# CASE D
# Invalid JSON Score Policy must fail closed.
# ------------------------------------------------------------

print()
print("CASE D - INVALID SCORE POLICY JSON")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    invalid_policy = (
        temp_dir / "invalid_score_policy.json"
    )

    invalid_policy.write_text(
        "{ invalid json",
        encoding="utf-8",
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=METRICS,
        score_policy=invalid_policy,
    )

    check(
        "D generator fails closed",
        result.returncode != 0,
    )

    check(
        "D output is not created",
        not output.exists(),
    )

    check(
        "D error references Score Policy",
        "Score Policy" in (
            result.stdout + result.stderr
        ),
    )


# ------------------------------------------------------------
# CASE E
# Structurally invalid policy root.
# ------------------------------------------------------------

print()
print("CASE E - INVALID SCORE POLICY ROOT")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    invalid_root = (
        temp_dir / "invalid_root.json"
    )

    invalid_root.write_text(
        "[]",
        encoding="utf-8",
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=METRICS,
        score_policy=invalid_root,
    )

    check(
        "E generator fails closed",
        result.returncode != 0,
    )

    check(
        "E output is not created",
        not output.exists(),
    )


# ------------------------------------------------------------
# CASE F
# Policy object without canonical components.
# ------------------------------------------------------------

print()
print("CASE F - SCORE POLICY WITHOUT COMPONENTS")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    invalid_components = (
        temp_dir / "invalid_components.json"
    )

    invalid_components.write_text(
        json.dumps(
            {
                "coverage": {
                    "minimum_for_reliable_score": 0.70,
                    "minimum_for_publication": 0.85,
                }
            }
        ),
        encoding="utf-8",
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=METRICS,
        score_policy=invalid_components,
    )

    check(
        "F generator fails closed",
        result.returncode != 0,
    )

    check(
        "F output is not created",
        not output.exists(),
    )


# ------------------------------------------------------------
# CASE G
# Production generator must remain isolated from B2K artifacts.
# ------------------------------------------------------------

print()
print("CASE G - PRODUCTION ISOLATION")

generator_source = GENERATOR.read_text(
    encoding="utf-8-sig"
)

check(
    "G no hardcoded B2K metrics artifact",
    "metrics_real_B2K_v3.json"
    not in generator_source,
)

check(
    "G no hardcoded B2K risk artifact",
    "risk_history_real_B2K_v3.json"
    not in generator_source,
)

check(
    "G no hardcoded B2K fixture directory",
    "fixtures/b2k_e2e"
    not in generator_source.replace("\\", "/"),
)


print()
print("=" * 72)
print("RESULT")
print("=" * 72)
print("PASS:", passes)
print("FAIL:", failures)

if failures:
    print(
        "RESULT: SCORE RUNTIME ADVERSARIAL FAILED"
    )
    raise SystemExit(1)

print(
    "RESULT: SCORE RUNTIME ADVERSARIAL APPROVED"
)
raise SystemExit(0)
