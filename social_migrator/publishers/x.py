from .base import Publisher, PublishRequest, PublishResult


class XPublisher(Publisher):
    platform = "x"

    def publish(self, request: PublishRequest) -> PublishResult:
        if not request.confirm:
            return PublishResult(self.platform, "blocked", "需要用户明确确认后才能发布")
        return PublishResult(self.platform, "prepared", "已准备 X 直接发布入口，等待浏览器适配器执行")
