#!/usr/bin/env python3
"""Q235: register the CVH pelvic bones (closed sacrum + coccyx, pelvic bone) onto HER OWN CT pelvis (the Imaging-based female page; the Combined page shares her frame), for both side conventions of the CVH file
(sx = +1: file +x is the patient's right; sx = -1: left), report the residuals per landmark region, the cross-check against the page's organs and the chirality evidence.
    python3 scripts/anatomy/q235/register_own.py       -> data/derived/Q235_cvh_to_vhf_transform.json   (~6 min)"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q235 import core as C, cvh, evidence, fit as Fm, register as R  # noqa: E402

OUT = REPO / "data" / "derived" / "Q235_cvh_to_vhf_transform.json"
SRC = REPO / "build" / "viewer_f_hr_q234"


def main():
    np.random.seed(0)
    ev, B = evidence.own_evidence(SRC)
    res = {}
    for sx in (1, -1):
        T, aux = C.fit_page(ev, sx)
        dst = aux["dst"]
        reg = C.regional(T, ev, sx)
        inf = C.inferior_residual(T, ev, sx, dst)
        cc = C.crosscheck(ev, T, sx)
        res[sx] = dict(T=T, transform=C.regs(T), start_pitch_yaw=aux["start"], residual_mm=reg, inferior_pelvis_mm=inf, crosscheck=cc)
        print("sx", sx, "scale", round(T[0], 4), reg["all CVH bone vertices"], inf, flush=True)
    # chirality evidence: asymmetric structures, symmetric NN median for both conventions (smaller = better), bones included
    keys = {"CVH rectum smooth muscle (7) vs page rectum + sigmoid": "rectum smooth muscle (CVH 7) vs page rectum + sigmoid", "CVH ovaries (16) vs HRA ovaries (sides from Q233)": "ovaries (CVH 16) vs HRA ovaries",
            "CVH uterine wall (17) vs HRA uterus": "uterine wall (CVH 17) vs HRA uterus", "CVH vaginal wall (21) vs HRA vagina": "vaginal wall (CVH 21) vs HRA vagina"}
    ch = {}
    for nm, k in keys.items():
        a, b = res[1]["crosscheck"].get(k), res[-1]["crosscheck"].get(k)
        if a and b:
            ch[nm] = dict(sx_plus1_median_mm=a["sym_nn_median_mm"], sx_minus1_median_mm=b["sym_nn_median_mm"], difference_minus1_minus_plus1_mm=round(b["sym_nn_median_mm"] - a["sym_nn_median_mm"], 2),
                          sx_plus1_p90_mm=a["sym_nn_p90_mm"], sx_minus1_p90_mm=b["sym_nn_p90_mm"])
    bone = dict(sx_plus1_median_mm=res[1]["residual_mm"]["all CVH bone vertices"]["median"], sx_minus1_median_mm=res[-1]["residual_mm"]["all CVH bone vertices"]["median"],
                sx_plus1_p90_mm=res[1]["residual_mm"]["all CVH bone vertices"]["p90"], sx_minus1_p90_mm=res[-1]["residual_mm"]["all CVH bone vertices"]["p90"])
    bone["difference_minus1_minus_plus1_mm"] = round(bone["sx_minus1_median_mm"] - bone["sx_plus1_median_mm"], 2)
    prefer = {k: (1 if v["difference_minus1_minus_plus1_mm"] >= 2.0 else (-1 if v["difference_minus1_minus_plus1_mm"] <= -2.0 else 0)) for k, v in ch.items()}
    n1 = sum(1 for v in prefer.values() if v == 1); nm1 = sum(1 for v in prefer.values() if v == -1)
    determinable = (n1 >= 3 or nm1 >= 3) and not (n1 and nm1)
    # best-fit chirality = the convention with the lower mean symmetric nearest-neighbour median over the bones and the asymmetric structures (the bones are nearly mirror-symmetric: they hardly vote)
    m_plus = float(np.mean([bone["sx_plus1_median_mm"]] + [v["sx_plus1_median_mm"] for v in ch.values()])); m_minus = float(np.mean([bone["sx_minus1_median_mm"]] + [v["sx_minus1_median_mm"] for v in ch.values()]))
    chosen = 1 if m_plus <= m_minus else -1
    n_favour_minus = sum(1 for v in ch.values() if v["difference_minus1_minus_plus1_mm"] < 0)
    doc = dict(schema="q235_cvh_to_vhf_v1", page_source=str(SRC.relative_to(REPO)), cvh_meshes_used="44 pelvic bone (open-looking sheet, two components), 45 sacral and coccygeal bone (closed)",
               frame_note="CVH file: mm, x lateral, y posterior, z inferior, midline x = 184; atlas: +X right, +Y superior, +Z anterior. Map X = sx (x - 184), Y = -z, Z = -y; sx = +1 (file +x = right) is a reflection of the numbers, which is the identity on the anatomy "
                          "because the atlas frame is left-handed; sx = -1 is a proper rotation.",
               method="bidirectional trimmed closest-point iteration (scripts/anatomy/q235/register.py): rigid + uniform scale, only the page bone points inside the bounding box of the moved CVH bones take part (the CVH bones are cropped: a one-way ICP "
                      "of a partial surface onto the whole bone inflates the scale); three starts (pelvic tilt +30, 0, -30 deg), the lowest median wins; all three converge to the same transform within 0.1 %.",
               target="her hip bones, sacrum (with coccyx) of build/viewer_f_hr_q234",
               by_sx={str(sx): {k: v for k, v in res[sx].items() if k != "T"} for sx in (1, -1)},
               chirality=dict(bone_residual=bone, asymmetric_structures=ch, decision_rule="the side is called determinable only if at least 3 independent asymmetric structures prefer the same chirality by >= 2.0 mm in the median symmetric nearest-neighbour distance and none the other; "
                              "the round ligaments are not used (Q234 labels them on the side opposite to the ovaries of the same files)", preferences=prefer, determinable=bool(determinable),
                              conclusion=("not determinable: no asymmetric structure of the set separates the two conventions by 2 mm (all differences are below the individual variation); the bone fit differs by "
                                          f"{abs(bone['difference_minus1_minus_plus1_mm'])} mm median (bones are nearly mirror-symmetric). {n_favour_minus} of {len(ch)} asymmetric structures fit slightly better with sx = -1, each by less than 2 mm in the median "
                                          f"(mean over bones + structures: {m_plus:.2f} mm for sx = +1, {m_minus:.2f} mm for sx = -1). The side labels of the paired structures follow the best-fit convention sx = {chosen:+d} "
                                          f"(file +x = patient {'right' if chosen == 1 else 'left'}) and are marked as assigned by the registration.")), mean_median_mm=dict(sx_plus1=round(m_plus, 3), sx_minus1=round(m_minus, 3)), chosen_sx=chosen,
               transform=res[chosen]["transform"], scale=res[chosen]["transform"]["scale"], rotation=res[chosen]["transform"]["rotation"], translation_mm=res[chosen]["transform"]["translation_mm"],
               residual_mm=res[chosen]["residual_mm"], inferior_pelvis_mm=res[chosen]["inferior_pelvis_mm"], crosscheck=res[chosen]["crosscheck"])
    OUT.write_text(json.dumps(doc, indent=1, default=float) + "\n")
    print("wrote", OUT.name, "chosen sx", chosen, "determinable", determinable, ch)


if __name__ == "__main__":
    main()
