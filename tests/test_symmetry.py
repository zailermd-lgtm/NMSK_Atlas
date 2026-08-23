from engine import validators


def test_bilateral_entities_have_mirror_counterparts():
    problems = validators.validate_symmetry()
    assert not problems, "\n".join(problems)
