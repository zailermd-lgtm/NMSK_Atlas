"""Q393: the owner's UI round on the Base pages -- Labels on the bar, the Settings tree + search, the add-on panels' titled sections,
no stray tool mark at the screen centre, and the figure keeping the main part of the screen while panels are open.

  1  Labels: an entry on the bar; one tap opens the labels panel (labels drawn on the model) beside the figure; the button stays in Search.
  2  Settings: a tree by topic and a search of its own (by name, synonyms, Hebrew topic words); a leaf goes to the real control.
  3  Add-on panels: titled sections, one open at a time and remembered; long notes folded to one line; the safety line stays.
  4  The centre of the screen carries no tool mark once the tool is closed (needle, planning, scan, pose, after Clear).
  5  With a group / panel open the figure keeps >= 60 % of the width (desktop) or sits above a bottom sheet of <= 45 % (phone),
     centred in the free part.

  python3 scripts/anatomy/q393/verify_ui_q393.py <page dir> [--size 390x844] [--shots DIR]   -> Q393_UI_OK / Q393_UI_FAIL n
"""
import sys, json, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q321"))
import verify_quickcard_q321 as Q
from playwright.sync_api import sync_playwright

ROOM = """() => { const vw = innerWidth, vh = innerHeight, phone = vw <= 560;
  const sel = ['#q301-sheet','#lab-panel','#lab-legend','#pose-panel','#q382-panel','#needle-panel','#cut-panel','#ms-bar','#img-root','#us-root'];
  const vis = e => { if (!e || e.hidden) return false; const s = getComputedStyle(e); if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false; const r = e.getBoundingClientRect(); return r.width > 30 && r.height > 30 && r.right > 0 && r.left < vw && r.bottom > 0 && r.top < vh; };
  const ps = sel.map(s => [s, document.querySelector(s)]).filter(x => vis(x[1])).map(x => { const r = x[1].getBoundingClientRect(); return {s: x[0], l: r.left, t: r.top, r: r.right, b: r.bottom}; });
  const cv = document.getElementById('view'), c = cv.getBoundingClientRect();
  let span = null;
  if (!phone) {                                   /* the widest horizontal gap at mid height, inside the canvas */
    const y0 = vh * 0.3, y1 = vh * 0.7; let cuts = ps.filter(p => p.t < y1 && p.b > y0 && (p.b - p.t) > vh * 0.18).map(p => [Math.max(c.left, p.l), Math.min(c.right, p.r)]).filter(p => p[1] > p[0]).sort((a, b) => a[0] - b[0]);
    let x = Math.max(0, c.left), best = [x, x]; for (const k of cuts) { if (k[0] - x > best[1] - best[0]) best = [x, k[0]]; x = Math.max(x, k[1]); }
    const end = Math.min(vw, c.right); if (end - x > best[1] - best[0]) best = [x, end]; span = best;
  } else {
    let cuts = ps.filter(p => p.l < vw * 0.6 && p.r > vw * 0.4).map(p => [Math.max(c.top, p.t), Math.min(c.bottom, p.b)]).filter(p => p[1] > p[0]).sort((a, b) => a[0] - b[0]);
    let y = Math.max(0, c.top), best = [y, y]; for (const k of cuts) { if (k[0] - y > best[1] - best[0]) best = [y, k[0]]; y = Math.max(y, k[1]); }
    const end = Math.min(vh, c.bottom); if (end - y > best[1] - best[0]) best = [y, end]; span = best;
  }
  let box = null; try { box = NMSKQuick.box(); } catch (e) {}
  return {vw, vh, phone, ps, cv: {l: c.left, t: c.top, r: c.right, b: c.bottom}, span, free: span[1] - span[0], box,
          lay: document.body.className.split(' ').filter(k => /^lay-|mode-on/.test(k)).join(' ')}; }"""

CLOSE_ALL = """() => { try { NMSKGroups.close(); } catch (e) {}
  try { const p = document.getElementById('lab-panel'); if (p && !p.hidden) __labCtl.openPanel(false); } catch (e) {}
  try { const p = document.getElementById('pose-panel'); if (p && !p.hidden && getComputedStyle(p).display !== 'none') document.getElementById('pz-close').click(); } catch (e) {}
  try { NMSKLayout.close(); } catch (e) {}
  try { const n = document.getElementById('needle-panel'); if (n && !n.hidden) document.getElementById('ncl-close').click(); } catch (e) {}
  try { const m = document.getElementById('ms-bar'); if (m && !m.hidden) document.getElementById('ms-close').click(); } catch (e) {}
  try { const c = document.getElementById('cut-panel'); if (c && !c.hidden) document.getElementById('cut-exit') && document.getElementById('cut-exit').click(); } catch (e) {} }"""

CENTRE = """() => { const cx = innerWidth / 2, cy = innerHeight / 2, out = [];
  document.querySelectorAll('.q367-pin, .ncl-tip, #q367-pins *, [class*="needle"], [id*="needle"], [class*="aim"], [class*="cross"], [class*="probe"]').forEach(e => {
    if (e.closest('#q301-bar, #q301-sheet, #q301-park, #needle-panel, #mode-bar, #q382-panel')) return;
    const s = getComputedStyle(e); if (e.hidden || s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return;
    const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return;
    if (r.left < cx + 60 && r.right > cx - 60 && r.top < cy + 60 && r.bottom > cy - 60) out.push((e.id || e.className.baseVal || e.className) + ' ' + Math.round(r.left) + ',' + Math.round(r.top)); });
  const T = window.NMSKClinicalTool, marks = [];
  if (T && T.ov && T.ov.gate && T.ov.gate()) marks.push('needle marks drawn (tool ' + (T.active ? 'open' : 'closed') + ')');
  let cut = null; try { cut = T && T.api && T.api.cut ? T.api.cut() : null; } catch (e) {}
  return {dom: out, marks: marks, cut: !!cut}; }"""


def main():
    a = sys.argv[1:]; src = Path(a[0]); w, h = 1400, 900
    if "--size" in a: w, h = [int(x) for x in a[a.index("--size") + 1].split("x")]
    shots = Path(a[a.index("--shots") + 1]) if "--shots" in a else None
    tag = src.name.replace("viewer_", "") + "_%dx%d" % (w, h)
    d = Q.page_copy(src, False); bad = 0
    def say(ok, msg):
        nonlocal bad
        print(("  OK   " if ok else "  FAIL ") + msg, flush=True); bad += 0 if ok else 1
    def shot(pg, name):
        if shots:
            shots.mkdir(parents=True, exist_ok=True); pg.screenshot(path=str(shots / ("%s_%s.png" % (tag, name))))
    with sync_playwright() as pl:
        srv, b, pg = Q.V.open_page(pl, d, w, h)
        try:
            Q.wait_ready(pg)
            pg.wait_for_function("window.NMSKLayout && NMSKLayout.ready() && document.getElementById('qg-labels')", timeout=30000)
            phone = w <= 560
            r0 = pg.evaluate(ROOM)
            say(not r0["ps"] and r0["cv"]["l"] <= 1 and r0["cv"]["r"] >= w - 1, "nothing open: the canvas is the whole screen  %s" % json.dumps(r0["cv"]))
            box0 = r0["box"]

            # ---------------------------------------------------------------- 1. Labels on the bar
            lb = pg.evaluate("""() => { const b = document.getElementById('qg-labels'), bar = document.getElementById('q301-bar'); if (!b) return null;
              if (bar && bar.scrollWidth > bar.clientWidth) b.scrollIntoView({inline: 'nearest'}); const r = b.getBoundingClientRect(), br = bar.getBoundingClientRect();
              return {txt: b.textContent.trim(), vis: !b.hidden && r.width > 20, inView: r.left >= -1 && r.right <= innerWidth + 1 && r.top >= -1 && r.bottom <= innerHeight + 1, inBar: r.top >= br.top - 1 && r.bottom <= br.bottom + 1,
                      search: (NMSKGroups.members('mark') || []).some(m => [].concat(m.adopt || []).indexOf('t-labels') >= 0)}; }""")
            say(lb and lb["txt"].startswith("Labels") and lb["vis"] and lb["inView"] and lb["inBar"], "a Labels entry on the bar, on the screen  %s" % json.dumps(lb))
            say(lb and lb["search"], "the Labels button is still in the Search sheet as well")
            pg.click("#qg-labels"); pg.wait_for_timeout(1800)
            st = pg.evaluate("""() => { const p = document.getElementById('lab-panel'), L = document.getElementById('lab-layer'), r = p.getBoundingClientRect();
              return {open: !p.hidden && r.width > 50, mode: __labCtl.settings().mode, drawn: L ? L.querySelectorAll('text, .lb-l, g').length : 0, pressed: document.getElementById('qg-labels').getAttribute('aria-pressed'),
                      l: r.left, t: r.top, r: r.right, b: r.bottom}; }""")
            say(st["open"] and st["mode"] != "off" and st["drawn"] > 0, "one tap opens the labels panel and labels are drawn on the model  %s" % json.dumps(st))
            rm = pg.evaluate(ROOM); shot(pg, "1_labels")
            if phone:
                say(st["t"] >= h * 0.55 - 2, "phone: the labels panel is a bottom sheet of <= 45 %% of the height (top %d of %d)" % (st["t"], h))
            else:
                say(rm["free"] >= 0.6 * w and not (st["l"] < w * 0.4 and st["r"] > w * 0.6), "desktop: the labels panel sits at a side, the figure keeps %d px (>= %d)" % (rm["free"], 0.6 * w))
            pg.click("#qg-labels"); pg.wait_for_timeout(700)
            say(pg.evaluate("() => document.getElementById('lab-panel').hidden"), "a second tap closes it")

            # ---------------------------------------------------------------- 2. Settings tree + search
            pg.evaluate("() => NMSKLayout.open()"); pg.wait_for_timeout(500)
            tr = pg.evaluate("""() => { const t = document.getElementById('q393-tree'); return {topics: [...t.querySelectorAll('.q393-t')].map(d => d.getAttribute('data-t')), leaves: t.querySelectorAll('.q393-leaf').length,
              open: [...t.querySelectorAll('.q393-t')].filter(d => d.open).length, sq: !!document.getElementById('q393-sq'), structSearch: (document.getElementById('search') || document.getElementById('q') || {}).id}; }""")
            say(len(tr["topics"]) >= 7 and tr["leaves"] >= 20 and tr["open"] == 0, "Settings opens as a tree: %d topics, %d settings, all folded  %s" % (len(tr["topics"]), tr["leaves"], tr["topics"]))
            for need in ("display", "labels", "layout", "text", "pose", "colour"):
                say(need in tr["topics"], "the tree has the topic %s" % need)
            pg.click(".q393-t[data-t=labels] > summary"); pg.wait_for_timeout(200)
            say(pg.evaluate("() => document.querySelector('.q393-t[data-t=labels]').open"), "a topic unfolds on a tap")
            shot(pg, "2_tree")
            pg.click("#q393-sq"); pg.keyboard.type("font"); pg.wait_for_timeout(300)
            f1 = pg.evaluate("() => [...document.querySelectorAll('.q393-leaf')].filter(b => !b.parentNode.hidden && !b.closest('.q393-t').hidden).map(b => b.textContent)")
            say(0 < len(f1) < tr["leaves"] and any("font" in x.lower() for x in f1), "the settings search filters by name: 'font' -> %s" % f1)
            sv = pg.evaluate("() => { const s = document.getElementById('search') || document.getElementById('q'); return s ? s.value : ''; }")
            say(sv == "", "the settings search is its own field: the structure search stays empty (%r)" % sv)
            pg.fill("#q393-sq", "lock"); pg.wait_for_timeout(200)
            f2 = pg.evaluate("() => [...document.querySelectorAll('.q393-leaf')].filter(b => !b.parentNode.hidden && !b.closest('.q393-t').hidden).map(b => b.textContent)")
            say(any("Lock panels" in x for x in f2), "by synonym: 'lock' -> %s" % f2)
            pg.fill("#q393-sq", "תוויות"); pg.wait_for_timeout(200)
            f3 = pg.evaluate("() => [...document.querySelectorAll('.q393-t')].filter(d => !d.hidden).map(d => d.getAttribute('data-t'))")
            say("labels" in f3, "by the Hebrew topic word 'תוויות' -> %s" % f3)
            pg.fill("#q393-sq", "qqzzxx"); pg.wait_for_timeout(200)
            say(pg.evaluate("() => !document.getElementById('q393-empty').hidden"), "no match: says so")
            shot(pg, "2_search")
            pg.fill("#q393-sq", "label font"); pg.wait_for_timeout(200)
            leaf = pg.evaluate("() => { const b = [...document.querySelectorAll('.q393-leaf')].filter(b => !b.parentNode.hidden && !b.closest('.q393-t').hidden)[0]; b.click(); return b.textContent; }")
            try:      # the mark goes on once the panel has opened (a busy software-GL frame can delay the timer)
                pg.wait_for_function("() => document.getElementById('lab-font').classList.contains('q393-flash') || (document.activeElement || {}).id === 'lab-font'", timeout=4000)
            except Exception:
                pass
            g = pg.evaluate("() => ({leaf: '', lab: !document.getElementById('lab-panel').hidden, flash: document.getElementById('lab-font').classList.contains('q393-flash'), focus: (document.activeElement || {}).id, set: document.getElementById('q382-panel').hidden})")
            g["leaf"] = leaf
            say(g["lab"] and (g["flash"] or g["focus"] == "lab-font") and g["set"], "a leaf goes to its real control (Label font size: the labels panel opens, the slider is marked)  %s" % json.dumps(g))
            pg.evaluate(CLOSE_ALL); pg.wait_for_timeout(400)
            ways = pg.evaluate("""() => { try { NMSKInfo.open('settings'); } catch (e) {} const r = {view: (NMSKGroups.members('view') || []).map(m => m.label).filter(Boolean), i: !!document.getElementById('q393-open-find') && !!document.getElementById('q382-open')}; try { NMSKInfo.close(); } catch (e) {} return r; }""")
            say("Settings" in ways["view"] and "Search settings" in ways["view"] and ways["i"], "two ways in: Settings (tree) and Search settings, in Navigate and in the circled i  %s" % json.dumps(ways))
            pg.evaluate("() => NMSKLayout.find('nerve')"); pg.wait_for_timeout(300)
            say(pg.evaluate("() => document.activeElement && document.activeElement.id === 'q393-sq' && !document.getElementById('q382-panel').hidden"), "Search settings puts the cursor in the settings search")
            rm = pg.evaluate(ROOM); shot(pg, "2_settings_open")
            if phone:
                sp = [p for p in rm["ps"] if p["s"] == "#q382-panel"]
                say(sp and sp[0]["t"] >= h * 0.55 - 2, "phone: Settings is a bottom sheet of <= 45 %%  %s" % sp)
            else:
                say(rm["free"] >= 0.6 * w, "desktop: with Settings open the figure keeps %d px (>= %d)" % (rm["free"], 0.6 * w))
            pg.evaluate(CLOSE_ALL); pg.wait_for_timeout(500)

            # ---------------------------------------------------------------- 5. the figure keeps the screen, per group / panel
            ENTRIES = [("mark", "Search"), ("systems", "Systems"), ("cut", "Dissection"), ("imaging", "Imaging"), ("pose", "Pose"), ("measure", "Measure"),
                       ("needle", "Needle"), ("favorites", "Favorites"), ("labels", "Labels"), ("@settings", "Settings")]
            for key, name in ENTRIES:
                pg.evaluate(CLOSE_ALL); pg.wait_for_timeout(500)
                if key == "@settings": pg.evaluate("() => NMSKLayout.open()")
                else:
                    if not pg.evaluate("(k) => { const b = document.getElementById('qg-' + k); if (!b || b.hidden) return false; b.click(); return true; }", key):
                        print("  --   %s: not on this page" % name); continue
                pg.wait_for_timeout(1600)
                rm = pg.evaluate(ROOM); shot(pg, "5_" + name)
                if not rm["ps"]:
                    say(True, "%s: nothing opened over the figure" % name); continue
                if phone:
                    low = [p for p in rm["ps"] if (p["t"] + p["b"]) / 2 > h * 0.5 and p["r"] - p["l"] >= w * 0.6]
                    hi = max([h - p["t"] for p in low] or [0])
                    say(hi <= h * 0.45 + 4 and rm["free"] >= h * 0.4, "%s (phone): bottom sheet %d px (<= %d), figure area %d px above it  %s" % (name, hi, h * 0.45, rm["free"], [p["s"] for p in rm["ps"]]))
                else:
                    cross = [p["s"] for p in rm["ps"] if p["l"] < w * 0.38 and p["r"] > w * 0.62 and p["b"] - p["t"] > h * 0.18 and p["t"] < h * 0.7]
                    say(rm["free"] >= 0.6 * w - 1 and not cross, "%s: the figure keeps %d px of %d (>= 60 %%), no panel across the centre %s  %s" % (name, rm["free"], w, cross, [p["s"] for p in rm["ps"]]))
                    if ("lay-model" in rm["lay"] or "lay-split" in rm["lay"]) and rm["box"] and box0:
                        fc = (rm["span"][0] + rm["span"][1]) / 2; bc = (rm["box"]["l"] + rm["box"]["r"]) / 2; bc0 = (box0["l"] + box0["r"]) / 2
                        say(abs((bc - fc) - (bc0 - w / 2)) <= 0.08 * rm["free"] + 4, "%s: the figure moves into the free part (offset from its centre %d px, was %d px from the screen's)" % (name, bc - fc, bc0 - w / 2))
            pg.evaluate(CLOSE_ALL); pg.wait_for_timeout(700)
            r1 = pg.evaluate(ROOM)
            say(r1["cv"]["l"] <= 1 and r1["cv"]["r"] >= w - 1 and r1["cv"]["t"] <= 1, "all closed: the canvas is the whole screen again  %s" % json.dumps(r1["cv"]))
            # Search + Labels together (the owner's case)
            pg.click("#qg-mark"); pg.wait_for_timeout(600); pg.click("#qg-labels"); pg.wait_for_timeout(1200)
            pg.click("#qg-mark") if pg.evaluate("() => NMSKGroups.isOpen() !== 'mark'") else None
            pg.wait_for_timeout(900)
            rm = pg.evaluate(ROOM); shot(pg, "5_search_and_labels")
            if not phone:
                say(rm["free"] >= 0.6 * w - 1, "Search and Labels open together: the figure keeps %d px (>= %d)  %s" % (rm["free"], 0.6 * w, [(p["s"], round(p["l"]), round(p["r"])) for p in rm["ps"]]))
            # a box the user resized keeps its size
            wb = pg.evaluate("() => { const p = document.getElementById('lab-panel'); if (p.hidden) return null; p.style.width = '300px'; return p.getBoundingClientRect().width; }")
            pg.wait_for_timeout(1200)
            wa = pg.evaluate("() => { const p = document.getElementById('lab-panel'); return p.hidden ? null : p.getBoundingClientRect().width; }")
            if wb is not None and not phone:
                say(abs(wa - wb) < 1, "a panel's own size is never changed by the room-keeping (%s -> %s)" % (wb, wa))
            pg.evaluate(CLOSE_ALL); pg.wait_for_timeout(600)

            # ---------------------------------------------------------------- 3. the add-on panels: titled sections, notes folded
            if pg.evaluate("() => !!document.getElementById('t-needle')"):
                pg.evaluate("() => document.getElementById('t-needle').click()"); pg.wait_for_timeout(1500)
                ac = pg.evaluate("""() => { const P = document.getElementById('needle-panel'), A = [...P.querySelectorAll('details.q393-acc')];
                  const vis = e => { for (let x = e; x && x !== P; x = x.parentNode) if (x.tagName === 'DETAILS' && !x.open && !(x === e)) return false; return true; };
                  const cites = [...P.querySelectorAll('p.cite, .q393-one')].filter(p => vis(p) && !p.closest('details:not([open])')).map(p => p.textContent.length);
                  return {n: A.length, titles: A.map(d => d.querySelector('summary').textContent.trim()), open: A.filter(d => d.open).length, disc: (P.querySelector('.ncl-disc') || {}).textContent || '',
                          long: cites.filter(n => n > 170).length, more: P.querySelectorAll('details.q393-more').length}; }""")
                say(ac["n"] >= 6 and ac["open"] <= 1, "needle panel: %d titled sections, %d open  %s" % (ac["n"], ac["open"], ac["titles"]))
                say(ac["long"] == 0 and ac["more"] >= 3, "needle panel: long notes folded to one line (%d still long, %d under More)" % (ac["long"], ac["more"]))
                say("not clinical guidance" in ac["disc"], "needle panel: the limits line stays on top (%r)" % ac["disc"])
                one = pg.evaluate("""() => { const A = [...document.querySelectorAll('#needle-panel details.q393-acc')]; A[0].open = true;
                  return new Promise(r => setTimeout(() => { A[1].open = true; setTimeout(() => r({a0: A[0].open, a1: A[1].open, n: A.filter(d => d.open).length, kept: localStorage.getItem('nmsk.q393.acc.needle')}), 200); }, 200)); }""")
                say(not one["a0"] and one["a1"] and one["n"] == 1 and one["kept"], "needle panel: one section at a time, the open one remembered  %s" % json.dumps(one))
                shot(pg, "3_needle_panel")
                pg.evaluate("() => document.getElementById('ncl-close').click()"); pg.wait_for_timeout(800)
            for k, (rx, root, need) in enumerate(((r"ct|mri", "#img-root", 5), (r"^(?!.*(ct|mri)).*$", "#us-root", 6))):
                ok = pg.evaluate("(rx) => { const b = [...document.querySelectorAll('.q301-scan')].filter(b => new RegExp(rx, 'i').test(b.textContent.trim()))[0]; if (!b) return false; b.click(); return true; }", rx)
                if not ok:
                    print("  --   scan panel %s: no button on this page" % root); continue
                pg.wait_for_timeout(6000)
                ac = pg.evaluate("""(root) => { const P = document.querySelector(root); if (!P) return null; const A = [...P.querySelectorAll('details.q393-acc')];
                  const top = [...P.querySelectorAll('input[type=range], select, button')].filter(e => e.getClientRects().length && !e.closest('details.q393-acc')).length;
                  return {n: A.length, titles: A.map(d => d.querySelector('summary').textContent.trim()), open: A.filter(d => d.open).length, top: top}; }""", root)
                say(ac and ac["n"] >= need and ac["open"] <= 1 and ac["top"] >= 4, "%s: %d titled sections (%d open), %d controls always on top  %s" % (root, ac and ac["n"], ac and ac["open"], ac and ac["top"], ac and ac["titles"]))
                shot(pg, "3_scan%d" % k)
                pg.evaluate("(rx) => { const b = [...document.querySelectorAll('.q301-scan')].filter(b => new RegExp(rx, 'i').test(b.textContent.trim()))[0]; b.click(); }", rx)
                pg.wait_for_timeout(2500)
                c = pg.evaluate(CENTRE)
                say(not c["dom"] and not c["marks"] and not c["cut"], "after closing %s: no tool mark at the screen centre, the cut it made is gone  %s" % (root, json.dumps(c)))

            # ---------------------------------------------------------------- 4. nothing stays at the centre
            if pg.evaluate("() => !!(window.NMSKClinicalTool && document.getElementById('t-needle'))"):
                pg.evaluate(CLOSE_ALL); pg.wait_for_timeout(400)
                pg.evaluate("() => document.getElementById('t-needle').click()"); pg.wait_for_timeout(1500)
                pg.evaluate("() => NMSKClinicalTool.setMode('two')")
                bx = pg.evaluate("() => { const b = NMSKQuick.box(); return b ? {x: (b.l + b.r) / 2, y: b.t + (b.b - b.t) * 0.3} : null; }")
                if bx:
                    pg.mouse.click(bx["x"] - 6, bx["y"]); pg.wait_for_timeout(900); pg.mouse.click(bx["x"] + 6, bx["y"] + 10); pg.wait_for_timeout(1200)
                pl = pg.evaluate("() => { const T = NMSKClinicalTool; if (T.entry && T.target) T.addSavedPoint(); const z = document.getElementById('ncl-zoom'); if (z) z.click(); return {e: !!T.entry, t: !!T.target, saved: T.savedPts.length}; }")
                pg.wait_for_timeout(1200)
                pg.evaluate("() => document.getElementById('needle-clear').click()"); pg.wait_for_timeout(500)
                g1 = pg.evaluate("() => ({drawn: NMSKClinicalTool.ov.gate(), saved: NMSKClinicalTool.savedPts.length})")
                shot(pg, "4_needle_saved_open")
                pg.evaluate("() => document.getElementById('ncl-close').click()"); pg.wait_for_timeout(1500)
                c = pg.evaluate(CENTRE); shot(pg, "4_needle_closed")
                say(pl["saved"] >= 1 and g1["drawn"], "a saved needle point (zoomed to, then Clear) is drawn while the needle panel is open  %s %s" % (json.dumps(pl), json.dumps(g1)))
                say(not c["marks"] and not c["dom"], "the needle panel closed: none of its marks stays on the model (saved points kept: %d)  %s" % (pg.evaluate("() => NMSKClinicalTool.savedPts.length"), json.dumps(c)))
                pg.evaluate("() => NMSKClinicalTool.clearSavedPoints()")
            steps = [("needle on/off", "() => { document.getElementById('t-needle').click(); }", "() => { document.getElementById('ncl-close').click(); }"),
                     ("planning mode", "() => NMSKModes.enter('inj')", "() => NMSKModes.exit()"),
                     ("pose on/off", "() => document.getElementById('qg-pose').click()", "() => document.getElementById('qg-pose').click()")]
            for name, on, off in steps:
                try:
                    pg.evaluate(on); pg.wait_for_timeout(4000); pg.evaluate(off); pg.wait_for_timeout(2500)
                except Exception as e:
                    print("  --   %s: %s" % (name, str(e)[:80])); continue
                c = pg.evaluate(CENTRE)
                say(not c["dom"] and not (c["marks"] or []), "after %s: no tool mark at the screen centre  %s" % (name, json.dumps(c)))
            shot(pg, "4_after")
            say(not Q.V.ERRS, "no page errors %s" % Q.V.ERRS[:3])
        finally:
            b.close(); srv.terminate()
    shutil.rmtree(d, ignore_errors=True)
    print("Q393_UI_OK" if not bad else "Q393_UI_FAIL %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
