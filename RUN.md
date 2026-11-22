# RUN — uruchomienie przetwarzania

Przetwarza wszystkie pliki `*.pdf` z katalogu `input/` (rekurencyjnie, także
z podfolderów) i zapisuje wyniki JSON do katalogu `output/`.

Komenda (jednorazowa, kończy się sama, bez interakcji):

```
/opt/solution/.venv/bin/python /opt/solution/src/main.py --input /opt/solution/input --output /opt/solution/output
```

Wymagania (zainstalowane wcześniej na serwerze):

- Python 3.12+ z venv (`.venv`) i zależnościami (`requirements.txt`),
- Tesseract OCR z językiem polskim (`tesseract-ocr`, `tesseract-ocr-pol`).
