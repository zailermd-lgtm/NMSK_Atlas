#!/usr/bin/env python3
"""Q217 Z male fitted page, final stage: hard guards on the polished carried muscles, arm-end pulls, metrics before / after, pack into build/q217/viewer_zan_vhm, ship-diff.
    python3 scripts/transfer/q217_final_zan.py clamp|ends|metrics|pack"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(REPO))
from scripts.transfer import q217_common as C, q217_ends as E, q217_slide as SL  # noqa: E402
from scripts.transfer.q217_carry_zan import load_pages, CACHE  # noqa: E402
from scripts.transfer.q213_inbone import laplacian  # noqa: E402

SRC = REPO / "build/q211/viewer_zan_vhm"
OUT = REPO / "build/q217/viewer_zan_vhm"
STEM = "atlas_viewer_zan_male_fitted"
SKIN_MIN_MM = 1.0


def clamp_meshes(d, G, bv, rounds=6, win=(100.0, 300.0)):
    """vertices outside the skin / closer than SKIN_MIN_MM to it go inward, vertices > 0.5 mm inside a bone go out (displacement field smoothed over the mesh, so no spikes); vertices outside `win` stay"""
    out = {}
    for i, (v, f) in d.items():
        x = v.copy()
        Lap = laplacian(len(x), f)
        anch = 60.0 * np.maximum(SL.smooth_ramp(x[:, 1], win[0], 20.0), 1.0 - SL.smooth_ramp(x[:, 1], win[1], 20.0))
        for _ in range(rounds):
            t = np.zeros_like(x)
            sg = G.signed(x)
            need = np.maximum(sg + SKIN_MIN_MM, 0.0)
            sel = need > 0
            if sel.any():
                dd, ii = G.tree.query(x[sel])
                near = G.tree.data[ii]
                inside = sg[sel] <= 0
                dirn = np.where(inside[:, None], x[sel] - near, near - x[sel])
                t[sel] += need[sel, None] * dirn / np.maximum(np.linalg.norm(dirn, axis=1, keepdims=True), 1e-6)
            dep = bv.depth(x)
            sel2 = dep > 0.5
            if sel2.any():
                g = np.zeros((sel2.sum(), 3))
                for k in range(3):
                    e = np.zeros(3)
                    e[k] = 1.0
                    g[:, k] = (bv.depth(x[sel2] + e) - bv.depth(x[sel2] - e)) / 2.0
                n = np.linalg.norm(g, axis=1, keepdims=True)
                t[sel2] += (dep[sel2, None] + 0.3) * (-g / np.maximum(n, 1e-6))
            w = ((np.linalg.norm(t, axis=1) > 0)).astype(float) * 30.0
            if not w.any():
                break
            x = x + SL.solve_disp(Lap, w, t, 1.0, anch)
        out[i] = (x, f)
    return out


def clamp(src="zan_polish.pkl", dst="zan_clamp.pkl", rounds=6):
    B, P = load_pages()
    d = pickle.load(open(CACHE / src, "rb"))
    S = C.zan_left("zan_m")
    G = C.SkinGuard([s for s in S.values() if s["sys"] == "skin"])
    bones = {i: (s["v"], s["f"]) for i, s in P.items() if s["sys"] == "bone" and i.endswith("_l")}
    pickle.dump(clamp_meshes(d, G, C.BoneVox(bones), rounds), open(CACHE / dst, "wb"))


def ends(src="zan_clamp.pkl", dst="zan_ends.pkl"):
    """pull every muscle end that lies > END_GATE_MM from the bone its card names onto that bone (<= CAP_MM), the other end held: forearm origins + the arm muscles' distal ends (biceps -> radius ...)"""
    from scripts.transfer.q216_fix import pull_anchored
    B, P = load_pages()
    d = pickle.load(open(CACHE / src, "rb"))
    bones = {i: (s["v"], s["f"]) for i, s in P.items() if s["sys"] == "bone" and i.endswith("_l")}
    bt = E.bone_trees(bones)
    items = dict(d)
    for i in C.side_ids(C.ARM):
        if i in P:
            items[i] = (P[i]["v"], P[i]["f"])
    out, rep = dict(d), {}
    for i, (v, f) in items.items():
        rec = P[i].get("rec")
        zs, u, t = E.zones(v)
        pulls, anchors, info = [], [], []
        for nm, z, bid, p5, mn in E.plan(v, rec, bt):
            other = zs["hi" if nm == "lo" else "lo"]
            info.append(dict(end=nm, bone=bid, p5_before=round(p5, 1)))
            if p5 > E.END_GATE_MM and p5 <= E.CAP_MM:
                pulls.append((z, bt[bid][1], 0.0))
                anchors.append(other)
        if not pulls:
            rep[i] = dict(ends=info, pulled=False)
            continue
        nv, pinfo = pull_anchored(v, f, pulls, anchors)
        if nv is None:
            rep[i] = dict(ends=info, pulled=False, refused=pinfo)
            continue
        out[i] = (nv, f)
        after = [round(E.zone_dist(nv, z, bt[bid][0])[0], 1) for (nm, z, bid, p5, mn) in E.plan(v, rec, bt) if p5 > E.END_GATE_MM and p5 <= E.CAP_MM]
        rep[i] = dict(ends=info, pulled=True, applied_mm=[round(x.get("applied_mm", 0), 1) for x in pinfo], p5_after=after, max_move_mm=round(float(np.linalg.norm(nv - v, axis=1).max()), 1))
        print(i[:40].ljust(40), rep[i], flush=True)
    pickle.dump(out, open(CACHE / dst, "wb"))
    pickle.dump(rep, open(CACHE / "zan_ends_rep.pkl", "wb"))


def metrics(src="zan_final.pkl"):
    B, P = load_pages()
    d = pickle.load(open(CACHE / src, "rb"))
    fm = [i for i in C.side_ids(C.FOREARM) if i in d]
    fx = [i for i in C.side_ids(C.ARM) if i in P]
    S = C.zan_left("zan_m")
    G = C.SkinGuard([s for s in S.values() if s["sys"] == "skin"])
    bones = {i: (s["v"], s["f"]) for i, s in P.items() if s["sys"] == "bone" and i.endswith("_l")}
    bv = C.BoneVox(bones)
    res = {}
    for tag, mm, fixed in (("before", {i: (P[i]["v"], P[i]["f"]) for i in fm}, {i: (P[i]["v"], P[i]["f"]) for i in fx}),
                           ("after", {i: d[i] for i in fm}, {i: d.get(i, (P[i]["v"], P[i]["f"])) for i in fx})):
        out, tot = C.muscle_metrics(mm, fixed, G, bv, ids=fm)
        res[tag] = dict(per_muscle=out, total_shared_cm3=tot, mean_shared_pct=round(float(np.mean([o["shared_pct"] for o in out.values()])), 1))
        print(tag, "total shared", tot, "mean", res[tag]["mean_shared_pct"], flush=True)
    (REPO / "data/derived/Q217_zan_metrics.json").write_text(json.dumps(res, indent=1, default=str))
    for i in fm:
        a, b = res["before"]["per_muscle"][i], res["after"]["per_muscle"][i]
        print(i[:34].ljust(34), "vol", a["vol_cm3"], "->", b["vol_cm3"], "shared", a["shared_pct"], "->", b["shared_pct"], "outside skin", a["outside_skin_pct"], "->", b["outside_skin_pct"],
              "in bone", a["in_bone_pct"], "->", b["in_bone_pct"], "depth", a["bone_depth_max_mm"], "->", b["bone_depth_max_mm"], flush=True)


def badge_forearm(i, a, b, mv, seam, ends):
    seam_txt = (f" Joined at y = 105 mm to the page's own hand-side tendon part (kept: his hand fit of Q205 / Q206), which was shifted {', '.join(str(x) for x in seam)} mm within the plane at the seam and decays to 0 over 45 mm."
                if seam else " The whole muscle lies above the seam plane.")
    e_txt = ""
    for e in ends or []:
        if e.get("pulled_mm"):
            e_txt += f" Its {e['end']} end was {e['p5_before']} mm off the {e['bone'].replace('_', ' ')} its card names and was pulled {e['pulled_mm']} mm onto it (stretched along the muscle, other end held)."
    return (f"Q217: this muscle was lying in a tangle with its neighbours on the Q211 page (share of its volume inside other muscles {a['shared_pct']} %; Z base 3.5 % mean). It is now the Z-Anatomy BASE muscle carried onto HIS "
            f"left forearm by ONE injective map: at every axial level (8 mm) the section of the base forearm is turned and shifted exactly like the two bones radius + ulna of this page (his Z-fitted bones, same vertex order as the base "
            f"bones: the pronation twist), the chain ending in the distal-humerus block above and the carpal block below, so the Z tiling (muscle | muscle) comes with it and no overlap is created.{seam_txt} "
            f"Then pushed inside his skin (>= 1 mm) and out of his bones, and separated from the neighbouring muscles with a 1.0 mm fascial interface (0.5 mm each, no volume cut). Before -> after (voxel measures, 0.5 mm): "
            f"volume {a['vol_cm3']} -> {b['vol_cm3']} cm3 (Z-Anatomy source volume kept; the page muscle had been shrunk), share inside other muscles {a['shared_pct']} -> {b['shared_pct']} %, vertices outside the displayed skin "
            f"{a['outside_skin_pct']} -> {b['outside_skin_pct']} %, > 1 mm inside a displayed bone {a['in_bone_pct']} -> {b['in_bone_pct']} % (deepest {a['bone_depth_max_mm']} -> {b['bone_depth_max_mm']} mm); mean / max move vs the Q211 mesh "
            f"{mv[0]} / {mv[1]} mm.{e_txt} Source class unchanged (Z-Anatomy fitted to him, not measured on him). His photographed forearm is mostly muscle and larger than the Z muscles: the space between the muscles is "
            f"not filled (volumes are not inflated beyond the Z source). A position and boundary estimate, not a segmentation.")


def badge_extra(i, sysn, info, before_end, after_end, in_win):
    seams = []
    for nm in ("wrist", "arm"):
        x = info.get(nm)
        if x and x.get("seam_shift_mm"):
            seams.append(f"{'wrist' if nm == 'wrist' else 'upper-arm'} seam (y = {105 if nm == 'wrist' else 350} mm): its page part was shifted {', '.join(str(a) for a in x['seam_shift_mm'])} mm within the seam plane, decaying over 45 mm")
    seam_txt = (" Joined at the " + "; ".join(seams) + ".") if seams else " It lies wholly inside the range of the map (no seam)."
    what = ("the distal part of this arm muscle" if sysn == "muscle" else "this structure")
    end_txt = f" Distance of its distal end zone to the bone its card names: {before_end} -> {after_end} mm (5th percentile)." if before_end is not None else ""
    return (f"Q217: {what} touches the forearm muscles in the Z-Anatomy base (arm | forearm adjacency: brachialis | brachioradialis ...); the forearm muscles were carried onto his left forearm by one injective twisted-tube map "
            f"(turn and shift of the section of his Z-fitted radius + ulna, chained to the distal-humerus block and the carpal block), so it is carried by the SAME map from the Z base, otherwise the pairs that touch in the base "
            f"lay 10-30 mm apart on the Q211 page.{seam_txt} Pushed inside his skin and out of his bones where needed.{end_txt} Not measured on him; Source class unchanged (Z-Anatomy fitted to him). "
            f"A position estimate of the usual course / shape.")


def pack(src="zan_final.pkl"):
    from scripts.zanatomy import q205_pages as P5
    from scripts.zanatomy import q205_shipdiff as SD
    d = pickle.load(open(CACHE / src, "rb"))
    ex = pickle.load(open(CACHE / "zan_extra_clamp.pkl", "rb"))
    exinfo = pickle.load(open(CACHE / "zan_extra.pkl", "rb"))["info"]
    info = pickle.load(open(CACHE / "zan_carry.pkl", "rb"))["info"]
    met = json.loads((REPO / "data/derived/Q217_zan_metrics.json").read_text())
    erep = pickle.load(open(CACHE / "zan_ends_rep.pkl", "rb"))
    man, blob = P5.load_page(SRC, STEM)
    pg = P5.decode(man, blob)
    B, P = load_pages()
    bones = {i: (s["v"], s["f"]) for i, s in P.items() if s["sys"] == "bone" and i.endswith("_l")}
    bt = E.bone_trees(bones)
    replace, listed = {}, []
    # forearm muscles (and EPB / biceps end pulls of the first stage; the biceps is superseded by the carried one)
    for i, (v, f) in d.items():
        if i not in pg or i in ex:
            continue
        v0 = pg[i]["v"]
        if len(v0) == len(v) and np.allclose(v0, v, atol=1e-6):
            continue
        rec = dict(pg[i]["m"].get("rec") or {})
        a, b = met["before"]["per_muscle"][i], met["after"]["per_muscle"][i]
        dd = np.linalg.norm(v - v0, axis=1) if len(v0) == len(v) else None
        mv = (round(float(dd.mean()), 1), round(float(dd.max()), 1)) if dd is not None else ("-", "-")
        ends = []
        for e in erep.get(i, {}).get("ends", []):
            e = dict(e)
            if erep[i].get("pulled") and e["p5_before"] > E.END_GATE_MM:
                e["pulled_mm"] = erep[i]["applied_mm"][0] if erep[i].get("applied_mm") else None
            ends.append(e)
        rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + " " + badge_forearm(i, a, b, mv, info.get(i, {}).get("seam_shift_mm"), ends)).strip()
        replace[i] = (v, f, rec)
    for i, (v, f) in ex.items():
        if i not in pg:
            continue
        rec = dict(pg[i]["m"].get("rec") or {})
        be = ae = None
        if pg[i]["m"]["sys"] == "muscle":
            for nm, z, bid, p5, mn in E.plan(pg[i]["v"], rec, bt):
                if nm == "lo":
                    be = round(p5, 1)
            for nm, z, bid, p5, mn in E.plan(v, rec, bt):
                if nm == "lo":
                    ae = round(p5, 1)
        rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + " " + badge_extra(i, pg[i]["m"]["sys"], exinfo[i], be, ae, None)).strip()
        replace[i] = (v, f, rec)
    man2, blob2 = P5.save_page(OUT, STEM, man, blob, replace=replace)
    r = SD.diff(SRC, OUT, STEM, sorted(replace))
    r["listed_structures"] = len(replace)
    r["by_system"] = {sy: sum(1 for i in replace if pg[i]["m"]["sys"] == sy) for sy in sorted({pg[i]["m"]["sys"] for i in replace})}
    (REPO / "data/derived/Q217_ship_diff_zan.json").write_text(json.dumps(r, indent=1))
    print("page", OUT, "replaced", len(replace), r["by_system"], "geometry_changed", len(r["geometry_changed"]), "unlisted", r["geometry_changed_but_not_listed"], "added", len(r["added"]), "removed", len(r["removed"]), "card_only", len(r["card_only"]), "unchanged", r["unchanged"])


def post(src="zan_ends.pkl", dst="zan_final.pkl"):
    """clamp (skin / bone) the muscles whose ends were pulled: the pull lands the end zone on the bone surface, the smoothing can leave a few vertices inside it"""
    B, P = load_pages()
    d = pickle.load(open(CACHE / src, "rb"))
    erep = pickle.load(open(CACHE / "zan_ends_rep.pkl", "rb"))
    todo = {i: d[i] for i in d if erep.get(i, {}).get("pulled")}
    S = C.zan_left("zan_m")
    G = C.SkinGuard([s for s in S.values() if s["sys"] == "skin"])
    bones = {i: (s["v"], s["f"]) for i, s in P.items() if s["sys"] == "bone" and i.endswith("_l")}
    out = dict(d)
    for i, (x, f) in clamp_meshes(todo, G, C.BoneVox(bones), rounds=8).items():
        out[i] = (x, f)
    pickle.dump(out, open(CACHE / dst, "wb"))


if __name__ == "__main__":
    {"clamp": clamp, "ends": ends, "post": post, "metrics": metrics, "pack": pack}[sys.argv[1]]()
