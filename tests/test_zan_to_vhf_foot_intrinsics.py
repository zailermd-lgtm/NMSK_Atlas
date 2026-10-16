"""Q62 step 5: foot intrinsics transferred onto the VH female's own foot bones (zan_to_vhf_foot_intrinsics)."""
import json
from pathlib import Path

import numpy as np
import pytest
import trimesh

from scripts.transfer import zan_to_vhf_foot_intrinsics as F

REPO = Path(__file__).resolve().parents[1]


def test_ids_are_existing_entities_and_skip_her_meshes():
    tg = F.targets()
    assert len(tg) == 14 and not set(tg) & F.SKIP_EXISTING
    for aid in F.ZAN_ID:
        assert (REPO / "data" / "muscles" / "lower_limb" / f"{aid}.json").exists(), aid
    assert F.ZAN_ID["lumbricals_foot_r"] == "zan_lumbrical_muscles_of_foot_r"


def test_bounded_push_moves_only_shallow_vertices():
    box = trimesh.creation.box(extents=(20, 20, 20))
    v = np.array([[0.0, 0.0, 9.0],    # 1 mm deep -> pushed out
                  [0.0, 0.0, 0.0],    # 10 mm deep -> stays (bound 3 mm)
                  [0.0, 0.0, 15.0]])  # outside -> untouched
    out, n_push, n_deep = F.bounded_push_off_bones(v, [box], bound_mm=3.0, clearance_mm=1.0)
    assert (n_push, n_deep) == (1, 1)
    assert not box.contains(out[:1])[0] and out[0, 2] == pytest.approx(11.0, abs=1e-6)
    assert np.allclose(out[1:], v[1:])


def test_pull_inside_skin_is_bounded():
    skin = trimesh.creation.icosphere(subdivisions=3, radius=50.0)
    v = np.array([[0.0, 0.0, 52.0], [0.0, 0.0, 10.0]])
    out, n = F.pull_inside_skin(v, skin)
    assert n == 1 and skin.contains(out).all()
    assert np.linalg.norm(out[0] - v[0]) < 4.0 and np.allclose(out[1], v[1])


def test_shipped_rows_pass_gates():
    rp = REPO / "data" / "derived" / "Q62s5_vhf_foot_intrinsics.json"
    if not rp.exists():
        pytest.skip("report not built")
    d = json.loads(rp.read_text())
    for aid in d["summary"]["shipped"]:
        r = d["rows"][aid]
        assert r["outside_skin_frac_after"] == 0.0
        assert r["inside_bone_frac_after"] <= F.MAX_INSIDE_BONE
        assert r["overlap_frac_total"] <= F.MAX_OVERLAP
        assert r["rides_on"]["weighted_median_fit_mm"] <= F.MAX_BONE_FIT_MM
        assert "TRANSFERRED" in r["badge"] and "Z-Anatomy" in r["badge"]
