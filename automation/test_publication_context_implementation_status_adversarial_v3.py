import copy
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
AUTO = BASE / "automation"

CONTRACT_PATH = AUTO / "publication_context_implementation_status_v3.json"

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


canonical = json.loads(
    CONTRACT_PATH.read_text(encoding="utf-8-sig")
)


EXPECTED_PROHIBITIONS = {
    "REWRITE_D3D4G_HISTORY",
    "CHANGE_APPLY_PUBLICATION_ELIGIBILITY_RETURN_ARITY",
    "BREAK_EXISTING_PUBLICATION_CALLERS",
    "RECALCULATE_ELIGIBILITY_OUTSIDE_CANONICAL_EVALUATOR",
    "PROMOTE_PUBLICATION_INELIGIBLE",
    "INVENT_PUBLICATION_CONTEXT",
    "DEFAULT_MISSING_CONTEXT_TO_ELIGIBLE",
    "DEFINE_LOCAL_PUBLICATION_THRESHOLDS",
    "DROP_BLOCKED_COMPONENTS",
    "REWRITE_COMPONENT_REASONS",
    "PERSIST_PUBLICATION_CONTEXT",
    "MUTATE_RADAR",
    "MUTATE_ASSET",
    "WRITE_DECISION_CENTER",
    "MODIFY_GENERATOR",
    "MODIFY_SCHEMA_V3",
    "MODIFY_V2_1",
    "RESOLVE_CONFLICT",
    "SELECT_DECISION_STATE",
    "ESTABLISH_ACTIONABLE_AUTHORITY",
}


def valid(c):
    try:
        if c["contract_id"] != "RADAR_V3_PUBLICATION_CONTEXT_IMPLEMENTATION_STATUS":
            return False

        if c["contract_version"] != "3.4D.3D.4J.1":
            return False

        if c["status"] != "HOMOLOGATED":
            return False

        if c["scope"] != "V3_ONLY":
            return False

        purpose = c["purpose"]

        if purpose["records_implementation_status"] is not True:
            return False

        for key in (
            "replaces_historical_contract",
            "modifies_interface_semantics",
            "implements_context_bridge",
            "integrates_generator",
            "modifies_schema_v3",
            "modifies_v2_1",
            "writes_decision_center",
        ):
            if purpose[key] is not False:
                return False

        trace = c["historical_trace"]

        if trace["interface_contract_phase"] != "D.3D.4G":
            return False

        if trace["interface_contract_status_at_that_time"] != "PROPOSED_NOT_IMPLEMENTED":
            return False

        if trace["adversarial_contract_phase"] != "D.3D.4H":
            return False

        if trace["implementation_phase"] != "D.3D.4I":
            return False

        if trace["current_status"] != "IMPLEMENTED_AND_HOMOLOGATED":
            return False

        if trace["historical_contract_must_not_be_rewritten"] is not True:
            return False

        impl = c["implementation"]

        if impl["owner_module"] != "automation/publication_eligibility_v3.py":
            return False

        if impl["function"] != "build_publication_context_by_ticker":
            return False

        for key in (
            "implemented",
            "homologated",
            "transient_only",
        ):
            if impl[key] is not True:
                return False

        for key in (
            "persists_output",
            "mutates_radar",
            "mutates_asset",
            "writes_score_publishable",
            "writes_decision_center",
        ):
            if impl[key] is not False:
                return False

        api = c["canonical_api"]

        if api["function"] != "build_publication_context_by_ticker":
            return False

        if api["arguments"] != [
            "data",
            "registry",
            "policy",
            "risk_source_context_by_ticker",
        ]:
            return False

        if api["optional_arguments"] != [
            "policy",
            "risk_source_context_by_ticker",
        ]:
            return False

        if api["return_type"] != "DICT_BY_TICKER":
            return False

        if api["required_per_ticker_fields"] != [
            "ticker",
            "eligible",
            "components",
        ]:
            return False

        source = c["source_of_truth"]

        if source["canonical_evaluator"] != "evaluate_asset_publication":
            return False

        for key in (
            "builder_may_recalculate_eligibility_independently",
            "builder_may_override_evaluator",
            "builder_may_promote_ineligible",
            "builder_may_invent_missing_context",
            "builder_may_define_local_thresholds",
            "builder_may_remove_blocked_components",
            "builder_may_rewrite_component_reasons",
        ):
            if source[key] is not False:
                return False

        compat = c["backward_compatibility"]

        if compat["apply_publication_eligibility_api_preserved"] is not True:
            return False

        if compat["apply_publication_eligibility_return_arity"] != 2:
            return False

        for key in (
            "existing_callers_require_change",
            "generator_modified",
            "schema_v3_modified",
            "v2_1_modified",
            "public_output_modified",
        ):
            if compat[key] is not False:
                return False

        runtime = c["runtime_boundaries"]

        for key in (
            "context_bridge_implemented",
            "generator_integration_implemented",
            "evidence_gate_integration_implemented",
            "decision_state_selection_implemented",
            "conflict_resolution_implemented",
            "actionable_authority_established",
        ):
            if runtime[key] is not False:
                return False

        phases = c["phase_ownership"]

        if phases != {
            "context_bridge": "FUTURE_CONTROLLED_STEP",
            "conflict_resolver": "D.4",
            "decision_state_engine": "D.5",
            "traceability": "D.6",
            "generator_integration": "D.7",
        }:
            return False

        if set(c["prohibited_behaviors"]) != EXPECTED_PROHIBITIONS:
            return False

        return True

    except (KeyError, TypeError):
        return False


print("=" * 78)
print(" D.3D.4J.2 - IMPLEMENTATION STATUS ADVERSARIAL")
print("=" * 78)

check(valid(canonical), "canonical J.1 contract accepted")


def reject(mutator, message):
    candidate = copy.deepcopy(canonical)
    mutator(candidate)
    check(not valid(candidate), message)


# Identity / status corruption
reject(
    lambda c: c.__setitem__("contract_id", "BROKEN"),
    "reject altered contract id",
)

reject(
    lambda c: c.__setitem__("contract_version", "BROKEN"),
    "reject altered contract version",
)

reject(
    lambda c: c.__setitem__("status", "DRAFT"),
    "reject homologated status downgrade",
)

reject(
    lambda c: c.__setitem__("scope", "V2_AND_V3"),
    "reject scope expansion beyond V3",
)


# Historical integrity
reject(
    lambda c: c["purpose"].__setitem__(
        "replaces_historical_contract", True
    ),
    "reject replacement of historical G contract",
)

reject(
    lambda c: c["historical_trace"].__setitem__(
        "interface_contract_phase", "D.3D.4J"
    ),
    "reject rewriting historical interface phase",
)

reject(
    lambda c: c["historical_trace"].__setitem__(
        "interface_contract_status_at_that_time",
        "IMPLEMENTED_AND_HOMOLOGATED",
    ),
    "reject rewriting historical G state",
)

reject(
    lambda c: c["historical_trace"].__setitem__(
        "historical_contract_must_not_be_rewritten", False
    ),
    "reject permission to rewrite historical contract",
)


# Implementation boundaries
for key in (
    "persists_output",
    "mutates_radar",
    "mutates_asset",
    "writes_score_publishable",
    "writes_decision_center",
):
    reject(
        lambda c, k=key: c["implementation"].__setitem__(k, True),
        f"reject implementation permission: {key}",
    )


# Canonical API corruption
reject(
    lambda c: c["canonical_api"].__setitem__(
        "function", "apply_publication_eligibility"
    ),
    "reject replacing dedicated builder API",
)

reject(
    lambda c: c["canonical_api"].__setitem__(
        "arguments",
        ["data", "registry"],
    ),
    "reject canonical argument removal",
)

reject(
    lambda c: c["canonical_api"].__setitem__(
        "return_type", "PERSISTED_RADAR_FIELD"
    ),
    "reject persistent return type",
)

reject(
    lambda c: c["canonical_api"].__setitem__(
        "required_per_ticker_fields",
        ["ticker", "eligible"],
    ),
    "reject dropping components from context",
)


# Source-of-truth corruption
for key in (
    "builder_may_recalculate_eligibility_independently",
    "builder_may_override_evaluator",
    "builder_may_promote_ineligible",
    "builder_may_invent_missing_context",
    "builder_may_define_local_thresholds",
    "builder_may_remove_blocked_components",
    "builder_may_rewrite_component_reasons",
):
    reject(
        lambda c, k=key: c["source_of_truth"].__setitem__(k, True),
        f"reject source-of-truth permission: {key}",
    )

reject(
    lambda c: c["source_of_truth"].__setitem__(
        "canonical_evaluator",
        "LOCAL_RECALCULATION",
    ),
    "reject canonical evaluator reassignment",
)


# Existing API / caller compatibility
reject(
    lambda c: c["backward_compatibility"].__setitem__(
        "apply_publication_eligibility_api_preserved", False
    ),
    "reject breaking existing apply API",
)

reject(
    lambda c: c["backward_compatibility"].__setitem__(
        "apply_publication_eligibility_return_arity", 3
    ),
    "reject apply return arity change",
)

for key in (
    "existing_callers_require_change",
    "generator_modified",
    "schema_v3_modified",
    "v2_1_modified",
    "public_output_modified",
):
    reject(
        lambda c, k=key: c["backward_compatibility"].__setitem__(k, True),
        f"reject compatibility mutation: {key}",
    )


# Runtime scope creep
for key in (
    "context_bridge_implemented",
    "generator_integration_implemented",
    "evidence_gate_integration_implemented",
    "decision_state_selection_implemented",
    "conflict_resolution_implemented",
    "actionable_authority_established",
):
    reject(
        lambda c, k=key: c["runtime_boundaries"].__setitem__(k, True),
        f"reject runtime scope creep: {key}",
    )


# Phase ownership corruption
reject(
    lambda c: c["phase_ownership"].__setitem__(
        "conflict_resolver", "D.3"
    ),
    "reject D.3 taking ownership of Conflict Resolver",
)

reject(
    lambda c: c["phase_ownership"].__setitem__(
        "decision_state_engine", "D.3"
    ),
    "reject D.3 taking ownership of Decision State",
)

reject(
    lambda c: c["phase_ownership"].__setitem__(
        "generator_integration", "D.3"
    ),
    "reject early Generator integration ownership",
)


# Prohibition removal
for prohibition in sorted(EXPECTED_PROHIBITIONS):
    reject(
        lambda c, p=prohibition: c.__setitem__(
            "prohibited_behaviors",
            [
                x for x in c["prohibited_behaviors"]
                if x != p
            ],
        ),
        f"reject removal of prohibition: {prohibition}",
    )


# Required section removal
for section in (
    "purpose",
    "historical_trace",
    "implementation",
    "canonical_api",
    "source_of_truth",
    "backward_compatibility",
    "runtime_boundaries",
    "phase_ownership",
    "prohibited_behaviors",
):
    reject(
        lambda c, s=section: c.pop(s),
        f"reject missing required section: {section}",
    )


# Ensure adversarial test never changes source contract
after = json.loads(
    CONTRACT_PATH.read_text(encoding="utf-8-sig")
)

check(
    after == canonical,
    "adversarial mutations never modify J.1 contract file",
)

print()
print("=" * 78)
print(" D.3D.4J.2 - ADVERSARIAL RESULT")
print("=" * 78)
print(f"Checks executed: {checks}")
print(f"Failures: {failures}")
print("RESULT:", "APPROVED" if failures == 0 else "FAILED")

raise SystemExit(0 if failures == 0 else 1)