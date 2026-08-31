from social_migrator.wizard import run_wizard


def test_wizard_persists_non_secret_state(tmp_path):
    answers = iter(["Codex", "GPT", "能", "feishu-link", "meta"])
    path = tmp_path / "state.json"
    cfg = run_wizard(input_fn=lambda _: next(answers), output_fn=lambda _: None, state_path=str(path))
    assert cfg.agent == "Codex"
    assert path.exists()
    assert "has_comfly_api_key" in path.read_text(encoding="utf-8")
    assert "feishu-link" not in path.read_text(encoding="utf-8")
