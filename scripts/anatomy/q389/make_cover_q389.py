#!/usr/bin/env python3
"""Q389: the optional DISPLAY COVERING ("underwear") of the Base figures -- built from the page's own skin mesh.

    python3 scripts/anatomy/q389/make_cover_q389.py --inject DIR...   # compute it from each page dir's geometry and put it into the page html
    python3 scripts/anatomy/q389/make_cover_q389.py --check DIR...    # compute and report, change nothing
    python3 scripts/anatomy/q389/make_cover_q389.py --preview OUT.png DIR   # an offline picture (front / back / side / below), no browser

Owner, 2026-11-22: "allow the figures to wear underwear by choice" (to show results to children).

WHAT IT IS.  A covering drawn over the skin, NOT an anatomical structure and not from any scan or atlas source.  Nothing is
sculpted: every vertex of it is a fixed function of the page's real skin mesh --
  shell   the OUTER sheet of the skin's own triangles inside a band (the skin pieces are closed slabs: outer sheet, inner
          sheet, side wall), cut at the band's edges, each vertex lifted along the skin's normal by a small height.  The
          height is the least that keeps the sheet taut (a membrane relaxed along the normals, never below H0, never above
          HMAX), which is what bridges the gluteal cleft and the small creases the way cloth does.  A vertex is stored as
          a point of ONE skin triangle (three vertex indices, two weights) plus its height, so at run time it is recomputed
          from the posed skin vertices and normals: it follows the pose with the skin's own weights, by construction.
  pouch   over the external genital skin pieces a second layer lies on the shell: the rounded convex hull of those pieces'
          own vertices (lifted a little), so that their shape does not read through, kept where it lies outside the body
          and running up into a front panel on the lower abdomen.  The pelvis is the root of the pose rig and does not
          move, so the pouch is stored as fixed points; the shell under it follows the skin like everywhere else, so in a
          pose in which the skin there leaves the pouch it is still covered.
  rim     the band's edges: a slightly raised strip and a wall down to the skin.
The band limits come from the body's own hip bones and genital skin pieces (see `briefs_band` / `top_band`); they are a
display convention of this viewer.  Briefs on both bodies; on Base Female a band top as well (over the mammary region).

The page block (between the NMSK-COVER markers of the Z template):
  {"schema":"nmsk.cover.v1", "src":[[mesh index, id, vertex count]...], "garments":{key:{"label", "nb", "nf", "bind":b64(deflate(u16 x 7 per
   bound vertex: src k, a, b, c, wa, wb, h/0.01 mm)), "nf", "fix":b64(deflate(f32 x 6 per pouch vertex: position, normal)),
   "body" / "rim":b64(deflate(u16 triangles))}}, "stats":{...}}
Run by scripts/regen_template_only.py for the Base pages.  Deterministic: the same page geometry gives the same block.
"""
from __future__ import annotations

import base64
import json
import re
import sys
import zlib
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import ConvexHull, cKDTree

BEGIN, END = "<!-- NMSK-COVER begin -->", "<!-- NMSK-COVER end -->"
MAN_RE = re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M)
FILES_RE = re.compile(r"window\.__ANATOMY_BIN_FILES__\s*=\s*")

# skin pieces that are never part of a garment band (the upper limb hangs beside the pelvis and the chest)
LIMB = re.compile(r"\b(arm|forearm|elbow|cubital|wrist|hand|palm|digits|nail|perionyx|axill\w*|deltoid|deltopectoral|bicipital|radial foveola)\b", re.I)
GENITAL = re.compile(r"urogenital|vulva|perineal and labial", re.I)
MAMMARY = re.compile(r"^mammary region", re.I)

H0 = 2.5          # mm: the least height of the covering above the skin
HMAX = 16.0       # mm: the most the taut sheet may stand off (bridging a cleft)
RIM_W = 14.0      # mm: width of the raised edge strip
RIM_UP = 1.0      # mm: how much the strip stands above the rest
POUCH_H = 3.5     # mm: the pouch's height above the hull of the genital skin
PANEL_X = 75.0    # mm: half width of the front panel the pouch blends into
PANEL_UP = 70.0   # mm: how far above the genital pieces the panel starts
SNAP = 1.6        # mm: open borders of two pieces closer than this are one seam (the engine closes them at 1.5)
CONF = 2.0        # mm: a face whose normal step changes the distance to the inner anatomy by more than this is decided
SMOOTH = 0.5      # cos of the angle up to which a face continues its neighbour's sheet
THICK = 6.0       # mm: the other sheet of a skin slab lies within this (the slabs are ~1.5-4 mm thick)
PANEL_EDGE = 12.0 # mm: the panel's straight top / side edges lie this far inside its outermost points
PANEL_LIFT = 1.5  # mm: the front panel stands this much above the shell under it (a clean edge instead of two surfaces in one place)
WELD = 0.05       # mm: vertices of two pieces closer than this are one point of the surface (the engine welds at 0.03)


# ------------------------------------------------------------------ page geometry
def load_page(html: Path):
    s = html.read_text(encoding="utf-8")
    m = MAN_RE.search(s)
    if not m:
        return None
    man = json.loads(m.group(1))
    fm = FILES_RE.search(s)
    files, _ = json.JSONDecoder().raw_decode(s, fm.end())
    parts = []
    for f in files:
        raw = (html.parent / f["path"]).read_bytes()
        b = base64.b64decode(raw.strip()) if f.get("enc") == "base64" else raw
        assert len(b) == f["bytes"], f["path"]
        parts.append(b)
    return man, b"".join(parts)


def mesh(man, binb, i):
    """positions exactly as the engine decodes them (float32), and the triangles"""
    r = man["meshes"][i]
    q = np.frombuffer(binb, dtype="<u2", count=r["vc"] * 3, offset=r["vo"]).reshape(-1, 3).astype(np.float64)
    pos = np.asarray(r["min"], float) + q / 65535.0 * np.asarray(r["span"], float)
    idx = np.frombuffer(binb, dtype="<u2", count=r["ic"] * 3, offset=r["io"]).reshape(-1, 3).astype(np.int64)
    return pos.astype(np.float32).astype(np.float64), idx


def face_normals(p, f):
    n = np.cross(p[f[:, 1]] - p[f[:, 0]], p[f[:, 2]] - p[f[:, 0]])
    return n, np.linalg.norm(n, axis=1)


def vertex_normals(p, f, nv=None):
    n, _ = face_normals(p, f)
    vn = np.zeros((len(p) if nv is None else nv, 3))
    for k in range(3):
        np.add.at(vn, f[:, k], n)
    return vn / np.maximum(np.linalg.norm(vn, axis=1), 1e-12)[:, None]


def face_pairs(f, nv):
    """the pairs of faces that share an edge"""
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    e.sort(axis=1)
    fid = np.tile(np.arange(len(f)), 3)
    key = e[:, 0] * (nv + 1) + e[:, 1]
    o = np.argsort(key, kind="stable")
    key, fid = key[o], fid[o]
    same = key[1:] == key[:-1]
    return fid[:-1][same], fid[1:][same]


def face_components(f, nv, keep=None):
    a, b = face_pairs(f, nv)
    if keep is not None:
        k = keep(a, b)
        a, b = a[k], b[k]
    A = coo_matrix((np.ones(len(a)), (a, b)), shape=(len(f), len(f)))
    return connected_components(A, directed=False)[1]


def sheet_faces(p, f, u, tmax=THICK):
    """Which faces of a closed skin slab belong to one of its two SHEETS rather than to the side wall: a sheet face has the
    other sheet right behind it -- a ray from its centre against its normal meets a face of the same piece within tmax, and
    that face looks the other way.  A wall face looks along the slab, where there is nothing that near."""
    c = p[f].mean(1)
    k = min(24, len(f) - 1)
    if k < 1:
        return np.zeros(len(f), bool)
    _, nb = cKDTree(c).query(c - u * (tmax / 2), k=k + 1)
    hit = np.zeros(len(f), bool)
    me = np.arange(len(f))
    for q in range(k + 1):
        j = nb[:, q]
        a, e1, e2 = p[f[j, 0]], p[f[j, 1]] - p[f[j, 0]], p[f[j, 2]] - p[f[j, 0]]
        d = -u
        pv = np.cross(d, e2)
        det = (e1 * pv).sum(1)
        ok = np.abs(det) > 1e-12
        inv = 1.0 / np.where(ok, det, 1.0)
        tv = c - a
        bu = (tv * pv).sum(1) * inv
        qv = np.cross(tv, e1)
        bv = (d * qv).sum(1) * inv
        t = (e2 * qv).sum(1) * inv
        hit |= ok & (j != me) & (bu >= -0.02) & (bv >= -0.02) & (bu + bv <= 1.02) & (t > 0.2) & (t < tmax) & ((u[j] * u).sum(1) < -0.5)
    return hit


def outer_faces(p, f, inner_tree):
    """Which faces of a closed skin slab are its OUTER sheet (the slab: outer sheet, inner sheet, and a side wall).  First the
    wall is set aside (sheet_faces).  A sheet face's score: how much farther from the anatomy under the skin (the nearest
    vertex of any non-skin structure) a step along its normal ends than a step against it -- positive on the outer sheet,
    negative on the inner one.  The sheet faces fall into smooth patches; a patch whose decided faces (|score| > CONF)
    agree takes that label as a whole, which carries the label through places where the score alone is wrong (under the
    arm, where the other limb's anatomy is the nearer one).  In a patch that is mixed each face is decided by its own
    score, an undecided face taking the label of the decided faces it continues (cos > SMOOTH)."""
    n, ln = face_normals(p, f)
    u = n / np.maximum(ln, 1e-12)[:, None]
    c = p[f].mean(1)
    s = inner_tree.query(c + 4.0 * u)[0] - inner_tree.query(c - 4.0 * u)[0]
    area = ln / 2
    sheet = sheet_faces(p, f, u)
    comp = face_components(f, len(p), lambda a, b: sheet[a] & sheet[b] & ((u[a] * u[b]).sum(1) > 0.35))
    nc = comp.max() + 1
    a_pos = np.bincount(comp, weights=area * (s > CONF), minlength=nc)
    a_neg = np.bincount(comp, weights=area * (s < -CONF), minlength=nc)
    whole = np.where(a_pos + a_neg <= 0, 0, np.where(a_pos >= 4 * a_neg, 1, np.where(a_neg >= 4 * a_pos, -1, 2)))   # 2: mixed
    lab = np.where(sheet, whole[comp], 0)
    mixed = lab == 2
    lab = np.where(mixed, np.where(s > CONF, 1, np.where(s < -CONF, -1, 0)), lab)
    a, b = face_pairs(f, len(p))
    k = ((u[a] * u[b]).sum(1) > SMOOTH) & mixed[a] & mixed[b]
    a, b = a[k], b[k]
    for _ in range(40):
        vote = np.zeros(len(f))
        np.add.at(vote, a, lab[b])
        np.add.at(vote, b, lab[a])
        new = np.where((lab == 0) & mixed & (vote != 0), np.sign(vote), lab).astype(int)
        if (new == lab).all():
            break
        lab = new
    # a face the ray test missed (at a border the ray can leave through the wall): it continues an outer face smoothly
    # (cos > 0.8; the wall stands across the sheet) and either all three of its vertices are already vertices of the outer
    # sheet and its score does not say inner, or its score says outer clearly
    out = lab == 1
    a, b = face_pairs(f, len(p))
    k = (u[a] * u[b]).sum(1) > 0.8
    a, b = a[k], b[k]
    for _ in range(3):
        on = np.zeros(len(p), bool)
        on[f[out].ravel()] = True
        nb = np.zeros(len(f), bool)
        nb[a[out[b]]] = True
        nb[b[out[a]]] = True
        add = ~out & (lab == 0) & nb & ((on[f].all(1) & (s > -0.5)) | (s > CONF))      # ... or its own score says outer clearly
        if not add.any():
            break
        out |= add
    return out, s


# ------------------------------------------------------------------ the welded outer sheet of a set of pieces
class Sheet:
    """the outer sheet of several skin pieces as ONE surface: welded vertex ids, each with a representative (piece k, vertex)"""

    def __init__(self, man, binb, ids, inner_tree):
        self.ids = list(ids)
        P, F, K, V = [], [], [], []
        base = 0
        self.raw = {}
        for k, i in enumerate(self.ids):
            p, f = mesh(man, binb, i)
            self.raw[i] = (p, f)
            out, _ = outer_faces(p, f, inner_tree)
            P.append(p)
            K.append(np.full(len(p), k))
            V.append(np.arange(len(p)))
            F.append(np.column_stack([f[out] + base, np.full(out.sum(), k), np.where(out)[0]]))
            base += len(p)
        P, K, V, F = np.concatenate(P), np.concatenate(K), np.concatenate(V), np.concatenate(F)
        used = np.zeros(len(P), bool)
        used[F[:, :3].ravel()] = True
        # weld: (1) coincident vertices; (2) as the engine does at load (its crack closing, SNAP), the open-border vertices of
        # two DIFFERENT pieces that lie within SNAP of each other -- the rebuilt regions do not share their borders exactly
        ui = np.where(used)[0]
        T = cKDTree(P[ui])
        pairs = T.query_pairs(WELD, output_type="ndarray")
        border = np.zeros(len(P), bool)
        border[np.unique(boundary_edges(F[:, :3]))] = True
        wide = T.query_pairs(SNAP, output_type="ndarray")
        if len(wide):
            a, b = ui[wide[:, 0]], ui[wide[:, 1]]
            wide = wide[border[a] & border[b] & (K[a] != K[b])]
            pairs = np.concatenate([pairs, wide]) if len(pairs) else wide
        if len(pairs):
            A = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(ui), len(ui)))
            par = connected_components(A, directed=False)[1]
        else:
            par = np.arange(len(ui))
        _, first, inv = np.unique(par, return_index=True, return_inverse=True)
        g_of = np.full(len(P), -1)
        g_of[ui] = inv
        rep = ui[first]
        self.pos = P[rep]                       # welded vertex positions
        self.rep_k, self.rep_v = K[rep], V[rep]  # representative skin vertex of each welded vertex
        self.tri = g_of[F[:, :3]]               # triangles over welded ids
        self.tri_k = F[:, 3]                    # piece (index into ids) each triangle came from
        self.tri_f = F[:, 4]                    # its face index in that piece
        self.tri_local = F[:, :3] - np.concatenate([[0], np.cumsum([len(self.raw[i][0]) for i in self.ids])])[self.tri_k][:, None]
        ok = (self.tri[:, 0] != self.tri[:, 1]) & (self.tri[:, 1] != self.tri[:, 2]) & (self.tri[:, 0] != self.tri[:, 2])
        for a in ("tri", "tri_k", "tri_f", "tri_local"):
            setattr(self, a, getattr(self, a)[ok])
        self.nrm = vertex_normals(self.pos, self.tri)

    def keep_component(self, seed_pt):
        lab = face_components(self.tri, len(self.pos))
        d = np.linalg.norm(self.pos[self.tri].mean(1) - seed_pt, axis=1)
        k = lab == lab[np.argmin(d)]
        for a in ("tri", "tri_k", "tri_f", "tri_local"):
            setattr(self, a, getattr(self, a)[k])
        return int(k.sum()), int((~k).sum())


def boundary_edges(tri):
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    es = np.sort(e, axis=1)
    _, inv, cnt = np.unique(es, axis=0, return_inverse=True, return_counts=True)
    return e[cnt[inv.ravel()] == 1]


# ------------------------------------------------------------------ cutting triangles at a level of a scalar field
class Soup:
    """cover vertices as points of skin triangles: (sheet triangle t, barycentric w[3]); deduplicated by position"""

    def __init__(self, sheet: Sheet):
        self.S = sheet
        self.t, self.w, self.key = [], [], {}

    def add(self, t, w):
        p = (self.S.pos[self.S.tri[t]] * np.asarray(w)[:, None]).sum(0)
        k = tuple(np.round(p / 0.01).astype(np.int64))
        i = self.key.get(k)
        if i is None:
            i = self.key[k] = len(self.t)
            self.t.append(t)
            self.w.append(tuple(w))
        return i


def clip(S: Sheet, tris_w, field_v, level, keep_above=True):
    """tris_w: list of (t, W) with W a 3x3 array of barycentric rows (a sub-triangle of sheet triangle t).  Returns the parts
    with field >= level (or <= when keep_above is False), as the same kind of list."""
    out = []
    for t, W in tris_w:
        fv = W @ field_v[S.tri[t]] - level
        if not keep_above:
            fv = -fv
        ins = fv >= 0
        n = int(ins.sum())
        if n == 3:
            out.append((t, W))
        elif n == 0:
            continue
        else:
            # walk the polygon
            poly = []
            for a in range(3):
                b = (a + 1) % 3
                if ins[a]:
                    poly.append(W[a])
                if ins[a] != ins[b]:
                    s = fv[a] / (fv[a] - fv[b])
                    poly.append(W[a] * (1 - s) + W[b] * s)
            for q in range(1, len(poly) - 1):
                out.append((t, np.array([poly[0], poly[q], poly[q + 1]])))
    return out


# ------------------------------------------------------------------ the taut sheet
def relax(pos0, nrm, tri, h_min, h_max, pin=None, it=60):
    """heights h >= h_min along the normals such that the lifted sheet is as taut as the bounds allow (a membrane held up by
    the skin under it).  pin: vertices that keep h_min (the garment's edges lie on the body)."""
    n = len(pos0)
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    e = np.unique(np.sort(e, axis=1), axis=0)
    A = coo_matrix((np.ones(len(e) * 2), (np.concatenate([e[:, 0], e[:, 1]]), np.concatenate([e[:, 1], e[:, 0]]))), shape=(n, n)).tocsr()
    deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
    h = np.full(n, float(h_min)) if np.isscalar(h_min) else h_min.astype(float).copy()
    lo = h.copy()
    for _ in range(it):
        p = pos0 + nrm * h[:, None]
        tgt = (A @ p) / deg[:, None]
        h = np.clip(((tgt - pos0) * nrm).sum(1), lo, h_max)
        if pin is not None:
            h[pin] = lo[pin]
    return h


# ------------------------------------------------------------------ the pouch
def pouch(points, keep_fn, n_lat=20, n_lon=36):
    """the rounded convex hull of `points`, sampled as a grid about its centre; keep_fn(q) -> bool mask says which grid points
    lie outside the body.  Returns positions and triangles (their normals point outward)."""
    hull = ConvexHull(points)
    c = points[hull.vertices].mean(0)
    eq = hull.equations                                  # n.x + d <= 0 inside
    th = (np.arange(n_lat) + 0.5) / n_lat * np.pi
    ph = np.arange(n_lon) / n_lon * 2 * np.pi
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    U = np.stack([np.sin(TH) * np.cos(PH), np.cos(TH), np.sin(TH) * np.sin(PH)], -1).reshape(-1, 3)
    den = U @ eq[:, :3].T
    num = -(eq[:, :3] @ c + eq[:, 3])
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(den > 1e-9, num[None, :] / den, np.inf)
    r = t.min(1).reshape(n_lat, n_lon)
    # round the hull's edges: smooth the radius over the grid, never below the hull itself
    r0 = r.copy()
    for _ in range(6):
        rs = (np.roll(r, 1, 1) + np.roll(r, -1, 1) + np.vstack([r[:1], r[:-1]]) + np.vstack([r[1:], r[-1:]]) + 2 * r) / 6
        r = np.maximum(rs, r0)
    P = c + U * r.reshape(-1, 1)
    idx = np.arange(n_lat * n_lon).reshape(n_lat, n_lon)
    a, b = idx[:-1, :], idx[1:, :]
    a2, b2 = np.roll(a, -1, 1), np.roll(b, -1, 1)
    tri = np.concatenate([np.stack([a, b, a2], -1).reshape(-1, 3), np.stack([a2, b, b2], -1).reshape(-1, 3)])
    top, bot = len(P), len(P) + 1
    P = np.vstack([P, c + [0, r[0].mean(), 0], c - [0, r[-1].mean(), 0]])
    tri = np.concatenate([tri, np.stack([np.full(n_lon, top), idx[0], np.roll(idx[0], -1)], -1), np.stack([np.full(n_lon, bot), np.roll(idx[-1], -1), idx[-1]], -1)])
    nrm = vertex_normals(P, tri)
    if ((P - c) * nrm).sum() < 0:
        tri = tri[:, ::-1]
    keep = keep_fn(P)
    tri = tri[keep[tri].any(1)]
    used = np.unique(tri)
    re_ = np.full(len(P), -1)
    re_[used] = np.arange(len(used))
    return P[used], re_[tri]


def clip_mesh(P, tri, fv):
    """the part of a triangle mesh where the per-vertex field fv >= 0 (new vertices on the cut edges)"""
    P = [np.asarray(x, float) for x in P]
    fv = list(fv)
    made = {}

    def cut(a, b):
        k = (a, b) if a < b else (b, a)
        if k not in made:
            t = fv[a] / (fv[a] - fv[b])
            made[k] = len(P)
            P.append(P[a] * (1 - t) + P[b] * t)
            fv.append(0.0)
        return made[k]

    out = []
    for t in tri:
        ins = [fv[i] >= 0 for i in t]
        if all(ins):
            out.append(list(t))
        elif any(ins):
            poly = []
            for q in range(3):
                a, b = int(t[q]), int(t[(q + 1) % 3])
                if ins[q]:
                    poly.append(a)
                if ins[q] != ins[(q + 1) % 3]:
                    poly.append(cut(a, b))
            for q in range(1, len(poly) - 1):
                out.append([poly[0], poly[q], poly[q + 1]])
    out = np.array(out, dtype=np.int64).reshape(-1, 3)
    used = np.unique(out)
    re_ = np.full(len(P), -1)
    re_[used] = np.arange(len(used))
    return np.array(P)[used], re_[out]


# ------------------------------------------------------------------ garments
def page_context(man, binb):
    M = man["meshes"]
    ctx = {"man": man, "bin": binb, "M": M}
    ctx["skin"] = [i for i, r in enumerate(M) if r.get("sys") == "skin"]
    hip = [i for i, r in enumerate(M) if r.get("sys") == "bone" and re.match(r"hip bone", r["name"], re.I)]
    if len(hip) < 2:
        raise SystemExit("cover: the page has no hip bones to take the band from")
    hp = np.concatenate([mesh(man, binb, i)[0] for i in hip])
    ctx["crest"], ctx["isch"] = float(hp[:, 1].max()), float(hp[:, 1].min())
    return ctx


def inner_tree(ctx, ylo, yhi):
    man, binb, M = ctx["man"], ctx["bin"], ctx["M"]
    pts = []
    for i, r in enumerate(M):
        if r.get("sys") in ("skin", "fat", "fascia"):
            continue
        lo, hi = r["min"][1], r["min"][1] + r["span"][1]
        if hi < ylo - 80 or lo > yhi + 80:
            continue
        p = mesh(man, binb, i)[0]
        pts.append(p[(p[:, 1] > ylo - 80) & (p[:, 1] < yhi + 80)])
    return cKDTree(np.concatenate(pts))


def pieces_in(ctx, ylo, yhi, exclude):
    out = []
    for i in ctx["skin"]:
        r = ctx["M"][i]
        if exclude(r["name"]):
            continue
        lo, hi = r["min"][1], r["min"][1] + r["span"][1]
        if hi > ylo and lo < yhi:
            out.append(i)
    return out


def build_garment(ctx, sheet: Sheet, field, pin_edges=True):
    """the shell part of a garment: sheet triangles cut at field = 0, rim strip where field < RIM_W, relaxed heights, edge wall.
    Returns dict with bound vertices and triangle lists (indices into the bound vertices)."""
    S = sheet
    fv = field(S.pos)
    tw = [(t, np.eye(3)) for t in np.where((fv[S.tri] > 0).any(1))[0]]
    inside = clip(S, tw, fv, 0.0, True)
    body = clip(S, inside, fv, RIM_W, True)
    rim = clip(S, inside, fv, RIM_W, False)
    soup = Soup(S)
    T = {"body": [], "rim": []}
    for name, lst in (("body", body), ("rim", rim)):
        for t, W in lst:
            i = [soup.add(t, W[q]) for q in range(3)]
            if len(set(i)) == 3:
                T[name].append(i)
    T = {k: np.array(v, dtype=np.int64).reshape(-1, 3) for k, v in T.items()}
    st = np.array(soup.t)
    sw = np.array(soup.w)
    pos0 = (S.pos[S.tri[st]] * sw[:, :, None]).sum(1)
    nrm = (S.nrm[S.tri[st]] * sw[:, :, None]).sum(1)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)[:, None]
    f0 = (fv[S.tri[st]] * sw).sum(1)
    alltri = np.concatenate([T["body"], T["rim"]])
    edge = np.abs(f0) < 1e-6
    lo = np.where(f0 < RIM_W + 1e-6, H0 + RIM_UP, H0)
    h = relax(pos0, nrm, alltri, lo, HMAX, pin=np.where(edge)[0] if pin_edges else None)
    # the edge wall: from each boundary edge on the field's zero line down to the skin
    be = boundary_edges(alltri)
    on0 = edge[be[:, 0]] & edge[be[:, 1]]
    wall_e = be[on0]
    holes = be[~on0]
    return {"t": st, "w": sw, "h": h, "pos0": pos0, "nrm": nrm, "tri": T, "wall": wall_e, "open": holes, "f0": f0,
            "gaps": true_gaps(pos0, alltri, holes)}


def pt_tri_dist(q, a, b, c):
    """distance from point q to each triangle (a[i], b[i], c[i])"""
    ab, ac, aq = b - a, c - a, q - a
    d1, d2 = (ab * aq).sum(1), (ac * aq).sum(1)
    d00, d01, d11 = (ab * ab).sum(1), (ab * ac).sum(1), (ac * ac).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-18)
    v = np.clip((d11 * d1 - d01 * d2) / den, 0, 1)
    w = np.clip((d00 * d2 - d01 * d1) / den, 0, 1)
    over = v + w > 1
    sc = np.where(over, 1 / np.maximum(v + w, 1e-12), 1.0)
    v, w = v * sc, w * sc
    best = np.linalg.norm(aq - ab * v[:, None] - ac * w[:, None], axis=1)
    for p0, p1 in ((a, b), (b, c), (c, a)):               # the clamped projection is not always the nearest point: check the edges too
        e = p1 - p0
        t = np.clip(((q - p0) * e).sum(1) / np.maximum((e * e).sum(1), 1e-18), 0, 1)
        best = np.minimum(best, np.linalg.norm(q - p0 - e * t[:, None], axis=1))
    return best


def true_gaps(pos, tri, open_edges, tol=1.2):
    """Open edges of the cut sheet that are a real gap: no other triangle of the sheet (one that does not use either end of the
    edge) passes within tol of the edge's midpoint.  A seam between two pieces that the weld did not join (a vertex of one
    piece on an edge of the other) is an open edge too, but its neighbour lies on it; next to a left-out piece (the
    genital pieces under the pouch, the arm at the top's armhole) the gap is meant."""
    if not len(open_edges):
        return np.zeros((0, 3))
    cen = pos[tri].mean(1)
    T = cKDTree(cen)
    rad = float(np.linalg.norm(pos[tri] - cen[:, None], axis=2).max()) + tol
    out = []
    for a, b in open_edges:
        m = (pos[a] + pos[b]) / 2
        cand = np.array(T.query_ball_point(m, rad), dtype=np.int64)
        cand = cand[~((tri[cand] == a) | (tri[cand] == b)).any(1)]
        if not len(cand) or pt_tri_dist(m, pos[tri[cand, 0]], pos[tri[cand, 1]], pos[tri[cand, 2]]).min() > tol:
            out.append(m)
    return np.array(out).reshape(-1, 3)


def briefs(ctx):
    man, binb, M = ctx["man"], ctx["bin"], ctx["M"]
    gen = [i for i in ctx["skin"] if GENITAL.search(M[i]["name"])]
    if not gen:
        raise SystemExit("cover: no genital skin piece on this page")
    gp = np.concatenate([mesh(man, binb, i)[0] for i in gen])
    y_top = ctx["crest"] - 30.0
    y_hem = min(float(gp[:, 1].min()) - 12.0, ctx["isch"] - 55.0)
    ids = pieces_in(ctx, y_hem - 5, y_top + 5, lambda n: bool(LIMB.search(n)))      # the genital pieces too: the shell is one sheet, the pouch goes over it
    tree = inner_tree(ctx, y_hem, y_top)
    S = Sheet(man, binb, ids, tree)
    seed = np.array([0.0, (ctx["crest"] + ctx["isch"]) / 2, S.pos[:, 2].max()])
    kept, dropped = S.keep_component(seed)
    g = build_garment(ctx, S, lambda p: np.minimum(y_top - p[:, 1], p[:, 1] - y_hem))
    # the pouch over the genital pieces: outside the body = on the outer side of the nearest shell vertex
    used = np.unique(S.tri)
    T2 = cKDTree(S.pos[used])

    def outside(q):
        d, j = T2.query(q)
        v = used[j]
        return ((q - S.pos[v]) * S.nrm[v]).sum(1) > -8.0

    # the pouch, over the shell: the hull of the genital skin lifted along its own normals, and of the lifted shell just above it (lower
    # abdomen), so that the covering runs from the abdomen over the genital pieces as one gentle slope instead of a separate
    # bulge.  The panel stands a little above the shell under it, which gives it a clean edge.
    lift = g["pos0"] + g["nrm"] * g["h"][:, None]
    gtop, zmid = float(gp[:, 1].max()), float(np.median(S.pos[used][:, 2]))
    panel = (np.abs(lift[:, 0]) <= PANEL_X) & (lift[:, 2] > zmid) & (lift[:, 1] > gtop - 10.0) & (lift[:, 1] < gtop + PANEL_UP)
    gl = np.concatenate([p_ + vertex_normals(p_, f_) * POUCH_H for p_, f_ in (mesh(man, binb, i) for i in gen)])
    pp, pt = pouch(np.vstack([gp, gl, lift[panel] + g["nrm"][panel] * PANEL_LIFT]), outside)
    # the panel's top and side edges: straight, a little inside the outermost panel points (where the hull would otherwise
    # dip under the shell along a ragged line)
    pp, pt = clip_mesh(pp, pt, np.minimum(gtop + PANEL_UP - PANEL_EDGE - pp[:, 1], PANEL_X - PANEL_EDGE - np.abs(pp[:, 0])))
    pn = vertex_normals(pp, pt)
    g.update({"fix_pos": pp, "fix_nrm": pn, "fix_tri": pt, "sheet": S, "band": [y_hem, y_top], "left_out": [], "dropped": dropped})
    return g


def top(ctx):
    man, binb, M = ctx["man"], ctx["bin"], ctx["M"]
    mam = [i for i in ctx["skin"] if MAMMARY.search(M[i]["name"])]
    if not mam:
        return None
    mp = np.concatenate([mesh(man, binb, i)[0] for i in mam])
    y_lo, y_hi = float(mp[:, 1].min()) - 22.0, float(mp[:, 1].max()) + 6.0
    ids = pieces_in(ctx, y_lo - 5, y_hi + 5, lambda n: bool(LIMB.search(n)))
    tree = inner_tree(ctx, y_lo, y_hi)
    S = Sheet(man, binb, ids, tree)
    seed = np.array([0.0, (y_lo + y_hi) / 2, S.pos[:, 2].max()])
    kept, dropped = S.keep_component(seed)
    g = build_garment(ctx, S, lambda p: np.minimum(y_hi - p[:, 1], p[:, 1] - y_lo))
    limb = [i for i in ctx["skin"] if LIMB.search(M[i]["name"]) and M[i]["min"][1] < y_hi and M[i]["min"][1] + M[i]["span"][1] > y_lo]
    g.update({"sheet": S, "band": [y_lo, y_hi], "left_out": limb, "dropped": dropped})
    return g


# ------------------------------------------------------------------ packing
def b64z(a: np.ndarray) -> str:
    return base64.b64encode(zlib.compress(a.tobytes(), 9)).decode("ascii")


def pack(ctx, garments: dict):
    M = ctx["M"]
    src, src_of = [], {}
    out = {}
    stats = {}
    for key, (label, g) in garments.items():
        S = g["sheet"]
        st, sw, h = g["t"], g["w"], g["h"]
        loc = S.tri_local[st]
        pk = S.tri_k[st]
        ks = []
        for k in pk:
            i = S.ids[k]
            if i not in src_of:
                src_of[i] = len(src)
                src.append([i, M[i]["id"], M[i]["vc"]])
            ks.append(src_of[i])
        nb = len(st)
        # the wall: a second copy of each edge vertex at height ~0 (on the skin)
        wall = g["wall"]
        wv = np.unique(wall) if len(wall) else np.zeros(0, np.int64)
        wmap = {int(v): nb + q for q, v in enumerate(wv)}
        bind = np.zeros((nb + len(wv), 7), dtype=np.uint16)
        bind[:nb, 0] = ks
        bind[:nb, 1:4] = loc
        wq = np.clip(np.round(sw * 65535), 0, 65535)
        bind[:nb, 4:6] = wq[:, :2]
        bind[:nb, 6] = np.clip(np.round(h * 100), 0, 65535)
        bind[nb:] = bind[wv]
        bind[nb:, 6] = 20                                    # 0.2 mm above the skin
        wt = []
        for a, b in wall:
            wt.append([a, b, wmap[int(b)]])
            wt.append([a, wmap[int(b)], wmap[int(a)]])
        tri_body = g["tri"]["body"]
        tri_rim = np.concatenate([g["tri"]["rim"], np.array(wt, dtype=np.int64).reshape(-1, 3)])
        nbt = len(bind)
        o = {"label": label, "nb": int(nbt), "bind": b64z(bind)}
        nf = 0
        if "fix_pos" in g and len(g["fix_pos"]):
            fx = np.concatenate([g["fix_pos"], g["fix_nrm"]], axis=1).astype("<f4")
            nf = len(fx)
            o["fix"] = b64z(fx)
            tri_body = np.concatenate([tri_body, g["fix_tri"] + nbt])
        o["nf"] = int(nf)
        if nbt + nf > 65535:
            raise SystemExit(f"cover: {key} has {nbt + nf} vertices, more than one 16-bit index buffer holds")
        o["body"] = b64z(tri_body.astype("<u2"))
        o["rim"] = b64z(tri_rim.astype("<u2"))
        o["nt"] = [int(len(tri_body)), int(len(tri_rim))]
        o["band_mm"] = [round(float(x), 1) for x in g["band"]]
        out[key] = o
        gaps = g["gaps"]
        if len(gaps) and len(g.get("left_out", [])):
            lp = np.concatenate([mesh(ctx["man"], ctx["bin"], i)[0] for i in g["left_out"]])
            gaps = gaps[cKDTree(lp).query(gaps)[0] > 4.0]
        g["holes"] = gaps
        stats[key] = {"bound": int(nbt), "fixed": int(nf), "tris": int(len(tri_body) + len(tri_rim)), "open_edges": int(len(g["open"])), "holes": int(len(gaps)),
                      "h_max": round(float(h.max()), 2), "h_mean": round(float(h.mean()), 2), "dropped_faces": int(g["dropped"]), "pieces": len(set(ks))}
    return {"schema": "nmsk.cover.v1", "round": "Q389",
            "what": "display covering, not an anatomical structure; derived from this page's skin mesh (offset outer sheet, taut heights, hull pouch); hides nothing from measurements",
            "h0_mm": H0, "src": src, "garments": out, "stats": stats}


def build(html: Path):
    pg = load_page(html)
    if pg is None:
        return None
    ctx = page_context(*pg)
    gs = {"briefs": ("Briefs", briefs(ctx))}
    variant = (pg[0].get("variant") or "")
    if "female" in variant.lower():
        t = top(ctx)
        if t is not None:
            gs["top"] = ("Top", t)
    return ctx, gs, pack(ctx, gs)


def block(doc: dict) -> str:
    js = json.dumps(doc, separators=(",", ":"), sort_keys=True).replace("<", "\\u003c")
    return f'{BEGIN}<script type="application/json" id="nmsk-cover">{js}</script>{END}'


def inject(d: Path, write=True) -> int:
    n = 0
    for f in sorted(d.glob("*.html")):
        s = f.read_text(encoding="utf-8")
        if s.count(BEGIN) != 1 or s.count(END) != 1 or f.name == "index.html":
            continue
        r = build(f)
        if r is None:
            continue
        doc = r[2]
        b = block(doc)
        if write:
            i, j = s.index(BEGIN), s.index(END) + len(END)
            f.write_text(s[:i] + b + s[j:], encoding="utf-8")
        print(f"cover: {f.name}: {json.dumps(doc['stats'], sort_keys=True)} block {len(b)} bytes" + ("" if write else " (check only)"))
        n += 1
    if not n:
        raise SystemExit(f"no page with the NMSK-COVER markers and a manifest in {d}")
    return n


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("--inject", "--check") and argv[1:]:
        for a in argv[1:]:
            inject(Path(a), write=argv[0] == "--inject")
        return 0
    if argv and argv[0] == "--preview" and len(argv) == 3:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import preview_cover_q389 as pv
        return pv.main(argv[1], argv[2])
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
