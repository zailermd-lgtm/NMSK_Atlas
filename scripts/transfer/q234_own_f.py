#!/usr/bin/env python3
"""Q234 (own female): her Q233 bundle (build/viewer_f_hr_q233) -> build/viewer_f_hr_q234.
 ADDS the female structures her CT has no label for, from the HuBMAP HRA 3D Reference Object Library objects of the SAME DONOR (Visible Human female, CC BY 4.0), as separate structures:
   vagina, the ligaments of the uterus and ovaries (round, uterosacral, cardinal, broad, ovarian, suspensory of the ovary, mesosalpinx, mesovarium) with the page's pelvis registration of Q233 (the same transform as her
   uterus / ovaries / tubes), and both breasts (fat pad, mammary gland lobes, lactiferous ducts + sinuses, areola, nipple, suspensory ligaments) with a thoracic registration (HRA thoracic vertebrae onto her thoracic
   vertebrae) and a fit into HER skin envelope (chestfit.py).
 Card-only change: the five Q233 organs' badges no longer say that the vagina / ligaments are absent.
 Every other entry is byte-identical (ship diff data/derived/Q234_vertex_diff_f.json, exit 1 on any unlisted change).
    python3 scripts/transfer/q234_own_f.py [--out build/viewer_f_hr_q234]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.anatomy.q234 import hra_q234 as Q, place as PL  # noqa: E402

SUBJECT = "xfer_hra2vhf_q234"                      # vagina + ligaments (reference structures of the VH female frame)
SUBJECT_BREAST = "xfer_hrasculpt2vhf_q234"         # breasts: sculpted reference model, NOT donor data (own template class reference_model)
ATTR = (PL.CITE + ". Registered onto her own CT by this atlas (Q234: vagina and ligaments with the Q233 pelvis registration; breasts with a thoracic registration and a fit into her skin envelope); "
        "derived data, CC BY 4.0 attribution kept (third_party/hra_vh_f/NOTICE.md).")
OLD_TAIL = "The vagina, vulva and ligaments of the uterus / ovary are NOT in the HRA set and not built."
NEW_TAIL = "The vagina and the ligaments of the uterus and ovary were added in Q234 as separate structures (same registration). " + PL.ABSENT
SRC = "build/viewer_f_hr_q233"
CHEST_IDS = lambda e: e["cat"] in ("bone", "muscle") and not e["subject"].startswith("xfer_hra")  # noqa: E731


def keyed(B):
    seen, out, order = {}, {}, []
    for it in B.items:
        i = it["e"]["id"]; k = (i, seen.get(i, 0)); seen[i] = seen.get(i, 0) + 1; out[k] = it; order.append(k)
    return out, order


def main(out_dir, src=SRC):
    np.random.seed(0)
    B = Bundle(REPO / src); A0 = Bundle(REPO / src)
    M, anchor, info = Q.load()
    r33 = json.loads((REPO / "data/derived/Q233_hra_to_vhf_transform.json").read_text())
    T0 = (r33["scale"], np.array(r33["rotation"]), np.array(r33["translation_mm"]))
    # ---- evidence
    bone_meshes, ev, vert, groups = [], {}, [], {"pec": [], "bone": [], "muscle": []}
    for it in B.items:
        e = it["e"]
        v, f = B.mesh(it)
        if e["cat"] == "bone" and e["id"].split("#")[0] in ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx", "femur_l", "femur_r") and "zfill" not in e["id"] and e["subject"] != "xfer_vhm2vhf":
            bone_meshes.append(trimesh.Trimesh(v, f, process=False))
        if e["id"] in ("urinary_bladder", "rectum", "sigmoid_colon", "levator_ani_l", "levator_ani_r", "coccygeus_l", "coccygeus_r", "uterus") and e["id"] not in ev:
            ev[e["id"]] = (v, f)
        if e["id"] == "thoracic_vertebrae" and e["subject"] == "ct_vhf" and v[:, 1].min() > 295:
            vert.append(trimesh.Trimesh(v, f, process=False).sample(30000))
        if CHEST_IDS(e) and len(v) and v[:, 2].max() > -60 and v[:, 1].max() > 230 and v[:, 1].min() < 640:
            g = "bone" if e["cat"] == "bone" else ("pec" if e["id"].startswith("pectoralis_major") else "muscle")
            groups[g].append((e["id"], v, f))
    skin = B.get("skin")
    # ---- pelvic structures
    pel = PL.pelvic_place(M, info, T0, ev, bone_meshes, lambda V: B._depth(V)[0])
    reg_txt = (f"HRA VH_F pelvis registered onto her own CT pelvis (hip bones, sacrum, coccyx; rigid + uniform scale x{r33['scale']}, surface residual median {r33['residual_mm']['median']} mm, p90 {r33['residual_mm']['p90']}, "
               f"rms {r33['residual_mm']['rms']}), a bone-based estimate")
    # ---- breasts
    br = PL.breast_place(M, info, anchor, np.vstack(vert), (skin["v"], skin["f"]), groups)
    T, reg = br["thorax"]
    print("thorax registration", reg["scale"], reg["residual_mm"], flush=True)
    new, report = [], {}
    for sid, (V, F, g) in pel.items():
        inf = info[sid]
        report[sid] = dict(hra_object=inf["hra_file"], mode=inf["mode"], gates=g)
        print(sid, g.get("volume_cm3"), g["bone_min_mm"], g["bladder_rectum_sigmoid_pct_of_vertices"], "PASS" if g["pass"] else "HELD", flush=True)
        if not g["pass"]:
            report[sid]["held"] = True; continue
        rec = dict(name=inf["name"], latin=inf["latin"], folder=inf["folder"], region=inf["region"],
                   source="HuBMAP HRA 3D Reference Object Library v1.2 (CC BY 4.0), object of the Visible Human female frame; registered on her CT pelvis (Q234)", procedural_badge=PL.pelvic_badge(sid, inf, g, reg_txt, "her"))
        new.append((sid, inf["cat"], inf["side"], rec, V, F))
    for side in ("l", "r"):
        s = br["sides"][side]
        for sid, (V, F, g) in s["parts"].items():
            inf = info[sid]
            report[sid] = dict(hra_object=inf["hra_file"], mode=inf["mode"], gates=g)
            print(sid, g.get("volume_cm3"), "skin", g["skin_inside_min_mm"], "pec", g["pectoralis_major_min_mm"], "bone", g["bone_min_mm"], "PASS" if g["pass"] else "HELD " + g.get("held_reason", ""), flush=True)
            if not g["pass"]:
                report[sid]["held"] = True; continue
            rec = dict(name=inf["name"], latin=inf["latin"], folder=inf["folder"], region="breast",
                       source="HuBMAP HRA 3D Reference Object Library v1.3 (CC BY 4.0), sculpted reference model (not donor data); fitted into her skin envelope on her chest wall (Q234)",
                       procedural_badge=PL.breast_badge(sid, inf, g, reg, s["warp"], s["push_history"], "her", "her"))
            new.append((sid, inf["cat"], inf["side"], rec, V, F))
    # ---- apply
    for sid, cat, side, rec, V, F in new:
        B.add(sid, cat, side, SUBJECT_BREAST if info[sid]['region'] == 'breast' else SUBJECT, rec, V, F)
    card_only = []
    for it in B.items:
        e = it["e"]
        if e["subject"] == "xfer_hra2vhf_q233" and OLD_TAIL in (e["rec"].get("procedural_badge") or ""):
            e["rec"] = {**e["rec"], "procedural_badge": e["rec"]["procedural_badge"].replace(OLD_TAIL, NEW_TAIL)}
            card_only.append(e["id"])
    n_bytes = B.write(out_dir, new_subject_attribution={SUBJECT: ATTR, SUBJECT_BREAST: ATTR}, copy_clinical=True)
    # ---- ship diff
    N = Bundle(out_dir)
    Ak, Ao = keyed(A0); Nk, No = keyed(N)
    ident, unlisted, bad = 0, [], []
    for k in Ao:
        if k not in Nk:
            bad.append(f"{k} missing"); continue
        a, n = Ak[k], Nk[k]
        if a["raw"] == n["raw"] and a["e"] == n["e"]:
            ident += 1
        elif a["raw"] == n["raw"] and k[0] in card_only:
            pass
        else:
            unlisted.append(k[0])
    added = [k[0] for k in Nk if k not in Ak]
    diff = dict(source=src, new=str(Path(out_dir).resolve().relative_to(REPO)), entries_old=len(A0.items), entries_new=len(N.items), identical=ident, removed=[], added=added, card_only=card_only, unlisted_changes=unlisted,
                problems=bad, triangles_old=A0.j["triangles"], triangles_new=N.j["triangles"], bundle_bytes_added=int(n_bytes - sum(len(it["raw"]) for it in A0.items)))
    (REPO / "data/derived/Q234_vertex_diff_f.json").write_text(json.dumps(diff, indent=1) + "\n")
    rep = dict(pelvis_registration=r33, thorax_registration=reg, structures=report, warp={s: br["sides"][s]["warp"] for s in ("l", "r")}, push_history={s: br["sides"][s]["push_history"] for s in ("l", "r")},
               subjects=[SUBJECT, SUBJECT_BREAST], attribution=ATTR, hra_commit=Q.COMMIT, hra_files="third_party/hra_vh_f/SOURCES_Q234.json")
    (REPO / "data/derived/Q234_report_own_f.json").write_text(json.dumps(rep, indent=1, default=float) + "\n")
    print("ship diff:", {k: (v if not isinstance(v, list) else len(v)) for k, v in diff.items() if k in ("entries_old", "entries_new", "identical", "removed", "added", "card_only", "unlisted_changes", "problems", "triangles_new", "bundle_bytes_added")})
    sys.exit(1 if (unlisted or bad) else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(REPO / "build/viewer_f_hr_q234")); a = ap.parse_args()
    main(a.out)
