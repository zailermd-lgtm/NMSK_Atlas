#!/usr/bin/env python3
"""Q250: Base · Female with a WOMAN's skeleton. The Z-Anatomy body (one male body, exactly mirror-symmetric) is deformed onto a female skeleton target and every soft structure is carried with it.

    python3 scripts/zanatomy/q250_base_f.py [--src build/q244/viewer_base_female] [--comb build/q244/viewer_zan_female] [--out build/q250_pre/viewer_base_zonly] [--pelvis her|mean]

Steps (cached in build/q250_work/):
  1. the Z-only page = the source page minus the HRA-derived female structures (they are re-registered on the NEW pelvis afterwards by the unchanged Q233 / Q234 / Q243 patch scripts);
  2. female pelvic ring: her own CT hip bones + HRA sacrum / coccyx (her_pelvis.py) [or the mean of adult women, pelvis_mean.py] -> non-rigid registration of the Z pelvis (pelvis_reg.py);
  3. whole-skeleton target (skel_target.py: shape and proportions from Combined · Female = Z bones fitted to HER skeleton, Z pose, left / right symmetrised);
  4. all other structures carried with the bones (warp.py: bone-anchored thin-plate spline) with guards; 5. page written (untouched = none: every structure moves), cards badged.
The deformation (control points + displacements) is saved so a structure added later (Q248 ligaments) can be carried by exactly the same function: scripts/anatomy/q250/warp_apply.py."""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.anatomy.q250 import lib as L, skel_target as ST, pelvis_reg as PR, warp as W, her_pelvis as HP  # noqa: E402

STEM = "atlas_viewer_base_female"
WORK = REPO / "build" / "q250_work"
MIRROR_FILLS = {"zan_lateral_intermuscular_septum_of_arm_r", "zan_posterior_intermuscular_septum_of_leg_r"}
RING = ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx")


def hra_ids(src, q222="build/q222/viewer_base_female"):
    ids = {m["id"] for m in P5.load_page(REPO / src, STEM)[0]["meshes"]}
    old = {m["id"] for m in P5.load_page(REPO / q222, STEM)[0]["meshes"]}
    return sorted(ids - old - MIRROR_FILLS)


PELVIS_TXT = {
    "her": ("the pelvis of the Visible Human female (her CT hip bones; HRA sacrum / coccyx of the same donor)", "one woman (the Visible Human female), not an average"),
    "mean": ("the MEAN female pelvic shape of 47 adult women (CT, TotalSegmentator dataset v2.0.1, CC BY 4.0, Wasserthal et al. 2023; generalised Procrustes + signed-distance average of hip bones and sacrum) "
             "at the size and position of the Visible Human female's pelvis (her coccyx kept)", "the mean of 47 women"),
}


def badge_text(i, e, st, kind, s_info, ring_rep, pelvis="her"):
    sysn = e["m"]["sys"]
    if sysn == "bone":
        if kind == "nonrigid_ring":
            r = ring_rep.get(i, {})
            return ("Q250 female skeleton: this Z-Anatomy pelvic bone (shape of one male body) is DEFORMED (landmark thin-plate warp + non-rigid coherent point drift) onto "
                    f"{PELVIS_TXT[pelvis][0]}; distance of the deformed bone to that target: median {r.get('median_mm')} mm, p90 {r.get('p90_mm')} mm. "
                    f"Anatomy, vertex order and muscle attachments are those of Z-Anatomy; the shape is a woman's ({PELVIS_TXT[pelvis][1]}).")
        return (f"Q250 female skeleton: this Z-Anatomy bone is placed on the female target skeleton (the Visible Human female's CT skeleton, one woman) by a similarity transform: scale {s_info.get('scale')}, "
                f"rotation {s_info.get('rot_deg')} deg, shift {s_info.get('shift_mm')} mm; limb bones keep the Z-Anatomy standard pose (her supine cadaver pose is not copied); left / right symmetrised.")
    t = (f"Q250 female skeleton: carried with the deformation of the bones (bone-anchored thin-plate spline; within 1.5 mm of a bone it moves with that bone): mean displacement {st['mean_move_mm']} mm, "
         f"max {st['max_move_mm']} mm; surface area x{st['area_ratio']:.3f}")
    if st.get("signed_volume_ratio") is not None and st["signed_volume_before_mm3"] > 50:
        t += f", enclosed volume x{st['signed_volume_ratio']:.3f}"
    if st.get("newly_in_bone"):
        t += f"; {st['newly_in_bone']} vertices pushed out of a bone (0.4 mm)"
    if st.get("newly_outside_skin"):
        t += f"; {st['newly_outside_skin']} vertices pulled back inside the skin"
    return t + ". Shape is Z-Anatomy's (male-derived), not re-modelled."


def add_badge(m, text):
    rec = dict(m.get("rec") or {})
    if not rec:
        rec = {"name": m["name"]}
    old = rec.get("procedural_badge")
    # the Q233 male-body note of the pelvic bones is superseded by this one
    if old and old.startswith("Q233 sex audit: this Z-Anatomy pelvic bone"):
        old = None
    rec["procedural_badge"] = (old + " || " if old else "") + text
    return rec


def run(src, comb, out, pelvis="her"):
    t0 = time.time(); WORK.mkdir(parents=True, exist_ok=True)
    man, blob = P5.load_page(REPO / src, STEM)
    drop = set(hra_ids(src))
    man = dict(man); man["meshes"] = [m for m in man["meshes"] if m["id"] not in drop]
    Z = P5.decode(man, blob)
    _, _, C = L.load_page(REPO / comb, "atlas_viewer_zan_female")
    print("Z-only page:", len(Z), "structures,", len(drop), "HRA structures set aside", flush=True)

    def ring_fn(G):
        her = HP.her_ring()
        tgt_ring = {k: (G(v), f) for k, (v, f) in her.items()}
        if pelvis == "mean":
            # MEAN female pelvis shape (n = 47 women, CT, TotalSegmentator CC BY 4.0; data/derived/Q250_ts_mean_female_pelvis.npz) at HER pelvic size and position: similarity (scale free) ICP of the
            # mean hip bones + sacrum onto her pelvis in the Z frame; her coccyx is kept (the mean has none)
            zm = np.load(REPO / "data/derived/Q250_ts_mean_female_pelvis.npz")
            mean = {k: (zm[f"{k}_v"], zm[f"{k}_f"]) for k in ("hip_bone_l", "hip_bone_r", "sacrum")}
            sp = np.vstack([L.sample(*mean[k], 9000)[0] for k in mean]); tp = np.vstack([L.sample(*tgt_ring[k], 9000)[0] for k in mean])
            ms, mR, mt, md = L.icp_sim(sp, tp, iters=80, trim=0.9)
            ring_fn.mean_similarity = dict(scale=round(float(ms), 4), residual_median_mm=round(float(np.median(md)), 2), n_women=int(len(zm["cases"])))
            tgt_ring = {**{k: (ms * v @ mR.T + mt, f) for k, (v, f) in mean.items()}, "coccyx": tgt_ring["coccyx"]}
        cache = WORK / f"ring_{pelvis}.npz"
        if cache.exists():
            z = np.load(cache, allow_pickle=True)
            fn_out = {k: z[k] for k in RING}; ring_fn.report = json.loads(str(z["report"]))
        else:
            pts = np.vstack([L.sample(v, f, 20000)[0] for v, f in tgt_ring.values()])
            ring_Z = {k: (Z[k]["v"], Z[k]["f"]) for k in RING}
            # bone-wise start: hips / coccyx = similarity images of the Z bones in Combined . Female (homologous vertices) carried to the Z frame by G; sacrum = similarity ICP onto her sacrum
            placed = {k: G(C[k]["v"]) for k in ("hip_bone_l", "hip_bone_r", "coccyx")}
            sp = L.sample(Z["sacrum"]["v"], Z["sacrum"]["f"], 6000)[0]; tp = L.sample(*tgt_ring["sacrum"], 12000)[0]
            s_, R_, t_, _ = L.icp_sim(sp, tp, iters=60, trim=0.85)
            placed["sacrum"] = s_ * Z["sacrum"]["v"] @ R_.T + t_
            res = PR.register(ring_Z, pts, target_ring=tgt_ring, placed=placed)
            fn_out = res["v"]; ring_fn.report = res["report"]
            np.savez(cache, report=json.dumps(res["report"]), **fn_out)
        return fn_out
    ring_fn.report = {}
    B = ST.build(Z, C, ring_target_fn=ring_fn)
    tgt = B["target"]
    print("target skeleton built", round(time.time() - t0), "s", flush=True)
    A = W.apply(Z, tgt, symmetric=True)
    print("soft tissue carried", round(time.time() - t0), "s", flush=True)
    rep = A["report"]
    repl = {}
    for i, e in Z.items():
        st = rep["structures"][i]
        info = B["report"]["per_bone"].get(i, {})
        txt = badge_text(i, e, st, B["kind"].get(i), info, ring_fn.report, pelvis)
        repl[i] = (A["v"][i], e["f"], add_badge(e["m"], txt))
    man["attribution"] = (man.get("attribution") or "").rstrip() + (
        " Q250: the skeleton of this page is the Z-Anatomy skeleton deformed onto a FEMALE skeleton target: the proportions of the trunk, shoulder girdle and limbs are the Visible Human female's own CT skeleton (one woman), "
        f"the pelvis (hip bones, sacrum, coccyx) is {PELVIS_TXT[pelvis][0]}; standard anatomical pose, left / right symmetrised; every soft structure is carried with the bones (Z-Anatomy shape, not re-modelled); "
        "female organs are the HuBMAP Human Reference Atlas reference organs of the same donor (CC BY 4.0) registered on this pelvis. It is a base for fitting, not an average woman.")
    P5.save_page(REPO / out, STEM, man, blob, replace=repl)
    np.savez_compressed(WORK / f"warp_field_{pelvis}.npz", P=A["control"][0], U=A["control"][1], SP=A["samples"][0].astype(np.float32), SU=A["samples"][1].astype(np.float32))
    R = dict(pelvis_target=pelvis, mean_pelvis_similarity=getattr(ring_fn, "mean_similarity", None), source=src, combined=comb, dropped_hra_structures=sorted(drop), skeleton=B["report"], pelvis_registration=ring_fn.report, warp={k: v for k, v in rep.items() if k != "structures"},
             structures=rep["structures"], seconds=round(time.time() - t0))
    (REPO / ("data/derived/Q250_base_f_warp_report_" + pelvis + ".json")).write_text(json.dumps(R, indent=1, default=float) + "\n")
    print("done", R["seconds"], "s; newly in bone", rep["newly_in_bone_vertices"], "outside skin", rep["newly_outside_skin_vertices"], rep.get("attachment_distance_after_mm"))
    return R


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="build/q244/viewer_base_female"); ap.add_argument("--comb", default="build/q244/viewer_zan_female")
    ap.add_argument("--out", default="build/q250_pre/viewer_base_zonly"); ap.add_argument("--pelvis", default="her", choices=["her", "mean"])
    a = ap.parse_args()
    run(a.src, a.comb, a.out, a.pelvis)
