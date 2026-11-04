"""Q295 Phase 1: systematic axial cross-sections of each page's meshes; void / overlap per region; where the voids are; what the body's own
imaging (her CT HU / his cryosection colour) says is in each void.

    python3 audit295.py KEY [--tag before] [--src DIR] [--levels 30]
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sl295 as S  # noqa: E402

OUT = Path("/dev/shm/q295/audit")
BODY = {"own_m": "vhm", "comb_m": "vhm", "base_m": "vhm", "own_f": "vhf", "comb_f": "vhf", "base_f": "vhf"}
RES = 1.0
SKIN_MM = 1.5          # the skin itself (dermis + epidermis) is a surface on every page: its own thickness is not counted as void

ARM = re.compile(r'humer|radius|ulna|carp|scaphoid|lunate|triquetr|pisiform|trapezi|capitate|hamate|metacarp|phalan.*hand|phalanges_hand|finger_of_hand|_of_hand_|sesamoid.*hand')
HAND = re.compile(r'carp|scaphoid|lunate|triquetr|pisiform|trapezi|capitate|hamate|metacarp|phalan.*hand|phalanges_hand|finger_of_hand|_of_hand_')
LEG = re.compile(r'femur|patella|tibia|fibul|talus|calcan|navicul|cuboid|cuneif|metatars|phalan.*foot|phalanges_foot|finger_of_foot|toe|tarsal')
FOOT = re.compile(r'talus|calcan|navicul|cuboid|cuneif|metatars|phalan.*foot|phalanges_foot|finger_of_foot|toe|tarsal')
VERT = re.compile(r'vertebra|cervical_vertebrae|thoracic_vertebrae|lumbar_vertebrae')


def bone_range(pg, pat, side=None):
    s = pg.sid_where(lambda k, c, n: c == 'bone' and re.search(pat, k) and (side is None or k.endswith('_' + side)))
    if len(s) == 0:
        return None
    lo, hi = pg.bbox(s)
    return float(lo[1]), float(hi[1])


def regions(pg):
    R = {}
    mand = bone_range(pg, r'^mandible$'); stern = bone_range(pg, r'^sternum$'); hip = bone_range(pg, r'^hip_bone_[rl]$')
    fem = bone_range(pg, r'^femur_[rl]$'); tib = bone_range(pg, r'^tibia_[rl]$'); hum = bone_range(pg, r'^humerus_[rl]$')
    rad = bone_range(pg, r'^radius_[rl]$'); calc = bone_range(pg, r'^calcaneus_[rl]$'); tal = bone_range(pg, r'^talus_[rl]$')
    hand = bone_range(pg, HAND.pattern)
    R["head"] = (mand[0] + 5, mand[1] + 55)
    R["neck"] = (stern[1] + 8, mand[0] - 3)
    R["thorax"] = (stern[0] + 5, stern[1] - 3)
    R["abdomen"] = (hip[1] + 3, stern[0] - 5)
    R["pelvis"] = (hip[0] + 3, hip[1] - 3)
    R["thigh"] = (fem[0] + 70, hip[0] - 5)
    R["knee"] = (tib[1] - 25, fem[0] + 65)
    R["leg"] = (tib[0] + 25, tib[1] - 30)
    R["foot"] = (calc[0] + 3, tal[1] - 3)
    R["upper_arm"] = (hum[0] + 30, hum[1] - 35)
    R["forearm"] = (rad[0] + 15, rad[1] - 15)
    R["hand"] = (hand[0] + 2, hand[1] - 2)
    return R


LIMB_REG = {"thigh": LEG, "knee": LEG, "leg": LEG, "foot": FOOT, "upper_arm": ARM, "forearm": ARM, "hand": HAND}


def space_name(region, names, frac):
    """anatomical space of a deep void from the names of the structures around it"""
    t = " ".join(names).lower()
    has = lambda p: re.search(p, t) is not None
    if region == "head":
        if has(r'eyeball|bulb|rectus.*(sup|inf|lat|med)|oblique.*(sup|inf)|levator palpebrae|optic|lacrimal|orbit'):
            return "orbital"
        if has(r'buccinator|masseter|zygomatic|pterygoid|parotid|risorius'):
            return "buccal / masticator"
        return "head, other"
    if region == "neck":
        if has(r'carotid|jugular|vagus'):
            return "carotid sheath / parapharyngeal"
        if has(r'trapez|splen|semispin|levator scap|scalen'):
            return "posterior triangle / posterior neck"
        return "neck, other"
    if region == "thorax":
        if has(r'lung|heart|pericard|aort|esophag|oesophag|trachea|thym|atri|ventric|vena cava|azygos'):
            return "mediastinal / pleural"
        if has(r'breast|mamm'):
            return "breast"
        if has(r'axill|subscap|teres|latissim') and has(r'pector|serrat|coracobr|humer'):
            return "axillary"
        return "chest wall"
    if region == "abdomen":
        if has(r'kidney|renal|psoas|quadratus lumb|adrenal|suprarenal|ureter|vena cava|aorta'):
            return "retroperitoneal / perirenal"
        if has(r'intestin|colon|jejun|ileum|duoden|stomach|liver|mesent|pancrea|spleen|caecum|cecum|omentum|gallbl'):
            return "intraperitoneal (mesenteric / omental)"
        return "abdominal wall / paravertebral"
    if region == "pelvis":
        if has(r'levator|anal|ischio|coccyg|puborect|iliococcyg|pubococcyg') and has(r'obturator int|gluteus max|anal|sphinct'):
            return "ischioanal fossa"
        if has(r'bladder|uter|rectum|prostat|vagin|seminal|ovar|sigmoid'):
            return "pelvic visceral (perivesical / perirectal)"
        if has(r'glute|piriform|gemell'):
            return "gluteal intermuscular"
        return "pelvis, other"
    if region == "knee":
        if has(r'patell') and not has(r'gastrocn|popliteus|semimembr'):
            return "infrapatellar (Hoffa) / suprapatellar"
        if has(r'gastrocn|popliteus|semimembr|semitend|biceps femoris|tibial n|popliteal'):
            return "popliteal"
        return "knee, other"
    if region == "leg":
        if frac < 0.15 and has(r'calcaneal tendon|achilles|soleus|flexor hallucis'):
            return "pre-Achilles (Kager)"
        return "intermuscular (leg)"
    if region == "foot":
        if has(r'plantar|abductor hallucis|flexor digitorum brevis|quadratus plantae|calcan'):
            return "plantar / heel pad"
        return "foot, other"
    if region == "upper_arm":
        if frac > 0.8:
            return "axillary"
        return "intermuscular (arm)"
    if region == "forearm":
        return "intermuscular (forearm)"
    if region == "hand":
        return "palmar / digital"
    return region + ", deep"


def analyse(pg, key, nlev=30, orc=None, reg=None, shots=None):
    skin = pg.sid_where(lambda k, c, n: c == 'skin')
    cnt = pg.sid_where(lambda k, c, n: c != 'skin'); cnt = cnt[~pg.hidden[cnt]]
    bones = set(pg.sid_where(lambda k, c, n: c == 'bone').tolist())
    fat_s = pg.sid_where(lambda k, c, n: c == 'fat'); fat_s = fat_s if len(fat_s) else None
    lo, hi = pg.bbox(skin)
    u0, v0 = lo[0] - 5, lo[2] - 5; W = int((hi[0] - lo[0] + 10) / RES); H = int((hi[2] - lo[2] + 10) / RES)
    grid = (u0, v0, RES, W, H)
    jj, ii = np.mgrid[0:H, 0:W]
    R = regions(pg); out = {"key": key, "regions": {}, "grid_mm": RES, "skin_layer_mm": SKIN_MM}
    for rname, (ya, yb) in R.items():
        if yb <= ya:
            continue
        ys = np.linspace(ya, yb, nlev)
        acc = dict(body=0, cov=0, void=0, void_sub=0, void_deep=0, overlap=0, big3=0, big5=0, big10=0, maxdiam=0.0)
        spaces, cls_sub, cls_deep, levels = {}, np.zeros(6), np.zeros(6), []
        for li, y0 in enumerate(ys):
            body, cov, lab, bad = S.slice_page(pg, y0, grid, skin, cnt)
            body &= ~ndi.binary_dilation(~body, iterations=int(round(SKIN_MM / RES)))   # minus the skin layer itself
            # ROI: limb regions = body pixels whose nearest bone is a limb bone of the region; trunk regions = the rest
            bl = np.where(np.isin(lab, list(bones)), lab, -1)
            if (bl >= 0).any():
                _, (ni, nj) = ndi.distance_transform_edt(bl < 0, return_indices=True)
                near = bl[ni, nj]; dist = ndi.distance_transform_edt(bl < 0) * RES
                names = np.array(pg.ids, object)
                isl = np.zeros(len(pg.ids) + 1, bool)
                for s in bones:
                    isl[s] = bool(LIMB_REG[rname].search(pg.ids[s])) if rname in LIMB_REG else bool(ARM.search(pg.ids[s]) or LEG.search(pg.ids[s]))
                limb = isl[near]
                roi = body & (limb if rname in LIMB_REG else ~limb)
                if rname in LIMB_REG:
                    roi &= dist < {"thigh": 120, "knee": 90, "leg": 80, "foot": 80, "upper_arm": 80, "forearm": 60, "hand": 40}[rname]
            else:
                roi = body & (rname not in LIMB_REG)
            if roi.sum() < 50:
                continue
            void = roi & (cov == 0)
            solid = (cov > 0) & body
            env = ndi.binary_fill_holes(ndi.binary_closing(solid, iterations=4)) & roi
            vsub = void & ~env; vdeep = void & env
            lv, nv = ndi.label(void)
            dt = ndi.distance_transform_edt(void) * RES
            if nv:
                md = ndi.maximum(dt, lv, np.arange(1, nv + 1)) * 2
                acc["big3"] += int((md > 3).sum()); acc["big5"] += int((md > 5).sum()); acc["big10"] += int((md > 10).sum())
                acc["maxdiam"] = max(acc["maxdiam"], float(md.max()))
            acc["body"] += int(roi.sum()); acc["cov"] += int((roi & (cov > 0)).sum()); acc["void"] += int(void.sum())
            if fat_s is not None:
                _, covf, _, _ = S.slice_page(pg, y0, grid, skin, fat_s)
                fm = (covf > 0) & roi; other = (cov - covf) > 0
                acc["fat_px"] = acc.get("fat_px", 0) + int(fm.sum()); acc["fat_over"] = acc.get("fat_over", 0) + int((fm & other).sum())
                acc["over_nonfat"] = acc.get("over_nonfat", 0) + int((roi & ((cov - covf) > 1)).sum())
            acc["void_sub"] += int(vsub.sum()); acc["void_deep"] += int(vdeep.sum()); acc["overlap"] += int((roi & (cov > 1)).sum())
            # deep void spaces by their neighbours
            ld, nd = ndi.label(vdeep)
            if nd:
                ring = ndi.binary_dilation(vdeep, iterations=3) & (lab >= 0)
                # nearest deep-void component for every ring pixel
                _, (ai, aj) = ndi.distance_transform_edt(ld == 0, return_indices=True)
                comp = ld[ai, aj]
                areas = np.bincount(ld.ravel(), minlength=nd + 1)
                for c in range(1, nd + 1):
                    if areas[c] < 4:
                        nm = "small slivers (< 4 mm2)"
                    else:
                        nb = np.unique(lab[ring & (comp == c)])
                        nm = space_name(rname, [pg.names[s] + " " + pg.ids[s] for s in nb if s >= 0], li / max(nlev - 1, 1))
                    spaces[nm] = spaces.get(nm, 0) + int(areas[c])
            # what the body's own imaging says is there
            if orc is not None:
                import oracle295 as O
                full, _ = O.slice_classes(orc, reg, grid, y0, body)
                for m, accv in ((vsub, cls_sub), (vdeep, cls_deep)):
                    if m.any():
                        accv += np.bincount(full[m], minlength=6)[:6]
            levels.append({"y": round(float(y0), 1), "roi": int(roi.sum()), "void": int(void.sum()), "sub": int(vsub.sum()), "deep": int(vdeep.sum()), "overlap": int((roi & (cov > 1)).sum())})
            if shots is not None and li in (nlev // 4, nlev // 2, (3 * nlev) // 4):
                img = np.zeros((H, W, 3), np.uint8); img[body] = (45, 45, 45)
                img[(cov > 0) & body] = (170, 95, 80); img[(cov > 1) & body] = (215, 185, 70)
                if fat_s is not None:
                    isf = np.isin(lab, fat_s) & body
                    soft_ids = [x for x in fat_s if pg.ids[x].startswith("soft_")]
                    iss = np.isin(lab, soft_ids) & body
                    img[isf & ~iss] = (255, 244, 200); img[iss] = (150, 125, 185)
                img[vdeep] = (255, 40, 200); img[vsub] = (40, 210, 255)
                img[body & ~roi & (cov == 0)] = (80, 80, 80)
                ys_, xs_ = np.nonzero(roi)
                crop = img[max(ys_.min() - 5, 0): ys_.max() + 6, max(xs_.min() - 5, 0): xs_.max() + 6][::-1]
                shots.append((rname, round(float(y0)), crop))
        b = max(acc["body"], 1)
        out["regions"][rname] = {"y_range": [round(ya, 1), round(yb, 1)], "levels": len(levels), "area_cm2": round(acc["body"] * RES * RES / 100, 1),
                                 "void_frac": round(acc["void"] / b, 4), "void_sub_frac": round(acc["void_sub"] / b, 4), "void_deep_frac": round(acc["void_deep"] / b, 4),
                                 "overlap_frac": round(acc["overlap"] / b, 4), "holes_gt3mm": acc["big3"], "holes_gt5mm": acc["big5"], "holes_gt10mm": acc["big10"],
                                 "max_hole_diam_mm": round(acc["maxdiam"], 1),
                                 "fat_area_frac": round(acc.get("fat_px", 0) / b, 4), "fat_overlapping_other_frac": round(acc.get("fat_over", 0) / max(acc.get("fat_px", 0), 1), 4),
                                 "overlap_nonfat_frac": round(acc.get("over_nonfat", acc["overlap"]) / b, 4),
                                 "deep_spaces_cm2": {k: round(v * RES * RES / 100, 1) for k, v in sorted(spaces.items(), key=lambda x: -x[1])},
                                 "imaging_in_sub_void": {S_: round(float(cls_sub[i]) / max(cls_sub.sum(), 1), 3) for i, S_ in enumerate(("unknown", "air", "fat", "soft", "bone", "lung/gas"))},
                                 "imaging_in_deep_void": {S_: round(float(cls_deep[i]) / max(cls_deep.sum(), 1), 3) for i, S_ in enumerate(("unknown", "air", "fat", "soft", "bone", "lung/gas"))},
                                 "per_level": levels}
    return out


def montage(shots, path, title):
    from PIL import Image, ImageDraw
    cols = 6; th = 200
    tiles = []
    for rn, y, im in shots:
        h, w = im.shape[:2]; s = th / max(h, w)
        t = Image.fromarray(im).resize((max(1, int(w * s)), max(1, int(h * s))), Image.NEAREST)
        c = Image.new("RGB", (th, th + 14), (0, 0, 0)); c.paste(t, ((th - t.width) // 2, 14))
        ImageDraw.Draw(c).text((3, 1), f"{rn} y={y}", fill=(255, 255, 255)); tiles.append(c)
    rows = (len(tiles) + cols - 1) // cols
    M = Image.new("RGB", (cols * th, rows * (th + 14) + 18), (0, 0, 0))
    ImageDraw.Draw(M).text((4, 2), title + "   cyan = subcutaneous void, magenta = deep void, red = structure, gold = overlap, cream = fat (Q295), lilac = unlabelled soft tissue (Q295)", fill=(255, 255, 255))
    for i, t in enumerate(tiles):
        M.paste(t, ((i % cols) * th, 18 + (i // cols) * (th + 14)))
    M.save(path)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("key"); ap.add_argument("--tag", default="before"); ap.add_argument("--src"); ap.add_argument("--levels", type=int, default=30)
    ap.add_argument("--no-imaging", action="store_true"); ap.add_argument("--fat", action="store_true", help="add /dev/shm/q295/fat/KEY_fat.npz")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t = time.time(); pg = S.Page(a.key, a.src)
    if a.fat:
        z = np.load(f"/dev/shm/q295/fat/{a.key}_fat.npz"); us = sorted({k.split("__")[0] for k in z.files})
        pg.add([(u, "fat", u, z[u + "__v"], z[u + "__f"]) for u in us])
    orc = reg = None
    if not a.no_imaging:
        import oracle295 as O
        orc = O.make(BODY[a.key])
        if BODY[a.key] == "vhm" and a.key.startswith("base"):
            orc.precompute()
        if a.key.startswith("base"):
            import reg295 as RG
            reg = RG.fast(a.key, pg, RG.build(a.key, pg, S.Page(RG.PAIR[a.key])))
    shots = []
    r = analyse(pg, a.key, a.levels, orc, reg, shots)
    r["seconds"] = round(time.time() - t, 1)
    (OUT / f"{a.key}_{a.tag}.json").write_text(json.dumps(r, indent=1))
    montage(shots, OUT / f"{a.key}_{a.tag}.png", f"{a.key} ({a.tag})")
    for k, v in r["regions"].items():
        print(f"{a.key:7s} {k:10s} void {v['void_frac']:.3f} (sub {v['void_sub_frac']:.3f} deep {v['void_deep_frac']:.3f}) overlap {v['overlap_frac']:.3f} "
              f">5mm {v['holes_gt5mm']:4d} max {v['max_hole_diam_mm']:5.1f}  sub:fat {v['imaging_in_sub_void']['fat']:.2f} deep:fat {v['imaging_in_deep_void']['fat']:.2f} soft {v['imaging_in_deep_void']['soft']:.2f}")
    print("seconds", r["seconds"])


if __name__ == "__main__":
    main()
