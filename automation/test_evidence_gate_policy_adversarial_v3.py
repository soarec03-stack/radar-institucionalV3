import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICY_PATH = ROOT / "evidence_gate_policy_v3.json"

with POLICY_PATH.open("r", encoding="utf-8-sig") as f:
    BASE = json.load(f)


EXPECTED_DOMAINS = [
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

EXPECTED_RESULTS = {
    "ADMISSIBLE",
    "RESTRICTED",
    "BLOCKED",
    "INSUFFICIENT",
    "UNKNOWN",
}

EXPECTED_ORDER = [
    "RECOGNIZE_INFORMATION_CLASS",
    "RECOGNIZE_EVIDENCE_DOMAIN",
    "CHECK_REQUIRED_PRESENCE",
    "CHECK_AVAILABILITY_AND_UPSTREAM_STATUS",
    "CHECK_PROVENANCE",
    "CHECK_UPSTREAM_COVERAGE",
    "CHECK_PUBLICATION_ELIGIBILITY_WHERE_APPLICABLE",
    "APPLY_EXPLICIT_UPSTREAM_RESTRICTIONS",
    "CLASSIFY_GATE_RESULT",
]

MANDATORY_PROHIBITIONS = {
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
    "EXECUTE_TRADE_FROM_GATE_RESULT",
}


def valid(p):
    try:
        if p.get("policy_id") != "RADAR_V3_EVIDENCE_GATE_POLICY":
            return False
        if p.get("policy_version") != "3.4D.3B":
            return False
        if p.get("status") != "DRAFT":
            return False
        if p.get("scope") != "V3_ONLY":
            return False

        c = p["compatibility"]
        if c["preserve_v2_1"] is not True:
            return False
        if c["modify_v2_1"] is not False:
            return False
        if c["requires_schema_v3_change"] is not False:
            return False
        if c["requires_public_output_change"] is not False:
            return False
        if c["preserve_existing_decision_center_contract"] is not True:
            return False

        purpose = p["purpose"]
        if purpose["defines_evidence_admissibility"] is not True:
            return False
        if purpose["defines_decision_state"] is not False:
            return False
        if purpose["defines_actionable_authority"] is not False:
            return False
        if purpose["resolves_conflicts"] is not False:
            return False
        if purpose["recalculates_upstream_models"] is not False:
            return False
        if purpose["writes_decision_center"] is not False:
            return False

        info = p["information_classes"]
        if info["recognized"] != ["FACT", "MODEL", "INFERENCE"]:
            return False
        if info["DECISION_is_evidence"] is not False:
            return False
        if info["unknown_information_class_result"] != "UNKNOWN":
            return False

        if p["authorized_domains"] != EXPECTED_DOMAINS:
            return False

        results = p["gate_results"]
        if set(results) != EXPECTED_RESULTS:
            return False

        for name in ["RESTRICTED", "BLOCKED", "INSUFFICIENT", "UNKNOWN"]:
            if results[name]["may_establish_actionable_authority"] is not False:
                return False

        for name in EXPECTED_RESULTS:
            if results[name]["may_directly_select_decision_state"] is not False:
                return False

        if p["evaluation_order"] != EXPECTED_ORDER:
            return False

        fc = p["fail_closed"]
        expected_fc = {
            "enabled": True,
            "unknown_information_class": "UNKNOWN",
            "unknown_domain": "UNKNOWN",
            "unknown_required_status": "UNKNOWN",
            "missing_required_evidence": "INSUFFICIENT",
            "unavailable_required_evidence": "INSUFFICIENT",
            "insufficient_required_coverage": "INSUFFICIENT",
            "invalid_provenance": "BLOCKED",
            "blocked_upstream_evidence": "BLOCKED",
            "publication_ineligible_where_required": "BLOCKED",
        }
        for key, value in expected_fc.items():
            if fc.get(key) != value:
                return False

        missing = p["missing_semantics"]
        for key in [
            "missing_is_neutral",
            "missing_is_negative",
            "missing_is_positive",
            "missing_is_zero",
            "missing_is_admissible",
        ]:
            if missing[key] is not False:
                return False
        if missing["missing_required_result"] != "INSUFFICIENT":
            return False

        up = p["upstream_ownership"]
        if up["consume_upstream_results"] is not True:
            return False
        for key in [
            "recalculate_score",
            "recalculate_confidence",
            "recalculate_risk",
            "recalculate_signals",
            "recalculate_publication_eligibility",
            "recalculate_provenance",
            "redefine_upstream_statuses",
            "redefine_upstream_numeric_thresholds",
            "redefine_source_tiers",
        ]:
            if up[key] is not False:
                return False

        prov = p["provenance_policy"]
        if prov["consume_existing_provenance"] is not True:
            return False
        if prov["invent_provenance"] is not False:
            return False
        if prov["repair_invalid_provenance"] is not False:
            return False
        if prov["invalid_required_provenance_result"] != "BLOCKED":
            return False
        if prov["unknown_required_provenance_result"] != "UNKNOWN":
            return False

        pub = p["publication_policy"]
        if pub["consume_existing_publication_eligibility"] is not True:
            return False
        if pub["override_publication_eligibility"] is not False:
            return False
        if pub["promote_publication_ineligible_evidence"] is not False:
            return False
        if pub["publication_ineligible_where_required_result"] != "BLOCKED":
            return False
        if pub["publication_ineligibility_is_automatic_negative_evidence"] is not False:
            return False

        cov = p["coverage_policy"]
        if cov["consume_upstream_coverage"] is not True:
            return False
        if cov["define_new_coverage_threshold"] is not False:
            return False
        if cov["duplicate_upstream_coverage_threshold"] is not False:
            return False
        if cov["insufficient_required_coverage_result"] != "INSUFFICIENT":
            return False

        conf = p["confidence_policy"]
        if conf["recognized_statuses"] != [
            "VERIFIED", "PARTIAL", "LOW", "UNAVAILABLE"
        ]:
            return False
        if conf["unavailable_required_result"] != "INSUFFICIENT":
            return False
        if conf["low_confidence_is_automatically_admissible"] is not False:
            return False
        if conf["confidence_may_override_other_gate_failures"] is not False:
            return False

        score = p["score_policy"]
        if score["recognized_statuses"] != [
            "CALCULATED", "PARTIAL", "INSUFFICIENT_DATA"
        ]:
            return False
        if score["score_label_is_evidence_gate_result"] is not False:
            return False
        if score["high_score_may_override_gate_failure"] is not False:
            return False
        if score["score_label_may_override_gate_failure"] is not False:
            return False

        signal = p["signal_policy"]
        if signal["recognized_statuses"] != [
            "CALCULATED", "INSUFFICIENT_COVERAGE", "UNAVAILABLE"
        ]:
            return False
        if signal["signal_score_may_override_gate_failure"] is not False:
            return False

        risk = p["risk_policy"]
        for key in [
            "missing_risk_is_low",
            "missing_risk_is_zero",
            "risk_level_alone_is_gate_result",
            "risk_level_may_override_gate_failure",
        ]:
            if risk[key] is not False:
                return False

        conflict = p["conflict_boundary"]
        if conflict["detecting_semantic_conflict_is_d4_responsibility"] is not True:
            return False
        if conflict["resolving_conflicts_in_d3"] is not False:
            return False
        if conflict["discard_conflicting_evidence"] is not False:
            return False
        if conflict["gate_may_preserve_multiple_admissible_conflicting_items"] is not True:
            return False

        decision = p["decision_boundary"]
        if decision["gate_result_is_decision_state"] is not False:
            return False
        for state in [
            "ACTIONABLE",
            "WATCH",
            "WAIT_FOR_CONFIRMATION",
            "RISK_REVIEW",
            "THESIS_REVIEW",
            "INSUFFICIENT_EVIDENCE",
        ]:
            if decision[f"gate_may_select_{state}"] is not False:
                return False
        if decision["decision_state_selection_phase"] != "D.5":
            return False

        auth = p["actionable_authority_boundary"]
        if auth["gate_pass_is_required_for_actionable_authority"] is not True:
            return False
        if auth["gate_pass_alone_establishes_actionable_authority"] is not False:
            return False
        if auth["admissible_evidence_alone_establishes_actionable_authority"] is not False:
            return False
        if auth["actionable_authority_policy_remains_upstream_contract"] != \
                "RADAR_V3_ACTIONABLE_AUTHORITY_POLICY":
            return False

        trace = p["traceability"]
        for key in [
            "every_gate_result_requires_reason_code",
            "every_gate_result_requires_evidence_domain",
            "every_gate_result_requires_information_class",
            "source_evidence_must_remain_traceable",
            "blocked_evidence_must_not_be_silently_deleted",
            "insufficient_evidence_must_not_be_silently_imputed",
        ]:
            if trace[key] is not True:
                return False

        phase = p["phase_boundaries"]
        for key in [
            "implements_evidence_gate_engine",
            "implements_conflict_resolver",
            "implements_decision_state_engine",
            "writes_decision_center",
            "modifies_generator",
            "modifies_schema_v3",
            "modifies_v2_1",
        ]:
            if phase[key] is not False:
                return False

        if phase["evidence_gate_engine_phase"] != "D.3":
            return False
        if phase["conflict_resolver_phase"] != "D.4":
            return False
        if phase["decision_state_engine_phase"] != "D.5":
            return False
        if phase["generator_integration_phase"] != "D.7":
            return False

        if not MANDATORY_PROHIBITIONS.issubset(set(p["prohibited_behaviors"])):
            return False

        return True

    except (KeyError, TypeError, AttributeError):
        return False


def set_path(obj, path, value):
    cur = obj
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


cases = []


def mutation(name, path, value):
    def apply(p):
        set_path(p, path, value)
    cases.append((name, apply))


mutation("allow V2.1 modification",
         ["compatibility", "modify_v2_1"], True)

mutation("remove V2.1 preservation",
         ["compatibility", "preserve_v2_1"], False)

mutation("require schema change",
         ["compatibility", "requires_schema_v3_change"], True)

mutation("allow public output change",
         ["compatibility", "requires_public_output_change"], True)

mutation("define decision state in gate",
         ["purpose", "defines_decision_state"], True)

mutation("define actionable authority in gate",
         ["purpose", "defines_actionable_authority"], True)

mutation("resolve conflicts in gate",
         ["purpose", "resolves_conflicts"], True)

mutation("recalculate upstream models",
         ["purpose", "recalculates_upstream_models"], True)

mutation("write decision center",
         ["purpose", "writes_decision_center"], True)

mutation("DECISION becomes evidence",
         ["information_classes", "DECISION_is_evidence"], True)

mutation("unknown class becomes admissible",
         ["information_classes", "unknown_information_class_result"],
         "ADMISSIBLE")

mutation("remove MARKET_REGIME domain",
         ["authorized_domains"],
         EXPECTED_DOMAINS[:-1])

mutation("unknown domain becomes admissible",
         ["fail_closed", "unknown_domain"], "ADMISSIBLE")

mutation("missing required becomes admissible",
         ["fail_closed", "missing_required_evidence"], "ADMISSIBLE")

mutation("unavailable required becomes admissible",
         ["fail_closed", "unavailable_required_evidence"], "ADMISSIBLE")

mutation("insufficient coverage becomes admissible",
         ["fail_closed", "insufficient_required_coverage"], "ADMISSIBLE")

mutation("invalid provenance becomes admissible",
         ["fail_closed", "invalid_provenance"], "ADMISSIBLE")

mutation("publication ineligible becomes admissible",
         ["fail_closed", "publication_ineligible_where_required"],
         "ADMISSIBLE")

mutation("missing becomes neutral",
         ["missing_semantics", "missing_is_neutral"], True)

mutation("missing becomes zero",
         ["missing_semantics", "missing_is_zero"], True)

mutation("missing becomes admissible",
         ["missing_semantics", "missing_is_admissible"], True)

mutation("recalculate score",
         ["upstream_ownership", "recalculate_score"], True)

mutation("recalculate confidence",
         ["upstream_ownership", "recalculate_confidence"], True)

mutation("recalculate risk",
         ["upstream_ownership", "recalculate_risk"], True)

mutation("recalculate signals",
         ["upstream_ownership", "recalculate_signals"], True)

mutation("recalculate publication",
         ["upstream_ownership", "recalculate_publication_eligibility"], True)

mutation("recalculate provenance",
         ["upstream_ownership", "recalculate_provenance"], True)

mutation("redefine numeric thresholds",
         ["upstream_ownership", "redefine_upstream_numeric_thresholds"], True)

mutation("invent provenance",
         ["provenance_policy", "invent_provenance"], True)

mutation("repair invalid provenance",
         ["provenance_policy", "repair_invalid_provenance"], True)

mutation("invalid provenance becomes insufficient",
         ["provenance_policy", "invalid_required_provenance_result"],
         "INSUFFICIENT")

mutation("override publication eligibility",
         ["publication_policy", "override_publication_eligibility"], True)

mutation("promote publication-ineligible evidence",
         ["publication_policy",
          "promote_publication_ineligible_evidence"], True)

mutation("publication ineligible becomes negative evidence",
         ["publication_policy",
          "publication_ineligibility_is_automatic_negative_evidence"], True)

mutation("define new coverage threshold",
         ["coverage_policy", "define_new_coverage_threshold"], True)

mutation("duplicate coverage threshold",
         ["coverage_policy", "duplicate_upstream_coverage_threshold"], True)

mutation("LOW confidence automatically admissible",
         ["confidence_policy",
          "low_confidence_is_automatically_admissible"], True)

mutation("confidence overrides failures",
         ["confidence_policy",
          "confidence_may_override_other_gate_failures"], True)

mutation("score label becomes gate result",
         ["score_policy", "score_label_is_evidence_gate_result"], True)

mutation("high score overrides gate",
         ["score_policy", "high_score_may_override_gate_failure"], True)

mutation("score label overrides gate",
         ["score_policy", "score_label_may_override_gate_failure"], True)

mutation("signal score overrides gate",
         ["signal_policy", "signal_score_may_override_gate_failure"], True)

mutation("missing risk becomes LOW",
         ["risk_policy", "missing_risk_is_low"], True)

mutation("missing risk becomes zero",
         ["risk_policy", "missing_risk_is_zero"], True)

mutation("risk level becomes gate result",
         ["risk_policy", "risk_level_alone_is_gate_result"], True)

mutation("risk overrides gate",
         ["risk_policy", "risk_level_may_override_gate_failure"], True)

mutation("D.3 resolves conflicts",
         ["conflict_boundary", "resolving_conflicts_in_d3"], True)

mutation("discard conflicting evidence",
         ["conflict_boundary", "discard_conflicting_evidence"], True)

mutation("gate result becomes decision state",
         ["decision_boundary", "gate_result_is_decision_state"], True)

mutation("gate selects ACTIONABLE",
         ["decision_boundary", "gate_may_select_ACTIONABLE"], True)

mutation("gate selects WATCH",
         ["decision_boundary", "gate_may_select_WATCH"], True)

mutation("gate selects INSUFFICIENT_EVIDENCE",
         ["decision_boundary",
          "gate_may_select_INSUFFICIENT_EVIDENCE"], True)

mutation("gate pass alone creates authority",
         ["actionable_authority_boundary",
          "gate_pass_alone_establishes_actionable_authority"], True)

mutation("admissible evidence alone creates authority",
         ["actionable_authority_boundary",
          "admissible_evidence_alone_establishes_actionable_authority"], True)

mutation("blocked evidence may establish authority",
         ["gate_results", "BLOCKED",
          "may_establish_actionable_authority"], True)

mutation("insufficient evidence may establish authority",
         ["gate_results", "INSUFFICIENT",
          "may_establish_actionable_authority"], True)

mutation("unknown evidence may establish authority",
         ["gate_results", "UNKNOWN",
          "may_establish_actionable_authority"], True)

mutation("ADMISSIBLE directly selects decision state",
         ["gate_results", "ADMISSIBLE",
          "may_directly_select_decision_state"], True)

mutation("blocked evidence silently deleted",
         ["traceability",
          "blocked_evidence_must_not_be_silently_deleted"], False)

mutation("insufficient evidence silently imputed",
         ["traceability",
          "insufficient_evidence_must_not_be_silently_imputed"], False)

mutation("generator modified in D.3B",
         ["phase_boundaries", "modifies_generator"], True)

mutation("schema modified in D.3B",
         ["phase_boundaries", "modifies_schema_v3"], True)

mutation("V2.1 modified in D.3B",
         ["phase_boundaries", "modifies_v2_1"], True)

mutation("decision engine implemented in D.3B",
         ["phase_boundaries", "implements_decision_state_engine"], True)


def remove_prohibition(p):
    p["prohibited_behaviors"].remove("PROMOTE_BLOCKED_EVIDENCE")


cases.append(("remove mandatory prohibition", remove_prohibition))


def reorder_gate(p):
    p["evaluation_order"] = list(p["evaluation_order"])
    i = p["evaluation_order"].index("CHECK_PROVENANCE")
    j = p["evaluation_order"].index(
        "CHECK_PUBLICATION_ELIGIBILITY_WHERE_APPLICABLE"
    )
    p["evaluation_order"][i], p["evaluation_order"][j] = \
        p["evaluation_order"][j], p["evaluation_order"][i]


cases.append(("publication checked before provenance", reorder_gate))


print("=" * 60)
print(" D.3C - ADVERSARIAL EVIDENCE GATE POLICY TEST")
print("=" * 60)

if not valid(BASE):
    print("[FAIL] Baseline policy is not valid.")
    raise SystemExit(1)

print("[PASS] Baseline policy accepted.")

passed = 0
failed = []

for index, (name, mutate) in enumerate(cases, start=1):
    candidate = copy.deepcopy(BASE)
    mutate(candidate)

    if valid(candidate):
        print(f"[FAIL] {index:02d}. mutation survived: {name}")
        failed.append(name)
    else:
        print(f"[PASS] {index:02d}. mutation rejected: {name}")
        passed += 1

print()
print("=" * 60)
print(" D.3C - ADVERSARIAL RESULT")
print("=" * 60)
print(f"Mutations executed: {len(cases)}")
print(f"Passed: {passed}")
print(f"Failed: {len(failed)}")

if failed:
    print("RESULT: REJECTED")
    for item in failed:
        print(f" - {item}")
    raise SystemExit(1)

print("RESULT: APPROVED")
