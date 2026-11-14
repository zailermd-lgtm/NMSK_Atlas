#!/usr/bin/env python3
"""Q322: innervation-zone (IZ) bands placed on each Base page's own geometry -- RULE-BASED.

For every band of `data/anatomy/innervation_q322.json` (IZ level = % along a named line between two named landmarks):
  1. the landmarks are measured on that page's own bone meshes (extreme vertex along an anatomical axis, left and right
     separately; `derived` = midpoint of its two `of` points; soft-tissue points = the proxy written in their definition,
     flagged `proxy`; `muscle_derived` = the ends of the muscle's own mesh along its principal axis);
  2. P = from + pct/100 * (to - from);
  3. `level` lines: the plane through P perpendicular to the line is cut with the muscle (or the part's own structure);
     the band = the cross-section outline (ring), the dot = the inside point nearest the section's inside centroid.
     If the plane misses the muscle by more than 5 mm the band is FAILED and nothing is drawn; a miss of up to 5 mm moves
     the plane onto the muscle and records the shift. `point` lines: P is snapped to the nearest point inside the muscle
     (FAILED when that is more than 5 mm away); the ring is the section through that point, perpendicular to the line.
     A qualitative site (no %) stores only the line, drawn in thirds.
Bony landmarks are anatomy, not clinical rules; nothing here reads the private clinical layer.

    python3 scripts/anatomy/q322/place_iz_q322.py                 # both Base pages -> data/derived/Q322_iz_bands_<page>.json
    python3 scripts/anatomy/q322/place_iz_q322.py base_f --html build/q309/viewer_base_female/atlas_viewer_base_female.html

Frame: page mm, +X right, +Y superior, +Z anterior (checked on the bones: humerus_r has +X, the calcaneus lies behind MT1).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q219"))
import geomlib as G  # noqa: E402  (load_zan / winding / inside: the published bodies' own meshes)

DATA = REPO / "data" / "anatomy" / "innervation_q322.json"
OUT = REPO / "data" / "derived" / "Q322_iz_bands_{page}.json"
PAGES = {"base_m": REPO / "build/q309/viewer_zan_atlas/atlas_viewer_zan_atlas.html",
         "base_f": REPO / "build/q309/viewer_base_female/atlas_viewer_base_female.html"}
FAIL_MM = 5.0
RING_PTS = 32
SIDES = ("l", "r")


class LandmarkMissing(Exception):
    pass


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def band(V, axis, lo, hi):
    t = V[:, axis]
    a, b = t.min(), t.max()
    sel = V[(t >= a + lo * (b - a)) & (t <= a + hi * (b - a))]
    if len(sel) == 0:
        raise LandmarkMissing("empty band")
    return sel


# --------------------------------------------------------------------------- bony landmarks (each body's own bones)

class Body:
    def __init__(self, meshes):
        self.m = meshes
        self._c = {}

    def bone(self, name, s=None):
        cands = [f"{name}_{s}", f"zan_{name}_{s}"] if s else []
        cands += [name, f"zan_{name}"]
        for c in cands:
            if c in self.m:
                return self.m[c]["v"]
        raise LandmarkMissing(cands[0])

    def mesh(self, ids):
        vs, fs, o = [], [], 0
        for i in ids:
            if i not in self.m:
                raise LandmarkMissing(i)
            vs.append(self.m[i]["v"]); fs.append(self.m[i]["f"] + o); o += len(self.m[i]["v"])
        return np.vstack(vs), np.vstack(fs)

    # ---- scapula
    def acromion_tip(self, s, sx):
        top = band(self.bone("scapula", s), 1, 0.8, 1.0)
        return top[np.argmax(sx * top[:, 0])]

    def _acromion_lateral(self, s, sx):
        top = band(self.bone("scapula", s), 1, 0.8, 1.0)
        return top[sx * top[:, 0] >= np.percentile(sx * top[:, 0], 70)]

    def acromion_posterior_angle(self, s, sx):
        a = self._acromion_lateral(s, sx)
        return a[np.argmin(a[:, 2])]

    def acromion_anteroinferior_point(self, s, sx):
        a = self._acromion_lateral(s, sx)
        return a[np.argmax(a[:, 2] - (a[:, 1] - a[:, 1].min()))]

    def coracoid_tip(self, s, sx):
        top = band(self.bone("scapula", s), 1, 0.6, 1.0)
        return top[np.argmax(top[:, 2])]

    def scapula_inferior_angle(self, s, sx):
        v = self.bone("scapula", s)
        return v[np.argmin(v[:, 1])]

    def scapula_spine_medial_end(self, s, sx):
        # the root of the spine on the medial border: of the vertices within 15 mm of the medial border, between 55 % and 90 % of
        # the scapula's height, the most posterior one (the spine stands off the posterior surface; the superior angle is above 90 %)
        v = self.bone("scapula", s)
        med = -sx * v[:, 0]
        y0, y1 = v[:, 1].min(), v[:, 1].max()
        c = v[(med >= med.max() - 15) & (v[:, 1] >= y0 + 0.55 * (y1 - y0)) & (v[:, 1] <= y0 + 0.9 * (y1 - y0))]
        if len(c) == 0:
            raise LandmarkMissing("medial border at the spine level")
        return c[np.argmin(c[:, 2])]

    # ---- arm / forearm / hand
    def medial_epicondyle(self, s, sx):
        d = band(self.bone("humerus", s), 1, 0.0, 0.12)
        return d[np.argmax(-sx * d[:, 0])]

    def lateral_epicondyle(self, s, sx):
        d = band(self.bone("humerus", s), 1, 0.0, 0.12)
        return d[np.argmax(sx * d[:, 0])]

    def olecranon(self, s, sx):
        d = band(self.bone("ulna", s), 1, 0.9, 1.0)
        return d[np.argmin(d[:, 2])]

    def radial_styloid(self, s, sx):
        v = self.bone("radius", s)
        return v[np.argmin(v[:, 1])]

    def ulnar_styloid(self, s, sx):
        v = self.bone("ulna", s)
        return v[np.argmin(v[:, 1])]

    def hook_of_hamate(self, s, sx):
        v = self.bone("hamate_bone", s)          # palm faces anterior on these bodies (radius lateral to the ulna)
        return v[np.argmax(v[:, 2])]

    def _ray_head(self, bone, s, ref, head_mm=8.0):
        """(head centre, distal-most point) of a metacarpal / metatarsal: its principal axis, oriented away from `ref`."""
        v = self.bone(bone, s)
        c = v.mean(axis=0)
        u = np.linalg.svd(v - c, full_matrices=False)[2][0]
        if (c - ref) @ u < 0:
            u = -u
        t = (v - c) @ u
        return v[t >= t.max() - head_mm].mean(axis=0), v[np.argmax(t)]

    def _wrist(self, s, sx):
        return 0.5 * (self.lm("radial_styloid", s) + self.lm("ulnar_styloid", s))

    def mc1_head(self, s, sx):
        return self._ray_head("first_metacarpal_bone", s, self._wrist(s, sx))[0]

    def mc2_head(self, s, sx):
        return self._ray_head("second_metacarpal_bone", s, self._wrist(s, sx))[0]

    def mc5_head(self, s, sx):
        return self._ray_head("fifth_metacarpal_bone", s, self._wrist(s, sx))[0]

    def _joint(self, ray, phal, s, ref):
        head, tip = self._ray_head(ray, s, ref)
        p = self.bone(phal, s)
        q = p[cKDTree(p).query(head)[1]]
        return 0.5 * (tip + q)

    def mcp1_joint(self, s, sx):
        return self._joint("first_metacarpal_bone", "proximal_phalanx_of_first_finger_of_hand", s, self._wrist(s, sx))

    # ---- trunk
    def t12_spinous(self, s, sx):
        v = self.bone("vertebra_t12")
        return v[np.argmin(v[:, 2])]

    def l4_spinous(self, s, sx):
        v = self.bone("vertebra_l4")
        return v[np.argmin(v[:, 2])]

    def t12_vertebral_body(self, s, sx):
        v = self.bone("vertebra_t12")
        return v[v[:, 2] > np.median(v[:, 2])].mean(axis=0)

    # ---- pelvis
    def iliac_crest_top(self, s, sx):
        v = self.bone("hip_bone", s)
        return v[np.argmax(v[:, 1])]

    def asis(self, s, sx):
        up = band(self.bone("hip_bone", s), 1, 0.55, 1.0)
        return up[np.argmax(up[:, 2])]

    def pubic_tubercle(self, s, sx):
        # the anterior-most point of the pubis, biased laterally (the tubercle is the lateral end of the pubic crest)
        lo = band(self.bone("hip_bone", s), 1, 0.0, 0.4)
        lat = sx * lo[:, 0] - (sx * lo[:, 0]).min()
        c = lo[lat < 45]
        return c[np.argmax(c[:, 2] + 0.3 * lat[lat < 45])]

    def ischial_tuberosity(self, s, sx):
        v = self.bone("hip_bone", s)
        return v[np.argmin(v[:, 1])]

    # ---- thigh / knee / leg / foot
    def greater_trochanter(self, s, sx):
        p = band(self.bone("femur", s), 1, 0.8, 1.0)
        return p[np.argmax(sx * p[:, 0])]

    def medial_femoral_epicondyle(self, s, sx):
        d = band(self.bone("femur", s), 1, 0.0, 0.12)
        return d[np.argmax(-sx * d[:, 0])]

    def lateral_femoral_epicondyle(self, s, sx):
        d = band(self.bone("femur", s), 1, 0.0, 0.12)
        return d[np.argmax(sx * d[:, 0])]

    def medial_femoral_condyle(self, s, sx):
        d = band(self.bone("femur", s), 1, 0.0, 0.06)
        med = d[-sx * d[:, 0] > np.median(-sx * d[:, 0])]
        return med[np.argmin(med[:, 1])]

    def medial_tibial_condyle(self, s, sx):
        d = band(self.bone("tibia", s), 1, 0.92, 1.0)
        return d[np.argmax(-sx * d[:, 0])]

    def lateral_tibial_condyle(self, s, sx):
        d = band(self.bone("tibia", s), 1, 0.92, 1.0)
        return d[np.argmax(sx * d[:, 0])]

    def patella_base(self, s, sx):
        v = self.bone("patella", s)
        return v[np.argmax(v[:, 1])]

    def fibular_head(self, s, sx):
        v = self.bone("fibula", s)
        return v[np.argmax(v[:, 1])]

    def lateral_malleolus_tip(self, s, sx):
        v = self.bone("fibula", s)
        return v[np.argmin(v[:, 1])]

    def lateral_malleolus_prominence(self, s, sx):
        d = band(self.bone("fibula", s), 1, 0.0, 0.1)
        return d[np.argmax(sx * d[:, 0])]

    def medial_malleolus(self, s, sx):
        d = band(self.bone("tibia", s), 1, 0.0, 0.1)
        return d[np.argmax(-sx * d[:, 0])]

    def calcaneal_tuberosity_superior(self, s, sx):
        c = self.bone("calcaneus", s)
        post = c[c[:, 2] <= c[:, 2].min() + 12]
        return post[np.argmax(post[:, 1])]

    def sole_posteroinferior_mid(self, s, sx):
        # the plantar 8 mm of the calcaneus; its most posterior point; the mid-point across the tuberosity's width there
        c = self.bone("calcaneus", s)
        low = c[c[:, 1] <= c[:, 1].min() + 8]
        p0 = low[np.argmin(low[:, 2])]
        reg = low[np.abs(low[:, 2] - p0[2]) <= 8]
        return np.array([reg[:, 0].mean(), reg[:, 1].min(), reg[:, 2].mean()])

    def mtp1_joint(self, s, sx):
        heel = self.bone("calcaneus", s).mean(axis=0)
        return self._joint("first_metatarsal_bone", "proximal_phalanx_of_first_finger_of_foot", s, heel)

    # ---- soft-tissue points: the proxies written in the data's own definitions (badged "proxy")
    def posterior_axillary_fold(self, s, sx):
        # definition: the most lateral(-inferior) point of the teres major + latissimus dorsi pair at the level of the scapula inferior angle
        V, _ = self.mesh([f"teres_major_{s}", f"latissimus_dorsi_{s}"])
        y0 = self.lm("scapula_inferior_angle", s)[1]
        b = V[np.abs(V[:, 1] - y0) <= 10]
        if len(b) == 0:
            raise LandmarkMissing("teres major / latissimus dorsi at the inferior-angle level")
        return b[np.argmax(sx * b[:, 0])]

    def popliteal_fold(self, s, sx):
        # definition: the posterior point of the femoral intercondylar (knee joint line) level
        m = self.lm("femoral_intercondylar_mid", s)
        f = self.bone("femur", s)
        lev = f[np.abs(f[:, 1] - m[1]) <= 6]
        if len(lev) == 0:
            raise LandmarkMissing("femur at the epicondylar level")
        return np.array([m[0], m[1], lev[:, 2].min()])

    def submalleolar_point(self, s, sx):
        return self.lm("lateral_malleolus_tip", s)      # definition: undefined in the source; proxy = the lateral malleolus tip

    # ---- dispatch
    def lm(self, name, s):
        k = (name, s)
        if k not in self._c:
            spec = LMS[name]
            sx = 1.0 if s == "r" else -1.0
            if spec.get("kind") == "derived":
                a, b = spec["of"]
                self._c[k] = 0.5 * (self.lm(a, s) + self.lm(b, s))
            else:
                f = getattr(self, name, None)
                if f is None:
                    raise LandmarkMissing(f"no finder for {name}")
                self._c[k] = np.asarray(f(s, sx), float)
        return self._c[k]


LMS: dict = {}


# --------------------------------------------------------------------------- muscle ends (muscle_derived landmarks)

def muscle_ends(V):
    """(origin end, insertion end) of a muscle mesh along its principal axis: the mean of its outer 3 % at each end. The end nearer
    the midline is called the origin (pectoral / interosseous fascicles); at 50 %, the only value used, the order does not matter."""
    c = V.mean(axis=0)
    u = np.linalg.svd(V - c, full_matrices=False)[2][0]
    t = (V - c) @ u
    e1, e2 = V[t >= np.percentile(t, 97)].mean(axis=0), V[t <= np.percentile(t, 3)].mean(axis=0)
    return (e1, e2) if abs(e1[0]) <= abs(e2[0]) else (e2, e1)


def components(V, F):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(V)
    r = np.concatenate([F[:, 0], F[:, 1], F[:, 2]]); c = np.concatenate([F[:, 1], F[:, 2], F[:, 0]])
    k, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)), directed=False)
    return k, lab


# --------------------------------------------------------------------------- the section of a mesh by a plane

def section_loops(V, F, p0, n):
    """Polylines where the plane (p0, n) cuts the mesh (closed loops where the mesh is closed)."""
    d = (V - p0) @ n
    d = np.where(np.abs(d) < 1e-7, 1e-7, d)
    fd = d[F]
    cross = (fd.min(axis=1) < 0) & (fd.max(axis=1) > 0)
    if not cross.any():
        return [], float(np.min(np.abs(d)))
    pts, adj = {}, {}

    def ept(i, j):
        k = (i, j) if i < j else (j, i)
        if k not in pts:
            a, b = V[k[0]], V[k[1]]; da, db = d[k[0]], d[k[1]]
            pts[k] = a + (b - a) * (da / (da - db))
        return k

    for tri in F[cross]:
        ks = []
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            if (d[a] < 0) != (d[b] < 0):
                ks.append(ept(int(a), int(b)))
        if len(ks) == 2:
            adj.setdefault(ks[0], []).append(ks[1]); adj.setdefault(ks[1], []).append(ks[0])
    seen, loops = set(), []
    for start in adj:
        if start in seen:
            continue
        chain, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [q for q in adj[cur] if q != prev and q not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur); chain.append(cur)
        if len(chain) >= 3:
            loops.append(np.array([pts[k] for k in chain]))
    return loops, 0.0


def resample(loop, n=RING_PTS):
    closed = np.vstack([loop, loop[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < 1e-6:
        return loop[:1]
    t = np.linspace(0, s[-1], n, endpoint=False)
    return np.stack([np.interp(t, s, closed[:, k]) for k in range(3)], axis=1)


def plane_basis(n):
    e1 = unit(np.cross(n, [0, 0, 1.0]) if abs(n[2]) < 0.9 else np.cross(n, [1.0, 0, 0]))
    return e1, np.cross(n, e1)


def in_poly(P2, poly2):
    x, y = P2[:, 0], P2[:, 1]
    inside = np.zeros(len(P2), bool)
    xs, ys = poly2[:, 0], poly2[:, 1]
    j = len(poly2) - 1
    for i in range(len(poly2)):
        cond = ((ys[i] > y) != (ys[j] > y)) & (x < (xs[j] - xs[i]) * (y - ys[i]) / (ys[j] - ys[i] + 1e-12) + xs[i])
        inside ^= cond
        j = i
    return inside


HINT = {"lateral": (0, +1), "medial": (0, -1), "anterior": (2, +1), "posterior": (2, -1), "superior": (1, +1), "upper": (1, +1),
        "inferior": (1, -1), "lower": (1, -1)}


# heads that the page draws as one structure but that separate in the section: their relative position (textbook anatomy)
HEAD_HINT = {("biceps_brachii", "long_head"): "lateral", ("biceps_brachii", "short_head"): "medial",
             ("biceps_femoris", "long_head"): "posterior", ("biceps_femoris", "short_head"): "anterior"}


def part_hint(muscle, part):
    if (muscle, part) in HEAD_HINT:
        return HEAD_HINT[(muscle, part)]
    for w in (part or "").split("_"):
        if w in HINT:
            return w
    return None


def cut(V, F, p0, n, sx, hint):
    """(rings, dot, note) of the section of (V, F) by the plane (p0, n); rings = all loops, or the hinted one when there are several."""
    loops, miss = section_loops(V, F, p0, n)
    loops = [l for l in loops if len(l) >= 3 and np.linalg.norm(np.diff(np.vstack([l, l[:1]]), axis=0), axis=1).sum() > 2.0]
    if not loops:
        return None, None, "no section"
    note = ""
    if hint and len(loops) > 1:
        ax, sg = HINT[hint]
        sgn = sg * (sx if ax == 0 else 1.0)
        best = max(loops, key=lambda l: sgn * l.mean(axis=0)[ax])
        note = f"{hint} loop of {len(loops)}"
        loops = [best]
    e1, e2 = plane_basis(n)
    allp = np.vstack(loops)
    a, b = (allp - p0) @ e1, (allp - p0) @ e2
    span = max(np.ptp(a), np.ptp(b), 1.0)
    step = max(1.0, span / 40.0)
    ga = np.arange(a.min(), a.max() + step, step); gb = np.arange(b.min(), b.max() + step, step)
    A2, B2 = np.meshgrid(ga, gb, indexing="ij")
    P2 = np.stack([A2.ravel(), B2.ravel()], axis=1)
    keep = np.zeros(len(P2), bool)
    for l in loops:
        keep |= in_poly(P2, np.stack([(l - p0) @ e1, (l - p0) @ e2], axis=1))
    P3 = p0 + np.outer(P2[keep, 0], e1) + np.outer(P2[keep, 1], e2)
    ins = P3[G.inside(P3, V, F)] if len(P3) else P3
    if len(ins):
        c = ins.mean(axis=0)
        dot = ins[np.argmin(np.linalg.norm(ins - c, axis=1))]
    else:
        dot = allp.mean(axis=0)
        note = (note + "; " if note else "") + "no inside sample: dot = outline centroid"
    return [resample(l) for l in loops], dot, note


def snap_inside(V, F, P, reach=FAIL_MM):
    """Nearest point inside the mesh to P (P itself if inside); None if nothing inside within `reach` of the surface point nearest P."""
    if G.inside(P[None], V, F)[0]:
        return P, 0.0
    tree = cKDTree(V)
    dist, i = tree.query(P)
    q = V[i]
    g = np.arange(-4, 4.01, 1.0)
    Gp = q + np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    Gp = Gp[np.argsort(np.linalg.norm(Gp - P, axis=1))]
    ins = G.inside(Gp, V, F)
    if not ins.any():
        return None, float(dist)
    best = Gp[ins][0]
    return best, float(np.linalg.norm(best - P))


# --------------------------------------------------------------------------- placement

def r1(a):
    return [round(float(x), 1) for x in a]


def place_page(page: str, html: Path, data: dict) -> dict:
    meshes = G.load_zan(html)
    body = Body(meshes)
    LMS.clear(); LMS.update(data["landmarks"])
    # frame check: +X right, +Z anterior
    if not (body.bone("humerus", "r")[:, 0].mean() > 0 > body.bone("humerus", "l")[:, 0].mean()):
        raise SystemExit(f"{page}: frame check failed (humerus_r not on +X)")
    lm_out, lm_fail = {}, []
    for name, spec in data["landmarks"].items():
        kind = spec.get("kind")
        if kind == "muscle_derived":
            lm_out[name] = {"kind": kind, "note": "per muscle (its own mesh)"}
            continue
        rec = {"kind": kind, "label": spec.get("label")}
        if kind == "soft_tissue":
            rec["proxy"] = True
            rec["proxy_rule"] = spec.get("definition")
        for s in SIDES:
            try:
                rec[s] = r1(body.lm(name, s))
            except LandmarkMissing as e:
                rec[s] = None
                lm_fail.append(f"{name}_{s}: {e}")
        lm_out[name] = rec
    bands, fails = [], []
    for mk, m in data["muscles"].items():
        structs = m["structures"].get(page) or []
        parts = {p.get("id"): p for p in m.get("parts", [])}
        seen = {}
        for bi, iz in enumerate(m.get("iz", [])):
            ln = data["lines"][iz["line"]]
            for s in SIDES:
                sx = 1.0 if s == "r" else -1.0
                b = {"muscle": mk, "iz": bi, "part": iz["part"], "side": s, "line": iz["line"], "mode": ln["mode"], "pct": iz["pct"]}
                pstruct = (parts.get(iz["part"]) or {}).get("structures")
                ids = [f"{x}_{s}" for x in pstruct] if pstruct else [x for x in structs if x.endswith("_" + s)]
                b["structures"] = ids
                proxies = [k for k in (ln["from"], ln["to"]) if data["landmarks"].get(k, {}).get("kind") == "soft_tissue"]
                if proxies:
                    b["proxy"] = proxies
                try:
                    V, F = body.mesh(ids)
                    note = []
                    if mk == "dorsal_interossei_hand" and iz["part"] == "first_dorsal_interosseous":
                        # one structure for the four dorsal interossei: the first one = the connected piece nearest the MC1-MC2 web
                        k, lab = components(V, F)
                        if k < 2:
                            raise LandmarkMissing("the four dorsal interossei are one connected mesh on this page")
                        web = 0.5 * (body.lm("mc1_head", s) + body.lm("mc2_head", s))
                        dv = np.linalg.norm(V - web, axis=1)
                        keep = lab == lab[np.argmin(dv)]
                        idx = np.flatnonzero(keep); remap = -np.ones(len(V), int); remap[idx] = np.arange(len(idx))
                        F = remap[F[keep[F].all(axis=1)]]; V = V[idx]
                        note.append(f"first dorsal interosseous = the piece of {k} nearest the MC1-MC2 web")
                    if ln["from"] == "muscle_origin_end":
                        A, B = muscle_ends(V)
                    else:
                        A, B = body.lm(ln["from"], s), body.lm(ln["to"], s)
                    L = float(np.linalg.norm(B - A)); u = (B - A) / L
                    b["from_pt"], b["to_pt"], b["line_len_mm"] = r1(A), r1(B), round(L, 1)
                    if iz["pct"] is None:
                        b["status"] = "qualitative"
                        b["note"] = "qualitative site: the line is shown in thirds, no dot"
                        bands.append(b); continue
                    pct = float(np.mean(iz["pct"])) if isinstance(iz["pct"], list) else float(iz["pct"])
                    P = A + pct / 100.0 * (B - A)
                    hint = part_hint(mk, iz["part"])
                    if ln["mode"] == "point":
                        q, dd = snap_inside(V, F, P)
                        if q is None:
                            raise LandmarkMissing(f"no point of the muscle within {FAIL_MM:g} mm of the line point ({dd:.1f} mm to its surface)")
                        b["snap_mm"] = round(dd, 1)
                        if dd > FAIL_MM:
                            raise LandmarkMissing(f"the line point is {dd:.1f} mm from the muscle (> {FAIL_MM:g} mm)")
                        rings, _, n2 = cut(V, F, q, u, sx, None)
                        dot = q
                    else:
                        d = (V - P) @ u
                        if d.min() > 0 or d.max() < 0:
                            miss = float(min(abs(d.min()), abs(d.max())))
                            if miss > FAIL_MM:
                                raise LandmarkMissing(f"the plane misses the muscle by {miss:.1f} mm (> {FAIL_MM:g} mm)")
                            sh = (miss + 0.5) * (1 if d.min() > 0 else -1)
                            P = P + sh * u
                            b["shifted_mm"] = round(sh, 1)
                        rings, dot, n2 = cut(V, F, P, u, sx, hint)
                        if rings is None:
                            raise LandmarkMissing("the plane does not cut a closed section")
                    if n2:
                        note.append(n2)
                    b["status"] = "placed"
                    b["dot"] = r1(dot)
                    b["rings"] = [[r1(p) for p in ring] for ring in (rings or [])]
                    b["level_pct"] = round(float((dot - A) @ u / L * 100.0), 2)
                    b["dot_inside"] = bool(G.inside(dot[None], V, F)[0])
                    if note:
                        b["note"] = "; ".join(note)
                    key = json.dumps([ids, iz["line"], iz["pct"], s, hint])     # same structure, line, level and side = one drawn band
                    if key in seen:
                        b["same_as"] = seen[key]
                    else:
                        seen[key] = bi
                except LandmarkMissing as e:
                    b["status"] = "failed"
                    b["reason"] = str(e)
                    fails.append(f"{mk}[{bi}] {iz['part']} {s}: {e}")
                bands.append(b)
    n_pl = sum(1 for b in bands if b["status"] == "placed")
    return {
        "schema": "nmsk.iz_bands.v1", "round": "Q322", "page": page, "generated": dt.date.today().isoformat(),
        "source_page": str(html.relative_to(REPO)) if html.is_relative_to(REPO) else str(html),
        "frame": "page mm, +X right, +Y superior, +Z anterior",
        "rule": ("RULE-BASED. Landmarks measured on this body's own bones (soft-tissue points: the proxy in their definition, flagged proxy); "
                 "IZ level = pct along the line from its first landmark; band = the muscle's section by the plane perpendicular to the line "
                 "at that level (point lines: the nearest inside point); FAILED when the plane / point misses the muscle by more than 5 mm."),
        "fail_mm": FAIL_MM,
        "landmarks": lm_out, "landmark_failures": lm_fail,
        "counts": {"bands": len(bands), "placed": n_pl, "qualitative": sum(1 for b in bands if b["status"] == "qualitative"),
                   "failed": sum(1 for b in bands if b["status"] == "failed")},
        "failures": fails,
        "bands": bands,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*", default=list(PAGES))
    ap.add_argument("--html", help="page html to measure (one page only); default build/q309/<dir>")
    ap.add_argument("-o", "--out", help="output path (one page only)")
    a = ap.parse_args()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    for p in a.pages:
        html = Path(a.html) if a.html else PAGES[p]
        res = place_page(p, html, data)
        out = Path(a.out) if a.out else Path(str(OUT).format(page=p))
        out.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        c = res["counts"]
        print(f"{p}: landmarks {sum(1 for v in res['landmarks'].values() if v.get('l') is not None or v.get('r') is not None)}"
              f"/{len(res['landmarks'])} (failures {len(res['landmark_failures'])}); bands {c['bands']}: placed {c['placed']}, "
              f"qualitative {c['qualitative']}, failed {c['failed']} -> {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")
        for f in res["landmark_failures"] + res["failures"]:
            print("   ", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
