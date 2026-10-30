"""Click-to-seed preparation for the MALE right forearm (Q180-prep): five true cross-sections of his forearm,
perpendicular to the Q164 forearm axis, as JPEGs + a pixel <-> frame <-> atlas mapping + expected muscles per level.
Real data only (his photographs, his CT radius/ulna, the Q165 rule labels, the Q166 septum lines); nothing is segmented.

    python3 scripts/cryo/vhm_forearm_seed_sections.py --cryo SCRATCH/vh_cryo_m_forearm_q151 SCRATCH/q164_m_forearm/ext \
        --q164-work SCRATCH/q164_m_forearm/work --rgb-cache SCRATCH/q165_m_forearm/rgb_frame.npy --out SCRATCH/q180

Why: Q164-Q166 (vhm_forearm_muscles_fullres / _v3 / _v4; imported, not edited) could not split his forearm muscles
automatically. Route (1): the owner clicks one point per muscle on ~5 cross-sections; the seeds are later flooded inside
the Q166 septum mask and tracked between sections. This script only prepares the sections the page shows.

WHAT IT DOES
 1. Q164 frame: frame.npz (+ isl.pkl, track.pkl) from --q164-work, rebuilt with Q164's own functions exactly as its
    main() does if absent (no repo output is written). Frame point P(u, s, t) = c + u a + s v1 + t v2 in torso RAS
    (a = unit forearm axis pointing DISTALLY, v1 = RAS x made perpendicular to a, v2 = a x v1), frame grid
    us (1 mm) x ss x ts (0.5 mm); frame index (i, j, k) <-> (us[i], ss[j], ts[k]).
 2. Levels: his CT radius (label 2 of vhm_arm_bones_cryo_completed, resliced in the frame, > 20 voxels per slice =
    Q164's rule) spans u_top..u_bot; sections at FRACTIONS of that length (proximal -> distal), snapped to the 1 mm
    frame slice.
 3. Image: the photograph stack (Q165 build_rgb_stack: his photographs laid in torso RAS with Q164's per-photograph
    registration) sampled TRILINEARLY on the plane at PIX_MM per pixel (a section of his oblique forearm cuts ~70
    photographs, so each image is resliced from many photographs, not one), cropped to the forearm island + MARGIN_MM.
    Orientation (all five): viewed FROM DISTAL looking proximally (the radiological convention), ANTERIOR (flexor /
    palmar side) UP, so for his right forearm the RADIAL side is on the image LEFT. "Anterior" = the normal of the
    ulna->radius line (his CT bone centroids at that level) on the flexor side, the flexor side chosen by Q164's rule
    (the side of the bone line holding more muscle over the whole sections). The labels ANT / POST / RAD / ULN are drawn
    in the margin from the computed directions, so they cannot disagree with the geometry.
 4. Overlay: the Q166 septum lines at that slice (Q166 run() recomputed on a +-7 slice window with Q166's defaults:
    pale 0.10, support 0.5 over +-1 slice, sigma 0.5 mm, h 0.01, axial sigma 1.5 slices; exact for the centre slice),
    skeletonised to 1 px, cyan 50 %; his CT radius (yellow) / ulna (white) outlines.
 5. mapping.json: per section, affine matrices pixel <-> frame (s, t mm and frame index) <-> atlas mm, the pixel size,
    the frame index; self-check: photographed radius/ulna centroids (bone found in the photograph colours near his CT
    bone, Q164's find_bone rule at 0.5 mm) mapped pixel -> atlas against his CT label centroids at that level (voxels
    within 0.5 mm of the plane, an independent code path).
 6. Muscles expected per level: Gray's order, compartment/layer, textbook presence (belly / tendon / edge) from the
    fraction along the radius, and the area of each Q165 rule label on the plane (rule labels, not truth).

Pixel convention: continuous (x, y), x to the right, y DOWN, (0, 0) = the top-left CORNER of the image, so pixel
column j / row i has its centre at (j + 0.5, i + 0.5). A browser click maps as x = offsetX * naturalWidth / clientWidth.
Atlas mm: +X his right, +Y superior, +Z anterior; atlas = (x, z, y)_RAS - (-6.035, -895.476, 4.787) (every ct_vhm_*).
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
import vhm_forearm_muscles_fullres as Q  # noqa: E402  (Q164 frame + registration)

FRACTIONS = (0.15, 0.325, 0.50, 0.675, 0.85)
PIX_MM = 0.2                 # output pixel (his photographs are 0.33 mm in-plane, 1 mm apart)
MARGIN_MM = 5.0
JPEG_QUALITY = 85
MAX_SIDE = 900
WIDE = 90.0                  # mm half-width sampled round the bones for the crop
WIN = 7                      # frame slices each side for the Q166 septum lines (axial Gaussian radius 6)
Q166 = {"pale": 0.10, "support": 0.5, "support_slices": 1, "sigma_mm": 0.5, "h": 0.01, "sigma_u": 1.5}
RELIABLE_INSTANCES = (1655, 1743)   # Q164 report: registration fitted on these photographs; held/interpolated outside
RULE_VOLUME = REPO / "data/ct_sources/task_outputs/vhm_forearm_muscles_v3.nii.gz"
RULE_LABELS = REPO / "mappings/vhm_forearm_muscles_v3_labels.json"

# Gray's order (superficial -> deep within each compartment; the Q165 label order). Presence along the radius
# (0 = radial head, 1 = distal radius): (first, last) level of any muscle or tendon, and the level where the fleshy
# belly ends (tendon distal to it). Textbook approximations (Gray's Anatomy 42e, forearm chapter), NOT measurements.
MUSCLES = [
    # id, compartment, layer, first, last, belly_end
    ("pronator_teres", "anterior (flexor)", "superficial", 0.0, 0.50, 0.42),
    ("flexor_carpi_radialis", "anterior (flexor)", "superficial", 0.0, 1.0, 0.55),
    ("palmaris_longus", "anterior (flexor)", "superficial", 0.0, 1.0, 0.45),
    ("flexor_carpi_ulnaris", "anterior (flexor)", "superficial", 0.0, 1.0, 0.85),
    ("flexor_digitorum_superficialis", "anterior (flexor)", "intermediate", 0.0, 1.0, 0.75),
    ("flexor_digitorum_profundus", "anterior (flexor)", "deep", 0.0, 1.0, 0.80),
    ("flexor_pollicis_longus", "anterior (flexor)", "deep", 0.25, 1.0, 0.85),
    ("pronator_quadratus", "anterior (flexor)", "deep", 0.75, 1.0, 1.0),
    ("brachioradialis", "posterior (extensor), radial group", "superficial", 0.0, 1.0, 0.55),
    ("extensor_carpi_radialis_longus", "posterior (extensor), radial group", "superficial", 0.0, 1.0, 0.35),
    ("extensor_carpi_radialis_brevis", "posterior (extensor), radial group", "superficial", 0.0, 1.0, 0.55),
    ("extensor_digitorum", "posterior (extensor)", "superficial", 0.0, 1.0, 0.75),
    ("extensor_digiti_minimi", "posterior (extensor)", "superficial", 0.0, 1.0, 0.75),
    ("extensor_carpi_ulnaris", "posterior (extensor)", "superficial", 0.0, 1.0, 0.80),
    ("anconeus", "posterior (extensor)", "superficial", 0.0, 0.15, 0.15),
    ("supinator", "posterior (extensor)", "deep", 0.0, 0.33, 0.33),
    ("abductor_pollicis_longus", "posterior (extensor)", "deep", 0.30, 1.0, 0.80),
    ("extensor_pollicis_brevis", "posterior (extensor)", "deep", 0.50, 1.0, 0.85),
    ("extensor_pollicis_longus", "posterior (extensor)", "deep", 0.35, 1.0, 0.80),
    ("extensor_indicis", "posterior (extensor)", "deep", 0.60, 1.0, 0.90),
]
NOTES = {"palmaris_longus": "absent in ~15 % of limbs", "pronator_teres": "inserts mid-lateral radius",
         "anconeus": "proximal ulna only", "supinator": "wraps the proximal third of the radius",
         "pronator_quadratus": "distal quarter only", "extensor_indicis": "distal half only",
         "flexor_pollicis_longus": "arises below the radial tuberosity"}
EDGE = 0.04                  # within this fraction of a first/last level the muscle is "edge" (may or may not show)


# ----------------------------------------------------------------------------------------------- pure helpers
def presence(first, last, belly_end, f, edge=EDGE):
    """'belly' | 'tendon' | 'edge' | None for a muscle at radius fraction f."""
    if f < first - edge or f > last + edge:
        return None
    if f < first + edge or (last < 1.0 and f > last - edge) or abs(f - belly_end) <= edge:
        return "edge"
    return "belly" if f <= belly_end else "tendon"


def expected_muscles(f, rule_area=None):
    """Gray's-order list of dicts for the muscles expected at radius fraction f (rule_area: {name: mm2} on the plane)."""
    out = []
    for nm, comp, layer, f0, f1, fb in MUSCLES:
        p = presence(f0, f1, fb, f)
        ra = (rule_area or {}).get(nm, 0.0)
        if p is None and ra <= 0:
            continue
        out.append({"atlas_id": nm + "_r", "name": nm.replace("_", " "), "compartment": comp, "layer": layer,
                    "textbook": p or "absent", "q165_rule_label_area_mm2": round(float(ra), 1)})
        if nm in NOTES:
            out[-1]["note"] = NOTES[nm]
    return out


def image_axes(n):
    """Image right / down unit vectors in frame (s, t) for anterior direction n (s, t): viewed from DISTAL (view
    direction -a), anterior up: right = n x a = (n_t, -n_s), down = -n (see module docstring; v1 x v2 = a)."""
    n = np.asarray(n, float); n = n / np.linalg.norm(n)
    return np.array([n[1], -n[0]]), -n


def frame_basis(a):
    return Q.frame_basis(np.asarray(a, float))


def ras_to_atlas_matrix():
    """4x4: atlas = M @ [x, y, z, 1]_RAS (axis swap y <-> z + origin)."""
    M = np.zeros((4, 4)); M[0, 0] = 1; M[1, 2] = 1; M[2, 1] = 1; M[3, 3] = 1
    M[:3, 3] = -np.asarray(Q.ORIGIN, float)
    return M


def section_affines(u, corner_st, right, down, pix, c, a, s0_grid, t0_grid, ds, u0_grid, du):
    """All affine maps of one section. Pixel (x, y) continuous, (0, 0) = top-left corner.
    Returns dict of nested lists:
      pixel_to_frame_st (3x3: [s, t, 1] = M @ [x, y, 1]), frame_st_to_pixel (3x3),
      pixel_to_frame_index (4x3: [i, j, k, 1] = M @ [x, y, 1]), frame_index_to_pixel (3x4, i ignored),
      pixel_to_ras (4x3), pixel_to_atlas (4x3: [X, Y, Z, 1] = M @ [x, y, 1]),
      atlas_to_pixel (3x4: [x, y, 1] = M @ [X, Y, Z, 1], orthogonal projection onto the plane),
      atlas_plane_normal_distal (unit), atlas_plane_offset (signed distance of a point = n . X - offset)."""
    right = np.asarray(right, float); down = np.asarray(down, float); cs = np.asarray(corner_st, float)
    P2F = np.array([[pix * right[0], pix * down[0], cs[0]], [pix * right[1], pix * down[1], cs[1]], [0, 0, 1.0]])
    F2P = np.linalg.inv(P2F)
    fi = np.array([[0, 0, (u - u0_grid) / du], [1 / ds, 0, -s0_grid / ds], [0, 1 / ds, -t0_grid / ds], [0, 0, 1.0]])
    P2I = fi @ P2F
    I2F = np.array([[0, ds, 0, s0_grid], [0, 0, ds, t0_grid], [0, 0, 0, 1.0]])   # (s, t, 1) from (i, j, k, 1)
    I2P = F2P @ I2F
    v1, v2 = frame_basis(a); c = np.asarray(c, float); a = np.asarray(a, float)
    F2R = np.zeros((4, 3)); F2R[:3, 0] = v1; F2R[:3, 1] = v2; F2R[:3, 2] = c + u * a; F2R[3, 2] = 1   # [x,y,z,1] from (s,t,1)
    P2R = F2R @ P2F
    P2A = ras_to_atlas_matrix() @ P2R
    cx, cy, off = P2A[:3, 0], P2A[:3, 1], P2A[:3, 2]
    A2P = np.zeros((3, 4)); A2P[0, :3] = cx / pix ** 2; A2P[1, :3] = cy / pix ** 2
    A2P[0, 3] = -cx @ off / pix ** 2; A2P[1, 3] = -cy @ off / pix ** 2; A2P[2, 3] = 1
    nA = (ras_to_atlas_matrix()[:3, :3] @ a)
    return {"pixel_to_frame_st": P2F.tolist(), "frame_st_to_pixel": F2P.tolist(), "pixel_to_frame_index": P2I.tolist(),
            "frame_index_to_pixel": I2P.tolist(), "pixel_to_ras": P2R.tolist(), "pixel_to_atlas": P2A.tolist(),
            "atlas_to_pixel": A2P.tolist(), "atlas_plane_normal_distal": nA.tolist(), "atlas_plane_offset": float(nA @ off)}


def to2(M, pts):
    """Apply a map whose last output row is the homogeneous 1 and drop it."""
    M = np.asarray(M, float); p = np.atleast_2d(np.asarray(pts, float))
    return (np.hstack([p, np.ones((len(p), 1))]) @ M.T)[:, :-1]


def crop_box(st_pts, right, down, margin):
    """Top-left corner (s, t) and (W, H) mm of the image box holding st_pts (N, 2) + margin in the image axes."""
    p = np.asarray(st_pts, float); xr = p @ np.asarray(right, float); yd = p @ np.asarray(down, float)
    x0, x1 = xr.min() - margin, xr.max() + margin; y0, y1 = yd.min() - margin, yd.max() + margin
    corner = x0 * np.asarray(right, float) + y0 * np.asarray(down, float)
    return corner, (x1 - x0, y1 - y0)


def template_shift(bright, ct_mask, max_px=16, ring=(1, 4)):
    """Where does his CT bone section sit best on the PHOTOGRAPHED bone? Score of an integer shift (dy, dx) = mean of
    `bright` (photographed non-muscle: cryo classes fat/pale/white, his marrow + cortex) inside the shifted CT mask minus
    its mean in a ring ring[0]..ring[1] px outside it. Returns (dy, dx, best score, score at 0)."""
    from scipy import ndimage as ndi
    br = np.asarray(bright, float); ct = np.asarray(ct_mask, bool)
    rg = ndi.binary_dilation(ct, iterations=ring[1]) & ~ndi.binary_dilation(ct, iterations=ring[0])
    best = (-np.inf, 0, 0); s0 = None
    for dy in range(-max_px, max_px + 1):
        for dx in range(-max_px, max_px + 1):
            m = np.roll(ct, (dy, dx), (0, 1)); r = np.roll(rg, (dy, dx), (0, 1))
            sc = float(br[m].mean() - br[r].mean())
            if dy == 0 and dx == 0:
                s0 = sc
            if sc > best[0] + 1e-12 or (abs(sc - best[0]) <= 1e-12 and dy * dy + dx * dx < best[1] ** 2 + best[2] ** 2):
                best = (sc, dy, dx)
    return best[1], best[2], best[0], s0


# ----------------------------------------------------------------------------------------------- data stages
def ensure_q164(work, cryo, bones):
    """frame.npz (and isl.pkl / track.pkl) from Q164's work dir, rebuilt with Q164's functions as its main() if absent."""
    W = Path(work); W.mkdir(parents=True, exist_ok=True); p = W / "frame.npz"
    if p.exists() and (W / "isl.pkl").exists() and (W / "track.pkl").exists():
        return dict(np.load(p))
    if not cryo:
        raise SystemExit(f"{W} lacks frame.npz/isl.pkl/track.pkl and no --cryo given to rebuild them")
    ph = Q.Photos(*cryo)
    q = W / "isl.pkl"; isl = pickle.load(open(q, "rb")) if q.exists() else Q.islands(ph); pickle.dump(isl, open(q, "wb"), protocol=4)
    q = W / "track.pkl"; tr = pickle.load(open(q, "rb")) if q.exists() else Q.track(ph, bones, isl); pickle.dump(tr, open(q, "wb"), protocol=4)
    if p.exists():
        return dict(np.load(p))
    T, _rel = Q.smooth_translation(tr, ph.n)
    st = Q.build_stack(ph, isl, T); c, ax = Q.forearm_axis(bones, -810, -600)
    R, (us, ss, ts) = Q.reslice({"muscle": st["muscle"], "island": st["island"], "tophat": st["tophat"].astype(np.float32)}, st["grid"], c, ax, (-150, 170), 60, orders={"tophat": 1})
    del st
    F = dict(R, B=Q.reslice_bones(bones, c, ax, us, ss, ts), us=us, ss=ss, ts=ts, c=c, a=ax); np.savez_compressed(p, **F)
    return F


def flexor_sign(F, i_top, i_bot):
    """Q164 segment_frame's flexor-side rule: +1 if the side of the ulna->radius line at +90 deg (in frame index
    (j, k) coords) holds more muscle, summed over the whole sections; else -1."""
    from scipy import ndimage as ndi
    isl, mus, B = F["island"], F["muscle"], F["B"]; side = [0.0, 0.0]
    yy, xx = np.mgrid[0:isl.shape[1], 0:isl.shape[2]]
    for i in range(i_top, i_bot + 1):
        if not ((B[i] == 2).sum() > 20 and (B[i] == 3).sum() > 20 and isl[i].any()):
            continue
        complete = not ndi.binary_erosion(isl[i], iterations=1).sum() < 0.5 * isl[i].sum() and \
            not (isl[i][0].any() or isl[i][-1].any() or isl[i][:, 0].any() or isl[i][:, -1].any())
        if not complete:
            continue
        U = np.array(ndi.center_of_mass(B[i] == 3)); R = np.array(ndi.center_of_mass(B[i] == 2)); e = (R - U) / np.linalg.norm(R - U)
        nn = np.array([-e[1], e[0]]); tt = (yy - U[0]) * nn[0] + (xx - U[1]) * nn[1]; m = mus[i] & isl[i]
        side[0] += float((m & (tt > 0)).sum()); side[1] += float((m & (tt < 0)).sum())
    return (1.0 if side[0] >= side[1] else -1.0), round(max(side) / max(min(side), 1.0), 2)


def septum_slice(rgbw, islw, Bw, k0, ds):
    """Q166 septum lines + tissue of the centre slice k0 of a frame window (rgb (n, ns, nt, 3) nearest-resliced)."""
    from scipy import ndimage as ndi
    import vhm_forearm_muscles_v3 as V
    import vhm_forearm_muscles_v4 as V4
    from cryo_classes import classify as classify_m
    cls = V.classify_frame(rgbw, classify_m)
    bone = np.stack([ndi.binary_dilation(Bw[k] > 0, iterations=2) for k in range(len(Bw))])
    tis = V.tissue_map(cls, islw, bone)
    pres = np.stack([V.paleness_residual(rgbw[k], islw[k]) for k in range(len(rgbw))]).astype(np.float32)
    pale = (pres >= Q166["pale"]) & (tis > 0)
    sup = ndi.maximum_filter(pale, size=(2 * Q166["support_slices"] + 1, 3, 3))
    pflood = ndi.gaussian_filter1d(pres, Q166["sigma_u"], axis=0)
    musc = tis[k0] == V.TISSUE["muscle"]
    lines, nb = V4.slice_septa(musc, pflood[k0], sup[k0], Q166["support"], Q166["sigma_mm"] / ds, Q166["h"])
    return lines, tis[k0], cls[k0], nb


def sample_stack_rgb(chans, grid, P):
    """Trilinear RGB of the torso-RAS photograph stack at RAS points P (..., 3)."""
    from scipy.ndimage import map_coordinates
    k, r, cc = Q.stack_index(P[..., 0], P[..., 1], P[..., 2], grid)
    return np.stack([np.clip(map_coordinates(ch, [k, r, cc], order=1, mode="constant", cval=0), 0, 255) for ch in chans], -1).astype(np.uint8)


def sample_ct_bones(bones, P):
    from scipy.ndimage import map_coordinates
    return map_coordinates(bones, [Q.BONES_AFF[0] - P[..., 0], Q.BONES_AFF[1] - P[..., 1], P[..., 2] - Q.BONES_AFF[2]], order=0, mode="constant", cval=0)


def ct_centroid_on_plane(bones, label, c, a, u, half=0.5):
    """Atlas centroid of his CT label voxels whose centre lies within `half` mm of the plane u (independent path)."""
    ii, jj, kk = np.where(bones == label)
    P = np.stack([Q.BONES_AFF[0] - ii, Q.BONES_AFF[1] - jj, Q.BONES_AFF[2] + kk], 1).astype(float)
    d = (P - c) @ a - u; m = np.abs(d) <= half
    if not m.any():
        return None, 0
    return Q.ras_to_atlas(*P[m].mean(0)).tolist(), int(m.sum())


def draw_labels(img, right, down, e_st, n_st):
    """ANT / POST / RAD / ULN in the margins at the image edges, placed by the computed directions."""
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(img); W, H = img.size
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    def put(vec_st, text):
        vx, vy = float(np.dot(vec_st, right)), float(np.dot(vec_st, down)); L = max(abs(vx), abs(vy))
        vx, vy = vx / L, vy / L
        bb = d.textbbox((0, 0), text, font=font); tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x = W / 2 + vx * (W / 2 - tw / 2 - 3) - tw / 2; y = H / 2 + vy * (H / 2 - th / 2 - 4) - th / 2
        d.text((x, y), text, font=font, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    put(n_st, "ANT"); put(-np.asarray(n_st), "POST"); put(e_st, "RAD"); put(-np.asarray(e_st), "ULN")


def save_jpeg(img, path):
    img.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return round(Path(path).stat().st_size / 1024, 1)


# ----------------------------------------------------------------------------------------------- main
def main(argv=None):
    import nibabel as nib
    from PIL import Image
    from scipy import ndimage as ndi
    from skimage.measure import find_contours
    from skimage.morphology import skeletonize
    import vhm_forearm_muscles_v3 as V
    import vhm_forearm_muscles_v4 as V4
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cryo", nargs="+", required=True, help="photograph caches (as Q164/Q165)")
    ap.add_argument("--q164-work", required=True, help="Q164 work dir (frame.npz, isl.pkl, track.pkl; rebuilt if absent)")
    ap.add_argument("--rgb-cache", default=None, help="optional Q165 rgb_frame.npy, only to verify the resliced window")
    ap.add_argument("--bones", default=str(REPO / "data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    O = Path(a.out); O.mkdir(parents=True, exist_ok=True)
    bones = np.asanyarray(nib.load(a.bones).dataobj)
    F = ensure_q164(a.q164_work, a.cryo, bones)
    us, ss, ts, c, ax = F["us"], F["ss"], F["ts"], np.asarray(F["c"], float), np.asarray(F["a"], float)
    ds = float(ss[1] - ss[0]); du = float(us[1] - us[0]); B = F["B"]; isl3 = F["island"]
    rad = [i for i in range(len(us)) if (B[i] == 2).sum() > 20]
    i_top, i_bot = min(rad), max(rad); u_top, u_bot = float(us[i_top]), float(us[i_bot]); L = u_bot - u_top
    sign, flex_ratio = flexor_sign(F, i_top, i_bot)
    print(f"radius u {u_top:.0f}..{u_bot:.0f} mm (length {L:.0f}); flexor sign {sign:+.0f} (muscle ratio {flex_ratio})")
    # photograph stack (Q165 builder, Q164 registration)
    ph = Q.Photos(*a.cryo); isl = pickle.load(open(Path(a.q164_work) / "isl.pkl", "rb")); tr = pickle.load(open(Path(a.q164_work) / "track.pkl", "rb"))
    T, rel = Q.smooth_translation(tr, ph.n); del tr
    st, grid = V.build_rgb_stack(ph, isl, T); del isl
    chans = [np.ascontiguousarray(st[..., ch]) for ch in range(3)]
    occ = np.ascontiguousarray(np.any(st > 0, -1).astype(np.uint8) * 255)          # photographed-island occupancy
    print(f"stack {st.shape}")
    cache = np.load(a.rgb_cache, mmap_mode="r") if a.rgb_cache and Path(a.rgb_cache).exists() else None
    rule_key = {int(k): v for k, v in json.load(open(RULE_LABELS))["labels"].items()}
    v1, v2 = frame_basis(ax)
    sections = []
    for n_sec, frac in enumerate(FRACTIONS, 1):
        i = int(round((u_top + frac * L - us[0]) / du)); u = float(us[i]); f_act = (u - u_top) / L
        # --- orientation from his CT bones at this slice (frame index coords (j, k) == (s, t) directions)
        U = np.array(ndi.center_of_mass(B[i] == 3)); R = np.array(ndi.center_of_mass(B[i] == 2))
        e = (R - U) / np.linalg.norm(R - U); n = sign * np.array([-e[1], e[0]])
        right, down = image_axes(n)
        # --- crop: the forearm island at this slice (0.5 mm cells, corners included)
        # (the Q164 frame is +-60 mm and cuts his widest sections, so the crop comes from the photographed island
        #  sampled +-WIDE mm round the bone midpoint: the component holding the midpoint)
        mid = np.array([ss[0], ts[0]]) + ds * (U + R) / 2; g = np.arange(-WIDE, WIDE + 1e-6, ds)
        GX, GY = np.meshgrid(g, g); stw = mid + GX[..., None] * right + GY[..., None] * down
        Pw = c + u * ax + stw[..., :1] * v1 + stw[..., 1:] * v2
        occw = sample_stack_rgb([occ], grid, Pw)[..., 0] > 127; lw, _ = ndi.label(occw); cw = lw == lw[len(g) // 2, len(g) // 2]
        stp = np.concatenate([stw[cw] + np.array([dx, dy]) for dx in (-ds / 2, ds / 2) for dy in (-ds / 2, ds / 2)])
        whole = not (cw[0].any() or cw[-1].any() or cw[:, 0].any() or cw[:, -1].any())
        in_frame = not (isl3[i][0].any() or isl3[i][-1].any() or isl3[i][:, 0].any() or isl3[i][:, -1].any())
        corner, (wmm, hmm) = crop_box(stp, right, down, MARGIN_MM)
        pix = max(PIX_MM, max(wmm, hmm) / MAX_SIDE); Wd, Hd = int(math.ceil(wmm / pix)), int(math.ceil(hmm / pix))
        M = section_affines(u, corner, right, down, pix, c, ax, float(ss[0]), float(ts[0]), ds, float(us[0]), du)
        xg, yg = np.meshgrid(np.arange(Wd) + 0.5, np.arange(Hd) + 0.5)
        P = to2(M["pixel_to_ras"], np.stack([xg.ravel(), yg.ravel()], 1)).reshape(Hd, Wd, 3)
        rgb = sample_stack_rgb(chans, grid, P)
        # --- which photographs this section cuts
        inside = sample_stack_rgb([occ], grid, P)[..., 0] > 127
        zs = P[..., 2][inside]; inst = (Q.Z_OF_INST - zs)
        inst_rng = [int(np.floor(inst.min())), int(np.ceil(inst.max()))]
        in_rel = float(((inst >= RELIABLE_INSTANCES[0]) & (inst <= RELIABLE_INSTANCES[1])).mean())
        # --- Q166 septum lines on the frame window
        w0, w1 = i - WIN, i + WIN + 1
        rgbw = V.reslice_rgb(st, grid, c, ax, us[w0:w1], ss, ts)
        same = float((cache[i] == rgbw[WIN]).all(-1).mean()) if cache is not None else None
        lines, tis_i, cls_i, nbasins = septum_slice(rgbw, isl3[w0:w1], B[w0:w1], WIN, ds)
        I = to2(M["pixel_to_frame_index"], np.stack([xg.ravel(), yg.ravel()], 1)).reshape(Hd, Wd, 3)
        jn = np.clip(np.rint(I[..., 1] - 0.0).astype(int), 0, len(ss) - 1); kn = np.clip(np.rint(I[..., 2]).astype(int), 0, len(ts) - 1)
        okg = (I[..., 1] > -0.5) & (I[..., 1] < len(ss) - 0.5) & (I[..., 2] > -0.5) & (I[..., 2] < len(ts) - 0.5)
        sep_img = skeletonize(lines[jn, kn] & okg)
        # --- CT bone outlines at image resolution
        bl = sample_ct_bones(bones, P)
        outlines = {}
        for nm, lab in Q.BONE_ID.items():
            sm = ndi.gaussian_filter((bl == lab).astype(np.float32), 1.0 / pix)
            outlines[nm] = [cc[:, ::-1] + 0.5 for cc in find_contours(sm, 0.5) if len(cc) > 8]   # (x, y) px
        # --- images
        base = Image.fromarray(rgb)
        plain = base.copy(); draw_labels(plain, right, down, e, n)
        ov = Image.new("RGBA", base.size, (0, 0, 0, 0)); px = np.zeros((Hd, Wd, 4), np.uint8)
        px[sep_img] = (0, 255, 255, 128); ov = Image.fromarray(px, "RGBA")
        from PIL import ImageDraw
        dd = ImageDraw.Draw(ov)
        for nm, col in (("radius", (255, 220, 0, 200)), ("ulna", (255, 255, 255, 200))):
            for cc in outlines[nm]:
                dd.line([tuple(p) for p in cc] + [tuple(cc[0])], fill=col, width=1)
        over = Image.alpha_composite(base.convert("RGBA"), ov).convert("RGB"); draw_labels(over, right, down, e, n)
        tag = f"L{n_sec}_{int(round(f_act * 1000)) / 10:g}pct".replace(".", "p")
        f_plain, f_over = f"section_{tag}.jpg", f"section_{tag}_septa.jpg"
        kb = save_jpeg(plain, O / f_plain); kb2 = save_jpeg(over, O / f_over)
        # --- self-check: photographed bones (0.5 mm frame slice colours) vs his CT labels on the plane
        br = np.isin(cls_i, (2, 4, 5)) & isl3[i]
        chk = {}
        for nm, lab in Q.BONE_ID.items():
            ct_c = np.array(ndi.center_of_mass(B[i] == lab))                            # frame index (j, k)
            ct_atlas, nvox = ct_centroid_on_plane(bones, lab, c, ax, u)
            row = {"ct_label_centroid_atlas_mm": np.round(ct_atlas, 2).tolist() if ct_atlas else None, "ct_voxels_within_0p5mm": nvox}
            # (a) mapping: CT section centroid (resliced label) frame index -> pixel -> atlas vs the 3-D voxel centroid
            ct_px = to2(M["frame_index_to_pixel"], [[i, ct_c[0], ct_c[1]]])[0]
            ct_px_atlas = to2(M["pixel_to_atlas"], [ct_px])[0]
            row.update(ct_section_centroid_pixel=np.round(ct_px, 2).tolist(), ct_section_centroid_pixel_to_atlas_mm=np.round(ct_px_atlas, 2).tolist(),
                       mapping_error_mm=round(float(np.linalg.norm(ct_px_atlas - ct_atlas)), 2) if ct_atlas else None)
            # (b) photograph: the CT section shifted onto the photographed bone (0.5 mm frame slice, +-8 mm)
            dy, dx, sc, sc0 = template_shift(br, B[i] == lab)
            ph_c = ct_c + np.array([dy, dx]); p_px = to2(M["frame_index_to_pixel"], [[i, ph_c[0], ph_c[1]]])[0]
            p_at = to2(M["pixel_to_atlas"], [p_px])[0]
            off = float(np.hypot(dy, dx) * ds)
            row.update(photo_centroid_pixel=np.round(p_px, 2).tolist(), photo_centroid_atlas_mm=np.round(p_at, 2).tolist(),
                       photo_vs_ct_mm=round(float(np.linalg.norm(p_at - ct_atlas)), 2) if ct_atlas else None,
                       photo_shift_frame_mm=round(off, 2), fit_score=round(sc, 3), fit_score_unshifted=round(sc0, 3),
                       within_2mm=bool(off <= 2.0 and row["mapping_error_mm"] is not None and row["mapping_error_mm"] <= 2.0))
            chk[nm] = row
        # --- Q165 rule labels on the plane (0.5 mm frame slice) and the expected list
        rl = V4.sample_rule_labels(RULE_VOLUME, (1, len(ss), len(ts)), np.array([u]), ss, ts, c, ax)[0]
        area = {rule_key[l]: float(((rl == l) & isl3[i]).sum() * ds * ds) for l in np.unique(rl) if l in rule_key}
        mus = expected_muscles(f_act, area)
        ctr_px = to2(M["frame_index_to_pixel"], [[i, (U[0] + R[0]) / 2, (U[1] + R[1]) / 2]])[0]
        corners = to2(M["pixel_to_atlas"], [[0, 0], [Wd, 0], [0, Hd], [Wd, Hd]])
        sec = {"id": f"L{n_sec}", "radius_fraction_target": frac, "radius_fraction": round(f_act, 4), "frame_index_i": i, "frame_u_mm": u,
               "atlas_y_mm_at_bone_midpoint": round(float(to2(M["pixel_to_atlas"], [ctr_px])[0][1]), 1),
               "atlas_y_mm_range_over_image": [round(float(corners[:, 1].min()), 1), round(float(corners[:, 1].max()), 1)],
               "bone_midpoint_pixel": np.round(ctr_px, 1).tolist(),
               "image": {"file": f_plain, "file_septa": f_over, "width": Wd, "height": Hd, "pixel_mm": pix, "kb": kb, "kb_septa": kb2},
               "orientation": {"view": "from distal (looking proximally)", "up": "anterior (flexor/palmar)", "radial_side": "left" if float(np.dot(e, right)) < 0 else "right",
                               "anterior_st": np.round(n, 4).tolist(), "ulna_to_radius_st": np.round(e, 4).tolist(),
                               "image_right_st": np.round(right, 4).tolist(), "image_down_st": np.round(down, 4).tolist()},
               "photographs": {"instances_cut": inst_rng, "share_of_section_on_reliably_registered_photos": round(in_rel, 3),
                               "reliable_instances": list(RELIABLE_INSTANCES)},
               "whole_section_in_image": bool(whole), "whole_section_in_q164_frame": bool(in_frame),
               "q166_septa": {"watershed_basins": int(nbasins), "line_px_0p5mm": int(lines.sum()),
                              "window_equal_to_q165_rgb_cache": same},
               "tissue_share_mm2": {k: round(float((tis_i == v).sum() * ds * ds), 1) for k, v in V.TISSUE.items() if v},
               "maps": M, "self_check": chk, "muscles_expected": mus}
        sections.append(sec)
        print(f"{sec['id']} f {f_act:.3f} u {u:.0f} i {i}: {Wd}x{Hd} px @ {pix} mm, {kb} / {kb2} KB, photos {inst_rng} ({in_rel:.2f} reliable), "
              f"radial {sec['orientation']['radial_side']}, whole {whole}/{in_frame}, cache-equal {same}; "
              + ", ".join(f"{b}: photo-CT {r.get('photo_vs_ct_mm')} map {r['mapping_error_mm']}" for b, r in chk.items()))
    out = {"_README": ["Q180-prep: five cross-sections of the Visible Human MALE right forearm for owner click-to-seed. Real data; see README.md.",
                       "Pixel (x, y): continuous, x right, y DOWN, (0,0) = top-left CORNER of the JPEG; pixel centre = (col + 0.5, row + 0.5).",
                       "Matrices act on homogeneous column vectors: out = M @ [in..., 1]; the last output row is the homogeneous 1.",
                       "pixel_to_atlas: [X, Y, Z, 1] = M @ [x, y, 1]; atlas_to_pixel: [x, y, 1] = M @ [X, Y, Z, 1] (orthogonal projection onto the plane).",
                       "pixel_to_frame_st: [s, t, 1] = M @ [x, y, 1] (Q164 frame mm at the section's u); pixel_to_frame_index: [i, j, k, 1] = M @ [x, y, 1]."],
           "script": "scripts/cryo/vhm_forearm_seed_sections.py", "source_series": "IDC 4aaf9181-fb6a-4a4c-bf49-d1eb9ed4a385",
           "atlas_convention": "+X his right, +Y superior, +Z anterior; atlas = (x, z, y)_RAS - (-6.035, -895.476, 4.787)",
           "q164_frame": {"centre_ras": c.tolist(), "axis_unit_ras_distal": ax.tolist(), "v1_ras": v1.tolist(), "v2_ras": v2.tolist(),
                          "point": "P_ras = c + u a + s v1 + t v2", "u0_mm": float(us[0]), "du_mm": du, "s0_mm": float(ss[0]), "t0_mm": float(ts[0]), "ds_mm": ds,
                          "shape": list(B.shape), "ras_to_atlas_4x4": ras_to_atlas_matrix().tolist()},
           "radius": {"u_top_mm": u_top, "u_bot_mm": u_bot, "length_mm": L, "frame_i_top": i_top, "frame_i_bot": i_bot,
                      "rule": "his CT radius label resliced in the Q164 frame, > 20 voxels per 1 mm slice (Q164 segment rule)"},
           "flexor_side": {"sign": sign, "muscle_ratio_flexor_over_extensor": flex_ratio, "rule": "Q164: side of the ulna->radius line with more muscle"},
           "muscle_presence": "textbook ranges along the radius (Gray's Anatomy; approximations in the script's MUSCLES table): belly / tendon / edge (near a start, end or belly-tendon junction) / absent; plus the area of each Q165 RULE label on the plane (rule-based, not traced)",
           "q166_parameters": Q166, "pixel_mm_target": PIX_MM, "margin_mm": MARGIN_MM,
           "registration_note": f"Q164 per-photograph translation fitted on instances {RELIABLE_INSTANCES[0]}-{RELIABLE_INSTANCES[1]}; held constant beyond",
           "sections": sections}
    (O / "mapping.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {O / 'mapping.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
