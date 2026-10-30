"""Q295: page loader + axial cross-section rasteriser (nonzero winding per structure, outline fallback for open meshes)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts/zanatomy")); sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))

SRC = {"own_m": "build/q293/bundle_own_m", "own_f": "build/q293/bundle_own_f", "base_m": "build/q293/viewer_zan_atlas",
       "base_f": "build/q293/viewer_base_female", "comb_m": "build/q293/viewer_zan_vhm", "comb_f": "build/q293/viewer_zan_female"}
STEM = {'own_m': 'atlas_viewer_male', 'own_f': 'atlas_viewer_female', 'base_m': 'atlas_viewer_zan_atlas', 'base_f': 'atlas_viewer_base_female',
        'comb_m': 'atlas_viewer_zan_male_fitted', 'comb_f': 'atlas_viewer_zan_female'}
SHEET = {"fascia", "joint", "bursa", "insertion"}


class Page:
    """all structures of a page, concatenated: V (n,3) float32, F (m,3) int64, fs (m,) structure index; per structure id / cat / name / hidden"""

    def __init__(self, key, src=None):
        self.key = key
        src = Path(src or (REPO / SRC[key]))
        ids, cats, names, hid, parts = [], [], [], [], []
        if key.startswith("own"):
            b = json.loads((src / "bundle.json").read_text()); blob = (src / "bundle.bin").read_bytes()
            q = float(b["quantum_mm"]); off = 0; idx = {}
            for e in b["structures"]:
                nv, nf = int(e["nv"]), int(e["nf"])
                v = np.frombuffer(blob, np.int16, nv * 3, off).reshape(-1, 3).astype(np.float32) * q; off += nv * 6
                f = np.frombuffer(blob, np.uint16, nf * 3, off).reshape(-1, 3).astype(np.int64); off += nf * 6
                if e["id"] not in idx:
                    idx[e["id"]] = len(ids); ids.append(e["id"]); cat = e["cat"]
                    if e["id"] == "skin" or (e.get("rec") or {}).get("name", "").lower().startswith("skin"):
                        cat = "skin"
                    cats.append(cat); names.append((e.get("rec") or {}).get("name") or e["id"]); hid.append(bool(e.get("hidden_default")))
                parts.append((idx[e["id"]], v, f))
        else:
            from scripts.zanatomy import q205_pages as P5
            man, blob = P5.load_page(src, STEM[key]); idx = {}
            for m in man["meshes"]:
                qv = np.frombuffer(blob, "<u2", m["vc"] * 3, m["vo"]).reshape(-1, 3).astype(np.float32)
                v = (np.array(m["min"], np.float32) + qv / 65535.0 * np.array(m["span"], np.float32))
                f = np.frombuffer(blob, "<u2", m["ic"] * 3, m["io"]).reshape(-1, 3).astype(np.int64)
                if m["id"] not in idx:
                    idx[m["id"]] = len(ids); ids.append(m["id"]); cats.append(m["sys"]); names.append(m.get("name") or m["id"]); hid.append(bool(m.get("hd")))
                parts.append((idx[m["id"]], v, f))
        self.ids, self.cats, self.names, self.hidden = ids, np.array(cats), names, np.array(hid)
        vs, fs, ss, o = [], [], [], 0
        for s, v, f in parts:
            vs.append(v); fs.append(f + o); ss.append(np.full(len(f), s, np.int32)); o += len(v)
        self.V = np.vstack(vs); self.F = np.vstack(fs); self.fs = np.concatenate(ss)
        a, b_, c = self.V[self.F[:, 0]], self.V[self.F[:, 1]], self.V[self.F[:, 2]]
        self.N = np.cross(b_ - a, c - a)
        self.fy = np.stack([a[:, 1], b_[:, 1], c[:, 1]], 1)
        self.ymin, self.ymax = self.fy.min(1), self.fy.max(1)
        self.order = np.argsort(self.ymin); self.ymin_sorted = self.ymin[self.order]
        self.idmap = {k: i for i, k in enumerate(ids)}

    def add(self, items):
        """items: [(id, cat, name, V, F)] appended as new structures (for the after-audit)"""
        o = len(self.V); vs, fs, ss = [self.V], [self.F], [self.fs]
        for k, c, n, v, f in items:
            s = len(self.ids); self.ids.append(k); self.names.append(n)
            self.cats = np.append(self.cats, c); self.hidden = np.append(self.hidden, False)
            vs.append(np.asarray(v, np.float32)); fs.append(np.asarray(f, np.int64) + o); ss.append(np.full(len(f), s, np.int32)); o += len(v)
        self.V = np.vstack(vs); self.F = np.vstack(fs); self.fs = np.concatenate(ss)
        a, b_, c = self.V[self.F[:, 0]], self.V[self.F[:, 1]], self.V[self.F[:, 2]]
        self.N = np.cross(b_ - a, c - a)
        self.fy = np.stack([a[:, 1], b_[:, 1], c[:, 1]], 1)
        self.ymin, self.ymax = self.fy.min(1), self.fy.max(1)
        self.order = np.argsort(self.ymin); self.ymin_sorted = self.ymin[self.order]
        self.idmap = {k: i for i, k in enumerate(self.ids)}

    def sid_where(self, pred):
        return np.array([i for i, (k, c, n) in enumerate(zip(self.ids, self.cats, self.names)) if pred(k, c, n)], np.int64)

    def bbox(self, sids):
        m = np.isin(self.fs, sids); p = self.V[np.unique(self.F[m])]
        return p.min(0), p.max(0)

    def segments(self, y0):
        """plane y = y0 -> (sid, u0, v0, u1, v1) with u = x, v = z, oriented by the face normal (consistent winding)"""
        hi = np.searchsorted(self.ymin_sorted, y0, side="right")
        cand = self.order[:hi]; cand = cand[self.ymax[cand] > y0]
        if len(cand) == 0:
            return np.zeros((0,), np.int32), np.zeros((0, 4), np.float32)
        F = self.F[cand]; P = self.V[F]                    # (k,3,3)
        s = P[:, :, 1] - y0
        pos = s >= 0
        npos = pos.sum(1)
        keep = (npos == 1) | (npos == 2)
        F, P, s, pos, npos, cand = F[keep], P[keep], s[keep], pos[keep], npos[keep], cand[keep]
        lone = np.where(npos == 1, np.argmax(pos, 1), np.argmax(~pos, 1))
        a = lone; b = (lone + 1) % 3; c = (lone + 2) % 3
        r = np.arange(len(F))
        def cut(i, j):
            si, sj = s[r, i], s[r, j]; t = si / (si - sj)
            return P[r, i] + t[:, None] * (P[r, j] - P[r, i])
        p0, p1 = cut(a, b), cut(a, c)
        n = self.N[cand]
        d = np.stack([-n[:, 2], n[:, 0]], 1)               # in-plane (u=x, v=z) direction from the normal, rotated 90 deg
        seg = np.stack([p0[:, 0], p0[:, 2], p1[:, 0], p1[:, 2]], 1).astype(np.float32)
        flip = ((seg[:, 2] - seg[:, 0]) * d[:, 0] + (seg[:, 3] - seg[:, 1]) * d[:, 1]) < 0
        seg[flip] = seg[flip][:, [2, 3, 0, 1]]
        return self.fs[cand], seg


def raster(sid, seg, grid, sel=None, strict=True):
    """nonzero-winding fill per structure. grid = (u0, v0, res, W, H). Returns (pix_flat, pix_sid) for filled pixels, and the set of
    structures whose rows were open (odd winding) -> filled by the outline fallback (fill_holes of the dilated outline; sheets: outline only)."""
    u0, v0, res, W, H = grid
    if sel is not None:
        k = np.isin(sid, sel); sid, seg = sid[k], seg[k]
    va, vb = seg[:, 1], seg[:, 3]
    lo = np.minimum(va, vb); hi = np.maximum(va, vb)
    jlo = np.ceil((lo - v0) / res - 0.5).astype(np.int64); jhi = np.ceil((hi - v0) / res - 0.5).astype(np.int64)
    jlo = np.clip(jlo, 0, H); jhi = np.clip(jhi, 0, H)
    cnt = jhi - jlo
    m = cnt > 0
    rep = np.repeat(np.nonzero(m)[0], cnt[m])
    rows = np.concatenate([np.arange(a, b) for a, b in zip(jlo[m], jhi[m])]) if m.any() else np.zeros(0, np.int64)
    if len(rep) == 0:
        return np.zeros(0, np.int64), np.zeros(0, np.int32), set()
    vc = v0 + (rows + 0.5) * res
    sa = seg[rep]
    t = (vc - sa[:, 1]) / (sa[:, 3] - sa[:, 1])
    uc = sa[:, 0] + t * (sa[:, 2] - sa[:, 0])
    sg = np.where(sa[:, 3] > sa[:, 1], 1, -1)
    ss = sid[rep]
    o = np.lexsort((uc, rows, ss))
    ss, rows, uc, sg = ss[o], rows[o], uc[o], sg[o]
    grp = np.r_[True, (ss[1:] != ss[:-1]) | (rows[1:] != rows[:-1])]
    gid = np.cumsum(grp) - 1
    cs = np.cumsum(sg); start = np.nonzero(grp)[0]
    base = np.r_[0, cs[start[1:] - 1]] if len(start) > 1 else np.array([0])
    w = cs - base[gid]
    gsum = np.bincount(gid, weights=sg)
    bad_g = np.abs(gsum) > 0
    ngrp_s = np.bincount(ss[start], minlength=ss.max() + 1); nbad_s = np.bincount(ss[start][bad_g], minlength=ss.max() + 1)
    bad_s = set(np.nonzero(nbad_s > 0.02 * np.maximum(ngrp_s, 1) + 0.5)[0].tolist())
    nxt = np.r_[gid[1:] == gid[:-1], False]
    iv = nxt & (w != 0) & ~bad_g[gid]
    if bad_s and strict:
        iv &= ~np.isin(ss, list(bad_s))
    i0 = np.ceil((uc[iv] - u0) / res - 0.5).astype(np.int64); i1 = np.ceil((uc[np.nonzero(iv)[0] + 1] - u0) / res - 0.5).astype(np.int64)
    i0 = np.clip(i0, 0, W); i1 = np.clip(i1, 0, W); L = i1 - i0; k = L > 0
    rr, i0, L, sv = rows[iv][k], i0[k], L[k], ss[iv][k]
    tot = int(L.sum())
    if tot:
        st = np.repeat(np.cumsum(L) - L, L); cols = np.repeat(i0, L) + (np.arange(tot) - st)
        pix = np.repeat(rr, L) * W + cols; psid = np.repeat(sv, L).astype(np.int32)
    else:
        pix = np.zeros(0, np.int64); psid = np.zeros(0, np.int32)
    return pix, psid, bad_s


def outline_mask(seg, grid, dil=1):
    u0, v0, res, W, H = grid
    L = np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1]); n = np.maximum(2, np.ceil(L / (0.4 * res)).astype(int))
    rep = np.repeat(np.arange(len(seg)), n); t = np.concatenate([np.linspace(0, 1, k) for k in n]) if len(n) else np.zeros(0)
    s = seg[rep]; u = s[:, 0] + t * (s[:, 2] - s[:, 0]); v = s[:, 1] + t * (s[:, 3] - s[:, 1])
    i = np.floor((u - u0) / res).astype(int); j = np.floor((v - v0) / res).astype(int)
    k = (i >= 0) & (i < W) & (j >= 0) & (j < H)
    m = np.zeros((H, W), bool); m[j[k], i[k]] = True
    if dil:
        m = ndi.binary_dilation(m, iterations=dil)
    return m


def slice_page(pg, y0, grid, skin_sids, count_sids):
    """-> body (H,W) bool, cov count (H,W) int, lab (H,W) int (-1 none; one covering structure), fallback set"""
    u0, v0, res, W, H = grid
    sid, seg = pg.segments(y0)
    sk = np.isin(sid, skin_sids)
    body = np.zeros((H, W), bool)
    if sk.any():
        pix, _, bad = raster(sid[sk], seg[sk], grid, strict=False)
        body.ravel()[pix] = True
        ol = outline_mask(seg[sk], grid, dil=1)
        body |= ndi.binary_fill_holes(ol | body)
    cm = np.isin(sid, count_sids)
    sid, seg = sid[cm], seg[cm]
    sh = np.isin(pg.cats[sid], list(SHEET))
    pix, psid, bad = raster(sid[~sh], seg[~sh], grid)
    bad = set(bad) | set(np.unique(sid[sh]).tolist())
    cov = np.bincount(pix, minlength=H * W).reshape(H, W)
    lab = np.full(H * W, -1, np.int32); lab[pix] = psid
    for s in bad:
        k = sid == s
        ol = outline_mask(seg[k], grid, dil=1)
        m = ol if pg.cats[s] in SHEET else ndi.binary_fill_holes(ol)
        cov += m; lab[m.ravel()] = s
    return body, cov, lab.reshape(H, W), bad
