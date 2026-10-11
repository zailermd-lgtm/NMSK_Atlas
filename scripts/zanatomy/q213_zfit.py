#!/usr/bin/env python3
"""Q213: the TARGET MUSCLES (the muscles that carry motor points) of the Z-Anatomy page FITTED TO HER, corrected where her evidence supports it (in-process patch of the published
Q211 page, no Z build; every mesh not listed stays byte for byte).

    python3 scripts/zanatomy/q213_zfit.py [--dry] [--src build/q211/viewer_zan_female] [--out build/q213/viewer_zan_female]

  (1) IN-BONE REPAIR: a target muscle with more than IN_BONE_MIN % of its vertices inside the page's displayed bones (the Z bones are fitted to HER bones, Q168-Q211: the evidence)
      is pushed out of them by `scripts/transfer/q213_inbone.repair` (guarded displacement, origin / insertion zones held, move / volume / folds / stretch bounded, kept only if it passes).
      These are mostly the Z SOURCE's own overlaps (the Q211 in-bone pass skipped structures the unfitted Z base also has); here they are target muscles, so they are repaired.
  (2) MIS-NAMED / MERGED ID: Z-Anatomy's `opponens_digiti_minimi_<side>` is ONE mesh made of the hand muscle and a 120-vertex piece in the FOOT (952 mm apart): the two connected
      components are separated -- the hand component keeps the id, the foot component becomes `opponens_digiti_minimi_foot_<side>` (nothing deleted, nothing moved)."""
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
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer import q213_inbone as IB  # noqa: E402
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
import motor_points_q187 as MP  # noqa: E402

STEM = "atlas_viewer_zan_female"
IN_BONE_MIN = 8.0
Z_PARTS = {"deltoid": "zan_{x}_part_of_deltoid_muscle", "triceps_brachii": "zan_{x}_head_of_triceps_brachii", "pectoralis_major": "zan_{x}_of_pectoralis_major_muscle",
           "iliopsoas": ("zan_psoas_major", "zan_iliacus_muscle"), "palmaris_longus": ("zan_palmaris_longus_muscle",), "tibialis_posterior": ("zan_tibialis_posterior_muscle",),
           "splenius_cervicis": ("zan_splenius_colli_muscle",)}


def target_ids(ids):
    stems = sorted({r["muscle"] for r in MP.RULES} | set(MP.NOT_COVERED_REASON))
    pat = re.compile(r"^(?:%s)_(r|l)$" % "|".join(map(re.escape, stems)))
    extra = re.compile(r"^zan_(clavicular|acromial|scapular_spinal)_part_of_deltoid_muscle_(r|l)$|^zan_(long|medial|lateral)_head_of_triceps_brachii_(r|l)$|"
                       r"^zan_(clavicular_head|sternocostal_head|abdominal_part)_of_pectoralis_major_muscle_(r|l)$|^zan_(psoas_major|iliacus_muscle|palmaris_longus_muscle|tibialis_posterior_muscle|splenius_colli_muscle)_(r|l)$")
    return [i for i in ids if pat.match(i) or extra.match(i)]


def components(v, f):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(v)
    a = np.concatenate([f[:, 0], f[:, 1], f[:, 2]]); b = np.concatenate([f[:, 1], f[:, 2], f[:, 0]])
    return connected_components(coo_matrix((np.ones(len(a)), (a, b)), shape=(n, n)), directed=False)


def split(v, f, lab, i):
    keep = lab[f[:, 0]] == i
    idx = np.flatnonzero(lab == i)
    remap = -np.ones(len(v), np.int64)
    remap[idx] = np.arange(len(idx))
    return v[idx], remap[f[keep]]


def run(src, out, report, dry=False, log=print):
    src, out = Path(src), Path(out)
    man, blob = P5.load_page(src, STEM)
    S = P5.decode(man, blob)
    bones = {i: (e["v"], e["f"]) for i, e in S.items() if e["m"]["sys"] == "bone" and len(e["f"]) > 20}
    field = IB.BoneField(bones)
    tree = cKDTree(np.vstack([v for v, _ in bones.values()]))
    rep_all = {"repaired": {}, "held": {}, "split": {}, "params": dict(IN_BONE_MIN=IN_BONE_MIN, MEAN_MOVE_MAX=IB.MEAN_MOVE_MAX, MAX_MOVE_MAX=IB.MAX_MOVE_MAX, GATE_PCT=IB.GATE_PCT, VOL=[IB.VOL_LO, IB.VOL_HI])}
    replace, add = {}, []
    # ---------------------------------------------------------------- (2) merged opponens digiti minimi
    for s in ("r", "l"):
        i = f"opponens_digiti_minimi_{s}"
        e = S[i]
        k, lab = components(e["v"], e["f"])
        cs = [(int((lab == c).sum()), e["v"][lab == c].mean(0)) for c in range(k)]
        if k != 2:
            continue
        ys = [c[1][1] for c in cs]
        hand_c, foot_c = (0, 1) if ys[0] > ys[1] else (1, 0)
        hv, hf = split(e["v"], e["f"], lab, hand_c)
        fv, ff = split(e["v"], e["f"], lab, foot_c)
        rec = dict(e["m"].get("rec") or {})
        rec_h = dict(rec)
        rec_h["procedural_badge"] = ((rec.get("procedural_badge") or "") + (
            " Q213: the Z-Anatomy source mesh of this id was ONE mesh made of the hand muscle and a 120-vertex piece in the FOOT (the two parts lie "
            f"{abs(ys[0] - ys[1]):.0f} mm apart); the foot piece is now its own structure `opponens_digiti_minimi_foot_{s}`. Hand geometry unchanged.")).strip()
        rec_f = {k2: v2 for k2, v2 in rec.items() if k2 in ("source", "folder", "region", "latin")}
        rec_f.update(name="Opponens digiti minimi (foot)", origin="foot (Z-Anatomy source piece; the origin is not stated by the source)", insertion="foot (Z-Anatomy source piece)",
                     procedural_badge=("Q213: separated from the Z-Anatomy mesh `opponens_digiti_minimi_%s`, which merged this FOOT piece with the hand muscle (952 mm apart); geometry unchanged "
                                       "(fitted to her foot by the same per-bone fit). Identity of this small foot muscle follows the Z-Anatomy source; not verified on her." % s))
        replace[i] = (hv, hf, rec_h)
        ent = {"name": "Opponens digiti minimi (foot)", "id": f"opponens_digiti_minimi_foot_{s}", "side": s, "sys": "muscle", "rec": rec_f}
        add.append((ent, fv, ff))
        rep_all["split"][i] = {"hand_vertices": int(len(hv)), "foot_vertices": int(len(fv)), "distance_mm": round(abs(ys[0] - ys[1]), 1)}
        log(f"  split {i}: hand {len(hv)} v + foot {len(fv)} v ({abs(ys[0] - ys[1]):.0f} mm apart)")
    # ---------------------------------------------------------------- (1) in-bone repair
    for i in target_ids(list(S)):
        if S[i]["m"]["sys"] != "muscle":
            continue
        v, f = (replace[i][0], replace[i][1]) if i in replace else (S[i]["v"], S[i]["f"])
        ins, _, _ = field.inside(v)
        pct = 100.0 * float(ins.mean())
        if pct < IN_BONE_MIN:
            continue
        nv, rep = IB.repair(v, f, field, end_tree=tree)
        if nv is None:
            rep_all["held"][i] = rep
            log(f"  {i:44s} {pct:5.1f} % HELD {';'.join(rep['why_not'])}")
            continue
        rep_all["repaired"][i] = rep
        rec = dict((replace[i][2] if i in replace else S[i]["m"].get("rec")) or {})
        rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + (" Q213 (target-muscle audit): this muscle lay inside the displayed bones" + badge_tail(rep))).strip()
        replace[i] = (nv, f, rec)
        log(f"  {i:44s} {pct:5.1f} % -> {rep['inside_after_pct']:5.1f} % belly {rep.get('inside_before_belly_pct')}->{rep.get('inside_after_belly_pct')} mv {rep['mean_move_mm']}/{rep['max_move_mm']} vol {rep['volume_ratio']}")
    if not dry:
        P5.save_page(out, STEM, man, blob, replace=replace, add=add)
        for fcl in src.glob("clinical_*"):
            import shutil
            shutil.copy2(fcl, out / fcl.name)
        r = SD.diff(src, out, STEM, sorted(set(replace)))
        rep_all["ship_diff"] = {k2: (v2 if not isinstance(v2, dict) else {kk: vv for kk, vv in list(v2.items())[:400]}) for k2, v2 in r.items() if k2 in ("added", "removed", "geometry_changed_but_not_listed", "unchanged", "card_only")}
        rep_all["ship_diff"]["geometry_changed"] = len(r["geometry_changed"])
    Path(report).write_text(json.dumps(rep_all, indent=1, default=str) + "\n")
    log(f"repaired {len(rep_all['repaired'])}, held {len(rep_all['held'])}, split {len(rep_all['split'])}")
    return rep_all


def badge_tail(rep):
    belly = (f" (belly {rep['inside_before_belly_pct']} -> {rep['inside_after_belly_pct']} %)" if "inside_before_belly_pct" in rep else "")
    return (f": {rep['inside_before_pct']} % of its vertices were inside them{belly} -- mostly the Z source's own overlap with the bones (the unfitted Z base has it too, so the Q211 in-bone pass skipped it). "
            f"Pushed out of the displayed bones (which are fitted to her own bones) by a guarded displacement field (origin / insertion zones held; mean move {rep['mean_move_mm']} mm, max {rep['max_move_mm']} mm; "
            f"volume x{rep['volume_ratio']}; flipped faces {rep['flipped_pct']} %, stretched triangles {rep['stretched_before']} -> {rep['stretched_after']} %). In bone after: {rep['inside_after_pct']} % "
            f"(belly {rep.get('inside_after_belly_pct', rep['inside_after_pct'])} %). Nothing invented.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(REPO / "build/q211/viewer_zan_female"))
    ap.add_argument("--out", default=str(REPO / "build/q213/viewer_zan_female"))
    ap.add_argument("--report", default=str(REPO / "data/derived/Q213_zfit_report.json"))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    run(a.src, a.out, a.report, a.dry)


if __name__ == "__main__":
    main()
