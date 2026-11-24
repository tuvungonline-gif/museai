param([string]$AdminPhone = '', [switch]$UiOnly)
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
    $scriptMatch = [regex]::Match($owner.CommandLine, '(?i)(?:^|\s)(?:"([^"\r\n]+\\canvas_server\.py)"|([a-z]:\\(?:[^"\s]*\\)?canvas_server\.py))(?=\s|$)')
    $scriptPath = $scriptMatch.Groups[1].Value + $scriptMatch.Groups[2].Value
    if ($scriptMatch.Success -and (Test-Path -LiteralPath $scriptPath)) {
        $folder = Split-Path -Parent $scriptPath
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
$python = Join-Path $target '.venv\Scripts\python.exe'
$runner = Join-Path $target 'run-canvas-windows.ps1'
$files = @('canvas_server.py', 'run-canvas-windows.ps1')
if (-not $UiOnly) { $files += @('member_auth.py', 'member_pages.py') }
foreach ($file in @($envFile, $python, $runner)) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Thieu tep: $file. Chua thay doi gi." }
}
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $package $file))) { throw "Goi cap nhat thieu $file." }
    if ($file.EndsWith('.py')) {
        & $python -m py_compile (Join-Path $package $file)
        if ($LASTEXITCODE -ne 0) { throw "Tep $file khong hop le. Chua thay doi gi." }
    }
}
$uiArchive = Join-Path $package 'account-ui.zip'
$uiInstaller = Join-Path $package 'install_account_assets.py'
$localBuildUrl = 'http://127.0.0.1:1521/ibee-build.json'
$publicBase = 'https://ms.ibeetool.com'
$expectedBuild = ''
if (Test-Path -LiteralPath $uiArchive) {
    if (-not (Test-Path -LiteralPath $uiInstaller)) { throw 'Thieu install_account_assets.py. Chua thay doi gi.' }
    $expectedBuild = & $python $uiInstaller --archive $uiArchive --root $target --check
    if ($LASTEXITCODE -ne 0 -or $expectedBuild -notmatch '^[a-f0-9]{64}$') {
        throw 'Goi giao dien khong hop le. Chua thay doi gi.'
    }
} elseif ($UiOnly) {
    throw 'Thieu account-ui.zip. Hay giai nen toan bo goi cap nhat truoc khi chay.'
}
function Get-CanvasBuild([string]$Url, [int]$Timeout = 2) {
    try {
        $status = Invoke-RestMethod -Uri $Url -UseBasicParsing -TimeoutSec $Timeout
        return $status.index_sha256
    } catch {
        return ''
    }
}
function Show-IBEEBuild {
    $shortBuild = $expectedBuild.Substring(0, 12)
    Write-Host "IBEE dang phuc vu ban $shortBuild tai cong 1521."
    $publicBuild = Get-CanvasBuild "$publicBase/ibee-build.json?v=$expectedBuild" 8
    if ($publicBuild -eq $expectedBuild) {
        Write-Host "Da xac nhan $publicBase dang phuc vu cung ban $shortBuild." -ForegroundColor Green
    } else {
        Write-Host "Ten mien chua xac nhan ban $shortBuild. Hay kiem tra dinh tuyen ve cong 1521." -ForegroundColor Yellow
    }
    Start-Process "$publicBase/video?v=$shortBuild"
}
if (-not $UiOnly) {
    $lines = [IO.File]::ReadAllLines($envFile)
    $passwordLine = @($lines | Where-Object { $_ -match '^CANVAS_ACCESS_PASSWORD=.{8,}$' })
    if ($passwordLine.Count -eq 0) { throw 'Can CANVAS_ACCESS_PASSWORD it nhat 8 ky tu trong .env. Chua thay doi gi.' }
    if (-not ($lines | Where-Object { $_ -match '^MUSE_API_KEY=.+$' })) { throw 'Thieu MUSE_API_KEY. Chua thay doi gi.' }
    if (-not $AdminPhone) {
        $savedPhone = @($lines | Where-Object { $_ -match '^CANVAS_ADMIN_PHONE=.+$' } | Select-Object -First 1)
        if ($savedPhone.Count -gt 0) { $AdminPhone = $savedPhone[0].Substring('CANVAS_ADMIN_PHONE='.Length).Trim() }
    }
    if (-not $AdminPhone) {
        $localPhone = Join-Path $package 'admin-phone.local.txt'
        if (Test-Path -LiteralPath $localPhone) { $AdminPhone = [IO.File]::ReadAllText($localPhone).Trim() }
        else { $AdminPhone = (Read-Host 'Nhap SO DIEN THOAI cua admin').Trim() }
    }
    $AdminPhone = $AdminPhone -replace '[\s().-]', ''
    if ($AdminPhone.StartsWith('+84')) { $AdminPhone = '0' + $AdminPhone.Substring(3) }
    if ($AdminPhone -notmatch '^0[35789][0-9]{8}$') { throw 'So dien thoai admin khong hop le. Chua thay doi gi.' }
}
$backup = Join-Path $target ('member-update-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup | Out-Null
if (-not $UiOnly) { Copy-Item -LiteralPath $envFile -Destination (Join-Path $backup '.env') }
foreach ($file in $files) {
    $existing = Join-Path $target $file
    if (Test-Path -LiteralPath $existing) { Copy-Item -LiteralPath $existing -Destination (Join-Path $backup $file) }
}
$database = Join-Path $target 'data\members.sqlite3'
if (-not $UiOnly -and (Test-Path -LiteralPath $database)) {
    & $python -c 'import sqlite3,sys; src=sqlite3.connect(sys.argv[1]); dst=sqlite3.connect(sys.argv[2]); src.backup(dst); dst.close(); src.close()' $database (Join-Path $backup 'members.sqlite3')
    if ($LASTEXITCODE -ne 0) { throw 'Khong sao luu duoc thanh vien. Chua thay doi gi.' }
}
# Remove old external prompt sources; keep newly added prompts on repeated updates.
if (Test-Path -LiteralPath $uiArchive) {
    & $python $uiInstaller --archive $uiArchive --root $target --backup $backup
    if ($LASTEXITCODE -ne 0) { throw 'Chua cap nhat duoc giao dien. Chua bat dang nhap thanh vien.' }
} else {
    & $python (Join-Path $package 'reset_prompt_library.py') --root $target
    if ($LASTEXITCODE -ne 0) { throw 'Chua don duoc thu vien loi nhac. Chua bat dang nhap thanh vien.' }
}
foreach ($file in $files) {
    $source = Join-Path $package $file
    $dest = Join-Path $target $file
    if (-not [string]::Equals($source,$dest,[StringComparison]::OrdinalIgnoreCase)) {
        Copy-Item -LiteralPath $source -Destination $dest -Force
    }
}
if (-not $UiOnly) {
    $settings = [ordered]@{
        CANVAS_HOST = '127.0.0.1'
        CANVAS_PUBLIC = '1'
        CANVAS_MEMBERS_ENABLED = '1'
        CANVAS_ADMIN_PHONE = $AdminPhone
    }
    $newLines = [System.Collections.Generic.List[string]]::new()
    $newLines.AddRange([string[]]$lines)
    foreach ($name in $settings.Keys) {
        $found = $false
        for ($i = 0; $i -lt $newLines.Count; $i++) {
            if ($newLines[$i] -match ('^' + [regex]::Escape($name) + '=')) {
                $newLines[$i] = "$name=$($settings[$name])"; $found = $true
            }
        }
        if (-not $found) { $newLines.Add("$name=$($settings[$name])") }
    }
    [IO.File]::WriteAllLines($envFile,$newLines,(New-Object System.Text.UTF8Encoding($false)))
}
foreach ($pidToStop in $pids) { Stop-Process -Id $pidToStop -Force }
for ($i=0; $i -lt 20; $i++) {
    if (-not (Get-NetTCPConnection -LocalPort 1521 -State Listen -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 300
}
if (Get-NetTCPConnection -LocalPort 1521 -State Listen -ErrorAction SilentlyContinue) { throw "Cong 1521 van ban. Sao luu: $backup" }
Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-NoExit','-ExecutionPolicy','Bypass','-File',('"'+$runner+'"')) -WorkingDirectory $target
$ready = $false
for ($i=0; $i -lt 40; $i++) {
    try {
        $buildReady = -not $expectedBuild -or ((Get-CanvasBuild $localBuildUrl) -eq $expectedBuild)
        if ($buildReady) {
            if ($UiOnly) { $ready=$true; break }
            $result = Invoke-RestMethod -Uri 'http://127.0.0.1:1521/member-api/me' -UseBasicParsing -TimeoutSec 2
            if ($result.members_version -eq 1) { $ready=$true; break }
        }
    } catch { }
    Start-Sleep -Milliseconds 500
}
if (-not $ready) { throw "Canvas chua xac nhan dung ban giao dien $expectedBuild. Kiem tra cua so Muse Canvas. Sao luu: $backup" }
if ($UiOnly) {
    Show-IBEEBuild
    return
}
Write-Host "Da cap nhat. ADMIN: $AdminPhone"
Write-Host 'Mat khau admin: mat khau Canvas hien co (CANVAS_ACCESS_PASSWORD trong .env).'
Write-Host 'Thanh vien dang ky moi se CHO DUYET. Admin vao /members de duyet hoac khoa.'
Write-Host 'Thu vien chung va thu vien rieng: /prompts. Khong can khoi dong lai Muse API hoac Tunnel.'
Write-Host 'Quan ly tai khoan va thong tin thanh vien: https://ms.ibeetool.com/account'
Start-Process 'https://ms.ibeetool.com/account'
