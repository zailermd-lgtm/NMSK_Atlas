"""Q248: carrier-bone fits Z-Anatomy bone group (Combined page) -> own bone group (similarity: rotation + uniform scale + translation), bidirectional trimmed ICP, and the group map between the two pages."""
from __future__ import annotations
import re
import numpy as np, trimesh
from scipy.spatial import cKDTree

SCALE_LIM = (0.9, 1.12)


def surf_samples(meshes, n):
    """~n points on the union of the meshes, area weighted"""
    ms = [m for m in meshes if len(m.faces)]
    areas = np.array([m.area for m in ms]); tot = areas.sum()
    pts = []
    np.random.seed(1)
    for m, a in zip(ms, areas):
        k = max(200, int(n * a / tot))
        pts.append(trimesh.sample.sample_surface(m, k, seed=1)[0])
    return np.vstack(pts)


def umeyama(X, Y, lim=SCALE_LIM):
    mx, my = X.mean(0), Y.mean(0)
    Xc, Yc = X - mx, Y - my
    C = Yc.T @ Xc / len(X)
    U, S, Vt = np.linalg.svd(C)
    D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt
    var = (Xc ** 2).sum() / len(X)
    s = float(np.trace(np.diag(S) @ D) / var) if var > 0 else 1.0
    s = min(max(s, lim[0]), lim[1])
    t = my - s * R @ mx
    return s, R, t


def apply(T, V):
    s, R, t = T
    return s * (np.asarray(V) @ R.T) + t


def inv(T):
    s, R, t = T
    return (1 / s, R.T, -(1 / s) * R.T @ t)


def icp(src, dst, iters=40, trim=0.85, init=None):
    """bidirectional trimmed ICP of the cloud src onto dst; -> (T, stats)"""
    T = init or (1.0, np.eye(3), np.zeros(3))
    kd_dst, kd_src = cKDTree(dst), cKDTree(src)
    for _ in range(iters):
        Xs = apply(T, src)
        d1, i1 = kd_dst.query(Xs)
        k1 = d1 <= np.quantile(d1, trim)
        Ti = inv(T)
        Yb = apply(Ti, dst)
        d2, i2 = kd_src.query(Yb)
        k2 = d2 * T[0] <= np.quantile(d2 * T[0], trim)
        X = np.vstack([src[k1], src[i2[k2]]]); Y = np.vstack([dst[i1[k1]], dst[k2]])
        Tn = umeyama(X, Y)
        done = abs(Tn[0] - T[0]) < 1e-6 and np.abs(Tn[2] - T[2]).max() < 1e-4
        T = Tn
        if done:
            break
    Xs = apply(T, src)
    d1 = kd_dst.query(Xs)[0]; d2 = cKDTree(Xs).query(dst)[0]
    d = np.concatenate([d1, d2])
    st = dict(scale=round(float(T[0]), 4), median_mm=round(float(np.median(d)), 2), p90_mm=round(float(np.quantile(d, .9)), 2), forward_median_mm=round(float(np.median(d1)), 2), reverse_median_mm=round(float(np.median(d2)), 2))
    return T, st


# ---------------------------------------------------------------- group map own <- Z (Combined) page
NUM = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}


def side_of(i):
    return i[-1] if i.endswith(("_l", "_r")) else None


def group_map(OWN, COMB):
    """-> {group_name: (own_ids, comb_ids)}; one carrier group per own bone mesh (or per merged own mesh)"""
    ob = {i for i, e in OWN.items() if e["sys"] == "bone" and not re.search(r"zfill|_q212|#$", i)}
    cb = {i for i, e in COMB.items() if e["sys"] == "bone"}
    G = {}
    for i in sorted(ob):
        if i in cb and not re.match(r"(sacrum|coccyx|cranium|ribs|carpals|metacarpals?|phalanges|metatarsals)", i):
            G[i] = ([i], [i])
    # vertebrae by rank from the top
    def zv(prefix):
        return sorted([i for i in cb if re.match(prefix, i)], key=lambda x: int(re.search(r"(\d+)$", x).group(1)))
    cerv = ["zan_atlas_c1", "zan_axis_c2"] + zv(r"zan_vertebra_c\d+$")
    thor = zv(r"zan_vertebra_t\d+$"); lum = zv(r"zan_vertebra_l\d+$")
    for pre, zl in (("cervical_vertebrae", cerv), ("thoracic_vertebrae", thor), ("lumbar_vertebrae", lum)):
        own = sorted([i for i in ob if i.startswith(pre + "#")], key=lambda x: int(x.split("#")[1]))
        for k, o in enumerate(own[:len(zl)]):
            G[o] = ([o], [zl[k]])
    # sacrum / coccyx
    so = sorted([i for i in ob if i.startswith("sacrum")] + [i for i in ob if i == "coccyx"])
    sc = [i for i in ("sacrum", "coccyx") if i in cb]
    if so and sc:
        G["sacrococcyx"] = (so, sc)
    for s in ("l", "r"):
        rz = [i for i in cb if re.match(r"zan_(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)_rib_" + s, i)]
        if f"ribs_{s}" in ob and rz:
            G[f"ribs_{s}"] = ([f"ribs_{s}"], rz)
        mt = [i for i in cb if re.match(r"zan_\w+_metatarsal_bone_" + s + "$", i)]
        if f"metatarsals_{s}" in ob and mt:
            G[f"metatarsals_{s}"] = ([f"metatarsals_{s}"], mt)
        pf = [i for i in cb if re.match(r"zan_\w+_phalanx_of_\w+_finger_of_foot_" + s + "$", i)]
        if f"phalanges_foot_{s}" in ob and pf:
            G[f"phalanges_foot_{s}"] = ([f"phalanges_foot_{s}"], pf)
        ph = [i for i in cb if re.match(r"zan_\w+_phalanx_of_\w+_finger_of_hand_" + s + "$", i)]
        if f"phalanges_hand_{s}" in ob and ph:
            G[f"phalanges_hand_{s}"] = ([f"phalanges_hand_{s}"], ph)
        cp = [i for i in cb if re.match(r"zan_(scaphoid|lunate|triquetral|pisiform|trapezium|trapezoid|capitate|hamate)_bone_" + s + "$", i)]
        for cname in (f"carpals_{s}", f"carpals_{s}_q212"):
            if cname in OWN and cp:
                G[f"carpals_{s}"] = ([cname], cp); break
        for k, nm in enumerate(("first", "second", "third", "fourth", "fifth"), 1):
            mc = f"zan_{nm}_metacarpal_bone_{s}"
            if f"metacarpal_{k}_{s}" in ob and mc in cb:
                G[f"metacarpal_{k}_{s}"] = ([f"metacarpal_{k}_{s}"], [mc])
    return G


def fit_groups(OWN, COMB, G, n_src=3000, n_dst=15000, verbose=False):
    """per group ICP of the Z bones onto the own bones. -> {group: dict(T, stats, comb_ids, own_ids)}"""
    out = {}
    for g, (oi, ci) in G.items():
        dst = surf_samples([trimesh.Trimesh(OWN[i]["v"], OWN[i]["f"], process=False) for i in oi], n_dst)
        src = surf_samples([trimesh.Trimesh(COMB[i]["v"], COMB[i]["f"], process=False) for i in ci], n_src)
        T, st = icp(src, dst)
        T2, st2 = icp(src, dst, init=(1.0, np.eye(3), dst.mean(0) - src.mean(0)))     # second start: centroids together (cropped / displaced bones)
        if st2["median_mm"] < st["median_mm"] - 0.1:
            T, st = T2, st2
        out[g] = dict(T=T, stats=st, own_ids=oi, comb_ids=ci)
        if verbose:
            print(f"  {g:28s} s={st['scale']:.3f} med={st['median_mm']:.2f} p90={st['p90_mm']:.2f}", flush=True)
    return out
