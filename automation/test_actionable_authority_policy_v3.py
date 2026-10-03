import json
import sys
from pathlib import Path

POLICY_PATH = Path("automation/actionable_authority_policy_v3.json")

checks = []
failures = []

def check(name, condition):
    checks.append(name)
    if condition:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name}")
        failures.append(name)

with POLICY_PATH.open("r", encoding="utf-8-sig") as handle:
    p = json.load(handle)

check("policy_id canonical",
      p.get("policy_id") == "RADAR_V3_ACTIONABLE_AUTHORITY_POLICY")

check("policy_version canonical",
      p.get("policy_version") == "3.4D.2D.4B")

check("policy remains DRAFT",
      p.get("status") == "DRAFT")

check("scope V3 only",
      p.get("scope") == "RADAR_INSTITUCIONAL_V3_ONLY")

c = p["compatibility"]

check("V2.1 preserved", c["preserves_v2_1"] is True)
check("no schema change", c["schema_change_required"] is False)
check("no public output change", c["public_output_change_required"] is False)
check("D.2D.2 policy remains untouched",
      c["modifies_decision_policy_v3"] is False)

purpose = p["purpose"]

check("defines positive authority",
      purpose["defines_positive_actionable_authority"] is True)
check("does not define trade execution",
      purpose["defines_trade_execution"] is False)
check("does not define buy sell",
      purpose["defines_buy_or_sell_instruction"] is False)
check("does not define portfolio action",
      purpose["defines_portfolio_action"] is False)
check("does not recalculate upstream",
      purpose["recalculates_upstream_models"] is False)

a = p["authority_semantics"]

check("canonical authority token",
      a["authority_token"] ==
      "ACTIONABLE_AUTHORITY_EXPLICITLY_ESTABLISHED")

check("authority positive", a["authority_is_positive"] is True)
check("authority not default", a["authority_is_default"] is False)
check("authority not trade instruction",
      a["authority_is_trade_instruction"] is False)
check("authority not BUY", a["authority_is_buy"] is False)
check("authority not SELL", a["authority_is_sell"] is False)
check("authority not guarantee", a["authority_is_guarantee"] is False)
check("authority cannot be invented",
      a["authority_may_be_invented"] is False)

rule = p["establishment_rule"]

check("explicit evidence convergence mode",
      rule["mode"] == "EXPLICIT_EVIDENCE_CONVERGENCE")

check("all authority conditions required",
      rule["all_conditions_required"] is True)

expected_conditions = [
    "EVIDENCE_GATE_PASSED",
    "USABLE_AUTHORIZED_EVIDENCE_PRESENT",
    "EXPLICIT_DIRECTIONAL_THESIS_PRESENT",
    "DIRECTIONAL_THESIS_SUPPORTED_BY_AUTHORIZED_EVIDENCE",
    "NO_UNRESOLVED_MATERIAL_CONFLICT",
    "NO_MATERIAL_RISK_RESTRICTION",
    "NO_REQUIRED_CONFIRMATION_MISSING",
    "PUBLICATION_REQUIREMENTS_SATISFIED_WHERE_APPLICABLE"
]

check("authority conditions canonical",
      rule["conditions"] == expected_conditions)

check("failed establishment creates no authority",
      rule["failure_to_establish_authority"] ==
      "NO_ACTIONABLE_AUTHORITY")

check("failed establishment is not negative",
      rule["failure_does_not_mean_negative"] is True)

thesis = p["directional_thesis"]

check("directional thesis required", thesis["required"] is True)
check("directional thesis explicit", thesis["must_be_explicit"] is True)
check("directional thesis traceable", thesis["must_be_traceable"] is True)
check("directional thesis evidence supported",
      thesis["must_be_supported_by_authorized_evidence"] is True)

for key in [
    "may_be_invented_from_score_label",
    "may_be_invented_from_normalized_score",
    "may_be_invented_from_risk_level",
    "may_be_invented_from_confidence_status",
    "may_be_invented_from_generic_market_intuition"
]:
    check(f"directional_thesis.{key} false",
          thesis[key] is False)

check("authorized evidence classes exact",
      p["authorized_evidence_classes"] ==
      ["FACT", "MODEL", "INFERENCE"])

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

check("authorized domains exact",
      p["authorized_input_domains"] == expected_domains)

g = p["input_governance"]

check("inputs consumed not recalculated",
      g["inputs_are_consumed_not_recalculated"] is True)

for key in [
    "blocked_evidence_may_support_authority",
    "unavailable_evidence_may_support_authority",
    "unknown_evidence_may_support_authority",
    "invalid_provenance_may_support_authority",
    "publication_ineligible_evidence_may_support_authority_where_required",
    "missing_is_neutral",
    "missing_is_negative",
    "missing_is_positive",
    "missing_is_zero"
]:
    check(f"input_governance.{key} false", g[key] is False)

ns = p["non_shortcut_rules"]

for key in [
    "score_label_alone_establishes_authority",
    "normalized_score_alone_establishes_authority",
    "risk_level_alone_establishes_authority",
    "confidence_status_alone_establishes_authority",
    "signal_score_alone_establishes_authority",
    "single_evidence_domain_alone_establishes_authority"
]:
    check(f"non_shortcut_rules.{key} false", ns[key] is False)

tg = p["threshold_governance"]

for key in [
    "defines_new_numeric_thresholds",
    "duplicates_upstream_numeric_thresholds",
    "redefines_score_thresholds",
    "redefines_signal_thresholds",
    "redefines_confidence_thresholds",
    "redefines_risk_thresholds",
    "redefines_publication_source_tiers"
]:
    check(f"threshold_governance.{key} false", tg[key] is False)

rp = p["restriction_precedence"]

for key in [
    "insufficient_evidence_blocks_authority",
    "unresolved_material_conflict_blocks_authority",
    "material_risk_restriction_blocks_authority",
    "required_confirmation_missing_blocks_authority",
    "publication_ineligibility_where_required_blocks_authority"
]:
    check(f"restriction_precedence.{key} true", rp[key] is True)

check("positive authority cannot override restriction",
      rp["positive_authority_may_override_restriction"] is False)

fb = p["fallback_semantics"]

check("authority absence falls back to WATCH",
      fb["authority_not_established_state"] == "WATCH")
check("WATCH requires usable evidence",
      fb["watch_requires_usable_evidence"] is True)
check("WATCH requires no higher restriction",
      fb["watch_requires_no_higher_priority_restriction"] is True)
check("missing evidence does not become WATCH",
      fb["missing_evidence_does_not_fallback_to_watch"] is True)

ic = p["information_class"]

check("observations FACT", ic["input_observations"] == "FACT")
check("analytical outputs MODEL",
      ic["upstream_analytical_outputs"] == "MODEL")
check("directional thesis INFERENCE",
      ic["directional_thesis"] == "INFERENCE")
check("authority assessment INFERENCE",
      ic["actionable_authority_assessment"] == "INFERENCE")
check("decision state DECISION",
      ic["decision_state"] == "DECISION")
check("inference not FACT",
      ic["inference_may_be_presented_as_fact"] is False)
check("decision not FACT",
      ic["decision_may_be_presented_as_fact"] is False)

pb = p["phase_boundary"]

for key in [
    "implements_evidence_gate",
    "implements_conflict_resolver",
    "implements_decision_state_engine",
    "writes_decision_center",
    "modifies_generator",
    "modifies_schema_v3",
    "modifies_v2_1"
]:
    check(f"phase_boundary.{key} false", pb[key] is False)

required_prohibitions = {
    "MODIFY_V2_1",
    "MODIFY_SCHEMA_V3_IN_D2D4B",
    "RECALCULATE_UPSTREAM_MODELS",
    "DUPLICATE_UPSTREAM_NUMERIC_THRESHOLDS",
    "TREAT_STRONG_BUY_AS_ACTIONABLE_AUTHORITY",
    "TREAT_BUY_AS_ACTIONABLE_AUTHORITY",
    "CREATE_AUTHORITY_FROM_SCORE_ALONE",
    "CREATE_AUTHORITY_FROM_RISK_LEVEL_ALONE",
    "CREATE_AUTHORITY_FROM_CONFIDENCE_ALONE",
    "CREATE_AUTHORITY_FROM_SIGNAL_SCORE_ALONE",
    "CREATE_AUTHORITY_FROM_SINGLE_EVIDENCE_DOMAIN",
    "CREATE_AUTHORITY_FROM_BLOCKED_EVIDENCE",
    "CREATE_AUTHORITY_FROM_UNAVAILABLE_EVIDENCE",
    "CREATE_AUTHORITY_FROM_INVALID_PROVENANCE",
    "OVERRIDE_PUBLICATION_ELIGIBILITY",
    "OVERRIDE_MATERIAL_RISK_RESTRICTION",
    "DISCARD_MATERIAL_CONFLICT",
    "ASSUME_REQUIRED_CONFIRMATION_SATISFIED",
    "TREAT_MISSING_AS_NEUTRAL",
    "TREAT_MISSING_AS_WATCH",
    "TRANSLATE_ACTIONABLE_AUTHORITY_TO_BUY",
    "TRANSLATE_ACTIONABLE_AUTHORITY_TO_SELL",
    "EXECUTE_TRADE_FROM_ACTIONABLE_AUTHORITY",
    "WRITE_DECISION_CENTER_IN_D2D4B"
}

check("all mandatory prohibitions present",
      required_prohibitions.issubset(set(p["prohibited_behaviors"])))

print()
print("=" * 60)
print(" D.2D.4B - ACTIONABLE AUTHORITY POLICY TEST")
print("=" * 60)
print(f"Checks executed: {len(checks)}")
print(f"Failures: {len(failures)}")
print("RESULT:", "APPROVED" if not failures else "REJECTED")

sys.exit(0 if not failures else 1)
