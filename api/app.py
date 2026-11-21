"""Aplikacja FastAPI — ODWOŁANIA2JSON.

Endpoints:
- ``GET  /health``             — healthcheck Dockera/load balancera.
- ``POST /api/extract``        — przyjmuje plik PDF, zwraca wynik ekstrakcji
  (czysty JSON + metadane transparentności: source_text, rule_used).
- ``GET  /api/config``         — aktualna konfiguracja (config/document_rules.yaml).
- ``POST /api/config/reload``  — przeładowanie konfiguracji bez restartu.

Frontend z katalogu ``web/`` jest serwowany statycznie pod ścieżką ``/``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src import extractor

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
CONFIG_DIR = ROOT / "config"
DEFAULT_RULES = CONFIG_DIR / "document_rules.yaml"

app = FastAPI(title="ODWOŁANIA2JSON API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ekstraktor budowany raz, na podstawie config/document_rules.yaml.
_extractor = extractor.load_extractor(DEFAULT_RULES)


def _load_rules() -> dict[str, Any]:
    """Wczytuje aktualne reguły z pliku YAML."""
    return extractor.load_rules(DEFAULT_RULES)


def _read_rules_text() -> str:
    """Zwraca surową treść pliku reguł YAML."""
    if DEFAULT_RULES.exists():
        return DEFAULT_RULES.read_text(encoding="utf-8")
    return ""


def _extract_from_pdf(pdf_bytes: bytes, filename: str) -> dict[str, Any]:
    """Zapisuje PDF do pliku tymczasowego i uruchamia silnik ekstrakcji."""
    suffix = Path(filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)

    try:
        text = extractor.extract_text_from_pdf(tmp_path)
        document_type = _extractor.detect(text, filename)
        if document_type is None:
            # Dokument nierozpoznany (obcy) — zwróć sam pusty obiekt {}
            # (wymóg jury: brak klasyfikacji do żadnego z 3 typów -> {}).
            return {}
        data = _extractor.extract(text, document_type)
        return {
            "filename": filename,
            "document_type": document_type,
            "data": data,
            "transparency": {
                "extracted_text_length": len(text),
                "text_preview": text[:500],
            },
        }
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/health")
async def health() -> dict[str, str]:
    """Prosty healthcheck dla Dockera/load balancera."""
    return {"status": "ok"}


@app.post("/api/extract")
async def extract_pdf(file: UploadFile = File(...)) -> dict[str, Any]:
    """Przyjmuje plik PDF i zwraca wyekstrahowane dane w formacie JSON."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Oczekiwano pliku PDF.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Przesłano pusty plik.")

    try:
        return _extract_from_pdf(content, file.filename)
    except Exception as exc:  # noqa: BLE001 - zwracamy czytelny błąd do UI
        raise HTTPException(
            status_code=500, detail=f"Ekstrakcja nie powiodła się: {exc}"
        ) from exc


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    """Zwraca aktualną konfigurację klas dokumentów (YAML + sparsowaną postać)."""
    return {
        "source": DEFAULT_RULES.name,
        "raw": _read_rules_text(),
        "parsed": _load_rules(),
    }


@app.post("/api/config/reload")
async def reload_config() -> dict[str, Any]:
    """Przeładowuje reguły z pliku YAML bez restartu aplikacji."""
    global _extractor
    _extractor = extractor.load_extractor(DEFAULT_RULES)
    return {"status": "ok", "document_types": _extractor.names}


# Serwowanie frontendu (musi być po zarejestrowaniu tras API).
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
