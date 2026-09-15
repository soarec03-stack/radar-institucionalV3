import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("ERRO: pandas não instalado. Execute: python -m pip install pandas")
    raise SystemExit(2)

try:
    import yfinance as yf
except ImportError:
    print("ERRO: yfinance não instalado. Execute: python -m pip install yfinance")
    raise SystemExit(2)

# yfinance atual: não ocultar exceções de rede/parsing.
yf.config.debug.hide_exceptions = False


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_METRICS = BASE_DIR / "input" / "metrics_input_v3.json"

DEFAULT_TICKERS = ["VRT", "CRSP", "ETON"]
DEFAULT_BENCHMARK = "SPY"
SOURCE_ID = "YAHOO_FINANCE"


def load_json(path):
    path = Path(path)
    if not path.exists():
        return {
            "metrics_version": "3.0",
            "generated_at": None,
            "market_date": None,
            "assets": []
        }
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def finite_or_none(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, 6)


def normalize_history(df):
    if df is None or df.empty:
        return None

    required = {"Close", "Volume"}
    if not required.issubset(df.columns):
        return None

    out = df.copy()
    out = out.dropna(subset=["Close"])
    if out.empty:
        return None

    return out


def rsi_wilder(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))

    # If loss is truly zero over the relevant smoothed state, RSI tends to 100.
    rsi = rsi.fillna(100.0)
    return rsi


def calculate_metrics(df, benchmark_df):
    df = normalize_history(df)
    benchmark_df = normalize_history(benchmark_df)

    if df is None:
        raise ValueError("Histórico do ativo vazio ou inválido.")
    if benchmark_df is None:
        raise ValueError("Histórico do benchmark vazio ou inválido.")
    if len(df) < 205:
        raise ValueError(
            f"Histórico insuficiente ({len(df)} pregões). "
            "São necessários pelo menos 205 para SMA200."
        )

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)

    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - signal

    rsi14 = rsi_wilder(close, 14)

    latest_close = float(close.iloc[-1])
    latest_sma50 = float(sma50.iloc[-1])
    latest_sma200 = float(sma200.iloc[-1])

    return20 = (latest_close / float(close.iloc[-21]) - 1.0) * 100.0
    return60 = (latest_close / float(close.iloc[-61]) - 1.0) * 100.0

    bclose = benchmark_df["Close"].astype(float)
    if len(bclose) < 21:
        raise ValueError("Histórico insuficiente do benchmark para retorno de 20 dias.")
    benchmark_return20 = (
        float(bclose.iloc[-1]) / float(bclose.iloc[-21]) - 1.0
    ) * 100.0

    previous_20_volume = volume.iloc[-21:-1].replace(0, float("nan")).mean()
    volume_ratio = (
        float(volume.iloc[-1]) / float(previous_20_volume)
        if previous_20_volume and not math.isnan(previous_20_volume)
        else None
    )

    metrics = {
        "price_vs_sma50_pct": finite_or_none(
            (latest_close / latest_sma50 - 1.0) * 100.0
        ),
        "price_vs_sma200_pct": finite_or_none(
            (latest_close / latest_sma200 - 1.0) * 100.0
        ),
        "rsi_14": finite_or_none(rsi14.iloc[-1]),
        "macd_histogram_pct": finite_or_none(
            float(macd_hist.iloc[-1]) / latest_close * 100.0
        ),
        "relative_strength_20d_pct": finite_or_none(
            return20 - benchmark_return20
        ),
        "volume_ratio": finite_or_none(volume_ratio),
        "return_20d_pct": finite_or_none(return20),
        "return_60d_pct": finite_or_none(return60),
    }

    return metrics


def fetch_history(ticker, period="1y"):
    obj = yf.Ticker(ticker)
    df = obj.history(
        period=period,
        interval="1d",
        auto_adjust=True,
        actions=False,
        repair=True,
        timeout=20,
    )
    return normalize_history(df)


def last_market_date(df):
    idx = df.index[-1]
    if hasattr(idx, "date"):
        return idx.date().isoformat()
    return str(idx)[:10]


def get_or_create_asset(metrics_doc, ticker):
    assets = metrics_doc.setdefault("assets", [])
    for asset in assets:
        if asset.get("ticker") == ticker:
            return asset
    asset = {"ticker": ticker}
    assets.append(asset)
    return asset


def build_source(ticker, market_date, retrieved_at, benchmark):
    return {
        "primary_source": SOURCE_ID,
        "secondary_source": benchmark,
        "source_url": f"https://finance.yahoo.com/quote/{ticker}/history/",
        "retrieved_at": retrieved_at,
        "market_date": market_date,
        "sources_attempted": [SOURCE_ID],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Coleta métricas técnicas observáveis para o Radar V3."
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Tickers a coletar. Ex.: VRT CRSP ETON"
    )
    parser.add_argument(
        "--benchmark",
        default=DEFAULT_BENCHMARK,
        help="Benchmark para força relativa. Padrão: SPY"
    )
    parser.add_argument(
        "--period",
        default="1y",
        help="Período histórico do yfinance. Padrão: 1y"
    )
    parser.add_argument(
        "--metrics",
        default=str(DEFAULT_METRICS),
        help="Arquivo metrics_input_v3.json a atualizar."
    )
    parser.add_argument(
        "--output",
        help="Saída opcional. Se omitida, atualiza o arquivo --metrics."
    )
    args = parser.parse_args()

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metrics_path = Path(args.metrics)
    output_path = Path(args.output) if args.output else metrics_path

    doc = load_json(metrics_path)
    doc["metrics_version"] = "3.0"
    doc["generated_at"] = retrieved_at

    print("=" * 72)
    print("TECHNICAL METRICS COLLECTOR V3")
    print("=" * 72)
    print(f"Fonte       : {SOURCE_ID}")
    print(f"Benchmark   : {args.benchmark}")
    print(f"Periodo     : {args.period}")
    print()

    try:
        benchmark_df = fetch_history(args.benchmark, args.period)
    except Exception as exc:
        print(f"ERRO benchmark {args.benchmark}: {exc}")
        return 1

    if benchmark_df is None:
        print(f"ERRO: benchmark {args.benchmark} sem histórico.")
        return 1

    collected = 0
    failed = 0
    latest_dates = []

    for ticker in args.tickers:
        ticker = ticker.upper().strip()

        try:
            df = fetch_history(ticker, args.period)
            if df is None:
                raise ValueError("Histórico vazio.")

            metrics = calculate_metrics(df, benchmark_df)
            market_date = last_market_date(df)

            asset = get_or_create_asset(doc, ticker)
            asset["technical"] = {
                "metrics": metrics,
                "source": build_source(
                    ticker, market_date, retrieved_at, args.benchmark
                )
            }

            latest_dates.append(market_date)
            collected += 1

            print(f"OK {ticker} | market_date={market_date}")
            for key, value in metrics.items():
                print(f"  - {key}: {value}")

        except Exception as exc:
            failed += 1
            print(f"ERRO {ticker}: {exc}")

    if latest_dates:
        doc["market_date"] = max(latest_dates)

    save_json(output_path, doc)

    print()
    print("-" * 72)
    print(f"Coletados : {collected}")
    print(f"Falhas    : {failed}")
    print(f"Saida     : {output_path}")

    if collected == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
