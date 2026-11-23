@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bat-cong-khai-nhan-vien-windows.ps1"
if errorlevel 1 (
  echo Cap nhat chua thanh cong. Xem loi phia tren.
  pause
  exit /b 1
)
echo Xong. Mo https://ms.ibeetool.com/ bang trinh duyet rieng de kiem tra.
pause
