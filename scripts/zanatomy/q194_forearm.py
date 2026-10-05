"""Q194: the LEFT FOREARM muscles / tendons / nerves / vessels placed with her left radius / ulna and her left-forearm cryosection photographs.

Why: Q192 placed the left radius / ulna and the left hand on her own photographs, but the forearm soft tissue stayed a Q168 proxy (Q190 even fitted the forearm
muscles onto Q71's partial colour-threshold labels): extensor digitorum 27 mm from the radius / ulna (the Z source: 22), flexor carpi ulnaris 49 mm (18), pronator
quadratus 22 mm (5), the muscle bellies lay outside her skin in the photographs.  Real data used here (nothing is invented):
  1. the Q192 per-bone similarities of radius_l / ulna_l (data/derived/Q192_left_hand_fit.json) carry every left forearm structure from its Z SOURCE position
     (bone-anchored inverse-distance blend of the two bone maps, extended proximally with a smooth axial taper to the elbow where the humerus part keeps its place);
  2. her photographs (data/derived/Q194_left_forearm_photo_masks.npz: per-level muscle / bone / skin-silhouette masks of her left forearm, 1 mm grid, same frame as
     the Q192 bones): the outer surface of the moved muscles is driven onto the border of her muscle mass by a smooth, bounded, fold-guarded displacement field.
     Which muscle lies where inside the mass stays the Z arrangement (the photographs show the mass, not the individual muscles);
  3. out of her bones, inside her skin, volume guard 0.65-1.5 x the Z source, fold guard.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
MASKS = REPO / "data" / "derived" / "Q194_left_forearm_photo_masks.npz"
PX, AZ, YOFF, AX = 0.33, -166.4, 1850.0, 352.2          # photograph -> atlas frame (Q192_frame_calibration.json)
GRID_LO = np.array([-332.0, 196.0, -172.0])
GRID_N = np.array([216, 290, 292])                       # 1 mm grid: x -332..-117, y 196..485, z -172..119


GATE_MM = (110.0, 150.0)   # distance from the Z source radius / ulna beyond which the forearm carry fades out (hand structures are carried by Q192 already)
BLEND_SOFT_MM, BLEND_POWER = 12.0, 1.5       # inverse-distance blend of the radius / ulna maps: softer than the hand's (2.5, 2.5) so a muscle is sheared less across the forearm


def area_ok(v1, v0, r, f, lo=0.7, hi=1.45, rel=(0.8, 1.25)):
    """surface-area guard (a vessel / nerve must not swell into a tube or collapse into a sliver): area / (Z source area x BODY_SCALE^2) in [lo, hi], or at most 20-25 % off
    what it was before the move"""
    from scripts.zanatomy import q190_metrics as Mx
    a = lambda x: float(Mx.tri_area(x, f).sum())
    ref = a(r.astype(float)) * Mx.BODY_SCALE ** 2
    if ref < 1e-6:
        return True
    r1, r0 = a(v1) / ref, a(v0) / ref
    return (lo <= r1 <= hi) or (rel[0] <= r1 / max(r0, 1e-9) <= rel[1])


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def load_photo_masks(path=MASKS):
    """-> dict of float32 arrays on the 1 mm atlas grid: skin (tissue silhouette), muscle (muscle-coloured tissue, closed), bone (cream), valid (levels with photographs)"""
    z = np.load(path)
    zc = z["zc"]                                           # cryo z of each slice (1 mm apart, descending)
    out = {}
    xs = GRID_LO[0] + np.arange(GRID_N[0])
    ys = GRID_LO[1] + np.arange(GRID_N[1])
    zs = GRID_LO[2] + np.arange(GRID_N[2])
    px = float(z["px_mm"]) if "px_mm" in z.files else 3 * PX                      # mask pixel pitch (3 x 0.33 mm)
    c0, r0 = float(z["box_col0"]), float(z["box_row0"])
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    col = ((AX - X) / PX - c0 - 1.5) / 3.0
    row = ((Z - AZ) / PX - r0 - 1.5) / 3.0
    for k in ("T", "M", "C"):
        A = z[k].astype(np.float32) / (255.0 if z[k].dtype == np.uint8 else 1.0)
        G = np.zeros(tuple(GRID_N), np.float32)
        for iy, y in enumerate(ys):
            j = int(round(zc[0] + YOFF - y))
            if 0 <= j < len(zc):
                G[:, iy, :] = ndi.map_coordinates(A[j], [row, col], order=1, mode="constant")
        out[{"T": "skin", "M": "muscle", "C": "bone"}[k]] = G
    valid = np.zeros(GRID_N[1], bool)
    for iy, y in enumerate(ys):
        j = int(round(zc[0] + YOFF - y))
        valid[iy] = 0 <= j < len(zc)
    out["valid_y"] = valid
    return out


# ------------------------------------------------------------------------------------------------ carry
def carry_weights(raw_v, c_w, u, s_elbow, full_above_elbow=10.0, fade_mm=100.0):
    """axial weight of the forearm-bone carry: 1 from the wrist up to `full_above_elbow` below the elbow line, fading to 0 `fade_mm` above it, where the structure belongs to the humerus"""
    s = (raw_v - c_w) @ u                                  # <= 0 up the forearm
    t = (s - (s_elbow - fade_mm)) / ((s_elbow + full_above_elbow) - (s_elbow - fade_mm))
    return smoothstep(t)


def q191_near_tree(raw: dict, side: str, h):
    """(c_w, u, KD-tree) exactly as q191_hand.run_side builds them: the Z hand bones + the distal 90 mm of radius / ulna (Z source frame); the Q191 / Q192 carry weight of a vertex
    is h.field_weight(raw, c_w, u, tree)"""
    rad, uln = f"radius_{side}", f"ulna_{side}"
    c_w, u = h.wrist_frame(raw[rad])
    pts = [raw[i] for i in sum(h.bone_ids(side).values(), [])]
    for i in (rad, uln):
        pts.append(raw[i][(raw[i] - c_w) @ u > -90.0])
    return c_w, u, cKDTree(np.vstack(pts))


def carry(by: dict, raw: dict, fit: dict, ids: list[str], h) -> dict:
    """new vertices of the left forearm structures: x = v + (1 - w_old) (F(r) - v), F(r) = (1 - w) T_humerus(r) + w HM_radius_ulna(r), r = Z source vertex, w = axial weight
    (1 over the forearm, 0 at the humerus), w_old = what the Q192 carry applied (1 in the hand: unchanged).  Returns ({id: (v_new, weight)}, info)"""
    T = {i: (float(t["s"]), np.asarray(t["R"], float), np.asarray(t["t"], float)) for i, t in fit["transforms_from_Z_source_frame"].items()}
    rad, uln, hum = "radius_l", "ulna_l", "humerus_l"
    c_w, u = h.wrist_frame(raw[rad])
    HM = h.HandMap({i: raw[i] for i in (rad, uln)}, {i: T[i] for i in (rad, uln)}, soft=BLEND_SOFT_MM, power=BLEND_POWER, k=2)
    T_hum = h.kabsch(raw[hum], by[hum]["v"], scale=True)           # the Z humerus onto her (CT-fitted) humerus: the frame the upper arm / elbow end lives in
    s_top = float(((raw[uln] - c_w) @ u).min())            # most proximal point of the Z ulna along the axis (olecranon), negative
    near_tree = cKDTree(np.vstack([raw[rad], raw[uln]]))
    c_w_old, u_old, near_old = q191_near_tree(raw, "l", h)        # the weight the Q192 carry applied (hand bones included in its gate)
    out = {}
    for i in ids:
        r = raw[i].astype(float)
        w = carry_weights(r, c_w, u, s_top)
        w_old = h.field_weight(r, c_w_old, u_old, near_old)  # what the Q192 carry already applied
        Fr = (1.0 - w)[:, None] * h.apply_T(T_hum, r) + w[:, None] * HM.map(r)
        gate = 1.0 - smoothstep((near_tree.query(r)[0] - GATE_MM[0]) / (GATE_MM[1] - GATE_MM[0]))     # the foot half of a merged mesh, far structures: untouched
        b = (1.0 - w_old) * gate
        v = by[i]["v"].astype(float)
        out[i] = (v + b[:, None] * (Fr - v), b)
    return out, {"s_elbow_mm": s_top, "c_w": c_w.tolist(), "u": u.tolist()}


# ------------------------------------------------------------------------------------------------ occupancy
def to_grid(P):
    return (P - GRID_LO)


def surface_samples(v, f, spacing=0.6, rng=None):
    rng = rng or np.random.default_rng(0)
    tri = v[f]
    a = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    n = np.maximum(1, np.ceil(a / (spacing ** 2 * 0.5)).astype(int))
    idx = np.repeat(np.arange(len(f)), n)
    u = rng.random((len(idx), 2))
    m = u.sum(1) > 1
    u[m] = 1 - u[m]
    t = tri[idx]
    return t[:, 0] + u[:, :1] * (t[:, 1] - t[:, 0]) + u[:, 1:] * (t[:, 2] - t[:, 0])


def occupancy(v, f, close=1):
    """bool grid of the volume of a closed mesh: surface voxels, closed, filled slice by slice (x-z planes)"""
    P = to_grid(surface_samples(v, f)) + 0.5
    ij = np.floor(P).astype(int)
    ok = np.all((ij >= 0) & (ij < GRID_N), axis=1)
    g = np.zeros(tuple(GRID_N), bool)
    g[ij[ok, 0], ij[ok, 1], ij[ok, 2]] = True
    if close:
        g = ndi.binary_dilation(g, iterations=close)
    lo = np.floor(P.min(0)).astype(int).clip(0, None)
    hi = np.ceil(P.max(0)).astype(int).clip(None, GRID_N)
    sub = g[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    for iy in range(sub.shape[1]):
        sub[:, iy, :] = ndi.binary_fill_holes(sub[:, iy, :])
    if close:
        sub = ndi.binary_erosion(sub, iterations=close)
    g[:] = False
    g[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] = sub
    return g


# ------------------------------------------------------------------------------------------------ photograph-driven field
def sdf(mask):
    """signed distance (mm, > 0 outside) of a bool grid on the 1 mm grid"""
    return ndi.distance_transform_edt(~mask) - ndi.distance_transform_edt(mask)


def muscle_region(P, bone_occ, y0, y1):
    """her muscle compartment on the grid: muscle-coloured tissue closed over the fascial planes (4 voxels), + her bones, filled slice by slice; 0 outside [y0, y1]"""
    R = np.zeros(tuple(GRID_N), bool)
    ys = GRID_LO[1] + np.arange(GRID_N[1])
    for iy, y in enumerate(ys):
        if not (y0 <= y <= y1) or not P["valid_y"][iy]:
            continue
        m = (P["muscle"][:, iy, :] > 0.5) | bone_occ[:, iy, :]
        m = ndi.binary_closing(m, iterations=4)
        m = ndi.binary_fill_holes(m)
        m = ndi.binary_opening(m, iterations=2)
        lab, n = ndi.label(m)
        if n > 1:
            sz = ndi.sum(m, lab, range(1, n + 1))
            m = lab == (1 + int(np.argmax(sz)))
        R[:, iy, :] = m
    return R


def sample_grid(G, P, order=1):
    return ndi.map_coordinates(G, (to_grid(P) - 0.0).T, order=order, mode="nearest")


def grad_grid(G, P, h=1.0):
    g = np.zeros_like(P)
    for k in range(3):
        e = np.zeros(3); e[k] = h
        g[:, k] = (sample_grid(G, P + e) - sample_grid(G, P - e)) / (2 * h)
    return g


def photo_flow(moving: dict, bones_occ, P, followers: dict | None = None, y0=212.0, y1=338.0, iters=6, step=0.8, sigma=7.0, cap=12.0, taper_mm=14.0, log=print):
    """moving: {id: {"v": Nx3, "f": faces, "cat": cat}} (muscles; others follow through `follow`).  Returns total displacement per vertex of each muscle after `iters`
    rounds of: occupancy of the moving muscles -> exposed (outer-shell) vertices -> displacement to the border of her muscle compartment -> smooth extension."""
    from scripts.zanatomy.q190_refine import _vertex_normals
    R = muscle_region(P, bones_occ, y0, y1)
    sdR = sdf(R)
    followers = followers or {}
    total = {i: np.zeros_like(m["v"]) for i, m in moving.items()}
    cur = {i: m["v"].copy() for i, m in moving.items()}
    ftot = {i: np.zeros_like(v) for i, v in followers.items()}
    hist = []
    for it in range(iters):
        lab = np.zeros(tuple(GRID_N), np.int16)
        names = list(cur)
        for k, i in enumerate(names):
            occ = occupancy(cur[i], moving[i]["f"])
            lab[occ & (lab == 0)] = k + 1
        lab_b = lab.copy()
        lab_b[bones_occ & (lab_b == 0)] = -1
        iou = float((((lab > 0) | bones_occ) & R).sum() / max(1, (((lab > 0) | bones_occ) | R).sum()))
        hist.append(iou)
        Dsum = np.zeros(tuple(GRID_N) + (3,), np.float32)
        Wsum = np.zeros(tuple(GRID_N), np.float32)
        nex = 0
        for k, i in enumerate(names):
            v, f = cur[i], moving[i]["f"]
            n = _vertex_normals(v, f)
            if np.sum((np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]) * (v[f].mean(1) - v.mean(0))).sum(1)) < 0:
                n = -n
            d = sample_grid(sdR, v)
            g = grad_grid(sdR, v)
            gn = g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
            inband = (np.abs(d) < 18.0) & (v[:, 1] > y0) & (v[:, 1] < y1)
            facing = (n * gn).sum(1) > 0.35                              # surface faces the compartment border
            # exposed: what lies a few mm out along the normal is not another moving muscle or bone
            q = sample_grid(lab_b.astype(np.float32), v + 2.5 * n, order=0)
            exposed = (q == 0) | (q == k + 1)
            # also blocked if another structure lies between the vertex and the border it is pulled to
            sel = inband & facing & exposed
            sel &= ~((d < 0) & (sample_grid(lab_b.astype(np.float32), v - d[:, None] * gn * 0.5, order=0) > 0) & (np.abs(d) > 3))
            tgt = -(d + 0.7)[:, None] * gn                                # border inset 0.7 mm
            tgt = np.clip(tgt, -cap, cap)
            ij = np.floor(to_grid(v[sel]) + 0.5).astype(int)
            ok = np.all((ij >= 0) & (ij < GRID_N), 1)
            ij, tg = ij[ok], tgt[sel][ok]
            np.add.at(Wsum, (ij[:, 0], ij[:, 1], ij[:, 2]), 1.0)
            for c in range(3):
                np.add.at(Dsum[..., c], (ij[:, 0], ij[:, 1], ij[:, 2]), tg[:, c])
            nex += int(sel.sum())
        Wf = ndi.gaussian_filter(Wsum, sigma)
        Df = np.stack([ndi.gaussian_filter(Dsum[..., c], sigma) for c in range(3)], -1)
        conf = Wf / (Wf + 0.02)                                          # no data -> no displacement
        field = Df / np.maximum(Wf, 1e-9)[..., None] * conf[..., None]
        log(f"    photo flow round {it}: IoU(muscle + bone, her compartment) {iou:.3f}, exposed vertices {nex}")
        for i in names:
            v = cur[i]
            dv = np.stack([sample_grid(field[..., c], v) for c in range(3)], 1)
            ax = (v[:, 1] - y0) / taper_mm, (y1 - v[:, 1]) / taper_mm
            dv *= smoothstep(np.minimum(*ax))[:, None]
            nd = total[i] + step * dv
            m = np.linalg.norm(nd, axis=1)
            nd *= np.minimum(1.0, cap / np.maximum(m, 1e-9))[:, None]
            total[i] = nd
            cur[i] = moving[i]["v"] + nd
        for i, v0 in followers.items():
            v = v0 + ftot[i]
            dv = np.stack([sample_grid(field[..., c], v) for c in range(3)], 1)
            ax = (v[:, 1] - y0) / taper_mm, (y1 - v[:, 1]) / taper_mm
            dv *= smoothstep(np.minimum(*ax))[:, None]
            nd = ftot[i] + step * dv
            m = np.linalg.norm(nd, axis=1)
            ftot[i] = nd * np.minimum(1.0, cap / np.maximum(m, 1e-9))[:, None]
    return total, ftot, R, hist


# ------------------------------------------------------------------------------------------------ constraints, metrics, driver
def inside_pct(G, v, y0=214.0, y1=470.0):
    """share (%) of the vertices within her photographed levels that lie inside the bool grid G"""
    m = (v[:, 1] > y0) & (v[:, 1] < y1)
    if not m.any():
        return None
    g = np.floor(v[m] - GRID_LO + 0.5).astype(int)
    ok = np.all((g >= 0) & (g < GRID_N), axis=1)
    g = g[ok]
    return 100.0 * float(G[g[:, 0], g[:, 1], g[:, 2]].mean()) if len(g) else None


def clamp_into(v, f, sd, margin=1.5, band=1.0, max_move=10.0, passes=10, y0=214.0, y1=470.0):
    """vertices closer than `band` mm to / outside the border of a region (signed distance sd, > 0 outside) are moved inside to `margin` mm depth; the push is spread over the mesh"""
    from scripts.zanatomy import q190_refine as Q
    s = sample_grid(sd, v)
    act = (s > -band) & (v[:, 1] > y0) & (v[:, 1] < y1)
    if not act.any():
        return v, 0
    g = grad_grid(sd, v[act])
    g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
    step = np.minimum(s[act] + margin, max_move)[:, None]
    D = np.zeros_like(v)
    D[act] = -g * step
    D = Q._smooth_push(f, D, passes)
    return v + D, int(act.sum())


def metrics(v, r, f, cat, skin_occ, bones, sdb=None):
    from scripts.zanatomy import q190_metrics as Mx
    from scripts.zanatomy import q191_hand as H
    out = {}
    o = inside_pct(skin_occ, v)
    if o is not None:
        out["outside_her_skin_pct"] = round(100.0 - o, 1)
    out["inside_z_bone_pct"] = round(100 * float((np.max([b.depth(v) for b in bones], 0) > 1.5).mean()), 2)
    st = Mx.stretch_stats(v, r, f)
    out["stretch_area_outside_0.67_1.5_pct"] = round(100 * (st["area_frac_gt1.5"] + st["area_frac_lt0.67"]), 1) if st else None
    out["folded_edges_pct"] = round(100 * H.fold_stats(v, r, f), 2)
    vr = H.vol_ratio(v, r, f)
    if vr is not None:
        out["volume_ratio_vs_source"] = round(vr, 3)
    return out


FOLLOW_CATS = ("nerve", "vessel", "lymphatic", "tendon", "fascia", "ligament", "bursa", "cartilage")


def _fmt(m):
    return ", ".join(f"{k.replace('_pct', ' %').replace('_', ' ')} {v}" for k, v in m.items() if v is not None)


def refine_left_forearm(by: dict, raw: dict, fit: dict, regions: dict, log=print, flow_kw=None) -> dict:
    """build hook (post gap closure): see the module docstring.  Mutates by[i]["v"] / ["fit_note"] of the left forearm structures; returns the report"""
    from scripts.zanatomy import q190_refine as Q
    from scripts.zanatomy import q191_hand as H
    rawd = {k: np.asarray(v, float) for k, v in raw.items()}
    from scripts.zanatomy import q191_hand as H
    near = cKDTree(np.vstack([rawd["radius_l"], rawd["ulna_l"]]))
    ids = [k for k, d in by.items() if k.endswith("_l") and d["cat"] != "bone" and not H.FOOT_NAME.search(k)
           and (regions.get(k) == "forearm_hand" or H.SKIN_HAND.search(k)) and near.query(rawd[k][::4])[0].min() < 100.0]
    res, info = carry(by, rawd, fit, ids, H)
    changed = [i for i in ids if np.linalg.norm(res[i][0] - by[i]["v"], axis=1).max() > 0.5]
    P = load_photo_masks()
    skin_occ = P["skin"] > 0.5
    ys = GRID_LO[1] + np.arange(GRID_N[1])
    for iy in range(GRID_N[1]):                                # fill the silhouette slice by slice, keep the forearm component
        if P["valid_y"][iy]:
            skin_occ[:, iy, :] = ndi.binary_fill_holes(skin_occ[:, iy, :])
    sd_skin = sdf(skin_occ)
    rad, uln = by["radius_l"], by["ulna_l"]
    bones_occ = occupancy(rad["v"], rad["f"]) | occupancy(uln["v"], uln["f"])
    zb = [H.Inside(rad["v"], rad["f"]), H.Inside(uln["v"], uln["f"])]
    moving = {i: {"v": res[i][0], "f": by[i]["f"], "cat": "muscle"} for i in changed
              if by[i]["cat"] == "muscle" and Q._closed(by[i]["f"]) and not H.NOT_BODY.search(i)
              and res[i][0][:, 1].min() < 338.0 and res[i][0][:, 1].max() > 212.0}
    followers = {i: res[i][0] for i in changed if i not in moving and by[i]["cat"] != "skin"}
    log(f"  Q194 left forearm: {len(ids)} in scope, {len(changed)} carried, {len(moving)} muscles driven onto her muscle compartment, {len(followers)} followers")
    tot, ftot, R, hist = photo_flow(moving, bones_occ, P, followers, log=log, **(flow_kw or {}))
    sd_R = sdf(R)
    report = {"carry": info, "iou_rounds": [round(x, 3) for x in hist], "structures": {}}
    for i in changed:
        d = by[i]
        v0, r = d["v"].astype(float), rawd[i]
        carried = res[i][0]
        cand = carried + (tot[i] if i in moving else ftot.get(i, 0.0))
        if d["cat"] == "skin":                                  # skin: onto the border of her silhouette (the same photographs)
            m = (carried[:, 1] > 214.0)
            s = sample_grid(sd_skin, carried)
            g = grad_grid(sd_skin, carried)
            g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
            move = np.where((m & (res[i][1] > 0.02))[:, None], -(s + 0.8)[:, None] * g, 0.0)
            move = np.clip(move, -14.0, 14.0)
            cand = carried + Q._smooth_push(d["f"], move, 10)
        before = metrics(v0, r, d["f"], d["cat"], skin_occ, zb)
        best = None
        # candidates: flow on top of the carry (full / half), each with and without the Q190/Q191 shape relaxation (low-pass of the displacement against the Z source, 8 mm)
        tries = [(1.0, False), (1.0, True), (0.5, True), (0.0, True), (0.0, False)]
        for scale, relax in tries:
            v = carried + scale * (cand - carried)
            if relax:
                bb = np.clip(res[i][1], 0, 1)[:, None]
                v = v + bb * (Q.smooth_displacement({"r": r, "f": d["f"]}, v, 8.0) - v)
            if d["cat"] != "skin":
                v, _ = clamp_into(v, d["f"], sd_skin)
                if d["cat"] == "muscle":                      # a muscle belly outside her muscle compartment by > 3 mm (the fat layer) is brought back to its border
                    v, _ = clamp_into(v, d["f"], sd_R, margin=0.5, band=-3.0, max_move=12.0, y0=216.0, y1=336.0)
                if d["cat"] in H.SOFT_PUSH_CATS:
                    v = H.push_out_of_bones(v, d["f"], zb, np.ones(len(v), bool), tol=1.5, max_move=7.0)
            if d["cat"] == "muscle" and Q._closed(d["f"]) and not H.NOT_BODY.search(i):
                v, _ = Q.volume_guard(v, r, d["f"])
            after = metrics(v, r, d["f"], d["cat"], skin_occ, zb)
            ok = area_ok(v, v0, r, d["f"]) and after["folded_edges_pct"] <= max(before["folded_edges_pct"] + 1.0, 2.0) and (after.get("stretch_area_outside_0.67_1.5_pct") or 0) <= max((before.get("stretch_area_outside_0.67_1.5_pct") or 0) + 15.0, 25.0)
            sc = after.get("stretch_area_outside_0.67_1.5_pct") or 0
            cost = (after.get("outside_her_skin_pct") or 0) * 2 + after["inside_z_bone_pct"] * 2 + after["folded_edges_pct"] * 2 + sc * 0.3 + (0 if ok else 50)
            if best is None or cost < best[3]:
                best = (v, after, f"{scale}{'+relax' if relax else ''}", cost)
        v, after, scale, _ = best
        d["v"] = v
        report["structures"][i] = {"before": before, "after": after, "flow_scale": scale,
                                    "mean_move_mm": round(float(np.linalg.norm(v - v0, axis=1).mean()), 1), "max_move_mm": round(float(np.linalg.norm(v - v0, axis=1).max()), 1)}
        d["fit_note"] = (d.get("fit_note") or "") + (
            f" Q194: LEFT FOREARM structure re-placed (it was a Q168 proxy, outside her skin / detached from her radius and ulna): carried from the Z source by her photograph-fitted left "
            f"radius / ulna (Q192) and, for muscles, driven onto her own muscle mass in her left-forearm cryosection photographs (flow scale {scale}); out of her bones, inside her skin, volume guard 0.65-1.5x. "
            f"Before -> after: {_fmt(before)} -> {_fmt(after)}; mean move {report['structures'][i]['mean_move_mm']} mm. Which muscle lies where inside her muscle mass is the Z arrangement "
            f"(the photographs show the mass, not the individual muscles).")
    report["skin_seams"] = reweld_patches(by, [i for i in changed if by[i]["cat"] == "skin"], rawd)
    report["ids_changed"] = changed
    return report


def reweld_patches(by: dict, moved: list[str], raw: dict, passes=8) -> dict:
    """the skin patches tile one surface: vertices of a moved patch that share a Z-source position with an UNMOVED patch are pinned to that patch's vertex, those shared only
    between moved patches go to their common mean; the correction is spread over the moved patch (so no pleat)"""
    from scripts.zanatomy import q190_refine as Q
    if not moved:
        return {}
    fixed = {}
    for i, d in by.items():
        if d["cat"] == "skin" and i not in moved:
            for x, p in zip(np.round(raw[i], 2), d["v"]):
                fixed.setdefault(tuple(x), p)
    acc = {}
    for i in moved:
        for x, p in zip(np.round(raw[i], 2), by[i]["v"]):
            acc.setdefault(tuple(x), []).append(p)
    rep = {}
    for i in moved:
        keys = [tuple(x) for x in np.round(raw[i], 2)]
        tgt = np.array([fixed[k] if k in fixed else np.mean(acc[k], 0) for k in keys])
        corr = tgt - by[i]["v"]
        m = np.linalg.norm(corr, axis=1)
        if m.max() < 1e-6:
            continue
        pinned = np.array([k in fixed for k in keys])
        c2 = Q._smooth_push(by[i]["f"], corr, passes)
        c2 = np.where((np.linalg.norm(corr, axis=1) > 1e-6)[:, None], corr, c2)
        rep[i] = {"max_correction_mm": round(float(m.max()), 2), "pinned_vertices": int(pinned.sum())}
        by[i]["v"] = by[i]["v"] + c2
    return rep


# ------------------------------------------------------------------------------------------------ right forearm (her own-model forearm labels exist)
HER_ALIAS_R = {"zan_extensor_pollicis_longus_r": "extensor_pollicis_longus_r"}
FOLLOW_R = ("nerve", "vessel", "lymphatic", "tendon", "fascia", "ligament", "bursa", "muscle")


def refine_right_forearm(by: dict, raw: dict, regions: dict, her: dict, skin, skin_tree, log=print) -> dict:
    """Q190 left the forearm muscles out of its per-structure refinement (SKIP_RE), so the right forearm muscles are still the global-field result: 35-50 % of their triangles
    stretched outside 0.67-1.5x of the Z source and 8-15 mm from her own-model forearm labels (ECRB, ECU, EI, EPB, EPL).  Each muscle that has a label of hers is refined onto it
    with the Q190 per-structure fit (similarity, bounded affine, bounded smooth residual, volume guard 0.65-1.5x), carried into the hand by the Q191 taper (hand part unchanged), out of
    the displayed radius / ulna and inside her skin; the structures without a label follow (distance-weighted displacement, Q190 propagation rule)."""
    from scripts.zanatomy import q190_metrics as Mx
    from scripts.zanatomy import q190_refine as Q
    from scripts.zanatomy import q191_hand as H
    c_w, u, near_q191 = q191_near_tree(raw, "r", H)
    near = cKDTree(np.vstack([raw["radius_r"], raw["ulna_r"]]))
    zb = [H.Inside(by["radius_r"]["v"], by["radius_r"]["f"]), H.Inside(by["ulna_r"]["v"], by["ulna_r"]["f"])]
    pend = [{"mesh_id": k, "cat": d["cat"]} for k, d in by.items()]
    scope = [i for i in H.scope(pend, regions, "r") if by[i]["cat"] != "skin" and not H.FOOT_NAME.search(i) and near.query(raw[i][::4])[0].min() < 100.0
             and not re.search(r"trapezius|opponens_digiti_minimi", i)]
    rep = {"muscles": {}, "followers": {}}
    new, before = {}, {}
    for i in scope:
        d = by[i]
        hid = HER_ALIAS_R.get(i, i)
        if d["cat"] != "muscle" or hid not in her or her[hid]["cat"] != "muscle" or not Q._closed(d["f"]) or H.NOT_BODY.search(i):
            continue
        v0, r, f = d["v"].astype(float), raw[i].astype(float), d["f"]
        ref = Q.Ref(her[hid]["v"].astype(float), her[hid]["f"].astype(int))
        X, rr, _ = Q.refine_group([{"id": i, "v": v0, "r": r, "f": f}], ref, log=lambda *_: None)
        X, _ = Q.volume_guard(X, r, f)
        b = 1.0 - H.field_weight(r, c_w, u, near_q191)
        if b.max() < 0.05:
            continue
        v1 = v0 + b[:, None] * (X - v0)
        v1 = H.push_out_of_bones(v1, f, zb, b > 0.02, tol=1.5, max_move=7.0)
        v1 = H.clamp_inside_skin(v1, f, b > 0.02, skin, skin_tree, margin=1.0, max_move=14.0)
        v1, vr = Q.volume_guard(v1, r, f)
        part = rr["partial_reference"]
        c0, c1 = Q.chamfer(v0, f, ref, partial=part), Q.chamfer(v1, f, ref, partial=part)
        s0, s1 = Mx.stretch_stats(v0, r, f), Mx.stretch_stats(v1, r, f)
        p0, p1 = 100 * (s0["area_frac_gt1.5"] + s0["area_frac_lt0.67"]), 100 * (s1["area_frac_gt1.5"] + s1["area_frac_lt0.67"])
        f0, f1 = 100 * H.fold_stats(v0, r, f), 100 * H.fold_stats(v1, r, f)
        status = "refined" if (c1[2] < 0.9 * c0[2] and p1 <= p0 + 2.0 and f1 <= f0 + 1.0 and area_ok(v1, v0, r, f)) else "held"
        rep["muscles"][i] = {"status": status, "her_label": hid, "partial_label": part, "chamfer_mm_before": round(c0[2], 2), "chamfer_mm_after": round(c1[2], 2),
                             "stretch_area_pct_before": round(p0, 1), "stretch_area_pct_after": round(p1, 1), "folded_edges_pct_before": round(f0, 2), "folded_edges_pct_after": round(f1, 2),
                             "volume_ratio_after": round(vr, 3), "mean_move_mm": round(float(np.linalg.norm(v1 - v0, axis=1).mean()), 1)}
        log(f"  Q194 right forearm {i:36s} {status:8s} her-label chamfer {c0[2]:.1f} -> {c1[2]:.1f} mm, stretch {p0:.0f} -> {p1:.0f} %, vol x{vr:.2f}")
        if status == "refined":
            new[i] = v1
            before[i] = v0
            d["v"] = v1
            m = rep["muscles"][i]
            d["fit_note"] = (d.get("fit_note") or "") + (
                f" Q194: RIGHT FOREARM muscle refined onto her own-model forearm label ({hid.replace('_', ' ')}{', partial label' if part else ''}): two-way median distance {c0[2]:.1f} -> {c1[2]:.1f} mm, "
                f"triangles stretched outside 0.67-1.5x of the Z source {p0:.0f} -> {p1:.0f} %, folded edges {f0:.1f} -> {f1:.1f} %, volume {vr:.2f}x the Z source, mean move {m['mean_move_mm']} mm "
                f"(the hand part is carried by the Q191 taper and unchanged); out of the displayed radius / ulna, inside her skin.")
    if not new:
        return rep
    # followers: tendons, nerves, vessels, fascia and the muscles without a label of hers follow the refined muscles (Q190 propagation rule: Gaussian-weighted mean displacement,
    # sigma 22 mm, gate 35 mm), only part of the way if their own shape would get more distorted
    samp_old = np.vstack([before[i][:: max(1, len(before[i]) // 2500)] for i in new])
    samp_dlt = np.vstack([(new[i] - before[i])[:: max(1, len(before[i]) // 2500)] for i in new])
    tree = cKDTree(samp_old)
    for i in scope:
        d = by[i]
        if i in new or d["cat"] not in FOLLOW_R or H.NOT_BODY.search(i) and d["cat"] == "muscle":
            continue
        if d["cat"] == "muscle" and i in rep["muscles"]:
            continue                                            # a muscle with a label of hers that was held stays
        v0, r, f = d["v"].astype(float), raw[i].astype(float), d["f"]
        dist, idx = tree.query(v0, k=Q.PROP_K, distance_upper_bound=Q.PROP_GATE * 2.5)
        has = np.isfinite(dist[:, 0])
        if not has.any():
            continue
        dd = np.where(np.isfinite(dist), dist, 1e9)
        w = np.exp(-(dd / Q.PROP_SIGMA) ** 2)
        ws = w.sum(1)
        ok = has & (ws > 1e-9)
        ii = np.where(np.isfinite(dist), idx, 0)
        D = np.zeros_like(v0)
        D[ok] = (w[ok][:, :, None] * samp_dlt[ii[ok]]).sum(1) / ws[ok][:, None]
        step = (np.exp(-(dd[:, 0] / Q.PROP_GATE) ** 2) * has)[:, None] * D
        if np.linalg.norm(step, axis=1).max() < 0.3:
            continue
        s0 = Mx.stretch_stats(v0, r, f)
        p0 = 100 * (s0["area_frac_gt1.5"] + s0["area_frac_lt0.67"]) if s0 else 0.0
        for amp in (1.0, 0.6, 0.3):
            v1 = v0 + amp * step
            if d["cat"] in H.SOFT_PUSH_CATS:
                v1 = H.push_out_of_bones(v1, f, zb, np.ones(len(v1), bool), tol=1.5, max_move=7.0)
            v1 = H.clamp_inside_skin(v1, f, np.ones(len(v1), bool), skin, skin_tree, margin=1.0, max_move=14.0)
            s1 = Mx.stretch_stats(v1, r, f)
            p1 = 100 * (s1["area_frac_gt1.5"] + s1["area_frac_lt0.67"]) if s1 else 0.0
            if p1 <= p0 + 3.0 and area_ok(v1, v0, r, f):
                d["v"] = v1
                rep["followers"][i] = {"amplitude": amp, "stretch_area_pct_before": round(p0, 1), "stretch_area_pct_after": round(p1, 1),
                                       "mean_move_mm": round(float(np.linalg.norm(v1 - v0, axis=1).mean()), 1), "max_move_mm": round(float(np.linalg.norm(v1 - v0, axis=1).max()), 1)}
                d["fit_note"] = (d.get("fit_note") or "") + (
                    f" Q194: follows the right forearm muscles refined onto her own-model labels (distance-weighted displacement, {amp:.1f} of it; mean move "
                    f"{rep['followers'][i]['mean_move_mm']} mm, max {rep['followers'][i]['max_move_mm']}; triangles stretched {p0:.0f} -> {p1:.0f} %).")
                break
    log(f"  Q194 right forearm: {len(new)} muscles refined onto her labels, {len(rep['followers'])} followers")
    return rep
