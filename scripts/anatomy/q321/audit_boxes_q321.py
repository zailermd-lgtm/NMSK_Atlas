#!/usr/bin/env python3
"""Q321: width of every box that opens on a Z-engine page, against what is inside it.
    python3 scripts/anatomy/q321/audit_boxes_q321.py <page_dir> [WxH ...]
For each toolbar group's sheet (opened with a DOM click on its button) and the other panels, prints
    box | width | used (right edge of the widest descendant, relative to the box) | empty px at the right | rows wider than their buttons."""
from __future__ import annotations
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q319")); sys.path.insert(0, str(REPO / "scripts/anatomy/q321"))
import verify_search_q319 as V
import verify_quickcard_q321 as Q
from playwright.sync_api import sync_playwright

MEASURE = """(sel) => { const e = document.querySelector(sel); if (!e || !e.getClientRects().length || getComputedStyle(e).display === 'none') return null;
  const r = e.getBoundingClientRect(); let used = 0, wide = [];
  e.querySelectorAll('*').forEach(c => { const q = c.getBoundingClientRect(); if (!q.width || !q.height || getComputedStyle(c).position === 'fixed') return; used = Math.max(used, q.right - r.left);
    if (c.children.length > 1 && getComputedStyle(c).display.includes('flex')) { const kids = [...c.children].filter(k => k.getBoundingClientRect().width); const kr = Math.max(...kids.map(k => k.getBoundingClientRect().right)) - q.left;
      if (q.width - kr > 40 && q.width > 120) wide.push((c.className || c.tagName).toString().slice(0, 24) + ':' + Math.round(q.width - kr)); } });
  return {w: Math.round(r.width), h: Math.round(r.height), used: Math.round(used), empty: Math.round(r.width - used), wide: wide.slice(0, 4)}; }"""

def main():
    a = sys.argv[1:]; src = Path(a[0]); sizes = [tuple(map(int, s.split("x"))) for s in a[1:]] or [(1400, 900), (390, 844)]
    d = Q.page_copy(src, True)
    with sync_playwright() as pl:
        for w, h in sizes:
            srv, b, pg = V.open_page(pl, d, w, h)
            try:
                pg.wait_for_function("window.NMSKQuick", timeout=60000); pg.wait_for_timeout(1500)
                print(f"--- {w}x{h}")
                groups = pg.evaluate("() => [...document.querySelectorAll('.qg-bar .qg-g')].map((e, i) => [i, e.textContent.trim()])")
                for i, name in groups:
                    pg.evaluate("(i) => { document.querySelectorAll('.qg-sheet:not([hidden])').forEach(s => { const x = s.querySelector('.qg-sx'); if (x) x.click(); }); document.querySelectorAll('.qg-bar .qg-g')[i].click(); }", i)
                    pg.wait_for_timeout(500)
                    m = pg.evaluate(MEASURE, ".qg-sheet:not([hidden])")
                    print(f"{name:14s} sheet  ", m)
                pg.evaluate("() => document.querySelectorAll('.qg-sheet:not([hidden]) .qg-sx').forEach(x => x.click())")
                for sel in [".qg-bar", "#rail", "#foot", "#cut-panel", "#pm-card", "#needle-panel", "#lab-panel", "#sel-sec"]:
                    m = pg.evaluate(MEASURE, sel)
                    if m: print(f"{sel:14s}        ", m)
            finally:
                b.close(); srv.terminate()

main()
