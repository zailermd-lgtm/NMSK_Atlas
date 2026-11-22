"""Q195 audit of the Z-Anatomy male fitted to the VH male, against HIS CT: the quality gates of Q168 / Q190, whole body.

    python3 scripts/zanatomy/q195_audit.py --dump FILE.npz --out data/derived/Q195_audit_<tag>.json [--viewer DIR --stem atlas_viewer_zan_male_fitted]

--dump   the full-resolution pre-decimation state of the build (`--q194-dump FILE` writes it): per structure v (fitted), r (Z source), f.
--viewer the SHIPPED (decimated) geometry decoded from a built page: containment + overlap are re-measured on it too.

Gates (Q168 / Q190 definitions, whole body here): vertices outside HIS CT skin 0 %; muscle/nerve/vessel/fascia/organ vertices > 1 mm inside his bone
labels or lung label <= 5 %; neighbour-muscle overlap (vertex inside another closed muscle) <= 10 %; closed structures 0.65-1.5 x Z volume x body scale^3;
mean displacement bounded; folded faces (flipped against the Z source normal) per structure."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

BODY = "vhm"
SOFT = ("muscle", "nerve", "vessel", "fascia", "tendon", "ligament", "organ", "cartilage", "lymphatic", "bursa", "joint", "insertion")


def _closed(f):
    e = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    return bool((np.unique(e, axis=0, return_counts=True)[1] == 2).all())


def _vol(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum())) / 6.0


def load_structs(dump=None, viewer=None, stem=None):
    if dump:
        from scripts.zanatomy import q190_metrics as Mx
        return Mx.load_dump(dump)
    from scripts.zanatomy.trunk_refit_q186c_audit import load_viewer
    M = load_viewer(Path(viewer), stem)
    return [{"id": k, "cat": m["sys"], "v": m["v"], "r": m["v"], "f": m["f"]} for k, m in M.items()]


def depth_in(label_depth, B, P):
    import scripts.placement_sweep_q185 as P185
    return np.nan_to_num(P185.sample_depth(label_depth, B.A, B.O, P, B.shape))


LEG_Y = 25.0    # his TotalSegmentator `total` volume is the torso CT block (y >= ~32): below it the bone check uses his own bone MESHES


def his_leg_bones():
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    from scripts.zanatomy.q191_hand import Inside, merge_inside
    her = load_her_meshes()
    ids = [k for k, m in her.items() if m["cat"] == "bone" and m["v"][:, 1].mean() < LEG_Y - 60 and len(m["f"]) > 100]
    return merge_inside([Inside(her[k]["v"], her[k]["f"]) for k in ids]), ids


def containment(structs, body=BODY, stride_target=500):
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.placement_sweep_q185 import Body
    skin = load_skin(body)
    B = Body(body)
    legs, _ = his_leg_bones()

    def bone_depth(P):
        d = depth_in(B.bone, B, P)
        low = P[:, 1] < LEG_Y
        if low.any():
            d = np.where(low, np.maximum(legs.depth(P), 0.0), d)
        return d
    rows = {}
    for d in structs:
        v = d["v"]
        if len(v) == 0:
            continue
        P = v[:: max(1, len(v) // stride_target)]
        row = {"cat": d["cat"], "n": int(len(P))}
        if d["cat"] != "skin":
            row["outside_skin"] = float((~skin.contains(P)).mean())
        if d["cat"] in SOFT:
            row["in_bone_gt1mm"] = float((bone_depth(P) > 1.0).mean())
            if not d["id"].startswith(("lung", "zan_lung", "trachea", "zan_trachea", "zan_bronch", "zan_pleura")) and "lung" not in d["id"] and "pleura" not in d["id"] and "bronch" not in d["id"]:
                row["in_lung_gt1mm"] = float((depth_in(B.lung, B, P) > 1.0).mean())
        rows[d["id"]] = row
    return rows


def overlap_all(structs, nsamp=1200, seed=0):
    """fraction of each closed muscle's vertices lying inside another closed muscle (ray-parity), whole body"""
    import trimesh
    from scripts.zanatomy import q190_refine as Q
    rng = np.random.default_rng(seed)
    cand = [d for d in structs if d["cat"] == "muscle" and len(d["f"]) and _closed(d["f"]) and not Q.NOT_A_MUSCLE_BODY.search(d["id"])]
    meshes = {d["id"]: (trimesh.Trimesh(d["v"], d["f"], process=False), d["v"].min(0), d["v"].max(0)) for d in cand}
    out = {}
    for d in cand:
        v = d["v"]
        p = v[rng.choice(len(v), min(len(v), nsamp), replace=False)]
        inside = np.zeros(len(p), bool)
        for k, (m, lo, hi) in meshes.items():
            if k == d["id"]:
                continue
            sel = np.flatnonzero(np.all((p >= lo - 1) & (p <= hi + 1), 1) & ~inside)
            if len(sel):
                try:
                    inside[sel[m.contains(p[sel])]] = True
                except Exception:
                    continue
        out[d["id"]] = float(inside.mean())
    return out


def shape_rows(structs, body_scale):
    from scripts.zanatomy import q190_metrics as Mx
    rows = {}
    for d in structs:
        r, v, f = d["r"], d["v"], d["f"]
        e = {"cat": d["cat"], "mean_disp_vs_source_mm": None}
        st = Mx.stretch_stats(v, r, f)
        if st is not None:
            e["distortion_score"] = round(Mx.distortion_score(st), 2)
            e["flipped"] = round(st["flipped"], 4)
            e["area_outside_0.67_1.5"] = round(st["area_frac_gt1.5"] + st["area_frac_lt0.67"], 4)
        if d["cat"] not in ("skin", "fascia") and len(f) and _closed(f) and _vol(r, f) > 1000.0:
            e["volume_ratio_vs_source_x_scale3"] = round(_vol(v, f) / (_vol(r, f) * body_scale ** 3), 3)
        rows[d["id"]] = e
    return rows


def summarize(rows_c, rows_s, ov):
    def frac(sel, key):
        a = [r[key] for r in sel if key in r]
        return round(float(np.mean(a)), 4) if a else None
    out = {"outside_his_skin_mean_by_cat": {}, "inside_bone_mean_by_cat": {}, "inside_lung_mean_by_cat": {}}
    for cat in sorted({r["cat"] for r in rows_c.values()}):
        sel = [r for r in rows_c.values() if r["cat"] == cat]
        out["outside_his_skin_mean_by_cat"][cat] = frac(sel, "outside_skin")
        out["inside_bone_mean_by_cat"][cat] = frac(sel, "in_bone_gt1mm")
        out["inside_lung_mean_by_cat"][cat] = frac(sel, "in_lung_gt1mm")
    nonskin = [r for r in rows_c.values() if r["cat"] != "skin"]
    out["outside_his_skin_all_nonskin"] = frac(nonskin, "outside_skin")
    out["structures_with_any_vertex_outside_skin"] = int(sum(1 for r in nonskin if r.get("outside_skin", 0) > 0))
    soft = [r for r in rows_c.values() if r["cat"] in SOFT]
    out["soft_inside_bone"] = frac(soft, "in_bone_gt1mm")
    out["soft_inside_lung"] = frac(soft, "in_lung_gt1mm")
    vr = np.array([r["volume_ratio_vs_source_x_scale3"] for r in rows_s.values() if "volume_ratio_vs_source_x_scale3" in r])
    if len(vr):
        out["volume_guard"] = {"closed_structures": int(len(vr)), "within_0.65_1.5": round(float(((vr >= 0.65) & (vr <= 1.5)).mean()), 4),
                               "median": round(float(np.median(vr)), 3), "p05": round(float(np.percentile(vr, 5)), 3), "p95": round(float(np.percentile(vr, 95)), 3)}
    sc = np.array([r["distortion_score"] for r in rows_s.values() if "distortion_score" in r])
    fl = np.array([r["flipped"] for r in rows_s.values() if "flipped" in r])
    out["distortion"] = {"mean_score_pct_faces": round(float(sc.mean()), 2), "structures_gt25pct": int((sc > 25).sum()),
                         "mean_flipped_frac": round(float(fl.mean()), 4), "structures_flipped_gt2pct": int((fl > 0.02).sum())}
    if ov:
        a = np.array(list(ov.values()))
        out["muscle_overlap"] = {"muscles": int(len(a)), "mean_vertex_fraction_inside_another": round(float(a.mean()), 4), "gt10pct": int((a > 0.10).sum())}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=None)
    ap.add_argument("--viewer", default=None)
    ap.add_argument("--stem", default="atlas_viewer_zan_male_fitted")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-overlap", action="store_true")
    a = ap.parse_args(argv)
    from scripts.zanatomy import body_ctx
    body_ctx.configure("vhm")
    structs = load_structs(a.dump, a.viewer, a.stem)
    print(len(structs), "structures")
    rows_c = containment(structs)
    rows_s = shape_rows(structs, body_ctx.BODY_SCALE) if a.dump else {}
    ov = {} if a.no_overlap else overlap_all(structs)
    summ = summarize(rows_c, rows_s, ov)
    out = {"source": a.dump or a.viewer, "body_scale": body_ctx.BODY_SCALE, "summary": summ, "per_structure": {
        k: {**rows_c.get(k, {}), **rows_s.get(k, {}), **({"overlap": round(ov[k], 4)} if k in ov else {})} for k in sorted(set(rows_c) | set(rows_s))}}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
