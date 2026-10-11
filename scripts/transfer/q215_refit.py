#!/usr/bin/env python3
"""Q215: re-bound the hip / thigh target muscles of her page on HER OWN femur-registered photographs (1 mm cryosections registered to her CT femur, Q179) -- the Q48 marker watershed redone in the
registered frame (Q181 machinery, scripts/cryo/vhf_thigh_refit_q181.py) with her muscle rule as the region, her bones / CT muscles / pelvic floor held, and every muscle that is not a target held at its
base voxels.  Output = a label volume (same grid as the Q48 volume) in which only the target labels differ; per-muscle guards and the bundle patch are in q215_fill.py.

    python3 scripts/transfer/q215_refit.py --work SCRATCH/q215/work --crops SCRATCH/q215/crops --out SCRATCH/q215/refit.nii.gz [--hold id ...] [--targets id,...]

The registered stack (p1_<side>_{rgb,mus,th}.npy) is made by `python3 scripts/cryo/vhf_thigh_refit_q181.py photos --crops CROPS --work WORK` after streaming the crops with the Q181 commands
(docstring of that script); the crops are deleted after use (45 s per side to re-stream)."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import nibabel as nib
import trimesh
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
from scripts.cryo import vhf_thigh_refit_q181 as R  # noqa: E402
from scripts.transfer.q215_common import HIP_THIGH, SRC_BUNDLE  # noqa: E402

NEAR_MM = 2                       # voxels (1 mm)
MIN_PIECE_FRAC = 0.15            # Q181b dropped detached pieces < 2 % of a muscle; a muscle is ONE piece: pieces < 15 % go to the neighbour they touch most (never a held one) or to background
TARGET_STEMS = [s for s in HIP_THIGH if s != "piriformis"]            # piriformis is not in the Q48 volume (xfer_vhm2vhf, no septa refinement)


def target_ids():
    return [f"{s}_{x}" for s in TARGET_STEMS for x in "rl"]


def held_meshes_q214():
    """her bones (every displayed bone of the page that reaches the photographed window) and her own measured muscles / tendons (subject ct_vhf*, pelvic floor included, and their Z-fill continuation
    pieces) from the Q214 bundle: the surfaces a target muscle never occupies"""
    from scripts.transfer.q200_bundle import Bundle
    B = Bundle(SRC_BUNDLE)
    subj = {it["e"]["id"]: it["e"]["subject"] for it in B.items}
    bones, ct = [], []
    for it in B.items:
        e = it["e"]
        if e.get("hidden_default"):
            continue
        v, f = B.mesh(it)
        if not len(v) or v[:, 1].max() < -430 or v[:, 1].min() > 45:
            continue
        tm = trimesh.Trimesh(v, f, process=False)
        base = re.sub(r"_zfill\w*$", "", e["id"])
        if e["cat"] == "bone":
            bones.append((e["id"], tm))
        elif e["cat"] in ("muscle", "tendon") and subj.get(base, "").startswith("ct_vhf") and not subj.get(base, "").startswith("ct_vhf_xfersepta"):
            ct.append((e["id"], tm))
    return bones, ct


_orig_level = R.refit_level
_orig_bc = R.bc_raster


def solid_masks(shape, A, bones, ct):
    """(bone, own-CT-muscle) 3-D masks on the Q48 label grid, rasterised the way the Q204 audit does (every mesh on its own grid, surface closed by one dilation, filled): the CT bone meshes are open
    shells, a per-level section (Q181's bc_raster) leaves them unfilled and a target muscle kept voxels deep inside them (Q215 trial: embedded 5-14 mm)"""
    from scripts.zanatomy.q198_core import Grid
    out = []
    for group in (bones, ct):
        M = np.zeros(shape, bool)
        for _sid, tm in group:
            v = np.asarray(tm.vertices, float)
            ii = (v[:, 0] + R.ORIGIN[0] - A[0, 3]) / A[0, 0]
            jj = (v[:, 2] + R.ORIGIN[2] - A[1, 3]) / A[1, 1]
            kk = (v[:, 1] + R.ORIGIN[1] - A[2, 3]) / A[2, 2]
            vi = np.column_stack([ii, jj, kk])
            lo = np.floor(vi.min(0)).astype(int) - 4
            hi = np.ceil(vi.max(0)).astype(int) + 4
            g = Grid(lo.astype(float), hi.astype(float), 1.0)
            sol = g.solid(vi, np.asarray(tm.faces, np.int64), close=1)
            sl = tuple(slice(max(int(lo[a]), 0), min(int(lo[a]) + sol.shape[a], shape[a])) for a in range(3))
            sub = tuple(slice(sl[a].start - int(lo[a]), sl[a].stop - int(lo[a])) for a in range(3))
            M[sl] |= sol[sub]
        out.append(M)
    return out


def _bc_solid(bones, ct, A, y, nj, i0, i1):
    key = ("solid3d",)
    if key not in R._CACHE:
        R._CACHE[key] = solid_masks((700, nj, 810), A, bones, ct)
    B3, C3 = R._CACHE[key]
    k = int(round((y + R.ORIGIN[1] - A[2, 3]) / A[2, 2]))
    return B3[i0:i1, :, k], C3[i0:i1, :, k]


def _level_no_bone(L0s, Ls, rgb_th, mus, B, C, move_px, held, Tk=None):
    """Q181's level step + (Q215) a target muscle never keeps a voxel inside her bone or inside one of her own CT / pelvic-floor muscles (Q181 kept the base labels inside the 3 mm band around them,
    the structures themselves included: the Q48 labels filled the femur and ran through the levator ani)"""
    res = _orig_level(L0s, Ls, rgb_th, mus, B, C, move_px, held, Tk)
    hl = list(held) or [-1]
    tgt = (res > 0) & ~np.isin(res, hl)
    res[(B | C) & tgt] = 0
    # (Q215) a voxel on her photographed NON-muscle (fat, fascia, gel) farther than NEAR_MM from her photographed muscle is not part of a target muscle (Q48 / Q181 kept the base label of every voxel within 3 mm
    # of muscle AND, inside the 3 mm band around bone / CT muscles, regardless of what the photograph shows)
    near = ndi.binary_dilation(mus == 2, iterations=NEAR_MM)
    res[(mus == 1) & ~near & tgt] = 0
    return res


def bridge_gaps(out, labels, forbid, max_gap=14, frac=0.15):
    """a target muscle that is empty (< frac of its median section) over a few levels between two populated ones -- her blank / gel-spill photographs at y -127..-134 and the strict photographed-muscle
    rule leave such gaps -- gets the signed-distance blend of its two bounding sections there (only into unlabelled voxels outside her bones / own muscles).  Returns {label: [(y0, y1), ...]} in k"""
    done = {}
    for l in labels:
        area = (out == l).sum((0, 1))
        ks = np.nonzero(area)[0]
        if len(ks) < 3:
            continue
        med = float(np.median(area[ks]))
        thin = np.zeros(len(area), bool)
        thin[ks.min():ks.max() + 1] = area[ks.min():ks.max() + 1] < frac * med
        k = ks.min()
        while k <= ks.max():
            if not thin[k]:
                k += 1
                continue
            k1 = k
            while k1 + 1 <= ks.max() and thin[k1 + 1]:
                k1 += 1
            ka, kb = k - 1, k1 + 1
            if 0 < k - ks.min() and kb <= ks.max() and (k1 - k + 1) <= max_gap and not thin[ka] and not thin[kb]:
                Sa, Sb = R.sdf(out[:, :, ka] == l), R.sdf(out[:, :, kb] == l)
                for kk in range(k, k1 + 1):
                    t = (kk - ka) / (kb - ka)
                    m = (((1 - t) * Sa + t * Sb) < 0) & ~forbid[:, :, kk] & ((out[:, :, kk] == 0) | (out[:, :, kk] == l))
                    out[:, :, kk][m] = l
                done.setdefault(l, []).append((int(k), int(k1)))
            k = k1 + 1
    return done


def zfill_seams():
    """{target id: seam plane y (mm)} of the target muscles that carry a Z-fill continuation piece welded to a flat cut of the old mesh (the plane where the continuation touches the old base)"""
    from scripts.transfer.q200_bundle import Bundle
    B = Bundle(SRC_BUNDLE)
    out = {}
    for aid in target_ids():
        if not B.find(aid):
            continue
        v0, _f0 = B.mesh(B.items[B.find(aid)[0]])
        tree = cKDTree(v0)
        zs = [B.mesh(it)[0] for it in B.items if re.fullmatch(re.escape(aid) + r"_zfill\w*", it["e"]["id"])]
        if not zs:
            continue
        zv = np.vstack(zs)
        near = zv[tree.query(zv)[0] < 1.0]
        if len(near) >= 3:
            out[aid] = float(np.median(near[:, 1]))
    return out


def seam_blend(out, base, seams, forbid, A, band_mm=20):
    """Q215: a muscle whose old mesh carries a Z-fill continuation welded at a flat cut keeps its OLD end section at that plane: the label slice at the seam level is the base slice, blended by a signed-distance
    morph into the re-fitted slice over the BAND_MM below it (the continuation stays welded; the re-fit takes over below the band).  Returns {id: (k_top, k_from)}"""
    ids = R.label_ids()
    done = {}
    for aid, ys in seams.items():
        l = ids[aid]
        kb = np.nonzero((base == l).any((0, 1)))[0]
        k_s = int(round((ys + R.ORIGIN[1] - A[2, 3]) / A[2, 2]))
        if not len(kb) or not (kb.min() <= k_s <= kb.max() + 2):
            continue
        k_top = min(int(kb.max()), k_s)
        sgn = 1 if A[2, 2] > 0 else -1
        k_from = k_top - sgn * band_mm
        for k in range(k_top, k_from - sgn, -sgn):
            t = abs(k - k_from) / float(band_mm)        # 1 at the seam, 0 at the band's lower edge
            Sb, Sr = R.sdf(base[:, :, k] == l), R.sdf(out[:, :, k] == l)
            m = ((t * Sb + (1 - t) * Sr) < 0)
            sl = out[:, :, k]
            allowed = ((sl == 0) | (sl == l) | (base[:, :, k] == l)) & ~forbid[:, :, k]          # her bones / own muscles are never part of it, at the seam either
            sl[sl == l] = 0
            sl[m & allowed] = l
        done[aid] = (k_top, k_from)
    return done


def refit(work, crops, hold_ids, rule="her", log=print):
    R.refit_level = _level_no_bone
    R.bc_raster = _bc_solid
    R.MIN_PIECE_FRAC = MIN_PIECE_FRAC
    if "held_meshes" not in R._CACHE:
        R._CACHE["held_meshes"] = held_meshes_q214()
    a = SimpleNamespace(work=str(work), crops=str(crops), traced=False, rule=rule)
    out, lv, before, after, changed, img, full = R.refit_once(a, list(hold_ids))
    B3, C3 = R._CACHE[("solid3d",)]
    ids = R.label_ids()
    tl = [l for aid, l in ids.items() if aid not in set(hold_ids)]
    kill = np.isin(out, tl) & (B3 | C3)
    out[kill] = 0
    lv["outside_window_bone_ct_removed_voxels"] = int(kill.sum())
    lv["bridged_gaps_k"] = {str(l): g for l, g in bridge_gaps(out, tl, B3 | C3).items()}
    base = np.asarray(nib.load(str(R.Q48_VOL)).dataobj)
    seams = {a: y for a, y in zfill_seams().items() if a not in set(hold_ids)}
    lv["seam_blend"] = {a: [int(x) for x in v] for a, v in seam_blend(out, base, seams, B3 | C3, img.affine).items()}
    lv["zfill_seams_y_mm"] = seams
    after = {aid: int((out == l).sum()) for aid, l in ids.items()}
    changed = sorted(aid for aid, l in ids.items() if aid in before and before[aid] != after[aid])
    return out, lv, before, after, changed, img, full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True); ap.add_argument("--crops", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--hold", nargs="*", default=[]); ap.add_argument("--targets", default="")
    ap.add_argument("--rule", default="her", choices=["her", "q48"])
    a = ap.parse_args()
    ids = R.label_ids()
    targets = [t for t in (a.targets.split(",") if a.targets else target_ids()) if t in ids]
    hold = sorted(set(ids) - set(targets)) + list(a.hold)
    t0 = time.time()
    out, lv, before, after, changed, img, full = refit(a.work, a.crops, hold, a.rule)
    nib.save(nib.Nifti1Image(out, img.affine, img.header), a.out)
    print(f"done {time.time() - t0:.0f} s; changed {len(changed)}")
    for aid in changed:
        print(f"  {aid:28s} {before[aid] / 1000:8.1f} -> {after[aid] / 1000:8.1f} cm3 ({100 * (after[aid] - before[aid]) / max(before[aid], 1):+.1f} %)")
    Path(a.out).with_suffix(".json").write_text(json.dumps(dict(targets=targets, held=hold, changed=changed, before=before, after=after, levels=lv, field_full_weight_levels=full), default=str))


if __name__ == "__main__":
    main()
