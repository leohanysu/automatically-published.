from social_migrator.config import Config
from social_migrator.media_router import route_media


def test_video_always_uses_comfly():
    assert route_media("video", True).provider == "comfly-gemini"


def test_uncertain_image_falls_back_to_comfly():
    assert route_media("image", None).provider == "comfly-gemini"


def test_default_is_one_video():
    assert Config().max_videos == 1
