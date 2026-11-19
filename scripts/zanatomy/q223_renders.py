#!/usr/bin/env python3
"""Q223 renders (READ-ONLY): the 5 worst places -> build/q223_renders/ (git-ignored) and data/derived/Q223_render_<n>_*.png (committed, small).
1 own male femoral vein R (62 mm break), 2 own female longissimus L (flat sawn end 1308 mm2), 3 own female grouped tarsals mesh over the single tarsals, 4 Z male fitted left elbow bones
(ulna 9.4 mm into the humerus), 5 own male left hand vs where HIS thumb is (Z-fit thumb chain on his evidence).   python3 scripts/zanatomy/q223_renders.py [1 2 3 4 5]"""
import json, shutil, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q223_paths  # noqa: F401,E402
from scripts.zanatomy import q204_paths as P4  # noqa: E402
from scripts.zanatomy.q198_load import load  # noqa: E402
from scripts.zanatomy import q190_render as R  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

OUT = REPO / "build" / "q223_renders"
DER = REPO / "data" / "derived"
MAG, CREAM, BLUE, GREEN, ORANGE = (0.95, 0.05, 0.75), (0.93, 0.91, 0.80), (0.52, 0.60, 0.72), (0.20, 0.65, 0.30), (0.95, 0.55, 0.10)


def pagescene(key):
    S = load(key)
    if key.startswith("own"):
        S = P4.merge_zfill(S)
    return {s["id"]: s for s in S}


def window(s, c, half):
    cen = s["v"][s["f"]].mean(1)
    keep = np.linalg.norm(cen - c, axis=1) < half
    return s["f"][keep] if keep.sum() > 1 else None


def montage(name, title, lines, views, scene, size=560):
    d = OUT / name
    R.render(scene, views, d, size=(size, size))
    ims = [Image.open(d / f"{v['name']}.png").convert("RGB") for v in views]
    W = Image.new("RGB", (size * len(ims), size + 70), (255, 255, 255))
    for i, im in enumerate(ims):
        W.paste(im, (size * i, 70))
    dr = ImageDraw.Draw(W)
    dr.text((8, 6), title, fill=(0, 0, 0))
    for i, t in enumerate(lines):
        dr.text((8, 24 + 14 * i), t, fill=(120, 0, 0))
    W.save(OUT / f"{name}.png")
    small = W.resize((W.width * 2 // 3, W.height * 2 // 3), Image.LANCZOS)
    small.save(DER / f"Q223_render_{name}.png", optimize=True)
    print(name, "done", flush=True)


def ctx(S, c, half, systems, skip=(), color=None):
    sc = []
    for s in S.values():
        if s["id"] in skip or s["sys"] not in systems:
            continue
        f = window(s, c, half)
        if f is not None:
            sc.append({"v": s["v"], "f": f, "color": (color or (CREAM if s["sys"] == "bone" else BLUE))})
    return sc


def r1():
    S = pagescene("own_m"); t = S["femoral_v_r"]; c = t["v"].mean(0)
    sc = ctx(S, c, 230, ("bone", "vessel", "nerve"), skip=("femoral_v_r",)) + [{"v": t["v"], "f": t["f"], "color": MAG}]
    views = [dict(name="front", az=0, el=0, target=c, half=230), dict(name="side", az=90, el=0, target=c, half=230), dict(name="oblique", az=40, el=15, target=c, half=230)]
    montage("1_own_male_femoral_vein_r", "Own male | femoral_v_r (magenta): two separate pieces 62.0 mm apart, not continuous (also _l 35.0 mm; internal jugular v. r 51.8 / l 43.8 mm)",
            ["cream = bones, blue-grey = other vessels and nerves. The vein is not one tube: a 62 mm stretch of the right femoral vein is missing between its pieces (CT block seam)."], views, sc)


def r2():
    S = pagescene("own_f"); t = S["longissimus_l"]; c = t["v"].mean(0)
    sc = ctx(S, c, 190, ("bone",))
    vf = t["v"][t["f"]]
    nrm = np.cross(vf[:, 1] - vf[:, 0], vf[:, 2] - vf[:, 0]); nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    flat = (np.abs(nrm[:, 2]) > 0.95) & (np.ptp(vf[:, :, 2], axis=1) < 0.3) & (np.abs(vf[:, :, 2].mean(1) + 110.2) < 1.0)
    sc.append({"v": t["v"], "f": t["f"][~flat], "color": MAG}); sc.append({"v": t["v"], "f": t["f"][flat], "color": ORANGE})
    views = [dict(name="back", az=180, el=0, target=c, half=190), dict(name="side", az=-90, el=0, target=c, half=190), dict(name="oblique", az=150, el=20, target=c, half=190)]
    montage("2_own_female_longissimus_l_flat_cut", "Own female | longissimus_l (magenta): cut flat in the z=-110.2 plane, closed cut face 1308 mm2 (orange = the flat sawn face, CT block edge)",
            [f"cream = bones (other muscles hidden). {int(flat.sum())} coplanar faces. 77 flat-cut findings (7 major) on this page, 89 (9 major) on the own male page."], views, sc)


def r3():
    S = pagescene("own_f"); t = S["tarsals_r"]; c = t["v"].mean(0)
    skip = ("tarsals_r",)
    sc = ctx(S, c, 160, ("bone",), skip=skip)
    sc.append({"v": t["v"], "f": t["f"], "color": MAG})
    views = [dict(name="medial", az=-90, el=0, target=c, half=110), dict(name="top", az=0, el=70, target=c, half=110), dict(name="oblique", az=40, el=25, target=c, half=110)]
    montage("3_own_female_tarsals_group_mesh", "Own female | tarsals_r (magenta) is a grouped mesh that duplicates calcaneus_r, talus_r, cuboid_r ... (cream): calcaneus 14.9 mm, cuboid 11.4 mm inside it",
            ["Two overlapping versions of the same tarsal bones on the page (bone-penetration 'major' in the Q204 sense, exact 0.5 mm solid agrees); own male has the same for carpals_l/r vs carpals_l/r_q212 (6 mm)."], views, sc)


def r4():
    S = pagescene("z_male_fit")
    raw = json.loads((REPO / "build/q223_raw/Q204_regions_z_male_fit.json").read_text())
    c = np.asarray(raw["joint_centres"]["elbow_l"])
    sc = []
    for i, col in (("humerus_l", CREAM), ("radius_l", BLUE), ("ulna_l", MAG)):
        sc.append({"v": S[i]["v"], "f": S[i]["f"], "color": col})
    views = [dict(name="lateral", az=-90, el=0, target=c, half=85), dict(name="anterior", az=0, el=0, target=c, half=85), dict(name="posterior", az=180, el=15, target=c, half=85)]
    montage("4_zfit_male_left_elbow_bones", "Z fitted to his reconstruction | left elbow: ulna (magenta) 9.4 mm into the humerus (cream), radius (blue) 6.7 mm into the humerus and 6.2 mm into the ulna",
            ["exact 0.5 mm solids (Q204 2 mm solid: 4.9-6.0 mm). Unfitted base: no elbow pair above 2 mm. The female fit has humerus/radius 7.7 mm on the left."], views, sc)


def r5():
    So = pagescene("own_m"); Sz = pagescene("z_male_fit")
    d = np.linalg.norm(So["radius_l"]["v"].mean(0) - Sz["radius_l"]["v"].mean(0))
    thumb = [f"zan_{n}_l" for n in ("first_metacarpal_bone", "proximal_phalanx_of_first_finger_of_hand", "distal_phalanx_of_first_finger_of_hand")]
    c = Sz[thumb[0]]["v"].mean(0)
    sc = []
    for i in ("carpals_l", "carpals_l_q212", "metacarpals_l", "phalanges_hand_l", "radius_l", "ulna_l", "radius_l_distal_q212", "ulna_l_distal_q212"):
        if i in So:
            sc.append({"v": So[i]["v"], "f": So[i]["f"], "color": CREAM})
    for i in thumb:
        sc.append({"v": Sz[i]["v"], "f": Sz[i]["f"], "color": MAG})
    views = [dict(name="palmar", az=0, el=0, target=c, half=95), dict(name="dorsal", az=180, el=0, target=c, half=95), dict(name="lateral", az=-90, el=0, target=c, half=95)]
    montage("5_own_male_left_thumb", "Own male | left hand bones (cream) vs where HIS thumb is (magenta = Z-fit first metacarpal + phalanges, fitted to his CT/photo evidence, Q205)",
            [f"no own-page bone at the thumb ray (nearest own hand bone to the Z-fit thumb: first metacarpal median 18 mm, phalanges 32-37 mm); frames agree (radius_l centres {d:.1f} mm apart).",
             "Also absent on the own male page: abductor / flexor pollicis brevis L+R, opponens pollicis R (named Z muscles with no counterpart)."], views, sc)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    which = sys.argv[1:] or ["1", "2", "3", "4", "5"]
    for w in which:
        {"1": r1, "2": r2, "3": r3, "4": r4, "5": r5}[w]()
