from engine import validators


def test_every_bone_reference_resolves():
    problems = validators.validate_bone_references()
    assert not problems, "\n".join(problems)
