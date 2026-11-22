#!/usr/bin/env python3
"""Q300: real headless-Chromium check (desktop 1400x900 real clicks + phone 390x844 real touch) of this round's three claims.

A  ISOLATE AND BACK. The exact state before isolating is captured from the history's own snapshot; a structure is then
   isolated through the real UI; a persistent chip must name it; ONE real tap on that chip's x (and, separately, Escape
   on desktop) must bring back a snapshot that is byte-identical to the captured one -- and ONE Ctrl+Z must then put the
   isolated state back, i.e. the whole isolate-and-return is a single undo step in each direction.
B  NO DEAD END. Every hiding path the page registers with NMSKShowAll is driven into its active state one at a time;
   each must raise a chip of its own AND the "Show everything" button, and one real tap on that button must leave
   NMSKShowAll.active() false. A path with no visible way out fails here.
C  MODEL RESET. Several real changes are made (layers, a mark, isolation, a cut, the camera); one real tap on the model
   reset must return a snapshot equal to the one taken at load, and one Ctrl+Z must bring the changed state back.
D  THE SKELETON MUST READ. Measured, not eyeballed: a bone mask is taken from the page itself (bone-only state), then the
   rendered canvas is sampled in X-ray and in Fade with the bone-through pass Off / Clear / Strong. The figure reported is
   the Michelson contrast between the mean luminance of the bone pixels and of a ring of tissue-only pixels around them.
   The pre-Q300 look is measured too, by toggling the old alphas and the old flat fade back on, so the before and the
   after are read off the SAME page, camera and regions -- the only difference is what this round changed.

    python3 scripts/anatomy/q300/verify_q300.py PAGE_DIR... [--min-contrast=0.12]

Software rendering is slow: every wait here is generous. Never run this during a regen."""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap, serve, route, html_of = V.check, V.tap, V.serve, V.route, V.html_of
KEY = {"viewer_zan_atlas": "base_m", "viewer_base_female": "base_f", "viewer_zan_vhm": "comb_m",
       "viewer_zan_female": "comb_f", "viewer_m_hr": "own_m", "viewer_f_hr": "own_f"}
OWN = ("viewer_m_hr", "viewer_f_hr")
MIN_CONTRAST = 0.12


# ---------------------------------------------------------------- page helpers

def ready(pg):
    pg.wait_for_function("document.readyState === 'complete'", timeout=90000)
    pg.wait_for_function("window.NMSKClinicalTool && window.NMSKClinicalTool.api", timeout=180000)
    pg.wait_for_function("window.NMSKHistory && window.NMSKHistory.active()", timeout=180000)
    # The pose rig loads asynchronously and registers a history provider once it is ready, so a snapshot taken before
    # that is missing a key and can never be compared with one taken after -- which is exactly how A and C first failed.
    # Wait for the rig (or for the page to say it has no rig) before anything reads a snapshot.
    pg.wait_for_function("() => { const p = window.__poseApi; return !p || p.failed() || p.ready(); }", timeout=300000)
    pg.wait_for_function("() => { const p = window.__poseApi;"
                         " return !p || p.failed() || window.NMSKHistory.keys().indexOf('pose') >= 0; }", timeout=60000)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(800)
    # dismiss the welcome / pose banners with an in-page click: a real click here can hang on the Z pages (the
    # element reports itself actionable and the click never completes), and none of this round's claims depend on
    # these two buttons being pressed for real.
    for sel in ("#mw-close", "#pose-banner-close"):
        try:
            pg.evaluate("(s) => { const e = document.querySelector(s); if (e && e.offsetParent !== null) e.click(); }", sel)
        except Exception:
            pass
    pg.wait_for_timeout(300)


def snap(pg):
    return pg.evaluate("() => JSON.stringify(window.NMSKHistory.snapshot())")


def settle(pg, ms=900):
    pg.evaluate("() => { if (window.NMSKHistory) NMSKHistory.commit(); }")
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(ms)


def chips(pg):
    return pg.evaluate("() => window.NMSKShowAll ? NMSKShowAll.chips() : []")


def a_structure(pg, own, want="femur"):
    """an id on this page whose name contains `want` (a bone, so the x-ray / fade test has something to look for)"""
    return pg.evaluate(
        "(w) => { const L = window.NMSKClinicalTool.api.list();"
        " const hit = L.filter(m => (m.id + ' ' + (m.name || '')).toLowerCase().indexOf(w) >= 0);"
        " return (hit[0] || L[0] || {}).id || null; }", want)


def pick(pg, sid):
    """select the structure. Done BEFORE the "before" snapshot is taken: the selection is part of the page's state,
    and isolate/exit must be judged on the round trip alone, not on the selection that preceded it."""
    pg.evaluate("(id) => window.__q300dbg.pick(id)", sid)
    pg.wait_for_timeout(600)


def isolate_via_ui(pg, own, sid, phone):
    """isolate through the real controls: the own pages have an Isolate button, the Z pages isolate around the
    selection with their own `i` key (its panel button is folded away -- the defect this round fixes)."""
    if own:
        if pg.is_visible("#t-iso"):
            tap(pg, "#t-iso", phone); return "iso"
        return None
    pg.keyboard.press("i")            # the Z engine's own "isolate around the selection" key (its panel button may be folded away)
    pg.wait_for_timeout(900)
    return "box" if pg.evaluate("() => NMSKShowAll.chips().some(c => c.key === 'box')") else None


# ---------------------------------------------------------------- D: the measurement
# A screenshot of a WebGL canvas is NOT usable here: measured in this container, page.screenshot() returned a frame that
# stayed byte-identical while the engine's own camera kept advancing, i.e. the compositor hands back a stale frame under
# software rendering. So the pixels are read inside the page, from the engine's own GL context, right after a synchronous
# draw -- window.__q300px(step), which returns the frame as a downsampled grid of luminance.

def grid(pg, step=8):
    g = pg.evaluate("(s) => window.__q300px(s)", step)
    return np.array(g["luma"], dtype=np.float64).reshape(g["h"], g["w"])


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r:
                continue
            out |= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
    return out


def freeze(pg):
    """stop every auto-rotation first: the Z pages spin by default, so two frames of different states would not line up"""
    pg.evaluate("""() => {
        const b = document.getElementById('btn-spin');
        if (b && b.classList.contains('on')) b.click();
        const t = document.getElementById('t-spin');
        if (t && t.getAttribute('aria-pressed') === 'true') t.click();
    }""")
    settle(pg, 600)


def js_click(pg, ident):
    """for the page's own presets, which may sit in a collapsed panel: this sets up a measurement, it is not the
    reachability check -- the controls THIS round adds are tapped for real in A, B and C."""
    return pg.evaluate("(i) => { const e = document.getElementById(i); if (!e) return false; e.click(); return true; }", ident)


def regions(pg, own):
    """bone pixels, and soft-tissue pixels that are inside the body but not over bone -- taken from the page's own
    two states (everything shown, bone only), so no region is assumed"""
    if own:
        pg.evaluate("() => window.__q300dbg.allOn()")
    else:
        js_click(pg, "btn-solid")
    settle(pg, 1800)
    solid = grid(pg)
    bg = float(np.median(np.concatenate([solid[0, :], solid[-1, :], solid[:, 0], solid[:, -1]])))
    body = np.abs(solid - bg) > 8.0
    if own:
        pg.evaluate("() => window.__q300dbg.onlyBone()")
    else:
        js_click(pg, "btn-bones")
    settle(pg, 1800)
    bone = np.abs(grid(pg) - bg) > 8.0
    core = bone & ~dilate(~bone, 1)
    tissue = body & ~dilate(bone, 2)
    return core, tissue, bg


def contrast(pg, core, tissue):
    g = grid(pg)
    if core.sum() < 20 or tissue.sum() < 20:
        return None, int(core.sum()), int(tissue.sum())
    a, b = float(g[core].mean()), float(g[tissue].mean())
    return abs(a - b) / max(1e-6, a + b), round(a, 1), round(b, 1)


def set_bone(pg, level):
    pg.evaluate("(i) => { if (window.NMSKBoneRead) NMSKBoneRead.set(i); }", level)
    settle(pg, 1400)


def xray_on(pg, own, phone):
    """the real control on the own pages; the Z preset button may be inside a collapsed panel, so it is clicked in page"""
    if own:
        if not pg.is_visible("#t-xray"):
            return False
        tap(pg, "#t-xray", phone)
    elif not js_click(pg, "btn-xray"):
        return False
    settle(pg, 1800)
    return True


def group(pg, state):
    pg.evaluate("(s) => { const e = document.querySelector('#sel-sec .ss-st[data-g=\"oth\"][data-s=\"' + s + '\"]');"
                " if (e) e.click(); }", state)
    settle(pg, 1600)
    return pg.evaluate("(s) => { const q = window.__q300dbg.sel(); const st = q && q.state(); return !!st && st.oth === s; }", state)


def fade_on(pg, own, sid, phone):
    """Mark one structure, then put all the OTHERS into Fade -- the state the owner calls the "fade view".
    Returns the marked structure's own footprint so the caller can keep it OUT of the bone region: a marked
    structure is drawn solid, and if it overlaps the skeleton's silhouette (a gluteus over the pelvis does) it
    would be measured as if it were bone. Taken from the page's own "others hidden" state, nothing assumed."""
    ok = pg.evaluate("(id) => { const s = window.__q300dbg && window.__q300dbg.sel(); if (!s || !s.markIds) return false;"
                     " s.markIds([id], true); return true; }", sid)
    if not ok:
        return False, None
    pg.wait_for_timeout(500)
    mark = None
    if group(pg, "hide"):                       # only the marked structure is drawn: that is its footprint
        g = grid(pg)
        bg = float(np.median(np.concatenate([g[0, :], g[-1, :], g[:, 0], g[:, -1]])))
        mark = np.abs(g - bg) > 8.0
    if not group(pg, "fade"):
        return False, None
    return True, mark


def measure_modes(pg, own, phone, tag, errs, min_c):
    """X-ray and Fade, each measured four ways on the SAME page, camera and regions:
         legacy  the pre-Q300 look (the old per-class alphas, the old flat fade, no bone pass)
         off     this round's per-class alphas / fade floor, bone pass off
         clear   + bone pass 0.45 (the default)
         strong  + bone pass 0.80
       Measuring "before" by toggling the old behaviour back on beats measuring a different build: the bone and
       soft-tissue regions, the camera and the frame are then identical, so the difference is only what changed."""
    out = {}
    freeze(pg)
    core, tissue, bg = regions(pg, own)
    check(f"{tag}: D bone and soft-tissue regions are real ({int(core.sum())} / {int(tissue.sum())} cells, bg {bg:.0f})",
          core.sum() >= 20 and tissue.sum() >= 20, errs)
    if core.sum() < 20 or tissue.sum() < 20:
        return out
    core0 = core
    for mode in ("xray", "fade"):
        core = core0
        reset_all(pg, own)
        if mode == "xray":
            if not xray_on(pg, own, phone):
                check(f"{tag}: D the x-ray control is reachable", False, errs); continue
        else:
            sid = a_structure(pg, own, "gluteus")
            ok, mark = fade_on(pg, own, sid, phone)
            if not ok:
                check(f"{tag}: D the fade view is reachable", False, errs); continue
            if mark is not None and mark.shape == core.shape:
                keep = core & ~dilate(mark, 1)
                if keep.sum() >= 20:
                    core = keep
                    print(f"    {tag} fade: the marked structure covers part of the skeleton -- bone cells {int(keep.sum())} after excluding it")
        row = {}
        for word, legacy, lvl in (("legacy", True, 0), ("off", False, 0), ("clear", False, 1), ("strong", False, 2)):
            pg.evaluate("(v) => window.__q300dbg.legacy(v)", legacy)
            set_bone(pg, lvl)
            c, a, b = contrast(pg, core, tissue)
            row[word] = None if c is None else round(c, 4)
            print(f"    {tag} {mode:5s} {word:6s} contrast={row[word]}  (bone luma {a}, tissue luma {b})")
        pg.evaluate("() => window.__q300dbg.legacy(false)")
        out[mode] = row
        L, O = row.get("legacy"), row.get("off")
        if L is not None and O is not None:
            # what this round claims: with the per-class table and the fade floor, bone reads clearly -- and it is
            # never worse than before. The extra pass is a control the user reaches for, not the claim, so it is
            # asserted only to never make bone unreadable.
            check(f"{tag}: D {mode} bone reads clearly after: {O} >= {min_c}", O >= min_c, errs)
            check(f"{tag}: D {mode} this round did not make it worse ({L} -> {O})", O >= L - 0.003, errs)
            check(f"{tag}: D {mode} either improved materially or was already clear ({L} -> {O})",
                  O > L + 0.02 or L >= min_c, errs)
            weak = [w for w in ("clear", "strong") if row.get(w) is not None and row[w] < min_c]
            check(f"{tag}: D {mode} no bone-through step makes bone unreadable (weak: {weak})", not weak, errs)
        reset_all(pg, own)
    return out


def reset_all(pg, own):
    done = pg.evaluate("() => { if (window.NMSKModelReset && NMSKModelReset.state().on){ NMSKModelReset.run(); return true; } return false; }")
    if not done:
        if own:
            pg.evaluate("() => window.__q300dbg && window.__q300dbg.allOn()")
        else:
            js_click(pg, "btn-solid")
            pg.evaluate("""() => { const e = document.querySelector('#sel-sec .ss-st[data-g="oth"][data-s="show"]');
                                   if (e) e.click(); }""")
    settle(pg, 1600)


# ---------------------------------------------------------------- the run

def run_page(page_dir: Path, tag: str, errs: list, min_c):
    name = page_dir.name
    own = name in OWN
    html = html_of(page_dir)
    srv, port = serve(page_dir)
    res = {}
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in (((1400, 900), False), ((390, 844), True)):
                T = f"{tag}_{w}"
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page()
                perrs = []
                pg.on("pageerror", lambda e: perrs.append(str(e)))
                pg.route("**/*", route)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=120000)
                ready(pg)
                has = pg.evaluate("() => !!window.NMSKShowAll && !!window.NMSKModelReset && !!window.NMSKBoneRead && !!window.__q300px")
                check(f"{T}: Q300 modules are on the page", has, errs)
                if not has:
                    ctx.close(); continue

                # ---- A isolate and back
                sid = a_structure(pg, own, "femur")
                pick(pg, sid)
                settle(pg)
                s0 = snap(pg)
                check(f"{T}: A nothing is flagged as hidden on a page nobody has touched ({chips(pg)})",
                      not pg.evaluate("() => NMSKShowAll.active()"), errs)
                kind = isolate_via_ui(pg, own, sid, phone)
                settle(pg)
                check(f"{T}: A a structure could be isolated through the real UI ({kind})", bool(kind), errs)
                ch = chips(pg)
                check(f"{T}: A a chip names what is isolated ({[c['label'] for c in ch]})",
                      any(c["key"] in ("iso", "box") for c in ch), errs)
                check(f"{T}: A the 'Show everything' button is visible", pg.is_visible("#sa-all"), errs)
                s1 = snap(pg)
                check(f"{T}: A isolating really changed the state", s1 != s0, errs)
                k = next((c["key"] for c in ch if c["key"] in ("iso", "box")), None)
                if k:
                    tap(pg, f'#sa-bar .sa-chip[data-sa="{k}"] .sa-x', phone)
                    settle(pg)
                    check(f"{T}: A one tap on the chip restored the EXACT prior state", snap(pg) == s0, errs)
                    pg.keyboard.press("Control+z")
                    settle(pg)
                    check(f"{T}: A one Ctrl+Z puts the isolated state back (single undo step)", snap(pg) == s1, errs)
                if not phone:
                    pg.keyboard.press("Escape")
                    settle(pg)
                    check(f"{T}: A Escape on desktop also shows everything", snap(pg) == s0, errs)
                reset_all(pg, own)

                # ---- B no dead end
                keys = pg.evaluate("() => NMSKShowAll.keys()")
                check(f"{T}: B the page registers its hiding paths ({len(keys)}: {keys})", len(keys) >= 6, errs)
                bad = []
                for key in keys:
                    drove = pg.evaluate("(k) => !!NMSKShowAll.drive(k)", key)
                    settle(pg, 700)
                    if not drove:
                        bad.append(key + "(not driveable)"); pg.evaluate("() => NMSKModelReset.run()"); settle(pg, 700); continue
                    seen = [c["key"] for c in chips(pg)]
                    vis = pg.is_visible("#sa-all") and pg.is_visible("#sa-bar")
                    if key not in seen or not vis:
                        bad.append(f"{key}(chip={key in seen},btn={vis})")
                    else:
                        tap(pg, "#sa-all", phone)
                        settle(pg, 900)
                        if pg.evaluate("() => NMSKShowAll.active()"):
                            bad.append(key + "(still active after Show everything)")
                    reset_all(pg, own)
                check(f"{T}: B every hiding path has a visible way out (bad: {bad})", not bad, errs)

                # ---- C model reset
                load = pg.evaluate("() => JSON.stringify(NMSKModelReset.loaded())")
                pg.evaluate("() => { const d = window.__q300dbg; d.messUp(); }")
                settle(pg)
                mess = snap(pg)
                check(f"{T}: C the page really was changed before the reset", mess != load, errs)
                tap(pg, "#h-mr-model" if pg.is_visible("#h-mr-model") else "#mb-mr-model", phone)
                settle(pg, 1400)
                check(f"{T}: C one tap on the model reset returns the load state", snap(pg) == load, errs)
                pg.keyboard.press("Control+z")
                settle(pg, 1400)
                check(f"{T}: C the model reset is one undo step", snap(pg) == mess, errs)
                reset_all(pg, own)

                # ---- D the skeleton must read
                res[T] = {"modes": measure_modes(pg, own, phone, T, errs, min_c)}

                check(f"{T}: 0 page errors ({perrs[:2]})", not perrs, errs)
                ctx.close()
            b.close()
    finally:
        srv.terminate()
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    min_c = float(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--min-contrast=")), MIN_CONTRAST))
    errs, out = [], {}
    rep = REPO / "data" / "derived" / "Q300_browser_check.json"

    def save():
        rep.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    for d in args:
        p = Path(d)
        tag = KEY.get(p.name, p.name)
        print(f"== {tag} ({p})")
        try:
            out[tag] = run_page(p, tag, errs, min_c)
        except Exception as err:                 # a page that falls over must not take the pages already measured with it
            errs.append(f"{tag}: {type(err).__name__}: {err}")
            print(f"  FAIL {tag}: {type(err).__name__}: {str(err)[:200]}")
        finally:
            save()
    print(f"\nwrote {rep.relative_to(REPO)}")
    print(f"\n{'FAIL' if errs else 'OK'}: {len(errs)} failure(s)")
    for e in errs:
        print("  - " + e)
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
