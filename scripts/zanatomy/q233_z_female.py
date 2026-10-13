#!/usr/bin/env python3
"""Q233 (Z pages, female): add the female organs the Z-Anatomy source does not have (uterus, ovaries, uterine tubes) as the HuBMAP HRA reference organs of the Visible Human FEMALE (CC BY 4.0), in-process patch of the
published page (as Q202-Q225: untouched structures byte for byte, ship diff with 0 unlisted).
    python3 scripts/zanatomy/q233_z_female.py comb_f [--src build/q225/viewer_zan_female] [--out build/q233_pre/viewer_zan_female]
    python3 scripts/zanatomy/q233_z_female.py base_f [--src build/q222/viewer_base_female] [--out build/q233_pre/viewer_base_female]
comb_f: the organs are the same five meshes as on the Imaging-based female (her atlas frame, registration on her CT pelvis, data/derived/Q233_organs_vhf.npz).
base_f: the HRA pelvis is registered (rigid + uniform scale ICP) onto the Z-Anatomy pelvis of that page (male-derived bones: the residual is itself a dimorphism measure) and the organs are rebuilt there.
Guards: deep inside the page's skin (>= 20 mm), out of the page's bones (>= 0.5 mm); the overlap with the page's own Z-Anatomy soft structures (bladder, colon, vessels: fit estimates) is REPORTED and flagged above 10 %, not gated.
Held organs are not added; nothing is pushed or deformed."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
from scripts.anatomy.q233 import hra_register as H  # noqa: E402
from scripts.transfer.q233_own_f import ORGANS, decimate, mask_of  # noqa: E402
import q233_load as Q  # noqa: E402

CFG = {
    "comb_f": dict(src="build/q225/viewer_zan_female", stem="atlas_viewer_zan_female", out="build/q233_pre/viewer_zan_female", page="comb_f"),
    "base_f": dict(src="build/q222/viewer_base_female", stem="atlas_viewer_base_female", out="build/q233_pre/viewer_base_female", page="base_f"),
}
HRA_ATTR = ("HuBMAP Human Reference Atlas, 3D Reference Object Library v1.3 (CC BY 4.0), Kristen Browne and Heidi Schlehlein, created from the National Library of Medicine Visible Human FEMALE data "
            "(VH_F_Uterus, VH_F_Ovary_L/R, VH_F_Fallopian_Tube_L/R, VH_F_Pelvis; https://humanatlas.io/3d-reference-library, DOI 10.48539/HBM228.JBNJ.299). Registered onto this page's pelvis by this atlas (Q233); "
            "derived data, CC BY 4.0 attribution kept (third_party/hra_vh_f/NOTICE.md).")


def side_code(side):
    return {"left": "l", "right": "r", None: "m"}[side]


def run(which, src, out):
    np.random.seed(0)
    cfg = CFG[which]
    src, out = Path(src), Path(out)
    man, blob = P5.load_page(src, cfg["stem"])
    S = P5.decode(man, blob)
    ids = set(S)
    # ---- the organs in this page's frame
    if which == "comb_f":
        z = np.load(REPO / "data/derived/Q233_organs_vhf.npz")
        reg = json.loads((REPO / "data/derived/Q233_hra_to_vhf_transform.json").read_text())
        organs = {sid: (z[sid + "_v"].astype(float), z[sid + "_f"]) for sid, *_ in ORGANS}
        info = {}
        reg_txt = (f"registered onto HER OWN CT pelvis (hip bones, sacrum, coccyx; rigid + uniform scale x{reg['scale']}, surface residual median {reg['residual_mm']['median']} mm, p90 {reg['residual_mm']['p90']}) -- "
                   f"the same five meshes, in the same coordinates, as on the Imaging-based female page")
    else:
        pts_src = Q.load(which)
        T = H.register_to(pts_src)
        s, R, t, d = T
        reg = dict(scale=round(float(s), 5), residual_mm=dict(median=round(float(np.median(d)), 2), p90=round(float(np.quantile(d, .9)), 2), rms=round(float(np.sqrt((d ** 2).mean())), 2), max=round(float(d.max()), 1)),
                   rotation=R.round(6).tolist(), translation_mm=t.round(3).tolist(), det_R=round(float(np.linalg.det(R)), 4))
        organs, info = {}, {}
        for sid, obj, side, name, latin, pitch, clo, ntri in ORGANS:
            V, F, inf = H.closed_surface(H.parts_world(obj, T), pitch=pitch, close_it=clo)
            V, F = decimate(V, F, ntri)
            m = trimesh.Trimesh(V, F, process=True); trimesh.repair.fix_normals(m)
            organs[sid] = (np.asarray(m.vertices), np.asarray(m.faces)); info[sid] = inf
        reg_txt = (f"registered (rigid + uniform scale x{reg['scale']}: this page's body is smaller than the donor) by ICP of the HRA VH_F pelvis onto THIS page's Z-Anatomy pelvis bones; "
                   f"surface residual median {reg['residual_mm']['median']} mm, p90 {reg['residual_mm']['p90']}, rms {reg['residual_mm']['rms']} mm -- the residual mostly measures that the Z-Anatomy pelvis is MALE-derived "
                   f"and the donor's is female, so the organs' position relative to these bones is approximate")
    # ---- guards against this page
    allv = np.vstack([v for v, _ in organs.values()])
    lo = allv.min(0) - 14; hi = allv.max(0) + 14
    pitch = 1.0; shape = tuple(np.ceil((hi - lo) / pitch).astype(int))
    skin_pts = np.vstack([trimesh.Trimesh(e["v"], e["f"], process=False).sample(20000) for i, e in S.items() if e["m"]["sys"] == "skin" and len(e["f"])])
    skin_tree = cKDTree(skin_pts)
    bone_pts = np.vstack([trimesh.Trimesh(e["v"], e["f"], process=False).sample(6000) for i, e in S.items() if e["m"]["sys"] == "bone" and len(e["f"]) > 20 and not ((e["v"].max(0) < lo).any() or (e["v"].min(0) > hi).any())])
    bone_tree = cKDTree(bone_pts)
    near = {}
    for i, e in S.items():
        v = e["v"]
        if len(v) == 0 or e["m"]["sys"] == "skin" or (v.max(0) < lo).any() or (v.min(0) > hi).any() or len(e["f"]) < 8:
            continue
        near[i] = mask_of(v, e["f"], lo, shape, pitch)
    report, add = {}, []
    for sid, obj, side, name, latin, p_, c_, nt in ORGANS:
        V, F = organs[sid]
        m = trimesh.Trimesh(V, F, process=False)
        vol = float(abs(m.volume)) / 1000
        mk = mask_of(V, F, lo, shape, pitch)
        mkvol = float(mk.sum()) * pitch ** 3 / 1000
        ov = {i: round(float((mk & g).sum()) * pitch ** 3 / 1000, 3) for i, g in near.items() if (mk & g).sum()}
        ov_by_sys = {}
        for i, x in ov.items():
            ov_by_sys.setdefault(S[i]["m"]["sys"], 0.0); ov_by_sys[S[i]["m"]["sys"]] += x
        frac = round(100 * sum(ov.values()) / max(mkvol, 1e-9), 2)
        db = bone_tree.query(V)[0]
        # inside the skin: the organs are deep (nearest skin point far) and the page's skin encloses the pelvis: nearest-skin distance as the proxy plus the body's own box
        dskin = float(skin_tree.query(V)[0].min())
        g = dict(volume_cm3=round(vol, 2), voxel_mask_cm3=round(mkvol, 2), skin_distance_min_mm=round(dskin, 1), bone_min_mm=round(float(db.min()), 2), vertices_within_1mm_of_bone=int((db < 1).sum()),
                 overlap_cm3=ov, overlap_by_system_cm3={k: round(v, 3) for k, v in ov_by_sys.items()}, overlap_total_pct_of_mask=frac, watertight=bool(m.is_watertight), triangles=int(len(F)))
        g["soft_overlap_flag_gt10pct"] = bool(frac > 10.0)         # reported, NOT a gate: the Z-Anatomy soft structures are estimates (fit error ~10 mm), the HRA organ sits on measured pelvic bone (~1-2 mm)
        g["pass"] = bool(dskin >= 20 and g["bone_min_mm"] >= 0.5)
        report[sid] = dict(hra_object=obj, gates=g, **({"envelope": info[sid]} if sid in info else {}))
        print(which, sid, g["volume_cm3"], "cm3", "bone", g["bone_min_mm"], "overlap %", frac, "PASS" if g["pass"] else "HELD", flush=True)
        if not g["pass"]:
            report[sid]["held"] = True; continue
        who = "her own" if which == "comb_f" else "this body's"
        badge = (f"Reference organ of the SAME DONOR as the Visible Human female (HuBMAP HRA 3D reference object `{obj}`, v1.3, CC BY 4.0, Browne and Schlehlein; built from the National Library of Medicine Visible Human "
                 f"FEMALE data), NOT part of Z-Anatomy (Z-Anatomy has no female reproductive organ) and NOT measured by this atlas: closed envelope of the HRA surfaces (voxel fill, {len(F)} triangles, volume "
                 f"{g['volume_cm3']} cm3; hollow structures are shown solid), {reg_txt}. Guards (Q233): {g['skin_distance_min_mm']} mm from the skin, {g['bone_min_mm']} mm from the nearest displayed bone, "
                 f"overlap with the page's Z-Anatomy soft structures (fit ESTIMATES, error about 10 mm, so they give way to the organ placed on measured bone) {frac} % of the organ ({', '.join(f'{k} {v} cm3' for k, v in g['overlap_by_system_cm3'].items()) or 'none'}); nothing was pushed or deformed. "
                 f"The Z-Anatomy structures around it are the male-derived body fitted to the page's bones, so contact with them is approximate. The vagina, vulva, uterine / ovarian ligaments and the mammary gland are NOT in "
                 f"the HRA set and are not drawn.")
        rec = dict(name=name, latin=latin, folder="viscera", region="pelvis",
                   source="HuBMAP HRA 3D Reference Object Library v1.3 (CC BY 4.0), Visible Human female; registered on this page's pelvis (Q233)", procedural_badge=badge)
        ent = {"name": name, "id": sid, "side": side_code(side), "sys": "viscera", "rec": rec}
        add.append((ent, V, F))
    # ---- card-only honesty notes on the page's own pelvis bones / urogenital closure
    meta = {}
    note_bones = (f" Q233 sex audit: this {'Z-Anatomy pelvic bone fitted to her skeleton' if which == 'comb_f' else 'Z-Anatomy pelvic bone'} derives from the single male body of Z-Anatomy / BodyParts3D; "
                  f"measured on the meshes, see data/derived/Q233_sex_audit.json (subpubic angle, sciatic notch, ischiopubic index).")
    for i in ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx"):
        if i in S:
            rec = dict(S[i]["m"].get("rec") or {})
            rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + note_bones).strip()
            meta[i] = (S[i]["m"]["name"], rec)
    man = dict(man); man["attribution"] = (man.get("attribution") or "").rstrip() + " " + HRA_ATTR      # CC BY 4.0 attribution of the added organs, kept on the page
    P5.save_page(out, cfg["stem"], man, blob, add=add, meta=meta)
    for f in src.glob("clinical_*"):
        import shutil; shutil.copy2(f, out / f.name)
    r = SD.diff(src, out, cfg["stem"], [])
    listed_added = sorted(e["id"] for e, _, _ in add)
    diff = dict(source=str(src), new=str(out), added=r["added"], added_expected=listed_added, removed=r["removed"], geometry_changed=sorted(r["geometry_changed"]), card_only=sorted(r["card_only"]),
                card_only_expected=sorted(meta), unchanged=r["unchanged"], unlisted=sorted(set(r["added"]) ^ set(listed_added)) + sorted(set(r["card_only"]) - set(meta)) + sorted(r["geometry_changed"]) + sorted(r["removed"]))
    rep = dict(page=which, registration=reg, organs=report, subject_text=HRA_ATTR, ship_diff=diff)
    (REPO / f"data/derived/Q233_report_{which}.json").write_text(json.dumps(rep, indent=1, default=float) + "\n")
    (REPO / f"data/derived/Q233_vertex_diff_{which}.json").write_text(json.dumps(diff, indent=1) + "\n")
    print(which, "ship diff: added", len(diff["added"]), "card_only", len(diff["card_only"]), "geometry_changed", len(diff["geometry_changed"]), "removed", len(diff["removed"]), "unlisted", diff["unlisted"], "unchanged", diff["unchanged"])
    sys.exit(1 if diff["unlisted"] else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("which", choices=list(CFG)); ap.add_argument("--src"); ap.add_argument("--out"); a = ap.parse_args()
    c = CFG[a.which]
    run(a.which, a.src or str(REPO / c["src"]), a.out or str(REPO / c["out"]))
