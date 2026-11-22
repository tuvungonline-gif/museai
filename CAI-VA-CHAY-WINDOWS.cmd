@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-windows.ps1"
if errorlevel 1 (
  echo Cai dat that bai. Xem loi o phia tren.
  pause
  exit /b 1
)
start "Muse API" powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0run-api-windows.ps1"
start "Muse Canvas" powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0run-canvas-windows.ps1"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:521/"
echo Muse Canvas: http://127.0.0.1:521/
echo Giu hai cua so Muse API va Muse Canvas dang mo trong luc su dung.
pause
