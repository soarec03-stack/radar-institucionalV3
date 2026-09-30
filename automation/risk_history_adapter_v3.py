import math
from datetime import date, datetime


ADAPTER_VERSION = "3.4J.5C-B.2J.5C"


class RiskHistoryValidationError(ValueError):
    """
    Raised when historical market data violates the Risk input boundary.
    """


def parse_market_date(value):
    """
    Accepts only canonical YYYY-MM-DD strings.

    Returns a datetime.date object when valid.
    Raises RiskHistoryValidationError otherwise.
    """
    if not isinstance(value, str):
        raise RiskHistoryValidationError(
            "market_date must be a YYYY-MM-DD string."
        )

    if value != value.strip():
        raise RiskHistoryValidationError(
            "market_date must not contain surrounding whitespace."
        )

    try:
        parsed = datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()
    except ValueError as exc:
        raise RiskHistoryValidationError(
            f"Invalid market_date: {value!r}."
        ) from exc

    # Defensive canonical-format check.
    if parsed.isoformat() != value:
        raise RiskHistoryValidationError(
            f"market_date is not canonical YYYY-MM-DD: {value!r}."
        )

    return parsed


def validate_close(value):
    """
    Boundary semantics:

    None:
        valid missing observation; may be dropped before calculation.

    Positive finite int/float:
        valid observed Close.

    Everything else:
        malformed market data and therefore rejected.

    bool is explicitly rejected because bool is a subclass of int.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        raise RiskHistoryValidationError(
            "Close must not be boolean."
        )

    if not isinstance(value, (int, float)):
        raise RiskHistoryValidationError(
            "Close must be numeric or null."
        )

    numeric = float(value)

    if not math.isfinite(numeric):
        raise RiskHistoryValidationError(
            "Close must be finite."
        )

    if numeric <= 0.0:
        raise RiskHistoryValidationError(
            "Close must be strictly positive."
        )

    return numeric


def normalize_history_records(records):
    """
    Validates and normalizes historical market records.

    Required record shape:

        {
            "market_date": "YYYY-MM-DD",
            "Close": <positive number or None>
        }

    Behavior:
    - records must be a list;
    - every item must be an object/dict;
    - market_date is required and canonical;
    - Close key is required;
    - duplicate market_date is rejected;
    - malformed non-null Close is rejected;
    - null Close is accepted as missing data;
    - output is sorted ascending by market_date;
    - input is not mutated.

    Returns normalized records, including records whose Close is None.
    """
    if not isinstance(records, list):
        raise RiskHistoryValidationError(
            "Historical records must be a list."
        )

    normalized = []
    seen_dates = set()

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise RiskHistoryValidationError(
                f"Historical record at index {index} must be an object."
            )

        if "market_date" not in record:
            raise RiskHistoryValidationError(
                f"Historical record at index {index} is missing market_date."
            )

        if "Close" not in record:
            raise RiskHistoryValidationError(
                f"Historical record at index {index} is missing Close."
            )

        market_date = parse_market_date(
            record["market_date"]
        )

        canonical_date = market_date.isoformat()

        if canonical_date in seen_dates:
            raise RiskHistoryValidationError(
                f"Duplicate market_date: {canonical_date}."
            )

        seen_dates.add(canonical_date)

        close = validate_close(
            record["Close"]
        )

        normalized.append(
            {
                "market_date": canonical_date,
                "Close": close,
            }
        )

    normalized.sort(
        key=lambda item: item["market_date"]
    )

    return normalized


def extract_valid_closes(records):
    """
    Produces the canonical Close[] input expected by
    risk_metrics_calculator_v3.py.

    Validation occurs before missing observations are dropped.

    This ordering is deliberate:
    malformed data must not silently disappear as if it were missing.
    """
    normalized = normalize_history_records(records)

    return [
        record["Close"]
        for record in normalized
        if record["Close"] is not None
    ]


def prepare_risk_history(records):
    """
    Convenience boundary result for diagnostics/integration.

    Keeps the validated chronological records plus the exact Close[]
    passed to the Risk Metrics Calculator.
    """
    normalized = normalize_history_records(records)

    closes = [
        record["Close"]
        for record in normalized
        if record["Close"] is not None
    ]

    return {
        "records": normalized,
        "closes": closes,
        "input_observations": len(normalized),
        "valid_close_observations": len(closes),
        "missing_close_observations": (
            len(normalized) - len(closes)
        ),
    }