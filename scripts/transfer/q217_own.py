#!/usr/bin/env python3
"""Q217 own male page (bundle build/viewer_m_hr_q214): the left forearm muscles = the Q217 carried set of the Z male fitted page (build q217_final_zan: zan_ends.pkl) pushed inside HIS OWN skin and out of HIS OWN
bones, separated from his measured arm muscles; replaces his 13 Z-carried forearm muscles (+ their continuation pieces), adds the 8 left forearm muscles his page did not carry.
    python3 scripts/transfer/q217_own.py polish|clamp|metrics|bundle"""
from __future__ import annotations

import json
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer import q217_common as C, q217_slide as SL  # noqa: E402
from scripts.transfer.q200_bundle import Bundle  # noqa: E402

CACHE = REPO / "build" / "q217_cache"
SRC_BUNDLE = REPO / "build/viewer_m_hr_q214"
OWN_BONES = ["humerus_l", "humerus_l_zfill", "radius_l", "radius_l_zfill", "radius_l_distal_q212", "ulna_l", "ulna_l_distal_q212", "carpals_l_q212", "metacarpals_l"]
ARM_OWN = ["biceps_brachii_l", "brachialis_l", "coracobrachialis_l", "triceps_brachii_l"]
_ZF = re.compile(r"_zfill\w*$")


def merged(B, sid):
    """base mesh + its Z-fill continuation pieces (ids sid_zfill*) as one (v, f); hidden base included (the audit merges them the same way)"""
    parts = [it for it in B.items if it["e"]["id"] == sid or re.fullmatch(re.escape(sid) + r"_zfill\w*", it["e"]["id"])]
    vs, fs, off = [], [], 0
    for it in parts:
        v, f = B.mesh(it)
        vs.append(v)
        fs.append(f + off)
        off += len(v)
    return (np.concatenate(vs), np.concatenate(fs)) if vs else None, [it["e"]["id"] for it in parts]


def own_context(B):
    fixed = {}
    for i in ARM_OWN:
        m, _ids = merged(B, i)
        if m is not None:
            fixed[i] = m
    bones = {}
    for i in OWN_BONES:
        g = B.get(i)
        if g is not None:
            bones[i] = (g["v"], g["f"])
    sk = B.get("skin")
    skin = C.SkinGuard([dict(v=sk["v"], f=sk["f"], sys="skin", id="skin")], zone_lo=(-330.0, 40.0, -160.0), zone_hi=(-60.0, 360.0, 200.0), close=1)
    return fixed, bones, skin


def polish(src="zan_ends.pkl", dst="own_polish.pkl", rounds=12):
    B = Bundle(SRC_BUNDLE)
    fixed, bones, skin = own_context(B)
    d = pickle.load(open(CACHE / src, "rb"))
    zone = pickle.load(open(CACHE / "zan_zone.pkl", "rb"))
    mov = {i: d[i] for i in d if i in zone and zone[i]["sys"] == "muscle" and i in C.side_ids(C.FOREARM)}
    sp = SL.Separator(mov, fixed, bones, skin)
    sp.gap_pair = 0.8
    lams = [3.0, 1.5, 0.75, 0.75, 0.4, 0.4, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2]
    for k, lam in enumerate(lams[:rounds]):
        t = time.time()
        tot = sp.step(lam)
        mv = np.mean([np.linalg.norm(sp.x[i] - sp.x0[i], axis=1).mean() for i in sp.ids])
        print(k, lam, {n: (v[0], round(v[1]), round(v[2], 1)) for n, v in tot.items()}, "mean move", round(mv, 2), round(time.time() - t), flush=True)
        pickle.dump({i: (sp.x[i], sp.f[i]) for i in sp.ids}, open(CACHE / dst, "wb"))


OUT_BUNDLE = REPO / "build/viewer_m_hr_q217"
SUBJECT = "xfer_zan2vhm_arm_q217"
ATTRIBUTION = ("Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D): the left forearm muscles this page lacked and the Z-Anatomy base muscles that replace his Z-carried left forearm muscles, carried onto his own "
               "radius / ulna chain by one twisted-tube map and refitted to his own bones and skin inside guards (Q217); the measured structures are not edited. Z-Anatomy: models by the Z-Anatomy project, "
               "app by Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. Licensed CC BY-SA 4.0; this derivative remains CC BY-SA 4.0 (ShareAlike).")
# Z page id -> own id (his page has the first 13 under the same id; the 8 others are added)
ADD_ID = {"anconeus_l": "anconeus_l", "extensor_digiti_minimi_l": "extensor_digiti_minimi_l", "extensor_digitorum_l": "extensor_digitorum_l", "extensor_indicis_l": "extensor_indicis_l",
          "flexor_digitorum_profundus_l": "flexor_digitorum_profundus_l", "zan_extensor_pollicis_longus_l": "zan_extensor_pollicis_longus_l",
          "zan_humero_ulnar_head_of_flexor_digitorum_superficialis_l": "zan_humero_ulnar_head_of_flexor_digitorum_superficialis_l", "zan_palmaris_longus_muscle_l": "zan_palmaris_longus_muscle_l"}


class Bundle217(Bundle):
    def remove(self, sid):
        i = self.find(sid)
        assert len(i) == 1, (sid, i)
        del self.items[i[0]]


def clamp(src="own_polish.pkl", dst="own_clamp.pkl"):
    from scripts.transfer import q217_final_zan as FZ
    B = Bundle(SRC_BUNDLE)
    fixed, bones, skin = own_context(B)
    d = pickle.load(open(CACHE / src, "rb"))
    pickle.dump(FZ.clamp_meshes(d, skin, C.BoneVox(bones)), open(CACHE / dst, "wb"))


def metrics(src="own_clamp.pkl"):
    B = Bundle(SRC_BUNDLE)
    fixed, bones, skin = own_context(B)
    d = pickle.load(open(CACHE / src, "rb"))
    bv = C.BoneVox(bones)
    out, tot = C.muscle_metrics(d, fixed, skin, bv, ids=list(d))
    res = dict(per_muscle=out, total_shared_cm3=tot, mean_shared_pct=round(float(np.mean([o["shared_pct"] for o in out.values()])), 1))
    (REPO / "data/derived/Q217_own_metrics.json").write_text(json.dumps(res, indent=1, default=str))
    print("after total shared", tot, "mean", res["mean_shared_pct"])
    for i, o in out.items():
        print(i[:34].ljust(34), o["vol_cm3"], "shared", o["shared_pct"], "outside skin", o["outside_skin_pct"], "in bone", o["in_bone_pct"], o["bone_depth_max_mm"])


def bundle(src="own_clamp.pkl"):
    from scripts.transfer.q217_final_zan import badge_forearm
    B = Bundle217(SRC_BUNDLE)
    d = pickle.load(open(CACHE / src, "rb"))
    zone = pickle.load(open(CACHE / "zan_zone.pkl", "rb"))
    info = pickle.load(open(CACHE / "zan_carry.pkl", "rb"))["info"]
    met = json.loads((REPO / "data/derived/Q217_own_metrics.json").read_text())["per_muscle"]
    zmet = json.loads((REPO / "data/derived/Q217_zan_metrics.json").read_text())["after"]["per_muscle"]
    report = dict(replaced={}, added={}, removed=[], source_bundle=str(SRC_BUNDLE.name))
    for zid, (v, f) in d.items():
        oid = ADD_ID.get(zid, zid)
        b = met[zid]
        seam = info.get(zid, {}).get("seam_shift_mm")
        existing = B.find(oid)
        if existing:
            e = B.items[existing[0]]["e"]
            old_vol = None
            rec = dict(e.get("rec") or {})
            txt = badge_own(zid, b, seam, replaced=True)
            B.replace(oid, v, f, rec_updates={"procedural_badge": ((rec.get("procedural_badge") or "") + " " + txt).strip()})
            B.items[existing[0]]["e"].pop("hidden_default", None)
            pieces = [it["e"]["id"] for it in B.items if re.fullmatch(re.escape(oid) + r"_zfill\w*", it["e"]["id"])]
            for pid in pieces:
                B.remove(pid)
            report["replaced"][oid] = dict(pieces_removed=pieces, volume_cm3=b["vol_cm3"], shared_pct=b["shared_pct"])
            report["removed"] += pieces
        else:
            rec = dict(zone[zid].get("rec") or {})
            rec["source"] = "Z-Anatomy (CC BY-SA 4.0), fitted to this body; see the badge"
            rec["procedural_badge"] = badge_own(zid, b, seam, replaced=False)
            B.add(oid, "muscle", "left", SUBJECT, rec, v, f)
            report["added"][oid] = dict(volume_cm3=b["vol_cm3"], shared_pct=b["shared_pct"])
    n = B.write(OUT_BUNDLE, new_subject_attribution={SUBJECT: ATTRIBUTION})
    (REPO / "data/derived/Q217_own_report.json").write_text(json.dumps(report, indent=1, default=str))
    print("wrote", OUT_BUNDLE, n, "bytes", len(B.items), "entries; replaced", len(report["replaced"]), "added", len(report["added"]), "pieces removed", len(report["removed"]))


def badge_own(zid, b, seam, replaced):
    seam_txt = (f" Joined at y = 105 mm to its hand-side tendon part (shifted {', '.join(str(x) for x in seam)} mm within the seam plane, decaying over 45 mm)." if seam else "")
    what = ("This muscle replaces his Z-carried left forearm muscle of the same name (one bone at a time, truncated, overlapping its neighbours: share of its volume inside other muscles up to 76 %, and its Z-fill "
            "continuation pieces, which are removed because the new mesh is the whole muscle)") if replaced else "His page did not carry this muscle at all (Z-fill)."
    return (f"Q217: {what}. It is the Z-Anatomy BASE muscle carried onto HIS left forearm by ONE injective map: at every axial level (8 mm) the section of the base forearm is turned and shifted like the two bones radius + ulna "
            f"of the Z-fitted page (his bones within 2 mm; the pronation twist), the chain ending in the distal-humerus block above and the carpal block below, so the Z tiling (muscle | muscle) comes with it.{seam_txt} "
            f"Then pushed inside his own skin (>= 1 mm) and out of his own bone meshes, and separated from the neighbouring muscles (his measured arm muscles included) with a 1.0 mm fascial interface. Numbers "
            f"(voxel measures, 0.5 mm): volume {b['vol_cm3']} cm3 in the working window, share of its volume inside other muscles {b['shared_pct']} %, vertices outside the displayed skin {b['outside_skin_pct']} %, > 1 mm inside a "
            f"displayed bone {b['in_bone_pct']} % (deepest {b['bone_depth_max_mm']} mm). Source class: Filled from Z-Anatomy (not measured on him). His photographed forearm is mostly muscle and larger than the Z muscles: "
            f"the space between them is not filled (volumes are not inflated). A position and boundary estimate, not a segmentation.")


if __name__ == "__main__":
    st = sys.argv[1]
    {"polish": polish, "clamp": clamp, "metrics": metrics, "bundle": bundle}[st]()
