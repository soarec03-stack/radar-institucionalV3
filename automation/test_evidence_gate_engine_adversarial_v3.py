import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent

ENGINE_PATH = ROOT / "evidence_gate_engine_v3.py"
POLICY_PATH = ROOT / "evidence_gate_policy_v3.json"

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
        raise RuntimeError("Unable to create module spec")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = load_json(POLICY_PATH)
engine = load_module(ENGINE_PATH)

evaluate_asset_evidence = engine.evaluate_asset_evidence
apply_evidence_gate = engine.apply_evidence_gate


def base_asset():
    return {
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


def publication_ok():
    return {
        "eligible": True,
        "status": "ELIGIBLE",
    }


def risk_ok():
    return {
        "source_id": "TEST_SOURCE",
        "publication_eligible": True,
    }


def all_evidence(result):
    items = []

    for bucket in [
        "admissible_evidence",
        "restricted_evidence",
        "blocked_evidence",
        "insufficient_evidence",
        "unknown_evidence",
    ]:
        value = result.get(bucket, [])

        if isinstance(value, list):
            items.extend(value)

    return items


def evidence_for_domain(result, domain):
    return [
        item
        for item in all_evidence(result)
        if isinstance(item, dict)
        and item.get("domain") == domain
    ]


def has_result(result, gate_result):
    return any(
        item.get("gate_result") == gate_result
        for item in all_evidence(result)
        if isinstance(item, dict)
    )


def evaluate(asset=None, publication=None, risk=None, gate_policy=None):
    if asset is None:
        asset = base_asset()

    if publication is None:
        publication = publication_ok()

    if risk is None:
        risk = risk_ok()

    if gate_policy is None:
        gate_policy = policy

    return evaluate_asset_evidence(
        asset,
        gate_policy,
        publication,
        risk,
    )


print("=" * 72)
print(" D.3D.3C - EVIDENCE GATE ENGINE RUNTIME ADVERSARIAL TEST")
print("=" * 72)

# ============================================================
# A. BASELINE
# ============================================================

baseline_asset = base_asset()
baseline_before = copy.deepcopy(baseline_asset)

baseline = evaluate(baseline_asset)

check(
    baseline_asset == baseline_before,
    "01. baseline evaluation does not mutate asset",
)

check(
    baseline["gate_status"] == "PASSED",
    "02. fully admissible baseline -> PASSED",
)

check(
    baseline["evidence_gate_passed"] is True,
    "03. PASSED baseline sets evidence_gate_passed true",
)

check(
    not baseline["blocked_evidence"],
    "04. baseline contains no blocked evidence",
)

check(
    not baseline["insufficient_evidence"],
    "05. baseline contains no insufficient evidence",
)

check(
    not baseline["unknown_evidence"],
    "06. baseline contains no unknown evidence",
)

# ============================================================
# B. AGGREGATE PRECEDENCE
#
# Expected fail-closed precedence frozen by current runtime:
# UNKNOWN > BLOCKED > INSUFFICIENT > RESTRICTED > PASSED
# ============================================================

asset = base_asset()
asset["score"]["status"] = "PARTIAL"

result = evaluate(asset)

check(
    result["gate_status"] == "RESTRICTED",
    "07. RESTRICTED dominates otherwise admissible evidence",
)

check(
    result["evidence_gate_passed"] is False,
    "08. RESTRICTED cannot pass gate",
)


asset = base_asset()
asset.pop("score")

result = evaluate(asset)

check(
    result["gate_status"] == "INSUFFICIENT",
    "09. INSUFFICIENT dominates admissible evidence",
)

check(
    result["evidence_gate_passed"] is False,
    "10. INSUFFICIENT cannot pass gate",
)


asset = base_asset()
asset.pop("score")

publication = {
    "eligible": False,
    "status": "INELIGIBLE",
}

result = evaluate(asset, publication=publication)

check(
    result["gate_status"] == "BLOCKED",
    "11. BLOCKED dominates INSUFFICIENT",
)

check(
    has_result(result, "INSUFFICIENT"),
    "12. lower-precedence INSUFFICIENT evidence remains preserved",
)


asset = base_asset()
asset.pop("score")
asset["confidence"]["status"] = "MYSTERY_STATUS"

publication = {
    "eligible": False,
    "status": "INELIGIBLE",
}

result = evaluate(asset, publication=publication)

check(
    result["gate_status"] == "UNKNOWN",
    "13. UNKNOWN dominates BLOCKED and INSUFFICIENT",
)

check(
    has_result(result, "BLOCKED"),
    "14. BLOCKED evidence remains preserved under UNKNOWN aggregate",
)

check(
    has_result(result, "INSUFFICIENT"),
    "15. INSUFFICIENT evidence remains preserved under UNKNOWN aggregate",
)

# ============================================================
# C. MALFORMED / UNKNOWN POLICY
# ============================================================

result = evaluate(
    gate_policy={},
)

check(
    result["gate_status"] == "UNKNOWN",
    "16. unknown Evidence Gate policy -> UNKNOWN",
)

check(
    result["evidence_gate_passed"] is False,
    "17. unknown Evidence Gate policy cannot pass",
)


result = evaluate(
    gate_policy="INVALID_POLICY",
)

check(
    result["gate_status"] == "UNKNOWN",
    "18. malformed Evidence Gate policy -> UNKNOWN",
)

check(
    result["evidence_gate_passed"] is False,
    "19. malformed Evidence Gate policy cannot pass",
)

# ============================================================
# D. MALFORMED ASSET
# ============================================================

result = evaluate_asset_evidence(
    "INVALID_ASSET",
    policy,
    publication_ok(),
    risk_ok(),
)

check(
    result["gate_status"] == "UNKNOWN",
    "20. malformed asset -> UNKNOWN",
)

check(
    result["evidence_gate_passed"] is False,
    "21. malformed asset cannot pass",
)

# ============================================================
# E. TICKER ANOMALIES
# ============================================================

asset = base_asset()
asset.pop("ticker")

result = evaluate(asset)

check(
    result["ticker"] == "",
    "22. missing ticker is not invented",
)

check(
    "decision_state" not in result,
    "23. missing ticker cannot manufacture decision state",
)


asset = base_asset()
asset["ticker"] = 12345

result = evaluate(asset)

check(
    result["ticker"] == "",
    "24. non-string ticker is not coerced into identity",
)

# ============================================================
# F. PUBLICATION CONTEXT ATTACKS
# ============================================================

result = evaluate_asset_evidence(
    base_asset(),
    policy,
    None,
    risk_ok(),
)

publication_items = evidence_for_domain(
    result,
    "PUBLICATION_ELIGIBILITY",
)

check(
    any(
        item.get("gate_result") == "RESTRICTED"
        for item in publication_items
    ),
    "25. missing publication context remains restricted",
)

check(
    result["gate_status"] == "RESTRICTED",
    "26. missing publication context prevents PASSED",
)


result = evaluate_asset_evidence(
    base_asset(),
    policy,
    "INVALID_CONTEXT",
    risk_ok(),
)

publication_items = evidence_for_domain(
    result,
    "PUBLICATION_ELIGIBILITY",
)

check(
    any(
        item.get("gate_result") == "UNKNOWN"
        for item in publication_items
    ),
    "27. malformed publication context -> UNKNOWN evidence",
)

check(
    result["gate_status"] == "UNKNOWN",
    "28. malformed publication context -> UNKNOWN aggregate",
)


result = evaluate_asset_evidence(
    base_asset(),
    policy,
    {
        "eligible": "YES",
        "status": "ELIGIBLE",
    },
    risk_ok(),
)

check(
    result["gate_status"] == "UNKNOWN",
    "29. non-boolean publication eligibility fails closed",
)

# ============================================================
# G. RISK SIDECAR ATTACKS
# ============================================================

asset = base_asset()

result = evaluate_asset_evidence(
    asset,
    policy,
    publication_ok(),
    {
        "source_id": "RESEARCH_ONLY",
        "publication_eligible": False,
    },
)

risk_items = evidence_for_domain(result, "RISK")

check(
    any(
        item.get("gate_result") == "BLOCKED"
        for item in risk_items
    ),
    "30. publication-ineligible risk source -> BLOCKED",
)

check(
    result["gate_status"] == "BLOCKED",
    "31. blocked risk provenance prevents gate pass",
)


asset = base_asset()
asset.pop("risk")

result = evaluate(asset)

risk_items = evidence_for_domain(result, "RISK")

check(
    any(
        item.get("gate_result") == "INSUFFICIENT"
        for item in risk_items
    ),
    "32. missing risk remains INSUFFICIENT",
)

check(
    result["evidence_gate_passed"] is False,
    "33. missing risk cannot be assumed safe",
)

# ============================================================
# H. CONFIDENCE ATTACKS
# ============================================================

asset = base_asset()
asset["confidence"]["status"] = "UNAVAILABLE"

result = evaluate(asset)

check(
    any(
        item.get("gate_result") == "INSUFFICIENT"
        for item in evidence_for_domain(result, "CONFIDENCE")
    ),
    "34. unavailable confidence -> INSUFFICIENT",
)


asset = base_asset()
asset["confidence"]["status"] = "LOW"

result = evaluate(asset)

check(
    any(
        item.get("gate_result") == "RESTRICTED"
        for item in evidence_for_domain(result, "CONFIDENCE")
    ),
    "35. LOW confidence is not automatically admissible",
)

check(
    result["gate_status"] == "RESTRICTED",
    "36. LOW confidence restricts otherwise admissible baseline",
)


asset = base_asset()
asset.pop("confidence")

result = evaluate(asset)

check(
    any(
        item.get("gate_result") == "INSUFFICIENT"
        for item in evidence_for_domain(result, "CONFIDENCE")
    ),
    "37. missing confidence -> INSUFFICIENT",
)

# ============================================================
# I. SCORE ATTACKS
# ============================================================

asset = base_asset()
asset["score"]["status"] = "MYSTERY"

result = evaluate(asset)

check(
    any(
        item.get("gate_result") == "UNKNOWN"
        for item in evidence_for_domain(result, "RADAR_SCORE")
    ),
    "38. unknown score status -> UNKNOWN",
)


asset = base_asset()
asset["score"]["status"] = "INSUFFICIENT_DATA"

result = evaluate(asset)

check(
    result["gate_status"] == "INSUFFICIENT",
    "39. upstream insufficient score prevents pass",
)


asset = base_asset()
asset["score"]["analytically_usable"] = False

result = evaluate(asset)

check(
    result["gate_status"] == "RESTRICTED",
    "40. non-usable upstream score is restricted",
)


asset = base_asset()
asset["score"]["publishable"] = False

result = evaluate(asset)

check(
    result["gate_status"] == "RESTRICTED",
    "41. non-publishable score cannot silently pass",
)

# ============================================================
# J. NUMERIC MAGNITUDE MUST NOT CREATE AUTHORITY
# ============================================================

for index, value in enumerate(
    [
        -999999.0,
        -1.0,
        0.0,
        1.0,
        50.0,
        100.0,
        999999.0,
    ],
    start=42,
):
    asset = base_asset()

    asset["score"]["normalized_score"] = value
    asset["signals"]["technical"]["score"] = value
    asset["risk"]["score"] = value
    asset["confidence"]["score"] = value

    result = evaluate(asset)

    check(
        result["gate_status"] == "PASSED",
        f"{index}. numeric magnitude {value} does not create a new Gate threshold",
    )

    check(
        "decision_state" not in result
        and "actionable_authority" not in result,
        f"{index}A. numeric magnitude {value} does not manufacture decision authority",
    )

# ============================================================
# K. SCORE LABEL ATTACKS
# ============================================================

for label in [
    "STRONG_BUY",
    "BUY",
    "WATCH_ACCUMULATE",
    "HOLD",
    "CAUTION",
    "AVOID",
    "SOMETHING_UNKNOWN",
    None,
]:
    asset = base_asset()
    asset["score"]["label"] = label

    result = evaluate(asset)

    check(
        result["gate_status"] == "PASSED",
        f"score label {label!r} does not select Gate result",
    )

    check(
        "decision_state" not in result,
        f"score label {label!r} does not create Decision State",
    )

# ============================================================
# L. SIGNAL ATTACKS
# ============================================================

asset = base_asset()
asset.pop("signals")

result = evaluate(asset)

check(
    result["gate_status"] == "INSUFFICIENT",
    "missing signals remain INSUFFICIENT",
)


asset = base_asset()
asset["signals"] = {}

result = evaluate(asset)

check(
    result["gate_status"] == "INSUFFICIENT",
    "empty signals remain INSUFFICIENT",
)


asset = base_asset()
asset["signals"] = "INVALID"

result = evaluate(asset)

check(
    result["gate_status"] == "UNKNOWN",
    "malformed signals container -> UNKNOWN",
)


asset = base_asset()
asset["signals"]["technical"]["status"] = "MYSTERY"

result = evaluate(asset)

check(
    result["gate_status"] == "UNKNOWN",
    "unknown signal status -> UNKNOWN",
)


asset = base_asset()
asset["signals"]["technical"]["status"] = "UNAVAILABLE"

result = evaluate(asset)

check(
    result["gate_status"] == "INSUFFICIENT",
    "unavailable signal -> INSUFFICIENT",
)


asset = base_asset()
asset["signals"]["technical"]["status"] = "INSUFFICIENT_COVERAGE"

result = evaluate(asset)

check(
    result["gate_status"] == "INSUFFICIENT",
    "insufficient signal coverage -> INSUFFICIENT",
)

# ============================================================
# M. PROVENANCE ATTACKS
# ============================================================

asset = base_asset()
asset.pop("provenance")

result = evaluate(asset)

check(
    result["gate_status"] == "INSUFFICIENT",
    "missing required provenance -> INSUFFICIENT",
)


asset = base_asset()
asset["provenance"].pop("price")

result = evaluate(asset)

check(
    result["gate_status"] == "INSUFFICIENT",
    "missing price provenance -> INSUFFICIENT",
)


asset = base_asset()
asset["provenance"]["price"]["status"] = "INVALID"

result = evaluate(asset)

check(
    result["gate_status"] == "BLOCKED",
    "invalid price provenance -> BLOCKED",
)


asset = base_asset()
asset["provenance"]["price"]["status"] = "MYSTERY"

result = evaluate(asset)

check(
    result["gate_status"] == "UNKNOWN",
    "unknown price provenance -> UNKNOWN",
)


asset = base_asset()
asset["provenance"]["price"]["status"] = "UNAVAILABLE"

result = evaluate(asset)

check(
    result["gate_status"] == "INSUFFICIENT",
    "unavailable price provenance -> INSUFFICIENT",
)

# ============================================================
# N. MULTIPLE SIGNALS MUST SURVIVE
# ============================================================

asset = base_asset()

asset["signals"] = {
    "technical": {
        "status": "CALCULATED",
        "coverage": 1.0,
        "score": 90.0,
    },
    "momentum": {
        "status": "CALCULATED",
        "coverage": 1.0,
        "score": 10.0,
    },
}

result = evaluate(asset)

signal_items = evidence_for_domain(
    result,
    "DOMAIN_SIGNALS",
)

check(
    len(signal_items) == 2,
    "multiple signal evidence items are preserved",
)

check(
    all(
        item.get("gate_result") == "ADMISSIBLE"
        for item in signal_items
    ),
    "conflicting numeric signal direction is not resolved by D.3",
)

check(
    result["gate_status"] == "PASSED",
    "semantic signal conflict is not invented by Evidence Gate",
)

# ============================================================
# O. RADAR API / MUTATION ATTACKS
# ============================================================

radar = {
    "schema_version": "3.0",
    "assets": [
        base_asset(),
    ],
    "decision_center": {
        "action_of_day": "DO_NOT_TOUCH",
        "top_opportunities": ["KEEP"],
        "top_risks": ["KEEP"],
        "recommended_actions": ["KEEP"],
    },
}

radar_before = copy.deepcopy(radar)

sidecar = apply_evidence_gate(
    radar,
    policy,
    {
        "TEST": publication_ok(),
    },
    {
        "TEST": risk_ok(),
    },
)

check(
    radar == radar_before,
    "radar-level evaluation is non-mutating",
)

check(
    radar["decision_center"]
    == radar_before["decision_center"],
    "decision_center remains byte-for-byte logically unchanged",
)

check(
    "evidence_gate" not in radar,
    "Evidence Gate sidecar not persisted in radar root",
)

check(
    "evidence_gate" not in radar["assets"][0],
    "Evidence Gate sidecar not persisted in asset",
)

check(
    set(sidecar.keys()) == {"TEST"},
    "radar sidecar keyed only by evaluated ticker",
)

# ============================================================
# P. MALFORMED RADAR CONTAINERS
# ============================================================

check(
    apply_evidence_gate(
        "INVALID_RADAR",
        policy,
    ) == {},
    "malformed radar fails closed to empty sidecar",
)

check(
    apply_evidence_gate(
        {},
        policy,
    ) == {},
    "missing assets container fails closed to empty sidecar",
)

check(
    apply_evidence_gate(
        {"assets": "INVALID"},
        policy,
    ) == {},
    "malformed assets container fails closed to empty sidecar",
)

# ============================================================
# Q. INVALID ASSETS DO NOT CREATE FAKE IDENTITIES
# ============================================================

radar = {
    "assets": [
        "INVALID",
        {"ticker": 123},
        {"ticker": ""},
        base_asset(),
    ]
}

sidecar = apply_evidence_gate(
    radar,
    policy,
    {
        "TEST": publication_ok(),
    },
    {
        "TEST": risk_ok(),
    },
)

check(
    set(sidecar.keys()) == {"TEST"},
    "invalid assets do not create fake ticker identities",
)

# ============================================================
# R. OPTIONAL SIDECAR CONTAINERS MUST NOT MUTATE
# ============================================================

publication_contexts = {
    "TEST": publication_ok(),
}

risk_contexts = {
    "TEST": risk_ok(),
}

publication_before = copy.deepcopy(publication_contexts)
risk_before = copy.deepcopy(risk_contexts)

apply_evidence_gate(
    {
        "assets": [
            base_asset(),
        ]
    },
    policy,
    publication_contexts,
    risk_contexts,
)

check(
    publication_contexts == publication_before,
    "publication sidecar input is not mutated",
)

check(
    risk_contexts == risk_before,
    "risk sidecar input is not mutated",
)

# ============================================================
# S. OUTPUT MUST NOT CONTAIN DECISION AUTHORITY
# ============================================================

result = evaluate()

for prohibited_field in [
    "decision_state",
    "actionable_authority",
    "decision_center",
    "buy",
    "sell",
    "trade_instruction",
]:
    check(
        prohibited_field not in result,
        f"output does not expose prohibited field {prohibited_field}",
    )

# ============================================================
# T. TRACEABILITY
# ============================================================

result = evaluate()

for index, item in enumerate(all_evidence(result)):
    check(
        bool(item.get("evidence_id")),
        f"traceability item {index}: evidence_id present",
    )

    check(
        bool(item.get("domain")),
        f"traceability item {index}: domain present",
    )

    check(
        item.get("information_class") in {
            "FACT",
            "MODEL",
            "INFERENCE",
        },
        f"traceability item {index}: information class canonical",
    )

    check(
        item.get("gate_result") in {
            "ADMISSIBLE",
            "RESTRICTED",
            "BLOCKED",
            "INSUFFICIENT",
            "UNKNOWN",
        },
        f"traceability item {index}: gate result canonical",
    )

    check(
        bool(item.get("reason_code")),
        f"traceability item {index}: reason code present",
    )

# ============================================================
# U. FINAL
# ============================================================

print()
print("=" * 72)
print(" D.3D.3C - ADVERSARIAL RUNTIME RESULT")
print("=" * 72)
print(f"Checks executed: {checks}")
print(f"Failures: {len(failures)}")

if failures:
    print("RESULT: FAILED")

    for failure in failures:
        print(f" - {failure}")

    raise SystemExit(1)

print("RESULT: APPROVED")
