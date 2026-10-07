"""Q201 audit of the ELBOW, FOREARM and WRIST of both arms of the Z-Anatomy model fitted to the VH male: numbers before -> after.

    python3 scripts/zanatomy/q201_audit.py --before-dump B.npz --after-dump A.npz [--before build/q197/viewer_zan_male_fitted] [--after build/viewer_zan_vhm_q201]
                                           [--out data/derived/Q201_arm_audit.json]

  joint        nearest-surface gap at the Z-source humerus - radius / ulna contact patch (median / p90), elbow angles (flexion, carrying, ulna-vs-epicondylar twist; q198_audit.elbow_angles)
  evidence     the three bones vs HIS evidence (scripts/cryo/q201_arm_evidence.py): label -> Z / Z -> label, Z outside the photographed elbow bone mass, mass boundary -> Z
  wrist        radius / ulna against the carpals: the Z-source contacts' gap change (mean abs)
  footprint    median distance of each muscle's origin / insertion footprint to its bone vs the Z source (full-resolution dumps)
  touching     structure pairs that touch in the Z source (< 3 mm) within 100 mm of the elbow / wrist: gap now (shipped meshes), vessel / nerve pairs apart
  containment  soft structures of the zone outside his skin, inside the bones; vessels outside his skin
  overlap      neighbour-muscle overlap of the zone muscles
  skin seams   shared-border steps between adjacent skin patches (whole skin, arm patches separately)
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
from scripts.zanatomy import body_ctx  # noqa: E402

body_ctx.configure("vhm")
from scripts.zanatomy import q199_audit as A  # noqa: E402
from scripts.zanatomy import q199_elbow as E  # noqa: E402
from scripts.zanatomy import q201_chain as C  # noqa: E402

SOFT = A.SOFT
WRIST_ZONE_MM = 90.0


def zone_ids(M, raw, side, jc, wc, cats=SOFT, r_elbow=140.0, r_wrist=WRIST_ZONE_MM):
    s = "_" + side
    out = []
    for i, d in M.items():
        if not (i.endswith(s) or s + "_" in i) or A.cat_of(d) not in cats or i not in raw:
            continue
        if np.any(np.linalg.norm(raw[i] - jc, axis=1) < r_elbow) or np.any(np.linalg.norm(raw[i] - wc, axis=1) < r_wrist):
            out.append(i)
    return out


def evidence_stats(side, M, ev, n=3000):
    """the three bones of M (any resolution) against his evidence"""
    s = "_" + side
    S = {b: E.at(M[b + s]["v"], E.bary_samples(M[b + s]["v"], M[b + s]["f"], n, seed=21)) for b in C.BONES}
    sh, sr = [], []
    for b in C.BONES:
        P = ev[f"shaft_{b}_{side}"]
        y0, y1 = P[:, 1].min(), P[:, 1].max()
        m = (S[b][:, 1] >= y0 - 5) & (S[b][:, 1] <= y1 + 5) & ((S[b][:, 1] > C.ZONE[1]) if b == "humerus" else (S[b][:, 1] < C.ZONE[0] + 8))
        sh.append(cKDTree(P).query(S[b][m])[0])
        sr.append(cKDTree(S[b]).query(P[::max(1, len(P) // 3000)])[0])
    Zall = np.vstack([S[b] for b in C.BONES])
    lo, edt, bound = C._union_field(ev[f"union_{side}"])
    inz = (Zall[:, 1] >= C.ZONE[0]) & (Zall[:, 1] <= C.ZONE[1])
    up = C._lookup(lo, edt, Zall[inz])
    ur = cKDTree(Zall).query(bound[::max(1, len(bound) // 3000)])[0]
    sh, sr = np.concatenate(sh), np.concatenate(sr)
    return {"label_to_Z_mm_median": round(float(np.median(sr)), 2), "Z_to_label_mm_median": round(float(np.median(sh)), 2), "label_to_Z_mm_p90": round(float(np.percentile(sr, 90)), 2),
            "elbow_Z_surface_outside_photographed_bone_mass_pct": round(100 * float((up > 1.0).mean()), 1), "bone_mass_boundary_to_Z_mm_median": round(float(np.median(ur)), 2),
            "bone_mass_boundary_to_Z_mm_p90": round(float(np.percentile(ur, 90)), 2)}


def wrist_stat(side, M, raw):
    s = "_" + side
    F = C.Fit.__new__(C.Fit)
    F._wrist(M, raw, side)
    out = []
    for b, (sm, d0) in F.wr.items():
        out.append(F.wr_tree.query(E.at(M[b + s]["v"], sm))[0] - d0)
    gaps = np.concatenate(out) if out else np.zeros(0)
    return {"pairs": int(len(gaps)), "gap_change_mm_mean_abs": round(float(np.abs(gaps).mean()), 2) if len(gaps) else None, "gap_change_mm_p90_abs": round(float(np.percentile(np.abs(gaps), 90)), 2) if len(gaps) else None}


def angles(M, side, centre):
    from scripts.zanatomy import q198_audit as Q
    B = {(n, side): [{"v": np.asarray(M[n + "_" + side]["v"], float)}] for n in C.BONES}
    return Q.elbow_angles({"centre": np.asarray(centre, float)}, B, side)


def vessels_outside(M, skin, ids):
    out = {}
    for i in ids:
        if A.cat_of(M[i]) != "vessel":
            continue
        v = np.asarray(M[i]["v"], float)
        out[i] = round(100 * float((~skin.contains(v)).mean()), 1)
    return {"vessels": len(out), "vessels_gt2pct_outside": int(sum(x > 2 for x in out.values())), "mean_outside_pct": round(float(np.mean(list(out.values()))), 2) if out else None,
            "vertices_outside_pct": None, "worst": sorted(out.items(), key=lambda t: -t[1])[:8]}


def skin_seams_all(by, raw):
    rows_all = {}
    for side in "lr":
        ids = [i for i, d in by.items() if A.cat_of(d) == "skin" and i.endswith("_" + side)]
        d_ = {i: {"v": by[i]["v"]} for i in ids}
        rows = E.skin_seam_rows(d_, raw, side, ids)
        arm = [r for r in rows if E.SKIN_ELBOW_RE.search(r["a"]) or E.SKIN_ELBOW_RE.search(r["b"]) or re.search(r"forearm|wrist|hand|palm|digit|elbow|arm_", r["a"] + r["b"])]
        summ = lambda rr: {"seams": len(rr), "steps_gt3mm": int(sum(r["step_mm_max"] > 3 for r in rr)), "max_step_mm": round(max([r["step_mm_max"] for r in rr] or [0]), 2),
                           "mean_step_p95_mm": round(float(np.mean([r["step_mm_p95"] for r in rr])), 2) if rr else None}
        rows_all[side] = {"all": summ(rows), "arm_forearm_hand": summ(arm)}
    return rows_all


def audit_side(side, Db, Da, Mb, Ma, raw, skin, ev, log=print):
    s = "_" + side
    out = {}
    smp, sel, jj, d0 = E.joint_pairs(raw, side, Db)
    jc = E.at(raw["humerus" + s], smp["humerus"])[sel].mean(0)
    wc = C.wrist_centre(Db, raw, side)
    out["joint"] = {"before": E.joint_stat(smp, sel, jj, d0, Db["humerus" + s]["v"], Db["radius" + s]["v"], Db["ulna" + s]["v"]),
                    "after": E.joint_stat(smp, sel, jj, d0, Da["humerus" + s]["v"], Da["radius" + s]["v"], Da["ulna" + s]["v"])}
    ctr = lambda M: E.at(M["humerus" + s]["v"], smp["humerus"])[sel].mean(0)
    out["angles"] = {"before": angles(Db, side, ctr(Db)), "after": angles(Da, side, ctr(Da))}
    for k in ("humerus_axis", "forearm_axis", "epicondylar_axis"):
        for t in ("before", "after"):
            out["angles"][t].pop(k, None)
    out["evidence"] = {"before": evidence_stats(side, Db, ev), "after": evidence_stats(side, Da, ev)}
    out["wrist"] = {"before": wrist_stat(side, Db, raw), "after": wrist_stat(side, Da, raw)}
    ids_f = zone_ids(Da, raw, side, jc, wc)
    out["n_zone_structures"] = len(ids_f)
    att = A.attachments(Db, Da, raw, side, ids_f)
    out["footprints"] = att
    devb = [max(abs(v["before_mm"] - v["source_mm"]) for k, v in r.items() if k != "_atlas_record") for r in att.values()]
    deva = [max(abs(v["after_mm"] - v["source_mm"]) for k, v in r.items() if k != "_atlas_record") for r in att.values()]
    out["footprints_summary"] = {"muscles": len(att), "mean_worst_bone_deviation_from_source_before_mm": round(float(np.mean(devb)), 2) if devb else None,
                                 "after_mm": round(float(np.mean(deva)), 2) if deva else None, "muscles_dev_gt5mm_before": int(sum(d > 5 for d in devb)), "after": int(sum(d > 5 for d in deva))}
    ids_s = zone_ids(Ma, raw, side, jc, wc)
    cen = np.vstack([jc, wc])
    rows = A.continuity(Mb, Ma, raw, side, ids_s, cen)
    out["touching_pairs"] = rows
    out["touching_summary"] = A.summary_gaps(rows)
    out["touching_vessel_nerve_summary"] = A.summary_gaps([r for r in rows if re.search(r"vessel|nerve", r["cats"])])
    out["named_centrelines"] = A.named_centrelines([r for r in rows if re.search(r"vessel|nerve", r["cats"]) and not r["cats"].startswith("muscle") and not r["cats"].endswith("muscle")])
    soft = [i for i in ids_s if A.cat_of(Ma[i]) in ("muscle", "vessel", "nerve", "tendon", "fascia")]
    bones = ["humerus" + s, "radius" + s, "ulna" + s]
    cb, perb = A.containment(Mb, skin, bones, soft)
    ca, pera = A.containment(Ma, skin, bones, soft)
    out["containment"] = {"before": cb, "after": ca}
    out["containment_worst_after"] = sorted(((k, v["outside_skin_pct"], v["inside_bone_pct"]) for k, v in pera.items()), key=lambda t: -(t[1] + t[2]))[:12]
    out["vessels_outside_skin"] = {"before": vessels_outside(Mb, skin, ids_s), "after": vessels_outside(Ma, skin, ids_s)}
    from scripts.zanatomy import q190_refine as Q190
    closed = {i for i in ids_s if Q190._closed(Ma[i]["f"])}
    try:
        out["muscle_overlap"] = A.muscle_overlap(Mb, Ma, ids_s, closed=closed)
    except Exception as e:                                   # a pyembree crash: once more with the pure-numpy ray tester
        log(f"  overlap audit failed ({e!r}); repeating in safe mode")
        out["muscle_overlap"] = A.muscle_overlap(Mb, Ma, ids_s, safe=True, closed=closed)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", default=str(REPO / "build" / "q197" / "viewer_zan_male_fitted"))
    ap.add_argument("--after", default=None, help="the shipped page dir after (decimated meshes: touching pairs, containment, overlap, ship diff); omitted = the full-resolution dumps are used for everything")
    ap.add_argument("--before-dump", required=True, help="full-resolution dump of the Q195 state (the hook's input)")
    ap.add_argument("--after-dump", required=True, help="full-resolution dump after the hook (--q201-dump-after)")
    ap.add_argument("--out", default=str(REPO / "data" / "derived" / "Q201_arm_audit.json"))
    ap.add_argument("--ship-diff", default=str(REPO / "data" / "derived" / "Q201_ship_diff.json"))
    ap.add_argument("--report", default=None)
    a = ap.parse_args(argv)
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.zanatomy import q190_metrics as Mx
    from scripts.zanatomy import trunk_refit_q186c_audit as A186
    Db_l, Da_l = Mx.load_dump(a.before_dump), Mx.load_dump(a.after_dump)
    raw = {d["id"]: d["r"] for d in Db_l}
    Db = {d["id"]: {"v": d["v"], "f": d["f"], "sys": d["cat"], "cat": d["cat"]} for d in Db_l}
    Da = {d["id"]: {"v": d["v"], "f": d["f"], "sys": d["cat"], "cat": d["cat"]} for d in Da_l}
    if a.after:
        Mb, Ma = A186.load_viewer(Path(a.before)), A186.load_viewer(Path(a.after))
    else:
        Mb, Ma = Db, Da
    skin = load_skin("vhm")
    ev = C.load_evidence()
    out = {side_name: audit_side(side, Db, Da, Mb, Ma, raw, skin, ev) for side, side_name in (("l", "left"), ("r", "right"))}
    out["skin_seams"] = {"before": skin_seams_all(Db, raw), "after": skin_seams_all(Da, raw)}
    Path(a.out).write_text(json.dumps(out, indent=1, default=float))
    changed, unchanged = A.diff(Mb, Ma) if a.after else ({}, 0)
    listed = set()
    if a.report:
        rep = json.loads(Path(a.report).read_text())
        listed = set(rep.get("q201", rep).get("moved_ids", []))
    ship = {"structures": len(Mb), "unchanged_within_0.05mm": unchanged, "changed": len(changed), "changed_but_not_listed_in_report": sorted(k for k in changed if k not in listed) if listed else None,
            "listed_in_report_but_unchanged": sorted(k for k in listed if k not in changed), "changed_detail": changed}
    Path(a.ship_diff).write_text(json.dumps(ship, indent=1))
    print({k: v for k, v in ship.items() if k != "changed_detail"})
    for side in ("left", "right"):
        o = out[side]
        print(side, "joint", o["joint"], "\n  angles", o["angles"], "\n  evidence", o["evidence"], "\n  wrist", o["wrist"], "\n  footprints", o["footprints_summary"],
              "\n  touching", o["touching_summary"], "\n  containment", o["containment"], "\n  vessels", {k: {x: y for x, y in v.items() if x != 'worst'} for k, v in o["vessels_outside_skin"].items()},
              "\n  overlap", {k: {x: y for x, y in v.items() if x != "per_muscle"} for k, v in o["muscle_overlap"].items()})
    print("skin seams", out["skin_seams"])


if __name__ == "__main__":
    main()
