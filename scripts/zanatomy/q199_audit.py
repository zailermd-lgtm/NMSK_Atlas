"""Q199 audit of the ELBOW (both arms): numbers before -> after, on the SHIPPED meshes of two viewer directories (or two full-resolution dumps).

    python3 scripts/zanatomy/q199_audit.py [--before build/viewer_zan_female] [--after build/viewer_zan_female_q199] [--report data/derived/Q199_zan_female_q199_build.json]
                                           [--out data/derived/Q199_elbow_audit.json] [--ship-diff data/derived/Q199_ship_diff.json]

  joint        nearest-surface gap at the humerus - radius / ulna contact patch (the Z-source patch), pair-distance change
  attachments  per muscle crossing the elbow: median distance of its Z-source origin / insertion footprint (vertices < 8 mm from the bone in the Z source) to that bone, source / before / after
  continuity   structure pairs that touch in the Z source (< 3 mm): gap before / after (count of gaps > 5 mm); the vessel / nerve pairs separately (centreline jumps)
  containment  vertices outside her skin, inside the displayed humerus / radius / ulna (> 1.5 mm), moved soft structures
  skin seams   adjacent skin patches of the elbow: the step between their shared border
  ship diff    every structure vertex by vertex: unchanged (<= 0.05 mm) vs changed, changed ones must be listed in the build report
"""
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
from scripts.zanatomy import q199_elbow as E  # noqa: E402

ELBOW_BOX = {"l": (np.array([-330.0, 250.0, -160.0]), np.array([-130.0, 420.0, 80.0])), "r": (np.array([130.0, 250.0, -160.0]), np.array([330.0, 420.0, 80.0]))}
SOFT = ("muscle", "tendon", "ligament", "fascia", "vessel", "nerve", "bursa", "cartilage", "lymphatic")
CONT_CATS = ("muscle", "tendon", "ligament", "fascia", "vessel", "nerve", "bursa", "cartilage")


def to_M(by_or_M, key="sys"):
    return by_or_M


def cat_of(d):
    return d.get("sys") or d.get("cat")


def in_box(v, side, pad=0.0):
    lo, hi = ELBOW_BOX[side]
    c = v.mean(0)
    return bool(np.all(v.max(0) >= lo - pad) and np.all(v.min(0) <= hi + pad)) and bool(np.all(c >= lo - 60) and np.all(c <= hi + 60))


def elbow_ids(M, raw, side, jc, cats=SOFT, radius=140.0):
    """soft structures of the side with vertices within `radius` mm of the Z-source elbow joint centre (raw frame)"""
    s = "_" + side
    out = []
    for i, d in M.items():
        if not (i.endswith(s) or s + "_" in i) or cat_of(d) not in cats or i not in raw:
            continue
        if np.any(np.linalg.norm(raw[i] - jc, axis=1) < radius):
            out.append(i)
    return out


def attachments(Mb, Ma, raw, side, ids):
    """median distance of the Z-source attachment footprint of each muscle to the humerus / radius / ulna, source (x body scale) / before / after"""
    from scripts.zanatomy import q190_metrics as Mx
    s = "_" + side
    bones = {n: n + s for n in ("humerus", "radius", "ulna")}
    smp = {n: E.bary_samples(raw[b], Mb[b]["f"], 4000) for n, b in bones.items()}
    src = {n: cKDTree(E.at(raw[b], smp[n])) for n, b in bones.items()}
    tb = {n: cKDTree(E.at(Mb[b]["v"], smp[n])) for n, b in bones.items()}
    ta = {n: cKDTree(E.at(Ma[b]["v"], smp[n])) for n, b in bones.items()}
    out = {}
    for i in ids:
        if cat_of(Mb[i]) != "muscle" or len(raw[i]) != len(Mb[i]["v"]) or len(Ma[i]["v"]) != len(raw[i]):
            continue
        row = {}
        for n in bones:
            d0 = src[n].query(raw[i])[0] * Mx.BODY_SCALE
            fp = np.where(d0 < 8.0)[0]
            if len(fp) < 6:
                continue
            row[n] = {"footprint_vertices": int(len(fp)), "source_mm": round(float(np.median(d0[fp])), 1),
                      "before_mm": round(float(np.median(tb[n].query(Mb[i]["v"][fp])[0])), 1), "after_mm": round(float(np.median(ta[n].query(Ma[i]["v"][fp])[0])), 1)}
        if row:
            rec = record_attachments(i)
            if rec:
                exp = [b.rsplit("_", 1)[0] for b in (rec.get("origin_bone"), rec.get("insertion_bone")) if b]
                exp = [b for b in exp if b in ("humerus", "radius", "ulna")]
                row["_atlas_record"] = {"origin_bone": rec.get("origin_bone"), "origin_landmark": rec.get("origin_landmark"), "insertion_bone": rec.get("insertion_bone"),
                                        "insertion_landmark": rec.get("insertion_landmark"), "expected_on_elbow_bones": exp,
                                        "expected_footprint_found_in_Z_source": [b for b in exp if b in row],
                                        "after_gap_within_source_plus_3mm": [b for b in exp if b in row and row[b]["after_mm"] <= row[b]["source_mm"] + 3.0]}
            out[i] = row
    return out


def record_attachments(mid):
    """the atlas record's attachments block (data/muscles/*/<id>.json), if the Z id has one"""
    for p in (REPO / "data" / "muscles").glob(f"*/{mid}.json"):
        try:
            return json.loads(p.read_text()).get("attachments")
        except (OSError, ValueError):
            return None
    return None


def continuity(Mb, Ma, raw, side, ids, jc, touch_mm=3.0):
    """pairs of elbow structures that touch in the Z source (< touch_mm between vertex sets): gap now (min distance of the vertex sets, shipped meshes: surface-sampled)"""
    from scripts.zanatomy import q191_hand as H
    S = {}
    for i in ids:
        if cat_of(Mb[i]) in CONT_CATS and len(raw[i]) > 3:
            S[i] = i
    ids = list(S)
    rt = {i: cKDTree(raw[i][::max(1, len(raw[i]) // 1500)]) for i in ids}
    pts_b = {i: H.surf_pts(Mb[i]["v"], Mb[i]["f"], 1500) for i in ids}
    pts_a = {i: H.surf_pts(Ma[i]["v"], Ma[i]["f"], 1500) for i in ids}
    tb = {i: cKDTree(pts_b[i]) for i in ids}
    ta = {i: cKDTree(pts_a[i]) for i in ids}
    rows = []
    for a_ in range(len(ids)):
        for b_ in range(a_ + 1, len(ids)):
            i, j = ids[a_], ids[b_]
            ra = raw[i][::max(1, len(raw[i]) // 1500)]
            dd, _ = rt[j].query(ra)
            k = int(np.argmin(dd))
            d0 = float(dd[k]) * __import__("scripts.zanatomy.q190_metrics", fromlist=["x"]).BODY_SCALE
            if d0 > touch_mm or np.linalg.norm(ra[k] - jc) > E.ELBOW_ZONE_MM:
                continue
            gb = float(tb[j].query(pts_b[i])[0].min())
            ga = float(ta[j].query(pts_a[i])[0].min())
            rows.append({"a": i, "b": j, "cats": f"{cat_of(Mb[i])}/{cat_of(Mb[j])}", "source_mm": round(d0, 2), "before_mm": round(gb, 2), "after_mm": round(ga, 2)})
    return rows


def containment(M, skin, bones, ids):
    from scripts.zanatomy import q191_hand as H
    zb = [H.Inside(M[b]["v"], M[b]["f"]) for b in bones]
    tot = {"vertices": 0, "outside_her_skin": 0, "inside_bone_gt1.5mm": 0}
    per = {}
    for i in ids:
        v = M[i]["v"]
        sel = np.all((v >= -1e9), axis=1)
        o = int((~skin.contains(v)).sum())
        ib = int((np.max([b.depth(v) for b in zb], 0) > 1.5).sum()) if cat_of(M[i]) not in ("ligament", "bursa", "cartilage") else 0
        tot["vertices"] += len(v)
        tot["outside_her_skin"] += o
        tot["inside_bone_gt1.5mm"] += ib
        per[i] = {"outside_skin_pct": round(100 * o / len(v), 2), "inside_bone_pct": round(100 * ib / len(v), 2)}
    tot["outside_her_skin_pct"] = round(100 * tot["outside_her_skin"] / max(1, tot["vertices"]), 3)
    tot["inside_bone_pct"] = round(100 * tot["inside_bone_gt1.5mm"] / max(1, tot["vertices"]), 3)
    return tot, per


def skin_seams(M, raw, side):
    s = "_" + side
    ids = [i for i, d in M.items() if cat_of(d) == "skin" and i.endswith(s) and E.SKIN_ELBOW_RE.search(i)]
    around = [i for i, d in M.items() if cat_of(d) == "skin" and i.endswith(s)]
    d = {i: {"v": M[i]["v"]} for i in around}
    return [r for r in E.skin_seam_rows(d, raw, side, around) if r["a"] in ids or r["b"] in ids]


def summary_gaps(rows):
    b = np.array([r["before_mm"] for r in rows]) if rows else np.zeros(0)
    a = np.array([r["after_mm"] for r in rows]) if rows else np.zeros(0)
    return {"pairs": len(rows), "gap_gt5mm_before": int((b > 5).sum()), "gap_gt5mm_after": int((a > 5).sum()), "mean_gap_before": round(float(b.mean()), 2) if len(b) else None,
            "mean_gap_after": round(float(a.mean()), 2) if len(a) else None, "max_gap_before": round(float(b.max()), 2) if len(b) else None, "max_gap_after": round(float(a.max()), 2) if len(a) else None}


def audit_pair(Mb, Ma, raw, skin, side, log=print, closed=None):
    s = "_" + side
    out = {}
    smp, sel, jj, d0 = E.joint_pairs(raw, side, Mb)
    out["joint"] = {"before": E.joint_stat(smp, sel, jj, d0, Mb["humerus" + s]["v"], Mb["radius" + s]["v"], Mb["ulna" + s]["v"]),
                    "after": E.joint_stat(smp, sel, jj, d0, Ma["humerus" + s]["v"], Ma["radius" + s]["v"], Ma["ulna" + s]["v"])}
    jc = E.at(raw["humerus" + s], smp["humerus"])[sel].mean(0)
    ids = elbow_ids(Ma, raw, side, jc)
    out["n_elbow_structures"] = len(ids)
    att = attachments(Mb, Ma, raw, side, ids)
    out["attachments"] = att
    dev_b = [max(abs(v["before_mm"] - v["source_mm"]) for k, v in r.items() if k != "_atlas_record") for r in att.values()]
    dev_a = [max(abs(v["after_mm"] - v["source_mm"]) for k, v in r.items() if k != "_atlas_record") for r in att.values()]
    out["attachments_summary"] = {"muscles": len(att), "mean_worst_bone_deviation_from_source_before_mm": round(float(np.mean(dev_b)), 2) if dev_b else None,
                                  "after_mm": round(float(np.mean(dev_a)), 2) if dev_a else None, "muscles_dev_gt5mm_before": int(sum(d > 5 for d in dev_b)), "after": int(sum(d > 5 for d in dev_a))}
    rows = continuity(Mb, Ma, raw, side, ids, jc)
    out["continuity_pairs"] = rows
    out["continuity_summary"] = summary_gaps(rows)
    out["centreline_pairs_summary"] = summary_gaps([r for r in rows if re.search(r"vessel|nerve", r["cats"])])
    out["named_centreline_pairs"] = named_centrelines([r for r in rows if re.search(r"vessel|nerve", r["cats"]) and not r["cats"].startswith("muscle") and not r["cats"].endswith("muscle")])
    soft_ids = [i for i in ids if cat_of(Ma[i]) in ("muscle", "vessel", "nerve", "tendon", "fascia")]
    bones = ["humerus" + s, "radius" + s, "ulna" + s]
    cb, perb = containment(Mb, skin, bones, soft_ids)
    ca, pera = containment(Ma, skin, bones, soft_ids)
    out["containment"] = {"before": cb, "after": ca}
    out["containment_worst_after"] = sorted(((k, v["outside_skin_pct"], v["inside_bone_pct"]) for k, v in pera.items()), key=lambda t: -(t[1] + t[2]))[:12]
    try:
        out["muscle_overlap"] = muscle_overlap(Mb, Ma, ids, closed=closed)
    except Exception as e:                                   # a pyembree crash in a worker: once more with the pure-numpy ray tester
        log(f"  overlap audit failed ({e!r}); repeating in safe mode")
        out["muscle_overlap"] = muscle_overlap(Mb, Ma, ids, safe=True, closed=closed)
    sb, sa = skin_seams(Mb, raw, side), skin_seams(Ma, raw, side)
    out["skin_seams"] = {"before": sb, "after": sa}
    return out


def left_photo_compartment(Mb, Ma, y0=345.0, y1=468.0):
    """her left upper arm in her photographs (y 345 .. 468): share of the Z muscle volume inside her photographed muscle compartment (muscle-coloured tissue closed over the fascial
    planes + the humerus, silhouette arm only, q194_forearm.muscle_region), and the distance of the Z humerus section centre to the humerus disc centres of the photographs"""
    from scipy import ndimage as ndi
    from scripts.zanatomy import q194_forearm as F
    P = F.load_photo_masks()
    xs = F.GRID_LO[0] + np.arange(F.GRID_N[0])
    out = {}
    z = np.load(E.EVID)
    shaft = z["shaft_y_x_z"]
    names = [i for i, m in Mb.items() if i.endswith("_l") and m["sys"] == "muscle" and re.search(r"biceps|brachialis|triceps|coracobrachialis|anconeus|brachioradialis", i)
             and "fascia" not in i and "bursa" not in i and "septum" not in i]
    for tag, M in (("before", Mb), ("after", Ma)):
        bone = F.occupancy(M["humerus_l"]["v"], M["humerus_l"]["f"])
        R = F.muscle_region(P, bone, y0, y1)
        R[xs > -170] = False
        U = np.zeros(R.shape, bool)
        for i in names:
            if M[i]["sys"] == "muscle" and len(M[i]["f"]):
                U |= F.occupancy(M[i]["v"], M[i]["f"])
        band = (F.GRID_LO[1] + np.arange(F.GRID_N[1]) >= y0) & (F.GRID_LO[1] + np.arange(F.GRID_N[1]) <= y1)
        Ub, Rb = U[:, band, :], R[:, band, :]
        res = []
        for y, x, zz in shaft:
            if y > y1:
                continue
            c = sec_centre(M["humerus_l"]["v"], M["humerus_l"]["f"], y)
            if c is not None:
                res.append(float(np.hypot(c[0] - x, c[1] - zz)))
        out[tag] = {"muscles": len(names), "muscle_volume_cm3": round(float(Ub.sum()) / 1000, 1), "volume_inside_her_compartment_pct": round(100 * float((Ub & Rb).sum() / max(1, Ub.sum())), 1),
                    "compartment_volume_cm3": round(float(Rb.sum()) / 1000, 1), "humerus_centre_to_photo_disc_mm_mean": round(float(np.mean(res)), 1) if res else None,
                    "humerus_centre_to_photo_disc_mm_max": round(float(np.max(res)), 1) if res else None}
    return out


def sec_centre(v, f, y):
    import trimesh
    s = trimesh.Trimesh(v, f, process=False).section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if s is None:
        return None
    best = None
    for p in s.discrete:
        P = np.asarray(p)[:, [0, 2]]
        x, z = P[:, 0], P[:, 1]
        a = 0.5 * (np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1)))
        if abs(a) > 1e-6 and (best is None or abs(a) > abs(best[0])):
            cx = np.sum((x + np.roll(x, -1)) * (x * np.roll(z, -1) - np.roll(x, -1) * z)) / (6 * a)
            cz = np.sum((z + np.roll(z, -1)) * (x * np.roll(z, -1) - np.roll(x, -1) * z)) / (6 * a)
            best = (a, cx, cz)
    return None if best is None else (best[1], best[2])


def right_label_chamfer(Mb, Ma, her, ids=None, side="r"):
    """right arm: shipped Z muscles vs her own-model labels (CT frame): median surface distance label -> Z (coverage of her label) and Z -> label inside the label's y range"""
    import trimesh
    from scripts.zanatomy import q191_hand as H
    out = {}
    for i in (ids or [k for k in her if k.endswith("_" + side) and her[k]["cat"] == "muscle" and k in Mb]):
        lab = E.at(np.asarray(her[i]["v"], float), E.bary_samples(her[i]["v"], np.asarray(her[i]["f"]), 5000, seed=7))
        y0, y1 = lab[:, 1].min(), lab[:, 1].max()
        tl = cKDTree(lab)
        row = {}
        for tag, M in (("before", Mb), ("after", Ma)):
            Z = H.surf_pts(M[i]["v"], M[i]["f"], 5000)
            row[tag] = {"label_to_Z_median_mm": round(float(np.median(cKDTree(Z).query(lab)[0])), 2),
                        "Z_to_label_median_mm": round(float(np.median(tl.query(Z[(Z[:, 1] >= y0) & (Z[:, 1] <= y1)])[0])), 2) if ((Z[:, 1] >= y0) & (Z[:, 1] <= y1)).any() else None}
        out[i] = row
    return out


def muscle_overlap(Mb, Ma, ids, safe=False, closed=None):
    """neighbour-muscle overlap (q194_separate.overlap_pct: share of sampled vertices lying > MIN_DEPTH_MM inside another muscle of the set), the arm muscles crossing the elbow"""
    from scripts.zanatomy import q190_refine as Q
    from scripts.zanatomy import q194_separate as Sp
    if safe:
        Sp.Skel.SAFE = True
    mus = [i for i in ids if cat_of(Mb[i]) == "muscle" and (i in closed if closed is not None else Q._closed(Mb[i]["f"])) and not Q.NOT_A_MUSCLE_BODY.search(i)]
    out = {}
    for tag, M in (("before", Mb), ("after", Ma)):
        ov = Sp.overlap_pct({i: (M[i]["v"], M[i]["f"]) for i in mus})
        out[tag] = {"muscles": len(mus), "mean_overlap_pct": round(float(np.mean(list(ov.values()))), 2), "max_overlap_pct": round(float(np.max(list(ov.values()))), 2),
                    "muscles_overlap_gt5pct": int(sum(v > 5 for v in ov.values())), "per_muscle": {k: round(float(v), 1) for k, v in ov.items()}}
    return out


NAMED_CENTRELINES = [("brachial_artery", "radial_artery"), ("brachial_artery", "ulnar_artery"), ("brachial_veins", "radial_veins"), ("brachial_veins", "ulnar_veins"),
                     ("radial_n_l|radial_n_r", "radial_n_superficial_branch|posterior_interosseous_n"), ("musculocutaneous_n", "lateral_antebrachial_cutaneous_nerve"),
                     ("median_n_lateral_root", "anterior_interosseous_n|muscular_branches_of_median_nerve"), ("ulnar_n_l|ulnar_n_r", "muscular_branches_of_ulnar_nerve"),
                     ("deep_brachial_artery", "radial_collateral_artery|middle_collateral_artery"), ("brachial_artery", "superior_ulnar_collateral_artery|inferior_ulnar_collateral_artery"),
                     ("common_interosseous_artery", "posterior_interosseous_artery|recurrent_interosseous_artery")]


def named_centrelines(rows):
    """the vessel / nerve pairs that continue each other across the elbow, from the continuity rows (only the pairs that touch in the Z source appear)"""
    out = []
    for pa, pb in NAMED_CENTRELINES:
        for r in rows:
            for x, y in ((r["a"], r["b"]), (r["b"], r["a"])):
                if re.search(pa, x) and re.search(pb, y):
                    out.append({"a": x, "b": y, "source_mm": r["source_mm"], "before_mm": r["before_mm"], "after_mm": r["after_mm"]})
                    break
    return out


def diff(Mb, Ma):
    from scripts.zanatomy import q194_audit as A194
    return A194.diff(Mb, Ma)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_q199"))
    ap.add_argument("--report", default=str(REPO / "data" / "derived" / "Q199_zan_female_q199_build.json"))
    ap.add_argument("--out", default=str(REPO / "data" / "derived" / "Q199_elbow_audit.json"))
    ap.add_argument("--ship-diff", default=str(REPO / "data" / "derived" / "Q199_ship_diff.json"))
    ap.add_argument("--before-dump", default=None, help="the full-resolution state of v12 (the --q194-dump / --q194-dump-after npz of the Q194 build): vertex-by-vertex attachment audit before")
    ap.add_argument("--raw-dump", default=None, help="a full-resolution dump (npz, q190_refine.dump_pending) whose r<i> arrays are the Z source vertices")
    a = ap.parse_args(argv)
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.zanatomy import trunk_refit_q186c_audit as A186
    from scripts.zanatomy import q190_metrics as Mx
    Mb, Ma = A186.load_viewer(Path(a.before)), A186.load_viewer(Path(a.after))
    dump = Mx.load_dump(a.raw_dump)
    raw = {d["id"]: d["r"] for d in dump}
    from scripts.zanatomy import q190_refine as Q190
    closed = {d["id"] for d in dump if Q190._closed(d["f"])}               # the muscle set = the closed meshes at full resolution (the decimated shipped faces are not always watertight)
    skin = load_skin("vhf")
    rep = json.loads(Path(a.report).read_text())
    out = {"left": audit_pair(Mb, Ma, raw, skin, "l", closed=closed), "right": audit_pair(Mb, Ma, raw, skin, "r", closed=closed)}
    out["left"]["photographs"] = left_photo_compartment(Mb, Ma)
    if a.before_dump:                              # the shipped meshes are decimated (no vertex correspondence): the attachment footprints are audited on the full-resolution dumps
        Db, Da = {d["id"]: d for d in Mx.load_dump(a.before_dump)}, {d["id"]: d for d in dump}
        Fb = {i: {"v": d["v"], "f": d["f"], "sys": d["cat"]} for i, d in Db.items()}
        Fa = {i: {"v": Da[i]["v"], "f": Da[i]["f"], "sys": Da[i]["cat"]} for i in Db}
        for side, key in (("l", "left"), ("r", "right")):
            smp, sel, _, _ = E.joint_pairs(raw, side, Fb)
            jc = E.at(raw["humerus_" + side], smp["humerus"])[sel].mean(0)
            ids_f = elbow_ids(Fa, raw, side, jc)
            att = attachments(Fb, Fa, raw, side, ids_f)
            devb = [max(abs(v["before_mm"] - v["source_mm"]) for k, v in r.items() if k != "_atlas_record") for r in att.values()]
            deva = [max(abs(v["after_mm"] - v["source_mm"]) for k, v in r.items() if k != "_atlas_record") for r in att.values()]
            out[key]["attachments_fullres"] = {"summary": {"muscles": len(att), "mean_worst_bone_deviation_from_source_before_mm": round(float(np.mean(devb)), 2), "after_mm": round(float(np.mean(deva)), 2),
                                                           "muscles_dev_gt5mm_before": int(sum(d > 5 for d in devb)), "after": int(sum(d > 5 for d in deva))}, "per_muscle": att}
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    her = load_her_meshes()
    out["right"]["labels"] = right_label_chamfer(Mb, Ma, her)
    out["left"]["arm_labels"] = right_label_chamfer(Mb, Ma, {k: v for k, v in her.items() if k.endswith("_l") and k in ("biceps_brachii_l", "brachialis_l")}, side="l")
    Path(a.out).write_text(json.dumps(out, indent=1, default=float))
    changed, unchanged = diff(Mb, Ma)
    listed = set(rep.get("q199", rep).get("moved_ids", []))
    ship = {"structures": len(Mb), "unchanged_within_0.05mm": unchanged, "changed": len(changed), "changed_but_not_listed_in_report": sorted(k for k in changed if k not in listed),
            "listed_in_report_but_unchanged": sorted(k for k in listed if k not in changed), "changed_detail": changed}
    Path(a.ship_diff).write_text(json.dumps(ship, indent=1))
    print({k: v for k, v in ship.items() if k != "changed_detail"})
    for side in ("left", "right"):
        o = out[side]
        print(side, "joint", o["joint"], "attach", o["attachments_summary"], "continuity", o["continuity_summary"], "containment", o["containment"])


if __name__ == "__main__":
    main()
