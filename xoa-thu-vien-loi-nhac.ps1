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
$python = Join-Path $target '.venv\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'reset_prompt_library.py'
if (-not (Test-Path -LiteralPath $python)) { throw 'Khong tim thay Python cua Muse.' }
& $python $script --root $target
if ($LASTEXITCODE -ne 0) { throw 'Chua cap nhat duoc thu vien loi nhac.' }
