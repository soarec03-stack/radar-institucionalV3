import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CONTRACT_PATH = ROOT / "evidence_gate_runtime_contract_v3.json"
POLICY_PATH = ROOT / "evidence_gate_policy_v3.json"

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


contract = load_json(CONTRACT_PATH)
policy = load_json(POLICY_PATH)

# ------------------------------------------------------------
# Identity
# ------------------------------------------------------------

check(
    contract.get("contract_id")
    == "RADAR_V3_EVIDENCE_GATE_RUNTIME_CONTRACT",
    "contract id canonical",
)

check(
    contract.get("contract_version") == "3.4D.3D.2",
    "contract version canonical",
)

check(contract.get("status") == "DRAFT", "contract remains DRAFT")
check(contract.get("scope") == "V3_ONLY", "scope V3 only")

# ------------------------------------------------------------
# Purpose
# ------------------------------------------------------------

purpose = contract["purpose"]

check(
    purpose["defines_runtime_interface"] is True,
    "defines runtime interface",
)

for key in [
    "implements_evidence_gate_engine",
    "defines_evidence_admissibility_policy",
    "defines_conflict_resolution",
    "defines_decision_state",
    "defines_actionable_authority",
    "writes_decision_center",
    "modifies_public_output",
]:
    check(
        purpose[key] is False,
        f"purpose.{key} false",
    )

# ------------------------------------------------------------
# Compatibility
# ------------------------------------------------------------

compat = contract["compatibility"]

check(compat["preserve_v2_1"] is True, "V2.1 preserved")
check(compat["modify_v2_1"] is False, "V2.1 not modified")
check(compat["modify_schema_v3"] is False, "schema V3 not modified")
check(compat["modify_generator"] is False, "Generator not modified")

check(
    compat["modify_existing_decision_center_contract"] is False,
    "existing decision center contract not modified",
)

check(
    compat["requires_public_output_change"] is False,
    "no public output change",
)

# ------------------------------------------------------------
# Policy relationship
# ------------------------------------------------------------

upstream_policy = contract["upstream_policy"]

check(
    upstream_policy["policy_id"]
    == "RADAR_V3_EVIDENCE_GATE_POLICY",
    "Evidence Gate policy id canonical",
)

check(
    upstream_policy["policy_version"]
    == policy["policy_version"],
    "runtime contract references current Evidence Gate policy version",
)

check(
    upstream_policy["consume_policy_without_redefinition"] is True,
    "runtime consumes policy without redefinition",
)

# ------------------------------------------------------------
# Runtime functions
# ------------------------------------------------------------

functions = contract["runtime_functions"]

check(
    set(functions.keys())
    == {"evaluate_asset_evidence", "apply_evidence_gate"},
    "runtime function set exact",
)

asset_fn = functions["evaluate_asset_evidence"]

check(
    asset_fn["responsibility"]
    == "CLASSIFY_EVIDENCE_FOR_ONE_ASSET",
    "asset evaluator responsibility canonical",
)

check(
    asset_fn["inputs"]
    == [
        "asset",
        "evidence_gate_policy",
        "publication_context",
        "risk_source_context",
    ],
    "asset evaluator inputs canonical",
)

check(
    asset_fn["required_inputs"]
    == ["asset", "evidence_gate_policy"],
    "asset evaluator required inputs canonical",
)

check(
    asset_fn["optional_inputs"]
    == ["publication_context", "risk_source_context"],
    "asset evaluator optional inputs canonical",
)

check(
    asset_fn["returns"] == "evidence_gate_result",
    "asset evaluator return canonical",
)

for key in [
    "may_mutate_asset",
    "may_write_decision_center",
    "may_select_decision_state",
    "may_establish_actionable_authority",
]:
    check(
        asset_fn[key] is False,
        f"asset evaluator {key} false",
    )

radar_fn = functions["apply_evidence_gate"]

check(
    radar_fn["responsibility"]
    == "CLASSIFY_EVIDENCE_FOR_RADAR_ASSETS",
    "radar evaluator responsibility canonical",
)

check(
    radar_fn["inputs"]
    == [
        "radar",
        "evidence_gate_policy",
        "publication_context_by_ticker",
        "risk_source_context_by_ticker",
    ],
    "radar evaluator inputs canonical",
)

check(
    radar_fn["required_inputs"]
    == ["radar", "evidence_gate_policy"],
    "radar evaluator required inputs canonical",
)

check(
    radar_fn["optional_inputs"]
    == [
        "publication_context_by_ticker",
        "risk_source_context_by_ticker",
    ],
    "radar evaluator optional inputs canonical",
)

check(
    radar_fn["returns"] == "evidence_gate_context_by_ticker",
    "radar evaluator return canonical",
)

for key in [
    "may_mutate_radar",
    "may_write_decision_center",
    "may_select_decision_state",
    "may_establish_actionable_authority",
]:
    check(
        radar_fn[key] is False,
        f"radar evaluator {key} false",
    )

# ------------------------------------------------------------
# Runtime ownership
# ------------------------------------------------------------

ownership = contract["runtime_input_ownership"]

expected_ownership = {
    "asset": "UPSTREAM_PERSISTED_INPUT",
    "radar": "UPSTREAM_PERSISTED_INPUT",
    "evidence_gate_policy": "D3_POLICY_INPUT",
    "publication_context": "OPTIONAL_RUNTIME_CONTEXT",
    "publication_context_by_ticker": "OPTIONAL_RUNTIME_SIDECAR",
    "risk_source_context": "OPTIONAL_RUNTIME_CONTEXT",
    "risk_source_context_by_ticker": "OPTIONAL_RUNTIME_SIDECAR",
}

check(
    ownership == expected_ownership,
    "runtime input ownership exact",
)

# ------------------------------------------------------------
# Domains
# ------------------------------------------------------------

expected_domains = [
    "RADAR_SCORE",
    "COVERAGE",
    "CONFIDENCE",
    "PUBLICATION_ELIGIBILITY",
    "RISK",
    "DOMAIN_SIGNALS",
    "CATALYSTS",
    "INSTITUTIONAL_FLOW",
    "PORTFOLIO",
    "MARKET_REGIME",
]

check(
    contract["authorized_upstream_domains"] == expected_domains,
    "authorized upstream domains canonical",
)

check(
    contract["authorized_upstream_domains"]
    == policy["authorized_domains"],
    "runtime domains match Evidence Gate policy",
)

# ------------------------------------------------------------
# Upstream consumption
# ------------------------------------------------------------

upstream = contract["upstream_consumption"]

expected_upstream = [
    "score",
    "coverage",
    "confidence",
    "publication_eligibility",
    "risk",
    "domain_signals",
    "provenance",
    "catalysts",
    "institutional_flow",
    "portfolio",
    "market_regime",
]

check(
    list(upstream.keys()) == expected_upstream,
    "upstream consumption domains exact",
)

for name in expected_upstream:
    check(
        upstream[name]["consume"] is True,
        f"{name} consumed",
    )

    check(
        upstream[name]["recalculate"] is False,
        f"{name} not recalculated",
    )

check(
    upstream["publication_eligibility"]["override"] is False,
    "publication eligibility not overridden",
)

check(
    upstream["provenance"]["invent"] is False,
    "provenance not invented",
)

check(
    upstream["provenance"]["repair"] is False,
    "provenance not repaired",
)

# ------------------------------------------------------------
# Threshold governance
# ------------------------------------------------------------

thresholds = contract["threshold_governance"]

for key, value in thresholds.items():
    check(value is False, f"threshold governance {key} false")

# ------------------------------------------------------------
# Result contract
# ------------------------------------------------------------

result = contract["result_contract"]

check(
    result["storage_mode"] == "TRANSIENT_SIDECAR",
    "Evidence Gate result is transient sidecar",
)

check(
    result["persist_in_asset"] is False,
    "Evidence Gate result not persisted in asset",
)

check(
    result["persist_in_radar_root"] is False,
    "Evidence Gate result not persisted in radar root",
)

check(
    result["write_decision_center"] is False,
    "Evidence Gate result does not write decision center",
)

expected_fields = [
    "ticker",
    "gate_status",
    "evidence_gate_passed",
    "admissible_evidence",
    "restricted_evidence",
    "blocked_evidence",
    "insufficient_evidence",
    "unknown_evidence",
    "reasons",
]

check(
    result["per_ticker_required_fields"] == expected_fields,
    "per-ticker result fields canonical",
)

expected_statuses = [
    "PASSED",
    "RESTRICTED",
    "BLOCKED",
    "INSUFFICIENT",
    "UNKNOWN",
]

check(
    result["gate_status_allowed_values"] == expected_statuses,
    "gate status values canonical",
)

expected_pass_semantics = {
    "PASSED": True,
    "RESTRICTED": False,
    "BLOCKED": False,
    "INSUFFICIENT": False,
    "UNKNOWN": False,
}

check(
    result["evidence_gate_passed_semantics"]
    == expected_pass_semantics,
    "gate pass semantics fail closed",
)

expected_buckets = {
    "admissible_evidence": "ADMISSIBLE",
    "restricted_evidence": "RESTRICTED",
    "blocked_evidence": "BLOCKED",
    "insufficient_evidence": "INSUFFICIENT",
    "unknown_evidence": "UNKNOWN",
}

check(
    result["evidence_buckets"] == expected_buckets,
    "evidence bucket mapping canonical",
)

# ------------------------------------------------------------
# Evidence item
# ------------------------------------------------------------

item = contract["evidence_item_contract"]

check(
    item["required_fields"]
    == [
        "evidence_id",
        "domain",
        "information_class",
        "gate_result",
        "reason_code",
    ],
    "evidence item required fields canonical",
)

check(
    item["information_class_allowed_values"]
    == ["FACT", "MODEL", "INFERENCE"],
    "evidence information classes canonical",
)

check(
    item["gate_result_allowed_values"]
    == [
        "ADMISSIBLE",
        "RESTRICTED",
        "BLOCKED",
        "INSUFFICIENT",
        "UNKNOWN",
    ],
    "evidence gate results canonical",
)

check(
    item["decision_is_evidence"] is False,
    "DECISION is not evidence",
)

check(
    item["reason_code_required"] is True,
    "reason code required",
)

check(item["domain_required"] is True, "domain required")

check(
    item["information_class_required"] is True,
    "information class required",
)

# ------------------------------------------------------------
# Reason contract
# ------------------------------------------------------------

reason = contract["reason_contract"]

check(
    reason["required_fields"]
    == [
        "reason_code",
        "domain",
        "information_class",
        "gate_result",
    ],
    "reason required fields canonical",
)

for key in [
    "must_be_traceable",
    "blocked_reason_must_be_preserved",
    "insufficient_reason_must_be_preserved",
    "unknown_reason_must_be_preserved",
]:
    check(reason[key] is True, f"reason contract {key} true")

# ------------------------------------------------------------
# Missing semantics
# ------------------------------------------------------------

missing = contract["missing_semantics"]

for key in [
    "missing_is_neutral",
    "missing_is_negative",
    "missing_is_positive",
    "missing_is_zero",
    "missing_is_admissible",
]:
    check(missing[key] is False, f"{key} false")

check(
    missing["missing_required_evidence_result"] == "INSUFFICIENT",
    "missing required evidence remains INSUFFICIENT",
)

# ------------------------------------------------------------
# Publication boundary
# ------------------------------------------------------------

publication = contract["publication_boundary"]

check(
    publication["consume_upstream_publication_eligibility"] is True,
    "consume upstream publication eligibility",
)

check(
    publication["may_override_publication_eligibility"] is False,
    "cannot override publication eligibility",
)

check(
    publication["may_promote_publication_ineligible_evidence"] is False,
    "cannot promote publication-ineligible evidence",
)

check(
    publication["publication_ineligible_where_required_result"]
    == "BLOCKED",
    "publication ineligible required -> BLOCKED",
)

# ------------------------------------------------------------
# Provenance boundary
# ------------------------------------------------------------

provenance = contract["provenance_boundary"]

check(
    provenance["consume_upstream_provenance"] is True,
    "consume upstream provenance",
)

check(
    provenance["may_invent_provenance"] is False,
    "cannot invent provenance",
)

check(
    provenance["may_repair_invalid_provenance"] is False,
    "cannot repair provenance",
)

check(
    provenance["invalid_required_provenance_result"] == "BLOCKED",
    "invalid required provenance -> BLOCKED",
)

check(
    provenance["unknown_required_provenance_result"] == "UNKNOWN",
    "unknown required provenance -> UNKNOWN",
)

# ------------------------------------------------------------
# Conflict boundary
# ------------------------------------------------------------

conflict = contract["conflict_boundary"]

check(
    conflict["preserve_multiple_evidence_items"] is True,
    "multiple evidence items preserved",
)

check(
    conflict["preserve_conflicting_admissible_evidence"] is True,
    "conflicting admissible evidence preserved",
)

check(
    conflict["detect_semantic_conflict"] is False,
    "D.3 does not detect semantic conflict",
)

check(
    conflict["resolve_conflict"] is False,
    "D.3 does not resolve conflict",
)

check(
    conflict["conflict_resolver_phase"] == "D.4",
    "conflict resolver remains D.4",
)

# ------------------------------------------------------------
# Decision boundary
# ------------------------------------------------------------

decision = contract["decision_boundary"]

for key in [
    "gate_result_is_decision_state",
    "gate_status_is_decision_state",
    "evidence_gate_passed_is_actionable_authority",
    "admissible_evidence_is_actionable_authority",
    "may_select_ACTIONABLE",
    "may_select_WATCH",
    "may_select_WAIT_FOR_CONFIRMATION",
    "may_select_RISK_REVIEW",
    "may_select_THESIS_REVIEW",
    "may_select_INSUFFICIENT_EVIDENCE",
]:
    check(decision[key] is False, f"decision boundary {key} false")

check(
    decision["decision_state_phase"] == "D.5",
    "decision state remains D.5",
)

check(
    decision["actionable_authority_policy"]
    == "RADAR_V3_ACTIONABLE_AUTHORITY_POLICY",
    "actionable authority policy canonical",
)

# ------------------------------------------------------------
# Mutation boundary
# ------------------------------------------------------------

mutation = contract["mutation_boundary"]

for key, value in mutation.items():
    check(value is False, f"mutation boundary {key} false")

# ------------------------------------------------------------
# Phase boundary
# ------------------------------------------------------------

phase = contract["phase_boundaries"]

check(
    phase["D3D2_defines_runtime_contract"] is True,
    "D.3D.2 defines runtime contract",
)

check(
    phase["D3D2_implements_engine"] is False,
    "D.3D.2 does not implement engine",
)

check(
    phase["evidence_gate_engine_phase"] == "D.3",
    "Evidence Gate engine remains D.3",
)

check(
    phase["conflict_resolver_phase"] == "D.4",
    "Conflict Resolver remains D.4",
)

check(
    phase["decision_state_engine_phase"] == "D.5",
    "Decision State Engine remains D.5",
)

check(
    phase["traceability_phase"] == "D.6",
    "Traceability remains D.6",
)

check(
    phase["generator_integration_phase"] == "D.7",
    "Generator integration remains D.7",
)

# ------------------------------------------------------------
# Prohibitions
# ------------------------------------------------------------

mandatory_prohibitions = {
    "MODIFY_V2_1",
    "MODIFY_SCHEMA_V3_IN_D3D2",
    "MODIFY_GENERATOR_IN_D3D2",
    "WRITE_DECISION_CENTER_IN_D3D2",
    "MUTATE_ASSET_IN_EVIDENCE_GATE",
    "MUTATE_RADAR_IN_EVIDENCE_GATE",
    "PERSIST_EVIDENCE_GATE_IN_ASSET",
    "PERSIST_EVIDENCE_GATE_IN_RADAR_ROOT",
    "RECALCULATE_SCORE",
    "RECALCULATE_COVERAGE",
    "RECALCULATE_CONFIDENCE",
    "RECALCULATE_RISK",
    "RECALCULATE_SIGNALS",
    "RECALCULATE_PUBLICATION_ELIGIBILITY",
    "RECALCULATE_PROVENANCE",
    "INVENT_PROVENANCE",
    "REPAIR_INVALID_PROVENANCE",
    "REDEFINE_UPSTREAM_NUMERIC_THRESHOLDS",
    "REDEFINE_PUBLICATION_SOURCE_TIERS",
    "OVERRIDE_PUBLICATION_ELIGIBILITY",
    "PROMOTE_PUBLICATION_INELIGIBLE_EVIDENCE",
    "TREAT_MISSING_AS_NEUTRAL",
    "TREAT_MISSING_AS_ZERO",
    "TREAT_MISSING_AS_ADMISSIBLE",
    "DISCARD_BLOCKED_EVIDENCE",
    "DISCARD_INSUFFICIENT_EVIDENCE",
    "DISCARD_UNKNOWN_EVIDENCE",
    "RESOLVE_CONFLICTS_IN_D3",
    "SELECT_DECISION_STATE_IN_D3",
    "CREATE_ACTIONABLE_AUTHORITY_FROM_GATE_PASS",
    "CREATE_ACTIONABLE_AUTHORITY_FROM_ADMISSIBLE_EVIDENCE",
    "TRANSLATE_GATE_PASS_TO_BUY",
    "TRANSLATE_GATE_PASS_TO_SELL",
    "EXECUTE_TRADE_FROM_EVIDENCE_GATE",
}

check(
    mandatory_prohibitions.issubset(
        set(contract["prohibited_behaviors"])
    ),
    "all mandatory runtime prohibitions present",
)

# ------------------------------------------------------------
# Cross-contract checks
# ------------------------------------------------------------

check(
    set(item["gate_result_allowed_values"])
    == set(policy["gate_results"].keys()),
    "runtime evidence results match D.3B policy",
)

check(
    contract["missing_semantics"]["missing_required_evidence_result"]
    == policy["fail_closed"]["missing_required_evidence"],
    "runtime missing behavior matches D.3B",
)

check(
    contract["provenance_boundary"]["invalid_required_provenance_result"]
    == policy["provenance_policy"]["invalid_required_provenance_result"],
    "runtime invalid provenance behavior matches D.3B",
)

check(
    contract["publication_boundary"][
        "publication_ineligible_where_required_result"
    ]
    == policy["publication_policy"][
        "publication_ineligible_where_required_result"
    ],
    "runtime publication behavior matches D.3B",
)

# ------------------------------------------------------------
# Result
# ------------------------------------------------------------

print()
print("=" * 60)
print(" D.3D.2 - EVIDENCE GATE RUNTIME CONTRACT TEST")
print("=" * 60)
print(f"Checks executed: {checks}")
print(f"Failures: {len(failures)}")

if failures:
    print("RESULT: REJECTED")
    for failure in failures:
        print(f" - {failure}")
    raise SystemExit(1)

print("RESULT: APPROVED")
