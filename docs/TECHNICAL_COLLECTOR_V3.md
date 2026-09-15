# Technical Metrics Collector V3

Coleta métricas técnicas observáveis para alimentar o Signal Engine V3.

## Fonte inicial
Yahoo Finance via `yfinance`, classificada no Radar como fonte de desenvolvimento
`TIER_3 / RESEARCH_ONLY`.

## Métricas
- price_vs_sma50_pct
- price_vs_sma200_pct
- rsi_14
- macd_histogram_pct
- relative_strength_20d_pct
- volume_ratio
- return_20d_pct
- return_60d_pct

## Benchmark
SPY por padrão para `relative_strength_20d_pct`.

## Fluxo
technical_metrics_collector_v3.py
→ input/metrics_input_v3.json
→ metrics_loader_v3.py
→ confidence_engine_v3.py
→ signal_engine_v3.py
→ score_engine_v3.py
