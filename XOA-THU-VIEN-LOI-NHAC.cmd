@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0xoa-thu-vien-loi-nhac.ps1"
if errorlevel 1 (
  echo Chua xoa duoc thu vien. Xem loi phia tren.
  pause
  exit /b 1
)
pause
