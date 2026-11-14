#!/usr/bin/env python3
"""Q234 (Z pages, female): add the female structures the Z-Anatomy source does not have -- vagina, ligaments of the uterus and ovaries, both breasts (fat pad, mammary gland lobes, lactiferous ducts + sinuses, areola, nipple,
suspensory ligaments) -- from the HuBMAP HRA 3D Reference Object Library objects of the Visible Human FEMALE (CC BY 4.0), as in-process patch of the Q233 pre-page (untouched structures byte for byte, ship diff 0 unlisted).
    python3 scripts/zanatomy/q234_z_female.py comb_f [--src build/q233_pre/viewer_zan_female] [--out build/q234_pre/viewer_zan_female]
    python3 scripts/zanatomy/q234_z_female.py base_f [--src build/q233_pre/viewer_base_female] [--out build/q234_pre/viewer_base_female]
comb_f: pelvic structures with the Q233 registration on her CT pelvis (same transform as the uterus there); breasts: HRA thoracic vertebrae onto the page's thoracic vertebrae + fit into the page's skin envelope.
base_f: pelvic structures with the Q233 registration on the Z pelvis (scale x0.817, male-derived bones); breasts as above on the Z thorax.
Gates: pelvic: >= 15 mm inside the skin, out of the page's bones; breasts: inside the page's skin, anterior to the pectoralis major, out of ribs / cartilage / sternum / clavicle / scapula (signed distance fields).
Overlaps with the page's own Z-Anatomy soft structures are REPORTED (they are fit estimates), not gated. Held structures are not added."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np, trimesh

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
from scripts.anatomy.q234 import hra_q234 as Q, place as PL  # noqa: E402

CFG = {
    "comb_f": dict(src="build/q233_pre/viewer_zan_female", stem="atlas_viewer_zan_female", out="build/q234_pre/viewer_zan_female"),
    "base_f": dict(src="build/q233_pre/viewer_base_female", stem="atlas_viewer_base_female", out="build/q234_pre/viewer_base_female"),
}
HRA_ATTR = (PL.CITE + ". Registered onto this page's body by this atlas (Q234); derived data, CC BY 4.0 attribution kept (third_party/hra_vh_f/NOTICE.md).")
OLD_TAIL = ("The vagina, vulva, uterine / ovarian ligaments and the mammary gland are NOT in "
            "the HRA set and are not drawn.")
NEW_TAIL = "The vagina, the ligaments of the uterus and ovary and the breasts were added in Q234 as separate structures. " + PL.ABSENT
SIDE = {"left": "l", "right": "r", None: "m"}
SYS = {"organ": "viscera", "ligament": "joint"}


def pick(S, pred):
    return [(i, e["v"], e["f"]) for i, e in S.items() if len(e["f"]) >= 6 and pred(i, e)]


def run(which, src, out):
    np.random.seed(0)
    import os
    if os.environ.get("Q233_ZAN_TEMPLATE"):
        P5.B.TEMPLATE_PATH = Path(os.environ["Q233_ZAN_TEMPLATE"])
    cfg = CFG[which]
    src, out = Path(src), Path(out)
    man, blob = P5.load_page(src, cfg["stem"])
    S = P5.decode(man, blob)
    M, anchor, info = Q.load()
    if which == "comb_f":
        reg0 = json.loads((REPO / "data/derived/Q233_hra_to_vhf_transform.json").read_text())
        reg0_txt = (f"HRA VH_F pelvis registered onto HER OWN CT pelvis (hip bones, sacrum, coccyx; rigid + uniform scale x{reg0['scale']}, surface residual median {reg0['residual_mm']['median']} mm, "
                    f"p90 {reg0['residual_mm']['p90']}), the same transform as the uterus of this page")
    else:
        reg0 = json.loads((REPO / "data/derived/Q233_report_base_f.json").read_text())["registration"]
        reg0_txt = (f"HRA VH_F pelvis registered (rigid + uniform scale x{reg0['scale']}: this page's body is smaller than the donor) onto THIS page's Z-Anatomy pelvis bones, surface residual median "
                    f"{reg0['residual_mm']['median']} mm, p90 {reg0['residual_mm']['p90']}, rms {reg0['residual_mm']['rms']} -- the residual mostly measures that the Z-Anatomy pelvis is MALE-derived and the donor's is female, "
                    f"the same transform as the uterus of this page")
    T0 = (reg0["scale"], np.array(reg0["rotation"]), np.array(reg0["translation_mm"]))
    # ---- page evidence
    skin_parts = pick(S, lambda i, e: e["m"]["sys"] == "skin")
    sv = np.vstack([v for _, v, _ in skin_parts]); sf = np.vstack([f + o for (_, v, f), o in zip(skin_parts, np.cumsum([0] + [len(v) for _, v, _ in skin_parts[:-1]]))])
    skin_depth = trimesh.Trimesh(sv, sf, process=False).sample(120000)
    from scipy.spatial import cKDTree
    sk_tree = cKDTree(skin_depth)
    pel_lo, pel_hi = np.array([-130, -100, -150.]), np.array([130, 130, 110.])
    inbox = lambda e: not ((e["v"].max(0) < pel_lo).any() or (e["v"].min(0) > pel_hi).any())  # noqa: E731
    bone_meshes = [trimesh.Trimesh(e["v"], e["f"], process=False) for i, e in S.items() if e["m"]["sys"] == "bone" and len(e["f"]) > 20 and inbox(e) and not i.startswith(("zan_rib", "ribs"))]
    ev = {}
    for key, ids in (("urinary_bladder", ("urinary_bladder", "zan_urinary_bladder")), ("rectum", ("rectum", "zan_rectum")), ("sigmoid_colon", ("sigmoid_colon", "zan_sigmoid_colon")), ("uterus", ("uterus",))):
        for i in ids:
            if i in S and len(S[i]["f"]):
                ev[key] = (S[i]["v"], S[i]["f"]); break
    pel = PL.pelvic_place(M, info, T0, ev, bone_meshes, lambda V: round(float(sk_tree.query(V)[0].min()), 1), gate_soft=False)
    # ---- thorax evidence
    vert = [trimesh.Trimesh(e["v"], e["f"], process=False).sample(30000) for i, e in S.items() if i.startswith("zan_vertebra_t") and len(e["f"])]
    groups = {"pec": [], "bone": [], "muscle": []}
    box_lo, box_hi = np.array([-300, 230, -80.]), np.array([300, 640, 200.])
    for i, e in S.items():
        if len(e["f"]) < 6 or e["m"]["sys"] not in ("muscle", "bone", "cartilage") or (e["v"].max(0) < box_lo).any() or (e["v"].min(0) > box_hi).any():
            continue
        if "pectoralis_major" in i:
            groups["pec"].append((i, e["v"], e["f"]))
        elif e["m"]["sys"] in ("bone", "cartilage"):
            groups["bone"].append((i, e["v"], e["f"]))
        elif e["v"][:, 2].max() > -60:
            groups["muscle"].append((i, e["v"], e["f"]))
    print(which, "thorax evidence: vertebrae", len(vert), "pec", len(groups["pec"]), "bone", len(groups["bone"]), "muscle", len(groups["muscle"]), flush=True)
    br = PL.breast_place(M, info, anchor, np.vstack(vert), (sv, sf), groups, gate_muscle=False)      # the Z-Anatomy muscles are fit estimates: distances reported, not gated
    T, reg = br["thorax"]
    print(which, "thorax registration", reg["scale"], reg["residual_mm"], flush=True)
    # ---- assemble
    who = "this page's"
    report, add = {}, []
    for sid, (V, F, g) in pel.items():
        inf = info[sid]
        report[sid] = dict(hra_object=inf["hra_file"], mode=inf["mode"], gates=g)
        print(which, sid, g.get("volume_cm3"), "bone", g["bone_min_mm"], "skin", g["skin_distance_min_mm"], "PASS" if g["pass"] else "HELD", flush=True)
        if not g["pass"]:
            report[sid]["held"] = True; continue
        rec = dict(name=inf["name"], latin=inf["latin"], folder=inf["folder"], region=inf["region"],
                   source="HuBMAP HRA 3D Reference Object Library v1.2 (CC BY 4.0), object of the Visible Human female frame; registered on this page's pelvis (Q234)",
                   procedural_badge=PL.pelvic_badge(sid, inf, g, reg0_txt, who) + " Z-Anatomy has no such structure; the Z-Anatomy structures around it are the page's own fits, so contact with them is approximate.")
        add.append(({"name": inf["name"], "id": sid, "side": SIDE[inf["side"]], "sys": SYS[inf["cat"]], "rec": rec}, V, F))
    for side in ("l", "r"):
        s = br["sides"][side]
        for sid, (V, F, g) in s["parts"].items():
            inf = info[sid]
            report[sid] = dict(hra_object=inf["hra_file"], mode=inf["mode"], gates=g)
            print(which, sid, g.get("volume_cm3"), "skin", g["skin_inside_min_mm"], "pec", g["pectoralis_major_min_mm"], "bone", g["bone_min_mm"], "muscle", g["other_muscle_min_mm"], "PASS" if g["pass"] else "HELD " + g.get("held_reason", ""), flush=True)
            if not g["pass"]:
                report[sid]["held"] = True; continue
            rec = dict(name=inf["name"], latin=inf["latin"], folder=inf["folder"], region="breast",
                       source="HuBMAP HRA 3D Reference Object Library v1.3 (CC BY 4.0), sculpted reference model (not donor data); fitted into this page's skin envelope on its chest wall (Q234)",
                       procedural_badge=PL.breast_badge(sid, inf, g, reg, s["warp"], s["push_history"], who, "this page's", z=True))
            add.append(({"name": inf["name"], "id": sid, "side": SIDE[inf["side"]], "sys": SYS[inf["cat"]], "rec": rec}, V, F))
    # ---- card-only: the Q233 organs' sentence about what is absent
    meta = {}
    for i, e in S.items():
        b = (e["m"].get("rec") or {}).get("procedural_badge") or ""
        if i in ("uterus", "ovary_l", "ovary_r", "uterine_tube_l", "uterine_tube_r") and OLD_TAIL.replace("  ", " ") in " ".join(b.split()):
            rec = dict(e["m"]["rec"]); rec["procedural_badge"] = " ".join(b.split()).replace(OLD_TAIL, NEW_TAIL)
            meta[i] = (e["m"]["name"], rec)
    man = dict(man); man["attribution"] = (man.get("attribution") or "").rstrip() + " " + HRA_ATTR
    P5.save_page(out, cfg["stem"], man, blob, add=add, meta=meta)
    for f in src.glob("clinical_*"):
        import shutil; shutil.copy2(f, out / f.name)
    r = SD.diff(src, out, cfg["stem"], [])
    listed_added = sorted(e["id"] for e, _, _ in add)
    rel = lambda p: str(p.resolve().relative_to(REPO)) if str(p.resolve()).startswith(str(REPO)) else str(p)  # noqa: E731
    diff = dict(source=rel(src), new=rel(out), added=r["added"], added_expected=listed_added, removed=r["removed"], geometry_changed=sorted(r["geometry_changed"]), card_only=sorted(r["card_only"]),
                card_only_expected=sorted(meta), unchanged=r["unchanged"], unlisted=sorted(set(r["added"]) ^ set(listed_added)) + sorted(set(r["card_only"]) - set(meta)) + sorted(r["geometry_changed"]) + sorted(r["removed"]))
    rep = dict(page=which, pelvis_registration=reg0, thorax_registration=reg, structures=report, warp={s: br["sides"][s]["warp"] for s in ("l", "r")}, push_history={s: br["sides"][s]["push_history"] for s in ("l", "r")},
               attribution=HRA_ATTR, ship_diff=diff)
    (REPO / f"data/derived/Q234_report_{which}.json").write_text(json.dumps(rep, indent=1, default=float) + "\n")
    (REPO / f"data/derived/Q234_vertex_diff_{which}.json").write_text(json.dumps(diff, indent=1) + "\n")
    print(which, "ship diff: added", len(diff["added"]), "card_only", len(diff["card_only"]), "geometry_changed", len(diff["geometry_changed"]), "removed", len(diff["removed"]), "unlisted", diff["unlisted"], "unchanged", diff["unchanged"])
    sys.exit(1 if diff["unlisted"] else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("which", choices=list(CFG)); ap.add_argument("--src"); ap.add_argument("--out"); a = ap.parse_args()
    c = CFG[a.which]
    run(a.which, a.src or str(REPO / c["src"]), a.out or str(REPO / c["out"]))
