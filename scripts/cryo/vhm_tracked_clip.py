"""Q176: his tracked outlines (Q57 sciatic nerve, Q174 femoral / popliteal veins + tibial nerve) clipped to the
photographed non-muscle of his own 0.33 mm cryosections, by a bounded erosion.

    # crops (atlas boxes around each structure; delete after use):
    python3 scripts/cryo/vhm_stream_leg_crops.py --index SCRATCH/vh_cryo/cryo_index.json --y-top -85 --y-bot -226 \
        --box right=80,145,-85,-25 --box left=-135,-60,-85,-30 --ap-row -1 --out SCRATCH/q176/sci
    python3 scripts/cryo/vhm_stream_leg_crops.py ... --y-top 40 --y-bot -285 --box right=30,100,-10,80 --box left=-110,-35,-25,75 --out SCRATCH/q176/fem
    python3 scripts/cryo/vhm_stream_leg_crops.py ... --y-top -375 --y-bot -460 --box right=105,165,-75,0 --box left=-145,-95,-95,-20 --out SCRATCH/q176/pop
    python3 scripts/cryo/vhm_femoral_popliteal_track.py register --crops SCRATCH/q176/fem --out SCRATCH/q176/femR   # (and pop -> popR)
    python3 scripts/cryo/vhm_tracked_clip.py clip --crops SCRATCH/q176 --montage SCRATCH/q176
    # after the subjects are reconverted from the *_clip volumes (vhm_rebuild_bundle.sh) and the bundle rebuilt:
    python3 scripts/cryo/vhm_tracked_clip.py verify --bundle build/viewer_m_hr --old-bundle SCRATCH/q176/old_bundle --old-subjects SCRATCH/q176/old_subjects
    python3 scripts/cryo/vhm_tracked_clip.py badge

RULE, per label, per side, per 1 mm level (the label volumes' own 0.5 x 0.5 mm grid):
  * photographed MUSCLE = Q175's rule: his colour rule made strict (value < 115, g < 0.62 r) AND red >= 55 (his veins'
    black clot, red 20-48, and his nerve's pale fascicles, value ~130, g/r ~0.7, are not muscle); the crop-pixel muscle
    mask is 3 x 3 (1 mm) majority-smoothed and each voxel reads 2 x 2 sub-samples (majority).
  * depth = Euclidean distance of the voxel to the section's own outside (boundary voxel = 0.5 mm).
  * removed = photographed-muscle voxels with depth <= 2 mm that are CONNECTED to the boundary through such voxels (a
    peel from the outside in: muscle seen deep inside the section is never touched), outside the CORE (depth > min(2 mm,
    half the section's largest depth), never removed).
  * rim specks the peel cuts off (<= 4 voxels = 1 mm2, all within 2 mm of the edge; nearly all 1-2 voxels) go with the
    peel (attempt 1 kept the whole level instead: 29-41 % of the femoral-vein levels unclipped for 1-voxel specks);
    a level whose clipped section would still split (4-connected pieces inside any original piece != 1) keeps its
    ORIGINAL section; counted as kept_split.
Photographs are read exactly as the outline was traced: the sciatic nerve on the raw Q57 crop mapping, clipped in its
ORIGINAL volume (vhm_nerves_cryo.nii.gz) and then moved by the identical Q173 registration step
(vhm_thigh_fat_plane_snap.write_nerve) -> vhm_nerves_cryo_reg_clip.nii.gz; the Q174 volumes through the Q173 per-side
registration folded into the crop mapping (vhm_femoral_popliteal_track.py register), as they were tracked.
The femoral ARTERIES are not clipped: their label is the gel lumen plus <= 1 mm of wall, and an arterial wall is smooth
muscle (it photographs as muscle); their muscle overlap was ~0 (Q174). Originals kept; new volumes *_clip.nii.gz.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.vhf_nerve_track import Crops  # noqa: E402
from scripts.cryo import vhm_thigh_fat_plane_snap as SNAP  # noqa: E402

T = REPO / "data/ct_sources/task_outputs"
REPORT = REPO / "data/derived/Q176_vhm_tracked_clip.json"
ORIGIN = np.array([-6.035, -895.476, 4.787])
VOX = 0.5
MIN_RED = 55.0
MAX_MM = 2.0
SPECK_VOX = 4                                   # 1 mm2: a detached rim speck removed with the peel (Q176 attempt 2)
Q174_REPORT = REPO / "data/derived/Q174_vhm_femoral_popliteal.json"
# volume -> (crop prefix stem, clipped labels {label: (atlas_id, side or None = by atlas x sign)}, output)
VOLS = {
    "sciatic": {"src": T / "vhm_nerves_cryo.nii.gz", "crops": "sci", "out": T / "vhm_nerves_cryo_clip.nii.gz",
                "reg_out": T / "vhm_nerves_cryo_reg_clip.nii.gz", "labels": {1: ("sciatic_n", None)}, "subject": "ct_vhm_sciatic"},
    "femoral": {"src": T / "vhm_femoral_cryo.nii.gz", "crops": "femR", "out": T / "vhm_femoral_cryo_clip.nii.gz",
                "labels": {3: ("femoral_v_l", "left"), 4: ("femoral_v_r", "right")}, "subject": "ct_vhm_femoral",
                "unclipped": {1: "femoral_a_l", 2: "femoral_a_r"}},
    "popliteal": {"src": T / "vhm_popliteal_cryo.nii.gz", "crops": "popR", "out": T / "vhm_popliteal_cryo_clip.nii.gz",
                  "labels": {1: ("popliteal_v_l", "left"), 2: ("popliteal_v_r", "right"), 3: ("tibial_n", "left")},
                  "subject": "ct_vhm_popliteal"},
}
PUBLISHED = {
    "sciatic_n": "Q57: Gray's Anatomy (Standring, 42nd ed.) ~2 cm wide at its origin, the thickest nerve in the body; the Q57 traced band "
                 "(fascicle core, not the whole sheath) median 10.4/12.2 mm wide x 7.4/7.9 mm thick, 51/64 mm2 (R/L)",
    "femoral_v": "Q174: common femoral vein ~10-13 mm, femoral vein ~8-11 mm in living adults (Gray's 42nd ed.; Moore 8th ed.); collapsed in a cadaver",
    "popliteal_v": "Q174: popliteal vein ~7-11 mm in living adults (Gray's 42nd ed.; Moore 8th ed.)",
    "tibial_n": "Q174: tibial nerve in the popliteal fossa ~20-40 mm2 (~5-7 mm) (Cartwright MS et al., Muscle Nerve 2008;37:566-71)",
}
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): his colour cryosections at full resolution "
          "(0.33 mm, NCI Imaging Data Commons) re-streamed by scripts/cryo/vhm_stream_leg_crops.py; his tracked outlines from Q57 "
          "(data/ct_sources/task_outputs/vhm_nerves_cryo.nii.gz, scripts/cryo/vhf_nerve_track.py + vhf_nerve_volume.py) and Q174 "
          "(vhm_femoral_cryo.nii.gz / vhm_popliteal_cryo.nii.gz, scripts/cryo/vhm_femoral_popliteal_track.py); photograph-to-atlas "
          "registration from Q173 (data/derived/Q173_vhm_adductor_magnus.json); muscle meshes for the overlap check from his hi-res "
          "viewer bundle (DU lower-extremity release, Andreassen TE et al., Sci Data 10:34 (2023), CC BY 4.0, with the Q173/Q175 snaps).")
MUSCLE_WORDS = ("adductor", "biceps_femoris", "semitendinosus", "semimembranosus", "gracilis", "sartorius", "vastus", "rectus_femoris",
                "gluteus", "tensor_fasciae", "pectineus", "iliopsoas", "psoas", "iliacus", "gastrocnemius", "soleus", "plantaris",
                "popliteus", "quadratus_femoris", "obturator", "piriformis", "gemellus")
BONES = tuple(b + x for b in ("femur", "tibia", "fibula", "patella", "hip_bone") for x in ("_r", "_l"))   # exact ids ("tibia" is in tibial_n)


# ------------------------------------------------------------------------------------------------ photographs
class MusclePhoto:
    def __init__(self, prefix, side):
        self.c = Crops(prefix, side); self.cache = {}

    def mask(self, y):
        y = int(y)
        if y not in self.c.j_of:
            return None
        if y not in self.cache:
            mus = SNAP.classes(self.c.image(y), MIN_RED) == 3
            self.cache = {y: ndi.uniform_filter(mus.astype(np.float32), 3) >= 0.5}
        return self.cache[y]

    def sample(self, y, ax, az):
        """fraction of 2 x 2 sub-samples (+-0.125 mm) on photographed muscle per atlas point; -1 = outside the crop."""
        k = self.mask(y)
        if k is None:
            return np.full(len(ax), -1.0)
        acc = np.zeros(len(ax)); bad = np.zeros(len(ax), bool)
        for dx in (-0.125, 0.125):
            for dz in (-0.125, 0.125):
                pr, pc = self.c.atlas_to_px(y, ax + dx, az + dz); pr = np.rint(pr).astype(int); pc = np.rint(pc).astype(int)
                ok = (pr >= 0) & (pc >= 0) & (pr < k.shape[0]) & (pc < k.shape[1]); bad |= ~ok
                acc[ok] += k[pr[ok], pc[ok]]
        out = acc / 4.0; out[bad] = -1.0
        return out


def vox_atlas(A, i, j, k):
    """voxel indices of a vhf_nerve_volume.py grid (+x +y RAS, 0.5 x 0.5 x 1 mm) -> atlas x, z and level y."""
    return (A[0, 3] + A[0, 0] * i - ORIGIN[0], A[1, 3] + A[1, 1] * j - ORIGIN[2], int(round(A[2, 3] + A[2, 2] * k - ORIGIN[1])))


def clip_section(M, frac):
    """M: bool section (one label, one side, one level); frac: photographed-muscle fraction per voxel (-1 unknown).
    -> (new section, n_removed, status) with status 'clipped' | 'unchanged' | 'kept_split'."""
    depth = ndi.distance_transform_edt(np.pad(M, 1))[1:-1, 1:-1] * VOX
    dmax = depth.max(); core = depth > min(MAX_MM, max(VOX, 0.5 * dmax))
    cand = M & (frac >= 0.5) & (depth <= MAX_MM) & ~core
    lab, n = ndi.label(cand, np.ones((3, 3)))
    touch = np.unique(lab[cand & (depth <= VOX + 1e-6)]); rem = np.isin(lab, touch[touch > 0])
    if not rem.any():
        return M, 0, "unchanged"
    new = M & ~rem
    lo, no = ndi.label(M)
    for c in range(1, no + 1):
        pl, pn = ndi.label(new & (lo == c))
        if pn > 1:          # rim specks (<= SPECK_VOX voxels, all within the peel zone) cut off by the peel go with it
            sz = np.bincount(pl.ravel())[1:]; keep = int(np.argmax(sz)) + 1
            for p in range(1, pn + 1):
                if p != keep and sz[p - 1] <= SPECK_VOX and (depth[pl == p] <= MAX_MM).all():
                    new[pl == p] = False; rem[pl == p] = True
            pn = ndi.label(new & (lo == c))[1]
        if pn != 1:
            return M, 0, "kept_split"
    return new, int(rem.sum()), "clipped"


def side_mask(A, shape, side):
    ax = A[0, 3] + A[0, 0] * np.arange(shape[0]) - ORIGIN[0]
    return (ax > 0) if side == "right" else (ax < 0)


def clip_volume(key, crops_dir, log=print):
    cfg = VOLS[key]; img = nib.load(str(cfg["src"])); L = np.asarray(img.dataobj).copy(); A = img.affine; out = L.copy()
    photos = {}; per = {}
    for lab, (aid, side) in cfg["labels"].items():
        for sd in ([side] if side else ["right", "left"]):
            xm = side_mask(A, L.shape, sd)
            if not ((L == lab) & xm[:, None, None]).any():
                continue
            if sd not in photos:
                photos[sd] = MusclePhoto(f"{crops_dir}/{cfg['crops']}", sd)
            ph = photos[sd]; rows = []
            for k in range(L.shape[2]):
                M = (L[:, :, k] == lab) & xm[:, None]
                if not M.any():
                    continue
                ii, jj = np.nonzero(M); ax, az, y = vox_atlas(A, ii, jj, k)
                fr = np.full(M.shape, -1.0); fr[ii, jj] = ph.sample(y, ax, az)
                if (fr[ii, jj] < 0).any():
                    log(f"  {aid} {sd} y {y}: {(fr[ii, jj] < 0).sum()} voxels outside the crop")
                new, nrem, st = clip_section(M, fr)
                sl = out[:, :, k]; sl[M & ~new] = 0
                a0 = M.sum() * VOX * VOX; a1 = new.sum() * VOX * VOX
                rows.append({"y": y, "status": st, "area0": a0, "area1": a1, "removed_vox": nrem,
                             "muscle_frac0": float((fr[ii, jj] >= 0.5).mean()), "muscle_frac1": float((fr[new] >= 0.5).mean()) if new.any() else 0.0,
                             "muscle_beyond1mm0": float(((fr >= 0.5) & M & (ndi.distance_transform_edt(np.pad(M, 1))[1:-1, 1:-1] * VOX > 1.0)).sum() / M.sum())})
            per[f"{aid}:{sd}"] = rows
            n = len(rows); st = [r["status"] for r in rows]
            log(f"{aid} {sd}: {n} levels, clipped {st.count('clipped')}, unchanged {st.count('unchanged')}, kept_split {st.count('kept_split')}; "
                f"area {np.mean([r['area0'] for r in rows]):.1f} -> {np.mean([r['area1'] for r in rows]):.1f} mm2; muscle frac "
                f"{np.average([r['muscle_frac0'] for r in rows], weights=[r['area0'] for r in rows]):.3f} -> "
                f"{np.average([r['muscle_frac1'] for r in rows], weights=[r['area1'] for r in rows]):.3f}")
    return L, out, A, per


def components(L, lab, side=None, A=None):
    m = L == lab
    if side:
        m &= side_mask(A, L.shape, side)[:, None, None]
    return int(ndi.label(m, np.ones((3, 3, 3)))[1]), int(ndi.label(m)[1])


def struct_stats(L0, L1, A, lab, aid, side, rows):
    sides = [side] if side else ["right", "left"]
    v0 = sum(((L0 == lab) & side_mask(A, L0.shape, s)[:, None, None]).sum() for s in sides) * VOX * VOX / 1000.0
    v1 = sum(((L1 == lab) & side_mask(A, L1.shape, s)[:, None, None]).sum() for s in sides) * VOX * VOX / 1000.0
    a0 = np.array([r["area0"] for r in rows]); a1 = np.array([r["area1"] for r in rows]); st = [r["status"] for r in rows]
    d0 = 2 * np.sqrt(a0 / np.pi); d1 = 2 * np.sqrt(a1 / np.pi)
    c0 = [components(L0, lab, s, A) for s in sides]; c1 = [components(L1, lab, s, A) for s in sides]
    return {"atlas_id": aid, "sides": sides, "levels": len(rows),
            "levels_clipped": st.count("clipped"), "levels_unchanged_no_muscle_edge": st.count("unchanged"),
            "levels_kept_original_would_split": st.count("kept_split"),
            "volume_cm3": [round(float(v0), 3), round(float(v1), 3)], "volume_change_pct": round(100 * (v1 - v0) / v0, 1),
            "section_mm2_mean": [round(float(a0.mean()), 1), round(float(a1.mean()), 1)],
            "diameter_area_equivalent_median_mm": [round(float(np.median(d0)), 2), round(float(np.median(d1)), 2)],
            "diameter_change_pct": round(100 * (np.median(d1) - np.median(d0)) / np.median(d0), 1),
            "removed_per_clipped_level_mm2_median": round(float(np.median((a0 - a1)[a1 < a0])), 2) if (a1 < a0).any() else 0.0,
            "on_photographed_muscle_frac": [round(float(np.average([r["muscle_frac0"] for r in rows], weights=a0)), 4),
                                            round(float(np.average([r["muscle_frac1"] for r in rows], weights=a1)), 4)],
            "on_photographed_muscle_deeper_than_1mm_frac_before": round(float(np.average([r["muscle_beyond1mm0"] for r in rows], weights=a0)), 4),
            "components_3d_26conn": [sum(c[0] for c in c0), sum(c[0] for c in c1)],
            "components_3d_6conn": [sum(c[1] for c in c0), sum(c[1] for c in c1)]}


# ------------------------------------------------------------------------------------------------ montage
def montage(key, crops_dir, L0, L1, A, per, out_png, n_per=4):
    cfg = VOLS[key]; tiles = []
    for lab, (aid, side) in cfg["labels"].items():
        for sd in ([side] if side else ["right", "left"]):
            rows = per.get(f"{aid}:{sd}")
            if not rows:
                continue
            cl = [r for r in rows if r["status"] == "clipped"]
            pick = sorted(cl, key=lambda r: -(r["area0"] - r["area1"]))[:2] + [cl[i] for i in np.linspace(0, len(cl) - 1, max(n_per - 2, 1)).astype(int)] if cl else rows[:1]
            seen = set(); ph = Crops(f"{crops_dir}/{cfg['crops']}", sd); xm = side_mask(A, L0.shape, sd)
            for r in pick:
                if r["y"] in seen:
                    continue
                seen.add(r["y"]); y = r["y"]; k = int(round(y + ORIGIN[1] - A[2, 3]))
                m0 = (L0[:, :, k] == lab) & xm[:, None]; m1 = (L1[:, :, k] == lab) & xm[:, None]
                ii, jj = np.nonzero(m0); ax, az, _ = vox_atlas(A, ii, jj, k); pr, pc = ph.atlas_to_px(y, ax, az)
                r0, c0 = int(pr.mean()), int(pc.mean()); h = 60; im = ph.image(y)
                win = im[max(r0 - h, 0):r0 + h, max(c0 - h, 0):c0 + h]; oy_, ox_ = max(r0 - h, 0), max(c0 - h, 0)
                # crop pixels -> voxel masks
                rr, cc = np.mgrid[0:win.shape[0], 0:win.shape[1]]; x_, z_ = ph.px_to_atlas(y, rr + oy_, cc + ox_)
                vi = np.rint((x_ + ORIGIN[0] - A[0, 3]) / A[0, 0]).astype(int); vj = np.rint((z_ + ORIGIN[2] - A[1, 3]) / A[1, 1]).astype(int)
                ok = (vi >= 0) & (vj >= 0) & (vi < m0.shape[0]) & (vj < m0.shape[1])
                p0 = np.zeros(win.shape[:2], bool); p1 = p0.copy(); p0[ok] = m0[vi[ok], vj[ok]]; p1[ok] = m1[vi[ok], vj[ok]]
                mus = SNAP.classes(win, MIN_RED) == 3
                raw = Image.fromarray(np.asarray(win)).resize((240, 240), Image.NEAREST)
                ov = np.asarray(win).copy()
                ov[p0 & ~ndi.binary_erosion(p0)] = (255, 255, 0); ov[p1 & ~ndi.binary_erosion(p1)] = (0, 255, 255)
                ov[p0 & ~p1] = (ov[p0 & ~p1] * 0.3 + np.array([255, 0, 255]) * 0.7).astype(np.uint8)
                mv = np.asarray(win).copy() // 3; mv[mus] = (200, 60, 60); mv[p1 & ~ndi.binary_erosion(p1)] = (0, 255, 255)
                mv[p0 & ~ndi.binary_erosion(p0)] = (255, 255, 0)
                t = Image.new("RGB", (720, 256), (0, 0, 0)); t.paste(raw, (0, 16))
                t.paste(Image.fromarray(ov).resize((240, 240), Image.NEAREST), (240, 16)); t.paste(Image.fromarray(mv).resize((240, 240), Image.NEAREST), (480, 16))
                ImageDraw.Draw(t).text((4, 2), f"{aid} {sd} y {y}: {r['area0']:.0f} -> {r['area1']:.0f} mm2 ({r['status']})  yellow=before cyan=after magenta=removed | right: photographed muscle (Q175 rule)", fill=(255, 255, 255))
                tiles.append(t)
    if tiles:
        W = Image.new("RGB", (720, 256 * len(tiles))); [W.paste(t, (0, 256 * i)) for i, t in enumerate(tiles)]; W.save(out_png)


# ------------------------------------------------------------------------------------------------ modes
def do_clip(a):
    rep = {"source": SOURCE, "task": "Q176 his tracked outlines clipped to photographed non-muscle (bounded erosion)",
           "method": __doc__.split("RULE, per label")[1].strip(), "rule": {"min_red": MIN_RED, "max_erosion_mm": MAX_MM,
           "strict_muscle": "value < 115, g < 0.62 r, r > g + 12 (vhm_thigh_fat_plane_snap.classes)", "voxel_mm": [VOX, VOX, 1.0]},
           "published": PUBLISHED, "volumes": {}, "structures": {}}
    for key, cfg in VOLS.items():
        print("==", key)
        L0, L1, A, per = clip_volume(key, a.crops)
        nib.save(nib.Nifti1Image(L1, A), str(cfg["out"]))
        vrep = {"in": str(cfg["src"].relative_to(REPO)), "out": str(cfg["out"].relative_to(REPO)), "per_level": per}
        if key == "sciatic":
            info = SNAP.write_nerve(tuple_reg(), src=cfg["out"], dst=cfg["reg_out"])
            vrep["registered_out"] = str(cfg["reg_out"].relative_to(REPO)); vrep["registration_step"] = info
        for lab, (aid, side) in cfg["labels"].items():
            rows = sum((per.get(f"{aid}:{s}", []) for s in ([side] if side else ["right", "left"])), [])
            rep["structures"][aid] = dict(struct_stats(L0, L1, A, lab, aid, side, rows), volume=key)
        for lab, aid in cfg.get("unclipped", {}).items():
            assert ((L0 == lab) == (L1 == lab)).all(); rep["structures"][aid] = {"atlas_id": aid, "volume": key, "clipped": False,
                                                                                 "why": "arterial wall is smooth muscle; Q174 muscle overlap ~0"}
        rep["volumes"][key] = vrep
        if a.montage:
            montage(key, a.crops, L0, L1, A, per, f"{a.montage}/montage_{key}.png")
    for aid, s in rep["structures"].items():
        if "volume_cm3" in s:
            print(aid, {k: s[k] for k in ("volume_cm3", "volume_change_pct", "section_mm2_mean", "diameter_area_equivalent_median_mm",
                                          "levels_clipped", "levels_unchanged_no_muscle_edge", "levels_kept_original_would_split",
                                          "on_photographed_muscle_frac", "components_3d_26conn", "components_3d_6conn")})
    REPORT.write_text(json.dumps(rep, indent=1))


def tuple_reg():
    r = json.loads(SNAP.REPORT.read_text())["registration"]["used_px"]; return {s: tuple(v) for s, v in r.items()}


def subject_meshes(d):
    d = Path(d); m = json.loads((d / "manifest.json").read_text())
    V = np.frombuffer((d / "vertices.f32").read_bytes(), np.float32).reshape(-1, 3).astype(np.float64)
    F = np.frombuffer((d / "faces.u32").read_bytes(), np.uint32).reshape(-1, 3).astype(np.int64)
    out = {}
    for st in m["structures"]:
        v = V[st["vertex_offset"]:st["vertex_offset"] + st["vertex_count"]]; f = F[st["face_offset"]:st["face_offset"] + st["triangle_count"]] - st["vertex_offset"]
        out[st["atlas_id"]] = (v, f)
    return out


def mesh_components(v, f):
    """vertex-connected pieces after welding coincident vertices (bundle meshes carry duplicated seam vertices, and the
    decimated ones non-manifold edges, so trimesh's face-adjacency split over-counts)."""
    import trimesh
    import scipy.sparse as sps
    from scipy.sparse.csgraph import connected_components
    tm = trimesh.Trimesh(np.round(v, 3), f, process=False); tm.merge_vertices(); f = tm.faces; n = len(tm.vertices)
    e = np.r_[f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]
    lab = connected_components(sps.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)), directed=False)[1]
    return int(len(np.unique(lab[f[:, 0]])))


def overlap(v, M, words, exact=False):
    """vertices of v inside each named mesh of the bundle: (beyond 1 mm total, max depth, per mesh)."""
    import trimesh
    lo, hi = v.min(0) - 5, v.max(0) + 5; per = {}; inside_any = np.zeros(len(v), bool); beyond = np.zeros(len(v), bool); mx = 0.0
    for aid, m in M.items():
        if not (aid in words if exact else any(w in aid for w in words)):
            continue
        if (m["v"].max(0) < lo).any() or (m["v"].min(0) > hi).any():
            continue
        tm = trimesh.Trimesh(m["v"], m["f"], process=False); c = tm.contains(v)
        if not c.any():
            continue
        d = np.zeros(len(v)); d[c] = trimesh.proximity.closest_point(tm, v[c])[1]
        per[aid] = {"inside": int(c.sum()), "beyond_1mm": int((d > 1).sum()), "max_depth_mm": round(float(d.max()), 2)}
        inside_any |= c; beyond |= d > 1; mx = max(mx, float(d.max()))
    return {"vertices": int(len(v)), "inside_any": int(inside_any.sum()), "beyond_1mm_any": int(beyond.sum()), "max_depth_mm": round(mx, 2), "per_mesh": per}


def geo_hashes(bdir):
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    bf, blob = read_bundle_dir(bdir); M = meshes_by_id(bf, blob)
    return {aid: hashlib.md5(np.ascontiguousarray(m["v"], np.float32).tobytes() + np.ascontiguousarray(m["f"], np.int64).tobytes()).hexdigest()
            for aid, m in M.items()}, M


def do_verify(a):
    rep = json.loads(REPORT.read_text())
    h1, M1 = geo_hashes(a.bundle); h0, M0 = geo_hashes(a.old_bundle)
    changed = sorted(k for k in h1 if h0.get(k) != h1[k]); rep["bundle"] = {
        "structures_before_after": [len(h0), len(h1)], "ids_added": sorted(set(h1) - set(h0)), "ids_removed": sorted(set(h0) - set(h1)),
        "geometry_changed": changed}
    muscles = [k for k in M1 if any(w in k for w in MUSCLE_WORDS)]
    rep["overlap"] = {"muscle_meshes_checked": len(muscles), "note": "bundle meshes (as shipped) of the tracked ids vs every thigh/leg muscle and bone mesh of the new bundle; beyond_1mm_any counts a vertex once"}
    for key, cfg in VOLS.items():
        subj_new = subject_meshes(REPO / "build/vh" / cfg["subject"]); subj_old = subject_meshes(Path(a.old_subjects) / cfg["subject"])
        for aid in list(dict.fromkeys([x[0] for x in cfg["labels"].values()])) + list(cfg.get("unclipped", {}).values()):
            s = rep["structures"][aid]
            ov0 = overlap(M0[aid]["v"], M1, MUSCLE_WORDS); ov1 = overlap(M1[aid]["v"], M1, MUSCLE_WORDS)
            fv0 = overlap(subj_old[aid][0], M1, MUSCLE_WORDS); fv1 = overlap(subj_new[aid][0], M1, MUSCLE_WORDS)
            b1 = overlap(M1[aid]["v"], M1, BONES, True); bf1 = overlap(subj_new[aid][0], M1, BONES, True)
            s["muscle_overlap_bundle"] = {"before": ov0, "after": ov1}
            s["muscle_overlap_fullres_subject"] = {"before": {k: fv0[k] for k in ("vertices", "inside_any", "beyond_1mm_any", "max_depth_mm")},
                                                   "after": {k: fv1[k] for k in ("vertices", "inside_any", "beyond_1mm_any", "max_depth_mm")}}
            s["bone_inside"] = {"bundle": b1["inside_any"], "fullres_subject": bf1["inside_any"]}
            s["mesh_components"] = {"subject_before": mesh_components(*subj_old[aid]), "subject_after": mesh_components(*subj_new[aid]),
                                    "bundle_before": mesh_components(M0[aid]["v"], M0[aid]["f"]), "bundle_after": mesh_components(M1[aid]["v"], M1[aid]["f"])}
            print(aid, "muscle>1mm bundle", ov0["beyond_1mm_any"], "->", ov1["beyond_1mm_any"], "of", ov1["vertices"], "max", ov0["max_depth_mm"], "->", ov1["max_depth_mm"],
                  "| full-res", fv0["beyond_1mm_any"], "->", fv1["beyond_1mm_any"], "of", fv1["vertices"], "| bone", b1["inside_any"], bf1["inside_any"],
                  "| comps", s["mesh_components"])
    print("changed ids:", changed, "structures", len(h0), "->", len(h1))
    REPORT.write_text(json.dumps(rep, indent=1))


BADGE_ADD = (" Q176: outline clipped to his photographed non-muscle (the traced edge had run up to ~2 mm into the neighbouring muscle): "
             "photographed-muscle voxels within 2 mm of the edge peeled off, core never touched, {lv} of {n} levels changed; volume {dv:+.0f}%, "
             "median section diameter {d0:.1f} -> {d1:.1f} mm, "
             "section on photographed muscle {m0:.0f}% -> {m1:.0f}%. Surface vertices more than 1 mm inside a muscle mesh: {b0} -> {b1} of {nv} "
             "(max {x1:.1f} mm).")


def aid_is_nerve(aid):
    return aid.endswith("_n")


def do_badge(a):
    rep = json.loads(REPORT.read_text())
    for key, cfg in VOLS.items():
        d = REPO / "build/vh" / cfg["subject"]; m = json.loads((d / "manifest.json").read_text())
        for st in m["structures"]:
            s = rep["structures"].get(st["atlas_id"])
            if not s or "volume_cm3" not in s or "muscle_overlap_bundle" not in s:
                continue
            b = st["procedural_badge"].split(" Q176:")[0]
            if st["atlas_id"] == "sciatic_n":      # Q173's residual sentences describe the unclipped outline
                b = b.split(" Residual overlap:")[0]
            ob = s["muscle_overlap_bundle"]
            st["procedural_badge"] = b + BADGE_ADD.format(lv=s["levels_clipped"], n=s["levels"], dv=s["volume_change_pct"],
                                                          d0=s["diameter_area_equivalent_median_mm"][0], d1=s["diameter_area_equivalent_median_mm"][1],
                                                          m0=100 * s["on_photographed_muscle_frac"][0], m1=100 * s["on_photographed_muscle_frac"][1],
                                                          b0=ob["before"]["beyond_1mm_any"], b1=ob["after"]["beyond_1mm_any"], nv=ob["after"]["vertices"],
                                                          x1=ob["after"]["max_depth_mm"])
            pm = ob["after"]["per_mesh"]
            if ob["after"]["beyond_1mm_any"] > 0.01 * ob["after"]["vertices"] and pm:
                top = max(pm, key=lambda k: pm[k]["beyond_1mm"]).replace("_", " ")[:-2]
                st["procedural_badge"] += (f" The rest is the muscle meshes' own surface reaching over the photographed "
                                           f"{'nerve' if aid_is_nerve(st['atlas_id']) else 'lumen'} (mostly {top}).")
            s["badge"] = st["procedural_badge"]
        (d / "manifest.json").write_text(json.dumps(m, indent=1))
    REPORT.write_text(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    c = sub.add_parser("clip"); c.add_argument("--crops", required=True, help="dir with sci_*, femR_*, popR_* crops"); c.add_argument("--montage")
    v = sub.add_parser("verify"); v.add_argument("--bundle", default="build/viewer_m_hr"); v.add_argument("--old-bundle", required=True)
    v.add_argument("--old-subjects", required=True, help="dir holding copies of the pre-Q176 ct_vhm_sciatic/femoral/popliteal subjects")
    sub.add_parser("badge")
    a = ap.parse_args()
    {"clip": do_clip, "verify": do_verify, "badge": do_badge}[a.mode](a)


if __name__ == "__main__":
    main()
