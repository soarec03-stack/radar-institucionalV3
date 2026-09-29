from __future__ import annotations
import copy, json, sys
from datetime import date
from pathlib import Path

VERSION="3.4I.9A-B.2I.9A"
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))

import catalyst_qualification_v3 as qual
import catalyst_metrics_composer_v3 as composer
import catalyst_event_validator_v3 as validator

def load(name): return json.loads((BASE/name).read_text(encoding="utf-8"))

QP=load("catalyst_qualification_policy_v3.json")
EP=load("catalyst_intelligence_policy_v3.json")
CONTRACT=load("catalyst_event_contract_v3.json")
CP=load("catalyst_metrics_composer_policy_v3.json")
REG=load("source_registry_v3.json")
UNIVERSE=load("asset_universe_v3.json")
SOURCES={x["id"]:x for x in REG["sources"]}
REGISTERED=set(SOURCES)
KNOWN=set(UNIVERSE["assets"].keys())
REF=date(2026,9,28)
passed=failed=diagnostics=0

def check(c,d):
    global passed,failed
    if c: passed+=1; print("[PASS]",d)
    else: failed+=1; print("[FAIL]",d)

def diag(c,d):
    global diagnostics
    diagnostics+=1
    print("[DIAG]",d, "=>", c)

def event(**kw):
    e={
      "event_id":"EVT-VRT-GUIDANCE-001","event_key":"VRT-GUIDANCE-2026Q3",
      "ticker":"VRT","event_type":"GUIDANCE","event_status":"COMPLETED",
      "event_date":"2026-09-20","direction":"POSITIVE",
      "direction_reason":"Observed event evidence supports positive direction.",
      "materiality":"HIGH","materiality_reason":"Material event for the tracked asset.",
      "title":"Canonical catalyst boundary fixture",
      "evidence":{"fact":"Canonical factual evidence for boundary testing."},
      "source":{"primary_source":"COMPANY_IR","retrieved_at":"2026-09-28T12:00:00Z"}
    }
    for k,v in kw.items():
        if k=="primary_source": e["source"]["primary_source"]=v
        elif k=="secondary_source": e["source"]["secondary_source"]=v
        else: e[k]=v
    return e

def qone(e):
    return qual.qualify_event(e,QP,EP,CONTRACT,KNOWN,REGISTERED,SOURCES,REF)

def main():
    print("="*76); print("CATALYST REAL-DATA / BOUNDARY REGRESSION V3"); print("Test version:",VERSION); print("="*76)

    good=event()
    q=qone(good)
    check(q["status"]=="ELIGIBLE","Authorized COMPANY_IR canonical event becomes ELIGIBLE.")
    check(q["usable"] is True,"ELIGIBLE event is marked usable.")

    for src in ("USER_PORTFOLIO","YAHOO_FINANCE","TRADINGVIEW"):
        r=qone(event(primary_source=src))
        check(r["status"]=="BLOCKED",f"{src} cannot qualify Catalyst merely because source is registered.")
        check("PRIMARY_SOURCE_NOT_AUTHORIZED_FOR_EVENT_TYPE" in r["reasons"],f"{src} blocked by event-type source authorization.")

    r=qone(event(materiality="LOW",materiality_reason="Low materiality."))
    check(r["status"]=="SUPPRESSED","LOW materiality event is SUPPRESSED.")

    r=qone(event(direction="UNCERTAIN",direction_reason="Evidence does not establish direction."))
    check(r["status"]=="BLOCKED","UNCERTAIN direction is BLOCKED.")

    r=qone(event(event_status="CANCELLED"))
    check(r["status"]=="SUPPRESSED","CANCELLED event is SUPPRESSED.")

    r=qone(event(event_date="2026-07-01"))
    check(r["status"]=="SUPPRESSED","Stale COMPLETED default-horizon event is SUPPRESSED.")
    check("STALE_COMPLETED_EVENT" in r["reasons"],"Stale event exposes explicit temporal reason.")

    r=qone(event(event_status="CONFIRMED",event_date="2026-10-05"))
    check(r["status"]=="BLOCKED","Future non-SCHEDULED event is BLOCKED.")

    r=qone(event(event_status="SCHEDULED",event_date="2027-01-15"))
    check(r["status"]=="SUPPRESSED","SCHEDULED event beyond 90-day horizon is SUPPRESSED.")

    e1=event()
    e2=copy.deepcopy(e1); e2["event_id"]="EVT-VRT-GUIDANCE-002"; e2["source"]["secondary_source"]="REUTERS"
    batch=qual.qualify_events([e1,e2],QP,EP,CONTRACT,KNOWN,REGISTERED,SOURCES,REF)
    check(batch["eligible_events"]==1,"Duplicate identity permits only first event to remain eligible.")
    check(batch["suppressed_events"]==1,"Duplicate event is counted as SUPPRESSED.")
    check(batch["results"][1]["reasons"]==["DUPLICATE_EVENT"],"Duplicate exposes DUPLICATE_EVENT reason.")

    # T3: Yahoo is intentionally unauthorized for Catalyst, so use any authorized T3 only if registry/policy has one.
    authorized_t3=[]
    auth=QP.get("source_authorization",{})
    for sid,sp in SOURCES.items():
        if sp.get("tier")=="TIER_3" and sid in auth and auth[sid].get("allowed_event_types"):
            authorized_t3.append(sid)
    diag(authorized_t3,"Authorized TIER_3 Catalyst sources discovered")
    if authorized_t3:
        sid=authorized_t3[0]
        ev=event(primary_source=sid)
        rr=qone(ev)
        check(rr["status"]=="BLOCKED","Authorized TIER_3 without secondary confirmation is BLOCKED.")
    else:
        print("[INFO] No authorized TIER_3 Catalyst source exists; confirmation runtime path cannot be exercised with canonical registry.")

    # SCHEDULED probability boundary: qualification may pass, Composer must not invent probability.
    scheduled=event(event_status="SCHEDULED",event_date="2026-10-20")
    qs=qone(scheduled)
    check(qs["status"]=="ELIGIBLE","In-horizon SCHEDULED event can pass qualification.")
    record=dict(qs); record["event"]=scheduled
    composed=composer.compose_metrics([record],REF,CP,EP,REG)
    check(composed["summary"]["ready_items"]==0,"SCHEDULED without observable probability creates no Catalyst item.")
    check(composed["summary"]["suppressed_records"]==1,"SCHEDULED without probability is SUPPRESSED by Composer.")
    check(composed["audit"][0]["reason"]=="PROBABILITY_NOT_DERIVABLE","Composer reports PROBABILITY_NOT_DERIVABLE.")
    check(composed["metrics"]["items"]==[],"Composer does not invent probability or metrics item.")

    # Contract-gap diagnostic: probability is consumed by Composer but absent from formal event fields.
    fields=CONTRACT.get("event",CONTRACT).get("fields",{})
    diag("probability" in fields,"Event Contract formally declares observable probability")
    check("probability" in fields,"Observable probability is now formally declared by Event Contract.")

    # T3 semantic diagnostic: qualification code/policy model secondary_source, not a second evidence object.
    source_fields=fields.get("source",{}).get("fields",{})
    check("secondary_source" in source_fields,"Event Contract declares secondary_source.")
    check("secondary_evidence" not in fields and "confirmations" not in fields,
          "Current contract has no independent second-evidence object (gap explicitly detected).")

    # Blocked/suppressed qualification must not become Composer metrics.
    blocked=qone(event(primary_source="USER_PORTFOLIO"))
    br=dict(blocked); br["event"]=event(primary_source="USER_PORTFOLIO")
    bc=composer.compose_metrics([br],REF,CP,EP,REG)
    check(bc["summary"]["ready_items"]==0,"BLOCKED qualification cannot produce Catalyst metrics.")
    check(bc["metrics"]["items"]==[],"BLOCKED qualification produces zero metric items.")

    suppressed=qone(event(materiality="LOW",materiality_reason="Low materiality."))
    sr=dict(suppressed); sr["event"]=event(materiality="LOW",materiality_reason="Low materiality.")
    sc=composer.compose_metrics([sr],REF,CP,EP,REG)
    check(sc["summary"]["ready_items"]==0,"SUPPRESSED qualification cannot produce Catalyst metrics.")
    check(sc["metrics"]["items"]==[],"SUPPRESSED qualification produces zero metric items.")

    # Raw narrative cannot satisfy canonical contract.
    narrative={"ticker":"VRT","title":"Portfolio narrative","source":{"primary_source":"USER_PORTFOLIO","retrieved_at":"2026-09-28T12:00:00Z"}}
    vr=validator.validate_event(narrative,CONTRACT,EP,KNOWN,REGISTERED)
    check(vr["valid"] is False,"Narrative-only object fails Catalyst Event Contract validation.")
    qr=qone(narrative)
    check(qr["status"]=="BLOCKED","Narrative-only object is BLOCKED upstream.")

    total=passed+failed
    print(); print("="*76); print("B.2I.9A RESULT"); print("="*76)
    print("Checks      :",total); print("Passed      :",passed); print("Failed      :",failed); print("Diagnostics :",diagnostics)
    print("RESULT      :","PASS" if failed==0 else "FAIL")
    print("="*76)
    return 0 if failed==0 else 1

if __name__=="__main__": sys.exit(main())


