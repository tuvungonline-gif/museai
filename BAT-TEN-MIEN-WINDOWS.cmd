@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-domain-windows.ps1"
if errorlevel 1 (
  echo Cau hinh ten mien that bai. Xem loi phia tren.
  pause
  exit /b 1
)
echo Da cau hinh. Dong hai cua so Muse API va Muse Canvas cu, sau do chay CAI-VA-CHAY-WINDOWS.cmd.
pause
