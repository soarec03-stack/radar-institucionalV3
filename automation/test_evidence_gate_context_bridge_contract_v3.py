import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent

CONTRACT_PATH = ROOT / "evidence_gate_context_bridge_contract_v3.json"
GATE_POLICY_PATH = ROOT / "evidence_gate_policy_v3.json"
RUNTIME_CONTRACT_PATH = ROOT / "evidence_gate_runtime_contract_v3.json"


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


contract = load_json(CONTRACT_PATH)
gate_policy = load_json(GATE_POLICY_PATH)
runtime_contract = load_json(RUNTIME_CONTRACT_PATH)


print("=" * 76)
print(" D.3D.4B - EVIDENCE GATE RUNTIME CONTEXT BRIDGE CONTRACT TEST")
print("=" * 76)


# ============================================================
# A. IDENTITY / SCOPE
# ============================================================

check(
    contract.get("contract_id")
    == "RADAR_V3_EVIDENCE_GATE_CONTEXT_BRIDGE_CONTRACT",
    "contract id canonical",
)

check(
    contract.get("contract_version") == "3.4D.3D.4B",
    "contract version canonical",
)

check(
    contract.get("status") == "DRAFT",
    "contract remains DRAFT",
)

check(
    contract.get("scope") == "V3_ONLY",
    "scope V3 only",
)


# ============================================================
# B. PURPOSE
# ============================================================

purpose = contract["purpose"]

check(
    purpose["defines_runtime_context_bridge"] is True,
    "defines runtime context bridge",
)

for key in [
    "implements_runtime_context_bridge",
    "implements_evidence_gate_engine",
    "defines_evidence_admissibility_policy",
    "recalculates_upstream_results",
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


# ============================================================
# C. COMPATIBILITY
# ============================================================

compat = contract["compatibility"]

check(
    compat["preserve_v2_1"] is True,
    "V2.1 preserved",
)

for key in [
    "modify_v2_1",
    "modify_schema_v3",
    "modify_generator",
    "modify_existing_decision_center_contract",
    "modify_public_output",
    "modify_b2k_fixtures",
]:
    check(
        compat[key] is False,
        f"compatibility.{key} false",
    )


# ============================================================
# D. REFERENCES
# ============================================================

refs = contract["references"]

check(
    refs["evidence_gate_policy_id"]
    == gate_policy["policy_id"],
    "references current Evidence Gate policy id",
)

check(
    refs["evidence_gate_policy_version"]
    == gate_policy["policy_version"],
    "references current Evidence Gate policy version",
)

check(
    refs["evidence_gate_runtime_contract_id"]
    == runtime_contract["contract_id"],
    "references current runtime contract id",
)

check(
    refs["evidence_gate_runtime_contract_version"]
    == runtime_contract["contract_version"],
    "references current runtime contract version",
)


# ============================================================
# E. ARCHITECTURAL ROLE
# ============================================================

role = contract["architectural_role"]

check(
    role["input"] == "UPSTREAM_RUNTIME_STATE",
    "bridge input canonical",
)

check(
    role["output"] == "EVIDENCE_GATE_RUNTIME_INPUTS",
    "bridge output canonical",
)

check(
    role["consumer"] == "EVIDENCE_GATE",
    "Evidence Gate is bridge consumer",
)

check(
    role["output_is_transient"] is True,
    "bridge output transient",
)

for key in [
    "output_is_public_schema",
    "may_persist_output",
    "may_write_asset",
    "may_write_radar_root",
    "may_write_decision_center",
]:
    check(
        role[key] is False,
        f"architectural_role.{key} false",
    )


# ============================================================
# F. OWNERSHIP
# ============================================================

ownership = contract["ownership"]

expected_owners = {
    "enriched_asset_state": "UPSTREAM_PIPELINE",
    "domain_signals": "SIGNAL_ENGINE",
    "publication_context": "PUBLICATION_ELIGIBILITY",
    "risk_source_context": "RISK_AND_PUBLICATION_RUNTIME",
    "score": "SCORE_ENGINE",
    "confidence": "CONFIDENCE_ENGINE",
    "risk": "RISK_ENGINE",
    "provenance": "UPSTREAM_PROVENANCE_PIPELINE",
}

check(
    set(ownership.keys()) == set(expected_owners.keys()),
    "ownership domains exact",
)

for domain, owner in expected_owners.items():
    entry = ownership[domain]

    check(
        entry["owner"] == owner,
        f"{domain}: owner canonical",
    )

    check(
        entry["bridge_role"] == "TRANSPORT_ONLY",
        f"{domain}: bridge role transport only",
    )


check(
    ownership["domain_signals"]["source_runtime_field"]
    == "asset.signals",
    "signals source runtime field canonical",
)

check(
    ownership["publication_context"]["destination_argument"]
    == "publication_context_by_ticker",
    "publication destination argument canonical",
)

check(
    ownership["risk_source_context"]["destination_argument"]
    == "risk_source_context_by_ticker",
    "risk sidecar destination argument canonical",
)


# ============================================================
# G. OUTPUT CONTRACT
# ============================================================

output = contract["bridge_output_contract"]

check(
    output["type"] == "TRANSIENT_RUNTIME_CONTEXT",
    "bridge output type canonical",
)

check(
    output["required_fields"]
    == [
        "radar",
        "publication_context_by_ticker",
        "risk_source_context_by_ticker",
    ],
    "bridge required fields exact",
)

check(
    output["radar"]["source"]
    == "ENRICHED_UPSTREAM_RADAR",
    "radar source is enriched upstream runtime",
)

check(
    output["radar"]["must_preserve_upstream_asset_state"]
    is True,
    "bridge preserves upstream asset state",
)

check(
    output["radar"]["may_mutate_source_radar"] is False,
    "bridge cannot mutate source radar",
)

check(
    output["radar"]["may_create_missing_signals"] is False,
    "bridge cannot create missing signals",
)

check(
    output["radar"]["may_translate_legacy_score"] is False,
    "bridge cannot translate legacy score",
)

check(
    output["radar"]["may_create_missing_provenance"] is False,
    "bridge cannot create missing provenance",
)

for name in [
    "publication_context_by_ticker",
    "risk_source_context_by_ticker",
]:
    entry = output[name]

    check(
        entry["type"] == "DICT_BY_TICKER",
        f"{name}: dict by ticker",
    )

    check(
        entry["may_be_empty"] is True,
        f"{name}: may be empty",
    )

    check(
        entry["missing_context_behavior"]
        == "PRESERVE_ABSENCE",
        f"{name}: missing context preserves absence",
    )

    check(
        entry["may_synthesize_missing_ticker"] is False,
        f"{name}: cannot synthesize missing ticker",
    )


# ============================================================
# H. EVIDENCE GATE INVOCATION
# ============================================================

invoke = contract["evidence_gate_invocation_contract"]

check(
    invoke["function"] == "apply_evidence_gate",
    "bridge targets canonical Evidence Gate API",
)

check(
    invoke["arguments"]
    == [
        "radar",
        "evidence_gate_policy",
        "publication_context_by_ticker",
        "risk_source_context_by_ticker",
    ],
    "Evidence Gate invocation arguments exact",
)

check(
    invoke["argument_mapping"]
    == {
        "radar": "bridge_output.radar",
        "publication_context_by_ticker":
            "bridge_output.publication_context_by_ticker",
        "risk_source_context_by_ticker":
            "bridge_output.risk_source_context_by_ticker",
    },
    "bridge argument mapping canonical",
)

check(
    invoke["bridge_may_change_evidence_gate_api"] is False,
    "bridge cannot change Evidence Gate API",
)

check(
    invoke["bridge_may_bypass_evidence_gate"] is False,
    "bridge cannot bypass Evidence Gate",
)


# ============================================================
# I. ABSENCE SEMANTICS
# ============================================================

absence = contract["absence_semantics"]

for key in [
    "missing_signal_context",
    "missing_publication_context",
    "missing_risk_source_context",
    "missing_score_runtime_fields",
    "missing_provenance",
]:
    check(
        absence[key] == "PRESERVE_ABSENCE",
        f"{key}: preserve absence",
    )

for key in [
    "missing_is_neutral",
    "missing_is_negative",
    "missing_is_positive",
    "missing_is_zero",
    "missing_is_admissible",
    "bridge_may_fill_missing_with_defaults",
    "bridge_may_fill_missing_with_legacy_values",
    "bridge_may_convert_missing_to_pass",
]:
    check(
        absence[key] is False,
        f"absence_semantics.{key} false",
    )


# ============================================================
# J. LEGACY B2K BOUNDARY
# ============================================================

legacy = contract["legacy_data_boundary"]

check(
    legacy["legacy_b2k_score_may_be_detected"] is True,
    "legacy B2K score may be detected",
)

for key in [
    "legacy_b2k_score_may_be_translated",
    "legacy_b2k_score_may_be_promoted",
    "legacy_b2k_missing_signals_may_be_reconstructed",
    "legacy_b2k_missing_publication_context_may_be_reconstructed",
    "legacy_b2k_missing_risk_context_may_be_reconstructed",
]:
    check(
        legacy[key] is False,
        f"legacy boundary.{key} false",
    )

check(
    legacy["legacy_fixture_is_not_runtime_authority"] is True,
    "legacy fixture is not runtime authority",
)


# ============================================================
# K. PUBLICATION BOUNDARY
# ============================================================

publication = contract["publication_boundary"]

check(
    publication["consume_upstream_publication_context"] is True,
    "consume upstream publication context",
)

for key in [
    "recalculate_publication_eligibility",
    "override_publication_eligibility",
    "promote_publication_ineligible",
    "infer_publication_eligibility_from_score_publishable",
]:
    check(
        publication[key] is False,
        f"publication_boundary.{key} false",
    )

check(
    publication["missing_publication_context"]
    == "PRESERVE_ABSENCE",
    "missing publication context preserved",
)


# ============================================================
# L. SIGNAL BOUNDARY
# ============================================================

signal = contract["signal_boundary"]

check(
    signal["consume_upstream_signals"] is True,
    "consume upstream signals",
)

for key in [
    "recalculate_signals",
    "infer_signals_from_score",
    "infer_signals_from_metrics",
    "infer_signals_from_price",
]:
    check(
        signal[key] is False,
        f"signal_boundary.{key} false",
    )

check(
    signal["missing_signals"] == "PRESERVE_ABSENCE",
    "missing signals preserved",
)


# ============================================================
# M. RISK BOUNDARY
# ============================================================

risk = contract["risk_boundary"]

check(
    risk["consume_upstream_risk"] is True,
    "consume upstream risk",
)

check(
    risk["consume_upstream_risk_source_context"] is True,
    "consume upstream risk source context",
)

for key in [
    "recalculate_risk",
    "rebuild_risk_source_context",
    "infer_risk_source_context_from_public_risk",
]:
    check(
        risk[key] is False,
        f"risk_boundary.{key} false",
    )

check(
    risk["missing_risk_source_context"]
    == "PRESERVE_ABSENCE",
    "missing risk source context preserved",
)


# ============================================================
# N. SCORE BOUNDARY
# ============================================================

score = contract["score_boundary"]

check(
    score["consume_upstream_score"] is True,
    "consume upstream score",
)

for key in [
    "recalculate_score",
    "translate_legacy_score",
    "infer_score_status",
    "infer_score_coverage",
    "infer_score_publishable",
    "infer_analytically_usable",
]:
    check(
        score[key] is False,
        f"score_boundary.{key} false",
    )


# ============================================================
# O. PROVENANCE BOUNDARY
# ============================================================

provenance = contract["provenance_boundary"]

check(
    provenance["consume_upstream_provenance"] is True,
    "consume upstream provenance",
)

for key in [
    "recalculate_provenance",
    "invent_provenance",
    "repair_provenance",
    "infer_provenance_from_source_name",
]:
    check(
        provenance[key] is False,
        f"provenance_boundary.{key} false",
    )

check(
    provenance["missing_provenance"] == "PRESERVE_ABSENCE",
    "missing provenance preserved",
)


# ============================================================
# P. MUTATION BOUNDARY
# ============================================================

mutation = contract["mutation_boundary"]

for key, value in mutation.items():
    check(
        value is False,
        f"mutation_boundary.{key} false",
    )


# ============================================================
# Q. DECISION BOUNDARY
# ============================================================

decision = contract["decision_boundary"]

for key in [
    "may_select_decision_state",
    "may_establish_actionable_authority",
    "may_resolve_conflicts",
    "may_create_buy_signal",
    "may_create_sell_signal",
    "may_create_trade_instruction",
]:
    check(
        decision[key] is False,
        f"decision_boundary.{key} false",
    )

check(
    decision["conflict_resolution_owner"] == "D.4",
    "Conflict Resolver remains D.4",
)

check(
    decision["decision_state_owner"] == "D.5",
    "Decision State remains D.5",
)

check(
    decision["traceability_owner"] == "D.6",
    "Traceability remains D.6",
)

check(
    decision["generator_integration_owner"] == "D.7",
    "Generator integration remains D.7",
)


# ============================================================
# R. IMPLEMENTATION BOUNDARY
# ============================================================

implementation = contract["implementation_boundary"]

check(
    implementation["this_step_defines_contract_only"] is True,
    "D.3D.4B defines contract only",
)

for key in [
    "bridge_implementation_allowed_in_this_step",
    "generator_integration_allowed_in_this_step",
    "schema_change_allowed_in_this_step",
    "fixture_rewrite_allowed_in_this_step",
    "evidence_gate_engine_change_allowed_in_this_step",
]:
    check(
        implementation[key] is False,
        f"implementation_boundary.{key} false",
    )


# ============================================================
# S. PROHIBITIONS
# ============================================================

prohibited = set(contract["prohibited_behaviors"])

required_prohibitions = {
    "RECALCULATE_SCORE",
    "TRANSLATE_LEGACY_SCORE",
    "INVENT_SCORE_STATUS",
    "INVENT_SCORE_COVERAGE",
    "INVENT_SCORE_PUBLISHABLE",
    "RECALCULATE_CONFIDENCE",
    "RECALCULATE_SIGNALS",
    "INFER_SIGNALS_FROM_SCORE",
    "INFER_SIGNALS_FROM_METRICS",
    "INFER_SIGNALS_FROM_PRICE",
    "RECALCULATE_RISK",
    "REBUILD_RISK_SOURCE_CONTEXT",
    "INFER_RISK_SOURCE_CONTEXT_FROM_PUBLIC_RISK",
    "RECALCULATE_PUBLICATION_ELIGIBILITY",
    "OVERRIDE_PUBLICATION_ELIGIBILITY",
    "PROMOTE_PUBLICATION_INELIGIBLE",
    "INFER_PUBLICATION_ELIGIBILITY_FROM_SCORE_PUBLISHABLE",
    "RECALCULATE_PROVENANCE",
    "INVENT_PROVENANCE",
    "REPAIR_PROVENANCE",
    "FILL_MISSING_WITH_DEFAULTS",
    "FILL_MISSING_WITH_LEGACY_VALUES",
    "CONVERT_MISSING_TO_PASS",
    "MUTATE_RADAR",
    "MUTATE_ASSET",
    "MUTATE_PUBLICATION_CONTEXT",
    "MUTATE_RISK_SOURCE_CONTEXT",
    "WRITE_EVIDENCE_GATE_RESULT",
    "WRITE_DECISION_CENTER",
    "SELECT_DECISION_STATE",
    "ESTABLISH_ACTIONABLE_AUTHORITY",
    "RESOLVE_CONFLICT",
    "MODIFY_SCHEMA_V3",
    "MODIFY_GENERATOR",
    "MODIFY_V2_1",
    "REWRITE_B2K_FIXTURES",
}

check(
    prohibited == required_prohibitions,
    "mandatory bridge prohibitions exact",
)


# ============================================================
# T. CROSS-CONTRACT CONSISTENCY
# ============================================================

runtime_functions = runtime_contract["runtime_functions"]

check(
    "apply_evidence_gate" in runtime_functions,
    "runtime contract exposes apply_evidence_gate",
)

apply_contract = runtime_functions["apply_evidence_gate"]

check(
    apply_contract["inputs"]
    == invoke["arguments"],
    "bridge invocation matches runtime contract inputs",
)

check(
    runtime_contract["mutation_boundary"]["modify_generator"]
    is False,
    "runtime contract still prohibits Generator modification",
)

check(
    runtime_contract["mutation_boundary"]["modify_schema_v3"]
    is False,
    "runtime contract still prohibits schema modification",
)

check(
    gate_policy["upstream_ownership"]["recalculate_signals"]
    is False,
    "Evidence Gate policy still prohibits signal recalculation",
)

check(
    gate_policy["upstream_ownership"][
        "recalculate_publication_eligibility"
    ]
    is False,
    "Evidence Gate policy still prohibits publication recalculation",
)

check(
    gate_policy["upstream_ownership"]["recalculate_provenance"]
    is False,
    "Evidence Gate policy still prohibits provenance recalculation",
)


# ============================================================
# U. FINAL
# ============================================================

print()
print("=" * 76)
print(" D.3D.4B - CONTEXT BRIDGE CONTRACT RESULT")
print("=" * 76)
print(f"Checks executed: {checks}")
print(f"Failures: {len(failures)}")

if failures:
    print("RESULT: FAILED")

    for failure in failures:
        print(f" - {failure}")

    raise SystemExit(1)

print("RESULT: APPROVED")
