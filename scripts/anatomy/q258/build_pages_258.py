#!/usr/bin/env python3
"""Q258: add the PROXIMAL brachial plexus to the two own pages (roots/trunks/divisions/cords, rule_brachial_own.py) and
the two missing cords to the four Z-family pages (lateral/medial, rule_cords_z.py), onto the CURRENT page content
(build/q256 -- the last full geometry+UI regen; clinical/* siblings are re-staged fresh by scripts/q258_build_all.sh
to pick up Q257's cine addition, not read from build/q256).

Own pages are rebuilt from the FIXED pre-nerve bundle (build/q249_pre/bundle_own_<m|f>, unchanged since Q249/Q252 per
PROJECT_STATE's own "byte-identical" confirmation) plus a FRESH reapplication of Q249's own pelvic/perineal nerves
(read from the current data/derived/Q249_rule_<key>.{json,npz}, i.e. already carrying Q252's fix) plus this round's
new items -- the same "replay from the fixed baseline" method Q252 itself used, so the ship-diff check below is
against that same baseline and lists EVERY addition (Q249's nerves + Q258's), not just this round's.

Z pages are patched incrementally onto build/q256/<dir> (scripts.zanatomy.q205_pages.save_page, add=[...]) -- the
same method q249/build_pages.py's build_z used, just a different, smaller set of new items.

    python3 scripts/anatomy/q258/build_pages.py KEY [--out build/q258_pre]      KEY = own_m own_f base_m base_f comb_m comb_f
"""
from __future__ import annotations
import argparse, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q248")); sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))
import collect249 as CO249              # noqa: E402
import build_pages as Q249BP            # noqa: E402  (q249's own build_pages.py: OWN_BUNDLE / STEM / sidemap / diff_own)
import rule_brachial_own as RBO         # noqa: E402
import rule_cords_z as RCZ              # noqa: E402

CUR = "build/q256"      # current full-regen content source (own pages' siblings, Z pages' baseline to patch)
DIRS = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas", "base_f": "viewer_base_female",
        "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
SUBJ258 = {"own_f": "ct_vhf_rule_nerve_q258", "own_m": "ct_vhm_rule_nerve_q258"}
ATTR258_OWN = ("Proximal brachial plexus of this atlas (Q258): roots C5-T1, trunks, divisions and cords, round tubes along splines through waypoints measured on this page's own cervical/T1 "
               "vertebrae, scalenus anterior/medius (the interscalene triangle) and clavicle/pectoralis minor; courses from Gray's Anatomy for Students (Drake, Vogl, Mitchell) / Moore, Dalley, "
               "Agur, Clinically Oriented Anatomy / Terminologia Anatomica; not segmented, not Z-Anatomy geometry.")
ATTR258_Z = ("Lateral and medial cords of the brachial plexus (Q258): geometric continuation of this page's own already-shipped anterior-division meshes through the lateral border of "
             "pectoralis minor to the already-shipped terminal nerves they become; not segmented, not newly invented Z-Anatomy geometry.")


def build_own(key, out_root):
    from scripts.transfer.q200_bundle import Bundle
    bsrc = Q249BP.OWN_BUNDLE[key]
    B = Bundle(REPO / bsrc)
    q249_items = CO249.collect(key)
    for it in q249_items:
        B.add(it["id"], it["cat"], Q249BP.sidemap(it["side"]), it["subject"], it["rec"], it["V"], it["F"])
    own_items, notes = RBO.build(key)
    subj = SUBJ258[key]
    for it in own_items:
        B.add(it["id"], it["cat"], Q249BP.sidemap(it["side"]), subj, it["rec"], it["V"], it["F"])
    attr_map = {it["subject"]: Q249BP.ATTR for it in q249_items}
    attr_map[subj] = ATTR258_OWN
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
    new_ids = [i["id"] for i in q249_items] + [i["id"] for i in own_items]
    from scripts.transfer.q234_own_f import keyed
    diff = Q249BP.diff_own(bsrc, bdir, new_ids, Bundle, keyed)
    return own_items, notes, diff


def build_z(key, out_root):
    from scripts.zanatomy import q205_pages as P5
    from scripts.zanatomy import q205_shipdiff as SD
    stem = Q249BP.STEM[key]
    src = REPO / CUR / DIRS[key]; out = REPO / out_root / DIRS[key]
    man, blob = P5.load_page(src, stem)
    items = RCZ.build(key)
    add = [({"name": it["name"], "id": it["id"], "side": it["side"], "sys": "nerve", "rec": it["rec"]}, it["V"], it["F"]) for it in items]
    man = dict(man)
    man["attribution"] = ((man.get("attribution") or "").rstrip() + " " + ATTR258_Z).strip()
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
    ap = argparse.ArgumentParser(); ap.add_argument("key", choices=list(DIRS)); ap.add_argument("--out", default="build/q258_pre")
    a = ap.parse_args()
    if a.key in ("own_m", "own_f"):
        items, notes, diff = build_own(a.key, a.out)
    else:
        items, diff = build_z(a.key, a.out)
    print(a.key, "shipped", len(items), "unlisted:", diff.get("unlisted") or diff.get("unlisted_changes"))
