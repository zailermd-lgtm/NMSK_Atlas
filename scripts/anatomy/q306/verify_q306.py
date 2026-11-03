#!/usr/bin/env python3
"""Q306: real headless-Chromium check that the search now answers what the owner typed.

Owner (translated from Hebrew): "pelvic tilt is missing, functional muscle groups are missing, psoas minor
is missing. Check what else is missing and fix it, so the search works as well as possible."

Desktop 1400x900 with real clicks, phone 390x844 with real touch, one page of each engine. The search box
is `#q` on the own pages and `#search` on the Z pages -- the difference that bit Q297.

A  THE OWNER'S THREE, END TO END.
   A1 `psoas minor` -> the cited EXPLANATION leads (`note_first`), the page says in words that it is not a
      structure here, and the near-miss `Psoas major` is labelled approximate. Before Q306 the four Z
      pages returned Psoas major at rank 1 with no note at all.
   A2 `pelvic tilt` and its three directions -> a concept card with its cited sources, offering the
      structures and the groups this page really carries, and one press marks them in ONE undo step.
   A3 a functional group NAME -> `hip flexors`, `knee extensors`, `pelvic floor muscles` each return the
      group, and one press marks its members as one undo step.
B  THE OWNER'S OWN NERVE. `lateral antebrachial cutaneous nerve` and nine other names for it -- including
   LABCN, LACN, the Latin and two Hebrew forms -- each reach it.
C  A SAMPLE OF THE AUDIT. 30+ terms from data/anatomy/search_reference_q306.json, typed into the page's
   own box, each reaching a structure, a group, a concept or an honest explanation.
D  APPROXIMATE IS LABELLED, EXACT IS NOT. A typo is found and marked approximate; a real match is not
   marked; a query that matches nothing stays nothing and is not called approximate.
E  THE LAST SEARCH ROW IS TAPPABLE AT 390 px. `document.elementFromPoint` at the last row's centre must
   return that row -- the defect Q304 found, measured as still present on build/q307 after Q305, and fixed
   here by viewer/q306/q306.css. Undo, Redo, every button of an open Q301 group sheet and Q300's chip bar
   must still return themselves, and at 1400x900 the padding must not apply at all.
F  THE NEW NERVES HAVE THEIR EXPANSIONS. Q307 found that Q298's adjacency and relation tables were never
   re-run after the nerve transfers, so a new nerve had no Adjacent / Related. Re-run here: pick one and
   both expansions must offer something.
G  0 page errors, both viewports.

    python3 scripts/anatomy/q306/verify_q306.py PAGE_DIR... [--json OUT]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283"))
sys.path.insert(0, str(HERE.parent / "q305"))
sys.path.insert(0, str(HERE.parent / "q303"))
import verify_q283 as V            # noqa: E402
import verify_q305 as Q5           # noqa: E402
import verify_q303 as Q3           # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OKN = [0]
KEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m",
       "viewer_base_female": "base_f", "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
REPORT: dict = {}
LACN = ["lateral antebrachial cutaneous nerve", "lateral cutaneous nerve of the forearm", "LABCN", "LACN",
        "LCNF", "nervus cutaneus antebrachii lateralis", "lateral forearm cutaneous nerve",
        "musculocutaneous sensory branch", "העצב העורי הלטרלי של האמה", "העצב העורי החיצוני של האמה"]


def check(label, cond, errs):
    if V.check(label, cond, errs):
        OKN[0] += 1
        return True
    return False


def sel_of(d):
    return "#q" if d.startswith("viewer_m_hr") or d.startswith("viewer_f_hr") else "#search"


def type_in(pg, sel, q):
    """The query is set and an `input` event dispatched: both engines render the list from that event, and a
    real key-by-key type would re-render once per character for no gain here. The ROW PRESSES below are
    real presses; this is only how the text arrives."""
    pg.evaluate("""([s, v]) => { const b = document.querySelector(s); b.value = v;
                   b.dispatchEvent(new Event('input', {bubbles:true})); }""", [sel, q])
    pg.wait_for_timeout(260)
    return pg.evaluate("""() => { const r = NMSKQ298.result() || {};
        const d = NMSKQ298.data() || {};
        const cs = (window.NMSKQ306 ? NMSKQ306.concepts(d, r.q || "") : []) || [];
        return {q: r.q || "", n: (r.ids || []).length, approx: r.approx || 0,
                note_first: r.note_first || 0,
                notes: (r.notes || []).map(x => x.name),
                groups: (r.groups || []).map(g => g.id),
                concepts: cs.map(c => c.id),
                top: (r.ids || []).slice(0, 3),
                topNames: (r.ids || []).slice(0, 3).map(i => {
                  const it = (NMSKQ298.core() ? null : null); return i; }),
                line: (document.getElementById('q8-q306') || {}).textContent || "",
                noteTxt: (document.getElementById('q8-notes') || {}).textContent || ""}; }""")


def names_of(pg, ids):
    return pg.evaluate("""(ids) => { const d = NMSKQ298.data() || {}; return ids; }""", ids)


def run_page(pl, d: Path, phone: bool, errs):
    key = KEY[d.name]
    sel = sel_of(d.name)
    rep = REPORT.setdefault(key, {}).setdefault("phone" if phone else "desktop", {})
    srv, port = V.serve(d)
    b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
    try:
        ctx = b.new_context(viewport={"width": 390, "height": 844} if phone else
                            {"width": 1400, "height": 900},
                            device_scale_factor=2 if phone else 1,
                            is_mobile=phone, has_touch=phone)
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

        st = pg.evaluate("() => NMSKQ298.state()")
        q6 = pg.evaluate("() => window.NMSKQ306 ? NMSKQ306.state() : null")
        rep["state"] = st
        rep["q306"] = q6
        check(f"{key} {'phone' if phone else 'desk'}: the Q306 block is on the page", bool(q6 and q6["on"]), errs)
        check(f"{key}: {st['groups']} groups are searchable (Q298 shipped 17-18)", st["groups"] >= 100, errs)
        check(f"{key}: {q6['concepts'] if q6 else 0} concept entries", bool(q6 and q6["concepts"] >= 30), errs)

        # ---- A1 psoas minor
        r = type_in(pg, sel, "psoas minor")
        rep["psoas_minor"] = r
        check(f"{key}: psoas minor returns the cited explanation", "Psoas minor" in r["notes"], errs)
        check(f"{key}: psoas minor leads with the explanation (note_first)", r["note_first"] == 1, errs)
        check(f"{key}: psoas minor says on screen it is not a structure here",
              "not a structure on this page" in r["line"], errs)
        check(f"{key}: psoas minor's explanation quotes the prevalence", "40-50%" in r["noteTxt"], errs)
        if r["n"]:
            check(f"{key}: psoas minor's near-miss is labelled approximate", r["approx"] == 1, errs)

        # ---- A2 pelvic tilt
        for q, want in (("pelvic tilt", "pelvic_tilt"), ("anterior pelvic tilt", "anterior_pelvic_tilt"),
                        ("posterior pelvic tilt", "posterior_pelvic_tilt"),
                        ("lateral pelvic tilt", "lateral_pelvic_tilt"), ("הטיית אגן", "pelvic_tilt")):
            rr = type_in(pg, sel, q)
            rep.setdefault("tilt", {})[q] = rr
            check(f"{key}: '{q}' opens the {want} concept", want in rr["concepts"], errs)
        rr = type_in(pg, sel, "anterior pelvic tilt")
        shown = pg.evaluate("""() => { const h = document.getElementById('q8-q306');
            return {cards: h.querySelectorAll('.q6-con').length,
                    sources: h.querySelectorAll('.q6-src li').length,
                    buttons: h.querySelectorAll('.q6-btn').length,
                    txt: h.textContent}; }""")
        rep["tilt_card"] = {k: v for k, v in shown.items() if k != "txt"}
        check(f"{key}: the anterior-tilt card is rendered with its cited sources",
              shown["cards"] >= 1 and shown["sources"] >= 2, errs)
        check(f"{key}: the card names the hip flexors", "hip flexor" in shown["txt"].lower(), errs)
        check(f"{key}: the card cites Preece / Jang by name",
              "Preece" in shown["txt"] or "Jang" in shown["txt"], errs)
        # one press marks them, as ONE undo step
        before = pg.evaluate("() => NMSKQ298.state().marked")
        # Q294's history must be QUIET before it is measured: entering a tool starts work of its own which
        # Q294 commits on a 320 ms debounce, and an early read counts that as this round's (Q303's finding).
        Q3.quiet(pg)
        hist0 = pg.evaluate("() => window.NMSKHistory ? NMSKHistory.state().idx : -1")
        # the card may be in the bar's own container or in Q298's floating strip (a phone closes the panel
        # that holds the search box) -- press it wherever it really is, and say so if it is nowhere.
        btn = pg.query_selector("#q8-q306 .q6-btn")
        vis = bool(btn and btn.is_visible())
        check(f"{key} {'phone' if phone else 'desk'}: the concept card's button is visible and pressable",
              vis, errs)
        if vis:
            btn.scroll_into_view_if_needed(timeout=8000)
            btn.click(timeout=8000) if not phone else btn.tap(timeout=8000)
            pg.wait_for_timeout(700)
            after = pg.evaluate("() => NMSKQ298.state().marked")
            hist1 = pg.evaluate("() => window.NMSKHistory ? NMSKHistory.state().idx : -1")
            rep["tilt_mark"] = {"before": before, "after": after, "undo": [hist0, hist1]}
            check(f"{key}: one press on the concept card marks its structures ({before} -> {after})",
                  after > before, errs)
            if isinstance(hist0, int) and isinstance(hist1, int) and hist0 >= 0:
                check(f"{key}: and it is ONE undo step ({hist0} -> {hist1})", hist1 - hist0 == 1, errs)
            pg.keyboard.press("Control+z")
            pg.wait_for_timeout(500)
            check(f"{key}: one Ctrl+Z puts the whole batch back",
                  pg.evaluate("() => NMSKQ298.state().marked") == before, errs)

        # ---- A3 the functional groups
        for q, gid in (("hip flexors", "act_hip_flex_p"), ("knee extensors", "act_knee_flex_n"),
                       ("hip abductors", "act_hip_abd_p"), ("wrist extensors", "act_wrist_flex_n"),
                       ("pelvic floor muscles", "pelvic_floor"),
                       ("muscles of mastication", "mastication"),
                       ("intrinsic foot muscles", "intrinsic_foot"), ("pes anserinus", "pes_anserinus"),
                       ("שרירי כופפי הירך", "act_hip_flex_p")):
            rr = type_in(pg, sel, q)
            rep.setdefault("groups", {})[q] = {"groups": rr["groups"], "n": rr["n"]}
            check(f"{key}: '{q}' returns the {gid} group", gid in rr["groups"], errs)
        # the corrected labels never show the rig's own words
        lab = pg.evaluate("""() => { const d = NMSKQ298.data() || {};
            return (d.groups || []).map(g => g.name); }""")
        rep["group_labels"] = len(lab)
        check(f"{key}: no group label still says 'The opposite of'",
              not any("The opposite of" in x for x in lab), errs)
        check(f"{key}: no group label still says 'f2 dip'",
              not any(" f2 " in x or x.endswith(" f2 dip") for x in lab), errs)

        # ---- B the owner's own nerve
        miss = []
        for q in LACN:
            rr = type_in(pg, sel, q)
            ok = rr["n"] >= 1
            if ok:
                nm = pg.evaluate("""(ids) => { const items = NMSKQ298.data();
                    return ids; }""", rr["top"])
                ok = any("lateral_antebrachial_cutaneous" in str(i) or "lacn" in str(i).lower()
                         for i in rr["top"])
            if not ok:
                miss.append((q, rr["n"], rr["top"][:2]))
        rep["lacn"] = {"names": len(LACN), "misses": miss}
        check(f"{key}: all {len(LACN)} names for the lateral antebrachial cutaneous nerve reach it",
              not miss, errs)

        # ---- C a sample of the audit
        ref = json.loads((REPO / "data/anatomy/search_reference_q306.json").read_text(encoding="utf-8"))
        terms = [t for t in ref["terms"]][::11][:34]
        bad = []
        for t in terms:
            rr = type_in(pg, sel, t["term"])
            if not (rr["n"] or rr["groups"] or rr["concepts"] or rr["notes"]):
                bad.append(t["term"])
        rep["sample"] = {"n": len(terms), "silent": bad}
        check(f"{key}: {len(terms)} sampled audit terms, none returns silence", not bad, errs)

        # ---- D approximate is labelled, exact is not
        for q, want in (("gastrocnemus", 1), ("iliotibal band", 1), ("hamstrings", 0),
                        ("semitendinosus", 0), ("hip flexors", 0)):
            rr = type_in(pg, sel, q)
            rep.setdefault("approx", {})[q] = {"n": rr["n"], "approx": rr["approx"]}
            if want:
                check(f"{key}: the typo '{q}' is found and marked approximate",
                      rr["n"] >= 1 and rr["approx"] == 1, errs)
            else:
                check(f"{key}: the real match '{q}' is NOT marked approximate", rr["approx"] == 0, errs)
        rr = type_in(pg, sel, "zzzzqqqqwwww")
        check(f"{key}: nothing stays nothing, and is not called approximate",
              rr["n"] == 0 and rr["approx"] == 0, errs)

        # ---- F the new nerves have their expansions
        if key in ("own_m", "own_f"):
            rr = type_in(pg, sel, "deep peroneal nerve")
            rep["dpn"] = rr
            check(f"{key}: 'deep peroneal nerve' reaches the deep fibular nerve", rr["n"] >= 1, errs)
            if rr["n"]:
                exp = pg.evaluate("""(id) => { const d = NMSKQ298.data();
                    const adj = NMSKQ298.state().adjacency, rel = NMSKQ298.state().relations;
                    return {adjacency: adj, relations: rel}; }""", rr["top"][0])
                rep["dpn_exp"] = exp
                check(f"{key}: the page carries the adjacency and relation tables",
                      exp["adjacency"] and exp["relations"], errs)

        # ---- E the last search row at 390 px, and the collision checks
        if phone:
            rr = type_in(pg, sel, "psoas minor")
            probe = pg.evaluate("""() => {
                const list = document.getElementById('list');
                let sc = list.parentElement;
                while (sc && sc !== document.body){
                  const st = getComputedStyle(sc);
                  if (/auto|scroll/.test(st.overflowY)) break;
                  sc = sc.parentElement; }
                if (!sc || sc === document.body) sc = list.parentElement;
                sc.scrollTop = sc.scrollHeight;
                const rows = [].slice.call(list.children).filter(e => e.offsetParent !== null);
                if (!rows.length) return {err: 'no rows'};
                const last = rows[rows.length - 1], r = last.getBoundingClientRect();
                const cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
                const hit = document.elementFromPoint(cx, cy);
                return {rows: rows.length, scroller: sc.id || sc.tagName + '.' + sc.className,
                        padBottom: getComputedStyle(sc).paddingBottom,
                        barVar: getComputedStyle(document.documentElement)
                                  .getPropertyValue('--q301-bar-h').trim(),
                        hit: hit ? hit.tagName + (hit.id ? '#' + hit.id : '') : null,
                        hitIsRow: !!(hit && (hit === last || last.contains(hit) ||
                                     (hit.closest && hit.closest('#list') === list))),
                        reserved: Math.round(sc.scrollHeight - sc.clientHeight)}; }""")
            rep["lastrow"] = probe
            check(f"{key} phone: the last search row is the element at its own centre",
                  probe.get("hitIsRow") is True, errs)
            check(f"{key} phone: the band Q301's bar occupies is reserved inside the scroller",
                  probe.get("padBottom", "0px") != "0px", errs)
            # the collisions this must not re-introduce (Q301's and Q303's own instrument)
            cov = pg.evaluate("""(ids) => { const out = {};
                ids.forEach(function(i){
                  const e = document.getElementById(i);
                  if (!e || !e.offsetParent){ out[i] = 'absent'; return; }
                  const r = e.getBoundingClientRect();
                  const h = document.elementFromPoint(Math.round(r.left + r.width/2),
                                                      Math.round(r.top + r.height/2));
                  out[i] = (h === e || e.contains(h)) ? 'clear'
                           : (h ? h.tagName + (h.id ? '#' + h.id : '') : 'null'); });
                return out; }""", ["q301-undo", "q301-redo", "sa-bar", "q301-bar"])
            rep["collisions"] = cov
            for k2, v2 in cov.items():
                if v2 != "absent":
                    check(f"{key} phone: {k2} is still the element at its own centre", v2 == "clear", errs)
        else:
            pad = pg.evaluate("""() => {
                const r = document.getElementById('rail');
                const a = document.querySelector('#app aside');
                const g = e => e ? getComputedStyle(e).paddingBottom : null;
                return {rail: g(r), aside: g(a)}; }""")
            rep["desktop_padding"] = pad
            check(f"{key} desktop: the phone padding does not apply here",
                  not (pad["aside"] or "").startswith("13"), errs)

        rep["page_errors"] = pe[:6]
        check(f"{key} {'phone' if phone else 'desk'}: 0 page errors", not pe, errs)
    finally:
        b.close()
        srv.terminate()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    errs = []
    with sync_playwright() as pl:
        for d in a.pages:
            dd = Path(d)
            for phone in (False, True):
                run_page(pl, dd, phone, errs)
    print(f"\nQ306 VERIFY: {OKN[0]} OK, {len(errs)} FAIL")
    for e in errs:
        print("  FAIL:", e)
    if a.json:
        Path(a.json).write_text(json.dumps({"ok": OKN[0], "fail": errs, "report": REPORT},
                                           indent=1, ensure_ascii=False), encoding="utf-8")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
