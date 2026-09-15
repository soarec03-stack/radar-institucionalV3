# Macro Collector V3

Fonte inicial: FRED (TIER_1).

Séries:
- DGS10 — Treasury 10-Year Constant Maturity
- DTWEXBGS — Nominal Broad U.S. Dollar Index
- WALCL — Federal Reserve Total Assets

Métricas:
- rates_change_20d_bps
- dollar_change_20d_pct
- liquidity_change_20d_pct
- sector_macro_surprise_pct = null

Não há interpolação: a comparação usa a observação real mais recente em ou antes de 20 dias corridos antes da última observação.

## Configuração

A API oficial FRED exige API key:

```powershell
$env:FRED_API_KEY="SUA_CHAVE_FRED"
```

## Execução

```powershell
python automation\macro_collector_v3.py `
  --tickers VRT CRSP ETON `
  --metrics input\metrics_fundamentals_test_v3.json `
  --output input\metrics_macro_test_v3.json
```
