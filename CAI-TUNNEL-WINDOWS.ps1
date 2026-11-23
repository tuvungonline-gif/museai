$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $args = @('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $args
    exit 0
}

$serviceName = 'cloudflared-museai-ms'
$service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($service) {
    Write-Host 'Tunnel Muse da duoc cai tren may nay. Khong ghi de service.'
    Write-Host ('Trang thai hien tai: ' + $service.Status)
    Read-Host 'Nhan Enter de thoat'
    exit 0
}
$otherService = Get-Service -Name 'cloudflared' -ErrorAction SilentlyContinue
if ($otherService) {
    Write-Host 'Da phat hien cloudflared service dang dung cho ung dung khac.'
    Write-Host 'Se tao service cloudflared-museai-ms rieng, giu nguyen service cu.'
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
    $commandLine = '"' + $binary + '" tunnel --no-autoupdate run --token ' + $token
    New-Service -Name $serviceName -BinaryPathName $commandLine -DisplayName 'Cloudflare Tunnel - Muse ms.ibeetool.com' -StartupType Automatic | Out-Null
} finally {
    $token = $null
}
$service = Get-Service -Name $serviceName -ErrorAction Stop
if ($service.Status -ne 'Running') {
    Start-Service -Name $serviceName
    $service.WaitForStatus('Running', (New-TimeSpan -Seconds 30))
}
Write-Host 'cloudflared-museai-ms dang Running. Service cloudflared cu duoc giu nguyen.'
Read-Host 'Nhan Enter de dong'
