"""Q383 -- objective measures on one simulated frame (the dB image, its label / structure rasters and its raster plan).

All measures are taken on the frame's own rasters: an interface is where the page's meshes say it is (a change of structure id or
of tissue class along a beam column), never where the image happens to be bright."""
from __future__ import annotations

import numpy as np

BONE = ("bone_cortical", "bone_cancellous", "marrow_yellow", "tooth")
SHEATHED = ("muscle", "nerve", "blood_artery", "blood_vein")


def lin(db):
    return np.where(db > -150, 10.0 ** (db / 10.0), 0.0)


def mean_db(v):
    v = v[v > 0]
    return float(10 * np.log10(v.mean())) if v.size else float("nan")


def frame(db, lab, sid, plan):
    """rasters resampled on the OUTPUT grid (Ho x Wo): class id and structure id under every image pixel"""
    Wo, Ho, px = plan["Wo"], plan["Ho"], plan["px"]
    jx = np.clip(((plan["xo0"] + (np.arange(Wo) + 0.5) * px - plan["xr0"]) / px).astype(int), 0, lab.shape[1] - 1)
    jy = np.clip(((plan["yo0"] + (np.arange(Ho) + 0.5) * px - plan["yr0"]) / px).astype(int), 0, lab.shape[0] - 1)
    return lab[np.ix_(jy, jx)], sid[np.ix_(jy, jx)]


def interior(mask, r):
    """pixels of the mask at least r px from its edge (box erosion)"""
    m = mask.copy()
    for _ in range(r):
        n = m.copy()
        n[1:, :] &= m[:-1, :]; n[:-1, :] &= m[1:, :]; n[:, 1:] &= m[:, :-1]; n[:, :-1] &= m[:, 1:]
        m = n
    return m


def _box(a, r):
    c = np.cumsum(np.pad(a, ((r + 1, r), (0, 0)), mode="edge"), axis=0); a2 = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
    c = np.cumsum(np.pad(a2, ((0, 0), (r + 1, r)), mode="edge"), axis=1); return (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)


def measure(db, lab, sid, plan, cls_key, max_depth_mm=None, win_px=3):
    """-> dict of measures. cls_key: list, class id -> class key."""
    px = plan["px"]; Ho, Wo = db.shape
    L, S = frame(db, lab, sid, plan)
    I = lin(db)
    key = np.array(cls_key + [""] * (256 - len(cls_key)), dtype=object)
    K = key[L]
    is_m = K == "muscle"; is_f = K == "fat"; is_b = np.isin(K, BONE); is_sh = np.isin(K, SHEATHED)
    y_mm = plan["yo0"] + (np.arange(Ho) + 0.5) * px
    deep_ok = np.ones(Ho, bool) if max_depth_mm is None else (y_mm <= max_depth_mm)
    rI = max(2, int(round(1.0 / px)))
    m_in = interior(is_m, rI) & deep_ok[:, None]; f_in = interior(is_f, max(1, rI // 2))
    out = {"px": px, "muscle_db": mean_db(I[m_in]), "fat_db": mean_db(I[f_in]), "muscle_px": int(m_in.sum()), "fat_px": int(f_in.sum())}
    # ---- interfaces along the beam columns (linear probe: a column is a beam line)
    cols = range(int(Wo * 0.12), int(Wo * 0.88))
    lines = {"septum": [], "sheath": [], "fascia": []}      # per boundary sample: the peak within win_px, dB above the muscle beside it
    peaks = {"septum": [], "sheath": [], "fascia": []}      # ... and its absolute level (dB re liver)
    bone_edge, shadow = [], []
    for x in cols:
        col_s, col_k = S[:, x], K[:, x]
        chg = np.nonzero((col_s[1:] != col_s[:-1]) | (col_k[1:] != col_k[:-1]))[0] + 1
        hit_bone = False
        for y in chg:
            if y < 4 or y > Ho - 5 or not deep_ok[y] or hit_bone and col_k[y] not in BONE:
                continue
            ka, kb = col_k[y - 1], col_k[y]
            if kb in BONE and ka not in BONE and not hit_bone:
                hit_bone = True
                pk = I[max(0, y - win_px):y + win_px + 1, x].max()
                bone_edge.append(10 * np.log10(pk) if pk > 0 else -200.0)
                y0, y1 = y + int(3 / px), y + int(8 / px)
                if y1 < Ho:
                    shadow.append(mean_db(I[y0:y1, max(0, x - 1):x + 2].ravel() + 1e-30))
                continue
            if hit_bone or ka == "" or kb == "" or ka == "air" or kb == "air" or ka == "skin" or kb == "skin":
                continue
            # septum: muscle against ANOTHER muscle mesh (no change of tissue class: nothing but the mesh boundary says it is there);
            # sheath: a muscle / nerve / vessel against other soft tissue; fascia: a fascia / septum / aponeurosis MESH of the page
            kind = "fascia" if "tendon_ligament" in (ka, kb) else "septum" if (ka == "muscle" and kb == "muscle") else "sheath" if (ka in SHEATHED or kb in SHEATHED) else None
            if kind is None:
                continue
            # the boundary's slope from the same boundary in the neighbouring columns (+-4 px): keep it when within ~35 deg of square to the beam
            def edge_y(xx):
                c2s, c2k = S[:, xx], K[:, xx]
                c = np.nonzero((c2s[1:] != c2s[:-1]) | (c2k[1:] != c2k[:-1]))[0] + 1
                c = c[np.abs(c - y) <= 4]
                return None if c.size == 0 else int(c[np.argmin(np.abs(c - y))])
            ya, yb = edge_y(max(0, x - 4)), edge_y(min(Wo - 1, x + 4))
            if ya is None or yb is None or abs(yb - ya) > 8 * 0.7:
                continue
            # reference: muscle 1.2 - 3.5 mm to either side of the boundary, same column band
            ref = []
            for sgn in (-1, 1):
                a0, a1 = y + sgn * int(1.2 / px), y + sgn * int(3.5 / px)
                lo, hi = min(a0, a1), max(a0, a1)
                if lo >= 0 and hi < Ho:
                    seg = (K[lo:hi, x] == "muscle")
                    if seg.sum() >= 3:
                        ref.append(I[lo:hi, x][seg].mean())
            if not ref:
                continue
            pk = I[y - win_px:y + win_px + 1, max(0, x - 1):x + 2].max()
            lines[kind].append(10 * np.log10(pk / np.mean(ref)) if pk > 0 else -99.0)
            peaks[kind].append(10 * np.log10(pk) if pk > 0 else -200.0)
    for k, v in lines.items():
        v = np.array(v)
        out[k + "_n"] = int(v.size)
        out[k + "_median_over_muscle_db"] = float(np.median(v)) if v.size else float("nan")
        out[k + "_found_frac"] = float((v >= 6).mean()) if v.size else float("nan")
        out[k + "_peak_db"] = float(np.median(peaks[k])) if v.size else float("nan")
    out["bone_n"] = len(bone_edge)
    out["bone_edge_db"] = float(np.median(bone_edge)) if bone_edge else float("nan")
    out["shadow_db"] = float(np.median(shadow)) if shadow else float("nan")
    out["shadow_n"] = len(shadow)
    # ---- like tissue reads alike with depth: muscle interior, upper vs lower half of its depth range
    ys = np.nonzero(m_in.any(axis=1))[0]
    if ys.size > 20:
        mid = (ys[0] + ys[-1]) // 2
        out["muscle_top_db"] = mean_db(I[:mid][m_in[:mid]]); out["muscle_bottom_db"] = mean_db(I[mid:][m_in[mid:]])
    # ---- texture direction inside muscle: energy of the brightness change down the image vs across it (dB image, clipped)
    D = np.clip(db, -60, 30)
    gy = np.zeros_like(D); gx = np.zeros_like(D)
    gy[1:-1] = D[2:] - D[:-2]; gx[:, 1:-1] = D[:, 2:] - D[:, :-2]
    m2 = interior(is_m, rI + 1) & deep_ok[:, None]
    if m2.sum() > 500:
        out["tex_down_over_across"] = float((gy[m2] ** 2).mean() / max(1e-9, (gx[m2] ** 2).mean()))
        # short bright marks: share of muscle pixels more than 6 dB above the muscle's own median
        med = np.median(D[m2]); out["bright_frac"] = float((D[m2] > med + 6).mean())
        # do the bright marks run on as LINES?  the muscle's high-passed image against itself 3 mm further along a direction within
        # +-30 deg of the image's lateral axis: near 0 for dots and dashes (across the fibres), clearly positive for striations
        Hh = D - _box(D, max(2, int(round(1.5 / px))))
        best, ang = -1.0, 0
        for a in range(-30, 31, 5):
            dxs = int(round(3.0 / px * np.cos(np.radians(a)))); dys = int(round(3.0 / px * np.sin(np.radians(a))))
            A = Hh[max(0, dys):Ho + min(0, dys), 0:Wo - dxs]; B = Hh[max(0, -dys):Ho + min(0, -dys), dxs:Wo]
            mm = m2[max(0, dys):Ho + min(0, dys), 0:Wo - dxs] & m2[max(0, -dys):Ho + min(0, -dys), dxs:Wo]
            if mm.sum() < 300:
                continue
            c = float((A[mm] * B[mm]).mean() / max(1e-9, np.sqrt((A[mm] ** 2).mean() * (B[mm] ** 2).mean())))
            if c > best:
                best, ang = c, a
        out["line_persistence"] = best; out["line_angle_deg"] = ang
    return out
