#!/usr/bin/env python3
"""Q205: scope check of a finished Q205 page against the published Q202 page: every structure whose geometry changed must be listed (a dump of the moved structures or a skin weld);
writes data/derived/Q205_ship_diff_<which>.json.   python3 scripts/zanatomy/q205_finalize.py male|female DUMP [DUMP ...]"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pack as PK  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402


def main(argv):
    which = argv[0]
    cfg = PK.PAGES[which]
    listed = set()
    for p in argv[1:]:
        v, notes, cats, rep = PK.load_dumps([p])
        listed |= set(v)
    sw = REPO / "data" / "derived" / f"Q205_skinweld_{which}.json"
    if sw.exists():
        listed |= set(json.loads(sw.read_text())["patches"])
    extra = REPO / "data" / "derived" / f"Q205_listed_extra_{which}.json"
    if extra.exists():
        listed |= set(json.loads(extra.read_text()))
    r = SD.diff(cfg["src"], cfg["out"], cfg["stem"], sorted(listed))
    r["listed_structures"] = len(listed)
    out = REPO / "data" / "derived" / f"Q205_ship_diff_{which}.json"
    out.write_text(json.dumps(r, indent=1))
    print({k: (len(v) if hasattr(v, "__len__") else v) for k, v in r.items()})


if __name__ == "__main__":
    main(sys.argv[1:])
