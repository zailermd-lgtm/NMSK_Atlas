#!/usr/bin/env python3
"""Q308: real headless-Chromium check of what this round built, and of the three cards that denied real tissue.

Owner (translated from Hebrew): "Build everything. Then compare it both against papers, and against the images
that appear in those papers, and against other 3D models."

Desktop 1400x900 with real clicks, phone 390x844 with real TOUCH, one page of each engine. The accumulated
lessons are applied by REUSING the code that encodes them (verify_q283 / q305 / q306): pixels are read through
an in-page hook and never from `page.screenshot`; the Z pages' auto-spin is frozen before anything is measured;
the welcome banner is dismissed in-page; Q294's history is committed explicitly rather than trusting its
debounce; `wait_for_function` is passed its argument only as a keyword; the search box is `#q` on the own pages
and `#search` on the Z pages; and a row is pressed at a point measured AFTER scrolling inside the scroller,
checked with `elementFromPoint`, instead of with `force=True`.

A  EVERY BUILT STRUCTURE IS ON THE PAGE AND ACCOUNTABLE. Each one this round ships is in the page's own data,
   is reachable by typing its name, and its card says RULE-BASED in words, prints its volume in cm3 and names
   a source with a PMID or a DOI.
B  PSOAS MINOR IS HIDDEN BY DEFAULT, and that is read from the engine, not assumed: its list row carries the
   engine's own `hid` class and its card's own button reads "unhide". On the two Imaging pages it is NOT
   shipped at all, because that engine has no hidden-by-default flag and a muscle absent in roughly half of
   people must not default to visible on a named body.
C  THE THREE CARDS THAT DENIED REAL TISSUE. On a Z page `pubic symphysis`, `retrocalcaneal bursa` and `TFCC`
   must now return the STRUCTURE and must NOT lead with the old explanation; on an Imaging page, where all
   three genuinely are absent, the honest explanation must still be what comes back.
D  THE OWNER'S OWN NERVE. The anterior and posterior branches are reachable by name, and the card carries the
   measured division distance.
E  THE NEW STRUCTURES HAVE THEIR EXPANSIONS, because Q298's adjacency and relation builders were re-run on all
   six pages: pick one and `Adjacent` must offer something.
F  0 page errors, both viewports.

    python3 scripts/anatomy/q308/verify_q308.py PAGE_DIR... [--json OUT]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE.parent / "q283", HERE.parent / "q305", HERE.parent / "q306", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import verify_q283 as V      # noqa: E402
import verify_q305 as Q5     # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OKN = [0]
KEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m",
       "viewer_base_female": "base_f", "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
REPORT: dict = {}
BUILT = json.loads((REPO / "data/derived/Q308_built_structures.json").read_text(encoding="utf-8"))
PAGEREP = json.loads((REPO / "data/derived/Q308_page_report.json").read_text(encoding="utf-8"))
TIER_A = {"pubic symphysis": "pubic_symphysis_disc",
          "retrocalcaneal bursa": "zan_subtendinous_calcaneal_bursa_l",
          "TFCC": "zan_articular_disc_of_distal_radio_ulnar_joint_l"}


def check(label, cond, errs):
    if V.check(label, cond, errs):
        OKN[0] += 1
        return True
    return False


def sel_of(d):
    return "#q" if d.startswith("viewer_m_hr") or d.startswith("viewer_f_hr") else "#search"


def type_in(pg, sel, q):
    pg.evaluate("""([s, v]) => { const b = document.querySelector(s); b.value = v;
                   b.dispatchEvent(new Event('input', {bubbles:true})); }""", [sel, q])
    pg.wait_for_timeout(280)
    return pg.evaluate("""() => { const r = NMSKQ298.result() || {};
        return {q: r.q || "", n: (r.ids || []).length, approx: r.approx || 0,
                note_first: r.note_first || 0,
                notes: (r.notes || []).map(x => x.name),
                top: (r.ids || []).slice(0, 5),
                rows: [].slice.call(document.querySelectorAll('#list .item'))
                        .slice(0, 6).map(b => ({t: (b.querySelector('.t')||{}).textContent || '',
                                                cls: b.className}))}; }""")


def select_by_name(pg, sel, name, phone):
    """Type the name, then press the first result row at a point measured after scrolling inside the scroller
    and verified with elementFromPoint -- the Q304/Q306 method, not force=True."""
    type_in(pg, sel, name)
    spot = pg.evaluate("""() => {
        const b = document.querySelector('#list .item');
        if (!b) return {err: 'no row'};
        b.scrollIntoView({block: 'center', inline: 'nearest'});
        const r = b.getBoundingClientRect();
        const cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
        const h = document.elementFromPoint(cx, cy);
        return {x: cx, y: cy, onIt: !!(h && (h === b || b.contains(h))),
                hit: h ? h.tagName + (h.id ? '#' + h.id : '') : null,
                label: (b.textContent || '').slice(0, 60), cls: b.className}; }""")
    if spot.get("onIt"):
        if phone:
            pg.touchscreen.tap(spot["x"], spot["y"])
        else:
            pg.mouse.click(spot["x"], spot["y"])
        pg.wait_for_timeout(600)
    return spot


def card_text(pg):
    return pg.evaluate("""() => {
        const h = document.getElementById('a-hide');
        const panel = h ? h.closest('aside, section, div[id]') : null;
        const t = (panel ? panel.textContent : document.body.textContent) || '';
        return {hide_label: h ? (h.textContent || '').trim() : null, len: t.length, text: t.slice(0, 7000)}; }""")


def run_page(pl, d: Path, phone: bool, errs):
    key = KEY[d.name]
    sel = sel_of(d.name)
    tag = "phone" if phone else "desk"
    rep = REPORT.setdefault(key, {}).setdefault(tag, {})
    srv, port = V.serve(d)
    b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
    try:
        ctx = b.new_context(viewport={"width": 390, "height": 844} if phone else {"width": 1400, "height": 900},
                            device_scale_factor=2 if phone else 1, is_mobile=phone, has_touch=phone)
        pg = ctx.new_page()
        pe = []
        pg.on("pageerror", lambda e: pe.append(str(e)))
        pg.route("**/*", V.route)
        pg.goto(f"http://127.0.0.1:{port}/{V.html_of(d)}", wait_until="load", timeout=240000)
        pg.wait_for_function(expression="() => document.readyState === 'complete'", timeout=120000)
        Q5.quiet_chrome(pg)
        # the Z pages spin by themselves: two measurements would be of two different poses (Q300's finding)
        pg.evaluate("""() => { const b = document.getElementById('btn-spin');
                               if (b && b.classList.contains('on')) b.click(); }""")
        pg.wait_for_function(expression="() => window.NMSKQ298 && NMSKQ298.ready()", timeout=240000)
        pg.wait_for_function(expression="() => { const l = document.getElementById('list');"
                                        "return !!(l && l.children.length); }", timeout=240000)
        Q5.stage(pg, phone)
        pg.wait_for_timeout(400)

        ship = sorted(PAGEREP[key]["added"])
        rep["shipped"] = ship
        ids = pg.evaluate("() => (NMSKQ298.data() || {}).ids || []")
        rep["n_ids"] = len(ids)

        # ---------------- A every built structure is on the page, reachable, and accountable
        for sid in ship:
            st = BUILT[key][sid]
            check(f"{key} {tag}: {sid} is in the page's own data", sid in ids, errs)
            name = st.get("name") or ""
            r = type_in(pg, sel, {"coracoacromial_ligament": "coracoacromial ligament",
                                  "lacn_anterior_branch": "anterior branch of lateral antebrachial",
                                  "lacn_posterior_branch": "posterior branch of lateral antebrachial",
                                  "psoas_minor": "psoas minor",
                                  "anterolateral_ligament": "anterolateral ligament"}[sid.rsplit("_", 1)[0]])
            check(f"{key} {tag}: typing its clinical name reaches {sid}", sid in r["top"], errs)
        # one card read in full, per family, and it must say the three things
        fams = {}
        for sid in ship:
            fams.setdefault(sid.rsplit("_", 1)[0], sid)
        for fam, sid in sorted(fams.items()):
            spot = select_by_name(pg, sel, sid.replace("_", " "), phone)
            ct = card_text(pg)
            rep.setdefault("cards", {})[sid] = {"spot": spot, "hide_label": ct["hide_label"],
                                                "chars": ct["len"]}
            t = ct["text"]
            vol = str(BUILT[key][sid]["volume_cm3"])
            check(f"{key} {tag}: {sid}'s card says RULE-BASED", "RULE-BASED" in t, errs)
            check(f"{key} {tag}: {sid}'s card prints its volume {vol} cm3", vol in t, errs)
            check(f"{key} {tag}: {sid}'s card names a PMID or a DOI",
                  ("PMID" in t) or ("doi:" in t), errs)
            check(f"{key} {tag}: {sid}'s card does NOT claim 'Measured on this body'",
                  "Measured on this body" not in t, errs)

        # ---------------- B psoas minor: hidden by default where it ships, absent where it cannot be hidden
        if key.startswith("own"):
            check(f"{key} {tag}: psoas minor is NOT shipped here (this engine cannot hide a mesh by default)",
                  not any(s.startswith("psoas_minor") for s in ids), errs)
        else:
            spot = select_by_name(pg, sel, "psoas minor", phone)
            ct = card_text(pg)
            rep["psoas"] = {"spot": spot, "hide_label": ct["hide_label"]}
            check(f"{key} {tag}: the psoas minor row carries the engine's own `hid` class "
                  f"(cls={spot.get('cls')})", "hid" in (spot.get("cls") or ""), errs)
            check(f"{key} {tag}: its card's own button reads 'unhide', i.e. the engine has it hidden "
                  f"(label={ct['hide_label']!r})", (ct["hide_label"] or "").lower() == "unhide", errs)
            check(f"{key} {tag}: its card says it is not demonstrated on this body",
                  "NOT DEMONSTRATED ON THIS BODY" in ct["text"].upper(), errs)

        # ---------------- C the three that denied real tissue
        for term, sid in TIER_A.items():
            r = type_in(pg, sel, term)
            rep.setdefault("tier_a", {})[term] = r
            if key.startswith("own"):
                check(f"{key} {tag}: `{term}` still returns the honest explanation here, where it IS absent",
                      bool(r["notes"]), errs)
            else:
                check(f"{key} {tag}: `{term}` now returns the STRUCTURE {sid}", sid in r["top"], errs)
                check(f"{key} {tag}: `{term}` no longer leads with the denial", r["note_first"] == 0, errs)

        # ---------------- D the owner's own nerve
        if any(s.startswith("lacn_") for s in ship):
            sid = sorted(s for s in ship if s.startswith("lacn_"))[0]
            select_by_name(pg, sel, "anterior branch of lateral antebrachial", phone)
            ct = card_text(pg)
            div = str(BUILT[key][sid]["division_distal_to_iel_mm"])
            check(f"{key} {tag}: the branch card carries its measured division distance {div} mm",
                  div in ct["text"], errs)
            check(f"{key} {tag}: the branch card names Khadanovich's 47.8 +- 34.2 mm",
                  "47.8" in ct["text"] and "34.2" in ct["text"], errs)

        # ---------------- E the new structures have their Q298 expansions
        sid = ship[0]
        type_in(pg, sel, sid.replace("_", " "))
        exp = pg.evaluate("""(sid) => { const d = NMSKQ298.data() || {};
            const i = (d.ids || []).indexOf(sid);
            if (i < 0) return {err: 'not in ids'};
            const adj = (d.adj && d.adj[i]) ? d.adj[i].length : 0;
            const rel = (d.rel && d.rel[i]) ? d.rel[i].length : 0;
            return {i: i, adjacent: adj, related: rel}; }""", sid)
        rep["expansions"] = exp
        check(f"{key} {tag}: {sid} has an Adjacent row after the builders were re-run "
              f"({exp.get('adjacent')} neighbours)", (exp.get("adjacent") or 0) > 0, errs)

        # ---------------- F no page errors
        rep["page_errors"] = pe
        check(f"{key} {tag}: 0 page errors", not pe, errs)
    finally:
        b.close()
        srv.shutdown()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--json", default=str(REPO / "data/derived/Q308_browser_report.json"))
    a = ap.parse_args(argv)
    errs: list = []
    with sync_playwright() as pl:
        for phone in (False, True):
            for d in a.dirs:
                run_page(pl, Path(d), phone, errs)
    Path(a.json).write_text(json.dumps(REPORT, indent=1), encoding="utf-8")
    print(f"\n{OKN[0]} OK, {len(errs)} FAIL")
    for e in errs:
        print("  FAIL", e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
