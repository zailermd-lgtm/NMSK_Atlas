#!/usr/bin/env python3
"""Q321: the engine wiring of the quick card, as three exact string replacements (idempotent).

    python3 scripts/anatomy/q321/patch_q321.py            # patch viewer/zan_atlas.template.html
    python3 scripts/anatomy/q321/patch_q321.py FILE...    # patch built pages (used by verify_quickcard_q321.py)

The shared module is spliced separately (scripts/sync_quickcard_q321.py)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

CLICK_OLD = "select(hz,false); if(!hz&&pzTap(e)) pzReset(); }"
CLICK_NEW = "select(hz,false); if(window.NMSKQuick) NMSKQuick.open(hz?hz.id:null,e.clientX,e.clientY); if(!hz&&pzTap(e)) pzReset(); }   /* Q321: every pick no tool consumed opens the quick card, an empty click closes it */"

SEL_OLD = "    function select(o,focus){\n      selected=o;\n"
SEL_NEW = "    function select(o,focus){\n      selected=o;\n      if(window.NMSKQuick) NMSKQuick.sync(o?o.id:null);      // Q321: the quick card follows the selection\n"

GLUE_AFTER = "    window.__selState = function(){ return selCtl.state(); };\n"
GLUE = """    /* Q321 quick card glue begin */
    if (window.NMSKQuickCard) window.NMSKQuick = NMSKQuickCard.start({
      canvas:canvas,
      canvasRect:function(){ return canvas.getBoundingClientRect(); },
      info:function(id){ var o = objsById[id] && objsById[id][0]; if (!o) return null;
        return {name:o.name, sub:o.layer + " \\u00b7 " + (o.side === "r" ? "right" : o.side === "l" ? "left" : "midline")}; },
      state:function(id){ var o = objsById[id] && objsById[id][0]; return o ? {hidden:hidden.has(o), faded:faded.has(o)} : {}; },
      toggleHide:function(id){ var o = objsById[id] && objsById[id][0]; if (!o) return;
        if (hidden.has(o)) hidden.delete(o); else { hidden.add(o); faded.delete(o); }
        if (selected === o) select(o, false); renderList(); need = true; },
      toggleFade:function(id){ var o = objsById[id] && objsById[id][0]; if (!o) return;
        if (faded.has(o)) faded.delete(o); else { faded.add(o); hidden.delete(o); }
        if (selected === o) select(o, false); need = true; },
      zoom:function(id){ var o = objsById[id] && objsById[id][0]; if (o) select(o, true); },
      more:function(id){ var o = objsById[id] && objsById[id][0]; if (!o) return; infoMin = false; select(o, false); },
      screenBox:function(){
        if (!lastMVP) return null;
        var r = canvas.getBoundingClientRect(), sx = r.width / W, sy = r.height / H, l = 1e9, t = 1e9, rr = -1e9, b = -1e9;
        OBJ.forEach(function(o){
          if (!vis(o)) return;
          var mn = o.bmin, mx = o.bmax;
          for (var i = 0; i < 8; i++){
            var p = proj([i & 1 ? mx[0] : mn[0], i & 2 ? mx[1] : mn[1], i & 4 ? mx[2] : mn[2]]); if (!p) continue;
            var x = r.left + p.x * sx, y = r.top + p.y * sy;
            if (x < l) l = x; if (x > rr) rr = x; if (y < t) t = y; if (y > b) b = y;
          }
        });
        return l < rr ? {l:l, t:t, r:rr, b:b} : null;
      },
      obstacles:function(){ return ["brand", "topright", "rail", "foot", "cut-panel", "needle-panel", "pm-card", "info"].map(function(id){ return document.getElementById(id); }); }
    });
    /* Q321 quick card glue end */
"""


def apply(t: str) -> str:
    if "Q321 quick card glue begin" in t:
        return t
    for old, new in ((CLICK_OLD, CLICK_NEW), (SEL_OLD, SEL_NEW), (GLUE_AFTER, GLUE_AFTER + GLUE)):
        if t.count(old) != 1:
            raise SystemExit("Q321 anchor not found exactly once: " + old[:50])
        t = t.replace(old, new, 1)
    return t


if __name__ == "__main__":
    files = [Path(a) for a in sys.argv[1:]] or [REPO / "viewer" / "zan_atlas.template.html"]
    for f in files:
        s = f.read_text(encoding="utf-8"); n = apply(s)
        if n != s:
            f.write_text(n, encoding="utf-8"); print("patched", f)
        else:
            print("up to date", f)
