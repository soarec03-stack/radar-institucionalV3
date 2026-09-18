"""
RADAR INSTITUCIONAL V3

SHORT INTEREST
REAL POSITIVE OFFICIAL WINDOW REVIEW BRIDGE
REGRESSION TEST

Version:
3.4D.2-B.2C.8C.1
"""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


BASE_DIR = Path(__file__).resolve().parent.parent
AUTOMATION_DIR = BASE_DIR / "automation"

if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(AUTOMATION_DIR),
    )


from short_interest_real_positive_official_window_review_bridge_v3 import (  # noqa: E402
    NORMALIZED_FILE,
    POLICY_FILE,
    BridgeError,
    build_review_case,
    read_json,
    run_bridge,
    serialize_security_identity,
)


VERSION = "3.4D.2-B.2C.8C.1"


class RegressionTestError(Exception):
    pass


def find_asset(
    document: dict[str, Any],
    ticker: str,
) -> dict[str, Any]:

    assets = document.get("assets")

    if not isinstance(assets, list):
        raise RegressionTestError(
            "assets must be list."
        )

    matches = [
        asset
        for asset in assets
        if (
            isinstance(asset, dict)
            and asset.get("ticker") == ticker
        )
    ]

    if len(matches) != 1:
        raise RegressionTestError(
            f"Expected exactly one {ticker} asset."
        )

    return matches[0]


def expect_bridge_error(
    function: Callable[[], Any],
    expected_text: str,
) -> None:

    try:
        function()

    except BridgeError as exc:

        if expected_text not in str(exc):
            raise RegressionTestError(
                (
                    "Unexpected BridgeError. "
                    f"Expected={expected_text!r}; "
                    f"actual={str(exc)!r}"
                )
            )

        return

    raise RegressionTestError(
        "Expected BridgeError."
    )


def test_real_current_state(
    normalized: dict[str, Any],
    policy: dict[str, Any],
) -> None:

    result = run_bridge(
        deepcopy(normalized),
        deepcopy(policy),
    )

    summary = result.get("summary", {})

    expected = {
        "total_assets": 3,
        "no_action_proven": 0,
        "action_found": 0,
        "unresolved": 3,
        "ready_for_adapter": 0,
        "analytically_usable": 0,
    }

    if summary != expected:
        raise RegressionTestError(
            (
                "Unexpected real summary. "
                f"Expected={expected}; "
                f"actual={summary}"
            )
        )

    for asset in result["assets"]:

        review = asset.get(
            "review_result",
            {},
        )

        if (
            review.get("review_status")
            != "UNRESOLVED"
        ):
            raise RegressionTestError(
                "Real asset must remain UNRESOLVED."
            )

        if (
            review.get(
                "corporate_action_status"
            )
            != "UNRESOLVED"
        ):
            raise RegressionTestError(
                (
                    "Real Corporate Action "
                    "status must remain UNRESOLVED."
                )
            )

        if (
            review.get(
                "reconciliation_eligible"
            )
            is not False
        ):
            raise RegressionTestError(
                (
                    "Real asset must not become "
                    "reconciliation eligible."
                )
            )

        if (
            asset.get("downstream_status")
            != "BLOCKED_PENDING_OFFICIAL_REVIEW"
        ):
            raise RegressionTestError(
                "Real asset must remain blocked."
            )

        diagnostics = review.get(
            "diagnostics",
            [],
        )

        if (
            "MISSING_AUTHORITATIVE_SOURCE"
            not in diagnostics
        ):
            raise RegressionTestError(
                (
                    "Expected "
                    "MISSING_AUTHORITATIVE_SOURCE."
                )
            )


def test_no_authoritative_review_is_invented(
    normalized: dict[str, Any],
) -> None:

    for asset in normalized["assets"]:

        case = build_review_case(
            deepcopy(asset)
        )

        reviews = case.get(
            "authoritative_reviews"
        )

        if reviews != []:
            raise RegressionTestError(
                (
                    "Bridge invented an "
                    "authoritative review."
                )
            )


def test_security_identity_translation(
    normalized: dict[str, Any],
) -> None:

    expected = {
        "CRSP": "CUSIP:H17182108",
        "ETON": "CUSIP:29772L108",
        "VRT": "CUSIP:92537N108",
    }

    for ticker, expected_value in (
        expected.items()
    ):

        asset = find_asset(
            normalized,
            ticker,
        )

        identity = asset.get("identity")

        if not isinstance(identity, dict):
            raise RegressionTestError(
                "Identity missing."
            )

        actual = (
            serialize_security_identity(
                identity
            )
        )

        if actual != expected_value:
            raise RegressionTestError(
                (
                    f"{ticker}: identity "
                    "translation mismatch. "
                    f"Expected={expected_value}; "
                    f"actual={actual}"
                )
            )


def test_identity_continuity_not_verified_blocks(
    normalized: dict[str, Any],
) -> None:

    modified = deepcopy(normalized)

    asset = find_asset(
        modified,
        "CRSP",
    )

    asset[
        "identity"
    ][
        "identity_continuity_status"
    ] = "UNRESOLVED"

    expect_bridge_error(
        lambda:
            build_review_case(asset),
        "identity continuity not VERIFIED",
    )


def test_invalid_security_identity_blocks(
    normalized: dict[str, Any],
) -> None:

    modified = deepcopy(normalized)

    asset = find_asset(
        modified,
        "ETON",
    )

    asset[
        "identity"
    ][
        "security_identity"
    ] = None

    expect_bridge_error(
        lambda:
            build_review_case(asset),
        "security_identity must be object",
    )


def test_invalid_settlement_window_blocks(
    normalized: dict[str, Any],
) -> None:

    modified = deepcopy(normalized)

    asset = find_asset(
        modified,
        "VRT",
    )

    asset[
        "settlement_window"
    ][
        "previous_settlement_date"
    ] = ""

    expect_bridge_error(
        lambda:
            build_review_case(asset),
        "previous_settlement_date must not be empty",
    )


def test_missing_raw_evidence_blocks(
    normalized: dict[str, Any],
) -> None:

    modified = deepcopy(normalized)

    asset = find_asset(
        modified,
        "CRSP",
    )

    asset[
        "raw_upstream"
    ].pop(
        "corporate_action_evidence",
        None,
    )

    expect_bridge_error(
        lambda:
            build_review_case(asset),
        "raw Corporate Action evidence missing",
    )


def test_invalid_qualified_count_blocks(
    normalized: dict[str, Any],
) -> None:

    modified = deepcopy(normalized)

    asset = find_asset(
        modified,
        "ETON",
    )

    asset[
        "corporate_action_evidence"
    ][
        "qualified_evidence_count"
    ] = -1

    expect_bridge_error(
        lambda:
            build_review_case(asset),
        "qualified_evidence_count must be non-negative integer",
    )


def test_invalid_domain_blocks(
    normalized: dict[str, Any],
    policy: dict[str, Any],
) -> None:

    modified = deepcopy(normalized)

    modified["domain"] = (
        "INVALID_DOMAIN"
    )

    expect_bridge_error(
        lambda:
            run_bridge(
                modified,
                deepcopy(policy),
            ),
        "Invalid normalized input domain",
    )


def test_raw_normalized_input_not_mutated(
    normalized: dict[str, Any],
    policy: dict[str, Any],
) -> None:

    normalized_before = deepcopy(
        normalized
    )

    policy_before = deepcopy(
        policy
    )

    run_bridge(
        normalized,
        policy,
    )

    if normalized != normalized_before:
        raise RegressionTestError(
            (
                "Normalized input was "
                "mutated in memory."
            )
        )

    if policy != policy_before:
        raise RegressionTestError(
            (
                "Policy input was "
                "mutated in memory."
            )
        )


def run_test(
    number: int,
    name: str,
    function: Callable[[], None],
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
    print("REAL POSITIVE OFFICIAL REVIEW BRIDGE")
    print("REGRESSION TEST")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:

        normalized = read_json(
            NORMALIZED_FILE
        )

        policy = read_json(
            POLICY_FILE
        )

    except Exception as exc:

        print(
            "ERRO DE INICIALIZACAO:",
            exc,
        )

        return 1

    tests = [
        (
            "Real current state remains unresolved",
            lambda:
                test_real_current_state(
                    normalized,
                    policy,
                ),
        ),
        (
            "Bridge never invents authoritative review",
            lambda:
                test_no_authoritative_review_is_invented(
                    normalized
                ),
        ),
        (
            "CUSIP identity translation is deterministic",
            lambda:
                test_security_identity_translation(
                    normalized
                ),
        ),
        (
            "Unverified identity continuity blocks",
            lambda:
                test_identity_continuity_not_verified_blocks(
                    normalized
                ),
        ),
        (
            "Invalid security identity blocks",
            lambda:
                test_invalid_security_identity_blocks(
                    normalized
                ),
        ),
        (
            "Invalid settlement window blocks",
            lambda:
                test_invalid_settlement_window_blocks(
                    normalized
                ),
        ),
        (
            "Missing raw evidence blocks",
            lambda:
                test_missing_raw_evidence_blocks(
                    normalized
                ),
        ),
        (
            "Invalid qualified evidence count blocks",
            lambda:
                test_invalid_qualified_count_blocks(
                    normalized
                ),
        ),
        (
            "Invalid normalized domain blocks",
            lambda:
                test_invalid_domain_blocks(
                    normalized,
                    policy,
                ),
        ),
        (
            "Inputs are not mutated",
            lambda:
                test_raw_normalized_input_not_mutated(
                    normalized,
                    policy,
                ),
        ),
    ]

    passed = 0
    failed = 0

    for number, (
        name,
        function,
    ) in enumerate(
        tests,
        start=1,
    ):

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