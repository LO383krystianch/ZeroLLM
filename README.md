# ODWOŁANIA2JSON

Ekstrakcja danych z dokumentów postępowania odwoławczego (odwołań do Krajowej
Izby Odwoławczej, pełnomocnictw, potwierdzeń przelewu) z plików **PDF** do
ustrukturyzowanego **JSON**, zgodnego ze schematami UZP.

Projekt zbudowany w całości w oparciu o **Python 3.13+**, działa lokalnie na
**CPU** — bez GPU, bez zewnętrznych/płatnych API LLM. Obsługuje także
**skany dokumentów** (OCR).

---

## Funkcje

- **Klasyfikacja** — automatyczne rozpoznanie 1 z 3 typów dokumentu:
  `odwołanie`, `pełnomocnictwo`, `przelew`.
- **Ekstrakcja pól** — wyodrębnienie istotnych danych z zachowaniem relacji
  (np. odwołujący → pełnomocnik, zamawiający → prowadzący postępowanie).
- **Zgodność ze schematem** — wynikowy JSON zgodny z oficjalnymi schematami UZP.
- **OCR skanów** — dokumenty bez warstwy tekstowej są czytane przez Tesseract
  (z fallbackiem na `easyocr`).
- **Transparentność** — każde pole zwraca `{value, source_text, rule_used}`,
  więc wiadomo, skąd pochodzi wartość i jaka reguła ją wyłowiła.
- **Rozszerzalność bez kodu** — nowe typy dokumentów i pola dodaje się wyłącznie
  w `config/document_rules.yaml` (wzorzec Registry).
- **Pusty wynik dla obcych plików** — dokument niepasujący do żadnego z 3 typów
  daje dokładnie `{}`.

---

## Szybki start

### 1. Przetwarzanie wsadowe (ocena automatyczna)

```bat
start.bat
```

Wczytuje wszystkie pliki `*.pdf` z `./input/` i zapisuje wyniki do `./output/`.

### 2. Pojedynczy plik (CLI)

```bat
run.bat --input dokument.pdf --output wynik.json
```

### 3. Aplikacja webowa (API + UI)

```bash
docker compose up --build
```

Otwórz <http://localhost:8000/>.

---

## Spis treści

1. [Typy dokumentów i schematy](#typy-dokumentów-i-schematy)
2. [Opis architektury](#opis-architektury)
3. [Struktura katalogów](#struktura-katalogów)
4. [Wymagania i instalacja](#wymagania-i-instalacja)
5. [Uruchomienie](#uruchomienie)
6. [Wejście i wyjście](#wejście-i-wyjście)
7. [Obsługa skanów (OCR)](#obsługa-skanów-ocr)
8. [Format wyniku i transparentność](#format-wyniku-i-transparentność)
9. [Konfiguracja — config/document_rules.yaml](#konfiguracja--configdocument_rulesyaml)
10. [Dodawanie nowej klasy dokumentów](#dodawanie-nowej-klasy-dokumentów)
11. [Ewaluacja (F1)](#ewaluacja-f1)
12. [Zasady projektowe](#zasady-projektowe)
13. [Rozwiązywanie problemów](#rozwiązywanie-problemów)

---

## Typy dokumentów i schematy

Każdy z 3 typów ma własny, ustalony schemat wynikowego JSON:

| Typ | Klucz główny | Zawartość (skrót) |
| --- | --- | --- |
| `odwołanie` | `OdwolanieKIO` + `Odwolujacy[]` + `Zamawiajacy[]` + `ZamowieniePubliczne` | data, czynność (kod + opis), miejscowość, dane odwołującego (KRS/NIP/REGON, pełnomocnik), dane zamawiającego, numer BZP/TED/postępowania, tytuł |
| `pełnomocnictwo` | `mocodawca[]` + `pelnomocnicy[]` | dane mocodawcy (nazwa/KRS/NIP/REGON), pełnomocnicy (imię i nazwisko, PESEL) |
| `przelew` | `przelew_bankowy` | data operacji, kwota, rachunek odbiorcy/nadawcy, numer transakcji, tytuł |

Pełna, aktualna definicja pól znajduje się w `config/document_rules.yaml`
(sekcja `document_types` → `structure`).

Przykład wyniku dla odwołania:

```json
{
  "OdwolanieKIO": {
    "data": "2026-07-02",
    "czynnosc_dzien": "2026-08-04",
    "czynnosc_powod_id": 4,
    "czynnosc_opis": "Publikacja specyfikacji warunków zamówienia (SWZ)",
    "miejscowosc": "Kraków"
  },
  "Odwolujacy": [
    {
      "krs": "9991840562",
      "nazwa": "Małopolskie Centrum Logistyki Medycznej sp. z o.o.",
      "nip": "9998802341",
      "regon": "999015873",
      "pelnomocnik": {
        "imie_nazwisko": "Joanna Stępień",
        "nazwa": "Stępień Borkowski Kancelaria Prawna sp.p.",
        "mail": "sekretariat@sbkancelaria.example"
      }
    }
  ],
  "Zamawiajacy": [ { "nazwa": "Gmina …", "prowadzacy_postepowanie": 1 } ],
  "ZamowieniePubliczne": {
    "numer_bzp": "2026/BZP00999263",
    "numer_postepowania": "MCLM/ZP/07/2026",
    "numer_ted": "999562-2026",
    "tytul": "Kompleksowe usługi utrzymania czystości…"
  }
}
```

---

## Opis architektury

Aplikacja składa się z warstw rozdzielonych tak, aby rozbudowa wymagała
**wyłącznie edycji konfiguracji**:

```
web/  ──►  api/app.py (FastAPI)  ──►  src/extractor.py (silnik)  ──►  config/document_rules.yaml
                                          │
                                          └──► wynik JSON (value, source_text, rule_used)
```

### 1. Warstwa API — `api/app.py`

Aplikacja **FastAPI**, która:

- udostępnia endpoint `POST /api/extract` przyjmujący plik **PDF**,
- wykrywa typ dokumentu; dla pliku nierozpoznanego zwraca sam **`{}`**,
- zwraca wynik JSON z metadanymi transparentności (źródłowy fragment tekstu + reguła),
- serwuje statyczny frontend (`web/`) pod `/`.

### 2. Silnik ekstrakcji — `src/extractor.py`

Silnik wg wzorca **Registry**:

- wczytuje typy dokumentów, pola i reguły z `config/document_rules.yaml`,
- dla każdego rodzaju reguły (`kind`) zarejestrowany jest handler (dekorator `@register`),
- **klasyfikuje** dokument (najpierw po nazwie pliku, potem po treści),
- **rekurencyjnie ekstrahuje** pola (string/date/number/boolean/object/array),
- każde pole zwraca obiekt transparentności `{value, source_text, rule_used}`,
- **ekstrahuje tekst** z PDF przez `pypdf`, a dla skanów uruchamia **OCR**.

### 3. Konfiguracja — `config/document_rules.yaml`

Jedyne źródło prawdy dla typów dokumentów, pól, reguł ekstrakcji i klasyfikacji.

### 4. Frontend — `web/`

Interfejs umożliwiający wgranie PDF-a, podgląd, uruchomienie ekstrakcji oraz
pobranie wynikowego JSON (pojedynczo lub zbiorczo jako ZIP).

---

## Struktura katalogów

```
.
├── api/
│   └── app.py              # FastAPI + CORS + POST /api/extract
├── config/
│   └── document_rules.yaml # typy dokumentów, pola i reguły (jedyne źródło prawdy)
├── src/
│   ├── extractor.py        # silnik ekstrakcji + OCR (wzorzec Registry)
│   ├── main.py             # przetwarzanie wsadowe ./input -> ./output
│   └── cli.py              # CLI dla pojedynczego pliku
├── web/                    # frontend (index.html, script.js, style.css, zipExport.js)
├── input/                  # pliki PDF wejściowe (z podfolderami)
├── output/                 # wynikowe pliki JSON (odtwarzana struktura podfolderów)
├── Dockerfile              # obraz: python:3.13-slim + Tesseract (polski)
├── docker-compose.yml
├── requirements.txt
├── run.bat                 # CLI — pojedynczy plik
├── start.bat               # wsadowe przetwarzanie input/ -> output/
└── README.md
```

---

## Wymagania i instalacja

- **Python 3.13+**
- Dla OCR (skany) — opcjonalnie **Tesseract** (binarka systemowa + język polski).

Zależności Pythona (patrz `requirements.txt`):

| Pakiet | Przeznaczenie |
| --- | --- |
| `fastapi` / `uvicorn` / `python-multipart` | warstwa API |
| `pypdf` | ekstrakcja tekstu z PDF |
| `pydantic` | walidacja/modelowanie |
| `PyYAML` | wczytywanie konfiguracji |
| `PyMuPDF` + `Pillow` | renderowanie stron PDF do obrazów (OCR) |
| `pytesseract` | OCR — Tesseract (binarka systemowa) |
| `easyocr` | OCR — fallback w pełni pip-instalowalny |

Instalacja:

```bash
pip install -r requirements.txt
```

---

## Uruchomienie

### 1. Przetwarzanie wsadowe — `start.bat` (ocena automatyczna)

```bat
start.bat
```

- Rekurencyjnie wyszukuje `*.pdf` w `./input/` (także w podfolderach).
- Dla każdego PDF: wyciąga tekst (pypdf/OCR), klasyfikuje i ekstrahuje pola.
- Zapisuje JSON do `./output/`, odtwarzając strukturę podfolderów.
- Dokument nierozpoznany → plik zawierający **`{}`**.

Domyślnie przetwarza `./input` → `./output`. Można to nadpisać:

```bash
python src/main.py --input ./input --output ./output
```

### 2. Pojedynczy plik — `run.bat` (CLI)

```bat
run.bat --input dokument.pdf --output wynik.json
```

lub:

```bash
python src/cli.py --input dokument.pdf --output wynik.json
```

Akceptuje **PDF** (z OCR dla skanów) oraz zwykły **TXT**.

### 3. Aplikacja webowa — Docker

```bash
docker compose up --build
```

- frontend: <http://localhost:8000/>
- API: `POST http://localhost:8000/api/extract`
- dokumentacja OpenAPI (Swagger): <http://localhost:8000/docs>

Obraz bazuje na `python:3.13-slim` i instaluje Tesseract z językiem polskim,
więc OCR działa od razu.

### 4. API lokalnie (bez Dockera)

```bash
pip install -r requirements.txt
uvicorn api.app:app --host 0.0.0.0 --port 8000 --app-dir .
```

---

## Wejście i wyjście

- **Wejście**: katalog `./input/` — pliki `*.pdf` (mogą być w podfolderach).
- **Wyjście**: katalog `./output/` — pliki `*.json` z **odtworzoną strukturą podfolderów**.

Mapowanie nazw:

```
input/case1/odwolanie.pdf             ->  output/case1/odwolanie.json
input/case1/pelnomocnictwo.pdf        ->  output/case1/pelnomocnictwo.json
input/case1/potwierdzenie_przelewu.pdf ->  output/case1/przelew.json
```

Zasada: nazwa JSON = nazwa PDF (zmiana rozszerzenia), z jednym wyjątkiem —
`potwierdzenie_przelewu.pdf` → `przelew.json` (zgodnie z nazewnictwem UZP).

### Dokument nierozpoznany („obcy" plik)

Jeśli dokument **nie pasuje** do żadnego z 3 typów, program generuje plik
zawierający dokładnie **pusty obiekt JSON `{}`** (2 bajty) — zarówno w trybie
wsadowym, jak i przez API/UI.

---

## Obsługa skanów (OCR)

Dokumenty **bez warstwy tekstowej** (zeskanowane) są rozpoznawane automatycznie:

1. `pypdf` próbuje wyciągnąć tekst.
2. Jeśli tekst jest pusty/prawie pusty (< 40 znaków) — uruchamiany jest OCR.

Kolejność silników OCR:

| Silnik | Instalacja | Kiedy używany |
| --- | --- | --- |
| **Tesseract** (polski) | binarka systemowa (Docker instaluje automatycznie; Windows — instalator) | pierwszy wybór — szybki i dokładny |
| **easyocr** (polski) | `pip install easyocr` (w `requirements.txt`) | fallback, gdy brak binarki Tesseract |

- **Docker**: Tesseract + polski instalowany w obrazie (`Dockerfile`) — OCR działa od razu.
- **Lokalnie (Windows)**: jeśli nie masz binarki Tesseract, działa `easyocr`
  (w pełni pip). Uwaga: `easyocr` przy pierwszym uruchomieniu **pobiera modele**
  (potrzebny internet) i jest wolniejszy na CPU.

Degradacja jest łagodna: gdy żaden silnik OCR nie jest dostępny, skan zwraca
pusty tekst (bez błędu), a wynik to `{}`.

---

## Format wyniku i transparentność

W **trybie wsadowym / CLI / pobieraniu z UI** wynik to **czysty JSON** (same
wartości), zgodny ze schematem UZP.

W **API** każde pole zwraca dodatkowo **obiekt transparentności**:

```json
{
  "value": "wyekstrahowana wartość",
  "source_text": "fragment tekstu źródłowego",
  "rule_used": "regex:<wzorzec>"
}
```

Dzięki temu w UI widać, skąd pochodzi wartość i jaka reguła została użyta.

---

## Konfiguracja — config/document_rules.yaml

Plik jest **jedynym źródłem prawdy** dla:

- typów dokumentów (`document_types`),
- reguł klasyfikacji (`classification`),
- struktury pól (`structure`),
- normalizatorów (`normalize`).

### Typy pól (`type`)

| `type` | Znaczenie |
| --- | --- |
| `string` | wartość tekstowa |
| `date` | data (normalizacja do ISO) |
| `number` | liczba |
| `boolean` | obecność wzorca |
| `integer` | liczba całkowita (np. kod przyczyny) |
| `object` | obiekt zagnieżdżony (`fields`) |
| `array` | tablica (`items.fields`) |

### Reguły ekstrakcji (`kind: regex`)

```yaml
- kind: regex
  pattern: '\bKRS\s*[:.]?\s*(\d{10})'   # wyrażenie regularne
  group: 1                              # nr grupy (domyślnie 0)
  flags: [IGNORECASE]                   # IGNORECASE / MULTILINE / DOTALL
  output: value                         # value (domyślnie) | boolean
  require: 'Konsorcjum'                 # wzorzec musi wystąpić (inaczej reguła pominięta)
  after: 'Lider\s+Konsorcjum\s*:'       # szukaj dopiero po tym markerze
  until: 'Działając'                    # szukaj tylko do tego markera
  normalize: whitespace                 # normalizacja wartości
```

### Klasyfikacja (`classification`)

Lista reguł — typ dokumentu to **pierwsze dopasowanie**. Reguły `kind: filename`
działają na nazwie pliku, `kind: regex` na treści.

---

## Dodawanie nowej klasy dokumentów

Dodanie nowego typu wymaga **wyłącznie edycji** `config/document_rules.yaml`.

Przykład — typ `faktura`:

```yaml
document_types:
  faktura:
    label: "Faktura"
    classification:
      - kind: regex
        pattern: '\b(?:faktura|Faktura VAT)\b'
        flags: [IGNORECASE]
    structure:
      dane_faktury:
        type: object
        fields:
          numer:
            type: string
            rules:
              - kind: regex
                pattern: '\b(?:numer|nr)\s+faktury\s*[:.]?\s*([A-Za-z0-9/.\-]+)'
                group: 1
                flags: [IGNORECASE]
          kwota:
            type: number
            rules:
              - kind: regex
                pattern: '\bkwota\s*[:.]?\s*([\d\s]+[.,]\d{2})'
                group: 1
                flags: [IGNORECASE]
```

Gotowe — silnik automatycznie rozpozna typ `faktura` i wyodrębni `numer` oraz
`kwota`. W ten sam sposób dodaje się nowe pola i reguły.

---

## Ewaluacja (F1)

Lokalny skrypt `evaluate.py` porównuje wygenerowane `output/` z plikami
referencyjnymi (ground truth) w `data/uzp_materialy/dane/` i liczy F1.

```bash
python evaluate.py
```

Oczekiwany układ danych testowych:

```
input/<sprawa>/*.pdf                  # dokumenty wejściowe
data/uzp_materialy/dane/<sprawa>/*.json  # wzorce (ground truth)
```

Nazwy folderów muszą się zgadzać, a pliki wzorcowe nazywać się
`odwolanie.json`, `pelnomocnictwo.json`, `przelew.json`.

---

## Zasady projektowe

- **Brak sztywnych nazw** dokumentów i pól w kodzie — wszystko z `config/document_rules.yaml`.
- **Wzorzec Registry** — nowy `kind` reguły rejestruje się dekoratorem `@register`.
- **Transparentność** — każde pole zwraca `{value, source_text, rule_used}`.
- **Lokalnie i open source** — CPU, bez GPU, bez zewnętrznych/płatnych API LLM.
- **Stabilne wejście/wyjście** — `./input/*.pdf` → `./output/*.json`.
- **Pusty wynik `{}`** dla dokumentów nierozpoznanych.

---

## Rozwiązywanie problemów

| Objaw | Przyczyna / rozwiązanie |
| --- | --- |
| Skan daje `{}` | brak OCR. Docker: przebuduj obraz. Lokalnie: zainstaluj Tesseract (`tesseract-ocr` + `tesseract-ocr-pol`) albo upewnij się, że `easyocr` jest zainstalowany i ma internet do pobrania modeli. |
| `start.bat` nie znajduje Pythona | użyj `py -3.13` albo dodaj Pythona do PATH (skrypt ma fallback `python`). |
| Obcy plik dostaje strukturę z `null` | upewnij się, że reguły klasyfikacji w `document_rules.yaml` są precyzyjne (pliki obce → `{}`). |
| Wynik w UI ma wrapper `{filename, …}` | pobierz przez przycisk „Pobierz .json" — zapisuje czysty JSON (same dane). |
