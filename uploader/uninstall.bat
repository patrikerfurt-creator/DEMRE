@echo off
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Bitte als Administrator ausfuehren (Rechtsklick → Als Administrator ausfuehren)
    pause
    exit /b 1
)

echo ============================================
echo  DEMRE Datei-Uploader  –  Deinstallation
echo ============================================
echo.
python "%~dp0demre_uploader_service.py" stop
python "%~dp0demre_uploader_service.py" remove
echo.
echo Dienst wurde entfernt.
pause
