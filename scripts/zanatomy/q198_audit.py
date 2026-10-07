#!/usr/bin/env python3
"""Q198 READ-ONLY anatomy audit of one q197 page: continuity / in-place checks per junction, per side.
    python3 scripts/zanatomy/q198_audit.py MODEL [--joints elbow,shoulder,...]   -> data/derived/Q198_model_<MODEL>.json
MODEL in own_m own_f z_male z_base_f z_male_fit z_female_fit (one page at a time: ~3 GB peak)."""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy.q198_load import load, MODELS  # noqa: E402
from scripts.zanatomy.q198_core import Grid, SkinField, SkinSurf, weld, boundary_loops, loop_stats, pca, surf_points, tri_area  # noqa: E402
from scripts.zanatomy.q198_joints import find_joints  # noqa: E402
from scripts.zanatomy import q198_soft as SO  # noqa: E402

OUT = REPO / "data" / "derived"
SOFT_SYS_OWN = {"muscle", "tendon", "ligament", "fascia", "cartilage"}
SOFT_SYS_Z = {"muscle", "joint", "fascia", "bursa", "insertion", "cartilage"}
TUBE_SYS = {"vessel", "nerve"}


def own_classes(S):
    sys.path.insert(0, str(REPO / "scripts"))
    import audit_q189_model_separation as Q
    for s in S:
        s["cls"] = Q.classify(s["src"], (s.get("rec") or {}).get("procedural_badge"))[0]
    return S


def female_sealers(key, S):
    """the two male skin patches (urogenital region) that the female variants delete leave a hole in the skin envelope; for the ENVELOPE ONLY (never audited)
    they are re-added: base page = in place (same frame as the male base); fitted page = warped by the IDW displacement of the matched base->fitted skin vertices."""
    if key not in ("z_base_f", "z_female_fit"):
        return []
    M = load("z_male")
    pt = [m for m in M if m["id"] in ("zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r")]
    out = [dict(id=m["id"], sys="skin", v=m["v"].copy(), f=m["f"]) for m in pt]
    if key == "z_female_fit":
        Bf = load("z_base_f"); bi = {b["id"]: b for b in Bf}; fi = {x["id"]: x for x in S}
        ids = [i for i in bi if bi[i]["sys"] == "skin" and i in fi and len(bi[i]["v"]) == len(fi[i]["v"])]
        V = np.concatenate([bi[i]["v"] for i in ids]); W = np.concatenate([fi[i]["v"] for i in ids]) - V
        tr = cKDTree(V)
        for o in out:
            d, ix = tr.query(o["v"], k=10)
            w = 1.0 / np.maximum(d, 1.0) ** 2
            o["v"] = o["v"] + (W[ix] * w[..., None]).sum(1) / w.sum(1, keepdims=True)
    return out


def seam_planes(S, minn=3):
    """axis-aligned flat cut faces over ALL structures; clusters of >= minn structures cut in the same plane (+-1 mm) = a data-block seam"""
    from scripts.zanatomy.q198_core import flat_caps
    rows = []
    for s in S:
        if s["sys"] == "skin" or s["id"] == "skin" or len(s["f"]) < 8:
            continue
        v, f = weld(s["v"], s["f"])
        for cp in flat_caps(v, f, minarea=60.0):
            rows.append((s["id"], s["sys"], s["side"], cp["axis"], cp["plane_mm"], cp["area_mm2"], np.asarray(cp["centre"]), s.get("src")))
    out = []
    for ax in "xyz":
        rr = sorted([r for r in rows if r[3] == ax], key=lambda r: r[4])
        i = 0
        while i < len(rr):
            j = i
            while j + 1 < len(rr) and rr[j + 1][4] - rr[i][4] <= 1.0:
                j += 1
            grp = rr[i:j + 1]
            if len({g[0] for g in grp}) >= minn:
                ctr = np.mean([g[6] for g in grp], 0)
                out.append({"axis": ax, "plane_mm": round(float(np.mean([g[4] for g in grp])), 1), "n_structures": len({g[0] for g in grp}), "total_area_mm2": round(sum(g[5] for g in grp), 0),
                            "centre_mm": np.round(ctr, 0).tolist(), "ids": sorted({g[0] for g in grp})[:14], "sys": sorted({g[1] for g in grp}), "src": sorted({str(g[7]) for g in grp})[:4]})
            i = j + 1
    return sorted(out, key=lambda x: -x["n_structures"])[:25]


def make_bonefill(J, bones_by_id, h=1.5):
    c, R = J["centre"], J["R"]
    g = Grid(c - (R + 40), c + (R + 40), h)
    sols = {}
    for bid, b in bones_by_id.items():
        v = b["v"]
        if (np.linalg.norm(v - c, axis=1) < R + 60).any():
            sols[bid] = g.solid(v, b["f"], close=1)
    uni = np.zeros(g.shape, bool)
    for s in sols.values():
        uni |= s
    depth = ndi.distance_transform_edt(uni, sampling=h).astype(np.float32)

    def fn(p):
        d, ok = g.lookup(depth, p)
        return d > 0, d
    fn.g, fn.sols, fn.h = g, sols, h
    return fn


def bone_pair_metrics(J, bonesd, bf, bfill):
    pr = [b for b in J["prox"]]; di = [b for b in J["dist"]]
    gap = float("inf")
    for a in pr:
        for b in di:
            d = bf.tree[a].query(bf.pts[b])[0]
            gap = min(gap, float(d.min()))
    # pairwise penetration between each prox bone and each dist bone
    pen = []
    for a in pr:
        for b in di:
            if a in bfill.sols and b in bfill.sols:
                ov = bfill.sols[a] & bfill.sols[b]
                if ov.any():
                    da = ndi.distance_transform_edt(bfill.sols[a], sampling=bfill.h); db = ndi.distance_transform_edt(bfill.sols[b], sampling=bfill.h)
                    dep = np.minimum(da, db)[ov]
                    pen.append({"a": a, "b": b, "vol_mm3": round(float(ov.sum() * bfill.h ** 3), 1), "max_depth_mm": round(float(dep.max()), 2)})
    # between the two distal bones (radius/ulna) overlap also matters
    if len(di) == 2 and all(x in bfill.sols for x in di):
        ov = bfill.sols[di[0]] & bfill.sols[di[1]]
        if ov.any():
            da = ndi.distance_transform_edt(bfill.sols[di[0]], sampling=bfill.h); db = ndi.distance_transform_edt(bfill.sols[di[1]], sampling=bfill.h)
            pen.append({"a": di[0], "b": di[1], "vol_mm3": round(float(ov.sum() * bfill.h ** 3), 1), "max_depth_mm": round(float(np.minimum(da, db)[ov].max()), 2)})
    return {"surface_gap_mm": round(gap, 2), "penetrations": pen,
            "max_penetration_mm": max([p["max_depth_mm"] for p in pen], default=0.0),
            "penetration_vol_mm3": round(sum(p["vol_mm3"] for p in pen), 1)}


def shaft_axis(v, c_joint, frac=(0.2, 0.8)):
    cc, vt, sv = pca(v)
    ax = vt[0]
    t = (v - cc) @ ax
    lo, hi = t.min(), t.max()
    m = (t > lo + frac[0] * (hi - lo)) & (t < lo + frac[1] * (hi - lo))
    c2, vt2, _ = pca(v[m])
    ax = vt2[0]
    # orient: from the far end towards the joint
    far = v[(t < lo + 0.1 * (hi - lo))].mean(0) if np.linalg.norm(v[t < lo + 0.1 * (hi - lo)].mean(0) - c_joint) > np.linalg.norm(v[t > hi - 0.1 * (hi - lo)].mean(0) - c_joint) else v[(t > hi - 0.1 * (hi - lo))].mean(0)
    if np.dot(c_joint - far, ax) < 0:
        ax = -ax
    return c2, ax, far


def elbow_angles(J, B, side):
    h = B[("humerus", side)][0]["v"]; ul = B[("ulna", side)][0]["v"]; ra = B[("radius", side)][0]["v"]
    c = J["centre"]
    hc, hax, hfar = shaft_axis(h, c)                # shoulder -> elbow
    uc, uax_toward_elbow, ufar = shaft_axis(ul, c)  # wrist -> elbow
    fax = -uax_toward_elbow                          # elbow -> wrist
    rc, rax_toe, rfar = shaft_axis(ra, c); rfax = -rax_toe
    # epicondylar axis: distal 15% of humerus, widest direction perpendicular to shaft
    t = (h - hc) @ hax
    dist_end = h[t > t.max() - 0.15 * (t.max() - t.min())]
    perp = dist_end - np.outer((dist_end - dist_end.mean(0)) @ hax, hax)
    _, vtp, _ = pca(perp)
    e = vtp[0] - np.dot(vtp[0], hax) * hax; e /= np.linalg.norm(e)
    lateral = np.array([-1.0, 0, 0]) if side == "l" else np.array([1.0, 0, 0])
    if np.dot(e, lateral) < 0:
        e = -e
    n = np.cross(e, hax); n /= np.linalg.norm(n)
    # flexion: angle between continuation of the humerus axis and the forearm axis, in the plane perpendicular to e
    fp = fax - np.dot(fax, e) * e
    flex = np.degrees(np.arctan2(abs(np.dot(fp, n)), np.dot(fp, hax)))
    carry = np.degrees(np.arcsin(np.clip(np.dot(fax, e) / np.linalg.norm(fax), -1, 1)))   # +: forearm deviates laterally
    # ulna transverse axis: smallest-variance direction of the proximal 25 % of the ulna
    tu = (ul - uc) @ fax
    prox = ul[tu < tu.min() + 0.25 * (tu.max() - tu.min())]
    _, vtu, svu = pca(prox)
    eu = vtu[2] - np.dot(vtu[2], fax) * fax; eu /= np.linalg.norm(eu)
    ep = e - np.dot(e, fax) * fax; ep /= np.linalg.norm(ep)
    twist = np.degrees(np.arccos(np.clip(abs(np.dot(eu, ep)), 0, 1)))
    # axis offset at the joint plane
    def lineproj(p, a0, ax): return a0 + np.dot(p - a0, ax) * ax
    off = float(np.linalg.norm(lineproj(c, hc, hax) - lineproj(c, uc, fax)))
    return {"flexion_deg": round(float(flex), 1), "carrying_deg_lateral_positive": round(float(carry), 1), "ulna_vs_epicondylar_twist_deg": round(float(twist), 1),
            "humerus_forearm_axis_offset_mm": round(off, 1), "radius_ulna_axis_angle_deg": round(float(np.degrees(np.arccos(np.clip(np.dot(fax, rfax), -1, 1)))), 1),
            "humerus_axis": np.round(hax, 3).tolist(), "forearm_axis": np.round(fax, 3).tolist(), "epicondylar_axis": np.round(e, 3).tolist()}


def skin_profile(skin_structs, J, half=90.0, dt=3.0):
    """cross-sections of the skin surface (all shells of all patches) perpendicular to the junction axis, the outline containing the axis point
    (largest polygon): equivalent radius and centroid per slice -> steps between neighbouring slices; slices with no closed outline = holes"""
    import trimesh
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union, polygonize
    Vs, Fs, off = [], [], 0
    c0 = J["centre"]
    for s_ in skin_structs:
        if (np.linalg.norm(s_["v"] - c0, axis=1) < half + 120).any():
            Vs.append(s_["v"]); Fs.append(s_["f"] + off); off += len(s_["v"])
    if not Vs:
        return {}
    V = np.concatenate(Vs); F = np.concatenate(Fs)
    c, a = J["centre"], J["axis"]
    rows = []
    for t in np.arange(-half, half + 0.1, dt):
        seg = trimesh.intersections.mesh_plane(trimesh.Trimesh(V, F, process=False), a, c + t * a, return_faces=False)
        if len(seg) == 0:
            rows.append((t, np.nan, np.nan, np.nan, 0)); continue
        u = np.cross(a, [1, 0, 0]); u /= np.linalg.norm(u); w = np.cross(a, u)
        s2 = np.stack([((seg - (c + t * a)) @ u), ((seg - (c + t * a)) @ w)], axis=-1)
        import shapely
        lines = unary_union([shapely.set_precision(LineString(x), 2.0) for x in s2 if np.linalg.norm(x[0] - x[1]) > 1e-6])
        polys = [p for p in polygonize(lines) if p.contains(Point(0, 0))]
        if not polys:
            rows.append((t, np.nan, np.nan, np.nan, 1)); continue
        pl = max(polys, key=lambda p: p.area)
        rows.append((t, float(np.sqrt(pl.area / np.pi)), pl.centroid.x, pl.centroid.y, 0))
    r = np.array(rows)
    ok = ~np.isnan(r[:, 1])
    out = {"slices": int(len(r)), "valid": int(ok.sum()), "open_or_missing_sections": int((r[:, 4] > 0).sum())}
    if ok.sum() > 6:
        rr, cu, cw = r[ok, 1], r[ok, 2], r[ok, 3]
        dr = np.abs(np.diff(rr)); dc = np.hypot(np.diff(cu), np.diff(cw))
        out.update({"max_radius_step_mm_per_3mm": round(float(dr.max()), 2), "max_centroid_step_mm_per_3mm": round(float(dc.max()), 2),
                    "radius_range_mm": [round(float(rr.min()), 1), round(float(rr.max()), 1)],
                    "steps_gt3mm": int(((dr > 3) | (dc > 3)).sum()), "at_t_mm": round(float(r[ok][:-1][np.argmax(np.maximum(dr, dc)), 0]), 1)})
    return out


def zone_ids(S, J, sysset, sidef=True, minv=3):
    c, R = J["centre"], J["R"]
    out = []
    for s in S:
        if s["sys"] not in sysset:
            continue
        if sidef and J["side"] in ("l", "r") and s["side"] not in (J["side"], "m"):
            continue
        d = np.linalg.norm(s["v"] - c, axis=1)
        if (d < R).sum() >= minv:
            out.append(s)
    return out


CHAINS = [("brachial_artery", "radial_artery"), ("brachial_artery", "ulnar_artery"), ("brachial_veins", "radial_veins"), ("brachial_veins", "ulnar_veins"),
          ("musculocutaneous_n", "lateral_antebrachial_cutaneous_nerve"), ("radial_n", "radial_n_superficial_branch"), ("radial_n", "posterior_interosseous_nerve_of_forearm"),
          ("median_cubital_vein", "basilic_vein"), ("median_cubital_vein", "cephalic_vein"), ("ulnar_artery", "common_interosseous_artery"),
          ("ulnar_n", "ulnar_n_deep_branch"), ("median_n_lateral_root", "anterior_interosseous_n"), ("brachial_artery", "radial_collateral_artery")]


def find_by_stem(byid, stem, side):
    for pre in ("zan_", ""):
        for suf in (f"_{side}",):
            k = f"{pre}{stem}{suf}"
            if k in byid:
                return byid[k]
    return None


def chain_checks(byid, side):
    out = []
    for p, ch in CHAINS:
        a, b = find_by_stem(byid, p, side), find_by_stem(byid, ch, side)
        if a is None or b is None:
            out.append({"parent": p, "child": ch, "present": [a is not None, b is not None]})
            continue
        va, fa = weld(a["v"], a["f"]); vb, fb = weld(b["v"], b["f"])
        ca, _, _, _ = SO.graph_levels(va, fa); cb, _, _, _ = SO.graph_levels(vb, fb)
        ends_a, ends_b = np.array([ca[0], ca[-1]]), np.array([cb[0], cb[-1]])
        dee = np.linalg.norm(ends_a[:, None] - ends_b[None], axis=2)
        dvv = cKDTree(va).query(vb)[0].min()
        out.append({"parent": a["id"], "child": b["id"], "end_to_end_mm": round(float(dee.min()), 1), "min_surface_vertex_mm": round(float(dvv), 1)})
    return out


def audit_junction(S, byid, J, B, skin, bf, kind, only_flags, skin_structs=None):
    c, R = J["centre"], J["R"]
    bones_by_id = {s["id"]: s for s in S if s["sys"] == "bone"}
    bfill = make_bonefill(J, bones_by_id)
    rec = {"name": J["name"], "side": J["side"], "centre_mm": np.round(c, 1).tolist(), "axis": np.round(J["axis"], 3).tolist(), "R": R}
    rec["bones"] = bone_pair_metrics(J, bones_by_id, bf, bfill)
    if J["name"] == "elbow":
        try:
            rec["elbow_angles"] = elbow_angles(J, B, J["side"])
        except Exception as ex:  # noqa
            rec["elbow_angles"] = {"error": repr(ex)}
    rec["skin"] = skin_profile(skin_structs, J, half=min(90, R)) if J["name"] in ("elbow", "wrist", "knee", "ankle", "shoulder") else {}
    softsys = SOFT_SYS_OWN if kind == "own" else SOFT_SYS_Z
    soft, tubes = [], []
    for s in zone_ids(S, J, softsys):
        expb = SO.expected_bones(s["id"]) if J["name"] == "elbow" else None
        try:
            soft.append(SO.analyse_belly(s, J, bf, skin, bfill, expb=expb, near_end_R=R))
        except Exception as ex:  # noqa
            soft.append({"id": s["id"], "error": repr(ex)})
    for s in zone_ids(S, J, TUBE_SYS):
        try:
            tubes.append(SO.analyse_tube(s, J, bf, skin, bfill))
        except Exception as ex:  # noqa
            tubes.append({"id": s["id"], "error": repr(ex)})
    rec["soft"] = soft; rec["tubes"] = tubes
    rec["zone_ids"] = sorted({x["id"] for x in zone_ids(S, J, softsys | TUBE_SYS | {"bone"})})
    # bones in the zone: flat cut faces / islands (a bone cut at a data-block edge)
    bl = []
    for b in zone_ids(S, J, {"bone"}):
        try:
            r_ = SO.analyse_belly(b, J, bf, skin, bfill, expb=None, near_end_R=R)
            bl.append({k: r_.get(k) for k in ("id", "src", "cls", "nv", "islands", "main_area_share", "max_island_gap_mm", "flat_caps", "open_edge_frac", "length_mm", "end_prox_mm", "end_dist_mm", "outside_skin_pct")})
        except Exception as ex:  # noqa
            bl.append({"id": b["id"], "error": repr(ex)})
    rec["bones_detail"] = bl
    # soft-tissue interpenetration among muscles in the zone (voxel solids, 1.5 mm): share of each muscle's volume that lies inside another muscle
    try:
        mus = [m for m in zone_ids(S, J, {"muscle"})]
        g = bfill.g; cnt = np.zeros(g.shape, np.int8); sol = {}
        for m in mus:
            sv = g.solid(m["v"], m["f"], close=1); sol[m["id"]] = sv; cnt += sv
        ov = {}
        for mid, sv in sol.items():
            n = int(sv.sum())
            if n > 200:
                ov[mid] = {"vol_cm3": round(n * g.h ** 3 / 1000, 1), "overlap_pct": round(100 * float(((cnt > 1) & sv).sum()) / n, 1)}
        rec["muscle_overlap"] = ov
    except Exception as ex:  # noqa
        rec["muscle_overlap"] = {"error": repr(ex)}
    if J["name"] == "elbow" and kind == "zan":
        rec["chains"] = chain_checks(byid, J["side"])
    # bones in zone: outside skin / soft overlap are reported per structure above
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("--joints", default="")
    a = ap.parse_args()
    t0 = time.time()
    key = a.model
    kind = MODELS[key][2]
    S = load(key)
    if kind == "own":
        own_classes(S)
    byid = {}
    for s in S:
        byid.setdefault(s["id"], s)
    J, B, lev = find_joints(S)
    only = set(x for x in a.joints.split(",") if x)
    skin_structs = [s for s in S if s["sys"] == "skin" or s["id"] == "skin"]
    skin = SkinField(skin_structs + female_sealers(key, S), 3.0, close=1 if kind == "own" else 2)
    bones = [s for s in S if s["sys"] == "bone"]
    bf = SO.BoneField(bones)
    res_seams = seam_planes(S) if not only else []
    res = {"seam_planes": res_seams, "missing_joints": B.get("_missing", []), "model": key, "label": MODELS[key][3], "kind": kind, "n_structures": len(S), "skin_volume_L": round(skin.vol_L, 1), "junctions": []}
    for j in J:
        if only and j["name"] not in only:
            continue
        tj = time.time()
        r = audit_junction(S, byid, j, B, skin, bf, kind, only, skin_structs)
        res["junctions"].append(r)
        print(f"{key} {j['name']}{j['side']} done {time.time()-tj:.0f}s", flush=True)
    (OUT / f"Q198_model_{key}{'_' + '+'.join(sorted(only)) if only else ''}.json").write_text(json.dumps(res, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o)))
    print("total", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
