$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = $PSScriptRoot
$upstreamSha = '46d217189d13aeee690b6211f8a87674d70e4536'
$python = Get-Command py -ErrorAction SilentlyContinue
$pythonArgs = @('-3')
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    $pythonArgs = @()
}
if (-not $python) { throw 'Can cai Python 3.10+ va chon Add Python to PATH.' }
$version = & $python.Source @pythonArgs -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)'
if ($LASTEXITCODE -ne 0 -or [int]$version -lt 310) { throw 'Can Python 3.10 hoac moi hon.' }

if (-not (Test-Path -LiteralPath (Join-Path $root 'muse2api\app.py')) -or
    -not (Test-Path -LiteralPath (Join-Path $root 'canvas\dist\index.html')) -or
    -not (Test-Path -LiteralPath (Join-Path $root 'muse2api\requirements.txt'))) {
    $temp = Join-Path ([IO.Path]::GetTempPath()) ("muse-canvas-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temp | Out-Null
    try {
        $zip = Join-Path $temp 'source.zip'
        $url = "https://github.com/huwanbin/Muse-Canvas/archive/$upstreamSha.zip"
        Write-Host 'Dang tai ma Muse-Canvas dung phien ban da kiem tra...'
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
        Expand-Archive -LiteralPath $zip -DestinationPath $temp
        $source = Join-Path $temp "Muse-Canvas-$upstreamSha"
        if (-not (Test-Path -LiteralPath (Join-Path $source 'muse2api\app.py'))) {
            throw 'Goi tai ve thieu ma muse2api; khong tiep tuc cai.'
        }
        $prefixLength = $source.TrimEnd('\', '/').Length + 1
        Get-ChildItem -LiteralPath $source -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($prefixLength)
            $destination = Join-Path $root $relative
            if (-not (Test-Path -LiteralPath $destination)) {
                $parent = Split-Path -Parent $destination
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
                Copy-Item -LiteralPath $_.FullName -Destination $destination
            }
        }
    } finally {
        Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $python.Source @pythonArgs -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Khong tao duoc Python venv.' }
}
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $root 'muse2api\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Cai thu vien Python that bai.' }

$envFile = Join-Path $root '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $keyBytes = New-Object byte[] 32
        $passwordBytes = New-Object byte[] 24
        $rng.GetBytes($keyBytes)
        $rng.GetBytes($passwordBytes)
    } finally { $rng.Dispose() }
    $key = ([BitConverter]::ToString($keyBytes)).Replace('-', '').ToLowerInvariant()
    $password = [Convert]::ToBase64String($passwordBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    $lines = @(
        'MUSE_API_BASE=http://127.0.0.1:1314',
        "MUSE_API_KEY=$key",
        'MUSE2API_HOST=127.0.0.1',
        'MUSE2API_PORT=1314',
        'CANVAS_HOST=127.0.0.1',
        'CANVAS_PORT=1521',
        'CANVAS_ACCESS_USER=admin',
        "CANVAS_ACCESS_PASSWORD=$password",
        'DEEPSEEK_API_KEY='
    )
    [IO.File]::WriteAllText($envFile, ($lines -join "`r`n") + "`r`n", (New-Object System.Text.UTF8Encoding($false)))
    Write-Host 'Tai khoan canvas: admin'
    Write-Host "Mat khau canvas: $password"
    Write-Host "Trang them tai khoan Muse: http://127.0.0.1:1314/admin?key=$key"
} else {
    $existing = [IO.File]::ReadAllText($envFile)
    $migrated = [Text.RegularExpressions.Regex]::Replace($existing, '(?m)^CANVAS_PORT=521\r?$', 'CANVAS_PORT=1521')
    if ($migrated -ne $existing) {
        [IO.File]::WriteAllText($envFile, $migrated, (New-Object System.Text.UTF8Encoding($false)))
        Write-Host 'Da chuyen cong canvas 521 sang 1521, giu nguyen cac khoa dang nhap.'
    }
    Write-Host 'Giu nguyen .env hien co. Xem CANVAS_ACCESS_PASSWORD trong file .env neu can dang nhap.'
}
$uiArchive = Join-Path $root 'account-ui.zip'
if (Test-Path -LiteralPath $uiArchive) {
    & $venvPython (Join-Path $root 'install_account_assets.py') --archive $uiArchive --root $root
    if ($LASTEXITCODE -ne 0) { throw 'Cai goi giao dien IBEE that bai.' }
}
Write-Host 'Da cai xong. Mo http://127.0.0.1:1521/ sau khi hai cua so may chu khoi dong.'
