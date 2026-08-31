$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$version = (Get-Content (Join-Path $root 'VERSION') -Raw).Trim()
$out = Join-Path (Split-Path $root -Parent) ("social-publishing-migrator-$version.zip")
if (Test-Path $out) { Remove-Item -LiteralPath $out -Force }
$stage = Join-Path ([System.IO.Path]::GetTempPath()) ("social-migrator-stage-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage -Force | Out-Null
try {
  $items = Get-ChildItem -LiteralPath $root -Force | Where-Object { $_.Name -notin @('.git','.venv','backups','logs','state','__pycache__','.pytest_cache','tmp_download_0823') }
  Copy-Item -Path $items.FullName -Destination $stage -Recurse -Force
  Get-ChildItem -LiteralPath $stage -Recurse -File -Force | Where-Object {
    $_.Name -in @('.env') -or $_.Extension -in @('.mp4','.mov','.webm','.mkv') -or $_.FullName -match '\\(__pycache__|\.pytest_cache|logs|state|backups|tmp_download_0823)\\'
  } | Remove-Item -Force
  Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $out -CompressionLevel Optimal
} finally {
  if (Test-Path $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
Write-Host "created $out"
