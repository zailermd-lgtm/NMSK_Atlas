"""Q243 unit tests (no GLBs, no build/ needed): tube capping, the fast signed bone distance, the per-vertebra blend, the SUBJECT_LABELS sync, the library manifest."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "anatomy"))


def _open_cylinder(r=2.0, h=20.0, n=24):
    c = trimesh.creation.cylinder(radius=r, height=h, sections=n)
    keep = np.abs(c.face_normals[:, 2]) < 0.9          # drop the two end caps -> an open tube
    return trimesh.Trimesh(c.vertices, c.faces[keep], process=True)


def test_cap_open_ends_closes_a_tube_with_flat_discs():
    from scripts.anatomy.q243 import hra
    t = _open_cylinder()
    assert not t.is_watertight
    V, F, info = hra.cap_open_ends(t.vertices, t.faces)
    m = trimesh.Trimesh(V, F, process=False)
    assert info["capped"] == 2 and info["left_open"] == 0 and m.is_watertight
    assert abs(abs(m.volume) - np.pi * 2.0 ** 2 * 20.0) / (np.pi * 4 * 20) < 0.03


def test_cap_open_ends_leaves_a_folded_end_open():
    from scripts.anatomy.q243 import hra
    t = _open_cylinder()
    V = t.vertices.copy()
    top = V[:, 2] > 9.9
    V[top, 2] += np.where(np.arange(top.sum()) % 2 == 0, 3.0, -3.0)          # a ragged (non-planar) rim
    _, _, info = hra.cap_open_ends(V, t.faces)
    assert info["left_open"] >= 1 and not info["watertight"]


def test_cap_is_orientation_consistent_with_the_tube():
    from scripts.anatomy.q243 import hra
    t = _open_cylinder()
    V, F, _ = hra.cap_open_ends(t.vertices, t.faces)
    assert trimesh.Trimesh(V, F, process=False).is_winding_consistent


def test_fastbone_signed_distance_and_push_out():
    from scripts.anatomy.q243.fastbone import Bones
    s = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
    b = Bones([s], n=60000)
    P = np.array([[0, 0, 12.0], [0, 0, 8.0], [0, 0, 0.0], [13.0, 0, 0]])
    sd, nrm = b.signed(P)
    assert np.allclose(sd, [2.0, -2.0, -10.0, 3.0], atol=0.35)
    V, n_moved, mx = b.rest_on(np.array([[0, 0, 9.5], [0, 0, 30.0]]), margin=1.0, iters=6)
    assert n_moved == 1 and abs(V[0, 2] - 11.0) < 0.4 and V[1, 2] == 30.0 and mx < 2.0


def test_blend_is_the_identity_for_identity_fits_and_halfway_for_disc():
    from scripts.anatomy.q243 import spine as SP
    fits = {}
    for k, lv in enumerate(SP.LEVELS):
        fits[lv] = dict(T=(1.0, np.eye(3), np.array([0.0, 0, 0])), hra_centroid=np.array([0.0, 700 - 20 * k, 0.0]))
    fits["S1"] = dict(T=(1.0, np.eye(3), np.array([0.0, 0, 0])), hra_centroid=np.array([0.0, 100.0, 0]))
    X = np.array([[1.0, 650.0, 2.0], [3.0, 400.0, 1.0]])
    assert np.allclose(SP.Blend(fits)(X), X)
    fits["C3"]["T"] = (1.0, np.eye(3), np.array([4.0, 0, 0]))
    out = SP.Blend(fits).disc(X, "C3", "C4")
    assert np.allclose(out, X + np.array([2.0, 0, 0]))


def test_levels_and_disc_table_cover_24_discs_and_29_segments():
    from scripts.anatomy.q243 import spine as SP
    assert len(SP.LEVELS) == 25 and len(SP.DISCS) == 24 and len(SP.CORD) == 29
    assert [d[0] for d in SP.DISCS][0] == "axis" and SP.DISCS[-1][1:] == ("L6", "S1")
    assert SP.CORD[0][0] == "C1" and SP.CORD[-1][0] == "S4"


def test_subject_labels_patch_is_idempotent_and_minimal():
    import sync_subjects_q243 as S
    text = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    new = S.patch(text)
    assert S.patch(new) == new
    assert new.count("xfer_hra2vhf_q243:") == 1 and new.count("xfer_hra2vhf_spine_q243:") == 1
    if new != text:
        assert len(new.splitlines()) - len(text.splitlines()) == 2


def test_subject_labels_in_template_if_synced():
    text = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    if "xfer_hra2vhf_q243:" not in text:
        pytest.skip("the working-tree template has not been synced yet (python3 scripts/sync_subjects_q243.py)")
    # classifySource maps every xfer_hra2* subject to the same-donor class
    assert 'if (b.indexOf("xfer_hra2") === 0) return "reference_same_donor";' in text


def test_manifest_has_the_objects_q243_uses_and_they_are_cc_by_4():
    man = json.loads((REPO / "data" / "derived" / "Q242_hra_manifest.json").read_text())
    objs = {o["object"]: o for o in man["objects"]}
    for name in ("united-female", "united-male", "blood-vasculature-female", "spinal-cord-female", "intervertebral-disk-female", "pelvis-male", "pelvis-female"):
        assert name in objs, name
        assert objs[name]["licence_ok_cc_by_4"] and objs[name]["licence_object"] == "https://creativecommons.org/licenses/by/4.0/"
        assert any(f["file"].endswith(".glb") and len(f["sha256"]) == 64 for f in objs[name]["files"])
    assert "6 lumbar vertebrae" in objs["spinal-cord-female"]["description_head"]


def test_vessel_table_pairs_left_right_and_names_match_ids():
    from scripts.anatomy.q243 import vessels as V
    ids = [v[0] for v in V.VESSELS]
    assert len(ids) == len(set(ids)) == 15
    for sid, name, latin, node, side, kind, grp in V.VESSELS:
        assert (side == "left") == (sid.endswith("_l") or "_L" == node[-2:] or "left" in node), sid
        assert (side == "right") == (sid.endswith("_r") or "_R" == node[-2:] or "right" in node), sid
        assert (side is not None) or not (sid.endswith("_l") or sid.endswith("_r")), sid
        assert kind in ("a", "v") and node in V.ONTO
        assert ("(left)" in name) == (side == "left") and ("(right)" in name) == (side == "right")
