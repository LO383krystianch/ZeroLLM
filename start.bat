@echo off
setlocal

rem Uruchamia przetwarzanie wsadowe: ./input/*.pdf -> ./output/*.json
python "%~dp0src\main.py" %*
