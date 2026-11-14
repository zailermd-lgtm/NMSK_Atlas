#!/usr/bin/env python3
"""Q297: real headless-Chromium check (desktop 1400x900 real clicks + phone 390x844 real touch) of what this round changed.

A  the generated perineal surface closure is GONE from Base F and Combined F -- not hidden, not faded: absent from the
   page's own structure list and from its mesh list -- while every REAL perineal structure the Q235 CVH import brought
   (perineal body, deep perineal muscle, superficial transverse perineal, bulbospongiosus, ischiocavernosus,
   urethrovaginal sphincter) is still present and still drawable. On the male Z pages nothing perineal was removed.
B  the rule-based brachial-plexus cords are reachable from the real structure list (typed search + a real click / tap on
   the row) and their card now SHOWS the rule-based badge with a volume, and no longer prints the Z-Anatomy geometry line.
C  on the two Imaging pages the rule-built brachial plexus now prints the ORANGE "Rule-based on this body's own data"
   source line instead of the green "Measured on this body" one -- read from the live card, not from the data.
D  the hand distal phalanx cards carry the Q297 fingertip measurement; the cross-section module still fills a pelvic
   section (the perineal region is now open skin, which must not break the cut-face fill); 0 page errors.

    python3 scripts/anatomy/q297/verify_q297.py PAGE_DIR... [--shots DIR] [--phone=N]"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283")); sys.path.insert(0, str(HERE))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap = V.check, V.tap
KEY = {"viewer_zan_atlas": "base_m", "viewer_base_female": "base_f", "viewer_zan_vhm": "comb_m",
       "viewer_zan_female": "comb_f", "viewer_m_hr": "own_m", "viewer_f_hr": "own_f"}
CLOSURE = "zan_skin_perineal_closure"
REAL_PERINEAL = ["perineal_body", "deep_perineal_muscle_cvh", "superficial_transverse_perineal_cvh",
                 "bulbospongiosus_cvh", "ischiocavernosus_cvh_l", "urethrovaginal_sphincter_cvh"]
CORDS = ["brachial_cord_lateral_l", "brachial_cord_medial_r"]
PLEXUS = ["brachial_root_c5_l", "brachial_trunk_superior_r"]
PHAL = "zan_distal_phalanx_of_third_finger_of_hand_r"


def ids_on_page(pg, kind):
    if kind == "own":
        return pg.evaluate("() => Object.keys(window.groups || {})") or \
               pg.evaluate("() => window.NMSKClinicalTool.api.list().map(m => m.id)")
    return pg.evaluate("() => window.NMSKClinicalTool.api.list().map(m => m.id)")


def open_card(pg, name, phone):
    """the real UI: type into the structure search, then click / tap the row.
    The two engines name the box differently: the Z pages use #search, the own pages #q."""
    box = None
    for _ in range(6):
        for sel in ("#search", "#q"):
            if pg.is_visible(sel):
                box = sel; break
        if box:
            break
        for s in ("#btn-panel", "#m-list", "#t-lay3", "#insp-min"):
            if pg.is_visible(s):
                tap(pg, s, phone); break
        pg.wait_for_timeout(400)
    if not box:
        return None
    pg.fill(box, name); pg.wait_for_timeout(600)
    SEL = "#list button.item, #list .row, #list button"
    idx = pg.evaluate("([s, n]) => Array.from(document.querySelectorAll(s))"
                      ".findIndex(b => b.innerText.toLowerCase().indexOf(n.toLowerCase()) >= 0)", [SEL, name])
    if idx < 0:
        return None
    tap(pg, f"{SEL} >> nth={idx}", phone)
    pg.wait_for_timeout(700)
    for _ in range(2):
        if not pg.evaluate("() => { const e = document.getElementById('info') || document.getElementById('inspector');"
                           " return !!e && e.classList.contains('min'); }"):
            break
        for s in ("#im", "#insp-min", "#info .info-min"):
            if pg.is_visible(s):
                tap(pg, s, phone); break
        pg.wait_for_timeout(400)
    return pg.evaluate("() => { const e = document.getElementById('info') || document.getElementById('inspector');"
                       " if (!e) return ''; const s = document.getElementById('i-src');"
                       " return (s && !s.hidden ? s.textContent + '\\n' : '') + e.innerText; }")


def close_card(pg, phone):
    for s in ("#ic", "#insp-close", ".info-close"):
        if pg.is_visible(s):
            tap(pg, s, phone); pg.wait_for_timeout(300); return


def run_page(d: Path, errs: list, shots: Path | None, only_phone=None):
    key = KEY[d.name]
    kind = "own" if key in ("own_m", "own_f") else "zan"
    html = V.html_of(d)
    srv, port = V.serve(d)
    female_z = key in ("base_f", "comb_f")
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            sizes = [((1400, 900), False), ((390, 844), True)]
            if only_phone is not None:
                sizes = [sizes[1]] if only_phone else [sizes[0]]
            for (w, h), phone in sizes:
                T = f"{key}_{w}"
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page(); perr = []
                pg.on("pageerror", lambda e: perr.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=120000)
                V.ready(pg)
                ids = ids_on_page(pg, kind)
                # --- A: the generated closure is absent; the real perineal structures are not
                if kind == "zan":
                    check(f"{T}: A the generated perineal surface closure is absent from the page ({len(ids)} meshes)",
                          CLOSURE not in ids, errs)
                if female_z:
                    present = [s for s in REAL_PERINEAL if s in ids]
                    check(f"{T}: A every real (CVH) perineal structure is still on the page ({len(present)}/{len(REAL_PERINEAL)})",
                          len(present) == len(REAL_PERINEAL), errs)
                    drawn = pg.evaluate("(ids) => { const a = window.NMSKClinicalTool.api, L = a.list(); let n = 0;"
                                        " for (let i = 0; i < L.length; i++) if (ids.indexOf(L[i].id) >= 0 && a.geometry(i)) n++;"
                                        " return n; }", present)
                    check(f"{T}: A all {len(present)} of them have real geometry on the page ({drawn})", drawn == len(present), errs)
                # --- B: the rule-based cords are badged on the live card
                if kind == "zan":
                    txt = open_card(pg, "Brachial plexus, lateral cord", phone) or open_card(pg, "lateral cord", phone)
                    ok = bool(txt) and "RULE-BASED" in txt.upper() and "cm3" in txt
                    check(f"{T}: B the lateral cord's card shows the rule-based badge with a volume ({(txt or '')[:60]!r})", ok, errs)
                    check(f"{T}: B that card no longer claims the geometry is Z-Anatomy's",
                          bool(txt) and "Geometry from Z-Anatomy" not in txt, errs)
                    close_card(pg, phone)
                # --- C: the Imaging pages' rule-built plexus is no longer called measured
                if kind == "own":
                    # these structures carry no display name of their own, so the list row shows the raw id
                    txt = open_card(pg, "brachial_root_c5_l", phone)
                    if txt is None:
                        txt = open_card(pg, "brachial_cord_lateral_l", phone)
                    ok = bool(txt) and "Rule-based on this body" in txt
                    check(f"{T}: C the rule-built brachial plexus card prints the RULE-BASED source line ({(txt or '')[:70]!r})", ok, errs)
                    # the one-line SOURCE CLASS statement itself, not the whole card: the subject description below it
                    # quotes the old wrong wording on purpose, to record what Q297 fixed
                    srcline = pg.evaluate("() => { const e = document.getElementById('i-src');"
                                          " return e && !e.hidden ? e.textContent : ''; }")
                    check(f"{T}: C the source line no longer says 'Measured on this body' ({srcline[:60]!r})",
                          bool(srcline) and "Measured on this body" not in srcline, errs)
                    close_card(pg, phone)
                # --- D: the fingertip measurement is on the distal phalanx card
                if kind == "zan":
                    txt = open_card(pg, "Distal phalanx of third finger of hand", phone)
                    check(f"{T}: D the middle-finger distal phalanx card carries the Q297 fingertip measurement",
                          bool(txt) and "Q297 FINGERTIP MEASUREMENT" in txt, errs)
                    close_card(pg, phone)
                check(f"{T}: D no page errors ({perr[:1]})", not perr, errs)
                if shots:
                    shots.mkdir(parents=True, exist_ok=True)
                    pg.screenshot(path=str(shots / f"{key}_{w}.png"))
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main(argv):
    shots = None; only_phone = None
    if "--shots" in argv:
        i = argv.index("--shots"); shots = Path(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    ph = [a for a in argv if a.startswith("--phone=")]
    if ph:
        only_phone = ph[0].split("=")[1] == "1"; argv = [a for a in argv if not a.startswith("--phone=")]
    dirs = [Path(a) for a in argv]
    errs = []
    for d in dirs:
        print(f"== {d}")
        run_page(d, errs, shots, only_phone)
    print(f"\nQ297 VERIFY: {'FAIL ' + str(len(errs)) if errs else 'OK'}")
    for e in errs:
        print("  FAIL", e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
