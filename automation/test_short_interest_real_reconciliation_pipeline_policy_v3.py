"""
RADAR INSTITUCIONAL V3

SHORT INTEREST
REAL CORPORATE ACTION RECONCILIATION PIPELINE
POLICY TEST

Version:
3.4D.2-B.2C.8A
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.8A"

POLICY_ID = (
    "RADAR_INSTITUCIONAL_V3_"
    "SHORT_INTEREST_REAL_RECONCILIATION_PIPELINE"
)

BASE_DIR = Path(__file__).resolve().parent.parent

POLICY_FILE = (
    BASE_DIR
    / "automation"
    / "short_interest_real_reconciliation_pipeline_policy_v3.json"
)


class PolicyTestError(Exception):
    pass


def read_json(
    path: Path,
) -> dict[str, Any]:

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise PolicyTestError(
            "Policy root must be an object."
        )

    return data


def require_true(
    container: dict[str, Any],
    key: str,
) -> None:

    if container.get(key) is not True:
        raise PolicyTestError(
            f"{key} must be true."
        )


def require_false(
    container: dict[str, Any],
    key: str,
) -> None:

    if container.get(key) is not False:
        raise PolicyTestError(
            f"{key} must be false."
        )


def test_identity_and_version(
    policy: dict[str, Any],
) -> None:

    if policy.get("policy_id") != POLICY_ID:
        raise PolicyTestError(
            "Invalid policy_id."
        )

    if policy.get("version") != VERSION:
        raise PolicyTestError(
            "Invalid version."
        )

    if policy.get("status") != "ACTIVE":
        raise PolicyTestError(
            "Policy must be ACTIVE."
        )


def test_scope_boundaries(
    policy: dict[str, Any],
) -> None:

    scope = policy["scope"]

    if scope.get("domain") != "SHORT_INTEREST":
        raise PolicyTestError(
            "Invalid domain."
        )

    if (
        scope.get("mode")
        != "REAL_CONTROLLED_EXECUTION"
    ):
        raise PolicyTestError(
            "Invalid execution mode."
        )

    require_false(
        scope,
        "network_collection_owned_by_pipeline",
    )

    for key in (
        "mutates_radar_v3",
        "calculates_signal",
        "calculates_confidence",
        "calculates_radar_score",
        "generates_decision",
        "publishes_asset",
    ):
        require_false(scope, key)


def test_fail_closed_principles(
    policy: dict[str, Any],
) -> None:

    principles = policy["principles"]

    required = (
        "fail_closed",
        "absence_of_evidence_is_not_no_action",
        "zero_sec_matches_is_not_no_action",
        "resolver_status_resolved_is_not_no_action",
        "missing_is_not_zero",
        "missing_is_not_neutral",
        "real_inputs_must_be_preserved",
        "raw_short_interest_must_be_preserved",
        "raw_corporate_action_evidence_must_be_preserved",
        "identity_continuity_required",
        "settlement_window_consistency_required",
        "positive_official_review_required_for_no_action",
        "authoritative_action_evidence_required_for_adjustment",
        "double_adjustment_prohibited",
        "adapter_ready_is_not_final_usability",
        "reconciler_owns_final_comparability",
        "quality_gate_required_before_downstream_use",
    )

    for key in required:
        require_true(principles, key)


def test_real_inputs(
    policy: dict[str, Any],
) -> None:

    inputs = policy["real_inputs"]

    expected = {
        "short_interest_collection":
            "input/short_interest_collection_v3.json",

        "corporate_action_evidence":
            (
                "input/"
                "short_interest_corporate_action_evidence_v3.json"
            ),
    }

    for key, expected_path in expected.items():

        item = inputs.get(key)

        if not isinstance(item, dict):
            raise PolicyTestError(
                f"Missing real input: {key}"
            )

        if item.get("path") != expected_path:
            raise PolicyTestError(
                f"Invalid path for {key}."
            )

        require_true(item, "required")
        require_true(item, "real_data")
        require_true(item, "read_only")


def test_join_identity_and_window(
    policy: dict[str, Any],
) -> None:

    contract = policy["join_contract"]

    if contract.get(
        "required_identity_fields"
    ) != [
        "ticker",
        "listing_exchange",
        "security_identity",
    ]:
        raise PolicyTestError(
            "Invalid identity contract."
        )

    require_false(
        contract,
        "ticker_only_identity_is_sufficient",
    )

    require_true(
        contract,
        "require_identity_continuity",
    )

    require_true(
        contract,
        "require_exact_settlement_window_match",
    )

    require_true(
        contract,
        "current_must_be_after_previous",
    )

    for key in (
        "missing_asset_on_either_side",
        "duplicate_asset_on_either_side",
        "identity_mismatch",
        "settlement_window_mismatch",
    ):
        if contract.get(key) != "BLOCK":
            raise PolicyTestError(
                f"{key} must BLOCK."
            )


def test_pipeline_order(
    policy: dict[str, Any],
) -> None:

    stages = policy["pipeline_stages"]

    expected = [
        "LOAD_REAL_INPUTS",
        "VALIDATE_JOIN_AND_IDENTITY",
        "POSITIVE_OFFICIAL_WINDOW_REVIEW",
        "INTEGRATION_ADAPTER",
        "CORPORATE_ACTION_RECONCILER",
        "BUILD_RECONCILED_SHORT_INTEREST_FACT",
        "QUALITY_GATE",
    ]

    actual = [
        stage.get("stage")
        for stage in stages
    ]

    if actual != expected:
        raise PolicyTestError(
            "Invalid pipeline stage order."
        )

    orders = [
        stage.get("order")
        for stage in stages
    ]

    if orders != list(
        range(1, len(expected) + 1)
    ):
        raise PolicyTestError(
            "Invalid pipeline stage numbering."
        )

    for stage in stages:
        require_true(
            stage,
            "fail_closed",
        )


def test_review_adapter_reconciler_boundaries(
    policy: dict[str, Any],
) -> None:

    review = policy["review_contract"]

    require_true(
        review,
        "no_action_requires_positive_official_review",
    )

    require_false(
        review,
        "zero_raw_matches_sufficient_for_no_action",
    )

    require_false(
        review,
        "zero_qualified_actions_sufficient_for_no_action",
    )

    require_false(
        review,
        "resolver_resolved_sufficient_for_no_action",
    )

    adapter = policy["adapter_contract"]

    require_true(
        adapter,
        "blocked_result_must_not_enter_reconciler",
    )

    require_false(
        adapter,
        "ready_for_reconciliation_is_final_usability",
    )

    require_false(
        adapter,
        "adapter_may_invent_evidence",
    )

    require_false(
        adapter,
        "adapter_may_invent_action_parameters",
    )

    require_false(
        adapter,
        "adapter_may_invent_source_adjustment",
    )

    reconciler = policy[
        "reconciler_contract"
    ]

    require_true(
        reconciler,
        "owns_final_corporate_action_comparability",
    )

    require_true(
        reconciler,
        "verified_action_required_for_adjustment",
    )

    require_true(
        reconciler,
        "preserve_previous_raw",
    )

    require_true(
        reconciler,
        "preserve_current_raw",
    )

    require_true(
        reconciler,
        "current_raw_must_not_be_adjusted",
    )

    require_true(
        reconciler,
        "source_already_adjusted_must_not_be_adjusted_again",
    )


def test_quality_gate(
    policy: dict[str, Any],
) -> None:

    gate = policy[
        "quality_gate_contract"
    ]

    require_true(gate, "required")

    require_true(
        gate,
        "verified_requires_reconciler_usable",
    )

    require_true(
        gate,
        "blocked_reconciliation_must_not_be_verified",
    )

    require_true(
        gate,
        "unresolved_corporate_action_must_not_be_verified",
    )

    require_true(
        gate,
        "missing_required_fact_must_not_be_verified",
    )

    require_true(
        gate,
        "quality_gate_may_promote_to_downstream_usable",
    )

    require_false(
        gate,
        "pipeline_before_quality_gate_may_promote_to_downstream_usable",
    )


def test_unresolved_is_valid_real_result(
    policy: dict[str, Any],
) -> None:

    expectations = policy[
        "real_execution_expectations"
    ]

    require_true(
        expectations,
        "unresolved_is_valid_pipeline_outcome",
    )

    require_true(
        expectations,
        "all_assets_unresolved_is_valid_pipeline_outcome",
    )

    require_true(
        expectations,
        "real_execution_success_does_not_require_verified_assets",
    )

    require_true(
        expectations,
        "real_execution_success_requires_structural_completion",
    )

    require_true(
        expectations,
        "real_execution_success_requires_fail_closed_behavior",
    )


def test_permissions_and_prohibitions(
    policy: dict[str, Any],
) -> None:

    permissions = policy[
        "downstream_permissions"
    ]

    require_true(
        permissions,
        "may_write_reconciled_short_interest_file",
    )

    require_true(
        permissions,
        "may_update_short_interest_quality_layer",
    )

    forbidden_permissions = (
        "may_write_radar_v3_directly",
        "may_write_signal_directly",
        "may_write_confidence_directly",
        "may_write_radar_score_directly",
        "may_write_decision_center_directly",
        "may_publish_directly",
    )

    for key in forbidden_permissions:
        require_false(
            permissions,
            key,
        )

    prohibited = set(
        policy["prohibited_behaviors"]
    )

    required_prohibitions = {
        "DECLARE_NO_ACTION_FROM_ZERO_SEC_MATCHES",
        "DECLARE_NO_ACTION_FROM_ZERO_QUALIFIED_ACTIONS",
        "DECLARE_NO_ACTION_FROM_RESOLVER_STATUS_RESOLVED",
        "DECLARE_NO_ACTION_FROM_ABSENCE_OF_EVIDENCE",
        "CALL_RECONCILER_AFTER_ADAPTER_BLOCKED",
        "PROMOTE_ADAPTER_READY_TO_FINAL_USABILITY",
        "INVENT_CORPORATE_ACTION",
        "INVENT_ACTION_EFFECTIVE_DATE",
        "INVENT_SPLIT_RATIO",
        "INVENT_SOURCE_ADJUSTMENT",
        "DOUBLE_ADJUST_SHORT_INTEREST",
        "OVERWRITE_RAW_SHORT_INTEREST",
        "OVERWRITE_RAW_CORPORATE_ACTION_EVIDENCE",
        "WRITE_DIRECTLY_TO_RADAR_SCORE",
        "WRITE_DIRECTLY_TO_DECISION_CENTER",
        "PUBLISH_BEFORE_QUALITY_GATE",
    }

    missing = (
        required_prohibitions
        - prohibited
    )

    if missing:
        raise PolicyTestError(
            (
                "Missing prohibited behaviors: "
                f"{sorted(missing)}"
            )
        )


def run_test(
    number: int,
    name: str,
    function: Any,
) -> bool:

    print("-" * 72)
    print(f"TESTE {number}: {name}")

    try:
        function()
        print("RESULTADO: PASS")
        return True

    except Exception as exc:
        print("RESULTADO: FAIL")
        print("ERRO:", exc)
        return False


def main() -> int:

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST")
    print("REAL RECONCILIATION PIPELINE POLICY TEST")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:
        policy = read_json(
            POLICY_FILE
        )

    except Exception as exc:
        print("ERRO DE INICIALIZACAO:")
        print(exc)
        return 1

    tests = [
        (
            1,
            "Policy identity and version",
            lambda:
                test_identity_and_version(
                    policy
                ),
        ),
        (
            2,
            "Scope boundaries",
            lambda:
                test_scope_boundaries(
                    policy
                ),
        ),
        (
            3,
            "Fail-closed principles",
            lambda:
                test_fail_closed_principles(
                    policy
                ),
        ),
        (
            4,
            "Real input contract",
            lambda:
                test_real_inputs(
                    policy
                ),
        ),
        (
            5,
            "Join, identity and settlement window",
            lambda:
                test_join_identity_and_window(
                    policy
                ),
        ),
        (
            6,
            "Pipeline stage order",
            lambda:
                test_pipeline_order(
                    policy
                ),
        ),
        (
            7,
            "Review, Adapter and Reconciler boundaries",
            lambda:
                test_review_adapter_reconciler_boundaries(
                    policy
                ),
        ),
        (
            8,
            "Quality Gate contract",
            lambda:
                test_quality_gate(
                    policy
                ),
        ),
        (
            9,
            "UNRESOLVED is valid real outcome",
            lambda:
                test_unresolved_is_valid_real_result(
                    policy
                ),
        ),
        (
            10,
            "Permissions and prohibitions",
            lambda:
                test_permissions_and_prohibitions(
                    policy
                ),
        ),
    ]

    passed = 0
    failed = 0

    for number, name, function in tests:

        if run_test(
            number,
            name,
            function,
        ):
            passed += 1
        else:
            failed += 1

    print("=" * 72)
    print("RESUMO")
    print("=" * 72)
    print("Total :", len(tests))
    print("PASS  :", passed)
    print("FAIL  :", failed)

    if failed:
        print(
            "RESULTADO FINAL: REPROVADO"
        )
        return 1

    print(
        "RESULTADO FINAL: APROVADO"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())