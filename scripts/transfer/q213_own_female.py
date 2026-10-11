#!/usr/bin/env python3
"""Q213: the TARGET MUSCLES (the muscles that carry motor points) of the OWN female bundle, corrected where her own evidence supports it.

    python3 scripts/transfer/q213_own_female.py [--dry] [--src build/viewer_f_hr_q212] [--out build/viewer_f_hr_q213] [--report data/derived/Q213_own_female_report.json]

Input = the Q212 bundle; output = a NEW bundle.  Every entry that is not listed in the report stays byte for byte.
  (1) IN-BONE REPAIR.  A target muscle (or one of its Z-fill continuation pieces) with more than IN_BONE_MIN % of its vertices inside HER OWN bone meshes (the evidence) is
      pushed out of them by `q213_inbone.repair` (guarded displacement: origin / insertion zones and the seam to its sibling piece held; move, volume, folds and stretch
      bounded; kept only if it passes).  A muscle the Q185 carve had HIDDEN by default because of this overlap is shown again when the belly ends up <= 5 % in bone.
  (2) MISSING TARGET MUSCLES.  Target muscles that her page does not carry at all (her left hand has no intrinsic muscle, no thenar muscle on either side, no right
      palmaris longus) are added as badged Z-Anatomy counterparts taken from the Z page fitted to her body (same frame, per-bone fits), pushed out of her bones by the same
      repair, and kept only if <= IN_BONE_MAX_ADD % is left in her bones and <= OVERLAP_MAX_ADD % lies inside her other muscles.  What fails is listed (not added).
Nothing is invented: moved meshes are her own muscles' vertices, added meshes are the Z structures fitted to her; both carry badges with the numbers."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q213_inbone as IB  # noqa: E402
import motor_points_q187 as MP  # noqa: E402

IN_BONE_MIN = 8.0          # % of vertices inside her bones that makes a target muscle a repair candidate
IN_BONE_MAX_ADD = 5.0      # an added Z muscle must leave <= this share (belly) in her bones
OVERLAP_MAX_ADD = 35.0     # ... and <= this share of its vertices inside her other muscles
SUBJECT = "xfer_zan2vhf_hand_q213"
Z_PAGE = REPO / "build/q211/viewer_zan_female/atlas_viewer_zan_female.html"
# Z structures her page lacks that carry a motor-point rule (id on the Z page -> id on her page); opponens digiti minimi: the hand island only
ADD = {
    "abductor_pollicis_brevis_l": None, "flexor_pollicis_brevis_l": None, "adductor_pollicis_l": None, "abductor_digiti_minimi_hand_l": None,
    "flexor_digiti_minimi_brevis_hand_l": None, "opponens_digiti_minimi_l": None,
    "abductor_pollicis_brevis_r": None, "flexor_pollicis_brevis_r": None, "zan_palmaris_longus_muscle_r": None,
    "flexor_hallucis_brevis_r": None,
}
HELD_BY_RULE = {   # missing on her page, Z counterpart exists but is NOT added (reason in the report)
    "fibularis_brevis_r": "lies 71 % inside her (male-carried) lateral-compartment muscles: adding it would stack it on fibularis longus / soleus",
    "fibularis_brevis_l": "lies 71 % inside her (male-carried) lateral-compartment muscles: adding it would stack it on fibularis longus / soleus",
    "splenius_capitis_r": "lies 38-42 % inside her trapezius / semispinalis meshes (her CT labels cannot separate the splenius; Q185 noted 'splenius not shipped')",
    "splenius_capitis_l": "lies 38-42 % inside her trapezius / semispinalis meshes (her CT labels cannot separate the splenius; Q185 noted 'splenius not shipped')",
    "zan_splenius_colli_muscle_r": "lies 52-57 % inside her trapezius / semispinalis / levator meshes",
    "zan_splenius_colli_muscle_l": "lies 52-57 % inside her trapezius / semispinalis / levator meshes",
}


def target_stems():
    return sorted({r["muscle"] for r in MP.RULES} | set(MP.NOT_COVERED_REASON))


def load_z_meshes():
    MP.VIEWERS["_q213z"] = {"kind": "zan", "html": Z_PAGE, "label": "z"}
    return MP.load_viewer("_q213z")


def badge_repair(rep, who="her"):
    belly = (f" (belly {rep['inside_before_belly_pct']} -> {rep['inside_after_belly_pct']} %)" if "inside_before_belly_pct" in rep else "")
    return (f" Q213 (target-muscle audit): {rep['inside_before_pct']} % of this mesh's vertices lay inside {who} own bone meshes{belly}; pushed out of them by a guarded displacement field "
            f"(origin / insertion zones and the seam to the Z-fill continuation held; mean move {rep['mean_move_mm']} mm, max {rep['max_move_mm']} mm; volume x{rep['volume_ratio']}; "
            f"flipped faces {rep['flipped_pct']} %, stretched triangles {rep['stretched_before']} -> {rep['stretched_after']} %). In bone after: {rep['inside_after_pct']} % "
            f"(belly {rep.get('inside_after_belly_pct', rep['inside_after_pct'])} %). Her bones are the evidence; nothing was added or invented.")


def run(src, out, report, dry=False, log=print):
    B = Bundle(src)
    bones = {}
    for it in B.items:
        if it["e"]["cat"] == "bone":
            v, f = B.mesh(it)
            bones.setdefault(it["e"]["id"], (v, f))
    field = IB.BoneField(bones)
    tree = cKDTree(np.vstack([v for v, _ in bones.values()]))
    stems = target_stems()
    pat = re.compile(r"^(?:%s)_(r|l)(_zfill\w*)?$" % "|".join(map(re.escape, stems)))
    pat2 = re.compile(r"^zan_palmaris_longus_muscle_(r|l)$")
    rep_all = {"repaired": {}, "held": {}, "unhidden": [], "added": {}, "not_added": {}, "params": dict(IN_BONE_MIN=IN_BONE_MIN, MEAN_MOVE_MAX=IB.MEAN_MOVE_MAX, MAX_MOVE_MAX=IB.MAX_MOVE_MAX, GATE_PCT=IB.GATE_PCT,
                                                                                                  VOL=[IB.VOL_LO, IB.VOL_HI], IN_BONE_MAX_ADD=IN_BONE_MAX_ADD, OVERLAP_MAX_ADD=OVERLAP_MAX_ADD)}
    # ---------------------------------------------------------------- (1) in-bone repair
    cand = [(k, it) for k, it in enumerate(B.items) if it["e"]["cat"] == "muscle" and (pat.match(it["e"]["id"]) or pat2.match(it["e"]["id"]))]
    log(f"target-muscle entries: {len(cand)}")
    by_base = {}
    for k, it in cand:
        base = re.sub(r"_zfill\w*$", "", it["e"]["id"])
        by_base.setdefault(base, []).append(k)
    for k, it in cand:
        e = it["e"]
        v, f = B.mesh(it)
        ins, _, _ = field.inside(v)
        pct = 100.0 * float(ins.mean())
        if pct < IN_BONE_MIN:
            continue
        sib = [j for j in by_base[re.sub(r"_zfill\w*$", "", e["id"])] if j != k]
        anchors = None
        if sib:
            sv = np.vstack([B.mesh(B.items[j])[0] for j in sib])
            anchors = cKDTree(sv).query(v)[0] < 3.0
        t = time.time()
        nv, rep = IB.repair(v, f, field, anchors=anchors, end_tree=tree)
        rep["pieces_seam_vertices"] = int(anchors.sum()) if anchors is not None else 0
        hidden = bool(e.get("hidden_default"))
        if nv is not None:
            rep["was_hidden_default"] = hidden
            rep_all["repaired"][e["id"]] = rep
            note = badge_repair(rep)
            show = hidden and rep.get("inside_after_belly_pct", rep["inside_after_pct"]) <= IB.GATE_PCT
            if show:
                note += " It had been hidden by default since Q185 (the bounded carve could not clear the overlap); it is shown by default again."
                rep_all["unhidden"].append(e["id"])
            if not dry:
                B._set(it, nv, f)   # this item only (an id may have several pieces)
                it["e"]["rec"] = {**it["e"]["rec"], "procedural_badge": ((e["rec"].get("procedural_badge") or "") + note).strip()}
                if show:
                    it["e"].pop("hidden_default", None)
        else:
            rep["was_hidden_default"] = hidden
            rep_all["held"][e["id"]] = rep
        log(f"  {e['id']:44s} {pct:5.1f} % -> {rep['inside_after_pct']:5.1f} % belly {rep.get('inside_before_belly_pct')}->{rep.get('inside_after_belly_pct')} "
            f"mv {rep['mean_move_mm']}/{rep['max_move_mm']} vol {rep['volume_ratio']} {'REPAIRED' if nv is not None else 'HELD ' + ';'.join(rep['why_not'])} [{time.time() - t:.0f}s]")
    # ---------------------------------------------------------------- (2) missing target muscles
    h = Z_PAGE.read_text(encoding="utf-8")
    i0 = h.find("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    zman = {m["id"]: m for m in json.JSONDecoder().raw_decode(h[i0:])[0]["meshes"]}
    zmesh = load_z_meshes()
    own_muscles = {it["e"]["id"]: B.mesh(it) for it in B.items if it["e"]["cat"] == "muscle"}
    own_tm = {k: trimesh.Trimesh(v, f, process=False) for k, (v, f) in own_muscles.items()}
    for zid in ADD:
        nid = zid
        if B.find(nid):
            rep_all["not_added"][nid] = "already on her page"
            continue
        v, f = zmesh[zid]["v"], zmesh[zid]["f"]
        if zid.startswith("opponens_digiti_minimi"):
            ref = zmesh[zid.replace("opponens_digiti_minimi", "abductor_digiti_minimi_hand")]["v"].mean(axis=0)
            v, f = MP.component_near(v, f, ref)
        v = np.asarray(v, float)
        nv, rep = IB.repair(v, f, field, end_tree=tree)
        use = nv if nv is not None else v
        rep.setdefault("inside_after_belly_pct", rep["inside_after_pct"])
        ins, _, _ = field.inside(use)
        inm = np.zeros(len(use), bool)
        for k, tm in own_tm.items():
            lo, hi = tm.bounds[0] - 1, tm.bounds[1] + 1
            sel = np.flatnonzero(np.all((use >= lo) & (use <= hi), axis=1) & ~inm)
            if len(sel):
                inm[sel] = tm.contains(use[sel])
        rep["inside_own_muscles_pct"] = round(100.0 * float(inm.mean()), 1)
        rep["inside_bone_final_pct"] = round(100.0 * float(ins.mean()), 1)
        ok = rep["inside_after_belly_pct"] <= IN_BONE_MAX_ADD and rep["inside_own_muscles_pct"] <= OVERLAP_MAX_ADD
        rep["accepted_for_add"] = bool(ok)
        log(f"  ADD? {zid:40s} in bone {rep['inside_before_pct']} -> {rep['inside_after_pct']} % (belly {rep['inside_after_belly_pct']}), in her muscles {rep['inside_own_muscles_pct']} % -> {'ADD' if ok else 'not added'}")
        if not ok:
            rep_all["not_added"][nid] = rep
            continue
        zr = dict(zman[zid].get("rec") or {})
        side = "left" if zid.endswith("_l") else "right"
        rec = {k: zr[k] for k in ("name", "latin", "folder", "region", "source", "origin", "insertion", "nerve", "compartments", "notes", "part_of_id", "part_of") if k in zr}
        rec["source"] = "Z-Anatomy (CC BY-SA 4.0), fitted to this body; see the badge"
        mv = np.linalg.norm(use - v, axis=1)
        rec["procedural_badge"] = (
            f"Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) counterpart of {rec.get('name', zid)}, which her page did not carry (no measured or transferred mesh): taken from the Z-Anatomy page fitted to her body "
            f"(per-bone fits onto her own skeleton, Q168-Q211; the left hand on her left-hand cryosection photographs, Q192) and added in Q213 as the target of the motor-point rules of this muscle. Not measured on her. "
            f"Her left forearm / hand bones are the Z fit placed on her photographs, her page's bones differ from the fitted ones by a few mm: the mesh was pushed out of her page's bone meshes "
            f"({rep['inside_before_pct']} % -> {rep['inside_after_pct']} % of its vertices inside, mean move {float(mv.mean()):.1f} mm, max {float(mv.max()):.1f} mm; guarded displacement) and lies {rep['inside_own_muscles_pct']} % inside "
            f"her other muscle meshes (gate <= {OVERLAP_MAX_ADD:g} %). A position estimate of the usual muscle, not a segmentation.")
        if not dry:
            B.add(nid, "muscle", side, SUBJECT, rec, use, f)
        rep_all["added"][nid] = rep
    for zid, why in HELD_BY_RULE.items():
        rep_all["not_added"].setdefault(zid, why)
    if not dry:
        att = {SUBJECT: ("Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D): hand / palmar target muscles her page lacked, taken from the Z-Anatomy page fitted to her body and pushed out of her bones (Q213); "
                         "the measured structures are not edited. Z-Anatomy: models by the Z-Anatomy project, app by Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and "
                         "third_party/z-anatomy/README.md. Licensed CC BY-SA 4.0; this derivative remains CC BY-SA 4.0 (ShareAlike).")} if rep_all["added"] else {}
        n = B.write(out, new_subject_attribution=att)
        log(f"wrote {out}: {n} bytes")
    Path(report).write_text(json.dumps(rep_all, indent=1, default=str) + "\n")
    log(f"repaired {len(rep_all['repaired'])}, held {len(rep_all['held'])}, unhidden {len(rep_all['unhidden'])}, added {len(rep_all['added'])}, not added {len(rep_all['not_added'])}")
    return rep_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(REPO / "build/viewer_f_hr_q212"))
    ap.add_argument("--out", default=str(REPO / "build/viewer_f_hr_q213"))
    ap.add_argument("--report", default=str(REPO / "data/derived/Q213_own_female_report.json"))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    run(a.src, a.out, a.report, a.dry)


if __name__ == "__main__":
    main()
