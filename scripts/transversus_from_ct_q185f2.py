"""Q185f2: her transversus abdominis r/l from HER OWN CT -- the muscle-density layer deep to her own TotalSegmentator
internal-oblique label (the female bundle had shipped HIS cryosection TA carried across, 24-46 % inside her organs).

    python3 scripts/transversus_from_ct_q185f2.py build    # -> task_outputs/vhf_transversus_q185f2.nii.gz + label key + subject mapping
    (vhf_rebuild_bundle.sh converts it: ct_vhf_tam, --smooth 1.0)
    python3 scripts/transversus_from_ct_q185f2.py gate     # gates the converted meshes (+ route c numbers) -> data/derived/Q185f2_transversus_vhf.json
    python3 scripts/transversus_from_ct_q185f2.py stamp    # badge (+ shipped flag) into build/vh/ct_vhf_tam/manifest.json
    python3 scripts/transversus_from_ct_q185f2.py montage  # scratch q185f2c2/montage_abdominal_wall_before_after.png

Route (Q183b order): (a) her own CT label -- TS `abdominal_muscles` has NO transversus class (mappings/
totalsegmentator_abdominal_muscles_labels.json: rectus, external / internal oblique, QL, psoas, ... ), but its wall labels
plus her own CT (the restacked torso series, scratch vh_idc/nii/vhf_torso_0937.nii.gz, same 0.9375 x 0.9375 x 1 mm grid)
show an UNLABELLED muscle-density band directly deep to the internal-oblique label (0-1 / 1-2 / 2-3 mm: 87 / 77 / 58 % of
voxels in -30..150 HU, fat beyond 3-4 mm; the superficial side falls off within 1-2 mm = partial volume). TA lies
immediately deep to IO (Gray's Anatomy 42nd ed., 'Anterior abdominal wall'), so that band is taken as TA:
  TA(side) = voxels 0 < d <= SHELL_MM from that side's IO label, on the deep side (in-slice distance to the wall-ring
  centre smaller than that of the nearest IO voxel), NOT in any `total` / `abdominal_muscles` label (organs, bone, other
  muscles), CT 3x3x3-median in MUSCLE_HU, then only 26-connected components reaching the d <= SEED_MM layer and >= MIN_CC_ML.
(b) her cryosection photographs of the abdomen are not local -> not used. (c) his TA carried by the bone-driven transfer =
what shipped until now (xfer_vhm2vhf_tva) -- measured beside it in the report.
Gates (Q185f2): <= 5 % of vertices > 1 mm inside her organ labels (sweep ORGANS) and <= 5 % in lung, <= 2 % > 1 mm in bone,
0 % outside her skin, layer order: <= 5 % inside her IO mesh, <= 1 % inside her EO mesh, >= 90 % of vertices deeper
(farther from her skin) than the nearest IO vertex. Volume reported vs her IO / EO; no published TA volume was found
(Rankin 2006 Muscle Nerve doi:10.1002/mus.20589: ultrasound thickness order RA > IO > EO > TA, TA the thinnest layer;
Izumoto 2019 PLoS One doi:10.1371/journal.pone.0214752 and Sanchis-Moysi 2013 doi:10.1080/14763141.2012.725087 give only
the obliques + TA together).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

TASK = REPO / "data" / "ct_sources" / "task_outputs"
SCRATCH = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad")
CT = SCRATCH / "vh_idc" / "nii" / "vhf_torso_0937.nii.gz"
OUT_VOL = TASK / "vhf_transversus_q185f2.nii.gz"
KEY = REPO / "mappings" / "vhf_transversus_labels.json"
SUBJ = "ct_vhf_tam"
MAPPING = REPO / "mappings" / "subjects" / f"{SUBJ}_volume_mapping.json"
REPORT = REPO / "data" / "derived" / "Q185f2_transversus_vhf.json"
IO = {"right": 13, "left": 14}                # TS abdominal_muscles internal_oblique_right / _left
WALL = (3, 4, 11, 12, 13, 14)                 # rectus, external + internal oblique (wall-ring centre)
AID = {"right": "transversus_abdominis_r", "left": "transversus_abdominis_l"}
LAB = {"right": 1, "left": 2}
SHELL_MM, SEED_MM, MIN_CC_ML = 6.0, 1.5, 1.0
MUSCLE_HU = (-30, 150)                        # same window as trunk_wall_from_ct.py on her CT
GATES = {"in_organ_gt1mm_frac": 0.05, "in_lung_gt1mm_frac": 0.05, "in_bone_gt1mm_frac": 0.02, "outside_skin_frac": 0.0,
         "inside_io_frac": 0.05, "inside_eo_frac": 0.01, "deeper_than_io_frac": 0.90}


# ---------------------------------------------------------------- pure rule (tested)
def deep_band(io: np.ndarray, occupied: np.ndarray, muscle: np.ndarray, centre_ij: np.ndarray, sp,
              shell=SHELL_MM, seed=SEED_MM, min_vox=1) -> np.ndarray:
    """voxels 0 < d <= shell from `io`, deeper than their nearest io voxel (in-slice radius from centre_ij[k]), free,
    muscle-dense, in 26-connected components that reach d <= seed and have >= min_vox voxels"""
    from scipy import ndimage as ndi
    d, ind = ndi.distance_transform_edt(~io, sampling=sp, return_indices=True)
    cand = (d > 0) & (d <= shell) & ~occupied & muscle
    X, Y, Z = np.nonzero(cand)
    ci, cj = centre_ij[Z, 0], centre_ij[Z, 1]
    deeper = np.hypot(X - ci, Y - cj) < np.hypot(ind[0][X, Y, Z] - ci, ind[1][X, Y, Z] - cj)
    m = np.zeros(io.shape, bool); m[X[deeper], Y[deeper], Z[deeper]] = True
    lab, n = ndi.label(m, np.ones((3, 3, 3), bool))
    if not n:
        return m
    size = ndi.sum(m, lab, range(1, n + 1)); touch = ndi.maximum(m & (d <= seed), lab, range(1, n + 1))
    keep = np.flatnonzero((size >= min_vox) & (touch > 0)) + 1
    return np.isin(lab, keep)


def ring_centres(wall: np.ndarray) -> np.ndarray:
    """per axial slice k: (i, j) centroid of the wall-muscle voxels (NaN-free: empty slices take the nearest filled)"""
    ii, jj, kk = np.nonzero(wall); nz = wall.shape[2]
    cnt = np.bincount(kk, minlength=nz).astype(float)
    c = np.c_[np.bincount(kk, ii, nz), np.bincount(kk, jj, nz)] / np.maximum(cnt, 1)[:, None]
    full = np.flatnonzero(cnt)
    for k in np.flatnonzero(cnt == 0):
        c[k] = c[full[np.argmin(np.abs(full - k))]]
    return c


# ---------------------------------------------------------------- build
def build() -> int:
    import nibabel as nib
    from scipy import ndimage as ndi
    if not CT.exists():
        print(f"missing {CT} (scripts/cryo/vhf_skin_and_depth.sh restacks it)"); return 1
    A_img = nib.load(TASK / "vhf_abdominal_muscles.nii.gz"); A_full = np.asarray(A_img.dataobj).astype(np.uint8)
    sp = tuple(float(x) for x in np.sqrt((A_img.affine[:3, :3] ** 2).sum(0)))
    bb = ndi.find_objects(np.isin(A_full, list(IO.values())).astype(np.uint8))[0]
    sl = tuple(slice(max(s.start - 25, 0), min(s.stop + 25, n)) for s, n in zip(bb, A_full.shape))
    A = A_full[sl].copy()
    T = np.asarray(nib.load(TASK / "vhf_total.nii.gz").dataobj)[sl].astype(np.uint8)
    ct_img = nib.load(CT); assert np.allclose(ct_img.affine, A_img.affine), "CT grid differs from the label grid"
    hu = ndi.median_filter(np.asarray(ct_img.dataobj)[sl].astype(np.int16), size=3)
    occupied = (T > 0) | (A > 0); muscle = (hu > MUSCLE_HU[0]) & (hu < MUSCLE_HU[1]); del T, hu
    centre = ring_centres(np.isin(A, WALL)); vml = float(np.prod(sp)) / 1000
    out = np.zeros(A_full.shape, np.uint8); stats = {}
    for side, lab in IO.items():
        io = A == lab
        m = deep_band(io, occupied, muscle, centre, sp, min_vox=int(MIN_CC_ML / vml))
        sub = out[sl]; sub[m & (sub == 0)] = LAB[side]
        lab_, n = ndi.label(m, np.ones((3, 3, 3), bool)); sz = np.sort(ndi.sum(m, lab_, range(1, n + 1)))[::-1] if n else [0]
        stats[side] = {"voxels": int(m.sum()), "volume_cm3": round(float(m.sum() * vml), 1),
                       "io_label_cm3": round(float(io.sum() * vml), 1), "components": int(n),
                       "largest_frac": round(float(sz[0] / max(m.sum(), 1)), 3)}
        print(side, stats[side], flush=True)
    nib.save(nib.Nifti1Image(out, A_img.affine, A_img.header), OUT_VOL)
    KEY.write_text(json.dumps({
        "_README": ["Label id -> structure name for the Visible Human FEMALE transversus abdominis volume (scripts/transversus_from_ct_q185f2.py, Q185f2), plus the mapping onto atlas entities.",
                    "A KEY, not data. Rule-based on her own CT: the unlabelled muscle-density (-30..150 HU, 3x3x3 median) band within 6 mm DEEP to her TotalSegmentator internal-oblique label, outside every total / abdominal_muscles label; components reaching the 1.5 mm layer, >= 1 cm3. TS has no transversus class. Badge it."],
        "source": "U.S. National Library of Medicine, The Visible Human Project (public domain), female fresh-cadaver 'Normal' CT via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 `total` + `abdominal_muscles` labels. Rule from Standring S (ed.), Gray's Anatomy, 42nd ed., 'Anterior abdominal wall' (TA lies immediately deep to IO).",
        "task": "vhf_transversus", "version": "2026-10-01",
        "labels": {"1": "transversus_right", "2": "transversus_left"},
        "atlas": {f"transversus_{s}": {"atlas_id": AID[s], "relationship": "exact",
                                        "note": "Rule-based (muscle-density band deep to her own IO label); Q185f2."} for s in IO}}, indent=1))
    MAPPING.write_text(json.dumps({
        "_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                    "'status' is advisory; convert reads 'atlas_id' only."],
        "subject": SUBJ, "source_volume": str(OUT_VOL), "label_map": "vhf_transversus",
        "entries": [{"label": LAB[s], "source_structure": f"transversus_{s}", "side": s, "status": "curated", "atlas_id": AID[s],
                     "relationship": "exact", "note": f"{stats[s]['volume_cm3']} cm3; rule-based (see _README of the label key)",
                     "candidates": []} for s in IO]}, indent=1))
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    rep.update({"_README": (__doc__ or "").strip().splitlines(), "build": stats, "rule": {"shell_mm": SHELL_MM, "seed_mm": SEED_MM,
                "min_component_cm3": MIN_CC_ML, "muscle_hu": MUSCLE_HU}, "gates": GATES})
    REPORT.write_text(json.dumps(rep, indent=1))
    print(f"wrote {OUT_VOL.relative_to(REPO)}")
    return 0


# ---------------------------------------------------------------- gate
def _mesh(sub: str, aid: str):
    from scripts.placement_sweep_q185 import FullRes
    import trimesh
    g = FullRes().get(sub, aid)
    return None if g is None else trimesh.Trimesh(g[0].astype(np.float64), g[1], process=False)


def gate() -> int:
    import trimesh
    from scipy.spatial import cKDTree
    import scripts.placement_sweep_q185 as S
    B = S.Body("vhf"); rep = json.loads(REPORT.read_text()); rows = {}
    wall = {k: _mesh(s, k) for s, k in [("ct_vhf_abd", "internal_oblique_r"), ("ct_vhf_abd", "internal_oblique_l"),
                                         ("ct_vhf_abd_contfix_mesh", "external_oblique_r"), ("ct_vhf_abd_contfix_mesh", "external_oblique_l")]}
    for side, aid in AID.items():
        s = side[0]; io, eo = wall[f"internal_oblique_{s}"], wall[f"external_oblique_{s}"]
        for route, sub in (("a_own_ct", SUBJ), ("c_transfer_shipped", "xfer_vhm2vhf_tva")):
            t = _mesh(sub, aid)
            if t is None:
                continue
            v = t.vertices; r = S.measure(B, aid, {"cat": "muscle"}, v)
            pts = r["_pts"]
            ins_io = float(io.contains(pts).mean()); ins_eo = float(eo.contains(pts).mean())
            dt, j = cKDTree(io.vertices).query(pts)
            ds = B.skin_tree.query(pts)[0]; dio = B.skin_tree.query(io.vertices[j])[0]
            parts = t.split(only_watertight=False); pv = sorted((len(p.vertices) for p in parts), reverse=True)
            row = {k: r.get(k) for k in ("outside_skin_frac", "in_bone_gt1mm_frac", "in_lung_gt1mm_frac", "in_organ_gt1mm_frac",
                                         "in_organ_top")}
            row.update({"inside_io_frac": round(ins_io, 4), "inside_eo_frac": round(ins_eo, 4),
                        "deeper_than_io_frac": round(float((ds > dio).mean()), 4), "to_io_median_mm": round(float(np.median(dt)), 2),
                        "volume_cm3": round(abs(float(t.volume)) / 1000, 1), "watertight": bool(t.is_watertight),
                        "largest_piece_frac": round(pv[0] / sum(pv), 3), "pieces": len(pv), "triangles": int(len(t.faces)),
                        "io_volume_cm3": round(abs(float(io.volume)) / 1000, 1), "eo_volume_cm3": round(abs(float(eo.volume)) / 1000, 1)})
            row["vs_io"] = round(row["volume_cm3"] / row["io_volume_cm3"], 2); row["vs_eo"] = round(row["volume_cm3"] / row["eo_volume_cm3"], 2)
            row["fails"] = [k for k, lim in GATES.items() if row.get(k) is not None and
                            ((row[k] < lim) if k == "deeper_than_io_frac" else (row[k] > lim))]
            row["pass"] = not row["fails"]
            rows.setdefault(aid, {})[route] = row
            print(aid, route, {k: row[k] for k in ("in_organ_gt1mm_frac", "in_bone_gt1mm_frac", "in_lung_gt1mm_frac", "outside_skin_frac",
                                                   "inside_io_frac", "inside_eo_frac", "deeper_than_io_frac", "volume_cm3", "vs_io",
                                                   "vs_eo", "largest_piece_frac", "fails")}, flush=True)
    rep["structures"] = rows
    rep["route_b"] = "her abdominal cryosection photographs are not local (only QC PNGs of limb/neck/pelvic tasks) -> not used"
    rep["route_a_label_check"] = "TS abdominal_muscles v2.18.0 has no transversus class (labels 1-22); TA derived from her IO label + her CT"
    rep["published_volume"] = ("none found: Rankin 2006 (doi:10.1002/mus.20589) gives ultrasound thickness order RA > IO > EO > TA only; "
                               "Izumoto 2019 (doi:10.1371/journal.pone.0214752), Sanchis-Moysi 2013 (doi:10.1080/14763141.2012.725087) "
                               "report the lateral wall (obliques + TA) together")
    REPORT.write_text(json.dumps(rep, indent=1))
    return 0


def stamp() -> int:
    rep = json.loads(REPORT.read_text()); mf = REPO / "build" / "vh" / SUBJ / "manifest.json"
    m = json.loads(mf.read_text())
    held = [a for a, r in rep["structures"].items() if not r["a_own_ct"]["pass"]]
    if held:                                  # not stamped -> vhf_rebuild_bundle.sh does not list the subject
        print("HELD (gate fails):", {a: rep["structures"][a]["a_own_ct"]["fails"] for a in held}); return 1
    for s in m["structures"]:
        r = rep["structures"][s["atlas_id"]]["a_own_ct"]; c = rep["structures"][s["atlas_id"]].get("c_transfer_shipped", {})
        s["procedural_badge"] = (
            f"RULE-BASED (Q185f2, 2026-10-01): from HER OWN CT -- the unlabelled muscle-density band (-30..150 HU) within "
            f"{SHELL_MM:g} mm deep to her own TotalSegmentator internal-oblique label (TS has no transversus class), outside "
            f"every labelled organ / bone / muscle. {r['volume_cm3']} cm3 ({r['vs_io']} x her IO, {r['vs_eo']} x her EO; no "
            f"published TA volume found); {100 * r['in_organ_gt1mm_frac']:.1f} % > 1 mm in her organs, "
            f"{100 * r['in_bone_gt1mm_frac']:.1f} % in bone, {100 * r['outside_skin_frac']:.0f} % outside skin, "
            f"{100 * r['inside_io_frac']:.1f} % inside her IO, {100 * r['deeper_than_io_frac']:.0f} % deeper than her IO. "
            f"Replaces his cryosection TA carried across by the bone-driven transfer "
            f"({100 * c.get('in_organ_gt1mm_frac', 0):.0f} % in her organs). Thin layer (CT shows 2-4 mm); "
            f"the aponeurosis and the part beyond her IO label are not modelled.")
        s["geometry_source"] = "Q185f2 own-CT band deep to IO"
        s.pop("hidden_default", None)
    m["attribution"] = ["Q185f2: transversus abdominis from her own CT (scripts/transversus_from_ct_q185f2.py)."]
    mf.write_text(json.dumps(m, indent=2))
    print("stamped", [s["atlas_id"] for s in m["structures"]])
    return 0


def montage() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = SCRATCH / "q185f2c2" / "montage_abdominal_wall_before_after.png"; out.parent.mkdir(parents=True, exist_ok=True)
    import scripts.placement_sweep_q185 as S
    B = S.Body("vhf")
    meshes = {"EO": [_mesh("ct_vhf_abd_contfix_mesh", f"external_oblique_{s}") for s in "rl"],
              "IO": [_mesh("ct_vhf_abd", f"internal_oblique_{s}") for s in "rl"],
              "TA before (his, transferred)": [_mesh("xfer_vhm2vhf_tva", a) for a in AID.values()],
              "TA after (her own CT)": [_mesh(SUBJ, a) for a in AID.values()]}
    col = {"EO": "#d62728", "IO": "#ff7f0e", "TA before (his, transferred)": "#7f7f7f", "TA after (her own CT)": "#1f77b4"}
    import trimesh
    ta = trimesh.util.concatenate([m for m in meshes["TA after (her own CT)"] if m is not None])
    ys = np.percentile(ta.vertices[:, 1], [25, 50, 75])
    fig, ax = plt.subplots(2, 3, figsize=(18, 11))
    for row, which in enumerate(("TA before (his, transferred)", "TA after (her own CT)")):
        for c, y in enumerate(ys):
            a = ax[row, c]
            # her organs (liver/kidney/bowel ...) at that level from her labels: sampled on a grid
            xs, zs = np.meshgrid(np.arange(-200, 200, 2.0), np.arange(-180, 180, 2.0))
            P = np.c_[xs.ravel(), np.full(xs.size, y), zs.ravel()]
            lab = S.label_at(B.tot, B.A, B.O, P).reshape(xs.shape)
            org = np.isin(lab, list(S.ORGANS)); bone = np.isin(lab, list(S.BONE))
            a.imshow(np.where(org, 0.75, np.where(bone, 0.45, 1.0)), cmap="gray", vmin=0, vmax=1, origin="lower",
                     extent=(-200, 200, -180, 180))
            for name in ("EO", "IO", which):
                for m in meshes[name]:
                    if m is None:
                        continue
                    sec = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
                    if sec is None:
                        continue
                    for e in sec.discrete:
                        a.plot(e[:, 0], e[:, 2], color=col[name], lw=1.2)
            a.set_title(f"{which} -- y = {y:.0f} mm", fontsize=10)
            a.set_aspect("equal"); a.set_xlim(-200, 200); a.set_ylim(-180, 180)
    handles = [plt.Line2D([], [], color=c, label=n) for n, c in col.items()]
    fig.legend(handles=handles + [plt.Rectangle((0, 0), 1, 1, color="0.75", label="her organ labels"),
                                  plt.Rectangle((0, 0), 1, 1, color="0.45", label="her bone labels")], loc="lower center", ncol=6)
    fig.suptitle("Q185f2 -- her abdominal wall layers (axial sections; x right, z anterior): TA before = his TA transferred, "
                 "after = her own CT band deep to IO")
    fig.savefig(out, dpi=80); print(out); return 0


def main(argv=None) -> int:
    cmd = (argv or sys.argv[1:] or ["build"])[0]
    return {"build": build, "gate": gate, "stamp": stamp, "montage": montage}[cmd]()


if __name__ == "__main__":
    sys.exit(main())
