import json
import os
import subprocess


class FeishuCli:
    """Thin adapter around a locally authenticated lark-cli installation."""

    def __init__(self, executable: str = "lark-cli"):
        self.executable = executable

    def run(self, *args: str) -> dict:
        env = os.environ.copy()
        env.pop("FEISHU_BASE_TOKEN", None)
        result = subprocess.run([self.executable, *args, "--format", "json"], capture_output=True, text=True, env=env, timeout=120)
        if result.returncode:
            return {"ok": False, "returncode": result.returncode, "stderr": result.stderr[-2000:]}
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload = {"raw": result.stdout[-2000:]}
        return {"ok": True, "data": payload}

    def list_records(self, base_token: str, table_id: str) -> dict:
        if not base_token or not table_id:
            return {"ok": False, "error": "需要飞书 Base token 和表 ID"}
        return self.run("base", "+record-list", "--base-token", base_token, "--table-id", table_id)
