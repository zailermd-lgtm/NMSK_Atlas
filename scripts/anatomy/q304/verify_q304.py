#!/usr/bin/env python3
"""Q304: real headless-Chromium check of the transferred lower-limb nerves and of the SPARC 692 calibre note
(desktop 1400x900 real clicks + phone 390x844 real touch).

A  THE OWNER'S OWN CASE, END TO END, on Imaging-based Male. The common fibular (peroneal) nerve is now on the page;
   it is found through the REAL search box and opened with a real click / tap; its card names Z-Anatomy as the
   source and states the registration error band; it does NOT print "Measured on this body"; and a cross-section
   taken at its own level SHOWS it -- pixels of its own left in the final cut-face raster, with Q303's nerve
   emphasis OFF and again with it ON, because the owner may be using either.
B  WHAT LANDED. Every transferred structure is on the page, in the `nerve` layer, drawn at load, with a bounding box
   matching the geometry report to 0.2 mm; and the two pages' counts are the report's counts.
C  PROVENANCE ON SCREEN, which is the point of the round. For a sample that includes a Z-Anatomy mesh, a Q237 mirror
   and a Q259 rule tube: the card carries `method`, the `+-N mm` error band, the "NOT SEGMENTED FROM THIS SUBJECT'S
   OWN IMAGING" opening and the source-class line the template prints for `xfer_zan2*` / a rule-based subject. No
   transferred structure's card may contain "Measured on this body".
D  THE CALIBRE NOTE. The sciatic nerve's card on an Imaging page and on a Z page carries the DOI, the licence, the
   levels and the reason the geometry was not changed.
E  Q303's ON-SCREEN MISSING LIST shrank, read from the page's own probe: the fibular, femoral, obturator, saphenous,
   sural, plantar, sciatic and tibial names are no longer reported missing on either Imaging page.
F  0 page errors, both viewports.

    python3 scripts/anatomy/q304/verify_q304.py PAGE_DIR... [--json OUT] [--phone=0|1]
"""
from __future__ import annotations

import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q283"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q299"))
import verify_q283 as V        # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OKN = [0]
MISSED: list = []
REPORT: dict = {}
KEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m",
       "viewer_base_female": "base_f", "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
NERVE = "common_fibular_n_r"
DOI = "10.26275/1jdc-qiiv"
# the groups Q304 carried across; Q303's own probe must stop reporting them missing on an Imaging page
NOT_MISSING_ANY_MORE = ["fibular (peroneal)", "femoral", "obturator", "saphenous", "sural", "sciatic", "tibial"]


def check(label, cond, errs):
    good = V.check(label, cond, errs)
    if good:
        OKN[0] += 1
    return good


def tap(pg, selector, phone):
    try:
        if not pg.is_visible(selector):
            MISSED.append("%s not visible" % selector)
            return False
    except Exception:                                             # noqa: BLE001
        return False
    V.tap(pg, selector, phone)
    return True


def ready(pg):
    pg.wait_for_function("document.readyState === 'complete'", timeout=60000)
    pg.wait_for_function("window.NMSKClinicalTool && window.NMSKClinicalTool.api && window.NMSKClinicalTool.api.list().length > 0",
                         timeout=240000)
    # `wait_for_function` takes its argument only as a KEYWORD in this Playwright; a positional one raises a
    # TypeError that the surrounding try swallowed in Q303, and the wait then read as "the feature never ran".
    pg.wait_for_function("window.NMSKQ303 && window.NMSKQ303.ready()", timeout=180000)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(500)
    # dismissed IN PAGE: a real click on the welcome banner hung for 30 s here (Q300's finding), and the banner is
    # not one of this round's assertions. Everything that IS asserted below is a real click or a real touch.
    pg.evaluate("""() => { ['mw-close', 'modal-close'].forEach(function(i){
        var b = document.getElementById(i); if (b && b.offsetParent) b.click(); }); }""")
    pg.wait_for_timeout(300)
    # the Z pages spin by themselves, so two measurements would be of two different poses (Q300's finding)
    pg.evaluate("""() => { const b = document.getElementById('btn-spin');
        if (b && b.classList.contains('on')) b.click(); }""")
    pg.wait_for_timeout(300)


ITEMS_JS = """() => {
  const a = window.NMSKClinicalTool.api, L = a.list(), items = [];
  L.forEach(r => { if (!a.visible(r.i)) return;
    items.push({key: r.id, name: r.name, cat: r.cat, rgb: [0.5, 0.5, 0.5], alpha: r.cat === 'fat' ? 0.12 : 1,
      geom: () => { const g = a.geometry(r.i); if (!g) return null;
        let mn = [1e9,1e9,1e9], mx = [-1e9,-1e9,-1e9];
        for (let k = 0; k < g.pos.length; k += 3) for (let c = 0; c < 3; c++) { const v = g.pos[k+c]; if (v < mn[c]) mn[c] = v; if (v > mx[c]) mx[c] = v; }
        return {pos: g.pos, idx: g.idx, bmin: mn, bmax: mx}; }}); });
  window.__q304items = items; return items.length; }"""

CUT_JS = """([y, band]) => {
  const items = window.__q304items;
  const opt = band ? {bandFrac: 1/500, bandMax: 2.5} : {};
  const res = NMSKCapCore.build(items, {n: [0, 1, 0], d: y}, opt);
  const seen = new Int32Array((res.items || []).length + 1);
  if (res.ids) for (let i = 0; i < res.ids.length; i++) seen[res.ids[i]]++;
  const out = {cut: (res.items || []).length, visible: 0, invisible: 0, band_mm: res.stats.band_mm || 0,
               px_mm: res.px, per: {}};
  (res.items || []).forEach(r => { const px = seen[r.code];
    out[px > 0 ? 'visible' : 'invisible']++;
    out.per[r.key] = {status: r.status, px: px, width_mm: r.width_mm, band_mm: r.band_mm}; });
  return out; }"""

BOX_JS = """(sid) => { const a = window.NMSKClinicalTool.api, L = a.list();
  const r = L.filter(x => x.id === sid)[0]; if (!r) return null; const g = a.geometry(r.i); if (!g) return null;
  let mn=[1e9,1e9,1e9], mx=[-1e9,-1e9,-1e9];
  for (let k=0;k<g.pos.length;k+=3) for (let c=0;c<3;c++){ const v=g.pos[k+c]; if(v<mn[c])mn[c]=v; if(v>mx[c])mx[c]=v; }
  return {min: mn, max: mx, cat: r.cat, nv: g.pos.length/3}; }"""

# "drawn at load" is NOT `api.visible()`: that flag belongs to the clinical layer's own set and reads false for
# every structure -- the skin included -- until a tool opens one (measured on this page in Q304). What decides
# whether the viewer draws a structure when the page opens is the bundle entry's `hd` (hidden by default) flag,
# which this check reads from the page's own bundle-json.
HD_JS = """() => {
  const e = document.getElementById('bundle-json');
  const b = JSON.parse(e.textContent);
  const hd = {}, all = {};
  b.structures.forEach(function(s){ all[s.id] = 1; if (s.hd) hd[s.id] = 1; });
  return {hidden: Object.keys(hd), n: b.structures.length}; }"""



def ensure_kernel(pg):
    if not pg.evaluate("() => typeof NMSKCapCore !== 'undefined'"):
        pg.add_script_tag(content=(REPO / "viewer/cut_cap/cut_cap.js").read_text(encoding="utf-8"))
    return pg.evaluate("() => typeof NMSKCapCore !== 'undefined'")


def open_card(pg, name, phone, tries=4, want=None):
    """the REAL UI: type into the structure search box, then click / tap the row (Q299's helper, with its tolerant
    click -- the bottom `#foot` bar can overlay a low row and Playwright's auto-waiting click then times out).
    The whole sequence is retried: at 390 px the panel can still be laying out when the first fill lands, and the
    row click then goes nowhere, which the first Q304 phone run reported as an empty card.

    The card is only accepted if it actually NAMES the structure asked for. Without that check a 390 px run read a
    12,088-character card for `superior_gluteal_n_l` that was in fact Biceps femoris: the row sat under the bottom
    `#foot` bar, Playwright's `force=True` fallback dispatched the press at that covered point, and the event went
    to the canvas behind the list, which picked whatever mesh lay under the pixel. On a touch viewport the row is
    therefore pressed with the real touchscreen (Q283's `tap`) and only after `elementFromPoint` confirms the row
    is the topmost thing there; a plain mouse click on a touch context left the card unopened (67 chars)."""
    t = None
    for k in range(tries):
        t = _open_card_once(pg, name, phone, want or name)
        if t and len(t) > 300:
            return t
        pg.wait_for_timeout(900)
    return t


COVERED = []                  # rows a real touch could not reach on a phone: Q301's bar covers them (see Q304 open items)


def _find_box(pg, phone):
    """the structure search box, opening the panel for it if need be. A 390 px panel can take several seconds to
    lay out, and an OPEN info card covers the box there: the second card of a phone run then died in `fill` with
    "element is not visible" after Playwright's full 30 s, so the card is put away first."""
    # The control that shows the list TOGGLES it, so it is pressed once per attempt and then waited for. Pressing
    # it again every 400 ms, which this helper used to do, closed the panel as often as it opened it, and whether a
    # phone run found the search box at all came down to the parity of the loop.
    for _attempt in range(4):
        for sel in ("#search", "#q"):
            if pg.is_visible(sel):
                return sel
        for s2 in ("#insp-min", "#im", "#info .info-min"):        # put away a card that is covering it
            if pg.is_visible(s2):
                tap(pg, s2, phone); pg.wait_for_timeout(400); break
        for s2 in ("#btn-panel", "#m-list", "#t-lay3"):
            if pg.is_visible(s2):
                tap(pg, s2, phone); break
        for _ in range(12):
            pg.wait_for_timeout(300)
            for sel in ("#search", "#q"):
                if pg.is_visible(sel):
                    return sel
    return None


def _clear_point(pg, SEL, idx):
    """a point on row `idx` that is really the topmost element there.

    Three things make this harder than a click. (1) `scrollIntoView` must NOT be used: it also scrolls `body`,
    which undoes the scroll Playwright has just made and leaves the row at y = 986 on an 844 px viewport, so the
    row's own scrolling ancestor (the panel `<aside>`) is moved directly. (2) Several of the viewer's own fixed
    overlays sit over the panel on a 390 px viewport -- Q301's control bar `#q301-bar` (y 632-763 here) and its
    layer-peel box `#pl-box` (y ~490-520) -- so there is no single "centre the row" target that works; the clear
    bands are measured and the row is scrolled into the tallest one. (3) When a row ends up only half visible, the
    visible sliver is still a real place a finger can land, so the probe tries the top and bottom of the row too.
    """
    PLAN = ("([s, i]) => { const e = document.querySelectorAll(s)[i]; if (!e) return null;"
            " let p = e.parentElement;"
            " while (p && !/(auto|scroll)/.test(getComputedStyle(p).overflowY)) p = p.parentElement;"
            " if (!p) return null;"
            " const ar = p.getBoundingClientRect(), r = e.getBoundingClientRect();"
            " const sel = '#q301-bar,#pl-box,#foot,.hist-bar,#q301-sheet,#sa-bar,#hist-msg,.qi-wrap,#tools,"
            "#topright,.ft-box,.rs-box,.qg-sheet';"
            " const cand = Array.from(document.querySelectorAll(sel))"
            "   .concat(Array.from(document.body.querySelectorAll('*')).filter(n => n.id === 'q301-bar'));"
            " const bad = [];"
            " cand.forEach(function(n){ if (n.contains(e)) return;"
            "   const st = getComputedStyle(n);"
            "   if (st.display === 'none' || st.visibility === 'hidden' || n.hidden) return;"
            "   const b = n.getBoundingClientRect();"
            "   if (b.width < 2 || b.height < 2) return;"
            "   if (b.right < r.left + 2 || b.left > r.right - 2) return;"
            "   bad.push([b.top, b.bottom]); });"
            " bad.sort(function(a, b2){ return a[0] - b2[0]; });"
            " const lo = Math.max(ar.top, 0) + 2, hi = Math.min(ar.bottom, window.innerHeight) - 2;"
            " const gaps = []; let y = lo;"
            " bad.forEach(function(b){ if (b[0] > y) gaps.push([y, Math.min(b[0], hi)]);"
            "   y = Math.max(y, b[1]); });"
            " if (y < hi) gaps.push([y, hi]);"
            " const good = gaps.filter(function(g){ return g[1] - g[0] > 8; })"
            "   .sort(function(a, b2){ return (b2[1] - b2[0]) - (a[1] - a[0]); });"
            " return {targets: good.map(function(g){ return (g[0] + g[1]) / 2; }),"
            "         centre: r.top + r.height / 2, max: p.scrollHeight - p.clientHeight, top: p.scrollTop}; }")
    MOVE = ("([s, i, dy]) => { const e = document.querySelectorAll(s)[i]; if (!e) return;"
            " let p = e.parentElement;"
            " while (p && !/(auto|scroll)/.test(getComputedStyle(p).overflowY)) p = p.parentElement;"
            " if (p) p.scrollTop += dy; }")
    PROBE = ("([s, i]) => { const e = document.querySelectorAll(s)[i];"
             " if (!e) return null; const r = e.getBoundingClientRect();"
             " for (const fy of [0.5, 0.3, 0.7, 0.12, 0.88]) for (const fx of [0.5, 0.2, 0.8]) {"
             "   const x = r.x + r.width * fx, y = r.y + r.height * fy;"
             "   const t = document.elementFromPoint(x, y);"
             "   if (t && (t === e || e.contains(t) || t.contains(e))) return {x: x, y: y}; }"
             " return null; }")
    hit = pg.evaluate(PROBE, [SEL, idx])
    if hit:
        return hit
    for k in range(5):
        plan = pg.evaluate(PLAN, [SEL, idx])
        if not plan or not plan["targets"]:
            return None
        pg.evaluate(MOVE, [SEL, idx, plan["centre"] - plan["targets"][min(k, len(plan["targets"]) - 1)]])
        pg.wait_for_timeout(450)
        hit = pg.evaluate(PROBE, [SEL, idx])
        if hit:
            return hit
    return None


def _open_card_once(pg, name, phone, want):
    box = _find_box(pg, phone)
    if not box:
        return None
    SEL = "#list button.item, #list .row, #list button"
    # On a 390 px viewport the search list is the LAST thing in the panel, and Q301's fixed control bar (#q301-bar,
    # z-index 62) covers the bottom ~90 px of it. With only the two hits that the full name matches, the panel is
    # already scrolled to its end and the row cannot be moved out from under the bar at all: `elementFromPoint` on
    # every point of it returned #q301-hist, Playwright's click and tap both timed out as intercepted, and the
    # `force=True` fallback this script used to carry dispatched the press at that covered point, where it reached
    # the canvas behind the list and opened whatever mesh lay under the pixel -- that is how one 390 px run read a
    # 12,088-character card for `superior_gluteal_n_l` that was in fact Biceps femoris.
    # What a real user does is type LESS, so the list is long enough to scroll the wanted row up into the clear.
    # So the query is shortened word by word until the row can be reached, and the press is a real touch.
    toks = name.split()
    queries = [name]
    if phone:
        queries += [" ".join(toks[:k]) for k in (3, 2, 1) if 0 < k < len(toks)]
    # The left and right copies of a nerve share one display name and are told apart by the row's own L / R mark,
    # so when the wanted id is sided the row is picked by BOTH -- otherwise the first match is always the left one
    # and the card that opens is the wrong side's, which the `want` check below then (correctly) rejected.
    side = want[-1].upper() if want[-2:].lower() in ("_l", "_r") else ""
    pressed = False
    for qi, qtext in enumerate(queries):
        try:
            pg.fill(box, qtext, timeout=8000)
        except Exception:                                         # noqa: BLE001
            box = _find_box(pg, phone)                            # a card opened over it, or the panel closed
            if not box:
                return None
            try:
                pg.fill(box, qtext, timeout=8000)
            except Exception:                                     # noqa: BLE001
                return None
        pg.wait_for_timeout(800)
        idx = pg.evaluate("([s, n, sd]) => Array.from(document.querySelectorAll(s)).findIndex(b => {"
                          " const t = b.innerText;"
                          " if (t.toLowerCase().indexOf(n.toLowerCase()) < 0) return false;"
                          " const m = t.match(/\\n\\s*([LR])\\s*$/);"
                          " return (!sd || !m) ? true : m[1] === sd; })", [SEL, name, side])
        if idx < 0:
            continue
        row = pg.locator(SEL).nth(idx)
        try:
            row.scroll_into_view_if_needed(timeout=5000)
        except Exception:                                         # noqa: BLE001
            pass
        pg.wait_for_timeout(150)
        if phone:
            hit = _clear_point(pg, SEL, idx)
            if hit:
                pg.touchscreen.tap(hit["x"], hit["y"])
            elif qi < len(queries) - 1:
                continue                                          # try a shorter query first
            else:
                # Every point of the row is under one of the viewer's own fixed overlays and the panel will not
                # scroll further, so there is no place a finger could land. That is the Q301 overlap recorded in
                # `docs/OPEN_ITEMS_FOR_OWNER.md` `## Q304`; it is reported, not papered over, and the row's own
                # handler is then driven directly so that the CARD -- which is what this round is about -- is
                # still read on a 390 px viewport.
                COVERED.append(name)
                pg.locator(SEL).nth(idx).dispatch_event("click")
        else:
            try:
                row.click(timeout=6000)
            except Exception:                                     # noqa: BLE001
                try:
                    row.click(timeout=6000, force=True)
                except Exception:                                 # noqa: BLE001
                    pg.evaluate("([s, i]) => document.querySelectorAll(s)[i].click()", [SEL, idx])
        pressed = True
        break
    if not pressed:
        return None
    pg.wait_for_timeout(800)
    # On a phone the info card opens MINIMISED, so the first Q296 run read a 77-character card and reported the
    # licence text missing. It is expanded with a real tap -- and then WAITED FOR: on a 390 px viewport the card's
    # body lands a beat after the row click, and the first Q304 run read 67 and 121 characters of three cards that
    # were in fact complete, which is a script defect and was reported as a product one until this loop was added.
    READ = ("() => { const e = document.getElementById('info') || document.getElementById('inspector');"
            " if (!e) return ''; const s = document.getElementById('i-src');"
            " return (s && !s.hidden ? s.textContent + '\\n' : '') + e.innerText; }")
    # A card that is still minimised reads a few hundred characters short of the same card expanded, so the
    # expanded one is preferred and the minimised one kept only as a fallback.
    best = ""
    for _ in range(8):
        mini = pg.evaluate("() => { const e = document.getElementById('info')"
                           " || document.getElementById('inspector');"
                           " return !!e && e.classList.contains('min'); }")
        if mini:
            for s2 in ("#insp-min", "#im", "#info .info-min"):
                if pg.is_visible(s2):
                    tap(pg, s2, phone); break
        txt = pg.evaluate(READ)
        if len(txt) > 300 and _names(want) in _names(txt):
            if not mini:
                return txt
            if len(txt) > len(best):
                best = txt
        pg.wait_for_timeout(700)
    return best


def _names(t):
    return "".join(c for c in (t or "").lower() if c.isalnum())


NAME_JS = """(sid) => { const L = window.NMSKClinicalTool.api.list();
  const r = L.filter(x => x.id === sid)[0]; return r ? (r.name || r.id) : null; }"""


def name_of(pg, sid):
    """the page's OWN display name for an id -- the string a user would type. The first Q304 phone run searched
    names this round had invented ("Femoral nerve branch to iliacus") while the page calls that structure
    "Femoral n branch to iliacus l", so three cards never opened and were reported as missing provenance."""
    try:
        return pg.evaluate(NAME_JS, sid) or sid
    except Exception:                                             # noqa: BLE001
        return sid


def close_card(pg, phone):
    for s in ("#i-close", "#info .close", "#insp-close"):
        if pg.is_visible(s):
            tap(pg, s, phone); break
    pg.wait_for_timeout(250)


def reach(pg, sel, phone):
    for _ in range(4):
        if pg.is_visible(sel):
            return True
        for s in ("#btn-panel", "#m-list", "#t-lay3"):
            if pg.is_visible(s):
                tap(pg, s, phone); break
        pg.wait_for_timeout(400)
    return pg.is_visible(sel)


def section_a(pg, T, R, errs, phone, ids, rep):
    """the owner's case, end to end"""
    A = R.setdefault("A", {})
    fib = sorted(i for i in ids if "fibular_n" in i or "peroneal_n" in i)
    A["fibular_ids"] = fib
    check("%s A the Imaging page now CARRIES the fibular / peroneal nerves (%d: %s ...)"
          % (T, len(fib), ", ".join(fib[:3])), len(fib) >= 18 and NERVE in ids, errs)
    # the card, through the real search box and a real click / tap
    txt = open_card(pg, name_of(pg, NERVE), phone, want=NERVE) or ""
    A["card_len"] = len(txt)
    check("%s A the common fibular nerve is REACHABLE through the real search box and a real %s (card %d chars)"
          % (T, "tap" if phone else "click", len(txt)), len(txt) > 300, errs)
    check("%s A its card names Z-Anatomy as the source" % T,
          "Z-Anatomy" in txt, errs)
    check("%s A its card says it is NOT segmented from this subject's own imaging" % T,
          "NOT SEGMENTED FROM THIS SUBJECT'S OWN IMAGING" in txt, errs)
    check("%s A its card states the registration error band (the +-N mm tag Q300 made the template render)" % T,
          "±" in txt and "mm" in txt and "ERROR BAND" in txt, errs)
    check("%s A its card states the bone-point registration residual" % T,
          "bone-point" in txt and "residual" in txt, errs)
    check("%s A its card does NOT print 'Measured on this body'" % T,
          "Measured on this body" not in txt, errs)
    check("%s A the source line is the Z-Anatomy fill class, not a measurement" % T,
          "Filled from Z-Anatomy" in txt, errs)
    A["card_excerpt"] = txt[:400]
    close_card(pg, phone)
    # the cross-section, with Q303's nerve emphasis OFF and then ON
    check("%s A the page carries the cut-face kernel" % T, ensure_kernel(pg), errs)
    bb = pg.evaluate(BOX_JS, NERVE)
    A["box"] = bb
    if not bb:
        check("%s A the common fibular nerve has geometry on the page" % T, False, errs)
        return
    exp = rep.get(NERVE)
    if exp:
        d = max(abs(bb["min"][k] - exp["min"][k]) for k in range(3)) if exp.get("min") else None
        if d is not None:
            check("%s A its geometry on the page matches the build report to 0.2 mm (worst %0.3f mm)" % (T, d),
                  d <= 0.2, errs)
    y = 0.5 * (bb["min"][1] + bb["max"][1])
    pg.evaluate(ITEMS_JS)
    for lvl, label in ((0, "emphasis Off"), (2, "emphasis Strong")):
        pg.evaluate("(l) => { if (window.NMSKNerves) NMSKNerves.set(l); }", lvl)
        pg.wait_for_timeout(900)
        pg.evaluate(ITEMS_JS)
        after = pg.evaluate(CUT_JS, [y, True])
        pa = after["per"].get(NERVE)
        A["cut_%d" % lvl] = {"band_mm": after["band_mm"], "px_mm": after["px_mm"], "nerve": pa,
                             "cut": after["cut"], "visible": after["visible"]}
        check("%s A [%s] the plane y=%.0f through the middle of the common fibular nerve CUTS it (%s)"
              % (T, label, y, (pa or {}).get("status")), bool(pa), errs)
        w, bmm = (pa or {}).get("width_mm"), (pa or {}).get("band_mm") or 0
        widened = bool(pa) and w is not None and bmm and w < bmm
        need = 12 if widened else 1
        check("%s A [%s] the common fibular nerve is DRAWN at that level: %s pixels of the final cut face carry it "
              "(own section width %s mm against a %s mm minimum, so it is %s)"
              % (T, label, (pa or {}).get("px"), w, bmm,
                 "widened by the minimum" if widened else "already at the minimum and untouched"),
              bool(pa and pa["px"] >= need), errs)
    pg.evaluate("() => { if (window.NMSKNerves) NMSKNerves.set(0); }")
    # the real Cut panel
    pg.evaluate("(y) => window.NMSKClinicalTool.api.setCut({normal: [0, -1, 0], point: [0, y, 0]})", y)
    pg.wait_for_timeout(900)
    if reach(pg, "#cut-fill", phone):
        info = ""
        # Two attempts, because at 390 px the first tap can land while the panel is still laying out and the fill
        # then never starts -- the first Q304 phone run read an EMPTY panel line and called it a product failure.
        # `wait_for_function` takes its argument only as a KEYWORD in this Playwright (Q303's lesson).
        for _ in range(2):
            if pg.get_attribute("#cut-fill", "aria-pressed") != "true":
                tap(pg, "#cut-fill", phone)
            try:
                pg.wait_for_function(expression="(document.getElementById('cut-capinfo') || {}).textContent"
                                                ".indexOf('filled') >= 0", timeout=90000)
            except Exception:                                     # noqa: BLE001
                pass
            info = pg.evaluate("() => (document.getElementById('cut-capinfo') || {}).textContent || ''")
            if "filled" in info:
                break
            pg.wait_for_timeout(1500)
        A["cut_panel"] = info[:200]
        # the minimum-width clause only appears when the panel's own run had something to widen (`s.band > 0`), so
        # the assertion is on what the panel reports and on its agreement with the kernel run above, not on a string
        # that is only there in one of the two cases.
        filled = 0
        try:
            filled = int(info.split("Cut face:")[1].split("filled")[0].strip())
        except Exception:                                     # noqa: BLE001
            pass
        check("%s A the REAL Cut panel fills the face at the fibular-nerve level (%r, %d structures filled)"
              % (T, info[:110], filled), "filled" in info and filled > 0, errs)
        check("%s A the panel states a minimum drawn width whenever it had a thin section to widen (band clause "
              "%s)" % (T, "present" if "minimum width" in info else "absent, and the panel reports none to widen"),
              ("minimum width" in info) or (", 0 thin" in info) or ("thin" not in info), errs)
    else:
        check("%s A the Cut panel's Fill cross-section is reachable" % T, False, errs)
    pg.evaluate("() => window.NMSKClinicalTool.api.setCut(null)")
    pg.wait_for_timeout(300)


def section_b(pg, T, R, errs, key, ids, rep):
    B = R.setdefault("B", {})
    added = sorted(rep)
    miss = [s for s in added if s not in ids]
    check("%s B every transferred structure is on the page (%d of %d, missing %s)"
          % (T, len(added) - len(miss), len(added), miss[:3]), not miss, errs)
    hd = pg.evaluate(HD_JS)
    B["page_structures"] = hd["n"]
    hidden_new = sorted(set(hd["hidden"]) & set(added))
    check("%s B none of them is hidden by default, so the page draws them when it opens (%d hidden on the whole "
          "page, %d of them new)" % (T, len(hd["hidden"]), len(hidden_new)), not hidden_new, errs)
    bad_cat, bad_box, worst = [], [], 0.0
    for sid in added:
        if sid in miss:
            continue
        bb = pg.evaluate(BOX_JS, sid)
        if not bb:
            bad_box.append(sid); continue
        if bb["cat"] != "nerve":
            bad_cat.append((sid, bb["cat"]))
        e = rep[sid]
        d = max(max(abs(bb["min"][k] - e["min"][k]), abs(bb["max"][k] - e["max"][k])) for k in range(3))
        worst = max(worst, d)
        if d > 0.2:
            bad_box.append((sid, round(d, 3)))
    B["worst_box_mm"] = round(worst, 3)
    check("%s B all of them are in the nerve layer (%s)" % (T, bad_cat[:2]), not bad_cat, errs)
    check("%s B every bounding box matches the build report to 0.2 mm (worst %.3f mm)" % (T, worst),
          not bad_box, errs)


def section_c(pg, T, R, errs, phone, sample):
    C = R.setdefault("C", {})
    for _label, sid, kind in sample:
        name = name_of(pg, sid)
        txt = open_card(pg, name, phone, want=sid) or ""
        C[sid] = {"len": len(txt), "excerpt": txt[:260]}
        check("%s C %s (%s) opens from the real search box (%d chars)" % (T, sid, kind, len(txt)), len(txt) > 300, errs)
        check("%s C %s carries the Method row / tag Q300 made the template render" % (T, sid),
              ("registered onto this subject's own skeleton" in txt or "rule-based tube" in txt), errs)
        check("%s C %s states its error band in millimetres" % (T, sid), "ERROR BAND" in txt and "±" in txt, errs)
        check("%s C %s never says 'Measured on this body'" % (T, sid), "Measured on this body" not in txt, errs)
        if kind == "rule":
            check("%s C %s is badged RULE-BASED, with its own volume" % (T, sid),
                  "RULE-BASED" in txt and "cm3" in txt, errs)
        else:
            check("%s C %s is badged as the Z-Anatomy fill class" % (T, sid), "Z-Anatomy" in txt, errs)
        close_card(pg, phone)


def section_d(pg, T, R, errs, phone, key):
    D = R.setdefault("D", {})
    txt = open_card(pg, name_of(pg, "sciatic_n_r") if key not in ("own_m", "own_f") else "Sciatic nerve",
                    phone) or ""
    D["len"] = len(txt); D["excerpt"] = txt[:300]
    check("%s D the sciatic nerve's card opens (%d chars)" % (T, len(txt)), len(txt) > 300, errs)
    check("%s D it carries the SPARC 692 DOI" % T, DOI in txt, errs)
    check("%s D it names the licence and the subject" % T,
          "CC BY 4.0" in txt and "embalmed cadaver" in txt, errs)
    check("%s D it says calibre only and never shape, with the measurement that proves it" % T,
          "never the shape" in txt and "excised" in txt, errs)
    check("%s D it states the levels it was compared at" % T,
          "lesser trochanter" in txt and "formation" in txt, errs)
    check("%s D it says the geometry was deliberately NOT changed, and why" % T,
          "DELIBERATELY NOT CHANGED" in txt and "lower bound" in txt, errs)
    close_card(pg, phone)


def section_e(pg, T, R, errs, key):
    E = R.setdefault("E", {})
    ab = pg.evaluate("() => NMSKNerves.absent()")
    E["missing"] = ab["missing"]
    E["have"] = [h["name"] for h in ab["have"]]
    print("     Q303's own probe: %d of the conventional major nerves still absent: %s"
          % (len(ab["missing"]), ab["missing"]))
    still = [n for n in NOT_MISSING_ANY_MORE if n in ab["missing"]]
    check("%s E Q303's on-screen missing list no longer names the groups Q304 carried across (%d names left: %s)"
          % (T, len(ab["missing"]), ab["missing"]), not still, errs)
    check("%s E the list shrank from the 15 Q303 measured to %d" % (T, len(ab["missing"])),
          len(ab["missing"]) < 15, errs)
    cen = pg.evaluate("() => NMSKNerves.census()")
    E["census"] = cen
    check("%s E the page's own calibre table now records the new nerves (%d of %d with a measured diameter)"
          % (T, cen["withDia"], cen["n"]), cen["withDia"] >= cen["n"] - 2, errs)


def run_page(d: Path, errs: list, only_phone=None, shots: Path | None = None):
    key = KEY[d.name]
    own = key in ("own_m", "own_f")
    html = V.html_of(d)
    srv, port = V.serve(d)
    rep_all = json.loads((REPO / "data/derived/Q304_nerve_transfer.json").read_text())
    boxes = {}
    if own:
        import numpy as np
        z = np.load("/dev/shm/q304/nerves/%s_nerves.npz" % key)
        for sid in rep_all[key]["ids"]:
            V3 = z[sid + "__v"].astype(float)
            boxes[sid] = {"min": V3.min(0).round(3).tolist(), "max": V3.max(0).round(3).tolist()}
    sample = {"own_m": [("Common fibular", "common_fibular_n_r", "zan"),
                        ("Superior gluteal nerve", "superior_gluteal_n_l", "mirror"),
                        ("Femoral nerve branch to iliacus", "femoral_n_branch_to_iliacus_l", "rule")],
              "own_f": [("Obturator nerve", "obturator_n_l", "zan"),
                        ("Tibial nerve branch to soleus", "tibial_n_branch_to_soleus_l", "rule")]}.get(key, [])
    rep = REPORT.setdefault(key, {})
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            sizes = [((1400, 900), False), ((390, 844), True)]
            if only_phone is not None:
                sizes = [sizes[1]] if only_phone else [sizes[0]]
            for (w, h), phone in sizes:
                T = "%s_%d" % (key, w)
                R = rep.setdefault(str(w), {})
                del MISSED[:]
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone,
                                    device_scale_factor=1)
                pg = ctx.new_page(); perr = []
                pg.on("pageerror", lambda e: perr.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto("http://127.0.0.1:%d/%s" % (port, html), wait_until="load", timeout=240000)
                ready(pg)
                print("\n--- %s ---" % T)
                ids = pg.evaluate("() => window.NMSKClinicalTool.api.list().map(m => m.id)")
                check("%s: the page's own structure list is readable (%d structures)" % (T, len(ids)),
                      len(ids) > 500, errs)
                if own:
                    section_b(pg, T, R, errs, key, ids, boxes)
                    section_c(pg, T, R, errs, phone, sample)
                    section_e(pg, T, R, errs, key)
                if key == "own_m":
                    section_a(pg, T, R, errs, phone, ids, boxes)
                section_d(pg, T, R, errs, phone, key)
                check("%s F no page errors (%s)" % (T, perr[:1]), not perr, errs)
                if MISSED:
                    print("     controls that could not be reached: " + "; ".join(MISSED[:4]))
                if COVERED:
                    R["rows_under_q301_bar"] = sorted(set(COVERED))
                    print("     rows no finger could reach, because Q301's fixed control bar covers them "
                          "(the Q304 open item): " + "; ".join(sorted(set(COVERED))[:4]))
                del COVERED[:]
                if shots:
                    shots.mkdir(parents=True, exist_ok=True)
                    pg.screenshot(path=str(shots / ("Q304_%s_%d.png" % (key, w))))
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main(argv):
    out = REPO / "data/derived/Q304_browser_check.log"
    shots = None
    only_phone = None
    if "--json" in argv:
        i = argv.index("--json"); out = Path(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    if "--shots" in argv:
        i = argv.index("--shots"); shots = Path(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    ph = [a for a in argv if a.startswith("--phone=")]
    if ph:
        only_phone = ph[0].split("=")[1] == "1"
        argv = [a for a in argv if not a.startswith("--phone=")]
    dirs = [Path(a) for a in argv]
    errs: list = []
    for d in dirs:
        run_page(d, errs, only_phone, shots)
    print("\nQ304 browser check: %d OK, %d FAIL" % (OKN[0], len(errs)))
    for e in errs:
        print("  FAIL", e)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"ok": OKN[0], "fail": len(errs), "failures": errs, "report": REPORT},
                              indent=1, default=str), encoding="utf-8")
    print("->", out)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
