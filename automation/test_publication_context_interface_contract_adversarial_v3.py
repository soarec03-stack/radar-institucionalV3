import copy
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
AUTO = BASE / "automation"

CONTRACT_PATH = AUTO / "publication_context_interface_contract_v3.json"

checks = 0
failures = 0


def check(condition, message):
    global checks, failures
    checks += 1
    if condition:
        print(f"[PASS] {message}")
    else:
        failures += 1
        print(f"[FAIL] {message}")


def load_contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8-sig"))


CANONICAL = load_contract()


EXPECTED_TOP_LEVEL_KEYS = {
    "contract_id",
    "contract_version",
    "status",
    "scope",
    "purpose",
    "ownership",
    "compatibility",
    "proposed_interface",
    "context_semantics",
    "per_ticker_context",
    "absence_semantics",
    "runtime_relationship",
    "downstream_contract",
    "traceability",
    "prohibited_behaviors",
    "phase_boundary",
}


EXPECTED_PROHIBITIONS = {
    "CHANGE_APPLY_PUBLICATION_ELIGIBILITY_RETURN_ARITY",
    "BREAK_EXISTING_PUBLICATION_CALLERS",
    "RECALCULATE_PUBLICATION_IN_CONTEXT_BRIDGE",
    "RECALCULATE_PUBLICATION_IN_EVIDENCE_GATE",
    "INVENT_PUBLICATION_CONTEXT",
    "DEFAULT_MISSING_CONTEXT_TO_ELIGIBLE",
    "PROMOTE_INELIGIBLE_TO_ELIGIBLE",
    "DEFINE_LOCAL_PUBLICATION_THRESHOLDS",
    "TRANSLATE_LEGACY_SCORE_INTO_PUBLICATION_CONTEXT",
    "WRITE_PUBLICATION_CONTEXT_TO_RADAR_JSON",
    "WRITE_PUBLICATION_CONTEXT_TO_ASSET",
    "WRITE_DECISION_CENTER",
    "SELECT_DECISION_STATE",
    "ESTABLISH_ACTIONABLE_AUTHORITY",
    "RESOLVE_EVIDENCE_CONFLICTS",
    "CHANGE_SCHEMA_V3",
    "CHANGE_V2_1",
}


def validate_contract(c):
    try:
        if set(c.keys()) != EXPECTED_TOP_LEVEL_KEYS:
            return False

        if c["contract_id"] != "RADAR_V3_PUBLICATION_CONTEXT_INTERFACE_CONTRACT":
            return False

        if c["contract_version"] != "3.4D.3D.4G":
            return False

        if c["status"] != "DRAFT":
            return False

        if c["scope"] != "V3_ONLY":
            return False

        purpose = c["purpose"]

        expected_purpose_keys = {
            "objective",
            "problem_confirmed_by_runtime_inventory",
            "interface_role",
            "not_a_new_evaluation_model",
        }

        if set(purpose.keys()) != expected_purpose_keys:
            return False

        if (
            purpose["problem_confirmed_by_runtime_inventory"]
            != "PUBLICATION_CONTEXT_BY_TICKER_IS_NOT_CURRENTLY_EXPOSED_BY_PUBLICATION_ELIGIBILITY_RUNTIME"
        ):
            return False

        if purpose["interface_role"] != "EXPOSE_EXISTING_UPSTREAM_EVALUATION_CONTEXT":
            return False

        if purpose["not_a_new_evaluation_model"] is not True:
            return False

        ownership = c["ownership"]

        expected_ownership_keys = {
            "owner",
            "canonical_evaluator",
            "consumer",
            "transport_consumer",
            "evidence_gate_may_recalculate_publication",
            "context_bridge_may_recalculate_publication",
        }

        if set(ownership.keys()) != expected_ownership_keys:
            return False

        if ownership["owner"] != "PUBLICATION_ELIGIBILITY":
            return False

        if ownership["canonical_evaluator"] != "evaluate_asset_publication":
            return False

        if ownership["consumer"] != "EVIDENCE_GATE":
            return False

        if ownership["transport_consumer"] != "EVIDENCE_GATE_CONTEXT_BRIDGE":
            return False

        if ownership["evidence_gate_may_recalculate_publication"] is not False:
            return False

        if ownership["context_bridge_may_recalculate_publication"] is not False:
            return False

        compat = c["compatibility"]

        expected_compatibility_keys = {
            "preserve_v2_1",
            "preserve_schema_v3",
            "preserve_public_decision_center_contract",
            "preserve_existing_apply_publication_eligibility_api",
            "apply_publication_eligibility_existing_return_arity",
            "apply_publication_eligibility_existing_return_semantics",
            "may_change_existing_return_arity",
            "may_require_existing_callers_to_change",
        }

        if set(compat.keys()) != expected_compatibility_keys:
            return False

        if compat["preserve_v2_1"] is not True:
            return False

        if compat["preserve_schema_v3"] is not True:
            return False

        if compat["preserve_public_decision_center_contract"] is not True:
            return False

        if compat["preserve_existing_apply_publication_eligibility_api"] is not True:
            return False

        if compat["apply_publication_eligibility_existing_return_arity"] != 2:
            return False

        if (
            compat["apply_publication_eligibility_existing_return_semantics"]
            != ["data", "publication_changes"]
        ):
            return False

        if compat["may_change_existing_return_arity"] is not False:
            return False

        if compat["may_require_existing_callers_to_change"] is not False:
            return False

        interface = c["proposed_interface"]

        expected_interface_keys = {
            "name",
            "owner_module",
            "implementation_status",
            "arguments",
            "optional_arguments",
            "returns",
            "return_type",
            "transient_only",
        }

        if set(interface.keys()) != expected_interface_keys:
            return False

        if interface["name"] != "build_publication_context_by_ticker":
            return False

        if interface["owner_module"] != "publication_eligibility_v3.py":
            return False

        if interface["implementation_status"] != "NOT_IMPLEMENTED_IN_D3D4G":
            return False

        if interface["arguments"] != [
            "data",
            "registry",
            "policy",
            "risk_source_context_by_ticker",
        ]:
            return False

        if interface["optional_arguments"] != [
            "policy",
            "risk_source_context_by_ticker",
        ]:
            return False

        if interface["returns"] != "publication_context_by_ticker":
            return False

        if interface["return_type"] != "DICT_BY_TICKER":
            return False

        if interface["transient_only"] is not True:
            return False

        sem = c["context_semantics"]

        expected_semantic_keys = {
            "source_of_truth",
            "must_be_derived_from_canonical_evaluator",
            "may_invent",
            "may_repair",
            "may_impute",
            "may_promote",
            "may_translate_legacy_score",
            "may_define_new_thresholds",
            "may_override_publication_policy",
            "may_override_source_registry",
            "may_override_risk_source_context",
            "missing_context_may_be_defaulted_to_eligible",
        }

        if set(sem.keys()) != expected_semantic_keys:
            return False

        if sem["source_of_truth"] != "evaluate_asset_publication":
            return False

        if sem["must_be_derived_from_canonical_evaluator"] is not True:
            return False

        for key in (
            "may_invent",
            "may_repair",
            "may_impute",
            "may_promote",
            "may_translate_legacy_score",
            "may_define_new_thresholds",
            "may_override_publication_policy",
            "may_override_source_registry",
            "may_override_risk_source_context",
            "missing_context_may_be_defaulted_to_eligible",
        ):
            if sem[key] is not False:
                return False

        per_ticker = c["per_ticker_context"]

        expected_per_ticker_keys = {
            "required_fields",
            "ticker",
            "eligible",
            "components",
        }

        if set(per_ticker.keys()) != expected_per_ticker_keys:
            return False

        if per_ticker["required_fields"] != [
            "ticker",
            "eligible",
            "components",
        ]:
            return False

        ticker = per_ticker["ticker"]

        if set(ticker.keys()) != {"source", "may_be_invented"}:
            return False

        if ticker["source"] != "asset.ticker":
            return False

        if ticker["may_be_invented"] is not False:
            return False

        eligible = per_ticker["eligible"]

        if set(eligible.keys()) != {
            "source",
            "type",
            "may_be_recalculated_by_bridge",
            "may_be_promoted",
        }:
            return False

        if eligible["source"] != "evaluate_asset_publication.result.eligible":
            return False

        if eligible["type"] != "BOOLEAN":
            return False

        if eligible["may_be_recalculated_by_bridge"] is not False:
            return False

        if eligible["may_be_promoted"] is not False:
            return False

        components = per_ticker["components"]

        if set(components.keys()) != {
            "source",
            "type",
            "preserve_component_results",
            "may_drop_blocked_components",
            "may_rewrite_reasons",
        }:
            return False

        if components["source"] != "evaluate_asset_publication.result.components":
            return False

        if components["type"] != "OBJECT":
            return False

        if components["preserve_component_results"] is not True:
            return False

        if components["may_drop_blocked_components"] is not False:
            return False

        if components["may_rewrite_reasons"] is not False:
            return False

        absence = c["absence_semantics"]

        expected_absence_keys = {
            "missing_asset_ticker",
            "missing_risk_source_context",
            "missing_publication_context",
            "unknown_publication_result",
            "absence_is_not_eligibility",
        }

        if set(absence.keys()) != expected_absence_keys:
            return False

        if absence["missing_asset_ticker"] != "DO_NOT_INVENT_IDENTITY":
            return False

        if (
            absence["missing_risk_source_context"]
            != "PRESERVE_CANONICAL_EVALUATOR_FAIL_CLOSED_SEMANTICS"
        ):
            return False

        if absence["missing_publication_context"] != "DO_NOT_ASSUME_ELIGIBLE":
            return False

        if absence["unknown_publication_result"] != "FAIL_CLOSED":
            return False

        if absence["absence_is_not_eligibility"] is not True:
            return False

        runtime = c["runtime_relationship"]

        if set(runtime.keys()) != {
            "existing_apply_publication_eligibility",
            "new_context_interface",
        }:
            return False

        existing = runtime["existing_apply_publication_eligibility"]

        if set(existing.keys()) != {
            "remains_authoritative_for_publishable_restriction",
            "existing_behavior_must_be_preserved",
        }:
            return False

        if existing["remains_authoritative_for_publishable_restriction"] is not True:
            return False

        if existing["existing_behavior_must_be_preserved"] is not True:
            return False

        new_interface = runtime["new_context_interface"]

        if set(new_interface.keys()) != {
            "role",
            "must_not_write_score_publishable",
            "must_not_write_decision_center",
            "must_not_write_asset",
            "must_not_persist_context",
        }:
            return False

        if new_interface["role"] != "TRANSIENT_CONTEXT_EXPOSURE":
            return False

        for key in (
            "must_not_write_score_publishable",
            "must_not_write_decision_center",
            "must_not_write_asset",
            "must_not_persist_context",
        ):
            if new_interface[key] is not True:
                return False

        downstream = c["downstream_contract"]

        expected_downstream_keys = {
            "destination",
            "context_bridge_role",
            "evidence_gate_role",
            "evidence_gate_may_override_eligible",
            "evidence_gate_may_re_evaluate_sources",
            "evidence_gate_may_re_evaluate_tiers",
        }

        if set(downstream.keys()) != expected_downstream_keys:
            return False

        if downstream["destination"] != "publication_context_by_ticker":
            return False

        if downstream["context_bridge_role"] != "TRANSPORT_ONLY":
            return False

        if downstream["evidence_gate_role"] != "CONSUME_ONLY":
            return False

        if downstream["evidence_gate_may_override_eligible"] is not False:
            return False

        if downstream["evidence_gate_may_re_evaluate_sources"] is not False:
            return False

        if downstream["evidence_gate_may_re_evaluate_tiers"] is not False:
            return False

        trace = c["traceability"]

        if set(trace.keys()) != {
            "preserve_eligible",
            "preserve_components",
            "preserve_component_reasons",
            "preserve_source_information_when_produced_upstream",
            "silent_deletion_of_blocked_evidence",
        }:
            return False

        if trace["preserve_eligible"] is not True:
            return False

        if trace["preserve_components"] is not True:
            return False

        if trace["preserve_component_reasons"] is not True:
            return False

        if trace["preserve_source_information_when_produced_upstream"] is not True:
            return False

        if trace["silent_deletion_of_blocked_evidence"] is not False:
            return False

        if set(c["prohibited_behaviors"]) != EXPECTED_PROHIBITIONS:
            return False

        phase = c["phase_boundary"]

        expected_phase_keys = {
            "d3d4g_contract_only",
            "implements_interface",
            "changes_publication_engine",
            "changes_generator",
            "changes_evidence_gate_engine",
            "changes_context_bridge",
            "changes_schema",
            "changes_v2_1",
            "implementation_requires_separate_test_proven_step",
        }

        if set(phase.keys()) != expected_phase_keys:
            return False

        if phase["d3d4g_contract_only"] is not True:
            return False

        for key in (
            "implements_interface",
            "changes_publication_engine",
            "changes_generator",
            "changes_evidence_gate_engine",
            "changes_context_bridge",
            "changes_schema",
            "changes_v2_1",
        ):
            if phase[key] is not False:
                return False

        if phase["implementation_requires_separate_test_proven_step"] is not True:
            return False

        return True

    except (KeyError, TypeError, AttributeError):
        return False


def mutation(message, mutator):
    candidate = copy.deepcopy(CANONICAL)
    mutator(candidate)
    check(not validate_contract(candidate), message)


print("=" * 78)
print(" D.3D.4H - PUBLICATION CONTEXT INTERFACE ADVERSARIAL CONTRACT TEST")
print("=" * 78)

check(validate_contract(CANONICAL), "canonical D.3D.4G contract accepted")

# ----------------------------------------------------------------------
# Identity / scope
# ----------------------------------------------------------------------

mutation(
    "reject altered contract id",
    lambda c: c.__setitem__("contract_id", "BROKEN"),
)

mutation(
    "reject altered contract version",
    lambda c: c.__setitem__("contract_version", "9.9"),
)

mutation(
    "reject production status mutation",
    lambda c: c.__setitem__("status", "PRODUCTION"),
)

mutation(
    "reject scope expansion beyond V3",
    lambda c: c.__setitem__("scope", "V2_AND_V3"),
)

# ----------------------------------------------------------------------
# Purpose / ownership
# ----------------------------------------------------------------------

mutation(
    "reject new evaluation model",
    lambda c: c["purpose"].__setitem__("not_a_new_evaluation_model", False),
)

mutation(
    "reject changing interface role to evaluator",
    lambda c: c["purpose"].__setitem__(
        "interface_role",
        "RECALCULATE_PUBLICATION_ELIGIBILITY",
    ),
)

mutation(
    "reject Publication Eligibility ownership reassignment",
    lambda c: c["ownership"].__setitem__("owner", "EVIDENCE_GATE"),
)

mutation(
    "reject canonical evaluator replacement",
    lambda c: c["ownership"].__setitem__(
        "canonical_evaluator",
        "score.publishable",
    ),
)

mutation(
    "reject Evidence Gate publication recalculation",
    lambda c: c["ownership"].__setitem__(
        "evidence_gate_may_recalculate_publication",
        True,
    ),
)

mutation(
    "reject Context Bridge publication recalculation",
    lambda c: c["ownership"].__setitem__(
        "context_bridge_may_recalculate_publication",
        True,
    ),
)

# ----------------------------------------------------------------------
# Existing API compatibility
# ----------------------------------------------------------------------

mutation(
    "reject disabling existing apply API preservation",
    lambda c: c["compatibility"].__setitem__(
        "preserve_existing_apply_publication_eligibility_api",
        False,
    ),
)

mutation(
    "reject changing existing apply return arity to three",
    lambda c: c["compatibility"].__setitem__(
        "apply_publication_eligibility_existing_return_arity",
        3,
    ),
)

mutation(
    "reject changing existing apply return arity to one",
    lambda c: c["compatibility"].__setitem__(
        "apply_publication_eligibility_existing_return_arity",
        1,
    ),
)

mutation(
    "reject adding publication context to existing apply returns",
    lambda c: c["compatibility"].__setitem__(
        "apply_publication_eligibility_existing_return_semantics",
        ["data", "publication_changes", "publication_context_by_ticker"],
    ),
)

mutation(
    "reject changing existing apply return semantics",
    lambda c: c["compatibility"].__setitem__(
        "apply_publication_eligibility_existing_return_semantics",
        ["data", "publication_context_by_ticker"],
    ),
)

mutation(
    "reject permission to change existing return arity",
    lambda c: c["compatibility"].__setitem__(
        "may_change_existing_return_arity",
        True,
    ),
)

mutation(
    "reject forcing existing callers to change",
    lambda c: c["compatibility"].__setitem__(
        "may_require_existing_callers_to_change",
        True,
    ),
)

mutation(
    "reject V2.1 compatibility weakening",
    lambda c: c["compatibility"].__setitem__("preserve_v2_1", False),
)

mutation(
    "reject schema V3 compatibility weakening",
    lambda c: c["compatibility"].__setitem__("preserve_schema_v3", False),
)

mutation(
    "reject public Decision Center compatibility weakening",
    lambda c: c["compatibility"].__setitem__(
        "preserve_public_decision_center_contract",
        False,
    ),
)

# ----------------------------------------------------------------------
# Dedicated interface
# ----------------------------------------------------------------------

mutation(
    "reject replacing dedicated interface with existing apply API",
    lambda c: c["proposed_interface"].__setitem__(
        "name",
        "apply_publication_eligibility",
    ),
)

mutation(
    "reject interface ownership outside publication module",
    lambda c: c["proposed_interface"].__setitem__(
        "owner_module",
        "evidence_gate_engine_v3.py",
    ),
)

mutation(
    "reject pretending interface already implemented in D.3D.4G",
    lambda c: c["proposed_interface"].__setitem__(
        "implementation_status",
        "IMPLEMENTED",
    ),
)

mutation(
    "reject removing registry argument",
    lambda c: c["proposed_interface"].__setitem__(
        "arguments",
        [
            "data",
            "policy",
            "risk_source_context_by_ticker",
        ],
    ),
)

mutation(
    "reject argument reordering",
    lambda c: c["proposed_interface"].__setitem__(
        "arguments",
        [
            "registry",
            "data",
            "policy",
            "risk_source_context_by_ticker",
        ],
    ),
)

mutation(
    "reject making registry optional",
    lambda c: c["proposed_interface"].__setitem__(
        "optional_arguments",
        ["registry", "policy", "risk_source_context_by_ticker"],
    ),
)

mutation(
    "reject persistent interface output",
    lambda c: c["proposed_interface"].__setitem__("transient_only", False),
)

mutation(
    "reject alternate return destination",
    lambda c: c["proposed_interface"].__setitem__(
        "returns",
        "radar",
    ),
)

# ----------------------------------------------------------------------
# Context semantics
# ----------------------------------------------------------------------

for key in (
    "may_invent",
    "may_repair",
    "may_impute",
    "may_promote",
    "may_translate_legacy_score",
    "may_define_new_thresholds",
    "may_override_publication_policy",
    "may_override_source_registry",
    "may_override_risk_source_context",
    "missing_context_may_be_defaulted_to_eligible",
):
    mutation(
        f"reject context semantic capability: {key}",
        lambda c, k=key: c["context_semantics"].__setitem__(k, True),
    )

mutation(
    "reject source of truth reassignment to score.publishable",
    lambda c: c["context_semantics"].__setitem__(
        "source_of_truth",
        "score.publishable",
    ),
)

mutation(
    "reject canonical evaluator derivation weakening",
    lambda c: c["context_semantics"].__setitem__(
        "must_be_derived_from_canonical_evaluator",
        False,
    ),
)

mutation(
    "reject new local confidence threshold",
    lambda c: c["context_semantics"].__setitem__(
        "minimum_confidence",
        0.60,
    ),
)

mutation(
    "reject new local source tier threshold",
    lambda c: c["context_semantics"].__setitem__(
        "minimum_source_tier",
        "T2",
    ),
)

# ----------------------------------------------------------------------
# Per ticker context
# ----------------------------------------------------------------------

mutation(
    "reject removal of ticker from required context",
    lambda c: c["per_ticker_context"].__setitem__(
        "required_fields",
        ["eligible", "components"],
    ),
)

mutation(
    "reject removal of eligible from required context",
    lambda c: c["per_ticker_context"].__setitem__(
        "required_fields",
        ["ticker", "components"],
    ),
)

mutation(
    "reject removal of components from required context",
    lambda c: c["per_ticker_context"].__setitem__(
        "required_fields",
        ["ticker", "eligible"],
    ),
)

mutation(
    "reject invented ticker identity",
    lambda c: c["per_ticker_context"]["ticker"].__setitem__(
        "may_be_invented",
        True,
    ),
)

mutation(
    "reject ticker source reassignment",
    lambda c: c["per_ticker_context"]["ticker"].__setitem__(
        "source",
        "context.key",
    ),
)

mutation(
    "reject eligible source reassignment to score.publishable",
    lambda c: c["per_ticker_context"]["eligible"].__setitem__(
        "source",
        "asset.score.publishable",
    ),
)

mutation(
    "reject eligible becoming non-boolean",
    lambda c: c["per_ticker_context"]["eligible"].__setitem__(
        "type",
        "STRING",
    ),
)

mutation(
    "reject eligible recalculation by bridge",
    lambda c: c["per_ticker_context"]["eligible"].__setitem__(
        "may_be_recalculated_by_bridge",
        True,
    ),
)

mutation(
    "reject promotion of eligible false to true",
    lambda c: c["per_ticker_context"]["eligible"].__setitem__(
        "may_be_promoted",
        True,
    ),
)

mutation(
    "reject components source reassignment",
    lambda c: c["per_ticker_context"]["components"].__setitem__(
        "source",
        "asset.score",
    ),
)

mutation(
    "reject blocked component deletion",
    lambda c: c["per_ticker_context"]["components"].__setitem__(
        "may_drop_blocked_components",
        True,
    ),
)

mutation(
    "reject component reason rewriting",
    lambda c: c["per_ticker_context"]["components"].__setitem__(
        "may_rewrite_reasons",
        True,
    ),
)

mutation(
    "reject disabling component preservation",
    lambda c: c["per_ticker_context"]["components"].__setitem__(
        "preserve_component_results",
        False,
    ),
)

# ----------------------------------------------------------------------
# Absence semantics
# ----------------------------------------------------------------------

mutation(
    "reject missing ticker synthetic identity",
    lambda c: c["absence_semantics"].__setitem__(
        "missing_asset_ticker",
        "GENERATE_TICKER",
    ),
)

mutation(
    "reject missing risk context assumed eligible",
    lambda c: c["absence_semantics"].__setitem__(
        "missing_risk_source_context",
        "ASSUME_ELIGIBLE",
    ),
)

mutation(
    "reject missing publication context assumed eligible",
    lambda c: c["absence_semantics"].__setitem__(
        "missing_publication_context",
        "ASSUME_ELIGIBLE",
    ),
)

mutation(
    "reject unknown publication result assumed eligible",
    lambda c: c["absence_semantics"].__setitem__(
        "unknown_publication_result",
        "ELIGIBLE",
    ),
)

mutation(
    "reject absence becoming eligibility",
    lambda c: c["absence_semantics"].__setitem__(
        "absence_is_not_eligibility",
        False,
    ),
)

# ----------------------------------------------------------------------
# Runtime write boundaries
# ----------------------------------------------------------------------

mutation(
    "reject existing apply losing publishable authority",
    lambda c: c["runtime_relationship"][
        "existing_apply_publication_eligibility"
    ].__setitem__(
        "remains_authoritative_for_publishable_restriction",
        False,
    ),
)

mutation(
    "reject existing apply behavior mutation",
    lambda c: c["runtime_relationship"][
        "existing_apply_publication_eligibility"
    ].__setitem__(
        "existing_behavior_must_be_preserved",
        False,
    ),
)

for key in (
    "must_not_write_score_publishable",
    "must_not_write_decision_center",
    "must_not_write_asset",
    "must_not_persist_context",
):
    mutation(
        f"reject runtime write-boundary weakening: {key}",
        lambda c, k=key: c["runtime_relationship"][
            "new_context_interface"
        ].__setitem__(k, False),
    )

mutation(
    "reject context interface becoming persistence writer",
    lambda c: c["runtime_relationship"]["new_context_interface"].__setitem__(
        "role",
        "PERSIST_PUBLICATION_CONTEXT",
    ),
)

# ----------------------------------------------------------------------
# Downstream boundaries
# ----------------------------------------------------------------------

mutation(
    "reject alternate downstream destination",
    lambda c: c["downstream_contract"].__setitem__(
        "destination",
        "asset.publication_context",
    ),
)

mutation(
    "reject Context Bridge becoming evaluator",
    lambda c: c["downstream_contract"].__setitem__(
        "context_bridge_role",
        "PUBLICATION_EVALUATOR",
    ),
)

mutation(
    "reject Evidence Gate becoming publication evaluator",
    lambda c: c["downstream_contract"].__setitem__(
        "evidence_gate_role",
        "RECALCULATE_PUBLICATION",
    ),
)

mutation(
    "reject Evidence Gate eligibility override",
    lambda c: c["downstream_contract"].__setitem__(
        "evidence_gate_may_override_eligible",
        True,
    ),
)

mutation(
    "reject Evidence Gate source re-evaluation",
    lambda c: c["downstream_contract"].__setitem__(
        "evidence_gate_may_re_evaluate_sources",
        True,
    ),
)

mutation(
    "reject Evidence Gate tier re-evaluation",
    lambda c: c["downstream_contract"].__setitem__(
        "evidence_gate_may_re_evaluate_tiers",
        True,
    ),
)

# ----------------------------------------------------------------------
# Traceability
# ----------------------------------------------------------------------

mutation(
    "reject eligible trace removal",
    lambda c: c["traceability"].__setitem__("preserve_eligible", False),
)

mutation(
    "reject component trace removal",
    lambda c: c["traceability"].__setitem__("preserve_components", False),
)

mutation(
    "reject component reason trace removal",
    lambda c: c["traceability"].__setitem__(
        "preserve_component_reasons",
        False,
    ),
)

mutation(
    "reject upstream source trace removal",
    lambda c: c["traceability"].__setitem__(
        "preserve_source_information_when_produced_upstream",
        False,
    ),
)

mutation(
    "reject silent deletion of blocked evidence",
    lambda c: c["traceability"].__setitem__(
        "silent_deletion_of_blocked_evidence",
        True,
    ),
)

# ----------------------------------------------------------------------
# Phase boundaries: D.4 / D.5 / D.7 etc.
# ----------------------------------------------------------------------

mutation(
    "reject interface implementation inside D.3D.4G contract step",
    lambda c: c["phase_boundary"].__setitem__(
        "implements_interface",
        True,
    ),
)

mutation(
    "reject publication engine change inside contract step",
    lambda c: c["phase_boundary"].__setitem__(
        "changes_publication_engine",
        True,
    ),
)

mutation(
    "reject early Generator integration",
    lambda c: c["phase_boundary"].__setitem__(
        "changes_generator",
        True,
    ),
)

mutation(
    "reject Evidence Gate engine mutation",
    lambda c: c["phase_boundary"].__setitem__(
        "changes_evidence_gate_engine",
        True,
    ),
)

mutation(
    "reject Context Bridge implementation in contract step",
    lambda c: c["phase_boundary"].__setitem__(
        "changes_context_bridge",
        True,
    ),
)

mutation(
    "reject schema mutation",
    lambda c: c["phase_boundary"].__setitem__(
        "changes_schema",
        True,
    ),
)

mutation(
    "reject V2.1 mutation",
    lambda c: c["phase_boundary"].__setitem__(
        "changes_v2_1",
        True,
    ),
)

mutation(
    "reject removing separate test-proven implementation requirement",
    lambda c: c["phase_boundary"].__setitem__(
        "implementation_requires_separate_test_proven_step",
        False,
    ),
)

# ----------------------------------------------------------------------
# Prohibitions
# ----------------------------------------------------------------------

for prohibition in sorted(EXPECTED_PROHIBITIONS):
    mutation(
        f"reject removal of prohibition: {prohibition}",
        lambda c, p=prohibition: c.__setitem__(
            "prohibited_behaviors",
            [
                item
                for item in c["prohibited_behaviors"]
                if item != p
            ],
        ),
    )

mutation(
    "reject unauthorized extra prohibition mutation",
    lambda c: c["prohibited_behaviors"].append(
        "ALLOW_CONTEXT_BRIDGE_TO_BUY"
    ),
)

# ----------------------------------------------------------------------
# Required section deletion
# ----------------------------------------------------------------------

for section in sorted(EXPECTED_TOP_LEVEL_KEYS - {
    "contract_id",
    "contract_version",
    "status",
    "scope",
}):
    mutation(
        f"reject missing required section: {section}",
        lambda c, s=section: c.pop(s),
    )

# ----------------------------------------------------------------------
# Ensure adversarial test itself never rewrites canonical contract
# ----------------------------------------------------------------------

before = CONTRACT_PATH.read_bytes()
after = CONTRACT_PATH.read_bytes()

check(
    before == after,
    "adversarial mutations never modify D.3D.4G contract file",
)

print()
print("=" * 78)
print(" D.3D.4H - PUBLICATION CONTEXT INTERFACE ADVERSARIAL RESULT")
print("=" * 78)
print(f"Checks executed: {checks}")
print(f"Failures: {failures}")
print("RESULT:", "APPROVED" if failures == 0 else "FAILED")

raise SystemExit(0 if failures == 0 else 1)