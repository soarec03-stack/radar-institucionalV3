from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.8E.1"

BASE_DIR = Path(__file__).resolve().parent.parent
AUTOMATION_DIR = BASE_DIR / "automation"

if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))


from short_interest_authoritative_conflict_semantics_v3 import (  # noqa: E402
    classify_authoritative_conflict,
)
from short_interest_corporate_action_reconciler_v3 import (  # noqa: E402
    reconcile_case,
)


INPUT_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_real_integration_adapter_v3.json"
)

REVIEW_INPUT_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_real_positive_official_review_v3.json"
)

BOUNDARY_POLICY_FILE = (
    AUTOMATION_DIR
    / "short_interest_real_reconciler_boundary_policy_v3.json"
)

SEMANTICS_POLICY_FILE = (
    AUTOMATION_DIR
    / "short_interest_authoritative_conflict_semantics_policy_v3.json"
)

RECONCILIATION_POLICY_FILE = (
    AUTOMATION_DIR
    / "short_interest_corporate_action_reconciliation_policy_v3.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_real_reconciler_boundary_v3.json"
)


class BoundaryError(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(
            "r",
            encoding="utf-8-sig",
        ) as file:
            value = json.load(file)
    except FileNotFoundError as exc:
        raise BoundaryError(
            f"Arquivo não encontrado: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise BoundaryError(
            f"JSON inválido em {path}: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise BoundaryError(
            f"Root deve ser objeto: {path}"
        )

    return value


def write_json(
    path: Path,
    value: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            value,
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")


def non_empty_string(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
    )


def asset_map(
    document: dict[str, Any],
    document_name: str,
) -> dict[str, dict[str, Any]]:
    assets = document.get("assets")

    if not isinstance(assets, list):
        raise BoundaryError(
            f"{document_name}: assets deve ser lista."
        )

    result: dict[str, dict[str, Any]] = {}

    for asset in assets:
        if not isinstance(asset, dict):
            raise BoundaryError(
                f"{document_name}: asset inválido."
            )

        ticker = asset.get("ticker")

        if not non_empty_string(ticker):
            raise BoundaryError(
                f"{document_name}: ticker inválido."
            )

        if ticker in result:
            raise BoundaryError(
                f"{document_name}: ticker duplicado: "
                f"{ticker}"
            )

        result[ticker] = asset

    return result


def validate_boundary_policy(
    policy: dict[str, Any],
) -> None:
    if (
        policy.get("policy_version")
        != "3.4D.2-B.2C.8E"
    ):
        raise BoundaryError(
            "Boundary policy version inesperada."
        )

    principles = policy.get("principles")

    if not isinstance(principles, dict):
        raise BoundaryError(
            "Boundary principles ausente."
        )

    required_true = [
        "fail_closed",
        "blocked_never_invokes_reconciler",
        "verified_no_conflict_does_not_authorize_alone",
        "not_established_blocks",
        "conflict_detected_blocks",
        "identity_must_match_exactly",
        "settlement_window_must_match_exactly",
        "preserve_upstream_raw",
    ]

    for field in required_true:
        if principles.get(field) is not True:
            raise BoundaryError(
                f"Boundary principle inválido: {field}"
            )


def validate_identity_match(
    adapter_asset: dict[str, Any],
    review_asset: dict[str, Any],
) -> bool:
    adapter_case = adapter_asset.get(
        "adapter_case"
    )

    review_case = review_asset.get(
        "review_case"
    )

    if not isinstance(adapter_case, dict):
        return False

    if not isinstance(review_case, dict):
        return False

    adapter_identity = adapter_case.get(
        "identity"
    )

    review_identity = review_case.get(
        "identity"
    )

    if not isinstance(
        adapter_identity,
        dict,
    ):
        return False

    if not isinstance(
        review_identity,
        dict,
    ):
        return False

    return adapter_identity == review_identity


def validate_window_match(
    adapter_asset: dict[str, Any],
    review_asset: dict[str, Any],
) -> bool:
    adapter_case = adapter_asset.get(
        "adapter_case"
    )

    review_case = review_asset.get(
        "review_case"
    )

    if not isinstance(adapter_case, dict):
        return False

    if not isinstance(review_case, dict):
        return False

    return (
        adapter_case.get(
            "previous_settlement_date"
        )
        == review_case.get(
            "previous_settlement_date"
        )
        and
        adapter_case.get(
            "current_settlement_date"
        )
        == review_case.get(
            "current_settlement_date"
        )
    )


def blocked_boundary_result(
    ticker: str,
    semantic_result: dict[str, Any] | None,
    diagnostics: list[str],
    adapter_asset: dict[str, Any],
    review_asset: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "boundary_version": VERSION,
        "boundary_status": "BLOCKED",
        "reconciler_invoked": False,
        "reconciler_result": None,
        "analytically_usable": False,
        "authoritative_conflict_semantics":
            deepcopy(semantic_result),
        "diagnostics": deepcopy(diagnostics),
        "raw_adapter_asset":
            deepcopy(adapter_asset),
        "raw_review_asset":
            deepcopy(review_asset),
    }


def build_reconciler_case(
    adapter_asset: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    adapter_case = adapter_asset.get(
        "adapter_case"
    )

    adapter_result = adapter_asset.get(
        "adapter_result"
    )

    if not isinstance(adapter_case, dict):
        raise BoundaryError(
            "adapter_case inválido."
        )

    if not isinstance(adapter_result, dict):
        raise BoundaryError(
            "adapter_result inválido."
        )

    ticker = adapter_asset.get("ticker")

    identity = adapter_case.get("identity")
    action_evidence = adapter_result.get(
        "action_evidence"
    )
    source_adjustment = adapter_result.get(
        "source_adjustment"
    )

    if not isinstance(identity, dict):
        raise BoundaryError(
            f"{ticker}: identity inválida."
        )

    if not isinstance(
        action_evidence,
        dict,
    ):
        raise BoundaryError(
            f"{ticker}: action_evidence inválida."
        )

    if not isinstance(
        source_adjustment,
        dict,
    ):
        raise BoundaryError(
            f"{ticker}: source_adjustment inválido."
        )

    reconciler_case = {
        "case":
            adapter_case.get("case")
            or f"REAL_{ticker}",
        "identity":
            deepcopy(identity),
        "evidence":
            deepcopy(action_evidence),
        "source_adjustment":
            deepcopy(source_adjustment),
    }

    short_interest = adapter_case.get(
        "short_interest"
    )

    if isinstance(short_interest, dict):
        reconciler_case["short_interest"] = (
            deepcopy(short_interest)
        )

    common = {
        "previous_settlement_date":
            adapter_case.get(
                "previous_settlement_date"
            ),
        "current_settlement_date":
            adapter_case.get(
                "current_settlement_date"
            ),
    }

    return reconciler_case, common


def evaluate_asset(
    adapter_asset: dict[str, Any],
    review_asset: dict[str, Any],
    boundary_policy: dict[str, Any],
    semantics_policy: dict[str, Any],
    reconciliation_policy: dict[str, Any],
) -> dict[str, Any]:

    ticker = adapter_asset.get("ticker")

    if not non_empty_string(ticker):
        raise BoundaryError(
            "Ticker inválido no Adapter."
        )

    if review_asset.get("ticker") != ticker:
        return blocked_boundary_result(
            ticker,
            None,
            ["TICKER_MISMATCH"],
            adapter_asset,
            review_asset,
        )

    adapter_result = adapter_asset.get(
        "adapter_result"
    )

    if not isinstance(adapter_result, dict):
        return blocked_boundary_result(
            ticker,
            None,
            ["ADAPTER_RESULT_INVALID"],
            adapter_asset,
            review_asset,
        )

    review_result = review_asset.get(
        "review_result"
    )

    if not isinstance(review_result, dict):
        return blocked_boundary_result(
            ticker,
            None,
            ["REVIEW_RESULT_INVALID"],
            adapter_asset,
            review_asset,
        )

    try:
        semantic_result = (
            classify_authoritative_conflict(
                review_result,
                semantics_policy,
            )
        )
    except Exception as exc:
        return blocked_boundary_result(
            ticker,
            None,
            [
                "CONFLICT_SEMANTICS_INVALID",
                str(exc),
            ],
            adapter_asset,
            review_asset,
        )

    diagnostics: list[str] = []

    semantic_status = semantic_result.get(
        "status"
    )

    if semantic_status in {
        "NOT_ESTABLISHED",
        "CONFLICT_DETECTED",
    }:
        diagnostics.append(
            f"SEMANTIC_STATUS_{semantic_status}"
        )

    required_state = boundary_policy.get(
        "required_adapter_state_for_invocation",
        {},
    )

    if (
        adapter_result.get(
            "integration_status"
        )
        != required_state.get(
            "integration_status"
        )
    ):
        diagnostics.append(
            "ADAPTER_NOT_READY_FOR_RECONCILIATION"
        )

    if (
        adapter_result.get("route")
        != required_state.get("route")
    ):
        diagnostics.append(
            "ADAPTER_ROUTE_NOT_RECONCILER"
        )

    if (
        adapter_result.get(
            "reconciler_input_status"
        )
        != required_state.get(
            "reconciler_input_status"
        )
    ):
        diagnostics.append(
            "RECONCILER_INPUT_NOT_READY"
        )

    if (
        adapter_asset.get(
            "reconciler_invoked"
        )
        is not False
    ):
        diagnostics.append(
            "RECONCILER_ALREADY_INVOKED_OR_INVALID"
        )

    if not validate_identity_match(
        adapter_asset,
        review_asset,
    ):
        diagnostics.append(
            "BOUNDARY_IDENTITY_MISMATCH"
        )

    if not validate_window_match(
        adapter_asset,
        review_asset,
    ):
        diagnostics.append(
            "BOUNDARY_SETTLEMENT_WINDOW_MISMATCH"
        )

    allowed_semantics = (
        boundary_policy.get(
            "allowed_semantic_status_for_invocation",
            [],
        )
    )

    if semantic_status not in allowed_semantics:
        diagnostics.append(
            "SEMANTIC_STATUS_NOT_AUTHORIZED"
        )

    # ------------------------------------------------------------
    # HARD BOUNDARY
    # ------------------------------------------------------------
    #
    # Nothing below this point may invoke the Reconciler
    # if ANY boundary diagnostic exists.
    #
    # ------------------------------------------------------------

    if diagnostics:
        return blocked_boundary_result(
            ticker,
            semantic_result,
            diagnostics,
            adapter_asset,
            review_asset,
        )

    try:
        reconciler_case, common = (
            build_reconciler_case(
                adapter_asset
            )
        )
    except BoundaryError as exc:
        return blocked_boundary_result(
            ticker,
            semantic_result,
            [
                "RECONCILER_CASE_BUILD_BLOCKED",
                str(exc),
            ],
            adapter_asset,
            review_asset,
        )

    # ------------------------------------------------------------
    # ONLY AUTHORIZED RECONCILER INVOCATION
    # ------------------------------------------------------------

    reconciler_result = reconcile_case(
        reconciler_case,
        common,
        reconciliation_policy,
    )

    if not isinstance(
        reconciler_result,
        dict,
    ):
        raise BoundaryError(
            f"{ticker}: Reconciler retornou "
            "resultado inválido."
        )

    reconciler_usable = (
        reconciler_result.get(
            "analytically_usable"
        )
        is True
    )

    return {
        "ticker": ticker,
        "boundary_version": VERSION,
        "boundary_status": "RECONCILED",
        "reconciler_invoked": True,
        "reconciler_result":
            deepcopy(reconciler_result),
        "analytically_usable":
            reconciler_usable,
        "authoritative_conflict_semantics":
            deepcopy(semantic_result),
        "diagnostics": [],
        "raw_adapter_asset":
            deepcopy(adapter_asset),
        "raw_review_asset":
            deepcopy(review_asset),
    }


def run_boundary(
    adapter_document: dict[str, Any],
    review_document: dict[str, Any],
    boundary_policy: dict[str, Any],
    semantics_policy: dict[str, Any],
    reconciliation_policy: dict[str, Any],
) -> dict[str, Any]:

    validate_boundary_policy(
        boundary_policy
    )

    adapters = asset_map(
        adapter_document,
        "Adapter",
    )

    reviews = asset_map(
        review_document,
        "Review",
    )

    if set(adapters) != set(reviews):
        raise BoundaryError(
            "Universo de tickers Adapter/Review "
            "não coincide."
        )

    results: list[dict[str, Any]] = []

    for ticker in sorted(adapters):
        result = evaluate_asset(
            adapters[ticker],
            reviews[ticker],
            boundary_policy,
            semantics_policy,
            reconciliation_policy,
        )

        results.append(result)

    summary = {
        "total_assets": len(results),
        "blocked": sum(
            1
            for item in results
            if item.get("boundary_status")
            == "BLOCKED"
        ),
        "reconciled": sum(
            1
            for item in results
            if item.get("boundary_status")
            == "RECONCILED"
        ),
        "reconciler_invocations": sum(
            1
            for item in results
            if item.get("reconciler_invoked")
            is True
        ),
        "analytically_usable": sum(
            1
            for item in results
            if item.get("analytically_usable")
            is True
        ),
    }

    return {
        "version": VERSION,
        "domain":
            "SHORT_INTEREST_REAL_RECONCILER_BOUNDARY",
        "summary": summary,
        "assets": results,
    }


def main() -> int:

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST")
    print("REAL RECONCILER BOUNDARY")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:
        adapter_document = read_json(
            INPUT_FILE
        )
        review_document = read_json(
            REVIEW_INPUT_FILE
        )
        boundary_policy = read_json(
            BOUNDARY_POLICY_FILE
        )
        semantics_policy = read_json(
            SEMANTICS_POLICY_FILE
        )
        reconciliation_policy = read_json(
            RECONCILIATION_POLICY_FILE
        )

        output = run_boundary(
            adapter_document,
            review_document,
            boundary_policy,
            semantics_policy,
            reconciliation_policy,
        )

        write_json(
            OUTPUT_FILE,
            output,
        )

    except Exception as exc:
        print(
            f"RESULTADO: BLOCKED - "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    for asset in output["assets"]:
        semantic = asset.get(
            "authoritative_conflict_semantics"
        ) or {}

        print("-" * 72)
        print(
            "Ticker:",
            asset.get("ticker"),
        )
        print(
            "Semantic status:",
            semantic.get("status"),
        )
        print(
            "Boundary:",
            asset.get("boundary_status"),
        )
        print(
            "Reconciler invoked:",
            asset.get("reconciler_invoked"),
        )
        print(
            "Analytically usable:",
            asset.get("analytically_usable"),
        )
        print(
            "Diagnostics:",
            asset.get("diagnostics"),
        )

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    for key, value in output["summary"].items():
        print(f"{key}: {value}")

    print(
        "Output:",
        OUTPUT_FILE,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())