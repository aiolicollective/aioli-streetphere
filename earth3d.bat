@echo off
:: ============================================================
::  earth3d.bat  —  Google Earth 3D -> OBJ a l'echelle (v0)
::
::  Prerequis : Node.js + Git dans le PATH.
::  Python : detecte automatiquement (meme logique que setup.bat).
::  Aucune dependance pip -- le venv est optionnel.
:: ============================================================

set PYTHON_CMD=

:: 1. venv du projet (cree par setup.bat)
if exist venv\Scripts\python.exe ( set PYTHON_CMD=venv\Scripts\python.exe& goto :run )

:: 2. Lanceur Windows (py)
py --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=py& goto :run )

:: 3. python dans le PATH
python --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=python& goto :run )

:: 4. Chemins courants
for %%P in (
    "D:\Python\Python312\python.exe"
    "D:\Python\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) do (
    if exist %%P ( set PYTHON_CMD=%%~P& goto :run )
)

:: 5. Python non trouve : demander le chemin
echo  [!] Python introuvable automatiquement.
echo.
echo  Entrez le chemin complet vers python.exe
echo  Exemple : D:\Python\Python312\python.exe
echo  (ou lancez setup.bat une fois : il cree le venv local,
echo   detecte ensuite automatiquement par ce script)
echo.
set /p PYTHON_CMD="  Chemin > "
if not exist "%PYTHON_CMD%" (
    echo.
    echo  [ERREUR] Fichier introuvable : %PYTHON_CMD%
    pause
    exit /b 1
)

:run
"%PYTHON_CMD%" earth3d.py
echo.
pause
