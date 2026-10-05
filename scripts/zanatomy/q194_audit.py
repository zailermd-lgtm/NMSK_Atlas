"""Q194 audit: shipped-geometry no-regression diff vs v9 + the numbers of every Q194 fix.

    python3 scripts/zanatomy/q194_audit.py [--before build/viewer_zan_female] [--after build/viewer_zan_female_q194] [--report data/derived/Q194_zan_female_q194_build.json]
                                           [--dump-before final_v9.npz --dump-after after_q194.npz] [--out-prefix data/derived/Q194]

Writes Q194_ship_diff.json (every structure vertex by vertex: unchanged = same vertex count and max displacement <= 0.05 mm; every changed structure must be listed in the
build report's Q194 sections), Q194_forearm_photo_audit.json (her left-forearm photographs: muscle volume inside her muscle compartment / compartment covered / outside her skin,
detachment from her radius / ulna, v9 vs now, on the SHIPPED meshes), Q194_overlap.json (neighbour-muscle overlap, Au.overlap as the Q190 audit, + hand / forearm sets) and, with the two
full-resolution dumps, Q194_distortion.json (q190_metrics stretch score per moved structure, before / after)."""
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
from scripts.zanatomy import q190_audit as Au  # noqa: E402
from scripts.zanatomy import q190_metrics as Mx  # noqa: E402
from scripts.zanatomy import q190_ship_audit as SA  # noqa: E402
from scripts.zanatomy import q190_refine as Q  # noqa: E402
from scripts.zanatomy import q191_hand as H  # noqa: E402
from scripts.zanatomy import q194_forearm as F  # noqa: E402
from scripts.zanatomy import q194_separate as Sp  # noqa: E402
from scripts.zanatomy import trunk_refit_q186c_audit as A186  # noqa: E402


def moved_ids_from_report(rep: dict) -> set:
    q = rep.get("q194", rep)
    out = set(q.get("left_forearm", {}).get("ids_changed", []))
    out |= set(q.get("relaxed", {}))
    out |= set(q.get("right_hand", {}).get("bones_nudged", {})) | set(q.get("right_hand", {}).get("relaxed", {}))
    for s in q.get("separated", {}).values():
        out |= {k for k, m in s.get("moved", {}).items() if m["max_move_mm"] >= 0.3}
    out |= set(q.get("skin", {}).get("smoothed", {}))
    return out


def diff(Mb, Ma):
    changed, unchanged = {}, 0
    for k, mb in Mb.items():
        ma = Ma[k]
        if len(mb["v"]) != len(ma["v"]) or len(mb["f"]) != len(ma["f"]):
            d = float("inf")
        else:
            d = float(np.abs(mb["v"] - ma["v"]).max())
        if d > 0.05 and np.isfinite(d):
            d = float(max(cKDTree(mb["v"]).query(ma["v"])[0].max(), cKDTree(ma["v"]).query(mb["v"])[0].max()))
        if d <= 0.05:
            unchanged += 1
        else:
            A_, B_ = H.surf_pts(mb["v"], mb["f"], 3000), H.surf_pts(ma["v"], ma["f"], 3000)
            sd = max(float(np.percentile(cKDTree(B_).query(A_)[0], 99)), float(np.percentile(cKDTree(A_).query(B_)[0], 99)))
            changed[k] = {"max_vertex_mm": round(d, 2) if np.isfinite(d) else "topology changed", "surface_p99_mm": round(sd, 2)}
    return changed, unchanged


def forearm_photo_audit(M, ids):
    """her left-forearm photographs: shipped meshes of the left forearm muscles vs her muscle compartment / skin silhouette / bones"""
    P = F.load_photo_masks()
    skin = P["skin"] > 0.5
    ys = F.GRID_LO[1] + np.arange(F.GRID_N[1])
    for iy in range(F.GRID_N[1]):
        if P["valid_y"][iy]:
            skin[:, iy, :] = __import__("scipy.ndimage", fromlist=["x"]).binary_fill_holes(skin[:, iy, :])
    bones = F.occupancy(M["radius_l"]["v"], M["radius_l"]["f"]) | F.occupancy(M["ulna_l"]["v"], M["ulna_l"]["f"])
    R = F.muscle_region(P, bones, 212.0, 338.0)
    band = (ys >= 215) & (ys <= 335)
    U = np.zeros(R.shape, bool)
    out = {"per_muscle": {}}
    tot_out, tot_v = 0, 0
    rad_tree = cKDTree(np.vstack([M["radius_l"]["v"], M["ulna_l"]["v"]]))
    for i in ids:
        m = M[i]
        occ = F.occupancy(m["v"], m["f"])
        U |= occ
        v = m["v"]
        sel = (v[:, 1] > 215) & (v[:, 1] < 335)
        g = np.floor(v[sel] - F.GRID_LO + 0.5).astype(int)
        ok = np.all((g >= 0) & (g < F.GRID_N), 1)
        g = g[ok]
        o = float((~skin[g[:, 0], g[:, 1], g[:, 2]]).mean()) if len(g) else None
        n_in = float(R[g[:, 0], g[:, 1], g[:, 2]].mean()) if len(g) else None
        out["per_muscle"][i] = {"outside_her_skin_vertex_pct": None if o is None else round(100 * o, 1), "vertices_in_her_muscle_compartment_pct": None if n_in is None else round(100 * n_in, 1),
                                "median_dist_to_radius_ulna_mm": round(float(np.median(rad_tree.query(v[::4])[0])), 1)}
        if len(g):
            tot_out += int((~skin[g[:, 0], g[:, 1], g[:, 2]]).sum()); tot_v += len(g)
    Ub, Rb = U[:, band, :], R[:, band, :]
    out["summary"] = {"muscle_volume_in_band_cm3": round(float(Ub.sum()) / 1000, 1), "volume_inside_her_compartment_pct": round(100 * float((Ub & Rb).sum() / max(1, Ub.sum())), 1),
                      "her_compartment_covered_pct": round(100 * float(((Ub | bones[:, band, :]) & Rb).sum() / max(1, Rb.sum())), 1),
                      "vertices_outside_her_skin_pct": round(100 * tot_out / max(1, tot_v), 1), "compartment_volume_cm3": round(float(Rb.sum()) / 1000, 1)}
    return out


def overlap_sets(M, regions):
    S_ = SA.as_structs(M)
    pend = [{"mesh_id": k, "cat": d["cat"]} for k, d in {s["id"]: s for s in S_}.items()]
    res = {}
    o = Au.overlap(S_)
    res["trunk_audit_overlap_mean_vertex_fraction"] = round(float(np.mean(list(o.values()))), 4)
    for side, name in (("r", "right_forearm_hand"), ("l", "left_forearm_hand")):
        ids = [i for i in H.scope(pend, regions, side) if M[i]["sys"] == "muscle" and Q._closed(M[i]["f"]) and not Q.NOT_A_MUSCLE_BODY.search(i) and not H.FOOT_NAME.search(i)]
        ov = Sp.overlap_pct({i: (M[i]["v"], M[i]["f"]) for i in ids})
        res[name] = {"muscles": len(ids), "mean_overlap_pct": round(float(np.mean(list(ov.values()))), 2),
                     "hypothenar_interossei_pct": {i: round(ov[i], 1) for i in ov if re.search(r"digiti_minimi|interossei|opponens", i)}}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_q194"))
    ap.add_argument("--report", default=str(REPO / "data" / "derived" / "Q194_zan_female_q194_build.json"))
    ap.add_argument("--dump-before", default=None)
    ap.add_argument("--dump-after", default=None)
    ap.add_argument("--out-prefix", default=str(REPO / "data" / "derived" / "Q194"))
    a = ap.parse_args(argv)
    from scripts.transfer.zan_to_vhf_whole_body import DEFAULT_REPORT
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    Mb, Ma = A186.load_viewer(Path(a.before)), A186.load_viewer(Path(a.after))
    assert set(Mb) == set(Ma), "structure sets differ"
    rep = json.loads(Path(a.report).read_text())
    listed = moved_ids_from_report(rep)
    changed, unchanged = diff(Mb, Ma)
    unlisted = sorted(k for k in changed if k not in listed)
    by_region = {}
    for k in Mb:
        r = regions.get(k, "other")
        by_region.setdefault(r, [0, 0])
        by_region[r][0] += 1
        by_region[r][1] += int(k not in changed)
    out = {"structures": len(Mb), "unchanged_within_0.05mm": unchanged, "changed": len(changed), "changed_but_not_listed_in_report": unlisted,
           "listed_in_report_but_unchanged": sorted(k for k in listed if k not in changed), "changed_detail": changed,
           "unchanged_by_q168_region": {k: {"total": v[0], "unchanged": v[1]} for k, v in by_region.items()}}
    Path(a.out_prefix + "_ship_diff.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k not in ("changed_detail", "unchanged_by_q168_region")})
    fa = [i for i in Mb if i.endswith("_l") and Mb[i]["sys"] == "muscle" and regions.get(i) == "forearm_hand" and not H.FOOT_NAME.search(i) and i in
          set(rep.get("q194", rep).get("left_forearm", {}).get("structures", {})) and Q._closed(Mb[i]["f"])]
    pa = {"before": forearm_photo_audit(Mb, fa), "after": forearm_photo_audit(Ma, fa), "muscles": fa}
    Path(a.out_prefix + "_forearm_photo_audit.json").write_text(json.dumps(pa, indent=1))
    print("forearm photo audit:", pa["before"]["summary"], "->", pa["after"]["summary"])
    ov = {"before": overlap_sets(Mb, regions), "after": overlap_sets(Ma, regions)}
    Path(a.out_prefix + "_overlap.json").write_text(json.dumps(ov, indent=1))
    print("overlap:", json.dumps(ov)[:900])
    if a.dump_before and a.dump_after:
        B_, A_ = {d["id"]: d for d in Mx.load_dump(a.dump_before)}, {d["id"]: d for d in Mx.load_dump(a.dump_after)}
        rows = {}
        for k in sorted(listed):
            if k not in B_:
                continue
            b, af = B_[k], A_[k]
            sb, sa = Mx.stretch_stats(b["v"], b["r"], b["f"]), Mx.stretch_stats(af["v"], af["r"], af["f"])
            sc = lambda s: None if s is None else round(100 * (s["area_frac_gt1.5"] + s["area_frac_lt0.67"]), 1)
            rows[k] = {"cat": b["cat"], "stretch_area_pct_before": sc(sb), "stretch_area_pct_after": sc(sa), "folded_edges_pct_before": round(100 * H.fold_stats(b["v"], b["r"], b["f"]), 2),
                       "folded_edges_pct_after": round(100 * H.fold_stats(af["v"], af["r"], af["f"]), 2), "volume_ratio_before": H.vol_ratio(b["v"], b["r"], b["f"]),
                       "volume_ratio_after": H.vol_ratio(af["v"], af["r"], af["f"])}
        Path(a.out_prefix + "_distortion.json").write_text(json.dumps(rows, indent=1, default=float))
        print("distortion rows:", len(rows))


if __name__ == "__main__":
    main()
