import copy
import importlib.util
import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ENGINE_PATH = ROOT / "evidence_gate_engine_v3.py"
POLICY_PATH = ROOT / "evidence_gate_policy_v3.json"
RUNTIME_CONTRACT_PATH = ROOT / "evidence_gate_runtime_contract_v3.json"

failures = []
checks = 0


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


def load_engine(path):
    spec = importlib.util.spec_from_file_location(
        "evidence_gate_engine_v3",
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to create engine module spec")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = load_json(POLICY_PATH)
runtime_contract = load_json(RUNTIME_CONTRACT_PATH)

print("=" * 68)
print(" D.3D.3A - EVIDENCE GATE ENGINE BEHAVIORAL CONTRACT - RED")
print("=" * 68)

# ============================================================
# A. PRECONDITIONS
# ============================================================

check(
    policy.get("policy_id") == "RADAR_V3_EVIDENCE_GATE_POLICY",
    "D.3B Evidence Gate policy available",
)

check(
    runtime_contract.get("contract_id")
    == "RADAR_V3_EVIDENCE_GATE_RUNTIME_CONTRACT",
    "D.3D.2 runtime contract available",
)

# ============================================================
# B. EXPECTED RED BOUNDARY
# ============================================================

if not ENGINE_PATH.exists():
    check(
        False,
        "evidence_gate_engine_v3.py exists",
    )

    print()
    print("=" * 68)
    print(" EXPECTED RED BOUNDARY")
    print("=" * 68)
    print("Engine implementation is intentionally absent.")
    print("D.3D.3A must remain RED until D.3D.3B implements the engine.")
    print()
    print(f"Checks executed: {checks}")
    print(f"Failures: {len(failures)}")
    print("RESULT: EXPECTED_RED")
    raise SystemExit(1)

# ============================================================
# C. MODULE LOAD
# ============================================================

try:
    engine = load_engine(ENGINE_PATH)
    check(True, "engine module imports successfully")
except Exception as exc:
    check(False, f"engine module imports successfully: {exc}")

    print()
    print(f"Checks executed: {checks}")
    print(f"Failures: {len(failures)}")
    print("RESULT: RED")
    raise SystemExit(1)

# ============================================================
# D. PUBLIC API
# ============================================================

check(
    hasattr(engine, "evaluate_asset_evidence"),
    "evaluate_asset_evidence exported",
)

check(
    hasattr(engine, "apply_evidence_gate"),
    "apply_evidence_gate exported",
)

if not hasattr(engine, "evaluate_asset_evidence"):
    print()
    print(f"Checks executed: {checks}")
    print(f"Failures: {len(failures)}")
    print("RESULT: RED")
    raise SystemExit(1)

if not hasattr(engine, "apply_evidence_gate"):
    print()
    print(f"Checks executed: {checks}")
    print(f"Failures: {len(failures)}")
    print("RESULT: RED")
    raise SystemExit(1)

evaluate_asset_evidence = engine.evaluate_asset_evidence
apply_evidence_gate = engine.apply_evidence_gate

asset_signature = inspect.signature(evaluate_asset_evidence)
radar_signature = inspect.signature(apply_evidence_gate)

check(
    list(asset_signature.parameters.keys())
    == [
        "asset",
        "evidence_gate_policy",
        "publication_context",
        "risk_source_context",
    ],
    "evaluate_asset_evidence signature canonical",
)

check(
    asset_signature.parameters["publication_context"].default is None,
    "publication_context defaults to None",
)

check(
    asset_signature.parameters["risk_source_context"].default is None,
    "risk_source_context defaults to None",
)

check(
    list(radar_signature.parameters.keys())
    == [
        "radar",
        "evidence_gate_policy",
        "publication_context_by_ticker",
        "risk_source_context_by_ticker",
    ],
    "apply_evidence_gate signature canonical",
)

check(
    radar_signature.parameters[
        "publication_context_by_ticker"
    ].default is None,
    "publication_context_by_ticker defaults to None",
)

check(
    radar_signature.parameters[
        "risk_source_context_by_ticker"
    ].default is None,
    "risk_source_context_by_ticker defaults to None",
)

# ============================================================
# E. RESULT STRUCTURE HELPERS
# ============================================================

required_result_fields = set(
    runtime_contract["result_contract"]["per_ticker_required_fields"]
)

allowed_gate_statuses = set(
    runtime_contract["result_contract"]["gate_status_allowed_values"]
)

bucket_mapping = runtime_contract[
    "result_contract"
]["evidence_buckets"]


def validate_result_structure(result, ticker):
    check(
        isinstance(result, dict),
        f"{ticker}: result is dict",
    )

    if not isinstance(result, dict):
        return

    check(
        required_result_fields.issubset(result.keys()),
        f"{ticker}: required result fields present",
    )

    check(
        result.get("ticker") == ticker,
        f"{ticker}: ticker preserved",
    )

    check(
        result.get("gate_status") in allowed_gate_statuses,
        f"{ticker}: gate status canonical",
    )

    check(
        isinstance(result.get("evidence_gate_passed"), bool),
        f"{ticker}: evidence_gate_passed boolean",
    )

    for bucket in bucket_mapping:
        check(
            isinstance(result.get(bucket), list),
            f"{ticker}: {bucket} is list",
        )

    check(
        isinstance(result.get("reasons"), list),
        f"{ticker}: reasons is list",
    )


def all_evidence(result):
    items = []

    for bucket in bucket_mapping:
        value = result.get(bucket, [])
        if isinstance(value, list):
            items.extend(value)

    return items


def find_domain(result, domain):
    return [
        item
        for item in all_evidence(result)
        if isinstance(item, dict)
        and item.get("domain") == domain
    ]


# ============================================================
# F. SYNTHETIC UPSTREAM ASSET
#
# Important:
# These values are NOT financial recommendations and do NOT
# introduce thresholds. They are categorical upstream outputs
# already recognized by D.3 policy.
# ============================================================

base_asset = {
    "ticker": "TEST",
    "score": {
        "status": "CALCULATED",
        "coverage": 1.0,
        "analytically_usable": True,
        "publishable": True,
        "normalized_score": 80.0,
        "label": "BUY",
        "components": {},
    },
    "confidence": {
        "score": 0.90,
        "status": "VERIFIED",
    },
    "signals": {
        "technical": {
            "status": "CALCULATED",
            "coverage": 1.0,
            "score": 70.0,
        }
    },
    "risk": {
        "status": "CALCULATED",
        "level": "MODERATE",
        "score": 35.0,
    },
    "provenance": {
        "price": {
            "status": "VERIFIED",
            "source_id": "TEST_SOURCE",
        }
    },
}

publication_ok = {
    "eligible": True,
    "status": "ELIGIBLE",
}

risk_context_ok = {
    "source_id": "TEST_SOURCE",
    "publication_eligible": True,
}

# ============================================================
# G. NO MUTATION
# ============================================================

asset = copy.deepcopy(base_asset)
asset_before = copy.deepcopy(asset)

result = evaluate_asset_evidence(
    asset,
    policy,
    publication_ok,
    risk_context_ok,
)

check(
    asset == asset_before,
    "evaluate_asset_evidence does not mutate asset",
)

validate_result_structure(result, "TEST")

# ============================================================
# H. PASS IS NOT DECISION AUTHORITY
# ============================================================

check(
    result["gate_status"] in allowed_gate_statuses,
    "aggregate gate status uses runtime vocabulary",
)

check(
    "decision_state" not in result,
    "result does not create decision_state",
)

check(
    "actionable_authority" not in result,
    "result does not create actionable_authority",
)

check(
    "decision_center" not in result,
    "result does not create decision_center",
)

# ============================================================
# I. SCORE LABEL CANNOT BECOME DECISION
# ============================================================

score_asset = copy.deepcopy(base_asset)
score_asset["score"]["normalized_score"] = 100.0
score_asset["score"]["label"] = "STRONG_BUY"

score_result = evaluate_asset_evidence(
    score_asset,
    policy,
    publication_ok,
    risk_context_ok,
)

check(
    "decision_state" not in score_result,
    "high score does not create decision state",
)

check(
    "actionable_authority" not in score_result,
    "high score does not create actionable authority",
)

# ============================================================
# J. MISSING REQUIRED SCORE
# ============================================================

missing_score_asset = copy.deepcopy(base_asset)
missing_score_asset.pop("score")

missing_score_result = evaluate_asset_evidence(
    missing_score_asset,
    policy,
    publication_ok,
    risk_context_ok,
)

score_missing_items = find_domain(
    missing_score_result,
    "RADAR_SCORE",
)

check(
    len(score_missing_items) >= 1,
    "missing score remains represented",
)

check(
    any(
        item.get("gate_result") == "INSUFFICIENT"
        for item in score_missing_items
    ),
    "missing required score -> INSUFFICIENT",
)

check(
    missing_score_result["evidence_gate_passed"] is False,
    "missing required score cannot pass gate",
)

# ============================================================
# K. INVALID PROVENANCE
# ============================================================

invalid_provenance_asset = copy.deepcopy(base_asset)

invalid_provenance_asset["provenance"]["price"] = {
    "status": "INVALID",
    "source_id": "TEST_SOURCE",
}

invalid_provenance_result = evaluate_asset_evidence(
    invalid_provenance_asset,
    policy,
    publication_ok,
    risk_context_ok,
)

provenance_items = [
    item
    for item in all_evidence(invalid_provenance_result)
    if isinstance(item, dict)
    and item.get("gate_result") == "BLOCKED"
]

check(
    len(provenance_items) >= 1,
    "invalid required provenance remains BLOCKED and visible",
)

check(
    invalid_provenance_result["evidence_gate_passed"] is False,
    "invalid required provenance cannot pass gate",
)

# ============================================================
# L. UNKNOWN UPSTREAM STATUS
# ============================================================

unknown_asset = copy.deepcopy(base_asset)
unknown_asset["confidence"]["status"] = "MYSTERY_STATUS"

unknown_result = evaluate_asset_evidence(
    unknown_asset,
    policy,
    publication_ok,
    risk_context_ok,
)

confidence_unknown_items = find_domain(
    unknown_result,
    "CONFIDENCE",
)

check(
    len(confidence_unknown_items) >= 1,
    "unknown confidence status remains represented",
)

check(
    any(
        item.get("gate_result") == "UNKNOWN"
        for item in confidence_unknown_items
    ),
    "unknown confidence status -> UNKNOWN",
)

check(
    unknown_result["evidence_gate_passed"] is False,
    "unknown required status cannot pass gate",
)

# ============================================================
# M. PUBLICATION INELIGIBILITY
# ============================================================

publication_blocked = {
    "eligible": False,
    "status": "INELIGIBLE",
}

publication_result = evaluate_asset_evidence(
    copy.deepcopy(base_asset),
    policy,
    publication_blocked,
    risk_context_ok,
)

publication_items = find_domain(
    publication_result,
    "PUBLICATION_ELIGIBILITY",
)

check(
    len(publication_items) >= 1,
    "publication evidence represented",
)

check(
    any(
        item.get("gate_result") == "BLOCKED"
        for item in publication_items
    ),
    "publication ineligible where applicable -> BLOCKED",
)

check(
    publication_result["evidence_gate_passed"] is False,
    "publication ineligible cannot pass gate",
)

# ============================================================
# N. BLOCKED / INSUFFICIENT / UNKNOWN PRESERVED
# ============================================================

for name, tested_result, bucket in [
    (
        "blocked",
        publication_result,
        "blocked_evidence",
    ),
    (
        "insufficient",
        missing_score_result,
        "insufficient_evidence",
    ),
    (
        "unknown",
        unknown_result,
        "unknown_evidence",
    ),
]:
    check(
        len(tested_result.get(bucket, [])) >= 1,
        f"{name} evidence preserved in sidecar",
    )

# ============================================================
# O. RADAR-LEVEL API AND IMMUTABILITY
# ============================================================

radar = {
    "schema_version": "3.0",
    "assets": [
        copy.deepcopy(base_asset),
    ],
    "decision_center": {
        "action_of_day": "UNCHANGED",
        "top_opportunities": [],
        "top_risks": [],
        "recommended_actions": [],
    },
}

radar_before = copy.deepcopy(radar)

radar_result = apply_evidence_gate(
    radar,
    policy,
    {
        "TEST": publication_ok,
    },
    {
        "TEST": risk_context_ok,
    },
)

check(
    radar == radar_before,
    "apply_evidence_gate does not mutate radar",
)

check(
    isinstance(radar_result, dict),
    "radar result is sidecar dict",
)

check(
    "TEST" in radar_result,
    "radar sidecar keyed by ticker",
)

if "TEST" in radar_result:
    validate_result_structure(
        radar_result["TEST"],
        "TEST",
    )

check(
    radar["decision_center"]
    == radar_before["decision_center"],
    "decision_center remains untouched",
)

check(
    "evidence_gate" not in radar,
    "Evidence Gate not persisted in radar root",
)

check(
    "evidence_gate" not in radar["assets"][0],
    "Evidence Gate not persisted in asset",
)

# ============================================================
# P. REASONS / TRACEABILITY
# ============================================================

for name, tested_result in [
    ("base", result),
    ("missing", missing_score_result),
    ("invalid provenance", invalid_provenance_result),
    ("unknown", unknown_result),
    ("publication blocked", publication_result),
]:
    evidence = all_evidence(tested_result)

    for index, item in enumerate(evidence):
        check(
            isinstance(item, dict),
            f"{name}: evidence item {index} is dict",
        )

        if not isinstance(item, dict):
            continue

        for field in [
            "evidence_id",
            "domain",
            "information_class",
            "gate_result",
            "reason_code",
        ]:
            check(
                field in item,
                f"{name}: evidence item {index} has {field}",
            )

# ============================================================
# Q. FINAL
# ============================================================

print()
print("=" * 68)
print(" D.3D.3A - ENGINE BEHAVIORAL CONTRACT RESULT")
print("=" * 68)
print(f"Checks executed: {checks}")
print(f"Failures: {len(failures)}")

if failures:
    print("RESULT: RED")
    for failure in failures:
        print(f" - {failure}")
    raise SystemExit(1)

print("RESULT: GREEN")
