@echo off
:: ============================================================
::  run.bat  —  Lance le script dans le venv (apres setup)
:: ============================================================
call venv\Scripts\activate.bat
python streetview.py
echo.
pause
