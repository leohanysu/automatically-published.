from social_migrator.platforms import validate_selection


def test_pinterest_requires_opt_in():
    assert validate_selection(["pinterest"]) == ["pinterest 需要用户明确选择"]
    assert validate_selection(["pinterest"], {"pinterest"}) == []


def test_unknown_platform_is_rejected():
    assert validate_selection(["reddit"])[0].startswith("不支持")
