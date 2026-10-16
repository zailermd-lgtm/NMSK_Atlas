"""Q217: ONE smooth injective map of the Z BASE forearm onto HIS forearm: a twisted tube.

The Z base radius / ulna and the Z-fitted radius / ulna of his page have the same vertex order, so every base bone vertex has its place on the page.  Along the forearm (axial coordinate s of the base mid-axis, every STEP mm) the two bone
centroids give a local frame: e1 = ulna - radius (interosseous direction), e3 = the axis, e2 = e3 x e1.  The map at level s is x -> m_p(s) + S(s) R_p(s) R_b(s)^T (x - m_b(s)) (frames and centres smoothed along s): the whole cross-section
of the base forearm (every muscle in it) is turned and shifted exactly like its two bones, the turn changing smoothly along the forearm (the pronation twist).  A map of this kind cannot create overlap that the base does not
have (injective); the Z base's own tiling (muscle | muscle) comes with it."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d


def _unit(a):
    return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-12)


def frames(c_r, c_u, m):
    """(n, 3, 3) orthonormal frames from centres (n, 3): rows e1 (r -> u), e2, e3 (axis)"""
    t = np.gradient(m, axis=0)
    t = _unit(gaussian_filter1d(t, 1.0, axis=0, mode="nearest"))
    e1 = c_u - c_r
    e1 = _unit(e1 - (e1 * t).sum(1, keepdims=True) * t)
    e2 = np.cross(t, e1)
    return np.stack([e1, e2, t], axis=1)


class TwistMap:
    def __init__(self, base, page, bones=("radius_l", "ulna_l"), step=8.0, smooth=1.5, scale=False, blocks=(), block_gap=12.0):
        """base / page = {bone id: vertices (same order)}; blocks = [(base points, page points)] rigid blocks (distal humerus, carpals) that become extra levels of the chain at their own axial position"""
        rb, ub = base[bones[0]], base[bones[1]]
        rp, up = page[bones[0]], page[bones[1]]
        allb = np.concatenate([rb, ub])
        c = allb.mean(0)
        a = np.linalg.svd(allb - c, full_matrices=False)[2][0]
        if a[1] < 0:
            a = -a
        self.a = a
        self.o = c
        sb = (allb - c) @ a
        lo, hi = float(np.percentile(sb, 3)), float(np.percentile(sb, 97))
        self.edges = np.arange(lo, hi + step, step)
        self.s = 0.5 * (self.edges[:-1] + self.edges[1:])
        cr_b, cu_b, cr_p, cu_p, keep = [], [], [], [], []
        for k in range(len(self.s)):
            mr = (((rb - c) @ a) >= self.edges[k]) & (((rb - c) @ a) < self.edges[k + 1])
            mu = (((ub - c) @ a) >= self.edges[k]) & (((ub - c) @ a) < self.edges[k + 1])
            if mr.sum() < 3 or mu.sum() < 3:
                continue
            keep.append(k)
            cr_b.append(rb[mr].mean(0)); cr_p.append(rp[mr].mean(0))
            cu_b.append(ub[mu].mean(0)); cu_p.append(up[mu].mean(0))
        self.s = self.s[keep]
        cr_b, cu_b, cr_p, cu_p = map(np.array, (cr_b, cu_b, cr_p, cu_p))
        sm = lambda x: gaussian_filter1d(x, smooth, axis=0, mode="nearest")
        cr_b, cu_b, cr_p, cu_p = sm(cr_b), sm(cu_b), sm(cr_p), sm(cu_p)
        self.mb, self.mp = 0.5 * (cr_b + cu_b), 0.5 * (cr_p + cu_p)
        Fb, Fp = frames(cr_b, cu_b, self.mb), frames(cr_p, cu_p, self.mp)
        self.R = np.einsum("nki,nkj->nij", Fp, Fb)          # R_p R_b^T maps base frame coordinates to page: x_p = Fp^T Fb x_b  (row frames)
        self.S = (np.linalg.norm(cu_p - cr_p, axis=1) / np.maximum(np.linalg.norm(cu_b - cr_b, axis=1), 1e-9)) if scale else np.ones(len(self.s))
        self.S = np.clip(sm(self.S), 0.9, 1.15)
        # smooth the rotation entries along s and re-orthonormalise
        Rm = sm(self.R.reshape(len(self.s), 9)).reshape(-1, 3, 3)
        U, _, Vt = np.linalg.svd(Rm)
        self.R = U @ Vt
        self.block_info = []
        for bp, qp in blocks:
            bp, qp = np.asarray(bp, float), np.asarray(qp, float)
            cb, cq = bp.mean(0), qp.mean(0)
            Hm = (bp - cb).T @ (qp - cq)
            Ub, _, Vb = np.linalg.svd(Hm)
            Rb = Vb.T @ np.diag([1, 1, np.sign(np.linalg.det(Vb.T @ Ub.T))]) @ Ub.T
            sb_ = float((cb - c) @ a)
            if sb_ > self.s[-1]:
                keep = self.s < sb_ - block_gap
            else:
                keep = self.s > sb_ + block_gap
            self.s, self.mb, self.mp, self.R, self.S = self.s[keep], self.mb[keep], self.mp[keep], self.R[keep], self.S[keep]
            self.s = np.append(self.s, sb_)
            self.mb = np.vstack([self.mb, cb])
            self.mp = np.vstack([self.mp, cq])
            self.R = np.concatenate([self.R, Rb[None]])
            self.S = np.append(self.S, 1.0)
            o = np.argsort(self.s)
            self.s, self.mb, self.mp, self.R, self.S = self.s[o], self.mb[o], self.mp[o], self.R[o], self.S[o]
            self.block_info.append(dict(s=round(sb_, 1), rms=round(float(np.sqrt((((bp - cb) @ Rb.T + cq - qp) ** 2).sum(1).mean())), 2)))

    def _at(self, s_x):
        """interpolated (m_b, m_p, R, S) at axial coordinates (clamped linear interpolation; beyond the ends the end frame is kept)"""
        sc = np.clip(s_x, self.s[0], self.s[-1])
        i = np.clip(np.searchsorted(self.s, sc) - 1, 0, len(self.s) - 2)
        w = ((sc - self.s[i]) / (self.s[i + 1] - self.s[i]))[:, None]
        mb = self.mb[i] * (1 - w) + self.mb[i + 1] * w
        mp = self.mp[i] * (1 - w) + self.mp[i + 1] * w
        R = self.R[i] * (1 - w[:, :, None]) + self.R[i + 1] * w[:, :, None]
        U, _, Vt = np.linalg.svd(R)
        R = U @ Vt
        S = (self.S[i] * (1 - w[:, 0]) + self.S[i + 1] * w[:, 0])
        return mb, mp, R, S, sc

    def __call__(self, x):
        x = np.asarray(x, float)
        sx = (x - self.o) @ self.a
        mb, mp, R, S, sc = self._at(sx)
        # beyond the ends the map continues rigidly along the axis from the end frame
        off = (sx - sc)[:, None] * self.a
        y = np.einsum("nij,nj->ni", R, x - mb - off)
        # R maps base-frame (rows) to page: use x_p = R (x_b - m_b)
        return mp + S[:, None] * y + off @ np.eye(3)
