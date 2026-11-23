#!/usr/bin/env python3
"""Q391: the Z engine's half of the gentle, muscle-by-muscle hide.

Owner (translated from Hebrew, 2026-11-22): "... Also allow gently hiding muscle by muscle."

`viewer/q309/mushide.js` decides WHICH muscle goes and WHEN; only the engine can draw one structure at an opacity
of its own for the ~250 ms it takes to fade. So this adds, on the Z template only:
  * `q391Fade` -- a Map id -> opacity factor in (0, 1), written only through the Q309 adaptor's `fade(map)`;
  * the four scene predicates (solid, Q364 own-opacity, faded, selection looks) leave a fading structure out, and
    one translucent pass per distinct factor draws it at factor x its layer's opacity;
  * the engine's own reset also empties the muscle-by-muscle list.
When the fade ends the module moves the structure into Q309's veto set, so vis(), the cut, the labels, the pose and
picking see an ordinary hidden structure. The own engine gets nothing: its adaptor has no `fade`, and the module then
hides at once (that engine's pages are frozen; nothing is done for its sake).
Exact, anchored, idempotent edits, like scripts/anatomy/q309/patch_engines_q309.py.

    python3 scripts/anatomy/q391/patch_engines_q391.py            # apply
    python3 scripts/anatomy/q391/patch_engines_q391.py --check    # exit 1 if the template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ZAN = REPO / "viewer" / "zan_atlas.template.html"

NOT_FADING = " && (!q391Fade.size || q391F(e) === undefined)"
EDITS = [
    (
        "    var q309Off = new Set();\n",
        "    var q309Off = new Set();\n"
        "    /* Q391: the gentle hide -- a structure fading out (or back in) is drawn at its own opacity factor for ~250 ms;\n"
        "       written only through the Q309 adaptor's fade(map), read only by the scene pass. */\n"
        "    var q391Fade = new Map();\n"
        "    function q391F(e){ return q391Fade.get(e.id || e.name); }\n",
    ),
    (
        '      function solid0(e){ return vis(e) && !faded.has(e) && selLook(e) === ""; }',
        '      function solid0(e){ return vis(e) && !faded.has(e) && selLook(e) === ""' + NOT_FADING + "; }",
    ),
    (
        "      function isFaded(e){ return vis(e) && faded.has(e); }",
        "      function isFaded(e){ return vis(e) && faded.has(e)" + NOT_FADING + "; }",
    ),
    (
        "      function selIs(k){ return function(e){ return vis(e) && !faded.has(e) && selLook(e) === k; }; }",
        "      function selIs(k){ return function(e){ return vis(e) && !faded.has(e) && selLook(e) === k" + NOT_FADING + "; }; }",
    ),
    (
        "      /* Q300: the bone once more, over the soft tissue.",
        "      if (q391Fade.size){      /* Q391: a muscle fading out or back in, one translucent pass per distinct factor */\n"
        "        var q391V = []; q391Fade.forEach(function(v){ if (q391V.indexOf(v) < 0) q391V.push(v); });\n"
        "        BATCHES.forEach(function(B){\n"
        "          if (!on[B.layer] || (soloLayer && B.layer !== soloLayer)) return;\n"
        "          q391V.forEach(function(v){ paint(B, Math.max(0.004, v * layerAlpha(B.layer)), function(e){ return vis(e) && q391F(e) === v; }); });\n"
        "        });\n"
        "      }\n"
        "      /* Q300: the bone once more, over the soft tissue.",
    ),
    (
        'NMSKSysPeel.put("body||0"); }   /* Q309: this engine\'s own reset also puts every system and every peeled layer back */',
        'NMSKSysPeel.put("body||0"); }   /* Q309: this engine\'s own reset also puts every system and every peeled layer back */\n'
        '      if (window.NMSKMusHide && NMSKMusHide.put) NMSKMusHide.put("");   /* Q391: and every muscle hidden one by one */',
    ),
]


def main() -> int:
    check = "--check" in sys.argv
    t0 = t = ZAN.read_text(encoding="utf-8")
    todo = []
    for old, new in EDITS:
        if new in t:
            continue
        n = t.count(old)
        if n != 1:
            raise SystemExit(f"{ZAN.name}: anchor occurs {n} times, expected 1:\n  {old.splitlines()[0][:110]}")
        t = t.replace(old, new)
        todo.append(old.strip().splitlines()[0][:80])
    if t == t0:
        print(f"up to date: {ZAN.relative_to(REPO)}")
        return 0
    if check:
        print(f"out of date: {ZAN.relative_to(REPO)} ({len(todo)} edits pending)")
        for d in todo:
            print("    " + d)
        return 1
    ZAN.write_text(t, encoding="utf-8")
    print(f"patched {ZAN.relative_to(REPO)} ({len(todo)} edits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
