"""Przygotowuje dane testowe do ewaluacji — rozdziela PDF-y i wzorcowe JSON-y.

Użycie:
    python prepare_data.py --source dane/moja_sprawa

Dla każdego podfolderu w ``--source`` (np. ``case_01_baseline_paragrafy``):
- pliki ``*.pdf``  trafiają do ``input/<nazwa_podfolderu>/``,
- pliki ``*.json`` trafiają do ``data/uzp_materialy/dane/<nazwa_podfolderu>/``.

Dzięki temu ``start.bat`` czyta PDF-y z ``input/``, a ``evaluate.py`` porównuje
wynik z ``output/`` z wzorcami w ``data/uzp_materialy/dane/`` (te same nazwy
folderów w obu miejscach).

Opcje:
    --source PATH   katalog ze sprawami (domyślnie: dane/moja_sprawa)
    --clean         wyczyść input/ i data/uzp_materialy/dane/ przed kopiowaniem
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input"
REF_DIR = ROOT / "data" / "uzp_materialy" / "dane"

# Nazwa JSON-a dla przelewu musi być `przelew.json` (oczekuje tego evaluate.py).
TRANSFER_JSON_MAP = {
    "potwierdzenie_przelewu": "przelew",
}


def clear_dir(directory: Path, keep_gitkeep: bool = True) -> None:
    """Usuwa zawartość katalogu (zachowując opcjonalnie plik .gitkeep)."""
    if not directory.exists():
        return
    for item in directory.iterdir():
        if keep_gitkeep and item.name == ".gitkeep":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def prepare(source: Path, clean: bool = False) -> None:
    if not source.is_dir():
        raise SystemExit(f"Nie znaleziono katalogu źródłowego: {source}")

    if clean:
        clear_dir(INPUT_DIR)
        clear_dir(REF_DIR)

    pdfs_copied = 0
    jsons_copied = 0
    folders = sorted(p for p in source.iterdir() if p.is_dir())

    for case_dir in folders:
        name = case_dir.name
        pdfs = sorted(case_dir.glob("*.pdf"))
        jsons = sorted(case_dir.glob("*.json"))

        if not pdfs and not jsons:
            print(f"[pomijam] {name} — brak plików")
            continue

        if pdfs:
            dest = INPUT_DIR / name
            dest.mkdir(parents=True, exist_ok=True)
            for pdf in pdfs:
                shutil.copy2(pdf, dest / pdf.name)
                pdfs_copied += 1

        if jsons:
            dest = REF_DIR / name
            dest.mkdir(parents=True, exist_ok=True)
            for js in jsons:
                out_name = TRANSFER_JSON_MAP.get(js.stem, js.stem) + ".json"
                shutil.copy2(js, dest / out_name)
                jsons_copied += 1

    print(f"Gotowe: skopiowano {pdfs_copied} PDF-ów -> {INPUT_DIR}")
    print(f"        skopiowano {jsons_copied} JSON-ów -> {REF_DIR}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(ROOT / "dane" / "moja_sprawa"),
                        help="Katalog ze sprawami (PDF + JSON razem).")
    parser.add_argument("--clean", action="store_true",
                        help="Wyczyść input/ i data/uzp_materialy/dane/ przed kopiowaniem.")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    prepare(Path(args.source), clean=args.clean)
