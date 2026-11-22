"""Q202 skin / surface metrics of a built Z-Anatomy page (the Q198 skin metrics, re-run on any page dir):
  * seams      shared-border steps between adjacent skin patches (q199_elbow.skin_seam_rows; adjacency = border vertices < 1.5 mm apart in the Z source = the unfitted base page)
  * sections   Q198 skin cross-sections perpendicular to every junction axis (q198_audit.skin_profile): sections whose outline is not closed, radius / centroid steps per 3 mm
  * escape     fraction of rays from interior points of the trunk / pelvis / thigh that leave the body without hitting a skin sheet (an open envelope = > 0)
  * open       open boundary edges of the skin patches (source: auricle sheets + toe dorsal sheet are open by design)
    python3 scripts/zanatomy/q202_metrics.py PAGEKEY|--dir DIR --stem STEM [--raw BASEKEY] -o OUT.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.zanatomy import q202_pages as P  # noqa: E402
from scripts.zanatomy import q198_core as C  # noqa: E402
C_ = C
from scripts.zanatomy import q198_joints as J  # noqa: E402

SIDE = {"l": "l", "r": "r", "m": "m", "left": "l", "right": "r"}


def struct_list(d, stem, sysset=None):
    man, blob = P.load_page(d, stem)
    S = P.decode(man, blob, only=(lambda m: m["sys"] in sysset) if sysset else None)
    out = []
    for i, e in S.items():
        out.append(dict(id=i, name=e["m"]["name"], sys=e["m"]["sys"], side=SIDE.get(e["m"]["side"], "m"), v=e["v"], f=e["f"], src="zan", rec=e["m"].get("rec") or {}))
    cnt = {}
    for s_ in out:
        if s_["sys"] == "bone":
            cnt[s_["id"]] = cnt.get(s_["id"], 0) + 1
    seen = {}
    for s_ in out:
        if s_["sys"] == "bone" and cnt[s_["id"]] > 1:
            seen[s_["id"]] = seen.get(s_["id"], 0) + 1
            s_["id"] = f"{s_['id']}#{seen[s_['id']]}"
    return out


def seams(skin, raw_by):
    from scripts.zanatomy import q199_elbow as E
    by = {s["id"]: {"v": s["v"], "f": s["f"], "cat": "skin"} for s in skin}
    raw = {i: raw_by[i] for i in by if i in raw_by}
    ids = [i for i in by if i in raw]                     # ALL patches, cross-side pairs (midline) included
    rows = E.skin_seam_rows(by, raw, None, ids)
    st = [r["step_mm_max"] for r in rows]
    # true surface gap: the border vertices of A against the SURFACE of B (a vertex-to-vertex step over-reads where the two borders are sampled differently)
    import trimesh
    from scipy.spatial import cKDTree
    tm = {}
    gaps = []
    for r in rows:
        a, b = r["a"], r["b"]
        d, k = cKDTree(raw[b]).query(raw[a])
        sel = np.where(d < 1.5)[0]
        for x, y in ((a, b), (b, a)):
            if y not in tm:
                tm[y] = trimesh.proximity.ProximityQuery(trimesh.Trimesh(by[y]["v"], by[y]["f"], process=False))
        da = tm[b].on_surface(by[a]["v"][sel])[1]
        gaps.append(float(da.max()))
    gp = np.array(gaps) if gaps else np.zeros(1)
    return {"surface_gap_gt1mm": int((gp > 1).sum()), "surface_gap_gt2mm": int((gp > 2).sum()), "surface_gap_gt3mm": int((gp > 3).sum()), "surface_gap_max_mm": round(float(gp.max()), 2),
            "surface_gap_worst": sorted([(rows[i]["a"], rows[i]["b"], round(gaps[i], 2)) for i in range(len(rows))], key=lambda t: -t[2])[:6], "seams": len(rows), "steps_gt_1mm": int(sum(x > 1 for x in st)), "steps_gt_3mm": int(sum(x > 3 for x in st)), "max_step_mm": round(max(st or [0]), 2),
            "mean_step_mm": round(float(np.mean(st)) if st else 0, 3), "worst": sorted([(r["a"], r["b"], r["step_mm_max"]) for r in rows], key=lambda t: -t[2])[:6]}


def sections(S, skin):
    from scripts.zanatomy.q198_audit import skin_profile
    Jn, B, lev = J.find_joints(S)
    out = {}
    for j in Jn:
        if j["name"] not in ("elbow", "wrist", "knee", "ankle"):    # as Q198 audit_junction: the limb junctions whose axis runs along a tube
            continue
        r = skin_profile(skin, j, half=min(90, j["R"]))
        out[f"{j['name']}_{j['side']}"] = {k: r.get(k) for k in ("slices", "valid", "open_or_missing_sections", "merged_with_trunk_sections", "max_radius_step_mm_per_3mm", "max_centroid_step_mm_per_3mm", "steps_gt3mm", "at_t_mm")}
    return out


def open_edges(skin):
    tot, per = 0, {}
    for s in skin:
        v, f = C.weld(s["v"], s["f"], 0.02)
        lp, nb, nm = C.boundary_loops(v, f)
        if nb:
            per[s["id"]] = nb
        tot += nb
    return {"open_boundary_edges_total": tot, "patches_with_open_edges": len(per)}


def escape(skin, n_dirs=4000, seed=0):
    """rays from interior points (pelvis, lower trunk, upper trunk, both thighs: points inside the skin envelope found on the sections) in uniformly random directions;
    a ray 'escapes' when it never meets a skin sheet within 3 m.  Counted per point; the closed body has 0 escapes."""
    import trimesh
    V = np.concatenate([s["v"] for s in skin]); o = 0; F = []
    for s in skin:
        F.append(s["f"] + o); o += len(s["v"])
    F = np.concatenate(F)
    mesh = trimesh.Trimesh(V, F, process=False)
    rng = np.random.default_rng(seed)
    pts = {"pelvis_floor": (0, -60, 20), "pelvis_centre": (0, -10, 20), "perineal_gap": (0, -80, 25), "lower_abdomen": (0, 60, 30), "chest": (0, 330, 20), "r_thigh": (45, -150, 10), "l_thigh": (-45, -150, 10)}
    out = {}
    for k, p in pts.items():
        d = rng.normal(size=(n_dirs, 3)); d /= np.linalg.norm(d, axis=1)[:, None]
        o_ = np.tile(np.asarray(p, float), (n_dirs, 1))
        hit = mesh.ray.intersects_any(o_, d)
        out[k] = {"point": p, "escape_fraction": round(float(1 - hit.mean()), 5), "escape_dirs": int((~hit).sum())}
    return out


def raw_by_ids(skin, raw):
    return [s_["id"] for s_ in skin if s_["id"] in raw]


def run(dir_, stem, raw_key=None):
    S = struct_list(dir_, stem, {"skin", "bone"})
    skin = [s for s in S if s["sys"] == "skin"]
    if raw_key:
        rd, rs = P.PAGES[raw_key]
        raw = {s["id"]: s["v"] for s in struct_list(REPO / rd, rs, {"skin"})}
    else:
        raw = {s["id"]: s["v"] for s in skin}
    from scripts.zanatomy import q202_contact as K
    ids = sorted(i for i in raw_by_ids(skin, raw))
    by = {s_["id"]: {"v": s_["v"], "f": s_["f"]} for s_ in skin}
    cons = K.contacts({i: {"v": raw[i], "f": by[i]["f"]} for i in ids}, ids)
    g = K.gaps(by, ids, cons)
    contact = {"contacts": len(cons), "gap_p99_mm": round(float(np.percentile(g, 99)), 2), "gap_gt_2mm": int((g > 2).sum()), "gap_gt_3mm": int((g > 3).sum()), "gap_gt_5mm": int((g > 5).sum()), "gap_max_mm": round(float(g.max()), 2)}
    env = {}
    for cl in (2, 3):
        env[f"envelope_L_close{cl}"] = round(C_.SkinField(skin, 3.0, close=cl).vol_L, 1)
    res = {"n_skin_patches": len(skin), "contact": contact, "envelope": env, "seams": seams(skin, raw), "open": open_edges(skin), "sections": sections(S, skin), "escape": escape(skin)}
    sec = res["sections"].values()
    res["sections_summary"] = {"junctions": len(res["sections"]), "open_or_missing_total": int(sum((x["open_or_missing_sections"] or 0) for x in sec)),
                               "max_radius_step_mm_per_3mm": max([x["max_radius_step_mm_per_3mm"] or 0 for x in sec] or [0]), "junctions_with_step_gt3": int(sum(1 for x in sec if (x["max_radius_step_mm_per_3mm"] or 0) > 3))}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page", nargs="?")
    ap.add_argument("--dir"); ap.add_argument("--stem"); ap.add_argument("--raw", help="PAGES key of the unfitted base page whose skin is the Z source")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    if a.page:
        d, s = P.PAGES[a.page]
        d = REPO / d
    else:
        d, s = Path(a.dir), a.stem
    res = run(d, s, a.raw)
    Path(a.out).write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: v for k, v in res.items() if k not in ("sections",)}, default=float)[:1800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
