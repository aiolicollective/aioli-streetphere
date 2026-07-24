@echo off
:: ============================================================
::  run.bat  —  aioli-streetphere : menu de lancement
::  [1] Sphere 360 (streetview, requiert setup.bat une fois)
::  [2] Environnement 3D a l'echelle (earth3d)
::  [3] Les deux depuis la meme URL (requiert setup.bat)
:: ============================================================

:: ── Detection Python (meme logique que setup.bat) ──────────
set PYTHON_CMD=
if exist venv\Scripts\python.exe ( set PYTHON_CMD=venv\Scripts\python.exe& goto :menu )
py --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=py& goto :menu )
python --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=python& goto :menu )
for %%P in (
    "D:\Python\Python312\python.exe"
    "D:\Python\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) do (
    if exist %%P ( set PYTHON_CMD=%%~P& goto :menu )
)
echo.
echo  [!] Python introuvable automatiquement.
echo  Lancez setup.bat une fois (il demande le chemin et cree le venv),
echo  ce menu le detectera ensuite tout seul.
echo.
pause
exit /b 1

:menu
echo.
echo ============================================================
echo   aioli-streetphere
echo ============================================================
echo.
echo   [1] Sphere 360 equirectangulaire (streetview)
echo   [2] Environnement 3D a l'echelle (earth3d)
echo   [3] Les deux depuis la meme URL
echo   [Q] Quitter
echo.
set CHOICE=
set /p CHOICE="  Choix > "
if /i "%CHOICE%"=="1" goto :sphere
if /i "%CHOICE%"=="2" goto :earth3d
if /i "%CHOICE%"=="3" goto :both
if /i "%CHOICE%"=="q" exit /b 0
goto :menu

:sphere
if not exist venv\Scripts\python.exe (
    echo.
    echo  [!] La sphere 360 requiert le venv : lancez setup.bat d'abord.
    goto :menu
)
call venv\Scripts\activate.bat
python streetview.py
goto :menu

:earth3d
"%PYTHON_CMD%" earth3d.py
goto :menu

:both
if not exist venv\Scripts\python.exe (
    echo.
    echo  [!] Le mode combine requiert le venv : lancez setup.bat d'abord.
    goto :menu
)
call venv\Scripts\activate.bat
python both.py
goto :menu
