import argparse
import json

from .config import Config
from .evidence import new_run, write_json
from .media_router import route_media
from .preflight import preflight_dict
from .wizard import run_wizard


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="social-migrator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("wizard")
    pre = sub.add_parser("preflight")
    pre.add_argument("--config")
    pub = sub.add_parser("publish")
    pub.add_argument("--platform", required=True)
    pub.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "wizard":
        cfg = run_wizard()
        print(json.dumps(cfg.public_dict(), ensure_ascii=False, indent=2))
        return 0
    cfg = Config.load(getattr(args, "config", None))
    if args.command == "preflight":
        result = preflight_dict(cfg)
        result.update({"config": cfg.public_dict(), "video_route": route_media("video", cfg.native_vision).__dict__})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 2
    if args.command == "publish":
        if not args.confirm:
            print(json.dumps({"ok": False, "error": "需要明确确认：请加 --confirm；默认只发布 1 条"}, ensure_ascii=False))
            return 3
        run = new_run()
        write_json(run / "checkpoint.json", {"platform": args.platform, "status": "pending", "max_videos": 1})
        print(json.dumps({"ok": False, "run_id": run.name, "error": "发布器尚未接入；预检和证据目录已建立，未发布视频"}, ensure_ascii=False))
        return 4
    return 1
