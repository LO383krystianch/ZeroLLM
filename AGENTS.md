# Zasady projektu ODWOŁANIA2JSON (OBOWIĄZKOWE)

## Wymagania techniczne
- Język: wyłącznie Python 3.13+.
- Wszystkie zewnętrzne zależności muszą być dopisywane do `requirements.txt` i instalowalne przez `pip`.
- Wyłącznie komponenty open source, uruchomienie lokalne na CPU **bez GPU** i **bez zewnętrznych płatnych/chmurowych API LLM**.
- Zachowaj prosty punkt wejścia CLI (`run.bat` oraz moduł CLI w Pythonie) obok aplikacji FastAPI.
- Schematy dokumentów i reguły ekstrakcji/klasyfikacji trzymaj w plikach konfiguracyjnych w `config/`, aby nowe typy dokumentów i pola można było dodawać bez zmiany głównego kodu.
- Zwracaj wynik zgodny ze schematem JSON dla danego typu dokumentu oraz dołączaj informacje o transparentności ekstrakcji (np. fragment tekstu źródłowego, dopasowana reguła).

## Zasady Git (OBOWIĄZKOWE PO KAŻDYM ZADANIU)
1. Sprawdź `git status`. Nigdy nie commituj `.env`, `*.db`, `*.sqlite*`, `__pycache__/`, `.venv/`, `venv/`, `node_modules/`.
2. Pobierz zmiany: `git pull --rebase origin HEAD` (w razie konfliktu poza swoim folderem rozwiąż zachowując zmiany z `origin`).
3. Wykonaj `git add .`, `git commit -m "feat: ..."` (lub `fix: ...`, `chore: ...`) i `git push origin HEAD`.
4. Nigdy nie używaj `git push --force`. 
## Architektura i Rozbudowa (KRYTYCZNE) 
- **Zero hardcodowania:** Nie wpisuj na sztywno nazw dokumentow ani pol do kodu Pythona. 
- **Sterowanie konfiguracja:** Dodanie nowego typu dokumentu lub pola ma wymagac wylacznie edycji pliku np. config/document_types.yaml. 
- **Interfejsy:** Kod glowny ma dynamicznie ladowac reguly z konfiguracji (wzorzec Registry). 
- **Transparentnosc:** Kazde pole musi zwracac obiekt: value, source_text, rule_used, aby mozna to bylo wyswietlic w UI. 
