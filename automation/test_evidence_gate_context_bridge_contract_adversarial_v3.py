import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent

CONTRACT_PATH = ROOT / "evidence_gate_context_bridge_contract_v3.json"
GATE_POLICY_PATH = ROOT / "evidence_gate_policy_v3.json"
RUNTIME_CONTRACT_PATH = ROOT / "evidence_gate_runtime_contract_v3.json"


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


contract = load_json(CONTRACT_PATH)
gate_policy = load_json(GATE_POLICY_PATH)
runtime_contract = load_json(RUNTIME_CONTRACT_PATH)


# ============================================================
# CANONICAL VALIDATOR
#
# This validator exists only inside the adversarial test.
# It does NOT implement the bridge.
# It validates the frozen D.3D.4B contract against canonical
# invariants and upstream contracts.
# ============================================================

EXPECTED_PROHIBITIONS = {
    "RECALCULATE_SCORE",
    "TRANSLATE_LEGACY_SCORE",
    "INVENT_SCORE_STATUS",
    "INVENT_SCORE_COVERAGE",
    "INVENT_SCORE_PUBLISHABLE",
    "RECALCULATE_CONFIDENCE",
    "RECALCULATE_SIGNALS",
    "INFER_SIGNALS_FROM_SCORE",
    "INFER_SIGNALS_FROM_METRICS",
    "INFER_SIGNALS_FROM_PRICE",
    "RECALCULATE_RISK",
    "REBUILD_RISK_SOURCE_CONTEXT",
    "INFER_RISK_SOURCE_CONTEXT_FROM_PUBLIC_RISK",
    "RECALCULATE_PUBLICATION_ELIGIBILITY",
    "OVERRIDE_PUBLICATION_ELIGIBILITY",
    "PROMOTE_PUBLICATION_INELIGIBLE",
    "INFER_PUBLICATION_ELIGIBILITY_FROM_SCORE_PUBLISHABLE",
    "RECALCULATE_PROVENANCE",
    "INVENT_PROVENANCE",
    "REPAIR_PROVENANCE",
    "FILL_MISSING_WITH_DEFAULTS",
    "FILL_MISSING_WITH_LEGACY_VALUES",
    "CONVERT_MISSING_TO_PASS",
    "MUTATE_RADAR",
    "MUTATE_ASSET",
    "MUTATE_PUBLICATION_CONTEXT",
    "MUTATE_RISK_SOURCE_CONTEXT",
    "WRITE_EVIDENCE_GATE_RESULT",
    "WRITE_DECISION_CENTER",
    "SELECT_DECISION_STATE",
    "ESTABLISH_ACTIONABLE_AUTHORITY",
    "RESOLVE_CONFLICT",
    "MODIFY_SCHEMA_V3",
    "MODIFY_GENERATOR",
    "MODIFY_V2_1",
    "REWRITE_B2K_FIXTURES",
}


EXPECTED_OWNERS = {
    "enriched_asset_state": "UPSTREAM_PIPELINE",
    "domain_signals": "SIGNAL_ENGINE",
    "publication_context": "PUBLICATION_ELIGIBILITY",
    "risk_source_context": "RISK_AND_PUBLICATION_RUNTIME",
    "score": "SCORE_ENGINE",
    "confidence": "CONFIDENCE_ENGINE",
    "risk": "RISK_ENGINE",
    "provenance": "UPSTREAM_PROVENANCE_PIPELINE",
}


EXPECTED_GATE_ARGUMENTS = [
    "radar",
    "evidence_gate_policy",
    "publication_context_by_ticker",
    "risk_source_context_by_ticker",
]


def canonical_contract_is_valid(candidate):
    try:
        if candidate.get("contract_id") != (
            "RADAR_V3_EVIDENCE_GATE_CONTEXT_BRIDGE_CONTRACT"
        ):
            return False

        if candidate.get("contract_version") != "3.4D.3D.4B":
            return False

        if candidate.get("status") != "DRAFT":
            return False

        if candidate.get("scope") != "V3_ONLY":
            return False

        purpose = candidate["purpose"]

        if purpose["defines_runtime_context_bridge"] is not True:
            return False

        for key in (
            "implements_runtime_context_bridge",
            "implements_evidence_gate_engine",
            "defines_evidence_admissibility_policy",
            "recalculates_upstream_results",
            "defines_conflict_resolution",
            "defines_decision_state",
            "defines_actionable_authority",
            "writes_decision_center",
            "modifies_public_output",
        ):
            if purpose[key] is not False:
                return False

        compatibility = candidate["compatibility"]

        if compatibility["preserve_v2_1"] is not True:
            return False

        for key in (
            "modify_v2_1",
            "modify_schema_v3",
            "modify_generator",
            "modify_existing_decision_center_contract",
            "modify_public_output",
            "modify_b2k_fixtures",
        ):
            if compatibility[key] is not False:
                return False

        references = candidate["references"]

        if references["evidence_gate_policy_id"] != gate_policy["policy_id"]:
            return False

        if references["evidence_gate_policy_version"] != (
            gate_policy["policy_version"]
        ):
            return False

        if references["evidence_gate_runtime_contract_id"] != (
            runtime_contract["contract_id"]
        ):
            return False

        if references["evidence_gate_runtime_contract_version"] != (
            runtime_contract["contract_version"]
        ):
            return False

        role = candidate["architectural_role"]

        if role["input"] != "UPSTREAM_RUNTIME_STATE":
            return False

        if role["output"] != "EVIDENCE_GATE_RUNTIME_INPUTS":
            return False

        if role["consumer"] != "EVIDENCE_GATE":
            return False

        if role["output_is_transient"] is not True:
            return False

        for key in (
            "output_is_public_schema",
            "may_persist_output",
            "may_write_asset",
            "may_write_radar_root",
            "may_write_decision_center",
        ):
            if role[key] is not False:
                return False

        ownership = candidate["ownership"]

        if set(ownership.keys()) != set(EXPECTED_OWNERS.keys()):
            return False

        for domain, owner in EXPECTED_OWNERS.items():
            entry = ownership[domain]

            if entry["owner"] != owner:
                return False

            if entry["bridge_role"] != "TRANSPORT_ONLY":
                return False

        signals_owner = ownership["domain_signals"]

        if signals_owner["source_runtime_field"] != "asset.signals":
            return False

        if signals_owner["destination_runtime_field"] != "asset.signals":
            return False

        for key in (
            "may_recalculate",
            "may_invent",
            "may_repair",
            "may_infer_from_score",
        ):
            if signals_owner[key] is not False:
                return False

        publication_owner = ownership["publication_context"]

        if publication_owner["destination_argument"] != (
            "publication_context_by_ticker"
        ):
            return False

        for key in (
            "may_recalculate",
            "may_invent",
            "may_repair",
            "may_override",
            "may_promote_ineligible",
        ):
            if publication_owner[key] is not False:
                return False

        risk_context_owner = ownership["risk_source_context"]

        if risk_context_owner["destination_argument"] != (
            "risk_source_context_by_ticker"
        ):
            return False

        for key in (
            "may_recalculate",
            "may_invent",
            "may_repair",
            "may_override",
        ):
            if risk_context_owner[key] is not False:
                return False

        score_owner = ownership["score"]

        for key in (
            "may_recalculate",
            "may_translate_legacy_score",
            "may_invent_status",
            "may_invent_coverage",
            "may_invent_publishable",
        ):
            if score_owner[key] is not False:
                return False

        for domain in (
            "enriched_asset_state",
            "confidence",
            "risk",
            "provenance",
        ):
            if ownership[domain]["may_recalculate"] is not False:
                return False

        output = candidate["bridge_output_contract"]

        if output["type"] != "TRANSIENT_RUNTIME_CONTEXT":
            return False

        if output["required_fields"] != [
            "radar",
            "publication_context_by_ticker",
            "risk_source_context_by_ticker",
        ]:
            return False

        radar_output = output["radar"]

        if radar_output["source"] != "ENRICHED_UPSTREAM_RADAR":
            return False

        if radar_output["must_preserve_upstream_asset_state"] is not True:
            return False

        for key in (
            "may_mutate_source_radar",
            "may_create_missing_signals",
            "may_translate_legacy_score",
            "may_create_missing_provenance",
        ):
            if radar_output[key] is not False:
                return False

        for name in (
            "publication_context_by_ticker",
            "risk_source_context_by_ticker",
        ):
            entry = output[name]

            if entry["type"] != "DICT_BY_TICKER":
                return False

            if entry["may_be_empty"] is not True:
                return False

            if entry["missing_context_behavior"] != "PRESERVE_ABSENCE":
                return False

            if entry["may_synthesize_missing_ticker"] is not False:
                return False

        invocation = candidate["evidence_gate_invocation_contract"]

        if invocation["function"] != "apply_evidence_gate":
            return False

        if invocation["arguments"] != EXPECTED_GATE_ARGUMENTS:
            return False

        if invocation["argument_mapping"] != {
            "radar": "bridge_output.radar",
            "publication_context_by_ticker":
                "bridge_output.publication_context_by_ticker",
            "risk_source_context_by_ticker":
                "bridge_output.risk_source_context_by_ticker",
        }:
            return False

        if invocation["bridge_may_change_evidence_gate_api"] is not False:
            return False

        if invocation["bridge_may_bypass_evidence_gate"] is not False:
            return False

        absence = candidate["absence_semantics"]

        for key in (
            "missing_signal_context",
            "missing_publication_context",
            "missing_risk_source_context",
            "missing_score_runtime_fields",
            "missing_provenance",
        ):
            if absence[key] != "PRESERVE_ABSENCE":
                return False

        for key in (
            "missing_is_neutral",
            "missing_is_negative",
            "missing_is_positive",
            "missing_is_zero",
            "missing_is_admissible",
            "bridge_may_fill_missing_with_defaults",
            "bridge_may_fill_missing_with_legacy_values",
            "bridge_may_convert_missing_to_pass",
        ):
            if absence[key] is not False:
                return False

        legacy = candidate["legacy_data_boundary"]

        if legacy["legacy_b2k_score_may_be_detected"] is not True:
            return False

        for key in (
            "legacy_b2k_score_may_be_translated",
            "legacy_b2k_score_may_be_promoted",
            "legacy_b2k_missing_signals_may_be_reconstructed",
            "legacy_b2k_missing_publication_context_may_be_reconstructed",
            "legacy_b2k_missing_risk_context_may_be_reconstructed",
        ):
            if legacy[key] is not False:
                return False

        if legacy["legacy_fixture_is_not_runtime_authority"] is not True:
            return False

        publication = candidate["publication_boundary"]

        if publication["consume_upstream_publication_context"] is not True:
            return False

        for key in (
            "recalculate_publication_eligibility",
            "override_publication_eligibility",
            "promote_publication_ineligible",
            "infer_publication_eligibility_from_score_publishable",
        ):
            if publication[key] is not False:
                return False

        if publication["missing_publication_context"] != "PRESERVE_ABSENCE":
            return False

        signal = candidate["signal_boundary"]

        if signal["consume_upstream_signals"] is not True:
            return False

        for key in (
            "recalculate_signals",
            "infer_signals_from_score",
            "infer_signals_from_metrics",
            "infer_signals_from_price",
        ):
            if signal[key] is not False:
                return False

        if signal["missing_signals"] != "PRESERVE_ABSENCE":
            return False

        risk = candidate["risk_boundary"]

        if risk["consume_upstream_risk"] is not True:
            return False

        if risk["consume_upstream_risk_source_context"] is not True:
            return False

        for key in (
            "recalculate_risk",
            "rebuild_risk_source_context",
            "infer_risk_source_context_from_public_risk",
        ):
            if risk[key] is not False:
                return False

        if risk["missing_risk_source_context"] != "PRESERVE_ABSENCE":
            return False

        score = candidate["score_boundary"]

        if score["consume_upstream_score"] is not True:
            return False

        for key in (
            "recalculate_score",
            "translate_legacy_score",
            "infer_score_status",
            "infer_score_coverage",
            "infer_score_publishable",
            "infer_analytically_usable",
        ):
            if score[key] is not False:
                return False

        provenance = candidate["provenance_boundary"]

        if provenance["consume_upstream_provenance"] is not True:
            return False

        for key in (
            "recalculate_provenance",
            "invent_provenance",
            "repair_provenance",
            "infer_provenance_from_source_name",
        ):
            if provenance[key] is not False:
                return False

        if provenance["missing_provenance"] != "PRESERVE_ABSENCE":
            return False

        mutation = candidate["mutation_boundary"]

        for value in mutation.values():
            if value is not False:
                return False

        decision = candidate["decision_boundary"]

        for key in (
            "may_select_decision_state",
            "may_establish_actionable_authority",
            "may_resolve_conflicts",
            "may_create_buy_signal",
            "may_create_sell_signal",
            "may_create_trade_instruction",
        ):
            if decision[key] is not False:
                return False

        if decision["conflict_resolution_owner"] != "D.4":
            return False

        if decision["decision_state_owner"] != "D.5":
            return False

        if decision["traceability_owner"] != "D.6":
            return False

        if decision["generator_integration_owner"] != "D.7":
            return False

        implementation = candidate["implementation_boundary"]

        if implementation["this_step_defines_contract_only"] is not True:
            return False

        for key in (
            "bridge_implementation_allowed_in_this_step",
            "generator_integration_allowed_in_this_step",
            "schema_change_allowed_in_this_step",
            "fixture_rewrite_allowed_in_this_step",
            "evidence_gate_engine_change_allowed_in_this_step",
        ):
            if implementation[key] is not False:
                return False

        if set(candidate["prohibited_behaviors"]) != EXPECTED_PROHIBITIONS:
            return False

        runtime_functions = runtime_contract["runtime_functions"]

        if "apply_evidence_gate" not in runtime_functions:
            return False

        runtime_apply = runtime_functions["apply_evidence_gate"]

        if runtime_apply["inputs"] != invocation["arguments"]:
            return False

        if runtime_apply["may_mutate_radar"] is not False:
            return False

        if runtime_apply["may_write_decision_center"] is not False:
            return False

        if runtime_apply["may_select_decision_state"] is not False:
            return False

        if runtime_apply["may_establish_actionable_authority"] is not False:
            return False

        return True

    except (KeyError, TypeError, AttributeError):
        return False


def mutate(path, value):
    candidate = copy.deepcopy(contract)

    cursor = candidate

    for key in path[:-1]:
        cursor = cursor[key]

    cursor[path[-1]] = value

    return candidate


def remove_key(path):
    candidate = copy.deepcopy(contract)

    cursor = candidate

    for key in path[:-1]:
        cursor = cursor[key]

    del cursor[path[-1]]

    return candidate


def mutation_rejected(name, candidate):
    check(
        canonical_contract_is_valid(candidate) is False,
        name,
    )


print("=" * 78)
print(" D.3D.4C - CONTEXT BRIDGE ADVERSARIAL CONTRACT TEST")
print("=" * 78)


# ============================================================
# A. CANONICAL BASELINE
# ============================================================

check(
    canonical_contract_is_valid(contract) is True,
    "canonical D.3D.4B contract accepted",
)


# ============================================================
# B. IDENTITY / SCOPE ATTACKS
# ============================================================

mutation_rejected(
    "reject altered contract id",
    mutate(["contract_id"], "OTHER_CONTRACT"),
)

mutation_rejected(
    "reject altered contract version",
    mutate(["contract_version"], "999"),
)

mutation_rejected(
    "reject production status mutation",
    mutate(["status"], "PRODUCTION"),
)

mutation_rejected(
    "reject scope expansion beyond V3",
    mutate(["scope"], "V2_AND_V3"),
)


# ============================================================
# C. IMPLEMENTATION / SCOPE CREEP
# ============================================================

for key in (
    "implements_runtime_context_bridge",
    "implements_evidence_gate_engine",
    "defines_evidence_admissibility_policy",
    "recalculates_upstream_results",
    "defines_conflict_resolution",
    "defines_decision_state",
    "defines_actionable_authority",
    "writes_decision_center",
    "modifies_public_output",
):
    mutation_rejected(
        f"reject purpose scope creep: {key}",
        mutate(["purpose", key], True),
    )


# ============================================================
# D. V2.1 / SCHEMA / GENERATOR / FIXTURE ATTACKS
# ============================================================

mutation_rejected(
    "reject disabling V2.1 preservation",
    mutate(["compatibility", "preserve_v2_1"], False),
)

for key in (
    "modify_v2_1",
    "modify_schema_v3",
    "modify_generator",
    "modify_existing_decision_center_contract",
    "modify_public_output",
    "modify_b2k_fixtures",
):
    mutation_rejected(
        f"reject compatibility mutation: {key}",
        mutate(["compatibility", key], True),
    )


# ============================================================
# E. OWNERSHIP ATTACKS
# ============================================================

for domain in EXPECTED_OWNERS:
    mutation_rejected(
        f"reject ownership reassignment: {domain}",
        mutate(
            ["ownership", domain, "owner"],
            "CONTEXT_BRIDGE",
        ),
    )

    mutation_rejected(
        f"reject non-transport bridge role: {domain}",
        mutate(
            ["ownership", domain, "bridge_role"],
            "CALCULATE_AND_TRANSPORT",
        ),
    )


# ============================================================
# F. SIGNAL RECONSTRUCTION ATTACKS
# ============================================================

for key in (
    "may_recalculate",
    "may_invent",
    "may_repair",
    "may_infer_from_score",
):
    mutation_rejected(
        f"reject signal ownership capability: {key}",
        mutate(["ownership", "domain_signals", key], True),
    )

for key in (
    "recalculate_signals",
    "infer_signals_from_score",
    "infer_signals_from_metrics",
    "infer_signals_from_price",
):
    mutation_rejected(
        f"reject signal boundary capability: {key}",
        mutate(["signal_boundary", key], True),
    )

mutation_rejected(
    "reject synthetic signal fallback",
    mutate(
        ["signal_boundary", "missing_signals"],
        "CREATE_DEFAULT_SIGNAL",
    ),
)


# ============================================================
# G. LEGACY SCORE TRANSLATION ATTACKS
# ============================================================

for key in (
    "may_recalculate",
    "may_translate_legacy_score",
    "may_invent_status",
    "may_invent_coverage",
    "may_invent_publishable",
):
    mutation_rejected(
        f"reject score ownership capability: {key}",
        mutate(["ownership", "score", key], True),
    )

for key in (
    "recalculate_score",
    "translate_legacy_score",
    "infer_score_status",
    "infer_score_coverage",
    "infer_score_publishable",
    "infer_analytically_usable",
):
    mutation_rejected(
        f"reject score boundary capability: {key}",
        mutate(["score_boundary", key], True),
    )

mutation_rejected(
    "reject B2K legacy score translation",
    mutate(
        [
            "legacy_data_boundary",
            "legacy_b2k_score_may_be_translated",
        ],
        True,
    ),
)

mutation_rejected(
    "reject B2K legacy score promotion",
    mutate(
        [
            "legacy_data_boundary",
            "legacy_b2k_score_may_be_promoted",
        ],
        True,
    ),
)


# ============================================================
# H. PUBLICATION PROMOTION / RECONSTRUCTION ATTACKS
# ============================================================

for key in (
    "may_recalculate",
    "may_invent",
    "may_repair",
    "may_override",
    "may_promote_ineligible",
):
    mutation_rejected(
        f"reject publication ownership capability: {key}",
        mutate(
            ["ownership", "publication_context", key],
            True,
        ),
    )

for key in (
    "recalculate_publication_eligibility",
    "override_publication_eligibility",
    "promote_publication_ineligible",
    "infer_publication_eligibility_from_score_publishable",
):
    mutation_rejected(
        f"reject publication boundary capability: {key}",
        mutate(["publication_boundary", key], True),
    )

mutation_rejected(
    "reject publication fallback from absence",
    mutate(
        [
            "publication_boundary",
            "missing_publication_context",
        ],
        "ASSUME_ELIGIBLE",
    ),
)

mutation_rejected(
    "reject B2K publication reconstruction",
    mutate(
        [
            "legacy_data_boundary",
            "legacy_b2k_missing_publication_context_may_be_reconstructed",
        ],
        True,
    ),
)


# ============================================================
# I. RISK CONTEXT RECONSTRUCTION ATTACKS
# ============================================================

for key in (
    "may_recalculate",
    "may_invent",
    "may_repair",
    "may_override",
):
    mutation_rejected(
        f"reject risk sidecar ownership capability: {key}",
        mutate(
            ["ownership", "risk_source_context", key],
            True,
        ),
    )

for key in (
    "recalculate_risk",
    "rebuild_risk_source_context",
    "infer_risk_source_context_from_public_risk",
):
    mutation_rejected(
        f"reject risk boundary capability: {key}",
        mutate(["risk_boundary", key], True),
    )

mutation_rejected(
    "reject missing risk sidecar fallback",
    mutate(
        ["risk_boundary", "missing_risk_source_context"],
        "ASSUME_PUBLICATION_ELIGIBLE",
    ),
)

mutation_rejected(
    "reject B2K risk context reconstruction",
    mutate(
        [
            "legacy_data_boundary",
            "legacy_b2k_missing_risk_context_may_be_reconstructed",
        ],
        True,
    ),
)


# ============================================================
# J. PROVENANCE ATTACKS
# ============================================================

for key in (
    "recalculate_provenance",
    "invent_provenance",
    "repair_provenance",
    "infer_provenance_from_source_name",
):
    mutation_rejected(
        f"reject provenance boundary capability: {key}",
        mutate(["provenance_boundary", key], True),
    )

mutation_rejected(
    "reject provenance fallback from absence",
    mutate(
        ["provenance_boundary", "missing_provenance"],
        "ASSUME_VERIFIED",
    ),
)


# ============================================================
# K. MISSING DATA DEFAULT ATTACKS
# ============================================================

for key in (
    "missing_is_neutral",
    "missing_is_negative",
    "missing_is_positive",
    "missing_is_zero",
    "missing_is_admissible",
    "bridge_may_fill_missing_with_defaults",
    "bridge_may_fill_missing_with_legacy_values",
    "bridge_may_convert_missing_to_pass",
):
    mutation_rejected(
        f"reject missing semantics mutation: {key}",
        mutate(["absence_semantics", key], True),
    )

for key in (
    "missing_signal_context",
    "missing_publication_context",
    "missing_risk_source_context",
    "missing_score_runtime_fields",
    "missing_provenance",
):
    mutation_rejected(
        f"reject absence reconstruction: {key}",
        mutate(
            ["absence_semantics", key],
            "SYNTHESIZE_DEFAULT",
        ),
    )


# ============================================================
# L. OUTPUT MUTATION / PERSISTENCE ATTACKS
# ============================================================

for key in (
    "output_is_public_schema",
    "may_persist_output",
    "may_write_asset",
    "may_write_radar_root",
    "may_write_decision_center",
):
    mutation_rejected(
        f"reject architectural persistence capability: {key}",
        mutate(["architectural_role", key], True),
    )

for key in (
    "may_mutate_source_radar",
    "may_create_missing_signals",
    "may_translate_legacy_score",
    "may_create_missing_provenance",
):
    mutation_rejected(
        f"reject radar output mutation capability: {key}",
        mutate(["bridge_output_contract", "radar", key], True),
    )

for context_name in (
    "publication_context_by_ticker",
    "risk_source_context_by_ticker",
):
    mutation_rejected(
        f"reject synthetic ticker in {context_name}",
        mutate(
            [
                "bridge_output_contract",
                context_name,
                "may_synthesize_missing_ticker",
            ],
            True,
        ),
    )

    mutation_rejected(
        f"reject absence synthesis in {context_name}",
        mutate(
            [
                "bridge_output_contract",
                context_name,
                "missing_context_behavior",
            ],
            "SYNTHESIZE",
        ),
    )


# ============================================================
# M. DIRECT MUTATION BOUNDARY ATTACKS
# ============================================================

for key in contract["mutation_boundary"]:
    mutation_rejected(
        f"reject mutation permission: {key}",
        mutate(["mutation_boundary", key], True),
    )


# ============================================================
# N. DECISION CENTER / D.4 / D.5 / D.7 INVASION
# ============================================================

for key in (
    "may_select_decision_state",
    "may_establish_actionable_authority",
    "may_resolve_conflicts",
    "may_create_buy_signal",
    "may_create_sell_signal",
    "may_create_trade_instruction",
):
    mutation_rejected(
        f"reject decision capability: {key}",
        mutate(["decision_boundary", key], True),
    )

mutation_rejected(
    "reject bridge taking ownership of D.4",
    mutate(
        ["decision_boundary", "conflict_resolution_owner"],
        "CONTEXT_BRIDGE",
    ),
)

mutation_rejected(
    "reject bridge taking ownership of D.5",
    mutate(
        ["decision_boundary", "decision_state_owner"],
        "CONTEXT_BRIDGE",
    ),
)

mutation_rejected(
    "reject bridge taking ownership of D.6",
    mutate(
        ["decision_boundary", "traceability_owner"],
        "CONTEXT_BRIDGE",
    ),
)

mutation_rejected(
    "reject bridge taking ownership of D.7",
    mutate(
        ["decision_boundary", "generator_integration_owner"],
        "CONTEXT_BRIDGE",
    ),
)


# ============================================================
# O. IMPLEMENTATION BOUNDARY ATTACKS
# ============================================================

mutation_rejected(
    "reject changing contract-only phase",
    mutate(
        ["implementation_boundary", "this_step_defines_contract_only"],
        False,
    ),
)

for key in (
    "bridge_implementation_allowed_in_this_step",
    "generator_integration_allowed_in_this_step",
    "schema_change_allowed_in_this_step",
    "fixture_rewrite_allowed_in_this_step",
    "evidence_gate_engine_change_allowed_in_this_step",
):
    mutation_rejected(
        f"reject implementation scope expansion: {key}",
        mutate(["implementation_boundary", key], True),
    )


# ============================================================
# P. EVIDENCE GATE API ATTACKS
# ============================================================

mutation_rejected(
    "reject alternate Evidence Gate function",
    mutate(
        ["evidence_gate_invocation_contract", "function"],
        "custom_gate",
    ),
)

mutation_rejected(
    "reject removing publication context argument",
    mutate(
        ["evidence_gate_invocation_contract", "arguments"],
        [
            "radar",
            "evidence_gate_policy",
            "risk_source_context_by_ticker",
        ],
    ),
)

mutation_rejected(
    "reject argument reordering",
    mutate(
        ["evidence_gate_invocation_contract", "arguments"],
        [
            "evidence_gate_policy",
            "radar",
            "publication_context_by_ticker",
            "risk_source_context_by_ticker",
        ],
    ),
)

mutation_rejected(
    "reject Evidence Gate API mutation permission",
    mutate(
        [
            "evidence_gate_invocation_contract",
            "bridge_may_change_evidence_gate_api",
        ],
        True,
    ),
)

mutation_rejected(
    "reject Evidence Gate bypass",
    mutate(
        [
            "evidence_gate_invocation_contract",
            "bridge_may_bypass_evidence_gate",
        ],
        True,
    ),
)


# ============================================================
# Q. REQUIRED OUTPUT CONTRACT ATTACKS
# ============================================================

mutation_rejected(
    "reject missing publication output context",
    mutate(
        ["bridge_output_contract", "required_fields"],
        [
            "radar",
            "risk_source_context_by_ticker",
        ],
    ),
)

mutation_rejected(
    "reject missing risk output context",
    mutate(
        ["bridge_output_contract", "required_fields"],
        [
            "radar",
            "publication_context_by_ticker",
        ],
    ),
)

mutation_rejected(
    "reject persistent bridge output type",
    mutate(
        ["bridge_output_contract", "type"],
        "PERSISTED_PUBLIC_OUTPUT",
    ),
)


# ============================================================
# R. PROHIBITION ATTACKS
# ============================================================

for prohibition in sorted(EXPECTED_PROHIBITIONS):
    candidate = copy.deepcopy(contract)

    candidate["prohibited_behaviors"] = [
        item
        for item in candidate["prohibited_behaviors"]
        if item != prohibition
    ]

    mutation_rejected(
        f"reject removal of prohibition: {prohibition}",
        candidate,
    )


candidate = copy.deepcopy(contract)
candidate["prohibited_behaviors"].append("UNKNOWN_EXTRA_RULE")

mutation_rejected(
    "reject unauthorized extra prohibition mutation",
    candidate,
)


# ============================================================
# S. STRUCTURAL DELETION ATTACKS
# ============================================================

for section in (
    "purpose",
    "compatibility",
    "references",
    "architectural_role",
    "ownership",
    "bridge_output_contract",
    "evidence_gate_invocation_contract",
    "absence_semantics",
    "legacy_data_boundary",
    "publication_boundary",
    "signal_boundary",
    "risk_boundary",
    "score_boundary",
    "provenance_boundary",
    "mutation_boundary",
    "decision_boundary",
    "implementation_boundary",
    "prohibited_behaviors",
):
    mutation_rejected(
        f"reject missing required section: {section}",
        remove_key([section]),
    )


# ============================================================
# T. ORIGINAL OBJECT MUST REMAIN UNCHANGED
# ============================================================

contract_after_tests = load_json(CONTRACT_PATH)

check(
    contract_after_tests == contract,
    "adversarial mutations never modify contract file",
)


# ============================================================
# U. FINAL
# ============================================================

print()
print("=" * 78)
print(" D.3D.4C - ADVERSARIAL CONTRACT RESULT")
print("=" * 78)
print(f"Checks executed: {checks}")
print(f"Failures: {len(failures)}")

if failures:
    print("RESULT: FAILED")

    for failure in failures:
        print(f" - {failure}")

    raise SystemExit(1)

print("RESULT: APPROVED")
