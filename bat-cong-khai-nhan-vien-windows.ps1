param([switch]$ConfigureRetention)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$package = $PSScriptRoot
$pids = @(Get-NetTCPConnection -LocalPort 1521 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
$runningFolders = [System.Collections.Generic.List[string]]::new()
foreach ($pidOnPort in $pids) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$pidOnPort" -ErrorAction SilentlyContinue
    if (-not $owner -or -not $owner.CommandLine -or
        $owner.CommandLine.IndexOf('canvas_server.py', [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Cong 1521 do tien trinh $pidOnPort khac chiem. Chua thay doi gi."
    }
    # Prefer the actual quoted script path; fall back to the venv executable.
    $folder = $null
    $scriptMatch = [regex]::Match($owner.CommandLine, '(?i)"([^"\r\n]+\\canvas_server\.py)"')
    if ($scriptMatch.Success -and (Test-Path -LiteralPath $scriptMatch.Groups[1].Value)) {
        $folder = Split-Path -Parent $scriptMatch.Groups[1].Value
    } elseif ($owner.ExecutablePath) {
        $exeFolder = Split-Path -Parent $owner.ExecutablePath
        if ([string]::Equals((Split-Path -Leaf $exeFolder), 'Scripts', [StringComparison]::OrdinalIgnoreCase) -and
            [string]::Equals((Split-Path -Leaf (Split-Path -Parent $exeFolder)), '.venv', [StringComparison]::OrdinalIgnoreCase)) {
            $folder = [IO.Path]::GetFullPath((Join-Path $exeFolder '..\..'))
        }
    }
    if (-not $folder -or -not (Test-Path -LiteralPath (Join-Path $folder '.env')) -or
        -not (Test-Path -LiteralPath (Join-Path $folder 'canvas_server.py'))) {
        throw "Khong xac nhan duoc thu muc Muse cua tien trinh $pidOnPort. Chua thay doi gi."
    }
    if (-not $runningFolders.Contains($folder)) { $runningFolders.Add($folder) }
}
if ($runningFolders.Count -gt 1) { throw 'Nhieu ban Muse cung chiem cong 1521. Chua thay doi gi.' }
if ($runningFolders.Count -eq 1) {
    $target = $runningFolders[0]
    Write-Host "Da tim thay thu muc Muse DANG CHAY: $target"
} else {
    $target = $package
    if (-not (Test-Path -LiteralPath (Join-Path $target '.env'))) {
        $target = (Read-Host 'Cong 1521 dang tat. Dan THU MUC Muse co file .env').Trim('"')
    }
    $target = (Resolve-Path -LiteralPath $target).Path
}
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
& $python -m py_compile $sourceServer
if ($LASTEXITCODE -ne 0) { throw 'canvas_server.py moi khong hop le. Chua thay doi gi.' }
$settings = [ordered]@{ CANVAS_HOST = '127.0.0.1'; CANVAS_PUBLIC = '1' }
if ($ConfigureRetention) {
    Write-Host 'Anh/video trong muse2api\data\media cu hon thoi gian chon se bi XOA VINH VIEN.'
    Write-Host 'Link tai tep do se het hieu luc. Ban da tai ve may nhan vien van giu nguyen.'
    $answer = Read-Host 'Nhap so NGAY luu (vi du 1, 3, 7; nhap 0 de TAT tu xoa)'
    $days = 0
    if (-not [int]::TryParse($answer, [ref]$days) -or $days -lt 0 -or $days -gt 3650) {
        throw 'Can nhap so ngay tu 0 den 3650. Chua thay doi gi.'
    }
    $settings['CANVAS_MEDIA_RETENTION_HOURS'] = [string]($days * 24)
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item -LiteralPath $envFile -Destination (Join-Path $target ('.env.backup-public-' + $stamp))
Copy-Item -LiteralPath $targetServer -Destination (Join-Path $target ('canvas_server.backup-public-' + $stamp + '.py'))

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
if (-not [string]::Equals($sourceServer, $targetServer, [StringComparison]::OrdinalIgnoreCase)) {
    Copy-Item -LiteralPath $sourceServer -Destination $targetServer -Force
}

# Restart only the Canvas Python process in this folder. Keep Muse API,
# Cloudflare Tunnel and the user's other websites running.
foreach ($pidToStop in $pids) {
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
if ($ConfigureRetention) {
    if ($days -gt 0) {
        Write-Host "Da bat TU XOA tep cu hon $days ngay. Kiem tra moi gio khi Canvas dang chay."
    } else {
        Write-Host 'Da TAT tu dong xoa anh/video.'
    }
}
