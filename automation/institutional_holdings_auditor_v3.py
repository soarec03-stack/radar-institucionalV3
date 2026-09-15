"""
RADAR INSTITUCIONAL V3
Institutional Holdings Auditor
Version: V3.4A.4 - Reconstruction Integrity Audit

OBJETIVO
--------
Auditar a reconstrução SEC Form 13F realizada pelo collector V3.4A.3
sem alterar sua matemática.

Investigações principais:
1. Identificar amendment types não reconhecidos.
2. Identificar NEW HOLDINGS órfãos.
3. Identificar RESTATEMENT sem estado anterior.
4. Inspecionar colisões de position-key em NEW HOLDINGS.
5. Identificar gestores incompletos usados nos ativos.
6. Medir o impacto dos gestores incompletos no cálculo.
7. Auditar especialmente ETON, comparando gestores afetados e
   não afetados por amendments.
8. Preservar accessions e eventos para rastreabilidade.

IMPORTANTE
----------
- NÃO altera radar_v3.json.
- NÃO altera institutional_holdings_collector_v3.py.
- NÃO altera Signal Engine.
- NÃO altera Confidence Engine.
- NÃO altera Score Engine.
- NÃO homologa thresholds de qualidade.
- Saída exclusivamente de auditoria.

Saída padrão:
    data/audit/sec13f/institutional_holdings_audit_v3.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================
# CONFIGURAÇÃO
# ============================================================

AUDITOR_VERSION = "3.4A.4"

DEFAULT_COLLECTOR_OUTPUT = Path(
    "input/metrics_institutional_holdings_test_v3.json"
)

DEFAULT_OUTPUT = Path(
    "data/audit/sec13f/institutional_holdings_audit_v3.json"
)

DEFAULT_UNIVERSE = Path(
    "automation/institutional_holdings_universe_v3.json"
)

DEFAULT_CACHE_DIR = Path(
    "data/cache/sec13f"
)


# ============================================================
# UTILITIES
# ============================================================

def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def read_json(path: Path) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def write_json(
    path: Path,
    payload: dict[str, Any]
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False
        )

        file.write("\n")


def pct_change(
    current: float,
    previous: float
) -> float | None:

    if previous <= 0:
        return None

    return (
        (current - previous)
        / previous
        * 100.0
    )


def round_or_none(
    value: float | None,
    digits: int = 6
) -> float | None:

    if value is None:
        return None

    return round(
        value,
        digits
    )


# ============================================================
# CARREGA O COLLECTOR V3.4A.3
# ============================================================

def load_collector_functions():
    """
    Carrega institutional_holdings_collector_v3.py diretamente
    pelo caminho físico.

    Isso permite executar:

        python automation/institutional_holdings_auditor_v3.py

    sem exigir que automation seja um package Python e sem
    depender de __init__.py.

    Nenhuma lógica do collector é alterada.
    """

    collector_path = (
        Path(__file__).resolve().parent
        / "institutional_holdings_collector_v3.py"
    )

    if not collector_path.exists():
        raise RuntimeError(
            "Collector V3.4A.3 não encontrado em: "
            f"{collector_path}"
        )

    try:

        spec = importlib.util.spec_from_file_location(
            "institutional_holdings_collector_v3",
            collector_path,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError(
                "Não foi possível criar a especificação "
                "do módulo do collector."
            )

        collector = importlib.util.module_from_spec(
            spec
        )

        spec.loader.exec_module(
            collector
        )

    except Exception as exc:

        raise RuntimeError(
            "Não foi possível carregar "
            "institutional_holdings_collector_v3.py. "
            f"Detalhe: {exc}"
        ) from exc

    required = [
        "build_session",
        "discover_datasets",
        "download_dataset",
        "load_universe",
        "build_cusip_map",
        "read_submissions",
        "read_coverpages",
        "read_information_table",
        "build_filings",
        "merge_filings_across_datasets",
        "reconstruct_manager_states",
        "build_asset_manager_positions",
        "parse_sec_period",
        "make_position_key",
        "normalize_text",
        "AMENDMENT_RESTATEMENT",
        "AMENDMENT_NEW_HOLDINGS",
    ]

    missing = [
        name
        for name in required
        if not hasattr(
            collector,
            name
        )
    ]

    if missing:
        raise RuntimeError(
            "Collector V3.4A.3 incompatível com o auditor. "
            "Funções/constantes ausentes: "
            + ", ".join(
                missing
            )
        )

    return {
        name: getattr(
            collector,
            name
        )
        for name in required
    }


# ============================================================
# RECONSTRUÇÃO PARA AUDITORIA
# ============================================================

def rebuild_source_state(
    dataset_count: int,
    universe_path: Path,
    cache_dir: Path,
) -> dict[str, Any]:

    fn = load_collector_functions()

    universe = fn[
        "load_universe"
    ](
        universe_path
    )

    cusip_map = fn[
        "build_cusip_map"
    ](
        universe
    )

    session = fn[
        "build_session"
    ]()

    print(
        "Descobrindo datasets SEC 13F..."
    )

    datasets = fn[
        "discover_datasets"
    ](
        session
    )

    print(
        f"Datasets encontrados: {len(datasets)}"
    )

    selected = datasets[
        :dataset_count
    ]

    global_filings = {}

    merge_audit = {
        "duplicate_accessions_removed": 0
    }

    dataset_audit = []

    for dataset in selected:

        print()

        print(
            f"Auditando dataset: "
            f"{dataset['label']}"
        )

        zip_path = fn[
            "download_dataset"
        ](
            session,
            dataset,
            cache_dir
        )

        submissions = fn[
            "read_submissions"
        ](
            zip_path
        )

        coverpages = fn[
            "read_coverpages"
        ](
            zip_path
        )

        (
            rows_by_accession,
            matched_positions,
        ) = fn[
            "read_information_table"
        ](
            zip_path,
            submissions,
            cusip_map,
        )

        filings = fn[
            "build_filings"
        ](
            submissions,
            coverpages,
            rows_by_accession,
        )

        fn[
            "merge_filings_across_datasets"
        ](
            global_filings,
            filings,
            merge_audit,
        )

        print(
            f"  submissions elegíveis: "
            f"{len(submissions):,}"
        )

        print(
            f"  coverpages: "
            f"{len(coverpages):,}"
        )

        print(
            f"  posições do universo: "
            f"{matched_positions:,}"
        )

        dataset_audit.append(
            {
                "label":
                    dataset[
                        "label"
                    ],

                "filename":
                    dataset[
                        "filename"
                    ],

                "eligible_submissions":
                    len(
                        submissions
                    ),

                "coverpages":
                    len(
                        coverpages
                    ),

                "matched_positions":
                    matched_positions,

                "filings":
                    len(
                        filings
                    ),
            }
        )

    print()

    print(
        "Reconstruindo estados para auditoria..."
    )

    (
        states,
        state_machine_audit,
    ) = fn[
        "reconstruct_manager_states"
    ](
        global_filings
    )

    (
        asset_positions,
        position_state_audit,
    ) = fn[
        "build_asset_manager_positions"
    ](
        states
    )

    return {
        "functions":
            fn,

        "universe":
            universe,

        "datasets":
            dataset_audit,

        "filings":
            global_filings,

        "states":
            states,

        "asset_positions":
            asset_positions,

        "merge_audit":
            merge_audit,

        "state_machine_audit":
            state_machine_audit,

        "position_state_audit":
            position_state_audit,
    }


# ============================================================
# UNKNOWN AMENDMENTS
# ============================================================

def audit_unknown_amendments(
    filings: dict[str, dict[str, Any]],
    fn: dict[str, Any],
) -> dict[str, Any]:

    known = {
        fn[
            "AMENDMENT_RESTATEMENT"
        ],
        fn[
            "AMENDMENT_NEW_HOLDINGS"
        ],
    }

    by_type = defaultdict(
        list
    )

    for accession, filing in filings.items():

        if not filing.get(
            "is_amendment"
        ):
            continue

        amendment_type = fn[
            "normalize_text"
        ](
            filing.get(
                "amendment_type"
            )
        )

        if amendment_type in known:
            continue

        key = (
            amendment_type
            if amendment_type
            else "<EMPTY>"
        )

        by_type[
            key
        ].append(
            {
                "accession_number":
                    accession,

                "cik":
                    filing.get(
                        "cik"
                    ),

                "period_of_report":
                    filing.get(
                        "period_of_report"
                    ),

                "filing_date":
                    filing.get(
                        "filing_date"
                    ),

                "submission_type":
                    filing.get(
                        "submission_type"
                    ),

                "amendment_no":
                    filing.get(
                        "amendment_no"
                    ),

                "rows_in_universe":
                    len(
                        filing.get(
                            "rows",
                            []
                        )
                    ),
            }
        )

    return {
        "count":
            sum(
                len(items)
                for items
                in by_type.values()
            ),

        "types": {
            key: {
                "count":
                    len(items),

                "filings":
                    items,
            }
            for key, items
            in sorted(
                by_type.items()
            )
        },
    }


# ============================================================
# ORPHAN EVENTS
# ============================================================

def audit_orphan_events(
    states: dict[
        tuple[str, str],
        dict[str, Any]
    ]
) -> dict[str, Any]:

    new_holdings = []
    restatements = []

    for (
        cik,
        period
    ), state in states.items():

        events = state.get(
            "events",
            []
        )

        for event in events:

            event_type = event.get(
                "event"
            )

            if (
                event_type
                == "ORPHAN_NEW_HOLDINGS"
            ):

                new_holdings.append(
                    {
                        "cik":
                            cik,

                        "period":
                            period,

                        **event,
                    }
                )

        # RESTATEMENT pode reconstruir um estado completo
        # mesmo sem o original dentro da janela carregada.
        # Aqui apenas registramos o caso para auditoria.

        if events:

            first = events[0]

            if (
                first.get(
                    "event"
                )
                == "RESTATEMENT"
            ):

                restatements.append(
                    {
                        "cik":
                            cik,

                        "period":
                            period,

                        **first,
                    }
                )

    return {
        "orphan_new_holdings": {
            "count":
                len(
                    new_holdings
                ),

            "events":
                new_holdings,
        },

        "restatement_without_loaded_original": {
            "count":
                len(
                    restatements
                ),

            "events":
                restatements,
        },
    }


# ============================================================
# POSITION-KEY COLLISIONS
# ============================================================

def filing_audit_sort_key(
    filing: dict[str, Any]
) -> tuple[Any, ...]:

    filing_date = str(
        filing.get(
            "filing_date",
            ""
        )
    )

    is_amendment = (
        1
        if filing.get(
            "is_amendment"
        )
        else 0
    )

    amendment_no = filing.get(
        "amendment_no",
        0
    )

    try:
        amendment_no = int(
            amendment_no or 0
        )

    except (
        TypeError,
        ValueError
    ):
        amendment_no = 0

    accession = str(
        filing.get(
            "accession_number",
            ""
        )
    )

    return (
        filing_date,
        is_amendment,
        amendment_no,
        accession,
    )


def audit_position_collisions(
    filings: dict[str, dict[str, Any]],
    fn: dict[str, Any],
) -> dict[str, Any]:

    grouped = defaultdict(
        list
    )

    for filing in filings.values():

        key = (
            filing[
                "cik"
            ],
            filing[
                "period_of_report"
            ],
        )

        grouped[
            key
        ].append(
            filing
        )

    collisions = []

    for (
        cik,
        period
    ), group in grouped.items():

        ordered = sorted(
            group,
            key=filing_audit_sort_key
        )

        state_rows = []
        state_exists = False

        for filing in ordered:

            rows = filing.get(
                "rows",
                []
            )

            amendment_type = fn[
                "normalize_text"
            ](
                filing.get(
                    "amendment_type"
                )
            )

            # ORIGINAL

            if (
                filing.get(
                    "submission_type"
                ) == "13F-HR"
                and not filing.get(
                    "is_amendment"
                )
            ):

                state_rows = [
                    dict(row)
                    for row in rows
                ]

                state_exists = True

                continue

            # RESTATEMENT

            if (
                filing.get(
                    "is_amendment"
                )
                and amendment_type
                == fn[
                    "AMENDMENT_RESTATEMENT"
                ]
            ):

                state_rows = [
                    dict(row)
                    for row in rows
                ]

                state_exists = True

                continue

            # NEW HOLDINGS

            if (
                filing.get(
                    "is_amendment"
                )
                and amendment_type
                == fn[
                    "AMENDMENT_NEW_HOLDINGS"
                ]
            ):

                if not state_exists:

                    state_rows = [
                        dict(row)
                        for row in rows
                    ]

                    state_exists = True

                    continue

                existing = defaultdict(
                    list
                )

                for row in state_rows:

                    position_key = fn[
                        "make_position_key"
                    ](
                        row
                    )

                    existing[
                        position_key
                    ].append(
                        row
                    )

                for amendment_row in rows:

                    position_key = fn[
                        "make_position_key"
                    ](
                        amendment_row
                    )

                    if (
                        position_key
                        not in existing
                    ):
                        continue

                    collisions.append(
                        {
                            "cik":
                                cik,

                            "period":
                                period,

                            "accession_number":
                                filing.get(
                                    "accession_number"
                                ),

                            "filing_date":
                                filing.get(
                                    "filing_date"
                                ),

                            "amendment_no":
                                filing.get(
                                    "amendment_no"
                                ),

                            "position_key":
                                list(
                                    position_key
                                ),

                            "existing_rows":
                                existing[
                                    position_key
                                ],

                            "new_holding_row":
                                amendment_row,
                        }
                    )

                state_rows.extend(
                    [
                        dict(row)
                        for row in rows
                    ]
                )

    return {
        "count":
            len(
                collisions
            ),

        "collisions":
            collisions,
    }


# ============================================================
# ASSET PERIODS
# ============================================================

def get_latest_two_periods(
    periods: dict[str, Any],
    parse_sec_period,
) -> tuple[
    str | None,
    str | None
]:

    ordered = sorted(
        periods.keys(),
        key=parse_sec_period,
        reverse=True
    )

    if len(ordered) < 2:

        return (
            None,
            None
        )

    return (
        ordered[0],
        ordered[1],
    )


# ============================================================
# ASSET AUDIT
# ============================================================

def audit_asset(
    ticker: str,
    asset_periods: dict[
        str,
        dict[str, dict[str, Any]]
    ],
    collector_asset: dict[str, Any],
    states: dict[
        tuple[str, str],
        dict[str, Any]
    ],
    parse_sec_period,
) -> dict[str, Any]:

    (
        current_period,
        previous_period,
    ) = get_latest_two_periods(
        asset_periods,
        parse_sec_period
    )

    result = {
        "ticker":
            ticker,

        "current_period":
            current_period,

        "previous_period":
            previous_period,

        "collector_value":
            collector_asset.get(
                "value"
            ),

        "manager_coverage":
            collector_asset.get(
                "manager_coverage"
            ),

        "current_managers":
            collector_asset.get(
                "current_managers"
            ),

        "previous_managers":
            collector_asset.get(
                "previous_managers"
            ),

        "comparable_managers":
            collector_asset.get(
                "comparable_managers"
            ),

        "incomplete_comparable_managers":
            [],

        "amendment_affected_comparable_managers":
            [],

        "calculation_reproduction":
            {},

        "incomplete_manager_impact":
            {},

        "amendment_impact":
            {},
    }

    if (
        current_period is None
        or previous_period is None
    ):

        return result

    current = asset_periods[
        current_period
    ]

    previous = asset_periods[
        previous_period
    ]

    comparable = (
        set(
            current.keys()
        )
        &
        set(
            previous.keys()
        )
    )

    # --------------------------------------------------------
    # REPRODUÇÃO DO CÁLCULO DO COLLECTOR
    # --------------------------------------------------------

    current_shares = sum(
        current[
            cik
        ][
            "shares"
        ]
        for cik
        in comparable
    )

    previous_shares = sum(
        previous[
            cik
        ][
            "shares"
        ]
        for cik
        in comparable
    )

    reproduced = pct_change(
        current_shares,
        previous_shares
    )

    collector_value = collector_asset.get(
        "value"
    )

    reproduction_difference = None

    if (
        reproduced is not None
        and collector_value is not None
    ):

        reproduction_difference = round(
            reproduced
            - collector_value,
            9
        )

    result[
        "calculation_reproduction"
    ] = {
        "current_shares":
            round(
                current_shares,
                6
            ),

        "previous_shares":
            round(
                previous_shares,
                6
            ),

        "reproduced_value":
            round_or_none(
                reproduced
            ),

        "collector_value":
            collector_value,

        "difference":
            reproduction_difference,
    }

    # --------------------------------------------------------
    # GESTORES INCOMPLETOS
    # --------------------------------------------------------

    incomplete_ids = []

    for cik in sorted(
        comparable
    ):

        current_complete = current[
            cik
        ][
            "state_complete"
        ]

        previous_complete = previous[
            cik
        ][
            "state_complete"
        ]

        if (
            current_complete
            and previous_complete
        ):
            continue

        incomplete_ids.append(
            cik
        )

        result[
            "incomplete_comparable_managers"
        ].append(
            {
                "cik":
                    cik,

                "current_shares":
                    current[
                        cik
                    ][
                        "shares"
                    ],

                "previous_shares":
                    previous[
                        cik
                    ][
                        "shares"
                    ],

                "current_complete":
                    current_complete,

                "previous_complete":
                    previous_complete,

                "current_accessions":
                    current[
                        cik
                    ][
                        "accessions"
                    ],

                "previous_accessions":
                    previous[
                        cik
                    ][
                        "accessions"
                    ],
            }
        )

    complete_only = (
        comparable
        -
        set(
            incomplete_ids
        )
    )

    complete_current_shares = sum(
        current[
            cik
        ][
            "shares"
        ]
        for cik
        in complete_only
    )

    complete_previous_shares = sum(
        previous[
            cik
        ][
            "shares"
        ]
        for cik
        in complete_only
    )

    without_incomplete = pct_change(
        complete_current_shares,
        complete_previous_shares
    )

    incomplete_impact = None

    if (
        reproduced is not None
        and without_incomplete is not None
    ):

        incomplete_impact = round(
            reproduced
            - without_incomplete,
            6
        )

    result[
        "incomplete_manager_impact"
    ] = {
        "incomplete_manager_count":
            len(
                incomplete_ids
            ),

        "value_with_incomplete":
            round_or_none(
                reproduced
            ),

        "value_without_incomplete":
            round_or_none(
                without_incomplete
            ),

        "impact_pp":
            incomplete_impact,
    }

    # --------------------------------------------------------
    # GESTORES AFETADOS POR AMENDMENTS
    # --------------------------------------------------------

    amendment_ids = []

    for cik in sorted(
        comparable
    ):

        current_state = states.get(
            (
                cik,
                current_period
            )
        )

        previous_state = states.get(
            (
                cik,
                previous_period
            )
        )

        events = []

        if current_state:

            events.extend(
                [
                    {
                        "period":
                            current_period,

                        **event,
                    }
                    for event
                    in current_state.get(
                        "events",
                        []
                    )
                ]
            )

        if previous_state:

            events.extend(
                [
                    {
                        "period":
                            previous_period,

                        **event,
                    }
                    for event
                    in previous_state.get(
                        "events",
                        []
                    )
                ]
            )

        amendment_events = [
            event
            for event
            in events
            if event.get(
                "event"
            ) in {
                "RESTATEMENT",
                "NEW_HOLDINGS",
                "ORPHAN_NEW_HOLDINGS",
                "UNKNOWN_AMENDMENT_TYPE",
            }
        ]

        if not amendment_events:
            continue

        amendment_ids.append(
            cik
        )

        result[
            "amendment_affected_comparable_managers"
        ].append(
            {
                "cik":
                    cik,

                "current_shares":
                    current[
                        cik
                    ][
                        "shares"
                    ],

                "previous_shares":
                    previous[
                        cik
                    ][
                        "shares"
                    ],

                "events":
                    amendment_events,
            }
        )

    affected = set(
        amendment_ids
    )

    unaffected = (
        comparable
        -
        affected
    )

    # --------------------------------------------------------
    # SOMENTE GESTORES NÃO AFETADOS
    # --------------------------------------------------------

    unaffected_current_shares = sum(
        current[
            cik
        ][
            "shares"
        ]
        for cik
        in unaffected
    )

    unaffected_previous_shares = sum(
        previous[
            cik
        ][
            "shares"
        ]
        for cik
        in unaffected
    )

    unaffected_value = pct_change(
        unaffected_current_shares,
        unaffected_previous_shares
    )

    # --------------------------------------------------------
    # SOMENTE GESTORES AFETADOS
    # --------------------------------------------------------

    affected_current_shares = sum(
        current[
            cik
        ][
            "shares"
        ]
        for cik
        in affected
    )

    affected_previous_shares = sum(
        previous[
            cik
        ][
            "shares"
        ]
        for cik
        in affected
    )

    affected_value = pct_change(
        affected_current_shares,
        affected_previous_shares
    )

    amendment_impact = None

    if (
        reproduced is not None
        and unaffected_value is not None
    ):

        amendment_impact = round(
            reproduced
            - unaffected_value,
            6
        )

    result[
        "amendment_impact"
    ] = {
        "affected_manager_count":
            len(
                affected
            ),

        "unaffected_manager_count":
            len(
                unaffected
            ),

        "full_value":
            round_or_none(
                reproduced
            ),

        "unaffected_only_value":
            round_or_none(
                unaffected_value
            ),

        "affected_only_value":
            round_or_none(
                affected_value
            ),

        "full_minus_unaffected_pp":
            amendment_impact,

        "affected_current_shares":
            round(
                affected_current_shares,
                6
            ),

        "affected_previous_shares":
            round(
                affected_previous_shares,
                6
            ),

        "unaffected_current_shares":
            round(
                unaffected_current_shares,
                6
            ),

        "unaffected_previous_shares":
            round(
                unaffected_previous_shares,
                6
            ),
    }

    return result


# ============================================================
# SUMMARY
# ============================================================

def build_summary(
    collector_output: dict[str, Any],
    audits: dict[str, Any],
    unknown_amendments: dict[str, Any],
    orphan_events: dict[str, Any],
    collisions: dict[str, Any],
) -> dict[str, Any]:

    return {
        "collector_version":
            collector_output.get(
                "collector_version"
            ),

        "auditor_version":
            AUDITOR_VERSION,

        "unknown_amendments":
            unknown_amendments[
                "count"
            ],

        "orphan_new_holdings":
            orphan_events[
                "orphan_new_holdings"
            ][
                "count"
            ],

        "restatement_without_loaded_original":
            orphan_events[
                "restatement_without_loaded_original"
            ][
                "count"
            ],

        "position_key_collisions":
            collisions[
                "count"
            ],

        "assets": {
            ticker: {
                "value":
                    audit.get(
                        "collector_value"
                    ),

                "coverage":
                    audit.get(
                        "manager_coverage"
                    ),

                "incomplete_comparable_managers":
                    len(
                        audit.get(
                            "incomplete_comparable_managers",
                            []
                        )
                    ),

                "amendment_affected_comparable_managers":
                    len(
                        audit.get(
                            "amendment_affected_comparable_managers",
                            []
                        )
                    ),

                "incomplete_manager_impact_pp":
                    audit.get(
                        "incomplete_manager_impact",
                        {}
                    ).get(
                        "impact_pp"
                    ),

                "amendment_impact_pp":
                    audit.get(
                        "amendment_impact",
                        {}
                    ).get(
                        "full_minus_unaffected_pp"
                    ),
            }
            for ticker, audit
            in audits.items()
        },

        "homologation_status":
            "PENDING_RECONSTRUCTION_INTEGRITY_REVIEW",
    }


# ============================================================
# MAIN AUDIT
# ============================================================

def run_audit(
    collector_output_path: Path,
    universe_path: Path,
    cache_dir: Path,
    output_path: Path,
    dataset_count: int,
) -> dict[str, Any]:

    if not collector_output_path.exists():

        raise RuntimeError(
            "Saída do collector não encontrada: "
            f"{collector_output_path}"
        )

    collector_output = read_json(
        collector_output_path
    )

    source = rebuild_source_state(
        dataset_count=
            dataset_count,

        universe_path=
            universe_path,

        cache_dir=
            cache_dir,
    )

    fn = source[
        "functions"
    ]

    unknown_amendments = (
        audit_unknown_amendments(
            source[
                "filings"
            ],
            fn,
        )
    )

    orphan_events = (
        audit_orphan_events(
            source[
                "states"
            ]
        )
    )

    collisions = (
        audit_position_collisions(
            source[
                "filings"
            ],
            fn,
        )
    )

    asset_audits = {}

    for ticker, collector_asset in (
        collector_output.get(
            "assets",
            {}
        ).items()
    ):

        asset_audits[
            ticker
        ] = audit_asset(
            ticker=
                ticker,

            asset_periods=
                source[
                    "asset_positions"
                ].get(
                    ticker,
                    {}
                ),

            collector_asset=
                collector_asset,

            states=
                source[
                    "states"
                ],

            parse_sec_period=
                fn[
                    "parse_sec_period"
                ],
        )

    summary = build_summary(
        collector_output,
        asset_audits,
        unknown_amendments,
        orphan_events,
        collisions,
    )

    payload = {
        "schema_version":
            "3.0",

        "audit":
            "INSTITUTIONAL_HOLDINGS_SEC_13F_RECONSTRUCTION",

        "auditor_version":
            AUDITOR_VERSION,

        "generated_at":
            utc_now_iso(),

        "source":
            "SEC",

        "source_tier":
            "TIER_1",

        "purpose":
            "AUDIT_ONLY_DO_NOT_FEED_SIGNAL_OR_SCORE",

        "collector_input":
            str(
                collector_output_path
            ),

        "datasets":
            source[
                "datasets"
            ],

        "collector_amendment_audit":
            collector_output.get(
                "amendment_audit",
                {}
            ),

        "reconstruction_audit": {
            "merge":
                source[
                    "merge_audit"
                ],

            "state_machine":
                source[
                    "state_machine_audit"
                ],

            "position_states":
                source[
                    "position_state_audit"
                ],
        },

        "unknown_amendments":
            unknown_amendments,

        "orphan_events":
            orphan_events,

        "position_key_collisions":
            collisions,

        "assets":
            asset_audits,

        "summary":
            summary,
    }

    write_json(
        output_path,
        payload
    )

    return payload


# ============================================================
# CONSOLE
# ============================================================

def print_asset_summary(
    ticker: str,
    audit: dict[str, Any]
) -> None:

    print()

    print(
        ticker
    )

    print(
        "-" * 68
    )

    print(
        "Valor collector:",
        audit.get(
            "collector_value"
        )
    )

    print(
        "Coverage:",
        audit.get(
            "manager_coverage"
        )
    )

    reproduction = audit.get(
        "calculation_reproduction",
        {}
    )

    print(
        "Valor reproduzido:",
        reproduction.get(
            "reproduced_value"
        )
    )

    print(
        "Diferença reprodução:",
        reproduction.get(
            "difference"
        )
    )

    incomplete = audit.get(
        "incomplete_manager_impact",
        {}
    )

    print(
        "Gestores incompletos comparáveis:",
        incomplete.get(
            "incomplete_manager_count"
        )
    )

    print(
        "Impacto gestores incompletos:",
        incomplete.get(
            "impact_pp"
        ),
        "pp"
    )

    amendment = audit.get(
        "amendment_impact",
        {}
    )

    print(
        "Gestores comparáveis afetados "
        "por amendments:",
        amendment.get(
            "affected_manager_count"
        )
    )

    print(
        "Valor sem gestores afetados:",
        amendment.get(
            "unaffected_only_value"
        )
    )

    print(
        "Valor apenas gestores afetados:",
        amendment.get(
            "affected_only_value"
        )
    )

    print(
        "Impacto amendments:",
        amendment.get(
            "full_minus_unaffected_pp"
        ),
        "pp"
    )


# ============================================================
# CLI
# ============================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Radar Institucional V3 - "
            "Institutional Holdings Auditor V3.4A.4"
        )
    )

    parser.add_argument(
        "--collector-output",
        type=Path,
        default=DEFAULT_COLLECTOR_OUTPUT,
    )

    parser.add_argument(
        "--universe",
        type=Path,
        default=DEFAULT_UNIVERSE,
    )

    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    parser.add_argument(
        "--datasets",
        type=int,
        default=2,
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    args = parse_args()

    if args.datasets < 1:

        print(
            "ERRO: --datasets deve ser >= 1",
            file=sys.stderr
        )

        return 2

    print(
        "=" * 68
    )

    print(
        "RADAR INSTITUCIONAL V3"
    )

    print(
        "INSTITUTIONAL HOLDINGS AUDITOR"
    )

    print(
        f"VERSION {AUDITOR_VERSION} "
        "- RECONSTRUCTION INTEGRITY"
    )

    print(
        "=" * 68
    )

    try:

        payload = run_audit(
            collector_output_path=
                args.collector_output,

            universe_path=
                args.universe,

            cache_dir=
                args.cache_dir,

            output_path=
                args.output,

            dataset_count=
                args.datasets,
        )

    except Exception as exc:

        print()

        print(
            f"ERRO: {exc}",
            file=sys.stderr
        )

        return 1

    for ticker, audit in (
        payload[
            "assets"
        ].items()
    ):

        print_asset_summary(
            ticker,
            audit
        )

    print()

    print(
        "=" * 68
    )

    print(
        "INTEGRITY SUMMARY"
    )

    print(
        "=" * 68
    )

    summary = payload[
        "summary"
    ]

    print(
        "Unknown amendments:",
        summary[
            "unknown_amendments"
        ]
    )

    print(
        "Orphan NEW HOLDINGS:",
        summary[
            "orphan_new_holdings"
        ]
    )

    print(
        "RESTATEMENT sem original carregado:",
        summary[
            "restatement_without_loaded_original"
        ]
    )

    print(
        "Position-key collisions:",
        summary[
            "position_key_collisions"
        ]
    )

    print()

    print(
        "Homologação:",
        summary[
            "homologation_status"
        ]
    )

    print()

    print(
        "Gerado:",
        args.output
    )

    print(
        "=" * 68
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )