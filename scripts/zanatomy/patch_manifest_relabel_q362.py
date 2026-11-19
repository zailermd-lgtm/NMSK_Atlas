#!/usr/bin/env python3
"""Q362: display-name corrections from data/anatomy/relabels_q362.json applied to a built Base page's embedded manifest (at regen,
after patch_manifest_cards_q354.py; precedent patch_manifest_records_q327.py / patch_manifest_nerves_q350.py).

Per entry: the mesh's name and its record's name become `name`; the record gets `latin`, `source_label` (the Z-Anatomy label, shown on
the card through `notes`), `notes` = the page's one-sentence reason + the book facts, and `source` = the book citation. Id and geometry
unchanged. Idempotent (a record that already carries the entry's notes is left as is); only the manifest literal is rewritten.

    python3 scripts/zanatomy/patch_manifest_relabel_q362.py <page_dir>... [--check]"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data/anatomy/relabels_q362.json"
LIT = re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M)
KEY = {"viewer_zan_atlas": "base_m", "viewer_base_female": "base_f"}


def ser(man):
    return json.dumps(man, separators=(",", ":")).replace("</", "<\\/")


def patch_manifest(man, key, entries):
    n = 0
    for m in man["meshes"]:
        e = entries.get(m["id"])
        if not e or key not in e["reason"]:
            continue
        rec = dict(m.get("rec") or {})
        notes = e["reason"][key] + " " + e["facts"]
        new = dict(rec, name=e["name"], latin=e["latin"], source_label=e["source_label"], notes=notes, source=e["source"])
        if m["name"] != e["name"] or rec != new:
            m["name"] = e["name"]; m["rec"] = new; n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    entries = {e["id"]: e for e in json.loads(DATA.read_text(encoding="utf-8"))["entries"]}
    bad = 0
    for d in map(Path, a.dirs):
        key = KEY.get(d.name)
        if not key:
            continue
        for p in [x for x in (*d.glob("atlas_viewer_*.html"), d / "index.html") if x.exists() and not x.name.endswith(".html.q362")]:
            t = p.read_text(encoding="utf-8")
            mm = LIT.search(t)
            if not mm:
                continue
            man = json.loads(mm.group(1))
            n = patch_manifest(man, key, entries)
            if a.check:
                bad += n; print(f"{p}: {n} to relabel"); continue
            if n:
                p.write_text(LIT.sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + ser(man) + ";", t, count=1), encoding="utf-8")
            print(f"{p}: relabelled {n}")
    return 1 if (a.check and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
