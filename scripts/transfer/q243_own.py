#!/usr/bin/env python3
"""Q243 (own pages): new structures from the HRA 3D Reference Object Library v1.10 (CC BY 4.0), registered onto the body of the SAME DONOR (the Visible Human female / male), as separate structures.
 own_f: the female pelvic vessels (uterine a./v., internal iliac v., internal pudendal v., middle / inferior / superior rectal v., median sacral v., superior rectal a.; blood-vasculature-female v1.3) with the Q233
        pelvis transform; the nucleus pulposus of each intervertebral disk and the 29 spinal cord segments (united-female v1.10) with one fit per vertebra. Subjects xfer_hra2vhf_q243 / xfer_hra2vhf_spine_q243.
 own_m: the prostate zones + seminal colliculus are tried with the HRA male pelvis registration and guarded; they are shipped only if every guard passes (see data/derived/Q243_report_own_m.json).
Every other entry is byte-identical (ship diff data/derived/Q243_vertex_diff_f.json, exit 1 on any unlisted change).
    python3 scripts/transfer/q243_own.py own_f|own_m [--src build/viewer_f_hr_q237] [--out build/viewer_f_hr_q243]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer.q234_own_f import keyed  # noqa: E402
from scripts.anatomy.q243 import vessels as VS, evidence as EV, badges as BD, spine as SP, spine_place as SPL, hra, male as ML  # noqa: E402

SUBJ_V, SUBJ_S, SUBJ_M = "xfer_hra2vhf_q243", "xfer_hra2vhf_spine_q243", "xfer_hra2vhm_q243"
CFG = {"own_f": dict(src="build/viewer_f_hr_q237", out="build/viewer_f_hr_q243", diff="Q243_vertex_diff_f.json", report="Q243_report_own_f.json"),
       "own_m": dict(src="build/viewer_m_hr_q237", out="build/viewer_m_hr_q243", diff="Q243_vertex_diff_m.json", report="Q243_report_own_m.json")}
ATTR_V = (f"{BD.HRA_NAME} (CC BY 4.0; https://humanatlas.io/3d-reference-library): blood-vasculature-female v1.3, {BD.AUTH}, {BD.BV_DOI}; created from the Visible Human Dataset. Registered onto her own CT pelvis by this atlas "
          "(Q243; the Q233 pelvis transform), open tube ends closed with flat discs; derived data, CC BY 4.0 attribution kept (third_party/hra_vh_f/SOURCES_Q242.md).")
ATTR_S = (f"{BD.HRA_NAME} (CC BY 4.0): united-female v1.10 ({BD.UF_DOI}), spinal-cord-female v1.1 ({BD.SC_DOI}), intervertebral-disk-female v1.0 ({BD.DISK_DOI}); {BD.AUTH}; created from the Visible Human Dataset. "
          "Nucleus pulposus and spinal cord segments registered onto her own CT vertebrae by this atlas (Q243; one rigid + uniform-scale fit per vertebra, blended between vertebrae); derived data, CC BY 4.0 attribution kept.")
CACHE_F = REPO / "data/derived/Q243_spine_fits_own_f.json"


def _fits_to_json(fits, glob):
    j = {lv: {k: (np.asarray(v).tolist() if k in ("hra_centroid", "page_centroid") else v) for k, v in f.items() if k != "T"} | {"s": float(f["T"][0]), "R": np.asarray(f["T"][1]).tolist(), "t": np.asarray(f["T"][2]).tolist()} for lv, f in fits.items()}
    return dict(fits=j, global_fit=dict(scale=glob["scale"], median_mm=glob["median_mm"]))


def _fits_from_json(j):
    fits = {}
    for lv, f in j["fits"].items():
        d = {k: v for k, v in f.items() if k not in ("s", "R", "t")}
        d["T"] = (f["s"], np.array(f["R"]), np.array(f["t"]))
        d["hra_centroid"] = np.array(d["hra_centroid"]); d["page_centroid"] = np.array(d["page_centroid"])
        fits[lv] = d
    return fits, j["global_fit"]


def spine_fits(B, pv):
    if CACHE_F.exists():
        return _fits_from_json(json.loads(CACHE_F.read_text()))
    hv = SP.hra_vertebrae()
    fits, glob = SP.fit_levels(hv, pv)
    hs = SP.hra_sacrum(); fits["S1"] = SP.fit_sacrum(fits, hs[0], hs[1], SP.page_sacrum_own(B))
    CACHE_F.write_text(json.dumps(_fits_to_json(fits, glob), indent=1) + "\n")
    return _fits_from_json(json.loads(CACHE_F.read_text()))


def female(B, src):
    np.random.seed(0)
    r33 = json.loads((REPO / "data/derived/Q233_hra_to_vhf_transform.json").read_text())
    T0 = (r33["scale"], np.array(r33["rotation"]), np.array(r33["translation_mm"]))
    ev = EV.own_pelvis(REPO / src)
    M = VS.load_hra()
    placed, order = VS.place(M, T0, ev["ev"], ev["bones"], ev["hips"], ev["skin_fn"], soft_gate=True)
    reg_txt = (f"HRA VH_F pelvis registered onto her own CT pelvis (hip bones, sacrum, coccyx; rigid + uniform scale x{r33['scale']}, surface residual median {r33['residual_mm']['median']} mm, p90 {r33['residual_mm']['p90']}, "
               f"rms {r33['residual_mm']['rms']}), a bone-based estimate")
    new, report = [], {}
    for sid, name, latin, node, side, kind, grp in VS.VESSELS:
        o = placed[sid]; g = o["gates"]; g["caps"] = M[sid][2]
        g["calibre_kind"] = kind
        report[sid] = dict(hra_node=node, gates=g)
        print(sid, "PASS" if g["pass"] else "HELD", g["bone_min_mm"], g["calibre_mm"], g["length_mm"], flush=True)
        if not g["pass"]:
            report[sid]["held"] = True; continue
        v = dict(node=node, side=side)
        rec = dict(name=name, latin=latin, folder="vascular", region="pelvis", source=BD.vessel_source(),
                   procedural_badge=BD.vessel_badge(v, g, VS.ONTO[node], reg_txt, "her", page_note=" own"))
        new.append((sid, "vessel", side, SUBJ_V, rec, o["V"], o["F"]))
    # ---- spine
    pv = SP.page_vertebrae_own(B)
    fits, glob = spine_fits(B, pv)
    bl = SP.Blend(fits)
    bones = list(pv.values()); sac = SP.page_sacrum_own(B); bones.append(sac)
    bbl = dict(pv); bbl["S1"] = sac
    discs = {it["e"]["id"]: B.mesh(it) for it in B.items if it["e"]["id"].startswith("intervertebral_disc_")}
    page_for = {}
    for (s_, u, l) in SP.DISCS:
        page_for[(u, l)] = f"intervertebral_disc_{u.lower()}_{l.lower()}"
    # her six lumbar bodies (top down) are HRA L1..L6 (rank match); her page names them L1, L1B, L2, L3, L4, L5 (Q185k), so HRA disc (L2,L3) = her disc named L1-L2, ...
    page_for.update({("L1", "L2"): None, ("L2", "L3"): "intervertebral_disc_l1_l2", ("L3", "L4"): "intervertebral_disc_l2_l3", ("L4", "L5"): "intervertebral_disc_l3_l4",
                     ("L5", "L6"): "intervertebral_disc_l4_l5", ("L6", "S1"): "intervertebral_disc_l5_s1"})
    nuc = SPL.place_nuclei(bl, discs, bones, ev["skin_fn"], fits, page_for, bones_by_level=bbl)
    cord, canal = SPL.place_cord(bl, pv, bones, ev["skin_fn"], fits, bones_by_level=bbl)
    page_lumbar_name = {"L1": "L1", "L2": "L1B", "L3": "L2", "L4": "L3", "L5": "L4", "L6": "L5"}
    for (u, l), o in nuc.items():
        g = o["gates"]; did = g["page_disc"]
        pid = did.replace("intervertebral_disc_", "") if did else None
        sid = f"nucleus_pulposus_{pid}" if pid else None
        key = f"{u}-{l}"
        report["nucleus_" + key] = dict(hra_node=g["hra_node"], page_disc=did, gates=g)
        print("nucleus", key, did, "PASS" if g["pass"] else "HELD " + g.get("held_reason", ""), g["bone_min_mm"], g["inside_disc_pct"], flush=True)
        if not g["pass"] or not sid:
            report["nucleus_" + key]["held"] = True; continue
        lum = ""
        if u.startswith("L") or l.startswith("L"):
            lum = (f"NUMBERING: HRA counts the donor's six lumbar vertebrae L1-L6 from the rib-bearing T12 (object description: 'The Visible Human Female has 6 lumbar vertebrae'); this page names the extra body L1B (Q185k2), "
                   f"so the disc that HRA calls 'below {u}' is the page's {did.replace('intervertebral_disc_', '').upper().replace('_', '-')} disc (page body names {page_lumbar_name.get(u, u)} / {page_lumbar_name.get(l, l)}). "
                   f"The page's names are NOT changed here.")
        name = "Nucleus pulposus, " + (f"disc {pid.upper().replace('_', '-')}")
        rec = dict(name=name, latin=f"Nucleus pulposus ({pid.upper().replace('_', '-')})", folder="cartilage", region="spine", source=f"{BD.HRA_NAME} united-female v1.10 ({BD.UF_DOI}, {BD.CC}), Visible Human female; fitted per vertebra to her CT spine (Q243)",
                   procedural_badge=BD.nucleus_badge(key, g, "her", u, l, did, lum))
        new.append((sid, "cartilage", None, SUBJ_S, rec, o["V"], o["F"]))
    cord_rep = {}
    for lv, o in cord.items():
        g = o["gates"]; report["cord_" + lv] = dict(hra_node=g["hra_node"], gates=g)
        print("cord", lv, "PASS" if g["pass"] else "HELD " + g.get("held_reason", ""), g["bone_min_mm"], g["canal_inside_pct"], flush=True)
        if not g["pass"]:
            report["cord_" + lv]["held"] = True; continue
        sid = f"spinal_cord_segment_{lv.lower()}"
        region = {"C": "cervical", "T": "thoracic", "L": "lumbar", "S": "sacral"}[lv[0]]
        rec = dict(name=f"Spinal cord, {lv} segment", latin=f"Segmentum medullae spinalis {lv}", folder="nerves", region="spine", source=f"{BD.HRA_NAME} spinal-cord-female v1.1 ({BD.SC_DOI}, {BD.CC}), Visible Human female; fitted per vertebra to her CT spine (Q243)",
                   procedural_badge=BD.cord_badge(lv, g, "her", f"foramen of the nearest of her vertebrae, section at the pedicle plane, tested {g['canal_tested_pct']} % of the vertices", "linear blend by height"))
        new.append((sid, "nerve", None, SUBJ_S, rec, o["V"], o["F"]))
    lum = {}
    page_names = ["L1", "L1B", "L2", "L3", "L4", "L5"]
    for k in range(6):
        h = f"L{k + 1}"
        lum[h] = dict(page_name=page_names[k], page_centroid_y_mm=round(float(fits[h]["page_centroid"][1]), 1), fit_residual_median_mm=fits[h]["residual_median_mm"], fit_scale=fits[h]["scale"],
                      page_disc_below=(page_for.get((h, f"L{k + 2}" if k < 5 else "S1"))))
    lumbar_numbering = dict(
        hra="The library names six lumbar vertebrae L1-L6 counted from the rib-bearing T12 (spinal-cord-female v1.1: 'The Visible Human Female has 6 lumbar vertebrae'; united-female nodes VH_F_lumbar_vertebra_1..6, nucleus pulposus / disk 'of the first .. sixth lumbar vertebra' = the disk BELOW that vertebra).",
        page="This page has six lumbar bodies (Q185k) and names them L1, L1B, L2, L3, L4, L5; the disc between L1 and L1B is not an atlas entity (Q185k2), so the page has 23 discs (C2-C3 .. L5-S1) where the HRA has 24.",
        match="Rank-matched fits (7 cervical, 12 thoracic, 6 lumbar counted from the top, then refined by ICP) give a surface residual median 0.4-0.6 mm for every level incl. all six lumbar bodies: the page's six lumbar bodies ARE the HRA's L1-L6, one to one.",
        mapping=lum,
        consequence="HRA numbering is RIB-ANCHORED throughout and puts the extra vertebra at the bottom: HRA L2 = the page's L1B, HRA L3 = page L2, L4 = L3, L5 = L4, L6 = L5 (page L5-S1 disc = HRA L6-S1). The page's L2..L5 are off by one against the HRA (and against the usual convention) exactly as Q185k2 says; the page's L1 and the thoracic and cervical numbering agree.",
        decision="No structure of the page is renamed (Q185k2 is an owner decision). The new nuclei carry the PAGE's disc names in their id and name (nucleus_pulposus_l2_l3 sits in intervertebral_disc_l2_l3) and say on the card which HRA disk it is; the HRA L1-L2 nucleus (page L1/L1B) is not shipped because the page has no disc there.")
    rep = dict(pelvis_registration=r33, lumbar_numbering=lumbar_numbering, spine_global_fit=glob, spine_fits={lv: {k: v for k, v in f.items() if k in ("scale", "residual_median_mm", "residual_p90_mm", "residual_rms_mm", "reverse_median_mm", "rotation_from_global_deg")} for lv, f in fits.items()},
               rectal_order=order, structures=report)
    return new, rep


def male(B, src):
    np.random.seed(0)
    bones, ev = [], {}
    import trimesh
    for it in B.items:
        e = it["e"]
        if e["cat"] == "bone" and e["id"] in ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx") and "zfill" not in e["id"]:
            v, f = B.mesh(it); bones.append(trimesh.Trimesh(v, f, process=False))
        if e["id"] in ("prostate", "urinary_bladder", "urethra_male", "rectum") and e["id"] not in ev:
            ev[e["id"]] = B.mesh(it)
    T, reg = ML.register_pelvis(bones)
    rep = ML.guard_zones(T, reg, ev, bones, lambda V: B._depth(V)[0])
    print("own_m: zones ship" if rep["ships"] else "own_m: zones NOT shipped: " + rep["reason"])
    if rep["ships"]:
        raise SystemExit("zones pass the guards: the shipping path is not implemented")
    return [], rep


def main(key, src=None, out=None):
    cfg = CFG[key]; src = src or cfg["src"]; out = out or str(REPO / cfg["out"])
    B0 = Bundle(REPO / src)
    new, rep = (female if key == "own_f" else male)(Bundle(REPO / src), src)
    report_path = REPO / "data/derived" / cfg["report"]
    if not new:
        rep["shipped"] = []
        report_path.write_text(json.dumps(rep, indent=1, default=float) + "\n")
        print(key, "nothing shipped; report", report_path.name)
        return 0
    B = Bundle(REPO / src); A0 = Bundle(REPO / src)
    for sid, cat, side, subj, rec, V, F in new:
        B.add(sid, cat, side, subj, rec, V, F)
    attr = {SUBJ_V: ATTR_V, SUBJ_S: ATTR_S}
    n_bytes = B.write(out, new_subject_attribution=attr, copy_clinical=True)
    N = Bundle(out)
    Ak, Ao = keyed(A0); Nk, No = keyed(N)
    ident, unlisted, bad = 0, [], []
    for k in Ao:
        if k not in Nk:
            bad.append(f"{k} missing"); continue
        if Ak[k]["raw"] == Nk[k]["raw"] and Ak[k]["e"] == Nk[k]["e"]:
            ident += 1
        else:
            unlisted.append(k[0])
    added = [k[0] for k in Nk if k not in Ak]
    exp = sorted(s[0] for s in new)
    if sorted(added) != exp:
        unlisted += sorted(set(added) ^ set(exp))
    diff = dict(source=src, new=str(Path(out).resolve().relative_to(REPO)), entries_old=len(A0.items), entries_new=len(N.items), identical=ident, removed=[], added=added, added_expected=exp, card_only=[],
                unlisted_changes=unlisted, problems=bad, triangles_old=A0.j["triangles"], triangles_new=N.j["triangles"], bundle_bytes_added=int(n_bytes - sum(len(it["raw"]) for it in A0.items)))
    (REPO / "data/derived" / cfg["diff"]).write_text(json.dumps(diff, indent=1) + "\n")
    rep.update(shipped=exp, subjects=[SUBJ_V, SUBJ_S], attribution=attr)
    report_path.write_text(json.dumps(rep, indent=1, default=float) + "\n")
    print("ship diff:", {k: (v if not isinstance(v, list) else len(v)) for k, v in diff.items() if k in ("entries_old", "entries_new", "identical", "added", "unlisted_changes", "problems", "triangles_old", "triangles_new", "bundle_bytes_added")})
    return 1 if (unlisted or bad) else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("key", choices=list(CFG)); ap.add_argument("--src"); ap.add_argument("--out"); a = ap.parse_args()
    sys.exit(main(a.key, a.src, a.out))
