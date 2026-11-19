#!/usr/bin/env python3
"""Q304 Part A validation: the transferred nerves measured against the page they are going onto.

    python3 scripts/anatomy/q304/val304.py [own_m own_f] [--nerves /dev/shm/q304/nerves] [--src build/q303]

Reuses Q299's containment test verbatim (scripts/anatomy/q299/contain299.py): a voxelised body mask built from the
page's OWN outer tissues, validated before use, with distances read off a cKDTree of real skin surface samples; and
Q299's per-bone solidified boxes for bone penetration (never one global bone mask -- Q299 recorded that a global mask
closes the bony rings and its hole fill then calls half the aorta "inside a bone").

Checks, each reported as a number and not as a verdict:
  A  no penetration of skin  -- vertices outside the page's own body mask, and how far
  B  no penetration of bone  -- vertices inside the page's own per-bone masks, and how deep
  C  plausible course past the fibular neck -- the common fibular nerve's own y-range against the page's own fibular
     head, the minimum distance from the nerve to the fibular neck, and whether the deep / superficial fibular
     branches continue from it
  D  left / right consistency -- the mirror distance of each sided pair about the page's own midsagittal plane
  E  realness -- mean dihedral against the CVH reference meshes (31.7 / 27.6 / 29.5 deg), defect edges, volume, triangles
  F  overlap with what the page already carries for the same nerve (the duplication, measured)
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO, REPO / "scripts/anatomy/q299", REPO / "scripts/anatomy/q241", REPO / "scripts/anatomy/q237"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import contain299 as CT   # noqa: E402
import model as MD        # noqa: E402

CVH = (31.7, 27.6, 29.5)
OUT = REPO / "data/derived/Q304_nerve_validation.json"


def defect_pct(V, F):
    m = trimesh.Trimesh(V, F, process=False)
    e = m.edges_sorted
    import collections
    c = collections.Counter(map(tuple, e))
    bad = sum(1 for v in c.values() if v != 2)
    return round(100.0 * bad / max(len(c), 1), 2)


def mirror_pairs(items):
    out = {}
    for sid in items:
        if sid.endswith("_l"):
            r = sid[:-2] + "_r"
            if r in items:
                out[sid[:-2]] = (sid, r)
    return out


def run(key, nerves_dir, src):
    import os
    os.environ["Q237_SRC_" + key] = str(REPO / src / MD.SRC[key].split("/")[-1]) if not str(src).startswith("/") else str(Path(src) / MD.SRC[key].split("/")[-1])
    items = json.loads((Path(nerves_dir) / f"{key}_nerves.json").read_text())
    z = np.load(Path(nerves_dir) / f"{key}_nerves.npz")
    print(key, "building the Q299 body mask from the page's own outer tissues ...", flush=True)
    B = CT.build(key, 2.0)
    val = CT.validate(B)
    print(key, "mask", B["g"].shape, "vol", B["skin_volume_cm3"], "cm3",
          "valid" if val["ok"] else "INVALID: " + "; ".join(val["reasons"]), flush=True)
    g, body, bones, st, bt = B["g"], B["body"], B["bones"], B["skin_tree"], B["bone_tree"]
    S = B["S"]
    own_by_id = {x["id"]: x for x in S}
    rows = {}
    rng = np.random.default_rng(11)
    for sid, d in sorted(items.items()):
        V = z[sid + "__v"].astype(float); F = z[sid + "__f"].astype(np.int64)
        P = CT.tri_samples(V, F, 1.0, rng, cap=40000)
        ins = g.inside(body, P)
        r = dict(id=sid, n_samples=int(len(P)))
        if not ins.all():
            Q = P[~ins]; dd = st.query(Q, workers=-1)[0]
            r.update(out_n=int(len(Q)), out_frac=round(float(len(Q)) / len(P), 5),
                     out_max_mm=round(float(dd.max()), 2), out_p95_mm=round(float(np.quantile(dd, 0.95)), 2),
                     out_beyond_5mm=int((dd > 5.0).sum()))
        else:
            r.update(out_n=0, out_max_mm=0.0, out_beyond_5mm=0)
        pen = np.zeros(len(P), bool); which = []
        lo, hi = P.min(0), P.max(0)
        for b in bones:
            if (b.hi < lo).any() or (b.lo > hi).any():
                continue
            h = b.inside(P)
            if h.any():
                pen |= h; which.append((b.id, int(h.sum())))
        if pen.any():
            ddb = bt.query(P[pen], workers=-1)[0]
            r.update(bone_in_n=int(pen.sum()), bone_in_frac=round(float(pen.sum()) / len(P), 5),
                     bone_depth_max_mm=round(float(ddb.max()), 2),
                     bones=sorted(which, key=lambda t: -t[1])[:4])
        else:
            r.update(bone_in_n=0, bone_depth_max_mm=0.0)
        r.update(dihedral_mean_deg=d["dihedral_mean_deg"], defect_edges_pct=defect_pct(V, F),
                 cm3_abs=round(abs(d["cm3"]), 4), tris=d["tris"])
        # F: overlap with what the page already carries for the same nerve
        dup = d.get("already_on_page_same_nerve") or []
        if dup:
            ov = []
            for o in dup:
                x = own_by_id.get(o)
                if x is None:
                    continue
                t = cKDTree(CT.tri_samples(x["v"], x["f"], 1.0, rng, cap=40000))
                dd2 = t.query(P, workers=-1)[0]
                ov.append(dict(id=o, within_3mm_pct=round(100.0 * float((dd2 <= 3.0).mean()), 1),
                               min_mm=round(float(dd2.min()), 2), median_mm=round(float(np.median(dd2)), 2)))
            r["duplicates"] = ov
        rows[sid] = r
    # C: the fibular neck
    fib = {}
    for side in ("l", "r"):
        nb = own_by_id.get(f"fibula_{side}")
        cf = f"common_fibular_n_{side}"
        if nb is None or cf not in items:
            continue
        fv = nb["v"]
        head_y = float(np.quantile(fv[:, 1], 0.97))          # the proximal 3 % of the page's own fibula = the head
        neck = fv[(fv[:, 1] > head_y - 40) & (fv[:, 1] < head_y)]
        V = z[cf + "__v"].astype(float)
        dn = cKDTree(neck).query(V, workers=-1)[0] if len(neck) else np.array([np.inf])
        cont = {}
        for br in (f"deep_fibular_n_{side}", f"superficial_fibular_n_{side}"):
            if br in items:
                W = z[br + "__v"].astype(float)
                cont[br] = dict(gap_mm=round(float(cKDTree(V).query(W, workers=-1)[0].min()), 2),
                                y_range=[round(float(W[:, 1].min()), 1), round(float(W[:, 1].max()), 1)])
        fib[side] = dict(fibular_head_y=round(head_y, 1), fibula_y_range=[round(float(fv[:, 1].min()), 1), round(float(fv[:, 1].max()), 1)],
                         nerve_y_range=[round(float(V[:, 1].min()), 1), round(float(V[:, 1].max()), 1)],
                         min_dist_to_fibular_neck_mm=round(float(dn.min()), 2),
                         crosses_head_level=bool(V[:, 1].min() < head_y < V[:, 1].max()),
                         branches=cont)
    # D: left / right consistency. NOT mirror symmetry about the page's own midsagittal plane -- Q296 learned that
    # lesson on Combined M, and on the Imaging pages it is even starker: the Visible Human male's own FIBULA has a
    # mirror median of 76.7 mm on his own page because his two legs were scanned in different positions (the DU
    # lower-extremity release). So the criterion is that a transferred nerve pair is no more asymmetric than the
    # page's OWN SKELETON is at the same level: the nerve pair's mirror median against the mirror median of the
    # page's own bone group nearest to it, measured here on both pages with the identical rule.
    pj = json.loads((REPO / "data/derived/Q237_pairing.json").read_text())["pages"][key]["plane"]
    n = np.array(pj["n"], float); n /= np.linalg.norm(n); dpl = float(pj["d_mm"])

    def mirror_med(A, Bv):
        Am = A - 2 * ((A @ n) - dpl)[:, None] * n[None, :]
        dd = cKDTree(Bv).query(Am, workers=-1)[0]
        return round(float(np.median(dd)), 2), round(float(np.quantile(dd, 0.95)), 2)

    import xfer304 as XF
    own_bones = MD.Model(key).bones()
    bg = XF.aligned(own_bones, own_bones)          # the same groups, both sides, on the Imaging page's own bones
    bone_mirror = {}
    bone_tree_by_group = {}
    for gname in sorted(bg):
        if not gname.endswith("_l"):
            continue
        rname = gname[:-2] + "_r"
        if rname not in bg:
            continue
        A = bg[gname][1]["v"]; Bv = bg[rname][1]["v"]
        m, p = mirror_med(A, Bv)
        bone_mirror[gname[:-2]] = dict(median_mm=m, p95_mm=p)
    for gname in sorted(bg):
        bone_tree_by_group[gname] = cKDTree(bg[gname][1]["v"])
    mir = {}
    for base, (li, ri) in sorted(mirror_pairs(items).items()):
        A = z[li + "__v"].astype(float); Bv = z[ri + "__v"].astype(float)
        m, p = mirror_med(A, Bv)
        # the nearest bone group of the LEFT member
        best, bd = None, 1e9
        for gname, t in bone_tree_by_group.items():
            if not gname.endswith("_l"):
                continue
            dd = float(t.query(A[:: max(1, len(A) // 300)], workers=-1)[0].min())
            if dd < bd:
                best, bd = gname[:-2], dd
        mir[base] = dict(median_mm=m, p95_mm=p,
                         cm3_l=round(abs(items[li]["cm3"]), 4), cm3_r=round(abs(items[ri]["cm3"]), 4),
                         nearest_bone_group=best, nearest_bone_mm=round(bd, 2),
                         bone_mirror_median_mm=(bone_mirror.get(best) or {}).get("median_mm"),
                         ratio_to_bone=(round(m / bone_mirror[best]["median_mm"], 2)
                                        if best in bone_mirror and bone_mirror[best]["median_mm"] > 0.01 else None))
    out = dict(page=key, src=str(src), mask=dict(volume_cm3=B["skin_volume_cm3"], error_band=B["error_band"]),
               mask_validation=val, n=len(rows),
               skin=dict(n_with_any_outside=sum(1 for r in rows.values() if r["out_n"]),
                         n_beyond_5mm=sum(1 for r in rows.values() if r["out_beyond_5mm"]),
                         worst_mm=round(max(r["out_max_mm"] for r in rows.values()), 2)),
               bone=dict(n_with_any_inside=sum(1 for r in rows.values() if r["bone_in_n"]),
                         n_mostly_inside=sum(1 for r in rows.values() if r.get("bone_in_frac", 0) > 0.5),
                         worst_depth_mm=round(max(r["bone_depth_max_mm"] for r in rows.values()), 2)),
               dihedral=dict(min=min(r["dihedral_mean_deg"] for r in rows.values()),
                             max=max(r["dihedral_mean_deg"] for r in rows.values()),
                             cvh_reference_deg=list(CVH)),
               fibular_neck=fib, mirror=mir, bone_mirror=bone_mirror, structures=rows)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--nerves", default="/dev/shm/q304/nerves")
    ap.add_argument("--src", default="build/q303")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    rep = json.loads(Path(a.out).read_text()) if Path(a.out).exists() else {}
    for key in (a.keys or ["own_m", "own_f"]):
        r = run(key, a.nerves, a.src)
        rep[key] = r
        print(key, "skin:", r["skin"], flush=True)
        print(key, "bone:", r["bone"], flush=True)
        print(key, "fibular neck:", json.dumps(r["fibular_neck"]), flush=True)
        print(key, "mirror worst:", max((v["median_mm"] for v in r["mirror"].values()), default=None),
              "pairs", len(r["mirror"]), flush=True)
    rep["_README"] = ["Q304 Part A validation (scripts/anatomy/q304/val304.py): the transferred nerves against the "
                      "Imaging page's own skin / bones, by Q299's containment test."]
    Path(a.out).write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")
    print("->", a.out)


if __name__ == "__main__":
    main()
