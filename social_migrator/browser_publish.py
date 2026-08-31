from dataclasses import dataclass
from .adspower import AdsPowerLifecycle
from .publishers import PublishRequest
from .platforms import POLICIES


@dataclass
class BrowserPublishSession:
    lifecycle: AdsPowerLifecycle
    page_driver: object

    def publish_one(self, platform: str, request: PublishRequest) -> dict:
        policy = POLICIES.get(platform)
        if policy is None:
            raise ValueError(f"不支持的平台: {platform}")
        if not request.confirm:
            return {"platform": platform, "status": "blocked", "message": "需要明确确认"}
        self.lifecycle.open_foreground_verified()
        result = self.page_driver.publish(platform, request)
        if not result.get("verified"):
            return {"platform": platform, "status": "failed", "message": "页面未能确认发布结果", "evidence": result}
        return {"platform": platform, "status": "verified", "evidence": result}
