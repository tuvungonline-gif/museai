$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$package = $PSScriptRoot
$target = $package
if (-not (Test-Path -LiteralPath (Join-Path $target '.env'))) {
    $target = (Read-Host 'Dan THU MUC Muse dang chay, noi co file .env').Trim('"')
}
$target = (Resolve-Path -LiteralPath $target).Path
$envFile = Join-Path $target '.env'
$targetServer = Join-Path $target 'canvas_server.py'
$sourceServer = Join-Path $package 'canvas_server.py'
$runner = Join-Path $target 'run-canvas-windows.ps1'
$python = Join-Path $target '.venv\Scripts\python.exe'
foreach ($file in @($envFile, $targetServer, $sourceServer, $runner, $python, (Join-Path $target 'canvas\dist\index.html'))) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Thieu file: $file" }
}
$lines = [IO.File]::ReadAllLines($envFile)
if (-not ($lines | Where-Object { $_ -match '^MUSE_API_KEY=.+$' })) {
    throw 'MUSE_API_KEY trong .env dang trong. Chua thay doi gi.'
}
$key = (($lines | Where-Object { $_ -match '^MUSE_API_KEY=' } | Select-Object -First 1) -replace '^MUSE_API_KEY=', '')
# Check the replacement before touching the running installation.
& $python -c 'import ast,sys; ast.parse(open(sys.argv[1],encoding="utf-8").read())' $sourceServer
if ($LASTEXITCODE -ne 0) { throw 'canvas_server.py moi khong hop le. Chua thay doi gi.' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item -LiteralPath $envFile -Destination (Join-Path $target ('.env.backup-public-' + $stamp))
Copy-Item -LiteralPath $targetServer -Destination (Join-Path $target ('canvas_server.backup-public-' + $stamp + '.py'))

$settings = [ordered]@{ CANVAS_HOST = '127.0.0.1'; CANVAS_PUBLIC = '1' }
$newLines = [System.Collections.Generic.List[string]]::new()
$newLines.AddRange([string[]]$lines)
foreach ($name in $settings.Keys) {
    $found = $false
    for ($i = 0; $i -lt $newLines.Count; $i++) {
        if ($newLines[$i] -match ('^' + [regex]::Escape($name) + '=')) {
            $newLines[$i] = "$name=$($settings[$name])"
            $found = $true
        }
    }
    if (-not $found) { $newLines.Add("$name=$($settings[$name])") }
}
[IO.File]::WriteAllLines($envFile, $newLines, (New-Object System.Text.UTF8Encoding($false)))
Copy-Item -LiteralPath $sourceServer -Destination $targetServer -Force

# Restart only the Canvas Python process in this folder. Keep Muse API,
# Cloudflare Tunnel and the user's other websites running.
$pids = @(Get-NetTCPConnection -LocalPort 1521 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
foreach ($pidToStop in $pids) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$pidToStop" -ErrorAction SilentlyContinue
    if (-not $process -or -not $process.CommandLine -or
        $process.CommandLine.IndexOf($targetServer, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw 'Cong 1521 thuoc chuong trinh khac; khong dung tien trinh do. Hay mo lai Canvas thu cong.'
    }
    Stop-Process -Id $pidToStop -Force
}
for ($i = 0; $i -lt 20; $i++) {
    if (-not (Get-NetTCPConnection -LocalPort 1521 -State Listen -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 300
}
if (Get-NetTCPConnection -LocalPort 1521 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Cong 1521 van ban; khong khoi dong them ban sao Canvas.'
}
Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $runner + '"')) -WorkingDirectory $target
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:1521/config.js' -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200 -and $response.Content.Contains('public-canvas') -and
            -not $response.Content.Contains($key)) {
            $ready = $true
            break
        }
    } catch { }
    Start-Sleep -Milliseconds 500
}
if (-not $ready) { throw 'Canvas moi chua khoi dong an toan. Xem cua so Muse Canvas.' }
Write-Host 'Da bat trang Canvas khong can dang nhap. Khoa Muse2API chi con tren may chu.'
Write-Host 'Muse API va Cloudflare Tunnel van giu nguyen; khong thay doi cac website khac.'
Write-Host 'Moi nguoi biet ten mien deu co the dung quota Muse cua ban. Chi chia se cho nhan vien tin cay.'
