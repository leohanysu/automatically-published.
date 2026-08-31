from pathlib import Path
from .evidence import write_json


def checkpoint(run_dir: str | Path, platform: str, record_id: str, status: str, **details) -> Path:
    path = Path(run_dir) / f"{platform}-{record_id}.json"
    write_json(path, {"platform": platform, "record_id": record_id, "status": status, **details})
    return path


def resume_candidates(run_dir: str | Path) -> list[dict]:
    import json
    result = []
    for path in Path(run_dir).glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("status") not in {"verified", "published"}:
            result.append(data)
    return result
