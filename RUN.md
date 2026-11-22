# RUN — uruchomienie przetwarzania

Przetwarza wszystkie pliki `*.pdf` z katalogu `input/` (rekurencyjnie, także
z podfolderów) i zapisuje wyniki JSON do katalogu `output/`.

Komenda uruchamiana z katalogu `/opt/solution`:

```
cd /opt/solution && .venv/bin/python src/main.py --input input --output output
```

Komenda jest jednorazowa (batch) — kończy się sama po przetworzeniu wszystkich
plików, nie wymaga interakcji.

Wymagania (zainstalowane wcześniej na serwerze):

- Python 3.12+ z venv (`.venv`) i zależnościami (`requirements.txt`),
- Tesseract OCR z językiem polskim (`tesseract-ocr`, `tesseract-ocr-pol`).
