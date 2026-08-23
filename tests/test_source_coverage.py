from engine import validators


def test_every_entity_has_a_citation():
    problems = validators.validate_source_coverage()
    assert not problems, "\n".join(problems)
