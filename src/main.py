"""Przetwarzanie wsadowe plików PDF z ./input/ do ./output/.

Użycie:
    start.bat
    python src/main.py [--input ./input] [--output ./output]

Dla każdego pliku PDF w ./input/ (rekurencyjnie, z podfolderami) generowany
jest wynikowy plik JSON w ./output/ z zachowaniem struktury katalogów,
np. input/case1/doc.pdf -> output/case1/doc.json.

Ekstrakcja oparta o src/extractor.py (wzorzec Registry): typ dokumentu i pola
pochodzą wyłącznie z config/document_rules.yaml.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from . import extractor
except ImportError:  # uruchomienie jako skrypt: python src/main.py
    import extractor

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
DEFAULT_RULES = ROOT / "config" / "document_rules.yaml"


def find_pdfs(input_dir: Path) -> list[Path]:
    """Rekurencyjnie wyszukuje pliki PDF w podanym katalogu."""
    if not input_dir.exists():
        return []
    return sorted(p for p in input_dir.rglob("*.pdf") if p.is_file())


# Mapowanie nazw plików wejściowych na nazwy wyjściowe (zgodne z UZP).
OUTPUT_NAME_MAP = {
    "potwierdzenie_przelewu": "przelew",
}


def output_name(relative: Path) -> Path:
    """Zwraca ścieżkę wyjściową JSON (z uwzględnieniem mapowania nazw UZP)."""
    stem = relative.stem
    mapped = OUTPUT_NAME_MAP.get(stem, stem)
    return relative.with_name(mapped + ".json")


def build_result(
    relative: Path,
    text: str,
    ex: extractor.DocumentExtractor,
) -> dict[str, Any]:
    """Buduje czysty wynik JSON zgodny ze schematem UZP (bez warstwy debugowania).

    Dokument nierozpoznany (obcy — niepasujący do żadnego z 3 typów) daje
    pusty obiekt ``{}`` (wymóg jury), zapisywany pod nazwą oryginalnego pliku.
    """
    document_type = ex.detect(text, relative.name)
    if document_type is None:
        return {}
    return ex.extract_clean(text, document_type)


def process(
    input_dir: Path,
    output_dir: Path,
    ex: extractor.DocumentExtractor,
) -> list[Path]:
    """Przetwarza wszystkie PDF-y i zwraca listę utworzonych plików wyjściowych."""
    pdfs = find_pdfs(input_dir)
    total = len(pdfs)
    outputs: list[Path] = []

    for idx, pdf in enumerate(pdfs, start=1):
        relative = pdf.relative_to(input_dir)
        out = output_dir / output_name(relative)

        # Postęp: [bieżący/razem] plik — ile zostało do końca.
        print(f"[{idx}/{total}] {relative} — pozostało {total - idx}", file=sys.stderr)

        try:
            text = extractor.extract_text_from_pdf(pdf)
            result = build_result(relative, text, ex)
        except Exception as exc:  # nie przerywaj całego batcha na jednym pliku
            print(f"  Błąd przetwarzania {relative}: {exc}", file=sys.stderr)
            result = {}

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs.append(out)
    return outputs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Przetwarzanie wsadowe PDF z ./input/ do JSON w ./output/."
    )
    parser.add_argument("--input", default=str(INPUT_DIR), help="Katalog wejściowy z PDF.")
    parser.add_argument("--output", default=str(OUTPUT_DIR), help="Katalog wyjściowy na JSON.")
    parser.add_argument("--rules", default=str(DEFAULT_RULES), help="Plik reguł YAML.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    ex = extractor.load_extractor(Path(args.rules))
    outputs = process(input_dir, output_dir, ex)

    print(f"Przetworzono {len(outputs)} plików PDF.", file=sys.stderr)
    for out in outputs:
        print(f"  -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
