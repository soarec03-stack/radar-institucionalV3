import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = BASE_DIR / "automation" / "source_registry_v3.json"


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REGISTRY

    if not path.exists():
        print(f"ERRO: registry não encontrado: {path}")
        return 2

    original = path.read_text(encoding="utf-8")
    data = json.loads(original)

    backup = path.with_suffix(path.suffix + ".before_yahoo_finance")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    sources = data.get("sources")

    source_entry = {
        "name": "Yahoo Finance via yfinance",
        "tier": "TIER_3",
        "base_confidence": 0.70,
        "categories": ["MARKET", "TECHNICAL"],
        "verification_capable": False,
        "publication_use": "RESEARCH_ONLY",
        "notes": (
            "Fonte de desenvolvimento para histórico de preço/volume. "
            "Não tratar como fonte institucional final do Radar V3."
        )
    }

    if isinstance(sources, dict):
        sources["YAHOO_FINANCE"] = source_entry
    elif isinstance(sources, list):
        # Evita duplicata se o registry usar array.
        sources[:] = [
            x for x in sources
            if not (
                isinstance(x, dict)
                and (
                    x.get("id") == "YAHOO_FINANCE"
                    or x.get("name") == source_entry["name"]
                )
            )
        ]
        entry = {"id": "YAHOO_FINANCE", **source_entry}
        sources.append(entry)
    else:
        print("ERRO: formato de source_registry_v3.json não reconhecido.")
        return 2

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("OK YAHOO_FINANCE adicionado ao Source Registry como TIER_3 / RESEARCH_ONLY.")
    print(f"Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
