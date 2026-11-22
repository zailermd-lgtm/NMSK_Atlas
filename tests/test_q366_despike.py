"""Q366: the pure functions of scripts/anatomy/q366/despike_q366.py -- the local map follows a smooth warp, flags an injected spike
and puts it back, and leaves a legitimately bent tube alone."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/anatomy/q366"))
import despike_q366 as D  # noqa: E402


def sphere(sub=3, r=10.0):
    trimesh = pytest.importorskip("trimesh")
    s = trimesh.creation.icosphere(subdivisions=sub, radius=r)
    return np.asarray(s.vertices, float), np.asarray(s.faces, int)


def smooth_warp(X):
    """anisotropic scale, rotation, translation and a gentle quadratic bend"""
    a = np.radians(20)
    R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    Y = (X * np.array([1.15, 0.9, 1.05])) @ R.T + np.array([30.0, -12.0, 5.0])
    Y[:, 0] += 0.01 * X[:, 1] ** 2
    return Y


def tube(length=200.0, r=3.0, step=2.0, seg=12):
    zs = np.arange(0, length + 1e-9, step)
    t = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    X = np.array([[r * np.cos(a), r * np.sin(a), z] for z in zs for a in t])
    F = []
    for i in range(len(zs) - 1):
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg
            c, d = a + seg, b + seg
            F += [[a, b, d], [a, d, c]]
    return X, np.array(F)


def bend(X, Rc=80.0):
    th = X[:, 2] / Rc
    return np.stack([(Rc + X[:, 0]) * np.cos(th) - Rc, X[:, 1] * 1.1, (Rc + X[:, 0]) * np.sin(th)], 1)


def test_neighbours_leave_self_and_copies_out():
    X = np.array([[0, 0, 0], [0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0]], float)
    nb = D.neighbours(X, k=3)
    assert 1 not in nb[0] and 0 not in nb[0] and 0 not in nb[1]
    assert (nb[2] != 2).all()


def test_local_map_recovers_smooth_warp():
    XM, F = sphere()
    XF = smooth_warp(XM)
    nb = D.neighbours(XM)
    p, ok = D.local_predict(XM, XF, nb)
    assert ok.all()
    assert np.linalg.norm(p - XF, axis=1).max() < 0.4 < D.T_HI  # mm, on a 20 mm sphere warped anisotropically and bent


def test_injected_spike_is_flagged_and_put_back():
    XM, F = sphere()
    XF0 = smooth_warp(XM)
    XF = XF0.copy()
    i = 100
    nrm = XM[i] / np.linalg.norm(XM[i])
    XF[i] += 5.0 * nrm                                         # a 5 mm spike
    X1, fl, r0, sig, p, info = D.despike_structure(XM, XF, F)
    assert fl[i] and fl.sum() == 1
    assert np.linalg.norm(X1[i] - XF0[i]) < 0.3
    others = np.arange(len(XM)) != i
    assert np.array_equal(X1[others], XF[others])              # nothing else moves


def test_spike_patch_is_flagged():
    XM, F = sphere()
    XF0 = smooth_warp(XM)
    XF = XF0.copy()
    i = 200
    E = D.edges_of(F)
    ring = np.unique(E[(E == i).any(1)])                       # the vertex and its 1-ring: a 7-vertex patch
    nrm = XM[i] / np.linalg.norm(XM[i])
    XF[ring] += 4.0 * nrm
    X1, fl, r0, sig, p, info = D.despike_structure(XM, XF, F)
    assert fl[ring].all() and fl.sum() == len(ring)
    assert np.linalg.norm(X1[ring] - XF0[ring], axis=1).max() < 0.6


def test_frozen_vertex_is_not_moved():
    XM, F = sphere()
    XF = smooth_warp(XM)
    XF[100] += 5.0 * XM[100] / 10.0
    fr = np.zeros(len(XM), bool); fr[100] = True
    X1, fl, *_ = D.despike_structure(XM, XF, F, frozen=fr)
    assert not fl.any() and np.array_equal(X1, XF)


def test_bent_tube_is_not_flagged():
    XM, F = tube()
    XF = bend(XM)                                              # 200 mm tube bent through 2.5 rad: legitimate, not a spike
    X1, fl, r0, sig, p, info = D.despike_structure(XM, XF, F)
    assert not fl.any()
    assert r0.max() < D.T_HI
    # a rigid fit of the whole tube would call most of it a spike
    a, b = XM - XM.mean(0), XF - XF.mean(0)
    U, S, Vt = np.linalg.svd(b.T @ a)
    R = U @ Vt
    assert (np.linalg.norm(a @ R.T - b, axis=1) > 3.0).mean() > 0.3


def test_spike_on_bent_tube_is_flagged():
    XM, F = tube()
    XF0 = bend(XM)
    XF = XF0.copy()
    i = 50 * 12 + 3
    XF[i] += np.array([0.0, 0.0, 4.0])
    X1, fl, *_ = D.despike_structure(XM, XF, F)
    assert fl[i] and fl.sum() == 1
    assert np.linalg.norm(X1[i] - XF0[i]) < 0.3


def test_size_check():
    assert D.size_check(100.0, 101.0, 50.0)["ok"]                # within SIZE_FREE
    assert D.size_check(130.0, 105.0, 100.0)["ok"]               # spike removal: toward the source
    assert not D.size_check(100.0, 90.0, 100.0)["ok"]            # away from the source by 10 %


def test_twelve_vertex_patch_is_flagged():
    XM, F = sphere()
    XF0 = smooth_warp(XM)
    for i in (17, 200, 300):
        patch = np.argsort(np.linalg.norm(XM - XM[i], axis=1))[:D.PATCH_MAX]
        XF = XF0.copy()
        XF[patch] += 4.0 * XM[i] / 10.0
        X1, fl, *_ = D.despike_structure(XM, XF, F)
        assert fl[patch].all() and fl.sum() == len(patch)
        assert np.linalg.norm(X1[patch] - XF0[patch], axis=1).max() < 0.5
