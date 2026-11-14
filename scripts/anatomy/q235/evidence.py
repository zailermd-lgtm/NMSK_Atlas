"""Q235: page evidence (bones, skin, bladder, rectum, HRA vagina, own perineal muscles ...) as {key: (V, F)} in the page's atlas frame, from an own-viewer bundle or a Z page."""
from __future__ import annotations
import re, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

KEEP_OWN = ("hip_bone_l", "hip_bone_r", "coccyx", "sacrum", "urinary_bladder", "rectum", "sigmoid_colon", "uterus", "vagina", "skin", "external_anal_sphincter", "levator_ani_l", "levator_ani_r",
            "bulbospongiosus_l", "bulbospongiosus_r", "ischiocavernosus_l", "ischiocavernosus_r", "deep_transverse_perineal_l", "deep_transverse_perineal_r", "ovary_l", "ovary_r")
KEEP_Z = ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx", "zan_urinary_bladder", "zan_sigmoid_colon", "uterus", "vagina", "external_anal_sphincter", "levator_ani_l", "levator_ani_r", "ovary_l", "ovary_r",
          "pubic_symphysis_disc", "zan_skin_perineal_closure")


def own_evidence(bundle_dir):
    from scripts.transfer.q200_bundle import Bundle
    B = Bundle(bundle_dir)
    ev = {}
    for it in B.items:
        e = it["e"]; i = e["id"]
        if i in KEEP_OWN and "zfill" not in i and not e["subject"].startswith("xfer_cvh2"):
            v, f = B.mesh(it)
            k = i
            if i == "sacrum" and v[:, 1].min() > 60:
                k = "sacrum_fill"
            if k in ev:
                continue
            ev[k] = (v, f)
    return ev, B


def z_evidence(page_dir, stem):
    from scripts.zanatomy import q205_pages as P5
    man, blob = P5.load_page(page_dir, stem)
    S = P5.decode(man, blob)
    ev = {k: (S[k]["v"], S[k]["f"]) for k in KEEP_Z if k in S and len(S[k]["f"])}
    sk = [e for i, e in S.items() if e["m"]["sys"] == "skin" and len(e["f"]) >= 6]
    off = 0; V = []; F = []
    for e in sk:
        V.append(e["v"]); F.append(e["f"] + off); off += len(e["v"])
    ev["skin"] = (np.vstack(V), np.vstack(F))
    ev["urinary_bladder"] = ev.pop("zan_urinary_bladder", None) or ev.get("urinary_bladder")
    if ev.get("urinary_bladder") is None:
        ev.pop("urinary_bladder", None)
    if "zan_sigmoid_colon" in ev:
        ev["sigmoid_colon"] = ev.pop("zan_sigmoid_colon")
    return ev, (man, blob, S)
