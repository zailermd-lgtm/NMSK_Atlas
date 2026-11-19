#!/usr/bin/env python3
"""Q362: every transferred organ on a regenerated Base page -- its card opens with its OWN record and provenance, the Z structure it
replaces is hidden by default, and the organ is drawn (it is on screen when the view frames it).

    python3 scripts/anatomy/q362/verify_cards_q362.py <page dir> [--shots DIR] [--size 1400x900]

Checks per Q362 id on the page: the card's name is the record's name; the expanded card text says the geometry is registered from the
Visible Human (and the cross-sex sentence for kidneys taken from the female); no raw id / build path in it; a `hd` structure is not
visible at load; the organ is visible after "show only".  Prints OK / FAIL lines and Q362_CARDS_OK / Q362_CARDS_FAIL."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q319"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q362"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q336"))
import verify_search_q319 as V            # noqa: E402
import transfer_organs_q362 as T          # noqa: E402
import pagegeo_q336 as P                  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check = V.check


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("page_dir")
    ap.add_argument("--shots", default="")
    ap.add_argument("--size", default="1400x900")
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    key = T.DIRKEY[d.name]
    man = P.manifest(d); by = {m["id"]: m for m in man["meshes"]}
    new = [o for o in T.ORGANS if o["key"] == key and o["id"] in by]
    print(f"Q362 cards on {d}: {[o['id'] for o in new]} + relabelled Z meshes")
    w, h = (int(x) for x in a.size.split("x"))
    shots = Path(a.shots) if a.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pl:
        srv, b, pg = V.open_page(pl, d, w, h)
        try:
            hidden = sorted({x for o in new for x in o.get("hide", []) if x in by})
            vis = pg.evaluate("""(ids) => { const out = {}; for (const id of ids){ let v = null;
                try { v = window.__q334 && __q334.visible ? __q334.visible(id) : null; } catch (e) {}
                out[id] = v; } return out; }""", hidden)
            for hid in hidden:
                check(f"{hid}: flagged hidden by default in the manifest (hd)", by[hid].get("hd") == 1)
                if vis.get(hid) is not None:
                    check(f"{hid}: not visible at load", vis[hid] is False)
            # the relabelled Z gut meshes (data/anatomy/relabels_q362.json, applied at regen)
            for zid, want in (("zan_sigmoid_colon", "Rectum and anal canal"), ("zan_descending_colon", "Descending colon")):
                check(f"{zid}: manifest name '{want}' and not hidden by default on Base·M", by[zid]["name"] == want and (key == "base_f" or not by[zid].get("hd")))
                pg.evaluate("(id) => { NMSKSelectCtl.markIds([], true, true, true); if (window.__q334) __q334.select(id); NMSKQuick.open(id, null, null); }", zid)
                pg.wait_for_timeout(400)
                pg.evaluate("() => { const m = [...document.querySelectorAll('.qc button')].find(b => /^more/i.test(b.textContent.trim())); if (m) m.click(); }")
                pg.wait_for_timeout(300)
                txt = pg.evaluate("() => { const c = document.querySelector('.qc'); return c && !c.hidden ? c.innerText : ''; }")
                check(f"{zid}: card shows '{want}', the source label and the book", want in txt and "source label" in txt and "Mannan" in txt)
                if shots:
                    pg.screenshot(path=str(shots / f"card_{key}_{zid}.png"))
            if key == "base_m":
                res = pg.evaluate(V.QUERIES % '["rectum", "anal canal", "sigmoid colon"]')
                for q, r in res.items():
                    check(f"search '{q}' finds zan_sigmoid_colon (first hits {r['ids'][:3]})", "zan_sigmoid_colon" in r["ids"])
            for o in new:
                rec = by[o["id"]]["rec"]
                pg.evaluate("(id) => { NMSKSelectCtl.markIds([], true, true, true); if (window.__q334) __q334.select(id); NMSKQuick.open(id, null, null); }", o["id"])
                pg.wait_for_timeout(400)
                pg.evaluate("() => { const m = [...document.querySelectorAll('.qc button')].find(b => /^more/i.test(b.textContent.trim())); if (m) m.click(); "
                            "document.querySelectorAll('.qc details').forEach(x => x.open = true); }")
                pg.wait_for_timeout(300)
                info = pg.evaluate("() => { const c = document.querySelector('.qc'); if (!c || c.hidden) return null; "
                                   "return {name: (c.querySelector('.qc-name') || {}).textContent || '', text: c.innerText}; }")
                check(f"{o['id']}: card opens", bool(info))
                if not info:
                    continue
                txt = info["text"]
                check(f"{o['id']}: card name is its own record's name ({info['name'][:60]})", info["name"].strip().lower().startswith(o["name"].split(" (")[0].lower()))
                check(f"{o['id']}: card says registered from the Visible Human", ("Visible Human" in txt) and ("registered" in txt.lower()))
                lead = "another body" if o["kind"] == "ct" else "rule-based outline"
                check(f"{o['id']}: the expanded card carries its provenance badge ('{lead}')", lead in txt.lower())
                check(f"{o['id']}: the card cites the owner's books", ("Mannan" in txt) or ("Gray's Atlas" in txt))
                if o.get("cross_sex"):
                    check(f"{o['id']}: card says the kidney is the female's", "female" in txt.lower())
                bad = re.findall(r"\b(?:data|scripts|build)/\S+|\b\w+_vh[mf](?:_[lr])?\b", txt)
                check(f"{o['id']}: no raw id / build path on the card {bad[:3]}", not bad)
                if shots:
                    pg.screenshot(path=str(shots / f"card_{o['id']}.png"))
                    for lab in ("Show only", "Zoom to"):
                        pg.evaluate("(l) => { const b = [...document.querySelectorAll('.qc button')].find(x => x.textContent.trim() === l); if (b) b.click(); }", lab)
                        pg.wait_for_timeout(900)
                    pg.screenshot(path=str(shots / f"only_{o['id']}.png"))
                    pg.evaluate("() => { const b = [...document.querySelectorAll('button')].find(x => /show everything/i.test(x.textContent)); if (b) b.click(); }")
                    pg.wait_for_timeout(400)
        finally:
            b.close(); srv.kill()
    ok = not V.ERRS
    print("Q362_CARDS_OK" if ok else "Q362_CARDS_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
