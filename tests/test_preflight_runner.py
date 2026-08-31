from social_migrator.config import Config
from social_migrator.preflight import preflight_dict
from social_migrator.runner import plan_run


def test_preflight_reports_missing_comfly():
    result = preflight_dict(Config())
    assert result["ok"] is False
    assert any(c["name"] == "Comfly 配置" and not c["ok"] for c in result["checks"])


def test_plan_run_deduplicates_platforms(tmp_path):
    result = plan_run(["meta", "meta", "youtube"], "r1", str(tmp_path / "runs"))
    assert result["platforms"] == ["meta", "youtube"]
