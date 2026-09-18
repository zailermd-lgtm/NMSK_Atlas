"""Female suprahyoid, infrahyoid and extrinsic tongue muscles from her registered 1 mm cryosection frame (Q62 step 7a).
Rule-based; badged.

    python3 scripts/cryo/vhf_hyoid_muscles_from_cryo.py            # writes the volume, key, mapping, report, montage
    python3 scripts/cryo/vhf_hyoid_muscles_from_cryo.py --frame-dir SCRATCH/vh_cryo_f --out data/ct_sources/task_outputs

DATA (all hers). The z-corrected 1 mm frame of her colour cryosections in her torso-CT frame (cryo_frame_rgb.npy /
cryo_frame_cls.npy, frame.json: z = z0 + k; RAS x = 350 - col, y = 240 - row; a CT slice kk = z0 + k - z_ct0 of a
volume with affine A is laid into the frame at col = 350 - A[0,3] + |A[0,0]| i, row = 240 - A[1,3] + |A[1,1]| j -- for her
torso grid the columns 110..590 at 480/512 of vhf_deep_neck_from_cryo.py, for her head grid (0.488 mm, origin 125)
the columns 225..475) and her TotalSegmentator labels as anchors: `headneck_bones_vessels` (hyoid, thyroid and cricoid
cartilages, larynx air, styloid processes, carotids, jugulars), `headneck_muscles_merged` (SCM, platysma, constrictors,
sternothyroid, thyrohyoid, scalenes, prevertebral: all exclusions), `total` (vertebrae, skull, thyroid gland, trachea,
oesophagus, sternum, clavicles: exclusions and level anchors), `head_muscles` (the TONGUE label as the tongue mass, split
by rules; digastric, masseter, pterygoids as exclusions) and `craniofacial_structures` (mandible, teeth). Her digastric
is already shipped from the head_muscles CT task (ct_vhf_headm) and is not re-derived.

Her frozen muscle photographs dark and brown (cryo_classes_f: class 3), her glands (submandibular, sublingual, thyroid)
and fat pale (class 2) and the gelatin blue (class 0), so muscle = the closed muscle class under a brightness cap; the
muscle boundaries come from her CT labels and from the pale fascial septa of the photographs: marker watershed on the
white top-hat (disk 4 px) of the brightness, as vhf_deep_neck_from_cryo.py.

RULES (Standring, Gray's Anatomy 42nd ed., ch. 29 'Neck' (infrahyoid and suprahyoid muscles) and ch. 30 'Oral cavity'
(extrinsic muscles of the tongue); Moore, Clinically Oriented Anatomy 8th ed., ch. 9 'Neck' and ch. 8 'Head'), per
1 mm level, per side:
  STRAP compartment (the manubrium's top - 5 mm, or the first level with both SCM labels, .. the hyoid body's lower
    border): muscle within 15 mm in front of the anterior surface of the larynx / thyroid gland / trachea / carotid
    sheath / prevertebral column (anterior to the larynx's centre), deep to the platysma and the subcutaneous fat
    (skin depth > 6 mm, platysma label out), medial of 40 mm (18 mm below the omohyoid's crossing), the SCM label out. Depth fraction f from the
    compartment's anterior (0) to posterior (1) surface in each column; dx mm lateral of the visceral midline.
    sternohyoid = the superficial medial strap: dx < 14 mm (20 mm below the cricoid, where the two diverge) and
      f < 0.5 at levels with a thyroid cartilage or below it (the deep layer there is sternothyroid / thyrohyoid,
      shipped from the CT task: a SINK 'deep_strap', not shipped), full depth medially above the cartilage (the
      thyrohyoid is lateral: dx > 8 mm deep is the sink there);
    omohyoid (superior belly and its course under the SCM) = the superficial strap lateral of the sternohyoid,
      running down-and-lateral: dx >= 14 mm (+0.6 mm per mm below the cricoid's lower end) and f < 0.5; the
      inferior belly across the posterior triangle to the scapula is NOT attempted (a 2-3 mm band in fat at 1 mm).
  FLOOR compartment (the hyoid body + 1 .. the lower alveolar margin + 3 mm): muscle inside the mandibular arch
    (between the arch's inner surfaces; below the body the arch 10 mm above the mandible's lower border is carried down), anterior to the
    hyoid / pharynx / vertebra / vessels, the tongue label out (dilated 1 mm), the digastric label out, glands out
    (pale). d_out = distance to what is not floor muscle on the outer side (mandible, digastric, fat, gland, gelatin;
    the tongue and the posterior labels do not count); g = AP fraction of the column from the arch (0) to the
    posterior boundary (1).
    mylohyoid = the outer layer (d_out <= 5 mm) on the mandible (within 15 mm of it) and, below the mental spine
      level, the sling's anterior half (g < 0.5);
    geniohyoid = paramedian (dx < 9 mm), deeper than the mylohyoid, at levels up to the mental spine (the mandible's
      lower border + 12 mm); genioglossus = paramedian (dx < 12 mm) above the mental spine level;
    hyoglossus = the sagittal sheet lateral of the genioglossus: dx 13-21 mm, posterior (g >= 0.45), deeper than the mylohyoid;
    floor_lateral = the remainder (sublingual region, the lateral tongue root, the gland's deep part): a SINK, not shipped.
  TONGUE (the tongue label's levels; dxT mm lateral of the label's own centroid, gT its AP fraction, zT its height
    fraction): genioglossus = the paramedian fan dxT < 10 mm, gT > 0.25, below the dorsum's 8 mm; hyoglossus = the
    lateral lower posterior side (dxT >= 10, gT > 0.5, zT < 0.4); styloglossus = the lateral posterior side above it
    (dxT >= 15, gT > 0.55, zT >= 0.5, below the dorsum's 8 mm); tongue_intrinsic = the rest: a SINK, not shipped.
  CORRIDORS from the styloid process (per side, its label's lowest level): stylohyoid = a 5 mm disc along the line
    from the styloid to the hyoid at the junction of its body and greater horn (Gray's: with the posterior belly of
    the digastric, which it splits around -- the two are one band at 1 mm), levels above the hyoid body;
    styloglossus = a 5 mm disc along the line from the styloid's anterior face to the side of the tongue at 0.55 of
    its height (its posterior third), levels above that; muscle-dark, not gland, the labels out.
  septum support = for each adjacent pair inside a compartment, the mean top-hat on the 1 px boundary band over the
    mean 2 px inside (boundary_support of the deep-neck script), contact-weighted over all levels: a pair whose
    boundary is not a pale ridge (ratio < MERGE_RATIO) is MERGED into a named compartment and mapped to null.
NOT attempted: the intrinsic tongue muscles, palatoglossus, the palate, the pharynx (constrictors are shipped from
the CT task) and the larynx -- too small or without a septum at 1 mm; the omohyoid's inferior belly (see above).
Output: label volume (RAS 1 mm, frame affine) for `ingest_volume_geometry.py convert`, label key, subject mapping,
report (volumes, merges, levels, septum support, literature comparison), montage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
SCRATCH = "/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
FRAME_DIR = SCRATCH + "vh_cryo_f/"
TASK_DIR = REPO / "data/ct_sources/task_outputs"
BADGE = "rule-based"
VERSION = "2026-09-14"
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female colour cryosections "
          "(1 mm frame) and CT via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 `total`, `headneck_muscles`, "
          "`headneck_bones_vessels`, `head_muscles` (tongue, digastric) and `craniofacial_structures` (mandible) labels as "
          "anchors. Rules from Standring S (ed.), Gray's Anatomy, 42nd ed., ch. 29 'Neck' and ch. 30 'Oral cavity', and "
          "Moore KL et al., Clinically Oriented Anatomy, 8th ed., ch. 8 'Head' and ch. 9 'Neck'. Derived data "
          "(scripts/cryo/vhf_hyoid_muscles_from_cryo.py), rule-based.")

# ---- the rules -------------------------------------------------------------------------------------------------------
DARK_V = 135               # her frozen muscle: 3 px-mean brightness below this (glands and fat above)
MIN_HOLE_PX, MIN_PART_PX = 80, 30
MARKER_ERODE_PX = 2
MERGE_RATIO = 1.25
# strap
STRAP_BELOW_STERNUM_TOP_MM = 5
STRAP_LAT_MM = 40
STRAP_SKIN_MM = 6
STRAP_DEPTH_MM = 15                      # the strap layer is at most this thick in front of the visceral front
STRAP_LAT_LOW_MM = 18                    # below the omohyoid's crossing the straps are within this of the midline
OMO_BELOW_CRIC_MM = 10                   # the omohyoid is followed to this far below the cricoid (its tendon under the SCM)
STRAP_TOP_ABOVE_HYOID_MM = 2             # the strap band ends at the hyoid body's lower border
MH_MAND_MM = 15                          # the mylohyoid sheet stays within this of the mandible, or in the anterior half
MIN_MERGE_CONTACT_PX = 100
SH_W_MM, SH_W_LOW_MM = 14.0, 20.0       # sternohyoid half-width: above / below the cricoid's lower end
OMO_SLOPE = 0.6                          # omohyoid's medial edge moves 0.6 mm lateral per mm below the cricoid
DEEP_F = 0.5                             # the deep half of the strap column = sternothyroid / thyrohyoid (sink)
TH_LAT_MM = 8.0                          # above the thyroid cartilage the deep sink (thyrohyoid) is lateral of this
# floor
MH_T_MM = 5.0
GH_W_MM, GG_W_MM = 9.0, 12.0
GH_ABOVE_MAND_MM = 12                    # the mental spine above the mandible's lower border
HG_G = 0.45
HG_DX_MM = (13.0, 21.0)                  # hyoglossus: the sagittal sheet lateral of the genioglossus, in an axial cut a band at this dx
ARCH_ABOVE_MM = 10                       # the arch carried below the mandible is the body's arch this far above its lower border
STRAP_MIN_PART_PX = 12
SCM_MIN_PX = 100                         # the strap band starts where both SCM labels are at least this big
FLOOR_LAT_MM = 30
FLOOR_ABOVE_ALV_MM = 3
# tongue
GG_T_W_MM, HG_T_W_MM, SG_T_W_MM = 10.0, 10.0, 15.0
GG_T_G, HG_T_G, SG_T_G = 0.25, 0.5, 0.55
HG_T_Z, SG_T_Z = 0.4, 0.5
DORSUM_MM = 8
# corridors
COR_R_MM = 5.0
SG_TONGUE_Z = 0.55
STYLOID_ANT_MM = 3

STRAP = ("sternohyoid", "omohyoid", "deep_strap")
FLOOR = ("mylohyoid", "geniohyoid", "genioglossus", "hyoglossus", "floor_lateral")
TONGUE = ("genioglossus", "hyoglossus", "styloglossus", "tongue_intrinsic")
CORRIDOR = ("stylohyoid", "styloglossus")
MUSCLES = ("sternohyoid", "omohyoid", "mylohyoid", "geniohyoid", "genioglossus", "hyoglossus", "styloglossus",
           "stylohyoid", "deep_strap", "floor_lateral", "tongue_intrinsic")
SINKS = {"deep_strap": "sink for the deep strap layer (sternothyroid / thyrohyoid, shipped from the CT task as ct_vhf_neck; "
                       "their CT labels are also excluded); keeps that layer out of the sternohyoid",
         "floor_lateral": "sink for the anterolateral floor lateral of the geniohyoid / genioglossus (sublingual region, "
                          "lateral genioglossus fibres); not a target",
         "tongue_intrinsic": "sink for the intrinsic tongue (superior / inferior longitudinal, transverse, vertical) and the "
                             "palatoglossus: no septa at 1 mm, out of scope"}
COMPARTMENTS = {"stylohyoid": ["stylohyoid", "digastric"]}     # the corridor carries the posterior digastric belly: not shipped by name
ATLAS_OF = {nm: (None if (nm in SINKS or nm in COMPARTMENTS) else nm) for nm in MUSCLES}
GROUPS = {"strap": ("sternohyoid", "omohyoid"), "floor": ("mylohyoid", "geniohyoid", "genioglossus", "hyoglossus"),
          "tongue": ("genioglossus", "hyoglossus", "styloglossus"), "corridor": ("stylohyoid", "styloglossus")}
# label ids
VERT_IDS = list(range(41, 51)); SKULL = 91; THYROID_GLAND, TRACHEA, OESOPHAGUS, STERNUM = 17, 16, 15, 116
BV_HYOID, BV_THYC, BV_CRIC, BV_AIR = 3, 2, 4, 1
BV_STYLOID = {"right": 7, "left": 8}
BV_VESSELS = [9, 10, 11, 12]
NK_SCM = {"right": 1, "left": 2}; NK_PLAT = [8, 9]; NK_CONSTR = [3, 4, 5]; NK_ALL = list(range(1, 24))
HM_TONGUE = 9; HM_DIG = [10, 11]; HM_OTHER = list(range(1, 9))
CF_MANDIBLE = 1; CF_TEETH = [2, 7]


def strap_rules(dx, f, comp, below_cric_mm, has_thyc_or_below):
    """{muscle: mask} in the strap compartment: sternohyoid medial superficial, omohyoid lateral superficial (moving
    lateral below the cricoid), the deep layer a sink where a thyroid cartilage is present or below it (all dx) and
    above it only lateral of TH_LAT_MM."""
    sh_w = SH_W_LOW_MM if below_cric_mm > 0 else SH_W_MM
    omo_edge = sh_w + OMO_SLOPE * max(below_cric_mm, 0)
    deep = (f >= DEEP_F) & ((dx > TH_LAT_MM) if not has_thyc_or_below else True)
    out = {"deep_strap": comp & deep, "sternohyoid": comp & ~deep & (dx < omo_edge), "omohyoid": comp & ~deep & (dx >= omo_edge)}
    if below_cric_mm > OMO_BELOW_CRIC_MM:                 # under the SCM and beyond: the inferior belly is not attempted
        out["sternohyoid"] |= out.pop("omohyoid")
    return {k: v for k, v in out.items() if v.any()}


def floor_rules(dx, g, d_out, comp, above_spine, d_mand=None):
    """{muscle: mask} in the floor compartment (see the docstring)."""
    mh = comp & (d_out <= MH_T_MM)
    if d_mand is not None:                   # the sheet stays on the mandible; its sling crosses the floor only below the mental spine
        mh &= (d_mand <= MH_MAND_MM) | ((g < 0.5) & (not above_spine))
    deep = comp & ~mh
    w = GG_W_MM if above_spine else GH_W_MM
    para = deep & (dx < w)
    hg = deep & (dx >= max(w, HG_DX_MM[0])) & (dx < HG_DX_MM[1]) & (g >= HG_G)
    out = {"mylohyoid": mh, ("genioglossus" if above_spine else "geniohyoid"): para, "hyoglossus": hg,
           "floor_lateral": deep & ~para & ~hg}
    return {k: v for k, v in out.items() if v.any()}


def tongue_rules(dxT, gT, zT, below_dorsum, T):
    """{muscle: mask} inside the tongue label: genioglossus paramedian fan, hyoglossus lateral lower posterior,
    styloglossus lateral upper posterior, the rest intrinsic (sink)."""
    gg = T & below_dorsum & (dxT < GG_T_W_MM) & (gT > GG_T_G)
    hg = T & ~gg & (dxT >= HG_T_W_MM) & (gT > HG_T_G) & (zT < HG_T_Z)
    sg = T & ~gg & ~hg & below_dorsum & (dxT >= SG_T_W_MM) & (gT > SG_T_G) & (zT >= SG_T_Z)
    out = {"genioglossus": gg, "hyoglossus": hg, "styloglossus": sg, "tongue_intrinsic": T & ~gg & ~hg & ~sg}
    return {k: v for k, v in out.items() if v.any()}


def corridor_centre(a, b, k, ka, kb):
    """Point on the line a (at level ka) -> b (at level kb) at level k, as (row, col)."""
    t = (k - ka) / max(kb - ka, 1)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def merge_decision(support, ratio=MERGE_RATIO):
    merged = {}
    for pair, obs in support.items():
        w = sum(n for n, _ in obs)
        if w == 0:
            continue
        r = sum(n * q for n, q in obs) / w
        merged[pair] = (round(r, 2), int(w), bool(r < ratio and w >= MIN_MERGE_CONTACT_PX))
    return merged


def split_region(th, region, rules, ids):
    from scipy import ndimage as ndi
    from skimage.segmentation import watershed
    markers = np.zeros(region.shape, np.int32)
    for name, m in rules.items():
        core = ndi.binary_erosion(m, iterations=MARKER_ERODE_PX)
        if core.sum() < 10:
            core = ndi.binary_erosion(m, iterations=1)
        if core.sum() < 10:
            core = m
        markers[core & (markers == 0)] = ids[name]
    if not markers.any():
        return {}
    ws = watershed(th, markers, mask=region)
    return {name: ws == l for name, l in ids.items() if (ws == l).any()}


def boundary_support(th, cur, min_contact_px=15):
    from scipy import ndimage as ndi
    out = {}; names = list(cur)
    er = {nm: ndi.binary_erosion(cur[nm], iterations=2) for nm in names}
    dil = {nm: ndi.binary_dilation(cur[nm], iterations=1) for nm in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            band = (dil[a] & cur[b]) | (dil[b] & cur[a]); nb = int(band.sum())
            if nb < min_contact_px:
                continue
            inside = er[a] | er[b]
            ratio = float(th[band].mean() / max(th[inside].mean(), 1e-3)) if inside.any() else 0.0
            out[tuple(sorted((a, b)))] = (nb, round(ratio, 2))
    return out


def merge_groups(pairs):
    pairs = [p for p in pairs if not (set(p) & set(SINKS))]
    groups = []
    for a, b in pairs:
        ga = next((g for g in groups if a in g), None); gb = next((g for g in groups if b in g), None)
        if ga is None and gb is None:
            groups.append({a, b})
        elif ga is None:
            gb.add(a)
        elif gb is None:
            ga.add(b)
        elif ga is not gb:
            ga |= gb; groups.remove(gb)
    return [frozenset(g) for g in groups]


def group_name(g):
    if g == {"sternohyoid", "omohyoid"}:
        return "infrahyoid_superficial_group"
    if g <= {"mylohyoid", "geniohyoid", "genioglossus", "hyoglossus"}:
        return "floor_of_mouth_group" if len(g) > 2 else "_".join(sorted(g)) + "_compartment"
    return "_".join(sorted(g)) + "_compartment"


def relabel(ids, groups):
    final = []; taken = set()
    for nm in MUSCLES:
        g = next((g for g in groups if nm in g), None)
        if g is None:
            final.append((nm, [nm]))
        elif g not in taken:
            taken.add(g); final.append((group_name(g), sorted(g)))
    labels = {}
    for si, side in enumerate(("right", "left")):
        for i, (nm, members) in enumerate(final):
            labels[si * len(final) + i + 1] = (f"{nm}_{side}", nm, members, side)
    lut_r = np.zeros(len(MUSCLES) + 1, np.uint8); lut_l = np.zeros(len(MUSCLES) + 1, np.uint8)
    for lid, (_, nm, members, side) in labels.items():
        for m in members:
            (lut_r if side == "right" else lut_l)[ids[m]] = lid
    return final, labels, lut_r, lut_l


# ---- the data ---------------------------------------------------------------------------------------------------------
class Frame:
    def __init__(self, frame_dir, task_dir):
        import nibabel as nib
        d = Path(frame_dir)
        self.cls = np.load(d / "cryo_frame_cls.npy", mmap_mode="r"); self.rgb = np.load(d / "cryo_frame_rgb.npy", mmap_mode="r")
        self.z0 = float(json.load(open(d / "frame.json"))["z0"]); self.n, self.H, self.W = self.cls.shape
        def load(name):
            im = nib.load(str(Path(task_dir) / name)); return np.asarray(im.dataobj), im.affine
        self.tot, self.aT = load("vhf_total.nii.gz"); self.neck, self.aN = load("vhf_headneck_muscles_merged.nii.gz")
        self.bv, self.aB = load("vhf_headneck_bones_vessels.nii.gz"); self.hm, self.aH = load("vhf_head_muscles.nii.gz")
        self.cf, self.aC = load("vhf_craniofacial_structures.nii.gz")
        self._cache = {}

    def ct(self, arr, aff, k):
        """CT slice at frame level k laid into the frame (any grid: scale |A[0,0]| mm, origin A[:,3])."""
        from scipy import ndimage as ndi
        key = (id(arr), k)
        if key in self._cache:
            return self._cache[key]
        kk = int(round(self.z0 + k - aff[2, 3])); f = np.zeros((self.H, self.W), np.int32)
        if 0 <= kk < arr.shape[2]:
            sc = abs(float(aff[0, 0])); n = arr.shape[0]; w = int(round(n * sc))
            c0 = int(round(350 - aff[0, 3])); r0 = int(round(240 - aff[1, 3]))
            z = ndi.zoom(arr[:, :, kk], w / n, order=0).T
            rr = slice(max(r0, 0), min(r0 + w, self.H)); cc = slice(max(c0, 0), min(c0 + w, self.W))
            f[rr, cc] = z[rr.start - r0:rr.stop - r0, cc.start - c0:cc.stop - c0]
        if len(self._cache) > 40:
            self._cache.clear()
        self._cache[key] = f
        return f

    def k_of(self, aff, kk):
        return int(round(aff[2, 3] + kk - self.z0))

    def z_range(self, arr, aff, label_id):
        z = np.where((arr == label_id).any(axis=(0, 1)))[0]
        return (self.k_of(aff, int(z.min())), self.k_of(aff, int(z.max()))) if len(z) else None


def level_masks(fr, k):
    from scipy import ndimage as ndi
    c = np.asarray(fr.cls[k]); t = fr.ct(fr.tot, fr.aT, k); nk = fr.ct(fr.neck, fr.aN, k); b = fr.ct(fr.bv, fr.aB, k)
    h = fr.ct(fr.hm, fr.aH, k); cf = fr.ct(fr.cf, fr.aC, k)
    vert = np.isin(t, VERT_IDS); mand = (cf == CF_MANDIBLE) | np.isin(cf, CF_TEETH); bone = vert | (t == SKULL) | mand
    cart = np.isin(b, [BV_HYOID, BV_THYC, BV_CRIC]) | np.isin(b, list(BV_STYLOID.values()))
    tissue = ndi.binary_fill_holes(ndi.binary_closing(c > 0, iterations=3))
    dskin = ndi.distance_transform_edt(tissue)
    vessels = np.isin(b, BV_VESSELS); tongue = h == HM_TONGUE; dig = np.isin(h, HM_DIG)
    organs = (t > 0) & ~bone
    other = organs | np.isin(nk, NK_ALL) | vessels | dig | np.isin(h, HM_OTHER) | (b == BV_AIR)
    excl = ndi.binary_dilation(other, iterations=1) | ndi.binary_dilation(bone, iterations=2) \
        | ndi.binary_dilation(cart, iterations=1) | ~tissue | (dskin <= 4)
    v = ndi.uniform_filter(np.asarray(fr.rgb[k]).max(-1).astype(np.float32), 3)
    dark = ndi.binary_closing((c == 3) & (v < DARK_V), iterations=2) & tissue     # septa closed after the brightness cap
    return dict(c=c, t=t, nk=nk, b=b, h=h, cf=cf, vert=vert, mand=mand, bone=bone, cart=cart, tissue=tissue, dskin=dskin,
                vessels=vessels, tongue=tongue, dig=dig, excl=excl, dark=dark, v=v)


def clean(m, min_hole=MIN_HOLE_PX, min_part=MIN_PART_PX):
    from scipy import ndimage as ndi
    if not m.any():
        return m
    holes = ndi.binary_fill_holes(m) & ~m
    lab, n = ndi.label(holes)
    if n:
        sizes = np.bincount(lab.ravel())[1:]
        m = m | np.isin(lab, np.where(sizes < min_hole)[0] + 1)
    lab, n = ndi.label(m)
    sizes = np.bincount(lab.ravel())[1:]
    return m & np.isin(lab, np.where(sizes >= min_part)[0] + 1)


def column_extent(comp):
    W = comp.shape[1]; first = np.full(W, np.nan); last = np.full(W, np.nan)
    for cc in np.where(comp.any(axis=0))[0]:
        rs = np.where(comp[:, cc])[0]; first[cc] = rs.min(); last[cc] = rs.max()
    return first, last


def fraction(shape, first, last):
    yy = np.arange(shape[0])[:, None].astype(float)
    span = np.where(last > first, last - first, np.nan)[None, :]
    return (yy - first[None, :]) / span


def front_of(mask, H):
    """Per column: the first (anterior) row of mask, NaN where absent."""
    has = mask.any(axis=0)
    return np.where(has, np.argmax(mask, axis=0), np.nan).astype(float)


def strap_compartment(M, side, sgn, mid, H, W, lat_mm=STRAP_LAT_MM, low=False):
    from scipy import ndimage as ndi
    yy, xx = np.mgrid[0:H, 0:W]; dx = sgn * (xx - mid)
    visc = np.isin(M["b"], [BV_HYOID, BV_THYC, BV_CRIC, BV_AIR]) | np.isin(M["t"], [THYROID_GLAND, TRACHEA, OESOPHAGUS]) \
        | np.isin(M["nk"], NK_CONSTR) | M["vert"] | M["vessels"] | np.isin(M["nk"], [12, 13, 14, 15, 16, 17, 22, 23])
    fr_ = front_of(visc, H)
    core = np.isin(M["b"], [BV_HYOID, BV_THYC, BV_CRIC]) | np.isin(M["t"], [THYROID_GLAND, TRACHEA])
    cols_core = core.any(axis=0)
    if not cols_core.any():
        return np.zeros((H, W), bool), None, None, dx
    core_cols = np.where(cols_core)[0]
    ref = fr_.copy()
    for cc in np.where(np.isnan(fr_))[0]:                # columns without a front: the nearest visceral column's front
        ref[cc] = fr_[core_cols[np.argmin(np.abs(core_cols - cc))]]
    scm = ndi.binary_dilation(M["nk"] == NK_SCM[side], iterations=1)
    plat = ndi.binary_dilation(np.isin(M["nk"], NK_PLAT), iterations=1)
    row_core = float(np.where(core)[0].mean()) + 5 if low else H   # at the neck root the straps lie anterior to the trachea's centre
    comp = M["dark"] & (yy < ref[None, :]) & (yy >= (ref - STRAP_DEPTH_MM)[None, :]) & (yy < row_core) & (dx >= 0) & (dx <= lat_mm) \
        & ~M["excl"] & ~scm & ~plat & (M["dskin"] > STRAP_SKIN_MM)
    comp = clean(comp, min_part=STRAP_MIN_PART_PX)               # thin 3-4 mm straps: no opening, small crumbs only
    first, last = column_extent(comp)
    return comp, first, last, dx


def arch_interior(mand, H, W, side, mid):
    """The region inside the mandibular arch on this side: per row between the arch's inner surface and the midline;
    rows behind the arch's ends are closed at the arch's most posterior inner column."""
    inside = np.zeros((H, W), bool)
    cols = np.arange(W)
    lat_cols = (cols - mid) * (1 if side == "left" else -1)
    ys = np.where(mand.any(axis=1))[0]
    if len(ys) == 0:
        return inside
    inner_limit = None
    for r in range(ys.min(), H):
        row = mand[r] & (lat_cols >= 0)
        if row.any():
            inner = np.min(lat_cols[row])              # the innermost mandible column on this side
            inner_limit = inner
        elif inner_limit is None:
            continue
        inside[r] = (lat_cols >= 0) & (lat_cols < inner_limit)
    return inside


def floor_compartment(M, side, sgn, mid, arch, H, W):
    from scipy import ndimage as ndi
    yy, xx = np.mgrid[0:H, 0:W]; dx = sgn * (xx - mid)
    inside = arch_interior(arch, H, W, side, mid)
    post = M["vert"] | np.isin(M["nk"], NK_CONSTR) | M["vessels"] | (M["b"] == BV_HYOID) | (M["b"] == BV_AIR) | np.isin(M["nk"], list(NK_SCM.values()))
    pf = front_of(post, H)
    if np.isfinite(pf).any():
        pf = np.where(np.isnan(pf), np.nanmax(pf), pf)
        inside &= yy < pf[None, :]
    tongue_d = ndi.binary_dilation(M["tongue"], iterations=1)
    comp = M["dark"] & inside & ~M["excl"] & ~tongue_d & (dx >= 0) & (dx <= FLOOR_LAT_MM)
    comp = clean(comp)
    if not comp.any():
        return comp, None, dx, None
    outer = ~(comp | tongue_d | ndi.binary_dilation(post, iterations=2))
    d_out = ndi.distance_transform_edt(~outer)
    d_mand = ndi.distance_transform_edt(~arch)
    return comp, d_out, dx, d_mand


def run(a, log=print):
    from scipy import ndimage as ndi
    from skimage.morphology import white_tophat, disk
    fr = Frame(a.frame_dir, a.task_dir); H, W = fr.H, fr.W
    ids = {nm: i + 1 for i, nm in enumerate(MUSCLES)}
    # level anchors
    z_hy = fr.z_range(fr.bv, fr.aB, BV_HYOID); z_thyc = fr.z_range(fr.bv, fr.aB, BV_THYC); z_cric = fr.z_range(fr.bv, fr.aB, BV_CRIC)
    z_st = fr.z_range(fr.tot, fr.aT, STERNUM); z_tg = fr.z_range(fr.hm, fr.aH, HM_TONGUE); z_mand = fr.z_range(fr.cf, fr.aC, CF_MANDIBLE)
    z_teeth = fr.z_range(fr.cf, fr.aC, CF_TEETH[0]); z_sty = {s: fr.z_range(fr.bv, fr.aB, BV_STYLOID[s]) for s in BV_STYLOID}
    # the hyoid body's level: the hyoid label level with the most voxels within 8 mm of its centroid column
    best = (0, None); hy_col = None
    for k in range(z_hy[0], z_hy[1] + 1):
        b = fr.ct(fr.bv, fr.aB, k) == BV_HYOID
        if b.any():
            ys, xs = np.where(b); cm = float(xs.mean()); n = int((np.abs(xs - cm) < 8).sum())
            if n > best[0]:
                best = (n, k); hy_col = cm
    k_hyb = z_hy[0] + STRAP_TOP_ABOVE_HYOID_MM          # the strap band ends at the hyoid body's lower border
    k_strap_lo = z_st[1] - STRAP_BELOW_STERNUM_TOP_MM
    for k in range(k_strap_lo, k_strap_lo + 40):
        nk = fr.ct(fr.neck, fr.aN, k)
        if all((nk == NK_SCM[s]).sum() >= SCM_MIN_PX for s in NK_SCM):
            k_strap_lo = k; break
    k_floor_top = (z_teeth[0] if z_teeth else z_mand[1] - 20) + FLOOR_ABOVE_ALV_MM
    k_spine = z_mand[0] + GH_ABOVE_MAND_MM
    log(f"hyoid body k {k_hyb}, strap {k_strap_lo}..{k_hyb}, floor {k_hyb + 1}..{k_floor_top} (mental spine k {k_spine}), "
        f"tongue {z_tg}, thyroid cartilage {z_thyc}, cricoid {z_cric}, styloid {z_sty}")
    # corridor anchors (row, col) per side
    sty_pt = {}; hy_pt = {}; tg_pt = {}
    bhy = fr.ct(fr.bv, fr.aB, k_hyb) == BV_HYOID
    for side, sgn in (("right", -1), ("left", 1)):
        kb = z_sty[side][0]; m = fr.ct(fr.bv, fr.aB, kb) == BV_STYLOID[side]
        ys, xs = np.where(m); sty_pt[side] = (float(ys.mean()), float(xs.mean()))
        ys, xs = np.where(bhy & (sgn * (np.arange(W)[None, :] - hy_col) >= 0))
        d = sgn * (xs - hy_col); tgt = 0.55 * d.max(); i = int(np.argmin(np.abs(d - tgt)))
        hy_pt[side] = (float(ys[i]), float(xs[i]))
        k_tg = int(round(z_tg[0] + SG_TONGUE_Z * (z_tg[1] - z_tg[0])))
        T = fr.ct(fr.hm, fr.aH, k_tg) == HM_TONGUE; ys, xs = np.where(T); cmT = float(xs.mean())
        first, last = column_extent(T); gT = fraction((H, W), first, last)
        sel = T & (gT > 0.6) & (sgn * (np.arange(W)[None, :] - cmT) > 0)
        ys, xs = np.where(sel); i = int(np.argmax(sgn * (xs - cmT)))
        tg_pt[side] = (float(ys[i]), float(xs[i]) + sgn * 3, k_tg)
    out = {}; side_of = {}; support = {"right": {}, "left": {}}; levels_used = {"strap": [], "floor": [], "tongue": [], "corridor": []}
    k_lo = k_strap_lo; k_hi = max(z_tg[1], max(z_sty[s][0] for s in z_sty))
    arch_lo = fr.ct(fr.cf, fr.aC, z_mand[0] + ARCH_ABOVE_MM) == CF_MANDIBLE      # the body's arch, carried below it
    arch = arch_lo
    mid_v = None
    for k in range(k_lo, k_hi + 1):
        M = level_masks(fr, k); im = np.asarray(fr.rgb[k])
        th = white_tophat(im.max(-1).astype(np.float32), disk(4))
        lvl = np.zeros((H, W), np.uint8); sd = np.zeros((H, W), np.uint8)
        if M["vert"].any():
            ys, xs = np.where(M["vert"]); mid_v = float(xs.mean())
        if mid_v is None:
            continue
        in_strap = k <= k_hyb; in_floor = k_hyb < k <= k_floor_top; in_tongue = z_tg[0] <= k <= z_tg[1]
        if (in_floor or in_tongue) and k >= z_mand[0] + ARCH_ABOVE_MM:
            arch = M["cf"] == CF_MANDIBLE
        for side, sgn in (("right", -1), ("left", 1)):
            regs = {}
            if in_strap:
                visc = np.isin(M["b"], [BV_HYOID, BV_THYC, BV_CRIC]) | np.isin(M["t"], [TRACHEA])
                mid = float(np.where(visc)[1].mean()) if visc.any() else mid_v
                below = z_cric[0] - k
                low = below > OMO_BELOW_CRIC_MM
                comp, first, last, dx = strap_compartment(M, side, sgn, mid, H, W, STRAP_LAT_LOW_MM if low else STRAP_LAT_MM, low)
                if comp.sum() >= 30:
                    f = fraction((H, W), first, last)
                    rules = strap_rules(dx, f, comp, below, k <= z_thyc[1])
                    r = split_region(th, comp, rules, {nm: ids[nm] for nm in rules}); regs.update(r)
                    levels_used["strap"].append(k)
            if in_floor and arch is not None:
                mid = float(np.where(arch)[1].mean())
                comp, d_out, dx, d_mand = floor_compartment(M, side, sgn, mid, arch, H, W)
                if comp.sum() >= 30:
                    first, last = column_extent(comp); g = fraction((H, W), first, last)
                    rules = floor_rules(dx, g, d_out, comp, k > k_spine, d_mand)
                    r = split_region(th, comp, rules, {nm: ids[nm] for nm in rules})
                    for nm, m in r.items():
                        regs[nm] = regs.get(nm, np.zeros((H, W), bool)) | m
                    levels_used["floor"].append(k)
            if in_tongue:
                T = M["tongue"]
                if T.any():
                    cmT = float(np.where(T)[1].mean()); dxT = sgn * (np.arange(W)[None, :] - cmT) * np.ones((H, 1))
                    Ts = T & (dxT >= 0)
                    first, last = column_extent(T); gT = fraction((H, W), first, last)
                    zT = (k - z_tg[0]) / max(z_tg[1] - z_tg[0], 1)
                    rules = tongue_rules(dxT, gT, zT, k < z_tg[1] - DORSUM_MM, Ts)
                    r = split_region(th, Ts, rules, {nm: ids[nm] for nm in rules})
                    for nm, m in r.items():
                        regs[nm] = regs.get(nm, np.zeros((H, W), bool)) | m
                    levels_used["tongue"].append(k)
            # corridors
            kb = z_sty[side][0]
            yy, xx = np.mgrid[0:H, 0:W]
            taken = np.zeros((H, W), bool)
            for nm in regs.values():
                taken |= nm
            cands = {}
            if k_hyb < k < kb:
                c = corridor_centre(hy_pt[side], sty_pt[side], k, k_hyb, kb); cands["stylohyoid"] = c
            if tg_pt[side][2] < k < kb:
                c = corridor_centre(tg_pt[side][:2], (sty_pt[side][0] - STYLOID_ANT_MM, sty_pt[side][1]), k, tg_pt[side][2], kb); cands["styloglossus"] = c
            if cands:
                free = M["dark"] & ~M["excl"] & ~taken & ~ndi.binary_dilation(M["tongue"], iterations=1)
                dist = {nm: np.hypot(yy - c[0], xx - c[1]) for nm, c in cands.items()}
                for nm, d in dist.items():
                    m = free & (d <= COR_R_MM)
                    for o, d2 in dist.items():
                        if o != nm:
                            m &= d <= d2
                    m = clean(m, min_part=8)
                    if m.any():
                        regs[nm] = regs.get(nm, np.zeros((H, W), bool)) | m
                        levels_used["corridor"].append(k)
            for nm, m in regs.items():
                sel = m & (lvl == 0); lvl[sel] = ids[nm]; sd[sel] = 1 if side == "right" else 2
            for gname, members in GROUPS.items():
                for pair, obs in boundary_support(th, {nm: m for nm, m in regs.items() if nm in members}).items():
                    support[side].setdefault(pair, []).append(obs)
        if lvl.any():
            out[k] = lvl; side_of[k] = sd
        if k % 10 == 0:
            log(f"k {k} z {fr.z0 + k:.0f} px {int((lvl > 0).sum())}")
    merges = {}; dec = {s: merge_decision(support[s]) for s in support}
    for pair in set(dec["right"]) | set(dec["left"]):
        obs = [dec[s][pair] for s in ("right", "left") if pair in dec[s]]
        w = sum(o[1] for o in obs); r = sum(o[0] * o[1] for o in obs) / max(w, 1)
        merges[pair] = {"ratio": round(r, 2), "contact_px": int(w), "merge": bool(r < MERGE_RATIO and w >= MIN_MERGE_CONTACT_PX)}
    groups = merge_groups({p for p, d in merges.items() if d["merge"]})
    anchors = {"hyoid_body_k": k_hyb, "strap_k": [k_strap_lo, k_hyb], "floor_k": [k_hyb + 1, k_floor_top], "mental_spine_k": k_spine,
               "tongue_k": list(z_tg), "thyroid_cartilage_k": list(z_thyc), "cricoid_k": list(z_cric), "mandible_k": list(z_mand),
               "styloid_k": {s: list(v) for s, v in z_sty.items()}, "sternum_top_k": z_st[1],
               "levels_used": {g: [min(v), max(v)] if v else None for g, v in levels_used.items()}}
    return fr, out, side_of, ids, merges, groups, anchors


def montage(fr, vol, labels, ks, path, ka, cor_row, cor_cols):
    from PIL import Image, ImageDraw
    import colorsys
    n = max(labels) + 1
    lut = np.zeros((n, 3), np.uint8); bases = list(dict.fromkeys(l[1] for l in labels.values()))
    for lid, (nm, base, _, _) in labels.items():
        lut[lid] = [int(255 * v) for v in colorsys.hsv_to_rgb((bases.index(base) * 0.137) % 1.0, 0.85, 1.0)]
    tiles = []
    for name, k in ks:
        im = np.asarray(fr.rgb[k]).copy(); m = vol[k - ka]; ov = im.copy()
        sel = m > 0; ov[sel] = (0.45 * im[sel] + 0.55 * lut[m[sel]]).astype(np.uint8)
        r0, c0 = 100, 250
        crop = np.concatenate([im[r0:r0 + 170, c0:c0 + 200], ov[r0:r0 + 170, c0:c0 + 200]], axis=0)
        crop = np.kron(crop, np.ones((2, 2, 1), np.uint8))
        pil = Image.fromarray(crop); ImageDraw.Draw(pil).text((4, 4), f"{name} k={k} z={fr.z0 + k:.0f}", fill=(255, 255, 0))
        tiles.append(np.asarray(pil))
    # coronal through the tongue: rows = k (superior at top), cols = frame cols
    kb = ka + vol.shape[0]
    cor = np.stack([np.asarray(fr.rgb[k])[cor_row] for k in range(ka, kb)])[::-1]
    cm = vol[:, cor_row, :][::-1]; ovc = cor.copy(); sel = cm > 0; ovc[sel] = (0.45 * cor[sel] + 0.55 * lut[cm[sel]]).astype(np.uint8)
    cor = np.concatenate([cor[:, cor_cols[0]:cor_cols[1]], ovc[:, cor_cols[0]:cor_cols[1]]], axis=0)
    h = tiles[0].shape[0]; sc = max(1, min(2, h // cor.shape[0]))
    cor = np.kron(cor, np.ones((sc, sc, 1), np.uint8))
    pil = Image.fromarray(cor); ImageDraw.Draw(pil).text((4, 4), f"coronal row {cor_row}", fill=(255, 255, 0)); cor = np.asarray(pil)
    if cor.shape[0] < h:
        cor = np.pad(cor, ((0, h - cor.shape[0]), (0, 0), (0, 0)))
    tiles.append(cor[:h])
    leg = Image.new("RGB", (sum(t.shape[1] for t in tiles), 14 * ((len(bases) + 3) // 4 + 1)), (0, 0, 0))
    d = ImageDraw.Draw(leg); x = 4; y = 2; cw = leg.width // 4
    for base in bases:
        lid = next(l for l, v in labels.items() if v[1] == base)
        d.rectangle([x, y, x + 10, y + 10], fill=tuple(int(v) for v in lut[lid])); d.text((x + 14, y - 2), base, fill=(255, 255, 255))
        x += cw
        if x + cw > leg.width:
            x = 4; y += 14
    full = np.concatenate([np.concatenate(tiles, axis=1), np.asarray(leg)], axis=0)
    Image.fromarray(full).save(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--frame-dir", default=FRAME_DIR); ap.add_argument("--task-dir", default=str(TASK_DIR))
    ap.add_argument("--out", default=str(TASK_DIR / "vhf_hyoid_muscles_cryo.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / "mappings/vhf_hyoid_muscles_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / "mappings/subjects/ct_vhf_hyoid_volume_mapping.json"))
    a = ap.parse_args(argv)
    import nibabel as nib
    fr, out, side_of, ids, merges, groups, anchors = run(a)
    final, labels, lut_r, lut_l = relabel(ids, groups)
    ka, kb = min(out), max(out) + 1
    vol = np.zeros((kb - ka, fr.H, fr.W), np.uint8)
    for k in out:
        vol[k - ka] = np.where(side_of[k] == 2, lut_l[out[k]], np.where(side_of[k] == 1, lut_r[out[k]], 0))
    aff = np.array([[-1, 0, 0, 350], [0, -1, 0, 240], [0, 0, 1, fr.z0 + ka], [0, 0, 0, 1]], float)
    nib.save(nib.Nifti1Image(np.ascontiguousarray(vol.transpose(2, 1, 0)), aff), a.out)
    vols = {nm: round(float((vol == lid).sum()) / 1000, 1) for lid, (nm, *_) in labels.items()}
    print("volumes cm3", vols, flush=True)
    # montage: mandible body, hyoid, thyroid cartilage, cricoid, coronal through the tongue
    k_m = min(max(anchors["mandible_k"][0] + 10, ka), kb - 1); k_h = anchors["hyoid_body_k"]
    k_t = (anchors["thyroid_cartilage_k"][0] + anchors["thyroid_cartilage_k"][1]) // 2; k_c = (anchors["cricoid_k"][0] + anchors["cricoid_k"][1]) // 2
    k_tg = (anchors["tongue_k"][0] + anchors["tongue_k"][1]) // 2
    T = fr.ct(fr.hm, fr.aH, k_tg) == HM_TONGUE; cor_row = int(np.where(T)[0].mean()) + 8 if T.any() else 200
    mpath = str(Path(a.out).with_suffix("").with_suffix("")) + ".png"
    montage(fr, vol, labels, [("mandible", k_m), ("hyoid", k_h), ("thyroid cart.", k_t), ("cricoid", k_c), ("tongue", k_tg)], mpath, ka, cor_row, (240, 460))
    merged_compartments = {nm: (COMPARTMENTS.get(nm) or members) for nm, members in final if len(members) > 1 or nm in COMPARTMENTS}
    def note_for(lid):
        nm, base, members, side = labels[lid]; v = vols[nm]
        if base in SINKS:
            return f"{v} cm3; NOT shipped: {SINKS[base]}."
        if len(members) > 1:
            pairs = [f"{p[0]}/{p[1]} ratio {d['ratio']}" for p, d in merges.items() if d["merge"] and set(p) <= set(members)]
            return (f"{v} cm3; compartment holding {', '.join(members)}: the marker watershed found no pale septum between them "
                    f"(boundary / inside top-hat {'; '.join(pairs)} < {MERGE_RATIO}); not split, mapped to null.")
        if base == "stylohyoid":
            return (f"{v} cm3; compartment: stylohyoid + posterior belly of the digastric (one band from the styloid / mastoid to the hyoid at 1 mm; "
                    f"the stylohyoid splits around the digastric tendon) -- at ~2 cm3 it is 2-3x a stylohyoid; mapped to null, candidates listed.")
        if base == "omohyoid":
            return f"{v} cm3; {BADGE}: superior belly and its course under the SCM; the inferior belly across the posterior triangle is not attempted."
        if base == "styloglossus":
            return f"{v} cm3; {BADGE}: corridor from the styloid process to the side of the tongue and the lateral posterior side of the tongue label."
        return f"{v} cm3; {BADGE}: position-rule marker relative to her mandible / hyoid / larynx / tongue labels, boundary by the marker watershed on her fascial septa."
    entries = []
    for lid in sorted(labels):
        nm, base, members, side = labels[lid]; atlas = ATLAS_OF.get(base) if len(members) == 1 else None
        sfx = "_r" if side == "right" else "_l"
        cands = [m + sfx for m in (COMPARTMENTS.get(base) or (members if len(members) > 1 else []))] if atlas is None else []
        entries.append({"label": lid, "source_structure": nm, "side": side, "status": "curated",
                        "atlas_id": atlas + sfx if atlas else None, "relationship": "exact" if atlas else "no_usable_label",
                        "note": note_for(lid), "candidates": cands})
    not_attempted = {"intrinsic_tongue": "superior / inferior longitudinal, transverse and vertical muscles: no septa at 1 mm; carried in the tongue_intrinsic sink",
                     "palatoglossus": "a 1-2 mm fold; out of scope", "palate_and_pharynx": "out of scope (the constrictors are shipped from the CT task)",
                     "larynx": "out of scope", "omohyoid_inferior_belly": "a 2-3 mm band across the posterior triangle in fat at 1 mm; not attempted",
                     "digastric": "already shipped from the head_muscles CT task (ct_vhf_headm); its label is excluded here",
                     "sternothyroid_thyrohyoid": "shipped from the CT task (ct_vhf_neck); their labels excluded, the deep strap layer is a sink"}
    key = {"_README": [f"Label id -> structure name for the Visible Human FEMALE suprahyoid / infrahyoid / extrinsic tongue volume "
                       f"(scripts/cryo/vhf_hyoid_muscles_from_cryo.py), plus the mapping onto atlas entities. A KEY, not data. {BADGE}: "
                       f"markers by position rules relative to her mandible, hyoid, larynx, styloid and tongue labels, boundaries by marker "
                       f"watershed on the pale septa of her cryosection photographs; sinks and compartments are mapped to null."],
           "source": SOURCE, "task": "vhf_hyoid_muscles", "version": VERSION, "badge": BADGE,
           "labels": {str(l): labels[l][0] for l in sorted(labels)}, "merged_compartments": merged_compartments, "not_attempted": not_attempted,
           "atlas": {e["source_structure"]: {"atlas_id": e["atlas_id"], "relationship": e["relationship"], "note": e["note"]} for e in entries}}
    json.dump(key, open(a.labels_out, "w"), indent=1)
    mapping = {"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                           "'status' is advisory; convert reads 'atlas_id' only."],
               "subject": "ct_vhf_hyoid", "source_volume": str(Path(a.out).resolve()), "label_map": "vhf_hyoid_muscles", "entries": entries}
    json.dump(mapping, open(a.mapping_out, "w"), indent=1)
    report = {
        "_README": ["Female suprahyoid, infrahyoid and extrinsic tongue muscles by position rules on her registered 1 mm cryosection frame "
                    "(scripts/cryo/vhf_hyoid_muscles_from_cryo.py). Rule-based, derived data."],
        "source": SOURCE, "badge": BADGE, "version": VERSION, "volumes_cm3": vols,
        "labels": {str(l): labels[l][0] for l in sorted(labels)},
        "merged": {nm: {"members": merged_compartments[nm], "why": note_for(next(l for l, v in labels.items() if v[0] == nm + "_right"))} for nm in merged_compartments},
        "not_shipped": {**not_attempted, **SINKS},
        "septum_support": {f"{p[0]}|{p[1]}": d for p, d in merges.items()}, "merge_ratio_threshold": MERGE_RATIO,
        "levels": {**anchors, "k_range": [ka, kb - 1], "z_ras_range": [fr.z0 + ka, fr.z0 + kb - 1]},
        "rules": {"dark_v": DARK_V, "marker_erode_px": MARKER_ERODE_PX,
                  "strap": {"lateral_mm": STRAP_LAT_MM, "skin_mm": STRAP_SKIN_MM, "sternohyoid_half_width_mm": [SH_W_MM, SH_W_LOW_MM], "omohyoid_slope": OMO_SLOPE, "deep_sink_f": DEEP_F, "thyrohyoid_lateral_mm": TH_LAT_MM},
                  "floor": {"mylohyoid_thickness_mm": MH_T_MM, "geniohyoid_half_width_mm": GH_W_MM, "genioglossus_half_width_mm": GG_W_MM, "mental_spine_above_mandible_mm": GH_ABOVE_MAND_MM, "hyoglossus_g": HG_G},
                  "tongue": {"genioglossus": [GG_T_W_MM, GG_T_G], "hyoglossus": [HG_T_W_MM, HG_T_G, HG_T_Z], "styloglossus": [SG_T_W_MM, SG_T_G, SG_T_Z], "dorsum_mm": DORSUM_MM},
                  "corridor_radius_mm": COR_R_MM},
        "literature": {
            "note": "cross-sectional areas verified from PubMed abstracts; no per-muscle volume verified, so volumes are 'not compared'.",
            "geniohyoid_csa_ultrasound": {"pmid": "38587613", "doi": "10.1007/s41999-024-00971-6",
                                          "value": "geniohyoid CSA (ultrasound) 247.3 +/- 37.4 mm2 in younger women, 167.2 +/- 32.6 mm2 in women >= 65 (Mori 2024, Eur Geriatr Med)"},
            "geniohyoid_csa_ct": {"pmid": "39502723", "doi": "10.1002/ags3.12839",
                                  "value": "geniohyoid sagittal CSA on neck CT 2.4 +/- 0.5 cm2 in women (Kawata 2024, Ann Gastroenterol Surg; oesophagectomy patients)"},
            "geniohyoid_here": {"volume_cm3": {s: vols.get(f"geniohyoid_{s}") for s in ("right", "left")},
                                "note": "a paired 1-3 cm3 muscle ~35 mm long is consistent with a 2-2.5 cm2 sagittal CSA (the CSA covers both bellies)"},
            "tongue_dataset": {"pmid": "40368940", "doi": "10.1038/s41597-025-05092-8",
                               "value": "annotated MRI dataset of five tongue muscles incl. genioglossus with tongue muscle volumes (Ribeiro 2025, Sci Data); no numbers in the abstract"},
            "volumes": "not compared: no per-muscle volumetric value verified from an abstract"},
        "montage": mpath, "output": a.out, "labels_file": a.labels_out, "mapping_file": a.mapping_out,
        "limits": ["boundaries are rules + watershed on 1 mm photographs, not traced fascia", "z registration residual 8.9 mm rms; the hyoid, "
                   "mandible and tongue labels sit on their photographed structures to within ~5 mm at the levels checked",
                   "her head is flexed (chin at the hyoid's level): the geniohyoid / genioglossus split is by the mental spine level, not by fibre course",
                   "the stylohyoid corridor carries the posterior digastric belly (one band at 1 mm)",
                   "the tongue split is by rules inside the CT tongue label only (no septa)"],
    }
    json.dump(report, open(str(Path(a.out).with_suffix("").with_suffix("")) + "_report.json", "w"), indent=1)
    print("groups", [sorted(g) for g in groups]); print("merges", merges); print("anchors", anchors)
    print("HYOID_DONE")


if __name__ == "__main__":
    main()
