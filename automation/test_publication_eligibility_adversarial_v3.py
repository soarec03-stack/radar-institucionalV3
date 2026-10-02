import copy
import json
import math
from pathlib import Path

from publication_eligibility_v3 import (
    evaluate_asset_publication,
    apply_publication_eligibility,
)

BASE_DIR = Path(__file__).resolve().parent.parent
AUTO = BASE_DIR / "automation"

registry = json.loads(
    (AUTO / "source_registry_v3.json").read_text(
        encoding="utf-8-sig"
    )
)

policy = json.loads(
    (AUTO / "publication_eligibility_policy_v3.json").read_text(
        encoding="utf-8-sig"
    )
)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed

    if condition:
        print("PASS -", name)
        passed += 1
    else:
        print("FAIL -", name)
        failed += 1


def provenance(source="SEC", status="VERIFIED"):
    return {
        "primary_source": source,
        "retrieved_at": "2026-09-30T12:00:00Z",
        "market_date": "2026-09-30",
        "status": status,
        "attempts": 1,
        "sources_attempted": [source],
    }


def point(source):
    return {
        "value": {"normalized_score": 60.0},
        "confidence": {
            "score": 0.90,
            "status": "VERIFIED",
        },
        "provenance": provenance(source),
    }


def risk_context(
    source="CME",
    ticker="TEST",
    market_date="2026-09-30",
    retrieved_at="2026-09-30T12:00:00Z",
):
    return {
        "ticker": ticker,
        "market_date": market_date,
        "source": {
            "primary_source": source,
            "retrieved_at": retrieved_at,
        },
    }


def asset():
    return {
        "ticker": "TEST",
        "score": {
            "total": 80.0,
            "fundamental": 16.0,
            "technical": 16.0,
            "momentum": 12.0,
            "institutional_flow": 12.0,
            "catalysts": 12.0,
            "macro": 8.0,
            "risk": 4.0,
            "status": "CALCULATED",
            "raw_score": 80.0,
            "available_score": 100.0,
            "normalized_score": 80.0,
            "coverage": 1.0,
            "analytically_usable": True,
            "publishable": True,
            "label": "BUY",
        },
        "data_points": {
            "fundamentals": point("SEC"),
            "technical": point("TRADINGVIEW"),
            "institutional_flow": point("B3"),
            "catalysts": point("REUTERS"),
            "macro": point("FRED"),
        },
        "risk": {
            "score": 30.0,
            "level": "MODERATE",
            "drivers": [],
        },
    }


def evaluate(a=None, ctx=None, reg=None, pol=None):
    if a is None:
        a = asset()

    if ctx is None:
        ctx = risk_context()

    if reg is None:
        reg = registry

    if pol is None:
        pol = policy

    return evaluate_asset_publication(
        a,
        reg,
        pol,
        risk_source_context=ctx,
    )


print("=" * 72)
print("B.2L.5B — ADVERSARIAL / FAIL-CLOSED")
print("=" * 72)

# ---------------------------------------------------------------
# Provenance failures
# ---------------------------------------------------------------

a = asset()
a["data_points"]["fundamentals"].pop("provenance")

r = evaluate(a)

check(
    "Missing provenance fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


a = asset()
a["data_points"]["fundamentals"]["provenance"] = None

r = evaluate(a)

check(
    "Null provenance fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


a = asset()
a["data_points"]["fundamentals"]["provenance"] = "SEC"

r = evaluate(a)

check(
    "Malformed provenance fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


a = asset()
a["data_points"]["fundamentals"]["provenance"].pop(
    "primary_source"
)

r = evaluate(a)

check(
    "Missing primary source fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


a = asset()
a["data_points"]["fundamentals"]["provenance"][
    "status"
] = "UNAVAILABLE"

r = evaluate(a)

check(
    "UNAVAILABLE provenance fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


# ---------------------------------------------------------------
# Registry failures
# ---------------------------------------------------------------

bad_registry = copy.deepcopy(registry)

for src in bad_registry["sources"]:
    if src.get("id") == "SEC":
        src["tier"] = "TIER_99"

r = evaluate(reg=bad_registry)

check(
    "Unknown tier fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


bad_registry = copy.deepcopy(registry)

for src in bad_registry["sources"]:
    if src.get("id") == "SEC":
        src.pop("tier", None)

r = evaluate(reg=bad_registry)

check(
    "Missing tier fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


bad_registry = copy.deepcopy(registry)

for src in bad_registry["sources"]:
    if src.get("id") == "SEC":
        src["publication_use"] = "RESEARCH_ONLY"

r = evaluate(reg=bad_registry)

check(
    "Registry RESEARCH_ONLY fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


# Unknown publication_use must not silently become authorization.
bad_registry = copy.deepcopy(registry)

for src in bad_registry["sources"]:
    if src.get("id") == "SEC":
        src["publication_use"] = "UNKNOWN_MODE"

r = evaluate(reg=bad_registry)

check(
    "Unknown publication_use fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


# ---------------------------------------------------------------
# Capability failures
# ---------------------------------------------------------------

bad_registry = copy.deepcopy(registry)

for src in bad_registry["sources"]:
    if src.get("id") == "SEC":
        src["supports"] = []

r = evaluate(reg=bad_registry)

check(
    "Empty supports fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


bad_registry = copy.deepcopy(registry)

for src in bad_registry["sources"]:
    if src.get("id") == "SEC":
        src.pop("supports", None)

r = evaluate(reg=bad_registry)

check(
    "Missing supports fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


# ---------------------------------------------------------------
# Risk SIDECAR failures
# ---------------------------------------------------------------

r = evaluate(ctx={})

check(
    "Empty Risk context fails closed",
    r["components"]["risk"]["eligible"] is False,
)


ctx = risk_context()
ctx.pop("ticker")

r = evaluate(ctx=ctx)

check(
    "Risk context missing ticker fails closed",
    r["components"]["risk"]["eligible"] is False,
)


ctx = risk_context()
ctx.pop("market_date")

r = evaluate(ctx=ctx)

check(
    "Risk context missing market_date fails closed",
    r["components"]["risk"]["eligible"] is False,
)


ctx = risk_context()
ctx.pop("source")

r = evaluate(ctx=ctx)

check(
    "Risk context missing source fails closed",
    r["components"]["risk"]["eligible"] is False,
)


r = evaluate(
    ctx=risk_context(ticker="OTHER")
)

check(
    "Risk ticker mismatch fails closed",
    r["components"]["risk"]["eligible"] is False,
)


ctx = risk_context()
ctx["source"].pop("primary_source")

r = evaluate(ctx=ctx)

check(
    "Risk source missing primary_source fails closed",
    r["components"]["risk"]["eligible"] is False,
)


ctx = risk_context()
ctx["source"].pop("retrieved_at")

r = evaluate(ctx=ctx)

check(
    "Risk source missing retrieved_at fails closed",
    r["components"]["risk"]["eligible"] is False,
)


r = evaluate(
    ctx=risk_context(source="UNKNOWN_SOURCE")
)

check(
    "Unknown Risk source fails closed",
    r["components"]["risk"]["eligible"] is False,
)


r = evaluate(
    ctx=risk_context(source="YAHOO_FINANCE")
)

check(
    "Yahoo Risk fails closed from registry restriction",
    r["components"]["risk"]["eligible"] is False,
)


# ---------------------------------------------------------------
# Risk value boundaries
# ---------------------------------------------------------------

a = asset()
a["risk"]["score"] = None

r = evaluate(a)

check(
    "Null Risk score fails closed",
    r["components"]["risk"]["eligible"] is False,
)


a = asset()
a.pop("risk")

r = evaluate(a)

check(
    "Missing Risk object fails closed",
    r["components"]["risk"]["eligible"] is False,
)


# ---------------------------------------------------------------
# Policy tampering / malformed policy
# ---------------------------------------------------------------

bad_policy = copy.deepcopy(policy)
bad_policy["tier_policy"]["TIER_1"] = "UNKNOWN_ACTION"

r = evaluate(pol=bad_policy)

check(
    "Unknown tier action fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


bad_policy = copy.deepcopy(policy)
bad_policy["components"]["fundamental"][
    "allowed_supports"
] = ["IMPOSSIBLE_CAPABILITY"]

r = evaluate(pol=bad_policy)

check(
    "Impossible capability fails closed",
    r["components"]["fundamental"]["eligible"] is False,
)


bad_policy = copy.deepcopy(policy)
bad_policy["components"]["momentum"][
    "inherits_publication_from"
] = "DOES_NOT_EXIST"

r = evaluate(pol=bad_policy)

check(
    "Invalid Momentum inheritance fails closed",
    r["components"]["momentum"]["eligible"] is False,
)


# ---------------------------------------------------------------
# Mutation safety
# ---------------------------------------------------------------

a = asset()
before = copy.deepcopy(a)

evaluate(a)

check(
    "Adversarial evaluator remains pure",
    a == before,
)


# ---------------------------------------------------------------
# Never promote False → True
# ---------------------------------------------------------------

a = asset()
a["score"]["publishable"] = False
a["score"]["status"] = "PARTIAL"
a["score"].pop("label", None)

data = {"assets": [a]}

updated, changes = apply_publication_eligibility(
    copy.deepcopy(data),
    registry,
    policy,
    risk_source_context_by_ticker={
        "TEST": risk_context()
    },
)

check(
    "Eligible sources cannot promote publishable False",
    updated["assets"][0]["score"]["publishable"] is False,
)

check(
    "No promotion produces no change event",
    changes == [],
)

check(
    "Analytical status survives no-promotion gate",
    updated["assets"][0]["score"]["status"] == "PARTIAL",
)


# ---------------------------------------------------------------
# False remains False even under malformed dependency
# ---------------------------------------------------------------

a = asset()
a["score"]["publishable"] = False
a["score"]["status"] = "INSUFFICIENT_DATA"
a["score"].pop("label", None)
a["data_points"]["technical"] = point("YAHOO_FINANCE")

data = {"assets": [a]}

updated, changes = apply_publication_eligibility(
    copy.deepcopy(data),
    registry,
    policy,
    risk_source_context_by_ticker={
        "TEST": risk_context()
    },
)

check(
    "Already-false score remains false under blocked source",
    updated["assets"][0]["score"]["publishable"] is False,
)

check(
    "INSUFFICIENT_DATA status is preserved",
    updated["assets"][0]["score"]["status"]
    == "INSUFFICIENT_DATA",
)


print()
print("=" * 72)
print("PASS:", passed)
print("FAIL:", failed)

if failed:
    print("RESULT: ADVERSARIAL HARDENING NOT APPROVED")
    raise SystemExit(1)

print("RESULT: ADVERSARIAL HARDENING APPROVED")
raise SystemExit(0)
