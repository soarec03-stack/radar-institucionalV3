import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICY = ROOT / "evidence_gate_policy_v3.json"

checks = []
failures = []


def check(name, condition):
    checks.append(name)
    if condition:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name}")
        failures.append(name)


with POLICY.open("r", encoding="utf-8-sig") as f:
    p = json.load(f)

check("policy id canonical", p["policy_id"] == "RADAR_V3_EVIDENCE_GATE_POLICY")
check("policy version canonical", p["policy_version"] == "3.4D.3B")
check("policy remains DRAFT", p["status"] == "DRAFT")
check("scope V3 only", p["scope"] == "V3_ONLY")

c = p["compatibility"]
check("V2.1 preserved", c["preserve_v2_1"] is True)
check("V2.1 not modified", c["modify_v2_1"] is False)
check("no schema change", c["requires_schema_v3_change"] is False)
check("no public output change", c["requires_public_output_change"] is False)
check("existing decision center contract preserved",
      c["preserve_existing_decision_center_contract"] is True)

purpose = p["purpose"]
check("defines evidence admissibility",
      purpose["defines_evidence_admissibility"] is True)
check("does not define decision state",
      purpose["defines_decision_state"] is False)
check("does not define actionable authority",
      purpose["defines_actionable_authority"] is False)
check("does not resolve conflicts",
      purpose["resolves_conflicts"] is False)
check("does not recalculate upstream",
      purpose["recalculates_upstream_models"] is False)
check("does not write decision center",
      purpose["writes_decision_center"] is False)

info = p["information_classes"]
check("evidence classes exact",
      info["recognized"] == ["FACT", "MODEL", "INFERENCE"])
check("DECISION is not evidence", info["DECISION_is_evidence"] is False)
check("unknown information class fails closed",
      info["unknown_information_class_result"] == "UNKNOWN")

domains = p["authorized_domains"]
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
    "MARKET_REGIME"
]
check("authorized domains canonical", domains == expected_domains)

results = p["gate_results"]
check("gate result set exact",
      set(results) == {
          "ADMISSIBLE",
          "RESTRICTED",
          "BLOCKED",
          "INSUFFICIENT",
          "UNKNOWN"
      })

for name in ["RESTRICTED", "BLOCKED", "INSUFFICIENT", "UNKNOWN"]:
    check(f"{name} cannot establish actionable authority",
          results[name]["may_establish_actionable_authority"] is False)

for name in results:
    check(f"{name} cannot directly select decision state",
          results[name]["may_directly_select_decision_state"] is False)

order = p["evaluation_order"]
check("evaluation starts with information class",
      order[0] == "RECOGNIZE_INFORMATION_CLASS")
check("domain recognized before presence",
      order.index("RECOGNIZE_EVIDENCE_DOMAIN") <
      order.index("CHECK_REQUIRED_PRESENCE"))
check("availability checked before provenance",
      order.index("CHECK_AVAILABILITY_AND_UPSTREAM_STATUS") <
      order.index("CHECK_PROVENANCE"))
check("provenance checked before publication",
      order.index("CHECK_PROVENANCE") <
      order.index("CHECK_PUBLICATION_ELIGIBILITY_WHERE_APPLICABLE"))
check("classification is last",
      order[-1] == "CLASSIFY_GATE_RESULT")

fc = p["fail_closed"]
check("fail closed enabled", fc["enabled"] is True)
check("unknown class -> UNKNOWN",
      fc["unknown_information_class"] == "UNKNOWN")
check("unknown domain -> UNKNOWN", fc["unknown_domain"] == "UNKNOWN")
check("unknown status -> UNKNOWN",
      fc["unknown_required_status"] == "UNKNOWN")
check("missing required -> INSUFFICIENT",
      fc["missing_required_evidence"] == "INSUFFICIENT")
check("unavailable required -> INSUFFICIENT",
      fc["unavailable_required_evidence"] == "INSUFFICIENT")
check("insufficient coverage -> INSUFFICIENT",
      fc["insufficient_required_coverage"] == "INSUFFICIENT")
check("invalid provenance -> BLOCKED",
      fc["invalid_provenance"] == "BLOCKED")
check("upstream blocked -> BLOCKED",
      fc["blocked_upstream_evidence"] == "BLOCKED")
check("publication ineligible -> BLOCKED",
      fc["publication_ineligible_where_required"] == "BLOCKED")

missing = p["missing_semantics"]
for key in [
    "missing_is_neutral",
    "missing_is_negative",
    "missing_is_positive",
    "missing_is_zero",
    "missing_is_admissible"
]:
    check(f"{key} false", missing[key] is False)
check("missing required remains insufficient",
      missing["missing_required_result"] == "INSUFFICIENT")

up = p["upstream_ownership"]
check("consume upstream results", up["consume_upstream_results"] is True)
for key in [
    "recalculate_score",
    "recalculate_confidence",
    "recalculate_risk",
    "recalculate_signals",
    "recalculate_publication_eligibility",
    "recalculate_provenance",
    "redefine_upstream_statuses",
    "redefine_upstream_numeric_thresholds",
    "redefine_source_tiers"
]:
    check(f"upstream ownership {key} false", up[key] is False)

prov = p["provenance_policy"]
check("consume existing provenance",
      prov["consume_existing_provenance"] is True)
check("do not invent provenance", prov["invent_provenance"] is False)
check("do not repair invalid provenance",
      prov["repair_invalid_provenance"] is False)
check("invalid required provenance blocked",
      prov["invalid_required_provenance_result"] == "BLOCKED")
check("unknown required provenance unknown",
      prov["unknown_required_provenance_result"] == "UNKNOWN")

pub = p["publication_policy"]
check("consume publication eligibility",
      pub["consume_existing_publication_eligibility"] is True)
check("cannot override publication",
      pub["override_publication_eligibility"] is False)
check("cannot promote publication-ineligible evidence",
      pub["promote_publication_ineligible_evidence"] is False)
check("publication ineligible required blocked",
      pub["publication_ineligible_where_required_result"] == "BLOCKED")
check("publication ineligibility is not negative evidence",
      pub["publication_ineligibility_is_automatic_negative_evidence"] is False)

coverage = p["coverage_policy"]
check("consume upstream coverage", coverage["consume_upstream_coverage"] is True)
check("no new coverage threshold",
      coverage["define_new_coverage_threshold"] is False)
check("no duplicated coverage threshold",
      coverage["duplicate_upstream_coverage_threshold"] is False)
check("insufficient coverage remains insufficient",
      coverage["insufficient_required_coverage_result"] == "INSUFFICIENT")

confidence = p["confidence_policy"]
check("confidence statuses canonical",
      confidence["recognized_statuses"] ==
      ["VERIFIED", "PARTIAL", "LOW", "UNAVAILABLE"])
check("unavailable confidence insufficient",
      confidence["unavailable_required_result"] == "INSUFFICIENT")
check("LOW not automatically admissible",
      confidence["low_confidence_is_automatically_admissible"] is False)
check("confidence cannot override failures",
      confidence["confidence_may_override_other_gate_failures"] is False)

score = p["score_policy"]
check("score statuses canonical",
      score["recognized_statuses"] ==
      ["CALCULATED", "PARTIAL", "INSUFFICIENT_DATA"])
check("score label not gate result",
      score["score_label_is_evidence_gate_result"] is False)
check("high score cannot override gate",
      score["high_score_may_override_gate_failure"] is False)
check("score label cannot override gate",
      score["score_label_may_override_gate_failure"] is False)

signal = p["signal_policy"]
check("signal statuses canonical",
      signal["recognized_statuses"] ==
      ["CALCULATED", "INSUFFICIENT_COVERAGE", "UNAVAILABLE"])
check("signal score cannot override gate",
      signal["signal_score_may_override_gate_failure"] is False)

risk = p["risk_policy"]
check("missing risk not LOW", risk["missing_risk_is_low"] is False)
check("missing risk not zero", risk["missing_risk_is_zero"] is False)
check("risk level alone not gate result",
      risk["risk_level_alone_is_gate_result"] is False)
check("risk cannot override gate",
      risk["risk_level_may_override_gate_failure"] is False)

conflict = p["conflict_boundary"]
check("semantic conflict belongs to D.4",
      conflict["detecting_semantic_conflict_is_d4_responsibility"] is True)
check("D.3 does not resolve conflict",
      conflict["resolving_conflicts_in_d3"] is False)
check("conflicting evidence not discarded",
      conflict["discard_conflicting_evidence"] is False)
check("multiple conflicting admissible items may survive gate",
      conflict["gate_may_preserve_multiple_admissible_conflicting_items"] is True)

decision = p["decision_boundary"]
check("gate result is not decision state",
      decision["gate_result_is_decision_state"] is False)

for state in [
    "ACTIONABLE",
    "WATCH",
    "WAIT_FOR_CONFIRMATION",
    "RISK_REVIEW",
    "THESIS_REVIEW",
    "INSUFFICIENT_EVIDENCE"
]:
    check(f"gate cannot select {state}",
          decision[f"gate_may_select_{state}"] is False)

check("decision state selection remains D.5",
      decision["decision_state_selection_phase"] == "D.5")

authority = p["actionable_authority_boundary"]
check("gate pass required for actionable authority",
      authority["gate_pass_is_required_for_actionable_authority"] is True)
check("gate pass alone not actionable authority",
      authority["gate_pass_alone_establishes_actionable_authority"] is False)
check("admissible evidence alone not actionable authority",
      authority["admissible_evidence_alone_establishes_actionable_authority"] is False)
check("actionable authority policy reference canonical",
      authority["actionable_authority_policy_remains_upstream_contract"] ==
      "RADAR_V3_ACTIONABLE_AUTHORITY_POLICY")

trace = p["traceability"]
for key in [
    "every_gate_result_requires_reason_code",
    "every_gate_result_requires_evidence_domain",
    "every_gate_result_requires_information_class",
    "source_evidence_must_remain_traceable",
    "blocked_evidence_must_not_be_silently_deleted",
    "insufficient_evidence_must_not_be_silently_imputed"
]:
    check(f"traceability {key} true", trace[key] is True)

phase = p["phase_boundaries"]
for key in [
    "implements_evidence_gate_engine",
    "implements_conflict_resolver",
    "implements_decision_state_engine",
    "writes_decision_center",
    "modifies_generator",
    "modifies_schema_v3",
    "modifies_v2_1"
]:
    check(f"phase boundary {key} false", phase[key] is False)

check("engine remains D.3", phase["evidence_gate_engine_phase"] == "D.3")
check("conflict resolver remains D.4",
      phase["conflict_resolver_phase"] == "D.4")
check("decision engine remains D.5",
      phase["decision_state_engine_phase"] == "D.5")
check("generator integration remains D.7",
      phase["generator_integration_phase"] == "D.7")

required_prohibitions = {
    "MODIFY_V2_1",
    "MODIFY_SCHEMA_V3_IN_D3B",
    "WRITE_DECISION_CENTER_IN_D3B",
    "RECALCULATE_SCORE",
    "RECALCULATE_CONFIDENCE",
    "RECALCULATE_RISK",
    "RECALCULATE_SIGNALS",
    "RECALCULATE_PUBLICATION_ELIGIBILITY",
    "RECALCULATE_PROVENANCE",
    "REDEFINE_UPSTREAM_NUMERIC_THRESHOLDS",
    "REDEFINE_PUBLICATION_SOURCE_TIERS",
    "PROMOTE_BLOCKED_EVIDENCE",
    "PROMOTE_UNAVAILABLE_EVIDENCE",
    "PROMOTE_UNKNOWN_EVIDENCE",
    "PROMOTE_INVALID_PROVENANCE",
    "OVERRIDE_PUBLICATION_ELIGIBILITY",
    "TREAT_MISSING_AS_NEUTRAL",
    "TREAT_MISSING_AS_ZERO",
    "TREAT_MISSING_AS_ADMISSIBLE",
    "TREAT_MISSING_RISK_AS_LOW",
    "TREAT_MISSING_RISK_AS_ZERO",
    "USE_HIGH_SCORE_TO_OVERRIDE_GATE",
    "USE_SCORE_LABEL_TO_OVERRIDE_GATE",
    "USE_CONFIDENCE_TO_OVERRIDE_GATE",
    "USE_SIGNAL_SCORE_TO_OVERRIDE_GATE",
    "DISCARD_BLOCKED_EVIDENCE_SILENTLY",
    "IMPUTE_INSUFFICIENT_EVIDENCE_SILENTLY",
    "RESOLVE_CONFLICTS_IN_D3B",
    "SELECT_DECISION_STATE_IN_D3B",
    "CREATE_ACTIONABLE_AUTHORITY_FROM_GATE_PASS",
    "TRANSLATE_GATE_RESULT_TO_BUY",
    "TRANSLATE_GATE_RESULT_TO_SELL",
    "EXECUTE_TRADE_FROM_GATE_RESULT"
}

check("mandatory prohibitions exact coverage",
      required_prohibitions.issubset(set(p["prohibited_behaviors"])))

print()
print("=" * 60)
print(" D.3B - EVIDENCE GATE POLICY CONTRACT TEST")
print("=" * 60)
print(f"Checks executed: {len(checks)}")
print(f"Failures: {len(failures)}")

if failures:
    print("RESULT: REJECTED")
    raise SystemExit(1)

print("RESULT: APPROVED")
