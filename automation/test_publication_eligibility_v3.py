import copy
import json
from pathlib import Path

from publication_eligibility_v3 import (
    evaluate_asset_publication,
    apply_publication_eligibility,
)


BASE_DIR = Path(__file__).resolve().parent.parent
AUTOMATION_DIR = BASE_DIR / "automation"

REGISTRY_PATH = AUTOMATION_DIR / "source_registry_v3.json"
POLICY_PATH = AUTOMATION_DIR / "publication_eligibility_policy_v3.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def provenance(source, status="VERIFIED"):
    return {
        "primary_source": source,
        "secondary_source": None,
        "retrieved_at": "2026-09-30T12:00:00Z",
        "market_date": "2026-09-30",
        "source_url": None,
        "status": status,
        "attempts": 1,
        "sources_attempted": [source],
    }


def point(source, status="VERIFIED"):
    return {
        "value": {"normalized_score": 60.0},
        "confidence": {
            "score": 0.90,
            "status": "VERIFIED",
        },
        "provenance": provenance(source, status),
    }


def risk_context(source="CME", publication_use=None):
    context = {
        "ticker": "TEST",
        "market_date": "2026-09-30",
        "source": {
            "primary_source": source,
            "retrieved_at": "2026-09-30T12:00:00Z",
        },
    }

    if publication_use is not None:
        context["source"]["publication_use"] = publication_use

    return context


def build_asset():
    return {
        "ticker": "TEST",
        "score": {
            "total": 50.0,
            "fundamental": 10.0,
            "technical": 10.0,
            "momentum": 7.5,
            "institutional_flow": 7.5,
            "catalysts": 7.5,
            "macro": 5.0,
            "risk": 2.5,
            "status": "CALCULATED",
            "raw_score": 50.0,
            "available_score": 100.0,
            "normalized_score": 50.0,
            "coverage": 1.0,
            "analytically_usable": True,
            "publishable": True,
            "label": "HOLD",
        },
        "data_points": {
            "fundamentals": point("SEC"),
            "technical": point("TRADINGVIEW"),
            "institutional_flow": point("B3"),
            "catalysts": point("REUTERS"),
            "macro": point("FRED"),
        },
        "risk": {
            "score": 40.0,
            "level": "HIGH",
            "drivers": [],
        },
    }


registry = load_json(REGISTRY_PATH)
policy = load_json(POLICY_PATH)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed

    if condition:
        print(f"PASS - {name}")
        passed += 1
    else:
        print(f"FAIL - {name}")
        failed += 1


print("=" * 72)
print("B.2L.5A — PUBLICATION ELIGIBILITY ENGINE")
print("=" * 72)


# ------------------------------------------------------------------
# 1. Fully eligible institutional/publication-grade example
# ------------------------------------------------------------------

asset = build_asset()

result = evaluate_asset_publication(
    asset,
    registry,
    policy,
    risk_source_context=risk_context(),
)

check(
    "Fully eligible asset is publication eligible",
    result.get("eligible") is True,
)

for component in (
    "fundamental",
    "technical",
    "momentum",
    "institutional_flow",
    "catalysts",
    "macro",
    "risk",
):
    check(
        f"{component} is eligible",
        result.get("components", {})
              .get(component, {})
              .get("eligible") is True,
    )


# ------------------------------------------------------------------
# 2. Yahoo Technical blocks Technical and Momentum
# ------------------------------------------------------------------

asset = build_asset()
asset["data_points"]["technical"] = point("YAHOO_FINANCE")

result = evaluate_asset_publication(
    asset,
    registry,
    policy,
    risk_source_context=risk_context(),
)

check(
    "Yahoo technical is blocked",
    result["components"]["technical"]["eligible"] is False,
)

check(
    "Momentum inherits Technical block",
    result["components"]["momentum"]["eligible"] is False,
)

check(
    "Yahoo dependency blocks overall publication",
    result["eligible"] is False,
)


# ------------------------------------------------------------------
# 3. Unknown source fails closed
# ------------------------------------------------------------------

asset = build_asset()
asset["data_points"]["fundamentals"] = point("UNKNOWN_SOURCE")

result = evaluate_asset_publication(
    asset,
    registry,
    policy,
    risk_source_context=risk_context(),
)

check(
    "Unknown source fails closed",
    result["components"]["fundamental"]["eligible"] is False,
)


# ------------------------------------------------------------------
# 4. Tier 4 source blocked
# ------------------------------------------------------------------

asset = build_asset()
asset["data_points"]["catalysts"] = point("RADAR_UNIVERSE")

result = evaluate_asset_publication(
    asset,
    registry,
    policy,
    risk_source_context=risk_context(),
)

check(
    "Tier 4 catalyst source blocked",
    result["components"]["catalysts"]["eligible"] is False,
)


# ------------------------------------------------------------------
# 5. Tier 1 alone is insufficient: supports must match
# ------------------------------------------------------------------

asset = build_asset()
asset["data_points"]["catalysts"] = point("USER_PORTFOLIO")

result = evaluate_asset_publication(
    asset,
    registry,
    policy,
    risk_source_context=risk_context(),
)

check(
    "USER_PORTFOLIO cannot authorize Catalyst",
    result["components"]["catalysts"]["eligible"] is False,
)


# ------------------------------------------------------------------
# 6. Missing component fails closed
# ------------------------------------------------------------------

asset = build_asset()
asset["data_points"].pop("institutional_flow")

result = evaluate_asset_publication(
    asset,
    registry,
    policy,
    risk_source_context=risk_context(),
)

check(
    "Missing Institutional Flow is blocked",
    result["components"]["institutional_flow"]["eligible"] is False,
)


# ------------------------------------------------------------------
# 7. Missing Risk SIDECAR fails closed
# ------------------------------------------------------------------

asset = build_asset()

result = evaluate_asset_publication(
    asset,
    registry,
    policy,
)

check(
    "Missing Risk source context blocks Risk",
    result["components"]["risk"]["eligible"] is False,
)

check(
    "Missing Risk source context blocks overall publication",
    result["eligible"] is False,
)


# ------------------------------------------------------------------
# 8. Research-only Risk source blocked
# ------------------------------------------------------------------

asset = build_asset()

result = evaluate_asset_publication(
    asset,
    registry,
    policy,
    risk_source_context=risk_context(
        "YAHOO_FINANCE",
        "RESEARCH_ONLY",
    ),
)

check(
    "Research-only Risk source is blocked",
    result["components"]["risk"]["eligible"] is False,
)


# ------------------------------------------------------------------
# 9. Evaluator is pure
# ------------------------------------------------------------------

asset = build_asset()
before = copy.deepcopy(asset)

evaluate_asset_publication(
    asset,
    registry,
    policy,
    risk_source_context=risk_context(),
)

check(
    "Evaluator does not mutate asset",
    asset == before,
)


# ------------------------------------------------------------------
# 10. Apply may tighten True → False
# ------------------------------------------------------------------

data = {"assets": [build_asset()]}

data["assets"][0]["data_points"]["technical"] = point(
    "YAHOO_FINANCE"
)

updated, changes = apply_publication_eligibility(
    copy.deepcopy(data),
    registry,
    policy,
    risk_source_context_by_ticker={
        "TEST": risk_context()
    },
)

score = updated["assets"][0]["score"]

check(
    "Apply tightens publishable True to False",
    score.get("publishable") is False,
)

check(
    "Blocked publication removes label",
    "label" not in score,
)

check(
    "Apply reports one changed asset",
    isinstance(changes, list) and len(changes) == 1,
)


# ------------------------------------------------------------------
# 11. Gate never promotes False → True
# ------------------------------------------------------------------

asset = build_asset()
asset["score"]["publishable"] = False
asset["score"]["status"] = "PARTIAL"
asset["score"].pop("label", None)

data = {"assets": [asset]}

updated, changes = apply_publication_eligibility(
    copy.deepcopy(data),
    registry,
    policy,
    risk_source_context_by_ticker={
        "TEST": risk_context()
    },
)

score = updated["assets"][0]["score"]

check(
    "Gate never promotes False to True",
    score.get("publishable") is False,
)

check(
    "Gate preserves analytical PARTIAL status",
    score.get("status") == "PARTIAL",
)


print()
print("=" * 72)
print(f"PASS: {passed}")
print(f"FAIL: {failed}")

if failed:
    print("RESULT: PUBLICATION ELIGIBILITY ENGINE NOT APPROVED")
    raise SystemExit(1)

print("RESULT: PUBLICATION ELIGIBILITY ENGINE APPROVED")
raise SystemExit(0)
