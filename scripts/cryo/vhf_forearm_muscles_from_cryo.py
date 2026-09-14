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
  bones    = pale compact blobs (fill-holed, 30-900 mm2, solidity >= 0.6) enclosed by the closed muscle mass,
             tracked level to level from the CT-seeded level (nearest blob within 6 mm; a lost bone keeps its
             last position for up to 8 levels); the segment runs from the first level where the radius and ulna are
             two separate discs (radial head) to the last level with both discs before the carpals;
  frame    = e: ulna -> radius unit vector, n: its perpendicular pointing AWAY from the ulna's subcutaneous border
             (the male's compartment rule: the ulna's posterior border lies under the skin, so that side is
             extensor); f = level fraction along the segment (0 radial head, 1 distal radius);
  markers  = MARKER_RULES: per muscle a position in the bone frame (mm from the bone centres, the disc radii
             added) and the f-window in which it is seeded (textbook belly extent); once a muscle has a region,
             its marker at the next level is that region eroded 2 mm (tracking), the rule seed only starts it;
  split    = marker watershed on the white top-hat (disk 4 px) of the brightness inside the muscle mass (closed
             1 mm, seams <= 8 mm2 filled, bones out): the pale fascial septa are the ridges. A region may not
             move more than 3 mm per level from its previous region (a new one: 10 mm around its seed); pixels
             nobody may claim stay unassigned. A muscle with no region for > 10 levels ends.
Boundaries the photographs do not show are not invented: the muscles whose watershed split is not a visible
septum are MERGED into named compartments (see MERGE and the mapping notes) and mapped to null.
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
    "pronator_teres":                 ("R", +6, +8, 0.00, 0.40, "flexor"),
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
    "supinator":                      ("R", +2, -3, 0.00, 0.28, "extensor"),
    "abductor_pollicis_longus":       ("M", +5, -5, 0.35, 0.80, "extensor"),
    "extensor_pollicis_brevis":       ("M", +9, -4, 0.55, 0.85, "extensor"),
    "extensor_pollicis_longus":       ("M", -3, -5, 0.40, 0.85, "extensor"),
    "extensor_indicis":               ("M", -6, -4, 0.60, 0.92, "extensor"),
}
TRACK_BEYOND = 0.15          # a region is still tracked this far (in f) past its seeding window
ERODE_PX, MAX_MOVE_PX, NEW_ZONE_PX, SEED_PX = 6, 9, 30, 5
LOST_LEVELS = 10


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
        w = self.level(j)["w"]; return np.asarray(self.a[j, :w[1] - w[0], :w[3] - w[2]])

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


def bone_candidates(cl, isl, open_px=10, skin_mm=8.0):
    """Bone discs in the photograph: the pale class opened by a 3.3 mm disc (breaks the neck where the ulna's
    subcutaneous border joins the fat under the skin), blobs >= 20 mm2 whose centre lies >= 8 mm from the skin and
    whose box-solidity is >= 0.5 (a disc, not a strand of fascia), grown back 3.3 mm into the pale class but not into
    the 5 mm fat layer under the skin; 30-900 mm2. [(cy, cx, area_px, mask)]"""
    dist = ndi.distance_transform_edt(isl); ring = dist <= skin_mm * 0.625 / PX      # the fat layer under the skin (5 mm)
    core = ndi.binary_opening(cl["pale"] & isl, structure=disk(open_px)); lab, n = ndi.label(core); out = []
    for i in range(1, n + 1):
        m = lab == i; a = int(m.sum())
        if a * PX * PX < 20:
            continue
        ys, xs = np.where(m); cy, cx = ys.mean(), xs.mean()
        if dist[int(cy), int(cx)] * PX < skin_mm:
            continue
        box = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
        if a / box < 0.5:
            continue
        full = ndi.binary_fill_holes(ndi.binary_dilation(m, structure=disk(open_px)) & cl["pale"] & ~ring | m)
        af = int(full.sum())
        if af * PX * PX < 30 or af * PX * PX > 900:
            continue
        ys, xs = np.where(full); out.append((ys.mean(), xs.mean(), af, full))
    return out


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
def snap(pt, region, max_px=15):
    r, c = int(round(pt[0])), int(round(pt[1]))
    if 0 <= r < region.shape[0] and 0 <= c < region.shape[1] and region[r, c]:
        return r, c
    win = region[max(r - max_px, 0):r + max_px + 1, max(c - max_px, 0):c + max_px + 1]
    if not win.any():
        return None
    ys, xs = np.where(win); ys = ys + max(r - max_px, 0); xs = xs + max(c - max_px, 0)
    k = np.argmin(np.hypot(ys - r, xs - c))
    return (int(ys[k]), int(xs[k])) if np.hypot(ys[k] - r, xs[k] - c) <= max_px else None


def split_level(th, region, prev, seeds, ids):
    """Marker watershed of `region` on top-hat `th`. prev: {name: mask} of the previous level; seeds: {name: (r, c)}
    for muscles that may start here. Returns {name: mask}, unassigned mask."""
    markers = np.zeros(region.shape, np.int32); allowed = {}
    for name in ids:
        m = None
        if name in prev and prev[name] is not None and prev[name].any():
            e = ndi.binary_erosion(prev[name], iterations=ERODE_PX) & region
            m = e if e.any() else (prev[name] & region)
            if m.any():
                allowed[name] = ndi.binary_dilation(prev[name], iterations=MAX_MOVE_PX)
        if (m is None or not m.any()) and name in seeds:
            p = snap(seeds[name], region & (markers == 0))
            if p is not None:
                m = np.zeros(region.shape, bool); m[p] = True; m = ndi.binary_dilation(m, iterations=SEED_PX) & region & (markers == 0)
                z = np.zeros(region.shape, bool); z[p] = True; allowed[name] = ndi.binary_dilation(z, iterations=NEW_ZONE_PX)
        if m is not None and m.any():
            markers[m & (markers == 0)] = ids[name]
    if not markers.any():
        return {}, region.copy()
    ws = watershed(th, markers, mask=region); res = np.zeros_like(ws)
    for name, l in ids.items():
        if name in allowed:
            res[(ws == l) & allowed[name]] = l
    left = region & (res == 0)
    if left.any():
        ws2 = watershed(th, res, mask=region)
        for name, l in ids.items():
            if name in allowed:
                res[left & (ws2 == l) & allowed[name]] = l
    out = {name: res == l for name, l in ids.items() if (res == l).any()}
    return out, region & (res == 0)


# ----------------------------------------------------------------------------------------------- bone tracking
def nearest_blob(cands, ref, max_mm=6.0):
    best = None
    for cy, cx, a, m in cands:
        d = np.hypot(cy - ref[0], cx - ref[1]) * PX
        if d <= max_mm and (best is None or d < best[0]):
            best = (d, cy, cx, a, m)
    return best


def track_bones(crops, meshes, j_anchor, j_lo, j_hi, log=print):
    """Bone discs per level: {j: {'radius': (cy, cx, r_px, mask), 'ulna': ..., 'island': mask, 'lost': {...}}}.
    Seeded at j_anchor from the CT sections; tracked outward in both directions."""
    out = {}
    L = crops.level(j_anchor); im = crops.image(j_anchor); se = sections(meshes, crops, L, im.shape[:2])
    if "radius_r" not in se or "ulna_r" not in se:
        raise SystemExit(f"no CT radius+ulna section at anchor level {j_anchor}")
    cent = {b: tuple(np.mean(np.where(se[b + "_r"]), axis=1)) for b in ("radius", "ulna")}
    ref = tuple(np.mean([cent["radius"], cent["ulna"]], axis=0))
    residual = {}

    def one(j, prev):
        L = crops.level(j); im = crops.image(j); isl, er = island_mask(im, prev["ref"])
        if isl is None:
            return None
        cl = classes(im, isl); cands = bone_candidates(cl, isl); rec = {"island": isl, "erode": er, "lost": {}, "cl": cl, "im": im, "L": L}
        for b in ("radius", "ulna"):
            hit = nearest_blob(cands, prev[b][:2], 6.0 if prev["found"][b] else 9.0)
            if hit is None:
                rec[b] = (prev[b][0], prev[b][1], prev[b][2], None); rec["lost"][b] = prev["lost"].get(b, 0) + 1
            else:
                d, cy, cx, a, m = hit; rec[b] = (cy, cx, np.sqrt(a / np.pi), m); rec["lost"][b] = 0
        rec["found"] = {b: rec[b][3] is not None for b in ("radius", "ulna")}
        rec["ref"] = tuple(np.mean([rec["radius"][:2], rec["ulna"][:2]], axis=0))
        se = sections(meshes, crops, L, im.shape[:2], ("radius_r", "ulna_r"))
        for b in ("radius", "ulna"):
            if b + "_r" in se and rec["found"][b]:
                c = np.mean(np.where(se[b + "_r"]), axis=1)
                residual.setdefault(b, {})[j] = [round(float((rec[b][0] - c[0]) * PX), 1), round(float((rec[b][1] - c[1]) * PX), 1)]
        return rec

    prev0 = {"ref": ref, "radius": cent["radius"] + (0,), "ulna": cent["ulna"] + (0,), "found": {"radius": False, "ulna": False}, "lost": {}}
    rec = one(j_anchor, prev0)
    if rec is None or not all(rec["found"].values()):
        raise SystemExit("bones not found in the photograph at the anchor level")
    out[j_anchor] = rec
    for rng in (range(j_anchor - 1, j_lo - 1, -1), range(j_anchor + 1, j_hi + 1)):
        prev = out[j_anchor]
        for j in rng:
            r = one(j, prev)
            if r is None or max(r["lost"].values()) > 8:
                log(f"  bone track stops at level {j} ({'no island' if r is None else 'bone lost'})"); break
            out[j] = r; prev = r
    return out, residual


def segment_bounds(track):
    """First level (proximal) where radius and ulna are two separate found discs, last level (distal) with both found."""
    js = sorted(track)
    both = [j for j in js if all(track[j]["found"].values()) and not (track[j]["radius"][3] & track[j]["ulna"][3]).any()
            and np.hypot(track[j]["radius"][0] - track[j]["ulna"][0], track[j]["radius"][1] - track[j]["ulna"][1]) * PX > 8]
    return (min(both), max(both)) if both else (None, None)


# ----------------------------------------------------------------------------------------------- main
def run(a):
    crops = ArmCrops(a.crops); meshes = load_meshes(a.bones); log = print
    track, residual = track_bones(crops, meshes, a.anchor, a.j_lo, a.j_hi, log)
    j_top, j_bot = segment_bounds(track)
    if j_top is None:
        raise SystemExit("no level with two separate bone discs")
    log(f"segment levels {j_top}..{j_bot}  (atlas y {crops.level(j_top)['y']:.0f} .. {crops.level(j_bot)['y']:.0f})")
    names = list(MARKER_RULES); ids = {nm: i + 1 for i, nm in enumerate(names)}
    prev = {}; lost = {nm: 0 for nm in names}; ended = set(); started = set()
    labels_by_level = {}; area = {nm: 0.0 for nm in names}; unassigned = 0.0; orient_prev = None; frames = {}
    for j in range(j_top, j_bot + 1):
        t = track.get(j)
        if t is None:
            continue
        isl = t["island"]; cl = t["cl"]; im = t["im"]
        U = np.array(t["ulna"][:2]); R = np.array(t["radius"][:2]); ru, rr = t["ulna"][2], t["radius"][2]
        dist_out, idx = ndi.distance_transform_edt(isl, return_indices=True)
        ui, uj = int(round(U[0])), int(round(U[1])); skin = np.array([idx[0][ui, uj], idx[1][ui, uj]], float) - U if isl[ui, uj] else np.array([1.0, 0.0])
        # the nearest skin point of the ulna: use the skin point nearest the ulna's DISC (its boundary), not its centre
        um = t["ulna"][3] if t["ulna"][3] is not None else None
        if um is not None:
            ys, xs = np.where(um); k = np.argmin(dist_out[ys, xs]); skin = np.array([idx[0][ys[k], xs[k]], idx[1][ys[k], xs[k]]], float) - U
        e, n, d = bone_frame(U, R, skin)
        if orient_prev is not None and np.dot(n, orient_prev) < 0:
            n = -n                                       # never flips between adjacent levels
        orient_prev = n
        f = level_fraction(j, j_top, j_bot); frames[j] = {"U": U.tolist(), "R": R.tolist(), "e": e.tolist(), "n": n.tolist(), "f": round(f, 3)}
        bones = np.zeros(isl.shape, bool)
        for b in ("radius", "ulna"):
            if t[b][3] is not None:
                bones |= ndi.binary_dilation(t[b][3], iterations=2)
        region = ndi.binary_closing(cl["muscle"], iterations=3) & isl
        holes = ndi.binary_fill_holes(region) & ~region; hl, hn = ndi.label(holes)
        if hn:
            hs = ndi.sum(holes, hl, range(1, hn + 1)); small = np.zeros(hn + 1, bool); small[1:] = hs * PX * PX <= 8.0; region |= small[hl]
        region &= ~bones
        th = white_tophat(im.max(-1).astype(np.float32), disk(4))
        seeds = {}
        for nm, p in marker_positions(U, R, ru, rr, e, n, f).items():
            if nm not in ended:
                seeds[nm] = p
        active = {nm for nm in names if nm not in ended and (nm in seeds or (nm in started and f <= MARKER_RULES[nm][4] + TRACK_BEYOND))}
        cur, left = split_level(th, region, {nm: prev.get(nm) for nm in active}, {nm: seeds[nm] for nm in seeds if nm in active}, {nm: ids[nm] for nm in active})
        for nm in names:
            if nm in cur:
                started.add(nm); lost[nm] = 0; area[nm] += cur[nm].sum() * PX * PX
            elif nm in started and nm not in ended:
                lost[nm] += 1
                if lost[nm] > LOST_LEVELS:
                    ended.add(nm)
        unassigned += left.sum() * PX * PX
        lab = np.zeros(isl.shape, np.uint8)
        for nm, m in cur.items():
            lab[m] = ids[nm]
        labels_by_level[j] = lab; prev = {nm: cur.get(nm) for nm in names}
        if j % 20 == 0:
            log(f"  level {j} f={f:.2f} y={t['L']['y']:.0f} regions={len(cur)} unassigned={left.sum() * PX * PX:.0f} mm2")
    return crops, track, residual, (j_top, j_bot), labels_by_level, ids, area, unassigned, frames


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
    ap.add_argument("--merge", default=str(REPO / "scripts/cryo/vhf_forearm_merge.json"),
                    help="JSON {merged_name: [members]} of muscles the photographs do not separate (written to the label key as compartments)")
    a = ap.parse_args(argv)
    crops, track, residual, (j_top, j_bot), labels_by_level, ids, area, unassigned, frames = run(a)
    merge = json.load(open(a.merge)) if a.merge and Path(a.merge).exists() else {}
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
    report = {"_README": [f"Female right forearm muscles from her full-resolution cryosections ({Path(__file__).name}); {BADGE}. "
                          "Bones tracked in the photographs; markers by textbook position rules in the radius-ulna frame; boundaries by a "
                          "marker watershed on the pale fascial septa; muscles the photographs do not separate merged into compartments.",
                          "ct_to_photo_shift_mm: photographed bone disc centre minus the CT section centre (rows +posterior->anterior?, cols), per bone: "
                          "the residual of the CT->cryo registration at the forearm; it varies along the arm, so the CT bones were not used as the frame."],
              "source": SOURCE, "badge": BADGE, "segment_levels": [j_top, j_bot],
              "segment_atlas_y": [round(crops.level(j_top)["y"], 1), round(crops.level(j_bot)["y"], 1)],
              "ct_to_photo_shift_mm": res_summary, "voxel_mm": [float(aff[0, 0]), float(aff[1, 1]), float(aff[2, 2])],
              "volumes_cm3": vols, "unassigned_muscle_cm3": round(unassigned / 1000.0, 1), "merged_compartments": membership,
              "montages": mont, "labels": {str(l): nm for l, nm in sorted(final_names.items())}}
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
                            "relationship": "no_usable_label", "note": f"Compartment holding {', '.join(merge[nm])}: the photographs show no septum the "
                            f"watershed could follow between them at most levels, so no boundary is invented. {vols.get(nm, 0)} cm3.", "candidates": [m + "_r" for m in merge[nm]]})
        else:
            entries.append({"label": l, "source_structure": nm, "side": "right", "status": "curated", "atlas_id": nm + "_r", "relationship": "exact",
                            "note": f"{BADGE}: position-rule marker in the radius-ulna frame, boundary by the marker watershed on her fascial septa; {vols.get(nm, 0)} cm3.",
                            "candidates": []})
    Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only."],
                                                "subject": "ct_vhf_forearm", "source_volume": str(Path(a.out).resolve()), "label_map": "vhf_forearm_muscles",
                                                "entries": entries}, indent=2))
    print(json.dumps({"segment": [j_top, j_bot], "volumes_cm3": vols, "unassigned_cm3": round(unassigned / 1000, 1), "residual": res_summary, "montages": mont}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
