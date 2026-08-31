from .base import Publisher, PublishRequest, PublishResult


class YouTubePublisher(Publisher):
    platform = "youtube"

    def prepare_metadata(self, request: PublishRequest) -> dict:
        return {
            "title": request.title,
            "description": request.description,
            "made_for_kids": False,
            "audience_label": "不是面向儿童",
        }

    def publish(self, request: PublishRequest) -> PublishResult:
        if not request.confirm:
            return PublishResult(self.platform, "blocked", "需要用户明确确认后才能发布")
        metadata = self.prepare_metadata(request)
        return PublishResult(self.platform, "prepared", "已准备 YouTube 发布参数，明确设置为不是面向儿童", evidence=metadata)
