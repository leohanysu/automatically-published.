#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -e "$ROOT"
if [ ! -f "$ROOT/.env" ]; then cp "$ROOT/config/.env.example" "$ROOT/.env"; fi
echo '安装完成。请编辑 .env，然后运行 .venv/bin/python -m social_migrator wizard'
