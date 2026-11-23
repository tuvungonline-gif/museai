@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0cap-nhat-tieng-viet-windows.ps1"
if errorlevel 1 (
  echo Cap nhat chua thanh cong. Xem loi o phia tren.
  pause
  exit /b 1
)
pause
