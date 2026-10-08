import copy
import importlib.util
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
AUTO = BASE / "automation"

MODULE_PATH = AUTO / "publication_eligibility_v3.py"
REGISTRY_PATH = AUTO / "source_registry_v3.json"
POLICY_PATH = AUTO / "publication_eligibility_policy_v3.json"

checks = 0
failures = 0


def check(condition, message):
    global checks, failures
    checks += 1
    if condition:
        print(f"[PASS] {message}")
    else:
        failures += 1
        print(f"[FAIL] {message}")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "publication_context_runtime_adversarial",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = load_module()

evaluate = module.evaluate_asset_publication
build = module.build_publication_context_by_ticker

registry = load_json(REGISTRY_PATH)
policy = load_json(POLICY_PATH)


def verified_provenance(source):
    return {
        "status": "VERIFIED",
        "primary_source": source,
        "retrieved_at": "2026-09-13T12:00:00Z",
    }


def make_asset(ticker="TEST"):
    return {
        "ticker": ticker,
        "score": {
            "status": "CALCULATED",
            "publishable": True,
        },
        "risk": {
            "status": "CALCULATED",
            "score": 25.0,
            "level": "MODERATE",
        },
        "provenance": {
            "price": verified_provenance("TRADINGVIEW"),
            "fundamentals": verified_provenance("SEC"),
            "technical": verified_provenance("TRADINGVIEW"),
            "institutional_flow": verified_provenance("SEC"),
            "catalysts": verified_provenance("COMPANY_IR"),
            "macro": verified_provenance("FRED"),
        },
    }


def make_risk_context(ticker):
    return {
        "ticker": ticker,
        "market_date": "2026-09-12",
        "source": {
            "primary_source": "TRADINGVIEW",
            "retrieved_at": "2026-09-13T12:00:00Z",
        },
    }


def canonical_context(asset, risk_context=None):
    evaluation = evaluate(
        asset,
        registry,
        policy,
        risk_context,
    )

    return {
        "ticker": asset["ticker"].strip(),
        "eligible": evaluation["eligible"],
        "components": evaluation["components"],
    }


print("=" * 78)
print(" D.3D.4I.3 - PUBLICATION CONTEXT INTERFACE RUNTIME ADVERSARIAL")
print("=" * 78)

# ------------------------------------------------------------------
# 1. API / basic behavior
# ------------------------------------------------------------------

check(callable(build), "dedicated interface callable")

check(build(None, registry, policy) == {},
      "non-dict radar fails closed to empty context")

check(build([], registry, policy) == {},
      "list radar fails closed to empty context")

check(build({}, registry, policy) == {},
      "missing assets fails closed to empty context")

check(build({"assets": None}, registry, policy) == {},
      "null assets fails closed to empty context")

check(build({"assets": {}}, registry, policy) == {},
      "non-list assets fails closed to empty context")

# ------------------------------------------------------------------
# 2. Invalid asset / ticker handling
# ------------------------------------------------------------------

invalid_assets = [
    None,
    123,
    "asset",
    {},
    {"ticker": None},
    {"ticker": ""},
    {"ticker": "   "},
]

for index, asset in enumerate(invalid_assets, start=1):
    radar = {"assets": [asset]}
    result = build(radar, registry, policy)

    check(
        result == {},
        f"invalid asset/ticker case {index} does not invent identity",
    )

# ------------------------------------------------------------------
# 3. Exact equivalence with canonical evaluator
# ------------------------------------------------------------------

asset = make_asset("VRT")
risk = make_risk_context("VRT")

radar = {"assets": [asset]}
risk_map = {"VRT": risk}

expected = canonical_context(asset, risk)

result = build(
    radar,
    registry,
    policy,
    risk_map,
)

check("VRT" in result,
      "valid ticker included in context")

check(result.get("VRT") == expected,
      "context exactly matches canonical evaluator projection")

check(
    result["VRT"]["eligible"] == evaluate(
        asset,
        registry,
        policy,
        risk,
    )["eligible"],
    "eligible copied from canonical evaluator",
)

check(
    result["VRT"]["components"] == evaluate(
        asset,
        registry,
        policy,
        risk,
    )["components"],
    "components copied without rewriting",
)

# ------------------------------------------------------------------
# 4. Non-mutation
# ------------------------------------------------------------------

asset = make_asset("CRSP")
radar = {"assets": [asset]}
risk_map = {"CRSP": make_risk_context("CRSP")}

radar_before = copy.deepcopy(radar)
registry_before = copy.deepcopy(registry)
policy_before = copy.deepcopy(policy)
risk_before = copy.deepcopy(risk_map)

build(radar, registry, policy, risk_map)

check(radar == radar_before,
      "builder does not mutate radar")

check(registry == registry_before,
      "builder does not mutate registry")

check(policy == policy_before,
      "builder does not mutate publication policy")

check(risk_map == risk_before,
      "builder does not mutate risk context map")

check(
    "publication_context_by_ticker" not in radar,
    "builder does not persist sidecar into radar",
)

check(
    "publication_context" not in asset,
    "builder does not write publication context into asset",
)

check(
    "decision_center" not in asset,
    "builder does not write Decision Center",
)

# ------------------------------------------------------------------
# 5. Multiple assets preserve per-ticker evaluator semantics
# ------------------------------------------------------------------

vrt = make_asset("VRT")
crsp = make_asset("CRSP")
eton = make_asset("ETON")

multi_radar = {
    "assets": [vrt, crsp, eton]
}

multi_risk = {
    "VRT": make_risk_context("VRT"),
    "CRSP": make_risk_context("CRSP"),
    "ETON": make_risk_context("ETON"),
}

multi_result = build(
    multi_radar,
    registry,
    policy,
    multi_risk,
)

check(
    set(multi_result.keys()) == {"VRT", "CRSP", "ETON"},
    "multiple assets produce independent ticker contexts",
)

for asset in (vrt, crsp, eton):
    ticker = asset["ticker"]

    expected = canonical_context(
        asset,
        multi_risk[ticker],
    )

    check(
        multi_result[ticker] == expected,
        f"{ticker} context equals canonical evaluator",
    )

# ------------------------------------------------------------------
# 6. Missing risk context must preserve evaluator fail-closed behavior
# ------------------------------------------------------------------

asset = make_asset("RISKLESS")

expected_eval = evaluate(
    asset,
    registry,
    policy,
    None,
)

result = build(
    {"assets": [asset]},
    registry,
    policy,
    None,
)

check(
    "RISKLESS" in result,
    "missing risk context does not silently delete valid ticker",
)

check(
    result["RISKLESS"]["eligible"]
    == expected_eval["eligible"],
    "missing risk context preserves evaluator eligibility",
)

check(
    result["RISKLESS"]["components"]
    == expected_eval["components"],
    "missing risk context preserves evaluator components",
)

check(
    result["RISKLESS"]["eligible"] is False,
    "missing required risk context does not promote eligibility",
)

# ------------------------------------------------------------------
# 7. Malformed risk map must not create eligibility
# ------------------------------------------------------------------

for malformed in (
    None,
    [],
    "risk",
    123,
):
    asset = make_asset("MALFORMED")

    expected_eval = evaluate(
        asset,
        registry,
        policy,
        None,
    )

    result = build(
        {"assets": [asset]},
        registry,
        policy,
        malformed,
    )

    check(
        result["MALFORMED"]["eligible"]
        == expected_eval["eligible"],
        f"malformed risk map {type(malformed).__name__} preserves evaluator semantics",
    )

# ------------------------------------------------------------------
# 8. Research-only / blocked evidence must remain blocked
# ------------------------------------------------------------------

blocked = make_asset("BLOCKED")
blocked["provenance"]["technical"] = verified_provenance(
    "YAHOO_FINANCE"
)

blocked_risk = make_risk_context("BLOCKED")

expected_eval = evaluate(
    blocked,
    registry,
    policy,
    blocked_risk,
)

result = build(
    {"assets": [blocked]},
    registry,
    policy,
    {"BLOCKED": blocked_risk},
)

check(
    result["BLOCKED"]["eligible"]
    == expected_eval["eligible"],
    "blocked evidence eligibility exactly preserved",
)

check(
    result["BLOCKED"]["components"]
    == expected_eval["components"],
    "blocked component detail exactly preserved",
)

check(
    result["BLOCKED"]["eligible"] is False,
    "blocked evidence cannot be promoted",
)

# ------------------------------------------------------------------
# 9. Existing publishable False must never be promoted/mutated
# ------------------------------------------------------------------

asset = make_asset("NOPROMOTE")
asset["score"]["publishable"] = False

before = copy.deepcopy(asset)

result = build(
    {"assets": [asset]},
    registry,
    policy,
    {"NOPROMOTE": make_risk_context("NOPROMOTE")},
)

check(
    asset == before,
    "builder does not mutate existing publishable False",
)

check(
    asset["score"]["publishable"] is False,
    "builder never promotes score.publishable",
)

check(
    "NOPROMOTE" in result,
    "context may be exposed without modifying publishable state",
)

# ------------------------------------------------------------------
# 10. Ticker whitespace normalization must not mutate source asset
# ------------------------------------------------------------------

asset = make_asset("  VRT  ")
before = copy.deepcopy(asset)

result = build(
    {"assets": [asset]},
    registry,
    policy,
    {"VRT": make_risk_context("VRT")},
)

check(
    asset == before,
    "ticker normalization does not mutate asset",
)

check(
    "VRT" in result,
    "trimmed ticker used as transient context key",
)

# ------------------------------------------------------------------
# 11. No fabricated public/schema fields
# ------------------------------------------------------------------

asset = make_asset("BOUNDARY")
radar = {"assets": [asset]}
before = copy.deepcopy(radar)

build(
    radar,
    registry,
    policy,
    {"BOUNDARY": make_risk_context("BOUNDARY")},
)

check(
    radar == before,
    "runtime interface leaves complete radar unchanged",
)

check(
    set(radar.keys()) == {"assets"},
    "runtime interface creates no new radar root fields",
)

# ------------------------------------------------------------------
# Result
# ------------------------------------------------------------------

print()
print("=" * 78)
print(" D.3D.4I.3 - RUNTIME ADVERSARIAL RESULT")
print("=" * 78)
print(f"Checks executed: {checks}")
print(f"Failures: {failures}")
print("RESULT:", "APPROVED" if failures == 0 else "FAILED")

raise SystemExit(0 if failures == 0 else 1)