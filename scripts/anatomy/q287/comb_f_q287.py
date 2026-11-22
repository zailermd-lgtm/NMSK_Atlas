#!/usr/bin/env python3
"""Q287: Combined · Female gets HER OWN body surface and HER OWN breasts (both measured on the Visible Human female's CT).

    python3 scripts/anatomy/q287/comb_f_q287.py build [--out build/q287_pre]   # page dir + data/derived/Q287_comb_f_report.json
    python3 scripts/anatomy/q287/comb_f_q287.py rig --fresh FILE                # splice the new entries into data/anatomy/pose_rig_comb_f.json

Why no transfer map: Combined · Female is Z-Anatomy geometry fitted onto HER own CT skeleton (Q168), in her atlas frame (hip-joint
origin, mm), so structures measured on her CT drop in unchanged. Measured, not assumed: the report gives, per layer, the share of the
page's sampled vertices that lie outside her skin.

What changes (everything else byte-identical):
  + skin_ct_vhf   her whole body surface (CT HU > -300 silhouette united with the cryosection silhouette where the CT clips the arms;
                  the viewing mesh of Imaging-based Female, subject ct_vhf_skin). A version cut at the wrists / ankles (keeping the
                  Z-Anatomy hand / foot skin) was measured and dropped: 56-67 mm (p90) step at the wrists;
  + breast_ct_r / breast_ct_l   her breasts from her CT (Q285, TotalSegmentator `breasts`), unchanged, faded by default (`fd`)
    so the tissue inside is seen;
  + breast_fgt_ct_r / _l   the fibroglandular tissue inside them (Q287 HU rule on her CT, scripts/anatomy/q287/breast_fgt_q287.py);
  + hd (hidden by default, still listed, `unhide` on the card) on: every Z-Anatomy skin patch (male-derived contour; incl. the Q202
    perineal SURFACE CLOSURE) and the HRA sculpted breast set (12 meshes, "sculpted from scratch").
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
import scripts.anatomy.q249.build_pages as BP  # noqa: E402
from scripts.transfer.q200_bundle import Bundle  # noqa: E402

KEY, DIR = "comb_f", "viewer_zan_female"
STEM = BP.STEM[KEY]
LIVE = "build/q265/viewer_zan_female"           # live Combined · Female geometry (Q265; Q266-Q286 changed templates / sidecars only)
OWN_F_BUNDLE = "build/q263_pre/bundle_own_f"     # her skin: the viewing mesh Imaging-based Female ships (unchanged since Q263)
BREAST_DIR = "build/vh/ct_vhf_breast"            # Q285 meshes
FGT_DIR = "build/vh/ct_vhf_breast_fgt"           # Q287 fibroglandular meshes
HRA_BREAST = "REFERENCE MODEL, NOT donor data: HuBMAP HRA 3D reference object `VH_F_mammary_gland"

SKIN_BADGE = (
    "Q287: HER OWN BODY SURFACE, measured on this body (not Z-Anatomy, not drawn): the silhouette of the Visible Human female's own CT "
    "(HU > -300) united with her cryosection silhouette where the CT clips the arms -- the same surface Imaging-based Female shows "
    "(subject ct_vhf_skin), viewing copy decimated to {nf:,} triangles. The Z-Anatomy structures of this page are fitted onto her own "
    "skeleton (Q168), so her skin sits in the same frame with no transfer; measured: {inside} of the sampled vertices of the non-skin "
    "structures lie inside it. Her breasts, mons pubis and labia majora are her own contour here (the CT resolves the outer surface only: "
    "0.94 mm voxels; the labia minora and the vestibule are not resolved). Where the fitted Z-Anatomy shapes do not follow her pose, "
    "they cross her skin: {ncross} structures by more than 2 mm over more than 5 % of their surface, mostly fingertips of the left hand, "
    "toes and the ankle retinacula (largest: {worst}) -- the Z-Anatomy fingers and toes are not in her hand / foot posture; they are "
    "left as fitted, not moved. "
    "The Z-Anatomy skin patches this surface replaces ({n_hidden} patches: male-derived chest contour, the Q202 perineal surface closure, "
    "...) are kept in the list, hidden by default ('unhide' on their card).")
SKIN_SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): the female CT and colour cryosections "
               "via the NCI Imaging Data Commons; body silhouette meshed by this project (subject ct_vhf_skin).")
ATTR = (" Combined · Female, Q287: her own body surface (subject ct_vhf_skin) and her own breasts (Q285: TotalSegmentator v2.18.0 "
        "`breasts`, Apache-2.0, Wasserthal J et al., Radiology: Artificial Intelligence 2023, doi:10.1148/ryai.230024) with the "
        "fibroglandular tissue inside them (HU rule on her CT), from the NLM Visible Human Project female CT (public domain), shown in the frame this page's Z-Anatomy structures are fitted to.")


def decode_all(man, blob, only=None):
    D = P5.decode(man, blob, only=(lambda m: m["id"] in only) if only is not None else None)
    return {k: (np.asarray(v["v"], float), np.asarray(v["f"], np.int64)) for k, v in D.items()}


def build(out_root):
    import trimesh
    from trimesh.proximity import signed_distance
    src = REPO / LIVE
    man, blob = P5.load_page(src, STEM)
    ids = {m["id"] for m in man["meshes"]}
    fgt_items = json.loads((REPO / FGT_DIR / "items.json").read_text())
    assert not ({"skin_ct_vhf", "breast_ct_r", "breast_ct_l"} | {it["id"] for it in fgt_items}) & ids
    sk = Bundle(REPO / OWN_F_BUNDLE).get("skin")
    assert sk["e"]["subject"] == "ct_vhf_skin"
    v0, f0 = sk["v"], sk["f"]
    full = trimesh.Trimesh(v0, f0, process=False)
    rep = {"her_skin": {"nv": int(len(v0)), "nf": int(len(f0)), "watertight": bool(full.is_watertight)}}

    # 1) where the page's structures lie relative to her FULL skin (frame check)
    rng = np.random.default_rng(287)
    G = decode_all(man, blob)
    by = {}
    for m in man["meshes"]:
        v = G[m["id"]][0]
        by.setdefault(m["sys"], []).append(v[rng.choice(len(v), min(60, len(v)), replace=False)])
    frame = {}
    for s, L in by.items():
        P = np.concatenate(L); sd = signed_distance(full, P)
        frame[s] = {"n": int(len(P)), "outside_gt2mm_pct": round(100 * float((sd < -2).mean()), 2),
                    "outside_gt10mm_pct": round(100 * float((sd < -10).mean()), 2)}
    rep["frame_check_vs_her_full_skin"] = frame
    ns = [k for k in frame if k != "skin"]
    tot = sum(frame[k]["n"] for k in ns)
    inside = 100 - sum(frame[k]["outside_gt2mm_pct"] * frame[k]["n"] for k in ns) / tot
    rep["non_skin_inside_pct_2mm"] = round(inside, 2)

    # 2) her FULL skin is used (her real hands and feet too: a cut at the wrists / ankles left a 56-67 mm (p90) step to the
    #    fitted Z-Anatomy hand skin, whose finger pose is not hers). Structures crossing it are listed, not moved.
    v1, f1 = v0, f0
    tm = full
    cross = []
    for m in man["meshes"]:
        if m["sys"] == "skin":
            continue
        v = G[m["id"]][0]
        s_ = v[:: max(1, len(v) // 300)]
        sd = signed_distance(full, s_)
        o = float((sd < -2).mean())
        if o > 0.05:
            cross.append({"id": m["id"], "sys": m["sys"], "outside_gt2mm_pct": round(100 * o, 1), "max_mm": round(float(-sd.min()), 1)})
    cross.sort(key=lambda r: -r["max_mm"])
    rep["structures_crossing_her_skin"] = cross

    # 3) every Z-Anatomy skin patch -> hidden by default (still listed)
    hide = [m["id"] for m in man["meshes"] if m["sys"] == "skin"]
    assert "zan_skin_perineal_closure" in hide
    rep["z_skin_patches_hidden_default"] = len(hide)

    # 4) her breasts
    items = json.loads((REPO / BREAST_DIR / "items.json").read_text())
    brs = []
    for it in items:
        mm = trimesh.load(REPO / BREAST_DIR / it["obj"], process=False)
        sd = signed_distance(tm, np.asarray(mm.vertices))
        rep.setdefault("breasts", {})[it["id"]] = {
            "volume_cm3": round(float(mm.volume) / 1000, 1),
            "outside_her_skin_gt1mm_pct": round(100 * float((sd < -1).mean()), 2),
            "outside_page_z_skin_note": "the hidden Z chest skin no longer bounds it"}
        brs.append((it, mm))

    fgts = []
    for it in fgt_items:
        mm = trimesh.load(REPO / FGT_DIR / it["obj"], process=False)
        sd = signed_distance(tm, np.asarray(mm.vertices))
        rep.setdefault("breast_fgt", {})[it["id"]] = {"volume_cm3": round(float(mm.volume) / 1000, 1),
                                                     "outside_her_skin_gt1mm_pct": round(100 * float((sd < -1).mean()), 2)}
        fgts.append((it, mm))

    # overlap with the Z-Anatomy pectoralis major (male-derived shape fitted to her skeleton, watertight): reported on the cards, not gated
    pec = {s: [trimesh.Trimesh(*G[k], process=False) for k in G if k.startswith("zan_") and "pectoralis_major" in k and k.endswith("_" + s)
               and ("sternocostal" in k or "abdominal_part" in k)] for s in "rl"}
    def pec_overlap(mm, side):
        P = trimesh.sample.sample_surface(mm, 4000, seed=287)[0]
        ins = np.zeros(len(P), bool)
        for q in pec[side]:
            ins |= signed_distance(q, P) > 1.0
        return round(100 * float(ins.mean()), 1)
    for it, mm in brs:
        rep["breasts"][it["id"]]["z_pectoralis_major_overlap_pct"] = pec_overlap(mm, it["side"][0])
    for it, mm in fgts:
        rep["breast_fgt"][it["id"]]["z_pectoralis_major_overlap_pct"] = pec_overlap(mm, it["side"][0])
    PEC = (" Overlap reported, not corrected: {p} % of its surface lies more than 1 mm inside this page's Z-Anatomy pectoralis major "
           "(a male-derived muscle shape fitted to her skeleton, not her own muscle, which lies behind her breast on her CT).")

    # HRA sculpted breast set
    hra = [m["id"] for m in man["meshes"] if ((m.get("rec") or {}).get("procedural_badge") or "").startswith(HRA_BREAST)]
    assert len(hra) == 12, hra
    rep["hra_sculpted_breast_hidden_default"] = hra

    # 5) write
    hset = set(hide) | set(hra)
    man2 = json.loads(json.dumps(man))
    for m in man2["meshes"]:
        if m["id"] in hset:
            m["hd"] = 1
    man2["attribution"] = man["attribution"] + ATTR
    badge = SKIN_BADGE.format(nf=len(f1), inside=f"{rep['non_skin_inside_pct_2mm']:.1f} %", ncross=len(cross),
                              worst=", ".join(f"{r['id']} {r['max_mm']} mm" for r in cross[:3]), n_hidden=len(hide))
    add = [({"name": "Skin: her own body surface (CT)", "id": "skin_ct_vhf", "side": "m", "sys": "skin",
             "rec": {"name": "Integumentum commune (her own body surface)", "folder": "skin", "region": "whole_body",
                     "source": SKIN_SOURCE, "procedural_badge": badge}}, v1, f1)]
    for it, mm in brs:
        b = it["badge"] + (" On Combined · Female (Q287): unchanged mesh, in this page's frame (its Z-Anatomy structures are fitted to her "
                           "skeleton); the page now shows her own skin around it, and the HRA sculpted breast set is hidden by default.")
        b += PEC.format(p=rep["breasts"][it["id"]]["z_pectoralis_major_overlap_pct"])
        if fgts:
            b += " Faded by default so the fibroglandular tissue inside it is seen ('unfade' on the card)."
        add.append(({"name": it["name"], "id": it["id"], "side": "r" if it["side"] == "right" else "l", "sys": "viscera",
                     "rec": {"name": it["name"], "latin": it["latin"], "folder": "viscera", "region": "breast",
                             "source": "Her own CT (NLM Visible Human Project, public domain), TotalSegmentator v2.18.0 `breasts` task (Apache-2.0)",
                             "procedural_badge": b}, **({"fd": 1} if fgts else {})}, np.asarray(mm.vertices), np.asarray(mm.faces)))
    for it, mm in fgts:
        add.append(({"name": it["name"], "id": it["id"], "side": "r" if it["side"] == "right" else "l", "sys": "viscera",
                     "rec": {"name": it["name"], "latin": it["latin"], "folder": "viscera", "region": "breast",
                             "source": "Her own CT (NLM Visible Human Project, public domain); rule-based HU threshold inside her Q285 breast",
                             "procedural_badge": it["badge"] + PEC.format(p=rep["breast_fgt"][it["id"]]["z_pectoralis_major_overlap_pct"])}},
                    np.asarray(mm.vertices), np.asarray(mm.faces)))
    out = REPO / out_root / DIR
    P5.save_page(out, STEM, man2, blob, add=add)
    for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json", src / "plexus_groups.json"]:
        if f.exists():
            shutil.copy2(f, out / f.name)
    rep["added"] = [a[0]["id"] for a in add]
    rep["new_indices"] = list(range(len(man["meshes"]), len(man["meshes"]) + len(add)))
    (REPO / "data/derived/Q287_comb_f_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("non_skin_inside_pct_2mm", "z_skin_patches_hidden_default", "breasts", "breast_fgt", "added")}, indent=1))
    print("crossing:", len(cross), cross[:12])
    return out, rep


def splice_rig(committed, fresh, new_idx, out, note):
    """committed rig byte-for-byte + only the new entries from a fresh make_pose_rig run (the builder is not bit-reproducible, Q285)"""
    A = json.loads(Path(committed).read_text()); F = json.loads(Path(fresh).read_text())
    wa = zlib.decompress(base64.b64decode(A["weights_zlib_b64"])); wf = zlib.decompress(base64.b64decode(F["weights_zlib_b64"]))
    offs = sorted(e[4] for e in F["rig"]["skin"]) + [len(wf)]
    span = {e[0]: (e[4], offs[offs.index(e[4]) + 1]) for e in F["rig"]["skin"]}
    rig = json.loads(json.dumps(A["rig"]))
    assert rig["count"] == min(new_idx) and F["rig"]["count"] == max(new_idx) + 1
    rig["count"] = F["rig"]["count"]; rig["nv"] = rig["nv"] + [F["rig"]["nv"][i] for i in new_idx]
    blob = bytearray(wa)
    fe = {e[0]: e for e in F["rig"]["skin"]}
    for i in new_idx:
        if i in fe:
            e = list(fe[i]); s, t = span[i]; e[4] = len(blob); blob += wf[s:t]; rig["skin"].append(e)
        else:
            for seg, (si, lst) in enumerate(F["rig"]["rigid"]):
                if i in lst:
                    rig["rigid"][seg][1].append(i)
    rig["notes"] = A["rig"]["notes"] + note
    o = dict(A); o["rig"] = rig; o["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(blob), 9)).decode("ascii")
    Path(out).write_text(json.dumps(o, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return rig["count"], len(rig["skin"])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build", "rig"]); ap.add_argument("--out", default="build/q287_pre")
    ap.add_argument("--fresh"); ap.add_argument("--committed", default=str(REPO / "data/anatomy/pose_rig_comb_f.json"))
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.out)
    else:
        rep = json.loads((REPO / "data/derived/Q287_comb_f_report.json").read_text())
        print(splice_rig(a.committed, a.fresh, rep["new_indices"], a.committed,
                         f"; Q287: +{len(rep['new_indices'])} structures (her skin, her CT breasts and their fibroglandular tissue) spliced in, every other entry as committed"))


if __name__ == "__main__":
    main()
