"""Male RIGHT forearm muscles flooded from one seed per visible belly on five cross-sections (Q180).

The seeds were placed by Claude by reading the five resliced photograph sections (vhm_forearm_seed_sections.py), NOT by
an anatomist: every structure shipped from here carries the badge "seeded by Claude from the photographs, not by an
anatomist; owner review pending". Real data only: his cryosection photographs (Q164 frame, Q165 tissue classes), the Q166
septum lines and his CT radius/ulna.

    python3 scripts/cryo/vhm_forearm_seeded_q180.py prep  --q164-work SCRATCH/q164_m_forearm/work \
        --rgb SCRATCH/q165_m_forearm/rgb_frame.npy --work SCRATCH/q180/work
    python3 scripts/cryo/vhm_forearm_seeded_q180.py views --work SCRATCH/q180/work --sections SCRATCH/q180
    python3 scripts/cryo/vhm_forearm_seeded_q180.py seeds --work SCRATCH/q180/work --sections SCRATCH/q180
    python3 scripts/cryo/vhm_forearm_seeded_q180.py flood --work SCRATCH/q180/work --sections SCRATCH/q180 \
        --q164-work SCRATCH/q164_m_forearm/work --rgb SCRATCH/q165_m_forearm/rgb_frame.npy
    python3 scripts/cryo/vhm_forearm_seeded_q180.py ship  --work SCRATCH/q180/work --q164-work SCRATCH/q164_m_forearm/work
    python3 scripts/cryo/vhm_forearm_seeded_q180.py --stamp build/vh/ct_vhm_forearm_seeded   # after the converter

Stages
 prep   frame-space caches (Q164 frame 1 mm x 0.5 mm): Q165 tissue classes (male colour rule, CT bone dilated 1 mm),
        Q165 paleness residual, Q166 septum lines per slice (Q166 defaults: pale 0.10, support 0.5 over +-1 slice,
        sigma 0.5 mm, h 0.01, axial sigma 1.5 slices), Q165 rule labels sampled per frame voxel.
 seeds  SEED_TABLE -> data/derived/Q180_forearm_seeds.json (+ _page.json in the owner page's store shape), Q165 rule cross-check.
 views  per section: contrast-enhanced gridded crops, Q166 regions and Q165 rule labels drawn in section pixels
        (for reading the photographs and for the rule cross-check).
 flood  (1) seeds (data/derived/Q180_forearm_seeds.json) mapped pixel -> frame index; (2) per seeded plane a marker
        watershed of the muscle class, elevation = Q166 septum line (1) / paleness ridge, lines are barriers;
        (3) the five plane labellings are the markers of a 3-D marker watershed on the paleness + septum volume
        inside the muscle class (compact, 0.005/voxel); a muscle stops where the next plane marks it absent (that plane's
        labels hold the ground), and beyond L5 at max(last seeded plane, the Q165 rule label's last slice) + 10 mm.
        (4) metrics: volumes, main component, bone overlap, boundary on septum, seed jitter Dice.
 ship   RAS label volume, label key, subject mapping (atlas_id only for gate-passing muscles, badged), report
        data/derived/Q180_vhm_forearm_seeded.json. Attempt 2 of 2 (compact watershed) is the shipped one.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(Path(__file__).resolve().parent))

BADGE = "seeded by Claude from the photographs, not by an anatomist; owner review pending"
SUBJECT = "ct_vhm_forearm_seeded"
LABEL_MAP = "vhm_forearm_muscles_seeded"
Q166P = {"pale": 0.10, "support": 0.5, "support_slices": 1, "sigma_mm": 0.5, "h": 0.01, "sigma_u": 1.5}
RULE_VOLUME = REPO / "data/ct_sources/task_outputs/vhm_forearm_muscles_v3.nii.gz"
RULE_LABELS = REPO / "mappings/vhm_forearm_muscles_v3_labels.json"
SEEDS = REPO / "data/derived/Q180_forearm_seeds.json"


# The seeds, read by Claude from the section JPEGs (section_L*.jpg: viewed from distal, anterior up, radial left) with
# contrast/paleness (g/r) zooms and the Q166 septum overlay; identified by compartment, layer, relation to radius/ulna and
# neighbours (Gray's / Moore cross-sectional anatomy). (muscle, x, y, confidence h|m|l, reason); x None = absent.
# "extra" seeds mark a second visible belly of the same muscle on that plane (JSON only; the page holds one per muscle).
SEED_TABLE = {
    "L1": [
        ("pronator_teres", 240, 190, "m", "distinct oval anterolateral belly with oblique (concentric) fascicles, superficial to the radius, lateral-most flexor; radial vessels at its deep lateral edge"),
        ("flexor_carpi_radialis", 365, 130, "l", "superficial strip medial to the PT oval, between its septum and the pale line at x~405"),
        ("palmaris_longus", 430, 110, "l", "small superficial strip between the x~405 line and the FCU septum (x~455)"),
        ("flexor_carpi_ulnaris", 520, 180, "m", "superficial anteromedial belly along the ulnar border"),
        ("flexor_digitorum_superficialis", 420, 230, "l", "intermediate layer deep to FCR/PL, anterior to the radius-ulna gap; no closed septum"),
        ("flexor_digitorum_profundus", 500, 265, "l", "deep belly on the anteromedial ulna"),
        ("flexor_pollicis_longus", None, None, None, "arises below the radial tuberosity; no separate belly on the anterior radius at 15 %"),
        ("brachioradialis", 120, 320, "l", "upper (anterolateral) part of the lateral mass next to the radial vessels; no septum seen splitting it from ECRL"),
        ("extensor_carpi_radialis_longus", 130, 440, "l", "lower (lateral/posterolateral) part of the lateral mass; boundary with BR not visible"),
        ("extensor_carpi_radialis_brevis", 250, 420, "m", "darker belly medial in the lateral mass, lateral to the ED septum (x~300)"),
        ("extensor_digitorum", 340, 470, "m", "superficial posterior belly bounded by septa medial to ECRB and below the supinator"),
        ("extensor_digiti_minimi", 430, 465, "l", "posterior belly medial to ED across the x~400 septum"),
        ("extensor_carpi_ulnaris", 500, 420, "l", "posteromedial belly beside the ulna"),
        ("anconeus", None, None, None, "not distinguishable from ECU/supinator at 15 % (anconeus is on the proximal ulna)"),
        ("supinator", 292, 380, "m", "crescent wrapping the lateral/posterior radius, bounded by a curved pale septum"),
    ],
    "L2": [
        ("pronator_teres", 225, 265, "l", "deep-lateral region above the radius just medial to the oblique septum carrying the radial vessels; heading to its insertion"),
        ("flexor_carpi_radialis", 230, 130, "l", "superficial anterolateral region above the curved line (y~210)"),
        ("palmaris_longus", 340, 80, "l", "superficial midline; no septum separating it from FDS"),
        ("flexor_carpi_ulnaris", 490, 200, "m", "anteromedial superficial belly beyond the ulnar neurovascular junction"),
        ("flexor_digitorum_superficialis", 360, 140, "m", "intermediate belly above the oblique septum that runs from the median nerve (310,215) to the ulnar bundle"),
        ("flexor_digitorum_profundus", 400, 260, "m", "deep belly below the median-nerve/ulnar-bundle septum, on the anterior ulna"),
        ("flexor_pollicis_longus", 285, 285, "l", "deep on the anterior radius, medial to PT"),
        ("brachioradialis", 100, 240, "m", "anterolateral part of the lateral mass above a transverse septum (y~285)"),
        ("extensor_carpi_radialis_longus", 95, 380, "l", "lateral strip of the lateral mass, lateral to the vertical septum x~130"),
        ("extensor_carpi_radialis_brevis", 195, 400, "m", "dark belly between the x~130 septum and the ECRB/ED septum (x~250)"),
        ("extensor_digitorum", 300, 455, "l", "superficial posterior belly below the horizontal posterior septum"),
        ("extensor_digiti_minimi", 390, 450, "l", "posterior belly medial to ED across the x~375 septum"),
        ("extensor_carpi_ulnaris", 455, 430, "l", "posteromedial belly beside the ulna"),
        ("supinator", 330, 385, "l", "deep posterior layer between the bones and the horizontal septum (distal edge of supinator)"),
        ("abductor_pollicis_longus", None, None, None, "only its origin edge expected; not distinguishable from supinator/deep layer"),
        ("extensor_pollicis_longus", None, None, None, "only its origin edge expected; not distinguishable"),
    ],
    "L3": [
        ("pronator_teres", None, None, None, "at its insertion on the lateral radius; no belly separable"),
        ("flexor_carpi_radialis", 185, 120, "l", "superficial anterior region lateral to the Q166 line at x~260, above the radial-vessel Y junction"),
        ("palmaris_longus", None, None, None, "tendon level; no belly seen"),
        ("flexor_carpi_ulnaris", 440, 200, "m", "superficial anteromedial belly along the ulnar border"),
        ("flexor_digitorum_superficialis", 300, 90, "m", "superficial/intermediate belly above the curved septum joining the median nerve (240,170) and the ulnar bundle (375,115)"),
        ("flexor_digitorum_profundus", 340, 215, "m", "deep belly below that septum, anterior to the ulna"),
        ("flexor_pollicis_longus", 175, 232, "l", "deep on the anterior radius below the radial-vessel Y junction"),
        ("brachioradialis", 95, 170, "m", "anterolateral superficial belly lateral to the Y junction (radial artery)"),
        ("extensor_carpi_radialis_longus", None, None, None, "only a thin pale strip (tendon) lateral to ECRB"),
        ("extensor_carpi_radialis_brevis", 140, 310, "m", "large oval belly lateral/posterolateral to the radius, capped by the ECRL tendon line"),
        ("extensor_digitorum", 265, 415, "l", "superficial posterior belly below the Q166 line at y~390"),
        ("extensor_digiti_minimi", 345, 400, "l", "posterior belly medial to ED, below the ECU septum"),
        ("extensor_carpi_ulnaris", 378, 345, "l", "posteromedial belly under the ulna, above the y~370 septum"),
        ("abductor_pollicis_longus", 215, 335, "l", "deep posterior layer on the posterior radius"),
        ("extensor_pollicis_brevis", None, None, None, "origin edge; not distinguishable from APL"),
        ("extensor_pollicis_longus", 285, 328, "l", "deep posterior layer between the bones"),
    ],
    "L4": [
        ("flexor_carpi_radialis", 125, 100, "l", "anterolateral superficial belly with the median nerve (180,148) at its deep-medial corner (FCR/FDS/FPL topology); textbook expects tendon here"),
        ("palmaris_longus", None, None, None, "tendon level"),
        ("flexor_carpi_ulnaris", 370, 150, "h", "large anteromedial belly, clear septum from FDS/FDP and the ulnar bundle"),
        ("flexor_digitorum_superficialis", 225, 110, "m", "dark central superficial oval belly, septum-bounded, medial to the median nerve"),
        ("flexor_digitorum_profundus", 290, 175, "m", "deep belly below the septum from the median nerve to the ulnar bundle"),
        ("flexor_pollicis_longus", 150, 185, "m", "deep belly on the anterior radius below the horizontal septum y~148"),
        ("brachioradialis", None, None, None, "tendon level"),
        ("extensor_carpi_radialis_longus", None, None, None, "tendon level"),
        ("extensor_carpi_radialis_brevis", None, None, None, "lateral strip is tendon-coloured (yellow-brown), no belly"),
        ("extensor_digitorum", 240, 333, "l", "thin superficial posterior layer carrying the pale ED tendon group (195,322)"),
        ("extensor_digiti_minimi", 275, 318, "l", "superficial posterior, medial to ED near its tendon (265,325)"),
        ("extensor_carpi_ulnaris", 325, 290, "m", "posteromedial belly beyond the septum x~305"),
        ("abductor_pollicis_longus", 130, 300, "l", "lateral posterior belly emerging at the lateral border of ED"),
        ("extensor_pollicis_brevis", 185, 262, "l", "deep on the posterior radius, lateral to the vertical septum x~215"),
        ("extensor_pollicis_longus", 205, 300, "l", "deep central belly inside the Q166 enclosure"),
        ("extensor_indicis", 260, 275, "l", "deep posteromedial belly towards the ulna"),
    ],
    "L5": [
        ("flexor_carpi_radialis", 120, 100, "l", "continuation of the L4 anterolateral belly (followed slice by slice); textbook expects tendon"),
        ("palmaris_longus", None, None, None, "tendon (pale superficial midline)"),
        ("flexor_carpi_ulnaris", 310, 125, "h", "large anteromedial belly, clearly septum-bounded"),
        ("flexor_digitorum_superficialis", 185, 90, "m", "central superficial belly (continuation of the dark L4 oval)"),
        ("flexor_digitorum_profundus", 240, 135, "m", "deep medial belly below the superficial row"),
        ("flexor_pollicis_longus", 115, 160, "m", "deep lateral belly on the anterior radius"),
        ("pronator_quadratus", 215, 190, "m", "thin deep layer directly on the anterior radius/ulna and interosseous gap"),
        ("brachioradialis", None, None, None, "tendon level"),
        ("extensor_carpi_radialis_longus", None, None, None, "tendon level"),
        ("extensor_carpi_radialis_brevis", None, None, None, "tendon level"),
        ("extensor_digitorum", None, None, None, "tendons only (pale superficial posterior band)"),
        ("extensor_digiti_minimi", None, None, None, "tendon level"),
        ("extensor_carpi_ulnaris", 288, 262, "l", "small posteromedial belly beside the ulna"),
        ("abductor_pollicis_longus", None, None, None, "tendon (yellow-brown lateral to the radius)"),
        ("extensor_pollicis_brevis", 120, 258, "l", "posterolateral belly on the distal radius"),
        ("extensor_pollicis_longus", 185, 272, "l", "lateral lower part of the large posterior belly, split by a short pale line"),
        ("extensor_indicis", 240, 240, "l", "main part of the large deep posterior belly between the bones"),
    ],
}
EXTRA_SEEDS = {
    "L4": [("flexor_digitorum_superficialis", 295, 85, "l", "second FDS belly superficial-medial (ring/little), septum-bounded above FDP")],
    "L5": [("flexor_digitorum_superficialis", 245, 78, "l", "second FDS belly superficial-medial, septum-bounded")],
}


def to_frame(sec, x, y):
    M = np.array(sec["maps"]["pixel_to_frame_index"]); P = M @ np.array([x, y, 1.0])
    return [float(P[0]), float(P[1]), float(P[2])]


def seeds_stage(a):
    """Write data/derived/Q180_forearm_seeds.json (+ _page.json) with frame/atlas coordinates and the rule cross-check."""
    from scipy import ndimage as ndi
    W = Path(a.work); P = np.load(W / "prep.npz"); M = load_sections(a.sections)
    rule, tis, lines = P["rule"], P["tis"], P["lines"]
    ids = {nm: int(k) for k, nm in json.load(open(RULE_LABELS))["labels"].items()}; inv = {v: k for k, v in ids.items()}
    t = "2026-09-30T00:00:00Z"
    out, page = [], {}
    for sec in M["sections"]:
        L = sec["id"]; i = sec["frame_index_i"]; A = np.array(sec["maps"]["pixel_to_atlas"])
        dl = ndi.distance_transform_edt(~lines[i]) * 0.5
        rows = [(r, False) for r in SEED_TABLE[L]] + [(r, True) for r in EXTRA_SEEDS.get(L, [])]
        for (nm, x, y, conf, why), extra in rows:
            aid = nm + "_r"
            if x is None:
                out.append({"section": L, "muscle": aid, "status": "absent", "reason": why, "by": "claude"})
                page[f"{L}__{aid}"] = {"section": L, "muscle": aid, "status": "absent", "by": "claude", "t": t}
                continue
            fi, fj, fk = to_frame(sec, x, y); j, k = int(round(fj)), int(round(fk))
            inside = 0 <= j < rule.shape[1] and 0 <= k < rule.shape[2]
            rl = inv.get(int(rule[i, j, k]), None) if inside else None
            maj = None
            if inside:
                win = rule[i, max(j - 4, 0):j + 5, max(k - 4, 0):k + 5]; v = np.bincount(win.ravel(), minlength=32); v[0] = 0
                maj = inv.get(int(v.argmax())) if v.max() else None
            X = (A @ np.array([x, y, 1.0]))[:3]
            e = {"section": L, "muscle": aid, "status": "placed", "extra_belly": extra, "x": x, "y": y, "confidence": {"h": "high", "m": "medium", "l": "low"}[conf],
                 "reason": why, "by": "claude", "frame_index_ijk": [round(fi, 2), round(fj, 2), round(fk, 2)],
                 "atlas_mm": [round(float(v), 2) for v in X],
                 "tissue_class_at_seed": {0: "outside", 1: "muscle", 2: "fat", 3: "pale", 4: "bone", 5: "other"}.get(int(tis[i, j, k]), "?") if inside else "outside frame",
                 "distance_to_q166_septum_line_mm": round(float(dl[j, k]), 2) if inside else None,
                 "q165_rule_label_at_seed": rl, "q165_rule_majority_2mm": maj,
                 "agrees_with_q165_rule": bool(rl == nm or maj == nm)}
            out.append(e)
            if not extra:
                page[f"{L}__{aid}"] = {"section": L, "muscle": aid, "status": "placed", "x": x, "y": y, "by": "claude", "t": t}
    placed = [e for e in out if e["status"] == "placed"]
    conf = {c: sum(1 for e in placed if e["confidence"] == c) for c in ("high", "medium", "low")}
    agree = sum(1 for e in placed if e["agrees_with_q165_rule"])
    doc = {"_README": ["Q180 seeds for the Visible Human MALE right forearm, one per visible muscle belly on 5 cross-sections. " + BADGE + ".",
                       "x, y: section JPEG pixels (continuous, (0,0) top-left corner; mapping.json of vhm_forearm_seed_sections.py); frame_index_ijk: Q164 frame; atlas_mm: +X his right, +Y up, +Z anterior.",
                       "Cross-check: Q165 RULE label (rule-based, not truth) at the seed voxel and its majority within 2 mm."],
           "source": "U.S. National Library of Medicine, The Visible Human Project (public domain): male cryosection photographs (IDC series 4aaf9181-fb6a-4a4c-bf49-d1eb9ed4a385), resliced by scripts/cryo/vhm_forearm_seed_sections.py; seeds placed by Claude (" + BADGE + ").",
           "badge": BADGE, "script": "scripts/cryo/vhm_forearm_seeded_q180.py", "sections_script": "scripts/cryo/vhm_forearm_seed_sections.py",
           "summary": {"placed": len(placed), "placed_primary": sum(1 for e in placed if not e["extra_belly"]), "extra_bellies": sum(1 for e in placed if e["extra_belly"]),
                       "absent": sum(1 for e in out if e["status"] == "absent"), "confidence": conf, "agree_with_q165_rule": agree},
           "seeds": out}
    SEEDS.parent.mkdir(parents=True, exist_ok=True); SEEDS.write_text(json.dumps(doc, indent=1))
    pg = {"_README": ["Q180 seeds in the owner page's store shape (forearm_seeds page, db collection 'seeds', doc id '<L#>__<atlas_id>'); for upload by the main session. " + BADGE + "."],
          "collection": "seeds", "docs": page}
    Path(str(SEEDS).replace(".json", "_page.json")).write_text(json.dumps(pg, indent=1))
    print(f"seeds: {doc['summary']}")
    for e in placed:
        if e["tissue_class_at_seed"] != "muscle" or not e["agrees_with_q165_rule"]:
            print(f"  {e['section']} {e['muscle']:36s} tissue {e['tissue_class_at_seed']:6s} line {e['distance_to_q166_septum_line_mm']} rule {e['q165_rule_label_at_seed']} / {e['q165_rule_majority_2mm']}")
    return 0


def load_frame(q164_work):
    F = dict(np.load(Path(q164_work) / "frame.npz"))
    return F


def prep(a):
    from scipy import ndimage as ndi
    import vhm_forearm_muscles_v3 as V
    import vhm_forearm_muscles_v4 as V4
    from cryo_classes import classify as classify_m
    W = Path(a.work); W.mkdir(parents=True, exist_ok=True)
    F = load_frame(a.q164_work); us, ss, ts, c, ax = F["us"], F["ss"], F["ts"], F["c"], F["a"]
    ds = float(ss[1] - ss[0])
    rgb = np.load(a.rgb); isl3 = F["island"]; B = F["B"]
    cls = V.classify_frame(rgb, classify_m)
    bone = np.stack([ndi.binary_dilation(B[i] > 0, iterations=2) for i in range(len(us))])
    tis = V.tissue_map(cls, isl3, bone); del cls, bone
    pres = np.zeros(tis.shape, np.float32)
    for i in range(len(us)):
        if isl3[i].any():
            pres[i] = V.paleness_residual(rgb[i], isl3[i])
    pale = (pres >= Q166P["pale"]) & (tis > 0)
    sup = ndi.maximum_filter(pale, size=(2 * Q166P["support_slices"] + 1, 3, 3))
    pflood = ndi.gaussian_filter1d(pres, Q166P["sigma_u"], axis=0)
    lines = np.zeros(tis.shape, bool)
    for i in range(len(us)):
        m = tis[i] == V.TISSUE["muscle"]
        if m.any():
            lines[i], _ = V4.slice_septa(m, pflood[i], sup[i], Q166P["support"], Q166P["sigma_mm"] / ds, Q166P["h"])
    rule = V4.sample_rule_labels(RULE_VOLUME, tis.shape, us, ss, ts, c, ax)
    np.savez_compressed(W / "prep.npz", tis=tis.astype(np.uint8), pres=pres.astype(np.float16), lines=lines, rule=rule, B=B.astype(np.uint8))
    print(f"prep: {tis.shape}, muscle {(tis == 1).sum()} vox, lines {lines.sum()}, rule labelled {(rule > 0).sum()}")
    return 0


ABBR = {"pronator_teres": "PT", "flexor_carpi_radialis": "FCR", "palmaris_longus": "PL", "flexor_carpi_ulnaris": "FCU",
        "flexor_digitorum_superficialis": "FDS", "flexor_digitorum_profundus": "FDP", "flexor_pollicis_longus": "FPL",
        "pronator_quadratus": "PQ", "brachioradialis": "BR", "extensor_carpi_radialis_longus": "ECRL",
        "extensor_carpi_radialis_brevis": "ECRB", "extensor_digitorum": "ED", "extensor_digiti_minimi": "EDM",
        "extensor_carpi_ulnaris": "ECU", "anconeus": "ANC", "supinator": "SUP", "abductor_pollicis_longus": "APL",
        "extensor_pollicis_brevis": "EPB", "extensor_pollicis_longus": "EPL", "extensor_indicis": "EI"}


def load_sections(sec_dir):
    return json.load(open(Path(sec_dir) / "mapping.json"))


def pixel_grid_to_frame(sec, w, h):
    """Nearest frame (j, k) index for every pixel centre of a section image; -1 outside the frame."""
    M = np.array(sec["maps"]["pixel_to_frame_index"])
    X, Y = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    J = M[1, 0] * X + M[1, 1] * Y + M[1, 2]; K = M[2, 0] * X + M[2, 1] * Y + M[2, 2]
    return np.rint(J).astype(int), np.rint(K).astype(int)


def sample_plane(arr2d, J, K, fill=0):
    ok = (J >= 0) & (K >= 0) & (J < arr2d.shape[0]) & (K < arr2d.shape[1])
    out = np.full(J.shape, fill, arr2d.dtype); out[ok] = arr2d[J[ok], K[ok]]
    return out


def palette(n, seed=3):
    rs = np.random.RandomState(seed); p = rs.randint(40, 255, (n + 1, 3)).astype(np.uint8); p[0] = 0
    return p


def views(a):
    from PIL import Image, ImageDraw
    from scipy import ndimage as ndi
    from skimage import exposure
    import vhm_forearm_muscles_v4 as V4
    W = Path(a.work); P = np.load(W / "prep.npz"); M = load_sections(a.sections); out = W / "views"; out.mkdir(exist_ok=True)
    ids = {int(k): nm for k, nm in json.load(open(RULE_LABELS))["labels"].items()}
    for sec in M["sections"]:
        i = sec["frame_index_i"]; im = Image.open(Path(a.sections) / sec["image"]["file"]).convert("RGB"); w, h = im.size
        J, K = pixel_grid_to_frame(sec, w, h)
        musc = P["tis"][i] == 1; lines = P["lines"][i]
        R, n = V4.regions(musc, lines, 16)
        Rp = sample_plane(R, J, K); Lp = sample_plane(P["rule"][i], J, K); Lin = sample_plane(lines.astype(np.uint8), J, K)
        eq = (exposure.equalize_adapthist(np.asarray(im) / 255.0, clip_limit=0.02, kernel_size=64) * 255).astype(np.uint8)
        up = 2
        for tag, lab, names in (("regions", Rp, None), ("rule", Lp, ids)):
            pal = palette(int(lab.max()) + 1, 3 if tag == "regions" else 7)
            col = pal[lab]; o = eq.copy(); m = lab > 0
            o[m] = (0.55 * eq[m] + 0.45 * col[m]).astype(np.uint8)
            edge = (lab != ndi.grey_erosion(lab, size=3)) & m
            o[edge] = (255, 255, 255)
            if tag == "regions":
                o[Lin > 0] = (0, 255, 255)
            I = Image.fromarray(o).resize((w * up, h * up), Image.NEAREST); d = ImageDraw.Draw(I)
            for x in range(50, w, 50):
                d.line([(x * up, 0), (x * up, h * up)], fill=(0, 160, 0)); d.text((x * up + 2, 2), str(x), fill=(255, 255, 0))
            for y in range(50, h, 50):
                d.line([(0, y * up), (w * up, y * up)], fill=(0, 160, 0)); d.text((2, y * up + 2), str(y), fill=(255, 255, 0))
            for l in np.unique(lab[lab > 0]):
                yy, xx = np.nonzero(lab == l)
                if len(yy) < 60:
                    continue
                k = np.argmin((yy - yy.mean()) ** 2 + (xx - xx.mean()) ** 2)
                txt = ABBR.get(names[int(l)], str(l)) if names else str(int(l))
                d.text((xx[k] * up - 6, yy[k] * up - 5), txt, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
            I.save(out / f"{sec['id']}_{tag}.png")
        eqI = Image.fromarray(eq).resize((w * up, h * up), Image.LANCZOS); d = ImageDraw.Draw(eqI)
        for x in range(25, w, 25):
            d.line([(x * up, 0), (x * up, h * up)], fill=(0, 200, 0) if x % 100 == 0 else (0, 110, 0)); d.text((x * up + 2, 2), str(x), fill=(255, 255, 0))
        for y in range(25, h, 25):
            d.line([(0, y * up), (w * up, y * up)], fill=(0, 200, 0) if y % 100 == 0 else (0, 110, 0)); d.text((2, y * up + 2), str(y), fill=(255, 255, 0))
        eqI.save(out / f"{sec['id']}_eq.png")
        print(sec["id"], "regions", n)
    return 0


OUT_OF_RANGE = ("pronator_teres", "brachioradialis", "extensor_carpi_radialis_longus", "anconeus")   # Q165: arise above his radial-head plane
RIDGE_FULL = 0.15      # paleness residual at which the ridge term is 1 (Q165)
W_RIDGE = 0.8          # Q165 elevation weight
JITTER_MM = 1.5
EXTENT_MARGIN = 10     # slices (mm) past max(last seeded plane, Q165 rule label's last slice) a muscle may run distally
COMPACTNESS = 0.005    # attempt 2: compact watershed (elevation + 0.005 per voxel of distance from the marker) so flat belly
                       # interiors split geometrically between competing seeds while a septum (elevation step ~0.6) still
                       # outweighs ~120 voxels (60 mm in-plane); attempt 1 (0.0) starved seeds sitting on slightly pale spots
SEED_SETTLE_MM = 1.0   # attempt 2: a seed moves to the lowest elevation within 1 mm (Q165 used 2.5 mm)


def load_seeds():
    d = json.load(open(SEEDS))
    return [e for e in d["seeds"] if e["status"] == "placed"]


def muscle_mask(tis, lines, it, ib, ds, min_mm2=4.0):
    from scipy import ndimage as ndi
    m = np.zeros(tis.shape, bool); m[it:ib + 1] = tis[it:ib + 1] == 1
    for i in range(it, ib + 1):
        lb, n = ndi.label(m[i])
        if n:
            sz = np.bincount(lb.ravel()); sm = sz * ds * ds < min_mm2; sm[0] = False; m[i] &= ~sm[lb]
    return m


def elevation(musc, pres, lines, ds):
    """Q165 elevation (0.2 x closeness to non-muscle within 3 mm + 0.8 x pale ridge), Q166 septum lines forced to 1."""
    from scipy import ndimage as ndi
    E = np.ones(musc.shape, np.float32)
    for i in range(musc.shape[0]):
        if musc[i].any():
            d = ndi.distance_transform_edt(musc[i]) * ds
            ridge = np.clip(pres[i].astype(np.float32) / RIDGE_FULL, 0, 1)
            E[i] = (1 - W_RIDGE) * (1 - np.minimum(d, 3.0) / 3.0) + W_RIDGE * ridge
    E[lines] = 1.0
    return E


def plane_labels(seeds, secs, ids, musc, E, lines, shift_px=(0.0, 0.0), r_mm=1.0, ds=0.5, settle_mm=SEED_SETTLE_MM, compactness=COMPACTNESS):
    """2-D marker watershed per seeded plane inside muscle AND NOT septum line. Returns {i: label image}, moves."""
    from skimage.segmentation import watershed
    out, moved = {}, []
    by = {}
    for e in seeds:
        by.setdefault(e["section"], []).append(e)
    for L, es in by.items():
        sec = secs[L]; i = sec["frame_index_i"]; allowed = musc[i] & ~lines[i]
        mk = np.zeros(allowed.shape, np.int32); jj, kk = np.mgrid[0:allowed.shape[0], 0:allowed.shape[1]]
        for e in es:
            _, fj, fk = to_frame(sec, e["x"] + shift_px[0], e["y"] + shift_px[1])
            j, k = int(round(fj)), int(round(fk))
            if settle_mm > 0 and 0 <= j < allowed.shape[0] and 0 <= k < allowed.shape[1] and allowed[j, k]:
                d2 = (jj - fj) ** 2 + (kk - fk) ** 2; cand = allowed & (d2 <= (settle_mm / ds) ** 2)
                sc = np.where(cand, E[i], np.inf); j, k = np.unravel_index(np.argmin(sc), sc.shape)
            if not (0 <= j < allowed.shape[0] and 0 <= k < allowed.shape[1]) or not allowed[j, k]:
                d2 = (jj - fj) ** 2 + (kk - fk) ** 2; cand = allowed & (d2 <= (3.0 / ds) ** 2)
                if not cand.any():
                    moved.append((L, e["muscle"], None)); continue
                sc = np.where(cand, E[i] + 0.01 * np.sqrt(d2), np.inf); j, k = np.unravel_index(np.argmin(sc), sc.shape)
                moved.append((L, e["muscle"], round(float(np.hypot(j - fj, k - fk)) * ds, 2)))
            disk = ((jj - j) ** 2 + (kk - k) ** 2 <= (r_mm / ds) ** 2) & allowed
            mk[disk & (mk == 0)] = ids[e["muscle"][:-2]]
        out[i] = watershed(E[i], mk, mask=allowed, compactness=compactness).astype(np.uint8)
    return out, moved


def flood_once(seeds, secs, ids, musc, E, lines, limits, shift_px=(0.0, 0.0)):
    from skimage.segmentation import watershed
    planes, moved = plane_labels(seeds, secs, ids, musc, E, lines, shift_px)
    mk = np.zeros(musc.shape, np.int32)
    for i, lab in planes.items():
        mk[i] = lab
    nz = np.nonzero(musc.any(axis=(1, 2)))[0]; i0, i1 = int(nz[0]), int(nz[-1]) + 1
    lab = np.zeros(musc.shape, np.uint8)
    lab[i0:i1] = watershed(E[i0:i1], mk[i0:i1], mask=musc[i0:i1], compactness=COMPACTNESS).astype(np.uint8)
    cut = 0
    for l, (lo, hi) in limits.items():
        for sl in (slice(0, lo), slice(hi + 1, None)):
            sel = lab[sl] == l; cut += int(sel.sum()); lab[sl][sel] = 0
    return lab, planes, moved, cut


def dice(a, b):
    s = a.sum() + b.sum()
    return float(2 * (a & b).sum() / s) if s else 1.0


def flood(a):
    from scipy import ndimage as ndi
    import vhm_forearm_muscles_fullres as Q
    import vhm_forearm_muscles_v3 as V
    W = Path(a.work); P = np.load(W / "prep.npz"); M = load_sections(a.sections); secs = {s["id"]: s for s in M["sections"]}
    F = load_frame(a.q164_work); us, ss, ts, c, ax = F["us"], F["ss"], F["ts"], F["c"], F["a"]
    ds = float(ss[1] - ss[0]); du = float(us[1] - us[0]); vox = ds * ds * du / 1000.0
    tis, lines, rule, B = P["tis"], P["lines"], P["rule"], P["B"]; pres = P["pres"].astype(np.float32)
    q165 = json.load(open(REPO / "data/derived/Q165_vhm_forearm_v3.json")); u0, u1 = q165["segment"]["u_mm"]
    it, ib = int(np.argmin(abs(us - u0))), int(np.argmin(abs(us - u1)))
    ids = {nm: int(k) for k, nm in json.load(open(RULE_LABELS))["labels"].items()}; inv = {v: k for k, v in ids.items()}
    seeds = load_seeds(); present = {}
    for e in seeds:
        present.setdefault(e["muscle"][:-2], set()).add(secs[e["section"]]["frame_index_i"])
    names = [nm for nm in ids if nm in present]
    musc = muscle_mask(tis, lines, it, ib, ds)
    E = elevation(musc, pres, lines, ds)
    # distal limit beyond L5 / proximal limit before L1: the rule label's extent (soft) + margin; other ends are held by
    # the neighbouring plane's labels (the muscle is absent/tendon there)
    iL = sorted(s["frame_index_i"] for s in M["sections"])
    limits, lim_info = {}, {}
    for nm in names:
        l = ids[nm]; area = (rule[it:ib + 1] == l).sum(axis=(1, 2)) * ds * ds; ok = np.nonzero(area >= 10.0)[0]
        r_lo, r_hi = (it + int(ok[0]), it + int(ok[-1])) if len(ok) else (it, ib)
        p_lo, p_hi = min(present[nm]), max(present[nm])
        lo = it if p_lo == iL[0] else it       # proximal ends are held by the absent plane above, or the segment top
        hi = min(ib, max(p_hi, r_hi) + EXTENT_MARGIN) if p_hi == iL[-1] else ib
        limits[l] = (lo, hi); lim_info[nm] = {"seeded_planes_i": sorted(present[nm]), "rule_extent_i": [r_lo, r_hi], "allowed_i": [lo, hi]}
    lab, planes, moved, cut = flood_once(seeds, secs, ids, musc, E, lines, limits)
    print(f"flood: labelled {float((lab > 0).sum() * vox):.1f} cm3 of muscle {float(musc.sum() * vox):.1f}; cut by extent {cut * vox:.1f} cm3; seed moves {moved}")
    # ---- jitter: every seed 1.5 mm in 4 directions (section pixels)
    sh = JITTER_MM / secs["L3"]["image"]["pixel_mm"]
    jit = {}
    for tag, s in (("+x", (sh, 0)), ("-x", (-sh, 0)), ("+y", (0, sh)), ("-y", (0, -sh))):
        lj, _, _, _ = flood_once(seeds, secs, ids, musc, E, lines, limits, s)
        jit[tag] = {nm: dice(lab == ids[nm], lj == ids[nm]) for nm in names}
        print(f"jitter {tag}: min Dice {min(jit[tag].values()):.3f}")
    # ---- metrics
    pale = (pres >= Q166P["pale"]) & (tis > 0)
    nonm = ~musc
    per, perc, base = {}, {}, []
    for i in range(it, ib + 1):
        if not musc[i].any():
            continue
        onsep = ndi.binary_dilation(nonm[i] | pale[i], structure=np.ones((3, 3), bool))
        base.append(float(onsep[musc[i]].mean()))
        for l, (fa, fc, _n) in V.boundary_septum_fractions(lab[i], onsep).items():
            per.setdefault(l, []).append(fa)
            if fc is not None:
                perc.setdefault(l, []).append(fc)
    ex = Q.expectations_from_repo(names); arch_arm = Q.expectations_from_repo(list(V.ARM_MUSCLES)); his = V.his_arm_volumes()
    factor = V.scale_factor({k: v[0] for k, v in his.items()}, {k: arch_arm[k][0] for k in V.ARM_MUSCLES})
    photo_bone = tis == 4
    rows = {}
    for nm in names:
        l = ids[nm]; m = lab == l; v = float(m.sum() * vox)
        cc, n = ndi.label(m, structure=np.ones((3, 3, 3), bool))
        mf = float(np.bincount(cc.ravel())[1:].max() / m.sum()) if n else 0.0
        exp = ex[nm][0] * factor; ratio = v / exp if exp else None
        jd = [jit[t][nm] for t in jit]
        sl = np.nonzero(m.any(axis=(1, 2)))[0]
        top_area = float(m[it].sum() * ds * ds); edge = int((m[:, 0, :].sum() + m[:, -1, :].sum() + m[:, :, 0].sum() + m[:, :, -1].sum()))
        why = []
        if nm in OUT_OF_RANGE:
            why.append("arises above his radial-head plane (segment top): only its forearm part is segmented")
        if mf < 0.95:
            why.append(f"main piece {mf:.3f} < 0.95")
        if min(jd) < 0.8:
            why.append(f"seed-jitter Dice {min(jd):.3f} < 0.8")
        if ratio is None or not (0.5 <= ratio <= 2.0):
            why.append(f"volume {v:.1f} cm3 = {ratio:.2f} x expected {exp:.1f}")
        rows[nm] = {"atlas_id": nm + "_r", "label": l, "volume_cm3": round(v, 1), "expected_cm3": round(exp, 1), "ratio": round(ratio, 2) if ratio else None,
                    "architecture_volume_cm3": ex[nm][0], "components_26": int(n), "main_component_fraction": round(mf, 4),
                    "overlap_ct_radius_ulna_vox": int((m & (B > 0)).sum()), "overlap_photographed_bone_class_vox": int((m & photo_bone).sum()),
                    "boundary_on_septum_or_nonmuscle_median": round(float(np.median(per[l])), 3) if l in per else None,
                    "contact_boundary_on_septum_median": round(float(np.median(perc[l])), 3) if l in perc else None,
                    "jitter_dice": {t: round(jit[t][nm], 3) for t in jit}, "jitter_dice_min": round(min(jd), 3),
                    "slices": [int(sl[0]), int(sl[-1])] if len(sl) else None, "u_mm": [float(us[sl[0]]), float(us[sl[-1]])] if len(sl) else None,
                    "area_at_segment_top_mm2": round(top_area, 1), "frame_edge_voxels": edge, "extent": lim_info[nm],
                    "seeds": [{"section": e["section"], "confidence": e["confidence"], "extra_belly": e["extra_belly"]} for e in seeds if e["muscle"] == nm + "_r"],
                    "ship": not why, "reason": "; ".join(why) if why else "passes: main piece >= 0.95, jitter Dice >= 0.8, volume 0.5-2.0 x expected"}
        r = rows[nm]
        print(f"  {nm:32s} {v:6.1f} cm3 x{r['ratio']} main {mf:.3f} ({n}) jit {min(jd):.3f} sep {r['boundary_on_septum_or_nonmuscle_median']} contact {r['contact_boundary_on_septum_median']} {'SHIP' if r['ship'] else 'no: ' + r['reason'][:70]}")
    np.save(W / "lab_frame.npy", lab)
    res = {"rows": rows, "factor": factor, "his": his, "arch_arm": {k: arch_arm[k][0] for k in V.ARM_MUSCLES},
           "chance": round(float(np.median(base)), 3), "cut_cm3": round(cut * vox, 1), "moved": moved,
           "labelled_cm3": round(float((lab > 0).sum() * vox), 1), "muscle_cm3": round(float(musc.sum() * vox), 1),
           "segment": [it, ib], "names": names}
    (W / "flood_result.json").write_text(json.dumps(res, indent=1, default=str))
    montage(a, lab, planes, secs, ids, inv, W)
    return 0


def montage(a, lab, planes, secs, ids, inv, W):
    """Sections with the flooded labels (and 4 in-between frame slices) for looking at."""
    from PIL import Image, ImageDraw
    from scipy import ndimage as ndi
    seeds = load_seeds(); tiles = []
    pal = palette(40, 11)
    for L, sec in secs.items():
        im = Image.open(Path(a.sections) / sec["image"]["file"]).convert("RGB"); w, h = im.size
        J, K = pixel_grid_to_frame(sec, w, h); lp = sample_plane(lab[sec["frame_index_i"]], J, K)
        o = np.asarray(im).copy(); m = lp > 0
        o[m] = (0.5 * o[m] + 0.5 * pal[lp[m]]).astype(np.uint8)
        edge = (lp != ndi.grey_erosion(lp, size=3)) & m; o[edge] = 255
        I = Image.fromarray(o); d = ImageDraw.Draw(I)
        for l in np.unique(lp[lp > 0]):
            yy, xx = np.nonzero(lp == l); k = np.argmin((yy - yy.mean()) ** 2 + (xx - xx.mean()) ** 2)
            d.text((xx[k] - 8, yy[k] - 5), ABBR[inv[int(l)]], fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        for e in seeds:
            if e["section"] == L:
                d.ellipse([e["x"] - 3, e["y"] - 3, e["x"] + 3, e["y"] + 3], fill=(255, 255, 0), outline=(0, 0, 0))
        d.text((4, 4), f"{L} i{sec['frame_index_i']}", fill=(255, 255, 0))
        tiles.append(I)
    # in-between slices in the frame grid (0.5 mm), upsampled 2x
    F = np.load(Path(a.work) / "prep.npz")
    rgb = np.load(a.rgb, mmap_mode="r") if a.rgb else None
    iL = sorted(s["frame_index_i"] for s in secs.values())
    for i in [(iL[k] + iL[k + 1]) // 2 for k in range(4)]:
        base = np.asarray(rgb[i]).copy() if rgb is not None else np.zeros(lab.shape[1:] + (3,), np.uint8)
        lp = lab[i]; m = lp > 0; base[m] = (0.5 * base[m] + 0.5 * pal[lp[m]]).astype(np.uint8)
        edge = (lp != ndi.grey_erosion(lp, size=3)) & m; base[edge] = 255
        I = Image.fromarray(base).resize((lp.shape[1] * 2, lp.shape[0] * 2), Image.NEAREST); d = ImageDraw.Draw(I)
        for l in np.unique(lp[lp > 0]):
            yy, xx = np.nonzero(lp == l); k = np.argmin((yy - yy.mean()) ** 2 + (xx - xx.mean()) ** 2)
            d.text((xx[k] * 2 - 8, yy[k] * 2 - 5), ABBR[inv[int(l)]], fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        d.text((4, 4), f"frame i{i} (frame axes, not section orientation)", fill=(255, 255, 0)); tiles.append(I)
    wmax = max(t.width for t in tiles); hmax = max(t.height for t in tiles); ncol = 3; nr = (len(tiles) + ncol - 1) // ncol
    O = Image.new("RGB", (wmax * ncol, hmax * nr))
    for k, t in enumerate(tiles):
        O.paste(t, ((k % ncol) * wmax, (k // ncol) * hmax))
    p = Path(a.sections) / "montage_seeded.png"; O.save(p); print("montage", p)


SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): male cryosection photographs at full "
          "resolution (0.33 mm, IDC series 4aaf9181-fb6a-4a4c-bf49-d1eb9ed4a385, instances 1575-1819) and his CT radius/ulna labels "
          "(data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz) for registration. Derived data "
          "(scripts/cryo/vhm_forearm_seeded_q180.py): one seed per visible muscle belly on five cross-sections placed by Claude "
          "from the photographs (" + BADGE + "), flooded inside the photographed muscle colour class between the Q166 septum lines "
          "(2-D then 3-D compact marker watershed). Expectations: repository architecture volumes (Holzbaur, Murray & Delp 2005 "
          "Ann Biomed Eng 33:829) scaled by his own upper-arm muscle volumes.")
REF_NOTE = ("Holzbaur KR, Murray WM, Gold GE, Delp SL. Upper limb muscle volumes in adult subjects. J Biomech 2007;40(4):742-749 "
            "(PubMed 17241636): the per-muscle table is not readable here (no PubMed Central full text, checked 2026-09-30), so the "
            "reference per muscle is the repository architecture volume (PCSA x optimal fascicle length / cos pennation, Holzbaur 2005) "
            "x ONE factor = his own biceps+brachialis+triceps volume / theirs (as Q165).")


def badge(r):
    return (f"{BADGE[0].upper() + BADGE[1:]}. Method: Claude placed one seed per visible belly on 5 cross-sections of his cryosection "
            f"photographs (15-85 % of the radius, seeds on {', '.join(sorted({s['section'] for s in r['seeds']}))}, confidence "
            f"{'/'.join(s['confidence'] for s in r['seeds'])}); each seed was grown inside the photographed muscle colour class "
            f"between the photographed septum lines (Q166) by a 2-D then 3-D compact marker watershed on the pale septa. "
            f"Seed-jitter stability (every seed moved 1.5 mm in 4 directions): Dice >= {r['jitter_dice_min']:.2f}. "
            f"Median {round(100 * r['boundary_on_septum_or_nonmuscle_median'])} % of its outline per section lies on a photographed "
            f"pale septum or non-muscle (chance 21 %); where it touches another muscle {round(100 * r['contact_boundary_on_septum_median'])} %. "
            f"Volume {r['volume_ras_cm3']:.1f} cm3 vs reference {r['expected_cm3']:.1f} cm3 (repository architecture volume "
            f"{r['architecture_volume_cm3']:.1f} cm3 x 2.70, his upper-arm ratio; Holzbaur 2007's per-muscle table not accessible). "
            f"Only the part between his radial-head and distal-radius planes is segmented.")


def ship(a):
    import nibabel as nib
    import vhm_forearm_muscles_fullres as Q
    W = Path(a.work); lab = np.load(W / "lab_frame.npy"); res = json.load(open(W / "flood_result.json"))
    F = load_frame(a.q164_work); us, ss, ts, c, ax = F["us"], F["ss"], F["ts"], F["c"], F["a"]
    vol, aff = Q.frame_to_ras_volume(lab, us, ss, ts, c, ax); voxr = float(abs(np.linalg.det(aff[:3, :3])))
    out = REPO / "data/ct_sources/task_outputs/vhm_forearm_muscles_seeded.nii.gz"; nib.save(nib.Nifti1Image(vol, aff), str(out))
    rows = res["rows"]
    for nm, r in rows.items():
        r["volume_ras_cm3"] = round(float((vol == r["label"]).sum() * voxr / 1000.0), 1)
    key = {"_README": [f"Label id -> structure for the Visible Human MALE right forearm seeded muscle volume (Q180). A KEY, not data. {BADGE}."],
           "source": SOURCE, "task": LABEL_MAP, "version": "2026-09-30", "badge": BADGE, "labels": {str(r["label"]): nm for nm, r in rows.items()}}
    (REPO / f"mappings/{LABEL_MAP}_labels.json").write_text(json.dumps(key, indent=1))
    entries = []
    for nm, r in rows.items():
        e = {"label": r["label"], "source_structure": nm, "side": "right", "relationship": "exact", "candidates": [nm + "_r"]}
        if r["ship"]:
            e.update(status="curated", atlas_id=nm + "_r", procedural_badge=badge(r), note=f"{BADGE}; SHIPPED: {r['reason']}.")
        else:
            e.update(status="review", atlas_id=None, note=f"{BADGE}; NOT SHIPPED: {r['reason']}.")
        entries.append(e)
    mp = REPO / f"mappings/subjects/{SUBJECT}_volume_mapping.json"
    mp.write_text(json.dumps({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                          "'procedural_badge' is stamped onto the converted manifest by vhm_forearm_seeded_q180.py --stamp."],
                              "subject": SUBJECT, "source_volume": str(out.relative_to(REPO)), "label_map": LABEL_MAP, "entries": entries}, indent=2))
    seeds = json.load(open(SEEDS))
    report = {"source": SOURCE, "badge": BADGE, "task": "Q180", "script": "scripts/cryo/vhm_forearm_seeded_q180.py", "subject": SUBJECT,
              "seeds": {"file": "data/derived/Q180_forearm_seeds.json", "page_store_file": "data/derived/Q180_forearm_seeds_page.json", **seeds["summary"]},
              "method": {"plane": "2-D compact marker watershed per seeded plane inside muscle class AND NOT Q166 septum line; seed disk 1 mm, seed settles to the lowest elevation within 1 mm",
                         "propagation": "3-D compact marker watershed through the Q164 frame (1 mm x 0.5 mm) on elevation 0.8 x paleness ridge (residual/0.15) + 0.2 x closeness to non-muscle, Q166 lines = 1, inside the Q165 muscle class (specks < 4 mm2 dropped); the 5 plane labellings are the markers",
                         "compactness": COMPACTNESS, "extent": f"proximal: segment top (his radial-head plane) or the plane where the muscle was marked absent; distal beyond L5: max(last seeded plane, Q165 rule label's last slice with >= 10 mm2) + {EXTENT_MARGIN} mm",
                         "attempts": [{"n": 1, "compactness": 0.0, "seed_settle_mm": 0.0, "result": "seeds on slightly pale spots were starved (L3 FCR 8 mm2 on its plane); jitter min Dice 0.34; ship set FDS, FDP", "file": "scratchpad q180/work/flood_result_attempt1.json"},
                                      {"n": 2, "compactness": COMPACTNESS, "seed_settle_mm": SEED_SETTLE_MM, "result": "this report"}]},
              "reference_volumes": {"note": REF_NOTE, "factor": round(res["factor"], 4), "his_upper_arm": res["his"], "architecture_upper_arm_cm3": res["arch_arm"]},
              "septum_metric": {"definition": "per slice, share of a muscle's boundary pixels within 1 px of a non-muscle or pale (paleness residual >= 0.10) pixel; median over slices (Q165 metric); contact = boundary against another muscle only",
                                "chance_baseline": res["chance"], "q165_contact_range": [0.21, 0.53]},
              "tissue": {"muscle_class_cm3": res["muscle_cm3"], "labelled_cm3": res["labelled_cm3"], "cut_by_extent_cm3": res["cut_cm3"]},
              "gate": "main 26-connected piece >= 0.95; seed-jitter Dice (1.5 mm x 4 directions) >= 0.8 in every direction; volume 0.5-2.0 x reference; PT/BR/ECRL/anconeus out of range (arise above the radial-head plane, Q165 rule)",
              "muscles": rows, "shipped": [r["atlas_id"] for r in rows.values() if r["ship"]],
              "label_volume": str(out.relative_to(REPO)), "mapping": str(mp.relative_to(REPO)), "montage": "scratchpad q180/montage_seeded.png"}
    (REPO / "data/derived/Q180_vhm_forearm_seeded.json").write_text(json.dumps(report, indent=1, default=str))
    print(f"shipped {report['shipped']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", nargs="?", choices=("prep", "views", "seeds", "flood", "ship"))
    ap.add_argument("--q164-work"); ap.add_argument("--rgb"); ap.add_argument("--work"); ap.add_argument("--sections")
    ap.add_argument("--stamp", default=None)
    a = ap.parse_args(argv)
    if a.stage == "prep":
        return prep(a)
    if a.stage == "views":
        return views(a)
    if a.stage == "seeds":
        return seeds_stage(a)
    if a.stage == "flood":
        return flood(a)
    if a.stage == "ship":
        return ship(a)
    if a.stamp:
        import vhm_forearm_muscles_fullres as Q
        print(f"stamped {Q.stamp_badges(a.stamp, REPO / f'mappings/subjects/{SUBJECT}_volume_mapping.json')} badges"); return 0
    ap.error("stage required")


if __name__ == "__main__":
    sys.exit(main())
