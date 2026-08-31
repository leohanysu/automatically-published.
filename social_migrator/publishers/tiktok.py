from .base import Publisher, PublishRequest, PublishResult


class TikTokPublisher(Publisher):
    platform = "tiktok"

    def publish(self, request: PublishRequest) -> PublishResult:
        if not request.confirm:
            return PublishResult(self.platform, "blocked", "需要用户明确确认后才能发布")
        return PublishResult(self.platform, "prepared", "已保留现有 TikTok 发布流程入口，等待浏览器适配器执行")
