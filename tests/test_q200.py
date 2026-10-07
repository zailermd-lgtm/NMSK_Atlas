"""Q200: elbow continuity of the two OWN reconstructed models (Z-Anatomy continuations welded to measured structures cut flat at CT seams).

Unit tests use synthetic meshes; the build tests (skipped when build/viewer_*_q200 is absent) check the shipped bundles."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.transfer.q200_continue import find_caps, continue_cap2, ordered_loops, clip_side  # noqa: E402
from scripts.transfer.q200_geom import fit_bone, align_rigid_local, sample_surface  # noqa: E402
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer.q200_overlap import separate, mesh_volume  # noqa: E402


def cyl(r0, r1, y0, y1, n=24, rings=12, cx=0.0, cz=0.0, capped=True):
    """tapered cylinder along +y (closed when capped)"""
    ys = np.linspace(y0, y1, rings)
    rs = np.linspace(r0, r1, rings)
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    V = np.vstack([np.stack([cx + r * np.cos(th), np.full(n, y), cz + r * np.sin(th)], 1) for y, r in zip(ys, rs)])
    F = []
    for j in range(rings - 1):
        for i in range(n):
            a, b = j * n + i, j * n + (i + 1) % n
            c, d = (j + 1) * n + i, (j + 1) * n + (i + 1) % n
            F += [[a, b, d], [a, d, c]]
    if capped:
        for yv, off, flip in ((y0, 0, True), (y1, (rings - 1) * n, False)):
            ci = len(V); V = np.vstack([V, [cx, yv, cz]])
            for i in range(n):
                a, b = off + i, off + (i + 1) % n
                F.append([ci, b, a] if flip else [ci, a, b])
    return np.asarray(V, float), np.asarray(F, np.int64)


def test_find_caps_and_ordered_loop():
    v, f = cyl(10, 10, 100, 200)
    caps = find_caps(v, f, minarea=40)
    ys = sorted(round(c["pos"], 1) for c in caps if c["axis"] == "y")
    assert ys == [100.0, 200.0]
    c = [c for c in caps if c["axis"] == "y" and abs(c["pos"] - 100) < 1e-6][0]
    assert c["sign"] == -1 and c["n_comp"] == 1
    assert len(ordered_loops(v, f[c["faces"]])[0]) == 24


def test_continuation_joins_the_cap_outline_exactly():
    # measured: a cylinder cut flat at y=100 (outward = -y); Z counterpart: longer, thinner, shifted 3 mm
    mv, mf = cyl(10, 10, 100, 200)
    zv, zf = cyl(10, 5, 40, 210, cx=3.0)
    cap = [c for c in find_caps(mv, mf) if c["axis"] == "y" and abs(c["pos"] - 100) < 1e-6][0]
    r = continue_cap2(mv, cap, zv, zf, min_beyond=10.0)
    assert "v" in r, r
    V = r["v"]
    ring0 = V[r["ring0"]]
    # ring 0 lies on the cap plane and on the measured outline (radius 10 about the axis)
    assert np.allclose(ring0[:, 1], 100.0, atol=1e-6)
    assert np.allclose(np.hypot(ring0[:, 0], ring0[:, 2]), 10.0, atol=0.3)
    # nothing of the continuation is on the measured side of the plane
    assert V[:, 1].max() <= 100.0 + 1e-6
    # loft tapers, then the Z shape continues to its own end (y=40)
    assert V[:, 1].min() < 45.0
    # no flat planar end left at the far Z end other than the Z mesh's own closure; ring-0 end is open (it abuts the measured cap)
    assert r["Lt"] >= 6.0


def test_thin_z_section_gives_a_local_continuation_not_a_loft_over_the_whole_face():
    mv, mf = cyl(10, 10, 100, 200)
    zv, zf = cyl(3, 2, 40, 210, cx=2.0)           # Z section 9 % of the measured face
    cap = [c for c in find_caps(mv, mf) if c["axis"] == "y" and abs(c["pos"] - 100) < 1e-6][0]
    r = continue_cap2(mv, cap, zv, zf, min_beyond=10.0)
    assert r["mode"] == "local" and r["cap_covered"] < 0.2
    V = r["v"]
    assert V[:, 1].max() <= 100.0 + 1e-6
    # the section stays on the measured face (inside the radius-10 disc)
    assert (np.hypot(V[r["ring0"], 0], V[r["ring0"], 2]) < 10.0).all()


def test_continuation_held_when_z_has_nothing_beyond():
    mv, mf = cyl(10, 10, 100, 200)
    zv, zf = cyl(10, 10, 98, 300)          # Z ends 2 mm beyond the plane
    cap = [c for c in find_caps(mv, mf) if c["axis"] == "y" and abs(c["pos"] - 100) < 1e-6][0]
    r = continue_cap2(mv, cap, zv, zf, min_beyond=10.0)
    assert "v" not in r and "no Z material" in r["reason"]


def test_fit_bone_recovers_a_rigid_motion_with_a_truncated_target():
    z, zf = cyl(8, 12, 0, 200, n=32, rings=40)
    # make the profile non-symmetric so the fit is unique
    z[:, 0] += 0.04 * z[:, 1]
    R = trimesh.transformations.rotation_matrix(np.radians(25), [0.3, 0.2, 0.9])[:3, :3]
    own = z @ R.T + np.array([30.0, 5.0, -12.0])
    keep = own[:, 1] > own[:, 1].min() + 60       # target = 70 % of the bone (truncated)
    fm = keep[zf].all(1)
    A, t, st = fit_bone(z, zf, own, zf[fm], scale0=1.0, scale=(0.95, 1.05))
    assert st["median"] < 1.0


def test_align_rigid_local_keeps_the_axial_position():
    mv, mf = cyl(10, 10, 100, 200)
    zv, zf = cyl(10, 10, 60, 160)
    zv2 = zv + np.array([4.0, 0.0, -3.0])       # in-plane offset only
    out, info = align_rigid_local(zv2, zf, mv, mf, 1, 100.0, -1, window=45.0)
    assert info["applied"]
    assert abs(np.median(out[:, 1] - zv2[:, 1])) < 1e-6 or info["mode"] == "rigid"
    assert info["after_median"] < info["before_median"]


def test_bundle_edit_leaves_other_entries_byte_identical(tmp_path):
    src = REPO / "build" / "viewer_m_hr_q193"
    if not (src / "bundle.json").exists():
        pytest.skip("q193 bundle not present")
    B = Bundle(src)
    raws = [it["raw"] for it in B.items]
    n0 = len(B.items)
    v, f = cyl(5, 5, 0, 10)
    B.add("zz_test_piece", "muscle", "left", "xfer_zan2vhm_elbow_q200", {"name": "t", "procedural_badge": "b"}, v, f)
    B.write(tmp_path, copy_clinical=False)
    B2 = Bundle(tmp_path)
    assert len(B2.items) == n0 + 1
    assert all(a["raw"] == b for a, b in zip(B2.items[:n0], raws))
    v2, f2 = B2.mesh(B2.items[-1])
    assert np.abs(v2 - v).max() <= 0.125 + 1e-9 and (f2 == f).all()


def test_separate_moves_a_muscle_out_of_a_fixed_neighbour_within_the_guards():
    box = trimesh.creation.box(extents=(40, 40, 40))
    sph = trimesh.creation.icosphere(subdivisions=3, radius=8.0)
    sph.apply_translation([20.0 - 4.0, 0.0, 0.0])          # pokes 4 mm into the box face
    v, info = separate(np.asarray(sph.vertices), np.asarray(sph.faces), [box])
    assert info["inside_after"] < info["inside_before"]
    assert info["move_max"] <= 8.0 + 1e-6
    assert 0.65 <= info["volume_ratio"] <= 1.5


# ---------------------------------------------------------------- the shipped bundles
Q193 = {"vhm": REPO / "build/viewer_m_hr_q193", "vhf": REPO / "build/viewer_f_hr_q193"}
Q200 = {"vhm": REPO / "build/viewer_m_hr_q200", "vhf": REPO / "build/viewer_f_hr_q200"}
NEW_SUBJECTS = {"vhm": {"xfer_zan2vhm_elbow_q200", "xfer_zan2vhm_armvessels_q200"},
                "vhf": {"xfer_zan2vhf_elbow_q200", "xfer_zan2vhf_armvessels_q200", "xfer_zan2vhf_leftforearm_q200"}}


@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_q200_bundle_measured_entries_untouched_and_additions_are_badged(body):
    if not (Q200[body] / "bundle.json").exists():
        pytest.skip("q200 bundle not built")
    A, B = Bundle(Q193[body]), Bundle(Q200[body])
    old = {(it["e"]["id"], it["e"]["subject"]): it["raw"] for it in A.items}
    new = {(it["e"]["id"], it["e"]["subject"]): it["raw"] for it in B.items}
    changed = [k for k, raw in old.items() if k not in new or new[k] != raw]
    for sid, sub in changed:
        assert sub.startswith("xfer_zan2"), f"a non-Z entry changed: {sid} ({sub})"          # measured / rule-based / transferred-VH never edited
    added = [it for it in B.items if (it["e"]["id"], it["e"]["subject"]) not in old]
    assert added and all(it["e"]["subject"] in NEW_SUBJECTS[body] for it in added)
    for it in added:
        assert "Z-Anatomy" in it["e"]["rec"]["procedural_badge"], it["e"]["id"]


def test_new_subjects_are_described_and_classed_as_z_fill():
    txt = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    for s in sorted(set().union(*NEW_SUBJECTS.values())):
        assert re.search(rf"^\s{{2}}{s}:\s*\"", txt, re.M), s
        assert s.startswith("xfer_zan2")      # classifySource(): startswith xfer_zan2 -> filled_zan
