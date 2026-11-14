"""Q284 moment arms from THIS body's geometry: muscle path from the muscle's own mesh, segments from the Q241 pose rig, tendon-excursion
moment arms (r = -dL/dq) through the rig's own forward kinematics (scripts/anatomy/q241/fk.py, the maths the viewer runs).

Path of one muscle (all from the page's own meshes, nothing assumed per muscle):
  * centre line: an iterated principal curve of the muscle's mesh vertices (bin the vertices along the current curve, take the bin
    centroids, smooth, repeat) -- it follows the belly where the mesh bends, e.g. iliopsoas over the pelvic brim;
  * bone contact per centre-line bin: the muscle's own vertices lie within CONTACT_MM of a bone (an attachment or a pulley on this body);
  * ends: the centroid of the contacts in the outermost END_FRACS of the curve (the attachment), else the curve's own end ('free end');
  * a point is fixed to the rig segment of the bone it touches, or -- when it touches none -- of its nearest bone if that bone is within
    FIX_MM (the muscle lies on it); points farther from every bone are carried by other soft tissue, not by a bone, and are dropped;
  * at every joint the path crosses, points over the articular region slide: within ZONE of the joint centre every point except the
    path's own ends is dropped (contacts there are sliding contacts, e.g. iliopsoas on the femoral head); between ZONE and 2 x ZONE the
    free points are dropped and the walk stops at the first bone contact (a pulley, e.g. the iliopectineal eminence);
  * the dropped points set one wrap sphere per crossed joint: centre = the joint centre, radius = their closest approach to it (where
    THIS muscle sits over THIS joint at rest). The span across the joint is the shortest path around that sphere (straight when it
    clears it): the obstacle-set method (Garner and Pandy 2000) with a measured, not assumed, radius.
Moment arm about a degree of freedom q: r = -dL/dq (L = path length; central difference of +-H_DEG through the rig's FK; mm per rad).
r > 0: shortening the muscle drives q in its positive direction (rom.py: hip flexion / abduction / internal rotation +, ...).
Only the joint of interest moves; every other joint stays at its rest value (the pose the meshes were built in)."""
from __future__ import annotations
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q241"))
from fk import fk, default_pose  # noqa: E402
from geom import pca, unit  # noqa: E402

CONTACT_MM = 3.0
FIX_MM = 20.0
END_FRACS = (0.08, 0.18)
N_BINS = 24
ITERS = 14
H_DEG = 1.0

# articular region of each joint (mm, order of magnitude); forearm rotation has none (its axis runs along the whole forearm)
ZONE = {"hip": 40.0, "shoulder": 40.0, "knee": 45.0, "elbow": 30.0, "ankle": 30.0, "subtalar": 30.0, "wrist": 20.0,
        "thumb_cmc": 12.0, "thumb_mcp": 10.0, "thumb_ip": 8.0, "forearm": 0.0}


def zone_of(jid):
    base = re.sub(r"_(r|l)$", "", jid)
    if base in ZONE:
        return ZONE[base]
    if re.match(r"f\d_mcp$", base) or re.match(r"t\d_mtp$", base):
        return 10.0
    if re.match(r"[ft]\d_(pip|dip|ip)$", base):
        return 7.0
    return 0.0


# ---------------------------------------------------------------- centre line
def principal_curve(v, n=N_BINS, iters=ITERS):
    """ordered centre line (n, 3) through the point cloud v"""
    c, w, V = pca(v)
    u = V[:, 0]
    t = (v - c) @ u
    lo, hi = np.percentile(t, 1), np.percentile(t, 99)
    P = c + np.outer(np.linspace(lo, hi, n), u)
    for _ in range(iters):
        tp = project(v, P)
        edges = np.linspace(0, 1, n + 1)
        Q = []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (tp >= a) & (tp < b) if b < 1 else (tp >= a)
            if m.sum() >= 3:
                Q.append(v[m].mean(0))
        Q = np.array(Q)
        if len(Q) < 4:
            break
        S = Q.copy()
        S[1:-1] = 0.25 * Q[:-2] + 0.5 * Q[1:-1] + 0.25 * Q[2:]
        P = resample(S, n)
    return P


def resample(P, n):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    if d[-1] <= 0:
        return np.repeat(P[:1], n, 0)
    s = np.linspace(0, d[-1], n)
    return np.c_[[np.interp(s, d, P[:, k]) for k in range(3)]].T


def project(v, P):
    """arc-length parameter in [0, 1] of the nearest point of polyline P, for each row of v"""
    seg = P[1:] - P[:-1]
    L = np.linalg.norm(seg, axis=1)
    cum = np.r_[0, np.cumsum(L)]
    best_d = np.full(len(v), np.inf)
    best_t = np.zeros(len(v))
    for i in range(len(seg)):
        if L[i] <= 0:
            continue
        a = np.clip(((v - P[i]) @ seg[i]) / (L[i] ** 2), 0, 1)
        q = P[i] + np.outer(a, seg[i])
        d = np.einsum("ij,ij->i", v - q, v - q)
        m = d < best_d
        best_d[m] = d[m]
        best_t[m] = cum[i] + a[m] * L[i]
    return best_t / max(cum[-1], 1e-9)


# ---------------------------------------------------------------- bones
class Bones:
    """KD-tree over every bone vertex of the page, labelled with its rig segment index"""

    def __init__(self, K, RB):
        from scipy.spatial import cKDTree
        pts, lab, keys = [], [], []
        thor = RB.sid["v" + RB._thorax_vert()]
        self.approx = set()
        for k, b in K.B.items():
            sname = RB.bone_seg.get(k)
            if sname is None and k in RB.soft_bones:          # ribs: skinned between segments in the viewer
                m = re.match(r"rib_(\d+)_[lr]$", k)
                nm = ("vT%d" % int(m.group(1))) if m else None
                if nm in RB.sid:
                    si = RB.sid[nm]
                else:
                    si = thor
                    self.approx.add(len(keys))
            elif sname is None:
                continue
            else:
                si = RB.sid[sname]
            pts.append(b["v"]); lab.append(np.full(len(b["v"]), si)); keys.append(k)
        self.v = np.vstack(pts)
        self.seg = np.concatenate(lab)
        self.bone = np.concatenate([np.full(len(p), i) for i, p in enumerate(pts)])
        self.keys = keys
        self.tree = cKDTree(self.v)

    def query(self, p):
        d, i = self.tree.query(p)
        return d, self.seg[i], self.bone[i]


def majority(s, w=2):
    s = np.asarray(s)
    out = s.copy()
    for i in range(1, len(s) - 1):
        win = s[max(0, i - w): i + w + 1]
        vals, cnt = np.unique(win, return_counts=True)
        out[i] = vals[np.argmax(cnt)]
    return out


# ---------------------------------------------------------------- path
def raw_path(v, bones: Bones):
    """centre line + attachments + per-point segment / contact / fixable flags, before any joint is considered"""
    P = principal_curve(v)
    d_v, s_v, b_v = bones.query(v)
    t = project(v, P)
    flags, ends = [], []
    n = len(P)
    bin_of = np.minimum((t * n).astype(int), n - 1)
    contact = np.zeros(n, bool)
    cseg = np.full(n, -1)
    for i in range(n):
        m = bin_of == i
        c = m & (d_v <= CONTACT_MM)
        if c.sum() >= max(5, 0.02 * m.sum()):
            vals, cnt = np.unique(s_v[c], return_counts=True)
            contact[i] = True
            cseg[i] = int(vals[np.argmax(cnt)])
    pts, con, cs = list(P), list(contact), list(cseg)
    for which in ("start", "end"):
        hit = None
        for f in END_FRACS:
            m = (t <= f) if which == "start" else (t >= 1 - f)
            c = m & (d_v <= CONTACT_MM)
            if c.sum() >= 5:
                hit = c
                break
        if hit is None:
            ends.append(("free", None, 0))
            continue
        q = v[hit].mean(0)
        vals, cnt = np.unique(s_v[hit], return_counts=True)
        s = int(vals[np.argmax(cnt)])
        ends.append(("bone", s, int(hit.sum())))
        tq = project(q[None, :], P)[0]
        if which == "start":
            if tq <= 0.02:
                pts.insert(0, q); con.insert(0, True); cs.insert(0, s)
            else:
                con[0] = True; cs[0] = s
        else:
            if tq >= 0.98:
                pts.append(q); con.append(True); cs.append(s)
            else:
                con[-1] = True; cs[-1] = s
    p = np.array(pts)
    con = np.array(con, bool)
    cs = np.array(cs)
    d_p, s_p, b_p = bones.query(p)
    s_p = s_p.copy()
    s_p[con] = cs[con]
    s_p = majority(s_p)
    s_p[con] = cs[con]
    fixable = con | (d_p <= FIX_MM)
    fixable[0] = fixable[-1] = True
    if any(b in bones.approx for b in b_p[con]):
        flags.append("rib attachment approximated (merged rib mesh -> thorax segment)")
    return dict(p=p, seg=s_p.astype(int), contact=con, fixable=fixable, ends=ends, dist=d_p, flags=flags)


def joint_side(rig, jid):
    """segments on the moving side of joint jid; the knee also moves the patella (coupled), so a path on femur + patella crosses it"""
    j = next(x for x in rig["joints"] if x["id"] == jid)
    S = subtree(rig, j["seg"])
    for k in rig["joints"]:
        d = k["dof"][0].get("drv") if k.get("driven") else None
        if d and d.get("src") == jid and not jid.startswith("shoulder"):
            S |= subtree(rig, k["seg"])
    return S


def muscle_path(v, bones: Bones, rig=None):
    """-> dict(p, seg, contact, ends, flags, wraps={jid: dict(c, R, par)}, dropped) -- see the module header"""
    R = raw_path(v, bones)
    if rig is None:
        R["wraps"] = {}
        return R
    p, seg, con = R["p"], R["seg"], R["contact"]
    keep = R["fixable"].copy()
    wraps = {}
    for kind, jid in crossed(rig, seg[keep]):
        if kind != "j":
            continue
        z = zone_of(jid)
        if z <= 0:
            continue
        j = next(x for x in rig["joints"] if x["id"] == jid)
        c = np.array(j["c"])
        hinge = len(j["dof"]) == 1
        u = unit(np.array(j["dof"][0]["a"])) if hinge else None
        if hinge:          # distance to the hinge axis; points far along the axis (beyond 1.2 x zone) are not over the joint
            rel = p - c
            axial = rel @ u
            d = np.linalg.norm(rel - np.outer(axial, u), axis=1)
            d[np.abs(axial) > 1.2 * z] = np.inf
        else:
            d = np.linalg.norm(p - c, axis=1)
        side = joint_side(rig, jid)
        ins = np.array([int(s) in side for s in seg])
        idx = np.where(keep)[0]
        cx = [k for k in range(len(idx) - 1) if ins[idx[k]] != ins[idx[k + 1]]]
        if len(cx) != 1:
            R["flags"].append("%s: path crosses the joint %d times, no slide / wrap" % (jid, len(cx)))
            continue
        lo, hi = idx[cx[0]], idx[cx[0] + 1]
        drop = np.zeros(len(p), bool)
        drop[lo + 1:hi] = True                                 # already-dropped points between the two kept ones
        for start, step in ((lo, -1), (hi, 1)):                # walk away from the crossing on each side to the first anchor
            i = start
            while 0 < i < len(p) - 1:
                if d[i] < z or (d[i] < 2 * z and not con[i]):
                    drop[i] = True
                    i += step
                else:
                    break
        drop[0] = drop[-1] = False
        near = drop & (d < 2 * z)
        if near.any():
            k = np.argmin(np.where(near, d, np.inf))
            wraps[jid] = dict(c=c.tolist(), R=float(d[k]), par=j["par"], side_pt=p[k].tolist(), u=(u.tolist() if hinge else None))
        keep &= ~drop
    out = dict(R)
    out["p"], out["seg"], out["contact"] = p[keep], seg[keep], con[keep]
    out["dropped"] = int((~keep).sum())
    for jid, w in list(wraps.items()):      # wrap only when the anchor chord at rest passes on the side of the centre the muscle lies on
        pair = crossing_pair(rig, out["seg"], jid)
        if pair is None:
            del wraps[jid]; continue
        a, b = out["p"][pair[0]], out["p"][pair[1]]
        c = np.array(w["c"])
        sp = np.array(w["side_pt"]) - c
        if w.get("u") is not None:
            uu = np.array(w["u"])
            a, b, sp = flat(a - c, uu), flat(b - c, uu), flat(sp, uu)
            c = np.zeros(3)
        q = closest_on_segment(a, b, c)
        A, B, Sd = a - c, b - c, sp
        if (q - c) @ sp > 0:
            n0 = np.cross(A, B)               # the chord already passes on the muscle's side: the short way round is the muscle's way
        else:
            # the anchor chord passes on the other side of the joint than the muscle really lies (a tendon held behind the malleolus or a
            # condyle by its retinaculum / pulley): the path goes round on the muscle's side, a -> muscle -> b, the long way if need be
            n1, n2 = np.cross(A, Sd), np.cross(Sd, B)
            if n1 @ n2 <= 0:
                out["flags"].append("%s: the muscle's side of the joint is ambiguous, no wrap" % jid)
                del wraps[jid]; continue
            n0 = n1 / max(np.linalg.norm(n1), 1e-12) + n2 / max(np.linalg.norm(n2), 1e-12)
            w["held"] = True
        if np.linalg.norm(n0) < 1e-9:
            del wraps[jid]; continue
        w["n0"] = (n0 / np.linalg.norm(n0)).tolist()
    out["wraps"] = wraps
    out["flags"] = list(R["flags"])
    return out


def closest_on_segment(a, b, c):
    ab = b - a
    t = np.clip(((c - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
    return a + t * ab


def crossing_count(rig, seg, jid):
    side = joint_side(rig, jid)
    ins = [int(s) in side for s in seg]
    return sum(1 for i in range(len(seg) - 1) if ins[i] != ins[i + 1])


def crossing_pair(rig, seg, jid):
    side = joint_side(rig, jid)
    ins = [int(s) in side for s in seg]
    idx = [i for i in range(len(seg) - 1) if ins[i] != ins[i + 1]]
    return (idx[0], idx[0] + 1) if len(idx) == 1 else None


def flat(x, u):
    """component of x perpendicular to the unit axis u"""
    return x - (x @ u) * u


def wrapped_cyl(a, b, c, u, R, n0=None):
    """length from a to b around a cylinder (axis through c along unit u, radius R): the wrapped length in the plane normal to the axis
    combined with the axial run, sqrt(L2d^2 + dz^2) (the path unrolls to a straight line on the cylinder)"""
    a2, b2 = flat(a - c, u), flat(b - c, u)
    dz = (b - a) @ u
    L2 = wrapped(a2, b2, np.zeros(3), R, n0)
    return float(np.sqrt(L2 * L2 + dz * dz))


def wrapped(a, b, c, R, n0=None):
    """length from a to b around a sphere (centre c, radius R) going round it in the sense n0 (the side the muscle lies on at rest):
    the two tangent lines plus the arc in the plane (a, c, b) when the oriented angle a -> b exceeds the two tangent angles, else the
    straight segment -- the obstacle-set sphere of Garner and Pandy (2000). Without n0: the shorter way round."""
    A, B = a - c, b - c
    da, db = np.linalg.norm(A), np.linalg.norm(B)
    if da <= 1e-9 or db <= 1e-9:
        return float(np.linalg.norm(b - a))
    R = min(R, 0.98 * min(da, db))            # an anchor on the wrap surface itself (an attachment on the condyle): wrap from there
    if R <= 0:
        return float(np.linalg.norm(b - a))
    ang = np.arccos(np.clip((A @ B) / (da * db), -1, 1))
    if n0 is not None and np.cross(A, B) @ np.asarray(n0) < 0:
        ang = 2 * np.pi - ang                 # the muscle's side is the long way round now: it stays wrapped on that side
    phi = ang - np.arccos(R / da) - np.arccos(R / db)
    if phi <= 0:
        return float(np.linalg.norm(b - a))
    return float(np.sqrt(da * da - R * R) + np.sqrt(db * db - R * R) + R * phi)


# ---------------------------------------------------------------- kinematics
_SUB = {}


def subtree(rig, root):
    key = (id(rig), root)
    if key in _SUB:
        return _SUB[key]
    kids = {}
    for i, s in enumerate(rig["segments"]):
        kids.setdefault(s["par"], []).append(i)
    out, st = set(), [root]
    while st:
        x = st.pop()
        out.add(x)
        st.extend(kids.get(x, []))
    _SUB[key] = out
    return out


def length(rig, pose, path):
    p, seg, wraps = path["p"], path["seg"], path.get("wraps") or {}
    M = fk(rig, pose)
    q = np.array([M[s][:3, :3] @ x + M[s][:3, 3] for x, s in zip(p, seg)])
    seglen = np.linalg.norm(np.diff(q, axis=0), axis=1)
    pairs = path.get("_pairs")
    if pairs is None:
        pairs = {}
        for jid, w in wraps.items():
            pr = crossing_pair(rig, seg, jid)
            if pr is not None:
                pairs.setdefault(pr[0], []).append(w)
        path["_pairs"] = pairs
    for i, ws in pairs.items():
        best = seglen[i]
        for w in ws:          # one chord across two joints (ankle + subtalar): it must clear both wraps -> the longer of the two
            Mp = M[w["par"]]
            c = Mp[:3, :3] @ np.array(w["c"]) + Mp[:3, 3]
            n0 = Mp[:3, :3] @ np.array(w["n0"]) if w.get("n0") is not None else None
            if w.get("u") is not None:
                L = wrapped_cyl(q[i], q[i + 1], c, Mp[:3, :3] @ np.array(w["u"]), w["R"], n0)
            else:
                L = wrapped(q[i], q[i + 1], c, w["R"], n0)
            best = max(best, L)
        seglen[i] = best
    return float(seglen.sum())


def crossed(rig, seg):
    """non-driven joints and spine regions whose motion changes the distance between path points (driven joints -- patella,
    shoulder girdle -- are folded into the joints that drive them by the FK)"""
    S = set(int(s) for s in seg)
    J = []
    for j in rig["joints"]:
        if j.get("driven"):
            continue
        side = joint_side(rig, j["id"])
        if S & side and S - side:
            J.append(("j", j["id"]))
    for r in rig["regions"]:
        for L in r["levels"]:
            sub = subtree(rig, L["seg"])
            if S & sub and S - sub:
                J.append(("r", r["id"]))
                break
    return J


def sweep_angles(d):
    lo, hi = d["lo"], d["hi"]
    a = [x for x in (0.0, 45.0, 90.0) if lo <= x <= hi]
    if len(a) < 3:
        a = sorted(set([round(lo / 2.0, 1), 0.0 if lo <= 0 <= hi else round((lo + hi) / 2, 1), round(hi, 1)]))
    return a


def moment_arms(rig, path, kind, jid, base=None, angles=None):
    """-> dict(dofs=[k...], sweep=k0, angles=[...], r={k: [mm at each angle]}); the joint's other dofs at 0 during the sweep"""
    pose0 = base or default_pose(rig)

    def L_at(jq=None, rq=None):
        P = {"joints": dict(pose0["joints"]), "regions": dict(pose0["regions"])}
        if jq is not None:
            P["joints"][jid] = jq
        if rq is not None:
            P["regions"][jid] = rq
        return length(rig, P, path)

    h = np.radians(H_DEG)
    if kind == "j":
        j = next(x for x in rig["joints"] if x["id"] == jid)
        dofs = j["dof"]
        zero = [min(max(0.0, d["lo"]), d["hi"]) for d in dofs]
        ang = list(angles) if angles else sweep_angles(dofs[0])
        out = {d["k"]: [] for d in dofs}
        for a in ang:
            q = list(zero); q[0] = float(a)
            for k, d in enumerate(dofs):
                qp, qm = list(q), list(q)
                qp[k] += H_DEG; qm[k] -= H_DEG
                out[d["k"]].append(round(-(L_at(jq=qp) - L_at(jq=qm)) / (2 * h), 2))
        return dict(dofs=[d["k"] for d in dofs], sweep=dofs[0]["k"], angles=[float(a) for a in ang], r=out)
    r = next(x for x in rig["regions"] if x["id"] == jid)
    out = {}
    for k, d in enumerate(r["dof"]):
        tp, tm = [0.0] * len(r["dof"]), [0.0] * len(r["dof"])
        tp[k], tm[k] = H_DEG, -H_DEG
        out[d["k"]] = [round(-(L_at(rq=tp) - L_at(rq=tm)) / (2 * h), 2)]
    return dict(dofs=[d["k"] for d in r["dof"]], sweep=None, angles=[0.0], r=out)


# ---------------------------------------------------------------- shared tendons
# a tendon that is its own mesh on a page is joined to the muscles it belongs to (anatomical identity of the tendon, Terminologia
# Anatomica / Gray's: the calcaneal tendon is the common tendon of gastrocnemius and soleus, the quadriceps tendon that of rectus femoris
# and the three vasti, ...), so the path reaches the bone the tendon inserts on.
TENDON_OF = [(r"calcaneal_tendon", r"(gastrocnemius|soleus|triceps_surae)"),
             (r"quadriceps_tendon", r"(rectus_femoris|vastus_(lateralis|medialis|intermedius)|quadriceps)"),
             (r"iliopsoas_tendon", r"(iliopsoas|psoas_major|iliacus)"),
             (r"adductor_magnus_distal_tendon", r"adductor_magnus")]


def tendon_for(S, x):
    """vertices of the separately-meshed tendon(s) of muscle structure x on the same side, or None"""
    mid = re.sub(r"^zan_", "", x["id"].lower())
    out = []
    for tpat, mpat in TENDON_OF:
        if not re.search(mpat, mid):
            continue
        for t in S:
            if t["sys"] in ("tendon", "insertion") and re.search(tpat, t["id"].lower()) and t.get("side") == x.get("side"):
                out.append(t["v"])
    return np.vstack(out) if out else None
