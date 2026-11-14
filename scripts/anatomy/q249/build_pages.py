#!/usr/bin/env python3
"""Q249: add the rule-based nerves to the pre-pages (in-process patch of the latest page dirs, every other structure byte for byte; ship diff 0 unlisted).
    python3 scripts/anatomy/q249/build_pages.py KEY [--out build/q249_pre] [--tpl DIR]        KEY = own_m own_f comb_m comb_f base_m base_f
Z pages: scripts/zanatomy/q205_pages.save_page (add=[(entry, V, F)]); own pages: Bundle.add on the Q248 pre-bundle (build/q248_pre/bundle_<key>) + scripts/build_viewer_html.py.
Sources: Q249_SRC_<key> (page dir) or the defaults of run_rule.SRC; own bundles Q249_BUNDLE_<key> or build/q248_pre/bundle_<key>."""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy")); sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
import collect249 as CO  # noqa: E402
SRC = {"own_m": "build/q248/viewer_m_hr", "own_f": "build/q248/viewer_f_hr", "comb_m": "build/q248/viewer_zan_vhm", "base_m": "build/q248/viewer_zan_atlas",
       "base_f": "build/q250/viewer_base_female", "comb_f": "build/q250/viewer_zan_female"}
DIRS = {k: Path(v).name for k, v in SRC.items()}
STEM = {"own_m": "atlas_viewer_male", "own_f": "atlas_viewer_female", "base_m": "atlas_viewer_zan_atlas", "base_f": "atlas_viewer_base_female", "comb_m": "atlas_viewer_zan_male_fitted", "comb_f": "atlas_viewer_zan_female"}
OWN_BUNDLE = {"own_f": "build/q248_pre/bundle_own_f", "own_m": "build/q248_pre/bundle_own_m"}
TITLE = {"own_f": "NMSK Atlas Viewer (VH female)", "own_m": "NMSK Atlas Viewer (VH male)"}
ATTR = ("Rule-based nerves of this atlas (Q249): round tubes along splines through documented waypoints defined on this page's bones and neighbouring structures; courses from Gray's Anatomy 1918 (public domain), calibres and positional "
        "variability from the cited PubMed-indexed dissection / imaging papers (each nerve card lists them); not segmented, not dissected, not Z-Anatomy geometry.")


def sidemap(s):
    return {"l": "left", "r": "right", "m": None}.get(s, None)


def page_src(key):
    return os.environ.get("Q249_SRC_" + key) or SRC[key]


def diff_own(src, out, new_ids, Bcls, keyed):
    A0 = Bcls(REPO / src); N = Bcls(out)
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
    if sorted(added) != sorted(new_ids):
        unlisted += sorted(set(added) ^ set(new_ids))
    return dict(source=src, new=str(Path(out).resolve().relative_to(REPO)), entries_old=len(A0.items), entries_new=len(N.items), identical=ident, removed=[], added=added, added_expected=sorted(new_ids), card_only=[],
                unlisted_changes=unlisted, problems=bad, triangles_old=A0.j["triangles"], triangles_new=N.j["triangles"])


def build_own(key, out_root, tpl):
    from scripts.transfer.q200_bundle import Bundle
    from scripts.transfer.q234_own_f import keyed
    items = CO.collect(key)
    bsrc = os.environ.get("Q249_BUNDLE_" + key) or OWN_BUNDLE[key]
    B = Bundle(REPO / bsrc)
    for it in items:
        B.add(it["id"], it["cat"], sidemap(it["side"]), it["subject"], it["rec"], it["V"], it["F"])
    attr = {s: ATTR for s in {i["subject"] for i in items}}
    bdir = REPO / out_root / f"bundle_{key}"
    B.write(bdir, new_subject_attribution=attr, copy_clinical=True)
    d = REPO / out_root / DIRS[key]; d.mkdir(parents=True, exist_ok=True)
    html = Path(page_src(key)).name
    stem = STEM[key] + ".html"
    cmd = [sys.executable, str(REPO / "scripts/build_viewer_html.py"), "--bundle", str(bdir), "-o", str(d / stem), "--external-bin"] + (["--template", str(Path(tpl) / "atlas_viewer.template.html")] if tpl else [])
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO); print((r.stdout or "").strip().splitlines()[-1:] or r.stderr[-300:])
    if r.returncode:
        raise SystemExit(r.stderr[-800:])
    p = d / stem
    txt = p.read_text(encoding="utf-8"); txt = txt.replace("<title>NMSK Atlas Viewer</title>", f"<title>{TITLE[key]}</title>"); p.write_text(txt, encoding="utf-8")
    src_page = REPO / page_src(key)
    for f in list(src_page.glob("clinical_*")) + [src_page / "parts_data.json", src_page / "symmetry_q237.json"]:
        if f.exists(): shutil.copy2(f, d / f.name)
    diff = diff_own(bsrc, bdir, [i["id"] for i in items], Bundle, keyed)
    return items, diff


def build_z(key, out_root):
    from scripts.zanatomy import q205_pages as P5
    from scripts.zanatomy import q205_shipdiff as SD
    stem = STEM[key]
    src = REPO / page_src(key); out = REPO / out_root / DIRS[key]
    man, blob = P5.load_page(src, stem)
    items = CO.collect(key)
    add = []
    for it in items:
        ent = {"name": it["name"], "id": it["id"], "side": it["side"], "sys": "nerve", "rec": it["rec"]}
        add.append((ent, it["V"], it["F"]))
    man = dict(man)
    man["attribution"] = ((man.get("attribution") or "").rstrip() + " " + ATTR).strip()
    P5.save_page(out, stem, man, blob, add=add)
    for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json"]:
        if f.exists(): shutil.copy2(f, out / f.name)
    r = SD.diff(src, out, stem, [])
    listed = sorted(e["id"] for e, _, _ in add)
    diff = dict(source=str(src.relative_to(REPO)), new=str(out.relative_to(REPO)), added=r["added"], added_expected=listed, removed=r["removed"], geometry_changed=sorted(r["geometry_changed"]), card_only=sorted(r["card_only"]),
                unchanged=r["unchanged"], unlisted=sorted(set(r["added"]) ^ set(listed)) + sorted(r["card_only"]) + sorted(r["geometry_changed"]) + sorted(r["removed"]))
    return items, diff


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("key", choices=list(SRC)); ap.add_argument("--out", default="build/q249_pre"); ap.add_argument("--tpl")
    a = ap.parse_args()
    if a.key.startswith("own"):
        items, diff = build_own(a.key, a.out, a.tpl)
        bad = diff["unlisted_changes"] or diff["problems"]
    else:
        items, diff = build_z(a.key, a.out)
        bad = diff["unlisted"]
    (REPO / f"data/derived/Q249_vertex_diff_{a.key}.json").write_text(json.dumps(diff, indent=1) + "\n")
    (REPO / f"data/derived/Q249_shipped_{a.key}.json").write_text(json.dumps({i["id"]: dict(name=i["name"], side=i["side"], vertices=int(len(i["V"])), triangles=int(len(i["F"])), length_mm=i["report"]["length_mm"], volume_cm3=i["report"]["volume_cm3"]) for i in items}, indent=1) + "\n")
    print(a.key, "added", len(items), "unlisted", bad)
    sys.exit(1 if bad else 0)
