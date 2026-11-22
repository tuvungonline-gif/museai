$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$envFile = Join-Path $root '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    throw 'Chua co .env. Hay chay CAI-VA-CHAY-WINDOWS.cmd truoc.'
}

$lines = [System.Collections.Generic.List[string]]::new()
$lines.AddRange([string[]]([IO.File]::ReadAllLines($envFile)))
$settings = [ordered]@{
    MUSE_API_BASE = 'https://ms.ibeetool.com'
    MUSE2API_PUBLIC_BASE = 'https://ms.ibeetool.com'
}
foreach ($name in $settings.Keys) {
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match ('^' + [regex]::Escape($name) + '=')) {
            $lines[$i] = "$name=$($settings[$name])"
            $found = $true
        }
    }
    if (-not $found) { $lines.Add("$name=$($settings[$name])") }
}
$backup = Join-Path $root ('.env.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
Copy-Item -LiteralPath $envFile -Destination $backup
[IO.File]::WriteAllLines($envFile, $lines, (New-Object System.Text.UTF8Encoding($false)))
Write-Host 'Da cau hinh Muse API va media tren https://ms.ibeetool.com.'
Write-Host 'Hay dong va mo lai hai cua so Muse API, Muse Canvas de nhan cau hinh moi.'
Write-Host 'Luu y: ten mien chi hoat dong khi Cloudflare Tunnel tren may nay chay va DNS da kich hoat.'
