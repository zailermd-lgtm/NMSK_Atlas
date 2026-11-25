#!/usr/bin/env python3
"""Q394: what must lie under the skin, and where it does not -- the census library (Base · Male / Base · Female).

Owner, 2026-11-25: "make sure that all the structures that should be under the skin ARE under the skin".

    python3 scripts/anatomy/q394/under_skin_q394.py --page-dir DIR [--rig RIG.json] [--states rest,sh_abd,...] [--json OUT]

The test (the Q353 outside_count definition, unchanged; this file only makes it complete and fast):
  skin      every `sys: skin` piece of the page except the nail plates; each skin slab's faces are split into its OUTER sheet,
            INNER sheet and walls by Q353 `Geo.sheets` (computed once on the rest geometry; a face keeps its class in a pose).
  outside   a vertex of a structure is OUTSIDE when, against the closest outer-sheet triangle, it lies on the outer side
            (s_out > 0), against the closest inner-sheet triangle it is not deeper than the inner sheet (s_in < 0), and it lies
            over the skin surface, not beyond the border of a real opening (tangential offset from the closest point < TANG_MAX,
            Q353 `covered`).  Q353 only tested vertices within 12 mm of a skin vertex; here every vertex is tested (a structure
            further out than 12 mm would have been missed), with an exact point-triangle distance over the K nearest triangles.
  the set   every structure of the page that is not skin, minus EXCLUDE (what legitimately lies on or passes through the
            surface: rule + one-line reason each).
  poses     STATES: the page's own rig (data/anatomy/pose_rig_base_{m,f}.json), forward kinematics incl. the spine regions as
            viewer/pose/pose.js fk does them, the rig's blend (dual quaternion) -- the numpy port of scripts/anatomy/q384/
            pose_replica_q384.py (checked against the page by verify_pose_q384.py); skin and structures are posed by the same
            rig, then the same test.
Deterministic; reads only.
"""
from __future__ import annotations

import argparse, json, os, pickle, re, sys, time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for _p in ("q353", "q340", "q384", "q241"):
    if str(HERE.parent / _p) not in sys.path:
        sys.path.insert(0, str(HERE.parent / _p))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

TANG_MAX = 2.0       # mm, Q353 `covered`
K_NEAR, K_FAR, FAR_MM = 24, 6, 15.0
DIRKEY = {"viewer_zan_atlas": "base_m", "viewer_base_female": "base_f"}
SKIN_SKIP = re.compile(r"nail_plate")

# What legitimately lies on / passes through the surface.  (regex on the structure id, reason)
EXCLUDE = [
    (r"(^|_)(eyeball|cornea|sclera|iris|lens|pupil|conjunctiva|bulbar_conj|choroid|retina|vitreous|anterior_chamber|ciliary_body|"
     r"eye_globe|globe|zonular_fibres|zonular|hyaloid|ora_serrata)(_|$)", "eye: its front (cornea / bulbar conjunctiva) is the body surface in the palpebral fissure"),
    (r"(^|_)(tarsal_plate|tarsus|superior_tarsus|inferior_tarsus|palpebral|eyelid|lacrimal_caruncle|caruncle|plica_semilunaris|"
     r"lacrimal_punct)", "eyelid margin / caruncle: the free lid margin and the caruncle are surface"),
    (r"(^|_)(tooth|teeth|incisor|canine|premolar|molar|crown|dental|gingiva|gum)", "teeth crowns and gingiva lie in the open mouth"),
    (r"(^|_)(tongue|lingual_mucosa|oral_mucosa|lip_mucosa|vermilion|palate|uvula|oral_vestibule|oral_cavity|buccal_mucosa)",
     "oral mucosa / tongue: the mouth opening"),
    (r"(^|_)(nasal_vestibule|nostril|naris|nares|nasal_cavity|nasal_mucosa|vibrissae)", "nostrils: the nasal opening"),
    (r"(^|_)(external_acoustic|external_auditory|ear_canal|auditory_canal|tympanic_membrane|auricular_cartilage)",
     "ear canal / auricle cartilage: the ear's skin side and canal open to the surface"),
    (r"(^|_)(glans|prepuce|foreskin|external_urethral|urethral_orifice|navicular_fossa|labia_minora|labium_minus|labium_majus|"
     r"labia_majora|clitoris|clitoral_hood|vestibule_of_vagina|vaginal_vestibule|vaginal_orifice|hymen|vagina\b|vulva|"
     r"anal_canal|anus|anal_verge|rectum_and_anal|perineal_opening|scrotum|penis|penile|corpus_spongiosum|corpora_cavernosa|"
     r"corpus_cavernosum)", "external genitalia / anus / urethral and vaginal orifices: perineal openings and genital surface parts"),
    (r"(^|_)(hair|eyelash|cilia|eyebrow_hair)", "hair (not modelled as structure under skin)"),
    (r"(^|_)nail(_|$)|nail_bed|nail_matrix|lunula|hyponychium|eponychium", "nail apparatus: the nail is surface"),
]
EXCLUDE_RE = [(re.compile(p, re.I), why) for p, why in EXCLUDE]

STATES = {
    "rest": {},
    "sh_abd": {"j": {"shoulder_l": {"abd": 120}, "shoulder_r": {"abd": 120}}},
    "sh_flex": {"j": {"shoulder_l": {"flex": 120}, "shoulder_r": {"flex": 120}}},
    "arm_elbow": {"j": {"shoulder_r": {"abd": 90, "flex": 30}, "elbow_r": {"flex": 120}, "elbow_l": {"flex": 120}}},
    "hipknee": {"j": {"hip_l": {"flex": 90}, "knee_l": {"flex": 90}, "hip_r": {"flex": 90}, "knee_r": {"flex": 90}}},
    "neck_flex_rot": {"r": {"cervical": {"flex": 45, "rot": 40}}},
    "neck_ext_lat": {"r": {"cervical": {"flex": -45, "lat": 30}}},
    "trunk": {"r": {"lumbar": {"flex": 45}, "thoracic": {"flex": 20, "rot": 20}}},
}


def excluded(sid):
    for rx, why in EXCLUDE_RE:
        if rx.search(sid):
            return why
    return None


# ------------------------------------------------------------------ geometry
def closest_on_tris(P, A, B, C):
    """exact closest point of each P[i] on triangle (A[i], B[i], C[i]) (Ericson, Real-Time Collision Detection 5.1.5), vectorised"""
    ab, ac, ap = B - A, C - A, P - A
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    bp = P - B; d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    cp = P - C; d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va = d3 * d6 - d5 * d4; vb = d5 * d2 - d1 * d6; vc = d1 * d4 - d3 * d2
    den = va + vb + vc
    den = np.where(np.abs(den) < 1e-30, 1e-30, den)
    v = vb / den; w = vc / den
    Q = A + ab * v[..., None] + ac * w[..., None]                       # interior
    # edges / vertices (applied from the least to the most specific region, so the right one wins)
    with np.errstate(divide="ignore", invalid="ignore"):
        m = (vc <= 0) & (d1 >= 0) & (d3 <= 0); t = d1 / (d1 - d3); Q = np.where(m[..., None], A + ab * t[..., None], Q)
        m = (vb <= 0) & (d2 >= 0) & (d6 <= 0); t = d2 / (d2 - d6); Q = np.where(m[..., None], A + ac * t[..., None], Q)
        m = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0); t = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        Q = np.where(m[..., None], B + (C - B) * t[..., None], Q)
    Q = np.where(((d1 <= 0) & (d2 <= 0))[..., None], A, Q)
    Q = np.where(((d3 >= 0) & (d4 <= d3))[..., None], B, Q)
    Q = np.where(((d6 >= 0) & (d5 <= d6))[..., None], C, Q)
    return Q


class Sheet:
    """one merged sheet (outer or inner) of the skin: closest triangle by exact distance over the K nearest triangle centroids"""

    def __init__(self, V, F, own):
        self.V, self.F, self.own = V, F, own
        A, B, C = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
        n = np.cross(B - A, C - A); ln = np.linalg.norm(n, axis=1)
        ok = ln > 1e-12
        self.F, self.own = F[ok], own[ok]
        self.N = n[ok] / ln[ok, None]
        self.A, self.B, self.C = A[ok], B[ok], C[ok]
        self.tree = cKDTree((self.A + self.B + self.C) / 3.0)
        self.vtree = cKDTree(V)

    def query(self, P, chunk=20000):
        """-> signed distance along the closest triangle's normal, closest point, triangle index, unsigned distance"""
        n = len(P)
        s = np.zeros(n); q = np.zeros((n, 3)); ti = np.zeros(n, np.int64); dist = np.zeros(n)
        dv, _ = self.vtree.query(P)
        for lo in range(0, n, chunk):
            hi = min(n, lo + chunk); p = P[lo:hi]
            far = dv[lo:hi] > FAR_MM
            for sel, k in ((~far, K_NEAR), (far, K_FAR)):
                ix = np.where(sel)[0]
                if not len(ix):
                    continue
                _, cand = self.tree.query(p[ix], k=k)
                pp = np.repeat(p[ix][:, None, :], k, 1)
                Qc = closest_on_tris(pp, self.A[cand], self.B[cand], self.C[cand])
                d2 = ((pp - Qc) ** 2).sum(-1)
                j = np.argmin(d2, 1); r = np.arange(len(ix))
                t = cand[r, j]; qq = Qc[r, j]
                ti[lo + ix] = t; q[lo + ix] = qq; dist[lo + ix] = np.sqrt(d2[r, j])
                s[lo + ix] = ((p[ix] - qq) * self.N[t]).sum(1)
        return s, q, ti, dist


RAYS = ((0, 1), (0, -1), (1, 1), (1, -1), (2, 1))   # (axis, direction): +x, -x, +y, -y, +z


def _axis_hits(V, F, P, axis, sign, cell=4.0):
    """number of triangles of (V, F) crossed by the ray from each P along +/- the given axis: the triangles are binned by their
    projection on the other two axes (a cell grid), each ray meets only the triangles of its own cell; exact 2-D barycentric test"""
    u, w = [i for i in range(3) if i != axis]
    A, B, C = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    lo = np.floor(np.minimum(np.minimum(A, B), C)[:, [u, w]] / cell).astype(np.int64)
    hi = np.floor(np.maximum(np.maximum(A, B), C)[:, [u, w]] / cell).astype(np.int64)
    base = lo.min(0); lo -= base; hi -= base
    W = int(hi[:, 1].max()) + 2
    nu, nw = hi[:, 0] - lo[:, 0] + 1, hi[:, 1] - lo[:, 1] + 1
    cnt = nu * nw
    tri = np.repeat(np.arange(len(F)), cnt)
    k = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    cu = lo[tri, 0] + k // np.repeat(nw, cnt); cw = lo[tri, 1] + k % np.repeat(nw, cnt)
    key = cu * W + cw
    o = np.argsort(key, kind="stable"); key, tri = key[o], tri[o]
    qc = np.floor(P[:, [u, w]] / cell).astype(np.int64) - base
    ok = (qc >= 0).all(1) & (qc[:, 1] < W - 1)
    qk = qc[:, 0] * W + qc[:, 1]
    s0 = np.searchsorted(key, qk, "left"); s1 = np.searchsorted(key, qk, "right")
    n = np.where(ok, s1 - s0, 0)
    out = np.zeros(len(P), np.int64)
    if n.sum() == 0:
        return out
    qi = np.repeat(np.arange(len(P)), n)
    ti = tri[np.repeat(s0, n) + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))]
    p = P[qi]; a, b, c = A[ti], B[ti], C[ti]
    x, y = p[:, u] + 1.4142e-4, p[:, w] + 1.7321e-4      # a fixed sub-micron offset: a ray never runs exactly through a vertex / edge
    d = (b[:, w] - c[:, w]) * (a[:, u] - c[:, u]) + (c[:, u] - b[:, u]) * (a[:, w] - c[:, w])
    with np.errstate(divide="ignore", invalid="ignore"):
        l1 = ((b[:, w] - c[:, w]) * (x - c[:, u]) + (c[:, u] - b[:, u]) * (y - c[:, w])) / d
        l2 = ((c[:, w] - a[:, w]) * (x - c[:, u]) + (a[:, u] - c[:, u]) * (y - c[:, w])) / d
    l3 = 1 - l1 - l2
    inside = (np.abs(d) > 1e-12) & (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
    z = l1 * a[:, axis] + l2 * b[:, axis] + l3 * c[:, axis]
    hit = inside & ((z - p[:, axis]) * sign > 0)
    np.add.at(out, qi[hit], 1)
    return out


def parity_outside(V, F, P, rays=RAYS, chunk=20000):
    """independent inside / outside test of points P against the skin's OUTER sheet (V, F): a ray to infinity crosses the outer
    sheet an odd number of times from inside the body, an even number from outside (a fold -- the arm beside the chest, two toes
    -- adds two crossings). It needs only that ONE of a slab's two sheets is labelled outer, so it holds where the outer / inner
    labels of a patch are swapped. Seams leak a ray now and then: majority of five axis rays. -> bool (True = outside)"""
    votes = np.zeros(len(P), int)
    for lo in range(0, len(P), chunk):
        p = P[lo:lo + chunk]
        for ax, sg in rays:
            votes[lo:lo + chunk] += (_axis_hits(V, F, p, ax, sg) % 2 == 0)
    return votes >= 3


class Skin:
    def __init__(self, ids, pos, F, cls):
        Vo, Fo, Oo, Fi, Oi, off = [], [], [], [], [], 0
        for i, k in enumerate(ids):
            v, f, c = pos[k], F[k], cls[k]
            Vo.append(v)
            fo, fi = f[c == 1], f[c == -1]
            Fo.append(fo + off); Oo.append(np.full(len(fo), i)); Fi.append(fi + off); Oi.append(np.full(len(fi), i))
            off += len(v)
        V = np.vstack(Vo)
        self.ids = list(ids)
        # single-sheet pieces (the auricle's surfaces, ~no sheet faces): not in the distance test (no outer / inner side), but they
        # close the outer surface for the parity test -- without them the ear is a hole and the tissue under the concha reads outside
        Fp, off = [np.vstack(Fo)], 0
        for k in ids:
            c = cls[k]
            if (c != 0).mean() < 0.2:
                Fp.append(F[k] + off)
            off += len(pos[k])
        self.parity_F = np.vstack(Fp)
        self.outer = Sheet(V, np.vstack(Fo), np.concatenate(Oo))
        self.inner = Sheet(V, np.vstack(Fi), np.concatenate(Oi))

    def test(self, P):
        """-> (outside mask, s_out, s_in, owner skin index of the closest outer triangle, tangential offset, closest outer point)"""
        so, q, t, _ = self.outer.query(P)
        si, _, _, _ = self.inner.query(P)
        tang = np.linalg.norm((P - q) - so[:, None] * self.outer.N[t], axis=1)
        out = (so > 0) & (si < 0) & (tang < TANG_MAX)
        return out, so, si, self.outer.own[t], tang, q

    def confirm(self, P):
        return parity_outside(self.outer.V, self.parity_F, P)


# ------------------------------------------------------------------ page + rig
def sheet_vote(v, f, cls, g, agree=0.8):
    """Q353 `Geo.sheets` decides outer / inner per face from the direction away from the nearest bone vertices, smoothed over
    three rings of neighbours. Where a bone of ANOTHER segment is nearer than the body wall's own (the arm's humerus beside the
    lateral thoracic skin, measured on Base·F: a 1020-face patch of the inner sheet labelled outer, with the outer sheet above
    it labelled inner) that is the wrong way round. Q394 keeps Q353's per-face vote and its sheet / wall split, but decides the
    vote once per connected sheet patch (neighbouring sheet faces whose normals agree within acos(agree)), area-weighted, so a
    local error is outvoted by its own sheet. The new labels are kept for the piece only when they are more consistent with the
    slab than Q353's: across a slab the two sheets alternate, so a sheet face's PARTNER (the face its inward ray hits 0.8..6 mm
    behind it, Q353's own sheet test) must carry the other label. -> (cls, faces changed, partner agreement before, after)"""
    import trimesh
    from scipy import sparse
    from scipy.sparse.csgraph import connected_components
    t = trimesh.Trimesh(v, f, process=False)
    fn, c, ar, adj = t.face_normals, t.triangles_center, t.area_faces, t.face_adjacency
    _, idx = g.itree.query(c, k=24)
    u = c - g.interior[idx].mean(1)
    u /= np.linalg.norm(u, axis=1, keepdims=True) + 1e-12
    dot = (fn * u).sum(1)
    sh = cls != 0
    a_, b_ = adj[:, 0], adj[:, 1]
    e = sh[a_] & sh[b_] & ((fn[a_] * fn[b_]).sum(1) > agree)
    G = sparse.coo_matrix((np.ones(int(e.sum())), (a_[e], b_[e])), shape=(len(f), len(f)))
    _, lab = connected_components(G, directed=False)
    vote = np.bincount(lab, weights=np.where(sh, ar * dot, 0.0), minlength=lab.max() + 1)
    new = np.where(sh, np.where(vote[lab] > 0, 1, -1), 0)
    # partner of each sheet face (first hit of the inward ray, 0.8..6 mm)
    loc, ri, ti = trimesh.ray.ray_triangle.RayMeshIntersector(t).intersects_location(c - fn * 0.02, -fn, multiple_hits=False)
    dd = np.linalg.norm(loc - (c[ri] - fn[ri] * 0.02), axis=1)
    ok = (dd > 0.8) & (dd < 6.0) & sh[ri] & sh[ti]
    ri, ti, w = ri[ok], ti[ok], ar[ri[ok]]

    def agreement(cl):
        return float((w * (cl[ri] == -cl[ti])).sum() / max(w.sum(), 1e-12))
    a0, a1 = agreement(cls), agreement(new)
    if a1 <= a0:
        return cls, 0, a0, a0
    return new, int((new != cls).sum()), a0, a1


class Page:
    def __init__(self, d, rig_path=None, cache_dir=None):
        import conform_skin_q353 as Q
        self.d = Path(d).resolve()
        self.key = DIRKEY[self.d.name]
        self.g = Q.Geo(self.d)
        self.ids = list(self.g.M)
        self.idx = {k: i for i, k in enumerate(self.ids)}
        self.F = self.g.F
        self.V = {k: self.g.cur[k] for k in self.ids}
        self.sys = self.g.sys
        self.name = {k: self.g.M[k].get("name", k) for k in self.ids}
        self.skin_ids = [k for k in self.ids if self.sys[k] == "skin" and not SKIN_SKIP.search(k)]
        self.rig_path = Path(rig_path) if rig_path else REPO / f"data/anatomy/pose_rig_{self.key}.json"
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._cls = None
        self._W = None

    def cls(self):
        if self._cls is None:
            cf = None
            if self.cache_dir:
                import hashlib
                h = hashlib.sha1(b"".join(np.ascontiguousarray(self.V[k]).tobytes() + self.F[k].tobytes() for k in self.skin_ids)).hexdigest()[:16]
                cf = self.cache_dir / f"sheets394_{self.d.name}_{h}.pkl"
                if cf.exists():
                    self._cls = pickle.load(open(cf, "rb"))
                    return self._cls
            self._cls = {k: sheet_vote(self.V[k], self.F[k], self.g.sheets(k)[0], self.g)[0] for k in self.skin_ids}
            if cf:
                cf.parent.mkdir(parents=True, exist_ok=True)
                pickle.dump(self._cls, open(cf, "wb"))
        return self._cls

    def tested(self):
        """the set that must be under the skin, and the excluded structures with their reason"""
        inc, exc = [], {}
        for k in self.ids:
            if self.sys[k] == "skin":
                continue
            why = excluded(k)
            if why:
                exc[k] = why
            else:
                inc.append(k)
        return inc, exc

    # ---- rig
    def rig(self):
        if self._W is None:
            import pose_replica_q384 as PR
            rig, blob = PR.load_rig(self.rig_path)
            if rig["count"] != len(self.ids) or rig["nv"] != [len(self.V[k]) for k in self.ids]:
                raise SystemExit("pose rig out of step with the page (%s)" % self.rig_path)
            S = [dict(idx=i, id=k, v=self.V[k]) for i, k in enumerate(self.ids)]
            self._W = (rig, PR.decode_all(rig, blob, S), PR.blend_of(rig))
        return self._W

    def posed(self, state, ids=None):
        """{id: vertices} in a STATES entry (rest: the page's own vertices)"""
        st = STATES[state] if isinstance(state, str) else state
        if not st:
            return {k: self.V[k] for k in (ids or self.ids)}
        rig, W, blend = self.rig()
        M = fk(rig, st)
        out = {}
        for k in (ids or self.ids):
            o = W[self.idx[k]]; v = self.V[k]
            out[k] = v @ M[o[1]][:3, :3].T + M[o[1]][:3, 3] if o[0] == "rigid" else blend(v, o[1], o[2], M)
        return out


def fk(rig, st):
    """viewer/pose/pose.js fk: joints (q0 unless given) and the spine regions (regional angle x the level's weight)"""
    import pose_replica_q384 as PR
    pose = st.get("j", {})
    reg = st.get("r", {})
    segs = rig["segs"]; byseg = {j["seg"]: j for j in rig["joints"]}; jid = {j["id"]: j for j in rig["joints"]}
    lev = {L["seg"]: (r, k) for r in rig["regions"] for k, L in enumerate(r["levels"])}

    def qof(j):
        return [pose.get(j["id"], {}).get(d["k"], d["q0"]) for d in j["dof"]]
    M = [np.eye(4) for _ in segs]
    for i in range(len(segs)):
        par = segs[i][1]
        if par < 0:
            continue
        if i in lev:
            r, k = lev[i]; c = np.array(r["levels"][k]["c"]); dR = np.eye(3)
            th = reg.get(r["id"], {})
            for d in r["dof"]:
                dR = dR @ PR.rot(d["a"], th.get(d["k"], 0.0) * d["w"][k])
        elif i in byseg:
            j = byseg[i]; c = np.array(j["c"])
            if j.get("driven"):
                d0 = j["dof"][0]; src = jid[d0["drv"]["src"]]; sq = qof(src)
                ang = d0["drv"]["k"] * ((PR.elevation(src, sq) - PR.elevation(src, [x["q0"] for x in src["dof"]])) if src.get("down")
                                         else (sq[0] - src["dof"][0]["q0"]))
                dR = PR.rot(d0["a"], ang)
            else:
                dR = PR.jointR(j, qof(j)) @ PR.jointR(j, [x["q0"] for x in j["dof"]]).T
            if j["ref"] >= 0:
                R = M[j["ref"]][:3, :3] @ dR; pos = M[par][:3, :3] @ c + M[par][:3, 3]
                m = np.eye(4); m[:3, :3] = R; m[:3, 3] = pos - R @ c; M[i] = m
                continue
        else:
            M[i] = M[par].copy()
            continue
        A = np.eye(4); A[:3, :3] = dR; A[:3, 3] = c - dR @ c
        M[i] = M[par] @ A
    return M


# ------------------------------------------------------------------ census
def region_of(skin_id):
    return re.sub(r"^zan_skin_", "", skin_id).replace("_", " ")


def census(page: Page, state="rest", ids=None, pos=None):
    """-> {structure: dict(n, nv, max_mm, p95_mm, region, verts[list], s_out[list])} for structures with vertices outside"""
    inc, _ = page.tested()
    ids = inc if ids is None else ids
    if pos is None:
        pos = page.posed(state, ids=list(ids) + page.skin_ids)
    sk = Skin(page.skin_ids, pos, page.F, page.cls())
    P = np.vstack([pos[k] for k in ids]); own = np.repeat(np.arange(len(ids)), [len(pos[k]) for k in ids])
    off = np.r_[0, np.cumsum([len(pos[k]) for k in ids])]
    out, so, si, sown, tang, _ = sk.test(P)
    cand = np.where(out)[0]
    conf = sk.confirm(P[cand])
    suspect = np.zeros(len(P), bool); suspect[cand[~conf]] = True
    out[cand[~conf]] = False
    res = {}
    for i in np.unique(own[out]):
        m = np.where(out & (own == i))[0]
        k = ids[i]; s = so[m]
        j = m[np.argmax(s)]
        res[k] = dict(n=int(len(m)), nv=int(len(pos[k])), max_mm=round(float(s.max()), 3), p95_mm=round(float(np.percentile(s, 95)), 3),
                      region=region_of(sk.ids[sown[j]]), verts=(m - off[i]).tolist(), s_out=[round(float(x), 4) for x in s])
    res["__suspect__"] = {ids[i]: int((suspect & (own == i)).sum()) for i in np.unique(own[suspect])}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--rig")
    ap.add_argument("--states", default=",".join(STATES))
    ap.add_argument("--json")
    ap.add_argument("--cache")
    a = ap.parse_args(argv)
    pg = Page(a.page_dir, a.rig, a.cache)
    inc, exc = pg.tested()
    rep = dict(page=pg.d.name, tested=len(inc), excluded={k: v for k, v in sorted(exc.items())}, states={})
    for s in a.states.split(","):
        t = time.time()
        c = census(pg, s)
        rep["states"][s] = c
        tot = sum(x["n"] for x in c.values())
        print(f"{pg.d.name} {s}: {len(c)} structures, {tot} vertices outside ({time.time() - t:.0f}s)", flush=True)
        for k, x in sorted(c.items(), key=lambda kv: -kv[1]["max_mm"])[:12]:
            print(f"   {k:55s} {x['n']:5d}  max {x['max_mm']:6.2f}  p95 {x['p95_mm']:6.2f}  {x['region']}")
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=0) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
