from social_migrator.browser_publish import BrowserPublishSession
from social_migrator.publishers.base import PublishRequest


class Lifecycle:
    def open_foreground_verified(self):
        return {"visible": True}


class Driver:
    def publish(self, platform, request):
        return {"platform": platform, "verified": True, "record_id": request.record_id}


def test_browser_session_verifies_one_publish():
    session = BrowserPublishSession(Lifecycle(), Driver())
    result = session.publish_one("youtube", PublishRequest("r1", "v.mp4", confirm=True))
    assert result["status"] == "verified"


def test_browser_session_blocks_without_confirmation():
    session = BrowserPublishSession(Lifecycle(), Driver())
    assert session.publish_one("meta", PublishRequest("r1", "v.mp4"))["status"] == "blocked"
