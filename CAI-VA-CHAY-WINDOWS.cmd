@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-windows.ps1"
if errorlevel 1 (
  echo Cai dat that bai. Xem loi o phia tren.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0wait-for-services.ps1" -Quick
if not errorlevel 1 goto ready
start "Muse API" powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0run-api-windows.ps1"
start "Muse Canvas" powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0run-canvas-windows.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0wait-for-services.ps1"
if errorlevel 1 (
  echo Khong mo trang vi Muse API hoac Muse Canvas chua chay.
  echo Hay chup anh HAI cua so Muse API va Muse Canvas de toi xem loi.
  pause
  exit /b 1
)
:ready
start "" "http://127.0.0.1:521/"
echo Muse Canvas: http://127.0.0.1:521/
echo Giu hai cua so Muse API va Muse Canvas dang mo trong luc su dung.
pause
