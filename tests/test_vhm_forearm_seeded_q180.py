"""scripts/cryo/vhm_forearm_seeded_q180.py (Q180): pure helpers, the seed table, and the shipped outputs when present
(each output-dependent test skips cleanly when its file is absent)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "cryo"))
import vhm_forearm_seeded_q180 as S  # noqa: E402

SEEDS = REPO / "data/derived/Q180_forearm_seeds.json"
PAGE = REPO / "data/derived/Q180_forearm_seeds_page.json"
REPORT = REPO / "data/derived/Q180_vhm_forearm_seeded.json"
MAPPING = REPO / "mappings/subjects/ct_vhm_forearm_seeded_volume_mapping.json"
MANIFEST = REPO / "build/vh/ct_vhm_forearm_seeded/manifest.json"


def test_dice():
    a = np.zeros((4, 4), bool); a[:2] = True; b = np.zeros((4, 4), bool); b[1:3] = True
    assert S.dice(a, a) == 1.0 and abs(S.dice(a, b) - 0.5) < 1e-9 and S.dice(a & False, b & False) == 1.0


def test_seed_table_is_one_per_muscle_per_section_and_within_expected():
    for L, rows in S.SEED_TABLE.items():
        names = [r[0] for r in rows]
        assert len(names) == len(set(names)), L
        for nm, x, y, conf, why in rows:
            assert nm in S.ABBR and why
            assert (x is None) == (conf is None)
            assert conf in (None, "h", "m", "l")


def test_plane_watershed_is_bounded_by_septum_lines():
    musc = np.ones((1, 30, 30), bool); lines = np.zeros_like(musc); lines[0, :, 15] = True   # closed wall
    E = np.zeros(musc.shape, np.float32); E[lines] = 1.0
    sec = {"frame_index_i": 0, "maps": {"pixel_to_frame_index": [[0, 0, 0], [0, 1, 0], [1, 0, 0], [0, 0, 1]]}}
    seeds = [{"section": "L1", "muscle": "supinator_r", "x": 5.0, "y": 5.0}]
    out, moved = S.plane_labels(seeds, {"L1": sec}, {"supinator": 7}, musc, E, lines, compactness=0.0)
    lab = out[0]
    assert (lab[:, :15] == 7).all() and (lab[:, 15:] == 0).all() and not moved


@pytest.mark.skipif(not SEEDS.exists(), reason="Q180 seeds not written")
def test_seeds_file_badge_and_coordinates():
    d = json.loads(SEEDS.read_text())
    assert S.BADGE in d["_README"][0] and d["source"]
    placed = [e for e in d["seeds"] if e["status"] == "placed"]
    assert placed and all(e["tissue_class_at_seed"] == "muscle" for e in placed)
    assert all(len(e["atlas_mm"]) == 3 and e["by"] == "claude" for e in placed)
    assert d["summary"]["placed"] == len(placed)


@pytest.mark.skipif(not PAGE.exists(), reason="Q180 page store file not written")
def test_page_store_shape():
    d = json.loads(PAGE.read_text())
    assert d["collection"] == "seeds"
    for k, v in d["docs"].items():
        L, aid = k.split("__")
        assert v["section"] == L and v["muscle"] == aid and v["by"] == "claude" and v["t"]
        assert v["status"] in ("placed", "absent")
        if v["status"] == "placed":
            assert isinstance(v["x"], (int, float)) and isinstance(v["y"], (int, float))


@pytest.mark.skipif(not (REPORT.exists() and MAPPING.exists()), reason="Q180 report/mapping not written")
def test_only_gate_passing_muscles_carry_an_atlas_id():
    r = json.loads(REPORT.read_text()); m = json.loads(MAPPING.read_text())
    assert r["source"] and r["badge"] == S.BADGE
    rows = r["muscles"]
    for e in m["entries"]:
        row = rows[e["source_structure"]]
        assert bool(e["atlas_id"]) == row["ship"]
        if row["ship"]:
            assert row["main_component_fraction"] >= 0.95 and row["jitter_dice_min"] >= 0.8
            assert 0.5 <= row["ratio"] <= 2.0 and row["overlap_ct_radius_ulna_vox"] == 0
            assert S.BADGE[1:] in e["procedural_badge"]


@pytest.mark.skipif(not MANIFEST.exists(), reason="ct_vhm_forearm_seeded not converted")
def test_converted_subject_is_badged():
    man = json.loads(MANIFEST.read_text())
    assert man["structures"] and all("not by an anatomist" in s.get("procedural_badge", "") for s in man["structures"])
