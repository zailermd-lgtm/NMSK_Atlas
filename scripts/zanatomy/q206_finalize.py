#!/usr/bin/env python3
"""Q206: scope check of a Q206 page against the Q205 page: every geometry-changed structure must be listed in the carry dump; writes data/derived/Q206_ship_diff_<which>.json
python3 scripts/zanatomy/q206_finalize.py male|female [DUMP]"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pack as PK  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
from scripts.zanatomy import q206_state as ST  # noqa: E402


def main(argv):
    which = argv[0]
    cfg = ST.CFG[which]
    dump = argv[1] if len(argv) > 1 else str(REPO / "build" / "q206" / f"{which}_state.npz")
    v, notes, cats, rep = PK.load_dumps([dump])
    r = SD.diff(cfg["page"], cfg["out"], cfg["stem"], sorted(v))
    r["listed_structures"] = len(v)
    (REPO / "data" / "derived" / f"Q206_ship_diff_{which}.json").write_text(json.dumps(r, indent=1))
    print({k: (len(x) if hasattr(x, "__len__") else x) for k, x in r.items()})


if __name__ == "__main__":
    main(sys.argv[1:])
