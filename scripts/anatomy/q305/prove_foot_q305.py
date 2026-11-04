#!/usr/bin/env python3
"""Q305: the inherited `#foot` defect, measured before and after the one-line fix, on the real built pages.

THE DEFECT (Q301-era). Q301's **View** group adopts the Z engine's bottom pill row `#foot` into its sheet. Q301
styles an adopted member with `.qg-sbody .qg-adopted` -- two classes, specificity 0,0,2,0 -- which cannot beat the
engine's own `#foot{position:fixed}` -- one id, 0,1,0,0. So the adopted row stayed `fixed` at the bottom of the
viewport, out of the sheet's flow and on top of it, and painted over every member listed after it in that sheet.
`#q305-restore`, Q305's own "Restore layout" button, is one of those members.

THE INSTRUMENT is the one that found it, and the one that caught Q301's info drawer over Undo and Q300's chip bar
over Redo: `document.elementFromPoint` at the centre of the control. Before the fix it returns `DIV#foot`; after
it, the button itself.

THE FIX is one declaration, `.qg-sbody #foot{position:static}` (0,1,1,0, specific enough), and it lives in **Q305's
own** `viewer/q305/q305.css`, not in Q301's block -- so Q301's block comes out of the regen byte-identical, which is
this round's contract, and the defect still goes away. It is scoped to the sheet, so `#foot` where the page itself
puts it is untouched.

HOW BEFORE/AFTER IS PRODUCED. Both states are measured on the SAME built page, in one run: the fix's rule is found
in the page's own stylesheet by its selector text and `deleteRule`d for the "before" pass, then re-inserted at the
same index for the "after" pass. Deleting that one declaration restores exactly the pre-fix cascade, so the two
passes differ in nothing else -- no second build, no edited copy of the page.

THE PAGE IS PUT INTO THE STATE THE OWNER WORKS IN FIRST, with `verify_q305.py`'s own `quiet_chrome` and `stage`.
That is not a detail: the first run of this script skipped it, the Z pages' full-screen model switcher was still on
top, and `elementFromPoint` answered `DIV.mw-body` for every point on both engines -- the same overlay that cost
Q305's first smoke run twelve false "covered" failures.

WHAT IS CHECKED, per page and per viewport (desktop 1400x900, phone 390x844):
  1  with the sheet never opened, `#foot` is where the PAGE puts it -- `position:fixed`, visible, in the bottom-left
     band, and on the phone inside the `calc(3.3rem + safe-b)` band `#rail` reserves for it. That is Q270's band, and
     it is measured BEFORE the View group has ever adopted the row, because Q301 parks an adopted element in a hidden
     node when its sheet closes (by design: the group takes the row over, it does not borrow it -- which is also why
     this script does not look for the band again afterwards).
  2  the View group is opened and `#foot` is adopted into its sheet.
  3  before: at all four `scrollIntoView` alignments of `#q305-restore`, what is on top.
  4  after: the same four alignments -- every one must be the button itself, and `#foot` must cover no member of that
     sheet.
  5  the adopted row is in the sheet's flow: horizontally inside the sheet's box. Vertically it may be scrolled out
     of view, because the sheet's body scrolls -- which is exactly what the four alignments exercise.
  6  0 page errors.
The own engine (`viewer_m_hr`, `viewer_f_hr`) has NO `#foot` at all -- it is a Z-template element -- so there the run
asserts that, and that `#q305-restore` is reachable in both passes, i.e. the fix changes nothing there.

    python3 scripts/anatomy/q305/prove_foot_q305.py PAGE_DIR... [--json OUT]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283"))
sys.path.insert(0, str(HERE))
import verify_q283 as V  # noqa: E402
import verify_q305 as Q  # noqa: E402  (its ready / quiet_chrome / stage put the page into the owner's state)
from playwright.sync_api import sync_playwright  # noqa: E402

OKN = [0]
ALIGN = ("center", "start", "end", "nearest")
SEL = ".qg-sbody #foot"
REPORT: dict = {}


def check(label, cond, errs):
    if V.check(label, cond, errs):
        OKN[0] += 1
        return True
    return False


FIND = """() => {
  const out = [];
  for (let i = 0; i < document.styleSheets.length; i++) {
    let rs; try { rs = document.styleSheets[i].cssRules; } catch (e) { continue; }
    if (!rs) continue;
    for (let j = 0; j < rs.length; j++) {
      if (rs[j].selectorText === %r) out.push({sheet: i, index: j, text: rs[j].cssText});
    }
  }
  return out;
}""" % SEL

TOP = """(s) => {
  const e = document.querySelector(s);
  if (!e) return {missing: true};
  const r = e.getBoundingClientRect();
  if (!(r.width > 0 && r.height > 0)) return {zero: true};
  const h = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
  const tag = h ? (h.tagName + (h.id ? '#' + h.id : '.' + (h.className || '').toString().split(' ')[0])) : null;
  return {on_top: tag, self: !!(h && (h === e || e.contains(h) || h.contains(e))),
          pos: getComputedStyle(e).position,
          rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}};
}"""

HOME = """() => {
  const f = document.getElementById('foot'); if (!f) return null;
  const r = f.getBoundingClientRect(); const s = document.getElementById('q301-sheet');
  const rail = document.getElementById('rail');
  return {pos: getComputedStyle(f).position, z: getComputedStyle(f).zIndex,
          in_sheet: !!(s && s.contains(f)), vis: r.width > 8 && r.height > 8,
          rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
          from_bottom: Math.round(innerHeight - r.bottom), from_left: Math.round(r.left),
          rail_pad: rail ? getComputedStyle(rail).paddingBottom : null,
          vh: innerHeight, vw: innerWidth};
}"""


def scan(pg, sel):
    """what is on top of `sel` at each of the four alignments its scroller can be left in"""
    seen = []
    for how in ALIGN:
        pg.eval_on_selector(sel, "(e, b) => e.scrollIntoView({block: b})", how)
        pg.wait_for_timeout(260)
        seen.append({"align": how, **pg.evaluate(TOP, sel)})
    return seen


def run_page(pg, tag, errs, phone):
    Q.ready(pg)
    Q.quiet_chrome(pg)
    Q.stage(pg, phone)
    rules = pg.evaluate(FIND)
    check("%s the fix's rule is in the page exactly once" % tag, len(rules) == 1, errs)
    if len(rules) != 1:
        return
    rule = rules[0]
    has_foot = pg.evaluate("() => !!document.getElementById('foot')")
    print("    #foot on this page: %s ; fix rule at sheet %d index %d" % (has_foot, rule["sheet"], rule["index"]))

    # ---- 1. Q270's band, measured BEFORE the View group has ever adopted the row
    if has_foot:
        home = pg.evaluate(HOME)
        print("      #foot where the page puts it: %s" % home)
        check("%s Q270 band: #foot is position:fixed where the page puts it" % tag, home["pos"] == "fixed", errs)
        check("%s Q270 band: #foot is visible and not in the sheet" % tag, home["vis"] and not home["in_sheet"], errs)
        check("%s Q270 band: it sits in the bottom-left band (%d px up, %d px in)" % (tag, home["from_bottom"], home["from_left"]),
              0 <= home["from_bottom"] <= 70 and 0 <= home["from_left"] <= 40, errs)
        if phone:
            # Q270 reserves calc(3.3rem + safe-b) ~= 53 px under #rail's scroll area for this band
            check("%s Q270 band: on the phone it stays within the band #rail reserves (%s, band %d px)"
                  % (tag, home["rail_pad"], home["rect"]["h"] + home["from_bottom"]),
                  home["rect"]["h"] + home["from_bottom"] <= 80, errs)
        REPORT.setdefault(tag, {})["home_before"] = home
    else:
        check("%s this engine has no #foot at all, so Q270's band cannot be disturbed" % tag, True, errs)

    # ---- 2. the View group, where #foot is adopted and #q305-restore lives
    pg.evaluate("() => { if (window.NMSKGroups) NMSKGroups.open('view'); }")
    pg.wait_for_timeout(800)
    check("%s the View group's sheet is open" % tag,
          pg.evaluate("() => { const s = document.getElementById('q301-sheet'); return !!s && !s.hidden; }"), errs)
    check("%s #q305-restore is in that sheet" % tag,
          pg.evaluate("() => { const b = document.getElementById('q305-restore'); const s = document.getElementById('q301-sheet'); return !!b && !!s && s.contains(b); }"), errs)
    if has_foot:
        check("%s #foot is adopted into that sheet" % tag,
              pg.evaluate("() => { const f = document.getElementById('foot'); const s = document.getElementById('q301-sheet'); return !!f && !!s && s.contains(f) && f.classList.contains('qg-adopted'); }"), errs)

    # ---- 3. BEFORE: the fix's one declaration deleted, which is exactly the pre-fix cascade
    pg.evaluate("(r) => document.styleSheets[r.sheet].deleteRule(r.index)", rule)
    pg.wait_for_timeout(350)
    if has_foot:
        check("%s before: the adopted #foot is position:fixed" % tag,
              pg.evaluate("() => getComputedStyle(document.getElementById('foot')).position") == "fixed", errs)
    before = scan(pg, "#q305-restore")
    for s in before:
        print("      before  %-8s on top: %-22s self=%s" % (s["align"], s.get("on_top"), s.get("self")))
    covered = [s["align"] for s in before if s.get("on_top") == "DIV#foot"]
    # THE HONEST MEASURE is "is the button the thing under that point", not "is the thing under it the DIV". The row
    # is a flex box of pills, so at some alignments `elementFromPoint` answers one of #foot's OWN pills
    # (`BUTTON.pill`) rather than `DIV#foot` -- which is the same defect, one layer down: the row is still on top.
    unreachable = [(s["align"], s.get("on_top")) for s in before if not s.get("self")]
    if has_foot:
        # The defect is proven by the button being unreachable AT ALL: one alignment the user can leave the sheet in
        # is already one the button cannot be pressed from.
        check("%s before: Restore layout is NOT the element at its own centre at %d of the %d scroll alignments "
              "(DIV#foot itself at %d of them) %s"
              % (tag, len(unreachable), len(ALIGN), len(covered), unreachable),
              len(unreachable) >= 1, errs)
    else:
        check("%s before: nothing covers Restore layout (this engine has no #foot)" % tag,
              all(s.get("self") for s in before), errs)

    # ---- 4. AFTER: the declaration put back where it was
    pg.evaluate("(r) => document.styleSheets[r.sheet].insertRule(r.text, r.index)", rule)
    pg.wait_for_timeout(350)
    if has_foot:
        check("%s after: the adopted #foot is position:static" % tag,
              pg.evaluate("() => getComputedStyle(document.getElementById('foot')).position") == "static", errs)
    after = scan(pg, "#q305-restore")
    for s in after:
        print("      after   %-8s on top: %-22s self=%s" % (s["align"], s.get("on_top"), s.get("self")))
    check("%s after: Restore layout is on top at all four alignments" % tag,
          all(s.get("self") for s in after), errs)
    check("%s after: #foot is on top of Restore layout at no alignment" % tag,
          not [s for s in after if s.get("on_top") == "DIV#foot"], errs)

    # ---- the sheet's other members are reachable too, not just ours
    others = pg.evaluate("""() => {
      const s = document.getElementById('q301-sheet'); if (!s) return [];
      const out = [];
      const all = s.querySelectorAll('.qg-adopted, .qg-b, .q301-b, .nm-grip');
      for (let i = 0; i < all.length; i++) {
        const e = all[i]; if (e.id === 'foot') continue;
        const r = e.getBoundingClientRect(); if (!(r.width > 0 && r.height > 0)) continue;
        e.scrollIntoView({block: 'nearest'});
        const r2 = e.getBoundingClientRect();
        const h = document.elementFromPoint(r2.x + r2.width / 2, r2.y + r2.height / 2);
        if (h && h.id === 'foot') out.push(e.id || e.textContent.trim().slice(0, 18));
      }
      return out; }""")
    check("%s after: #foot covers no other member of the sheet %s" % (tag, others[:4]), not others, errs)

    # ---- 5. the adopted row is in the sheet's FLOW: horizontally inside its box
    if has_foot:
        box = pg.evaluate("""() => {
          const f = document.getElementById('foot').getBoundingClientRect();
          const s = document.getElementById('q301-sheet').getBoundingClientRect();
          return {f: {x: Math.round(f.x), y: Math.round(f.y), w: Math.round(f.width), h: Math.round(f.height)},
                  s: {x: Math.round(s.x), y: Math.round(s.y), w: Math.round(s.width), h: Math.round(s.height)},
                  inx: f.left >= s.left - 2 && f.right <= s.right + 2}; }""")
        print("      adopted #foot %s inside sheet %s" % (box["f"], box["s"]))
        check("%s after: the adopted #foot is horizontally inside the sheet's box" % tag, box["inx"], errs)

    lay = pg.evaluate("""() => ({ ow: document.documentElement.scrollWidth, vw: innerWidth,
        canvas: !!document.querySelector('canvas'), bar: !!document.getElementById('q301-bar') })""")
    check("%s the layout does not overflow the viewport width (%d <= %d)" % (tag, lay["ow"], lay["vw"]),
          lay["ow"] <= lay["vw"] + 1, errs)
    check("%s the model canvas and the control bar are both still there" % tag, lay["canvas"] and lay["bar"], errs)

    REPORT.setdefault(tag, {}).update({
        "has_foot": has_foot, "rule": rule["text"],
        "before": [{k: s.get(k) for k in ("align", "on_top", "self")} for s in before],
        "before_unreachable": unreachable, "before_div_foot_on_top": covered,
        "after": [{k: s.get(k) for k in ("align", "on_top", "self")} for s in after],
    })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--json")
    a = ap.parse_args()
    errs: list = []
    with sync_playwright() as p:
        for d in a.dirs:
            d = Path(d).resolve()
            key = d.name
            srv, port = V.serve(d)
            try:
                url = "http://127.0.0.1:%d/%s" % (port, V.html_of(d))
                for phone in (False, True):
                    w, h = (390, 844) if phone else (1400, 900)
                    br = p.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
                    ctx = br.new_context(viewport={"width": w, "height": h},
                                         device_scale_factor=2 if phone else 1,
                                         has_touch=phone, is_mobile=phone)
                    pg = ctx.new_page()
                    bad: list = []
                    pg.on("pageerror", lambda e: bad.append(str(e)))
                    pg.route("**/*", V.route)
                    print("  %s %dx%d" % (key, w, h))
                    pg.goto(url, wait_until="domcontentloaded", timeout=180000)
                    tag = "%s %d" % (key, w)
                    run_page(pg, tag, errs, phone)
                    check("%s 0 page errors %s" % (tag, bad[:1]), not bad, errs)
                    ctx.close(); br.close()
            finally:
                srv.terminate()
    if a.json:
        Path(a.json).write_text(json.dumps({"ok": OKN[0], "fail": len(errs), "pages": REPORT}, indent=1), encoding="utf-8")
    print("\nQ305 #foot PROOF: %d OK / %d FAIL" % (OKN[0], len(errs)))
    for e in errs:
        print("  FAIL", e)
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
