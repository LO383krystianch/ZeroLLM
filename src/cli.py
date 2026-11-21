"""CLI punktu wejścia projektu ODWOŁANIA2JSON.

Użycie:
    run.bat --input dokument.pdf --output wynik.json
    python -m src.cli --input dokument.pdf --output wynik.json

Przetwarza pojedynczy dokument (PDF lub TXT) i zapisuje czysty wynik JSON
(zgodny ze schematem UZP — bez warstwy transparentności), identyczny jak
wynik przetwarzania wsadowego (``start.bat``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from . import extractor
except ImportError:  # uruchomienie jako skrypt: python src/cli.py
    import extractor


def read_text(path: Path) -> str:
    """Wyodrębnia tekst z PDF (pypdf + OCR) lub z pliku tekstowego."""
    if path.suffix.lower() == ".pdf":
        return extractor.extract_text_from_pdf(path)
    return path.read_text(encoding="utf-8", errors="replace")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ekstrakcja danych z dokumentów (odwołań, pełnomocnictw, przelewów) do JSON."
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
        "--rules",
        default=str(extractor.DEFAULT_RULES),
        help="Plik reguł YAML (domyślnie config/document_rules.yaml).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Błąd: plik wejściowy nie istnieje: {input_path}", file=sys.stderr)
        return 1

    ex = extractor.load_extractor(Path(args.rules))
    text = read_text(input_path)
    document_type = ex.detect(text, input_path.name)

    # Dokument nierozpoznany (obcy) -> pusty JSON {} (wymóg jury).
    result = ex.extract_clean(text, document_type) if document_type is not None else {}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Zapisano wynik do: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
