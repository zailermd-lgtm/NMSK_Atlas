#!/usr/bin/env python3
"""Q293: every head / origin of the multi-headed muscles (data/anatomy/muscle_heads_q293.json) and, per page, whether the page's own
muscle mesh(es) reach the bone each head arises from (data/derived/Q293_heads_check.json).

The table lists the heads named by Terminologia Anatomica / Gray's Anatomy for Students 4th ed. / Moore's Clinically Oriented Anatomy
8th ed. (the references the muscle files already use) with each head's origin; `bones` are the bone(s) the head arises from, used for
the check. A head counts as present on a page when the muscle's structures (resolved exactly as the Q284 moment-arm build resolves
them) come within CONTACT_MM of that bone. Nothing is moved or added here: the check shows where a head is in the geometry and where
not; the only head with no geometry at all was the reflected head of rectus femoris (added rule-based in Q293, rf_reflected.py).

    python3 scripts/anatomy/q293/heads_q293.py            # write the table (idempotent) + run the check on the six current page dirs
    python3 scripts/anatomy/q293/heads_q293.py --check    # exit 1 if the table is stale"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
TABLE = REPO / "data/anatomy/muscle_heads_q293.json"
CHECK = REPO / "data/derived/Q293_heads_check.json"
CONTACT_MM = 6.0
GS, MO = "Gray's Anatomy for Students 4th ed.", "Moore's Clinically Oriented Anatomy 8th ed."
# muscle: [(head id, name, origin, [bones], source)]
HEADS = {
    "rectus_femoris": [("straight_head", "Straight (direct) head", "anterior inferior iliac spine (AIIS)", ["hip_bone"], f"{GS}; {MO}; Ryan 2014"),
                       ("reflected_head", "Reflected (indirect) head", "groove above the superior acetabular rim and the hip joint capsule", ["hip_bone"], f"{GS}; {MO}; Ryan 2014; Atzmon 2020")],
    "biceps_brachii": [("long_head", "Long head", "supraglenoid tubercle of the scapula (intra-articular tendon)", ["scapula"], f"{GS}; {MO}"),
                       ("short_head", "Short head", "tip of the coracoid process (with coracobrachialis)", ["scapula"], f"{GS}; {MO}")],
    "triceps_brachii": [("long_head", "Long head", "infraglenoid tubercle of the scapula", ["scapula"], f"{GS}; {MO}"),
                        ("lateral_head", "Lateral head", "posterior humerus above the radial groove", ["humerus"], f"{GS}; {MO}"),
                        ("medial_head", "Medial head", "posterior humerus below the radial groove", ["humerus"], f"{GS}; {MO}")],
    "biceps_femoris": [("long_head", "Long head", "ischial tuberosity (with semitendinosus)", ["hip_bone"], f"{GS}; {MO}"),
                       ("short_head", "Short head", "lateral lip of the linea aspera and lateral supracondylar line", ["femur"], f"{GS}; {MO}")],
    "gastrocnemius": [("medial_head", "Medial head", "popliteal surface of the femur above the medial condyle", ["femur"], f"{GS}; {MO}"),
                      ("lateral_head", "Lateral head", "lateral surface of the lateral femoral condyle", ["femur"], f"{GS}; {MO}")],
    "sternocleidomastoid": [("sternal", "Sternal head", "anterior surface of the manubrium", ["sternum", "manubrium"], f"{GS}; {MO}"),
                            ("clavicular", "Clavicular head", "superior surface of the medial third of the clavicle", ["clavicle"], f"{GS}; {MO}")],
    "pectoralis_major": [("clavicular", "Clavicular head", "anterior surface of the medial half of the clavicle", ["clavicle"], f"{GS}; {MO}"),
                         ("sternocostal", "Sternocostal head", "anterior sternum and the upper six costal cartilages", ["sternum", "manubrium", "body_of_sternum"], f"{GS}; {MO}"),
                         ("abdominal", "Abdominal head", "aponeurosis of the external oblique", [], f"{GS}; {MO}")],
    "flexor_digitorum_superficialis": [("humeroulnar", "Humero-ulnar head", "medial epicondyle, ulnar collateral ligament, coronoid process", ["humerus", "ulna"], f"{GS}; {MO}"),
                                       ("radial", "Radial head", "superior half of the anterior border of the radius", ["radius"], f"{GS}; {MO}")],
    "pronator_teres": [("humeral", "Humeral head", "medial epicondyle", ["humerus"], f"{GS}; {MO}"),
                       ("ulnar", "Ulnar head", "coronoid process of the ulna", ["ulna"], f"{GS}; {MO}")],
    "flexor_carpi_ulnaris": [("humeral", "Humeral head", "medial epicondyle", ["humerus"], f"{GS}; {MO}"),
                             ("ulnar", "Ulnar head", "olecranon and posterior border of the ulna", ["ulna"], f"{GS}; {MO}")],
    "extensor_carpi_ulnaris": [("humeral", "Humeral head", "lateral epicondyle", ["humerus"], f"{GS}; {MO}"),
                               ("ulnar", "Ulnar head", "posterior border of the ulna", ["ulna"], f"{GS}; {MO}")],
    "deltoid": [("clavicular", "Clavicular (anterior) part", "lateral third of the clavicle", ["clavicle"], f"{GS}; {MO}"),
                ("acromial", "Acromial (middle) part", "acromion", ["scapula"], f"{GS}; {MO}"),
                ("spinal", "Spinal (posterior) part", "spine of the scapula", ["scapula"], f"{GS}; {MO}")],
    "adductor_magnus": [("adductor_part", "Adductor part", "inferior pubic ramus, ischial ramus", ["hip_bone"], f"{GS}; {MO}"),
                        ("hamstring_part", "Hamstring part", "ischial tuberosity", ["hip_bone"], f"{GS}; {MO}")],
    "soleus": [("fibular", "Fibular origin", "posterior head and upper quarter of the fibula", ["fibula"], f"{GS}; {MO}"),
               ("tibial", "Tibial origin", "soleal line and medial border of the tibia", ["tibia"], f"{GS}; {MO}")],
    "iliopsoas": [("psoas_major", "Psoas major", "T12-L5 vertebral bodies, discs and transverse processes", ["lumbar"], f"{GS}; {MO}"),
                  ("iliacus", "Iliacus", "iliac fossa, iliac crest, ala of the sacrum", ["hip_bone"], f"{GS}; {MO}")],
    "adductor_pollicis": [("oblique", "Oblique head", "capitate and bases of the 2nd / 3rd metacarpals", ["carpal", "mc_2", "mc_3", "metacarpal"], f"{GS}; {MO}"),
                          ("transverse", "Transverse head", "anterior surface of the 3rd metacarpal shaft", ["mc_3", "metacarpal"], f"{GS}; {MO}")],
    "flexor_pollicis_brevis": [("superficial", "Superficial head", "flexor retinaculum, tubercle of the trapezium", ["carpal"], f"{GS}; {MO}"),
                               ("deep", "Deep head", "trapezoid and capitate", ["carpal"], f"{GS}; {MO}")],
    "medial_pterygoid": [("deep", "Deep head", "medial surface of the lateral pterygoid plate, pyramidal process of the palatine", ["sphenoid", "palatine"], f"{GS}; {MO}"),
                         ("superficial", "Superficial head", "tuberosity of the maxilla, pyramidal process", ["maxilla"], f"{GS}; {MO}")],
    "lateral_pterygoid": [("superior", "Superior head", "infratemporal surface of the greater wing of the sphenoid", ["sphenoid"], f"{GS}; {MO}"),
                          ("inferior", "Inferior head", "lateral surface of the lateral pterygoid plate", ["sphenoid"], f"{GS}; {MO}")],
    "quadratus_plantae": [("medial", "Medial head", "medial surface of the calcaneus", ["calcaneus", "tarsal"], f"{GS}; {MO}"),
                          ("lateral", "Lateral head", "lateral border of the plantar surface of the calcaneus", ["calcaneus", "tarsal"], f"{GS}; {MO}")],
    "adductor_hallucis": [("oblique", "Oblique head", "bases of metatarsals 2-4", ["mt_", "metatarsal"], f"{GS}; {MO}"),
                          ("transverse", "Transverse head", "plantar ligaments of the MTP joints 3-5", [], f"{GS}; {MO}")],
    "digastric": [("posterior", "Posterior belly", "mastoid notch of the temporal bone", ["temporal"], f"{GS}; {MO}"),
                  ("anterior", "Anterior belly", "digastric fossa of the mandible", ["mandible"], f"{GS}; {MO}")],
    "omohyoid": [("inferior_belly", "Inferior belly", "superior border of the scapula near the suprascapular notch", ["scapula"], f"{GS}; {MO}"),
                 ("superior_belly", "Superior belly", "body of the hyoid (insertion; joined by the intermediate tendon)", ["hyoid"], f"{GS}; {MO}")],
}
VARIANTS = {"rectus_femoris": "A third (tendinous) head to the iliofemoral ligament / greater trochanter was found on 83 % of 96 sides by Tubbs 2006 (Folia Morphol 65:377-80, PMID 17171618); a variant, not modelled.",
            "flexor_pollicis_longus": "An accessory head from the medial epicondyle / coronoid (Gantzer's muscle) is a common variant; not modelled.",
            "biceps_brachii": "A third (humeral) head is a recognised variant; not modelled."}
KEYS = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]


def table():
    return {"_README": ["Q293: heads / origins of the multi-headed muscles; scripts/anatomy/q293/heads_q293.py. Sources: " + GS + "; " + MO + "."],
            "m": {m: [{"c": c, "n": n, "o": o, "bones": b, "src": s} for (c, n, o, b, s) in H] for m, H in HEADS.items()}, "variants": VARIANTS}


def check(pagedirs=None):
    import model as Mo
    from scipy.spatial import cKDTree
    out = {"_README": ["Q293: per page, does the page's muscle mesh reach the bone each head arises from (min distance mm; present = <= %g mm)" % CONTACT_MM], "pages": {}}
    for key in KEYS:
        if pagedirs and key in pagedirs:
            os.environ["Q241_SRC_" + key] = str(pagedirs[key])
        M = Mo.Model(key); B = M.bones()
        res = {}
        mom = json.loads((REPO / f"data/anatomy/moment_arms_{key}.json").read_text())["s"]
        idx = {x["id"]: x for x in M.S}
        for m, H in HEADS.items():
            for s in "rl":
                sids = [k for k, v in mom.items() if v["b"] == m and (v.get("side") == s)]
                if m == "rectus_femoris" and f"rectus_femoris_reflected_head_{s}" in idx:
                    sids.append(f"rectus_femoris_reflected_head_{s}")
                if not sids:
                    continue
                V = np.vstack([np.asarray(idx[k]["v"], float) for k in sids if k in idx])
                T = cKDTree(V)
                for (c, n, o, bones, src) in H:
                    if not bones:
                        res[f"{m}|{c}|{s}"] = {"d_mm": None, "present": None, "note": "no bone attachment to check"}; continue
                    ks = [k for k in B if any(k.startswith(bb) or bb in k for bb in bones) and (k.endswith("_" + s) or not k.endswith(("_r", "_l")))]
                    if not ks:
                        res[f"{m}|{c}|{s}"] = {"d_mm": None, "present": None, "note": "bone not on this page"}; continue
                    d = min(float(T.query(np.asarray(B[k]["v"], float))[0].min()) for k in ks)
                    res[f"{m}|{c}|{s}"] = {"d_mm": round(d, 1), "present": d <= CONTACT_MM, "structures": sids}
        out["pages"][key] = res
        miss = sorted(k for k, v in res.items() if v.get("present") is False)
        print(key, len(res), "head checks;", len(miss), "not reaching their bone:", miss[:20])
    CHECK.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


def main():
    t = json.dumps(table(), indent=1, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        ok = TABLE.exists() and TABLE.read_text(encoding="utf-8") == t
        print("up to date" if ok else "out of date: " + str(TABLE)); return 0 if ok else 1
    TABLE.write_text(t, encoding="utf-8")
    dirs = {}
    for a in sys.argv[1:]:
        if "=" in a:
            k, v = a.split("=", 1); dirs[k] = v
    check(dirs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
