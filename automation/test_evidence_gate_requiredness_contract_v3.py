import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent

CONTRACT_PATH = ROOT / "evidence_gate_requiredness_contract_v3.json"
POLICY_PATH = ROOT / "evidence_gate_policy_v3.json"
RUNTIME_PATH = ROOT / "evidence_gate_runtime_contract_v3.json"
BRIDGE_PATH = ROOT / "evidence_gate_context_bridge_contract_v3.json"


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
policy = load_json(POLICY_PATH)
runtime = load_json(RUNTIME_PATH)
bridge = load_json(BRIDGE_PATH)


print("=" * 78)
print(" D.3D.4D - EVIDENCE GATE REQUIREDNESS CONTRACT TEST")
print("=" * 78)


# ============================================================
# A. IDENTITY
# ============================================================

check(
    contract["contract_id"]
    == "RADAR_V3_EVIDENCE_GATE_REQUIREDNESS_CONTRACT",
    "contract id canonical",
)

check(
    contract["contract_version"] == "3.4D.3D.4D",
    "contract version canonical",
)

check(contract["status"] == "DRAFT", "contract remains DRAFT")
check(contract["scope"] == "V3_ONLY", "scope V3 only")


# ============================================================
# B. PURPOSE
# ============================================================

purpose = contract["purpose"]

check(
    purpose["defines_evidence_requiredness"] is True,
    "defines evidence requiredness",
)

for key in (
    "defines_evidence_admissibility",
    "defines_numeric_thresholds",
    "duplicates_upstream_thresholds",
    "recalculates_upstream_results",
    "implements_evidence_gate_engine",
    "implements_context_bridge",
    "defines_conflict_resolution",
    "defines_decision_state",
    "defines_actionable_authority",
    "writes_decision_center",
    "modifies_public_output",
):
    check(
        purpose[key] is False,
        f"purpose.{key} false",
    )


# ============================================================
# C. COMPATIBILITY
# ============================================================

compatibility = contract["compatibility"]

check(
    compatibility["preserve_v2_1"] is True,
    "V2.1 preserved",
)

for key in (
    "modify_v2_1",
    "modify_schema_v3",
    "modify_generator",
    "modify_existing_decision_center_contract",
    "modify_public_output",
    "modify_b2k_fixtures",
):
    check(
        compatibility[key] is False,
        f"compatibility.{key} false",
    )


# ============================================================
# D. REFERENCES
# ============================================================

refs = contract["references"]

check(
    refs["evidence_gate_policy_id"] == policy["policy_id"],
    "references canonical Evidence Gate policy",
)

check(
    refs["evidence_gate_policy_version"] == policy["policy_version"],
    "references canonical Evidence Gate policy version",
)

check(
    refs["evidence_gate_runtime_contract_id"]
    == runtime["contract_id"],
    "references canonical runtime contract",
)

check(
    refs["context_bridge_contract_id"]
    == bridge["contract_id"],
    "references canonical context bridge contract",
)

check(
    refs["context_bridge_contract_version"]
    == bridge["contract_version"],
    "references canonical context bridge version",
)


# ============================================================
# E. REQUIREDNESS CLASSES
# ============================================================

classes = contract["requiredness_classes"]

check(
    set(classes.keys())
    == {"REQUIRED", "CONDITIONAL", "OPTIONAL"},
    "requiredness classes exact",
)

required_class = classes["REQUIRED"]

check(
    required_class["missing_result"] == "INSUFFICIENT",
    "REQUIRED missing -> INSUFFICIENT",
)

for key in (
    "may_be_imputed",
    "may_be_defaulted",
    "may_be_reconstructed",
    "absence_is_neutral",
    "absence_is_negative",
    "absence_is_positive",
):
    check(
        required_class[key] is False,
        f"REQUIRED.{key} false",
    )

conditional_class = classes["CONDITIONAL"]

check(
    conditional_class["condition_source"]
    == "UPSTREAM_EXPLICIT_CONTEXT_ONLY",
    "CONDITIONAL uses explicit upstream condition",
)

check(
    conditional_class["missing_when_condition_applies_result"]
    == "INSUFFICIENT",
    "CONDITIONAL missing when applicable -> INSUFFICIENT",
)

check(
    conditional_class["missing_when_condition_does_not_apply_result"]
    == "NOT_REQUIRED",
    "CONDITIONAL missing when not applicable -> NOT_REQUIRED",
)

for key in (
    "may_infer_condition_from_missing_data",
    "may_infer_condition_from_score_magnitude",
    "may_infer_condition_from_risk_magnitude",
    "may_infer_condition_from_signal_magnitude",
    "may_be_imputed",
    "may_be_defaulted",
    "may_be_reconstructed",
):
    check(
        conditional_class[key] is False,
        f"CONDITIONAL.{key} false",
    )

optional_class = classes["OPTIONAL"]

check(
    optional_class["missing_result"] == "NOT_REQUIRED",
    "OPTIONAL missing -> NOT_REQUIRED",
)

check(
    optional_class["presence_does_not_guarantee_admissibility"]
    is True,
    "OPTIONAL presence does not guarantee admissibility",
)

for key in (
    "may_be_imputed",
    "may_be_defaulted",
    "may_be_reconstructed",
):
    check(
        optional_class[key] is False,
        f"OPTIONAL.{key} false",
    )


# ============================================================
# F. REQUIRED BASELINE
# ============================================================

required = contract["required_evidence"]

expected_required = {
    "score",
    "coverage",
    "confidence",
    "risk",
    "domain_signals",
    "price_provenance",
}

check(
    set(required.keys()) == expected_required,
    "required evidence baseline exact",
)

for name in sorted(expected_required):
    check(
        required[name]["requiredness"] == "REQUIRED",
        f"{name} is REQUIRED",
    )

    check(
        required[name]["missing_result"] == "INSUFFICIENT",
        f"{name} missing -> INSUFFICIENT",
    )


# ============================================================
# G. SCORE
# ============================================================

score = required["score"]

check(
    score["domain"] == "RADAR_SCORE",
    "score domain canonical",
)

check(
    score["canonical_runtime_source"] == "asset.score",
    "score runtime source canonical",
)

check(
    score["required_runtime_fields"]
    == ["status", "analytically_usable", "publishable"],
    "score required runtime fields exact",
)

check(
    score["legacy_shape_is_canonical_runtime_evidence"] is False,
    "legacy score shape is not canonical runtime evidence",
)

check(
    score["may_translate_legacy_shape"] is False,
    "legacy score cannot be translated",
)

check(
    score["may_infer_missing_fields"] is False,
    "missing score runtime fields cannot be inferred",
)

check(
    score["threshold_owner"] == "SCORE_ENGINE",
    "score threshold ownership preserved",
)


# ============================================================
# H. COVERAGE
# ============================================================

coverage = required["coverage"]

check(
    coverage["canonical_runtime_source"] == "asset.score.coverage",
    "coverage runtime source canonical",
)

check(
    coverage["may_calculate_from_components"] is False,
    "Gate cannot calculate coverage",
)

check(
    coverage["may_infer_from_score_status"] is False,
    "Gate cannot infer coverage from score status",
)

check(
    coverage["may_define_new_threshold"] is False,
    "Gate cannot define coverage threshold",
)

check(
    coverage["threshold_owner"] == "SCORE_ENGINE",
    "coverage threshold ownership preserved",
)


# ============================================================
# I. CONFIDENCE
# ============================================================

confidence = required["confidence"]

check(
    confidence["canonical_runtime_source"] == "asset.confidence",
    "confidence runtime source canonical",
)

check(
    confidence["required_runtime_fields"] == ["status"],
    "confidence required runtime fields exact",
)

for key in (
    "may_recalculate",
    "may_infer_status",
    "may_define_new_threshold",
):
    check(
        confidence[key] is False,
        f"confidence.{key} false",
    )

check(
    confidence["threshold_owner"] == "CONFIDENCE_ENGINE",
    "confidence threshold ownership preserved",
)


# ============================================================
# J. RISK
# ============================================================

risk = required["risk"]

check(
    risk["canonical_runtime_source"] == "asset.risk",
    "risk runtime source canonical",
)

for key in (
    "missing_is_low_risk",
    "missing_is_zero_risk",
    "may_recalculate",
    "may_infer_from_price",
    "may_define_new_threshold",
):
    check(
        risk[key] is False,
        f"risk.{key} false",
    )

check(
    risk["threshold_owner"] == "RISK_ENGINE",
    "risk threshold ownership preserved",
)


# ============================================================
# K. SIGNALS
# ============================================================

signals = required["domain_signals"]

check(
    signals["canonical_runtime_source"] == "asset.signals",
    "signals runtime source canonical",
)

check(
    signals["empty_result"] == "INSUFFICIENT",
    "empty signals -> INSUFFICIENT",
)

for key in (
    "may_recalculate",
    "may_infer_from_score",
    "may_infer_from_metrics",
    "may_infer_from_price",
    "may_define_new_threshold",
):
    check(
        signals[key] is False,
        f"signals.{key} false",
    )

check(
    signals["threshold_owner"] == "SIGNAL_ENGINE",
    "signal threshold ownership preserved",
)


# ============================================================
# L. PRICE PROVENANCE
# ============================================================

provenance = required["price_provenance"]

check(
    provenance["canonical_runtime_source"]
    == "asset.provenance.price",
    "price provenance runtime source canonical",
)

check(
    provenance["invalid_result"] == "BLOCKED",
    "invalid price provenance -> BLOCKED",
)

check(
    provenance["unknown_result"] == "UNKNOWN",
    "unknown price provenance -> UNKNOWN",
)

for key in (
    "may_invent",
    "may_repair",
    "may_infer_from_price_presence",
    "may_infer_from_source_name",
):
    check(
        provenance[key] is False,
        f"price provenance.{key} false",
    )


# ============================================================
# M. CONDITIONAL EVIDENCE
# ============================================================

conditional = contract["conditional_evidence"]

check(
    set(conditional.keys())
    == {"publication_context", "risk_source_context"},
    "conditional evidence set exact",
)

publication = conditional["publication_context"]

check(
    publication["requiredness"] == "CONDITIONAL",
    "publication context conditional",
)

check(
    publication["condition_must_be_explicit"] is True,
    "publication condition must be explicit",
)

check(
    publication["missing_when_condition_applies_result"]
    == "INSUFFICIENT",
    "missing applicable publication context -> INSUFFICIENT",
)

check(
    publication["missing_when_condition_does_not_apply_result"]
    == "NOT_REQUIRED",
    "non-applicable publication context -> NOT_REQUIRED",
)

for key in (
    "may_recalculate_publication_eligibility",
    "may_infer_condition_from_score_publishable",
    "may_assume_eligible_when_missing",
):
    check(
        publication[key] is False,
        f"publication context.{key} false",
    )

risk_context = conditional["risk_source_context"]

check(
    risk_context["requiredness"] == "CONDITIONAL",
    "risk source context conditional",
)

check(
    risk_context["condition_must_be_explicit"] is True,
    "risk context condition must be explicit",
)

check(
    risk_context["missing_when_condition_applies_result"]
    == "INSUFFICIENT",
    "missing applicable risk context -> INSUFFICIENT",
)

check(
    risk_context["missing_when_condition_does_not_apply_result"]
    == "NOT_REQUIRED",
    "non-applicable risk context -> NOT_REQUIRED",
)

for key in (
    "may_rebuild_from_public_risk",
    "may_infer_condition_from_risk_level",
    "may_assume_eligible_when_missing",
):
    check(
        risk_context[key] is False,
        f"risk context.{key} false",
    )


# ============================================================
# N. OPTIONAL EVIDENCE
# ============================================================

optional = contract["optional_evidence"]

expected_optional = {
    "catalysts",
    "institutional_flow",
    "portfolio",
    "market_regime",
}

check(
    set(optional.keys()) == expected_optional,
    "optional evidence set exact",
)

for name in sorted(expected_optional):
    check(
        optional[name]["requiredness"] == "OPTIONAL",
        f"{name} is OPTIONAL",
    )

    check(
        optional[name]["absence_alone_blocks_gate"] is False,
        f"{name} absence alone does not block Gate",
    )


# ============================================================
# O. MISSING SEMANTICS
# ============================================================

semantics = contract["requiredness_semantics"]

for key in (
    "required_missing_is_neutral",
    "required_missing_is_negative",
    "required_missing_is_positive",
    "required_missing_is_zero",
    "required_missing_is_admissible",
):
    check(
        semantics[key] is False,
        f"requiredness semantics.{key} false",
    )

check(
    semantics["required_missing_result"] == "INSUFFICIENT",
    "required missing canonical result",
)

check(
    semantics["optional_missing_is_failure"] is False,
    "optional missing is not failure",
)

check(
    semantics["optional_missing_is_admissible_evidence"] is False,
    "optional missing is not admissible evidence",
)

check(
    semantics["optional_missing_result"] == "NOT_REQUIRED",
    "optional missing canonical result",
)

check(
    semantics["conditional_requiredness_must_be_explicit"] is True,
    "conditional requiredness must be explicit",
)

check(
    semantics["conditional_requiredness_may_be_inferred_from_magnitude"]
    is False,
    "conditional requiredness cannot derive from magnitude",
)

check(
    semantics["conditional_requiredness_may_be_inferred_from_absence"]
    is False,
    "conditional requiredness cannot derive from absence",
)


# ============================================================
# P. THRESHOLD GOVERNANCE
# ============================================================

thresholds = contract["threshold_governance"]

for key in (
    "defines_new_numeric_thresholds",
    "duplicates_score_thresholds",
    "duplicates_confidence_thresholds",
    "duplicates_risk_thresholds",
    "duplicates_signal_thresholds",
    "duplicates_publication_source_tiers",
):
    check(
        thresholds[key] is False,
        f"threshold governance.{key} false",
    )

check(
    thresholds["consume_upstream_statuses_only"] is True,
    "requiredness consumes upstream statuses only",
)


# ============================================================
# Q. ENGINE ALIGNMENT
# ============================================================

alignment = contract["engine_alignment"]

check(
    alignment["required_baseline_exact"]
    == [
        "score",
        "coverage",
        "confidence",
        "risk",
        "domain_signals",
        "price_provenance",
    ],
    "engine required baseline exact",
)

check(
    alignment["must_not_silently_expand_required_baseline"] is True,
    "required baseline cannot silently expand",
)

check(
    alignment["must_not_silently_reduce_required_baseline"] is True,
    "required baseline cannot silently shrink",
)

check(
    alignment["engine_change_required_if_contract_changes"] is True,
    "engine must change when requiredness contract changes",
)

check(
    alignment["contract_change_required_if_engine_requiredness_changes"]
    is True,
    "contract must change when engine requiredness changes",
)


# ============================================================
# R. DECISION BOUNDARY
# ============================================================

decision = contract["decision_boundary"]

for key in (
    "requiredness_result_is_decision_state",
    "requiredness_result_is_actionable_authority",
    "requiredness_alone_may_select_ACTIONABLE",
    "requiredness_alone_may_select_WATCH",
    "requiredness_alone_may_select_WAIT_FOR_CONFIRMATION",
    "requiredness_alone_may_select_RISK_REVIEW",
    "requiredness_alone_may_select_THESIS_REVIEW",
    "requiredness_alone_may_select_INSUFFICIENT_EVIDENCE",
):
    check(
        decision[key] is False,
        f"decision boundary.{key} false",
    )

check(
    decision["decision_state_owner"] == "D.5",
    "Decision State remains D.5",
)

check(
    decision["conflict_resolution_owner"] == "D.4",
    "Conflict Resolver remains D.4",
)


# ============================================================
# S. MUTATION BOUNDARY
# ============================================================

mutation = contract["mutation_boundary"]

for key, value in mutation.items():
    check(
        value is False,
        f"mutation boundary.{key} false",
    )


# ============================================================
# T. PHASE BOUNDARY
# ============================================================

phase = contract["phase_boundary"]

check(
    phase["this_step"] == "D.3D.4D",
    "phase identity canonical",
)

check(
    phase["this_step_defines_requiredness_contract_only"] is True,
    "D.3D.4D contract only",
)

check(
    phase["adversarial_requiredness_test"] == "D.3D.4E",
    "adversarial requiredness reserved for D.3D.4E",
)

check(
    phase["generator_integration"] == "D.7",
    "Generator integration remains D.7",
)


# ============================================================
# U. CROSS-CONTRACT ALIGNMENT
# ============================================================

check(
    policy["missing_semantics"]["missing_required_result"]
    == "INSUFFICIENT",
    "Evidence Gate policy agrees required missing -> INSUFFICIENT",
)

check(
    runtime["missing_semantics"]["missing_required_evidence_result"]
    == "INSUFFICIENT",
    "runtime contract agrees required missing -> INSUFFICIENT",
)

check(
    runtime["publication_boundary"][
        "publication_ineligible_where_required_result"
    ]
    == "BLOCKED",
    "runtime publication boundary remains fail-closed",
)

check(
    bridge["absence_semantics"]["bridge_may_fill_missing_with_defaults"]
    is False,
    "bridge cannot fill required evidence with defaults",
)

check(
    bridge["absence_semantics"][
        "bridge_may_fill_missing_with_legacy_values"
    ]
    is False,
    "bridge cannot fill required evidence with legacy values",
)

check(
    bridge["absence_semantics"]["bridge_may_convert_missing_to_pass"]
    is False,
    "bridge cannot convert missing evidence to pass",
)

check(
    bridge["score_boundary"]["translate_legacy_score"] is False,
    "bridge cannot translate legacy score",
)

check(
    bridge["signal_boundary"]["recalculate_signals"] is False,
    "bridge cannot reconstruct required signals",
)

check(
    bridge["provenance_boundary"]["invent_provenance"] is False,
    "bridge cannot invent required provenance",
)


# ============================================================
# V. PROHIBITED BEHAVIORS
# ============================================================

expected_prohibitions = {
    "INVENT_REQUIRED_EVIDENCE",
    "IMPUTE_REQUIRED_EVIDENCE",
    "DEFAULT_REQUIRED_EVIDENCE",
    "TRANSLATE_LEGACY_SCORE",
    "INFER_REQUIRED_SCORE_FIELDS",
    "CALCULATE_COVERAGE_IN_GATE",
    "INFER_CONFIDENCE_STATUS",
    "TREAT_MISSING_RISK_AS_LOW",
    "TREAT_MISSING_RISK_AS_ZERO",
    "RECALCULATE_SIGNALS",
    "INFER_SIGNALS_FROM_SCORE",
    "INFER_SIGNALS_FROM_METRICS",
    "INFER_SIGNALS_FROM_PRICE",
    "INVENT_PROVENANCE",
    "REPAIR_PROVENANCE",
    "INFER_PROVENANCE_FROM_PRICE",
    "INFER_PROVENANCE_FROM_SOURCE_NAME",
    "ASSUME_PUBLICATION_ELIGIBLE",
    "RECALCULATE_PUBLICATION_ELIGIBILITY",
    "REBUILD_RISK_SOURCE_CONTEXT",
    "INFER_CONDITIONAL_REQUIREDNESS_FROM_MAGNITUDE",
    "INFER_CONDITIONAL_REQUIREDNESS_FROM_ABSENCE",
    "PROMOTE_OPTIONAL_EVIDENCE_TO_REQUIRED_SILENTLY",
    "DEMOTE_REQUIRED_EVIDENCE_TO_OPTIONAL_SILENTLY",
    "DEFINE_NEW_NUMERIC_THRESHOLDS",
    "DUPLICATE_UPSTREAM_THRESHOLDS",
    "SELECT_DECISION_STATE",
    "ESTABLISH_ACTIONABLE_AUTHORITY",
    "RESOLVE_CONFLICT",
    "WRITE_DECISION_CENTER",
    "MODIFY_GENERATOR",
    "MODIFY_SCHEMA_V3",
    "MODIFY_V2_1",
    "REWRITE_B2K_FIXTURES",
}

check(
    set(contract["prohibited_behaviors"])
    == expected_prohibitions,
    "requiredness prohibitions exact",
)


# ============================================================
# W. FINAL
# ============================================================

print()
print("=" * 78)
print(" D.3D.4D - REQUIREDNESS CONTRACT RESULT")
print("=" * 78)
print(f"Checks executed: {checks}")
print(f"Failures: {len(failures)}")

if failures:
    print("RESULT: FAILED")

    for failure in failures:
        print(f" - {failure}")

    raise SystemExit(1)

print("RESULT: APPROVED")
