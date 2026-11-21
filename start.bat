@echo off
setlocal

rem ============================================================
rem ODWOŁANIA2JSON — przetwarzanie wsadowe: ./input/*.pdf -> ./output/*.json
rem (punkt wejścia pod automatyczną ocenę)
rem ============================================================

rem 1) Znajdź Pythona (preferuj 3.13, fallback na `python`).
set "PYTHON=py -3.13"
where py >nul 2>nul
if errorlevel 1 (
    set "PYTHON=python"
)

rem 2) Zainstaluj zależności (idempotentne — pomija już zainstalowane).
%PYTHON% -m pip install -r "%~dp0requirements.txt" --quiet --disable-pip-version-check 2>nul

rem 3) Uruchom przetwarzanie.
%PYTHON% "%~dp0src\main.py" %*
