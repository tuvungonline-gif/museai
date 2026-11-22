param([switch] $Quick)
$deadline = (Get-Date).AddSeconds($(if ($Quick) { 0 } else { 45 }))
function Test-LocalPort([int] $port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect('127.0.0.1', $port, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(1200)) { return $false }
        $client.EndConnect($pending)
        return $true
    } catch { return $false }
    finally { $client.Close() }
}
do {
    $api = Test-LocalPort 1314
    $canvas = Test-LocalPort 1521
    if ($api -and $canvas) {
        Write-Host 'Muse API (1314) va Muse Canvas (1521) dang chay.'
        exit 0
    }
    if ($Quick) { break }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)
Write-Host "Chua san sang: API 1314=$api; Canvas 1521=$canvas. Xem loi trong hai cua so chuong trinh."
exit 1
