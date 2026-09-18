"""
RADAR INSTITUCIONAL V3

SHORT INTEREST
REAL INPUT NORMALIZER
REGRESSION TEST

Version:
3.4D.2-B.2C.8B.1
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


from short_interest_real_input_normalizer_v3 import (  # noqa: E402
    COLLECTION_FILE,
    EVIDENCE_FILE,
    NormalizationError,
    normalize_documents,
    read_json,
)


VERSION = "3.4D.2-B.2C.8B.1"


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
            (
                f"Expected exactly one "
                f"{ticker} asset."
            )
        )

    return matches[0]


def expect_normalization_error(
    function: Callable[[], Any],
    expected_text: str,
) -> None:

    try:
        function()

    except NormalizationError as exc:

        if expected_text not in str(exc):
            raise RegressionTestError(
                (
                    "Unexpected error. "
                    f"Expected text={expected_text!r}; "
                    f"actual={str(exc)!r}"
                )
            )

        return

    raise RegressionTestError(
        "Expected NormalizationError."
    )


def test_real_happy_path(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> None:

    result = normalize_documents(
        deepcopy(collection),
        deepcopy(evidence),
    )

    summary = result.get("summary", {})

    if summary.get("total_assets") != 3:
        raise RegressionTestError(
            "Expected 3 real assets."
        )

    if summary.get("normalized") != 3:
        raise RegressionTestError(
            "Expected 3 normalized assets."
        )

    if summary.get("blocked") != 0:
        raise RegressionTestError(
            "Expected zero blocked assets."
        )

    if (
        summary.get("analytically_usable")
        != 0
    ):
        raise RegressionTestError(
            (
                "Normalizer must not make "
                "assets analytically usable."
            )
        )

    if (
        summary.get(
            "pending_positive_official_review"
        )
        != 3
    ):
        raise RegressionTestError(
            "All assets must remain pending review."
        )

    assets = result.get("assets", [])

    tickers = [
        asset.get("ticker")
        for asset in assets
    ]

    if tickers != [
        "CRSP",
        "ETON",
        "VRT",
    ]:
        raise RegressionTestError(
            (
                "Unexpected normalized "
                f"ticker order: {tickers}"
            )
        )

    for asset in assets:

        if (
            asset.get(
                "normalization_status"
            )
            != "NORMALIZED"
        ):
            raise RegressionTestError(
                "Invalid normalization status."
            )

        if (
            asset.get(
                "structurally_compatible"
            )
            is not True
        ):
            raise RegressionTestError(
                "Asset must be structurally compatible."
            )

        if (
            asset.get(
                "corporate_action_status"
            )
            != "NOT_CHECKED"
        ):
            raise RegressionTestError(
                (
                    "Normalizer must not infer "
                    "Corporate Action status."
                )
            )

        if (
            asset.get(
                "positive_official_review_status"
            )
            != "NOT_CHECKED"
        ):
            raise RegressionTestError(
                (
                    "Normalizer must not infer "
                    "positive official review."
                )
            )

        if (
            asset.get(
                "reconciliation_pipeline_status"
            )
            != "PENDING_REVIEW"
        ):
            raise RegressionTestError(
                (
                    "Normalized real asset must "
                    "remain PENDING_REVIEW."
                )
            )

        if (
            asset.get(
                "analytically_usable"
            )
            is not False
        ):
            raise RegressionTestError(
                (
                    "Normalizer must never "
                    "promote usability."
                )
            )

        identity = asset.get(
            "identity",
        )

        if not isinstance(
            identity,
            dict,
        ):
            raise RegressionTestError(
                "Normalized identity missing."
            )

        security_identity = (
            identity.get(
                "security_identity"
            )
        )

        if not isinstance(
            security_identity,
            dict,
        ):
            raise RegressionTestError(
                "security_identity missing."
            )

        if (
            security_identity.get("type")
            != "CUSIP"
        ):
            raise RegressionTestError(
                "security_identity must preserve CUSIP type."
            )

        if not security_identity.get(
            "value"
        ):
            raise RegressionTestError(
                "security_identity value missing."
            )

        raw_upstream = asset.get(
            "raw_upstream"
        )

        if not isinstance(
            raw_upstream,
            dict,
        ):
            raise RegressionTestError(
                "raw_upstream missing."
            )

        if (
            "short_interest_collection"
            not in raw_upstream
        ):
            raise RegressionTestError(
                "Collection raw record not preserved."
            )

        if (
            "corporate_action_evidence"
            not in raw_upstream
        ):
            raise RegressionTestError(
                "Evidence raw record not preserved."
            )


def test_identity_mismatch(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> None:

    modified = deepcopy(evidence)

    asset = find_asset(
        modified,
        "CRSP",
    )

    asset["identity"]["cusip"] = (
        "INVALIDCUSIP"
    )

    expect_normalization_error(
        lambda:
            normalize_documents(
                deepcopy(collection),
                modified,
            ),
        "CUSIP mismatch",
    )


def test_settlement_window_mismatch(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> None:

    modified = deepcopy(evidence)

    asset = find_asset(
        modified,
        "ETON",
    )

    asset[
        "settlement_window"
    ][
        "previous_settlement_date"
    ] = "2026-08-13"

    expect_normalization_error(
        lambda:
            normalize_documents(
                deepcopy(collection),
                modified,
            ),
        "settlement window mismatch",
    )


def test_missing_asset(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> None:

    modified = deepcopy(evidence)

    modified["assets"] = [
        asset
        for asset in modified["assets"]
        if asset.get("ticker") != "VRT"
    ]

    expect_normalization_error(
        lambda:
            normalize_documents(
                deepcopy(collection),
                modified,
            ),
        "Asset universe mismatch",
    )


def test_duplicate_ticker(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> None:

    modified = deepcopy(collection)

    crsp = find_asset(
        modified,
        "CRSP",
    )

    modified["assets"].append(
        deepcopy(crsp)
    )

    expect_normalization_error(
        lambda:
            normalize_documents(
                modified,
                deepcopy(evidence),
            ),
        "Duplicate ticker CRSP",
    )


def test_non_tier_1_short_interest(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> None:

    modified = deepcopy(collection)

    asset = find_asset(
        modified,
        "CRSP",
    )

    asset[
        "provenance"
    ][
        "source_tier"
    ] = "TIER_2"

    expect_normalization_error(
        lambda:
            normalize_documents(
                modified,
                deepcopy(evidence),
            ),
        "Short Interest source must be TIER_1",
    )


def test_non_tier_1_evidence(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> None:

    modified = deepcopy(evidence)

    asset = find_asset(
        modified,
        "CRSP",
    )

    asset[
        "source"
    ][
        "source_tier"
    ] = "TIER_2"

    expect_normalization_error(
        lambda:
            normalize_documents(
                deepcopy(collection),
                modified,
            ),
        (
            "Corporate Action evidence "
            "source must be TIER_1"
        ),
    )


def test_zero_evidence_does_not_become_no_action(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> None:

    modified = deepcopy(evidence)

    for asset in modified["assets"]:

        asset[
            "resolver_status"
        ] = "RESOLVED"

        asset[
            "qualified_evidence_count"
        ] = 0

        asset[
            "text_matches_count"
        ] = 0

        asset[
            "analytically_conclusive"
        ] = False

    result = normalize_documents(
        deepcopy(collection),
        modified,
    )

    for asset in result["assets"]:

        if (
            asset.get(
                "corporate_action_status"
            )
            == "NO_ACTION"
        ):
            raise RegressionTestError(
                (
                    "Zero evidence must never "
                    "become NO_ACTION."
                )
            )

        if (
            asset.get(
                "positive_official_review_status"
            )
            != "NOT_CHECKED"
        ):
            raise RegressionTestError(
                (
                    "Zero evidence must remain "
                    "pending official review."
                )
            )

        if (
            asset.get(
                "analytically_usable"
            )
            is not False
        ):
            raise RegressionTestError(
                (
                    "Zero evidence must not "
                    "become analytically usable."
                )
            )


def test_raw_inputs_not_mutated(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> None:

    collection_before = deepcopy(
        collection
    )

    evidence_before = deepcopy(
        evidence
    )

    normalize_documents(
        collection,
        evidence,
    )

    if collection != collection_before:
        raise RegressionTestError(
            (
                "Collection input was "
                "mutated in memory."
            )
        )

    if evidence != evidence_before:
        raise RegressionTestError(
            (
                "Evidence input was "
                "mutated in memory."
            )
        )


def test_previous_short_interest_zero_blocks(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> None:

    modified = deepcopy(collection)

    asset = find_asset(
        modified,
        "VRT",
    )

    asset[
        "metric"
    ][
        "raw"
    ][
        "previous_short_interest_shares"
    ] = 0

    expect_normalization_error(
        lambda:
            normalize_documents(
                modified,
                deepcopy(evidence),
            ),
        (
            "previous_short_interest_shares "
            "must be positive integer"
        ),
    )


def run_test(
    number: int,
    name: str,
    function: Callable[[], None],
) -> bool:

    print("-" * 72)
    print(
        f"TESTE {number}: {name}"
    )

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
    print("REAL INPUT NORMALIZER REGRESSION TEST")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:

        collection = read_json(
            COLLECTION_FILE
        )

        evidence = read_json(
            EVIDENCE_FILE
        )

    except Exception as exc:

        print(
            "ERRO DE INICIALIZACAO:",
            exc,
        )

        return 1

    tests = [
        (
            "Real happy path",
            lambda:
                test_real_happy_path(
                    collection,
                    evidence,
                ),
        ),
        (
            "Identity mismatch blocks",
            lambda:
                test_identity_mismatch(
                    collection,
                    evidence,
                ),
        ),
        (
            "Settlement window mismatch blocks",
            lambda:
                test_settlement_window_mismatch(
                    collection,
                    evidence,
                ),
        ),
        (
            "Missing asset blocks",
            lambda:
                test_missing_asset(
                    collection,
                    evidence,
                ),
        ),
        (
            "Duplicate ticker blocks",
            lambda:
                test_duplicate_ticker(
                    collection,
                    evidence,
                ),
        ),
        (
            "Non-TIER_1 Short Interest blocks",
            lambda:
                test_non_tier_1_short_interest(
                    collection,
                    evidence,
                ),
        ),
        (
            "Non-TIER_1 CA evidence blocks",
            lambda:
                test_non_tier_1_evidence(
                    collection,
                    evidence,
                ),
        ),
        (
            "Zero evidence never becomes NO_ACTION",
            lambda:
                test_zero_evidence_does_not_become_no_action(
                    collection,
                    evidence,
                ),
        ),
        (
            "Raw inputs are not mutated",
            lambda:
                test_raw_inputs_not_mutated(
                    collection,
                    evidence,
                ),
        ),
        (
            "Previous Short Interest zero blocks",
            lambda:
                test_previous_short_interest_zero_blocks(
                    collection,
                    evidence,
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

    print(
        "Total :",
        len(tests),
    )

    print(
        "PASS  :",
        passed,
    )

    print(
        "FAIL  :",
        failed,
    )

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