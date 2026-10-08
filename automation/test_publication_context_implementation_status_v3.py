import ast
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
AUTO = BASE / "automation"

CONTRACT_PATH = AUTO / "publication_context_implementation_status_v3.json"
PUBLICATION_PATH = AUTO / "publication_eligibility_v3.py"
GENERATOR_PATH = AUTO / "generate_radar_v3.py"
SCHEMA_PATH = AUTO / "schema_v3.json"

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


contract = json.loads(
    CONTRACT_PATH.read_text(encoding="utf-8-sig")
)

check(
    contract["contract_id"]
    == "RADAR_V3_PUBLICATION_CONTEXT_IMPLEMENTATION_STATUS",
    "contract id canonical",
)

check(
    contract["contract_version"] == "3.4D.3D.4J.1",
    "contract version canonical",
)

check(
    contract["status"] == "HOMOLOGATED",
    "implementation status homologated",
)

check(
    contract["scope"] == "V3_ONLY",
    "scope remains V3 only",
)

trace = contract["historical_trace"]

check(
    trace["interface_contract_phase"] == "D.3D.4G",
    "historical G phase preserved",
)

check(
    trace["interface_contract_status_at_that_time"]
    == "PROPOSED_NOT_IMPLEMENTED",
    "historical G state preserved",
)

check(
    trace["implementation_phase"] == "D.3D.4I",
    "implementation attributed to I",
)

check(
    trace["current_status"] == "IMPLEMENTED_AND_HOMOLOGATED",
    "current implementation status canonical",
)

check(
    trace["historical_contract_must_not_be_rewritten"] is True,
    "historical G contract cannot be rewritten",
)

implementation = contract["implementation"]

check(
    implementation["function"]
    == "build_publication_context_by_ticker",
    "implementation function canonical",
)

check(
    implementation["implemented"] is True,
    "interface implemented",
)

check(
    implementation["homologated"] is True,
    "interface homologated",
)

check(
    implementation["transient_only"] is True,
    "interface remains transient only",
)

for key in (
    "persists_output",
    "mutates_radar",
    "mutates_asset",
    "writes_score_publishable",
    "writes_decision_center",
):
    check(
        implementation[key] is False,
        f"implementation boundary {key} false",
    )

api = contract["canonical_api"]

expected_args = [
    "data",
    "registry",
    "policy",
    "risk_source_context_by_ticker",
]

check(
    api["arguments"] == expected_args,
    "canonical API arguments frozen",
)

check(
    api["required_per_ticker_fields"]
    == ["ticker", "eligible", "components"],
    "per-ticker output fields canonical",
)

tree = ast.parse(
    PUBLICATION_PATH.read_text(encoding="utf-8-sig")
)

functions = {
    node.name: node
    for node in tree.body
    if isinstance(node, ast.FunctionDef)
}

check(
    "build_publication_context_by_ticker" in functions,
    "implemented function exists in production module",
)

build_node = functions["build_publication_context_by_ticker"]

check(
    [a.arg for a in build_node.args.args] == expected_args,
    "implemented function signature matches contract",
)

apply_node = functions["apply_publication_eligibility"]

check(
    [a.arg for a in apply_node.args.args] == expected_args,
    "existing apply API remains unchanged",
)

check(
    len(apply_node.args.defaults) == 2,
    "existing apply optional arguments preserved",
)

source = contract["source_of_truth"]

check(
    source["canonical_evaluator"] == "evaluate_asset_publication",
    "canonical evaluator ownership preserved",
)

for key in (
    "builder_may_recalculate_eligibility_independently",
    "builder_may_override_evaluator",
    "builder_may_promote_ineligible",
    "builder_may_invent_missing_context",
    "builder_may_define_local_thresholds",
    "builder_may_remove_blocked_components",
    "builder_may_rewrite_component_reasons",
):
    check(
        source[key] is False,
        f"source-of-truth boundary {key} false",
    )

compat = contract["backward_compatibility"]

check(
    compat["apply_publication_eligibility_api_preserved"] is True,
    "existing apply API explicitly preserved",
)

check(
    compat["apply_publication_eligibility_return_arity"] == 2,
    "existing apply return arity remains two",
)

for key in (
    "existing_callers_require_change",
    "generator_modified",
    "schema_v3_modified",
    "v2_1_modified",
    "public_output_modified",
):
    check(
        compat[key] is False,
        f"compatibility boundary {key} false",
    )

runtime = contract["runtime_boundaries"]

for key in (
    "context_bridge_implemented",
    "generator_integration_implemented",
    "evidence_gate_integration_implemented",
    "decision_state_selection_implemented",
    "conflict_resolution_implemented",
    "actionable_authority_established",
):
    check(
        runtime[key] is False,
        f"runtime boundary {key} false",
    )

generator_text = GENERATOR_PATH.read_text(
    encoding="utf-8-sig"
)

schema_text = SCHEMA_PATH.read_text(
    encoding="utf-8-sig"
)

check(
    "publication_context_by_ticker" not in generator_text,
    "Generator still has no publication context integration",
)

check(
    "publication_context_by_ticker" not in schema_text,
    "schema still does not persist publication context",
)

required_prohibitions = {
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

check(
    set(contract["prohibited_behaviors"])
    == required_prohibitions,
    "mandatory prohibitions exact",
)

print()
print("=" * 78)
print(" D.3D.4J.1 - IMPLEMENTATION STATUS CONTRACT RESULT")
print("=" * 78)
print(f"Checks executed: {checks}")
print(f"Failures: {failures}")
print("RESULT:", "APPROVED" if failures == 0 else "FAILED")

raise SystemExit(0 if failures == 0 else 1)