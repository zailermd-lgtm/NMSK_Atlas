#!/usr/bin/env python3
"""Q259: add the CERVICAL PLEXUS (rule_cervical.py, all six pages), the THORACIC/LUMBAR/SACRAL SPLANCHNIC NERVES +
the LUMBAR/SACRAL sympathetic chain (rule_splanchnic.py, all six pages) and the VAGUS's recurrent laryngeal branch
(rule_vagus.py, the four Z pages only) onto the CURRENT page content (build/q258 -- Q258's own output, the last
full regen + its brachial-plexus additions).

Own pages: replayed from the FIXED pre-nerve bundle (build/q248_pre/bundle_own_<m|f>) + a fresh reapplication of
Q249's pelvic nerves (collect249.collect) + Q258's brachial plexus (rule_brachial_own.build) + this round's new
items -- the SAME "replay from the fixed baseline" method Q258 itself used, so the ship-diff below lists every
addition across all three rounds, not just this one.
Z pages: patched incrementally onto build/q258/<dir> (scripts.zanatomy.q205_pages.save_page, add=[...]), the same
method Q258 used for its own two cords.

    python3 scripts/anatomy/q259/build_pages_259.py KEY [--out build/q259_pre]      KEY = own_m own_f base_m base_f comb_m comb_f
"""
from __future__ import annotations
import argparse, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q248")); sys.path.insert(0, str(REPO / "scripts/anatomy/q249")); sys.path.insert(0, str(REPO / "scripts/anatomy/q258"))
import collect249 as CO249              # noqa: E402
import build_pages as Q249BP            # noqa: E402
import rule_brachial_own as RBO         # noqa: E402
import rule_cervical as RCV             # noqa: E402
import rule_splanchnic as RSP           # noqa: E402
import rule_vagus as RVG                # noqa: E402

CUR = "build/q258"
DIRS = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas", "base_f": "viewer_base_female",
        "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
SUBJ259 = {"own_f": "ct_vhf_rule_nerve_q259", "own_m": "ct_vhm_rule_nerve_q259"}
ATTR259_OWN = ("Cervical plexus (C1-C4 roots, ansa cervicalis, phrenic n. origin + proximal course, scalene branch, 4 cutaneous branches) and thoracic/lumbar/sacral splanchnic nerves + the lumbar/sacral sympathetic "
               "chain of this atlas (Q259): round tubes along splines through waypoints measured on this page's own cervical/thoracic/lumbar vertebrae, sternocleidomastoid, scalenes, common carotid artery and "
               "abdominal aorta; courses from Gray's Anatomy for Students (Drake, Vogl, Mitchell) / Moore, Dalley, Agur, Clinically Oriented Anatomy / Terminologia Anatomica; not segmented, not Z-Anatomy geometry.")
ATTR259_Z = ("Cervical plexus, thoracic/lumbar/sacral splanchnic nerves + lumbar/sacral sympathetic chain, and the vagus nerve's recurrent laryngeal branch (Q259): rule-based round tubes through waypoints measured "
             "on this page's own vertebrae / sternocleidomastoid / scalenes / carotid-subclavian-aortic vessels / trachea / cricoid cartilage, or (thoracic splanchnics' origin) the real already-shipped "
             "zan_sympathetic_trunk mesh; courses from the same textbooks; not newly invented Z-Anatomy geometry.")


def _own_items(key):
    items = []
    for fn in (RCV.build, RSP.build, RVG.build):
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
    own_items = _own_items(key)
    subj = SUBJ259[key]
    for it in own_items:
        B.add(it["id"], it["cat"], Q249BP.sidemap(it["side"]), subj, it["rec"], it["V"], it["F"])
    attr_map = {it["subject"]: Q249BP.ATTR for it in q249_items}
    attr_map[subj258] = ("Proximal brachial plexus of this atlas (Q258): roots C5-T1, trunks, divisions and cords, round tubes along splines through waypoints measured on this page's own cervical/T1 "
                          "vertebrae, scalenus anterior/medius and clavicle/pectoralis minor; courses from Gray's Anatomy for Students / Moore, Dalley, Agur / Terminologia Anatomica; not segmented, not Z-Anatomy geometry.")
    attr_map[subj] = ATTR259_OWN
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
    new_ids = [i["id"] for i in q249_items] + [i["id"] for i in brachial_items] + [i["id"] for i in own_items]
    from scripts.transfer.q234_own_f import keyed
    diff = Q249BP.diff_own(bsrc, bdir, new_ids, Bundle, keyed)
    return own_items, diff


def build_z(key, out_root):
    from scripts.zanatomy import q205_pages as P5
    from scripts.zanatomy import q205_shipdiff as SD
    stem = Q249BP.STEM[key]
    src = REPO / CUR / DIRS[key]; out = REPO / out_root / DIRS[key]
    man, blob = P5.load_page(src, stem)
    cerv, _ = RCV.build(key, root=CUR)
    spl, _ = RSP.build(key, root=CUR)
    vag, _ = RVG.build(key, root=CUR)
    items = [it for it in (cerv + spl + vag) if it.get("status") == "ship"]
    add = [({"name": it["name"], "id": it["id"], "side": it["side"], "sys": "nerve", "rec": it["rec"]}, it["V"], it["F"]) for it in items]
    man = dict(man)
    man["attribution"] = ((man.get("attribution") or "").rstrip() + " " + ATTR259_Z).strip()
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
    ap = argparse.ArgumentParser(); ap.add_argument("key", choices=list(DIRS)); ap.add_argument("--out", default="build/q259_pre")
    a = ap.parse_args()
    if a.key in ("own_m", "own_f"):
        items, diff = build_own(a.key, a.out)
    else:
        items, diff = build_z(a.key, a.out)
    print(a.key, "shipped", len(items), "unlisted:", diff.get("unlisted") or diff.get("unlisted_changes"))
