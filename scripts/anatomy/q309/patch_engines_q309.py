#!/usr/bin/env python3
"""Q309: the three edits per engine that only the engine can own, plus its own wiring.

Owner (translated from Hebrew): "Also allow display by SYSTEMS with an on/off button, and by LAYERS -- for the
whole body, per system, and for the displayed systems only."

Everything shareable is in `viewer/q309/` and goes into both templates through `scripts/sync_q309.py`. What cannot
be shared is the VETO ITSELF: each engine decides what it draws in its own way, so each needs one set of its own and
one line in its own visibility predicate. Three exact, idempotent, anchored edits on the Z template and two on the
own one, plus the per-engine wiring spliced from `glue_zan.js` / `glue_own.js` between `/* Q309 glue begin/end */`
so a later run re-syncs it in place.

Why a SET OF ITS OWN rather than reusing what is there:
  * the per-layer `on` table is written by the tissue rows, by `preset()` and by Q301's whole-body peel -- a fourth
    writer would fight all three, and Q301's own compatibility table already calls two of them incompatible;
  * `hidden` / `hideOverride` is the structure card's own hide, counted by Q300 as "hidden: N" with its own exit --
    a system switched off would be indistinguishable from a structure the user hid by hand, and clearing one would
    clear the other.
  So Q309 adds `q309Off`, read only in `vis()` / `apply()`, written only through the module's single `off(ids)`.

    python3 scripts/anatomy/q309/patch_engines_q309.py            # apply
    python3 scripts/anatomy/q309/patch_engines_q309.py --check    # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ZAN = REPO / "viewer" / "zan_atlas.template.html"
OWN = REPO / "viewer" / "atlas_viewer.template.html"
HERE = Path(__file__).resolve().parent

_C = ["/* Q309: the systems switched off and the scoped depth peel, as ONE veto set of structure ids. Kept apart",
      "   from the per-layer `on` table (the tissue rows, the presets and Q301's whole-body peel write that) and",
      "   from `hidden` (the card's own hide, which Q300 counts and exits separately). */"]
QZ = "".join("    " + ln + "\n" for ln in _C)
QO = "".join(ln + "\n" for ln in _C)

ZAN_EDITS = [
    (
        "    var hidden = new Set(), faded = new Set(), soloLayer = null;",
        "    var hidden = new Set(), faded = new Set(), soloLayer = null;\n" + QZ + "    var q309Off = new Set();",
    ),
    (
        "      if (hidden.has(o)) return false;",
        "      if (hidden.has(o)) return false;\n"
        "      if (q309Off.size && q309Off.has(o.id || o.name)) return false;      /* Q309: this system is switched off, or this layer of it is peeled away */",
    ),
    (
        "      if (window.NMSKFat) NMSKFat.set(false); else on.fat=false;      // Q301: plain fat is off by default, and a reset goes to the default",
        "      if (window.NMSKFat) NMSKFat.set(false); else on.fat=false;      // Q301: plain fat is off by default, and a reset goes to the default\n"
        "      if (window.NMSKQ309 && window.NMSKSysToggle) { NMSKSysToggle.put(\"\"); if (window.NMSKSysPeel) NMSKSysPeel.put(\"body||0\"); }   /* Q309: this engine's own reset also puts every system and every peeled layer back */",
    ),
]

OWN_EDITS = [
    (
        "var hideOverride = {}, fadeOverride = {};",
        "var hideOverride = {}, fadeOverride = {};\n" + QO + "var q309Off = {};",
    ),
    (
        "    if (hideOverride[s.id]) vis = false;",
        "    if (hideOverride[s.id]) vis = false;\n"
        "    if (q309Off[s.id]) vis = false;              /* Q309: this system is switched off, or this layer of it is peeled away */",
    ),
]

GLUE_BEGIN, GLUE_END = "/* Q309 glue begin */", "/* Q309 glue end */"
ANCHOR = "/* Q303 glue end */"


def splice_glue(path: Path, glue_file: Path, indent: int, check: bool) -> int:
    t = path.read_text(encoding="utf-8")
    body = glue_file.read_text(encoding="utf-8").rstrip("\n")
    pad = " " * indent
    block = f"{pad}{GLUE_BEGIN}\n{body}\n{pad}{GLUE_END}\n"
    if t.count(GLUE_BEGIN) == 1 and t.count(GLUE_END) == 1:
        i = t.rindex("\n", 0, t.index(GLUE_BEGIN)) + 1
        j = t.index(GLUE_END) + len(GLUE_END) + 1
        new = t[:i] + block + t[j:]
    else:
        if t.count(ANCHOR) != 1:
            raise SystemExit(f"{path.name}: glue anchor occurs {t.count(ANCHOR)} times, expected 1")
        k = t.index(ANCHOR) + len(ANCHOR) + 1
        new = t[:k] + block + t[k:]
    if new == t:
        print(f"glue up to date: {path.relative_to(REPO)}")
        return 0
    if check:
        print(f"glue out of date: {path.relative_to(REPO)}")
        return 1
    path.write_text(new, encoding="utf-8")
    print(f"glue spliced: {path.relative_to(REPO)} ({len(body)} bytes)")
    return 0


def apply(path: Path, edits, check: bool) -> int:
    t0 = t = path.read_text(encoding="utf-8")
    todo = []
    for old, new in edits:
        if new in t:
            continue                                   # already applied (idempotent)
        n = t.count(old)
        if n != 1:
            raise SystemExit(f"{path.name}: anchor occurs {n} times, expected 1:\n  {old.splitlines()[0][:110]}")
        t = t.replace(old, new)
        todo.append(old.splitlines()[0].strip()[:80])
    if t == t0:
        print(f"up to date: {path.relative_to(REPO)}")
        return 0
    if check:
        print(f"out of date: {path.relative_to(REPO)} ({len(todo)} edits pending)")
        for d in todo:
            print("    " + d)
        return 1
    path.write_text(t, encoding="utf-8")
    print(f"patched {path.relative_to(REPO)} ({len(todo)} edits)")
    return 0


def main() -> int:
    check = "--check" in sys.argv
    bad = 0
    bad |= apply(ZAN, ZAN_EDITS, check)
    bad |= apply(OWN, OWN_EDITS, check)
    bad |= splice_glue(ZAN, HERE / "glue_zan.js", 6, check)
    bad |= splice_glue(OWN, HERE / "glue_own.js", 2, check)
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
