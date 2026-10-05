"""Q190 audit on the SHIPPED geometry (decimated, as the viewer draws it): v6 (build/viewer_zan_female) vs q190.

    python3 scripts/zanatomy/q190_ship_audit.py [--before DIR] [--after DIR] [--out data/derived/Q190_trunk_audit.json]

Her-label chamfer of every refined muscle, containment (outside her CT skin / inside her bone labels) per layer, L/R symmetry, neighbour
overlap, the front crease metric (dihedral angle between faces of the chest/abdomen skin: must not regress), back skin gap.
Stretch against the Z source needs the full-resolution pre-decimation meshes: see the build report (Q190_zan_female_q190_build.json)."""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q190_audit as Au  # noqa: E402
from scripts.zanatomy import q190_refine as Q  # noqa: E402
from scripts.zanatomy import trunk_refit_q186c as T  # noqa: E402
from scripts.zanatomy import trunk_refit_q186c_audit as A186  # noqa: E402


def as_structs(M):
    return [{"id": k, "cat": {"muscle": "muscle", "skin": "skin", "nerve": "nerve", "vessel": "vessel", "fascia": "fascia", "bone": "bone"}.get(m["sys"], m["sys"]),
             "v": m["v"], "f": m["f"], "r": m["v"]} for k, m in M.items()]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_q190"))
    ap.add_argument("--out", default=str(REPO / "data" / "derived" / "Q190_trunk_audit.json"))
    ap.add_argument("--her-cache", default=None)
    args = ap.parse_args(argv)
    from scripts.placement_sweep_q185 import Body
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    Mb, Ma = A186.load_viewer(Path(args.before)), A186.load_viewer(Path(args.after))
    sb, sa = as_structs(Mb), as_structs(Ma)
    her = pickle.load(open(args.her_cache, "rb"))["her"] if args.her_cache else load_her_meshes()
    skin = load_skin("vhf")
    axis = T.trunk_axis(np.asarray(skin.vertices, np.float64))
    body = Body("vhf")
    G = Q.Guards(body)
    out = {"before": args.before, "after": args.after}
    # 1. her-label chamfer
    groups = Q.plan_groups(sb, her)
    rows = {}
    for hid, mem in sorted(groups.items()):
        ref = Q.Ref(her[hid]["v"].astype(float), her[hid]["f"].astype(int))
        ids = [m["id"] for m in mem]
        va = {m["id"]: Ma[m["id"]] for m in mem if m["id"] in Ma}
        if len(va) != len(mem):
            continue
        cover = (ref.tree.query(np.vstack([m["v"] for m in mem])[::7])[0] <= Q.PARTIAL_NEAR_MM).mean()
        partial = bool(cover < Q.PARTIAL_COVER)

        def cf(M):
            V, F, o = [], [], 0
            for k in ids:
                V.append(M[k]["v"]); F.append(M[k]["f"] + o); o += len(M[k]["v"])
            return Q.chamfer(np.vstack(V), np.vstack(F), ref, partial=partial)
        b, a = cf(Mb), cf(Ma)
        rows[hid] = {"members": ids, "partial_label": partial, "z_to_her_before": round(b[0], 2), "her_to_z_before": round(b[1], 2), "mean_before": round(b[2], 2),
                     "z_to_her_after": round(a[0], 2), "her_to_z_after": round(a[1], 2), "mean_after": round(a[2], 2)}
    out["her_label_chamfer_mm"] = rows
    out["her_label_chamfer_median_mm"] = {"before": round(float(np.median([r["mean_before"] for r in rows.values()])), 2),
                                          "after": round(float(np.median([r["mean_after"] for r in rows.values()])), 2), "groups": len(rows)}
    # 2. containment
    rng = np.random.default_rng(0)
    cont = {}
    for cat in ("muscle", "fascia", "nerve", "vessel", "tendon", "ligament"):
        res = {}
        for tag, S_ in (("before", sb), ("after", sa)):
            ids = [d["id"] for d in S_ if d["cat"] == cat and Au.region_of(d) and not Au.HAND.search(d["id"])]
            by = {d["id"]: d for d in S_}
            P = np.vstack([by[k]["v"][::max(1, len(by[k]["v"]) // 400)] for k in ids])
            res[tag] = {"n_structures": len(ids), "outside_her_skin": round(float((~skin.contains(P)).mean()), 4), "inside_her_bone_gt1mm": round(float((G.depth(P) > 1).mean()), 4)}
        cont[cat] = res
    out["containment"] = cont
    # 3. symmetry
    s0, base = Au.lr_symmetry(sb, axis, None, her)
    s1, _ = Au.lr_symmetry(sa, axis, None, None)
    out["lr_symmetry_mm"] = {"pairs": len(s0), "before_mean": round(float(np.mean(list(s0.values()))), 2), "after_mean": round(float(np.mean(list(s1.values()))), 2),
                             "her_own_pairs_mean": round(float(np.mean(list(base.values()))), 2) if base else None, "her_pairs": len(base),
                             "per_pair": {k: [round(s0[k], 2), round(s1[k], 2), round(base[k], 2) if k in base else None] for k in sorted(s0)}}
    # 4. overlap
    o0, o1 = Au.overlap(sb), Au.overlap(sa)
    ks = sorted(o0)
    out["muscle_overlap"] = {"muscles": len(ks), "mean_vertex_fraction_inside_another_before": round(float(np.mean([o0[k] for k in ks])), 4),
                             "after": round(float(np.mean([o1[k] for k in ks if k in o1])), 4),
                             "per_muscle": {k: [round(o0[k], 4), round(o1.get(k, float('nan')), 4)] for k in ks}}
    # 5. front crease + back skin
    class _R:
        pass
    r = _R(); r.axis = axis
    out["front_crease"] = {"before": A186.crease_stats(Mb, r), "after": A186.crease_stats(Ma, r)}
    chart = Q.outline_chart(skin, axis)
    ys, ths, Rs, tr = chart
    gaps = {}
    for tag, S_ in (("before", sb), ("after", sa)):
        g_all, out_all, n = [], 0, 0
        grp = {}
        for d in S_:
            if d["cat"] != "skin" or Q.LIMB_SKIN.search(d["id"]) or Au.region_of(d) is None:
                continue
            v = d["v"]
            xc, zc = axis(v[:, 1]); rr = np.hypot(v[:, 0] - xc, v[:, 2] - zc); th = np.arctan2(v[:, 0] - xc, v[:, 2] - zc)
            Rh = T.bilinear(Rs, ys, ths, v[:, 1], th); trm = T.bilinear(tr.astype(float), ys, ths, v[:, 1], th) > 0.99
            ok = trm & (np.abs(np.degrees(th)) > 100) & (v[:, 1] > -100) & (v[:, 1] < 300)
            if ok.any():
                grp[d["id"]] = Rh[ok] - rr[ok]
            n += len(v); out_all += int((~skin.contains(v[::3])).sum()) * 3
        allg = np.concatenate(list(grp.values()))
        gaps[tag] = {"back_gap_her_minus_fitted_mm": {"median": round(float(np.median(allg)), 2), "p90": round(float(np.percentile(allg, 90)), 2), "p10": round(float(np.percentile(allg, 10)), 2)},
                     "skin_vertices_outside_her_skin_frac": round(out_all / n, 4),
                     "worst_patches_median_gap": {k: round(float(np.median(v)), 1) for k, v in sorted(grp.items(), key=lambda kv: -np.median(kv[1]))[:8]}}
    out["back_skin"] = gaps
    Path(args.out).write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("her_label_chamfer_median_mm", "containment", "front_crease")}, default=float)[:3000])
    print({k: out[k] for k in ("muscle_overlap",)}["muscle_overlap"]["mean_vertex_fraction_inside_another_before"], out["muscle_overlap"]["after"])
    print(out["lr_symmetry_mm"]["before_mean"], out["lr_symmetry_mm"]["after_mean"], out["lr_symmetry_mm"]["her_own_pairs_mean"])
    print(json.dumps(out["back_skin"], default=float)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
