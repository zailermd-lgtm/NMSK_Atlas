#!/usr/bin/env python3
"""Q296 geometry step: import the SPL Inner Ear Atlas structures our pages do not have, onto each page's own ossicles.

    python3 scripts/anatomy/q296/ear296.py fetch   [--dl DIR]        -> download the atlas models + sha256 manifest
    python3 scripts/anatomy/q296/ear296.py build   [KEY...]          -> meshes + measurements into $Q296_OUT (default /dev/shm/q296/ear)
    python3 scripts/anatomy/q296/ear296.py validate [KEY...]         -> non-penetration / containment report only

Source: https://www.openanatomy.org/atlas-pages/atlas-spl-inner-ear.html -- SPL Inner Ear Atlas (Feb 2018),
Bartling (DKFZ) / Jakab / Kikinis (SPL), flat-panel CT ~140 um, licensed under 3D Slicer License Part B.
Our modifications, clearly marked as such per Part B (d): uniform scale + rotation + translation from the
bone-point registration in reg296.py, and quadric decimation to 40 % of the atlas triangle count.
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys, urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (str(HERE), str(REPO), str(REPO / "scripts/anatomy/q295")):
    if p not in sys.path:
        sys.path.insert(0, p)

BASE = "https://www.openanatomy.org/atlases/nac/inner-ear-2018-02/models"
DL = Path(os.environ.get("Q296_DL", "/dev/shm/q296_dl"))
OUT = Path(os.environ.get("Q296_OUT", "/dev/shm/q296/ear"))
DIR = {"base_m": "viewer_zan_atlas", "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
SRC_ROOT = Path(os.environ.get("Q296_SRC", str(REPO / "build/q295")))

# the atlas's landmark ossicles (present on every page as bones) and the structures we import
LANDMARK = {"malleus": "Model_140_Malleus_Bone", "incus": "Model_14_Incus_Bone", "stapes": "Model_17_Stapes_Bone"}
IMPORT = {
    "labyrinth": ("Model_10_Labyrinth", "Bony labyrinth", "Labyrinthus osseus", "bone",
                  "The bony cavity of the inner ear: cochlea, vestibule and the three semicircular canals as one space."),
    "spiral_lamina": ("Model_23_Osseous_Spiral_Lamina", "Osseous spiral lamina", "Lamina spiralis ossea", "bone",
                      "The bony shelf that spirals up the cochlear modiolus and carries the basilar membrane."),
    "fenestra_cochleae": ("Model_12_Fenestra_Rotunda", "Round window (fenestra cochleae)", "Fenestra cochleae", "bone",
                         "The round window at the base of the scala tympani, closed in life by the secondary tympanic membrane."),
    "stapedius": ("Model_28_Stapedius_Muscle", "Stapedius", "Musculus stapedius", "muscle",
                  "The smallest skeletal muscle of the body, in the pyramidal eminence; its tendon pulls the stapes neck."),
}
DECIMATE = 0.4


def fetch(dl=None):
    dl = Path(dl or DL)
    dl.mkdir(parents=True, exist_ok=True)
    man = {}
    for stem in list(LANDMARK.values()) + [v[0] for v in IMPORT.values()]:
        p = dl / f"{stem}.vtk"
        if not p.exists():
            with urllib.request.urlopen(f"{BASE}/{stem}.vtk", timeout=120) as r:
                p.write_bytes(r.read())
        b = p.read_bytes()
        man[stem] = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(), "url": f"{BASE}/{stem}.vtk"}
    (dl / "_manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    return man


def page(key):
    import sl295
    return sl295.Page(key, src=SRC_ROOT / DIR[key])


def struct_mesh(p, sid):
    import trimesh
    m = p.fs == sid; f = p.F[m]; u = np.unique(f)
    r = np.full(p.V.shape[0], -1, np.int64); r[u] = np.arange(len(u))
    return trimesh.Trimesh(p.V[u].astype(np.float64), r[f], process=False)


def dihedral(m):
    a = m.face_adjacency_angles
    return float(np.degrees(np.abs(a).mean())) if len(a) else float("nan")


def defect_pct(m):
    import trimesh
    e = trimesh.grouping.group_rows(m.edges_sorted, require_count=1)
    return round(100.0 * len(e) / max(len(m.edges_sorted), 1), 2)


def build_side(p, sp, side, decimate=DECIMATE):
    """-> (fit, {name: (V, F, stats)}) for one page and one side."""
    import fast_simplification as fs
    import reg296, trimesh
    dst = {k: struct_mesh(p, p.idmap[f"{k}_{side}"]).vertices for k in reg296.OSSICLES}
    M = reg296.fit({k: sp[LANDMARK[k]][0] for k in reg296.OSSICLES}, dst)
    out = {}
    for uid, (stem, name, latin, cat, note) in IMPORT.items():
        V, F = sp[stem]
        Z = reg296.apply(M, V)
        raw = trimesh.Trimesh(Z, F, process=False)
        n = max(200, int(round(len(F) * decimate)))
        v2, f2 = fs.simplify(Z.astype(np.float32), F.astype(np.int32), target_count=n, agg=5)
        v2 = np.asarray(v2, np.float64); f2 = np.asarray(f2, np.int64)
        m = trimesh.Trimesh(v2, f2, process=False)
        out[uid] = (v2, f2, {
            "name": name, "latin": latin, "cat": cat, "note": note, "atlas_model": stem,
            "cm3": round(abs(m.volume) / 1000.0, 5), "cm3_undecimated": round(abs(raw.volume) / 1000.0, 5),
            "tris": int(len(f2)), "tris_atlas": int(len(F)), "verts": int(len(v2)),
            "dihedral_mean_deg": round(dihedral(m), 1), "dihedral_atlas_deg": round(dihedral(raw), 1),
            "defect_edges_pct": defect_pct(m), "area_mm2": round(float(m.area), 1),
            "ext_mm": [round(float(x), 1) for x in (v2.max(0) - v2.min(0))],
        })
    return M, out


def validate(p, made, side, probes=30000):
    """fraction of each imported structure's VOLUME that falls inside each nearby page structure."""
    import trimesh
    rep = {}
    lo = np.vstack([v for v, _, _ in made.values()]).min(0) - 6
    hi = np.vstack([v for v, _, _ in made.values()]).max(0) + 6
    near = []
    for i in range(len(p.ids)):
        m = p.fs == i
        if not m.any():
            continue
        vv = p.V[np.unique(p.F[m])]
        if (vv.max(0) >= lo).all() and (vv.min(0) <= hi).all():
            near.append(i)
    meshes = {}
    for i in near:
        nm = struct_mesh(p, i)
        if nm.is_watertight and abs(nm.volume) > 1e-9:
            meshes[i] = nm
    tb = p.idmap.get(f"temporal_{side}")
    tbm = struct_mesh(p, tb) if tb is not None else None     # the petrous temporal is not watertight; reported separately
    for uid, (v, f, _) in made.items():
        m = trimesh.Trimesh(v, f, process=False)
        try:
            pts = trimesh.sample.volume_mesh(m, probes)
        except Exception:
            pts = np.zeros((0, 3))
        if len(pts) < 200:
            pts = m.vertices
        hits = []
        skinp = None
        for i, nm in meshes.items():
            fr = float(nm.contains(pts).mean())
            if str(p.cats[i]) == "skin":                       # being inside the skin is the desired result, reported on its own
                skinp = max(skinp or 0.0, round(100 * fr, 1))
                continue
            if i == tb:                                        # ditto for the petrous temporal: these are cavities inside it
                continue
            if fr > 0.005:
                hits.append({"id": p.ids[i], "name": p.names[i], "cat": str(p.cats[i]), "pct_of_volume": round(100 * fr, 1)})
        hits.sort(key=lambda h: -h["pct_of_volume"])
        tbp = round(100 * float(tbm.contains(pts).mean()), 1) if tbm is not None and len(pts) else None
        rep[uid] = {"probes": int(len(pts)), "inside": hits, "neighbours_tested": len(meshes),
                    "inside_temporal_bone_pct": tbp, "inside_skin_pct": skinp}
    return rep


def run(cmd, keys):
    import reg296
    man = fetch()
    import oavtk296
    sp = {stem: oavtk296.read_polydata(str(DL / f"{stem}.vtk")) for stem in man}
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for key in keys:
        p = page(key)
        per = {}
        arrays = {}
        for side in ("l", "r"):
            M, made = build_side(p, sp, side)
            fitrec = {k: (v if not isinstance(v, np.ndarray) else np.round(v, 6).tolist()) for k, v in M.items()}
            val = validate(p, made, side) if cmd in ("build", "validate") else {}
            for uid, (v, f, st) in made.items():
                st = dict(st); st["overlap"] = val.get(uid, {}).get("inside", [])
                st["inside_temporal_bone_pct"] = val.get(uid, {}).get("inside_temporal_bone_pct")
                st["inside_skin_pct"] = val.get(uid, {}).get("inside_skin_pct")
                per[f"{uid}_{side}"] = st
                arrays[f"{uid}_{side}__v"] = v.astype(np.float32); arrays[f"{uid}_{side}__f"] = f.astype(np.int32)
            per[f"_fit_{side}"] = fitrec
            print(f"{key} {side}: {M['mode']} scale={M['s']:.5f} rms={M['rms']:.3f} median={M['median_mm']:.3f} "
                  f"p95={M['p95_mm']:.3f} max={M['max_mm']:.3f} (n={M['n']})", flush=True)
            for uid, (v, f, st) in made.items():
                vv = val.get(uid, {})
                ov = ", ".join(f"{h['name']} {h['pct_of_volume']}%" for h in vv.get("inside", [])[:4])
                ov = f"in temporal bone {vv.get('inside_temporal_bone_pct')}% in skin {vv.get('inside_skin_pct')}% | " + ov
                print(f"   {uid:17s} {st['cm3']:8.5f} cm3 {st['tris']:6d} tris dih {st['dihedral_mean_deg']:5.1f} "
                      f"def {st['defect_edges_pct']:4.2f}% | {ov}", flush=True)
        report[key] = per
        if cmd == "build":
            np.savez_compressed(OUT / f"{key}_ear.npz", **arrays)
            (OUT / f"{key}_ear.json").write_text(json.dumps(per, indent=1), encoding="utf-8")
    (OUT / "_report.json").write_text(json.dumps({"atlas": man, "decimate": DECIMATE, "pages": report}, indent=1), encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "build", "validate"])
    ap.add_argument("keys", nargs="*")
    a = ap.parse_args()
    if a.cmd == "fetch":
        print(json.dumps(fetch(), indent=1))
        return
    run(a.cmd, a.keys or list(DIR))


if __name__ == "__main__":
    main()
