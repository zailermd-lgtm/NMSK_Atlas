/* Cut-face fill ("cap") for Cut mode (Q227). CPU cross-section of the ACTUAL meshes with the cut plane:
   signed distance of the vertices -> triangle/plane segments -> gaps of the open ends closed (<= 1 mm) -> even-odd scanline fill of every
   structure into an id raster (painter order: tissue rank, then large before small, so vessels / nerves / bones are not hidden by muscle or fat)
   -> colour texture from the structures' CURRENT display colours + a crisp vector outline (the segments themselves, drawn as 1 px lines).
   The meshes are NOT watertight (Q197 note): rows with an odd number of crossings are counted (leak statistics), repaired from the nearest valid row
   when they are few, and a structure that fails the parity sanity test is drawn as an OUTLINE only (never a wrong fill).
   Pure functions in NMSKCapCore (no DOM, runs under node); the controller NMSKCap(E) owns the toggle, the debounce and the camera button; the engine
   (three.js Mesh + LineSegments / raw-WebGL textured quad) only uploads what the controller hands over through the adaptor E. */
var NMSKCapCore = (function(){
  "use strict";
  var RANK = {skin:0, fascia:1, bursa:1, other:2, fat:2, muscle:3, insertion:3, tendon:3, organ:4, viscera:4, lymph:4, cns:4,
              cartilage:5, joint:5, ligament:5, bone:6, nerve:7, vessel:8};       // painter order: lower first (underneath)
  function cross(a, b){ return [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]]; }
  function unit(a){ var l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0]/l, a[1]/l, a[2]/l]; }
  function basis(n){ var up = Math.abs(n[1]) < 0.99 ? [0,1,0] : [1,0,0], u = unit(cross(up, n)); return [u, cross(n, u)]; }   // same as the cut-mode overlay
  function rankOf(cat){ var r = RANK[cat]; return r == null ? 3 : r; }

  /* does the plane n.p = d cross the box? */
  function boxCrosses(bmin, bmax, n, d){
    var lo = -d, hi = -d;
    for (var k = 0; k < 3; k++){ var a = n[k]*bmin[k], b = n[k]*bmax[k]; lo += Math.min(a, b); hi += Math.max(a, b); }
    return lo < 0 && hi > 0;
  }

  /* ---- 1. triangles x plane -> segments between "edge points" (a point is identified by the mesh edge it lies on) ----
     returns null when no triangle straddles the plane, else {pu, pv, sa, sb} (plane coordinates u = p.U, v = p.V) */
  function slice(pos, idx, n, d, U, V){
    var nv = pos.length / 3, sd = new Float32Array(nv), nx = n[0], ny = n[1], nz = n[2], lo = 1e30, hi = -1e30, i;
    for (i = 0; i < nv; i++){
      var s = nx*pos[3*i] + ny*pos[3*i+1] + nz*pos[3*i+2] - d;
      if (s === 0) s = 1e-7;                                           // a vertex exactly on the plane counts as "above": consistent, so closed meshes give closed contours
      sd[i] = s; if (s < lo) lo = s; if (s > hi) hi = s;
    }
    if (lo > 0 || hi < 0) return null;
    var map = new Map(), pu = [], pv = [], sa = [], sb = [], nt = idx.length / 3;
    function pt(a, b){
      if (a > b){ var t0 = a; a = b; b = t0; }
      var key = a * nv + b, id = map.get(key);
      if (id !== undefined) return id;
      var s0 = sd[a], s1 = sd[b], t = s0 / (s0 - s1);
      var x = pos[3*a] + t * (pos[3*b] - pos[3*a]), y = pos[3*a+1] + t * (pos[3*b+1] - pos[3*a+1]), z = pos[3*a+2] + t * (pos[3*b+2] - pos[3*a+2]);
      pu.push(x*U[0] + y*U[1] + z*U[2]); pv.push(x*V[0] + y*V[1] + z*V[2]);
      id = pu.length - 1; map.set(key, id); return id;
    }
    for (var k = 0; k < nt; k++){
      var a = idx[3*k], b = idx[3*k+1], c = idx[3*k+2], pa = sd[a] > 0, pb = sd[b] > 0, pc = sd[c] > 0, p0, p1;
      if (pa === pb && pb === pc) continue;
      if (pa === pb){ p0 = pt(a, c); p1 = pt(b, c); }
      else if (pa === pc){ p0 = pt(a, b); p1 = pt(c, b); }
      else { p0 = pt(a, b); p1 = pt(a, c); }
      sa.push(p0); sb.push(p1);
    }
    if (!sa.length) return null;
    return {pu:pu, pv:pv, sa:sa, sb:sb};
  }

  /* ---- 2. drop duplicate segments (double-sided / duplicated faces would cancel in the even-odd count) ---- */
  function dedupe(S){
    var seen = new Set(), sa = [], sb = [], dup = 0;
    for (var k = 0; k < S.sa.length; k++){
      var a = S.sa[k], b = S.sb[k], lo = a < b ? a : b, hi = a < b ? b : a, key = lo * 67108864 + hi;
      if (seen.has(key)){ dup++; continue; }
      seen.add(key); sa.push(a); sb.push(b);
    }
    S.sa = sa; S.sb = sb; return dup;
  }

  /* ---- 3. close the open ends: a contour point of odd degree is an end of an open chain (a tear in the mesh, a duplicated vertex);
     ends closer than `gap` mm are joined (greedy, nearest pairs first). Returns {before, after, joined}. */
  function closeGaps(S, gap){
    var np = S.pu.length, deg = new Uint8Array(np), k, i;
    for (k = 0; k < S.sa.length; k++){ if (deg[S.sa[k]] < 255) deg[S.sa[k]]++; if (deg[S.sb[k]] < 255) deg[S.sb[k]]++; }
    var open = [];
    for (i = 0; i < np; i++) if (deg[i] & 1) open.push(i);
    var r = {before:open.length, after:open.length, joined:0};
    if (!open.length || !(gap > 0)) return r;
    var cell = gap, grid = new Map(), g2 = gap * gap;
    function key(cx, cy){ return cx * 1000003 + cy; }
    open.forEach(function(p){
      var kk = key(Math.floor(S.pu[p] / cell), Math.floor(S.pv[p] / cell)), l = grid.get(kk);
      if (l) l.push(p); else grid.set(kk, [p]);
    });
    var pairs = [];
    open.forEach(function(p){
      var cx = Math.floor(S.pu[p] / cell), cy = Math.floor(S.pv[p] / cell);
      for (var dx = -1; dx <= 1; dx++) for (var dy = -1; dy <= 1; dy++){
        var l = grid.get(key(cx + dx, cy + dy)); if (!l) continue;
        for (var j = 0; j < l.length; j++){
          var q = l[j]; if (q <= p) continue;
          var ex = S.pu[p] - S.pu[q], ey = S.pv[p] - S.pv[q], dd = ex*ex + ey*ey;
          if (dd <= g2) pairs.push([dd, p, q]);
        }
      }
    });
    pairs.sort(function(a, b){ return a[0] - b[0]; });
    var used = new Uint8Array(np);
    pairs.forEach(function(pr){
      if (used[pr[1]] || used[pr[2]]) return;
      used[pr[1]] = used[pr[2]] = 1; S.sa.push(pr[1]); S.sb.push(pr[2]); r.joined++;
    });
    r.after = open.length - 2 * r.joined;
    return r;
  }

  /* ---- 4. crossings of the segments with the pixel rows (row r has its centre at v0 + (r + 0.5) px); half-open so a vertex is counted once ---- */
  function crossings(S, g){
    var np = S.pu.length, xs = new Float64Array(np), ys = new Float64Array(np), inv = 1 / g.px, i, k;
    var ymin = 1e30, ymax = -1e30, xmin = 1e30, xmax = -1e30;
    for (i = 0; i < np; i++){
      xs[i] = (S.pu[i] - g.u0) * inv; ys[i] = (S.pv[i] - g.v0) * inv;
      if (ys[i] < ymin) ymin = ys[i]; if (ys[i] > ymax) ymax = ys[i];
      if (xs[i] < xmin) xmin = xs[i]; if (xs[i] > xmax) xmax = xs[i];
    }
    var r0 = Math.max(0, Math.ceil(ymin - 0.5)), r1 = Math.min(g.h - 1, Math.ceil(ymax - 0.5) - 1), nrow = r1 - r0 + 1;
    var out = {r0:r0, nrow:Math.max(0, nrow), start:null, x:null, cnt:null, xmin:xmin, xmax:xmax, ymin:ymin, ymax:ymax};
    if (nrow <= 0) return out;
    var cnt = new Int32Array(nrow + 1), ns = S.sa.length, ra, rb, y0, y1, lo, hi, r;
    for (k = 0; k < ns; k++){
      y0 = ys[S.sa[k]]; y1 = ys[S.sb[k]]; if (y0 === y1) continue;
      lo = y0 < y1 ? y0 : y1; hi = y0 < y1 ? y1 : y0;
      ra = Math.max(r0, Math.ceil(lo - 0.5)); rb = Math.min(r1, Math.ceil(hi - 0.5) - 1);
      for (r = ra; r <= rb; r++) cnt[r - r0 + 1]++;
    }
    var start = new Int32Array(nrow + 1);
    for (r = 0; r < nrow; r++) start[r + 1] = start[r] + cnt[r + 1];
    var fillp = start.slice(0, nrow), x = new Float64Array(start[nrow]), xa, xb, ya, yb;
    for (k = 0; k < ns; k++){
      xa = xs[S.sa[k]]; ya = ys[S.sa[k]]; xb = xs[S.sb[k]]; yb = ys[S.sb[k]]; if (ya === yb) continue;
      if (ya < yb){ lo = ya; hi = yb; } else { lo = yb; hi = ya; }
      ra = Math.max(r0, Math.ceil(lo - 0.5)); rb = Math.min(r1, Math.ceil(hi - 0.5) - 1);
      var sl = (xb - xa) / (yb - ya);
      for (r = ra; r <= rb; r++) x[fillp[r - r0]++] = xa + (r + 0.5 - ya) * sl;
    }
    out.start = start; out.x = x; out.cnt = cnt;
    return out;
  }

  function sortRow(x, a, b){                                  // sort x[a..b) in place (rows are short)
    var n = b - a, i, j, v;
    if (n > 24){ var sub = x.subarray(a, b); sub.sort(); return; }
    for (i = a + 1; i < b; i++){ v = x[i]; for (j = i - 1; j >= a && x[j] > v; j--) x[j+1] = x[j]; x[j+1] = v; }
  }

  /* ---- 5. even-odd fill of one structure into the id raster. Returns the parity statistics; paints nothing when the sanity test fails. ---- */
  function fillItem(S, g, ids, code, opt){
    var cr = crossings(S, g), st = {rows:0, odd:0, repaired:0, maxOddRun:0, painted:0, failed:false, reason:""};
    if (!cr.nrow || !cr.x) return st;
    var nrow = cr.nrow, r, i, odd = new Uint8Array(nrow), run = 0, nonEmpty = 0;
    for (r = 0; r < nrow; r++){
      var n = cr.start[r + 1] - cr.start[r];
      if (!n){ run = 0; continue; }
      nonEmpty++;
      if (n & 1){ odd[r] = 1; st.odd++; run++; if (run > st.maxOddRun) st.maxOddRun = run; } else run = 0;
    }
    st.rows = nonEmpty;
    if (!nonEmpty) return st;
    if (st.odd / nonEmpty > opt.maxOddFrac || st.maxOddRun > opt.maxOddRun){ st.failed = true; st.reason = "parity"; return st; }
    var w = g.w;
    function span(row, a, b, from){                              // paint pixels whose centre lies in [a, b) on raster row `row`
      var c0 = Math.max(0, Math.ceil(a - 0.5)), c1 = Math.min(w - 1, Math.ceil(b - 0.5) - 1);
      for (var c = c0; c <= c1; c++){ ids[row * w + c] = code; }
      return c1 >= c0 ? c1 - c0 + 1 : 0;
    }
    function paintRow(rowIdx, srcIdx){                           // paint the spans of crossing row srcIdx onto raster row of rowIdx
      var a = cr.start[srcIdx], b = cr.start[srcIdx + 1], px = 0;
      for (var q = a; q + 1 < b; q += 2) px += span(cr.r0 + rowIdx, cr.x[q], cr.x[q+1]);
      return px;
    }
    for (r = 0; r < nrow; r++){
      var a0 = cr.start[r], b0 = cr.start[r + 1];
      if (a0 === b0 || odd[r]) continue;
      sortRow(cr.x, a0, b0);
      st.painted += paintRow(r, r);
    }
    for (r = 0; r < nrow; r++){                                  // repair: an odd row takes the spans of the nearest valid row (<= maxOddRun rows away)
      if (!odd[r]) continue;
      var src = -1;
      for (i = 1; i <= opt.maxOddRun && src < 0; i++){
        if (r - i >= 0 && !odd[r - i] && cr.start[r - i + 1] > cr.start[r - i]) src = r - i;
        else if (r + i < nrow && !odd[r + i] && cr.start[r + i + 1] > cr.start[r + i]) src = r + i;
      }
      if (src >= 0){ st.painted += paintRow(r, src); st.repaired++; }
    }
    return st;
  }

  /* ---- 6. build everything for one plane ----
     items: [{key, name, cat, rgb:[r,g,b] 0..1, alpha, geom:function()->{pos,idx,bmin,bmax}}] (visible structures only)
     plane: {n:[unit normal], d: offset (n.p = d)}
     opt: {gap:1.0, minPx:0.4, maxDim:2048, px:override, maxOddFrac:0.12, maxOddRun:30, outline:true} */
  function build(items, plane, opt){
    opt = opt || {};
    var o = {gap:opt.gap == null ? 1.0 : opt.gap, minPx:opt.minPx || 0.4, maxDim:opt.maxDim || 2048, px:opt.px || 0,
             maxOddFrac:opt.maxOddFrac == null ? 0.12 : opt.maxOddFrac, maxOddRun:opt.maxOddRun || 30, outline:opt.outline !== false};
    var t0 = Date.now(), n = unit(plane.n), d = plane.d, UV = basis(n), U = UV[0], V = UV[1];
    var cut = [], k;
    items.forEach(function(it, ii){
      if (!(it.alpha >= 0.2)) return;                                  // a ghost / faded / (nearly) invisible structure is not cut: it must not hide what lies under it
      var gm = it.geom(); if (!gm || !boxCrosses(gm.bmin, gm.bmax, n, d)) return;
      var S = slice(gm.pos, gm.idx, n, d, U, V);
      if (!S) return;
      var dup = dedupe(S), cg = closeGaps(S, o.gap), np = S.pu.length, u0 = 1e30, u1 = -1e30, v0 = 1e30, v1 = -1e30;
      for (var i = 0; i < np; i++){ var u = S.pu[i], v = S.pv[i]; if (u < u0) u0 = u; if (u > u1) u1 = u; if (v < v0) v0 = v; if (v > v1) v1 = v; }
      cut.push({it:it, ii:ii, S:S, dup:dup, cg:cg, box:[u0, v0, u1, v1], rank:rankOf(it.cat), area:(u1 - u0) * (v1 - v0)});
    });
    var res = {n:n, d:d, U:U, V:V, O:[n[0]*d, n[1]*d, n[2]*d], w:0, h:0, px:0, u0:0, v0:0, ids:null, items:[], lines:null, stats:null, ms:0};
    var stats = {items_total:items.length, structures_cut:cut.length, filled:0, outline_only:0, thin:0, rows:0, odd_rows:0, odd_rows_in_filled:0, odd_rows_in_outline_only:0, rows_in_filled:0, filled_with_repair:0, repaired_rows:0,
                 open_ends_before:0, open_ends_after:0, joined:0, duplicate_segments:0, segments:0, by_cat:{}, outline_only_names:[]};
    if (!cut.length){ res.stats = stats; res.ms = Date.now() - t0; return res; }
    var U0 = 1e30, U1 = -1e30, V0 = 1e30, V1 = -1e30;
    cut.forEach(function(c){ U0 = Math.min(U0, c.box[0]); V0 = Math.min(V0, c.box[1]); U1 = Math.max(U1, c.box[2]); V1 = Math.max(V1, c.box[3]); });
    var ext = Math.max(U1 - U0, V1 - V0, 1), px = o.px || Math.max(o.minPx, ext / o.maxDim);
    var pad = 2 * px;
    res.px = px; res.u0 = U0 - pad; res.v0 = V0 - pad;
    res.w = Math.max(2, Math.ceil((U1 - U0 + 2 * pad) / px)); res.h = Math.max(2, Math.ceil((V1 - V0 + 2 * pad) / px));
    var ids = res.ids = new Int32Array(res.w * res.h), g = {px:px, u0:res.u0, v0:res.v0, w:res.w, h:res.h};
    cut.sort(function(a, b){ return a.rank - b.rank || b.area - a.area; });          // painter order: later paints over earlier
    cut.forEach(function(c, order){
      var code = order + 1, it = c.it, fs = fillItem(c.S, g, ids, code, o);
      c.order = order; c.stat = fs;
      var status = fs.failed ? "outline" : (fs.painted ? "filled" : "thin");
      var bc = stats.by_cat[it.cat] || (stats.by_cat[it.cat] = {cut:0, filled:0, outline_only:0, thin:0, odd_rows:0, rows:0});
      bc.cut++; bc[status === "filled" ? "filled" : status === "outline" ? "outline_only" : "thin"]++; bc.odd_rows += fs.odd; bc.rows += fs.rows;
      stats[status === "filled" ? "filled" : status === "outline" ? "outline_only" : "thin"]++;
      if (status === "outline" && stats.outline_only_names.length < 40) stats.outline_only_names.push(it.key);
      stats.rows += fs.rows; stats.odd_rows += fs.odd; stats.repaired_rows += fs.repaired;
      if (status === "outline") stats.odd_rows_in_outline_only += fs.odd;
      else { stats.odd_rows_in_filled += fs.odd; stats.rows_in_filled += fs.rows; if (fs.repaired) stats.filled_with_repair++; }
      stats.open_ends_before += c.cg.before; stats.open_ends_after += c.cg.after; stats.joined += c.cg.joined; stats.duplicate_segments += c.dup;
      stats.segments += c.S.sa.length;
      res.items.push({code:code, key:it.key, name:it.name, cat:it.cat, ii:c.ii, status:status, odd:fs.odd, rows:fs.rows, repaired:fs.repaired,
                      open_before:c.cg.before, open_after:c.cg.after});
      c.status = status;
    });
    stats.odd_row_fraction = stats.rows ? +(stats.odd_rows / stats.rows).toFixed(5) : 0;
    res.stats = stats; res._cut = cut; res._o = o;
    outlines(res, items);
    res.ms = Date.now() - t0;
    return res;
  }

  /* ---- 7. vector outline: the contour segments of every drawn structure in model coordinates (x6 floats per segment), hidden when another
     structure painted later covers the segment's midpoint ---- */
  function outlines(res, items){
    var cut = res._cut, n = 0, i;
    cut.forEach(function(c){ n += c.S.sa.length; });
    var pos = new Float32Array(n * 6), owner = new Int32Array(n), m = 0, U = res.U, V = res.V, O = res.O, w = res.w, h = res.h, inv = 1 / res.px;
    cut.forEach(function(c){
      var S = c.S, code = c.order + 1;
      for (var k = 0; k < S.sa.length; k++){
        var a = S.sa[k], b = S.sb[k], ua = S.pu[a], va = S.pv[a], ub = S.pu[b], vb = S.pv[b];
        var cx = Math.floor(((ua + ub) / 2 - res.u0) * inv), cy = Math.floor(((va + vb) / 2 - res.v0) * inv);
        if (cx >= 0 && cy >= 0 && cx < w && cy < h){ var oc = res.ids[cy * w + cx]; if (oc > code) continue; }
        pos[6*m] = O[0] + U[0]*ua + V[0]*va; pos[6*m+1] = O[1] + U[1]*ua + V[1]*va; pos[6*m+2] = O[2] + U[2]*ua + V[2]*va;
        pos[6*m+3] = O[0] + U[0]*ub + V[0]*vb; pos[6*m+4] = O[1] + U[1]*ub + V[1]*vb; pos[6*m+5] = O[2] + U[2]*ub + V[2]*vb;
        owner[m++] = code;
      }
    });
    res.lines = {pos:pos.subarray(0, m * 6), owner:owner.subarray(0, m), count:m};
  }

  /* ---- 8. colours: rgba texture and line colours from the structures' CURRENT display colours (a colour-only change needs no new cross-section) ---- */
  function recolor(res, items){
    if (!res.w) return res;
    var pal = new Uint32Array(res.items.length + 1), lc = new Float32Array(res.items.length * 3 + 3), by = items;
    res.items.forEach(function(r){
      var it = by[r.ii], a = Math.round(Math.max(0, Math.min(1, it.alpha)) * 255), c = it.rgb;
      var R = Math.round(Math.max(0, Math.min(1, c[0])) * 255), G = Math.round(Math.max(0, Math.min(1, c[1])) * 255), B = Math.round(Math.max(0, Math.min(1, c[2])) * 255);
      pal[r.code] = r.status === "filled" ? ((a << 24) | (B << 16) | (G << 8) | R) >>> 0 : 0;
      lc[3*r.code] = c[0] * 0.45; lc[3*r.code+1] = c[1] * 0.45; lc[3*r.code+2] = c[2] * 0.45;
    });
    var n = res.w * res.h;
    if (!res.rgba || res.rgba.length !== n * 4) res.rgba = new Uint8Array(n * 4);
    var px32 = new Uint32Array(res.rgba.buffer, res.rgba.byteOffset, n), ids = res.ids;
    for (var i = 0; i < n; i++) px32[i] = pal[ids[i]];
    var L = res.lines, col = new Float32Array(L.count * 6);
    for (var k = 0; k < L.count; k++){
      var o = L.owner[k];
      col[6*k] = col[6*k+3] = lc[3*o]; col[6*k+1] = col[6*k+4] = lc[3*o+1]; col[6*k+2] = col[6*k+5] = lc[3*o+2];
    }
    L.col = col;
    return res;
  }

  /* ---- 9. which structure lies at the plane point p (model coordinates)? null when the pixel is empty / outside the raster ---- */
  function lookup(res, p){
    if (!res || !res.w) return null;
    var u = p[0]*res.U[0] + p[1]*res.U[1] + p[2]*res.U[2], v = p[0]*res.V[0] + p[1]*res.V[1] + p[2]*res.V[2];
    var x = Math.floor((u - res.u0) / res.px), y = Math.floor((v - res.v0) / res.px);
    if (x < 0 || y < 0 || x >= res.w || y >= res.h) return null;
    var c = res.ids[y * res.w + x];
    return c ? res.items[c - 1] : null;
  }

  return {RANK:RANK, basis:basis, boxCrosses:boxCrosses, slice:slice, dedupe:dedupe, closeGaps:closeGaps, crossings:crossings,
          fillItem:fillItem, build:build, recolor:recolor, lookup:lookup, rankOf:rankOf};
})();

/* The controller. Adaptor E:
   cut() -> {on, kn, c, th} (the kept part is 0 <= kn.p + c <= th, th = 0: whole rest)   items() -> the VISIBLE structures [{key, name, cat, rgb, alpha, geom}]
   upload(face, res | null)  face 0 = the cut plane, 1 = the far face of a slice; res = NMSKCapCore.build() output after recolor() (null removes it)
   show(face, bool) hides / shows an uploaded face   lookAt(dirFromTarget, target, extent, free)   bounds() -> {min,max}   canvasRect()   redraw() */
function NMSKCap(E){
  "use strict";
  var $ = function(id){ return document.getElementById(id); };
  var btn = $("cut-fill"), look = $("cut-look"), info = $("cut-capinfo");
  var st = {on:false, res:[null, null], planeSig:"", itemsSig:"", palSig:"", timer:0, dirty:false, busy:false, builds:0, recolors:0, ms:0, msTotal:0, stats:null, showing:false};
  var items = [];
  function pref(v){ try { if (v === undefined) return localStorage.getItem("nmsk-capfill") === "1"; localStorage.setItem("nmsk-capfill", v ? "1" : "0"); } catch (err){} return false; }
  function r4(v){ return Math.round(v * 1e4) / 1e4; }
  function planes(){
    var c = E.cut();
    if (!c || !c.on) return null;
    var out = [{n:c.kn.slice(), d:-c.c}];
    if (c.th > 0) out.push({n:c.kn.slice(), d:c.th - c.c});
    return out;
  }
  function sigs(){
    var pl = planes(), ps = pl ? pl.map(function(p){ return p.n.map(r4).join(",") + "|" + r4(p.d); }).join(";") : "";
    var is = "", pal = "";
    items.forEach(function(it){ is += it.key + (it.alpha >= 0.2 ? "" : "~") + ";"; pal += it.rgb.map(function(x){ return Math.round(x * 255); }).join(",") + ":" + Math.round(it.alpha * 100) + ";"; });
    return {plane:ps, items:is, pal:pal, pl:pl};
  }
  function ui(){
    if (btn){ btn.setAttribute("aria-pressed", String(st.on)); btn.classList.toggle("on", st.on); }
    if (!info) return;
    if (!st.on){ info.textContent = ""; return; }
    var s = st.stats;
    if (!s){ info.textContent = st.busy ? "Filling the cut face..." : "The plane does not cut any shown structure."; return; }
    info.textContent = "Cut face: " + s.filled + " filled" + (s.outline_only ? ", " + s.outline_only + " outline only (open meshes)" : "") +
      (s.thin ? ", " + s.thin + " too thin to fill" : "") + " - " + (st.ms / 1000).toFixed(2) + " s";
  }
  function clear(){
    for (var f = 0; f < 2; f++){ if (st.res[f]) E.upload(f, null); st.res[f] = null; }
    st.stats = null; st.planeSig = st.itemsSig = st.palSig = ""; st.showing = false;
  }
  function flush(){
    st.timer = 0; st.dirty = false;
    if (!st.on){ clear(); ui(); return; }
    items = E.items();
    var s = sigs();
    if (!s.pl){ clear(); ui(); return; }
    var same = s.plane === st.planeSig && s.items === st.itemsSig;
    if (same && s.pal === st.palSig){ for (var f0 = 0; f0 < 2; f0++) if (st.res[f0]) E.show(f0, true); st.showing = true; ui(); return; }
    var t0 = Date.now();
    if (same){                                             // only colours / opacities changed: no new cross-section needed
      for (var f1 = 0; f1 < 2; f1++) if (st.res[f1]){ NMSKCapCore.recolor(st.res[f1], items); E.upload(f1, st.res[f1]); E.show(f1, true); }
      st.palSig = s.pal; st.recolors++; ui(); return;
    }
    st.busy = true; ui();
    var stats = null, tot = {filled:0, outline_only:0, thin:0, structures_cut:0};
    for (var f = 0; f < 2; f++){
      if (!s.pl[f]){ if (st.res[f]){ E.upload(f, null); st.res[f] = null; } continue; }
      var res = NMSKCapCore.build(items, s.pl[f], {gap:1.0});
      NMSKCapCore.recolor(res, items); res._cut = null;           // the per-structure contours are not needed any more (the lines and the id raster are)
      st.res[f] = res; E.upload(f, res); E.show(f, true);
      if (f === 0) stats = res.stats;
    }
    st.stats = stats; st.planeSig = s.plane; st.itemsSig = s.items; st.palSig = s.pal; st.builds++;
    st.ms = Date.now() - t0; st.msTotal += st.ms; st.busy = false; st.showing = true; ui();
  }
  function schedule(delay){
    if (st.timer){ st.dirty = true; return; }
    st.timer = setTimeout(flush, delay);
  }
  var api = {
    /* the engine calls these: a plane move / cut on-off, any visibility or colour change */
    planeChanged: function(){
      if (!st.on) return;
      var c = E.cut(), pl = planes();
      if (!pl){ clear(); ui(); return; }
      var s = sigs();                                      // hide the old face at once: it no longer lies in the plane
      if (s.plane !== st.planeSig){ for (var f = 0; f < 2; f++) if (st.res[f]) E.show(f, false); st.showing = false; }
      schedule(90);
    },
    itemsChanged: function(){ if (st.on) schedule(40); },
    set: function(on){
      st.on = !!on; pref(st.on); if (E.redraw) E.redraw();
      if (!on){ if (st.timer){ clearTimeout(st.timer); st.timer = 0; } clear(); }
      else schedule(0);
      ui();
    },
    isOn: function(){ return st.on; },
    result: function(f){ return st.res[f || 0]; },
    /* ray (model coordinates) against the uploaded faces: the nearest filled texel */
    hit: function(o, d){
      var best = null;
      for (var f = 0; f < 2; f++){
        var res = st.res[f]; if (!res || !st.showing) continue;
        var nd = res.n[0]*d[0] + res.n[1]*d[1] + res.n[2]*d[2]; if (Math.abs(nd) < 1e-9) continue;
        var t = (res.d - (res.n[0]*o[0] + res.n[1]*o[1] + res.n[2]*o[2])) / nd; if (!(t > 0)) continue;
        var p = [o[0] + d[0]*t, o[1] + d[1]*t, o[2] + d[2]*t], r = NMSKCapCore.lookup(res, p);
        if (r && (!best || t < best.t)) best = {t:t, point:p, item:r, face:f};
      }
      return best;
    },
    /* the part of the canvas the cut panel does not cover (the camera frames the cut face there): centre and size as fractions of the canvas */
    freeRegion: function(){
      var out = {cx:0.5, cy:0.5, w:1, h:1}, p = $("cut-panel"), c = E.canvasRect ? E.canvasRect() : null;
      if (!c || !p || p.hidden || !c.width || !c.height) return out;
      var r = p.getBoundingClientRect();
      if (!(r.width > 0) || Math.min(c.right, r.right) <= Math.max(c.left, r.left) || Math.min(c.bottom, r.bottom) <= Math.max(c.top, r.top)) return out;
      var cand = [];
      if (r.top - c.top > 0.2 * c.height) cand.push([c.left, c.top, c.right, r.top]);
      if (r.left - c.left > 0.2 * c.width) cand.push([c.left, c.top, r.left, c.bottom]);
      if (c.bottom - r.bottom > 0.2 * c.height) cand.push([c.left, r.bottom, c.right, c.bottom]);
      var best = null, ba = 0;
      cand.forEach(function(q){ var a = (q[2] - q[0]) * (q[3] - q[1]); if (a > ba){ ba = a; best = q; } });
      if (!best) return out;
      return {cx:((best[0] + best[2]) / 2 - c.left) / c.width, cy:((best[1] + best[3]) / 2 - c.top) / c.height, w:(best[2] - best[0]) / c.width, h:(best[3] - best[1]) / c.height};
    },
    lookAtFace: function(){
      var c = E.cut(); if (!c || !c.on) return false;
      var bnd = E.bounds(), ctr = [(bnd.min[0] + bnd.max[0]) / 2, (bnd.min[1] + bnd.max[1]) / 2, (bnd.min[2] + bnd.max[2]) / 2];
      var kn = c.kn, sdist = kn[0]*ctr[0] + kn[1]*ctr[1] + kn[2]*ctr[2] + c.c, tgt = [ctr[0] - sdist*kn[0], ctr[1] - sdist*kn[1], ctr[2] - sdist*kn[2]], ext = 0;
      var r = st.res[0];
      if (r && r.w){                                       // centre of what was actually cut
        var uc = r.u0 + r.w * r.px / 2, vc = r.v0 + r.h * r.px / 2;
        tgt = [r.O[0] + r.U[0]*uc + r.V[0]*vc, r.O[1] + r.U[1]*uc + r.V[1]*vc, r.O[2] + r.U[2]*uc + r.V[2]*vc];
        ext = Math.max(r.w, r.h) * r.px;
      }
      E.lookAt([-kn[0], -kn[1], -kn[2]], tgt, ext, api.freeRegion());        // the eye lies on the REMOVED side, looking along the kept normal; the face is framed in the free part of the canvas
      return true;
    },
    state: function(){
      return {on:st.on, showing:st.showing, builds:st.builds, recolors:st.recolors, ms:st.ms, msTotal:st.msTotal, busy:st.busy, stats:st.stats,
              faces:st.res.map(function(r){ return r ? {w:r.w, h:r.h, px:r.px, items:r.items.length, lines:r.lines.count, ms:r.ms} : null; })};
    },
    flushNow: function(){ if (st.timer){ clearTimeout(st.timer); st.timer = 0; } flush(); }
  };
  if (btn) btn.addEventListener("click", function(){ api.set(!st.on); });
  if (look) look.addEventListener("click", function(){ api.lookAtFace(); });
  if (pref()) api.preferred = true;
  return api;
}
