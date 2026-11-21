# ODWOŁANIA2JSON

Ekstrakcja danych z dokumentów (m.in. odwołań do Krajowej Izby Odwoławczej,
pełnomocnictw, przelewów bankowych) z plików **PDF** do ustrukturyzowanego
**JSON**. Projekt zbudowany w całości w oparciu o **Python 3.13+**, działa
lokalnie na **CPU** — bez GPU, bez zewnętrznych/płatnych API LLM.

---

## Spis treści

1. [Opis architektury](#opis-architektury)
2. [Struktura katalogów](#struktura-katalogów)
3. [Wymagania i zależności](#wymagania-i-zależności)
4. [Uruchomienie — Docker (docker-compose.yml)](#uruchomienie--docker-docker-composeyml)
5. [Uruchomienie — ocena automatyczna (start.bat)](#uruchomienie--ocena-automatyczna-startbat)
6. [Interfejs API (FastAPI)](#interfejs-api-fastapi)
7. [Format wyniku JSON i transparentność](#format-wyniku-json-i-transparentność)
8. [Konfiguracja — config/document_rules.yaml](#konfiguracja--configdocument_rulesyaml)
9. [Dodawanie nowej klasy dokumentów bez zmiany kodu](#dodawanie-nowej-klasy-dokumentów-bez-zmiany-kodu)
10. [Zasady projektowe (zero hardcodowania)](#zasady-projektowe-zero-hardcodowania)

---

## Opis architektury

Aplikacja składa się z dwóch głównych warstw, rozdzielonych w sposób, który
pozwala rozbudowywać system **wyłącznie przez edycję konfiguracji**:

```
web/  ──►  api/app.py (FastAPI)  ──►  src/extractor.py (silnik)  ──►  config/document_rules.yaml
                                          │
                                          └──► wynik JSON (value, source_text, rule_used)
```

### 1. Warstwa API — `api/app.py`

Aplikacja **FastAPI**, która:

- udostępnia endpoint `POST /api/extract` przyjmujący plik **PDF**,
- posiada `CORSMiddleware` z `allow_origins=['*']`,
- zapisuje przesłany PDF do pliku tymczasowego i przekazuje go do silnika
  ekstrakcji,
- zwraca wynik JSON z dołączoną informacją o transparentności (źródłowy
  fragment tekstu + użyta reguła),
- serwuje statyczny frontend z katalogu `web/` pod ścieżką `/`.

### 2. Silnik ekstrakcji — `src/extractor.py`

Silnik zaimplementowany wg wzorca **Registry**:

- wczytuje typy dokumentów, pola i reguły z `config/document_rules.yaml`,
- dla każdej reguły (atrybut `kind`) zarejestrowany jest handler (dekorator
  `register`); dodanie nowego `kind` nie wymaga zmiany reszty kodu,
- wykrywa typ dokumentu (klasyfikacja) i rekurencyjnie ekstrahuje pola,
- każde pole zwraca obiekt transparentności `{value, source_text, rule_used}`.

### 3. Konfiguracja — `config/document_rules.yaml`

Jedno źródło prawdy dla **typów dokumentów**, **pól** i **reguł** ekstrakcji
oraz **klasyfikacji**. Zobacz sekcję
[Konfiguracja](#konfiguracja--configdocument_rulesyaml).

### 4. Frontend — `web/`

Prosty interfejs (`index.html` + `script.js`) umożliwiający wgranie pliku PDF,
podgląd go w przeglądarce, wywołanie ekstrakcji oraz pobranie wynikowego JSON.

---

## Struktura katalogów

```
.
├── api/
│   ├── __init__.py
│   └── app.py              # FastAPI + CORS + POST /api/extract
├── config/
│   └── document_rules.yaml # typy dokumentów, pola i reguły (główne źródło prawdy)
├── src/
│   ├── __init__.py
│   ├── extractor.py        # silnik ekstrakcji (wzorzec Registry)
│   ├── main.py             # przetwarzanie wsadowe ./input -> ./output
│   └── cli.py              # CLI dla pojedynczego pliku
├── web/
│   ├── index.html
│   └── script.js
├── input/                  # pliki PDF wejściowe (z podfolderami)
├── output/                 # wynikowe pliki JSON (odtwarzana struktura podfolderów)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── run.bat                 # CLI — pojedynczy plik
├── start.bat               # wsadowe przetwarzanie input/ -> output/
└── README.md
```

---

## Wymagania i zależności

- **Python 3.13+**
- Zależności (instalowane przez `pip`, patrz `requirements.txt`):

| Pakiet | Przeznaczenie |
| --- | --- |
| `fastapi` | warstwa API |
| `uvicorn` | serwer ASGI |
| `python-multipart` | odbiór przesyłanych plików (multipart/form-data) |
| `pypdf` | ekstrakcja tekstu z PDF |
| `pydantic` | walidacja/modelowanie danych |
| `PyYAML` | wczytywanie konfiguracji YAML |

Instalacja lokalna:

```bash
pip install -r requirements.txt
```

---

## Uruchomienie — Docker (docker-compose.yml)

Najprostszy sposób uruchomienia całej aplikacji (API + frontend):

```bash
docker compose up --build
```

Po uruchomieniu:

- frontend: <http://localhost:8000/>
- API: `POST http://localhost:8000/api/extract`
- dokumentacja OpenAPI (Swagger): <http://localhost:8000/docs>

`docker-compose.yml`:

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config   # reguły/schematy — edytowalne bez rebuild
      - ./input:/app/input     # pliki PDF wejściowe
      - ./output:/app/output   # wyniki JSON
```

Dzięki montowaniu `config/` jako wolumenu zmiany w regułach są widoczne
natychmiast po restarcie kontenera (bez przebudowy obrazu).

> Obraz bazowy: `python:3.13-slim`. Kontener wystawia port **8000**.

---

## Uruchomienie — ocena automatyczna (start.bat)

Do oceny automatycznej służy skrypt **`start.bat`** w głównym katalogu
projektu. Przetwarza on cały folder `./input/` i generuje wyniki w `./output/`:

```
start.bat
```

Działanie (wewnętrznie uruchamia `python src/main.py`):

1. Rekurencyjnie wyszukuje wszystkie pliki `*.pdf` w `./input/` (także
   w podfolderach, np. `./input/case1/odwolanie_nr_1.pdf`).
2. Dla każdego PDF wyodrębnia tekst (`pypdf`), wykrywa typ dokumentu
   i ekstrahuje pola zgodnie z `config/document_rules.yaml`.
3. Zapisuje wynikowy JSON do `./output/`, **odtwarzając strukturę podfolderów**
   z `input/`, np.:

   ```
   input/case1/odwolanie_nr_1.pdf  ->  output/case1/odwolanie_nr_1.json
   ```

   Nazwa pliku JSON jest identyczna z nazwą PDF (zmienione tylko rozszerzenie).

Opcjonalne argumenty (domyślnie `./input` i `./output`):

```bash
python src/main.py --input ./input --output ./output
```

### Przetwarzanie pojedynczego pliku (CLI)

Skrypt `run.bat` uruchamia `src/cli.py` dla jednego pliku:

```bash
run.bat --input dokument.pdf --output wynik.json
```

---

## Interfejs API (FastAPI)

### `POST /api/extract`

Przyjmuje plik PDF (pole formularza `file`) i zwraca wynik ekstrakcji.

Przykład (curl):

```bash
curl -F "file=@./input/odwolanie.pdf" http://localhost:8000/api/extract
```

Przykład odpowiedzi:

```json
{
  "filename": "odwolanie.pdf",
  "document_type": "odwolanie",
  "data": {
    "OdwolanieKIO": {
      "data": {
        "value": "12.01.2025",
        "source_text": "data: 12.01.2025",
        "rule_used": "regex:..."
      }
    }
  },
  "transparency": {
    "extracted_text_length": 2143,
    "text_preview": "Fragment pierwszych 500 znaków tekstu..."
  }
}
```

---

## Format wyniku JSON i transparentność

Każde pole wyniku zawiera **obiekt transparentności**, a nie surową wartość:

```json
{
  "value": "wyekstrahowana wartość",
  "source_text": "dokładny fragment tekstu źródłowego, z którego pobrano wartość",
  "rule_used": "regex:<wzorzec>"
}
```

Pozwala to zweryfikować i zaprezentować w UI, skąd pochodzi dana wartość
i jaka reguła została użyta. Dodatkowo cały wynik zawiera blok `transparency`
z długością wyodrębnionego tekstu i jego podglądem.

---

## Konfiguracja — config/document_rules.yaml

Plik `config/document_rules.yaml` jest **jedynym źródłem prawdy** dla:

- typów dokumentów (`document_types`),
- reguł klasyfikacji (`classification`),
- struktury pól (`structure`),
- domyślnego typu dokumentu (`default_document_type`).

### Typy pól (`type`)

| `type` | Znaczenie | Opis |
| --- | --- | --- |
| `string` | wartość tekstowa | wartość skalarna + `rules[]` |
| `date` | data | wartość skalarna + `rules[]` |
| `number` | liczba | wartość skalarna + `rules[]` |
| `boolean` | prawda/fałsz | obecność wzorca (reguła `output: boolean`) |
| `object` | obiekt zagnieżdżony | pola w `fields` |
| `array` | tablica | elementy opisane w `items.fields` |

### Reguły ekstrakcji (`kind`)

Obecnie zarejestrowany jest handler `regex`:

```yaml
- kind: regex
  pattern: '\bKRS[ \t]*[:.]?[ \t]*(\d{10})'   # wyrażenie regularne
  group: 1                                    # nr grupy dopasowania (domyślnie 0)
  flags: [IGNORECASE]                         # opcjonalnie: IGNORECASE, MULTILINE, DOTALL
  output: value                               # value (domyślnie) | boolean (obecność wzorca)
```

### Klasyfikacja (`classification`)

Lista reguł; typ dokumentu jest wykrywany po **pierwszym dopasowaniu**.
Przykład:

```yaml
odwolanie:
  label: "Odwołanie do KIO"
  classification:
    - kind: regex
      pattern: '\b(?:odwołanie|odwołuj|KIO|Krajowa Izba Odwoławcza)\b'
      flags: [IGNORECASE]
```

---

## Dodawanie nowej klasy dokumentów bez zmiany kodu

Dodanie nowego typu dokumentu wymaga **wyłącznie edycji**
`config/document_rules.yaml` — bez żadnych zmian w kodzie Pythona.

### Przykład: nowy typ `faktura`

1. Otwórz `config/document_rules.yaml`.
2. Dodaj nowy wpis w sekcji `document_types`:

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
                   pattern: '\b(?:numer|nr)\s+faktury[ \t]*[:.]?[ \t]*([A-Za-z0-9/.\-]+)'
                   group: 1
                   flags: [IGNORECASE]
             kwota:
               type: number
               rules:
                 - kind: regex
                   pattern: '\bkwota[ \t]*[:.]?[ \t]*([\d\s]+[.,]\d{2})'
                   group: 1
                   flags: [IGNORECASE]
   ```

3. Gotowe — silnik automatycznie:
   - rozpozna typ `faktura` po dopasowaniu wzorca klasyfikacji,
   - wyekstrahuje pola `numer` i `kwota`,
   - zwróci je jako obiekty `{value, source_text, rule_used}`.

W ten sam sposób dodaje się **nowe pola** (dopisując je do `structure`/`fields`)
oraz **nowe reguły** dla istniejących pól (dopisując je do `rules`).

---

## Zasady projektowe (zero hardcodowania)

- **Brak sztywnych nazw** dokumentów i pól w kodzie Pythona — wszystko pochodzi
  z `config/document_rules.yaml`.
- **Wzorzec Registry** — nowy `kind` reguły rejestruje się dekoratorem
  `@register`, bez zmiany istniejącego kodu.
- **Transparentność** — każde pole zwraca `{value, source_text, rule_used}`.
- **Lokalnie i open source** — CPU, bez GPU i bez zewnętrznych/płatnych API LLM.
- **Stabilne wejście/wyjście** — `./input/*.pdf` → `./output/*.json`
  z zachowaniem struktury podfolderów i nazw plików.
