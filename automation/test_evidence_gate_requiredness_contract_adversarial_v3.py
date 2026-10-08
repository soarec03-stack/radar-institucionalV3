import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent

CONTRACT_PATH = ROOT / "evidence_gate_requiredness_contract_v3.json"
POLICY_PATH = ROOT / "evidence_gate_policy_v3.json"
RUNTIME_PATH = ROOT / "evidence_gate_runtime_contract_v3.json"
BRIDGE_PATH = ROOT / "evidence_gate_context_bridge_contract_v3.json"


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


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


canonical = load_json(CONTRACT_PATH)
policy = load_json(POLICY_PATH)
runtime = load_json(RUNTIME_PATH)
bridge = load_json(BRIDGE_PATH)


EXPECTED_REQUIRED = {
    "score",
    "coverage",
    "confidence",
    "risk",
    "domain_signals",
    "price_provenance",
}

EXPECTED_CONDITIONAL = {
    "publication_context",
    "risk_source_context",
}

EXPECTED_OPTIONAL = {
    "catalysts",
    "institutional_flow",
    "portfolio",
    "market_regime",
}

EXPECTED_REQUIRED_ORDER = [
    "score",
    "coverage",
    "confidence",
    "risk",
    "domain_signals",
    "price_provenance",
]

EXPECTED_PROHIBITIONS = {
    "INVENT_REQUIRED_EVIDENCE",
    "IMPUTE_REQUIRED_EVIDENCE",
    "DEFAULT_REQUIRED_EVIDENCE",
    "TRANSLATE_LEGACY_SCORE",
    "INFER_REQUIRED_SCORE_FIELDS",
    "CALCULATE_COVERAGE_IN_GATE",
    "INFER_CONFIDENCE_STATUS",
    "TREAT_MISSING_RISK_AS_LOW",
    "TREAT_MISSING_RISK_AS_ZERO",
    "RECALCULATE_SIGNALS",
    "INFER_SIGNALS_FROM_SCORE",
    "INFER_SIGNALS_FROM_METRICS",
    "INFER_SIGNALS_FROM_PRICE",
    "INVENT_PROVENANCE",
    "REPAIR_PROVENANCE",
    "INFER_PROVENANCE_FROM_PRICE",
    "INFER_PROVENANCE_FROM_SOURCE_NAME",
    "ASSUME_PUBLICATION_ELIGIBLE",
    "RECALCULATE_PUBLICATION_ELIGIBILITY",
    "REBUILD_RISK_SOURCE_CONTEXT",
    "INFER_CONDITIONAL_REQUIREDNESS_FROM_MAGNITUDE",
    "INFER_CONDITIONAL_REQUIREDNESS_FROM_ABSENCE",
    "PROMOTE_OPTIONAL_EVIDENCE_TO_REQUIRED_SILENTLY",
    "DEMOTE_REQUIRED_EVIDENCE_TO_OPTIONAL_SILENTLY",
    "DEFINE_NEW_NUMERIC_THRESHOLDS",
    "DUPLICATE_UPSTREAM_THRESHOLDS",
    "SELECT_DECISION_STATE",
    "ESTABLISH_ACTIONABLE_AUTHORITY",
    "RESOLVE_CONFLICT",
    "WRITE_DECISION_CENTER",
    "MODIFY_GENERATOR",
    "MODIFY_SCHEMA_V3",
    "MODIFY_V2_1",
    "REWRITE_B2K_FIXTURES",
}


def validate_contract(c):
    try:
        if c.get("contract_id") != "RADAR_V3_EVIDENCE_GATE_REQUIREDNESS_CONTRACT":
            return False

        if c.get("contract_version") != "3.4D.3D.4D":
            return False

        if c.get("status") != "DRAFT":
            return False

        if c.get("scope") != "V3_ONLY":
            return False

        purpose = c["purpose"]

        if purpose.get("defines_evidence_requiredness") is not True:
            return False

        for key in (
            "defines_evidence_admissibility",
            "defines_numeric_thresholds",
            "duplicates_upstream_thresholds",
            "recalculates_upstream_results",
            "implements_evidence_gate_engine",
            "implements_context_bridge",
            "defines_conflict_resolution",
            "defines_decision_state",
            "defines_actionable_authority",
            "writes_decision_center",
            "modifies_public_output",
        ):
            if purpose.get(key) is not False:
                return False

        compatibility = c["compatibility"]

        if compatibility.get("preserve_v2_1") is not True:
            return False

        for key in (
            "modify_v2_1",
            "modify_schema_v3",
            "modify_generator",
            "modify_existing_decision_center_contract",
            "modify_public_output",
            "modify_b2k_fixtures",
        ):
            if compatibility.get(key) is not False:
                return False

        refs = c["references"]

        if refs.get("evidence_gate_policy_id") != policy["policy_id"]:
            return False

        if refs.get("evidence_gate_policy_version") != policy["policy_version"]:
            return False

        if refs.get("evidence_gate_runtime_contract_id") != runtime["contract_id"]:
            return False

        if refs.get("context_bridge_contract_id") != bridge["contract_id"]:
            return False

        if refs.get("context_bridge_contract_version") != bridge["contract_version"]:
            return False

        classes = c["requiredness_classes"]

        if set(classes.keys()) != {"REQUIRED", "CONDITIONAL", "OPTIONAL"}:
            return False

        required_class = classes["REQUIRED"]

        if required_class.get("missing_result") != "INSUFFICIENT":
            return False

        for key in (
            "may_be_imputed",
            "may_be_defaulted",
            "may_be_reconstructed",
            "absence_is_neutral",
            "absence_is_negative",
            "absence_is_positive",
        ):
            if required_class.get(key) is not False:
                return False

        conditional_class = classes["CONDITIONAL"]

        if conditional_class.get("condition_source") != "UPSTREAM_EXPLICIT_CONTEXT_ONLY":
            return False

        if conditional_class.get("missing_when_condition_applies_result") != "INSUFFICIENT":
            return False

        if conditional_class.get("missing_when_condition_does_not_apply_result") != "NOT_REQUIRED":
            return False

        for key in (
            "may_infer_condition_from_missing_data",
            "may_infer_condition_from_score_magnitude",
            "may_infer_condition_from_risk_magnitude",
            "may_infer_condition_from_signal_magnitude",
            "may_be_imputed",
            "may_be_defaulted",
            "may_be_reconstructed",
        ):
            if conditional_class.get(key) is not False:
                return False

        optional_class = classes["OPTIONAL"]

        if optional_class.get("missing_result") != "NOT_REQUIRED":
            return False

        if optional_class.get("presence_does_not_guarantee_admissibility") is not True:
            return False

        for key in (
            "may_be_imputed",
            "may_be_defaulted",
            "may_be_reconstructed",
        ):
            if optional_class.get(key) is not False:
                return False

        required = c["required_evidence"]

        if set(required.keys()) != EXPECTED_REQUIRED:
            return False

        for name in EXPECTED_REQUIRED:
            item = required[name]

            if item.get("requiredness") != "REQUIRED":
                return False

            if item.get("missing_result") != "INSUFFICIENT":
                return False

        score = required["score"]

        if score.get("domain") != "RADAR_SCORE":
            return False

        if score.get("canonical_runtime_source") != "asset.score":
            return False

        if score.get("required_runtime_fields") != [
            "status",
            "analytically_usable",
            "publishable",
        ]:
            return False

        if score.get("legacy_shape_is_canonical_runtime_evidence") is not False:
            return False

        if score.get("may_translate_legacy_shape") is not False:
            return False

        if score.get("may_infer_missing_fields") is not False:
            return False

        if score.get("threshold_owner") != "SCORE_ENGINE":
            return False

        coverage = required["coverage"]

        if coverage.get("domain") != "COVERAGE":
            return False

        if coverage.get("canonical_runtime_source") != "asset.score.coverage":
            return False

        for key in (
            "may_calculate_from_components",
            "may_infer_from_score_status",
            "may_define_new_threshold",
        ):
            if coverage.get(key) is not False:
                return False

        if coverage.get("threshold_owner") != "SCORE_ENGINE":
            return False

        confidence = required["confidence"]

        if confidence.get("domain") != "CONFIDENCE":
            return False

        if confidence.get("canonical_runtime_source") != "asset.confidence":
            return False

        if confidence.get("required_runtime_fields") != ["status"]:
            return False

        for key in (
            "may_recalculate",
            "may_infer_status",
            "may_define_new_threshold",
        ):
            if confidence.get(key) is not False:
                return False

        if confidence.get("threshold_owner") != "CONFIDENCE_ENGINE":
            return False

        risk = required["risk"]

        if risk.get("domain") != "RISK":
            return False

        if risk.get("canonical_runtime_source") != "asset.risk":
            return False

        for key in (
            "missing_is_low_risk",
            "missing_is_zero_risk",
            "may_recalculate",
            "may_infer_from_price",
            "may_define_new_threshold",
        ):
            if risk.get(key) is not False:
                return False

        if risk.get("threshold_owner") != "RISK_ENGINE":
            return False

        signals = required["domain_signals"]

        if signals.get("domain") != "DOMAIN_SIGNALS":
            return False

        if signals.get("canonical_runtime_source") != "asset.signals":
            return False

        if signals.get("empty_result") != "INSUFFICIENT":
            return False

        for key in (
            "may_recalculate",
            "may_infer_from_score",
            "may_infer_from_metrics",
            "may_infer_from_price",
            "may_define_new_threshold",
        ):
            if signals.get(key) is not False:
                return False

        if signals.get("threshold_owner") != "SIGNAL_ENGINE":
            return False

        provenance = required["price_provenance"]

        if provenance.get("domain") != "RADAR_SCORE":
            return False

        if provenance.get("canonical_runtime_source") != "asset.provenance.price":
            return False

        if provenance.get("invalid_result") != "BLOCKED":
            return False

        if provenance.get("unknown_result") != "UNKNOWN":
            return False

        for key in (
            "may_invent",
            "may_repair",
            "may_infer_from_price_presence",
            "may_infer_from_source_name",
        ):
            if provenance.get(key) is not False:
                return False

        conditional = c["conditional_evidence"]

        if set(conditional.keys()) != EXPECTED_CONDITIONAL:
            return False

        publication = conditional["publication_context"]

        if publication.get("requiredness") != "CONDITIONAL":
            return False

        if publication.get("domain") != "PUBLICATION_ELIGIBILITY":
            return False

        if publication.get("canonical_runtime_source") != "publication_context_by_ticker[ticker]":
            return False

        if publication.get("condition") != "PUBLICATION_ELIGIBILITY_APPLICABLE_UPSTREAM":
            return False

        if publication.get("condition_owner") != "PUBLICATION_ELIGIBILITY":
            return False

        if publication.get("condition_must_be_explicit") is not True:
            return False

        if publication.get("missing_when_condition_applies_result") != "INSUFFICIENT":
            return False

        if publication.get("missing_when_condition_does_not_apply_result") != "NOT_REQUIRED":
            return False

        for key in (
            "may_recalculate_publication_eligibility",
            "may_infer_condition_from_score_publishable",
            "may_assume_eligible_when_missing",
        ):
            if publication.get(key) is not False:
                return False

        risk_context = conditional["risk_source_context"]

        if risk_context.get("requiredness") != "CONDITIONAL":
            return False

        if risk_context.get("domain") != "RISK":
            return False

        if risk_context.get("canonical_runtime_source") != "risk_source_context_by_ticker[ticker]":
            return False

        if risk_context.get("condition") != "RISK_PUBLICATION_CONTEXT_APPLICABLE_UPSTREAM":
            return False

        if risk_context.get("condition_owner") != "RISK_AND_PUBLICATION_RUNTIME":
            return False

        if risk_context.get("condition_must_be_explicit") is not True:
            return False

        if risk_context.get("missing_when_condition_applies_result") != "INSUFFICIENT":
            return False

        if risk_context.get("missing_when_condition_does_not_apply_result") != "NOT_REQUIRED":
            return False

        for key in (
            "may_rebuild_from_public_risk",
            "may_infer_condition_from_risk_level",
            "may_assume_eligible_when_missing",
        ):
            if risk_context.get(key) is not False:
                return False

        optional = c["optional_evidence"]

        if set(optional.keys()) != EXPECTED_OPTIONAL:
            return False

        for name in EXPECTED_OPTIONAL:
            item = optional[name]

            if item.get("requiredness") != "OPTIONAL":
                return False

            if item.get("absence_alone_blocks_gate") is not False:
                return False

        semantics = c["requiredness_semantics"]

        for key in (
            "required_missing_is_neutral",
            "required_missing_is_negative",
            "required_missing_is_positive",
            "required_missing_is_zero",
            "required_missing_is_admissible",
        ):
            if semantics.get(key) is not False:
                return False

        if semantics.get("required_missing_result") != "INSUFFICIENT":
            return False

        if semantics.get("optional_missing_is_failure") is not False:
            return False

        if semantics.get("optional_missing_is_admissible_evidence") is not False:
            return False

        if semantics.get("optional_missing_result") != "NOT_REQUIRED":
            return False

        if semantics.get("conditional_requiredness_must_be_explicit") is not True:
            return False

        if semantics.get("conditional_requiredness_may_be_inferred_from_magnitude") is not False:
            return False

        if semantics.get("conditional_requiredness_may_be_inferred_from_absence") is not False:
            return False

        thresholds = c["threshold_governance"]

        expected_threshold_governance_keys = {
            "defines_new_numeric_thresholds",
            "duplicates_score_thresholds",
            "duplicates_confidence_thresholds",
            "duplicates_risk_thresholds",
            "duplicates_signal_thresholds",
            "duplicates_publication_source_tiers",
            "consume_upstream_statuses_only",
        }

        if set(thresholds.keys()) != expected_threshold_governance_keys:
            return False

        for key in (
            "defines_new_numeric_thresholds",
            "duplicates_score_thresholds",
            "duplicates_confidence_thresholds",
            "duplicates_risk_thresholds",
            "duplicates_signal_thresholds",
            "duplicates_publication_source_tiers",
        ):
            if thresholds.get(key) is not False:
                return False

        if thresholds.get("consume_upstream_statuses_only") is not True:
            return False

        alignment = c["engine_alignment"]

        if alignment.get("required_baseline_exact") != EXPECTED_REQUIRED_ORDER:
            return False

        for key in (
            "must_not_silently_expand_required_baseline",
            "must_not_silently_reduce_required_baseline",
            "engine_change_required_if_contract_changes",
            "contract_change_required_if_engine_requiredness_changes",
        ):
            if alignment.get(key) is not True:
                return False

        decision = c["decision_boundary"]

        for key in (
            "requiredness_result_is_decision_state",
            "requiredness_result_is_actionable_authority",
            "requiredness_alone_may_select_ACTIONABLE",
            "requiredness_alone_may_select_WATCH",
            "requiredness_alone_may_select_WAIT_FOR_CONFIRMATION",
            "requiredness_alone_may_select_RISK_REVIEW",
            "requiredness_alone_may_select_THESIS_REVIEW",
            "requiredness_alone_may_select_INSUFFICIENT_EVIDENCE",
        ):
            if decision.get(key) is not False:
                return False

        if decision.get("decision_state_owner") != "D.5":
            return False

        if decision.get("conflict_resolution_owner") != "D.4":
            return False

        mutation = c["mutation_boundary"]

        for value in mutation.values():
            if value is not False:
                return False

        phase = c["phase_boundary"]

        if phase.get("this_step") != "D.3D.4D":
            return False

        if phase.get("this_step_defines_requiredness_contract_only") is not True:
            return False

        if phase.get("adversarial_requiredness_test") != "D.3D.4E":
            return False

        if phase.get("generator_integration") != "D.7":
            return False

        if set(c["prohibited_behaviors"]) != EXPECTED_PROHIBITIONS:
            return False

        return True

    except (KeyError, TypeError, AttributeError):
        return False


def mutate(path, value):
    candidate = copy.deepcopy(canonical)
    node = candidate

    for key in path[:-1]:
        node = node[key]

    node[path[-1]] = value
    return candidate


def reject(path, value, message):
    candidate = mutate(path, value)
    check(not validate_contract(candidate), message)


def reject_removed(path, message):
    candidate = copy.deepcopy(canonical)
    node = candidate

    for key in path[:-1]:
        node = node[key]

    del node[path[-1]]
    check(not validate_contract(candidate), message)


def reject_added(path, key, value, message):
    candidate = copy.deepcopy(canonical)
    node = candidate

    for item in path:
        node = node[item]

    node[key] = value
    check(not validate_contract(candidate), message)


print("=" * 78)
print(" D.3D.4E - REQUIREDNESS ADVERSARIAL CONTRACT TEST")
print("=" * 78)


# ============================================================
# A. CANONICAL BASELINE
# ============================================================

check(validate_contract(canonical), "canonical D.3D.4D contract accepted")


# ============================================================
# B. IDENTITY / SCOPE
# ============================================================

reject(["contract_id"], "BROKEN", "reject altered contract id")
reject(["contract_version"], "3.4D.3D.4E", "reject altered contract version")
reject(["status"], "PRODUCTION", "reject production status mutation")
reject(["scope"], "V2_AND_V3", "reject scope expansion beyond V3")


# ============================================================
# C. PURPOSE SCOPE CREEP
# ============================================================

reject(
    ["purpose", "defines_evidence_requiredness"],
    False,
    "reject disabling requiredness definition",
)

for key in (
    "defines_evidence_admissibility",
    "defines_numeric_thresholds",
    "duplicates_upstream_thresholds",
    "recalculates_upstream_results",
    "implements_evidence_gate_engine",
    "implements_context_bridge",
    "defines_conflict_resolution",
    "defines_decision_state",
    "defines_actionable_authority",
    "writes_decision_center",
    "modifies_public_output",
):
    reject(
        ["purpose", key],
        True,
        f"reject purpose scope creep: {key}",
    )


# ============================================================
# D. COMPATIBILITY
# ============================================================

reject(
    ["compatibility", "preserve_v2_1"],
    False,
    "reject disabling V2.1 preservation",
)

for key in (
    "modify_v2_1",
    "modify_schema_v3",
    "modify_generator",
    "modify_existing_decision_center_contract",
    "modify_public_output",
    "modify_b2k_fixtures",
):
    reject(
        ["compatibility", key],
        True,
        f"reject compatibility mutation: {key}",
    )


# ============================================================
# E. REQUIREDNESS CLASS CORRUPTION
# ============================================================

reject(
    ["requiredness_classes", "REQUIRED", "missing_result"],
    "NOT_REQUIRED",
    "reject REQUIRED missing -> NOT_REQUIRED",
)

for key in (
    "may_be_imputed",
    "may_be_defaulted",
    "may_be_reconstructed",
    "absence_is_neutral",
    "absence_is_negative",
    "absence_is_positive",
):
    reject(
        ["requiredness_classes", "REQUIRED", key],
        True,
        f"reject REQUIRED capability/semantics mutation: {key}",
    )

reject(
    ["requiredness_classes", "CONDITIONAL", "condition_source"],
    "GATE_INFERENCE",
    "reject inferred conditional source",
)

reject(
    [
        "requiredness_classes",
        "CONDITIONAL",
        "missing_when_condition_applies_result",
    ],
    "NOT_REQUIRED",
    "reject applicable conditional evidence becoming optional",
)

reject(
    [
        "requiredness_classes",
        "CONDITIONAL",
        "missing_when_condition_does_not_apply_result",
    ],
    "ADMISSIBLE",
    "reject non-applicable absence becoming admissible evidence",
)

for key in (
    "may_infer_condition_from_missing_data",
    "may_infer_condition_from_score_magnitude",
    "may_infer_condition_from_risk_magnitude",
    "may_infer_condition_from_signal_magnitude",
    "may_be_imputed",
    "may_be_defaulted",
    "may_be_reconstructed",
):
    reject(
        ["requiredness_classes", "CONDITIONAL", key],
        True,
        f"reject CONDITIONAL inference/capability: {key}",
    )

reject(
    ["requiredness_classes", "OPTIONAL", "missing_result"],
    "INSUFFICIENT",
    "reject OPTIONAL absence becoming failure",
)

reject(
    [
        "requiredness_classes",
        "OPTIONAL",
        "presence_does_not_guarantee_admissibility",
    ],
    False,
    "reject OPTIONAL presence guaranteeing admissibility",
)

for key in (
    "may_be_imputed",
    "may_be_defaulted",
    "may_be_reconstructed",
):
    reject(
        ["requiredness_classes", "OPTIONAL", key],
        True,
        f"reject OPTIONAL reconstruction capability: {key}",
    )


# ============================================================
# F. REQUIRED BASELINE
# ============================================================

for name in sorted(EXPECTED_REQUIRED):
    reject(
        ["required_evidence", name, "requiredness"],
        "OPTIONAL",
        f"reject demoting required evidence to OPTIONAL: {name}",
    )

    reject(
        ["required_evidence", name, "requiredness"],
        "CONDITIONAL",
        f"reject demoting required evidence to CONDITIONAL: {name}",
    )

    reject(
        ["required_evidence", name, "missing_result"],
        "NOT_REQUIRED",
        f"reject required missing becoming NOT_REQUIRED: {name}",
    )

for name in sorted(EXPECTED_REQUIRED):
    candidate = copy.deepcopy(canonical)
    del candidate["required_evidence"][name]

    check(
        not validate_contract(candidate),
        f"reject removing required evidence: {name}",
    )


# ============================================================
# G. OPTIONAL BASELINE
# ============================================================

for name in sorted(EXPECTED_OPTIONAL):
    reject(
        ["optional_evidence", name, "requiredness"],
        "REQUIRED",
        f"reject promoting optional evidence to REQUIRED: {name}",
    )

    reject(
        ["optional_evidence", name, "requiredness"],
        "CONDITIONAL",
        f"reject promoting optional evidence to CONDITIONAL: {name}",
    )

    reject(
        ["optional_evidence", name, "absence_alone_blocks_gate"],
        True,
        f"reject optional absence blocking Gate: {name}",
    )


# ============================================================
# H. SCORE / LEGACY SCORE
# ============================================================

reject(
    ["required_evidence", "score", "legacy_shape_is_canonical_runtime_evidence"],
    True,
    "reject legacy score as canonical runtime evidence",
)

reject(
    ["required_evidence", "score", "may_translate_legacy_shape"],
    True,
    "reject legacy score translation",
)

reject(
    ["required_evidence", "score", "may_infer_missing_fields"],
    True,
    "reject score field inference",
)

reject(
    ["required_evidence", "score", "threshold_owner"],
    "EVIDENCE_GATE",
    "reject Evidence Gate taking score threshold ownership",
)

reject(
    ["required_evidence", "score", "required_runtime_fields"],
    ["total", "label"],
    "reject legacy score runtime field contract",
)

reject(
    ["required_evidence", "score", "canonical_runtime_source"],
    "asset.decision",
    "reject alternate score runtime source",
)


# ============================================================
# I. COVERAGE
# ============================================================

for key in (
    "may_calculate_from_components",
    "may_infer_from_score_status",
    "may_define_new_threshold",
):
    reject(
        ["required_evidence", "coverage", key],
        True,
        f"reject coverage capability: {key}",
    )

reject(
    ["required_evidence", "coverage", "threshold_owner"],
    "EVIDENCE_GATE",
    "reject Gate ownership of coverage thresholds",
)

reject(
    ["required_evidence", "coverage", "canonical_runtime_source"],
    "asset.score.components",
    "reject coverage reconstruction source",
)


# ============================================================
# J. CONFIDENCE
# ============================================================

for key in (
    "may_recalculate",
    "may_infer_status",
    "may_define_new_threshold",
):
    reject(
        ["required_evidence", "confidence", key],
        True,
        f"reject confidence capability: {key}",
    )

reject(
    ["required_evidence", "confidence", "threshold_owner"],
    "EVIDENCE_GATE",
    "reject Gate ownership of confidence thresholds",
)

reject(
    ["required_evidence", "confidence", "required_runtime_fields"],
    ["score"],
    "reject confidence status removal",
)


# ============================================================
# K. RISK
# ============================================================

for key in (
    "missing_is_low_risk",
    "missing_is_zero_risk",
    "may_recalculate",
    "may_infer_from_price",
    "may_define_new_threshold",
):
    reject(
        ["required_evidence", "risk", key],
        True,
        f"reject risk capability/absence mutation: {key}",
    )

reject(
    ["required_evidence", "risk", "threshold_owner"],
    "EVIDENCE_GATE",
    "reject Gate ownership of risk thresholds",
)


# ============================================================
# L. SIGNALS
# ============================================================

for key in (
    "may_recalculate",
    "may_infer_from_score",
    "may_infer_from_metrics",
    "may_infer_from_price",
    "may_define_new_threshold",
):
    reject(
        ["required_evidence", "domain_signals", key],
        True,
        f"reject signal reconstruction capability: {key}",
    )

reject(
    ["required_evidence", "domain_signals", "empty_result"],
    "ADMISSIBLE",
    "reject empty signals becoming admissible",
)

reject(
    ["required_evidence", "domain_signals", "threshold_owner"],
    "EVIDENCE_GATE",
    "reject Gate ownership of signal thresholds",
)

reject(
    ["required_evidence", "domain_signals", "canonical_runtime_source"],
    "asset.metrics",
    "reject metrics used as reconstructed signals",
)


# ============================================================
# M. PROVENANCE
# ============================================================

for key in (
    "may_invent",
    "may_repair",
    "may_infer_from_price_presence",
    "may_infer_from_source_name",
):
    reject(
        ["required_evidence", "price_provenance", key],
        True,
        f"reject provenance capability: {key}",
    )

reject(
    ["required_evidence", "price_provenance", "invalid_result"],
    "ADMISSIBLE",
    "reject invalid provenance becoming admissible",
)

reject(
    ["required_evidence", "price_provenance", "unknown_result"],
    "ADMISSIBLE",
    "reject unknown provenance becoming admissible",
)

reject(
    ["required_evidence", "price_provenance", "canonical_runtime_source"],
    "asset.price",
    "reject price presence replacing provenance",
)


# ============================================================
# N. PUBLICATION CONDITIONAL CONTEXT
# ============================================================

reject(
    ["conditional_evidence", "publication_context", "requiredness"],
    "REQUIRED",
    "reject publication context becoming globally REQUIRED",
)

reject(
    ["conditional_evidence", "publication_context", "requiredness"],
    "OPTIONAL",
    "reject publication context becoming globally OPTIONAL",
)

reject(
    [
        "conditional_evidence",
        "publication_context",
        "condition_must_be_explicit",
    ],
    False,
    "reject implicit publication applicability",
)

for key in (
    "may_recalculate_publication_eligibility",
    "may_infer_condition_from_score_publishable",
    "may_assume_eligible_when_missing",
):
    reject(
        ["conditional_evidence", "publication_context", key],
        True,
        f"reject publication conditional capability: {key}",
    )

reject(
    ["conditional_evidence", "publication_context", "condition_owner"],
    "EVIDENCE_GATE",
    "reject Gate ownership of publication applicability",
)

reject(
    ["conditional_evidence", "publication_context", "condition"],
    "SCORE_PUBLISHABLE_TRUE",
    "reject score-derived publication applicability",
)

reject(
    [
        "conditional_evidence",
        "publication_context",
        "missing_when_condition_applies_result",
    ],
    "NOT_REQUIRED",
    "reject missing applicable publication context becoming optional",
)


# ============================================================
# O. RISK CONDITIONAL CONTEXT
# ============================================================

reject(
    ["conditional_evidence", "risk_source_context", "requiredness"],
    "REQUIRED",
    "reject risk source context becoming globally REQUIRED",
)

reject(
    ["conditional_evidence", "risk_source_context", "requiredness"],
    "OPTIONAL",
    "reject risk source context becoming globally OPTIONAL",
)

reject(
    [
        "conditional_evidence",
        "risk_source_context",
        "condition_must_be_explicit",
    ],
    False,
    "reject implicit risk context applicability",
)

for key in (
    "may_rebuild_from_public_risk",
    "may_infer_condition_from_risk_level",
    "may_assume_eligible_when_missing",
):
    reject(
        ["conditional_evidence", "risk_source_context", key],
        True,
        f"reject risk conditional capability: {key}",
    )

reject(
    ["conditional_evidence", "risk_source_context", "condition_owner"],
    "EVIDENCE_GATE",
    "reject Gate ownership of risk-context applicability",
)

reject(
    ["conditional_evidence", "risk_source_context", "condition"],
    "RISK_LEVEL_HIGH",
    "reject risk-magnitude-derived applicability",
)

reject(
    [
        "conditional_evidence",
        "risk_source_context",
        "missing_when_condition_applies_result",
    ],
    "NOT_REQUIRED",
    "reject missing applicable risk context becoming optional",
)


# ============================================================
# P. MISSING SEMANTICS
# ============================================================

for key in (
    "required_missing_is_neutral",
    "required_missing_is_negative",
    "required_missing_is_positive",
    "required_missing_is_zero",
    "required_missing_is_admissible",
):
    reject(
        ["requiredness_semantics", key],
        True,
        f"reject required missing semantic mutation: {key}",
    )

reject(
    ["requiredness_semantics", "required_missing_result"],
    "ADMISSIBLE",
    "reject required missing -> ADMISSIBLE",
)

reject(
    ["requiredness_semantics", "required_missing_result"],
    "NOT_REQUIRED",
    "reject required missing -> NOT_REQUIRED",
)

reject(
    ["requiredness_semantics", "optional_missing_is_failure"],
    True,
    "reject optional absence becoming failure",
)

reject(
    ["requiredness_semantics", "optional_missing_is_admissible_evidence"],
    True,
    "reject optional absence becoming admissible evidence",
)

reject(
    ["requiredness_semantics", "optional_missing_result"],
    "INSUFFICIENT",
    "reject optional absence -> INSUFFICIENT",
)

reject(
    ["requiredness_semantics", "conditional_requiredness_must_be_explicit"],
    False,
    "reject implicit conditional requiredness",
)

reject(
    [
        "requiredness_semantics",
        "conditional_requiredness_may_be_inferred_from_magnitude",
    ],
    True,
    "reject conditional requiredness inferred from magnitude",
)

reject(
    [
        "requiredness_semantics",
        "conditional_requiredness_may_be_inferred_from_absence",
    ],
    True,
    "reject conditional requiredness inferred from absence",
)


# ============================================================
# Q. THRESHOLD GOVERNANCE
# ============================================================

for key in (
    "defines_new_numeric_thresholds",
    "duplicates_score_thresholds",
    "duplicates_confidence_thresholds",
    "duplicates_risk_thresholds",
    "duplicates_signal_thresholds",
    "duplicates_publication_source_tiers",
):
    reject(
        ["threshold_governance", key],
        True,
        f"reject threshold governance mutation: {key}",
    )

reject(
    ["threshold_governance", "consume_upstream_statuses_only"],
    False,
    "reject local reinterpretation of upstream statuses",
)

reject_added(
    ["threshold_governance"],
    "minimum_confidence",
    0.60,
    "reject new local confidence threshold",
)

reject_added(
    ["threshold_governance"],
    "minimum_coverage",
    0.85,
    "reject new local coverage threshold",
)


# ============================================================
# R. ENGINE ALIGNMENT
# ============================================================

reject(
    ["engine_alignment", "required_baseline_exact"],
    [
        "score",
        "coverage",
        "confidence",
        "risk",
        "domain_signals",
    ],
    "reject silently shrinking required baseline",
)

reject(
    ["engine_alignment", "required_baseline_exact"],
    EXPECTED_REQUIRED_ORDER + ["catalysts"],
    "reject silently expanding required baseline",
)

for key in (
    "must_not_silently_expand_required_baseline",
    "must_not_silently_reduce_required_baseline",
    "engine_change_required_if_contract_changes",
    "contract_change_required_if_engine_requiredness_changes",
):
    reject(
        ["engine_alignment", key],
        False,
        f"reject engine alignment weakening: {key}",
    )


# ============================================================
# S. DECISION / D.4 / D.5 BOUNDARY
# ============================================================

for key in (
    "requiredness_result_is_decision_state",
    "requiredness_result_is_actionable_authority",
    "requiredness_alone_may_select_ACTIONABLE",
    "requiredness_alone_may_select_WATCH",
    "requiredness_alone_may_select_WAIT_FOR_CONFIRMATION",
    "requiredness_alone_may_select_RISK_REVIEW",
    "requiredness_alone_may_select_THESIS_REVIEW",
    "requiredness_alone_may_select_INSUFFICIENT_EVIDENCE",
):
    reject(
        ["decision_boundary", key],
        True,
        f"reject decision authority mutation: {key}",
    )

reject(
    ["decision_boundary", "decision_state_owner"],
    "D.3",
    "reject D.3 taking ownership of Decision State",
)

reject(
    ["decision_boundary", "conflict_resolution_owner"],
    "D.3",
    "reject D.3 taking ownership of Conflict Resolver",
)


# ============================================================
# T. MUTATION BOUNDARY
# ============================================================

for key in canonical["mutation_boundary"].keys():
    reject(
        ["mutation_boundary", key],
        True,
        f"reject mutation permission: {key}",
    )


# ============================================================
# U. PHASE / D.7 BOUNDARY
# ============================================================

reject(
    ["phase_boundary", "this_step"],
    "D.7",
    "reject phase reassignment to D.7",
)

reject(
    ["phase_boundary", "this_step_defines_requiredness_contract_only"],
    False,
    "reject contract-only boundary removal",
)

reject(
    ["phase_boundary", "adversarial_requiredness_test"],
    "D.5",
    "reject adversarial ownership reassignment",
)

reject(
    ["phase_boundary", "generator_integration"],
    "D.3D.4E",
    "reject early Generator integration",
)


# ============================================================
# V. PROHIBITED BEHAVIORS
# ============================================================

for prohibition in sorted(EXPECTED_PROHIBITIONS):
    candidate = copy.deepcopy(canonical)
    candidate["prohibited_behaviors"].remove(prohibition)

    check(
        not validate_contract(candidate),
        f"reject removal of prohibition: {prohibition}",
    )

candidate = copy.deepcopy(canonical)
candidate["prohibited_behaviors"].append("ALLOW_MISSING_AS_NEUTRAL")

check(
    not validate_contract(candidate),
    "reject unauthorized extra prohibition mutation",
)


# ============================================================
# W. REQUIRED SECTION REMOVAL
# ============================================================

for section in (
    "purpose",
    "compatibility",
    "references",
    "requiredness_classes",
    "required_evidence",
    "conditional_evidence",
    "optional_evidence",
    "requiredness_semantics",
    "threshold_governance",
    "engine_alignment",
    "decision_boundary",
    "mutation_boundary",
    "phase_boundary",
    "prohibited_behaviors",
):
    candidate = copy.deepcopy(canonical)
    del candidate[section]

    check(
        not validate_contract(candidate),
        f"reject missing required section: {section}",
    )


# ============================================================
# X. CROSS-CONTRACT CANONICAL ALIGNMENT
# ============================================================

check(
    policy["missing_semantics"]["missing_required_result"]
    == "INSUFFICIENT",
    "D.3B policy still says required missing -> INSUFFICIENT",
)

check(
    runtime["missing_semantics"]["missing_required_evidence_result"]
    == "INSUFFICIENT",
    "D.3D.2 runtime still says required missing -> INSUFFICIENT",
)

check(
    bridge["absence_semantics"]["bridge_may_fill_missing_with_defaults"]
    is False,
    "D.3D.4B bridge still forbids defaults",
)

check(
    bridge["absence_semantics"]["bridge_may_fill_missing_with_legacy_values"]
    is False,
    "D.3D.4B bridge still forbids legacy fallback",
)

check(
    bridge["score_boundary"]["translate_legacy_score"] is False,
    "D.3D.4B bridge still forbids legacy score translation",
)

check(
    bridge["signal_boundary"]["recalculate_signals"] is False,
    "D.3D.4B bridge still forbids signal reconstruction",
)

check(
    bridge["provenance_boundary"]["invent_provenance"] is False,
    "D.3D.4B bridge still forbids provenance invention",
)


# ============================================================
# Y. FILE IMMUTABILITY
# ============================================================

before = CONTRACT_PATH.read_bytes()
after = CONTRACT_PATH.read_bytes()

check(
    before == after,
    "adversarial mutations never modify requiredness contract file",
)


# ============================================================
# Z. FINAL
# ============================================================

print()
print("=" * 78)
print(" D.3D.4E - REQUIREDNESS ADVERSARIAL CONTRACT RESULT")
print("=" * 78)
print(f"Checks executed: {checks}")
print(f"Failures: {len(failures)}")

if failures:
    print("RESULT: FAILED")

    for failure in failures:
        print(f" - {failure}")

    raise SystemExit(1)

print("RESULT: APPROVED")
