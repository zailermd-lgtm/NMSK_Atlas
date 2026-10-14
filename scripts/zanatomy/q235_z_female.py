#!/usr/bin/env python3
"""Q235 (Z pages, female): add the vulvar / perineal / urethral structures of the Chinese Visible Human young adult female (Wu et al. 2015, CC BY 4.0; third_party/cvh_wu2015) to the Q234 pre-page as in-process patch
(untouched structures byte for byte, ship diff 0 unlisted). Structures that fail a guard are not added.
    python3 scripts/zanatomy/q235_z_female.py comb_f [--src build/q234_pre/viewer_zan_female] [--out build/q235_pre/viewer_zan_female]
    python3 scripts/zanatomy/q235_z_female.py base_f        -> report only if the registration is unsound (the male-derived pelvis): no page is built
comb_f: the registration of the Imaging-based page (her CT frame; the Combined page is the Z body fitted to HER skeleton) evaluated against THIS page's Z-Anatomy bones.
base_f: the CVH bones are fitted to the Z male-derived pelvis; if a bone-attached structure (clitoral crura, ischiocavernosus) or the bulbospongiosus fails the bone guard, the page is skipped."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
from scripts.anatomy.q235 import core as C, evidence, structs as ST, place as PL, cvh, fit as Fm  # noqa: E402

CFG = {
    "comb_f": dict(src="build/q234_pre/viewer_zan_female", stem="atlas_viewer_zan_female", out="build/q235_pre/viewer_zan_female", label="Combined female"),
    "base_f": dict(src="build/q234_pre/viewer_base_female", stem="atlas_viewer_base_female", out="build/q235_pre/viewer_base_female", label="Base female"),
}
HRA_ATTR = (C.CITE + ". Registered onto this page's body by this atlas (Q235; bones only, rigid + uniform scale); derived data (triangles re-oriented, components below 100 triangles dropped, the urethral lumen cut and capped), "
            "CC BY 4.0 attribution kept (third_party/cvh_wu2015/NOTICE.md). Not endorsed by the authors or PLOS.")
SIDE = {"left": "l", "right": "r", None: "m"}
SYS = {"organ": "viscera", "muscle": "muscle"}
BONE_ATTACHED = ("clitoris_cavernous_body", "ischiocavernosus_cvh_l", "ischiocavernosus_cvh_r", "bulbospongiosus_cvh")


def run(which, src, out):
    np.random.seed(0)
    cfg = CFG[which]
    src, out = Path(src), Path(out)
    tr = json.loads((REPO / "data/derived/Q235_cvh_to_vhf_transform.json").read_text())
    sx = int(tr["chosen_sx"])
    ev, (man, blob, S) = evidence.z_evidence(src, cfg["stem"])
    dst = Fm.page_bone_points(ev)
    if which == "comb_f":
        T = (tr["scale"], np.array(tr["rotation"]), np.array(tr["translation_mm"]))
        reg = dict(source="the registration of the Imaging-based page (her CT frame, data/derived/Q235_cvh_to_vhf_transform.json)", transform=C.regs(T))
    else:
        T, aux = C.fit_page(ev, sx)
        reg = dict(source="fitted to this page's Z-Anatomy pelvis (bones only)", transform=C.regs(T), start_pitch_yaw=aux["start"])
    res = C.regional(T, ev, sx)
    inf = C.inferior_residual(T, ev, sx, dst)
    cross = C.crosscheck(ev, T, sx)
    print(which, "scale", round(T[0], 4), "residual", res["all CVH bone vertices"], "inferior", inf, flush=True)
    run_ = C.run_page(ev, T, sx)
    items = run_["items"]; s = T[0]
    report, shipped, held = {}, [], []
    for it in items:
        sid = C.make_id(it["key"], it["side"]); g = it["gates"]
        report[sid] = dict(cvh_index=it["info"]["cvh_index"], cvh_name=C.CVH_NAME[it["key"]], side=it["side"], gates=g, info={k: v for k, v in it["info"].items() if k != "components"}, components=it["info"].get("components"),
                           volume_page_cm3=round(it["info"]["volume_cvh_cm3"] * s ** 3, 3), area_page_cm2=round(it["info"]["area_cvh_cm2"] * s ** 2, 2))
        print(which, sid, "PASS" if g["pass"] else "HELD " + str(g["fail_reasons"]), flush=True)
        if g["pass"]:
            shipped.append((sid, it))
        else:
            held.append(sid)
    skipped_page = None
    if which == "base_f" and any(h in held for h in BONE_ATTACHED):
        skipped_page = ("SKIPPED: the registration is not sound on this page. The male-derived Z pelvis (Q233: subpubic angle 57 deg, male range) does not accept the female CVH ischiopubic arch: after the best bone fit "
                        f"(rigid + uniform scale x{round(T[0], 3)}; inferior-pelvis residual median {inf['median']} mm, p90 {inf['p90']} mm; all CVH bone vertices median {res['all CVH bone vertices']['median']}, p90 {res['all CVH bone vertices']['p90']}) "
                        f"the bone-attached structures {[h for h in held if h in BONE_ATTACHED]} fail the bone guard (penetration of the ischiopubic rami / pubic arch beyond the allowed shift), so every structure placed by the same transform is "
                        "unreliable on this page; nothing was added.")
        print(skipped_page)
    cfg_rep = dict(page=which, label=cfg["label"], registration=reg, residual_mm=res, inferior_pelvis_mm=inf, crosscheck=cross, order_checks=run_["order"], structures=report, shipped=sorted(s_ for s_, _ in shipped), held=held,
                   skipped_page=skipped_page, tolerances=dict(soft_tolerance_mm=PL.SOFT_TOL_MM, soft_max_share_deeper_pct=PL.SOFT_MAX_PCT_DEEP, bone_min_free_mm=PL.BONE_MIN_FREE, bone_min_attach_mm=PL.BONE_MIN_ATTACH, max_shift_mm=PL.MAX_SHIFT_MM,
                   max_shift_fraction=PL.MAX_SHIFT_FRAC, skin_min_mm=PL.SKIN_MIN_MM), not_shipped_by_choice=C.NOT_SHIPPED, attribution=HRA_ATTR)
    if skipped_page:
        (REPO / f"data/derived/Q235_report_{which}.json").write_text(json.dumps(cfg_rep, indent=1, default=float) + "\n")
        print(which, "no page built"); return 0
    who = "this page's"
    if which == "comb_f":
        reg_txt = (f"Registration (bones only, Q235): the CVH pelvic bone and the closed sacrum + coccyx mesh onto HER OWN CT pelvis (the Imaging-based page; this Combined page is the Z-Anatomy body fitted bone by bone to HER skeleton, so the same transform "
                   f"is used), rigid + uniform scale x{round(T[0], 4)} (the CVH pelvis is {round(100 * (1 - 1 / T[0]))} % smaller than hers); residual against HER bones median {tr['residual_mm']['all CVH bone vertices']['median']} mm, p90 "
                   f"{tr['residual_mm']['all CVH bone vertices']['p90']} mm (pubic arch median {tr['residual_mm'][C.ARCH_KEY]['median']} / p90 {tr['residual_mm'][C.ARCH_KEY]['p90']} mm); against THIS page's Z-Anatomy bones (themselves fits to her skeleton) "
                   f"median {res['all CVH bone vertices']['median']} mm, p90 {res['all CVH bone vertices']['p90']} mm (pubic arch median {res[C.ARCH_KEY]['median']} / p90 {res[C.ARCH_KEY]['p90']}; the Z hip bones lack the medial pubic faces, so the symphysis region "
                   f"reads {res['pubic symphysis region (|x-184|<8)']['median']} mm). The soft organs of the CVH woman are NOT where hers are (CVH bladder wall / vaginal wall differ from the page's bladder / the HRA vagina by "
                   f"{cross['bladder wall (CVH 27) vs page bladder']['sym_nn_median_mm']} / {cross['vaginal wall (CVH 21) vs HRA vagina']['sym_nn_median_mm']} mm median nearest-neighbour distance: individual differences, not registration error), so the soft tissue "
                   f"relations come from the CVH woman and are only registered by bones.")
        skin_text = ("The skin of this page is the Z-Anatomy skin-region patches fitted to her body (a perineal closure patch, no labia / vulva): these structures were checked against its closed envelope only; there is no vulvar surface to check against.")
    ctx = dict(scale=T[0], reg_txt=reg_txt, skin_text=skin_text, sx=sx)
    ctx["order_text"] = {k: (f"Anatomical order: the urethral meatus lies {run_['order']['meatus_anterior_to_vaginal_wall_mm']} mm in front of the anterior wall of the HRA vagina at its level (positive = anterior, as it should be), "
                             f"and the clitoral body ends {run_['order'].get('clitoral_body_anterior_to_meatus_mm')} mm in front of the meatus.")
                         for k in ("urethral_sphincter_cvh", "urethral_sphincter_raphe_cvh", "urethral_compressor_cvh", "urethrovaginal_sphincter_cvh", "urethra_female_submucous_layer", "urethra_female_lumen")}
    ctx["order_text"]["perineal_body"] = (f"Anatomical order: the perineal body (centroid Z {run_['order']['perineal_body_centroid_z_mm']} mm) lies behind the introitus of the HRA vagina (Z {run_['order']['hra_vaginal_introitus_centroid_z_mm']} mm) and in front of the "
                                          f"centroid of this page's Z-Anatomy external anal sphincter (Z {run_['order'].get('page_external_anal_sphincter_centroid_z_mm')} mm).")
    keys = {sid for sid, _ in shipped}
    add = []
    for sid, it in shipped:
        key = it["key"]; _, nm, latin, cat, folder, region, paired = ST.S[key]
        side = {"l": "left", "r": "right", None: None}[it["side"]]
        rec = dict(name=C.make_name(key, it["side"]), latin=latin, folder=folder, region=region,
                   source="Chinese Visible Human young adult female (Wu et al. 2015 PLOS ONE, S3 Fig, CC BY 4.0); another person's real segmentation registered onto this page's pelvis by bones (Q235)",
                   procedural_badge=C.badge(it, ctx) + " Z-Anatomy has no such structure; the Z-Anatomy structures around it are the page's own fits, so contact with them is approximate.")
        add.append(({"name": rec["name"], "id": sid, "side": SIDE[side], "sys": SYS[cat], "rec": rec}, it["V"], it["F"]))
    # card-only: the HRA structures' sentence about what is absent
    meta = {}
    new_abs = C.new_absent_sentence(keys)
    if new_abs:
        for m in man["meshes"]:
            b = (m.get("rec") or {}).get("procedural_badge") or ""
            if C.OLD_ABSENT in " ".join(b.split()) and str((m.get("rec") or {}).get("source", "")).startswith("HuBMAP"):
                rec = dict(m["rec"]); rec["procedural_badge"] = " ".join(b.split()).replace(C.OLD_ABSENT, new_abs)
                meta[m["id"]] = (m["name"], rec)
    man = dict(man); man["attribution"] = (man.get("attribution") or "").rstrip() + " " + HRA_ATTR
    P5.save_page(out, cfg["stem"], man, blob, add=add, meta=meta)
    import shutil
    for f in src.glob("clinical_*"):
        shutil.copy2(f, out / f.name)
    r = SD.diff(src, out, cfg["stem"], [])
    listed_added = sorted(e["id"] for e, _, _ in add)
    rel = lambda p: str(p.resolve().relative_to(REPO)) if str(p.resolve()).startswith(str(REPO)) else str(p)  # noqa: E731
    diff = dict(source=rel(src), new=rel(out), added=r["added"], added_expected=listed_added, removed=r["removed"], geometry_changed=sorted(r["geometry_changed"]), card_only=sorted(r["card_only"]), card_only_expected=sorted(meta),
                unchanged=r["unchanged"], held=held, unlisted=sorted(set(r["added"]) ^ set(listed_added)) + sorted(set(r["card_only"]) - set(meta)) + sorted(r["geometry_changed"]) + sorted(r["removed"]))
    cfg_rep["ship_diff"] = diff
    (REPO / f"data/derived/Q235_report_{which}.json").write_text(json.dumps(cfg_rep, indent=1, default=float) + "\n")
    (REPO / f"data/derived/Q235_vertex_diff_{which}.json").write_text(json.dumps(diff, indent=1) + "\n")
    print(which, "ship diff: added", len(diff["added"]), "card_only", len(diff["card_only"]), "geometry_changed", len(diff["geometry_changed"]), "removed", len(diff["removed"]), "unlisted", diff["unlisted"], "unchanged", diff["unchanged"])
    return 1 if diff["unlisted"] else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("which", choices=list(CFG)); ap.add_argument("--src"); ap.add_argument("--out"); a = ap.parse_args()
    c = CFG[a.which]
    sys.exit(run(a.which, a.src or str(REPO / c["src"]), a.out or str(REPO / c["out"])))
