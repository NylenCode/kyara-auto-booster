@echo off
rem Lance le programme dans la langue choisie (double-clic).
rem Un 2e navigateur, depuis un terminal / A 2nd browser, from a terminal:  run.bat brave
rem Starts the program in the language chosen (double-click).
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Kyara Auto Booster
call :trouver_python
if not defined PY goto sans_python
"%PY%" start.py %*
echo.
pause
exit /b 0

:sans_python
echo Python introuvable : lance d'abord install.bat.
echo Python not found: run install.bat first.
pause
exit /b 1


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
