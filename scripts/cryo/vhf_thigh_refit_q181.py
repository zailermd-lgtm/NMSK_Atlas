"""Q181 (owner option (a2) on the Q179 audit): her Q48 thigh-muscle boundaries re-fitted on her photographs as placed by the
femur-registered reconstruction (Q179), with every surface that touches bone or her own CT muscles held where it is; then her
photo-tracked outlines (Q179 registered + clipped + interpolated candidates) and a bounded Q177 face snap where they still enter.

STATUS (2026-09-30): STOPPED after attempt 2, NOT wired (vhf_rebuild_bundle.sh, mappings and build/viewer_f_hr are pre-Q181; the
viewer rebuilt from the restored script is byte-identical). The candidate volume / store / snap moves stay in task_outputs; see
data/derived/Q181_vhf_thigh_refit.json "decision". Attempt 1 (Q48's own classifier): the sciatic stayed inside the adductor magnus /
biceps (her nerve is Q48 class 3). Attempt 2 (+ traced nerve / vessel sections kept out of the region): sciatic 50,970 -> 2,078
full-res vertices > 1 mm in muscle, popliteal 1,959/1,555 -> 8/0, but 14 muscles held by the 10 % volume rule (the anterior
compartment stays in the lost frame; pectineus_r at +10.3 % keeps the femoral vessels inside it: 830/1,821 -> 1,307/2,719),
tibial_n (kept as traced) 638 -> 1,647 bundle vertices inside biceps femoris_r, and 10 continuity regressions (rectus femoris_r
main_frac 1.00 -> 0.77).

Why: Q48 (scripts/transfer/refine_transfer_to_septa.py) put the male's lower-limb muscles on her CT bones and moved the boundaries
between neighbouring bellies onto the septa photographed in her 1 mm frame -- a frame that was lost and, re-registered to her CT
femur (Q179), turns out to sit 2-14 mm off (vhf_tracked_reg_q179.json). Translating whole muscles (Q179a) drove the bone-held
surfaces into bone; so here only the photograph-refined boundaries are redone.

    # crops (as Q179; delete after use):
    python3 scripts/cryo/vhm_stream_leg_crops.py --body vhf --index SCRATCH/vh_cryo_f_idx/cryo_index.json --y-top 40 --y-bot -420 \
        --box right=0,200,-140,80 --ap-row -1 --rs-cs=-2,-108 --margin 20 --z-offset="0:-20,-375:-14" --out SCRATCH/q181/crops/R
    python3 scripts/cryo/vhm_stream_leg_crops.py --body vhf ... --box left=-200,0,-140,80 --z-offset="0:-18.5,-375:-17" --out SCRATCH/q181/crops/L
    # then copy Q179's registered R_bbox.json / L_bbox.json + registration.json + photo_stats.json over (same windows, checked)
    python3 scripts/cryo/vhf_thigh_refit_q181.py photos  --crops SCRATCH/q181/crops --work SCRATCH/q181   # 1 mm registered stack
    python3 scripts/cryo/vhf_thigh_refit_q181.py refit   --work SCRATCH/q181 [--hold id ...]           # -> task_outputs volume
    python3 scripts/cryo/vhf_thigh_refit_q181.py measure --crops SCRATCH/q181/crops                     # gates, snap -> store/npz
    python3 scripts/cryo/vhf_thigh_refit_q181.py apply [--if-stale]     # rebuild: -> build/vh/xfer_vhm2vhf_sep_q181 (byte-reproducible)
    python3 scripts/cryo/vhf_thigh_refit_q181.py badge-tracked          # rebuild: badges on ct_vhf_{nerve,femoral,popliteal}_q181
    python3 scripts/cryo/vhf_thigh_refit_q181.py verify --old-bundle OLD.json [--crops ...]   # after the rebuild

REFIT, per 1 mm level of the Q48 label volume (vhf_xfer_lowerlimb_septa.nii.gz, her torso-RAS grid) and side, on the levels the
Q179 offset was measured on (y +14..-386, faded over 20 mm beyond: Q179a's field):
  base  = the Q48 labels; its own broken levels (y -129..-134: her blank / gel-spill photographs in the lost frame -- a side's
          muscle area < 90 % of its neighbours') replaced by a multi-label signed-distance blend of the bounding levels;
  Ls    = base translated by the Q179a field (the lost frame's offset: where her photographed septa really are);
  photo = her photograph sampled through the femur registration onto the same 1 mm grid (3 x 3 full-res mean), her muscle rule
          (Q179: red > blue + 8, value < 100, red >= 50, not a photographed lumen; 3 x 3 majority);
  Q48's step, unchanged: markers = each muscle of Ls eroded 3 mm, region = her muscle (closed 2, holes filled) within 4 mm of Ls's
          union minus her own CT muscles (dilated 2 mm), marker watershed on the white top-hat (disk 4) of the brightness, each
          muscle at most 8 mm (x the field weight) from its Ls mask, Ls pixels left unassigned kept if within 3 mm of muscle;
  added: bone voxels are never region (Q48 filled holes, so the femur was); every voxel within 3 mm of bone (femur, patella,
          tibia, fibula, hip bone, sacrum) or of her CT muscles / tendons (glutei, iliopsoas, quadriceps and adductor magnus tendons,
          pelvic floor) keeps its base label, so those surfaces stay where they are; photograph-less voxels keep the base label;
  unusable photographs (Q179: y -127..-131 R, -127..-132 L) take the multi-label blend of the nearest re-fitted levels.
A muscle whose volume changes > 10 % is held and the refit re-run (--auto-hold): it keeps exactly its base voxels, its re-fitted
territory beyond them stays empty (so no neighbour grows into it) and the voxels it keeps are taken from whichever neighbour had them.
Meshes: label_surface as convert (smooth 1.0; 0.0 for the Q115 ids), Q152's approved gap bridges / island drops re-applied to the
ids Q152 fixed; only ids that change are written (subject listed before every Q48 subject in vhf_rebuild_bundle.sh).
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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
import nibabel as nib  # noqa: E402
from scripts.cryo import vhf_tracked_q179 as Q  # noqa: E402
from scripts.cryo import vhf_frame_fix_q179a as FF  # noqa: E402
from scripts.cryo import vhm_thigh_fat_plane_snap as SNAP  # noqa: E402
from scripts.cryo.cryo_classes_f import classify as classify_f  # noqa: E402

T = REPO / "data/ct_sources/task_outputs"
VH = REPO / "build/vh"
Q48_VOL = T / "vhf_xfer_lowerlimb_septa.nii.gz"
OUT_VOL = T / "vhf_xfer_lowerlimb_septa_q181.nii.gz"
STORE = T / "vhf_thigh_refit_q181.json"
SNAP_NPZ = T / "vhf_thigh_refit_q181_snap.npz"
REPORT = REPO / "data/derived/Q181_vhf_thigh_refit.json"
LABELS = REPO / "mappings/vhf_xfer_septa_labels.json"
Q152_JSON = REPO / "data/derived/Q152_continuity_repair.json"
OUT_SUBJ = "xfer_vhm2vhf_sep_q181"
ORIGIN = Q.ORIGIN
SIDE_I = {"right": (0, 350), "left": (335, 700)}          # grid columns (i) photographed per side (atlas x = 342.231 - i)
ERODE_PX, DILATE_PX, MAX_MOVE_PX = 3, 4, 8                 # Q48's constants
HOLD_PX = 3                                                # bone / CT-muscle contact band held (mm)
MAX_DVOL_PCT = 10.0
BONE_WORDS = ("femur", "patella", "tibia", "fibula", "hip_bone", "sacrum")
SMOOTH0 = {"extensor_hallucis_longus_l", "flexor_digitorum_longus_l", "plantaris_l"}   # Q115/Q116 (ct_vhf_xfersepta_fix)
SNAP_TRACKED = ("sciatic_n", "femoral_a_r", "femoral_v_r", "femoral_n", "popliteal_a_r", "popliteal_v_r")
SNAP_MAX_DVOL_PCT = 5.0
TRACK_NEW = {"sciatic_n": ("ct_vhf_nerve_q181", "vhf_nerves_cryo_q179.nii.gz"),
             "femoral_a_r": ("ct_vhf_femoral_q181", "vhf_femoral_bundle_cryo_q179.nii.gz"),
             "femoral_v_r": ("ct_vhf_femoral_q181", "vhf_femoral_bundle_cryo_q179.nii.gz"),
             "femoral_n": ("ct_vhf_femoral_q181", "vhf_femoral_bundle_cryo_q179.nii.gz"),
             "popliteal_a_r": ("ct_vhf_popliteal_q181", "vhf_popliteal_cryo_q179.nii.gz"),
             "popliteal_v_r": ("ct_vhf_popliteal_q181", "vhf_popliteal_cryo_q179.nii.gz")}
TRACK_OLD = {"sciatic_n": "ct_vhf_nerve", "femoral_a_r": "ct_vhf_femoral", "femoral_v_r": "ct_vhf_femoral", "femoral_n": "ct_vhf_femoral",
             "popliteal_a_r": "ct_vhf_popliteal", "popliteal_v_r": "ct_vhf_popliteal", "tibial_n": "ct_vhf_popliteal"}
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): her colour cryosections at full resolution "
          "(0.33 mm, NCI Imaging Data Commons) re-streamed by scripts/cryo/vhm_stream_leg_crops.py --body vhf and registered to her CT "
          "femur (Q179); her CT bones and CT muscles (VH female CT, TotalSegmentator labels); her thigh muscles = the male's (DU "
          "lower-extremity release, Andreassen TE et al., Sci Data 10:34 (2023), CC BY 4.0) transferred onto her and refined to her "
          "septa (Q48); her tracked outlines Q53/Q55/Q56 (Q179 candidates). Derived data (scripts/cryo/vhf_thigh_refit_q181.py).")


def md5b(b):
    return hashlib.md5(b).hexdigest()


def md5(p):
    return md5b(Path(p).read_bytes())


def side_of(aid):
    return "right" if aid.endswith("_r") else "left"


def label_ids():
    lab = json.loads(LABELS.read_text())["labels"]; return {aid: int(l) for l, aid in lab.items()}


def y_of_k(A, k):
    return float(A[2, 3] + A[2, 2] * k - ORIGIN[1])


def grid_xz(A, i, j):
    return A[0, 3] + A[0, 0] * np.asarray(i, float) - ORIGIN[0], A[1, 3] + A[1, 1] * np.asarray(j, float) - ORIGIN[2]


# ------------------------------------------------------------------------------------------------ geometry helpers
def shift2d(S, di, dj):
    out = np.zeros_like(S); H, W = S.shape
    si = slice(max(0, -di), min(H, H - di)); sj = slice(max(0, -dj), min(W, W - dj))
    ti = slice(max(0, di), min(H, H + di)); tj = slice(max(0, dj), min(W, W + dj))
    out[ti, tj] = S[si, sj]; return out


def sdf(m):
    if not m.any():
        return np.full(m.shape, 1e3, np.float32)
    return (ndi.distance_transform_edt(~m) - ndi.distance_transform_edt(m)).astype(np.float32)


def blend_labels(Sa, Sb, t):
    """multi-label signed-distance blend of two label slices at t in [0, 1] (0 = Sa); a voxel takes the label it is deepest in."""
    labs = sorted(set(np.unique(Sa)) | set(np.unique(Sb)) - {0}); out = np.zeros_like(Sa)
    if not labs:
        return out
    D = np.stack([(1 - t) * sdf(Sa == l) + t * sdf(Sb == l) for l in labs]); a = D.argmin(0); m = D.min(0) < 0
    out[m] = np.asarray(labs, Sa.dtype)[a[m]]; return out


def raster(meshes, A, y, shape):
    """bool mask of the union of the meshes' sections at atlas level y on the (i, j) grid (even-odd over each mesh's loops)."""
    out = np.zeros(shape, bool)
    for tm in meshes:
        if tm.bounds[0, 1] > y or tm.bounds[1, 1] < y:
            continue
        s = tm.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
        if s is None:
            continue
        acc = np.zeros(shape[::-1], bool)
        for e in s.entities:
            p = s.vertices[e.points]
            if len(p) < 3:
                continue
            ii = (p[:, 0] + ORIGIN[0] - A[0, 3]) / A[0, 0]; jj = (p[:, 2] + ORIGIN[2] - A[1, 3]) / A[1, 1]
            img = Image.new("1", (shape[0], shape[1]), 0); ImageDraw.Draw(img).polygon(list(zip(ii.tolist(), jj.tolist())), fill=1)
            acc ^= np.asarray(img, bool)
        out |= acc.T
    return out


def held_meshes():
    """her bones and her own CT muscles / tendons from the shipped bundle (the surfaces held)."""
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    bf, blob = read_bundle_dir(str(REPO / "build/viewer_f_hr")); M = meshes_by_id(bf, blob); bones, ct = [], []
    for e in bf["structures"]:
        v = np.asarray(M[e["id"]]["v"], float)
        if v[:, 1].max() < -430 or v[:, 1].min() > 45:
            continue
        tm = trimesh.Trimesh(v, np.asarray(M[e["id"]]["f"]), process=False)
        if e["cat"] == "bone" and any(w in e["id"] for w in BONE_WORDS):
            bones.append((e["id"], tm))
        elif e["cat"] in ("muscle", "tendon") and e["subject"].startswith("ct_vhf") and not e["subject"].startswith("ct_vhf_xfersepta"):
            ct.append((e["id"], tm))
    return bones, ct


# ------------------------------------------------------------------------------------------------ photos (1 mm registered stack)
def do_photos(a):
    from skimage.morphology import white_tophat, disk
    img = nib.load(str(Q48_VOL)); A = img.affine; n = img.shape[2]; W = Path(a.work); W.mkdir(parents=True, exist_ok=True)
    for side, (i0, i1) in SIDE_I.items():
        c = Q.Crops(str(Path(a.crops) / Q.SIDES[side][0]), side); ph = Q.HerMusclePhoto(a.crops, side)
        ks = [k for k in range(n) if int(round(y_of_k(A, k))) in c.j_of]
        II, JJ = np.meshgrid(np.arange(i0, i1), np.arange(img.shape[1]), indexing="ij"); X, Z = grid_xz(A, II, JJ)
        rgb = np.lib.format.open_memmap(str(W / f"p1_{side}_rgb.npy"), mode="w+", dtype=np.uint8, shape=(len(ks),) + II.shape + (3,))
        mus = np.lib.format.open_memmap(str(W / f"p1_{side}_mus.npy"), mode="w+", dtype=np.uint8, shape=(len(ks),) + II.shape)
        th = np.lib.format.open_memmap(str(W / f"p1_{side}_th.npy"), mode="w+", dtype=np.float32, shape=(len(ks),) + II.shape)
        for t, k in enumerate(ks):
            y = int(round(y_of_k(A, k))); im = c.image(y); pr, pc = c.atlas_to_px(y, X, Z); pr = np.rint(pr).astype(int); pc = np.rint(pc).astype(int)
            ok = (pr >= 1) & (pc >= 1) & (pr < im.shape[0] - 1) & (pc < im.shape[1] - 1)
            f3 = ndi.uniform_filter(im.astype(np.float32), (3, 3, 0)); m3 = ndi.uniform_filter(ph.mask(y).astype(np.float32), 3)
            known = np.zeros(II.shape, bool); known[ok] = im[pr[ok], pc[ok]].astype(int).sum(-1) > 0
            R = np.zeros(II.shape + (3,), np.uint8); R[known] = np.rint(f3[pr[known], pc[known]]).astype(np.uint8)
            Mm = np.zeros(II.shape, np.uint8); Mm[known] = 1 + (m3[pr[known], pc[known]] >= 0.5)      # 0 unknown, 1 not muscle, 2 muscle
            rgb[t] = R; mus[t] = Mm; th[t] = white_tophat(R.max(-1).astype(np.float32), disk(4)); Q._PHOTO_CACHE.clear()
            if t % 50 == 0:
                print(side, t, len(ks), flush=True)
        for mm in (rgb, mus, th):
            mm.flush()
        (W / f"p1_{side}.json").write_text(json.dumps({"ks": ks, "i0": i0, "i1": i1, "bbox_md5": md5(Path(a.crops) / f"{Q.SIDES[side][0]}_bbox.json")}))
    print("photos done")


# ------------------------------------------------------------------------------------------------ traced structures as obstacles
TRACED_VOLS = (("vhf_nerves_cryo_q179.nii.gz", (1,)), ("vhf_femoral_bundle_cryo_q179.nii.gz", (1, 2, 3)), ("vhf_popliteal_cryo_q179.nii.gz", (1, 2)))


def traced_mask(A, shape):
    """her photo-traced nerves / vessels as shipped by Q181 (the Q179 registered + clipped + interpolated candidates; tibial_n, kept as
    traced in the lost frame, is not included) on the Q48 1 mm grid: a voxel is traced when any 0.5 mm traced voxel centre falls in it."""
    out = np.zeros(shape, bool)
    for fn, labs in TRACED_VOLS:
        img = nib.load(str(T / fn)); V = np.asarray(img.dataobj); ii, jj, kk = np.nonzero(np.isin(V, labs))
        ras = img.affine @ np.c_[ii, jj, kk, np.ones(len(ii))].T; inv = np.linalg.inv(A)
        g = np.rint((inv @ ras)[:3]).astype(int); ok = ((g >= 0) & (g < np.array(shape)[:, None])).all(0)
        out[g[0, ok], g[1, ok], g[2, ok]] = True
    return out


# ------------------------------------------------------------------------------------------------ refit
def field_at(field, y):
    fs = field; yy = np.asarray(fs["y"], float)
    if y > yy.max() or y < yy.min():
        return 0.0, 0.0, 0.0
    return float(np.interp(y, yy, fs["dx"])), float(np.interp(y, yy, fs["dz"])), float(np.interp(y, yy, fs["weight"]))


def broken_levels(L, A, side_labs, ks):
    """a side's Q48 levels whose muscle area is < 90 % of the median of the levels 3-10 mm away (her lost-frame blank photographs)."""
    area = {k: int(np.isin(L[:, :, k], side_labs).sum()) for k in range(max(0, min(ks) - 12), min(L.shape[2], max(ks) + 13))}; bad = []
    for k in ks:
        ref = [area[kk] for kk in range(k - 10, k + 11) if 3 <= abs(kk - k) and kk in area]
        if ref and area[k] < 0.9 * np.median(ref):
            bad.append(k)
    return bad


def runs(ks):
    out = []
    for k in sorted(ks):
        if out and out[-1][1] == k - 1:
            out[-1][1] = k
        else:
            out.append([k, k])
    return out


def refit_level(L0s, Ls, rgb_th, mus, B, C, move_px, held, Tk=None):
    """one level, one side: Q48's marker watershed on the registered photograph + the held bands (see the module doc)."""
    th, known = rgb_th; musc = mus == 2
    F = ndi.binary_dilation(B | C, iterations=HOLD_PX)
    hold_l = np.isin(L0s, list(held)) if held else np.zeros_like(F)
    Lm = Ls; union = Lm > 0
    region = (ndi.binary_fill_holes(ndi.binary_closing(musc, iterations=2)) & ndi.binary_dilation(union, iterations=DILATE_PX)
              & ~ndi.binary_dilation(C, iterations=2) & ~B & known)
    if Tk is not None:                  # attempt 2: her traced nerve / vessel sections are not muscle region (Q48's class 3 takes her nerve)
        region &= ~Tk
    res = np.zeros_like(L0s)
    if region.any() and move_px > 0:
        from skimage.segmentation import watershed
        markers = np.zeros_like(L0s)
        for l in np.unique(Lm[union]):
            m = Lm == l; e = ndi.binary_erosion(m, iterations=ERODE_PX) & region
            markers[e if e.any() else (m & region)] = l
        ws = watershed(th, markers, mask=region)
        for l in np.unique(ws[ws > 0]):
            res[(ws == l) & ndi.binary_dilation(Lm == l, iterations=move_px)] = l
        keep = (res == 0) & union & ndi.binary_dilation(musc, iterations=3)
        res[keep] = Lm[keep]
    else:
        res = L0s.copy()
    if held:          # a held muscle keeps exactly its base voxels; its re-fitted territory beyond them is left empty (no neighbour grows in)
        res[np.isin(res, list(held))] = 0; res[hold_l] = L0s[hold_l]
    res[~known] = L0s[~known]; res[F] = L0s[F]
    if Tk is not None:
        res[Tk & ~hold_l] = 0
    if held:
        res[np.isin(res, list(held)) & ~hold_l] = 0
    return res


def refit_once(a, hold_ids):
    img = nib.load(str(Q48_VOL)); A = img.affine; L = np.asarray(img.dataobj).copy(); ids = label_ids(); W = Path(a.work)
    field, full = FF.build_field(); skip = {s: set(v) for s, v in Q.unusable(a.crops).items()}
    held = {ids[h] for h in hold_ids}
    bones, ct = held_meshes(); out = L.copy(); base_all = L.copy(); lv = {}
    TR = traced_mask(A, L.shape) if a.traced else None
    for side, (i0, i1) in SIDE_I.items():
        meta = json.loads((W / f"p1_{side}.json").read_text()); tk = {k: t for t, k in enumerate(meta["ks"])}
        rgb = np.load(W / f"p1_{side}_rgb.npy", mmap_mode="r"); mus = np.load(W / f"p1_{side}_mus.npy", mmap_mode="r")
        th = np.load(W / f"p1_{side}_th.npy", mmap_mode="r")
        sl = [l for aid, l in ids.items() if side_of(aid) == side]
        ks = [k for k in tk if field_at(field[side], y_of_k(A, k))[2] > 0]
        base = L[i0:i1].copy()
        # the Q48 volume's own broken levels -> multi-label blend of the bounding intact levels (this side's labels only)
        bad = broken_levels(L, A, sl, ks)
        for r0, r1 in runs(bad):
            ka, kb = r0 - 1, r1 + 1; Sa = np.where(np.isin(base[:, :, ka], sl), base[:, :, ka], 0); Sb = np.where(np.isin(base[:, :, kb], sl), base[:, :, kb], 0)
            for k in range(r0, r1 + 1):
                Bl = blend_labels(Sa, Sb, (k - ka) / (kb - ka)); other = ~np.isin(base[:, :, k], sl) & (base[:, :, k] > 0)
                s_ = base[:, :, k]; s_[np.isin(s_, sl)] = 0; s_[(Bl > 0) & ~other] = Bl[(Bl > 0) & ~other]
        base_all[i0:i1] = np.where(np.isin(base, sl), base, base_all[i0:i1])
        res_of = {}; unus = []
        for k in sorted(ks):
            y = y_of_k(A, k); yi = int(round(y)); dx, dz, w = field_at(field[side], y)
            L0 = base[:, :, k]; L0s = np.where(np.isin(L0, sl), L0, 0)
            Bk = raster([tm for _, tm in bones], A, y, (700, L.shape[1]))[i0:i1]; Ck = raster([tm for _, tm in ct], A, y, (700, L.shape[1]))[i0:i1]
            if yi in skip[side]:
                unus.append(k); res_of[k] = None; lv[f"{side}:{k}"] = {"y": round(y, 3), "status": "unusable_photo"}; continue
            di, dj = int(round(dx / A[0, 0])), int(round(dz / A[1, 1]))
            Ls = shift2d(L0s, di, dj); t = tk[k]
            mk = np.asarray(mus[t])
            if a.rule == "q48":            # Q48's own tissue classes (cryo_classes_f: muscle = class 3) on the registered 1 mm photograph
                mk = np.where(mk > 0, 1 + (classify_f(np.asarray(rgb[t])) == 3), 0).astype(np.uint8)
            res = refit_level(L0s, Ls, (np.asarray(th[t]), np.asarray(mus[t]) > 0), mk, Bk, Ck, int(round(MAX_MOVE_PX * w)), held,
                              None if TR is None else TR[i0:i1, :, k])
            res_of[k] = (res, Bk, Ck)
            lv[f"{side}:{k}"] = {"y": round(y, 3), "shift_vox": [di, dj], "weight": round(w, 3), "changed_vox": int((res != L0s).sum())}
        for r0, r1 in runs(unus):
            ka, kb = r0 - 1, r1 + 1
            while ka in res_of and res_of[ka] is None:
                ka -= 1
            while kb in res_of and res_of[kb] is None:
                kb += 1
            for k in range(r0, r1 + 1):
                y = y_of_k(A, k); L0 = base[:, :, k]; L0s = np.where(np.isin(L0, sl), L0, 0)
                Bk = raster([tm for _, tm in bones], A, y, (700, L.shape[1]))[i0:i1]; Ck = raster([tm for _, tm in ct], A, y, (700, L.shape[1]))[i0:i1]
                res = blend_labels(res_of[ka][0], res_of[kb][0], (k - ka) / (kb - ka))
                F = ndi.binary_dilation(Bk | Ck, iterations=HOLD_PX); res[F] = L0s[F]
                h = np.isin(L0s, list(held)) if held else np.zeros(res.shape, bool)
                if held:
                    res[np.isin(res, list(held)) & ~h] = 0; res[h] = L0s[h]
                if TR is not None:
                    res[TR[i0:i1, :, k] & ~h] = 0
                res_of[k] = (res, Bk, Ck); lv[f"{side}:{k}"].update(status="interpolated", between=[ka, kb], changed_vox=int((res != L0s).sum()))
        for k, (res, _, _) in res_of.items():
            s_ = out[i0:i1, :, k]; other = (s_ > 0) & ~np.isin(s_, sl)
            s_[np.isin(s_, sl)] = 0; s_[(res > 0) & ~other] = res[(res > 0) & ~other]
        lv[f"{side}:broken_q48_levels"] = [round(y_of_k(A, k), 3) for k in bad]
        print(side, len(ks), "levels refitted,", len(unus), "interpolated, Q48 broken levels", [round(y_of_k(A, k)) for k in bad], flush=True)
    before = {aid: int((L == l).sum()) for aid, l in ids.items()}; after = {aid: int((out == l).sum()) for aid, l in ids.items()}
    changed = sorted(aid for aid, l in ids.items() if not np.array_equal(L == l, out == l))
    return out, lv, before, after, changed, img, full


def do_refit(a):
    """refit; any muscle whose volume changes > 10 % is held at its Q48 voxels and the refit re-run, until none does (max 8 rounds)."""
    hold = list(a.hold or []); rounds = []
    for rnd in range(8):
        out, lv, before, after, changed, img, full = refit_once(a, hold)
        pct = {aid: 100 * (after[aid] - before[aid]) / max(before[aid], 1) for aid in changed}
        over = sorted(aid for aid in changed if abs(pct[aid]) > MAX_DVOL_PCT and aid not in hold)
        rounds.append({"held_in": list(hold), "over_10pct": {aid: round(pct[aid], 2) for aid in over}})
        print("round", rnd, "held", len(hold), "-> over 10 %:", {aid: round(pct[aid], 1) for aid in over}, flush=True)
        if not over or not a.auto_hold:
            break
        hold += over
    A = img.affine
    if a.out:
        nib.save(nib.Nifti1Image(out, A, img.header), a.out)
    else:
        nib.save(nib.Nifti1Image(out, A, img.header), str(OUT_VOL))
        st = json.loads(STORE.read_text()) if STORE.exists() else {}
        st.update({"source": SOURCE, "_README": "Q181 store: the refit label volume (OUT_VOL) and its inputs' hashes; ship_ids / snap / badges "
                   "are written by measure and read by apply.", "q48_vol_md5": md5(Q48_VOL), "out_vol_md5": md5(OUT_VOL),
                   "reg_json_md5": md5(Q.REG_JSON), "field_full_weight_levels": full, "held": sorted(hold), "hold_rounds": rounds,
                   "muscle_rule": a.rule, "traced_excluded": bool(a.traced), "params": {"erode": ERODE_PX, "dilate": DILATE_PX, "max_move": MAX_MOVE_PX, "hold_band_mm": HOLD_PX,
                                                     "bone_words": BONE_WORDS, "max_dvol_pct": MAX_DVOL_PCT},
                   "voxels_before_after": {aid: [before[aid], after[aid]] for aid in before}, "changed_ids": changed, "levels": lv})
        STORE.write_text(json.dumps(st, indent=1))
    for aid in changed:
        print(f"  {aid:28s} {before[aid] / 1000:8.1f} -> {after[aid] / 1000:8.1f} cm3 ({100 * (after[aid] - before[aid]) / max(before[aid], 1):+.1f} %)"
              + ("  HELD" if aid in hold else ""))


# ------------------------------------------------------------------------------------------------ meshes
def q152_rules():
    d = json.loads(Q152_JSON.read_text()); ids = set(label_ids()); out = {}
    for key, r in d["results"].items():
        if key.startswith("female|") and r["id"] in ids and r["cause"] in ("GAP_BRIDGE", "PIPELINE_ARTIFACT", "DROP_ISLAND"):
            out[r["id"]] = {"cause": r["cause"], "bridges": [(int(b["gap_zmin"]), int(b["gap_zmax"])) for b in r.get("bridges", [])],
                            "max_gap_mm": max((b["gap_mm"] for b in r.get("bridges", [])), default=0)}
    return out


def label_mesh(V, A, lab, aid, origin, rules):
    """as convert (label_surface, smooth 1.0 / 0.0 for the Q115 ids) on a crop around the label, with Q152's fix for its ids."""
    from engine import volume_ingest as vol
    import repair_continuity_q152 as diag
    m = V == lab; idx = np.nonzero(m.any((1, 2)))[0], np.nonzero(m.any((0, 2)))[0], np.nonzero(m.any((0, 1)))[0]
    if not len(idx[0]):
        return None
    M = 8; lo = [max(0, int(x.min()) - M) for x in idx]; hi = [min(s, int(x.max()) + M + 1) for x, s in zip(idx, V.shape)]
    r = rules.get(aid); note = []
    sub = V[lo[0]:hi[0], lo[1]:hi[1], :].copy()          # z kept whole: Q152's gap ranges are z indices of the full volume
    sub[(sub != lab)] = np.where(sub[(sub != lab)] > 0, 255, 0)
    if r and r["cause"] == "GAP_BRIDGE":
        ap = [(z0, z1) for z0, z1 in r["bridges"]]
        before = int((sub == lab).sum()); sub, added = diag.bridge_label_in_volume(sub, lab, 2, 1.0, approved_ranges=ap)
        if added:
            note.append(f"slice gaps bridged ({r['max_gap_mm']:.0f} mm max, {100 * added / max(before, 1):.1f} % of volume, Q152 rule)")
    if r and aid != "extensor_digitorum_longus_r":
        sub, nd, dropped = diag.drop_volume_islands(sub, lab, 2, np.ones(3))
        if dropped:
            note.append(f"{len(dropped)} stray fragment(s) ({100 * nd / max(int((sub == lab).sum()) + nd, 1):.1f} % of volume) dropped (Q152 rule)")
    sub = sub[:, :, lo[2]:hi[2]]
    smooth = 0.0 if (aid in SMOOTH0 or (r and r["cause"] == "PIPELINE_ARTIFACT")) else 1.0
    v, f = vol.label_surface(sub, lab, step=1, smooth=smooth)
    v = v + np.array(lo, float)
    return vol.voxels_to_atlas(v, A) - origin, f.astype(np.int64), smooth, note


def new_meshes(ids_wanted, origin=None):
    """{aid: (v, f, smooth, note)} from OUT_VOL."""
    img = nib.load(str(OUT_VOL)); V = np.asarray(img.dataobj); A = img.affine; ids = label_ids(); rules = q152_rules()
    o = ORIGIN if origin is None else np.asarray(origin, float)
    return {aid: label_mesh(V, A, ids[aid], aid, o, rules) for aid in ids_wanted}


def snapped(v, f, D):
    return v - D[:, None] * SNAP.outward_normals(v, f) if D is not None else v


# ------------------------------------------------------------------------------------------------ measure
def bone_counts(v, bones):
    row = {}
    for bn, tm in bones.items():
        if (tm.bounds[1] < v.min(0) - 15).any() or (tm.bounds[0] > v.max(0) + 15).any():
            continue
        d = FF.depth_inside(tm, v)
        if (d > 0).any():
            row[bn] = {"beyond_1mm": int((d > 1).sum()), "max_depth_mm": round(float(d.max()), 2)}
    return row


def surf_move(v_new, v_old):
    from scipy.spatial import cKDTree
    d1 = cKDTree(v_old).query(v_new)[0]; d0 = cKDTree(v_new).query(v_old)[0]
    return {"max_mm": round(float(max(d1.max(), d0.max())), 2), "p95_mm": round(float(np.percentile(np.r_[d1, d0], 95)), 2),
            "moved_gt_1mm_frac": round(float((np.r_[d1, d0] > 1.0).mean()), 4)}


def tracked_new():
    """full-res tracked candidates: the q181 subjects when built, else convert-equivalent meshes of the Q179 volumes (smooth as shipped)."""
    from engine import volume_ingest as vol
    out = {}
    for aid, (sub, fn) in TRACK_NEW.items():
        if (VH / sub / "manifest.json").exists():
            out[aid] = Q.subject_meshes(VH / sub)[aid]; continue
        mp = json.loads((REPO / "mappings/subjects" / f"{TRACK_OLD[aid]}_volume_mapping.json").read_text())
        lab = [e["label"] for e in mp["entries"] if e.get("atlas_id") == aid][0]
        img = nib.load(str(T / fn)); V = np.asarray(img.dataobj); sm = 1.0 if "femoral" in fn else 0.0
        if aid == "sciatic_n":
            v, f = vol.label_surface(V, lab, step=1, smooth=sm)
        else:
            v, f = vol.label_surface(V, lab, step=1, smooth=sm)
        out[aid] = (vol.voxels_to_atlas(v, img.affine) - ORIGIN, f)
    return out


def do_measure(a):
    from scipy.spatial import cKDTree  # noqa: F401
    from scripts.cryo.vhm_tracked_clip import overlap
    st = json.loads(STORE.read_text()); assert st["out_vol_md5"] == md5(OUT_VOL), "OUT_VOL changed since refit"
    skip = Q.unusable(a.crops); W = FF.winners(); ids = label_ids(); rules = q152_rules()
    cand = sorted((set(st["changed_ids"]) - set(st["held"])) | set(a.extra or []))
    new = new_meshes(cand)
    old = {aid: FF.cat(W[aid][1]) for aid in cand}
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    bf, blob = read_bundle_dir(str(REPO / "build/viewer_f_hr")); B = meshes_by_id(bf, blob)
    bones = {k: trimesh.Trimesh(np.asarray(B[k]["v"], float), np.asarray(B[k]["f"]), process=False) for k in Q.BONES + ("sacrum",) if k in B}
    # re-mesh noise: the UNCHANGED Q48 label through this script's mesher vs the shipped mesh (same id) -> bone-count noise floor
    rows = {}; ship = []; hold = []
    for aid in cand:
        v1, f1, sm, note = new[aid]; v0, f0 = old[aid]
        vol0, vol1 = SNAP.vol_cm3(v0, f0), SNAP.vol_cm3(v1, f1); dv = 100 * (vol1 - vol0) / vol0
        vb = st["voxels_before_after"][aid]; dvox = 100 * (vb[1] - vb[0]) / max(vb[0], 1)
        b0 = bone_counts(v0, bones); b1 = bone_counts(v1, bones)
        t0 = sum(r["beyond_1mm"] for r in b0.values()); t1 = sum(r["beyond_1mm"] for r in b1.values())
        ys = range(min(40, int(v0[:, 1].max())), max(-420, int(v0[:, 1].min())) - 1, -10)
        sh0 = FF.photo_muscle_share(a.crops, v0, f0, side_of(aid), skip[side_of(aid)], ys)
        sh1 = FF.photo_muscle_share(a.crops, v1, f1, side_of(aid), skip[side_of(aid)], ys)
        mv = surf_move(v1, v0)
        bone_ok = t1 <= t0 + max(25, 0.05 * t0)
        status = "ship"
        if abs(dvox) > MAX_DVOL_PCT or abs(dv) > MAX_DVOL_PCT:
            status = "hold: volume change > 10 %"
        elif not bone_ok:
            status = "hold: more vertices > 1 mm inside bone"
        rows[aid] = {"subject_before": W[aid][0], "volume_cm3_mesh": [round(vol0, 2), round(vol1, 2)], "volume_change_pct_mesh": round(dv, 2),
                     "volume_change_pct_voxels": round(dvox, 2), "photo_share_her_rule": [sh0, sh1], "bone_beyond_1mm": [t0, t1],
                     "bone_per_bone": {"before": b0, "after": b1}, "surface_move": mv, "smooth": sm, "q152_note": note, "status": status}
        (ship if status == "ship" else hold).append(aid)
        print(aid, {k: rows[aid][k] for k in ("volume_change_pct_mesh", "bone_beyond_1mm", "surface_move", "status")},
              "share", (sh0 or {}).get("on_photographed_muscle"), "->", (sh1 or {}).get("on_photographed_muscle"), flush=True)
    res = {"muscles": rows, "ship": ship, "hold": hold}
    per_bone = {}
    for aid in cand:
        for side_, key in ((0, "before"), (1, "after")):
            for bn, r in rows[aid]["bone_per_bone"][key].items():
                per_bone.setdefault(bn, [0, 0])[side_] += r["beyond_1mm"]
    res["bone_totals_beyond_1mm"] = per_bone
    # tracked outlines: shipped (old subjects) vs Q179 candidates, against all thigh muscles (shipped / with the shipped refit ids)
    moved = {aid: (new[aid][0], new[aid][1]) for aid in ship}
    bj = str(REPO / "build/viewer_f_hr/bundle.json"); M0 = FF.all_muscles(bj); M1 = FF.all_muscles(bj, moved)
    trn = tracked_new(); tro = {}
    for sub in set(TRACK_OLD.values()):
        tro.update(Q.subject_meshes(Path(a.old_subjects) / sub if a.old_subjects else VH / sub))
    tr = {}
    for aid in SNAP_TRACKED:
        r0 = overlap(tro[aid][0], M0, Q.MUSCLE_WORDS); r1 = overlap(trn[aid][0], M1, Q.MUSCLE_WORDS)
        tr[aid] = {"before": r0, "after_refit": r1}
        print(aid, "full-res > 1 mm in muscle", r0["beyond_1mm_any"], "->", r1["beyond_1mm_any"], "of", r1["vertices"], "max", r0["max_depth_mm"], "->",
              r1["max_depth_mm"], {k: v["beyond_1mm"] for k, v in r1["per_mesh"].items() if v["beyond_1mm"]}, flush=True)
    res["tracked_in_muscle_fullres"] = tr
    # bounded Q177 face snap on the refit Q48 muscles a tracked candidate still enters > 1 mm
    snap = {}; D_store = {}
    if not a.no_snap:
        P_all = {aid: trn[aid][0] for aid in SNAP_TRACKED}
        q48_in_range = sorted(aid for aid in ids if aid in M1 and M1[aid]["v"][:, 1].max() > -420)
        for mid in q48_in_range:
            if mid in hold or mid in st["held"]:
                continue
            v, f = (new[mid][0], new[mid][1]) if mid in moved else FF.cat(W[mid][1])
            tm = trimesh.Trimesh(v, f, process=False); ent = []
            for tid, P in P_all.items():
                P = P[(P[:, 0] > 0) == (side_of(mid) == "right")]; lo, hi = v.min(0) - 2, v.max(0) + 2; P = P[((P > lo) & (P < hi)).all(1)]
                if len(P) and (FF.depth_inside(tm, P) > 1.0).any():
                    ent.append(tid)
            if not ent:
                continue
            if mid not in moved:
                new[mid] = new_meshes([mid])[mid]; v, f = new[mid][0], new[mid][1]; tm = trimesh.Trimesh(v, f, process=False)
            P = np.concatenate([P_all[t] for t in ent]); P = P[(P[:, 0] > 0) == (side_of(mid) == "right")]
            lo, hi = v.min(0) - 2, v.max(0) + 2; P = P[((P > lo) & (P < hi)).all(1)]; d = FF.depth_inside(tm, P); keep = d > 0.5
            cp, _, fi = trimesh.proximity.closest_point(tm, P[keep]); nn = tm.face_normals[fi] * (1 if tm.volume > 0 else -1)
            dirv = nn.mean(0); dirv[1] = 0; dirv /= np.linalg.norm(dirv); yl, yh = P[keep, 1].min() - 2, P[keep, 1].max() + 2
            Dp, info = SNAP.snap(v, f, FF.HerPhoto(a.crops, skip), tuple(dirv), nz_min=0.5, y_range=(yl, yh), prefix_known=True)
            v2 = snapped(v, f, Dp); v0_, v1_ = SNAP.vol_cm3(v, f), SNAP.vol_cm3(v2, f); d2 = FF.depth_inside(trimesh.Trimesh(v2, f, process=False), P)
            row = {"entered_by": ent, "dir_xz": [round(float(dirv[0]), 3), round(float(dirv[2]), 3)], "y_range": [round(float(yl), 1), round(float(yh), 1)],
                   "tracked_beyond_1mm_before": int((d > 1).sum()), "max_before": round(float(d.max()), 2), "tracked_beyond_1mm_after": int((d2 > 1).sum()),
                   "max_after": round(float(d2.max()), 2), "volume_cm3": [round(v0_, 2), round(v1_, 2)], "dvol_pct": round(100 * (v1_ - v0_) / v0_, 2),
                   "move": SNAP.surface_move_stats(Dp, info["surface_vertices"]), "info": info}
            if abs(row["dvol_pct"]) > SNAP_MAX_DVOL_PCT:
                row["status"] = f"STOP: volume change > {SNAP_MAX_DVOL_PCT:.0f} % -- not stored"
            elif row["move"]["moved_vertices"] == 0:
                row["status"] = "nothing moved"
            else:
                row["status"] = "stored"; D_store[mid] = Dp.astype(np.float64)
                b2 = bone_counts(v2, bones); row["bone_beyond_1mm_after_snap"] = sum(r["beyond_1mm"] for r in b2.values())
                if mid not in ship:
                    ship.append(mid); rows[mid] = rows.get(mid) or {"subject_before": W[mid][0], "status": "ship (snap only, refit unchanged)"}
            snap[mid] = row; print("snap", mid, {k: v for k, v in row.items() if k != "info"}, flush=True)
        if D_store:
            np.savez_compressed(SNAP_NPZ, **D_store)
        elif SNAP_NPZ.exists():
            SNAP_NPZ.unlink()
    res["snap"] = snap
    # tracked after the snap
    if D_store:
        moved2 = {aid: (snapped(new[aid][0], new[aid][1], D_store.get(aid)), new[aid][1]) for aid in ship}; M2 = FF.all_muscles(bj, moved2)
        for aid in SNAP_TRACKED:
            r2 = overlap(trn[aid][0], M2, Q.MUSCLE_WORDS); tr[aid]["after_snap"] = r2
            print(aid, "after snap", r2["beyond_1mm_any"], "max", r2["max_depth_mm"], flush=True)
    st["ship_ids"] = sorted(ship); st["hold_ids"] = sorted(hold); st["snap_npz_md5"] = md5(SNAP_NPZ) if SNAP_NPZ.exists() else None
    st["badges"] = make_badges(rows, snap, st); STORE.write_text(json.dumps(st, indent=1))
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    rep.update({"source": SOURCE, "task": "Q181: her Q48 thigh-muscle boundaries re-fitted on the femur-registered photographs (bone / CT-muscle "
                "surfaces held); her tracked outlines to the Q179 registered + clipped + interpolated candidates; bounded Q177 snap",
                "measure_fullres": res, "refit": {k: st[k] for k in ("held", "params", "changed_ids", "field_full_weight_levels")},
                "broken_q48_levels": {s: st["levels"].get(f"{s}:broken_q48_levels") for s in SIDE_I}})
    REPORT.write_text(json.dumps(rep, indent=1))


BADGE = ("Boundaries with its neighbouring muscles re-fitted (Q181) on her cryosections as re-registered to her CT femur: its Q48 septa "
         "had been fitted in her lost 1 mm photograph frame, which sits {off} off her CT; the Q48 step (marker watershed on the "
         "photographed fascial lines, max 8 mm) was re-run with its markers moved by that offset and her traced sciatic nerve / femoral and "
         "popliteal vessels (re-registered, Q179) kept out of the muscle region, while every surface within 3 mm of her bones or her CT "
         "muscles was held where it was. Volume {v0:.1f} -> {v1:.1f} cm3; section on her photographed muscle "
         "{s0:.0%} -> {s1:.0%}; mesh vertices > 1 mm inside bone {b0} -> {b1}; surface moved up to {mx:.1f} mm (95 % within {p95:.1f} mm).")
BADGE_SNAP = (" Then its {face} face, where her tracked {what} still entered it, moved inward onto the fat plane photographed in her "
              "0.33 mm cryosections (Q177 rule, her muscle colour; median {med:.2f} / max {mx:.2f} mm, volume {dv:+.1f} %); {n1} of its "
              "vertices remain > 1 mm inside it (was {n0}).")
WORDS = {"sciatic_n": "sciatic nerve", "femoral_a_r": "femoral artery", "femoral_v_r": "femoral vein", "femoral_n": "femoral nerve",
         "popliteal_a_r": "popliteal artery", "popliteal_v_r": "popliteal vein"}


def make_badges(rows, snap, st):
    reg = json.loads(Q.REG_JSON.read_text()); out = {}
    med = {s: float(np.median([np.hypot(*v["atlas_dx_dz_mm"]) for y, v in reg["sides"][s].items() if -386 <= int(y) <= 14])) for s in ("right", "left")}
    for aid, r in rows.items():
        if not str(r.get("status", "")).startswith("ship"):
            continue
        if "volume_cm3_mesh" in r:
            s0 = (r["photo_share_her_rule"][0] or {}).get("on_photographed_muscle", 0); s1 = (r["photo_share_her_rule"][1] or {}).get("on_photographed_muscle", 0)
            b = BADGE.format(off=f"{med[side_of(aid)]:.0f} mm (median, {side_of(aid)} leg)", v0=r["volume_cm3_mesh"][0], v1=r["volume_cm3_mesh"][1],
                             s0=s0, s1=s1, b0=r["bone_beyond_1mm"][0], b1=r["bone_beyond_1mm"][1], mx=r["surface_move"]["max_mm"], p95=r["surface_move"]["p95_mm"])
        else:
            b = "Q48 boundaries unchanged by the Q181 re-fit."
        s = snap.get(aid)
        if s and s["status"] == "stored":
            ang = np.degrees(np.arctan2(s["dir_xz"][1], s["dir_xz"][0] if aid.endswith("_r") else -s["dir_xz"][0])) % 360
            b += BADGE_SNAP.format(face=SNAP.dir_name(ang), what=" / ".join(WORDS[t] for t in s["entered_by"]), med=s["move"]["median_mm"],
                                   mx=s["move"]["max_mm"], dv=s["dvol_pct"], n0=s["tracked_beyond_1mm_before"], n1=s["tracked_beyond_1mm_after"])
        if r.get("q152_note"):
            b += " Continuity (Q152 rule, re-applied): " + "; ".join(r["q152_note"]) + "."
        out[aid] = b
    return out


def do_rebadge(a):
    """re-stamp the store's badges from the stored measure report (badge text changes only; no geometry)."""
    st = json.loads(STORE.read_text()); r = json.loads(REPORT.read_text())["measure_fullres"]
    st["badges"] = make_badges(r["muscles"], r["snap"], st); STORE.write_text(json.dumps(st, indent=1)); print(len(st["badges"]), "badges")


# ------------------------------------------------------------------------------------------------ apply (rebuild)
def stamp():
    h = md5b(STORE.read_bytes() + OUT_VOL.read_bytes() + (SNAP_NPZ.read_bytes() if SNAP_NPZ.exists() else b"")); return f"q181-store-{h}"


def do_apply(a):
    if not (STORE.exists() and OUT_VOL.exists()):
        print("no Q181 store / volume"); return
    st = json.loads(STORE.read_text()); d = VH / OUT_SUBJ; sp = stamp()
    if not st.get("ship_ids"):
        print("Q181: nothing to ship"); return
    if a.if_stale and (d / "manifest.json").exists() and sp in (d / "manifest.json").read_text():
        print("have", OUT_SUBJ); return
    assert st["out_vol_md5"] == md5(OUT_VOL), "OUT_VOL does not match the store"
    origin = np.asarray([float(t) for t in a.origin.split(",")]) if a.origin else ORIGIN
    D = dict(np.load(SNAP_NPZ)) if SNAP_NPZ.exists() else {}
    meshes = new_meshes(st["ship_ids"], origin); vs, fs_, structs = [], [], []; vo = fo = 0
    for aid in sorted(meshes):
        v, f, sm, note = meshes[aid]
        if aid in D:
            assert len(D[aid]) == len(v), aid
            v = snapped(v, f, D[aid])
        e = {"atlas_id": aid, "side": side_of(aid), "source_structure": aid, "source_file": f"{OUT_VOL.name}#{label_ids()[aid]}",
             "vertex_offset": vo, "face_offset": fo, "vertex_count": int(len(v)), "triangle_count": int(len(f)),
             "bbox_min_mm": [round(float(x), 4) for x in v.min(0)], "bbox_max_mm": [round(float(x), 4) for x in v.max(0)],
             "surface_smoothing_sigma_voxels": sm}
        if st.get("badges", {}).get(aid):
            e["procedural_badge"] = st["badges"][aid]
        structs.append(e); vs.append(v.astype(np.float32)); fs_.append((f + vo).astype(np.uint32)); vo += len(v); fo += len(f)
    Vall = np.concatenate(vs); Fall = np.concatenate(fs_); d.mkdir(parents=True, exist_ok=True)
    (d / "vertices.f32").write_bytes(Vall.tobytes()); (d / "faces.u32").write_bytes(Fall.tobytes())
    srcm = json.loads((VH / "xfer_vhm2vhf_sep" / "manifest.json").read_text()) if (VH / "xfer_vhm2vhf_sep" / "manifest.json").exists() else {}
    man = {"subject": OUT_SUBJ, "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres", "source_volume": str(OUT_VOL),
           "source_kind": "Q48 label volume with its thigh boundaries re-fitted on her femur-registered photographs (Q181)",
           "label_map": "vhf_xfer_septa", "marching_cubes_step": 1, "vertex_count": int(len(Vall)), "triangle_count": int(len(Fall)),
           "bbox_min_mm": [round(float(x), 4) for x in Vall.min(0)], "bbox_max_mm": [round(float(x), 4) for x in Vall.max(0)],
           "attribution": srcm.get("attribution", []), "note": f"scripts/cryo/vhf_thigh_refit_q181.py apply; {sp}", "structures": structs}
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    print("wrote", d, len(structs), "ids,", len(Vall), "vertices")


# ------------------------------------------------------------------------------------------------ tracked badges (rebuild)
BADGE_TRACKED = ("Placed (Q181) on her photographs as re-registered to her CT femur: it was traced in her 1 mm cryosection frame, which was "
                 "lost; the frame's offset was reconstructed from the traced outlines of both legs against their photographed features "
                 "(femur registration taken out) and the outline moved by it ({how}){clip}{interp}. Her thigh muscles' boundaries were "
                 "re-fitted on the same registered photographs (Q181). Vertices > 1 mm inside a muscle mesh (full resolution): {b} -> {a}.")


def do_badge_tracked(a):
    reg = json.loads(Q.REG_JSON.read_text()); rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    tr = rep.get("verify_fullres", {}).get("tracked", {}) or rep.get("measure_fullres", {}).get("tracked_in_muscle_fullres", {})
    st = json.loads(STORE.read_text()) if STORE.exists() else {"held": []}

    def num(aid):
        r = tr.get(aid, {}); b = (r.get("before") or {}).get("beyond_1mm_any", "?")
        fin = r.get("final") or r.get("after_snap") or r.get("after_refit") or {}; a_ = fin.get("beyond_1mm_any", "?")
        rest = sorted(((k, v["beyond_1mm"]) for k, v in fin.get("per_mesh", {}).items() if v["beyond_1mm"]), key=lambda kv: -kv[1])[:3]
        why = [f"{k} {n}" + (" -- kept in its Q48 place: its re-fit changed its volume by more than 10 %" if k in st["held"] else
                             " -- her CT muscle, not moved" if k.startswith(("iliopsoas", "gluteus")) else "") for k, n in rest]
        return b, (f"{a_} ({'; '.join(why)})" if why else a_)
    med = lambda s: np.median([np.hypot(*v["atlas_dx_dz_mm"]) for y, v in reg["sides"][s].items() if -386 <= int(y) <= 14])
    txt = {}
    b, a_ = num("sciatic_n")
    txt["sciatic_n"] = BADGE_TRACKED.format(how=f"per level and side: right median {med('right'):.1f} mm, left {med('left'):.1f} mm",
                                            clip="; then clipped to her photographed non-muscle (Q176 rule, her calibrated muscle colour)",
                                            interp="; her photographs at y -127..-131 (right) / -127..-132 (left) are unusable (blank, gel spill, "
                                                   "frost) and the nerve there is interpolated between the neighbouring traced levels", b=b, a=a_)
    for g, ids in (("femoral", ("femoral_a_r", "femoral_v_r", "femoral_n")), ("popliteal", ("popliteal_a_r", "popliteal_v_r"))):
        dx, dz = reg["groups"][g]["atlas_dx_dz_mm"]
        for aid in ids:
            b, a_ = num(aid)
            clip = ("; arteries are not clipped (their wall photographs as muscle)" if aid.endswith("_a_r") else
                    "; then clipped to her photographed non-muscle (Q176 rule, her calibrated muscle colour)")
            txt[aid] = BADGE_TRACKED.format(how=f"one translation for the {g} group, {np.hypot(dx, dz):.1f} mm", clip=clip, interp="", b=b, a=a_)
    done = []
    for sub in sorted({s for s, _ in TRACK_NEW.values()}):
        p = VH / sub / "manifest.json"
        if not p.exists():
            continue
        m = json.loads(p.read_text()); ch = False
        for s in m["structures"]:
            t = txt.get(s["atlas_id"])
            if t and s.get("procedural_badge") != t:
                s["procedural_badge"] = t; ch = True; done.append(s["atlas_id"])
        if ch:
            p.write_text(json.dumps(m, indent=1))
    print("badged", sorted(set(done)))


# ------------------------------------------------------------------------------------------------ verify (after the rebuild)
def do_verify(a):
    from scripts.cryo.vhm_tracked_clip import overlap
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    bdir = REPO / (a.bundle or "build/viewer_f_hr"); bf, blob = read_bundle_dir(str(bdir)); B = meshes_by_id(bf, blob)
    ob = json.loads(Path(a.old_bundle).read_text()); oblob = Path(a.old_bundle).with_suffix(".bin").read_bytes(); O = meshes_by_id(ob, oblob)
    h = lambda m: md5b(np.ascontiguousarray(m["v"], np.float32).tobytes() + np.ascontiguousarray(m["f"], np.int64).tobytes())
    new_ids = {e["id"] for e in bf["structures"]}; old_ids = {e["id"] for e in ob["structures"]}
    changed = sorted(i for i in new_ids & old_ids if h(B[i]) != h(O[i]))
    meta = {e["id"]: json.dumps(e.get("rec", {}), sort_keys=True) for e in bf["structures"]}
    ometa = {e["id"]: json.dumps(e.get("rec", {}), sort_keys=True) for e in ob["structures"]}
    st = json.loads(STORE.read_text()); rep = json.loads(REPORT.read_text())
    intended = set(st["ship_ids"]) | set(SNAP_TRACKED)
    out = {"ids_added": sorted(new_ids - old_ids), "ids_removed": sorted(old_ids - new_ids), "geometry_changed": changed,
           "geometry_changed_unintended": sorted(set(changed) - intended), "intended_unchanged": sorted(intended - set(changed)),
           "metadata_changed": sorted(i for i in new_ids & old_ids if meta[i] != ometa.get(i)),
           "structures": [len(ob["structures"]), len(bf["structures"])], "triangles": [ob.get("triangles"), bf.get("triangles")],
           "hashes": {i: [h(O[i]), h(B[i])] for i in sorted(intended) if i in O and i in B}}
    import audit_full_continuity_q112 as AU        # Q112's continuity metric (face-adjacency components, vertex main_frac)
    mf = lambda m: round(AU.analyze_group([(None, np.asarray(m["f"], np.int64), len(m["v"]))])["main_frac"], 4)
    out["continuity_main_frac"] = {i: [mf(O[i]), mf(B[i])] for i in sorted(intended) if i in O and i in B}
    out["continuity_regressions"] = sorted(i for i, (a0, a1) in out["continuity_main_frac"].items()
                                           if (a0 >= AU.CONTINUOUS_THRESHOLD > a1) or a1 < a0 - 0.02)
    Mo = {k: v for k, v in O.items() if any(w in k for w in Q.MUSCLE_WORDS)}; Mn = {k: v for k, v in B.items() if any(w in k for w in Q.MUSCLE_WORDS)}
    tb = {}
    for aid in Q.TRACKED:
        r0 = overlap(np.asarray(O[aid]["v"], float), Mo, Q.MUSCLE_WORDS); r1 = overlap(np.asarray(B[aid]["v"], float), Mn, Q.MUSCLE_WORDS)
        b0 = overlap(np.asarray(O[aid]["v"], float), O, Q.BONES, exact=True); b1 = overlap(np.asarray(B[aid]["v"], float), B, Q.BONES, exact=True)
        tb[aid] = {"muscle_before": r0, "muscle_after": r1, "bone_beyond_1mm": [b0["beyond_1mm_any"], b1["beyond_1mm_any"]],
                   "bone_max_mm": [b0["max_depth_mm"], b1["max_depth_mm"]]}
        print(aid, "bundle > 1 mm in muscle", r0["beyond_1mm_any"], "->", r1["beyond_1mm_any"], "/", r1["vertices"], "max", r0["max_depth_mm"], "->",
              r1["max_depth_mm"], "bone", tb[aid]["bone_beyond_1mm"], flush=True)
    out["tracked_bundle"] = tb
    # full-res: built subjects
    trn = tracked_new(); tro = {}
    for sub in set(TRACK_OLD.values()):
        tro.update(Q.subject_meshes(VH / sub))
    bj = str(REPO / "build/viewer_f_hr/bundle.json"); M1 = FF.all_muscles(bj)        # the rebuilt bundle names the winning subjects
    full = {}
    for aid in SNAP_TRACKED:
        r1 = overlap(trn[aid][0], M1, Q.MUSCLE_WORDS); b1 = overlap(trn[aid][0], B, Q.BONES, exact=True)
        full[aid] = {"final": r1, "bone_beyond_1mm": b1["beyond_1mm_any"]}
        print(aid, "full-res final > 1 mm in muscle", r1["beyond_1mm_any"], "/", r1["vertices"], "max", r1["max_depth_mm"], "bone", b1["beyond_1mm_any"], flush=True)
    out["tracked_fullres_final"] = full
    rep["verify_bundle"] = out; REPORT.write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("tracked_bundle", "tracked_fullres_final", "hashes")}, indent=0)[:3000])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("photos"); p.add_argument("--crops", required=True); p.add_argument("--work", required=True)
    p = sub.add_parser("refit"); p.add_argument("--crops", required=True); p.add_argument("--work", required=True); p.add_argument("--hold", nargs="*")
    p.add_argument("--auto-hold", action="store_true")
    p.add_argument("--traced", action="store_true", help="attempt 2: the traced nerve / vessel sections are excluded from the muscle region")
    p.add_argument("--rule", choices=["q48", "her"], default="q48", help="muscle class for the region / keep (Q48 used cryo_classes_f)")
    p.add_argument("--out", default=None, help="write the volume here instead of OUT_VOL (trial runs; store not touched)")
    p = sub.add_parser("measure"); p.add_argument("--crops", required=True); p.add_argument("--old-subjects", default=None)
    p.add_argument("--no-snap", action="store_true"); p.add_argument("--extra", nargs="*")
    p = sub.add_parser("apply"); p.add_argument("--if-stale", action="store_true"); p.add_argument("--origin", default=None)
    sub.add_parser("rebadge")
    sub.add_parser("badge-tracked")
    p = sub.add_parser("verify"); p.add_argument("--old-bundle", required=True); p.add_argument("--bundle", default=None)
    a = ap.parse_args()
    {"rebadge": do_rebadge, "photos": do_photos, "refit": do_refit, "measure": do_measure, "apply": do_apply, "badge-tracked": do_badge_tracked, "verify": do_verify}[a.cmd](a)


if __name__ == "__main__":
    main()
