from __future__ import annotations
import copy, sys
from pathlib import Path
from typing import Any

VERSION="3.4I.8A-B.2I.8A"
BASE_DIR=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE_DIR))
import score_engine_v3 as score
POLICY=score.load_json(BASE_DIR/"score_policy_v3.json")
passed=failed=0

def check(c,d):
    global passed,failed
    if c: passed+=1; print(f"[PASS] {d}")
    else: failed+=1; print(f"[FAIL] {d}")

def approx(a,b,t=1e-9):
    try:return abs(float(a)-float(b))<=t
    except:return False

def asset(sig=87.5,conf=1.0,status="VERIFIED",point=True,signal=True):
    a={"ticker":"VRT","data_points":{}}
    if not point:return a
    v={}
    if signal:v["normalized_score"]=sig
    a["data_points"]["catalysts"]={"value":v,"confidence":{"score":conf,"status":status},
      "provenance":{"status":"PARTIAL","primary_source":"COMPANY_IR"}}
    return a

def main():
    print("="*72); print("CATALYST -> RADAR SCORE INTEGRATION V3"); print("Test version:",VERSION); print("="*72)
    cp=score.get_component_policy(POLICY,"catalysts"); rp=POLICY["components"]["catalysts"]
    check(cp["source_path"]=="data_points.catalysts","Catalyst resolves data_points.catalysts.")
    check(approx(cp["max_points"],15),"Catalyst maximum is exactly 15 points.")
    check("normalized_score" in cp["signal_keys"],"Catalyst accepts normalized_score.")
    check(rp.get("source")=="data_points.catalysts","Policy explicitly binds Catalyst source.")
    check(rp.get("max_points")==15,"Policy explicitly defines Catalyst max_points=15.")
    check(approx(score.get_minimum_usable_confidence(POLICY),.60),"Minimum usable confidence resolves to 0.60.")

    full=score.calculate_component(asset(100,1,"VERIFIED"),"catalysts",POLICY)
    check(full["available"],"100/100 verified Catalyst is available.")
    check(approx(full["signal"],100),"Catalyst reads normalized_score=100.")
    check(approx(full["confidence_multiplier"],1),"Numeric confidence 1.00 is multiplier 1.00.")
    check(approx(full["points"],15),"100 x 15 x 1.00 = 15.00 points.")
    check(full["points"]<=full["max_points"],"Catalyst contribution does not exceed 15 points.")

    high=score.calculate_component(asset(87.5,1,"VERIFIED"),"catalysts",POLICY)
    check(approx(high["points"],13.125),"87.5 x 15 = 13.125 points at confidence 1.00.")

    part=score.calculate_component(asset(87.5,.80,"PARTIAL"),"catalysts",POLICY)
    check(approx(part["confidence_multiplier"],.80),"Numeric confidence 0.80 takes precedence over PARTIAL status.")
    check(approx(part["points"],10.50),"87.5 x 15 x 0.80 = 10.50 points.")

    dp={"value":{"normalized_score":87.5},"confidence":{"score":"INVALID","status":"PARTIAL"}}
    fallback=score.resolve_confidence_multiplier(dp,POLICY)
    fc=score.calculate_component({"ticker":"VRT","data_points":{"catalysts":copy.deepcopy(dp)}},"catalysts",POLICY)
    check(approx(fc["confidence_multiplier"],fallback),"Invalid numeric confidence uses engine status fallback.")
    check(approx(fc["points"],round(.875*15*fallback,4)),"Fallback points use engine-resolved multiplier.")

    contra=score.calculate_component(asset(87.5,.80,"VERIFIED"),"catalysts",POLICY)
    check(approx(contra["confidence_multiplier"],.80),"Numeric confidence precedes VERIFIED status.")

    zero=score.calculate_component(asset(0,1,"VERIFIED"),"catalysts",POLICY)
    check(zero["available"],"Zero Catalyst signal remains observed/available.")
    check(approx(zero["points"],0),"Zero Catalyst contributes exactly zero points.")

    low=score.calculate_component(asset(87.5,.59,"LOW"),"catalysts",POLICY)
    check(not low["available"],"Confidence 0.59 is below usability threshold.")
    check(approx(low["points"],0),"Below-threshold Catalyst contributes zero points.")

    un=score.calculate_component(asset(87.5,0,"UNAVAILABLE"),"catalysts",POLICY)
    check(not un["available"],"UNAVAILABLE Catalyst is excluded.")
    check(approx(un["points"],0),"UNAVAILABLE Catalyst receives zero points.")

    missing=score.calculate_component(asset(conf=1,status="VERIFIED",signal=False),"catalysts",POLICY)
    check(not missing["available"],"Catalyst without normalized signal is unavailable.")
    check(missing["signal"] is None,"Missing signal is not converted to neutral 50.")
    check(approx(missing["points"],0),"Missing signal receives zero points.")

    absent=score.calculate_component(asset(point=False),"catalysts",POLICY)
    check(not absent["available"],"Missing data_points.catalysts is unavailable.")
    check(absent["signal"] is None,"Missing Catalyst has no synthetic signal.")

    result=score.calculate_asset_score(asset(87.5,1,"VERIFIED"),POLICY); c=result["components"]["catalysts"]
    check(approx(c["points"],13.125),"Asset score preserves Catalyst contribution 13.125.")
    check(approx(result["raw_score"],13.12),"Asset raw_score rounds contribution to 13.12.")
    check(approx(result["available_score"],15),"Available Catalyst adds full 15 to denominator.")
    check(approx(result["coverage"],.15),"Catalyst-only coverage is exactly 15%.")
    check(result["status"]=="INSUFFICIENT_DATA","Catalyst-only remains INSUFFICIENT_DATA.")
    check(result["normalized_score"] is None,"Insufficient coverage does not invent normalized Radar Score.")
    check(result["label"] is None,"Insufficient coverage does not create label.")

    lr=score.calculate_asset_score(asset(87.5,.59,"LOW"),POLICY)
    check(approx(lr["available_score"],0),"Below-threshold Catalyst does not enter available_score.")
    check(approx(lr["coverage"],0),"Below-threshold Catalyst creates no coverage.")

    zr=score.calculate_asset_score(asset(0,1,"VERIFIED"),POLICY)
    check(approx(zr["available_score"],15),"Observed zero Catalyst adds 15 available points.")
    check(approx(zr["coverage"],.15),"Observed zero Catalyst still adds 15% coverage.")

    wa=asset(87.5,1,"VERIFIED"); wa["radar_score"]={"legacy":True}; score.write_score_to_asset(wa,result)
    check("radar_score" not in wa,"Writer removes transient radar_score.")
    check(isinstance(wa.get("score"),dict),"Writer creates official asset.score.")
    check(approx(wa["score"]["catalysts"],13.12),"asset.score.catalysts stores rounded points.")
    check(approx(wa["score"]["available_score"],15),"asset.score preserves available_score.")
    check(approx(wa["score"]["coverage"],.15),"asset.score preserves coverage.")
    check("label" not in wa["score"],"Non-publishable score writes no label.")

    ia=asset(87.5,.80,"PARTIAL"); ic=copy.deepcopy(ia); score.calculate_component(ia,"catalysts",POLICY)
    check(ia==ic,"calculate_component does not mutate Catalyst input.")

    total=passed+failed
    print(); print("="*72); print("B.2I.8A CATALYST -> RADAR SCORE RESULT"); print("="*72)
    print("Checks :",total); print("Passed :",passed); print("Failed :",failed); print("RESULT :","PASS" if failed==0 else "FAIL"); print("="*72)
    return 0 if failed==0 else 1

if __name__=="__main__":sys.exit(main())

