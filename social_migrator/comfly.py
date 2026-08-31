from dataclasses import dataclass
import os
from urllib import request


@dataclass
class ComflyClient:
    api_key: str | None = None
    model: str = "gemini-3-flash-preview"
    base_url: str = "https://ai.comfly.org/v1"

    def __post_init__(self):
        self.api_key = self.api_key or os.getenv("COMFLY_API_KEY", "")
        self.model = os.getenv("COMFLY_MODEL", self.model)

    def analyze_video(self, video_path: str) -> dict:
        if not self.api_key:
            raise ValueError("缺少 COMFLY_API_KEY；奶团不会把密钥写入项目")
        return {"model": self.model, "media": video_path, "status": "ready_for_api_adapter"}

    def analyze_image(self, image_path: str) -> dict:
        if not self.api_key:
            raise ValueError("缺少 COMFLY_API_KEY；请在本地 .env 中配置")
        return {"model": self.model, "media": image_path, "status": "ready_for_api_adapter"}
