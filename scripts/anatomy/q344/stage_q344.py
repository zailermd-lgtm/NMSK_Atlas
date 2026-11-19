#!/usr/bin/env python3
"""Q344: put the round's shared blocks and template patch into a BUILT page (a copy under /dev/shm), the same text the syncs and
patch_ui_q344.py write into the template, so the verifier can run before a regen.

    python3 scripts/anatomy/q344/stage_q344.py /dev/shm/q344/zan_atlas"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
MODS = ["sync_parts_ui_q220", "sync_q294", "sync_q298", "sync_q301", "sync_q305", "sync_pose_q241", "sync_q344"]


def load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main() -> int:
    d = Path(sys.argv[1])
    def mk(n):
        r = load(n).render
        return (lambda t: r(t, "zan")) if n == "sync_pose_q241" else r
    renders = [mk(n) for n in MODS]
    import patch_ui_q344 as P
    for f in sorted(d.glob("*.html")):
        if f.name.endswith(".html") and not (f.name == "index.html" or f.name.startswith("atlas_viewer")):
            continue
        t = f.read_text(encoding="utf-8")
        for r in renders:
            t = r(t)
        t, bad = P.patch(t)
        if bad:
            print("patch anchors missing:", bad); return 2
        f.write_text(t, encoding="utf-8"); print("staged", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
