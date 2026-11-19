#!/usr/bin/env python3
"""Q241: keep the Pose fragment (viewer/pose/) and its small engine hooks in both viewer templates.

viewer/pose/pose.{css,html,js} is the shared single source (same pattern as scripts/sync_symview_q237.py / sync_parts_ui_q220.py); viewer/pose/glue_{own,zan}.js is the per-engine adaptor. Each template
carries them verbatim between `POSE <kind> begin` / `POSE <kind> end` marker lines, placed right after the SYMVIEW pair. The per-page rig table sits in an `NMSK-POSE-RIG begin/end` block next to
the abbreviation table and is filled by scripts/anatomy/q241/make_pose_rig.py --inject. The few engine-hook lines (Z engine only: the vertex offset of a structure in its batch buffer, the cut-cap /
label geometry hook) are inserted idempotently at fixed anchors, so the script can be re-run on a template another change touched (it fails loudly when an anchor is gone):

    python3 scripts/sync_pose_q241.py                  # rewrite both templates in viewer/
    python3 scripts/sync_pose_q241.py --check          # exit 1 if a template is out of date
    python3 scripts/sync_pose_q241.py --dir DIR        # operate on DIR/{atlas_viewer,zan_atlas}.template.html (private template copies for a build)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FR = REPO / "viewer" / "pose"
MARK = {"css": ("/* POSE css begin */", "/* POSE css end */"), "html": ("<!-- POSE html begin -->", "<!-- POSE html end -->"),
        "js": ("/* POSE js begin */", "/* POSE js end */"), "glue": ("/* POSE glue begin */", "/* POSE glue end */")}
ANCHORS = {      # the pair is inserted BEFORE the anchor (after the SYMVIEW pair)
    "own": {"css": "/* PARTS-UI css begin */", "html": "    <!-- PARTS-UI html begin -->", "js": "/* PARTS-UI js begin */", "glue": "window.__selState = function(){ return selCtl.state(); };"},
    "zan": {"css": "  /* PARTS-UI css begin */", "html": "<!-- PARTS-UI html begin -->", "js": "/* PARTS-UI js begin */", "glue": "    window.__selState = function(){ return selCtl.state(); };"},
}
RIG_BEGIN, RIG_END = "<!-- NMSK-POSE-RIG begin -->", "<!-- NMSK-POSE-RIG end -->"
RIG_BLOCK = RIG_BEGIN + '<script type="application/json" id="nmsk-pose-rig">{}</script>' + RIG_END
EDITS = {
    "own": [],
    "zan": [
        ("        var base = cur.vU;\n        cur.pc.push(o.pos); cur.nc.push(o.nrm);",
         "        var base = cur.vU; o.vOff = base;      // Q241 pose: vertex offset of the structure in its batch buffer\n        cur.pc.push(o.pos); cur.nc.push(o.nrm);"),
        ("    function capGeom(i, o){\n      var g = capGeomCache[i]; if (g) return g;",
         "    function capGeom(i, o){\n      var pl = window.__poseLive && window.__poseLive(i);      // Q241: the posed vertices once the structure has been moved\n"
         "      if (pl){ var rc = MAN.meshes[i]; return {pos:pl, idx:new Uint16Array(BIN.buffer, BIN.byteOffset + rc.io, rc.ic * 3), bmin:o.bmin, bmax:o.bmax}; }\n      var g = capGeomCache[i]; if (g) return g;"),
    ],
}


def frag(kind):
    return {"css": FR / "pose.css", "html": FR / "pose.html", "js": FR / "pose.js"}.get(kind)


def render(text: str, eng: str) -> str:
    glue = (FR / ("glue_%s.js" % eng)).read_text(encoding="utf-8").rstrip("\n")
    for kind, anchor in ANCHORS[eng].items():
        b, e = MARK[kind]
        if b in text:
            if text.count(b) != 1 or text.count(e) != 1:
                raise SystemExit("marker pair for %s must occur exactly once" % kind)
            continue
        if text.count(anchor) != 1:
            raise SystemExit("%s: anchor for the %s marker pair must occur exactly once: %r (found %d)" % (eng, kind, anchor, text.count(anchor)))
        ind = re.match(r"\s*", anchor).group(0) if kind in ("css", "glue") else ""
        text = text.replace(anchor, "%s%s\n%s%s\n%s" % (ind, b, ind, e, anchor), 1)
    if RIG_BEGIN not in text:
        a = "<!-- NMSK-ABBREV begin -->"
        if text.count(a) != 1:
            raise SystemExit("%s: the NMSK-ABBREV block must occur exactly once (found %d)" % (eng, text.count(a)))
        i = text.index(a); ls = text.rfind("\n", 0, i) + 1; ind = re.match(r"\s*", text[ls:i]).group(0)
        text = text[:i] + RIG_BLOCK + "\n" + ind + text[i:]
    for old, new in EDITS[eng]:
        if new in text:
            continue
        if text.count(old) != 1:
            raise SystemExit("%s: engine-hook anchor must occur exactly once (found %d): %r" % (eng, text.count(old), old[:90]))
        text = text.replace(old, new, 1)
    for kind, (b, e) in MARK.items():
        body = glue if kind == "glue" else frag(kind).read_text(encoding="utf-8").rstrip("\n")
        i, j = text.index(b) + len(b), text.index(e)
        text = text[:i] + "\n" + body + "\n" + text[j:]
    return text


def main() -> int:
    check = "--check" in sys.argv
    d = REPO / "viewer"
    if "--dir" in sys.argv:
        d = Path(sys.argv[sys.argv.index("--dir") + 1])
    bad = 0
    for eng, name in (("own", "atlas_viewer.template.html"), ("zan", "zan_atlas.template.html")):
        t = d / name
        old = t.read_text(encoding="utf-8")
        new = render(old, eng)
        if new != old:
            if check:
                print("out of date:", t); bad = 1
            else:
                if t.read_text(encoding="utf-8") != old:            # re-read right before writing (other agents edit these templates)
                    print(t.name, "changed while syncing; run again"); return 2
                t.write_text(new, encoding="utf-8"); print("synced", t)
        else:
            print("up to date:", t)
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
