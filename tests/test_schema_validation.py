from engine import validators


def test_all_data_files_validate_against_schema():
    problems = validators.validate_schemas()
    assert not problems, "\n".join(problems)
