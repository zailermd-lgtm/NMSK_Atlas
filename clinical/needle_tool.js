/*!
 * NMSK Atlas -- clinical needle-planning add-on (Q188).
 *
 * PRIVATE: the owner's clinical layer. NOT CC BY-SA, not part of the anatomy
 * model, not for redistribution -- see clinical/LICENSE_PRIVATE.md. This file
 * holds NO anatomy geometry: it reads the anatomy layer at run time only
 * through the generic API object a viewer page hands to NMSKClinical.attach()
 * (viewer/atlas_viewer.template.html, viewer/zan_atlas.template.html), and is
 * published as a separate file next to each viewer (clinical_needle_tool.js).
 * Without it the viewers run as plain anatomy atlases.
 *
 * Planning / education aid only. Not clinical guidance. Halo margins are a
 * heuristic planning margin, not validated safety distances.
 *
 * Features: 3-D needle (lit shaft, bevelled tip, hub; depth-tested plus a faint
 * see-through pass for the part inside tissue); three targeting modes (entry ->
 * target; entry + direction + length; target first on a cut face / motor
 * point); motor points (clinical_motor_points.json, schema nmsk.motor_points.v1);
 * risk halos and "safer pathways" (clinical_risk.json, schema
 * nmsk.clinical_risk.v1, from scripts/clinical/risk_structures_q188.py).
 */
(function (global) {
"use strict";

/* ===================================================================== */
/* Risk classification table -- the single source of truth. Parsed as JSON */
/* by scripts/clinical/risk_structures_q188.py, so keep it strict JSON.    */
/* Matching: first rule whose `cats` holds the structure's category (the   */
/* viewer's tissue system: vessel/nerve/organ/bone for the specimen        */
/* viewers; vessel/nerve/cns/viscera/lymph/bone layers for Z-Anatomy),     */
/* whose `vt` (Z-Anatomy vein flag) matches if given, and whose regex `re` */
/* matches the lower-cased "name id" text if given. No match: not a risk.  */
/* ===================================================================== */
var RISK_TABLE = /*RISK_TABLE_BEGIN*/{
  "version": 1,
  "classes": {
    "artery": {"label": "Artery (and heart)", "color": "#E5483F", "halo": true},
    "vein":   {"label": "Vein", "color": "#3D7BE8", "halo": true},
    "nerve":  {"label": "Nerve / spinal cord", "color": "#F2C230", "halo": true},
    "lung":   {"label": "Pleura / lung / airway", "color": "#2FC4D3", "halo": true},
    "organ":  {"label": "Other organ (bowel, bladder, kidney, liver, brain ...)", "color": "#A05BD6", "halo": true},
    "bone":   {"label": "Bone (blocks a straight needle)", "color": "#C9BFA6", "halo": false}
  },
  "rules": [
    {"cats": ["lymph", "lymphatic"], "re": "thoracic duct|cisterna chyli", "cls": "vein"},
    {"cats": ["vessel"], "vt": "v", "cls": "vein"},
    {"cats": ["vessel"], "re": "heart|atrium|atrial|ventricle|ventricular|pericard|myocard|endocard|valve|cusp|auricle", "cls": "artery"},
    {"cats": ["vessel"], "re": "\\bveins?\\b|vena|venous|(^|_| )v(_|$| )|jugular|azygos|portal|sinus|plexus", "cls": "vein"},
    {"cats": ["vessel"], "cls": "artery"},
    {"cats": ["nerve"], "cls": "nerve"},
    {"cats": ["cns"], "re": "nerve|spinal|cord|cauda|conus|filum|dura|arachnoid|ganglion|root", "cls": "nerve"},
    {"cats": ["cns"], "cls": "organ"},
    {"cats": ["viscera", "organ"], "re": "lung|pleura|bronch|trachea|lingula", "cls": "lung"},
    {"cats": ["viscera", "organ"], "cls": "organ"},
    {"cats": ["bone"], "cls": "bone"}
  ]
}/*RISK_TABLE_END*/;
var CLASSES = RISK_TABLE.classes;
var RULES = RISK_TABLE.rules.map(function (r) {
  return {cats: r.cats, vt: r.vt || null, re: r.re ? new RegExp(r.re) : null, cls: r.cls};
});
var HALO_CLASSES = Object.keys(CLASSES).filter(function (k) { return CLASSES[k].halo; });

/* Halo radius (heuristic planning margin, mm):
     r = clamp( m_type * ( b0 * clamp((r_cal / r_ref)^p, fMin, fMax) + k * L ), rMin, rMax )
   r_cal: the structure's approximate calibre radius (clinical_risk.json);
   L: trajectory length (entry -> target), or the target's depth below the skin
   before an entry exists. k * L grows the margin with depth because aiming
   error and needle deflection grow with insertion length (k = 0.035 ~ the
   lateral miss of a 2 degree aiming error). Arteries > nerves > organs >
   veins through m_type; large > small through the calibre factor. */
var HALO_DEFAULTS = {b0: 4, rRef: 3, p: 0.5, fMin: 0.5, fMax: 3, k: 0.035, rMin: 2, rMax: 50,
                     mult: {artery: 1.0, nerve: 0.9, lung: 1.0, organ: 0.8, vein: 0.6}};
var TOUCH_MM = 0.75;   // clearance at or below this: the path touches / crosses the structure
var HUB_CLEAR_MM = 30; // free length needed outside the entry for the hub and the hand

function clamp(x, a, b) { return x < a ? a : (x > b ? b : x); }
function classify(rec) {
  var txt = ((rec.name || "") + " " + (rec.id || "")).toLowerCase();
  for (var k = 0; k < RULES.length; k++) {
    var r = RULES[k];
    if (r.cats.indexOf(rec.cat) < 0) continue;
    if (r.vt && rec.vt !== r.vt) continue;
    if (r.re && !r.re.test(txt)) continue;
    return r.cls;
  }
  return null;
}
function calibreFactor(rCal, P) {
  P = P || HALO_DEFAULTS;
  if (!(rCal > 0)) return 1;
  return clamp(Math.pow(rCal / P.rRef, P.p), P.fMin, P.fMax);
}
function haloRadius(cls, rCal, L, P) {
  P = P || HALO_DEFAULTS;
  var m = P.mult[cls];
  if (!m) return 0;
  return clamp(m * (P.b0 * calibreFactor(rCal, P) + P.k * Math.max(0, L || 0)), P.rMin, P.rMax);
}
/* items: [{cls, rCal, clear}] -- per risk structure, the path's clearance to
   its surface (mm). Returns the colour (green: outside every halo; amber:
   inside a halo but clear of the structure; red: touches a risk structure or
   is blocked) and a cost for ranking (lower is better). */
function scorePath(items, L, blocked, P) {
  P = P || HALO_DEFAULTS;
  var colour = blocked ? "red" : "green", cost = 0.004 * L + (blocked ? 1000 : 0), minMargin = Infinity, worst = null;
  for (var k = 0; k < items.length; k++) {
    var it = items[k], h = haloRadius(it.cls, it.rCal, L, P), m = it.clear - h;
    var w = (P.mult[it.cls] || 0) * calibreFactor(it.rCal, P);
    if (it.clear <= TOUCH_MM) colour = "red";
    else if (m < 0 && colour === "green") colour = "amber";
    cost += w * Math.exp(-Math.max(m, 0) / 6) + (m < 0 ? w * (-m) / 2 : 0);
    if (m < minMargin) { minMargin = m; worst = {ref: it.ref, cls: it.cls, clear: it.clear, halo: h, margin: m}; }
  }
  return {colour: colour, cost: cost, minMargin: minMargin, worst: worst};
}
function fibonacciSphere(n) {
  var out = new Float32Array(n * 3), ga = Math.PI * (3 - Math.sqrt(5));
  for (var i = 0; i < n; i++) {
    var y = 1 - 2 * (i + 0.5) / n, r = Math.sqrt(Math.max(0, 1 - y * y)), th = ga * i;
    out[3 * i] = Math.cos(th) * r; out[3 * i + 1] = y; out[3 * i + 2] = Math.sin(th) * r;
  }
  return out;
}

var PURE = {RISK_TABLE: RISK_TABLE, HALO_DEFAULTS: HALO_DEFAULTS, TOUCH_MM: TOUCH_MM, classify: classify,
            calibreFactor: calibreFactor, haloRadius: haloRadius, scorePath: scorePath, fibonacciSphere: fibonacciSphere};
if (typeof module !== "undefined" && module.exports) { module.exports = PURE; return; }

/* ===================================================================== */
/* small vector helpers (plain arrays)                                    */
/* ===================================================================== */
function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
function mul(a, s) { return [a[0] * s, a[1] * s, a[2] * s]; }
function addS(a, b, s) { return [a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s]; }
function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function len(a) { return Math.hypot(a[0], a[1], a[2]); }
function norm(a) { var l = len(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
function perpBasis(u) {
  var a = Math.abs(u[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0];
  var e1 = norm(cross(a, u)), e2 = cross(u, e1);
  return [e1, e2];
}
function segPointDist(A, d, L, px, py, pz) {   // d: unit direction A->B, L: length
  var vx = px - A[0], vy = py - A[1], vz = pz - A[2];
  var t = vx * d[0] + vy * d[1] + vz * d[2];
  t = t < 0 ? 0 : (t > L ? L : t);
  var qx = vx - d[0] * t, qy = vy - d[1] * t, qz = vz - d[2] * t;
  return Math.sqrt(qx * qx + qy * qy + qz * qz);
}
function boxHitsSegment(bmin, bmax, A, B, pad) {     // slab test, AABB padded by `pad`
  var t0 = 0, t1 = 1;
  for (var k = 0; k < 3; k++) {
    var d = B[k] - A[k], lo = bmin[k] - pad, hi = bmax[k] + pad;
    if (Math.abs(d) < 1e-12) { if (A[k] < lo || A[k] > hi) return false; continue; }
    var ta = (lo - A[k]) / d, tb = (hi - A[k]) / d;
    if (ta > tb) { var s = ta; ta = tb; tb = s; }
    if (ta > t0) t0 = ta; if (tb < t1) t1 = tb;
    if (t0 > t1) return false;
  }
  return true;
}
function boxOverlap(amin, amax, bmin, bmax) {
  return !(amax[0] < bmin[0] || amax[1] < bmin[1] || amax[2] < bmin[2] || amin[0] > bmax[0] || amin[1] > bmax[1] || amin[2] > bmax[2]);
}
/* Moller-Trumbore, two-sided; returns t or -1. Geometric normal = (b-a)x(c-a)
   (the same orientation three.js reports as face.normal). */
function rayTri(o, d, ax, ay, az, bx, by, bz, cx, cy, cz) {
  var e1x = bx - ax, e1y = by - ay, e1z = bz - az, e2x = cx - ax, e2y = cy - ay, e2z = cz - az;
  var px = d[1] * e2z - d[2] * e2y, py = d[2] * e2x - d[0] * e2z, pz = d[0] * e2y - d[1] * e2x;
  var det = e1x * px + e1y * py + e1z * pz;
  if (det > -1e-12 && det < 1e-12) return -1;
  var inv = 1 / det, tx = o[0] - ax, ty = o[1] - ay, tz = o[2] - az;
  var u = (tx * px + ty * py + tz * pz) * inv; if (u < 0 || u > 1) return -1;
  var qx = ty * e1z - tz * e1y, qy = tz * e1x - tx * e1z, qz = tx * e1y - ty * e1x;
  var v = (d[0] * qx + d[1] * qy + d[2] * qz) * inv; if (v < 0 || u + v > 1) return -1;
  return (e2x * qx + e2y * qy + e2z * qz) * inv;
}
function triNormalDot(P, I, f, d) {   // dot(normalised face normal, d)
  var a = I[f] * 3, b = I[f + 1] * 3, c = I[f + 2] * 3;
  var n = cross([P[b] - P[a], P[b + 1] - P[a + 1], P[b + 2] - P[a + 2]], [P[c] - P[a], P[c + 1] - P[a + 1], P[c + 2] - P[a + 2]]);
  var l = len(n) || 1;
  return {nd: dot(n, d) / l, n: [n[0] / l, n[1] / l, n[2] / l]};
}

/* ===================================================================== */
/* uniform grids                                                          */
/* ===================================================================== */
/* Points (risk-structure surface samples) bucketed in a regular grid over a
   box; queried by a segment's capsule. */
function PointGrid(pts, owner, bmin, bmax, cell) {
  this.c = cell; this.o = bmin.slice();
  this.n = [0, 1, 2].map(function (k) { return Math.max(1, Math.ceil((bmax[k] - bmin[k]) / cell)); });
  var N = this.n[0] * this.n[1] * this.n[2], cnt = new Int32Array(N + 1), np = pts.length / 3, cellOf = new Int32Array(np);
  for (var i = 0; i < np; i++) { var ci = this.cellIndex(pts[3 * i], pts[3 * i + 1], pts[3 * i + 2]); cellOf[i] = ci; cnt[ci + 1]++; }
  for (var k = 0; k < N; k++) cnt[k + 1] += cnt[k];
  var fill = cnt.slice(0, N), items = new Int32Array(np);
  for (var j = 0; j < np; j++) items[fill[cellOf[j]]++] = j;
  this.start = cnt; this.items = items; this.pts = pts; this.owner = owner;
}
PointGrid.prototype.cellIndex = function (x, y, z) {
  var n = this.n, c = this.c, o = this.o;
  var ix = clamp(Math.floor((x - o[0]) / c), 0, n[0] - 1), iy = clamp(Math.floor((y - o[1]) / c), 0, n[1] - 1), iz = clamp(Math.floor((z - o[2]) / c), 0, n[2] - 1);
  return (ix * n[1] + iy) * n[2] + iz;
};
/* calls cb(pointIndex, distanceToSegment) for every point within R of segment A->B */
PointGrid.prototype.capsule = function (A, B, R, cb) {
  var n = this.n, c = this.c, o = this.o, d = sub(B, A), L = len(d), u = L > 1e-9 ? mul(d, 1 / L) : [1, 0, 0];
  var lo = [], hi = [];
  for (var k = 0; k < 3; k++) {
    lo[k] = clamp(Math.floor((Math.min(A[k], B[k]) - R - o[k]) / c), 0, n[k] - 1);
    hi[k] = clamp(Math.floor((Math.max(A[k], B[k]) + R - o[k]) / c), 0, n[k] - 1);
  }
  var reach = R + c * 0.8661, P = this.pts, S = this.start, I = this.items;
  for (var ix = lo[0]; ix <= hi[0]; ix++) for (var iy = lo[1]; iy <= hi[1]; iy++) for (var iz = lo[2]; iz <= hi[2]; iz++) {
    if (segPointDist(A, u, L, o[0] + (ix + 0.5) * c, o[1] + (iy + 0.5) * c, o[2] + (iz + 0.5) * c) > reach) continue;
    var ci = (ix * n[1] + iy) * n[2] + iz;
    for (var q = S[ci], e = S[ci + 1]; q < e; q++) {
      var p = I[q], dd = segPointDist(A, u, L, P[3 * p], P[3 * p + 1], P[3 * p + 2]);
      if (dd <= R) cb(p, dd);
    }
  }
};

/* Triangles in a regular grid; rays walk it cell by cell (Amanatides-Woo). */
function TriGrid(tris, owner, bmin, bmax, cell) {
  this.c = cell; this.o = bmin.slice(); this.hi = bmax.slice();
  this.n = [0, 1, 2].map(function (k) { return Math.max(1, Math.ceil((bmax[k] - bmin[k]) / cell)); });
  var n = this.n, N = n[0] * n[1] * n[2], nt = tris.length / 9, self = this;
  var cnt = new Int32Array(N + 1), ranges = new Int32Array(nt * 6);
  for (var t = 0; t < nt; t++) {
    var b = 9 * t;
    for (var k = 0; k < 3; k++) {
      var mn = Math.min(tris[b + k], tris[b + 3 + k], tris[b + 6 + k]), mx = Math.max(tris[b + k], tris[b + 3 + k], tris[b + 6 + k]);
      ranges[6 * t + k] = clamp(Math.floor((mn - self.o[k]) / cell), 0, n[k] - 1);
      ranges[6 * t + 3 + k] = clamp(Math.floor((mx - self.o[k]) / cell), 0, n[k] - 1);
    }
    for (var ix = ranges[6 * t]; ix <= ranges[6 * t + 3]; ix++) for (var iy = ranges[6 * t + 1]; iy <= ranges[6 * t + 4]; iy++)
      for (var iz = ranges[6 * t + 2]; iz <= ranges[6 * t + 5]; iz++) cnt[(ix * n[1] + iy) * n[2] + iz + 1]++;
  }
  for (var q = 0; q < N; q++) cnt[q + 1] += cnt[q];
  var fill = cnt.slice(0, N), items = new Int32Array(cnt[N]);
  for (var t2 = 0; t2 < nt; t2++) {
    for (var jx = ranges[6 * t2]; jx <= ranges[6 * t2 + 3]; jx++) for (var jy = ranges[6 * t2 + 1]; jy <= ranges[6 * t2 + 4]; jy++)
      for (var jz = ranges[6 * t2 + 2]; jz <= ranges[6 * t2 + 5]; jz++) items[fill[(jx * n[1] + jy) * n[2] + jz]++] = t2;
  }
  this.start = cnt; this.items = items; this.tris = tris; this.owner = owner;
  this.stamp = new Int32Array(nt); this.st = 0; this.ntris = nt;
}
/* all hits of the ray o + t d (d unit) with t in [t0, t1], sorted by t */
TriGrid.prototype.ray = function (o, d, t0, t1) {
  var out = [], n = this.n, c = this.c, O = this.o, T = this.tris, S = this.start, I = this.items;
  var tin = t0, tout = t1;
  for (var k = 0; k < 3; k++) {       // clip to the grid box
    var lo = O[k], hi = O[k] + n[k] * c;
    if (Math.abs(d[k]) < 1e-12) { if (o[k] < lo || o[k] > hi) return out; continue; }
    var ta = (lo - o[k]) / d[k], tb = (hi - o[k]) / d[k];
    if (ta > tb) { var s = ta; ta = tb; tb = s; }
    if (ta > tin) tin = ta; if (tb < tout) tout = tb;
  }
  if (tin > tout) return out;
  this.st++; var st = this.st, stamp = this.stamp;
  var p = addS(o, d, tin + 1e-6), idx = [], step = [], tMax = [], tDel = [];
  for (var a = 0; a < 3; a++) {
    idx[a] = clamp(Math.floor((p[a] - O[a]) / c), 0, n[a] - 1);
    step[a] = d[a] > 0 ? 1 : (d[a] < 0 ? -1 : 0);
    var bound = O[a] + (idx[a] + (step[a] > 0 ? 1 : 0)) * c;
    tMax[a] = step[a] !== 0 ? tin + (bound - p[a]) / d[a] : Infinity;
    tDel[a] = step[a] !== 0 ? c / Math.abs(d[a]) : Infinity;
  }
  for (var guard = 0; guard < 100000; guard++) {
    var ci = (idx[0] * n[1] + idx[1]) * n[2] + idx[2];
    for (var q = S[ci], e = S[ci + 1]; q < e; q++) {
      var t = I[q]; if (stamp[t] === st) continue; stamp[t] = st;
      var b = 9 * t, h = rayTri(o, d, T[b], T[b + 1], T[b + 2], T[b + 3], T[b + 4], T[b + 5], T[b + 6], T[b + 7], T[b + 8]);
      if (h >= t0 && h <= t1) out.push({t: h, tri: t});
    }
    var m = tMax[0] < tMax[1] ? (tMax[0] < tMax[2] ? 0 : 2) : (tMax[1] < tMax[2] ? 1 : 2);
    if (tMax[m] > tout) break;
    idx[m] += step[m]; if (idx[m] < 0 || idx[m] >= n[m]) break;
    tMax[m] += tDel[m];
  }
  out.sort(function (x, y) { return x.t - y.t; });
  return out;
};

/* ===================================================================== */
/* procedural overlay geometry (atlas mm, built fresh for every change)    */
/* ===================================================================== */
function Geo() { this.pos = []; this.nrm = []; this.idx = []; }
Geo.prototype.v = function (p, n) { this.pos.push(p[0], p[1], p[2]); this.nrm.push(n[0], n[1], n[2]); return this.pos.length / 3 - 1; };
Geo.prototype.count = function () { return this.pos.length / 3; };
/* Tube A->B, radii r0 (at A) / r1 (at B). opts.bevel: length of an oblique
   bevel cut at B (needle point); opts.capA / opts.capB: flat (or bevel) caps. */
function addTube(g, A, B, r0, r1, seg, opts) {
  opts = opts || {};
  var d = sub(B, A), L = len(d); if (L < 1e-6) return g;
  var u = mul(d, 1 / L), E = perpBasis(u), e1 = E[0], e2 = E[1], bev = Math.min(opts.bevel || 0, L * 0.9);
  var a0 = [], b0 = [], rimA = [], rimB = [];
  for (var k = 0; k < seg; k++) {
    var ph = 2 * Math.PI * k / seg, cs = Math.cos(ph), sn = Math.sin(ph), rad = add(mul(e1, cs), mul(e2, sn));
    var pa = addS(A, rad, r0), pb = addS(addS(B, rad, r1), u, -bev * (1 - cs) / 2);
    a0.push(g.v(pa, rad)); b0.push(g.v(pb, rad)); rimA.push(pa); rimB.push(pb);
  }
  for (var j = 0; j < seg; j++) {
    var j2 = (j + 1) % seg;
    g.idx.push(a0[j], a0[j2], b0[j2], a0[j], b0[j2], b0[j]);
  }
  function cap(rim, nrm) {
    var c = [0, 0, 0]; rim.forEach(function (p) { c = add(c, p); }); c = mul(c, 1 / rim.length);
    var ci = g.v(c, nrm), ids = rim.map(function (p) { return g.v(p, nrm); });
    for (var q = 0; q < ids.length; q++) g.idx.push(ci, ids[q], ids[(q + 1) % ids.length]);
  }
  if (opts.capA) cap(rimA, mul(u, -1));
  if (opts.capB) cap(rimB, bev > 0 ? norm(cross(add(mul(e1, r1), mul(u, bev / 2)), mul(e2, r1))) : u);
  return g;
}
function addSphere(g, c, r, su, sv) {
  su = su || 12; sv = sv || 8;
  var base = g.count();
  for (var i = 0; i <= sv; i++) {
    var th = Math.PI * i / sv, st = Math.sin(th), ct = Math.cos(th);
    for (var j = 0; j <= su; j++) {
      var ph = 2 * Math.PI * j / su, n = [st * Math.cos(ph), ct, st * Math.sin(ph)];
      g.v(addS(c, n, r), n);
    }
  }
  for (var a = 0; a < sv; a++) for (var b = 0; b < su; b++) {
    var p0 = base + a * (su + 1) + b, p1 = p0 + su + 1;
    g.idx.push(p0, p1, p0 + 1, p0 + 1, p1, p1 + 1);
  }
  return g;
}
/* split a long list of small parts into Geo chunks of < 65k vertices */
function chunked(parts, build) {
  var out = [], g = new Geo();
  parts.forEach(function (p) { if (g.count() > 60000) { out.push(g); g = new Geo(); } build(g, p); });
  if (g.count()) out.push(g);
  return out;
}
function hexRgb(h) { h = h.replace("#", ""); return [parseInt(h.slice(0, 2), 16) / 255, parseInt(h.slice(2, 4), 16) / 255, parseInt(h.slice(4, 6), 16) / 255]; }

/* ===================================================================== */
/* overlay back-ends: three.js scene objects, or raw WebGL drawn after the */
/* host's own frame (same depth buffer, so depth tests are against tissue) */
/* spec: {color, alpha, pass:"opaque"|"trans"|"xray", lit, shin, emis}     */
/* "xray" = no depth test, drawn last: the faint see-through pass.         */
/* Halos re-draw a host structure inflated along its vertex normals.       */
/* ===================================================================== */
function ThreeOverlay(api) {
  var T = api.three.THREE, root = api.three.root, items = {}, halos = {};
  function mkGeom(g) {
    var bg = new T.BufferGeometry();
    bg.setAttribute("position", new T.Float32BufferAttribute(g.pos, 3));
    bg.setAttribute("normal", new T.Float32BufferAttribute(g.nrm, 3));
    bg.setIndex(g.count() > 65535 ? new T.Uint32BufferAttribute(g.idx, 1) : new T.Uint16BufferAttribute(g.idx, 1));
    bg.computeBoundingSphere();
    return bg;
  }
  function mkMat(s) {
    var col = new T.Color(s.color), m;
    if (s.lit === false) m = new T.MeshBasicMaterial({color: col});
    else m = new T.MeshPhongMaterial({color: col, shininess: s.shin || 40, specular: new T.Color(s.spec || 0x555555),
                                      emissive: col.clone().multiplyScalar(s.emis || 0)});
    m.side = T.DoubleSide;
    m.opacity = s.alpha == null ? 1 : s.alpha;
    m.transparent = s.pass !== "opaque" || m.opacity < 1;
    m.depthTest = s.pass !== "xray"; m.depthWrite = s.pass === "opaque";
    return m;
  }
  this.set = function (name, geos, spec) {
    this.remove(name);
    items[name] = [].concat(geos).filter(function (g) { return g && g.count(); }).map(function (g) {
      var mesh = new T.Mesh(mkGeom(g), mkMat(spec));
      mesh.renderOrder = spec.pass === "xray" ? 1000 + (spec.order || 0) : (spec.pass === "trans" ? 900 + (spec.order || 0) : 0);
      mesh.frustumCulled = false; mesh.userData.overlay = true;
      root.add(mesh); return mesh;
    });
  };
  this.remove = function (name) {
    (items[name] || []).forEach(function (m) { root.remove(m); m.geometry.dispose(); m.material.dispose(); });
    delete items[name];
  };
  this.setHalos = function (list) {
    var keep = {}, planes = api.three.clippingPlanes();
    list.forEach(function (h) {
      keep[h.i] = 1;
      var e = halos[h.i];
      if (!e) {
        var u = {value: 0}, mat = new T.MeshPhongMaterial({transparent: true, depthWrite: false, side: T.DoubleSide, shininess: 8});
        mat.onBeforeCompile = function (sh) {
          sh.uniforms.uInflate = u;
          sh.vertexShader = "uniform float uInflate;\n" + sh.vertexShader.replace("#include <begin_vertex>",
            "#include <begin_vertex>\n  transformed += normalize(objectNormal) * uInflate;");
        };
        mat.customProgramCacheKey = function () { return "nmsk-clinical-halo"; };
        var mesh = new T.Mesh(api.three.mesh(h.i).geometry, mat);
        mesh.renderOrder = 800; mesh.userData.overlay = true;
        root.add(mesh); e = halos[h.i] = {mesh: mesh, u: u};
      }
      e.u.value = h.r;
      e.mesh.material.color.set(h.color); e.mesh.material.emissive.set(h.color).multiplyScalar(0.45);
      e.mesh.material.opacity = h.alpha || 0.2;
      e.mesh.material.clippingPlanes = planes;
    });
    Object.keys(halos).forEach(function (k) {
      if (!keep[k]) { root.remove(halos[k].mesh); halos[k].mesh.material.dispose(); delete halos[k]; }
    });
  };
}

function GLOverlay(api) {
  var gl = api.webgl.gl, items = {}, halos = [], U = {};
  var VS = "attribute vec3 aPos;attribute vec3 aNrm;uniform mat4 uMVP;uniform float uInflate;varying vec3 vN;varying vec3 vP;" +
           "void main(){vec3 p=aPos+normalize(aNrm)*uInflate;vN=aNrm;vP=p;gl_Position=uMVP*vec4(p,1.0);}";
  var FS = "#ifdef GL_FRAGMENT_PRECISION_HIGH\nprecision highp float;\n#else\nprecision mediump float;\n#endif\n" +
    "varying vec3 vN;varying vec3 vP;uniform vec3 uColor;uniform vec3 uEye;uniform float uAlpha;uniform float uLit;" +
    "uniform float uShin;uniform float uEmis;uniform vec4 uClip;uniform float uClipOn;" +
    "void main(){if(uClipOn>0.5&&dot(vP,uClip.xyz)+uClip.w>0.0)discard;" +
    " vec3 n=normalize(vN);vec3 v=normalize(uEye-vP);if(dot(n,v)<0.0)n=-n;" +
    " vec3 l=normalize(v+vec3(0.3,0.55,0.2));float d=max(dot(n,l),0.0);" +
    " float s=pow(max(dot(n,normalize(l+v)),0.0),uShin);" +
    " vec3 c=uLit>0.5?uColor*(0.30+0.72*d+uEmis)+vec3(s*0.6):uColor;" +
    " gl_FragColor=vec4(c,uAlpha);}";
  function sh(t, s) { var o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o);
    if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; }
  var prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
  gl.bindAttribLocation(prog, 0, "aPos"); gl.bindAttribLocation(prog, 1, "aNrm"); gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
  ["uMVP", "uInflate", "uColor", "uEye", "uAlpha", "uLit", "uShin", "uEmis", "uClip", "uClipOn"].forEach(function (n) { U[n] = gl.getUniformLocation(prog, n); });
  function upload(g) {
    function buf(type, data) { var b = gl.createBuffer(); gl.bindBuffer(type, b); gl.bufferData(type, data, gl.STATIC_DRAW); return b; }
    return {vb: buf(gl.ARRAY_BUFFER, new Float32Array(g.pos)), nb: buf(gl.ARRAY_BUFFER, new Float32Array(g.nrm)),
            ib: buf(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(g.idx)), count: g.idx.length};
  }
  this.set = function (name, geos, spec) {
    this.remove(name);
    items[name] = [].concat(geos).filter(function (g) { return g && g.count(); }).map(function (g) {
      var b = upload(g); b.spec = spec; b.rgb = hexRgb(spec.color); return b;
    });
  };
  this.remove = function (name) {
    (items[name] || []).forEach(function (b) { gl.deleteBuffer(b.vb); gl.deleteBuffer(b.nb); gl.deleteBuffer(b.ib); });
    delete items[name];
  };
  this.setHalos = function (list) { halos = list.map(function (h) { return {i: h.i, r: h.r, rgb: hexRgb(h.color), alpha: h.alpha || 0.2}; }); };
  function style(rgb, s) {
    gl.uniform3f(U.uColor, rgb[0], rgb[1], rgb[2]); gl.uniform1f(U.uAlpha, s.alpha == null ? 1 : s.alpha);
    gl.uniform1f(U.uLit, s.lit === false ? 0 : 1); gl.uniform1f(U.uShin, s.shin || 40); gl.uniform1f(U.uEmis, s.emis || 0);
  }
  function drawItem(b) {
    style(b.rgb, b.spec);
    gl.bindBuffer(gl.ARRAY_BUFFER, b.vb); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, b.nb); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, b.ib); gl.drawElements(gl.TRIANGLES, b.count, gl.UNSIGNED_SHORT, 0);
  }
  api.webgl.onAfterDraw(function (ctx) {
    var all = [];
    Object.keys(items).forEach(function (k) { all = all.concat(items[k]); });
    if (!all.length && !halos.length) return;
    gl.useProgram(prog);
    gl.uniformMatrix4fv(U.uMVP, false, ctx.mvp); gl.uniform3f(U.uEye, ctx.eye[0], ctx.eye[1], ctx.eye[2]);
    gl.uniform1f(U.uInflate, 0); gl.uniform1f(U.uClipOn, 0);
    gl.enableVertexAttribArray(0); gl.enableVertexAttribArray(1); gl.disable(gl.CULL_FACE);
    gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
    all.filter(function (b) { return b.spec.pass === "opaque"; }).forEach(drawItem);
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false);
    if (halos.length) {
      if (ctx.clip) { gl.uniform4f(U.uClip, ctx.clip[0], ctx.clip[1], ctx.clip[2], ctx.clip[3]); gl.uniform1f(U.uClipOn, 1); }
      halos.forEach(function (h) {
        style(h.rgb, {alpha: h.alpha, shin: 8, emis: 0.45}); gl.uniform1f(U.uInflate, h.r);
        api.webgl.drawStructure(h.i);
      });
      gl.uniform1f(U.uInflate, 0); gl.uniform1f(U.uClipOn, 0);
    }
    all.filter(function (b) { return b.spec.pass === "trans"; }).forEach(drawItem);
    gl.disable(gl.DEPTH_TEST);
    all.filter(function (b) { return b.spec.pass === "xray"; }).forEach(drawItem);
    gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
  });
}

/* ===================================================================== */
/* panel styles (scoped .ncl-*, host colour tokens with fallbacks)          */
/* ===================================================================== */
var CSS = [
".ncl{--ncl-acc:var(--accent,#1d7c99);--ncl-line:var(--line,rgba(22,32,42,.16));--ncl-mut:var(--muted,var(--ink-dim,#5c6a77));",
"  --ncl-bg:var(--panel,#fff);--ncl-sunk:var(--sunk,var(--panel-2,#eef2f5));font-size:12px;line-height:1.45;color:var(--ink,#16202a)}",
".ncl{padding:11px 13px;background:var(--ncl-bg);border-bottom:1px solid var(--ncl-line)}",
".ncl.ncl-float{position:fixed;top:calc(3.3rem + env(safe-area-inset-top,0px));right:.9rem;width:340px;max-height:calc(100vh - 8rem);",
"  overflow-y:auto;z-index:26;border:1px solid var(--ncl-line);border-radius:12px;box-shadow:0 10px 34px rgba(22,32,42,.18)}",
"@media (max-width:900px){.ncl.ncl-float{left:.6rem;right:.6rem;width:auto;top:auto;bottom:calc(3.9rem + env(safe-area-inset-bottom,0px));max-height:52vh}}",
".ncl.ncl-stage{position:absolute;left:12px;top:12px;width:330px;max-height:calc(100% - 150px);overflow-y:auto;z-index:5;",
"  border:1px solid var(--ncl-line);border-radius:10px;box-shadow:0 8px 26px rgba(15,21,26,.16)}",
"@media (max-width:760px){.ncl.ncl-stage{left:8px;right:8px;width:auto;top:auto;bottom:8px;max-height:46%}}",
".ncl h3{margin:0;font-size:13px;font-weight:700}",
".ncl-head{display:flex;align-items:center;gap:6px;margin-bottom:6px}.ncl-head h3{flex:1}",
".ncl button{font:inherit;color:inherit;cursor:pointer;border:1px solid var(--ncl-line);background:var(--ncl-sunk);border-radius:5px;padding:2px 8px;font-size:11px}",
".ncl button:hover{border-color:var(--ncl-acc)}",
".ncl button[aria-pressed=true]{background:var(--ncl-acc);color:#fff;border-color:var(--ncl-acc)}",
".ncl-disc{margin:0 0 8px;padding:6px 8px;border-radius:6px;background:#FFF4DC;color:#6B4A00;font-size:11px;border:1px solid #F0D48A}",
"@media (prefers-color-scheme:dark){.ncl-disc{background:#2E2410;color:#F3D58B;border-color:#5A4718}}",
".ncl-modes{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:6px}",
".ncl-status{margin:0 0 6px;color:var(--ncl-mut);font-size:11.5px}",
".ncl-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:4px 0}",
".ncl-row input[type=range]{flex:1;min-width:90px}",
".ncl input[type=number]{width:58px;font:inherit;font-size:11px;padding:1px 3px;border:1px solid var(--ncl-line);border-radius:4px;background:var(--surface,#fff);color:inherit}",
".ncl input[type=search]{width:100%;font:inherit;padding:4px 6px;border:1px solid var(--ncl-line);border-radius:5px;background:var(--surface,#fff);color:inherit}",
".ncl dl{display:grid;grid-template-columns:82px minmax(0,1fr);gap:2px 8px;margin:6px 0}",
".ncl dt{color:var(--ncl-mut)}.ncl dd{margin:0;overflow-wrap:anywhere}",
".ncl ol{margin:4px 0 0;padding-left:18px}.ncl ol li{margin:2px 0}",
".ncl .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle}",
".ncl .rng{color:var(--ncl-mut);margin-left:4px;white-space:nowrap}",
".ncl .mono{font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}",
".ncl .cite{font-size:10.5px;color:var(--ncl-mut);margin:6px 0 0}",
".ncl details{margin-top:8px;border-top:1px solid var(--ncl-line);padding-top:6px}",
".ncl summary{cursor:pointer;font-weight:700;font-size:12px}",
".ncl .lg{display:flex;flex-wrap:wrap;gap:4px 10px;margin:4px 0;font-size:11px}",
".ncl .formula{font-family:'JetBrains Mono',monospace;font-size:10.5px;background:var(--ncl-sunk);padding:5px 6px;border-radius:5px;overflow-wrap:anywhere}",
".ncl .grid2{display:grid;grid-template-columns:repeat(3,auto);gap:3px 8px;align-items:center;font-size:11px}",
".ncl .res{max-height:170px;overflow-y:auto;margin-top:4px}",
".ncl .res button{display:block;width:100%;text-align:left;margin:2px 0;padding:4px 6px}",
".ncl .warn{color:var(--risk,#B3400C);font-size:11px;margin:4px 0}",
".ncl .pill-g{color:#1E8A4F;font-weight:700}.ncl .pill-a{color:#B07300;font-weight:700}.ncl .pill-r{color:#C23232;font-weight:700}",
".ncl-tip{position:fixed;z-index:80;pointer-events:none;max-width:280px;padding:5px 8px;border-radius:6px;font-size:11.5px;",
"  background:var(--surface,var(--panel,#fff));color:var(--ink,#16202a);border:1px solid var(--line,#ccd);box-shadow:0 6px 18px rgba(0,0,0,.18)}"
].join("\n");

function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
function f1(v) { return '<span class="mono">' + Number(v).toFixed(1) + "</span>"; }
function xyz1(v) { return '<span class="mono">' + v.map(function (c) { return c.toFixed(1); }).join(", ") + "</span> mm"; }
var EPS = 0.5, MINIV = 0.05, SPACING = 2.5;
var COLOUR = {green: "#2FA866", amber: "#F0A830", red: "#D64545"};
var STEEL = {color: "#C9CED6", pass: "opaque", shin: 90, spec: 0x888888, emis: 0.05};
var MP_COLOUR = "#FF4FD8";

/* ===================================================================== */
/* the tool                                                               */
/* ===================================================================== */
function Tool(api) {
  var self = this;
  this.api = api;
  this.recs = api.list();
  this.byId = {};
  this.recs.forEach(function (r) { (self.byId[r.id] = self.byId[r.id] || []).push(r.i); });
  this.cls = this.recs.map(classify);
  this.skin = this.recs.filter(function (r) { return /^skin(_|$)/.test(r.id); }).map(function (r) { return r.i; });
  this.ov = api.kind === "three" ? new ThreeOverlay(api) : new GLOverlay(api);
  this.P = JSON.parse(JSON.stringify(HALO_DEFAULTS));
  this.active = false; this.mode = "two"; this.entry = null; this.target = null;
  this.dir = {src: "normal", tilt: 0, az: 0, view: null};
  this.len = 60; this.rDisp = 1.0;
  this.risk = {data: null, rcal: {}, on: false, transp: 0.8, saved: null, region: null, safer: null, pathEval: null};
  this.mp = {data: null, points: [], on: false, msg: "loading...", sel: null};
  this.gcache = new Map(); this.gverts = 0; this.orient = {};
  this.buildUI();
  this.loadData();
  api.setClickHandler(function (e) { return self.onClick(e); });
  api.onChange(function () { self.onHostChange(); });
  api.canvas.addEventListener("pointermove", function (e) { if (!e.buttons) self.onHover(e); });
  api.canvas.addEventListener("pointerleave", function () { self.tip.hidden = true; });
  window.addEventListener("keydown", function (e) {
    var t = e.target; if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
    if (e.key === "Escape" && self.active) self.clear();
  });
}
var TP = Tool.prototype;

/* ---------- geometry access ---------- */
TP.geom = function (i) {
  var g = this.gcache.get(i);
  if (!g) {
    g = this.api.geometry(i); if (!g) return null;
    if (this.api.kind !== "three") {
      this.gverts += g.pos.length / 3;
      if (this.gverts > 6e6) { this.gcache.clear(); this.gverts = g.pos.length / 3; }
    }
    this.gcache.set(i, g);
  }
  return g;
};
/* +1 when the mesh's winding makes its vertex normals point outward (positive
   signed volume), -1 otherwise -- the sign a halo inflates with. */
TP.orientSign = function (i) {
  if (this.orient[i] != null) return this.orient[i];
  var g = this.geom(i), P = g.pos, I = g.idx, v = 0;
  for (var f = 0; f < I.length; f += 3) {
    var a = I[f] * 3, b = I[f + 1] * 3, c = I[f + 2] * 3;
    v += P[a] * (P[b + 1] * P[c + 2] - P[b + 2] * P[c + 1]) - P[a + 1] * (P[b] * P[c + 2] - P[b + 2] * P[c]) + P[a + 2] * (P[b] * P[c + 1] - P[b + 1] * P[c]);
  }
  return (this.orient[i] = v < 0 ? -1 : 1);
};
/* every hit of the ray with mesh i, t in [near, far]: [{t, nd, n}] (nd: face normal . nd_dir) */
TP.rayAll = function (i, o, d, near, far, ndDir) {
  var g = this.geom(i), out = []; if (!g) return out;
  var P = g.pos, I = g.idx, ndd = ndDir || d;
  for (var f = 0; f < I.length; f += 3) {
    var a = I[f] * 3, b = I[f + 1] * 3, c = I[f + 2] * 3;
    var t = rayTri(o, d, P[a], P[a + 1], P[a + 2], P[b], P[b + 1], P[b + 2], P[c], P[c + 1], P[c + 2]);
    if (t >= near && t <= far) { var nn = triNormalDot(P, I, f, ndd); out.push({t: t, nd: nn.nd, n: nn.n}); }
  }
  return out;
};
TP.rayNearest = function (i, o, d, cut) {
  var best = null;
  this.rayAll(i, o, d, 1e-6, 1e9).forEach(function (h) {
    if (best && h.t >= best.t) return;
    var p = addS(o, d, h.t);
    if (cut && dot(cut, p) + cut[3] < -1e-6) return;
    best = {t: h.t, p: p, n: h.n};
  });
  return best;
};
TP.insideMesh = function (i, p) {   // parity of crossings along a fixed skew direction
  return this.rayAll(i, p, [0.57735, 0.57736, 0.57734], 1e-5, 1e9).length % 2 === 1;
};
/* the smallest visible structure containing p; the skin (a closed body shell
   here) only as a fallback, returned as -1: "inside the body, between the
   modelled structures" */
TP.containing = function (p, skip) {
  var self = this, best = null, bv = Infinity;
  this.recs.forEach(function (r) {
    if (r.i === skip || !self.api.visible(r.i) || self.skin.indexOf(r.i) >= 0) return;
    if (p[0] < r.bmin[0] || p[1] < r.bmin[1] || p[2] < r.bmin[2] || p[0] > r.bmax[0] || p[1] > r.bmax[1] || p[2] > r.bmax[2]) return;
    var vol = (r.bmax[0] - r.bmin[0]) * (r.bmax[1] - r.bmin[1]) * (r.bmax[2] - r.bmin[2]);
    if (vol >= bv) return;
    if (self.insideMesh(r.i, p)) { best = r.i; bv = vol; }
  });
  if (best == null && this.skin.some(function (i) { return i !== skip && self.insideMesh(i, p); })) return -1;
  return best;
};
/* The point under the pointer: the nearest visible surface (never in the half
   the cut plane removed), or -- when the ray meets the cut plane first and that
   point lies inside a structure -- the point ON the cut face, so a deep target
   can be picked where the cut exposes it. */
TP.pickPoint = function (e, skip) {
  var api = this.api, R = api.ray(e), cut = api.cut(), h = api.pick(e, skip != null ? {skip: skip} : null), res = null;
  if (h && h.i >= 0) {
    var hit = this.rayNearest(h.i, R.o, R.d, cut);
    if (hit) res = {i: h.i, p: hit.p, n: hit.n, t: hit.t};
    else if (h.point) res = {i: h.i, p: h.point, n: null, t: dist(R.o, h.point)};
  }
  if (cut) {
    var cn = [cut[0], cut[1], cut[2]], den = dot(cn, R.d);
    if (Math.abs(den) > 1e-6) {
      var tp = -(dot(cn, R.o) + cut[3]) / den;
      if (tp > 0 && (!res || tp < res.t - 0.05)) {
        var P = addS(R.o, R.d, tp), inside = this.containing(P, skip);
        if (inside != null) res = {i: inside >= 0 ? inside : null, p: P, n: cn, t: tp, onCut: true};
      }
    }
  }
  if (res && res.n && dot(res.n, R.d) < 0) res.n = mul(res.n, -1);   // inward: along the viewing ray
  if (res) res.ray = R.d;
  return res;
};
TP.name = function (i) { return i == null ? "(no modelled structure)" : this.recs[i].name; };

/* ---------- needle path report (ported from the template's Q58 tool) ---------- */
TP.needleHits = function (A, B, list) {
  var d = sub(B, A), L = len(d); if (L < 1e-6) return {hits: [], L: 0};
  d = mul(d, 1 / L);
  var self = this, evs = [], cands = list.filter(function (i) { var r = self.recs[i]; return boxHitsSegment(r.bmin, r.bmax, A, B, EPS + 0.05); });
  function cast(origin, dir, sign, base) {
    cands.forEach(function (i) {
      self.rayAll(i, origin, dir, 0, L + 2 * EPS, d).forEach(function (h) {
        evs.push({i: i, t: base + sign * h.t, enter: h.nd < 0, flat: Math.abs(h.nd) < 1e-6});
      });
    });
  }
  cast(addS(A, d, -EPS), d, 1, -EPS);
  cast(addS(B, d, EPS), mul(d, -1), -1, L + EPS);
  evs.sort(function (a, b) { return a.t - b.t; });
  var out = [];
  evs.forEach(function (e) {
    var last = out.length ? out[out.length - 1] : null;
    if (last && last.i === e.i && Math.abs(last.t - e.t) < 0.02 && last.enter === e.enter) return;
    out.push(e);
  });
  return {hits: out, L: L};
};
TP.crossings = function (A, B, list, targetI) {
  var r = this.needleHits(A, B, list), L = r.L, per = new Map(), self = this;
  r.hits.forEach(function (e) {
    var s = per.get(e.i);
    if (!s) { s = {i: e.i, inside: false, start: 0, ivs: []}; per.set(e.i, s); }
    var enter = e.flat ? !s.inside : e.enter;
    if (enter) { if (!s.inside) { s.inside = true; s.start = Math.max(0, e.t); } }
    else {
      var t = Math.min(L, e.t);
      if (s.inside) { s.ivs.push([s.start, t]); s.inside = false; }
      else if (t > 0) s.ivs.push([0, t]);
    }
  });
  var rows = [];
  per.forEach(function (s) {
    if (s.inside) s.ivs.push([s.start, L]);
    var ivs = s.ivs.filter(function (iv) { return iv[1] - iv[0] >= MINIV; });
    if (!ivs.length && s.i === targetI) ivs = [[L, L]];
    ivs.forEach(function (iv) { rows.push({i: s.i, id: self.recs[s.i].id, name: self.name(s.i), from: iv[0], to: iv[1]}); });
  });
  rows.sort(function (a, b) { return a.from - b.from || a.to - b.to; });
  return rows;
};
TP.skinDepth = function (A, B) {
  var L = dist(A, B), self = this;
  if (this.skin.length) {
    if (this.entry && this.entry.i != null && this.skin.indexOf(this.entry.i) >= 0) return {depth: L, how: "entry on the skin"};
    var r = this.needleHits(A, B, this.skin), best = null;
    r.hits.forEach(function (e) {
      if (e.t < -MINIV || e.t > L + MINIV) return;
      var dd = L - Math.max(0, Math.min(L, e.t)); if (best == null || dd < best) best = dd;
    });
    return best == null ? {depth: null, how: "no skin crossed"} : {depth: best, how: "nearest skin hit on the path"};
  }
  var all = this.recs.map(function (rr) { return rr.i; }), h = this.needleHits(A, B, all).hits.filter(function (e) { return e.t >= -MINIV && e.t <= L; });
  if (!h.length) return {depth: null, how: "no model surface crossed"};
  return {depth: L - Math.max(0, h[0].t), how: "below the outermost model surface on the path (this model has no skin or subcutaneous fat; real depth is greater)"};
};
TP.report = function () {
  if (!this.entry || !this.target) return null;
  var self = this, A = this.entry.p, B = this.target.p;
  var vis = this.recs.filter(function (r) { return self.api.visible(r.i); }).map(function (r) { return r.i; });
  var rows = this.crossings(A, B, vis, this.target.i), L = dist(A, B);
  var tipIn = rows.filter(function (c) { return c.to >= L - 0.05 && (c.to - c.from >= MINIV || c.i === self.target.i); });
  return {
    mode: this.mode, length_mm: L, entry: A.slice(), target: B.slice(),
    entry_id: this.entry.i != null ? this.recs[this.entry.i].id : null,
    target_id: this.target.i != null ? this.recs[this.target.i].id : null,
    target_name: this.target.i != null ? this.name(this.target.i) : null,
    crossings: rows.map(function (r) { return {id: r.id, name: r.name, from_mm: r.from, to_mm: r.to}; }),
    tip_in: tipIn.map(function (r) { return r.name; }),
    skin: this.skinDepth(A, B),
    needle_mm: this.len, exposed_mm: Math.max(0, this.len - L),
    motor_point: this.target.mp ? this.target.mp.id : null,
    risk: this.risk.pathEval || null
  };
};

/* ---------- UI ---------- */
TP.buildUI = function () {
  var self = this, api = this.api, three = api.kind === "three";
  if (!document.getElementById("ncl-css")) {
    var st = document.createElement("style"); st.id = "ncl-css"; st.textContent = CSS; document.head.appendChild(st);
  }
  var btn = document.createElement("button");
  btn.id = "t-needle"; btn.type = "button"; btn.className = three ? "tool" : "pill";
  btn.setAttribute("aria-pressed", "false"); btn.textContent = three ? "Needle" : "needle";
  btn.title = "Needle planning (private add-on): entry/target, direction + length, motor points, risk halos, safer pathways";
  btn.addEventListener("click", function () { self.toggle(); });
  api.toolbar.insertBefore(btn, api.toolbar.lastElementChild);
  this.btn = btn;
  var el = document.createElement("div");
  el.className = "ncl " + (api.panelHost ? "ncl-stage" : "ncl-float"); el.id = "needle-panel"; el.hidden = true;
  var legend = HALO_CLASSES.map(function (k) { return '<span><span class="dot" style="background:' + CLASSES[k].color + '"></span>' + esc(CLASSES[k].label) + "</span>"; }).join("");
  var mults = HALO_CLASSES.map(function (k) {
    return "<span>" + esc(CLASSES[k].label.split(" (")[0].split(" /")[0]) + '</span><input type="number" step="0.05" min="0" max="3" data-mult="' + k + '" value="' + self.P.mult[k] + '"><span></span>';
  }).join("");
  el.innerHTML =
    '<div class="ncl-head"><h3>Needle planning</h3><button type="button" id="needle-clear">Clear</button>' +
    '<button type="button" id="ncl-close" title="Close the needle tool">&times;</button></div>' +
    '<p class="ncl-disc"><b>Planning / education aid only &mdash; not clinical guidance.</b> Model anatomy (decimated viewing meshes, one body), ' +
    'not the patient. Risk halos are a heuristic planning margin, not validated safety distances.</p>' +
    '<div class="ncl-modes" id="ncl-modes">' +
    '<button type="button" data-mode="two" title="Click the entry point, then the target">Entry &rarr; target</button>' +
    '<button type="button" data-mode="dir" title="Click the entry; the tip lies along a direction at the needle length">Entry + direction + length</button>' +
    '<button type="button" data-mode="tfirst" title="Pick the deep target first (on a cut face or a motor point), then the entry">Target first</button></div>' +
    '<p class="ncl-status" id="needle-status"></p>' +
    '<div id="ncl-dirbox" hidden>' +
    '<div class="ncl-row"><button type="button" id="ncl-useview" title="Aim along the current viewing direction">Use view axis</button>' +
    '<button type="button" id="ncl-usenormal" title="Perpendicular to the skin at the entry">Perpendicular</button></div>' +
    '<div class="ncl-row">tilt <input type="number" id="ncl-tilt" min="0" max="85" step="1" value="0">&deg; from perpendicular, toward ' +
    '<input type="number" id="ncl-az" min="-180" max="180" step="5" value="0">&deg; (0 = cranial, 90 = the entry\'s right-hand side)</div></div>' +
    '<div class="ncl-row"><span>Needle length</span><input type="range" id="ncl-len" min="5" max="200" step="1" value="' + this.len + '">' +
    '<input type="number" id="ncl-lenn" min="5" max="200" step="1" value="' + this.len + '"> mm</div>' +
    '<div class="ncl-row"><button type="button" id="ncl-shortest" title="Shortest straight path from the target to the skin (or the outermost model surface)">Shortest entry</button>' +
    '<button type="button" id="ncl-zoom" title="Centre the view on the target (or the entry)">Zoom to target</button>' +
    '<button type="button" id="ncl-cuthere" title="A cut plane facing you through the target (or the screen centre) to expose deep tissue; click the cut face to pick a deep target">Cut through target</button></div>' +
    '<div id="needle-report"></div>' +
    '<details id="ncl-mp" open><summary>Motor points</summary>' +
    '<p class="ncl-status" id="ncl-mp-msg"></p>' +
    '<div class="ncl-row"><button type="button" id="ncl-mp-on" aria-pressed="false">Emphasize motor points</button></div>' +
    '<input type="search" id="ncl-mp-q" placeholder="Search a muscle to target its motor point" autocomplete="off">' +
    '<div class="res" id="ncl-mp-res"></div><div id="ncl-mp-info"></div></details>' +
    '<details id="ncl-risk" open><summary>Risk halos &amp; safer pathways</summary>' +
    '<p class="ncl-status" id="ncl-risk-msg"></p>' +
    '<div class="ncl-row"><button type="button" id="ncl-halo" aria-pressed="false">Show risk halos</button>' +
    '<button type="button" id="ncl-safer" title="Sample many straight approaches to the target and light the safer entries">Light safer pathways</button></div>' +
    '<div class="ncl-row"><span>Other tissue transparent</span><input type="range" id="ncl-transp" min="50" max="95" step="1" value="80"><span class="mono" id="ncl-transp-v">80%</span></div>' +
    '<div class="lg">' + legend + "</div>" +
    '<div class="formula" id="ncl-formula"></div>' +
    '<div class="grid2" style="margin-top:5px"><span>b0 (mm)</span><input type="number" step="0.5" min="0" max="20" data-p="b0" value="' + this.P.b0 + '"><span></span>' +
    '<span>k (per mm of path)</span><input type="number" step="0.005" min="0" max="0.3" data-p="k" value="' + this.P.k + '"><span></span>' +
    '<span>calibre exponent p</span><input type="number" step="0.1" min="0" max="2" data-p="p" value="' + this.P.p + '"><span></span>' + mults + "</div>" +
    '<div id="ncl-safer-out"></div><div id="ncl-halo-list"></div></details>' +
    '<details><summary>Display</summary><div class="ncl-row"><span>Shaft radius (display)</span>' +
    '<input type="range" id="ncl-rdisp" min="0.3" max="3" step="0.1" value="' + this.rDisp + '"><span class="mono" id="ncl-rdisp-v">' + this.rDisp.toFixed(1) + ' mm</span></div>' +
    '<p class="cite">The needle is drawn as a lit 3-D object in the model, so nearer parts look larger. The part beyond the entry is drawn ' +
    'normally (hidden by opaque tissue) plus a faint see-through copy, so it stays findable in deep tissue.</p></details>';
  if (api.panelHost) api.panelHost.insertBefore(el, api.panelBefore || null); else document.body.appendChild(el);
  this.el = el;
  var tip = document.createElement("div"); tip.className = "ncl-tip"; tip.hidden = true; document.body.appendChild(tip); this.tip = tip;
  function $(id) { return el.querySelector("#" + id); }
  this.$ = $;
  $("needle-clear").onclick = function () { self.clear(); };
  $("ncl-close").onclick = function () { self.toggle(false); };
  el.querySelectorAll("#ncl-modes button").forEach(function (b) { b.onclick = function () { self.setMode(b.dataset.mode); }; });
  $("ncl-useview").onclick = function () { self.dir.src = "view"; self.dir.view = api.view().dir; self.update(); };
  $("ncl-usenormal").onclick = function () { self.dir.src = "normal"; $("ncl-tilt").value = 0; self.dir.tilt = 0; self.update(); };
  $("ncl-tilt").oninput = function () { self.dir.src = "angles"; self.dir.tilt = +this.value || 0; self.update(); };
  $("ncl-az").oninput = function () { self.dir.src = "angles"; self.dir.az = +this.value || 0; self.update(); };
  function setLen(v) { self.len = clamp(+v || 60, 5, 200); $("ncl-len").value = self.len; $("ncl-lenn").value = self.len; self.update(); }
  this.setLength = setLen;
  $("ncl-len").oninput = function () { setLen(this.value); };
  $("ncl-lenn").onchange = function () { setLen(this.value); };
  $("ncl-shortest").onclick = function () { self.shortestEntry(); };
  $("ncl-zoom").onclick = function () {
    var p = self.target ? self.target.p : (self.entry ? self.entry.p : null);
    if (p && api.focus) api.focus(p, Math.max(160, (self.entry && self.target ? dist(self.entry.p, self.target.p) : self.len) * 3.2));
  };
  $("ncl-cuthere").onclick = function () {
    var v = api.view(); api.setCut({normal: v.dir, point: self.target ? self.target.p : v.target}); self.update();
  };
  $("ncl-mp-on").onclick = function () { self.emphasize(!self.mp.on); };
  $("ncl-mp-q").oninput = function () { self.renderSearch(); };
  $("ncl-halo").onclick = function () { self.halos(!self.risk.on); };
  $("ncl-safer").onclick = function () { self.runSafer(); };
  $("ncl-transp").oninput = function () { self.risk.transp = this.value / 100; $("ncl-transp-v").textContent = this.value + "%"; if (self.risk.on) self.applyOverride(); };
  el.querySelectorAll("[data-p]").forEach(function (inp) { inp.onchange = function () { self.P[inp.dataset.p] = +inp.value; self.paramsChanged(); }; });
  el.querySelectorAll("[data-mult]").forEach(function (inp) { inp.onchange = function () { self.P.mult[inp.dataset.mult] = +inp.value; self.paramsChanged(); }; });
  $("ncl-rdisp").oninput = function () { self.rDisp = +this.value; $("ncl-rdisp-v").textContent = self.rDisp.toFixed(1) + " mm"; self.drawNeedle(); api.redraw(); };
  this.renderFormula();
  this.setMode("two", true);
};
TP.renderFormula = function () {
  var P = this.P;
  this.$("ncl-formula").innerHTML = "halo r = clamp( m<sub>type</sub> &times; ( b0 &times; clamp((r<sub>cal</sub>/" + P.rRef + ")<sup>p</sup>, " + P.fMin + ", " + P.fMax +
    ") + k &times; L ), " + P.rMin + ", " + P.rMax + " ) mm<br>b0 = " + P.b0 + ", k = " + P.k + ", p = " + P.p +
    "; L = trajectory length (entry&rarr;target), else the needle length. r<sub>cal</sub> = vessel/nerve/organ calibre radius " +
    (this.risk.data ? "from clinical_risk.json" : "(approximate: clinical_risk.json not loaded)") + ". Heuristic planning margin.";
};
TP.paramsChanged = function () {
  this.renderFormula(); this.risk.safer = null; this.$("ncl-safer-out").innerHTML = "";
  this.ov.remove("sp-g"); this.ov.remove("sp-a"); this.ov.remove("sp-r"); this.ov.remove("sp-best"); this.ov.remove("sp-best-x");
  if (this.risk.on) this.refreshHalos();
  this.update();
};
TP.toggle = function (onOff) {
  this.active = onOff == null ? !this.active : !!onOff;
  this.btn.setAttribute("aria-pressed", String(this.active));
  this.el.hidden = !this.active;
  if (this.active) { this.api.stopMotion(); this.api.showPanel(); this.render(); }
  else { this.clear(); if (this.risk.on) this.halos(false); if (this.mp.on) this.emphasize(false); }
  this.api.redraw();
};
TP.cursor = function () { return this.active ? "crosshair" : null; };
TP.setMode = function (m, quiet) {
  this.mode = m;
  this.el.querySelectorAll("#ncl-modes button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.mode === m)); });
  this.$("ncl-dirbox").hidden = m !== "dir";
  if (!quiet) { if (m === "dir") this.target = null; this.update(); }
};
TP.clear = function () {
  this.entry = this.target = null; this.risk.pathEval = null; this.risk.safer = null;
  ["n-inner", "n-inner-x", "n-outer", "n-hub", "n-tgt", "n-tgt-x", "n-entry", "sp-g", "sp-a", "sp-r", "sp-best", "sp-best-x"].forEach(this.ov.remove, this.ov);
  this.$("ncl-safer-out").innerHTML = "";
  if (this.risk.on) this.refreshHalos();
  this.render(); this.api.redraw();
};

/* ---------- interaction ---------- */
TP.onClick = function (e) {
  var mpHit = this.mp.on ? this.markerAt(e) : null;
  if (mpHit) { if (!this.active) this.toggle(true); this.useMotorPoint(mpHit); return true; }
  if (!this.active) return false;
  var sp = this.risk.safer ? this.saferAt(e) : null;
  if (sp) { this.adopt(sp); return true; }
  var m = this.mode, hit;
  if (m === "two") {
    if (!this.entry || this.target) { hit = this.pickPoint(e, null); if (hit) { this.entry = hit; this.target = null; } }
    else { hit = this.pickPoint(e, this.entry.i); if (hit) this.target = hit; }
  } else if (m === "tfirst") {
    if (!this.target || this.entry) { hit = this.pickPoint(e, null); if (hit) { this.target = hit; this.entry = null; this.risk.safer = null; } }
    else { hit = this.pickPoint(e, null); if (hit) this.entry = hit; }
  } else {
    hit = this.pickPoint(e, null); if (hit) { this.entry = hit; this.dir.src = this.dir.src === "view" ? "view" : this.dir.src; }
  }
  this.update();
  return true;
};
TP.dirVector = function () {
  if (this.dir.src === "view" && this.dir.view) return norm(this.dir.view);
  var n = this.entry && this.entry.n ? norm(this.entry.n) : norm(this.entry && this.entry.ray ? this.entry.ray : this.api.view().dir);
  var up = sub([0, 1, 0], mul(n, n[1]));
  if (len(up) < 1e-3) up = sub([0, 0, 1], mul(n, n[2]));
  up = norm(up);
  var side = cross(n, up), th = this.dir.tilt * Math.PI / 180, az = this.dir.az * Math.PI / 180;
  return norm(add(mul(n, Math.cos(th)), mul(add(mul(up, Math.cos(az)), mul(side, Math.sin(az))), Math.sin(th))));
};
TP.update = function () {
  if (this.mode === "dir" && this.entry) {
    var u = this.dirVector(), tip = addS(this.entry.p, u, this.len), self = this;
    var vis = this.recs.filter(function (r) { return self.api.visible(r.i); }).map(function (r) { return r.i; });
    var rows = this.crossings(this.entry.p, tip, vis, null).filter(function (c) { return c.to >= self.len - 0.05; });
    var nonSkin = rows.filter(function (c) { return self.skin.indexOf(c.i) < 0; });
    var pickRow = (nonSkin.length ? nonSkin : rows).sort(function (a, b) { return b.from - a.from; })[0];
    this.target = {p: tip, i: pickRow ? pickRow.i : null, n: null, computed: true};
  }
  this.risk.pathEval = null;
  this.drawNeedle();
  if (this.risk.on) { this.refreshHalos(); if (this.entry && this.target) this.evalCurrent(); }
  this.render();
  this.api.redraw();
};
TP.onHostChange = function () { if (this.active && this.entry && this.target) this.render(); if (this.risk.on) this.refreshHalos(); };

/* ---------- needle drawing ---------- */
TP.drawNeedle = function () {
  var ov = this.ov, r = this.rDisp;
  ["n-inner", "n-inner-x", "n-outer", "n-hub", "n-tgt", "n-tgt-x", "n-entry"].forEach(ov.remove, ov);
  if (this.target) {
    ov.set("n-tgt", addSphere(new Geo(), this.target.p, r * 1.9), {color: "#E8875A", pass: "opaque", emis: 0.25});
    ov.set("n-tgt-x", addSphere(new Geo(), this.target.p, r * 1.9), {color: "#E8875A", pass: "xray", alpha: 0.45, emis: 0.3});
  }
  if (!this.entry) return;
  if (!this.target) { ov.set("n-entry", addSphere(new Geo(), this.entry.p, r * 1.7), {color: "#2F7D5B", pass: "opaque"}); return; }
  var E = this.entry.p, T = this.target.p, L = dist(E, T); if (L < 1e-3) return;
  var u = mul(sub(T, E), 1 / L), exposed = this.mode === "dir" ? 0 : clamp(this.len - L, 0, 200);
  var S0 = addS(E, u, -exposed), hubLen = Math.max(10, 7 * r), rHub = Math.max(2.4, 2.6 * r);
  var inner = addTube(new Geo(), E, T, r, r, 18, {bevel: Math.min(r * 5, L * 0.4), capB: true});
  ov.set("n-inner", inner, STEEL);
  ov.set("n-inner-x", inner, {color: "#FFD27A", pass: "xray", alpha: 0.3, emis: 0.35});
  if (exposed > 0.01) ov.set("n-outer", addTube(new Geo(), S0, E, r, r, 18, {}), STEEL);
  ov.set("n-hub", addTube(addTube(new Geo(), addS(S0, u, -hubLen), addS(S0, u, -hubLen * 0.25), rHub, rHub * 0.85, 24, {capA: true}),
                         addS(S0, u, -hubLen * 0.25), S0, rHub * 0.85, r * 1.3, 24, {capB: true}),
         {color: "#3C9A6E", pass: "opaque", shin: 30});
};

/* ---------- report panel ---------- */
TP.render = function () {
  if (!this.active) return;
  var st = this.$("needle-status"), rep = this.$("needle-report"), self = this, m = this.mode;
  var cutOn = !!this.api.cut(), cutHint = cutOn ? " The cut is on: a click on the cut face picks the point on the face." : "";
  rep.innerHTML = "";
  if (m === "dir" && !this.entry) { st.textContent = "Click the entry point on the skin (or the outermost surface). The tip lies along the direction below, at the needle length." + cutHint; return; }
  if (m !== "dir") {
    if (m === "two" && !this.entry) {
      st.textContent = this.skin.length ? "Click the entry point (usually the skin -- switch its system on to show it)." + cutHint
                                        : "Click the entry point (this model has no skin: use the outermost surface)." + cutHint;
      return;
    }
    if (m === "two" && !this.target) {
      st.innerHTML = "Entry on <b>" + esc(this.name(this.entry.i)) + "</b> at " + xyz1(this.entry.p) +
        ". Now click the target (the click looks through the entry structure; use the cut or hide what is in the way)." + esc(cutHint);
      return;
    }
    if (m === "tfirst" && !this.target) { st.textContent = "Click the deep target -- on a cut face (Cut through target / the Cut tool), or pick a motor point below." + cutHint; return; }
    if (m === "tfirst" && !this.entry) {
      st.innerHTML = "Target <b>" + esc(this.target.mp ? this.target.mp.muscle_name + " motor point" : this.name(this.target.i)) + "</b> at " + xyz1(this.target.p) +
        (this.target.onCut ? " (on the cut face)" : "") + ". Now click the entry, use <b>Shortest entry</b>, or <b>Light safer pathways</b>.";
      return;
    }
  }
  var R = this.report(); if (!R) return;
  st.innerHTML = "Entry <b>" + esc(this.name(this.entry.i)) + "</b> &rarr; " + (m === "dir" ? "tip" : "target") + " <b>" +
    esc(this.target.mp ? this.target.mp.muscle_name + " motor point" : (R.target_name || "no visible structure")) + "</b>. " +
    (m === "dir" ? "Click again to move the entry; Esc clears." : "Click again to start a new path; Esc clears.");
  var h = "<dl>" +
    "<dt>Length</dt><dd>" + f1(R.length_mm) + " mm" + (m !== "dir" && R.length_mm > this.len + 0.05 ? ' <span class="warn">longer than the ' + this.len + " mm needle</span>" : "") + "</dd>" +
    "<dt>Entry</dt><dd>" + xyz1(R.entry) + "</dd>" +
    "<dt>" + (m === "dir" ? "Tip" : "Target") + "</dt><dd>" + xyz1(R.target) + (this.target.onCut ? " (cut face)" : "") + "</dd>" +
    "<dt>Tip lands in</dt><dd>" + (R.tip_in.length ? esc(R.tip_in.join(" / ")) : '<span class="ncl-status">no visible structure (between structures, or the structure is hidden)</span>') + "</dd>" +
    "<dt>Below skin</dt><dd>" + (R.skin.depth == null ? esc(R.skin.how) : f1(R.skin.depth) + ' mm <span class="ncl-status">(' + esc(R.skin.how) + ")</span>") + "</dd>" +
    "</dl>";
  if (R.risk) h += this.riskLine(R.risk);
  h += '<p class="ncl-status" style="margin:8px 0 2px;font-weight:700">Passes through (mm from entry)</p>';
  if (!R.crossings.length) h += '<p class="ncl-status">No visible structure is crossed.</p>';
  else h += "<ol>" + R.crossings.map(function (c) {
    var col = self.api.catColor(self.recs[self.byId[c.id][0]].cat);
    var rng = (c.to_mm - c.from_mm < MINIV) ? '<span class="rng mono">' + c.from_mm.toFixed(1) + " (surface reached)</span>"
      : '<span class="rng mono">' + c.from_mm.toFixed(1) + "&ndash;" + c.to_mm.toFixed(1) + "</span>";
    return '<li><span class="dot" style="background:' + col + '"></span>' + esc(c.name) + (c.name !== c.id ? ' <span class="ncl-status mono">' + esc(c.id) + "</span>" : "") + rng + "</li>";
  }).join("") + "</ol>";
  h += '<p class="cite">Straight-line geometry on the decimated viewing meshes, visible structures only; depths are along the path, ' +
       "not perpendicular to the skin. Not a clinical recommendation.</p>";
  rep.innerHTML = h;
};
TP.riskLine = function (ev) {
  if (ev.pending) return '<p class="ncl-status">Risk margins on this path: computing...</p>';
  var cls = {green: "pill-g", amber: "pill-a", red: "pill-r"}[ev.colour], self = this;
  var words = {green: "clear of every halo", amber: "inside a heuristic margin", red: ev.blocked ? "blocked by bone or by the body outside the entry" : "touches a risk structure"};
  var h = '<p style="margin:6px 0 2px">Risk margins on this path: <span class="' + cls + '">' + ev.colour.toUpperCase() + "</span> -- " + words[ev.colour] + "</p>";
  if (ev.close && ev.close.length) h += "<ol>" + ev.close.slice(0, 5).map(function (c) {
    return '<li><span class="dot" style="background:' + CLASSES[c.cls].color + '"></span>' + esc(self.name(c.ref)) +
      ' <span class="rng mono">clear ' + c.clear.toFixed(1) + " / halo " + c.halo.toFixed(1) + " mm</span></li>";
  }).join("") + "</ol>";
  return h;
};

/* ---------- data files (published next to the page) ---------- */
TP.loadData = function () {
  var self = this;
  function get(url) {
    return fetch(url, {cache: "no-cache"}).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  Promise.all([get("clinical_risk.json"), get("clinical_motor_points.json")]).then(function (res) {
    var risk = res[0], mp = res[1];
    if (risk && risk.schema === "nmsk.clinical_risk.v1") {
      self.risk.data = risk;
      (risk.structures || []).forEach(function (s) { if (s.r_mm > 0) self.risk.rcal[s.id] = s.r_mm; });
    }
    self.viewerKey = (risk && risk.viewer) || self.api.viewerGuess;
    if (mp && mp.schema === "nmsk.motor_points.v1" && mp.viewers) {
      self.mp.data = mp;
      var v = mp.viewers[self.viewerKey];
      self.mp.points = v && v.points ? v.points.filter(function (p) { return p.pos && p.pos.length === 3; }) : [];
      self.mp.msg = self.mp.points.length
        ? self.mp.points.length + " motor points for this body (" + esc(self.viewerKey) + ")" + (mp.licence ? " -- " + esc(mp.licence) : "")
        : "no motor-point data loaded for this body (" + esc(self.viewerKey) + ")";
    } else self.mp.msg = "no motor-point data loaded";
    self.renderMp(); self.renderRiskMsg(); self.renderFormula();
  });
};
TP.renderRiskMsg = function () {
  var d = this.risk.data, n = this.cls.filter(function (c) { return c && CLASSES[c].halo; }).length;
  this.$("ncl-risk-msg").innerHTML = n + " risk structures in this model (classification table in the add-on). " +
    (d ? "Calibre from clinical_risk.json (" + esc(d.viewer) + ", " + esc(d.generated || "") + ")."
       : '<span class="warn">clinical_risk.json not loaded: calibre approximated from bounding boxes.</span>');
};
TP.rCal = function (i) {
  var r = this.risk.rcal[this.recs[i].id];
  if (r) return r;
  var R = this.recs[i], ext = Math.min(R.bmax[0] - R.bmin[0], R.bmax[1] - R.bmin[1], R.bmax[2] - R.bmin[2]);
  return clamp(ext / 2, 0.5, 15);
};

/* ---------- motor points ---------- */
TP.renderMp = function () {
  this.$("ncl-mp-msg").innerHTML = this.mp.msg;
  var none = !this.mp.points.length;
  this.$("ncl-mp-on").disabled = none; this.$("ncl-mp-q").disabled = none;
  this.renderSearch();
};
TP.renderSearch = function () {
  var q = this.$("ncl-mp-q").value.trim().toLowerCase(), box = this.$("ncl-mp-res"), self = this;
  box.innerHTML = "";
  if (!q || !this.mp.points.length) return;
  var hits = this.mp.points.filter(function (p) {
    return ((p.muscle_name || "") + " " + (p.structure_id || "") + " " + (p.atlas_id || "") + " " + (p.nerve || "")).toLowerCase().indexOf(q) >= 0;
  }).slice(0, 40);
  if (!hits.length) { box.innerHTML = '<p class="ncl-status">No motor point matches.</p>'; return; }
  hits.forEach(function (p) {
    var b = document.createElement("button"); b.type = "button";
    b.innerHTML = esc(p.muscle_name) + (p.side ? " (" + esc(p.side) + ")" : "") + ' <span class="ncl-status">' + esc(p.kind || "") +
      (p.depth_from_skin_mm != null ? " &middot; " + Number(p.depth_from_skin_mm).toFixed(0) + " mm deep" : "") + "</span>";
    b.onclick = function () { self.useMotorPoint(p); };
    box.appendChild(b);
  });
};
TP.mpStructure = function (p) {
  var ids = this.byId[p.structure_id] || this.byId[p.atlas_id] || [], self = this;
  var inBox = ids.filter(function (i) { var r = self.recs[i]; return p.pos.every(function (c, k) { return c >= r.bmin[k] - 2 && c <= r.bmax[k] + 2; }); });
  return (inBox.length ? inBox : ids).length ? (inBox.length ? inBox : ids)[0] : null;
};
TP.useMotorPoint = function (p) {
  this.mp.sel = p;
  this.target = {p: p.pos.slice(), i: this.mpStructure(p), n: null, mp: p};
  if (this.mode === "dir") this.setMode("tfirst", true);
  if (this.mode === "tfirst") this.entry = null;
  if (this.mode === "two" && !this.entry) this.setMode("tfirst", true);
  this.risk.safer = null;
  ["sp-g", "sp-a", "sp-r", "sp-best", "sp-best-x"].forEach(this.ov.remove, this.ov);
  this.$("ncl-safer-out").innerHTML = "";
  this.renderMpInfo(p);
  this.update();
};
TP.renderMpInfo = function (p) {
  var s = p.source || {};
  this.$("ncl-mp-info").innerHTML = '<dl style="margin-top:8px">' +
    "<dt>Motor point</dt><dd><b>" + esc(p.muscle_name) + "</b>" + (p.side ? " (" + esc(p.side) + ")" : "") + (p.kind ? " &middot; " + esc(p.kind) : "") + "</dd>" +
    "<dt>Nerve</dt><dd>" + esc(p.nerve || "--") + "</dd>" +
    "<dt>Depth</dt><dd>" + (p.depth_from_skin_mm != null ? f1(p.depth_from_skin_mm) + " mm from the skin" : "--") +
    (p.projection_mm != null ? "; projection " + esc(JSON.stringify(p.projection_mm)) : "") + "</dd>" +
    "<dt>Uncertainty</dt><dd>" + (p.uncertainty_mm != null ? f1(p.uncertainty_mm) + " mm (sphere radius)" : "--") + "</dd>" +
    "<dt>Source</dt><dd>" + esc(s.citation || "--") + (s.doi ? " doi:" + esc(s.doi) : "") + (s.pmid ? " PMID " + esc(s.pmid) : "") +
    (s.rule ? '<br><span class="ncl-status">' + esc(s.rule) + "</span>" : "") + "</dd>" +
    (p.badge ? "<dt>Badge</dt><dd>" + esc(p.badge) + "</dd>" : "") + "</dl>";
};
TP.emphasize = function (on) {
  this.mp.on = !!on && this.mp.points.length > 0;
  this.$("ncl-mp-on").setAttribute("aria-pressed", String(this.mp.on));
  ["mp-core", "mp-core-x", "mp-unc", "mp-unc-x"].forEach(this.ov.remove, this.ov);
  if (this.mp.on) {
    var pts = this.mp.points;
    var cores = chunked(pts, function (g, p) { addSphere(g, p.pos, 1.8, 10, 6); });
    var unc = chunked(pts, function (g, p) { addSphere(g, p.pos, Math.max(2, +p.uncertainty_mm || 5), 14, 9); });
    this.ov.set("mp-core", cores, {color: MP_COLOUR, pass: "opaque", emis: 0.6});
    this.ov.set("mp-core-x", cores, {color: MP_COLOUR, pass: "xray", alpha: 0.55, emis: 0.7});
    this.ov.set("mp-unc", unc, {color: MP_COLOUR, pass: "trans", alpha: 0.14, emis: 0.5});
    this.ov.set("mp-unc-x", unc, {color: MP_COLOUR, pass: "xray", alpha: 0.06, emis: 0.5});
  }
  this.applyOverride();
};
TP.markerAt = function (e) {
  var best = null, bd = 14, api = this.api;
  this.mp.points.forEach(function (p) {
    var s = api.toScreen(p.pos); if (!s) return;
    var d = Math.hypot(s[0] - e.clientX, s[1] - e.clientY); if (d < bd) { bd = d; best = p; }
  });
  return best;
};
TP.onHover = function (e) {
  var p = this.mp.on ? this.markerAt(e) : null, tip = this.tip;
  if (!p) { tip.hidden = true; return; }
  var s = p.source || {};
  tip.innerHTML = "<b>" + esc(p.muscle_name) + "</b>" + (p.side ? " (" + esc(p.side) + ")" : "") + " motor point" + (p.kind ? " &middot; " + esc(p.kind) : "") +
    "<br>Nerve: " + esc(p.nerve || "--") + (p.uncertainty_mm != null ? "<br>&plusmn; " + Number(p.uncertainty_mm).toFixed(0) + " mm" : "") +
    "<br><span style='opacity:.75'>" + esc(s.citation || "") + "</span>" + (p.badge ? "<br><i>" + esc(p.badge) + "</i>" : "") +
    "<br><span style='opacity:.75'>click: make it the needle target</span>";
  tip.style.left = Math.min(window.innerWidth - 290, e.clientX + 14) + "px"; tip.style.top = (e.clientY + 12) + "px"; tip.hidden = false;
};

/* ---------- tissue opacity while emphasising / showing halos ---------- */
/* tissue systems that stay opaque (and are switched on) in halo mode: those
   holding vessels, nerves and organs; every other system gets the slider's
   transparency (brain/cord and lymph layers too -- they are haloed, not hidden). */
var RISK_SYSTEMS = ["vessel", "nerve", "organ", "viscera"];
TP.riskCats = function () {
  var s = {}, self = this;
  this.recs.forEach(function (r) { if (RISK_SYSTEMS.indexOf(r.cat) >= 0) s[r.cat] = 1; });
  return s;
};
TP.applyOverride = function () {
  var self = this, risk = this.risk.on ? this.riskCats() : null, alpha = 1 - this.risk.transp, mpOn = this.mp.on;
  if (!risk && !mpOn) { this.api.setOpacityOverride(null); return; }
  this.api.setOpacityOverride(function (cat) {
    var v = null;
    if (risk && !risk[cat]) v = alpha;
    if (mpOn && cat === "muscle") v = Math.min(v == null ? 1 : v, 0.35);
    return v;
  });
};

/* ---------- risk halos ---------- */
TP.currentL = function () {
  if (this.entry && this.target) return dist(this.entry.p, this.target.p);
  return this.len;
};
TP.halos = function (on) {
  var api = this.api, self = this;
  this.risk.on = !!on;
  this.$("ncl-halo").setAttribute("aria-pressed", String(this.risk.on));
  if (this.risk.on) {
    var cats = this.riskCats();
    this.risk.saved = {};
    Object.keys(cats).forEach(function (c) { self.risk.saved[c] = api.categoryOn(c); api.setCategoryOn(c, true); });
  } else if (this.risk.saved) {
    Object.keys(this.risk.saved).forEach(function (c) { api.setCategoryOn(c, self.risk.saved[c]); });
    this.risk.saved = null;
  }
  this.applyOverride();
  this.refreshHalos();
  if (this.risk.on && this.entry && this.target) this.evalCurrent();
  this.render(); api.redraw();
};
TP.refreshHalos = function () {
  if (!this.risk.on) { this.ov.setHalos([]); this.$("ncl-halo-list").innerHTML = ""; this.api.redraw(); return; }
  var self = this, L = this.currentL(), focus = this.target ? this.target.p : (this.entry ? this.entry.p : null);
  var reach = this.len + 60, list = [], rows = [];
  this.recs.forEach(function (r, i) {
    var c = self.cls[i]; if (!c || !CLASSES[c].halo || !self.api.visible(i)) return;
    var dmin = 0;
    if (focus) {
      for (var k = 0; k < 3; k++) { var dk = Math.max(r.bmin[k] - focus[k], 0, focus[k] - r.bmax[k]); dmin += dk * dk; }
      dmin = Math.sqrt(dmin); if (dmin > reach) return;
    }
    var rc = self.rCal(i), h = haloRadius(c, rc, L, self.P);
    list.push({i: i, r: h * self.orientSign(i), color: CLASSES[c].color, alpha: 0.22});
    rows.push({i: i, cls: c, rc: rc, h: h, d: dmin});
  });
  this.ov.setHalos(list);
  rows.sort(function (a, b) { return a.d - b.d; });
  this.$("ncl-halo-list").innerHTML = '<p class="ncl-status" style="margin-top:6px">' + list.length + " halos at L = " + L.toFixed(0) + " mm" +
    (focus ? " (within " + reach.toFixed(0) + " mm of the " + (this.target ? "target" : "entry") + ")" : " (whole model -- set a target to narrow)") + ". Nearest:</p>" +
    "<ol>" + rows.slice(0, 8).map(function (r) {
      return '<li><span class="dot" style="background:' + CLASSES[r.cls].color + '"></span>' + esc(self.name(r.i)) +
        ' <span class="rng mono">r<sub>cal</sub> ' + r.rc.toFixed(1) + " &rarr; halo " + r.h.toFixed(1) + " mm</span></li>";
    }).join("") + "</ol>";
  this.api.redraw();
};

/* ---------- the region around a target: surfaces, bone, risk samples ---------- */
/* Built once per target and reach (the expensive step), then reused by every
   path query: a triangle grid of the skin (or, in a model without skin, of
   every structure: the outermost surface), a triangle grid of bone, and the
   risk structures' surface vertices thinned to one per 2.5 mm voxel. */
TP.region = function (T, reach) {
  var R0 = this.risk.region, tgtId = this.target && this.target.i != null ? this.recs[this.target.i].id : null;
  if (R0 && R0.reach === reach && dist(R0.T, T) < 1e-6 && R0.P === JSON.stringify(this.P) && R0.tgtId === tgtId) return R0;
  var t0 = performance.now(), self = this, H = reach + HUB_CLEAR_MM + 8;
  var bmin = [T[0] - H, T[1] - H, T[2] - H], bmax = [T[0] + H, T[1] + H, T[2] + H];
  function gather(idxs) {
    var tris = [], owner = [];
    idxs.forEach(function (i) {
      var r = self.recs[i]; if (!boxOverlap(r.bmin, r.bmax, bmin, bmax)) return;
      var g = self.geom(i); if (!g) return;
      var P = g.pos, I = g.idx;
      for (var f = 0; f < I.length; f += 3) {
        var a = I[f] * 3, b = I[f + 1] * 3, c = I[f + 2] * 3, ok = true;
        for (var k = 0; k < 3 && ok; k++) {
          var mn = Math.min(P[a + k], P[b + k], P[c + k]), mx = Math.max(P[a + k], P[b + k], P[c + k]);
          if (mx < bmin[k] || mn > bmax[k]) ok = false;
        }
        if (!ok) continue;
        tris.push(P[a], P[a + 1], P[a + 2], P[b], P[b + 1], P[b + 2], P[c], P[c + 1], P[c + 2]); owner.push(i);
      }
    });
    return new TriGrid(new Float32Array(tris), new Int32Array(owner), bmin, bmax, 10);
  }
  var all = this.recs.map(function (r) { return r.i; });
  var useSkin = this.skin.length > 0;
  var surf = gather(useSkin ? this.skin : all);
  var bone = gather(all.filter(function (i) { return self.cls[i] === "bone"; }));
  // the target's own structure (the thing being injected) is excluded from the risk check
  var pts = [], own = [], sIdx = [], seen = new Set();
  all.forEach(function (i) {
    var c = self.cls[i]; if (!c || !CLASSES[c].halo || self.recs[i].id === tgtId) return;
    var r = self.recs[i]; if (!boxOverlap(r.bmin, r.bmax, bmin, bmax)) return;
    var g = self.geom(i); if (!g) return;
    var P = g.pos, I = g.idx, si = sIdx.length, before = pts.length;
    seen.clear();
    function addPt(x, y, z) {
      if (x < bmin[0] || y < bmin[1] || z < bmin[2] || x > bmax[0] || y > bmax[1] || z > bmax[2]) return;
      var key = Math.floor((x - bmin[0]) / SPACING) * 1e8 + Math.floor((y - bmin[1]) / SPACING) * 1e4 + Math.floor((z - bmin[2]) / SPACING);
      if (seen.has(key)) return; seen.add(key); pts.push(x, y, z); own.push(si);
    }
    for (var v = 0; v < P.length; v += 3) addPt(P[v], P[v + 1], P[v + 2]);
    for (var f = 0; f < I.length; f += 3) {       // fill big triangles with their centroids
      var a = I[f] * 3, b = I[f + 1] * 3, cc = I[f + 2] * 3;
      var e = Math.max(Math.hypot(P[a] - P[b], P[a + 1] - P[b + 1], P[a + 2] - P[b + 2]), Math.hypot(P[a] - P[cc], P[a + 1] - P[cc + 1], P[a + 2] - P[cc + 2]));
      if (e > 2 * SPACING) addPt((P[a] + P[b] + P[cc]) / 3, (P[a + 1] + P[b + 1] + P[cc + 1]) / 3, (P[a + 2] + P[b + 2] + P[cc + 2]) / 3);
    }
    if (pts.length > before) sIdx.push({i: i, cls: c, rCal: self.rCal(i)});
  });
  var grid = new PointGrid(new Float32Array(pts), new Int32Array(own), bmin, bmax, 8);
  var reg = {T: T.slice(), reach: reach, P: JSON.stringify(this.P), tgtId: tgtId, surf: surf, useSkin: useSkin, bone: bone, grid: grid, structs: sIdx,
             nTris: surf.ntris + bone.ntris, nPts: pts.length / 3, ms: performance.now() - t0, minD: new Float32Array(sIdx.length)};
  this.risk.region = reg;
  return reg;
};
/* the entry for direction u from target T: {E, L, entryI, ok, why} */
TP.entryFor = function (reg, T, u, reach) {
  if (reg.useSkin) {
    var hs = reg.surf.ray(T, u, 0.2, reach + HUB_CLEAR_MM);
    if (!hs.length) return {ok: false, why: "no skin within reach"};
    var t1 = hs[0].t; if (t1 > reach) return {ok: false, why: "longer than the needle"};
    var again = hs.some(function (h) { return h.t > t1 + 0.5 && h.t <= t1 + HUB_CLEAR_MM; });
    return {ok: true, E: addS(T, u, t1), L: t1, entryI: reg.surf.owner[hs[0].tri], obstructed: again};
  }
  var ho = reg.surf.ray(T, u, 0.2, reach + HUB_CLEAR_MM);
  if (!ho.length) return {ok: false, why: "no surface"};
  var last = ho[ho.length - 1];
  if (last.t > reach) return {ok: false, why: "longer than the needle"};
  return {ok: true, E: addS(T, u, last.t), L: last.t, entryI: reg.surf.owner[last.tri], obstructed: false};
};
/* risk evaluation of the straight path E -> T */
TP.evalPath = function (reg, E, T, L, obstructed) {
  var P = this.P, maxM = 0;
  HALO_CLASSES.forEach(function (c) { maxM = Math.max(maxM, P.mult[c] || 0); });
  var R = clamp(maxM * (P.b0 * P.fMax + P.k * L), P.rMin, P.rMax) + 8;
  var minD = reg.minD, owner = reg.grid.owner, touched = [];
  reg.grid.capsule(E, T, R, function (p, d) {
    var s = owner[p];
    if (minD[s] === 0) touched.push(s);
    if (minD[s] === 0 || d < minD[s] - 1e-9) minD[s] = d + 1e-9;
  });
  var items = [];
  touched.forEach(function (s) {
    var st = reg.structs[s];
    items.push({ref: st.i, cls: st.cls, rCal: st.rCal, clear: Math.max(0, minD[s] - SPACING / 2)});
    minD[s] = 0;
  });
  var u = norm(sub(E, T));
  var boneHit = reg.bone.ntris ? reg.bone.ray(T, u, 2, Math.max(2, L - 0.5)) : [];
  var blocked = boneHit.length > 0 || !!obstructed;
  var sc = scorePath(items, L, blocked, P);
  items.sort(function (a, b) { return (a.clear - haloRadius(a.cls, a.rCal, L, P)) - (b.clear - haloRadius(b.cls, b.rCal, L, P)); });
  return {colour: sc.colour, cost: sc.cost, minMargin: sc.minMargin, blocked: blocked, bone: boneHit.length > 0, obstructed: !!obstructed,
          close: items.slice(0, 6).map(function (it) { return {ref: it.ref, cls: it.cls, clear: it.clear, halo: haloRadius(it.cls, it.rCal, L, P)}; })};
};
TP.evalCurrent = function () {
  var self = this; if (!this.entry || !this.target) return;
  this.risk.pathEval = {pending: true};
  setTimeout(function () {
    if (!self.entry || !self.target) return;
    var T = self.target.p, E = self.entry.p, L = dist(E, T);
    var reg = self.region(T, Math.max(self.len, L + 1));
    self.risk.pathEval = self.evalPath(reg, E, T, L, false);
    self.render();
  }, 0);
};

/* ---------- safer pathways ---------- */
TP.runSafer = function (opts) {
  var self = this, out = this.$("ncl-safer-out");
  if (!this.target) { out.innerHTML = '<p class="warn">Set a target first (target-first mode, a cut face, or a motor point).</p>'; return Promise.resolve(null); }
  if (!this.risk.on) this.halos(true);
  opts = opts || {};
  var N = opts.n || 720, T = this.target.p.slice(), reach = this.len, dirs = fibonacciSphere(N), t0 = performance.now();
  out.innerHTML = '<p class="ncl-status">Building the region around the target...</p>';
  var token = (this.saferToken = (this.saferToken || 0) + 1);
  return new Promise(function (resolve) {
    setTimeout(function () {
      t0 = performance.now();   // compute time only (not the wait for queued frames before this task runs)
      var reg = self.region(T, reach), tReg = performance.now() - t0, res = [], k = 0, tEval = 0;
      function chunk() {
        if (token !== self.saferToken) return resolve(null);
        var c0 = performance.now(), stop = Math.min(N, k + 60);
        for (; k < stop; k++) {
          var u = [dirs[3 * k], dirs[3 * k + 1], dirs[3 * k + 2]], en = self.entryFor(reg, T, u, reach);
          if (!en.ok) continue;
          var ev = self.evalPath(reg, en.E, T, en.L, en.obstructed);
          res.push({u: u, E: en.E, L: en.L, entryI: en.entryI, colour: ev.colour, cost: ev.cost, ev: ev});
        }
        tEval += performance.now() - c0;     // compute only; the browser draws between chunks
        if (k < N) { out.innerHTML = '<p class="ncl-status">Evaluating approaches ' + k + "/" + N + "...</p>"; return setTimeout(chunk, 0); }
        res.sort(function (a, b) { return a.cost - b.cost; });
        var greens = res.filter(function (r) { return r.colour === "green"; }), ambers = res.filter(function (r) { return r.colour === "amber"; });
        var best = (greens.length ? greens : ambers).slice(0, 3);
        self.risk.safer = {res: res, best: best, N: N, ms: tReg + tEval, msRegion: tReg, msEval: tEval, reg: reg};
        self.drawSafer(); self.renderSafer();
        resolve(self.saferSummary());
      }
      chunk();
    }, 0);
  });
};
TP.saferSummary = function () {
  var s = this.risk.safer; if (!s) return null;
  var c = {green: 0, amber: 0, red: 0};
  s.res.forEach(function (r) { c[r.colour]++; });
  return {directions: s.N, reachable: s.res.length, green: c.green, amber: c.amber, red: c.red, ms_total: Math.round(s.ms),
          ms_region: Math.round(s.msRegion), ms_eval: Math.round(s.msEval), region_triangles: s.reg.nTris, risk_samples: s.reg.nPts,
          risk_structures: s.reg.structs.length,
          best: s.best.map(function (b) { return {colour: b.colour, length_mm: +b.L.toFixed(1), entry: b.E.map(function (x) { return +x.toFixed(1); }),
                                                  min_margin_mm: isFinite(b.ev.minMargin) ? +b.ev.minMargin.toFixed(1) : null}; })};
};
TP.drawSafer = function () {
  var s = this.risk.safer, ov = this.ov, self = this;
  ["sp-g", "sp-a", "sp-r", "sp-best", "sp-best-x"].forEach(ov.remove, ov);
  if (!s) return;
  ["green", "amber", "red"].forEach(function (c) {
    var pts = s.res.filter(function (r) { return r.colour === c; });
    ov.set("sp-" + c[0], chunked(pts, function (g, r) { addSphere(g, r.E, c === "red" ? 1.1 : 1.5, 8, 5); }), {color: COLOUR[c], pass: "opaque", emis: 0.35});
  });
  var g = new Geo(), T = this.target.p;
  s.best.forEach(function (b) { addTube(g, b.E, T, 0.4 * self.rDisp + 0.15, 0.4 * self.rDisp + 0.15, 10, {}); });
  ov.set("sp-best", g, {color: "#7BE0A6", pass: "trans", alpha: 0.5, emis: 0.3});
  ov.set("sp-best-x", g, {color: "#7BE0A6", pass: "xray", alpha: 0.18, emis: 0.3});
  this.api.redraw();
};
TP.renderSafer = function () {
  var S = this.saferSummary(), out = this.$("ncl-safer-out"), self = this; if (!S) return;
  var h = '<p style="margin:8px 0 2px"><b>' + S.reachable + "</b> of " + S.directions + " sampled directions reach the " + (this.skin.length ? "skin" : "outermost surface") +
    " within " + this.len + ' mm: <span class="pill-g">' + S.green + ' green</span>, <span class="pill-a">' + S.amber + ' amber</span>, <span class="pill-r">' + S.red +
    ' red</span>. <span class="ncl-status">' + S.ms_total + " ms (region " + S.ms_region + " ms: " + S.region_triangles.toLocaleString() + " triangles, " +
    S.risk_samples.toLocaleString() + " risk samples from " + S.risk_structures + " structures; paths " + S.ms_eval + " ms)</span></p>";
  if (!S.best.length) h += '<p class="warn">No approach within the needle length clears the risk structures' + (S.reachable ? "" : " (none reaches the skin)") + ".</p>";
  else h += "<ol>" + this.risk.safer.best.map(function (b, k) {
    var w = b.ev.close[0];
    return '<li><button type="button" data-best="' + k + '">use</button> <span class="pill-' + b.colour[0] + '">' + b.colour + "</span> " + b.L.toFixed(0) + " mm" +
      (w ? ' <span class="ncl-status">closest: ' + esc(self.name(w.ref)) + " " + w.clear.toFixed(1) + "/" + w.halo.toFixed(1) + " mm</span>" : "") + "</li>";
  }).join("") + "</ol>";
  h += '<p class="cite">Green: outside every halo; amber: inside a halo but clear of the structure; red: touches a risk structure, crosses bone, or the body ' +
       "lies within " + HUB_CLEAR_MM + " mm outside the entry. Click an entry dot or a faint best path in the model to adopt it. The target's own structure is not scored. Heuristic.</p>";
  out.innerHTML = h;
  out.querySelectorAll("[data-best]").forEach(function (b) { b.onclick = function () { self.adopt(self.risk.safer.best[+b.dataset.best]); }; });
};
TP.saferAt = function (e) {
  var s = this.risk.safer, api = this.api, best = null, bd = 11;
  s.res.forEach(function (r) {
    var p = api.toScreen(r.E); if (!p) return;
    var d = Math.hypot(p[0] - e.clientX, p[1] - e.clientY); if (d < bd) { bd = d; best = r; }
  });
  if (best) return best;
  var T = api.toScreen(this.target.p);
  if (T) s.best.forEach(function (r) {   // the faint best lines themselves
    var A = api.toScreen(r.E); if (!A) return;
    var dx = T[0] - A[0], dy = T[1] - A[1], l2 = dx * dx + dy * dy || 1, t = clamp(((e.clientX - A[0]) * dx + (e.clientY - A[1]) * dy) / l2, 0, 1);
    var d = Math.hypot(A[0] + t * dx - e.clientX, A[1] + t * dy - e.clientY); if (d < bd - 4) { bd = d + 4; best = r; }
  });
  return best;
};
TP.adopt = function (r) {
  this.entry = {p: r.E.slice(), i: r.entryI, n: mul(r.u, -1)};
  if (this.mode === "dir") this.setMode("tfirst", true);
  this.update();
};
TP.shortestEntry = function () {
  var self = this; if (!this.target) { this.$("needle-status").textContent = "Set a target first."; return; }
  setTimeout(function () {
    var T = self.target.p, reg = self.region(T, self.len), dirs = fibonacciSphere(1200), best = null;
    for (var k = 0; k < 1200; k++) {
      var en = self.entryFor(reg, T, [dirs[3 * k], dirs[3 * k + 1], dirs[3 * k + 2]], self.len);
      if (en.ok && !en.obstructed && (!best || en.L < best.L)) best = {E: en.E, L: en.L, entryI: en.entryI, u: [dirs[3 * k], dirs[3 * k + 1], dirs[3 * k + 2]]};
    }
    if (!best) { self.$("needle-status").innerHTML = '<span class="warn">No skin within the ' + self.len + " mm needle length.</span>"; return; }
    self.adopt(best);
  }, 0);
};

/* ---------- facade for the host page and for test harnesses ---------- */
TP.setPath = function (entry, target, entryId, targetId) {
  if (!this.active) this.toggle(true);
  if (this.mode === "dir") this.setMode("two", true);
  var self = this;
  function idx(id, p) {
    var ids = id ? self.byId[id] || [] : [];
    if (ids.length > 1 && p) {
      var inb = ids.filter(function (i) { var r = self.recs[i]; return p.every(function (c, k) { return c >= r.bmin[k] - 1 && c <= r.bmax[k] + 1; }); });
      if (inb.length) return inb[0];
    }
    return ids.length ? ids[0] : null;
  }
  this.entry = {p: entry.slice(), i: idx(entryId, entry), n: null};
  this.target = target ? {p: target.slice(), i: idx(targetId, target), n: null} : null;
  this.update();
};

global.NMSKClinical = {
  version: 1,
  pure: PURE,
  attach: function (api) {
    var tool = new Tool(api);
    global.NMSKClinicalTool = tool;
    global.NeedlePath = {        // compatible with the pre-Q188 in-template tool's harness API
      toggle: function (on) { tool.toggle(on); }, clear: function () { tool.clear(); },
      setPoints: function (e, t, eid, tid) { tool.setPath(e, t, eid, tid); },
      report: function () { return tool.report(); },
      toScreen: function (p) { return api.toScreen(p); }
    };
    return {cursor: function () { return tool.cursor(); },
            setPath: function (e, t, eid, tid) { tool.setPath(e, t, eid, tid); }};
  }
};
})(typeof window !== "undefined" ? window : globalThis);
