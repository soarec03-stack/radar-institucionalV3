# Fundamentals Collector V3 — SEC EDGAR

Primeiro coletor fundamentalista quantitativo do Radar Institucional V3.

## Fonte

SEC EDGAR / `data.sec.gov` / Company Facts XBRL.

Classificação do Radar:

- Source ID: `SEC`
- Tier: `TIER_1`
- Dados regulatórios oficiais
- Sem API key

## Métricas calculadas

Quando os tags XBRL necessários existem:

- `revenue_growth_pct`
- `eps_growth_pct`
- `fcf_margin_pct`
- `debt_to_ebitda`

Mantidas como `null` nesta etapa:

- `earnings_revision_pct`
- `valuation_percentile`

Essas duas últimas não são fatos regulatórios SEC e deverão ser alimentadas
por coletores específicos de estimativas/market valuation.

## Regras conservadoras

- Apenas fatos anuais `10-K` / `10-K/A`
- Não inventa tags ausentes
- EPS growth não é calculado quando o EPS anterior é <= 0
- Debt/EBITDA só é calculado quando Debt, Operating Income e D&A estão disponíveis
  e o EBITDA aproximado é positivo
- FCF = Cash Flow from Operations - Capex
- Provenance explícita por domínio

## User-Agent SEC

Antes de executar no PowerShell:

```powershell
$env:SEC_USER_AGENT="RadarInstitucionalV3/3.0 seu-email@dominio.com"
```

Use um contato válido, conforme as práticas de acesso automatizado da SEC.

## Execução recomendada

Preservando as métricas técnicas já coletadas:

```powershell
python automation\fundamentals_collector_v3.py `
  --tickers VRT CRSP ETON `
  --metrics input\metrics_technical_test_v3.json `
  --output input\metrics_fundamentals_test_v3.json
```

Depois:

```powershell
python automation\metrics_loader_v3.py `
  --radar radar_v3.json `
  --metrics input\metrics_fundamentals_test_v3.json `
  --output radar_v3_metrics_test.json

python automation\confidence_engine_v3.py `
  radar_v3_metrics_test.json `
  --output radar_v3_confidence_metrics_test.json

python automation\signal_engine_v3.py `
  radar_v3_confidence_metrics_test.json `
  --output radar_v3_signals_test.json

python automation\score_engine_v3.py `
  radar_v3_signals_test.json `
  --output radar_v3_score_test.json
```
