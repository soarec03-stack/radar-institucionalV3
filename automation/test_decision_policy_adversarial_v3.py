import copy
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
POLICY_PATH = BASE_DIR / "decision_policy_v3.json"


EXPECTED_STATES = [
    "INSUFFICIENT_EVIDENCE",
    "THESIS_REVIEW",
    "RISK_REVIEW",
    "WAIT_FOR_CONFIRMATION",
    "WATCH",
    "ACTIONABLE",
]

EXPECTED_LABELS = {
    "STRONG_BUY",
    "BUY",
    "WATCH_ACCUMULATE",
    "HOLD",
    "CAUTION",
    "AVOID",
}

EXPECTED_RISK_LEVELS = {
    "LOW",
    "MODERATE",
    "HIGH",
    "VERY_HIGH",
    "CRITICAL",
}

EXPECTED_REQUIREMENTS = {
    "EVIDENCE_GATE_PASSED",
    "NO_UNRESOLVED_MATERIAL_CONFLICT",
    "NO_MATERIAL_RISK_RESTRICTION",
    "NO_REQUIRED_CONFIRMATION_MISSING",
    "PUBLICATION_REQUIREMENTS_SATISFIED_WHERE_APPLICABLE",
    "ACTIONABLE_AUTHORITY_EXPLICITLY_ESTABLISHED",
}


def load_policy():
    with POLICY_PATH.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def validate_contract(policy):
    errors = []

    # --------------------------------------------------------
    # Identity / compatibility
    # --------------------------------------------------------

    if policy.get("policy_id") != "RADAR_V3_DECISION_POLICY":
        errors.append("POLICY_ID_CHANGED")

    if policy.get("policy_version") != "3.4D.2D.2":
        errors.append("POLICY_VERSION_CHANGED")

    if policy.get("status") != "DRAFT":
        errors.append("POLICY_STATUS_CHANGED")

    if policy.get("scope") != "RADAR_INSTITUCIONAL_V3_ONLY":
        errors.append("POLICY_SCOPE_CHANGED")

    compatibility = policy.get("compatibility", {})

    if compatibility.get("preserve_v2_1") is not True:
        errors.append("V2_1_NOT_PRESERVED")

    if compatibility.get("may_modify_v2_1") is not False:
        errors.append("V2_1_MODIFICATION_ALLOWED")

    if (
        compatibility.get("preserve_existing_v3_decision_center_root")
        is not True
    ):
        errors.append("V3_DECISION_CENTER_ROOT_NOT_PRESERVED")

    if compatibility.get("schema_change_required_by_this_policy") is not False:
        errors.append("SCHEMA_CHANGE_INTRODUCED")

    if compatibility.get("public_output_change_required_by_this_policy") is not False:
        errors.append("PUBLIC_OUTPUT_CHANGE_INTRODUCED")

    # --------------------------------------------------------
    # Ownership
    # --------------------------------------------------------

    ownership = policy.get("ownership", {})

    if ownership.get("decision_center_owns_decision_state") is not True:
        errors.append("DECISION_STATE_OWNERSHIP_CHANGED")

    for key in [
        "decision_center_owns_score",
        "decision_center_owns_risk",
        "decision_center_owns_confidence",
        "decision_center_owns_publication_eligibility",
        "decision_center_owns_domain_signals",
        "decision_center_may_recalculate_upstream_models",
        "decision_center_may_promote_upstream_evidence",
    ]:
        if ownership.get(key) is not False:
            errors.append(f"OWNERSHIP_BOUNDARY_CHANGED:{key}")

    # --------------------------------------------------------
    # Threshold governance
    # --------------------------------------------------------

    threshold = policy.get("threshold_governance", {})

    if threshold.get("reuse_upstream_thresholds") is not True:
        errors.append("UPSTREAM_THRESHOLD_REUSE_DISABLED")

    for key in [
        "duplicate_upstream_numeric_thresholds",
        "decision_center_may_redefine_signal_coverage_threshold",
        "decision_center_may_redefine_score_coverage_threshold",
        "decision_center_may_redefine_confidence_thresholds",
        "decision_center_may_redefine_risk_level_thresholds",
        "decision_center_may_redefine_publication_source_tiers",
    ]:
        if threshold.get(key) is not False:
            errors.append(f"THRESHOLD_GOVERNANCE_VIOLATION:{key}")

    if threshold.get("decision_specific_rules_must_be_explicit") is not True:
        errors.append("IMPLICIT_DECISION_RULES_ALLOWED")

    # --------------------------------------------------------
    # Evidence authority
    # --------------------------------------------------------

    evidence = policy.get("evidence_authority", {})

    insufficient_keys = [
        "missing_required_evidence",
        "unavailable_required_evidence",
        "blocked_required_evidence",
        "invalid_required_provenance",
        "insufficient_required_coverage",
        "publication_ineligible_where_required",
        "unknown_required_evidence_status",
    ]

    for key in insufficient_keys:
        if evidence.get(key) != "INSUFFICIENT_EVIDENCE":
            errors.append(f"EVIDENCE_FAIL_CLOSED_CHANGED:{key}")

    for key in [
        "missing_is_neutral",
        "missing_is_negative",
        "missing_is_positive",
        "missing_is_zero",
        "blocked_evidence_may_support_actionable",
        "unavailable_evidence_may_support_actionable",
        "unknown_evidence_may_support_actionable",
    ]:
        if evidence.get(key) is not False:
            errors.append(f"EVIDENCE_AUTHORITY_PROMOTION:{key}")

    # --------------------------------------------------------
    # Conflict policy
    # --------------------------------------------------------

    conflict = policy.get("conflict_policy", {})

    if conflict.get("decision_policy_invents_conflict_materiality") is not False:
        errors.append("CONFLICT_MATERIALITY_INVENTED")

    if conflict.get("material_conflict_must_remain_visible") is not True:
        errors.append("CONFLICT_VISIBILITY_DISABLED")

    if (
        conflict.get("unresolved_material_conflict_state")
        != "THESIS_REVIEW"
    ):
        errors.append("CONFLICT_STATE_CHANGED")

    for key in [
        "high_score_may_hide_material_conflict",
        "score_label_may_resolve_material_conflict",
        "conflict_may_be_silently_discarded",
    ]:
        if conflict.get(key) is not False:
            errors.append(f"CONFLICT_SAFETY_VIOLATION:{key}")

    # --------------------------------------------------------
    # Risk policy
    # --------------------------------------------------------

    risk = policy.get("risk_policy", {})

    if risk.get("decision_policy_invents_risk_score") is not False:
        errors.append("RISK_SCORE_INVENTION_ALLOWED")

    if risk.get("decision_policy_recalculates_risk_level") is not False:
        errors.append("RISK_RECALCULATION_ALLOWED")

    level_mapping = risk.get("level_mapping", {})

    if set(level_mapping.keys()) != EXPECTED_RISK_LEVELS:
        errors.append("RISK_LEVEL_VOCABULARY_CHANGED")
    else:
        for level in EXPECTED_RISK_LEVELS:
            if level_mapping.get(level) != "NO_AUTOMATIC_DECISION_STATE":
                errors.append(f"RISK_LEVEL_DIRECT_MAPPING:{level}")

    if risk.get("risk_level_alone_selects_risk_review") is not False:
        errors.append("RISK_LEVEL_AUTOMATIC_REVIEW_ALLOWED")

    if risk.get("material_risk_restriction_state") != "RISK_REVIEW":
        errors.append("MATERIAL_RISK_STATE_CHANGED")

    if risk.get("risk_review_is_automatic_rejection") is not False:
        errors.append("RISK_REVIEW_BECAME_REJECTION")

    if risk.get("missing_risk_may_be_assumed_safe") is not False:
        errors.append("MISSING_RISK_ASSUMED_SAFE")

    # --------------------------------------------------------
    # Confirmation policy
    # --------------------------------------------------------

    confirmation = policy.get("confirmation_policy", {})

    if (
        confirmation.get("decision_policy_invents_required_confirmation")
        is not False
    ):
        errors.append("CONFIRMATION_INVENTION_ALLOWED")

    if (
        confirmation.get("required_confirmation_missing_state")
        != "WAIT_FOR_CONFIRMATION"
    ):
        errors.append("CONFIRMATION_STATE_CHANGED")

    for key in [
        "score_label_may_satisfy_confirmation",
        "high_score_may_satisfy_confirmation",
        "missing_confirmation_may_be_assumed_satisfied",
    ]:
        if confirmation.get(key) is not False:
            errors.append(f"CONFIRMATION_SAFETY_VIOLATION:{key}")

    # --------------------------------------------------------
    # ACTIONABLE authority
    # --------------------------------------------------------

    actionable = policy.get("actionable_authority", {})

    if actionable.get("actionable_is_positive_authority") is not True:
        errors.append("ACTIONABLE_POSITIVE_AUTHORITY_DISABLED")

    if actionable.get("actionable_is_default_state") is not False:
        errors.append("ACTIONABLE_BECAME_DEFAULT")

    if set(actionable.get("requires", [])) != EXPECTED_REQUIREMENTS:
        errors.append("ACTIONABLE_REQUIREMENTS_CHANGED")

    for key in [
        "score_label_alone_establishes_actionable_authority",
        "normalized_score_alone_establishes_actionable_authority",
        "risk_level_alone_establishes_actionable_authority",
        "confidence_status_alone_establishes_actionable_authority",
        "actionable_authority_may_be_invented",
    ]:
        if actionable.get(key) is not False:
            errors.append(f"ACTIONABLE_SHORTCUT_ALLOWED:{key}")

    establishment = actionable.get("authority_establishment", {})

    if establishment.get("mode") != "EXPLICIT_FUTURE_RULE_REQUIRED":
        errors.append("ACTIONABLE_AUTHORITY_MODE_CHANGED")

    if establishment.get("defined_in_this_policy") is not False:
        errors.append("ACTIONABLE_TRIGGER_INVENTED_IN_D2D2")

    if establishment.get("fallback_when_not_established") != "WATCH":
        errors.append("ACTIONABLE_FALLBACK_CHANGED")

    # --------------------------------------------------------
    # WATCH
    # --------------------------------------------------------

    watch = policy.get("watch_policy", {})

    for key in [
        "watch_is_neutral",
        "watch_is_hold",
        "watch_is_buy",
        "watch_is_accumulate",
        "watch_is_default_for_missing_evidence",
    ]:
        if watch.get(key) is not False:
            errors.append(f"WATCH_SEMANTICS_CHANGED:{key}")

    for key in [
        "requires_usable_evidence",
        "requires_no_higher_priority_restriction",
        "requires_actionable_authority_not_established",
    ]:
        if watch.get(key) is not True:
            errors.append(f"WATCH_REQUIREMENT_CHANGED:{key}")

    # --------------------------------------------------------
    # State selection
    # --------------------------------------------------------

    selection = policy.get("state_selection", {})

    if selection.get("mode") != "FAIL_CLOSED_FIRST_MATCH":
        errors.append("FAIL_CLOSED_SELECTION_DISABLED")

    if selection.get("evaluation_order") != EXPECTED_STATES:
        errors.append("STATE_PRECEDENCE_CHANGED")

    rules = selection.get("rules", [])

    if [rule.get("state") for rule in rules] != EXPECTED_STATES:
        errors.append("STATE_RULE_ORDER_CHANGED")

    if [rule.get("priority") for rule in rules] != [1, 2, 3, 4, 5, 6]:
        errors.append("STATE_PRIORITY_CHANGED")

    if (
        selection.get("unknown_condition_behavior")
        != "INSUFFICIENT_EVIDENCE"
    ):
        errors.append("UNKNOWN_CONDITION_FAIL_OPEN")

    # --------------------------------------------------------
    # Score label non-mapping
    # --------------------------------------------------------

    non_mapping = policy.get("score_label_non_mapping", {})

    if set(non_mapping.keys()) != EXPECTED_LABELS:
        errors.append("SCORE_LABEL_SET_CHANGED")
    else:
        for label in EXPECTED_LABELS:
            if non_mapping.get(label) != "NO_DIRECT_DECISION_STATE":
                errors.append(f"SCORE_LABEL_DIRECT_MAPPING:{label}")

    # --------------------------------------------------------
    # Information classes
    # --------------------------------------------------------

    classes = policy.get("information_classes", {})

    expected_classes = {
        "upstream_observation": "FACT",
        "score": "MODEL",
        "risk": "MODEL",
        "signal": "MODEL",
        "conflict_resolution": "INFERENCE",
        "confirmation_assessment": "INFERENCE",
        "decision_state": "DECISION",
    }

    for key, value in expected_classes.items():
        if classes.get(key) != value:
            errors.append(f"INFORMATION_CLASS_CHANGED:{key}")

    if classes.get("inference_may_be_presented_as_fact") is not False:
        errors.append("INFERENCE_MAY_BE_FACT")

    if classes.get("decision_may_be_presented_as_fact") is not False:
        errors.append("DECISION_MAY_BE_FACT")

    # --------------------------------------------------------
    # Phase boundaries
    # --------------------------------------------------------

    boundaries = policy.get("phase_boundaries", {})

    for key in [
        "implements_evidence_gate_engine",
        "implements_conflict_resolver",
        "implements_decision_state_engine",
        "writes_decision_center",
        "modifies_generator",
    ]:
        if boundaries.get(key) is not False:
            errors.append(f"PHASE_BOUNDARY_VIOLATION:{key}")

    expected_phases = {
        "evidence_gate_implementation_phase": "D.3",
        "conflict_resolver_implementation_phase": "D.4",
        "decision_state_engine_phase": "D.5",
        "generator_integration_phase": "D.7",
    }

    for key, value in expected_phases.items():
        if boundaries.get(key) != value:
            errors.append(f"PHASE_ASSIGNMENT_CHANGED:{key}")

    return errors


def set_path(obj, path, value):
    cursor = obj

    for key in path[:-1]:
        cursor = cursor[key]

    cursor[path[-1]] = value


def remove_list_value(obj, path, value):
    cursor = obj

    for key in path:
        cursor = cursor[key]

    cursor.remove(value)


def run_mutation(baseline, name, mutate, expected_error):
    candidate = copy.deepcopy(baseline)
    mutate(candidate)

    errors = validate_contract(candidate)

    matched = (
        expected_error in errors
        or any(
            error.startswith(expected_error)
            for error in errors
        )
    )

    if matched:
        print(f"[PASS] {name} -> {expected_error}")
        return True

    print(
        f"[FAIL] {name} -> expected {expected_error}; "
        f"received {errors}"
    )

    return False


baseline = load_policy()
baseline_errors = validate_contract(baseline)

if baseline_errors:
    print("BASELINE POLICY IS INVALID")
    for error in baseline_errors:
        print(f" - {error}")
    raise SystemExit(1)


cases = []


def add(name, path, value, expected_error):
    cases.append(
        (
            name,
            lambda obj, p=path, v=value: set_path(obj, p, v),
            expected_error,
        )
    )


add(
    "allow_v2_1_modification",
    ["compatibility", "may_modify_v2_1"],
    True,
    "V2_1_MODIFICATION_ALLOWED",
)

add(
    "require_schema_change",
    ["compatibility", "schema_change_required_by_this_policy"],
    True,
    "SCHEMA_CHANGE_INTRODUCED",
)

add(
    "decision_center_owns_score",
    ["ownership", "decision_center_owns_score"],
    True,
    "OWNERSHIP_BOUNDARY_CHANGED",
)

add(
    "allow_upstream_recalculation",
    ["ownership", "decision_center_may_recalculate_upstream_models"],
    True,
    "OWNERSHIP_BOUNDARY_CHANGED",
)

add(
    "allow_evidence_promotion",
    ["ownership", "decision_center_may_promote_upstream_evidence"],
    True,
    "OWNERSHIP_BOUNDARY_CHANGED",
)

add(
    "duplicate_upstream_thresholds",
    ["threshold_governance", "duplicate_upstream_numeric_thresholds"],
    True,
    "THRESHOLD_GOVERNANCE_VIOLATION",
)

add(
    "redefine_signal_coverage",
    [
        "threshold_governance",
        "decision_center_may_redefine_signal_coverage_threshold",
    ],
    True,
    "THRESHOLD_GOVERNANCE_VIOLATION",
)

add(
    "redefine_score_coverage",
    [
        "threshold_governance",
        "decision_center_may_redefine_score_coverage_threshold",
    ],
    True,
    "THRESHOLD_GOVERNANCE_VIOLATION",
)

add(
    "redefine_confidence_thresholds",
    [
        "threshold_governance",
        "decision_center_may_redefine_confidence_thresholds",
    ],
    True,
    "THRESHOLD_GOVERNANCE_VIOLATION",
)

add(
    "missing_becomes_neutral",
    ["evidence_authority", "missing_is_neutral"],
    True,
    "EVIDENCE_AUTHORITY_PROMOTION",
)

add(
    "missing_becomes_positive",
    ["evidence_authority", "missing_is_positive"],
    True,
    "EVIDENCE_AUTHORITY_PROMOTION",
)

add(
    "blocked_evidence_supports_actionable",
    [
        "evidence_authority",
        "blocked_evidence_may_support_actionable",
    ],
    True,
    "EVIDENCE_AUTHORITY_PROMOTION",
)

add(
    "unavailable_evidence_supports_actionable",
    [
        "evidence_authority",
        "unavailable_evidence_may_support_actionable",
    ],
    True,
    "EVIDENCE_AUTHORITY_PROMOTION",
)

add(
    "missing_required_evidence_becomes_watch",
    [
        "evidence_authority",
        "missing_required_evidence",
    ],
    "WATCH",
    "EVIDENCE_FAIL_CLOSED_CHANGED",
)

add(
    "invent_conflict_materiality",
    [
        "conflict_policy",
        "decision_policy_invents_conflict_materiality",
    ],
    True,
    "CONFLICT_MATERIALITY_INVENTED",
)

add(
    "hide_material_conflict",
    [
        "conflict_policy",
        "material_conflict_must_remain_visible",
    ],
    False,
    "CONFLICT_VISIBILITY_DISABLED",
)

add(
    "high_score_hides_conflict",
    [
        "conflict_policy",
        "high_score_may_hide_material_conflict",
    ],
    True,
    "CONFLICT_SAFETY_VIOLATION",
)

add(
    "change_conflict_state",
    [
        "conflict_policy",
        "unresolved_material_conflict_state",
    ],
    "WATCH",
    "CONFLICT_STATE_CHANGED",
)

add(
    "invent_risk_score",
    ["risk_policy", "decision_policy_invents_risk_score"],
    True,
    "RISK_SCORE_INVENTION_ALLOWED",
)

add(
    "recalculate_risk_level",
    ["risk_policy", "decision_policy_recalculates_risk_level"],
    True,
    "RISK_RECALCULATION_ALLOWED",
)

add(
    "high_risk_directly_selects_state",
    ["risk_policy", "level_mapping", "HIGH"],
    "RISK_REVIEW",
    "RISK_LEVEL_DIRECT_MAPPING",
)

add(
    "risk_level_alone_selects_review",
    ["risk_policy", "risk_level_alone_selects_risk_review"],
    True,
    "RISK_LEVEL_AUTOMATIC_REVIEW_ALLOWED",
)

add(
    "missing_risk_assumed_safe",
    ["risk_policy", "missing_risk_may_be_assumed_safe"],
    True,
    "MISSING_RISK_ASSUMED_SAFE",
)

add(
    "risk_review_becomes_rejection",
    ["risk_policy", "risk_review_is_automatic_rejection"],
    True,
    "RISK_REVIEW_BECAME_REJECTION",
)

add(
    "invent_required_confirmation",
    [
        "confirmation_policy",
        "decision_policy_invents_required_confirmation",
    ],
    True,
    "CONFIRMATION_INVENTION_ALLOWED",
)

add(
    "score_label_satisfies_confirmation",
    [
        "confirmation_policy",
        "score_label_may_satisfy_confirmation",
    ],
    True,
    "CONFIRMATION_SAFETY_VIOLATION",
)

add(
    "missing_confirmation_assumed_satisfied",
    [
        "confirmation_policy",
        "missing_confirmation_may_be_assumed_satisfied",
    ],
    True,
    "CONFIRMATION_SAFETY_VIOLATION",
)

add(
    "actionable_becomes_default",
    ["actionable_authority", "actionable_is_default_state"],
    True,
    "ACTIONABLE_BECAME_DEFAULT",
)

add(
    "score_label_establishes_actionable",
    [
        "actionable_authority",
        "score_label_alone_establishes_actionable_authority",
    ],
    True,
    "ACTIONABLE_SHORTCUT_ALLOWED",
)

add(
    "normalized_score_establishes_actionable",
    [
        "actionable_authority",
        "normalized_score_alone_establishes_actionable_authority",
    ],
    True,
    "ACTIONABLE_SHORTCUT_ALLOWED",
)

add(
    "risk_level_establishes_actionable",
    [
        "actionable_authority",
        "risk_level_alone_establishes_actionable_authority",
    ],
    True,
    "ACTIONABLE_SHORTCUT_ALLOWED",
)

add(
    "invent_actionable_trigger",
    [
        "actionable_authority",
        "authority_establishment",
        "defined_in_this_policy",
    ],
    True,
    "ACTIONABLE_TRIGGER_INVENTED_IN_D2D2",
)

add(
    "change_actionable_fallback",
    [
        "actionable_authority",
        "authority_establishment",
        "fallback_when_not_established",
    ],
    "ACTIONABLE",
    "ACTIONABLE_FALLBACK_CHANGED",
)

cases.append(
    (
        "remove_evidence_gate_requirement",
        lambda obj: remove_list_value(
            obj,
            ["actionable_authority", "requires"],
            "EVIDENCE_GATE_PASSED",
        ),
        "ACTIONABLE_REQUIREMENTS_CHANGED",
    )
)

add(
    "watch_becomes_hold",
    ["watch_policy", "watch_is_hold"],
    True,
    "WATCH_SEMANTICS_CHANGED",
)

add(
    "watch_accepts_missing_evidence",
    ["watch_policy", "watch_is_default_for_missing_evidence"],
    True,
    "WATCH_SEMANTICS_CHANGED",
)

add(
    "watch_without_usable_evidence",
    ["watch_policy", "requires_usable_evidence"],
    False,
    "WATCH_REQUIREMENT_CHANGED",
)

add(
    "disable_fail_closed_selection",
    ["state_selection", "mode"],
    "FIRST_MATCH",
    "FAIL_CLOSED_SELECTION_DISABLED",
)

add(
    "unknown_condition_fail_open",
    ["state_selection", "unknown_condition_behavior"],
    "WATCH",
    "UNKNOWN_CONDITION_FAIL_OPEN",
)

cases.append(
    (
        "put_actionable_first",
        lambda obj: obj["state_selection"].__setitem__(
            "evaluation_order",
            [
                "ACTIONABLE",
                "INSUFFICIENT_EVIDENCE",
                "THESIS_REVIEW",
                "RISK_REVIEW",
                "WAIT_FOR_CONFIRMATION",
                "WATCH",
            ],
        ),
        "STATE_PRECEDENCE_CHANGED",
    )
)

add(
    "buy_directly_maps_actionable",
    ["score_label_non_mapping", "BUY"],
    "ACTIONABLE",
    "SCORE_LABEL_DIRECT_MAPPING",
)

add(
    "hold_directly_maps_watch",
    ["score_label_non_mapping", "HOLD"],
    "WATCH",
    "SCORE_LABEL_DIRECT_MAPPING",
)

add(
    "score_becomes_decision_class",
    ["information_classes", "score"],
    "DECISION",
    "INFORMATION_CLASS_CHANGED",
)

add(
    "decision_presented_as_fact",
    ["information_classes", "decision_may_be_presented_as_fact"],
    True,
    "DECISION_MAY_BE_FACT",
)

add(
    "implement_evidence_gate_in_d2d2",
    ["phase_boundaries", "implements_evidence_gate_engine"],
    True,
    "PHASE_BOUNDARY_VIOLATION",
)

add(
    "write_decision_center_in_d2d2",
    ["phase_boundaries", "writes_decision_center"],
    True,
    "PHASE_BOUNDARY_VIOLATION",
)

add(
    "move_evidence_gate_phase",
    ["phase_boundaries", "evidence_gate_implementation_phase"],
    "D.2",
    "PHASE_ASSIGNMENT_CHANGED",
)


passed = 0
failed = 0

for name, mutate, expected_error in cases:
    if run_mutation(
        baseline,
        name,
        mutate,
        expected_error,
    ):
        passed += 1
    else:
        failed += 1


print()
print("=" * 60)
print(" D.2D.3 - ADVERSARIAL DECISION POLICY TEST")
print("=" * 60)
print(f"Cases executed: {len(cases)}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")

if failed:
    print("RESULT: REJECTED")
    raise SystemExit(1)

print("RESULT: APPROVED")
