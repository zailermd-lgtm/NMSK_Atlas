/* Structure labels with callouts, abbreviations and a legend window (Q236). One controller for both viewers. The engine is reached only through the adaptor E:
   modelId()  structures() -> [{id,name,side:'l'|'r'|'m'|'',cat}] (one per entity, list order)   alphas() -> Float32Array(n) opacity of what is drawn now (0 = not drawn;
   hidden / layer off / source facet / isolate / side filter all give 0; fade, ghost and x-ray give their opacity)   color(i) -> [r,g,b] 0..255 as drawn
   geometry(i) -> [{pos:Float32Array, idx:Uint16Array}] (model frame, millimetres)   view() -> {m:Array16 column-major model->clip, eye:[x,y,z], rect:{left,top,width,height}}
   idImage(all, w) -> {w,h,ids:Uint16Array|Int32Array} structure index + 1 per pixel, row 0 = top (all=false: the opaque structures only, all=true: everything drawn at >= 20 %);
   it honours the cut plane / slab / isolation exactly like the screen, so a structure that is clipped away or fully hidden behind others has no pixel   cut() -> {on,kn,c,th}
   capHit(o,d) -> {point,item:{key}} | null (the filled cut face, when it is on)   fillCut()   ray(clientX,clientY) -> {o,d} (model frame)   selected() marked() hovered() select(id)
   bg() -> [r,g,b]   obstacles() -> [Element] (HUD panels labels and windows keep clear of)   canvasRect() -> DOMRect   redraw()   toolbar + toolClass   isPhone().
   The engine calls update() at the end of every draw, hover(id) when the pointer moves over another structure, and dirty() when something that is not in the view
   changed. Nothing here changes geometry, colours or visibility of the model: the labels are a DOM / SVG overlay.
   Vessels and nerves (Q240): the page's table #nmsk-calibre {v:1,c:{id:[kind a|v|n, diameter_mm, level 1..4, promoted]}} (scripts/anatomy/q240/make_calibre.py) gives each artery /
   vein / nerve its calibre and level; Arteries / Nerves are labelled by default in Visible and All (Veins on request), filtered by the level and the minimum diameter, main
   trunks first and with a reserved share of the label budget; their anchor is the middle of the longest visible run, not the centroid; "Hide vessel / nerve labels" switches all off.
   Pure geometry (silhouette mask, callout placement without overlaps / crossings) lives in NMSKLabelsCore so it can be tested without a browser. */
var NMSKLabelsCore = (function(){
  "use strict";
  /* occ: Uint8Array w*h (non-zero = body). The mask maps grid cell (x,y) to screen x = ox + x*sx, y = oy + y*sy. A summed-area table answers "does this rectangle touch the body" in O(1). */
  function makeMask(occ, w, h, ox, oy, sx, sy){
    var W1 = w + 1, S = new Int32Array(W1 * (h + 1)), x, y, row, minx = w, maxx = -1, miny = h, maxy = -1, n = 0;
    for (y = 0; y < h; y++){
      row = 0;
      for (x = 0; x < w; x++){
        if (occ[y * w + x]){ row++; n++; if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y; }
        S[(y + 1) * W1 + x + 1] = S[y * W1 + x + 1] + row;
      }
    }
    var M = {w:w, h:h, S:S, ox:ox, oy:oy, sx:sx, sy:sy, n:n};
    if (n){ M.x0 = ox + minx * sx; M.x1 = ox + (maxx + 1) * sx; M.y0 = oy + miny * sy; M.y1 = oy + (maxy + 1) * sy; M.bx = (M.x0 + M.x1) / 2; M.by = (M.y0 + M.y1) / 2; }
    return M;
  }
  function maskCount(M, X0, Y0, X1, Y1){
    var x0 = Math.max(0, Math.floor((X0 - M.ox) / M.sx)), y0 = Math.max(0, Math.floor((Y0 - M.oy) / M.sy)),
        x1 = Math.min(M.w, Math.ceil((X1 - M.ox) / M.sx)), y1 = Math.min(M.h, Math.ceil((Y1 - M.oy) / M.sy));
    if (x1 <= x0 || y1 <= y0) return 0;
    var W1 = M.w + 1, S = M.S;
    return S[y1 * W1 + x1] - S[y0 * W1 + x1] - S[y1 * W1 + x0] + S[y0 * W1 + x0];
  }
  function segX(a, b){            // proper intersection of the segments a = {x1,y1,x2,y2}, b
    function o(px, py, qx, qy, rx, ry){ return (qx - px) * (ry - py) - (qy - py) * (rx - px); }
    var d1 = o(a.x1, a.y1, a.x2, a.y2, b.x1, b.y1), d2 = o(a.x1, a.y1, a.x2, a.y2, b.x2, b.y2),
        d3 = o(b.x1, b.y1, b.x2, b.y2, a.x1, a.y1), d4 = o(b.x1, b.y1, b.x2, b.y2, a.x2, a.y2);
    return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
  }
  function edgePoint(q, w, h, ax, ay){   // where the leader meets the label box: the point of the box outline nearest to the anchor (side midpoint region for anchors beside the box, top / bottom edge for anchors above / below)
    var x0 = q.x - w / 2, x1 = q.x + w / 2, y0 = q.y - h / 2, y1 = q.y + h / 2;
    if (ax >= x0 && ax <= x1 && ay >= y0 && ay <= y1) return {x:ax, y:ay};          // the anchor is inside the box
    var dx = ax < x0 ? x0 - ax : (ax > x1 ? ax - x1 : 0), dy = ay < y0 ? y0 - ay : (ay > y1 ? ay - y1 : 0);
    if (dx >= dy) return {x:ax < x0 ? x0 : x1, y:Math.max(y0 + Math.min(3, h / 2), Math.min(y1 - Math.min(3, h / 2), ay))};
    return {x:Math.max(x0 + Math.min(3, w / 2), Math.min(x1 - Math.min(3, w / 2), ax)), y:ay < y0 ? y0 : y1};
  }
  function boxesOverlap(a, b, pad){
    return Math.abs(a.x - b.x) < (a.w + b.w) / 2 + pad && Math.abs(a.y - b.y) < (a.h + b.h) / 2 + pad;
  }
  /* Callout placement. P = {labels:[{id,ax,ay,w,h,prio,px,py}], mask, frame:{x0,y0,x1,y1}, obstacles:[{x0,y0,x1,y1}], pad, mpad, iters}
     Each label is put just outside the body silhouette (the mask), along the outward normal of the body's bounding ellipse at its anchor (the nearest free place
     of a few tried directions), then the boxes are pulled apart (no two overlap, none touches the body, an obstacle or leaves the frame), and finally pairs whose
     leader lines cross swap places. Result: [{id,x,y,w,h,ok,forced,lx,ly}] (x,y = box centre, lx,ly = where the leader meets the box). Deterministic. */
  function solve(P){
    var L = P.labels, n = L.length, M = P.mask && P.mask.n ? P.mask : null, F = P.frame, O = P.obstacles || [], pad = P.pad == null ? 2 : P.pad,
        mpad = P.mpad == null ? 3 : P.mpad, i, j, k;
    var cx = M ? M.bx : (F.x0 + F.x1) / 2, cy = M ? M.by : (F.y0 + F.y1) / 2;
    var hw = M ? Math.max(8, (M.x1 - M.x0) / 2) : 100, hh = M ? Math.max(8, (M.y1 - M.y0) / 2) : 100;
    var maxS = Math.hypot(F.x1 - F.x0, F.y1 - F.y0);
    var R = [];
    function inFrame(q, w, h){ return q.x - w / 2 >= F.x0 && q.x + w / 2 <= F.x1 && q.y - h / 2 >= F.y0 && q.y + h / 2 <= F.y1; }
    function hitObs(q, w, h){
      for (var o = 0; o < O.length; o++){ var b = O[o]; if (q.x - w / 2 < b.x1 && q.x + w / 2 > b.x0 && q.y - h / 2 < b.y1 && q.y + h / 2 > b.y0) return b; }
      return null;
    }
    function hitBody(q, w, h){ return !!M && maskCount(M, q.x - w / 2 - mpad, q.y - h / 2 - mpad, q.x + w / 2 + mpad, q.y + h / 2 + mpad) > 0; }
    function free(q, w, h){ return inFrame(q, w, h) && !hitObs(q, w, h) && !hitBody(q, w, h); }
    function clampF(q, w, h){ q.x = Math.max(F.x0 + w / 2, Math.min(F.x1 - w / 2, q.x)); q.y = Math.max(F.y0 + h / 2, Math.min(F.y1 - h / 2, q.y)); }
    /* 1) target: the nearest free place along a few directions around the outward normal of the bounding ellipse */
    var DEL = [0, 0.44, -0.44, 0.87, -0.87, 1.4, -1.4];
    for (i = 0; i < n; i++){
      var l = L[i], nx = (l.ax - cx) / (hw * hw), ny = (l.ay - cy) / (hh * hh);
      var a0 = Math.abs(nx) + Math.abs(ny) < 1e-12 ? (i % 2 ? 0 : Math.PI) : Math.atan2(ny, nx), best = null, cands = [];
      for (k = 0; k < DEL.length; k++){
        var ang = a0 + DEL[k], dx = Math.cos(ang), dy = Math.sin(ang);
        for (var s = 0; s <= maxS; s += 6){
          var q = {x:l.ax + dx * s, y:l.ay + dy * s};
          if (free(q, l.w, l.h)){
            var cost = s + Math.abs(DEL[k]) * 45 + (l.px != null ? 0.3 * Math.hypot(q.x - l.px, q.y - l.py) : 0), cd = {x:q.x, y:q.y, cost:cost, dx:dx, dy:dy};
            cands.push(cd);
            if (!best || cost < best.cost) best = cd;
            break;
          }
          if (!inFrame(q, l.w, l.h) && s > 12 && (q.x < F.x0 - 400 || q.x > F.x1 + 400 || q.y < F.y0 - 400 || q.y > F.y1 + 400)) break;
        }
      }
      var forced = false, dropped = false;
      if (!best){                      // the body fills the frame here (zoomed in): the label sits on the body at the frame edge nearest the anchor (not under a HUD panel; if there is no such place it is left out)
        forced = true;
        var edges = [{x:F.x0 + l.w / 2, y:l.ay}, {x:F.x1 - l.w / 2, y:l.ay}, {x:l.ax, y:F.y0 + l.h / 2}, {x:l.ax, y:F.y1 - l.h / 2}], bf = null;
        edges.forEach(function(q){
          clampF(q, l.w, l.h); if (hitObs(q, l.w, l.h)) return;
          var dd = Math.hypot(q.x - l.ax, q.y - l.ay); if (!bf || dd < bf.dd) bf = {x:q.x, y:q.y, dd:dd};
        });
        if (bf) best = {x:bf.x, y:bf.y, cost:0, dx:Math.cos(a0), dy:Math.sin(a0)};
        else { best = {x:l.ax, y:l.ay, cost:0, dx:Math.cos(a0), dy:Math.sin(a0)}; dropped = true; }
      }
      R.push({id:l.id, ax:l.ax, ay:l.ay, w:l.w, h:l.h, prio:l.prio || 0, tx:best.x, ty:best.y, dx:best.dx, dy:best.dy, x:best.x, y:best.y, cands:cands, ok:!dropped, forced:forced});
    }
    /* 2) relax: pull the boxes apart, keep them off the body / obstacles / outside of the frame, spring back toward the targets */
    function enforce(r){
      clampF(r, r.w, r.h);
      var ob = hitObs(r, r.w, r.h);
      if (ob){                         // out of the nearest side of the obstacle
        var dl = r.x + r.w / 2 - ob.x0, dr = ob.x1 - (r.x - r.w / 2), du = r.y + r.h / 2 - ob.y0, dd = ob.y1 - (r.y - r.h / 2), mn = Math.min(dl, dr, du, dd);
        if (mn === dl) r.x -= dl; else if (mn === dr) r.x += dr; else if (mn === du) r.y -= du; else r.y += dd;
        clampF(r, r.w, r.h);
      }
      if (r.forced) return;
      if (hitBody(r, r.w, r.h)){       // back out of the body along the outward direction of the target
        for (var st = 0; st < 40 && hitBody(r, r.w, r.h); st++){ r.x += r.dx * 3; r.y += r.dy * 3; }
        clampF(r, r.w, r.h);
      }
    }
    var iters = P.iters || (n > 80 ? 14 : 32);
    for (var it = 0; it < iters; it++){
      var moved = false;
      for (i = 0; i < n; i++) for (j = i + 1; j < n; j++){
        var a = R[i], b = R[j];
        var ox = (a.w + b.w) / 2 + pad - Math.abs(a.x - b.x), oy = (a.h + b.h) / 2 + pad - Math.abs(a.y - b.y);
        if (ox <= 0 || oy <= 0) continue;
        moved = true;
        var wa = 1 / (1 + a.prio * 2), wb = 1 / (1 + b.prio * 2), sa = wa / (wa + wb), sb = 1 - sa;
        if (ox < oy){ var sg = a.x === b.x ? (i < j ? 1 : -1) : (a.x > b.x ? 1 : -1); a.x += sg * ox * sa; b.x -= sg * ox * sb; }
        else { var sg2 = a.y === b.y ? (i < j ? 1 : -1) : (a.y > b.y ? 1 : -1); a.y += sg2 * oy * sa; b.y -= sg2 * oy * sb; }
      }
      for (i = 0; i < n; i++){
        var r = R[i];
        if (!r.forced){ r.x += (r.tx - r.x) * 0.06; r.y += (r.ty - r.y) * 0.06; }
        enforce(r);
      }
      if (!moved && it > 4) break;
    }
    /* columns beside a narrow body fill up: a vertical sweep (top to bottom, then bottom to top) removes what the pairwise pushes left, then the constraints are enforced again */
    function sweep(){
      var ix = [], u, v;
      for (u = 0; u < n; u++) if (!R[u].forced) ix.push(u);
      ix.sort(function(p1, p2){ return R[p1].y - R[p2].y || p1 - p2; });
      for (u = 0; u < ix.length; u++){
        var ra = R[ix[u]];
        for (v = 0; v < u; v++){ var rb = R[ix[v]]; if (Math.abs(ra.x - rb.x) < (ra.w + rb.w) / 2 + pad){ var need = rb.y + (rb.h + ra.h) / 2 + pad; if (ra.y < need) ra.y = need; } }
      }
      for (u = ix.length - 1; u >= 0; u--){
        var rc = R[ix[u]]; if (rc.y > F.y1 - rc.h / 2) rc.y = F.y1 - rc.h / 2;
        for (v = u + 1; v < ix.length; v++){ var rd = R[ix[v]]; if (Math.abs(rc.x - rd.x) < (rc.w + rd.w) / 2 + pad){ var need2 = rd.y - (rd.h + rc.h) / 2 - pad; if (rc.y > need2) rc.y = need2; } }
      }
    }
    for (var rd2 = 0; rd2 < 4; rd2++){ sweep(); for (i = 0; i < n; i++) enforce(R[i]); }
    /* 3) leader lines must not cross: a crossing pair swaps places, or one of the two moves to another of its candidate places, when that is free and removes crossings */
    function lead(r, pos){ var q = pos || r, e = edgePoint(q, r.w, r.h, r.ax, r.ay); return {x1:r.ax, y1:r.ay, x2:e.x, y2:e.y}; }
    function clashes(r, pos, skip){
      var q = {x:pos.x, y:pos.y, w:r.w, h:r.h};
      for (var u = 0; u < n; u++){ if (R[u] === r || R[u] === skip || !R[u].ok) continue; if (boxesOverlap(q, R[u], pad)) return true; }
      return false;
    }
    function crossings(r, pos, skip){
      var a = lead(r, pos), c = 0;
      for (var u = 0; u < n; u++){ if (R[u] === r || R[u] === skip || !R[u].ok || R[u].forced) continue; if (segX(a, lead(R[u]))) c++; }
      return c;
    }
    /* a swap that shortens the two leaders also removes the crossing between them (triangle inequality): do all of those first, which untangles a crowded column */
    function dist2(r, pos){ return Math.hypot(pos.x - r.ax, pos.y - r.ay); }
    for (var sp = 0; sp < 8; sp++){
      var swapped = false;
      for (i = 0; i < n; i++){
        var A0 = R[i]; if (A0.forced) continue;
        for (j = i + 1; j < n; j++){
          var B0 = R[j]; if (B0.forced) continue;
          var gain = dist2(A0, A0) + dist2(B0, B0) - dist2(A0, B0) - dist2(B0, A0);
          if (gain < 1.5) continue;
          var qa = {x:A0.x, y:A0.y}, qb = {x:B0.x, y:B0.y};
          if (free(qb, A0.w, A0.h) && free(qa, B0.w, B0.h) && !clashes(A0, qb, B0) && !clashes(B0, qa, A0) &&
              !boxesOverlap({x:qb.x, y:qb.y, w:A0.w, h:A0.h}, {x:qa.x, y:qa.y, w:B0.w, h:B0.h}, pad)){
            A0.x = qb.x; A0.y = qb.y; B0.x = qa.x; B0.y = qa.y; swapped = true;
          }
        }
      }
      if (!swapped) break;
    }
    for (var pass = 0; pass < 4; pass++){
      var any = false;
      for (i = 0; i < n; i++){
        var A = R[i]; if (A.forced) continue;
        var ca = crossings(A, A, null); if (!ca) continue;
        var fixed = false;
        for (j = 0; j < n && !fixed; j++){                      // swap with a label whose leader crosses ours
          var B = R[j]; if (j === i || B.forced || !segX(lead(A), lead(B))) continue;
          var pa = {x:A.x, y:A.y}, pb = {x:B.x, y:B.y}, before = crossings(A, pa, B) + crossings(B, pb, A) + 1;
          if (free(pb, A.w, A.h) && free(pa, B.w, B.h) && !clashes(A, pb, B) && !clashes(B, pa, A) && crossings(A, pb, B) + crossings(B, pa, A) + (segX(lead(A, pb), lead(B, pa)) ? 1 : 0) < before){
            A.x = pb.x; A.y = pb.y; B.x = pa.x; B.y = pa.y; fixed = true; any = true;
          }
        }
        if (fixed) continue;
        var bestC = null;
        for (k = 0; k < A.cands.length; k++){                   // or move to another candidate place
          var cd = A.cands[k]; if (Math.abs(cd.x - A.x) < 1 && Math.abs(cd.y - A.y) < 1) continue;
          if (!free(cd, A.w, A.h) || clashes(A, cd, null)) continue;
          var cc = crossings(A, cd, null);
          if (cc < ca && (!bestC || cc < bestC.cc || (cc === bestC.cc && cd.cost < bestC.cd.cost))) bestC = {cd:cd, cc:cc};
        }
        if (bestC){ A.x = bestC.cd.x; A.y = bestC.cd.y; A.dx = bestC.cd.dx; A.dy = bestC.cd.dy; A.tx = A.x; A.ty = A.y; any = true; }
      }
      if (!any) break;
    }
    for (i = 0; i < n; i++){ var rf = R[i]; if (rf.forced ? (!inFrame(rf, rf.w, rf.h) || !!hitObs(rf, rf.w, rf.h)) : !free(rf, rf.w, rf.h)) rf.ok = false; }      // an enforcement that pushed one box into another constraint: that label is left out
    /* 4) whatever still overlaps loses (lower priority first); the rest is final */
    for (i = 0; i < n; i++){
      if (!R[i].ok) continue;
      for (j = 0; j < n; j++){
        if (i === j || !R[j].ok) continue;
        if (boxesOverlap(R[i], R[j], 0.5)){
          var loser = (R[i].prio < R[j].prio || (R[i].prio === R[j].prio && i > j)) ? R[i] : R[j];
          loser.ok = false;
          if (loser === R[i]) break;
        }
      }
    }
    for (i = 0; i < n; i++){ var e = edgePoint(R[i], R[i].w, R[i].h, R[i].ax, R[i].ay); R[i].lx = e.x; R[i].ly = e.y; }
    return R;
  }
  return {makeMask:makeMask, maskCount:maskCount, segX:segX, edgePoint:edgePoint, solve:solve};
})();

function NMSKLabels(E){
  "use strict";
  var $ = function(id){ return document.getElementById(id); };
  var NS = "http://www.w3.org/2000/svg", KEY = "nmsk.labels.v1";
  var AMIN = 0.2, OPQ = 0.6, ALLCAP = 160, SEL_CAP = 80, BUF_MIN = 320, BUF_MAX = 640, CATW = {skin:0.15, fascia:0.6};
  var S = E.structures(), N = S.length, idx = {};
  S.forEach(function(s, i){ idx[s.id] = i; });
  var MODES = {off:1, sel:1, vis:1, all:1}, TEXTS = {full:1, abbr:1}, CALLS = {auto:1, out:1, "in":1}, COLS = {own:1, neutral:1}, SIZES = {S:[250, 220], M:[350, 340], L:[520, 520]};
  function dflt(){
    var ph = !!(E.isPhone && E.isPhone());
    return {mode:"off", text:"full", callout:"auto", density:ph ? 12 : 24, font:ph ? 11 : 12, colour:"own", side:true, occl:true,
            vn:{hide:false, a:true, v:false, n:true, lva:2, lvn:2, da:0, dn:0},
            lg:{open:false, x:null, y:null, w:350, h:340, font:13, only:"shown", size:"M"}, pn:{x:null, y:null, min:false}};
  }
  var P = dflt();
  /* ---- storage: a convenience that may be blocked (private window, artifact origin); the settings always live in memory too ---- */
  var storageOK = true;
  function num(v, lo, hi, d){ v = Number(v); return isFinite(v) ? Math.max(lo, Math.min(hi, v)) : d; }
  function restore(){
    var r = null;
    try { var t = localStorage.getItem(KEY); r = t ? JSON.parse(t) : null; storageOK = true; } catch (err){ storageOK = false; r = null; }
    if (!r || typeof r !== "object") return;
    if (MODES[r.mode]) P.mode = r.mode;
    if (TEXTS[r.text]) P.text = r.text;
    if (CALLS[r.callout]) P.callout = r.callout;
    if (COLS[r.colour]) P.colour = r.colour;
    P.density = Math.round(num(r.density, 3, 120, P.density)); P.font = Math.round(num(r.font, 9, 22, P.font));
    if (typeof r.side === "boolean") P.side = r.side;
    if (typeof r.occl === "boolean") P.occl = r.occl;
    var vv = r.vn;
    if (vv && typeof vv === "object"){
      ["hide", "a", "v", "n"].forEach(function(k){ if (typeof vv[k] === "boolean") P.vn[k] = vv[k]; });
      P.vn.lva = Math.round(num(vv.lva, 1, 4, P.vn.lva)); P.vn.lvn = Math.round(num(vv.lvn, 1, 4, P.vn.lvn)); P.vn.da = num(vv.da, 0, 20, 0); P.vn.dn = num(vv.dn, 0, 12, 0);
    }
    var g = r.lg;
    if (g && typeof g === "object"){
      P.lg.open = g.open === true; P.lg.w = Math.round(num(g.w, 200, 900, P.lg.w)); P.lg.h = Math.round(num(g.h, 140, 900, P.lg.h)); P.lg.font = Math.round(num(g.font, 10, 24, P.lg.font));
      if (g.only === "shown" || g.only === "all") P.lg.only = g.only;
      if (SIZES[g.size]) P.lg.size = g.size;
      P.lg.x = g.x == null ? null : num(g.x, -2000, 5000, null); P.lg.y = g.y == null ? null : num(g.y, -2000, 5000, null); P.lg.user = P.lg.x != null && P.lg.y != null;
    }
    var q = r.pn;
    if (q && typeof q === "object"){ P.pn.x = q.x == null ? null : num(q.x, -2000, 5000, null); P.pn.y = q.y == null ? null : num(q.y, -2000, 5000, null); P.pn.min = q.min === true; P.pn.user = P.pn.x != null && P.pn.y != null; }
  }
  function persist(){
    try {
      var c = JSON.parse(JSON.stringify(P)); if (!P.lg.user){ c.lg.x = c.lg.y = null; } if (!P.pn.user){ c.pn.x = c.pn.y = null; }
      localStorage.setItem(KEY, JSON.stringify(c)); storageOK = true;
    } catch (err){ storageOK = false; }
  }
  restore();
  /* ---- abbreviations: the table the build step put into the page (scripts/anatomy/q236); a plain fallback for a page without it ---- */
  var AB = {}, haveTable = false;
  try { var tb = $("nmsk-abbrev"); if (tb && tb.textContent.trim().length > 2){ var jj = JSON.parse(tb.textContent); if (jj && jj.a){ AB = jj.a; haveTable = true; } } } catch (err){ AB = {}; }
  var abbr = new Array(N), gen = new Array(N), full = new Array(N), used = {};
  function sideL(s){ return s === "r" ? "R" : s === "l" ? "L" : ""; }
  function fbAbbr(nm){
    var w = String(nm || "").replace(/\([^)]*\)/g, " ").split(/[^A-Za-z0-9]+/).filter(function(x){ return x && !/^(of|the|and|to|for|in|on|with|from|left|right)$/i.test(x); });
    if (!w.length) return "X";
    return w.length === 1 ? w[0].charAt(0).toUpperCase() + w[0].slice(1, 3).toLowerCase() : w.slice(0, 5).map(function(x){ return x.charAt(0).toUpperCase(); }).join("");
  }
  S.forEach(function(s, i){
    var t = AB[s.id], a, g, f;
    if (t){ a = t[0]; g = t[1] ? 1 : 0; f = t[2] || s.name; }
    else { a = fbAbbr(s.name) + (sideL(s.side) ? "-" + sideL(s.side) : ""); g = 1; f = String(s.name || s.id).replace(/\s*\((?:left|right)\)\s*$/i, ""); }
    if (!t){ var k = a.toLowerCase(); if (used[k]){ used[k]++; a = a + "." + used[k]; } else used[k] = 1; }
    abbr[i] = a; gen[i] = g; full[i] = f;
  });
  /* ---- vessels and nerves: kind / diameter / level per structure (the page's calibre table; a name-based fallback without it) ---- */
  var VK = new Array(N), VD = new Array(N), VL = new Array(N), VP = new Array(N), haveCal = false, calCount = 0;
  var CAL = {};
  try { var ct = $("nmsk-calibre"); if (ct && ct.textContent.trim().length > 2){ var cj = JSON.parse(ct.textContent); if (cj && cj.c){ CAL = cj.c; haveCal = true; } } } catch (err){ CAL = {}; }
  var RX_N = /(^|_)(n|nn|nerve|nerves|plexus|trunk|trunks|root|roots|rami|ramus|branch|branches|cord|cords|div|division|divisions|ansa|ganglion|ganglia|chorda)(_|$)/,
      RX_V = /(^|_)(vein|veins|vena|v|sinus|sinuses|venous|plexus)(_|$)/, RX_A = /(^|_)(artery|arteries|a|aorta|arterial|trunk|arch|branch|branches|anastomosis|circle)(_|$)|aort|arter/,
      RX_X = /atrium|ventricle|leaflet|papillary|valve|unnamed|(^|_)x(_|$)|chordae|septum/;
  S.forEach(function(s, i){
    var c = CAL[s.id]; VK[i] = ""; VD[i] = null; VL[i] = 4; VP[i] = 0;
    if (c){ VK[i] = c[0]; VD[i] = c[1]; VL[i] = c[2]; VP[i] = c[3] ? 1 : 0; calCount++; return; }
    if (haveCal) return;
    var n = String(s.id).replace(/^zan_/, "").replace(/_(l|r)$/, "");
    if (s.cat === "nerve" && RX_N.test(n)) { VK[i] = "n"; VL[i] = 2; }
    else if (s.cat === "vessel" && !RX_X.test(n)) { if (RX_V.test(n)) { VK[i] = "v"; VL[i] = 2; } else if (RX_A.test(n)) { VK[i] = "a"; VL[i] = 2; } }
  });
  var LVN = {a:["Main", "+ secondary", "+ tertiary", "All"], n:["Main trunks", "+ branches", "+ small", "All"]};
  /* does the vessel / nerve filter let structure i have a label (forced ones - selected, hovered, marked - skip it) */
  function vnPass(i){
    var k = VK[i]; if (!k) return true;
    if (P.vn.hide || (k === "a" && !P.vn.a) || (k === "v" && !P.vn.v) || (k === "n" && !P.vn.n)) return false;
    if (!haveCal) return true;
    if (VL[i] > (k === "n" ? P.vn.lvn : P.vn.lva)) return false;
    var dm = k === "n" ? P.vn.dn : P.vn.da;
    return !(dm > 0 && VD[i] != null && VD[i] < dm);
  }
  function vnPrio(i){ var k = VK[i]; return !k ? 0 : VL[i] === 1 ? 1 : VL[i] === 2 ? 0.5 : 0.25; }
  /* ---- text measuring ---- */
  var cvs = null, ctx = null, mcache = {}, mfont = 0;
  function fontCss(px, w){ return (w || 600) + " " + px + 'px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif'; }
  function measure(text, px){
    var key = px + "|" + text, w = mcache[key];
    if (w != null) return w;
    try { if (!ctx){ cvs = document.createElement("canvas"); ctx = cvs.getContext("2d"); } ctx.font = fontCss(px, 600); w = ctx.measureText(text).width; }
    catch (err){ w = text.length * px * 0.58; }
    if (!(w > 0)) w = text.length * px * 0.58;
    mcache[key] = w; return w;
  }
  function dupKey(i){ return full[i].toLowerCase() + "|" + S[i].side; }
  function labelText(i, sel){
    var s = S[i], t = P.text === "abbr" ? abbr[i] : full[i];
    if (P.text === "full" && P.side){ var sl = sideL(s.side); if (sl) t += " (" + sl + ")"; }
    return t;
  }
  /* ---- state ---- */
  var cur = null, items = [], shown = [], lastHeavy = 0, lastHeavyMs = 0, lastIdMs = 0, heavyCount = 0, needHeavy = true, settleT = 0, trailT = 0, animRaf = 0, lastSig = "", forcedSig = "";
  var hoverId = null, hotId = null, drawn = {}, solved = {}, samples = {}, layoutMs = 0, layoutN = 0, enabled = false, lastShownKey = "", elMap = {}, inlineMode = {};
  var layer = $("lab-layer"), gLead = null, gTxt = null;
  function el(name, attrs, parent){
    var e = document.createElementNS(NS, name);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"}[c]; }); }
  function ensureLayer(){
    if (!layer || gLead) return;
    gLead = el("g", {"class":"lb-leads"}, layer); gTxt = el("g", {"class":"lb-txts"}, layer);
  }
  function nowMs(){ return (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now(); }
  /* ---- colours ---- */
  function lum(c){ function f(v){ v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); } return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); }
  function contrast(a, b){ var la = lum(a) + 0.05, lb = lum(b) + 0.05; return la > lb ? la / lb : lb / la; }
  var bgc = [225, 230, 235], bgT = 0;
  function readBg(){ try { var b = E.bg(); if (b && b.length === 3) bgc = b; } catch (err){} }
  function textColour(rgb){
    var c = rgb ? [rgb[0], rgb[1], rgb[2]] : [20, 20, 20];
    if (P.colour === "neutral" || !rgb) c = lum(bgc) > 0.4 ? [17, 24, 32] : [240, 244, 248];
    var tgt = lum(bgc) > 0.4 ? [0, 0, 0] : [255, 255, 255];
    for (var k = 0; k < 9 && contrast(c, bgc) < 4.2; k++) c = [c[0] + (tgt[0] - c[0]) * 0.22, c[1] + (tgt[1] - c[1]) * 0.22, c[2] + (tgt[2] - c[2]) * 0.22];
    return "rgb(" + Math.round(c[0]) + "," + Math.round(c[1]) + "," + Math.round(c[2]) + ")";
  }
  /* ---- samples: a few dozen surface points per structure (triangle centroids, area-weighted, deterministic), made lazily ---- */
  var K = 96, TRIALS = 900;
  function getSamples(i){
    var s = samples[i];
    if (s) return s;
    var parts = E.geometry(i) || [], tot = 0, p, t;
    for (p = 0; p < parts.length; p++) tot += (parts[p].idx.length / 3) | 0;
    if (!tot){ samples[i] = new Float32Array(0); return samples[i]; }
    var M = Math.min(tot, TRIALS), cand = new Float32Array(M * 4), cum = new Float64Array(M), area = 0, m;
    for (m = 0; m < M; m++){
      var g = Math.min(tot - 1, Math.floor((m + 0.5) * tot / M)), q = 0;
      while (q < parts.length - 1 && g >= ((parts[q].idx.length / 3) | 0)){ g -= (parts[q].idx.length / 3) | 0; q++; }
      var pp = parts[q], ix = pp.idx, ps = pp.pos, a = ix[g * 3] * 3, b = ix[g * 3 + 1] * 3, c = ix[g * 3 + 2] * 3;
      var ux = ps[b] - ps[a], uy = ps[b + 1] - ps[a + 1], uz = ps[b + 2] - ps[a + 2], vx = ps[c] - ps[a], vy = ps[c + 1] - ps[a + 1], vz = ps[c + 2] - ps[a + 2];
      var cx = uy * vz - uz * vy, cy = uz * vx - ux * vz, cz = ux * vy - uy * vx, ar = 0.5 * Math.sqrt(cx * cx + cy * cy + cz * cz);
      cand[m * 4] = (ps[a] + ps[b] + ps[c]) / 3; cand[m * 4 + 1] = (ps[a + 1] + ps[b + 1] + ps[c + 1]) / 3; cand[m * 4 + 2] = (ps[a + 2] + ps[b + 2] + ps[c + 2]) / 3; cand[m * 4 + 3] = ar;
      area += ar; cum[m] = area;
    }
    var nk = Math.min(K, M), out = new Float32Array(nk * 3), mi = 0;
    for (var kk = 0; kk < nk; kk++){
      var want = area * (kk + 0.5) / nk;
      while (mi < M - 1 && cum[mi] < want) mi++;
      out[kk * 3] = cand[mi * 4]; out[kk * 3 + 1] = cand[mi * 4 + 1]; out[kk * 3 + 2] = cand[mi * 4 + 2];
    }
    samples[i] = out; return out;
  }
  /* ---- projection ---- */
  function proj(m, rect, x, y, z, o){
    var w = m[3] * x + m[7] * y + m[11] * z + m[15];
    if (!(w > 1e-6)){ o.ok = false; return o; }
    var cx = m[0] * x + m[4] * y + m[8] * z + m[12], cy = m[1] * x + m[5] * y + m[9] * z + m[13];
    o.x = rect.left + (cx / w * 0.5 + 0.5) * rect.width; o.y = rect.top + (1 - (cy / w * 0.5 + 0.5)) * rect.height; o.w = w; o.ok = true; return o;
  }
  function bufStats(buf, n){
    var cnt = new Int32Array(n + 1), sx = new Float64Array(n + 1), sy = new Float64Array(n + 1), ids = buf.ids, w = buf.w, h = buf.h, x, y, v, o = 0;
    for (y = 0; y < h; y++) for (x = 0; x < w; x++){ v = ids[o++]; if (v){ cnt[v]++; sx[v] += x; sy[v] += y; } }
    return {cnt:cnt, sx:sx, sy:sy};
  }
  /* per wanted id: the visible pixel nearest to the visible centroid (the 2D anchor) and up to 9 spread pixels; one pass over the image */
  function bufScan(buf, st, want, n){
    var bd = new Float64Array(n + 1).fill(1e18), bx = new Int32Array(n + 1).fill(-1), by = new Int32Array(n + 1).fill(-1), seen = new Int32Array(n + 1), sp = {}, ids = buf.ids, w = buf.w, h = buf.h, x, y, v, o = 0, mx, my, d;
    for (y = 0; y < h; y++) for (x = 0; x < w; x++){
      v = ids[o++]; if (!v || !want[v]) continue;
      mx = st.sx[v] / st.cnt[v]; my = st.sy[v] / st.cnt[v]; d = (x - mx) * (x - mx) + (y - my) * (y - my);
      if (d < bd[v]){ bd[v] = d; bx[v] = x; by[v] = y; }
      var stride = Math.max(1, Math.floor(st.cnt[v] / 8));
      if ((seen[v]++ % stride) === 0){ var a = sp[v] || (sp[v] = []); if (a.length < 9) a.push([x, y]); }
    }
    return {bd:bd, bx:bx, by:by, sp:sp};
  }
  /* long structures (vessels, nerves): the anchor is the middle part of the longest visible run along the structure's own main axis (nearest to the canvas centre there),
     not the centroid of its pixels, which for a curved or forked structure lies off it. want = flags per id (index + 1); -> {id1: {x, y, len}} in ID image pixels */
  function longAnchors(buf, want){
    var ids = buf.ids, w = buf.w, h = buf.h, lists = {}, x, y, o = 0, v, any = false;
    for (y = 0; y < h; y++) for (x = 0; x < w; x++){
      v = ids[o++]; if (!v || !want[v]) continue;
      var a = lists[v] || (lists[v] = []); if (a.length < 16000){ a.push(x, y); any = true; }
    }
    var out = {};
    if (!any) return out;
    for (var key in lists){
      var L = lists[key], n = L.length / 2, i, sx = 0, sy = 0;
      if (n < 12) continue;
      for (i = 0; i < n; i++){ sx += L[i * 2]; sy += L[i * 2 + 1]; }
      var mx = sx / n, my = sy / n, sxx = 0, sxy = 0, syy = 0;
      for (i = 0; i < n; i++){ var dx = L[i * 2] - mx, dy = L[i * 2 + 1] - my; sxx += dx * dx; sxy += dx * dy; syy += dy * dy; }
      var th = 0.5 * Math.atan2(2 * sxy, sxx - syy), ax = Math.cos(th), ay = Math.sin(th), tmin = 1e9, tmax = -1e9, t = new Float32Array(n);
      for (i = 0; i < n; i++){ var tt = (L[i * 2] - mx) * ax + (L[i * 2 + 1] - my) * ay; t[i] = tt; if (tt < tmin) tmin = tt; if (tt > tmax) tmax = tt; }
      var nb = Math.ceil(tmax - tmin) + 2, occ = new Int32Array(nb);
      for (i = 0; i < n; i++) occ[Math.floor(t[i] - tmin)]++;
      var best = null, b0 = -1, last = -1, cnt = 0;
      for (var b = 0; b <= nb + 3; b++){          // runs of occupied 1 px bins; a gap of up to 2 px bridges (aliasing of a thin diagonal line)
        var on = b < nb && occ[b] > 0;
        if (on){ if (b0 < 0){ b0 = b; cnt = 0; } last = b; cnt += occ[b]; }
        else if (b0 >= 0 && b - last > 2){
          var run = {b0:b0, b1:last, len:last - b0, cnt:cnt};
          if (!best || run.len > best.len || (run.len === best.len && run.cnt > best.cnt)) best = run;
          b0 = -1;
        }
      }
      if (!best || best.len < 6) continue;
      var lo = best.b0 + best.len * 0.25, hi = best.b0 + best.len * 0.75, bd = 1e18, px = -1, py = -1, cx = w / 2, cy = h / 2;
      for (i = 0; i < n; i++){
        var tb = t[i] - tmin; if (tb < lo || tb > hi) continue;
        var ddx = L[i * 2] - cx, ddy = L[i * 2 + 1] - cy, dd = ddx * ddx + ddy * ddy; if (dd < bd){ bd = dd; px = L[i * 2]; py = L[i * 2 + 1]; }
      }
      if (px >= 0) out[key] = {x:px, y:py, len:best.len};
    }
    return out;
  }
  /* ---- the heavy refresh: which structures are visible (ID image), which get a label, where their anchors are ---- */
  var wantLive = {};
  function forcedIds(){
    var out = [], seen = {}, a = [E.selected(), hoverId].concat(E.marked() || []);
    a.forEach(function(id){ if (id != null && idx[id] != null && !seen[id]){ seen[id] = 1; out.push(idx[id]); } });
    return out;
  }
  /* the anchors: per candidate a 3D point (on the cut face, or a visible surface sample) or, failing that, a 2D pixel of the ID image; the surface samples are made in slices */
  function buildItems(C){
    var v = C.v, rect = C.rect, al = C.al, bufB = C.bufB, bufA = C.bufA, stB = C.stB, stA = C.stA, scB = C.scB, scA = C.scA, cand = C.cand, capOn = C.capOn;
    var budget = nowMs() + 9, deferred = false, out = [], tmp = {ok:false, x:0, y:0, w:0};
    cand.forEach(function(c){
      var k = c.i, buf = al[k] >= OPQ ? bufB : (bufA || bufB), st = al[k] >= OPQ ? stB : (stA || stB), b = buf.ids, bw2 = buf.w, bh2 = buf.h, cnt = st.cnt[k + 1];
      var it = {i:k, id:S[k].id, forced:c.forced, px:cnt, p3:null, ax:0, ay:0, occluded: cnt <= 0, kind:"2d"};
      var mx = 0, my = 0;
      if (cnt > 0){ mx = st.sx[k + 1] / cnt; my = st.sy[k + 1] / cnt; }
      var id1 = k + 1, sc = al[k] >= OPQ || !scA ? scB : scA, bestD = sc.bd[k + 1], bpx = sc.bx[k + 1], bpy = sc.by[k + 1], spread = sc.sp[k + 1] || [];
      var la = (al[k] >= OPQ || !C.laA ? C.laB : C.laA);
      la = la && la[id1];
      if (la && cnt > 0){ bpx = la.x; bpy = la.y; bestD = 0; mx = la.x; my = la.y; it.long = la.len; }
      if (cnt > 0){
        if (bpx < 0){ bpx = Math.round(mx); bpy = Math.round(my); }
        it.ax = rect.left + (bpx + 0.5) / bw2 * rect.width; it.ay = rect.top + (bpy + 0.5) / bh2 * rect.height; it.u = bpx; it.v = bpy;
      }
      /* cut mode, filled cut face, the camera on the removed side: the anchor lies ON the cut face of this structure */
      if (capOn && cnt > 0){
        var tryPx = [[bpx, bpy]].concat(spread);
        for (var tq = 0; tq < tryPx.length && !it.p3; tq++){
          var rr = E.ray(rect.left + (tryPx[tq][0] + 0.5) / bw2 * rect.width, rect.top + (tryPx[tq][1] + 0.5) / bh2 * rect.height), hit = rr ? E.capHit(rr.o, rr.d) : null;
          if (hit && hit.item && hit.item.key === S[k].id){ it.p3 = [hit.point[0], hit.point[1], hit.point[2]]; it.kind = "cut"; var pj = proj(v.m, rect, it.p3[0], it.p3[1], it.p3[2], tmp); if (pj.ok){ it.ax = pj.x; it.ay = pj.y; } }
        }
      }
      /* otherwise: the surface sample that is visible (its pixel names this structure), on the camera's side, nearest to the visible centroid */
      if (!it.p3 && cnt > 0){
        var sm = samples[k];
        if (!sm && nowMs() < budget) sm = getSamples(k);
        if (!sm) deferred = true;
        else {
          var bb = S[k].bb, ec = bb ? [(bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2] : null, bd = 1e18, bp = -1;
          for (var q = 0; q < sm.length / 3; q++){
            var X = sm[q * 3], Y = sm[q * 3 + 1], Z = sm[q * 3 + 2];
            if (ec && ((X - ec[0]) * (v.eye[0] - ec[0]) + (Y - ec[1]) * (v.eye[1] - ec[1]) + (Z - ec[2]) * (v.eye[2] - ec[2])) < 0) continue;      // far side of the structure
            var pq = proj(v.m, rect, X, Y, Z, tmp); if (!pq.ok) continue;
            var u = Math.floor((pq.x - rect.left) / rect.width * bw2), w2 = Math.floor((pq.y - rect.top) / rect.height * bh2);
            if (u < 0 || w2 < 0 || u >= bw2 || w2 >= bh2 || b[w2 * bw2 + u] !== id1) continue;
            var dq = (u - mx) * (u - mx) + (w2 - my) * (w2 - my);
            if (dq < bd){ bd = dq; bp = q; }
          }
          if (bp >= 0 && bd <= Math.max(bestD * 4 + 400, 0.7 * cnt)){
            it.p3 = [sm[bp * 3], sm[bp * 3 + 1], sm[bp * 3 + 2]]; it.kind = "surf";
            var pr = proj(v.m, rect, it.p3[0], it.p3[1], it.p3[2], tmp); if (pr.ok){ it.ax = pr.x; it.ay = pr.y; }
          }
        }
      }
      if (cnt <= 0){                                                     // occluded but asked for (Hide occluded is off): the nearest surface sample, dashed
        var sm2 = samples[k] || (nowMs() < budget ? getSamples(k) : null);
        if (sm2 && sm2.length){
          var bq = -1, bdist = 1e18;
          for (var q2 = 0; q2 < sm2.length / 3; q2++){ var dx = sm2[q2 * 3] - v.eye[0], dy = sm2[q2 * 3 + 1] - v.eye[1], dz = sm2[q2 * 3 + 2] - v.eye[2], d2 = dx * dx + dy * dy + dz * dz; if (d2 < bdist){ bdist = d2; bq = q2; } }
          it.p3 = [sm2[bq * 3], sm2[bq * 3 + 1], sm2[bq * 3 + 2]]; it.kind = "hid";
          var p4 = proj(v.m, rect, it.p3[0], it.p3[1], it.p3[2], tmp); if (p4.ok){ it.ax = p4.x; it.ay = p4.y; } else return;
        } else return;
      }
      if (it.kind === "2d" && cnt <= 0) return;
      it.rgb = E.color(k);
      out.push(it);
    });
    return {out:out, deferred:deferred};
  }
  function refresh(){
    var t0 = nowMs();
    needHeavy = false; lastHeavy = t0; heavyCount++;
    if (P.mode === "off"){ cur = null; items = []; return; }
    var v = E.view();
    if (!v || !v.m || !v.rect || !(v.rect.width > 8)){ cur = null; items = []; return; }
    readBg();
    var al = E.alphas(), i, needA = false;
    for (i = 0; i < N; i++) if (al[i] >= AMIN && al[i] < OPQ){ needA = true; break; }
    var bw = Math.max(BUF_MIN, Math.min(BUF_MAX, Math.round(v.rect.width * 0.5)));
    var tI = nowMs(), bufB = E.idImage(false, bw), bufA = needA ? E.idImage(true, bw) : null;
    lastIdMs = nowMs() - tI;
    if (!bufB){ cur = null; items = []; return; }
    var stB = bufStats(bufB, N), stA = bufA ? bufStats(bufA, N) : null, mbuf = bufA || bufB;
    function vp(k){ return al[k] >= OPQ ? stB.cnt[k + 1] : (stA ? stA.cnt[k + 1] : 0); }
    var forced = forcedIds(), isForced = {}; forced.forEach(function(k){ isForced[k] = 1; });
    var cand = [], minPx = P.mode === "all" ? 1 : Math.max(3, Math.round(bufB.w * bufB.h * 0.00003));
    forced.forEach(function(k){
      if (al[k] < AMIN) return;
      if (vp(k) <= 0 && P.occl) return;
      cand.push({i:k, px:vp(k), forced:true, score:1e15});
    });
    if (P.mode !== "sel"){
      var pool = [], vpool = [];
      for (i = 0; i < N; i++){
        if (isForced[i] || al[i] < AMIN) continue;
        var px = vp(i); if (px < minPx) continue;
        if (VK[i]){
          if (!vnPass(i)) continue;
          vpool.push({i:i, px:px, forced:false, score:(5 - VL[i]) * 1e7 + px});         // main trunks first, then by the visible length
        } else pool.push({i:i, px:px, forced:false, score:px * (wantLive[i] ? 1.35 : 1) * (CATW[S[i].cat] || 1)});
      }
      pool.sort(function(a, b){ return b.score - a.score || (a.i - b.i); });
      vpool.sort(function(a, b){ return b.score - a.score || (a.i - b.i); });
      var cap = P.mode === "all" ? ALLCAP : Math.max(0, P.density - cand.length), seenT = {}, keep = [], vkeep = [];
      cand.forEach(function(c){ seenT[dupKey(c.i)] = 1; });
      var vq = P.mode === "all" ? cap : Math.min(vpool.length, Math.max(3, Math.round(cap * 0.4)));          // vessels / nerves get a reserved share of the budget (thin structures never win on pixel area)
      function takeFrom(list, into, limit){
        for (var pi = 0; pi < list.length && into.length < limit; pi++){        // one label per name + side (a structure continued by a gap-filling mesh is one entity to the reader)
          if (list[pi].taken) continue;
          var dk = dupKey(list[pi].i); if (seenT[dk]) continue; seenT[dk] = 1; list[pi].taken = 1; into.push(list[pi]);
        }
      }
      takeFrom(vpool, vkeep, vq);
      takeFrom(pool, keep, cap - vkeep.length);
      if (keep.length + vkeep.length < cap) takeFrom(vpool, vkeep, cap - keep.length);
      cand = cand.concat(vkeep, keep);
    } else cand = cand.slice(0, SEL_CAP);
    var rect = v.rect, bwid = bufB.w, bh = bufB.h, ids = bufB.ids, cutS = E.cut(), cutOn = !!(cutS && cutS.on), eyeKept = true;
    if (cutOn){ var se = cutS.kn[0] * v.eye[0] + cutS.kn[1] * v.eye[1] + cutS.kn[2] * v.eye[2] + cutS.c; eyeKept = se >= 0; }
    var capOn = cutOn && !eyeKept && E.capHit;
    var wantB = new Uint8Array(N + 1), wantA = new Uint8Array(N + 1);
    cand.forEach(function(c){ (al[c.i] >= OPQ || !stA ? wantB : wantA)[c.i + 1] = 1; });
    var scB = bufScan(bufB, stB, wantB, N), scA = stA ? bufScan(bufA, stA, wantA, N) : null;
    var lwB = new Uint8Array(N + 1), lwA = new Uint8Array(N + 1), anyLB = false, anyLA = false;
    cand.forEach(function(c){ if (!VK[c.i]) return; if (al[c.i] >= OPQ || !stA){ lwB[c.i + 1] = 1; anyLB = true; } else { lwA[c.i + 1] = 1; anyLA = true; } });
    var laB = anyLB ? longAnchors(bufB, lwB) : null, laA = anyLA && bufA ? longAnchors(bufA, lwA) : null;
    var cap0 = {v:v, rect:rect, al:al, bufB:bufB, bufA:bufA, stB:stB, stA:stA, scB:scB, scA:scA, laB:laB, laA:laA, cand:cand, capOn:capOn};
    var built = buildItems(cap0), out = built.out, deferred = built.deferred;
    /* body silhouette for the callouts: every pixel any structure drew */
    var occ = new Uint8Array(mbuf.w * mbuf.h), ii = mbuf.ids, nn = occ.length;
    for (var o = 0; o < nn; o++) occ[o] = ii[o] ? 1 : 0;
    var mask = NMSKLabelsCore.makeMask(occ, mbuf.w, mbuf.h, rect.left, rect.top, rect.width / mbuf.w, rect.height / mbuf.h);
    var visCount = 0; for (i = 0; i < N; i++) if (al[i] >= AMIN && vp(i) > 0) visCount++;
    var vnVis = 0; for (i = 0; i < N; i++) if (VK[i] && al[i] >= AMIN && vp(i) > 0) vnVis++;
    cur = {items:out, buf:bufB, mask:mask, rect:rect, visible:visCount, vnVisible:vnVis, cutOn:cutOn, capOn:!!capOn, hasTable:haveTable};
    items = out; wantLive = {}; out.forEach(function(it){ wantLive[it.i] = 1; });
    lastHeavyMs = nowMs() - t0; forcedSig = sigForced();
    if (deferred) sliceLater(cur, cap0);          // surface samples of the remaining structures are made in the next slice (no new ID pass)
    legendSoon();
  }
  var sliceT = 0;
  function sliceLater(curObj, C){
    if (sliceT) return;
    sliceT = setTimeout(function(){
      sliceT = 0; if (cur !== curObj || P.mode === "off") return;
      var b = buildItems(C); curObj.items = b.out; items = b.out; wantLive = {}; b.out.forEach(function(it){ wantLive[it.i] = 1; });
      lastLSig = ""; layout();
      if (b.deferred) sliceLater(curObj, C);
    }, 25);
  }
  function sigForced(){ var m = E.marked() || []; return (E.selected() || "") + "|" + (hoverId || "") + "|" + m.length + ":" + (m.length ? m[0] + m[m.length - 1] : ""); }
  /* ---- per-frame layout: re-project the anchors, decide inline / callout, place, ease, draw ---- */
  var disp = {};
  function obstSig(){ var s = ""; try { allObst().forEach(function(e){ if (e && e.getBoundingClientRect && !e.hidden){ var r = e.getBoundingClientRect(); s += Math.round(r.left) + "," + Math.round(r.top) + "," + Math.round(r.width) + "," + Math.round(r.height) + ";"; } }); } catch (err){} return s; }
  function allObst(){ return (E.obstacles() || []).concat([panel, legend]); }
  function inlineFit(it, bw, bh){        // is the label box (centred on the anchor) mostly on its own structure?
    var buf = cur.buf, rect = cur.rect, ids = buf.ids, id1 = it.i + 1, hit = 0, tot = 0;
    for (var gy = -1; gy <= 1; gy++) for (var gx = -2; gx <= 2; gx++){
      var X = it.sx + gx * bw / 4, Y = it.sy + gy * bh / 2.4, u = Math.floor((X - rect.left) / rect.width * buf.w), w2 = Math.floor((Y - rect.top) / rect.height * buf.h);
      tot++;
      if (u >= 0 && w2 >= 0 && u < buf.w && w2 < buf.h && ids[w2 * buf.w + u] === id1) hit++;
    }
    return hit / tot;
  }
  var lastLSig = "", lastDraw = null;
  function layout(){
    if (!layer) return;
    if (P.mode === "off" || !cur){ lastLSig = ""; lastDraw = null; render([]); return; }
    var t0 = nowMs(), v = E.view(); if (!v || !v.m){ render([]); return; }
    var lsig = heavyCount + "|" + P.font + P.text + P.callout + P.side + P.colour + "|" + v.m.join(",") + "|" + v.rect.left + "," + v.rect.top + "," + v.rect.width + "," + v.rect.height + "|" + (E.selected() || "") + "|" + (hotId || "") + (hoverId || "") + "|" + obstSig();
    if (lsig === lastLSig && lastDraw){ render(lastDraw, E.selected()); return; }       // nothing moved: only the easing continues
    var rect = v.rect, fs = P.font, tmp = {ok:false, x:0, y:0}, L = [], fr = {x0:rect.left + 6, y0:rect.top + 6, x1:rect.left + rect.width - 6, y1:rect.top + rect.height - 6};
    var obst = [];
    try { allObst().forEach(function(e){
      if (!e || !e.getBoundingClientRect) return; var st = e.offsetParent === null && getComputedStyle(e).position !== "fixed" ? null : e.getBoundingClientRect();
      if (!st || !(st.width > 4) || !(st.height > 4) || e.hidden) return;
      if (st.right <= fr.x0 || st.left >= fr.x1 || st.bottom <= fr.y0 || st.top >= fr.y1) return;
      var cs = getComputedStyle(e); if (cs.display === "none" || cs.visibility === "hidden") return;
      obst.push({x0:st.left - 4, y0:st.top - 4, x1:st.right + 4, y1:st.bottom + 4});
    }); } catch (err){}
    var sel = E.selected();
    cur.items.forEach(function(it){
      var ax = it.ax, ay = it.ay;
      if (it.p3){ var pj = proj(v.m, rect, it.p3[0], it.p3[1], it.p3[2], tmp); if (!pj.ok) return; ax = pj.x; ay = pj.y; }
      if (ax < rect.left + 2 || ay < rect.top + 2 || ax > rect.left + rect.width - 2 || ay > rect.top + rect.height - 2) return;
      it.sx = ax; it.sy = ay;
      var text = labelText(it.i), w = measure(text, fs) + 8, h = fs * 1.3 + 3;
      L.push({it:it, text:text, w:w, h:h, ax:ax, ay:ay, prio:(it.i === idx[sel] ? 3 : it.forced ? 2 : vnPrio(it.i)), id:it.id});
    });
    /* inline or callout */
    var inl = [], out = [], placedBoxes = [];
    L.sort(function(a, b){ return b.prio - a.prio || b.it.px - a.it.px || (a.it.i - b.it.i); });
    L.forEach(function(l){
      var want = P.callout, mode;
      if (want === "out") mode = "out";
      else {
        var f = inlineFit(l.it, l.w, l.h), was = inlineMode[l.id];
        var ok = f >= (was === "in" ? 0.62 : 0.8) || (l.it.kind === "hid");
        mode = ok ? "in" : (want === "in" ? "in" : "out");
        if (mode === "in"){
          var box = {x:l.ax, y:l.ay, w:l.w, h:l.h}, clash = false;
          for (var b = 0; b < placedBoxes.length; b++) if (Math.abs(box.x - placedBoxes[b].x) < (box.w + placedBoxes[b].w) / 2 + 1 && Math.abs(box.y - placedBoxes[b].y) < (box.h + placedBoxes[b].h) / 2 + 1){ clash = true; break; }
          var hitO = false;
          for (var oi = 0; oi < obst.length; oi++){ var ob = obst[oi]; if (box.x - box.w / 2 < ob.x1 && box.x + box.w / 2 > ob.x0 && box.y - box.h / 2 < ob.y1 && box.y + box.h / 2 > ob.y0){ hitO = true; break; } }
          if (clash || hitO || box.x - box.w / 2 < fr.x0 || box.x + box.w / 2 > fr.x1 || box.y - box.h / 2 < fr.y0 || box.y + box.h / 2 > fr.y1){ mode = want === "in" ? "drop" : "out"; }
          else placedBoxes.push(box);
        }
      }
      inlineMode[l.id] = mode;
      l.mode = mode;
      if (mode === "in") inl.push(l); else if (mode === "out") out.push(l);
    });
    out.forEach(function(l){ var pv = solved[l.id]; l.px = pv ? pv.x : null; l.py = pv ? pv.y : null; });
    var res = out.length ? NMSKLabelsCore.solve({labels:out.map(function(l){ return {id:l.id, ax:l.ax, ay:l.ay, w:l.w, h:l.h, prio:l.prio, px:l.px, py:l.py}; }),
                                                 mask:cur.mask, frame:fr, obstacles:obst.concat(placedBoxes.map(function(b){ return {x0:b.x - b.w / 2, y0:b.y - b.h / 2, x1:b.x + b.w / 2, y1:b.y + b.h / 2}; })), pad:2}) : [];
    var byId = {}; res.forEach(function(r){ byId[r.id] = r; });
    var next = {}, draw = [];
    inl.forEach(function(l){ draw.push({l:l, mode:"in", x:l.ax, y:l.ay, w:l.w, h:l.h}); });
    out.forEach(function(l){
      var r = byId[l.id]; if (!r || !r.ok) return;
      next[l.id] = {x:r.x, y:r.y};
      draw.push({l:l, mode:"out", x:r.x, y:r.y, w:l.w, h:l.h, lx:r.lx, ly:r.ly, forced:r.forced});
    });
    solved = next; lastLSig = lsig; lastDraw = draw;
    layoutMs = nowMs() - t0; layoutN = draw.length;
    render(draw, sel);
  }
  /* ---- DOM ---- */
  var lastFont = 0, animating = false;
  function r1(x){ return Math.round(x * 2) / 2; }
  function render(draw, sel){
    ensureLayer(); if (!gTxt) return;
    var keep = {}, anim = false, tnow = nowMs(), dt = Math.min(100, tnow - (render.t || tnow)); render.t = tnow;
    var kf = 1 - Math.exp(-dt / 65);
    if (P.font !== lastFont){ layer.setAttribute("font-size", P.font); lastFont = P.font; }
    var halo = lum(bgc) > 0.4 ? "rgba(255,255,255,.88)" : "rgba(10,14,18,.82)";
    layer.style.setProperty("--lb-halo", halo);
    draw.forEach(function(d){
      var l = d.l, id = l.id, e = elMap[id];
      if (!e){
        e = elMap[id] = {lead:el("polyline", {"class":"lb-lead lb-bg"}, gLead), lead2:el("polyline", {"class":"lb-lead"}, gLead), dot:el("circle", {"class":"lb-dot", r:3}, gLead),
                         t:el("text", {"class":"lb-t", "text-anchor":"middle"}, gTxt), x:null, y:null, fresh:true};
        e.t.addEventListener("click", function(ev){ ev.stopPropagation(); E.select(id); });
        e.t.addEventListener("pointerenter", function(){ hot(id); }); e.t.addEventListener("pointerleave", function(){ hot(null); });
        e.t.addEventListener("pointerdown", function(ev){ ev.stopPropagation(); });
      }
      keep[id] = 1;
      var tx = d.x, ty = d.y;
      if (e.x == null){ e.x = d.mode === "out" ? l.ax : tx; e.y = d.mode === "out" ? l.ay : ty; }
      if (d.mode === "out"){ e.x += (tx - e.x) * kf; e.y += (ty - e.y) * kf; if (Math.abs(tx - e.x) > 0.4 || Math.abs(ty - e.y) > 0.4) anim = true; else { e.x = tx; e.y = ty; } }
      else { e.x = tx; e.y = ty; }
      var col = textColour(l.it.rgb), isSel = sel != null && l.it.i === idx[sel], hv = hotId === id || hoverId === id;
      if (e.text !== l.text){ e.t.textContent = l.text; e.text = l.text; }
      if (e.col !== col){ e.t.setAttribute("fill", col); e.lead2.setAttribute("stroke", col); e.dot.setAttribute("fill", col); e.col = col; }
      var cls = "lb-t" + (isSel ? " lb-sel" : "") + (hv ? " lb-hot" : "") + (l.it.kind === "hid" ? " lb-hid" : "") + (gen[l.it.i] ? " lb-gen" : "");
      if (e.cls !== cls){ e.t.setAttribute("class", cls); e.cls = cls; e.dot.setAttribute("class", "lb-dot" + (l.it.kind === "hid" ? " lb-hid" : "")); e.lead2.setAttribute("class", "lb-lead" + (l.it.kind === "hid" ? " lb-hid" : "")); e.lead.setAttribute("class", "lb-lead lb-bg"); e.cls = cls; }
      var px = r1(e.x), py = r1(e.y + P.font * 0.35);
      if (e.px !== px || e.py !== py){ e.t.setAttribute("x", px); e.t.setAttribute("y", py); e.px = px; e.py = py; }
      var pts;
      if (d.mode === "out"){
        var q = {x:e.x, y:e.y}, ep = NMSKLabelsCore.edgePoint(q, l.w, l.h, l.ax, l.ay);
        pts = r1(l.ax) + "," + r1(l.ay) + " " + r1(ep.x) + "," + r1(ep.y);
      } else pts = "";
      if (e.pts !== pts){ e.lead.setAttribute("points", pts); e.lead2.setAttribute("points", pts); e.pts = pts; }
      e.forced = !!d.forced; e.mode = d.mode; e.w = l.w; e.h = l.h; e.ax = l.ax; e.ay = l.ay; e.kind = l.it.kind;
      var dp = d.mode === "out" ? r1(l.ax) + "," + r1(l.ay) : "";
      if (e.dp !== dp){ if (dp){ e.dot.setAttribute("cx", r1(l.ax)); e.dot.setAttribute("cy", r1(l.ay)); e.dot.style.display = ""; } else e.dot.style.display = "none"; e.dp = dp; }
      if (e.fresh){ e.fresh = false; }
    });
    for (var id in elMap) if (!keep[id]){
      var o = elMap[id]; if (o.t.parentNode) o.t.parentNode.removeChild(o.t); if (o.lead.parentNode) o.lead.parentNode.removeChild(o.lead);
      if (o.lead2.parentNode) o.lead2.parentNode.removeChild(o.lead2); if (o.dot.parentNode) o.dot.parentNode.removeChild(o.dot); delete elMap[id]; delete disp[id];
    }
    layer.style.display = draw.length ? "block" : "none";
    var key = draw.map(function(d){ return d.l.id; }).join(",");
    if (key !== lastShownKey){ lastShownKey = key; shown = draw.map(function(d){ return d.l.it.i; }); legendSoon(); statusText(); }
    animating = anim;
    if (anim && !animRaf && typeof requestAnimationFrame !== "undefined") animRaf = requestAnimationFrame(function(){ animRaf = 0; layout(); });
  }
  function hot(id){ hotId = id; if (cur) layout(); }
  /* ---- scheduling ---- */
  function minGap(){ return Math.max(170, Math.min(6000, (lastHeavyMs + 1) * 6)); }       // the ID pass takes about 1/7 of the time or less (6 x its own measured cost between two passes, 0.17 - 6 s)
  function update(){
    if (!enabled || P.mode === "off"){ if (layer && layer.style.display !== "none" && !enabled) layer.style.display = "none"; return; }
    var t = nowMs(), fs = sigForced();
    if (needHeavy || fs !== forcedSig){ var gap = Math.min(minGap(), 400); if (t - lastHeavy >= gap){ refresh(); } else schedule(gap - (t - lastHeavy)); }
    else if (t - lastHeavy >= minGap()) refresh();
    else schedule(minGap() - (t - lastHeavy));
    layout(); autoPlace();
    if (settleT) clearTimeout(settleT);
    settleT = setTimeout(function(){ settleT = 0; autoPlace(true); if (P.mode !== "off"){ refresh(); layout(); } }, Math.max(190, minGap() - (t - lastHeavy)));       // the last look after the camera stopped, never sooner than the throttle allows
  }
  function schedule(ms){
    if (trailT) return;
    trailT = setTimeout(function(){ trailT = 0; if (P.mode !== "off"){ refresh(); layout(); } }, Math.max(10, ms));
  }
  function redrawNow(){ needHeavy = true; if (E.redraw) E.redraw(); else update(); }
  function dirty(){ needHeavy = true; }
  function hover(id){ var h = id || null; if (h !== hoverId){ hoverId = h; if (P.mode === "sel" || P.mode === "vis" || P.mode === "all"){ needHeavy = P.mode === "sel" ? true : needHeavy; if (E.redraw) E.redraw(); } } }
  /* ---- UI: panel ---- */
  var panel = $("lab-panel"), legend = $("lab-legend"), tbtn = null;
  function setSeg(id, val){ var g = $(id); if (!g) return; [].forEach.call(g.querySelectorAll("button"), function(b){ b.setAttribute("aria-pressed", String(b.getAttribute("data-v") === val)); }); }
  function statusText(){
    var s = $("lab-status"), h = $("lab-hint"); if (!s) return;
    if (P.mode === "off"){ s.textContent = "off"; }
    else {
      var nv = 0; shown.forEach(function(k){ if (VK[k]) nv++; });
      s.textContent = shown.length + " labelled" + (cur ? " / " + cur.visible + " visible" : "") + (nv ? " (" + nv + " vessels / nerves)" : "");
    }
    if (h){
      var msg = "";
      if (P.mode !== "off" && cur){
        if (cur.cutOn && !cur.capOn) msg = "Cut mode: with Fill cross-section on and the camera on the removed side, labels sit on the cut face.";
        else if (P.mode === "vis" && cur.visible > shown.length) msg = (cur.visible - shown.length) + " more visible structures are not labelled (Max labels). Zoom in or raise the limit.";
        else if (P.mode === "all" && cur.visible > ALLCAP) msg = "All shown is capped at " + ALLCAP + " labels (the largest on screen).";
      }
      if (P.mode === "sel") msg = "Selected, hovered and marked structures. Tap a structure to label it.";
      if (!haveTable && P.text === "abbr") msg = "This page has no abbreviation table: abbreviations are generated on the fly.";
      else if (!haveCal && P.mode !== "off" && P.mode !== "sel") msg = (msg ? msg + " " : "") + "This page has no calibre table: vessel / nerve levels and diameters do not apply (all of them by name).";
      else if (P.mode !== "off" && P.mode !== "sel" && cur && cur.vnVisible > 0 && !P.vn.hide){
        var nv2 = 0; shown.forEach(function(k){ if (VK[k]) nv2++; });
        if (nv2 < cur.vnVisible) msg = (msg ? msg + " " : "") + (cur.vnVisible - nv2) + " visible vessels / nerves are not labelled (level, minimum diameter, group or Max labels).";
      }
      h.textContent = msg;
    }
    var cf = $("lab-cutfill"); if (cf) cf.hidden = !(cur && cur.cutOn && !cur.capOn);
    if (tbtn) tbtn.setAttribute("aria-pressed", String(P.mode !== "off"));
    var cnt = $("lg-count"); if (cnt && legend && !legend.hidden) legendRender();
  }
  function applyUI(){
    setSeg("lab-show", P.mode); setSeg("lab-text", P.text); setSeg("lab-callout", P.callout); setSeg("lab-colour", P.colour);
    var d = $("lab-dens"), f = $("lab-font"), dv = $("lab-dens-v"), fv = $("lab-font-v"), sd = $("lab-side"), oc = $("lab-occl");
    if (d){ d.value = P.density; dv.textContent = P.density; d.disabled = P.mode !== "vis"; }
    if (f){ f.value = P.font; fv.textContent = P.font + " px"; }
    if (sd) sd.checked = P.side; if (oc) oc.checked = P.occl;
    if (tbtn) tbtn.setAttribute("aria-pressed", String(P.mode !== "off"));
    if (panel) panel.classList.toggle("lb-min", !!P.pn.min);
    var mn = $("lab-min"); if (mn){ mn.setAttribute("aria-expanded", String(!P.pn.min)); mn.innerHTML = P.pn.min ? "&#9652;" : "&#9662;"; }
    var lb = $("lab-legend-btn"); if (lb) lb.setAttribute("aria-pressed", String(!!P.lg.open));
    setSeg("lab-lva", String(P.vn.lva)); setSeg("lab-lvn", String(P.vn.lvn));
    [["a", "ga"], ["v", "gv"], ["n", "gn"]].forEach(function(g){ var b = $("lab-g-" + g[0]); if (b){ b.setAttribute("aria-pressed", String(!!P.vn[g[0]] && !P.vn.hide)); b.disabled = !!P.vn.hide; } });
    var vh = $("lab-vhide"); if (vh) vh.checked = !!P.vn.hide;
    var da = $("lab-da"), dn = $("lab-dn"), dav = $("lab-da-v"), dnv = $("lab-dn-v");
    if (da){ da.value = P.vn.da; da.disabled = !haveCal || P.vn.hide; } if (dn){ dn.value = P.vn.dn; dn.disabled = !haveCal || P.vn.hide; }
    if (dav) dav.textContent = P.vn.da > 0 ? "\u2265 " + P.vn.da.toFixed(1).replace(/\.0$/, "") + " mm" : "no minimum"; if (dnv) dnv.textContent = P.vn.dn > 0 ? "\u2265 " + P.vn.dn.toFixed(1).replace(/\.0$/, "") + " mm" : "no minimum";
    [].forEach.call(document.querySelectorAll("#lab-lva button, #lab-lvn button"), function(b){ b.disabled = !haveCal || !!P.vn.hide; });
  }
  function setMode(m, quiet){
    if (!MODES[m]) return; P.mode = m; applyUI(); persist();
    if (m === "off"){ cur = null; items = []; render([]); statusText(); if (E.redraw) E.redraw(); return; }
    enabled = true; needHeavy = true; if (E.redraw) E.redraw(); else { refresh(); layout(); }
  }
  function set(key, val){
    if (key === "text" && TEXTS[val]) P.text = val; else if (key === "callout" && CALLS[val]) P.callout = val; else if (key === "colour" && COLS[val]) P.colour = val;
    else if (key === "density") P.density = Math.round(num(val, 3, 120, P.density)); else if (key === "font") P.font = Math.round(num(val, 9, 22, P.font));
    else if (key === "side") P.side = !!val; else if (key === "occl") P.occl = !!val;
    else if (key === "vhide") P.vn.hide = !!val; else if (key === "ga") P.vn.a = !!val; else if (key === "gv") P.vn.v = !!val; else if (key === "gn") P.vn.n = !!val;
    else if (key === "lva") P.vn.lva = Math.round(num(val, 1, 4, P.vn.lva)); else if (key === "lvn") P.vn.lvn = Math.round(num(val, 1, 4, P.vn.lvn));
    else if (key === "da") P.vn.da = num(val, 0, 20, P.vn.da); else if (key === "dn") P.vn.dn = num(val, 0, 12, P.vn.dn); else return;
    applyUI(); persist(); needHeavy = key === "occl" || key === "density" || key === "colour" || /^(vhide|ga|gv|gn|lva|lvn|da|dn)$/.test(key) ? true : needHeavy;
    if (key === "font" || key === "text" || key === "side"){ if (cur) layout(); }
    if (key === "colour"){ for (var id in elMap) elMap[id].col = null; if (cur) layout(); }
    if (key === "callout"){ inlineMode = {}; solved = {}; }
    if (E.redraw) E.redraw(); else if (cur) layout();
    if (legend && !legend.hidden) legendRender();
  }
  function reset(){
    var l = P.lg, p = P.pn, d = dflt(); P = d; P.lg.open = l.open; P.lg.x = l.x; P.lg.y = l.y; P.pn = p; P.mode = "vis"; inlineMode = {}; solved = {};
    applyUI(); persist(); legendApplySize(); needHeavy = true; enabled = true; if (E.redraw) E.redraw();
  }
  /* ---- floating windows (drag by the header; on phones they are bottom sheets) ---- */
  function phone(){          // sheet layout: the page's phone layout, or a stage too narrow for a floating window (a tablet with three columns)
    if (E.isPhone && E.isPhone()) return true;
    try { var r = E.canvasRect && E.canvasRect(); return !!r && r.width > 0 && r.width < 560 && vw() < 1000; } catch (err){ return false; }
  }
  function vw(){ return window.innerWidth || document.documentElement.clientWidth || 800; }
  function vh(){ return window.innerHeight || document.documentElement.clientHeight || 600; }
  function obstRects(skip, withWins){
    var out = [];
    try { (E.obstacles() || []).concat(withWins ? [panel, legend] : []).forEach(function(e){
      if (!e || e === skip || !e.getBoundingClientRect || e.hidden) return; var r = e.getBoundingClientRect();
      if (r.width > 4 && r.height > 4 && r.right > 0 && r.left < vw() && r.bottom > 0 && r.top < vh() && getComputedStyle(e).display !== "none") out.push(r);
    }); } catch (err){}
    return out;
  }
  function clampWin(x, y, w, h){ return {x:Math.max(4, Math.min(vw() - Math.min(w, vw() - 8) - 4, x)), y:Math.max(4, Math.min(vh() - Math.min(h, vh() - 8) - 4, y))}; }
  function overlapArea(x, y, w, h, ob){
    var ov = 0; ob.forEach(function(r){ var ox = Math.min(x + w, r.right) - Math.max(x, r.left), oy = Math.min(y + h, r.bottom) - Math.max(y, r.top); if (ox > 0 && oy > 0) ov += ox * oy; });
    return ov;
  }
  function bestCorner(w, h, skip, prefer, withWins){
    var cr0 = E.canvasRect ? E.canvasRect() : {left:0, top:0, width:vw(), height:vh()}, cr = {left:cr0.left, top:cr0.top, right:cr0.left + cr0.width, bottom:cr0.top + cr0.height}, ob = obstRects(skip, withWins), best = null;
    var c = [{x:cr.right - w - 12, y:cr.top + 54}, {x:cr.left + 12, y:cr.top + 54}, {x:cr.right - w - 12, y:cr.bottom - h - 12}, {x:cr.left + 12, y:cr.bottom - h - 12}];
    if (prefer === "bottom") c = [c[3], c[2], c[1], c[0]];
    var pref = c[0], x, y;
    c.forEach(function(p, k){                                  // a top corner sits below the HUD toolbar that already occupies it (it may wrap into several rows on a narrow stage)
      if (p.y < cr.top + 100){
        var top = p.y;
        ob.forEach(function(r){ if (r.top < cr.top + 170 && r.bottom > cr.top && p.x < r.right && p.x + w > r.left && r.bottom + 8 > top && r.bottom - r.top < 120) top = r.bottom + 8; });
        p.y = top;
      }
    });
    for (x = cr.left + 8; x + w <= cr.right - 4; x += 48) for (y = cr.top + 8; y + h <= cr.bottom - 4; y += 48) c.push({x:x, y:y});       // and any free place of the canvas (the corners may all be taken by panels)
    c.forEach(function(p, k){
      var q = clampWin(p.x, p.y, w, h), ov = overlapArea(q.x, q.y, w, h, ob);
      var edge = Math.min(q.x - cr.left, cr.right - (q.x + w)), sc = ov * 2 + Math.max(0, edge) * 40 + Math.hypot(q.x - pref.x, q.y - pref.y) * 5 + (k < 4 ? 0 : 200);
      if (q.x < cr.left - 1 || q.x + w > cr.right + 1) sc += 1e9;
      if (!best || sc < best.sc) best = {x:q.x, y:q.y, sc:sc, ov:ov};
    });
    return best;
  }
  function placeWin(elm, st, prefer){
    if (!elm) return;
    if (phone()){ elm.classList.add("lb-phone"); elm.style.left = elm.style.top = ""; return; }
    elm.classList.remove("lb-phone");
    var w = elm.offsetWidth || 260, h = elm.offsetHeight || 200;
    if (st.x == null || st.y == null){ var b = bestCorner(w, h, elm, prefer, elm === legend); st.x = b.x; st.y = b.y; }
    var q = clampWin(st.x, st.y, w, h); st.x = q.x; st.y = q.y; elm.style.left = q.x + "px"; elm.style.top = q.y + "px";
  }
  function drag(elm, handle, st){
    var sx = 0, sy = 0, ox = 0, oy = 0, on = false;
    handle.addEventListener("pointerdown", function(e){
      if (phone() || (e.target.closest && e.target.closest("button,input,select,label"))) return;
      on = true; sx = e.clientX; sy = e.clientY; ox = st.x == null ? elm.getBoundingClientRect().left : st.x; oy = st.y == null ? elm.getBoundingClientRect().top : st.y;
      try { handle.setPointerCapture(e.pointerId); } catch (err){}
      e.preventDefault();
    });
    handle.addEventListener("pointermove", function(e){
      if (!on) return;
      var q = clampWin(ox + e.clientX - sx, oy + e.clientY - sy, elm.offsetWidth, elm.offsetHeight); st.x = q.x; st.y = q.y; elm.style.left = q.x + "px"; elm.style.top = q.y + "px";
    });
    function end(){ if (on){ on = false; st.user = true; persist(); if (cur) layout(); } }
    handle.addEventListener("pointerup", end); handle.addEventListener("pointercancel", end);
  }
  var lastAuto = 0;
  function autoPlace(force){          // a window the user has not moved steps aside when a HUD panel (e.g. the cut panel) opens under it (the legend also avoids the panel)
    var tn = nowMs(); if ((!force && tn - lastAuto < 350) || phone()) return; lastAuto = tn;
    [[panel, P.pn, "top"], [legend, P.lg, "bottom"]].forEach(function(w){
      var e = w[0], st = w[1]; if (!e || e.hidden || st.user) return;
      var r = e.getBoundingClientRect(), now = overlapArea(r.left, r.top, r.width, r.height, obstRects(e, e === legend));
      if (now <= 0) return;
      var b = bestCorner(r.width, r.height, e, w[2], e === legend);
      if (b.ov < now * 0.6){ st.x = b.x; st.y = b.y; placeWin(e, st, w[2]); }
    });
  }
  function openPanel(on){
    if (!panel) return;
    panel.hidden = !on;
    if (on){ if (P.mode === "off") setMode("vis"); placeWin(panel, P.pn, "top"); if (phone() && legend && !legend.hidden) openLegend(false); }
    if (tbtn) tbtn.classList.toggle("lb-open", !!on);
    if (cur) layout();
  }
  /* ---- legend window ---- */
  var lgSearch = "", lgSig = "", lgTimer = 0;
  function legendApplySize(){
    if (!legend) return;
    legend.style.setProperty("--lg-fs", P.lg.font + "px");
    var fl = $("lg-font"), fv = $("lg-font-v"); if (fl){ fl.value = P.lg.font; } if (fv) fv.textContent = P.lg.font + " px";
    [].forEach.call(legend.querySelectorAll("[data-size]"), function(b){ b.setAttribute("aria-pressed", String(b.getAttribute("data-size") === P.lg.size)); });
    var on = $("lg-only"); if (on) [].forEach.call(on.querySelectorAll("button"), function(b){ b.setAttribute("aria-pressed", String(b.getAttribute("data-v") === P.lg.only)); });
    if (phone()){
      legend.classList.add("lb-phone"); legend.style.width = ""; legend.style.height = ({S:"30vh", M:"44vh", L:"72vh"})[P.lg.size] || "44vh";
    } else {
      legend.classList.remove("lb-phone");
      var w = Math.min(P.lg.w, vw() - 8), h = Math.min(P.lg.h, vh() - 8); legend.style.width = w + "px"; legend.style.height = h + "px";
    }
  }
  function openLegend(on){
    if (!legend) return;
    P.lg.open = !!on; legend.hidden = !on; legendApplySize();
    if (on){ placeWin(legend, P.lg, "bottom"); legendRender(true); if (phone() && panel) panel.hidden = true; }
    var lb = $("lab-legend-btn"); if (lb) lb.setAttribute("aria-pressed", String(!!on));
    persist(); if (cur) layout();
  }
  function legendSoon(){
    if (!legend || legend.hidden || lgTimer) return;
    lgTimer = setTimeout(function(){ lgTimer = 0; legendRender(); }, 120);
  }
  function legendRender(force){
    var list = $("lg-list"); if (!list || !legend || legend.hidden) return;
    var q = lgSearch.trim().toLowerCase(), ids = [], i;
    if (P.lg.only === "shown"){ ids = shown.slice(); }
    else { for (i = 0; i < N; i++) ids.push(i); }
    if (q) ids = ids.filter(function(k){ return abbr[k].toLowerCase().indexOf(q) >= 0 || full[k].toLowerCase().indexOf(q) >= 0; });
    ids.sort(function(a, b){ return abbr[a].localeCompare(abbr[b]); });
    var total = ids.length, CAP = 300; if (ids.length > CAP) ids = ids.slice(0, CAP);
    var sel = E.selected(), sig = P.lg.only + "|" + q + "|" + ids.join(",") + "|" + sel + "|" + P.lg.font;
    if (!force && sig === lgSig) return; lgSig = sig;
    var html = "";
    ids.forEach(function(k){
      var c = E.color(k) || [150, 150, 150];
      html += '<div class="lg-row' + (S[k].id === sel ? " lg-sel" : "") + '" role="listitem" data-i="' + k + '"><span class="lg-sw" style="background:rgb(' + Math.round(c[0]) + "," + Math.round(c[1]) + "," + Math.round(c[2]) +
              ')"></span><b class="lg-ab' + (gen[k] ? " lg-gen" : "") + '">' + esc(abbr[k]) + '</b><span class="lg-nm">' + esc(full[k]) + (VK[k] && haveCal ? ' <span class="lg-d">' + (VK[k] === "n" ? "nerve" : VK[k] === "v" ? "vein" : "artery") + (VD[k] != null ? " &middot; \u00d8 " + VD[k].toFixed(1) + " mm" : "") + " &middot; level " + VL[k] + "</span>" : "") + "</span></div>";
    });
    if (!ids.length) html = '<p class="lg-none">' + (P.lg.only === "shown" ? "No labels on screen yet. Switch Labels on, or choose All structures." : "No match.") + "</p>";
    list.innerHTML = html;
    var cnt = $("lg-count"); if (cnt) cnt.textContent = total + (total === 1 ? " entry" : " entries") + (total > CAP ? " (first " + CAP + ", refine the search)" : "");
  }
  /* ---- wiring ---- */
  function bindSeg(id, key){
    var g = $(id); if (!g) return;
    g.addEventListener("click", function(e){
      var b = e.target.closest ? e.target.closest("button") : null; if (!b || !g.contains(b)) return;
      var v = b.getAttribute("data-v");
      if (key === "mode") setMode(v); else set(key, v);
    });
  }
  function bindUI(){
    if (!panel) return;
    bindSeg("lab-show", "mode"); bindSeg("lab-text", "text"); bindSeg("lab-callout", "callout"); bindSeg("lab-colour", "colour");
    $("lab-dens").addEventListener("input", function(){ set("density", this.value); });
    $("lab-font").addEventListener("input", function(){ set("font", this.value); });
    $("lab-side").addEventListener("change", function(){ set("side", this.checked); });
    $("lab-occl").addEventListener("change", function(){ set("occl", this.checked); });
    $("lab-reset").addEventListener("click", reset);
    bindSeg("lab-lva", "lva"); bindSeg("lab-lvn", "lvn");
    $("lab-vhide").addEventListener("change", function(){ set("vhide", this.checked); });
    ["a", "v", "n"].forEach(function(k){ $("lab-g-" + k).addEventListener("click", function(){ set("g" + k, !P.vn[k]); }); });
    $("lab-da").addEventListener("input", function(){ set("da", this.value); }); $("lab-dn").addEventListener("input", function(){ set("dn", this.value); });
    $("lab-close").addEventListener("click", function(){ openPanel(false); });
    $("lab-min").addEventListener("click", function(){ P.pn.min = !P.pn.min; applyUI(); persist(); placeWin(panel, P.pn); });
    $("lab-legend-btn").addEventListener("click", function(){ openLegend(legend.hidden); });
    var cf = $("lab-cutfill"); if (cf) cf.addEventListener("click", function(){ if (E.fillCut) E.fillCut(); needHeavy = true; });
    drag(panel, $("lab-head"), P.pn);
    if (legend){
      drag(legend, $("lg-head"), P.lg);
      $("lg-close").addEventListener("click", function(){ openLegend(false); });
      [].forEach.call(legend.querySelectorAll("[data-size]"), function(b){ b.addEventListener("click", function(){
        var sz = b.getAttribute("data-size"); if (!SIZES[sz]) return; P.lg.size = sz; P.lg.w = Math.min(SIZES[sz][0], vw() - 8); P.lg.h = Math.min(SIZES[sz][1], vh() - 8); legendApplySize(); placeWin(legend, P.lg); persist();
      }); });
      function fontTo(v){ P.lg.font = Math.round(num(v, 10, 24, P.lg.font)); legendApplySize(); persist(); legendRender(true); }
      $("lg-fdn").addEventListener("click", function(){ fontTo(P.lg.font - 1); }); $("lg-fup").addEventListener("click", function(){ fontTo(P.lg.font + 1); });
      $("lg-font").addEventListener("input", function(){ fontTo(this.value); });
      $("lg-q").addEventListener("input", function(){ lgSearch = this.value; legendRender(true); });
      $("lg-only").addEventListener("click", function(e){ var b = e.target.closest ? e.target.closest("button") : null; if (!b) return; P.lg.only = b.getAttribute("data-v"); legendApplySize(); persist(); legendRender(true); });
      $("lg-list").addEventListener("click", function(e){
        var r = e.target.closest ? e.target.closest(".lg-row") : null; if (!r) return; var k = +r.getAttribute("data-i"); if (S[k]) E.select(S[k].id); legendRender(true);
      });
      $("lg-list").addEventListener("pointerover", function(e){ var r = e.target.closest ? e.target.closest(".lg-row") : null; var id = r ? S[+r.getAttribute("data-i")].id : null; if (id !== hotId) hot(id); });
      $("lg-list").addEventListener("pointerleave", function(){ hot(null); });
      var grip = $("lg-grip"), gs = null;
      grip.addEventListener("pointerdown", function(e){ if (phone()) return; gs = {x:e.clientX, y:e.clientY, w:legend.offsetWidth, h:legend.offsetHeight}; try { grip.setPointerCapture(e.pointerId); } catch (err){} e.preventDefault(); });
      grip.addEventListener("pointermove", function(e){
        if (!gs) return;
        var r = legend.getBoundingClientRect();
        P.lg.w = Math.round(Math.max(200, Math.min(vw() - r.left - 4, gs.w + e.clientX - gs.x))); P.lg.h = Math.round(Math.max(140, Math.min(vh() - r.top - 4, gs.h + e.clientY - gs.y)));
        P.lg.size = ""; legendApplySize();
      });
      function gend(){ if (gs){ gs = null; persist(); } }
      grip.addEventListener("pointerup", gend); grip.addEventListener("pointercancel", gend);
    }
    window.addEventListener("resize", function(){
      if (panel && !panel.hidden) placeWin(panel, P.pn); if (legend && !legend.hidden){ legendApplySize(); placeWin(legend, P.lg); }
      needHeavy = true; if (P.mode !== "off" && E.redraw) E.redraw();
    });
    window.addEventListener("keydown", function(e){
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      var t = e.target, tag = t && t.tagName; if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable)) return;
      if (e.key === "l" || e.key === "L"){ var order = ["off", "sel", "vis", "all"]; setMode(order[(order.indexOf(P.mode) + 1) % order.length]); e.preventDefault(); }
      else if (e.key === "Escape" && legend && !legend.hidden && document.activeElement && legend.contains(document.activeElement)) openLegend(false);
    });
  }
  function mountToolbar(){
    var tb = E.toolbar; if (!tb) return;
    tbtn = document.createElement("button"); tbtn.type = "button"; tbtn.id = "t-labels"; tbtn.className = E.toolClass || "tool"; tbtn.textContent = "Labels";
    tbtn.setAttribute("aria-pressed", "false"); tbtn.title = "Names or abbreviations on the structures, with leader lines when crowded (key L cycles Off / Selected / Visible / All)";
    tbtn.addEventListener("click", function(){ openPanel(panel.hidden); });
    var ref = $("t-reset") || null; if (ref && ref.parentNode === tb) tb.insertBefore(tbtn, ref); else tb.appendChild(tbtn);
  }
  mountToolbar(); bindUI(); applyUI(); legendApplySize();
  if (P.mode !== "off") enabled = true;
  if (legend && P.lg.open){ legend.hidden = false; setTimeout(function(){ openLegend(true); }, 0); }
  statusText();
  return {
    engine:function(){ return E; }, update:update, dirty:dirty, hover:hover, set:set, setMode:setMode, reset:reset, openPanel:openPanel, openLegend:openLegend, refreshNow:function(){ refresh(); layout(); },
    selectId:function(id){ if (idx[id] != null) E.select(id); },
    abbr:function(id){ var k = idx[id]; return k == null ? null : abbr[k]; }, fullName:function(id){ var k = idx[id]; return k == null ? null : full[k]; },
    settings:function(){ return JSON.parse(JSON.stringify(P)); },
    state:function(){
      return {mode:P.mode, text:P.text, callout:P.callout, density:P.density, font:P.font, colour:P.colour, shown:shown.map(function(k){ return S[k].id; }), visible:cur ? cur.visible : 0,
              heavyMs:Math.round(lastHeavyMs * 10) / 10, idMs:Math.round(lastIdMs * 10) / 10, layoutMs:Math.round(layoutMs * 100) / 100, heavyCount:heavyCount, storageOK:storageOK, hasTable:haveTable,
              animating:animating, modes:JSON.parse(JSON.stringify(inlineMode)), legendOpen:!!(legend && !legend.hidden), panelOpen:!!(panel && !panel.hidden), cutOn:!!(cur && cur.cutOn), capOn:!!(cur && cur.capOn),
              vn:JSON.parse(JSON.stringify(P.vn)), haveCal:haveCal, calCount:calCount, vnShown:shown.filter(function(k){ return !!VK[k]; }).map(function(k){ return S[k].id; }), vnVisible:cur ? cur.vnVisible : 0,
              kinds:cur ? cur.items.reduce(function(a, it){ a[it.kind] = (a[it.kind] || 0) + 1; return a; }, {}) : {}};
    },
    boxes:function(){        // the drawn label boxes, for tests: [{id, x,y,w,h, mode, ax,ay}]
      var out = [];
      for (var id in elMap){ var e = elMap[id]; if (e && e.px != null){ var tw = measure(e.text || "", P.font) + 8; out.push({id:id, x:e.px, y:e.py - P.font * 0.35, w:tw, h:P.font * 1.3 + 3, text:e.text, lead:e.pts || "", mode:e.pts ? "out" : "in"}); } }
      return out;
    },
    mask:function(){ return cur && cur.mask; },
    anchors:function(){ return cur ? cur.items.map(function(it){ return {id:it.id, kind:it.kind, p3:it.p3, long:it.long || 0, sx:it.sx, sy:it.sy}; }) : []; },
    calibre:function(id){ var k = idx[id]; return k == null ? null : {kind:VK[k], diameter:VD[k], level:VL[k], promoted:VP[k]}; },
    /* geometry self-check of what is drawn now (tests / browser checks): overlaps between label boxes, callout boxes touching the body silhouette, boxes outside the canvas or
       inside a HUD panel, crossing leader lines, leader lengths */
    selfCheck:function(){
      var b = [], id, i, j, rect = cur && cur.rect, M = cur && cur.mask, obs = [];
      for (id in elMap){ var e = elMap[id]; if (e && e.px != null) b.push({id:id, x:e.x, y:e.y, w:e.w, h:e.h, mode:e.mode, forced:e.forced, ax:e.ax, ay:e.ay}); }
      try { allObst().forEach(function(o){ if (!o || !o.getBoundingClientRect || o.hidden) return; var r = o.getBoundingClientRect(); if (r.width > 4 && r.height > 4 && getComputedStyle(o).display !== "none") obs.push({left:r.left, right:r.right, top:r.top, bottom:r.bottom, id:o.id}); }); } catch (err){}
      var res = {n:b.length, inline:0, callout:0, overlaps:0, bodyHits:0, outsideFrame:0, obstacleHits:0, leaderCrossings:0, meanLeader:0, maxLeader:0, forced:0}, ls = [], tot = 0;
      for (i = 0; i < b.length; i++){
        var a = b[i]; if (a.mode === "in") res.inline++; else res.callout++;
        if (a.forced) res.forced++;
        for (j = i + 1; j < b.length; j++){ var c = b[j]; if (Math.abs(a.x - c.x) < (a.w + c.w) / 2 - 0.5 && Math.abs(a.y - c.y) < (a.h + c.h) / 2 - 0.5) res.overlaps++; }
        if (rect && (a.x - a.w / 2 < rect.left - 1 || a.x + a.w / 2 > rect.left + rect.width + 1 || a.y - a.h / 2 < rect.top - 1 || a.y + a.h / 2 > rect.top + rect.height + 1)) res.outsideFrame++;
        if (a.mode === "out" && !a.forced && M && M.n && NMSKLabelsCore.maskCount(M, a.x - a.w / 2, a.y - a.h / 2, a.x + a.w / 2, a.y + a.h / 2) > 0) res.bodyHits++;
        obs.forEach(function(r){ if (a.x - a.w / 2 < r.right && a.x + a.w / 2 > r.left && a.y - a.h / 2 < r.bottom && a.y + a.h / 2 > r.top){ res.obstacleHits++; (res.hitWhat = res.hitWhat || []).push(a.id + "@" + r.id + "[" + a.mode + "]"); } });
        if (a.mode === "out"){ var ep = NMSKLabelsCore.edgePoint({x:a.x, y:a.y}, a.w, a.h, a.ax, a.ay), len = Math.hypot(ep.x - a.ax, ep.y - a.ay); tot += len; res.maxLeader = Math.max(res.maxLeader, len); if (!a.forced) ls.push({x1:a.ax, y1:a.ay, x2:ep.x, y2:ep.y}); }
      }
      for (i = 0; i < ls.length; i++) for (j = i + 1; j < ls.length; j++) if (NMSKLabelsCore.segX(ls[i], ls[j])) res.leaderCrossings++;
      res.meanLeader = ls.length ? Math.round(tot / ls.length) : 0; res.maxLeader = Math.round(res.maxLeader);
      return res;
    }
  };
}
