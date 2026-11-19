#!/usr/bin/env python3
"""Q206: pack the structures a q206_carry dump moved into the Q205 page (published Q205 geometry copied byte for byte for everything else), badges extended with the Q206 before -> after numbers;
the female page dir gets the clinical_* files copied unchanged.   python3 scripts/zanatomy/q206_pack.py male|female [DUMP]"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pack as PK  # noqa: E402
from scripts.zanatomy import q206_state as ST  # noqa: E402


def pack(which, dump=None, out=None):
    cfg = ST.CFG[which]
    dump = dump or REPO / "build" / "q206" / f"{which}_state.npz"
    old = dict(PK.PAGES[which])
    PK.PAGES[which] = dict(old, src=cfg["page"], out=Path(out or cfg["out"]))
    try:
        by, _, _ = ST.load(which)
        man2, blob2, replace, meta, rep = PK.pack(which, [str(dump)], str(PK.PAGES[which]["out"]), state_by=by)
    finally:
        PK.PAGES[which] = old
    o = Path(out or cfg["out"])
    if which == "female":
        for f in cfg["page"].glob("clinical_*"):
            shutil.copy2(f, o / f.name)
    return man2, replace, meta, rep


if __name__ == "__main__":
    w = sys.argv[1]
    man2, replace, meta, rep = pack(w, sys.argv[2] if len(sys.argv) > 2 else None)
    print("page written", ST.CFG[w]["out"], "| replaced", len(replace), "| card repairs", len(meta))
