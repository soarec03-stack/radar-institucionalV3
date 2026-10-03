import copy
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONTRACT_PATH = BASE_DIR / "decision_center_contract_v3.json"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_contract():
    require(
        CONTRACT_PATH.exists(),
        "decision_center_contract_v3.json is missing.",
    )

    with CONTRACT_PATH.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def validate_safety(contract):
    errors = []

    compatibility = contract.get("compatibility", {})
    boundaries = contract.get("boundaries", {})
    semantics = contract.get("evidence_semantics", {})
    gate = contract.get("evidence_gate", {})
    traceability = contract.get("traceability", {})
    fail_closed = contract.get("fail_closed_rules", {})
    prohibited = set(contract.get("prohibited_behaviors", []))
    information_classes = set(
        contract.get("information_classes", {}).keys()
    )

    if compatibility.get("preserve_v2_1") is not True:
        errors.append("V2_1_NOT_PRESERVED")

    if compatibility.get("may_modify_v2_1") is not False:
        errors.append("V2_1_MODIFICATION_ALLOWED")

    if boundaries.get(
        "decision_center_may_recalculate_radar_score"
    ) is not False:
        errors.append("RADAR_SCORE_RECALCULATION_ALLOWED")

    if boundaries.get(
        "decision_center_may_override_confidence"
    ) is not False:
        errors.append("CONFIDENCE_OVERRIDE_ALLOWED")

    if boundaries.get(
        "decision_center_may_override_risk"
    ) is not False:
        errors.append("RISK_OVERRIDE_ALLOWED")

    if boundaries.get(
        "decision_center_may_override_publication_eligibility"
    ) is not False:
        errors.append("PUBLICATION_OVERRIDE_ALLOWED")

    if boundaries.get(
        "domain_engines_may_write_decision_center_directly"
    ) is not False:
        errors.append("DOMAIN_DIRECT_WRITE_ALLOWED")

    if boundaries.get(
        "reconciliation_pipelines_may_write_decision_center_directly"
    ) is not False:
        errors.append("RECONCILIATION_DIRECT_WRITE_ALLOWED")

    if boundaries.get(
        "collectors_may_write_decision_center_directly"
    ) is not False:
        errors.append("COLLECTOR_DIRECT_WRITE_ALLOWED")

    if semantics.get("missing_is_neutral") is not False:
        errors.append("MISSING_BECAME_NEUTRAL")

    if semantics.get("missing_is_negative") is not False:
        errors.append("MISSING_BECAME_NEGATIVE")

    if semantics.get("missing_is_positive") is not False:
        errors.append("MISSING_BECAME_POSITIVE")

    if semantics.get("unavailable_is_usable") is not False:
        errors.append("UNAVAILABLE_BECAME_USABLE")

    if semantics.get("blocked_is_usable") is not False:
        errors.append("BLOCKED_BECAME_USABLE")

    if semantics.get(
        "low_confidence_may_be_silently_promoted"
    ) is not False:
        errors.append("LOW_CONFIDENCE_PROMOTION_ALLOWED")

    if semantics.get(
        "conflicting_evidence_must_be_preserved"
    ) is not True:
        errors.append("CONFLICT_PRESERVATION_DISABLED")

    if gate.get("required_before_decision") is not True:
        errors.append("EVIDENCE_GATE_DISABLED")

    mandatory_gate_inputs = {
        "CONFIDENCE",
        "COVERAGE",
        "PROVENANCE",
        "PUBLICATION_ELIGIBILITY",
        "RISK",
    }

    if not mandatory_gate_inputs.issubset(
        set(gate.get("must_consider", []))
    ):
        errors.append("MANDATORY_GATE_INPUT_REMOVED")

    if gate.get(
        "blocked_evidence_may_generate_actionable_decision"
    ) is not False:
        errors.append("BLOCKED_EVIDENCE_ACTIONABLE")

    if gate.get("insufficient_evidence_behavior") != "FAIL_CLOSED":
        errors.append("FAIL_CLOSED_DISABLED")

    if traceability.get(
        "decision_requires_supporting_evidence"
    ) is not True:
        errors.append("DECISION_WITHOUT_EVIDENCE_ALLOWED")

    if traceability.get(
        "inference_requires_source_evidence"
    ) is not True:
        errors.append("INFERENCE_WITHOUT_EVIDENCE_ALLOWED")

    if traceability.get(
        "decision_requires_information_classification"
    ) is not True:
        errors.append("UNCLASSIFIED_DECISION_ALLOWED")

    if traceability.get(
        "conflicts_must_remain_auditable"
    ) is not True:
        errors.append("CONFLICT_AUDIT_DISABLED")

    if information_classes != {
        "FACT",
        "MODEL",
        "INFERENCE",
        "DECISION",
    }:
        errors.append("INFORMATION_CLASS_CONTRACT_CHANGED")

    required_prohibitions = {
        "INVENT_DATA",
        "TREAT_MISSING_AS_NEUTRAL",
        "PROMOTE_UNAVAILABLE_EVIDENCE",
        "PROMOTE_BLOCKED_EVIDENCE",
        "OVERRIDE_CONFIDENCE",
        "OVERRIDE_RISK",
        "OVERRIDE_PUBLICATION_ELIGIBILITY",
        "RECALCULATE_RADAR_SCORE",
        "MANUFACTURE_DECISION_FROM_BLOCKED_SCORE",
        "DISCARD_CONFLICTING_EVIDENCE",
        "WRITE_DIRECTLY_FROM_COLLECTOR_TO_DECISION_CENTER",
        "WRITE_DIRECTLY_FROM_DOMAIN_ENGINE_TO_DECISION_CENTER",
        "WRITE_DIRECTLY_FROM_RECONCILIATION_TO_DECISION_CENTER",
        "MODIFY_V2_1",
    }

    if not required_prohibitions.issubset(prohibited):
        errors.append("MANDATORY_PROHIBITION_REMOVED")

    expected_fail_closed = {
        "unknown_evidence_status": "BLOCK",
        "missing_required_evidence": "RESTRICT_DECISION",
        "invalid_provenance": "BLOCK_EVIDENCE",
        "publication_ineligible": "BLOCK_ACTIONABLE_DECISION",
        "unresolved_evidence_conflict": "PRESERVE_AND_RESTRICT",
        "unknown_information_class": "BLOCK",
    }

    for key, expected in expected_fail_closed.items():
        if fail_closed.get(key) != expected:
            errors.append(f"FAIL_CLOSED_RULE_CHANGED:{key}")

    return errors


def mutate(base, mutation):
    candidate = copy.deepcopy(base)
    mutation(candidate)
    return candidate


def main():
    base = load_contract()

    base_errors = validate_safety(base)

    require(
        not base_errors,
        f"Baseline contract is already unsafe: {base_errors}",
    )

    cases = [
        (
            "allow_modify_v2_1",
            lambda c: c["compatibility"].update(
                {"may_modify_v2_1": True}
            ),
            "V2_1_MODIFICATION_ALLOWED",
        ),
        (
            "disable_v2_1_preservation",
            lambda c: c["compatibility"].update(
                {"preserve_v2_1": False}
            ),
            "V2_1_NOT_PRESERVED",
        ),
        (
            "allow_score_recalculation",
            lambda c: c["boundaries"].update(
                {"decision_center_may_recalculate_radar_score": True}
            ),
            "RADAR_SCORE_RECALCULATION_ALLOWED",
        ),
        (
            "allow_confidence_override",
            lambda c: c["boundaries"].update(
                {"decision_center_may_override_confidence": True}
            ),
            "CONFIDENCE_OVERRIDE_ALLOWED",
        ),
        (
            "allow_risk_override",
            lambda c: c["boundaries"].update(
                {"decision_center_may_override_risk": True}
            ),
            "RISK_OVERRIDE_ALLOWED",
        ),
        (
            "allow_publication_override",
            lambda c: c["boundaries"].update(
                {
                    "decision_center_may_override_publication_eligibility": True
                }
            ),
            "PUBLICATION_OVERRIDE_ALLOWED",
        ),
        (
            "allow_domain_direct_write",
            lambda c: c["boundaries"].update(
                {
                    "domain_engines_may_write_decision_center_directly": True
                }
            ),
            "DOMAIN_DIRECT_WRITE_ALLOWED",
        ),
        (
            "allow_reconciliation_direct_write",
            lambda c: c["boundaries"].update(
                {
                    "reconciliation_pipelines_may_write_decision_center_directly": True
                }
            ),
            "RECONCILIATION_DIRECT_WRITE_ALLOWED",
        ),
        (
            "allow_collector_direct_write",
            lambda c: c["boundaries"].update(
                {
                    "collectors_may_write_decision_center_directly": True
                }
            ),
            "COLLECTOR_DIRECT_WRITE_ALLOWED",
        ),
        (
            "missing_becomes_neutral",
            lambda c: c["evidence_semantics"].update(
                {"missing_is_neutral": True}
            ),
            "MISSING_BECAME_NEUTRAL",
        ),
        (
            "missing_becomes_negative",
            lambda c: c["evidence_semantics"].update(
                {"missing_is_negative": True}
            ),
            "MISSING_BECAME_NEGATIVE",
        ),
        (
            "missing_becomes_positive",
            lambda c: c["evidence_semantics"].update(
                {"missing_is_positive": True}
            ),
            "MISSING_BECAME_POSITIVE",
        ),
        (
            "unavailable_becomes_usable",
            lambda c: c["evidence_semantics"].update(
                {"unavailable_is_usable": True}
            ),
            "UNAVAILABLE_BECAME_USABLE",
        ),
        (
            "blocked_becomes_usable",
            lambda c: c["evidence_semantics"].update(
                {"blocked_is_usable": True}
            ),
            "BLOCKED_BECAME_USABLE",
        ),
        (
            "promote_low_confidence",
            lambda c: c["evidence_semantics"].update(
                {"low_confidence_may_be_silently_promoted": True}
            ),
            "LOW_CONFIDENCE_PROMOTION_ALLOWED",
        ),
        (
            "discard_conflicts",
            lambda c: c["evidence_semantics"].update(
                {"conflicting_evidence_must_be_preserved": False}
            ),
            "CONFLICT_PRESERVATION_DISABLED",
        ),
        (
            "disable_evidence_gate",
            lambda c: c["evidence_gate"].update(
                {"required_before_decision": False}
            ),
            "EVIDENCE_GATE_DISABLED",
        ),
        (
            "remove_risk_from_gate",
            lambda c: c["evidence_gate"].update(
                {
                    "must_consider": [
                        value
                        for value in c["evidence_gate"]["must_consider"]
                        if value != "RISK"
                    ]
                }
            ),
            "MANDATORY_GATE_INPUT_REMOVED",
        ),
        (
            "blocked_evidence_actionable",
            lambda c: c["evidence_gate"].update(
                {
                    "blocked_evidence_may_generate_actionable_decision": True
                }
            ),
            "BLOCKED_EVIDENCE_ACTIONABLE",
        ),
        (
            "disable_fail_closed",
            lambda c: c["evidence_gate"].update(
                {"insufficient_evidence_behavior": "CONTINUE"}
            ),
            "FAIL_CLOSED_DISABLED",
        ),
        (
            "decision_without_supporting_evidence",
            lambda c: c["traceability"].update(
                {"decision_requires_supporting_evidence": False}
            ),
            "DECISION_WITHOUT_EVIDENCE_ALLOWED",
        ),
        (
            "inference_without_source_evidence",
            lambda c: c["traceability"].update(
                {"inference_requires_source_evidence": False}
            ),
            "INFERENCE_WITHOUT_EVIDENCE_ALLOWED",
        ),
        (
            "decision_without_classification",
            lambda c: c["traceability"].update(
                {"decision_requires_information_classification": False}
            ),
            "UNCLASSIFIED_DECISION_ALLOWED",
        ),
        (
            "disable_conflict_audit",
            lambda c: c["traceability"].update(
                {"conflicts_must_remain_auditable": False}
            ),
            "CONFLICT_AUDIT_DISABLED",
        ),
        (
            "remove_fact_class",
            lambda c: c["information_classes"].pop("FACT"),
            "INFORMATION_CLASS_CONTRACT_CHANGED",
        ),
        (
            "remove_prohibition",
            lambda c: c["prohibited_behaviors"].remove(
                "MODIFY_V2_1"
            ),
            "MANDATORY_PROHIBITION_REMOVED",
        ),
        (
            "weaken_publication_fail_closed",
            lambda c: c["fail_closed_rules"].update(
                {"publication_ineligible": "ALLOW"}
            ),
            "FAIL_CLOSED_RULE_CHANGED:publication_ineligible",
        ),
        (
            "weaken_invalid_provenance",
            lambda c: c["fail_closed_rules"].update(
                {"invalid_provenance": "ALLOW"}
            ),
            "FAIL_CLOSED_RULE_CHANGED:invalid_provenance",
        ),
        (
            "weaken_unknown_status",
            lambda c: c["fail_closed_rules"].update(
                {"unknown_evidence_status": "ALLOW"}
            ),
            "FAIL_CLOSED_RULE_CHANGED:unknown_evidence_status",
        ),
        (
            "weaken_conflict_rule",
            lambda c: c["fail_closed_rules"].update(
                {"unresolved_evidence_conflict": "IGNORE"}
            ),
            "FAIL_CLOSED_RULE_CHANGED:unresolved_evidence_conflict",
        ),
    ]

    passed = 0
    failed = []

    for name, mutation, expected_error in cases:
        candidate = mutate(base, mutation)
        errors = validate_safety(candidate)

        if expected_error in errors:
            print(f"[PASS] {name} -> {expected_error}")
            passed += 1
        else:
            print(
                f"[FAIL] {name} -> expected {expected_error}; "
                f"got {errors}"
            )
            failed.append(name)

    print("")
    print("============================================================")
    print(" D.1E - DECISION CENTER ADVERSARIAL CONTRACT TEST")
    print("============================================================")
    print(f"Cases executed: {len(cases)}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("RESULT: REJECTED")
        raise AssertionError(
            "Adversarial cases not detected: "
            + ", ".join(failed)
        )

    print("RESULT: APPROVED")


if __name__ == "__main__":
    main()
