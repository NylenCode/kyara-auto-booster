@echo off
rem Installe tout ce qu'il faut, une seule fois par ordinateur : Python, les
rem outils Python (requirements.txt) et Tesseract. Ce qui est déjà là est gardé.
rem Installs everything needed, once per computer. What is already there is kept.
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Kyara Auto Booster - installation

echo.
echo ============================================================
echo   KYARA AUTO BOOSTER - installation
echo ============================================================
echo   Installe ce qui manque : Python, outils Python, Tesseract.
echo   Installs what is missing: Python, Python tools, Tesseract.
echo.

rem ---------- 1. Python ----------
call :trouver_python
if defined PY goto python_ok
call :winget_requis || goto erreur
echo [1/3] Installation de Python / Installing Python...
winget install -e --id Python.Python.3.13 --scope user --silent --accept-package-agreements --accept-source-agreements
call :trouver_python
if defined PY goto python_ok
echo.
echo   Python n'a pas pu être installé. / Python could not be installed.
echo   Installe-le à la main / Install it by hand: https://www.python.org/downloads/
echo   (coche / tick "Add python.exe to PATH")
goto erreur
:python_ok
echo [1/3] Python : OK

rem ---------- 2. Outils Python / Python tools ----------
echo [2/3] Outils Python / Python tools...
"%PY%" -m ensurepip >nul 2>&1
"%PY%" -m pip install --disable-pip-version-check --quiet -r requirements.txt
if errorlevel 1 goto erreur_pip
echo [2/3] Outils Python / Python tools : OK

rem ---------- 3. Tesseract (lecture du texte / reads the text) ----------
set "TESSERACT=C:\Program Files\Tesseract-OCR\tesseract.exe"
if exist "%TESSERACT%" goto tesseract_ok
call :winget_requis || goto erreur
echo [3/3] Installation de Tesseract / Installing Tesseract...
echo       Windows va demander l'autorisation : clique sur Oui.
echo       Windows will ask for permission: click Yes.
winget install -e --id UB-Mannheim.TesseractOCR --silent --accept-package-agreements --accept-source-agreements
if exist "%TESSERACT%" goto tesseract_ok
echo.
echo   Tesseract n'a pas pu être installé. / Tesseract could not be installed.
echo   Installe-le à la main, sans changer le dossier proposé :
echo   Install it by hand, keeping the folder offered:
echo   https://github.com/UB-Mannheim/tesseract/wiki
goto erreur
:tesseract_ok
echo [3/3] Tesseract : OK

rem ---------- Vérification / Check ----------
"%PY%" -c "import pyautogui, pytesseract, mss, PIL" >nul 2>&1
if errorlevel 1 goto erreur_pip

echo.
echo ============================================================
echo   Tout est installé ! / Everything is installed!
echo ============================================================
echo   Ensuite / Next:  configure.bat  (réglages / setup)
echo                    run.bat        (lancer / start)
echo.
choice /c ONY /n /m "Ouvrir l'assistant maintenant ? / Open the assistant now? [O/Y = oui/yes, N = non/no] "
if errorlevel 3 goto assistant
if errorlevel 2 goto fin
:assistant
"%PY%" configure.py
:fin
echo.
pause
exit /b 0

:erreur_pip
echo.
echo   Les outils Python n'ont pas pu être installés (connexion Internet ?).
echo   The Python tools could not be installed (Internet connection?).
:erreur
echo.
echo   Installation incomplète : relance install.bat après avoir corrigé.
echo   Installation not finished: run install.bat again once fixed.
echo.
pause
exit /b 1


rem Python 3.10 ou plus récent / or newer : py, python, puis le dossier
rem d'installation par défaut (juste installé, pas encore dans le PATH).
:trouver_python
set "PY="
call :essayer_python py
if not defined PY call :essayer_python python
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :essayer_python "%%D\python.exe"
exit /b 0

:essayer_python
if defined PY exit /b 0
"%~1" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
exit /b 0

:winget_requis
where winget >nul 2>&1 && exit /b 0
echo.
echo   winget introuvable : installe "Programme d'installation d'application"
echo   (App Installer) depuis le Microsoft Store, puis relance install.bat.
echo   winget not found: install "App Installer" from the Microsoft Store,
echo   then run install.bat again.
exit /b 1
