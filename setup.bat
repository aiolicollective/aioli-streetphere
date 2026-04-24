@echo off
:: ============================================================
::  setup.bat  —  Installation de l'environnement virtuel
::
::  Cherche Python automatiquement. Si introuvable, demande
::  le chemin a l'utilisateur.
::  Rien n'est modifie en dehors du dossier courant.
:: ============================================================

echo.
echo ============================================================
echo   Street View Panorama Downloader  ^|  Setup
echo ============================================================
echo.

:: ── Si le venv existe deja, passer directement a pip ────────
if exist venv\Scripts\python.exe (
    echo  [INFO] venv deja present, mise a jour des dependances...
    echo.
    goto :install_deps
)

:: ── Recherche automatique de Python ─────────────────────────
set PYTHON_CMD=

:: 1. Lanceur Windows (py)
py --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=py& goto :found_python )

:: 2. python dans le PATH
python --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=python& goto :found_python )

:: 3. python3 dans le PATH
python3 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=python3& goto :found_python )

:: 4. Chemins courants
for %%P in (
    "D:\Python\Python312\python.exe"
    "D:\Python\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) do (
    if exist %%P ( set PYTHON_CMD=%%P & goto :found_python )
)

:: ── Python non trouve : demander le chemin ───────────────────
echo  [!] Python introuvable automatiquement.
echo.
echo  Entrez le chemin complet vers python.exe
echo  Exemple : D:\Python\Python312\python.exe
echo.
set /p PYTHON_CMD="  Chemin > "

:: Verifier que le chemin entre est valide
if not exist "%PYTHON_CMD%" (
    echo.
    echo  [ERREUR] Fichier introuvable : %PYTHON_CMD%
    echo  Verifiez le chemin et relancez setup.bat.
    pause
    exit /b 1
)

:found_python
:: ── Afficher la version trouvee ──────────────────────────────
for /f "delims=" %%V in ('"%PYTHON_CMD%" --version 2^>^&1') do set PY_VERSION=%%V
echo  [OK] Python detecte : %PYTHON_CMD%
echo       Version        : %PY_VERSION%
echo.
echo  *** Notez ce chemin pour vos autres machines : ***
echo  *** %PYTHON_CMD% ***
echo.

:: ── Creer le venv ────────────────────────────────────────────
echo  [1/3] Creation du venv dans .\venv\ ...
"%PYTHON_CMD%" -m venv venv
if errorlevel 1 (
    echo  [ERREUR] Impossible de creer le venv.
    pause
    exit /b 1
)
echo  [OK] venv cree.
echo.

:: ── Installer les dependances ────────────────────────────────
:install_deps
echo  [2/3] Installation de requests + Pillow...
call venv\Scripts\activate.bat
pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERREUR] Echec pip. Verifiez votre connexion Internet.
    pause
    exit /b 1
)
echo  [OK] Dependances installees.
echo.

:: ── Lancement ────────────────────────────────────────────────
echo  [3/3] Lancement de streetview.py...
echo.
python streetview.py

echo.
pause
