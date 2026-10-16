#!/usr/bin/env python3
"""Q235 (own female): her Q234 bundle (build/viewer_f_hr_q234) -> build/viewer_f_hr_q235.
 ADDS the vulvar / perineal / urethral structures her CT has no label for, from the Chinese Visible Human young adult female (Wu et al. 2015, CC BY 4.0; third_party/cvh_wu2015): cavernous body of the clitoris, vestibular bulbs,
 Bartholin's glands, bulbospongiosus, ischiocavernosus, superficial and deep transverse perineal muscles, the layers and the lumen of the female urethra, the perineal body -- as separate structures (another person's real
 segmentation registered onto her pelvis by bones, rigid + uniform scale; every structure passed the guards of scripts/anatomy/q235/place.py). Card-only change: the badges of the HRA structures no longer say the clitoris /
 urethra are absent. Every other entry is byte-identical (ship diff data/derived/Q235_vertex_diff_f.json, exit 1 on any unlisted change).
    python3 scripts/transfer/q235_own_f.py [--out build/viewer_f_hr_q235]       (needs data/derived/Q235_cvh_to_vhf_transform.json: scripts/anatomy/q235/register_own.py)"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.anatomy.q235 import core as C, evidence, structs as ST, place as PL, fit as Fm  # noqa: E402
from scripts.transfer.q234_own_f import keyed  # noqa: E402

SUBJECT = "xfer_cvh2vhf_q235"
SRC = "build/viewer_f_hr_q234"
ATTR = (C.CITE + ". Registered onto her own CT pelvis by this atlas (Q235; bones only, rigid + uniform scale); derived data (triangles re-oriented, components below 100 triangles dropped, the urethral lumen cut and capped), "
        "CC BY 4.0 attribution kept (third_party/cvh_wu2015/NOTICE.md). Not endorsed by the authors or PLOS.")


def main(out_dir, src=SRC):
    np.random.seed(0)
    tr = json.loads((REPO / "data/derived/Q235_cvh_to_vhf_transform.json").read_text())
    sx = int(tr["chosen_sx"]); T = (tr["scale"], np.array(tr["rotation"]), np.array(tr["translation_mm"]))
    ev, B = evidence.own_evidence(REPO / src)
    A0 = Bundle(REPO / src)
    run = C.run_page(ev, T, sx)
    items = run["items"]
    s = T[0]
    reg_txt = (f"Registration (bones only, Q235): the CVH pelvic bone and the closed sacrum + coccyx mesh onto HER OWN hip bones, sacrum and coccyx (rigid + uniform scale x{tr['scale']}: the CVH pelvis is "
               f"{round(100 * (1 - 1 / tr['scale']))} % smaller than hers; bidirectional trimmed closest-point fit), surface residual of all CVH bone vertices median {tr['residual_mm']['all CVH bone vertices']['median']} mm, "
               f"p90 {tr['residual_mm']['all CVH bone vertices']['p90']} mm; pubic symphysis region median {tr['residual_mm']['pubic symphysis region (|x-184|<8)']['median']} / p90 {tr['residual_mm']['pubic symphysis region (|x-184|<8)']['p90']}, "
               f"ischiopubic arch median {tr['residual_mm'][C.ARCH_KEY]['median']} / p90 {tr['residual_mm'][C.ARCH_KEY]['p90']}, ischial tuberosities median {tr['residual_mm']['ischial tuberosity region (lowest 25 mm of the hip bones)']['median']} / "
               f"p90 {tr['residual_mm']['ischial tuberosity region (lowest 25 mm of the hip bones)']['p90']}, sacrum + coccyx median {tr['residual_mm']['sacrum+coccyx (closed mesh), all']['median']} / p90 {tr['residual_mm']['sacrum+coccyx (closed mesh), all']['p90']} "
               f"(coccyx alone {tr['residual_mm']['coccyx (lowest 15 mm of the closed mesh)']['median']} mm median). The soft organs of the CVH woman are NOT where hers are: CVH bladder wall / vaginal wall / uterine wall differ from her bladder / the HRA "
               f"vagina / uterus by {tr['crosscheck']['bladder wall (CVH 27) vs page bladder']['sym_nn_median_mm']} / {tr['crosscheck']['vaginal wall (CVH 21) vs HRA vagina']['sym_nn_median_mm']} / {tr['crosscheck']['uterine wall (CVH 17) vs HRA uterus']['sym_nn_median_mm']} mm "
               f"(median nearest-neighbour distance; individual differences, not registration error), so the soft tissue relations come from the CVH woman and are only registered by her bones.")
    skin_text = ("The page's skin mesh has no vulvar, labial or perineal surface of its own (the skin of both thighs merges below the crotch, about 40 mm below these structures), so nothing here is checked against a perineal skin surface, only against the "
                 "closed skin envelope of the body.")
    cross = tr["crosscheck"]
    ctx = dict(scale=tr["scale"], reg_txt=reg_txt, skin_text=skin_text, sx=sx)
    ctx["order_text"] = {k: (f"Anatomical order: the urethral meatus lies {run['order']['meatus_anterior_to_vaginal_wall_mm']} mm in front of the anterior wall of the HRA vagina at its level (positive = anterior, as it should be), "
                             f"and the clitoral body ends {run['order'].get('clitoral_body_anterior_to_meatus_mm')} mm in front of the meatus.")
                         for k in ("urethral_sphincter_cvh", "urethral_sphincter_raphe_cvh", "urethral_compressor_cvh", "urethrovaginal_sphincter_cvh", "urethra_female_submucous_layer", "urethra_female_lumen")}
    ctx["order_text"]["perineal_body"] = (f"Anatomical order: the perineal body (centroid Z {run['order']['perineal_body_centroid_z_mm']} mm) lies behind the introitus of the HRA vagina (Z {run['order']['hra_vaginal_introitus_centroid_z_mm']} mm) and in front of the centroid "
                                          f"of her rule-based external anal sphincter (Z {run['order'].get('page_external_anal_sphincter_centroid_z_mm')} mm).")
    pc = {"ischiocavernosus_cvh": "ischiocavernosus (CVH 36) vs page ischiocavernosus", "bulbospongiosus_cvh": "bulbospongiosus (CVH 37) vs page bulbospongiosus", "deep_perineal_muscle_cvh": "deep perineal muscle (CVH 25) vs page deep transverse perineal"}
    ctx["cross_text"] = {k: (f"Her page ALSO has its own rule-based {n} (subject ct_vhf_pfloor, a different, estimated structure): the two differ by a symmetric nearest-neighbour distance of median {cross[c]['sym_nn_median_mm']} / p90 {cross[c]['sym_nn_p90_mm']} mm "
                              f"(centroid offset {cross[c]['centroid_offset_mm']} mm); both are shown, they are not merged.")
                         for (k, c), n in zip(pc.items(), ("ischiocavernosus", "bulbospongiosus", "deep transverse perineal muscle")) if c in cross}
    shipped, held, report = [], [], {}
    for it in items:
        sid = C.make_id(it["key"], it["side"])
        g = it["gates"]
        report[sid] = dict(cvh_index=it["info"]["cvh_index"], cvh_name=C.CVH_NAME[it["key"]], side=it["side"], gates=g, info={k: v for k, v in it["info"].items() if k != "components"},
                           components=it["info"].get("components"), volume_page_cm3=round(it["info"]["volume_cvh_cm3"] * s ** 3, 3), area_page_cm2=round(it["info"]["area_cvh_cm2"] * s ** 2, 2))
        print(sid, "PASS" if g["pass"] else "HELD " + str(g["fail_reasons"]), flush=True)
        if not g["pass"]:
            report[sid]["held"] = True; held.append(sid); continue
        shipped.append((sid, it))
    keys = {it["key"] if it["side"] is None else f"{it['key']}_{it['side']}" for _, it in shipped}
    for sid, it in shipped:
        key = it["key"]; _, nm, latin, cat, folder, region, paired = ST.S[key]
        side = {"l": "left", "r": "right", None: None}[it["side"]]
        rec = dict(name=C.make_name(key, it["side"]), latin=latin, folder=folder, region=region,
                   source="Chinese Visible Human young adult female (Wu et al. 2015 PLOS ONE, S3 Fig, CC BY 4.0); another person's real segmentation registered onto her CT pelvis by bones (Q235)",
                   procedural_badge=C.badge(it, ctx))
        B.add(sid, cat, side, SUBJECT, rec, it["V"], it["F"])
    # card-only: the HRA structures' sentence about what is absent
    new_abs = C.new_absent_sentence(keys)
    card_only = []
    if new_abs:
        for it in B.items:
            e = it["e"]
            if e["subject"] in ("xfer_hra2vhf_q233", "xfer_hra2vhf_q234", "xfer_hrasculpt2vhf_q234") and C.OLD_ABSENT in (e["rec"].get("procedural_badge") or ""):
                e["rec"] = {**e["rec"], "procedural_badge": e["rec"]["procedural_badge"].replace(C.OLD_ABSENT, new_abs)}
                card_only.append(e["id"])
    n_bytes = B.write(out_dir, new_subject_attribution={SUBJECT: ATTR}, copy_clinical=True)
    # ship diff
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
    exp_added = sorted(sid for sid, _ in shipped)
    if sorted(added) != exp_added:
        unlisted += sorted(set(added) ^ set(exp_added))
    diff = dict(source=src, new=str(Path(out_dir).resolve().relative_to(REPO)), entries_old=len(A0.items), entries_new=len(N.items), identical=ident, removed=[], added=added, card_only=card_only, unlisted_changes=unlisted, problems=bad,
                held=held, triangles_old=A0.j["triangles"], triangles_new=N.j["triangles"], bundle_bytes_added=int(n_bytes - sum(len(it["raw"]) for it in A0.items)))
    (REPO / "data/derived/Q235_vertex_diff_f.json").write_text(json.dumps(diff, indent=1) + "\n")
    rep = dict(registration=tr, order_checks=run["order"], structures=report, shipped=exp_added, held=held, subject=SUBJECT, attribution=ATTR,
               tolerances=dict(soft_tolerance_mm=PL.SOFT_TOL_MM, soft_max_share_deeper_pct=PL.SOFT_MAX_PCT_DEEP, bone_min_free_mm=PL.BONE_MIN_FREE, bone_min_attach_mm=PL.BONE_MIN_ATTACH, max_shift_mm=PL.MAX_SHIFT_MM,
                               max_shift_fraction=PL.MAX_SHIFT_FRAC, skin_min_mm=PL.SKIN_MIN_MM), not_shipped_by_choice=C.NOT_SHIPPED)
    (REPO / "data/derived/Q235_report_own_f.json").write_text(json.dumps(rep, indent=1, default=float) + "\n")
    print("ship diff:", {k: (v if not isinstance(v, list) else len(v)) for k, v in diff.items() if k in ("entries_old", "entries_new", "identical", "added", "card_only", "unlisted_changes", "problems", "held", "triangles_new", "bundle_bytes_added")})
    sys.exit(1 if (unlisted or bad) else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(REPO / "build/viewer_f_hr_q235")); a = ap.parse_args()
    main(a.out)
