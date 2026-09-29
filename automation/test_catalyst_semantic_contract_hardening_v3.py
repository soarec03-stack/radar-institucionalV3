from __future__ import annotations
import copy, json, sys
from datetime import date
from pathlib import Path

VERSION = "3.4I.9B-TEST"
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import catalyst_event_validator_v3 as validator
import catalyst_qualification_v3 as qual
import catalyst_metrics_composer_v3 as composer

def load(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))

CONTRACT = load("catalyst_event_contract_v3.json")
OLD = load("catalyst_event_contract_v3.pre_B2I9B.json")
EP = load("catalyst_intelligence_policy_v3.json")
QP = load("catalyst_qualification_policy_v3.json")
CP = load("catalyst_metrics_composer_policy_v3.json")
REG = load("source_registry_v3.json")
UNIVERSE = load("asset_universe_v3.json")
SOURCES = {x["id"]: x for x in REG["sources"]}
REGISTERED = set(SOURCES)
KNOWN = set(UNIVERSE["assets"].keys())
REF = date(2026, 9, 28)
passed = failed = 0

def check(c, d):
    global passed, failed
    if c:
        passed += 1
        print("[PASS]", d)
    else:
        failed += 1
        print("[FAIL]", d)

def event(**kw):
    e = {
        "event_id": "EVT-VRT-GUIDANCE-001",
        "event_key": "VRT-GUIDANCE-2026Q3",
        "ticker": "VRT",
        "event_type": "GUIDANCE",
        "event_status": "COMPLETED",
        "event_date": "2026-09-20",
        "direction": "POSITIVE",
        "direction_reason": "Observed evidence supports direction.",
        "materiality": "HIGH",
        "materiality_reason": "Material event for tracked asset.",
        "title": "Canonical semantic contract fixture",
        "evidence": {"fact": "Canonical factual evidence."},
        "source": {
            "primary_source": "COMPANY_IR",
            "retrieved_at": "2026-09-28T12:00:00Z",
        },
    }
    for k, v in kw.items():
        if k == "primary_source":
            e["source"]["primary_source"] = v
        else:
            e[k] = v
    return e

def validate(e):
    return validator.validate_event(e, CONTRACT, EP, KNOWN, REGISTERED)

def qone(e):
    return qual.qualify_event(e, QP, EP, CONTRACT, KNOWN, REGISTERED, SOURCES, REF)

def main():
    print("=" * 76)
    print("CATALYST SEMANTIC CONTRACT HARDENING V3")
    print("Test version:", VERSION)
    print("=" * 76)

    fields = CONTRACT["event"]["fields"]
    required = CONTRACT["event"]["required"]

    check(CONTRACT["contract_version"] == "3.4I.9B-B.2I.9B",
          "Contract version is B.2I.9B.")
    check("probability" in fields, "Contract formally declares probability.")
    check(fields["probability"].get("type") == "number",
          "probability type is number.")
    check(fields["probability"].get("minimum") == 0,
          "probability minimum is 0.")
    check(fields["probability"].get("maximum") == 1,
          "probability maximum is 1.")
    check("probability" not in required, "probability remains optional.")
    check("market_scope" in fields, "Contract formally declares market_scope.")
    check(fields["market_scope"].get("type") == "string",
          "market_scope type is string.")
    check("market_scope" not in required, "market_scope remains optional.")

    old_fields = OLD["event"]["fields"]
    check(set(old_fields).issubset(set(fields)),
          "No pre-B.2I.9B event field was removed.")
    check(all(fields[k] == old_fields[k] for k in old_fields),
          "No pre-B.2I.9B event field definition was changed.")
    check(set(fields) - set(old_fields) == {"probability", "market_scope"},
          "Only probability and market_scope were added to event fields.")

    old_without_version = copy.deepcopy(OLD)
    new_without_version = copy.deepcopy(CONTRACT)
    old_without_version["contract_version"] = "<VERSION>"
    new_without_version["contract_version"] = "<VERSION>"
    new_without_version["event"]["fields"].pop("probability", None)
    new_without_version["event"]["fields"].pop("market_scope", None)
    check(old_without_version == new_without_version,
          "Outside version + two new fields, contract is byte-semantically unchanged.")

    base = event()
    check(validate(base)["valid"] is True,
          "Existing COMPLETED event remains valid without probability.")
    check(qone(base)["status"] == "ELIGIBLE",
          "Existing COMPLETED event remains qualification-eligible.")

    scheduled = event(
        event_status="SCHEDULED",
        event_date="2026-10-20",
        probability=0.80,
    )
    check(validate(scheduled)["valid"] is True,
          "SCHEDULED event with observable probability is contract-valid.")
    qs = qone(scheduled)
    check(qs["status"] == "ELIGIBLE",
          "SCHEDULED event with observable probability passes qualification.")
    rec = dict(qs)
    rec["event"] = scheduled
    cm = composer.compose_metrics([rec], REF, CP, EP, REG)
    check(cm["summary"]["ready_items"] == 1,
          "SCHEDULED event with probability reaches Composer READY.")
    check(cm["metrics"]["items"][0]["probability"] == 0.80,
          "Composer preserves observable probability 0.80.")

    scheduled_missing = event(
        event_status="SCHEDULED",
        event_date="2026-10-20",
    )
    check(validate(scheduled_missing)["valid"] is True,
          "SCHEDULED probability remains optional at raw contract layer.")
    qm = qone(scheduled_missing)
    rm = dict(qm)
    rm["event"] = scheduled_missing
    cm2 = composer.compose_metrics([rm], REF, CP, EP, REG)
    check(cm2["summary"]["ready_items"] == 0,
          "Missing SCHEDULED probability still creates no metrics item.")
    check(cm2["audit"][0]["reason"] == "PROBABILITY_NOT_DERIVABLE",
          "Missing SCHEDULED probability remains fail-closed in Composer.")

    b3_missing = event(
        event_id="EVT-VRT-CA-001",
        event_key="VRT-CA-2026-09",
        event_type="CORPORATE_ACTION",
        primary_source="B3",
    )
    check(validate(b3_missing)["valid"] is True,
          "market_scope remains optional at raw contract layer.")
    check(qone(b3_missing)["status"] == "BLOCKED",
          "B3 event without market_scope is blocked contextually.")

    b3_ok = copy.deepcopy(b3_missing)
    b3_ok["market_scope"] = "B3"
    check(validate(b3_ok)["valid"] is True,
          "B3 event can formally carry market_scope.")
    check(qone(b3_ok)["status"] == "ELIGIBLE",
          "B3 CORPORATE_ACTION with market_scope=B3 passes qualification.")

    total = passed + failed
    print()
    print("=" * 76)
    print("B.2I.9B RESULT")
    print("=" * 76)
    print("Checks :", total)
    print("Passed :", passed)
    print("Failed :", failed)
    print("RESULT :", "PASS" if failed == 0 else "FAIL")
    print("=" * 76)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
