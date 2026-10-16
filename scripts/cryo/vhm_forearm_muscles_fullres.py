"""Male RIGHT forearm muscles from his own full-resolution (0.33 mm) cryosection photographs, v2 (Q164 / queue Q62
"his forearm"). Rule-based; every structure badged. Supersedes nothing by itself: it writes subject ct_vhm_forearm_v2.

    python3 scripts/cryo/vhm_forearm_muscles_fullres.py --cryo SCRATCH/vh_cryo_m_forearm_q151 --work SCRATCH/q164_m_forearm

DATA. SCRATCH/vh_cryo_m_forearm_q151/cryo_1mm.npy: his whole photographs (IDC series 4aaf9181-..., 1216 x 2048 px,
0.33 mm/px, spine at the top, his left on the image right) at every 1 mm level, DICOM instances 1625..1761 (index in
cryo_index.json; streamed by scripts/cryo/vhm_stream_crops.py). Torso RAS z = 985 - instance; atlas y = 1880.476 -
instance; atlas = (x, z, y) - (-6.035, -895.476, 4.787) as every ct_vhm_* subject.

WHAT IS NEW AGAINST vhm_forearm_muscles_from_cryo.py (ct_vhm_forearm, 3 muscles shipped):
 1. His forearm is strongly OBLIQUE to the photographs (his CT radius runs 136 mm in x, 152 mm in y over 169 mm of z,
    ~50 deg from the slice normal), so the old per-photograph position rules were applied in sections stretched ~1.5x
    along one direction. Here the photographs are stacked into a 3-D volume in his torso RAS frame and RESLICED
    PERPENDICULAR to his forearm axis (principal axis of his CT radius + ulna labels); the rules act in true
    cross-sections.
 2. The split is ONE 3-D marker watershed per compartment (not 137 independent 2-D ones), so a boundary that is
    visible on some levels carries through the neighbouring ones.
 3. Registration without his torso CT (not stored): per photograph, the translation that lays the photographed radius
    and ulna (bone masks tracked in the photographs) on his CT radius/ulna sections (vhm_arm_bones_cryo_completed,
    labels 2/3), median-filtered over 21 levels; scale fixed at 0.33 mm/px, no rotation (the residual angle between the
    photographed and CT ulna->radius vectors is reported). Checked against the shipped radius_r / ulna_r meshes
    (build/vh/ct_vhm_arm): median distance from the photographed bone boundary to the mesh surface.
 4. Ship gate per muscle (repo rule): volume within 0.5x-2.0x of an expectation from a cited source AND one dominant
    piece (largest 26-connected component >= 0.98 of the volume left after dropping islands < 1 %).
    Expectation (per muscle): V = PCSA x optimal fascicle length / cos(pennation) from the repository's own
    architecture table data/muscles/upper_limb/<id>_r.json (each file names its source: Holzbaur, Murray & Delp 2005
    Ann Biomed Eng 33:829 for most; FDS/FDP/ED cite Gray's Anatomy for Students). Those are cadaver-architecture
    volumes; his measured forearm muscle total is several times their sum, so the gate uses them SIZE-NORMALISED:
    expected_i = V_i / sum(V) x (his total segmented forearm muscle), justified by Holzbaur, Murray, Gold & Delp 2007
    J Biomech 40:742 (doi:10.1016/j.jbiomech.2006.11.011; abstract): "the distribution of muscle volume in the upper
    limb is highly conserved across these subjects with a three-fold variation in total muscle volumes (1427-4426 cm3)".
    The raw (un-normalised) ratio is reported beside it.

RULES (textbook positions, not traced anatomy): her MARKER_RULES (vhf_forearm_muscles_from_cryo.py: mm from the bone
SURFACES in the ulna->radius frame, per f-window), offsets x --scale; her compartment rule (flexor / lateral / extensor
by the bone line); the septa = white top-hat (disk 4 px at 0.33 mm, i.e. ~1.3 mm) of the photograph brightness,
resampled with the photographs. Nothing here is anatomy traced by a person -- badge it.

Outputs: label volume (torso RAS, 0.5 mm grid, positive-determinant affine) in data/ct_sources/task_outputs/,
label key mappings/vhm_forearm_muscles_v2_labels.json, subject mapping mappings/subjects/ct_vhm_forearm_v2_volume_mapping.json,
report data/derived/Q164_vhm_forearm_fullres.json, montage PNG in --work.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pickle
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(Path(__file__).resolve().parent))

PX = 0.33                                        # mm per full-resolution photograph pixel
Z_OF_INST = 985.0                                # torso RAS z = 985 - instance
ORIGIN = (-6.035, -895.476, 4.787)               # atlas = (x, z, y) - ORIGIN
BONES_AFF = (350.0, 240.0, -1113.0)              # vhm_arm_bones: x = 350 - i, y = 240 - j, z = -1113 + k
BONE_ID = {"radius": 2, "ulna": 3}
BOX = (150, 1150, 50, 900)                       # full-res photograph rows r0:r1, cols c0:c1 holding his right forearm
BADGE = "rule-based"
SUBJECT = "ct_vhm_forearm_v2"
LABEL_MAP = "vhm_forearm_muscles_v2"
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): male cryosection photographs at "
          "full resolution (0.33 mm, IDC series 4aaf9181-fb6a-4a4c-bf49-d1eb9ed4a385, instances 1625-1761) and his CT "
          "radius/ulna labels (data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz) for registration. "
          "Derived data (scripts/cryo/vhm_forearm_muscles_fullres.py): rule-based segmentation (position-rule markers, "
          "3-D marker watershed on the pale fascial septa), not traced by an anatomist.")
HOLZBAUR_2007 = ("Holzbaur KR, Murray WM, Gold GE, Delp SL. Upper limb muscle volumes in adult subjects. J Biomech "
                 "2007;40(4):742-749. doi:10.1016/j.jbiomech.2006.11.011 (PubMed 17241636; abstract: muscle-volume "
                 "distribution highly conserved, three-fold variation in totals 1427-4426 cm3)")
MUSCLES = ["pronator_teres", "flexor_carpi_radialis", "palmaris_longus", "flexor_carpi_ulnaris",
           "flexor_digitorum_superficialis", "flexor_digitorum_profundus", "flexor_pollicis_longus", "pronator_quadratus",
           "brachioradialis", "extensor_carpi_radialis_longus", "extensor_carpi_radialis_brevis", "extensor_digitorum",
           "extensor_digiti_minimi", "extensor_carpi_ulnaris", "anconeus", "supinator", "abductor_pollicis_longus",
           "extensor_pollicis_brevis", "extensor_pollicis_longus", "extensor_indicis"]


# ----------------------------------------------------------------------------------------------- pure functions
def inst_to_z(inst):
    return Z_OF_INST - float(inst)


def photo_to_ras(pr, pc, X0, Y0):
    """Full-frame photograph px (row, col) -> torso RAS (x, y) at one level: x = X0 - col * PX, y = Y0 + row * PX
    (his photographs: column to the image right = RAS x decreasing, row down = RAS y increasing; the same convention
    as vhm_forearm_muscles_from_cryo.photo_to_ras)."""
    return X0 - np.asarray(pc, float) * PX, Y0 + np.asarray(pr, float) * PX


def ras_to_photo(x, y, X0, Y0):
    return (np.asarray(y, float) - Y0) / PX, (X0 - np.asarray(x, float)) / PX


def translation_from_bones(photo_rc, ct_xy):
    """Per-level (X0, Y0) that lays photographed bone centroids {name: (row, col)} on CT section centroids
    {name: (x, y)}: the mean over the bones present in both of (x + col*PX, y - row*PX)."""
    v = [(ct_xy[b][0] + photo_rc[b][1] * PX, ct_xy[b][1] - photo_rc[b][0] * PX) for b in photo_rc if b in ct_xy]
    if not v:
        return None
    return tuple(np.mean(np.asarray(v, float), axis=0))


def architecture_volume_cm3(compartments):
    """Sum over functional compartments of PCSA (mm2) x optimal fascicle length (mm) / cos(pennation) -> cm3
    (PCSA = V cos(alpha) / L_f, so V = PCSA L_f / cos(alpha)). Compartments lacking PCSA or length are skipped."""
    v = 0.0
    for c in compartments:
        fa = c.get("fiber_architecture", {}) or {}
        p, L = fa.get("physiological_cross_section_area_mm2"), fa.get("optimal_fascicle_length_mm")
        a = fa.get("pennation_deg") or 0.0
        if p and L:
            v += float(p) * float(L) / math.cos(math.radians(float(a))) / 1000.0
    return v


def normalised_expectations(raw, total):
    """expected_i = raw_i / sum(raw) * total (size normalisation; Holzbaur 2007: conserved distribution)."""
    s = float(sum(raw.values()))
    return {k: (v / s * total if s > 0 else 0.0) for k, v in raw.items()}


def main_component_fraction(mask, island_frac=0.01):
    """(fraction, n_components): largest 26-connected component over the volume left after dropping components
    smaller than island_frac of the whole mask."""
    from scipy import ndimage as ndi
    m = np.asarray(mask, bool)
    tot = int(m.sum())
    if tot == 0:
        return 0.0, 0
    lab, n = ndi.label(m, structure=np.ones((3,) * m.ndim, bool))
    sizes = np.bincount(lab.ravel())[1:]
    kept = sizes[sizes >= island_frac * tot]
    return float(kept.max() / kept.sum()), int(n)


def gate(v, expected, main_frac, lo=0.5, hi=2.0, min_main=0.98):
    """(ship: bool, reason: str) for the repo's ship gate."""
    if expected <= 0:
        return False, "no expectation"
    r = v / expected
    if not (lo <= r <= hi):
        return False, f"volume {v:.1f} cm3 is {r:.2f}x the expectation {expected:.1f} cm3 (gate {lo}-{hi}x)"
    if main_frac < min_main:
        return False, f"main component {main_frac:.3f} of the volume (< {min_main})"
    return True, f"{r:.2f}x the expectation, main component {main_frac:.3f}"


def expectations_from_repo(names=MUSCLES, side="r"):
    """{name: (raw cm3, source string)} from data/muscles/upper_limb/<name>_<side>.json."""
    out = {}
    for nm in names:
        d = json.load(open(REPO / "data/muscles/upper_limb" / f"{nm}_{side}.json"))
        comps = d.get("functional_compartments", [])
        srcs = sorted({(c.get("source") or "").split(" -- ")[0].strip() for c in comps if c.get("source")})
        out[nm] = (round(architecture_volume_cm3(comps), 2), "; ".join(srcs))
    return out


# ----------------------------------------------------------------------------------------------- photographs
class Photos:
    """His photographs through the forearm BOX, from one or more caches: a whole-frame cache (cryo_1mm.npy +
    cryo_index.json, as SCRATCH/vh_cryo_m_forearm_q151) and/or box crops written by vhm_stream_crops.py crop with
    --box = BOX (crops.npy + crops_bbox.json). Levels (DICOM instances) sorted ascending (proximal first)."""

    def __init__(self, *dirs):
        self.src = {}
        for d in map(Path, dirs):
            if (d / "cryo_1mm.npy").exists():
                a = np.load(d / "cryo_1mm.npy", mmap_mode="r")
                for k, row in enumerate(json.load(open(d / "cryo_index.json"))):
                    self.src[int(row[1])] = (a, k, True)
            elif (d / "crops.npy").exists():
                b = json.load(open(d / "crops_bbox.json"))
                if list(b["box"]) != list(BOX):
                    raise SystemExit(f"{d}: crop box {b['box']} is not BOX {BOX}")
                a = np.load(d / "crops.npy", mmap_mode="r")
                for k, inst in enumerate(b["levels"]):
                    self.src.setdefault(int(inst), (a, k, False))
        self.levels = sorted(self.src); self.n = len(self.levels)

    def crop(self, j):
        a, k, whole = self.src[self.levels[j]]
        if whole:
            r0, r1, c0, c1 = BOX
            return np.asarray(a[k, r0:r1, c0:c1])
        return np.asarray(a[k])


def forearm_island(c, prev=None):
    """His forearm's tissue in one crop (classify codes), separated from the trunk it lies against.
    prev None (first level, forearm free): the tissue component with the leftmost centroid among those >= 20000 px.
    Otherwise: the smallest erosion (0..60 px) at which the component under the previous island's core is at most
    1.15x the previous island's area; grown back inside the tissue, each pixel kept only when nearer to that component
    than to any other eroded component."""
    from scipy import ndimage as ndi
    t0 = ndi.binary_fill_holes(ndi.binary_closing(c > 0, iterations=2))
    if prev is None:
        lab, n = ndi.label(t0); sizes = np.bincount(lab.ravel())[1:]
        big = [i + 1 for i in range(n) if sizes[i] >= 20000]
        cols = {i: np.mean(np.where(lab == i)[1]) for i in big}
        return lab == min(cols, key=cols.get)
    core = ndi.binary_erosion(prev, iterations=25) if prev.sum() > 40000 else prev
    area = prev.sum()
    raw = ndi.binary_fill_holes(c > 0)                                  # unclosed tissue: the skin-to-skin contact line stays open
    for k in (0, 1, 2, 3, 5, 8, 12, 16):                                # opened k px to break a thin contact, grown back
        t = ndi.binary_opening(raw, iterations=k) if k else raw
        lab, n = ndi.label(t)
        if not n:
            continue
        ov = np.bincount(lab[core], minlength=n + 1); ov[0] = 0; i = int(np.argmax(ov))
        if not ov[i]:
            continue
        g = lab == i
        if k:
            others = (lab > 0) & ~g
            d_me = ndi.distance_transform_edt(~g); d_ot = ndi.distance_transform_edt(~others) if others.any() else np.full(g.shape, np.inf)
            g = raw & (d_me <= k + 1) & (d_me < d_ot)
        if 0.8 * area <= g.sum() <= 1.15 * area:
            return ndi.binary_fill_holes(ndi.binary_closing(g, iterations=2))
    for it in (0, 3, 6, 10, 14, 20, 28, 36, 48, 60):
        t = ndi.binary_erosion(t0, iterations=it) if it else t0
        lab, n = ndi.label(t)
        if n == 0:
            continue
        ov = np.bincount(lab[core], minlength=n + 1); ov[0] = 0
        i = int(np.argmax(ov))
        if ov[i] == 0:
            continue
        comp = lab == i
        if it:
            d_me = ndi.distance_transform_edt(~comp)
            others = (lab > 0) & ~comp
            d_ot = ndi.distance_transform_edt(~others) if others.any() else np.full(comp.shape, np.inf)
            g = t0 & (d_me <= it + 2) & (d_me < d_ot)
            lab2, _ = ndi.label(g); g = lab2 == lab2[tuple(np.argwhere(comp)[0])]
        else:
            g = comp
        g = ndi.binary_fill_holes(g)
        if g.sum() <= 1.15 * area:
            return g
    return None


def bright_filled(c, isl, marrow_mm2=400.0):
    """fat | pale | white inside the island, closed 2 px, holes <= marrow_mm2 filled (his cream marrow, white cortex)."""
    from scipy import ndimage as ndi
    p0 = ndi.binary_closing(np.isin(c, (2, 4, 5)) & isl, iterations=2)
    holes = ndi.binary_fill_holes(p0) & ~p0; hl, hn = ndi.label(holes)
    if hn:
        hs = ndi.sum(holes, hl, range(1, hn + 1)); small = np.zeros(hn + 1, bool); small[1:] = np.asarray(hs) * PX * PX <= marrow_mm2
        p0 = p0 | small[hl]
    return p0


def find_bone(bright, isl, pred, search_mm, skin_mm=6.0, min_r_mm=3.0, exclude=None):
    """The largest circle inscribed in `bright` whose centre lies within search_mm of pred (row, col) and >= skin_mm
    inside the island; its bone = the bright component holding that centre, clipped to 1.8x the circle radius around
    the circle-to-component axis (so subcutaneous fat touching a bone is not taken). Returns (cy, cx, r, mask) or None."""
    from scipy import ndimage as ndi
    b = bright & ~exclude if exclude is not None else bright
    dt = ndi.distance_transform_edt(b); dist = ndi.distance_transform_edt(isl)
    yy, xx = np.mgrid[0:b.shape[0], 0:b.shape[1]]
    win = (np.hypot(yy - pred[0], xx - pred[1]) * PX <= search_mm) & (dist * PX >= skin_mm)
    if not win.any():
        return None
    v = np.where(win, dt, -1.0); cy, cx = np.unravel_index(int(np.argmax(v)), v.shape); r = float(dt[cy, cx])
    if r * PX < min_r_mm:
        return None
    lab, _ = ndi.label(b); comp = lab == lab[cy, cx]
    # the bone: pixels of the component whose own inscribed radius is >= 0.45 r grown back by that radius
    core = comp & (dt >= 0.45 * r)
    lab2, _ = ndi.label(core); core = lab2 == lab2[cy, cx]
    m = ndi.binary_dilation(core, iterations=int(round(0.45 * r)) + 1) & comp
    return float(cy), float(cx), r, ndi.binary_fill_holes(m)


def ct_sections(bones, z):
    """{name: (x, y centroid, (xs, ys) of the section voxels)} of his CT radius/ulna label at RAS z."""
    k = int(round(z - BONES_AFF[2])); out = {}
    if not (0 <= k < bones.shape[2]):
        return out
    for b, l in BONE_ID.items():
        ii, jj = np.where(bones[:, :, k] == l)
        if len(ii):
            x = BONES_AFF[0] - ii; y = BONES_AFF[1] - jj
            out[b] = (float(x.mean()), float(y.mean()), x, y)
    return out


def islands(ph, anchor_inst=1625, log=print):
    """Pass 1: the forearm island per level, tracked both ways from anchor_inst where the forearm lies free of the
    trunk. Returns {j: bool mask}."""
    from cryo_classes import classify
    ja = ph.levels.index(anchor_inst); out = {ja: forearm_island(classify(ph.crop(ja)), None)}
    for rng in (range(ja - 1, -1, -1), range(ja + 1, ph.n)):
        prev = out[ja]
        for j in rng:
            isl = forearm_island(classify(ph.crop(j)), prev)
            if isl is None:
                log(f"  level {ph.levels[j]}: island lost; stops"); break
            out[j] = isl; prev = isl
    return out


def seed_pair(br, isl, ct):
    """Two strongest inscribed circles in the bright class (>= 15 mm apart, >= 6 mm inside the skin), assigned
    ulna/radius by the orientation matching his CT ulna->radius vector. Returns ({ulna, radius: (row, col)}, photo
    distance mm, CT distance mm)."""
    from scipy import ndimage as ndi
    v = ndi.distance_transform_edt(br) * (ndi.distance_transform_edt(isl) * PX >= 6.0); pk = []
    yy, xx = np.mgrid[0:v.shape[0], 0:v.shape[1]]
    for _ in range(2):
        cy, cx = np.unravel_index(int(np.argmax(v)), v.shape); pk.append((int(cy), int(cx)))
        v[np.hypot(yy - cy, xx - cx) * PX < 15.0] = 0
    ctv = np.array([ct["radius"][0] - ct["ulna"][0], ct["radius"][1] - ct["ulna"][1]]); best = None
    for ui, ri in ((0, 1), (1, 0)):
        d = np.array([-(pk[ri][1] - pk[ui][1]) * PX, (pk[ri][0] - pk[ui][0]) * PX]); s = float(np.dot(ctv, d))
        if best is None or s > best[0]:
            best = (s, ui, ri, float(np.hypot(*d)))
    return {"ulna": pk[best[1]], "radius": pk[best[2]]}, best[3], float(np.hypot(*ctv))


def track(ph, bones, isl_by_level, anchor_inst=1700, log=print, lost_max=8):
    """Pass 2: photographed radius/ulna from the anchor level both ways (search 5 mm + 2 mm per lost level), their
    masks, centroids (full-frame px) and the raw per-level translation onto his CT sections."""
    from scipy import ndimage as ndi
    from cryo_classes import classify
    r0, _, c0, _ = BOX; out = {}
    def one(j, prev, lost, first=False):
        c = classify(ph.crop(j)); isl = isl_by_level[j]; br = bright_filled(c, isl); z = inst_to_z(ph.levels[j])
        ct = ct_sections(bones, z); rec = {"inst": ph.levels[j], "z": z, "ct": {b: v[:2] for b, v in ct.items()}}
        found = {}; masks = {}; excl = np.zeros(isl.shape, bool)
        for b in ("ulna", "radius"):
            h = find_bone(br, isl, prev[b], 6.0 if first else 5.0 + 2.0 * lost[b], exclude=excl)
            if h is None:
                continue
            found[b] = (h[0], h[1], h[2]); masks[b] = h[3]; excl |= ndi.binary_dilation(h[3], iterations=3)
        rec["found"] = found; rec["bone_masks"] = masks
        cen = {b: tuple(np.mean(np.where(m), axis=1) + [r0, c0]) for b, m in masks.items()}
        rec["photo_centroid_full"] = cen; rec["T_raw"] = translation_from_bones(cen, rec["ct"])
        return rec
    anchor = ph.levels.index(anchor_inst)
    c = classify(ph.crop(anchor)); ct = ct_sections(bones, inst_to_z(ph.levels[anchor]))
    pair, dp, dc = seed_pair(bright_filled(c, isl_by_level[anchor]), isl_by_level[anchor], ct)
    log(f"  anchor {ph.levels[anchor]}: photo ulna-radius {dp:.1f} mm, CT {dc:.1f} mm")
    out[anchor] = one(anchor, pair, {"radius": 0, "ulna": 0}, first=True)
    for rng in (range(anchor - 1, -1, -1), range(anchor + 1, ph.n)):
        prev = {b: out[anchor]["found"][b][:2] for b in ("radius", "ulna")}; lost = {"radius": 0, "ulna": 0}
        for j in rng:
            if j not in isl_by_level:
                break
            r = one(j, prev, lost)
            for b in ("radius", "ulna"):
                if b in r["found"]:
                    prev[b] = r["found"][b][:2]; lost[b] = 0
                else:
                    lost[b] += 1
            out[j] = r
            if max(lost.values()) > lost_max:
                log(f"  level {ph.levels[j]}: a bone lost > {lost_max} levels; track ends"); break
            if j % 20 == 0:
                log(f"  level {ph.levels[j]}: bones {sorted(r['found'])} T {None if r['T_raw'] is None else np.round(r['T_raw'], 1).tolist()}")
    return out


# ----------------------------------------------------------------------------------------------- registration
def smooth_translation(tr, n, pair_tol_mm=3.0, size=21):
    """Per-level (X0, Y0): the raw bone translation at the RELIABLE levels (both bones found, photographed
    ulna-radius distance within pair_tol_mm of the CT's), median-filtered over `size` reliable levels, linearly
    interpolated between them and held constant beyond. Returns ({j: (X0, Y0)}, reliable level list)."""
    from scipy import ndimage as ndi
    rel = []
    for j in sorted(tr):
        r = tr[j]; pc = r.get("photo_centroid_full", {}); ct = r["ct"]
        if r.get("T_raw") is None or not all(b in pc and b in ct for b in ("radius", "ulna")):
            continue
        dp = np.hypot(pc["radius"][0] - pc["ulna"][0], pc["radius"][1] - pc["ulna"][1]) * PX
        dc = np.hypot(ct["radius"][0] - ct["ulna"][0], ct["radius"][1] - ct["ulna"][1])
        if abs(dp - dc) <= pair_tol_mm:
            rel.append(j)
    if not rel:
        raise SystemExit("no reliable registration level")
    arr = np.array([tr[j]["T_raw"] for j in rel], float); k = min(size, len(rel))
    sm = np.stack([ndi.median_filter(arr[:, i], size=k, mode="nearest") for i in range(2)], 1)
    return {j: (float(np.interp(j, rel, sm[:, 0])), float(np.interp(j, rel, sm[:, 1]))) for j in range(n)}, rel


def rotation_residual_deg(tr, rel):
    """Median |angle| between the photographed and the CT ulna->radius vectors over the reliable levels (the
    registration is translation-only; this is what a rotation would have had to fix)."""
    a = []
    for j in rel:
        pc = tr[j]["photo_centroid_full"]; ct = tr[j]["ct"]
        vp = np.array([-(pc["radius"][1] - pc["ulna"][1]), pc["radius"][0] - pc["ulna"][0]])
        vc = np.array([ct["radius"][0] - ct["ulna"][0], ct["radius"][1] - ct["ulna"][1]])
        a.append(abs(math.degrees(math.atan2(vp[0] * vc[1] - vp[1] * vc[0], float(np.dot(vp, vc))))))
    return float(np.median(a)) if a else None


# ----------------------------------------------------------------------------------------------- 3-D stacks
def build_stack(ph, isl_by_level, T, log=print):
    """The photographs laid into one torso-RAS stack at the photograph's own pixel (PX in x and y, 1 mm in z): each
    level shifted by its registration (whole px; <= 0.17 mm rounding). Returns dict: muscle, island (bool),
    tophat (float16; white top-hat, disk 4 px, of the brightness = the pale septa), grid (Xg0, Yg0, z of level 0)."""
    from skimage.morphology import white_tophat, disk
    from cryo_classes import classify
    r0, _, c0, _ = BOX; js = sorted(isl_by_level)
    ext = []
    for j in js:
        rr, cc = np.where(isl_by_level[j]); x, y = photo_to_ras([rr.min() + r0, rr.max() + r0], [cc.min() + c0, cc.max() + c0], *T[j])
        ext.append((x.min(), x.max(), y.min(), y.max()))
    ext = np.array(ext); Xg0 = ext[:, 1].max() + 1.0; Yg0 = ext[:, 2].min() - 1.0
    nr = int(np.ceil((ext[:, 3].max() + 1.0 - Yg0) / PX)) + 1; nc = int(np.ceil((Xg0 - ext[:, 0].min() + 1.0) / PX)) + 1
    nz = len(js); muscle = np.zeros((nz, nr, nc), bool); island = np.zeros((nz, nr, nc), bool); th = np.zeros((nz, nr, nc), np.float16)
    for k, j in enumerate(js):
        im = ph.crop(j); c = classify(im); isl = isl_by_level[j]
        t = white_tophat(im.max(-1).astype(np.float32), disk(4))
        dr = int(round((T[j][1] - Yg0) / PX)) + r0; dc = int(round((Xg0 - T[j][0]) / PX)) + c0   # grid row = r + dr, col = c + dc
        rr, cc = np.where(isl); gr = rr + dr; gc = cc + dc; ok = (gr >= 0) & (gr < nr) & (gc >= 0) & (gc < nc)
        rr, cc, gr, gc = rr[ok], cc[ok], gr[ok], gc[ok]
        island[k, gr, gc] = True; muscle[k, gr, gc] = c[rr, cc] == 3; th[k, gr, gc] = t[rr, cc]
    log(f"  stack {nz} x {nr} x {nc} (PX {PX} mm in-plane)")
    return {"muscle": muscle, "island": island, "tophat": th, "grid": (float(Xg0), float(Yg0), inst_to_z(ph.levels[js[0]])), "levels": [ph.levels[j] for j in js]}


def stack_index(x, y, z, grid):
    """Torso RAS -> fractional stack index (k, row, col)."""
    Xg0, Yg0, zt = grid
    return zt - np.asarray(z, float), (np.asarray(y, float) - Yg0) / PX, (Xg0 - np.asarray(x, float)) / PX


def forearm_axis(bones, zlo, zhi):
    """(centre, unit axis pointing distally = towards decreasing z) of his CT radius + ulna voxels between zlo and zhi
    (principal axis)."""
    ii, jj, kk = np.where(np.isin(bones, list(BONE_ID.values())))
    x = BONES_AFF[0] - ii; y = BONES_AFF[1] - jj; z = BONES_AFF[2] + kk
    m = (z >= zlo) & (z <= zhi); P = np.stack([x[m], y[m], z[m]], 1).astype(float); c = P.mean(0)
    a = np.linalg.svd(P - c, full_matrices=False)[2][0]
    if a[2] > 0:
        a = -a
    return c, a


def frame_basis(a):
    """In-plane orthonormal (v1, v2) perpendicular to the axis a: v1 = RAS x made perpendicular, v2 = a x v1."""
    v1 = np.array([1.0, 0, 0]) - a[0] * a; v1 /= np.linalg.norm(v1); v2 = np.cross(a, v1)
    return v1, v2


def reslice(arrays, grid, c, a, u_rng, st_half, du=1.0, ds=0.5, orders=None):
    """Sample stack arrays on planes perpendicular to the forearm axis: point = c + u a + s v1 + t v2 with u in
    u_rng (step du), s, t in [-st_half, st_half] (step ds). Returns ({name: (nu, ns, nt) array}, (us, ss, ts))."""
    from scipy.ndimage import map_coordinates
    v1, v2 = frame_basis(a); us = np.arange(u_rng[0], u_rng[1] + 1e-6, du); ss = np.arange(-st_half, st_half + 1e-6, ds); ts = ss
    S, Tt = np.meshgrid(ss, ts, indexing="ij"); out = {k: np.zeros((len(us), len(ss), len(ts)), v.dtype) for k, v in arrays.items()}
    for i, u in enumerate(us):
        P = c[None, None, :] + u * a + S[..., None] * v1 + Tt[..., None] * v2
        k, r, cc = stack_index(P[..., 0], P[..., 1], P[..., 2], grid)
        for name, arr in arrays.items():
            o = (orders or {}).get(name, 0)
            out[name][i] = map_coordinates(arr, [k, r, cc], order=o, mode="constant", cval=0).astype(arr.dtype) if o else \
                map_coordinates(arr.astype(np.uint8) if arr.dtype == bool else arr, [k, r, cc], order=0, mode="constant", cval=0).astype(arr.dtype)
    return out, (us, ss, ts)


def reslice_bones(bones, c, a, us, ss, ts):
    """His CT radius/ulna labels sampled on the forearm-frame planes (nearest)."""
    from scipy.ndimage import map_coordinates
    v1, v2 = frame_basis(a); S, Tt = np.meshgrid(ss, ts, indexing="ij"); out = np.zeros((len(us), len(ss), len(ts)), np.uint8)
    for i, u in enumerate(us):
        P = c[None, None, :] + u * a + S[..., None] * v1 + Tt[..., None] * v2
        out[i] = map_coordinates(bones, [BONES_AFF[0] - P[..., 0], BONES_AFF[1] - P[..., 1], P[..., 2] - BONES_AFF[2]], order=0, mode="constant", cval=0)
    return out


# ----------------------------------------------------------------------------------------------- rules in true cross-sections
GROUP_ID = {"flexor": 1, "lateral": 2, "extensor": 3}


def her_rules(scale):
    """Her MARKER_RULES (vhf_forearm_muscles_from_cryo.py) with the mm offsets x scale."""
    from vhf_forearm_muscles_from_cryo import MARKER_RULES
    return {nm: (anc, em * scale, n_ * scale, f0, f1, g) for nm, (anc, em, n_, f0, f1, g) in MARKER_RULES.items()}


def bone_frame(U, R, skin_dir_at_ulna):
    """e: unit ulna -> radius; n: its perpendicular pointing AWAY from the ulna's nearest skin (the flexor side)."""
    U = np.asarray(U, float); R = np.asarray(R, float); e = R - U; d = float(np.hypot(*e))
    if d < 1e-6:
        raise ValueError("coincident bones")
    e = e / d; n = np.array([-e[1], e[0]])
    if np.dot(n, np.asarray(skin_dir_at_ulna, float)) > 0:
        n = -n
    return e, n, d


def marker_positions(U, R, ru, rr, e, n, f, rules, px_mm):
    """Rule seeds {name: (row, col)} px for level fraction f; offsets are mm from the anchor bone's SURFACE."""
    U = np.asarray(U, float); R = np.asarray(R, float); M = (U + R) / 2; out = {}
    for name, (anc, em, nm, f0, f1, _g) in rules.items():
        if not (f0 <= f <= f1):
            continue
        base = {"U": U, "R": R, "M": M}[anc]; rad = {"U": ru, "R": rr, "M": 0.0}[anc]
        ev = em / px_mm + (np.sign(em) * rad if em else 0.0); nv = nm / px_mm + (np.sign(nm) * rad if nm else 0.0)
        out[name] = tuple(base + e * ev + n * nv)
    return out


def compartments(shape, U, R, ru, rr, e, n, px_mm):
    """Her bone-line compartment rule (vhf_forearm_muscles_from_cryo.compartments) at pixel size px_mm."""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]; py = yy - U[0]; px = xx - U[1]; d = np.hypot(R[0] - U[0], R[1] - U[1])
    s = (py * e[0] + px * e[1]) / d; t = (py * n[0] + px * n[1]) * px_mm
    lat = (s > 1.0) & (t > -(rr * px_mm + 14.0))
    flex = ((t > 0) | ((s < 0) & (t > -ru * px_mm))) & ~lat
    comp = np.full(shape, GROUP_ID["extensor"], np.uint8); comp[lat] = GROUP_ID["lateral"]; comp[flex] = GROUP_ID["flexor"]
    return comp


def snap(pt, region, max_px):
    r, c = int(round(pt[0])), int(round(pt[1]))
    if 0 <= r < region.shape[0] and 0 <= c < region.shape[1] and region[r, c]:
        return r, c
    r0, c0 = max(r - max_px, 0), max(c - max_px, 0); win = region[r0:r + max_px + 1, c0:c + max_px + 1]
    if not win.any():
        return None
    ys, xs = np.where(win); ys = ys + r0; xs = xs + c0; k = int(np.argmin(np.hypot(ys - r, xs - c)))
    return (int(ys[k]), int(xs[k])) if np.hypot(ys[k] - r, xs[k] - c) <= max_px else None


# superficial ring (textbook cross-section order round the forearm, Gray's Anatomy: from the ulna's subcutaneous
# border anteriorly FCU, FDS/PL, FCR, (PT proximally), BR, then posteriorly ECRL, ECRB, ED, EDM, ECU back to the
# ulna): name -> (angle deg in the bone frame: 0 = +e towards the radius, 90 = +n the flexor side, 180 = -e,
# 270 = -n; depth = fraction of the way from the muscle surface (0) to the bone-pair midpoint (1)). Rule parameters,
# not measurements. The other muscles keep her bone-relative MARKER_RULES.
RING = {
    "flexor_carpi_ulnaris":           (150.0, 0.25),
    "flexor_digitorum_superficialis": (110.0, 0.50),
    "palmaris_longus":                (95.0, 0.15),
    "flexor_carpi_radialis":          (65.0, 0.25),
    "pronator_teres":                 (40.0, 0.45),
    "brachioradialis":                (10.0, 0.25),
    "extensor_carpi_radialis_longus": (-15.0, 0.30),
    "extensor_carpi_radialis_brevis": (-40.0, 0.30),
    "extensor_digitorum":             (-80.0, 0.25),
    "extensor_digiti_minimi":         (-110.0, 0.25),
    "extensor_carpi_ulnaris":         (-140.0, 0.25),
}


def ring_positions(M, e, n, surf_dist, f, rules, ring=RING):
    """Seeds {name: (row, col)} for the RING muscles active at f (her f-windows): along the ray at the ring angle
    from M, at depth fraction of the muscle surface distance surf_dist(theta_deg) (px) from the surface."""
    out = {}
    for nm, (ang, dep) in ring.items():
        f0, f1 = rules[nm][3], rules[nm][4]
        if not (f0 <= f <= f1):
            continue
        th = math.radians(ang); v = math.cos(th) * np.asarray(e, float) + math.sin(th) * np.asarray(n, float)
        D = surf_dist(ang)
        if D is None:
            continue
        out[nm] = tuple(np.asarray(M, float) + v * D * (1.0 - dep))
    return out


def ray_surface(mask, M, e, n, ang, step=0.5):
    """Distance (px) from M along the ray at angle ang (bone frame) to the last pixel of `mask` on it."""
    th = math.radians(ang); v = math.cos(th) * np.asarray(e, float) + math.sin(th) * np.asarray(n, float); last = None
    for k in range(1, 800):
        p = np.asarray(M, float) + v * k * step; r, c = int(round(p[0])), int(round(p[1]))
        if not (0 <= r < mask.shape[0] and 0 <= c < mask.shape[1]):
            break
        if mask[r, c]:
            last = k * step
    return last


def segment_frame(F, rules, ds=0.5, seed_mm=1.7, snap_mm=5.0, mode="ring", compactness=0.0, log=print):
    """3-D marker watershed in the forearm frame. F: dict with island, muscle, tophat, B (CT bones) arrays
    (nu, ns, nt) and us. Returns (labels, info) with info: per-slice frame (U, R, e, n, f) and the segment u range."""
    from scipy import ndimage as ndi
    from skimage.segmentation import watershed
    isl, mus, th, B, us = F["island"], F["muscle"], F["tophat"], F["B"], F["us"]
    has = [(B[i] == 2).sum() > 20 and (B[i] == 3).sum() > 20 for i in range(len(us))]
    rad_u = [i for i in range(len(us)) if (B[i] == 2).sum() > 20]
    i_top, i_bot = min(rad_u), max(rad_u)                        # radial head .. distal radius along the axis
    names = list(rules); ids = {nm: k + 1 for k, nm in enumerate(names)}
    markers = np.zeros(isl.shape, np.int32); comp = np.zeros(isl.shape, np.uint8); region = np.zeros(isl.shape, bool)
    frames = {}; flips = 0; rpx = max(1, int(round(seed_mm / ds))); geo = {}
    for i in range(i_top, i_bot + 1):                            # pass 1: the skin rule per slice
        if not has[i] or not isl[i].any():
            continue
        U = np.array(ndi.center_of_mass(B[i] == 3)); R = np.array(ndi.center_of_mass(B[i] == 2))
        ru = math.sqrt((B[i] == 3).sum() / math.pi); rr = math.sqrt((B[i] == 2).sum() / math.pi)
        dist, idx = ndi.distance_transform_edt(isl[i], return_indices=True)
        ys, xs = np.where(B[i] == 3); k = int(np.argmin(dist[ys, xs])); skin = np.array([idx[0][ys[k], xs[k]], idx[1][ys[k], xs[k]]], float) - U
        complete = not ndi.binary_erosion(isl[i], iterations=1).sum() < 0.5 * isl[i].sum() and \
            not (isl[i][0].any() or isl[i][-1].any() or isl[i][:, 0].any() or isl[i][:, -1].any())
        geo[i] = (U, R, ru, rr) + bone_frame(U, R, skin) + (complete,)
    # the flexor side: the skin rule on the slices whose cross-section is whole (not cut by the photographed range),
    # as a sign relative to e rotated +90 deg; the majority sign is applied to every slice
    votes = [np.sign(np.dot(g[5], np.array([-g[4][1], g[4][0]]))) for g in geo.values() if g[7]]
    # the skin rule is near a coin toss in these sections (votes reported); the flexor side is taken as the side of
    # the bone line holding MORE muscle, summed over the whole sections (flexors outweigh extensors in every
    # forearm), and checked against his CT thumb metacarpal (report: orientation)
    side = [0.0, 0.0]
    for i, g in geo.items():
        if not g[7]:
            continue
        U, e = g[0], g[4]; nn = np.array([-e[1], e[0]]); yy, xx = np.mgrid[0:isl.shape[1], 0:isl.shape[2]]
        tt = (yy - U[0]) * nn[0] + (xx - U[1]) * nn[1]; m = mus[i] & isl[i]
        side[0] += float((m & (tt > 0)).sum()); side[1] += float((m & (tt < 0)).sum())
    sign = 1.0 if side[0] >= side[1] else -1.0
    for i, (U, R, ru, rr, e, n, d, complete) in geo.items():
        n2 = sign * np.array([-e[1], e[0]]); flips += int(np.dot(n2, n) < 0); geo[i] = (U, R, ru, rr, e, n2, d, complete)
    for i in sorted(geo):                                        # pass 2: compartments, seeds
        U, R, ru, rr, e, n, d, complete = geo[i]; f = (i - i_top) / max(i_bot - i_top, 1)
        reg = ndi.binary_closing(mus[i], iterations=2) & isl[i]
        holes = ndi.binary_fill_holes(reg) & ~reg; hl, hn = ndi.label(holes)
        if hn:
            hs = np.asarray(ndi.sum(holes, hl, range(1, hn + 1))) * ds * ds; small = np.zeros(hn + 1, bool); small[1:] = hs <= 8.0; reg |= small[hl]
        reg &= ~ndi.binary_dilation(B[i] > 0, iterations=2)
        region[i] = reg; comp[i] = compartments(reg.shape, U, R, ru, rr, e, n, ds)
        seeds = marker_positions(U, R, ru, rr, e, n, f, rules, ds); placed = {}
        if mode == "ring":
            M = (U + R) / 2; body = ndi.binary_fill_holes(reg | ndi.binary_dilation(B[i] > 0, iterations=2))
            seeds.update(ring_positions(M, e, n, lambda ang: ray_surface(body, M, e, n, ang), f, rules))
        for nm, pt in seeds.items():
            g = GROUP_ID[rules[nm][5]]; allowed = reg if mode == "ring" else reg & (comp[i] == g)
            p = snap(pt, allowed & (markers[i] == 0), int(round(snap_mm / ds)))
            if p is None:
                continue
            placed[nm] = p
            z = np.zeros(reg.shape, bool); z[p] = True
            markers[i][ndi.binary_dilation(z, iterations=rpx) & allowed & (markers[i] == 0)] = ids[nm]
        frames[i] = {"u": float(us[i]), "f": round(f, 3), "U": U.tolist(), "R": R.tolist(), "e": e.tolist(), "n": n.tolist(), "d_mm": round(d * ds, 1), "whole": bool(complete),
                     "seeds": {k: [int(v[0]), int(v[1])] for k, v in placed.items()}}
    lab = np.zeros(isl.shape, np.uint8)
    if mode == "ring":                                           # one watershed over the whole muscle mass
        ws = watershed(th, markers, mask=region, compactness=compactness); lab[ws > 0] = ws[ws > 0]
    for g, gid in (GROUP_ID.items() if mode != "ring" else ()):
        m = region & (comp == gid); mk = np.where(m, markers, 0)
        mk[~np.isin(mk, [ids[nm] for nm in names if rules[nm][5] == g])] = 0
        if not mk.any():
            continue
        ws = watershed(th, mk, mask=m); lab[ws > 0] = ws[ws > 0]
    log(f"  segment slices {i_top}..{i_bot} (u {us[i_top]:.0f}..{us[i_bot]:.0f} mm), skin-rule votes {int(sum(v > 0 for v in votes))}+/{int(sum(v < 0 for v in votes))}-, slices overruled {flips}")
    return lab, {"ids": ids, "frames": frames, "i_top": i_top, "i_bot": i_bot, "flips": flips, "votes": [int(sum(v > 0 for v in votes)), int(sum(v < 0 for v in votes))],
                 "flexor_over_extensor_muscle_area": round(max(side) / max(min(side), 1.0), 2), "region": region, "comp": comp}


def thumb_check(bones, info, c, a):
    """His CT thumb metacarpal against the flexor normal of the most distal whole section (the old script's
    thumb_side rule: the thumb = the metacarpal component farthest from the line through the others, at the axial
    level with the most components). Returns dict or None."""
    from scipy import ndimage as ndi
    from vhm_forearm_muscles_from_cryo import thumb_side
    whole = [i for i, fr in info["frames"].items() if fr["whole"]]
    if not whole:
        return None
    fr = info["frames"][max(whole)]; v1, v2 = frame_basis(a); n3 = fr["n"][0] * v1 + fr["n"][1] * v2; n_ras = n3[:2]
    best = None
    for k in range(bones.shape[2]):
        m = bones[:, :, k] == 10
        if m.sum() < 50:
            continue
        lab, nc = ndi.label(m)
        if nc < 4:
            continue
        sizes = ndi.sum(m, lab, range(1, nc + 1)); keep = [i + 1 for i, sz in enumerate(sizes) if sz >= 10]
        if len(keep) < 4:
            continue
        cents = [ndi.center_of_mass(lab == i) for i in keep]; P = np.array([[BONES_AFF[0] - q[0], BONES_AFF[1] - q[1]] for q in cents])
        off, ti = thumb_side(P, n_ras)
        if best is None or len(keep) > best["n_components"]:
            best = {"z": float(BONES_AFF[2] + k), "n_components": len(keep), "thumb_offset_mm_along_flexor_normal": round(off, 1)}
    return best


def boundary_support_3d(lab, th, ids, i_range, min_contact_px=15):
    """Per adjacent pair, per slice (the repo's pale-line score, vhf_forearm_muscles_from_cryo.boundary_support):
    mean top-hat on the 1 px contact band / mean top-hat 2 px inside the two regions. Returns
    {"a|b": {levels, median_ridge_ratio, frac_levels_ratio_ge_1.8}} for pairs sharing >= 5 slices."""
    from scipy import ndimage as ndi
    inv = {v: k for k, v in ids.items()}; acc = {}
    for i in range(*i_range):
        L = lab[i]; present = [l for l in np.unique(L) if l]
        er = {l: ndi.binary_erosion(L == l, iterations=2) for l in present}; dl = {l: ndi.binary_dilation(L == l) for l in present}
        for x, a in enumerate(present):
            for b in present[x + 1:]:
                band = (dl[a] & (L == b)) | (dl[b] & (L == a))
                if band.sum() < min_contact_px:
                    continue
                inside = er[a] | er[b]
                if not inside.any():
                    continue
                r = float(th[i][band].mean() / max(th[i][inside].mean(), 1e-3))
                acc.setdefault(tuple(sorted((inv[a], inv[b]))), []).append(r)
    return {f"{a}|{b}": {"levels": len(v), "median_ridge_ratio": round(float(np.median(v)), 2),
                         "frac_levels_ratio_ge_1.8": round(float(np.mean([x >= 1.8 for x in v])), 2)}
            for (a, b), v in sorted(acc.items()) if len(v) >= 5}


def septum_support_per_muscle(support, names, min_frac=0.7):
    """Per muscle: the share of its boundary pairs (by shared slices) that run on a pale line at >= min_frac of
    slices, and the list of weak pairs (the repo's ship_or_merge criterion, vhm_forearm_muscles_from_cryo)."""
    out = {}
    for nm in names:
        pairs = [(k, v) for k, v in support.items() if nm in k.split("|")]
        weak = [k for k, v in pairs if v["frac_levels_ratio_ge_1.8"] < min_frac]
        out[nm] = {"pairs": len(pairs), "weak_pairs": weak, "all_on_pale_line": bool(pairs) and not weak}
    return out


# ----------------------------------------------------------------------------------------------- registration check
def load_subject_meshes(subject_dir, ids):
    """{atlas_id: (vertices (n,3), faces (m,3))} from a build/vh subject (manifest.json, vertices.f32, faces.u32)."""
    d = Path(subject_dir); m = json.load(open(d / "manifest.json"))
    V = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3); Fc = np.fromfile(d / "faces.u32", np.uint32).reshape(-1, 3)
    out = {}
    for s in m["structures"]:
        if s["atlas_id"] in ids:
            v0, nv, f0, nf = s["vertex_offset"], s["vertex_count"], s["face_offset"], s["triangle_count"]
            out[s["atlas_id"]] = (V[v0:v0 + nv].astype(float), Fc[f0:f0 + nf].astype(np.int64) - v0)
    return out


def ras_to_atlas(x, y, z):
    return np.stack([np.asarray(x, float) - ORIGIN[0], np.asarray(z, float) - ORIGIN[1], np.asarray(y, float) - ORIGIN[2]], -1)


def registration_check(ph, tr, T, meshes, rel, n_surface=400000):
    """Median distance (mm) from the photographed radius/ulna boundary (all tracked levels, laid by the smoothed
    registration) to the shipped radius_r / ulna_r mesh surfaces; also split into levels used for the fit (reliable)
    and the rest."""
    import trimesh
    from scipy import ndimage as ndi
    from scipy.spatial import cKDTree
    r0, _, c0, _ = BOX; trees = {}
    for b in ("radius", "ulna"):
        v, f = meshes[f"{b}_r"]; pts, _ = trimesh.sample.sample_surface_even(trimesh.Trimesh(v, f, process=False), n_surface, seed=0)
        trees[b] = cKDTree(pts)
    dist = {"all": [], "fit_levels": [], "other_levels": []}; per_bone = {"radius": [], "ulna": []}
    for j, r in tr.items():
        for b, m in r.get("bone_masks", {}).items():
            edge = m & ~ndi.binary_erosion(m); rr, cc = np.where(edge)
            x, y = photo_to_ras(rr + r0, cc + c0, *T[j]); P = ras_to_atlas(x, y, np.full(len(x), r["z"]))
            d, _ = trees[b].query(P); dist["all"] += d.tolist(); per_bone[b] += d.tolist()
            dist["fit_levels" if j in rel else "other_levels"] += d.tolist()
    out = {k: {"n_points": len(v), "median_mm": round(float(np.median(v)), 2), "p90_mm": round(float(np.percentile(v, 90)), 2)} for k, v in dist.items() if v}
    out["per_bone_median_mm"] = {b: round(float(np.median(v)), 2) for b, v in per_bone.items() if v}
    return out


# ----------------------------------------------------------------------------------------------- outputs
def frame_to_ras_volume(lab, us, ss, ts, c, a, dx=0.5):
    """Frame labels -> one torso-RAS grid (dx in x/y, 1 mm in z; nearest). Returns (vol, affine)."""
    v1, v2 = frame_basis(a); du = us[1] - us[0]; ds = ss[1] - ss[0]
    iu, is_, it = np.where(lab > 0); sub = slice(None, None, 7)
    P = c + us[iu[sub], None] * a + ss[is_[sub], None] * v1 + ts[it[sub], None] * v2
    lo = np.floor(P.min(0)) - 2; hi = np.ceil(P.max(0)) + 2
    gx = np.arange(lo[0], hi[0] + 1e-6, dx); gy = np.arange(lo[1], hi[1] + 1e-6, dx); gz = np.arange(lo[2], hi[2] + 1e-6, 1.0)
    vol = np.zeros((len(gx), len(gy), len(gz)), np.uint8); X, Y = np.meshgrid(gx, gy, indexing="ij")
    for k, z in enumerate(gz):
        Q = np.stack([X - c[0], Y - c[1], np.full(X.shape, z - c[2])], -1)
        u = Q @ a; s = Q @ v1; t = Q @ v2
        ku = np.rint((u - us[0]) / du).astype(int); ks = np.rint((s - ss[0]) / ds).astype(int); kt = np.rint((t - ts[0]) / ds).astype(int)
        ok = (ku >= 0) & (ku < lab.shape[0]) & (ks >= 0) & (ks < lab.shape[1]) & (kt >= 0) & (kt < lab.shape[2])
        sl = np.zeros(X.shape, np.uint8); sl[ok] = lab[ku[ok], ks[ok], kt[ok]]; vol[:, :, k] = sl
    aff = np.array([[dx, 0, 0, gx[0]], [0, dx, 0, gy[0]], [0, 0, 1.0, gz[0]], [0, 0, 0, 1]])
    return vol, aff


def badge_text(nm, v, exp_n, exp_raw, septa_frac):
    return (f"Rule-based segmentation from his own cryosection photographs (Visible Human male, 0.33 mm, instances "
            f"1575-1819): position-rule markers relative to his radius/ulna and a 3-D compact marker watershed on the "
            f"pale fascial septa; its boundaries run on a visible pale septum at {round(100 * septa_frac)} % of shared "
            f"slices, elsewhere they are rule lines, not traced anatomy. Measured volume {v:.1f} cm3 vs expectation "
            f"{exp_n:.1f} cm3 (repository architecture volume {exp_raw:.1f} cm3, PCSA x fascicle length, size-normalised "
            f"to his forearm total per Holzbaur et al. 2007). Only the part between his radial-head and distal-radius "
            f"planes is segmented.")


def stamp_badges(subject_dir, mapping_path):
    """Write each mapping entry's 'procedural_badge' onto the matching structure of the converted manifest (the field
    scripts/export_viewer_bundle.py carries into the viewer)."""
    m = json.load(open(mapping_path)); bad = {e["atlas_id"]: e.get("procedural_badge") for e in m["entries"] if e.get("atlas_id")}
    p = Path(subject_dir) / "manifest.json"; man = json.load(open(p)); n = 0
    for s in man["structures"]:
        if bad.get(s["atlas_id"]):
            s["procedural_badge"] = bad[s["atlas_id"]]; n += 1
    p.write_text(json.dumps(man, indent=1))
    return n


def montage(F, lab, info, path, slices):
    from PIL import Image, ImageDraw
    from vhf_forearm_muscles_from_cryo import palette
    p = palette(len(info["ids"])); col = np.array([p[k] for k in range(len(info["ids"]) + 1)], np.uint8); outs = []
    for i in slices:
        th = np.clip(F["tophat"][i] * 5, 0, 255).astype(np.uint8); im = np.stack([th] * 3, -1)
        L = lab[i]; ov = im.copy()
        for l in range(1, len(info["ids"]) + 1):
            ov[L == l] = col[l]
        im = (0.55 * ov + 0.45 * im).astype(np.uint8); im[F["B"][i] == 2] = 255; im[F["B"][i] == 3] = 170
        pil = Image.fromarray(im); d = ImageDraw.Draw(pil); fr = info["frames"].get(i)
        if fr:
            d.text((3, 3), f"u {fr['u']:.0f} mm f {fr['f']}", fill=(255, 255, 0))
        outs.append(np.asarray(pil))
    Image.fromarray(np.concatenate(outs, 1)).save(path)
    return str(path)


def main(argv=None):
    import nibabel as nib
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cryo", nargs="+", help="photograph caches (whole-frame q151 cache and/or BOX crops)")
    ap.add_argument("--work", help="scratch folder for stage caches and the montage")
    ap.add_argument("--bones", default=str(REPO / "data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz"))
    ap.add_argument("--bone-meshes", default=str(REPO / "build/vh/ct_vhm_arm"))
    ap.add_argument("--scale", type=float, default=1.15, help="factor on her deep-marker mm offsets (as vhm_forearm_muscles_from_cryo)")
    ap.add_argument("--compactness", type=float, default=0.05)
    ap.add_argument("--out", default=str(REPO / "data/ct_sources/task_outputs/vhm_forearm_muscles_fullres.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / f"mappings/{LABEL_MAP}_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / f"mappings/subjects/{SUBJECT}_volume_mapping.json"))
    ap.add_argument("--report", default=str(REPO / "data/derived/Q164_vhm_forearm_fullres.json"))
    ap.add_argument("--stamp", default=None, help="only stamp badges from --mapping-out onto this converted subject dir")
    a = ap.parse_args(argv)
    if a.stamp:
        print(f"stamped {stamp_badges(a.stamp, a.mapping_out)} badges"); return 0
    if not (a.cryo and a.work):
        ap.error("--cryo and --work are required unless --stamp")
    W = Path(a.work); W.mkdir(parents=True, exist_ok=True)
    ph = Photos(*a.cryo); bones = np.asanyarray(nib.load(a.bones).dataobj)
    print(f"{ph.n} levels {ph.levels[0]}..{ph.levels[-1]}")
    p = W / "isl.pkl"
    isl = pickle.load(open(p, "rb")) if p.exists() else islands(ph)
    pickle.dump(isl, open(p, "wb"), protocol=4)
    p = W / "track.pkl"
    tr = pickle.load(open(p, "rb")) if p.exists() else track(ph, bones, isl)
    pickle.dump(tr, open(p, "wb"), protocol=4)
    T, rel = smooth_translation(tr, ph.n)
    p = W / "frame.npz"
    if p.exists():
        F = dict(np.load(p))
    else:
        st = build_stack(ph, isl, T); c, ax = forearm_axis(bones, -810, -600)
        R, (us, ss, ts) = reslice({"muscle": st["muscle"], "island": st["island"], "tophat": st["tophat"].astype(np.float32)}, st["grid"], c, ax, (-150, 170), 60, orders={"tophat": 1})
        del st
        F = dict(R, B=reslice_bones(bones, c, ax, us, ss, ts), us=us, ss=ss, ts=ts, c=c, a=ax); np.savez_compressed(p, **F)
    rules = her_rules(a.scale)
    lab, info = segment_frame(F, rules, compactness=a.compactness)
    ids = info["ids"]; names = list(ids)
    vol, aff = frame_to_ras_volume(lab, F["us"], F["ss"], F["ts"], F["c"], F["a"])
    vox = float(abs(np.linalg.det(aff[:3, :3])))
    vols = {nm: round(float((vol == l).sum() * vox / 1000.0), 1) for nm, l in ids.items()}
    total = float(sum(vols.values()))
    ex = expectations_from_repo(names); exp_n = normalised_expectations({k: v[0] for k, v in ex.items()}, total)
    support = boundary_support_3d(lab, F["tophat"], ids, (info["i_top"], info["i_bot"] + 1))
    rows = {}
    for nm, l in ids.items():
        mf, ncomp = main_component_fraction(vol == l)
        ok, why = gate(vols[nm], exp_n[nm], mf)
        pr = [v for k, v in support.items() if nm in k.split("|")]; w = sum(v["levels"] for v in pr)
        sep = sum(v["levels"] * v["frac_levels_ratio_ge_1.8"] for v in pr) / max(w, 1)
        rows[nm] = {"label": l, "volume_cm3": vols[nm], "expected_cm3": round(exp_n[nm], 1), "ratio": round(vols[nm] / exp_n[nm], 2),
                    "architecture_volume_cm3": ex[nm][0], "raw_ratio": round(vols[nm] / ex[nm][0], 2), "expectation_source": ex[nm][1],
                    "main_component_fraction": round(mf, 4), "components_26": ncomp, "septum_supported_fraction": round(sep, 2),
                    "ship": ok, "reason": why}
        print(f"  {nm:32s} {vols[nm]:6.1f} cm3  exp {exp_n[nm]:6.1f}  x{vols[nm] / exp_n[nm]:.2f}  main {mf:.3f}  septa {sep:.2f}  {'SHIP' if ok else '-'}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); nib.save(nib.Nifti1Image(vol, aff), a.out)
    q = [int(info["i_top"] + (info["i_bot"] - info["i_top"]) * t) for t in (0.1, 0.3, 0.5, 0.7, 0.9)]
    mont = montage(F, lab, info, W / "vhm_forearm_fullres_montage.png", q)
    regc = registration_check(ph, tr, T, load_subject_meshes(a.bone_meshes, ["radius_r", "ulna_r"]), rel)
    thumb = thumb_check(bones, info, F["c"], F["a"])
    key = {"_README": [f"Label id -> structure for the Visible Human MALE right forearm muscle volume v2 ({Path(__file__).name}). A KEY, not data. {BADGE}."],
           "source": SOURCE, "task": LABEL_MAP, "version": "2026-09-29", "badge": BADGE, "labels": {str(l): nm for nm, l in ids.items()}}
    Path(a.labels_out).write_text(json.dumps(key, indent=1))
    entries = []
    for nm, r in rows.items():
        b = badge_text(nm, r["volume_cm3"], r["expected_cm3"], r["architecture_volume_cm3"], r["septum_supported_fraction"])
        e = {"label": r["label"], "source_structure": nm, "side": "right", "relationship": "exact", "candidates": [nm + "_r"]}
        if r["ship"]:
            e.update(status="curated", atlas_id=nm + "_r", procedural_badge=b, note=f"{BADGE}; SHIPPED: {r['reason']}. Expectation source: {r['expectation_source']}.")
        else:
            e.update(status="review", atlas_id=None, note=f"{BADGE}; NOT SHIPPED: {r['reason']}. Expectation source: {r['expectation_source']}.")
        entries.append(e)
    Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only. 'procedural_badge' is stamped onto the converted manifest by this script's --stamp."],
                                                "subject": SUBJECT, "source_volume": str(Path(a.out).resolve()), "label_map": LABEL_MAP, "entries": entries}, indent=2))
    report = {"source": SOURCE, "badge": BADGE, "script": "scripts/cryo/vhm_forearm_muscles_fullres.py", "subject": SUBJECT,
              "levels": [ph.levels[0], ph.levels[-1]], "scale": a.scale, "compactness": a.compactness,
              "forearm_axis": {"centre_ras": np.round(F["c"], 1).tolist(), "unit": np.round(F["a"], 3).tolist(),
                               "angle_from_slice_normal_deg": round(float(np.degrees(np.arccos(abs(F["a"][2])))), 1)},
              "segment": {"u_mm": [float(F["us"][info["i_top"]]), float(F["us"][info["i_bot"]])], "rule": "radial head .. distal radius of his CT radius label along the axis"},
              "registration": {"method": "per-photograph translation laying the photographed radius/ulna on his CT sections, median over 21 reliable levels",
                               "reliable_levels": [ph.levels[j] for j in (rel[0], rel[-1])], "n_reliable": len(rel),
                               "rotation_residual_deg_median": rotation_residual_deg(tr, rel),
                               "bone_boundary_to_ct_vhm_arm_mesh": regc},
              "orientation": {"flexor_side_rule": "side of the bone line with more muscle (whole sections)", "skin_rule_votes_plus_minus": info["votes"],
                              "flexor_over_extensor_muscle_area": info["flexor_over_extensor_muscle_area"], "thumb_metacarpal": thumb},
              "expectations": {"rule": "V = PCSA x optimal fascicle length / cos(pennation), data/muscles/upper_limb/<id>_r.json, size-normalised to his total",
                               "normalisation_citation": HOLZBAUR_2007, "his_total_cm3": round(total, 1),
                               "architecture_total_cm3": round(sum(v[0] for v in ex.values()), 1)},
              "gate": "0.5 <= volume/expected <= 2.0 and main 26-connected component >= 0.98 of the volume left after dropping islands < 1 %",
              "muscles": rows, "boundary_support": support, "montage": mont,
              "shipped": [nm + "_r" for nm, r in rows.items() if r["ship"]]}
    Path(a.report).parent.mkdir(parents=True, exist_ok=True); Path(a.report).write_text(json.dumps(report, indent=1))
    print(f"shipped {len(report['shipped'])}: {report['shipped']}")
    print(f"registration: {json.dumps(regc)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
