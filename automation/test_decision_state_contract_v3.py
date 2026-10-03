import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONTRACT_PATH = BASE_DIR / "decision_state_contract_v3.json"


checks = 0
failures = []


def check(condition, message):
    global checks
    checks += 1
    if not condition:
        failures.append(message)


def require(mapping, key, expected=None):
    check(
        isinstance(mapping, dict),
        f"Expected dict while checking key: {key}",
    )

    if not isinstance(mapping, dict):
        return None

    check(
        key in mapping,
        f"Missing required key: {key}",
    )

    value = mapping.get(key)

    if expected is not None:
        check(
            value == expected,
            f"{key}: expected {expected!r}, got {value!r}",
        )

    return value


def main():
    check(
        CONTRACT_PATH.exists(),
        "decision_state_contract_v3.json is missing",
    )

    if not CONTRACT_PATH.exists():
        finish()

    with CONTRACT_PATH.open(
        "r",
        encoding="utf-8-sig",
    ) as handle:
        contract = json.load(handle)

    check(
        contract.get("contract_id")
        == "RADAR_V3_DECISION_STATE_CONTRACT",
        "Invalid contract_id",
    )

    check(
        contract.get("version") == "3.4D.2B",
        "Invalid contract version",
    )

    check(
        contract.get("scope")
        == "RADAR_INSTITUCIONAL_V3_ONLY",
        "Invalid contract scope",
    )

    compatibility = require(
        contract,
        "compatibility",
    )

    require(
        compatibility,
        "preserve_v2_1",
        True,
    )

    require(
        compatibility,
        "may_modify_v2_1",
        False,
    )

    require(
        compatibility,
        "preserve_existing_v3_decision_center_root",
        True,
    )

    require(
        compatibility,
        "schema_change_required_by_this_contract",
        False,
    )

    require(
        compatibility,
        "public_output_change_required_by_this_contract",
        False,
    )

    states = require(
        contract,
        "states",
    )

    expected_states = {
        "ACTIONABLE",
        "WATCH",
        "WAIT_FOR_CONFIRMATION",
        "RISK_REVIEW",
        "THESIS_REVIEW",
        "INSUFFICIENT_EVIDENCE",
    }

    check(
        set(states.keys()) == expected_states,
        "Decision state set changed",
    )

    expected_ranks = {
        "ACTIONABLE": 60,
        "WATCH": 50,
        "WAIT_FOR_CONFIRMATION": 40,
        "RISK_REVIEW": 30,
        "THESIS_REVIEW": 20,
        "INSUFFICIENT_EVIDENCE": 10,
    }

    for state, rank in expected_ranks.items():
        state_contract = states.get(state)

        check(
            isinstance(state_contract, dict),
            f"{state} contract must be a dict",
        )

        if not isinstance(state_contract, dict):
            continue

        check(
            state_contract.get("authority_rank") == rank,
            f"{state} authority_rank changed",
        )

        check(
            state_contract.get("terminal_for_evaluation")
            is True,
            f"{state} must be terminal_for_evaluation",
        )

        check(
            isinstance(
                state_contract.get("meaning"),
                str,
            )
            and bool(
                state_contract.get("meaning")
            ),
            f"{state} must define meaning",
        )

    insufficient = states.get(
        "INSUFFICIENT_EVIDENCE",
        {},
    )

    required_insufficient_causes = {
        "MISSING_REQUIRED_EVIDENCE",
        "UNAVAILABLE_REQUIRED_EVIDENCE",
        "BLOCKED_REQUIRED_EVIDENCE",
        "INVALID_REQUIRED_PROVENANCE",
        "INSUFFICIENT_REQUIRED_COVERAGE",
        "PUBLICATION_INELIGIBLE_WHERE_REQUIRED",
        "UNKNOWN_REQUIRED_EVIDENCE_STATUS",
    }

    check(
        set(
            insufficient.get(
                "requires_any",
                [],
            )
        )
        == required_insufficient_causes,
        "INSUFFICIENT_EVIDENCE causes changed",
    )

    precedence = require(
        contract,
        "precedence",
    )

    require(
        precedence,
        "mode",
        "FAIL_CLOSED_FIRST_MATCH",
    )

    expected_order = [
        "INSUFFICIENT_EVIDENCE",
        "THESIS_REVIEW",
        "RISK_REVIEW",
        "WAIT_FOR_CONFIRMATION",
        "WATCH",
        "ACTIONABLE",
    ]

    check(
        precedence.get("evaluation_order")
        == expected_order,
        "Decision precedence changed",
    )

    rules = precedence.get("rules")

    check(
        isinstance(rules, list)
        and len(rules) == 6,
        "Precedence must contain exactly 6 rules",
    )

    if isinstance(rules, list):
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

        check(
            rule_states == expected_order,
            "Precedence rule state order changed",
        )

        check(
            priorities == [1, 2, 3, 4, 5, 6],
            "Precedence priorities changed",
        )

    score = require(
        contract,
        "score_semantics",
    )

    score_false_rules = [
        "radar_score_is_decision",
        "score_label_is_decision",
        "strong_buy_implies_actionable",
        "buy_implies_actionable",
        "watch_accumulate_implies_watch",
        "hold_implies_watch",
        "caution_implies_risk_review",
        "avoid_implies_thesis_review",
    ]

    for key in score_false_rules:
        require(
            score,
            key,
            False,
        )

    require(
        score,
        "score_may_be_used_as_evidence",
        True,
    )

    require(
        score,
        "score_must_remain_upstream_owned",
        True,
    )

    risk = require(
        contract,
        "risk_semantics",
    )

    require(
        risk,
        "risk_may_be_ignored",
        False,
    )

    require(
        risk,
        "risk_may_be_overridden",
        False,
    )

    require(
        risk,
        "missing_risk_is_low_risk",
        False,
    )

    require(
        risk,
        "missing_risk_is_zero_risk",
        False,
    )

    require(
        risk,
        "material_risk_may_restrict_decision",
        True,
    )

    require(
        risk,
        "risk_review_is_automatic_rejection",
        False,
    )

    confidence = require(
        contract,
        "confidence_semantics",
    )

    require(
        confidence,
        "confidence_may_be_overridden",
        False,
    )

    require(
        confidence,
        "unavailable_confidence_is_usable",
        False,
    )

    require(
        confidence,
        "low_confidence_may_be_silently_promoted",
        False,
    )

    require(
        confidence,
        "missing_confidence_is_neutral",
        False,
    )

    publication = require(
        contract,
        "publication_semantics",
    )

    require(
        publication,
        "publication_eligibility_may_be_overridden",
        False,
    )

    require(
        publication,
        "publication_ineligible_may_be_promoted",
        False,
    )

    require(
        publication,
        "publication_gate_can_restrict_actionable_authority",
        True,
    )

    require(
        publication,
        "decision_center_may_restore_removed_score_label",
        False,
    )

    missing = require(
        contract,
        "missing_data_semantics",
    )

    for key in [
        "missing_is_neutral",
        "missing_is_negative",
        "missing_is_positive",
        "missing_is_zero",
        "missing_may_create_actionable_authority",
    ]:
        require(
            missing,
            key,
            False,
        )

    require(
        missing,
        "default_behavior",
        "RESTRICT_DECISION_AUTHORITY",
    )

    conflicts = require(
        contract,
        "conflict_semantics",
    )

    require(
        conflicts,
        "material_conflicts_must_be_preserved",
        True,
    )

    require(
        conflicts,
        "conflicts_may_be_silently_discarded",
        False,
    )

    require(
        conflicts,
        "conflicts_may_be_hidden_by_high_score",
        False,
    )

    require(
        conflicts,
        "unresolved_material_conflict_state",
        "THESIS_REVIEW",
    )

    authority = require(
        contract,
        "authority_rules",
    )

    require(
        authority,
        "actionable_is_highest_decision_authority",
        True,
    )

    require(
        authority,
        "actionable_requires_all_gates_passed",
        True,
    )

    require(
        authority,
        "actionable_may_be_inferred_from_score_label_alone",
        False,
    )

    require(
        authority,
        "restrictive_states_take_precedence_over_actionable",
        True,
    )

    require(
        authority,
        "unknown_condition_behavior",
        "FAIL_CLOSED",
    )

    classes = require(
        contract,
        "information_class_rules",
    )

    check(
        classes.get("allowed_classes")
        == [
            "FACT",
            "MODEL",
            "INFERENCE",
            "DECISION",
        ],
        "Information classes changed",
    )

    require(
        classes,
        "decision_state_class",
        "DECISION",
    )

    require(
        classes,
        "upstream_score_class",
        "MODEL",
    )

    require(
        classes,
        "upstream_risk_class",
        "MODEL",
    )

    require(
        classes,
        "decision_must_not_be_presented_as_fact",
        True,
    )

    require(
        classes,
        "inference_must_not_be_presented_as_fact",
        True,
    )

    prohibited = set(
        require(
            contract,
            "prohibited_behaviors",
        )
        or []
    )

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

    check(
        mandatory_prohibitions.issubset(
            prohibited
        ),
        "Mandatory prohibited behavior missing",
    )

    future = require(
        contract,
        "future_policy_boundary",
    )

    require(
        future,
        "numeric_thresholds_defined_here",
        False,
    )

    require(
        future,
        "component_thresholds_defined_here",
        False,
    )

    require(
        future,
        "portfolio_actions_defined_here",
        False,
    )

    require(
        future,
        "trade_execution_defined_here",
        False,
    )

    require(
        future,
        "thresholds_require_separate_decision_policy",
        True,
    )

    finish()


def finish():
    print("=" * 60)
    print(
        " D.2B - DECISION STATE CONTRACT TEST"
    )
    print("=" * 60)
    print(f"Checks executed: {checks}")
    print(f"Failures: {len(failures)}")

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")

        print("RESULT: REJECTED")
        raise SystemExit(1)

    print("RESULT: APPROVED")


if __name__ == "__main__":
    main()
