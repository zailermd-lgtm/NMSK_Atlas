"""Q191 audit of every hand / wrist structure of the female Z-Anatomy viewer against HER own data.

    python3 scripts/zanatomy/q191_audit.py --npz /tmp/q191/after_q190.npz --label before   (pre-decimation, has the Z source -> stretch)
    python3 scripts/zanatomy/q191_audit.py --viewer build/viewer_zan_female --label v7      (shipped geometry, no stretch)

Per structure (both sides): vertices outside her CT skin / inside her CT hand+forearm bone meshes (right: she has no left hand bones) / inside the
displayed Z hand bones, distance to her own reference (her bone or hand/forearm label mesh; skin: gap to her skin), stretch vs the Z source
(triangles outside 0.67-1.5x of their own median, edge and area), folded edges, volume vs source x body scale^3, overlap with neighbouring hand
muscles, L/R mirror distance.  Only the hand zone of a structure counts (vertices the Q191 field weight puts above 0.02)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q190_metrics as Mx  # noqa: E402
from scripts.zanatomy import q190_refine as Q  # noqa: E402
from scripts.zanatomy import q191_hand as H  # noqa: E402

THRESH = {"outside_skin_pct": 1.0, "inside_bone_pct": 5.0, "stretch_area_pct": 25.0, "folded_edges_pct": 2.0, "label_mm": 4.0, "volume": (0.65, 1.5)}
PUBLISHED_THENAR_CM3 = 13.0     # Naarding 2021 J Cachexia Sarcopenia Muscle 12:694, doi:10.1002/jcsm.12711, 13 controls 9.5-25.4 y, right hand, qMRI total thenar volume
LABEL_ALIAS = {"zan_extensor_pollicis_longus_r": "extensor_pollicis_longus_r", "zan_extensor_pollicis_longus_l": "extensor_pollicis_longus_l"}
NOT_BODY = Q.NOT_A_MUSCLE_BODY


def group_of(i: str, cat: str) -> str:
    if cat == "bone":
        return "bones"
    if cat == "skin":
        return "skin"
    if cat == "vessel":
        return "vessels (arteries/veins/arches)"
    if cat == "nerve":
        return "nerves"
    if re.search(r"retinaculum|aponeurosis|fascia|membrane", i):
        return "retinacula / fascia / aponeurosis"
    if cat in ("ligament", "joint") or re.search(r"ligament|capsule|disc", i):
        return "ligaments / capsules / disc"
    if cat in ("bursa", "tendon") or re.search(r"sheath|bursa", i):
        return "tendon sheaths / bursae"
    if re.search(r"opponens_pollicis|abductor_pollicis_brevis|flexor_pollicis_brevis", i):
        return "intrinsic: thenar"
    if re.search(r"adductor_pollicis", i):
        return "intrinsic: adductor pollicis"
    if re.search(r"digiti_minimi.*hand|opponens_digiti|palmaris_brevis", i):
        return "intrinsic: hypothenar"
    if re.search(r"lumbrical", i):
        return "intrinsic: lumbricals"
    if re.search(r"interossei", i):
        return "intrinsic: interossei"
    return "extrinsic muscles / tendons crossing the wrist"


def zone(by: dict, raw: dict, side: str, regions: dict):
    """ids + field weights (the Q191 hand zone) of one side"""
    ids_b = H.bone_ids(side)
    rad, uln = f"radius_{side}", f"ulna_{side}"
    c_w, u = H.wrist_frame(raw[rad])
    pts = [raw[i] for i in sum(ids_b.values(), [])]
    for i in (rad, uln):
        pts.append(raw[i][(raw[i] - c_w) @ u > -90.0])
    near = cKDTree(np.vstack(pts))
    ids = H.scope([{"mesh_id": k, "cat": by[k]["cat"]} for k in by], regions, side)
    W = {i: H.field_weight(raw[i].astype(float), c_w, u, near) for i in ids}
    ids = [i for i in ids if W[i].max() > 0.02]
    hb = sum(ids_b.values(), [])
    return ids, {i: W[i] > 0.02 for i in ids}, hb


def audit(by: dict, raw: dict, her: dict, skin, regions: dict, with_stretch=True, log=print) -> dict:
    """by {id: {v, f, cat}}; raw {id: Z source verts} (zone definition, stretch)"""
    skin_tree = cKDTree(np.asarray(skin.vertices, float))
    out = {}
    her_bones = [H.merged_bones([(her[k]["v"].astype(float), her[k]["f"].astype(int)) for k in list(H.HER_BONES.values()) + list(H.HER_FOREARM_BONES)])]
    for side in "rl":
        ids, act, hb = zone(by, raw, side, regions)
        zb = H.merged_bones([(by[i]["v"].astype(float), by[i]["f"]) for i in hb + [f"radius_{side}", f"ulna_{side}"]])
        ctx = H.Ctx(skin, skin_tree, her_bones if side == "r" else [], [zb])
        for i in ids + hb:
            d = by[i]
            a = act.get(i)
            if a is None:                       # bones: all vertices
                a = np.ones(len(d["v"]), bool)
            v = d["v"].astype(float)
            m = H.struct_metrics(v, raw[i].astype(float), d["f"], ctx, a) if with_stretch else {}
            if not with_stretch:
                P = v[a]
                m = {"outside_her_skin_pct": round(100 * float((~skin.contains(P)).mean()), 2),
                     "inside_z_bone_pct": round(100 * float((zb.depth(P) > 1.5).mean()), 2)}
                if side == "r":
                    m["inside_her_bone_pct"] = round(100 * float((her_bones[0].depth(P) > 1.5).mean()), 2)
            row = {"side": side, "cat": d["cat"], "group": group_of(i, d["cat"]), "vertices": int(len(v)), "zone_vertices": int(a.sum()), **m}
            gap = skin_tree.query(v[a])[0]
            if row.get("outside_her_skin_pct", 0) > 0:
                o = ~skin.contains(v[a])
                row["outside_her_skin_max_mm"] = round(float(gap[o].max()), 1) if o.any() else 0.0
            row["median_gap_to_her_skin_mm"] = round(float(np.median(gap)), 2)
            # distance to her own reference
            if side == "r":
                ref_id = None
                if d["cat"] == "bone":
                    ref_id = H.HER_BONES["carpals"] if i in H.bone_ids("r")["carpals"] else H.HER_BONES["phal"] if i in H.bone_ids("r")["phal"] else \
                        H.HER_BONES[f"mc{H.bone_ids('r')['mc'].index(i) + 1}"] if i in H.bone_ids("r")["mc"] else None
                else:
                    ref_id = LABEL_ALIAS.get(i, i)
                    ref_id = ref_id if ref_id in her and her[ref_id]["cat"] == "muscle" else None
                if ref_id:
                    rv, rf = her[ref_id]["v"].astype(float), her[ref_id]["f"].astype(int)
                    tr = cKDTree(Q.Ref(rv, rf).pts)
                    row["her_reference"] = ref_id
                    row["dist_to_her_reference_mm"] = round(float(np.median(tr.query(v[a])[0])), 2)       # zone vertices -> her surface
                    if i in H.HAND_LABELS:           # two-way on the ZONE vertices only (the opponens mesh also holds the foot part)
                        P = v[a]
                        row["two_way_median_to_her_reference_mm"] = round(0.5 * (float(np.median(tr.query(P)[0])) + float(np.median(cKDTree(P).query(tr.data)[0]))), 2)
            out[i] = row
    bg = {}
    b_ = H.bone_ids("r")
    for name, zids, hid in [("carpals", b_["carpals"], H.HER_BONES["carpals"]), ("phalanges", b_["phal"], H.HER_BONES["phal"])] + \
            [(f"metacarpal_{k + 1}", [b_["mc"][k]], H.HER_BONES[f"mc{k + 1}"]) for k in range(5)]:
        hv, hf = her[hid]["v"].astype(float), her[hid]["f"].astype(int)
        zp = np.vstack([H.surf_pts(by[i]["v"].astype(float), by[i]["f"], 900) for i in zids])
        c = H.chamfer2(zp, H.surf_pts(hv, hf, 6000))
        bg[name] = {"z_to_her_mm": round(c[0], 2), "her_to_z_mm": round(c[1], 2), "two_way_median_mm": round(c[2], 2)}
    # neighbour overlap among hand muscles (closed meshes), per side
    import trimesh
    for side in "rl":
        mus = [i for i in out if out[i]["side"] == side and out[i]["cat"] == "muscle" and Q._closed(by[i]["f"]) and not NOT_BODY.search(i) and "extrinsic" not in out[i]["group"]]
        meshes = {i: trimesh.Trimesh(by[i]["v"], by[i]["f"], process=False) for i in mus}
        for i in mus:
            P = by[i]["v"][::3]
            ins = np.zeros(len(P), bool)
            for k, m in meshes.items():
                if k == i:
                    continue
                lo, hi = m.bounds
                sel = np.flatnonzero(np.all((P >= lo - 1) & (P <= hi + 1), 1) & ~ins)
                if len(sel):
                    try:
                        ins[sel[m.contains(P[sel])]] = True
                    except Exception:
                        pass
            out[i]["inside_other_hand_muscle_pct"] = round(100 * float(ins.mean()), 2)
    # L/R mirror distance (mirror about x = 0: the Z source is symmetric about it)
    for i in list(out):
        if out[i]["side"] != "l":
            continue
        j = re.sub(r"_l(_\d+)?$", lambda m: "_r" + (m.group(1) or ""), i)
        if j in out and by[i]["cat"] != "skin":
            vl = by[i]["v"].astype(float).copy()
            vl[:, 0] *= -1
            a, b = Mx.two_way(vl, by[i]["f"][:, [0, 2, 1]], by[j]["v"].astype(float), by[j]["f"], n=2000)
            out[i]["mirror_to_right_mm"] = round(0.5 * (a + b), 1)
    # volumes
    thenar = 0.0
    for i, r in out.items():
        if "volume_ratio_vs_source" in r:
            vol = abs(Q.volume(by[i]["v"].astype(float), by[i]["f"])) / 1000.0
            r["volume_cm3"] = round(vol, 2)
            if raw.get(i) is not None and r["group"] == "intrinsic: thenar" and r["side"] == "r":
                thenar += vol
    out["_bone_groups_right_vs_her_ct"] = bg
    out["_thenar_right_volume_cm3"] = {"value": round(thenar, 2), "published_cm3": PUBLISHED_THENAR_CM3, "ratio": round(thenar / PUBLISHED_THENAR_CM3, 2),
                                      "size_caveat_1.5x": bool(thenar > 1.5 * PUBLISHED_THENAR_CM3),
                                      "ref": "Naarding KJ et al. J Cachexia Sarcopenia Muscle 2021;12:694-703, doi:10.1002/jcsm.12711 (13 controls, qMRI, right hand); other intrinsic muscles: no published volume verified"}
    return out


def issues(tab: dict) -> dict:
    """counts of what is wrong, by criterion and by group"""
    rows = {k: v for k, v in tab.items() if not k.startswith("_")}
    crit = {
        "outside_her_skin > 1 %": lambda r: r.get("outside_her_skin_pct", 0) > THRESH["outside_skin_pct"],
        "inside her bone > 5 % (muscle/nerve/vessel/fascia)": lambda r: r["cat"] in ("muscle", "nerve", "vessel", "fascia", "tendon") and r.get("inside_her_bone_pct", r.get("inside_z_bone_pct", 0)) > THRESH["inside_bone_pct"],
        "stretch (area outside 0.67-1.5x) > 25 %": lambda r: r.get("stretch_area_outside_0.67_1.5_pct", 0) > THRESH["stretch_area_pct"],
        "folded edges > 2 %": lambda r: r.get("folded_edges_pct", 0) > THRESH["folded_edges_pct"],
        "distance to her label > 4 mm (labelled intrinsic)": lambda r: r.get("two_way_median_to_her_reference_mm", 0) > THRESH["label_mm"] and r["cat"] == "muscle",
        "bone zone > 3 mm from her CT bone (median, Z->her)": lambda r: r["cat"] == "bone" and r.get("dist_to_her_reference_mm", 0) > 3.0,
        "volume outside 0.65-1.5x of source (closed muscles)": lambda r: r["cat"] == "muscle" and "volume_ratio_vs_source" in r and not (0.65 <= r["volume_ratio_vs_source"] <= 1.5),
        "inside another hand muscle > 10 %": lambda r: r.get("inside_other_hand_muscle_pct", 0) > 10.0,
    }
    out = {"structures": len(rows), "by_criterion": {}, "by_group": {}}
    for k, f in crit.items():
        for s in "rl":
            sel = [i for i, r in rows.items() if r["side"] == s and f(r)]
            out["by_criterion"].setdefault(k, {})[s] = len(sel)
    for s_ in "rl":
        for g in sorted({r["group"] for r in rows.values() if r["side"] == s_}):
            gg = [r for r in rows.values() if r["group"] == g and r["side"] == s_]

            def mean(key):
                v = [r[key] for r in gg if key in r]
                return round(float(np.mean(v)), 2) if v else None
            out["by_group"].setdefault(g, {})[s_] = {"n": len(gg), "mean_outside_her_skin_pct": mean("outside_her_skin_pct"), "mean_inside_her_bone_pct": mean("inside_her_bone_pct"),
                                                      "mean_inside_z_bone_pct": mean("inside_z_bone_pct"), "mean_stretch_area_pct": mean("stretch_area_outside_0.67_1.5_pct"),
                                                      "mean_folded_edges_pct": mean("folded_edges_pct"), "mean_two_way_to_her_reference_mm": mean("two_way_median_to_her_reference_mm"),
                                                      "mean_dist_zone_to_her_reference_mm": mean("dist_to_her_reference_mm"), "mean_gap_to_her_skin_mm": mean("median_gap_to_her_skin_mm"),
                                                      "mean_inside_other_hand_muscle_pct": mean("inside_other_hand_muscle_pct")}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz")
    ap.add_argument("--viewer")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes, DEFAULT_REPORT
    her, skin = load_her_meshes(), load_skin("vhf")
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    if args.npz:
        L = Mx.load_dump(args.npz)
        by = {d["id"]: {"v": d["v"], "f": d["f"], "cat": d["cat"]} for d in L}
        raw = {d["id"]: d["r"] for d in L}
        tab = audit(by, raw, her, skin, regions, with_stretch=True)
    else:
        from scripts.zanatomy import trunk_refit_q186c_audit as A186
        M = A186.load_viewer(Path(args.viewer))
        by = {k: {"v": m["v"], "f": m["f"], "cat": m["sys"]} for k, m in M.items()}
        # zone definition needs the Z source frame: take it from the dump of the same ids (identical for every build)
        z = {d["id"]: d["r"] for d in Mx.load_dump(args.npz or "/tmp/q191/after_q190.npz")}
        raw = {k: z[k] for k in by if k in z}
        by = {k: v for k, v in by.items() if k in raw}
        tab = audit(by, raw, her, skin, regions, with_stretch=False)
    res = {"label": args.label, "thresholds": THRESH, "table": tab, "issues": issues(tab)}
    out = Path(args.out or REPO / "data" / "derived" / f"Q191_hand_audit_{args.label}.json")
    out.write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res["issues"], indent=1))


if __name__ == "__main__":
    main()
