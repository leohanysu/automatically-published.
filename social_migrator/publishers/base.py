from dataclasses import dataclass, field


@dataclass
class PublishRequest:
    record_id: str
    video_path: str
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    confirm: bool = False


@dataclass
class PublishResult:
    platform: str
    status: str
    message: str
    external_url: str | None = None
    evidence: dict = field(default_factory=dict)


class Publisher:
    platform = "unknown"

    def preflight(self) -> PublishResult:
        return PublishResult(self.platform, "ready", "发布器已准备")

    def publish(self, request: PublishRequest) -> PublishResult:
        if not request.confirm:
            return PublishResult(self.platform, "blocked", "需要用户明确确认后才能发布")
        raise NotImplementedError
