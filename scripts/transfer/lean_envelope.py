"""Lean-tissue envelopes of the lower limb, per level and direction.

The bone-driven affine puts a transferred muscle at the right height and
orientation on the other body, but keeps the donor's soft-tissue thickness
around the bone. The two donors differ exactly there (the female's anterior
thigh is 56 mm deep where the male's is 95 mm, and 58 % of hers is fat), so
each vertex is re-placed radially: its fraction of the distance from the
bone centre to the outer boundary of the muscle compartment ("lean
envelope") on the source body is kept on the target body.

Source (male): the envelope is the outer boundary of his own segmented
lower-limb muscles at each level (max radius per angular bin about the
femur/tibia centre). Target (female): her muscle compartment is read off
her registered cryosection colour classes as a fraction of her skin radius
per direction, then applied to her measured skin mesh. Levels are 10 mm
apart, 36 angular bins, femur-centred above the knee, tibia-centred below.
Everything here is measured; nothing is a textbook value.
"""
from __future__ import annotations

import json
import numpy as np

SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), male and female CT and "
          "cryosections via the NCI Imaging Data Commons; lower-limb geometry Andreassen et al. 2023, Sci Data 10:34, "
          "doi:10.1038/s41597-022-01905-2 (CC BY 4.0). Derived data (scripts/transfer/lean_envelope.py).")
NBINS = 36
STEP_MM = 10.0
BAND_MM = 6.0
TOP_MM = -20.0          # above this (hip region) the transfer stays bone-driven
BLEND_MM = 40.0         # fade the envelope correction in over this height below TOP_MM


def angle_bins(theta):
    return ((theta + np.pi) / (2 * np.pi) * NBINS).astype(int) % NBINS


def circular_smooth(r, k=1):
    out = r.copy()
    for _ in range(k):
        out = (np.roll(out, 1) + out + np.roll(out, -1)) / 3.0
    return out


def fill_gaps(r):
    """Replace NaN bins by circular interpolation of the neighbours."""
    if np.all(np.isnan(r)):
        return r
    idx = np.arange(len(r)); ok = ~np.isnan(r)
    return np.interp(idx, idx[ok], r[ok], period=len(r))


def midline_x(bones, y):
    """x halfway between the two legs' bone centres at level y (the ray/points stop there)."""
    cs = []
    for side in "rl":
        for b in (bones[f"femur_{side}"], bones[f"tibia_{side}"]):
            sel = np.abs(b[:, 1] - y) < BAND_MM
            if sel.sum() >= 8:
                cs.append(float(b[sel, 0].mean())); break
    return float(np.mean(cs)) if len(cs) == 2 else 0.0


def levels_for(bones, side):
    """Level table for one side: y -> (centre_x, centre_z, bone_id), femur above the knee, tibia below."""
    fem, tib = bones[f"femur_{side}"], bones[f"tibia_{side}"]
    tib_top = float(tib[:, 1].max()); fem_bot = float(fem[:, 1].min())
    knee = (tib_top + fem_bot) / 2
    ys = np.arange(TOP_MM, float(tib[:, 1].min()) + 10, -STEP_MM)
    out = {}
    for y in ys:
        b = fem if y > knee else tib
        sel = np.abs(b[:, 1] - y) < BAND_MM
        if sel.sum() < 8:
            continue
        out[float(y)] = (float(b[sel, 0].mean()), float(b[sel, 2].mean()), "femur" if y > knee else "tibia")
    return out


def envelope_from_points(pts, centre, y, band=BAND_MM, reduce="max", same_side_x=None):
    """Radius per angular bin (max, or min = nearest surface) of points within +-band of level y, about
    centre (x, z). same_side_x: keep only points on the centre's side of that x (the other leg is excluded)."""
    sel = np.abs(pts[:, 1] - y) < band
    if same_side_x is not None:
        sel &= (pts[:, 0] - same_side_x) * (centre[0] - same_side_x) > 0
    p = pts[sel]
    r2 = np.full(NBINS, np.nan)
    if len(p) == 0:
        return r2
    dx, dz = p[:, 0] - centre[0], p[:, 2] - centre[1]
    rad = np.hypot(dx, dz); b = angle_bins(np.arctan2(dz, dx))
    for i in range(NBINS):
        m = b == i
        if m.any():
            r2[i] = rad[m].max() if reduce == "max" else rad[m].min()
    return r2


def source_envelopes(muscle_pts_by_side, bones, side):
    """Male: per level, the outer boundary of his own lower-limb muscles (both bodies' atlas frame)."""
    lv = levels_for(bones, side)
    pts = muscle_pts_by_side[side]
    tab = {}
    for y, (cx, cz, which) in lv.items():
        r = envelope_from_points(pts, (cx, cz), y)
        tab[y] = {"centre": [cx, cz], "bone": which, "r": circular_smooth(fill_gaps(r)).tolist()}
    return tab


def frame_y_correction(y, corr):
    """anatomy_y = frame_y + d(y): d from data/derived/vhf_cryo_frame_y_correction.json (0 = none)."""
    if not corr:
        return 0.0
    dl, yl = corr["legs"]["d_mm"], corr["legs"]["valid_below_y"]
    dt, yt = corr["torso"]["d_mm"], corr["torso"]["valid_above_y"]
    if y >= yt:
        return dt
    if y <= yl:
        return dl
    return dt + (dl - dt) * (yt - y) / (yt - yl)


def photo_slice_of(y, frame, oy, corr=None):
    """Frame slice index showing anatomy at atlas height y."""
    return int(round(y - frame_y_correction(y, corr) + oy - frame["z0"]))


def target_envelopes_from_cryo(cls, frame, origin, skin_pts, bones, side, muscle_class=3, corr=None):
    """Female: per level, her muscle-compartment radius per direction = (last muscle-class pixel /
    last tissue pixel along the ray, in her photographs) x her skin-mesh radius in that direction."""
    z0 = frame["z0"]; ox, oy, oz = origin
    lv = levels_for(bones, side)
    tab = {}
    thetas = (np.arange(NBINS) + 0.5) / NBINS * 2 * np.pi - np.pi
    for y, (cx, cz, which) in lv.items():
        k = photo_slice_of(y, frame, oy, corr)
        if not (2 <= k < cls.shape[0] - 2):
            continue
        sl = np.asarray(cls[k - 2:k + 3])
        muscle = (sl == muscle_class).sum(axis=0) >= 3
        tissue = (sl > 0).sum(axis=0) >= 3
        # photograph pixel of the bone centre: RAS x = 350 - col, RAS y = 240 - row (frame convention)
        c_col = 350.0 - (cx + ox); c_row = 240.0 - (cz + oz)
        mid = midline_x(bones, y)
        mid_col = 350.0 - (mid + ox)
        skin_r = envelope_from_points(skin_pts, (cx, cz), y, reduce="min", same_side_x=mid)
        q = np.full(NBINS, np.nan)
        for i, th in enumerate(thetas):
            # atlas direction (cos th along +x right, sin th along +z anterior) -> photo (col decreases, row decreases)
            steps = np.arange(0, 400, 0.5)
            cols = np.rint(c_col - steps * np.cos(th)).astype(int); rows = np.rint(c_row - steps * np.sin(th)).astype(int)
            ok = (cols >= 0) & (cols < sl.shape[2]) & (rows >= 0) & (rows < sl.shape[1])
            ok &= (cols - mid_col) * (c_col - mid_col) > 0          # never cross into the other leg
            if ok.sum() < 10:
                continue
            cols, rows, st = cols[ok], rows[ok], steps[ok]
            # stop at the first gap in tissue of >= 3 mm (gelatin)
            t = tissue[rows, cols]; m = muscle[rows, cols]
            end = len(t)
            run = 0
            for g in range(len(t)):
                run = run + 1 if not t[g] else 0
                if run >= 6 and g > 20:
                    end = g - run + 1; break
            t = t[:end]; m = m[:end]; st = st[:end]
            if t.sum() < 10:
                continue
            r_skin = st[np.where(t)[0][-1]]
            if m.sum() < 3:
                continue
            r_lean = st[np.where(m)[0][-1]]
            q[i] = min(1.0, r_lean / max(r_skin, 1e-3))
        q = circular_smooth(fill_gaps(q))
        skin_r = circular_smooth(fill_gaps(skin_r))
        tab[y] = {"centre": [cx, cz], "bone": which, "q": q.tolist(), "skin_r": skin_r.tolist(),
                  "r": (q * skin_r).tolist(), "photo_slice": k}
    return tab


def _lookup(tab, y):
    ys = np.array(sorted(tab));
    if len(ys) == 0:
        return None
    i = int(np.argmin(np.abs(ys - y)))
    return tab[float(ys[i])]


def apply_envelope(v_src, v_bone, src_tab, dst_tab):
    """Re-place vertices radially. v_src: source positions (male frame); v_bone: after the bone-driven
    blend (target frame). Returns corrected positions and the mean radial fraction used."""
    out = v_bone.copy()
    ys_s = np.array(sorted(src_tab)); ys_d = np.array(sorted(dst_tab))
    fr_all = []
    for n in range(len(v_src)):
        ys, yd = v_src[n, 1], v_bone[n, 1]
        if yd > TOP_MM or ys > TOP_MM or len(ys_s) == 0 or len(ys_d) == 0:
            continue
        s = src_tab[float(ys_s[np.argmin(np.abs(ys_s - ys))])]
        d = dst_tab[float(ys_d[np.argmin(np.abs(ys_d - yd))])]
        cs, cd = s["centre"], d["centre"]
        dxs, dzs = v_src[n, 0] - cs[0], v_src[n, 2] - cs[1]
        rs = np.hypot(dxs, dzs); bs = angle_bins(np.array([np.arctan2(dzs, dxs)]))[0]
        Rs = s["r"][bs]
        if not np.isfinite(Rs) or Rs <= 1e-3:
            continue
        frac = rs / Rs
        dxd, dzd = v_bone[n, 0] - cd[0], v_bone[n, 2] - cd[1]
        thd = np.arctan2(dzd, dxd); bd = angle_bins(np.array([thd]))[0]
        Rd = d["r"][bd]
        if not np.isfinite(Rd) or Rd <= 1e-3:
            continue
        r_new = frac * Rd
        w = min(1.0, (TOP_MM - yd) / BLEND_MM)     # fade in below the hip region
        r_old = np.hypot(dxd, dzd)
        r_mix = (1 - w) * r_old + w * r_new
        out[n, 0] = cd[0] + r_mix * np.cos(thd); out[n, 2] = cd[1] + r_mix * np.sin(thd)
        fr_all.append(frac)
    return out, (float(np.mean(fr_all)) if fr_all else None)


def save(tab_by_side, path, meta):
    js = {"_README": meta, "source": SOURCE, "sides": {s: {str(y): v for y, v in t.items()} for s, t in tab_by_side.items()}}
    json.dump(js, open(path, "w"), indent=0)


def load(path):
    js = json.load(open(path))
    return {s: {float(y): v for y, v in t.items()} for s, t in js["sides"].items()}
