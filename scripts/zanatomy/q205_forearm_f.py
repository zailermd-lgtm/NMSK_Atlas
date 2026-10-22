"""Q205 (female): the forearm bones of the Z-Anatomy model fitted to HER, refit on her own evidence so that the WRIST chain closes.

Measured (Q204 hands audit of the published Z female page): forearm bones -> scaphoid gap 20.0 mm (R) / 8.3 (L), lunate 10.5 (L), triquetrum 12.8 (R) / 15.5 (L) mm (unfitted base 0.5 / 1.4 / 5.7).  Her own CT
shows radius -> carpals 0.1 mm and ulna -> carpals 6.0 mm (right); the Z radius_r ends 24 mm short of her radius label (distal end y 150 vs 126) while the Z ulna_r reaches 22 mm beyond her ulna label (y 113 vs 135):
the Q168 per-bone fits of the FOV-cut / partial labels left an axial offset of each bone.  Same method as Q201 for his arms (q201_chain.Fit: each bone a similarity about its centroid + a smooth bend of the
elbow end <= 15 mm, fitted to its label surface, the Z-source humerus-radius/ulna contact distances (humerus fixed) and the Z-source radius/ulna - scaphoid/lunate/triquetrum contacts onto HER fixed carpals),
aimed at her evidence: right = her CT radius / ulna meshes, left = her left-forearm cryosection evidence (Q192, cream voxels assigned to the nearest bone).
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q190_metrics as Mx
from scripts.zanatomy import q199_elbow as E
from scripts.zanatomy import q201_chain as C

C.SCALE_ABS = {"humerus": (0.9, 1.2), "radius": (0.9, 1.2), "ulna": (0.9, 1.2)}
ZONE_F = (300.0, 400.0)


class FitF(C.Fit):
    def __init__(self, side, by, raw, ev_shaft, n=3000):
        """ev_shaft = {'radius': points, 'ulna': points} (her radius / ulna evidence, atlas mm)"""
        s = "_" + side
        self.side, self.by, self.raw = side, by, raw
        self.smp = {b: E.bary_samples(raw[b + s], by[b + s]["f"], n, seed=21) for b in C.BONES}
        self.v0 = {b: by[b + s]["v"] for b in C.BONES}
        self.S0 = {b: E.at(self.v0[b], self.smp[b]) for b in C.BONES}
        self.c0 = {b: self.v0[b].mean(0) for b in C.BONES}
        rng = np.random.default_rng(5)
        self.lab = {}
        for b in C.BONES:
            P = ev_shaft.get(b)
            if P is None:
                P = self.v0[b][:5]
            self.lab[b] = (cKDTree(P[rng.permutation(len(P))[:6000]]), P[rng.permutation(len(P))[:2500]], (P[:, 1].min(), P[:, 1].max()))
        self.lo, self.edt, self.bound_s = np.zeros(3), np.zeros((2, 2, 2), np.float32), np.zeros((1, 3))
        self.jsmp, self.jsel, self.jj, self.jd0 = E.joint_pairs(raw, side, by)
        self._wrist(by, raw, side)
        self.cur = {b: np.r_[np.zeros(6), 1.0, np.zeros(3)] for b in C.BONES}
        self.abs0 = {b: C._procrustes_scale(raw[b + s], by[b + s]["v"]) for b in C.BONES}

    def reg(self, cur, active):
        r = []
        for b in active:
            p = cur[b]
            r += [4.0 * (p[6] - 1.0), 0.01 * np.degrees(np.linalg.norm(p[:3])), 0.01 * np.linalg.norm(p[3:6]), 0.15 * np.linalg.norm(p[7:10])]
        return np.array(r)

    def run_f(self, log=print):
        """radius and ulna only (humerus fixed at its Q199 pose); label-only multi-start over the roll, then both bones together with the elbow-contact and wrist-contact terms"""
        C.ZONE = ZONE_F
        act = ("radius", "ulna")
        before = self.stats_f(self.cur)
        cur = dict(self.cur)
        for b in act:
            cands = self.label_fit(b)
            # the roll of a long bone about its axis is the weakly constrained DOF of a partial label (Q201: six rolls of one ulna fit the label equally): among the label-only solutions within 5 % of the
            # best cost the one with the SMALLEST rotation from the Q199 pose wins (no roll the evidence does not ask for)
            c0 = cands[0][0]
            ok = [c for c in cands if c[0] <= 1.05 * c0 + 1e-9]
            best = min(ok, key=lambda c: float(np.linalg.norm(c[1][:3])))
            cur[b] = best[1]
            log(f"  Q205 {self.side} {b}: label-only candidates within 5 %: {len(ok)} of {len(cands)}; chosen rotation {np.degrees(np.linalg.norm(best[1][:3])):.0f} deg (best-cost one {np.degrees(np.linalg.norm(cands[0][1][:3])):.0f} deg)")
        cur, _ = self.stage(act, C.W_PAIR, cur, box=C.BOX, w_union=0.0)
        self.cur = cur
        return cur, before, self.stats_f(cur)

    def stats_f(self, cur):
        sh, sr, up, ur, pair = self.parts(cur, ("radius", "ulna"))
        ch, S = self.surfaces(cur)
        jt = E.joint_stat(self.jsmp, self.jsel, self.jj, self.jd0, ch.hum(self.v0["humerus"]), ch.rad(self.v0["radius"]), ch.uln(self.v0["ulna"]))
        return {"label_to_Z_mm_median": round(float(np.median(sr)), 2), "Z_to_label_mm_median": round(float(np.median(sh[sh > 0])) if (sh > 0).any() else 0.0, 2), "joint": jt,
                "wrist_gap_change_mm_mean_abs": round(float(np.abs(self.wrist_last).mean()), 2) if len(self.wrist_last) else None}


def fit_forearm_f(side, by, raw, ev_shaft, log=print):
    """returns (ChainM, report): humerus identity, radius / ulna refit"""
    F = FitF(side, by, raw, ev_shaft)
    cur, before, after = F.run_f(log)
    ch = F.chain(cur)
    s = "_" + side
    rep = {"before": before, "after": after, "params": {b: {"rot_deg": round(float(np.degrees(np.linalg.norm(ch.p[b][:3]))), 2), "translation_mm": ch.p[b][3:6].round(2).tolist(), "scale": round(float(ch.p[b][6]), 4),
                                                           "bend_mm": ch.p[b][7:10].round(1).tolist()} for b in ("radius", "ulna")},
           "bone_move_mm": {b: {"max": round(float(np.linalg.norm(ch.apply(b, F.v0[b]) - F.v0[b], axis=1).max()), 1), "mean": round(float(np.linalg.norm(ch.apply(b, F.v0[b]) - F.v0[b], axis=1).mean()), 1)} for b in ("radius", "ulna")},
           "wrist_centre_raw": C.wrist_centre(by, raw, side).round(2).tolist()}
    log(f"  Q205 {side} forearm: {rep['params']}\n   before {before}\n   after  {after}")
    return ch, rep
