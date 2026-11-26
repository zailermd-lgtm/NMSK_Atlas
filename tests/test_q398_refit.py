"""Q398: the refit's pure parts on a synthetic skin slab -- the depth remap moves what pokes out to GAP under the inner sheet,
keeps the order of a column (no fold) and leaves a shell's deep face; the skin offset moves both sheets outward together (the
thickness is kept), never inward, and only where a requirement's normal agrees."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q398"))
import refit_q398 as R  # noqa: E402
import under_skin_q394 as U  # noqa: E402


def sphere_slab(r_out=50.0, r_in=48.0, sub=3):
    import trimesh
    o = trimesh.creation.icosphere(subdivisions=sub, radius=r_out)
    i = trimesh.creation.icosphere(subdivisions=sub, radius=r_in)
    V = np.vstack([o.vertices, i.vertices]); F = np.vstack([o.faces, i.faces[:, ::-1] + len(o.vertices)])
    cls = np.r_[np.ones(len(o.faces), int), -np.ones(len(i.faces), int)]
    return V, F, cls


def column(z0, z1, n=9):
    """points stacked along +z (the outward normal at the sphere's top), z0 deep .. z1 shallow"""
    z = np.linspace(z0, z1, n)
    return np.stack([np.zeros(n), np.zeros(n), z], 1)


def test_remap_moves_out_points_under_the_inner_sheet_without_reordering():
    V, F, cls = sphere_slab()
    sk = U.Skin(["s"], {"s": V}, {"s": F}, {"s": cls})
    v = column(35.0, 52.0)                                  # deep end inside, shallow end 2 mm outside the outer sheet
    for shell in (True, False):
        w = v.copy()
        for _ in range(R.ROUNDS):
            w2 = R.remap_step(w, sk, shell, 0.5)
            if w2 is None:
                break
            w = w2
        assert not U.Skin(["s"], {"s": V}, {"s": F}, {"s": cls}).test(w)[0].any()
        assert w[:, 2].max() <= 48.0 - R.GAP + 0.05
        assert np.all(np.diff(w[:, 2]) > 0)                 # the column keeps its order: no fold
        if shell:
            assert abs(w[0, 2] - v[0, 2]) < 1e-6             # a shell's deepest point stays


def test_skin_offset_is_outward_and_keeps_thickness():
    V, F, cls = sphere_slab()

    class P:  # the minimum of a Page the offset needs
        pass
    pg = P(); pg.skin_ids = ["s"]; pg.ids = ["s"]; pg.V = {"s": V.copy()}; pg.F = {"s": F}
    sk = U.Skin(["s"], pg.V, pg.F, {"s": cls})
    req = np.array([[0.0, 0.0, 51.0]])
    new, rep = R.skin_offset(pg, sk, req, np.array([2.0 + 1.0 + R.GAP]))
    v1 = new["s"]
    rr0, rr1 = np.linalg.norm(V, axis=1), np.linalg.norm(v1, axis=1)
    assert np.all(rr1 >= rr0 - 1e-9)                        # never inward
    assert rep["s"]["max_mm"] <= R.SKIN_MAX + 1e-9
    top = V[:, 2] > 49.9 * np.cos(np.radians(3))
    assert (rr1 - rr0)[top].max() > 2.0
    bottom = V[:, 2] < -40
    assert np.allclose(v1[bottom], V[bottom])               # the far side (normal disagrees, far away) does not move
    no = len(V) // 2
    th0 = rr0[:no].mean() - rr0[no:].mean()
    moved = (rr1 - rr0)[:no] > 0.5
    # the inner vertex under each moved outer vertex moved by about the same amount: slab thickness kept
    d_out = (rr1 - rr0)[:no][moved].mean(); d_in = (rr1 - rr0)[no:][moved].mean()
    assert abs(d_out - d_in) < 0.25 and th0 > 1.9


def test_outside_complete_on_two_digits():
    # two neighbouring "digits" (slabs): the complete test (ray parity + s_out > 0, no inner-sheet condition) calls a point just
    # above digit A outside and a point inside A inside, with B's sheets in the parity surface
    import trimesh
    parts = []
    for cx in (0.0, 9.0):
        o = trimesh.creation.icosphere(subdivisions=3, radius=5.0); i = trimesh.creation.icosphere(subdivisions=3, radius=4.0)
        V = np.vstack([o.vertices, i.vertices]) + [cx, 0, 0]
        F = np.vstack([o.faces, i.faces[:, ::-1] + len(o.vertices)])
        cls = np.r_[np.ones(len(o.faces), int), -np.ones(len(i.faces), int)]
        parts.append((V, F, cls))
    ids = ["a", "b"]
    sk = U.Skin(ids, {k: p[0] for k, p in zip(ids, parts)}, {k: p[1] for k, p in zip(ids, parts)}, {k: p[2] for k, p in zip(ids, parts)})
    P = np.array([[0.0, 0.0, 5.6], [0.0, 0.0, 3.0]])           # just above digit A's top / inside digit A
    m, so = R.outside_complete(sk, P)
    assert m.tolist() == [True, False]
