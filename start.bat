@echo off
setlocal

rem Uruchamia przetwarzanie wsadowe: ./input/*.pdf -> ./output/*.json
rem przez Python 3.13 (z fallbackiem na `python`).

set "PYTHON=py -3.13"
where py >nul 2>nul
if errorlevel 1 (
    set "PYTHON=python"
)

%PYTHON% "%~dp0src\main.py" %*
