#!/usr/bin/env python3
"""Q323: engine glue of the attachments view (the "insertions" preset) in the Z-engine template.

The shared part lives in viewer/parts_ui/ (synced by scripts/sync_parts_ui_q220.py). This adds the two engine-only lines:
  1. preset(): the "insert" preset turns the attachments view on, every other preset turns it off;
  2. the NMSKParts adaptor's structs(): this body's structures by layer, with "has origin/insertion wording", for the per-class counts.
The own-engine template has no insertions preset and needs no glue (structs() is optional).

    flock /tmp/nmsk_sync.lock python3 scripts/anatomy/q323/patch_q323.py          # patch viewer/zan_atlas.template.html
    python3 scripts/anatomy/q323/patch_q323.py --check                            # exit 1 if not patched
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "viewer" / "zan_atlas.template.html"

EDITS = [
    ('      LK.forEach(function(k){ on[k]=true; setA(k, map[k]!==undefined?map[k]:0); });\n      sync(); need=true;\n    }\n',
     '      LK.forEach(function(k){ on[k]=true; setA(k, map[k]!==undefined?map[k]:0); });\n'
     '      if(partsCtl && partsCtl.attach) partsCtl.attach(name==="insert");      // Q323: the insertions preset is the attachments view (origins + insertions)\n'
     '      sync(); need=true;\n    }\n'),
    ('      setDots:function(list){ partDotList=list; },\n',
     '      setDots:function(list){ partDotList=list; },\n'
     '      structs:function(){ return OBJ.map(function(o){ var a=o.atlas; return {n:o.name, l:o.layer, t:!!(a&&(a.origin||a.insertion))}; }); },      // Q323: per-class counts of the attachments view\n'),
]


def apply(text: str) -> str:
    for old, new in EDITS:
        if new in text:
            continue
        if text.count(old) != 1:
            raise SystemExit("Q323 patch anchor not found exactly once: " + old.strip()[:80])
        text = text.replace(old, new, 1)
    return text


def main() -> int:
    t = TEMPLATE.read_text(encoding="utf-8")
    n = apply(t)
    if "--check" in sys.argv:
        print("up to date" if n == t else "not patched"); return 0 if n == t else 1
    if n != t:
        TEMPLATE.write_text(n, encoding="utf-8"); print("patched", TEMPLATE.relative_to(REPO))
    else:
        print("already patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
