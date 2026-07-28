@echo off
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
echo  [2/3] Installing requests + Pillow...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] pip failed. Check your Internet connection.
    pause
    exit /b 1
)
echo  [OK] Dependencies installed.
echo.

:: -- Optional modules ----------------------------------
echo  [i] 3D module (streetphere.bat option 2): Node.js + Git required
node --version >nul 2>&1 && ( echo      Node.js : OK ) || ( echo      Node.js : missing -- https://nodejs.org )
git --version >nul 2>&1 && ( echo      Git     : OK ) || ( echo      Git     : missing -- https://git-scm.com )
echo.

:: -- Done -------------------------------------------
echo  [3/3] Installation complete.
echo.
echo  To use the tool: double-click streetphere.bat
echo    [1] 360 sphere   [2] 3D environment   [3] Both
echo.
set LAUNCH=
set /p LAUNCH="  Open the menu now? [Enter = yes / n] > "
if /i "%LAUNCH%"=="n" goto :end
call streetphere.bat
exit /b 0

:end
echo.
pause
