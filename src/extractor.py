"""Silnik ekstrakcji dokumentów oparty o wzorzec Registry.

Wczytuje reguły z ``config/document_rules.yaml`` i dynamicznie parsuje tekst
(wyekstrahowany np. z PDF przez pypdf) do zagnieżdżonych struktur JSON.

Zasady (AGENTS.md):
- **Zero hardcodowania** — typy dokumentów, pola, sekcje i reguły pochodzą wyłącznie z YAML.
- **Registry** — handler dla danego ``kind`` reguły rejestruje się dekoratorem
  ``register``; dodanie nowego ``kind`` nie wymaga zmian w reszcie kodu.
- **Segmentacja kontekstowa** — tekst jest najpierw dzielony na bloki (``sections``),
  a reguły pola są aplikowane wyłącznie do wskazanego bloku (``section``).
- **Transparentność** — każde pole zwraca obiekt ``{value, source_text, rule_used}``.
"""

from __future__ import annotations

import functools
import operator
import re
from pathlib import Path
from typing import Any, Callable

import yaml

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_RULES = CONFIG_DIR / "document_rules.yaml"


# ---------------------------------------------------------------------------
# Registry handlerów reguł ekstrakcji
# ---------------------------------------------------------------------------

# Handler przyjmuje (rule: dict, text: str) i zwraca (value, source_text, rule_used).
RuleHandler = Callable[[dict[str, Any], str], tuple[Any, str, str]]

_REGISTRY: dict[str, RuleHandler] = {}

_FLAGS: dict[str, int] = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
}

# Polskie nazwy miesięcy (dopełniacz) -> numer miesiąca, do normalizacji dat.
_PL_MONTHS: dict[str, int] = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
    "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8,
    "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
}

_PL_DATE_RE = re.compile(
    r"(\d{1,2})\s+"
    r"(stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)"
    r"\s+(\d{4})",
    re.IGNORECASE,
)


def register(kind: str) -> Callable[[RuleHandler], RuleHandler]:
    """Dekorator rejestrujący handler dla rodzaju reguły ``kind``."""

    def decorator(fn: RuleHandler) -> RuleHandler:
        _REGISTRY[kind] = fn
        return fn

    return decorator


def _resolve_flags(spec: dict[str, Any]) -> int:
    """Zamienia wpis ``flags`` (str lub lista nazw) na wartość bitową ``re``."""
    raw = spec.get("flags", 0)
    if isinstance(raw, str):
        raw = [raw]
    if isinstance(raw, (list, tuple)):
        return functools.reduce(operator.or_, (_FLAGS.get(f, 0) for f in raw), 0)
    return int(raw or 0)


@register("regex")
def _regex_handler(rule: dict[str, Any], text: str) -> tuple[Any, str, str]:
    """Reguła regex: zwraca grupę dopasowania lub flagę obecności wzorca.

    Opcjonalne sterowanie zakresem wyszukiwania:
    - ``require``: wzorzec, który musi wystąpić w tekście (inaczej reguła pominięta),
    - ``after``: marker — dopasowanie szukane dopiero po pierwszym jego wystąpieniu.
    """
    pattern = str(rule.get("pattern", ""))
    rule_used = f"regex:{pattern}"
    if not pattern:
        return None, "", rule_used

    flags = _resolve_flags(rule)

    require = rule.get("require")
    if require and re.search(str(require), text, flags) is None:
        return None, "", rule_used

    search_text = text
    after = rule.get("after")
    if after:
        anchor = re.search(str(after), text, flags)
        if anchor is None:
            return None, "", rule_used
        search_text = text[anchor.end():]

    match = re.search(pattern, search_text, flags)

    if str(rule.get("output", "value")) == "boolean":
        if match:
            return True, match.group(0), rule_used
        return False, "", rule_used

    if not match:
        return None, "", rule_used

    group = int(rule.get("group", 0))
    try:
        value = match.group(group)
    except IndexError:
        value = match.group(0)
    if rule.get("normalize") == "whitespace":
        value = " ".join(str(value).split())
    return value, match.group(0), rule_used


@register("filename")
def _filename_handler(rule: dict[str, Any], filename: str) -> tuple[Any, str, str]:
    """Reguła klasyfikacji po nazwie pliku (dopasowanie wzorca do nazwy)."""
    pattern = str(rule.get("pattern", ""))
    rule_used = f"filename:{pattern}"
    if pattern and re.search(pattern, filename, _resolve_flags(rule)):
        return filename, filename, rule_used
    return None, "", rule_used


# ---------------------------------------------------------------------------
# Ładowanie reguł i segmentacja tekstu
# ---------------------------------------------------------------------------


def load_rules(path: Path | None = None) -> dict[str, Any]:
    """Wczytuje reguły z pliku YAML (brak pliku -> {})."""
    path = path or DEFAULT_RULES
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_extractor(path: Path | None = None) -> "DocumentExtractor":
    """Buduje ekstraktor na podstawie reguł z pliku YAML."""
    return DocumentExtractor(load_rules(path))


def extract_text_from_pdf(path: Path) -> str:
    """Wyodrębnia tekst z PDF (pypdf) do dalszego parsowania."""
    if PdfReader is None:
        raise RuntimeError("Brak biblioteki pypdf. Zainstaluj zależności z requirements.txt.")
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def segment_text(text: str, sections: list[dict[str, Any]] | None) -> dict[str, str]:
    """Dzieli tekst na bloki kontekstowe wg markerów ``start`` (pierwsza sekcja = od początku).

    Każda sekcja to ``{name, start, flags?}``. Blok sekcji rozciąga się od pozycji
    jej markera do pozycji markera kolejnej sekcji (albo do końca tekstu).
    """
    blocks: dict[str, str] = {}
    if not sections:
        return blocks

    # Znajdź pozycję startową każdej sekcji.
    named_positions: list[tuple[str, int]] = []
    for spec in sections:
        name = spec.get("name")
        start = spec.get("start")
        if not start:
            pos = 0
        else:
            match = re.search(str(start), text, _resolve_flags(spec))
            pos = match.start() if match else -1
        named_positions.append((name, pos))

    # Uporządkuj wg pozycji (sekcje bez trafienia pomijane w cięciu).
    found = [(name, pos) for name, pos in named_positions if pos >= 0]
    found.sort(key=lambda item: item[1])

    for idx, (name, pos) in enumerate(found):
        end = found[idx + 1][1] if idx + 1 < len(found) else len(text)
        blocks[name] = text[pos:end]

    # Sekcje, których marker nie wystąpił, są puste (reguły na nich zwrócą null).
    for name, pos in named_positions:
        if pos < 0:
            blocks.setdefault(name, "")

    return blocks


def _field(value: Any, source_text: str = "", rule_used: str | None = None) -> dict[str, Any]:
    """Buduje obiekt transparentności pojedynczego pola."""
    return {"value": value, "source_text": source_text, "rule_used": rule_used}


class DocumentExtractor:
    """Parsuje tekst zgodnie ze strukturą, sekcjami i regułami z config/document_rules.yaml."""

    def __init__(self, rules: dict[str, Any]):
        self.rules: dict[str, Any] = rules or {}
        self.document_types: dict[str, Any] = self.rules.get("document_types", {}) or {}
        self.default_document_type: str | None = self.rules.get("default_document_type")
        self._normalizers: dict[str, Callable[[Any], Any]] = {
            "iso_date": self._normalize_iso_date,
            "bool_to_int": self._normalize_bool_to_int,
            "iban_clean": self._normalize_iban_clean,
        }

    @property
    def names(self) -> list[str]:
        return list(self.document_types.keys())

    def detect(self, text: str, filename: str | None = None) -> str | None:
        """Wykrywa typ dokumentu.

        Kolejność: najpierw reguły klasyfikacji oparte o nazwę pliku (``kind: filename``),
        potem reguły tekstowe (``kind: regex``).
        """
        if filename:
            doc_type = self._classify(filename, kind="filename")
            if doc_type is not None:
                return doc_type
        doc_type = self._classify(text, skip_kind="filename")
        if doc_type is not None:
            return doc_type
        return self.default_document_type

    def _classify(
        self,
        against: str,
        kind: str | None = None,
        skip_kind: str | None = None,
    ) -> str | None:
        """Stosuje reguły klasyfikacji (określonego ``kind``) względem ``against``."""
        for name, spec in self.document_types.items():
            for rule in spec.get("classification", []):
                rule_kind = rule.get("kind")
                if kind is not None and rule_kind != kind:
                    continue
                if skip_kind is not None and rule_kind == skip_kind:
                    continue
                handler = _REGISTRY.get(rule_kind)
                if handler is None:
                    continue
                value, _, _ = handler(rule, against)
                if value:
                    return name
        return None

    def extract(self, text: str, document_type: str | None = None) -> dict[str, Any]:
        """Ekstrahuje pola dla danego (lub wykrytego) typu dokumentu."""
        doc_type = document_type or self.detect(text)
        if doc_type not in self.document_types:
            return {}
        spec = self.document_types[doc_type]
        structure = spec.get("structure", {})
        blocks = segment_text(text, spec.get("sections"))
        return self._extract_structure(structure, text, blocks)

    # -- wewnętrzna, rekurencyjna ekstrakcja ----------------------------------

    def _extract_structure(
        self,
        structure: dict[str, Any],
        text: str,
        blocks: dict[str, str],
        default_section: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, spec in structure.items():
            result[name] = self._extract_field(spec, text, blocks, default_section)
        return result

    def _extract_field(
        self,
        spec: dict[str, Any],
        text: str,
        blocks: dict[str, str],
        default_section: str | None = None,
    ) -> dict[str, Any]:
        section = spec.get("section", default_section)
        # Obecność `fields`/`items` decyduje o strukturze (umożliwia typy jak
        # `object`, `array`, ale też własne etykiety, np. `osoba_prawna`).
        if "fields" in spec:
            value = self._extract_structure(spec.get("fields", {}), text, blocks, section)
            return _field(value)
        if "items" in spec:
            value = self._extract_items(spec, text, blocks, section)
            return _field(value)
        return self._extract_scalar(spec, text, blocks, section)

    def _extract_items(
        self,
        spec: dict[str, Any],
        text: str,
        blocks: dict[str, str],
        default_section: str | None = None,
    ) -> list[dict[str, Any]]:
        """Ekstrahuje elementy tablicy (jedno- lub wieloelementowej).

        Opcje na poziomie tablicy:
        - ``after`` / ``until`` — zawężenie zakresu źródła,
        - ``separator`` — regex dzielący tekst na pojedyncze elementy.
        """
        section = spec.get("section", default_section)
        source = self._resolve_source(section, text, blocks)
        item_spec = spec.get("items", {})
        items: list[dict[str, Any]] = []
        for part in self._split_items(source, spec):
            item = self._extract_structure(item_spec.get("fields", {}), part, {})
            has_value = any(
                v.get("value") not in (None, "", False, []) for v in item.values()
            )
            if has_value:
                items.append(item)
        return items

    @staticmethod
    def _split_items(source: str, spec: dict[str, Any]) -> list[str]:
        """Dzieli źródło tablicy na fragmenty (bloki elementów)."""
        flags = _resolve_flags(spec)
        after = spec.get("after")
        if after:
            anchor = re.search(str(after), source, flags)
            if anchor is not None:
                source = source[anchor.end():]
        until = spec.get("until")
        if until:
            stop = re.search(str(until), source, flags)
            if stop is not None:
                source = source[:stop.start()]
        separator = spec.get("separator")
        if not separator:
            return [source]
        return [part for part in re.split(str(separator), source, flags) if part.strip()]

    def _extract_scalar(
        self,
        spec: dict[str, Any],
        text: str,
        blocks: dict[str, str],
        section: str | None = None,
    ) -> dict[str, Any]:
        source = self._resolve_source(section, text, blocks)
        ftype = spec.get("type")
        normalize = spec.get("normalize")
        for rule in spec.get("rules", []):
            handler = _REGISTRY.get(rule.get("kind"))
            if handler is None:
                continue
            value, src, rule_used = handler(rule, source)
            if str(rule.get("output")) == "boolean":
                # Wynik logiczny: True/False jest prawidłową wartością pola.
                return _field(self._postprocess(value, ftype, normalize), src, rule_used)
            if value not in (None, "", False):
                return _field(self._postprocess(value, ftype, normalize), src, rule_used)
        return _field(None)

    def _resolve_source(
        self,
        section: str | None,
        text: str,
        blocks: dict[str, str],
    ) -> str:
        """Wybiera tekst źródłowy: wskazany blok sekcji albo cały tekst."""
        if not section:
            return text
        if isinstance(section, str):
            return blocks.get(section, "")
        if isinstance(section, (list, tuple)):
            return "\n".join(blocks.get(s, "") for s in section)
        return text

    @staticmethod
    def _cast(value: Any, ftype: str | None) -> Any:
        """Rzutuje wartość na typ docelowy (np. ``integer`` -> int)."""
        if value is None:
            return None
        if ftype == "integer":
            try:
                return int(str(value).strip())
            except (TypeError, ValueError):
                return value
        return value

    def _postprocess(self, value: Any, ftype: str | None, normalize: str | None) -> Any:
        """Rzutuje na typ docelowy, a następnie aplikuje wskazany normalizator."""
        value = self._cast(value, ftype)
        return self._normalize(value, normalize)

    def _normalize(self, value: Any, name: str | None) -> Any:
        """Aplikuje nazwany normalizator (``iso_date``, ``bool_to_int``)."""
        if value is None or not name:
            return value
        normalizer = self._normalizers.get(name)
        return normalizer(value) if normalizer else value

    def _normalize_iso_date(self, value: Any) -> Any:
        """Zamienia polską nazwę miesiąca (np. ``3 lipca 2026``) na ISO ``2026-07-03``."""
        if value is None:
            return None
        match = _PL_DATE_RE.search(str(value).strip())
        if not match:
            return value
        day = int(match.group(1))
        month = _PL_MONTHS.get(match.group(2).lower())
        if month is None:
            return value
        year = int(match.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    def _normalize_bool_to_int(self, value: Any) -> Any:
        """Zamienia wartość logiczną (True/False, 'true'/'false') na 1/0."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return 1 if value else 0
        if value is None:
            return None
        s = str(value).strip().lower()
        if s in ("true", "1", "tak", "yes"):
            return 1
        if s in ("false", "0", "nie", "no"):
            return 0
        return value

    def _normalize_iban_clean(self, value: Any) -> Any:
        """Usuwa prefiks ``PL`` oraz spacje z numeru konta bankowego."""
        if value is None:
            return None
        s = str(value).strip()
        if s[:2].upper() == "PL":
            s = s[2:]
        return re.sub(r"\s+", "", s)
