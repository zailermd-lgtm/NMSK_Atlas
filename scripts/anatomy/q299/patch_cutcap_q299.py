"""Q299 Part C: the minimum DRAWN section width ("band") in the cut-face fill.

    python3 scripts/anatomy/q299/patch_cutcap_q299.py [--file PATH] [--check]

Why: `NMSKCapCore.fillItem` paints a structure's cut section by an even-odd scanline fill, and a structure that paints
no pixel ("thin") or that fails the parity sanity test on an open mesh ("outline") was left as a 1 px vector outline.
Measured on the shipped pages (scripts/anatomy/q299/xsec299.js, 30 axial levels per region per page): that is the whole
fascia class (76 % of fascial sections outline-only on Combined M), plus a tail of vessels and nerves -- i.e. exactly
the classes the owner could not find in a cross-section.

The fix paints a band of the minimum drawn width along the structure's OWN contour segments. It is a thickened outline,
not a fill: no pixel is painted that is not within half the band width of a real contour segment, so a parity failure
still cannot produce a wrong filled area (the Q227 guarantee). The minimum is 1/500 of the section's own extent, capped
at 2.5 mm, and the structure's own measured section width is kept and reported beside it (res.items[].width_mm), the
same way Q294 kept the real sheet thickness while fixing the drawn ultrasound fascia.

Idempotent: run it again and it reports "up to date".
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TARGET = REPO / "viewer/cut_cap/cut_cap.js"

STROKE = '''
  /* ---- 5b. Q299 minimum drawn width ("band"). A structure whose cut section is thinner than the raster can show --
     a 1 mm nerve, a 0.9 mm fascial sheet, a tendon cut edge-on -- paints few pixels or none, and an OPEN sheet fails
     the parity test and used to be left as a 1 px outline: invisible. This paints a band of `half` raster pixels on
     EACH SIDE OF THE STRUCTURE'S OWN CONTOUR SEGMENTS. It is a thickened outline, never a fill: no pixel is painted
     that is not within `half` of a real contour segment, so a parity failure still cannot produce a wrong filled area.
     The drawn width is a DISPLAY minimum; the structure's own measured section width is reported next to it
     (res.items[].width_mm / band_mm), so the millimetres stay honest. ---- */
  function strokeItem(S, g, ids, code, half){
    var inv = 1 / g.px, w = g.w, h = g.h, hp = half < 0.5 ? 0.5 : half, hp2 = hp * hp, n = 0, k, r, c;
    for (k = 0; k < S.sa.length; k++){
      var a = S.sa[k], b = S.sb[k];
      var x0 = (S.pu[a] - g.u0) * inv, y0 = (S.pv[a] - g.v0) * inv, x1 = (S.pu[b] - g.u0) * inv, y1 = (S.pv[b] - g.v0) * inv;
      var c0 = Math.max(0, Math.floor(Math.min(x0, x1) - hp)), c1 = Math.min(w - 1, Math.ceil(Math.max(x0, x1) + hp));
      var r0 = Math.max(0, Math.floor(Math.min(y0, y1) - hp)), r1 = Math.min(h - 1, Math.ceil(Math.max(y0, y1) + hp));
      var dx = x1 - x0, dy = y1 - y0, L2 = dx * dx + dy * dy;
      for (r = r0; r <= r1; r++){
        var base = r * w;
        for (c = c0; c <= c1; c++){
          var qx = c + 0.5 - x0, qy = r + 0.5 - y0;
          var t = L2 > 0 ? (qx * dx + qy * dy) / L2 : 0; t = t < 0 ? 0 : (t > 1 ? 1 : t);
          var ex = qx - t * dx, ey = qy - t * dy;
          if (ex * ex + ey * ey <= hp2){ if (ids[base + c] !== code) n++; ids[base + c] = code; }
        }
      }
    }
    return n;
  }

  /* the length of one structure's section contour, in mm */
  function contourLen(S){
    var L = 0;
    for (var k = 0; k < S.sa.length; k++){
      var a = S.sa[k], b = S.sb[k], du = S.pu[a] - S.pu[b], dv = S.pv[a] - S.pv[b];
      L += Math.sqrt(du * du + dv * dv);
    }
    return L;
  }
'''

EDITS = [
 # 1. the two new pure functions, after fillItem
 ("""      if (src >= 0){ st.painted += paintRow(r, src); st.repaired++; }
    }
    return st;
  }
""",
  """      if (src >= 0){ st.painted += paintRow(r, src); st.repaired++; }
    }
    return st;
  }
""" + STROKE),
 # 2. the option documentation
 ("""     opt: {gap:1.0, minPx:0.4, maxDim:2048, px:override, maxOddFrac:0.12, maxOddRun:30, outline:true, win:[u0, v0, u1, v1] (Q294: plane-coordinate window -- only what is cut inside it)} */""",
  """     opt: {gap:1.0, minPx:0.4, maxDim:2048, px:override, maxOddFrac:0.12, maxOddRun:30, outline:true, win:[u0, v0, u1, v1] (Q294: plane-coordinate window -- only what is cut inside it),
           band:0 (Q299: minimum DRAWN section width in mm; 0 = off, which is the behaviour before Q299), bandFrac:0 (the same minimum expressed as a
           fraction of the section's own extent, so it scales with what is on screen: 1/500 of the extent is about 2 screen px on a 900 px canvas),
           bandMax:2.5 (never draw a band wider than this, so a 1 mm nerve is never drawn as a 5 mm cable)} */"""),
 # 3. the option defaults
 ("""    var o = {gap:opt.gap == null ? 1.0 : opt.gap, minPx:opt.minPx || 0.4, maxDim:opt.maxDim || 2048, px:opt.px || 0,
             maxOddFrac:opt.maxOddFrac == null ? 0.12 : opt.maxOddFrac, maxOddRun:opt.maxOddRun || 30, outline:opt.outline !== false};""",
  """    var o = {gap:opt.gap == null ? 1.0 : opt.gap, minPx:opt.minPx || 0.4, maxDim:opt.maxDim || 2048, px:opt.px || 0,
             maxOddFrac:opt.maxOddFrac == null ? 0.12 : opt.maxOddFrac, maxOddRun:opt.maxOddRun || 30, outline:opt.outline !== false,
             band:opt.band || 0, bandFrac:opt.bandFrac || 0, bandMax:opt.bandMax == null ? 2.5 : opt.bandMax};"""),
 # 4. the stats record
 ("""    var stats = {items_total:items.length, structures_cut:cut.length, filled:0, outline_only:0, thin:0, rows:0,""",
  """    var stats = {items_total:items.length, structures_cut:cut.length, filled:0, outline_only:0, thin:0, band:0, banded:0, band_mm:0, rows:0,"""),
 # 5. the per-structure pass
 ("""    cut.sort(function(a, b){ return a.rank - b.rank || b.area - a.area; });          // painter order: later paints over earlier
    cut.forEach(function(c, order){
      var code = order + 1, it = c.it, fs = fillItem(c.S, g, ids, code, o);
      c.order = order; c.stat = fs;
      var status = fs.failed ? "outline" : (fs.painted ? "filled" : "thin");""",
  """    var bandMm = Math.min(o.bandMax, Math.max(o.band, o.bandFrac * ext));            // Q299: the minimum drawn section width for THIS cut
    if (bandMm > 0) bandMm = Math.max(bandMm, px);                                   // a band is never thinner than one raster pixel, so report what is actually drawn
    stats.band_mm = Math.round(bandMm * 1000) / 1000;
    cut.sort(function(a, b){ return a.rank - b.rank || b.area - a.area; });          // painter order: later paints over earlier
    cut.forEach(function(c, order){
      var code = order + 1, it = c.it, fs = fillItem(c.S, g, ids, code, o);
      c.order = order; c.stat = fs;
      if (bandMm > 0){                                                               // Q299: widen only what is too thin to be seen, and only along its own contour
        var lenMm = contourLen(c.S);
        fs.width_mm = lenMm > 0 ? 2 * fs.painted * px * px / lenMm : 0;              // 2 x area / contour length = the section's own mean thickness (exact for a sheet)
        if (fs.failed || fs.painted === 0 || fs.width_mm < bandMm){
          fs.banded = strokeItem(c.S, g, ids, code, 0.5 * bandMm / px);
          fs.band_mm = bandMm;
          if (fs.banded) stats.banded++;
        }
      }
      var status = (fs.banded && (fs.failed || !fs.painted)) ? "band" : (fs.failed ? "outline" : (fs.painted ? "filled" : "thin"));"""),
 # 6. per-category tally
 ("""      var bc = stats.by_cat[it.cat] || (stats.by_cat[it.cat] = {cut:0, filled:0, outline_only:0, thin:0, odd_rows:0, rows:0});
      bc.cut++; bc[status === "filled" ? "filled" : status === "outline" ? "outline_only" : "thin"]++; bc.odd_rows += fs.odd; bc.rows += fs.rows;
      stats[status === "filled" ? "filled" : status === "outline" ? "outline_only" : "thin"]++;""",
  """      var bc = stats.by_cat[it.cat] || (stats.by_cat[it.cat] = {cut:0, filled:0, outline_only:0, thin:0, band:0, odd_rows:0, rows:0});
      var sk = status === "filled" ? "filled" : status === "outline" ? "outline_only" : status === "band" ? "band" : "thin";
      bc.cut++; bc[sk] = (bc[sk] || 0) + 1; bc.odd_rows += fs.odd; bc.rows += fs.rows;
      stats[sk]++;"""),
 # 7. the per-item record
 ("""      res.items.push({code:code, key:it.key, name:it.name, cat:it.cat, ii:c.ii, status:status, odd:fs.odd, rows:fs.rows, repaired:fs.repaired,
                      open_before:c.cg.before, open_after:c.cg.after});""",
  """      res.items.push({code:code, key:it.key, name:it.name, cat:it.cat, ii:c.ii, status:status, odd:fs.odd, rows:fs.rows, repaired:fs.repaired,
                      open_before:c.cg.before, open_after:c.cg.after, banded:fs.banded || 0,
                      band_mm:fs.band_mm == null ? 0 : fs.band_mm, width_mm:fs.width_mm == null ? null : Math.round(fs.width_mm * 1000) / 1000});"""),
 # 8. a banded structure is drawn in its own colour
 ("""      pal[r.code] = r.status === "filled" ? ((a << 24) | (B << 16) | (G << 8) | R) >>> 0 : 0;""",
  """      pal[r.code] = (r.status === "filled" || r.status === "band") ? ((a << 24) | (B << 16) | (G << 8) | R) >>> 0 : 0;"""),
 # 9. exports
 ("""          fillItem:fillItem, build:build, recolor:recolor, lookup:lookup, rankOf:rankOf, capA:capA};""",
  """          fillItem:fillItem, strokeItem:strokeItem, contourLen:contourLen, build:build, recolor:recolor, lookup:lookup, rankOf:rankOf, capA:capA};"""),
 # 10. the controller's own minimum
 ("""function NMSKCap(E){
  "use strict";""",
  """function NMSKCap(E){
  "use strict";
  /* Q299: a thin section gets a minimum DRAWN width so a 1 mm nerve or a 0.9 mm fascial sheet is visible at all. The
     minimum is 1/500 of the section's own extent (about 2 screen px on a 900 px canvas, so it scales with what is on
     screen) capped at 2.5 mm; the structure's own measured section width stays on record (res.items[].width_mm). */
  var BAND_FRAC = 1 / 500, BAND_MAX = 2.5;"""),
 # 11-13. the four build call sites of the controller
 ("""      var res = NMSKCapCore.build(items, s.pl[f], {gap:1.0});""",
  """      var res = NMSKCapCore.build(items, s.pl[f], {gap:1.0, bandFrac:BAND_FRAC, bandMax:BAND_MAX});"""),
 ("""      var L = [], near = NMSKCapCore.build(use, pl.near, {gap:1.0, win:win, px:px}); NMSKCapCore.recolor(near, use); near._cut = null; L.push(near); tot += near.items.length;
      if (pl.far){ var far = NMSKCapCore.build(use, pl.far, {gap:1.0, win:win, px:px}); NMSKCapCore.recolor(far, use); far._cut = null; L.push(far); }""",
  """      var L = [], near = NMSKCapCore.build(use, pl.near, {gap:1.0, win:win, px:px, bandFrac:BAND_FRAC, bandMax:BAND_MAX}); NMSKCapCore.recolor(near, use); near._cut = null; L.push(near); tot += near.items.length;
      if (pl.far){ var far = NMSKCapCore.build(use, pl.far, {gap:1.0, win:win, px:px, bandFrac:BAND_FRAC, bandMax:BAND_MAX}); NMSKCapCore.recolor(far, use); far._cut = null; L.push(far); }"""),
 ("""      var L = [], near = NMSKCapCore.build(items, pl.near, {gap:1.0}); NMSKCapCore.recolor(near, items); near._cut = null; L.push(near);
      if (pl.far){ var far = NMSKCapCore.build(items, pl.far, {gap:1.0}); NMSKCapCore.recolor(far, items); far._cut = null; L.push(far); }""",
  """      var L = [], near = NMSKCapCore.build(items, pl.near, {gap:1.0, bandFrac:BAND_FRAC, bandMax:BAND_MAX}); NMSKCapCore.recolor(near, items); near._cut = null; L.push(near);
      if (pl.far){ var far = NMSKCapCore.build(items, pl.far, {gap:1.0, bandFrac:BAND_FRAC, bandMax:BAND_MAX}); NMSKCapCore.recolor(far, items); far._cut = null; L.push(far); }"""),
 # 14. the Cut-mode info line
 ("""    info.textContent = "Cut face: " + s.filled + " filled" + (s.outline_only ? ", " + s.outline_only + " outline only (open meshes)" : "") +
      (s.thin ? ", " + s.thin + " too thin to fill" : "") + " - " + (st.ms / 1000).toFixed(2) + " s";""",
  """    info.textContent = "Cut face: " + s.filled + " filled" + (s.band ? ", " + s.band + " thin drawn at a " + s.band_mm.toFixed(2) + " mm minimum width" : "") +
      (s.outline_only ? ", " + s.outline_only + " outline only (open meshes)" : "") +
      (s.thin ? ", " + s.thin + " too thin to fill" : "") + " - " + (st.ms / 1000).toFixed(2) + " s";"""),
 # 15. the module header
 ("""   Pure functions in NMSKCapCore (no DOM, runs under node); the controller NMSKCap(E) owns the toggle, the debounce and the camera button; the engine""",
  """   Q299: a section too thin for the raster (a 1 mm nerve, a 0.9 mm fascial sheet) and an open sheet that fails the parity test are drawn as a BAND of a
   minimum drawn width along their own contour segments (`band` / `bandFrac` / `bandMax`, controller default 1/500 of the section extent capped at 2.5 mm) --
   a thickened outline, never a fill; the structure's own measured section width stays on record as res.items[].width_mm.
   Pure functions in NMSKCapCore (no DOM, runs under node); the controller NMSKCap(E) owns the toggle, the debounce and the camera button; the engine"""),
]


def apply(text):
    done = 0
    for old, new in EDITS:
        if new in text:
            continue
        if text.count(old) != 1:
            raise SystemExit(f"Q299 patch: anchor not found exactly once ({text.count(old)}):\n{old[:160]}")
        text = text.replace(old, new)
        done += 1
    return text, done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(TARGET))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    p = Path(a.file)
    src = p.read_text(encoding="utf-8")
    out, done = apply(src)
    if a.check:
        print("up to date" if done == 0 else f"{done} edit(s) MISSING")
        sys.exit(0 if done == 0 else 1)
    if done:
        p.write_text(out, encoding="utf-8")
    print(f"{p}: {done} edit(s) applied" if done else f"{p}: up to date")


if __name__ == "__main__":
    main()
