@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0CAI-TUNNEL-WINDOWS.ps1"
if errorlevel 1 (
  echo Cai Tunnel chua thanh cong. Xem thong bao o cua so tren.
  pause
  exit /b 1
)
pause
