import copy
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


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
PUBLICATION_POLICY = (
    ROOT
    / "automation"
    / "publication_eligibility_policy_v3.json"
)


passes = 0
failures = 0


def check(name, condition, detail=""):
    global passes, failures

    if condition:
        passes += 1
        print(f"PASS - {name}")
    else:
        failures += 1
        print(f"FAIL - {name}")
        if detail:
            print(detail)


def load_json(path):
    return json.loads(
        Path(path).read_text(encoding="utf-8-sig")
    )


def shift_timestamp(value, delta):
    if not isinstance(value, str):
        return value

    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return value

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    shifted = dt + delta

    return (
        shifted.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def rebase_timestamps(value, delta):
    if isinstance(value, dict):
        result = {}

        for key, item in value.items():
            if (
                isinstance(item, str)
                and (
                    key == "generated_at"
                    or key == "timestamp"
                    or key.endswith("_at")
                )
            ):
                result[key] = shift_timestamp(
                    item,
                    delta,
                )
            else:
                result[key] = rebase_timestamps(
                    item,
                    delta,
                )

        return result

    if isinstance(value, list):
        return [
            rebase_timestamps(item, delta)
            for item in value
        ]

    return value


def build_rebased_metrics_fixture(
    source_path,
    destination_path,
):
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
        original_reference = (
            original_reference.replace(
                tzinfo=timezone.utc
            )
        )

    current_reference = datetime.now(
        timezone.utc
    )

    delta = (
        current_reference
        - original_reference
    )

    rebased = rebase_timestamps(
        data,
        delta,
    )

    destination_path.write_text(
        json.dumps(
            rebased,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return destination_path


def run_generator(
    temp_dir,
    *,
    metrics_input,
    risk_history=None,
    publication_policy=None,
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
        str(SCORE_POLICY),
        "--risk-policy",
        str(RISK_POLICY),
        "--publication-policy",
        str(
            publication_policy
            if publication_policy is not None
            else PUBLICATION_POLICY
        ),
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


def combined_output(result):
    return (
        (result.stdout or "")
        + (result.stderr or "")
    )


print("=" * 72)
print("PUBLICATION ELIGIBILITY RUNTIME ADVERSARIAL V3")
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
    PUBLICATION_POLICY,
):
    check(
        f"Required file exists: {path.name}",
        path.exists(),
    )


# ------------------------------------------------------------
# CASE A
# Official policy + Metrics.
# Publication must execute successfully in the real Generator.
# ------------------------------------------------------------

print()
print("CASE A - OFFICIAL PUBLICATION POLICY")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    rebased_metrics = (
        build_rebased_metrics_fixture(
            METRICS,
            temp_dir / "metrics_rebased.json",
        )
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=rebased_metrics,
    )

    runtime_text = combined_output(result)

    check(
        "A generator exits successfully",
        result.returncode == 0,
        runtime_text,
    )

    check(
        "A output is created",
        output.exists(),
        runtime_text,
    )

    check(
        "A Publication runtime stage executed",
        "PUBLICATION ELIGIBILITY"
        in runtime_text.upper(),
        runtime_text,
    )

    if output.exists():
        data = load_json(output)

        assets = data.get("assets")

        check(
            "A output contains assets",
            isinstance(assets, list)
            and len(assets) > 0,
        )

        check(
            "A output remains schema-shaped object",
            isinstance(data, dict)
            and data.get("schema_version")
            == "3.0",
        )


# ------------------------------------------------------------
# CASE B
# Missing Publication Policy.
# Must fail closed and must not create output.
# ------------------------------------------------------------

print()
print("CASE B - MISSING PUBLICATION POLICY")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    missing_policy = (
        temp_dir
        / "missing_publication_policy.json"
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=METRICS,
        publication_policy=missing_policy,
    )

    runtime_text = combined_output(result)

    check(
        "B generator fails closed",
        result.returncode != 0,
        runtime_text,
    )

    check(
        "B output is not created",
        not output.exists(),
        runtime_text,
    )

    check(
        "B error references Publication Eligibility Policy",
        (
            "Publication Eligibility Policy"
            in runtime_text
            or "publication"
            in runtime_text.lower()
        ),
        runtime_text,
    )


# ------------------------------------------------------------
# CASE C
# Invalid JSON.
# ------------------------------------------------------------

print()
print("CASE C - INVALID PUBLICATION POLICY JSON")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    invalid_policy = (
        temp_dir
        / "invalid_publication_policy.json"
    )

    invalid_policy.write_text(
        "{ invalid json",
        encoding="utf-8",
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=METRICS,
        publication_policy=invalid_policy,
    )

    runtime_text = combined_output(result)

    check(
        "C generator fails closed",
        result.returncode != 0,
        runtime_text,
    )

    check(
        "C output is not created",
        not output.exists(),
        runtime_text,
    )

    check(
        "C error references Publication Eligibility Policy",
        (
            "Publication Eligibility Policy"
            in runtime_text
            or "publication"
            in runtime_text.lower()
        ),
        runtime_text,
    )


# ------------------------------------------------------------
# CASE D
# Invalid root type.
# ------------------------------------------------------------

print()
print("CASE D - INVALID PUBLICATION POLICY ROOT")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    invalid_root = (
        temp_dir
        / "invalid_publication_root.json"
    )

    invalid_root.write_text(
        "[]",
        encoding="utf-8",
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=METRICS,
        publication_policy=invalid_root,
    )

    runtime_text = combined_output(result)

    check(
        "D generator fails closed",
        result.returncode != 0,
        runtime_text,
    )

    check(
        "D output is not created",
        not output.exists(),
        runtime_text,
    )

    check(
        "D error identifies invalid root",
        (
            "objeto JSON"
            in runtime_text
            or "root"
            in runtime_text.lower()
            or "publication"
            in runtime_text.lower()
        ),
        runtime_text,
    )


# ------------------------------------------------------------
# CASE E
# Missing canonical required section.
# ------------------------------------------------------------

print()
print("CASE E - MISSING REQUIRED PUBLICATION SECTION")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    policy = copy.deepcopy(
        load_json(PUBLICATION_POLICY)
    )

    removed = policy.pop(
        "publication_use_policy",
        None,
    )

    check(
        "E fixture removed publication_use_policy",
        removed is not None,
    )

    incomplete_policy = (
        temp_dir
        / "incomplete_publication_policy.json"
    )

    incomplete_policy.write_text(
        json.dumps(
            policy,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=METRICS,
        publication_policy=incomplete_policy,
    )

    runtime_text = combined_output(result)

    check(
        "E generator fails closed",
        result.returncode != 0,
        runtime_text,
    )

    check(
        "E output is not created",
        not output.exists(),
        runtime_text,
    )

    check(
        "E error identifies missing section",
        (
            "publication_use_policy"
            in runtime_text
            or "bloco obrigatorio"
            in runtime_text.lower()
        ),
        runtime_text,
    )


# ------------------------------------------------------------
# CASE F
# Metrics + Risk.
# Risk fixture is RESEARCH_ONLY.
# Runtime must execute Publication without promoting eligibility.
# ------------------------------------------------------------

print()
print("CASE F - METRICS + RESEARCH_ONLY RISK")

with tempfile.TemporaryDirectory() as tmp:
    temp_dir = Path(tmp)

    rebased_metrics = (
        build_rebased_metrics_fixture(
            METRICS,
            temp_dir / "metrics_rebased.json",
        )
    )

    result, output = run_generator(
        temp_dir,
        metrics_input=rebased_metrics,
        risk_history=RISK_HISTORY,
    )

    runtime_text = combined_output(result)

    check(
        "F generator exits successfully",
        result.returncode == 0,
        runtime_text,
    )

    check(
        "F output is created",
        output.exists(),
        runtime_text,
    )

    check(
        "F Publication runtime stage executed",
        "PUBLICATION ELIGIBILITY"
        in runtime_text.upper(),
        runtime_text,
    )

    if output.exists():
        data = load_json(output)
        assets = data.get("assets") or []

        check(
            "F output contains assets",
            isinstance(assets, list)
            and len(assets) > 0,
        )

        score_objects = [
            asset.get("score") or {}
            for asset in assets
            if isinstance(asset, dict)
        ]

        check(
            "F score objects remain present",
            bool(score_objects)
            and all(
                isinstance(score, dict)
                for score in score_objects
            ),
        )

        check(
            "F Publication does not promote publishable score",
            all(
                score.get("publishable")
                is not True
                for score in score_objects
            ),
        )


# ------------------------------------------------------------
# CASE G
# Production isolation.
# Generator must not know B2K fixture filenames/directories.
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
        "RESULT: PUBLICATION RUNTIME ADVERSARIAL FAILED"
    )
    raise SystemExit(1)

print(
    "RESULT: PUBLICATION RUNTIME ADVERSARIAL APPROVED"
)
