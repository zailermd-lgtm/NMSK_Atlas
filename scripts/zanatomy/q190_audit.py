"""Q190 audit: per-structure distortion (stretch vs the Z source, flips), L/R symmetry, neighbour overlap, distance to her label,
skin/bone containment.  All on full-resolution fitted meshes (the pending list of the build / its npz dump)."""
from __future__ import annotations

import re

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q190_metrics as Mx
from scripts.zanatomy import q190_refine as Q

REGIONS = {   # name -> (y range, |x| max, predicate on id)
    "lumbar": ((100, 290), 110), "sacral/gluteal/hip": ((-150, 100), 200), "abdomen": ((100, 420), 110),
    "thoracic back/shoulder": ((290, 640), 200),
}
HAND = re.compile(r"forearm|wrist|hand|digit|palm|pollic|carpal|radial|ulnar|antebrach|metacarp|interossei|lumbrical|thumb|finger|median_n|"
                  r"supinator|pronator|flexor_|extensor_|perionyx|nail|lunate|scaphoid|phalan|trapezium|trapezoid|capitate|hamate|pisiform|triquetr|"
                  r"stylo|hyoid|digastric|tongue|larynx|thyroid|mandib|cranial|ear|eye|nose|teeth|tooth|scalp|face|facial|cervical_n|cerebr|brain|"
                  r"nucleus|ventric|artery_of_penis|penis|testis|scrot|prostate|vas_def|epididym|seminal|glans|ductus")


def region_of(d):
    c = d["v"].mean(0)
    for name, ((y0, y1), xm) in REGIONS.items():
        if y0 <= c[1] < y1 and abs(c[0]) < xm:
            return name
    return None


def table(structs, newv=None):
    """{id: {cat, region, stretch}} for the trunk/pelvis/hip/shoulder structures; newv: {id: v} overrides"""
    out = {}
    for d in structs:
        if HAND.search(d["id"]):
            continue
        rg = region_of(d)
        if rg is None:
            continue
        v = newv.get(d["id"], d["v"]) if newv else d["v"]
        st = Mx.stretch_stats(v, d["r"], d["f"])
        if st is None:
            continue
        out[d["id"]] = {"cat": d["cat"], "region": rg, "stretch": st, "score": Mx.distortion_score(st), "n_faces": st["n_faces"]}
    return out


def lr_symmetry(structs, axis, newv=None, her=None, ids=None):
    """mirror each left structure about her trunk axis (x' = 2 xc(y) - x) and report the two-way surface chamfer (mean mm) to its right
    partner; her own pairs give the baseline (her real asymmetry)"""
    byid = {d["id"]: d for d in structs}
    res = {}
    for k, d in byid.items():
        if not k.endswith("_l") or HAND.search(k) or d["cat"] not in ("muscle", "fascia"):
            continue
        r = byid.get(k[:-2] + "_r")
        if r is None or region_of(d) is None or (ids is not None and k not in ids):
            continue
        vl = newv.get(k, d["v"]) if newv else d["v"]
        vr = newv.get(r["id"], r["v"]) if newv else r["v"]
        xc, _ = axis(vl[:, 1])
        m = vl.copy(); m[:, 0] = 2 * xc - m[:, 0]
        fl = d["f"][:, [0, 2, 1]]
        a, b = Mx.two_way(m, fl, vr, r["f"], n=2500)
        res[k[:-2]] = 0.5 * (a + b)
    base = {}
    if her is not None:
        for k in res:
            hl, hr = her.get(k + "_l"), her.get(k + "_r")
            if hl is None or hr is None:
                continue
            vl = hl["v"].astype(float)
            xc, _ = axis(vl[:, 1])
            m = vl.copy(); m[:, 0] = 2 * xc - m[:, 0]
            a, b = Mx.two_way(m, hl["f"][:, [0, 2, 1]].astype(int), hr["v"].astype(float), hr["f"].astype(int), n=2500)
            base[k] = 0.5 * (a + b)
    return res, base


def overlap(structs, newv=None, ids=None, nsamp=1500, seed=0):
    """fraction of each trunk muscle's vertices lying INSIDE another (closed) trunk muscle; ray-parity containment"""
    import trimesh
    rng = np.random.default_rng(seed)
    cand = [d for d in structs if d["cat"] == "muscle" and region_of(d) is not None and not HAND.search(d["id"]) and Q._closed(d["f"])]
    meshes = {}
    for d in cand:
        v = newv.get(d["id"], d["v"]) if newv else d["v"]
        meshes[d["id"]] = (trimesh.Trimesh(v, d["f"], process=False), v.min(0), v.max(0))
    out = {}
    for d in structs:
        if d["cat"] != "muscle" or region_of(d) is None or HAND.search(d["id"]) or (ids is not None and d["id"] not in ids):
            continue
        v = newv.get(d["id"], d["v"]) if newv else d["v"]
        p = v[rng.choice(len(v), min(len(v), nsamp), replace=False)]
        inside = np.zeros(len(p), bool)
        for k, (m, lo, hi) in meshes.items():
            if k == d["id"]:
                continue
            sel = np.flatnonzero(np.all((p >= lo - 1) & (p <= hi + 1), 1) & ~inside)
            if len(sel):
                try:
                    c = m.contains(p[sel])
                except Exception:
                    continue
                # a point deeper than 1 mm: require it to be inside after a 1 mm inward test of a neighbour is not available; plain parity
                inside[sel[c]] = True
        out[d["id"]] = float(inside.mean())
    return out
