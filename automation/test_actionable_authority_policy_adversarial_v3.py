import copy
import json
import sys
from pathlib import Path

POLICY_PATH = Path("automation/actionable_authority_policy_v3.json")

EXPECTED_CONDITIONS = [
    "EVIDENCE_GATE_PASSED",
    "USABLE_AUTHORIZED_EVIDENCE_PRESENT",
    "EXPLICIT_DIRECTIONAL_THESIS_PRESENT",
    "DIRECTIONAL_THESIS_SUPPORTED_BY_AUTHORIZED_EVIDENCE",
    "NO_UNRESOLVED_MATERIAL_CONFLICT",
    "NO_MATERIAL_RISK_RESTRICTION",
    "NO_REQUIRED_CONFIRMATION_MISSING",
    "PUBLICATION_REQUIREMENTS_SATISFIED_WHERE_APPLICABLE",
]

EXPECTED_EVIDENCE_CLASSES = [
    "FACT",
    "MODEL",
    "INFERENCE",
]

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

REQUIRED_PROHIBITIONS = {
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
    "WRITE_DECISION_CENTER_IN_D2D4B",
}


def load_policy():
    with POLICY_PATH.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def validate(p):
    errors = []

    if p.get("policy_id") != "RADAR_V3_ACTIONABLE_AUTHORITY_POLICY":
        errors.append("POLICY_ID_CHANGED")

    if p.get("policy_version") != "3.4D.2D.4B":
        errors.append("POLICY_VERSION_CHANGED")

    if p.get("status") != "DRAFT":
        errors.append("POLICY_STATUS_CHANGED")

    if p.get("scope") != "RADAR_INSTITUCIONAL_V3_ONLY":
        errors.append("POLICY_SCOPE_CHANGED")

    compatibility = p.get("compatibility", {})

    if compatibility.get("preserves_v2_1") is not True:
        errors.append("V2_1_PRESERVATION_DISABLED")

    if compatibility.get("schema_change_required") is not False:
        errors.append("SCHEMA_CHANGE_INTRODUCED")

    if compatibility.get("public_output_change_required") is not False:
        errors.append("PUBLIC_OUTPUT_CHANGE_INTRODUCED")

    if compatibility.get("modifies_decision_policy_v3") is not False:
        errors.append("D2D2_MODIFICATION_ALLOWED")

    purpose = p.get("purpose", {})

    if purpose.get("defines_positive_actionable_authority") is not True:
        errors.append("POSITIVE_AUTHORITY_DEFINITION_DISABLED")

    if purpose.get("defines_trade_execution") is not False:
        errors.append("TRADE_EXECUTION_INTRODUCED")

    if purpose.get("defines_buy_or_sell_instruction") is not False:
        errors.append("BUY_SELL_INSTRUCTION_INTRODUCED")

    if purpose.get("defines_portfolio_action") is not False:
        errors.append("PORTFOLIO_ACTION_INTRODUCED")

    if purpose.get("recalculates_upstream_models") is not False:
        errors.append("UPSTREAM_RECALCULATION_ALLOWED")

    authority = p.get("authority_semantics", {})

    if authority.get("authority_token") != \
            "ACTIONABLE_AUTHORITY_EXPLICITLY_ESTABLISHED":
        errors.append("AUTHORITY_TOKEN_CHANGED")

    if authority.get("authority_is_positive") is not True:
        errors.append("POSITIVE_AUTHORITY_SEMANTICS_CHANGED")

    if authority.get("authority_is_default") is not False:
        errors.append("AUTHORITY_BECAME_DEFAULT")

    if authority.get("authority_is_trade_instruction") is not False:
        errors.append("AUTHORITY_BECAME_TRADE_INSTRUCTION")

    if authority.get("authority_is_buy") is not False:
        errors.append("AUTHORITY_BECAME_BUY")

    if authority.get("authority_is_sell") is not False:
        errors.append("AUTHORITY_BECAME_SELL")

    if authority.get("authority_is_guarantee") is not False:
        errors.append("AUTHORITY_BECAME_GUARANTEE")

    if authority.get("authority_may_be_invented") is not False:
        errors.append("AUTHORITY_INVENTION_ALLOWED")

    rule = p.get("establishment_rule", {})

    if rule.get("mode") != "EXPLICIT_EVIDENCE_CONVERGENCE":
        errors.append("AUTHORITY_ESTABLISHMENT_MODE_CHANGED")

    if rule.get("all_conditions_required") is not True:
        errors.append("AUTHORITY_CONVERGENCE_WEAKENED")

    if rule.get("conditions") != EXPECTED_CONDITIONS:
        errors.append("AUTHORITY_CONDITIONS_CHANGED")

    if rule.get("failure_to_establish_authority") != \
            "NO_ACTIONABLE_AUTHORITY":
        errors.append("AUTHORITY_FAILURE_SEMANTICS_CHANGED")

    if rule.get("failure_does_not_mean_negative") is not True:
        errors.append("AUTHORITY_FAILURE_BECAME_NEGATIVE")

    thesis = p.get("directional_thesis", {})

    for key in [
        "required",
        "must_be_explicit",
        "must_be_traceable",
        "must_be_supported_by_authorized_evidence",
    ]:
        if thesis.get(key) is not True:
            errors.append("DIRECTIONAL_THESIS_REQUIREMENT_WEAKENED")
            break

    for key in [
        "may_be_invented_from_score_label",
        "may_be_invented_from_normalized_score",
        "may_be_invented_from_risk_level",
        "may_be_invented_from_confidence_status",
        "may_be_invented_from_generic_market_intuition",
    ]:
        if thesis.get(key) is not False:
            errors.append("DIRECTIONAL_THESIS_INVENTION_ALLOWED")
            break

    if p.get("authorized_evidence_classes") != EXPECTED_EVIDENCE_CLASSES:
        errors.append("AUTHORIZED_EVIDENCE_CLASSES_CHANGED")

    if p.get("authorized_input_domains") != EXPECTED_DOMAINS:
        errors.append("AUTHORIZED_INPUT_DOMAINS_CHANGED")

    governance = p.get("input_governance", {})

    if governance.get("inputs_are_consumed_not_recalculated") is not True:
        errors.append("INPUT_RECALCULATION_ALLOWED")

    for key in [
        "blocked_evidence_may_support_authority",
        "unavailable_evidence_may_support_authority",
        "unknown_evidence_may_support_authority",
        "invalid_provenance_may_support_authority",
        "publication_ineligible_evidence_may_support_authority_where_required",
    ]:
        if governance.get(key) is not False:
            errors.append("UNUSABLE_EVIDENCE_PROMOTION_ALLOWED")
            break

    for key in [
        "missing_is_neutral",
        "missing_is_negative",
        "missing_is_positive",
        "missing_is_zero",
    ]:
        if governance.get(key) is not False:
            errors.append("MISSING_SEMANTICS_CHANGED")
            break

    shortcuts = p.get("non_shortcut_rules", {})

    for key in [
        "score_label_alone_establishes_authority",
        "normalized_score_alone_establishes_authority",
        "risk_level_alone_establishes_authority",
        "confidence_status_alone_establishes_authority",
        "signal_score_alone_establishes_authority",
        "single_evidence_domain_alone_establishes_authority",
    ]:
        if shortcuts.get(key) is not False:
            errors.append("ACTIONABLE_SHORTCUT_ALLOWED")
            break

    thresholds = p.get("threshold_governance", {})

    for key in [
        "defines_new_numeric_thresholds",
        "duplicates_upstream_numeric_thresholds",
        "redefines_score_thresholds",
        "redefines_signal_thresholds",
        "redefines_confidence_thresholds",
        "redefines_risk_thresholds",
        "redefines_publication_source_tiers",
    ]:
        if thresholds.get(key) is not False:
            errors.append("THRESHOLD_GOVERNANCE_VIOLATION")
            break

    restrictions = p.get("restriction_precedence", {})

    for key in [
        "insufficient_evidence_blocks_authority",
        "unresolved_material_conflict_blocks_authority",
        "material_risk_restriction_blocks_authority",
        "required_confirmation_missing_blocks_authority",
        "publication_ineligibility_where_required_blocks_authority",
    ]:
        if restrictions.get(key) is not True:
            errors.append("RESTRICTION_PRECEDENCE_WEAKENED")
            break

    if restrictions.get("positive_authority_may_override_restriction") \
            is not False:
        errors.append("POSITIVE_AUTHORITY_OVERRIDE_ALLOWED")

    fallback = p.get("fallback_semantics", {})

    if fallback.get("authority_not_established_state") != "WATCH":
        errors.append("AUTHORITY_FALLBACK_CHANGED")

    if fallback.get("watch_requires_usable_evidence") is not True:
        errors.append("WATCH_USABLE_EVIDENCE_REQUIREMENT_DISABLED")

    if fallback.get("watch_requires_no_higher_priority_restriction") \
            is not True:
        errors.append("WATCH_RESTRICTION_REQUIREMENT_DISABLED")

    if fallback.get("missing_evidence_does_not_fallback_to_watch") \
            is not True:
        errors.append("MISSING_EVIDENCE_BECAME_WATCH")

    info = p.get("information_class", {})

    expected_info = {
        "input_observations": "FACT",
        "upstream_analytical_outputs": "MODEL",
        "directional_thesis": "INFERENCE",
        "actionable_authority_assessment": "INFERENCE",
        "decision_state": "DECISION",
        "inference_may_be_presented_as_fact": False,
        "decision_may_be_presented_as_fact": False,
    }

    if info != expected_info:
        errors.append("INFORMATION_CLASS_CHANGED")

    boundary = p.get("phase_boundary", {})

    for key in [
        "implements_evidence_gate",
        "implements_conflict_resolver",
        "implements_decision_state_engine",
        "writes_decision_center",
        "modifies_generator",
        "modifies_schema_v3",
        "modifies_v2_1",
    ]:
        if boundary.get(key) is not False:
            errors.append("PHASE_BOUNDARY_VIOLATION")
            break

    prohibitions = set(p.get("prohibited_behaviors", []))

    if not REQUIRED_PROHIBITIONS.issubset(prohibitions):
        errors.append("MANDATORY_PROHIBITION_REMOVED")

    return sorted(set(errors))


BASELINE = load_policy()
baseline_errors = validate(BASELINE)

if baseline_errors:
    print("BASELINE POLICY IS INVALID")
    for error in baseline_errors:
        print(" -", error)
    sys.exit(1)


def mutation(name, expected_error, mutate):
    return {
        "name": name,
        "expected_error": expected_error,
        "mutate": mutate,
    }


cases = [
    mutation(
        "allow_v2_1_modification",
        "V2_1_PRESERVATION_DISABLED",
        lambda p: p["compatibility"].__setitem__("preserves_v2_1", False),
    ),
    mutation(
        "require_schema_change",
        "SCHEMA_CHANGE_INTRODUCED",
        lambda p: p["compatibility"].__setitem__("schema_change_required", True),
    ),
    mutation(
        "require_public_output_change",
        "PUBLIC_OUTPUT_CHANGE_INTRODUCED",
        lambda p: p["compatibility"].__setitem__(
            "public_output_change_required", True
        ),
    ),
    mutation(
        "allow_modify_d2d2",
        "D2D2_MODIFICATION_ALLOWED",
        lambda p: p["compatibility"].__setitem__(
            "modifies_decision_policy_v3", True
        ),
    ),
    mutation(
        "introduce_trade_execution",
        "TRADE_EXECUTION_INTRODUCED",
        lambda p: p["purpose"].__setitem__("defines_trade_execution", True),
    ),
    mutation(
        "introduce_buy_sell_instruction",
        "BUY_SELL_INSTRUCTION_INTRODUCED",
        lambda p: p["purpose"].__setitem__(
            "defines_buy_or_sell_instruction", True
        ),
    ),
    mutation(
        "introduce_portfolio_action",
        "PORTFOLIO_ACTION_INTRODUCED",
        lambda p: p["purpose"].__setitem__("defines_portfolio_action", True),
    ),
    mutation(
        "allow_upstream_recalculation",
        "UPSTREAM_RECALCULATION_ALLOWED",
        lambda p: p["purpose"].__setitem__("recalculates_upstream_models", True),
    ),
    mutation(
        "authority_becomes_default",
        "AUTHORITY_BECAME_DEFAULT",
        lambda p: p["authority_semantics"].__setitem__(
            "authority_is_default", True
        ),
    ),
    mutation(
        "authority_becomes_trade_instruction",
        "AUTHORITY_BECAME_TRADE_INSTRUCTION",
        lambda p: p["authority_semantics"].__setitem__(
            "authority_is_trade_instruction", True
        ),
    ),
    mutation(
        "authority_becomes_buy",
        "AUTHORITY_BECAME_BUY",
        lambda p: p["authority_semantics"].__setitem__("authority_is_buy", True),
    ),
    mutation(
        "authority_becomes_sell",
        "AUTHORITY_BECAME_SELL",
        lambda p: p["authority_semantics"].__setitem__("authority_is_sell", True),
    ),
    mutation(
        "authority_becomes_guarantee",
        "AUTHORITY_BECAME_GUARANTEE",
        lambda p: p["authority_semantics"].__setitem__(
            "authority_is_guarantee", True
        ),
    ),
    mutation(
        "allow_authority_invention",
        "AUTHORITY_INVENTION_ALLOWED",
        lambda p: p["authority_semantics"].__setitem__(
            "authority_may_be_invented", True
        ),
    ),
    mutation(
        "disable_all_conditions_required",
        "AUTHORITY_CONVERGENCE_WEAKENED",
        lambda p: p["establishment_rule"].__setitem__(
            "all_conditions_required", False
        ),
    ),
    mutation(
        "remove_evidence_gate",
        "AUTHORITY_CONDITIONS_CHANGED",
        lambda p: p["establishment_rule"]["conditions"].remove(
            "EVIDENCE_GATE_PASSED"
        ),
    ),
    mutation(
        "remove_explicit_directional_thesis",
        "AUTHORITY_CONDITIONS_CHANGED",
        lambda p: p["establishment_rule"]["conditions"].remove(
            "EXPLICIT_DIRECTIONAL_THESIS_PRESENT"
        ),
    ),
    mutation(
        "remove_evidence_support_for_thesis",
        "AUTHORITY_CONDITIONS_CHANGED",
        lambda p: p["establishment_rule"]["conditions"].remove(
            "DIRECTIONAL_THESIS_SUPPORTED_BY_AUTHORIZED_EVIDENCE"
        ),
    ),
    mutation(
        "remove_material_conflict_block",
        "AUTHORITY_CONDITIONS_CHANGED",
        lambda p: p["establishment_rule"]["conditions"].remove(
            "NO_UNRESOLVED_MATERIAL_CONFLICT"
        ),
    ),
    mutation(
        "remove_material_risk_block",
        "AUTHORITY_CONDITIONS_CHANGED",
        lambda p: p["establishment_rule"]["conditions"].remove(
            "NO_MATERIAL_RISK_RESTRICTION"
        ),
    ),
    mutation(
        "remove_confirmation_requirement",
        "AUTHORITY_CONDITIONS_CHANGED",
        lambda p: p["establishment_rule"]["conditions"].remove(
            "NO_REQUIRED_CONFIRMATION_MISSING"
        ),
    ),
    mutation(
        "remove_publication_requirement",
        "AUTHORITY_CONDITIONS_CHANGED",
        lambda p: p["establishment_rule"]["conditions"].remove(
            "PUBLICATION_REQUIREMENTS_SATISFIED_WHERE_APPLICABLE"
        ),
    ),
    mutation(
        "make_directional_thesis_optional",
        "DIRECTIONAL_THESIS_REQUIREMENT_WEAKENED",
        lambda p: p["directional_thesis"].__setitem__("required", False),
    ),
    mutation(
        "allow_thesis_from_score_label",
        "DIRECTIONAL_THESIS_INVENTION_ALLOWED",
        lambda p: p["directional_thesis"].__setitem__(
            "may_be_invented_from_score_label", True
        ),
    ),
    mutation(
        "allow_thesis_from_normalized_score",
        "DIRECTIONAL_THESIS_INVENTION_ALLOWED",
        lambda p: p["directional_thesis"].__setitem__(
            "may_be_invented_from_normalized_score", True
        ),
    ),
    mutation(
        "allow_thesis_from_risk_level",
        "DIRECTIONAL_THESIS_INVENTION_ALLOWED",
        lambda p: p["directional_thesis"].__setitem__(
            "may_be_invented_from_risk_level", True
        ),
    ),
    mutation(
        "allow_blocked_evidence",
        "UNUSABLE_EVIDENCE_PROMOTION_ALLOWED",
        lambda p: p["input_governance"].__setitem__(
            "blocked_evidence_may_support_authority", True
        ),
    ),
    mutation(
        "allow_unavailable_evidence",
        "UNUSABLE_EVIDENCE_PROMOTION_ALLOWED",
        lambda p: p["input_governance"].__setitem__(
            "unavailable_evidence_may_support_authority", True
        ),
    ),
    mutation(
        "allow_invalid_provenance",
        "UNUSABLE_EVIDENCE_PROMOTION_ALLOWED",
        lambda p: p["input_governance"].__setitem__(
            "invalid_provenance_may_support_authority", True
        ),
    ),
    mutation(
        "missing_becomes_neutral",
        "MISSING_SEMANTICS_CHANGED",
        lambda p: p["input_governance"].__setitem__("missing_is_neutral", True),
    ),
    mutation(
        "score_label_alone_establishes_authority",
        "ACTIONABLE_SHORTCUT_ALLOWED",
        lambda p: p["non_shortcut_rules"].__setitem__(
            "score_label_alone_establishes_authority", True
        ),
    ),
    mutation(
        "normalized_score_alone_establishes_authority",
        "ACTIONABLE_SHORTCUT_ALLOWED",
        lambda p: p["non_shortcut_rules"].__setitem__(
            "normalized_score_alone_establishes_authority", True
        ),
    ),
    mutation(
        "risk_level_alone_establishes_authority",
        "ACTIONABLE_SHORTCUT_ALLOWED",
        lambda p: p["non_shortcut_rules"].__setitem__(
            "risk_level_alone_establishes_authority", True
        ),
    ),
    mutation(
        "confidence_alone_establishes_authority",
        "ACTIONABLE_SHORTCUT_ALLOWED",
        lambda p: p["non_shortcut_rules"].__setitem__(
            "confidence_status_alone_establishes_authority", True
        ),
    ),
    mutation(
        "signal_alone_establishes_authority",
        "ACTIONABLE_SHORTCUT_ALLOWED",
        lambda p: p["non_shortcut_rules"].__setitem__(
            "signal_score_alone_establishes_authority", True
        ),
    ),
    mutation(
        "single_domain_establishes_authority",
        "ACTIONABLE_SHORTCUT_ALLOWED",
        lambda p: p["non_shortcut_rules"].__setitem__(
            "single_evidence_domain_alone_establishes_authority", True
        ),
    ),
    mutation(
        "introduce_numeric_thresholds",
        "THRESHOLD_GOVERNANCE_VIOLATION",
        lambda p: p["threshold_governance"].__setitem__(
            "defines_new_numeric_thresholds", True
        ),
    ),
    mutation(
        "duplicate_upstream_thresholds",
        "THRESHOLD_GOVERNANCE_VIOLATION",
        lambda p: p["threshold_governance"].__setitem__(
            "duplicates_upstream_numeric_thresholds", True
        ),
    ),
    mutation(
        "disable_insufficient_evidence_block",
        "RESTRICTION_PRECEDENCE_WEAKENED",
        lambda p: p["restriction_precedence"].__setitem__(
            "insufficient_evidence_blocks_authority", False
        ),
    ),
    mutation(
        "disable_material_conflict_block",
        "RESTRICTION_PRECEDENCE_WEAKENED",
        lambda p: p["restriction_precedence"].__setitem__(
            "unresolved_material_conflict_blocks_authority", False
        ),
    ),
    mutation(
        "disable_material_risk_block",
        "RESTRICTION_PRECEDENCE_WEAKENED",
        lambda p: p["restriction_precedence"].__setitem__(
            "material_risk_restriction_blocks_authority", False
        ),
    ),
    mutation(
        "assume_confirmation_satisfied",
        "RESTRICTION_PRECEDENCE_WEAKENED",
        lambda p: p["restriction_precedence"].__setitem__(
            "required_confirmation_missing_blocks_authority", False
        ),
    ),
    mutation(
        "disable_publication_block",
        "RESTRICTION_PRECEDENCE_WEAKENED",
        lambda p: p["restriction_precedence"].__setitem__(
            "publication_ineligibility_where_required_blocks_authority", False
        ),
    ),
    mutation(
        "allow_authority_override_restriction",
        "POSITIVE_AUTHORITY_OVERRIDE_ALLOWED",
        lambda p: p["restriction_precedence"].__setitem__(
            "positive_authority_may_override_restriction", True
        ),
    ),
    mutation(
        "missing_falls_back_to_watch",
        "MISSING_EVIDENCE_BECAME_WATCH",
        lambda p: p["fallback_semantics"].__setitem__(
            "missing_evidence_does_not_fallback_to_watch", False
        ),
    ),
    mutation(
        "watch_without_usable_evidence",
        "WATCH_USABLE_EVIDENCE_REQUIREMENT_DISABLED",
        lambda p: p["fallback_semantics"].__setitem__(
            "watch_requires_usable_evidence", False
        ),
    ),
    mutation(
        "watch_ignores_higher_restriction",
        "WATCH_RESTRICTION_REQUIREMENT_DISABLED",
        lambda p: p["fallback_semantics"].__setitem__(
            "watch_requires_no_higher_priority_restriction", False
        ),
    ),
    mutation(
        "change_fallback_to_actionable",
        "AUTHORITY_FALLBACK_CHANGED",
        lambda p: p["fallback_semantics"].__setitem__(
            "authority_not_established_state", "ACTIONABLE"
        ),
    ),
    mutation(
        "directional_thesis_becomes_fact",
        "INFORMATION_CLASS_CHANGED",
        lambda p: p["information_class"].__setitem__(
            "directional_thesis", "FACT"
        ),
    ),
    mutation(
        "authority_assessment_becomes_decision",
        "INFORMATION_CLASS_CHANGED",
        lambda p: p["information_class"].__setitem__(
            "actionable_authority_assessment", "DECISION"
        ),
    ),
    mutation(
        "write_decision_center_in_d2d4b",
        "PHASE_BOUNDARY_VIOLATION",
        lambda p: p["phase_boundary"].__setitem__(
            "writes_decision_center", True
        ),
    ),
    mutation(
        "implement_evidence_gate_in_d2d4b",
        "PHASE_BOUNDARY_VIOLATION",
        lambda p: p["phase_boundary"].__setitem__(
            "implements_evidence_gate", True
        ),
    ),
    mutation(
        "modify_generator_in_d2d4b",
        "PHASE_BOUNDARY_VIOLATION",
        lambda p: p["phase_boundary"].__setitem__(
            "modifies_generator", True
        ),
    ),
    mutation(
        "remove_no_score_shortcut_prohibition",
        "MANDATORY_PROHIBITION_REMOVED",
        lambda p: p["prohibited_behaviors"].remove(
            "CREATE_AUTHORITY_FROM_SCORE_ALONE"
        ),
    ),
    mutation(
        "remove_no_buy_translation_prohibition",
        "MANDATORY_PROHIBITION_REMOVED",
        lambda p: p["prohibited_behaviors"].remove(
            "TRANSLATE_ACTIONABLE_AUTHORITY_TO_BUY"
        ),
    ),
    mutation(
        "remove_trade_execution_prohibition",
        "MANDATORY_PROHIBITION_REMOVED",
        lambda p: p["prohibited_behaviors"].remove(
            "EXECUTE_TRADE_FROM_ACTIONABLE_AUTHORITY"
        ),
    ),
]


passed = 0
failed = 0

for case in cases:
    candidate = copy.deepcopy(BASELINE)
    case["mutate"](candidate)

    errors = validate(candidate)
    expected = case["expected_error"]

    if expected in errors:
        print(f'[PASS] {case["name"]} -> {expected}')
        passed += 1
    else:
        print(
            f'[FAIL] {case["name"]} -> expected {expected}; '
            f'got {errors}'
        )
        failed += 1


print()
print("=" * 64)
print(" D.2D.4C - ADVERSARIAL ACTIONABLE AUTHORITY TEST")
print("=" * 64)
print(f"Cases executed: {len(cases)}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print("RESULT:", "APPROVED" if failed == 0 else "REJECTED")

sys.exit(0 if failed == 0 else 1)
