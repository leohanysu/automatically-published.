from social_migrator.feishu import check_permissions, load_manifest, verify_schema
from social_migrator.publishers.base import PublishRequest
from social_migrator.publishers.pinterest import PinterestPublisher
from social_migrator.publishers.youtube import YouTubePublisher


def test_feishu_manifest_is_structure_only():
    manifest = load_manifest()
    assert manifest["copy_mode"] == "structure_only"
    assert "credentials" in manifest["excluded_data"]


def test_feishu_permission_check():
    assert check_permissions({"base.read"})["ok"] is False


def test_youtube_not_for_kids_is_forced():
    req = PublishRequest("r1", "video.mp4", confirm=True)
    assert YouTubePublisher().publish(req).evidence["made_for_kids"] is False


def test_pinterest_requires_explicit_confirmation():
    req = PublishRequest("r1", "video.mp4", confirm=False)
    assert PinterestPublisher().publish(req).status == "blocked"
