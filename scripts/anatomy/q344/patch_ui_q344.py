#!/usr/bin/env python3
"""Q344: the template-only edits of the UI round, as exact string replacements (idempotent).

    python3 scripts/anatomy/q344/patch_ui_q344.py            # patch viewer/zan_atlas.template.html (take /tmp/nmsk_sync.lock first)
    python3 scripts/anatomy/q344/patch_ui_q344.py --check    # exit 1 if a file still needs a patch
    python3 scripts/anatomy/q344/patch_ui_q344.py FILE...    # patch built pages (used by stage_q344.py)

What it changes: the structure card prints human names (NMSKHuman, viewer/parts_ui) instead of ids, file names and round numbers;
the search list marks the side when two rows share a name and gives every row its full name as a tooltip."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "viewer" / "zan_atlas.template.html"

PAIRS = [
    # --- the structure card: plain wording ---
    ("if(a.origin) h+='<dt>Origin</dt><dd>'+esc(a.origin)+'</dd>';",
     "if(a.origin) h+='<dt>Origin</dt><dd>'+esc(NMSKHuman.line(a.origin))+'</dd>';"),
    ("if(a.insertion) h+='<dt>Insertion</dt><dd>'+esc(a.insertion)+'</dd>';",
     "if(a.insertion) h+='<dt>Insertion</dt><dd>'+esc(NMSKHuman.line(a.insertion))+'</dd>';"),
    ("if(a.nerve&&a.nerve.length) h+='<dt>Nerve</dt><dd>'+esc(a.nerve.join(\", \").replace(/_/g,\" \"))+'</dd>';",
     "if(a.nerve&&a.nerve.length) h+='<dt>Nerve</dt><dd>'+esc(a.nerve.map(NMSKHuman.nerve).join(\", \"))+'</dd>';"),
    ("if(a.source) h+='<dt>Source</dt><dd>'+esc(a.source)+'</dd>';",
     "if(a.source) h+='<dt>Source</dt><dd>'+esc(NMSKHuman.text(a.source))+'</dd>';"),
    ("if(c.function) h+='<p class=\"sub2\">'+esc(c.function)+'</p>';",
     "if(c.function) h+='<p class=\"sub2\">'+esc(NMSKHuman.text(c.function))+'</p>';"),
    ("h+='<dl class=\"facts\"><dt>Targets</dt><dd>'+esc(a.targets.join(\", \"))+'</dd></dl>';",
     "h+='<dl class=\"facts\"><dt>Targets</dt><dd>'+esc(NMSKHuman.list(a.targets).join(\", \"))+'</dd></dl>';"),
    ("h+='<dl class=\"facts\"><dt>Supplies</dt><dd>'+esc(a.supplies.join(\", \"))+'</dd></dl>';",
     "h+='<dl class=\"facts\"><dt>Supplies</dt><dd>'+esc(NMSKHuman.list(a.supplies).join(\", \"))+'</dd></dl>';"),
    ("if(a.notes) h+='<p class=\"sub2\">'+esc(a.notes)+'</p>';",
     "if(a.notes) h+='<p class=\"sub2\">'+esc(NMSKHuman.text(a.notes))+'</p>';"),
    ("if(a.procedural_badge) h+='<div class=\"warn\">'+esc(a.procedural_badge)+'</div>';",
     "if(a.procedural_badge) h+=NMSKHuman.badgeHtml(a.procedural_badge, esc, \"warn\");      // Q344: one plain line, the method behind an (i)"),
    ("h+='<div class=\"ok-note\">'+(a.geom_src?'Geometry: '+esc(a.geom_src)+'; ':'Geometry from Z-Anatomy (CC BY-SA 4.0); ')+",
     "h+='<div class=\"ok-note\">'+(a.geom_src?'Geometry: '+esc(NMSKHuman.text(a.geom_src))+'; ':'Geometry from Z-Anatomy (CC BY-SA 4.0); ')+"),
    # the learn card prints the data folder as its source
    ("esc(m.s || \"data/muscles\")", "esc(NMSKHuman.text(m.s || \"this atlas's muscle records\"))"),
    # --- the search list ---
    ("      listEl.innerHTML=\"\";\n      items.forEach(function(o){\n        var b=document.createElement(\"button\");\n        b.className=\"item\"",
     "      listEl.innerHTML=\"\";\n      var nameN={}; items.forEach(function(o){ nameN[o.name]=(nameN[o.name]||0)+1; });      // Q344: rows that share a name get the structure's side\n      items.forEach(function(o){\n        var b=document.createElement(\"button\");\n        b.className=\"item\""),
    ("'<span class=\"badge-x\" style=\"opacity:.65\">part of</span>':'<span class=\"badge-x\">atlas</span>');",
     "'<span class=\"badge-x\" style=\"opacity:.8\" title=\"Its own mesh; this project keeps it as part of a coarser entity\">part of</span>':'');   /* Q355: the plain \"atlas\" tag said nothing (every row has one); only \"part of\" informs */"),
    ("<span class=\"t\">'+\n          o.name+(q8?NMSKQ298.whySuffix(o.id):\"\")+'</span>'+badge;",
     "<span class=\"t\">'+\n          o.name+((nameN[o.name]>1&&(o.side===\"r\"||o.side===\"l\"))?' <span class=\"side-lr\" title=\"'+(o.side===\"r\"?\"right\":\"left\")+' side\">'+(o.side===\"r\"?\"R\":\"L\")+'</span>':\"\")+(q8?NMSKQ298.whySuffix(o.id):\"\")+'</span>'+badge;\n        b.title=o.name+(o.side===\"r\"?\" (right)\":o.side===\"l\"?\" (left)\":\"\");"),
]


def patch(text: str):
    out, bad = text, []
    for old, new in PAIRS:
        if new in out:
            continue
        if out.count(old) == 1:
            out = out.replace(old, new)
        else:
            bad.append(old[:70])
    return out, bad


def main() -> int:
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv
    files = [Path(a) for a in argv] or [TEMPLATE]
    rc = 0
    for f in files:
        old = f.read_text(encoding="utf-8")
        new, bad = patch(old)
        if bad:
            print(f"cannot patch {f}: anchor missing or ambiguous: {bad}"); rc = 2; continue
        if new != old:
            if check:
                print(f"needs patch: {f}"); rc = max(rc, 1)
            else:
                f.write_text(new, encoding="utf-8"); print(f"patched {f}")
        else:
            print(f"up to date: {f}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
