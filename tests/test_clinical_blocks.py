"""The owner's clinical reference block (`clinical`, see docs/DATA_MODEL.md):
every entry must carry his citations, and every trigger point and test
inside it must name its source."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "muscles"


def _muscles_with_clinical():
    for path in sorted(DATA.glob("*/*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(rec, dict) and "clinical" in rec:
            yield path, rec


def test_clinical_blocks_exist():
    assert any(_muscles_with_clinical()), "no muscle record carries a clinical block"


def test_every_clinical_entry_has_sources_and_caveat():
    problems = []
    for path, rec in _muscles_with_clinical():
        assert isinstance(rec["clinical"], list), path
        for entry in rec["clinical"]:
            if not entry.get("sources"):
                problems.append(f"{path}: {entry.get('document')} has empty sources")
            if not entry.get("caveat"):
                problems.append(f"{path}: {entry.get('document')} has no caveat")
            if not entry.get("document") or not entry.get("compiled_by"):
                problems.append(f"{path}: entry missing document/compiled_by")
    assert not problems, "\n".join(problems)


def test_every_trigger_point_and_test_carries_a_source():
    problems = []
    for path, rec in _muscles_with_clinical():
        for entry in rec["clinical"]:
            for tp in entry.get("trigger_points", []):
                if not tp.get("source") or not tp.get("referred_pain"):
                    problems.append(f"{path}: trigger point without source/referred_pain")
            for t in entry.get("tests", []):
                if not t.get("source") or not t.get("name"):
                    problems.append(f"{path}: test {t.get('name')!r} without source")
                for k in ("sensitivity", "specificity"):
                    v = t.get(k)
                    if v is not None and not (isinstance(v, (int, float)) and 0 <= v <= 100):
                        problems.append(f"{path}: test {t['name']!r} {k}={v!r} not a percent or null")
    assert not problems, "\n".join(problems)


def test_clinical_block_identical_on_both_sides():
    seen = {}
    for path, rec in _muscles_with_clinical():
        base = rec["id"].rsplit("_", 1)[0]
        seen.setdefault(base, []).append((path, rec["clinical"]))
    problems = [base for base, sides in seen.items()
                if len(sides) != 2 or sides[0][1] != sides[1][1]]
    assert not problems, f"clinical block differs between sides or one side missing: {problems}"
