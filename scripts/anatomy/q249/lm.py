"""Q249: bone / neighbour landmarks of one page for the rule-based nerves.  Pel(key) -> .lm[name] (3-vectors, atlas frame mm; +X right, +Y sup, +Z ant), .notes (how each was found).
Everything is MEASURED ON THE PAGE'S OWN MESHES (hip bones, sacrum, coccyx, obturator internus, external anal sphincter, ...) by geometric rules; fractions / offsets taken from the literature are listed in LIT.
Frame helper functions only: the nerve courses are in rule_nerves.py."""
from __future__ import annotations
import os, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
import lig_pages as PG, rulelig as RL  # noqa: E402

SG = {"l": -1.0, "r": 1.0}
# sacral anterior foramina: centre of foramen k as a fraction of the sacral height (top of the sacral mass -> apex, measured along y) and the lateral distance from the midline (mm at a sacral half-width of 60 mm, scaled
# with the page's half-width).  The S3 / S4 positions were READ OFF the foramina that the Z-Anatomy sacrum has as holes (S3 0.63-0.66 of the height, 16-19 mm from the midline on four Z pages); S1 / S2 follow the
# standard sacral proportions (foramen spacing 20-25 mm) = ASSUMPTION.  Foramen height 13 / 13 / 10 mm for S1 / S2 / S3 (Ebraheim NA et al., Orthopedics 1998;21:703-6, PMID 9642709, 21 dry sacra).
FORAMEN_FRAC = {1: 0.28, 2: 0.46, 3: 0.63, 4: 0.79}
FORAMEN_LAT = {1: 25.0, 2: 22.0, 3: 18.0, 4: 16.0}


class Pel:
    def __init__(self, key):
        self.key = key
        self.ctx = RL.Ctx(key)
        self.E, self.bf, self.F = self.ctx.E, self.ctx.bf, self.ctx.F
        self.female = self.ctx.female
        self.lm, self.notes = {}, {}
        self._sacrum()
        for s in "lr":
            self._side(s)

    # ------------------------------------------------------------------ helpers
    def ids(self, pat_start, side=None, exclude="zfill"):
        out = []
        for i in self.E:
            if i.startswith(pat_start) and exclude not in i and (side is None or i.endswith(f"_{side}")):
                out.append(i)
        return out

    def lumbar(self):
        """[L1..L5] entry ids (the own pages number lumbar_vertebrae#k bottom-up, the Z pages carry zan_vertebra_l1..l5)"""
        import re
        z = [f"zan_vertebra_l{k}" for k in range(1, 6)]
        if all(i in self.E for i in z):
            return z
        own = sorted([i for i in self.E if re.match(r"lumbar_vertebrae#\d+$", i)], key=lambda i: -float(self.E[i]["v"][:, 1].mean()))
        return own[-5:] if len(own) >= 5 else None      # the Imaging-based female page carries a 6th (T12-like) piece above L1: the lowest five

    def bones(self):
        return [i for i, e in self.E.items() if e["sys"] == "bone" and "zfill" not in i and len(e["f"]) > 20]

    def snap(self, P, ids=None):
        ids = ids or self.ctx.near_bones(np.atleast_2d(P), 15.0)
        d, a, n, p = self.bf.signed(np.atleast_2d(P), ids)
        return p[0], n[0], float(d[0])

    # ------------------------------------------------------------------ sacrum
    def _sacrum(self):
        xm = self.F["x_mid"]
        ids = [i for i in self.E if self.E[i]["sys"] == "bone" and (i.startswith("sacrum") or i == "coccyx") and "zfill" not in i]
        S = np.vstack([self.E[i]["v"] for i in ids]); S = S[np.abs(S[:, 0] - xm) < 70]
        self.sac_ids = ids
        self.sac_v = S
        y_top = float(np.percentile(S[:, 1], 99.5)); y_min = float(S[:, 1].min())
        # sacral apex: lowest level at which the sacral width (x extent) is still >= 24 mm (the coccyx is narrower / separate)
        ys = np.arange(y_top, y_min, -1.0); y_end = y_min
        for y in ys:
            m = np.abs(S[:, 1] - y) < 1.5
            if m.sum() and np.ptp(S[m, 0]) < 24 and y < y_top - 60:
                y_end = float(y); break
        self.sac = dict(y_top=y_top, y_end=y_end, half_w=float(np.percentile(np.abs(S[:, 0] - xm), 99) ), x_mid=xm)
        # promontory: most anterior vertex of the upper sacral body on the midline
        m = (np.abs(S[:, 0] - xm) < 10) & (S[:, 1] > y_top - 30)
        self.lm["promontory"] = S[m][np.argmax(S[m, 2])]
        # coccyx tip
        cx = self.E["coccyx"]["v"] if "coccyx" in self.E else S
        self.lm["coccyx_tip"] = cx[np.argmin(cx[:, 1])]
        hw = self.sac["half_w"]
        for k in (1, 2, 3, 4):
            yk = y_top - FORAMEN_FRAC[k] * (y_top - y_end)
            for s in "lr":
                xk = xm + SG[s] * FORAMEN_LAT[k] * hw / 60.0
                win = (np.abs(S[:, 0] - xk) < 7) & (np.abs(S[:, 1] - yk) < 7)
                if win.sum() < 3:
                    win = (np.abs(S[:, 0] - xk) < 12) & (np.abs(S[:, 1] - yk) < 12)
                P = np.array([xk, yk, S[win][:, 2].max()])
                p, n, d = self.snap(P, self.sac_ids)
                self.lm[f"S{k}_foramen_{s}"] = p; self.lm[f"S{k}_normal_{s}"] = n
        self.notes["sacrum"] = f"sacral mass y {y_end:.0f}..{y_top:.0f}, half-width {hw:.0f} mm; foramina by fractions of the height {FORAMEN_FRAC} and lateral offsets {FORAMEN_LAT} (scaled by half-width / 60)"

    # ------------------------------------------------------------------ one side
    def _side(self, s):
        sg = SG[s]; F = self.F; hip = f"hip_bone_{s}"
        IS = self.ctx.ischial_spine(s)
        IS, _, _ = self.snap(IS, [hip]); self.lm[f"IS_{s}"] = IS
        v = self.E[hip]["v"]
        mt = (v[:, 2] < F["z_front"] - 60) & (sg * (v[:, 0] - F["x_mid"]) > 20)
        IT = v[np.argmin(np.where(mt, v[:, 1], 1e9))]; self.lm[f"IT_{s}"] = IT
        # subpubic point of the inferior pubic ramus (just lateral to the symphysis, at the subpubic angle)
        T = np.array([F["x_mid"] + sg * (F["half_gap"] + 5.0), F["y_bot"] - 2.0, F["z_front"] - 12.0])
        p, n, d = self.snap(T, [hip]); self.lm[f"subpubic_{s}"] = p
        # anterior superior iliac spine: anterior-most vertex of the upper hip bone
        up = v[v[:, 1] > np.percentile(v[:, 1], 62)]
        self.lm[f"ASIS_{s}"] = up[np.argmax(up[:, 2])]
        # upper pubic tubercle / body for the genital nerves
        T2 = np.array([F["x_mid"] + sg * (F["half_gap"] + 14.0), F["y_top"] - 2.0, F["z_front"] - 6.0])
        self.lm[f"pubic_crest_{s}"] = self.snap(T2, [hip])[0]


def vec(a):
    a = np.asarray(a, float); return a / (np.linalg.norm(a) + 1e-12)


if __name__ == "__main__":
    import json
    P = Pel(sys.argv[1]); print(P.notes)
    for k, v in P.lm.items():
        if not k.endswith(("normal_l", "normal_r")): print(k, np.round(v, 1).tolist())


# ---------------------------------------------------------------------- tube-like neighbour structures
def centerline(v, f, n=40, min_len=10.0):
    """centreline of a tube-like mesh: geodesic (edge-graph) distance from one end, vertices binned by it, mean position per bin.  -> (n,3) ordered end A -> end B, or None"""
    import scipy.sparse as sp
    from scipy.sparse.csgraph import dijkstra, connected_components
    v = np.asarray(v, float); f = np.asarray(f)
    e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]); e = np.unique(np.sort(e, axis=1), axis=0)
    w = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    G = sp.coo_matrix((np.r_[w, w], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(len(v), len(v))).tocsr()
    nc, lab = connected_components(G, directed=False)
    big = np.argmax(np.bincount(lab)); idx = np.where(lab == big)[0]
    d0 = dijkstra(G, indices=idx[0], directed=False)[idx]
    a = idx[np.argmax(d0)]
    da = dijkstra(G, indices=a, directed=False)
    b = idx[np.argmax(da[idx])]
    D = da[idx]
    if D.max() < min_len:
        return None
    bins = np.linspace(0, D.max() + 1e-6, n + 1)
    C = []
    for i in range(n):
        m = (D >= bins[i]) & (D < bins[i + 1])
        if m.any():
            C.append(v[idx][m].mean(0))
    return np.array(C)


def resample(P, n):
    P = np.asarray(P, float); s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(3)], 1)
