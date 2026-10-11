#!/usr/bin/env python3
"""Q214: close the muscles that the OWN pages still lack -- splenius capitis, splenius cervicis (both sides), fibularis (peroneus) brevis (both sides), flexor pollicis brevis right.

    python3 scripts/transfer/q214_fill.py --body vhm|vhf [--dry] [--only splenius_capitis,...] [--out DIR] [--report FILE]

Input = the Q212 male bundle (build/viewer_m_hr_q212) / the Q213 female bundle (build/viewer_f_hr_q213); output = a NEW bundle (build/viewer_?_hr_q214).  EVERY existing entry stays byte for byte (the
bundle only gains entries).  Per muscle and side:
  0. ABSENCE is verified first (no entry with the id on the bundle; the Z-Anatomy counterpart exists on the Z page fitted to this body).
  1. OWN EVIDENCE first (female splenius only): the splenius compartment of her cryosection frame (q214_splenius_own.py) is checked against the same guards as a transferred muscle
     (volume / length within bounds of the Z counterparts fitted to her, attachments on her bones, inside the skin, out of bone, <= 35 % inside other muscles) and the numbers are recorded.  It does NOT pass
     (1.35-1.59 x the Z volume, cut flat at the T1 body top), so it is not shipped; there is no code path that ships a compartment that failed.
  2. TRANSFER-FIT of the Z-Anatomy muscle taken from the Z page fitted to this body (per-bone chain fits onto the person's own skeleton, Q168 - Q211), `q214_fit.inner_fit`: attachments pulled onto the
     person's own bone landmarks, out of his / her bones and neighbouring muscles, guards on skin / bone / overlap / volume / length / folds.  A muscle that cannot pass is NOT added; the reasons are recorded
     (data/derived/Q214_<body>_report.json).
Badge on the card: class Filled from Z-Anatomy (subject xfer_zan2<body>_q214), the volume, the fit error and every guard number."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import trimesh

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q214_fit as F  # noqa: E402
from scripts.transfer import q214_targets as T  # noqa: E402
from scripts.transfer import q213_inbone as IB  # noqa: E402
import motor_points_q187 as MP  # noqa: E402

OWN_SUBJECT = {"vhf": "ct_vhf_dneck_splenius_q214"}
ATTRIBUTION = ("Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D): muscles this page lacked (splenius capitis / cervicis, fibularis brevis, flexor pollicis brevis), taken from the Z-Anatomy page fitted to "
               "this body and refitted to its own bones inside guards (Q214); the measured structures are not edited. Z-Anatomy: models by the Z-Anatomy project, app by Lluis Vinent Juanico -- see "
               "third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. Licensed CC BY-SA 4.0; this derivative remains CC BY-SA 4.0 (ShareAlike).")


def load_z(cfg):
    MP.VIEWERS["_q214z"] = {"kind": "zan", "html": cfg["z_page"], "label": "z"}
    return MP.load_viewer("_q214z")


def z_manifest_ids(html):
    h = Path(html).read_text(encoding="utf-8")
    i = h.find("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    return [m["id"] for m in json.JSONDecoder().raw_decode(h[i:])[0]["meshes"]]


def absence(body):
    """step 0: the ids on the SOURCE bundle (manifest: bundle.json structures) that carry any of the wanted stems, and the Z ids on the Z page fitted to this body"""
    cfg = T.BODY[body]
    src_ids = sorted({e["id"] for e in json.loads((cfg["src"] / "bundle.json").read_text())["structures"]})
    zids = set(z_manifest_ids(cfg["z_page"]))
    out = {}
    for stem, sides in T.WANT.items():
        for s in sides:
            nid, zid = T.own_id(stem, s), T.z_id(stem, s)
            out[nid] = dict(on_bundle=nid in src_ids, bundle_ids_with_stem=[i for i in src_ids if i.startswith(stem)], z_id=zid, z_present=zid in zids)
    return out


def atlas_rec(nid):
    from scripts import export_viewer_bundle as X
    recs = X.load_atlas_records()
    folder, r = recs[nid]
    return X.summarise(folder, r)


def vol_cm3(v, f):
    return abs(trimesh.Trimesh(v, f, process=False).volume) / 1000.0


def pron_word(cfg):
    return "his" if cfg["pron"] == "his" else "her"


def badge_zfill(cfg, stem, s, rep, name):
    g = rep["guards"]
    pr, Pr = cfg["pron"], cfg["Pron"]
    o_txt, i_txt = (t.replace("the person's", pron_word(cfg)) for t in T.LANDMARK_TEXT[stem])
    z0 = rep["end_dist_z_mm"]
    ends = g["end_dist_mm"]
    sep = rep.get("separation", {})
    err_med = round(float(np.median([a["dist_before_p5"] for a in rep["attach_pull"]])), 1)
    err_max = round(float(max(a["dist_before_p5"] for a in rep["attach_pull"])), 1)
    v = rep["variant"]
    lm = rep.get("landmarks", {})
    note = f" ({lm['mastoid_landmark_note']})" if lm.get("mastoid_landmark_note") else ""
    rise = [x for x in g["neighbour_overlap_rise"] if x[2] - x[1] >= 1.0][:3]
    rise_txt = ("It raises the overlap of its neighbours (share of their volume inside other muscles, Q204 audit measure): " + "; ".join(f"{x[0].replace('_', ' ')} {x[1]} -> {x[2]} %" for x in rise) + ". ") if rise else ""
    hc = rep.get("her_cryo_compartment")
    cross = (f"Cross-check with her own cryosection splenius compartment (capitis + cervicis in one sheet, 65-76 cm3, cut flat at the T1 body top; not used as the mesh because it fails the volume / length / attachment "
             f"guards): of this muscle's vertices above the compartment's lower cut ({hc['vertices_compared']} of them) {hc['vertices_inside_pct']} % lie inside it, median distance to it {hc['median_distance_mm']} mm "
             f"(her compartment lies more superficially: it is a rule-based layer under the trapezius). ") if hc else ""
    return (f"Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) counterpart of {name}, which {pr} page did not carry (no measured or transferred mesh; Z-fill, Q214): the Z-Anatomy structure "
            f"fitted to {pr} body (per-bone chain fits onto {pr} own skeleton, Q168-Q211), refitted in Q214 inside guards -- origin zone pulled onto {o_txt} and insertion zone onto {i_txt} "
            f"(contact distance origin / insertion {z0[0]} / {z0[1]} mm before, {ends[0]} / {ends[1]} mm after{note}), pushed out of {pr} own bone meshes (belly {g['belly_in_bone_pct']} % inside bone after; "
            f"all vertices {g['in_bone_pct']} %, deepest {g['bone_depth_max_mm']} mm), separated from the neighbouring muscle meshes it sat in (share of its volume inside other muscles, measured the way the Q204 audit "
            f"does: {g['overlap_vol_z_fit_pct']} % for the fitted Z muscle, {g['overlap_vol_pct']} % now; gate {F.OVERLAP_MAX:g} %{', above the audit severity-1 line of ' + format(F.OVERLAP_NOTE_MAX, 'g') + ' %' if g['overlap_vol_pct'] > F.OVERLAP_NOTE_MAX else ''}), "
            f"held inside {pr} skin (closest {g['min_skin_depth_mm']} mm below the surface). "
            f"Volume {g['volume_cm3']} cm3 (fitted Z muscle {rep['volume_z_cm3']} cm3, x{g['volume_ratio']}); length {g['length_mm']} mm (fitted Z muscle {rep['length_z_mm']} mm, x{g['length_ratio']}); "
            f"mean / max move {g['mean_move_mm']} / {g['max_move_mm']} mm; flipped faces {g['flipped_pct']} %. "
            f"Q214 validation median error {err_med} mm, max {err_max} mm (end zones of the fitted Z muscle vs {pr} own origin / insertion bone, before the pull). "
            f"{rise_txt}{cross}Not measured on {'him' if pr == 'his' else 'her'}. A position estimate of the usual muscle, not a segmentation.")


def own_splenius_check(ctx, lm, s, v, f, zref):
    """guards for the cryosection compartment of HER splenius used as splenius_capitis_<s>: same numbers as a transferred muscle (volume / length vs the Z counterparts fitted to her, ends on her bones, skin, bone, overlap)"""
    g, why = {}, []
    ins, _, dist = ctx.bone_field.inside(v)
    g["in_bone_pct"] = round(100.0 * float(ins.mean()), 1)
    g["overlap_pct"] = round(ctx.muscle_overlap.pct(v), 1)
    g["inside_skin_pct"], g["min_skin_depth_mm"] = [round(x, 2) for x in ctx.skin_state(v)]
    vol = vol_cm3(v, f)
    zcap, zcer = zref
    zv = vol_cm3(zcap["v"], zcap["f"]) + vol_cm3(zcer["v"], zcer["f"])
    g["volume_cm3"], g["z_pair_volume_cm3"], g["volume_ratio"] = round(vol, 1), round(zv, 1), round(vol / zv, 2)
    u, t, zlo, zhi = F.axis_and_zones(v)
    A, Bt, _ = T.targets(ctx, lm, "splenius_capitis", s)
    za, zb = F.assign_targets(v, zlo, zhi, A, Bt)
    g["end_dist_mm"] = [round(F.zone_dist(v, za, A), 1), round(F.zone_dist(v, zb, Bt), 1)]
    L = F.length_mm(v, zlo, zhi)
    zu, zt, zzlo, zzhi = F.axis_and_zones(np.asarray(zcap["v"], float))
    Lz = F.length_mm(np.asarray(zcap["v"], float), zzlo, zzhi)
    g["length_mm"], g["z_capitis_length_mm"], g["length_ratio"] = round(L, 1), round(Lz, 1), round(L / Lz, 2)
    if g["in_bone_pct"] > F.BELLY_IN_BONE_MAX:
        why.append(f"{g['in_bone_pct']} % inside bone")
    if g["overlap_pct"] > F.OVERLAP_MAX:
        why.append(f"{g['overlap_pct']} % inside other muscles")
    if g["inside_skin_pct"] < 100.0 or g["min_skin_depth_mm"] < F.SKIN_DEPTH_MIN_MM:
        why.append("skin")
    if not (F.VOL_LO <= g["volume_ratio"] <= F.VOL_HI):
        why.append(f"volume {g['volume_cm3']} cm3 is x{g['volume_ratio']} of the two Z-Anatomy splenius muscles fitted to her ({g['z_pair_volume_cm3']} cm3; gate {F.VOL_LO}-{F.VOL_HI})")
    if not (F.LEN_LO <= g["length_ratio"] <= F.LEN_HI):
        why.append(f"length {g['length_mm']} mm is x{g['length_ratio']} of the Z capitis fitted to her ({g['z_capitis_length_mm']} mm; gate {F.LEN_LO}-{F.LEN_HI}): the compartment is cut flat at the T1 body top")
    if max(g["end_dist_mm"]) > F.END_DIST_MAX_MM:
        why.append(f"an end lies {max(g['end_dist_mm'])} mm from the bone named as origin / insertion (gate {F.END_DIST_MAX_MM:g}): the lower end is the flat cut at the T1 body top, not her spinous processes")
    return g, why


def run(body, out=None, report=None, dry=False, only=None, log=print):
    cfg = T.BODY[body]
    out = Path(out or cfg["out"])
    report = Path(report or REPO / f"data/derived/Q214_{body}_report.json")
    B = Bundle(cfg["src"])
    n0 = len(B.items)
    ctx = F.Context(B)
    lm = T.body_for_landmarks(B, body)
    Z = load_z(cfg)
    rep = dict(body=body, source_bundle=str(cfg["src"].relative_to(REPO)), z_page=str(cfg["z_page"].relative_to(REPO)), absence={}, added={}, skipped={}, own_evidence={},
               params=dict(ATTACH_CAP_MM=F.ATTACH_CAP_MM, END_DIST_MAX_MM=F.END_DIST_MAX_MM, BELLY_IN_BONE_MAX=F.BELLY_IN_BONE_MAX, ALL_IN_BONE_MAX=F.ALL_IN_BONE_MAX, OVERLAP_MAX=F.OVERLAP_MAX,
                           VOL=[F.VOL_LO, F.VOL_HI], LEN=[F.LEN_LO, F.LEN_HI], SKIN_DEPTH_MIN_MM=F.SKIN_DEPTH_MIN_MM, MEAN_MOVE_MAX=F.MEAN_MOVE_MAX, MAX_MOVE_MAX=F.MAX_MOVE_MAX))
    absence_rec = absence(body)
    own_npz = None
    if body == "vhf":
        p = REPO / "build/q214/splenius_own.npz"
        if p.exists():
            own_npz = np.load(p)
    added_any, own_added = False, False
    for stem, sides in T.WANT.items():
        if only and stem not in only:
            continue
        for s in sides:
            nid, zid = T.own_id(stem, s), T.z_id(stem, s)
            rep["absence"][nid] = absence_rec[nid]
            if B.find(nid):
                rep["skipped"][nid] = "already on the page"
                continue
            if zid not in Z:
                rep["skipped"][nid] = f"no Z-Anatomy counterpart {zid} on the Z page"
                continue
            name = atlas_rec(nid)["name"]
            t0 = time.time()
            # ---------------- 1. own evidence (her splenius capitis)
            if own_npz is not None and stem == "splenius_capitis":
                ov, of = own_npz[f"splenius_capitis_{s}_v"], own_npz[f"splenius_capitis_{s}_f"]
                g, why = own_splenius_check(ctx, lm, s, ov, of, (Z[zid], Z[T.z_id("splenius_cervicis", s)]))
                rep["own_evidence"][nid] = dict(source="her splenius compartment, cryosection frame (labels 1 / 11 of vhf_deep_neck_cryo.nii.gz)", guards=g, why_not=why, accepted=not why)
                log(f"  {nid}: own cryo compartment {g} -> {'OK' if not why else 'refused: ' + '; '.join(why)}")
            elif stem == "splenius_cervicis" and body == "vhf":
                rep["own_evidence"][nid] = dict(source="no separate label: splenius capitis + cervicis are ONE sheet in her photographs (Q62 not_shipped)", accepted=False)
            # ---------------- 2. transfer-fit
            v0, f0 = np.asarray(Z[zid]["v"], float), np.asarray(Z[zid]["f"], np.int64)
            A, Bt, info = T.targets(ctx, lm, stem, s)
            v, r = F.inner_fit(v0, f0, ctx, A, Bt, skip_ids=(nid,), log=lambda *a: None)
            r["landmarks"] = info
            r["seconds"] = round(time.time() - t0, 1)
            if v is None:
                rep["skipped"][nid] = dict(why_not=r["why_not"], fit=r)
                log(f"  {nid}: NOT added -- {'; '.join(r['why_not'])}")
                continue
            r["neighbours_pct"] = F.neighbour_table(v, ctx, skip_ids=(nid,))
            if own_npz is not None and stem.startswith("splenius"):
                cm = trimesh.Trimesh(own_npz[f"splenius_capitis_{s}_v"], own_npz[f"splenius_capitis_{s}_f"], process=False)
                above = v[v[:, 1] >= cm.bounds[0][1]]                                   # only the part of the muscle that her compartment can speak for (it is cut at the T1 body top)
                dd = trimesh.proximity.closest_point(cm, above)[1]
                r["her_cryo_compartment"] = dict(vertices_compared=int(len(above)), vertices_inside_pct=round(100.0 * float(cm.contains(above).mean()), 1), median_distance_mm=round(float(np.median(dd)), 1),
                                                 note="her cryosection splenius compartment (capitis + cervicis, one sheet; refused as the mesh, see own_evidence) as a cross-check of the position; vertices above its lower cut only")
            r["badge"] = badge_zfill(cfg, stem, s, r, name)
            rec = atlas_rec(nid)
            rec["source"] = "Z-Anatomy (CC BY-SA 4.0), fitted to this body; see the badge"
            rec["procedural_badge"] = r["badge"]
            side = "right" if s == "r" else "left"
            if not dry:
                B.add(nid, "muscle", side, cfg["subject"], rec, v, f0)
                ctx.add_muscle(nid, v, f0)
            rep["added"][nid] = r
            added_any = True
            log(f"  {nid}: ADDED vol {r['guards']['volume_cm3']} cm3 overlap {r['guards']['overlap_pct']} % ends {r['guards']['end_dist_mm']} [{r['seconds']} s]")
    if not dry and added_any:
        att = {cfg["subject"]: ATTRIBUTION}
        n = B.write(out, new_subject_attribution=att)
        log(f"wrote {out}: {n} bytes, {len(B.items)} entries (was {n0})")
    report.write_text(json.dumps(rep, indent=1, default=str) + "\n")
    log(f"added {len(rep['added'])}, skipped {len(rep['skipped'])}")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, choices=["vhm", "vhf"])
    ap.add_argument("--out"); ap.add_argument("--report"); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--absence-only", action="store_true", help="write data/derived/Q214_absence.json (step 0 for both bodies) and stop")
    a = ap.parse_args()
    if a.absence_only:
        (REPO / "data/derived/Q214_absence.json").write_text(json.dumps({b: absence(b) for b in ("vhm", "vhf")}, indent=1) + "\n")
        print("wrote data/derived/Q214_absence.json")
        return
    run(a.body, a.out, a.report, a.dry, [x for x in a.only.split(",") if x] or None)


if __name__ == "__main__":
    main()
