import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FIXTURE_DIR = ROOT / "fixtures" / "b2k_e2e"

ENGINE_PATH = ROOT / "evidence_gate_engine_v3.py"
POLICY_PATH = ROOT / "evidence_gate_policy_v3.json"

RADAR_PATH = FIXTURE_DIR / "radar_base.json"
METRICS_PATH = FIXTURE_DIR / "metrics.json"
RISK_HISTORY_PATH = FIXTURE_DIR / "risk_history.json"


checks = 0
failures = []


def check(condition, message):
    global checks
    checks += 1

    if condition:
        print(f"[PASS] {message}")
    else:
        print(f"[FAIL] {message}")
        failures.append(message)


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_module(path):
    spec = importlib.util.spec_from_file_location(
        "evidence_gate_engine_v3",
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence_items(result):
    items = []

    for bucket in (
        "admissible_evidence",
        "restricted_evidence",
        "blocked_evidence",
        "insufficient_evidence",
        "unknown_evidence",
    ):
        value = result.get(bucket, [])

        if isinstance(value, list):
            items.extend(value)

    return items


def reason_codes(result):
    return [
        item.get("reason_code")
        for item in evidence_items(result)
        if isinstance(item, dict)
    ]


print("=" * 76)
print(" D.3D.4A - EVIDENCE GATE B2K REAL-DATA RUNTIME PROBE")
print("=" * 76)

# ----------------------------------------------------------------------
# A. REQUIRED FILES
# ----------------------------------------------------------------------

check(ENGINE_PATH.exists(), "Evidence Gate engine exists")
check(POLICY_PATH.exists(), "Evidence Gate policy exists")
check(RADAR_PATH.exists(), "B2K radar_base.json exists")
check(METRICS_PATH.exists(), "B2K metrics.json exists")
check(RISK_HISTORY_PATH.exists(), "B2K risk_history.json exists")

if failures:
    print()
    print("RESULT: FAILED - REQUIRED FILE MISSING")
    raise SystemExit(1)


engine = load_module(ENGINE_PATH)
policy = load_json(POLICY_PATH)
radar = load_json(RADAR_PATH)
metrics = load_json(METRICS_PATH)
risk_history = load_json(RISK_HISTORY_PATH)

evaluate_asset_evidence = engine.evaluate_asset_evidence
apply_evidence_gate = engine.apply_evidence_gate


# ----------------------------------------------------------------------
# B. FIXTURE STRUCTURE - OBSERVATION ONLY
# ----------------------------------------------------------------------

print()
print("----- B2K FIXTURE STRUCTURE -----")

print("RADAR ROOT KEYS:")
print(sorted(radar.keys()))

assets = radar.get("assets")

check(
    isinstance(assets, list),
    "B2K radar assets is a list",
)

check(
    len(assets) > 0 if isinstance(assets, list) else False,
    "B2K radar contains assets",
)

if not isinstance(assets, list):
    print("RESULT: FAILED - INVALID B2K ASSET CONTAINER")
    raise SystemExit(1)


print()
print("ASSET INVENTORY:")

for asset in assets:
    if not isinstance(asset, dict):
        print("INVALID ASSET:", repr(asset))
        continue

    ticker = asset.get("ticker")

    print()
    print(f"[{ticker}]")
    print("keys =", sorted(asset.keys()))
    print("score =", repr(asset.get("score")))
    print("confidence =", repr(asset.get("confidence")))
    print("risk =", repr(asset.get("risk")))
    print("signals present =", "signals" in asset)
    print("provenance present =", "provenance" in asset)


# ----------------------------------------------------------------------
# C. NO SYNTHETIC ENRICHMENT
#
# Critical rule:
# This first probe feeds the fixture exactly as persisted.
# No signals, publication context, provenance or risk sidecar may be
# manufactured just to make the Gate pass.
# ----------------------------------------------------------------------

radar_before = copy.deepcopy(radar)

sidecar_without_transient_context = apply_evidence_gate(
    radar,
    policy,
)

check(
    radar == radar_before,
    "Evidence Gate does not mutate B2K fixture",
)

check(
    isinstance(sidecar_without_transient_context, dict),
    "B2K Evidence Gate output is transient dict",
)


# ----------------------------------------------------------------------
# D. PER-ASSET REAL-DATA OBSERVATION
# ----------------------------------------------------------------------

print()
print("----- EVIDENCE GATE RESULTS - PERSISTED B2K ONLY -----")

for asset in assets:
    if not isinstance(asset, dict):
        continue

    ticker = asset.get("ticker")

    if not isinstance(ticker, str) or not ticker:
        continue

    result = sidecar_without_transient_context.get(ticker)

    check(
        isinstance(result, dict),
        f"{ticker}: Gate result exists",
    )

    if not isinstance(result, dict):
        continue

    print()
    print(f"[{ticker}]")
    print("gate_status =", result.get("gate_status"))
    print(
        "evidence_gate_passed =",
        result.get("evidence_gate_passed"),
    )

    print(
        "admissible =",
        len(result.get("admissible_evidence", [])),
    )
    print(
        "restricted =",
        len(result.get("restricted_evidence", [])),
    )
    print(
        "blocked =",
        len(result.get("blocked_evidence", [])),
    )
    print(
        "insufficient =",
        len(result.get("insufficient_evidence", [])),
    )
    print(
        "unknown =",
        len(result.get("unknown_evidence", [])),
    )

    print("reason_codes =", reason_codes(result))

    check(
        result.get("gate_status")
        in {
            "PASSED",
            "RESTRICTED",
            "BLOCKED",
            "INSUFFICIENT",
            "UNKNOWN",
        },
        f"{ticker}: aggregate Gate status canonical",
    )

    check(
        isinstance(result.get("evidence_gate_passed"), bool),
        f"{ticker}: evidence_gate_passed boolean",
    )

    check(
        "decision_state" not in result,
        f"{ticker}: Gate does not create Decision State",
    )

    check(
        "actionable_authority" not in result,
        f"{ticker}: Gate does not create Actionable Authority",
    )


# ----------------------------------------------------------------------
# E. PERSISTED SIGNALS OBSERVATION
# ----------------------------------------------------------------------

print()
print("----- SIGNAL PERSISTENCE OBSERVATION -----")

assets_with_signals = []
assets_without_signals = []

for asset in assets:
    if not isinstance(asset, dict):
        continue

    ticker = asset.get("ticker")

    if "signals" in asset:
        assets_with_signals.append(ticker)
    else:
        assets_without_signals.append(ticker)

print("assets_with_signals =", assets_with_signals)
print("assets_without_signals =", assets_without_signals)

check(
    len(assets_with_signals) + len(assets_without_signals)
    == len(
        [
            asset
            for asset in assets
            if isinstance(asset, dict)
        ]
    ),
    "signal persistence inventory covers every valid B2K asset",
)


# ----------------------------------------------------------------------
# F. PUBLICATION CONTEXT OBSERVATION
#
# We deliberately do NOT invent publication_context_by_ticker.
# We only establish whether such an object is persisted in the fixture.
# ----------------------------------------------------------------------

print()
print("----- PUBLICATION CONTEXT OBSERVATION -----")

persisted_publication_objects = []

for asset in assets:
    if not isinstance(asset, dict):
        continue

    ticker = asset.get("ticker")

    if "publication_eligibility" in asset:
        persisted_publication_objects.append(ticker)

print(
    "assets_with_persisted_publication_eligibility =",
    persisted_publication_objects,
)

print(
    "radar_has_publication_context =",
    "publication_context_by_ticker" in radar,
)


# ----------------------------------------------------------------------
# G. RISK SIDECAR OBSERVATION
# ----------------------------------------------------------------------

print()
print("----- RISK SIDECAR OBSERVATION -----")

print(
    "radar_has_risk_source_context =",
    "risk_source_context_by_ticker" in radar,
)

print(
    "risk_history_type =",
    type(risk_history).__name__,
)

if isinstance(risk_history, dict):
    print(
        "risk_history_root_keys =",
        sorted(risk_history.keys()),
    )


# ----------------------------------------------------------------------
# H. METRICS OBSERVATION
# ----------------------------------------------------------------------

print()
print("----- METRICS OBSERVATION -----")

print(
    "metrics_type =",
    type(metrics).__name__,
)

if isinstance(metrics, dict):
    print(
        "metrics_root_keys =",
        sorted(metrics.keys()),
    )


# ----------------------------------------------------------------------
# I. FAIL-CLOSED REAL-DATA ASSERTIONS
#
# These assertions do NOT require B2K to PASS the Gate.
# They require the Gate to refuse to invent missing runtime context.
# ----------------------------------------------------------------------

for asset in assets:
    if not isinstance(asset, dict):
        continue

    ticker = asset.get("ticker")

    if not isinstance(ticker, str) or not ticker:
        continue

    result = sidecar_without_transient_context[ticker]

    if "signals" not in asset:
        check(
            "SIGNALS_MISSING" in reason_codes(result),
            f"{ticker}: missing persisted signals remains explicit",
        )

    if "publication_eligibility" not in asset:
        check(
            "PUBLICATION_CONTEXT_NOT_PROVIDED"
            in reason_codes(result),
            f"{ticker}: absent publication context is not invented",
        )

    check(
        result.get("evidence_gate_passed") is False
        or result.get("gate_status") == "PASSED",
        f"{ticker}: pass boolean remains consistent with Gate status",
    )


# ----------------------------------------------------------------------
# J. DECISION CENTER MUST REMAIN UNTOUCHED
# ----------------------------------------------------------------------

check(
    radar.get("decision_center")
    == radar_before.get("decision_center"),
    "B2K decision_center remains untouched",
)

check(
    "evidence_gate" not in radar,
    "Evidence Gate not persisted in B2K radar root",
)

for asset in assets:
    if not isinstance(asset, dict):
        continue

    check(
        "evidence_gate" not in asset,
        f"{asset.get('ticker')}: Evidence Gate not persisted in asset",
    )


# ----------------------------------------------------------------------
# K. IMPORTANT ARCHITECTURAL DIAGNOSTIC
# ----------------------------------------------------------------------

print()
print("=" * 76)
print(" ARCHITECTURAL DIAGNOSTIC")
print("=" * 76)

print(
    "This probe intentionally does NOT reconstruct signals, "
    "publication eligibility, or risk provenance."
)

print(
    "A non-PASSED result caused by absent transient/persisted context "
    "is therefore a valid fail-closed observation, not automatically "
    "an engine defect."
)

print(
    "The next step must determine which upstream runtime contexts "
    "must be handed to Evidence Gate explicitly."
)


# ----------------------------------------------------------------------
# L. FINAL
# ----------------------------------------------------------------------

print()
print("=" * 76)
print(" D.3D.4A - B2K REAL-DATA PROBE RESULT")
print("=" * 76)
print(f"Checks executed: {checks}")
print(f"Failures: {len(failures)}")

if failures:
    print("RESULT: FAILED")

    for failure in failures:
        print(f" - {failure}")

    raise SystemExit(1)

print("RESULT: APPROVED")
