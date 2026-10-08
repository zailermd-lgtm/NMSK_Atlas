#!/usr/bin/env python3
"""Q205: pack the moved structures of a state dump (q205_male.py / q205_female.py) into the published Q202 page: shipped meshes through the builder's own decimation, card badges extended,
card names / atlas facts repaired against the clean base page; everything else byte for byte.  Writes a ship diff (changed / unchanged / unlisted).

    python3 scripts/zanatomy/q205_pack.py male|female DUMP [DUMP ...] [--out DIR] [--no-skin-weld]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P  # noqa: E402
from scripts.zanatomy import q205_ship as Sh  # noqa: E402

PAGES = {
    "male": dict(src=REPO / "build" / "q202" / "viewer_zan_vhm", stem="atlas_viewer_zan_male_fitted", base=(REPO / "build" / "q197" / "viewer_zan_atlas", "atlas_viewer_zan_atlas"), out=REPO / "build" / "q205" / "viewer_zan_vhm"),
    "female": dict(src=REPO / "build" / "q202" / "viewer_zan_female", stem="atlas_viewer_zan_female", base=(REPO / "build" / "q202" / "viewer_base_female", "atlas_viewer_base_female"), out=REPO / "build" / "q205" / "viewer_zan_female"),
}


def load_dumps(paths):
    ids, notes, v, cats, rep = [], {}, {}, {}, {}
    for p in paths:
        z = np.load(p, allow_pickle=False)
        ii = json.loads(str(z["ids"]))
        nn = json.loads(str(z["notes"]))
        for k, i in enumerate(ii):
            v[i] = z[f"v{k}"]
            notes[i] = nn.get(i, "")
        rep[Path(p).name] = json.loads(str(z["report"]))
        if "cats" in z.files:
            cats.update(json.loads(str(z["cats"])))
    return v, notes, cats, rep


def pack(which, dumps, out=None, state_by=None, extra_replace=None, log=print):
    cfg = PAGES[which]
    out = Path(out or cfg["out"])
    man, blob = P.load_page(cfg["src"], cfg["stem"])
    bman, _ = P.load_page(*cfg["base"])
    E = {m["id"]: m for m in man["meshes"]}
    meta = P.card_repairs(man, bman)
    v, notes, cats, rep = load_dumps(dumps)
    replace = {}
    for i, vv in v.items():
        if i not in E:
            log(f"  not on the page: {i}")
            continue
        f = state_by[i]["f"] if state_by else None
        cat = state_by[i]["cat"] if state_by else cats[i]
        dv, df = Sh.ship_mesh(vv, f, i, cat)
        rec = dict(meta[i][1] if i in meta and meta[i][1] is not None else (E[i].get("rec") or {}))
        base_badge = (E[i].get("rec") or {}).get("procedural_badge") or ""
        if notes.get(i):
            rec["procedural_badge"] = (base_badge + " " + notes[i].strip()).strip() if notes[i].strip() not in base_badge else base_badge
        elif base_badge:
            rec["procedural_badge"] = base_badge
        replace[i] = (dv, df, rec if rec else None)
    for i, (vv, ff, rec) in (extra_replace or {}).items():
        replace[i] = (vv, ff, rec)
    man2, blob2 = P.save_page(out, cfg["stem"], man, blob, replace=replace, meta=meta)
    return man2, blob2, replace, meta, rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("which", choices=["male", "female"])
    ap.add_argument("dumps", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    from scripts.zanatomy import q205_male as M
    by, _ = M.load_all(str(REPO / "build" / "q201" / "after_q201.npz")) if a.which == "male" else (None, None)
    man2, blob2, replace, meta, rep = pack(a.which, a.dumps, a.out, state_by=by)
    print("page written:", a.out or PAGES[a.which]["out"], "| replaced", len(replace), "| card repairs", len(meta))


if __name__ == "__main__":
    main()
