"""Q243: page evidence for the pelvic vessels (own bundle or Z page): pelvic + lumbar bones, hips, soft organs, skin distance function."""
from __future__ import annotations
import re, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
ORG_OWN = ("urinary_bladder", "rectum", "sigmoid_colon", "uterus", "vagina", "ovary_l", "ovary_r", "levator_ani_l", "levator_ani_r", "common_iliac_v_l", "common_iliac_v_r")


def own_pelvis(bundle_dir):
    from scripts.transfer.q200_bundle import Bundle
    B = Bundle(bundle_dir)
    bones, hips, ev = [], {}, {}
    for it in B.items:
        e = it["e"]; i = e["id"].split("#")[0]
        if e["cat"] == "bone" and "zfill" not in i and e["subject"] != "xfer_vhm2vhf" and (i in ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx", "femur_l", "femur_r")
                                                                                        or (i == "lumbar_vertebrae" and B.mesh(it)[0][:, 1].max() < 330)):
            v, f = B.mesh(it)
            m = trimesh.Trimesh(v, f, process=False); bones.append(m)
            if i in ("hip_bone_l", "hip_bone_r"):
                hips[i[-1]] = m
        if i in ORG_OWN and i not in ev and "zfill" not in e["id"]:
            ev[i] = B.mesh(it)
    return dict(bones=bones, hips=hips, ev=ev, skin_fn=lambda V: B._depth(V)[0], B=B)


def z_pelvis(page_dir, stem):
    from scripts.zanatomy import q205_pages as P5
    man, blob = P5.load_page(Path(page_dir), stem)
    S = P5.decode(man, blob)
    skin = [(e["v"], e["f"]) for i, e in S.items() if e["m"]["sys"] == "skin" and len(e["f"]) >= 6]
    sv = np.vstack([v for v, _ in skin]); off = np.cumsum([0] + [len(v) for v, _ in skin[:-1]])
    sf = np.vstack([f + o for (v, f), o in zip(skin, off)])
    sk_tree = cKDTree(trimesh.Trimesh(sv, sf, process=False).sample(120000))
    lo, hi = np.array([-130, -100, -150.]), np.array([130, 130, 110.])
    bones, hips = [], {}
    for i, e in S.items():
        if e["m"]["sys"] == "bone" and len(e["f"]) > 20 and not ((e["v"].max(0) < lo).any() or (e["v"].min(0) > hi).any()) and not i.startswith(("zan_rib", "ribs")):
            m = trimesh.Trimesh(e["v"], e["f"], process=False); bones.append(m)
            if i in ("hip_bone_l", "hip_bone_r"):
                hips[i[-1]] = m
    ev = {}
    for key, ids in (("urinary_bladder", ("urinary_bladder", "zan_urinary_bladder")), ("rectum", ("rectum", "zan_rectum")), ("sigmoid_colon", ("sigmoid_colon", "zan_sigmoid_colon")),
                     ("uterus", ("uterus",)), ("vagina", ("vagina",)), ("ovary_l", ("ovary_l",)), ("ovary_r", ("ovary_r",)), ("levator_ani_l", ("levator_ani_l",)), ("levator_ani_r", ("levator_ani_r",)),
                     ("common_iliac_v_l", ("zan_common_iliac_vein_l",)), ("common_iliac_v_r", ("zan_common_iliac_vein_r",))):
        for i in ids:
            if i in S and len(S[i]["f"]):
                ev[key] = (S[i]["v"], S[i]["f"]); break
    return dict(bones=bones, hips=hips, ev=ev, skin_fn=lambda V: round(float(sk_tree.query(V)[0].min()), 1), S=S, man=man, blob=blob)
