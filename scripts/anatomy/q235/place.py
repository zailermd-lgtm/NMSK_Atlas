"""Q235: placement + guards of the CVH perineal / urethral structures on a page. The registration T (scale, rotation, translation; CVH atlas-axis frame -> page frame) comes from fit.py (bones only). Guards are
signed distances / masks of EVERY vertex; a structure that fails is not shipped."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, trimesh
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q235 import cvh, register as R, fit as Fm, structs as ST  # noqa: E402
from scripts.anatomy.q234 import place as P4  # noqa: E402
from scripts.transfer.q233_own_f import mask_of  # noqa: E402

ATTACH = {"ischiocavernosus_cvh", "clitoris_cavernous_body", "deep_perineal_muscle_cvh", "superficial_transverse_perineal_cvh", "urethral_sphincter_cvh", "urethral_compressor_cvh"}   # muscles / crura that attach to the ischiopubic bone
MAX_SHIFT_MM = 3.0           # an attachment structure may be moved out of the bone by at most this much (registration error), for at most MAX_SHIFT_FRAC of its vertices
MAX_SHIFT_FRAC = 0.15
BONE_MIN_FREE = 1.0          # non-attachment structures: signed distance to every bone >= this (mm, positive = outside)
BONE_MIN_ATTACH = 0.25
SOFT_TOL_MM = 5.0            # a vertex deeper than this inside the page's bladder / rectum + sigmoid / HRA vagina counts as a penetration: about the root-sum-square of the two bone-registration p90 residuals (CVH -> her bones 3.2 mm, HRA -> her bones 3.5 mm = 4.8 mm)
SOFT_DEPTH_MM = SOFT_TOL_MM
SOFT_MAX_PCT_DEEP = 5.0      # at most this share of the vertices may be a penetration
SKIN_MIN_MM = 2.0            # distance from the nearest skin sample (inside the envelope)


def skin_envelope(sv, sf, lo, hi, pitch=1.5):
    """boolean mask (inside the page skin) on a grid: skin triangles in the box rasterised, 3-D closing, every axial (constant Y) slice hole-filled. Valid where the axial skin contour is closed (checked by the caller:
    a point far above / below the body is reported outside)"""
    shape = tuple(np.ceil((hi - lo) / pitch).astype(int))
    sel = np.any(((sv[sf] >= lo - 20) & (sv[sf] <= hi + 20)).all(2), axis=1) | np.all(((sv[sf].mean(1) >= lo - 20) & (sv[sf].mean(1) <= hi + 20)), axis=1)
    m = trimesh.Trimesh(sv, sf[sel], process=False)
    np.random.seed(0)
    pts = m.sample(int(m.area / (pitch * pitch * 0.2)) + 3000)
    idx = np.floor((pts - lo) / pitch).astype(int)
    ok = np.all((idx >= 0) & (idx < np.array(shape)), axis=1)
    g = np.zeros(shape, bool); g[tuple(idx[ok].T)] = True
    st = ndi.generate_binary_structure(2, 2)
    out = np.zeros(shape, bool)
    for j in range(shape[1]):
        sl = ndi.binary_dilation(g[:, j - 1:j + 2, :].any(1) if j > 0 else g[:, j, :], structure=st, iterations=2)     # the skin triangles cut a slice in a ragged line: thicken, fill, shrink back
        out[:, j, :] = ndi.binary_erosion(ndi.binary_fill_holes(sl), structure=st, iterations=2) | g[:, j, :]
    return out, lo, pitch


def in_grid(mask, lo, pitch, P):
    idx = np.floor((P - lo) / pitch).astype(int)
    ok = np.all((idx >= 0) & (idx < np.array(mask.shape)), axis=1)
    v = np.zeros(len(P), bool)
    v[ok] = mask[tuple(idx[ok].T)]
    return v


class Page:
    """evidence of one page in its atlas frame. ev: key -> (V, F); keys used: hip_bone_l/r, sacrum, sacrum_fill, coccyx, skin, urinary_bladder (or zan_urinary_bladder), rectum, sigmoid_colon (or zan_sigmoid_colon), vagina, uterus,
    external_anal_sphincter (+ the page's own perineal muscles for the report)"""

    def __init__(self, ev, name):
        self.ev, self.name = ev, name
        self.bones = []
        for k in ("hip_bone_l", "hip_bone_r", "sacrum", "sacrum_fill", "coccyx"):
            if k in ev:
                V, F = Fm.largest(*ev[k]) if k in ("sacrum",) else ev[k]
                self.bones.append(trimesh.Trimesh(V, F, process=False))
        self.skin = ev["skin"]
        self.sk_tree = cKDTree(Fm.sample(*self.skin, 250000))
        self.vag = ev["vagina"]
        self.soft = {}
        for nm, keys in (("bladder", ("urinary_bladder", "zan_urinary_bladder")), ("rectum_sigmoid", ("rectum", "sigmoid_colon", "zan_sigmoid_colon")), ("vagina_HRA", ("vagina",)), ("uterus_HRA", ("uterus",))):
            self.soft[nm] = [ev[k] for k in keys if k in ev]
        self._masks = None

    def masks(self, lo, hi, pitch=1.0):
        if self._masks is None or (self._masks[0] != tuple(lo)):
            shape = tuple(np.ceil((hi - lo) / pitch).astype(int))
            self._masks = (tuple(lo), {nm: np.any([mask_of(v, f, lo, shape, pitch) for v, f in lst], axis=0) for nm, lst in self.soft.items() if lst}, pitch)
        return self._masks[1], self._masks[2]


def place_structure(page, key, parts, T, side_assign, env):
    """parts = ST.build output (list of dict V,F,x_mid,info). T = (s,R,t). Returns list of dict(sid, name, side, V, F, gates, info). side_assign(x_mid_page) -> 'l'/'r'/None"""
    out = []
    s = T[0]
    for part in parts:
        W = R.apply(T, part["V"]); F = part["F"]
        xm = float(W[:, 0].mean())
        out.append(dict(key=key, V=W, F=F, side=("l" if xm < 0 else "r") if ST.S[key][6] else None, info=part["info"], meatus=(R.apply(T, part["meatus"][None])[0] if "meatus" in part else None)))
    return out


def guards(page, item, env, attach):
    """gates of one placed structure (modifies item['V'] only for attachment structures: vertices that the registration error left inside a bone are moved out along the bone normal, recorded)"""
    V = item["V"].copy(); F = item["F"]
    g = {}
    sd0, n0 = P4.bone_signed(page.bones, V)
    g["bone_min_mm_before"] = round(float(sd0.min()), 2)
    g["vertices_inside_bone_before"] = int((sd0 < 0).sum())
    moved, maxm = 0, 0.0
    if attach:
        V, moved, maxm = P4.rest_on_bone(V, page.bones, margin=BONE_MIN_ATTACH)
    sd, _ = P4.bone_signed(page.bones, V)
    g.update(bone_min_mm=round(float(sd.min()), 2), vertices_moved_out_of_bone=int(moved), max_move_out_of_bone_mm=round(maxm, 2), vertices_within_1mm_of_bone=int((np.abs(sd) < 1).sum()), vertices=int(len(V)))
    mask, lo, pitch = env
    ins = in_grid(mask, lo, pitch, V)
    g["vertices_outside_skin_envelope"] = int((~ins).sum())
    dsk = page.sk_tree.query(V)[0]
    g["skin_distance_min_mm"] = round(float(dsk.min()), 1)
    g["skin_distance_median_mm"] = round(float(np.median(dsk)), 1)
    item["V"] = V
    return g


def soft_overlap(page, items, lo, hi):
    """vertices inside the page's soft organs: % inside, % deeper than SOFT_DEPTH_MM, max depth (mm; depth = Euclidean distance to the organ boundary on the 1 mm grid)"""
    masks, pitch = page.masks(lo, hi)
    shape = next(iter(masks.values())).shape
    edt = {nm: ndi.distance_transform_edt(g) * pitch for nm, g in masks.items()}
    for it in items:
        V = it["V"]
        idx = np.floor((V - lo) / pitch).astype(int)
        ok = np.all((idx >= 0) & (idx < np.array(shape)), axis=1)
        d = {}
        for nm, g in masks.items():
            dep = np.zeros(len(V)); dep[ok] = edt[nm][tuple(idx[ok].T)]
            d[nm] = dict(pct_inside=round(100 * float((dep > 0).mean()), 1), pct_deeper_than_tol=round(100 * float((dep > SOFT_DEPTH_MM).mean()), 1), max_depth_mm=round(float(dep.max()), 1))
        it["gates"]["page_organ_overlap"] = d
