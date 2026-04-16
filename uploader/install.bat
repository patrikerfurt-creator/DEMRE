@echo off
:: Muss als Administrator ausgefuehrt werden
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Bitte als Administrator ausfuehren (Rechtsklick → Als Administrator ausfuehren)
    pause
    exit /b 1
)

echo ============================================
echo  DEMRE Datei-Uploader  –  Installation
echo ============================================
echo.

:: Abhaengigkeiten installieren
echo [1/3] Installiere Python-Pakete ...
pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo FEHLER beim Installieren der Pakete.
    pause
    exit /b 1
)

:: config.json anlegen falls nicht vorhanden
if not exist "%~dp0config.json" (
    echo.
    echo [2/3] config.json nicht gefunden – Vorlage wird geoeffnet ...
    copy "%~dp0config.json.example" "%~dp0config.json"
    notepad "%~dp0config.json"
    echo Bitte config.json speichern und dann eine beliebige Taste druecken ...
    pause >nul
) else (
    echo [2/3] config.json bereits vorhanden – wird verwendet.
)

:: Dienst installieren und starten
echo.
echo [3/3] Installiere und starte Windows-Dienst ...
python "%~dp0demre_uploader_service.py" --startup auto install
if %errorlevel% neq 0 (
    echo FEHLER beim Installieren des Dienstes.
    pause
    exit /b 1
)
python "%~dp0demre_uploader_service.py" start
if %errorlevel% neq 0 (
    echo FEHLER beim Starten des Dienstes.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Installation abgeschlossen!
echo  Der Dienst laeuft jetzt im Hintergrund
echo  und startet automatisch mit Windows.
echo.
echo  Logdatei: %~dp0uploader.log
echo ============================================
pause
