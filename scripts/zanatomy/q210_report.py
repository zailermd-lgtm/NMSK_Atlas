#!/usr/bin/env python3
"""Q210 report stage: before (published Q208 page) -> after (Q210 state) numbers for the three fixes; data/derived/Q210_report_male.json and build/q210/male_report.pkl (the card badges use it).
    python3 scripts/zanatomy/q210_report.py"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q210_core as K  # noqa: E402
from scripts.zanatomy import q207_geom as G  # noqa: E402
from scripts.zanatomy import q207_uro as U7  # noqa: E402
from scripts.zanatomy import q208_core as K8  # noqa: E402
from scripts.zanatomy import q208_eval as E8  # noqa: E402
from scripts.zanatomy import q210_contact as CT  # noqa: E402
from scripts.zanatomy import q210_struct as ST  # noqa: E402

R2 = lambda x, n=2: round(float(x), n)


def final_state():
    V = pickle.load(open(K.state_path("contact"), "rb"))[0]
    return V


def seams(pg, raw, V):
    from scripts.zanatomy import q199_elbow as EL
    sids = sorted(i for i in pg.skin_ids if i in raw.S)
    rawd = {i: raw.v(i) for i in sids}
    by = {i: {"v": V[i], "f": pg.f(i), "cat": "skin"} for i in sids}
    return EL.skin_seam_rows(by, rawd, None, sids)


def seam_summary(rows):
    return {"steps_gt_2mm": int(sum(r["step_mm_max"] > 2 for r in rows)), "steps_gt_3mm": int(sum(r["step_mm_max"] > 3 for r in rows)), "max_step_mm": R2(max(r["step_mm_max"] for r in rows)),
            "worst": [[r["a"][9:], r["b"][9:], r["step_mm_max"]] for r in sorted(rows, key=lambda r: -r["step_mm_max"])[:5]]}


def forearm_trunk(pg, V):
    """Q209 measure on a skin state: deep face pairs forearm / elbow slabs | every non-arm-hand patch (Q209 category 'fore_vs_trunk_thigh')"""
    fore = {i for i in pg.skin_ids if CT.BASE(i) in K8.TUBE + K8.ELBOW}
    fv = np.concatenate([V[i] for i in fore])
    lo, hi = fv.min(0) - 20, fv.max(0) + 20
    cand = sorted({i for i in pg.skin_ids if "nail_plate" not in i and "perionyx" not in i and (V[i].max(0) >= lo).all() and (V[i].min(0) <= hi).all()} | fore)
    Vc, F, ow, nm = G.concat({i: (V[i], pg.f(i)) for i in cand})
    pr = G.intersecting_pairs(Vc, F, ow)
    dd = G.pair_depth(Vc, F, pr) if len(pr) else np.zeros(0)
    rows = []
    for (x, y), d in zip(pr, dd):
        a, b = nm[ow[x]], nm[ow[y]]
        if (a in fore) != (b in fore) and CT.BASE(b if a in fore else a) not in CT.NB:
            rows.append((a, b, float(d), x, y))
    deep = [r for r in rows if r[2] > 2]
    d_ft = np.array([r[2] for r in deep])
    pp = {}
    for a, b, d, x, y in deep:
        pp.setdefault(tuple(sorted((a[9:], b[9:]))), []).append(d)
    area = G_area(Vc, F)
    fa = {r[3] for r in deep} | {r[4] for r in deep}
    out = {"candidates": len(cand), "forearm_trunk_pairs_gt0": len(rows), "forearm_trunk_pairs_gt0_3": sum(r[2] > 0.3 for r in rows), "deep_gt2": len(deep), "deep_gt4": int((d_ft > 4).sum()), "deep_gt8": int((d_ft > 8).sum()), "deep_gt12": int((d_ft > 12).sum()),
           "depth_mm_median_p90_max": [R2(np.median(d_ft)) if len(d_ft) else 0, R2(np.percentile(d_ft, 90)) if len(d_ft) else 0, R2(d_ft.max()) if len(d_ft) else 0],
           "all_pairs_depth_max_mm": R2(max([r[2] for r in rows] or [0])),
           "patch_pairs": [{"pair": list(k), "n": len(v), "max_mm": R2(max(v))} for k, v in sorted(pp.items(), key=lambda kv: -len(kv[1]))[:8]],
           "footprint": {"faces": len(fa), "area_cm2": R2(sum(area[f_] for f_ in fa) / 100)}}
    # all other deep pairs among the candidates (fore-fore, trunk-trunk, forearm | arm / hand ...) for the 'no new crossings elsewhere' check
    other = [(nm[ow[x]], nm[ow[y]]) for (x, y), d in zip(pr, dd) if d > 2 and not ((nm[ow[x]] in fore) != (nm[ow[y]] in fore) and CT.BASE(nm[ow[y]] if nm[ow[x]] in fore else nm[ow[x]]) not in CT.NB)]
    out["other_deep_pairs_among_candidates"] = len(other)
    return out


def G_area(V, F):
    t = V[F]
    return 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)


def tube_view(pg, V, side):
    """trunk-skin vertices lying INSIDE the forearm's own outer skin tube (Q209): count, deeper than 10 mm, depth median / p90 / max"""
    rb = np.concatenate([pg.v(f"radius_{side}"), pg.v(f"ulna_{side}")])
    c0 = rb.mean(0)
    ax = np.linalg.svd(rb - c0, full_matrices=False)[2][0]
    palm = V[f"zan_skin_palm_{side}"].mean(0)
    if (palm - c0) @ ax < 0:
        ax = -ax
    t_ = (rb - c0) @ ax
    tmin, tmax = float(t_.min()), float(t_.max())
    ref = np.cross(ax, [0, 0, 1.0]); ref /= np.linalg.norm(ref); ref2 = np.cross(ax, ref)

    def cyl(P):
        q = P - c0
        return q @ ax, np.arctan2(q @ ref2, q @ ref), np.linalg.norm(q - np.outer(q @ ax, ax), axis=1)
    fv = np.concatenate([V[i] for i in CT.forearm_ids(pg, side)])
    t, th, r = cyl(fv)
    nb_t, nb_a = 28, 24
    edges = np.linspace(tmin - 10, tmax + 10, nb_t + 1)
    R = np.full((nb_t, nb_a), np.nan)
    for i in range(nb_t):
        m = (t >= edges[i]) & (t < edges[i + 1])
        ab = np.minimum(((th[m] + np.pi) / (2 * np.pi) * nb_a).astype(int), nb_a - 1)
        for j in range(nb_a):
            if (ab == j).any():
                R[i, j] = r[m][ab == j].max()
    trunk = [i for i in pg.skin_ids if i not in CT.forearm_ids(pg) and CT.BASE(i) not in CT.NB + K8.ELBOW and "nail_plate" not in i and "perionyx" not in i]
    tv = np.concatenate([V[i] for i in trunk])
    tt, tth, tr_ = cyl(tv)
    ti = np.clip(np.floor((tt - (tmin - 10)) / (tmax + 20 - tmin) * nb_t).astype(int), 0, nb_t - 1)
    ta = np.minimum(((tth + np.pi) / (2 * np.pi) * nb_a).astype(int), nb_a - 1)
    ok = (tt > tmin) & (tt < tmax) & (tr_ < 120)
    depth = np.where(ok & np.isfinite(R[ti, ta]), R[ti, ta] - tr_, -1e9)
    d = depth[depth > 2]
    return {"vertices_inside_tube": int((depth > 2).sum()), "gt10mm": int((depth > 10).sum()), "depth_median_p90_max_mm": [R2(np.median(d)), R2(np.percentile(d, 90)), R2(d.max())] if len(d) else [0, 0, 0]}


def margins(pg, V, V0, tissue, ids, isF):
    """distance of the skin vertices of ids to the own deep tissue before / after: min and 1st percentile (forearm skin over forearm tissue, trunk skin over trunk tissue)"""
    out = {}
    for i in ids:
        tr = cKDTree(tissue[i[-1]] if isF(i) else tissue["trunk"])
        d0, d1 = tr.query(V0[i])[0], tr.query(V[i])[0]
        out[i] = {"min_margin_mm": [R2(d0.min(), 1), R2(d1.min(), 1)], "p5_margin_mm": [R2(np.percentile(d0, 5), 1), R2(np.percentile(d1, 5), 1)]}
    return out


def genital_block(pg, raw, V0, V1, log=print):
    out = {}
    sf0 = K.coarse(pg, V0)
    sf1 = K.coarse(pg, V1)
    fine0 = K.fine_box(pg, V0, sf0)
    fine1 = K.fine_box(pg, V1, sf1)
    r0, r1 = K.outside_rows(pg, sf0, fine=fine0), K.outside_rows(pg, sf1, fine=fine1)
    out["structures"] = {i: {"before": r0[i], "after": r1[i]} for i in r0}
    out["envelope_L"] = [R2(sf0.vol_L, 1), R2(sf1.vol_L, 1)]
    ids = list(K.UROS)
    vol = lambda V, i: round(U7.volume(V[i], pg.f(i)))
    out["volume_mm3"] = {i[-1]: [vol(V0, i), vol(V1, i), vol({k: raw.v(k) for k in ids}, i)] for i in ids}
    sl, sr = np.abs(raw.v(ids[0])[:, 0]) < 1.2, np.abs(raw.v(ids[1])[:, 0]) < 1.2
    for tag, Vk in (("before", V0), ("after", V1)):
        l, r = Vk[ids[0]], Vk[ids[1]]
        P = np.vstack([l[sl], r[sr]])
        c = P.mean(0)
        n = np.linalg.svd(P - c)[2][2]
        if (r.mean(0) - c) @ n < 0:
            n = -n
        out["across_midline_plane_mm_" + tag] = {"l_reaches_into_r_side": R2(((l - c) @ n).max(), 1), "r_reaches_into_l_side": R2((-(r - c) @ n).max(), 1)}
    # structure fit scale vs the Z source (evidence for the volume target): closed meshes volume ratio, penis length ratio
    import trimesh
    sc = {}
    for i in ("zan_testis_l", "zan_testis_r", "zan_corpus_spongiosum_of_penis", "zan_epididymis_l", "zan_epididymis_r"):
        a, b = trimesh.Trimesh(raw.v(i), raw.f(i), process=False), trimesh.Trimesh(pg.v(i), pg.f(i), process=False)
        sc[i] = {"volume_ratio_fit_over_source": R2(b.volume / a.volume)}
    for i in ("zan_corpus_cavernosum_of_penis", "zan_urethra", "zan_glans_penis"):
        a, b = raw.v(i), pg.v(i)
        ext = lambda v: float(np.ptp((v - v.mean(0)) @ np.linalg.svd(v - v.mean(0), full_matrices=False)[2][0]))
        sc[i] = {"axis_length_ratio_fit_over_source": R2(ext(b) / ext(a))}
    out["structure_fit_scale"] = sc
    # the rejected alternative: move the structures with the Q207 skin warp (Gaussian-weighted displacement of the Q206 -> Q208 skin vertices)
    out["alternative_move_structures_with_skin_warp"] = alt_structure_warp(pg, sf0)
    # own skin
    from scripts.zanatomy.q207_inflate import OwnSkin
    own = OwnSkin("male")
    out["structures_outside_own_skin_pct"] = {i: R2((own.sd(pg.v(i)) > 0).mean() * 100, 1) for i in K.GEN_MAIN}
    return out


def alt_structure_warp(pg, sf):
    pg6 = K.C7.Page("male", src=REPO / "build/q206/viewer_zan_vhm", stem=K.PAGE["stem"])
    ids = list(K.UROS)
    P6 = np.vstack([pg6.v(i) for i in ids])
    P8 = np.vstack([pg.v(i) for i in ids])
    d = P8 - P6
    t = cKDTree(P6)

    def warp(x, sig=8.0):
        nb = t.query_ball_point(x, 3 * sig)
        o = np.zeros_like(x)
        for k, l in enumerate(nb):
            if not l:
                dd, j = t.query(x[k])
                o[k] = d[j]
                continue
            w = np.exp(-np.linalg.norm(P6[l] - x[k], axis=1) ** 2 / (2 * sig ** 2))
            o[k] = (w[:, None] * d[l]).sum(0) / w.sum()
        return o

    def ext(v):
        c = v - v.mean(0)
        p = c @ np.linalg.svd(c, full_matrices=False)[2][0]
        return float(p.max() - p.min())
    rows = {}
    for i in K.GEN_MAIN:
        v = pg.v(i)
        u = warp(v)
        rows[i] = {"move_mean_mm": R2(np.linalg.norm(u, axis=1).mean(), 1), "move_max_mm": R2(np.linalg.norm(u, axis=1).max(), 1), "axis_extent_mm": [R2(ext(v), 1), R2(ext(v + u), 1)]}
    return rows


def contact_block(pg, raw, V0, V1, tissue, rep, log=print):
    out = {"before": forearm_trunk(pg, V0), "after": forearm_trunk(pg, V1)}
    out["tube_view"] = {s: {"before": tube_view(pg, V0, s), "after": tube_view(pg, V1, s)} for s in "lr"}
    free = rep["free"]
    isF = lambda i: i in rep["F"]
    out["margins"] = margins(pg, V1, V0, tissue, free, isF)
    out["rho"] = rep["rho"]
    out["history"] = rep["hist"]
    return out


def run(log=print):
    t0 = time.time()
    pg, raw = K.load()
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    V1 = final_state()
    moved = sorted(i for i in V1 if np.linalg.norm(V1[i] - V0[i], axis=1).max() > 0.05)
    log(f"{len(moved)} skin patches changed")
    rep = {"moved": {}}
    q = E8.quality(pg, V1, V0, raw, moved)
    from scripts.zanatomy.q207_inflate import OwnSkin
    own = OwnSkin("male")
    s0 = seams(pg, raw, V0)
    s1 = seams(pg, raw, V1)
    for i in moved:
        d = np.linalg.norm(V1[i] - V0[i], axis=1)
        a0, a1 = own.sd(V0[i]), own.sd(V1[i])
        sb = max([r["step_mm_max"] for r in s0 if i in (r["a"], r["b"])] or [0])
        sa = max([r["step_mm_max"] for r in s1 if i in (r["a"], r["b"])] or [0])
        rep["moved"][i] = dict(max_move_mm=R2(d.max()), mean_move_mm=R2(d.mean()), vertices=len(d), vertices_moved_gt0_3mm=int((d > 0.3).sum()), **q[i], outside_own_skin_gt2mm_pct=[R2((a0 > 2).mean() * 100), R2((a1 > 2).mean() * 100)],
                               seam_step_max_mm=[R2(sb), R2(sa)])
    rep["seams"] = {"q208": seam_summary(s0), "q210": seam_summary(s1)}
    log(f"seams {rep['seams']['q208']['steps_gt_3mm']} -> {rep['seams']['q210']['steps_gt_3mm']} steps > 3 mm; max {rep['seams']['q208']['max_step_mm']} -> {rep['seams']['q210']['max_step_mm']}")
    from scripts.zanatomy import q202_metrics as M2
    rep["escape"] = {tag: M2.escape([{"id": i, "v": VV[i], "f": pg.f(i)} for i in pg.skin_ids]) for tag, VV in (("q208", V0), ("q210", V1))}
    log("rays escaping (perineal probe): " + str({t: rep["escape"][t]["perineal_gap"]["escape_dirs"] for t in rep["escape"]}))
    gen = pickle.load(open(K.state_path("genital"), "rb"))[1]
    rep["genital"] = genital_block(pg, raw, V0, pickle.load(open(K.state_path("genital"), "rb"))[0], log)
    rep["genital"]["target_volume_mm3"] = gen["T"]
    rep["genital"]["search"] = gen["trials"]
    rep["genital"]["refit"] = {k: v for k, v in gen["rep"].items() if k != "weld"}
    rep["genital"]["weld_moves_max_mean_mm"] = gen["rep"]["weld"]
    tis = CT.tissue_points(pg)
    crep = pickle.load(open(K.state_path("contact"), "rb"))[1]
    rep["contact"] = contact_block(pg, raw, V0, V1, tis, crep, log)
    log(f"forearm|trunk deep pairs {rep['contact']['before']['deep_gt2']} -> {rep['contact']['after']['deep_gt2']}")
    # final state of the genital stage + contact stage combined: the genital block above used the genital-stage state; re-measure on the final state
    sfF = K.coarse(pg, V1)
    fineF = K.fine_box(pg, V1, sfF)
    rep["genital"]["structures_final_state"] = K.outside_rows(pg, sfF, fine=fineF)
    rep["genital"]["envelope_L_final"] = R2(sfF.vol_L, 1)
    # forearm-axis sections (Q208 measure): outline closed / segment crossings / radius step, before -> after
    from scripts.zanatomy import q208_report as R8
    rep["forearm_sections"] = {}
    for side in "lr":
        rep["forearm_sections"][side] = {"q208": R8.forearm_sections(pg, V0, side), "q210": R8.forearm_sections(pg, V1, side)}
        log(f"forearm sections {side}: {rep['forearm_sections'][side]}")
    # palmaris longus
    if K.state_path("struct").exists():
        sv, sinfo = pickle.load(open(K.state_path("struct"), "rb"))
        v0, v1, f = pg.v(ST.ID), sv[ST.ID], pg.f(ST.ID)
        ax = np.linalg.svd(v0 - v0.mean(0), full_matrices=False)[2][0]
        er = ST.edge_ratio(v0, v1, f)
        sfs = sfF
        rep["palmaris"] = {"info": sinfo, "outside_own_skin": [int((own.sd(v0) > 0).sum()), int((own.sd(v1) > 0).sum())], "max_outside_own_skin_mm": [R2(max(own.sd(v0).max(), 0), 1), R2(max(own.sd(v1).max(), 0), 1)],
                           "outside_displayed_skin_gt3_pct": [R2((sfs.signed(v0) > 3).mean() * 100), R2((sfs.signed(v1) > 3).mean() * 100)], "extent_along_axis_mm": [R2(ST.extent_along(v0, ax), 1), R2(ST.extent_along(v1, ax), 1)],
                           "edge_ratio_p1_p99": [R2(np.percentile(er, 1)), R2(np.percentile(er, 99))], "edges_gt2x": int((er > 2).sum()), "edges": int(len(er))}
    pickle.dump(rep, open(K.state_path("report"), "wb"))
    (REPO / "data" / "derived" / "Q210_report_male.json").write_text(json.dumps(rep, indent=1, default=float))
    log(f"report written [{time.time() - t0:.0f}s]")
    return rep


if __name__ == "__main__":
    run()
