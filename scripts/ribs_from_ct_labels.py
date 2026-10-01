"""Q182: ribs_l / ribs_r of BOTH own-model bundles re-surfaced from the body's own CT rib labels.

    python3 scripts/ribs_from_ct_labels.py build --body vhm|vhf      # -> build/vh/ct_v{m,f}_ribs (one piece per side)
    python3 scripts/ribs_from_ct_labels.py audit --body vhm|vhf --bundle build/viewer_m_hr [--report PATH]

The ribs both bundles shipped until Q182 were the Q105/Q109 voxel remesh (2 mm voxels, 4 dilation iterations,
rib hubs): a blocky envelope whose every vertex sat 12-13 mm outside the TotalSegmentator rib labels (Q182 audit;
Q62 step 9 found it first). `build` runs the project's own convert path (ingest_volume_geometry.py convert, TS
`total` labels 92-103 = rib_left_1..12 -> ribs_l, 104-115 = rib_right_1..12 -> ribs_r, --smooth 1.0, NO dilation)
and then merges the twelve per-rib records of a side into ONE record, so the viewer keeps exactly the ids and the
one-piece-per-side structure it had. The subject is listed BEFORE ct_vhm / ct_vhf in the rebuild scripts, so it wins
the two ids and nothing else moves. Costal cartilages are NOT included (no atlas entity; Q105c).

`audit` measures the shipped (decoded, decimated) ribs of a bundle against the label: signed distance (+ = outside
the label) from the label's own distance field, label -> mesh distance, volume vs the label voxel volume, share of
vertices outside the skin mesh (ct_v?_skin) and inside the lung labels (total 10-14), and the gates below.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

TASK = REPO / "data" / "ct_sources" / "task_outputs"
LABELS = {"ribs_l": list(range(92, 104)), "ribs_r": list(range(104, 116))}
LUNG = list(range(10, 15))
# same origins as the rebuild scripts: her $O (inspect vhf_total), his torso-block origin
ORIGIN = {"vhf": "7.769,-885.229,14.137", "vhm": "-6.035,-895.476,4.787"}
GATES = {"max_median_abs_mm": 1.0, "max_outside_skin_frac": 0.0, "volume_ratio": (0.9, 1.1)}


def subject(body: str) -> str:
    return f"ct_{body}_ribs"


def mapping(body: str) -> dict:
    """the 24 rib entries of the TS `total` map, many-to-one onto ribs_l / ribs_r"""
    names = json.loads((REPO / "mappings" / "totalsegmentator_labels.json").read_text())["labels"]
    entries = [{"label": lab, "source_structure": names[str(lab)], "side": "left" if aid == "ribs_l" else "right",
                "status": "curated", "atlas_id": aid, "relationship": "part_of",
                "note": "Q182: twelve rib labels of one side -> the atlas's one ribs entity (merged into one record)."}
               for aid, labs in LABELS.items() for lab in labs]
    return {"_README": ["Q182 (scripts/ribs_from_ct_labels.py): rib labels only; written by `build`."],
            "subject": subject(body), "source_volume": str(TASK / f"{body}_total.nii.gz"),
            "label_map": "totalsegmentator", "entries": entries}


def merge_records(structs: list) -> list:
    """consecutive records sharing an atlas_id -> one record (vertex/face blocks are contiguous; faces are global)"""
    out = []
    for s in structs:
        p = out[-1] if out else None
        if p and p["atlas_id"] == s["atlas_id"] and p["vertex_offset"] + p["vertex_count"] == s["vertex_offset"] \
                and p["face_offset"] + p["triangle_count"] == s["face_offset"]:
            p["vertex_count"] += s["vertex_count"]; p["triangle_count"] += s["triangle_count"]
            p["bbox_min_mm"] = [min(a, b) for a, b in zip(p["bbox_min_mm"], s["bbox_min_mm"])]
            p["bbox_max_mm"] = [max(a, b) for a, b in zip(p["bbox_max_mm"], s["bbox_max_mm"])]
            p["source_structure"] += "+" + s["source_structure"]; p["source_file"] += "+" + s["source_file"].split("#")[-1]
        else:
            out.append(dict(s))
    return out


def build(body: str) -> int:
    sub = subject(body); mp = REPO / "build" / "vh" / f"{sub}_volume_mapping.json"
    mp.parent.mkdir(parents=True, exist_ok=True); mp.write_text(json.dumps(mapping(body), indent=1))
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "ingest_volume_geometry.py"), "convert",
                        str(TASK / f"{body}_total.nii.gz"), "--labels", "totalsegmentator", "--subject", sub,
                        f"--origin={ORIGIN[body]}", "--smooth", "1.0"], cwd=REPO, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:]); return r.returncode
    mf = REPO / "build" / "vh" / sub / "manifest.json"; m = json.loads(mf.read_text())
    m["structures"] = merge_records(m["structures"])
    m["attribution"] = list(m.get("attribution", [])) + [
        "Q182: ribs re-surfaced from this body's own TotalSegmentator rib labels (no dilation, smoothing 1 voxel); "
        "replaces the Q105/Q109 dilated voxel remesh."]
    mf.write_text(json.dumps(m, indent=2))
    print(f"wrote {mf.parent}: " + ", ".join(f"{s['atlas_id']} {s['triangle_count']} tris" for s in m["structures"]))
    return 0


def _lazy():
    import nibabel as nib, trimesh
    from scipy import ndimage as ndi
    return nib, trimesh, ndi


def to_vox(p, A, O):
    """inverse of engine.volume_ingest.voxels_to_atlas(.) - origin (atlas x, y, z = RAS x, z, y)"""
    p = np.asarray(p, np.float64) + O
    return (np.linalg.inv(A) @ np.c_[p[:, 0], p[:, 2], p[:, 1], np.ones(len(p))].T)[:3].T


def signed_distance(mask, A, O, pts):
    """mm from the label surface, + outside (EDT of a crop around the label, trilinear)"""
    _, _, ndi = _lazy()
    sp = np.sqrt((A[:3, :3] ** 2).sum(0)); idx = np.argwhere(mask)
    lo = np.maximum(idx.min(0) - 40, 0); hi = np.minimum(idx.max(0) + 41, mask.shape)
    m = mask[tuple(slice(a, b) for a, b in zip(lo, hi))]
    sd = np.where(m, -(ndi.distance_transform_edt(m, sampling=sp) - 0.5 * sp.min()),
                  ndi.distance_transform_edt(~m, sampling=sp) - 0.5 * sp.min()).astype(np.float32)
    return ndi.map_coordinates(sd, (to_vox(pts, A, O) - lo).T, order=1, mode="nearest")


def closed_volume_cm3(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0) / 1000.0


def load_skin(body):
    import trimesh
    d = REPO / "build" / "vh" / f"ct_{body}_skin"; s = json.loads((d / "manifest.json").read_text())["structures"][0]
    V = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3); F = np.fromfile(d / "faces.u32", np.uint32).reshape(-1, 3)
    v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]]
    f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
    return trimesh.Trimesh(v, f, process=False)


def audit(body: str, bundle_dir: Path) -> dict:
    nib, trimesh, ndi = _lazy()
    from scipy.spatial import cKDTree
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    from scripts.vhf_pelvic_viscera import mesh_mask
    O = np.array([float(x) for x in ORIGIN[body].split(",")])
    img = nib.load(TASK / f"{body}_total.nii.gz"); A = img.affine; tot = np.asarray(img.dataobj).astype(np.uint8)
    vox = float(np.prod(np.sqrt((A[:3, :3] ** 2).sum(0)))); lung = np.isin(tot, LUNG).astype(np.uint8)
    M = meshes_by_id(*read_bundle_dir(bundle_dir)); skin = load_skin(body); rep = {}
    for rid, labs in LABELS.items():
        mask = np.isin(tot, labs); v, f = M[rid]["v"].astype(float), M[rid]["f"]
        lv, _ = mesh_mask(mask, A, O, smooth=1.0)
        d = signed_distance(mask, A, O, v); back = cKDTree(v).query(lv)[0]
        t = trimesh.Trimesh(v, f, process=False)
        vol = closed_volume_cm3(v, f); lab_vol = mask.sum() * vox / 1000
        r = {"subject": M[rid]["subject"], "pieces": M[rid]["pieces"], "nv": int(len(v)), "nf": int(len(f)),
             "watertight": bool(t.is_watertight),
             "mesh_to_label_mm": {"median_abs": round(float(np.median(np.abs(d))), 2),
                                  "p90_abs": round(float(np.percentile(np.abs(d), 90)), 2),
                                  "median_signed": round(float(np.median(d)), 2),
                                  "frac_outside_label": round(float((d > 0).mean()), 4),
                                  "frac_outside_gt2mm": round(float((d > 2).mean()), 4),
                                  "frac_inside_gt2mm": round(float((d < -2).mean()), 4)},
             "label_to_mesh_mm": {"median": round(float(np.median(back)), 2), "p90": round(float(np.percentile(back, 90)), 2)},
             "volume_cm3": {"mesh": round(vol, 1), "label_voxels": round(lab_vol, 1), "ratio": round(vol / lab_vol, 3),
                            "exact": bool(t.is_watertight)},
             "outside_skin_frac": round(float((~skin.contains(v)).mean()), 4),
             "in_lung_frac": round(float(ndi.map_coordinates(lung, to_vox(v, A, O).T, order=0).mean()), 4),
             "label_surface_in_lung_frac": round(float(ndi.map_coordinates(lung, to_vox(lv, A, O).T, order=0).mean()), 4)}
        g = GATES
        r["gates_pass"] = bool(r["mesh_to_label_mm"]["median_abs"] <= g["max_median_abs_mm"]
                               and r["outside_skin_frac"] <= g["max_outside_skin_frac"]
                               and g["volume_ratio"][0] <= r["volume_cm3"]["ratio"] <= g["volume_ratio"][1])
        rep[rid] = r
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "audit")); ap.add_argument("--body", choices=("vhm", "vhf"), required=True)
    ap.add_argument("--bundle"); ap.add_argument("--report")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        return build(a.body)
    rep = audit(a.body, Path(a.bundle))
    txt = json.dumps({"body": a.body, "bundle": a.bundle, "gates": GATES, "ribs": rep}, indent=1)
    if a.report:
        Path(a.report).write_text(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
