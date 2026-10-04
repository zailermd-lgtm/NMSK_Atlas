"""Q186c audit: the female Z-Anatomy trunk BEFORE (build/viewer_zan_female) vs AFTER (build/viewer_zan_female_trunkfix)
measured against HER OWN CT: her CT skin (build/vh/ct_vhf_skin), her TotalSegmentator rib / vertebra labels, her own
muscle meshes.

    python3 scripts/zanatomy/trunk_refit_q186c_audit.py [--before DIR] [--after DIR] [--png OUT.png] [--out OUT.json]

On the shipped (decimated) geometry: trunk skin patches vs her skin (horizontal ray from her trunk axis; the front/back
sectors are the fair comparison, her lateral outline is fused with her arms), share of vertices outside her skin and > 1 mm
inside her bone / lung / organ labels per layer, ribs + vertebrae vs her labels, rib-cage width/depth per height, trunk
muscles vs her own muscle meshes, plus the width/depth-vs-height profile plot.
"""
from __future__ import annotations

import argparse
import base64
import collections
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import trunk_refit_q186c as T  # noqa: E402

LIMB_RE = ("arm", "forearm", "wrist", "hand", "digits", "palm", "nail", "perionyx", "thigh", "foramen", "radial", "bicipital",
           "border_of_forearm", "deltoid_region", "foveola", "sternocleido", "muscular_triangle", "anal", "gluteal_fold")
WALL_MUSCLES = ("external_oblique", "internal_oblique", "rectus_abdominis", "serratus_anterior", "pectoralis_major", "latissimus",
                "iliocostalis", "longissimus")


# ----------------------------------------------------------------------------------- viewer geometry
def load_viewer(d: Path, stem: str = "atlas_viewer_zan_female") -> dict:
    """{id: {v (float mm, her frame), f, sys}} decoded from a built Z-Anatomy viewer directory"""
    d = Path(d)
    html = (d / f"{stem}.html").read_text()
    files = json.loads(re.search(r"window\.__ANATOMY_BIN_FILES__=(\[.*?\]);\s*window\.__ANATOMY_MANIFEST__=", html, re.S).group(1))
    i = html.index("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    man, _ = json.JSONDecoder().raw_decode(html[i:])
    blob = b"".join(base64.b64decode((d / f["path"]).read_bytes()) if f.get("enc") == "base64" else (d / f["path"]).read_bytes()
                    for f in files)
    out = {}
    for m in man["meshes"]:
        q = np.frombuffer(blob, "<u2", m["vc"] * 3, m["vo"]).reshape(-1, 3).astype(np.float64)
        v = np.asarray(m["min"]) + q / 65535.0 * np.asarray(m["span"])
        f = np.frombuffer(blob, "<u2", m["ic"] * 3, m["io"]).reshape(-1, 3).astype(np.int64)
        out[m["id"]] = {"v": v, "f": f, "sys": m["sys"]}
    return out


def trunk_skin_ids(M: dict) -> list[str]:
    out = []
    for k, m in M.items():
        if m["sys"] != "skin":
            continue
        c = m["v"].mean(0)
        if (-30 < c[1] < 600 and (abs(c[0]) < 160 or "hip_region" in k)) and not any(s in k for s in LIMB_RE):
            out.append(k)
    return out


# ----------------------------------------------------------------------------------- her reference
class Ref:
    def __init__(self):
        from scripts.placement_sweep_q185 import Body
        self.B = Body("vhf")
        self.skin, self.skin_tree = self.B.skin, self.B.skin_tree
        self.axis = T.trunk_axis(np.asarray(self.skin.vertices, np.float64))
        self.ray = None

    def radial_gap(self, pts: np.ndarray):
        """her skin radius along the horizontal ray from her trunk axis minus the point's radius (> 0: inside her skin)"""
        from trimesh.ray.ray_pyembree import RayMeshIntersector
        self.ray = self.ray or RayMeshIntersector(self.skin)
        xc, zc = self.axis(pts[:, 1])
        d = np.stack([pts[:, 0] - xc, np.zeros(len(pts)), pts[:, 2] - zc], 1)
        r = np.linalg.norm(d, axis=1)
        d /= np.maximum(r, 1e-6)[:, None]
        org = np.stack([xc, pts[:, 1], zc], 1)
        loc, ir, _ = self.ray.intersects_location(org, d, multiple_hits=True)
        far = np.full(len(pts), np.nan)
        if len(loc):
            np.fmax.at(far, ir, np.linalg.norm(loc - org[ir], axis=1))
        th = np.degrees(np.arctan2(pts[:, 0] - xc, pts[:, 2] - zc))
        return far - r, th

    def metrics(self, items: dict, max_pts: int = 20000) -> dict:
        import scripts.placement_sweep_q185 as P
        rng, out = np.random.default_rng(1), {}
        for k, m in items.items():
            v = m["v"]
            p = v if len(v) <= max_pts else v[rng.choice(len(v), max_pts, replace=False)]
            ins = self.skin.contains(p)
            dep = lambda dm: np.nan_to_num(P.sample_depth(dm, self.B.A, self.B.O, p, self.B.shape)) > 1.0
            out[k] = {"n": len(p), "outside_skin_frac": float((~ins).mean()), "in_bone_frac": float(dep(self.B.bone).mean()),
                      "in_lung_frac": float(dep(self.B.lung).mean()), "in_organ_frac": float(dep(self.B.organ).mean()),
                      "outside_max_mm": float(self.skin_tree.query(p[~ins])[0].max()) if (~ins).any() else 0.0}
        return out


def _wavg(rows, key):
    n = sum(r["n"] for r in rows)
    return round(sum(r[key] * r["n"] for r in rows) / n, 4)


# ----------------------------------------------------------------------------------- measurement of one viewer
def measure(M: dict, ref: Ref, sk: list[str], region: dict, her: dict, lab_pts: dict, per_structure: dict) -> dict:
    res = {}
    gaps, gaps_fb = [], []
    for k in sk:
        g, th = ref.radial_gap(M[k]["v"])
        ok = ~np.isnan(g)
        gaps.append(g[ok])
        fb = ok & ((np.abs(th) < T.SKIN_ANTERIOR_DEG) | (np.abs(th) > T.SKIN_POSTERIOR_DEG))
        gaps_fb.append(g[fb])
    pc = lambda a, q: {n: round(float(x), 1) for n, x in zip(("p10", "median", "p90", "p98"), np.percentile(np.concatenate(a), q))}
    res["skin_gap_her_minus_fitted_mm_all_angles"] = pc(gaps, [10, 50, 90, 98])
    res["skin_gap_her_minus_fitted_mm_front_back_sectors"] = pc(gaps_fb, [10, 50, 90, 98])
    ms = ref.metrics({k: M[k] for k in sk})
    res["skin_patches"] = {"n": len(sk), "outside_her_skin_frac": _wavg(list(ms.values()), "outside_skin_frac")}
    ids = [k for k, m in M.items() if m["sys"] not in ("bone", "skin") and region.get(k) == "trunk"]
    mt = ref.metrics({k: M[k] for k in ids})
    by = collections.defaultdict(list)
    for k in ids:
        by[M[k]["sys"]].append(mt[k])
    res["soft_trunk_by_layer"] = {c: {"structures": len(L), **{f: _wavg(L, f) for f in ("outside_skin_frac", "in_bone_frac", "in_lung_frac", "in_organ_frac")}}
                                  for c, L in by.items()}
    rb = {}
    for mid, pts in lab_pts.items():
        if mid in M:
            v = M[mid]["v"]
            rb[mid] = (float(np.median(cKDTree(pts).query(v)[0])), float(np.median(cKDTree(v).query(pts)[0])))
    for name, key in (("ribs", "rib"), ("vertebrae", "vertebra")):
        a = np.array([x for k, x in rb.items() if key in k])
        res[f"{name}_vs_her_ct_label_mm"] = {"n": len(a), "Z_to_label_median": round(float(np.median(a[:, 0])), 1),
                                             "label_to_Z_median": round(float(np.median(a[:, 1])), 1)}
    # posterior / shoulder / pelvis: skin groups vs her skin, and every non-bone structure by zone
    groups = {"shoulder skin (deltoid, scapular, supra/infraclavicular, deltopectoral)": ("deltoid_region", "scapular_region", "supraclavicular", "infraclavicular", "deltopectoral", "triangle_of_ausc"),
              "lumbar + sacral skin": ("lumbar_region", "sacral_region", "vertebral_region", "infrascapular"),
              "gluteal + hip skin": ("gluteal_region", "hip_region"),
              "chest + abdomen front skin": ("pectoral", "mammary", "inframammary", "presternal", "epigastric", "umbilical", "hypogastric", "hypochondriac", "inguinal"),
              "flank skin": ("lateral_region_of",)}
    res["skin_by_group"] = {}
    for gname, keys in groups.items():
        ks = [k for k, m in M.items() if m["sys"] == "skin" and any(t in k for t in keys)]
        if not ks:
            continue
        gg = np.concatenate([ref.radial_gap(M[k]["v"])[0] for k in ks])
        gg = gg[~np.isnan(gg)]
        mm = ref.metrics({k: M[k] for k in ks})
        res["skin_by_group"][gname] = {"patches": len(ks), "gap_her_minus_fitted_median": round(float(np.median(gg)), 1), "gap_p10": round(float(np.percentile(gg, 10)), 1),
                                       "gap_p90": round(float(np.percentile(gg, 90)), 1), "outside_her_skin_frac": _wavg(list(mm.values()), "outside_skin_frac"),
                                       "outside_max_mm": round(max(m["outside_max_mm"] for m in mm.values()), 1)}
    def zone(m):
        c = m["v"].mean(0)
        if c[1] < 110: return "pelvis/buttock (y<110)"
        if c[1] < 430: return "abdomen/lower thorax (110-430)"
        if abs(c[0]) > 110 and c[1] > 470: return "shoulder"
        return "upper thorax"
    zi = {k: m for k, m in M.items() if m["sys"] != "bone" and -140 < m["v"][:, 1].mean() < 640 and abs(m["v"][:, 0].mean()) < 260
          and not any(t in k for t in ("forearm", "wrist", "hand", "digit", "palm", "nail", "perionyx", "phalang", "carpal", "metacarp", "finger", "thumb", "pollic"))}
    mz = ref.metrics(zi, max_pts=12000)
    byz = collections.defaultdict(lambda: collections.defaultdict(list))
    for k, m in zi.items():
        byz[zone(m)][m["sys"]].append(mz[k])
    res["zones"] = {z: {c: {"structures": len(L), **{f: _wavg(L, f) for f in ("outside_skin_frac", "in_bone_frac", "in_lung_frac", "in_organ_frac")}} for c, L in d.items()} for z, d in byz.items()}
    res["per_bone_vs_her_label_mm"] = {k: [round(a, 1), round(b, 1)] for k, (a, b) in rb.items()}
    zr = np.concatenate([M[k]["v"] for k in M if M[k]["sys"] == "bone" and k.startswith("zan_") and k.endswith(("rib_l", "rib_r"))])
    lab = np.vstack(list(lab_pts_ribs(lab_pts)))
    res["rib_cage_bands"] = {}
    for y0 in range(240, 580, 40):
        a = lab[(lab[:, 1] >= y0) & (lab[:, 1] < y0 + 40)]
        b = zr[(zr[:, 1] >= y0) & (zr[:, 1] < y0 + 40)]
        res["rib_cage_bands"][str(y0)] = {"her_width": round(float(np.percentile(np.abs(a[:, 0]), 98) * 2)), "Z_width": round(float(np.percentile(np.abs(b[:, 0]), 98) * 2)),
                                          "her_depth": round(float(np.ptp(a[:, 2]))), "Z_depth": round(float(np.ptp(b[:, 2])))}
    rows = {}
    for k, v in per_structure.items():
        if v["region"] == "trunk" and v["cat"] == "muscle" and k in M and k in her and not v.get("fit_target"):
            hv = her[k]["v"]
            hv = hv[np.random.default_rng(1).choice(len(hv), min(len(hv), 20000), replace=False)]
            z = M[k]["v"]
            rows[k] = (float(np.median(cKDTree(z).query(hv)[0])), float(np.median(cKDTree(hv).query(z)[0])))
    a = np.array(list(rows.values()))
    res["trunk_muscles_vs_her_own_mesh_mm"] = {"n": len(a), "her_mesh_to_Z_median": round(float(np.median(a[:, 0])), 1),
                                               "Z_to_her_mesh_median": round(float(np.median(a[:, 1])), 1)}
    res["trunk_muscles_her_mesh_to_Z_mm"] = {k: round(x[0], 1) for k, x in rows.items()}
    return res


def lab_pts_ribs(lab_pts):
    return [p for k, p in lab_pts.items() if "rib" in k]


# ----------------------------------------------------------------------------------- profile plot
def profile_plot(Mb: dict, Ma: dict, sk: list[str], ref: Ref, lab_pts: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ys = np.arange(-40, 601, 10.0)
    lab = np.vstack(lab_pts_ribs(lab_pts))

    def ext(V, y, h=8):
        s = np.abs(V[:, 1] - y) < h
        return (np.percentile(V[s, 0], 1), np.percentile(V[s, 0], 99), V[s, 2].min(), V[s, 2].max()) if s.sum() > 8 else (np.nan,) * 4

    def groups(M):
        ribs = np.concatenate([m["v"] for k, m in M.items() if m["sys"] == "bone" and k.startswith("zan_") and k.endswith(("rib_l", "rib_r"))])
        mus = np.concatenate([M[k]["v"] for k in M if M[k]["sys"] == "muscle" and any(t in k for t in WALL_MUSCLES)])
        skin = np.concatenate([M[k]["v"] for k in sk])
        return {n: np.array([ext(V, y) for y in ys]) for n, V in (("skin", skin), ("ribs", ribs), ("muscle", mus))}

    rb, ra = groups(Mb), groups(Ma)
    her_rib = np.array([ext(lab, y) for y in ys])
    # her skin AP depth from the axis ray (front + back, one crossing there)
    sv = ref.skin
    from scripts.zanatomy.trunk_refit_q186c import her_outline_chart
    cyy = np.arange(-60.0, 641.0, 10.0)
    R, _, _ = her_outline_chart(sv, ref.axis, cyy, np.radians(np.array([0.0, 180.0])))
    her_depth = np.interp(ys, cyy, R[:, 0] + R[:, 1])
    w = lambda r: r[:, 1] - r[:, 0]
    d = lambda r: r[:, 3] - r[:, 2]
    fig, ax = plt.subplots(1, 3, figsize=(19, 8))
    a = ax[0]
    a.plot(w(her_rib), ys, "k", lw=2.4, label="her CT rib labels")
    a.plot(w(rb["ribs"]), ys, "tab:red", label="Z ribs BEFORE (Q168)")
    a.plot(w(ra["ribs"]), ys, "tab:green", lw=2, label="Z ribs AFTER (Q186c)")
    a.set_title("Rib-cage width L-R (mm)"); a.legend(loc="lower right"); a.set_xlim(0, 330)
    a = ax[1]
    a.plot(w(rb["skin"]), ys, "tab:red", label="fitted skin BEFORE"); a.plot(w(ra["skin"]), ys, "tab:green", lw=2, label="fitted skin AFTER")
    a.plot(w(rb["muscle"]), ys, "tab:red", ls="--", label="wall muscles BEFORE"); a.plot(w(ra["muscle"]), ys, "tab:green", ls="--", label="wall muscles AFTER")
    a.plot(w(her_rib), ys, "k", lw=1.5, label="her rib labels (inner reference)")
    a.set_title("Trunk width L-R (mm); her skin outline is fused with her arms laterally"); a.legend(loc="lower right", fontsize=8); a.set_xlim(0, 560)
    a = ax[2]
    a.plot(her_depth, ys, "k", lw=2.4, label="her CT skin A-P depth (axis ray, front+back)")
    a.plot(d(rb["skin"]), ys, "tab:red", label="fitted skin BEFORE"); a.plot(d(ra["skin"]), ys, "tab:green", lw=2, label="fitted skin AFTER")
    a.plot(d(her_rib), ys, "k", ls="--", lw=1, label="her rib labels"); a.plot(d(ra["ribs"]), ys, "tab:green", ls="--", lw=1, label="Z ribs AFTER")
    a.set_title("Trunk depth A-P (mm)"); a.legend(loc="lower right", fontsize=8); a.set_xlim(0, 330)
    for x in ax:
        x.set_ylabel("y (mm, pelvis to shoulders)"); x.set_ylim(-40, 600); x.grid(alpha=.3)
    fig.suptitle("Q186c: width / depth vs height, female Z-Anatomy trunk (before = shipped viewer, after = trunk refit)")
    fig.tight_layout(); fig.savefig(out, dpi=75); plt.close(fig)


def posterior_profile(Mb: dict, Ma: dict, ref: Ref, out: Path) -> dict:
    """back-surface depth (min z of the skin) vs height at the midline and 80 mm either side: fitted vs her CT skin.
    Her back is flat (CT table), so this is the reference the buttocks / lumbar / scapular skin may not exceed."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ys = np.arange(-120, 600, 10.0)
    her = np.asarray(ref.skin.vertices, np.float64)

    def prof(V, x0, w=18.0, h=6.0):
        o = []
        for y in ys:
            s = (np.abs(V[:, 1] - y) < h) & (np.abs(V[:, 0] - x0) < w)
            o.append(V[s, 2].min() if s.sum() > 3 else np.nan)
        return np.array(o)

    def skin_all(M):
        return np.concatenate([m["v"] for k, m in M.items() if m["sys"] == "skin" and not any(t in k for t in LIMB_RE + ("thigh", "gluteal_fold"))
                               and -150 < m["v"][:, 1].mean() < 620 and abs(m["v"][:, 0].mean()) < 200])
    sb, sa = skin_all(Mb), skin_all(Ma)
    fig, ax = plt.subplots(1, 3, figsize=(18, 8))
    stats = {}
    for a, x0 in zip(ax, (-80, 0, 80)):
        h, b, c = prof(her, x0), prof(sb, x0), prof(sa, x0)
        a.plot(h, ys, "k", lw=2.4, label="her CT skin (back surface)"); a.plot(b, ys, "tab:red", label="fitted skin BEFORE")
        a.plot(c, ys, "tab:green", lw=2, label="fitted skin AFTER"); a.set_title(f"back surface z (mm) at x = {x0:+d} mm"); a.grid(alpha=.3)
        a.set_ylabel("y (mm, pelvis to shoulders)"); a.legend(loc="lower right", fontsize=8)
        ok = ~np.isnan(h) & ~np.isnan(b) & ~np.isnan(c)
        stats[str(x0)] = {"median_abs_gap_before": round(float(np.nanmedian(np.abs(h - b)[ok])), 1), "median_abs_gap_after": round(float(np.nanmedian(np.abs(h - c)[ok])), 1),
                          "max_protrusion_behind_her_back_before": round(float(np.nanmax((h - b)[ok])), 1), "max_protrusion_behind_her_back_after": round(float(np.nanmax((h - c)[ok])), 1)}
    fig.suptitle("Q186c: posterior contour (back surface depth vs height), fitted vs her CT skin")
    fig.tight_layout(); fig.savefig(out, dpi=75); plt.close(fig)
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_trunkfix"))
    ap.add_argument("--png", default=None)
    ap.add_argument("--png-posterior", default=None)
    ap.add_argument("--out", default=str(REPO / "data" / "derived" / "Q186c_trunk_refit_audit.json"))
    args = ap.parse_args(argv)
    from scripts.transfer import zan_to_vhf_whole_body as Q
    rep = json.loads((REPO / "data" / "derived" / "Q168_zan_to_vhf.json").read_text())
    Mb, Ma = load_viewer(Path(args.before)), load_viewer(Path(args.after))
    ref, her, vol = Ref(), Q.load_her_meshes(), T.load_her_vol()
    lab_pts = {mid: T.rib_label_points(lab, vol) for mid, lab in T.bone_targets().items()}
    sk = trunk_skin_ids(Mb)
    out = {"before": measure(Mb, ref, sk, rep["region_of_structure"], her, lab_pts, rep["per_structure"]),
           "after": measure(Ma, ref, sk, rep["region_of_structure"], her, lab_pts, rep["per_structure"]),
           "trunk_skin_patches": sk}
    Path(args.out).write_text(json.dumps(out, indent=1))
    if args.png:
        profile_plot(Mb, Ma, sk, ref, lab_pts, Path(args.png))
    if args.png_posterior:
        out["posterior_contour"] = posterior_profile(Mb, Ma, ref, Path(args.png_posterior))
        Path(args.out).write_text(json.dumps(out, indent=1))
    for t in ("before", "after"):
        print(t, json.dumps({k: v for k, v in out[t].items() if k in ("skin_gap_her_minus_fitted_mm_front_back_sectors", "skin_patches", "ribs_vs_her_ct_label_mm", "vertebrae_vs_her_ct_label_mm", "trunk_muscles_vs_her_own_mesh_mm")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
