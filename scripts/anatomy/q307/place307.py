"""Q307 placement audit: does every tubular structure sit in the compartment and at the depth its own anatomy requires?

The round exists because the owner reported the LATERAL ANTEBRACHIAL CUTANEOUS NERVE as "not in place" (Hebrew:
"לא במקום!!") right after the missing fibular nerve of Q299/Q304, so the question is asked of every nerve on every page.

What is measured, and why these and not others:

  depth-in-muscle   a nerve's samples that lie INSIDE a muscle, with the DEPTH below that muscle's own surface.
                    Depth, not a bare inside/outside flag, because the voxel solid is inflated: measured on
                    base_m `brachioradialis_l` the mask is 116.7 cm3 against the mesh's own 93.8 cm3, about one
                    1.5 mm voxel all round, so an inside/outside flag alone calls a nerve LYING ON a muscle
                    "inside it". Every structure's own inflation is measured here (`mask_offset_mm`, the p95 over
                    that mesh's own surface samples of their distance inside the mask) and only samples deeper
                    than that offset count. This is the test that found the owner's defect.
  continuity        surface-to-surface distance from the branch's proximal end to its parent trunk, parent taken
                    from the project's own cited nerve registry (data/nerves/*.json) or from this round's cited
                    table (data/anatomy/nerve_parents_q307.json); never guessed.
  side              the centroid's sign against the page's own midsagittal plane vs the id's own side token.

Two things are NOT re-measured here because the project already has them and they were validated in their own
round: body containment and bone penetration (Q299, `data/derived/Q299_containment.json`) and whether a
structure touches anything at all (Q298's 2.0 mm voxel adjacency, contact <= 3.46 mm). This module reads those.

Distances are surface-to-surface on area-weighted triangle samples (>= 1 pt/mm2, vertices always included),
never vertex to vertex: Q298 measured that 69.3 % of the triangles on a Z page have a longest edge over 3 mm,
and Q304 recorded that a vertex-to-vertex figure between meshes of different density is flattering and wrong.
"""
from __future__ import annotations
import argparse, glob, json, os, re, sys, time
from pathlib import Path
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q241"))
import model as MODEL  # noqa: E402

DERIVED = REPO / "data" / "derived"
PITCH = 1.5          # voxel pitch of a per-structure solid, mm
DEEP_MM = 2.0        # a sample counts as inside a muscle only this far past the mask's own measured offset
RNG = np.random.default_rng(20261103)


# --------------------------------------------------------------------------- sampling
def samples(v, f, per_mm2=1.0, cap=250_000):
    """Area-weighted surface samples, vertices always included (the Q298 rule)."""
    f = np.asarray(f)
    if len(f) == 0:
        return np.asarray(v, float)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    ar = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    n = np.maximum(0, np.ceil(ar * per_mm2).astype(np.int64))
    tot = int(n.sum())
    if tot > cap:
        n = np.maximum(0, (n * (cap / tot)).astype(np.int64)); tot = int(n.sum())
    out = [np.asarray(v, float)]
    if tot:
        idx = np.repeat(np.arange(len(f)), n)
        u = RNG.random(len(idx)); w = RNG.random(len(idx))
        m = u + w > 1.0
        u[m], w[m] = 1 - u[m], 1 - w[m]
        out.append(a[idx] + u[:, None] * (b[idx] - a[idx]) + w[:, None] * (c[idx] - a[idx]))
    return np.vstack(out)


def merged(xs):
    v = np.vstack([x["v"] for x in xs]); ff, o = [], 0
    for x in xs:
        ff.append(np.asarray(x["f"]) + o); o += len(x["v"])
    return v, np.vstack(ff)


# --------------------------------------------------------------------------- per-structure solid
class Solid:
    """Q299's recipe, per structure in its OWN padded box: surface voxels -> dilate -> flood the OUTSIDE from
    the box border -> erode back. Never one global mask: Q299 measured that a global bone mask closes the bony
    rings and its hole fill swallows the mediastinum, which made it call 53 % of an aorta "inside a bone"."""

    def __init__(self, v, f, pitch=PITCH, pad=6.0):
        P = samples(v, f, 4.0)
        self.lo = P.min(0) - pad; hi = P.max(0) + pad
        self.pitch = pitch
        dim = np.maximum(3, np.ceil((hi - self.lo) / pitch).astype(int) + 1)
        g = np.zeros(dim, bool)
        ix = np.clip(((P - self.lo) / pitch).round().astype(int), 0, dim - 1)
        g[ix[:, 0], ix[:, 1], ix[:, 2]] = True
        k = np.ones((3, 3, 3), bool)
        d = ndimage.binary_dilation(g, k, iterations=2)
        out = np.zeros_like(d)
        out[0], out[-1] = True, True
        out[:, 0], out[:, -1] = True, True
        out[:, :, 0], out[:, :, -1] = True, True
        out &= ~d
        out = ndimage.binary_propagation(out, mask=~d)
        self.mask = ndimage.binary_erosion(~out, k, iterations=2)
        self.surf = samples(v, f, 1.0)
        self._tree = cKDTree(self.surf)
        # The mask's own inflation, measured, not assumed: how far the mask's OWN BOUNDARY lies beyond this
        # mesh's real surface. (Measuring the surface samples' own depth instead gives 0 by construction --
        # their nearest surface sample is themselves -- which is the first version of this line and was
        # caught by a 20 mm unit cube reporting offset 0.0 while its mask was 9.26 cm3 against a true 8.0.)
        b = self.mask & ~ndimage.binary_erosion(self.mask, np.ones((3, 3, 3), bool))
        if b.any():
            ix = np.argwhere(b) * self.pitch + self.lo
            self.offset_mm = float(np.percentile(self._tree.query(ix, k=1)[0], 95))
        else:
            self.offset_mm = 0.0

    def inside(self, P):
        ix = ((P - self.lo) / self.pitch).round().astype(int)
        ok = np.all((ix >= 0) & (ix < np.array(self.mask.shape)), axis=1)
        r = np.zeros(len(P), bool)
        r[ok] = self.mask[ix[ok, 0], ix[ok, 1], ix[ok, 2]]
        return r

    def _depth_raw(self, P):
        if len(P) == 0:
            return np.zeros(0)
        return self._tree.query(P, k=1)[0]

    def depth(self, P):
        """-> (inside_and_deeper_than_the_offset, depth_mm_below_the_surface) for every point of P."""
        ins = self.inside(P)
        d = np.zeros(len(P))
        d[ins] = self._depth_raw(P[ins])
        return ins & (d > self.offset_mm + DEEP_MM), d

    def volume_cm3(self):
        return float(self.mask.sum() * self.pitch ** 3 / 1000.0)


# --------------------------------------------------------------------------- the cited parent table
def base_id(i):
    i = re.sub(r"#\d+$", "", str(i).lower())
    i = re.sub(r"^zan_", "", i)
    i = re.sub(r"_(l|r)$", "", i)
    return i


def parent_table():
    """{base id: (parent base id, source, how)} -- 'registry' = the project's own cited nerve registry,
    'q307' = this round's cited table, 'name' = derived from the structure's own name (a RULE of this
    project, labelled inferred wherever it is shown)."""
    out = {}
    for p in sorted(glob.glob(str(REPO / "data" / "nerves" / "*.json"))):
        d = json.load(open(p))
        if isinstance(d, dict):
            d = [e for v in d.values() if isinstance(v, list) for e in v]
        for e in d:
            if isinstance(e, dict) and e.get("id") and e.get("parent_id"):
                out[base_id(e["id"])] = (base_id(e["parent_id"]), e.get("source", ""), "registry")
    q = REPO / "data" / "anatomy" / "nerve_parents_q307.json"
    if q.exists():
        for e in json.load(open(q))["parents"]:
            out[base_id(e["id"])] = (base_id(e["parent_id"]), e["source"], "q307")
    OF = re.compile(r"^(.*)_(?:branch|branches|rami|ramus)_of_(.+?)(?:_nerve|_n)?$")
    return out, OF


def resolve_parent(b, table, OF):
    if b in table:
        return table[b]
    m = OF.match(b)
    if m:
        return (base_id(m.group(2)), "name of the structure itself (a rule of this project, inferred)", "name")
    return None


# --------------------------------------------------------------------------- the scope: real peripheral nerves
def calibre_nerves(key):
    """Q303's own rule: the set of real peripheral nerves on a page is every structure the page's OWN calibre
    table records with kind 'n' (439 of 552 nerve-category meshes on a Z page; the rest are the spinal dura,
    the cord, its tracts and its nuclei). The table rows are [kind, diameter_mm, level, ...]."""
    d = json.load(open(REPO / "data" / "anatomy" / "calibre.json"))
    page = MODEL.page_dir(key).name
    c = d["pages"][page]["c"]
    return {k: {"d_mm": v[1], "level": v[2]} for k, v in c.items() if v and v[0] == "n"}


def calibre_all(key, kinds=("n", "a", "v")):
    d = json.load(open(REPO / "data" / "anatomy" / "calibre.json"))
    page = MODEL.page_dir(key).name
    c = d["pages"][page]["c"]
    return {k: {"kind": v[0], "d_mm": v[1], "level": v[2]} for k, v in c.items() if v and v[0] in kinds}


# --------------------------------------------------------------------------- which nerves must be superficial
CUT = re.compile(r"cutaneous")
# Terminologia Anatomica uses "cutaneous" for a nerve that pierces the deep fascia and supplies skin, so the
# name itself carries the claim; everything else is reported as data and not flagged. The project's rule is
# stated on screen wherever the flag is shown.


def is_cutaneous(i):
    return bool(CUT.search(base_id(i)))


def prox_end(P, frac=0.12, axis=None):
    """The proximal ~12 % of a tube's samples along its own principal axis, at whichever end is 'proximal'.
    Returns both ends; the caller picks by distance to the parent, because a tube carries no direction."""
    c = P.mean(0)
    u = np.linalg.svd(P - c, full_matrices=False)[2][0]
    t = (P - c) @ u
    lo = t <= t.min() + frac * (t.max() - t.min())
    hi = t >= t.max() - frac * (t.max() - t.min())
    return P[lo], P[hi]


def audit_page(key, out_dir, systems=("nerve",), progress=True):
    t0 = time.time()
    m = MODEL.Model(key)
    by = {}
    for x in m.S:
        by.setdefault(x["id"], []).append(x)
    cal = calibre_all(key)
    scope = {i: r for i, r in cal.items() if i in by and (
        (r["kind"] == "n" and "nerve" in systems) or (r["kind"] == "a" and "artery" in systems) or (r["kind"] == "v" and "vein" in systems))}
    if progress:
        print(f"[{key}] {len(m.S)} structures, {len(scope)} in scope", flush=True)
    # sample every structure in scope once
    SAMP, PROX = {}, {}
    for i in scope:
        v, f = merged(by[i])
        P = samples(v, f, 2.0)
        SAMP[i] = P
        PROX[i] = prox_end(P)
    boxes = {i: (P.min(0) - 3.0, P.max(0) + 3.0) for i, P in SAMP.items()}

    # ---- depth inside a muscle: outer loop over muscles so only one solid is live at a time
    deep = {i: {} for i in scope}
    mus = [x for x in m.S if x["sys"] == "muscle"]
    for n, x in enumerate(mus):
        cand = [i for i in scope if x["side"] in (by[i][0]["side"], "m") or by[i][0]["side"] == "m"]
        bl, bh = x["v"].min(0) - 3.0, x["v"].max(0) + 3.0
        cand = [i for i in cand if not (np.any(boxes[i][1] < bl) or np.any(boxes[i][0] > bh))]
        if not cand:
            continue
        S = Solid(x["v"], np.asarray(x["f"]))
        for i in cand:
            ins, d = S.depth(SAMP[i])
            if ins.mean() > 0.0:
                deep[i][x["id"]] = dict(frac=round(float(ins.mean()), 4),
                                        p95_mm=round(float(np.percentile(d[ins], 95)), 2),
                                        max_mm=round(float(d[ins].max()), 2),
                                        offset_mm=round(S.offset_mm, 2))
        del S
        if progress and n % 50 == 0:
            print(f"[{key}]   muscle {n}/{len(mus)}  {time.time()-t0:.0f}s", flush=True)

    # ---- continuity with the parent trunk
    table, OF = parent_table()
    cont = {}
    for i in scope:
        b = base_id(i)
        pr = resolve_parent(b, table, OF)
        if pr is None:
            cont[i] = dict(parent=None, how=None); continue
        pb, src, how = pr
        side = by[i][0]["side"]
        cands = [j for j in by if base_id(j) == pb and (by[j][0]["side"] == side or side == "m" or by[j][0]["side"] == "m")]
        if not cands:
            cont[i] = dict(parent=pb, how=how, source=src, on_page=False); continue
        PP = np.vstack([samples(*merged(by[j]), 1.0) for j in cands])
        T = cKDTree(PP)
        a, bb = PROX[i]
        da = float(T.query(a, k=1)[0].min()); db = float(T.query(bb, k=1)[0].min())
        whole = float(T.query(SAMP[i], k=1)[0].min())
        cont[i] = dict(parent=pb, parent_ids=cands, how=how, source=src, on_page=True,
                       d_prox_end_mm=round(min(da, db), 2), d_other_end_mm=round(max(da, db), 2),
                       d_anywhere_mm=round(whole, 2))

    # ---- side
    sidechk = {}
    for i in scope:
        tok = by[i][0]["side"]
        c = SAMP[i].mean(0)
        s = float(m.plane.n @ c - m.plane.d)   # +X = the subject's right
        sidechk[i] = dict(token=tok, signed_mm=round(s, 1),
                          ok=(tok == "r" and s > 0) or (tok == "l" and s < 0) or tok == "m")

    res = dict(page=key, page_dir=str(MODEL.page_dir(key)), generated_by="scripts/anatomy/q307/place307.py",
               deep_mm_threshold=DEEP_MM, pitch_mm=PITCH, n_scope=len(scope),
               structures={i: dict(kind=cal[i]["kind"], d_mm=cal[i]["d_mm"], cutaneous=is_cutaneous(i),
                                   in_muscle=deep[i], continuity=cont[i], side=sidechk[i],
                                   n_samples=int(len(SAMP[i]))) for i in scope})
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    p = Path(out_dir) / f"Q307_placement_{key}.json"
    json.dump(res, open(p, "w"), indent=1)
    print(f"[{key}] done {time.time()-t0:.0f}s -> {p}", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["audit"])
    ap.add_argument("--pages", default=",".join(MODEL.KEYS))
    ap.add_argument("--systems", default="nerve")
    ap.add_argument("--out", default=str(DERIVED))
    a = ap.parse_args()
    for k in a.pages.split(","):
        audit_page(k, a.out, tuple(a.systems.split(",")))


if __name__ == "__main__":
    main()
