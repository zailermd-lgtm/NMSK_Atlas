#!/usr/bin/env python3
"""Q375: how two neighbouring skin slabs meet along their border -- read-only census of a Z page's skin (nothing is written).

    python3 scripts/anatomy/q375/border_census_q375.py --page-dir DIR [--pairs a:b,...] [--json OUT]

For every pair of skin slabs (ids `zan_skin_*` and the other skin pieces, nail plates left out) the BORDER vertices of A that face B
are counted -- the engine's rim rule (Q334 1b: a vertex with an incident face more than ~45 degrees off its own vertex normal, i.e.
where the slab's surface turns into its side wall) and within NEAR_MM of B's surface -- and each is put in one class:
  * shared   -- a vertex of B lies within WELD_MM (0.03 mm, the engine's weld distance): the load-time weld joins them;
  * tjunction -- no vertex of B there, but the point lies ON one of B's border edges (within WELD_MM, inside the edge): the two
                 borders are cut at different vertices (a T-junction). No move of existing vertices can make it a shared vertex;
  * offset   -- neither: a vertex of B (its mutually nearest border vertex, same face of the skin) lies OFFSET_MM or less away; a
                guarded snap of the pair could join it;
  * other    -- the rest (near B's surface, no partner: a corner of three slabs, an overlap).
The Q375 finding on Base · Male / Base · Female (both the same Z topology there): the finger and toe slabs carry about twice the
border vertices of the palm, the dorsum of the hand and the arches of the foot; every other one of theirs is a T-junction. The
coarse side is fully shared once the engine has run (its inner-sheet vertices, 0.6-1.2 mm off, are joined by the rim join).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q340"))

WELD_MM = 0.03     # the engine's weld distance (Q334_WELD)
NEAR_MM = 1.5      # a border vertex this close to the other slab's surface faces that slab
OFFSET_MM = 1.5    # a mutually nearest border vertex this close is a snap candidate
RIM_COS = 0.7      # the engine's rim rule (Q334 1b)


# ------------------------------------------------------------------ pure functions (tests/test_q375_border_census.py)
def vertex_normals(P, F):
    """area-weighted vertex normals and unit face normals of one mesh (as the page computes them, over the mesh's own faces)"""
    fn = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    vn = np.zeros_like(P, dtype=float)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    fu = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    return vn, fu


def rim_vertices(P, F, cos=RIM_COS):
    """the engine's rim rule: True where an incident face stands more than acos(cos) off the vertex's own normal"""
    vn, fu = vertex_normals(P, F)
    r = np.zeros(len(P), bool)
    for k in range(3):
        bad = (fu * vn[F[:, k]]).sum(1) < cos
        r[F[bad, k]] = True
    return r, vn


def rim_edges(P, F, rim, vn, cos=0.5):
    """edges of F with both ends on the rim whose ends' normals agree (along the border, not across the side wall), unique (a<b)"""
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    E = np.sort(E, axis=1)
    E = np.unique(E, axis=0)
    keep = rim[E[:, 0]] & rim[E[:, 1]] & ((vn[E[:, 0]] * vn[E[:, 1]]).sum(1) >= cos)
    return E[keep]


def on_segment(p, a, b):
    """(t, d): parameter of the closest point of segment a-b to p (0..1, clamped) and the distance to it"""
    ab = b - a
    ll = float(ab @ ab)
    if not ll > 0:
        return 0.0, float(np.linalg.norm(p - a))
    t = float(np.clip((p - a) @ ab / ll, 0.0, 1.0))
    return t, float(np.linalg.norm(p - (a + t * ab)))


def classify(Pa, Fa, Pb, Fb, near=NEAR_MM, weld=WELD_MM, offset=OFFSET_MM, surf_dist=None):
    """the border vertices of A that face B, each in one class (see the module doc). surf_dist(points) -> distance to B's surface
    (default: to B's vertices and rim edges only -- enough where B's border is what A meets). -> dict of index arrays + offsets"""
    ra, na = rim_vertices(Pa, Fa)
    rb, nb = rim_vertices(Pb, Fb)
    Eb = rim_edges(Pb, Fb, rb, nb)
    ia = np.where(ra)[0]
    if surf_dist is None:
        def surf_dist(X):
            d = cKDTree(Pb).query(X)[0]
            for k, x in enumerate(X):
                for e0, e1 in Eb:
                    d[k] = min(d[k], on_segment(x, Pb[e0], Pb[e1])[1])
            return d
    if len(ia):
        ia = ia[surf_dist(Pa[ia]) <= near]
    out = {"border": ia, "shared": [], "tjunction": [], "offset": [], "other": [], "offset_mm": []}
    if not len(ia):
        return {k: np.asarray(v) for k, v in out.items()}
    dv, jv = cKDTree(Pb).query(Pa[ia])
    ib = np.where(rb)[0]
    tb = cKDTree(Pb[ib]) if len(ib) else None
    ta = cKDTree(Pa[ia])
    for k, v in enumerate(ia):
        if dv[k] <= weld:
            out["shared"].append(v)
            continue
        on = False
        for e0, e1 in Eb:
            t, d = on_segment(Pa[v], Pb[e0], Pb[e1])
            if d <= weld and 0.02 < t < 0.98:
                on = True
                break
        if on:
            out["tjunction"].append(v)
            continue
        if tb is not None:
            d2, j2 = tb.query(Pa[v])
            u = ib[j2]
            back = ia[ta.query(Pb[u])[1]]
            if d2 <= offset and back == v and float(na[v] @ nb[u]) > 0:
                out["offset"].append(v)
                out["offset_mm"].append(d2)
                continue
        out["other"].append(v)
    return {k: np.asarray(v) for k, v in out.items()}


# ------------------------------------------------------------------ page
def skin_pieces(page_dir: Path):
    import conform_palm_q340 as C340
    stem = C340.stem_of(page_dir)
    man, blob, _ = C340.read_page(page_dir, stem)
    out = {}
    for m in man["meshes"]:
        if (m.get("sys") or "bone") != "skin" or str(m.get("name", "")).lower().startswith("nail plate"):
            continue
        P, F = C340.dec(m, blob)
        out[m["id"]] = (P.astype(np.float32).astype(float), F)
    return out


DEFAULT_PAIRS = [(f"zan_skin_{a}_{s}", f"zan_skin_{b}_{s}") for s in "rl" for a, b in (
    ("palmar_surfaces_of_digits_of_hand", "palm"), ("dorsal_surfaces_of_digits_of_hand", "dorsum_of_hand"),
    ("plantar_surfaces_of_digits_of_foot", "distal_transverse_arch_of_foot"), ("plantar_surfaces_of_digits_of_foot", "hallucial_eminence"),
    ("dorsal_surfaces_of_digits_of_foot", "metatarsal_region"))]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--pairs", default="", help="a:b,... (skin ids; default the finger and toe bases, both sides)")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    S = skin_pieces(Path(a.page_dir))
    pairs = [tuple(p.split(":")) for p in a.pairs.split(",") if p] or DEFAULT_PAIRS
    rep = []
    for x, y in pairs:
        for A, B in ((x, y), (y, x)):
            c = classify(*S[A], *S[B])
            r = {"a": A, "b": B, **{k: int(len(c[k])) for k in ("border", "shared", "tjunction", "offset", "other")},
                 "offset_max_mm": round(float(c["offset_mm"].max()), 3) if len(c["offset_mm"]) else 0.0}
            rep.append(r)
            print("%-48s -> %-40s border %4d shared %4d T %4d offset %3d (max %.2f) other %3d" % (
                A[9:], B[9:], r["border"], r["shared"], r["tjunction"], r["offset"], r["offset_max_mm"], r["other"]))
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
