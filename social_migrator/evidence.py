from datetime import datetime, timezone
import json
from pathlib import Path

from .redact import redact


def new_run(root: str | Path = "state/runs") -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(root) / run_id
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_json(path: str | Path, value) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(redact(value), ensure_ascii=False, indent=2), encoding="utf-8")
