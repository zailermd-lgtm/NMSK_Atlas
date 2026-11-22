#!/usr/bin/env python3
"""Q248: add the new ligaments to the pre-pages (in-process patch of the Q244 page dirs, every other structure byte for byte; ship diff 0 unlisted).
    python3 scripts/anatomy/q248/build_pages.py KEY [--src build/q244] [--out build/q248_pre] [--tpl DIR]        KEY = own_m own_f comb_m comb_f base_m base_f
Z pages: scripts/zanatomy/q205_pages.save_page (add=[(entry, V, F)]); own pages: Bundle.add of the source bundle (build/viewer_{f,m}_hr_q243 / _q237) + scripts/build_viewer_html.py."""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
import lig_pages as PG, collect as CO  # noqa: E402

OWN_BUNDLE = {"own_f": "build/viewer_f_hr_q243", "own_m": "build/viewer_m_hr_q237"}
HTML = {"own_f": "atlas_viewer_female.html", "own_m": "atlas_viewer_male.html"}
TITLE = {"own_f": "NMSK Atlas Viewer (VH female)", "own_m": "NMSK Atlas Viewer (VH male)"}
ATTR_CVH = ("Chinese Visible Human female (Wu et al. 2015, PLoS ONE 10(8):e0132226, S3 Fig, CC BY 4.0): anococcygeal ligament registered onto this page's pelvis by this atlas (Q248; Q235 bone registration); derived data, "
            "CC BY 4.0 attribution kept (third_party/cvh_wu2015/NOTICE.md).")
ATTR_ZAN = "Z-Anatomy (CC BY-SA 4.0): ligament / capsule / retinaculum shapes carried onto this body's bones by Q248 (carrier-bone fits); derived data, CC BY-SA 4.0 attribution kept."
ATTR_RULE = "Rule-based ligaments of this atlas (Q248): bands built from this page's bone / organ geometry; attachment descriptions cited on each card (Terminologia Anatomica, Gray's Anatomy 1918 public domain, PubMed-indexed papers)."


def sidemap(s):
    return {"l": "left", "r": "right", "m": None}.get(s, None)


def diff_own(src, out, new_ids, B0cls, Bcls, keyed):
    A0 = B0cls(REPO / src); N = Bcls(out)
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


def build_own(key, src_root, out_root, tpl):
    from scripts.transfer.q200_bundle import Bundle
    from scripts.transfer.q234_own_f import keyed
    items = CO.collect(key)
    bsrc = OWN_BUNDLE[key]
    B = Bundle(REPO / bsrc)
    for it in items:
        B.add(it["id"], it["cat"], sidemap(it["side"]), it["subject"], it["rec"], it["V"], it["F"])
    attr = {}
    subs = {i["subject"] for i in items}
    for s in subs:
        attr[s] = ATTR_CVH if "cvh" in s else ATTR_ZAN if "xfer_zan" in s else ATTR_RULE
    bdir = REPO / out_root / f"bundle_{key}"
    n_bytes = B.write(bdir, new_subject_attribution=attr, copy_clinical=True)
    d = REPO / out_root / PG.DIRS[key]
    d.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(REPO / "scripts/build_viewer_html.py"), "--bundle", str(bdir), "-o", str(d / HTML[key]), "--external-bin"] + (["--template", str(Path(tpl) / "atlas_viewer.template.html")] if tpl else [])
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO); print((r.stdout or "").strip().splitlines()[-1:] or r.stderr[-300:])
    if r.returncode:
        raise SystemExit(r.stderr[-800:])
    p = d / HTML[key]
    txt = p.read_text(encoding="utf-8"); txt = txt.replace("<title>NMSK Atlas Viewer</title>", f"<title>{TITLE[key]}</title>"); p.write_text(txt, encoding="utf-8")
    src_page = REPO / src_root / PG.DIRS[key]
    for f in list(src_page.glob("clinical_*")) + [src_page / "parts_data.json", src_page / "symmetry_q237.json"]:
        if f.exists(): shutil.copy2(f, d / f.name)
    diff = diff_own(bsrc, bdir, [i["id"] for i in items], Bundle, Bundle, keyed)
    return items, diff


def build_z(key, src_root, out_root):
    from scripts.zanatomy import q205_pages as P5
    from scripts.zanatomy import q205_shipdiff as SD
    stem = PG.STEM[key]
    src = REPO / src_root / PG.DIRS[key]; out = REPO / out_root / PG.DIRS[key]
    man, blob = P5.load_page(src, stem)
    items = CO.collect(key)
    add = []
    for it in items:
        ent = {"name": it["name"], "id": it["id"], "side": it["side"], "sys": it["z_sys"] if it["cat"] != "cartilage" else "cartilage", "rec": it["rec"]}
        add.append((ent, it["V"], it["F"]))
    man = dict(man)
    kinds = {i["kind"] for i in items}
    extra = (ATTR_RULE if "rule" in kinds else "") + (" " + ATTR_CVH if "cvh" in kinds else "")
    man["attribution"] = ((man.get("attribution") or "").rstrip() + " " + extra).strip()
    P5.save_page(out, stem, man, blob, add=add)
    for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json"]:
        if f.exists(): shutil.copy2(f, out / f.name)
    r = SD.diff(src, out, stem, [])
    listed = sorted(e["id"] for e, _, _ in add)
    diff = dict(source=str(src.relative_to(REPO)), new=str(out.relative_to(REPO)), added=r["added"], added_expected=listed, removed=r["removed"], geometry_changed=sorted(r["geometry_changed"]), card_only=sorted(r["card_only"]),
                unchanged=r["unchanged"], unlisted=sorted(set(r["added"]) ^ set(listed)) + sorted(r["card_only"]) + sorted(r["geometry_changed"]) + sorted(r["removed"]))
    return items, diff


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("key", choices=list(PG.DIRS)); ap.add_argument("--src", default="build/q244"); ap.add_argument("--out", default="build/q248_pre"); ap.add_argument("--tpl")
    a = ap.parse_args()
    if a.key.startswith("own"):
        items, diff = build_own(a.key, a.src, a.out, a.tpl)
        bad = diff["unlisted_changes"] or diff["problems"]
    else:
        items, diff = build_z(a.key, a.src, a.out)
        bad = diff["unlisted"]
    (REPO / f"data/derived/Q248_vertex_diff_{a.key}.json").write_text(json.dumps(diff, indent=1) + "\n")
    (REPO / f"data/derived/Q248_shipped_{a.key}.json").write_text(json.dumps({i["id"]: dict(kind=i["kind"], name=i["name"], side=i["side"], vertices=int(len(i["V"])), triangles=int(len(i["F"]))) for i in items}, indent=1) + "\n")
    print(a.key, "added", len(items), "unlisted", bad)
    sys.exit(1 if bad else 0)
