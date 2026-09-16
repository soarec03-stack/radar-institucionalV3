"""Radar Institucional V3 - Corporate Action Guard V3.4B.1.
Fail-closed: nao pesquisa a internet e nao infere corporate actions.
Consome somente registry previamente revisado/homologado.
Nao altera radar_v3.json, Signal, Confidence, Score ou Collector A.5.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any

VERSION="3.4B.1"
DEFAULT_POLICY=Path("automation/corporate_action_policy_v3.json")
DEFAULT_REGISTRY=Path("automation/corporate_action_registry_v3.json")
DEFAULT_OUTPUT=Path("input/corporate_action_guard_test_v3.json")
ALLOWED_STATUS={"NOT_CHECKED","NO_ACTION","VERIFIED_ACTION","UNRESOLVED"}
ALLOWED_TYPES={"NONE","STOCK_SPLIT","REVERSE_STOCK_SPLIT","CUSIP_CHANGE","RECLASSIFICATION","OTHER","UNKNOWN"}
SHARE_TYPES={"STOCK_SPLIT","REVERSE_STOCK_SPLIT"}

def read_json(p:Path)->dict[str,Any]:
    with p.open("r",encoding="utf-8") as f:return json.load(f)

def write_json(p:Path,x:dict[str,Any])->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8") as f:
        json.dump(x,f,indent=2,ensure_ascii=False);f.write("\n")

def validate_entry(t:str,e:dict[str,Any])->list[str]:
    z=[]
    s=e.get("status"); a=e.get("action_type")
    if s not in ALLOWED_STATUS:z.append(f"{t}: INVALID_STATUS")
    if a not in ALLOWED_TYPES:z.append(f"{t}: INVALID_ACTION_TYPE")
    if s=="NOT_CHECKED":
        if e.get("verified") is True:z.append(f"{t}: NOT_CHECKED_CANNOT_BE_VERIFIED")
        if e.get("adjustment_required") is True:z.append(f"{t}: NOT_CHECKED_CANNOT_REQUIRE_ADJUSTMENT")
    elif s=="NO_ACTION":
        if a!="NONE":z.append(f"{t}: NO_ACTION_REQUIRES_TYPE_NONE")
        if e.get("verified") is not True:z.append(f"{t}: NO_ACTION_REQUIRES_VERIFIED_TRUE")
        if e.get("window_review_completed") is not True:z.append(f"{t}: NO_ACTION_REQUIRES_WINDOW_REVIEW")
        if e.get("identity_continuity_review") is not True:z.append(f"{t}: NO_ACTION_REQUIRES_IDENTITY_REVIEW")
        if not e.get("evidence"):z.append(f"{t}: NO_ACTION_REQUIRES_EVIDENCE")
    elif s=="VERIFIED_ACTION":
        if a in {"NONE","UNKNOWN"}:z.append(f"{t}: VERIFIED_ACTION_REQUIRES_CONCRETE_TYPE")
        if e.get("verified") is not True:z.append(f"{t}: VERIFIED_ACTION_REQUIRES_VERIFIED_TRUE")
        if not e.get("effective_date"):z.append(f"{t}: VERIFIED_ACTION_REQUIRES_EFFECTIVE_DATE")
        if not e.get("evidence"):z.append(f"{t}: VERIFIED_ACTION_REQUIRES_EVIDENCE")
        if a in SHARE_TYPES:
            n=e.get("ratio_numerator"); d=e.get("ratio_denominator")
            if not isinstance(n,(int,float)) or n<=0:z.append(f"{t}: INVALID_RATIO_NUMERATOR")
            if not isinstance(d,(int,float)) or d<=0:z.append(f"{t}: INVALID_RATIO_DENOMINATOR")
    elif s=="UNRESOLVED":
        if e.get("verified") is True:z.append(f"{t}: UNRESOLVED_CANNOT_BE_VERIFIED")
        if e.get("adjustment_required") is True:z.append(f"{t}: UNRESOLVED_CANNOT_AUTHORIZE_ADJUSTMENT")
    return z

def evaluate_entry(t:str,e:dict[str,Any])->dict[str,Any]:
    errors=validate_entry(t,e)
    r={"ticker":t,"status":e.get("status"),"action_type":e.get("action_type"),"guard_passed":False,"adjustment_authorized":False,"adjustment_factor":None,"adjusted_holdings_allowed":False,"verified":bool(e.get("verified",False)),"effective_date":e.get("effective_date"),"old_cusip":e.get("old_cusip"),"new_cusip":e.get("new_cusip"),"evidence":e.get("evidence",[]),"diagnostics":errors}
    if errors:
        r["status"]="UNRESOLVED";r["diagnostics"].append("REGISTRY_ENTRY_INVALID_FAIL_CLOSED");return r
    s=e["status"]; a=e["action_type"]
    if s=="NOT_CHECKED":r["diagnostics"].append("SOURCE_REVIEW_REQUIRED");return r
    if s=="UNRESOLVED":r["diagnostics"].append("CORPORATE_ACTION_UNRESOLVED");return r
    if s=="NO_ACTION":
        r.update(guard_passed=True,adjustment_authorized=True,adjustment_factor=1.0,adjusted_holdings_allowed=True);return r
    if s=="VERIFIED_ACTION" and a in SHARE_TYPES:
        factor=float(e["ratio_numerator"])/float(e["ratio_denominator"])
        r.update(guard_passed=True,adjustment_authorized=True,adjustment_factor=factor,adjusted_holdings_allowed=True);return r
    if s=="VERIFIED_ACTION":
        r["diagnostics"].append("VERIFIED_NON_SHARE_ACTION_REQUIRES_SEPARATE_RECONCILIATION");return r
    r["diagnostics"].append("UNHANDLED_STATE_FAIL_CLOSED");return r

def run(policy_path:Path,registry_path:Path,output_path:Path)->dict[str,Any]:
    policy=read_json(policy_path); reg=read_json(registry_path); assets=reg.get("assets",{})
    if not isinstance(assets,dict) or not assets:raise RuntimeError("Registry sem assets.")
    results={t:evaluate_entry(t,e) for t,e in assets.items()}
    p={"schema_version":"3.0","guard_version":VERSION,"policy_version":policy.get("version"),"registry_version":reg.get("registry_version"),"comparison_window":reg.get("comparison_window"),"assets":results}
    p["summary"]={"total":len(results),"passed":sum(x["guard_passed"] for x in results.values()),"blocked":sum(not x["guard_passed"] for x in results.values()),"not_checked":sum(x["status"]=="NOT_CHECKED" for x in results.values()),"no_action":sum(x["status"]=="NO_ACTION" for x in results.values()),"verified_action":sum(x["status"]=="VERIFIED_ACTION" for x in results.values()),"unresolved":sum(x["status"]=="UNRESOLVED" for x in results.values())}
    write_json(output_path,p);return p

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--policy",type=Path,default=DEFAULT_POLICY);ap.add_argument("--registry",type=Path,default=DEFAULT_REGISTRY);ap.add_argument("--output",type=Path,default=DEFAULT_OUTPUT);a=ap.parse_args()
    print("="*68);print("RADAR INSTITUCIONAL V3");print(f"CORPORATE ACTION GUARD - VERSION {VERSION}");print("="*68)
    try:p=run(a.policy,a.registry,a.output)
    except Exception as exc:print(f"ERRO: {exc}",file=sys.stderr);return 1
    w=p["comparison_window"];print(f"Janela: {w.get('previous_period')} -> {w.get('current_period')}");print("-"*68)
    for t,r in p["assets"].items():
        ft="N/D" if r["adjustment_factor"] is None else f"{r['adjustment_factor']:.8f}"
        print(f"{t:6} status={r['status']:16} guard={'PASS' if r['guard_passed'] else 'BLOCK':5} factor={ft}")
        for d in r["diagnostics"]:print(f"       ! {d}")
    s=p["summary"];print("-"*68);print(f"Total={s['total']} Passed={s['passed']} Blocked={s['blocked']} NOT_CHECKED={s['not_checked']} NO_ACTION={s['no_action']} VERIFIED_ACTION={s['verified_action']} UNRESOLVED={s['unresolved']}");print(f"Gerado: {a.output}");print("="*68);return 0
if __name__=="__main__":raise SystemExit(main())
