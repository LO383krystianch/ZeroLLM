"""Lokalny ewaluator F1 — porównanie wygenerowanego output/ z plikami referencyjnymi.

Użycie:
    python evaluate.py

Dla każdego podfolderu w ``output/`` (np. ``przyklad_01``) skrypt:
1. ładuje wygenerowane pliki JSON z ``output/<folder>/``,
2. ładuje pliki referencyjne z ``data/uzp_materialy/dane/<folder>/``,
3. porównuje klucze i wartości (difflib, próg >80%) licząc TP/FP/FN oraz F1.

Definicje (wg FAQ z Discorda):
- True Positive  — klucz istnieje w referencji i wartość jest zgodna >80% (difflib),
- False Positive — klucz istnieje w wyniku, ale nie w referencji (lub wartość niezgodna),
- False Negative — klucz istnieje w referencji, ale nie w wyniku.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
DATA_DIR = ROOT / "data" / "uzp_materialy" / "dane"

DOC_TYPES = ("odwolanie", "pelnomocnictwo", "przelew")
SIMILARITY_THRESHOLD = 0.8


def load_json(path: Path) -> dict[str, Any]:
    """Wczytuje plik JSON (w razie błędu zwraca {})."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def flatten_paths(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Spłaszcza JSON do mapy ``{ścieżka.klucza: wartość}`` (listy z indeksem ``[i]``)."""
    result: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(flatten_paths(value, path))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            result.update(flatten_paths(value, f"{prefix}[{idx}]"))
    else:
        result[prefix] = obj
    return result


def similarity(a: Any, b: Any) -> float:
    """Podobieństwo dwóch wartości (0.0–1.0).

    - None vs None -> 1.0 (zgodne), None vs wartość -> 0.0,
    - liczby porównywane numerycznie (dokładnie),
    - pozostałe porównywane tekstowo przez difflib.
    """
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.0
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return 1.0 if a == b else 0.0
    return difflib.SequenceMatcher(None, str(a), str(b)).ratio()


def count_metrics(output: dict[str, Any], reference: dict[str, Any]) -> tuple[int, int, int]:
    """Liczy (TP, FP, FN) dla pary (wynik, referencja)."""
    out_flat = flatten_paths(output)
    ref_flat = flatten_paths(reference)

    tp = fp = fn = 0
    for path, ref_value in ref_flat.items():
        if path in out_flat:
            if similarity(out_flat[path], ref_value) > SIMILARITY_THRESHOLD:
                tp += 1
            else:
                fp += 1
        else:
            fn += 1
    for path in out_flat:
        if path not in ref_flat:
            fp += 1
    return tp, fp, fn


def compute_f1(tp: int, fp: int, fn: int) -> float:
    """Oblicza wskaźnik F1 z TP/FP/FN."""
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def main() -> int:
    folders = sorted(p for p in OUTPUT_DIR.iterdir() if p.is_dir())
    if not folders:
        print("Brak podfolderów w output/.")
        return 0

    rows: list[tuple[str, str, int, int, int, float]] = []
    total_tp = total_fp = total_fn = 0

    for folder in folders:
        ref_dir = DATA_DIR / folder.name
        if not ref_dir.is_dir():
            continue
        for doc_type in DOC_TYPES:
            out_file = folder / f"{doc_type}.json"
            ref_file = ref_dir / f"{doc_type}.json"
            if not out_file.exists() or not ref_file.exists():
                continue
            tp, fp, fn = count_metrics(load_json(out_file), load_json(ref_file))
            f1 = compute_f1(tp, fp, fn)
            rows.append((folder.name, doc_type, tp, fp, fn, f1))
            total_tp += tp
            total_fp += fp
            total_fn += fn

    # Raport.
    line = "-" * 78
    print("=" * 78)
    print("RAPORT EWALUACJI F1 — ODWOŁANIA2JSON")
    print("=" * 78)
    print(f"{'Folder':<16}{'Typ':<16}{'TP':>6}{'FP':>6}{'FN':>6}{'F1':>10}")
    print(line)
    for folder, doc_type, tp, fp, fn, f1 in rows:
        print(f"{folder:<16}{doc_type:<16}{tp:>6}{fp:>6}{fn:>6}{f1:>10.4f}")
    print(line)
    total_f1 = compute_f1(total_tp, total_fp, total_fn)
    print(f"{'RAZEM':<16}{'':<16}{total_tp:>6}{total_fp:>6}{total_fn:>6}{total_f1:>10.4f}")
    print("=" * 78)

    if rows:
        avg_f1 = sum(r[5] for r in rows) / len(rows)
        print(f"Dokumentów porównanych: {len(rows)}")
        print(f"Średni F1 (per dokument): {avg_f1:.4f}")
        print(f"F1 łączny (z sum TP/FP/FN): {total_f1:.4f}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
