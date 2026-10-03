import copy
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONTRACT_PATH = BASE_DIR / "decision_state_contract_v3.json"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_contract():
    require(
        CONTRACT_PATH.exists(),
        "decision_state_contract_v3.json is missing.",
    )

    with CONTRACT_PATH.open(
        "r",
        encoding="utf-8-sig",
    ) as handle:
        return json.load(handle)


def validate_safety(contract):
    errors = []

    compatibility = contract.get(
        "compatibility",
        {},
    )

    states = contract.get(
        "states",
        {},
    )

    precedence = contract.get(
        "precedence",
        {},
    )

    score = contract.get(
        "score_semantics",
        {},
    )

    risk = contract.get(
        "risk_semantics",
        {},
    )

    confidence = contract.get(
        "confidence_semantics",
        {},
    )

    publication = contract.get(
        "publication_semantics",
        {},
    )

    missing = contract.get(
        "missing_data_semantics",
        {},
    )

    conflicts = contract.get(
        "conflict_semantics",
        {},
    )

    authority = contract.get(
        "authority_rules",
        {},
    )

    classes = contract.get(
        "information_class_rules",
        {},
    )

    prohibited = set(
        contract.get(
            "prohibited_behaviors",
            [],
        )
    )

    future = contract.get(
        "future_policy_boundary",
        {},
    )

    expected_states = {
        "ACTIONABLE",
        "WATCH",
        "WAIT_FOR_CONFIRMATION",
        "RISK_REVIEW",
        "THESIS_REVIEW",
        "INSUFFICIENT_EVIDENCE",
    }

    expected_order = [
        "INSUFFICIENT_EVIDENCE",
        "THESIS_REVIEW",
        "RISK_REVIEW",
        "WAIT_FOR_CONFIRMATION",
        "WATCH",
        "ACTIONABLE",
    ]

    expected_ranks = {
        "ACTIONABLE": 60,
        "WATCH": 50,
        "WAIT_FOR_CONFIRMATION": 40,
        "RISK_REVIEW": 30,
        "THESIS_REVIEW": 20,
        "INSUFFICIENT_EVIDENCE": 10,
    }

    required_insufficient_causes = {
        "MISSING_REQUIRED_EVIDENCE",
        "UNAVAILABLE_REQUIRED_EVIDENCE",
        "BLOCKED_REQUIRED_EVIDENCE",
        "INVALID_REQUIRED_PROVENANCE",
        "INSUFFICIENT_REQUIRED_COVERAGE",
        "PUBLICATION_INELIGIBLE_WHERE_REQUIRED",
        "UNKNOWN_REQUIRED_EVIDENCE_STATUS",
    }

    mandatory_prohibitions = {
        "TRANSLATE_SCORE_LABEL_DIRECTLY_TO_DECISION_STATE",
        "TREAT_STRONG_BUY_AS_AUTOMATIC_ACTIONABLE",
        "TREAT_BUY_AS_AUTOMATIC_ACTIONABLE",
        "TREAT_MISSING_AS_WATCH",
        "TREAT_MISSING_AS_HOLD",
        "TREAT_MISSING_RISK_AS_LOW_RISK",
        "TREAT_MISSING_RISK_AS_ZERO_RISK",
        "IGNORE_MATERIAL_RISK",
        "OVERRIDE_RISK",
        "OVERRIDE_CONFIDENCE",
        "OVERRIDE_PUBLICATION_ELIGIBILITY",
        "RESTORE_BLOCKED_SCORE_LABEL",
        "DISCARD_MATERIAL_CONFLICT",
        "HIDE_CONFLICT_BECAUSE_SCORE_IS_HIGH",
        "CREATE_ACTIONABLE_STATE_FROM_BLOCKED_EVIDENCE",
        "CREATE_ACTIONABLE_STATE_FROM_UNAVAILABLE_EVIDENCE",
        "CREATE_ACTIONABLE_STATE_WITHOUT_EVIDENCE_GATE",
        "MODIFY_UPSTREAM_ANALYTICAL_OUTPUTS",
        "MODIFY_V2_1",
    }

    if compatibility.get(
        "preserve_v2_1"
    ) is not True:
        errors.append(
            "V2_1_NOT_PRESERVED"
        )

    if compatibility.get(
        "may_modify_v2_1"
    ) is not False:
        errors.append(
            "V2_1_MODIFICATION_ALLOWED"
        )

    if compatibility.get(
        "schema_change_required_by_this_contract"
    ) is not False:
        errors.append(
            "SCHEMA_CHANGE_INTRODUCED"
        )

    if compatibility.get(
        "public_output_change_required_by_this_contract"
    ) is not False:
        errors.append(
            "PUBLIC_OUTPUT_CHANGE_INTRODUCED"
        )

    if set(states.keys()) != expected_states:
        errors.append(
            "DECISION_STATE_SET_CHANGED"
        )

    for state, expected_rank in expected_ranks.items():
        state_contract = states.get(
            state,
            {},
        )

        if state_contract.get(
            "authority_rank"
        ) != expected_rank:
            errors.append(
                f"AUTHORITY_RANK_CHANGED:{state}"
            )

        if state_contract.get(
            "terminal_for_evaluation"
        ) is not True:
            errors.append(
                f"STATE_NOT_TERMINAL:{state}"
            )

    insufficient = states.get(
        "INSUFFICIENT_EVIDENCE",
        {},
    )

    if set(
        insufficient.get(
            "requires_any",
            [],
        )
    ) != required_insufficient_causes:
        errors.append(
            "INSUFFICIENT_CAUSES_CHANGED"
        )

    if precedence.get(
        "mode"
    ) != "FAIL_CLOSED_FIRST_MATCH":
        errors.append(
            "FAIL_CLOSED_PRECEDENCE_DISABLED"
        )

    if precedence.get(
        "evaluation_order"
    ) != expected_order:
        errors.append(
            "PRECEDENCE_CHANGED"
        )

    rules = precedence.get(
        "rules",
        [],
    )

    if not isinstance(
        rules,
        list,
    ) or len(rules) != 6:
        errors.append(
            "PRECEDENCE_RULE_COUNT_CHANGED"
        )
    else:
        rule_states = [
            item.get("state")
            for item in rules
            if isinstance(item, dict)
        ]

        priorities = [
            item.get("priority")
            for item in rules
            if isinstance(item, dict)
        ]

        if rule_states != expected_order:
            errors.append(
                "PRECEDENCE_RULE_ORDER_CHANGED"
            )

        if priorities != [
            1,
            2,
            3,
            4,
            5,
            6,
        ]:
            errors.append(
                "PRECEDENCE_PRIORITY_CHANGED"
            )

    score_false_rules = {
        "radar_score_is_decision":
            "RADAR_SCORE_BECAME_DECISION",

        "score_label_is_decision":
            "SCORE_LABEL_BECAME_DECISION",

        "strong_buy_implies_actionable":
            "STRONG_BUY_BECAME_ACTIONABLE",

        "buy_implies_actionable":
            "BUY_BECAME_ACTIONABLE",

        "watch_accumulate_implies_watch":
            "WATCH_ACCUMULATE_BECAME_WATCH",

        "hold_implies_watch":
            "HOLD_BECAME_WATCH",

        "caution_implies_risk_review":
            "CAUTION_BECAME_RISK_REVIEW",

        "avoid_implies_thesis_review":
            "AVOID_BECAME_THESIS_REVIEW",
    }

    for key, error in score_false_rules.items():
        if score.get(key) is not False:
            errors.append(error)

    if score.get(
        "score_may_be_used_as_evidence"
    ) is not True:
        errors.append(
            "SCORE_EVIDENCE_DISABLED"
        )

    if score.get(
        "score_must_remain_upstream_owned"
    ) is not True:
        errors.append(
            "SCORE_UPSTREAM_OWNERSHIP_DISABLED"
        )

    if risk.get(
        "risk_may_be_ignored"
    ) is not False:
        errors.append(
            "RISK_IGNORE_ALLOWED"
        )

    if risk.get(
        "risk_may_be_overridden"
    ) is not False:
        errors.append(
            "RISK_OVERRIDE_ALLOWED"
        )

    if risk.get(
        "missing_risk_is_low_risk"
    ) is not False:
        errors.append(
            "MISSING_RISK_BECAME_LOW"
        )

    if risk.get(
        "missing_risk_is_zero_risk"
    ) is not False:
        errors.append(
            "MISSING_RISK_BECAME_ZERO"
        )

    if risk.get(
        "material_risk_may_restrict_decision"
    ) is not True:
        errors.append(
            "RISK_RESTRICTION_DISABLED"
        )

    if risk.get(
        "risk_review_is_automatic_rejection"
    ) is not False:
        errors.append(
            "RISK_REVIEW_BECAME_REJECTION"
        )

    if confidence.get(
        "confidence_may_be_overridden"
    ) is not False:
        errors.append(
            "CONFIDENCE_OVERRIDE_ALLOWED"
        )

    if confidence.get(
        "unavailable_confidence_is_usable"
    ) is not False:
        errors.append(
            "UNAVAILABLE_CONFIDENCE_USABLE"
        )

    if confidence.get(
        "low_confidence_may_be_silently_promoted"
    ) is not False:
        errors.append(
            "LOW_CONFIDENCE_PROMOTION_ALLOWED"
        )

    if confidence.get(
        "missing_confidence_is_neutral"
    ) is not False:
        errors.append(
            "MISSING_CONFIDENCE_BECAME_NEUTRAL"
        )

    if publication.get(
        "publication_eligibility_may_be_overridden"
    ) is not False:
        errors.append(
            "PUBLICATION_OVERRIDE_ALLOWED"
        )

    if publication.get(
        "publication_ineligible_may_be_promoted"
    ) is not False:
        errors.append(
            "PUBLICATION_PROMOTION_ALLOWED"
        )

    if publication.get(
        "publication_gate_can_restrict_actionable_authority"
    ) is not True:
        errors.append(
            "PUBLICATION_RESTRICTION_DISABLED"
        )

    if publication.get(
        "decision_center_may_restore_removed_score_label"
    ) is not False:
        errors.append(
            "SCORE_LABEL_RESTORE_ALLOWED"
        )

    missing_false_rules = {
        "missing_is_neutral":
            "MISSING_BECAME_NEUTRAL",

        "missing_is_negative":
            "MISSING_BECAME_NEGATIVE",

        "missing_is_positive":
            "MISSING_BECAME_POSITIVE",

        "missing_is_zero":
            "MISSING_BECAME_ZERO",

        "missing_may_create_actionable_authority":
            "MISSING_BECAME_ACTIONABLE",
    }

    for key, error in missing_false_rules.items():
        if missing.get(key) is not False:
            errors.append(error)

    if missing.get(
        "default_behavior"
    ) != "RESTRICT_DECISION_AUTHORITY":
        errors.append(
            "MISSING_DEFAULT_BEHAVIOR_CHANGED"
        )

    if conflicts.get(
        "material_conflicts_must_be_preserved"
    ) is not True:
        errors.append(
            "CONFLICT_PRESERVATION_DISABLED"
        )

    if conflicts.get(
        "conflicts_may_be_silently_discarded"
    ) is not False:
        errors.append(
            "CONFLICT_DISCARD_ALLOWED"
        )

    if conflicts.get(
        "conflicts_may_be_hidden_by_high_score"
    ) is not False:
        errors.append(
            "HIGH_SCORE_MAY_HIDE_CONFLICT"
        )

    if conflicts.get(
        "unresolved_material_conflict_state"
    ) != "THESIS_REVIEW":
        errors.append(
            "CONFLICT_STATE_CHANGED"
        )

    if authority.get(
        "actionable_is_highest_decision_authority"
    ) is not True:
        errors.append(
            "ACTIONABLE_AUTHORITY_DISABLED"
        )

    if authority.get(
        "actionable_requires_all_gates_passed"
    ) is not True:
        errors.append(
            "ACTIONABLE_WITHOUT_ALL_GATES"
        )

    if authority.get(
        "actionable_may_be_inferred_from_score_label_alone"
    ) is not False:
        errors.append(
            "ACTIONABLE_FROM_SCORE_LABEL_ALLOWED"
        )

    if authority.get(
        "restrictive_states_take_precedence_over_actionable"
    ) is not True:
        errors.append(
            "RESTRICTIVE_PRECEDENCE_DISABLED"
        )

    if authority.get(
        "unknown_condition_behavior"
    ) != "FAIL_CLOSED":
        errors.append(
            "UNKNOWN_CONDITION_FAIL_OPEN"
        )

    if classes.get(
        "allowed_classes"
    ) != [
        "FACT",
        "MODEL",
        "INFERENCE",
        "DECISION",
    ]:
        errors.append(
            "INFORMATION_CLASSES_CHANGED"
        )

    if classes.get(
        "decision_state_class"
    ) != "DECISION":
        errors.append(
            "DECISION_STATE_CLASS_CHANGED"
        )

    if classes.get(
        "decision_must_not_be_presented_as_fact"
    ) is not True:
        errors.append(
            "DECISION_MAY_BE_PRESENTED_AS_FACT"
        )

    if classes.get(
        "inference_must_not_be_presented_as_fact"
    ) is not True:
        errors.append(
            "INFERENCE_MAY_BE_PRESENTED_AS_FACT"
        )

    if not mandatory_prohibitions.issubset(
        prohibited
    ):
        errors.append(
            "MANDATORY_PROHIBITION_REMOVED"
        )

    if future.get(
        "numeric_thresholds_defined_here"
    ) is not False:
        errors.append(
            "NUMERIC_THRESHOLD_LEAKED_INTO_D2B"
        )

    if future.get(
        "component_thresholds_defined_here"
    ) is not False:
        errors.append(
            "COMPONENT_THRESHOLD_LEAKED_INTO_D2B"
        )

    if future.get(
        "portfolio_actions_defined_here"
    ) is not False:
        errors.append(
            "PORTFOLIO_ACTION_LEAKED_INTO_D2B"
        )

    if future.get(
        "trade_execution_defined_here"
    ) is not False:
        errors.append(
            "TRADE_EXECUTION_LEAKED_INTO_D2B"
        )

    if future.get(
        "thresholds_require_separate_decision_policy"
    ) is not True:
        errors.append(
            "SEPARATE_POLICY_REQUIREMENT_DISABLED"
        )

    return errors


def mutate(base, mutation):
    candidate = copy.deepcopy(base)
    mutation(candidate)
    return candidate


def remove_prohibition(contract, value):
    behaviors = contract.get(
        "prohibited_behaviors",
        [],
    )

    if value in behaviors:
        behaviors.remove(value)


def main():
    base = load_contract()

    baseline_errors = validate_safety(
        base
    )

    require(
        not baseline_errors,
        "Baseline Decision State contract is unsafe: "
        + repr(baseline_errors),
    )

    cases = [
        (
            "allow_v2_1_modification",
            lambda c: c[
                "compatibility"
            ].update(
                {
                    "may_modify_v2_1":
                        True
                }
            ),
            "V2_1_MODIFICATION_ALLOWED",
        ),

        (
            "require_schema_change",
            lambda c: c[
                "compatibility"
            ].update(
                {
                    "schema_change_required_by_this_contract":
                        True
                }
            ),
            "SCHEMA_CHANGE_INTRODUCED",
        ),

        (
            "remove_actionable_state",
            lambda c: c[
                "states"
            ].pop(
                "ACTIONABLE"
            ),
            "DECISION_STATE_SET_CHANGED",
        ),

        (
            "change_actionable_rank",
            lambda c: c[
                "states"
            ][
                "ACTIONABLE"
            ].update(
                {
                    "authority_rank":
                        5
                }
            ),
            "AUTHORITY_RANK_CHANGED:ACTIONABLE",
        ),

        (
            "remove_insufficient_missing_cause",
            lambda c: c[
                "states"
            ][
                "INSUFFICIENT_EVIDENCE"
            ][
                "requires_any"
            ].remove(
                "MISSING_REQUIRED_EVIDENCE"
            ),
            "INSUFFICIENT_CAUSES_CHANGED",
        ),

        (
            "disable_fail_closed_precedence",
            lambda c: c[
                "precedence"
            ].update(
                {
                    "mode":
                        "BEST_MATCH"
                }
            ),
            "FAIL_CLOSED_PRECEDENCE_DISABLED",
        ),

        (
            "put_actionable_first",
            lambda c: c[
                "precedence"
            ].update(
                {
                    "evaluation_order":
                        [
                            "ACTIONABLE",
                            "INSUFFICIENT_EVIDENCE",
                            "THESIS_REVIEW",
                            "RISK_REVIEW",
                            "WAIT_FOR_CONFIRMATION",
                            "WATCH",
                        ]
                }
            ),
            "PRECEDENCE_CHANGED",
        ),

        (
            "score_becomes_decision",
            lambda c: c[
                "score_semantics"
            ].update(
                {
                    "radar_score_is_decision":
                        True
                }
            ),
            "RADAR_SCORE_BECAME_DECISION",
        ),

        (
            "score_label_becomes_decision",
            lambda c: c[
                "score_semantics"
            ].update(
                {
                    "score_label_is_decision":
                        True
                }
            ),
            "SCORE_LABEL_BECAME_DECISION",
        ),

        (
            "strong_buy_becomes_actionable",
            lambda c: c[
                "score_semantics"
            ].update(
                {
                    "strong_buy_implies_actionable":
                        True
                }
            ),
            "STRONG_BUY_BECAME_ACTIONABLE",
        ),

        (
            "buy_becomes_actionable",
            lambda c: c[
                "score_semantics"
            ].update(
                {
                    "buy_implies_actionable":
                        True
                }
            ),
            "BUY_BECAME_ACTIONABLE",
        ),

        (
            "hold_becomes_watch",
            lambda c: c[
                "score_semantics"
            ].update(
                {
                    "hold_implies_watch":
                        True
                }
            ),
            "HOLD_BECAME_WATCH",
        ),

        (
            "risk_may_be_ignored",
            lambda c: c[
                "risk_semantics"
            ].update(
                {
                    "risk_may_be_ignored":
                        True
                }
            ),
            "RISK_IGNORE_ALLOWED",
        ),

        (
            "risk_override_allowed",
            lambda c: c[
                "risk_semantics"
            ].update(
                {
                    "risk_may_be_overridden":
                        True
                }
            ),
            "RISK_OVERRIDE_ALLOWED",
        ),

        (
            "missing_risk_becomes_low",
            lambda c: c[
                "risk_semantics"
            ].update(
                {
                    "missing_risk_is_low_risk":
                        True
                }
            ),
            "MISSING_RISK_BECAME_LOW",
        ),

        (
            "missing_risk_becomes_zero",
            lambda c: c[
                "risk_semantics"
            ].update(
                {
                    "missing_risk_is_zero_risk":
                        True
                }
            ),
            "MISSING_RISK_BECAME_ZERO",
        ),

        (
            "disable_risk_restriction",
            lambda c: c[
                "risk_semantics"
            ].update(
                {
                    "material_risk_may_restrict_decision":
                        False
                }
            ),
            "RISK_RESTRICTION_DISABLED",
        ),

        (
            "confidence_override_allowed",
            lambda c: c[
                "confidence_semantics"
            ].update(
                {
                    "confidence_may_be_overridden":
                        True
                }
            ),
            "CONFIDENCE_OVERRIDE_ALLOWED",
        ),

        (
            "unavailable_confidence_usable",
            lambda c: c[
                "confidence_semantics"
            ].update(
                {
                    "unavailable_confidence_is_usable":
                        True
                }
            ),
            "UNAVAILABLE_CONFIDENCE_USABLE",
        ),

        (
            "low_confidence_promoted",
            lambda c: c[
                "confidence_semantics"
            ].update(
                {
                    "low_confidence_may_be_silently_promoted":
                        True
                }
            ),
            "LOW_CONFIDENCE_PROMOTION_ALLOWED",
        ),

        (
            "publication_override_allowed",
            lambda c: c[
                "publication_semantics"
            ].update(
                {
                    "publication_eligibility_may_be_overridden":
                        True
                }
            ),
            "PUBLICATION_OVERRIDE_ALLOWED",
        ),

        (
            "publication_ineligible_promoted",
            lambda c: c[
                "publication_semantics"
            ].update(
                {
                    "publication_ineligible_may_be_promoted":
                        True
                }
            ),
            "PUBLICATION_PROMOTION_ALLOWED",
        ),

        (
            "restore_removed_score_label",
            lambda c: c[
                "publication_semantics"
            ].update(
                {
                    "decision_center_may_restore_removed_score_label":
                        True
                }
            ),
            "SCORE_LABEL_RESTORE_ALLOWED",
        ),

        (
            "missing_becomes_neutral",
            lambda c: c[
                "missing_data_semantics"
            ].update(
                {
                    "missing_is_neutral":
                        True
                }
            ),
            "MISSING_BECAME_NEUTRAL",
        ),

        (
            "missing_becomes_positive",
            lambda c: c[
                "missing_data_semantics"
            ].update(
                {
                    "missing_is_positive":
                        True
                }
            ),
            "MISSING_BECAME_POSITIVE",
        ),

        (
            "missing_creates_actionable",
            lambda c: c[
                "missing_data_semantics"
            ].update(
                {
                    "missing_may_create_actionable_authority":
                        True
                }
            ),
            "MISSING_BECAME_ACTIONABLE",
        ),

        (
            "discard_material_conflicts",
            lambda c: c[
                "conflict_semantics"
            ].update(
                {
                    "material_conflicts_must_be_preserved":
                        False
                }
            ),
            "CONFLICT_PRESERVATION_DISABLED",
        ),

        (
            "hide_conflict_with_high_score",
            lambda c: c[
                "conflict_semantics"
            ].update(
                {
                    "conflicts_may_be_hidden_by_high_score":
                        True
                }
            ),
            "HIGH_SCORE_MAY_HIDE_CONFLICT",
        ),

        (
            "change_conflict_state",
            lambda c: c[
                "conflict_semantics"
            ].update(
                {
                    "unresolved_material_conflict_state":
                        "WATCH"
                }
            ),
            "CONFLICT_STATE_CHANGED",
        ),

        (
            "actionable_without_all_gates",
            lambda c: c[
                "authority_rules"
            ].update(
                {
                    "actionable_requires_all_gates_passed":
                        False
                }
            ),
            "ACTIONABLE_WITHOUT_ALL_GATES",
        ),

        (
            "actionable_from_score_label",
            lambda c: c[
                "authority_rules"
            ].update(
                {
                    "actionable_may_be_inferred_from_score_label_alone":
                        True
                }
            ),
            "ACTIONABLE_FROM_SCORE_LABEL_ALLOWED",
        ),

        (
            "disable_restrictive_precedence",
            lambda c: c[
                "authority_rules"
            ].update(
                {
                    "restrictive_states_take_precedence_over_actionable":
                        False
                }
            ),
            "RESTRICTIVE_PRECEDENCE_DISABLED",
        ),

        (
            "unknown_condition_fail_open",
            lambda c: c[
                "authority_rules"
            ].update(
                {
                    "unknown_condition_behavior":
                        "ALLOW"
                }
            ),
            "UNKNOWN_CONDITION_FAIL_OPEN",
        ),

        (
            "decision_presented_as_fact",
            lambda c: c[
                "information_class_rules"
            ].update(
                {
                    "decision_must_not_be_presented_as_fact":
                        False
                }
            ),
            "DECISION_MAY_BE_PRESENTED_AS_FACT",
        ),

        (
            "remove_modify_v2_1_prohibition",
            lambda c: remove_prohibition(
                c,
                "MODIFY_V2_1",
            ),
            "MANDATORY_PROHIBITION_REMOVED",
        ),

        (
            "remove_blocked_evidence_prohibition",
            lambda c: remove_prohibition(
                c,
                "CREATE_ACTIONABLE_STATE_FROM_BLOCKED_EVIDENCE",
            ),
            "MANDATORY_PROHIBITION_REMOVED",
        ),

        (
            "leak_numeric_thresholds",
            lambda c: c[
                "future_policy_boundary"
            ].update(
                {
                    "numeric_thresholds_defined_here":
                        True
                }
            ),
            "NUMERIC_THRESHOLD_LEAKED_INTO_D2B",
        ),

        (
            "leak_trade_execution",
            lambda c: c[
                "future_policy_boundary"
            ].update(
                {
                    "trade_execution_defined_here":
                        True
                }
            ),
            "TRADE_EXECUTION_LEAKED_INTO_D2B",
        ),

        (
            "disable_separate_policy_requirement",
            lambda c: c[
                "future_policy_boundary"
            ].update(
                {
                    "thresholds_require_separate_decision_policy":
                        False
                }
            ),
            "SEPARATE_POLICY_REQUIREMENT_DISABLED",
        ),
    ]

    passed = 0
    failed = []

    for (
        name,
        mutation,
        expected_error,
    ) in cases:

        candidate = mutate(
            base,
            mutation,
        )

        errors = validate_safety(
            candidate
        )

        if expected_error in errors:
            print(
                f"[PASS] {name} -> "
                f"{expected_error}"
            )
            passed += 1

        else:
            print(
                f"[FAIL] {name} -> "
                f"expected {expected_error}; "
                f"got {errors}"
            )
            failed.append(
                name
            )

    print("")
    print("=" * 60)
    print(
        " D.2C - ADVERSARIAL DECISION STATE CONTRACT TEST"
    )
    print("=" * 60)
    print(
        f"Cases executed: {len(cases)}"
    )
    print(
        f"Passed: {passed}"
    )
    print(
        f"Failed: {len(failed)}"
    )

    if failed:
        print(
            "RESULT: REJECTED"
        )

        raise AssertionError(
            "Adversarial mutations not detected: "
            + ", ".join(failed)
        )

    print(
        "RESULT: APPROVED"
    )


if __name__ == "__main__":
    main()
