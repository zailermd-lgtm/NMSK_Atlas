#!/usr/bin/env python3
"""Q214: HER splenius from her OWN evidence: the splenius compartment of her registered 1 mm cryosection frame (labels 1 = right, 11 = left of
data/ct_sources/task_outputs/vhf_deep_neck_cryo.nii.gz; Q62 step 3, rule-based on her photographs + her CT labels; 79.0 / 68.1 cm3), which the Q62 build left unshipped because splenius capitis and
splenius cervicis are ONE sheet at 1 mm (no septum between them in her photographs, `not_shipped` in vhf_deep_neck_cryo_report.json).  It is shipped as ONE mesh per side under the id
`splenius_capitis_<side>` (the compartment is mostly the capitis; the cervicis is its inferolateral part) and `splenius_cervicis_<side>` is NOT built separately: cutting the sheet in two would need a
boundary that her photographs do not show (cutting it by the Z-Anatomy counterparts, fitted to her, leaves 1.6 / 2.6 cm3 for the cervicis against 13-15 cm3 in Z-Anatomy and puts 96-100 % of the Z splenius
vertices outside her compartment -- recorded in the report).  Surfaced like every other cryo structure of her page (`engine.volume_ingest.mask_surface`, Gaussian sigma 1 voxel, the page's atlas origin) and
decimated to the page budget; the lower end is the compartment's own cut at the T1 body top (`limits` of the Q62 report).

    python3 scripts/transfer/q214_splenius_own.py [--out build/q214/splenius_own.npz] [--report data/derived/Q214_splenius_own.json]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from engine import volume_ingest as vol  # noqa: E402
import motor_points_q187 as MP  # noqa: E402

VOLUME = REPO / "data/ct_sources/task_outputs/vhf_deep_neck_cryo.nii.gz"
ORIGIN = np.array([7.769, -885.229, 14.137])        # atlas origin of her page (scripts/ingest_volume_geometry.py inspect vhf_total.nii.gz)
LABEL = {"r": 1, "l": 11}
Z_PAGE = REPO / "build/q213/viewer_zan_female/atlas_viewer_zan_female.html"
FACE_BUDGET = 9000          # the page's budget for a mid-size muscle (semispinalis capitis 9000)


def z_meshes():
    MP.VIEWERS["_q214z"] = {"kind": "zan", "html": Z_PAGE, "label": "z"}
    return MP.load_viewer("_q214z")


def compartment_mask(volume, s):
    m = volume == LABEL[s]
    lab, n = ndi.label(m, structure=np.ones((3, 3, 3)))
    if n > 1:
        sizes = ndi.sum(m, lab, index=np.arange(1, n + 1))
        m = lab == 1 + int(np.argmax(sizes))
    return ndi.binary_fill_holes(m)


def mesh_of(mask, affine):
    v, f = vol.mask_surface(mask, step=1, smooth=1.0)
    v = vol.voxels_to_atlas(v, affine) - ORIGIN
    tm = trimesh.Trimesh(v, f, process=False)
    n0 = len(f)
    if len(f) > FACE_BUDGET:
        tm = tm.simplify_quadric_decimation(face_count=FACE_BUDGET)
    return np.asarray(tm.vertices, float), np.asarray(tm.faces, np.int64), n0


def build():
    volume, affine, _ = vol.load_labels(str(VOLUME))
    voxel_cm3 = float(abs(np.linalg.det(affine[:3, :3]))) / 1000.0
    Z = z_meshes()
    res, rep = {}, {}
    for s in "rl":
        m = compartment_mask(volume, s)
        v, f, n0 = mesh_of(m, affine)
        tm = trimesh.Trimesh(v, f, process=False)
        res[f"splenius_capitis_{s}"] = (v, f)
        cap = Z[f"splenius_capitis_{s}"]
        cer = Z[f"zan_splenius_colli_muscle_{s}"]
        full = trimesh.Trimesh(*mask_full_mesh(m, affine), process=False)
        outside = {n: round(100.0 * float((~full.contains(z["v"])).mean()), 1) for n, z in (("z_capitis", cap), ("z_cervicis", cer))}
        rep[f"splenius_{s}"] = dict(label=LABEL[s], voxels=int(m.sum()), voxel_volume_cm3=round(float(m.sum()) * voxel_cm3, 2), mesh_volume_cm3=round(abs(tm.volume) / 1000.0, 2),
                                    watertight=bool(tm.is_watertight), faces_full=int(n0), faces=int(len(f)),
                                    y_range_mm=[round(float(v[:, 1].min()), 1), round(float(v[:, 1].max()), 1)],
                                    z_fit_capitis_cm3=round(abs(trimesh.Trimesh(cap["v"], cap["f"], process=False).volume) / 1000.0, 2),
                                    z_fit_cervicis_cm3=round(abs(trimesh.Trimesh(cer["v"], cer["f"], process=False).volume) / 1000.0, 2),
                                    z_fit_vertices_outside_her_compartment_pct=outside)
    return res, rep


def mask_full_mesh(mask, affine):
    v, f = vol.mask_surface(mask, step=1, smooth=1.0)
    return vol.voxels_to_atlas(v, affine) - ORIGIN, f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "build/q214/splenius_own.npz"))
    ap.add_argument("--report", default=str(REPO / "data/derived/Q214_splenius_own.json"))
    a = ap.parse_args()
    res, rep = build()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, **{f"{k}_v": v for k, (v, f) in res.items()}, **{f"{k}_f": f for k, (v, f) in res.items()})
    Path(a.report).write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
