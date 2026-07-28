@echo off
:: ============================================================
::  streetphere.bat  --  aioli-streetphere : launcher menu
::  [1] 360 sphere (streetview, needs setup.bat once)
::  [2] True-to-scale 3D environment (earth3d)
::  [3] Both from the same URL (needs setup.bat)
:: ============================================================

:: -- Python detection (same logic as setup.bat) --------------
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
echo  [!] Python could not be found automatically.
echo  Run setup.bat once (it asks for the path and creates the venv),
echo  this menu will then detect it on its own.
echo.
pause
exit /b 1

:menu
if not defined AIOLI_BANNER call :intro
echo.
echo   ------------------------------------------------------------
echo.
echo   [1] Equirectangular 360 sphere (streetview)
echo   [2] True-to-scale 3D environment (earth3d)
echo   [3] Both from the same URL
echo   [Q] Quit
echo.
set CHOICE=
set /p CHOICE="  Choice > "
if /i "%CHOICE%"=="1" goto :sphere
if /i "%CHOICE%"=="2" goto :earth3d
if /i "%CHOICE%"=="3" goto :both
if /i "%CHOICE%"=="q" exit /b 0
goto :menu

:sphere
if not exist venv\Scripts\python.exe (
    echo.
    echo  [!] The 360 sphere needs the venv: run setup.bat first.
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
    echo  [!] The combined mode needs the venv: run setup.bat first.
    goto :menu
)
call venv\Scripts\activate.bat
python both.py
goto :menu

:: ------------------------------------------------------------
::  Intro screen: shown only once per run.
::  AIOLI_BANNER is inherited by the Python scripts, which then
::  stay quiet so the logo is not repeated.
:: ------------------------------------------------------------
:intro
cls
"%PYTHON_CMD%" banner.py
if errorlevel 1 (
    echo.
    echo   ^> ai.oli/   aiolicollective.com   github.com/aiolicollective
    echo.
)
set AIOLI_BANNER=1
goto :eof
