"""Q173: his adductor magnus (posterior surface) and biceps femoris long head / semitendinosus (anterior surfaces)
snapped onto the fat plane photographed in his 0.33 mm cryosections; his Q57 sciatic nerve put into the same frame.

    # measure (needs the re-streamed crops, scripts/cryo/vhm_stream_leg_crops.py --box right=0,215,-135,60
    #          --box left=-215,0,-135,60 --ap-row -1 --y-top -40 --y-bot -470 --out SCRATCH/q173/thigh):
    python3 scripts/cryo/vhm_thigh_fat_plane_snap.py measure --crops SCRATCH/q173/thigh
    # rebuild from the stored result (no photographs needed; vhm_rebuild_bundle.sh):
    python3 scripts/cryo/vhm_thigh_fat_plane_snap.py apply
    # after the rebuild: overlap numbers on the built subjects and the shipped bundle -> the report
    python3 scripts/cryo/vhm_thigh_fat_plane_snap.py verify --bundle build/viewer_m_hr [--crops SCRATCH/q173/thigh]
    # Q175, his adductor longus (crops: vhm_stream_leg_crops.py --box right=0,170,-60,100 --box left=-170,0,-60,100
    #          --ap-row -1 --y-top 40 --y-bot -285 --out SCRATCH/q175/al):
    python3 scripts/cryo/vhm_thigh_fat_plane_snap.py measure-al --crops SCRATCH/q175/al
    python3 scripts/cryo/vhm_thigh_fat_plane_snap.py verify-al --bundle build/viewer_m_hr --old-bundle SCRATCH/q175/old_bundle

Where his thigh muscles come from: build/vh/vhm_both, the decimated copy (recovered from his published viewer v25) of
the DU lower-extremity release (Andreassen et al. 2023, Sci Data 10:34: manual segmentation of HIS cryosections).

1. REGISTRATION (the main finding). The Q57 crop mapping (legs_total grid flipped + the fixed legs->torso block offset)
   does not put his atlas meshes on the photographs: rasterised sections of ALL his vhm_both thigh muscles match the
   photographed muscle class best (IoU) with the photograph shifted by a constant per side at every level, and his
   femur section (an independent check, bone vs bone) gives the same shift. The nerve was tracked with that mapping,
   so it sat ~2.3 mm ANTERIOR of where his meshes put the same tissue -- most of Q57's 3.0 mm median "inside the
   adductor magnus". This script measures the per-side shift (crop pixels, 0.33 mm) and (a) samples the photographs
   through it and (b) writes the nerve label volume translated by it (vhm_nerves_cryo_reg.nii.gz).
2. SNAP (bounded, posterior/anterior surface only). Meshes are midpoint-subdivided once (~3.8 mm edges). For every
   vertex whose outward normal faces the fat plane (adductor magnus n_z < -0.2; biceps long head / semitendinosus
   n_z > +0.2), the photograph class is read along the inward normal (0.33 mm steps). Vertex on non-muscle ->
   moved in to the first run of >= 1.65 mm photographed muscle; vertex in muscle with muscle outside it and a
   >= 0.66 mm non-muscle run within 2.5 mm inward (it crossed the plane into the neighbour) -> moved past that run.
   Moves only INWARD (the muscle can only shrink, so no new overlap), capped at 8 mm and at 45 % of the local
   thickness; 1-ring median + 3 Laplacian passes (other vertices fixed at 0); a fold guard shrinks any move that
   would flip a face. Muscle class = his colour rule (scripts/cryo/cryo_classes.py) made strict (value < 115,
   g < 0.62 r): the nerve's fascicles (value ~130, g/r ~0.7) are not muscle.
3. Q175 ADDUCTOR LONGUS. His Q174 femoral veins sat 14-21 % inside his (DU, decimated) adductor longus, against its
   ANTEROLATERAL face (the face under the femoral vessels: normals of the entered faces 30-90 deg from lateral toward
   anterior). Same snap, candidate vertices n . (0.5 lateral, 0, 0.87 anterior) > 0.5 (within 60 deg of the anterolateral
   direction) at the vein's levels (y +40..-285). (Attempt 1, > 0.2 as Q173, took the whole lateral-to-anteromedial half:
   left volume -6.3 % > the 5 % stop, with the same vein result.)
   photographs through the Q173 per-side registration (re-checked on these crops: the femur gives the Q173 shift);
   muscle additionally needs red >= 55, because his veins' black clot (red 20-48) passes the strict rule (his adductor
   longus: red 1st percentile 50-59, median 66-78). Moves in task_outputs/vhm_thigh_snap_q175.npz; `apply` adds them to
   ct_vhm_thigh_snap after the six Q173 ids (whose bytes do not change).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
import scipy.sparse as sp

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.vhf_nerve_track import Crops  # noqa: E402

SRC = REPO / "build/vh/vhm_both"
OUT_SUBJ = "ct_vhm_thigh_snap"
T = REPO / "data/ct_sources/task_outputs"
STORE = T / "vhm_thigh_snap_q173.npz"
NERVE_IN = T / "vhm_nerves_cryo.nii.gz"
NERVE_OUT = T / "vhm_nerves_cryo_reg.nii.gz"
REPORT = REPO / "data/derived/Q173_vhm_adductor_magnus.json"
ORIGIN = np.array([-6.035, -895.476, 4.787])
PX = 0.99 / 3                                   # crop pixel, mm (full resolution = 3 x the 0.99-scaled 1 mm photo)
# (atlas id, side, facing: -1 posterior surface / +1 anterior surface, piece index to snap or None = all)
SPEC = (("adductor_magnus_r", "right", -1, None), ("adductor_magnus_l", "left", -1, None),
        ("biceps_femoris_r", "right", 1, 0), ("biceps_femoris_l", "left", 1, 0),      # piece 0 = long head (from the tuberosity)
        ("semitendinosus_r", "right", 1, None), ("semitendinosus_l", "left", 1, None))
THIGH = ["adductor_magnus", "adductor_longus", "adductor_brevis", "biceps_femoris", "semimembranosus", "semitendinosus",
         "gracilis", "sartorius", "vastus_lateralis", "vastus_medialis", "vastus_intermedius", "rectus_femoris",
         "gluteus_maximus", "tensor_fasciae_latae", "pectineus", "iliopsoas"]
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): his colour cryosections at full "
          "resolution (0.33 mm, NCI Imaging Data Commons) re-streamed by scripts/cryo/vhm_stream_leg_crops.py; his thigh "
          "muscles from build/vh/vhm_both = the DU lower-extremity release (Andreassen TE et al., Sci Data 10:34 (2023), "
          "doi:10.1038/s41597-022-01905-2, CC BY 4.0) as recovered from his published viewer v25; his sciatic nerve from "
          "Q57 (data/ct_sources/task_outputs/vhm_nerves_cryo.nii.gz, scripts/cryo/vhf_nerve_track.py + vhf_nerve_volume.py).")
BADGE_MUSCLE = ("{surf} surface moved onto the fat plane photographed in his own 0.33 mm cryosections (Q173): inward only, "
                "median {med:.1f} mm, max {mx:.1f} mm (cap 8 mm), {pct:.0f}% of that surface's vertices moved; volume "
                "{v0:.0f} -> {v1:.0f} cm3 ({dv:+.1f}%). The rest of the mesh is his DU segmentation unchanged. Photographs "
                "sampled through a measured per-side registration (femur + all thigh muscles agree), not the raw crop mapping.")
BADGE_NERVE = ("Traced in his own 0.33 mm cryosections (Q57), placed with the per-side photograph-to-atlas registration measured "
               "on his femur and thigh muscles (Q173: {ap:.1f} mm posterior, left also {ml:.1f} mm lateral). Covers about a "
               "third of its course: right 126 / left 84 verified levels (right y -91..-216, left four runs y -89..-222); "
               "the gluteal and distal thirds are missing. Residual overlap: {res}. The traced outline runs up to ~2.6 mm "
               "past the photographed nerve into muscle in places (22-26% of its voxels lie on photographed muscle).")

# Q175: his adductor longus, anterolateral face (under the femoral vessels), at the femoral vein's levels
STORE_Q175 = T / "vhm_thigh_snap_q175.npz"
REPORT_Q175 = REPO / "data/derived/Q175_vhm_adductor_longus.json"
SPEC_Q175 = (("adductor_longus_r", "right"), ("adductor_longus_l", "left"))
TAG = {aid: "Q175" for aid, _ in SPEC_Q175}
Y_RANGE_Q175 = (-285.0, 40.0)
MIN_RED_Q175 = 55.0
NZ_Q175 = 0.5
NEIGH_Q175 = ["femur", "pectineus", "adductor_brevis", "adductor_magnus", "sartorius", "vastus_medialis", "gracilis", "iliopsoas",
              "femoral_a", "femoral_v", "popliteal_v", "sciatic_n"]
SOURCE_Q175 = ("U.S. National Library of Medicine, The Visible Human Project (public domain): his colour cryosections at full "
               "resolution (0.33 mm, NCI Imaging Data Commons) re-streamed by scripts/cryo/vhm_stream_leg_crops.py; his adductor "
               "longus from build/vh/vhm_both = the DU lower-extremity release (Andreassen TE et al., Sci Data 10:34 (2023), "
               "doi:10.1038/s41597-022-01905-2, CC BY 4.0) as recovered from his published viewer v25; his femoral veins from Q174 "
               "(data/ct_sources/task_outputs/vhm_femoral_cryo.nii.gz, scripts/cryo/vhm_femoral_popliteal_track.py); photograph-to-"
               "atlas registration from Q173 (data/ct_sources/task_outputs/vhm_thigh_snap_q173.npz).")
BADGE_AL = ("Anterolateral surface (the face under the femoral vessels) moved onto the fat plane photographed in his own 0.33 mm "
            "cryosections (Q175): inward only, median {med:.1f} mm, max {mx:.1f} mm (cap 8 mm), {pct:.0f}% of that surface's vertices "
            "moved; volume {v0:.0f} -> {v1:.0f} cm3 ({dv:+.1f}%). The rest of the mesh is his DU segmentation unchanged. Photographs "
            "sampled through the Q173 per-side registration (re-checked on his femur); the femoral vein's clot is not counted as muscle.")


def facing_q175(side):
    sg = 1.0 if side == "right" else -1.0                               # his right leg is atlas +x; lateral = away from 0
    return (0.5 * sg, 0.0, float(np.sqrt(0.75)))


# ----------------------------------------------------------------------------------------------- photographs
def classes(im, min_red=None):
    """0 gel, 1 other tissue, 2 fat, 3 muscle (strict), 4 pale, 5 bone-white -- his colour rule, strict muscle.
    min_red (Q175): muscle also needs red >= min_red -- his femoral veins' black clot (red 20-48) passes the strict rule."""
    im = im.astype(np.float32); r, g, b = im[..., 0], im[..., 1], im[..., 2]; v = im.max(-1); mn = im.min(-1)
    sat = (v - mn) / (v + 1e-3); tissue = r > b + 8
    white = tissue & (v > 200) & (sat < 0.30)
    fat = tissue & (v > 140) & (sat >= 0.30) & (g > 0.72 * r) & ~white
    muscle = tissue & (r > g + 12) & (v < 115) & (g < 0.62 * r) & ~fat
    if min_red is not None:
        muscle &= r >= min_red
    pale = tissue & (v > 150) & (sat < 0.30) & ~white
    out = np.zeros(im.shape[:2], np.uint8); out[tissue] = 1; out[fat] = 2; out[muscle] = 3; out[pale] = 4; out[white] = 5
    return out


class Photo:
    def __init__(self, prefix, side, reg=(0.0, 0.0), min_red=None):
        self.c = Crops(prefix, side); self.cache = {}; self.reg = reg; self.min_red = min_red

    def cls(self, y):
        y = int(y)
        if y not in self.c.j_of:
            return None
        if y not in self.cache:
            if len(self.cache) > 60:
                self.cache.pop(next(iter(self.cache)))
            self.cache[y] = classes(self.c.image(y), self.min_red)
        return self.cache[y]

    def to_px(self, y, x, z):
        pr, pc = self.c.atlas_to_px(y, x, z); return pr + self.reg[0], pc + self.reg[1]

    def sample(self, P):
        P = np.asarray(P, float); out = np.full(len(P), 255, np.uint8); ys = np.rint(P[:, 1]).astype(int)
        for y in np.unique(ys):
            k = self.cls(y)
            if k is None:
                continue
            s = ys == y; pr, pc = self.to_px(y, P[s, 0], P[s, 2]); pr = np.rint(pr).astype(int); pc = np.rint(pc).astype(int)
            ok = (pr >= 0) & (pc >= 0) & (pr < k.shape[0]) & (pc < k.shape[1]); o = np.full(s.sum(), 255, np.uint8)
            o[ok] = k[pr[ok], pc[ok]]; out[s] = o
        return out

    def raster(self, meshes, y, shape):
        img = Image.new("L", (shape[1], shape[0]), 0); dr = ImageDraw.Draw(img)
        for v, f in meshes:
            if v[:, 1].min() > y or v[:, 1].max() < y:
                continue
            s = trimesh.Trimesh(v, f, process=False).section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
            if s is None:
                continue
            for e in s.entities:
                p = s.vertices[e.points]; pr, pc = self.to_px(y, p[:, 0], p[:, 2])
                if len(pr) >= 3:
                    dr.polygon(list(zip(pc.tolist(), pr.tolist())), fill=1)
        return np.asarray(img, bool)


# ----------------------------------------------------------------------------------------------- meshes
def load_subject(d):
    d = Path(d); m = json.loads((d / "manifest.json").read_text())
    V = np.frombuffer((d / "vertices.f32").read_bytes(), np.float32).reshape(-1, 3)
    F = np.frombuffer((d / "faces.u32").read_bytes(), np.uint32).reshape(-1, 3)
    return m, V, F


def pieces_of(m, V, F, aid):
    out = []
    for s in m["structures"]:
        if s["atlas_id"] == aid:
            v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]].astype(np.float64)
            f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
            out.append((s, v, f))
    return out


def by_id(m, V, F, ids=None):
    out = {}
    for s in m["structures"]:
        a = s["atlas_id"]
        if ids is not None and a not in ids:
            continue
        v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]].astype(np.float64)
        f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
        if a in out:
            f = f + len(out[a][0]); out[a] = (np.concatenate([out[a][0], v]), np.concatenate([out[a][1], f]))
        else:
            out[a] = (v, f)
    return out


def outward_normals(v, f):
    tm = trimesh.Trimesh(v, f, process=False)
    return tm.vertex_normals * (1.0 if tm.volume > 0 else -1.0)


def neighbours(nv, f):
    e = np.r_[f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]
    A = sp.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv)).tocsr(); A = ((A + A.T) > 0).astype(float)
    return A, [A.indices[A.indptr[i]:A.indptr[i + 1]] for i in range(nv)]


def run_start(mask, i0, R):
    n, TT = mask.shape; cs = np.concatenate([np.zeros((n, 1)), np.cumsum(mask, 1)], 1)
    ok = np.zeros((n, TT), bool); ok[:, :TT - R + 1] = (cs[:, R:] - cs[:, :TT - R + 1]) == R; ok[:, :i0] = False
    return np.where(ok.any(1), ok.argmax(1), -1)


def snap(v, f, photo, facing, nz_min=0.2, MAX=8.0, R_muscle=5, R_fat=2, t_cross=2.5, thick_frac=0.45, smooth_iter=3, y_range=None):
    """facing: +-1 = anterior/posterior (atlas z, Q173) or a 3-vector (Q175: anterolateral); y_range = (lo, hi) limits the
    candidate vertices to those levels."""
    n = outward_normals(v, f); tm = trimesh.Trimesh(v, f, process=False)
    fv = np.array([0.0, 0.0, float(facing)]) if np.ndim(facing) == 0 else np.asarray(facing, float)
    ok = n @ fv > nz_min
    if y_range is not None:
        ok &= (v[:, 1] >= y_range[0]) & (v[:, 1] <= y_range[1])
    cand = np.nonzero(ok)[0]
    Ts = np.arange(-3.0, MAX + 2.0 + 1e-6, PX); i0 = int(np.argmin(np.abs(Ts)))
    c = photo.sample((v[cand, None, :] - Ts[None, :, None] * n[cand, None, :]).reshape(-1, 3)).reshape(len(cand), len(Ts))
    known = (c != 255).all(1); mus = c == 3
    locs, ri, _ = tm.ray.intersects_location(v[cand] - 0.05 * n[cand], -n[cand], multiple_hits=False)
    thick = np.full(len(cand), np.inf)
    if len(ri):
        thick[ri] = np.linalg.norm(locs - v[cand][ri], axis=1)
    d = np.zeros(len(cand))
    A_ = known & ~mus[:, i0]; sA = run_start(mus, i0, R_muscle); okA = A_ & (sA >= 0); d[okA] = Ts[sA[okA]]
    it = int(np.argmin(np.abs(Ts - t_cross))); io = int(np.argmin(np.abs(Ts + 1.5)))
    Bm = known & mus[:, i0] & (mus[:, io:i0].mean(1) >= 0.8)
    sF = run_start(~mus, i0, R_fat); okF = Bm & (sF >= 0) & (sF <= it)
    sB = np.array([run_start(mus[j:j + 1], sF[j], R_muscle)[0] if okF[j] else -1 for j in range(len(cand))])
    okB = okF & (sB >= 0); d[okB] = Ts[sB[okB]]
    d = np.minimum(d, thick_frac * thick); over = d > MAX; d[over] = 0
    D = np.zeros(len(v)); D[cand] = d
    Adj, nb = neighbours(len(v), f); isc = np.zeros(len(v), bool); isc[cand] = True
    Dm = D.copy()
    for i in cand:
        Dm[i] = np.median(np.r_[D[i], D[nb[i]]])
    D = Dm; deg = np.asarray(Adj.sum(1)).ravel()
    for _ in range(smooth_iter):
        D = np.where(isc, 0.5 * D + 0.5 * (Adj @ D) / np.maximum(deg, 1), 0.0)
    D = np.clip(D, 0, MAX); fn0 = tm.face_normals; nfix = 0
    for _ in range(25):
        bad = (trimesh.Trimesh(v - D[:, None] * n, f, process=False).face_normals * fn0).sum(1) < 0.2
        if not bad.any():
            break
        for i in np.unique(f[bad]):
            D[i] = min(D[i], D[nb[i]].min()); nfix += 1
    info = {"surface_vertices": int(len(cand)), "on_non_muscle_moved_in": int(okA.sum()),
            "on_non_muscle_no_muscle_within_cap": int((A_ & ~okA).sum()), "crossed_into_neighbour": int(okB.sum()),
            "over_cap_left": int(over.sum()), "fold_guard_updates": nfix}
    return D, info


def surface_move_stats(D, cand_n):
    mv = D[D > 0.05]
    return {"moved_vertices": int(len(mv)), "surface_vertices": int(cand_n),
            "median_mm": round(float(np.median(mv)), 2) if len(mv) else 0.0,
            "p95_mm": round(float(np.percentile(mv, 95)), 2) if len(mv) else 0.0, "max_mm": round(float(mv.max()), 2) if len(mv) else 0.0}


def vol_cm3(v, f):
    return abs(trimesh.Trimesh(v, f, process=False).volume) / 1000.0


# ----------------------------------------------------------------------------------------------- registration
def fit_registration(prefix, meshes, femurs, levels=range(-60, -401, -20), rng=12):
    """Per side: crop-pixel shift (rows, cols) of the photograph that best matches (IoU) his rasterised thigh-muscle
    sections to the photographed muscle class; parabolic sub-pixel peak; femur (bone blob) fitted independently."""
    sh = np.arange(-rng, rng + 1)

    def best(mesh, ref):
        G = np.zeros((len(sh), len(sh)))
        for a, dr in enumerate(sh):
            for b, dc in enumerate(sh):
                m2 = np.roll(np.roll(ref, -dr, 0), -dc, 1); G[a, b] = (mesh & m2).sum() / max((mesh | m2).sum(), 1)
        a, b = np.unravel_index(G.argmax(), G.shape)

        def par(g0, g1, g2):
            q = g0 - 2 * g1 + g2; return 0.0 if q >= 0 else 0.5 * (g0 - g2) / q
        ra = par(G[a - 1, b], G[a, b], G[a + 1, b]) if 0 < a < len(sh) - 1 else 0.0
        rb = par(G[a, b - 1], G[a, b], G[a, b + 1]) if 0 < b < len(sh) - 1 else 0.0
        return float(sh[a] + ra), float(sh[b] + rb), float(G.max()), float(G[rng, rng])
    out = {}
    for side, sfx in (("right", "_r"), ("left", "_l")):
        ph = Photo(prefix, side); mus_rows, fem_rows = [], []
        ms = [meshes[n + sfx] for n in THIGH if n + sfx in meshes]
        for y in levels:
            k = ph.cls(y)
            if k is None:
                continue
            mus_rows.append((y,) + best(ph.raster(ms, y, k.shape), k == 3))
            fm = ph.raster([femurs[side]], y, k.shape)
            if fm.sum() == 0:
                continue
            nm = ndi.binary_opening((k != 3) & (k != 0), iterations=3); rr, cc = np.nonzero(fm)
            lab, _ = ndi.label(nm); L = lab[int(rr.mean()), int(cc.mean())]
            if L == 0:
                continue
            bone = ndi.binary_fill_holes(lab == L)
            if bone.sum() > 4 * fm.sum():
                continue
            fem_rows.append((y,) + best(fm, bone))
        M = np.array([r[1:3] for r in mus_rows]); Fm = np.array([r[1:3] for r in fem_rows])
        out[side] = {"shift_px_rows_cols": [round(float(np.median(M[:, 0])), 2), round(float(np.median(M[:, 1])), 2)],
                     "muscle_levels": len(mus_rows), "muscle_iqr_rows": np.percentile(M[:, 0], [25, 75]).round(2).tolist(),
                     "muscle_iqr_cols": np.percentile(M[:, 1], [25, 75]).round(2).tolist(),
                     "muscle_iou_median_at_zero_vs_fit": [round(float(np.median([r[4] for r in mus_rows])), 3), round(float(np.median([r[3] for r in mus_rows])), 3)],
                     "femur_shift_px_median": np.median(Fm, 0).round(2).tolist() if len(Fm) else None, "femur_levels": len(fem_rows),
                     "femur_iou_median_at_zero_vs_fit": [round(float(np.median([r[4] for r in fem_rows])), 3), round(float(np.median([r[3] for r in fem_rows])), 3)] if fem_rows else None,
                     "per_level_muscle": [[int(r[0]), round(r[1], 2), round(r[2], 2), round(r[3], 3), round(r[4], 3)] for r in mus_rows],
                     "per_level_femur": [[int(r[0]), round(r[1], 2), round(r[2], 2), round(r[3], 3), round(r[4], 3)] for r in fem_rows]}
    return out


def reg_atlas_shift(reg):
    """crop shift (rows, cols) -> atlas translation of what the photograph shows (the nerve): rows are posterior-ward
    (atlas -z), cols are atlas -x... see Crops.atlas_to_px: +1 crop row = +sc/3 mm atlas z; +1 crop col = -sc/3 mm atlas x."""
    dr, dc = reg; return np.array([dc * PX, 0.0, -dr * PX])


# ----------------------------------------------------------------------------------------------- outputs
def write_subject(pieces_out, badges, note):
    d = REPO / "build/vh" / OUT_SUBJ; d.mkdir(parents=True, exist_ok=True)
    _, V, F = load_subject(SRC)
    vs, fs, structs = [], [], []; vo = fo = 0
    for aid, pieces in pieces_out.items():
        for s, v, f in pieces:
            e = {"atlas_id": aid, "source_structure": s["source_structure"], "side": s.get("side"),
                 "source_file": f"vhm_both#{aid} (DU release, recovered v25) + {TAG.get(aid, 'Q173')} fat-plane snap",
                 "vertex_offset": vo, "face_offset": fo, "vertex_count": int(len(v)), "triangle_count": int(len(f)),
                 "bbox_min_mm": [round(float(x), 4) for x in v.min(0)], "bbox_max_mm": [round(float(x), 4) for x in v.max(0)],
                 "procedural_badge": badges[aid]}
            structs.append(e); vs.append(v.astype(np.float32)); fs.append((f + vo).astype(np.uint32)); vo += len(v); fo += len(f)
    Vall = np.concatenate(vs); Fall = np.concatenate(fs)
    (d / "vertices.f32").write_bytes(Vall.tobytes()); (d / "faces.u32").write_bytes(Fall.tobytes())
    srcm = json.loads((SRC / "manifest.json").read_text())
    man = {"subject": OUT_SUBJ, "frame": srcm["frame"], "source_volume": None,
           "source_kind": "vhm_both meshes, posterior/anterior thigh surfaces snapped to his photographed fat plane (Q173)",
           "vertex_count": int(len(Vall)), "triangle_count": int(len(Fall)),
           "bbox_min_mm": [round(float(x), 4) for x in Vall.min(0)], "bbox_max_mm": [round(float(x), 4) for x in Vall.max(0)],
           "attribution": srcm.get("attribution", []), "note": note, "structures": structs}
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    return d


def build_pieces(D_store, spec=SPEC):
    """vhm_both pieces -> snapped pieces from the stored per-vertex inward moves (keys '<aid>#<piece>')."""
    m, V, F = load_subject(SRC); out = {}; before = {}
    for aid, *_ in spec:
        out[aid] = []; before[aid] = []
        for i, (s, v, f) in enumerate(pieces_of(m, V, F, aid)):
            key = f"{aid}#{i}"
            if key in D_store:
                v2, f2 = trimesh.remesh.subdivide(v, f); n = outward_normals(v2, f2); D = D_store[key]
                assert len(D) == len(v2), key
                out[aid].append((s, v2 - D[:, None] * n, f2)); before[aid].append((s, v2, f2))
            else:
                out[aid].append((s, v, f)); before[aid].append((s, v, f))
    return out, before


def write_nerve(reg, src=NERVE_IN, dst=NERVE_OUT):
    import nibabel as nib
    img = nib.load(str(src)); L = np.asarray(img.dataobj).copy(); A = img.affine.copy()
    vox = np.abs(np.diag(A)[:3]); assert A[0, 0] > 0 and A[1, 1] > 0, "expects a +x +y RAS grid (vhf_nerve_volume.py)"
    sR = reg_atlas_shift(reg["right"]); sL = reg_atlas_shift(reg["left"])
    # atlas (x, z) = RAS (x, y) - origin; the AP shift is common to both sides -> exact, in the affine;
    # the per-side x difference is applied in whole voxels (0.5 mm) to the left leg's voxels
    ap = 0.5 * (sR[2] + sL[2]); dx_vox = int(round((sL[0] - sR[0]) / vox[0]))
    nx = L.shape[0]; left = (A[0, 3] + vox[0] * np.arange(nx)) - ORIGIN[0] < 0      # atlas x < 0
    pad = abs(dx_vox); off_r = pad if dx_vox < 0 else 0; off_l = off_r + dx_vox
    L2 = np.zeros((nx + pad,) + L.shape[1:], L.dtype)
    L2[off_r:off_r + nx][~left] = L[~left]
    sub = L2[off_l:off_l + nx]; sub[left] = np.maximum(sub[left], L[left])
    A[0, 3] += -off_r * vox[0] + sR[0]; A[1, 3] += ap
    nib.save(nib.Nifti1Image(L2, A), str(dst))
    return {"ap_shift_mm_atlas_z": round(float(ap), 3), "right_x_shift_mm": round(float(sR[0]), 3),
            "left_x_shift_mm_applied": round(float(sR[0] + dx_vox * vox[0]), 3), "left_x_shift_mm_measured": round(float(sL[0]), 3),
            "voxels_in": int((L > 0).sum()), "voxels_out": int((L2 > 0).sum())}


def badges_for(stats):
    b = {}
    for aid, side, facing, piece in SPEC:
        st = stats[aid]; surf = "Posterior" if facing < 0 else ("Anterior (long head)" if piece == 0 else "Anterior")
        b[aid] = BADGE_MUSCLE.format(surf=surf, med=st["move"]["median_mm"], mx=st["move"]["max_mm"],
                                     pct=100 * st["move"]["moved_vertices"] / max(st["move"]["surface_vertices"], 1),
                                     v0=st["volume_cm3"][0], v1=st["volume_cm3"][1], dv=st["volume_change_pct"])
    return b


def photo_overlap(prefix, reg, meshes_before, meshes_after, side, levels, min_red=None):
    """section area on photographed muscle / total, and photographed muscle removed (cm3), every 2 mm."""
    ph = Photo(prefix, side, reg, min_red); a0 = a1 = m0 = m1 = lost = 0
    for y in levels:
        k = ph.cls(y)
        if k is None:
            continue
        mus = k == 3; r0 = ph.raster(meshes_before, y, k.shape); r1 = ph.raster(meshes_after, y, k.shape)
        a0 += r0.sum(); a1 += r1.sum(); m0 += (r0 & mus).sum(); m1 += (r1 & mus).sum(); lost += (r0 & ~r1 & mus).sum()
    step = abs(levels[1] - levels[0]) if len(levels) > 1 else 1; px2 = PX * PX * step / 1000.0
    return {"on_photographed_muscle_frac_before": round(m0 / max(a0, 1), 4), "on_photographed_muscle_frac_after": round(m1 / max(a1, 1), 4),
            "non_muscle_inside_cm3_before": round((a0 - m0) * px2, 2), "non_muscle_inside_cm3_after": round((a1 - m1) * px2, 2),
            "photographed_muscle_cut_away_cm3": round(lost * px2, 2), "levels_every_mm": step}


def measure(a):
    m, V, F = load_subject(SRC); allm = by_id(m, V, F)
    femurs = {"right": allm["femur_r"], "left": allm["femur_l"]}
    reg_fit = fit_registration(a.crops, allm, femurs)
    reg = {s: tuple(reg_fit[s]["shift_px_rows_cols"]) for s in ("right", "left")}
    print("registration", reg, flush=True)
    ph = {s: Photo(a.crops, s, reg[s]) for s in reg}
    D_store = {}; stats = {}
    for aid, side, facing, piece in SPEC:
        mv = {"moved_vertices": 0, "surface_vertices": 0}; allD = []
        for i, (s, v, f) in enumerate(pieces_of(m, V, F, aid)):
            if piece is not None and i != piece:
                continue
            v2, f2 = trimesh.remesh.subdivide(v, f); D, info = snap(v2, f2, ph[side], facing)
            D_store[f"{aid}#{i}"] = np.round(D, 3); allD.append(D); stats.setdefault(aid, {})[f"piece{i}_snap"] = info
            mv["surface_vertices"] += info["surface_vertices"]
        D = np.concatenate(allD); st = surface_move_stats(D, mv["surface_vertices"]); stats[aid]["move"] = st
        print(aid, st, flush=True)
    np.savez_compressed(STORE, reg=json.dumps({s: list(r) for s, r in reg.items()}), **{k.replace("#", "__"): v for k, v in D_store.items()})
    after, before = build_pieces(D_store)
    for aid, side, facing, piece in SPEC:
        v0 = sum(vol_cm3(v, f) for _, v, f in before[aid]); v1 = sum(vol_cm3(v, f) for _, v, f in after[aid])
        stats[aid]["volume_cm3"] = [round(v0, 1), round(v1, 1)]; stats[aid]["volume_change_pct"] = round(100 * (v1 - v0) / v0, 2)
        ys = [p[1][:, 1] for p in before[aid]]; lo = max(-468, int(np.ceil(min(y.min() for y in ys)))); hi = min(-41, int(np.floor(max(y.max() for y in ys))))
        stats[aid]["photo"] = photo_overlap(a.crops, reg[side], [(v, f) for _, v, f in before[aid]], [(v, f) for _, v, f in after[aid]], side, list(range(hi, lo - 1, -2)))
        print(aid, stats[aid]["volume_cm3"], stats[aid]["photo"], flush=True)
    badges = badges_for(stats)
    write_subject(after, badges, "Q173: see data/derived/Q173_vhm_adductor_magnus.json")
    nerve = write_nerve(reg)
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    rep.update({"source": SOURCE, "subject": OUT_SUBJ, "origin_atlas_mm": ORIGIN.tolist(), "method": __doc__.split("Where his")[1].strip(),
                "supplier": {"subject": "vhm_both", "what": "DU lower-extremity release (Andreassen 2023): manual segmentation of his cryosections; "
                             "decimated copy recovered from his published viewer v25 (adductor magnus ~3.6k triangles, ~7.5 mm edges)"},
                "registration": {"crop_px_mm": PX, "fit": reg_fit, "used_px": {s: list(r) for s, r in reg.items()}, "nerve_volume": nerve},
                "params": {"nz_min": 0.2, "max_move_mm": 8.0, "muscle_run_mm": 5 * PX, "fat_run_mm": 2 * PX, "cross_window_mm": 2.5,
                           "thickness_cap": 0.45, "smoothing": "1-ring median + 3 Laplacian passes (others fixed at 0) + fold guard",
                           "subdivision": "midpoint x1"},
                "structures": stats, "badges": badges, "stored_moves": str(STORE.relative_to(REPO)), "nerve_volume": str(NERVE_OUT.relative_to(REPO))})
    REPORT.write_text(json.dumps(rep, indent=1)); print("wrote", REPORT)


def load_store():
    z = np.load(STORE); reg = {s: tuple(r) for s, r in json.loads(str(z["reg"])).items()}
    return reg, {k.replace("__", "#"): z[k] for k in z.files if k != "reg"}


def apply(a):
    reg, D_store = load_store(); after, _ = build_pieces(D_store)
    rep = json.loads(REPORT.read_text()); badges = dict(rep["badges"]); note = "Q173: see data/derived/Q173_vhm_adductor_magnus.json"
    if STORE_Q175.exists() and REPORT_Q175.exists():                      # Q175 adductor longus, after the six Q173 ids
        after.update(build_pieces(load_store_q175()[1], SPEC_Q175)[0]); badges.update(json.loads(REPORT_Q175.read_text())["badges"])
        note += "; Q175 (adductor longus): data/derived/Q175_vhm_adductor_longus.json"
    write_subject(after, badges, note)
    if not NERVE_OUT.exists() or a.force_nerve:
        print("nerve", write_nerve(reg))
    print("wrote build/vh/" + OUT_SUBJ)


def inside_depth(P, v, f):
    tm = trimesh.Trimesh(v, f, process=False); c = tm.contains(P); d = np.zeros(len(P))
    if c.any():
        d[c] = trimesh.proximity.closest_point(tm, P[c])[1]
    return c, d


def nerve_stats(P, v, f):
    c, d = inside_depth(P, v, f)
    return {"vertices_inside": int(c.sum()), "of": int(len(P)), "beyond_1mm": int((d > 1).sum()),
            "median_depth_mm": round(float(np.median(d[c])), 2) if c.any() else 0.0, "max_depth_mm": round(float(d.max()), 2) if c.any() else 0.0}


def verify(a):
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    rep = json.loads(REPORT.read_text()); reg, D_store = load_store(); after, before = build_pieces(D_store)
    mN, VN, FN = load_subject(REPO / "build/vh/ct_vhm_sciatic"); nv, nf = by_id(mN, VN, FN)["sciatic_n"]
    # the Q57 (unregistered) nerve = the registered one moved back
    info = rep["registration"]["nerve_volume"]; back = {}; back["left"] = np.array([-info["left_x_shift_mm_applied"], 0.0, -info["ap_shift_mm_atlas_z"]])
    back["right"] = np.array([-info["right_x_shift_mm"], 0.0, -info["ap_shift_mm_atlas_z"]])
    bf, blob = read_bundle_dir(a.bundle); B = meshes_by_id(bf, blob); O = None
    if a.old_bundle:
        ob = json.loads(Path(a.old_bundle + ".json").read_text()); O = meshes_by_id(ob, Path(a.old_bundle + ".bin").read_bytes())
    out = {}
    for aid, side, facing, piece in SPEC:
        sg = 1 if side == "right" else -1; P = nv[sg * nv[:, 0] > 0]
        vb = np.concatenate([p[1] for p in before[aid]]); fb = np.concatenate([p[2] + sum(len(q[1]) for q in before[aid][:j]) for j, p in enumerate(before[aid])])
        va = np.concatenate([p[1] for p in after[aid]]); fa = np.concatenate([p[2] + sum(len(q[1]) for q in after[aid][:j]) for j, p in enumerate(after[aid])])
        out[aid] = {"q57_nerve_as_shipped_before_q173_vs_old_mesh": nerve_stats(P + back[side], vb, fb),
                    "registered_nerve_vs_old_mesh": nerve_stats(P, vb, fb),
                    "registered_nerve_vs_new_mesh": nerve_stats(P, va, fa),
                    "registered_nerve_vs_shipped_bundle_mesh": nerve_stats(P, B[aid]["v"], B[aid]["f"])}
        # neighbours: surface-area samples of the changed mesh inside the femur / other thigh muscles, old bundle vs new bundle
        nb = {}
        if O is not None:
            def samp(mm):
                return trimesh.sample.sample_surface(trimesh.Trimesh(mm["v"], mm["f"], process=False), 20000, seed=0)[0]
            p0, p1 = samp(O[aid]), samp(B[aid])
            for other in ["femur"] + THIGH:
                oid = other + ("_r" if side == "right" else "_l")
                if oid == aid or oid not in B:
                    continue
                c0, d0 = inside_depth(p0, O[oid]["v"], O[oid]["f"]); c1, d1 = inside_depth(p1, B[oid]["v"], B[oid]["f"])
                if c0.sum() or c1.sum():
                    nb[oid] = {"frac_old": round(float(c0.mean()), 4), "frac_new": round(float(c1.mean()), 4),
                               "max_depth_old_mm": round(float(d0.max()), 2), "max_depth_new_mm": round(float(d1.max()), 2)}
        out[aid]["surface_inside_neighbour_old_vs_new_bundle"] = nb
        print(aid, json.dumps(out[aid])[:400], flush=True)
    sk = B.get("skin"); outside = None
    if sk is not None:
        c, _ = inside_depth(nv[::5], sk["v"], sk["f"]); outside = round(float(1 - c.mean()), 4)
    rep["verify"] = {"bundle": a.bundle, "per_structure": out, "nerve_vertices": int(len(nv)), "nerve_outside_skin_frac_sampled": outside,
                     "inside_test": "trimesh contains (agreed 100% with a generalized winding-number test on 5000 nerve vertices vs adductor_magnus_r)"}
    if a.crops:
        rows = {}
        import nibabel as nib
        img = nib.load(str(NERVE_IN)); L = np.asarray(img.dataobj); A = img.affine
        ii, jj, kk = np.nonzero(L); R = (A @ np.c_[ii, jj, kk, np.ones(len(ii))].T).T[:, :3]
        atl = np.c_[R[:, 0] - ORIGIN[0], R[:, 2] - ORIGIN[1], R[:, 1] - ORIGIN[2]]
        for side, sg in (("right", 1), ("left", -1)):
            p = Photo(a.crops, side); P = atl[sg * atl[:, 0] > 0]; ys = np.rint(P[:, 1]).astype(int); dist = []
            for y in np.unique(ys):
                k = p.cls(y); e = ndi.distance_transform_edt(k == 3) * PX; s = ys == y
                pr, pc = p.c.atlas_to_px(y, P[s, 0], P[s, 2]); dist.append(e[np.rint(pr).astype(int), np.rint(pc).astype(int)])
            d = np.concatenate(dist)
            rows[side] = {"voxels": int(len(d)), "on_photographed_muscle_frac": round(float((d > 0).mean()), 3),
                          "beyond_1mm_into_muscle_frac": round(float((d > 1).mean()), 4), "max_into_muscle_mm": round(float(d.max()), 2)}
        rep["verify"]["q57_nerve_label_vs_photographed_muscle"] = rows
    REPORT.write_text(json.dumps(rep, indent=1)); print("wrote", REPORT)


def badge_nerve(a):
    """Stamp the nerve's badge onto build/vh/ct_vhm_sciatic (after convert) from the report's own measured numbers."""
    rep = json.loads(REPORT.read_text()); info = rep["registration"]["nerve_volume"]; per = rep.get("verify", {}).get("per_structure", {})
    if per:
        tot = sum(per[k]["registered_nerve_vs_new_mesh"]["of"] for k in ("adductor_magnus_r", "adductor_magnus_l"))
        b1 = sum(v["registered_nerve_vs_new_mesh"]["beyond_1mm"] for v in per.values())
        mx = max(v["registered_nerve_vs_new_mesh"]["max_depth_mm"] for v in per.values())
        am = sum(per[k]["registered_nerve_vs_new_mesh"]["beyond_1mm"] for k in ("adductor_magnus_r", "adductor_magnus_l"))
        res = (f"{100 * b1 / tot:.1f}% of its surface vertices lie more than 1 mm inside the adductor magnus / biceps femoris / "
               f"semitendinosus (adductor magnus alone {100 * am / tot:.1f}%), max {mx:.1f} mm")
    else:
        res = "not yet measured"
    badge = BADGE_NERVE.format(ap=-info["ap_shift_mm_atlas_z"], ml=-info["left_x_shift_mm_applied"], res=res)
    d = REPO / "build/vh/ct_vhm_sciatic"; m = json.loads((d / "manifest.json").read_text())
    for st in m["structures"]:
        if st["atlas_id"] == "sciatic_n":
            st["procedural_badge"] = badge
    (d / "manifest.json").write_text(json.dumps(m, indent=1)); rep["nerve_badge"] = badge; REPORT.write_text(json.dumps(rep, indent=1))
    print(badge)


# ----------------------------------------------------------------------------------------------- Q175 adductor longus
def load_store_q175():
    z = np.load(STORE_Q175); reg = {s: tuple(r) for s, r in json.loads(str(z["reg"])).items()}
    return reg, {k.replace("__", "#"): z[k] for k in z.files if k not in ("reg", "params")}


def cat_pieces(pcs):
    v = np.concatenate([p[1] for p in pcs]); o = np.cumsum([0] + [len(p[1]) for p in pcs])
    return v, np.concatenate([p[2] + o[j] for j, p in enumerate(pcs)])


def measure_al(a):
    m, V, F = load_subject(SRC); reg = load_store()[0]; D_store = {}; stats = {}
    params = {"facing": f"n . (0.5 lateral, 0, 0.866 anterior) > {NZ_Q175}", "y_range": list(Y_RANGE_Q175), "min_red": MIN_RED_Q175,
              "max_move_mm": 8.0, "muscle_run_mm": 5 * PX, "fat_run_mm": 2 * PX, "cross_window_mm": 2.5, "thickness_cap": 0.45,
              "smoothing": "1-ring median + 3 Laplacian passes (others fixed at 0) + fold guard", "subdivision": "midpoint x1"}
    for aid, side in SPEC_Q175:
        ph = Photo(a.crops, side, reg[side], MIN_RED_Q175); allD = []; ns = 0
        for i, (s, v, f) in enumerate(pieces_of(m, V, F, aid)):
            v2, f2 = trimesh.remesh.subdivide(v, f); D, info = snap(v2, f2, ph, facing_q175(side), nz_min=NZ_Q175, y_range=Y_RANGE_Q175)
            D_store[f"{aid}#{i}"] = np.round(D, 3); allD.append(D); stats.setdefault(aid, {})[f"piece{i}_snap"] = info; ns += info["surface_vertices"]
        stats[aid]["move"] = surface_move_stats(np.concatenate(allD), ns); print(aid, stats[aid]["move"], flush=True)
    after, before = build_pieces(D_store, SPEC_Q175)
    fm, fV, fF = load_subject(REPO / "build/vh/ct_vhm_femoral"); fv = by_id(fm, fV, fF)
    ok = True
    for aid, side in SPEC_Q175:
        sfx = "_r" if side == "right" else "_l"; vb, fb = cat_pieces(before[aid]); va, fa = cat_pieces(after[aid])
        v0 = vol_cm3(vb, fb); v1 = vol_cm3(va, fa); dv = 100 * (v1 - v0) / v0; ok &= abs(dv) <= 5.0
        stats[aid]["volume_cm3"] = [round(v0, 1), round(v1, 1)]; stats[aid]["volume_change_pct"] = round(dv, 2)
        lo = max(int(Y_RANGE_Q175[0]), int(np.ceil(vb[:, 1].min()))); hi = min(int(Y_RANGE_Q175[1]), int(np.floor(vb[:, 1].max())))
        stats[aid]["photo"] = photo_overlap(a.crops, reg[side], [(vb, fb)], [(va, fa)], side, list(range(hi, lo - 1, -2)), MIN_RED_Q175)
        P = fv["femoral_v" + sfx][0]
        stats[aid]["femoral_vein_full_res"] = {"vs_old_mesh": nerve_stats(P, vb, fb), "vs_new_mesh": nerve_stats(P, va, fa)}
        print(aid, stats[aid]["volume_cm3"], stats[aid]["photo"], stats[aid]["femoral_vein_full_res"], flush=True)
    rep = json.loads(REPORT_Q175.read_text()) if REPORT_Q175.exists() else {}
    rep.update({"source": SOURCE_Q175, "task": "Q175", "subject": OUT_SUBJ, "method": __doc__.split("3. Q175")[1].strip(),
                "supplier": {"subject": "vhm_both", "what": "DU lower-extremity release (Andreassen 2023): manual segmentation of his "
                             "cryosections; decimated copy recovered from his published viewer v25 (adductor longus ~3.5k triangles)"},
                "registration": {"used_px": {s: list(r) for s, r in reg.items()}, "from": str(STORE.relative_to(REPO))},
                "params": params, "structures": stats, "status": "ok" if ok else "STOPPED: volume change > 5 %"})
    if a.regcheck:
        rep["registration"]["recheck_on_these_crops"] = json.loads(Path(a.regcheck).read_text())
    if not ok:
        REPORT_Q175.write_text(json.dumps(rep, indent=1)); print("STOP: volume change > 5 %; nothing stored"); return
    np.savez_compressed(STORE_Q175, reg=json.dumps({s: list(r) for s, r in reg.items()}), params=json.dumps(params),
                        **{k.replace("#", "__"): v for k, v in D_store.items()})
    rep["badges"] = {aid: BADGE_AL.format(med=st["move"]["median_mm"], mx=st["move"]["max_mm"],
                                          pct=100 * st["move"]["moved_vertices"] / max(st["move"]["surface_vertices"], 1),
                                          v0=st["volume_cm3"][0], v1=st["volume_cm3"][1], dv=st["volume_change_pct"])
                     for aid, st in ((aid, stats[aid]) for aid, _ in SPEC_Q175)}
    rep["stored_moves"] = str(STORE_Q175.relative_to(REPO))
    REPORT_Q175.write_text(json.dumps(rep, indent=1)); print("wrote", REPORT_Q175)
    apply(argparse.Namespace(force_nerve=False))


def new_overlap(nb):
    """neighbours whose overlap with the changed mesh got worse beyond the bundle's re-decimation noise (<= 0.25 mm here):
    more of their vertices > 1 mm inside it, or a deeper max (either way) by > 0.5 mm."""
    return [k for k, r in nb.items() if r["its_vertices_inside_al_beyond_1mm_old_new"][1] > r["its_vertices_inside_al_beyond_1mm_old_new"][0]
            or r["its_vertices_inside_al_max_depth_old_new_mm"][1] > r["its_vertices_inside_al_max_depth_old_new_mm"][0] + 0.5
            or r["al_surface_inside_max_depth_old_new_mm"][1] > r["al_surface_inside_max_depth_old_new_mm"][0] + 0.5]


def verify_al(a):
    """After the rebuild: the femoral veins vs adductor longus old/new (full-res subject meshes and the shipped bundle), and
    the changed mesh vs its neighbours (surface samples inside them; their vertices inside it), old bundle vs new."""
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    rep = json.loads(REPORT_Q175.read_text()); after, before = build_pieces(load_store_q175()[1], SPEC_Q175)
    B = meshes_by_id(*read_bundle_dir(a.bundle))
    ob = json.loads(Path(a.old_bundle + ".json").read_text()); O = meshes_by_id(ob, Path(a.old_bundle + ".bin").read_bytes())
    out = {}
    for aid, side in SPEC_Q175:
        sfx = "_r" if side == "right" else "_l"; vid = "femoral_v" + sfx
        o = {"femoral_vein_bundle_vs_old_bundle_mesh": nerve_stats(O[vid]["v"], O[aid]["v"], O[aid]["f"]),
             "femoral_vein_bundle_vs_new_bundle_mesh": nerve_stats(B[vid]["v"], B[aid]["v"], B[aid]["f"])}
        tm0 = trimesh.Trimesh(O[aid]["v"], O[aid]["f"], process=False); tm1 = trimesh.Trimesh(B[aid]["v"], B[aid]["f"], process=False)
        p0 = trimesh.sample.sample_surface(tm0, 20000, seed=0)[0]; p1 = trimesh.sample.sample_surface(tm1, 20000, seed=0)[0]
        nb = {}
        for other in NEIGH_Q175:
            oid = other + sfx if other + sfx in B else other
            if oid not in B or oid not in O:
                continue
            c0, d0 = inside_depth(p0, O[oid]["v"], O[oid]["f"]); c1, d1 = inside_depth(p1, B[oid]["v"], B[oid]["f"])
            k0, e0 = inside_depth(O[oid]["v"], O[aid]["v"], O[aid]["f"]); k1, e1 = inside_depth(B[oid]["v"], B[aid]["v"], B[aid]["f"])
            nb[oid] = {"al_surface_inside_frac_old_new": [round(float(c0.mean()), 4), round(float(c1.mean()), 4)],
                       "al_surface_inside_max_depth_old_new_mm": [round(float(d0.max()), 2), round(float(d1.max()), 2)],
                       "its_vertices_inside_al_old_new": [int(k0.sum()), int(k1.sum())],
                       "its_vertices_inside_al_beyond_1mm_old_new": [int((e0 > 1).sum()), int((e1 > 1).sum())],
                       "its_vertices_inside_al_max_depth_old_new_mm": [round(float(e0.max()), 2), round(float(e1.max()), 2)]}
        o["neighbours_old_vs_new_bundle"] = nb
        o["new_overlap"] = new_overlap(nb)
        out[aid] = o; print(aid, json.dumps(o)[:600], flush=True)
    if a.crops:                                   # is the residual the vein's own outline? (its vertices on photographed muscle)
        reg = load_store()[0]; fm, fV, fF = load_subject(REPO / "build/vh/ct_vhm_femoral"); fv = by_id(fm, fV, fF)
        for aid, side in SPEC_Q175:
            sfx = "_r" if side == "right" else "_l"; P = fv["femoral_v" + sfx][0]; va, fa = cat_pieces(after[aid])
            c, d = inside_depth(P, va, fa); ph = Photo(a.crops, side, reg[side], MIN_RED_Q175)
            e = np.zeros(len(P)); ys = np.rint(P[:, 1]).astype(int)
            for y in np.unique(ys):
                k = ph.cls(y)
                if k is None:
                    continue
                s_ = ys == y; E = ndi.distance_transform_edt(k == 3) * PX; pr, pc = ph.to_px(y, P[s_, 0], P[s_, 2])
                pr = np.clip(np.rint(pr).astype(int), 0, k.shape[0] - 1); pc = np.clip(np.rint(pc).astype(int), 0, k.shape[1] - 1)
                e[s_] = E[pr, pc]
            r = d > 1
            out[aid]["femoral_vein_outline_vs_photographs"] = {
                "vein_vertices": int(len(P)), "on_photographed_muscle_frac": round(float((e > 0).mean()), 4),
                "beyond_1mm_into_photographed_muscle_frac": round(float((e > 1).mean()), 4), "max_into_photographed_muscle_mm": round(float(e.max()), 2),
                "residual_beyond_1mm_inside_new_al": int(r.sum()), "of_those_on_photographed_muscle": int((r & (e > 0)).sum()),
                "of_those_median_depth_into_photographed_muscle_mm": round(float(np.median(e[r])), 2) if r.any() else 0.0}
            print(aid, out[aid]["femoral_vein_outline_vs_photographs"], flush=True)
    rep["verify"] = {"bundle": a.bundle, "per_structure": out,
                     "inside_test": "trimesh contains; depth = distance to the containing mesh's surface"}
    REPORT_Q175.write_text(json.dumps(rep, indent=1)); print("wrote", REPORT_Q175)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("measure"); p.add_argument("--crops", required=True)
    p = sub.add_parser("apply"); p.add_argument("--force-nerve", action="store_true")
    p = sub.add_parser("verify"); p.add_argument("--bundle", default="build/viewer_m_hr"); p.add_argument("--crops")
    p.add_argument("--old-bundle", help="prefix of the pre-Q173 bundle copy (<prefix>.json + <prefix>.bin)")
    sub.add_parser("badge-nerve")
    p = sub.add_parser("measure-al"); p.add_argument("--crops", required=True)
    p.add_argument("--regcheck", help="JSON of the registration re-check on the same crops (femur / adductor longus / all thigh fits)")
    p = sub.add_parser("verify-al"); p.add_argument("--bundle", default="build/viewer_m_hr"); p.add_argument("--old-bundle", required=True)
    p.add_argument("--crops", help="the measure-al crops: also measure the vein outline against the photographed muscle")
    a = ap.parse_args(); {"measure": measure, "apply": apply, "verify": verify, "badge-nerve": badge_nerve,
                          "measure-al": measure_al, "verify-al": verify_al}[a.cmd](a)


if __name__ == "__main__":
    main()
