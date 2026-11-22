"""Q198 per-structure continuity analysis at a junction (muscle/tendon/ligament/fascia bellies; vessels/nerves as tubes)."""
from __future__ import annotations
import re
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree
from scripts.zanatomy.q198_core import weld, boundary_loops, loop_stats, islands, pca, tri_area

# elbow muscle -> (expected bones at the elbow-side end)
ELBOW_ATTACH = [
    (r"biceps_brachii", ["radius", "ulna"]), (r"brachialis", ["ulna"]),
    (r"triceps", ["ulna", "humerus"]), (r"anconeus", ["humerus", "ulna"]), (r"brachioradialis", ["humerus"]),
    (r"pronator_teres", ["humerus", "ulna", "radius"]), (r"supinator", ["humerus", "ulna", "radius"]),
    (r"flexor_carpi_radialis|palmaris_longus|flexor_carpi_ulnaris|flexor_digitorum_superficialis|humero_ulnar_head", ["humerus", "ulna"]),
    (r"extensor_carpi_radialis|extensor_digitorum_l$|extensor_digitorum$|extensor_digiti_minimi|extensor_carpi_ulnaris", ["humerus", "ulna"]),
    (r"flexor_digitorum_profundus", ["ulna", "radius"]),
    (r"flexor_pollicis_longus|extensor_pollicis|abductor_pollicis|extensor_indicis|pronator_quadratus", ["radius", "ulna"]),
    (r"collateral_ligament_l$|collateral_ligament_r$|annular", ["humerus", "ulna", "radius"]),
]


def base_id(i):
    i = re.sub(r"^zan_", "", i)
    return i


def expected_bones(sid):
    b = base_id(sid)
    for rx, bones in ELBOW_ATTACH:
        if re.search(rx, b):
            return bones
    return None


def graph_levels(v, f, step=3.0):
    """geodesic levels from one end of a tube-like mesh -> (levels, centroids(k,3), counts, ncomp_main)"""
    n = len(v)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]); e = np.unique(np.sort(e, 1), axis=0)
    w = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1) + 1e-6
    A = coo_matrix((np.r_[w, w], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(n, n)).tocsr()
    nc, lab = connected_components(A, directed=False)
    main = np.bincount(lab).argmax()
    idx = np.where(lab == main)[0]
    d0 = dijkstra(A, indices=idx[0], limit=np.inf)
    a = idx[np.argmax(np.where(np.isfinite(d0[idx]), d0[idx], -1))]
    d1 = dijkstra(A, indices=a)
    d1[~np.isfinite(d1)] = -1
    L = d1[idx]
    k = np.floor(L / step).astype(int)
    cents, cnts = [], []
    for kk in range(k.max() + 1):
        m = idx[k == kk]
        if len(m):
            cents.append(v[m].mean(0)); cnts.append(len(m))
    return np.array(cents), np.array(cnts), nc, float(L.max())


def end_region(v, ax, c, frac=0.08, minv=6):
    t = (v - c) @ ax
    lo, hi = t.min(), t.max(); L = hi - lo
    out = []
    for sgn, ref in ((-1, lo), (1, hi)):
        m = (t <= lo + frac * L) if sgn < 0 else (t >= hi - frac * L)
        if m.sum() < minv:
            m = (t <= np.sort(t)[min(minv, len(t) - 1)]) if sgn < 0 else (t >= np.sort(t)[-min(minv, len(t))])
        out.append(np.where(m)[0])
    return out, t


class BoneField:
    """dense surface samples + KD-tree per bone; plus signed solids on a local grid"""
    def __init__(self, bones):
        from scripts.zanatomy.q198_core import surf_points
        self.pts = {}; self.tree = {}
        for b in bones:
            P = surf_points(b["v"], b["f"], 1.0, cap=50000)
            self.pts[b["id"]] = P; self.tree[b["id"]] = cKDTree(P)
        allp = np.concatenate(list(self.pts.values()))
        self.all = cKDTree(allp)

    def dist(self, p, ids=None):
        if ids is None:
            return self.all.query(p)[0]
        ds = [self.tree[i].query(p)[0] for i in ids if i in self.tree]
        return np.min(ds, axis=0) if ds else np.full(len(p), np.inf)


def analyse_belly(s, J, bf, skin, bonefill, expb=None, near_end_R=None):
    """continuity of one muscle/tendon/ligament/fascia mesh at a junction"""
    v0, f0 = s["v"], s["f"]
    v, f = weld(v0, f0)
    res = {"id": s["id"], "name": s["name"], "sys": s["sys"], "side": s["side"], "src": s.get("src"), "cls": s.get("cls"), "nv": int(len(v0)), "nf": int(len(f))}
    if len(f) < 4:
        res["note"] = "degenerate"
        return res
    c = J["centre"]; a = J["axis"]; R = J["R"]
    isl = islands(v, f)
    tot = sum(i["area"] for i in isl)
    main = isl[0]
    res["islands"] = len(isl)
    res["main_area_share"] = round(main["area"] / tot, 4)
    mt = cKDTree(v[main["vidx"]])
    small = []
    for i in isl[1:]:
        d = mt.query(v[i["vidx"]])[0].min()
        small.append({"area_share": round(i["area"] / tot, 4), "n": int(len(i["vidx"])), "gap_mm": round(float(d), 2), "dist_to_joint_mm": round(float(np.linalg.norm(v[i["vidx"]].mean(0) - c)), 1)})
    res["small_islands"] = small[:12]
    res["max_island_gap_mm"] = max([x["gap_mm"] for x in small], default=0.0)
    res["max_island_share_gt5mm"] = max([x["area_share"] for x in small if x["gap_mm"] > 5], default=0.0)
    # boundary / ragged ends
    loops, nb, nm = boundary_loops(v, f)
    ne = int(len(np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), 1), axis=0)))
    res["open_edge_frac"] = round(nb / max(ne, 1), 4)
    res["open_edges"] = int(nb)
    cuts = []
    for l in loops:
        st = loop_stats(v, l)
        dc = float(np.linalg.norm(np.asarray(st["centre"]) - c))
        st["dist_to_joint_mm"] = round(dc, 1)
        if st["n"] >= 8:
            cuts.append(st)
    # planar loops with real extent = flat cut face; (loop perimeter extent > 6 mm)
    flat = [x for x in cuts if x["planarity_mm"] < 1.0 and x["extent_mm"] > 6]
    res["flat_cut_loops"] = [{"n": x["n"], "extent_mm": x["extent_mm"], "planarity_mm": x["planarity_mm"], "dist_to_joint_mm": x["dist_to_joint_mm"]} for x in flat if x["dist_to_joint_mm"] < 1.3 * R][:6]
    res["open_loops_in_zone"] = int(sum(1 for x in cuts if x["dist_to_joint_mm"] < 1.3 * R))
    # axis, ends, axial gaps
    vm = v[main["vidx"]]
    cc, vt, sv = pca(vm)
    ax = vt[0]
    if np.dot(ax, a) < 0:
        ax = -ax                       # + = distal (along the junction axis)
    t = (vm - cc) @ ax
    L = float(t.max() - t.min()); res["length_mm"] = round(L, 1)
    allt = (v[np.unique(f)] - cc) @ ax
    srt = np.sort(allt); gaps = np.diff(srt)
    res["max_axial_gap_mm"] = round(float(gaps.max()), 2) if len(gaps) else 0.0
    ends, tt = end_region(v[np.unique(f)], ax, cc)
    vv = v[np.unique(f)]
    e_prox, e_dist = vv[ends[0]], vv[ends[1]]
    # closed flat caps (a cut through a closed mesh)
    from scripts.zanatomy.q198_core import flat_caps
    caps = [] if (s["sys"] in ("cartilage", "skin") or "disc" in s["id"]) else flat_caps(v, f)
    for cp in caps:
        cp["dist_to_joint_mm"] = round(float(np.linalg.norm(np.asarray(cp.pop("centre")) - c)), 1)
    res["flat_caps"] = caps[:4]
    res["end_prox_mm"] = np.round(e_prox.mean(0), 1).tolist(); res["end_dist_mm"] = np.round(e_dist.mean(0), 1).tolist()
    dp, dd = np.linalg.norm(e_prox.mean(0) - c), np.linalg.norm(e_dist.mean(0) - c)
    res["end_prox_to_joint_mm"] = round(float(dp), 1); res["end_dist_to_joint_mm"] = round(float(dd), 1)
    # crossing: vertices on both sides of the joint plane by >=12 mm, within lateral 1.0R
    along = (v - c) @ a
    lat = np.linalg.norm((v - c) - np.outer(along, a), axis=1)
    near = lat < R
    res["crosses_joint"] = bool((along[near] > 12).any() and (along[near] < -12).any())
    res["axis_extent_vs_joint_mm"] = [round(float(along[near].min()), 1) if near.any() else None, round(float(along[near].max()), 1) if near.any() else None]
    # attachments of the ends that lie in the zone
    att = {}
    for nm, e, dj in (("prox", e_prox, dp), ("dist", e_dist, dd)):
        if dj < 1.3 * R:
            dall = bf.dist(e)
            ent = {"to_joint_mm": round(float(dj), 1), "min_any_bone_mm": round(float(dall.min()), 2), "median_any_bone_mm": round(float(np.median(dall)), 2)}
            if expb:
                dd2 = bf.dist(e, [f'{x}_{J["side"]}' for x in expb])
                ent["min_expected_bone_mm"] = round(float(dd2.min()), 2); ent["median_expected_bone_mm"] = round(float(np.median(dd2)), 2)
            att[nm] = ent
    res["attach_ends_in_zone"] = att
    # containment
    sd = skin.signed(v)
    res["outside_skin_pct"] = round(100 * float((sd > 3).mean()), 2); res["outside_skin_max_mm"] = round(float(max(sd.max(), 0)), 1)
    inb, depth = bonefill(v)
    res["inside_bone_pct"] = round(100 * float((depth > 1.5).mean()), 2); res["inside_bone_max_mm"] = round(float(depth.max()), 1)
    return res


def analyse_tube(s, J, bf, skin, bonefill, step=3.0):
    v, f = weld(s["v"], s["f"])
    c = J["centre"]; R = J["R"]
    res = {"id": s["id"], "name": s["name"], "sys": s["sys"], "side": s["side"], "src": s.get("src"), "cls": s.get("cls"), "nv": int(len(s["v"]))}
    isl = islands(v, f)
    tot = sum(i["area"] for i in isl)
    res["islands"] = len(isl)
    mt = cKDTree(v[isl[0]["vidx"]])
    sm = []
    for i in isl[1:]:
        sm.append({"area_share": round(i["area"] / tot, 3), "gap_mm": round(float(mt.query(v[i["vidx"]])[0].min()), 2)})
    res["small_islands"] = sm[:8]
    res["max_island_gap_mm"] = max([x["gap_mm"] for x in sm], default=0.0)
    cen, cnt, nc, Lg = graph_levels(v, f, step)
    res["geodesic_len_mm"] = round(Lg, 1)
    if len(cen) >= 4:
        d = np.linalg.norm(np.diff(cen, axis=0), axis=1)
        res["max_level_jump_mm"] = round(float(d.max()), 2)           # centroid step between successive 3 mm geodesic levels (3 = perfectly straight)
        # turning angle over 2 levels
        seg = np.diff(cen, axis=0); seg /= np.maximum(np.linalg.norm(seg, axis=1, keepdims=True), 1e-6)
        ang = np.degrees(np.arccos(np.clip((seg[1:] * seg[:-1]).sum(1), -1, 1)))
        res["max_turn_deg"] = round(float(ang.max()), 1) if len(ang) else 0.0
        # in-zone centreline points
        dz = np.linalg.norm(cen - c, axis=1)
        res["centreline_in_zone_pts"] = int((dz < R).sum())
        res["centreline_end_a"] = np.round(cen[0], 1).tolist(); res["centreline_end_b"] = np.round(cen[-1], 1).tolist()
        # radial excursion: unrealistic steps = jump > 2.5*step
        res["jumps_gt_8mm"] = int((d > 8).sum())
    res["near_zone"] = bool((np.linalg.norm(v - c, axis=1) < R).any())
    sd = skin.signed(v)
    res["outside_skin_pct"] = round(100 * float((sd > 3).mean()), 2); res["outside_skin_max_mm"] = round(float(max(sd.max(), 0)), 1)
    inb, depth = bonefill(v)
    res["inside_bone_pct"] = round(100 * float((depth > 1.5).mean()), 2); res["inside_bone_max_mm"] = round(float(depth.max()), 1)
    return res
