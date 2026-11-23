@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-members-windows.ps1"
if errorlevel 1 (
  echo Cap nhat chua thanh cong. Xem loi phia tren.
  pause
  exit /b 1
)
pause
