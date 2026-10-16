"""Q205 (male): the SHOULDER structures follow the humerus Q201 turned.

Measured (Q204 / Q198 junction audit, shoulder): after Q201 the Z male fit has 7 / 10 (L / R) major shoulder findings against 4 / 3 on the Q195 page; the new ones are all `frame_offset`
(subscapular / circumflex scapular arteries and veins, deltoid parts, coracobrachialis, supraspinatus: "sits in a different frame from the shoulder bones, 25-41 mm").  Cause: Q201 rolled
each humerus about its shaft by 45-52 deg (his head + shaft labels and the epicondyle flare in his photographs agree) and refitted it, but its scope (arm structures) left the shoulder-zone
structures (they were put back to their Q195 record, which sits on the Q195 humerus).  Here the same bone-anchored field of Q199 is applied with the displacement of the humerus
vertices (Q201 - Q195, interpolated) as the moving bone and scapula / clavicle / ribs / sternum as fixed anchors, then the Q199 guard ladder (his skin, bones, stretch, folds, volume,
origin / insertion pull to the bone) per structure.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q199_elbow as E


class HumerusDeltaChain:
    """duck-typed q199_elbow.Chain for refine_side: the bones are NOT moved (identity), the soft tissue field comes from field_fn"""

    def __init__(self, side, by):
        s = "_" + side
        v = by["humerus" + s]["v"]
        self.hc = E.sphere_centre(v[v[:, 1] > v[:, 1].max() - 30.0])
        self.P = np.zeros(10)
        ident = lambda X, P=None: np.asarray(X, float)
        self.hum = self.rad = self.uln = ident


class ShoulderField:
    """D(x) = sum_b w_b(x) D_b(x) / sum w_b: moving bone = the humerus (D = interpolated vertex displacement Q201 - Q195), fixed = every other bone within 450 mm of the head (D = 0) + a null anchor"""

    def __init__(self, side, by, v_q195_humerus, hc):
        s = "_" + side
        h = by["humerus" + s]
        self.v0 = np.asarray(v_q195_humerus, float)
        self.dv = np.asarray(h["v"], float) - self.v0
        self.tree_h = cKDTree(self.v0)
        self.tree_h_now = cKDTree(np.asarray(h["v"], float))
        pts = [np.asarray(d["v"], float) for i, d in by.items() if d["cat"] == "bone" and i != "humerus" + s and np.linalg.norm(d["v"].mean(0) - hc) < 450.0]
        self.fixed = cKDTree(np.vstack(pts))

    def __call__(self, X):
        X = np.asarray(X, float)
        dh = self.tree_h_now.query(X)[0]
        # displacement of the humerus at the nearest Q195 / Q201 vertex pair (k = 3, inverse distance)
        d, j = self.tree_h_now.query(X, k=3)
        w = 1.0 / (d + 0.5)
        w /= w.sum(1, keepdims=True)
        Dh = (self.dv[j] * w[:, :, None]).sum(1)
        W = [1.0 / (dh + E.W_SOFT_MM) ** E.W_POWER, 1.0 / (self.fixed.query(X)[0] + E.W_SOFT_MM) ** E.W_POWER, np.full(len(X), 1.0 / (E.W_NULL_MM + E.W_SOFT_MM) ** E.W_POWER)]
        W = np.array(W)
        W /= W.sum(0)
        return W[0][:, None] * Dh


def note(side, i, cat, q, m1, mv, cont):
    how = {"not moved by the field": "its origin / insertion footprint brought back to the bone", "gap closure only": "closed up against the structures it touches in the Z source"}.get(q["name"])
    s = "left" if side == "l" else "right"
    txt = (f" Q205: {'adjusted' if how else 'moved'} with the {s} humerus at the shoulder ("
           + (how if how else f"Q201 had rolled this humerus about its shaft by 45-52 deg onto his labels / photographs and left the shoulder-zone structures on the Q195 humerus; they now follow it through the bone-anchored field (scapula, clavicle, ribs fixed): {q['name']}")
           + f"; mean {mv.mean():.1f} mm, max {mv.max():.1f} mm). Before -> after: " + E._fmt_m(q["m0"]) + " -> " + E._fmt_m(m1) + ".")
    a0, a1 = q["att0"], q["att1"]
    if a0 and a1:
        txt += " Origin / insertion footprint to the bone (source / before / after, mm): " + "; ".join(f"{b.rsplit('_', 1)[0]} {a1[b]['source_mm']} / {a0[b]['now_mm']} / {a1[b]['now_mm']}" for b in a1 if b in a0) + "."
    if cont:
        txt += f" Gap to {cont['neighbours']} neighbour structure(s) it touches in the Z source: {cont['before_mm']} -> {cont['after_mm']} mm."
    return txt


def refine_shoulder(by, raw, v_q195_hum, side, skin, skin_tree, regions, her, moved_q201, log=print, min_move_mm=2.0, tube_close=(25.0, 25.0, 35.0)):
    """moves the shoulder-zone structures of one side that Q201 left on the Q195 humerus (and are not in `moved_q201`); returns the refine_side report"""
    ch = HumerusDeltaChain(side, by)
    F = ShoulderField(side, by, v_q195_hum, ch.hc)
    s = "_" + side
    zone = {}
    for i, d in by.items():
        if d["cat"] in ("skin", "bone") or not (i.endswith(s) or s + "_" in i) or i in moved_q201:
            continue
        if np.linalg.norm(d["v"].mean(0) - ch.hc) > 260.0:
            continue
        if float(np.linalg.norm(F(d["v"]), axis=1).max()) >= min_move_mm:
            zone[i] = True
    log(f"  Q205 shoulder {side}: {len(zone)} structures follow the humerus")

    def scope(side_, i, raw_i, region, jc, hum_tree, humerus_moved=True):
        return i in zone

    E.SKIN_W, E.ATTACH_W, E.ATTACH_CAP_RUN, E.SEPARATE_MAX_MM, E.SKIN_CAP_MM = 6.0, 3.0, 20.0, 8.0, 20.0
    sh_raw = E.at(raw["humerus" + s], E.bary_samples(raw["humerus" + s], by["humerus" + s]["f"], 3000, seed=4))
    hc_raw = E.sphere_centre(sh_raw[sh_raw[:, 1] > sh_raw[:, 1].max() - 30.0])
    return E.refine_side(side, by, raw, ch, skin, skin_tree, regions=regions, log=log, her=her, label_sides=("l", "r"), scope=scope, extra_centres=[hc_raw], allow_unchanged=True, note_fn=note,
                         tube_close=tube_close, close_rounds=10, arm_radius_mm=800.0, final_skin_clamp=12.0, revert_outside_pp=8.0, field_fn=lambda i, v0: F(v0))
