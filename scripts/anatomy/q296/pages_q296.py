#!/usr/bin/env python3
"""Q296 page step: the four Z pages (build/q295) + the four imported SPL Inner Ear Atlas structures per side.

    python3 scripts/anatomy/q296/pages_q296.py build [KEY...] [--out /dev/shm/q296/pre]  -> page dirs + data/derived/Q296_page_report.json
    python3 scripts/anatomy/q296/pages_q296.py rig KEY --fresh FRESH.json                 -> splice the new entries into data/anatomy/pose_rig_KEY.json

The two Imaging pages are NOT touched: they have no ear ossicles (neither her 1.5 mm CT nor his 1 mm cryosections
resolve them), so there is nothing to register onto, and the brief forbids replacing anything that comes from a
subject's own imaging. Every other structure on the four Z pages is copied byte for byte (q205_pages.save_page).
"""
from __future__ import annotations

import argparse, json, os, shutil, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (str(HERE), str(REPO), str(REPO / "scripts/anatomy/q295"), str(REPO / "scripts/anatomy/q249")):
    if p not in sys.path:
        sys.path.insert(0, p)

EAR = Path(os.environ.get("Q296_OUT", "/dev/shm/q296/ear"))
DIR = {"base_m": "viewer_zan_atlas", "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
LIVE = {k: f"build/q295/{d}" for k, d in DIR.items()}
REPORT = Path(os.environ.get("Q296_PAGE_REPORT", str(REPO / "data/derived/Q296_page_report.json")))

ATLAS = ("SPL Inner Ear Atlas (Open Anatomy Project, release February 2018): Bartling S (DKFZ), Jakab M (SPL), "
         "Kikinis R (SPL); German Cancer Research Center, Heidelberg and the Surgical Planning Laboratory, Department "
         "of Radiology, Brigham and Women's Hospital, Harvard Medical School. Experimental flat-panel CT of a human "
         "temporal bone, about 140 um high-contrast resolution (Gupta R, Bartling SH et al., AJNR Am J Neuroradiol "
         "2004;25(8):1417-24, PMID 15466345). Funded by NIH P41 RR013218 (NCRR) and P41 EB015902 (NIBIB) through the "
         "Neuroimaging Analysis Center, and the Google Faculty Research Award. Licensed under the 3D Slicer License "
         "Part B; the full licence text, the attributions and the list of our modifications are in "
         "third_party/openanatomy_spl/ (LICENSE, NOTICE, README.md).")

FOLDER = {"bone": ("skeleton", "cranium_face"), "muscle": ("head_and_neck", "head")}
SIDEW = {"l": "left", "r": "right"}


def attribution():
    return ("Inner and middle ear (Q296): the bony labyrinth, the osseous spiral lamina, the round window and the "
            "stapedius are IMPORTED REAL MESHES from the SPL Inner Ear Atlas of the Open Anatomy Project (flat-panel "
            "CT of a human temporal bone, about 140 um), not Z-Anatomy geometry and not drawn by hand. They are placed "
            "by a similarity registration of that atlas's own malleus, incus and stapes onto this page's three ossicles, "
            "and are modified versions of the atlas models (scale corrected, decimated, the left side mirrored from the "
            "atlas's right ear). All or portions of this licensed product (such portions are the \"Software\") have been "
            "obtained under license from The Brigham and Women's Hospital, Inc. and are subject to the terms and "
            "conditions of the 3D Slicer License, reproduced in full in third_party/openanatomy_spl/LICENSE.")


def rec_for(uid, side, st, fit):
    folder, region = FOLDER[st["cat"]]
    ov = "; ".join(f"{h['name']} {h['pct_of_volume']} %" for h in st.get("overlap", [])) or "none above 0.5 %"
    badge = (
        f"Q296 IMPORTED REAL MESH, NOT RULE-BASED: segmented from the SPL Inner Ear Atlas's own flat-panel CT of a human "
        f"temporal bone (about 140 um), licensed under the 3D Slicer License Part B. It is a MODIFIED version of that "
        f"atlas's model {st['atlas_model']}, clearly marked as such and not the original: (1) one similarity transform "
        f"(uniform scale, rotation, translation) fitted by nearest-point ICP from the atlas's own malleus, incus and "
        f"stapes onto THIS page's three ossicles -- {fit['n']} points, residual {fit['median_mm']:.2f} mm median, "
        f"{fit['p95_mm']:.2f} mm p95, {fit['max_mm']:.2f} mm max, RMS {fit['rms']:.2f} mm; "
        f"(2) the atlas's model coordinates are uniformly about {1 / fit['s']:.2f}x life size (its label maps were meshed "
        f"with the scanner's nominal spacing, not the 140 um voxel), which this page's fitted scale {fit['s']:.5f} "
        f"corrects; (3) quadric decimation from {st['tris_atlas']} to {st['tris']} triangles (volume changed "
        f"{abs(st['cm3'] - st['cm3_undecimated']) / max(st['cm3_undecimated'], 1e-9) * 100:.2f} %); "
        f"(4) the atlas ear is a RIGHT ear, so the left side is its mirror image, not an independently segmented left ear. "
        f"Volume {st['cm3']} cm3, {st['tris']} triangles, mean dihedral {st['dihedral_mean_deg']} deg "
        f"(the atlas mesh itself {st['dihedral_atlas_deg']} deg; the CVH reference meshes are 27.6 / 29.5 / 31.7 deg -- "
        f"this source is finer than CVH's 1 mm cryosections, so a smaller angle is expected), defect edges "
        f"{st['defect_edges_pct']} %, extent {st['ext_mm'][0]} x {st['ext_mm'][1]} x {st['ext_mm'][2]} mm. "
        f"Non-penetration check against every page structure whose box it touches: {ov}. "
        f"{st['inside_temporal_bone_pct']} % of its volume falls inside this page's own temporal bone "
        f"(the labyrinth and the spiral lamina are cavities inside the petrous temporal, so containment is the correct "
        f"result; the remainder is the Z-Anatomy temporal bone's own coarseness, not a displacement of this mesh). "
        f"Research use only (3D Slicer License Part B paragraph 4), which is what this page's "
        f"\"simulation, not for clinical use\" badge already states."
    )
    return {"name": st["name"], "latin": st["latin"], "folder": folder, "region": region,
            "source": ATLAS, "procedural_badge": badge,
            "geom_src": (f"SPL Inner Ear Atlas (Open Anatomy), flat-panel CT about 140 um, 3D Slicer License Part B "
                         f"(third_party/openanatomy_spl/LICENSE); registered onto this page's own ossicles and decimated: "
                         f"{st['cm3']} cm3, {st['tris']} triangles")}


def load(key):
    st = json.loads((EAR / f"{key}_ear.json").read_text())
    z = np.load(EAR / f"{key}_ear.npz")
    items = []
    for side in ("l", "r"):
        fit = st[f"_fit_{side}"]
        for uid in ("labyrinth", "spiral_lamina", "fenestra_cochleae", "stapedius"):
            d = st[f"{uid}_{side}"]
            items.append((f"oa_{uid}_{side}", side, d, z[f"{uid}_{side}__v"], z[f"{uid}_{side}__f"], rec_for(uid, side, d, fit)))
    return items, st


def build(keys, out_root):
    from scripts.zanatomy import q205_pages as P5
    import build_pages as BP
    prep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    for key in keys:
        items, st = load(key)
        stem = BP.STEM[key]; src = REPO / LIVE[key]
        man, blob = P5.load_page(src, stem)
        add = [({"name": d["name"], "id": uid, "side": side, "sys": d["cat"], "rec": rec}, V, F)
               for uid, side, d, V, F, rec in items]
        man2 = json.loads(json.dumps(man)); man2["attribution"] = man["attribution"] + " " + attribution()
        dd = Path(out_root) / DIR[key]
        P5.save_page(dd, stem, man2, blob, add=add)
        for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json", src / "plexus_groups.json"]:
            if f.exists():
                shutil.copy2(f, dd / f.name)
        shutil.copy2(dd / f"{stem}.html", dd / "index.html")
        n0 = len(man["meshes"])
        prep[key] = {"added": [u for u, *_ in items], "new_indices": list(range(n0, n0 + len(add))),
                     "replaced": [], "replaced_indices": [],
                     "triangles_added": int(sum(d["tris"] for _, _, d, *_ in items)),
                     "cm3": {u: d["cm3"] for u, _, d, *_ in items},
                     "fit": {s: {k: v for k, v in st[f"_fit_{s}"].items() if k != "R"} for s in ("l", "r")}}
        print(key, "meshes", n0, "->", n0 + len(add), "| +", prep[key]["triangles_added"], "triangles", flush=True)
    prep["_README"] = ["Q296 page step (SPL Inner Ear Atlas import), scripts/anatomy/q296/pages_q296.py"]
    REPORT.write_text(json.dumps(prep, indent=1), encoding="utf-8")


def splice(key, fresh):
    """committed rig + only the new structures' entries from a fresh make_pose_rig run (Q295's splice, verbatim)."""
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
    rig["notes"] = A["rig"]["notes"] + f"; Q296: +{n1 - n0} structures (SPL Inner Ear Atlas import) from a fresh run, every other entry as committed"
    o = dict(A); o["rig"] = rig; o["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(packed), 9)).decode("ascii")
    committed.write_text(json.dumps(o, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(key, "rig", rig["count"], "skinned", len(rig["skin"]), "new skinned", nsk, "new rigid", nrg)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build", "rig"]); ap.add_argument("keys", nargs="*")
    ap.add_argument("--out", default="/dev/shm/q296/pre"); ap.add_argument("--fresh")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.keys or list(DIR), a.out)
    else:
        splice(a.keys[0], a.fresh)


if __name__ == "__main__":
    main()
