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


def elbow_ids(M, raw, side, cats=SOFT):
    s = "_" + side
    out = []
    for i, d in M.items():
        if not (i.endswith(s) or s + "_" in i) or cat_of(d) not in cats:
            continue
        v = d["v"]
        lo, hi = ELBOW_BOX[side]
        # structures that have vertices in the elbow box (raw frame is not used: the audit is about where they are)
        if np.any(np.all((v >= lo) & (v <= hi), axis=1)):
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
            out[i] = row
    return out


def continuity(Mb, Ma, raw, side, ids, touch_mm=3.0):
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
            d0 = float(rt[j].query(ra)[0].min()) * __import__("scripts.zanatomy.q190_metrics", fromlist=["x"]).BODY_SCALE
            if d0 > touch_mm:
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
    """adjacent skin patches around the elbow (they share a border in the Z source: raw vertices < 1.5 mm apart): distance of the shared-border vertices now"""
    s = "_" + side
    ids = [i for i, d in M.items() if cat_of(d) == "skin" and (i.endswith(s)) and np.any(np.all((d["v"] >= ELBOW_BOX[side][0] - 20) & (d["v"] <= ELBOW_BOX[side][1] + 20), axis=1))]
    rows = []
    for a_ in range(len(ids)):
        for b_ in range(a_ + 1, len(ids)):
            i, j = ids[a_], ids[b_]
            if len(raw[i]) != len(M[i]["v"]) or len(raw[j]) != len(M[j]["v"]):
                continue
            d, k = cKDTree(raw[j]).query(raw[i])
            sel = d < 1.5
            if sel.sum() < 3:
                continue
            step = np.linalg.norm(M[i]["v"][sel] - M[j]["v"][k[sel]], axis=1)
            rows.append({"a": i, "b": j, "border_vertices": int(sel.sum()), "step_mm_p95": round(float(np.percentile(step, 95)), 2), "step_mm_max": round(float(step.max()), 2)})
    return rows


def summary_gaps(rows):
    b = np.array([r["before_mm"] for r in rows]) if rows else np.zeros(0)
    a = np.array([r["after_mm"] for r in rows]) if rows else np.zeros(0)
    return {"pairs": len(rows), "gap_gt5mm_before": int((b > 5).sum()), "gap_gt5mm_after": int((a > 5).sum()), "mean_gap_before": round(float(b.mean()), 2) if len(b) else None,
            "mean_gap_after": round(float(a.mean()), 2) if len(a) else None, "max_gap_before": round(float(b.max()), 2) if len(b) else None, "max_gap_after": round(float(a.max()), 2) if len(a) else None}


def audit_pair(Mb, Ma, raw, skin, side, log=print):
    s = "_" + side
    out = {}
    smp, sel, jj, d0 = E.joint_pairs(raw, side, Mb)
    out["joint"] = {"before": E.joint_stat(smp, sel, jj, d0, Mb["humerus" + s]["v"], Mb["radius" + s]["v"], Mb["ulna" + s]["v"]),
                    "after": E.joint_stat(smp, sel, jj, d0, Ma["humerus" + s]["v"], Ma["radius" + s]["v"], Ma["ulna" + s]["v"])}
    ids = elbow_ids(Ma, raw, side)
    out["n_elbow_structures"] = len(ids)
    att = attachments(Mb, Ma, raw, side, ids)
    out["attachments"] = att
    dev_b = [max(abs(v["before_mm"] - v["source_mm"]) for v in r.values()) for r in att.values()]
    dev_a = [max(abs(v["after_mm"] - v["source_mm"]) for v in r.values()) for r in att.values()]
    out["attachments_summary"] = {"muscles": len(att), "mean_worst_bone_deviation_from_source_before_mm": round(float(np.mean(dev_b)), 2) if dev_b else None,
                                  "after_mm": round(float(np.mean(dev_a)), 2) if dev_a else None, "muscles_dev_gt5mm_before": int(sum(d > 5 for d in dev_b)), "after": int(sum(d > 5 for d in dev_a))}
    rows = continuity(Mb, Ma, raw, side, ids)
    out["continuity_pairs"] = rows
    out["continuity_summary"] = summary_gaps(rows)
    out["centreline_pairs_summary"] = summary_gaps([r for r in rows if re.search(r"vessel|nerve", r["cats"])])
    soft_ids = [i for i in ids if cat_of(Ma[i]) in ("muscle", "vessel", "nerve", "tendon", "fascia")]
    bones = ["humerus" + s, "radius" + s, "ulna" + s]
    cb, perb = containment(Mb, skin, bones, soft_ids)
    ca, pera = containment(Ma, skin, bones, soft_ids)
    out["containment"] = {"before": cb, "after": ca}
    out["containment_worst_after"] = sorted(((k, v["outside_skin_pct"], v["inside_bone_pct"]) for k, v in pera.items()), key=lambda t: -(t[1] + t[2]))[:12]
    sb, sa = skin_seams(Mb, raw, side), skin_seams(Ma, raw, side)
    out["skin_seams"] = {"before": sb, "after": sa}
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
    ap.add_argument("--raw-dump", default=None, help="a full-resolution dump (npz, q190_refine.dump_pending) whose r<i> arrays are the Z source vertices")
    a = ap.parse_args(argv)
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.zanatomy import trunk_refit_q186c_audit as A186
    from scripts.zanatomy import q190_metrics as Mx
    Mb, Ma = A186.load_viewer(Path(a.before)), A186.load_viewer(Path(a.after))
    raw = {d["id"]: d["r"] for d in Mx.load_dump(a.raw_dump)}
    skin = load_skin("vhf")
    rep = json.loads(Path(a.report).read_text())
    out = {"left": audit_pair(Mb, Ma, raw, skin, "l"), "right": audit_pair(Mb, Ma, raw, skin, "r")}
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
