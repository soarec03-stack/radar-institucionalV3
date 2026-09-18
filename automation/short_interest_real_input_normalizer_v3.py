"""
RADAR INSTITUCIONAL V3

SHORT INTEREST
REAL INPUT NORMALIZER

Version:
3.4D.2-B.2C.8B

Purpose:
Normalize and safely join real Short Interest Collection data
with real Corporate Action Evidence data.

This component:

- does not access the network
- does not collect new data
- does not infer NO_ACTION
- does not perform Corporate Action reconciliation
- does not calculate Signal, Confidence, Radar Score or Decision
- does not mutate radar_v3.json
- preserves raw upstream records
- fails closed on identity/window inconsistencies
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.8B"

BASE_DIR = Path(__file__).resolve().parent.parent

COLLECTION_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_collection_v3.json"
)

EVIDENCE_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_corporate_action_evidence_v3.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "input"
    / "short_interest_real_normalized_v3.json"
)


class NormalizationError(Exception):
    pass


def read_json(
    path: Path,
) -> dict[str, Any]:

    if not path.exists():
        raise NormalizationError(
            f"Required input file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise NormalizationError(
            f"Root must be object: {path}"
        )

    return data


def require_non_empty_string(
    value: Any,
    field_name: str,
) -> str:

    if not isinstance(value, str):
        raise NormalizationError(
            f"{field_name} must be string."
        )

    value = value.strip()

    if not value:
        raise NormalizationError(
            f"{field_name} must not be empty."
        )

    return value


def require_positive_integer(
    value: Any,
    field_name: str,
) -> int:

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise NormalizationError(
            f"{field_name} must be positive integer."
        )

    return value


def index_assets(
    document: dict[str, Any],
    document_name: str,
) -> dict[str, dict[str, Any]]:

    assets = document.get("assets")

    if not isinstance(assets, list):
        raise NormalizationError(
            f"{document_name}.assets must be list."
        )

    if not assets:
        raise NormalizationError(
            f"{document_name}.assets must not be empty."
        )

    indexed: dict[str, dict[str, Any]] = {}

    for position, asset in enumerate(assets):

        if not isinstance(asset, dict):
            raise NormalizationError(
                (
                    f"{document_name}.assets[{position}] "
                    "must be object."
                )
            )

        ticker = require_non_empty_string(
            asset.get("ticker"),
            (
                f"{document_name}.assets"
                f"[{position}].ticker"
            ),
        ).upper()

        if ticker in indexed:
            raise NormalizationError(
                (
                    f"Duplicate ticker {ticker} "
                    f"in {document_name}."
                )
            )

        indexed[ticker] = asset

    return indexed


def extract_collection_window(
    asset: dict[str, Any],
) -> dict[str, str]:

    previous_snapshot = asset.get(
        "previous_settlement_snapshot"
    )

    metric = asset.get("metric")

    if not isinstance(previous_snapshot, dict):
        raise NormalizationError(
            "Missing previous_settlement_snapshot."
        )

    if not isinstance(metric, dict):
        raise NormalizationError(
            "Missing metric."
        )

    previous_date = require_non_empty_string(
        previous_snapshot.get("settlement_date"),
        "collection.previous_settlement_date",
    )

    current_date = require_non_empty_string(
        metric.get("settlement_date"),
        "collection.current_settlement_date",
    )

    if current_date <= previous_date:
        raise NormalizationError(
            (
                "Collection current settlement date "
                "must be after previous settlement date."
            )
        )

    return {
        "previous_settlement_date":
            previous_date,

        "current_settlement_date":
            current_date,
    }


def extract_evidence_window(
    asset: dict[str, Any],
) -> dict[str, str]:

    window = asset.get("settlement_window")

    if not isinstance(window, dict):
        raise NormalizationError(
            "Missing evidence settlement_window."
        )

    previous_date = require_non_empty_string(
        window.get("previous_settlement_date"),
        "evidence.previous_settlement_date",
    )

    current_date = require_non_empty_string(
        window.get("current_settlement_date"),
        "evidence.current_settlement_date",
    )

    if current_date <= previous_date:
        raise NormalizationError(
            (
                "Evidence current settlement date "
                "must be after previous settlement date."
            )
        )

    return {
        "previous_settlement_date":
            previous_date,

        "current_settlement_date":
            current_date,
    }


def extract_identity(
    ticker: str,
    collection_asset: dict[str, Any],
    evidence_asset: dict[str, Any],
) -> dict[str, Any]:

    collection_identity = collection_asset.get(
        "identity"
    )

    evidence_identity = evidence_asset.get(
        "identity"
    )

    if not isinstance(
        collection_identity,
        dict,
    ):
        raise NormalizationError(
            f"{ticker}: collection identity missing."
        )

    if not isinstance(
        evidence_identity,
        dict,
    ):
        raise NormalizationError(
            f"{ticker}: evidence identity missing."
        )

    collection_exchange = (
        require_non_empty_string(
            collection_identity.get(
                "listing_exchange"
            ),
            f"{ticker}.collection.listing_exchange",
        )
        .upper()
    )

    evidence_exchange = (
        require_non_empty_string(
            evidence_identity.get(
                "listing_exchange"
            ),
            f"{ticker}.evidence.listing_exchange",
        )
        .upper()
    )

    collection_cusip = (
        require_non_empty_string(
            collection_identity.get("cusip"),
            f"{ticker}.collection.cusip",
        )
        .upper()
    )

    evidence_cusip = (
        require_non_empty_string(
            evidence_identity.get("cusip"),
            f"{ticker}.evidence.cusip",
        )
        .upper()
    )

    collection_issuer = (
        require_non_empty_string(
            collection_identity.get(
                "issuer_name"
            ),
            f"{ticker}.collection.issuer_name",
        )
    )

    evidence_issuer = (
        require_non_empty_string(
            evidence_identity.get(
                "issuer_name"
            ),
            f"{ticker}.evidence.issuer_name",
        )
    )

    if (
        collection_exchange
        != evidence_exchange
    ):
        raise NormalizationError(
            f"{ticker}: listing exchange mismatch."
        )

    if collection_cusip != evidence_cusip:
        raise NormalizationError(
            f"{ticker}: CUSIP mismatch."
        )

    if collection_issuer != evidence_issuer:
        raise NormalizationError(
            f"{ticker}: issuer name mismatch."
        )

    sec_cik = require_non_empty_string(
        evidence_identity.get("sec_cik"),
        f"{ticker}.evidence.sec_cik",
    )

    return {
        "ticker": ticker,

        "listing_exchange":
            collection_exchange,

        "issuer_name":
            collection_issuer,

        "security_identity": {
            "type": "CUSIP",
            "value": collection_cusip,
        },

        "cusip":
            collection_cusip,

        "sec_cik":
            sec_cik,

        "identity_continuity_status":
            "VERIFIED",
    }


def extract_short_interest_fact(
    ticker: str,
    asset: dict[str, Any],
) -> dict[str, Any]:

    metric = asset.get("metric")

    if not isinstance(metric, dict):
        raise NormalizationError(
            f"{ticker}: metric missing."
        )

    raw = metric.get("raw")

    calculated = metric.get("calculated")

    if not isinstance(raw, dict):
        raise NormalizationError(
            f"{ticker}: metric.raw missing."
        )

    if not isinstance(calculated, dict):
        raise NormalizationError(
            f"{ticker}: metric.calculated missing."
        )

    current_shares = require_positive_integer(
        raw.get(
            "current_short_interest_shares"
        ),
        (
            f"{ticker}."
            "current_short_interest_shares"
        ),
    )

    previous_shares = require_positive_integer(
        raw.get(
            "previous_short_interest_shares"
        ),
        (
            f"{ticker}."
            "previous_short_interest_shares"
        ),
    )

    return {
        "metric_name":
            metric.get("name"),

        "unit":
            metric.get("unit"),

        "previous_short_interest_shares":
            previous_shares,

        "current_short_interest_shares":
            current_shares,

        "collector_calculated_change_shares":
            calculated.get("change_shares"),

        "collector_calculated_change_pct":
            calculated.get("change_pct"),

        "source_reported_change_shares":
            raw.get("finra_change_shares"),

        "source_reported_change_pct":
            raw.get("finra_change_pct"),

        "average_daily_volume_shares":
            raw.get(
                "average_daily_volume_shares"
            ),

        "days_to_cover":
            raw.get("days_to_cover"),

        "cross_check":
            deepcopy(
                metric.get("cross_check")
            ),

        "continuity_check":
            deepcopy(
                metric.get(
                    "continuity_check"
                )
            ),
    }


def validate_source(
    ticker: str,
    collection_asset: dict[str, Any],
    evidence_asset: dict[str, Any],
) -> dict[str, Any]:

    provenance = collection_asset.get(
        "provenance"
    )

    evidence_source = evidence_asset.get(
        "source"
    )

    if not isinstance(provenance, dict):
        raise NormalizationError(
            f"{ticker}: collection provenance missing."
        )

    if not isinstance(evidence_source, dict):
        raise NormalizationError(
            f"{ticker}: evidence source missing."
        )

    collection_source = (
        require_non_empty_string(
            provenance.get("source"),
            f"{ticker}.collection.source",
        )
        .upper()
    )

    collection_tier = (
        require_non_empty_string(
            provenance.get("source_tier"),
            f"{ticker}.collection.source_tier",
        )
        .upper()
    )

    evidence_source_type = (
        require_non_empty_string(
            evidence_source.get("source_type"),
            f"{ticker}.evidence.source_type",
        )
        .upper()
    )

    evidence_tier = (
        require_non_empty_string(
            evidence_source.get("source_tier"),
            f"{ticker}.evidence.source_tier",
        )
        .upper()
    )

    if collection_tier != "TIER_1":
        raise NormalizationError(
            (
                f"{ticker}: Short Interest "
                "source must be TIER_1."
            )
        )

    if evidence_tier != "TIER_1":
        raise NormalizationError(
            (
                f"{ticker}: Corporate Action "
                "evidence source must be TIER_1."
            )
        )

    return {
        "short_interest": {
            "source": collection_source,
            "source_tier": collection_tier,
            "dataset":
                provenance.get("dataset"),
            "retrieved_at":
                provenance.get("retrieved_at"),
            "market_date":
                provenance.get("market_date"),
            "verification_status":
                provenance.get(
                    "verification_status"
                ),
        },

        "corporate_action_evidence": {
            "source":
                evidence_source.get("source"),
            "source_type":
                evidence_source_type,
            "source_tier":
                evidence_tier,
        },
    }


def normalize_asset(
    ticker: str,
    collection_asset: dict[str, Any],
    evidence_asset: dict[str, Any],
) -> dict[str, Any]:

    collection_window = (
        extract_collection_window(
            collection_asset
        )
    )

    evidence_window = (
        extract_evidence_window(
            evidence_asset
        )
    )

    if collection_window != evidence_window:
        raise NormalizationError(
            (
                f"{ticker}: settlement "
                "window mismatch."
            )
        )

    identity = extract_identity(
        ticker,
        collection_asset,
        evidence_asset,
    )

    short_interest_fact = (
        extract_short_interest_fact(
            ticker,
            collection_asset,
        )
    )

    sources = validate_source(
        ticker,
        collection_asset,
        evidence_asset,
    )

    return {
        "ticker": ticker,

        "normalization_status":
            "NORMALIZED",

        "structurally_compatible":
            True,

        "identity":
            identity,

        "settlement_window":
            collection_window,

        "short_interest":
            short_interest_fact,

        "corporate_action_evidence": {
            "resolver_status":
                evidence_asset.get(
                    "resolver_status"
                ),

            "analytically_conclusive":
                evidence_asset.get(
                    "analytically_conclusive"
                ),

            "reconciliation_required":
                evidence_asset.get(
                    "reconciliation_required"
                ),

            "reconciliation_status":
                evidence_asset.get(
                    "reconciliation_status"
                ),

            "reason":
                evidence_asset.get("reason"),

            "candidate_filings_count":
                evidence_asset.get(
                    "candidate_filings_count"
                ),

            "fetched_filings_count":
                evidence_asset.get(
                    "fetched_filings_count"
                ),

            "failed_filings_count":
                evidence_asset.get(
                    "failed_filings_count"
                ),

            "text_matches_count":
                evidence_asset.get(
                    "text_matches_count"
                ),

            "qualified_evidence_count":
                evidence_asset.get(
                    "qualified_evidence_count"
                ),

            "candidate_filings":
                deepcopy(
                    evidence_asset.get(
                        "candidate_filings",
                        [],
                    )
                ),

            "diagnostics":
                deepcopy(
                    evidence_asset.get(
                        "diagnostics",
                        [],
                    )
                ),
        },

        "sources":
            sources,

        # Critical:
        # normalization never proves NO_ACTION.
        "corporate_action_status":
            "NOT_CHECKED",

        "positive_official_review_status":
            "NOT_CHECKED",

        "reconciliation_pipeline_status":
            "PENDING_REVIEW",

        "analytically_usable":
            False,

        "raw_upstream": {
            "short_interest_collection":
                deepcopy(collection_asset),

            "corporate_action_evidence":
                deepcopy(evidence_asset),
        },

        "diagnostics": [],
    }


def normalize_documents(
    collection: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:

    if (
        collection.get("domain")
        != "SHORT_INTEREST"
    ):
        raise NormalizationError(
            "Invalid collection domain."
        )

    if (
        evidence.get("domain")
        != "SHORT_INTEREST_CORPORATE_ACTION_EVIDENCE"
    ):
        raise NormalizationError(
            "Invalid evidence domain."
        )

    collection_assets = index_assets(
        collection,
        "collection",
    )

    evidence_assets = index_assets(
        evidence,
        "evidence",
    )

    collection_tickers = set(
        collection_assets
    )

    evidence_tickers = set(
        evidence_assets
    )

    if (
        collection_tickers
        != evidence_tickers
    ):
        missing_evidence = sorted(
            collection_tickers
            - evidence_tickers
        )

        missing_collection = sorted(
            evidence_tickers
            - collection_tickers
        )

        raise NormalizationError(
            (
                "Asset universe mismatch. "
                f"missing_evidence={missing_evidence}; "
                f"missing_collection={missing_collection}"
            )
        )

    normalized_assets = []

    for ticker in sorted(
        collection_tickers
    ):

        normalized_assets.append(
            normalize_asset(
                ticker,
                collection_assets[ticker],
                evidence_assets[ticker],
            )
        )

    return {
        "normalizer_version":
            VERSION,

        "domain":
            "SHORT_INTEREST_REAL_NORMALIZED",

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat().replace(
                "+00:00",
                "Z",
            ),

        "source_files": {
            "short_interest_collection":
                str(
                    COLLECTION_FILE.relative_to(
                        BASE_DIR
                    )
                ).replace("\\", "/"),

            "corporate_action_evidence":
                str(
                    EVIDENCE_FILE.relative_to(
                        BASE_DIR
                    )
                ).replace("\\", "/"),
        },

        "upstream_versions": {
            "collector_version":
                collection.get(
                    "collector_version"
                ),

            "universe_version":
                collection.get(
                    "universe_version"
                ),

            "resolver_version":
                evidence.get(
                    "resolver_version"
                ),

            "evidence_schema_version":
                evidence.get(
                    "schema_version"
                ),
        },

        "summary": {
            "total_assets":
                len(normalized_assets),

            "normalized":
                len(normalized_assets),

            "blocked":
                0,

            "analytically_usable":
                0,

            "pending_positive_official_review":
                len(normalized_assets),
        },

        "assets":
            normalized_assets,
    }


def atomic_write_json(
    path: Path,
    data: dict[str, Any],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary_path.open(
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

    temporary_path.replace(path)


def main() -> int:

    print("=" * 72)
    print("RADAR INSTITUCIONAL V3")
    print("SHORT INTEREST REAL INPUT NORMALIZER")
    print(f"VERSION {VERSION}")
    print("=" * 72)

    try:

        collection = read_json(
            COLLECTION_FILE
        )

        evidence = read_json(
            EVIDENCE_FILE
        )

        normalized = normalize_documents(
            collection,
            evidence,
        )

        atomic_write_json(
            OUTPUT_FILE,
            normalized,
        )

    except Exception as exc:

        print("RESULTADO: BLOCKED")
        print("ERRO:", exc)

        return 1

    for asset in normalized["assets"]:

        print(
            asset["ticker"],
            "|",
            asset["normalization_status"],
            "|",
            asset["settlement_window"][
                "previous_settlement_date"
            ],
            "->",
            asset["settlement_window"][
                "current_settlement_date"
            ],
            "| review=",
            asset[
                "positive_official_review_status"
            ],
            "| usable=",
            asset["analytically_usable"],
        )

    print("-" * 72)

    print(
        "TOTAL:",
        normalized["summary"]["total_assets"],
    )

    print(
        "NORMALIZED:",
        normalized["summary"]["normalized"],
    )

    print(
        "PENDING REVIEW:",
        normalized["summary"][
            "pending_positive_official_review"
        ],
    )

    print(
        "ANALYTICALLY USABLE:",
        normalized["summary"][
            "analytically_usable"
        ],
    )

    print(
        "OUTPUT:",
        OUTPUT_FILE,
    )

    print("RESULTADO: PASS")

    return 0


if __name__ == "__main__":
    sys.exit(main())