#!/usr/bin/env python3
"""Q295 page step: the six live pages (build/q293) + the fat / unlabelled-soft-tissue meshes of fat295.py as a new system `fat`.

    python3 scripts/anatomy/q295/pages_q295.py build [KEY...] [--out /dev/shm/q295/pre]   -> page dirs + data/derived/Q295_page_report.json
    python3 scripts/anatomy/q295/pages_q295.py rig KEY --fresh FRESH.json                  -> splice the new entries into data/anatomy/pose_rig_KEY.json

Every other structure is copied byte for byte (Z pages: q205_pages.save_page; own pages: the Q286 bundle path)."""
from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
for p in (HERE, REPO, REPO / "scripts/anatomy/q286", REPO / "scripts/anatomy/q249", REPO / "scripts/anatomy/q293"):
    sys.path.insert(0, str(p))

FAT = Path("/dev/shm/q295/fat")
DIR = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas", "base_f": "viewer_base_female",
       "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
LIVE = {k: f"build/q293/{d}" for k, d in DIR.items()}
BUNDLE = {"own_m": "build/q293/bundle_own_m", "own_f": "build/q293/bundle_own_f"}
import os
REPORT = Path(os.environ.get("Q295_PAGE_REPORT", str(REPO / "data/derived/Q295_page_report.json")))
SUBJ = {"own_f": "img_vhf_fat_q295", "own_m": "img_vhm_fat_q295", "comb_f": "img_vhf_fat_q295", "comb_m": "img_vhm_fat_q295",
        "base_f": "reg_vhf_fat_q295", "base_m": "reg_vhm_fat_q295"}
WHO = {"vhf": ("her", "Her"), "vhm": ("his", "His")}
BODY = {"own_m": "vhm", "comb_m": "vhm", "base_m": "vhm", "own_f": "vhf", "comb_f": "vhf", "base_f": "vhf"}
IMG = {"vhf": "her own CT (NLM Visible Human Project female, fresh-cadaver CT: torso block + femur-to-toes block, public domain)",
       "vhm": "his own colour cryosections (NLM Visible Human Project male, 1 mm full-colour photographs, public domain; his frozen CT cannot separate fat from muscle)"}
RULE = {"vhf": "fat = HU -190..-30 (and -400..-190 partial volume at fat/air edges), soft tissue = HU -29..+200",
        "vhm": "fat = the cryosection colour class 'fat' (pale cream / yellow, scripts/cryo/cryo_classes.py), soft tissue = muscle-red, pale connective and other tissue colours"}


def attribution(key):
    b = BODY[key]
    s = (f"Fat and unlabelled soft tissue (Q295): the space inside this page's skin that no segmented structure covers, classified voxel by voxel "
         f"(1 mm) from {IMG[b]}: {RULE[b]}; meshed by marching cubes and decimated; not drawn by hand.")
    if key.startswith("base"):
        s += (" On this generic body the imaging class is read through a thin-plate-spline registration onto the Combined page of the same "
              "Visible Human body (vertex pairs of every structure the two pages share).")
    return s


def rec_for(key, uid, d, page_stats, reg_info=None):
    b = BODY[key]; who, Who = WHO[b]
    kind, part = d["kind"], d["part"]
    base = part[:-2] if part[-2:] in ("_r", "_l") else part
    common = (f"Volume {d['mesh_cm3']} cm3 (voxels {d['vox_cm3']} cm3), {d['tris']} triangles, mean dihedral {d['dihedral_mean_deg']} deg. "
              f"Body part by the nearest bone in each 1 mm section; subcutaneous / deep split at a 5 mm closing of the page's structures; "
              f"the skin itself (1.5 mm) is not counted. Where the imaging body outline and this page's skin differ (<= 20 mm), the class of the "
              f"nearest imaged tissue is used ({page_stats['propagated_pct']} % of this page's void voxels). It is clipped to the space the page "
              f"leaves empty; where the 4-5 mm meshing smooths it into a neighbouring structure the overlap is measured (data/derived/Q295_fat_report.json: median about 2 % of its section area).")
    if key.startswith("base"):
        common += (f" Registration to the Combined page of the same body: {reg_info['kept']} vertex pairs, median residual "
                   f"{reg_info['resid_median_mm']:.1f} mm, p95 {reg_info['resid_p95_mm']:.1f} mm; the generic Z-Anatomy body is not that person, so this is "
                   f"{who} fat pattern carried onto it, not this body's own.")
    if kind == "soft":
        ident = (page_stats.get("ident") or {}).get(part) or {}
        tot = sum(ident.values()) or 1
        top = [f"{k} {round(100 * v / tot)} %" for k, v in list(ident.items())[:6] if v / tot >= 0.03]
        idt = (f" At these points the Imaging page of the same body (its own segmentations) has: " + "; ".join(top) + "." if top else "")
        badge = (f"Q295 MEASURED FROM IMAGING: space this page leaves empty although {who} imaging shows SOFT TISSUE there (not fat), thicker than ~4 mm "
                 f"(thin seams between structures are left as they are). It marks tissue the page has not segmented, or segmented too thin / "
                 f"elsewhere: unsegmented muscle, fascia, vessels, lymph nodes, glands, dermis.{idt} {common}")
        return {"name": d["name"], "folder": "fat", "region": base,
                "source": f"{Who} own imaging, Q295 ({IMG[b]})", "procedural_badge": badge,
                "geom_src": f"Q295 imaging class 'soft tissue' in the page's empty space: {d['mesh_cm3']} cm3, {d['tris']} triangles"}
    latin = "Panniculus adiposus (tela subcutanea)" if kind == "fat_sub" else "Textus adiposus"
    badge = (f"Q295 MEASURED FROM IMAGING: {who} {'subcutaneous' if kind == 'fat_sub' else 'deep'} fat where {who} imaging shows fat and the page "
             f"has no structure; fat thinner than ~2 mm and pieces under 0.1 cm3 are not meshed. {common}")
    return {"name": d["name"], "latin": latin, "folder": "fat", "region": base,
            "source": f"{Who} own imaging, Q295 ({IMG[b]})", "procedural_badge": badge,
            "geom_src": f"Q295 fat from imaging: {d['mesh_cm3']} cm3, {d['tris']} triangles"}


def load(key):
    rep = json.loads((FAT / f"{key}_fat.json").read_text())
    z = np.load(FAT / f"{key}_fat.npz")
    vs = json.loads((FAT / f"{key}_vox.json").read_text())
    st = {"propagated_pct": round(100 * vs["propagated"] / max(vs["void"], 1), 1), "ident": vs.get("soft_void_identified_by_imaging_page_cm3")}
    reg = None
    if key.startswith("base"):
        import pickle, reg295  # noqa: F401  (unpickling needs lib292 on the path)
        reg = pickle.loads(Path(f"/dev/shm/q295/reg_{key}.pkl").read_bytes()).info
    out = []
    for uid, d in rep.items():
        out.append((uid, d, z[f"{uid}__v"], z[f"{uid}__f"], rec_for(key, uid, d, st, reg)))
    return out, st


def side_of(part):
    return {"_r": "r", "_l": "l"}.get(part[-2:], "m")


def build(keys, out_root):
    prep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    for key in keys:
        items, st = load(key)
        if key.startswith("own"):
            from scripts.transfer.q200_bundle import Bundle
            import build_pages_286 as Q286
            Q286.LIVE[key] = LIVE[key]
            B = Bundle(REPO / BUNDLE[key])
            for uid, d, V, F, rec in items:
                B.add(uid, "fat", {"r": "right", "l": "left", "m": None}[side_of(d["part"])], SUBJ[key], rec, V, F)
            dd = Q286.write_page(key, B, {SUBJ[key]: attribution(key)}, out_root)
            order = [e["id"] for e in json.loads((Path(out_root) / f"bundle_{key}" / "bundle.json").read_text())["structures"]]
            new = [order.index(u) for u, *_ in items]
        else:
            from scripts.zanatomy import q205_pages as P5
            import build_pages as BP
            stem = BP.STEM[key]; src = REPO / LIVE[key]
            man, blob = P5.load_page(src, stem)
            add = [({"name": rec["name"], "id": uid, "side": side_of(d["part"]), "sys": "fat", "rec": rec}, V, F) for uid, d, V, F, rec in items]
            man2 = json.loads(json.dumps(man)); man2["attribution"] = man["attribution"] + " " + attribution(key)
            dd = Path(out_root) / DIR[key]
            P5.save_page(dd, stem, man2, blob, add=add)
            for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json", src / "plexus_groups.json"]:
                if f.exists():
                    shutil.copy2(f, dd / f.name)
            shutil.copy2(dd / f"{stem}.html", dd / "index.html")
            n0 = len(man["meshes"]); new = list(range(n0, n0 + len(add)))
        prep[key] = {"added": [u for u, *_ in items], "new_indices": new, "replaced": [], "replaced_indices": [],
                     "triangles_added": int(sum(d["tris"] for _, d, *_ in items)),
                     "fat_cm3": round(sum(d["mesh_cm3"] for _, d, *_ in items if d["kind"] != "soft"), 1),
                     "soft_cm3": round(sum(d["mesh_cm3"] for _, d, *_ in items if d["kind"] == "soft"), 1)}
        print(key, {k: (v if not isinstance(v, list) else f"{len(v)} items") for k, v in prep[key].items()}, flush=True)
    prep["_README"] = ["Q295 page step (fat system), scripts/anatomy/q295/pages_q295.py"]
    REPORT.write_text(json.dumps(prep, indent=1), encoding="utf-8")


def splice(key, fresh):
    """committed rig + the new structures' entries from a fresh make_pose_rig run on the new page; every other entry byte for byte as committed"""
    import base64, zlib
    rep = json.loads(REPORT.read_text())[key]
    committed = REPO / f"data/anatomy/pose_rig_{key}.json"
    A = json.loads(committed.read_text()); F = json.loads(Path(fresh).read_text())
    assert [s_[0] for s_ in A["rig"]["segs"]] == [s_[0] for s_ in F["rig"]["segs"]], "segment lists differ"
    n0, n1 = A["rig"]["count"], F["rig"]["count"]
    assert list(range(n0, n1)) == rep["new_indices"], (n0, n1, rep["new_indices"][:3])
    wa = zlib.decompress(base64.b64decode(A["weights_zlib_b64"])); wf = zlib.decompress(base64.b64decode(F["weights_zlib_b64"]))
    offs = sorted(e[4] for e in F["rig"]["skin"]) + [len(wf)]
    span = {e[0]: (e[4], offs[offs.index(e[4]) + 1]) for e in F["rig"]["skin"]}
    rig = json.loads(json.dumps(A["rig"])); rig["count"] = n1; rig["nv"] = rig["nv"] + [F["rig"]["nv"][i] for i in range(n0, n1)]
    blob = bytearray(wa); fe = {e[0]: e for e in F["rig"]["skin"]}
    nsk = nrg = 0
    for i in range(n0, n1):
        if i in fe:
            e = list(fe[i]); s0, t0 = span[i]; e[4] = len(blob); blob.extend(wf[s0:t0]); rig["skin"].append(e); nsk += 1
        else:
            hit = [seg for seg, lst in F["rig"]["rigid"] if i in lst]
            assert len(hit) == 1, (i, hit)
            for g in rig["rigid"]:
                if g[0] == hit[0]:
                    g[1].append(i); g[1].sort(); break
            else:
                rig["rigid"].append([hit[0], [i]]); rig["rigid"].sort()
            nrg += 1

    def seglen(e):
        return (e[1] + 7) // 8 + e[5] * (2 * e[2] - 1)
    packed = bytearray()
    for e in rig["skin"]:
        s0 = e[4]; chunk = bytes(blob[s0:s0 + seglen(e)]); e[4] = len(packed); packed.extend(chunk)
    rig["notes"] = A["rig"]["notes"] + f"; Q295: +{n1 - n0} structures (fat / unlabelled soft tissue from imaging) from a fresh run, every other entry as committed"
    o = dict(A); o["rig"] = rig; o["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(packed), 9)).decode("ascii")
    committed.write_text(json.dumps(o, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(key, "rig", rig["count"], "skinned", len(rig["skin"]), "new skinned", nsk, "new rigid", nrg)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build", "rig"]); ap.add_argument("keys", nargs="*")
    ap.add_argument("--out", default="/dev/shm/q295/pre"); ap.add_argument("--fresh")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.keys or list(DIR), a.out)
    else:
        splice(a.keys[0], a.fresh)


if __name__ == "__main__":
    main()
