$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
python -m venv (Join-Path $root '.venv')
& (Join-Path $root '.venv\Scripts\python.exe') -m pip install --upgrade pip
& (Join-Path $root '.venv\Scripts\python.exe') -m pip install -e $root
if (-not (Test-Path (Join-Path $root '.env'))) { Copy-Item (Join-Path $root 'config\.env.example') (Join-Path $root '.env') }
Write-Host '安装完成。请编辑 .env，然后运行 .venv\Scripts\python.exe -m social_migrator wizard'
