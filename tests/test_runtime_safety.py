from social_migrator.comfly import ComflyClient
from social_migrator.evidence import new_run
from social_migrator.recovery import checkpoint, resume_candidates


def test_comfly_requires_environment_key(monkeypatch):
    monkeypatch.delenv("COMFLY_API_KEY", raising=False)
    try:
        ComflyClient().analyze_video("demo.mp4")
    except ValueError as exc:
        assert "COMFLY_API_KEY" in str(exc)
    else:
        raise AssertionError("missing key must block analysis")


def test_checkpoints_can_resume(tmp_path):
    run = new_run(tmp_path / "runs")
    checkpoint(run, "youtube", "r1", "failed", message="timeout")
    checkpoint(run, "meta", "r1", "verified")
    assert len(resume_candidates(run)) == 1
