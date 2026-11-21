"""Aplikacja FastAPI — ODWOŁANIA2JSON.

Endpoint POST /api/extract przyjmuje plik PDF i zwraca wynik ekstrakcji
wygenerowany przez silnik ``src/extractor.py`` (wzorzec Registry, reguły z YAML).

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

app = FastAPI(title="ODWOŁANIA2JSON API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ekstraktor budowany raz, na podstawie config/document_rules.yaml.
_extractor = extractor.load_extractor()


def _extract_from_pdf(pdf_bytes: bytes, filename: str) -> dict[str, Any]:
    """Zapisuje PDF do pliku tymczasowego i uruchamia silnik ekstrakcji."""
    suffix = Path(filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)

    try:
        text = extractor.extract_text_from_pdf(tmp_path)
        document_type = _extractor.detect(text)
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


# Serwowanie frontendu (musi być po zarejestrowaniu tras API).
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
