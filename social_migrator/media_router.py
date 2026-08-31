from dataclasses import dataclass


@dataclass(frozen=True)
class MediaRoute:
    media_type: str
    provider: str
    reason: str


def route_media(media_type: str, native_vision: bool | None) -> MediaRoute:
    if media_type.lower() == "video":
        return MediaRoute("video", "comfly-gemini", "视频分析统一走 Comfly Gemini")
    if native_vision is True:
        return MediaRoute("image", "agent-native", "当前模型已确认具备图片理解能力")
    return MediaRoute("image", "comfly-gemini", "模型无视觉能力或能力不确定，回退到 Comfly Gemini")
