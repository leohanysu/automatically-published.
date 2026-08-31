$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$version = (Get-Content (Join-Path $root 'VERSION') -Raw).Trim()
$zip = Join-Path (Split-Path $root -Parent) ("social-publishing-migrator-$version.zip")
if (-not (Test-Path $zip)) { throw "找不到分发包，请先运行 build_migration_package.ps1" }
$entries = tar -tf $zip
$forbidden = $entries | Where-Object { $_ -match '(^|/)(\.git|\.venv|logs|state|backups|\.pytest_cache)(/|$)|(^|/)\.env$|\.(mp4|mov|webm|mkv)$' }
if ($forbidden) { throw "分发包包含禁止内容: $($forbidden -join ', ')" }
$hash = (Get-FileHash -Algorithm SHA256 $zip).Hash
Write-Output "release: $zip"
Write-Output "sha256: $hash"
Write-Output "entries: $($entries.Count)"
Write-Output 'release verification: clean'
