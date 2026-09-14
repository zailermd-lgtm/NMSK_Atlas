"""Female RIGHT forearm muscles from her FULL-RESOLUTION cryosection crops (Q62 step 1). Rule-based; badged.

    python3 scripts/cryo/vhf_forearm_muscles_from_cryo.py --crops SCRATCH/vh_cryo_f --bones build/vh/ct_vhf_armb \
        --out data/ct_sources/task_outputs/vhf_forearm_muscles_cryo.nii.gz --montage-dir SCRATCH/vh_cryo_f

DATA. arm_full_right.npy (vhf_stream_arm_crops.py): 0.33 mm RGB crops of the right forearm, one per 1 mm level of
the v1 frame (RAS z -500 .. -990). The crops were cut BEFORE the frame-height correction of 2026-09-13, so the
level with v1 z = Z1 shows the anatomy at true RAS z = Z1 - offset(y) (frame.json "z_correction": v1 slice k showed
the anatomy of k - offset; ~69-76 mm here). In-plane: frame row r = (H-1 - pr/3) sc + RS, col c = (pc/3) sc + 110 +
CS with H = 405, sc = 0.99 and RS/CS the anchors.json shifts interpolated at the v1 z (as the crops were made);
RAS x = 350 - c, RAS y = 240 - r; atlas = (RAS x - 7.769, RAS z + 885.229, RAS y - 14.137). Photo top =
posterior, photo left = the subject's right (lateral).

MAPPING CHECK. Her CT radius/ulna (ct_vhf_armb, clipped by the CT field of view to y 126-300 / 135-230) are sectioned
at each level and overlaid; they land INSIDE the forearm island but 5-12 mm off the photographed bone discs, by an
amount that changes along the forearm (her forearm in the CT and in the frozen block are not one rigid body, as
found for the humerus in Q49). So the CT bones are used only to SEED the bone tracker at one level; the rules are
built on the bones AS PHOTOGRAPHED. The residual per level is recorded in the report (ct_to_photo_shift_mm).

RULE, per level (0.33 mm px):
  island   = the tissue component (R > B + 30, not black) holding the bones, separated from the thigh it rests on by
             the smallest erosion (>= 4 mm) that frees it, grown back inside the tissue;
  muscle   = 5 px-mean red channel < 100 inside the island (this cadaver: muscle R 50-90, fat > 178);
  bones    = the largest circle inscribed in the pale class (its marrow filled) within 6 mm of the previous
             level's centre and >= 7 mm from the skin (the fat under the skin is thinner than a bone is wide);
             seeded at one level from the CT sections (9 mm), tracked in both directions (a lost bone widens the
             search 2 mm per level, > 8 levels lost or the discs merging (< 15 mm) ends the track); the segment
             runs from the top of her CT radius label (the radial head, y 300) to the last tracked level (the
             discs merge into the carpus below y ~140);
  frame    = e: ulna -> radius unit vector, n: its perpendicular pointing AWAY from the ulna's subcutaneous border
             (the male's compartment rule: the ulna's posterior border lies under the skin, so that side is
             extensor); f = level fraction along the segment (0 radial head, 1 distal radius);
  markers  = MARKER_RULES: per muscle a position in the bone frame (mm from the bone SURFACES, the disc radii
             added) and the f-window in which it is seeded (textbook belly extent); a 1.7 mm disc snapped into
             its compartment's muscle within 5 mm, seeded afresh at every level (no level-to-level tracking);
  comps    = flexor / lateral (mobile wad, beyond the radius centre) / extensor by the bone-line rule
             (compartments()); each compartment is split on its own, so the compartment borders are rule lines;
  split    = marker watershed on the white top-hat (disk 4 px) of the brightness inside the muscle mass (closed
             1 mm, seams <= 8 mm2 filled, bones out): the pale fascial septa are the ridges. Muscle pixels in a
             compartment without a marker stay unassigned. boundary_support (report) scores every adjacent pair:
             mean top-hat on the boundary band / mean top-hat inside (>= 1.8 = the split runs on a pale line).
Boundaries the photographs do not show are not invented: the muscles whose watershed regions are not credible
(volumes outside what the muscle can have, or a split without a pale line at most levels) are MERGED into named
compartments (vhf_forearm_merge.json, --merge) and mapped to null with the reason in the mapping note.
Orientation: the flexor side of the bone line was checked two ways -- the ulna's nearest skin (its subcutaneous
posterior border) lies on the other side, and her CT thumb metacarpal lies 35 mm off the MC2-5 plane on that
side (the palm).
Output: label volume (RAS, 0.5 x 0.5 x 1 mm, positive-determinant affine) for `ingest_volume_geometry.py convert`,
label key, subject mapping, report (per-muscle volumes, bone track, CT residual, montage paths), montages.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
import trimesh
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage.morphology import white_tophat, disk
from skimage.segmentation import watershed

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

PX = 1 / 3.0                                   # mm per full-resolution pixel
H, SC, ORIGIN = 405, 0.99, (7.769, -885.229, 14.137)
MUSCLE_R, FAT_R = 100.0, 178.0
BADGE = "rule-based"
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections at full "
          "resolution (0.33 mm) and CT via the NCI Imaging Data Commons. Derived data "
          "(scripts/cryo/vhf_forearm_muscles_from_cryo.py), rule-based.")

# name: (anchor, e_mm, n_mm, f0, f1, group). Position = anchor centre + e * (e_mm [+ disc radius if anchor bone
# and e_mm != 0 and sign]) + n * (n_mm [+ disc radius]); anchors: U ulna, R radius, M midpoint. n > 0 flexor side.
MARKER_RULES = {
    # superficial flexors (medial epicondyle origin; lateral -> medial: PT, FCR, PL, FCU)
    "pronator_teres":                 ("R", -2, +9, 0.00, 0.40, "flexor"),
    "flexor_carpi_radialis":          ("R", -2, +14, 0.00, 0.55, "flexor"),
    "palmaris_longus":                ("M", 0, +24, 0.00, 0.45, "flexor"),
    "flexor_carpi_ulnaris":           ("U", -8, +4, 0.00, 0.85, "flexor"),
    "flexor_digitorum_superficialis": ("M", 0, +13, 0.05, 0.75, "flexor"),
    # deep flexors
    "flexor_digitorum_profundus":     ("U", +4, +5, 0.05, 0.85, "flexor"),
    "flexor_pollicis_longus":         ("R", -4, +4, 0.20, 0.85, "flexor"),
    "pronator_quadratus":             ("M", 0, +5, 0.82, 1.00, "flexor"),
    # lateral (mobile wad)
    "brachioradialis":                ("R", +16, +4, 0.00, 0.55, "lateral"),
    "extensor_carpi_radialis_longus": ("R", +8, -4, 0.00, 0.50, "lateral"),
    "extensor_carpi_radialis_brevis": ("R", +3, -8, 0.05, 0.65, "lateral"),
    # posterior
    "extensor_digitorum":             ("M", +4, -14, 0.05, 0.70, "extensor"),
    "extensor_digiti_minimi":         ("U", +10, -8, 0.10, 0.65, "extensor"),
    "extensor_carpi_ulnaris":         ("U", -2, -5, 0.05, 0.80, "extensor"),
    "anconeus":                       ("U", +6, -4, 0.00, 0.12, "extensor"),
    "supinator":                      ("R", -2, -4, 0.00, 0.28, "extensor"),
    "abductor_pollicis_longus":       ("M", +5, -5, 0.35, 0.80, "extensor"),
    "extensor_pollicis_brevis":       ("M", +9, -4, 0.55, 0.85, "extensor"),
    "extensor_pollicis_longus":       ("M", -3, -5, 0.40, 0.85, "extensor"),
    "extensor_indicis":               ("M", -6, -4, 0.60, 0.92, "extensor"),
}
SEED_PX = 5                  # rule seed disc radius (1.7 mm)


# ----------------------------------------------------------------------------------------------- crops / mapping
class ArmCrops:
    """The v1 arm crops (vhf_stream_arm_crops.py) with the frame-height correction applied per level."""

    def __init__(self, frame_dir, side="right"):
        d = Path(frame_dir); self.b = json.load(open(d / "arm_full_bbox.json")); self.side = side
        self.a = np.load(d / f"arm_full_{side}.npy", mmap_mode="r")
        fr = json.load(open(d / "frame.json")); corr = fr.get("z_correction", {}).get("offset_mm_at_y", {})
        self.cy = np.array(sorted(float(k) for k in corr)); self.co = np.array([corr[str(int(k))] for k in self.cy])
        A = [x for x in json.load(open(d / "anchors.json")) if x["flip"] == "fy" and x["iou"] >= 0.7]
        zs = np.array([x["ct_z"] for x in A]); o = np.argsort(zs)
        self.rs = ndi.median_filter(np.array([x["shift"][0] for x in A], float), 5, mode="nearest")[o]
        self.cs = ndi.median_filter(np.array([x["shift"][1] for x in A], float), 5, mode="nearest")[o]; self.zs = zs[o]
        self.n = len(self.b["z_ras"])

    def level(self, j):
        z1 = self.b["z_ras"][j]; zi = self.b["cryo_idx"][j]; w = self.b["windows"][str(zi)][self.side]
        y = corrected_y(z1, self.cy, self.co)
        return {"j": j, "z1": z1, "zi": zi, "w": w, "RS": float(np.interp(z1, self.zs, self.rs)),
                "CS": float(np.interp(z1, self.zs, self.cs)), "y": y, "z_true": y - 885.229}

    def image(self, j):
        """The whole memmap slice (one fixed shape for every level; outside this level's window it is black)."""
        return np.asarray(self.a[j])

    def px_to_ras(self, L, pr, pc):
        r = (H - 1 - (np.asarray(pr, float) + L["w"][0]) / 3) * SC + L["RS"]
        c = (np.asarray(pc, float) + L["w"][2]) / 3 * SC + 110 + L["CS"]
        return 350.0 - c, 240.0 - r

    def atlas_to_px(self, L, x, z):
        c = 350.0 - (np.asarray(x, float) + ORIGIN[0]); r = 240.0 - (np.asarray(z, float) + ORIGIN[2])
        return ((H - 1) - (r - L["RS"]) / SC) * 3 - L["w"][0], ((c - 110 - L["CS"]) / SC) * 3 - L["w"][2]


def corrected_y(z1, cy, co):
    """Atlas y of the anatomy shown by a v1-frame level Z1: y = Z1 - offset(y) + 885.229 (fixed point)."""
    y = z1 + 885.229
    if len(cy) == 0:
        return y
    for _ in range(6):
        y = z1 - float(np.interp(y, cy, co)) + 885.229
    return y


def load_meshes(d):
    man = json.loads((Path(d) / "manifest.json").read_text())
    V = np.fromfile(Path(d) / "vertices.f32", np.float32).reshape(-1, 3); F = np.fromfile(Path(d) / "faces.u32", np.uint32).reshape(-1, 3)
    out = {}
    for s in man["structures"]:
        v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]]
        f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
        out[s["atlas_id"]] = trimesh.Trimesh(v, f, process=False)
    return out


def sections(meshes, crops, L, shape, names=("radius_r", "ulna_r", "carpals_r")):
    out = {}
    for nm in names:
        tm = meshes.get(nm)
        if tm is None:
            continue
        sec = tm.section(plane_origin=[0, L["y"], 0], plane_normal=[0, 1, 0])
        if sec is None:
            continue
        img = Image.new("L", (shape[1], shape[0]), 0); dr = ImageDraw.Draw(img)
        for ent in sec.entities:
            pts = sec.vertices[ent.points]; pr, pc = crops.atlas_to_px(L, pts[:, 0], pts[:, 2])
            if len(pr) >= 3:
                dr.polygon(list(zip(pc.tolist(), pr.tolist())), fill=1)
        m = np.asarray(img, bool)
        if m.any():
            out[nm] = m
    return out


# ----------------------------------------------------------------------------------------------- photo classes
def island_mask(im, ref, thr=30):
    """The forearm's own tissue component: (R > B + thr, not black) closed and filled, eroded by the smallest of
    12..60 px that leaves the component at `ref` (row, col) under 120 000 px (the thigh it rests on is bigger),
    then grown back that far inside the tissue. Returns (mask, erosion_px) or (None, None)."""
    R = im[..., 0].astype(int); B = im[..., 2].astype(int); tissue = (R > B + thr) & (im.max(-1) > 60)
    t0 = ndi.binary_fill_holes(ndi.binary_closing(tissue, iterations=3))
    rr, cc = int(round(ref[0])), int(round(ref[1]))
    for it in (12, 18, 24, 30, 40, 50, 60):
        t = ndi.binary_erosion(t0, iterations=it); lab, n = ndi.label(t)
        if n == 0:
            continue
        i = lab[rr, cc] if (0 <= rr < lab.shape[0] and 0 <= cc < lab.shape[1]) else 0
        if i == 0:
            idx = ndi.distance_transform_edt(lab == 0, return_indices=True)[1]
            i = lab[idx[0][min(max(rr, 0), lab.shape[0] - 1), min(max(cc, 0), lab.shape[1] - 1)],
                    idx[1][min(max(rr, 0), lab.shape[0] - 1), min(max(cc, 0), lab.shape[1] - 1)]]
        m = lab == i
        if m.sum() < 120000:
            g = m
            for _ in range(it + 2):
                g = ndi.binary_dilation(g, iterations=1) & t0
            return g, it
    return None, None


def classes(im, isl):
    R = im[..., 0].astype(np.float32); m5 = ndi.uniform_filter(R, 5)
    muscle = (m5 < MUSCLE_R) & isl; pale = (m5 > 150) & isl
    return {"R": R, "m5": m5, "muscle": muscle, "pale": pale}


def pale_filled(cl, isl, marrow_mm2=200.0):
    """The pale class closed by 2 px with its small holes (the marrow, <= 200 mm2) filled -- not the muscle mass the
    subcutaneous fat ring encloses."""
    p0 = ndi.binary_closing(cl["pale"] & isl, iterations=2); holes = ndi.binary_fill_holes(p0) & ~p0; hl, hn = ndi.label(holes)
    if hn:
        hs = ndi.sum(holes, hl, range(1, hn + 1)); small = np.zeros(hn + 1, bool); small[1:] = hs * PX * PX <= marrow_mm2; p0 = p0 | small[hl]
    return p0


def dt_bone(dt, dist, prev, search_mm, skin_mm=7.0, min_r_mm=3.5):
    """A bone disc = the largest circle inscribed in the pale class (peak of its distance transform `dt`) within
    `search_mm` of the previous centre and >= `skin_mm` from the skin (`dist`: distance to the island edge). The fat
    under the skin is thinner than a bone is wide, so its inscribed circles lose. Returns (cy, cx, r_px) or None."""
    yy, xx = np.mgrid[0:dt.shape[0], 0:dt.shape[1]]
    win = (np.hypot(yy - prev[0], xx - prev[1]) * PX <= search_mm) & (dist * PX >= skin_mm)
    if not win.any():
        return None
    v = np.where(win, dt, -1.0); cy, cx = np.unravel_index(int(np.argmax(v)), v.shape); r = float(dt[cy, cx])
    return (float(cy), float(cx), r) if r * PX >= min_r_mm else None


def bone_mask(pale, cy, cx, r_px):
    yy, xx = np.mgrid[0:pale.shape[0], 0:pale.shape[1]]
    return ndi.binary_fill_holes(pale & (np.hypot(yy - cy, xx - cx) <= r_px + 3))


# ----------------------------------------------------------------------------------------------- pure rules
def bone_frame(U, R, skin_dir_at_ulna):
    """Unit e (ulna -> radius) and n (perpendicular pointing AWAY from the ulna's subcutaneous border, i.e. to the
    flexor side); rows/cols in px. skin_dir_at_ulna: vector from the ulna centre to the nearest skin point."""
    U = np.asarray(U, float); R = np.asarray(R, float); e = R - U; d = float(np.hypot(*e))
    if d < 1e-6:
        raise ValueError("coincident bones")
    e = e / d; n = np.array([-e[1], e[0]])
    if np.dot(n, np.asarray(skin_dir_at_ulna, float)) > 0:
        n = -n
    return e, n, d


def marker_positions(U, R, ru, rr, e, n, f, active_only=True):
    """Rule seeds for level fraction f: {name: (row, col)} in px. ru/rr: disc radii (px). Offsets in MARKER_RULES are
    mm from the anchor bone's SURFACE (the disc radius is added along the offset's direction)."""
    U = np.asarray(U, float); R = np.asarray(R, float); M = (U + R) / 2; out = {}
    for name, (anc, em, nm, f0, f1, _grp) in MARKER_RULES.items():
        if active_only and not (f0 <= f <= f1):
            continue
        base = {"U": U, "R": R, "M": M}[anc]; rad = {"U": ru, "R": rr, "M": 0.0}[anc]
        ev = em / PX + (np.sign(em) * rad if em else 0.0); nv = nm / PX + (np.sign(nm) * rad if nm else 0.0)
        out[name] = tuple(base + e * ev + n * nv)
    return out


def level_fraction(j, j_top, j_bot):
    return (j - j_top) / max(j_bot - j_top, 1)


# ----------------------------------------------------------------------------------------------- per-level split
GROUP_ID = {"flexor": 1, "lateral": 2, "extensor": 3}


def snap(pt, region, max_px=15):
    """`pt` (row, col) if it lies in `region`, else the nearest region pixel within max_px, else None."""
    r, c = int(round(pt[0])), int(round(pt[1]))
    if 0 <= r < region.shape[0] and 0 <= c < region.shape[1] and region[r, c]:
        return r, c
    win = region[max(r - max_px, 0):r + max_px + 1, max(c - max_px, 0):c + max_px + 1]
    if not win.any():
        return None
    ys, xs = np.where(win); ys = ys + max(r - max_px, 0); xs = xs + max(c - max_px, 0)
    k = np.argmin(np.hypot(ys - r, xs - c))
    return (int(ys[k]), int(xs[k])) if np.hypot(ys[k] - r, xs[k] - c) <= max_px else None


def compartments(shape, U, R, ru, rr, e, n):
    """Pixel -> compartment by the bone-line rule (px in, radii in px): s = position along ulna -> radius (0..1
    between the centres), t = mm from the line, + on the flexor side. lateral (mobile wad) = beyond the radius
    centre (s > 1) from the flexor side round to 14 mm behind the radius surface; flexor = the flexor side of the line
    plus the ulna's medial face (s < 0, t > -ulna radius), not lateral; extensor = the rest."""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]; py = yy - U[0]; px = xx - U[1]; d = np.hypot(R[0] - U[0], R[1] - U[1])
    s = (py * e[0] + px * e[1]) / d; t = (py * n[0] + px * n[1]) * PX
    lat = (s > 1.0) & (t > -(rr * PX + 14.0))
    flex = ((t > 0) | ((s < 0) & (t > -ru * PX))) & ~lat
    comp = np.full(shape, GROUP_ID["extensor"], np.uint8); comp[lat] = GROUP_ID["lateral"]; comp[flex] = GROUP_ID["flexor"]
    return comp


def split_level(th, region, comp, seeds, ids, groups):
    """Within each compartment, a marker watershed of `region` on the top-hat `th` from the rule seeds (1.7 mm discs
    snapped into the compartment's muscle within 5 mm). Returns {name: mask}, unassigned mask."""
    out = {}
    for g, gid in GROUP_ID.items():
        reg = region & (comp == gid); markers = np.zeros(region.shape, np.int32)
        for name, pt in seeds.items():
            if groups[name] != g:
                continue
            p = snap(pt, reg & (markers == 0))
            if p is None:
                continue
            z = np.zeros(region.shape, bool); z[p] = True
            markers[ndi.binary_dilation(z, iterations=SEED_PX) & reg & (markers == 0)] = ids[name]
        if not markers.any():
            continue
        ws = watershed(th, markers, mask=reg)
        for name, l in ids.items():
            m = ws == l
            if m.any():
                out[name] = m
    lab = np.zeros(region.shape, bool)
    for m in out.values():
        lab |= m
    return out, region & ~lab


def boundary_support(th, cur, ids, min_contact_px=15):
    """Per adjacent pair of regions: (contact px, mean top-hat on the 1 px boundary band / mean top-hat 2 px inside
    the two regions). A ridge ratio well above 1 means the split follows a pale septum."""
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
            out[(a, b)] = (nb, round(ratio, 2))
    return out


# ----------------------------------------------------------------------------------------------- bone tracking
def track_bones(crops, meshes, j_anchor, j_lo, j_hi, log=print, merge_mm=15.0, lost_max=8):
    """Bone discs per level: {j: {'radius': (cy, cx, r_px, mask), 'ulna': ..., 'island', 'cl', 'im', 'L', 'found',
    'ct': {bone: CT section centroid}}}. Seeded at j_anchor from the CT sections (search 9 mm), then tracked outward
    in both directions (search 6 mm, +2 mm per level lost; a bone lost for > 8 levels or the two discs merging
    (< 15 mm apart) end the track). residual: photographed centre minus CT centre (mm) where both exist."""
    out = {}; residual = {}
    L = crops.level(j_anchor); im = crops.image(j_anchor); se = sections(meshes, crops, L, im.shape[:2])
    if "radius_r" not in se or "ulna_r" not in se:
        raise SystemExit(f"no CT radius+ulna section at anchor level {j_anchor}")
    cent = {b: tuple(np.mean(np.where(se[b + "_r"]), axis=1)) for b in ("radius", "ulna")}

    def one(j, prev, lost, first=False):
        L = crops.level(j); im = crops.image(j); ref = tuple(np.mean([prev["radius"], prev["ulna"]], axis=0)); isl, er = island_mask(im, ref)
        if isl is None:
            return None
        cl = classes(im, isl); pale = pale_filled(cl, isl); dt = ndi.distance_transform_edt(pale); dist = ndi.distance_transform_edt(isl)
        rec = {"island": isl, "erode": er, "cl": cl, "im": im, "L": L, "found": {}, "ct": {}}
        for b in ("radius", "ulna"):
            h = dt_bone(dt, dist, prev[b], 9.0 if first else 6.0 + 2.0 * lost[b])
            if h is None:
                rec[b] = (prev[b][0], prev[b][1], 0.0, None); rec["found"][b] = False
            else:
                rec[b] = (h[0], h[1], h[2], bone_mask(pale, *h)); rec["found"][b] = True
        se = sections(meshes, crops, L, im.shape[:2], ("radius_r", "ulna_r"))
        for b in ("radius", "ulna"):
            if b + "_r" in se:
                c = np.mean(np.where(se[b + "_r"]), axis=1); rec["ct"][b] = (float(c[0]), float(c[1]))
                if rec["found"][b]:
                    residual.setdefault(b, {})[j] = [round(float((rec[b][0] - c[0]) * PX), 1), round(float((rec[b][1] - c[1]) * PX), 1)]
        return rec

    rec = one(j_anchor, cent, {"radius": 0, "ulna": 0}, first=True)
    if rec is None or not all(rec["found"].values()):
        raise SystemExit("bones not found in the photograph at the anchor level")
    out[j_anchor] = rec
    for rng in (range(j_anchor - 1, j_lo - 1, -1), range(j_anchor + 1, j_hi + 1)):
        prev = {b: out[j_anchor][b][:2] for b in ("radius", "ulna")}; lost = {"radius": 0, "ulna": 0}
        for j in rng:
            r = one(j, prev, lost)
            if r is None:
                log(f"  bone track stops at level {j} (no island)"); break
            for b in ("radius", "ulna"):
                if r["found"][b]:
                    prev[b] = r[b][:2]; lost[b] = 0
                else:
                    lost[b] += 1
            if max(lost.values()) > lost_max:
                log(f"  bone track stops at level {j} (bone lost)"); break
            if np.hypot(prev["radius"][0] - prev["ulna"][0], prev["radius"][1] - prev["ulna"][1]) * PX < merge_mm:
                log(f"  bone track stops at level {j} (discs merge)"); break
            out[j] = r
    return out, residual


def segment_bounds(track):
    """Proximal end: the first tracked level at which her CT radius label has a section (its top is the radial head,
    y 300; above it the crops show the elbow joint); distal end: the last tracked level (before the discs merge into
    the carpus)."""
    js = sorted(track); top = [j for j in js if "radius" in track[j]["ct"] and all(track[j]["found"].values())]
    return (min(top), max(js)) if top else (None, None)


# ----------------------------------------------------------------------------------------------- main
def level_region(t):
    """The muscle mass to split at a tracked level: muscle class closed 1 mm, seams <= 8 mm2 filled, bones out."""
    isl = t["island"]; cl = t["cl"]
    region = ndi.binary_closing(cl["muscle"], iterations=3) & isl
    holes = ndi.binary_fill_holes(region) & ~region; hl, hn = ndi.label(holes)
    if hn:
        hs = ndi.sum(holes, hl, range(1, hn + 1)); small = np.zeros(hn + 1, bool); small[1:] = hs * PX * PX <= 8.0; region |= small[hl]
    bones = np.zeros(isl.shape, bool)
    for b in ("radius", "ulna"):
        if t[b][3] is not None:
            bones |= ndi.binary_dilation(t[b][3], iterations=2)
    return region & ~bones


def level_frame(t, orient_prev):
    U = np.array(t["ulna"][:2]); R = np.array(t["radius"][:2]); isl = t["island"]
    dist_out, idx = ndi.distance_transform_edt(isl, return_indices=True)
    um = t["ulna"][3]
    if um is not None and um.any():
        ys, xs = np.where(um); k = np.argmin(dist_out[ys, xs]); skin = np.array([idx[0][ys[k], xs[k]], idx[1][ys[k], xs[k]]], float) - U
    else:
        ui, uj = int(round(U[0])), int(round(U[1])); skin = np.array([idx[0][ui, uj], idx[1][ui, uj]], float) - U
    e, n, d = bone_frame(U, R, skin)
    if orient_prev is not None and np.dot(n, orient_prev) < 0:
        n = -n                                           # never flips between adjacent levels
    return U, R, e, n, d


def run(a, log=print):
    crops = ArmCrops(a.crops); meshes = load_meshes(a.bones); cache = Path(a.cache) if getattr(a, "cache", None) else None
    if cache and cache.exists():
        import pickle; track, residual = pickle.load(open(cache, "rb")); log(f"bone track from cache {cache}")
    else:
        track, residual = track_bones(crops, meshes, a.anchor, a.j_lo, a.j_hi, log)
        if cache:
            import pickle; pickle.dump((track, residual), open(cache, "wb"), protocol=4)
    j_top, j_bot = segment_bounds(track)
    if j_top is None:
        raise SystemExit("no level with two separate bone discs")
    log(f"segment levels {j_top}..{j_bot}  (atlas y {crops.level(j_top)['y']:.0f} .. {crops.level(j_bot)['y']:.0f})")
    names = list(MARKER_RULES); ids = {nm: i + 1 for i, nm in enumerate(names)}; groups = {nm: MARKER_RULES[nm][5] for nm in names}
    labels_by_level = {}; area = {nm: 0.0 for nm in names}; unassigned = 0.0; orient_prev = None; frames = {}; support = {}
    for j in range(j_top, j_bot + 1):
        t = track.get(j)
        if t is None:
            continue
        U, R, e, n, d = level_frame(t, orient_prev); orient_prev = n; ru, rr = t["ulna"][2], t["radius"][2]
        f = level_fraction(j, j_top, j_bot); frames[j] = {"U": U.tolist(), "R": R.tolist(), "e": e.tolist(), "n": n.tolist(), "f": round(f, 3)}
        region = level_region(t); comp = compartments(region.shape, U, R, ru, rr, e, n)
        th = white_tophat(t["im"].max(-1).astype(np.float32), disk(4))
        seeds = marker_positions(U, R, ru, rr, e, n, f); frames[j]["seeds"] = {nm: [float(p[0]), float(p[1])] for nm, p in seeds.items()}
        cur, left = split_level(th, region, comp, seeds, ids, groups)
        for nm, m in cur.items():
            area[nm] += m.sum() * PX * PX
        unassigned += left.sum() * PX * PX
        for pair, v in boundary_support(th, cur, ids).items():
            support.setdefault(pair, []).append((j,) + v)
        lab = np.zeros(region.shape, np.uint8)
        for nm, m in cur.items():
            lab[m] = ids[nm]
        labels_by_level[j] = lab
        if j % 20 == 0:
            log(f"  level {j} f={f:.2f} y={t['L']['y']:.0f} regions={len(cur)} unassigned={left.sum() * PX * PX:.0f} mm2")
    return crops, track, residual, (j_top, j_bot), labels_by_level, ids, area, unassigned, frames, support


def to_volume(crops, labels_by_level, dx=0.5):
    """Resample the per-level label images onto one RAS grid (dx mm in-plane, 1 mm along z). Returns (vol, affine)."""
    js = sorted(labels_by_level); ext = []
    for j in js:
        lab = labels_by_level[j]; ys, xs = np.where(lab > 0)
        if len(ys) == 0:
            continue
        L = crops.level(j); x, y = crops.px_to_ras(L, [ys.min(), ys.max()], [xs.min(), xs.max()]); ext.append((x.min(), x.max(), y.min(), y.max()))
    ext = np.array(ext); x0, x1 = ext[:, 0].min() - 2, ext[:, 1].max() + 2; y0, y1 = ext[:, 2].min() - 2, ext[:, 3].max() + 2
    zt = np.array([crops.level(j)["z_true"] for j in js]); z0, z1 = np.floor(zt.min()), np.ceil(zt.max())
    nx, ny, nz = int(np.ceil((x1 - x0) / dx)) + 1, int(np.ceil((y1 - y0) / dx)) + 1, int(z1 - z0) + 1
    vol = np.zeros((nx, ny, nz), np.uint8); gx = x0 + dx * np.arange(nx); gy = y0 + dx * np.arange(ny)
    for k in range(nz):
        z = z0 + k; j = js[int(np.argmin(np.abs(zt - z)))]
        if abs(zt[js.index(j)] - z) > 1.0:
            continue
        L = crops.level(j); lab = labels_by_level[j]
        # RAS x = 350 - c, c = (pc + w2)/3*SC + 110 + CS  ->  pc = ((350 - x - 110 - CS) / SC) * 3 - w2 ; rows likewise
        pc = ((350.0 - gx - 110 - L["CS"]) / SC) * 3 - L["w"][2]; pr = (H - 1 - (240.0 - gy - L["RS"]) / SC) * 3 - L["w"][0]
        ci = np.round(pc).astype(int); ri = np.round(pr).astype(int)
        okc = (ci >= 0) & (ci < lab.shape[1]); okr = (ri >= 0) & (ri < lab.shape[0])
        sl = np.zeros((nx, ny), np.uint8)
        sub = lab[np.ix_(ri[okr], ci[okc])]              # (rows, cols)
        sl[np.ix_(okc, okr)] = sub.T
        vol[:, :, k] = sl
    aff = np.array([[dx, 0, 0, x0], [0, dx, 0, y0], [0, 0, 1.0, z0], [0, 0, 0, 1]])
    return vol, aff


def montage(crops, track, labels_by_level, ids, frames, levels, path, colors):
    tiles = []
    for j in levels:
        t = track.get(j); lab = labels_by_level.get(j)
        if t is None or lab is None:
            continue
        im = t["im"].copy(); isl = t["island"]; ys, xs = np.where(isl)
        r0, r1, c0, c1 = max(0, ys.min() - 6), ys.max() + 6, max(0, xs.min() - 6), xs.max() + 6
        for nm, l in ids.items():
            m = lab == l
            if m.any():
                edge = m & ~ndi.binary_erosion(m, iterations=2); im[edge] = colors[l]
        for b in ("radius", "ulna"):
            if t[b][3] is not None:
                e = t[b][3] & ~ndi.binary_erosion(t[b][3], iterations=2); im[e] = (255, 255, 255)
        sub = Image.fromarray(im[r0:r1, c0:c1]); dr = ImageDraw.Draw(sub)
        fr = frames.get(j)
        if fr:
            U = np.array(fr["U"]) - (r0, c0); R = np.array(fr["R"]) - (r0, c0); n = np.array(fr["n"])
            dr.line([(U[1], U[0]), (R[1], R[0])], fill=(255, 255, 255), width=1)
            M = (U + R) / 2; dr.line([(M[1], M[0]), (M[1] + n[1] * 30, M[0] + n[0] * 30)], fill=(0, 255, 255), width=2)
        for nm, p in (fr.get("seeds", {}) if fr else {}).items():
            y, x = p[0] - r0, p[1] - c0; dr.line([(x - 4, y), (x + 4, y)], fill=colors[ids.get(nm, 0)], width=2); dr.line([(x, y - 4), (x, y + 4)], fill=colors[ids.get(nm, 0)], width=2)
        dr.text((3, 3), f"j{j} y{t['L']['y']:.0f} f{fr['f'] if fr else '-'}", fill=(255, 255, 0))
        for nm, l in ids.items():
            m = lab[r0:r1, c0:c1] == l
            if m.sum() > 60:
                cy, cx = np.mean(np.where(m), axis=1); dr.text((cx - 8, cy - 4), nm.split("_")[0][:3] + "".join(w[0] for w in nm.split("_")[1:]), fill=colors[l])
        tiles.append(sub)
    if not tiles:
        return None
    cols = 3; rows = (len(tiles) + cols - 1) // cols; tw = max(t.width for t in tiles); th = max(t.height for t in tiles)
    out = Image.new("RGB", (cols * tw, rows * th))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * tw, (i // cols) * th))
    out.save(path); return str(path)


def palette(n):
    rng = np.random.default_rng(3); cols = {0: (0, 0, 0)}
    base = [(255, 0, 0), (0, 255, 0), (0, 128, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255), (255, 128, 0), (128, 0, 255),
            (0, 255, 128), (255, 128, 128), (128, 255, 0), (0, 128, 128), (255, 0, 128), (128, 128, 255), (200, 200, 0), (0, 200, 100),
            (255, 200, 150), (150, 100, 255), (100, 255, 200), (255, 255, 255)]
    for i in range(1, n + 1):
        cols[i] = base[(i - 1) % len(base)] if i <= len(base) else tuple(int(v) for v in rng.integers(60, 255, 3))
    return cols


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crops", required=True, help="SCRATCH/vh_cryo_f (arm_full_right.npy, arm_full_bbox.json, anchors.json, frame.json)")
    ap.add_argument("--bones", default=str(REPO / "build/vh/ct_vhf_armb"))
    ap.add_argument("--anchor", type=int, default=100, help="crop level where the CT radius and ulna sections seed the bone tracker")
    ap.add_argument("--j-lo", type=int, default=0); ap.add_argument("--j-hi", type=int, default=215)
    ap.add_argument("--out", default=str(REPO / "data/ct_sources/task_outputs/vhf_forearm_muscles_cryo.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / "mappings/vhf_forearm_muscles_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / "mappings/subjects/ct_vhf_forearm_volume_mapping.json"))
    ap.add_argument("--montage-dir", default=None); ap.add_argument("--montage-levels", default="")
    ap.add_argument("--cache", default=None, help="pickle of the bone track (scratch only; speeds up re-runs)")
    ap.add_argument("--merge", default=str(REPO / "scripts/cryo/vhf_forearm_merge.json"),
                    help="JSON {merged_name: [members]} of muscles the photographs do not separate (written to the label key as compartments)")
    a = ap.parse_args(argv)
    crops, track, residual, (j_top, j_bot), labels_by_level, ids, area, unassigned, frames, support = run(a)
    merge_raw = json.load(open(a.merge)) if a.merge and Path(a.merge).exists() else {}
    merge = {k: (v["members"] if isinstance(v, dict) else v) for k, v in merge_raw.items() if not k.startswith("_")}
    merge_note = {k: v.get("note", "") for k, v in merge_raw.items() if isinstance(v, dict)}
    # apply merges: members -> one label (the first member's id), name = merged compartment
    final_ids = dict(ids); final_names = {l: nm for nm, l in ids.items()}; remap = np.arange(max(ids.values()) + 1, dtype=np.uint8)
    for comp, members in merge.items():
        keep = ids[members[0]]
        for mm in members:
            remap[ids[mm]] = keep; final_ids.pop(mm, None)
        final_ids[comp] = keep; final_names[keep] = comp
        for mm in members[1:]:
            final_names.pop(ids[mm], None)
    for j in labels_by_level:
        labels_by_level[j] = remap[labels_by_level[j]]
    vol, aff = to_volume(crops, labels_by_level)
    vox = float(abs(np.linalg.det(aff[:3, :3])))
    vols = {nm: round(float((vol == l).sum() * vox / 1000.0), 1) for nm, l in sorted(final_ids.items(), key=lambda kv: kv[1])}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(vol, aff), a.out)
    colors = palette(len(ids)); mont = []
    if a.montage_dir:
        levels = [int(t) for t in a.montage_levels.split(",")] if a.montage_levels else [int(round(j_top + (j_bot - j_top) * q)) for q in (0.05, 0.2, 0.4, 0.6, 0.8, 0.95)]
        p = montage(crops, track, labels_by_level, final_ids, frames, levels, Path(a.montage_dir) / "forearm_muscles_right.png", colors)
        if p:
            mont.append(p)
    res_summary = {b: {"n_levels": len(v), "mean_mm": [round(float(np.mean([x[0] for x in v.values()])), 1), round(float(np.mean([x[1] for x in v.values()])), 1)],
                       "sd_mm": [round(float(np.std([x[0] for x in v.values()])), 1), round(float(np.std([x[1] for x in v.values()])), 1)],
                       "at_levels": {str(k): v[k] for k in sorted(v) if k % 30 == 10}} for b, v in residual.items()}
    membership = {comp: members for comp, members in merge.items()}
    supp = {f"{p[0]}|{p[1]}": {"levels": len(v), "median_ridge_ratio": round(float(np.median([x[2] for x in v])), 2),
                               "frac_levels_ratio_ge_1.8": round(float(np.mean([x[2] >= 1.8 for x in v])), 2),
                               "contact_mm": round(float(np.mean([x[1] for x in v])) * PX, 1)} for p, v in sorted(support.items()) if len(v) >= 5}
    report = {"_README": [f"Female right forearm muscles from her full-resolution cryosections ({Path(__file__).name}); {BADGE}. "
                          "Bones tracked in the photographs; markers by textbook position rules in the radius-ulna frame; boundaries by a "
                          "marker watershed on the pale fascial septa; muscles the photographs do not separate merged into compartments.",
                          "ct_to_photo_shift_mm: photographed bone disc centre minus the CT section centre, [photo rows, photo cols] in mm, per bone: "
                          "the residual of the CT->cryo registration at the forearm; it varies along the arm, so the CT bones were not used as the frame."],
              "source": SOURCE, "badge": BADGE, "segment_levels": [j_top, j_bot],
              "segment_atlas_y": [round(crops.level(j_top)["y"], 1), round(crops.level(j_bot)["y"], 1)],
              "ct_to_photo_shift_mm": res_summary, "voxel_mm": [float(aff[0, 0]), float(aff[1, 1]), float(aff[2, 2])],
              "volumes_cm3": vols, "unassigned_muscle_cm3": round(unassigned / 1000.0, 1), "merged_compartments": membership,
              "montages": mont, "labels": {str(l): nm for l, nm in sorted(final_names.items())},
              "boundary_support": supp}
    Path(str(a.out).replace(".nii.gz", "_report.json")).write_text(json.dumps(report, indent=1))
    key = {"_README": [f"Label id -> structure for the Visible Human FEMALE right forearm muscle volume ({Path(__file__).name}). A KEY, not data. {BADGE}: "
                       "see the script docstring for the rule; compartments are muscles the photographs do not separate (mapped to null)."],
           "source": SOURCE, "task": "vhf_forearm_muscles", "version": "2026-09-14", "badge": BADGE,
           "labels": {str(l): nm for l, nm in sorted(final_names.items())}, "merged_compartments": membership}
    Path(a.labels_out).write_text(json.dumps(key, indent=1))
    entries = []
    for l, nm in sorted(final_names.items()):
        if nm in merge:
            entries.append({"label": l, "source_structure": nm, "side": "right", "status": "no_atlas_entity", "atlas_id": None,
                            "relationship": "no_usable_label", "note": f"{BADGE}; compartment holding {', '.join(merge[nm])} ({vols.get(nm, 0)} cm3), not split: "
                            f"{merge_note.get(nm, 'the photographs show no septum the watershed could follow between them at most levels')}",
                            "candidates": [m + "_r" for m in merge[nm]]})
        else:
            entries.append({"label": l, "source_structure": nm, "side": "right", "status": "curated", "atlas_id": nm + "_r", "relationship": "exact",
                            "note": f"{BADGE}: position-rule marker in the radius-ulna frame, boundary by the marker watershed on her fascial septa; {vols.get(nm, 0)} cm3."
                                    + (" REVIEW: volume outside 5-45 cm3, the region may hold a neighbour's belly." if not 5.0 <= vols.get(nm, 0) <= 45.0 else ""),
                            "candidates": []})
    Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only."],
                                                "subject": "ct_vhf_forearm", "source_volume": str(Path(a.out).resolve()), "label_map": "vhf_forearm_muscles",
                                                "entries": entries}, indent=2))
    print(json.dumps({"segment": [j_top, j_bot], "volumes_cm3": vols, "unassigned_cm3": round(unassigned / 1000, 1), "residual": res_summary, "montages": mont}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
