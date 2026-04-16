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
echo [1/4] Installiere Python-Pakete ...
pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo FEHLER beim Installieren der Pakete.
    pause
    exit /b 1
)

:: config.json anlegen falls nicht vorhanden
if not exist "%~dp0config.json" (
    echo.
    echo [2/4] config.json nicht gefunden – Vorlage wird geoeffnet ...
    copy "%~dp0config.json.example" "%~dp0config.json"
    notepad "%~dp0config.json"
    echo Bitte config.json speichern und dann eine beliebige Taste druecken ...
    pause >nul
) else (
    echo [2/4] config.json bereits vorhanden – wird verwendet.
)

:: Windows-Benutzerkonto abfragen
:: Der Dienst muss unter einem echten Benutzerkonto laufen,
:: damit er auf Netzwerkordner (\\server\freigabe) zugreifen kann.
echo.
echo [3/4] Windows-Benutzerkonto fuer den Dienst
echo     (Der Dienst benoetigt ein Benutzerkonto mit Zugriff auf die Netzwerkordner)
echo.
set /p WIN_USER="Windows-Benutzername (z.B. maurer oder DOMAIN\maurer): "
set /p WIN_PASS="Windows-Passwort: "
echo.

:: Dienst installieren
echo [4/4] Installiere und starte Windows-Dienst ...
python "%~dp0demre_uploader_service.py" --startup auto --username "%WIN_USER%" --password "%WIN_PASS%" install
if %errorlevel% neq 0 (
    echo FEHLER beim Installieren des Dienstes.
    pause
    exit /b 1
)
python "%~dp0demre_uploader_service.py" start
if %errorlevel% neq 0 (
    echo FEHLER beim Starten des Dienstes.
    echo Bitte uploader.log pruefen: %~dp0uploader.log
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
