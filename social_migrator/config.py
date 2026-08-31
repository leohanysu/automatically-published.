from dataclasses import dataclass, field
import json
import os
from pathlib import Path

from .errors import ConfigError


@dataclass
class Config:
    agent: str = ""
    model: str = ""
    native_vision: bool | None = None
    comfly_api_key: str = ""
    comfly_model: str = "gemini-3-flash-preview"
    feishu_base_token: str = ""
    adspower_profile_id: str = ""
    platforms: list[str] = field(default_factory=list)
    max_videos: int = 1

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        data: dict = {}
        if path and Path(path).exists():
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        platforms = data.get("platforms", [])
        if isinstance(platforms, str):
            platforms = [p.strip() for p in platforms.split(",") if p.strip()]
        return cls(
            agent=data.get("agent", os.getenv("SOCIAL_AGENT", "")),
            model=data.get("model", os.getenv("SOCIAL_MODEL", "")),
            native_vision=data.get("native_vision"),
            comfly_api_key=os.getenv("COMFLY_API_KEY", data.get("comfly_api_key", "")),
            comfly_model=os.getenv("COMFLY_MODEL", data.get("comfly_model", "gemini-3-flash-preview")),
            feishu_base_token=os.getenv("FEISHU_BASE_TOKEN", data.get("feishu_base_token", "")),
            adspower_profile_id=os.getenv("ADSPOWER_PROFILE_ID", data.get("adspower_profile_id", "")),
            platforms=platforms,
            max_videos=int(data.get("max_videos", 1)),
        )

    def validate(self, require_publish: bool = False) -> list[str]:
        problems = []
        if self.max_videos != 1:
            problems.append("默认每次只能处理 1 条视频")
        allowed = {"meta", "tiktok", "x", "youtube", "pinterest"}
        unknown = sorted(set(self.platforms) - allowed)
        if unknown:
            problems.append(f"不支持的平台: {', '.join(unknown)}")
        if require_publish and not self.comfly_api_key:
            problems.append("缺少 COMFLY_API_KEY")
        return problems

    def public_dict(self) -> dict:
        return {
            "agent": self.agent,
            "model": self.model,
            "native_vision": self.native_vision,
            "comfly_model": self.comfly_model,
            "has_comfly_api_key": bool(self.comfly_api_key),
            "has_feishu_base_token": bool(self.feishu_base_token),
            "has_adspower_profile": bool(self.adspower_profile_id),
            "platforms": self.platforms,
            "max_videos": self.max_videos,
        }
