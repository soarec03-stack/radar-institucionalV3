"""
RADAR INSTITUCIONAL V3
Institutional Holdings Collector
Version: V3.4C.1 - Institutional Holdings Quality Gate

Fonte:
    SEC Form 13F Data Sets

Objetivo:
    Reconstruir o estado efetivo das holdings institucionais reportadas
    em Form 13F e calcular a variacao entre dois quarter-ends consecutivos.

Arquivos SEC utilizados:
    SUBMISSION.tsv
    COVERPAGE.tsv
    INFOTABLE.tsv

Politica de amendments:
    13F-HR original
        -> cria/substitui o estado inicial quando aplicavel

    13F-HR/A + RESTATEMENT
        -> substitui integralmente o estado anterior

    13F-HR/A + NEW HOLDINGS
        -> complementa o estado existente

Controles:
    - deduplicacao global por ACCESSION_NUMBER
    - agrupamento por CIK + PERIODOFREPORT
    - ordenacao cronologica real
    - CUSIP como identidade primaria do ativo
    - PUT/CALL excluidos
    - apenas SSHPRNAMTTYPE == SH
    - NEW HOLDINGS sem estado anterior gera diagnostico
    - comparacao somente entre gestores presentes nos dois periodos
    - nao estima dados ausentes
    - nao altera radar_v3.json

IMPORTANTE:
    AVAILABLE significa apenas que a metrica conseguiu ser calculada.
    A qualidade metodologica e avaliada por Quality Gate externo.
    O collector le os thresholds da policy V3.4C.0 e nao atribui
    confidence numerica.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import zipfile

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURACAO
# ============================================================

COLLECTOR_VERSION = "3.4C.1"

SEC_BASE_URL = "https://www.sec.gov"

SEC_DATASETS_PAGE = (
    "https://www.sec.gov/data-research/sec-markets-data/"
    "form-13f-data-sets"
)

DEFAULT_UNIVERSE = Path(
    "automation/institutional_holdings_universe_v3.json"
)

DEFAULT_OUTPUT = Path(
    "input/metrics_institutional_holdings_test_v3.json"
)

DEFAULT_CACHE_DIR = Path(
    "data/cache/sec13f"
)

DEFAULT_CORPORATE_ACTION_REGISTRY = Path(
    "automation/corporate_action_registry_v3.json"
)

DEFAULT_QUALITY_POLICY = Path(
    "automation/institutional_holdings_quality_policy_v3.json"
)

REQUEST_TIMEOUT = 180

REQUEST_DELAY_SECONDS = 0.15

ALLOWED_SUBMISSION_TYPES = {
    "13F-HR",
    "13F-HR/A",
}

AMENDMENT_RESTATEMENT = "RESTATEMENT"
AMENDMENT_NEW_HOLDINGS = "NEW HOLDINGS"


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


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value)
        .strip()
        .upper()
        .split()
    )


def normalize_cusip(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"[^A-Z0-9]",
        "",
        str(value).upper()
    )


def safe_float(value: Any) -> float | None:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        return float(text)

    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int:
    if value is None:
        return 0

    text = str(value).strip()

    if not text:
        return 0

    try:
        return int(float(text))

    except (TypeError, ValueError):
        return 0


def parse_sec_period(value: str) -> datetime:
    """
    Converte PERIODOFREPORT em datetime real.

    Exemplos:
        30-JUN-2026
        31-MAR-2026
        2026-06-30
        06/30/2026
    """

    value = str(value).strip().upper()

    for fmt in (
        "%d-%b-%Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(
                value,
                fmt
            )

        except ValueError:
            continue

    raise ValueError(
        f"PERIODOFREPORT invalido: {value}"
    )


def parse_filing_date(value: str) -> datetime:
    """
    Converte FILING_DATE em datetime.
    """

    value = str(value).strip()

    for fmt in (
        "%d-%b-%Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(
                value,
                fmt
            )

        except ValueError:
            continue

    return datetime.min


def read_json(path: Path) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


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
    ) as f:

        json.dump(
            payload,
            f,
            indent=2,
            ensure_ascii=False
        )

        f.write("\n")


# ============================================================
# SEC HTTP
# ============================================================

def get_sec_user_agent() -> str:
    value = os.getenv(
        "SEC_USER_AGENT",
        ""
    ).strip()

    if not value:
        raise RuntimeError(
            "SEC_USER_AGENT nao configurado."
        )

    return value


def build_session() -> requests.Session:
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": get_sec_user_agent(),
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }
    )

    return session


def sec_get(
    session: requests.Session,
    url: str,
    *,
    timeout: int = REQUEST_TIMEOUT,
) -> requests.Response:

    response = session.get(
        url,
        timeout=timeout
    )

    response.raise_for_status()

    time.sleep(
        REQUEST_DELAY_SECONDS
    )

    return response


# ============================================================
# DATASET DISCOVERY
# ============================================================

def discover_datasets(
    session: requests.Session
) -> list[dict[str, str]]:

    response = sec_get(
        session,
        SEC_DATASETS_PAGE
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    datasets: list[dict[str, str]] = []

    seen_urls = set()

    for anchor in soup.find_all("a"):

        href = anchor.get("href")

        if not href:
            continue

        if ".zip" not in href.lower():
            continue

        url = urljoin(
            SEC_BASE_URL,
            href
        )

        if url in seen_urls:
            continue

        seen_urls.add(url)

        label = anchor.get_text(
            " ",
            strip=True
        )

        datasets.append(
            {
                "label": label,
                "url": url,
                "filename": Path(
                    href
                ).name,
            }
        )

    if not datasets:
        raise RuntimeError(
            "Nenhum dataset SEC 13F encontrado."
        )

    return datasets


# ============================================================
# CACHE
# ============================================================

def download_dataset(
    session: requests.Session,
    dataset: dict[str, str],
    cache_dir: Path,
) -> Path:

    cache_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    target = (
        cache_dir /
        dataset["filename"]
    )

    if (
        target.exists()
        and target.stat().st_size > 0
    ):
        print(
            f"  CACHE {target.name}"
        )

        return target

    print(
        f"  DOWNLOAD {dataset['label']}"
    )

    response = sec_get(
        session,
        dataset["url"]
    )

    temp = target.with_suffix(
        target.suffix + ".part"
    )

    temp.write_bytes(
        response.content
    )

    try:

        with zipfile.ZipFile(
            temp
        ) as archive:

            bad_file = archive.testzip()

            if bad_file is not None:

                raise RuntimeError(
                    f"ZIP corrompido: "
                    f"{bad_file}"
                )

    except zipfile.BadZipFile as exc:

        temp.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            f"Arquivo SEC invalido: "
            f"{dataset['url']}"
        ) from exc

    temp.replace(
        target
    )

    print(
        f"  OK {target.name} "
        f"({target.stat().st_size:,} bytes)"
    )

    return target


# ============================================================
# UNIVERSE
# ============================================================

def load_universe(
    path: Path
) -> dict[str, dict[str, Any]]:

    payload = read_json(
        path
    )

    assets = payload.get(
        "assets",
        {}
    )

    if not isinstance(
        assets,
        dict
    ):
        raise RuntimeError(
            "Campo assets invalido no universe."
        )

    enabled = {}

    for ticker, config in assets.items():

        if not isinstance(
            config,
            dict
        ):
            continue

        if not config.get(
            "enabled",
            True
        ):
            continue

        enabled[
            ticker.upper()
        ] = config

    if not enabled:
        raise RuntimeError(
            "Nenhum ativo habilitado."
        )

    return enabled


# ============================================================
# SUBMISSION.tsv
# ============================================================

def read_submissions(
    zip_path: Path
) -> dict[str, dict[str, str]]:

    submissions = {}

    with zipfile.ZipFile(
        zip_path
    ) as archive:

        with archive.open(
            "SUBMISSION.tsv"
        ) as raw:

            text = io.TextIOWrapper(
                raw,
                encoding="utf-8-sig",
                newline=""
            )

            reader = csv.DictReader(
                text,
                delimiter="\t"
            )

            for row in reader:

                accession = (
                    row.get(
                        "ACCESSION_NUMBER",
                        ""
                    ).strip()
                )

                submission_type = (
                    row.get(
                        "SUBMISSIONTYPE",
                        ""
                    ).strip()
                    .upper()
                )

                period = (
                    row.get(
                        "PERIODOFREPORT",
                        ""
                    ).strip()
                )

                cik = (
                    row.get(
                        "CIK",
                        ""
                    ).strip()
                )

                if not accession:
                    continue

                if (
                    submission_type
                    not in ALLOWED_SUBMISSION_TYPES
                ):
                    continue

                if not period:
                    continue

                if not cik:
                    continue

                submissions[
                    accession
                ] = {
                    "accession_number":
                        accession,

                    "filing_date":
                        row.get(
                            "FILING_DATE",
                            ""
                        ).strip(),

                    "submission_type":
                        submission_type,

                    "cik":
                        cik,

                    "period_of_report":
                        period,
                }

    return submissions


# ============================================================
# COVERPAGE.tsv
# ============================================================

def is_true(value: Any) -> bool:
    return normalize_text(
        value
    ) in {
        "Y",
        "YES",
        "TRUE",
        "1",
    }


def read_coverpages(
    zip_path: Path
) -> dict[str, dict[str, Any]]:

    coverpages = {}

    with zipfile.ZipFile(
        zip_path
    ) as archive:

        with archive.open(
            "COVERPAGE.tsv"
        ) as raw:

            text = io.TextIOWrapper(
                raw,
                encoding="utf-8-sig",
                newline=""
            )

            reader = csv.DictReader(
                text,
                delimiter="\t"
            )

            for row in reader:

                accession = (
                    row.get(
                        "ACCESSION_NUMBER",
                        ""
                    ).strip()
                )

                if not accession:
                    continue

                is_amendment = is_true(
                    row.get(
                        "ISAMENDMENT"
                    )
                )

                amendment_type = (
                    normalize_text(
                        row.get(
                            "AMENDMENTTYPE"
                        )
                    )
                )

                amendment_no = safe_int(
                    row.get(
                        "AMENDMENTNO"
                    )
                )

                coverpages[
                    accession
                ] = {
                    "accession_number":
                        accession,

                    "report_calendar_or_quarter":
                        row.get(
                            "REPORTCALENDARORQUARTER",
                            ""
                        ).strip(),

                    "is_amendment":
                        is_amendment,

                    "amendment_no":
                        amendment_no,

                    "amendment_type":
                        amendment_type,

                    "filing_manager_name":
                        row.get(
                            "FILINGMANAGER_NAME",
                            ""
                        ).strip(),

                    "report_type":
                        row.get(
                            "REPORTTYPE",
                            ""
                        ).strip(),

                    "form13f_file_number":
                        row.get(
                            "FORM13FFILENUMBER",
                            ""
                        ).strip(),
                }

    return coverpages


# ============================================================
# ASSET MATCHING
# ============================================================

def build_cusip_map(
    universe: dict[str, dict[str, Any]]
) -> dict[str, str]:

    result = {}

    for ticker, config in universe.items():

        cusip = normalize_cusip(
            config.get(
                "cusip"
            )
        )

        if cusip:
            result[
                cusip
            ] = ticker

    return result


def match_asset(
    row: dict[str, str],
    cusip_map: dict[str, str],
) -> str | None:

    row_cusip = normalize_cusip(
        row.get(
            "CUSIP"
        )
    )

    if not row_cusip:
        return None

    return cusip_map.get(
        row_cusip
    )


# ============================================================
# INFOTABLE.tsv
# ============================================================

def is_equity_position(
    row: dict[str, str]
) -> bool:

    put_call = normalize_text(
        row.get(
            "PUTCALL"
        )
    )

    if put_call in {
        "PUT",
        "CALL",
    }:
        return False

    amount_type = normalize_text(
        row.get(
            "SSHPRNAMTTYPE"
        )
    )

    if amount_type != "SH":
        return False

    return True


def make_position_key(
    row: dict[str, Any]
) -> tuple[str, ...]:
    """
    Chave conservadora de uma linha da Information Table.

    NEW HOLDINGS complementa o filing anterior. A chave abaixo
    permite preservar linhas economicamente distintas sem reduzir
    tudo apenas ao CUSIP.

    SSHPRNAMT e VALUE nao fazem parte da chave porque sao valores
    quantitativos da posicao.
    """

    return (
        normalize_text(
            row.get(
                "issuer"
            )
        ),
        normalize_text(
            row.get(
                "title_of_class"
            )
        ),
        normalize_cusip(
            row.get(
                "cusip"
            )
        ),
        normalize_text(
            row.get(
                "figi"
            )
        ),
        normalize_text(
            row.get(
                "investment_discretion"
            )
        ),
        normalize_text(
            row.get(
                "other_manager"
            )
        ),
    )


def read_information_table(
    zip_path: Path,
    submissions: dict[
        str,
        dict[str, str]
    ],
    cusip_map: dict[str, str],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    int
]:

    rows_by_accession = defaultdict(
        list
    )

    matched_count = 0

    with zipfile.ZipFile(
        zip_path
    ) as archive:

        with archive.open(
            "INFOTABLE.tsv"
        ) as raw:

            text = io.TextIOWrapper(
                raw,
                encoding="utf-8-sig",
                newline=""
            )

            reader = csv.DictReader(
                text,
                delimiter="\t"
            )

            for row in reader:

                accession = (
                    row.get(
                        "ACCESSION_NUMBER",
                        ""
                    ).strip()
                )

                if accession not in submissions:
                    continue

                if not is_equity_position(
                    row
                ):
                    continue

                ticker = match_asset(
                    row,
                    cusip_map
                )

                if ticker is None:
                    continue

                shares = safe_float(
                    row.get(
                        "SSHPRNAMT"
                    )
                )

                if shares is None:
                    continue

                normalized_row = {
                    "ticker":
                        ticker,

                    "issuer":
                        row.get(
                            "NAMEOFISSUER",
                            ""
                        ).strip(),

                    "title_of_class":
                        row.get(
                            "TITLEOFCLASS",
                            ""
                        ).strip(),

                    "cusip":
                        normalize_cusip(
                            row.get(
                                "CUSIP"
                            )
                        ),

                    "figi":
                        row.get(
                            "FIGI",
                            ""
                        ).strip(),

                    "shares":
                        shares,

                    "value":
                        safe_float(
                            row.get(
                                "VALUE"
                            )
                        ),

                    "investment_discretion":
                        row.get(
                            "INVESTMENTDISCRETION",
                            ""
                        ).strip(),

                    "other_manager":
                        row.get(
                            "OTHERMANAGER",
                            ""
                        ).strip(),

                    "voting_auth_sole":
                        safe_float(
                            row.get(
                                "VOTING_AUTH_SOLE"
                            )
                        ),

                    "voting_auth_shared":
                        safe_float(
                            row.get(
                                "VOTING_AUTH_SHARED"
                            )
                        ),

                    "voting_auth_none":
                        safe_float(
                            row.get(
                                "VOTING_AUTH_NONE"
                            )
                        ),
                }

                rows_by_accession[
                    accession
                ].append(
                    normalized_row
                )

                matched_count += 1

    return (
        dict(
            rows_by_accession
        ),
        matched_count,
    )


# ============================================================
# FILING BUILD
# ============================================================

def build_filings(
    submissions: dict[str, dict[str, str]],
    coverpages: dict[str, dict[str, Any]],
    rows_by_accession: dict[
        str,
        list[dict[str, Any]]
    ],
) -> dict[str, dict[str, Any]]:

    filings = {}

    for accession, submission in submissions.items():

        cover = coverpages.get(
            accession,
            {}
        )

        rows = rows_by_accession.get(
            accession,
            []
        )

        is_amendment = bool(
            cover.get(
                "is_amendment",
                False
            )
        )

        amendment_type = normalize_text(
            cover.get(
                "amendment_type"
            )
        )

        if (
            submission[
                "submission_type"
            ] == "13F-HR/A"
        ):
            is_amendment = True

        filings[
            accession
        ] = {
            "accession_number":
                accession,

            "cik":
                submission[
                    "cik"
                ],

            "period_of_report":
                submission[
                    "period_of_report"
                ],

            "filing_date":
                submission[
                    "filing_date"
                ],

            "submission_type":
                submission[
                    "submission_type"
                ],

            "is_amendment":
                is_amendment,

            "amendment_no":
                safe_int(
                    cover.get(
                        "amendment_no"
                    )
                ),

            "amendment_type":
                amendment_type,

            "report_calendar_or_quarter":
                cover.get(
                    "report_calendar_or_quarter",
                    ""
                ),

            "filing_manager_name":
                cover.get(
                    "filing_manager_name",
                    ""
                ),

            "rows":
                rows,
        }

    return filings


# ============================================================
# ACCESSION DEDUPLICATION
# ============================================================

def merge_filings_across_datasets(
    global_filings: dict[
        str,
        dict[str, Any]
    ],
    incoming_filings: dict[
        str,
        dict[str, Any]
    ],
    audit: dict[str, int],
) -> None:

    for accession, filing in incoming_filings.items():

        if accession in global_filings:

            audit[
                "duplicate_accessions_removed"
            ] += 1

            # Mantemos a versao que possui mais linhas do universo.
            existing_rows = len(
                global_filings[
                    accession
                ].get(
                    "rows",
                    []
                )
            )

            incoming_rows = len(
                filing.get(
                    "rows",
                    []
                )
            )

            if incoming_rows > existing_rows:

                global_filings[
                    accession
                ] = filing

            continue

        global_filings[
            accession
        ] = filing


# ============================================================
# AMENDMENT STATE MACHINE
# ============================================================

def filing_sort_key(
    filing: dict[str, Any]
) -> tuple[Any, ...]:
    """
    Ordem de aplicacao dentro de CIK + PERIODOFREPORT.

    1. filing date
    2. original antes de amendment na mesma data
    3. amendment number
    4. accession
    """

    return (
        parse_filing_date(
            filing.get(
                "filing_date",
                ""
            )
        ),
        1 if filing.get(
            "is_amendment"
        ) else 0,
        safe_int(
            filing.get(
                "amendment_no"
            )
        ),
        filing.get(
            "accession_number",
            ""
        ),
    )


def copy_rows(
    rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:

    return [
        dict(row)
        for row in rows
    ]


def economic_position_signature(
    row: dict[str, Any]
) -> tuple[Any, ...]:
    """
    Assinatura economica usada somente para avaliar colisao de
    NEW HOLDINGS.

    Voting authority nao altera SSHPRNAMT e, portanto, nao cria
    uma nova quantidade economica para a metrica de holdings.
    """
    return (
        normalize_text(row.get("ticker")),
        normalize_text(row.get("issuer")),
        normalize_text(row.get("title_of_class")),
        normalize_cusip(row.get("cusip")),
        normalize_text(row.get("figi")),
        safe_float(row.get("shares")),
        safe_float(row.get("value")),
        normalize_text(row.get("investment_discretion")),
        normalize_text(row.get("other_manager")),
    )


def merge_new_holdings(
    current_rows: list[dict[str, Any]],
    amendment_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Aplica NEW HOLDINGS de forma conservadora.

    - chave inexistente: append;
    - chave existente + assinatura economica equivalente:
      nao duplica;
    - chave existente + assinatura economica diferente:
      nao adivinha append/replace, preserva o estado anterior e
      marca colisao ambigua para tornar o estado incompleto.
    """
    result = copy_rows(current_rows)

    existing_by_key = defaultdict(list)
    for row in result:
        existing_by_key[make_position_key(row)].append(row)

    audit = {
        "position_key_collisions": 0,
        "equivalent_collisions": 0,
        "ambiguous_collisions": 0,
        "new_rows_appended": 0,
    }

    for amendment_row in amendment_rows:
        key = make_position_key(amendment_row)
        existing_rows = existing_by_key.get(key, [])

        if not existing_rows:
            new_row = dict(amendment_row)
            result.append(new_row)
            existing_by_key[key].append(new_row)
            audit["new_rows_appended"] += 1
            continue

        audit["position_key_collisions"] += 1

        amendment_signature = economic_position_signature(amendment_row)

        if any(
            economic_position_signature(existing) == amendment_signature
            for existing in existing_rows
        ):
            audit["equivalent_collisions"] += 1
            # Nao soma novamente SSHPRNAMT. A linha existente
            # permanece como estado economico efetivo.
            continue

        audit["ambiguous_collisions"] += 1
        # Deliberadamente nao fazemos append nem replace.
        # O chamador marcara o estado como incompleto.

    return result, audit


def append_new_holdings(
    current_rows: list[dict[str, Any]],
    amendment_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Interface mantida por compatibilidade.

    Usa a politica V3.4A.5 e retorna somente as linhas reconstruidas.
    """
    result, _ = merge_new_holdings(
        current_rows,
        amendment_rows,
    )
    return result


def count_position_key_collisions(
    current_rows: list[dict[str, Any]],
    amendment_rows: list[dict[str, Any]],
) -> int:
    existing_keys = {
        make_position_key(row)
        for row in current_rows
    }

    return sum(
        1
        for row in amendment_rows
        if make_position_key(row) in existing_keys
    )

def reconstruct_manager_states(
    filings: dict[
        str,
        dict[str, Any]
    ]
) -> tuple[
    dict[
        tuple[str, str],
        dict[str, Any]
    ],
    dict[str, Any]
]:

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

    audit = {
        "manager_period_groups":
            len(grouped),

        "manager_period_states":
            0,

        "complete_states":
            0,

        "incomplete_states":
            0,

        "original_filings_applied":
            0,

        "restatements_applied":
            0,

        "new_holdings_applied":
            0,

        "orphan_new_holdings":
            0,

        "orphan_restatements":
            0,

        "unknown_amendment_types":
            0,

        "position_key_collisions":
            0,

        "equivalent_position_collisions":
            0,

        "ambiguous_position_collisions":
            0,

        "new_holding_rows_appended":
            0,

        "empty_filings":
            0,
    }

    states = {}

    for key, group_filings in grouped.items():

        ordered = sorted(
            group_filings,
            key=filing_sort_key
        )

        state_rows: list[
            dict[str, Any]
        ] = []

        state_exists = False
        state_complete = True

        applied_accessions = []

        event_log = []

        for filing in ordered:

            accession = filing[
                "accession_number"
            ]

            rows = filing.get(
                "rows",
                []
            )

            submission_type = filing.get(
                "submission_type",
                ""
            )

            is_amendment = bool(
                filing.get(
                    "is_amendment"
                )
            )

            amendment_type = normalize_text(
                filing.get(
                    "amendment_type"
                )
            )

            if not rows:
                audit[
                    "empty_filings"
                ] += 1

            # ------------------------------------------------
            # ORIGINAL
            # ------------------------------------------------

            if (
                submission_type == "13F-HR"
                and not is_amendment
            ):

                state_rows = copy_rows(
                    rows
                )

                state_exists = True
                state_complete = True

                audit[
                    "original_filings_applied"
                ] += 1

                applied_accessions.append(
                    accession
                )

                event_log.append(
                    {
                        "accession_number":
                            accession,

                        "event":
                            "ORIGINAL",

                        "filing_date":
                            filing[
                                "filing_date"
                            ],

                        "rows":
                            len(rows),
                    }
                )

                continue

            # ------------------------------------------------
            # RESTATEMENT
            # ------------------------------------------------

            if (
                is_amendment
                and amendment_type
                == AMENDMENT_RESTATEMENT
            ):

                if not state_exists:

                    audit[
                        "orphan_restatements"
                    ] += 1

                # RESTATEMENT e um filing completo de substituicao.
                # Mesmo sem o original na janela carregada, restaura
                # um estado reconstruivel e completo.
                state_rows = copy_rows(
                    rows
                )

                state_exists = True
                state_complete = True

                audit[
                    "restatements_applied"
                ] += 1

                applied_accessions.append(
                    accession
                )

                event_log.append(
                    {
                        "accession_number":
                            accession,

                        "event":
                            "RESTATEMENT",

                        "filing_date":
                            filing[
                                "filing_date"
                            ],

                        "amendment_no":
                            filing[
                                "amendment_no"
                            ],

                        "rows":
                            len(rows),
                    }
                )

                continue

            # ------------------------------------------------
            # NEW HOLDINGS
            # ------------------------------------------------

            if (
                is_amendment
                and amendment_type
                == AMENDMENT_NEW_HOLDINGS
            ):

                if not state_exists:

                    audit[
                        "orphan_new_holdings"
                    ] += 1

                    state_complete = False

                    # Guardamos as linhas para auditoria, mas
                    # o estado sera marcado como incompleto.
                    state_rows = copy_rows(
                        rows
                    )

                    state_exists = True

                    applied_accessions.append(
                        accession
                    )

                    event_log.append(
                        {
                            "accession_number":
                                accession,

                            "event":
                                "ORPHAN_NEW_HOLDINGS",

                            "filing_date":
                                filing[
                                    "filing_date"
                                ],

                            "amendment_no":
                                filing[
                                    "amendment_no"
                                ],

                            "rows":
                                len(rows),
                        }
                    )

                    continue

                (
                    state_rows,
                    merge_result,
                ) = merge_new_holdings(
                    state_rows,
                    rows
                )

                collisions = merge_result[
                    "position_key_collisions"
                ]

                equivalent_collisions = merge_result[
                    "equivalent_collisions"
                ]

                ambiguous_collisions = merge_result[
                    "ambiguous_collisions"
                ]

                audit[
                    "position_key_collisions"
                ] += collisions

                audit[
                    "equivalent_position_collisions"
                ] += equivalent_collisions

                audit[
                    "ambiguous_position_collisions"
                ] += ambiguous_collisions

                audit[
                    "new_holding_rows_appended"
                ] += merge_result[
                    "new_rows_appended"
                ]

                if ambiguous_collisions > 0:
                    state_complete = False

                audit[
                    "new_holdings_applied"
                ] += 1

                applied_accessions.append(
                    accession
                )

                event_log.append(
                    {
                        "accession_number":
                            accession,

                        "event":
                            "NEW_HOLDINGS",

                        "filing_date":
                            filing[
                                "filing_date"
                            ],

                        "amendment_no":
                            filing[
                                "amendment_no"
                            ],

                        "rows":
                            len(rows),

                        "position_key_collisions":
                            collisions,

                        "equivalent_position_collisions":
                            equivalent_collisions,

                        "ambiguous_position_collisions":
                            ambiguous_collisions,

                        "new_rows_appended":
                            merge_result[
                                "new_rows_appended"
                            ],
                    }
                )

                continue

            # ------------------------------------------------
            # AMENDMENT DESCONHECIDO
            # ------------------------------------------------

            if is_amendment:

                audit[
                    "unknown_amendment_types"
                ] += 1

                state_complete = False

                event_log.append(
                    {
                        "accession_number":
                            accession,

                        "event":
                            "UNKNOWN_AMENDMENT_TYPE",

                        "amendment_type":
                            amendment_type,

                        "filing_date":
                            filing[
                                "filing_date"
                            ],
                    }
                )

                continue

            # ------------------------------------------------
            # FALLBACK
            # ------------------------------------------------

            if submission_type == "13F-HR":

                state_rows = copy_rows(
                    rows
                )

                state_exists = True
                state_complete = True

                audit[
                    "original_filings_applied"
                ] += 1

                applied_accessions.append(
                    accession
                )

                event_log.append(
                    {
                        "accession_number":
                            accession,

                        "event":
                            "ORIGINAL_FALLBACK",

                        "filing_date":
                            filing[
                                "filing_date"
                            ],

                        "rows":
                            len(rows),
                    }
                )

        if not state_exists:
            continue

        audit[
            "manager_period_states"
        ] += 1

        if state_complete:

            audit[
                "complete_states"
            ] += 1

        else:

            audit[
                "incomplete_states"
            ] += 1

        states[
            key
        ] = {
            "cik":
                key[0],

            "period_of_report":
                key[1],

            "rows":
                state_rows,

            "complete":
                state_complete,

            "applied_accessions":
                applied_accessions,

            "events":
                event_log,
        }

    return (
        states,
        audit,
    )


# ============================================================
# CONVERTE ESTADOS EM POSICOES POR ATIVO
# ============================================================

def build_asset_manager_positions(
    states: dict[
        tuple[str, str],
        dict[str, Any]
    ]
) -> tuple[
    dict[
        str,
        dict[
            str,
            dict[
                str,
                dict[str, Any]
            ]
        ]
    ],
    dict[str, int]
]:

    result = defaultdict(
        lambda: defaultdict(dict)
    )

    diagnostics = {
        "states_with_asset_positions":
            0,

        "incomplete_states_with_asset_positions":
            0,

        "incomplete_states_excluded_from_analysis":
            0,
    }

    for (
        cik,
        period
    ), state in states.items():

        by_ticker = defaultdict(
            lambda: {
                "shares": 0.0,
                "rows": 0,
                "cusips": set(),
                "accessions": set(
                    state[
                        "applied_accessions"
                    ]
                ),
            }
        )

        for row in state[
            "rows"
        ]:

            ticker = row[
                "ticker"
            ]

            bucket = by_ticker[
                ticker
            ]

            bucket[
                "shares"
            ] += row[
                "shares"
            ]

            bucket[
                "rows"
            ] += 1

            if row.get(
                "cusip"
            ):
                bucket[
                    "cusips"
                ].add(
                    row[
                        "cusip"
                    ]
                )

        if by_ticker:

            diagnostics[
                "states_with_asset_positions"
            ] += 1

            if not state[
                "complete"
            ]:

                diagnostics[
                    "incomplete_states_with_asset_positions"
                ] += 1

        if by_ticker and not state[
            "complete"
        ]:
            diagnostics[
                "incomplete_states_excluded_from_analysis"
            ] += 1
            continue

        for ticker, bucket in by_ticker.items():

            result[
                ticker
            ][
                period
            ][
                cik
            ] = {
                "shares":
                    bucket[
                        "shares"
                    ],

                "rows":
                    bucket[
                        "rows"
                    ],

                "cusips":
                    sorted(
                        bucket[
                            "cusips"
                        ]
                    ),

                "accessions":
                    sorted(
                        bucket[
                            "accessions"
                        ]
                    ),

                "state_complete":
                    state[
                        "complete"
                    ],
            }

    return (
        result,
        diagnostics,
    )


# ============================================================
# CORPORATE ACTION GUARD V3.4B.1 INTEGRATION
# ============================================================

CA_SHARE_TYPES = {"STOCK_SPLIT", "REVERSE_STOCK_SPLIT"}

def load_corporate_action_registry(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload.get("assets"), dict) or not payload["assets"]:
        raise RuntimeError("Corporate Action Registry sem assets.")
    return payload

def get_corporate_action_for_window(
    registry: dict[str, Any],
    ticker: str,
    previous_period: str,
    current_period: str,
) -> dict[str, Any]:
    result = {
        "status": "NOT_CHECKED",
        "action_type": "UNKNOWN",
        "verified": False,
        "guard_passed": False,
        "adjustment_authorized": False,
        "adjustment_factor": None,
        "adjustment_required": False,
        "effective_date": None,
        "evidence_count": 0,
        "diagnostics": [],
    }
    window = registry.get("comparison_window", {})
    if (
        window.get("previous_period") != previous_period
        or window.get("current_period") != current_period
    ):
        result["status"] = "UNRESOLVED"
        result["diagnostics"].append("CORPORATE_ACTION_WINDOW_MISMATCH")
        return result

    entry = registry.get("assets", {}).get(ticker)
    if not isinstance(entry, dict):
        result["diagnostics"].append("CORPORATE_ACTION_REGISTRY_ENTRY_MISSING")
        return result

    status = entry.get("status")
    action_type = entry.get("action_type")
    result.update({
        "status": status,
        "action_type": action_type,
        "verified": bool(entry.get("verified", False)),
        "adjustment_required": bool(entry.get("adjustment_required", False)),
        "effective_date": entry.get("effective_date"),
        "evidence_count": len(entry.get("evidence", [])),
    })

    if status == "NO_ACTION":
        valid = (
            action_type == "NONE"
            and entry.get("verified") is True
            and entry.get("window_review_completed") is True
            and entry.get("identity_continuity_review") is True
            and bool(entry.get("evidence"))
            and entry.get("adjustment_required") is False
        )
        if not valid:
            result["status"] = "UNRESOLVED"
            result["diagnostics"].append("CORPORATE_ACTION_NO_ACTION_EVIDENCE_INVALID")
            return result
        result.update(
            guard_passed=True,
            adjustment_authorized=True,
            adjustment_factor=1.0,
        )
        return result

    if status == "VERIFIED_ACTION":
        n = safe_float(entry.get("ratio_numerator"))
        d = safe_float(entry.get("ratio_denominator"))
        valid = (
            action_type in CA_SHARE_TYPES
            and entry.get("verified") is True
            and bool(entry.get("effective_date"))
            and bool(entry.get("evidence"))
            and n is not None and n > 0
            and d is not None and d > 0
        )
        if not valid:
            result["status"] = "UNRESOLVED"
            result["diagnostics"].append("CORPORATE_ACTION_VERIFIED_ACTION_INVALID")
            return result
        result.update(
            guard_passed=True,
            adjustment_authorized=True,
            adjustment_factor=n / d,
        )
        return result

    if status == "UNRESOLVED":
        result["diagnostics"].append("CORPORATE_ACTION_UNRESOLVED")
    else:
        result["diagnostics"].append("CORPORATE_ACTION_SOURCE_REVIEW_REQUIRED")
    return result


# ============================================================
# INSTITUTIONAL HOLDINGS QUALITY GATE V3.4C.1
# ============================================================

QUALITY_STATUSES = {
    "VERIFIED",
    "PARTIAL",
    "INSUFFICIENT_COVERAGE",
    "BLOCKED",
}


def load_quality_policy(path: Path) -> dict[str, Any]:
    payload = read_json(path)

    if payload.get("policy_name") != "INSTITUTIONAL_HOLDINGS_QUALITY_GATE":
        raise RuntimeError("Quality Policy invalida: policy_name.")

    thresholds = payload.get("thresholds")
    blocking = payload.get("blocking_controls")

    if not isinstance(thresholds, dict):
        raise RuntimeError("Quality Policy sem thresholds.")

    if not isinstance(blocking, dict):
        raise RuntimeError("Quality Policy sem blocking_controls.")

    minimum_managers = safe_int(
        thresholds.get("minimum_comparable_managers")
    )

    coverage = thresholds.get("manager_coverage", {})
    verified_minimum = safe_float(coverage.get("verified_minimum"))
    partial_minimum = safe_float(coverage.get("partial_minimum"))

    if minimum_managers < 1:
        raise RuntimeError(
            "Quality Policy: minimum_comparable_managers deve ser >= 1."
        )

    if (
        verified_minimum is None
        or partial_minimum is None
        or not 0.0 <= partial_minimum <= 1.0
        or not 0.0 <= verified_minimum <= 1.0
        or partial_minimum >= verified_minimum
    ):
        raise RuntimeError("Quality Policy: thresholds de coverage invalidos.")

    return payload


def _quality_check(
    name: str,
    required: bool,
    passed: bool,
    observed: Any,
    expected: Any,
) -> dict[str, Any]:
    return {
        "control": name,
        "required": bool(required),
        "passed": bool(passed) if required else True,
        "observed": observed,
        "expected": expected,
    }


def evaluate_institutional_holdings_quality(
    result: dict[str, Any],
    config: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """
    Avalia qualidade sem recalcular a metrica.

    Ordem:
      1. blocking controls
      2. minimum comparable managers
      3. manager coverage
      4. quality status
      5. analytically usable

    Thresholds quantitativos sao lidos exclusivamente da policy.
    """
    thresholds = policy["thresholds"]
    blocking = policy["blocking_controls"]

    minimum_managers = safe_int(
        thresholds["minimum_comparable_managers"]
    )
    coverage_policy = thresholds["manager_coverage"]
    verified_minimum = float(coverage_policy["verified_minimum"])
    partial_minimum = float(coverage_policy["partial_minimum"])

    provenance = result.get("provenance") or {}
    corporate_action = result.get("corporate_action") or {}

    current_period = result.get("current_period")
    previous_period = result.get("previous_period")
    comparable_managers = safe_int(result.get("comparable_managers"))
    previous_shares = safe_float(result.get("raw_previous_shares"))
    adjusted_metric = safe_float(result.get("adjusted_holdings_change_pct"))
    manager_coverage = safe_float(result.get("manager_coverage"))
    incomplete_comparable = safe_int(
        result.get("incomplete_comparable_managers")
    )

    checks = [
        _quality_check(
            "CUSIP",
            blocking.get("require_cusip") is True,
            bool(normalize_cusip(config.get("cusip"))),
            normalize_cusip(config.get("cusip")) or None,
            "NON_EMPTY_VALID_NORMALIZED_CUSIP",
        ),
        _quality_check(
            "TWO_PERIODS",
            blocking.get("require_two_periods") is True,
            bool(current_period and previous_period and current_period != previous_period),
            {
                "previous_period": previous_period,
                "current_period": current_period,
            },
            "TWO_DISTINCT_PERIODS",
        ),
        _quality_check(
            "COMPARABLE_MANAGERS",
            blocking.get("require_comparable_managers") is True,
            comparable_managers > 0,
            comparable_managers,
            "> 0",
        ),
        _quality_check(
            "POSITIVE_PREVIOUS_SHARES",
            blocking.get("require_positive_previous_shares") is True,
            previous_shares is not None and previous_shares > 0,
            previous_shares,
            "> 0",
        ),
        _quality_check(
            "ZERO_INCOMPLETE_COMPARABLE_STATES",
            blocking.get("require_zero_incomplete_comparable_states") is True,
            incomplete_comparable == 0,
            incomplete_comparable,
            0,
        ),
        _quality_check(
            "CORPORATE_ACTION_GUARD",
            blocking.get("require_corporate_action_guard_pass") is True,
            corporate_action.get("guard_passed") is True,
            {
                "status": corporate_action.get("status"),
                "guard_passed": corporate_action.get("guard_passed"),
            },
            "PASS",
        ),
        _quality_check(
            "ADJUSTED_METRIC",
            blocking.get("require_adjusted_metric") is True,
            adjusted_metric is not None,
            adjusted_metric,
            "NOT_NULL",
        ),
        _quality_check(
            "SEC_TIER_1_PROVENANCE",
            blocking.get("require_sec_tier_1_provenance") is True,
            (
                provenance.get("source") == "SEC"
                and provenance.get("source_type") == "FORM_13F_DATA_SET"
                and provenance.get("tier") == policy["metric"]["required_source_tier"]
            ),
            {
                "source": provenance.get("source"),
                "source_type": provenance.get("source_type"),
                "tier": provenance.get("tier"),
            },
            {
                "source": policy["metric"]["source"],
                "source_type": policy["metric"]["source_type"],
                "tier": policy["metric"]["required_source_tier"],
            },
        ),
        _quality_check(
            "DATA_STATUS_AVAILABLE",
            blocking.get("require_data_status_available") is True,
            result.get("data_status") == "AVAILABLE",
            result.get("data_status"),
            "AVAILABLE",
        ),
    ]

    failed_blocking_controls = [
        check["control"]
        for check in checks
        if check["required"] and not check["passed"]
    ]

    if failed_blocking_controls:
        quality_status = "BLOCKED"
        analytically_usable = False
        reason = "BLOCKING_CONTROL_FAILED"
    elif comparable_managers < minimum_managers:
        quality_status = "INSUFFICIENT_COVERAGE"
        analytically_usable = False
        reason = "MINIMUM_COMPARABLE_MANAGERS_NOT_MET"
    elif manager_coverage is None or manager_coverage < partial_minimum:
        quality_status = "INSUFFICIENT_COVERAGE"
        analytically_usable = False
        reason = "MANAGER_COVERAGE_BELOW_PARTIAL_MINIMUM"
    elif manager_coverage < verified_minimum:
        quality_status = "PARTIAL"
        analytically_usable = True
        reason = "MANAGER_COVERAGE_PARTIAL"
    else:
        quality_status = "VERIFIED"
        analytically_usable = True
        reason = "QUALITY_GATE_VERIFIED"

    if quality_status not in QUALITY_STATUSES:
        raise RuntimeError(f"Quality status invalido: {quality_status}")

    return {
        "policy_version": policy.get("policy_version"),
        "status": quality_status,
        "analytically_usable": analytically_usable,
        "reason": reason,
        "blocking_controls_passed": not failed_blocking_controls,
        "failed_blocking_controls": failed_blocking_controls,
        "minimum_comparable_managers": minimum_managers,
        "comparable_managers": comparable_managers,
        "manager_coverage": manager_coverage,
        "manager_coverage_thresholds": {
            "verified_minimum": verified_minimum,
            "partial_minimum": partial_minimum,
        },
        "checks": checks,
    }


def apply_quality_gate(
    result: dict[str, Any],
    config: dict[str, Any],
    policy: dict[str, Any],
) -> None:
    quality_gate = evaluate_institutional_holdings_quality(
        result,
        config,
        policy,
    )

    result["quality_gate"] = quality_gate
    result["quality_status"] = quality_gate["status"]
    result["analytically_usable"] = quality_gate["analytically_usable"]

    if quality_gate["status"] == "BLOCKED":
        result["diagnostics"].append("INSTITUTIONAL_HOLDINGS_QUALITY_GATE_BLOCKED")
    elif quality_gate["status"] == "INSUFFICIENT_COVERAGE":
        result["diagnostics"].append(
            "INSTITUTIONAL_HOLDINGS_INSUFFICIENT_COVERAGE"
        )
    elif quality_gate["status"] == "PARTIAL":
        result["diagnostics"].append("INSTITUTIONAL_HOLDINGS_PARTIAL_QUALITY")


# ============================================================
# ASSET RESULT
# ============================================================

def build_asset_result(
    ticker: str,
    config: dict[str, Any],
    corporate_action_registry: dict[str, Any],
    quality_policy: dict[str, Any],
    asset_periods: dict[
        str,
        dict[
            str,
            dict[str, Any]
        ]
    ],
) -> dict[str, Any]:

    periods = sorted(
        asset_periods.keys(),
        key=parse_sec_period,
        reverse=True
    )

    result = {
        "ticker":
            ticker,

        "issuer_name":
            config.get(
                "issuer_name"
            ),

        "cusip":
            config.get(
                "cusip"
            ),

        "metric":
            "institutional_holdings_change_pct",

        "value":
            None,

        "data_status":
            "UNAVAILABLE",

        "quality_status":
            "NOT_HOMOLOGATED",

        "analytically_usable":
            False,

        # Compatibilidade temporaria com a saida anterior.
        "status":
            "UNAVAILABLE",

        "current_period":
            None,

        "previous_period":
            None,

        "current_shares":
            None,

        "previous_shares":
            None,

        "raw_current_shares":
            None,

        "raw_previous_shares":
            None,

        "raw_holdings_change_pct":
            None,

        "adjusted_current_shares":
            None,

        "adjusted_previous_shares":
            None,

        "adjusted_holdings_change_pct":
            None,

        "corporate_action_adjustment_factor":
            None,

        "corporate_action":
            None,

        "current_total_shares":
            None,

        "previous_total_shares":
            None,

        "current_managers":
            0,

        "previous_managers":
            0,

        "comparable_managers":
            0,

        "manager_coverage":
            None,

        "incomplete_current_managers":
            0,

        "incomplete_previous_managers":
            0,

        "incomplete_comparable_managers":
            0,

        "calculation_scope":
            "COMPARABLE_MANAGERS",

        "provenance": {
            "source":
                "SEC",

            "source_type":
                "FORM_13F_DATA_SET",

            "tier":
                "TIER_1",

            "status":
                "UNAVAILABLE",

            "retrieved_at":
                utc_now_iso(),
        },

        "diagnostics":
            [],
    }

    if not normalize_cusip(
        config.get(
            "cusip"
        )
    ):

        result[
            "diagnostics"
        ].append(
            "CUSIP_NOT_CONFIGURED"
        )

        return result

    if len(periods) < 2:

        result[
            "diagnostics"
        ].append(
            "INSUFFICIENT_PERIODS"
        )

        return result

    current_period = periods[0]
    previous_period = periods[1]

    current_map = asset_periods[
        current_period
    ]

    previous_map = asset_periods[
        previous_period
    ]

    current_manager_ids = set(
        current_map.keys()
    )

    previous_manager_ids = set(
        previous_map.keys()
    )

    comparable_ids = (
        current_manager_ids
        &
        previous_manager_ids
    )

    current_count = len(
        current_manager_ids
    )

    previous_count = len(
        previous_manager_ids
    )

    comparable_count = len(
        comparable_ids
    )

    denominator_managers = max(
        current_count,
        previous_count
    )

    manager_coverage = (
        comparable_count
        /
        denominator_managers

        if denominator_managers
        else None
    )

    current_total_shares = sum(
        item[
            "shares"
        ]
        for item
        in current_map.values()
    )

    previous_total_shares = sum(
        item[
            "shares"
        ]
        for item
        in previous_map.values()
    )

    comparable_current_shares = sum(
        current_map[
            cik
        ][
            "shares"
        ]
        for cik
        in comparable_ids
    )

    comparable_previous_shares = sum(
        previous_map[
            cik
        ][
            "shares"
        ]
        for cik
        in comparable_ids
    )

    incomplete_current = sum(
        1
        for item
        in current_map.values()
        if not item[
            "state_complete"
        ]
    )

    incomplete_previous = sum(
        1
        for item
        in previous_map.values()
        if not item[
            "state_complete"
        ]
    )

    incomplete_comparable = sum(
        1
        for cik
        in comparable_ids
        if (
            not current_map[
                cik
            ][
                "state_complete"
            ]
            or
            not previous_map[
                cik
            ][
                "state_complete"
            ]
        )
    )

    result.update(
        {
            "current_period":
                current_period,

            "previous_period":
                previous_period,

            "current_shares":
                round(
                    comparable_current_shares,
                    6
                ),

            "previous_shares":
                round(
                    comparable_previous_shares,
                    6
                ),

            "raw_current_shares":
                round(comparable_current_shares, 6),

            "raw_previous_shares":
                round(comparable_previous_shares, 6),

            "current_total_shares":
                round(
                    current_total_shares,
                    6
                ),

            "previous_total_shares":
                round(
                    previous_total_shares,
                    6
                ),

            "current_managers":
                current_count,

            "previous_managers":
                previous_count,

            "comparable_managers":
                comparable_count,

            "manager_coverage":
                (
                    round(
                        manager_coverage,
                        6
                    )
                    if manager_coverage
                    is not None
                    else None
                ),

            "incomplete_current_managers":
                incomplete_current,

            "incomplete_previous_managers":
                incomplete_previous,

            "incomplete_comparable_managers":
                incomplete_comparable,
        }
    )

    if comparable_count == 0:

        result[
            "diagnostics"
        ].append(
            "NO_COMPARABLE_MANAGERS"
        )

        return result

    if (
        comparable_previous_shares
        <= 0
    ):

        result[
            "diagnostics"
        ].append(
            "INVALID_PREVIOUS_SHARES"
        )

        return result

    raw_change_pct = (
        (comparable_current_shares - comparable_previous_shares)
        / comparable_previous_shares
        * 100.0
    )
    result["raw_holdings_change_pct"] = round(raw_change_pct, 6)

    corporate_action = get_corporate_action_for_window(
        corporate_action_registry,
        ticker,
        previous_period,
        current_period,
    )
    result["corporate_action"] = corporate_action
    factor = corporate_action.get("adjustment_factor")
    result["corporate_action_adjustment_factor"] = factor

    if corporate_action.get("guard_passed") and factor is not None:
        adjusted_previous = comparable_previous_shares * factor
        adjusted_current = comparable_current_shares

        if adjusted_previous <= 0:
            result["diagnostics"].append("INVALID_ADJUSTED_PREVIOUS_SHARES")
            return result

        adjusted_change_pct = (
            (adjusted_current - adjusted_previous)
            / adjusted_previous
            * 100.0
        )
        result["adjusted_previous_shares"] = round(adjusted_previous, 6)
        result["adjusted_current_shares"] = round(adjusted_current, 6)
        result["adjusted_holdings_change_pct"] = round(adjusted_change_pct, 6)

        # value passa a ser a metrica ajustada. Raw permanece preservado.
        result["value"] = round(adjusted_change_pct, 6)
        result["data_status"] = "AVAILABLE"
        result["status"] = "AVAILABLE"
        result["provenance"]["status"] = "VERIFIED"
    else:
        result["value"] = None
        result["data_status"] = "UNAVAILABLE"
        result["status"] = "UNAVAILABLE"
        result["diagnostics"].append(
            "CORPORATE_ACTION_GUARD_BLOCKED_ADJUSTED_METRIC"
        )

    result["provenance"]["market_date"] = current_period
    result["provenance"]["previous_market_date"] = previous_period
    result["provenance"]["cusip"] = normalize_cusip(config.get("cusip"))

    if incomplete_current > 0:

        result[
            "diagnostics"
        ].append(
            "INCOMPLETE_CURRENT_MANAGER_STATES"
        )

    if incomplete_previous > 0:

        result[
            "diagnostics"
        ].append(
            "INCOMPLETE_PREVIOUS_MANAGER_STATES"
        )

    if incomplete_comparable > 0:

        result[
            "diagnostics"
        ].append(
            "INCOMPLETE_COMPARABLE_MANAGER_STATES"
        )

    apply_quality_gate(
        result,
        config,
        quality_policy,
    )

    return result


# ============================================================
# BASELINE V3.4A.2
# ============================================================

BASELINE_V342 = {
    "VRT": {
        "value": -1.998824,
        "manager_coverage": 0.828140,
    },
    "CRSP": {
        "value": -2.436211,
        "manager_coverage": 0.838710,
    },
    "ETON": {
        "value": 6.712343,
        "manager_coverage": 0.658683,
    },
}


def build_baseline_comparison(
    asset_results: dict[
        str,
        dict[str, Any]
    ]
) -> dict[str, Any]:

    comparison = {}

    for ticker, current in asset_results.items():

        baseline = BASELINE_V342.get(
            ticker
        )

        if baseline is None:
            continue

        new_value = current.get(
            "value"
        )

        old_value = baseline.get(
            "value"
        )

        new_coverage = current.get(
            "manager_coverage"
        )

        old_coverage = baseline.get(
            "manager_coverage"
        )

        value_delta = None

        if (
            new_value is not None
            and old_value is not None
        ):
            value_delta = round(
                new_value - old_value,
                6
            )

        coverage_delta = None

        if (
            new_coverage is not None
            and old_coverage is not None
        ):
            coverage_delta = round(
                new_coverage
                - old_coverage,
                6
            )

        comparison[
            ticker
        ] = {
            "baseline_version":
                "3.4A.2",

            "new_version":
                COLLECTOR_VERSION,

            "baseline_value":
                old_value,

            "new_value":
                new_value,

            "value_delta":
                value_delta,

            "baseline_manager_coverage":
                old_coverage,

            "new_manager_coverage":
                new_coverage,

            "manager_coverage_delta":
                coverage_delta,
        }

    return comparison


# ============================================================
# MAIN COLLECTION
# ============================================================

def collect(
    universe_path: Path,
    output_path: Path,
    cache_dir: Path,
    dataset_count: int,
    corporate_action_registry_path: Path,
    quality_policy_path: Path,
) -> dict[str, Any]:

    universe = load_universe(
        universe_path
    )

    cusip_map = build_cusip_map(
        universe
    )

    corporate_action_registry = load_corporate_action_registry(
        corporate_action_registry_path
    )

    quality_policy = load_quality_policy(
        quality_policy_path
    )

    session = build_session()

    print(
        "Descobrindo datasets SEC 13F..."
    )

    datasets = discover_datasets(
        session
    )

    print(
        f"Datasets encontrados: "
        f"{len(datasets)}"
    )

    selected_datasets = datasets[
        :dataset_count
    ]

    global_filings: dict[
        str,
        dict[str, Any]
    ] = {}

    dataset_metadata = []

    merge_audit = {
        "duplicate_accessions_removed": 0
    }

    raw_coverpage_audit = {
        "coverpages": 0,
        "amendments": 0,
        "restatements": 0,
        "new_holdings": 0,
        "other_amendments": 0,
    }

    for dataset in selected_datasets:

        print()

        print(
            f"Dataset: "
            f"{dataset['label']}"
        )

        zip_path = download_dataset(
            session,
            dataset,
            cache_dir
        )

        submissions = read_submissions(
            zip_path
        )

        coverpages = read_coverpages(
            zip_path
        )

        print(
            f"  submissions elegiveis: "
            f"{len(submissions):,}"
        )

        dataset_amendments = 0
        dataset_restatements = 0
        dataset_new_holdings = 0

        for cover in coverpages.values():

            raw_coverpage_audit[
                "coverpages"
            ] += 1

            if not cover[
                "is_amendment"
            ]:
                continue

            raw_coverpage_audit[
                "amendments"
            ] += 1

            dataset_amendments += 1

            amendment_type = normalize_text(
                cover.get(
                    "amendment_type"
                )
            )

            if (
                amendment_type
                == AMENDMENT_RESTATEMENT
            ):

                raw_coverpage_audit[
                    "restatements"
                ] += 1

                dataset_restatements += 1

            elif (
                amendment_type
                == AMENDMENT_NEW_HOLDINGS
            ):

                raw_coverpage_audit[
                    "new_holdings"
                ] += 1

                dataset_new_holdings += 1

            else:

                raw_coverpage_audit[
                    "other_amendments"
                ] += 1

        (
            rows_by_accession,
            matched_positions,
        ) = read_information_table(
            zip_path,
            submissions,
            cusip_map,
        )

        print(
            f"  posicoes do universo: "
            f"{matched_positions:,}"
        )

        print(
            f"  amendments: "
            f"{dataset_amendments:,} "
            f"(RESTATEMENT="
            f"{dataset_restatements:,}, "
            f"NEW HOLDINGS="
            f"{dataset_new_holdings:,})"
        )

        filings = build_filings(
            submissions,
            coverpages,
            rows_by_accession,
        )

        merge_filings_across_datasets(
            global_filings,
            filings,
            merge_audit,
        )

        observed_periods = set()

        for filing in filings.values():

            if filing[
                "rows"
            ]:

                observed_periods.add(
                    filing[
                        "period_of_report"
                    ]
                )

        periods_sorted = sorted(
            observed_periods,
            key=parse_sec_period,
            reverse=True
        )

        dataset_metadata.append(
            {
                "label":
                    dataset[
                        "label"
                    ],

                "url":
                    dataset[
                        "url"
                    ],

                "filename":
                    dataset[
                        "filename"
                    ],

                "periods_observed":
                    periods_sorted,

                "matched_positions":
                    matched_positions,

                "eligible_submissions":
                    len(
                        submissions
                    ),

                "amendments":
                    dataset_amendments,

                "restatements":
                    dataset_restatements,

                "new_holdings":
                    dataset_new_holdings,
            }
        )

    print()

    print(
        "Reconstruindo estados "
        "CIK + PERIODOFREPORT..."
    )

    (
        manager_states,
        state_machine_audit,
    ) = reconstruct_manager_states(
        global_filings
    )

    print(
        f"  filings unicos: "
        f"{len(global_filings):,}"
    )

    print(
        f"  estados gestor/periodo: "
        f"{state_machine_audit['manager_period_states']:,}"
    )

    print(
        f"  originals aplicados: "
        f"{state_machine_audit['original_filings_applied']:,}"
    )

    print(
        f"  restatements aplicados: "
        f"{state_machine_audit['restatements_applied']:,}"
    )

    print(
        f"  new holdings aplicados: "
        f"{state_machine_audit['new_holdings_applied']:,}"
    )

    print(
        f"  estados incompletos: "
        f"{state_machine_audit['incomplete_states']:,}"
    )

    print(
        f"  orphan NEW HOLDINGS: "
        f"{state_machine_audit['orphan_new_holdings']:,}"
    )

    (
        asset_manager_positions,
        position_state_audit,
    ) = build_asset_manager_positions(
        manager_states
    )

    asset_results = {}

    for ticker, config in universe.items():

        asset_results[
            ticker
        ] = build_asset_result(
            ticker,
            config,
            corporate_action_registry,
            quality_policy,
            asset_manager_positions.get(
                ticker,
                {}
            ),
        )

    baseline_comparison = (
        build_baseline_comparison(
            asset_results
        )
    )

    amendment_audit = {
        **raw_coverpage_audit,

        "unique_filings":
            len(global_filings),

        "duplicate_accessions_removed":
            merge_audit[
                "duplicate_accessions_removed"
            ],

        **state_machine_audit,

        **position_state_audit,
    }

    payload = {
        "schema_version":
            "3.0",

        "collector":
            "INSTITUTIONAL_HOLDINGS_SEC_13F",

        "collector_version":
            COLLECTOR_VERSION,

        "generated_at":
            utc_now_iso(),

        "source":
            "SEC",

        "source_tier":
            "TIER_1",

        "methodology": {
            "metric":
                "institutional_holdings_change_pct",

            "period_basis":
                "PERIODOFREPORT",

            "period_sort":
                "CHRONOLOGICAL",

            "position_type":
                "SHARES_ONLY",

            "put_call_excluded":
                True,

            "comparison_scope":
                "COMPARABLE_MANAGERS",

            "missing_data_policy":
                "NULL_DO_NOT_ESTIMATE",

            "identity_policy":
                "VERIFIED_CUSIP_ONLY",

            "amendment_policy":
                "STATE_MACHINE_V3_4A_5_PLUS_CORPORATE_ACTION_GUARD_V3_4B_1",

            "original_policy":
                "INITIAL_STATE",

            "restatement_policy":
                "REPLACE_STATE",

            "new_holdings_policy":
                "CONSERVATIVE_MERGE_EQUIVALENT_DEDUP_AMBIGUOUS_INCOMPLETE",

            "orphan_new_holdings_policy":
                "KEEP_FOR_AUDIT_MARK_STATE_INCOMPLETE_EXCLUDE_ANALYSIS",

            "incomplete_state_policy":
                "EXCLUDE_FROM_ANALYTICAL_MANAGER_UNIVERSE",

            "restatement_completeness_policy":
                "FULL_REPLACEMENT_RESTORES_COMPLETE",

            "corporate_action_policy":
                "FAIL_CLOSED_EVIDENCE_REGISTRY",

            "corporate_action_registry":
                str(corporate_action_registry_path),

            "raw_metric_preserved":
                True,

            "published_metric_basis":
                "ADJUSTED_HOLDINGS_CHANGE_PCT",

            "quality_gate_policy":
                str(quality_policy_path),

            "quality_gate_policy_version":
                quality_policy.get("policy_version"),

            "quality_thresholds":
                quality_policy.get("thresholds"),

            "quality_gate":
                "INSTITUTIONAL_HOLDINGS_QUALITY_GATE_V3_4C_1",
        },

        "datasets":
            dataset_metadata,

        "amendment_audit":
            amendment_audit,

        "assets":
            asset_results,

        "baseline_comparison":
            baseline_comparison,
    }

    write_json(
        output_path,
        payload
    )

    return payload


# ============================================================
# CLI
# ============================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Radar Institucional V3 - "
            "SEC 13F Institutional Holdings "
            "Collector V3.4C.1"
        )
    )

    parser.add_argument(
        "--universe",
        type=Path,
        default=DEFAULT_UNIVERSE,
        help=(
            "Arquivo de configuracao "
            "do universo."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "Arquivo JSON de saida."
        ),
    )

    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=(
            "Diretorio de cache SEC."
        ),
    )

    parser.add_argument(
        "--datasets",
        type=int,
        default=2,
        help=(
            "Quantidade dos datasets SEC "
            "mais recentes a processar."
        ),
    )

    parser.add_argument(
        "--corporate-action-registry",
        type=Path,
        default=DEFAULT_CORPORATE_ACTION_REGISTRY,
        help="Evidence Registry homologado do Corporate Action Guard.",
    )

    parser.add_argument(
        "--quality-policy",
        type=Path,
        default=DEFAULT_QUALITY_POLICY,
        help="Policy homologada do Institutional Holdings Quality Gate.",
    )

    return parser.parse_args()


# ============================================================
# CONSOLE OUTPUT
# ============================================================

def print_asset_result(
    ticker: str,
    result: dict[str, Any]
) -> None:

    value = result.get(
        "value"
    )

    if value is None:
        value_text = "N/D"

    else:
        value_text = (
            f"{value:+.4f}%"
        )

    coverage = result.get(
        "manager_coverage"
    )

    print(
        f"{ticker:6} "
        f"{result['data_status']:12} "
        f"{value_text:>12} "
        f"coverage managers="
        f"{coverage}"
    )

    print(
        f"       "
        f"{result['previous_period']} "
        f"-> "
        f"{result['current_period']}"
    )

    print(
        f"       raw={result.get('raw_holdings_change_pct')}% "
        f"adjusted={result.get('adjusted_holdings_change_pct')}% "
        f"factor={result.get('corporate_action_adjustment_factor')}"
    )

    ca = result.get("corporate_action") or {}
    print(
        f"       corporate action status={ca.get('status')} "
        f"guard={'PASS' if ca.get('guard_passed') else 'BLOCK'}"
    )

    qg = result.get("quality_gate") or {}
    print(
        f"       quality={result.get('quality_status')} "
        f"analytically_usable={result.get('analytically_usable')} "
        f"reason={qg.get('reason')}"
    )

    print(
        f"       managers "
        f"current="
        f"{result['current_managers']} "
        f"previous="
        f"{result['previous_managers']} "
        f"comparable="
        f"{result['comparable_managers']}"
    )

    print(
        f"       incomplete "
        f"current="
        f"{result['incomplete_current_managers']} "
        f"previous="
        f"{result['incomplete_previous_managers']} "
        f"comparable="
        f"{result['incomplete_comparable_managers']}"
    )

    for diagnostic in result.get(
        "diagnostics",
        []
    ):

        print(
            f"       ! "
            f"{diagnostic}"
        )


def print_baseline_comparison(
    comparison: dict[str, Any]
) -> None:

    print()

    print(
        f"COMPARACAO V3.4A.2 x V{COLLECTOR_VERSION}"
    )

    print(
        "-" * 68
    )

    for ticker, item in comparison.items():

        old_value = item.get(
            "baseline_value"
        )

        new_value = item.get(
            "new_value"
        )

        delta = item.get(
            "value_delta"
        )

        old_text = (
            f"{old_value:+.6f}%"
            if old_value is not None
            else "N/D"
        )

        new_text = (
            f"{new_value:+.6f}%"
            if new_value is not None
            else "N/D"
        )

        delta_text = (
            f"{delta:+.6f} pp"
            if delta is not None
            else "N/D"
        )

        print(
            f"{ticker:6} "
            f"OLD={old_text:>12} "
            f"NEW={new_text:>12} "
            f"DELTA={delta_text:>14}"
        )


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
        "INSTITUTIONAL HOLDINGS COLLECTOR "
        "- SEC 13F"
    )

    print(
        f"VERSION {COLLECTOR_VERSION} "
        "- INSTITUTIONAL HOLDINGS QUALITY GATE"
    )

    print(
        "=" * 68
    )

    try:

        payload = collect(
            universe_path=
                args.universe,

            output_path=
                args.output,

            cache_dir=
                args.cache_dir,

            dataset_count=
                args.datasets,

            corporate_action_registry_path=
                args.corporate_action_registry,

            quality_policy_path=
                args.quality_policy,
        )

    except Exception as exc:

        print()

        print(
            f"ERRO: {exc}",
            file=sys.stderr
        )

        return 1

    print()

    print(
        "-" * 68
    )

    for ticker, result in (
        payload[
            "assets"
        ].items()
    ):

        print_asset_result(
            ticker,
            result
        )

    print_baseline_comparison(
        payload[
            "baseline_comparison"
        ]
    )

    print()

    audit = payload[
        "amendment_audit"
    ]

    print(
        "AUDITORIA AMENDMENTS"
    )

    print(
        "-" * 68
    )

    print(
        "Duplicate accessions removidos:",
        audit[
            "duplicate_accessions_removed"
        ]
    )

    print(
        "Original filings aplicados:",
        audit[
            "original_filings_applied"
        ]
    )

    print(
        "Restatements aplicados:",
        audit[
            "restatements_applied"
        ]
    )

    print(
        "New Holdings aplicados:",
        audit[
            "new_holdings_applied"
        ]
    )

    print(
        "Orphan New Holdings:",
        audit[
            "orphan_new_holdings"
        ]
    )

    print(
        "Orphan Restatements:",
        audit[
            "orphan_restatements"
        ]
    )

    print(
        "Unknown amendment types:",
        audit[
            "unknown_amendment_types"
        ]
    )

    print(
        "Position-key collisions:",
        audit[
            "position_key_collisions"
        ]
    )

    print(
        "Equivalent position collisions:",
        audit[
            "equivalent_position_collisions"
        ]
    )

    print(
        "Ambiguous position collisions:",
        audit[
            "ambiguous_position_collisions"
        ]
    )

    print(
        "Incomplete states excluded:",
        audit[
            "incomplete_states_excluded_from_analysis"
        ]
    )

    print(
        "Estados incompletos:",
        audit[
            "incomplete_states"
        ]
    )

    print()

    print(
        f"Gerado: "
        f"{args.output}"
    )

    print(
        "=" * 68
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )