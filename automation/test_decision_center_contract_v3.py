import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

CONTRACT_PATH = BASE_DIR / "decision_center_contract_v3.json"
SCHEMA_PATH = BASE_DIR / "schema_v3.json"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_json(path):
    require(path.exists(), f"Missing required file: {path.name}")

    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def main():
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)

    checks = 0

    def check(condition, message):
        nonlocal checks
        require(condition, message)
        checks += 1

    # Identity
    check(
        contract.get("contract_id") == "RADAR_V3_DECISION_CENTER_CONTRACT",
        "Unexpected Decision Center contract_id.",
    )

    check(
        contract.get("scope") == "RADAR_INSTITUCIONAL_V3_ONLY",
        "Decision Center contract must be scoped to V3 only.",
    )

    # V2.1 isolation
    compatibility = contract.get("compatibility", {})

    check(
        compatibility.get("preserve_v2_1") is True,
        "V2.1 preservation must be mandatory.",
    )

    check(
        compatibility.get("may_modify_v2_1") is False,
        "Decision Center must never modify V2.1.",
    )

    # Existing V3 public contract preservation
    expected_public_fields = {
        "action_of_day",
        "top_opportunities",
        "top_risks",
        "recommended_actions",
    }

    contract_public_fields = set(
        compatibility.get("existing_public_output_fields", [])
    )

    check(
        contract_public_fields == expected_public_fields,
        "Existing V3 Decision Center public fields were not preserved.",
    )

    decision_schema = schema.get("$defs", {}).get("decisionCenter")

    check(
        isinstance(decision_schema, dict),
        "$defs.decisionCenter missing from schema_v3.json.",
    )

    schema_required = set(decision_schema.get("required", []))

    check(
        schema_required == expected_public_fields,
        "Schema Decision Center required fields changed unexpectedly.",
    )

    schema_properties = set(
        decision_schema.get("properties", {}).keys()
    )

    check(
        schema_properties == expected_public_fields,
        "Schema Decision Center properties changed unexpectedly.",
    )

    check(
        decision_schema.get("additionalProperties") is False,
        "Existing Decision Center schema boundary must remain closed.",
    )

    check(
        compatibility.get("schema_change_required_by_this_contract") is False,
        "D.1 contract must not require a schema change.",
    )

    # Information classes
    information_classes = set(
        contract.get("information_classes", {}).keys()
    )

    check(
        information_classes == {
            "FACT",
            "MODEL",
            "INFERENCE",
            "DECISION",
        },
        "Information classes must be FACT/MODEL/INFERENCE/DECISION.",
    )

    # Core principles
    principles = set(contract.get("principles", []))

    required_principles = {
        "NEVER_INVENT_DATA",
        "MISSING_EVIDENCE_IS_NOT_NEUTRAL",
        "KEEP_FACT_MODEL_INFERENCE_DECISION_DISTINCT",
        "RADAR_SCORE_IS_NOT_AUTOMATIC_DECISION",
        "PRESERVE_CONFLICTING_EVIDENCE",
        "DO_NOT_IGNORE_RISK",
        "PUBLICATION_ELIGIBILITY_PARTICIPATES_IN_DECISION_ELIGIBILITY",
        "INSUFFICIENT_COVERAGE_RESTRICTS_DECISION_AUTHORITY",
        "DECISIONS_MUST_BE_EXPLAINABLE",
        "INFERENCES_MUST_BE_TRACEABLE",
        "DO_NOT_MODIFY_UPSTREAM_ANALYTICAL_OUTPUTS",
        "FAIL_CLOSED_BY_DEFAULT",
        "PRESERVE_V2_1",
        "DOMAIN_ENGINES_MUST_NOT_WRITE_DIRECTLY_TO_DECISION_CENTER",
        "DO_NOT_PROMOTE_UNAVAILABLE_EVIDENCE",
        "DO_NOT_OVERRIDE_PUBLICATION_ELIGIBILITY",
        "DO_NOT_MANUFACTURE_DECISIONS_FROM_BLOCKED_SCORES",
        "DO_NOT_DISCARD_CONFLICTS_TO_SIMPLIFY_CONCLUSION",
    }

    check(
        required_principles.issubset(principles),
        "One or more mandatory Decision Center principles are missing.",
    )

    # Architectural boundaries
    boundaries = contract.get("boundaries", {})

    check(
        boundaries.get("upstream_engines_produce_evidence") is True,
        "Upstream engines must produce evidence.",
    )

    check(
        boundaries.get("decision_center_consumes_evidence") is True,
        "Decision Center must consume evidence.",
    )

    forbidden_permissions = {
        "decision_center_may_recalculate_radar_score": False,
        "decision_center_may_override_confidence": False,
        "decision_center_may_override_risk": False,
        "decision_center_may_override_publication_eligibility": False,
        "domain_engines_may_write_decision_center_directly": False,
        "reconciliation_pipelines_may_write_decision_center_directly": False,
        "collectors_may_write_decision_center_directly": False,
    }

    for key, expected in forbidden_permissions.items():
        check(
            boundaries.get(key) is expected,
            f"Unsafe Decision Center boundary: {key}.",
        )

    # Evidence semantics
    semantics = contract.get("evidence_semantics", {})

    check(
        semantics.get("missing_is_neutral") is False,
        "Missing evidence must not become neutral evidence.",
    )

    check(
        semantics.get("missing_is_negative") is False,
        "Missing evidence must not become negative evidence.",
    )

    check(
        semantics.get("missing_is_positive") is False,
        "Missing evidence must not become positive evidence.",
    )

    check(
        semantics.get("unavailable_is_usable") is False,
        "Unavailable evidence must not be usable.",
    )

    check(
        semantics.get("blocked_is_usable") is False,
        "Blocked evidence must not be usable.",
    )

    check(
        semantics.get("low_confidence_may_be_silently_promoted") is False,
        "Low-confidence evidence must not be silently promoted.",
    )

    check(
        semantics.get("conflicting_evidence_must_be_preserved") is True,
        "Conflicting evidence must remain visible.",
    )

    # Evidence Gate
    evidence_gate = contract.get("evidence_gate", {})

    check(
        evidence_gate.get("required_before_decision") is True,
        "Evidence Gate must run before decision generation.",
    )

    required_gate_inputs = {
        "CONFIDENCE",
        "COVERAGE",
        "PROVENANCE",
        "PUBLICATION_ELIGIBILITY",
        "RISK",
    }

    check(
        required_gate_inputs.issubset(
            set(evidence_gate.get("must_consider", []))
        ),
        "Evidence Gate is missing mandatory inputs.",
    )

    check(
        evidence_gate.get(
            "blocked_evidence_may_generate_actionable_decision"
        ) is False,
        "Blocked evidence must not generate actionable decisions.",
    )

    check(
        evidence_gate.get("insufficient_evidence_behavior")
        == "FAIL_CLOSED",
        "Insufficient evidence must fail closed.",
    )

    # Traceability
    traceability = contract.get("traceability", {})

    for key in (
        "decision_requires_supporting_evidence",
        "inference_requires_source_evidence",
        "decision_requires_information_classification",
        "conflicts_must_remain_auditable",
    ):
        check(
            traceability.get(key) is True,
            f"Traceability requirement missing: {key}.",
        )

    # Explicit prohibitions
    prohibited = set(contract.get("prohibited_behaviors", []))

    required_prohibitions = {
        "INVENT_DATA",
        "TREAT_MISSING_AS_NEUTRAL",
        "TREAT_MISSING_AS_NEGATIVE",
        "TREAT_MISSING_AS_POSITIVE",
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

    check(
        required_prohibitions.issubset(prohibited),
        "Mandatory Decision Center prohibitions are missing.",
    )

    # Fail-closed behavior
    fail_closed = contract.get("fail_closed_rules", {})

    check(
        fail_closed.get("unknown_evidence_status") == "BLOCK",
        "Unknown evidence status must block.",
    )

    check(
        fail_closed.get("missing_required_evidence")
        == "RESTRICT_DECISION",
        "Missing required evidence must restrict decision.",
    )

    check(
        fail_closed.get("invalid_provenance") == "BLOCK_EVIDENCE",
        "Invalid provenance must block evidence.",
    )

    check(
        fail_closed.get("publication_ineligible")
        == "BLOCK_ACTIONABLE_DECISION",
        "Publication-ineligible evidence must block actionable decision.",
    )

    check(
        fail_closed.get("unresolved_evidence_conflict")
        == "PRESERVE_AND_RESTRICT",
        "Unresolved conflict must be preserved and restrict decision.",
    )

    check(
        fail_closed.get("unknown_information_class") == "BLOCK",
        "Unknown information class must block.",
    )

    # Public output
    public_output = contract.get("public_output_contract", {})

    check(
        public_output.get("target") == "decision_center",
        "Unexpected public output target.",
    )

    check(
        public_output.get("preserve_existing_fields") is True,
        "Existing Decision Center fields must be preserved.",
    )

    check(
        set(public_output.get("fields", []))
        == expected_public_fields,
        "Public Decision Center output fields changed unexpectedly.",
    )

    check(
        public_output.get(
            "internal_reasoning_may_not_be_presented_as_fact"
        ) is True,
        "Internal inference must not be presented as fact.",
    )

    print("============================================================")
    print(" D.1D - DECISION CENTER CONTRACT TEST")
    print("============================================================")
    print(f"Checks executed: {checks}")
    print("Failures: 0")
    print("RESULT: APPROVED")


if __name__ == "__main__":
    main()
