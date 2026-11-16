#!/usr/bin/env python3
"""Q343: the name card's "Related structures" families (Myofascial lines, Innervation) and its Parts chooser, measured in a
real Chromium on a Base page.

    python3 scripts/anatomy/q343/verify_groups_q343.py <page_dir> [--no-patch] [--size WxH ...]

The page dir is copied to /dev/shm/q343v_<dir>_<pid> (sidecars symlinked), patched with the sync output of the name card
(scripts/sync_quickcard_q321.py) and of this module (scripts/sync_groups342_q343.py) unless --no-patch, and given its
sidecar groups_q342.json from scripts/anatomy/q342/build_sidecar_q342.py. Expected sets are computed here from the
committed Q342 data files (data/anatomy/*_q342.json), not from the page.

Checked: biceps brachii -> Myofascial lines -> a class -> a line through it: the marked ids equal the line's muscle stations
on the clicked side, in station order; the evidence label is shown; "+ bones, fasciae, ligaments" marks every station;
Horizontal is greyed and says why; a line without dissection evidence says so. Innervation -> By root -> C6 (= the json's
C6 members, key muscles named) -> By peripheral nerve (its muscles + the nerve) -> By central pattern (rule-based label,
most direct tiers). A nerve offers "Muscles it supplies". Parts: pectoralis major clavicular head and deltoid show their three
parts, "Whole muscle" selects the three meshes, a part selects one, Hide acts on the chosen scope; trapezius lists its parts
greyed with the reason. Undo restores each step. Menu / card inside the viewport, readable contrast, keyboard (arrows, Enter,
Escape back), no developer wording, 0 page errors. Prints OK / FAIL lines and Q343_GROUPS_OK / Q343_GROUPS_FAIL."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q319"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q321"))
import verify_search_q319 as V            # noqa: E402  (serve / route / open_page / check)
import verify_quickcard_q321 as Q         # noqa: E402  (contrast / developer-text helpers)
from playwright.sync_api import sync_playwright  # noqa: E402

ERRS = V.ERRS
check = V.check
DA = REPO / "data" / "anatomy"
PAGE_KEY = {"viewer_zan_atlas": "base_m", "viewer_base_female": "base_f"}
EVL = {"strong": "Evidence: strong", "moderate": "Evidence: moderate", "none": "No dissection evidence — contested",
       "not_examined": "Not examined by any review — contested"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def page_copy(src: Path, patch: bool) -> Path:
    dst = Path("/dev/shm") / ("q343v_%s_%d" % (src.name, os.getpid()))
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for f in src.iterdir():
        if f.suffix == ".html":
            shutil.copy(f, dst / f.name)
        elif f.name != "groups_q342.json":
            os.symlink(f.resolve(), dst / f.name)
    if patch:
        mods = [_load(n, REPO / "scripts" / (n + ".py")) for n in ("sync_quickcard_q321", "sync_groups342_q343")]
        for f in dst.glob("*.html"):
            t = f.read_text(encoding="utf-8")
            for m in mods:
                t = m.render(t)
            f.write_text(t, encoding="utf-8")
    sc = _load("sc343", REPO / "scripts/anatomy/q342/build_sidecar_q342.py")
    (dst / sc.NAME).write_text(json.dumps(sc.build(PAGE_KEY[src.name], dst), ensure_ascii=False), encoding="utf-8")
    return dst


# ------------------------------------------------------------------ expected sets, from the committed data
def pick(o, ks):
    v = [i for k in ks for i in (o or {}).get(k, [])]
    if not v:
        v = list((o or {}).get("mid", []))
    if not v:
        v = [i for k in ("r", "l") for i in (o or {}).get(k, [])]
    return v


def uniq(a):
    s, o = set(), []
    for x in a:
        if x and x not in s:
            s.add(x); o.append(x)
    return o


def exp_line(page, lid, side, all_=False):
    L = [x for x in json.loads((DA / "myofascial_lines_q342.json").read_text())["lines"] if x["id"] == lid][0]
    oth = {"r": "l", "l": "r"}[side]
    out = []
    for s in L["stations"]:
        if not all_ and "muscle" not in s["kind"]:
            continue
        ks = {"S": [side], "O": [oth], "mid": ["mid"]}.get(s["side"], ["r", "l", "mid"])
        out += pick((s.get("structures") or {}).get(page), ks)
    return L, uniq(out)


def inn():
    return json.loads((DA / "innervation_groups_q342.json").read_text())


def exp_root(page, lv, side, ids):
    d = inn()
    out = []
    for x in d["families"]["root"]["levels"][lv]["members"]:
        out += pick(d["muscles"][x["muscle_id"]]["structures"].get(page), [side])
    return uniq([i for i in out if i in ids]), d["families"]["root"]["levels"][lv].get("isncsci_key_muscles")


def exp_nerve_muscles(page, nid, side, ids):
    d = inn()
    out = []
    for x in d["families"]["peripheral"]["nerves"][nid]["all_members"]:
        out += pick(d["muscles"][x["muscle_id"]]["structures"].get(page), [side])
    return uniq([i for i in out if i in ids])


def exp_pattern(page, pid, side, ids):
    d = inn()
    P = [p for p in d["families"]["central"]["patterns"] if p["id"] == pid][0]
    top = [m for m in P["members"] if m["tier"] in ("named_in_guide", "guide_section_and_action")]
    use = top or P["members"]
    out = []
    for m in use:
        if m["muscle_id"] in d["muscles"]:
            out += pick(d["muscles"][m["muscle_id"]]["structures"].get(page), [side])
    return P, uniq([i for i in out if i in ids])


# ------------------------------------------------------------------ page helpers
def marks(pg):
    return pg.evaluate("() => NMSKSelectCtl.state().marks.slice()")


def pick_card(pg, sid):
    pg.evaluate("(id) => { NMSKSelectCtl.markIds([], true, true, true); __q334.select(id); NMSKQuick.open(id, null, null); }", sid)
    pg.wait_for_timeout(250)
    try:
        pg.wait_for_function("NMSKGroups342.state().loaded", timeout=30000)
    except Exception:
        pass
    pg.evaluate("() => NMSKHistory.commit && NMSKHistory.commit()")
    pg.wait_for_timeout(250)
    return pg.evaluate("() => { const c = document.querySelector('.qc'); return c && !c.hidden ? c.querySelector('.qc-name').textContent : null; }")


def menu(pg):
    return pg.evaluate("""() => { const m = document.getElementById('qc-relmenu'); if (!m) return null; const r = m.getBoundingClientRect();
      const its = [...m.querySelectorAll('.qc-rmi')];
      return {sheet: m.getAttribute('data-sheet'), l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, sw: m.scrollWidth, cw: m.clientWidth,
              items: its.map(i => ({key: i.getAttribute('data-key') || i.getAttribute('data-fam'), text: i.textContent, off: i.classList.contains('qc-off'),
                                    here: i.classList.contains('qc-here'), title: i.title || ''})),
              focus: document.activeElement ? (document.activeElement.getAttribute('data-key') || document.activeElement.getAttribute('data-fam') || document.activeElement.className) : null}; }""")


def click_item(pg, key):
    return pg.evaluate("""(k) => { const m = document.getElementById('qc-relmenu'); if (!m) return false;
      const i = [...m.querySelectorAll('.qc-rmi')].find(e => (e.getAttribute('data-key') || e.getAttribute('data-fam')) === k); if (!i) return false; i.click(); return true; }""", key)


def open_rel(pg):
    pg.evaluate("() => { NMSKQuick.relClose(false); document.querySelector('.qc .qc-relb').click(); }")
    pg.wait_for_timeout(200)


def status(pg):
    return pg.evaluate("""() => { const s = document.getElementById('q8-status'); if (!s) return null; const r = s.getBoundingClientRect();
      return {text: s.firstChild ? s.firstChild.textContent : '', tags: [...s.querySelectorAll('[data-g3]')].map(e => [e.getAttribute('data-g3'), e.textContent]),
              info: !!s.querySelector('.q8-i'), more: (s.querySelector('.q8-more') || {}).textContent || '', inCard: !!s.closest('.qc'),
              r: r.right, b: r.bottom}; }""")


def undo_ok(pg, before):
    pg.evaluate("() => NMSKHistory.undo()"); pg.wait_for_timeout(300)
    return marks(pg) == before


def in_view(r, w, h):
    return r and r["l"] >= -0.5 and r["t"] >= -0.5 and r["r"] <= w + 0.5 and r["b"] <= h + 0.5


# ------------------------------------------------------------------ one viewport
def run_size(pl, d: Path, w: int, h: int, tag: str, page: str):
    print(f"--- {tag} {w}x{h}")
    srv, b, pg = V.open_page(pl, d, w, h)
    T = f"[{tag} {w}]"
    try:
        pg.wait_for_function("window.NMSKQuick && window.NMSKGroups342 && window.__q334", timeout=90000)
        ids = _load("sc343i", REPO / "scripts/anatomy/q342/build_sidecar_q342.py").page_ids(d)   # this page's own mesh ids
        fams = pg.evaluate("() => NMSKQuickCard.families()")
        check(f"{T} families registered in order {fams}", fams[:5] == ["grp", "adj", "rel", "mfl", "inn"])
        # ================= Myofascial lines, from biceps brachii
        nm = pick_card(pg, "biceps_brachii_r")
        st = pg.evaluate("() => NMSKGroups342.state()")
        check(f"{T} card on '{nm}', sidecar fetched on first use (loaded={st['loaded']})", nm and st["loaded"])
        open_rel(pg)
        m0 = menu(pg)
        lab = {i["key"]: i["text"] for i in m0["items"]} if m0 else {}
        check(f"{T} Related structures menu: {[lab.get(k) for k in ('mfl', 'inn')]}", m0 and "mfl" in lab and "inn" in lab
              and lab["mfl"].startswith("Myofascial lines") and lab["inn"].startswith("Innervation"))
        click_item(pg, "mfl"); pg.wait_for_timeout(150)
        m1 = menu(pg)
        keys = [i["key"] for i in m1["items"]] if m1 else []
        check(f"{T} class sheet: {[i['text'] for i in m1['items']] if m1 else None}",
              m1 and m1["sheet"] == "mfl" and [k for k in keys if k and k.startswith("cls-")] == ["cls-vertical", "cls-diagonal_spiral", "cls-arm", "cls-functional", "cls-horizontal"])
        hz = [i for i in m1["items"] if i["key"] == "cls-horizontal"][0]
        click_item(pg, "cls-horizontal"); pg.wait_for_timeout(100)
        why = pg.evaluate("() => { const p = document.querySelector('#qc-relmenu .qc-rwhy'); return p ? p.textContent : null; }")
        check(f"{T} Horizontal greyed, reason on hover ({len(hz['title'])} chars) and on tap", hz["off"] and "horizontal" in hz["title"].lower() and why and "horizontal" in why.lower())
        check(f"{T} sheet sized to content and inside the view ({round(m1['w'])} px)", in_view(m1, w, h) and m1["sw"] <= m1["cw"] + 1)
        here_cls = [i["key"] for i in m1["items"] if i["here"] and i["key"] and i["key"].startswith("cls-")]
        click_item(pg, here_cls[0] if here_cls else "cls-arm"); pg.wait_for_timeout(150)
        m2 = menu(pg)
        lines = [i for i in m2["items"] if i["key"] and i["key"].startswith("line-")]
        first_here = lines and lines[0]["here"]
        check(f"{T} {here_cls[:1]} lines, those through biceps first: {[(i['text'], i['here']) for i in lines][:4]}", bool(lines) and first_here)
        lid = lines[0]["key"][5:]
        before = marks(pg)
        click_item(pg, "line-" + lid); pg.wait_for_timeout(400)
        L, exp = exp_line(page, lid, "r")
        got = marks(pg)
        check(f"{T} {L['name']}: {len(got)} marked == the json's muscle stations on the right, in station order ({len(exp)})", got == exp)
        s = status(pg)
        evt = dict(s["tags"]).get("ev") if s else None
        check(f"{T} status names the line and its evidence: '{s and s['text']}' / '{evt}'", s and L["name"] in s["text"] and evt == EVL[L["evidence"]["label"]] and s["inCard"] and s["info"])
        pg.evaluate("() => document.querySelector('#q8-status .q8-i').click()"); pg.wait_for_timeout(100)
        mo = status(pg)["more"]
        check(f"{T} (i) gives the evidence + sources ({len(mo)} chars)", ("doi" in mo or "PMID" in mo) and "contested" in mo.lower() and "scripts/" not in mo)
        pg.evaluate("() => document.querySelector('#q8-status [data-g3=all]').click()"); pg.wait_for_timeout(300)
        _, exp_all = exp_line(page, lid, "r", True)
        check(f"{T} '+ bones, fasciae, ligaments' marks every station ({len(marks(pg))} == {len(exp_all)})", marks(pg) == exp_all)
        check(f"{T} Undo -> muscles only again", undo_ok(pg, got))
        check(f"{T} Undo -> marks as before the line ({len(before)})", undo_ok(pg, before))
        # a line with no dissection evidence says so plainly
        open_rel(pg); click_item(pg, "mfl"); click_item(pg, "cls-vertical"); pg.wait_for_timeout(150)
        click_item(pg, "line-superficial_front_line"); pg.wait_for_timeout(300)
        s = status(pg)
        check(f"{T} SFL says '{dict(s['tags']).get('ev')}'", dict(s["tags"]).get("ev") == EVL["none"])
        pg.evaluate("() => NMSKHistory.undo()"); pg.wait_for_timeout(250)
        # keyboard: Enter opens a sheet, Escape goes back one sheet, then closes the menu, the card stays
        open_rel(pg)
        pg.evaluate("() => { const i = document.querySelector('#qc-relmenu .qc-rmi[data-fam=mfl]'); i.focus(); }")
        pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
        k1 = menu(pg)
        pg.keyboard.press("ArrowDown"); pg.wait_for_timeout(60)
        k1b = menu(pg)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        k2 = menu(pg)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        k3 = menu(pg)
        check(f"{T} keyboard: Enter -> sheet ({k1 and k1['sheet']}), arrows move ({k1 and k1['focus']} -> {k1b and k1b['focus']}), Esc back, Esc closes, card stays",
              k1 and k1["sheet"] == "mfl" and k1b and k1b["focus"] != k1["focus"] and k2 and not k2["sheet"] and k3 is None
              and pg.evaluate("() => !!NMSKQuick.current()"))
        # ================= Innervation
        before = marks(pg)
        open_rel(pg); click_item(pg, "inn"); pg.wait_for_timeout(120)
        mi = menu(pg)
        check(f"{T} Innervation sheet: {[i['text'] for i in mi['items']]}", mi and [i["key"] for i in mi["items"] if i["key"] in ("root", "nerve", "central")] == ["root", "nerve", "central"])
        click_item(pg, "root"); pg.wait_for_timeout(120)
        mr = menu(pg)
        here = [i["key"] for i in mr["items"] if i["here"]]
        check(f"{T} By root: the muscle's own levels first {here}", here[:2] == ["root-C5", "root-C6"] and mr["items"][1]["key"] == "root-C5")
        click_item(pg, "root-C6"); pg.wait_for_timeout(350)
        exp, key = exp_root(page, "C6", "r", ids)
        got = marks(pg)
        s = status(pg)
        kt = dict(s["tags"]).get("key", "")
        check(f"{T} C6: {len(got)} marked == the json's C6 muscles on the right ({len(exp)})", sorted(got) == sorted(exp))
        check(f"{T} C6 key muscles flagged: '{kt[:90]}'", key and key["function"] in kt and "ISNCSCI" in kt)
        check(f"{T} Undo restores", undo_ok(pg, before))
        open_rel(pg); click_item(pg, "inn"); click_item(pg, "nerve"); pg.wait_for_timeout(120)
        mn = menu(pg)
        nh = [i for i in mn["items"] if i["here"]]
        check(f"{T} By peripheral nerve: its nerve first {[i['text'] for i in nh][:3]}", nh and nh[0]["key"] == "nerve-musculocutaneous_n")
        click_item(pg, "nerve-musculocutaneous_n"); pg.wait_for_timeout(350)
        expm = exp_nerve_muscles(page, "musculocutaneous_n", "r", ids)
        got = marks(pg)
        nmesh = [i for i in got if i not in expm]
        check(f"{T} musculocutaneous n.: muscles {sorted(set(got) & set(expm))} == json {sorted(expm)}, + the nerve {nmesh}",
              set(expm) <= set(got) and "musculocutaneous_n_r" in got and all(re.search(r"_n(_|$)|nerve", i) for i in nmesh))
        check(f"{T} Undo restores", undo_ok(pg, before))
        open_rel(pg); click_item(pg, "inn"); click_item(pg, "central"); pg.wait_for_timeout(120)
        mc = menu(pg)
        ph = [i for i in mc["items"] if i["here"]]
        check(f"{T} By central pattern: postures with biceps first {[i['text'] for i in ph][:3]}", bool(ph) and mc["items"][2]["here"])
        pid = ph[0]["key"][4:]
        click_item(pg, "pat-" + pid); pg.wait_for_timeout(350)
        P, exp = exp_pattern(page, pid, "r", ids)
        got = marks(pg)
        s = status(pg)
        check(f"{T} {P['name']}: {len(got)} marked == json (most direct tiers, else all) ({len(exp)})", sorted(got) == sorted(exp))
        check(f"{T} rule-based label shown: '{dict(s['tags']).get('rule')}'", dict(s["tags"]).get("rule") == "Rule-based from sourced posture + muscle actions")
        check(f"{T} Undo restores", undo_ok(pg, before))
        # a selected nerve: "Muscles it supplies"
        pick_card(pg, "musculocutaneous_n_r")
        open_rel(pg); click_item(pg, "inn"); pg.wait_for_timeout(120)
        mn2 = menu(pg)
        sup = [i for i in mn2["items"] if i["key"] and i["key"].startswith("sup-")]
        check(f"{T} a nerve offers {[i['text'] for i in sup]}", sup and sup[0]["text"].startswith("Muscles it supplies"))
        if sup:
            click_item(pg, sup[0]["key"]); pg.wait_for_timeout(300)
            got = marks(pg)
            check(f"{T} its muscles marked: {sorted(i for i in got if not i.startswith('musculocutaneous'))}",
                  {"biceps_brachii_r", "brachialis_r", "coracobrachialis_r"} <= set(got))
        pg.evaluate("() => NMSKQuick.relClose(false)")
        # ================= Parts chooser
        def parts():
            return pg.evaluate("""() => { const a = document.querySelector('.qc-addon[data-addon=parts]'); if (!a) return null; const r = a.getBoundingClientRect(), c = document.querySelector('.qc').getBoundingClientRect();
              return {head: a.querySelector('.g3-ph').textContent, chips: [...a.querySelectorAll('.g3-pc')].map(b => ({k: b.getAttribute('data-part'), t: b.textContent,
                      p: b.getAttribute('aria-pressed'), off: b.classList.contains('g3-off'), title: b.title})), note: a.querySelector('.g3-pnote').textContent,
                      inCard: r.right <= c.right + 0.5 && r.left >= c.left - 0.5, scope: document.querySelector('.qc').getAttribute('data-scope')}; }""")

        def chip(k):
            pg.evaluate("(k) => document.querySelector('.qc-addon[data-addon=parts] .g3-pc[data-part=\"' + k + '\"]').click()", k)
            pg.wait_for_timeout(250)
        for sid, mu, n3 in (("zan_clavicular_head_of_pectoralis_major_muscle_r", "Pectoralis major",
                             ["zan_clavicular_head_of_pectoralis_major_muscle_r", "zan_sternocostal_head_of_pectoralis_major_muscle_r", "zan_abdominal_part_of_pectoralis_major_muscle_r"]),
                            ("zan_acromial_part_of_deltoid_muscle_r", "Deltoid",
                             ["zan_clavicular_part_of_deltoid_muscle_r", "zan_acromial_part_of_deltoid_muscle_r", "zan_scapular_spinal_part_of_deltoid_muscle_r"])):
            pick_card(pg, sid)
            p = parts()
            ks = [c["k"] for c in (p or {}).get("chips", [])]
            check(f"{T} {mu}: chooser '{p and p['head']}' {[c['t'] for c in p['chips']] if p else None}",
                  p and mu in p["head"] and len(ks) == 4 and ks[0] == "whole" and not any(c["off"] for c in p["chips"]) and p["inCard"]
                  and [c["p"] for c in p["chips"]].count("true") == 1)
            before = marks(pg)
            hid0 = pg.evaluate("() => __viewerState().hidden")
            chip("whole")
            got = marks(pg)
            p = parts()
            check(f"{T} {mu}: Whole muscle selects the three meshes {len(got)} (scope {p['scope']})", sorted(got) == sorted(n3) and p["scope"] == "3")
            pg.evaluate("() => document.querySelector('.qc .qc-b[data-qc=hide]').click()"); pg.wait_for_timeout(250)
            hid1 = pg.evaluate("() => __viewerState().hidden")
            check(f"{T} {mu}: Hide acts on the whole muscle (hidden {hid0} -> {hid1})", hid1 - hid0 == 3)
            check(f"{T} {mu}: Undo shows them again", (pg.evaluate("() => NMSKHistory.undo()") or True) and pg.wait_for_timeout(300) is None
                  and pg.evaluate("() => __viewerState().hidden") == hid0)
            part2 = [c["k"] for c in parts()["chips"]][2]
            chip(part2)
            got = marks(pg)
            check(f"{T} {mu}: a part ({part2}) selects one mesh {got}", len(got) == 1 and got[0] in n3 and parts()["scope"] == "1")
            check(f"{T} {mu}: Undo -> the whole muscle again", undo_ok(pg, sorted(n3)) or sorted(marks(pg)) == sorted(n3))
            pg.evaluate("() => NMSKHistory.undo()"); pg.wait_for_timeout(250)
            check(f"{T} {mu}: Undo -> marks as before", marks(pg) == before)
        pick_card(pg, "trapezius_r")
        p = parts()
        off = [c for c in (p or {}).get("chips", []) if c["off"]]
        check(f"{T} Trapezius: Whole muscle + {len(off)} greyed parts with the reason ('{off and off[0]['title']}')",
              p and p["chips"][0]["k"] == "whole" and p["chips"][0]["p"] == "true" and len(off) == 3 and all("no separate mesh on this body" in c["title"] for c in off))
        if off:
            chip(off[0]["k"])
            check(f"{T} tap on a greyed part explains it: '{parts()['note'][:80]}'", "no separate mesh on this body" in parts()["note"] and marks(pg) == [])
        # ================= readability, layout, wording
        pick_card(pg, "biceps_brachii_r")
        open_rel(pg); click_item(pg, "mfl"); click_item(pg, "cls-arm"); pg.wait_for_timeout(150)
        bad = Q.contrast_fail(pg, "#qc-relmenu .qc-rmi, #qc-relmenu .qc-rbadge, .qc .g3-pc:not(.g3-off), .qc .qc-b")
        mm = menu(pg)
        check(f"{T} line sheet inside the view and readable{' ' + str(bad[:3]) if bad else ''}", in_view(mm, w, h) and not bad)
        pg.evaluate("() => NMSKQuick.relClose(false)")
        click = pg.evaluate("() => { const c = document.querySelector('.qc').getBoundingClientRect(); return {l: c.left, t: c.top, r: c.right, b: c.bottom}; }")
        check(f"{T} card inside the view ({round(click['r'])}x{round(click['b'])})", in_view(click, w, h))
        dev = Q.dev_strings(pg)
        check(f"{T} no developer wording visible{' ' + str(dev) if dev else ''}", not dev)
        ban = pg.evaluate("""() => { const t = document.documentElement.outerHTML.toLowerCase();
          return ['ultrasound', 'hounsfield', 't1_se', 'imaging_tissues', 'tissue table', 'nmskultrasound', 'acoustic', 'mrayl', 'b-mode'].filter(w => document.querySelector('.qc') && document.querySelector('.qc').outerHTML.toLowerCase().includes(w)); }""")
        check(f"{T} no banned word in the card", not ban)
    finally:
        b.close(); srv.terminate()


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sizes = [(1400, 900), (390, 844)]
    if "--size" in sys.argv:
        sizes = [tuple(int(v) for v in a.split("x")) for a in sys.argv[sys.argv.index("--size") + 1:] if re.match(r"\d+x\d+$", a)]
        args = [a for a in args if not re.match(r"\d+x\d+$", a)]
    src = Path(args[0]) if args else REPO / "build/q309/viewer_zan_atlas"
    page = PAGE_KEY[src.name]
    d = page_copy(src, "--no-patch" not in sys.argv)
    n_err = 0
    with sync_playwright() as pl:
        for w, h in sizes:
            n0 = len(ERRS)
            run_size(pl, d, w, h, src.name, page)
            pe = [e for e in ERRS[n0:] if e.startswith("page error")]
            n_err += len(pe)
            check(f"[{src.name} {w}] 0 page errors ({len(pe)})", not pe)
    shutil.rmtree(d, ignore_errors=True)
    print("Q343_GROUPS_FAIL" if ERRS else "Q343_GROUPS_OK")
    for e in ERRS:
        print("   ", e)
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
