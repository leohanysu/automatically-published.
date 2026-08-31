from dataclasses import dataclass, asdict
from .config import Config
from .feishu import check_permissions


@dataclass
class Check:
    name: str
    ok: bool
    message: str


def run_preflight(config: Config, granted_feishu_permissions: set[str] | None = None) -> list[Check]:
    checks = [Check("单视频限制", config.max_videos == 1, "默认每次只处理一条视频")]
    checks.append(Check("平台范围", not config.validate(), "平台配置可识别" if not config.validate() else "; ".join(config.validate())))
    checks.append(Check("Comfly 配置", bool(config.comfly_api_key), "已配置 Comfly" if config.comfly_api_key else "缺少 COMFLY_API_KEY"))
    if granted_feishu_permissions is not None:
        perm = check_permissions(granted_feishu_permissions)
        checks.append(Check("飞书权限", perm["ok"], "权限齐全" if perm["ok"] else "缺少: " + ", ".join(perm["missing"])))
    return checks


def preflight_dict(config: Config, granted_feishu_permissions: set[str] | None = None) -> dict:
    checks = run_preflight(config, granted_feishu_permissions)
    return {"ok": all(c.ok for c in checks), "checks": [asdict(c) for c in checks]}
