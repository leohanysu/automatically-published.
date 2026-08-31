from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
LEGACY = {
    "meta": ROOT / "scripts" / "meta_publish_v2.py",
    "tiktok": ROOT / "scripts" / "tk_v10.py",
}


def command_for(platform: str, record_id: str) -> list[str]:
    script = LEGACY.get(platform)
    if not script or not script.exists():
        raise ValueError(f"没有找到 {platform} 的已验证脚本")
    return [sys.executable, str(script), record_id]


def run_legacy(platform: str, record_id: str, dry_run: bool = True) -> dict:
    command = command_for(platform, record_id)
    if dry_run:
        return {"platform": platform, "status": "planned", "command": command}
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=900)
    return {"platform": platform, "status": "ok" if completed.returncode == 0 else "failed", "returncode": completed.returncode, "stdout": completed.stdout[-2000:], "stderr": completed.stderr[-2000:]}
