@echo off
setlocal

rem Uruchamia src/cli.py przez Python 3.13.
rem Przyklad: run.bat --input dokument.pdf --output wynik.json

set "PYTHON=py -3.13"
where py >nul 2>nul
if errorlevel 1 (
    set "PYTHON=python"
)

%PYTHON% "%~dp0src\cli.py" %*
