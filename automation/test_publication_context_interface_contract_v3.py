import ast
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
AUTO = BASE / "automation"

CONTRACT_PATH = AUTO / "publication_context_interface_contract_v3.json"
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


contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8-sig"))

check(
    contract["contract_id"]
    == "RADAR_V3_PUBLICATION_CONTEXT_INTERFACE_CONTRACT",
    "contract id canonical",
)
check(
    contract["contract_version"] == "3.4D.3D.4G",
    "contract version canonical",
)
check(contract["status"] == "DRAFT", "contract remains DRAFT")
check(contract["scope"] == "V3_ONLY", "scope V3 only")

purpose = contract["purpose"]
check(
    purpose["problem_confirmed_by_runtime_inventory"]
    == "PUBLICATION_CONTEXT_BY_TICKER_IS_NOT_CURRENTLY_EXPOSED_BY_PUBLICATION_ELIGIBILITY_RUNTIME",
    "runtime inventory finding preserved",
)
check(
    purpose["interface_role"]
    == "EXPOSE_EXISTING_UPSTREAM_EVALUATION_CONTEXT",
    "interface exposes existing evaluation",
)
check(
    purpose["not_a_new_evaluation_model"] is True,
    "interface is not a new evaluation model",
)

ownership = contract["ownership"]
check(
    ownership["owner"] == "PUBLICATION_ELIGIBILITY",
    "Publication Eligibility owns context",
)
check(
    ownership["canonical_evaluator"] == "evaluate_asset_publication",
    "canonical evaluator frozen",
)
check(
    ownership["consumer"] == "EVIDENCE_GATE",
    "Evidence Gate consumer frozen",
)
check(
    ownership["transport_consumer"]
    == "EVIDENCE_GATE_CONTEXT_BRIDGE",
    "Context Bridge transport consumer frozen",
)
check(
    ownership["evidence_gate_may_recalculate_publication"] is False,
    "Evidence Gate cannot recalculate publication",
)
check(
    ownership["context_bridge_may_recalculate_publication"] is False,
    "Context Bridge cannot recalculate publication",
)

compat = contract["compatibility"]
check(compat["preserve_v2_1"] is True, "V2.1 preserved")
check(compat["preserve_schema_v3"] is True, "schema V3 preserved")
check(
    compat["preserve_public_decision_center_contract"] is True,
    "public Decision Center contract preserved",
)
check(
    compat["preserve_existing_apply_publication_eligibility_api"] is True,
    "existing apply API preserved",
)
check(
    compat["apply_publication_eligibility_existing_return_arity"] == 2,
    "existing apply return arity remains two",
)
check(
    compat["apply_publication_eligibility_existing_return_semantics"]
    == ["data", "publication_changes"],
    "existing apply return semantics preserved",
)
check(
    compat["may_change_existing_return_arity"] is False,
    "existing return arity cannot change",
)
check(
    compat["may_require_existing_callers_to_change"] is False,
    "existing callers cannot be forced to change",
)

interface = contract["proposed_interface"]
check(
    interface["name"] == "build_publication_context_by_ticker",
    "dedicated interface name canonical",
)
check(
    interface["owner_module"] == "publication_eligibility_v3.py",
    "interface owner module canonical",
)
check(
    interface["implementation_status"]
    == "NOT_IMPLEMENTED_IN_D3D4G",
    "interface not implemented in contract step",
)
check(
    interface["arguments"]
    == [
        "data",
        "registry",
        "policy",
        "risk_source_context_by_ticker",
    ],
    "interface arguments exact",
)
check(
    interface["optional_arguments"]
    == ["policy", "risk_source_context_by_ticker"],
    "optional arguments exact",
)
check(
    interface["returns"] == "publication_context_by_ticker",
    "interface return canonical",
)
check(
    interface["return_type"] == "DICT_BY_TICKER",
    "interface return type canonical",
)
check(interface["transient_only"] is True, "context transient only")

sem = contract["context_semantics"]
check(
    sem["source_of_truth"] == "evaluate_asset_publication",
    "source of truth canonical",
)
check(
    sem["must_be_derived_from_canonical_evaluator"] is True,
    "context derived from canonical evaluator",
)

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
    check(sem[key] is False, f"{key} disabled")

per_ticker = contract["per_ticker_context"]
check(
    per_ticker["required_fields"]
    == ["ticker", "eligible", "components"],
    "per ticker fields exact",
)
check(
    per_ticker["ticker"]["source"] == "asset.ticker",
    "ticker comes from asset",
)
check(
    per_ticker["ticker"]["may_be_invented"] is False,
    "ticker cannot be invented",
)
check(
    per_ticker["eligible"]["source"]
    == "evaluate_asset_publication.result.eligible",
    "eligible source canonical",
)
check(
    per_ticker["eligible"]["type"] == "BOOLEAN",
    "eligible type boolean",
)
check(
    per_ticker["eligible"]["may_be_recalculated_by_bridge"] is False,
    "bridge cannot recalculate eligible",
)
check(
    per_ticker["eligible"]["may_be_promoted"] is False,
    "eligible cannot be promoted",
)
check(
    per_ticker["components"]["source"]
    == "evaluate_asset_publication.result.components",
    "components source canonical",
)
check(
    per_ticker["components"]["type"] == "OBJECT",
    "components type object",
)
check(
    per_ticker["components"]["preserve_component_results"] is True,
    "component results preserved",
)
check(
    per_ticker["components"]["may_drop_blocked_components"] is False,
    "blocked components cannot be dropped",
)
check(
    per_ticker["components"]["may_rewrite_reasons"] is False,
    "component reasons cannot be rewritten",
)

absence = contract["absence_semantics"]
check(
    absence["missing_asset_ticker"] == "DO_NOT_INVENT_IDENTITY",
    "missing ticker does not invent identity",
)
check(
    absence["missing_risk_source_context"]
    == "PRESERVE_CANONICAL_EVALUATOR_FAIL_CLOSED_SEMANTICS",
    "missing risk context preserves evaluator semantics",
)
check(
    absence["missing_publication_context"]
    == "DO_NOT_ASSUME_ELIGIBLE",
    "missing publication context does not assume eligible",
)
check(
    absence["unknown_publication_result"] == "FAIL_CLOSED",
    "unknown publication result fails closed",
)
check(
    absence["absence_is_not_eligibility"] is True,
    "absence is not eligibility",
)

runtime = contract["runtime_relationship"]
check(
    runtime["existing_apply_publication_eligibility"][
        "remains_authoritative_for_publishable_restriction"
    ] is True,
    "existing apply remains authoritative",
)
check(
    runtime["existing_apply_publication_eligibility"][
        "existing_behavior_must_be_preserved"
    ] is True,
    "existing apply behavior preserved",
)

new_runtime = runtime["new_context_interface"]
for key in (
    "must_not_write_score_publishable",
    "must_not_write_decision_center",
    "must_not_write_asset",
    "must_not_persist_context",
):
    check(new_runtime[key] is True, f"{key} enforced")

downstream = contract["downstream_contract"]
check(
    downstream["destination"] == "publication_context_by_ticker",
    "downstream destination canonical",
)
check(
    downstream["context_bridge_role"] == "TRANSPORT_ONLY",
    "Context Bridge transport only",
)
check(
    downstream["evidence_gate_role"] == "CONSUME_ONLY",
    "Evidence Gate consume only",
)
check(
    downstream["evidence_gate_may_override_eligible"] is False,
    "Evidence Gate cannot override eligibility",
)
check(
    downstream["evidence_gate_may_re_evaluate_sources"] is False,
    "Evidence Gate cannot re-evaluate sources",
)
check(
    downstream["evidence_gate_may_re_evaluate_tiers"] is False,
    "Evidence Gate cannot re-evaluate tiers",
)

trace = contract["traceability"]
check(trace["preserve_eligible"] is True, "eligible trace preserved")
check(trace["preserve_components"] is True, "components trace preserved")
check(
    trace["preserve_component_reasons"] is True,
    "component reasons preserved",
)
check(
    trace["preserve_source_information_when_produced_upstream"] is True,
    "source information preserved",
)
check(
    trace["silent_deletion_of_blocked_evidence"] is False,
    "blocked evidence cannot disappear silently",
)

prohibited = set(contract["prohibited_behaviors"])
required_prohibitions = {
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
check(
    required_prohibitions.issubset(prohibited),
    "all critical prohibitions present",
)

phase = contract["phase_boundary"]
check(phase["d3d4g_contract_only"] is True, "D.3D.4G contract only")
for key in (
    "implements_interface",
    "changes_publication_engine",
    "changes_generator",
    "changes_evidence_gate_engine",
    "changes_context_bridge",
    "changes_schema",
    "changes_v2_1",
):
    check(phase[key] is False, f"{key} remains false")
check(
    phase["implementation_requires_separate_test_proven_step"] is True,
    "implementation requires separate test-proven step",
)

# ------------------------------------------------------------
# Alignment with actual homologated runtime API
# ------------------------------------------------------------

publication_text = PUBLICATION_PATH.read_text(encoding="utf-8-sig")
publication_ast = ast.parse(publication_text)

functions = {
    node.name: node
    for node in publication_ast.body
    if isinstance(node, ast.FunctionDef)
}

check(
    "evaluate_asset_publication" in functions,
    "canonical evaluator exists in production module",
)
check(
    "apply_publication_eligibility" in functions,
    "existing apply API exists in production module",
)

apply_fn = functions["apply_publication_eligibility"]
apply_args = [arg.arg for arg in apply_fn.args.args]

check(
    apply_args
    == [
        "data",
        "registry",
        "policy",
        "risk_source_context_by_ticker",
    ],
    "existing apply arguments remain canonical",
)

check(
    "build_publication_context_by_ticker" not in functions,
    "new interface intentionally not implemented yet",
)

# Confirm current Generator still consumes two return values.
generator_text = GENERATOR_PATH.read_text(encoding="utf-8-sig")
generator_ast = ast.parse(generator_text)

apply_assignments = []

for node in ast.walk(generator_ast):
    if not isinstance(node, ast.Assign):
        continue

    if not isinstance(node.value, ast.Call):
        continue

    try:
        called = ast.unparse(node.value.func)
    except Exception:
        continue

    if called == "apply_publication_eligibility":
        apply_assignments.append(node)

check(
    len(apply_assignments) == 1,
    "Generator has exactly one apply publication assignment",
)

if len(apply_assignments) == 1:
    target = apply_assignments[0].targets[0]
    check(
        isinstance(target, (ast.Tuple, ast.List))
        and len(target.elts) == 2,
        "Generator still unpacks exactly two publication returns",
    )
else:
    check(False, "Generator still unpacks exactly two publication returns")

check(
    "publication_context_by_ticker" not in generator_text,
    "Generator does not fabricate publication context",
)

schema_text = SCHEMA_PATH.read_text(encoding="utf-8-sig")
check(
    "publication_context_by_ticker" not in schema_text,
    "schema does not persist publication context",
)

print()
print(f"Checks executed: {checks}")
print(f"Failures: {failures}")
print("RESULT:", "APPROVED" if failures == 0 else "FAILED")

raise SystemExit(0 if failures == 0 else 1)