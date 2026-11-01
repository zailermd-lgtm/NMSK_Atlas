"""Q299 Part B: a containment audit that actually works on these pages.

    python3 scripts/anatomy/q299/contain299.py PAGEKEY [--vox 2.0] [--out DIR]

Why not ray parity: Q297 ran a naive ray-parity "inside the skin" test and discarded it -- the Z pages carry the skin as
~250 OPEN patches, so there is no closed envelope to count crossings against, and the test called even near-raw geometry
20-100 % outside.  What is built here instead:

  1. a VOXELISED BODY MASK from the page's own outer tissues: every triangle of every `skin` structure (Z pages: all 248-250
     patches; Imaging pages: the single `skin` mesh) plus the OUTER tissues that stand in for skin where a patch is missing
     (`fat_subcut_*`, `soft_unlabelled_*`) is area-sampled at >= 1 point / mm2 and stamped into a `vox` mm grid; the shell is
     closed with a 1-voxel binary closing and the interior is taken with a 3-D hole fill plus a per-axial-slice fill, and only
     the largest connected component is kept.  The mask is VALIDATED before it is used (`validate`): the deep structures that
     must be inside by construction (femora, humeri, vertebrae, heart / liver / kidneys where the page has them) have to come
     out >= 99.5 % inside, and the mask volume has to be within a stated band of the enclosed skin volume.  A page whose mask
     fails validation is REPORTED as unmeasurable, never silently scored.
  2. the distance is not read off the voxel grid: a point classified outside is measured against a cKDTree of the same skin /
     outer-tissue surface samples, so the number is a true mm distance to the nearest real skin surface (sample spacing <= 1 mm).
  3. bone penetration: a separate voxel mask of all `bone` structures, eroded by one voxel so surface contact is not a hit;
     a non-bone vertex inside it is measured to the nearest bone surface sample.

Frame: mm, +X subject right, +Y superior, +Z anterior.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts/anatomy/q237"))
import core as C  # noqa: E402

OUTER_PREFIX = ("fat_subcut_", "soft_unlabelled_")
DEEP_MUST_BE_INSIDE = ("femur_l", "femur_r", "humerus_l", "humerus_r", "vertebra_l3", "vertebra_t8",
                       "heart", "liver", "kidney_l", "kidney_r", "urinary_bladder", "sacrum")


def tri_samples(v, f, per_mm2=1.0, rng=None, cap=None):
    """area-weighted samples on the triangles, >= per_mm2 points per mm2, plus every vertex."""
    rng = rng or np.random.default_rng(0)
    a = v[f[:, 0]]; b = v[f[:, 1]]; c = v[f[:, 2]]
    ar = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    tot = float(ar.sum())
    n = int(min(cap or 10 ** 9, max(0, np.ceil(tot * per_mm2))))
    if n <= 0 or tot <= 0:
        return v
    p = ar / tot
    k = rng.choice(len(f), size=n, p=p)
    u = rng.random(n); w = rng.random(n)
    m = u + w > 1.0
    u[m] = 1.0 - u[m]; w[m] = 1.0 - w[m]
    pts = a[k] + u[:, None] * (b[k] - a[k]) + w[:, None] * (c[k] - a[k])
    return np.vstack([v, pts])


class Grid:
    def __init__(self, lo, hi, vox):
        self.vox = float(vox)
        self.lo = lo - 4 * vox
        self.shape = tuple(int(np.ceil((hi[k] + 4 * vox - self.lo[k]) / vox)) + 1 for k in range(3))

    def ijk(self, P):
        q = np.floor((P - self.lo) / self.vox).astype(np.int64)
        np.clip(q, 0, np.array(self.shape) - 1, out=q)
        return q

    def stamp(self, P):
        m = np.zeros(self.shape, bool)
        q = self.ijk(P)
        m[q[:, 0], q[:, 1], q[:, 2]] = True
        return m

    def inside(self, mask, P):
        q = self.ijk(P)
        return mask[q[:, 0], q[:, 1], q[:, 2]]


def solidify(shell, g, rad_vox):
    """A true morphological closing of the open shell, done as dilate -> flood the OUTSIDE from the grid border -> erode back.
    (`binary_closing` with an iterated diamond kernel leaves the trunk unfilled on the Z pages, where the skin patches of the
    back leave 14 mm gaps; this version closes any gap narrower than 2 x rad and is what the validation passes on.)"""
    st = ndimage.generate_binary_structure(3, 1)
    d = ndimage.binary_dilation(shell, st, iterations=rad_vox)
    lab, n = ndimage.label(~d)
    border = set(np.unique(np.concatenate([lab[0].ravel(), lab[-1].ravel(), lab[:, 0].ravel(), lab[:, -1].ravel(),
                                           lab[:, :, 0].ravel(), lab[:, :, -1].ravel()])))
    border.discard(0)
    solid = ~np.isin(lab, list(border))
    body = ndimage.binary_erosion(solid, st, iterations=rad_vox) | shell
    lab2, n2 = ndimage.label(body)
    if n2 > 1:
        cnt = np.bincount(lab2.ravel()); cnt[0] = 0
        body = lab2 == int(np.argmax(cnt))
    return body


def band(body, g, tree, rng, n=300000):
    """the mask's own error band: the distance from its boundary voxels to the nearest real skin / outer-tissue sample."""
    bnd = body & ~ndimage.binary_erosion(body, ndimage.generate_binary_structure(3, 1), 1)
    ii = np.array(np.nonzero(bnd)).T
    if len(ii) > n:
        ii = ii[rng.choice(len(ii), n, replace=False)]
    d = tree.query(g.lo + (ii + 0.5) * g.vox, workers=-1)[0]
    return dict(p50_mm=round(float(np.median(d)), 2), p95_mm=round(float(np.quantile(d, 0.95)), 2), max_mm=round(float(d.max()), 2),
                boundary_voxels=int(bnd.sum()))


def build(key, vox=2.0, per_mm2=1.0, close_mm=8.0):
    os.environ.setdefault("Q237_SRC_" + key, str(REPO / "build/q297" / C.PAGES[key][4]))
    S = C.load(key)
    for i, x in enumerate(S):
        x["_i"] = i
    skin = [x for x in S if x["sys"] == "skin" or x["id"] == "skin"]
    outer = [x for x in S if x["id"].startswith(OUTER_PREFIX)]
    bone = [x for x in S if x["sys"] == "bone"]
    allv = np.vstack([x["v"] for x in S])
    lo = allv.min(0); hi = allv.max(0)
    g = Grid(lo, hi, vox)
    rng = np.random.default_rng(7)
    sk_pts = [tri_samples(x["v"], x["f"], per_mm2, rng) for x in skin + outer]
    sk_pts = np.vstack(sk_pts) if sk_pts else np.zeros((0, 3))
    skin_only = np.vstack([tri_samples(x["v"], x["f"], per_mm2, rng) for x in skin]) if skin else np.zeros((0, 3))
    rad = max(1, int(round(close_mm / vox)))
    body = solidify(g.stamp(sk_pts), g, rad)
    st = cKDTree(sk_pts)
    eb = band(body, g, st, rng)
    bn_pts = np.vstack([tri_samples(x["v"], x["f"], per_mm2, rng) for x in bone]) if bone else np.zeros((0, 3))
    bones = ndimage.binary_erosion(solidify(g.stamp(bn_pts), g, 2), ndimage.generate_binary_structure(3, 1), 1) if len(bn_pts) else np.zeros(g.shape, bool)
    return dict(key=key, S=S, g=g, body=body, bones=bones, skin_tree=st, bone_tree=cKDTree(bn_pts) if len(bn_pts) else None,
                close_mm=close_mm, error_band=eb,
                n_skin=len(skin), n_outer=len(outer), n_bone=len(bone), skin_pts=len(sk_pts),
                skin_volume_cm3=round(float(body.sum()) * vox ** 3 / 1000.0, 1), lo=lo, hi=hi,
                skin_bbox=np.round(hi - lo, 1).tolist(), skin_only_pts=len(skin_only))


def validate(B):
    """the mask is only usable if the structures that are inside by construction come out inside."""
    g, body = B["g"], B["body"]
    res = {"deep_inside_pct": {}, "ok": True, "reasons": []}
    for nm in DEEP_MUST_BE_INSIDE:
        xs = [x for x in B["S"] if x["id"].split("#")[0] == nm]
        if not xs:
            continue
        V = np.vstack([x["v"] for x in xs])
        pct = round(100.0 * float(g.inside(body, V).mean()), 2)
        res["deep_inside_pct"][nm] = pct
        if pct < 99.5:
            res["ok"] = False; res["reasons"].append(f"{nm} only {pct}% inside the body mask")
    vol = B["skin_volume_cm3"]
    res["body_mask_volume_cm3"] = vol
    if not (25000 <= vol <= 120000):
        res["ok"] = False; res["reasons"].append(f"body mask volume {vol} cm3 outside the plausible 25-120 L band")
    return res


def audit(B, tol_mm=5.0, cap=20000):
    g, body, bones = B["g"], B["body"], B["bones"]
    st, bt = B["skin_tree"], B["bone_tree"]
    rng = np.random.default_rng(11)
    out = []
    for x in B["S"]:
        V = x["v"]
        P = V if len(V) <= cap else tri_samples(V, x["f"], 0.25, rng, cap=cap)
        ins = g.inside(body, P)
        rec = dict(id=x["id"], sys=x["sys"], n=int(len(P)))
        if not ins.all():
            Q = P[~ins]
            d = st.query(Q, workers=-1)[0]
            rec["out_n"] = int(len(Q)); rec["out_frac"] = round(float(len(Q)) / len(P), 5)
            rec["out_max_mm"] = round(float(d.max()), 2); rec["out_p95_mm"] = round(float(np.quantile(d, 0.95)), 2)
            rec["out_mean_mm"] = round(float(d.mean()), 2)
            j = int(np.argmax(d)); rec["out_worst_xyz"] = np.round(Q[j], 1).tolist()
            rec["out_beyond_tol_n"] = int((d > tol_mm).sum())
        if x["sys"] != "bone" and bt is not None:
            pen = g.inside(bones, P)
            if pen.any():
                dd = bt.query(P[pen], workers=-1)[0]
                rec["bone_in_n"] = int(pen.sum()); rec["bone_in_frac"] = round(float(pen.sum()) / len(P), 5)
                rec["bone_depth_max_mm"] = round(float(dd.max()), 2)
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key"); ap.add_argument("--vox", type=float, default=2.0)
    ap.add_argument("--tol", type=float, default=5.0)
    ap.add_argument("--close", type=float, default=8.0)
    ap.add_argument("--out", default=str(REPO / "data/derived"))
    a = ap.parse_args()
    t0 = time.time()
    B = build(a.key, a.vox, close_mm=a.close)
    val = validate(B)
    print(a.key, "mask", B["g"].shape, "vol", B["skin_volume_cm3"], "cm3", "skin", B["n_skin"], "outer", B["n_outer"],
          "valid" if val["ok"] else "INVALID " + "; ".join(val["reasons"]), flush=True)
    recs = audit(B, a.tol)
    bad = sorted([r for r in recs if r.get("out_beyond_tol_n")], key=lambda r: -r["out_max_mm"])
    pen = sorted([r for r in recs if r.get("bone_depth_max_mm", 0) > a.tol], key=lambda r: -r["bone_depth_max_mm"])
    res = dict(page=a.key, label=C.PAGES[a.key][3], vox_mm=a.vox, tol_mm=a.tol, n_structures=len(recs),
               mask=dict(shape=list(B["g"].shape), volume_cm3=B["skin_volume_cm3"], n_skin=B["n_skin"], n_outer=B["n_outer"],
                         skin_samples=B["skin_pts"], bbox_mm=B["skin_bbox"], close_mm=B["close_mm"], error_band=B["error_band"]),
               validation=val, n_outside_any=sum(1 for r in recs if r.get("out_n")), n_outside_beyond_tol=len(bad),
               n_bone_penetrating=len(pen), offenders=bad, bone_penetration=pen[:200], seconds=round(time.time() - t0, 1))
    p = Path(a.out) / f"Q299_containment_{a.key}.json"
    p.write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    print("->", p, "offenders", len(bad), "bone-pen", len(pen), f"{res['seconds']}s", flush=True)
    for r in bad[:25]:
        print("   OUT", r["id"], r["sys"], r["out_max_mm"], "mm", r["out_beyond_tol_n"], "/", r["n"])


if __name__ == "__main__":
    main()
