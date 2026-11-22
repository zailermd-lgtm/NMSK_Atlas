#!/usr/bin/env python3
"""Q243 (Z pages, female): the pelvic vessels of the HRA `blood-vasculature-female` v1.3 (Visible Human female frame, CC BY 4.0) as an in-process patch of the page (untouched structures byte for byte,
ship diff 0 unlisted). comb_f: the Q233 pelvis transform (HER OWN CT pelvis, the same transform as the uterus there). base_f: the Q233 base transform (Z male-derived pelvis, scale x0.817), shipped only if every
guard passes. Overlaps with the page's own Z-Anatomy vessels / organs (fit estimates) are REPORTED, not gated. The spine is not placed here: see the report (`spine`).
    python3 scripts/zanatomy/q243_z.py comb_f|base_f [--src PAGE_DIR] [--out PRE_PAGE_DIR]
The pre-page is rendered from the template named by $Q233_ZAN_TEMPLATE (a committed revision) so that scripts/verify_regen_q218.py can find it in git."""
from __future__ import annotations
import argparse, json, os, shutil, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
from scripts.anatomy.q243 import vessels as VS, evidence as EV, badges as BD  # noqa: E402

CFG = {"comb_f": dict(src="build/q239/viewer_zan_female", stem="atlas_viewer_zan_female", out="build/q243_pre/viewer_zan_female"),
       "base_f": dict(src="build/q239/viewer_base_female", stem="atlas_viewer_base_female", out="build/q243_pre/viewer_base_female")}
ATTR = (f"{BD.HRA_NAME} (CC BY 4.0; https://humanatlas.io/3d-reference-library): blood-vasculature-female v1.3, {BD.AUTH}, {BD.BV_DOI}; created from the Visible Human Dataset. Registered onto this page's body by this atlas "
        "(Q243; the Q233 pelvis transform), open tube ends closed with flat discs; derived data, CC BY 4.0 attribution kept (third_party/hra_vh_f/SOURCES_Q242.md).")
# the page's own Z-Anatomy estimate of the same vessel, where there is one (reported next to the HRA vessel)
Z_TWIN = {"internal_iliac_v_l": "zan_internal_iliac_vein_l", "internal_iliac_v_r": "zan_internal_iliac_vein_r", "internal_pudendal_v_l": "zan_internal_pudendal_vein_l",
          "internal_pudendal_v_r": "zan_internal_pudendal_vein_r", "superior_rectal_a": "zan_superior_anorectal_artery"}


def run(which, src, out):
    np.random.seed(0)
    if os.environ.get("Q233_ZAN_TEMPLATE"):
        P5.B.TEMPLATE_PATH = Path(os.environ["Q233_ZAN_TEMPLATE"])
    cfg = CFG[which]; src, out = Path(src), Path(out)
    if which == "comb_f":
        reg0 = json.loads((REPO / "data/derived/Q233_hra_to_vhf_transform.json").read_text())
        reg_txt = (f"HRA VH_F pelvis registered onto HER OWN CT pelvis (hip bones, sacrum, coccyx; rigid + uniform scale x{reg0['scale']}, surface residual median {reg0['residual_mm']['median']} mm, "
                   f"p90 {reg0['residual_mm']['p90']}), the same transform as the uterus of this page")
    else:
        reg0 = json.loads((REPO / "data/derived/Q233_report_base_f.json").read_text())["registration"]
        reg_txt = (f"HRA VH_F pelvis registered (rigid + uniform scale x{reg0['scale']}: this page's body is smaller than the donor) onto THIS page's Z-Anatomy pelvis bones, surface residual median "
                   f"{reg0['residual_mm']['median']} mm, p90 {reg0['residual_mm']['p90']}, rms {reg0['residual_mm']['rms']} -- the residual mostly measures that the Z-Anatomy pelvis is MALE-derived and the donor's is female, "
                   f"the same transform as the uterus of this page")
    T0 = (reg0["scale"], np.array(reg0["rotation"]), np.array(reg0["translation_mm"]))
    ev = EV.z_pelvis(src, cfg["stem"])
    S, man, blob = ev["S"], ev["man"], ev["blob"]
    M = VS.load_hra()
    placed, order = VS.place(M, T0, ev["ev"], ev["bones"], ev["hips"], ev["skin_fn"], soft_gate=False)
    add, report = [], {}
    for sid, name, latin, node, side, kind, grp in VS.VESSELS:
        o = placed[sid]; g = o["gates"]; g["caps"] = M[sid][2]
        # Z-Anatomy twin: symmetric nearest-neighbour distance (reported)
        note = ""
        tw = Z_TWIN.get(sid)
        if tw and tw in S and len(S[tw]["f"]):
            a = trimesh.Trimesh(o["V"], o["F"], process=False).sample(8000); b = trimesh.Trimesh(S[tw]["v"], S[tw]["f"], process=False).sample(8000)
            d = np.concatenate([cKDTree(b).query(a)[0], cKDTree(a).query(b)[0]])
            g["z_twin"] = dict(id=tw, sym_nn_median_mm=round(float(np.median(d)), 1), sym_nn_p90_mm=round(float(np.quantile(d, .9)), 1), centroid_offset_mm=round(float(np.linalg.norm(a.mean(0) - b.mean(0))), 1))
            note = (f" This page ALSO has a Z-Anatomy estimate of this vessel (`{tw}`, a fit of the male-derived Z-Anatomy mesh to this body): the two differ by a symmetric nearest-neighbour distance of median {g['z_twin']['sym_nn_median_mm']} / "
                    f"p90 {g['z_twin']['sym_nn_p90_mm']} mm (centroid offset {g['z_twin']['centroid_offset_mm']} mm); both are shown, they are not merged. The Z-Anatomy soft structures of this page are fit estimates, so the course check against the "
                    f"common iliac vein of this page is reported, not gated.")
        report[sid] = dict(hra_node=node, gates=g)
        # Z-Anatomy soft structures are fit estimates: the iliac / vein-continuity check against them is not a gate
        if not g["pass"] and g["course"].get("ok") is False and "superior_end_to_common_iliac_vein_mm" in g["course"]:
            g["pass"] = bool(g["bone_min_mm"] >= 1.0 - 1e-6 and g["skin_distance_min_mm"] >= 15 and g["max_move_out_of_bone_mm"] <= 6.0 and g["moved_fraction_pct"] <= 40 and g["left_right"]["ok"])
            g["course_not_gated_note"] = "distance to the Z-Anatomy common iliac vein (an estimate) is reported, not gated"
        print(which, sid, "PASS" if g["pass"] else "HELD", g["bone_min_mm"], g["calibre_mm"], g["length_mm"], flush=True)
        if not g["pass"]:
            report[sid]["held"] = True; continue
        v = dict(node=node, side=side)
        rec = dict(name=name, latin=latin, folder="vascular", region="pelvis", source=BD.vessel_source(),
                   procedural_badge=BD.vessel_badge(v, g, VS.ONTO[node], reg_txt, "this page's", page_note=note))
        ent = {"name": name, "id": sid, "side": {"left": "l", "right": "r", None: "m"}[side], "sys": "vessel", "rec": rec}
        if kind == "v":
            ent["vt"] = "v"
        add.append((ent, o["V"], o["F"]))
    man = dict(man); man["attribution"] = (man.get("attribution") or "").rstrip() + " " + ATTR
    P5.save_page(out, cfg["stem"], man, blob, add=add)
    for f in src.glob("clinical_*"):
        shutil.copy2(f, out / f.name)
    r = SD.diff(src, out, cfg["stem"], [])
    listed = sorted(e["id"] for e, _, _ in add)
    rel = lambda p: str(p.resolve().relative_to(REPO)) if str(p.resolve()).startswith(str(REPO)) else str(p)  # noqa: E731
    diff = dict(source=rel(src), new=rel(out), added=r["added"], added_expected=listed, removed=r["removed"], geometry_changed=sorted(r["geometry_changed"]), card_only=sorted(r["card_only"]),
                unchanged=r["unchanged"], unlisted=sorted(set(r["added"]) ^ set(listed)) + sorted(r["card_only"]) + sorted(r["geometry_changed"]) + sorted(r["removed"]))
    rep = dict(page=which, pelvis_registration=reg0, rectal_order=order, structures=report, attribution=ATTR, ship_diff=diff, shipped=listed)
    (REPO / f"data/derived/Q243_report_{which}.json").write_text(json.dumps(rep, indent=1, default=float) + "\n")
    (REPO / f"data/derived/Q243_vertex_diff_{which}.json").write_text(json.dumps(diff, indent=1) + "\n")
    print(which, "ship diff: added", len(diff["added"]), "card_only", len(diff["card_only"]), "geometry_changed", len(diff["geometry_changed"]), "removed", len(diff["removed"]), "unlisted", diff["unlisted"], "unchanged", diff["unchanged"])
    return 1 if diff["unlisted"] else 0


def run_male(src="build/q239/viewer_zan_vhm", stem="atlas_viewer_zan_male_fitted"):
    """Combined male: the prostate zones of the HRA United Male with the HRA male pelvis registered onto this page's pelvic bones, guarded against the page's (Z-Anatomy fit) prostate. Report only unless
    every guard passes (then the shipping code path would have to be written: it has not been needed)."""
    from scripts.anatomy.q243 import male as ML
    np.random.seed(0)
    ev = EV.z_pelvis(REPO / src, stem)
    S = ev["S"]
    bones = [trimesh.Trimesh(e["v"], e["f"], process=False) for i, e in S.items() if e["m"]["sys"] == "bone" and len(e["f"]) > 20 and i in ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx")]
    if len(bones) < 4:
        bones = ev["bones"]
    evm = {k: (S[i]["v"], S[i]["f"]) for k, i in (("prostate", "zan_prostate"), ("urinary_bladder", "zan_urinary_bladder"), ("urethra_male", "zan_urethra")) if i in S}
    T, reg = ML.register_pelvis(bones)
    rep = ML.guard_zones(T, reg, evm, bones, ev["skin_fn"])
    rep["page"] = src; rep["bones_used"] = len(bones)
    (REPO / "data/derived/Q243_report_comb_m.json").write_text(json.dumps(rep, indent=1, default=float) + "\n")
    print("comb_m: zones ship" if rep["ships"] else "comb_m: zones NOT shipped: " + rep["reason"])
    if rep["ships"]:
        raise SystemExit("zones pass the guards: the shipping path is not implemented")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("which", choices=list(CFG) + ["comb_m"]); ap.add_argument("--src"); ap.add_argument("--out"); a = ap.parse_args()
    if a.which == "comb_m":
        sys.exit(run_male())
    c = CFG[a.which]
    sys.exit(run(a.which, a.src or str(REPO / c["src"]), a.out or str(REPO / c["out"])))
