#!/usr/bin/env python3
"""Q327: apply the builder's record_class_clash rule (build_zan_atlas_viewer.py) to already-built Z pages.

A ligament / fascia no longer borrows a muscle's or a bone's atlas record as its "part of" parent. regen_template_only.py does not
re-run the builder, it re-reads the manifest embedded in each page, so the rule reaches the pages through this patch. For each
id below whose manifest entry still carries the borrowed record (rec.part_of_id == the old parent), the record is dropped exactly
as the builder emits a never-linked structure: no `rec` key (or `rec` = {procedural_badge} when the entry has a badge).
Idempotent; only the manifest literal is rewritten (same compact JSON, byte-identical elsewhere).

    python3 scripts/zanatomy/patch_manifest_records_q327.py <page_dir>... [--check]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KEY = "window.__ANATOMY_MANIFEST__="
SIDES = ("l", "r")
# stable id stem -> old parent atlas id stem (the id gets _l / _r)
CLASHES = {
    "zan_lateral_thyrohyoid_ligament": "thyrohyoid",
    "zan_stylohyoid_ligament": "stylohyoid",
    "zan_piriformis_fascia": "piriformis",
    "zan_ligament_of_head_of_femur": "femur",
    "zan_dorsal_fascia_of_hand": "hand",
    "zan_collateral_interphalangeal_ligaments_of_hand": "hand",   # Q338: plural "ligaments" slipped the rule
    "zan_lumbrical_muscles_of_hand": "hand",                       # Q338: a muscle under the hand bones' record
}
OLD_PARENT = {f"{k}_{s}": f"{v}_{s}" for k, v in CLASHES.items() for s in SIDES}


def patch_text(html: str) -> tuple[str, list[str]]:
    if html.count(KEY) != 1:
        return html, []
    i = html.index(KEY) + len(KEY)
    man, n = json.JSONDecoder().raw_decode(html[i:])
    changed = []
    for m in man["meshes"]:
        old = OLD_PARENT.get(m.get("id"))
        rec = m.get("rec")
        if not old or not rec or rec.get("part_of_id") != old:
            continue
        if rec.get("procedural_badge"):
            m["rec"] = {"procedural_badge": rec["procedural_badge"]}
        else:
            del m["rec"]
        changed.append(m["id"])
    if not changed:
        return html, []
    return html[:i] + json.dumps(man, separators=(",", ":"), ensure_ascii=True) + html[i + n:], changed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 if a patch is needed")
    a = ap.parse_args(argv)
    need = False
    for d in map(Path, a.dirs):
        pages = sorted(d.glob("atlas_viewer*.html")) + ([d / "index.html"] if (d / "index.html").exists() else [])
        if not pages:
            sys.exit(f"{d}: no page html")
        for f in pages:
            html = f.read_text(encoding="utf-8")
            new, ids = patch_text(html)
            if ids:
                need = True
                if not a.check:
                    f.write_text(new, encoding="utf-8")
            print(f"{f}: {'would patch' if a.check and ids else 'patched' if ids else 'ok'} {len(ids)}: {' '.join(ids)}")
    return 1 if (need and a.check) else 0


if __name__ == "__main__":
    sys.exit(main())
