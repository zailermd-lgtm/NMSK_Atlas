"""Q183: costal_cartilage_r / _l of the MALE own-model bundle from HIS OWN CT costal-cartilage label.

    python3 scripts/costal_cartilage_from_ct_labels.py build                      # -> build/vh/ct_vhm_ccart
    python3 scripts/costal_cartilage_from_ct_labels.py audit --body vhm|vhf --bundle DIR [--report PATH]
    python3 scripts/costal_cartilage_from_ct_labels.py foreign --bundle build/viewer_m_hr [--report PATH]
    python3 scripts/costal_cartilage_from_ct_labels.py stamp                      # badge the remaining ct_s1159* records

Until Q183 his costal cartilages came from `ct_s1159`: TotalSegmentator dataset case s1159 (a 47 y female polytrauma
CT, chosen 2026-09-10 as the vertex-to-hip filler body), placed into his frame by its own femoral-head origin. They sat
12-62 mm off his ribs and 35 mm off his sternum. His own `total` run HAS label 117 (costal_cartilages, 164 cm3); his
mapping had nulled it with the copy-pasted vessel note ("no contrast"), which does not apply to cartilage. `build` runs
Q182's convert path on that label (no dilation, --smooth 1.0, his torso-block origin), split at his own midline measured
from his sternum label (`midline` splitter, mappings/totalsegmentator_labels.json). Listed before ct_s1159 in
vhm_rebuild_bundle.sh, so it wins exactly these two ids.

`foreign` measures every other ct_s1159* record of his bundle against his own labels (no source of his own for them:
vessels are no-contrast fragments, quadratus lumborum failed asymmetrically); `stamp` writes the resulting badge.
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

from scripts.ribs_from_ct_labels import ORIGIN, TASK, LUNG, closed_volume_cm3, load_skin, signed_distance, to_vox  # noqa: E402

SUB = "ct_vhm_ccart"
CART = 117
STERNUM = 116
IDS = {"right": "costal_cartilage_r", "left": "costal_cartilage_l"}
RIBS = {"costal_cartilage_l": list(range(92, 102)), "costal_cartilage_r": list(range(104, 114))}   # ribs 1-10
BONE = list(range(25, 51)) + list(range(69, 79)) + [91] + list(range(92, 117)) + [118]   # 118: her Q185k L1B (vhf_total_q185k)
TOUCH_MM = 3.0
HALF = 0.9375   # in-plane voxel: a voxel centre is half a voxel inside the label surface
GATES = {"rib_end_touch_min": 8, "sternum_min_mm": 1.0, "outside_skin_frac": 0.0, "volume_ratio": (0.85, 1.1)}
NOTE = ("Q183: from his own TotalSegmentator `total` label 117, split at his midline measured from his sternum label; "
        "replaces the ct_s1159 (another person's CT) cartilages, which sat 12-62 mm off his ribs.")
# Q183 audit -> the other ct_s1159* records: what each should touch in HIS labels
FOREIGN_TOUCH = {
    "aortic_arch_and_great_vessels": [52, 16, 15], "descending_thoracic_aorta": [52] + list(range(32, 41)),
    "abdominal_aorta": [52] + list(range(27, 32)), "brachiocephalic_trunk_r": [54, 16],
    "subclavian_a_r": [55, 104], "subclavian_a_l": [56, 92], "common_carotid_a_r": [57, 16, 17],
    "common_carotid_a_l": [58, 16, 17], "brachiocephalic_v_l": [59], "brachiocephalic_v_r": [60],
    "superior_vena_cava": [62, 51], "inferior_vena_cava": [63, 5, 51], "common_iliac_a_l": [65, 27], "common_iliac_a_r": [66, 27],
    "common_iliac_v_l": [67, 27], "common_iliac_v_r": [68, 27],
    "quadratus_lumborum_r": [115, 78, 89, 87], "quadratus_lumborum_l": [103, 77, 88, 86]}
OWN_LABEL = {"aortic_arch_and_great_vessels": 52, "descending_thoracic_aorta": 52, "abdominal_aorta": 52,
             "brachiocephalic_trunk_r": 54, "subclavian_a_r": 55, "subclavian_a_l": 56, "common_carotid_a_r": 57,
             "common_carotid_a_l": 58, "brachiocephalic_v_l": 59, "brachiocephalic_v_r": 60, "superior_vena_cava": 62,
             "inferior_vena_cava": 63, "common_iliac_a_l": 65, "common_iliac_a_r": 66, "common_iliac_v_l": 67,
             "common_iliac_v_r": 68}


def mapping() -> dict:
    return {"_README": ["Q183 (scripts/costal_cartilage_from_ct_labels.py): costal cartilage label only; written by `build`."],
            "subject": SUB, "source_volume": str(TASK / "vhm_total.nii.gz"), "label_map": "totalsegmentator",
            "entries": [{"label": CART, "source_structure": "costal_cartilages", "side": None, "status": "curated",
                         "atlas_id": None, "relationship": "split", "splitter": "midline", "split_parts": dict(IDS),
                         "note": "Q183: his own label (cartilage needs no contrast); cut at his midline from his sternum label."}]}


def fix_manifest(m: dict) -> dict:
    """side from the split part (convert copies the entry's null side), Q183 attribution; idempotent"""
    side = {v: k for k, v in IDS.items()}
    for s in m["structures"]:
        s["side"] = side[s["atlas_id"]]
    if NOTE not in m.get("attribution", []):
        m["attribution"] = list(m.get("attribution", [])) + [NOTE]
    return m


def build() -> int:
    mp = REPO / "build" / "vh" / f"{SUB}_volume_mapping.json"
    mp.parent.mkdir(parents=True, exist_ok=True); mp.write_text(json.dumps(mapping(), indent=1))
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "ingest_volume_geometry.py"), "convert",
                        str(TASK / "vhm_total.nii.gz"), "--labels", "totalsegmentator", "--subject", SUB,
                        f"--origin={ORIGIN['vhm']}", "--smooth", "1.0"], cwd=REPO, capture_output=True, text=True)
    print("\n".join(l for l in r.stdout.splitlines() if "midline" in l))
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:]); return r.returncode
    mf = REPO / "build" / "vh" / SUB / "manifest.json"
    m = fix_manifest(json.loads(mf.read_text())); mf.write_text(json.dumps(m, indent=2))
    print(f"wrote {mf.parent}: " + ", ".join(f"{s['atlas_id']} {s['triangle_count']} tris" for s in m["structures"]))
    return 0


def _vox_pts(mask, A, O):
    """atlas mm (origin-subtracted) of mask voxels"""
    from engine.volume_ingest import atlas_points_of
    return atlas_points_of(mask, A)[1] - O


def _surface_pts(v, f, n=200000, seed=0):
    import trimesh
    p, _ = trimesh.sample.sample_surface(trimesh.Trimesh(v, f, process=False), n, seed=seed)
    return np.vstack([p, v])


def _load(body):
    import nibabel as nib
    img = nib.load(TASK / f"{body}_total.nii.gz"); A = img.affine
    return np.asarray(img.dataobj).astype(np.uint8), A, np.array([float(x) for x in ORIGIN[body].split(",")])


def audit(body: str, bundle_dir: Path) -> dict:
    from scipy import ndimage as ndi
    from scipy.spatial import cKDTree
    import trimesh
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    from scripts.vhf_pelvic_viscera import mesh_mask
    from engine.volume_ingest import split_at_midline, load_label_names
    tot, A, O = _load(body)
    vox = float(np.prod(np.sqrt((A[:3, :3] ** 2).sum(0))))
    names = load_label_names("totalsegmentator"); parts, notes = split_at_midline(tot, CART, A, {n: i for i, n in names.items()})
    M = meshes_by_id(*read_bundle_dir(bundle_dir)); skin = load_skin(body); lung = np.isin(tot, LUNG).astype(np.uint8)
    rib_tree = cKDTree(np.vstack([_surface_pts(M[r]["v"].astype(float), M[r]["f"]) for r in ("ribs_l", "ribs_r")]))
    st = M["sternum"]; st_tree = cKDTree(_surface_pts(st["v"].astype(float), st["f"]))
    rep = {"midline": notes}
    for side, rid in IDS.items():
        v, f = M[rid]["v"].astype(float), M[rid]["f"]; t = trimesh.Trimesh(v, f, process=False)
        cv = cKDTree(_surface_pts(v, f)); mask = parts[side]
        d_rib = rib_tree.query(v)[0]; d_st = st_tree.query(v)[0]
        ends, contact = [], []
        for lab in RIBS[rid]:
            p = _vox_pts(tot == lab, A, O)
            if len(p) == 0:
                ends.append(None); contact.append(None); continue
            tip = p[p[:, 2] >= np.percentile(p[:, 2], 97)].mean(0)    # most anterior 3 % of the rib = costochondral end
            ends.append(round(float(cv.query(tip)[0]), 1))
            contact.append(round(float(max(cv.query(p)[0].min() - 0.5 * HALF, 0.0)), 1))   # rib label -> cartilage surface
        lv, _ = mesh_mask(mask, A, O, smooth=1.0)
        sd = signed_distance(tot == CART, A, O, v)
        vol = closed_volume_cm3(v, f); lab_vol = mask.sum() * vox / 1000; ext = v.max(0) - v.min(0)
        r = {"subject": M[rid]["subject"], "nv": int(len(v)), "nf": int(len(f)), "pieces": M[rid]["pieces"],
             "watertight": bool(t.is_watertight),
             "to_ribs_mm": {"min": round(float(d_rib.min()), 1), "median": round(float(np.median(d_rib)), 1),
                            "frac_within_3mm": round(float((d_rib <= TOUCH_MM).mean()), 3)},
             "rib_1_10_anterior_end_to_cartilage_mm": ends,
             "rib_1_10_label_to_cartilage_min_mm": contact,
             "rib_ends_touched": int(sum(e is not None and e <= TOUCH_MM for e in contact)),
             "to_sternum_mm": {"min": round(float(d_st.min()), 1), "median": round(float(np.median(d_st)), 1),
                               "frac_within_3mm": round(float((d_st <= TOUCH_MM).mean()), 3)},
             "to_own_label_mm": {"median_abs": round(float(np.median(np.abs(sd))), 2),
                                 "p90_abs": round(float(np.percentile(np.abs(sd), 90)), 2),
                                 "frac_outside_gt2mm": round(float((sd > 2).mean()), 4)},
             "volume_cm3": {"mesh": round(vol, 1), "label_side_voxels": round(lab_vol, 1), "ratio": round(vol / lab_vol, 3)},
             "extent_mm_lr_si_ap": [round(float(x), 1) for x in ext],
             "outside_skin_frac": round(float((~skin.contains(v)).mean()), 4),
             "in_lung_frac": round(float(ndi.map_coordinates(lung, to_vox(v, A, O).T, order=0).mean()), 4),
             "label_surface_in_lung_frac": round(float(ndi.map_coordinates(lung, to_vox(lv, A, O).T, order=0).mean()), 4)}
        g = GATES
        r["gates_pass"] = bool(r["rib_ends_touched"] >= g["rib_end_touch_min"] and r["to_sternum_mm"]["min"] <= g["sternum_min_mm"]
                               and r["outside_skin_frac"] <= g["outside_skin_frac"]
                               and r["in_lung_frac"] <= r["label_surface_in_lung_frac"] + 0.005
                               and g["volume_ratio"][0] <= r["volume_cm3"]["ratio"] <= g["volume_ratio"][1])
        rep[rid] = r
    return rep


def foreign(bundle_dir: Path) -> dict:
    """every non-VHM, non-transfer record of his bundle, measured against HIS labels"""
    from scipy import ndimage as ndi
    from scipy.spatial import cKDTree
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    tot, A, O = _load("vhm"); M = meshes_by_id(*read_bundle_dir(bundle_dir)); skin = load_skin("vhm")
    lung = np.isin(tot, LUNG).astype(np.uint8); bone = np.isin(tot, BONE).astype(np.uint8)
    trees = {}

    def tree(lab):
        if lab not in trees:
            p = _vox_pts(tot == lab, A, O); trees[lab] = (cKDTree(p) if len(p) else None, len(p))
        return trees[lab]
    names = json.loads((REPO / "mappings" / "totalsegmentator_labels.json").read_text())["labels"]
    out = {}
    for rid, m in M.items():
        if m["subject"].startswith(("ct_vhm", "vhm_", "xfer_")):
            continue
        v = m["v"].astype(float); iv = to_vox(v, A, O).T
        r = {"subject": m["subject"], "nv": int(len(v)), "outside_skin_frac": round(float((~skin.contains(v)).mean()), 4),
             "in_his_lung_frac": round(float(ndi.map_coordinates(lung, iv, order=0).mean()), 4),
             "in_his_bone_frac": round(float(ndi.map_coordinates(bone, iv, order=0).mean()), 4), "should_touch": {}}
        for lab in FOREIGN_TOUCH.get(rid, []):
            t, n = tree(lab)
            r["should_touch"][names[str(lab)]] = None if t is None else round(float(t.query(v)[0].min()), 1)
        own = OWN_LABEL.get(rid)
        if own is not None:
            t, n = tree(own)
            if t is not None:
                d = t.query(v)[0]; vt = cKDTree(v); back = vt.query(t.data)[0]
                r["his_own_label"] = {"name": names[str(own)], "voxels": n, "mesh_to_label_median_mm": round(float(np.median(d)), 1),
                                      "label_within_5mm_of_mesh_frac": round(float((back <= 5).mean()), 3)}
        out[rid] = r
    return out


def badge(rid: str, r: dict) -> str:
    st = ", ".join(f"{k} {v} mm" for k, v in r["should_touch"].items() if v is not None)
    own = r.get("his_own_label")
    own_s = (f"; his own no-contrast '{own['name']}' label fragment lies {own['mesh_to_label_median_mm']} mm (median) from it"
             if own else "")
    return ("Q183: NOT HIS GEOMETRY. Surfaced from another person's CT (TotalSegmentator case s1159, a 47-year-old "
            "female, contrast CT) and placed in his frame by its own femoral-head fit, not registered to his body. "
            f"Measured against his CT: nearest distance to what it should touch {st or 'n/a'}{own_s}; "
            f"{100 * r['outside_skin_frac']:.1f} % outside his skin, {100 * r['in_his_bone_frac']:.1f} % inside his bone labels, "
            f"{100 * r['in_his_lung_frac']:.1f} % inside his lung labels. His own CT has no usable source for it "
            "(frozen cadaver, no contrast" + ("" if rid.startswith("quadratus") else ": vessel labels are fragments") +
            ("; his abdominal-muscle task failed, quadratus lumborum asymmetric 2-6x" if rid.startswith("quadratus") else "")
            + "). Queued to replace.")


def stamp(report: Path) -> int:
    """procedural_badge onto the ct_s1159 / ct_s1159_abd manifest records (idempotent: rewritten from the report)"""
    rep = json.loads(report.read_text())["foreign"]; n = 0
    for sub in ("ct_s1159", "ct_s1159_abd"):
        mf = REPO / "build" / "vh" / sub / "manifest.json"
        if not mf.exists():
            continue
        m = json.loads(mf.read_text())
        for s in m["structures"]:
            if s["atlas_id"] in rep and rep[s["atlas_id"]]["subject"] == sub:
                s["procedural_badge"] = badge(s["atlas_id"], rep[s["atlas_id"]]); n += 1
        mf.write_text(json.dumps(m, indent=2))
    print(f"stamped {n} ct_s1159* records")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "audit", "foreign", "stamp"))
    ap.add_argument("--body", choices=("vhm", "vhf"), default="vhm"); ap.add_argument("--bundle"); ap.add_argument("--report")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        return build()
    if a.cmd == "stamp":
        return stamp(Path(a.report or REPO / "data" / "derived" / "Q183_vhm_foreign_audit.json"))
    rep = audit(a.body, Path(a.bundle)) if a.cmd == "audit" else {"foreign": foreign(Path(a.bundle))}
    txt = json.dumps({"cmd": a.cmd, "body": a.body, "bundle": a.bundle, "gates": GATES, **({"cartilage": rep} if a.cmd == "audit" else rep)}, indent=1)
    if a.report:
        Path(a.report).write_text(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
