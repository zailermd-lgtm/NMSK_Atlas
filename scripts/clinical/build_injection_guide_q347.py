#!/usr/bin/env python3
"""Q347: the injection guide's per-page sibling `clinical_injection_guide.json` (PRIVATE clinical layer, Base pages only).

The injection-technique facts of the EURO-MUSCULUS/USPRM spasticity guide (Güvener et al., Eur J Phys Rehabil Med
2026;62(5):441-59, CC BY-NC-ND: facts with citation only) as extracted in `clinical/data/innervation_injection_q322.json`
(injection points, sites, scan start, dynamic manoeuvre, structures at risk; copied VERBATIM, per muscle), plus what the
needle tool's injection mode needs to act on them on this body -- all of it stated, nothing measured here:

  * risk:  the structures the guide's "at risk" text names, each mapped to this project's structure-id stems (the side is
           the target's; the page decides at run time which exist). A name with no modelled structure is kept, unmapped, with
           the reason -- never replaced by a neighbour.
  * conflict: where the guide's TABLE and its TEXT disagree (docs/Q322_innervation_sources.md §1, the `conflicts[]` of
           data/anatomy/innervation_q322.json): the adopted value and the other one.
  * scan:  only where the guide's scan start names a point that is a landmark of the Q322 band placement
           (data/derived/Q322_iz_bands_<page>.json, measured on this body's own bones): the landmark, its bone, its rest
           coordinates per side, and the probe plane when the text states one. Otherwise none (the text is shown only).
  * show:  only where the manoeuvre is a joint motion of this page's pose rig (data/anatomy/pose_rig_<page>.json), as
           illustrative key frames inside the rig's range of motion (the guide gives no angles). Otherwise none.

The IZ bands themselves (the sites' % along named lines and their placement on this body) are NOT copied: the page reads
them from its public sidecar innervation_q322.json.

    python3 scripts/clinical/build_injection_guide_q347.py base_m <page dir>      # writes <page dir>/clinical_injection_guide.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRIVATE = REPO / "clinical" / "data" / "innervation_injection_q322.json"
PUBLIC = REPO / "data" / "anatomy" / "innervation_q322.json"
BANDS = REPO / "data" / "derived" / "Q322_iz_bands_{page}.json"
RIG = REPO / "data" / "anatomy" / "pose_rig_{page}.json"
NAME = "clinical_injection_guide.json"
PAGES = ("base_m", "base_f")
FIELDS = ("injection_points", "sites", "scan_start", "manoeuvre", "at_risk", "src", "cite")

# ---- the named structures of each "at_risk" text -> structure-id stems (side suffix added at run time when the stem has one)
MEDIAN_NOTE = "no median-nerve trunk is modelled on this body (only its muscular / palmar / digital branches)"
R_LACN = {"name": "lateral antebrachial cutaneous nerve", "stems": ["zan_lateral_antebrachial_cutaneous_nerve"]}
R_MEDIAN = {"name": "median nerve", "stems": [], "note": MEDIAN_NOTE}
R_BRACH_A = {"name": "brachial artery", "stems": ["zan_brachial_artery"]}
R_SRN = {"name": "superficial branch of radial nerve", "stems": ["radial_n_superficial_branch"]}
R_RAD_A = {"name": "radial artery", "stems": ["zan_radial_artery"]}
R_ULN_N = {"name": "ulnar nerve", "stems": ["ulnar_n"]}
R_ULN_A = {"name": "ulnar artery", "stems": ["zan_ulnar_artery"]}
R_SCIATIC = {"name": "sciatic nerve", "stems": ["sciatic_n"]}
R_TIBIAL = {"name": "tibial nerve", "stems": ["tibial_n"]}
R_ATA = {"name": "anterior tibial artery", "stems": ["zan_anterior_tibial_artery"]}
R_DPN = {"name": "deep peroneal nerve", "stems": ["deep_fibular_n"]}
RISK = {
    "latissimus_dorsi": [{"name": "intercostal muscles", "stems": ["zan_external_intercostal_muscles", "zan_internal_intercostal_muscles", "zan_innermost_intercostal_muscles"]},
                         {"name": "pleura", "stems": ["zan_pleura"]}],
    "biceps_brachii": [R_LACN],
    "brachialis": [R_MEDIAN, R_BRACH_A],
    "brachioradialis": [R_SRN],
    "pronator_teres": [R_MEDIAN, R_BRACH_A],
    "pronator_quadratus": [dict(R_SRN, name="superficial radial nerve"), R_RAD_A],
    "flexor_carpi_ulnaris": [R_ULN_N],
    "flexor_digitorum_superficialis": [R_MEDIAN, R_ULN_A, R_ULN_N],
    "flexor_digitorum_profundus": [dict(R_MEDIAN, via="flexor_digitorum_superficialis"), dict(R_ULN_A, via="flexor_digitorum_superficialis"),
                                   dict(R_ULN_N, via="flexor_digitorum_superficialis")],          # the guide: "as FDS"
    "flexor_pollicis_longus": [dict(R_SRN, name="superficial radial nerve"), R_RAD_A],
    "extensor_carpi_radialis_longus": [R_SRN],
    "extensor_carpi_radialis_brevis": [R_SRN],
    "piriformis": [R_SCIATIC],
    "biceps_femoris": [R_SCIATIC],
    "flexor_hallucis_longus": [R_TIBIAL],
    "tibialis_anterior": [R_ATA, R_DPN],
    "extensor_digitorum_longus": [R_ATA, R_DPN],
    "extensor_hallucis_longus": [R_ATA, R_DPN],
}

# ---- the guide's table and text disagree (docs/Q322_innervation_sources.md §1; data/anatomy/innervation_q322.json conflicts[])
LD_LINE = ("popliteal fold - inferior margin of the lateral malleolus (text p.455)", "popliteal fold - intermalleolar line (Table II)")
FH_LINE = ("fibular head - medial malleolus (text p.456)", "fibular head - lateral malleolus (Table II)")
CONFLICT = {
    "latissimus_dorsi": ("posterior axillary fold (text p.444)", "axillary fossa (Table I)"),
    "flexor_pollicis_longus": ("Table I: 50% and 65%", "FPL paragraph p.448: no IZ given"),
    "adductor_longus": ("pubic tubercle - medial femoral epicondyle (Table II)", "pubic tubercle - medial femoral condyle (text p.452)"),
    "gastrocnemius": LD_LINE,
    "soleus": LD_LINE,
    "flexor_digitorum_longus": FH_LINE,
    "flexor_hallucis_longus": FH_LINE,
}

# ---- scan starts that name a landmark of the band placement ("trans" = axial / short axis / horizontal plane; None = not stated)
SCAN = {
    "subscapularis": [("scapula_inferior_angle", "trans")],      # "caudal tip of the scapula in the horizontal plane"
    "teres_major": [("scapula_inferior_angle", "trans")],        # "caudal tip of the scapula, horizontal plane"
    "latissimus_dorsi": [("scapula_inferior_angle", "trans")],   # "caudal end of the scapula in short axis"
    "pectoralis_minor": [("coracoid_tip", "trans")],             # "horizontal plane over the coracoid"
    "sartorius": [("medial_femoral_condyle", "trans")],          # "axial over the medial femoral condyle"
    "gracilis": [("medial_femoral_condyle", "trans")],           # "axial over the medial femoral condyle"
    "flexor_hallucis_longus": [("medial_malleolus", "trans")],   # "short axis over the medial malleolus"
    "fibularis_longus": [("lateral_malleolus_tip", None), ("fibular_head", None)],   # "from the lateral malleolus (distal) or the fibular head (proximal)"
    "fibularis_brevis": [("lateral_malleolus_tip", None), ("fibular_head", None)],   # "as fibularis longus"
}

# ---- manoeuvres that are a motion of the pose rig: key frames {joint (side added at run time): {dof: degrees}}, clamped to the rig's ROM
SHOW = {
    "flexor_hallucis_longus": [{"t1_mtp": {"flex": 30}}, {"t1_mtp": {"flex": -30}}, {"t1_mtp": {"flex": 30}}, {"t1_mtp": {"flex": -30}}],
    "extensor_hallucis_longus": [{"t1_mtp": {"flex": 30}}, {"t1_mtp": {"flex": -30}}, {"t1_mtp": {"flex": 30}}, {"t1_mtp": {"flex": -30}}],
    "piriformis": [{"knee": {"flex": 90}}, {"knee": {"flex": 90}, "hip": {"rot": 30}}, {"knee": {"flex": 90}, "hip": {"rot": -30}},
                   {"knee": {"flex": 90}, "hip": {"rot": 30}}, {"knee": {"flex": 90}, "hip": {"rot": -30}}],
    "gracilis": [{"hip": {"abd": 15, "rot": -15}}, {"hip": {"abd": 30, "rot": -30}}, {"hip": {"abd": 30, "rot": -30}}],
}


def build(page: str) -> dict:
    prv = json.loads(PRIVATE.read_text(encoding="utf-8"))
    pub = json.loads(PUBLIC.read_text(encoding="utf-8"))
    lm = json.loads(Path(str(BANDS).format(page=page)).read_text(encoding="utf-8"))["landmarks"]
    rig = json.loads(Path(str(RIG).format(page=page)).read_text(encoding="utf-8"))["rig"]
    joints = {j["id"]: j for j in rig["joints"]}
    src = pub["sources"]["guv2026"]
    muscles = {}
    for k, v in prv["muscles"].items():
        m = {f: v.get(f) for f in FIELDS}
        risk = RISK.get(k, [])
        if v.get("at_risk") and not risk:
            raise SystemExit(f"{k}: at_risk text has no mapping row")
        m["risk"] = [dict(r) for r in risk]
        c = CONFLICT.get(k)
        m["conflict"] = {"adopted": c[0], "other": c[1], "cite": "docs/Q322_innervation_sources.md §1"} if c else None
        scans = []
        for key, plane in SCAN.get(k, []):
            L = lm[key]
            scans.append({"landmark": key, "label": L["label"], "bone": pub["landmarks"][key]["bone"], "plane": plane,
                          "l": L["l"], "r": L["r"]})
        m["scan"] = scans
        frames = SHOW.get(k)
        if frames:
            for fr in frames:
                for jn, dofs in fr.items():
                    j = joints.get(jn + "_r")
                    if not j:
                        raise SystemExit(f"{k}: joint {jn}_r not in the {page} rig")
                    for dk, deg in dofs.items():
                        d = [x for x in j["dof"] if x["k"] == dk]
                        if not d or not (d[0]["lo"] <= deg <= d[0]["hi"]):
                            raise SystemExit(f"{k}: {jn}.{dk} {deg} outside the {page} rig's range")
        m["show"] = frames or None
        muscles[k] = m
    return {"schema": "nmsk.injection_guide.page.v1", "round": "Q347", "page": page, "generated": prv["generated"],
            "licence": prv["licence"],
            "source": {"label": "Güvener et al. 2026", "doi": src["doi"], "journal": "Eur J Phys Rehabil Med 2026;62(5):441-59",
                       "licence": "CC BY-NC-ND 4.0 (facts with citation only)"},
            "rules": {"scan": "Seated over a landmark of the band placement (measured on this body's bones) only where the guide's scan start names it; otherwise text only.",
                      "show": "An illustration on this page's pose rig, inside its range of motion; the guide gives no angles."},
            "muscles": muscles}


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if len(a) != 2 or a[0] not in PAGES:
        print(__doc__)
        return 2
    out = Path(a[1]) / NAME
    out.write_text(json.dumps(build(a[0]), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{a[0]}: wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
