#!/usr/bin/env python3
"""Q216: piriformis r / l re-bounded on HER registered photographs with the Q215 machinery (scripts/transfer/q215_refit.py: marker watershed in the registered frame, region = her photographed muscle,
her bones / own CT muscles / pelvic floor never part of it, every other muscle held), after the evidence check of q216_piriformis.py found no label of her own.

    python3 scripts/transfer/q216_piriformis_refit.py --work SCRATCH/q215/work --crops SCRATCH/q215/crops --labels SCRATCH/q215/final_labels.nii.gz --out-dir SCRATCH/q216 [--dry]

Input labels = the FINAL Q215 label volume (her re-bounded hip / thigh muscles) plus the male-carried piriformis meshes of the Q215 bundle rasterised into the unlabelled voxels as labels 58 / 59 (the markers).
Output = candidate meshes (marching cubes of the label, Q215 smoothing) + the Q215 guards (skin, bone, photographed-muscle share, evidence volume, length, one piece, overlap, move) -> JSON for q216_fix.py
(`--piriformis JSON`).  Nothing is written to the bundle here."""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import nibabel as nib

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q215_refit as RF  # noqa: E402
from scripts.transfer import q215_fill as Q15  # noqa: E402
from scripts.transfer.q216_common import SRC_BUNDLE  # noqa: E402
from scripts.cryo import vhf_thigh_refit_q181 as R  # noqa: E402
from scripts.zanatomy.q198_core import Grid  # noqa: E402

PIR = {"piriformis_r": 58, "piriformis_l": 59}


def rasterise(v, f, A, shape):
    ii = (v[:, 0] + R.ORIGIN[0] - A[0, 3]) / A[0, 0]
    jj = (v[:, 2] + R.ORIGIN[2] - A[1, 3]) / A[1, 1]
    kk = (v[:, 1] + R.ORIGIN[1] - A[2, 3]) / A[2, 2]
    vi = np.column_stack([ii, jj, kk])
    lo = np.floor(vi.min(0)).astype(int) - 3
    hi = np.ceil(vi.max(0)).astype(int) + 3
    g = Grid(lo.astype(float), hi.astype(float), 1.0)
    sol = g.solid(vi, np.asarray(f, np.int64), close=1)
    out = np.zeros(shape, bool)
    sl = tuple(slice(max(int(lo[a]), 0), min(int(lo[a]) + sol.shape[a], shape[a])) for a in range(3))
    sub = tuple(slice(sl[a].start - int(lo[a]), sl[a].stop - int(lo[a])) for a in range(3))
    out[sl] = sol[sub]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--crops", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    img = nib.load(a.labels)
    A = img.affine
    D = np.asarray(img.dataobj).copy()
    B = Bundle(SRC_BUNDLE)
    base_masks = {}
    for sid, lab in PIR.items():
        v, f = B.mesh(B.items[B.find(sid)[0]])
        m = rasterise(v, f, A, D.shape)
        base_masks[sid] = m
        D[m & (D == 0)] = lab
    base_path = out_dir / "base_labels_piriformis.nii.gz"
    nib.save(nib.Nifti1Image(D, A, img.header), str(base_path))
    print(f"markers: {({s: int((D == l).sum()) for s, l in PIR.items()})} voxels, base volume written [{time.time() - t0:.0f} s]", flush=True)
    # patch the Q181 machinery: the base volume and the label table carry the two piriformis labels
    R.Q48_VOL = base_path
    _orig_ids = R.label_ids
    R.label_ids = lambda: {**_orig_ids(), **PIR}
    ids = R.label_ids()
    hold = sorted(set(ids) - set(PIR))
    out, lv, before, after, changed, img2, full = RF.refit(a.work, a.crops, hold, "her")
    print(f"refit done [{time.time() - t0:.0f} s]; before {({s: before[s] for s in PIR})} after {({s: after[s] for s in PIR})}", flush=True)
    nib.save(nib.Nifti1Image(out, A, img.header), str(out_dir / "refit_piriformis.nii.gz"))
    page = Q15.Page(B)
    evd = Q15.Evidence(a.work)
    ev_base = evd.shares(D, PIR)
    ev_new = evd.shares(out, PIR)
    rules = R.q152_rules()
    zmeshes = Q15.load_z()
    res = {}
    for sid, lab in PIR.items():
        v0, f0 = B.mesh(B.items[B.find(sid)[0]])
        r = Q15.label_mesh_smooth(out, A, lab, sid, rules)
        if r is None:
            res[sid] = dict(why=["empty label"], ev_base=ev_base[sid], ev_new=ev_new[sid])
            continue
        v, f, smooth, note = r
        v, f = Q15.decimate(v, f)
        v, f = np.asarray(v, float), np.asarray(f, np.int64)
        bpts = Q15.label_boundary_points(out, A, lab, R.ORIGIN)
        zv = zmeshes.get(sid)
        zref = round(Q15.vol_cm3(zv["v"], zv["f"]), 1) if zv is not None else None
        zlen = None
        if zv is not None:
            cz, uz = Q15.principal_axis(np.asarray(zv["v"], float))
            zlen = Q15.extent_along(np.asarray(zv["v"], float), cz, uz)
        g, why = Q15.evaluate(page, sid, v, f, v0, f0, bpts, ev_base[sid], ev_new[sid], zref, [], zlen)
        res[sid] = dict(v=v, f=f, guards=g, why=why, ev_base=ev_base[sid], ev_new=ev_new[sid], notes=note, voxels=[before[sid], after[sid]], bpts_n=int(len(bpts)))
        print(f"{sid}: vol {g['before']['volume_cm3']} -> {g['after']['volume_cm3']}  musc {ev_base[sid]['musc']} -> {ev_new[sid]['musc']}  bone {g['after']['in_bone_pct']} %  len x{g['length_ratio']}  move p95 {g['move']['p95_mm']}  {why or 'ok'}", flush=True)
    ov0 = page.overlap_state({})
    ok = {s: r for s, r in res.items() if "v" in r and not r["why"]}
    ov1 = page.overlap_state({s: (r["v"], r["f"]) for s, r in ok.items()})
    for s, r in res.items():
        if "v" in r:
            r["overlap_vol_pct"] = [ov0.get(s), ov1.get(s)]
            if ov1.get(s, 0) > Q15.OVERLAP_MAX:
                r["why"].append(f"{ov1.get(s)} % of its volume inside the other muscles (gate {Q15.OVERLAP_MAX:g})")
    (out_dir / "piriformis_candidates.pkl").write_bytes(pickle.dumps(res))
    summary = {s: dict(why=r.get("why"), guards=r.get("guards"), overlap_vol_pct=r.get("overlap_vol_pct"), ev_base=r["ev_base"], ev_new=r["ev_new"], notes=r.get("notes"), voxels=r.get("voxels")) for s, r in res.items()}
    (out_dir / "piriformis_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({s: dict(ok=not r.get("why")) for s, r in summary.items()}), f"[{time.time() - t0:.0f} s]")


if __name__ == "__main__":
    main()
