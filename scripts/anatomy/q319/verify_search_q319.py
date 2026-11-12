#!/usr/bin/env python3
"""Q319: the Search entry opens a search field in one press, finds what the owner listed, and recolours the selection.

Owner, Q318: "a search field that opens on a press of the icon [make sure there are organ names, synonyms such as peroneal /
fibular, functional groups and everything we discussed]. It also opens the option of changing the colour of the selected,
all of them or only from now on."

What this measures, in a real Chromium, on both engines (the Z page and the three.js page), at desktop and at phone width:

  1  one press of Search (DOM click on the group button) opens the sheet AND leaves the cursor in the real #search / #q;
     the field is on screen, inside the viewport, and typing into it filters the page's own list
  2  what the search finds (queries and the sets they return are printed): organ names, synonyms (peroneal / fibular must
     both reach the fibularis muscles), the functional group by its names, Latin names, abbreviations, Hebrew names.
     A name the data does not carry is reported as MISS, never padded with a made-up entry
  3  colour of the selected, measured on the drawn PIXELS of the canvas, not on a function call:
       "All selected"  recolours what is marked now; "From now on" colours only what is marked afterwards and leaves
       the earlier ones alone; Undo puts the colours back; "Own colour" puts the structure's colour back;
       the highlight wins over a user colour, and the X-ray / CT / MRI styles win over both

    python3 scripts/anatomy/q319/verify_search_q319.py [--no-patch] [build/q309/viewer_zan_atlas build/q309/viewer_m_hr]

A built page that predates the change is copied to /dev/shm and patched by the same string replacement the source edit makes
(the two sync fragments, then the two engines' colour glue); a page that already carries the change is used as it is.
"""
from __future__ import annotations

import importlib.util
import io
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import base64
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
THREE = "/tmp/three_x/package/build/three.min.js"
ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, p


def route(rq):
    u = rq.request.url
    if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
        rq.fulfill(body=open(THREE, "rb").read(), content_type="application/javascript")
    elif "fonts.g" in u:
        rq.abort()
    else:
        rq.continue_()


ERRS: list[str] = []


def check(label, cond):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label)
    if not ok:
        ERRS.append(label)
    return ok


# --------------------------------------------------------------------------------------------- the patched copy
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def patched_copy(src: Path, patch: bool) -> Path:
    """Copy the page dir to /dev/shm (sidecars symlinked, never copied) and apply the source edit by string replacement."""
    dst = Path("/dev/shm") / ("q319v_" + src.name)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for f in src.iterdir():
        if f.suffix == ".html":
            shutil.copy(f, dst / f.name)
        else:
            os.symlink(f.resolve(), dst / f.name)
    if not patch:
        return dst
    s227 = _load("s227", REPO / "scripts/sync_q227.py")
    s301 = _load("s301", REPO / "scripts/sync_q301.py")
    for f in dst.glob("atlas_viewer*.html"):
        t = f.read_text(encoding="utf-8")
        if "NMSKSelectCtl" in t:
            continue
        # 1. the shared selection controller (its own marker pair) and the top-row fragment
        sb, se = "/* SELECTION js begin */", "/* SELECTION js end */"
        frag = (REPO / "viewer/selection/selection.js").read_text(encoding="utf-8").rstrip("\n")
        i, j = t.index(sb) + len(sb), t.index(se)
        t = t[:i] + "\n" + frag + "\n" + t[j:]
        t = s301.render(t)
        # 2. the engines' colour glue
        a = '      if (selCtl && selCtl.look(o.id) === "hl") return hlCol(selCtl.hlHex());      // Q232: the selected group in a solid highlight colour\n'
        if a in t:
            t = t.replace(a, a + (
                '      var uh = selCtl && selCtl.userHex ? selCtl.userHex(o.id) : null;      // Q319\n'
                '      if (uh != null){ var uc = userCols.get(uh); if (!uc){ uc = [((uh >> 16) & 255) / 255, ((uh >> 8) & 255) / 255, (uh & 255) / 255]; userCols.set(uh, uc); } return uc; }\n'), 1)
            t = t.replace("    var markCols = new Map(), hlC = {h:-1, c:null};", "    var markCols = new Map(), userCols = new Map(), hlC = {h:-1, c:null};", 1)
        b = '    var mk = !!(selCtl && selCtl.tinted(s.id)), hlc = sr === "hl", bh = srcColour && SRC_BY[s.src] ? SRC_BY[s.src].hex : tis.hex;\n'
        if b in t:
            t = t.replace(b, b + '    var uh = selCtl && selCtl.userHex ? selCtl.userHex(s.id) : null;      // Q319\n    if (uh != null) bh = uh;\n', 1)
        f.write_text(t, encoding="utf-8")
    return dst


# --------------------------------------------------------------------------------------------------- page helpers
def open_page(pl, d: Path, w: int, h: int):
    srv, port = serve(d)
    b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": w, "height": h})
    pg.on("pageerror", lambda e: ERRS.append("page error: " + str(e)))
    pg.route("**/*", route)
    html = sorted(d.glob("atlas_viewer*.html"))[0]
    pg.goto(f"http://127.0.0.1:{port}/{html.name}", wait_until="load", timeout=90000)
    pg.wait_for_function("window.NMSKQ301 && window.NMSKQ298 && window.NMSKSelectCtl", timeout=90000)
    try:
        pg.wait_for_selector('.mw-tile[data-mode="anat"]', timeout=120000)
        pg.click('.mw-tile[data-mode="anat"]'); pg.wait_for_timeout(3000)
    except Exception:
        print("     (no mode wall to dismiss)")
    return srv, b, pg


def press(pg, sel):
    return pg.evaluate("(s) => { const e = document.querySelector(s); if (!e) return false; e.click(); return true; }", sel)


def fg_colour(pg, clip=None):
    """Mean RGB of the pixels that are not the background, over the middle of the canvas, from a real screenshot."""
    r = pg.evaluate("""() => { let best = null;
      document.querySelectorAll('canvas').forEach(c => { const q = c.getBoundingClientRect();
        if (q.width > 200 && q.height > 200 && (!best || q.width * q.height > best.w * best.h)) best = {x: q.left, y: q.top, w: q.width, h: q.height}; });
      return best; }""")
    x, y, w, h = r["x"], r["y"], r["w"], r["h"]
    clip = {"x": x + w * 0.28, "y": y + h * 0.34, "width": w * 0.44, "height": h * 0.58}
    png = pg.screenshot(clip=clip)
    # decoded and counted inside the browser itself (no imaging library needed)
    r = pg.evaluate("""async (b64) => {
      const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode();
      const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
      const x = c.getContext('2d'); x.drawImage(img, 0, 0); const d = x.getImageData(0, 0, c.width, c.height).data;
      // the drawn structures are the CHROMATIC pixels (max - min of the channels > 30): the page's own backdrop is a near-grey
      let sr = 0, sg = 0, sb = 0, n = 0;
      for (let i = 0; i < d.length; i += 4){ const mx = Math.max(d[i], d[i+1], d[i+2]), mn = Math.min(d[i], d[i+1], d[i+2]);
        if (mx - mn > 30){ sr += d[i]; sg += d[i+1]; sb += d[i+2]; n++; } }
      return n ? [sr / n, sg / n, sb / n, n] : [0, 0, 0, 0]; }""", base64.b64encode(png).decode())
    return tuple(r)


def same_hue(a, b, tol=0.035):
    """Two mean colours are 'the same colour' when their chromaticity (each channel's share of the sum) agrees: the amount of
    surface that is in view, and so the shading, varies a little between renders, the colour of what is drawn does not."""
    sa, sb = sum(a[:3]) or 1, sum(b[:3]) or 1
    return all(abs(a[i] / sa - b[i] / sb) < tol for i in range(3))


def fmt(c):
    return f"rgb({c[0]:.0f},{c[1]:.0f},{c[2]:.0f}) n={c[3]}"


# ------------------------------------------------------------------------------------------------------ the checks
QUERIES = """() => {
  const out = {};
  const qs = %s;
  for (const q of qs) {
    const ids = NMSKQ298.filter(q) || [];
    const r = NMSKQ298.result() || {};
    out[q] = {ids: ids, groups: (r.groups || []).map(g => g.name + ':' + g.ids.length), approx: !!r.approx};
  }
  return out;
}"""

FIB = r"^fibularis_(longus|brevis)_[lr]$"


def search_findings(pg, tag):
    import json, re
    qs = ["liver", "biceps brachii", "femur",                                            # organ / structure names
          "peroneal", "fibular", "peroneus longus", "fibularis longus", "peroneals",     # synonyms
          "lateral compartment of the leg", "hamstrings", "rotator cuff", "quadriceps femoris",   # functional groups
          "musculus biceps brachii", "tractus iliotibialis", "ligamentum collaterale fibulare",     # Latin
          "ITB", "CPN", "LCL",                                                           # abbreviations
          "המסטרינגס", "פרונאלים"]                                                       # Hebrew
    res = pg.evaluate(QUERIES % json.dumps(qs, ensure_ascii=False))
    rx = re.compile(FIB)
    for q in qs:
        r = res[q]
        top = ", ".join(r["ids"][:4])
        print(f"     [{tag}] {q!r:38} -> {len(r['ids']):3} hits  groups={r['groups']}  first: {top}")
    fibs = {q: sorted(i for i in res[q]["ids"] if rx.match(i)) for q in ("peroneal", "fibular", "peroneals")}
    on_page = sorted(i for i in res["peroneals"]["ids"] if rx.match(i))
    check(f"[{tag}] 'peroneal' finds the fibularis muscles ({fibs['peroneal']})", fibs["peroneal"] and fibs["peroneal"] == on_page)
    check(f"[{tag}] 'fibular' finds the SAME fibularis muscles", fibs["fibular"] == fibs["peroneal"])
    check(f"[{tag}] 'peroneal' and 'fibular' both offer the lateral-compartment functional group",
          any("Lateral compartment" in g for g in res["peroneal"]["groups"]) and any("Lateral compartment" in g for g in res["fibular"]["groups"]))
    check(f"[{tag}] 'peroneus longus' and 'fibularis longus' agree", res["peroneus longus"]["ids"][:2] == res["fibularis longus"]["ids"][:2] and res["fibularis longus"]["ids"])
    check(f"[{tag}] organ / structure names: liver, biceps brachii, femur", all(res[q]["ids"] for q in ("liver", "biceps brachii", "femur")))
    check(f"[{tag}] functional groups by their name: hamstrings, rotator cuff, quadriceps femoris",
          all(res[q]["groups"] for q in ("hamstrings", "rotator cuff", "quadriceps femoris")))
    check(f"[{tag}] Latin name 'musculus biceps brachii' finds the biceps", any(i.startswith("biceps_brachii") for i in res["musculus biceps brachii"]["ids"]))
    for q in ("tractus iliotibialis", "ligamentum collaterale fibulare", "ITB", "CPN", "LCL", "המסטרינגס", "פרונאלים"):
        n = len(res[q]["ids"]); g = res[q]["groups"]
        print(("  OK  " if n or g else "  MISS") + f" [{tag}] {q!r}: {n} structures, groups {g}" + ("" if n or g else "  (not findable on this page)"))


def search_ui(pg, tag, phone):
    r = pg.evaluate("""async () => {
      const sleep = ms => new Promise(r => setTimeout(r, ms));
      const g = document.getElementById('qg-mark');
      if (!g) return {err: 'no Search entry on the bar'};
      g.click();                                  // ONE press
      await sleep(500);
      const f = document.getElementById('search') || document.getElementById('q');
      const sh = document.getElementById('q301-sheet');
      const q = f.getBoundingClientRect(), s = sh.getBoundingClientRect();
      return {open: !sh.hidden, field: f.id, focused: document.activeElement === f,
              inSheet: sh.contains(f), onScreen: q.width > 120 && q.height > 20 && q.left >= 0 && q.right <= innerWidth + 1 && q.top >= 0 && q.bottom <= innerHeight,
              rect: [Math.round(q.left), Math.round(q.top), Math.round(q.width), Math.round(q.height)],
              sheet: [Math.round(s.left), Math.round(s.top), Math.round(s.width), Math.round(s.height)], vw: innerWidth, vh: innerHeight};
    }""")
    if r.get("err"):
        check(f"[{tag}] " + r["err"], False); return False
    print(f"     [{tag}] field #{r['field']} at {r['rect']}, sheet {r['sheet']}, viewport {r['vw']}x{r['vh']}")
    check(f"[{tag}] ONE press of Search opens the sheet", r["open"])
    check(f"[{tag}] the real search field is inside it, on screen and wide enough to type in", r["inSheet"] and r["onScreen"])
    check(f"[{tag}] and the cursor is already in it (document.activeElement)", r["focused"])
    pg.keyboard.type("peroneal", delay=30)
    pg.wait_for_timeout(700)
    rows = pg.evaluate("""() => { const l = document.getElementById('list'); const f = document.getElementById('search') || document.getElementById('q');
      const q = l.getBoundingClientRect();
      return {text: (l.innerText || '').toLowerCase().slice(0, 300), value: f.value, w: q.width, h: q.height, inSheet: document.getElementById('q301-sheet').contains(l)}; }""")
    check(f"[{tag}] typing reaches the engine's own list, which is in the sheet and on screen (value {rows['value']!r})",
          rows["value"] == "peroneal" and rows["inSheet"] and rows["h"] > 20 and "fibul" in rows["text"])
    if phone:
        c = pg.evaluate("""async () => {
          const e = document.querySelector('#ss-col .ss-col-s'); e.scrollIntoView({block: 'center'});
          await new Promise(r => setTimeout(r, 200));
          const q = e.getBoundingClientRect(); return {inView: q.top >= 0 && q.bottom <= innerHeight && q.left >= 0 && q.right <= innerWidth, w: q.width}; }""")
        check(f"[{tag}] phone width: the colour swatches can be scrolled to and are big enough to tap ({c['w']:.0f}px)", c["inView"] and c["w"] >= 30)
    press(pg, "#qg-close")
    return True


def colour_tests(pg, tag):
    """Measured on pixels. The marked set is isolated (Only marked) so what is drawn IS the marked set."""
    J = lambda js, *a: pg.evaluate(js, *a)
    J("() => { const f = document.getElementById('search') || document.getElementById('q'); f.value = ''; f.dispatchEvent(new Event('input')); }")
    ids = J("() => NMSKQ298.filter('hamstrings') || []")
    biceps = J("() => NMSKQ298.filter('biceps brachii') || []")
    femur = J("() => NMSKQ298.filter('quadriceps femoris') || []")
    check(f"[{tag}] test sets exist (hamstrings {len(ids)}, biceps {len(biceps)}, quadriceps {len(femur)})", ids and biceps and femur)
    J("(ids) => { NMSKSelectCtl.markIds(ids, true, true); NMSKSelectCtl.setMode('only'); }", ids)
    pg.wait_for_timeout(4000)           # let the geometry chunks finish loading before anything is measured
    base = fg_colour(pg)
    print(f"     [{tag}] marked + isolated, own colour with the amber mark tint: {fmt(base)}")
    check(f"[{tag}] something is drawn to measure", base[3] > 300)

    def open_search():
        if not J("() => { const s = document.getElementById('q301-sheet'); return !!(s && !s.hidden); }"):
            press(pg, "#qg-mark")
        pg.wait_for_timeout(1000)          # the page-wide history settles one user action at a time: let the opening press commit on its own

    def pick(mode, hexv):
        open_search()
        press(pg, "#ss-col-" + mode)
        if hexv is None:
            press(pg, "#ss-col-own")
        else:
            press(pg, f'#ss-col .ss-col-s[data-hex="{hexv}"]')
        pg.wait_for_timeout(900)

    def close():
        press(pg, "#qg-close"); pg.wait_for_timeout(500)

    st = lambda: J("() => NMSKSelectCtl.colourState()")
    BLUE, GREEN, RED, ORANGE = "#3f7fd6", "#4ca65a", "#d64545", "#e8892b"

    # ---- All selected
    pick("all", BLUE); close()
    s = st(); c1 = fg_colour(pg)
    print(f"     [{tag}] All selected -> blue: {fmt(c1)}; state own={s['own']}")
    check(f"[{tag}] 'All selected' recolours every marked structure ({s['own']} of {len(ids)})", s["own"] == len(ids))
    check(f"[{tag}] and the DRAWN pixels turn blue (b {c1[2]:.0f} > r {c1[0]:.0f}, and not what they were)", c1[2] > c1[0] + 12 and not same_hue(c1, base))

    # ---- Undo: a colour change is one history step
    pg.wait_for_timeout(900)
    pick("all", ORANGE); close()
    c2 = fg_colour(pg)
    check(f"[{tag}] a second colour replaces the first (orange: r {c2[0]:.0f} > b {c2[2]:.0f})", c2[0] > c2[2] + 25)
    pg.wait_for_timeout(900)
    press(pg, "#q301-undo"); pg.wait_for_timeout(1000)
    s = st(); c3 = fg_colour(pg)
    print(f"     [{tag}] Undo once: {fmt(c3)}; colours {set(s['ids'].values())}")
    check(f"[{tag}] Undo puts the previous colour back (state AND pixels blue again)", set(s["ids"].values()) == {BLUE} and c3[2] > c3[0] + 12)
    press(pg, "#q301-undo"); pg.wait_for_timeout(1000)
    s = st(); c4 = fg_colour(pg)
    print(f"     [{tag}] Undo twice: {fmt(c4)} (start was {fmt(base)}), recoloured {s['own']}, mode {J('() => NMSKSelectCtl.state().mode')}")
    check(f"[{tag}] Undo again puts back the structures' own colours ({s['own']} recoloured, pixels near the start)", s["own"] == 0 and same_hue(c4, base))
    press(pg, "#q301-redo"); pg.wait_for_timeout(1000)
    check(f"[{tag}] Redo brings the blue back", st()["own"] == len(ids))

    # ---- highlight and the radiographic styles win
    J("() => NMSKSelectCtl.preset('hlsel')"); pg.wait_for_timeout(900)
    ch = fg_colour(pg)
    check(f"[{tag}] the highlight wins over a user colour (amber-ish: r {ch[0]:.0f} > b {ch[2]:.0f})", ch[0] > ch[2] + 40)
    J("() => { NMSKSelectCtl.preset('hlsel'); NMSKSelectCtl.setMode('only'); }"); pg.wait_for_timeout(900)      # off again, and back to showing only the marked
    for style in ("ct", "xray", "mri"):
        J("(m) => NMSKRenderStyle.set(m)", style); pg.wait_for_timeout(1500)
        cs = fg_colour(pg)
        print(f"     [{tag}] {style} with a user colour set: {cs[3]:.0f} chromatic pixels (the blue case had {c1[3]:.0f})")
        check(f"[{tag}] {style} style stays grey under a user colour ({cs[3]:.0f} chromatic pixels, was {c1[3]:.0f})", cs[3] < 0.02 * c1[3])
    J("() => NMSKRenderStyle.toColour()"); pg.wait_for_timeout(1500)
    cb = fg_colour(pg)
    check(f"[{tag}] back to colour: the user colour is there again", cb[2] > cb[0] + 12)

    # ---- Own colour
    J("() => { if (NMSKSelectCtl.state().mode !== 'only') NMSKSelectCtl.setMode('only'); }")
    pick("all", None); close()
    c5 = fg_colour(pg)
    print(f"     [{tag}] Own colour: {fmt(c5)} (start {fmt(base)}), recoloured {st()['own']}")
    check(f"[{tag}] 'Own colour' puts the structures' own colour back", st()["own"] == 0 and same_hue(c5, base))

    # ---- From now on
    J("() => { NMSKSelectCtl.clear(); }"); pg.wait_for_timeout(500)
    pick("next", GREEN); close()
    s0 = st()
    check(f"[{tag}] 'From now on' colours nothing that is marked already (own {s0['own']}, next {s0['next']})", s0["own"] == 0 and s0["next"] == GREEN)
    J("(ids) => { NMSKSelectCtl.markIds(ids, true, true); NMSKSelectCtl.setMode('only'); }", ids); pg.wait_for_timeout(900)
    s1 = st(); c6 = fg_colour(pg)
    print(f"     [{tag}] marked after 'from now on' green: {fmt(c6)}; own={s1['own']}")
    check(f"[{tag}] structures marked afterwards get it ({s1['own']} of {len(ids)}), in state and in pixels (g {c6[1]:.0f} > r {c6[0]:.0f})",
          s1["own"] == len(ids) and c6[1] > c6[0] + 10)
    pick("next", RED); close()
    J("(ids) => { NMSKSelectCtl.markIds(ids, true, false); }", femur); pg.wait_for_timeout(900)
    s2 = st()
    olds = {s2["ids"].get(i) for i in ids}
    news = {s2["ids"].get(i) for i in femur if i not in ids}
    check(f"[{tag}] changing it again leaves the earlier ones green ({olds}) and gives the new ones red ({news})", olds == {GREEN} and news == {RED})
    pg.wait_for_timeout(900)
    press(pg, "#q301-undo"); pg.wait_for_timeout(1000)
    s3 = st()
    check(f"[{tag}] Undo takes the last marks (and their colour) back together", not any(i in s3["ids"] for i in femur if i not in ids) and s3["next"] in (RED, GREEN))
    pg.wait_for_timeout(900)
    press(pg, "#q301-undo"); pg.wait_for_timeout(1000)
    press(pg, "#q301-undo"); pg.wait_for_timeout(1000)
    s4 = st()
    print(f"     [{tag}] after more Undo: next={s4['next']} own={s4['own']}")
    check(f"[{tag}] Undo walks the 'from now on' colour back as well (next is {s4['next']})", s4["next"] != RED)
    J("() => { NMSKSelectCtl.reset(); }")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    patch = "--no-patch" not in sys.argv
    pages = [Path(a) for a in args] or [REPO / "build/q309/viewer_zan_atlas", REPO / "build/q309/viewer_m_hr"]
    with sync_playwright() as pl:
        for src in pages:
            src = src if src.is_absolute() else REPO / src
            d = patched_copy(src, patch)
            for (w, h, phone) in ((1400, 900, False), (390, 800, True)):
                tag = f"{src.name} {'phone' if phone else 'desktop'}"
                print(f"=== {tag} ===")
                srv, b, pg = open_page(pl, d, w, h)
                try:
                    if search_ui(pg, tag, phone):
                        if not phone:
                            search_findings(pg, src.name)
                            colour_tests(pg, tag)
                finally:
                    b.close(); srv.kill()
    print("\nQ319_SEARCH_OK" if not ERRS else "\nQ319_SEARCH_FAIL: " + "; ".join(ERRS[:12]))
    return 1 if ERRS else 0


if __name__ == "__main__":
    sys.exit(main())
