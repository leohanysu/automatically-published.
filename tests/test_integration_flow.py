import json
from social_migrator.config import Config
from social_migrator.evidence import new_run, write_json
from social_migrator.preflight import preflight_dict
from social_migrator.publishers.youtube import YouTubePublisher
from social_migrator.publishers.base import PublishRequest
from social_migrator.recovery import checkpoint, resume_candidates


def test_first_run_preflight_publish_evidence_and_resume(tmp_path):
    cfg = Config(comfly_api_key="test-key", platforms=["youtube"])
    assert preflight_dict(cfg)["ok"]
    run = new_run(tmp_path / "runs")
    req = PublishRequest("record-1", "demo.mp4", confirm=True)
    result = YouTubePublisher().publish(req)
    checkpoint(run, "youtube", "record-1", result.status, evidence=result.evidence)
    write_json(run / "summary.json", {"status": result.status})
    assert json.loads((run / "youtube-record-1.json").read_text(encoding="utf-8"))["evidence"]["made_for_kids"] is False
    assert resume_candidates(run)[0]["status"] == "prepared"
