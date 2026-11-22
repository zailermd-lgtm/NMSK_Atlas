#!/usr/bin/env python3
"""Q358: browser check of the closed vulvar / perineal skin on a built (regen) Base · Female page.

    python3 scripts/anatomy/q358/verify_q358.py PAGE_DIR        # e.g. /dev/shm/q358r/viewer_base_female

One browser, deviceScaleFactor 1, 1400x900, on a test copy with the read-only Q336 hook. Checks: skin_perineum_rule_q358 is the
last mesh and skin_vulva_cvh the one before it; a real pick (skin layer solo, opaque) at a visible point of the rule surface
returns it; a real mouse click there opens the name card on it, the card says rule-based and carries the citations (Mannan,
Gray's Atlas) and the method; the vulva's own card carries the Q358 cleaning note; 0 page errors.
Prints OK / FAIL lines and Q358_VERIFY_OK / Q358_VERIFY_FAIL."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q336"))
sys.path.insert(0, str(HERE))
import pagehook_q336 as PH          # noqa: E402
import perineum_skin_q358 as Q      # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

FAIL: list[str] = []


def check(label, cond):
    print(("  OK   " if cond else "  FAIL ") + label)
    if not cond:
        FAIL.append(label)
    return bool(cond)


CARD = """() => { const c = document.querySelector('.qc'); if (!c || c.hidden) return null;
  const nm = c.querySelector('.qc-name'), sb = c.querySelector('.qc-sub');
  return {name: nm ? nm.textContent : '', sub: sb ? sb.textContent : '', text: c.textContent}; }"""


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    d = Path(argv[0])
    man, blob, _ = Q.read(d)
    ids = [m["id"] for m in man["meshes"]]
    check("skin_perineum_rule_q358 is the last mesh, skin_vulva_cvh the one before", ids[-1] == Q.NEW_ID and ids[-2] == Q.CVH_ID)
    M = {m["id"]: m for m in man["meshes"]}
    v, f = Q.dec(M[Q.NEW_ID], blob)
    rec = M[Q.NEW_ID].get("rec") or {}
    check("its record is badged rule-based with book citations",
          rec.get("procedural_badge", "").startswith("RULE-BASED SURFACE") and "Mannan" in rec.get("source", "")
          and "Gray's Atlas" in rec.get("source", ""))
    check("the vulva's record carries the Q358 cleaning note", "Q358 cleaning" in (M[Q.CVH_ID].get("rec") or {}).get("procedural_badge", ""))
    errs = []
    t = PH.test_copy(d, Path("/dev/shm/q358t") / d.name)
    with sync_playwright() as pl:
        srv, b, pg = PH.open_page(pl, t, 1400, 900, errs=errs)
        try:
            check("the page lists it", pg.evaluate("(k) => __q336.has(k)", Q.NEW_ID))
            pg.evaluate("() => { __q336.defaults(); __q336.layer('skin', 1, 'skin'); }")
            # candidate points: outer-sheet vertices of the rule surface in its lower (posterior) half, seen from below-front
            n2 = len(v) // 2
            po = v[:n2]
            cand = po[np.argsort(po[:, 1])[: max(40, n2 // 6)]][::4]
            c = po.mean(0).tolist()
            got_pick, where = None, None
            for el in (-1.2, -0.9, -0.6):
                pg.evaluate("(a) => __q336.cam({az: 0, el: a[0], dist: 360, tgt: a[1]})", [el, c])
                pg.wait_for_timeout(400)
                for p in cand:
                    s = pg.evaluate("(p) => __q336.toScreen(p)", p.tolist())
                    if not s:
                        continue
                    if pg.evaluate("(q) => __q336.pickAt(q[0], q[1])", [s[0], s[1]]) == Q.NEW_ID:
                        got_pick, where = Q.NEW_ID, s
                        break
                if got_pick:
                    break
            check(f"a real pick on a visible point of it returns {Q.NEW_ID} (at {where})", got_pick == Q.NEW_ID)
            if where:
                pg.mouse.click(where[0], where[1]); pg.wait_for_timeout(900)
                card = pg.evaluate(CARD)
                check(f"a click opens its name card ({card and card['name']!r})", bool(card) and "rule-based" in card["name"].lower())
                txt = (card or {}).get("text", "")
                more = pg.evaluate("""() => { const c = document.querySelector('.qc'); if (!c) return false;
                  const b = [...c.querySelectorAll('button')].find(x => /more/i.test(x.textContent || '')); if (!b) return false; b.click(); return true; }""")
                pg.wait_for_timeout(600)
                card2 = pg.evaluate(CARD) or {}
                txt2 = card2.get("text", "") + " " + txt
                check(f"the card shows the rule-based badge (More pressed: {more})", "RULE-BASED" in txt2 or "rule-based" in txt2.lower())
                check("the card shows the citations (Mannan / Gray's Atlas)", "Mannan" in txt2 and "Gray" in txt2)
                pg.screenshot(path=str(Path("/dev/shm/q358t") / "verify_card_q358.png"))
        finally:
            b.close(); srv.terminate()
    check(f"0 page errors ({errs[:2]})", not errs)
    print("Q358_VERIFY_" + ("OK" if not FAIL else "FAIL"), len(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
