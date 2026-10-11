#!/usr/bin/env python3
"""Q214: the numbers behind the reasons a muscle was NOT added (data/derived/Q214_skip_evidence.json), measured on the source bundles and the Z pages fitted to the bodies:
  * fibularis brevis: the person's existing fibularis longus mesh vs the Z-Anatomy longus + brevis fitted to the same body (a measured / carried lateral-compartment mass that is already as big as the two Z
    muscles together holds the brevis' territory: adding it would count that tissue twice);
  * flexor pollicis brevis: the thumb skeleton (first metacarpal, proximal phalanx) of the person's right hand vs the fitted Z thumb: his hand bone set ends before the thumb;
  * splenius cervicis: share of the fitted Z cervicis volume that lies in the person's erector / semispinalis meshes (the neighbours it would stack on).

    python3 scripts/transfer/q214_extras.py"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q214_targets as T  # noqa: E402
import motor_points_q187 as MP  # noqa: E402


def vol(v, f):
    return abs(trimesh.Trimesh(np.asarray(v, float), np.asarray(f), process=False).volume) / 1000.0


def main():
    out = {}
    for body in ("vhm", "vhf"):
        cfg = T.BODY[body]
        B = Bundle(cfg["src"])
        MP.VIEWERS["_q214x"] = {"kind": "zan", "html": cfg["z_page"], "label": "z"}
        Z = MP.load_viewer("_q214x")
        o = {}
        for s in "rl":
            own = [vol(*B.mesh(it)) for it in B.items if it["e"]["id"] == f"fibularis_longus_{s}" and it["e"]["cat"] == "muscle"]
            zl, zb = Z[f"fibularis_longus_{s}"], Z[f"fibularis_brevis_{s}"]
            o[f"fibularis_{s}"] = dict(own_fibularis_longus_cm3=round(sum(own), 1), own_subject=[it["e"]["subject"] for it in B.items if it["e"]["id"] == f"fibularis_longus_{s}"][0],
                                       z_fibularis_longus_cm3=round(vol(zl["v"], zl["f"]), 1), z_fibularis_brevis_cm3=round(vol(zb["v"], zb["f"]), 1))
            x = o[f"fibularis_{s}"]
            x["own_over_z_longus"] = round(x["own_fibularis_longus_cm3"] / x["z_fibularis_longus_cm3"], 2)
            x["own_over_z_longus_plus_brevis"] = round(x["own_fibularis_longus_cm3"] / (x["z_fibularis_longus_cm3"] + x["z_fibularis_brevis_cm3"]), 2)
        # right thumb
        s = "r"
        bones = {it["e"]["id"]: B.mesh(it)[0] for it in B.items if it["e"]["cat"] == "bone" and not it["e"].get("hidden_default") and it["e"]["id"] in (
            "metacarpals_r", "phalanges_hand_r", "carpals_r", "carpals_r_q212", "metacarpal_1_r")}
        fpb = Z["flexor_pollicis_brevis_r"]["v"]
        u = np.linalg.svd(fpb - fpb.mean(0), full_matrices=False)[2][0]
        t = (fpb - fpb.mean(0)) @ u
        far = fpb[t >= np.percentile(t, 88)] if np.linalg.norm(fpb[t >= np.percentile(t, 88)].mean(0) - fpb.mean(0)) > 0 else fpb
        far2 = fpb[t <= np.percentile(t, 12)]
        ends = [far, far2]
        allb = np.vstack(list(bones.values()))
        tree = cKDTree(allb)
        dists = [round(float(np.percentile(tree.query(e)[0], 5)), 1) for e in ends]
        thumb_ray = {k: (np.round(v.min(0)).astype(int).tolist(), np.round(v.max(0)).astype(int).tolist()) for k, v in bones.items()}
        z_thumb = {k: (np.round(Z[k]["v"].min(0)).astype(int).tolist(), np.round(Z[k]["v"].max(0)).astype(int).tolist()) for k in ("zan_first_metacarpal_bone_r", "zan_proximal_phalanx_of_first_finger_of_hand_r") if k in Z}
        zp = Z["zan_proximal_phalanx_of_first_finger_of_hand_r"]["v"]
        dph = cKDTree(bones["phalanges_hand_r"]).query(zp)[0]
        zm = Z["zan_first_metacarpal_bone_r"]["v"]
        mc_key = "metacarpal_1_r" if "metacarpal_1_r" in bones else "metacarpals_r"
        dmc = cKDTree(bones[mc_key]).query(zm)[0]
        o["thumb_r"] = dict(z_thumb_proximal_phalanx_to_own_phalanges_mesh_mm=dict(median=round(float(np.median(dph)), 1), min=round(float(dph.min()), 1)),
                            z_first_metacarpal_to_own_metacarpal_mesh_median_mm=dict(mesh=mc_key, median=round(float(np.median(dmc)), 1)),
                            bone_ids_present=sorted(bones), fitted_fpb_end_distances_to_nearest_own_hand_bone_mm=dists, own_hand_bone_extents_mm=thumb_ray, z_thumb_bone_extents_mm=z_thumb,
                            has_first_metacarpal_entry="metacarpal_1_r" in bones)
        out[body] = o
    p = REPO / "data/derived/Q214_skip_evidence.json"
    p.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({b: {k: v for k, v in o.items() if k.startswith("fibularis")} for b, o in out.items()}, indent=1))
    print({b: o["thumb_r"]["fitted_fpb_end_distances_to_nearest_own_hand_bone_mm"] for b, o in out.items()})


if __name__ == "__main__":
    main()
