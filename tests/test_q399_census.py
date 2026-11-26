"""Q399: the completed outside test on synthetic skin -- a single-sheet patch (+2 / +3) joins the test whichever way it is
wound, the parity check drops a completed face whose side it cannot tell, and the per-digit test judges a digit by its own skin
tube (a neighbour digit's skin does not hide what pokes out of it)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q394"))
import under_skin_q394 as U  # noqa: E402


def sphere(r, sub=3, flip=False):
    import trimesh
    s = trimesh.creation.icosphere(subdivisions=sub, radius=r)
    F = s.faces[:, ::-1] if flip else s.faces
    return np.asarray(s.vertices, float), np.asarray(F)


def test_single_sheet_either_winding_counts_outside_points():
    for flip, code in ((False, 2), (True, 3)):
        V, F = sphere(50.0, flip=flip)
        g = SimpleNamespace(interior=np.zeros((30, 3)) + np.random.default_rng(0).normal(0, 1, (30, 3)), itree=None)
        from scipy.spatial import cKDTree
        g.itree = cKDTree(g.interior)
        cls = U.single_sheet(V, F, np.zeros(len(F), int), g)
        assert (cls == code).mean() > 0.95
        cls = U.confirm_single(["s"], {"s": V}, {"s": F}, {"s": cls})["s"]
        assert (cls == code).mean() > 0.95
        sk = U.Skin(["s"], {"s": V}, {"s": F}, {"s": cls})
        P = np.array([[0, 0, 52.0], [0, 0, 49.0], [30.0, 0, 0]])
        out, so, si, _, _, _ = sk.test(P)
        assert out.tolist() == [True, False, False]
        assert abs(so[0] - 2.0) < 0.2


def cyl(x0, r=8.0, z0=0.0, z1=60.0, n=24, m=30):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False); z = np.linspace(z0, z1, m)
    V = np.array([[x0 + r * np.cos(t), r * np.sin(t), zz] for zz in z for t in a])
    F = []
    for j in range(m - 1):
        for i in range(n):
            p, q = j * n + i, j * n + (i + 1) % n
            F += [[p, q, q + n], [p, q + n, p + n]]
    return V, np.array(F)


def test_digit_tube_judges_by_its_own_skin():
    ids, pos, Fs, sys_, cls = [], {}, {}, {}, {}
    for x0, nm in ((0.0, "second"), (15.0, "third")):          # two touching digits (radius 8, axes 15 apart)
        for part, (a, b) in (("proximal", (2, 25)), ("middle", (27, 40)), ("distal", (42, 55))):
            k = f"zan_{part}_phalanx_of_{nm}_finger_of_foot_l"
            t = np.linspace(a, b, 20); pos[k] = np.stack([np.full(20, x0), np.zeros(20), t], 1); Fs[k] = np.zeros((0, 3), int)
            ids.append(k); sys_[k] = "bone"
        k = f"skin_{nm}"; V, F = cyl(x0); pos[k] = V; Fs[k] = F; ids.append(k); sys_[k] = "skin"; cls[k] = np.ones(len(F), int)
    page = SimpleNamespace(ids=ids, skin_ids=["skin_second", "skin_third"], F=Fs, sys=sys_)
    dg = U.Digits(page, pos, cls)
    assert dg.ok and len(dg.tubes) == 2
    P = np.array([[0, 0, 40.0],          # on the axis of the second digit: inside
                  [0, 10.0, 40.0],       # 2 mm outside the second digit's skin, dorsal: outside
                  [9.0, 0, 40.0]])       # 1 mm outside the second digit, inside the third digit's tube: inside the body
    ind, out, dep = dg.test(P)
    assert ind.all()
    assert out.tolist() == [False, True, False]
    assert abs(dep[1] - 2.0) < 0.3
