#!/usr/bin/env sh
# ODWOŁANIA2JSON — przetwarzanie wsadowe: ./input/*.pdf -> ./output/*.json
# (odpowiednik start.bat dla systemów Linux/macOS)

set -e
cd "$(dirname "$0")"

# 1) Znajdź Pythona 3.
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "[BLAD] Nie znaleziono Pythona 3. Zainstaluj Python 3.13+." >&2
    exit 1
fi

# 2) Zainstaluj zależności (idempotentne).
"$PYTHON" -m pip install -r requirements.txt --quiet --disable-pip-version-check 2>/dev/null || true

# 3) Uruchom przetwarzanie.
exec "$PYTHON" src/main.py "$@"
