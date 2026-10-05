"""Q194: leftovers of Q190 (trunk) and Q191 (right hand): shape relaxation of the still-distorted structures, skin patches onto her CT outline, bounded
muscle-muscle separation (scripts/zanatomy/q194_separate.py).  Real sources only: the reference is her CT skin / bones / her own labels, the shape is the Z source."""
from __future__ import annotations

import re

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q190_metrics as Mx
from scripts.zanatomy import q190_refine as Q
from scripts.zanatomy import q191_hand as H

RELAX_SIGMAS = (8.0, 14.0, 24.0)


def stretch_pct(v, r, f):
    st = Mx.stretch_stats(v, r, f)
    return None if st is None else 100.0 * (st["area_frac_gt1.5"] + st["area_frac_lt0.67"])


def relax_one(d, sigmas=RELAX_SIGMAS, max_move=10.0, accept=None):
    """smallest low-pass sigma (Q190 shape relaxation) that brings the area-stretch score under max(25 %, half of before); returns (v_new, info) or None"""
    v0, r, f = d["v"].astype(float), d["r"].astype(float), d["f"]
    s0 = stretch_pct(v0, r, f)
    if s0 is None or s0 < 25.0:
        return None
    best = None
    for sg in sigmas:
        v1 = Q.smooth_displacement({"r": r, "f": f}, v0, sg)
        mv = np.linalg.norm(v1 - v0, axis=1)
        if mv.max() > max_move:
            v1 = v0 + (v1 - v0) * np.minimum(1.0, max_move / np.maximum(mv, 1e-9))[:, None]
        s1 = stretch_pct(v1, r, f)
        if d["cat"] == "muscle" and Q._closed(f):
            v1, _ = Q.volume_guard(v1, r, f)
        if accept is not None and not accept(d["id"], v0, v1):
            continue
        if H.fold_stats(v1, r, f) > H.fold_stats(v0, r, f) + 0.003:
            continue
        info = {"sigma_mm": sg, "stretch_before_pct": round(s0, 1), "stretch_after_pct": round(s1, 1), "max_move_mm": round(float(np.linalg.norm(v1 - v0, axis=1).max()), 2),
                "mean_move_mm": round(float(np.linalg.norm(v1 - v0, axis=1).mean()), 2)}
        if best is None or s1 < best[1]["stretch_after_pct"]:
            best = (v1, info)
        if s1 <= max(25.0, 0.5 * s0):
            break
    if best is None or best[1]["stretch_after_pct"] >= 0.8 * s0:
        return None
    return best


# ------------------------------------------------------------------------------------------------ skin patches onto her CT outline
def skin_dist(skin_pts_tree, v):
    return skin_pts_tree.query(v)[0]


def patch_membrane(by: dict, group: list[str], raw: dict, skin, skin_tree, inset=0.8, max_move=45.0, iters=400):
    """Z skin patches of `group` that lie far off her CT outline (Q190: gluteal fold, anal region 17-42 mm): the patches tile one surface, so their SEAM vertices (shared with
    patches outside the group) keep the neighbours' positions (which are on her skin), the interior vertices become the harmonic (membrane) interpolation of the seam, and then
    every vertex goes onto her CT skin, `inset` mm inside it.  Returns {id: v_new}"""
    from trimesh.proximity import closest_point
    other = [i for i, d in by.items() if d["cat"] == "skin" and i not in group]
    ro = np.vstack([raw[i] for i in other])
    keyo = {tuple(x) for x in np.round(ro, 2)}
    # unique vertex ids over the group
    allr = np.vstack([raw[i] for i in group]).astype(float)
    u, inv = np.unique(np.round(allr, 2), axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    n = len(u)
    off = np.cumsum([0] + [len(raw[i]) for i in group])
    pos = np.zeros((n, 3)); cnt = np.zeros(n)
    for k, i in enumerate(group):
        np.add.at(pos, inv[off[k]:off[k + 1]], by[i]["v"]); np.add.at(cnt, inv[off[k]:off[k + 1]], 1)
    pos /= cnt[:, None]
    fixed = np.array([tuple(x) in keyo for x in u])
    if fixed.all() or not fixed.any():
        return None
    # fixed positions = the neighbour patch's current vertex at that raw position
    nb = {}
    for i in other:
        for x, p in zip(np.round(raw[i], 2), by[i]["v"]):
            nb.setdefault(tuple(x), p)
    for j in np.flatnonzero(fixed):
        pos[j] = nb[tuple(u[j])]
    e = []
    for k, i in enumerate(group):
        f = inv[off[k]:off[k + 1]][by[i]["f"]]
        e += [f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]
    e = np.unique(np.sort(np.vstack(e), 1), axis=0)
    nbr = [[] for _ in range(n)]
    for a, b in e:
        nbr[a].append(b); nbr[b].append(a)
    x = pos.copy()
    free = np.flatnonzero(~fixed)
    for _ in range(iters):                                  # Gauss-Seidel membrane
        for j in free:
            x[j] = x[nbr[j]].mean(0)
    cp, _, tri = closest_point(skin, x)
    tgt = cp - inset * skin.face_normals[tri]
    d = tgt - x
    mv = np.linalg.norm(d, axis=1)
    sc = np.minimum(1.0, max_move / np.maximum(mv, 1e-9))
    x = np.where(fixed[:, None], x, x + d * sc[:, None])
    return {i: x[inv[off[k]:off[k + 1]]] for k, i in enumerate(group)}


# ------------------------------------------------------------------------------------------------ acceptance gates
class Gates:
    """containment tests shared by every Q194 move: inside her CT skin, out of the displayed bones (ray parity), skin patches stay on her outline"""

    def __init__(self, by: dict, skin, skin_tree):
        from scripts.zanatomy.q194_separate import Skel
        self.by, self.skin, self.tree = by, skin, skin_tree
        self.bones = {i: Skel(d["v"].astype(float), d["f"]) for i, d in by.items() if d["cat"] == "bone" and Q._closed(d["f"])}
        self._cache = {}

    def outside_skin_pct(self, v):
        return 100.0 * float((~self.skin.contains(v)).mean())

    def inside_bone_pct(self, v, tol=1.5):
        lo, hi = v.min(0), v.max(0)
        worst = np.zeros(len(v), bool)
        for i, s in self.bones.items():
            if np.any(s.hi < lo - 2) or np.any(s.lo > hi + 2):
                continue
            worst |= s.depth(v) > tol
        return 100.0 * float(worst.mean())

    def accept(self, i, v0, v1, skin_tol=0.5, bone_tol=1.0, gap_tol=1.5):
        """a move v0 -> v1 of structure i is acceptable if it does not worsen containment (skin / bones) and, for skin patches, the gap to her skin"""
        d = self.by[i]
        if self.outside_skin_pct(v1) > self.outside_skin_pct(v0) + skin_tol:
            return False
        if d["cat"] == "skin":
            return float(np.median(self.tree.query(v1)[0])) <= float(np.median(self.tree.query(v0)[0])) + gap_tol
        if d["cat"] != "bone" and self.inside_bone_pct(v1) > self.inside_bone_pct(v0) + bone_tol:
            return False
        return True


# ------------------------------------------------------------------------------------------------ driver
NAMED_DISTORTED = re.compile(r"^(zan_cephalic_vein_[lr]|zan_skin_(greater|lesser)_supraclavicular_fossa_[lr]|zan_musculophrenic_(artery|veins)_[lr]|supraspinous_ligament|"
                             r"zan_deep_branch_of_transverse_cervical_artery_[lr]|(zan_)?intervertebral_disc_(c7_t1|t[1-6]_t[2-7])|rhomboid_major_[lr]|"
                             r"zan_(abdominal|clavicular|sternocostal)_(part|head)_of_pectoralis_major_muscle_[lr]|subclavius_[lr]|lateral_femoral_cutaneous_n_[lr])$")


def _note(i, what, before, after):
    return f" Q194: {what}: {before} -> {after}."


def refine(by: dict, raw: dict, regions: dict, decimate_fn=None, log=print) -> dict:
    """hand + trunk leftovers (see the module docstring); returns the report sections"""
    import trimesh  # noqa: F401
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.zanatomy import q190_audit as A
    from scripts.zanatomy import q194_separate as Sp
    skin = load_skin("vhf")
    skin_tree = cKDTree(H.surf_pts(np.asarray(skin.vertices, float), np.asarray(skin.faces), 200000))
    G = Gates(by, skin, skin_tree)
    snap = {i: d["v"].copy() for i, d in by.items()}
    rep = {"relaxed": {}, "separated": {}, "skin": {}}

    def commit(i, v, text):
        by[i]["v"] = v
        by[i]["fit_note"] = (by[i].get("fit_note") or "") + text

    # (a) the still-distorted trunk structures: shape relaxation
    for i, d in by.items():
        if not NAMED_DISTORTED.match(i):
            continue
        dd = {"id": i, "v": d["v"], "r": raw[i], "f": d["f"], "cat": d["cat"]}
        res = relax_one(dd, accept=lambda k, a, b: G.accept(k, a, b))
        if res is None:
            continue
        v1, info = res
        rep["relaxed"][i] = info
        commit(i, v1, f" Q194: shape relaxation (low-pass {info['sigma_mm']} mm of the displacement from its own Z source shape, the global field had sheared it): "
                      f"triangles stretched outside 0.67-1.5x {info['stretch_before_pct']} -> {info['stretch_after_pct']} %, mean move {info['mean_move_mm']} mm (max {info['max_move_mm']}); "
                      f"stays inside her skin and out of the displayed bones.")
    log(f"  Q194 relaxed {len(rep['relaxed'])} distorted structures")

    # (a1) sacral / gluteal skin faceting: volume-preserving (Taubin) smoothing of the welded skin patches where the skin lies within tolerance of her CT skin; <= 6 mm, never
    # further from her skin than before (+ 2 mm), never outside it, tapered at the region border; the patches are NOT decimated, so this is the shipped surface
    from scripts.zanatomy import trunk_refit_q186c as T186
    sk_ids = [i for i, d in by.items() if d["cat"] == "skin"]

    def wfn(p):
        wy = T186.smoothstep(np.minimum(p[:, 1] + 135.0, 115.0 - p[:, 1]) / 25.0)
        wz = T186.smoothstep((15.0 - p[:, 2]) / 25.0)
        near = (skin_tree.query(p)[0] < 8.0).astype(float)           # within tolerance of her CT skin
        return wy * wz * near

    smooth_v, _ = smooth_skin(by, sk_ids, raw, wfn, skin, skin_tree, iters=40, max_move=6.0, gap_tol=2.0)
    rep["skin"]["smoothed"] = {}
    for i in sk_ids:
        dmax = float(np.linalg.norm(smooth_v[i] - by[i]["v"], axis=1).max())
        if dmax < 0.3 or by[i]["v"].shape != smooth_v[i].shape:
            continue
        r0, r1 = face_roughness(by[i]["v"], by[i]["f"]), face_roughness(smooth_v[i], by[i]["f"])
        g0, g1 = float(np.median(skin_tree.query(by[i]["v"])[0])), float(np.median(skin_tree.query(smooth_v[i])[0]))
        rep["skin"]["smoothed"][i] = {"max_move_mm": round(dmax, 2), "face_roughness_deg_before": round(r0, 1), "face_roughness_deg_after": round(r1, 1),
                                      "median_gap_to_her_skin_mm_before": round(g0, 2), "median_gap_to_her_skin_mm_after": round(g1, 2)}
        by[i]["v"] = smooth_v[i]
        by[i]["fit_note"] = (by[i].get("fit_note") or "") + (
            f" Q194: sacral / gluteal skin faceting smoothed (volume-preserving Taubin smoothing, max move {dmax:.1f} mm, mean angle between neighbouring faces {r0:.1f} -> {r1:.1f} deg, "
            f"median gap to her CT skin {g0:.1f} -> {g1:.1f} mm, inside her skin).")
    log(f"  Q194 skin smoothing: {len(rep['skin']['smoothed'])} patches")

    # (a0) right forearm muscles onto her own-model forearm labels (Q190 skipped the forearm)
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    from scripts.zanatomy import q194_forearm as F
    rep["right_forearm"] = F.refine_right_forearm(by, raw, regions, load_her_meshes(), skin, skin_tree, log=log)

    # (a2) right hand / forearm (Q191 leftovers): bones left outside her thin finger skin are nudged in (<= 4 mm); structures still > 25 % stretched get the shape relaxation
    pend0 = [{"mesh_id": k, "cat": d["cat"]} for k, d in by.items()]
    rep["right_hand"] = {"bones_nudged": {}, "relaxed": {}}
    for i in sum(H.bone_ids("r").values(), []):
        d = by[i]
        o = G.outside_skin_pct(d["v"])
        if o <= 0.3:
            continue
        v1 = H.clamp_inside_skin(d["v"].astype(float), d["f"], np.ones(len(d["v"]), bool), skin, skin_tree, margin=0.8, max_move=4.0)
        o1 = G.outside_skin_pct(v1)
        if o1 < o:
            rep["right_hand"]["bones_nudged"][i] = {"outside_skin_pct_before": round(o, 2), "outside_skin_pct_after": round(o1, 2), "max_move_mm": round(float(np.linalg.norm(v1 - d["v"], axis=1).max()), 2)}
            by[i]["v"] = v1
            by[i]["fit_note"] = (by[i].get("fit_note") or "") + f" Q194: nudged inside her thin finger skin (vertices outside her CT skin {o:.1f} -> {o1:.1f} %, max move {rep['right_hand']['bones_nudged'][i]['max_move_mm']} mm)."
    for i in H.scope(pend0, regions, "r"):
        d = by[i]
        if d["cat"] == "bone" or H.FOOT_NAME.search(i):
            continue
        res = relax_one({"id": i, "v": d["v"], "r": raw[i], "f": d["f"], "cat": d["cat"]}, sigmas=(8.0, 14.0), max_move=5.0, accept=lambda k, a, b: G.accept(k, a, b))
        if res is None:
            continue
        v1, info = res
        rep["right_hand"]["relaxed"][i] = info
        by[i]["v"] = v1
        by[i]["fit_note"] = (by[i].get("fit_note") or "") + (
            f" Q194: shape relaxation (low-pass {info['sigma_mm']} mm of the displacement from its own Z source shape): triangles stretched outside 0.67-1.5x {info['stretch_before_pct']} -> "
            f"{info['stretch_after_pct']} %, mean move {info['mean_move_mm']} mm (max {info['max_move_mm']}); stays inside her skin and out of the displayed bones.")
    log(f"  Q194 right hand: {len(rep['right_hand']['bones_nudged'])} bones nudged in, {len(rep['right_hand']['relaxed'])} structures relaxed")

    # (b) neighbour-muscle overlap: bounded separation on the SHIPPED (decimated) meshes -- the overlap the viewer shows is the one after the quadric decimation (the full-resolution
    # meshes overlap less than the shipped ones: measured 9.65 % decimated vs the audit's 9.69 % shipped).  Sets: trunk + shoulder; right hand + forearm; left hand + forearm,
    # whose muscles Q194 has just re-placed and which never saw the gap closure.
    pend = [{"mesh_id": k, "cat": d["cat"]} for k, d in by.items()]
    hand_r = [i for i in H.scope(pend, regions, "r") if by[i]["cat"] == "muscle"]
    hand_l = [i for i in H.scope(pend, regions, "l") if by[i]["cat"] == "muscle"]
    trunk = [k for k, d in by.items() if d["cat"] == "muscle" and A.region_of({"v": d["v"]}) is not None and not A.HAND.search(k)]
    sets = {"trunk_shoulder": trunk, "right_forearm_hand": hand_r, "left_forearm_hand": hand_l}
    done = {}
    for name, ids in sets.items():
        ids = [i for i in ids if Q._closed(by[i]["f"]) and not Q.NOT_A_MUSCLE_BODY.search(i) and not H.FOOT_NAME.search(i)]
        meshes = {i: done.get(i) or decimate_fn(by[i]["v"].astype(float), by[i]["f"], i, "muscle") for i in ids}
        meshes = {i: (np.asarray(v, float), f) for i, (v, f) in meshes.items()}
        vol_ref = {i: abs(Q.volume(raw[i].astype(float), by[i]["f"])) * Mx.BODY_SCALE ** 3 for i in ids}
        ov0 = Sp.overlap_pct(meshes)
        movable = {i for i, o in ov0.items() if o > 1.0}
        base = {i: meshes[i][0] for i in movable}
        out, mrep = Sp.separate(meshes, vol_ref, movable, keep=lambda i, v2: G.accept(i, base[i], v2), log=log)
        ov1 = Sp.overlap_pct({i: (out[i], meshes[i][1]) for i in ids})
        rep["separated"][name] = {"structures": len(ids), "with_overlap_gt_1pct_before": len(movable),
                                  "mean_overlap_pct_before": round(float(np.mean(list(ov0.values()))), 2), "mean_overlap_pct_after": round(float(np.mean(list(ov1.values()))), 2),
                                  "moved": mrep, "overlap_pct": {i: [round(ov0[i], 1), round(ov1[i], 1)] for i in ids if i in movable}}
        for i, m in mrep.items():
            if m["max_move_mm"] < 0.3:
                continue
            by[i]["pre_decimated"] = (out[i], meshes[i][1])
            vr = abs(Q.volume(out[i], meshes[i][1])) / vol_ref[i]
            by[i]["fit_note"] = (by[i].get("fit_note") or "") + (
                f" Q194: overlap with neighbouring muscles removed by a bounded per-vertex separation along the contact normal on the shipped mesh (vertices inside a neighbour "
                f"{ov0[i]:.1f} -> {ov1[i]:.1f} %, mean move {m['mean_move_mm']} mm, max {m['max_move_mm']}, volume {vr:.2f}x the Z source).")
        log(f"  Q194 separation [{name}]: {len(ids)} muscles, overlap {rep['separated'][name]['mean_overlap_pct_before']} -> {rep['separated'][name]['mean_overlap_pct_after']} %")
    return rep


# ------------------------------------------------------------------------------------------------ skin faceting
def skin_graph(by: dict, ids: list[str], raw: dict):
    """welded vertex graph of the skin patches: unique Z-source positions (the patches share seam vertices), per-patch index maps, adjacency (sparse), mean positions"""
    from scipy import sparse
    allr = np.vstack([raw[i] for i in ids]).astype(float)
    u, inv = np.unique(np.round(allr, 2), axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    off = np.cumsum([0] + [len(raw[i]) for i in ids])
    n = len(u)
    pos = np.zeros((n, 3)); cnt = np.zeros(n)
    allv = np.vstack([by[i]["v"] for i in ids]).astype(float)
    np.add.at(pos, inv, allv); np.add.at(cnt, inv, 1)
    pos /= cnt[:, None]
    e = []
    for k, i in enumerate(ids):
        f = inv[off[k]:off[k + 1]][by[i]["f"]]
        e += [f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]
    e = np.vstack(e)
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    A = ((A + A.T) > 0).astype(float)
    return u, inv, off, pos, A


def face_roughness(v, f):
    """mean angle (deg) between the normals of edge-adjacent faces"""
    n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    e = np.vstack([np.c_[f[:, 0], f[:, 1], np.arange(len(f))], np.c_[f[:, 1], f[:, 2], np.arange(len(f))], np.c_[f[:, 2], f[:, 0], np.arange(len(f))]])
    key = np.sort(e[:, :2], 1)
    o = np.lexsort((key[:, 1], key[:, 0]))
    k, fi = key[o], e[o, 2]
    same = (k[1:] == k[:-1]).all(1)
    a, b = fi[:-1][same], fi[1:][same]
    return float(np.degrees(np.arccos(np.clip((n[a] * n[b]).sum(1), -1, 1))).mean()) if len(a) else 0.0


def smooth_skin(by: dict, ids: list[str], raw: dict, weight_fn, skin, skin_tree, iters=20, lam=0.5, mu=-0.53, max_move=3.0, gap_tol=1.0):
    """Taubin (volume-preserving) smoothing of the welded skin patches, weighted by weight_fn(v) in [0, 1] (smooth taper at the region border), displacement <= max_move mm,
    never further from her CT skin than before (+ gap_tol) and never outside it.  Returns {id: v_new} and the per-vertex displacement (welded)"""
    u, inv, off, pos0, A = skin_graph(by, ids, raw)
    deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1.0)
    w = weight_fn(pos0)
    x = pos0.copy()
    for _ in range(iters):
        for k in (lam, mu):
            x = x + (w * k)[:, None] * ((A @ x) / deg[:, None] - x)
    d = x - pos0
    m = np.linalg.norm(d, axis=1)
    d *= np.minimum(1.0, max_move / np.maximum(m, 1e-9))[:, None]
    g0 = skin_tree.query(pos0)[0]
    for _ in range(4):
        cand = pos0 + d
        bad = (skin_tree.query(cand)[0] > g0 + gap_tol) | (~skin.contains(cand) & skin.contains(pos0))
        if not bad.any():
            break
        d[bad] *= 0.5
    new = pos0 + d
    return {i: new[inv[off[k]:off[k + 1]]] for k, i in enumerate(ids)}, d
