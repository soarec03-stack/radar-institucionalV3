import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_METRICS = BASE_DIR / "input" / "metrics_input_v3.json"

DEFAULT_TICKERS = ["VRT", "CRSP", "ETON"]

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

SOURCE_ID = "SEC"
REQUEST_DELAY_SECONDS = 0.20

ANNUAL_FORMS = {"10-K", "10-K/A"}


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def fetch_json(url, user_agent):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()

            # urllib normally handles neither gzip nor deflate automatically.
            encoding = response.headers.get("Content-Encoding", "").lower()

            if encoding == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            elif encoding == "deflate":
                import zlib
                raw = zlib.decompress(raw)

            return json.loads(raw.decode("utf-8"))

    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"HTTP {exc.code} ao acessar {url}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Falha de rede ao acessar {url}: {exc.reason}"
        ) from exc


def get_ticker_map(user_agent):
    data = fetch_json(SEC_TICKERS_URL, user_agent)

    result = {}

    if isinstance(data, dict):
        for _, item in data.items():
            if not isinstance(item, dict):
                continue

            ticker = str(item.get("ticker", "")).upper().strip()
            cik = item.get("cik_str")

            if ticker and cik is not None:
                result[ticker] = {
                    "cik": int(cik),
                    "title": item.get("title"),
                }

    return result


def get_us_gaap_facts(companyfacts):
    facts = companyfacts.get("facts", {})

    if not isinstance(facts, dict):
        return {}

    return facts.get("us-gaap", {}) or {}


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def duration_days(item):
    start = parse_date(item.get("start"))
    end = parse_date(item.get("end"))

    if start is None or end is None:
        return None

    return (end - start).days


def get_tag_entries(us_gaap, tag, unit):
    fact = us_gaap.get(tag)

    if not isinstance(fact, dict):
        return []

    units = fact.get("units", {})

    if not isinstance(units, dict):
        return []

    entries = units.get(unit, [])

    return entries if isinstance(entries, list) else []


def annual_duration_entries(us_gaap, tag, unit):
    """
    Seleciona fatos anuais 10-K/10-K/A, preferindo períodos FY e duração
    aproximadamente anual. Deduplica pelo fiscal year/end usando o filing
    mais recente para evitar duplicação por amendments.
    """
    entries = get_tag_entries(us_gaap, tag, unit)

    candidates = []

    for item in entries:
        if not isinstance(item, dict):
            continue

        if item.get("form") not in ANNUAL_FORMS:
            continue

        days = duration_days(item)

        if days is None or days < 250 or days > 430:
            continue

        value = item.get("val")

        if not isinstance(value, (int, float)):
            continue

        candidates.append(item)

    # Deduplica por end date, mantendo o filing mais recente.
    by_end = {}

    for item in candidates:
        end = item.get("end")
        filed = item.get("filed", "")

        current = by_end.get(end)

        if current is None or filed > current.get("filed", ""):
            by_end[end] = item

    return sorted(
        by_end.values(),
        key=lambda x: (x.get("end", ""), x.get("filed", "")),
    )


def latest_two_annual(us_gaap, tags, unit):
    """
    Tenta tags alternativas e escolhe a primeira que ofereça pelo menos
    dois anos anuais comparáveis.
    """
    for tag in tags:
        entries = annual_duration_entries(us_gaap, tag, unit)

        if len(entries) >= 2:
            return tag, entries[-2], entries[-1]

    return None, None, None


def latest_annual(us_gaap, tags, unit, target_end=None):
    for tag in tags:
        entries = annual_duration_entries(us_gaap, tag, unit)

        if target_end:
            entries = [x for x in entries if x.get("end") == target_end]

        if entries:
            return tag, entries[-1]

    return None, None


def instant_entry_at_end(us_gaap, tags, unit, target_end):
    """
    Procura fatos de balanço na data do fim do exercício.
    """
    for tag in tags:
        entries = get_tag_entries(us_gaap, tag, unit)

        candidates = []

        for item in entries:
            if not isinstance(item, dict):
                continue

            if item.get("form") not in ANNUAL_FORMS:
                continue

            if item.get("end") != target_end:
                continue

            value = item.get("val")

            if not isinstance(value, (int, float)):
                continue

            candidates.append(item)

        if candidates:
            candidates.sort(key=lambda x: x.get("filed", ""))
            return tag, candidates[-1]

    return None, None


def pct_growth(current, previous):
    if previous is None or current is None:
        return None

    previous = float(previous)
    current = float(current)

    if previous <= 0:
        return None

    return ((current / previous) - 1.0) * 100.0


def round_metric(value):
    if value is None:
        return None

    return round(float(value), 6)


def compute_total_debt(us_gaap, target_end):
    """
    Estratégia conservadora:
    1. Current + noncurrent debt/finance lease tags.
    2. Current + noncurrent long-term debt tags.
    3. LongTermDebt total como fallback.

    Não soma ShortTermBorrowings isoladamente para evitar double count.
    """
    pairs = [
        (
            ["LongTermDebtAndFinanceLeaseObligationsCurrent"],
            ["LongTermDebtAndFinanceLeaseObligationsNoncurrent"],
        ),
        (
            ["LongTermDebtCurrent"],
            ["LongTermDebtNoncurrent"],
        ),
    ]

    for current_tags, noncurrent_tags in pairs:
        _, current_item = instant_entry_at_end(
            us_gaap, current_tags, "USD", target_end
        )
        _, noncurrent_item = instant_entry_at_end(
            us_gaap, noncurrent_tags, "USD", target_end
        )

        if current_item is not None or noncurrent_item is not None:
            current_value = (
                float(current_item["val"])
                if current_item is not None
                else 0.0
            )
            noncurrent_value = (
                float(noncurrent_item["val"])
                if noncurrent_item is not None
                else 0.0
            )
            return current_value + noncurrent_value

    _, total_item = instant_entry_at_end(
        us_gaap,
        ["LongTermDebt"],
        "USD",
        target_end,
    )

    if total_item is not None:
        return float(total_item["val"])

    return None


def calculate_fundamentals(companyfacts):
    us_gaap = get_us_gaap_facts(companyfacts)

    metrics = {
        "revenue_growth_pct": None,
        "eps_growth_pct": None,
        "fcf_margin_pct": None,
        "debt_to_ebitda": None,
        "earnings_revision_pct": None,
        "valuation_percentile": None,
    }

    diagnostics = []

    revenue_tags = [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ]

    eps_tags = [
        "EarningsPerShareDiluted",
    ]

    cfo_tags = [
        "NetCashProvidedByUsedInOperatingActivities",
    ]

    capex_tags = [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ]

    operating_income_tags = [
        "OperatingIncomeLoss",
    ]

    da_tags = [
        "DepreciationDepletionAndAmortization",
        "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
    ]

    revenue_tag, revenue_prev, revenue_latest = latest_two_annual(
        us_gaap, revenue_tags, "USD"
    )

    fiscal_end = revenue_latest.get("end") if revenue_latest else None

    if revenue_latest and revenue_prev:
        metrics["revenue_growth_pct"] = round_metric(
            pct_growth(revenue_latest["val"], revenue_prev["val"])
        )
        diagnostics.append(
            f"revenue={revenue_tag} ({revenue_prev.get('end')} -> {revenue_latest.get('end')})"
        )
    else:
        diagnostics.append("revenue_growth=N/D")

    eps_tag, eps_prev, eps_latest = latest_two_annual(
        us_gaap, eps_tags, "USD/shares"
    )

    if eps_latest and eps_prev:
        metrics["eps_growth_pct"] = round_metric(
            pct_growth(eps_latest["val"], eps_prev["val"])
        )

        if metrics["eps_growth_pct"] is None:
            diagnostics.append(
                "eps_growth=N/D (EPS anterior <= 0; crescimento percentual não usado)"
            )
        else:
            diagnostics.append(
                f"eps={eps_tag} ({eps_prev.get('end')} -> {eps_latest.get('end')})"
            )
    else:
        diagnostics.append("eps_growth=N/D")

    # FCF margin usa o mesmo fiscal_end da receita mais recente.
    if fiscal_end and revenue_latest:
        _, cfo = latest_annual(
            us_gaap, cfo_tags, "USD", target_end=fiscal_end
        )
        _, capex = latest_annual(
            us_gaap, capex_tags, "USD", target_end=fiscal_end
        )

        revenue = float(revenue_latest["val"])

        if (
            cfo is not None
            and capex is not None
            and revenue != 0
        ):
            # Tags de Payments... normalmente são valores positivos de saída.
            free_cash_flow = float(cfo["val"]) - abs(float(capex["val"]))
            metrics["fcf_margin_pct"] = round_metric(
                (free_cash_flow / revenue) * 100.0
            )
            diagnostics.append("fcf_margin=CFO-CAPEX / Revenue")
        else:
            diagnostics.append("fcf_margin=N/D")

    # Debt / EBITDA = debt / (Operating Income + D&A)
    if fiscal_end:
        debt = compute_total_debt(us_gaap, fiscal_end)

        _, operating_income = latest_annual(
            us_gaap,
            operating_income_tags,
            "USD",
            target_end=fiscal_end,
        )

        _, da = latest_annual(
            us_gaap,
            da_tags,
            "USD",
            target_end=fiscal_end,
        )

        if (
            debt is not None
            and operating_income is not None
            and da is not None
        ):
            ebitda = float(operating_income["val"]) + abs(float(da["val"]))

            if ebitda > 0:
                metrics["debt_to_ebitda"] = round_metric(
                    debt / ebitda
                )
                diagnostics.append("debt_to_ebitda=Debt/(OperatingIncome+D&A)")
            else:
                diagnostics.append(
                    "debt_to_ebitda=N/D (EBITDA aproximado <= 0)"
                )
        else:
            diagnostics.append("debt_to_ebitda=N/D")

    diagnostics.append(
        "earnings_revision_pct=N/D (não é fato regulatório SEC)"
    )
    diagnostics.append(
        "valuation_percentile=N/D (requer série de valuation/market data)"
    )

    non_null = sum(
        1 for value in metrics.values()
        if value is not None
    )

    return metrics, fiscal_end, diagnostics, non_null


def get_or_create_asset(doc, ticker):
    assets = doc.setdefault("assets", [])

    for asset in assets:
        if asset.get("ticker") == ticker:
            return asset

    asset = {"ticker": ticker}
    assets.append(asset)
    return asset


def build_source(cik, market_date, retrieved_at):
    return {
        "primary_source": SOURCE_ID,
        "secondary_source": None,
        "source_url": SEC_COMPANYFACTS_URL.format(cik=cik),
        "retrieved_at": retrieved_at,
        "market_date": market_date,
        "sources_attempted": [SOURCE_ID],
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Coleta métricas fundamentalistas observáveis do SEC EDGAR "
            "Company Facts para o Radar V3."
        )
    )

    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Tickers a coletar. Ex.: VRT CRSP ETON",
    )

    parser.add_argument(
        "--metrics",
        default=str(DEFAULT_METRICS),
        help=(
            "Arquivo base de métricas. Pode ser metrics_input_v3.json "
            "ou o arquivo técnico já coletado."
        ),
    )

    parser.add_argument(
        "--output",
        help="Saída. Se omitida, atualiza o arquivo informado em --metrics.",
    )

    parser.add_argument(
        "--user-agent",
        default=os.environ.get("SEC_USER_AGENT"),
        help=(
            "User-Agent para SEC. Preferencialmente configure SEC_USER_AGENT. "
            'Ex.: "RadarInstitucionalV3/3.0 seu-email@dominio.com"'
        ),
    )

    args = parser.parse_args()

    if not args.user_agent:
        print(
            "ERRO: SEC_USER_AGENT não configurado.\n"
            "Configure antes de executar, por exemplo no PowerShell:\n"
            '$env:SEC_USER_AGENT="RadarInstitucionalV3/3.0 seu-email@dominio.com"'
        )
        return 2

    retrieved_at = utc_now()
    metrics_path = Path(args.metrics)
    output_path = Path(args.output) if args.output else metrics_path

    doc = load_json(metrics_path)
    doc["metrics_version"] = "3.0"
    doc["generated_at"] = retrieved_at

    print("=" * 72)
    print("FUNDAMENTALS COLLECTOR V3 — SEC EDGAR / COMPANY FACTS")
    print("=" * 72)
    print("Fonte       : SEC")
    print("Tier        : TIER_1")
    print("Metodologia: fatos anuais 10-K / XBRL")
    print()

    try:
        ticker_map = get_ticker_map(args.user_agent)
    except Exception as exc:
        print(f"ERRO ao carregar mapa ticker/CIK da SEC: {exc}")
        return 1

    time.sleep(REQUEST_DELAY_SECONDS)

    collected = 0
    failed = 0
    latest_dates = []

    for raw_ticker in args.tickers:
        ticker = raw_ticker.upper().strip()

        mapping = ticker_map.get(ticker)

        if not mapping:
            failed += 1
            print(f"ERRO {ticker}: ticker não encontrado no mapa oficial SEC.")
            continue

        cik = mapping["cik"]

        try:
            url = SEC_COMPANYFACTS_URL.format(cik=cik)
            companyfacts = fetch_json(url, args.user_agent)

            metrics, market_date, diagnostics, non_null = (
                calculate_fundamentals(companyfacts)
            )

            if non_null == 0:
                raise ValueError(
                    "Nenhuma métrica fundamentalista calculável encontrada."
                )

            asset = get_or_create_asset(doc, ticker)
            asset["fundamentals"] = {
                "metrics": metrics,
                "source": build_source(
                    cik,
                    market_date,
                    retrieved_at,
                ),
            }

            collected += 1

            if market_date:
                latest_dates.append(market_date)

            entity_name = (
                companyfacts.get("entityName")
                or mapping.get("title")
                or ticker
            )

            print(
                f"OK {ticker} | {entity_name} | "
                f"CIK={cik:010d} | fiscal_end={market_date}"
            )

            for key, value in metrics.items():
                print(f"  - {key}: {value}")

            for diag in diagnostics:
                print(f"      {diag}")

        except Exception as exc:
            failed += 1
            print(f"ERRO {ticker}: {exc}")

        time.sleep(REQUEST_DELAY_SECONDS)

    if latest_dates:
        # Este campo é apenas informativo do arquivo de staging.
        # Cada domínio mantém seu próprio source.market_date.
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
