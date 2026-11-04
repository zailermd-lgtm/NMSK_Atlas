#!/usr/bin/env python3
"""Q260: round 3 of the owner's "all plexuses and major nerves" program. Adds, onto CURRENT page content
(build/q259 -- Q259's own output): the vagus nerve's cervical TRUNK on the two own pages (rule_vagus_own.py),
genuine lumbar/sacral plexus fills (rule_limb_fill.py, lumbar roots in psoas, femoral/tibial/sciatic muscular
branches, tibial medial calcaneal branches), and thoracic dorsal rami medial branches T1-T11 (rule_thoracic.py).

Own pages: replayed from the FIXED pre-nerve bundle (build/q248_pre/bundle_own_<m|f>) + Q249's pelvic nerves +
Q258's brachial plexus + Q259's cervical/splanchnic items + this round's new items -- the SAME "replay from the
fixed baseline" method Q258/Q259 each used, so the ship-diff lists every addition across all four rounds.
Z pages: patched incrementally onto build/q259/<dir> (q205_pages.save_page, add=[...]), the same method Q258/Q259
each used for their own additions.

    python3 scripts/anatomy/q260/build_pages_260.py KEY [--out build/q260_pre]      KEY = own_m own_f base_m base_f comb_m comb_f
"""
from __future__ import annotations
import argparse, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q248")); sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q258")); sys.path.insert(0, str(REPO / "scripts/anatomy/q259"))
import collect249 as CO249              # noqa: E402
import build_pages as Q249BP            # noqa: E402
import rule_brachial_own as RBO         # noqa: E402
import rule_cervical as RCV             # noqa: E402
import rule_splanchnic as RSP           # noqa: E402
import rule_vagus as RVG                # noqa: E402
import rule_vagus_own as RVGO           # noqa: E402
import rule_limb_fill as RLF            # noqa: E402
import rule_thoracic as RTH             # noqa: E402

CUR = "build/q259"
DIRS = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas", "base_f": "viewer_base_female",
        "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
SUBJ260 = {"own_f": "ct_vhf_rule_nerve_q260", "own_m": "ct_vhm_rule_nerve_q260"}
ATTR260_OWN = ("Vagus nerve cervical trunk, lumbar-plexus roots within psoas, femoral/tibial/sciatic muscular branches and thoracic dorsal-ramus medial branches of this atlas (Q260): round tubes along splines through "
               "waypoints measured on this page's own carotid-sheath vessels, vertebrae, psoas/iliopsoas and the nerve trunks already shipped; courses from Gray's Anatomy for Students (Drake, Vogl, Mitchell) / Moore, "
               "Dalley, Agur, Clinically Oriented Anatomy / Terminologia Anatomica; not segmented, not Z-Anatomy geometry.")
ATTR260_Z = ("Lumbar-plexus roots within psoas, femoral/tibial/sciatic muscular branches and thoracic dorsal-ramus medial branches (Q260): rule-based round tubes through waypoints measured on this page's own vertebrae, "
             "psoas major / iliacus, and the real nerve-trunk centrelines already shipped; courses from the same textbooks; not newly invented Z-Anatomy geometry.")


def _own_items(key):
    items = []
    for fn in (RCV.build, RSP.build, RVG.build, RVGO.build, RLF.build, RTH.build):
        out, _ = fn(key, root=CUR)
        items += [it for it in out if it.get("status") == "ship"]
    return items


def _z_items(key):
    items = []
    for fn in (RLF.build, RTH.build):
        out, _ = fn(key, root=CUR)
        items += [it for it in out if it.get("status") == "ship"]
    return items


def build_own(key, out_root):
    from scripts.transfer.q200_bundle import Bundle
    bsrc = Q249BP.OWN_BUNDLE[key]
    B = Bundle(REPO / bsrc)
    q249_items = CO249.collect(key)
    for it in q249_items:
        B.add(it["id"], it["cat"], Q249BP.sidemap(it["side"]), it["subject"], it["rec"], it["V"], it["F"])
    brachial_items, _ = RBO.build(key)
    subj258 = {"own_f": "ct_vhf_rule_nerve_q258", "own_m": "ct_vhm_rule_nerve_q258"}[key]
    for it in brachial_items:
        B.add(it["id"], it["cat"], Q249BP.sidemap(it["side"]), subj258, it["rec"], it["V"], it["F"])
    cerv, _ = RCV.build(key, root=CUR)
    spl, _ = RSP.build(key, root=CUR)
    vag, _ = RVG.build(key, root=CUR)
    q259_items = [it for it in (cerv + spl + vag) if it.get("status") == "ship"]
    subj259 = {"own_f": "ct_vhf_rule_nerve_q259", "own_m": "ct_vhm_rule_nerve_q259"}[key]
    for it in q259_items:
        B.add(it["id"], it["cat"], Q249BP.sidemap(it["side"]), subj259, it["rec"], it["V"], it["F"])
    vago, _ = RVGO.build(key, root=CUR)
    lfi, _ = RLF.build(key, root=CUR)
    thr, _ = RTH.build(key, root=CUR)
    own_items = [it for it in (vago + lfi + thr) if it.get("status") == "ship"]
    subj = SUBJ260[key]
    for it in own_items:
        B.add(it["id"], it["cat"], Q249BP.sidemap(it["side"]), subj, it["rec"], it["V"], it["F"])
    attr_map = {it["subject"]: Q249BP.ATTR for it in q249_items}
    attr_map[subj258] = ("Proximal brachial plexus of this atlas (Q258): roots C5-T1, trunks, divisions and cords, round tubes along splines through waypoints measured on this page's own cervical/T1 "
                          "vertebrae, scalenus anterior/medius and clavicle/pectoralis minor; courses from Gray's Anatomy for Students / Moore, Dalley, Agur / Terminologia Anatomica; not segmented, not Z-Anatomy geometry.")
    attr_map[subj259] = ("Cervical plexus, thoracic/lumbar/sacral splanchnic nerves and the lumbar/sacral sympathetic chain of this atlas (Q259): round tubes along splines through waypoints measured on this page's own "
                          "cervical/thoracic/lumbar vertebrae, sternocleidomastoid, scalenes, common carotid artery and abdominal aorta; courses from the same textbooks; not segmented, not Z-Anatomy geometry.")
    attr_map[subj] = ATTR260_OWN
    bdir = REPO / out_root / f"bundle_{key}"
    B.write(bdir, new_subject_attribution=attr_map, copy_clinical=True)
    d = REPO / out_root / DIRS[key]; d.mkdir(parents=True, exist_ok=True)
    stem = Q249BP.STEM[key] + ".html"
    cmd = [sys.executable, str(REPO / "scripts/build_viewer_html.py"), "--bundle", str(bdir), "-o", str(d / stem), "--external-bin"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    print((r.stdout or "").strip().splitlines()[-1:] or r.stderr[-300:])
    if r.returncode:
        raise SystemExit(r.stderr[-800:])
    txt = (d / stem).read_text(encoding="utf-8")
    txt = txt.replace("<title>NMSK Atlas Viewer</title>", f"<title>{Q249BP.TITLE[key]}</title>")
    (d / stem).write_text(txt, encoding="utf-8")
    src_page = REPO / CUR / DIRS[key]
    for f in list(src_page.glob("clinical_*")) + [src_page / "parts_data.json", src_page / "symmetry_q237.json", src_page / "plexus_groups.json"]:
        if f.exists():
            shutil.copy2(f, d / f.name)
    new_ids = [i["id"] for i in q249_items] + [i["id"] for i in brachial_items] + [i["id"] for i in q259_items] + [i["id"] for i in own_items]
    from scripts.transfer.q234_own_f import keyed
    diff = Q249BP.diff_own(bsrc, bdir, new_ids, Bundle, keyed)
    return own_items, diff


def build_z(key, out_root):
    from scripts.zanatomy import q205_pages as P5
    from scripts.zanatomy import q205_shipdiff as SD
    stem = Q249BP.STEM[key]
    src = REPO / CUR / DIRS[key]; out = REPO / out_root / DIRS[key]
    man, blob = P5.load_page(src, stem)
    items = _z_items(key)
    add = [({"name": it["name"], "id": it["id"], "side": it["side"], "sys": "nerve", "rec": it["rec"]}, it["V"], it["F"]) for it in items]
    man = dict(man)
    man["attribution"] = ((man.get("attribution") or "").rstrip() + " " + ATTR260_Z).strip()
    P5.save_page(out, stem, man, blob, add=add)
    for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json", src / "plexus_groups.json"]:
        if f.exists():
            shutil.copy2(f, out / f.name)
    r = SD.diff(src, out, stem, [])
    listed = sorted(e["id"] for e, _, _ in add)
    diff = dict(source=str(src.relative_to(REPO)), new=str(out.relative_to(REPO)), added=r["added"], added_expected=listed, removed=r["removed"],
                geometry_changed=sorted(r["geometry_changed"]), card_only=sorted(r["card_only"]), unchanged=r["unchanged"],
                unlisted=sorted(set(r["added"]) ^ set(listed)) + sorted(r["card_only"]) + sorted(r["geometry_changed"]) + sorted(r["removed"]))
    return items, diff


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("key", choices=list(DIRS)); ap.add_argument("--out", default="build/q260_pre")
    a = ap.parse_args()
    if a.key in ("own_m", "own_f"):
        items, diff = build_own(a.key, a.out)
    else:
        items, diff = build_z(a.key, a.out)
    print(a.key, "shipped", len(items), "unlisted:", diff.get("unlisted") or diff.get("unlisted_changes"))
