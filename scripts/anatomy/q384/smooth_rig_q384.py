#!/usr/bin/env python3
"""Q384: re-weight the soft tissue around the hip, knee, shoulder and elbow of a Base page's pose rig and splice it in.

Owner (2026-11-19, hip then knee flexed on Base Male): "distortions appeared. The great saphenous vein is plainly distorted.
Make sure that when a joint's position changes the tissues glide over one another and give a rounder and straighter look";
"the skin looks torn when a joint's state changes. It has to stretch over the tissues."

What was measured first (scratchpad q384/notes.md): 119 of the 250 skin pieces were bound RIGIDLY to one segment next to
per-vertex-skinned neighbours (femoral triangle -> pelvis, popliteal fossa -> femur, anterior arm -> humerus ...), so the skin
parted along piece borders by up to 141 mm (hip), 41 mm (knee), 40 mm (elbow), 263 mm (shoulder); and the weights of vessels
and nerves, taken from the distance to bone samples, placed the transition where two bones happen to be near rather than at
the joint (the great saphenous vein mixed pelvis and femur from 49 to 255 mm below the hip centre) and differed inside one
ring of a vessel, which is the kink.

THIS IS A DISPLAY RULE, NOT ANATOMY. No source says where a vein lies in a flexed limb; the numbers below are conventions of
ours, chosen so that the posed picture is continuous. The pose stays a kinematic preview and the panel says so.

The rule, inside a region around each limb's two big joints (a capsule around hip-knee / shoulder-elbow, full effect within
ROI[0] mm, none beyond ROI[1]); everything outside keeps its stored entry byte for byte:
  * skin, fat, fascia, vessels, nerves, lymph: the share of the DISTAL segment at a joint is a smooth step of the position
    along the limb axis through the joint centre (ZONES, mm), the same function of the rest position for every structure,
    so two vertices at the same place get the same weights. At the hip and the shoulder it is multiplied by a membership mu
    of the limb, harmonic over the welded skin surface between the limb's own skin pieces (1) and the trunk's (0), so the
    limb field ends where the limb does (the perineum and the chest wall do not follow the thigh and the arm): 1 on the
    limb's own pieces and on the pieces over the joint, 0 on the trunk's. The zone is longer for tissue far from the limb
    axis (ZONE_R), because tissue on the inside of a bend folds back on itself when the zone is short. Soft tissue within
    PAT_MM of the patella follows the patella. A vessel or nerve is the limb's when it reaches into the limb.
  * the skin is then one surface: vertices of different pieces that coincide at rest (the border welds of Q334/Q372/Q375)
    are one node, weights are smoothed over the welded surface, each node's weights are stored for all its vertices and
    those vertices are control vertices, so the viewer reconstructs them identically on both pieces.
  * a muscle of the limb follows the same limb field as the skin over it. This costs the attachments inside a blend zone
    (an origin that lies in the zone turns part of the way with the limb instead of staying on its bone); the two other
    rules tried and measured are kept behind Q384_MUSCLE: "axis" (stored attachment weights, only smoothed along the
    muscle: the hamstrings then stay stretched straight from the ischium to the knee and come out through the skin under
    the flexed thigh) and "ends" (stored weights within END_MM of the two ends, the field between).
  * E3: every muscle's placed origin / insertion footprint (data/derived/Q220_parts_z*.json) goes with the bone it is on,
    whole; the muscle's own weights return over PIN_RAMP mm from the footprint. Measured by attach_q384.py.
  * bones, cartilage, joints, ligaments: untouched (rigid as before).
The rig gets `blend:"dq"`: the viewer then blends the segments' motions as dual quaternions (viewer/pose/pose.js skinDQ), a
rotation part way about the joint instead of a straight line between two rotated copies, so a tube keeps its width in a bend.

    python3 scripts/anatomy/q384/smooth_rig_q384.py base_m base_f [--src DIR_OR_FILE] [--out DIR] [--dry-run]
`--src`: the rig to start from (default data/anatomy/pose_rig_<key>.json; a rig that already carries `q384` is refused: start
from the rig before this round). `--out`: where to write (default data/anatomy)."""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import zlib
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix, diags
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q241")); sys.path.insert(0, str(HERE.parent / "q338")); sys.path.insert(0, str(HERE))
import make_pose_rig as MK  # noqa: E402
from splice_rig_q338 import entries  # noqa: E402

DATA = REPO / "data/anatomy"
# conventions of ours (mm along the limb axis from the joint centre, proximal negative): where the distal segment takes over
ZONES = {"hip": (-40.0, 90.0), "knee": (-60.0, 60.0), "shoulder": (-30.0, 70.0), "elbow": (-55.0, 55.0)}
ROI = {"leg": (200.0, 260.0), "arm": (170.0, 230.0)}
ZONE_R, ZONE_RMAX = 0.8, 80.0      # the zone is longer for tissue far from the limb axis: each end moves out by ZONE_R x (distance from the axis, at most ZONE_RMAX)
ZONE_IN = 1.6                       # and, on the side the joint folds towards, the PROXIMAL end moves out further by ZONE_IN x (offset to that side): the tissue above a crease starts to turn early (it bulges), the tissue below stays on its bones
PAT_MM = 12.0
FIELD_SYS = ("skin", "fat", "fascia", "vessel", "nerve", "lymph")
AXIS_SYS = ("muscle",)
MUSCLE_SHARE = 0.5                  # a muscle is the limb's when at least this share of its vertices is stored with the limb's own segments
AXIS_SIGMA, AXIS_RATIO = 30.0, 2.5
LIMB_R = {"leg": (120.0, 170.0), "arm": (60.0, 85.0)}      # deep tissue is the limb's within this distance of the limb axis (full, none): the chest wall beside the arm is not the arm
import os as _os
MUSCLE_MODE = _os.environ.get("Q384_MUSCLE", "field")      # field | ends | axis (how a muscle follows; see run())
PIN_RAMP = float(__import__("os").environ.get("Q384_PIN_RAMP", 20.0))      # (15 and 25 were measured too: the footprints hold either way, the biceps' turn next to its radial insertion at 120 degrees of elbow flexion goes from +78 to +63 / +70 degrees, the rectus femoris' changes side; 40 kept)                     # E3: a muscle's placed footprint on a bone goes with that bone exactly; over the next PIN_RAMP mm the muscle's own weights take over
END_MM = 60.0                       # a muscle keeps its stored (attachment) weights at its two ends and follows the limb field beyond END_MM from them
SMOOTH_ITERS, SMOOTH_ALPHA = 4, 0.5      # 12 held the medial thigh skin back at the perineum for 30-40 mm while the adductors under it went with the thigh
REFINE = 0.02
EPS_WELD = 0.05
DISTAL_FINE = re.compile(r"^(hand|foot|th_\w+|f\d_\w|t\d_\w)_[lr]$")
LEG_W = re.compile(r"(thigh|knee|popliteal|(?<!fore)_leg|ankle|malleol|foot|heel|sole|hallucial|metatarsal)")
ARM_W = re.compile(r"(arm|elbow|cubital|wrist|palm|hand|radial_foveola)")
JUNC = {"leg": re.compile(r"(hip|gluteal|inguinal|femoral_triangle)"), "arm": re.compile(r"(deltoid|deltopectoral|bicipital)")}


def sstep(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def unit(a):
    return a / max(np.linalg.norm(a), 1e-12)


class Limb:
    def __init__(self, rig, kind, side):
        J = {j["id"]: j for j in rig["joints"]}
        names = [s[0] for s in rig["segs"]]; par = [s[1] for s in rig["segs"]]
        a, b, c = ("hip", "knee", "ankle") if kind == "leg" else ("shoulder", "elbow", "wrist")
        self.kind, self.side, self.ja, self.jb = kind, side, a, b
        self.ca, self.cb, self.cc = (np.array(J["%s_%s" % (n, side)]["c"], float) for n in (a, b, c))
        self.ax_a = unit(self.cb - self.ca)
        self.ax_b = unit(unit(self.cb - self.ca) + unit(self.cc - self.cb))
        self.mid = names.index(("fem_" if kind == "leg" else "hum_") + side)
        self.dist = names.index(("tib_" if kind == "leg" else "uln_") + side)
        self.pat = names.index("pat_" + side) if kind == "leg" else -1
        self.prox = par[self.mid]
        # the side each joint folds towards (a point on the distal segment moves that way when the joint flexes): flexion axis x limb axis
        fa = [d["a"] for d in J["%s_%s" % (a, side)]["dof"] if d["k"] == "flex"] if kind == "leg" else []
        self.in_a = unit(np.cross(fa[0], self.ax_a)) if fa else None
        fb = [d["a"] for d in J["%s_%s" % (b, side)]["dof"] if d["k"] == "flex"]
        self.in_b = unit(np.cross(fb[0], self.ax_b)) if fb else None

        def sub(root):
            out = {root}; grew = True
            while grew:
                grew = False
                for i, p in enumerate(par):
                    if p in out and i not in out:
                        out.add(i); grew = True
            return np.array(sorted(out))
        self.sub_mid, self.sub_dist = sub(self.mid), sub(self.dist)

    def roi(self, x):
        ab = self.cb - self.ca
        t = np.clip((x - self.ca) @ ab / (ab @ ab), 0, 1)
        d = np.linalg.norm(x - (self.ca + t[:, None] * ab), axis=1)
        r0, r1 = ROI[self.kind]
        return 1.0 - sstep((d - r0) / (r1 - r0))

    @staticmethod
    def _step(x, c, ax, zone, inside=None):
        """Tissue on the inside of a bend, r mm from the axis, folds back on itself when the joint turns by more than
        (zone length) / (1.5 r) radians: the great saphenous vein lies 55 mm in front of the hip centre, and a 130 mm zone
        folds it at exactly 90 degrees. So the zone grows with the distance from the limb axis."""
        d = x - c; s = d @ ax
        r = np.minimum(np.linalg.norm(d - np.outer(s, ax), axis=1), ZONE_RMAX) * ZONE_R
        rin = np.clip(d @ inside, 0.0, ZONE_RMAX) * ZONE_IN if inside is not None else 0.0
        return sstep((s - (zone[0] - r - rin)) / (zone[1] - zone[0] + 2 * r + rin))

    def member(self, x):
        """1 inside the limb, 0 away from it: distance from the limb's own axis, the two straight pieces joint centre to joint
        centre (hip-knee-ankle, shoulder-elbow-wrist). Measured from the upper piece's line alone, the forearm -- which
        does not continue the humerus -- counted as "away" and its muscles were left hanging from the trunk."""
        def seg(a, b):
            ab = b - a; t = np.clip((x - a) @ ab / (ab @ ab), 0, 1)
            return np.linalg.norm(x - (a + t[:, None] * ab), axis=1)
        r = np.minimum(seg(self.ca, self.cb), seg(self.cb, self.cc))
        r0, r1 = LIMB_R[self.kind]
        return 1.0 - sstep((r - r0) / (r1 - r0))

    def t_a(self, x):
        return self._step(x, self.ca, self.ax_a, ZONES[self.ja], self.in_a)

    def t_b(self, x):
        return self._step(x, self.cb, self.ax_b, ZONES[self.jb], self.in_b)


def dense_of(e, nv, nseg, blob_decode):
    """stored entry -> (nv, nseg) float weights as the viewer reconstructs them"""
    D = np.zeros((nv, nseg), np.float32)
    if e[0] == "rigid":
        D[:, e[1]] = 1.0
        return D
    sg, w = blob_decode
    for k in range(sg.shape[1]):
        np.add.at(D, (np.arange(nv), sg[:, k]), w[:, k])
    return D


def decode_entry(e, v):
    i, nv, K, pal, _, nc = e[1]
    b = np.frombuffer(e[2], np.uint8); mb = (nv + 7) >> 3
    ctrl = np.unpackbits(b[:mb])[:nv].astype(bool); p = mb
    ci = np.stack([b[p + k * nc: p + (k + 1) * nc] for k in range(K)], 1).astype(np.int64); p += K * nc
    cw = np.zeros((nc, K))
    for k in range(1, K):
        cw[:, k] = b[p + (k - 1) * nc: p + k * nc]
    cw[:, 0] = 255 - cw[:, 1:].sum(1)
    return MK.decode_weights(v, ctrl, pal, ci, cw)


def quant(D):
    """dense weights -> the same rows as the viewer can hold them: 3 largest, /255, summing to exactly 1"""
    top = np.argsort(-D, axis=1, kind="stable")[:, :3]
    tw = np.take_along_axis(D, top, 1).astype(np.float64)
    tw = tw / np.maximum(tw.sum(1, keepdims=True), 1e-9)
    q = np.round(tw * 255).astype(np.int32)
    q[:, 0] += 255 - q.sum(1)
    q = np.clip(q, 0, 255)
    out = np.zeros(D.shape, np.float32)
    np.put_along_axis(out, top, (q / 255.0).astype(np.float32), 1)
    return out


def encode(v, Dq, force_ctrl=None):
    """quantised dense weights -> ('rigid', seg) | ('skin', [None, nv, K, pal, None, nc], bytes)"""
    nv = len(v)
    used = np.where(Dq.max(0) > 0)[0]
    if len(used) == 1:
        return ("rigid", int(used[0]))
    ctrl = MK.control_set(Dq)
    if force_ctrl is not None:
        ctrl = ctrl | force_ctrl
    old = MK.REFINE_ERR
    MK.REFINE_ERR = REFINE
    try:
        ctrl = MK.refine_controls(v, Dq, ctrl)
    finally:
        MK.REFINE_ERR = old
    cv = np.where(ctrl)[0]
    Wc = Dq[cv]
    top = np.argsort(-Wc, axis=1, kind="stable")[:, :3]
    q = np.round(np.take_along_axis(Wc, top, 1).astype(np.float64) * 255).astype(np.int32)
    q[:, 0] += 255 - q.sum(1)
    pal = sorted(int(s) for s in np.unique(top[q > 0]))
    pm = {s: n for n, s in enumerate(pal)}
    K = max(1, int((q > 0).any(0).nonzero()[0].max() + 1))
    pi = np.zeros((len(cv), K), np.uint8)
    for k in range(K):
        pi[:, k] = [pm.get(int(s), 0) for s in top[:, k]]
        if k:
            pi[q[:, k] == 0, k] = pi[q[:, k] == 0, 0]
    b = np.packbits(ctrl).tobytes() + b"".join([pi[:, k].tobytes() for k in range(K)] + [q[:, k].astype(np.uint8).tobytes() for k in range(1, K)])
    return ("skin", [None, nv, K, pal, None, int(len(cv))], b)


def restrict(E, cols, default):
    """rows of E restricted to `cols`, renormalised; rows with (almost) no mass there become one-hot `default` -> (dist (n, nseg), mass (n,))"""
    out = np.zeros_like(E)
    out[:, cols] = E[:, cols]
    m = out.sum(1)
    ok = m >= 0.02
    out[ok] /= m[ok, None]
    out[~ok] = 0.0
    out[~ok, default] = 1.0
    return out, m


def apply_field(L, x, E, mu, donor=None):
    """the limb rule at rest positions x for stored weights E -> new weights (before the ROI blend)"""
    nseg = E.shape[1]
    rest = np.setdiff1d(np.arange(nseg), L.sub_mid)
    P, _ = restrict(E, rest, L.prox)
    Dd, md = restrict(E, L.sub_dist, L.dist)
    if donor is not None:                       # a vertex with no distal weights of its own takes the distribution of the nearest one that has
        need = md < 0.25
        if need.any() and donor[0] is not None:
            _, nn = donor[0].query(x[need])
            Dd[need] = donor[1][nn]
    H = mu * L.t_a(x)
    tb = L.t_b(x)
    q = np.zeros(len(x))
    if L.pat >= 0 and L.pat_tree is not None:
        d, _ = L.pat_tree.query(x, distance_upper_bound=4 * PAT_MM)
        q = np.where(np.isfinite(d), np.exp(-(d / PAT_MM) ** 2), 0.0)
    N = (1.0 - H)[:, None] * P + (H * (1 - q) * tb)[:, None] * Dd
    N[:, L.mid] += H * (1 - q) * (1 - tb)
    if L.pat >= 0:
        N[:, L.pat] += H * q
    return N


def run(key, src=None, out_dir=None, dry=False, verbose=True):
    import model as MD
    f = Path(src) if src else DATA / ("pose_rig_%s.json" % key)
    if f.is_dir():
        f = f / ("pose_rig_%s.json" % key)
    S0 = json.loads(f.read_text(encoding="utf-8"))
    old = S0["rig"]
    if old.get("q384"):
        raise SystemExit("%s already carries the Q384 weights: start from the rig before this round (--src)" % f)
    blob = zlib.decompress(base64.b64decode(S0["weights_zlib_b64"]))
    M = MD.Model(key)
    S = M.S
    if [len(x["v"]) for x in S] != old["nv"]:
        raise SystemExit("%s: the page geometry differs from the rig's" % key)
    nseg = len(old["segs"]); names = [s[0] for s in old["segs"]]
    eo = entries(old, blob)
    V = {x["idx"]: np.asarray(x["v"], float) for x in S}
    limbs = [Limb(old, k, s) for k in ("leg", "arm") for s in ("l", "r")]
    for L in limbs:
        L.pat_tree = None
        if L.pat >= 0:
            pv = [V[i] for g in old["rigid"] if g[0] == L.pat for i in g[1] if S[i]["sys"] == "bone"]
            L.pat_tree = cKDTree(np.vstack(pv)) if pv else None
    fine = np.array([bool(DISTAL_FINE.match(n)) for n in names])

    def in_roi(v):
        return np.max([L.roi(v) for L in limbs], axis=0)

    cache = {}

    def E_of(i):
        if i not in cache:
            e = eo[i]
            cache[i] = dense_of(e, len(V[i]), nseg, None if e[0] == "rigid" else decode_entry(e, V[i]))
        return cache[i]

    new = {}                                     # structure idx -> quantised dense weights
    # ---------------------------------------------------------------- the skin: one welded surface
    skin = [x for x in S if x["sys"] == "skin"]
    off = np.cumsum([0] + [len(x["v"]) for x in skin]); nvs = int(off[-1])
    X = np.vstack([V[x["idx"]] for x in skin]); own = np.repeat(np.arange(len(skin)), [len(x["v"]) for x in skin])
    pr = cKDTree(X).query_pairs(EPS_WELD, output_type="ndarray")
    from scipy.sparse.csgraph import connected_components
    nn, node = connected_components(coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(nvs, nvs)), directed=False)
    cnt = np.bincount(node, minlength=nn)
    Pm = csr_matrix((1.0 / cnt[node], (node, np.arange(nvs))), shape=(nn, nvs))           # vertex -> node mean
    ed = []
    for k, x in enumerate(skin):
        fc = np.asarray(x["f"], int) + off[k]
        ed.append(np.vstack([fc[:, [0, 1]], fc[:, [1, 2]], fc[:, [2, 0]]]))
    ed = node[np.vstack(ed)]; ed = ed[ed[:, 0] != ed[:, 1]]
    A = coo_matrix((np.ones(2 * len(ed)), (np.r_[ed[:, 0], ed[:, 1]], np.r_[ed[:, 1], ed[:, 0]])), shape=(nn, nn)).tocsr()
    A.data[:] = 1.0
    deg = np.asarray(A.sum(1)).ravel(); deg[deg == 0] = 1.0
    An = diags(1.0 / deg) @ A
    Xn = Pm @ X
    Esk = np.vstack([E_of(x["idx"]) for x in skin]).astype(np.float64)
    ids = [x["id"].lower() for x in skin]
    side = np.array([i[-1] if i.endswith(("_l", "_r")) else "m" for i in ids])
    cx = np.array([V[x["idx"]][:, 0].mean() for x in skin])
    tree_skin = cKDTree(X)
    MU = {}
    for L in limbs:
        # Dirichlet values per piece: this limb's own pieces 1, its junction pieces free (nan), every other piece 0
        val = np.zeros(len(skin))
        for k, i in enumerate(ids):
            if side[k] != L.side:
                continue
            if JUNC[L.kind].search(i):
                val[k] = 1.0          # the pieces over the joint itself belong to the limb: where they follow it is the zone's business
            elif MK.SK.skin_kind(skin[k]) == "limb":
                leg = bool(LEG_W.search(i)) or (not ARM_W.search(i) and abs(cx[k]) < 200)
                val[k] = 1.0 if (leg == (L.kind == "leg")) else 0.0
        vv = val[own]
        fixed_n = np.asarray(Pm @ np.isfinite(vv).astype(float)).ravel() > 0        # a node touched by any fixed piece is fixed at their mean
        s_ = np.asarray((Pm.multiply(cnt[:, None])) @ np.nan_to_num(vv)).ravel(); c_ = np.asarray((Pm.multiply(cnt[:, None])) @ np.isfinite(vv).astype(float)).ravel()
        mu = np.where(fixed_n, s_ / np.maximum(c_, 1), 0.0)
        free = ~fixed_n
        if free.any():
            Lp = diags(np.asarray(A.sum(1)).ravel()) - A
            rhs = -(Lp[free][:, fixed_n] @ mu[fixed_n])
            Lff = Lp[free][:, free] + diags(np.full(int(free.sum()), 1e-9))
            mu[free] = np.clip(spsolve(Lff.tocsc(), rhs), 0, 1)
        MU[(L.kind, L.side)] = mu
        rho = L.roi(X)
        act = rho > 0
        if not act.any():
            continue
        dm = Esk[:, L.sub_dist].sum(1)
        don = np.where(dm >= 0.9)[0]
        dd = Esk[don][:, :].copy(); keep = np.zeros(nseg, bool); keep[L.sub_dist] = True; dd[:, ~keep] = 0; dd /= np.maximum(dd.sum(1, keepdims=True), 1e-9)
        donor = (cKDTree(X[don]), dd) if len(don) else (None, None)
        N = apply_field(L, X[act], Esk[act], mu[node[act]], donor)
        Esk[act] = rho[act, None] * N + (1 - rho[act, None]) * Esk[act]
        L.mu_skin = mu[node]
    rho_v = in_roi(X)
    lock = Esk[:, fine].sum(1) >= 0.25           # the hand and the foot keep the weights of Q338 (a strip of forearm skin that carries 3% "hand" up to the elbow is not the hand)
    lam = np.minimum(1.0, rho_v / 0.2) * (~lock)
    lam_n = np.asarray(Pm @ lam).ravel()
    lam_n[np.asarray(Pm @ lock.astype(float)).ravel() > 0] = 0.0
    Wn = Pm @ Esk
    for _ in range(SMOOTH_ITERS):
        Wn = (1 - SMOOTH_ALPHA * lam_n)[:, None] * Wn + (SMOOTH_ALPHA * lam_n)[:, None] * (An @ Wn)
    Wq = quant(np.asarray(Wn, np.float32))
    lv = lam_n[node]
    En = np.asarray(Pm @ Esk)[node]              # where the rule fades out, the part that stays is the node's mean too: a border pair is one weight everywhere inside the region
    final = np.where((lv > 0)[:, None], lv[:, None] * Wq[node] + (1 - lv[:, None]) * En, Esk)
    border = cnt[node] > 1
    for k, x in enumerate(skin):
        sl = slice(off[k], off[k + 1])
        if not (lv[sl] > 0).any():
            continue
        new[x["idx"]] = (quant(final[sl].astype(np.float32)), border[sl] & (lv[sl] > 0))
    # ---------------------------------------------------------------- deep soft tissue that follows the limb field
    n_field = n_axis = 0
    for x in S:
        i = x["idx"]
        if x["sys"] == "skin" or x["sys"] not in FIELD_SYS + AXIS_SYS:
            continue
        v = V[i]
        rr = [L.roi(v) for L in limbs]
        if max(r.max() for r in rr) <= 0:
            continue
        E = E_of(i).astype(np.float64)
        if x["sys"] in FIELD_SYS:
            W = E.copy(); touched = False
            for L, rho in zip(limbs, rr):
                if rho.max() <= 0 or (E[:, L.sub_mid].sum(1) >= 0.5).mean() < 0.05:
                    continue
                # a deep structure that reaches into the limb is the limb's all along: taking the membership from the nearest
                # skin failed (the great saphenous vein runs 3 mm from the scrotal skin, which is the trunk's)
                mu = L.member(v)
                dm = W[:, L.sub_dist].sum(1); don = np.where(dm >= 0.5)[0]
                donor = (None, None)
                if len(don):
                    dd = W[don].copy(); keep = np.zeros(nseg, bool); keep[L.sub_dist] = True; dd[:, ~keep] = 0; dd /= np.maximum(dd.sum(1, keepdims=True), 1e-9)
                    donor = (cKDTree(v[don]), dd)
                N = apply_field(L, v, W, mu, donor)
                W = rho[:, None] * N + (1 - rho[:, None]) * W
                touched = True
            if not touched:
                continue
            n_field += 1
        else:
            # A muscle follows the same limb field as the skin over it. Left on its stored bone-distance weights it stayed
            # stretched straight from origin to insertion: the hamstrings came out through the skin under the flexed thigh.
            # MUSCLE_MODE "ends" keeps the stored (attachment) weights within END_MM of the muscle's two ends, "axis" only
            # smooths the stored weights along the muscle (the first version of this round).
            c = v.mean(0); u, s_, vt = np.linalg.svd(v - c, full_matrices=False)
            t = (v - c) @ vt[0]
            # ... a muscle OF THE LIMB: with the 5% that admits a vessel, the latissimus and the pectoralis major (trunk muscles
            # that only insert on the humerus) swung out with the abducted arm like a wing. Those keep their stored entry.
            gated = [(L, r_) for L, r_ in zip(limbs, rr) if r_.max() > 0 and (E[:, L.sub_mid].sum(1) >= 0.5).mean() >= MUSCLE_SHARE]
            if not gated:
                continue
            W = E.copy()
            if MUSCLE_MODE in ("ends", "axis") and s_[0] >= AXIS_RATIO * s_[1]:
                o = np.argsort(t); ts = t[o]
                lo = np.searchsorted(ts, t - 3 * AXIS_SIGMA); hi = np.searchsorted(ts, t + 3 * AXIS_SIGMA)
                Eo = E[o]
                for n_ in range(len(v)):
                    kk = np.exp(-0.5 * ((ts[lo[n_]:hi[n_]] - t[n_]) / AXIS_SIGMA) ** 2)
                    W[n_] = kk @ Eo[lo[n_]:hi[n_]] / kk.sum()
            if MUSCLE_MODE != "axis":
                F = W.copy()
                for L, rho_l in gated:
                    dm = F[:, L.sub_dist].sum(1); don = np.where(dm >= 0.5)[0]
                    donor = (None, None)
                    if len(don):
                        dd = F[don].copy(); keep = np.zeros(nseg, bool); keep[L.sub_dist] = True; dd[:, ~keep] = 0; dd /= np.maximum(dd.sum(1, keepdims=True), 1e-9)
                        donor = (cKDTree(v[don]), dd)
                    N = apply_field(L, v, F, L.member(v), donor)
                    F = rho_l[:, None] * N + (1 - rho_l[:, None]) * F
                if MUSCLE_MODE == "ends":
                    ends = sstep(np.minimum(t - t.min(), t.max() - t) / END_MM)
                    W = ends[:, None] * F + (1 - ends[:, None]) * W
                else:
                    W = F
            rho = np.max(rr, axis=0) * (E[:, fine].sum(1) < 0.25)
            W = rho[:, None] * W + (1 - rho[:, None]) * E
            n_axis += 1
        new[i] = (quant(W.astype(np.float32)), None)
    # ---------------------------------------------------------------- E3: origins and insertions stay on their bones
    # Owner, 2026-11-22: "latissimus dorsi loses its hold when the hand is abducted -- make sure origin + insertion are always
    # kept." Measured (attach_q384.py, Base Male): before this round 38 of 488 placed bony ends came more than 5 mm off their
    # bone in some pose (deltoid origin 24 mm, latissimus insertion 9 mm); with the limb field above and nothing else, 89 did
    # (the hamstrings' origins left the ischium by 82 mm at 90 degrees of hip flexion). So: the vertices of a muscle within
    # the footprint radius of one of its placed sites that touch the bone (attach_q384.py) take the segment of that bone, whole;
    # from those vertices the muscle's own weights return over PIN_RAMP mm. The sites are this project's placed sites (data/derived/Q220_parts_z*.json),
    # not new anatomy. Hands and feet keep the weights of Q338.
    import attach_q384 as AT
    n_pin = 0
    by_m = {}
    for st_ in AT.sites(key, S, old):
        if not fine[st_["seg"]]:
            by_m.setdefault(st_["muscle"], []).append(st_)
    for mi, lst in by_m.items():
        v = V[mi]
        Wm = (new[mi][0] if mi in new else quant(E_of(mi))).astype(np.float64)
        # distance from the footprint itself (the vertices that touch the bone), not from its centre: a sphere of the footprint
        # radius took the whole thickness of the muscle's end with it, and with the 40 mm ramp the nearest 70 mm of the biceps
        # and triceps stayed with the scapula, outside the skin of the raised arm
        es = np.stack([1.0 - sstep(cKDTree(v[st_["verts"]]).query(v)[0] / PIN_RAMP) for st_ in lst], 1)
        keep = np.prod(1.0 - es, axis=1)
        if (keep < 1).sum() == 0:
            continue
        share = es / np.maximum(es.sum(1, keepdims=True), 1e-12) * (1.0 - keep)[:, None]
        Wp = keep[:, None] * Wm
        for k_, st_ in enumerate(lst):
            Wp[:, st_["seg"]] += share[:, k_]
        new[mi] = (quant(Wp.astype(np.float32)), None)
        n_pin += 1
    # ---------------------------------------------------------------- splice
    rigid, skin_l, chunks, o_ = {}, [], [], 0
    changed = 0
    for i in range(old["count"]):
        e = eo[i]
        if i in new:
            Dq, force = new[i]
            # a skin piece with border vertices in the region is re-encoded on ANY difference: left on its old entry because it
            # "did not change" (within half a step of 1/255), its border vertex and the partner's differed by that step -- 1.3 mm
            if np.abs(Dq - quant(E_of(i))).max() > (1e-6 if force is not None and force.any() else 0.5 / 255):
                e = encode(V[i], Dq, force)
                changed += 1
        if e[0] == "rigid":
            rigid.setdefault(e[1], []).append(i)
        else:
            _, nv, K, pal, _, nc = e[1]
            skin_l.append([i, nv, K, pal, o_, nc]); chunks.append(e[2]); o_ += len(e[2])
    payload = dict(old)
    payload["rigid"] = [[s, v] for s, v in sorted(rigid.items())]
    payload["skin"] = skin_l
    payload["blend"] = "dq"
    payload["q384"] = dict(muscles=MUSCLE_MODE, pinned_muscles=n_pin, pin_ramp=PIN_RAMP, zones=ZONES, zone_r=[ZONE_R, ZONE_RMAX], zone_in=ZONE_IN, roi=ROI, pat_mm=PAT_MM, changed=changed,
                           note="display rule, not anatomy: limb-axis blend zones and their widths are conventions (scripts/anatomy/q384/smooth_rig_q384.py)")
    payload["notes"] = re.sub(r"\d+ skinned structures", "%d skinned structures" % len(skin_l), old["notes"]) + \
        "; Q384: soft tissue around hip, knee, shoulder and elbow re-weighted (%d structures; limb-axis blend zones = display convention), dual-quaternion blend" % changed
    nb = b"".join(chunks)
    p, nj, nw = MK.pack(payload, nb)
    if verbose:
        print("%s: skin pieces %d (welded nodes %d of %d vertices), field structures %d, muscles re-weighted (%s) %d, with pinned attachment sites %d; re-encoded %d; skinned %d -> %d, rigid %d -> %d; weights %.0f -> %.0f KB zlib" % (
            key, len(skin), nn, nvs, n_field, MUSCLE_MODE, n_axis, n_pin, changed, len(old["skin"]), len(skin_l), sum(len(g[1]) for g in old["rigid"]), sum(len(g[1]) for g in payload["rigid"]),
            len(S0["weights_zlib_b64"]) * 0.75 / 1024, nw / 1024), flush=True)
    if not dry:
        od = Path(out_dir) if out_dir else DATA
        od.mkdir(parents=True, exist_ok=True)
        g = od / ("pose_rig_%s.json" % key)
        g.write_text(json.dumps(dict(schema=S0["schema"], key=key, label=S0["label"], rig=payload, weights_zlib_b64=p["w"]), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print("wrote", g, flush=True)
    return payload


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("keys", nargs="+", choices=["base_m", "base_f"])
    ap.add_argument("--src"); ap.add_argument("--out"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    for k in a.keys:
        run(k, a.src, a.out, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
