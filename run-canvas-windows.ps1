$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location -LiteralPath $root
Get-Content -LiteralPath (Join-Path $root '.env') -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^([A-Z][A-Z0-9_]*)=(.*)$') { Set-Item -Path ("Env:" + $Matches[1]) -Value $Matches[2] }
}
& (Join-Path $root '.venv\Scripts\python.exe') (Join-Path $root 'canvas_server.py')
if ($LASTEXITCODE -ne 0) { throw 'Muse Canvas dung; kiem tra loi phia tren.' }
