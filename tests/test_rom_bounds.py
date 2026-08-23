from engine import validators


def test_joint_rom_ranges_are_physiologically_plausible():
    problems = validators.validate_rom_bounds()
    assert not problems, "\n".join(problems)
