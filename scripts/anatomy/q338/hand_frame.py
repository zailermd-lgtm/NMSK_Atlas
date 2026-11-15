"""Q338 hand geometry helpers: per-finger bone axes and palmar / radial frames of a Base page, and the local
coordinates of a point relative to a finger (which finger, which phalanx, distance to the bone axis, palmar and radial
offsets).  Reads the page through the Q241 model loader (scripts/anatomy/q241/model.py); never writes the page.

Frame per finger (model space, mm): u = the phalanx axis (joint centre -> joint centre, from the pose rig's joints),
p = palmar = the direction the distal end moves under positive flexion of the rig joint (a x u, the rig's own
convention "flexion moves the distal segment toward the palm"), r = radial = toward the thumb (sign from the first
metacarpal), orthogonal to u and p."""
from __future__ import annotations
import re, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
Q241 = HERE.parent / "q241"
sys.path.insert(0, str(Q241))
import model as MD  # noqa: E402
from geom import unit, components, trimmed_extreme, pca  # noqa: E402

PH = ("prox", "midd", "dist")
SEGN = {"prox": "p", "midd": "m", "dist": "d"}


def orth(a, b):
    return unit(a - (a @ b) * b)


class Hand:
    """finger frames of one side of one page.  rig: the rig payload dict (segs/joints as stored in the page)."""

    def __init__(self, M, rig, s):
        self.M, self.s = M, s
        B = M.bones()
        J = {j["id"]: j for j in rig["joints"]}
        self.fingers = {}
        mc1 = B.get("mc_1_" + s)
        th_c = mc1["v"].mean(0) if mc1 is not None else None
        for f in range(1, 6):
            bones = {}
            for ph in PH:
                k = "ph_hand_%d_%s_%s" % (f, ph, s)
                if k in B:
                    bones[ph] = B[k]["v"]
            mc = B.get("mc_%d_%s" % (f, s))
            if f == 1:
                cj = [J.get("thumb_cmc_" + s), J.get("thumb_mcp_" + s), J.get("thumb_ip_" + s)]
                names = ["mc", "prox", "dist"]
                vs = [mc["v"] if mc is not None else None, bones.get("prox"), bones.get("dist")]
            else:
                cj = [J.get("f%d_mcp_%s" % (f, s)), J.get("f%d_pip_%s" % (f, s)), J.get("f%d_dip_%s" % (f, s))]
                names = ["prox", "midd", "dist"]
                vs = [bones.get("prox"), bones.get("midd"), bones.get("dist")]
            if any(c is None for c in cj) or any(v is None for v in vs):
                continue
            cs = [np.array(c["c"], float) for c in cj]
            u_last = unit(cs[-1] - cs[-2]) if f != 1 else unit(cs[2] - cs[1])
            tip = trimmed_extreme(vs[-1], unit(vs[-1].mean(0) - cs[-1]), 0.03)
            ends = cs + [tip]
            segs = []
            for n, (a, b) in enumerate(zip(ends[:-1], ends[1:])):
                u = unit(b - a)
                j = cj[n]
                ax = np.array(j["dof"][0]["a"], float)
                p = unit(np.cross(ax, u))                  # d/dq of rot(ax, q) u = ax x u : where the distal end goes under flexion
                segs.append(dict(name=names[n], a=a, b=b, u=u, p=p, v=vs[n], joint=j["id"]))
            self.fingers[f] = segs
        # radial direction: per finger, toward the thumb metacarpal
        hc = np.vstack([B["mc_%d_%s" % (f, s)]["v"] for f in range(2, 6) if ("mc_%d_%s" % (f, s)) in B]).mean(0)
        for f, segs in self.fingers.items():
            for sg in segs:
                r = unit(np.cross(sg["p"], sg["u"]))
                ref = (th_c - hc) if f != 1 else (B["mc_2_" + s]["v"].mean(0) - hc)   # thumb: 'radial' kept as the side away from the index
                if th_c is not None and r @ ref < 0:
                    r = -r
                sg["r"] = r
        # the axis line through the bone's own cross-section centre (joint centres sit off-centre in the phalanx)
        for f, segs in self.fingers.items():
            for sg in segs:
                v = sg["v"]; L = np.linalg.norm(sg["b"] - sg["a"])
                t = (v - sg["a"]) @ sg["u"] / L
                m = (t > 0.25) & (t < 0.75)
                if m.sum() >= 10:
                    d = v[m] - sg["a"] - np.outer(t[m] * L, sg["u"])
                    off = 0.5 * (d @ sg["p"]).max() + 0.5 * (d @ sg["p"]).min(), 0.5 * (d @ sg["r"]).max() + 0.5 * (d @ sg["r"]).min()
                    sh = off[0] * sg["p"] + off[1] * sg["r"]
                    sg["a"] = sg["a"] + sh; sg["b"] = sg["b"] + sh; sg["shift"] = sh
                    dd = v[m] - sg["a"] - np.outer(t[m] * L, sg["u"])
                    sg["half_p"] = float(0.5 * ((dd @ sg["p"]).max() - (dd @ sg["p"]).min())); sg["half_r"] = float(0.5 * ((dd @ sg["r"]).max() - (dd @ sg["r"]).min()))

    def locate(self, P, fingers=None):
        """P (n,3) -> dict of arrays: finger, seg index, t (0..1 along the segment), dist to axis, palmar, radial offsets (mm)"""
        P = np.asarray(P, float)
        best = None
        for f, segs in self.fingers.items():
            if fingers is not None and f not in fingers:
                continue
            for k, sg in enumerate(segs):
                L = np.linalg.norm(sg["b"] - sg["a"])
                t = np.clip((P - sg["a"]) @ sg["u"] / L, 0, 1)
                Q = sg["a"] + np.outer(t * L, sg["u"])
                d = P - Q
                dist = np.linalg.norm(d, axis=1)
                row = np.c_[np.full(len(P), f), np.full(len(P), k), t, dist, d @ sg["p"], d @ sg["r"]]
                if best is None:
                    best = row
                else:
                    m = dist < best[:, 3]
                    best[m] = row[m]
        return dict(finger=best[:, 0].astype(int), seg=best[:, 1].astype(int), t=best[:, 2], dist=best[:, 3], palmar=best[:, 4], radial=best[:, 5])


def mesh_parts(x, min_v=8):
    """connected components of a structure -> list of vertex index arrays (largest first)"""
    lab = components(x["f"], len(x["v"]))
    out = [np.where(lab == c)[0] for c in np.unique(lab)]
    out = [o for o in out if len(o) >= min_v]
    return sorted(out, key=len, reverse=True)
