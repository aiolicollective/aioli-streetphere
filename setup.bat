@echo off
:: Always work from the folder this script sits in (run as admin,
:: from another terminal folder, via a shortcut...).
cd /d "%~dp0"
:: ============================================================
::  setup.bat  --  Virtual environment installer
::
::  Looks for Python automatically. If it cannot be found,
::  asks the user for the path.
::  Nothing is modified outside the current folder.
:: ============================================================

echo.
echo ============================================================
echo   Street View Panorama Downloader  ^|  Setup
echo ============================================================
echo.

:: -- 3D module requirements, checked FIRST --------------------
::  Deliberately before pip: if pip fails, this script stops, and
::  a check placed at the end would never be shown. Node.js being
::  missing is not a reason to stop the install -- option [1]
::  works without it -- so this only warns.
echo  [i] The 3D module (menu options [2] and [3]) needs Node.js and Git.
echo      The 360 sphere and the satellite image (options [1] and [4])
echo      do NOT need them.
echo.
node --version >nul 2>&1
if errorlevel 1 (
    echo      [!!] Node.js  NOT FOUND  -  install it from https://nodejs.org
    set MISSING_3D=1
) else (
    echo      [OK] Node.js
)
git --version >nul 2>&1
if errorlevel 1 (
    echo      [!!] Git      NOT FOUND  -  install it from https://git-scm.com
    set MISSING_3D=1
) else (
    echo      [OK] Git
)
echo.
if defined MISSING_3D (
    echo      Install what is marked NOT FOUND, then close and reopen this
    echo      window so the new programs are picked up. Setup continues now:
    echo      the 360 sphere will work either way.
    echo.
)

:: -- If the venv already exists, go straight to pip ----------
if exist venv\Scripts\python.exe (
    echo  [INFO] venv already present, updating the dependencies...
    echo.
    goto :install_deps
)

:: -- Automatic Python lookup -----------------------------
set PYTHON_CMD=

:: 1. Windows launcher (py)
py --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=py& goto :found_python )

:: 2. python in the PATH
python --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=python& goto :found_python )

:: 3. python3 in the PATH
python3 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=python3& goto :found_python )

:: 4. Common paths
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

:: -- Python not found: ask for the path -----------------------
echo  [!] Python could not be found automatically.
echo.
echo  Enter the full path to python.exe
echo  Example: D:\Python\Python312\python.exe
echo.
set /p PYTHON_CMD="  Path > "

:: Check that the given path is valid
if not exist "%PYTHON_CMD%" (
    echo.
    echo  [ERROR] File not found: %PYTHON_CMD%
    echo  Check the path and run setup.bat again.
    pause
    exit /b 1
)

:found_python
:: -- Show the version found -------------------------------
for /f "delims=" %%V in ('"%PYTHON_CMD%" --version 2^>^&1') do set PY_VERSION=%%V
echo  [OK] Python detected : %PYTHON_CMD%
echo       Version         : %PY_VERSION%
echo.
echo  *** Note this path down for your other machines: ***
echo  *** %PYTHON_CMD% ***
echo.

:: -- Create the venv ----------------------------------
echo  [1/3] Creating the venv in .\venv\ ...
"%PYTHON_CMD%" -m venv venv
if errorlevel 1 (
    echo  [ERROR] Could not create the venv.
    pause
    exit /b 1
)
echo  [OK] venv created.
echo.

:: -- Install the dependencies -----------------------------
:install_deps
echo  [2/3] Installing requests + Pillow + numpy...
call venv\Scripts\activate.bat
for /f "delims=" %%V in ('python --version 2^>^&1') do set VENV_PY=%%V
echo       venv is using: %VENV_PY%
echo.
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [ERROR] pip could not install the dependencies.
    echo.
    echo  Two usual causes:
    echo    1. No Internet connection, or a proxy / firewall blocking pip.
    echo    2. Your Python is too new: a library has no ready-made package yet
    echo       and pip tried to compile it. The log above then mentions
    echo       "building wheel" and a 46 MB Pillow .tar.gz.
    echo.
    echo  Fix for case 2 -- install Python 3.12 from
    echo  https://www.python.org/downloads/ -- tick "Add Python to PATH" --
    echo  then DELETE the venv folder sitting next to this script
    echo  and run setup.bat again.
    echo.
    pause
    exit /b 1
)
echo  [OK] Dependencies installed.
echo.

:: -- Done -------------------------------------------
echo  [3/3] Installation complete.
echo.
if defined MISSING_3D (
    echo  Reminder: Node.js and/or Git are still missing, so the 3D menu
    echo  options [2] and [3] will refuse to start. Options [1] and [4] are ready.
    echo.
)
echo  To use the tool: double-click streetphere.bat
echo    [1] 360 sphere   [2] 3D environment   [3] Both   [4] Satellite image
echo.
set LAUNCH=
set /p LAUNCH="  Open the menu now? [Enter = yes / n] > "
if /i "%LAUNCH%"=="n" goto :end
call streetphere.bat
exit /b 0

:end
echo.
pause
