$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$package = $PSScriptRoot
$target = $package
if (-not (Test-Path -LiteralPath (Join-Path $target '.env'))) {
    $target = (Read-Host 'Dan duong dan THU MUC Muse dang chay, noi co file .env').Trim('"')
}
$targetIndex = Join-Path $target 'canvas\dist\index.html'
$sourceIndex = Join-Path $package 'canvas\dist\index.html'
if (-not (Test-Path -LiteralPath (Join-Path $target '.env')) -or -not (Test-Path -LiteralPath $targetIndex)) {
    throw 'Khong tim thay .env va canvas\dist\index.html trong thu muc Muse dang chay.'
}
if (-not (Test-Path -LiteralPath $sourceIndex)) { throw 'Goi cap nhat thieu canvas\dist\index.html.' }
$sourceAssets = Join-Path $package 'canvas\dist\assets'
$targetAssets = Join-Path $target 'canvas\dist\assets'
$files = @('index-B-iW99V2.js', 'index-Bm6gxf5k.css', 'highlighted-body-KQOG7T2V-DQ41jpVp.js')
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceAssets $file))) {
        throw "Goi cap nhat thieu $file. Hay tai lai ZIP moi nhat."
    }
}
New-Item -ItemType Directory -Path $targetAssets -Force | Out-Null
$backup = Join-Path $target ('canvas-index-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.html')
Copy-Item -LiteralPath $targetIndex -Destination $backup
foreach ($file in $files) {
    $dest = Join-Path $targetAssets $file
    if (-not (Test-Path -LiteralPath $dest)) {
        Copy-Item -LiteralPath (Join-Path $sourceAssets $file) -Destination $dest
    }
}
# Chi chuyen index sau khi moi tai nguyen moi da san sang.
$tempIndex = "$targetIndex.new"
Copy-Item -LiteralPath $sourceIndex -Destination $tempIndex -Force
Move-Item -LiteralPath $tempIndex -Destination $targetIndex -Force
Write-Host 'Da cap nhat giao dien Canvas tieng Viet. .env, Muse API va du lieu khong thay doi.'
Write-Host 'Tai lai trang Canvas bang Ctrl+F5 de nhan giao dien moi.'
Write-Host "Da sao luu index cu tai $backup"
