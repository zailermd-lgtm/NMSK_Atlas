#!/usr/bin/env python3
"""Q293 page step: the six live pages + (a) the RULE-BASED reflected head of rectus femoris on both sides (rf_reflected.py) and, on the
two Combined pages, (b) the re-articulated finger bones + the finger soft tissue carried with them (fingers_q293.py).

    python3 scripts/anatomy/q293/pages_q293.py baseline own_m|own_f [--out DIR]   # rebuild the live own page from its bundle, prove geo == live
    python3 scripts/anatomy/q293/pages_q293.py build [KEY...] [--out /dev/shm/q293/pre2]   # -> page dirs + data/derived/Q293_page_report.json
    python3 scripts/anatomy/q293/pages_q293.py rig KEY --fresh FRESH.json             # splice the new / replaced entries (+ finger joints) into data/anatomy/pose_rig_KEY.json

Every other structure is copied byte for byte (Z pages: q205_pages.save_page; own pages: the Q286 bundle path)."""
from __future__ import annotations
import argparse, base64, json, shutil, sys, zlib
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO, REPO / "scripts/anatomy/q286", REPO / "scripts/anatomy/q249", REPO / "scripts/anatomy/q287"):
    sys.path.insert(0, str(p))
import rf_reflected as RF  # noqa: E402
import audit_q293 as AQ  # noqa: E402


def fix_rec(rec):
    """the Q293 attachment corrections (audit_q293.FILE_FIXES) applied to a structure card's origin / insertion text -> new rec or None"""
    if not isinstance(rec, dict):
        return None
    out, hit = dict(rec), False
    for (m, path, old, new, src) in AQ.FILE_FIXES:
        if not path.startswith("attachments.") or not old:
            continue
        fld = "origin" if "origin" in path else "insertion"
        t = out.get(fld)
        if not isinstance(t, str):
            continue
        for sd in "rl":
            o, n = old.replace("{s}", sd), new.replace("{s}", sd)
            if o in t and n not in t:
                t = t.replace(o, n); hit = True
        out[fld] = t
    return out if hit else None

DIR = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas", "base_f": "viewer_base_female",
       "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
LIVE = {"own_m": "build/q286/viewer_m_hr", "own_f": "build/q288/viewer_f_hr", "base_m": "build/q265/viewer_zan_atlas",
        "base_f": "build/q292/viewer_base_female", "comb_m": "build/q265/viewer_zan_vhm", "comb_f": "build/q288/viewer_zan_female"}
BUNDLE = {"own_m": "build/q286_pre/bundle_own_m", "own_f": "build/q288_pre/bundle_own_f"}
WORK = Path("/dev/shm/q293/work")
REPORT = REPO / "data/derived/Q293_page_report.json"
SUBJ = "rule_rf_reflected_q293"
NAME = {"r": "Rectus femoris, reflected (indirect) head (right) -- rule-based", "l": "Rectus femoris, reflected (indirect) head (left) -- rule-based"}
ATTR_RF = ("Reflected (indirect) head of rectus femoris (Q293): RULE-BASED, built on this body's own hip bone and joined to its own rectus "
           "femoris from published cadaveric dimensions (Ryan 2014 doi:10.1016/j.arthro.2014.03.003; Atzmon 2020 doi:10.1007/s00402-019-03293-6; "
           "Gursoy 2024 doi:10.1177/03635465241251824; Hapa 2013 doi:10.1016/j.arthro.2013.08.023); no mesh of it exists in Z-Anatomy, "
           "BodyParts3D, CVH or HRA.")
ATTR_FING = (" Q293: the Z-Anatomy finger bones of this page re-articulated (joint centres of the articulated Z-Anatomy hand carried by each "
             "parent bone, joints closed; finger joint angles refitted to the body's own CT where it shows the finger); finger soft tissue "
             "carried by the pose rig's skinning model.")


def rf_rec(key, side, o):
    lr = {"r": "right", "l": "left"}[side]
    badge = (f"RULE-BASED (Q293): no source we hold has a mesh of this head (Z-Anatomy names it, TA2 2616, without geometry; BodyParts3D, "
             f"CVH and HRA have none), so it is BUILT on this page's own {lr} hip bone and joined to this page's own rectus femoris: footprint "
             f"on the lateral wall of the ilium just above the superior acetabular rim from {o['clock_apex']:.2f} to {o['clock_anterior_end']:.1f} "
             f"o'clock (arthroscopic clock; posterior apex 21 mm of rim posterior to 12:30, Gursoy 2024), {o['footprint_len_mm']} mm long, "
             f"{o['footprint_width_mm'][0]}-{o['footprint_width_mm'][1]} mm wide (literature 38.1-47.7 x 16.8 mm, Atzmon 2020 / Ryan 2014), "
             f"thinner and wider posteriorly (Atzmon 2020); free tendon {o['free_len_mm']} mm forward and down to the confluence with the direct "
             f"(straight) head, {o['confluence_width_thick_mm'][0]} x {o['confluence_width_thick_mm'][1]} mm there (Atzmon 2020); total {o['total_len_mm']} mm "
             f"(literature 55.3 mm). Angle between the two heads at the confluence {o['angle_reflected_vs_direct_head_deg']} deg (measured, no literature "
             f"target). Volume {o['volume_cm3']} cm3. Bone: {o['bone_penetration']['verts_inside_gt_0_5mm_before_push_pct']} % of the vertices were "
             f"> 0.5 mm inside the hip bone as built and were pushed to its surface (+0.3 mm); after: {o['bone_penetration']['verts_inside_gt_0_5mm_after_pct']} %. "
             f"Its deep continuation (the intramuscular tendon of the indirect head, Hasselman 1995) lies inside the rectus femoris mesh and is not drawn. "
             f"This page's rectus femoris reaches to {o['rf_nearest_to_aiis_mm']} mm of the AIIS.")
    return {"name": NAME[side], "latin": "Caput reflexum musculi recti femoris", "folder": "lower_limb", "region": "lower_limb",
            "source": "RULE-BASED from cadaveric studies (PubMed-verified quotes in data/derived/Q293_rf_reflected_head.json): Ryan JM et al. Arthroscopy 2014; "
                      "Atzmon R et al. Arch Orthop Trauma Surg 2020; Gursoy S et al. Am J Sports Med 2024; Hapa O et al. Arthroscopy 2013; Hasselman CT et al. Am J Sports Med 1995",
            "origin": f"hip_bone_{side}: groove above the superior acetabular rim (supra-acetabular groove) and the adjoining hip joint capsule",
            "insertion": f"joins the straight head below the AIIS (conjoint tendon) -> rectus femoris_{side} -> quadriceps tendon",
            "nerve": ["femoral_n"], "procedural_badge": badge,
            "geom_src": f"RULE-BASED (Q293) on this page's own hip bone and rectus femoris; volume {o['volume_cm3']} cm3"}


def load_rf(key):
    z = np.load(WORK / f"rf_reflected_{key}.npz")
    return {"r": (z["vr"], z["fr"]), "l": (z["vl"], z["fl"])}


def build(keys, out_root):
    rep_rf = json.loads(RF.REPORT.read_text())
    prep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    for key in keys:
        RFM = load_rf(key)
        new_ids = [f"rectus_femoris_reflected_head_{s}" for s in "rl"]
        if key.startswith("own"):
            from scripts.transfer.q200_bundle import Bundle
            import build_pages_286 as Q286
            Q286.LIVE[key] = LIVE[key]
            B = Bundle(REPO / BUNDLE[key])
            nfix = 0
            for it in B.items:
                r2 = fix_rec(it["e"].get("rec"))
                if r2:
                    it["e"]["rec"] = r2; nfix += 1
            for s in "rl":
                V, F = RFM[s]
                B.add(f"rectus_femoris_reflected_head_{s}", "muscle", {"r": "right", "l": "left"}[s], SUBJ, rf_rec(key, s, rep_rf[f"{key}_{s}"]), V, F)
            d = Q286.write_page(key, B, {SUBJ: ATTR_RF}, out_root)
            order = [e["id"] for e in json.loads((Path(out_root) / f"bundle_{key}" / "bundle.json").read_text())["structures"]]
            prep[key] = {"added": new_ids, "new_indices": [order.index(i) for i in new_ids], "replaced": [], "replaced_indices": [], "cards_corrected": nfix}
        else:
            from scripts.zanatomy import q205_pages as P5
            import build_pages as BP
            stem = BP.STEM[key]; src = REPO / LIVE[key]
            man, blob = P5.load_page(src, stem)
            E = {m["id"]: i for i, m in enumerate(man["meshes"])}
            replace = {}
            if key.startswith("comb"):
                fr = json.loads(RF.REPORT.parent.joinpath("Q293_fingers.json").read_text())[key]
                z = np.load(WORK / f"fingers_{key}.npz")
                D = P5.decode(man, blob, only=lambda m: m["id"] in set(z.files))
                for k in z.files:
                    rec = json.loads(json.dumps(man["meshes"][E[k]].get("rec") or {}))
                    bone = k in fr["moved_bones"]
                    extra = (" Q293: re-articulated -- this finger bone's own Z-Anatomy shape, unchanged, moved rigidly so that it sits on the joint "
                             "centre of its parent bone (articulated Z-Anatomy hand) and, where the body's own CT shows the finger, to its refitted "
                             "joint angles (data/derived/Q293_fingers.json)." if bone else
                             f" Q293: carried with the re-articulated finger bones by the pose rig's skinning model (max {fr['moved_soft_tissue_max_mm'].get(k, 0)} mm).")
                    rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + extra).strip()
                    replace[k] = (z[k], np.asarray(D[k]["f"], np.int64), rec)
            add = []
            for s in "rl":
                V, F = RFM[s]; r = rf_rec(key, s, rep_rf[f"{key}_{s}"])
                add.append(({"name": r["name"], "id": f"rectus_femoris_reflected_head_{s}", "side": s, "sys": "muscle", "rec": r}, V, F))
            man2 = json.loads(json.dumps(man)); man2["attribution"] = man["attribution"] + " " + ATTR_RF + (ATTR_FING if replace else "")
            meta = {}
            for m in man["meshes"]:
                if m["id"] in replace:
                    r2 = fix_rec(replace[m["id"]][2])
                    if r2:
                        replace[m["id"]] = (replace[m["id"]][0], replace[m["id"]][1], r2)
                    continue
                r2 = fix_rec(m.get("rec"))
                if r2:
                    meta[m["id"]] = (m["name"], r2)
            out = Path(out_root) / DIR[key]
            P5.save_page(out, stem, man2, blob, replace=replace, meta=meta, add=add)
            for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json", src / "plexus_groups.json"]:
                if f.exists():
                    shutil.copy2(f, out / f.name)
            shutil.copy2(out / f"{stem}.html", out / "index.html")
            n0 = len(man["meshes"])
            prep[key] = {"added": new_ids, "new_indices": [n0, n0 + 1], "replaced": sorted(replace), "replaced_indices": sorted(E[k] for k in replace), "cards_corrected": len(meta)}
        print(key, json.dumps({k: (v if not isinstance(v, list) or len(v) < 12 else f"{len(v)} items") for k, v in prep[key].items()}))
    prep["_README"] = ["Q293 page step, scripts/anatomy/q293/pages_q293.py"]
    REPORT.write_text(json.dumps(prep, indent=1), encoding="utf-8")


FINGER_JOINT = ("f2_", "f3_", "f4_", "f5_", "thumb_mcp_", "thumb_ip_")


def splice(key, fresh):
    """committed rig + (a) the new structures' and the replaced geometries' entries from a fresh make_pose_rig run, (b) on the Combined pages
    the finger joints (centres / axes / rest angles) from the same fresh run -- every other entry byte for byte as committed"""
    rep = json.loads(REPORT.read_text())[key]
    committed = REPO / f"data/anatomy/pose_rig_{key}.json"
    A = json.loads(committed.read_text()); F = json.loads(Path(fresh).read_text())
    assert [s[0] for s in A["rig"]["segs"]] == [s[0] for s in F["rig"]["segs"]], "segment lists differ"
    n0, n1 = A["rig"]["count"], F["rig"]["count"]
    assert list(range(n0, n1)) == rep["new_indices"], (n0, n1, rep["new_indices"])
    wa = zlib.decompress(base64.b64decode(A["weights_zlib_b64"])); wf = zlib.decompress(base64.b64decode(F["weights_zlib_b64"]))
    offs = sorted(e[4] for e in F["rig"]["skin"]) + [len(wf)]
    span = {e[0]: (e[4], offs[offs.index(e[4]) + 1]) for e in F["rig"]["skin"]}
    rig = json.loads(json.dumps(A["rig"])); rig["count"] = n1; rig["nv"] = rig["nv"] + [F["rig"]["nv"][i] for i in range(n0, n1)]
    blob = bytearray(wa); fe = {e[0]: e for e in F["rig"]["skin"]}

    def take(i):
        if i in fe:
            e = list(fe[i]); s, t = span[i]; e[4] = len(blob); blob.extend(wf[s:t]); rig["skin"].append(e)
        else:
            hit = [seg for seg, lst in F["rig"]["rigid"] if i in lst]
            assert len(hit) == 1, (i, hit)
            for g in rig["rigid"]:
                if g[0] == hit[0]:
                    g[1].append(i); g[1].sort(); break
            else:
                rig["rigid"].append([hit[0], [i]]); rig["rigid"].sort()
    for i in rep["replaced_indices"]:
        rig["nv"][i] = F["rig"]["nv"][i]
        rig["skin"] = [e for e in rig["skin"] if e[0] != i]
        for g in rig["rigid"]:
            if i in g[1]:
                g[1].remove(i)
        take(i)
    for i in range(n0, n1):
        take(i)
    nj = 0
    if rep["replaced_indices"]:
        FJ = {j["id"]: j for j in F["rig"]["joints"]}
        for k, j in enumerate(rig["joints"]):
            if j["id"].startswith(FINGER_JOINT):
                rig["joints"][k] = FJ[j["id"]]; nj += 1

    def seglen(e):
        return (e[1] + 7) // 8 + e[5] * (2 * e[2] - 1)
    packed = bytearray()
    for e in rig["skin"]:
        s = e[4]; chunk = bytes(blob[s:s + seglen(e)]); e[4] = len(packed); packed.extend(chunk)
    rig["notes"] = A["rig"]["notes"] + (f"; Q293: +{n1 - n0} structures (rule-based reflected heads of rectus femoris)"
                                        + (f", {len(rep['replaced_indices'])} re-articulated finger structures and {nj} finger joints" if nj else "")
                                        + " from a fresh run, every other entry as committed")
    o = dict(A); o["rig"] = rig; o["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(packed), 9)).decode("ascii")
    committed.write_text(json.dumps(o, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(key, "rig", rig["count"], "skinned", len(rig["skin"]), "replaced", len(rep["replaced_indices"]), "new", n1 - n0, "finger joints", nj)


def baseline(key, out_root):
    from scripts.transfer.q200_bundle import Bundle
    import build_pages_286 as Q286
    Q286.LIVE[key] = LIVE[key]
    d = Q286.write_page(key, Bundle(REPO / BUNDLE[key]), {}, out_root)
    live, mine = Q286.geo_digest(key, REPO / LIVE[key]), Q286.geo_digest(key, d)
    print(key, "geo files identical to the live page:", live == mine, len(live), "files")
    return live == mine


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["baseline", "build", "rig"]); ap.add_argument("keys", nargs="*")
    ap.add_argument("--out", default="/dev/shm/q293/pre2"); ap.add_argument("--fresh")
    a = ap.parse_args()
    if a.cmd == "baseline":
        for k in a.keys:
            if not baseline(k, a.out):
                raise SystemExit(1)
    elif a.cmd == "build":
        build(a.keys or list(DIR), a.out)
    else:
        splice(a.keys[0], a.fresh)


if __name__ == "__main__":
    main()
