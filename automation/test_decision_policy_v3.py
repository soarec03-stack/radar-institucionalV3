import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
POLICY_PATH = BASE_DIR / "decision_policy_v3.json"


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


def require_keys(obj, keys, prefix):
    for key in keys:
        check(
            key in obj,
            f"{prefix}.{key} exists",
        )


with POLICY_PATH.open(
    "r",
    encoding="utf-8-sig",
) as handle:
    policy = json.load(handle)


# ------------------------------------------------------------
# Identity / scope
# ------------------------------------------------------------

check(
    policy.get("policy_id")
    == "RADAR_V3_DECISION_POLICY",
    "policy_id is canonical",
)

check(
    policy.get("policy_version")
    == "3.4D.2D.2",
    "policy_version is canonical",
)

check(
    policy.get("status") == "DRAFT",
    "policy remains DRAFT",
)

check(
    policy.get("scope")
    == "RADAR_INSTITUCIONAL_V3_ONLY",
    "scope is V3 only",
)


# ------------------------------------------------------------
# Compatibility
# ------------------------------------------------------------

compat = policy["compatibility"]

check(
    compat["preserve_v2_1"] is True,
    "V2.1 is preserved",
)

check(
    compat["may_modify_v2_1"] is False,
    "V2.1 modification is forbidden",
)

check(
    compat[
        "preserve_existing_v3_decision_center_root"
    ] is True,
    "existing V3 decision_center root is preserved",
)

check(
    compat[
        "schema_change_required_by_this_policy"
    ] is False,
    "D.2D.2 requires no schema change",
)

check(
    compat[
        "public_output_change_required_by_this_policy"
    ] is False,
    "D.2D.2 requires no public output change",
)


# ------------------------------------------------------------
# Ownership
# ------------------------------------------------------------

ownership = policy["ownership"]

check(
    ownership[
        "decision_center_owns_decision_state"
    ] is True,
    "Decision Center owns decision state",
)

for key in [
    "decision_center_owns_score",
    "decision_center_owns_risk",
    "decision_center_owns_confidence",
    "decision_center_owns_publication_eligibility",
    "decision_center_owns_domain_signals",
    "decision_center_may_recalculate_upstream_models",
    "decision_center_may_promote_upstream_evidence",
]:
    check(
        ownership[key] is False,
        f"ownership.{key} is false",
    )


# ------------------------------------------------------------
# Upstream consumption
# ------------------------------------------------------------

upstream = policy["upstream_consumption"]

check(
    upstream["score"]["recalculate"] is False,
    "Score is not recalculated",
)

check(
    upstream["score"]["label_is_decision"] is False,
    "Score label is not a decision",
)

check(
    upstream["score"][
        "label_may_directly_select_state"
    ] is False,
    "Score label cannot directly select state",
)

check(
    set(
        upstream["score"]["recognized_statuses"]
    )
    == {
        "CALCULATED",
        "PARTIAL",
        "INSUFFICIENT_DATA",
    },
    "Score recognized statuses preserve upstream vocabulary",
)

check(
    upstream["confidence"]["recalculate"] is False,
    "Confidence is not recalculated",
)

check(
    set(
        upstream["confidence"]["recognized_statuses"]
    )
    == {
        "VERIFIED",
        "PARTIAL",
        "LOW",
        "UNAVAILABLE",
    },
    "Confidence recognized statuses preserve upstream vocabulary",
)

check(
    upstream["confidence"][
        "unavailable_is_usable"
    ] is False,
    "Unavailable confidence is not usable",
)

check(
    upstream["publication_eligibility"][
        "may_override"
    ] is False,
    "Publication Eligibility cannot be overridden",
)

check(
    upstream["publication_eligibility"][
        "may_promote_ineligible"
    ] is False,
    "Publication-ineligible evidence cannot be promoted",
)

check(
    upstream["publication_eligibility"][
        "ineligible_where_required_blocks_actionable_authority"
    ] is True,
    "Publication ineligibility can block actionable authority",
)

check(
    upstream["risk"]["recalculate"] is False,
    "Risk is not recalculated",
)

check(
    set(
        upstream["risk"]["recognized_levels"]
    )
    == {
        "LOW",
        "MODERATE",
        "HIGH",
        "VERY_HIGH",
        "CRITICAL",
    },
    "Risk levels preserve upstream vocabulary",
)

check(
    upstream["risk"]["missing_is_low"] is False,
    "Missing Risk is not LOW",
)

check(
    upstream["risk"]["missing_is_zero"] is False,
    "Missing Risk is not zero",
)

check(
    upstream["signals"]["recalculate"] is False,
    "Signals are not recalculated",
)

check(
    set(
        upstream["signals"]["recognized_statuses"]
    )
    == {
        "CALCULATED",
        "INSUFFICIENT_COVERAGE",
        "UNAVAILABLE",
    },
    "Signal statuses preserve upstream vocabulary",
)

check(
    upstream["signals"][
        "minimum_metric_coverage_is_owned_upstream"
    ] is True,
    "Signal coverage threshold remains upstream-owned",
)

check(
    upstream["signals"][
        "decision_policy_may_define_new_signal_coverage_threshold"
    ] is False,
    "Decision Policy cannot redefine signal coverage",
)


# ------------------------------------------------------------
# Threshold governance
# ------------------------------------------------------------

thresholds = policy["threshold_governance"]

check(
    thresholds["reuse_upstream_thresholds"] is True,
    "upstream thresholds are reused",
)

for key in [
    "duplicate_upstream_numeric_thresholds",
    "decision_center_may_redefine_signal_coverage_threshold",
    "decision_center_may_redefine_score_coverage_threshold",
    "decision_center_may_redefine_confidence_thresholds",
    "decision_center_may_redefine_risk_level_thresholds",
    "decision_center_may_redefine_publication_source_tiers",
]:
    check(
        thresholds[key] is False,
        f"threshold_governance.{key} is false",
    )

check(
    thresholds[
        "decision_specific_rules_must_be_explicit"
    ] is True,
    "decision-specific rules must be explicit",
)


# ------------------------------------------------------------
# Evidence authority
# ------------------------------------------------------------

evidence = policy["evidence_authority"]

for key in [
    "missing_required_evidence",
    "unavailable_required_evidence",
    "blocked_required_evidence",
    "invalid_required_provenance",
    "insufficient_required_coverage",
    "publication_ineligible_where_required",
    "unknown_required_evidence_status",
]:
    check(
        evidence[key] == "INSUFFICIENT_EVIDENCE",
        f"{key} maps to INSUFFICIENT_EVIDENCE",
    )

for key in [
    "missing_is_neutral",
    "missing_is_negative",
    "missing_is_positive",
    "missing_is_zero",
    "blocked_evidence_may_support_actionable",
    "unavailable_evidence_may_support_actionable",
    "unknown_evidence_may_support_actionable",
]:
    check(
        evidence[key] is False,
        f"evidence_authority.{key} is false",
    )


# ------------------------------------------------------------
# Conflict
# ------------------------------------------------------------

conflict = policy["conflict_policy"]

check(
    conflict[
        "decision_policy_invents_conflict_materiality"
    ] is False,
    "Decision Policy does not invent conflict materiality",
)

check(
    conflict[
        "material_conflict_must_remain_visible"
    ] is True,
    "material conflict remains visible",
)

check(
    conflict[
        "unresolved_material_conflict_state"
    ] == "THESIS_REVIEW",
    "unresolved material conflict maps to THESIS_REVIEW",
)

check(
    conflict[
        "high_score_may_hide_material_conflict"
    ] is False,
    "high Score cannot hide material conflict",
)

check(
    conflict[
        "score_label_may_resolve_material_conflict"
    ] is False,
    "Score label cannot resolve material conflict",
)

check(
    conflict[
        "conflict_may_be_silently_discarded"
    ] is False,
    "material conflict cannot be silently discarded",
)


# ------------------------------------------------------------
# Risk
# ------------------------------------------------------------

risk = policy["risk_policy"]

check(
    risk["decision_policy_invents_risk_score"]
    is False,
    "Decision Policy does not invent Risk score",
)

check(
    risk[
        "decision_policy_recalculates_risk_level"
    ] is False,
    "Decision Policy does not recalculate Risk level",
)

expected_levels = {
    "LOW",
    "MODERATE",
    "HIGH",
    "VERY_HIGH",
    "CRITICAL",
}

check(
    set(risk["level_mapping"].keys())
    == expected_levels,
    "Risk level mapping contains exact upstream levels",
)

for level in expected_levels:
    check(
        risk["level_mapping"][level]
        == "NO_AUTOMATIC_DECISION_STATE",
        f"{level} does not automatically select a decision state",
    )

check(
    risk[
        "risk_level_alone_selects_risk_review"
    ] is False,
    "Risk level alone does not select RISK_REVIEW",
)

check(
    risk[
        "material_risk_restriction_state"
    ] == "RISK_REVIEW",
    "explicit material Risk restriction maps to RISK_REVIEW",
)

check(
    risk[
        "risk_review_is_automatic_rejection"
    ] is False,
    "RISK_REVIEW is not automatic rejection",
)

check(
    risk[
        "missing_risk_may_be_assumed_safe"
    ] is False,
    "missing Risk cannot be assumed safe",
)


# ------------------------------------------------------------
# Confirmation
# ------------------------------------------------------------

confirmation = policy["confirmation_policy"]

check(
    confirmation[
        "decision_policy_invents_required_confirmation"
    ] is False,
    "Decision Policy does not invent required confirmations",
)

check(
    confirmation[
        "required_confirmation_missing_state"
    ] == "WAIT_FOR_CONFIRMATION",
    "missing required confirmation maps to WAIT_FOR_CONFIRMATION",
)

for key in [
    "score_label_may_satisfy_confirmation",
    "high_score_may_satisfy_confirmation",
    "missing_confirmation_may_be_assumed_satisfied",
]:
    check(
        confirmation[key] is False,
        f"confirmation_policy.{key} is false",
    )


# ------------------------------------------------------------
# ACTIONABLE authority
# ------------------------------------------------------------

actionable = policy["actionable_authority"]

check(
    actionable[
        "actionable_is_positive_authority"
    ] is True,
    "ACTIONABLE requires positive authority",
)

check(
    actionable[
        "actionable_is_default_state"
    ] is False,
    "ACTIONABLE is not default",
)

expected_requirements = {
    "EVIDENCE_GATE_PASSED",
    "NO_UNRESOLVED_MATERIAL_CONFLICT",
    "NO_MATERIAL_RISK_RESTRICTION",
    "NO_REQUIRED_CONFIRMATION_MISSING",
    "PUBLICATION_REQUIREMENTS_SATISFIED_WHERE_APPLICABLE",
    "ACTIONABLE_AUTHORITY_EXPLICITLY_ESTABLISHED",
}

check(
    set(actionable["requires"])
    == expected_requirements,
    "ACTIONABLE requires all mandatory gates",
)

for key in [
    "score_label_alone_establishes_actionable_authority",
    "normalized_score_alone_establishes_actionable_authority",
    "risk_level_alone_establishes_actionable_authority",
    "confidence_status_alone_establishes_actionable_authority",
    "actionable_authority_may_be_invented",
]:
    check(
        actionable[key] is False,
        f"actionable_authority.{key} is false",
    )

authority_establishment = actionable[
    "authority_establishment"
]

check(
    authority_establishment["mode"]
    == "EXPLICIT_FUTURE_RULE_REQUIRED",
    "ACTIONABLE authority requires an explicit future rule",
)

check(
    authority_establishment[
        "defined_in_this_policy"
    ] is False,
    "D.2D.2 does not invent ACTIONABLE trigger",
)

check(
    authority_establishment[
        "fallback_when_not_established"
    ] == "WATCH",
    "usable unrestricted evidence falls back to WATCH when ACTIONABLE authority is absent",
)


# ------------------------------------------------------------
# WATCH
# ------------------------------------------------------------

watch = policy["watch_policy"]

for key in [
    "watch_is_neutral",
    "watch_is_hold",
    "watch_is_buy",
    "watch_is_accumulate",
    "watch_is_default_for_missing_evidence",
]:
    check(
        watch[key] is False,
        f"watch_policy.{key} is false",
    )

for key in [
    "requires_usable_evidence",
    "requires_no_higher_priority_restriction",
    "requires_actionable_authority_not_established",
]:
    check(
        watch[key] is True,
        f"watch_policy.{key} is true",
    )


# ------------------------------------------------------------
# State selection
# ------------------------------------------------------------

selection = policy["state_selection"]

expected_order = [
    "INSUFFICIENT_EVIDENCE",
    "THESIS_REVIEW",
    "RISK_REVIEW",
    "WAIT_FOR_CONFIRMATION",
    "WATCH",
    "ACTIONABLE",
]

check(
    selection["mode"]
    == "FAIL_CLOSED_FIRST_MATCH",
    "state selection remains fail-closed first-match",
)

check(
    selection["evaluation_order"]
    == expected_order,
    "state precedence matches D.2B",
)

check(
    [
        rule["state"]
        for rule in selection["rules"]
    ] == expected_order,
    "state rule order matches precedence",
)

check(
    [
        rule["priority"]
        for rule in selection["rules"]
    ] == [1, 2, 3, 4, 5, 6],
    "state priorities are canonical",
)

check(
    selection[
        "unknown_condition_behavior"
    ] == "INSUFFICIENT_EVIDENCE",
    "unknown conditions fail closed",
)


# ------------------------------------------------------------
# Score label non-mapping
# ------------------------------------------------------------

non_mapping = policy[
    "score_label_non_mapping"
]

expected_labels = {
    "STRONG_BUY",
    "BUY",
    "WATCH_ACCUMULATE",
    "HOLD",
    "CAUTION",
    "AVOID",
}

check(
    set(non_mapping.keys())
    == expected_labels,
    "all Score labels are explicitly covered",
)

for label in expected_labels:
    check(
        non_mapping[label]
        == "NO_DIRECT_DECISION_STATE",
        f"{label} has no direct Decision State mapping",
    )


# ------------------------------------------------------------
# Information classes
# ------------------------------------------------------------

classes = policy["information_classes"]

check(
    classes["upstream_observation"]
    == "FACT",
    "upstream observations are FACT",
)

check(
    classes["score"] == "MODEL",
    "Score is MODEL",
)

check(
    classes["risk"] == "MODEL",
    "Risk is MODEL",
)

check(
    classes["signal"] == "MODEL",
    "Signal is MODEL",
)

check(
    classes["conflict_resolution"]
    == "INFERENCE",
    "Conflict resolution is INFERENCE",
)

check(
    classes["confirmation_assessment"]
    == "INFERENCE",
    "Confirmation assessment is INFERENCE",
)

check(
    classes["decision_state"]
    == "DECISION",
    "Decision State is DECISION",
)

check(
    classes[
        "inference_may_be_presented_as_fact"
    ] is False,
    "INFERENCE cannot be presented as FACT",
)

check(
    classes[
        "decision_may_be_presented_as_fact"
    ] is False,
    "DECISION cannot be presented as FACT",
)


# ------------------------------------------------------------
# Phase boundaries
# ------------------------------------------------------------

boundaries = policy["phase_boundaries"]

for key in [
    "implements_evidence_gate_engine",
    "implements_conflict_resolver",
    "implements_decision_state_engine",
    "writes_decision_center",
    "modifies_generator",
]:
    check(
        boundaries[key] is False,
        f"phase_boundaries.{key} is false",
    )

check(
    boundaries[
        "evidence_gate_implementation_phase"
    ] == "D.3",
    "Evidence Gate remains D.3",
)

check(
    boundaries[
        "conflict_resolver_implementation_phase"
    ] == "D.4",
    "Conflict Resolver remains D.4",
)

check(
    boundaries[
        "decision_state_engine_phase"
    ] == "D.5",
    "Decision State Engine remains D.5",
)

check(
    boundaries[
        "generator_integration_phase"
    ] == "D.7",
    "Generator integration remains D.7",
)


# ------------------------------------------------------------
# Mandatory prohibitions
# ------------------------------------------------------------

prohibited = set(
    policy["prohibited_behaviors"]
)

mandatory = {
    "MODIFY_V2_1",
    "MODIFY_SCHEMA_V3_IN_D2D2",
    "RECALCULATE_SCORE",
    "RECALCULATE_RISK",
    "RECALCULATE_CONFIDENCE",
    "RECALCULATE_PUBLICATION_ELIGIBILITY",
    "RECALCULATE_DOMAIN_SIGNALS",
    "DUPLICATE_UPSTREAM_NUMERIC_THRESHOLDS",
    "TRANSLATE_SCORE_LABEL_DIRECTLY_TO_DECISION_STATE",
    "TREAT_STRONG_BUY_AS_AUTOMATIC_ACTIONABLE",
    "TREAT_BUY_AS_AUTOMATIC_ACTIONABLE",
    "TREAT_HOLD_AS_AUTOMATIC_WATCH",
    "TREAT_CAUTION_AS_AUTOMATIC_RISK_REVIEW",
    "TREAT_AVOID_AS_AUTOMATIC_THESIS_REVIEW",
    "TREAT_MISSING_AS_NEUTRAL",
    "TREAT_MISSING_AS_WATCH",
    "TREAT_MISSING_RISK_AS_LOW_RISK",
    "TREAT_MISSING_RISK_AS_ZERO_RISK",
    "OVERRIDE_PUBLICATION_ELIGIBILITY",
    "PROMOTE_PUBLICATION_INELIGIBLE_EVIDENCE",
    "RESTORE_REMOVED_SCORE_LABEL",
    "IGNORE_MATERIAL_RISK",
    "HIDE_MATERIAL_CONFLICT_WITH_HIGH_SCORE",
    "INVENT_REQUIRED_CONFIRMATION",
    "INVENT_ACTIONABLE_AUTHORITY",
    "CREATE_ACTIONABLE_WITHOUT_EVIDENCE_GATE",
    "CREATE_ACTIONABLE_FROM_BLOCKED_EVIDENCE",
    "CREATE_ACTIONABLE_FROM_UNAVAILABLE_EVIDENCE",
    "WRITE_DECISION_CENTER_IN_D2D2",
}

check(
    mandatory.issubset(prohibited),
    "all mandatory prohibited behaviors are present",
)


# ------------------------------------------------------------
# Final
# ------------------------------------------------------------

print("")
print("=" * 60)
print(" D.2D.2 - DECISION POLICY CONTRACT TEST")
print("=" * 60)
print(f"Checks executed: {checks}")
print(f"Failures: {len(failures)}")

if failures:
    print("RESULT: REJECTED")

    for failure in failures:
        print(f" - {failure}")

    raise SystemExit(1)

print("RESULT: APPROVED")
