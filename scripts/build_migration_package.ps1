$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$version = (Get-Content (Join-Path $root 'VERSION') -Raw).Trim()
$out = Join-Path (Split-Path $root -Parent) ("social-publishing-migrator-$version.zip")
if (Test-Path $out) { Remove-Item -LiteralPath $out -Force }
$items = Get-ChildItem -LiteralPath $root -Force | Where-Object { $_.Name -notin @('.git','.venv','backups','logs','state','__pycache__') }
Compress-Archive -Path $items.FullName -DestinationPath $out -CompressionLevel Optimal
Write-Host "created $out"
