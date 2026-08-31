from .evidence import new_run
from .recovery import checkpoint


def plan_run(platforms: list[str], record_id: str, run_root: str = "state/runs") -> dict:
    platforms = list(dict.fromkeys(platforms))
    run_dir = new_run(run_root)
    for platform in platforms:
        checkpoint(run_dir, platform, record_id, "pending")
    return {"run_id": run_dir.name, "run_dir": str(run_dir), "platforms": platforms, "record_id": record_id, "max_videos": 1}
