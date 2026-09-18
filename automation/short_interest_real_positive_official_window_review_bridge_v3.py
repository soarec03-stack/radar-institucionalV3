"""
RADAR INSTITUCIONAL V3

SHORT INTEREST
REAL POSITIVE OFFICIAL WINDOW REVIEW BRIDGE

Version:
3.4D.2-B.2C.8C

Purpose:
Translate real normalized Short Interest / Corporate Action
inputs into the already-homologated Positive Official Window
Review Engine contract.

Important:

- no network access
- no new data collection
- no inference of NO_ACTION
- zero SEC matches does not prove NO_ACTION
- no authoritative review is invented
- no signal/confidence/score/decision
- radar_v3.json is not modified
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.8C"

BASE_DIR = Path(__file__).resolve().parent.parent

AUTOMATION_DIR = BASE_DIR / "automation"

if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(AUTOMATION_DIR),
    )


from short_interest_positive_official_window_review_v3 import (  # noqa: E402
    evaluate_case,
)


NORMALIZED_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_real_normalized_v3.json"
)

POLICY_FILE = (
    BASE_DIR
    / "automation"
    / "short_interest_positive_official_window_review_policy_v3.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_real_positive_official_review_v3.json"
)


class BridgeError(Exception):
    pass


def read_json(
    path: Path,
) -> dict[str, Any]:

    if not path.exists():
        raise BridgeError(
            f"Required file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise BridgeError(
            f"Root must be object: {path}"
        )

    return data


def non_empty_string(
    value: Any,
    field_name: str,
) -> str:

    if not isinstance(value, str):
        raise BridgeError(
            f"{field_name} must be string."
        )

    value = value.strip()

    if not value:
        raise BridgeError(
            f"{field_name} must not be empty."
        )

    return value


def non_negative_integer(
    value: Any,
    field_name: str,
) -> int:

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise BridgeError(
            f"{field_name} must be non-negative integer."
        )

    return value


def serialize_security_identity(
    identity: dict[str, Any],
) -> str:

    security_identity = identity.get(
        "security_identity"
    )

    if not isinstance(
        security_identity,
        dict,
    ):
        raise BridgeError(
            "security_identity must be object."
        )

    identity_type = non_empty_string(
        security_identity.get("type"),
        "security_identity.type",
    ).upper()

    identity_value = non_empty_string(
        security_identity.get("value"),
        "security_identity.value",
    ).upper()

    return (
        f"{identity_type}:"
        f"{identity_value}"
    )


def count_unresolved_candidates(
    evidence: dict[str, Any],
) -> int:
    """
    Conservative derivation.

    A candidate is considered unresolved when it has some
    indication of a possible Corporate Action but does not
    contain qualified evidence sufficient to resolve it.

    Zero text matches by itself is NOT evidence of NO_ACTION.

    This function only answers whether unresolved candidates
    exist for the B.2C.7B interface.
    """

    candidate_filings = evidence.get(
        "candidate_filings"
    )

    if not isinstance(
        candidate_filings,
        list,
    ):
        raise BridgeError(
            "candidate_filings must be list."
        )

    unresolved = 0

    for index, filing in enumerate(
        candidate_filings
    ):

        if not isinstance(filing, dict):
            raise BridgeError(
                (
                    "candidate_filings"
                    f"[{index}] must be object."
                )
            )

        text_matches_count = (
            filing.get(
                "text_matches_count"
            )
        )

        qualified_count = (
            filing.get(
                "qualified_evidence_count"
            )
        )

        if (
            not isinstance(
                text_matches_count,
                int,
            )
            or isinstance(
                text_matches_count,
                bool,
            )
            or text_matches_count < 0
        ):
            raise BridgeError(
                (
                    "Invalid filing "
                    "text_matches_count."
                )
            )

        if (
            not isinstance(
                qualified_count,
                int,
            )
            or isinstance(
                qualified_count,
                bool,
            )
            or qualified_count < 0
        ):
            raise BridgeError(
                (
                    "Invalid filing "
                    "qualified_evidence_count."
                )
            )

        candidate_action_type = (
            filing.get(
                "candidate_action_type"
            )
        )

        effective_date_candidate = (
            filing.get(
                "effective_date_candidate"
            )
        )

        ratio_candidate = (
            filing.get(
                "ratio_candidate"
            )
        )

        economic_relation = (
            filing.get(
                "economic_temporal_relation"
            )
        )

        has_action_indicator = any(
            (
                text_matches_count > 0,
                qualified_count > 0,
                candidate_action_type
                is not None,
                effective_date_candidate
                is not None,
                ratio_candidate
                is not None,
            )
        )

        if (
            has_action_indicator
            and (
                qualified_count == 0
                or economic_relation
                == "UNRESOLVED"
            )
        ):
            unresolved += 1

    return unresolved


def build_review_case(
    asset: dict[str, Any],
) -> dict[str, Any]:

    ticker = non_empty_string(
        asset.get("ticker"),
        "ticker",
    ).upper()

    identity = asset.get("identity")

    if not isinstance(identity, dict):
        raise BridgeError(
            f"{ticker}: identity missing."
        )

    if (
        identity.get(
            "identity_continuity_status"
        )
        != "VERIFIED"
    ):
        raise BridgeError(
            (
                f"{ticker}: identity "
                "continuity not VERIFIED."
            )
        )

    window = asset.get(
        "settlement_window"
    )

    if not isinstance(window, dict):
        raise BridgeError(
            f"{ticker}: settlement_window missing."
        )

    previous_date = non_empty_string(
        window.get(
            "previous_settlement_date"
        ),
        (
            f"{ticker}."
            "previous_settlement_date"
        ),
    )

    current_date = non_empty_string(
        window.get(
            "current_settlement_date"
        ),
        (
            f"{ticker}."
            "current_settlement_date"
        ),
    )

    evidence = asset.get(
        "corporate_action_evidence"
    )

    if not isinstance(evidence, dict):
        raise BridgeError(
            (
                f"{ticker}: "
                "corporate_action_evidence missing."
            )
        )

    qualified_count = (
        non_negative_integer(
            evidence.get(
                "qualified_evidence_count"
            ),
            (
                f"{ticker}."
                "qualified_evidence_count"
            ),
        )
    )

    raw_upstream = asset.get(
        "raw_upstream"
    )

    if not isinstance(
        raw_upstream,
        dict,
    ):
        raise BridgeError(
            f"{ticker}: raw_upstream missing."
        )

    raw_evidence = raw_upstream.get(
        "corporate_action_evidence"
    )

    if not isinstance(
        raw_evidence,
        dict,
    ):
        raise BridgeError(
            (
                f"{ticker}: raw Corporate "
                "Action evidence missing."
            )
        )

    raw_match_count = (
        non_negative_integer(
            raw_evidence.get(
                "text_matches_count"
            ),
            (
                f"{ticker}."
                "text_matches_count"
            ),
        )
    )

    unresolved_candidate_count = (
        count_unresolved_candidates(
            raw_evidence
        )
    )

    #
    # CRITICAL:
    #
    # No authoritative review exists in the current
    # real normalized input.
    #
    # Therefore the bridge MUST pass an empty list.
    #
    # It must NOT manufacture:
    #
    # NO_RELEVANT_ACTION_FOUND
    #
    authoritative_reviews: list[
        dict[str, Any]
    ] = []

    return {
        "case":
            f"REAL_{ticker}",

        "ticker":
            ticker,

        "identity": {
            "ticker":
                ticker,

            "listing_exchange":
                non_empty_string(
                    identity.get(
                        "listing_exchange"
                    ),
                    (
                        f"{ticker}."
                        "listing_exchange"
                    ),
                ),

            "security_identity":
                serialize_security_identity(
                    identity
                ),

            "continuity_status":
                "VERIFIED",
        },

        "previous_settlement_date":
            previous_date,

        "current_settlement_date":
            current_date,

        "sec_resolver": {
            "status":
                evidence.get(
                    "resolver_status"
                ),

            "raw_match_count":
                raw_match_count,

            "qualified_evidence_count":
                qualified_count,

            "unresolved_candidate_count":
                unresolved_candidate_count,
        },

        "authoritative_reviews":
            authoritative_reviews,
    }


def run_bridge(
    normalized: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:

    if (
        normalized.get("domain")
        != "SHORT_INTEREST_REAL_NORMALIZED"
    ):
        raise BridgeError(
            "Invalid normalized input domain."
        )

    assets = normalized.get("assets")

    if not isinstance(assets, list):
        raise BridgeError(
            "normalized.assets must be list."
        )

    if not assets:
        raise BridgeError(
            "normalized.assets must not be empty."
        )

    output_assets = []

    for asset in assets:

        if not isinstance(asset, dict):
            raise BridgeError(
                "Normalized asset must be object."
            )

        ticker = asset.get("ticker")

        review_case = build_review_case(
            asset
        )

        review_result = evaluate_case(
            review_case,
            policy,
        )

        output_assets.append(
            {
                "ticker":
                    ticker,

                "bridge_status":
                    "EVALUATED",

                "review_case":
                    review_case,

                "review_result":
                    review_result,

                "analytically_usable":
                    False,

                "downstream_status":
                    (
                        "READY_FOR_ADAPTER"
                        if review_result.get(
                            "reconciliation_eligible"
                        )
                        is True
                        else
                        "BLOCKED_PENDING_OFFICIAL_REVIEW"
                    ),
            }
        )

    total = len(output_assets)

    no_action = sum(
        1
        for asset in output_assets
        if asset[
            "review_result"
        ].get(
            "review_status"
        )
        == "NO_ACTION_PROVEN"
    )

    action_found = sum(
        1
        for asset in output_assets
        if asset[
            "review_result"
        ].get(
            "review_status"
        )
        == "ACTION_FOUND"
    )

    unresolved = sum(
        1
        for asset in output_assets
        if asset[
            "review_result"
        ].get(
            "review_status"
        )
        == "UNRESOLVED"
    )

    ready_for_adapter = sum(
        1
        for asset in output_assets
        if asset.get(
            "downstream_status"
        )
        == "READY_FOR_ADAPTER"
    )

    return {
        "bridge_version":
            VERSION,

        "domain":
            (
                "SHORT_INTEREST_REAL_"
                "POSITIVE_OFFICIAL_REVIEW"
            ),

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat().replace(
                "+00:00",
                "Z",
            ),

        "source_file":
            str(
                NORMALIZED_FILE.relative_to(
                    BASE_DIR
                )
            ).replace("\\", "/"),

        "summary": {
            "total_assets":
                total,

            "no_action_proven":
                no_action,

            "action_found":
                action_found,

            "unresolved":
                unresolved,

            "ready_for_adapter":
                ready_for_adapter,

            "analytically_usable":
                0,
        },

        "assets":
            output_assets,
    }


def atomic_write_json(
    path: Path,
    data: dict[str, Any],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")

    temporary.replace(path)


def main() -> int:

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST")
    print("REAL POSITIVE OFFICIAL WINDOW REVIEW BRIDGE")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:

        normalized = read_json(
            NORMALIZED_FILE
        )

        policy = read_json(
            POLICY_FILE
        )

        result = run_bridge(
            normalized,
            policy,
        )

        atomic_write_json(
            OUTPUT_FILE,
            result,
        )

    except Exception as exc:

        print("RESULTADO: BLOCKED")
        print("ERRO:", exc)

        return 1

    for asset in result["assets"]:

        review = asset[
            "review_result"
        ]

        print(
            asset["ticker"],
            "| review=",
            review.get(
                "review_status"
            ),
            "| CA=",
            review.get(
                "corporate_action_status"
            ),
            "| eligible=",
            review.get(
                "reconciliation_eligible"
            ),
            "| downstream=",
            asset.get(
                "downstream_status"
            ),
        )

    print("-" * 72)

    for key, value in (
        result["summary"].items()
    ):
        print(
            key.upper(),
            ":",
            value,
        )

    print(
        "OUTPUT:",
        OUTPUT_FILE,
    )

    print("RESULTADO: PASS")

    return 0


if __name__ == "__main__":
    sys.exit(main())