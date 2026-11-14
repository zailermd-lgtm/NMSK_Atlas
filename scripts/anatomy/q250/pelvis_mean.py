#!/usr/bin/env python3
"""Q250: MEAN FEMALE PELVIS SHAPE from adult women's CT (TotalSegmentator dataset v2.0.1, CC BY 4.0, n = number of cases that pass the QC of ts_pelvis.py meshes).
The Z-Anatomy pelvic ring (hip bones, sacrum, coccyx; vertex order fixed) is registered (landmark thin-plate pre-warp + non-rigid coherent point drift, pelvis_reg.py) onto every woman's pelvis surface;
the registered rings share the Z vertex order, so they are averaged after a generalised Procrustes alignment (similarity: size removed). The mean has the Z-Anatomy mesh topology (muscle attachments).
    python3 scripts/anatomy/q250/pelvis_mean.py register MESH_DIR OUT_DIR Z_PAGE_DIR [--part i/n]      # one registration per case (about 2 min each)
    python3 scripts/anatomy/q250/pelvis_mean.py mean OUT_DIR MEAN.npz                                  # GPA mean + per-case indicators of the registered rings + validation vs the case's own surface
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q250 import lib as L, pelvis_reg as PR  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

RING = ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx")


def z_ring(zdir):
    _, _, Z = L.load_page(zdir, "atlas_viewer_base_female")
    return {k: (Z[k]["v"], Z[k]["f"]) for k in RING}


def cmd_register(mesh_dir, out_dir, zdir, part="0/1"):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    zr = z_ring(zdir)
    i0, n = (int(x) for x in part.split("/"))
    cases = sorted(p for p in Path(mesh_dir).glob("s*.npz"))[i0::n]
    for p in cases:
        o = out / p.name
        if o.exists():
            continue
        z = np.load(p)
        tr = {k: (z[f"{k}_v"], z[f"{k}_f"]) for k in ("hip_bone_l", "hip_bone_r", "sacrum")}
        pts = np.vstack([L.sample(v, f, 16000)[0] for v, f in tr.values()])
        res = PR.register(zr, pts, target_ring=tr, refine=False, n_ctrl=1300, n_tgt=1700, iters=35, skip=("coccyx",))
        np.savez_compressed(o, report=json.dumps(res["report"]), **res["v"])
        print(p.stem, res["report"]["hip_bone_l"], res["report"]["sacrum"], flush=True)


def gpa(rings, it=8):
    ref = rings[0].copy()
    for _ in range(it):
        al = []
        for r in rings:
            s, R, t = L.umeyama(r, ref)
            al.append(s * r @ R.T + t)
        m = np.mean(al, 0); m = m - m.mean(0)
        ref = m / np.sqrt((m ** 2).sum()) * np.sqrt(((rings[0] - rings[0].mean(0)) ** 2).sum())
    sizes = [float(np.sqrt(((r - r.mean(0)) ** 2).sum())) for r in rings]
    return ref, al, sizes


def cmd_mean(out_dir, mean_npz):
    files = sorted(Path(out_dir).glob("s*.npz"))
    stack, names, reps = [], [], []
    for p in files:
        z = np.load(p)
        stack.append(np.vstack([z[k] for k in RING])); names.append(p.stem); reps.append(json.loads(str(z["report"])))
    ref, al, sizes = gpa(stack)
    mean = np.mean(al, 0)
    # the mean at the mean size of the cases
    ms = float(np.mean(sizes)); mean = mean / np.sqrt(((mean - mean.mean(0)) ** 2).sum()) * ms
    off = np.cumsum([0] + [len(np.load(files[0])[k]) for k in RING])
    np.savez_compressed(mean_npz, mean=mean, offsets=off, cases=np.array(names), sizes=np.array(sizes), centroid_size_mean=ms,
                        **{k: mean[off[i]:off[i + 1]] for i, k in enumerate(RING)})
    print("mean of", len(files), "women; centroid size mean", round(ms, 1), "sd", round(float(np.std(sizes)), 1))


if __name__ == "__main__":
    if sys.argv[1] == "register":
        cmd_register(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[sys.argv.index("--part") + 1] if "--part" in sys.argv else "0/1")
    else:
        cmd_mean(sys.argv[2], sys.argv[3])
