$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $args = @('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $args
    exit 0
}

$service = Get-Service -Name 'cloudflared' -ErrorAction SilentlyContinue
if ($service) {
    Write-Host 'May nay da co cloudflared service. Khong cai de tranh anh huong Tunnel dang chay.'
    Write-Host ('Trang thai hien tai: ' + $service.Status)
    Read-Host 'Nhan Enter de thoat'
    exit 1
}

Write-Host 'CAI TUNNEL museai-ms-ibeetool CHO MAY WINDOWS NAY'
Write-Host 'Vao Cloudflare > Tunnels > museai-ms-ibeetool > Add a replica > Windows.'
Write-Host 'Chi dan TOKEN vao cua so nay. Khong gui token qua chat hoac GitHub.'
$secret = Read-Host 'Dan Tunnel token va nhan Enter' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    $secret.Dispose()
}
if ([string]::IsNullOrWhiteSpace($token) -or $token.Length -lt 80 -or $token -match '\s') {
    throw 'Token khong hop le. Chi dan token, khong dan ca lenh cloudflared service install.'
}

$folder = Join-Path $env:ProgramFiles 'Cloudflare\cloudflared'
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$binary = Join-Path $folder 'cloudflared.exe'
if (-not (Test-Path -LiteralPath $binary)) {
    $url = 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'
    $tempBinary = Join-Path $folder 'cloudflared.download.exe'
    try {
        Write-Host 'Dang tai cloudflared Windows tu Cloudflare GitHub...'
        Invoke-WebRequest -Uri $url -OutFile $tempBinary -UseBasicParsing
        if ((Get-Item -LiteralPath $tempBinary).Length -lt 1000000) {
            throw 'Tep tai ve khong dung kich thuoc, da huy cai dat.'
        }
        Move-Item -LiteralPath $tempBinary -Destination $binary -Force
    } finally {
        Remove-Item -LiteralPath $tempBinary -Force -ErrorAction SilentlyContinue
    }
}
& $binary --version
if ($LASTEXITCODE -ne 0) { throw 'Khong chay duoc cloudflared.' }
Write-Host 'Dang cai Windows service...'
try {
    & $binary service install $token
    if ($LASTEXITCODE -ne 0) { throw ('Cai service that bai, ma ' + $LASTEXITCODE) }
} finally {
    $token = $null
}
$service = Get-Service -Name 'cloudflared' -ErrorAction Stop
if ($service.Status -ne 'Running') {
    Start-Service -Name 'cloudflared'
    $service.WaitForStatus('Running', (New-TimeSpan -Seconds 30))
}
Write-Host 'cloudflared service dang Running. Cho Cloudflare bao Tunnel Healthy.'
Read-Host 'Nhan Enter de dong'
