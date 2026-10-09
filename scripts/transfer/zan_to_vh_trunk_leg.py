"""Q62 step 9: the remaining TRUNK and small LOWER-LIMB muscle gaps on BOTH own-model bodies (VH female `--target vhf`,
VH male `--target vhm`), TRANSFERRED from Z-Anatomy onto each body's own skeleton.

Same route and gates as Q62 steps 5 / 7 / 7b (zan_to_vhf_foot_intrinsics.py, zan_to_vhf_head_neck.py, whose helpers
this reuses): Z-Anatomy (CC BY-SA 4.0) objects carried by the Q168 per-bone fits (zan_to_vhf_whole_body, onto her or
his own bones), then measured and fixed per muscle:
  carrier  LOCAL error: Z-Anatomy bone surface within LOCAL_MM of the muscle (axial units for the trunk, lower_<side>
           units for the leg), carried by its own piece fit, vs her CT bone surface; held if the muscle's or its
           group's pooled median > MAX_CARRIER_MM.
  bone     vertices inside her bones: trunk = spine (C1-S5) / ribs / sternum / clavicles / scapulae / hip bones
           RE-MESHED from her (his) own TotalSegmentator `total` labels (the bundle rib meshes are not watertight on
           either body: her ribs_r probe reads 60 % inside at 1 mm depth); leg = her bundle femur / patella / tibia /
           fibula / foot bones (watertight enough: 1 mm-in probe 96-100 %, 3 mm-out 0-7 %). Bounded push-out
           (<= PUSH_BOUND_MM deep -> surface + 1 mm); > MAX_INSIDE_BONE still inside -> held.
  skin     her ct_<body>_skin: > MAX_OUTSIDE_SKIN_PRECLIP outside before -> failed fit; pull_inside_skin; 0 % after.
           Thin sheets (intercostals): skin pull moving > MAX_SKIN_MOVED of the vertices, or fixes keeping
           < MIN_VOL_KEPT of the transferred volume -> held (deformed, not fitted).
  lung     vertices inside her lung labels (total 10-14; no pleura label exists): > MAX_IN_LUNG -> held.
  overlap  vertices inside her existing bundle muscles (any subject) + her organ labels (heart, liver, spleen,
           kidneys, stomach, aorta, oesophagus), plus the EXCESS over Z-Anatomy's own overlap of vertices inside the
           other new muscles (intercostal layers touch in the source itself): > MAX_OVERLAP -> held.
Only ids from data/muscles/{trunk,lower_limb} that the body's bundle lacks; NOT_BUILDABLE says why the rest are not
built; dartos / cremaster are male-only and never targeted on her. Output subject xfer_zan2vhf_trunk /
xfer_zan2vhm_trunk, report data/derived/Q62s9_<vhf|vhm>_trunk_leg.json.

    python3 scripts/transfer/zan_to_vh_trunk_leg.py --target vhf|vhm [--out DIR] [--report JSON] [--dry]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.transfer import zan_to_vhf_whole_body as Z  # noqa: E402
from scripts.transfer import zan_to_vhf_foot_intrinsics as FT  # noqa: E402
from scripts.transfer import zan_to_vhf_head_neck as HN  # noqa: E402

MAX_INSIDE_BONE = 0.05
MAX_OUTSIDE_SKIN_PRECLIP = 0.5
MAX_CARRIER_MM = 3.0
MAX_OVERLAP = 0.10
MAX_IN_LUNG = 0.05
MAX_SKIN_MOVED = HN.MAX_SKIN_MOVED
MIN_VOL_KEPT = HN.MIN_VOL_KEPT
LOCAL_MM = HN.LOCAL_MM
_S = "rl"

# shared region table: group -> bases (ids = <base>_<side>), the Q168 unit groups that carry/measure it, bone set.
# Groups follow the bones that carry them (the pooled carrier gate): spine-borne transversospinal/segmental muscles
# vs the rib-borne posterior wall (levatores costarum insert on the ribs, like the serratus posterior muscles).
REGIONS = {
    "deep_back": {"bases": ["interspinales", "intertransversarii", "rotatores", "semispinalis_thoracis"],
                  "units": "axial", "bones": "trunk"},
    "posterior_thoracic_wall": {"bases": ["levatores_costarum", "serratus_posterior_superior",
                                          "serratus_posterior_inferior"], "units": "axial", "bones": "trunk"},
    "chest_wall": {"bases": ["internal_intercostals", "innermost_intercostals", "transversus_thoracis",
                             "subclavius"], "units": "axial", "bones": "trunk"},
    "abdominal_wall": {"bases": ["pyramidalis"], "units": "axial", "bones": "trunk"},
    "leg": {"bases": ["fibularis_brevis", "fibularis_tertius"], "units": "lower", "bones": "leg"},
}
GROUP_OF = {f"{b}_{s}": g for g, r in REGIONS.items() for b in r["bases"] for s in _S}
# atlas id -> Z-Anatomy mesh ids where not the atlas id itself (orphan pool of the Z-Anatomy build)
ORPHAN = {**{f"internal_intercostals_{s}": [f"zan_internal_intercostal_muscles_{s}"] for s in _S},
          **{f"innermost_intercostals_{s}": [f"zan_innermost_intercostal_muscles_{s}"] for s in _S},
          **{f"intertransversarii_{s}": [f"zan_dorsal_parts_of_lateral_intertransversarii_lumborum_muscles_{s}",
                                         f"zan_ventral_parts_of_lateral_intertransversarii_lumborum_muscles_{s}"]
             for s in _S}}
PARTIAL_NOTE = {f"intertransversarii_{s}": "lateral lumbar intertransversarii only (dorsal + ventral parts); Z-Anatomy "
                "has no cervical, thoracic or medial lumbar intertransversarii" for s in _S}
_NO_ZAN = "no CC BY-SA Z-Anatomy object of this name (inventory + name map searched by name)"
NOT_BUILDABLE = {
    **{f"cremaster_{s}": _NO_ZAN for s in _S}, "dartos": _NO_ZAN,
    **{f"subcostales_{s}": _NO_ZAN + " ('Subcostal artery/vein' are vessels)" for s in _S},
    **{f"superficial_transverse_perineal_{s}": _NO_ZAN for s in _S},
    **{f"articularis_genus_{s}": "Z-Anatomy has only its attachment-area markers on the femur ('Articularis genus "
       "muscle.o<s>', Skeletal system), no muscle object" for s in _S},
}
MALE_ONLY = {"dartos", "cremaster_r", "cremaster_l"}
# trunk bones re-meshed from the body's own TotalSegmentator `total` labels
TRUNK_CT_BONES = {"spine": ("total", list(range(25, 51))), "ribs_r": ("total", list(range(104, 116))),
                  "ribs_l": ("total", list(range(92, 104))), "sternum": ("total", [116]),
                  "clavicle_r": ("total", [74]), "clavicle_l": ("total", [73]), "scapula_r": ("total", [72]),
                  "scapula_l": ("total", [71]), "hip_bone_r": ("total", [78]), "hip_bone_l": ("total", [77])}
LEG_BONES = ["femur", "patella", "tibia", "fibula", "talus", "calcaneus", "navicular", "cuboid", "cuneiform_medial",
             "cuneiform_intermediate", "cuneiform_lateral", "metatarsals", "phalanges_foot"]
ORGANS = {"heart": [51], "liver": [5], "spleen": [1], "kidneys": [2, 3], "stomach": [6], "aorta": [52],
          "oesophagus": [15]}
LUNG, COSTAL_CARTILAGE = list(range(10, 15)), [117]
CARRIER = {"trunk": "her own spine, ribs, sternum, shoulder girdle and pelvis", "leg": "her own tibia, fibula and foot bones"}
# published adult volumes (cm3) where a value could be read; everything else: none found (report says so)
PUBLISHED: dict = {}
PUBLISHED_NOTE = (
    "No per-muscle adult volume could be read for any of these muscles (PubMed searched 2026-10-01). Fibularis brevis: "
    "Jeng CL et al. Foot Ankle Int 2012;33(5):394-9 (doi:10.3113/FAI.2012.0394, 3T MRI, n=10) measured it but the "
    "abstract gives no value; Ward SR et al. Clin Orthop Relat Res 2009;467(4):1074-82 (doi:10.1007/s11999-008-0594-8, "
    "cadaver masses) -- PMC full text came back empty; Handsfield GG et al. J Biomech 2014;47(3):631-8 "
    "(doi:10.1016/j.jbiomech.2013.12.002) pools the peroneals. Fibularis tertius, subclavius, pyramidalis, serratus "
    "posterior, transversus thoracis, intercostals and the deep back muscles: none found. Rows compare with the "
    "Z-Anatomy source only, so no SIZE CAVEAT can trigger.")
TARGETS = {t: {"subject": f"xfer_zan2{t}_trunk", "report": REPO / "data" / "derived" / f"Q62s9_{t}_trunk_leg.json",
               "bundle": HN.TARGETS[t]["bundle"], "q168": HN.TARGETS[t]["q168"], "origin": HN.TARGETS[t]["origin"]}
           for t in ("vhf", "vhm")}


def entity_ids() -> list[str]:
    return sorted(p.stem for d in ("trunk", "lower_limb") for p in (REPO / "data" / "muscles" / d).glob("*.json"))


def targets(target: str, have: set) -> list[str]:
    """buildable ids (REGIONS) that the body's bundle lacks, in region order"""
    ents = set(entity_ids())
    return [a for a in GROUP_OF if a in ents and a not in have]


def not_built(target: str, have: set) -> dict:
    ents = set(entity_ids())
    out = {a: why for a, why in NOT_BUILDABLE.items() if a in ents and a not in have
           and not (target == "vhf" and a in MALE_ONLY)}
    if target == "vhf":
        out.update({a: "male-only structure: never built on the female" for a in sorted(MALE_ONLY) if a in ents})
    return out


def zan_parts(aid: str) -> list[str]:
    return ORPHAN.get(aid, [aid])


def pron(text, target: str):
    if target == "vhf" or text is None:
        return text
    for a, b in ((r"segmented from her\b", "segmented from him"), (r"\bher\b", "his"), (r"\bHER\b", "HIS"),
                 (r"\bshe\b", "he"), (r"VH female", "VH male"), (r"zanatomy -> vhf", "zanatomy -> vhm")):
        text = re.sub(a, b, text)
    return text


def hits(v: np.ndarray, meshes) -> dict:
    """{name: share of v inside mesh} over (name, trimesh) pairs whose box meets v's box"""
    lo, hi = v.min(0), v.max(0); out = {}
    for k, m in meshes:
        if np.all(m.bounds[0] <= hi) and np.all(m.bounds[1] >= lo):
            n = int(m.contains(v).sum())
            if n:
                out[k] = round(n / len(v), 4)
    return out


class LabelLookup(HN.MaskLookup):
    """HN.MaskLookup over ONE shared uint8 label array (labels tested at query time: no bool mask per organ)"""

    def __init__(self, lab: np.ndarray, labels: list, affine: np.ndarray, origin: np.ndarray):
        self.m, self.labels, self.A, self.O = lab, labels, affine, origin

    def __call__(self, pts: np.ndarray) -> np.ndarray:
        ijk = np.rint(HN.to_vox(pts, self.A, self.O)).astype(int)
        ok = np.all((ijk >= 0) & (ijk < np.array(self.m.shape)), axis=1)
        out = np.zeros(len(pts), bool)
        out[ok] = np.isin(self.m[ijk[ok, 0], ijk[ok, 1], ijk[ok, 2]], self.labels)
        return out


def label_lookups(target: str, origin: np.ndarray) -> dict:
    import nibabel as nib
    img = nib.load(HN.TASK / f"{target}_total.nii.gz"); tot = np.asarray(img.dataobj).astype(np.uint8)
    looks = {k: LabelLookup(tot, labs, img.affine, origin) for k, labs in ORGANS.items()}
    looks["lung"] = LabelLookup(tot, LUNG, img.affine, origin)
    looks["costal_cartilage"] = LabelLookup(tot, COSTAL_CARTILAGE, img.affine, origin)
    return looks


def volume_cm3(v: np.ndarray, f: np.ndarray) -> tuple[float, str]:
    """Closed mesh: exact enclosed volume. Open mesh (the Z-Anatomy internal intercostals, levatores costarum): voxel
    fill of a dense surface sample at 0.5 mm (1 mm for a box > 1.5e8 half-mm voxels) -- FT.voxel_volume_cm3's
    subdivision blows up (> 14 GB) on the 25 mm-edged whole-thorax sheets."""
    from scipy import ndimage as ndi
    m = trimesh.Trimesh(v, f, process=False)
    if m.is_watertight:
        return abs(float(m.volume)) / 1000.0, "closed mesh"
    lo = v.min(0) - 2; pitch = 0.5 if np.prod(np.ptp(v, axis=0) + 4) / 0.125 < 1.5e8 else 1.0
    pts = trimesh.sample.sample_surface(m, int(m.area / (pitch * pitch / 8)) + 1000, seed=3)[0]
    ijk = np.floor((pts - lo) / pitch).astype(int); g = np.zeros(ijk.max(0) + 3, bool)
    g[ijk[:, 0] + 1, ijk[:, 1] + 1, ijk[:, 2] + 1] = True
    return float(ndi.binary_fill_holes(g).sum() * pitch ** 3 / 1000.0), f"open mesh: voxel fill at {pitch} mm"


def write_subject(out: Path, ids: list, meshes: dict, rows: dict, T: str, report_name: str) -> None:
    """build/vh subject (vertices.f32 / faces.u32 / manifest.json); a held row's badge is its HELD reason"""
    out.mkdir(parents=True, exist_ok=True)
    verts, faces, structs, voff, foff = [], [], [], 0, 0
    for aid in ids:
        v, f = meshes[aid]; v32 = v.astype(np.float32)
        structs.append({"atlas_id": aid, "source_structure": "+".join(rows[aid]["zanatomy_mesh_ids"]),
                        "side": "right" if aid.endswith("_r") else "left",
                        "source_file": "zanatomy#" + "+".join(rows[aid]["zanatomy_objects"]),
                        "vertex_offset": voff, "face_offset": foff, "vertex_count": int(len(v32)),
                        "triangle_count": int(len(f)), "bbox_min_mm": [round(float(x), 4) for x in v32.min(0)],
                        "bbox_max_mm": [round(float(x), 4) for x in v32.max(0)],
                        "procedural_badge": rows[aid].get("badge") or f"HELD (not shipped): {rows[aid]['dropped']}",
                        "transfer": {"from": "zanatomy", "method": f"Q168 per-bone fit (zan_to_vhf_whole_body --target {T})",
                                     "rides_on": rows[aid]["rides_on"]["bones"][:3]}})
        verts.append(v32); faces.append((f + voff).astype(np.uint32)); voff += len(v32); foff += len(f)
    V = np.concatenate(verts); F = np.concatenate(faces)
    V.tofile(out / "vertices.f32"); F.tofile(out / "faces.u32")
    attribution = [pron(
        "GENERIC MODEL, NOT SEGMENTED FROM THIS SPECIMEN: trunk and small lower-limb muscles from Z-Anatomy (CC BY-SA "
        "4.0), fitted onto this specimen's OWN spine, ribs, sternum, shoulder girdle, pelvis and leg bones one bone at a "
        "time (Q168 per-bone similarity fits); pushed off her bones and pulled inside her skin "
        "(scripts/transfer/zan_to_vh_trunk_leg.py, Q62 step 9). Only ids she had no mesh for. Per-muscle badge gives "
        f"the measured fit error of the bone around it; data/derived/{report_name} has every gate number.", T),
        "Z-Anatomy: models by the Z-Anatomy project (BodyParts3D upstream credited in its own LICENSE), app by "
        "Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. "
        "Licensed CC BY-SA 4.0; this registered derivative remains CC BY-SA 4.0 (ShareAlike)."]
    man = {"subject": out.name, "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
           "source_volume": None, "source_kind": f"cross-subject transfer zanatomy -> {T} (Q168 per-bone fit)",
           "vertex_count": int(len(V)), "triangle_count": int(len(F)),
           "bbox_min_mm": [round(float(x), 4) for x in V.min(0)], "bbox_max_mm": [round(float(x), 4) for x in V.max(0)],
           "attribution": attribution, "license": "CC-BY-SA-4.0", "structures": structs}
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    print(f"{out.name}: {len(structs)} structures, {len(V)} vertices, {len(F)} triangles")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=sorted(TARGETS), required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--dry", action="store_true", help="measure and report only; write no subject")
    ap.add_argument("--candidates", default=None, metavar="DIR",
                    help="also write every built row (shipped AND held, after the fixes) as a subject here, for inspection")
    ap.add_argument("--q168", default=None, help="Q168 bone-fit report to carry with (default: the target's Q168 report; "
                                                 "Q182 passes a refit onto the label-derived ribs)")
    a = ap.parse_args(argv)
    T = a.target; cfg = dict(TARGETS[T]); SUBJ = cfg["subject"]
    if a.q168:
        cfg["q168"] = Path(a.q168).resolve()
    a.out = a.out or str(REPO / "build" / "vh" / SUBJ)
    a.report = a.report or str(cfg["report"])
    O = np.array([float(x) for x in cfg["origin"].split(",")])

    bundle = json.loads(Path(cfg["bundle"]).read_text())
    have = {e["id"] for e in bundle["structures"] if e["subject"] != SUBJ}
    tg = targets(T, have); skipped = not_built(T, have)
    rep168 = json.loads(Path(cfg["q168"]).read_text())
    fits = Z.fits_from_json(rep168["bone_fits"])
    need = {p for fr in fits.values() if fr.get("status") == "fitted" for p in fr["pieces"]}
    items = {it["mesh_id"]: it for it in Z.collect_zan(ids={z for t in tg for z in zan_parts(t)} | need)}
    xf = Z.load_zan_to_vhf(zan_meshes=items, report_path=cfg["q168"])
    order = [s for s in bundle["subject"].split("+") if s != SUBJ]
    her_all = Z.load_her_meshes(order=order, bundle_json=cfg["bundle"])
    skin = her_all["skin"]; skin_mesh = trimesh.Trimesh(skin["v"], skin["f"], process=False)
    looks = label_lookups(T, O)
    bone_sets = {"trunk": HN.ct_bone_meshes(T, O, TRUNK_CT_BONES)}
    for s in _S:
        bone_sets[f"leg_{s}"] = {f"{b}_{s}": trimesh.Trimesh(her_all[f"{b}_{s}"]["v"], her_all[f"{b}_{s}"]["f"])
                                 for b in LEG_BONES if f"{b}_{s}" in her_all}
    trees = {k: cKDTree(np.vstack([Z.sample_surface(m.vertices, m.faces, 20000, seed=1) for m in bs.values()]))
             for k, bs in bone_sets.items()}

    t0 = time.time(); print(f"setup done, {len(tg)} targets", flush=True)
    rows, out_mesh, src_mesh, dropped, cand_mesh = {}, {}, {}, {}, {}
    pooled = {g: [] for g in REGIONS}
    for aid in tg:
        g = GROUP_OF[aid]; reg = REGIONS[g]; side = aid[-1]
        parts = [z for z in zan_parts(aid) if z in items]
        if not parts:
            dropped[aid] = f"no Z-Anatomy object {zan_parts(aid)}"; continue
        vs, fs, off = [], [], 0
        for z in parts:
            vs.append((items[z]["v"], xf(z, items[z]["cat"], items[z]["v"]))); fs.append(items[z]["f"] + off)
            off += len(items[z]["v"])
        v_src = np.vstack([p[0] for p in vs]); nv = np.vstack([p[1] for p in vs]); f = np.vstack(fs)
        bkey = "trunk" if reg["bones"] == "trunk" else f"leg_{side}"
        ugroups = ("axial",) if reg["units"] == "axial" else (f"lower_{side}",)
        lo, hi = nv.min(0) - 5, nv.max(0) + 5
        near = {b: m for b, m in bone_sets[bkey].items() if np.all(m.bounds[0] <= hi) and np.all(m.bounds[1] >= lo)}
        in_bone = np.zeros(len(nv), bool); per_bone = {}
        for b, m in near.items():
            ins = m.contains(nv); in_bone |= ins
            if ins.any():
                per_bone[b] = round(float(ins.mean()), 4)
        frac_out = float((~skin_mesh.contains(nv)).mean()); od = FT.outside_depth(nv, skin_mesh)
        ride = FT.rides_on(xf, fits, v_src, side, groups=ugroups)
        loc = HN.local_carrier_error(xf, v_src, trees[bkey], groups=ugroups)
        pooled[g].append(loc.pop("d"))
        nv2, n_push, n_deep = FT.bounded_push_off_bones(nv, list(near.values()))
        in_bone_p = np.zeros(len(nv2), bool)
        for m in near.values():
            in_bone_p |= m.contains(nv2)
        nv3, n_clip = FT.pull_inside_skin(nv2, skin_mesh)
        skin_moved = float((np.linalg.norm(nv3 - nv2, axis=1) > 0).mean())
        in_bone2 = np.zeros(len(nv3), bool)
        for m in near.values():
            in_bone2 |= m.contains(nv3)
        mv = np.linalg.norm(nv3 - nv, axis=1)
        (vol_src, vmeth), (vol_x, _), (vol_out, _) = (volume_cm3(x, f) for x in (v_src, nv, nv3))
        lab = {k: round(float(fn(nv3).mean()), 4) for k, fn in looks.items()}
        depth = skin_mesh.nearest.on_surface(Z._sub(nv3, 600, 6))[1]
        rows[aid] = row = {
            "atlas_id": aid, "group": g, "zanatomy_objects": [items[z]["name"] for z in parts],
            "zanatomy_mesh_ids": parts, "partial": PARTIAL_NOTE.get(aid), "vertices": int(len(nv)),
            "triangles": int(len(f)), "inside_bone_frac_before": round(float(in_bone.mean()), 4),
            "inside_bone_by_bone": per_bone, "outside_skin_frac_before": round(frac_out, 4),
            "outside_skin_depth_mm": {"p95": round(float(np.percentile(od, 95)), 2) if len(od) else 0.0,
                                      "max": round(float(od.max()), 2) if len(od) else 0.0},
            "pushed_off_bone": n_push, "inside_bone_deeper_than_bound": n_deep,
            "inside_bone_frac_after_push": round(float(in_bone_p.mean()), 4), "rides_on": ride, "carrier_local": loc,
            "clipped_to_skin": n_clip, "skin_moved_frac": round(skin_moved, 4),
            "fix_move_mm": {"p95": round(float(np.percentile(mv, 95)), 2), "max": round(float(mv.max()), 2)},
            "inside_bone_frac_after": round(float(in_bone2.mean()), 4),
            "outside_skin_frac_after": round(float((~skin_mesh.contains(nv3)).mean()), 4),
            "inside_label_frac": lab, "inside_lung_frac": lab["lung"],
            "depth_under_skin_mm": {"min": round(float(depth.min()), 1), "median": round(float(np.median(depth)), 1)},
            "volume_method": vmeth, "volume_zanatomy_cm3": round(vol_src, 2), "volume_transferred_before_fix_cm3": round(vol_x, 2),
            "volume_cm3": round(vol_out, 2), "volume_ratio_vs_zanatomy": round(vol_out / vol_src, 3),
            "volume_kept_after_fix": round(vol_out / vol_x, 3) if vol_x else None}
        why = None
        if in_bone_p.mean() > MAX_INSIDE_BONE:
            why = (f"{in_bone_p.mean():.1%} of vertices still inside her bone after the bounded push-out "
                   f"(> {MAX_INSIDE_BONE:.0%}; {in_bone.mean():.1%} before)")
        elif frac_out > MAX_OUTSIDE_SKIN_PRECLIP:
            why = f"{frac_out:.0%} of vertices outside her skin before the fix (failed fit)"
        elif skin_moved > MAX_SKIN_MOVED:
            why = f"thin sheet: the skin pull drags {skin_moved:.0%} of its vertices (> {MAX_SKIN_MOVED:.0%})"
        elif vol_x and vol_out / vol_x < MIN_VOL_KEPT:
            why = f"the fixes leave {vol_out / vol_x:.0%} of its transferred volume (< {MIN_VOL_KEPT:.0%})"
        elif loc["median_mm"] is None or loc["median_mm"] > MAX_CARRIER_MM:
            why = f"bone around it fits her CT at {loc['median_mm']} mm median (> {MAX_CARRIER_MM} mm)"
        elif lab["lung"] > MAX_IN_LUNG:
            why = f"{lab['lung']:.1%} of vertices inside her lung (> {MAX_IN_LUNG:.0%})"
        print(f"  {aid}: bone {in_bone.mean():.3f}->{in_bone_p.mean():.3f} skin_out {frac_out:.3f} carrier "
              f"{loc['median_mm']} lung {lab['lung']:.3f} vol {vol_out:.2f}/{vol_x:.2f} ({time.time() - t0:.0f} s)"
              + (f" HELD: {pron(why, T)}" if why else ""), flush=True)
        cand_mesh[aid] = (nv3, f)
        if why:
            row["dropped"] = dropped[aid] = pron(why, T)
        else:
            out_mesh[aid] = (nv3, f); src_mesh[aid] = (v_src, f)

    group_carrier = {}
    for g, ds in pooled.items():
        d = np.concatenate(ds) if ds else np.zeros(0)
        med = float(np.median(d)) if len(d) else None
        group_carrier[g] = {"median_mm": round(med, 2) if med is not None else None,
                            "p90_mm": round(float(np.percentile(d, 90)), 2) if len(d) else None,
                            "held": bool(len(d) and med > MAX_CARRIER_MM)}
        if group_carrier[g]["held"]:
            for aid in [x for x in out_mesh if GROUP_OF[x] == g]:
                rows[aid]["dropped"] = dropped[aid] = f"group {g}: carrier median {med:.2f} mm > {MAX_CARRIER_MM} mm"
                del out_mesh[aid]

    exist = [(k, trimesh.Trimesh(m["v"], m["f"], process=False)) for k, m in her_all.items() if m.get("cat") == "muscle"]
    tm_new = {k: trimesh.Trimesh(v, f, process=False) for k, (v, f) in out_mesh.items()}
    tm_src = {k: trimesh.Trimesh(v, f, process=False) for k, (v, f) in src_mesh.items()}
    for aid in list(out_mesh):
        v = out_mesh[aid][0]; r = rows[aid]
        ov = hits(v, exist)
        ov.update({f"her_{k}_label": x for k, x in r["inside_label_frac"].items()
                   if x and k not in ("lung", "costal_cartilage")})
        on = hits(v, [(k, m) for k, m in tm_new.items() if k != aid])
        os_ = hits(src_mesh[aid][0], [(k, m) for k, m in tm_src.items() if k != aid])
        her_t, new_t, src_t = sum(ov.values()), sum(on.values()), sum(os_.values())
        r.update({"overlap_her_structures": dict(sorted(ov.items(), key=lambda kv: -kv[1])),
                  "overlap_new_muscles": dict(sorted(on.items(), key=lambda kv: -kv[1])),
                  "overlap_new_muscles_in_zanatomy_source": dict(sorted(os_.items(), key=lambda kv: -kv[1])),
                  "overlap_her_total": round(her_t, 4), "overlap_new_total": round(new_t, 4),
                  "overlap_new_total_source": round(src_t, 4),
                  "overlap_frac_total": round(her_t + max(0.0, new_t - src_t), 4)})
    for aid in list(out_mesh):
        r = rows[aid]
        if r["overlap_frac_total"] > MAX_OVERLAP:
            top = next(iter(r["overlap_her_structures"] or r["overlap_new_muscles"]))
            r["dropped"] = dropped[aid] = pron(
                f"{r['overlap_frac_total']:.1%} of vertices inside other muscles/organs (> {MAX_OVERLAP:.0%}; her "
                f"structures {r['overlap_her_total']:.1%}, new muscles {r['overlap_new_total']:.1%} vs "
                f"{r['overlap_new_total_source']:.1%} in Z-Anatomy itself; mostly {top})", T)
            del out_mesh[aid]

    for aid in out_mesh:
        r = rows[aid]; loc = r["carrier_local"]
        r["badge"] = pron(
            "Q62 step 9: TRANSFERRED, not segmented from her. Z-Anatomy geometry (CC BY-SA 4.0; Z-Anatomy / "
            f"BodyParts3D) fitted onto {CARRIER[REGIONS[r['group']]['bones']]} (Q168 per-bone fits). Not measured on "
            f"this muscle (she has no mesh of it); the bone surface within {LOCAL_MM:.0f} mm of it fits her CT at "
            f"{loc['median_mm']:.1f} mm median (p90 {loc['p90_mm']:.1f} mm). Volume {r['volume_cm3']:.2f} cm3; "
            f"{r['pushed_off_bone']} vertices pushed off her bones, {r['clipped_to_skin']} pulled inside her skin."
            + (f" Partial: {r['partial']}." if r["partial"] else ""), T)
        pub = PUBLISHED.get(re.sub(r"_[rl]$", "", aid), {})
        if pub.get("value_cm3") and r["volume_cm3"] > 1.5 * pub["value_cm3"]:
            r["badge"] += (f" SIZE CAVEAT: {r['volume_cm3'] / pub['value_cm3']:.1f}x the published adult volume "
                           f"({pub['value_cm3']:.1f} cm3, {pub['short']}); treat its bulk as an overestimate.")

    shipped = [x for x in tg if x in out_mesh]
    by_group = {g: {"shipped": [x for x in tg if GROUP_OF[x] == g and x in out_mesh],
                    "held": {x: dropped[x] for x in tg if GROUP_OF[x] == g and x in dropped}} for g in REGIONS}
    doc = {"source": pron("Q62 step 9 (scripts/transfer/zan_to_vh_trunk_leg.py --target vhf): Z-Anatomy trunk and "
                          "small lower-limb muscles (CC BY-SA 4.0) carried onto the VH female's own skeleton (Q168 "
                          f"per-bone fits, {Path(cfg['q168']).relative_to(REPO)}).", T).replace("--target vhf", f"--target {T}"),
           "gates": {"max_inside_bone_frac": MAX_INSIDE_BONE, "max_outside_skin_preclip_frac": MAX_OUTSIDE_SKIN_PRECLIP,
                     "max_carrier_mm": MAX_CARRIER_MM, "max_overlap_frac": MAX_OVERLAP, "max_in_lung_frac": MAX_IN_LUNG,
                     "max_skin_moved_frac": MAX_SKIN_MOVED, "min_volume_kept": MIN_VOL_KEPT,
                     "push_bound_mm": FT.PUSH_BOUND_MM, "local_mm": LOCAL_MM},
           "summary": {"targets": tg, "shipped": shipped, "n_shipped": len(shipped), "dropped": dropped,
                       "by_group": by_group, "group_carrier": group_carrier, "not_built": skipped,
                       "trunk_bones_from_ct_labels": {k: list(v) for k, v in TRUNK_CT_BONES.items()}},
           "published_volumes": PUBLISHED, "published_note": PUBLISHED_NOTE, "rows": rows}
    Path(a.report).write_text(json.dumps(doc, indent=1))
    print(f"report {a.report}: shipped {len(shipped)}, held {len(dropped)}, not built {len(skipped)}")
    if a.candidates:   # every built row (shipped or held), post-fix, for inspection/montage only -- never bundled
        write_subject(Path(a.candidates), [x for x in tg if x in cand_mesh], cand_mesh, rows, T, Path(a.report).name)
    if a.dry or not shipped:
        return 0
    write_subject(Path(a.out), shipped, out_mesh, rows, T, Path(a.report).name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
