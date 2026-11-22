#!/usr/bin/env python3
"""Q358: Base · Female -- the skin of the vulva and perineum: clean the real vulvar surface and close the skin ring around it with a
RULE-BASED closing surface shaped from the atlas topography and anchored to this body's own landmarks and skin borders.

    python3 scripts/anatomy/q358/perineum_skin_q358.py --page-dir DIR                 # dry run: build + measure, report only
    python3 scripts/anatomy/q358/perineum_skin_q358.py --page-dir DIR --write         # and write DIR (+ the pose rig, see --rig-file)

What was wrong (QA sweep Q337, Q353 measurements): `skin_vulva_cvh` (Q336: the REAL vulvar / perineal skin of the Chinese Visible
Human female, registered onto this body, its border tucked 25 mm under the Z-Anatomy neighbours) shows ragged fragments and a hanging
flap where pieces of it cross the neighbours' outer surface; around it the skin ring is open (no skin piece in a 20-30 mm band
between the medial thigh rim and the vulva, axial slices y ~ -126..-98 and -68..-56 mm), and the adductors / gracilis / pectineus and
vessels show through the gaps. Q353's conform of the patch alone failed its guards (structures pushed out in turn).

The fix (deterministic; every number into the report):
  1. CLEAN the real surface (no vertex of it moves): its loose pieces are removed; of its outer sheet only the faces over the opening
     (the free rim of the Z-Anatomy skin, data/derived/Q202_perineal_loop.json, re-read on this page) are kept, with a TUCK_MM margin,
     and no face that rises out of the opening faster than RAMP_SLOPE (the flap / wings standing in front of the neighbours); the
     largest connected piece stays; the 3 mm slab is rebuilt from its own (unmoved) outer and inner vertices.
  2. ADD `skin_perineum_rule_q358`, a RULE-BASED closing skin: a surface spanning the whole opening, bounded EXACTLY by the
     neighbours' free rim (outer and inner border vertices, so the engine's load-time skin weld joins it), interpolated (Coons patch,
     then a harmonic height field along the inward normal) between: the rim (height 0), the real vulva (held RULE_GAP mm behind its
     deepest layer, so the real surface stays on top wherever it exists), and the deeper structures (held in front of them by the skin
     thickness + DEEP_GAP; this wins over the vulva constraint, and such places are counted). It therefore forms the medial-thigh /
     genitofemoral walls of the pudendal cleft, the skin over the perineal body between the vulva and the anal skin, and fills the
     real surface's holes; it is a 3 mm closed slab like every Z skin patch.
The topography the rule follows (owner's books, knowledge only; see ATLAS below and docs/Q358_perineum_skin.md): the perineum is the
interval between the upper medial thighs and the lower buttocks, limited in front by the mons pubis; diamond outlet between the pubic
symphysis, ischiopubic rami, ischial tuberosities, sacrotuberous ligaments and coccyx; the interischial line passes just in front of
the anus; the labia majora run down and back from the mons and meet ~1 inch in front of the anus (posterior commissure, over the
perineal body); the gynaecological perineum between them is ~1 inch long; one continuous skin with no free border inside the region.
Guards: real-surface vertices unchanged (positions identical); the new slab watertight, consistently wound, no flipped face against
its membrane; no face stretched beyond STRETCH_MAX against the membrane median; the rule surface never in front of the kept real
surface by more than COVER_TOL where the vulva constraint was met; ring closed (Q353 ring test) in the region; no structure gains
vertices outside the skin. Originals are copied beside each changed file as `<name>.q358` (never overwritten). Idempotent: a page
that already carries `skin_perineum_rule_q358` is left as it is.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (REPO, REPO / "scripts" / "zanatomy", REPO / "scripts" / "anatomy" / "q340"):
    sys.path.insert(0, str(p))
import build_zan_atlas_viewer as B  # noqa: E402  pack_mesh / split_blob (the builder's own layout)
import conform_palm_q340 as C340    # noqa: E402  page I/O (read_page, dec, LIT, ser_manifest, pages_of, badge_add)

STEM = "atlas_viewer_base_female"
CVH_ID = "skin_vulva_cvh"
NEW_ID = "skin_perineum_rule_q358"
TAG = "Q358"
LOOP = REPO / "data/derived/Q202_perineal_loop.json"
REPORT = REPO / "data/derived/Q358_perineum_report.json"
RIG = REPO / "data/anatomy/pose_rig_base_f.json"

# ------------------------------------------------------------------ the atlas facts the rule uses (knowledge only; cited)
MANNAN = "Noor MA. Mannan's Regional Dissection and Surface Anatomy, 14th ed. Jaypee, New Delhi 2017"
GRAYS_ATLAS = "Drake RL, Vogl AW, Mitchell AWM et al. Gray's Atlas of Anatomy, Churchill Livingstone / Elsevier (edition not in the owner's scan)"
ATLAS = {
    "perineum_interval": dict(fact="the perineum occupies, externally, the interval between the upper medial thighs and the lower "
                                   "buttocks, limited in front by the mons pubis; one skin, continuous with the neighbouring regions",
                              cite=f"{MANNAN}, p. 343"),
    "outlet_diamond": dict(fact="diamond-shaped outlet: pubic arch / inferior pubic ligament in front, tip of the coccyx behind, "
                                "ischiopubic rami and ischial tuberosities anterolaterally, sacrotuberous ligaments posterolaterally; "
                                "palpable landmarks pubic symphysis, ischial tuberosities, coccyx",
                           cite=f"{MANNAN}, pp. 343-344; {GRAYS_ATLAS}, p. 244"),
    "interischial_line": dict(fact="the transverse line joining the two ischial tuberosities passes just in front of the anus "
                                   "(urogenital triangle in front, anal triangle behind)",
                              cite=f"{MANNAN}, pp. 344-345"),
    "labia_majora": dict(fact="two thick skin folds (fat-filled) running down and back from the mons pubis, diminishing posteriorly; "
                              "lateral surface convex; they meet in front (anterior commissure, continuous with the mons) and behind "
                              "(posterior commissure) on either side of the median pudendal cleft, almost horizontal when erect",
                         cite=f"{MANNAN}, pp. 361-362"),
    "posterior_commissure": dict(fact="the labia majora unite about an inch in front of the anus (posterior commissure), which overlies "
                                      "the perineal body", cite=f"{MANNAN}, p. 361; {GRAYS_ATLAS}, p. 243"),
    "gyn_perineum": dict(fact="the gynaecological perineum, between the posterior commissure and the anus, is about an inch long",
                         cite=f"{MANNAN}, p. 362"),
    "mons": dict(fact="the mons pubis is the soft elevation over the pubic symphysis produced by a pad of fat", cite=f"{MANNAN}, p. 361"),
    "vestibule": dict(fact="labia minora, vestibule, urethral and vaginal openings lie within the pudendal cleft, medial to the labia "
                           "majora", cite=f"{MANNAN}, pp. 361-362; {GRAYS_ATLAS}, pp. 242-243"),
}
INCH_MM = 25.4                     # "about an inch" (posterior commissure -> anus, ATLAS gyn_perineum / posterior_commissure)

# ------------------------------------------------------------------ parameters
THICK = 3.0          # mm: skin slab thickness of the Z patches (Q202) -- the new slab is built the same way
ROW_MM = 3.0         # mm: target spacing of the rows along the rim rails
COLS = 36            # vertices across a row of the closing surface (after arc-length resampling)
NF = 160             # samples across a row for the height field
REACH = 80.0         # mm: rays start this far outside the opening
LB_WIN = 1.5         # mm: the real surface's deepest layer within this distance along the row bounds a sample
HIT_OUT, HIT_IN = 25.0, 45.0   # mm: real-surface hits farther out / in along a row's direction belong to another part of it
PROUD_MM = 0.3       # mm: a real-surface vertex over a neighbouring region must lie at least this far under its outer surface
TANG_MAX = 2.0       # mm: farther sideways from a neighbouring region than this = beyond its border, not over it (Q353)
TUCK_MM = 2.0        # mm: the real surface may reach this far past the rim (under the neighbours)
RAMP_SLOPE = 1.0     # a kept real face rises out of the opening at most this many mm per mm from the rim (+ RAMP0)
RAMP0 = 2.0          # mm
MIN_PIECE = 200      # faces: smaller connected pieces of the real surface are loose fragments
RULE_GAP = 1.0       # mm: the rule surface lies this far behind the deepest layer of the real surface over it
DEPTH_WIN = 20.0     # mm: layers of the real surface within this depth of its first layer count (folds of the labia)
DEEP_GAP = 0.3       # mm: deeper structures lie at least the slab thickness + this under the rule surface (Q353 GAP)
DEEP_HARD = 0.5      # mm: when even that cannot be met, at least this under the outer surface (Q353 HIDE)
SMOOTH_IT = 1500     # projected SOR rounds of the height field
COVER_TOL = 0.05     # mm
TUCK_SLOPES = (0.08, 0.05)   # gentler Lipschitz slopes tried after the Q353 default 0.15 (same guards)
SMOOTH_REAL = True   # Q358 follow-up: the real surface's staircase facets smoothed (optional step, ON by default)
SMOOTH_REAL_IT = 6
CAP_REAL = 1.0       # mm: per-vertex cap of that smoothing (source spacing unknown)
CAP_ROWS = 4         # rows blended between the anal-region border and the first row of the walls
TAUBIN_IT = 12       # Taubin smoothing rounds of the rule surface's interior
EDGE_W = 6.0         # mm: a deeper structure counts as covered by the real surface only this far inside its edge
FOLD_AREA_MAX = 50.0 # mm2: folded faces allowed in all (sub-millimetre slivers where the rim itself turns sharply)
FOLD_DEG = 120.0     # degrees between neighbouring faces = folded back
EDGE_MAX = 25.0      # mm: no edge of the rule surface longer (the neighbouring Z patches have 10-25 mm edges)
REGION = (np.array([-75.0, -145.0, -60.0]), np.array([75.0, -15.0, 125.0]))
NOT_DEEP = ("skin", "fat", "fascia")
NOT_TUCK = __import__("re").compile(r"saphenous|lateral_femoral_cutaneous")   # thigh / leg structures: not perineal, their
#   poke-throughs belong to other rounds (Q337 item 5; the great saphenous vein is also in the Q357 in-bone round)
DEEP_REACH = 45.0   # mm: deeper structures within this distance of the opening constrain the rule surface


# ------------------------------------------------------------------ page I/O
def read(d: Path):
    man, blob, files = C340.read_page(d, STEM)
    return man, blob, files


def dec(m, blob):
    return C340.dec(m, blob)


def repack(man, blob, replace, add):
    """replace = {id: (v, f, rec)} (geometry in place, index kept); add = [(entry, v, f)] appended (no index moves)"""
    meshes, chunks, off = [], [], 0
    for m in man["meshes"]:
        n = dict(m)
        if m["id"] in replace:
            v, f, rec = replace[m["id"]]
            fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
            n.update(fields); n["rec"] = rec
            chunks.append(packed); off += len(packed)
        else:
            pos = blob[m["vo"]: m["vo"] + m["vc"] * 6]; idx = blob[m["io"]: m["io"] + m["ic"] * 6]
            n["vo"], n["io"] = off, off + len(pos)
            chunks += [pos, idx]; off += len(pos) + len(idx)
        meshes.append(n)
    for entry, v, f in add:
        fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
        n = dict(entry); n.update(fields)
        meshes.append(n); chunks.append(packed); off += len(packed)
    man2 = dict(man); man2["meshes"] = meshes
    t = json.loads(json.dumps(man.get("totals") or {}))
    if t:
        t["meshes"] = len(meshes)
        bl = t.setdefault("by_layer", {})
        for entry, _, _ in add:
            bl[entry["sys"]] = bl.get(entry["sys"], 0) + 1
        man2["totals"] = t
    return man2, b"".join(chunks)


def write_page(d: Path, man_old, man_new, blob_new, old_files):
    pages = C340.pages_of(d, STEM)
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    for p, t in texts.items():
        assert C340.LIT["manifest"].search(t).group(1) == C340.ser_manifest(man_old), f"{p}: manifest serialisation differs"
        assert C340.LIT["files"].search(t).group(1) == json.dumps(old_files), f"{p}: file list serialisation differs"
    chunks = B.split_blob(blob_new, STEM)
    assert [n for n, _ in chunks] == [f["path"] for f in old_files], "geo file set would change; not handled"
    files = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    import base64
    changed = []
    for n, c in chunks:
        p = d / n; new = base64.b64encode(c)
        if p.read_bytes() != new:
            bk = p.with_name(p.name + ".q358")
            if not bk.exists():
                shutil.copy2(p, bk)
            p.write_bytes(new); changed.append(n)
    for p, t in texts.items():
        bk = p.with_name(p.name + ".q358")
        if not bk.exists():
            shutil.copy2(p, bk)
        t2 = C340.LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + C340.ser_manifest(man_new) + ";", t, count=1)
        t2 = C340.LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8"); changed.append(p.name)
    return changed


# ------------------------------------------------------------------ small helpers
def stats(x):
    x = np.asarray(x, float)
    if not len(x):
        return None
    return {"median": round(float(np.median(x)), 2), "p90": round(float(np.percentile(x, 90)), 2),
            "max": round(float(x.max()), 2), "n": int(len(x))}


def comp_labels(f):
    t = trimesh.Trimesh(np.zeros((int(f.max()) + 1, 3)), f, process=False)
    adj = t.face_adjacency
    A = sparse.coo_matrix((np.ones(len(adj)), (adj[:, 0], adj[:, 1])), shape=(len(f), len(f)))
    return connected_components(A, directed=False)[1]


def boundary_edges(f):
    """directed boundary edges (a, b) as they appear in the faces"""
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    key = np.sort(e, axis=1)
    u, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    return e[cnt[inv.ravel()] == 1]


def slab(outer_v, inner_v, fo):
    """closed slab from an outer sheet (faces fo, outward) and per-vertex inner positions: inner sheet reversed + rim wall"""
    used = np.unique(fo)
    remap = -np.ones(len(outer_v), int); remap[used] = np.arange(len(used))
    po, pi = outer_v[used], inner_v[used]
    f = remap[fo]; nv = len(po)
    walls = []
    for a, b in boundary_edges(f):
        walls += [[b, a, a + nv], [b, a + nv, b + nv]]
    F = np.vstack([f, f[:, ::-1] + nv] + ([np.array(walls, int)] if walls else []))
    return np.vstack([po, pi]), F, used


def ray_cast(mesh, O, D, multiple=False, chunk=48):
    """(ray index, distance along D, face) of the hits, in chunks of rays (the triangle broad phase of a long ray is large)"""
    R, T, Fh = [], [], []
    for a in range(0, len(O), chunk):
        loc, ri, fi = mesh.ray.intersects_location(O[a:a + chunk], D[a:a + chunk], multiple_hits=multiple)
        if len(ri):
            R.append(ri + a); T.append(np.einsum("ij,ij->i", loc - O[ri + a], D[ri + a])); Fh.append(fi)
    if not R:
        return np.zeros(0, int), np.zeros(0), np.zeros(0, int)
    return np.concatenate(R), np.concatenate(T), np.concatenate(Fh)


def ray_hits(mesh, O, D, multiple=False):
    """distances along D from O of the hits (first, or all as a sorted list per ray)"""
    if mesh is None or not len(mesh.faces):
        return [[] for _ in O] if multiple else np.full(len(O), np.inf)
    ri, t, _ = ray_cast(mesh, O, D, multiple)
    if multiple:
        out = [[] for _ in O]
        for i, tt in zip(ri, t):
            out[i].append(float(tt))
        return [sorted(x) for x in out]
    best = np.full(len(O), np.inf)
    np.minimum.at(best, ri, t)
    return best


def crop(v, f, lo, hi):
    c = v[f].mean(1)
    k = np.all((c >= lo) & (c <= hi), axis=1)
    return f[k]


# ------------------------------------------------------------------ the page's own landmarks
class Page:
    def __init__(self, man, blob):
        self.man, self.blob = man, blob
        self.M = {m["id"]: m for m in man["meshes"]}
        self._c = {}

    def V(self, k):
        if k not in self._c:
            self._c[k] = dec(self.M[k], self.blob)
        return self._c[k]

    def rails(self):
        L = json.loads(LOOP.read_text())["loop"]
        P = np.array([self.V(e["members"][0][0])[0][e["members"][0][1]] for e in L])
        Q = np.array([self.V(e["partner_members"][0][0])[0][e["partner_members"][0][1]] for e in L])
        return P, Q, L

    def landmarks(self):
        out = {}
        v = self.V("pubic_symphysis_disc")[0]
        out["pubic_symphysis_lower_end"] = v[v[:, 1].argmin()]
        for s in "lr":
            h = self.V(f"hip_bone_{s}")[0]
            post = h[h[:, 2] < h[:, 2].mean()]
            out[f"ischial_tuberosity_{s}"] = post[post[:, 1].argmin()]
            med = h[np.abs(h[:, 0]) < 40]
            out[f"ischiopubic_ramus_{s}_lowest_medial"] = med[med[:, 1].argmin()]
        c = self.V("coccyx")[0]
        out["coccyx_tip"] = c[c[:, 1].argmin()]
        pb = self.V("perineal_body")[0]
        out["perineal_body_lowest"] = pb[pb[:, 1].argmin()]
        return {k: [round(float(x), 1) for x in val] for k, val in out.items()}


def anus_point(pg: Page, skin_mesh):
    """where the anal canal axis (centre of the lowest fifth of the external anal sphincter) meets the skin, straight down"""
    v = pg.V("external_anal_sphincter_ct_vhf")[0]
    low = v[v[:, 1] < np.percentile(v[:, 1], 20)]
    c = low.mean(0); c[1] = low[:, 1].min()
    t = ray_hits(skin_mesh, c[None], np.array([[0.0, -1.0, 0.0]]))[0]
    return c, (c + np.array([0.0, -t, 0.0])) if np.isfinite(t) else None


# ------------------------------------------------------------------ the closing surface's domain (Coons patch on the rim)
def resample_poly(poly, n_per_seg):
    """points along a polyline: each segment cut into its own number of pieces, so every polyline vertex is a sample"""
    out = [poly[0]]
    for a, b, m in zip(poly[:-1], poly[1:], n_per_seg):
        for i in range(1, m + 1):
            out.append(a + (b - a) * i / m)
    return np.array(out)


def split_counts(poly, total):
    L = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    m = np.maximum(1, np.round(L / L.sum() * total)).astype(int)
    while m.sum() > total:
        m[np.argmax(m)] -= 1
    while m.sum() < total:
        m[np.argmax(L / m)] += 1
    return m


def smooth_real(po, pi, fo):
    """volume-preserving Taubin smoothing (lambda / mu) of the real surface's outer sheet: the source segmentation's facets are a
    sampling artefact, not anatomy. Border vertices (outer border and the source's own openings) pinned; every vertex's move capped
    at CAP_REAL; the inner sheet moves with its outer vertex (thickness kept)."""
    used = np.unique(fo)
    e = np.concatenate([fo[:, [0, 1]], fo[:, [1, 2]], fo[:, [2, 0]]])
    key = np.sort(e, axis=1)
    u, cnt = np.unique(key, axis=0, return_counts=True)
    pinned = np.zeros(len(po), bool); pinned[np.unique(u[cnt == 1])] = True
    ue = u
    A = sparse.coo_matrix((np.ones(2 * len(ue)), (np.r_[ue[:, 0], ue[:, 1]], np.r_[ue[:, 1], ue[:, 0]])), shape=(len(po), len(po))).tocsr()
    deg = np.asarray(A.sum(1)).ravel()
    mov = np.zeros(len(po), bool); mov[used] = True; mov &= ~pinned & (deg > 0)
    X0 = po.copy(); X = po.copy()
    for _ in range(SMOOTH_REAL_IT):
        for lam in (0.5, -0.53):
            L = (A @ X) / np.maximum(deg, 1)[:, None] - X
            X = np.where(mov[:, None], X + lam * L, X)
            D = X - X0; n = np.linalg.norm(D, axis=1)
            over = n > CAP_REAL
            X[over] = X0[over] + D[over] * (CAP_REAL / n[over])[:, None]
    D = X - X0; n = np.linalg.norm(D, axis=1)
    t0 = trimesh.Trimesh(X0, fo, process=False); t1 = trimesh.Trimesh(X, fo, process=False)
    # volume swept by the outer sheet (signed, + = outwards): the change of the enclosed volume the smoothing makes
    vn = t0.vertex_normals
    area_v = np.zeros(len(po)); np.add.at(area_v, fo.ravel(), np.repeat(t0.area_faces / 3.0, 3))
    swept = float(np.sum(np.einsum("ij,ij->i", D, vn) * area_v))
    rep = {"method": f"Taubin lambda 0.5 / mu -0.53, {SMOOTH_REAL_IT} rounds, border vertices pinned, per-vertex cap {CAP_REAL:g} mm",
           "source_spacing": "not recoverable (the source mesh is decimated: vertex coordinates lie on no grid, median edge 5.2 mm); "
                             "cap 1.0 mm as for an unknown spacing",
           "vertices_moved": int((n > 1e-6).sum()), "pinned": int(pinned[used].sum()),
           "move_max_mm": round(float(n.max()), 3), "move_mean_mm": round(float(n[mov].mean()), 3),
           "outer_area_mm2": [round(float(t0.area), 1), round(float(t1.area), 1)],
           "volume_swept_by_outer_sheet_mm3": round(swept, 1),
           "slab_volume_change_pct": round(100.0 * swept / max(t0.area * THICK, 1e-9), 3)}
    return X, pi + D, rep


def domain(P, Q):
    """rows along the two rim rails (left P[0..16], right P[32..16]); row 0 = the anal-region border P0-P35-P34-P33-P32; the last
    row = the apex P16 (mons, midline). Returns the row rails (outer and inner) and the Coons patch of the opening (rows x NF+1)."""
    assert len(P) == 36, "the Q202 loop has 36 rim vertices"
    left = list(range(0, 17)); right = [32 - k for k in range(17)]
    rows = []
    for k in range(16):
        ell = 0.5 * (np.linalg.norm(P[left[k + 1]] - P[left[k]]) + np.linalg.norm(P[right[k + 1]] - P[right[k]]))
        m = max(1, int(round(ell / ROW_MM)))
        rows += [(k, i / m) for i in range(m)]
    rows.append((16, 0.0))

    def rail(idx, k, s, A):
        a = A[idx[k]]
        return a if s == 0 else a + s * (A[idx[k + 1]] - a)

    Lp = np.array([rail(left, k, s, P) for k, s in rows]); Rp = np.array([rail(right, k, s, P) for k, s in rows])
    Lq = np.array([rail(left, k, s, Q) for k, s in rows]); Rq = np.array([rail(right, k, s, Q) for k, s in rows])
    bot = [0, 35, 34, 33, 32]
    cnt = split_counts(P[bot], NF)
    Bp, Bq = resample_poly(P[bot], cnt), resample_poly(Q[bot], cnt)
    arc = np.r_[0, np.cumsum(0.5 * (np.linalg.norm(np.diff(Lp, axis=0), axis=1) + np.linalg.norm(np.diff(Rp, axis=0), axis=1)))]
    v = (arc / arc[-1])[:, None, None]
    u = np.linspace(0, 1, NF + 1)[None, :, None]
    T = P[16][None, None]
    S = ((1 - u) * Lp[:, None] + u * Rp[:, None] + (1 - v) * Bp[None] + v * T
         - ((1 - u) * (1 - v) * P[0] + u * (1 - v) * P[32] + (1 - u) * v * T + u * v * T))
    S[0] = Bp; S[-1] = P[16]; S[:, 0] = Lp; S[:, -1] = Rp
    return dict(rows=rows, Lp=Lp, Rp=Rp, Lq=Lq, Rq=Rq, Bp=Bp, Bq=Bq, bot_counts=cnt, S=S, Q16=Q[16], P16=P[16])


def row_frames(D, centre):
    """one inward direction per row (the Coons patch's mean normal over the row, at right angles to the row's chord, pointing into
    the body) -- straight rays in the row's own plane"""
    S = D["S"]; NR = len(S)
    U = np.zeros((NR, 3))
    for r in range(NR):
        if r in (0, NR - 1):
            continue
        ex = D["Rp"][r] - D["Lp"][r]; ex /= np.linalg.norm(ex)
        a, b = S[max(r - 1, 0)], S[min(r + 1, NR - 1)]
        dv = (b - a).mean(0)
        n = np.cross(ex, dv); n -= (n @ ex) * ex; n /= np.linalg.norm(n)
        if n @ (centre - S[r].mean(0)) < 0:
            n = -n
        U[r] = n
    for _ in range(3):                                              # smooth the directions across rows
        U2 = U.copy()
        for r in range(1, NR - 1):
            w = U[max(r - 1, 1):min(r + 2, NR - 1)].sum(0)
            ex = D["Rp"][r] - D["Lp"][r]; ex /= np.linalg.norm(ex)
            w -= (w @ ex) * ex; U2[r] = w / np.linalg.norm(w)
        U = U2
    U[0], U[-1] = U[1], U[-2]
    return U


def solve_heights(lb, ub, fixed, du, dr, it=SMOOTH_IT, omega=1.8):
    """projected SOR on the rows x samples grid: harmonic (anisotropic: du per row, dr between rows) between the fixed border (0)
    and the constraints lb <= h <= ub (ub wins where they cross)"""
    NR, NC = lb.shape
    h = np.zeros((NR, NC))
    wu = 1.0 / du[:, None] ** 2 * np.ones((1, NC)); wr = np.full((NR, NC), 1.0 / dr ** 2)
    rb = (np.add.outer(np.arange(NR), np.arange(NC)) % 2).astype(bool)
    lo = np.where(np.isfinite(lb), lb, -np.inf); hi = np.where(np.isfinite(ub), ub, np.inf)
    for _ in range(it):
        for colour in (False, True):
            m = (rb == colour) & ~fixed
            up = np.vstack([h[1:], h[-1:]]); dn = np.vstack([h[:1], h[:-1]])
            lf = np.hstack([h[:, :1], h[:, :-1]]); rt = np.hstack([h[:, 1:], h[:, -1:]])
            g = (wu * (lf + rt) + wr * (up + dn)) / (2 * wu + 2 * wr)
            hn = h + omega * (g - h)
            hn = np.minimum(np.maximum(hn, lo), hi)
            h = np.where(m, hn, h)
    return h


def beyond_rim(D, U, pts):
    """True where a point lies past the free rim of the opening: the line through it along the local inward direction (that of
    the nearest sample of the Coons patch) does not cross the patch -- it lies beside the rails, behind the anal border or above
    the mons rim, i.e. over a neighbouring region"""
    S = D["S"]; NR, NC = S.shape[:2]
    idx = np.arange(NR * NC).reshape(NR, NC)
    F = np.vstack([np.c_[idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel()],
                   np.c_[idx[:-1, :-1].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()]])
    patch = trimesh.Trimesh(S.reshape(-1, 3), F, process=False)
    Ug = np.repeat(U[:, None, :], NC, axis=1).reshape(-1, 3)
    u = Ug[cKDTree(S.reshape(-1, 3)).query(pts)[1]]
    ri, _, _ = ray_cast(patch, pts + 150.0 * u, -u)
    inside = np.zeros(len(pts), bool); inside[ri] = True
    return ~inside


def neighbour_outer(pg: Page, P):
    """outer sheets of the Z skin patches around the opening (Q202 split_slab against the bones), cropped to 110 mm"""
    import q202_geom as GG
    bones = np.vstack([pg.V(k)[0] for k in ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx", "femur_l", "femur_r")])
    bt = cKDTree(bones)
    V, Fs, n = [], [], 0
    c0 = P.mean(0)
    for m in pg.man["meshes"]:
        if m["sys"] != "skin" or m["id"] in (CVH_ID, NEW_ID):
            continue
        v, f = pg.V(m["id"])
        if np.linalg.norm(v - c0, axis=1).min() > 120:
            continue
        mo, _, _, _ = GG.split_slab(v, f, bt)
        fo = f[mo]
        fo = fo[np.linalg.norm(v[fo].mean(1) - c0, axis=1) < 130]
        V.append(v); Fs.append(fo + n); n += len(v)
    return trimesh.Trimesh(np.vstack(V), np.vstack(Fs), process=False)


def build(pg: Page, log=print):
    rep = {"atlas_facts": ATLAS}
    P, Q, Lraw = pg.rails()
    rep["rim"] = {"vertices": int(len(P)), "perimeter_mm": round(float(np.linalg.norm(P - np.roll(P, -1, 0), axis=1).sum()), 1),
                  "neighbours": sorted({m[0] for e in Lraw for m in e["members"]}),
                  "outer_inner_gap_mm": stats(np.linalg.norm(P - Q, axis=1))}
    lm = pg.landmarks()
    D = domain(P, Q)
    S = D["S"]; NR = len(S)
    centre = np.array(lm["perineal_body_lowest"]) + np.array([0.0, 30.0, 0.0])
    U = row_frames(D, centre)
    rep["domain"] = {"rows": int(NR), "samples_per_row": NF + 1, "coons_area_mm2": None}

    # ---- 1. the real surface: clean (no vertex moves)
    vc, fc = pg.V(CVH_ID)
    n2 = len(vc) // 2
    outer_f = np.all(fc < n2, axis=1)
    assert np.all(fc[~outer_f].max(1) >= n2), "skin_vulva_cvh is not the Q336 slab layout"
    fo = fc[outer_f]
    po, pi = vc[:n2], vc[n2:]
    lab_all = comp_labels(fc); sizes = np.bincount(lab_all)
    loose = [dict(faces=int(s), area_mm2=round(float(trimesh.Trimesh(vc, fc[lab_all == c], process=False).area), 1),
                  centroid=[round(float(x), 1) for x in vc[np.unique(fc[lab_all == c])].mean(0)])
             for c, s in enumerate(sizes) if s < MIN_PIECE]
    fo_keep = np.isin(lab_all, [c for c, s in enumerate(sizes) if s >= MIN_PIECE])[outer_f]
    zo = neighbour_outer(pg, P)
    q, _, tri = trimesh.proximity.closest_point(zo, po)
    nz = zo.face_normals[tri]
    s_out = np.einsum("ij,ij->i", po - q, nz)
    tang = np.linalg.norm((po - q) - s_out[:, None] * nz, axis=1)
    beyond = beyond_rim(D, U, po)
    proud = beyond & ~((tang < TANG_MAX) & (s_out <= -PROUD_MM))   # past the rim and not safely under a neighbour's outer surface
    fo_ok = fo_keep & ~proud[fo].any(1)
    lab = comp_labels(fo[fo_ok])
    big = np.argmax(np.bincount(lab))
    sel = np.zeros(len(fo), bool); sel[np.flatnonzero(fo_ok)[lab == big]] = True
    other_pieces = [int(s) for c, s in enumerate(np.bincount(lab)) if c != big]
    kept_fo = fo[sel]
    sm = None
    if SMOOTH_REAL:
        po, pi, sm = smooth_real(po, pi, kept_fo)
        log(f"  real surface smoothed (Taubin, cap {CAP_REAL:g} mm): max {sm['move_max_mm']} / mean {sm['move_mean_mm']} mm")
    Vc, Fc, _ = slab(po, pi, kept_fo)
    cvh_inside = trimesh.Trimesh(po, kept_fo[~beyond[kept_fo].any(1)], process=False)   # the part over the opening: it shapes the rule
    cvh_outer = trimesh.Trimesh(po, kept_fo, process=False)
    removed = trimesh.Trimesh(po, fo[~sel], process=False)
    rep["real_surface_cleaning"] = {
        "id": CVH_ID, "published": {"vertices": int(len(vc)), "triangles": int(len(fc)),
                                     "outer_area_mm2": round(float(trimesh.Trimesh(po, fo, process=False).area), 1),
                                     "outer_vertices_in_front_of_neighbour_skin": int(((tang < TANG_MAX) & (s_out > 0)).sum()),
                                     "max_in_front_mm": round(float(s_out[tang < TANG_MAX].max()), 2)},
        "loose_pieces_removed": loose,
        "outer_faces_removed": {"rule": f"a face with a vertex over a neighbouring skin region and less than {PROUD_MM:g} mm under its "
                                        "outer surface (it showed through / stood in front of it), then every piece cut off from "
                                        "the main surface",
                                "proud_faces": int((fo_keep & proud[fo].any(1)).sum()),
                                "pieces_cut_off_faces": other_pieces,
                                "total_outer_faces_removed": int((~sel).sum()), "area_removed_mm2": round(float(removed.area), 1)},
        "kept": {"outer_triangles": int(len(kept_fo)), "outer_area_mm2": round(float(cvh_outer.area), 1),
                 "slab_vertices": int(len(Vc)), "slab_triangles": int(len(Fc)),
                 "watertight": bool(trimesh.Trimesh(Vc, Fc, process=False).is_watertight)},
        "vertices_moved": 0 if sm is None else sm["vertices_moved"], "staircase_smoothing": sm}
    log(f"  real surface: {len(fo)} -> {len(kept_fo)} outer faces (proud {int((fo_keep & proud[fo].any(1)).sum())}, "
        f"cut-off pieces {other_pieces[:8]}), removed {removed.area:.0f} mm2, kept {cvh_outer.area:.0f} mm2")

    # ---- 2. constraints along each row's inward direction, at every sample of the Coons patch
    Ug = np.repeat(U[:, None, :], NF + 1, axis=1)
    X0 = S.reshape(-1, 3); Uf = Ug.reshape(-1, 3)
    fixed = np.zeros((NR, NF + 1), bool); fixed[0] = fixed[-1] = True; fixed[:, 0] = fixed[:, -1] = True
    inner = np.flatnonzero(~fixed.ravel())
    O = X0[inner] - REACH * Uf[inner]
    hits = ray_hits(cvh_inside, O, Uf[inner], multiple=True)
    lb = np.full(X0.shape[0], -np.inf); first = np.full(X0.shape[0], np.inf)
    for i, h_ in zip(inner, hits):
        t = np.array(h_) - REACH
        t = t[(t > -HIT_OUT) & (t < HIT_IN)]
        if len(t):
            first[i] = t[0]
            lb[i] = first[i] + RULE_GAP
    lo, hi = X0.min(0) - DEEP_REACH, X0.max(0) + DEEP_REACH
    mtree = cKDTree(X0)
    DV, DF, Down, n0 = [], [], [], 0
    for m in pg.man["meshes"]:
        if m["sys"] in NOT_DEEP:
            continue
        v, f = pg.V(m["id"])
        if np.any(v.max(0) < lo) or np.any(v.min(0) > hi):
            continue
        fk = crop(v, f, lo, hi)
        if len(fk):
            fk = fk[mtree.query(v[fk].mean(1), distance_upper_bound=DEEP_REACH)[0] < DEEP_REACH]
        if not len(fk):
            continue
        DV.append(v); DF.append(fk + n0); Down += [m["id"]] * len(fk); n0 += len(v)
    deep = trimesh.Trimesh(np.vstack(DV), np.vstack(DF), process=False)
    Down = np.array(Down)
    log(f"  deeper structures near the opening: {len(set(Down))} meshes, {len(deep.faces)} faces")
    ri, tt, ti = ray_cast(deep, O, Uf[inner], True)
    td = np.full(X0.shape[0], np.inf); who = np.array([""] * X0.shape[0], dtype=object)
    for i, t_, f_ in zip(inner[ri], tt - REACH, ti):
        if t_ < td[i]:
            td[i] = t_; who[i] = Down[f_]
    lb = lb.reshape(NR, NF + 1); td = td.reshape(NR, NF + 1); first = first.reshape(NR, NF + 1)
    # a deeper structure behind the real surface's outer layer is covered by it already: it bounds the rule surface only where it
    # lies in front of that layer (or where there is no real surface)
    hidden_by_real = td > first
    # ... but not near the real surface's edge, where the structure is seen past it from an oblique view: the whole neighbourhood
    # (+-EDGE_W mm along the row, +-2 rows) must be over the real surface
    has = np.isfinite(first)
    chord0 = np.linalg.norm(D["Rp"] - D["Lp"], axis=1); du0 = np.maximum(chord0 / NF, 0.05)
    cov = has.copy()
    for r in range(1, NR - 1):
        w = int(np.ceil(EDGE_W / du0[r]))
        for rr in range(max(1, r - 2), min(NR - 1, r + 3)):
            for sft in range(-w, w + 1, max(1, w // 6)):
                cov[r] &= np.roll(has[rr], sft)
    hidden_by_real &= cov
    ub = np.where(hidden_by_real, np.inf, td - (THICK + DEEP_GAP))
    # side clearance: a structure beside a sample's ray still bounds it (min over +-WIN mm along the row, +-1 row)
    chord = np.linalg.norm(D["Rp"] - D["Lp"], axis=1); du = np.maximum(chord / NF, 0.05)
    ub2 = ub.copy(); lb2 = lb.copy()
    for r in range(1, NR - 1):
        w = int(np.ceil((THICK + DEEP_GAP + 1.0) / du[r])); wl = int(np.ceil(LB_WIN / du[r]))
        for rr in (r - 1, r, r + 1):
            if 0 < rr < NR - 1:
                for sft in range(-w, w + 1):
                    ub2[r] = np.minimum(ub2[r], np.roll(ub[rr], sft) if True else ub[rr])
        for sft in range(-wl, wl + 1):
            lb2[r] = np.maximum(lb2[r], np.roll(lb[r], sft))
    ub, lb = ub2, lb2
    # where the real surface's constraint and the full clearance cross, the rule surface may come within DEEP_HARD of the
    # structure (it stays in front of it, under its own slab); only beyond that does the structure win (counted)
    ub_hard = td - DEEP_HARD
    ub = np.where(np.isfinite(lb) & (lb > ub) & np.isfinite(ub), np.maximum(ub, np.minimum(lb, ub_hard)), ub)
    who = who.reshape(NR, NF + 1)
    ub[:, 0] = ub[:, -1] = np.inf
    # ---- 3. heights
    h = solve_heights(lb, ub, fixed, du, ROW_MM)
    conflict = ~fixed & np.isfinite(lb) & (lb > ub)
    Xg = S + h[..., None] * Ug
    # ---- 4. rows resampled by arc length (walls get their share of vertices), exact rim on both ends, apex fan
    cnt_row = COLS
    rows_out = [resample_poly(D["Bp"], split_counts(D["Bp"], cnt_row))]
    rows_in = [resample_poly(D["Bq"], split_counts(D["Bp"], cnt_row))]
    for r in range(1, NR - 1):
        pl = Xg[r]
        sl = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pl, axis=0), axis=1))]
        # walls (a row much longer than its chord) are resampled by arc length; flat rows keep the patch's own parameter
        beta = float(np.clip((sl[-1] / max(chord[r], 1e-6) - 1.0) / 0.5, 0.0, 1.0))
        su = np.linspace(0, 1, NF + 1)
        t = np.linspace(0, 1, cnt_row + 1)
        s_arc = np.interp(t * sl[-1], sl, su)
        s_use = (1 - beta) * t + beta * s_arc
        rows_out.append(np.array([np.interp(s_use, su, pl[:, k]) for k in range(3)]).T)
        rows_in.append(None)
    # the posterior cap (anal-region border -> first row, which already climbs the walls): CAP_ROWS blended rows in between
    Lq_rows = [D["Lq"][0]] + [D["Lq"][r] for r in range(1, NR - 1)]
    Rq_rows = [D["Rq"][0]] + [D["Rq"][r] for r in range(1, NR - 1)]
    ins = [(1 - a_) * rows_out[0] + a_ * rows_out[1] for a_ in np.linspace(0, 1, CAP_ROWS + 2)[1:-1]]
    insL = [(1 - a_) * Lq_rows[0] + a_ * Lq_rows[1] for a_ in np.linspace(0, 1, CAP_ROWS + 2)[1:-1]]
    insR = [(1 - a_) * Rq_rows[0] + a_ * Rq_rows[1] for a_ in np.linspace(0, 1, CAP_ROWS + 2)[1:-1]]
    rows_out = rows_out[:1] + ins + rows_out[1:]
    Lq_rows = Lq_rows[:1] + insL + Lq_rows[1:]; Rq_rows = Rq_rows[:1] + insR + Rq_rows[1:]
    rowU = [U[1]] + [U[1]] * CAP_ROWS + [U[r] for r in range(1, NR - 1)]
    NRo = len(rows_out)
    idx = np.arange(NRo * (cnt_row + 1)).reshape(NRo, cnt_row + 1)
    apex = NRo * (cnt_row + 1)
    X = np.vstack(rows_out + [D["P16"][None]])
    F = []
    for r in range(NRo - 1):
        for j in range(cnt_row):
            a, b, c, d = idx[r, j], idx[r, j + 1], idx[r + 1, j], idx[r + 1, j + 1]
            if np.linalg.norm(X[a] - X[d]) < np.linalg.norm(X[b] - X[c]):
                F += [[a, b, d], [a, d, c]]
            else:
                F += [[a, b, c], [b, d, c]]
    for j in range(cnt_row):
        F.append([idx[-1, j], idx[-1, j + 1], apex])
    F = np.array(F)
    B0 = np.zeros(len(X), bool); B0[idx[0]] = True; B0[idx[:, 0]] = True; B0[idx[:, -1]] = True; B0[apex] = True
    Xi0 = np.zeros_like(X)
    Xi0[idx[0]] = rows_in[0]
    for r in range(NRo):
        Xi0[idx[r, 0]] = Lq_rows[r]; Xi0[idx[r, -1]] = Rq_rows[r]
    Xi0[apex] = D["Q16"]
    Urow = np.vstack([np.repeat(np.array(rowU)[:, None], cnt_row + 1, axis=1).reshape(-1, 3), U[-2][None]])
    # Taubin smoothing of the interior (rounds the creases where a wall meets the floor; the border stays exact)
    e = trimesh.Trimesh(X, F, process=False).edges_unique
    Ad = sparse.coo_matrix((np.ones(2 * len(e)), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(len(X), len(X))).tocsr()
    dg = np.asarray(Ad.sum(1)).ravel()
    for _ in range(TAUBIN_IT):
        for lam in (0.5, -0.53):
            Lx = (Ad @ X) / dg[:, None] - X
            X = np.where(B0[:, None], X, X + lam * Lx)
    outer = trimesh.Trimesh(X, F, process=False)
    if np.mean(np.einsum("ij,ij->i", outer.face_normals, -Urow[F[:, 0]])) < 0:
        F = F[:, ::-1]; outer = trimesh.Trimesh(X, F, process=False)
    nin = -outer.vertex_normals
    Xi = np.where(B0[:, None], Xi0, X + THICK * nin)
    Vr, Fr, _ = slab(X, Xi, F)
    sl_ = trimesh.Trimesh(Vr, Fr, process=False)
    # folds: neighbouring faces turned against each other by more than FOLD_DEG (a crease folded back on itself)
    fa = outer.face_adjacency[outer.face_adjacency_angles > np.radians(FOLD_DEG)]
    big_enough = (outer.area_faces[fa[:, 0]] > 0.05) & (outer.area_faces[fa[:, 1]] > 0.05)
    flip = np.zeros(len(F), bool); flip[fa[big_enough].ravel()] = True
    ar = outer.area_faces
    el = np.linalg.norm(X[F] - X[np.roll(F, 1, axis=1)], axis=2)
    aspect = el.max(1) ** 2 / np.maximum(2 * ar, 1e-9)
    stretch = np.array([el.max(), np.percentile(aspect[ar > 0.05], 99.5)])
    # the rule surface in front of the kept real surface? (sampled: rays from outside along the row direction)
    Oc = X[~B0] - 60.0 * Urow[~B0]
    t_rule = ray_hits(outer, Oc, Urow[~B0]); t_cvh = ray_hits(cvh_outer, Oc, Urow[~B0])
    over_real = np.isfinite(t_cvh) & (t_rule < t_cvh - COVER_TOL)
    hid = np.zeros(len(X), bool); hid[np.flatnonzero(~B0)] = np.isfinite(t_cvh) & ~over_real
    vis_area = float(outer.area_faces[~np.all(hid[F], axis=1)].sum())
    rep["rule_surface"] = {
        "id": NEW_ID, "vertices": int(len(Vr)), "triangles": int(len(Fr)), "thickness_mm": THICK,
        "outer_area_mm2": round(float(outer.area), 1), "volume_cm3": round(float(abs(sl_.volume)) / 1000.0, 3),
        "watertight": bool(sl_.is_watertight), "winding_consistent": bool(sl_.is_winding_consistent),
        "height_along_row_normal_mm": stats(h[~fixed]),
        "samples_under_real_surface": int((np.isfinite(lb) & ~fixed & ~conflict).sum()),
        "samples_bounded_by_deeper_structures": int((np.isfinite(td) & ~fixed).sum()),
        "deep_wins_over_real_surface_samples": int(conflict.sum()),
        "deep_wins_structures": sorted(set(str(x) for x in who[conflict].tolist()) - {""}),
        "vertices_in_front_of_real_surface": int(over_real.sum()),
        "faces_folded": int(flip.sum()), "folded_area_mm2": round(float(outer.area_faces[flip].sum()), 1),
        "area_visible_estimate_mm2": round(vis_area, 1),
        "longest_edge_mm": round(float(stretch[0]), 2), "aspect_p99_5": round(float(stretch[1]), 1),
    }
    log(f"  rule surface: {len(Vr)} v / {len(Fr)} t, outer area {outer.area:.0f} mm2, {abs(sl_.volume) / 1000:.2f} cm3, "
        f"watertight {sl_.is_watertight}, deep-wins {int(conflict.sum())} {rep['rule_surface']['deep_wins_structures'][:6]}, "
        f"folded {int(flip.sum())}, longest edge {stretch[0]:.1f} mm, aspect p99.5 {stretch[1]:.0f}, over real {int(over_real.sum())}")
    rep["landmarks"] = lm
    rep["_geo"] = dict(Vc=Vc, Fc=Fc, Vr=Vr, Fr=Fr, X=X, F=F, U=Urow, h=h, lb=lb, td=td, X0=X, B0=B0, cvh_outer=cvh_outer,
                       outer=outer)
    return rep


# ------------------------------------------------------------------ checks on the result (all skin of the region)
def region_skin(pg: Page, extra):
    lo, hi = REGION
    V, Fs, n = [], [], 0
    for m in pg.man["meshes"]:
        if m["sys"] != "skin" or m["id"] in extra:
            continue
        v, f = pg.V(m["id"])
        if np.any(v.max(0) < lo - 20) or np.any(v.min(0) > hi + 20):
            continue
        V.append(v); Fs.append(f + n); n += len(v)
    for v, f in extra.values():
        V.append(v); Fs.append(f + n); n += len(v)
    return trimesh.Trimesh(np.vstack(V), np.vstack(Fs), process=False)


def ring_open(tm, ylo=-140.0, yhi=-40.0, P=1.5, K=2):
    """the Q337 / Q353 ring test: axial slices of the region whose skin outline does not close"""
    from scipy import ndimage
    sp, _ = trimesh.sample.sample_surface(tm, int(tm.area * 4), seed=2)
    sp = sp[(sp[:, 1] >= ylo) & (sp[:, 1] <= yhi) & (np.abs(sp[:, 0]) < 200)]
    lo = sp.min(0) - 12; hi = sp.max(0) + 12
    shp = np.ceil((hi - lo) / P).astype(int) + 1
    occ = np.zeros(shp, bool)
    ijk = np.floor((sp - lo) / P).astype(int); occ[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = True
    d = ndimage.binary_dilation(occ, ndimage.generate_binary_structure(3, 1), iterations=K)
    lev = []
    for j in range(shp[1]):
        s_ = d[:, j, :]
        if not s_.any():
            continue
        fl = ndimage.binary_fill_holes(s_)
        if fl.sum() < s_.sum() * 1.15 and s_.sum() > 200:
            lev.append(round(float(lo[1] + j * P)))
    return lev


def see_through(tm, X, U, reach=15.0):
    """rays from outside along the inward normal onto the opening's own points: a ray that passes 15 mm beyond its point without
    meeting skin is a hole"""
    O = X - 150.0 * U
    t = ray_hits(tm, O, U)
    return {"rays": int(len(O)), "open": int((t > 150.0 + reach).sum()), "open_share": round(float((t > 150.0 + reach).mean()), 4)}


# ------------------------------------------------------------------ guarded tuck of what still shows (the Q353 rule and guards)
def q353():
    sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q353"))
    import conform_skin_q353 as T353
    return T353


def inject(g, k, v, f):
    """put a new / re-cut skin slab built by slab() into a Q353 Geo (its sheets are known: outer faces first, then inner, then wall)"""
    g.V0[k] = (v, f); g.cur[k] = v.copy(); g.F[k] = f; g.sys[k] = "skin"
    g.M.setdefault(k, {"id": k, "sys": "skin"})
    n2 = len(v) // 2
    cls = np.where(np.all(f < n2, axis=1), 1, np.where(np.all(f >= n2, axis=1), -1, 0))
    g._sheet[k] = (cls, np.zeros((0, 2), int))


def tuck_side(T, g, k, sk, bones):
    """the Q353 tuck on one structure: standard tries, then the same tries with gentler envelope slopes (TUCK_SLOPES)"""
    import functools
    v0 = g.cur[k].copy()
    r = T.run_tuck(g, k, sk, bones, lambda *_: None)
    if r["ships"]:
        r["envelope_slope"] = T.K_ENV
        return r
    orig = T.envelope
    fails = [dict(envelope_slope=T.K_ENV, reason=r.get("reason"))]
    try:
        for kk in TUCK_SLOPES:
            T.envelope = functools.partial(orig, K=kk)
            g.cur[k] = v0.copy()
            r2 = T.run_tuck(g, k, sk, bones, lambda *_: None)
            if r2["ships"]:
                r2.update(envelope_slope=kk, earlier=fails)
                return r2
            fails.append(dict(envelope_slope=kk, reason=r2.get("reason")))
    finally:
        T.envelope = orig
    g.cur[k] = v0
    r.update(ships=False, reason="; ".join(f"slope {f['envelope_slope']}: {f['reason']}" for f in fails), per_slope=fails)
    return r


def tuck_round(d: Path, Vc, Fc, Vr, Fr, log=print):
    """structures of the region with vertices outside the closed skin are tucked under it by the Q353 rule (guarded, capped);
    exact mirror twins must pass by the same try on both sides, else both stay (Q353 / Q349). Returns (Geo, report)."""
    T = q353()
    g = T.Geo(d)
    lo, hi = REGION
    cand = [k for k in g.in_box(lo, hi) if g.sys[k] in T.VISIBLE_SYS and not k.startswith(("hip_bone", "femur", "sacrum", "coccyx"))
            and not NOT_TUCK.search(k)]
    # the region's skin only (each neighbouring region cropped to the box: a structure is judged here, not at the knee)
    crop_ids = []
    for k in g.in_box(lo - 20, hi + 20, sys_=("skin",)):
        if "nail_plate" in k:
            continue
        cls, rim = g.sheets(k)
        c = g.cur[k][g.F[k]].mean(1)
        keep = np.all((c >= lo - 15) & (c <= hi + 15), axis=1)
        ck = "crop:" + k
        g.V0[ck] = (g.cur[k], g.F[k][keep]); g.cur[ck] = g.cur[k]; g.F[ck] = g.F[k][keep]; g.sys[ck] = "skin"
        g._sheet[ck] = (cls[keep], rim); crop_ids.append(ck)
    sk0 = T.SkinSet(g, crop_ids)
    before = {k: T.outside_count(g, sk0, k) for k in cand}
    inject(g, CVH_ID, Vc, Fc); inject(g, NEW_ID, Vr, Fr)
    g.cur["crop:" + CVH_ID] = g.cur[CVH_ID]; g.F["crop:" + CVH_ID] = Fc; g._sheet["crop:" + CVH_ID] = g._sheet[CVH_ID]
    sk = T.SkinSet(g, crop_ids + [NEW_ID])
    mid = {k: T.outside_count(g, sk, k) for k in cand}
    todo = sorted(k for k in cand if mid[k]["outside"] > 0)
    bones = T.Bones(g, lo, hi)
    rep = {"rule": "Q353 tuck (scripts/anatomy/q353/conform_skin_q353.py run_tuck): move inward along the skin's inner normal to "
                   f"{T.GAP} mm under its inner sheet (fallback {T.HIDE} mm under the outer surface), Lipschitz envelope, cap "
                   f"{T.CAP_TUCK} mm; guards: flipped <= {T.FLIP_MAX} % of moved faces, stretch, no new vertex in bone, volume "
                   f"<= {T.VOL_MAX} %, none left outside; mirror twins by the same try",
           "structures": {}}
    done = set()
    for k in todo:
        if k in done:
            continue
        o = k[:-2] + ("_l" if k.endswith("_r") else "_r")
        a0, _ = T.mirror_err(g, k)
        if o in todo and a0 is not None and a0 < 0.1:
            v0k, v0o = g.cur[k].copy(), g.cur[o].copy()
            ok = False
            for tr in T.TUCK_TRIES:
                rk = T.run_tuck(g, k, sk, bones, lambda *_: None, tries=[tr])
                ro = T.run_tuck(g, o, sk, bones, lambda *_: None, tries=[tr])
                if rk["ships"] and ro["ships"]:
                    ok = True
                    break
                g.cur[k], g.cur[o] = v0k.copy(), v0o.copy()
            if not ok:
                # Q358 follow-up: no common try -- each side on its own, the same guards evaluated per side (moved faces only),
                # with the standard tries and then a gentler envelope slope (wider, smaller-gradient move; the guards unchanged)
                g.cur[k], g.cur[o] = v0k.copy(), v0o.copy()
                rk = tuck_side(T, g, k, sk, bones); ro = tuck_side(T, g, o, sk, bones)
                for r in (rk, ro):
                    r["independent_of_twin"] = True
            for x, r in ((k, rk), (o, ro)):
                rep["structures"][x] = dict(r, mirror_pair=[k, o])
            done |= {k, o}
        else:
            rep["structures"][k] = tuck_side(T, g, k, sk, bones)
            done.add(k)
    for x, r in rep["structures"].items():
        b = r["before"]
        log(f"    tuck {x}: outside {b['outside']} (max {b['max_out_mm']} mm) -> "
            + (f"SHIPS ({r['mode']}, max {r['displacement']['max_mm']} mm)" if r["ships"] else f"KEPT ({r.get('reason')})"))
    after = {k: T.outside_count(g, sk, k) for k in cand}
    rep["outside_skin_vertices"] = {
        "before_q358": {k: v["outside"] for k, v in before.items() if v["outside"]},
        "after_closing_before_tuck": {k: v["outside"] for k, v in mid.items() if v["outside"]},
        "after": {k: v["outside"] for k, v in after.items() if v["outside"]},
        "after_max_mm": {k: v["max_out_mm"] for k, v in after.items() if v["outside"]},
        "gained_vs_before": sorted(k for k in cand if T.worse_than(before[k], after[k]))}
    return g, rep


# ------------------------------------------------------------------ cards
def new_entry(rep):
    r = rep["rule_surface"]; c = rep["real_surface_cleaning"]; lm = rep["landmarks"]
    facts = "; ".join(f"{v['fact']} ({v['cite']})" for v in ATLAS.values())
    badge = (
        "RULE-BASED SURFACE -- not scanned, not measured, not from any specimen. It closes the skin ring of the vulva and perineum "
        "where no source skin exists. "
        f"Made by a stated rule (Q358, scripts/anatomy/q358/perineum_skin_q358.py): a surface spanning the opening between this "
        f"body's skin regions (the free border of the medial thigh, femoral triangle, inguinal, hypogastric and anal-region skin, "
        f"{rep['rim']['vertices']} border vertices, shared exactly), interpolated between that border, the real vulvar surface "
        f"(`skin_vulva_cvh`, kept on top: this surface lies {RULE_GAP:g} mm behind its deepest layer) and the deeper structures "
        f"(kept {THICK:g} + {DEEP_GAP:g} mm under it), as a {THICK:g} mm closed slab like every skin region. "
        f"Outer area {r['outer_area_mm2']} mm2 (of which ~{r['area_visible_estimate_mm2']} mm2 not under the real surface), volume "
        f"{r['volume_cm3']} cm3. It forms the medial-thigh walls of the pudendal cleft, the skin between the vulva and the anal "
        "region over the perineal body, and closes the real surface's gaps; the mons pubis, labia and vestibule shown are the real "
        "surface. Landmarks of this body used to place and check it: pubic symphysis, ischiopubic rami, ischial tuberosities, "
        "coccyx, perineal body, the external anal sphincter (anus point) and the borders of the neighbouring skin regions. "
        f"Topography followed: {facts}. Limits: no pubic hair, no labial pigmentation, no separate labium majus object; the "
        "surface is rigid with the pelvis when the body is posed.")
    rec = {"name": "Perineal and labial closing skin (rule-based)", "latin": "Cutis perinei et pudendi (regula)",
           "folder": "skin", "region": "perineum",
           "source": "; ".join(sorted({v["cite"] for v in ATLAS.values()})) + "; placement: rule-based (this card)",
           "geom_src": "RULE-BASED (Q358): a surface made by a stated rule from this body's own skin borders and landmarks -- "
                       "NOT Z-Anatomy geometry and NOT a scan",
           "method": "rule-based closing surface (Coons patch on the neighbouring skin's free border + harmonic height field "
                     "constrained by the real vulvar surface and the deeper structures)",
           "procedural_badge": badge,
           "notes": "Closes the skin ring around the vulva: no skin region of the source bodies covers this band "
                    f"(c. {c['kept']['outer_area_mm2']} mm2 of real vulvar surface kept on top)."}
    return {"name": rec["name"], "id": NEW_ID, "side": "m", "sys": "skin", "rec": rec}


def cvh_note(rep):
    c = rep["real_surface_cleaning"]; o = c["outer_faces_removed"]
    return (f"|| {TAG} cleaning: {len(c['loose_pieces_removed'])} loose pieces removed; of the outer surface "
            f"{o['total_outer_faces_removed']} triangles ({o['area_removed_mm2']} mm2) removed -- those more than {TUCK_MM:g} mm past "
            "the border of the opening (they showed as fragments through the neighbouring skin) or rising out of it faster than "
            f"{RAMP_SLOPE:g} mm per mm (the hanging flap). "
            + (f"{TAG}: staircase facets of the source segmentation smoothed, max {c['staircase_smoothing']['move_max_mm']} mm "
               f"(cap {CAP_REAL:g} mm, border pinned). " if c.get("staircase_smoothing") else "no vertex moved. ")
            + "The skin ring around it is closed by the rule-based "
            f"`{NEW_ID}` lying behind it.")


# ------------------------------------------------------------------ pose rig (append rigid in the pelvis segment, as Q336)
def splice_rig(man_old, man_new, rig_path: Path, write: bool):
    src = json.loads(rig_path.read_text(encoding="utf-8"))
    R = src["rig"]
    ids_old = [m["id"] for m in man_old["meshes"]]; ids_new = [m["id"] for m in man_new["meshes"]]
    assert R["count"] == len(ids_old), f"rig count {R['count']} != page {len(ids_old)} (rig and page out of step)"
    assert ids_new[:-1] == ids_old and ids_new[-1] == NEW_ID, "existing indices must not move"
    nv_old = [int(m["vc"]) for m in man_old["meshes"]]
    assert nv_old == R["nv"], "the rig's vertex counts differ from the page: rig and page out of step"
    ci = ids_old.index(CVH_ID)
    seg = next(i for i, s_ in enumerate(R["segs"]) if s_[0] == "pelvis")
    rigid = {g[0]: list(g[1]) for g in R["rigid"]}
    assert ci in rigid.get(seg, []), "skin_vulva_cvh is not rigid in the pelvis segment"
    R2 = dict(R)
    R2["nv"] = [int(m["vc"]) for m in man_new["meshes"]]
    R2["count"] = len(ids_new)
    rigid.setdefault(seg, []).append(len(ids_old))
    R2["rigid"] = [[s_, sorted(v)] for s_, v in sorted(rigid.items())]
    R2["notes"] = R["notes"] + (f"; {TAG}: skin_vulva_cvh re-cut (vertex count {nv_old[ci]} -> {R2['nv'][ci]}, still rigid in the "
                                f"pelvis segment); +1 structure ({NEW_ID}, rule-based closing skin, appended so no index moved), "
                                "rigid in the pelvis segment; weights blob unchanged")
    out = dict(src); out["rig"] = R2
    if write:
        rig_path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return {"rig": str(rig_path), "count_before": R["count"], "count_after": R2["count"],
            "vulva_vertices": [nv_old[ci], R2["nv"][ci]], "written": bool(write)}


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    return o


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--rig-file", default=str(RIG), help="pose rig to splice (default the shared data/anatomy/pose_rig_base_f.json "
                                                         "-- ONLY when applying to the build page it describes; else pass a copy)")
    ap.add_argument("--no-rig", action="store_true")
    ap.add_argument("--no-smooth-real", action="store_true", help="skip the staircase smoothing of the real surface")
    ap.add_argument("--skip-checks", action="store_true", help="no ring / see-through / outside-skin measurement")
    ap.add_argument("--debug-npz", help="save the new geometry (and the membrane) to this .npz")
    a = ap.parse_args(argv)
    d = Path(a.page_dir)
    global SMOOTH_REAL
    SMOOTH_REAL = not a.no_smooth_real
    assert C340.pages_of(d, STEM), f"{d}: no {STEM}.html (Base · Female only)"
    t0 = time.time()
    man, blob, files = read(d)
    ids = [m["id"] for m in man["meshes"]]
    if NEW_ID in ids:
        print(f"Q358_PERINEUM_REFUSED {d}: the page already carries {NEW_ID} (an earlier Q358 result). Re-apply only on the page "
              f"before Q358: restore every '<file>.q358' beside its file in {d} and the pose rig (git checkout "
              f"data/anatomy/pose_rig_base_f.json), then run again.")
        return 3
    assert ids[-1] == CVH_ID, "skin_vulva_cvh is expected as the last mesh (Q336 layout)"
    pg = Page(man, blob)
    print(f"Q358 perineum skin on {d}")
    rep = build(pg)
    g = rep.pop("_geo")
    if a.debug_npz:
        np.savez_compressed(a.debug_npz, **{k: g[k] for k in ("Vc", "Fc", "Vr", "Fr", "X", "F", "U", "h", "lb", "td", "X0", "B0")})
    if not a.skip_checks:
        before = region_skin(pg, {})
        after = region_skin(pg, {CVH_ID: (g["Vc"], g["Fc"]), NEW_ID: (g["Vr"], g["Fr"])})
        rep["ring_open_slices_y_mm"] = {"before": ring_open(before), "after": ring_open(after), "range": [-140, -40]}
        rep["see_through_opening"] = {"before": see_through(before, g["X0"], g["U"]), "after": see_through(after, g["X0"], g["U"])}
        cA, pA = anus_point(pg, after)
        rep["anus_point"] = {"sphincter_axis_low": [round(float(x), 1) for x in cA],
                             "skin_point": None if pA is None else [round(float(x), 1) for x in pA]}
        print("  ring open (y) before", rep["ring_open_slices_y_mm"]["before"][:30], "after", rep["ring_open_slices_y_mm"]["after"][:30])
        print("  see-through", rep["see_through_opening"])
    replace = {}
    if not a.skip_checks:
        gt, tr = tuck_round(d, g["Vc"], g["Fc"], g["Vr"], g["Fr"])
        rep["tuck"] = tr
        for k, r in tr["structures"].items():
            if r["ships"]:
                rec = C340.badge_add(pg.M[k].get("rec") or {},
                                     f"|| {TAG} tuck: moved under the closed vulvar / perineal skin by the Q353 rule (rule-based; max "
                                     f"{r['displacement']['max_mm']} mm, cap 8 mm; vertex and triangle counts unchanged).")
                replace[k] = (gt.cur[k], gt.F[k], rec)
        print("  outside skin (vertices) after:", json.dumps(tr["outside_skin_vertices"]["after"])[:500],
              "gained:", tr["outside_skin_vertices"]["gained_vs_before"])
        del gt
    cv = pg.M[CVH_ID]
    rec_c = C340.badge_add(cv.get("rec") or {}, cvh_note(rep))
    entry = new_entry(rep)
    replace[CVH_ID] = (g["Vc"], g["Fc"], rec_c)
    man_new, blob_new = repack(man, blob, replace, [(entry, g["Vr"], g["Fr"])])
    # guard: the kept real vertices are byte-for-byte the published positions (re-quantised over a smaller bbox: within 0.01 mm)
    vchk, _ = dec(next(m for m in man_new["meshes"] if m["id"] == CVH_ID), blob_new)
    vpub, _ = pg.V(CVH_ID)
    dmax = float(cKDTree(vpub).query(vchk)[0].max())
    rep["guards"] = {"real_vertices_move_max_mm": round(dmax, 4), "real_move_cap_mm": CAP_REAL if SMOOTH_REAL else 0.05,
                     "rule_watertight": rep["rule_surface"]["watertight"],
                     "rule_winding_consistent": rep["rule_surface"]["winding_consistent"],
                     "rule_folded_faces": rep["rule_surface"]["faces_folded"],
                     "rule_stretch_ok": rep["rule_surface"]["longest_edge_mm"] <= EDGE_MAX,
                     "ring_closed": (not a.skip_checks) and not rep["ring_open_slices_y_mm"]["after"],
                     "no_structure_gains_outside_skin": (not a.skip_checks) and not rep["tuck"]["outside_skin_vertices"]["gained_vs_before"]}
    ok = (dmax <= (CAP_REAL + 0.01 if SMOOTH_REAL else 0.05) and rep["rule_surface"]["watertight"] and rep["rule_surface"]["winding_consistent"]
          and rep["rule_surface"]["folded_area_mm2"] <= FOLD_AREA_MAX and rep["guards"]["rule_stretch_ok"]
          and rep["guards"]["ring_closed"] and rep["guards"]["no_structure_gains_outside_skin"])
    rep["guards"]["pass"] = bool(ok)
    rep.update({"schema": "nmsk.q358.perineum.v1", "round": TAG, "generated": time.strftime("%Y-%m-%d"), "page_dir": str(d),
                "parameters": dict(thick_mm=THICK, row_mm=ROW_MM, cols=COLS, tuck_mm=TUCK_MM, ramp_slope=RAMP_SLOPE, ramp0_mm=RAMP0,
                                   min_piece_faces=MIN_PIECE, rule_gap_mm=RULE_GAP, depth_window_mm=DEPTH_WIN, deep_gap_mm=DEEP_GAP,
                                   deep_hard_mm=DEEP_HARD, smooth_rounds=SMOOTH_IT, edge_max_mm=EDGE_MAX),
                "meshes_before": len(man["meshes"]), "meshes_after": len(man_new["meshes"])})
    if a.write and ok:
        rep["files_written"] = write_page(d, man, man_new, blob_new, files)
        if not a.no_rig:
            rep["rig"] = splice_rig(man, man_new, Path(a.rig_file).resolve(), True)
    else:
        rep["files_written"] = []
        rep["rig"] = "dry run" if not a.write else "guards failed: nothing written"
    rep["seconds"] = round(time.time() - t0, 1)
    Path(a.report).write_text(json.dumps(jsonable(rep), indent=1), encoding="utf-8")
    print("  guards:", json.dumps(rep["guards"]))
    print(f"Q358_PERINEUM_{'WRITTEN' if (a.write and ok) else ('GUARD_FAIL' if not ok else 'DRY')} {d}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
