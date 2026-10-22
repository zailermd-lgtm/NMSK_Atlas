"""Q186b: can HER OWN CT skin replace the male-shaped breast + perineal skin of the female Z-Anatomy viewer?

The female Z-Anatomy skin is Z-Anatomy's male region patches fitted to her skeleton (Q168).  Z-Anatomy has no
female breast or perineal skin; her CT body surface (build/vh/ct_vhf_skin) has.  This script MEASURES both
regions and applies the ship gate; it only ever writes the report (data/derived/Q186b_her_skin_transfer.json).

  chest      footprint = the 8 chest patches (mammary, inframammary, pectoral, presternal, l+r), chart = cylinder
             around her trunk axis (angle x radius, height)
  perineum   footprint = the opening the dropped male-only urogenital patches leave, chart = plan view from below

Per region: footprint area, 3-D distance fitted skin <-> her skin (median/p90/max), volume between the two
outer surfaces, and the SEAM offset (her surface minus the neighbouring Z-Anatomy skin surface, radial in the chart,
on a 2-4 mm ring just outside the footprint).  A her-skin patch can only be joined to the neighbours with a
BOUNDED, FOLD-GUARDED radial blend (|shift| <= SEAM_BOUND_MM, ramp slope <= SLOPE_DEG, so ramp width
W = 1.5*|offset|/tan(SLOPE_DEG)); anything larger needs a fabricated ramp or a change to neighbouring (non-chest,
non-perineal) skin, so the gate refuses to ship.

Run: python3 scripts/zanatomy/her_skin_transfer_q186b.py   (rebuilds the Q168 fit in memory, ~2 min, writes no viewer)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
CELL = 1.0                      # chart raster cell, mm
SEAM_BOUND_MM = 15.0            # largest radial shift a blend may apply at the seam
SLOPE_DEG = 30.0                # steepest allowed blend ramp (fold guard: normals turn at most this much)
MIN_SEAM_FRACTION = 0.90        # share of the seam that must be within the bound
MIN_FREE_AREA = 0.25            # share of the her-skin patch that must stay un-displaced after the ramp
CHEST_IDS = [f"zan_skin_{p}_region_{s}" for p in ("mammary", "inframammary", "pectoral", "presternal") for s in "lr"]
OUT_JSON = REPO / "data" / "derived" / "Q186b_her_skin_transfer.json"


# ----------------------------------------------------------------------------------- charts
class CylChart:
    """a = R0*theta (0 anterior, + towards +x), b = y, r = distance from the trunk axis x = 0, z = zc(y)."""

    def __init__(self, ys, zc, R0=150.0):
        self.ys, self.zc, self.R0 = np.asarray(ys), np.asarray(zc), R0

    def forward(self, V):
        dx, dz = V[:, 0], V[:, 2] - np.interp(V[:, 1], self.ys, self.zc)
        return np.stack([self.R0 * np.arctan2(dx, dz), V[:, 1], np.hypot(dx, dz)], 1)


class PlanChart:
    """Plan view from below: (a, b) = (x, z), r = -y (more inferior = larger)."""

    def forward(self, V):
        return np.stack([V[:, 0], V[:, 2], -V[:, 1]], 1)


def trunk_chart(her_v, y_lo, y_hi, half_x=120.0):
    ys = np.arange(y_lo - 40, y_hi + 41, 10.0)
    zc = np.full(len(ys), np.nan)
    for i, y in enumerate(ys):
        m = (np.abs(her_v[:, 1] - y) < 6) & (np.abs(her_v[:, 0]) < half_x)
        if m.sum() > 20:
            zc[i] = 0.5 * (her_v[m, 2].max() + her_v[m, 2].min())
    ok = ~np.isnan(zc)
    zc = np.interp(ys, ys[ok], zc[ok])
    return CylChart(ys, np.convolve(np.pad(zc, 2, mode="edge"), np.ones(5) / 5, mode="valid"))


# ----------------------------------------------------------------------------------- rasterising
def raster_max(P, depth, F, lo, shape, cell=CELL):
    """Per-cell maximum of the linearly interpolated `depth` over triangles F drawn in the plane P (n,2).
    Returns (map, covered); cells no triangle covers hold -inf."""
    H, W = shape
    out = np.full(H * W, -np.inf)
    x = (P[:, 0] - lo[0]) / cell - 0.5
    y = (P[:, 1] - lo[1]) / cell - 0.5
    tx, ty, tz = x[F], y[F], depth[F]
    x0, x1 = np.floor(tx.min(1)).astype(int), np.ceil(tx.max(1)).astype(int)
    y0, y1 = np.floor(ty.min(1)).astype(int), np.ceil(ty.max(1)).astype(int)
    inside = (x1 >= 0) & (x0 <= W - 1) & (y1 >= 0) & (y0 <= H - 1)
    x0, y0, x1, y1 = x0.clip(0, W - 1), y0.clip(0, H - 1), x1.clip(0, W - 1), y1.clip(0, H - 1)
    size = np.maximum(x1 - x0, y1 - y0) + 1
    bounds = [0, 4, 8, 16, 32, 10 ** 9]
    for lo_s, hi_s in zip(bounds[:-1], bounds[1:]):
        sel = np.nonzero(inside & (size > lo_s) & (size <= hi_s))[0]
        if not len(sel):
            continue
        n = int(size[sel].max())
        off = np.arange(n)
        for s in range(0, len(sel), max(1, 4_000_000 // (n * n))):
            t = sel[s:s + max(1, 4_000_000 // (n * n))]
            gx = x0[t][:, None, None] + off[None, :, None] + 0 * off[None, None, :]
            gy = y0[t][:, None, None] + 0 * off[None, :, None] + off[None, None, :]
            (ax, bx, cx), (ay, by, cy) = (tx[t, i][:, None, None] for i in range(3)), (ty[t, i][:, None, None] for i in range(3))
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            ok = np.abs(d) > 1e-12
            d = np.where(ok, d, 1.0)
            w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d
            w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / d
            w2 = 1 - w0 - w1
            m = (ok & (w0 >= -1e-3) & (w1 >= -1e-3) & (w2 >= -1e-3) & (gx <= x1[t][:, None, None])
                 & (gy <= y1[t][:, None, None]) & (gx < W) & (gy < H))
            z = w0 * tz[t, 0][:, None, None] + w1 * tz[t, 1][:, None, None] + w2 * tz[t, 2][:, None, None]
            np.maximum.at(out, (gy * W + gx)[m], z[m])
    out = out.reshape(H, W)
    return out, np.isfinite(out)


# ----------------------------------------------------------------------------------- gate
def ship_gate(seam_offsets_mm, footprint_dist_mm, bound=SEAM_BOUND_MM, slope_deg=SLOPE_DEG):
    """seam_offsets_mm: |her surface - neighbour surface| at seam ring cells; footprint_dist_mm: for every
    footprint cell its [distance to the seam, |offset| of the nearest seam cell].  Returns (ship, why)."""
    off = np.abs(np.asarray(seam_offsets_mm, float))
    frac = float((off <= bound).mean()) if len(off) else 0.0
    dist, near_off = (np.asarray(footprint_dist_mm, float)[:, i] for i in (0, 1))
    width = 1.5 * near_off / np.tan(np.radians(slope_deg))        # ramp width needed for a <= slope_deg ramp
    free = float((dist >= width).mean()) if len(dist) else 0.0
    why = []
    if frac < MIN_SEAM_FRACTION:
        why.append(f"only {frac:.0%} of the seam is within the {bound:g} mm blend bound (need {MIN_SEAM_FRACTION:.0%})")
    if free < MIN_FREE_AREA:
        why.append(f"a <= {slope_deg:g} deg ramp leaves only {free:.1%} of her patch un-displaced (need {MIN_FREE_AREA:.0%})")
    return (not why), why, {"seam_fraction_within_bound": round(frac, 3), "free_area_fraction": round(free, 3)}


def _stats(a):
    a = np.asarray(a, float)
    return {"median": round(float(np.median(a)), 1), "p90": round(float(np.percentile(a, 90)), 1),
            "max": round(float(a.max()), 1)}


def _footprint_stats(mask, Pm, Fn_ring_depth, ring, cell, dist_extra=None):
    """Seam offsets (her - neighbour) on the ring and the (distance-to-seam, nearest offset) pair per footprint cell."""
    ok = ring & np.isfinite(Fn_ring_depth) & np.isfinite(Pm)
    seam = (Pm - Fn_ring_depth)[ok]
    idx = ndi.distance_transform_edt(~ok, return_indices=True)[1]          # nearest valid seam cell
    near_off = np.abs((Pm - Fn_ring_depth)[idx[0], idx[1]])
    dist = ndi.distance_transform_edt(mask) * cell
    return seam, np.stack([dist[mask], near_off[mask]], 1)


# ----------------------------------------------------------------------------------- measurement
def measure_chest(patches, her_v, her_f):
    import trimesh
    ch = trunk_chart(her_v, 280, 570)
    lo, hi = np.array([-300.0, 270.0]), np.array([300.0, 580.0])
    shape = (int((hi[1] - lo[1]) / CELL), int((hi[0] - lo[0]) / CELL))
    C = ch.forward(her_v)
    m = (np.abs(C[:, 0]) < 310) & (C[:, 1] > 260) & (C[:, 1] < 590)
    Pm, _ = raster_max(C[:, :2], C[:, 2], her_f[m[her_f].all(1)], lo, shape)
    rem = [k for k in sorted(patches) if k in CHEST_IDS]
    nb = [k for k in sorted(patches) if k not in CHEST_IDS]

    def cat(keys):
        vs, fs, o = [], [], 0
        for k in keys:
            vs.append(patches[k][0])
            fs.append(patches[k][1] + o)
            o += len(vs[-1])
        return np.vstack(vs), np.vstack(fs)

    RV, RF = cat(rem)
    NV, NF = cat(nb)

    def rast(V, F):
        c = ch.forward(V)
        mm = (np.abs(c[:, 0]) < 310) & (c[:, 1] > 260) & (c[:, 1] < 590)
        return raster_max(c[:, :2], c[:, 2], F[mm[F].all(1)], lo, shape)[0]

    Fm, Fn = rast(RV, RF), rast(NV, NF)
    mask = ndi.binary_fill_holes(ndi.binary_closing(np.isfinite(Fm), iterations=3))
    ring = ndi.binary_dilation(mask, iterations=4) & ~ndi.binary_dilation(mask, iterations=2)
    seam, fdist = _footprint_stats(mask, Pm, Fn, ring, CELL)
    # 3-D distances: her front-facing skin inside the footprint -> fitted patches; fitted vertices -> her skin
    iy, ix = ((C[:, 1] - lo[1]) / CELL).astype(int), ((C[:, 0] - lo[0]) / CELL).astype(int)
    okc = (ix >= 0) & (ix < shape[1]) & (iy >= 0) & (iy < shape[0])
    ins = np.zeros(len(her_v), bool)
    ins[okc] = mask[iy[okc], ix[okc]]
    hn = trimesh.Trimesh(her_v, her_f, process=False).vertex_normals
    radial = np.stack([np.sin(C[:, 0] / ch.R0), 0 * C[:, 0], np.cos(C[:, 0] / ch.R0)], 1)
    ins &= (np.abs(C[:, 0]) < ch.R0 * 1.4) & ((hn * radial).sum(1) > 0.3)
    fit_mesh = trimesh.Trimesh(RV, RF, process=False)
    d_her = trimesh.proximity.closest_point(fit_mesh, her_v[ins])[1]
    d_fit = cKDTree(her_v).query(RV)[0]
    both = mask & np.isfinite(Pm) & np.isfinite(Fm)
    gap = Pm[both] - Fm[both]
    vol_between = float((0.5 * (Pm[both] ** 2 - Fm[both] ** 2) * (CELL / ch.R0) * CELL).sum())
    shell_vol = sum(trimesh.Trimesh(*patches[k][:2], process=False).volume for k in rem)
    ship, why, gate = ship_gate(seam, fdist)
    return {"region": "chest (breast)", "replaces": rem, "footprint_area_mm2": int(mask.sum()),
            "her_vertices_in_footprint": int(ins.sum()),
            "dist_her_skin_to_fitted_patches_mm": _stats(d_her), "dist_fitted_vertices_to_her_skin_mm": _stats(d_fit),
            "radial_gap_her_minus_fitted_mm": {**_stats(gap), "min": round(float(gap.min()), 1)},
            "volume_between_outer_surfaces_mL": round(vol_between / 1e3, 1),
            "fitted_chest_shell_volume_mL": round(shell_vol / 1e3, 1),
            "seam_offset_her_minus_neighbour_mm": {**_stats(np.abs(seam)), "signed_median": round(float(np.median(seam)), 1),
                                                   "signed_min": round(float(seam.min()), 1), "signed_max": round(float(seam.max()), 1)},
            "max_inscribed_radius_mm": round(float(fdist[:, 0].max()), 1),
            "gate": gate, "ship": bool(ship), "why_not": why}


def measure_perineum(patches, her_v, her_f):
    ch = PlanChart()
    lo, shape = np.array([-220.0, -160.0]), (320, 440)

    def rast(V, F):
        c = ch.forward(V)
        c[:, 2] = np.minimum(c[:, 2], 200)
        m = (V[:, 1] > -200) & (V[:, 1] < 10) & (np.abs(V[:, 0]) < 230)
        return raster_max(c[:, :2], c[:, 2], F[m[F].all(1)], lo, shape)

    Pm, cov = rast(her_v, her_f)
    vs, fs, o = [], [], 0
    for k in sorted(patches):
        vs.append(patches[k][0])
        fs.append(patches[k][1] + o)
        o += len(vs[-1])
    Fm, covf = rast(np.vstack(vs), np.vstack(fs))
    X, Z = np.meshgrid(np.arange(shape[1]) + lo[0] + 0.5, np.arange(shape[0]) + lo[1] + 0.5)
    win = (np.abs(X) <= 75) & (Z >= 15) & (Z <= 75)
    lab, _ = ndi.label(~covf & cov & win)
    mask = lab == lab[int(45 - lo[1]), int(0 - lo[0])]       # the opening under the pubis, centred on x=0, z=45
    ring = ndi.binary_dilation(mask, iterations=4) & ~ndi.binary_dilation(mask, iterations=2)
    seam, fdist = _footprint_stats(mask, Pm, np.where(covf, Fm, np.nan), ring, CELL)
    ship, why, gate = ship_gate(seam, fdist)
    return {"region": "perineum (opening left by the dropped male-only urogenital patches)",
            "footprint_area_mm2": int(mask.sum()), "footprint_x_mm": [float(X[mask].min()), float(X[mask].max())],
            "footprint_z_mm": [float(Z[mask].min()), float(Z[mask].max())],
            "seam_offset_her_minus_neighbour_mm": {**_stats(np.abs(seam)), "signed_median": round(float(np.median(seam)), 1),
                                                   "signed_min": round(float(seam.min()), 1), "signed_max": round(float(seam.max()), 1)},
            "max_inscribed_radius_mm": round(float(fdist[:, 0].max()), 1),
            "gate": gate, "ship": bool(ship), "why_not": why}


def capture_fitted_skin():
    """{patch id: (verts, faces)} of the female Z-Anatomy skin after the Q168 fit (build aborted right after)."""
    sys.path.insert(0, str(REPO))
    from scripts.zanatomy import build_zan_atlas_viewer as B
    got, orig = {}, B.fit_to_vhf

    def hook(pending):
        orig(pending)
        got.update({p["mesh_id"]: (p["v"].copy(), p["f"].copy()) for p in pending if p["cat"] == "skin"})
        raise StopIteration

    B.fit_to_vhf = hook
    try:
        B.main(["--external-bin", "--target-body", "vhf", "-o", "build/viewer_zan_female_q186b/_capture.html",
                "--q162-report", "/dev/null", "--report", "/dev/null"])
    except StopIteration:
        pass
    finally:
        B.fit_to_vhf = orig
    return got, B.load_her_skin(), B


def main():
    patches, her, B = capture_fitted_skin()
    sub, hv = her
    from scripts.transfer import zan_to_vhf_whole_body as Q168
    hf = np.fromfile(Q168.VH_DIR / sub / "faces.u32", dtype="<u4").reshape(-1, 3)
    rep = {"source": "Q186b: her own CT skin (%s) vs the female Z-Anatomy fitted skin; scripts/zanatomy/her_skin_transfer_q186b.py" % sub,
           "limits": {"seam_bound_mm": SEAM_BOUND_MM, "slope_deg": SLOPE_DEG, "min_seam_fraction": MIN_SEAM_FRACTION,
                      "min_free_area": MIN_FREE_AREA},
           "chest": measure_chest(patches, hv.astype(np.float64), hf),
           "perineum": measure_perineum(patches, hv.astype(np.float64), hf)}
    rep["shipped"] = rep["chest"]["ship"] or rep["perineum"]["ship"]
    OUT_JSON.write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
