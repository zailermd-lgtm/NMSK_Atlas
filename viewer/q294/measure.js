/* Q294: measurement tools -- point-to-point distance, 3-point angle, angle between two lines, Cobb angle -- on the 3-D model of
   either engine and on any 2-D image pane an optional add-on registers (CT / MR / echo panes: NMSKMeasure.surface(el, adaptor)).
   Pure math in NMSKMeasureCore (no DOM, runs under node). Points are kept in each surface's own millimetre frame (3-D: the
   model frame; a 2-D pane: its image plane), so a value never depends on the zoom, the pan or the window size.
     NMSKMeasure.surface(el, {name, toMM(ev) -> [x, y] | null, fromMM([x, y]) -> [clientX, clientY] | null})   a 2-D pane
     NMSKMeasure.start(api, {toolbar, cls})   the 3-D model through the generic add-on API (pick / ray / toScreen / geometry)
     ctl.consumeClick(ev)   the engine's tap handler asks first: true = the tap placed (or tried to place) a measurement point
     ctl.arm(kind) kind = dist | ang3 | ang2 | cobb | circ | area | surf | vol | pix | null    ctl.add(kind, surfaceId, pts[, structure])   ctl.clear()   ctl.remove(id)   ctl.state()
   One tap on a structure of the 3-D model (its own triangles, posed if it is posed; model frame = mm, the same frame `dist` reads):
   circ / area = the closed loop of the mesh cut by a plane -- the active cut plane when a cut is on (the tapped point on the cut
   face picks the loop), else the plane through the tapped point perpendicular to the structure's long axis (principal axis of its
   surface; view-independent, so the same tap gives the same number from any angle) -- its length (mm) and the area it encloses
   (shoelace in that plane, cm2). surf = sum of the triangle areas (cm2). vol = signed tetrahedra (divergence theorem, cm3), reported
   only for a closed, consistently oriented surface. pix = the expected CT number of the structure's class from the page's own
   sourced reference (NMSKTissue), shown only when that value's status is sourced.
   Cobb: two lines along the two endplates; the Cobb angle is the angle between them (= the angle between their perpendiculars),
   0-90 deg. On the 3-D model the angle between the two 3-D lines is given, plus the angle in the current view plane (what a
   radiograph taken along the view direction would show). Results: one small chip per measurement on the image and in the bar. */
var NMSKMeasureCore = (function(){
  "use strict";
  var D = 180 / Math.PI;
  function sub(a, b){ return a.map(function(x, i){ return x - b[i]; }); }
  function dot(a, b){ var s = 0; for (var i = 0; i < a.length; i++) s += a[i] * b[i]; return s; }
  function len(a){ return Math.sqrt(dot(a, a)); }
  function dist(a, b){ return len(sub(a, b)); }
  function angleBetween(u, v){ var l = len(u) * len(v); if (!(l > 1e-12)) return NaN; return Math.acos(Math.max(-1, Math.min(1, dot(u, v) / l))) * D; }
  function angle3(a, b, c){ return angleBetween(sub(a, b), sub(c, b)); }                     // the angle at b
  function lineAngle(a1, a2, b1, b2){ var t = angleBetween(sub(a2, a1), sub(b2, b1)); return t > 90 ? 180 - t : t; }   // 0..90 (lines have no direction)
  function project(p, n){ var k = dot(p, n) / dot(n, n); return p.map(function(x, i){ return x - k * n[i]; }); }
  function cobb(a1, a2, b1, b2, viewN){
    var r = {deg:lineAngle(a1, a2, b1, b2)};
    r.perp = r.deg;                                                                          // perpendiculars of two lines in one plane meet at the same angle
    if (viewN && a1.length === 3) r.view = lineAngle(project(a1, viewN), project(a2, viewN), project(b1, viewN), project(b2, viewN));
    return r;
  }
  /* ---- one tap on a structure: its cross-section, surface area, volume (the structure's own triangles, model frame = mm) ---- */
  function cross3(a, b){ return [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]]; }
  function unit(a){ var l = len(a); return l > 1e-12 ? a.map(function(x){ return x / l; }) : null; }
  function basis(n){                                                      // two unit vectors spanning the plane with normal n
    var N = unit(n), h = Math.abs(N[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0], u = unit(cross3(N, h));
    return {n:N, u:u, v:cross3(N, u)};
  }
  /* vertices merged by position (0.1 um grid): meshes split at normal / texture seams share their edges again, so a seam is
     not counted as a hole and a section loop runs across it; collapsed triangles (two corners merged) are dropped -- no area, no volume */
  function weld(pos, idx){
    var n = pos.length / 3, map = new Map(), id = new Int32Array(n), P = [], q = 1e4, v, t;
    for (v = 0; v < n; v++){
      var k = Math.round(pos[3*v] * q) + "," + Math.round(pos[3*v+1] * q) + "," + Math.round(pos[3*v+2] * q), j = map.get(k);
      if (j === undefined){ j = P.length / 3; map.set(k, j); P.push(pos[3*v], pos[3*v+1], pos[3*v+2]); }
      id[v] = j;
    }
    var T = [], nt = Math.floor(idx.length / 3), degen = 0;
    for (t = 0; t < nt; t++){ var a = id[idx[3*t]], b = id[idx[3*t+1]], c = id[idx[3*t+2]]; if (a === b || b === c || a === c){ degen++; continue; } T.push(a, b, c); }
    return {P:new Float64Array(P), T:new Int32Array(T), nv:P.length / 3, degen:degen};
  }
  /* every undirected edge: used once = boundary (a hole), more than twice = non-manifold, twice in the SAME direction = the two
     triangles disagree on which side is outside (then a signed volume means nothing) */
  function edgeStats(W){
    var m = new Map(), T = W.T, nv = W.nv, out = {edges:0, boundary:0, nonManifold:0, misoriented:0};
    for (var t = 0; t < T.length; t += 3) for (var e = 0; e < 3; e++){
      var a = T[t+e], c = T[t+(e+1)%3], k = a < c ? a * nv + c : c * nv + a, r = m.get(k);
      if (!r){ r = [0, 0]; m.set(k, r); }
      r[0]++; r[1] += a < c ? 1 : -1;
    }
    out.edges = m.size;
    m.forEach(function(r){ if (r[0] === 1) out.boundary++; else if (r[0] > 2) out.nonManifold++; else if (r[1] !== 0) out.misoriented++; });
    return out;
  }
  /* surface area = SUM |e1 x e2| / 2.  Volume (divergence theorem) = |SUM a . (b x c)| / 6 over the triangles (signed tetrahedra to a
     reference point), valid only for a closed, consistently oriented surface: otherwise volume = null and the reason is returned */
  function solid(pos, idx){
    var W = weld(pos, idx), E = edgeStats(W), P = W.P, T = W.T, A = 0, V = 0, o = [0, 0, 0], k;
    for (k = 0; k < W.nv; k++){ o[0] += P[3*k]; o[1] += P[3*k+1]; o[2] += P[3*k+2]; }
    if (W.nv){ o = o.map(function(x){ return x / W.nv; }); }             // tetrahedra to the centroid: same sum for a closed surface, less round-off
    for (var t = 0; t < T.length; t += 3){
      var a = [P[3*T[t]] - o[0], P[3*T[t]+1] - o[1], P[3*T[t]+2] - o[2]], b = [P[3*T[t+1]] - o[0], P[3*T[t+1]+1] - o[1], P[3*T[t+1]+2] - o[2]], c = [P[3*T[t+2]] - o[0], P[3*T[t+2]+1] - o[1], P[3*T[t+2]+2] - o[2]];
      A += len(cross3(sub(b, a), sub(c, a))) / 2;
      V += dot(a, cross3(b, c)) / 6;
    }
    var closed = T.length > 0 && E.boundary === 0 && E.nonManifold === 0, ok = closed && E.misoriented === 0;
    return {tris:T.length / 3, verts:W.nv, degen:W.degen, area:A, signed:V, volume:ok ? Math.abs(V) : null, closed:closed, oriented:E.misoriented === 0,
            boundary:E.boundary, nonManifold:E.nonManifold, misoriented:E.misoriented,
            why:ok ? "" : !T.length ? "no triangles" : E.boundary ? "not closed (" + E.boundary + " boundary edges)" : E.nonManifold ? "not closed (" + E.nonManifold + " non-manifold edges)" : "not consistently oriented (" + E.misoriented + " edges)"};
  }
  /* the plane n.x + c = 0 through the mesh: each triangle whose corners straddle it gives one segment between the crossing points of
     its two crossing edges; segments share a crossing point exactly when they share the (welded) edge, so the loops are chained by
     edge, not by a distance tolerance. A corner exactly on the plane counts as the positive side. -> [{pts:[[x,y,z]...], closed}] */
  function section(pos, idx, n, c){
    var W = weld(pos, idx), P = W.P, T = W.T, nv = W.nv, nl = len(n), N = [n[0] / nl, n[1] / nl, n[2] / nl], cc = c / nl, v, t;
    var d = new Float64Array(nv), pt = new Map(), adj = new Map(), seg = [];
    for (v = 0; v < nv; v++) d[v] = N[0] * P[3*v] + N[1] * P[3*v+1] + N[2] * P[3*v+2] + cc;
    function node(a, b){
      var k = a < b ? a * nv + b : b * nv + a;
      if (!pt.has(k)){ var s = d[a] / (d[a] - d[b]); pt.set(k, [P[3*a] + s * (P[3*b] - P[3*a]), P[3*a+1] + s * (P[3*b+1] - P[3*a+1]), P[3*a+2] + s * (P[3*b+2] - P[3*a+2])]); }
      return k;
    }
    for (t = 0; t < T.length; t += 3){
      var ks = [];
      for (var e = 0; e < 3; e++){ var a = T[t+e], b = T[t+(e+1)%3]; if ((d[a] >= 0) !== (d[b] >= 0)) ks.push(node(a, b)); }
      if (ks.length !== 2) continue;
      var si = seg.length; seg.push(ks);
      ks.forEach(function(k){ var L = adj.get(k); if (!L) adj.set(k, L = []); L.push(si); });
    }
    var used = new Uint8Array(seg.length), loops = [];
    function step(k){ var L = adj.get(k) || []; for (var i = 0; i < L.length; i++) if (!used[L[i]]){ used[L[i]] = 1; return seg[L[i]][0] === k ? seg[L[i]][1] : seg[L[i]][0]; } return null; }
    for (var s0 = 0; s0 < seg.length; s0++){
      if (used[s0]) continue;
      used[s0] = 1;
      var start = seg[s0][0], cur = seg[s0][1], chain = [start, cur], closed = false, nx;
      while ((nx = step(cur)) != null){ if (nx === start){ closed = true; break; } chain.push(nx); cur = nx; }
      if (!closed){ var back = [], cb = start; while ((nx = step(cb)) != null){ back.push(nx); cb = nx; } chain = back.reverse().concat(chain); }
      loops.push({pts:chain.map(function(k){ return pt.get(k); }), closed:closed});
    }
    return loops;
  }
  function loopLength(pts, closed){
    var s = 0; for (var i = 1; i < pts.length; i++) s += dist(pts[i - 1], pts[i]);
    return closed && pts.length > 2 ? s + dist(pts[pts.length - 1], pts[0]) : s;
  }
  function plane2(pts, B){ var o = pts[0]; return pts.map(function(p){ var q = sub(p, o); return [dot(q, B.u), dot(q, B.v)]; }); }
  function loopArea(pts, n){                                              // shoelace in the plane's own 2-D frame
    if (pts.length < 3) return 0;
    var q = plane2(pts, basis(n)), s = 0;
    for (var i = 0; i < q.length; i++){ var j = (i + 1) % q.length; s += q[i][0] * q[j][1] - q[j][0] * q[i][1]; }
    return Math.abs(s) / 2;
  }
  function inLoop(pts, p, n){                                             // even-odd test of p (projected on the plane) against a closed loop
    var B = basis(n), o = pts[0], q = plane2(pts, B), x = dot(sub(p, o), B.u), y = dot(sub(p, o), B.v), c = false;
    for (var i = 0, j = q.length - 1; i < q.length; j = i++) if ((q[i][1] > y) !== (q[j][1] > y) && x < (q[j][0] - q[i][0]) * (y - q[i][1]) / (q[j][1] - q[i][1]) + q[i][0]) c = !c;
    return c;
  }
  function segDist(p, a, b){ var ab = sub(b, a), l2 = dot(ab, ab), t = l2 > 0 ? Math.max(0, Math.min(1, dot(sub(p, a), ab) / l2)) : 0; return dist(p, [a[0] + t * ab[0], a[1] + t * ab[1], a[2] + t * ab[2]]); }
  function loopDist(L, p){ var m = Infinity, P = L.pts; for (var i = 1; i < P.length; i++) m = Math.min(m, segDist(p, P[i - 1], P[i])); if (L.closed && P.length > 2) m = Math.min(m, segDist(p, P[P.length - 1], P[0])); return P.length === 1 ? dist(p, P[0]) : m; }
  /* the loop the tap belongs to: the one it lies on (within 1 mm), else the smallest closed loop around it, else the nearest */
  function pickLoop(loops, p, n){
    var best = -1, bd = Infinity, i;
    for (i = 0; i < loops.length; i++){ var dd = loopDist(loops[i], p); if (dd < bd){ bd = dd; best = i; } }
    if (bd <= 1) return best;
    var inner = -1, ia = Infinity;
    for (i = 0; i < loops.length; i++) if (loops[i].closed && inLoop(loops[i].pts, p, n)){ var a = loopArea(loops[i].pts, n); if (a < ia){ ia = a; inner = i; } }
    return inner >= 0 ? inner : best;
  }
  /* the structure's long axis: principal axis of its surface (area-weighted triangle centroids), by power iteration */
  function longAxis(pos, idx){
    var nt = Math.floor(idx.length / 3), S = 0, m = [0, 0, 0], C = [0, 0, 0, 0, 0, 0], cs = [], t, k;
    for (t = 0; t < nt; t++){
      var a = idx[3*t] * 3, b = idx[3*t+1] * 3, c = idx[3*t+2] * 3, A = [pos[a], pos[a+1], pos[a+2]], Bv = [pos[b], pos[b+1], pos[b+2]], Cv = [pos[c], pos[c+1], pos[c+2]];
      var w = len(cross3(sub(Bv, A), sub(Cv, A))) / 2, g = [(A[0] + Bv[0] + Cv[0]) / 3, (A[1] + Bv[1] + Cv[1]) / 3, (A[2] + Bv[2] + Cv[2]) / 3];
      if (!(w > 0)) continue;
      cs.push(g, w); S += w; m[0] += w * g[0]; m[1] += w * g[1]; m[2] += w * g[2];
    }
    if (!(S > 0)) return [0, 1, 0];
    m = m.map(function(x){ return x / S; });
    for (k = 0; k < cs.length; k += 2){ var q = sub(cs[k], m), ww = cs[k + 1]; C[0] += ww*q[0]*q[0]; C[1] += ww*q[0]*q[1]; C[2] += ww*q[0]*q[2]; C[3] += ww*q[1]*q[1]; C[4] += ww*q[1]*q[2]; C[5] += ww*q[2]*q[2]; }
    var M = [[C[0], C[1], C[2]], [C[1], C[3], C[4]], [C[2], C[4], C[5]]], dg = [C[0], C[3], C[5]], i0 = dg.indexOf(Math.max.apply(null, dg)), v = [0, 0, 0]; v[i0] = 1; v = unit([v[0] + 0.01, v[1] + 0.02, v[2] + 0.03]);
    for (k = 0; k < 200; k++){ var nv2 = unit([dot(M[0], v), dot(M[1], v), dot(M[2], v)]); if (!nv2) break; v = nv2; }
    return v;
  }
  function rayPlane(o, d, pl){ var dn = pl[0] * d[0] + pl[1] * d[1] + pl[2] * d[2]; if (Math.abs(dn) < 1e-12) return null; var t = -(pl[0] * o[0] + pl[1] * o[1] + pl[2] * o[2] + pl[3]) / dn; return t > 0 ? [o[0] + t * d[0], o[1] + t * d[1], o[2] + t * d[2]] : null; }
  /* the cross-section through p: in plane pl ([nx, ny, nz, c], the active cut) if given, else the plane through p perpendicular to the
     structure's long axis. -> {perim mm, area mm2 (enclosed by THAT loop), n, c, how, loops, loop} or {err} */
  function sectionAt(pos, idx, p, pl){
    var n = pl ? unit(pl.slice(0, 3)) : longAxis(pos, idx), c = pl ? pl[3] / len(pl.slice(0, 3)) : -dot(n, p);
    var how = pl ? "in the cut plane" : "perpendicular to its long axis", loops = section(pos, idx, n, c);
    if (!loops.length) return {err:(pl ? "the cut plane does not cross this structure" : "no section through this point"), how:how};
    var k = pickLoop(loops, p, n), L = loops[k];
    if (!L.closed) return {err:"the section is not closed here (the mesh is open) -- not reported", how:how, loops:loops.length, loop:L.pts};
    return {perim:loopLength(L.pts, true), area:loopArea(L.pts, n), n:n, c:c, how:how, loops:loops.length, closedLoops:loops.filter(function(x){ return x.closed; }).length, loop:L.pts};
  }
  /* the expected CT number of the tapped structure, from the page's own sourced reference (T = its tissue-reference module: classOf / hu /
     status / label). Only a value whose status is sourced is shown; anything else says so instead of showing a number. */
  var SOURCED = {verified:1, derived:1, secondary_checked:1};
  function pointValue(T, rec){
    rec = rec || {};
    if (!T || !T.ready || !T.ready()) return {v:null, unit:"", text:"No sourced value (no value reference on this page)"};
    var cls = T.classOf(rec.cat, rec.id, rec.name, rec.vt), st = T.status(cls), lab = T.label ? T.label(cls) : cls;
    if (!SOURCED[st] || typeof T.hu(cls) !== "number") return {v:null, unit:"", cls:cls, status:st, text:"No sourced value · " + lab + " (" + String(st).replace(/_/g, " ") + ")"};
    var v = T.hu(cls);
    return {v:v, unit:"HU", cls:cls, status:st, text:"CT ≈ " + (Math.round(v * 10) / 10) + " HU · " + lab + " (" + String(st).replace(/_/g, " ") + ")"};
  }
  var NEED = {dist:2, ang3:3, ang2:4, cobb:4, circ:1, area:1, surf:1, vol:1, pix:1}, NAME = {dist:"Distance", ang3:"Angle (3 points)", ang2:"Angle between 2 lines", cobb:"Cobb angle",
    circ:"Circumference", area:"Cross-section area", surf:"Surface area", vol:"Volume", pix:"Expected CT value"};
  var ONE = {circ:1, area:1, surf:1, vol:1, pix:1};                       // one tap on a structure of the 3-D model
  function structLabel(kind, r){                                          // r: sectionAt / solid / pointValue result -> {v, unit, text, note}
    if (kind === "pix") return r;
    if (kind === "circ" || kind === "area"){
      if (r.err) return {v:null, unit:"", text:NAME[kind] + ": " + r.err, note:r.how, loop:r.loop};
      var o = kind === "circ" ? {v:r.perim, unit:"mm", text:"Circumference " + r.perim.toFixed(1) + " mm"} : {v:r.area / 100, unit:"cm²", text:"Section area " + (r.area / 100).toFixed(2) + " cm² (" + r.area.toFixed(0) + " mm²)"};
      o.note = "section " + r.how + (r.loops > 1 ? "; the loop at the tap, 1 of " + r.loops : ""); o.loop = r.loop; o.mm = kind === "circ" ? r.perim : r.area; o.plane = r.n.concat([r.c]).map(function(x){ return Math.round(x * 1e6) / 1e6; });
      return o;
    }
    if (kind === "surf") return {v:r.area / 100, unit:"cm²", mm:r.area, text:"Surface area " + (r.area / 100).toFixed(1) + " cm²" + (r.closed ? "" : " (open mesh)"), note:"whole structure surface, " + r.tris + " triangles"};
    if (kind === "vol"){
      if (r.volume == null) return {v:null, unit:"", text:"Volume: " + r.why + " -- volume not reported", note:r.why};
      return {v:r.volume / 1000, unit:"cm³", mm:r.volume, text:"Volume " + (r.volume / 1000).toFixed(2) + " cm³", note:"closed surface, " + r.tris + " triangles"};
    }
    return null;
  }
  function value(kind, p, viewN){
    if (!p || p.length < NEED[kind]) return null;
    if (kind === "dist") return {v:dist(p[0], p[1]), unit:"mm"};
    if (kind === "ang3") return {v:angle3(p[0], p[1], p[2]), unit:"deg"};
    if (kind === "ang2") return {v:lineAngle(p[0], p[1], p[2], p[3]), unit:"deg"};
    if (kind === "cobb"){ var c = cobb(p[0], p[1], p[2], p[3], viewN); return {v:c.deg, unit:"deg", view:c.view}; }
    return null;
  }
  function label(kind, r){
    if (r && ONE[kind] && typeof r.text === "string") return r.text;
    if (!r || !isFinite(r.v)) return "";
    var s = r.unit === "mm" ? r.v.toFixed(1) + " mm" : r.v.toFixed(1) + "°";
    if (kind === "cobb") s = "Cobb " + s + (r.view != null && isFinite(r.view) && Math.abs(r.view - r.v) >= 0.1 ? " (view " + r.view.toFixed(1) + "°)" : "");
    return s;
  }
  /* ray (o, d) x triangle mesh (pos Float32 xyz, idx) -> nearest t > 0 or null (Moller-Trumbore) */
  function rayMesh(o, d, pos, idx){
    var best = null, nt = idx.length / 3;
    for (var k = 0; k < nt; k++){
      var a = idx[3*k] * 3, b = idx[3*k+1] * 3, c = idx[3*k+2] * 3;
      var e1x = pos[b] - pos[a], e1y = pos[b+1] - pos[a+1], e1z = pos[b+2] - pos[a+2], e2x = pos[c] - pos[a], e2y = pos[c+1] - pos[a+1], e2z = pos[c+2] - pos[a+2];
      var px = d[1]*e2z - d[2]*e2y, py = d[2]*e2x - d[0]*e2z, pz = d[0]*e2y - d[1]*e2x, det = e1x*px + e1y*py + e1z*pz;
      if (Math.abs(det) < 1e-12) continue;
      var inv = 1 / det, tx = o[0] - pos[a], ty = o[1] - pos[a+1], tz = o[2] - pos[a+2], u = (tx*px + ty*py + tz*pz) * inv;
      if (u < 0 || u > 1) continue;
      var qx = ty*e1z - tz*e1y, qy = tz*e1x - tx*e1z, qz = tx*e1y - ty*e1x, v = (d[0]*qx + d[1]*qy + d[2]*qz) * inv;
      if (v < 0 || u + v > 1) continue;
      var t = (e2x*qx + e2y*qy + e2z*qz) * inv;
      if (t > 1e-6 && (best == null || t < best)) best = t;
    }
    return best;
  }
  return {dist:dist, angle3:angle3, lineAngle:lineAngle, cobb:cobb, value:value, label:label, rayMesh:rayMesh, NEED:NEED, NAME:NAME, ONE:ONE,
          weld:weld, edgeStats:edgeStats, solid:solid, section:section, loopLength:loopLength, loopArea:loopArea, pickLoop:pickLoop, longAxis:longAxis,
          rayPlane:rayPlane, sectionAt:sectionAt, pointValue:pointValue, structLabel:structLabel};
})();
var NMSKMeasure = (function(){
  "use strict";
  var tbEl = null, C = NMSKMeasureCore, surf = {}, sid = 0, api = null, tool = null, pend = null, list = [], seq = 0, raf = 0, svg = null, bar = null, tb = null, geoCache = [], msg = "";
  var SVGNS = "http://www.w3.org/2000/svg";
  function $(id){ return document.getElementById(id); }
  function r1(v){ return Math.round(v * 100) / 100; }
  function surface(el, ad){
    if (!el || !ad) return null;
    var id = el.getAttribute("data-ms-id"); if (!id){ id = "p" + (++sid); el.setAttribute("data-ms-id", id); }
    surf[id] = {id:id, el:el, name:ad.name || "image", toMM:ad.toMM, fromMM:ad.fromMM, two:true};
    var down = null;
    function armedHere(){ return tool && (!pend || pend.s === id); }
    function onBtn(e){ return !!(e.target && e.target.closest && e.target.closest(".ms-pane-b")); }
    if (!el.querySelector(".ms-pane-b")){                 // a small ruler on the pane itself: measuring works even when a panel covers the toolbar
      var pb = document.createElement("button"); pb.type = "button"; pb.className = "ms-pane-b"; pb.title = "Measure on this image (distance, angles, Cobb)"; pb.setAttribute("aria-label", "Measure on this image");
      pb.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M3 17L17 3l4 4L7 21zM7 13l2 2M10 10l2 2M13 7l2 2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
      ["pointerdown", "pointerup"].forEach(function(t){ pb.addEventListener(t, function(e){ e.stopPropagation(); }); });   // the pane's own handlers (crosshair, pointer capture) never see a tap on the button
      pb.addEventListener("click", function(e){ e.stopPropagation(); if (bar && bar.hidden){ open(true); if (!tool) arm("dist"); } else open(false); });
      el.appendChild(pb);
    }
    el.addEventListener("pointerdown", function(e){ if (onBtn(e)) return; if (!armedHere() || (e.pointerType === "mouse" && e.button !== 0)) return; if (down && down.id !== e.pointerId){ down = null; return; } down = {id:e.pointerId, x:e.clientX, y:e.clientY}; e.stopPropagation(); }, true);
    el.addEventListener("pointermove", function(e){ if (down && down.id === e.pointerId) e.stopPropagation(); }, true);
    el.addEventListener("pointerup", function(e){
      if (!down || down.id !== e.pointerId) return;
      var d0 = down; down = null; e.stopPropagation();
      if (Math.hypot(e.clientX - d0.x, e.clientY - d0.y) > 8 || !armedHere()) return;
      if (C.ONE[tool]){ say(C.NAME[tool] + " works on the 3-D model: tap a structure there."); return; }
      var p = surf[id].toMM(e); if (!p){ say("Tap inside the image."); return; }
      addPoint(id, p.slice(0, 2));
    }, true);
    el.addEventListener("click", function(e){ if (tool && !onBtn(e)) { e.stopPropagation(); e.preventDefault(); } }, true);
    return id;
  }
  /* ---- the 3-D model ---- */
  function geom(i){
    for (var k = 0; k < geoCache.length; k++) if (geoCache[k].i === i) return geoCache[k].g;
    var g = null; try { g = api.geometry ? api.geometry(i) : null; } catch (err){ g = null; }
    geoCache.push({i:i, g:g}); if (geoCache.length > 6) geoCache.shift();
    return g;
  }
  /* the structure's triangles as drawn: a posed structure is measured on its posed vertices (the WebGL engine keeps them apart in
     window.__poseLive(i); the three.js engine bakes them into the geometry itself, so geometry(i) already is the posed shape) */
  function mesh(i){
    var g = geom(i); if (!g || !g.pos || !g.idx) return null;
    var pl = null; try { pl = window.__poseLive ? window.__poseLive(i) : null; } catch (err){ pl = null; }
    return pl && pl.length === g.pos.length ? {pos:pl, idx:g.idx} : g;
  }
  function pick3(e){
    var h = null, r = null; try { h = api.pick(e); } catch (err){ h = null; }
    if (!h) return null;
    try { r = api.ray(e); } catch (err){ r = null; }
    if (h.point) return {p:h.point.slice(), i:h.i, ray:r};
    var g = h.i != null ? mesh(h.i) : null;
    if (!g || !r) return null;
    var t = C.rayMesh(r.o, r.d, g.pos, g.idx);
    return t == null ? null : {p:[r.o[0] + r.d[0] * t, r.o[1] + r.d[1] * t, r.o[2] + r.d[2] * t], i:h.i, ray:r};
  }
  function point3(e){ var h = pick3(e); return h ? h.p : null; }
  function recOf(i){ try { var L = api.list ? api.list() : null; return L && L[i] ? L[i] : null; } catch (err){ return null; } }
  function cutPlane(){ var c = null; try { c = api.cut ? api.cut() : null; } catch (err){ c = null; } return c && c.length === 4 && c.every(isFinite) ? Array.prototype.slice.call(c) : null; }
  function tissueRef(){ return typeof NMSKTissue !== "undefined" ? NMSKTissue : (window.NMSKTissue || null); }
  /* one tap on structure i at p: compute once (the slicing is not redone every frame) and keep the result with the measurement */
  function measureOne(kind, i, p, ray){
    var rec = recOf(i), nm = rec ? (rec.name || rec.id) : "this structure", r = null, q = p;
    if (kind === "pix"){
      var T = tissueRef();
      if (T && !T.ready() && !(T.error && T.error())){ if (T.load) T.load().catch(function(){}); say("The value reference is still loading: tap again in a moment."); return null; }
      r = C.pointValue(T, rec);
    } else {
      var g = mesh(i); if (!g){ say("No geometry for " + nm + " on this page."); return null; }
      if (kind === "surf" || kind === "vol") r = C.structLabel(kind, C.solid(g.pos, g.idx));
      else {
        var cp = cutPlane();
        if (cp && ray){ var hit = C.rayPlane(ray.o, ray.d, cp); if (hit) q = hit; }    // with a cut: the tapped point ON the cut face
        r = C.structLabel(kind, C.sectionAt(g.pos, g.idx, q, cp));
      }
    }
    r.name = nm;
    if (r.loop){ var L = r.loop, st = Math.max(1, Math.ceil(L.length / 240)), sm = []; for (var k = 0; k < L.length; k += st) sm.push(L[k].map(r1)); r.loop = sm; }   // drawn only: the values above used every point
    var m = {id:"m" + (++seq), k:kind, s:"3d", p:[p.map(r1)], i:i, r:r};
    list.push(m); pend = null;
    say(r.text + " -- " + nm + (r.note ? " (" + r.note + ")" : "") + ". Tap again for another, or pick another tool.");
    if (window.NMSKHistory && NMSKHistory.active()) NMSKHistory.commit();
    render(); kick();
    return m;
  }
  function viewN(){ try { var v = api.view(); return v && v.dir ? v.dir : null; } catch (err){ return null; } }
  function consumeClick(e){
    if (!tool || !api) return false;
    if (pend && pend.s !== "3d"){ say("Finish this measurement on the same image first."); return true; }
    var h = pick3(e);
    if (!h){ say("Nothing under the pointer: tap on the model."); return true; }
    if (C.ONE[tool]){ measureOne(tool, h.i, h.p, h.ray); return true; }
    addPoint("3d", h.p.map(r1));
    return true;
  }
  function addPoint(s, p){
    if (!pend) pend = {s:s, p:[]};
    pend.p.push(p);
    if (pend.p.length >= C.NEED[tool]){
      var m = {id:"m" + (++seq), k:tool, s:pend.s, p:pend.p.map(function(q){ return q.map(r1); })};
      list.push(m); pend = null;
      say(C.NAME[m.k] + ": " + C.label(m.k, valueOf(m)) + ". Tap again for another, or pick another tool.");
      if (window.NMSKHistory && NMSKHistory.active()) NMSKHistory.commit();
    } else say(C.NAME[tool] + ": point " + (pend.p.length + 1) + " of " + C.NEED[tool] + (tool === "cobb" ? (pend.p.length < 2 ? " (first endplate line)" : " (second endplate line)") : "") + ".");
    render(); kick();
  }
  function valueOf(m){ return m.r ? m.r : C.value(m.k, m.p, m.s === "3d" ? viewN() : null); }
  /* ---- drawing: one fixed SVG over the page; each surface gets a nested <svg> on its own rectangle (it clips to it) ---- */
  function ensureSvg(){
    if (svg) return svg;
    svg = document.createElementNS(SVGNS, "svg"); svg.setAttribute("id", "ms-svg"); svg.setAttribute("class", "ms-svg"); svg.setAttribute("aria-hidden", "true");
    document.body.appendChild(svg); return svg;
  }
  function toClient(s, p){
    if (s === "3d") return api ? api.toScreen(p) : null;
    var S = surf[s]; if (!S) return null;
    try { return S.fromMM(p); } catch (err){ return null; }
  }
  function rectOf(s){
    var e = s === "3d" ? (api && api.canvas) : (surf[s] && surf[s].el);
    if (!e || !e.getBoundingClientRect) return null;
    var r = e.getBoundingClientRect(); if (!(r.width > 2 && r.height > 2)) return null;
    if (e.offsetParent === null && getComputedStyle(e).position !== "fixed") return null;
    return r;
  }
  function draw(){
    raf = 0; ensureSvg();
    var groups = {}, h = "";
    list.concat(pend ? [{id:"pend", k:tool, s:pend.s, p:pend.p, pend:true}] : []).forEach(function(m){ (groups[m.s] = groups[m.s] || []).push(m); });
    Object.keys(groups).forEach(function(s){
      var R = rectOf(s); if (!R) return;
      var g = "";
      groups[s].forEach(function(m){
        var q = m.p.map(function(p){ var c = toClient(s, p); return c ? [c[0] - R.left, c[1] - R.top] : null; });
        if (q.some(function(x){ return !x; })) return;
        var cls = "ms-l" + (m.pend ? " ms-pend" : "");
        function ln(a, b){ return '<line class="' + cls + '" x1="' + a[0].toFixed(1) + '" y1="' + a[1].toFixed(1) + '" x2="' + b[0].toFixed(1) + '" y2="' + b[1].toFixed(1) + '"/>'; }
        if (m.k === "dist" && q.length >= 2) g += ln(q[0], q[1]);
        if (m.k === "ang3"){ if (q.length >= 2) g += ln(q[0], q[1]); if (q.length >= 3) g += ln(q[1], q[2]); }
        if ((m.k === "ang2" || m.k === "cobb")){ if (q.length >= 2) g += ln(q[0], q[1]); if (q.length >= 4) g += ln(q[2], q[3]); }
        if (m.k === "cobb" && q.length >= 4){                       // the perpendiculars, faint, from each line's midpoint
          [[q[0], q[1]], [q[2], q[3]]].forEach(function(L){ var mx = (L[0][0] + L[1][0]) / 2, my = (L[0][1] + L[1][1]) / 2, dx = L[1][0] - L[0][0], dy = L[1][1] - L[0][1], l = Math.hypot(dx, dy) || 1;
            g += '<line class="ms-perp" x1="' + mx.toFixed(1) + '" y1="' + my.toFixed(1) + '" x2="' + (mx - dy / l * 40).toFixed(1) + '" y2="' + (my + dx / l * 40).toFixed(1) + '"/>'; });
        }
        if (m.r && m.r.loop && m.r.loop.length > 1){       // the section loop that was measured
          var lp = m.r.loop.map(function(p){ var c = toClient(s, p); return c ? (c[0] - R.left).toFixed(1) + "," + (c[1] - R.top).toFixed(1) : null; });
          if (lp.every(function(x){ return x; })) g += '<polygon class="ms-l ms-loop" points="' + lp.join(" ") + '"/>';
        }
        q.forEach(function(c){ g += '<circle class="ms-pt' + (m.pend ? " ms-pend" : "") + '" cx="' + c[0].toFixed(1) + '" cy="' + c[1].toFixed(1) + '" r="4"/>'; });
        if (!m.pend){
          var t = C.label(m.k, valueOf(m)), at = C.ONE[m.k] ? q[0] : m.k === "ang3" ? q[1] : m.k === "dist" ? [(q[0][0] + q[1][0]) / 2, (q[0][1] + q[1][1]) / 2] : [(q[0][0] + q[1][0] + q[2][0] + q[3][0]) / 4, (q[0][1] + q[1][1] + q[2][1] + q[3][1]) / 4];
          var w = 7 * t.length + 12;
          g += '<g class="ms-chip" data-mid="' + m.id + '"><rect x="' + (at[0] + 8).toFixed(1) + '" y="' + (at[1] - 22).toFixed(1) + '" width="' + w + '" height="18" rx="9"/><text x="' + (at[0] + 14).toFixed(1) + '" y="' + (at[1] - 9).toFixed(1) + '">' + t + '</text></g>';
        }
      });
      h += '<svg x="' + R.left.toFixed(1) + '" y="' + R.top.toFixed(1) + '" width="' + R.width.toFixed(1) + '" height="' + R.height.toFixed(1) + '">' + g + '</svg>';
    });
    svg.innerHTML = h;
    svg.style.display = h ? "block" : "none";
    if (list.length || pend) kick();
  }
  function kick(){ if (!raf && typeof requestAnimationFrame !== "undefined") raf = requestAnimationFrame(function(){ raf = setTimeout(draw, 40); }); }
  /* ---- the bar ---- */
  function say(m){ msg = m || ""; var e = $("ms-msg"); if (e) e.textContent = msg; }
  function render(){
    if (!bar) return;
    Array.prototype.forEach.call(bar.querySelectorAll("[data-ms]"), function(b){ b.setAttribute("aria-pressed", String(b.getAttribute("data-ms") === tool)); });
    var ch = $("ms-res"), h = "";
    list.forEach(function(m){ h += '<span class="ms-r" data-mid="' + m.id + '"><span>' + C.label(m.k, valueOf(m)) + '</span><button type="button" data-del="' + m.id + '" aria-label="Remove this measurement" title="Remove">&times;</button></span>'; });
    if (ch) ch.innerHTML = h;
    var cl = $("ms-clear"); if (cl) cl.disabled = !list.length && !pend;
    if (tb){ tb.setAttribute("aria-pressed", String(!bar.hidden)); tb.textContent = list.length ? "Measure · " + list.length : "Measure"; }
    document.body.classList.toggle("ms-armed", !!tool);
  }
  function arm(k){
    tool = k && C.NEED[k] ? k : null; pend = null;
    if (tool === "pix"){ var T = tissueRef(); if (T && !T.ready() && T.load) T.load().catch(function(){}); }
    say(!tool ? "" : C.ONE[tool] ? C.NAME[tool] + ": tap a structure on the 3-D model" + (tool === "circ" || tool === "area" ? " (section in the cut plane when a cut is on, else perpendicular to the structure's long axis)." : ".")
      : C.NAME[tool] + ": tap point 1 of " + C.NEED[tool] + " on the model or on an image pane.");
    render(); kick();
  }
  function remove(id){ var n = list.length; list = list.filter(function(m){ return m.id !== id; }); if (list.length !== n && window.NMSKHistory && NMSKHistory.active()) NMSKHistory.commit(); render(); kick(); }
  function clear(){ list = []; pend = null; render(); kick(); if (window.NMSKHistory && NMSKHistory.active()) NMSKHistory.commit(); say("Measurements cleared (Undo brings them back)."); }
  function place(){                                     // right under the toolbar (phones: the bottom belongs to the structure card / sheets)
    if (!bar || bar.hidden) return;
    var t = tbEl && tbEl.getBoundingClientRect ? tbEl.getBoundingClientRect() : null;
    if (t && t.height > 0){ bar.style.top = Math.round(Math.min(window.innerHeight * 0.5, t.bottom + 6)) + "px"; bar.style.bottom = "auto"; }   // never over the toolbar
    else { bar.style.top = ""; bar.style.bottom = ""; }
    var c = api && api.canvas && api.canvas.getBoundingClientRect ? api.canvas.getBoundingClientRect() : null;   // desktop: at the 3-D view's left edge, so an image pane beside it stays clear
    if (window.innerWidth > 560 && c && c.width > 200){ bar.style.left = Math.round(Math.max(8, c.left + 8)) + "px"; bar.style.transform = "none"; bar.style.maxWidth = Math.round(Math.max(260, c.width - 16)) + "px"; }
    else { bar.style.left = ""; bar.style.transform = ""; bar.style.maxWidth = ""; }
  }
  function open(v){
    if (!bar) return; bar.hidden = !v; if (!v) arm(null); render(); place();
  }
  function buildBar(){
    bar = document.createElement("div"); bar.id = "ms-bar"; bar.className = "ms-bar"; bar.hidden = true; bar.setAttribute("role", "toolbar"); bar.setAttribute("aria-label", "Measure");
    bar.innerHTML = '<div class="ms-row">' +
      '<button type="button" data-ms="dist" aria-pressed="false" title="Distance between two points (mm)"><b>&#8596;</b> mm</button>' +
      '<button type="button" data-ms="ang3" aria-pressed="false" title="Angle at the middle one of three points"><b>&ang;</b> 3 pts</button>' +
      '<button type="button" data-ms="ang2" aria-pressed="false" title="Angle between two lines (two points each)"><b>&ang;</b> 2 lines</button>' +
      '<button type="button" data-ms="cobb" aria-pressed="false" title="Cobb angle: draw one line along each endplate; the angle between them = between their perpendiculars"><b>&ang;</b> Cobb</button>' +
      '<button type="button" data-ms="circ" aria-pressed="false" title="Circumference of the tapped structure\'s cross-section (its mesh sliced by the cut plane, or perpendicular to its long axis without a cut)"><b>&#9711;</b> mm</button>' +
      '<button type="button" data-ms="area" aria-pressed="false" title="Area enclosed by that cross-section loop (cm²)"><b>&#9711;</b> cm²</button>' +
      '<button type="button" data-ms="surf" aria-pressed="false" title="Surface area of the whole tapped structure (sum of its triangles, cm²)"><b>&#9634;</b> surface</button>' +
      '<button type="button" data-ms="vol" aria-pressed="false" title="Volume of the tapped structure (cm³) -- only when its surface is closed"><b>&#9634;</b> cm³</button>' +
      '<button type="button" data-ms="pix" aria-pressed="false" title="Expected CT number of the tapped structure\'s tissue class -- only a sourced value is shown"><b>CT</b> value</button>' +
      '<button type="button" id="ms-clear" title="Remove every measurement (undoable)">Clear</button>' +
      '<button type="button" id="ms-close" aria-label="Close the measure bar" title="Close">&times;</button></div>' +
      '<p id="ms-msg" class="ms-msg" aria-live="polite"></p><div id="ms-res" class="ms-res"></div>';
    document.body.appendChild(bar);
    Array.prototype.forEach.call(bar.querySelectorAll("[data-ms]"), function(b){ b.addEventListener("click", function(){ var k = b.getAttribute("data-ms"); arm(tool === k ? null : k); }); });
    $("ms-clear").addEventListener("click", clear);
    $("ms-close").addEventListener("click", function(){ open(false); });
    $("ms-res").addEventListener("click", function(e){ var b = e.target.closest ? e.target.closest("[data-del]") : null; if (b) remove(b.getAttribute("data-del")); });
  }
  function start(a, opt){
    api = a; opt = opt || {}; tbEl = opt.toolbar || null;
    buildBar(); window.addEventListener("resize", place);
    if (opt.toolbar){
      tb = document.createElement("button"); tb.type = "button"; tb.id = "t-measure"; tb.className = (opt.cls || "") + " ms-tb"; tb.textContent = "Measure";
      tb.title = "Measure: distance, 3-point angle, angle between two lines, Cobb angle -- on the model and on the image panes; circumference, section area, surface area, volume, expected CT value -- on the model";
      tb.setAttribute("aria-pressed", "false"); tb.addEventListener("click", function(){ open(bar.hidden); });
      opt.toolbar.appendChild(tb);
    }
    surf["3d"] = {id:"3d", el:a.canvas, name:"3-D model", two:false};
    if (window.NMSKHistory) NMSKHistory.register("measure", {
      get:function(){ return list.map(function(m){ var o = {k:m.k, s:m.s, p:m.p}; if (m.r){ o.i = m.i; o.r = m.r; } return o; }); },
      set:function(v){ seq = 0; list = (v || []).map(function(m){ var o = {id:"m" + (++seq), k:m.k, s:m.s, p:m.p.map(function(q){ return q.slice(); })}; if (m.r){ o.i = m.i; o.r = JSON.parse(JSON.stringify(m.r)); } return o; }); pend = null; render(); kick(); },
      reset:function(){ list = []; pend = null; tool = null; if (bar) bar.hidden = true; render(); kick(); }
    });
    render();
    return ctl;
  }
  var ctl = {
    consumeClick:consumeClick, arm:arm, open:open, clear:clear, remove:remove,
    add:function(kind, s, pts, i){ if (C.ONE[kind]) return pts && pts[0] && i != null ? measureOne(kind, i, pts[0], null) : null; if (!C.NEED[kind] || !pts || pts.length !== C.NEED[kind]) return null; tool = kind; pend = null; pts.forEach(function(p){ addPoint(s || "3d", p); }); tool = null; render(); return list[list.length - 1]; },
    surfaces:function(){ return Object.keys(surf).map(function(k){ return {id:k, name:surf[k].name, two:!!surf[k].two}; }); },
    state:function(){ return {tool:tool, open:!!(bar && !bar.hidden), pending:pend ? {s:pend.s, n:pend.p.length} : null, msg:msg,
      list:list.map(function(m){ var r = valueOf(m); return {id:m.id, kind:m.k, surface:m.s, pts:m.p, value:r ? r.v : null, view:r && r.view != null ? r.view : null, unit:r ? r.unit : null, label:C.label(m.k, r), structure:m.i != null ? m.i : null, note:r && r.note ? r.note : null}; })}; },
    redraw:kick
  };
  return {surface:surface, start:start, ctl:ctl, core:C};
})();
