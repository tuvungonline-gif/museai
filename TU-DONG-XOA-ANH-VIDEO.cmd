@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bat-cong-khai-nhan-vien-windows.ps1" -ConfigureRetention
if errorlevel 1 (
  echo Chua cau hinh duoc tu xoa. Xem loi phia tren.
  pause
  exit /b 1
)
echo Da cau hinh thoi gian luu anh/video.
pause
