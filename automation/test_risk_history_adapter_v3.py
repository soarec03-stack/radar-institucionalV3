from copy import deepcopy
from datetime import date, timedelta
import math
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


from risk_history_adapter_v3 import (
    ADAPTER_VERSION,
    RiskHistoryValidationError,
    extract_valid_closes,
    normalize_history_records,
    parse_market_date,
    prepare_risk_history,
    validate_close,
)

from risk_metrics_calculator_v3 import (
    CALCULATOR_VERSION,
    calculate_risk_metrics,
)

from risk_engine_v3 import (
    ENGINE_VERSION,
    STATUS_CALCULATED,
    calculate_asset_risk,
    load_policy,
    write_risk_to_asset,
)


TEST_VERSION = "3.4J.5C-B.2J.5C"

EXPECTED_ADAPTER_VERSION = "3.4J.5C-B.2J.5C"
EXPECTED_CALCULATOR_VERSION = "3.4J.4B-B.2J.4B"
EXPECTED_ENGINE_VERSION = "3.4J.5A-B.2J.5A"
EXPECTED_POLICY_VERSION = "3.4J.3B-B.2J.3B"

passed = 0
failed = 0


def check(condition, description):
    global passed, failed

    if condition:
        passed += 1
        print(f"[PASS] {description}")
    else:
        failed += 1
        print(f"[FAIL] {description}")


def raises_validation_error(function, *args):
    try:
        function(*args)
    except RiskHistoryValidationError:
        return True
    except Exception:
        return False

    return False


def build_history(
    count,
    start_date=date(2026, 1, 1),
    close_factory=None,
):
    records = []

    for index in range(count):
        current_date = (
            start_date + timedelta(days=index)
        )

        if close_factory is None:
            close = 100.0
        else:
            close = close_factory(index)

        records.append(
            {
                "market_date": current_date.isoformat(),
                "Close": close,
            }
        )

    return records


print("=" * 72)
print("B.2J.5C HISTORICAL RISK INPUT BOUNDARY")
print(f"Test:       {TEST_VERSION}")
print(f"Adapter:    {EXPECTED_ADAPTER_VERSION}")
print(f"Calculator: {EXPECTED_CALCULATOR_VERSION}")
print(f"Engine:     {EXPECTED_ENGINE_VERSION}")
print(f"Policy:     {EXPECTED_POLICY_VERSION}")
print("=" * 72)


policy = load_policy()


# ---------------------------------------------------------------------
# VERSION BOUNDARY
# ---------------------------------------------------------------------

check(
    ADAPTER_VERSION == EXPECTED_ADAPTER_VERSION,
    "Historical Risk Adapter version is B.2J.5C."
)

check(
    CALCULATOR_VERSION == EXPECTED_CALCULATOR_VERSION,
    "Boundary consumes homologated B.2J.4B Calculator."
)

check(
    ENGINE_VERSION == EXPECTED_ENGINE_VERSION,
    "Boundary consumes homologated B.2J.5A Risk Engine."
)

check(
    policy.get("policy_version") == EXPECTED_POLICY_VERSION,
    "Boundary consumes homologated B.2J.3B Risk Policy."
)


# ---------------------------------------------------------------------
# market_date VALIDATION
# ---------------------------------------------------------------------

parsed_date = parse_market_date(
    "2026-09-30"
)

check(
    parsed_date.isoformat() == "2026-09-30",
    "Canonical YYYY-MM-DD market_date is accepted."
)

check(
    raises_validation_error(
        parse_market_date,
        None,
    ),
    "Null market_date is rejected."
)

check(
    raises_validation_error(
        parse_market_date,
        20260930,
    ),
    "Numeric market_date is rejected."
)

check(
    raises_validation_error(
        parse_market_date,
        "30/09/2026",
    ),
    "Non-ISO market_date is rejected."
)

check(
    raises_validation_error(
        parse_market_date,
        "2026-02-30",
    ),
    "Impossible calendar market_date is rejected."
)

check(
    raises_validation_error(
        parse_market_date,
        " 2026-09-30 ",
    ),
    "market_date with surrounding whitespace is rejected."
)


# ---------------------------------------------------------------------
# Close VALIDATION
# ---------------------------------------------------------------------

check(
    validate_close(100) == 100.0,
    "Positive integer Close is accepted."
)

check(
    validate_close(100.25) == 100.25,
    "Positive float Close is accepted."
)

check(
    validate_close(None) is None,
    "Null Close is accepted as missing observation."
)

check(
    raises_validation_error(
        validate_close,
        0,
    ),
    "Zero Close is rejected at historical boundary."
)

check(
    raises_validation_error(
        validate_close,
        -10.0,
    ),
    "Negative Close is rejected at historical boundary."
)

check(
    raises_validation_error(
        validate_close,
        "100.25",
    ),
    "String Close is rejected rather than coerced."
)

check(
    raises_validation_error(
        validate_close,
        True,
    ),
    "Boolean Close is rejected."
)

check(
    raises_validation_error(
        validate_close,
        float("nan"),
    ),
    "NaN Close is rejected."
)

check(
    raises_validation_error(
        validate_close,
        float("inf"),
    ),
    "Infinite Close is rejected."
)


# ---------------------------------------------------------------------
# CONTAINER / RECORD VALIDATION
# ---------------------------------------------------------------------

check(
    raises_validation_error(
        normalize_history_records,
        None,
    ),
    "Null historical collection is rejected."
)

check(
    raises_validation_error(
        normalize_history_records,
        {},
    ),
    "Non-list historical collection is rejected."
)

check(
    raises_validation_error(
        normalize_history_records,
        ["bad-record"],
    ),
    "Non-object historical record is rejected."
)

check(
    raises_validation_error(
        normalize_history_records,
        [
            {
                "Close": 100.0,
            }
        ],
    ),
    "Record missing market_date is rejected."
)

check(
    raises_validation_error(
        normalize_history_records,
        [
            {
                "market_date": "2026-09-30",
            }
        ],
    ),
    "Record missing Close key is rejected."
)


# ---------------------------------------------------------------------
# ASCENDING ORDER
# ---------------------------------------------------------------------

unordered = [
    {
        "market_date": "2026-09-03",
        "Close": 103.0,
    },
    {
        "market_date": "2026-09-01",
        "Close": 101.0,
    },
    {
        "market_date": "2026-09-02",
        "Close": 102.0,
    },
]

normalized_unordered = normalize_history_records(
    unordered
)

check(
    [
        item["market_date"]
        for item in normalized_unordered
    ]
    == [
        "2026-09-01",
        "2026-09-02",
        "2026-09-03",
    ],
    "Historical records are sorted ascending by market_date."
)

check(
    [
        item["Close"]
        for item in normalized_unordered
    ]
    == [
        101.0,
        102.0,
        103.0,
    ],
    "Ascending sort preserves each market_date/Close relationship."
)


# ---------------------------------------------------------------------
# DUPLICATE DATE REJECTION
# ---------------------------------------------------------------------

duplicate_dates = [
    {
        "market_date": "2026-09-01",
        "Close": 100.0,
    },
    {
        "market_date": "2026-09-01",
        "Close": 101.0,
    },
]

check(
    raises_validation_error(
        normalize_history_records,
        duplicate_dates,
    ),
    "Duplicate market_date is rejected."
)


# ---------------------------------------------------------------------
# MISSING Close SEMANTICS
# ---------------------------------------------------------------------

history_with_missing = [
    {
        "market_date": "2026-09-03",
        "Close": 103.0,
    },
    {
        "market_date": "2026-09-01",
        "Close": 101.0,
    },
    {
        "market_date": "2026-09-02",
        "Close": None,
    },
]

normalized_missing = normalize_history_records(
    history_with_missing
)

check(
    len(normalized_missing) == 3,
    "Normalized history preserves missing Close observation."
)

check(
    normalized_missing[1]["market_date"]
    == "2026-09-02",
    "Missing Close remains attached to its chronological market_date."
)

check(
    normalized_missing[1]["Close"] is None,
    "Missing Close remains null before calculation boundary."
)

valid_closes = extract_valid_closes(
    history_with_missing
)

check(
    valid_closes == [
        101.0,
        103.0,
    ],
    "Missing Close is dropped before Risk metric calculation."
)


# ---------------------------------------------------------------------
# MALFORMED Close MUST NOT SILENTLY DISAPPEAR
# ---------------------------------------------------------------------

malformed_history = [
    {
        "market_date": "2026-09-01",
        "Close": 100.0,
    },
    {
        "market_date": "2026-09-02",
        "Close": "BAD",
    },
    {
        "market_date": "2026-09-03",
        "Close": 102.0,
    },
]

check(
    raises_validation_error(
        extract_valid_closes,
        malformed_history,
    ),
    "Malformed non-null Close is rejected rather than dropped."
)


# ---------------------------------------------------------------------
# PREPARE RESULT
# ---------------------------------------------------------------------

prepared = prepare_risk_history(
    history_with_missing
)

check(
    set(prepared.keys())
    == {
        "records",
        "closes",
        "input_observations",
        "valid_close_observations",
        "missing_close_observations",
    },
    "Prepared Risk history exposes only canonical boundary fields."
)

check(
    prepared["input_observations"] == 3,
    "Prepared history counts all input observations."
)

check(
    prepared["valid_close_observations"] == 2,
    "Prepared history counts valid Close observations."
)

check(
    prepared["missing_close_observations"] == 1,
    "Prepared history counts missing Close observations."
)

check(
    prepared["closes"] == [
        101.0,
        103.0,
    ],
    "Prepared history emits chronological valid Close array."
)


# ---------------------------------------------------------------------
# INPUT IMMUTABILITY
# ---------------------------------------------------------------------

unordered_before = deepcopy(
    unordered
)

normalize_history_records(
    unordered
)

check(
    unordered == unordered_before,
    "Historical Adapter does not mutate raw input records."
)


# =====================================================================
# FULL BOUNDARY -> CALCULATOR -> ENGINE -> asset.risk
# =====================================================================

full_history = build_history(
    60,
    close_factory=lambda index: (
        100.0
        + (index * 0.30)
        + (
            2.0
            if index % 4 == 0
            else -1.0
            if index % 4 == 1
            else 0.5
            if index % 4 == 2
            else 0.0
        )
    ),
)

# Deliberately reverse the input to prove that the Adapter,
# rather than the caller, establishes chronological order.
full_history_reversed = list(
    reversed(full_history)
)

prepared_full = prepare_risk_history(
    full_history_reversed
)

check(
    prepared_full["input_observations"] == 60,
    "Full boundary receives exactly 60 historical observations."
)

check(
    prepared_full["valid_close_observations"] == 60,
    "Full boundary preserves 60 valid Close observations."
)

check(
    prepared_full["missing_close_observations"] == 0,
    "Full boundary reports zero missing Close observations."
)

check(
    prepared_full["records"][0]["market_date"]
    < prepared_full["records"][-1]["market_date"],
    "Full boundary output is chronological despite reversed input."
)

risk_metrics = calculate_risk_metrics(
    prepared_full["closes"]
)

check(
    risk_metrics["realized_volatility_20d_pct"]
    is not None,
    "Boundary output produces realized volatility."
)

check(
    risk_metrics["max_drawdown_60d_pct"]
    is not None,
    "Boundary output produces max drawdown."
)

check(
    risk_metrics["downside_return_20d_pct"]
    is not None,
    "Boundary output produces downside return."
)

analytical_risk = calculate_asset_risk(
    risk_metrics,
    policy,
)

check(
    analytical_risk["status"]
    == STATUS_CALCULATED,
    "Boundary -> Calculator -> Engine produces CALCULATED Risk."
)

check(
    analytical_risk["coverage"] == 1.0,
    "Full historical boundary produces Risk coverage 1.0."
)

asset = {
    "ticker": "TEST_BOUNDARY",
    "name": "Synthetic Historical Boundary Asset",
}

written_asset = write_risk_to_asset(
    deepcopy(asset),
    analytical_risk,
)

check(
    "risk" in written_asset,
    "Full historical pipeline creates public asset.risk."
)

check(
    set(written_asset["risk"].keys())
    == {
        "score",
        "level",
        "drivers",
    },
    "Historical pipeline preserves strict public asset.risk shape."
)

check(
    isinstance(
        written_asset["risk"]["score"],
        float,
    ),
    "Historical pipeline produces numeric public Risk score."
)

check(
    written_asset["risk"]["level"]
    in {
        "LOW",
        "MODERATE",
        "HIGH",
        "VERY_HIGH",
        "CRITICAL",
    },
    "Historical pipeline produces canonical Schema V3 Risk level."
)

check(
    isinstance(
        written_asset["risk"]["drivers"],
        list,
    ),
    "Historical pipeline produces Risk drivers list."
)


# =====================================================================
# MISSING OBSERVATION WITH SUFFICIENT VALID HISTORY
# =====================================================================

history_61_with_missing = build_history(
    61,
)

history_61_with_missing[30]["Close"] = None

prepared_61 = prepare_risk_history(
    history_61_with_missing
)

check(
    prepared_61["input_observations"] == 61,
    "61-row history preserves all boundary observations."
)

check(
    prepared_61["valid_close_observations"] == 60,
    "One missing Close leaves 60 valid observations."
)

check(
    prepared_61["missing_close_observations"] == 1,
    "One missing Close is reported explicitly."
)

metrics_61 = calculate_risk_metrics(
    prepared_61["closes"]
)

risk_61 = calculate_asset_risk(
    metrics_61,
    policy,
)

check(
    risk_61["status"] == STATUS_CALCULATED,
    "Missing Close does not block Risk when 60 valid observations remain."
)

check(
    risk_61["coverage"] == 1.0,
    "60 valid observations after missing-data removal retain full coverage."
)


# =====================================================================
# DUPLICATE DATE MUST BLOCK BEFORE CALCULATOR
# =====================================================================

duplicate_full_history = build_history(
    60,
)

duplicate_full_history[59][
    "market_date"
] = duplicate_full_history[58][
    "market_date"
]

check(
    raises_validation_error(
        prepare_risk_history,
        duplicate_full_history,
    ),
    "Duplicate date blocks Risk pipeline before Calculator execution."
)


# =====================================================================
# MALFORMED PRICE MUST BLOCK BEFORE CALCULATOR
# =====================================================================

malformed_full_history = build_history(
    60,
)

malformed_full_history[10]["Close"] = "100.0"

check(
    raises_validation_error(
        prepare_risk_history,
        malformed_full_history,
    ),
    "Malformed Close blocks Risk pipeline before Calculator execution."
)


# =====================================================================
# SUMMARY
# =====================================================================

print()
print("=" * 72)
print("B.2J.5C SUMMARY")
print(f"Checks: {passed + failed}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print("=" * 72)

if failed:
    print("RESULTADO: FAIL")
    raise SystemExit(1)

print("RESULTADO: PASS")