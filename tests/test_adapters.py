from social_migrator.legacy import command_for, run_legacy


def test_legacy_meta_command_points_to_verified_script():
    command = command_for("meta", "record-1")
    assert command[-2].endswith("meta_publish_v2.py")
    assert command[-1] == "record-1"


def test_legacy_dry_run_never_executes():
    result = run_legacy("tiktok", "record-1", dry_run=True)
    assert result["status"] == "planned"
