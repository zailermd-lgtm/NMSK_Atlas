"""Q183b: replace the 16 great vessels + quadratus lumborum r/l his bundle still took from ct_s1159 / ct_s1159_abd.

    python3 scripts/vessels_ql_q183b.py own [--report PATH]                 # route (a): his own CT labels, gated
    python3 scripts/vessels_ql_q183b.py transfer --male-bundle DIR [--ids ...] [-o DIR]   # route (c): her own, carried
    python3 scripts/vessels_ql_q183b.py audit --bundle DIR|--subject DIR [--report PATH]  # gates on meshes
    python3 scripts/vessels_ql_q183b.py stamp                               # TRANSFERRED badge with the measured error

Routes, in order, per structure: (a) his own TotalSegmentator label if it passes the gates; (b) his cryosection
photographs if already local (they are not: Q179-Q181 streamed crops of the thigh only, all deleted); (c) HER own
CT-label structure (ct_vhf / ct_vhf_abd / ct_vhf_descaorta in build/viewer_f_hr) carried onto HIS skeleton by the
existing bone-driven body-to-body transfer (scripts/transfer/cross_subject_transfer.py --direction f2m, the Q44
`xfer_vhf2vhm` route), into subject xfer_vhf2vhm_vessels, listed before ct_s1159 in vhm_rebuild_bundle.sh; (d) keep the
ct_s1159 record with its Q183 NOT-HIS-GEOMETRY badge (the viewer has no per-structure default-hidden flag: visibility
is per tissue system). SHIP lists the ids that passed (data/derived/Q183b_vessels_ql.json).
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

from scripts.ribs_from_ct_labels import ORIGIN, TASK, LUNG, closed_volume_cm3, load_skin, to_vox  # noqa: E402
from scripts.costal_cartilage_from_ct_labels import BONE, FOREIGN_TOUCH, OWN_LABEL  # noqa: E402

SUB = "xfer_vhf2vhm_vessels"
VESSELS = list(OWN_LABEL)
QL = {"quadratus_lumborum_r": 21, "quadratus_lumborum_l": 22}
IDS = VESSELS + list(QL)
AORTA = ["aortic_arch_and_great_vessels", "descending_thoracic_aorta", "abdominal_aorta"]
REPORT = REPO / "data" / "derived" / "Q183b_vessels_ql.json"
# ids that passed the route (c) gates on the 2026-10-01 run (see REPORT); the rebuild transfers exactly these
SHIP: list[str] = []
# published adult calibre (mm, mean, SD) -- only where a source was checked; the gate band is mean +- 3 SD
PUBLISHED = {
    "aortic_arch_and_great_vessels": (27.7, 3.7, "Hager 2002 doi:10.1067/mtc.2002.122310, proximal transverse arch 2.77 +- 0.37 cm (helical CT, 70 adults)"),
    "descending_thoracic_aorta": (24.0, 3.0, "Wolak 2008 doi:10.1016/j.jcmg.2007.11.005, descending thoracic aorta 24 +- 3 mm (non-contrast CT, n=1931); Hager 2002 2.43-2.47 cm"),
    "common_carotid_a_r": (6.52, 0.98, "Krejza 2006 doi:10.1161/01.STR.0000206440.48756.f7, CCA men 6.52 +- 0.98 mm (ultrasound)"),
    "common_carotid_a_l": (6.52, 0.98, "Krejza 2006 doi:10.1161/01.STR.0000206440.48756.f7, CCA men 6.52 +- 0.98 mm (ultrasound)"),
}
NO_PUBLISHED = ("no published value checked (Horejs 1988 doi:10.1097/00004728-198807000-00011 gives aorto-iliac CT norms but "
                "not in its abstract); compared with HER own label calibre instead")
GATES = {"outside_skin_frac": 0.0, "in_bone_frac": 0.02, "in_lung_frac": 0.02, "largest_component_share": 0.95,
         "calibre_vs_hers": (0.6, 1.8), "volume_vs_hers": (0.5, 2.5), "ql_lr_ratio": (0.67, 1.5)}


# ---------------------------------------------------------------- shared measurements
def calibre_mm(mask: np.ndarray, sp) -> dict:
    """lumen diameter as LOCAL THICKNESS (diameter of the largest inscribed ball containing each voxel, the
    BoneJ / Hildebrand-Rueegsegger measure): balls centred on the 3-D skeleton with their EDT radius are painted
    largest-last; median / p90 over the mask voxels. Raw skeleton EDT medians undercount (surface spurs)."""
    from scipy import ndimage as ndi
    from skimage.morphology import skeletonize
    if mask.sum() < 8:
        return {"median": None, "p90": None}
    sp = np.asarray(sp, float); m = np.pad(mask, 2)
    edt = ndi.distance_transform_edt(m, sampling=sp)
    c = np.argwhere(skeletonize(m) > 0); r = edt[tuple(c.T)]
    lt = np.zeros(m.shape, np.float32)
    for (i, j, k), rr in zip(c[np.argsort(r)], np.sort(r)):
        h = np.ceil(rr / sp).astype(int)
        sl = tuple(slice(max(a - b, 0), a + b + 1) for a, b in zip((i, j, k), h))
        g = np.ogrid[sl]
        ball = sum(((gg - a) * s_) ** 2 for gg, a, s_ in zip(g, (i, j, k), sp)) <= rr ** 2
        sub = lt[sl]; sub[ball] = 2 * rr
    d = lt[m > 0]; d = d[d > 0]
    return {"median": round(float(np.median(d)), 1), "p90": round(float(np.percentile(d, 90)), 1)}


def components(mask: np.ndarray) -> tuple[int, float]:
    from scipy import ndimage as ndi
    lab, k = ndi.label(mask, np.ones((3, 3, 3)))
    if k == 0:
        return 0, 0.0
    sz = np.bincount(lab.ravel())[1:]
    return int(k), round(float(sz.max() / sz.sum()), 3)


def crop(vol, lab):
    idx = np.argwhere(vol == lab)
    if len(idx) == 0:
        return None
    lo, hi = idx.min(0), idx.max(0) + 1
    return vol[tuple(slice(a, b) for a, b in zip(lo, hi))] == lab


def _vol(name):
    import nibabel as nib
    img = nib.load(TASK / name); A = img.affine
    return np.asarray(img.dataobj).astype(np.uint8), A, np.sqrt((A[:3, :3] ** 2).sum(0))


# ---------------------------------------------------------------- route (a)
def own() -> dict:
    """his own labels vs hers, per structure; aorta label shared by the three aorta records"""
    names = json.loads((REPO / "mappings" / "totalsegmentator_labels.json").read_text())["labels"]
    out = {}
    for body in ("vhm", "vhf"):
        tot, A, sp = _vol(f"{body}_total.nii.gz"); vox = float(np.prod(sp)) / 1000
        for lab in sorted(set(OWN_LABEL.values())):
            m = crop(tot, lab)
            r = {"label": names[str(lab)], "volume_cm3": 0.0, "components": 0, "largest_share": 0.0,
                 "calibre_mm": {"median": None}}
            if m is not None:
                k, share = components(m)
                r.update(volume_cm3=round(float(m.sum() * vox), 1), components=k, largest_share=share,
                         extent_mm=[round(float(x), 0) for x in np.array(m.shape) * sp], calibre_mm=calibre_mm(m, sp))
            out.setdefault(str(lab), {})[body] = r
        del tot
    for body, f in (("vhm", "vhm_abdominal_muscles.nii.gz"), ("vhm_hybrid", "vhm_hybrid_abdominal_muscles.nii.gz"),
                    ("vhf", "vhf_abdominal_muscles.nii.gz")):
        v, A, sp = _vol(f); vox = float(np.prod(sp)) / 1000
        for rid, lab in QL.items():
            m = crop(v, lab); k, share = components(m)
            out.setdefault(rid, {})[body] = {"task": f, "volume_cm3": round(float(m.sum() * vox), 1), "components": k,
                                             "largest_share": share,
                                             "extent_mm": [round(float(x), 0) for x in np.array(m.shape) * sp]}
        del v
    verdict = {}
    for rid in VESSELS:
        lab = str(OWN_LABEL[rid]); h, f = out[lab]["vhm"], out[lab]["vhf"]
        cal = h["calibre_mm"]["median"]; ok_c = cal is not None and f["calibre_mm"]["median"] and \
            GATES["calibre_vs_hers"][0] <= cal / f["calibre_mm"]["median"] <= GATES["calibre_vs_hers"][1]
        ok_v = f["volume_cm3"] > 0 and GATES["volume_vs_hers"][0] <= h["volume_cm3"] / f["volume_cm3"] <= GATES["volume_vs_hers"][1]
        ok_k = h["largest_share"] >= GATES["largest_component_share"]
        verdict[rid] = {"pass": bool(ok_c and ok_v and ok_k), "continuous": ok_k, "volume_ok": ok_v, "calibre_ok": bool(ok_c),
                        "his_vs_her_volume": round(h["volume_cm3"] / f["volume_cm3"], 2) if f["volume_cm3"] else None}
    for rid in QL:
        o = out[rid]; other = "quadratus_lumborum_l" if rid.endswith("_r") else "quadratus_lumborum_r"
        for t in ("vhm", "vhm_hybrid"):
            lr = o[t]["volume_cm3"] / out[other][t]["volume_cm3"]
            ok = (o[t]["largest_share"] >= GATES["largest_component_share"] and GATES["ql_lr_ratio"][0] <= lr <= GATES["ql_lr_ratio"][1]
                  and GATES["volume_vs_hers"][0] <= o[t]["volume_cm3"] / o["vhf"]["volume_cm3"] <= GATES["volume_vs_hers"][1])
            verdict.setdefault(rid, {})[t] = {"pass": bool(ok), "l_r_ratio": round(lr, 2),
                                             "his_vs_her_volume": round(o[t]["volume_cm3"] / o["vhf"]["volume_cm3"], 2)}
        verdict[rid]["pass"] = any(verdict[rid][t]["pass"] for t in ("vhm", "vhm_hybrid"))
    return {"labels": out, "verdict": verdict}


# ---------------------------------------------------------------- route (c)
def transfer(male_bundle: str, ids: list[str], out: Path, report: Path) -> int:
    cmd = [sys.executable, str(REPO / "scripts" / "transfer" / "cross_subject_transfer.py"), "--direction", "f2m",
           "--male-html", male_bundle, "--female-bundle", str(REPO / "build" / "viewer_f_hr"), "--default-region", "trunk", "--ids", *ids,
           "--skin-nii", str(TASK / "vhm_skin_ct.nii.gz"), f"--skin-origin={ORIGIN['vhm']}", "-o", str(out),
           "--report", str(report)]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    print(r.stdout[-600:], r.stderr[-1500:] if r.returncode else "")
    return r.returncode


def load_subject(d: Path) -> dict:
    m = json.loads((d / "manifest.json").read_text())
    V = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3); F = np.fromfile(d / "faces.u32", np.uint32).reshape(-1, 3)
    out = {}
    for s in m["structures"]:
        v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]]
        f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
        out[s["atlas_id"]] = {"v": v, "f": f, "subject": m.get("subject", d.name)}
    return out


def mesh_mask(v, f, pitch):
    import trimesh
    vg = trimesh.Trimesh(v, f, process=False).voxelized(pitch).fill()
    return vg.matrix


def bone_fit_residual(male_bundle: str) -> dict:
    """per bone: median distance (mm) of HER bone carried by its own affine to HIS bone surface"""
    from scipy.spatial import cKDTree
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id, own_only
    from scripts.transfer.cross_subject_transfer import build_bone_maps
    from scripts.transfer.bone_frames import apply
    F = own_only(meshes_by_id(*read_bundle_dir(REPO / "build" / "viewer_f_hr")))
    M = own_only(meshes_by_id(*read_bundle_dir(male_bundle)))
    maps = build_bone_maps(F, M); res = {}
    for b, mp in maps.items():
        p = apply(mp["A"], mp["t"], F[b]["v"].astype(float))
        res[b] = round(float(np.median(cKDTree(M[b]["v"]).query(p)[0])), 1)
    return res


def audit(meshes: dict, his_bundle_meshes: dict | None = None, xfer_rows: dict | None = None, bone_res: dict | None = None) -> dict:
    import trimesh
    from scipy import ndimage as ndi
    from scipy.spatial import cKDTree
    names = json.loads((REPO / "mappings" / "totalsegmentator_labels.json").read_text())["labels"]
    tot, A, sp = _vol("vhm_total.nii.gz"); O = np.array([float(x) for x in ORIGIN["vhm"].split(",")])
    hyb, _, _ = _vol("vhm_hybrid_abdominal_muscles.nii.gz")
    from engine.volume_ingest import atlas_points_of
    skin = load_skin("vhm"); lung = np.isin(tot, LUNG).astype(np.uint8); bone = np.isin(tot, BONE).astype(np.uint8)
    lab_pts = {}

    def pts(vol, lab, key):
        if key not in lab_pts:
            lab_pts[key] = atlas_points_of(vol == lab, A)[1] - O
        return lab_pts[key]
    aorta_trees = {a: cKDTree(meshes[a]["v"]) for a in AORTA if a in meshes}
    out = {}
    for rid in IDS:
        if rid not in meshes:
            continue
        v = meshes[rid]["v"].astype(float); f = meshes[rid]["f"]; iv = to_vox(v, A, O).T
        t = trimesh.Trimesh(v, f, process=False); parts = t.split(only_watertight=False)
        nf = np.array([len(p.faces) for p in parts]) if len(parts) else np.array([len(f)])
        pitch = 0.5 if rid.startswith(("common_carotid", "subclavian", "brachiocephalic_trunk")) else 1.0
        mm = mesh_mask(v, f, pitch)
        r = {"subject": meshes[rid]["subject"], "nv": int(len(v)), "nf": int(len(f)),
             "outside_skin_frac": round(float((~skin.contains(v)).mean()), 4),
             "in_bone_frac": round(float(ndi.map_coordinates(bone, iv, order=0).mean()), 4),
             "in_lung_frac": round(float(ndi.map_coordinates(lung, iv, order=0).mean()), 4),
             "components": int(len(nf)), "largest_component_share": round(float(nf.max() / nf.sum()), 3),
             "volume_cm3": round(closed_volume_cm3(v, f), 1), "watertight": bool(t.is_watertight),
             "calibre_mm": calibre_mm(mm, np.array([pitch] * 3)) if rid in VESSELS else None,
             "should_touch_mm": {}}
        for lab in FOREIGN_TOUCH.get(rid, []):
            p = pts(tot, lab, lab)
            r["should_touch_mm"][names[str(lab)]] = round(float(cKDTree(p).query(v)[0].min()), 1) if len(p) else None
        tree = cKDTree(v)
        if rid in VESSELS:     # his own no-contrast label fragment: where his CT does show the vessel
            p = pts(tot, OWN_LABEL[rid], OWN_LABEL[rid])
            if rid in AORTA and len(aorta_trees) == 3:
                near = np.argmin(np.stack([aorta_trees[a].query(p)[0] for a in AORTA], 1), 1)
                p = p[near == AORTA.index(rid)]
            if len(p):
                d = tree.query(p)[0]; inside = t.contains(p) if t.is_watertight else None
                r["his_label_fragment"] = {"voxels": int(len(p)), "to_mesh_median_mm": round(float(np.median(d)), 1),
                                           "within_5mm_frac": round(float((d <= 5).mean()), 3),
                                           "inside_mesh_frac": None if inside is None else round(float(inside.mean()), 3)}
        else:
            p = pts(hyb, QL[rid], f"hyb{QL[rid]}")
            d = tree.query(p)[0]
            r["his_hybrid_ql_label"] = {"voxels": int(len(p)), "to_mesh_median_mm": round(float(np.median(d)), 1),
                                        "within_5mm_frac": round(float((d <= 5).mean()), 3)}
        if xfer_rows and rid in xfer_rows:
            row = xfer_rows[rid]; w = row["driving_bones"]
            r["transfer"] = {"driving_bones": w, "volume_src_cm3": row["volume_src_cm3"], "volume_out_cm3": row["volume_out_cm3"],
                             "displacement_mm_median": row["displacement_mm_median"],
                             "vertices_clipped_to_skin": row.get("vertices_clipped_to_skin", 0)}
            if bone_res:
                tw = sum(w.values())
                r["transfer"]["bone_fit_residual_mm"] = round(sum(bone_res[b] * x for b, x in w.items()) / tw, 1)
        if rid in PUBLISHED and r["calibre_mm"]:
            mu, sd, src = PUBLISHED[rid]; c = r["calibre_mm"]["median"]
            r["published"] = {"mean_mm": mu, "sd_mm": sd, "source": src, "within_3sd": bool(c is not None and abs(c - mu) <= 3 * sd)}
        elif rid in VESSELS:
            r["published"] = {"source": NO_PUBLISHED}
        out[rid] = r
    return out


def gate(r: dict, her: dict | None) -> dict:
    g = GATES
    checks = {"skin": r["outside_skin_frac"] <= g["outside_skin_frac"],
              "continuous": r["largest_component_share"] >= g["largest_component_share"]}
    if r["calibre_mm"] is not None:
        checks["bone"] = r["in_bone_frac"] <= g["in_bone_frac"]
        checks["lung"] = r["in_lung_frac"] <= g["in_lung_frac"]
        if r.get("published", {}).get("within_3sd") is not None:
            checks["calibre_published"] = r["published"]["within_3sd"]
        if her and her.get("calibre_mm") and her["calibre_mm"]["median"]:
            ratio = r["calibre_mm"]["median"] / her["calibre_mm"]["median"]
            checks["calibre_vs_her_own"] = g["calibre_vs_hers"][0] <= ratio <= g["calibre_vs_hers"][1]
    return {"pass": bool(all(checks.values())), "checks": {k: bool(x) for k, x in checks.items()}}


def badge(rid: str, r: dict) -> str:
    t = r["transfer"]; c = r.get("calibre_mm")
    frag = r.get("his_label_fragment") or r.get("his_hybrid_ql_label")
    fs = (f"; his own CT label for it ({'no-contrast fragment' if rid in VESSELS else 'hybrid-CT quadratus lumborum'}, "
          f"{frag['voxels']} voxels) lies {frag['to_mesh_median_mm']} mm (median) from it, {100 * frag['within_5mm_frac']:.0f} % within 5 mm"
          if frag else "")
    return ("Q183b: TRANSFERRED from the Visible Human female, not measured on him: her own CT-label "
            f"{'vessel' if rid in VESSELS else 'muscle'} carried onto his skeleton by the bone-driven body-to-body transfer "
            f"(driving bones {', '.join(t['driving_bones'])}). Measured error: carried bones sit {t.get('bone_fit_residual_mm', 'n/a')} mm "
            f"(median, weighted) from his own{fs}; {100 * r['in_bone_frac']:.1f} % inside his bone labels, "
            f"{100 * r['in_lung_frac']:.1f} % inside his lung labels, {100 * r['outside_skin_frac']:.1f} % outside his skin"
            + (f"; calibre {c['median']} mm (median)" if c else f"; {r['volume_cm3']} cm3")
            + ". Replaces the ct_s1159 record (another person's CT, never registered to him).")


def stamp(report: Path = REPORT) -> int:
    rep = json.loads(report.read_text()); mf = REPO / "build" / "vh" / SUB / "manifest.json"
    if not mf.exists():
        return 0
    m = json.loads(mf.read_text()); n = 0
    for s in m["structures"]:
        r = rep["after"].get(s["atlas_id"])
        if r and "transfer" in r:
            s["procedural_badge"] = badge(s["atlas_id"], r); n += 1
    m["subject"] = SUB
    mf.write_text(json.dumps(m, indent=2)); print(f"stamped {n} {SUB} records")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("own", "transfer", "audit", "stamp"))
    ap.add_argument("--male-bundle", default=str(REPO / "build" / "viewer_m_hr"))
    ap.add_argument("--ids", nargs="*"); ap.add_argument("-o", "--out", default=str(REPO / "build" / "vh" / SUB))
    ap.add_argument("--bundle"); ap.add_argument("--subject"); ap.add_argument("--xfer-report")
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    if a.cmd == "stamp":
        return stamp(Path(a.report) if a.report else REPORT)
    if a.cmd == "transfer":
        ids = a.ids if a.ids is not None else SHIP
        if not ids:
            print("nothing to transfer"); return 0
        return transfer(a.male_bundle, ids, Path(a.out), Path(a.xfer_report or REPO / "data" / "derived" / "Q183b_transfer_report.json"))
    if a.cmd == "own":
        rep = own()
    else:
        from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
        meshes = load_subject(Path(a.subject)) if a.subject else meshes_by_id(*read_bundle_dir(a.bundle))
        rows = {r["atlas_id"]: r for r in json.loads(Path(a.xfer_report).read_text())["rows"]} if a.xfer_report else None
        rep = audit(meshes, xfer_rows=rows, bone_res=bone_fit_residual(a.male_bundle) if rows else None)
    txt = json.dumps(rep, indent=1)
    if a.report:
        Path(a.report).write_text(txt)
    print(txt[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
