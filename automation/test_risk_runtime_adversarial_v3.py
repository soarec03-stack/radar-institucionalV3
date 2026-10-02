import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AUTOMATION = ROOT / "automation"

GENERATOR = AUTOMATION / "generate_radar_v3.py"

BASE_INPUT = (
    AUTOMATION
    / "fixtures"
    / "b2k_e2e"
    / "radar_base.json"
)

RISK_FIXTURE = (
    AUTOMATION
    / "fixtures"
    / "b2k_e2e"
    / "risk_history.json"
)

TEMP = AUTOMATION / "temp_b2l6g3d2"

SCHEMA = AUTOMATION / "schema_v3.json"
QUALITY_POLICY = (
    AUTOMATION / "data_quality_policy_v3.json"
)
REGISTRY = (
    AUTOMATION / "source_registry_v3.json"
)
SIGNAL_POLICY = (
    AUTOMATION / "signal_policy_v3.json"
)
RISK_POLICY = (
    AUTOMATION / "risk_policy_v3.json"
)


PASS_COUNT = 0
FAIL_COUNT = 0


def check(name, condition, detail=None):
    global PASS_COUNT, FAIL_COUNT

    if condition:
        PASS_COUNT += 1
        print(f"PASS - {name}")
        return

    FAIL_COUNT += 1
    print(f"FAIL - {name}")

    if detail is not None:
        print(f"       {detail}")


def load_json(path):
    return json.loads(
        Path(path).read_text(
            encoding="utf-8-sig"
        )
    )


def write_json(path, data):
    Path(path).write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def run_generator(
    input_path,
    output_path,
    risk_history=None,
    risk_policy=RISK_POLICY,
):
    command = [
        sys.executable,
        str(GENERATOR),
        "--input",
        str(input_path),
        "--schema",
        str(SCHEMA),
        "--output",
        str(output_path),
        "--policy",
        str(QUALITY_POLICY),
        "--registry",
        str(REGISTRY),
        "--signal-policy",
        str(SIGNAL_POLICY),
        "--history-dir",
        str(TEMP / "history"),
        "--allow-quality-critical-in-draft",
    ]

    if risk_history is not None:
        command.extend(
            [
                "--risk-history",
                str(risk_history),
                "--risk-policy",
                str(risk_policy),
            ]
        )

    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def combined_output(result):
    return (
        (result.stdout or "")
        + "\n"
        + (result.stderr or "")
    )


def assets_by_ticker(data):
    return {
        asset.get("ticker"): asset
        for asset in data.get("assets", [])
        if isinstance(asset, dict)
    }


print("=" * 72)
print("B.2L.6G.3D.2 - RISK RUNTIME ADVERSARIAL")
print("=" * 72)


# ------------------------------------------------------------
# Environment
# ------------------------------------------------------------

if TEMP.exists():
    shutil.rmtree(TEMP)

TEMP.mkdir(
    parents=True,
    exist_ok=True,
)

check(
    "Base fixture exists",
    BASE_INPUT.exists(),
)

check(
    "Risk fixture exists",
    RISK_FIXTURE.exists(),
)

check(
    "Generator exists",
    GENERATOR.exists(),
)


base = load_json(BASE_INPUT)
risk_fixture = load_json(RISK_FIXTURE)

base_assets = assets_by_ticker(base)

original_risk = {
    ticker: copy.deepcopy(
        asset.get("risk")
    )
    for ticker, asset in base_assets.items()
}


# ------------------------------------------------------------
# CASE A
# Canonical valid runtime
# ------------------------------------------------------------

print()
print("CASE A - VALID RISK HISTORY")

case_a_output = TEMP / "case_a.json"

case_a = run_generator(
    BASE_INPUT,
    case_a_output,
    RISK_FIXTURE,
)

case_a_text = combined_output(case_a)

check(
    "A1 generator exits zero",
    case_a.returncode == 0,
    case_a_text,
)

check(
    "A2 Risk Pipeline executed",
    "[RISK PIPELINE]" in case_a_text,
    case_a_text,
)

check(
    "A3 output created",
    case_a_output.exists(),
)

if case_a_output.exists():
    case_a_data = load_json(case_a_output)
    case_a_assets = assets_by_ticker(
        case_a_data
    )

    for ticker in ("VRT", "CRSP", "ETON"):
        asset = case_a_assets.get(ticker, {})
        risk = asset.get("risk")

        check(
            f"A4 {ticker} has runtime risk",
            isinstance(risk, dict),
        )

        check(
            f"A5 {ticker} risk replaced stale input",
            risk != original_risk.get(ticker),
            {
                "before": original_risk.get(ticker),
                "after": risk,
            },
        )

        check(
            f"A6 {ticker} risk has score",
            isinstance(
                (risk or {}).get("score"),
                (int, float),
            )
            and not isinstance(
                (risk or {}).get("score"),
                bool,
            ),
        )

        check(
            f"A7 {ticker} risk has level",
            isinstance(
                (risk or {}).get("level"),
                str,
            ),
        )

        check(
            f"A8 {ticker} risk has drivers",
            isinstance(
                (risk or {}).get("drivers"),
                list,
            ),
        )

        check(
            f"A9 {ticker} public risk has no provenance",
            isinstance(risk, dict)
            and "provenance" not in risk
            and "source" not in risk
            and "market_date" not in risk
            and "retrieved_at" not in risk
            and "publication_use" not in risk,
        )

    serialized = json.dumps(
        case_a_data,
        ensure_ascii=False,
    )

    check(
        "A10 sidecar name is not serialized",
        "risk_source_context_by_ticker"
        not in serialized,
    )


# ------------------------------------------------------------
# CASE B
# Risk remains opt-in
# ------------------------------------------------------------

print()
print("CASE B - ENRICHMENT WITHOUT --risk-history")

case_b_output = TEMP / "case_b.json"
case_b_metrics = TEMP / "case_b_metrics.json"

write_json(
    case_b_metrics,
    {
        "assets": []
    },
)

command_b = [
    sys.executable,
    str(GENERATOR),
    "--input",
    str(BASE_INPUT),
    "--schema",
    str(SCHEMA),
    "--output",
    str(case_b_output),
    "--policy",
    str(QUALITY_POLICY),
    "--registry",
    str(REGISTRY),
    "--signal-policy",
    str(SIGNAL_POLICY),
    "--history-dir",
    str(TEMP / "history_b"),
    "--metrics-input",
    str(case_b_metrics),
    "--allow-quality-critical-in-draft",
]

case_b = subprocess.run(
    command_b,
    cwd=ROOT,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)

case_b_text = combined_output(case_b)

check(
    "B1 enrichment route exits zero without Risk input",
    case_b.returncode == 0,
    case_b_text,
)

check(
    "B2 Risk Pipeline does not execute",
    "[RISK PIPELINE]" not in case_b_text,
    case_b_text,
)

check(
    "B3 output created",
    case_b_output.exists(),
)

if case_b_output.exists():
    case_b_data = load_json(case_b_output)
    case_b_assets = assets_by_ticker(
        case_b_data
    )

    for ticker in ("VRT", "CRSP", "ETON"):
        check(
            f"B4 {ticker} existing risk preserved",
            case_b_assets.get(
                ticker,
                {},
            ).get("risk")
            == original_risk.get(ticker),
        )


# ------------------------------------------------------------
# CASE C
# Missing Risk History file
# ------------------------------------------------------------

print()
print("CASE C - MISSING RISK HISTORY")

case_c_output = TEMP / "case_c.json"

case_c = run_generator(
    BASE_INPUT,
    case_c_output,
    TEMP / "does_not_exist.json",
)

case_c_text = combined_output(case_c)

check(
    "C1 missing Risk History fails closed",
    case_c.returncode != 0,
    case_c_text,
)

check(
    "C2 missing Risk History creates no output",
    not case_c_output.exists(),
)


# ------------------------------------------------------------
# CASE D
# Invalid JSON
# ------------------------------------------------------------

print()
print("CASE D - INVALID RISK JSON")

invalid_json = TEMP / "invalid_risk.json"

invalid_json.write_text(
    "{ invalid json",
    encoding="utf-8",
)

case_d_output = TEMP / "case_d.json"

case_d = run_generator(
    BASE_INPUT,
    case_d_output,
    invalid_json,
)

case_d_text = combined_output(case_d)

check(
    "D1 invalid Risk JSON fails closed",
    case_d.returncode != 0,
    case_d_text,
)

check(
    "D2 invalid Risk JSON creates no output",
    not case_d_output.exists(),
)


# ------------------------------------------------------------
# CASE E
# Invalid root
# ------------------------------------------------------------

print()
print("CASE E - INVALID RISK ROOT")

invalid_root = TEMP / "invalid_root.json"

write_json(
    invalid_root,
    [],
)

case_e_output = TEMP / "case_e.json"

case_e = run_generator(
    BASE_INPUT,
    case_e_output,
    invalid_root,
)

case_e_text = combined_output(case_e)

check(
    "E1 invalid Risk root fails closed",
    case_e.returncode != 0,
    case_e_text,
)

check(
    "E2 invalid Risk root creates no output",
    not case_e_output.exists(),
)


# ------------------------------------------------------------
# CASE F
# Invalid assets structure
# ------------------------------------------------------------

print()
print("CASE F - INVALID ASSETS STRUCTURE")

invalid_assets = copy.deepcopy(
    risk_fixture
)

invalid_assets["assets"] = {
    "VRT": {}
}

invalid_assets_path = (
    TEMP / "invalid_assets.json"
)

write_json(
    invalid_assets_path,
    invalid_assets,
)

case_f_output = TEMP / "case_f.json"

case_f = run_generator(
    BASE_INPUT,
    case_f_output,
    invalid_assets_path,
)

case_f_text = combined_output(case_f)

check(
    "F1 invalid assets structure fails closed",
    case_f.returncode != 0,
    case_f_text,
)

check(
    "F2 invalid assets structure creates no output",
    not case_f_output.exists(),
)


# ------------------------------------------------------------
# CASE G
# One asset has invalid records.
# Must not invent new Risk for that asset.
# Other valid assets may continue analytically.
# ------------------------------------------------------------

print()
print("CASE G - INVALID RECORDS FOR ONE TICKER")

partial_bad = copy.deepcopy(
    risk_fixture
)

for item in partial_bad.get("assets", []):
    if (
        isinstance(item, dict)
        and item.get("ticker") == "CRSP"
    ):
        item["records"] = [
            {
                "market_date":
                    "NOT-A-DATE",
                "Close":
                    55.0,
            }
        ]

partial_bad_path = (
    TEMP / "partial_bad.json"
)

write_json(
    partial_bad_path,
    partial_bad,
)

case_g_output = TEMP / "case_g.json"

case_g = run_generator(
    BASE_INPUT,
    case_g_output,
    partial_bad_path,
)

case_g_text = combined_output(case_g)

check(
    "G1 per-asset invalid Risk does not crash run",
    case_g.returncode == 0,
    case_g_text,
)

check(
    "G2 Risk warning is emitted",
    "Risk indisponivel" in case_g_text,
    case_g_text,
)

check(
    "G3 partial output created",
    case_g_output.exists(),
)

if case_g_output.exists():
    case_g_data = load_json(case_g_output)
    case_g_assets = assets_by_ticker(
        case_g_data
    )

    check(
        "G4 CRSP invalid history does not create replacement risk",
        case_g_assets.get(
            "CRSP",
            {},
        ).get("risk")
        == original_risk.get("CRSP"),
    )

    for ticker in ("VRT", "ETON"):
        check(
            f"G5 {ticker} valid history still replaces stale risk",
            case_g_assets.get(
                ticker,
                {},
            ).get("risk")
            != original_risk.get(ticker),
        )


# ------------------------------------------------------------
# CASE H
# Missing source metadata:
# analytical Risk may still run.
# Sidecar is intentionally unavailable for later publication gate.
# It must never leak into public JSON.
# ------------------------------------------------------------

print()
print("CASE H - MISSING SOURCE METADATA")

missing_source = copy.deepcopy(
    risk_fixture
)

missing_source.pop(
    "source",
    None,
)

missing_source_path = (
    TEMP / "missing_source.json"
)

write_json(
    missing_source_path,
    missing_source,
)

case_h_output = TEMP / "case_h.json"

case_h = run_generator(
    BASE_INPUT,
    case_h_output,
    missing_source_path,
)

case_h_text = combined_output(case_h)

check(
    "H1 analytical Risk can run without publication source metadata",
    case_h.returncode == 0,
    case_h_text,
)

check(
    "H2 output created",
    case_h_output.exists(),
)

if case_h_output.exists():
    case_h_data = load_json(case_h_output)
    case_h_assets = assets_by_ticker(
        case_h_data
    )

    for ticker in ("VRT", "CRSP", "ETON"):
        check(
            f"H3 {ticker} analytical risk still calculated",
            case_h_assets.get(
                ticker,
                {},
            ).get("risk")
            != original_risk.get(ticker),
        )

    serialized = json.dumps(
        case_h_data,
        ensure_ascii=False,
    )

    check(
        "H4 absent sidecar metadata does not leak into public output",
        "risk_source_context_by_ticker"
        not in serialized,
    )


# ------------------------------------------------------------
# CASE I
# Invalid Risk Policy path
# ------------------------------------------------------------

print()
print("CASE I - MISSING RISK POLICY")

case_i_output = TEMP / "case_i.json"

case_i = run_generator(
    BASE_INPUT,
    case_i_output,
    RISK_FIXTURE,
    TEMP / "missing_policy.json",
)

case_i_text = combined_output(case_i)

check(
    "I1 missing Risk Policy fails closed",
    case_i.returncode != 0,
    case_i_text,
)

check(
    "I2 missing Risk Policy creates no output",
    not case_i_output.exists(),
)


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

print()
print("=" * 72)
print(f"PASS: {PASS_COUNT}")
print(f"FAIL: {FAIL_COUNT}")

if FAIL_COUNT:
    print(
        "RESULT: RISK RUNTIME ADVERSARIAL FAILED"
    )
    raise SystemExit(1)

print(
    "RESULT: RISK RUNTIME ADVERSARIAL APPROVED"
)

raise SystemExit(0)
