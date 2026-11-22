"""Q292 page step: the live Base · Female page + the Q292 geometry (build_q292.py geometry) -> a new page dir, and the pose-rig splice.

Changes, everything else byte-identical to the live page (build/q265/viewer_base_female):
  + her own breasts + fibroglandular tissue, her own urinary bladder / rectum / pelvic sigmoid colon (CT), her uterus (cryosections),
    her rule-based external anal sphincter; the HRA / CVH female structures that were absent here (round ligaments, superior rectal
    artery, anococcygeal ligament, clitoris cavernous body) where they now pass the same checks;
  ~ replaced geometry: the chest skin patches (fitted onto her skin), the Z soft structures her breasts entered (thinned toward the rib
    cage), the Z levator parts (pushed out of her organs), the HRA / CVH female set (placement re-checked against her organs);
  hd (hidden by default, still listed): the HRA sculpted breast set (12), the Z bladder, the Z sigmoid colon, the Z external anal
    sphincter, the HRA reference uterus (her cryosection uterus replaces it), and any female-set structure that still enters bone /
    her organs / psoas by more than 20 % of its vertices; fd (faded by default): her breasts, so the glandular tissue inside is seen.
"""
from __future__ import annotations

import base64
import json
import pickle
import shutil
import sys
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
import build_q292 as BQ  # noqa: E402
from scripts.transfer.q200_bundle import Bundle  # noqa: E402

PAGE_REPORT = REPO / "data/derived/Q292_page_report.json"
SYS = {"organ": "viscera", "muscle": "muscle", "ligament": "joint", "vessel": "vessel", "nerve": "nerve", "fascia": "fascia"}
SIDE = {"left": "l", "right": "r", None: "m", "midline": "m"}
COHORT = ("cohort means for comparison, not a range for her: MRI volumetry, 22 women, left 771 / right 764 mL (Behrens AS et al., "
          "doi:10.1007/s12282-024-01647-6); VECTRA, 100 healthy women, 637 / 665 mL (Killaars RC et al., doi:10.1007/s00266-026-06058-w)")
ATTR = (" Base · Female, Q292: her own breasts (Q285, TotalSegmentator v2.18.0 `breasts`, Apache-2.0, Wasserthal J et al., Radiology: AI 2023, "
        "doi:10.1148/ryai.230024) with their fibroglandular tissue (Q287 HU rule), her own urinary bladder / rectum / pelvic sigmoid colon "
        "(TotalSegmentator `total`), her uterus from her colour cryosections (Q288) and her rule-based external anal sphincter, from the NLM "
        "Visible Human Project female (public domain), registered onto this body by its bones (Q292); the chest skin patches are fitted onto "
        "her own skin contour. HRA reference organs (CC BY 4.0) and CVH perineal structures (Wu et al. 2015, CC BY 4.0) re-checked against them.")


GEOM_HER_CT = "her own CT (NLM Visible Human female, public domain), registered onto this body (Q292)"


def geom_src_for(k, rec, subject=""):
    if subject.startswith("xfer_cvh2vhf"):
        return "Chinese Visible Human young adult female (Wu et al. 2015, CC BY 4.0) -- another woman, registered onto this body"
    if subject.startswith("xfer_hra2vhf"):
        return "HuBMAP HRA 3D Reference Object Library (CC BY 4.0), Visible Human female frame -- a reference object, registered onto this body"
    t = json.dumps(rec)
    if "Chinese Visible Human" in t or k.endswith("_cvh"):
        return "Chinese Visible Human young adult female (Wu et al. 2015, CC BY 4.0) -- another woman, registered onto this body"
    if "HuBMAP" in t or "HRA" in t:
        return "HuBMAP HRA 3D Reference Object Library (CC BY 4.0), Visible Human female frame -- a reference object, registered onto this body"
    return None


def _r(x, n=1):
    return round(float(x), n)


def badge_breast(R, T):
    return (f"Q292: HER OWN BREAST, measured on her CT (Q285: TotalSegmentator `breasts`), REFITTED onto this body BY STATED RULES -- "
            f"not her exact shape here. Rigid fit of her own chest wall (ribs 2-7, costal cartilages, sternum) onto this page's chest wall "
            f"(rotation {T['rot_deg']} deg, residual median {T['wall_fit_resid_med_mm']} mm), her breast-to-rib-cage height kept (depth "
            f"correction p95 {R['depth_correction']['correction_p95_mm']} mm). RULE-BASED adjustments: {R['lateral_squash']['rule']} (her "
            f"supine lateral spread lies against her arm in the CT; the arm of this page hangs there; up to {R['lateral_squash']['max_mm']} mm), "
            f"pushed out of the arm (max {R['out_of_arm']['disp_max_mm']} mm) and out of the rib cage keeping {BQ.WALL_GAP:.0f} mm for the "
            f"pectoral layer (max {R['out_of_rib_cage']['disp_max_mm']} mm). Volume {R['final_volume_cm3']} cm3 = {R['volume_kept_pct']} % of "
            f"her CT breast ({R['her_volume_cm3']} cm3; {COHORT}). Checks: {R['vertices_outside_skin_gt0_5mm_pct']} % of vertices more than "
            f"0.5 mm outside the skin, {R['vertices_in_rib_cage_gt0_5mm_pct']} % inside the rib cage. Supine cadaver shape (59 y): a standing "
            f"breast sits lower and projects more. No separate nipple / areola object (her skin contour only). The HRA sculpted breast set is "
            f"hidden by default ('unhide' on its cards). Faded by default so the glandular tissue inside is seen.")


def badge_fgt(R, base):
    return (base + f" Q292: moved with her breast on this body (the same transform, squash and pushes), then kept inside it: "
            f"{R['final_fgt_volume_cm3']} cm3 here ({R['her_fgt_volume_cm3']} cm3 on her CT).")


def badge_skin(rep):
    s = rep['skin']
    return (f"Q292: this Z-Anatomy skin patch (male-derived chest contour) is SUBDIVIDED to {s['max_edge_mm']:.0f} mm edges and FITTED onto "
            f"HER OWN skin surface (her CT, mapped with her breasts' transform): fully over the breasts, tapering to nothing 30-80 mm from "
            f"them and at the borders with the patches that do not move; pushed outward over her breast where her CT has no skin of her "
            f"own (her lateral breast lies against her arm there; max {s['pushed_out_max_mm']} mm). The Q250 skin bump over the HRA "
            f"sculpted breast is removed (this starts from the patch before that lift). Contour hers (supine), outline Z-Anatomy's.")


def badge_thinned(info):
    return (f" Q292: THINNED under her breast (this Z-Anatomy shape is male-derived: the sternocostal head is ~17 mm thick here, her own "
            f"pectoralis major ~10 mm on her CT): every vertex her breast entered was moved toward the rib cage to 1 mm behind the breast "
            f"(never closer than 0.5 mm to the ribs), the displacement smoothed over the mesh; max move {info['disp_max_mm']} mm, volume "
            f"{info.get('volume_before_cm3')} -> {info.get('volume_after_cm3')} cm3; {info['inside_breast_after']} vertices still inside the breast.")


def badge_lev(info):
    return (f" Q292: pushed out of her own rectum / vagina / bladder / uterus (registered onto this page) by at most 5 mm "
            f"(max {info['disp_max_mm']} mm, volume {info['volume_before_cm3']} -> {info['volume_after_cm3']} cm3); "
            f"{info['still_violating']} vertices still inside them.")


def badge_organ(k, info, rep, base=""):
    m = rep['map']
    return ((base + " " if base else "") +
            f"Q292: HER OWN organ registered onto this body by its bones (thin-plate spline through {m['control_points']} control points of the "
            f"two Z-Anatomy skeletons, Combined F = fitted to her skeleton, Base F = deformed onto it; residual median {m['tps_resid_med_mm']} / "
            f"p95 {m['tps_resid_p95_mm']} mm). Volume {info['her_volume_cm3']} cm3 on her CT, {info['volume_cm3']} cm3 here (the spline follows "
            f"this page's pelvis, a little wider than hers). The Z-Anatomy organ it replaces is hidden by default ('unhide' on its card).")


def badge_female(k, c, rep):
    pl = ("the earlier registration of this page kept" if c['placement'] == 'live' else
          "her-frame placement (Imaging-based Female) carried by the same spline as her own organs")
    b = (f" Q292: placement re-checked against her own registered organs: {pl}; pushed out of the bones / her organs / psoas by at most 8 mm "
         f"(max {c['push']['disp_max_mm']} mm); {c['vertices_in_bone_her_organs_or_psoas_pct']} % of vertices still inside them")
    if c['overlap_pct_of_volume']:
        b += "; largest overlaps " + ", ".join(f"{a} {v} %" for a, v in list(c['overlap_pct_of_volume'].items())[:3])
    if c.get('urethral_group_anterior_shift_mm'):
        b += f"; the urethral group moved {c['urethral_group_anterior_shift_mm']} mm anteriorly together so the urethra lies in front of the vagina"
    if c['hidden_default']:
        b += f". HIDDEN BY DEFAULT: more than {BQ.HOLD_PCT:.0f} % of it still lies inside bone / her organs / psoas ('unhide' on the card)"
    return b + "."


def build(work, out_root):
    G = pickle.load(open(Path(work) / "geometry.pkl", "rb")); rep = G['rep']
    src = BQ.LIVE_BASE_F
    man, blob = P5.load_page(src, BQ.STEM)
    E = {m["id"]: m for m in man["meshes"]}
    own = Bundle(BQ.OWN_F)
    replace, add, hd, fd = {}, [], set(), set()

    def rec_of(k):
        return json.loads(json.dumps(E[k].get("rec") or {}))

    def add_badge(rec, extra):
        rec = dict(rec); rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + extra).strip(); return rec
    # skin patches
    for k, (v, f) in G['SKIN'].items():
        rec = rec_of(k); prev = (rec.get("procedural_badge") or "").split(" || Q250 female chest envelope")[0]
        rec["procedural_badge"] = badge_skin(rep) + ((" Earlier: " + prev) if prev else "")
        rec["geom_src"] = "Z-Anatomy skin patch (CC BY-SA 4.0) fitted onto her own CT skin contour (NLM Visible Human female, public domain), Q292"
        replace[k] = (v, f, rec)
    # thinned / fitted Z structures
    for k, (v, f) in G['MOD'].items():
        if k in replace:
            continue
        info = rep.get('thinned_under_breast', {}).get(k) or rep.get('levator_fitted_to_her_organs', {}).get(k)
        extra = badge_thinned(info) if k in rep.get('thinned_under_breast', {}) else badge_lev(info)
        replace[k] = (v, f, add_badge(rec_of(k), extra))
    # female set (HRA / CVH): re-placed on the page or added
    for k, c in rep['female_set'].items():
        v, f = G['NEW'][k]
        if c['hidden_default']:
            hd.add(k)
        if k in E:
            r0 = add_badge(rec_of(k), badge_female(k, c, rep)); g = geom_src_for(k, r0, own.get(k)["e"].get("subject") or "")
            if g:
                r0["geom_src"] = g
            replace[k] = (v, f, r0)
        else:
            it = own.get(k); e = it["e"]; rec = dict(e.get("rec") or {})
            rec["procedural_badge"] = (rec.get("procedural_badge") or "") + " Q292: NEW on Base · Female (was not on this page)." + badge_female(k, c, rep)
            g = geom_src_for(k, rec, e.get("subject") or "")
            if g:
                rec["geom_src"] = g
            add.append(({"name": rec.get("name", k), "id": k, "side": SIDE.get(e.get("side"), "m"), "sys": SYS.get(e["cat"], e["cat"]), "rec": rec}, v, f))
    # her organs
    for k in BQ.ORG + ['external_anal_sphincter_ct_vhf']:
        v, f = G['NEW'][k]
        sid = 'external_anal_sphincter' if k == 'external_anal_sphincter_ct_vhf' else k
        it = own.get(sid); e = it["e"]; rec = dict(e.get("rec") or {})
        if k == 'uterus_cryo_vhf':
            items = json.loads((REPO / "build/vh/ct_vhf_uterus/items.json").read_text()); base = items[0]["badge"]
            rec.update(name=items[0]["name"], source="Her own colour cryosections (NLM Visible Human Project female, public domain), Q288")
            rec["procedural_badge"] = badge_organ(k, rep['organs'][k], rep, base)
        elif k == 'external_anal_sphincter_ct_vhf':
            h = rep['her_external_anal_sphincter']
            rec["name"] = "External anal sphincter (her pelvic-floor rules)"
            rec["procedural_badge"] = (
                "RULE-BASED (her pelvic floor by position rules inside her own bony pelvis, with her colour cryosections as the tissue evidence; "
                "subject ct_vhf_pfloor of Imaging-based Female): NOT a segmentation of a visible sphincter. Q292: registered onto this body with "
                f"the same bone spline as her rectum; volume {h['her_volume_cm3']} -> {h['volume_cm3']} cm3; overlaps "
                + ", ".join(f"{a} {b} %" for a, b in h['overlap_pct_of_volume'].items()) +
                ". The Z-Anatomy external anal sphincter (male-derived, it lay ~30 mm above her anal canal here) is hidden by default.")
        else:
            rec["name"] = {"urinary_bladder": "Urinary bladder (her own, CT)", "rectum": "Rectum (her own, CT)",
                           "sigmoid_colon": "Sigmoid colon, pelvic part (her own, CT)"}[k]
            rec["source"] = "Her own CT (NLM Visible Human Project, public domain), TotalSegmentator `total` task (Apache-2.0); subject ct_vhf_pelvis of Imaging-based Female"
            rec["procedural_badge"] = ("MEASURED on her own CT (automatic segmentation, not hand-drawn; the colon label cut at her pelvic inlet "
                                       "and split at the sigmoid take-off, as on Imaging-based Female). " + badge_organ(k, rep['organs'][k], rep))
        rec["geom_src"] = ("her own colour cryosections (NLM Visible Human female, public domain), registered onto this body (Q292)" if k == 'uterus_cryo_vhf' else
                           "RULE-BASED on her own pelvis (Visible Human female), registered onto this body (Q292)" if k.startswith('external_anal') else GEOM_HER_CT)
        add.append(({"name": rec.get("name", k), "id": k, "side": "m", "sys": SYS.get(e["cat"], e["cat"]), "rec": rec}, v, f))
    # breasts + FGT
    bi = {it["id"]: it for it in json.loads((REPO / "build/vh/ct_vhf_breast/items.json").read_text())}
    fi = {it["id"]: it for it in json.loads((REPO / "build/vh/ct_vhf_breast_fgt/items.json").read_text())}
    for s in 'lr':
        R = rep['breasts'][s]; T = rep['breast_transform'][s]
        it = bi['breast_ct_' + s]; v, f = G['NEW']['breast_ct_' + s]
        add.append(({"name": it["name"], "id": it["id"], "side": s, "sys": "viscera", "fd": 1,
                     "rec": {"name": it["name"], "latin": it["latin"], "folder": "viscera", "region": "breast",
                             "source": "Her own CT (NLM Visible Human Project, public domain), TotalSegmentator v2.18.0 `breasts` task (Apache-2.0)",
                             "procedural_badge": it["badge"] + " " + badge_breast(R, T),
                             "geom_src": "her own CT (NLM Visible Human female, public domain; TotalSegmentator `breasts`), refitted onto this body by stated rules (Q292)"}}, v, f))
        it = fi['breast_fgt_ct_' + s]; v, f = G['NEW']['breast_fgt_ct_' + s]
        add.append(({"name": it["name"], "id": it["id"], "side": s, "sys": "viscera",
                     "rec": {"name": it["name"], "latin": it["latin"], "folder": "viscera", "region": "breast",
                             "source": "Her own CT (NLM Visible Human Project, public domain); RULE-BASED HU threshold inside her Q285 breast (Q287)",
                             "procedural_badge": badge_fgt(R, it["badge"]),
                             "geom_src": "RULE-BASED (HU threshold) on her own CT (NLM Visible Human female, public domain), moved with her breast (Q292)"}}, v, f))
    hra = [m["id"] for m in man["meshes"] if BQ.HRA_BREAST_RE.match(m["id"])]
    assert len(hra) == 12, hra
    hd |= set(hra) | set(BQ.HIDE_PELVIS)
    man2 = json.loads(json.dumps(man))
    for m in man2["meshes"]:
        if m["id"] in hd:
            m["hd"] = 1
    man2["attribution"] = man["attribution"] + ATTR
    for k in list(replace):
        v, f, rec = replace[k]
        if k in hd:
            rec = dict(rec); rec["procedural_badge"] = (rec.get("procedural_badge") or "") + " Hidden by default on Base · Female since Q292 ('unhide' on the card)."
            replace[k] = (v, f, rec)
    meta = {}
    for k in hd:
        if k not in replace and k in E:
            rec = rec_of(k)
            why = ("replaced by her own CT breast (Q292); this HRA object is sculpted from scratch (HRA record), not donor data" if k in hra else
                   "replaced on Base · Female by her own organ (Q292)")
            meta[k] = (E[k]["name"], add_badge(rec, f" Hidden by default on Base · Female since Q292: {why} ('unhide' on the card)."))
    out = Path(out_root) / "viewer_base_female"
    man3, _ = P5.save_page(out, BQ.STEM, man2, blob, replace=replace, meta=meta, add=add)
    for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json", src / "plexus_groups.json"]:
        if f.exists():
            shutil.copy2(f, out / f.name)
    shutil.copy2(out / f"{BQ.STEM}.html", out / "index.html")
    idx = {m["id"]: i for i, m in enumerate(man3["meshes"])}
    prep = {"_README": ["Q292 Base · Female page step; scripts/anatomy/q292/page_q292.py"],
            "added": [a[0]["id"] for a in add], "new_indices": [idx[a[0]["id"]] for a in add],
            "replaced": sorted(replace), "card_only": sorted(meta), "replaced_indices": sorted(idx[k] for k in replace if _geom_changed(k, replace, man, blob)),
            "hidden_default": sorted(hd), "faded_default": [a[0]["id"] for a in add if a[0].get("fd")],
            "meshes": len(man3["meshes"]), "triangles": int(sum(m["ic"] for m in man3["meshes"]))}
    PAGE_REPORT.write_text(json.dumps(prep, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if not isinstance(v, list) or len(v) < 30 else f"{len(v)} items") for k, v in prep.items()}, indent=1))
    return out


def _decode(man, blob, k):
    D = P5.decode(man, blob, only=lambda m: m["id"] == k)
    return np.asarray(D[k]["v"], float), np.asarray(D[k]["f"], np.int64)


def _geom_changed(k, replace, man, blob):
    v, f, _ = replace[k]
    v0, f0 = _decode(man, blob, k)
    return not (len(v0) == len(v) and np.array_equal(np.asarray(f0), np.asarray(f)) and np.abs(np.asarray(v) - v0).max() < 1e-6)


def splice_rig(fresh):
    """committed rig byte for byte + fresh entries for the new AND the replaced-geometry indices (the Q286 pattern), weight blob repacked"""
    rep = json.loads(PAGE_REPORT.read_text())
    committed = REPO / "data/anatomy/pose_rig_base_f.json"
    A = json.loads(committed.read_text()); F = json.loads(Path(fresh).read_text())
    n0, n1 = A["rig"]["count"], F["rig"]["count"]
    new_idx = list(range(n0, n1)); assert new_idx == rep["new_indices"], (n0, n1, rep["new_indices"][:3])
    wa = zlib.decompress(base64.b64decode(A["weights_zlib_b64"])); wf = zlib.decompress(base64.b64decode(F["weights_zlib_b64"]))
    offs = sorted(e[4] for e in F["rig"]["skin"]) + [len(wf)]
    span = {e[0]: (e[4], offs[offs.index(e[4]) + 1]) for e in F["rig"]["skin"]}
    rig = json.loads(json.dumps(A["rig"])); rig["count"] = n1; rig["nv"] = rig["nv"] + [F["rig"]["nv"][i] for i in new_idx]
    blob = bytearray(wa); fe = {e[0]: e for e in F["rig"]["skin"]}

    def take(i):
        if i in fe:
            e = list(fe[i]); s, t = span[i]; e[4] = len(blob); blob.extend(wf[s:t]); rig["skin"].append(e)
        else:
            for seg, (si, lst) in enumerate(F["rig"]["rigid"]):
                if i in lst:
                    rig["rigid"][seg][1].append(i)
    for i in rep["replaced_indices"]:
        rig["nv"][i] = F["rig"]["nv"][i]
        rig["skin"] = [e for e in rig["skin"] if e[0] != i]
        for seg in rig["rigid"]:
            if i in seg[1]:
                seg[1].remove(i)
        take(i)
    for i in new_idx:
        take(i)

    def seglen(e):
        return (e[1] + 7) // 8 + e[5] * (2 * e[2] - 1)
    packed = bytearray()
    for e in rig["skin"]:
        s = e[4]; chunk = bytes(blob[s:s + seglen(e)]); e[4] = len(packed); packed.extend(chunk)
    rig["notes"] = A["rig"]["notes"] + (f"; Q292: +{len(new_idx)} structures (her breasts / pelvic organs) and {len(rep['replaced_indices'])} replaced "
                                        "geometries (chest skin, thinned muscles, re-placed female set) taken from a fresh run, every other entry as committed")
    o = dict(A); o["rig"] = rig; o["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(packed), 9)).decode("ascii")
    committed.write_text(json.dumps(o, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print("rig", rig["count"], "skinned", len(rig["skin"]), "replaced", len(rep["replaced_indices"]), "new", len(new_idx))
