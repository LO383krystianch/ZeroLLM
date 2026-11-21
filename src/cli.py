"""CLI punktu wejścia projektu ODWOŁANIA2JSON.

Użycie:
    py -3.13 src/cli.py --input dokument.pdf --output wynik.json
    python -m src.cli --input dokument.pdf --output wynik.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_SCHEMA = CONFIG_DIR / "schemas.yaml"


def load_schemas(path: Path | None = None) -> dict[str, Any]:
    """Wczytuje konfigurację schematów dokumentów z pliku YAML."""
    path = path or DEFAULT_SCHEMA
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def extract_text(path: Path) -> str:
    """Wyodrębnia tekst z pliku PDF (przez pypdf) lub z pliku tekstowego."""
    if path.suffix.lower() == ".pdf":
        if PdfReader is None:
            raise RuntimeError("Brak biblioteki pypdf. Zainstaluj zależności z requirements.txt.")
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="replace")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ekstrakcja danych z dokumentów (odwołań) do JSON."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Ścieżka do pliku wejściowego (PDF lub TXT).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Ścieżka do pliku wyjściowego JSON.",
    )
    parser.add_argument(
        "--schemas",
        default=str(DEFAULT_SCHEMA),
        help="Ścieżka do pliku schematów YAML (domyślnie config/schemas.yaml).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Błąd: plik wejściowy nie istnieje: {input_path}", file=sys.stderr)
        return 1

    schemas = load_schemas(Path(args.schemas))
    text = extract_text(input_path)

    result = {
        "document_type": schemas.get("default_document_type"),
        "source": str(input_path),
        "extracted_text_length": len(text),
        "text_preview": text[:500],
        "transparency": {
            "rule": "skeleton",
            "source_fragment": text[:200],
        },
        "schemas": schemas,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Zapisano wynik do: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
