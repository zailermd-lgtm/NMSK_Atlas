#!/usr/bin/env python3
"""Q368: the name card's colour swatch and ADD menu, measured in a real Chromium on a Base (Z-engine) page.

    python3 scripts/anatomy/q368/verify_card_q368.py <page dir> [--size WxH ...] [--shots DIR]

Default sizes 1400x900 and 390x844. The page dir is used as built (a regenerated copy); nothing is patched.
Checks: the swatch shows the colour the engine draws (unmarked / marked / user colour); a palette choice recolours that
structure only and Undo / Redo restore it; ADD -> functional group adds exactly the group's members to what is marked;
ADD -> antagonist group for biceps brachii adds the elbow extensors the antagonist table names; ADD -> adjacent adds the
adjacency list (all, or one); a bone's rows are disabled with a reason; on a phone the name row keeps its height and no
menu leaves the screen. Prints OK / FAIL lines and Q368_CARD_OK / Q368_CARD_FAIL.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q319"))
import verify_search_q319 as V            # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ERRS = V.ERRS
check = V.check
ANT = json.loads((REPO / "data/anatomy/antagonist_groups_q368.json").read_text(encoding="utf-8"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


Q321 = _load("vq321", REPO / "scripts/anatomy/q321/verify_quickcard_q321.py")
MUS = "biceps_brachii_l"


def ev(pg, js, arg=None):
    return pg.evaluate(js, arg) if arg is not None else pg.evaluate(js)


def marks(pg):
    return set(ev(pg, "() => NMSKSelectCtl.state().marks"))


def open_card(pg, i):
    ev(pg, "(i) => NMSKQuick.open(i, null, null)", i)
    pg.wait_for_timeout(250)


def sw(pg):
    return ev(pg, "() => NMSKQuick.swatch()")


def in_screen(pg, sel):
    return ev(pg, """(s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect();
      return {l: r.left, r: r.right, t: r.top, b: r.bottom, vw: innerWidth, vh: innerHeight,
              ok: r.left >= 0 && r.right <= innerWidth + 0.5 && r.top >= 0 && r.bottom <= innerHeight + 0.5,
              hscroll: e.scrollWidth > e.clientWidth + 1}; }""", sel)


def head_geom(pg):
    """the name row with the two buttons, and the same row with them taken out (display:none): heights must match"""
    return ev(pg, """() => { const c = document.querySelector('.qc'), h = c.querySelector('.qc-head'), a = c.querySelector('.qc-acts');
      const s = c.querySelector('.qc-sw'), d = c.querySelector('.qc-addb'), n = c.querySelector('.qc-name');
      const rs = s.getBoundingClientRect(), rd = d.getBoundingClientRect(), rh = h.getBoundingClientRect(), rn = n.getBoundingClientRect();
      const with_ = rh.height, cw = c.getBoundingClientRect();
      a.style.display = 'none'; const without = h.getBoundingClientRect().height, cardNo = c.getBoundingClientRect().height; a.style.display = '';
      return {with: with_, without, cardWith: cw.height, cardWithout: cardNo, cardR: cw.right, vw: innerWidth,
              sw: [rs.width, rs.height], add: [rd.width, rd.height], sameRow: rs.top >= rh.top - 2.5 && rs.bottom <= rh.bottom + 2.5 && rd.top >= rh.top - 2.5 && rd.bottom <= rh.bottom + 2.5,
              besideName: rs.left >= rn.right - 1 && rs.left - rn.right < 40}; }""")


def shot(pg, path):
    if path:
        pg.screenshot(path=str(path))


def find_bone(pg):
    return ev(pg, """() => { const ms = (window.__ANATOMY_MANIFEST__ || {}).meshes || [];
      for (const m of ms){ if (!/humerus|femur|radius|tibia/.test(m.id) || !/_l$/.test(m.id)) continue;
        NMSKQuick.open(m.id, null, null); const s = document.querySelector('.qc-sub'); if (s && /^bone/i.test(s.textContent)) return m.id; }
      return null; }""")


def item_key(pg, menu, key):
    return f'{menu} .qc-rmi[data-key="{key}"]'


def run_size(pl, d: Path, w: int, h: int, tag: str, shots: Path | None):
    print(f"--- {tag} {w}x{h}")
    srv, b, pg = V.open_page(pl, d, w, h)
    T = f"[{tag} {w}]"
    sp = (lambda n: shots / f"q368_{tag}_{w}_{n}.png") if shots else (lambda n: None)
    try:
        Q321.wait_ready(pg)
        pg.wait_for_function("() => NMSKQ298.groups && NMSKQ298.groups('biceps_brachii_l') && NMSKQ298.adjacent('biceps_brachii_l')", timeout=60000)
        ev(pg, "() => { NMSKSelectCtl.clear(); NMSKSelectCtl.setUserColour(null, 'ids', ['biceps_brachii_l','biceps_brachii_r']); }")
        # ---- 1. the swatch: unmarked, marked, user colour
        open_card(pg, MUS)
        s0 = sw(pg)
        check(f"{T} swatch shown for an unmarked muscle: {s0}", bool(s0) and s0["src"] == "own" and re.match(r"#[0-9a-f]{6}$", s0["hex"] or "") is not None)
        g = head_geom(pg)
        check(f"{T} swatch {g['sw']} and ADD {g['add']} are >= 32 px touch targets on the name row, beside the name",
              min(g["sw"] + g["add"]) >= 32 and g["sameRow"] and g["besideName"])
        check(f"{T} the name row keeps its height with the two buttons ({g['with']:.0f} vs {g['without']:.0f} px; card {g['cardWith']:.0f} vs {g['cardWithout']:.0f})",
              g["with"] <= g["without"] + 0.5 and g["cardWith"] <= g["cardWithout"] + 0.5)
        check(f"{T} card within the screen (right {g['cardR']:.0f} <= {g['vw']})", g["cardR"] <= g["vw"] + 0.5)
        # a long name: the two buttons take ~80 px of the name row; on a phone such a name may need one more line, never more
        open_card(pg, "flexor_digitorum_superficialis_l")
        gl = head_geom(pg)
        check(f"{T} long name: the name row grows by at most one text line ({gl['with']:.0f} vs {gl['without']:.0f} px), buttons stay on it",
              gl["with"] <= gl["without"] + 17 and gl["sameRow"] and gl["cardR"] <= gl["vw"] + 0.5)
        open_card(pg, MUS)
        pg.click('.qc [data-qc="sel"]'); pg.wait_for_timeout(250)
        s1 = sw(pg)
        check(f"{T} marked: swatch shows the mark colour {s1} (own was {s0['hex']})", bool(s1) and s1["src"] == "mark" and s1["hex"] != s0["hex"])
        # ---- 2. the palette: one structure only, undo / redo
        pg.click('.qc .qc-sw'); pg.wait_for_timeout(250)
        ps = in_screen(pg, "#qc-palmenu")
        n_sw = ev(pg, "() => document.querySelectorAll('#qc-palmenu .qc-pc').length")
        pal = ev(pg, "() => NMSKSelectCtl.palette().length")
        check(f"{T} palette opens with the colour control's {pal} colours + other + own colour ({n_sw} chips), inside the screen {ps}",
              ps is not None and ps["ok"] and n_sw == pal and ev(pg, "() => !!document.querySelector('#qc-palmenu .qc-pown') && !!document.querySelector('#qc-palmenu input[type=color]')"))
        shot(pg, sp("palette"))
        pg.click('#qc-palmenu .qc-pc[data-hex="#3f7fd6"]'); pg.wait_for_timeout(300)
        s2 = sw(pg)
        user = ev(pg, "() => NMSKSelectCtl.colourState().user")
        check(f"{T} choosing Blue recolours the swatch at once {s2} and only this structure {user}",
              bool(s2) and s2["hex"] == "#3f7fd6" and s2["src"] == "user" and user == {MUS: "#3f7fd6"})
        open_card(pg, "biceps_brachii_r")
        st = sw(pg)
        check(f"{T} the twin keeps its colour {st}", bool(st) and st["hex"] != "#3f7fd6")
        open_card(pg, MUS)
        ev(pg, "() => NMSKHistory.undo()"); pg.wait_for_timeout(400)
        s3 = sw(pg)
        check(f"{T} Undo restores the colour {s3} == {s1['hex']}", bool(s3) and s3["hex"] == s1["hex"] and s3["src"] == "mark")
        ev(pg, "() => NMSKHistory.redo()"); pg.wait_for_timeout(400)
        s4 = sw(pg)
        check(f"{T} Redo puts it back {s4}", bool(s4) and s4["hex"] == "#3f7fd6")
        pg.click('.qc .qc-sw'); pg.wait_for_timeout(200); pg.click('#qc-palmenu .qc-pown'); pg.wait_for_timeout(300)
        s5 = sw(pg)
        check(f"{T} 'Own colour' resets it {s5}", bool(s5) and s5["src"] == "mark" and ev(pg, "() => Object.keys(NMSKSelectCtl.colourState().user).length") == 0)
        pg.keyboard.press("Escape")
        # ---- 3. ADD -> functional group: adds exactly the members, keeps earlier marks
        ev(pg, "() => NMSKSelectCtl.clear()")
        ev(pg, "() => NMSKSelectCtl.markIds(['sartorius_l'], true, false, true)")
        open_card(pg, MUS)
        before = marks(pg)
        pg.click('.qc .qc-addb'); pg.wait_for_timeout(300)
        am = in_screen(pg, "#qc-addmenu")
        items = ev(pg, "() => NMSKQuick.addItems()")
        keys = [i["key"] for i in items]
        check(f"{T} ADD menu opens inside the screen {am} with {keys}", am is not None and am["ok"] and not am["hscroll"] and keys == ["grp", "ant", "adj"])
        shot(pg, sp("add"))
        grp = ev(pg, "() => NMSKQ298.groups('biceps_brachii_l').map(g => ({id: g.id, ids: g.ids}))")
        gsel = next((x for x in grp if x["id"] == "act_elbow_flex_p"), None)
        check(f"{T} biceps brachii is in {len(grp)} functional groups, among them elbow flexion", gsel is not None)
        pg.click(item_key(pg, "#qc-addmenu", "grp")); pg.wait_for_timeout(250)
        shot(pg, sp("add_groups"))
        # click and read the button in one go: its "+n marked" shows for 2.6 s, a loaded machine can take longer between calls
        lbl = ev(pg, "(s) => { document.querySelector(s).click(); return document.querySelector('.qc .qc-addb').textContent; }",
                 item_key(pg, "#qc-addmenu", "act_elbow_flex_p"))
        pg.wait_for_timeout(400)
        after = marks(pg)
        la = ev(pg, "() => NMSKQuick.lastAdd()")
        exp = before | set(gsel["ids"] if gsel else [])
        check(f"{T} functional group added exactly its {len(gsel['ids']) if gsel else 0} members, earlier marks kept ({len(before)} -> {len(after)}); button says '{lbl}'",
              after == exp and "sartorius_l" in after and la and la["n"] == len(exp - before) and lbl == f"+{la['n']} marked")
        ev(pg, "() => NMSKHistory.undo()"); pg.wait_for_timeout(400)
        check(f"{T} one Undo takes the whole add back ({len(marks(pg))} marked)", marks(pg) == before)
        # ---- 4. ADD -> antagonist group (biceps brachii -> elbow extensors named in the table)
        named = {p["b"] if p["a"] == "act_elbow_flex_p" else p["a"] for p in ANT["pairs"] if "act_elbow_flex_p" in (p["a"], p["b"])}
        check(f"{T} the table opposes elbow flexion with {sorted(named)}", named == {"act_elbow_flex_n"})
        ext = set(ev(pg, "() => NMSKQ298.group('act_elbow_flex_n').ids"))
        pg.click('.qc .qc-addb'); pg.wait_for_timeout(250)
        pg.click(item_key(pg, "#qc-addmenu", "ant")); pg.wait_for_timeout(250)
        shot(pg, sp("add_antagonists"))
        pg.click(item_key(pg, "#qc-addmenu", "act_elbow_flex_n")); pg.wait_for_timeout(400)
        a2 = marks(pg)
        check(f"{T} antagonist group added the elbow extensors {sorted(ext)}", a2 == before | ext and any("triceps" in x for x in ext) and any("anconeus" in x for x in ext))
        ev(pg, "() => NMSKHistory.undo()"); pg.wait_for_timeout(400)
        # ---- 5. ADD -> adjacent: all, then one
        adj = set(ev(pg, "() => NMSKQ298.adjacent('biceps_brachii_l')"))
        pg.click('.qc .qc-addb'); pg.wait_for_timeout(250)
        pg.click(item_key(pg, "#qc-addmenu", "adj")); pg.wait_for_timeout(250)
        nrows = ev(pg, "() => document.querySelectorAll('#qc-addmenu .qc-rsi').length")
        am2 = in_screen(pg, "#qc-addmenu")
        check(f"{T} adjacent sheet: All + {nrows - 1} single rows for {len(adj)} adjacent, inside the screen", nrows == len(adj) + 1 and am2 and am2["ok"])
        shot(pg, sp("add_adjacent"))
        pg.click(item_key(pg, "#qc-addmenu", "adj-all")); pg.wait_for_timeout(400)
        check(f"{T} 'All' adjacent added the adjacency list ({len(adj)})", marks(pg) == before | adj)
        ev(pg, "() => NMSKHistory.undo()"); pg.wait_for_timeout(400)
        one = sorted(adj - before)[0]
        pg.click('.qc .qc-addb'); pg.wait_for_timeout(250)
        pg.click(item_key(pg, "#qc-addmenu", "adj")); pg.wait_for_timeout(250)
        pg.click(item_key(pg, "#qc-addmenu", one)); pg.wait_for_timeout(400)
        check(f"{T} a single adjacent row adds just that one ({one})", marks(pg) == before | {one})
        # ---- 6. a bone: disabled rows with a reason
        bone = find_bone(pg)
        if bone:
            open_card(pg, bone)
            bi = ev(pg, "() => NMSKQuick.addItems()")
            off = {i["key"]: i for i in bi}
            check(f"{T} bone {bone}: functional / antagonist rows disabled with a reason ({off['grp']['why']!r})",
                  off["grp"]["off"] and off["ant"]["off"] and "bone" in (off["grp"]["why"] or "").lower() and bool(off["ant"]["why"]))
            pg.click('.qc .qc-addb'); pg.wait_for_timeout(250)
            ev(pg, "() => document.querySelector('#qc-addmenu .qc-rmi[data-key=\"grp\"]').click()"); pg.wait_for_timeout(200)
            check(f"{T} a tap on a disabled row shows its reason", ev(pg, "() => !!document.querySelector('#qc-addmenu .qc-rwhy')"))
            pg.keyboard.press("Escape")
        else:
            check(f"{T} a bone found on the page", False)
        # ---- 7. keyboard: the swatch and ADD open from Enter and close with Escape
        open_card(pg, MUS)
        pg.focus('.qc .qc-addb'); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
        k1 = ev(pg, "() => !!NMSKQuick.addMenu() && document.activeElement && document.activeElement.classList.contains('qc-rmi')")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
        k2 = ev(pg, "() => !NMSKQuick.addMenu() && document.activeElement && document.activeElement.classList.contains('qc-addb')")
        check(f"{T} keyboard: Enter opens ADD with focus in it ({k1}), Escape closes it back to the button ({k2})", k1 and k2)
        ev(pg, "() => NMSKSelectCtl.clear()")
    finally:
        try:
            b.close()
        finally:
            srv.terminate()


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sizes = [(1400, 900), (390, 844)]
    shots = None
    if "--shots" in sys.argv:
        shots = Path(sys.argv[sys.argv.index("--shots") + 1]); shots.mkdir(parents=True, exist_ok=True)
        args = [a for a in args if a != str(shots)]
    if "--size" in sys.argv:
        sizes = [tuple(int(v) for v in a.split("x")) for a in sys.argv[sys.argv.index("--size") + 1:] if re.match(r"\d+x\d+$", a)]
        args = [a for a in args if not re.match(r"\d+x\d+$", a)]
    src = Path(args[0])
    with sync_playwright() as pl:
        for w, h in sizes:
            run_size(pl, src, w, h, src.name, shots)
    print("Q368_CARD_FAIL" if ERRS else "Q368_CARD_OK")
    for e in ERRS:
        print("   ", e)
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
