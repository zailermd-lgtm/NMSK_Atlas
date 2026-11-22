#!/usr/bin/env python3
"""Q237 steps 1+2: classify every structure of the six CURRENT pages (paired / midline / lateralised by nature / unmatched) and quantify the asymmetry of every matched pair
-> data/derived/Q237_pairing.json (+ Q237_pairing.md by scripts/anatomy/q237/report_md.py).
    python3 scripts/anatomy/q237/pairing.py [--pages own_m,own_f,...] [--no-metrics] [--jobs 4]
Reads (never edits) the six page dirs (core.PAGES; Q237_SRC_<key> overrides). Measured data is NEVER overwritten by this script."""
from __future__ import annotations
import argparse, json, re, sys, time, datetime
from multiprocessing import Pool
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import core as C  # noqa: E402

REPO = C.REPO
OUT = REPO / "data/derived/Q237_pairing.json"
RATIO_LO, RATIO_HI, IOU_MIN = 0.8, 1.25, 0.6          # flag thresholds of the owner's request
MUCH_SMALLER = (0.5, 2.0)                               # 'one side much smaller' = unmatched kind
STRADDLE_MM = 8.0                                       # a mesh reaching >= this far to BOTH sides of the plane is one midline structure
SHEETS = ("fascia", "skin")                             # surface sheets: area ratio, shell IoU
THIN_MM = 4.0                                           # structures thinner than this (mean thickness 2V/A): the IoU is a 1 mm misalignment, not a shape difference -> not flagged by IoU
MIDLINE_C_MM = 12.0                                     # centroid within this of the plane = midline


# ------------------------------------------------------------------ geometry of a group
def gstats(S, ids, plane):
    v, f = C.merge(S, ids)
    s = C.area_samples(v, f, 600)
    sd = plane.signed(v)
    return dict(c=s.mean(0), lo=float(sd.min()), hi=float(sd.max()), n=len(v))


ALIAS = {"tlf": ("thoracolumbar", "fascia"), "peroneal": ("fibular",)}


def tokens(canon):
    out = set()
    for t in canon.split("_"):
        if not t or t in ("of", "the", "and", "a"): continue
        out.update(ALIAS.get(t, (t,)))
    return out


def classify(S, plane):
    G = C.groups_of(S)
    keys = {}
    for (sy, cn, sd), ids in G.items():
        keys.setdefault((sy, cn), {})[sd] = ids
    cache = {}

    def st(sy, cn, sd):
        k = (sy, cn, sd)
        if k not in cache:
            cache[k] = gstats(S, G[k], plane)
        return cache[k]

    def straddles(g):
        return g["lo"] <= -STRADDLE_MM and g["hi"] >= STRADDLE_MM

    def lat_of(sy, cn, sd):
        for i in G[(sy, cn, sd)]:
            r = C.lateral_reason(S[i])
            if r: return r
        return None

    units = []
    for (sy, cn), sides in sorted(keys.items()):
        base = dict(sys=sy, canon=cn)
        for sd in ("m",):
            if sd in sides:
                g = st(sy, cn, "m"); lat = lat_of(sy, cn, "m"); off = float(plane.signed(g["c"]))
                if lat: cls, why = "lateralised", lat
                elif straddles(g) or abs(off) <= MIDLINE_C_MM or C.MIDLINE_NAME.search(cn): cls, why = "midline", ("crosses the plane" if straddles(g) else f"centroid {off:+.1f} mm from the plane")
                else: cls, why = "lateralised", f"single mesh {abs(off):.0f} mm {'right' if off > 0 else 'left'} of the midline, not crossing it"
                units.append(dict(base, cls=cls, why=why, ids_m=[S[i]["id"] for i in sides["m"]], centroid_offset_mm=round(off, 1)))
        has_r, has_l = "r" in sides, "l" in sides
        if has_r and has_l:
            gr, gl = st(sy, cn, "r"), st(sy, cn, "l")
            lat = lat_of(sy, cn, "r") or lat_of(sy, cn, "l")
            u = dict(base, ids_r=[S[i]["id"] for i in sides["r"]], ids_l=[S[i]["id"] for i in sides["l"]], match="name")
            if straddles(gr) and straddles(gl):
                units.append(dict(u, cls="midline", why="both sides are one mesh crossing the plane"))
            elif lat:
                units.append(dict(u, cls="lateralised", why="paired organ with different sides by design: " + lat, paired_lateralised=True))
            else:
                units.append(dict(u, cls="paired", why=""))
        elif has_r or has_l:
            sd = "r" if has_r else "l"; g = st(sy, cn, sd); lat = lat_of(sy, cn, sd)
            u = dict(base, **{"ids_" + sd: [S[i]["id"] for i in sides[sd]]}, only_side=sd, centroid_offset_mm=round(float(plane.signed(g["c"])), 1))
            if straddles(g):
                units.append(dict(u, cls="midline", why="one mesh crossing the plane (labelled " + ("right" if sd == "r" else "left") + ")"))
            elif lat:
                units.append(dict(u, cls="lateralised", why=("one-sided by nature: " if True else "") + lat))
            else:
                units.append(dict(u, cls="unmatched", kind="missing_side", why=f"no {'left' if sd == 'r' else 'right'} counterpart by name"))
    # geometry + name fallback for the leftover singles of different spelling (Z aliases): the opposite single of the same system, similar words, mirrored centroid close
    left_u = [u for u in units if u["cls"] == "unmatched" and u.get("only_side") == "l"]
    right_u = [u for u in units if u["cls"] == "unmatched" and u.get("only_side") == "r"]
    used = set(); merged = []
    cand = []
    for a in right_u:
        for b in left_u:
            if a["sys"] != b["sys"]: continue
            ta, tb = tokens(a["canon"]), tokens(b["canon"])
            j = len(ta & tb) / max(1, len(ta | tb))
            if j < 0.4: continue
            ca = st(a["sys"], a["canon"], "r")["c"]; cb = st(b["sys"], b["canon"], "l")["c"]
            dm = float(np.linalg.norm(plane.reflect(cb) - ca))
            if dm <= 250.0: cand.append((dm, id(a), id(b), a, b, j, dm))
    for _, _, _, a, b, j, dm in sorted(cand, key=lambda t: t[0]):
        if id(a) in used or id(b) in used: continue
        used.add(id(a)); used.add(id(b))
        a.update(cls="paired", why="", match=f"geometry+name (word overlap {j:.2f}, mirrored centroids {dm:.0f} mm apart)", ids_l=b["ids_l"], canon_l=b["canon"])
        a.pop("only_side", None); a.pop("kind", None); a.pop("centroid_offset_mm", None)
        merged.append(b)
    units = [u for u in units if not any(u is m for m in merged)]
    return units, G



# ------------------------------------------------------------------ asymmetry metrics of one pair
G_S = None        # set in the worker processes (fork): the page's structures, plane, groups


def _wt(v, f):
    import trimesh
    try:
        m = trimesh.Trimesh(v, f, process=True)
        return m, bool(m.is_watertight)
    except Exception:
        return None, False


def kabsch(P, Q):
    """rigid R,t minimising |R P + t - Q|"""
    pc, qc = P.mean(0), Q.mean(0)
    H = (P - pc).T @ (Q - qc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    return R, qc - R @ pc


def icp(P, Q, tree_Q, iters=12, keep=0.8):
    """rigid ICP of P onto Q (trimmed); returns R, t and the composite"""
    R_t, t_t = np.eye(3), np.zeros(3)
    X = P.copy()
    for _ in range(iters):
        dd, ii = tree_Q.query(X)
        k = dd <= np.quantile(dd, keep)
        R, t = kabsch(X[k], Q[ii[k]])
        X = X @ R.T + t
        R_t, t_t = R @ R_t, R @ t_t + t
    return R_t, t_t


def solid_mask(v, f, lo, pitch, shape, rng):
    """voxel solid of a (possibly open / non-manifold) surface: shell from dense surface samples, sealed by one voxel of dilation, exterior flood-filled from the grid corner, eroded back.
    Returns (mask, ok): ok = the filled volume agrees with the mesh's signed volume (0.7-1.4) so the surface really enclosed something."""
    from scipy import ndimage as ndi
    A = C.area(v, f)
    n = int(min(max(4.0 * A / pitch ** 2, 3000), 350000))
    P = C.area_samples(v, f, n, rng)
    idx = np.floor((P - lo) / pitch).astype(int)
    idx = np.clip(idx, 0, np.array(shape) - 1)
    shell = np.zeros(shape, bool); shell[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    shell_d = ndi.binary_dilation(shell, iterations=1)
    lab, nl = ndi.label(~shell_d)
    ext = lab == lab[0, 0, 0]
    solid = ndi.binary_erosion(~ext, iterations=1)
    vol = solid.sum() * pitch ** 3
    sv = abs(C.signed_volume(v, f))
    ok = bool(solid.sum() >= 8 and solid.sum() >= 0.35 * shell.sum())        # an enclosed solid is much thicker than the shell; a leaking (open) surface leaves almost nothing
    return solid, ok, float(vol), shell


def voxel_pair(vA, fA, vB, fB, tf, rng, force_shell=False):
    """IoU of two structures on a common grid -> (iou, kind, pitch, volA, volB) ; kind 'volume' when both surfaces enclose a solid, else 'shell' (surface voxels with one voxel of tolerance)"""
    if tf is not None:
        vB = vB @ tf[0].T + tf[1]
    lo = np.minimum(vA.min(0), vB.min(0)) - 3.0; hi = np.maximum(vA.max(0), vB.max(0)) + 3.0
    ext = float((hi - lo).max())
    pitch = float(np.clip(ext / 70.0, 0.8, 3.0))
    shape = tuple(np.ceil((hi - lo) / pitch).astype(int) + 1)
    while np.prod(shape) > 6.0e6:
        pitch *= 1.25; shape = tuple(np.ceil((hi - lo) / pitch).astype(int) + 1)
    sa, oka, va, sha = solid_mask(vA, fA, lo, pitch, shape, rng)
    sb, okb, vb, shb = solid_mask(vB, fB, lo, pitch, shape, rng)
    if oka and okb and not force_shell:
        u = (sa | sb).sum()
        return float((sa & sb).sum() / u) if u else float("nan"), "volume", pitch, va, vb
    from scipy import ndimage as ndi
    da, db = ndi.binary_dilation(sha, iterations=1), ndi.binary_dilation(shb, iterations=1)
    inter = (sha & db).sum() + (shb & da).sum(); uni = sha.sum() + shb.sum()
    return float(inter / uni) if uni else float("nan"), "shell", pitch, (va if oka else None), (vb if okb else None)


def pair_metrics(job):
    from scipy.spatial import cKDTree
    S, plane = G_S
    ur, ul = job
    vr, fr = C.merge(S, ur); vl, fl = C.merge(S, ul)
    vm, fm = plane.reflect_mesh(vl, fl)                       # left mirrored onto the right
    mr, wr = _wt(vr, fr); ml, wl = _wt(vm, fm)
    vol = lambda v, f, m, w: abs(float(m.volume)) if (w and m is not None) else None
    Vr, Vl = vol(vr, fr, mr, wr), vol(vm, fm, ml, wl)
    Ar, Al = C.area(vr, fr), C.area(vm, fm)
    rng = np.random.default_rng(0)
    A = C.area_samples(vr, fr, 2000, rng); B = C.area_samples(vm, fm, 2000, rng)
    tA, tB = cKDTree(A), cKDTree(B)
    d_ab = tB.query(A)[0]; d_ba = tA.query(B)[0]
    dd = np.concatenate([d_ab, d_ba])
    cA, cB = A.mean(0), B.mean(0)
    off = cB - cA
    R, t = icp(B, A, tA)
    B2 = B @ R.T + t
    dd2 = np.concatenate([cKDTree(B2).query(A)[0], tA.query(B2)[0]])
    ang = float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))
    rng2 = np.random.default_rng(1)
    sheet = S[ur[0]]["sys"] in SHEETS                          # skin / fascia are sheets: area, not volume, and no solid IoU
    try:
        if sheet:
            iou0, kind0, p0, va0, vb0 = voxel_pair(vr, fr, vm, fm, None, rng2, force_shell=True)
            iou1, kind1, p1, va1, vb1 = voxel_pair(vr, fr, vm, fm, (R, t), rng2, force_shell=True)
        else:
            iou0, kind0, p0, va0, vb0 = voxel_pair(vr, fr, vm, fm, None, rng2)
            iou1, kind1, p1, va1, vb1 = voxel_pair(vr, fr, vm, fm, (R, t), rng2)
    except Exception as e:
        iou0 = iou1 = float("nan"); kind0 = kind1 = "error"; p0 = None; va0 = vb0 = None
    if sheet:
        Vr_, Vl_, basis = None, None, "area"
    elif wr and wl:                                          # exact volumes of two closed meshes
        Vr_, Vl_, basis = Vr, Vl, "volume"
    elif va0 is not None and vb0 is not None:                # voxel volumes of two enclosing (open / non-manifold) surfaces
        Vr_, Vl_, basis = va0, vb0, "volume (voxel)"
    else:
        Vr_, Vl_, basis = None, None, "area"
    ratio = (Vr_ / Vl_) if basis != "area" and Vl_ > 0 else (Ar / Al if Al > 0 else float("nan"))
    thick = (2.0 * Vr_ / Ar) if (Vr_ is not None and Ar > 0) else None      # mean thickness 2V/A (mm): a tube of radius r gives r
    thin = bool(thick is not None and thick < THIN_MM)
    r = lambda x, n=2: (None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n))
    return dict(ids_r=ur and [S[i]["id"] for i in ur], vol_r_cm3=r(Vr_ / 1000, 3) if Vr_ is not None else None, vol_l_cm3=r(Vl_ / 1000, 3) if Vl_ is not None else None,
                area_r_cm2=r(Ar / 100, 2), area_l_cm2=r(Al / 100, 2), watertight=bool(wr and wl), ratio_basis=basis, ratio_r_over_l=r(ratio, 3), area_ratio_r_over_l=r(Ar / Al if Al > 0 else float("nan"), 3), thickness_mm=r(thick, 1) if thick is not None else None, thin=thin,
                centroid_offset_mm=r(np.linalg.norm(off)), centroid_offset_xyz_mm=[r(x, 1) for x in off],
                msd_mm=r(np.median(dd)), hd95_mm=r(np.percentile(dd, 95)), hd_max_mm=r(dd.max()),
                icp_translation_mm=r(np.linalg.norm(t)), icp_rotation_deg=r(ang, 1), msd_aligned_mm=r(np.median(dd2)), hd95_aligned_mm=r(np.percentile(dd2, 95)),
                iou_mirror=r(iou0, 3), iou_aligned=r(iou1, 3), iou_kind=kind1, iou_pitch_mm=r(p1, 2))


def init_worker(S, plane):
    global G_S
    G_S = (S, plane)


def tier_of(m):
    """major: ratio outside 0.67-1.5 or aligned IoU < 0.3 (volume); flag: any owner threshold crossed; ok"""
    rr, io = m["ratio_r_over_l"], m["iou_aligned"]
    if (rr is not None and (rr < 0.67 or rr > 1.5)) or (io is not None and m["iou_kind"] == "volume" and not m.get("thin") and io < 0.3):
        return "major"
    return "flag" if flags_of(m, "") else "ok"


def flags_of(m, sy):
    fl = []
    rr = m["ratio_r_over_l"]
    if rr is not None and (rr < RATIO_LO or rr > RATIO_HI): fl.append(f"{m['ratio_basis']} ratio R/L {rr}")
    if m["iou_aligned"] is not None and m["iou_kind"] == "volume" and not m.get("thin") and m["iou_aligned"] < IOU_MIN: fl.append(f"IoU {m['iou_aligned']} after mirroring + rigid alignment")
    return fl


def run_page(k, jobs=4, with_metrics=True):
    t0 = time.time()
    S = C.load(k); C.groups_of(S)
    plane, q = C.fit_midsagittal(S)
    units, G = classify(S, plane)
    tg = C.PAGES[k]
    # the structures-by-id table
    pairs = [u for u in units if "ids_r" in u and "ids_l" in u]
    if tg[2] == "own":
        sys.path.insert(0, str(REPO))
        from scripts import audit_q189_model_separation as AUD
        by = {}
        for x in S: by.setdefault(x["id"], x)
        cl = lambda ids: sorted({AUD.classify(by[i]["src"], (by[i]["rec"] or {}).get("procedural_badge"))[0] for i in ids})
        for u in units:
            for sd in ("r", "l", "m"):
                if "ids_" + sd in u: u["class_" + sd] = cl(u["ids_" + sd])
    if with_metrics:
        idx_of = {}
        for x in S: idx_of.setdefault(x["id"], []).append(x["idx"])
        jl = []
        for u in pairs:
            jl.append(([i for d in u["ids_r"] for i in idx_of[d]], [i for d in u["ids_l"] for i in idx_of[d]]))
        if jobs > 1:
            with Pool(jobs, initializer=init_worker, initargs=(S, plane)) as pool:
                res = pool.map(pair_metrics, jl, chunksize=8)
        else:
            init_worker(S, plane); res = [pair_metrics(j) for j in jl]
        for u, m in zip(pairs, res):
            m.pop("ids_r", None); u["metrics"] = m
            u["flags"] = flags_of(m, u["sys"]); u["tier"] = tier_of(m)
            if m["centroid_offset_mm"] is not None and m["centroid_offset_mm"] > 30: u["posed_differently_mm"] = m["centroid_offset_mm"]
            rr = m["ratio_r_over_l"]
            if u["cls"] == "paired" and rr is not None and (rr < MUCH_SMALLER[0] or rr > MUCH_SMALLER[1]):
                u["cls_before"] = "paired"; u["cls"] = "unmatched"; u["kind"] = "much_smaller"
                u["why"] = f"one side much smaller: {m['ratio_basis']} ratio R/L {rr}"
    return dict(page=k, label=tg[3], dir=os.environ.get("Q237_SRC_" + k, tg[0]), n_structures=len(S), n_groups=len(G), plane=dict(n=[round(float(x), 6) for x in plane.n], d_mm=round(plane.d, 3), tilt=plane.tilt_deg(), quality=q), units=units,
                seconds=round(time.time() - t0, 1))


import os


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--pages", default=",".join(C.KEYS)); ap.add_argument("--no-metrics", action="store_true"); ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out", default=str(OUT)); a = ap.parse_args()
    import collections
    out = {}
    for k in a.pages.split(","):
        r = run_page(k, a.jobs, not a.no_metrics); out[k] = r
        cnt = collections.Counter(u["cls"] for u in r["units"])
        nfl = sum(1 for u in r["units"] if u.get("flags"))
        print(k, r["n_structures"], dict(cnt), "flagged", nfl, "plane", r["plane"]["n"], r["plane"]["d_mm"], r["seconds"], "s", flush=True)
        Path(a.out).with_suffix(".partial.json").write_text(json.dumps(out, default=float))
    Path(a.out).write_text(json.dumps(dict(generated=datetime.date.today().isoformat(), thresholds=dict(ratio_lo=RATIO_LO, ratio_hi=RATIO_HI, iou_min=IOU_MIN, much_smaller=MUCH_SMALLER), pages=out), separators=(",", ":"), default=float))
    Path(a.out).with_suffix(".partial.json").unlink(missing_ok=True)
