"""Q62 step 5: the VH FEMALE's foot intrinsic muscles, TRANSFERRED from Z-Anatomy onto her own foot bones.

Replacement route for the blocked DU female release (Q59). Z-Anatomy (CC BY-SA 4.0; BodyParts3D upstream) plantar
layers 1-4 + dorsal foot muscles are carried by the Q168 per-bone fit (`zan_to_vhf_whole_body.load_zan_to_vhf`:
talus/calcaneus/navicular/cuboid/3 cuneiforms/each metatarsal/each toe phalanx fitted to HER CT bones), then:
  1. inside-bone gate: vertices inside her own CT foot bones are pushed to the bone surface + 1 mm along the
     point-to-surface ray (`limb_per_bone_transfer.push_off_bones`' method), BOUNDED: only vertices at most
     PUSH_BOUND_MM deep (= the gate-4 bone-fit tolerance: penetration within the bones' own fit error); deeper
     vertices stay where they are and count; > MAX_INSIDE_BONE still inside after the push -> dropped. Measured
     before the fix too (Z-Anatomy itself draws some of these muscles 5-21 % into its OWN bones at attachments);
  2. skin gate: against her ct_vhf_skin mesh (the containment test of limb_per_bone_transfer.clip_to_skin_mesh);
     fraction/depth outside reported before the fix (> MAX_OUTSIDE_SKIN_PRECLIP -> dropped as a failed fit, the
     Q147 rule), then `pull_inside_skin` (nearest skin point + 0.5 mm) -- 0 % outside is required after;
  3. muscle-to-muscle overlap (vertices of A inside B, same side, incl. the 11 foot muscles she already has from
     xfer_zan2vhf_limb) and the fit error of the foot bones each muscle rides on (Q168 per-piece residuals,
     weighted by how many of the muscle's vertices lie nearest each Z-Anatomy bone piece).
Only ids with NO mesh in her bundle yet are built (SKIP_EXISTING). Non-commercial Z-Anatomy objects never enter
(`collect_zan` = the Z-Anatomy build's own source, which excludes them). Output subject xfer_zan2vhf_foot
(xfer_ prefix: never counted as her own mesh by Q168's validation), report data/derived/Q62s5_vhf_foot_intrinsics.json.

    python3 scripts/transfer/zan_to_vhf_foot_intrinsics.py [--out build/vh/xfer_zan2vhf_foot] [--dry]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.transfer import zan_to_vhf_whole_body as Z  # noqa: E402

SUBJECT = "xfer_zan2vhf_foot"
REPORT = REPO / "data" / "derived" / "Q62s5_vhf_foot_intrinsics.json"
MAX_INSIDE_BONE = 0.05          # task rule: drop a muscle with > 5 % of its vertices inside her bones
MAX_OUTSIDE_SKIN_PRECLIP = 0.5  # Q147's OUTSIDE_SKIN_REJECT_FRACTION: more than this outside = failed fit
MAX_BONE_FIT_MM = 3.0           # gate 4: weighted median fit residual of the foot bones a muscle rides on
MAX_OVERLAP = 0.10              # gate 3: more than this share of a muscle's vertices inside other foot muscles -> held
PUSH_BOUND_MM = 3.0             # bounded push-out: only vertices at most this deep inside a bone are moved
CLEARANCE_MM = 1.0              # limb_per_bone_transfer.BONE_PUSH_CLEARANCE_MM
SKIN_INSET_MM = 0.5             # outside vertices go this far inside her skin surface

BASES = ["abductor_hallucis", "flexor_digitorum_brevis", "abductor_digiti_minimi_foot", "quadratus_plantae",
         "lumbricals_foot", "flexor_hallucis_brevis", "adductor_hallucis", "flexor_digiti_minimi_brevis_foot",
         "plantar_interossei", "dorsal_interossei_foot", "extensor_digitorum_brevis", "extensor_hallucis_brevis"]
# atlas id -> Z-Anatomy mesh id. The foot lumbricals are unmatched in the name map (score 0.33) and live in the
# Z-Anatomy build's orphan pool as zan_lumbrical_muscles_of_foot_<s> ("Lumbrical muscles of foot.<s>").
ZAN_ID = {f"{b}_{s}": (f"zan_lumbrical_muscles_of_foot_{s}" if b == "lumbricals_foot" else f"{b}_{s}")
          for b in BASES for s in "rl"}
# already in her bundle (xfer_zan2vhf_limb, Q147; checked in build/viewer_f_hr/bundle.json 2026-09-30)
SKIP_EXISTING = {"abductor_hallucis_l", "quadratus_plantae_r", "quadratus_plantae_l", "adductor_hallucis_r",
                 "adductor_hallucis_l", "flexor_digiti_minimi_brevis_foot_r", "flexor_digiti_minimi_brevis_foot_l",
                 "plantar_interossei_r", "plantar_interossei_l", "dorsal_interossei_foot_r"}
FOOT_BONES = ["talus", "calcaneus", "navicular", "cuboid", "cuneiform_medial", "cuneiform_intermediate",
              "cuneiform_lateral", "metatarsals", "phalanges_foot"]
# published adult volumes for comparison. Per-muscle MRI volumes exist (Kusagawa et al. 2022, J Foot Ankle Res 15:22,
# doi:10.1186/s13047-022-00532-9, 17 young men; order ABH > FDB > ABDM > ADDH-OH > FHB > QP > ADDH-TH) but their
# tables could not be read here (PubMed full text omits tables; PMC and the publisher are blocked by the proxy), so
# only whole-group values are compared, per foot.
PUBLISHED = {
    "plantar_intrinsics_contractile_cm3": {"value": 113.3, "what": "mean contractile volume, all plantar intrinsic "
                                           "foot muscles, healthy feet (MRI, n=8)", "ref": "Chang R, Kent-Braun JA, "
                                           "Hamill J. Clin Biomech 2012;27(5):500-5. doi:10.1016/j.clinbiomech.2011.11.007"},
    "all_intrinsic_foot_muscles_cm3": {"value": 168, "sd": 42, "what": "total volume of the intrinsic foot muscles, "
                                       "healthy controls (MRI stereology, n=23)", "ref": "Andersen H, Gjerstad MD, "
                                       "Jakobsen J. Diabetes Care 2004;27(10):2382-5. doi:10.2337/diacare.27.10.2382"}}
PUBLISHED_NOTE = ("no per-muscle published volume could be read in this session (see PUBLISHED); per-muscle rows compare "
                  "with the Z-Anatomy source only. Z-Anatomy meshes include tendon/aponeurosis, MRI contractile volumes do not.")
PLANTAR = {"abductor_hallucis", "flexor_digitorum_brevis", "abductor_digiti_minimi_foot", "quadratus_plantae",
           "lumbricals_foot", "flexor_hallucis_brevis", "adductor_hallucis", "flexor_digiti_minimi_brevis_foot",
           "plantar_interossei", "dorsal_interossei_foot"}


def targets() -> list[str]:
    return [a for a in ZAN_ID if a not in SKIP_EXISTING]


def piece_residual(fits: dict, piece: str) -> float | None:
    """Q168's final residual (mm) of one Z-Anatomy bone piece: chain > piece refinement > unit fit."""
    for unit, fr in fits.items():
        if fr.get("status") != "fitted" or piece not in fr["pieces"]:
            continue
        pf = fr.get("piece_fits", {}).get(piece)
        if pf:
            if "chain" in pf:
                return float(pf["chain"]["residual_after_mm"])
            if "residual_after_mm" in pf:
                return float(pf["residual_after_mm"])
        return float(fr["residual_mm"])
    return None


def rides_on(xf, fits: dict, v_src: np.ndarray, side: str, groups: tuple | None = None) -> dict:
    """Which of the Z-Anatomy foot bone pieces this muscle's (source-frame) vertices lie nearest, and their fit.
    `groups` (Q168 unit_group names, e.g. ("axial",)) widens it beyond the foot (default: lower_<side>)."""
    groups = groups or (f"lower_{side}",)
    names = [n for n in xf.unit_names if Z.unit_group(n.split("/")[0]) in groups]
    idx = [xf.unit_names.index(n) for n in names]
    pts = np.vstack([xf.unit_pts[i] for i in idx]); lab = np.concatenate([np.full(len(xf.unit_pts[i]), k)
                                                                           for k, i in enumerate(idx)])
    _, j = cKDTree(pts).query(v_src)
    cnt = np.bincount(lab[j], minlength=len(idx))
    rows = []
    for k in np.argsort(-cnt):
        if cnt[k] == 0:
            break
        piece = names[k].split("/")[-1]
        rows.append({"piece": piece, "share": round(float(cnt[k] / cnt.sum()), 3),
                     "fit_residual_mm": piece_residual(fits, piece)})
    res = np.array([r["fit_residual_mm"] for r in rows]); w = np.array([r["share"] for r in rows])
    o = np.argsort(res); cw = np.cumsum(w[o]) / w.sum()
    return {"bones": rows[:6], "weighted_median_fit_mm": round(float(res[o][np.searchsorted(cw, 0.5)]), 2),
            "max_fit_mm": round(float(res.max()), 2)}


def bounded_push_off_bones(v: np.ndarray, bone_meshes: list, bound_mm: float = PUSH_BOUND_MM,
                           clearance_mm: float = CLEARANCE_MM):
    """push_off_bones (limb_per_bone_transfer) with a depth bound: a vertex inside a bone and at most bound_mm from
    its surface goes to the nearest surface point + clearance along the point-to-surface ray; deeper ones stay.
    Returns (v', n_pushed, n_left_deep)."""
    out = np.asarray(v, np.float64).copy(); n_push = n_deep = 0
    for m in bone_meshes:
        ins = np.where(m.contains(out))[0]
        if not len(ins):
            continue
        cl, dist, _ = m.nearest.on_surface(out[ins])
        ok = dist <= bound_mm
        n_deep += int((~ok).sum()); sel = ins[ok]
        if not len(sel):
            continue
        d = cl[ok] - out[sel]; ln = np.linalg.norm(d, axis=1, keepdims=True); ln[ln == 0] = 1.0
        new = cl[ok] + d / ln * clearance_mm
        still = m.contains(new)
        new[still] = cl[ok][still] + (d / ln)[still] * clearance_mm * 4
        out[sel] = new; n_push += len(sel)
    return out, n_push, n_deep


def pull_inside_skin(v: np.ndarray, skin_mesh, inset_mm: float = SKIN_INSET_MM):
    """Every vertex outside her skin goes to its nearest skin point + inset_mm further in (along the vertex-to-surface
    ray); a vertex still outside after that retries with 3x the inset. Bounded by how far outside it was (+ inset),
    unlike clip_to_skin_mesh's ray-to-centroid bisection, which collapses vertices of a multi-belly muscle
    (extensor digitorum brevis: 58-82 mm moves measured) when the ray to the centroid leaves the foot.
    Returns (v', n_moved)."""
    out = np.asarray(v, np.float64).copy()
    bad = np.where(~skin_mesh.contains(out))[0]
    if not len(bad):
        return out, 0
    for k in (1.0, 3.0):
        cl, _, _ = skin_mesh.nearest.on_surface(out[bad])
        d = cl - out[bad]; ln = np.linalg.norm(d, axis=1, keepdims=True); ln[ln == 0] = 1.0
        out[bad] = cl + d / ln * inset_mm * k
        bad = bad[~skin_mesh.contains(out[bad])]
        if not len(bad):
            break
    return out, int(len(np.where(np.linalg.norm(out - v, axis=1) > 0)[0]))


def outside_depth(v: np.ndarray, skin_mesh) -> np.ndarray:
    """distance (mm) outside her skin of each vertex that is outside it"""
    out = ~skin_mesh.contains(v)
    if not out.any():
        return np.zeros(0)
    return skin_mesh.nearest.on_surface(v[out])[1]


def voxel_volume_cm3(v: np.ndarray, f: np.ndarray, pitch: float = 0.5) -> float:
    m = trimesh.Trimesh(v, f, process=False)
    return float(m.voxelized(pitch).fill().points.shape[0] * pitch ** 3 / 1000.0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO / "build" / "vh" / SUBJECT))
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--dry", action="store_true", help="measure and report only; write no subject")
    a = ap.parse_args(argv)

    tg = targets()
    rep168 = json.loads(Path(Z.DEFAULT_REPORT).read_text())
    fits = Z.fits_from_json(rep168["bone_fits"])
    need = {p for fr in fits.values() if fr.get("status") == "fitted" for p in fr["pieces"]}
    items = {it["mesh_id"]: it for it in Z.collect_zan(ids={ZAN_ID[t] for t in tg} | need)}
    xf = Z.load_zan_to_vhf(zan_meshes=items)
    her = Z.load_her_meshes()
    skin = her["skin"]; skin_mesh = trimesh.Trimesh(skin["v"], skin["f"], process=False)
    bones = {s: {b: trimesh.Trimesh(her[f"{b}_{s}"]["v"], her[f"{b}_{s}"]["f"], process=False)
                 for b in FOOT_BONES if f"{b}_{s}" in her} for s in "rl"}
    existing = Z.load_her_meshes(order=["xfer_zan2vhf_limb"])

    rows, out_mesh, dropped = {}, {}, {}
    for aid in tg:
        zid = ZAN_ID[aid]; side = aid[-1]
        if zid not in items:
            dropped[aid] = f"no Z-Anatomy object {zid}"; continue
        it = items[zid]; v_src, f = it["v"], it["f"]
        nv = xf(zid, it["cat"], v_src)
        in_bone = np.zeros(len(nv), bool)
        per_bone = {}
        for b, m in bones[side].items():
            ins = m.contains(nv); per_bone[b] = int(ins.sum()); in_bone |= ins
        frac_bone = float(in_bone.mean())
        frac_out = float((~skin_mesh.contains(nv)).mean())
        od = outside_depth(nv, skin_mesh)
        ride = rides_on(xf, fits, v_src, side)
        nv2, n_push, n_deep = bounded_push_off_bones(nv, list(bones[side].values()))
        in_bone_p = np.zeros(len(nv2), bool)
        for m in bones[side].values():
            in_bone_p |= m.contains(nv2)
        row = {"atlas_id": aid, "zanatomy_object": it["name"], "zanatomy_mesh_id": zid, "vertices": int(len(nv)),
               "triangles": int(len(f)), "watertight": bool(trimesh.Trimesh(v_src, f, process=False).is_watertight),
               "inside_bone_frac_before": round(frac_bone, 4),
               "inside_bone_by_bone": {k: n for k, n in per_bone.items() if n},
               "outside_skin_frac_before": round(frac_out, 4),
               "outside_skin_depth_mm": {"p95": round(float(np.percentile(od, 95)), 2) if len(od) else 0.0,
                                         "max": round(float(od.max()), 2) if len(od) else 0.0},
               "pushed_off_bone": n_push, "inside_bone_deeper_than_bound": n_deep,
               "inside_bone_frac_after_push": round(float(in_bone_p.mean()), 4), "rides_on": ride}
        why = None
        if in_bone_p.mean() > MAX_INSIDE_BONE:
            why = (f"{in_bone_p.mean():.1%} of vertices still inside her foot bones after the bounded push-out "
                   f"(> {MAX_INSIDE_BONE:.0%}; {frac_bone:.1%} before)")
        elif frac_out > MAX_OUTSIDE_SKIN_PRECLIP:
            why = f"{frac_out:.0%} of vertices outside her skin before clipping (failed fit)"
        elif ride["weighted_median_fit_mm"] > MAX_BONE_FIT_MM:
            why = f"foot bones it rides on fit her CT at {ride['weighted_median_fit_mm']} mm (> {MAX_BONE_FIT_MM} mm)"
        if why:
            row["dropped"] = why; dropped[aid] = why; rows[aid] = row; continue
        nv3, n_clip = pull_inside_skin(nv2, skin_mesh)
        in_bone2 = np.zeros(len(nv3), bool)
        for m in bones[side].values():
            in_bone2 |= m.contains(nv3)
        mv = np.linalg.norm(nv3 - nv, axis=1)
        vol_src = voxel_volume_cm3(v_src, f); vol_out = voxel_volume_cm3(nv3, f)
        row.update({"clipped_to_skin": n_clip,
                    "fix_move_mm": {"p95": round(float(np.percentile(mv, 95)), 2), "max": round(float(mv.max()), 2)},
                    "inside_bone_frac_after": round(float(in_bone2.mean()), 4),
                    "outside_skin_frac_after": round(float((~skin_mesh.contains(nv3)).mean()), 4),
                    "volume_transferred_before_fix_cm3": round(voxel_volume_cm3(nv, f), 2),
                    "volume_zanatomy_cm3": round(vol_src, 2), "volume_cm3": round(vol_out, 2),
                    "volume_ratio": round(vol_out / vol_src, 3)})
        rows[aid] = row; out_mesh[aid] = (nv3, f)

    # gate 3: muscle-to-muscle overlap (vertices of A inside B), same side, new + her existing foot intrinsics
    pool = {k: (v[0], v[1]) for k, v in out_mesh.items()}
    for k in ZAN_ID:
        if k in SKIP_EXISTING and k in existing:
            pool[k] = (existing[k]["v"], existing[k]["f"])
    tm = {k: trimesh.Trimesh(v, f, process=False) for k, (v, f) in pool.items()}
    for aid in out_mesh:
        ov = {}
        for k, m in tm.items():
            if k == aid or k[-1] != aid[-1]:
                continue
            n = int(m.contains(pool[aid][0]).sum())
            if n:
                ov[k] = round(n / len(pool[aid][0]), 4)
        rows[aid]["overlap_frac_inside_other"] = dict(sorted(ov.items(), key=lambda kv: -kv[1]))
        rows[aid]["overlap_frac_total"] = round(float(sum(ov.values())), 4)
    for aid in list(out_mesh):
        if rows[aid]["overlap_frac_total"] > MAX_OVERLAP:
            why = (f"{rows[aid]['overlap_frac_total']:.1%} of vertices inside other foot muscles (> {MAX_OVERLAP:.0%}; "
                   f"mostly {next(iter(rows[aid]['overlap_frac_inside_other']))})")
            rows[aid]["dropped"] = why; dropped[aid] = why; del out_mesh[aid]
    # per-foot volume totals (this subject + her existing xfer_zan2vhf_limb foot intrinsics)
    totals = {}
    for s in "rl":
        new = sum(rows[a]["volume_cm3"] for a in out_mesh if a[-1] == s)
        old = sum(voxel_volume_cm3(existing[k]["v"], existing[k]["f"]) for k in SKIP_EXISTING
                  if k[-1] == s and k in existing)
        pl = sum(rows[a]["volume_cm3"] for a in out_mesh if a[-1] == s and a[:-2] in PLANTAR) + sum(
            voxel_volume_cm3(existing[k]["v"], existing[k]["f"]) for k in SKIP_EXISTING
            if k[-1] == s and k in existing and k[:-2] in PLANTAR)
        totals[s] = {"new_cm3": round(new, 1), "existing_cm3": round(old, 1), "all_cm3": round(new + old, 1),
                     "plantar_cm3": round(pl, 1)}

    for aid, r in rows.items():
        if "dropped" in r:
            continue
        rd = r["rides_on"]
        r["badge"] = ("Q62 step 5: TRANSFERRED, not segmented from her. Z-Anatomy geometry (CC BY-SA 4.0; Z-Anatomy / "
                      "BodyParts3D) fitted onto this specimen's own foot bones one bone at a time (Q168 per-bone fits). "
                      f"Not measured on this muscle (she has no mesh of it); the foot bones it is carried by fit her CT at "
                      f"{rd['weighted_median_fit_mm']:.1f} mm median surface residual (worst of them {rd['max_fit_mm']:.1f} mm). "
                      f"Volume {r['volume_cm3']:.1f} cm3; {r['pushed_off_bone']} vertices pushed off her bones, "
                      f"{r['clipped_to_skin']} clipped to her skin.")

    shipped = sorted(out_mesh)
    summary = {"shipped": shipped, "dropped": dropped, "skipped_existing": sorted(SKIP_EXISTING),
               "n_shipped": len(shipped), "volume_totals_per_foot": totals}
    doc = {"source": "Q62 step 5 (scripts/transfer/zan_to_vhf_foot_intrinsics.py): Z-Anatomy foot intrinsic muscles "
                     "(CC BY-SA 4.0) carried onto the VH female's own foot bones by the Q168 per-bone fits "
                     "(data/derived/Q168_zan_to_vhf.json).",
           "gates": {"max_inside_bone_frac": MAX_INSIDE_BONE, "max_outside_skin_preclip_frac": MAX_OUTSIDE_SKIN_PRECLIP,
                     "max_bone_fit_mm": MAX_BONE_FIT_MM,
                     "max_overlap_frac": MAX_OVERLAP, "push_bound_mm": PUSH_BOUND_MM},
           "summary": summary, "published_volumes": PUBLISHED, "published_note": PUBLISHED_NOTE, "rows": rows}
    Path(a.report).write_text(json.dumps(doc, indent=1))
    print(f"report {a.report}: shipped {len(shipped)}, dropped {sorted(dropped)}")
    if a.dry or not shipped:
        return 0

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    verts, faces, structs, voff, foff = [], [], [], 0, 0
    for aid in shipped:
        v, f = out_mesh[aid]; v32 = v.astype(np.float32)
        structs.append({"atlas_id": aid, "source_structure": ZAN_ID[aid], "side": "right" if aid.endswith("_r") else "left",
                        "source_file": f"zanatomy#{rows[aid]['zanatomy_object']}",
                        "vertex_offset": voff, "face_offset": foff, "vertex_count": int(len(v32)),
                        "triangle_count": int(len(f)),
                        "bbox_min_mm": [round(float(x), 4) for x in v32.min(0)],
                        "bbox_max_mm": [round(float(x), 4) for x in v32.max(0)],
                        "procedural_badge": rows[aid]["badge"],
                        "transfer": {"from": "zanatomy", "method": "Q168 per-bone fit (zan_to_vhf_whole_body)",
                                     "rides_on": rows[aid]["rides_on"]["bones"][:3]}})
        verts.append(v32); faces.append((f + voff).astype(np.uint32)); voff += len(v32); foff += len(f)
    V = np.concatenate(verts); F = np.concatenate(faces)
    V.tofile(out / "vertices.f32"); F.tofile(out / "faces.u32")
    attribution = [
        "GENERIC MODEL, NOT SEGMENTED FROM THIS SPECIMEN: foot intrinsic muscles from Z-Anatomy (CC BY-SA 4.0), fitted "
        "onto this specimen's OWN foot bones one bone at a time (Q168 per-bone similarity fits; scripts/transfer/"
        "zan_to_vhf_foot_intrinsics.py, Q62 step 5), pushed off her bones and clipped to her skin. Only ids she had "
        "no mesh for. Per-muscle badge gives the fit error of the bones it rides on; data/derived/"
        "Q62s5_vhf_foot_intrinsics.json has every gate number.",
        "Z-Anatomy: models by the Z-Anatomy project (BodyParts3D upstream credited in its own LICENSE), app by "
        "Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. "
        "Licensed CC BY-SA 4.0; this registered derivative remains CC BY-SA 4.0 (ShareAlike)."]
    man = {"subject": out.name, "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
           "source_volume": None, "source_kind": "cross-subject transfer zanatomy -> vhf (Q168 per-bone fit)",
           "vertex_count": int(len(V)), "triangle_count": int(len(F)),
           "bbox_min_mm": [round(float(x), 4) for x in V.min(0)], "bbox_max_mm": [round(float(x), 4) for x in V.max(0)],
           "attribution": attribution, "license": "CC-BY-SA-4.0", "structures": structs}
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    print(f"{out.name}: {len(structs)} structures, {len(V)} vertices, {len(F)} triangles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
