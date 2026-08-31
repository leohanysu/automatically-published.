from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformPolicy:
    name: str
    explicit_opt_in: bool
    direct_publish: bool
    notes: str


POLICIES = {
    "meta": PlatformPolicy("meta", False, True, "沿用已验证的 Meta 流程"),
    "tiktok": PlatformPolicy("tiktok", False, True, "沿用已验证的 TikTok 流程"),
    "x": PlatformPolicy("x", False, True, "发布前必须完成登录态预检"),
    "youtube": PlatformPolicy("youtube", False, True, "必须选择不是面向儿童"),
    "pinterest": PlatformPolicy("pinterest", True, True, "只有用户明确选择时才发布；使用网站和默认标签"),
}


def validate_selection(platforms: list[str], explicit: set[str] | None = None) -> list[str]:
    explicit = explicit or set()
    errors = []
    for platform in platforms:
        if platform not in POLICIES:
            errors.append(f"不支持的平台: {platform}")
        elif POLICIES[platform].explicit_opt_in and platform not in explicit:
            errors.append(f"{platform} 需要用户明确选择")
    return errors
