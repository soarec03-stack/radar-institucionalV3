"""
RADAR INSTITUCIONAL V3
V3.4D.2-B.2B-R1 - SEC CORPORATE ACTION EVIDENCE RESOLVER

Coleta evidencias SEC/EDGAR para a janela de Short Interest.
Nao altera registry, radar_v3.json, Signal, Confidence, Score ou Decision.
Nao converte ausencia de evidencia em NO_ACTION.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

VERSION = "3.4D.2-B.2B-R1"
UNIVERSE = Path("automation/asset_universe_v3.json")
COLLECTION = Path("input/short_interest_collection_v3.json")
OUTPUT = Path("input/short_interest_corporate_action_evidence_v3.json")
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
PRE_DAYS = 45
POST_DAYS = 15
REQUEST_INTERVAL = 0.20
TIMEOUT = 30

FORMS = {
    "8-K", "8-K/A", "6-K", "6-K/A", "10-Q", "10-Q/A",
    "10-K", "10-K/A", "20-F", "20-F/A",
    "DEF 14A", "DEFA14A", "PRE 14A",
}

PATTERNS = {
    "REVERSE_STOCK_SPLIT": re.compile(
        r"\breverse\s+(?:stock\s+|share\s+)?split\b|"
        r"\bshare\s+consolidation\b", re.I
    ),
    "STOCK_SPLIT": re.compile(
        r"(?<!reverse\s)\b(?:stock|share)\s+split\b|"
        r"\bforward\s+(?:stock|share)\s+split\b", re.I
    ),
    "CUSIP_CHANGE": re.compile(
        r"\b(?:new|changed?|change\s+in)\s+CUSIP\b|"
        r"\bCUSIP\s+(?:number\s+)?(?:will\s+)?change\b|"
        r"\bassigned\s+a\s+new\s+CUSIP\b", re.I
    ),
    # Deliberately narrower than the previous generic "reclassif..." regex.
    # A reclassification match must be tied to shares/capital stock.
    "RECLASSIFICATION": re.compile(
        r"\breclassif(?:y|ied|ication)\b.{0,120}?"
        r"\b(?:common\s+stock|capital\s+stock|ordinary\s+shares?|shares?)\b|"
        r"\b(?:common\s+stock|capital\s+stock|ordinary\s+shares?|shares?)\b"
        r".{0,120}?\breclassif(?:y|ied|ication)\b",
        re.I | re.S
    ),
}

RATIO = re.compile(r"\b(\d+)\s*[- ]for[- ]\s*(\d+)\b", re.I)
EVERY_INTO = re.compile(
    r"\bevery\s+(\d+)\s+shares?.{0,160}?"
    r"(?:into|for)\s+(?:one|1)\s+share\b",
    re.I | re.S,
)
DATE_PATTERNS = [
    re.compile(
        r"(?:effective|effected|become effective|became effective)"
        r"(?:\s+for\s+trading\s+purposes)?"
        r"(?:\s+as\s+of|\s+on|\s+at)?\s+"
        r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", re.I
    ),
    re.compile(
        r"(?:effective|effected|become effective|became effective)"
        r"(?:\s+for\s+trading\s+purposes)?"
        r"(?:\s+as\s+of|\s+on|\s+at)?\s+"
        r"(\d{4}-\d{2}-\d{2})", re.I
    ),
]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        return " ".join(self.parts)


class SecClient:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        self.last_request = 0.0

    def get_bytes(self, url: str) -> tuple[bytes, str]:
        wait = REQUEST_INTERVAL - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)

        req = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json,text/html,text/plain,*/*",
                # Do not request gzip here. urllib does not transparently
                # decompress it in the same way as Invoke-WebRequest.
            },
        )
        try:
            with urlopen(req, timeout=TIMEOUT) as response:
                body = response.read()
                content_type = response.headers.get("Content-Type", "")
        except HTTPError as exc:
            raise RuntimeError(f"SEC HTTP {exc.code}: {url}") from exc
        except URLError as exc:
            raise RuntimeError(f"SEC network error: {exc.reason}") from exc
        finally:
            self.last_request = time.monotonic()

        return body, content_type

    def get_json(self, url: str) -> dict[str, Any]:
        body, _ = self.get_bytes(url)
        try:
            value = json.loads(body.decode("utf-8-sig"))
        except Exception as exc:
            raise RuntimeError(f"SEC JSON invalido: {url}") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"SEC JSON root invalido: {url}")
        return value

    def get_text(self, url: str) -> str:
        body, content_type = self.get_bytes(url)
        raw = body.decode("utf-8", errors="replace")
        if "html" in content_type.lower() or "<html" in raw[:1000].lower():
            parser = TextExtractor()
            parser.feed(raw)
            raw = parser.get_text()
        return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Arquivo nao encontrado: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"JSON invalido {path}: linha {exc.lineno}, coluna {exc.colno}"
        ) from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Objeto JSON esperado: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def iso_date(value: Any, name: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{name} ausente")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} invalida: {value!r}") from exc


def canonical_cik(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{10}", value.strip()):
        raise ValueError("sec_cik deve possuir exatamente 10 digitos")
    return value.strip()


def collection_map(collection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    assets = collection.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("collection.assets deve ser lista")
    result = {}
    for asset in assets:
        if isinstance(asset, dict) and isinstance(asset.get("ticker"), str):
            result[asset["ticker"].strip().upper()] = asset
    return result


def settlement_window(asset: dict[str, Any]) -> tuple[date, date]:
    prev = asset.get("previous_settlement_snapshot")
    metric = asset.get("metric")
    if not isinstance(prev, dict) or not isinstance(metric, dict):
        raise ValueError("janela de settlement incompleta")
    p = iso_date(prev.get("settlement_date"), "previous_settlement_date")
    c = iso_date(metric.get("settlement_date"), "current_settlement_date")
    if c <= p:
        raise ValueError("current settlement deve ser posterior ao previous")
    return p, c


def recent_rows(submissions: dict[str, Any]) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        return []
    keys = (
        "accessionNumber", "filingDate", "reportDate",
        "acceptanceDateTime", "form", "items",
        "primaryDocument", "primaryDocDescription",
    )
    count = max(
        [len(recent.get(k, [])) for k in keys if isinstance(recent.get(k), list)]
        or [0]
    )
    rows = []
    for i in range(count):
        row = {}
        for k in keys:
            values = recent.get(k, [])
            row[k] = values[i] if isinstance(values, list) and i < len(values) else None
        rows.append(row)
    return rows


def document_url(cik: str, accession: str, document: str) -> str:
    return (
        f"{SEC_ARCHIVES}/{int(cik)}/"
        f"{accession.replace('-', '')}/{document}"
    )


def temporal_relation(d: date, previous: date, current: date) -> str:
    if d == previous:
        return "ENDPOINT_PRE"
    if d == current:
        return "ENDPOINT_POST"
    if previous < d < current:
        return "IN_WINDOW"
    return "OUTSIDE_WINDOW"


def economic_temporal_relation(
    effective: str | None,
    previous: date,
    current: date,
) -> str:
    if effective is None:
        return "UNRESOLVED"
    try:
        d = date.fromisoformat(effective)
    except ValueError:
        return "UNRESOLVED"
    if d <= previous:
        return "BEFORE_ECONOMIC_WINDOW"
    if d <= current:
        return "IN_ECONOMIC_WINDOW"
    return "AFTER_ECONOMIC_WINDOW"


def snippet(text: str, start: int, end: int) -> str:
    a = max(0, start - 260)
    b = min(len(text), end + 260)
    return re.sub(r"\s+", " ", text[a:b]).strip()[:900]


def effective_date(text: str) -> str | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw = match.group(1)
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                return date.fromisoformat(raw).isoformat()
            return datetime.strptime(raw, "%B %d, %Y").date().isoformat()
        except ValueError:
            pass
    return None


def ratio_candidate(text: str, action_type: str) -> dict[str, int] | None:
    match = RATIO.search(text)
    if match and action_type in {"STOCK_SPLIT", "REVERSE_STOCK_SPLIT"}:
        return {
            "ratio_numerator": int(match.group(1)),
            "ratio_denominator": int(match.group(2)),
        }

    if action_type == "REVERSE_STOCK_SPLIT":
        match = EVERY_INTO.search(text)
        if match:
            # One new share for every N old shares.
            return {
                "ratio_numerator": 1,
                "ratio_denominator": int(match.group(1)),
            }
    return None


def classify(
    text: str,
    previous: date,
    current: date,
) -> dict[str, Any]:
    """
    Preserve raw text matches, then qualify them conservatively.

    A text match is not automatically evidence for the current Short Interest
    comparison. Qualified evidence requires:
      1) a concrete corporate-action category;
      2) an explicit effective-date candidate;
      3) that effective date to fall inside the economic settlement window.

    Missing effective date remains UNRESOLVED. It is never converted to
    NO_ACTION and never authorizes an adjustment.
    """
    text_matches: list[dict[str, Any]] = []
    qualified_evidence: list[dict[str, Any]] = []

    for action_type, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            context = snippet(text, match.start(), match.end())
            eff = effective_date(context)
            relation = economic_temporal_relation(eff, previous, current)
            ratio = ratio_candidate(context, action_type)

            category = (
                "SHARE_ADJUSTING_ACTION"
                if action_type in {"STOCK_SPLIT", "REVERSE_STOCK_SPLIT"}
                else action_type
            )

            if relation == "IN_ECONOMIC_WINDOW":
                qualification = "QUALIFIED_IN_ECONOMIC_WINDOW"
                is_qualified = True
            elif relation in {
                "BEFORE_ECONOMIC_WINDOW",
                "AFTER_ECONOMIC_WINDOW",
            }:
                qualification = "OUTSIDE_ECONOMIC_WINDOW"
                is_qualified = False
            else:
                qualification = "UNRESOLVED_EFFECTIVE_DATE"
                is_qualified = False

            item = {
                "category": category,
                "candidate_action_type": action_type,
                "matched_text": match.group(0),
                "effective_date_candidate": eff,
                "economic_temporal_relation": relation,
                "qualification_status": qualification,
                "qualified_for_current_reconciliation": is_qualified,
                "adjustment_authorized": False,
                "ratio_candidate": ratio,
                "text": context,
            }
            text_matches.append(item)

            if is_qualified:
                qualified_evidence.append(item)

    # Preserve categories found in raw text for audit, but keep them separate
    # from semantically qualified evidence.
    raw_categories = sorted({x["category"] for x in text_matches})
    qualified_categories = sorted({x["category"] for x in qualified_evidence})

    first_qualified = qualified_evidence[0] if qualified_evidence else None

    return {
        "text_matches_count": len(text_matches),
        "qualified_evidence_count": len(qualified_evidence),
        "raw_evidence_categories": raw_categories,
        "qualified_evidence_categories": qualified_categories,
        "candidate_action_type": (
            first_qualified["candidate_action_type"]
            if first_qualified else None
        ),
        "effective_date_candidate": (
            first_qualified["effective_date_candidate"]
            if first_qualified else None
        ),
        "economic_temporal_relation": (
            first_qualified["economic_temporal_relation"]
            if first_qualified else "UNRESOLVED"
        ),
        "ratio_candidate": (
            first_qualified["ratio_candidate"]
            if first_qualified else None
        ),
        "text_matches": text_matches[:40],
        "qualified_evidence": qualified_evidence[:20],
    }


def resolve_one(
    ticker: str,
    master: dict[str, Any],
    collected: dict[str, Any],
    client: SecClient,
    pre_days: int,
    post_days: int,
) -> dict[str, Any]:
    identifiers = master.get("identifiers")
    if not isinstance(identifiers, dict):
        raise ValueError("identifiers ausente no Master Asset Universe")
    cik = canonical_cik(identifiers.get("sec_cik"))
    previous, current = settlement_window(collected)
    start = previous - timedelta(days=pre_days)
    end = current + timedelta(days=post_days)

    submissions_url = SEC_SUBMISSIONS.format(cik=cik)
    submissions = client.get_json(submissions_url)
    filings = []

    for row in recent_rows(submissions):
        if row.get("form") not in FORMS:
            continue
        try:
            filing_date = iso_date(row.get("filingDate"), "filingDate")
        except ValueError:
            continue
        if not start <= filing_date <= end:
            continue

        accession = row.get("accessionNumber")
        primary = row.get("primaryDocument")
        base = {
            "form": row.get("form"),
            "filing_date": filing_date.isoformat(),
            "report_date": row.get("reportDate"),
            "acceptance_datetime": row.get("acceptanceDateTime"),
            "items": row.get("items"),
            "accession_number": accession,
            "primary_document": primary,
            "temporal_relation": temporal_relation(
                filing_date, previous, current
            ),
        }

        if not isinstance(accession, str) or not isinstance(primary, str):
            filings.append({
                **base,
                "fetch_status": "BLOCKED_MISSING_DOCUMENT_IDENTITY",
                "evidence_categories": [],
            })
            continue

        url = document_url(cik, accession, primary)
        try:
            text = client.get_text(url)
            filings.append({
                **base,
                "document_url": url,
                "official_document_url": url,
                "fetch_status": "FETCHED",
                **classify(text, previous, current),
            })
        except RuntimeError as exc:
            filings.append({
                **base,
                "document_url": url,
                "official_document_url": url,
                "fetch_status": "FETCH_FAILED",
                "evidence_categories": [],
                "error": str(exc),
            })

    failed = [x for x in filings if x.get("fetch_status") != "FETCHED"]
    text_match_filings = [
        x for x in filings if (x.get("text_matches_count") or 0) > 0
    ]
    qualified_filings = [
        x for x in filings if (x.get("qualified_evidence_count") or 0) > 0
    ]
    text_matches_count = sum(
        int(x.get("text_matches_count") or 0) for x in filings
    )
    qualified_evidence_count = sum(
        int(x.get("qualified_evidence_count") or 0) for x in filings
    )
    status = "PARTIAL" if failed else "RESOLVED"

    listing = master.get("listing")
    exchange = listing.get("exchange") if isinstance(listing, dict) else None

    return {
        "ticker": ticker,
        "identity": {
            "issuer_name": master.get("issuer_name"),
            "security_name": master.get("security_name"),
            "listing_exchange": exchange,
            "cusip": identifiers.get("cusip"),
            "sec_cik": cik,
            "sec_submission_name": submissions.get("name"),
            "sec_submission_cik": submissions.get("cik"),
        },
        "settlement_window": {
            "previous_settlement_date": previous.isoformat(),
            "current_settlement_date": current.isoformat(),
        },
        "search_window": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "pre_window_days": pre_days,
            "post_window_days": post_days,
        },
        "source": {
            "source": "SEC",
            "source_type": "SEC_FILING",
            "source_tier": "TIER_1",
            "submissions_url": submissions_url,
        },
        "resolver_status": status,
        "analytically_conclusive": False,
        "reconciliation_required": True,
        "reconciliation_status": "NOT_CHECKED",
        "reason": (
            "ONE_OR_MORE_CANDIDATE_FILINGS_NOT_REVIEWED"
            if failed
            else "EVIDENCE_COLLECTION_COMPLETED_RECONCILIATION_STILL_REQUIRED"
        ),
        "candidate_filings_count": len(filings),
        "fetched_filings_count": len(filings) - len(failed),
        "failed_filings_count": len(failed),
        "filings_with_text_matches_count": len(text_match_filings),
        "text_matches_count": text_matches_count,
        # Compatibility field: from R1 onward this means filings containing
        # semantically qualified evidence for the current economic window.
        "filings_with_evidence_count": len(qualified_filings),
        "qualified_evidence_count": qualified_evidence_count,
        "candidate_filings": filings,
        "diagnostics": (
            ["SEC_CANDIDATE_FILING_REVIEW_INCOMPLETE"] if failed else []
        ),
    }


def build(
    universe: dict[str, Any],
    collection: dict[str, Any],
    client: SecClient,
    pre_days: int,
    post_days: int,
) -> tuple[dict[str, Any], int]:
    masters = universe.get("assets")
    if not isinstance(masters, dict):
        raise RuntimeError("Master Asset Universe sem assets")

    collected = collection_map(collection)
    results = []

    for ticker in sorted(collected):
        master = masters.get(ticker)
        if not isinstance(master, dict):
            results.append({
                "ticker": ticker,
                "resolver_status": "BLOCKED",
                "analytically_conclusive": False,
                "reconciliation_required": True,
                "reconciliation_status": "NOT_CHECKED",
                "reason": "ASSET_NOT_FOUND_IN_MASTER_UNIVERSE",
                "diagnostics": ["MASTER_ASSET_UNIVERSE_IDENTITY_MISSING"],
            })
            continue
        try:
            results.append(resolve_one(
                ticker, master, collected[ticker], client, pre_days, post_days
            ))
        except (ValueError, RuntimeError) as exc:
            results.append({
                "ticker": ticker,
                "resolver_status": "BLOCKED",
                "analytically_conclusive": False,
                "reconciliation_required": True,
                "reconciliation_status": "NOT_CHECKED",
                "reason": str(exc),
                "diagnostics": ["SEC_EVIDENCE_RESOLUTION_BLOCKED"],
            })

    resolved = sum(x.get("resolver_status") == "RESOLVED" for x in results)
    partial = sum(x.get("resolver_status") == "PARTIAL" for x in results)
    blocked = sum(x.get("resolver_status") == "BLOCKED" for x in results)
    exit_code = 0 if not partial and not blocked else 1

    return {
        "schema_version": "3.0",
        "resolver_version": VERSION,
        "domain": "SHORT_INTEREST_CORPORATE_ACTION_EVIDENCE",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "methodology": {
            "source": "SEC_EDGAR",
            "source_tier": "TIER_1",
            "identity_source": "MASTER_ASSET_UNIVERSE_SEC_CIK",
            "settlement_window_source": "SHORT_INTEREST_COLLECTION",
            "absence_of_evidence_is_no_action": False,
            "resolver_assigns_no_action": False,
            "resolver_modifies_registry": False,
            "effective_date_has_temporal_precedence": True,
            "filing_date_is_discovery_metadata": True,
            "raw_text_matches_preserved": True,
            "qualified_evidence_requires_effective_date_in_economic_window": True,
            "economic_window_rule": (
                "previous_settlement_date < effective_date <= "
                "current_settlement_date"
            ),
            "reconciliation_required_after_resolution": True,
        },
        "summary": {
            "total_assets": len(results),
            "resolved_assets": resolved,
            "partial_assets": partial,
            "blocked_assets": blocked,
            "overall_status": (
                "EVIDENCE_COLLECTION_RESOLVED"
                if exit_code == 0 else "PARTIAL_OR_BLOCKED"
            ),
        },
        "assets": results,
    }, exit_code


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--universe", default=str(UNIVERSE))
    p.add_argument("--collection", default=str(COLLECTION))
    p.add_argument("--output", default=str(OUTPUT))
    p.add_argument("--pre-window-days", type=int, default=PRE_DAYS)
    p.add_argument("--post-window-days", type=int, default=POST_DAYS)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.pre_window_days < 0 or args.post_window_days < 0:
        print("ERRO OPERACIONAL: margens negativas")
        return 2

    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent:
        print("ERRO OPERACIONAL: SEC_USER_AGENT nao configurado.")
        return 2

    try:
        universe = read_json(Path(args.universe))
        collection = read_json(Path(args.collection))
        payload, exit_code = build(
            universe,
            collection,
            SecClient(user_agent),
            args.pre_window_days,
            args.post_window_days,
        )
        output = Path(args.output)
        write_json(output, payload)

        print("=" * 72)
        print("RADAR INSTITUCIONAL V3")
        print("SEC CORPORATE ACTION EVIDENCE RESOLVER")
        print(f"VERSION {VERSION}")
        print("=" * 72)
        for asset in payload["assets"]:
            print(
                asset.get("ticker"),
                "|", asset.get("resolver_status"),
                "| filings:", asset.get("candidate_filings_count", "N/D"),
                "| text matches:", asset.get("text_matches_count", "N/D"),
                "| qualified evidence:", asset.get("qualified_evidence_count", "N/D"),
                "| reconciliation:", asset.get("reconciliation_status"),
            )
        print("-" * 72)
        print(payload["summary"])
        print("Output:", output)
        print("Ausencia de evidencia SEC NAO autoriza NO_ACTION.")
        print("Corporate Action Registry NAO foi modificado.")
        return exit_code

    except RuntimeError as exc:
        print(f"ERRO OPERACIONAL: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
