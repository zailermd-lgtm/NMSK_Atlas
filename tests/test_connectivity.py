import json
from pathlib import Path
from collections import defaultdict

from engine.nerve_tree import NerveTree
from engine.vascular_tree import VascularTree
from engine.validators import DATA_DIR


def _load_all(dirname):
    records = []
    for path in (DATA_DIR / dirname).glob("*.json"):
        payload = json.loads(path.read_text())
        records.extend(payload if isinstance(payload, list) else [payload])
    return records


def test_nerve_trees_are_fully_connected():
    records = _load_all("nerves")
    by_plexus = defaultdict(list)
    for r in records:
        if "plexus" in r:
            by_plexus[r["plexus"]].append(r)
    assert by_plexus, "no nerve branch records found under data/nerves/"
    problems = []
    for plexus, recs in by_plexus.items():
        tree = NerveTree(recs)
        problems.extend(f"[{plexus}] {p}" for p in tree.validate_connectivity())
    assert not problems, "\n".join(problems)


def test_vascular_trees_are_fully_connected():
    records = _load_all("vascular")
    by_tree = defaultdict(list)
    for r in records:
        if "tree_name" in r:
            by_tree[r["tree_name"]].append(r)
    assert by_tree, "no vessel branch records found under data/vascular/"
    problems = []
    for tree_name, recs in by_tree.items():
        tree = VascularTree(recs)
        problems.extend(f"[{tree_name}] {p}" for p in tree.validate_connectivity())
    assert not problems, "\n".join(problems)
