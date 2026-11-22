$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Get-Content -LiteralPath (Join-Path $root '.env') | ForEach-Object {
    if ($_ -match '^([A-Z][A-Z0-9_]*)=(.*)$') { Set-Item -Path ("Env:" + $Matches[1]) -Value $Matches[2] }
}
$env:MUSE2API_KEY = $env:MUSE_API_KEY
$env:MUSE2API_PUBLIC_BASE = $env:MUSE_API_BASE
Set-Location (Join-Path $root 'muse2api')
& (Join-Path $root '.venv\Scripts\python.exe') -m uvicorn app:app --host 127.0.0.1 --port 1314
if ($LASTEXITCODE -ne 0) { throw 'Muse API dung; kiem tra loi phia tren.' }
