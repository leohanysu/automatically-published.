from social_migrator.config import Config


def test_config_reads_local_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("COMFLY_API_KEY=local-test\n", encoding="utf-8")
    monkeypatch.delenv("COMFLY_API_KEY", raising=False)
    assert Config.load().comfly_api_key == "local-test"
