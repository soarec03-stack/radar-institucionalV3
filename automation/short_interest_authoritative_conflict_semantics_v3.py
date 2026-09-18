from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


VERSION = "3.4D.2-B.2C.8D.2"

BASE_DIR = Path(__file__).resolve().parent.parent

POLICY_FILE = (
    BASE_DIR
    / "automation"
    / "short_interest_authoritative_conflict_semantics_policy_v3.json"
)


class ConflictSemanticsError(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConflictSemanticsError(
            f"Arquivo não encontrado: {path}"
        )

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConflictSemanticsError(
            f"JSON inválido em {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ConflictSemanticsError(
            "Root JSON deve ser objeto."
        )

    return data


def validate_policy(
    policy: dict[str, Any],
) -> None:
    if not isinstance(policy, dict):
        raise ConflictSemanticsError(
            "Policy deve ser objeto."
        )

    if policy.get("policy_version") != VERSION:
        raise ConflictSemanticsError(
            "policy_version incompatível."
        )

    expected_statuses = {
        "VERIFIED_NO_CONFLICT",
        "CONFLICT_DETECTED",
        "NOT_ESTABLISHED",
    }

    statuses = policy.get("statuses")

    if (
        not isinstance(statuses, list)
        or set(statuses) != expected_statuses
    ):
        raise ConflictSemanticsError(
            "Statuses da policy inválidos."
        )


def classify_authoritative_conflict(
    review: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """
    Deriva semântica tri-state sem modificar
    o contrato upstream homologado.
    """

    validate_policy(policy)

    if not isinstance(review, dict):
        raise ConflictSemanticsError(
            "Review deve ser objeto."
        )

    diagnostics = review.get(
        "diagnostics"
    )

    if not isinstance(diagnostics, list):
        raise ConflictSemanticsError(
            "Review diagnostics deve ser lista."
        )

    if not all(
        isinstance(item, str)
        for item in diagnostics
    ):
        raise ConflictSemanticsError(
            "Review diagnostics contém "
            "valor inválido."
        )

    raw_flag = review.get(
        "no_authoritative_evidence_conflict"
    )

    if not isinstance(raw_flag, bool):
        raise ConflictSemanticsError(
            "no_authoritative_evidence_conflict "
            "deve ser boolean."
        )

    explicit_conflict = (
        "AUTHORITATIVE_EVIDENCE_CONFLICT"
        in diagnostics
    )

    if explicit_conflict:
        status = "CONFLICT_DETECTED"
        reason = (
            "EXPLICIT_UPSTREAM_CONFLICT_DIAGNOSTIC"
        )

    elif raw_flag is True:
        status = "VERIFIED_NO_CONFLICT"
        reason = (
            "UPSTREAM_NO_CONFLICT_EXPLICITLY_TRUE"
        )

    else:
        status = "NOT_ESTABLISHED"
        reason = (
            "NO_EXPLICIT_CONFLICT_AND_NO_VERIFIED_"
            "NO_CONFLICT"
        )

    return {
        "semantic_version": VERSION,
        "status": status,
        "reason": reason,
        "raw_no_authoritative_evidence_conflict":
            raw_flag,
        "explicit_conflict_diagnostic":
            explicit_conflict,
        "upstream_diagnostics":
            deepcopy(diagnostics),
        "reconciliation_allowed_by_semantics":
            (
                False
                if status
                in {
                    "CONFLICT_DETECTED",
                    "NOT_ESTABLISHED",
                }
                else None
            ),
    }


def main() -> int:
    input_file = (
        BASE_DIR
        / "input"
        / "short_interest_real_positive_official_review_v3.json"
    )

    try:
        policy = read_json(
            POLICY_FILE
        )

        data = read_json(
            input_file
        )

        assets = data.get("assets")

        if not isinstance(assets, list):
            raise ConflictSemanticsError(
                "Input real sem assets válidos."
            )

        print("=" * 72)
        print("RADAR INSTITUCIONAL V3")
        print("SHORT INTEREST")
        print("AUTHORITATIVE CONFLICT SEMANTICS")
        print(f"VERSION {VERSION}")
        print("=" * 72)

        for asset in assets:
            if not isinstance(asset, dict):
                raise ConflictSemanticsError(
                    "Asset inválido."
                )

            ticker = asset.get("ticker")
            review = asset.get(
                "review_result"
            )

            result = (
                classify_authoritative_conflict(
                    review,
                    policy,
                )
            )

            print("-" * 72)
            print("Ticker:", ticker)
            print(
                "Status:",
                result["status"],
            )
            print(
                "Reason:",
                result["reason"],
            )
            print(
                "Raw flag:",
                result[
                    "raw_no_authoritative_evidence_conflict"
                ],
            )
            print(
                "Explicit conflict:",
                result[
                    "explicit_conflict_diagnostic"
                ],
            )
            print(
                "Diagnostics:",
                result[
                    "upstream_diagnostics"
                ],
            )

        return 0

    except Exception as exc:
        print(
            f"ERRO: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())