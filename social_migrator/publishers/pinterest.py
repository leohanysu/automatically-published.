from .base import Publisher, PublishRequest, PublishResult


class PinterestPublisher(Publisher):
    platform = "pinterest"

    def publish(self, request: PublishRequest) -> PublishResult:
        if not request.confirm:
            return PublishResult(self.platform, "blocked", "Pinterest 需要用户明确选择后才能发布")
        return PublishResult(self.platform, "prepared", "已准备 Pinterest 发布参数", evidence={"tags": request.tags, "website": "https://www.marshkiky.com/"})
