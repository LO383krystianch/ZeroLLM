"""Silnik ekstrakcji dokumentów oparty o wzorzec Registry.

Wczytuje reguły z ``config/document_rules.yaml`` i dynamicznie parsuje tekst
(wyekstrahowany np. z PDF przez pypdf) do zagnieżdżonych struktur JSON.

Zasady (AGENTS.md):
- **Zero hardcodowania** — typy dokumentów, pola i reguły pochodzą wyłącznie z YAML.
- **Registry** — handler dla danego ``kind`` reguły rejestruje się dekoratorem
  ``register``; dodanie nowego ``kind`` nie wymaga zmian w reszcie kodu.
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


def register(kind: str) -> Callable[[RuleHandler], RuleHandler]:
    """Dekorator rejestrujący handler dla rodzaju reguły ``kind``."""

    def decorator(fn: RuleHandler) -> RuleHandler:
        _REGISTRY[kind] = fn
        return fn

    return decorator


def _resolve_flags(rule: dict[str, Any]) -> int:
    """Zamienia wpis ``flags`` (str lub lista nazw) na wartość bitową ``re``."""
    raw = rule.get("flags", 0)
    if isinstance(raw, str):
        raw = [raw]
    if isinstance(raw, (list, tuple)):
        return functools.reduce(operator.or_, (_FLAGS.get(f, 0) for f in raw), 0)
    return int(raw or 0)


@register("regex")
def _regex_handler(rule: dict[str, Any], text: str) -> tuple[Any, str, str]:
    """Reguła regex: zwraca grupę dopasowania lub flagę obecności wzorca."""
    pattern = str(rule.get("pattern", ""))
    rule_used = f"regex:{pattern}"
    if not pattern:
        return None, "", rule_used

    compiled = re.compile(pattern, _resolve_flags(rule))
    match = compiled.search(text)

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
    return value, match.group(0), rule_used


# ---------------------------------------------------------------------------
# Ładowanie reguł i ekstraktor
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


def _field(value: Any, source_text: str = "", rule_used: str | None = None) -> dict[str, Any]:
    """Buduje obiekt transparentności pojedynczego pola."""
    return {"value": value, "source_text": source_text, "rule_used": rule_used}


class DocumentExtractor:
    """Parsuje tekst zgodnie ze strukturą i regułami z config/document_rules.yaml."""

    def __init__(self, rules: dict[str, Any]):
        self.rules: dict[str, Any] = rules or {}
        self.document_types: dict[str, Any] = self.rules.get("document_types", {}) or {}
        self.default_document_type: str | None = self.rules.get("default_document_type")

    @property
    def names(self) -> list[str]:
        return list(self.document_types.keys())

    def detect(self, text: str) -> str | None:
        """Wykrywa typ dokumentu (pierwsza reguła ``classification`` z dopasowaniem)."""
        for name, spec in self.document_types.items():
            for rule in spec.get("classification", []):
                handler = _REGISTRY.get(rule.get("kind"))
                if handler is None:
                    continue
                value, _, _ = handler(rule, text)
                if value:
                    return name
        return self.default_document_type

    def extract(self, text: str, document_type: str | None = None) -> dict[str, Any]:
        """Ekstrahuje pola dla danego (lub wykrytego) typu dokumentu."""
        doc_type = document_type or self.detect(text)
        if doc_type not in self.document_types:
            return {}
        structure = self.document_types[doc_type].get("structure", {})
        return self._extract_structure(structure, text)

    # -- wewnętrzna, rekurencyjna ekstrakcja ----------------------------------

    def _extract_structure(self, structure: dict[str, Any], text: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, spec in structure.items():
            result[name] = self._extract_field(spec, text)
        return result

    def _extract_field(self, spec: dict[str, Any], text: str) -> dict[str, Any]:
        ftype = spec.get("type", "string")
        if ftype == "object":
            return _field(self._extract_structure(spec.get("fields", {}), text))
        if ftype == "array":
            return _field(self._extract_items(spec.get("items", {}), text))
        return self._extract_scalar(spec, text)

    def _extract_items(self, item_spec: dict[str, Any], text: str) -> list[dict[str, Any]]:
        """Ekstrahuje elementy tablicy (na razie jeden; format pozwala rozszerzyć)."""
        item = self._extract_structure(item_spec.get("fields", {}), text)
        has_value = any(
            v.get("value") not in (None, "", False, []) for v in item.values()
        )
        return [item] if has_value else []

    def _extract_scalar(self, spec: dict[str, Any], text: str) -> dict[str, Any]:
        for rule in spec.get("rules", []):
            handler = _REGISTRY.get(rule.get("kind"))
            if handler is None:
                continue
            value, source, rule_used = handler(rule, text)
            if value not in (None, "", False):
                return _field(value, source, rule_used)
        return _field(None)
