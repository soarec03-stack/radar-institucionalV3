import argparse, json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

FRED_API="https://api.stlouisfed.org/fred/series/observations"
SERIES={"rates":"DGS10","dollar":"DTWEXBGS","liquidity":"WALCL"}

def load_json(p):
    with open(p,"r",encoding="utf-8") as f: return json.load(f)
def save_json(p,d):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    with open(p,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2); f.write("\n")
def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def fetch(series,key):
    q=urllib.parse.urlencode({"series_id":series,"api_key":key,"file_type":"json","sort_order":"asc"})
    req=urllib.request.Request(FRED_API+"?"+q,headers={"User-Agent":"RadarInstitucionalV3/3.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r: data=json.loads(r.read().decode())
    out=[]
    for x in data.get("observations",[]):
        if x.get("value") in (None,"."): continue
        try: v=float(x["value"])
        except: continue
        out.append({"date":x["date"],"value":v})
    if not out: raise ValueError(f"{series} sem observações utilizáveis")
    return out
def prior20(obs):
    latest=datetime.strptime(obs[-1]["date"],"%Y-%m-%d").date()
    target=latest-timedelta(days=20)
    c=[x for x in obs if datetime.strptime(x["date"],"%Y-%m-%d").date()<=target]
    return c[-1] if c else None
def pct(a,b):
    return None if b==0 else (a/b-1)*100
def asset(doc,ticker):
    for a in doc.setdefault("assets",[]):
        if str(a.get("ticker","")).upper()==ticker: return a
    a={"ticker":ticker}; doc["assets"].append(a); return a

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tickers",nargs="+",default=["VRT","CRSP","ETON"])
    ap.add_argument("--metrics",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--api-key",default=os.environ.get("FRED_API_KEY"))
    a=ap.parse_args()
    if not a.api_key:
        print('ERRO: configure $env:FRED_API_KEY="sua_chave_fred"'); return 2
    doc=load_json(a.metrics); retrieved=now()
    print("="*72); print("MACRO COLLECTOR V3 — FRED / FEDERAL RESERVE"); print("="*72)
    raw={}
    try:
        for name,sid in SERIES.items():
            obs=fetch(sid,a.api_key); raw[name]={"latest":obs[-1],"previous":prior20(obs)}
    except Exception as e:
        print(f"ERRO na coleta macro: {e}"); return 1
    m={"rates_change_20d_bps":None,"dollar_change_20d_pct":None,"liquidity_change_20d_pct":None,"sector_macro_surprise_pct":None}
    if raw["rates"]["previous"]:
        m["rates_change_20d_bps"]=round((raw["rates"]["latest"]["value"]-raw["rates"]["previous"]["value"])*100,6)
    if raw["dollar"]["previous"]:
        m["dollar_change_20d_pct"]=round(pct(raw["dollar"]["latest"]["value"],raw["dollar"]["previous"]["value"]),6)
    if raw["liquidity"]["previous"]:
        m["liquidity_change_20d_pct"]=round(pct(raw["liquidity"]["latest"]["value"],raw["liquidity"]["previous"]["value"]),6)
    market_date=min(x["latest"]["date"] for x in raw.values())
    source={"primary_source":"FRED","secondary_source":None,"source_url":"https://fred.stlouisfed.org/","retrieved_at":retrieved,"market_date":market_date,"sources_attempted":["FRED"],"series":["DGS10","DTWEXBGS","WALCL"]}
    for t in a.tickers:
        t=t.upper().strip(); x=asset(doc,t); x["macro"]={"metrics":dict(m),"source":dict(source)}
        print(f"OK {t} | macro snapshot={market_date}")
        for k,v in m.items(): print(f"  - {k}: {v}")
    print("  sector_macro_surprise_pct=N/D (sem proxy institucional aprovado)")
    doc["generated_at"]=retrieved; save_json(a.output,doc)
    print(); print("-"*72); print(f"Saida: {a.output}"); return 0
if __name__=="__main__": sys.exit(main())
