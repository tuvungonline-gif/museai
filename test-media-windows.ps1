$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$settings = @{}
Get-Content -LiteralPath (Join-Path $root '.env') | ForEach-Object {
    if ($_ -match '^([A-Z][A-Z0-9_]*)=(.*)$') { $settings[$Matches[1]] = $Matches[2] }
}
$key = $settings['MUSE_API_KEY']
if (-not $key) { throw 'Chua co MUSE_API_KEY trong .env. Chay CAI-VA-CHAY-WINDOWS.cmd truoc.' }
$base = 'http://127.0.0.1:1314'
$headers = @{ Authorization = "Bearer $key" }
$status = Invoke-RestMethod -Uri "$base/readyz" -TimeoutSec 10
if ([int]$status.accounts -lt 1) { throw 'Chua co tai khoan Muse. Nhap phien muse.ai tai trang quan tri truoc khi test.' }
$outputDir = Join-Path $root 'test-output'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

Write-Host '1/2 Dang tao anh mau bang tai khoan muse.ai cua ban...'
$imageBody = @{
    model = 'muse-image'
    prompt = 'A single grape vine in a pot, green leaves and purple grape clusters, natural morning light, realistic photo, no text'
    size = '9:16'
    response_format = 'b64_json'
} | ConvertTo-Json -Compress
$imageResult = Invoke-RestMethod -Uri "$base/v1/images/generations" -Method Post -Headers $headers -ContentType 'application/json' -Body $imageBody -TimeoutSec 600
$imageB64 = $imageResult.data[0].b64_json
if (-not $imageB64) { throw 'Muse chua tra du lieu anh b64_json. Kiem tra loi trong cua so Muse API.' }
$imageBytes = [Convert]::FromBase64String($imageB64)
$imageMime = ''
$extension = ''
if ($imageBytes.Length -gt 12 -and $imageBytes[0] -eq 137 -and $imageBytes[1] -eq 80) {
    $imageMime = 'image/png'; $extension = 'png'
} elseif ($imageBytes.Length -gt 12 -and $imageBytes[0] -eq 255 -and $imageBytes[1] -eq 216) {
    $imageMime = 'image/jpeg'; $extension = 'jpg'
} elseif ($imageBytes.Length -gt 12 -and [Text.Encoding]::ASCII.GetString($imageBytes, 8, 4) -eq 'WEBP') {
    $imageMime = 'image/webp'; $extension = 'webp'
} else { throw 'Anh Muse tra ve khong phai PNG, JPG hoac WebP hop le.' }
$imagePath = Join-Path $outputDir "muse-test-image.$extension"
[IO.File]::WriteAllBytes($imagePath, $imageBytes)
Write-Host "Anh tao thanh cong: $imagePath"

Write-Host '2/2 Dang dung anh vua tao de yeu cau video mau...'
$videoBody = @{
    prompt = 'Slow handheld camera push-in toward the grape vine; leaves gently move in a light breeze, natural realistic motion, no text, vertical video'
    duration = 5
    size = '9:16'
    images = @(@{ url = "data:$imageMime;base64,$imageB64" })
} | ConvertTo-Json -Depth 5 -Compress
$videoTask = Invoke-RestMethod -Uri "$base/v1/videos" -Method Post -Headers $headers -ContentType 'application/json' -Body $videoBody -TimeoutSec 120
if (-not $videoTask.id) { throw 'Muse chua tao video task; xem cua so Muse API.' }
Write-Host "Video task ID: $($videoTask.id)"
$deadline = (Get-Date).AddMinutes(15)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    $task = Invoke-RestMethod -Uri "$base/v1/videos/$($videoTask.id)" -Headers $headers -TimeoutSec 30
    Write-Host "Trang thai: $($task.status)"
    if ($task.status -in @('succeeded', 'completed')) { break }
    if ($task.status -in @('failed', 'error', 'cancelled', 'canceled')) { throw "Muse tao video that bai: $($task.error | ConvertTo-Json -Compress)" }
}
if ($task.status -notin @('succeeded', 'completed') -or -not $task.result.url) {
    throw "Qua 15 phut chua nhan duoc video. Giu lai task ID $($videoTask.id) de kiem tra; khong gui lai de tranh tru credit."
}
$videoPath = Join-Path $outputDir 'muse-test-video.mp4'
Invoke-WebRequest -Uri $task.result.url -Headers $headers -OutFile $videoPath -UseBasicParsing -TimeoutSec 120
$videoBytes = [IO.File]::ReadAllBytes($videoPath)
if ($videoBytes.Length -lt 32 -or [Text.Encoding]::ASCII.GetString($videoBytes, 4, 4) -ne 'ftyp') {
    throw 'File video tai ve khong co MP4 header hop le. Kiem tra task va link tai.'
}
Write-Host "THANH CONG: Anh $imagePath va video $videoPath"
