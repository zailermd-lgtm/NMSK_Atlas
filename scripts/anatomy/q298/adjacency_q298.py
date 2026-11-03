#!/usr/bin/env python3
"""Q298 "Adjacent": which structures physically neighbour which, measured on each page's OWN shipped meshes.

Criterion, stated exactly because the card and the UI quote it:
  every triangle of every structure is SAMPLED so that no point of it is further than CELL/2 mm from a sample (the
  triangle's vertices, plus a stratified barycentric sample per triangle at a density set by its area), the samples are
  rasterised into a shared CELL = 2.0 mm voxel grid, and two structures are ADJACENT when a voxel of one touches a voxel
  of the other in the 3x3x3 neighbourhood. The STRICT surface-to-surface bound that implies is sqrt(3) * 2 * cell = 6.93 mm
  (Q308's correction: sqrt(3) * cell = 3.46 mm bounds the two voxel CENTRES, not the surface points), and
  under 2.0 mm for a face-touching pair. Sampling, not vertex-to-vertex distance, is the reason this is honest: 69 % of the
  triangles on a Z page have a longest edge over 3 mm and the longest is 134 mm, so a vertex-to-vertex test would miss most
  real contacts.

It is a MEASUREMENT, not an anatomical claim: two structures can be adjacent in the mesh and not be related, and the UI
says so ("measured on this page's geometry").

    python3 scripts/anatomy/q298/adjacency_q298.py [KEY...] [--src build/q297] [--cell 2.0]
    python3 scripts/anatomy/q298/adjacency_q298.py --isolated [KEY...]   # record the real nearest distance of any structure with no neighbour
-> data/derived/Q298_adjacency_<key>.json  {ids, adj (index lists), threshold_mm (the STRICT bound), threshold_voxel_centres_mm, threshold_note, cell_mm, pairs, how, per_structure, isolated_ids}
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pagedata as P  # noqa: E402

REPO = P.REPO
DERIVED = REPO / "data/derived"
CELL = 2.0
MAXSAMP = 4_000_000        # per structure; only the whole-body skin patch comes near it
OFF = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)]
HALF = [o for o in OFF if o > (0, 0, 0)]          # one of each unordered offset pair; (0,0,0) handled separately
BIAS = 1 << 20


def samples(v, f, cell):
    """Surface sample points: every vertex, plus uniform barycentric samples at one per (cell/2)^2 mm2 of triangle area
    (mean spacing cell/2, so no point of a triangle is further than ~cell/2 from a sample)."""
    if len(f) == 0:
        return v
    tv = v[f]
    e0, e1 = tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0]
    area = 0.5 * np.linalg.norm(np.cross(e0, e1), axis=1)
    step = cell * 0.5
    n = np.ceil(area / (step * step)).astype(np.int64)              # one sample per (cell/2)^2 of surface area
    n = np.clip(n, 0, 1 << 20)
    tot = int(n.sum())
    if tot > MAXSAMP:                                              # keep the cost bounded, uniformly
        n = np.maximum((n * (MAXSAMP / tot)).astype(np.int64), np.where(n > 0, 1, 0))
        tot = int(n.sum())
    if tot == 0:
        return v
    idx = np.repeat(np.arange(len(f)), n)
    rng = np.random.default_rng(20298)
    r1, r2 = rng.random(tot), rng.random(tot)
    s = np.sqrt(r1)
    a, b = 1.0 - s, s * (1.0 - r2)
    # uniform barycentric sample of a triangle: s = sqrt(r1); P = (1-s)A + s(1-r2)B + s*r2*C
    pts = tv[idx, 0] * a[:, None] + tv[idx, 1] * b[:, None] + tv[idx, 2] * (s * r2)[:, None]
    return np.vstack([v, pts.astype(np.float32)])


def cells_of(v, f, cell):
    """Sorted unique int64 voxel keys this structure's surface occupies."""
    p = samples(v, f, cell)
    q = np.floor(p / cell).astype(np.int64) + BIAS
    if q.min() < 0 or q.max() >= 2 * BIAS:
        raise SystemExit("voxel coordinate out of the packing range")
    k = (q[:, 0] << 42) | (q[:, 1] << 21) | q[:, 2]
    return np.unique(k)


def _shift(keys, o):
    return keys + (np.int64(o[0]) << 42) + (np.int64(o[1]) << 21) + np.int64(o[2])


def build(key, src, cell=CELL):
    t0 = time.time()
    ss = P.structures(key, src)
    ids = [s["id"] for s in ss]
    cl, counts = [], []
    for i, sid, v, f in P.meshes(key, src):
        c = cells_of(v, f, cell)
        cl.append(c)
        counts.append(len(c))
    assert len(cl) == len(ids), (len(cl), len(ids))
    print(f"{key}: {len(ids)} structures, {sum(counts):,} occupied {cell} mm voxels, {time.time() - t0:.0f}s")

    lab = np.concatenate([np.full(len(cl[i]), i, np.int32) for i in range(len(cl)) if len(cl[i])]) if cl else np.zeros(0, np.int32)
    allk = np.concatenate([c for c in cl if len(c)]) if cl else np.zeros(0, np.int64)
    order = np.argsort(allk, kind="stable")
    allk, lab = allk[order], lab[order]
    uniq, start = np.unique(allk, return_index=True)
    stop = np.append(start[1:], len(allk))
    nlab = stop - start

    pair = []
    # offset (0,0,0) covers "several structures in the SAME voxel"; the 13 half-space offsets cover the touching ones,
    # each unordered offset pair only once. All of it is vectorised: a per-voxel Python loop is far too slow at 3,300
    # structures (measured: minutes per page against seconds here).
    for o in [(0, 0, 0)] + HALF:
        sk = _shift(allk, o)
        t = np.searchsorted(uniq, sk)
        ok = (t < len(uniq)) & (uniq[np.minimum(t, len(uniq) - 1)] == sk)
        if not ok.any():
            continue
        srcl = lab[ok]
        t = t[ok]
        rep = nlab[t]
        a = np.repeat(srcl, rep)
        gi = np.repeat(start[t], rep) + (np.arange(rep.sum()) - np.repeat(np.cumsum(rep) - rep, rep))
        b = lab[gi]
        m = a != b
        pair.append(np.stack([np.minimum(a[m], b[m]), np.maximum(a[m], b[m])], 1))
    pr = np.unique(np.concatenate(pair, 0), axis=0) if pair else np.zeros((0, 2), np.int32)
    adj = [[] for _ in ids]
    for a, b in pr:
        adj[int(a)].append(int(b))
        adj[int(b)].append(int(a))
    adj = [sorted(x) for x in adj]
    deg = np.array([len(x) for x in adj])
    out = {"schema": "nmsk.adjacency.v1", "round": "Q298", "key": key, "src": str(src),
           # Q308 CORRECTION (Q306 measured it, Q306 could not publish it). `threshold_mm` is the number the
           # page PRINTS, and it was sqrt(3) * cell = 3.46 mm -- which is the bound on the two VOXEL CENTRES,
           # not on the surface points. Two samples whose voxel indices differ by at most 1 per axis lie in a
           # box 2 * cell on a side, so the strict bound on their separation is sqrt(3) * 2 * cell = 6.93 mm.
           # The page now prints the bound that CANNOT be exceeded, and the voxel-centre figure and the
           # measured distribution ride beside it so the claim is honest in both directions: measured on 120
           # random adjacent pairs of Imaging M, median 0.18 mm, mean 0.97, p95 3.64, max 4.45, with 10 of 120
           # past 3.46 (data/derived/Q306_adjacency_threshold.json).
           "cell_mm": cell, "threshold_mm": round(float(np.sqrt(3) * 2 * cell), 2),
           "threshold_voxel_centres_mm": round(float(np.sqrt(3) * cell), 2),
           "threshold_note": ("the strict surface-to-surface bound implied by 3x3x3 voxel contact is "
                              "sqrt(3) * 2 * cell; sqrt(3) * cell bounds the voxel CENTRES only. Measured on "
                              "120 random adjacent pairs of Imaging M: median 0.18 mm, mean 0.97, p95 3.64, "
                              "max 4.45, 10 of 120 past sqrt(3) * cell. Corrected in Q308."),
           "how": (f"surface samples at <= {cell / 2} mm spacing rasterised into a shared {cell} mm voxel grid; adjacent = a "
                   f"voxel of one touches a voxel of the other in the 3x3x3 neighbourhood, i.e. surface-to-surface "
                   f"separation <= {np.sqrt(3) * cell:.2f} mm (and <= {cell} mm for a face-touching pair). Measured on this "
                   f"page's own shipped meshes by scripts/anatomy/q298/adjacency_q298.py. A measurement, not an anatomical "
                   f"claim."),
           "ids": ids, "adj": adj, "pairs": int(len(pr)),
           "per_structure": {"min": int(deg.min()) if len(deg) else 0, "median": int(np.median(deg)) if len(deg) else 0,
                             "mean": round(float(deg.mean()), 1) if len(deg) else 0.0,
                             "max": int(deg.max()) if len(deg) else 0,
                             "isolated": int((deg == 0).sum())},
           "seconds": round(time.time() - t0, 1)}
    return out


def isolated(key, src):
    """For a page with structures that have NO neighbour at the threshold, measure how far away the nearest other
    structure really is and record it, so an isolated structure is a stated measurement and not a silent gap."""
    from scipy.spatial import cKDTree
    f = DERIVED / f"Q298_adjacency_{key}.json"
    out = json.loads(f.read_text(encoding="utf-8"))
    tgt = {i: out["ids"][i] for i, a in enumerate(out["adj"]) if not a}
    if not tgt:
        out["isolated_ids"] = []
        f.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
        print(f"{key}: no isolated structure")
        return
    cell = out["cell_mm"]
    pts, allp, lab = {}, [], []
    for i, sid, v, fc in P.meshes(key, src):
        sm = samples(v, fc, cell)
        if i in tgt:
            pts[i] = sm
        allp.append(sm[::5])
        lab.append(np.full(len(sm[::5]), i, np.int32))
    allp = np.vstack(allp)
    lab = np.concatenate(lab)
    rows = []
    for i, sid in sorted(tgt.items()):
        m = lab != i
        d, j = cKDTree(allp[m]).query(pts[i], k=1)
        k = int(np.argmin(d))
        rows.append({"id": sid, "nearest_mm": round(float(d.min()), 2), "nearest_id": out["ids"][int(lab[m][j[k]])]})
        print(f"  {sid}: nearest other structure {rows[-1]['nearest_mm']} mm ({rows[-1]['nearest_id']})")
    out["isolated_ids"] = rows
    f.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{key}: {len(rows)} isolated structure(s) recorded in {f.name}")


def main(argv):
    src, cell = "build/q297", CELL
    if "--src" in argv:
        i = argv.index("--src"); src = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    if "--cell" in argv:
        i = argv.index("--cell"); cell = float(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    DERIVED.mkdir(parents=True, exist_ok=True)
    if "--isolated" in argv:
        argv = [a for a in argv if a != "--isolated"]
        for key in (argv or P.KEYS):
            isolated(key, src)
        return 0
    for key in (argv or P.KEYS):
        out = build(key, src, cell)
        p = DERIVED / f"Q298_adjacency_{key}.json"
        p.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
        ps = out["per_structure"]
        print(f"  {out['pairs']:,} adjacent pairs; per structure min {ps['min']} median {ps['median']} "
              f"mean {ps['mean']} max {ps['max']}, {ps['isolated']} isolated -> {p.name} "
              f"({p.stat().st_size / 1024:.0f} KB, {out['seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
