#!/usr/bin/env python3
"""Q212: remaining flat-cut planes of the two OWN reconstructed models, completed with badged Z-Anatomy where the Z structure reaches the cut.

    python3 scripts/transfer/q212_complete.py --body vhm|vhf [--dry] [--out DIR] [--rows FILE] [--extra FILE.npz]

Input = the Q203 bundle (`build/viewer_?_hr_q203`), output = a NEW bundle (`build/viewer_?_hr_q212`). Every Q203 entry is kept byte for byte: Q212 only ADDS
entries (`<id>_zfill212`, subject `xfer_zan2vh?_seams_q212`, Source facet class "Filled from Z-Anatomy"). The machinery is the Q203 one (q203_complete: caps of the measured
structure -> Z counterpart fitted to the own bones or taken from the Z page fitted to this body -> loft / local mode -> far end carried onto its bone -> inside the skin, out of the
bones, separated from the neighbour muscles), with three changes, each justified by a measured fit error:
  1. Z counterparts the Q203 id match missed: Z-Anatomy names these `zan_<name>_muscle` (orphan pool), so the own `temporalis`, `tibialis_posterior`, `semispinalis_cervicis`
     (= Z `semispinalis colli`), `extensor_pollicis_longus`, `iliopsoas` (= Z psoas major + iliacus), `levator_ani` (= Z levator ani + iliococcygeus + pubococcygeus + pubo-analis)
     and `adductor_magnus` (+ Z adductor minimus) had no counterpart in Q203 ("no Z-Anatomy counterpart mesh").
  2. Coverage: caps already continued in Q200 or Q203 are skipped (the Q203 seam file is read in addition to the Q200 one).
  3. Two-sided fit gate: the Q200 gate (median distance from the measured surface within 30 mm of the cap to the fitted Z surface <= 25 mm) is inflated where the MEASURED mass is
     larger than the Z structure (the surface that has no Z counterpart is counted). A cap that fails it is still accepted when the Z surface lies on the measured one
     (Z -> measured median <= 8 mm within the same window) AND the belly of the muscle 30-100 mm from the cap fits <= 10 mm (the 85th percentile of the 136 accepted Q203 fits is
     10.7 mm, the median 4.4 mm): the registration is right and only the measured excess is unmatched.
Bones: the Q203 bone caps are NOT re-run (the held ones are where the Z bone ends before the cut: the measured bone is the larger one)."""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))

from scripts.transfer import q203_complete as C  # noqa: E402
from scripts.transfer import q200_elbow_repair as E  # noqa: E402
from scripts.transfer.q200_geom import sample_surface, align_rigid_local  # noqa: E402
from scripts.transfer.q200_continue import find_caps, continue_cap2 as continue_cap, AX  # noqa: E402

TAG = "_zfill212"
FIT_REV_MAX_MM = 8.0       # two-sided gate: Z surface -> measured surface median within the window
FIT_BELLY_MAX_MM = 10.0    # two-sided gate: measured belly 30-100 mm from the cap -> Z surface median
LOFT_RATIO_MAX = 12.0      # loft mode: Z section / measured cap face (the 272 Q203 loft continuations of both bodies lie within 0.02 - 11.7)

C.BODY["vhm"].update(src=REPO / "build/viewer_m_hr_q203", out=REPO / "build/viewer_m_hr_q212")
C.BODY["vhf"].update(src=REPO / "build/viewer_f_hr_q203", out=REPO / "build/viewer_f_hr_q212")
C.SUFFIX = {"sh": TAG, "seam": TAG}
C.SUBJECT = {(b, g): f"xfer_zan2{b}_seams_q212" for b in ("vhm", "vhf") for g in ("sh", "seam")}
C.group_of = lambda ctx, cen, side: "seam"

# own muscle stem -> Z-Anatomy mesh stems (all with the side suffix); the stems the Q203 id match could not reach
ALIAS = {
    "temporalis": ["zan_temporalis_muscle"],
    "tibialis_posterior": ["zan_tibialis_posterior_muscle"],
    "semispinalis_cervicis": ["zan_semispinalis_colli_muscle"],          # Terminologia Anatomica: M. semispinalis cervicis = Z-Anatomy "semispinalis colli"
    "extensor_pollicis_longus": ["zan_extensor_pollicis_longus"],
    "iliopsoas": ["zan_psoas_major", "zan_iliacus_muscle"],
    "levator_ani": ["levator_ani", "zan_iliococcygeus_muscle", "zan_pubococcygeus_muscle", "zan_pubo_analis_muscle"],
    "adductor_magnus": ["adductor_magnus", "zan_adductor_minimus"],
}
C.ATT.update({
    "temporalis": ["cranium", "mandible"], "tibialis_posterior": ["tibia", "fibula"], "semispinalis_cervicis": ["cervical_vertebrae", "thoracic_vertebrae", "cranium"],
    "extensor_pollicis_longus": ["ulna", "radius"], "iliopsoas": ["lumbar_vertebrae", "hip_bone", "femur"], "levator_ani": ["hip_bone", "sacrum", "coccyx"],
    "adductor_magnus": ["hip_bone", "femur"],
})
C.ATT["extensor_pollicis_longus"] = ["ulna", "radius", "carpals", "metacarpal_1", "phalanges_hand"]
TIP_BONES = {"extensor_pollicis_longus": ["metacarpal_1", "metacarpals", "phalanges_hand"]}   # a tendon continuation must END on its insertion bone
TIP_MAX_MM = 20.0          # the Q203 biceps / brachioradialis continuations (accepted, 7+3 with beyond >= 30 mm) end 11-25 mm from their bones, median 17.5
TIP_MIN_BEYOND_MM = 30.0   # only a continuation that travels >= 30 mm beyond the cut must END on its bone (short local pieces end inside the muscle belly)
_orig_z_ids = C.z_ids


def z_ids(own_id):
    m = re.match(r"^(.*)_(l|r)$", own_id)
    if m and m.group(1) in ALIAS:
        return [f"{p}_{m.group(2)}" for p in ALIAS[m.group(1)]]
    return _orig_z_ids(own_id)


C.z_ids = z_ids


def q_covered_frac(ctx, tid, cap):
    """fraction of the cap already covered by a Q200 or Q203 continuation of this structure (same plane)"""
    from shapely.ops import unary_union
    from shapely.geometry import Polygon
    ent = []
    for suf in ("_zfill", "_zfill203", "_zfill203s"):
        ent += ctx.q200cov.get(f"{tid}{suf}", [])
    polys = [Polygon(p).buffer(0.2) for e in ent if e["axis"] == cap["axis"] and abs(e["pos"] - cap["pos"]) < 1.5 for p in e["polys"] if len(p) >= 3]
    if not polys:
        return 0.0
    capA = unary_union(cap["polys"])
    return float(unary_union(polys).intersection(capA).area / max(capA.area, 1e-9))


C.q200_covered_frac = q_covered_frac


def two_sided_fit(mv, mf, zv, zf, cap, window=30.0):
    """(Z -> measured median within the window, measured belly 30-100 mm from the cap -> Z median); None when there is too little surface"""
    k = AX[cap["axis"]]
    P = sample_surface(mv, mf, 12000, 5)
    Zs = sample_surface(zv, zf, 12000, 6)
    dm = -cap["sign"] * (P[:, k] - cap["pos"])    # mm inside the structure from the cap plane
    dz = -cap["sign"] * (Zs[:, k] - cap["pos"])
    zin = (dz > 0) & (dz < window)
    belly = (dm >= window) & (dm < 100.0)
    if zin.sum() < 30 or belly.sum() < 30:
        return None
    rev = float(np.median(cKDTree(P).query(Zs[zin])[0]))
    bel = float(np.median(cKDTree(Zs).query(P[belly])[0]))
    return rev, bel


def stage_muscles(ctx, only=None):
    own = ctx.own
    allb_tree = None
    for tid in [t for t in ctx.muscles if (not only or t in only)]:
        o = own[tid]
        m_ = re.match(r"^(.*)_(l|r)$", tid)
        stem, side = (m_.group(1), m_.group(2)) if m_ else (tid, "m")
        caps = [c for c in find_caps(o["v"], o["f"], minarea=40.0, at_end=2.0)]
        if not caps:
            continue
        cands = C.candidates(ctx, tid)
        anch = E.anchors_of(o["e"]["rec"])
        pieces = {"seam": []}
        ids = ctx.bone_ids(C.ATT[stem], side) if stem in C.ATT else []
        for cap in caps:
            ccen = o["v"][np.unique(o["f"][cap["faces"]])].mean(0)
            row = dict(id=tid, stage="muscle", group="seam", axis=cap["axis"], pos=round(cap["pos"], 1), sign=cap["sign"], area=round(cap["area"]), n_frag=cap["n_comp"])
            if cap["area"] < C.MIN_CAP_MM2:
                row["status"] = f"skipped: cap {cap['area']:.0f} mm2 < {C.MIN_CAP_MM2:g} (facet)"; ctx.rows.append(row); continue
            cov = q_covered_frac(ctx, tid, cap)
            if cov >= 0.5:
                row["status"] = f"skipped: {100 * cov:.0f} % of the cap already continued (Q200 / Q203)"; ctx.rows.append(row); continue
            prev = [x for x in ctx.q203_rows if x["id"] == tid and x["axis"] == cap["axis"] and abs(x["pos"] - cap["pos"]) < 1.5 and x.get("status") == "continued"]
            if prev:
                row["status"] = (f"skipped: already continued in Q203 ({prev[0]['mode']} mode, {100 * prev[0]['cap_covered']:.0f} % of the cap face covered by the Z section; the rest of the "
                                 f"face is where the measured mass is wider than the Z structure)")
                ctx.rows.append(row); continue
            row["skin_gap_mm"] = round(C.skin_gap_mm(ctx, cap, ccen), 1)
            if row["skin_gap_mm"] < 3.0:
                row["status"] = "skipped: the cap lies on the body surface (skin within 3 mm), not a data-block seam"; ctx.rows.append(row); continue
            if not cands:
                row["status"] = "held: no Z-Anatomy counterpart mesh (not in Z-Anatomy under this name)"; ctx.rows.append(row); continue
            bt = ctx.bone_tree(ids) if ids else None
            if bt is None:
                if allb_tree is None:
                    allb_tree = ctx.bone_tree(ctx.all_bone_ids())
                bt = allb_tree
            row["end_to_nearest_bone_mm"] = round(float(bt[0].query(ccen)[0]), 1)
            ax_m = np.linalg.svd(o["v"] - o["v"].mean(0), full_matrices=False)[2][0]
            nrm = np.zeros(3); nrm[AX[cap["axis"]]] = 1.0
            section_like = abs(float(ax_m @ nrm)) >= 0.6
            best, tried = None, []
            for cname, ZV, ZF in cands:
                ZVa, ainfo = align_rigid_local(ZV, ZF, o["v"], o["f"], AX[cap["axis"]], cap["pos"], cap["sign"])
                r = continue_cap(o["v"], cap, ZVa, ZF, min_beyond=C.MIN_BEYOND_MUSCLE, loft=True if section_like else False)
                if "v" not in r:
                    tried.append(f"{cname[:14]}: {r['reason'][:70]}"); continue
                if r["sh"] > C.MAX_SHIFT_MM:
                    tried.append(f"{cname[:14]}: Z section {r['sh']:.0f} mm off the cap face > {C.MAX_SHIFT_MM:g}"); continue
                if r["mode"] == "loft" and r["area_ratio"] > LOFT_RATIO_MAX:
                    tried.append(f"{cname[:14]}: the Z section is {r['area_ratio']:.0f}x the measured cap face (> {LOFT_RATIO_MAX:g}x, a loft would balloon the measured end)"); continue
                dd = E.fit_error(o["v"], o["f"], ZVa, ZF, cap)
                med = float(np.median(dd))
                rule = "one-sided (Q200 gate, <= 25 mm)"
                if med > E.FIT_ERR_MAX_MM:
                    ts = two_sided_fit(o["v"], o["f"], ZVa, ZF, cap)
                    if ts is None or ts[0] > FIT_REV_MAX_MM or ts[1] > FIT_BELLY_MAX_MM:
                        tried.append(f"{cname[:14]}: fit median {med:.1f} mm > {E.FIT_ERR_MAX_MM:g}" + ("" if ts is None else f" (Z->measured {ts[0]:.1f}, belly {ts[1]:.1f} mm)"))
                        continue
                    rule = f"two-sided (near-cap {med:.1f} mm > 25; Z->measured {ts[0]:.1f} mm <= {FIT_REV_MAX_MM:g}, belly {ts[1]:.1f} mm <= {FIT_BELLY_MAX_MM:g})"
                if best is None or med < best[0]:
                    best = (med, float(np.quantile(dd, .95)), r, cname, ainfo, rule)
            if best is None:
                row["status"] = "held: " + "; ".join(tried); ctx.rows.append(row); continue
            med, p95, r, cname, ainfo, rule = best
            pull_max = 40.0 if ids else 15.0
            cv, pinfo = E.pull_end(r["v"], cap["axis"], cap["pos"], cap["sign"], anch, bt, max_pull=pull_max)
            cv, cinfo = E.constrain(cv, cap["axis"], cap["pos"], cap["sign"], ctx.skin_mesh, ctx.bones_near(cv.min(0), cv.max(0)))
            tip_note = None
            if ids and r["beyond_mm"] >= TIP_MIN_BEYOND_MM:
                kk_ = AX[cap["axis"]]
                sd_ = cap["sign"] * (cv[:, kk_] - cap["pos"])
                tipv = cv[sd_ >= 0.95 * sd_.max()]
                tb = ctx.bone_tree(ctx.bone_ids(TIP_BONES.get(stem, C.ATT[stem]), side) or ids)
                tip_d = float(np.median(tb[0].query(tipv)[0]))
                row["tip_to_bone_mm"] = round(tip_d, 1)
                if tip_d > TIP_MAX_MM:
                    row["status"] = (f"held: the Z end of the continuation (best fit {med:.1f} mm, {cname[:14]}) stops {tip_d:.0f} mm from the bone it attaches to (> {TIP_MAX_MM:g} mm): "
                                     f"the Z structure does not land on this person's bone")
                    ctx.rows.append(row); continue
            r["v"] = cv; r["info"] = row
            row.update(status="continued", z_source=cname, fit_rule=rule, fit_err_median_mm=round(med, 1), fit_err_max_mm=round(p95, 1), beyond_mm=round(r["beyond_mm"], 1),
                       L=round(r["Lt"], 1), shift_mm=round(r["sh"], 1), mode=r["mode"], section_like=bool(section_like), cap_covered=round(r["cap_covered"], 2),
                       z_to_cap_area=round(r["area_ratio"], 3), pull=pinfo, constraints=cinfo, nv=len(cv), nf=len(r["f"]),
                       z_ids=C.z_ids(tid), align={k_: (round(v_, 1) if isinstance(v_, float) else v_) for k_, v_ in ainfo.items()})
            ctx.rows.append(row); pieces["seam"].append(r)
        for grp, pcs in pieces.items():
            if pcs:
                V, F, off = [], [], 0
                for r in pcs:
                    V.append(r["v"]); F.append(r["f"] + off); off += len(r["v"])
                ctx.pieces[f"{tid}{TAG}"] = dict(v=np.vstack(V), f=np.vstack(F), base=tid, cat=o["e"]["cat"], pieces=pcs, kind="muscle", group=grp)


_orig_badge = C.badge_text


def badge_text(ctx, pieces, name, kind, group):
    s = _orig_badge(ctx, pieces, name, kind, group).replace("Q203 validation", "Q212 validation")
    rules = sorted({p["info"].get("fit_rule", "") for p in pieces if p["info"].get("fit_rule", "").startswith("two-sided")})
    if rules:
        s += " Fit gate: " + "; ".join(rules) + " (the measured mass at the cut is larger than the Z structure; the Z surface itself lies on the measured one)."
    zid = sorted({i for p in pieces for i in p["info"].get("z_ids", []) if i.startswith("zan_")})
    if zid:
        s += " Z-Anatomy mesh(es): " + ", ".join(zid) + "."
    return s


C.badge_text = badge_text


def write_bundle(ctx, out):
    he = ctx.cfg["he"]
    att = {f"xfer_zan2{ctx.body}_seams_q212": (
        f"Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D): continuations of structures cut flat at CT data-block edges, fitted onto {he} own bones or taken from the Z-Anatomy page fitted to "
        f"{he} body (Q212); the measured structures are not edited. Z-Anatomy: models by the Z-Anatomy project, app by Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and "
        "third_party/z-anatomy/README.md. Licensed CC BY-SA 4.0; this derivative remains CC BY-SA 4.0 (ShareAlike).")}
    if ctx.body == "vhm":
        att[WRIST_SUBJECT] = ("His own frozen CT (Visible Human Project male, public domain; CT series 5d409385 of the NCI Imaging Data Commons mirror): wrist re-segmented in Q212 "
                              "(radius / ulna distal ends and carpal bones). No third-party geometry.")
    return ctx.B.write(out, new_subject_attribution=att)


WRIST_SUBJECT = "ct_vhm_wrist_q212"


def add_wrist(ctx, log=print):
    """HIS wrist re-segmented from his own CT (q212_wrist_seg.py -> q212_wrist_mesh.py): the radius / ulna distal ends his carpal label had swallowed are ADDED as new entries
    (measured class: subject ct_vhm_wrist_q212), the carpal row without them is added as `carpals_?_q212`; the old grouped carpal mesh (which contains the two ends) and the Q203
    Z-Anatomy ulnar head of the right wrist (contradicted by his CT: 36 % of its surface lies in bone density vs 96 % of the measured ulna's) are kept byte for byte but start hidden."""
    rows = []
    for sd, side_name in (("r", "right"), ("l", "left")):
        W = np.load(REPO / f"build/q212/wrist_mesh_{sd}.npz")
        info = json.loads(str(W["info"]))
        for key, base, nid, label in (("radius_distal", f"radius_{sd}", f"radius_{sd}_distal_q212", "distal end of his radius (articular plate and styloid)"),
                                      ("ulna_distal", f"ulna_{sd}", f"ulna_{sd}_distal_q212", "ulnar head and styloid"),
                                      ("carpals", f"carpals_{sd}", f"carpals_{sd}_q212", "eight carpal bones")):
            st = info[key]; ph = st["photo"]
            b = ctx.own[base]["e"]
            ph_txt = (f"{100 * ph['within_1p5mm']:.0f} % of its voxels inside the photographed box ({100 * ph['in_photo_box']:.0f} % of the piece) lie within 1.5 mm of his cryosection-photograph bone evidence"
                      if ph.get("within_1p5mm") is not None else "outside the photographed box")
            if key == "carpals":
                core = (f"Measured on HIM, re-segmented from his frozen CT (Q212): the {label} ({st['volume_cm3']:.1f} cm3) = his carpal label without the distal radius and ulna ends it had swallowed "
                        f"(his radius and ulna labels were cut where the carpal row was thought to start). It supersedes the grouped carpal mesh `{base}` (kept unchanged in the bundle, hidden by default: it contains the radius "
                        f"and ulna ends). ")
            else:
                core = (f"Measured on HIM, re-segmented from his frozen CT (Q212): the {label} ({st['volume_cm3']:.1f} cm3) that his carpal label had swallowed because his {base.split('_')[0]} label was cut "
                        f"where the carpal row was thought to start. It abuts the cut face of his measured {base} (unchanged). ")
            badge = (core + "Separated from the carpals at the radiocarpal / ulnocarpal joint clefts by a marker watershed on his CT HU (relief = -HU, so the clefts are the ridges; markers = his radius, ulna, "
                     "carpal and metacarpal labels; the Z-Anatomy radius fitted to him (Q201 page, 3 mm from his CT epiphysis) is used only as a marker prior inside his old carpal label); every voxel is his CT / his label, "
                     f"no Z-Anatomy geometry. Check: {ph_txt}.")
            rec = {k: ctx.own[base]["e"]["rec"][k] for k in ("latin", "folder", "region", "origin", "insertion") if k in ctx.own[base]["e"]["rec"]}
            rec.update(name=f"{ctx.own[base]['e']['rec'].get('name', base)} ({'re-segmented from his CT: ' + label})", source="His own frozen CT (Visible Human Project male), Q212 re-segmentation; see the badge",
                       procedural_badge=badge)
            v, f = W[f"{key}_v"], W[f"{key}_f"]
            ctx.B.add(nid, "bone", b["side"], WRIST_SUBJECT, rec, v, f)
            rows.append(dict(id=nid, stage="wrist", side=sd, **{k: st[k] for k in ("volume_cm3", "n_vertices", "n_triangles", "photo", "bbox_min", "bbox_max")}))
    for sid, why in (("carpals_r", "grouped carpal mesh containing the distal radius and ulna ends"), ("carpals_l", "grouped carpal mesh containing the distal radius and ulna ends"),
                     ("ulna_r_zfill203s", "Z-Anatomy ulnar head contradicted by his CT (only 36 % of its surface in bone density, vs 96 % of his measured ulna)")):
        i = ctx.B.find(sid)
        assert len(i) == 1, sid
        e = ctx.B.items[i[0]]["e"]
        e["hidden_default"] = True
        rec = dict(e["rec"])
        rec["procedural_badge"] = (rec.get("procedural_badge", "") + f" Hidden by default since Q212 (not edited, kept for provenance): {why}; replaced by the Q212 CT re-segmentation of his wrist.").strip()
        e["rec"] = rec
        rows.append(dict(id=sid, stage="wrist_hidden", why=why))
    return rows


def build_ctx(body):
    ctx = C.Ctx(body, scope="all")
    for suf_file in (f"Q203_seams_{body}.json",):
        p = REPO / "data/derived" / suf_file
        if p.exists():
            ctx.q200cov.update(json.loads(p.read_text()))
    ctx.q203_rows = [x for x in json.loads((REPO / f"data/derived/Q203_rows_{body}.json").read_text()) if x.get("stage") == "muscle"]
    return ctx


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, choices=["vhm", "vhf"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out", default=None)
    ap.add_argument("--rows", default=None)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    t = time.time()
    ctx = build_ctx(a.body)
    print("ctx", round(time.time() - t, 1), flush=True)
    stage_muscles(ctx, only=a.only)
    print("muscles done", round(time.time() - t, 1), flush=True)
    if not a.only:
        C.stage_separate(ctx)
    for r in ctx.rows:
        print({k: v for k, v in r.items() if k not in ("align", "constraints", "pull")})
    if a.rows:
        Path(a.rows).write_text(json.dumps(ctx.rows, indent=1, default=str))
    if not a.dry:
        C.assemble(ctx)
        if a.body == "vhm":
            ctx.rows += add_wrist(ctx)
            if a.rows:
                Path(a.rows).write_text(json.dumps(ctx.rows, indent=1, default=str))
        out = Path(a.out) if a.out else ctx.cfg["out"]
        print("bundle bytes", write_bundle(ctx, out))
        seams = {nid: [dict(axis=r["axis"], pos=r["pos"], polys=r["covered"]) for r in pc["pieces"] if "covered" in r and "axis" in r] for nid, pc in ctx.pieces.items() if "pieces" in pc}
        (REPO / f"data/derived/Q212_seams_{a.body}.json").write_text(json.dumps(seams))
    print("done", round(time.time() - t, 1))
