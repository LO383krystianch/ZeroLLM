"""Przetwarzanie wsadowe plików PDF z ./input/ do ./output/.

Użycie:
    start.bat
    python src/main.py [--input ./input] [--output ./output]

Dla każdego pliku PDF w ./input/ (rekurencyjnie, z podfolderami) generowany
jest wynikowy plik JSON w ./output/ z zachowaniem struktury katalogów,
np. input/case1/doc.pdf -> output/case1/doc.json.

Reguły klasyfikacji/ekstrakcji są ładowane dynamicznie z config/document_rules.yaml
(wzorzec Registry) — żadne nazwy dokumentów ani pól nie są wpisane na sztywno.
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

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
CONFIG_DIR = ROOT / "config"
DEFAULT_RULES = CONFIG_DIR / "document_rules.yaml"


def load_rules(path: Path) -> dict[str, Any]:
    """Wczytuje reguły z pliku YAML (pusty/brak pliku -> {})."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def find_pdfs(input_dir: Path) -> list[Path]:
    """Rekurencyjnie wyszukuje pliki PDF w podanym katalogu."""
    if not input_dir.exists():
        return []
    return sorted(p for p in input_dir.rglob("*.pdf") if p.is_file())


def extract_text(path: Path) -> str:
    """Wyodrębnia tekst z pliku PDF za pomocą pypdf."""
    if PdfReader is None:
        raise RuntimeError("Brak biblioteki pypdf. Zainstaluj zależności z requirements.txt.")
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def build_result(relative: Path, text: str, rules: dict[str, Any]) -> dict[str, Any]:
    """Buduje (na razie pusty/mockowany) wynik zgodny z regułami z konfiguracji.

    Każde pole ma docelowo obiekt: {value, source_text, rule_used}.
    Dopóki config/document_rules.yaml nie zawiera reguł, lista pól jest pusta.
    """
    document_type = rules.get("default_document_type") if isinstance(rules, dict) else None
    return {
        "source": relative.as_posix(),
        "document_type": document_type,
        "fields": [],
        "transparency": {
            "rule_used": None,
            "source_fragment": text[:500] if text else "",
            "extracted_text_length": len(text),
        },
    }


def process(input_dir: Path, output_dir: Path, rules: dict[str, Any]) -> list[Path]:
    """Przetwarza wszystkie PDF-y i zwraca listę utworzonych plików wyjściowych."""
    outputs: list[Path] = []
    for pdf in find_pdfs(input_dir):
        relative = pdf.relative_to(input_dir)
        out = output_dir / relative.with_suffix(".json")

        try:
            text = extract_text(pdf)
            result = build_result(relative, text, rules)
        except Exception as exc:  # nie przerywaj całego batcha na jednym pliku
            result = {
                "source": relative.as_posix(),
                "document_type": None,
                "fields": [],
                "error": str(exc),
                "transparency": {
                    "rule_used": None,
                    "source_fragment": "",
                    "extracted_text_length": 0,
                },
            }

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
    rules = load_rules(Path(args.rules))

    outputs = process(input_dir, output_dir, rules)

    print(f"Przetworzono {len(outputs)} plików PDF.", file=sys.stderr)
    for out in outputs:
        print(f"  -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
