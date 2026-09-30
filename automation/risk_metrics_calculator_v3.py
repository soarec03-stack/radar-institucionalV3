import math
from statistics import stdev


CALCULATOR_VERSION = "3.4J.4B-B.2J.4B"

VOLATILITY_RETURN_OBSERVATIONS = 20
VOLATILITY_CLOSES_REQUIRED = 21
DRAWDOWN_CLOSES_REQUIRED = 60
DOWNSIDE_CLOSES_REQUIRED = 21
TRADING_PERIODS_PER_YEAR = 252
OUTPUT_DECIMALS = 6


def is_valid_close(value):
    """
    A valid Close observation must be numeric, finite and strictly positive.
    bool is explicitly rejected because bool is a subclass of int in Python.
    """
    if isinstance(value, bool):
        return False

    if not isinstance(value, (int, float)):
        return False

    value = float(value)

    return math.isfinite(value) and value > 0.0


def normalize_closes(closes):
    """
    Applies the B.2J.4A missing-close policy.

    Invalid/missing Close observations are dropped before calculation.
    Ordering is preserved.

    Date ordering and duplicate-market-date validation belong to the
    history/input boundary because this function intentionally receives
    only the Close series.
    """
    if closes is None:
        return []

    try:
        iterator = iter(closes)
    except TypeError:
        return []

    normalized = []

    for value in iterator:
        if is_valid_close(value):
            normalized.append(float(value))

    return normalized


def calculate_daily_returns(closes):
    """
    Calculates simple close-to-close returns:

        close_t / close_t_minus_1 - 1
    """
    normalized = normalize_closes(closes)

    if len(normalized) < 2:
        return []

    returns = []

    for index in range(1, len(normalized)):
        previous_close = normalized[index - 1]
        current_close = normalized[index]

        daily_return = current_close / previous_close - 1.0
        returns.append(daily_return)

    return returns


def calculate_realized_volatility_20d_pct(closes):
    """
    B.2J.4A:
    - 21 valid closes
    - exactly 20 daily returns
    - sample standard deviation
    - ddof = 1 (statistics.stdev)
    - annualization sqrt(252)
    - percent output
    - no intermediate rounding
    - final output rounded to 6 decimals
    """
    normalized = normalize_closes(closes)

    if len(normalized) < VOLATILITY_CLOSES_REQUIRED:
        return None

    window = normalized[-VOLATILITY_CLOSES_REQUIRED:]
    returns = calculate_daily_returns(window)

    if len(returns) != VOLATILITY_RETURN_OBSERVATIONS:
        return None

    sample_std = stdev(returns)

    result = (
        sample_std
        * math.sqrt(TRADING_PERIODS_PER_YEAR)
        * 100.0
    )

    return round(result, OUTPUT_DECIMALS)


def calculate_max_drawdown_60d_pct(closes):
    """
    B.2J.4A:
    - exactly the last 60 valid closes
    - running peak starts inside the 60-close window
    - no pre-window peak is allowed
    - drawdown = close / running_peak - 1
    - output = abs(min(drawdown)) * 100
    """
    normalized = normalize_closes(closes)

    if len(normalized) < DRAWDOWN_CLOSES_REQUIRED:
        return None

    window = normalized[-DRAWDOWN_CLOSES_REQUIRED:]

    running_peak = window[0]
    minimum_drawdown = 0.0

    for close in window:
        if close > running_peak:
            running_peak = close

        drawdown = close / running_peak - 1.0

        if drawdown < minimum_drawdown:
            minimum_drawdown = drawdown

    result = abs(minimum_drawdown) * 100.0

    return round(result, OUTPUT_DECIMALS)


def calculate_downside_return_20d_pct(closes):
    """
    B.2J.4A:
    - 21 valid closes
    - 20-session close-to-close return
    - positive/zero return => downside risk 0
    - negative return => absolute negative return in percent
    """
    normalized = normalize_closes(closes)

    if len(normalized) < DOWNSIDE_CLOSES_REQUIRED:
        return None

    window = normalized[-DOWNSIDE_CLOSES_REQUIRED:]

    start_close = window[0]
    latest_close = window[-1]

    return_20d_pct = (
        latest_close / start_close - 1.0
    ) * 100.0

    result = max(0.0, -return_20d_pct)

    return round(result, OUTPUT_DECIMALS)


def calculate_risk_metrics(closes):
    """
    Produces only observable/deterministically derived Risk metrics.

    This function does NOT calculate:
    - risk.score
    - risk.level
    - drivers
    - normalized Radar signals
    - Radar points
    - decisions
    """
    return {
        "realized_volatility_20d_pct":
            calculate_realized_volatility_20d_pct(closes),

        "max_drawdown_60d_pct":
            calculate_max_drawdown_60d_pct(closes),

        "downside_return_20d_pct":
            calculate_downside_return_20d_pct(closes),
    }