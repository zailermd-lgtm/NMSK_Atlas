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
var SKIN_STACK_MM = 5; // Q367: skin surfaces this close behind one another along a ray are one skin (overlapping pieces, shell meshes)

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

/* ===================================================================== */
/* Q268 (item 2): exact segment -> triangle-mesh distance. Pure functions,  */
/* unit-tested in tests/test_q268_segment_distance.py (node) against an     */
/* independent trimesh / numpy computation. The tool MEASURES and DISPLAYS  */
/* these numbers; it never turns them into a safe / unsafe verdict.         */
/* ===================================================================== */
/* closest point on triangle abc to p (Ericson, Real-Time Collision Detection 5.1.5); returns [x, y, z] */
function closestPtTri(p, a, b, c) {
  var abx = b[0] - a[0], aby = b[1] - a[1], abz = b[2] - a[2], acx = c[0] - a[0], acy = c[1] - a[1], acz = c[2] - a[2];
  var apx = p[0] - a[0], apy = p[1] - a[1], apz = p[2] - a[2];
  var d1 = abx * apx + aby * apy + abz * apz, d2 = acx * apx + acy * apy + acz * apz;
  if (d1 <= 0 && d2 <= 0) return [a[0], a[1], a[2]];
  var bpx = p[0] - b[0], bpy = p[1] - b[1], bpz = p[2] - b[2];
  var d3 = abx * bpx + aby * bpy + abz * bpz, d4 = acx * bpx + acy * bpy + acz * bpz;
  if (d3 >= 0 && d4 <= d3) return [b[0], b[1], b[2]];
  var vc = d1 * d4 - d3 * d2;
  if (vc <= 0 && d1 >= 0 && d3 <= 0) { var v = d1 / (d1 - d3); return [a[0] + abx * v, a[1] + aby * v, a[2] + abz * v]; }
  var cpx = p[0] - c[0], cpy = p[1] - c[1], cpz = p[2] - c[2];
  var d5 = abx * cpx + aby * cpy + abz * cpz, d6 = acx * cpx + acy * cpy + acz * cpz;
  if (d6 >= 0 && d5 <= d6) return [c[0], c[1], c[2]];
  var vb = d5 * d2 - d1 * d6;
  if (vb <= 0 && d2 >= 0 && d6 <= 0) { var w = d2 / (d2 - d6); return [a[0] + acx * w, a[1] + acy * w, a[2] + acz * w]; }
  var va = d3 * d6 - d5 * d4;
  if (va <= 0 && (d4 - d3) >= 0 && (d5 - d6) >= 0) {
    var w2 = (d4 - d3) / ((d4 - d3) + (d5 - d6));
    return [b[0] + (c[0] - b[0]) * w2, b[1] + (c[1] - b[1]) * w2, b[2] + (c[2] - b[2]) * w2];
  }
  var den = 1 / (va + vb + vc), v2 = vb * den, w3 = vc * den;
  return [a[0] + abx * v2 + acx * w3, a[1] + aby * v2 + acy * w3, a[2] + abz * v2 + acz * w3];
}
function pointTriDist(p, a, b, c) { var q = closestPtTri(p, a, b, c); return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]); }
/* Q325: a point kept ON the structure it was placed on while the body is posed. Anchor: the structure's nearest
   triangle, the point's UNCLAMPED barycentric coordinates in that triangle's plane and its signed height h above it
   (so p = wA*A + wB*B + wC*C + h*n reproduces the point exactly on the mesh it was taken from, also off the triangle's
   edges); a direction (the entry's surface normal) is kept in the triangle's own frame. Re-placed on any other vertex
   set of the same mesh (posed / rest), the point rides the triangle: exact for a rigidly moved part, the local
   surface's motion for a skinned one. pos: flat xyz; idx: triangle vertex indices; p, n: [x,y,z]. */
function triFrame(pos, idx, f) {
  var a = 3 * idx[3 * f], b = 3 * idx[3 * f + 1], c = 3 * idx[3 * f + 2];
  var A = [pos[a], pos[a + 1], pos[a + 2]], B = [pos[b], pos[b + 1], pos[b + 2]], C = [pos[c], pos[c + 1], pos[c + 2]];
  var e1 = [B[0] - A[0], B[1] - A[1], B[2] - A[2]], e2 = [C[0] - A[0], C[1] - A[1], C[2] - A[2]];
  var n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]], l = Math.hypot(n[0], n[1], n[2]), l1 = Math.hypot(e1[0], e1[1], e1[2]);
  if (!(l > 1e-12) || !(l1 > 1e-12)) return null;
  n = [n[0] / l, n[1] / l, n[2] / l];
  var t = [e1[0] / l1, e1[1] / l1, e1[2] / l1], s = [n[1] * t[2] - n[2] * t[1], n[2] * t[0] - n[0] * t[2], n[0] * t[1] - n[1] * t[0]];
  return {A: A, B: B, C: C, e1: e1, e2: e2, n: n, t: t, s: s};
}
function poseAnchor(pos, idx, p, nrm) {
  var best = Infinity, bf = -1, f, nt = idx.length / 3;
  for (f = 0; f < nt; f++) {
    var a = 3 * idx[3 * f], b = 3 * idx[3 * f + 1], c = 3 * idx[3 * f + 2];
    var q = closestPtTri(p, [pos[a], pos[a + 1], pos[a + 2]], [pos[b], pos[b + 1], pos[b + 2]], [pos[c], pos[c + 1], pos[c + 2]]);
    var d = (p[0] - q[0]) * (p[0] - q[0]) + (p[1] - q[1]) * (p[1] - q[1]) + (p[2] - q[2]) * (p[2] - q[2]);
    if (d < best && triFrame(pos, idx, f)) { best = d; bf = f; }
  }
  if (bf < 0) return null;
  var F = triFrame(pos, idx, bf), w = [p[0] - F.A[0], p[1] - F.A[1], p[2] - F.A[2]];
  var h = w[0] * F.n[0] + w[1] * F.n[1] + w[2] * F.n[2];
  var d11 = F.e1[0] * F.e1[0] + F.e1[1] * F.e1[1] + F.e1[2] * F.e1[2], d12 = F.e1[0] * F.e2[0] + F.e1[1] * F.e2[1] + F.e1[2] * F.e2[2], d22 = F.e2[0] * F.e2[0] + F.e2[1] * F.e2[1] + F.e2[2] * F.e2[2];
  var q1 = w[0] * F.e1[0] + w[1] * F.e1[1] + w[2] * F.e1[2], q2 = w[0] * F.e2[0] + w[1] * F.e2[1] + w[2] * F.e2[2], den = d11 * d22 - d12 * d12;
  var u = (d22 * q1 - d12 * q2) / den, v = (d11 * q2 - d12 * q1) / den;
  var nl = nrm ? [nrm[0] * F.t[0] + nrm[1] * F.t[1] + nrm[2] * F.t[2], nrm[0] * F.n[0] + nrm[1] * F.n[1] + nrm[2] * F.n[2], nrm[0] * F.s[0] + nrm[1] * F.s[1] + nrm[2] * F.s[2]] : null;
  return {f: bf, w: [1 - u - v, u, v], h: h, nl: nl, d: Math.sqrt(best)};
}
function poseAnchorPlace(pos, idx, anc) {
  var F = triFrame(pos, idx, anc.f); if (!F) return null;
  var w = anc.w, p = [0, 1, 2].map(function (k) { return w[0] * F.A[k] + w[1] * F.B[k] + w[2] * F.C[k] + anc.h * F.n[k]; });
  var n = anc.nl ? [0, 1, 2].map(function (k) { return anc.nl[0] * F.t[k] + anc.nl[1] * F.n[k] + anc.nl[2] * F.s[k]; }) : null;
  return {p: p, n: n};
}
/* distance between segments p1-q1 and p2-q2 (Ericson 5.1.9, closest points of two segments) */
function segSegDist(p1, q1, p2, q2) {
  var d1 = [q1[0] - p1[0], q1[1] - p1[1], q1[2] - p1[2]], d2 = [q2[0] - p2[0], q2[1] - p2[1], q2[2] - p2[2]], r = [p1[0] - p2[0], p1[1] - p2[1], p1[2] - p2[2]];
  var a = d1[0] * d1[0] + d1[1] * d1[1] + d1[2] * d1[2], e = d2[0] * d2[0] + d2[1] * d2[1] + d2[2] * d2[2], f = d2[0] * r[0] + d2[1] * r[1] + d2[2] * r[2];
  var EPSQ = 1e-12, s, t;
  if (a <= EPSQ && e <= EPSQ) return Math.hypot(r[0], r[1], r[2]);
  if (a <= EPSQ) { s = 0; t = f / e; t = t < 0 ? 0 : (t > 1 ? 1 : t); }
  else {
    var cc = d1[0] * r[0] + d1[1] * r[1] + d1[2] * r[2];
    if (e <= EPSQ) { t = 0; s = -cc / a; s = s < 0 ? 0 : (s > 1 ? 1 : s); }
    else {
      var b = d1[0] * d2[0] + d1[1] * d2[1] + d1[2] * d2[2], denom = a * e - b * b;
      s = denom !== 0 ? (b * f - cc * e) / denom : 0; s = s < 0 ? 0 : (s > 1 ? 1 : s);
      t = (b * s + f) / e;
      if (t < 0) { t = 0; s = -cc / a; s = s < 0 ? 0 : (s > 1 ? 1 : s); }
      else if (t > 1) { t = 1; s = (b - cc) / a; s = s < 0 ? 0 : (s > 1 ? 1 : s); }
    }
  }
  var c1 = [p1[0] + d1[0] * s, p1[1] + d1[1] * s, p1[2] + d1[2] * s], c2 = [p2[0] + d2[0] * t, p2[1] + d2[1] * t, p2[2] + d2[2] * t];
  return Math.hypot(c1[0] - c2[0], c1[1] - c2[1], c1[2] - c2[2]);
}
/* Moller-Trumbore, two-sided, segment form: does the segment A-B (A + s(B-A), s in [0,1]) cross triangle abc? */
function segCrossesTri(A, B, a, b, c) {
  var dx = B[0] - A[0], dy = B[1] - A[1], dz = B[2] - A[2];
  var e1x = b[0] - a[0], e1y = b[1] - a[1], e1z = b[2] - a[2], e2x = c[0] - a[0], e2y = c[1] - a[1], e2z = c[2] - a[2];
  var px = dy * e2z - dz * e2y, py = dz * e2x - dx * e2z, pz = dx * e2y - dy * e2x, det = e1x * px + e1y * py + e1z * pz;
  if (Math.abs(det) < 1e-12) return false;
  var inv = 1 / det, tx = A[0] - a[0], ty = A[1] - a[1], tz = A[2] - a[2], u = (tx * px + ty * py + tz * pz) * inv;
  if (u < 0 || u > 1) return false;
  var qx = ty * e1z - tz * e1y, qy = tz * e1x - tx * e1z, qz = tx * e1y - ty * e1x, v = (dx * qx + dy * qy + dz * qz) * inv;
  if (v < 0 || u + v > 1) return false;
  var s = (e2x * qx + e2y * qy + e2z * qz) * inv;
  return s >= 0 && s <= 1;
}
/* minimum distance between segment A-B and triangle abc (0 when they cross). Exact: the closest pair lies at an endpoint of
   the segment against the triangle's face, or between the segment and one of the triangle's edges. A degenerate segment
   (A == B) is the point case. */
function segTriDist(A, B, a, b, c) {
  var L2 = (B[0] - A[0]) * (B[0] - A[0]) + (B[1] - A[1]) * (B[1] - A[1]) + (B[2] - A[2]) * (B[2] - A[2]);
  if (L2 < 1e-18) return pointTriDist(A, a, b, c);
  if (segCrossesTri(A, B, a, b, c)) return 0;
  var d = Math.min(pointTriDist(A, a, b, c), pointTriDist(B, a, b, c));
  d = Math.min(d, segSegDist(A, B, a, b), segSegDist(A, B, b, c), segSegDist(A, B, c, a));
  return d;
}
/* minimum distance from segment A-B to an indexed triangle mesh (pos: flat xyz, idx: triangle vertex indices), searched only
   below `bound` (mm): {d, tri} with d = Infinity when every triangle is farther than `bound`. Each triangle is first pruned by
   a cheap lower bound (segment -> first vertex distance minus the triangle's longest edge from it) before the exact test. */
function meshSegDist(pos, idx, A, B, bound) {
  var dx = B[0] - A[0], dy = B[1] - A[1], dz = B[2] - A[2], L = Math.sqrt(dx * dx + dy * dy + dz * dz), best = bound, tri = -1;
  var u = L > 1e-9 ? [dx / L, dy / L, dz / L] : [0, 0, 0], a = [0, 0, 0], b = [0, 0, 0], c = [0, 0, 0];
  for (var f = 0; f < idx.length; f += 3) {
    var i0 = idx[f] * 3, i1 = idx[f + 1] * 3, i2 = idx[f + 2] * 3;
    a[0] = pos[i0]; a[1] = pos[i0 + 1]; a[2] = pos[i0 + 2]; b[0] = pos[i1]; b[1] = pos[i1 + 1]; b[2] = pos[i1 + 2]; c[0] = pos[i2]; c[1] = pos[i2 + 1]; c[2] = pos[i2 + 2];
    var da = segPointDist(A, u, L, a[0], a[1], a[2]);
    var reach = Math.max(Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]), Math.hypot(c[0] - a[0], c[1] - a[1], c[2] - a[2]));
    if (da - reach >= best) continue;
    var d = segTriDist(A, B, a, b, c);
    if (d < best) { best = d; tri = f / 3; if (best <= 0) break; }
  }
  return {d: tri >= 0 ? best : Infinity, tri: tri};
}
/* Q268 (item 3): rank entry candidates -- larger clearance first; candidates whose clearance is within `tie` mm of the best are
   then ordered by path length (shorter first). A simple, stated heuristic, not an optimiser. */
function rankCandidates(cands, tie) {
  var out = cands.slice().sort(function (x, y) { return y.minD - x.minD; });
  if (!out.length) return out;
  var top = out[0].minD, group = out.filter(function (c) { return c.minD >= top - tie; }), rest = out.slice(group.length);
  group.sort(function (x, y) { return x.L - y.L; });
  return group.concat(rest);
}
/* directions within a cone of half-angle `half` (radians) around unit u, roughly uniform in solid angle (spiral) */
function coneDirs(u, half, n) {
  var B = perpBasis(u), e1 = B[0], e2 = B[1], out = [u.slice()], ga = Math.PI * (3 - Math.sqrt(5)), cmin = Math.cos(half);
  for (var j = 0; j < n; j++) {
    var ct = 1 - (1 - cmin) * (j + 0.5) / n, st = Math.sqrt(Math.max(0, 1 - ct * ct)), ph = ga * j;
    out.push([u[0] * ct + (e1[0] * Math.cos(ph) + e2[0] * Math.sin(ph)) * st, u[1] * ct + (e1[1] * Math.cos(ph) + e2[1] * Math.sin(ph)) * st,
              u[2] * ct + (e1[2] * Math.cos(ph) + e2[2] * Math.sin(ph)) * st]);
  }
  return out;
}

/* ===================================================================== */
/* Q367 pure helpers (also exported for the node tests): the PLANE locus between two structures, the closest point on a mesh,  */
/* and a structure's size class from its calibre.                                                                                */
/* ===================================================================== */
/* nearest point of a mesh to p: {q, f, d} (brute force; a nerve / bursa / capsule mesh is small) */
function closestOnMesh(pos, idx, p) {
  var best = Infinity, bq = null, bf = -1, a = [0, 0, 0], b = [0, 0, 0], c = [0, 0, 0];
  for (var f = 0; f < idx.length; f += 3) {
    var i0 = idx[f] * 3, i1 = idx[f + 1] * 3, i2 = idx[f + 2] * 3;
    a[0] = pos[i0]; a[1] = pos[i0 + 1]; a[2] = pos[i0 + 2]; b[0] = pos[i1]; b[1] = pos[i1 + 1]; b[2] = pos[i1 + 2]; c[0] = pos[i2]; c[1] = pos[i2 + 1]; c[2] = pos[i2 + 2];
    var q = closestPtTri(p, a, b, c), d = (p[0] - q[0]) * (p[0] - q[0]) + (p[1] - q[1]) * (p[1] - q[1]) + (p[2] - q[2]) * (p[2] - q[2]);
    if (d < best) { best = d; bq = q; bf = f / 3; }
  }
  return {q: bq, f: bf, d: Math.sqrt(best)};
}
function meshBox(pos) {
  var lo = [1e30, 1e30, 1e30], hi = [-1e30, -1e30, -1e30];
  for (var k = 0; k < pos.length; k += 3) for (var c = 0; c < 3; c++) { var v = pos[k + c]; if (v < lo[c]) lo[c] = v; if (v > hi[c]) hi[c] = v; }
  return [lo, hi];
}
/* a uniform cell hash of a mesh's triangles, for "nearest surface point within maxD" queries */
function TriHash(pos, idx, cell) {
  var B = meshBox(pos), m = new Map(), lo = B[0];
  this.pos = pos; this.idx = idx; this.c = cell; this.lo = lo; this.box = B; this.m = m; this.stamp = new Int32Array(idx.length / 3); this.st = 0;
  for (var f = 0; f < idx.length; f += 3) {
    var mn = [1e30, 1e30, 1e30], mx = [-1e30, -1e30, -1e30];
    for (var j = 0; j < 3; j++) { var o = idx[f + j] * 3; for (var k = 0; k < 3; k++) { var v = pos[o + k]; if (v < mn[k]) mn[k] = v; if (v > mx[k]) mx[k] = v; } }
    var a0 = Math.floor((mn[0] - lo[0]) / cell), a1 = Math.floor((mx[0] - lo[0]) / cell), b0 = Math.floor((mn[1] - lo[1]) / cell), b1 = Math.floor((mx[1] - lo[1]) / cell);
    var c0 = Math.floor((mn[2] - lo[2]) / cell), c1 = Math.floor((mx[2] - lo[2]) / cell);
    for (var x = a0; x <= a1; x++) for (var y = b0; y <= b1; y++) for (var z = c0; z <= c1; z++) {
      var key = (x * 4096 + y) * 4096 + z, L = m.get(key); if (!L) m.set(key, L = []); L.push(f / 3);
    }
  }
}
TriHash.prototype.near = function (p, maxD) {   // -> {q, d} or null (nothing within maxD)
  var c = this.c, lo = this.lo, P = this.pos, I = this.idx, best = maxD * maxD, bq = null, st = ++this.st, S = this.stamp;
  var a0 = Math.floor((p[0] - maxD - lo[0]) / c), a1 = Math.floor((p[0] + maxD - lo[0]) / c), b0 = Math.floor((p[1] - maxD - lo[1]) / c), b1 = Math.floor((p[1] + maxD - lo[1]) / c);
  var c0 = Math.floor((p[2] - maxD - lo[2]) / c), c1 = Math.floor((p[2] + maxD - lo[2]) / c);
  for (var x = a0; x <= a1; x++) for (var y = b0; y <= b1; y++) for (var z = c0; z <= c1; z++) {
    var L = this.m.get((x * 4096 + y) * 4096 + z); if (!L) continue;
    for (var k = 0; k < L.length; k++) {
      var t = L[k]; if (S[t] === st) continue; S[t] = st;
      var i0 = I[3 * t] * 3, i1 = I[3 * t + 1] * 3, i2 = I[3 * t + 2] * 3;
      var q = closestPtTri(p, [P[i0], P[i0 + 1], P[i0 + 2]], [P[i1], P[i1 + 1], P[i1 + 2]], [P[i2], P[i2 + 1], P[i2 + 2]]);
      var d = (p[0] - q[0]) * (p[0] - q[0]) + (p[1] - q[1]) * (p[1] - q[1]) + (p[2] - q[2]) * (p[2] - q[2]);
      if (d < best) { best = d; bq = q; }
    }
  }
  return bq ? {q: bq, d: Math.sqrt(best)} : null;
};
/* Q367 PLANE (the interface between two adjacent structures, for a plane block): every vertex of A (at most maxV, evenly
   strided) whose nearest point on B's surface lies within `gap` mm, and the same from B to A; each such closest pair gives
   the MIDPOINT between the two surfaces, kept only when it really is midway: its own distances to A and to B (each the nearest
   surface point) differ by <= 0.5 mm (a midpoint of one pair can lie nearer another part of either surface where they curve or
   touch). The patch = those midpoints (thinned to one per 1 mm voxel, the smaller gap kept);
   it is empty when the two structures never come within `gap` of each other. keep(p) optionally filters (the joint-space
   use keeps only points inside the capsule's box). Returns {pts: [{m, g}], minGap}. */
function planeLocus(posA, idxA, posB, idxB, gap, maxV, keep) {
  maxV = maxV || 3000;
  var cell = Math.max(gap, 3), hA = new TriHash(posA, idxA, cell), hB = new TriHash(posB, idxB, cell), vox = new Map(), minGap = Infinity;
  function side(pos, other) {
    var n = pos.length / 3, step = Math.max(1, Math.ceil(n / maxV)), lo = other.box[0], hi = other.box[1];
    for (var v = 0; v < n; v += step) {
      var p = [pos[3 * v], pos[3 * v + 1], pos[3 * v + 2]];
      if (p[0] < lo[0] - gap || p[1] < lo[1] - gap || p[2] < lo[2] - gap || p[0] > hi[0] + gap || p[1] > hi[1] + gap || p[2] > hi[2] + gap) continue;
      var r = other.near(p, gap); if (!r) continue;
      var m = [(p[0] + r.q[0]) / 2, (p[1] + r.q[1]) / 2, (p[2] + r.q[2]) / 2];
      if (keep && !keep(m)) continue;
      var ma = hA.near(m, gap), mb = hB.near(m, gap);
      if (!ma || !mb || Math.abs(ma.d - mb.d) > 0.5) continue;
      if (r.d < minGap) minGap = r.d;
      var key = Math.round(m[0]) + "," + Math.round(m[1]) + "," + Math.round(m[2]), o = vox.get(key);
      if (!o || r.d < o.g) vox.set(key, {m: m, g: r.d});
    }
  }
  side(posA, hB); side(posB, hA);
  return {pts: Array.from(vox.values()), minGap: minGap};
}
/* Q367 size class from a calibre: a named main trunk (p) is large whatever its mesh calibre; else by the two thresholds
   [large >=, medium >=] in mm; no diameter -> null (no class: no rule applies, said so on the panel) */
function sizeClass(d, p, thr) {
  if (p) return "L";
  if (d == null || !isFinite(d)) return null;
  return d >= thr[0] ? "L" : (d >= thr[1] ? "M" : "S");
}

/* ===================================================================== */
/* Q381 pure helpers (node-tested, tests/test_q381_plan.py): the straight path against a mesh, and a point INSIDE a mesh.         */
/* ===================================================================== */
/* every crossing of the segment A-B with an indexed triangle mesh, as [{t (mm from A), f}] sorted by t. Two-sided Moller-Trumbore on
   the segment's own length, so a tip resting ON the surface is reported at t = L (the caller decides what a touch means); a
   crossing through a shared edge / vertex comes once per triangle (the caller merges equal t). */
function segMeshHits(pos, idx, A, B) {
  var dx = B[0] - A[0], dy = B[1] - A[1], dz = B[2] - A[2], L = Math.sqrt(dx * dx + dy * dy + dz * dz), out = [];
  if (!(L > 1e-9)) return out;
  var d = [dx / L, dy / L, dz / L], e = 1e-6;
  var lx = Math.min(A[0], B[0]) - e, hx = Math.max(A[0], B[0]) + e, ly = Math.min(A[1], B[1]) - e, hy = Math.max(A[1], B[1]) + e, lz = Math.min(A[2], B[2]) - e, hz = Math.max(A[2], B[2]) + e;
  for (var f = 0; f < idx.length; f += 3) {
    var a = idx[f] * 3, b = idx[f + 1] * 3, c = idx[f + 2] * 3;
    var ax = pos[a], bx = pos[b], cx = pos[c]; if ((ax < lx && bx < lx && cx < lx) || (ax > hx && bx > hx && cx > hx)) continue;
    var ay = pos[a + 1], by = pos[b + 1], cy = pos[c + 1]; if ((ay < ly && by < ly && cy < ly) || (ay > hy && by > hy && cy > hy)) continue;
    var az = pos[a + 2], bz = pos[b + 2], cz = pos[c + 2]; if ((az < lz && bz < lz && cz < lz) || (az > hz && bz > hz && cz > hz)) continue;
    var t = rayTri(A, d, ax, ay, az, bx, by, bz, cx, cy, cz);
    if (t >= -1e-9 && t <= L + 1e-9) out.push({t: t < 0 ? 0 : (t > L ? L : t), f: f / 3});
  }
  out.sort(function (x, y) { return x.t - y.t; });
  return out;
}
var SKEW_DIR = [0.57735, 0.57736, 0.57734];
/* is p inside the closed mesh? parity of the crossings along one fixed skew direction (the tool's own inside test) */
function meshInside(pos, idx, p) {
  var n = 0;
  for (var f = 0; f < idx.length; f += 3) {
    var a = idx[f] * 3, b = idx[f + 1] * 3, c = idx[f + 2] * 3;
    if (rayTri(p, SKEW_DIR, pos[a], pos[a + 1], pos[a + 2], pos[b], pos[b + 1], pos[b + 2], pos[c], pos[c + 1], pos[c + 2]) >= 1e-5) n++;
  }
  return n % 2 === 1;
}
/* A point INSIDE a structure, for "the centre of the structure". The mean of the vertices is not such a point: a curved muscle, or a
   belly with a long tendon, has it outside its own mesh (measured on the Base·Male page, Q381: 73 of 434 muscle / tendon meshes by
   more than 5 mm, 47 of them inside a bone -- tibialis posterior's lay 19 mm outside it, inside the tibia). Instead:
     1. c0 = the centre of VOLUME (signed tetrahedra; the area centroid for a mesh that is not a closed solid);
     2. candidates = the MID-THICKNESS points: from up to K faces (evenly strided) a ray along the inward normal to the opposite
        wall, the middle of that chord;
     3. each of the `top` thickest is kept only if it tests inside the mesh (and is not rejected by opt.reject, the tool's "inside a
        bone" test), with r = its exact distance to the surface (the inscribed radius there);
     4. of those within `keep` (80 %) of the largest r, the one nearest c0.
   So: the middle of the structure where it is (nearly) thickest, as near its centre of volume as that allows. Deterministic.
   Returns {p, r, inside, c0}; inside = false (p = the surface point nearest c0, r = 0) when no interior point was found (open mesh). */
function meshCentre(pos, idx, opt) {
  opt = opt || {};
  var K = opt.K || 400, TOP = opt.top || 40, KEEP = opt.keep || 0.8, nF = idx.length / 3, B = meshBox(pos), o = [(B[0][0] + B[1][0]) / 2, (B[0][1] + B[1][1]) / 2, (B[0][2] + B[1][2]) / 2];
  var vol = 0, area = 0, cv = [0, 0, 0], ca = [0, 0, 0], f, k;
  function tri(ff) {
    var a = idx[3 * ff] * 3, b = idx[3 * ff + 1] * 3, c = idx[3 * ff + 2] * 3;
    return [[pos[a], pos[a + 1], pos[a + 2]], [pos[b], pos[b + 1], pos[b + 2]], [pos[c], pos[c + 1], pos[c + 2]]];
  }
  for (f = 0; f < nF; f++) {
    var T = tri(f), a = [T[0][0] - o[0], T[0][1] - o[1], T[0][2] - o[2]], b = [T[1][0] - o[0], T[1][1] - o[1], T[1][2] - o[2]], c = [T[2][0] - o[0], T[2][1] - o[1], T[2][2] - o[2]];
    var bc = [b[1] * c[2] - b[2] * c[1], b[2] * c[0] - b[0] * c[2], b[0] * c[1] - b[1] * c[0]], v = (a[0] * bc[0] + a[1] * bc[1] + a[2] * bc[2]) / 6;
    var e1 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], e2 = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    var ar = Math.hypot(e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]) / 2;
    vol += v; area += ar;
    for (k = 0; k < 3; k++) { var s = a[k] + b[k] + c[k]; cv[k] += s / 4 * v; ca[k] += s / 3 * ar; }
  }
  var solid = Math.abs(vol) > 1e-6 && Math.abs(vol) >= 0.02 * area, sgn = vol >= 0 ? 1 : -1;
  var c0 = solid ? [o[0] + cv[0] / vol, o[1] + cv[1] / vol, o[2] + cv[2] / vol] : (area > 0 ? [o[0] + ca[0] / area, o[1] + ca[1] / area, o[2] + ca[2] / area] : o.slice());
  var cands = [], n = Math.min(K, nF);
  for (k = 0; k < n; k++) {
    var T2 = tri(Math.floor(k * nF / n)), u = [T2[1][0] - T2[0][0], T2[1][1] - T2[0][1], T2[1][2] - T2[0][2]], w = [T2[2][0] - T2[0][0], T2[2][1] - T2[0][1], T2[2][2] - T2[0][2]];
    var nn = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]], l = Math.hypot(nn[0], nn[1], nn[2]);
    if (!(l > 1e-12)) continue;
    var d = [-nn[0] / l * sgn, -nn[1] / l * sgn, -nn[2] / l * sgn];
    var g = [(T2[0][0] + T2[1][0] + T2[2][0]) / 3 + d[0] * 1e-3, (T2[0][1] + T2[1][1] + T2[2][1]) / 3 + d[1] * 1e-3, (T2[0][2] + T2[1][2] + T2[2][2]) / 3 + d[2] * 1e-3], t1 = Infinity;
    for (f = 0; f < idx.length; f += 3) {
      var i0 = idx[f] * 3, i1 = idx[f + 1] * 3, i2 = idx[f + 2] * 3;
      var t = rayTri(g, d, pos[i0], pos[i0 + 1], pos[i0 + 2], pos[i1], pos[i1 + 1], pos[i1 + 2], pos[i2], pos[i2 + 1], pos[i2 + 2]);
      if (t >= 1e-4 && t < t1) t1 = t;
    }
    if (t1 < Infinity) cands.push({h: t1 / 2, m: [g[0] + d[0] * t1 / 2, g[1] + d[1] * t1 / 2, g[2] + d[2] * t1 / 2]});
  }
  cands.sort(function (x, y) { return y.h - x.h; });
  var best = [], rmax = 0;
  for (k = 0; k < cands.length && k < TOP; k++) {
    var m = cands[k].m;
    if (!meshInside(pos, idx, m) || (opt.reject && opt.reject(m))) continue;
    var r = closestOnMesh(pos, idx, m).d;
    best.push({m: m, r: r, d0: Math.hypot(m[0] - c0[0], m[1] - c0[1], m[2] - c0[2])});
    if (r > rmax) rmax = r;
  }
  if (!best.length) { var q = closestOnMesh(pos, idx, c0); return {p: q.q ? q.q : c0, r: 0, inside: false, c0: c0}; }
  best = best.filter(function (x) { return x.r >= KEEP * rmax; }).sort(function (x, y) { return x.d0 - y.d0; });
  return {p: best[0].m, r: best[0].r, inside: true, c0: c0};
}

var PURE = {segMeshHits: segMeshHits, meshInside: meshInside, meshCentre: meshCentre,   // Q381
            RISK_TABLE: RISK_TABLE, HALO_DEFAULTS: HALO_DEFAULTS, TOUCH_MM: TOUCH_MM, classify: classify,
            calibreFactor: calibreFactor, haloRadius: haloRadius, scorePath: scorePath, fibonacciSphere: fibonacciSphere,
            closestPtTri: closestPtTri, pointTriDist: pointTriDist, segSegDist: segSegDist, segCrossesTri: segCrossesTri, segTriDist: segTriDist,
            meshSegDist: meshSegDist, rankCandidates: rankCandidates, coneDirs: coneDirs, poseAnchor: poseAnchor, poseAnchorPlace: poseAnchorPlace,
            closestOnMesh: closestOnMesh, planeLocus: planeLocus, sizeClass: sizeClass};   // Q367
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
  this.halosNow = function () { return Object.keys(halos).map(function (k) { return {i: +k, r: halos[k].u.value, alpha: halos[k].mesh.material.opacity}; }); };   // Q367
  this.setGhosts = function () {}; this.ghostsNow = function () { return []; };   // Q381: the silhouette pass exists on the WebGL engine only
}

function GLOverlay(api) {
  var gl = api.webgl.gl, items = {}, halos = [], ghosts = [], U = {};
  var VS = "attribute vec3 aPos;attribute vec3 aNrm;uniform mat4 uMVP;uniform float uInflate;varying vec3 vN;varying vec3 vP;" +
           "void main(){vec3 p=aPos+normalize(aNrm)*uInflate;vN=aNrm;vP=p;gl_Position=uMVP*vec4(p,1.0);}";
  var FS = "#ifdef GL_FRAGMENT_PRECISION_HIGH\nprecision highp float;\n#else\nprecision mediump float;\n#endif\n" +
    "varying vec3 vN;varying vec3 vP;uniform vec3 uColor;uniform vec3 uEye;uniform float uAlpha;uniform float uLit;" +
    "uniform float uShin;uniform float uEmis;uniform vec4 uClip;uniform vec4 uClip2;uniform float uClipOn;uniform float uRim;" +
    "void main(){if(uClipOn>0.5&&(dot(vP,uClip.xyz)+uClip.w>0.0||dot(vP,uClip2.xyz)+uClip2.w>0.0))discard;" +
    " vec3 n=normalize(vN);vec3 v=normalize(uEye-vP);if(dot(n,v)<0.0)n=-n;" +
    " vec3 l=normalize(v+vec3(0.3,0.55,0.2));float d=max(dot(n,l),0.0);" +
    " float s=pow(max(dot(n,normalize(l+v)),0.0),uShin);" +
    " vec3 c=uLit>0.5?uColor*(0.30+0.72*d+uEmis)+vec3(s*0.6):uColor;" +
    " float al=uAlpha;if(uRim>0.5){float e=1.0-clamp(dot(n,v),0.0,1.0);al=uAlpha*(0.10+0.90*e*e);}" +   // Q381: a silhouette -- strong at the rim, faint face-on
    " gl_FragColor=vec4(c,al);}";
  function sh(t, s) { var o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o);
    if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; }
  var prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
  gl.bindAttribLocation(prog, 0, "aPos"); gl.bindAttribLocation(prog, 1, "aNrm"); gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
  ["uMVP", "uInflate", "uColor", "uEye", "uAlpha", "uLit", "uShin", "uEmis", "uClip", "uClip2", "uClipOn", "uRim"].forEach(function (n) { U[n] = gl.getUniformLocation(prog, n); });
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
  this.halosNow = function () { return halos.map(function (h) { return {i: h.i, r: h.r, alpha: h.alpha}; }); };   // Q367: what the halo pass draws (tests)
  /* Q381: structures whose own (posed) surface is drawn THROUGH everything as a rim-lit silhouette (the tip's target structure) */
  this.setGhosts = function (list) { ghosts = (list || []).map(function (h) { return {i: h.i, rgb: hexRgb(h.color), alpha: h.alpha || 0.3}; }); };
  this.ghostsNow = function () { return ghosts.map(function (h) { return {i: h.i, alpha: h.alpha}; }); };
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
    if (!all.length && !halos.length && !ghosts.length) return;
    gl.useProgram(prog);
    gl.uniform1f(U.uRim, 0);
    gl.uniformMatrix4fv(U.uMVP, false, ctx.mvp); gl.uniform3f(U.uEye, ctx.eye[0], ctx.eye[1], ctx.eye[2]);
    gl.uniform1f(U.uInflate, 0); gl.uniform1f(U.uClipOn, 0);
    gl.enableVertexAttribArray(0); gl.enableVertexAttribArray(1); gl.disable(gl.CULL_FACE);
    gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
    all.filter(function (b) { return b.spec.pass === "opaque"; }).forEach(drawItem);
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false);
    if (halos.length) {
      if (ctx.clip) {
        gl.uniform4f(U.uClip, ctx.clip[0], ctx.clip[1], ctx.clip[2], ctx.clip[3]);
        var c2 = ctx.clip2;   /* Q218: the far face of a cut slice (optional; absent = no second plane) */
        gl.uniform4f(U.uClip2, c2 ? c2[0] : 0, c2 ? c2[1] : 0, c2 ? c2[2] : 0, c2 ? c2[3] : -1);
        gl.uniform1f(U.uClipOn, 1);
      }
      halos.forEach(function (h) {
        style(h.rgb, {alpha: h.alpha, shin: 8, emis: 0.45}); gl.uniform1f(U.uInflate, h.r);
        api.webgl.drawStructure(h.i);
      });
      gl.uniform1f(U.uInflate, 0); gl.uniform1f(U.uClipOn, 0);
    }
    all.filter(function (b) { return b.spec.pass === "trans"; }).forEach(drawItem);
    gl.disable(gl.DEPTH_TEST);
    if (ghosts.length) {
      gl.uniform1f(U.uRim, 1);
      ghosts.forEach(function (h) { style(h.rgb, {alpha: h.alpha, shin: 8, emis: 0.6}); api.webgl.drawStructure(h.i); });
      gl.uniform1f(U.uRim, 0);
    }
    all.filter(function (b) { return b.spec.pass === "xray"; }).forEach(drawItem);
    gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
  });
}

/* ===================================================================== */
/* panel styles (scoped .ncl-*, host colour tokens with fallbacks)          */
/* ===================================================================== */
var CSS = [
".ncl{--ncl-acc:var(--accent,#1d7c99);--ncl-line:var(--line,rgba(22,32,42,.16));--ncl-mut:var(--muted,var(--ink-dim,#49555f));",
"  --ncl-bg:var(--panel,#fff);--ncl-sunk:var(--sunk,var(--panel-2,#eef2f5));font-size:12px;line-height:1.45;color:var(--ink,#16202a)}",
".ncl{padding:11px 13px;background:var(--ncl-bg);border-bottom:1px solid var(--ncl-line)}",
".ncl.ncl-float{position:fixed;top:calc(3.3rem + env(safe-area-inset-top,0px));right:.9rem;width:340px;max-height:calc(100vh - 8rem);",
/* Q264: overscroll-behavior:contain on this own scroll container -- a touch-drag that scrolls this panel to its own
   top/bottom boundary and keeps going must not chain into the page/canvas beneath it (root cause of a mobile scroll
   being misread as "cancel the tool"; see PROJECT_STATE.md Q264). Stopped at this layer so it applies with or without
   a page-root guard. */
"  overflow-y:auto;overscroll-behavior:contain;z-index:26;border:1px solid var(--ncl-line);border-radius:12px;box-shadow:0 10px 34px rgba(22,32,42,.18)}",
"@media (max-width:900px){.ncl.ncl-float{left:.6rem;right:.6rem;width:auto;top:auto;bottom:calc(3.9rem + env(safe-area-inset-bottom,0px));max-height:40vh}}",   /* Q344: capped at 40 % of the screen, scrolls inside */
".ncl.ncl-stage{position:absolute;left:12px;top:12px;width:330px;max-height:calc(100% - 150px);overflow-y:auto;overscroll-behavior:contain;z-index:5;",
"  border:1px solid var(--ncl-line);border-radius:10px;box-shadow:0 8px 26px rgba(15,21,26,.16)}",
/* a clip-path keeps Chromium from leaving the scrolled-out panel content as a hole over the WebGL canvas */
".ncl.ncl-stage,.ncl.ncl-float{clip-path:inset(0 round 10px)}",
"@media (max-width:760px){.ncl.ncl-stage{left:8px;right:8px;width:auto;top:auto;bottom:8px;max-height:46%}}",
".ncl h3{margin:0;font-size:13px;font-weight:700}",
/* Q344: the shared drag grip (viewer/q305, opted in with data-nmsk-move) sits inside the panel's top-left corner, 26 px (34 px on touch)
   with its ⋮ menu beside it -- the header reserves that room, so the grip covers no title text */
".ncl-head{display:flex;align-items:center;gap:6px;margin-bottom:6px;min-height:28px;padding-left:64px}.ncl-head h3{flex:1;min-width:0}",
"@media (pointer:coarse){.ncl-head{min-height:36px;padding-left:82px}}",
/* Q344: compact state = the header and the current step line only */
".ncl.ncl-collapsed>#needle-status{display:block;margin:0}",
/* Q264: compact/minimize toggle -- same small-chevron idiom + visual language as Q262's per-system .sys-exp drill-down
   toggle in the two page templates (small square button, aria-expanded, highlighted in its non-default state), kept
   self-contained here since this file ships its own scoped CSS independent of either template. */
".ncl-min{flex:0 0 auto;width:26px;min-height:26px;border:1px solid transparent;border-radius:5px;background:none;color:var(--ncl-mut);font-size:11px;cursor:pointer}",
".ncl-min:hover{border-color:var(--ncl-line);background:var(--ncl-sunk)}",
".ncl-min[aria-expanded=false]{background:var(--ncl-sunk);color:var(--ncl-acc)}",
".ncl.ncl-collapsed>*:not(.ncl-head){display:none}",
".ncl button{font:inherit;color:var(--ink,#16202a);cursor:pointer;border:1px solid var(--ncl-line);background:var(--ncl-sunk);border-radius:5px;padding:3px 8px;font-size:12px}",
".ncl button:hover{border-color:var(--ncl-acc)}",
".ncl button[aria-pressed=true]{background:#17667f;color:#fff;border-color:#17667f}",   /* Q344: white on the dark theme's light accent was 2.2:1 */
".ncl-disc{margin:0 0 8px;padding:6px 8px;border-radius:6px;background:#FFF4DC;color:#6B4A00;font-size:11.5px;border:1px solid #F0D48A}",
"@media (prefers-color-scheme:dark){.ncl-disc{background:#2E2410;color:#F3D58B;border-color:#5A4718}}",
".ncl-modes{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:6px}",
".ncl-status{margin:0 0 6px;color:var(--ncl-mut);font-size:12px}",
".ncl-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:4px 0}",
".ncl-row input[type=range]{flex:1;min-width:90px}",
/* Q344: a field states its own colours (the theme's ink on the theme's panel): "inherit" on a fixed white fallback was white on white in the dark theme */
".ncl input[type=number]{width:58px;font:inherit;font-size:12px;padding:2px 3px;border:1px solid var(--line-strong,var(--ncl-line));border-radius:4px;background:var(--ncl-bg);color:var(--ink,#16202a)}",
".ncl input[type=search]{width:100%;font:inherit;padding:4px 6px;border:1px solid var(--line-strong,var(--ncl-line));border-radius:5px;background:var(--ncl-bg);color:var(--ink,#16202a)}",
".ncl input::placeholder{color:var(--ncl-mut);opacity:1}",
".ncl sub,.ncl sup{font-size:10px;line-height:0}",
".ncl dl{display:grid;grid-template-columns:82px minmax(0,1fr);gap:2px 8px;margin:6px 0}",
".ncl dt{color:var(--ncl-mut)}.ncl dd{margin:0;overflow-wrap:anywhere}",
".ncl ol{margin:4px 0 0;padding-left:18px}.ncl ol li{margin:2px 0}",
".ncl .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle}",
".ncl .rng{color:var(--ncl-mut);margin-left:4px;white-space:nowrap}",
".ncl .mono{font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}",
".ncl .cite{font-size:12px;color:var(--ncl-mut);margin:6px 0 0}",
".ncl details{margin-top:8px;border-top:1px solid var(--ncl-line);padding-top:6px}",
".ncl details details{margin-top:6px;border-top:0;padding-top:0}",
".ncl details details>summary{font-weight:400;font-size:11.5px;color:var(--ncl-mut)}",
".ncl summary{cursor:pointer;font-weight:700;font-size:12px}",
".ncl .lg{display:flex;flex-wrap:wrap;gap:4px 10px;margin:4px 0;font-size:11.5px}",
".ncl .formula{font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.6;background:var(--ncl-sunk);padding:5px 6px;border-radius:5px;overflow-wrap:anywhere}",
".ncl .grid2{display:grid;grid-template-columns:repeat(3,auto);gap:3px 8px;align-items:center;font-size:11.5px}",
".ncl .res{max-height:170px;overflow-y:auto;overscroll-behavior:contain;margin-top:4px}",
".ncl .res button{display:block;width:100%;text-align:left;margin:2px 0;padding:4px 6px}",
".ncl .warn{color:var(--risk,#B3400C);font-size:11.5px;margin:4px 0}",
".ncl .pill-g{color:#1E8A4F;font-weight:700}.ncl .pill-a{color:#B07300;font-weight:700}.ncl .pill-r{color:#C23232;font-weight:700}",
/* Q344: the same colours lightened on the dark theme (the light-theme ones are 3:1 on the dark panel) */
"@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .ncl .warn{color:#F2A27C}:root:not([data-theme=light]) .ncl .pill-g{color:#5FD08A}:root:not([data-theme=light]) .ncl .pill-a{color:#E8B04A}:root:not([data-theme=light]) .ncl .pill-r{color:#F58A8A}}",
":root[data-theme=dark] .ncl .warn{color:#F2A27C}:root[data-theme=dark] .ncl .pill-g{color:#5FD08A}:root[data-theme=dark] .ncl .pill-a{color:#E8B04A}:root[data-theme=dark] .ncl .pill-r{color:#F58A8A}",
".ncl .corr-list li{padding-left:4px;border-left:4px solid transparent}.ncl .corr-list li.band-n{border-left-color:#C23232}.ncl .corr-list li.band-m{border-left-color:#B07300}.ncl .corr-list li.band-f{border-left-color:#1E8A4F}",   /* Q268: display bands only */
/* Q347: the injection guide's section in the needle panel */
".ncl .ncl-guide .g-row{margin:4px 0 0;overflow-wrap:anywhere}.ncl .ncl-guide .g-k{color:var(--ncl-mut);font-weight:700}.ncl .ncl-guide .g-sub{color:var(--ncl-mut);overflow-wrap:anywhere}",
".ncl .ncl-guide .g-site{margin-top:4px;padding-top:4px;border-top:1px solid var(--ncl-line)}.ncl .ncl-guide button{margin-top:3px}",
".ncl .ncl-guide .g-badge{display:inline-block;font-size:11px;font-weight:600;color:#5A3E00;background:#FFF1CC;border-radius:999px;padding:0 6px}",
".ncl .ncl-guide .g-rrow{padding-left:4px;border-left:4px solid transparent;margin-top:2px}.ncl .ncl-guide .g-rrow.band-n{border-left-color:#C23232}.ncl .ncl-guide .g-rrow.band-m{border-left-color:#B07300}.ncl .ncl-guide .g-rrow.band-f{border-left-color:#1E8A4F}",
".ncl select{font-size:12px;max-width:150px;background:var(--ncl-bg);color:var(--ink,#16202a);border:1px solid var(--line-strong,var(--ncl-line));border-radius:4px}",
".ncl-tip{position:fixed;z-index:80;pointer-events:none;max-width:280px;padding:5px 8px;border-radius:6px;font-size:11.5px;",
"  background:var(--surface,var(--panel,#fff));color:var(--ink,#16202a);border:1px solid var(--line,#ccd);box-shadow:0 6px 18px rgba(0,0,0,.18)}"
].join("\n");

function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
function f1(v) { return '<span class="mono">' + Number(v).toFixed(1) + "</span>"; }
function xyz1(v) { return '<span class="mono">' + v.map(function (c) { return c.toFixed(1); }).join(", ") + "</span> mm"; }
var EPS = 0.5, MINIV = 0.05, SPACING = 2.5;
/* Q268 defaults. near / far: display band thresholds (mm) for the live distance list -- adjustable in the panel, labelled there
   as display thresholds, NOT clinical guidance (the number is the data; the clinician decides). R: the neighbourhood radius
   (mm) -- a vessel / nerve counts when its bounding box lies within R of the target's bounding box (item 1) or of the needle
   path (items 2-3). 40 mm: a generous limb-scale neighbourhood of the order of a typical injection depth, chosen so that a
   path of the default 60 mm needle length does not silently miss a structure lying just beside it. SUGG_*: item 3's cone
   sampling (half-angle and direction count around the nearest-skin direction) and the clearance tie band (mm) within which
   the shorter path is preferred. */
var CORR_DEFAULTS = {near: 5, far: 15, R: 40};
var SUGG_HALF_DEG = 35, SUGG_N = 48, SUGG_TIE_MM = 1.0, SUGG_SHOW = 2;
var CORR_CLASSES = {artery: 1, vein: 1, nerve: 1};
/* Q268 (item 1) labelled flexion-pattern postures for the Q241 pose rig -- ILLUSTRATIVE typical patterns, not any patient's
   measurement; every angle is clamped by the rig itself to the page's own normal range of motion; joints the page's rig does
   not carry are reported as skipped, never invented. Keys are the rig's own joint ids (without the _r/_l side suffix) and
   dof keys. */
var POSTURES = {
  ul: {label: "Upper limb flexion pattern (illustrative)", joints: {
    shoulder: {abd: -20, rot: 50}, elbow: {flex: 100}, forearm: {sup: -70}, wrist: {flex: 50, dev: -15},
    thumb_cmc: {flex: 15, abd: 0}, thumb_mcp: {flex: 40}, thumb_ip: {flex: 40},
    f2_mcp: {flex: 60}, f2_pip: {flex: 70}, f2_dip: {flex: 40}, f3_mcp: {flex: 60}, f3_pip: {flex: 70}, f3_dip: {flex: 40},
    f4_mcp: {flex: 60}, f4_pip: {flex: 70}, f4_dip: {flex: 40}, f5_mcp: {flex: 60}, f5_pip: {flex: 70}, f5_dip: {flex: 40}}},
  ll: {label: "Lower limb extension + equinovarus pattern (illustrative)", joints: {
    hip: {flex: 15, abd: -15, rot: 15}, knee: {flex: 10}, ankle: {dp: -35}, subtalar: {inv: 25}}}
};
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
  this.savedPts = [];   // Q276: 2+ saved injection points on the same (or any) target -- each an independent {entry,target} snapshot, own marker, own distance readout
  this.dir = {src: "normal", tilt: 0, az: 0, view: null};
  /* Q317: which point on the needle stays put when its direction changes -- "skin", "tip" or "hub" */
  this.pivot = "skin";
  this.len = 60; this.rDisp = 1.0;
  this.risk = {data: null, rcal: {}, on: false, transp: 0.8, saved: null, region: null, safer: null, pathEval: null};
  this.mp = {data: null, points: [], on: false, msg: "loading...", sel: null};
  /* Q268: (1) injection-planning preset, (2) live distance readout to vessels / nerves, (3) suggested entry candidates.
     near / far are DISPLAY band thresholds only (editable in the panel); R is the neighbourhood radius (mm) shared by all three. */
  this.hooks = [];   // Q272: mode-layer change hooks
  this.corr = {near: CORR_DEFAULTS.near, far: CORR_DEFAULTS.far, R: CORR_DEFAULTS.R, halo: true, items: [], n: 0, ms: 0, what: "", timer: 0};
  this.plan = {i: null, msg: "", posture: "rest", side: "r"};
  this.sugg = {cands: [], shown: [], msg: ""};
  this.gcache = new Map(); this.gverts = 0; this.orient = {};
  this.pgeo = {}; this.restBox = {}; this.poseT = 0;   // Q325: posed geometry views, the rest boxes of moved structures
  this.mpS = new Map(); this.mpAnc = new Map();          // Q328: a motor point's structure, and its rest-mesh anchor (taken the first time that structure moves)
  this.guide = {data: null, side: null, bm: {}, hl: null, busy: false, open: {}, msg: {}};   // Q347: the injection guide (private) + the public IZ sidecar
  this.plInit(); this.safeInit();   // Q367: the plan's refinements and the user's safety rules (stored per browser)
  this.blk = null; this.blkIs = null; this.cRest = {}; this.cPose = {}; this.block = null; this.tipF = null;   // Q381: the blocking structures, a structure's inside centre per pose, the path's bone test, the tip's measured facts
  this.buildUI();
  this.loadData();
  this.loadGuide();
  this.loadSafety(); this.pinsInit();   // Q367: the vessel calibre sibling; the tip / entry pins over the canvas
  api.setClickHandler(function (e) { return self.onClick(e); });
  if (global.addEventListener) global.addEventListener("nmsk-pose-rev", function (e) { self.onPose(e && e.detail); });   // Q325
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
TP.restGeom = function (i) {
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
/* Q325: the CURRENT geometry -- the posed vertices once the page's pose rig has moved structure i (the neutral
   window.__poseLive hook, same vertex order as the rest mesh), else the rest mesh. Every measurement (picking, the
   path report, the corridor, the halos) reads this, so a plan made in a posed body is made on the posed body. */
TP.geom = function (i) {
  var g = this.restGeom(i); if (!g) return null;
  var L = typeof global.__poseLive === "function" ? global.__poseLive(i) : null;
  if (!L || L.length !== g.pos.length) return g;
  var pg = this.pgeo[i];
  if (!pg || pg.pos !== L || pg.idx !== g.idx) pg = this.pgeo[i] = {pos: L, idx: g.idx};
  return pg;
};
/* Q325: follow the pose. The page bumps window.__poseRev and fires "nmsk-pose-rev" {ids, rest} after every geometry
   change. Then: (1) the boxes of the moved structures are re-taken from their posed vertices (the rest boxes are
   kept and restored exactly at rest); (2) the entry and the target ride the structure each was placed on (poseAnchor:
   nearest triangle + barycentric coordinates + height, taken on the geometry current when the point was placed), and
   come back to their placed coordinates exactly when the pose returns to the one they were placed in; (3) the needle
   is redrawn at once and the report / corridor / halos follow shortly after (one update per burst of pose events). */
TP.poseBoxes = function (ids) {
  var self = this, live = typeof global.__poseLive === "function" ? global.__poseLive : null;
  ids.forEach(function (i) {
    var r = self.recs[i]; if (!r) return;
    if (!self.restBox[i]) self.restBox[i] = [r.bmin.slice(), r.bmax.slice()];
    var L = live ? live(i) : null;
    if (!L || global.__poseAtRest) { r.bmin = self.restBox[i][0].slice(); r.bmax = self.restBox[i][1].slice(); return; }
    var lo = [1e30, 1e30, 1e30], hi = [-1e30, -1e30, -1e30], k, c;
    for (k = 0; k < L.length; k += 3) for (c = 0; c < 3; c++) { var v = L[k + c]; if (v < lo[c]) lo[c] = v; if (v > hi[c]) hi[c] = v; }
    r.bmin = lo; r.bmax = hi;
  });
};
TP.poseKey = function () { return global.__poseAtRest || !global.__poseRev ? "rest" : "rev" + global.__poseRev; };
TP.anchorPoint = function (pt, s, rest) {    // pt: {p, i, n, ...}; s: the structure to ride (the point's own, else a fallback)
  if (!pt) return;                           // rest (Q328): pt.p is given in REST coordinates -- anchor on the rest mesh, and it is pt.p exactly at rest
  var g = s != null && s >= 0 ? (rest ? this.restGeom(s) : this.geom(s)) : null, a = g ? poseAnchor(g.pos, g.idx, pt.p, pt.n || null) : null;
  pt._anc = a ? {s: s, a: a, p0: pt.p.slice(), n0: pt.n ? pt.n.slice() : null, key: rest ? "rest" : this.poseKey(), src: pt.p} : {s: -1, src: pt.p};
};
TP.ensureAnchors = function () {
  var e = this.entry, t = this.target;
  if (e && (!e._anc || e._anc.src !== e.p)) this.anchorPoint(e, e.i != null ? e.i : (t ? t.i : null));
  if (t && (!t._anc || t._anc.src !== t.p)) this.anchorPoint(t, t.i != null ? t.i : (e ? e.i : null));
};
TP.ridePoint = function (pt) {
  var A = pt && pt._anc; if (!A || A.s < 0) return false;
  var p, n;
  if (this.poseKey() === A.key) { p = A.p0.slice(); n = A.n0 ? A.n0.slice() : null; }          // back in the pose it was placed in: exactly there
  else { var g = this.geom(A.s), q = g ? poseAnchorPlace(g.pos, g.idx, A.a) : null; if (!q) return false; p = q.p; n = q.n; }
  pt.p = p; if (A.n0) pt.n = n; A.src = pt.p;
  return true;
};
TP.onPose = function (det) {
  var ids = (det && det.ids) || [], self = this;
  this.poseBoxes(ids);
  var moved = false;
  if (this.entry) moved = this.ridePoint(this.entry) || moved;
  if (this.target && !(this.mode === "dir" && this.entry)) moved = this.ridePoint(this.target) || moved;   // the direction mode derives its tip from the entry
  var ovMoved = this.poseOverlays(ids);   // Q328
  this.savedReach(ids);                   // Q332
  if (moved) this.drawNeedle();
  if (moved || ovMoved) this.api.redraw();
  clearTimeout(this.poseT);
  this.poseT = setTimeout(function () {
    var re = self.remeasureSaved(), dirty = self.savedDirty || re > 0;   // Q332: the saved points' readouts, once per burst
    if (dirty) { self.savedDirty = false; self.renderSavedPoints(); }
    self.cPose = {};                 // Q381: a structure's inside centre is taken on the mesh as it is now
    self.plCentreFollow();
    if (self.entry || self.target) self.update();
    else { if (self.risk.on) self.refreshHalos(); if (dirty) { self.notify(); self.api.redraw(); } }
    self.poseRerun();   // Q332: shown suggestions / safer pathways are measured again on the posed body
    self.plPoseRefresh();   // Q367: a plane patch is taken again on the posed meshes
  }, 160);
};
/* Q332: a saved point's readouts (nearest vessel / nerve, its distance and band colour; its length rides with the points in
   poseOverlays) are measured again on the current geometry -- the same corridorFor() call, radius and excluded structure the
   save used -- when a pose event moved the point's own structure (poseOverlays sets reDirty) or a vessel / nerve within the
   measurement's reach: one that was within R of it, or whose posed box now lies within R. Once per burst (onPose's timer).
   Back in the pose the point was saved in (rest), the readout is the saved one itself. */
TP.savedReach = function (ids) {
  if (!ids.length || !this.savedPts.length) return;
  var self = this;
  this.savedPts.forEach(function (it) {
    if (it.reDirty || !it.corr) return;
    var A = it.entry ? it.entry.p : it.target.p, B = it.target.p, R = it.R != null ? it.R : self.corr.R, w = it.within || [];
    it.reDirty = ids.some(function (i) {
      var r = self.recs[i];
      return !!r && self.isCorrStruct(i) && r.id !== it.skipId && (w.indexOf(i) >= 0 || boxHitsSegment(r.bmin, r.bmax, A, B, R));
    });
  });
};
TP.remeasureSaved = function () {
  var self = this, key = this.poseKey(), n = 0;
  this.savedPts.forEach(function (it) {
    if (!it.reDirty) return;
    it.reDirty = false; n++;
    if (it.key0 === key && it.corr0) { it.corr = it.corr0; it.within = it.within0; }
    else {
      var res = self.corridorFor(it.entry ? it.entry.p : it.target.p, it.target.p, it.skipId, it.R);
      it.corr = {items: res.items.slice(0, 8), n: res.n}; it.within = res.items.map(function (x) { return x.i; });
    }
    it.corrKey = key;
    self.drawSavedPoint(it);
  });
  return n;
};
TP.poseRerun = function () {
  if (!this.target) return;
  if (this.sugg.cands.length) this.suggest();
  if (this.risk.safer) {
    if (this.risk.on) this.runSafer({n: this.risk.safer.N});
    else { this.risk.safer = null; this.drawSafer(); this.$("ncl-safer-out").innerHTML = ""; }
  }
};
/* Q328: the overlays ride the pose the same way (anchorPoint / ridePoint above -- no second implementation), and only for
   the structures in the event's ids. A saved injection point keeps the anchors its entry / target had when it was saved
   (the structure each was placed on); a motor point -- given in rest coordinates -- rides its muscle, anchored once on the
   REST mesh the first time that muscle moves, and is its given coordinates again, exactly, at rest. The risk halos need
   nothing here: each is the structure's own current mesh inflated along its normals (the page draws its posed buffers),
   and which structures get one is decided on the posed boxes (poseBoxes). Returns whether a shown marker moved. */
TP.poseOverlays = function (ids) {
  if (!ids.length) return false;
  var self = this, mv = {}, shown = false;
  ids.forEach(function (i) { mv[i] = 1; });
  function ride(pt) { return !!(pt && pt._anc && pt._anc.s >= 0 && mv[pt._anc.s] === 1 && self.ridePoint(pt)); }
  this.savedPts.forEach(function (it) {
    var a = ride(it.entry), b = ride(it.target);
    if (!a && !b) return;
    if (it.entry) it.L = dist(it.entry.p, it.target.p);
    it.reDirty = true;   // Q332: its readout is measured again (remeasureSaved)
    self.drawSavedPoint(it); self.savedDirty = shown = true;
  });
  var movedMp = new Set();
  this.mp.points.forEach(function (p) {
    var s = self.mpStructure(p); if (s == null || mv[s] !== 1) return;
    var w = self.mpAnc.get(p);
    if (!w) { w = {p: p.pos.slice(), i: s}; self.anchorPoint(w, s, true); self.mpAnc.set(p, w); }
    if (self.ridePoint(w)) { p.pos = w.p; movedMp.add(p); }
  });
  if (movedMp.size) {
    var hit = function (list) { return list.some(function (p) { return movedMp.has(p); }); };
    if (this.mp.on && hit(this.visibleMpPoints())) { this.refreshMpOverlay(); shown = true; }   // never applyOverride() here (Q281)
    if (this.plan.zone && hit(this.plan.zone.mps)) { this.drawPlanMp(this.plan.zone.mps); shown = true; }
  }
  return shown;
};
/* Q325: the planned path for the probe image (clinical/ultrasound_tool.js "Show in scan"): entry -> target in the
   current (posed) model frame, and the needle's radius. null without a complete plan. */
TP.scanPath = function () {
  if (!this.entry || !this.target) return null;
  return {A: this.entry.p.slice(), B: this.target.p.slice(), r_mm: 0.45, target_id: this.target.i != null ? this.recs[this.target.i].id : null, rev: global.__poseRev | 0};
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
  var best = null, slab = (cut && this.api.cutSlab) ? this.api.cutSlab() : 0;   /* Q218: optional; mm kept behind the plane, 0 = all */
  this.rayAll(i, o, d, 1e-6, 1e9).forEach(function (h) {
    if (best && h.t >= best.t) return;
    var p = addS(o, d, h.t);
    if (cut && dot(cut, p) + cut[3] < -1e-6) return;
    if (slab > 0 && dot(cut, p) + cut[3] > slab + 1e-6) return;
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
/* Q344: the side of a structure as a word for the user ("left" / "right"), never the raw "l" / "r" of the id */
function sideWord(s) { return s === "r" || s === "right" ? "right" : s === "l" || s === "left" ? "left" : ""; }

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
    needle_mm: this.len, exposed_mm: Math.max(0, this.len - L), aim: this.aimAngles(), pivot: this.pivot,
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
  btn.title = "Needle planning: entry/target, direction + length, motor points, risk halos, safer pathways";
  btn.addEventListener("click", function () { self.toggle(); });
  api.toolbar.insertBefore(btn, api.toolbar.lastElementChild);
  this.btn = btn;
  var el = document.createElement("div");
  el.className = "ncl " + (api.panelHost ? "ncl-stage" : "ncl-float"); el.id = "needle-panel"; el.hidden = true;
  el.setAttribute("data-nmsk-move", "the needle panel");   /* Q344: opt in to the shared drag grip + menu (viewer/q305 reads this attribute) */
  var legend = HALO_CLASSES.map(function (k) { return '<span><span class="dot" style="background:' + CLASSES[k].color + '"></span>' + esc(CLASSES[k].label) + "</span>"; }).join("");
  var mults = HALO_CLASSES.map(function (k) {
    return "<span>" + esc(CLASSES[k].label.split(" (")[0].split(" /")[0]) + '</span><input type="number" step="0.05" min="0" max="3" data-mult="' + k + '" value="' + self.P.mult[k] + '"><span></span>';
  }).join("");
  el.innerHTML =
    '<div class="ncl-head"><h3>Needle planning</h3>' +
    '<button type="button" id="ncl-min" class="ncl-min" aria-expanded="true" aria-label="Minimize the needle panel" title="Compact mode: collapse to the title bar and the current step (tap again to expand)">&#9662;</button>' +
    '<button type="button" id="needle-clear">Clear</button>' +
    '<button type="button" id="ncl-close" title="Close the needle tool">&times;</button></div>' +
    '<p class="ncl-disc"><b>Planning / education aid only &mdash; not clinical guidance.</b></p>' +
    '<div class="ncl-modes" id="ncl-modes">' +
    '<button type="button" data-mode="two" title="Click the entry point, then the target">Entry &rarr; target</button>' +
    '<button type="button" data-mode="dir" title="Click the entry; the tip lies along a direction at the needle length">Entry + direction + length</button>' +
    '<button type="button" data-mode="tfirst" title="Pick the deep target first (on a cut face or a motor point), then the entry">Target first</button></div>' +
    '<p class="ncl-status" id="needle-status"></p>' +
    '<div id="ncl-dirbox" hidden>' +
    '<div class="ncl-row" id="ncl-pivot-row" hidden><span>Turn about</span>' +
    '<button type="button" class="ncl-pv" data-pivot="skin" aria-pressed="true" title="The skin crossing stays where it is; the tip swings">skin</button>' +
    '<button type="button" class="ncl-pv" data-pivot="tip" aria-pressed="false" title="The tip stays in the target; the shaft and hub swing around it">tip</button>' +
    '<button type="button" class="ncl-pv" data-pivot="hub" aria-pressed="false" title="The hub stays where your hand is; the whole needle swings around it">hub</button></div>' +
    '<div class="ncl-row"><button type="button" id="ncl-useview" title="Aim along the current viewing direction">Use view axis</button>' +
    '<button type="button" id="ncl-usenormal" title="Perpendicular to the skin at the entry">Perpendicular</button></div>' +
    '<div class="ncl-row"><span>tilt</span><input type="number" id="ncl-tilt" min="0" max="85" step="1" value="0" title="Degrees away from perpendicular to the skin at the entry">' +
    '<span>&deg; toward</span><input type="number" id="ncl-az" min="-180" max="180" step="5" value="0" title="Which way the tilt leans: 0 = cranial, 90 = the entry\'s right-hand side">&deg;</div></div>' +
    '<div class="ncl-row"><span>Needle length</span><input type="range" id="ncl-len" min="5" max="200" step="1" value="' + this.len + '">' +
    '<input type="number" id="ncl-lenn" min="5" max="200" step="1" value="' + this.len + '"> mm</div>' +
    '<div class="ncl-row"><button type="button" id="ncl-shortest" title="Shortest straight path from the target to the skin (or the outermost model surface)">Shortest entry</button>' +
    '<button type="button" id="ncl-zoom" title="Centre the view on the target (or the entry)">Zoom to target</button>' +
    '<button type="button" id="ncl-cuthere" title="A cut plane facing you through the target (or the screen centre) to expose deep tissue; click the cut face to pick a deep target">Cut through target</button></div>' +
    '<div id="needle-report"></div>' +
    /* Q268 (2): live distance readout -- measured, displayed, never judged */
    '<div id="ncl-corr"><div class="ncl-row" style="margin-top:6px"><b>Distance to vessels &amp; nerves</b>' +
    '<button type="button" id="ncl-corr-halo" aria-pressed="true" title="Translucent halo around the path at the two display thresholds">Halo</button></div>' +
    '<div id="ncl-corr-out"></div>' +
    '<div class="ncl-row"><button type="button" id="ncl-sugg" title="Sample straight candidate entries on the skin in a cone around the nearest-skin direction and rank them by measured clearance, then length">Suggest entries</button>' +
    '<button type="button" id="ncl-sugg-x" title="Remove the suggested ghost lines">Clear suggestions</button></div><div id="ncl-sugg-out"></div>' +
    /* Q276: multiple saved injection points -- the current entry/target is still exactly one working placement (unchanged), but it is no
       longer silently lost on the next placement: "Add point" records it (own marker, own distance readout, reusing corridorFor() verbatim),
       as one of two or more sites the owner places within the same muscle. Not a recommendation of how many or where -- a recorder only. */
    '<div class="ncl-row" style="margin-top:6px"><b>Saved points</b>' +
    '<button type="button" id="ncl-save-add" title="Record the current entry/target as an additional saved point (does not replace it)">Add point</button>' +
    '<button type="button" id="ncl-save-clear" title="Remove every saved point">Clear all</button></div>' +
    '<div id="ncl-save-out"></div>' +
    '<details><summary>Bands &amp; neighbourhood</summary>' +
    '<div class="grid2"><span>near band (mm)</span><input type="number" id="ncl-corr-near" min="0" max="100" step="0.5" value="' + this.corr.near + '"><span></span>' +
    '<span>far band (mm)</span><input type="number" id="ncl-corr-far" min="0" max="200" step="0.5" value="' + this.corr.far + '"><span></span>' +
    '<span>neighbourhood R (mm)</span><input type="number" id="ncl-corr-r" min="5" max="200" step="1" value="' + this.corr.R + '"><span></span></div>' +
    '<p class="cite">The two bands are adjustable DISPLAY thresholds (colour only), not clinical guidance: the number is the data, you decide. ' +
    'R = how far from the path a vessel / nerve is measured at all (default ' + CORR_DEFAULTS.R + ' mm, the same neighbourhood the planning preset uses).</p></details>' +
    '</div>' +
    /* Q268 (1): injection-planning preset -- pure wiring of mechanisms that already exist (structure list, selection controller, parts markers, pose rig) */
    '<details id="ncl-plan"><summary title="Pick the target muscle or tendon: the preset fades everything except it and the vessels / nerves within R mm, ' +
    'shows its origin / insertion markers where the page has them, and arms target-first placement">Injection planning (preset)</summary>' +
    '<input type="search" id="ncl-plan-q" placeholder="Search a muscle or tendon to plan an injection into" autocomplete="off">' +
    '<div class="res" id="ncl-plan-res"></div><p class="ncl-status" id="ncl-plan-msg"></p>' +
    '<div id="ncl-plan-zone"></div><div id="ncl-plan-guide"></div>' +
    '<div class="ncl-row"><button type="button" id="ncl-plan-x" title="Clear the preset\'s selection (marks and fade) and the plan">Release plan</button></div>' +
    '<div class="ncl-row"><span>Posture (pose rig)</span><select id="ncl-plan-pose"><option value="rest">Rest (model pose)</option>' +
    Object.keys(POSTURES).map(function (k) { return '<option value="' + k + '">' + esc(POSTURES[k].label) + "</option>"; }).join("") + "</select>" +
    '<select id="ncl-plan-side"><option value="r">right</option><option value="l">left</option></select>' +
    '<button type="button" id="ncl-plan-pose-go">Apply</button></div>' +
    '<p class="cite" id="ncl-plan-pose-msg">A labelled, illustrative flexion pattern driven only through the page\'s own pose rig (its joints, its normal ranges); ' +
    'not the patient\'s posture. The needle tool measures the current (posed) meshes; a placed entry and target ride the structure they were placed on. Motor points stay at their rest positions.</p></details>' +
    '<details id="ncl-mp"><summary title="The motor point(s) of the marked muscles only -- mark one or more muscles first">Motor points</summary>' +
    '<p class="ncl-status" id="ncl-mp-msg"></p>' +
    '<div class="ncl-row"><button type="button" id="ncl-mp-on" aria-pressed="false">Emphasize motor points</button></div>' +
    '<p class="cite">Shows the motor point(s) only of the currently <b>marked</b> muscles -- the same set the "Marked structures" panel ticks. ' +
    'With nothing marked, nothing is shown.</p>' +
    '<p class="ncl-status" id="ncl-mp-sel-msg"></p>' +
    '<input type="search" id="ncl-mp-q" placeholder="Search a muscle to target its motor point" autocomplete="off">' +
    '<div class="res" id="ncl-mp-res"></div><div id="ncl-mp-info"></div></details>' +
    '<details id="ncl-risk"><summary title="A heuristic planning margin around vessels and nerves, and the entries that keep clear of it. Not validated safety distances.">Risk halos &amp; safer pathways</summary>' +
    '<p class="ncl-status" id="ncl-risk-msg"></p>' +
    '<div class="ncl-row"><button type="button" id="ncl-halo" aria-pressed="false">Show risk halos</button>' +
    '<button type="button" id="ncl-safer" title="Sample many straight approaches to the target and light the safer entries">Light safer pathways</button></div>' +
    '<div class="ncl-row"><span>Other tissue transparent</span><input type="range" id="ncl-transp" min="50" max="95" step="1" value="80"><span class="mono" id="ncl-transp-v">80%</span></div>' +
    '<div class="lg">' + legend + "</div>" +
    '<div id="ncl-safer-out"></div><div id="ncl-halo-list"></div>' +
    '<details><summary>The halo model, and its numbers</summary>' +
    '<div class="formula" id="ncl-formula"></div>' +
    '<div class="grid2" style="margin-top:5px"><span>b0 (mm)</span><input type="number" step="0.5" min="0" max="20" data-p="b0" value="' + this.P.b0 + '"><span></span>' +
    '<span>k (per mm of path)</span><input type="number" step="0.005" min="0" max="0.3" data-p="k" value="' + this.P.k + '"><span></span>' +
    '<span>calibre exponent p</span><input type="number" step="0.1" min="0" max="2" data-p="p" value="' + this.P.p + '"><span></span>' + mults + "</div>" +
    '<p class="cite">A heuristic planning margin of ours, not a validated safety distance: the halo grows with the depth already travelled and with ' +
    'the vessel\'s or nerve\'s calibre. Every number here is yours to change.</p></details></details>' +
    '<details><summary>Display</summary><div class="ncl-row"><span>Shaft radius (display)</span>' +
    '<input type="range" id="ncl-rdisp" min="0.3" max="3" step="0.1" value="' + this.rDisp + '"><span class="mono" id="ncl-rdisp-v">' + this.rDisp.toFixed(1) + ' mm</span></div>' +
    '<p class="cite">The needle is drawn as a lit 3-D object in the model, so nearer parts look larger. The part beyond the entry is drawn ' +
    'normally (hidden by opaque tissue) plus a faint see-through copy, so it stays findable in deep tissue.</p></details>' +
    /* Q317: the honesty the panel used to carry inline, in one place, still one tap away */
    '<details id="ncl-notes"><summary>What these numbers are</summary>' +
    '<p class="cite">The geometry measured here is the <b>model\'s</b>: decimated viewing meshes of one body, not the patient. Distances and ' +
    'crossings are real measurements <i>of that model</i>, reported to the millimetre because that is what the meshes give -- they are not ' +
    'patient measurements and carry none of a patient\'s variation.</p>' +
    '<p class="cite">The distance bands, the risk halos and the suggested entries are planning aids of ours. They are labelled where they appear, ' +
    'every parameter is exposed, and none of them is a validated safety distance.</p>' +
    '<p class="cite">The tool measures the current meshes: posed by the pose rig, they are measured as posed, and a placed entry / target rides ' +
    'the structure it was placed on (its nearest triangle). Saved points ride the same way, and so do the motor points: given for the rest ' +
    'pose, each is anchored to its own muscle\'s nearest triangle and is exactly its given position again at rest. A risk halo is drawn ' +
    'around the structure\'s current (posed) surface.</p></details>';
  if (api.panelHost) api.panelHost.insertBefore(el, api.panelBefore || null); else document.body.appendChild(el);
  this.el = el;
  var tip = document.createElement("div"); tip.className = "ncl-tip"; tip.hidden = true; document.body.appendChild(tip); this.tip = tip;
  function $(id) { return el.querySelector("#" + id); }
  this.$ = $;
  $("needle-clear").onclick = function () { self.clear(); };
  $("ncl-close").onclick = function () { self.toggle(false); };
  $("ncl-min").onclick = function (ev) {       // Q264: compact/minimized panel, on request (not forced), off by default
    var wasOpen = $("ncl-min").getAttribute("aria-expanded") !== "false";
    /* a person's tap decides; the page's own layout code clicks this button too (it is not a choice) -- and it must not undo the compact start a phone gets */
    var byPerson = !!(ev && ev.isTrusted);
    if (!byPerson && !wasOpen && self.autoCompact) return;
    if (byPerson) { self.userSized = true; self.autoCompact = false; }
    self.setCompact(wasOpen);
  };
  el.querySelectorAll("#ncl-modes button").forEach(function (b) { b.onclick = function () { self.setMode(b.dataset.mode); }; });
  /* Q317: in the direction mode the entry is fixed and the tip follows the angles, as before. With two placed
     points the same two boxes turn the needle instead, about whichever point the pivot names. */
  function aimed(u) { if (self.mode === "dir") return false; if (!self.aimTo(u)) return false; self.syncAim(); self.update(); return true; }
  $("ncl-useview").onclick = function () {
    if (aimed(api.view().dir)) return;
    self.dir.src = "view"; self.dir.view = api.view().dir; self.update();
  };
  $("ncl-usenormal").onclick = function () {
    if (aimed(self.aimFrame().n)) return;
    self.dir.src = "normal"; $("ncl-tilt").value = 0; self.dir.tilt = 0; self.update();
  };
  function fromBoxes() {
    var t = +$("ncl-tilt").value || 0, z = +$("ncl-az").value || 0;
    self.dir.tilt = t; self.dir.az = z;
    if (self.mode === "dir") { self.dir.src = "angles"; self.update(); return; }
    if (self.aimTo(self.dirFrom(t, z))) self.update();
  }
  $("ncl-tilt").oninput = fromBoxes;
  $("ncl-az").oninput = fromBoxes;
  self.el.querySelectorAll(".ncl-pv").forEach(function (b) {
    b.onclick = function () { self.setPivot(b.dataset.pivot); };
  });
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
  /* Q268 bindings */
  $("ncl-corr-near").onchange = function () { self.setCorr({near: +this.value}); };
  $("ncl-corr-far").onchange = function () { self.setCorr({far: +this.value}); };
  $("ncl-corr-r").onchange = function () { self.setCorr({R: +this.value}); };
  $("ncl-corr-halo").onclick = function () { self.corr.halo = !self.corr.halo; this.setAttribute("aria-pressed", String(self.corr.halo)); self.drawCorridor(); api.redraw(); };
  $("ncl-sugg").onclick = function () { self.suggest(); };
  $("ncl-sugg-x").onclick = function () { self.clearSuggestions(); self.renderSuggestions(); api.redraw(); };
  $("ncl-save-add").onclick = function () { self.addSavedPoint(); };
  $("ncl-save-clear").onclick = function () { self.clearSavedPoints(); };
  $("ncl-plan-q").oninput = function () { self.renderPlanSearch(); };
  $("ncl-plan-x").onclick = function () { self.planRelease(); };
  $("ncl-plan-pose-go").onclick = function () { self.applyPosture($("ncl-plan-pose").value, $("ncl-plan-side").value); };
  this.renderFormula();
  this.renderSavedPoints();
  this.setMode("two", true);
};
TP.renderFormula = function () {
  var P = this.P;
  this.$("ncl-formula").innerHTML = "halo r = clamp( m<sub>type</sub> &times; ( b0 &times; clamp((r<sub>cal</sub>/" + P.rRef + ")<sup>p</sup>, " + P.fMin + ", " + P.fMax +
    ") + k &times; L ), " + P.rMin + ", " + P.rMax + " ) mm<br>b0 = " + P.b0 + ", k = " + P.k + ", p = " + P.p +
    "; L = trajectory length (entry&rarr;target), else the needle length. r<sub>cal</sub> = vessel/nerve/organ calibre radius " +
    (this.risk.data ? "from the loaded risk data" : "(approximate: risk data not loaded)") + ". Heuristic planning margin.";
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
  if (this.active) {
    this.api.stopMotion(); this.api.showPanel(); this.render();
    /* Q344: on a phone the panel opens COMPACT (header + the current step line) so it does not bury the model; one tap on the chevron expands it,
       and once the user has chosen either way their choice stands */
    if (!this.userSized && !this.api.panelHost) { try { this.autoCompact = window.matchMedia("(max-width:900px)").matches; this.setCompact(this.autoCompact); } catch (e) {} }
    this.clearBar();
  }
  else { this.clear(); if (this.risk.on) this.halos(false); if (this.mp.on) this.emphasize(false); }
  this.api.redraw();
};
/* Q344: on a wide screen the floating panel starts below the page's top control bar when that bar reaches over its column (its top-left corner,
   where the shared grip sits, was under the bar) */
TP.clearBar = function () {
  var el = this.el; if (!el || this.api.panelHost || window.innerWidth <= 900) return;
  try {
    el.style.top = ""; el.style.maxHeight = "";
    var bar = document.getElementById("q301-bar"), pr = el.getBoundingClientRect();
    if (!bar) return;
    var br = bar.getBoundingClientRect();
    if (br.width > 0 && br.right > pr.left && br.left < pr.right && br.bottom > pr.top - 2) {
      var top = Math.ceil(br.bottom) + 8;
      el.style.top = top + "px"; el.style.maxHeight = Math.max(240, window.innerHeight - top - 12) + "px";
    }
  } catch (e) {}
};
TP.setCompact = function (on) {
  var m = this.$("ncl-min"); if (!m) return;
  this.el.classList.toggle("ncl-collapsed", !!on);
  m.setAttribute("aria-expanded", String(!on));
  m.setAttribute("aria-label", on ? "Expand the needle panel" : "Minimize the needle panel");
};
TP.cursor = function () { return this.active ? "crosshair" : null; };
TP.setMode = function (m, quiet) {
  this.mode = m;
  this.el.querySelectorAll("#ncl-modes button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.mode === m)); });
  this.syncAimUI();
  if (!quiet) { if (m === "dir") this.target = null; this.update(); }
};
TP.clear = function () {
  this.entry = this.target = null; this.risk.pathEval = null; this.risk.safer = null;
  clearTimeout(this.blockT); this.block = null; this.tipF = null;   // Q381
  ["n-inner", "n-inner-x", "n-outer", "n-hub", "n-tgt", "n-tgt-x", "n-entry", "sp-g", "sp-a", "sp-r", "sp-best", "sp-best-x", "q381-blk", "q381-blk-x", "q381-alt", "q381-alt-x"].forEach(this.ov.remove, this.ov);
  this.$("ncl-safer-out").innerHTML = "";
  this.clearSuggestions(); this.renderSuggestions(); this.scheduleCorridor();   // Q268
  this.drawMarkers(); if (this.pl) { this.pl.kind = null; this.plPlaneClear(); }   // Q367
  if (this.safe) this.safeRun(); else if (this.risk.on) this.refreshHalos();
  this.render(); this.api.redraw();
  this.notify();
};

/* ---------- interaction ---------- */
TP.onClick = function (e) {
  var mpHit = this.mp.on ? this.markerAt(e) : null;
  if (mpHit) { if (!this.active) this.toggle(true); this.useMotorPoint(mpHit); return true; }
  if (!this.active) return false;
  if (this.armFn) {   // Q367: the plan panel armed a tap (entry / free tip / plane side / nerve point); Q381: an ENTRY tap lands on the skin under the pointer, whatever its look
    var ah = (this.armSkin ? this.pickSkin(e) : null) || this.pickPoint(e, this.armSkip != null ? this.armSkip : null);
    if (ah) this.armFn(ah); return true;
  }
  var sp = this.risk.safer ? this.saferAt(e) : null;
  if (sp) { this.adopt(sp); return true; }
  var sg = this.sugg.shown.length ? this.suggAt(e) : null;   // Q268 (3): an explicit tap on a ghost line adopts it; nothing is ever auto-placed
  if (sg) { this.adoptSuggestion(sg); return true; }
  var m = this.mode, hit;
  if (m === "two") {
    if (!this.entry || this.target) { hit = this.pickPoint(e, null); if (hit) { this.entry = hit; this.target = null; } }
    else { hit = this.pickPoint(e, this.entry.i); if (hit) this.target = hit; }
  } else if (m === "tfirst") {
    if (!this.target && this.entry) { hit = this.pickPoint(e, null); if (hit) { this.target = hit; this.risk.safer = null; } }   // Q367: entry first, then the tip -- the entry stays
    else if (!this.target || this.entry) { hit = this.pickPoint(e, null); if (hit) { this.target = hit; this.entry = null; this.risk.safer = null; } }
    else { hit = (this.injOn() ? this.pickSkin(e) : null) || this.pickPoint(e, null); if (hit) this.entry = hit; }   // Q381: in the planning mode the entry is on the skin
  } else {
    hit = this.pickPoint(e, null); if (hit) { this.entry = hit; this.dir.src = this.dir.src === "view" ? "view" : this.dir.src; }
  }
  this.update();
  return true;
};
/* Q317: the frame the tilt / azimuth pair is read in -- the skin normal at the entry, an "up" that leans
   cranial, and the entry's own right-hand side. dirFrom() turns a pair into an axis and aimAngles() turns an
   axis back into the pair, through this one frame, so the number shown and the needle drawn cannot disagree. */
TP.aimFrame = function () {
  var n = this.entry && this.entry.n ? norm(this.entry.n) : norm(this.entry && this.entry.ray ? this.entry.ray : this.api.view().dir);
  var up = sub([0, 1, 0], mul(n, n[1]));
  if (len(up) < 1e-3) up = sub([0, 0, 1], mul(n, n[2]));
  up = norm(up);
  return {n: n, up: up, side: cross(n, up)};
};
TP.dirFrom = function (tilt, az) {
  var F = this.aimFrame(), th = tilt * Math.PI / 180, a = az * Math.PI / 180;
  return norm(add(mul(F.n, Math.cos(th)), mul(add(mul(F.up, Math.cos(a)), mul(F.side, Math.sin(a))), Math.sin(th))));
};
TP.dirVector = function () {
  if (this.dir.src === "view" && this.dir.view) return norm(this.dir.view);
  return this.dirFrom(this.dir.tilt, this.dir.az);
};
/* the inverse: the axis the two placed points imply, as the same tilt / azimuth pair */
TP.aimAngles = function () {
  if (!this.entry || !this.target) return null;
  var L = dist(this.entry.p, this.target.p);
  if (L < 1e-3) return null;
  var u = mul(sub(this.target.p, this.entry.p), 1 / L), F = this.aimFrame();
  var c = clamp(dot(u, F.n), -1, 1), w = sub(u, mul(F.n, c));
  return {tilt: Math.acos(c) * 180 / Math.PI,
          az: len(w) < 1e-6 ? 0 : Math.atan2(dot(w, F.side), dot(w, F.up)) * 180 / Math.PI};
};
/* Every point of the needle lies on one axis, measured back from the tip: the tip at 0, the skin crossing at
   the entry-to-tip distance, the hub end at the needle's length plus the hub. Turning the whole thing about
   any of those keeps that one still and swings the rest -- the choice between what is held and what moves. */
TP.pivotBack = function () {
  if (this.pivot === "tip") return 0;
  if (this.pivot === "hub") return this.len + Math.max(10, 7 * this.rDisp);
  return this.entry && this.target ? dist(this.entry.p, this.target.p) : 0;
};
TP.structureAtTip = function (A, B) {
  var self = this, L = dist(A, B);
  var vis = this.recs.filter(function (r) { return self.api.visible(r.i); }).map(function (r) { return r.i; });
  var rows = this.crossings(A, B, vis, null).filter(function (c) { return c.to >= L - 0.05; });
  var nonSkin = rows.filter(function (c) { return self.skin.indexOf(c.i) < 0; });
  var pick = (nonSkin.length ? nonSkin : rows).sort(function (a, b) { return b.from - a.from; })[0];
  return pick ? pick.i : null;
};
/* turn the placed needle to a new axis, about whichever point the pivot names, keeping its length */
TP.aimTo = function (u2) {
  if (!this.entry || !this.target) return false;
  var E = this.entry.p, T = this.target.p, L = dist(E, T);
  if (L < 1e-3 || len(u2) < 1e-6) return false;
  u2 = norm(u2);
  var u = mul(sub(T, E), 1 / L), a = this.pivotBack(), P = addS(T, u, -a);
  var T2 = addS(P, u2, a), E2 = addS(T2, u2, -L);
  /* the tip has moved, so what it sits in is asked again, and a motor point or cut face it was on no longer holds */
  this.entry = {p: E2, i: this.entry.i, n: this.entry.n, ray: this.entry.ray};
  this.target = {p: T2, i: this.structureAtTip(E2, T2), n: null, computed: true};
  return true;
};
TP.setPivot = function (p) { this.pivot = p; this.syncAimUI(); };
/* the two angle boxes show the placement's own direction, so they are never stale against the needle drawn */
TP.syncAim = function () {
  var a = this.aimAngles();
  if (!a) return;
  var t = this.$("ncl-tilt"), z = this.$("ncl-az");
  if (t) t.value = Math.round(a.tilt);
  if (z) z.value = Math.round(a.az);
  this.dir.tilt = a.tilt; this.dir.az = a.az;
};
TP.syncAimUI = function () {
  var box = this.$("ncl-dirbox"), row = this.$("ncl-pivot-row"), self = this;
  var placed = !!(this.entry && this.target);
  if (box) box.hidden = this.mode !== "dir" && !placed;
  if (row) {
    row.hidden = this.mode === "dir";          /* in the direction mode the entry is the pivot by construction */
    row.querySelectorAll(".ncl-pv").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.pivot === self.pivot)); });
  }
  if (this.mode !== "dir" && placed) this.syncAim();
};
TP.update = function () {
  if (this.mode === "dir" && this.entry) {
    var u = this.dirVector(), tip = addS(this.entry.p, u, this.len), self = this;
    this.target = {p: tip, i: this.structureAtTip(this.entry.p, tip), n: null, computed: true};
  }
  this.ensureAnchors();   // Q325: a newly placed point is anchored on the geometry it was placed on
  this.risk.pathEval = null;
  this.blockRun();        // Q381: the straight path against bone, on every placement change
  this.drawNeedle();
  if (this.risk.on) { this.refreshHalos(); if (this.entry && this.target) this.evalCurrent(); }
  this.scheduleCorridor();   // Q268 (2): throttled to the placement change, not per frame
  this.safeSchedule();       // Q367: the user's distance rules, checked on the same placement change
  this.render();
  this.api.redraw();
  this.notify();
};
TP.onHostChange = function () {
  if (this.active && this.entry && this.target) this.render();
  if (this.risk.on) this.refreshHalos();
  if (this.mp.on) this.refreshMpOverlay();   // Q281: re-filter the shown motor points when the marked-muscle set changes -- never applyOverride() here, see refreshMpOverlay()'s own comment
};

/* ---------- needle drawing ---------- */
TP.drawNeedle = function () {
  var ov = this.ov, r = this.rDisp;
  ["n-inner", "n-inner-x", "n-outer", "n-hub", "n-tgt", "n-tgt-x", "n-entry"].forEach(ov.remove, ov);
  this.drawMarkers();   // Q367: the tip (sky-blue diamond) and the skin entry (orange ring) -- one pair everywhere
  this.drawBlock();     // Q381: a path that crosses bone, red from the first bone on; the offered entry
  if (!this.entry || !this.target) return;
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
      var skinCatOn = this.recs.some(function (rr) { return rr.cat === "skin"; });   // Q355: the skin exists but is hidden -> say so and offer to show it
      if (!this.skin.length && skinCatOn && !this.api.categoryOn("skin")) {
        st.textContent = "The skin is hidden. Show it to enter on it, or click the outermost surface." + cutHint;
        var sb = document.createElement("button"); sb.type = "button"; sb.textContent = "Show the skin";
        sb.addEventListener("click", function () { self.api.setCategoryOn("skin", true); self.render(); });
        rep.appendChild(sb);
        return;
      }
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
    (R.aim ? "<dt>Direction</dt><dd>" + f1(R.aim.tilt) + "&deg; from perpendicular to the skin, leaning toward " + f1(R.aim.az) + "&deg;" +
      ' <span class="ncl-status">(0&deg; = cranial, 90&deg; = the entry\'s right)</span></dd>' : "") +
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
    return '<li><span class="dot" style="background:' + col + '"></span>' + esc(c.name) + (sideWord(self.recs[self.byId[c.id][0]].side) ? ' <span class="ncl-status">(' + sideWord(self.recs[self.byId[c.id][0]].side) + ")</span>" : "") + rng + "</li>";
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
        ? self.mp.points.length + " motor points loaded for this body."
        : "No motor-point data loaded for this body.";
    } else self.mp.msg = "No motor-point data loaded.";
    self.renderMp(); self.renderRiskMsg(); self.renderFormula();
  });
};
TP.renderRiskMsg = function () {
  var d = this.risk.data, n = this.cls.filter(function (c) { return c && CLASSES[c].halo; }).length;
  this.$("ncl-risk-msg").innerHTML = n + " risk structures in this model. " +
    (d ? "Vessel and nerve calibre: risk data loaded."
       : '<span class="warn">Risk data not loaded: calibre approximated from bounding boxes.</span>');
};
TP.rCal = function (i) {
  var r = this.risk.rcal[this.recs[i].id];
  if (r) return r;
  var R = this.recs[i], B = this.restBox[i] || [R.bmin, R.bmax];   // Q332: the calibre is the rest box's, not a posed (rotated) box's
  var ext = Math.min(B[1][0] - B[0][0], B[1][1] - B[0][1], B[1][2] - B[0][2]);
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
TP.mpStructure = function (p) {   // Q328: decided once, on the rest data (the point's given coordinates, the rest boxes) -- a posed body cannot change it
  if (this.mpS.has(p)) return this.mpS.get(p);
  var ids = this.byId[p.structure_id] || this.byId[p.atlas_id] || [], self = this;
  var inBox = ids.filter(function (i) {
    var r = self.recs[i], B = self.restBox[i] || [r.bmin, r.bmax];
    return p.pos.every(function (c, k) { return c >= B[0][k] - 2 && c <= B[1][k] + 2; });
  });
  var s = (inBox.length ? inBox : ids).length ? (inBox.length ? inBox : ids)[0] : null;
  this.mpS.set(p, s);
  return s;
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
    (p.projection_mm != null ? "; projection " + (typeof p.projection_mm === "number" ? f1(p.projection_mm) + " mm" : esc(JSON.stringify(p.projection_mm))) : "") + "</dd>" +
    "<dt>Uncertainty</dt><dd>" + (p.uncertainty_mm != null ? f1(p.uncertainty_mm) + " mm (sphere radius)" : "--") + "</dd>" +
    "<dt>Source</dt><dd>" + esc(s.citation || "--") + (s.doi ? " doi:" + esc(s.doi) : "") + (s.pmid ? " PMID " + esc(s.pmid) : "") +
    (s.rule ? '<br><span class="ncl-status">' + esc(s.rule) + "</span>" : "") + "</dd>" +
    (p.badge ? "<dt>Badge</dt><dd>" + esc(p.badge) + "</dd>" : "") + "</dl>";
};
/* Q281: "only in the selected muscles" -- the project's own established multi-select vocabulary is the
   Marked-structures set (Q227, viewer/selection/selection.js), exposed to this add-on as api.selection().
   markedIds() returns null when the host page carries no selection controller at all (older/plain pages,
   or the Z-Anatomy template before it attaches one): in that one case emphasis falls back to the pre-Q281
   behaviour (every motor point) rather than silently showing nothing on a page that has no way to mark
   anything. Once a selection controller exists, an EMPTY mark set is read literally: zero muscles marked
   means zero motor points shown, not "show all" -- that is the request's own wording. */
TP.markedIds = function () {
  var sel = this.api && this.api.selection && this.api.selection();
  if (!sel || typeof sel.state !== "function") return null;
  try { var st = sel.state(); return (st && st.marks) || []; } catch (e) { return null; }
};
TP.visibleMpPoints = function () {
  var ids = this.markedIds();
  if (ids === null) return this.mp.points;           // no selection controller on this page: unfiltered (old behaviour)
  if (!ids.length) return [];                         // selection controller present but nothing marked: show none
  var set = {}; ids.forEach(function (id) { set[id] = 1; });
  return this.mp.points.filter(function (p) { return set[p.structure_id] === 1 || set[p.atlas_id] === 1; });
};
/* Q281: split from emphasize() itself -- this redraws the sphere overlay for the CURRENT this.mp.on state only; it
   never touches applyOverride()/setOpacityOverride(), which is what the host's own apply()/draw() cycle calls back
   into api.onChange() for (TP.onHostChange). emphasize() below calls applyOverride() exactly once, when the toggle
   itself flips; onHostChange() (fired whenever the host's marked-structures set changes) calls ONLY this refresh --
   calling applyOverride() again from inside onHostChange() would re-enter apply() -> changeHooks -> onHostChange()
   and recurse without end (the bug this comment is here to stop a future edit from reintroducing). */
TP.refreshMpOverlay = function () {
  ["mp-core", "mp-core-x", "mp-unc", "mp-unc-x"].forEach(this.ov.remove, this.ov);
  var shown = [];
  if (this.mp.on) {
    shown = this.visibleMpPoints();
    var cores = chunked(shown, function (g, p) { addSphere(g, p.pos, 1.8, 10, 6); });
    var unc = chunked(shown, function (g, p) { addSphere(g, p.pos, Math.max(2, +p.uncertainty_mm || 5), 14, 9); });
    this.ov.set("mp-core", cores, {color: MP_COLOUR, pass: "opaque", emis: 0.6});
    this.ov.set("mp-core-x", cores, {color: MP_COLOUR, pass: "xray", alpha: 0.55, emis: 0.7});
    this.ov.set("mp-unc", unc, {color: MP_COLOUR, pass: "trans", alpha: 0.14, emis: 0.5});
    this.ov.set("mp-unc-x", unc, {color: MP_COLOUR, pass: "xray", alpha: 0.06, emis: 0.5});
  }
  this.$("ncl-mp-sel-msg").innerHTML = !this.mp.on ? "" :
    this.markedIds() === null ? "No marked-structures selection on this page -- showing every motor point."
    : !shown.length ? '<span class="warn">No muscles marked: mark one or more muscles (tick in the structure list, or Shift/Ctrl/Cmd-click in 3-D) to see their motor points.</span>'
    : shown.length + " motor point" + (shown.length === 1 ? "" : "s") + " in " + (this.markedIds() || []).length + " marked structure" + ((this.markedIds() || []).length === 1 ? "" : "s") + ".";
};
TP.emphasize = function (on) {
  this.mp.on = !!on && this.mp.points.length > 0;
  this.$("ncl-mp-on").setAttribute("aria-pressed", String(this.mp.on));
  this.refreshMpOverlay();
  this.applyOverride();
};
TP.markerAt = function (e) {
  var best = null, bd = 14, api = this.api, pts = this.mp.on ? this.visibleMpPoints() : this.mp.points;
  pts.forEach(function (p) {
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
  var gh = this.guide && this.guide.hl ? this.guide.hl.set : null;   // Q347: the guide's "structures at risk" get their halo with the risk view off too
  var sh = this.safe && this.safe.halos.length ? this.safeHalos() : null;   // Q367: the user's rule halos (exact rule radius) win over any other halo of the same structure
  if (!this.risk.on && !gh) { this.ov.setHalos(sh || []); this.$("ncl-halo-list").innerHTML = ""; this.api.redraw(); return; }
  var self = this, L = this.currentL(), focus = this.target ? this.target.p : (this.entry ? this.entry.p : null);
  var reach = this.len + 60, list = [], rows = [];
  this.recs.forEach(function (r, i) {
    var g = !!gh && gh[i] === 1; if (!g && !self.risk.on) return;
    var c = self.cls[i]; if (!c || !CLASSES[c].halo || !self.api.visible(i)) return;
    var dmin = 0;
    if (focus) {
      for (var k = 0; k < 3; k++) { var dk = Math.max(r.bmin[k] - focus[k], 0, focus[k] - r.bmax[k]); dmin += dk * dk; }
      dmin = Math.sqrt(dmin); if (dmin > reach && !g) return;
    }
    var rc = self.rCal(i), h = haloRadius(c, rc, L, self.P);
    list.push({i: i, r: h * self.orientSign(i), color: CLASSES[c].color, alpha: 0.22});
    rows.push({i: i, cls: c, rc: rc, h: h, d: dmin});
  });
  if (sh) { var shI = {}; sh.forEach(function (x) { shI[x.i] = 1; }); list = list.filter(function (x) { return !shI[x.i]; }).concat(sh); }
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
  var R0 = this.risk.region, tgtId = this.target && this.target.i != null ? this.recs[this.target.i].id : null, pk = this.poseKey();
  if (R0 && R0.reach === reach && dist(R0.T, T) < 1e-6 && R0.P === JSON.stringify(this.P) && R0.tgtId === tgtId && R0.pk === pk) return R0;   // Q332: + the pose (a still target, moved neighbours)
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
  /* Q367: the entry surface is the skin LAYER (Z ids are "zan_skin_..."; only ids starting "skin_" counted before, so Base·M had no
     skin and took the last surface hit within reach -- on the trunk an organ such as the liver -- and Base·F had only its two perineal
     pieces, i.e. no computed entry anywhere else). No skin near the target: the outermost-surface rule, as on a page without skin. */
  this.skinIdx();
  var useSkin = this.skinLayer.length > 0;
  var surf = useSkin ? gather(this.skinLayer) : null;
  if (!surf || !surf.ntris) { useSkin = false; surf = gather(all); }
  var bone = gather(this.blockers());   // Q381: bone and hyaline cartilage -- what a straight needle cannot pass
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
  var reg = {T: T.slice(), reach: reach, P: JSON.stringify(this.P), tgtId: tgtId, pk: pk, surf: surf, useSkin: useSkin, bone: bone, grid: grid, structs: sIdx,
             nTris: surf.ntris + bone.ntris, nPts: pts.length / 3, ms: performance.now() - t0, minD: new Float32Array(sIdx.length)};
  this.risk.region = reg;
  return reg;
};
/* the entry for direction u from target T: {E, L, entryI, ok, why} */
TP.entryFor = function (reg, T, u, reach) {
  if (reg.useSkin) {
    var hs = reg.surf.ray(T, u, 0.2, reach + HUB_CLEAR_MM);
    if (!hs.length) return {ok: false, why: "no skin within reach"};
    /* Q367: skin pieces overlap at their seams and the Base meshes can be shells: skin surfaces within SKIN_STACK_MM of the first
       are the same skin -- the entry is the outermost of them; another skin surface beyond that, within the hub clearance, obstructs */
    var k0 = 0; while (k0 + 1 < hs.length && hs[k0 + 1].t <= hs[0].t + SKIN_STACK_MM) k0++;
    var t1 = hs[k0].t; if (t1 > reach) return {ok: false, why: "longer than the needle"};
    var again = hs.some(function (h) { return h.t > t1 + 0.5 && h.t <= t1 + HUB_CLEAR_MM; });
    return {ok: true, E: addS(T, u, t1), L: t1, entryI: reg.surf.owner[hs[k0].tri], obstructed: again};
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
  var boneHit = this.boneFreeRay(reg, T, u, L) ? [] : [1];   // Q381: the one bone rule (a tip may rest on a bone; nothing is crossed before it)
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
      var uk = [dirs[3 * k], dirs[3 * k + 1], dirs[3 * k + 2]], en = self.entryFor(reg, T, uk, self.len);
      if (en.ok && !en.obstructed && (!best || en.L < best.L) && self.boneFreeRay(reg, T, uk, en.L) && !self.boneCheck(en.E, T).blocked) best = {E: en.E, L: en.L, entryI: en.entryI, u: uk};   // Q381: never through bone
    }
    if (!best) { self.$("needle-status").innerHTML = '<span class="warn">No straight bone-free path to the skin within the ' + self.len + " mm needle length.</span>"; return; }
    self.adopt(best);
  }, 0);
};

/* ===================================================================== */
/* Q268 (2): live distance readout to vessels and nerves ("corridor")      */
/* ===================================================================== */
TP.isCorrStruct = function (i) { return !!CORR_CLASSES[this.cls[i]]; };
/* minimum distance from segment A-B (A == B: a single point) to the surface of every named vessel / nerve mesh whose bounding
   box lies within R mm of the segment (padded slab test), excluding the target's own structure. Exact closest point against
   the page's own triangles (meshSegDist). Returns {items (nearest first), n (meshes measured), ms}. */
TP.corridorFor = function (A, B, skipId, R) {   // R: the radius (default the panel's; a saved point keeps its own, Q332)
  var self = this, t0 = performance.now(), items = [], n = 0;
  if (R == null) R = this.corr.R;
  this.recs.forEach(function (r, i) {
    if (!self.isCorrStruct(i) || r.id === skipId || !boxHitsSegment(r.bmin, r.bmax, A, B, R)) return;
    var g = self.geom(i); if (!g) return;
    n++;
    var res = meshSegDist(g.pos, g.idx, A, B, R + 1e-6);
    if (res.d <= R) items.push({i: i, id: r.id, name: self.name(i), cls: self.cls[i], d: res.d});
  });
  items.sort(function (x, y) { return x.d - y.d; });
  return {items: items, n: n, ms: performance.now() - t0, min: items.length ? items[0].d : Infinity};
};
TP.scheduleCorridor = function () {
  var self = this; clearTimeout(this.corr.timer);
  this.corr.timer = setTimeout(function () { self.corr.timer = 0; self.computeCorridor(); }, 80);
};
TP.computeCorridor = function () {
  var A = this.entry ? this.entry.p : null, B = this.target ? this.target.p : null;
  this.tipF = this.target ? this.tipFacts() : null;                 // Q381: inside / on / outside its structure, the nearest skin
  this.corr.pass = A && B ? this.passList(A, B) : [];              // Q381: ligaments / membranes / capsules the path crosses (listed, not blocking)
  if (!A && !B) { this.corr.items = []; this.corr.n = 0; this.corr.what = ""; this.corr.seq = (this.corr.seq || 0) + 1; this.drawCorridor(); this.renderCorridor(); this.api.redraw(); return; }
  var seg = !!(A && B); if (!A) A = B; if (!B) B = A;
  var res = this.corrResult = this.corridorFor(A, B, this.target && this.target.i != null ? this.recs[this.target.i].id : null);
  this.corr.items = res.items; this.corr.n = res.n; this.corr.ms = res.ms; this.corr.seq = (this.corr.seq || 0) + 1;
  this.corr.what = (seg ? "the entry → target segment" : (this.target ? "the target point" : "the entry point")) + " to the surface triangles of " + res.n +
    " vessel / nerve mesh" + (res.n === 1 ? "" : "es") + " whose bounding box lies within R = " + this.corr.R + " mm of it";
  this.drawCorridor(); this.renderCorridor(); this.api.redraw();
};
TP.setCorr = function (o) {
  var c = this.corr, redo = false;
  if (o.near != null && isFinite(o.near)) c.near = clamp(o.near, 0, 100);
  if (o.far != null && isFinite(o.far)) c.far = clamp(o.far, 0, 200);
  if (c.far < c.near) c.far = c.near;
  if (o.R != null && isFinite(o.R) && clamp(o.R, 5, 200) !== c.R) { c.R = clamp(o.R, 5, 200); redo = true; }
  this.$("ncl-corr-near").value = c.near; this.$("ncl-corr-far").value = c.far; this.$("ncl-corr-r").value = c.R;
  if (redo) this.computeCorridor(); else { this.drawCorridor(); this.renderCorridor(); this.api.redraw(); }
};
TP.band = function (d) { return d < this.corr.near ? "n" : (d < this.corr.far ? "m" : "f"); };
TP.poseAway = function () {   // the page's pose rig is away from its rest pose (Q325: the add-on now measures the posed meshes)
  var pose = this.api.pose ? this.api.pose() : null;
  try { return !!(pose && pose.ready() && !pose.isRest()); } catch (err) { return false; }
};
TP.renderCorridor = function () {
  var out = this.$("ncl-corr-out"), c = this.corr, self = this;
  if (!this.entry && !this.target) { out.innerHTML = '<p class="ncl-status">Place a point: the distances appear here and update with every change.</p>'; return; }
  var h = '<p class="ncl-status">Measured: minimum distance from ' + esc(c.what) + " (" + c.ms.toFixed(0) + " ms; decimated viewing meshes, " + (this.poseAway() ? "current pose" : "rest pose") + ", hidden structures included; the target's own structure excluded).</p>";
  if (this.poseAway()) h += '<p class="ncl-status">Measured on the posed meshes (the pose rig is away from rest). A kinematic preview: the soft tissue is skinned, not simulated.</p>';
  if (!c.items.length) h += '<p class="ncl-status">No vessel or nerve within R = ' + c.R + " mm.</p>";
  else h += '<ol class="corr-list">' + c.items.slice(0, 12).map(function (it) {
    return '<li class="band-' + self.band(it.d) + '"><span class="dot" style="background:' + CLASSES[it.cls].color + '"></span>' + esc(it.name) +
      ' <span class="rng mono">' + it.d.toFixed(1) + " mm</span></li>";
  }).join("") + "</ol>" + (c.items.length > 12 ? '<p class="ncl-status">' + (c.items.length - 12) + " more farther away.</p>" : "");
  h += '<p class="cite">Bands: &lt; ' + c.near + " mm, " + c.near + "&ndash;" + c.far + " mm, &gt; " + c.far + " mm -- display only, set above; no safe / unsafe judgement is made or implied.</p>";
  out.innerHTML = h;
  this.notify();
};
TP.drawCorridor = function () {
  var ov = this.ov; ["corr-in", "corr-out"].forEach(ov.remove, ov);
  if (!this.corr.halo || (!this.entry && !this.target)) return;
  var A = this.entry ? this.entry.p : this.target.p, B = this.target ? this.target.p : this.entry.p, c = this.corr;
  function shape(r) { return dist(A, B) < 1e-3 ? addSphere(new Geo(), A, r, 18, 12) : addTube(new Geo(), A, B, r, r, 24, {capA: true, capB: true}); }
  if (c.near > 0) ov.set("corr-in", shape(c.near), {color: "#5B8DEF", pass: "trans", alpha: 0.14, emis: 0.2, order: 2});
  if (c.far > c.near) ov.set("corr-out", shape(c.far), {color: "#5B8DEF", pass: "trans", alpha: 0.06, emis: 0.15, order: 1});
};

/* ===================================================================== */
/* Q276: saved injection points -- bring the needle to 2+ locations in the same muscle. The working this.entry/this.target
   placement is UNCHANGED (one at a time, overwritten by the next placement exactly as before); "Add point" snapshots it into
   this.savedPts instead of losing it. Each saved point gets its own overlay marker (ov.set keyed per point, the exact addSphere
   pattern n-tgt/n-entry already use) and its own distance-to-nearest-vessel/nerve readout computed with corridorFor() verbatim
   -- no second distance-calculation path. This is a recorder: no count, spacing or pattern is ever suggested. */
TP.addSavedPoint = function () {
  if (!this.target) return null;
  var nextId = 1; this.savedPts.forEach(function (s) { if (s.id >= nextId) nextId = s.id + 1; });
  var A = this.entry ? this.entry.p : this.target.p, B = this.target.p, R = this.corr.R, key = this.poseKey();
  var skipId = this.target.i != null ? this.recs[this.target.i].id : null, res = this.corridorFor(A, B, skipId, R);
  this.ensureAnchors();   // Q328: a saved point keeps the working point's anchor (Q325), so it rides the pose like the plan does
  function snap(pt) { var o = {p: pt.p.slice(), i: pt.i}; if (pt._anc && pt._anc.s >= 0) o._anc = Object.assign({}, pt._anc, {src: o.p}); return o; }
  var item = {
    id: nextId,
    entry: this.entry ? snap(this.entry) : null,
    target: snap(this.target),
    targetName: this.target.i != null ? this.name(this.target.i) : (this.target.mp ? this.target.mp.muscle_name + " motor point" : null),
    L: this.entry ? dist(this.entry.p, this.target.p) : 0,
    corr: {items: res.items.slice(0, 8), n: res.n},
    skipId: skipId, R: R, key0: key, corrKey: key, within: res.items.map(function (x) { return x.i; })   // Q332: what a re-measure needs
  };
  item.corr0 = item.corr; item.within0 = item.within;   // the saved readout, shown again exactly in the pose it was saved in
  this.savedPts.push(item);
  this.drawSavedPoint(item);
  this.renderSavedPoints(); this.notify(); this.api.redraw();
  return item;
};
TP.drawSavedPoint = function (item) {
  var r = this.rDisp || 1, ov = this.ov;
  /* Q367: the same tip / entry pair as the working plan (smaller, translucent); the band colour is the row's in the list */
  ov.set("n-tgt-s" + item.id, addOcta(new Geo(), item.target.p, r * 2.0), {color: MK.tip.color, pass: "trans", alpha: 0.75, emis: 0.3, order: 4});
  ov.set("n-tgt-s" + item.id + "-x", addOcta(new Geo(), item.target.p, r * 2.0), {color: MK.tip.color, pass: "xray", alpha: 0.35, emis: 0.3});
  if (item.entry) ov.set("n-entry-s" + item.id, addRing(new Geo(), item.entry.p, sub(item.target.p, item.entry.p), r * 2.6, r * 0.6), {color: MK.entry.color, pass: "trans", alpha: 0.8, emis: 0.3, order: 4});
};
TP.removeSavedPoint = function (id) {
  var idx = -1, k; for (k = 0; k < this.savedPts.length; k++) if (this.savedPts[k].id === id) { idx = k; break; }
  if (idx < 0) return false;
  var it = this.savedPts[idx], ov = this.ov;
  ov.remove("n-tgt-s" + it.id); ov.remove("n-tgt-s" + it.id + "-x"); ov.remove("n-entry-s" + it.id);
  this.savedPts.splice(idx, 1);
  this.renderSavedPoints(); this.notify(); this.api.redraw();
  return true;
};
TP.clearSavedPoints = function () {
  var self = this;
  this.savedPts.forEach(function (it) { self.ov.remove("n-tgt-s" + it.id); self.ov.remove("n-tgt-s" + it.id + "-x"); self.ov.remove("n-entry-s" + it.id); });
  this.savedPts = [];
  this.renderSavedPoints(); this.notify(); this.api.redraw();
};
TP.renderSavedPoints = function () {
  var out = this.$ ? this.$("ncl-save-out") : null; if (!out) return;
  var self = this;
  if (!this.savedPts.length) { out.innerHTML = '<p class="ncl-status">No saved points yet. Place entry/target, then Add point to record it as one of two or more sites in the same muscle.</p>'; return; }
  out.innerHTML = '<ol class="corr-list">' + this.savedPts.map(function (it, k) {
    var nearest = it.corr.items[0], bnd = nearest ? self.band(nearest.d) : null;
    return '<li' + (bnd ? ' class="band-' + bnd + '"' : "") + '><b>Point ' + (k + 1) + "</b> — " + esc(it.targetName || "target") +
      (it.entry ? " · " + it.L.toFixed(1) + " mm" : " (target only)") +
      (nearest ? " · nearest " + esc(nearest.name) + ' <span class="rng mono">' + nearest.d.toFixed(1) + " mm</span>" : " · no vessel/nerve within R") +
      ' <button type="button" data-rmsaved="' + it.id + '" title="Remove this saved point">Remove</button></li>';
  }).join("") + "</ol>" + '<p class="ncl-status" id="ncl-save-pose">Nearest vessel / nerve per point: measured on the ' + (this.poseAway() ? "current pose" : "rest pose") +
    " (measured again after every pose change).</p>";
  Array.prototype.forEach.call(out.querySelectorAll("[data-rmsaved]"), function (b) { b.onclick = function () { self.removeSavedPoint(+b.dataset.rmsaved); }; });
};

/* ===================================================================== */
/* Q268 (3): suggested entry candidates -- a simple, stated heuristic      */
/* ===================================================================== */
TP.suggest = function () {
  var self = this, out = this.$("ncl-sugg-out");
  this.clearSuggestions();
  if (!this.target) { this.sugg.msg = "Set a target first (target-first mode, a cut face, a motor point, or the planning preset)."; this.renderSuggestions(); return null; }
  /* Q381: a suggestion never crosses bone. The nearest-skin direction is the shortest straight path to the skin that is unobstructed
     AND bone-free (the region's bone grid); every cone candidate is bone-free on the grid and confirmed by the exact test (boneCheck).
     No such direction: said plainly -- with the shortest bone-free length when only the needle is too short. */
  var T = this.target.p, reach = this.len, reg = this.region(T, reach), dirs = fibonacciSphere(600), best = null, k, nSkin = 0, nFree = 0;
  for (k = 0; k < 600; k++) {
    var u0 = [dirs[3 * k], dirs[3 * k + 1], dirs[3 * k + 2]], e0 = this.entryFor(reg, T, u0, reach);
    if (!e0.ok || e0.obstructed) continue;
    nSkin++;
    if (!this.boneFreeRay(reg, T, u0, e0.L)) continue;
    nFree++;
    if (!best || e0.L < best.L) best = {u: u0, L: e0.L};
  }
  this.sugg.nSkin = nSkin; this.sugg.nFree = nFree; this.sugg.none = null; this.sugg.longer = null;
  if (!best) {
    this.sugg.none = nSkin ? "bone" : "skin";
    var longer = null, R2 = 200;
    if (reach < R2) {   // would a longer needle do? the shortest bone-free straight path within 200 mm
      var reg2 = this.region(T, R2);
      for (k = 0; k < 600; k++) {
        var u2 = [dirs[3 * k], dirs[3 * k + 1], dirs[3 * k + 2]], e2 = this.entryFor(reg2, T, u2, R2);
        if (e2.ok && !e2.obstructed && (!longer || e2.L < longer.L) && this.boneFreeRay(reg2, T, u2, e2.L) && !this.boneCheck(e2.E, T).blocked) longer = {L: e2.L};
      }
    }
    this.sugg.longer = longer ? longer.L : null;
    this.sugg.msg = (nSkin ? "No straight path to this tip is free of bone within the " + reach + " mm needle length (" + nSkin + " of 600 sampled directions reach the skin, all cross bone)"
                           : "No skin within the " + reach + " mm needle length") + ": no candidate." +
                    (longer ? " Shortest bone-free straight path: " + longer.L.toFixed(0) + " mm." : (reach < R2 ? " None within " + R2 + " mm either." : ""));
    this.renderSuggestions(); return null;
  }
  var tgtId = this.target.i != null ? this.recs[this.target.i].id : null, cands = [], t0 = performance.now();
  coneDirs(best.u, SUGG_HALF_DEG * Math.PI / 180, SUGG_N).forEach(function (u) {
    var en = self.entryFor(reg, T, u, reach); if (!en.ok || en.obstructed) return;
    if (!self.boneFreeRay(reg, T, u, en.L) || self.boneCheck(en.E, T).blocked) return;
    var m = self.corridorFor(en.E, T, tgtId);
    cands.push({u: u, E: en.E, L: en.L, entryI: en.entryI, minD: m.min, nearest: m.items[0] || null, n: m.n});
  });
  var ranked = rankCandidates(cands, SUGG_TIE_MM), far = this.corr.far;
  var good = ranked.filter(function (c) { return c.minD > far; });
  this.sugg.cands = ranked; this.sugg.shown = good.slice(0, SUGG_SHOW); this.sugg.ms = performance.now() - t0; this.sugg.sampled = cands.length;
  this.sugg.msg = good.length ? "" : "None of the " + cands.length + " sampled candidates clears the far display threshold (" + far + " mm): none shown.";
  this.drawSuggestions(); this.renderSuggestions(); this.api.redraw();
  return this.sugg.shown;
};
TP.clearSuggestions = function () { this.sugg.cands = []; this.sugg.shown = []; this.sugg.msg = ""; this.sugg.none = null; this.sugg.longer = null; ["sg-0", "sg-1", "sg-0-x", "sg-1-x"].forEach(this.ov.remove, this.ov); };
TP.drawSuggestions = function () {
  var ov = this.ov, T = this.target.p, self = this;
  this.sugg.shown.forEach(function (c, k) {   // faint dashed ghost: 2.5 mm dashes, 2 mm gaps
    var g = new Geo(), L = dist(c.E, T), u = norm(sub(T, c.E)), r = 0.3 * self.rDisp + 0.12;
    for (var s = 0; s < L; s += 4.5) addTube(g, addS(c.E, u, s), addS(c.E, u, Math.min(L, s + 2.5)), r, r, 8, {});
    ov.set("sg-" + k, g, {color: "#9AD1FF", pass: "trans", alpha: 0.5, emis: 0.4});
    ov.set("sg-" + k + "-x", g, {color: "#9AD1FF", pass: "xray", alpha: 0.22, emis: 0.4});
  });
};
TP.renderSuggestions = function () {
  var out = this.$("ncl-sugg-out"), s = this.sugg, self = this;
  if (!s.shown.length) { out.innerHTML = s.msg ? '<p class="ncl-status">' + esc(s.msg) + "</p>" : ""; return; }
  out.innerHTML = '<p class="ncl-status">' + s.sampled + " straight candidates sampled in a " + SUGG_HALF_DEG + "&deg; cone around the nearest-skin direction (" + s.ms.toFixed(0) +
    " ms), ranked by measured clearance (larger first; within " + SUGG_TIE_MM + " mm, shorter first). Ghost lines in the model; tap <b>Use</b> or the line itself to adopt one -- nothing is placed for you.</p><ol>" +
    s.shown.map(function (c, k) {
      return '<li><button type="button" data-sg="' + k + '">Use</button> ' + c.L.toFixed(0) + " mm, clearance " +
        (isFinite(c.minD) ? c.minD.toFixed(1) + " mm" + (c.nearest ? ' <span class="ncl-status">(' + esc(c.nearest.name) + ")</span>" : "") : "&gt; R (nothing within " + self.corr.R + " mm)") + "</li>";
    }).join("") + '</ol><p class="cite">A simple sampling heuristic on the model\'s skin and decimated meshes, not an optimiser and not a recommendation.</p>';
  out.querySelectorAll("[data-sg]").forEach(function (b) { b.onclick = function () { self.adoptSuggestion(self.sugg.shown[+b.dataset.sg]); }; });
  this.notify();
};
TP.suggAt = function (e) {
  var api = this.api, T = api.toScreen(this.target ? this.target.p : null), best = null, bd = 9; if (!T) return null;
  this.sugg.shown.forEach(function (c) {
    var A = api.toScreen(c.E); if (!A) return;
    var dx = T[0] - A[0], dy = T[1] - A[1], l2 = dx * dx + dy * dy || 1, t = clamp(((e.clientX - A[0]) * dx + (e.clientY - A[1]) * dy) / l2, 0, 1);
    var d = Math.hypot(A[0] + t * dx - e.clientX, A[1] + t * dy - e.clientY); if (d < bd) { bd = d; best = c; }
  });
  return best;
};
TP.adoptSuggestion = function (c) {
  if (!c) return;
  this.entry = {p: c.E.slice(), i: c.entryI, n: mul(c.u, -1)};
  if (this.mode === "dir") this.setMode("tfirst", true);
  this.clearSuggestions(); this.renderSuggestions();
  this.update();
};

/* ===================================================================== */
/* Q268 (1): injection-planning preset                                    */
/* ===================================================================== */
var PLAN_CATS = {muscle: 1, tendon: 1, insertion: 1};   // own pages: muscle / tendon; Z pages: muscle / insertion (= tendons)
TP.renderPlanSearch = function () {
  var q = this.$("ncl-plan-q").value.trim().toLowerCase(), box = this.$("ncl-plan-res"), self = this;
  box.innerHTML = ""; if (!q) return;
  var hits = this.recs.filter(function (r) { return PLAN_CATS[r.cat] && (r.name + " " + r.id).toLowerCase().indexOf(q) >= 0; }).slice(0, 40);
  if (!hits.length) { box.innerHTML = '<p class="ncl-status">No muscle or tendon matches.</p>'; return; }
  hits.forEach(function (r) {
    var b = document.createElement("button"); b.type = "button";
    b.innerHTML = esc(r.name) + (sideWord(r.side) ? ' <span class="ncl-status">(' + sideWord(r.side) + ")</span>" : "");
    b.onclick = function () { self.planPick(r.i); };
    box.appendChild(b);
  });
};
function boxDist(amin, amax, bmin, bmax) {
  var s = 0; for (var k = 0; k < 3; k++) { var d = Math.max(bmin[k] - amax[k], 0, amin[k] - bmax[k]); s += d * d; } return Math.sqrt(s);
}
TP.planNeighbours = function (i) {
  var r = this.recs[i], R = this.corr.R, self = this, ids = {};
  this.recs.forEach(function (s, j) { if (j !== i && self.isCorrStruct(j) && boxDist(r.bmin, r.bmax, s.bmin, s.bmax) <= R) ids[s.id] = 1; });
  return Object.keys(ids);
};
TP.planPick = function (i) {
  var r = this.recs[i], api = this.api, self = this, msgs = [];
  if (this.guide.hl) this.guideHighlight(null, false);   // Q347: the previous target's at-risk marks go
  this.plan.i = i;
  this.$("ncl-plan-q").value = r.name; this.$("ncl-plan-res").innerHTML = "";
  // (b) fade everything except the target and its vessel / nerve neighbours -- through the selection controller's PUBLIC API only
  var sel = api.selection ? api.selection() : null, nb = this.planNeighbours(i);
  if (sel && sel.markIds && sel.setGroup) {
    var n = sel.markIds([r.id].concat(nb), true, true, true);
    sel.setGroup("oth", "fade", true);
    msgs.push(n + " marked (target + " + nb.length + " vessel / nerve structures with a bounding box within R = " + this.corr.R + " mm), the rest faded");
  } else msgs.push("no selection controller on this page: nothing faded");
  // (c) origin / insertion / adjacent-tissue (fascial passage, MTJ) markers (viewer/parts_ui) when the page has parts data, no-op otherwise
  var parts = api.parts ? api.parts() : null;
  if (parts && parts.select && parts.state) {
    parts.select(r.id);
    var ps = parts.state();
    if (ps.loaded && ps.sel && ps.sel.n) { if (ps.mode === "off") parts.setMode("sel"); parts.dirty(); msgs.push(ps.sel.n + " origin / insertion / adjacent-tissue part" + (ps.sel.n === 1 ? "" : "s") + " shown"); }
    else msgs.push(ps.loaded ? "no origin / insertion data for this structure" : "no parts data on this page");
  } else msgs.push("no parts markers on this page");
  // (c2) Q281: the "expected injection zone" together -- this target's own bundles/heads (origin / insertion / MTJ /
  // fascial-passage parts, grouped by their structure_parts.json part_set, i.e. this project's own bundle concept)
  // plus its own motor point(s) (NMJ), drawn regardless of the separate global "Emphasize motor points" toggle
  // (that one filters by the Marked-structures set; planning a target always shows THAT target's own NMJ).
  var zone = this.planZone(r);
  this.plan.zone = zone;   // Q281: cached so injectionMode() (the mode-inj Hebrew card) can render the same data without recomputing it
  this.drawPlanMp(zone.mps);
  this.renderPlanZone(r, zone);
  if (zone.mps.length > 1) msgs.push(zone.mps.length + " motor-point bundles (injection-zone list below)");
  else if (zone.mps.length === 1) msgs.push("1 motor point shown");
  else msgs.push("no motor-point data for this structure");
  // (d) arm the needle tool, target-first, and bring the target into view (view only -- no point is placed for you)
  if (!this.active) this.toggle(true);
  this.entry = this.target = null; this.risk.safer = null;
  this.setMode("tfirst", true);
  var c = [0, 1, 2].map(function (k) { return (r.bmin[k] + r.bmax[k]) / 2; }), ext = dist(r.bmin, r.bmax);
  if (api.focus) api.focus(c, Math.max(160, ext * 1.6));
  if (this.plan.posture !== "rest") msgs.push("posture preview is on: reset it for valid distances");
  this.plan.msg = "Target <b>" + esc(r.name) + "</b>: " + msgs.map(esc).join("; ") + ". Now click the target point inside it (Cut through target exposes deep tissue).";
  this.$("ncl-plan-msg").innerHTML = this.plan.msg;
  this.update();
  this.notify();
};
TP.planRelease = function () {
  if (this.guide.hl) this.guideHighlight(null, false);   // Q347
  var sel = this.api.selection ? this.api.selection() : null;
  if (sel && sel.clear && this.plan.i != null) sel.clear();
  this.plan.i = null; this.plan.msg = ""; this.$("ncl-plan-msg").innerHTML = ""; this.$("ncl-plan-q").value = "";
  this.drawPlanMp(null); this.$("ncl-plan-zone").innerHTML = ""; this.plan.zone = null;   // Q281
  this.api.redraw();
  this.notify();
};
/* Q281: a muscle's own motor point(s) for its "expected injection zone" -- matched against this project's own
   per-viewer motor_points.json id scheme, which is not always the plain structure id verbatim (e.g. one deltoid
   point set is keyed "deltoid_r_zfill203", a Z-Anatomy-fill variant id, while the other side is plain "deltoid_l") --
   exact id, atlas_id, or a "<id>_" prefix all count as this structure's own point. */
TP.planMotorPoints = function (r) {
  var id = r.id;
  return this.mp.points.filter(function (p) {
    return p.structure_id === id || p.atlas_id === id || (p.structure_id || "").indexOf(id + "_") === 0;
  });
};
var MP_BUNDLE_WORDS = ["anterior", "middle", "posterior", "medial", "lateral", "proximal", "distal", "superior", "inferior", "upper", "lower", "deep", "superficial", "clavicular", "acromial", "spinal", "long", "short"];
/* Best-effort label read directly from the point's OWN cited rule text (e.g. deltoid's three points literally say
   "anterior belly" / "middle belly" / "posterior belly", from Yi et al. 2023) -- never a fabricated index->name
   mapping: a muscle whose points don't name a part in their own text gets no label, just "point k of N". */
function mpBundleLabel(p) {
  var text = (((p.source && p.source.rule) || "") + " " + (p.kind || "")).toLowerCase();
  for (var i = 0; i < MP_BUNDLE_WORDS.length; i++) {
    var w = MP_BUNDLE_WORDS[i];
    if (text.indexOf(w + " belly") >= 0 || text.indexOf(w + " head") >= 0 || text.indexOf(w + " part") >= 0) return w;
  }
  return null;
}
TP.planZone = function (r) {
  var mps = this.planMotorPoints(r);
  var parts = this.api.parts ? this.api.parts() : null;
  var pf = (parts && parts.partsFor) ? parts.partsFor(r.id) : [];
  var bySet = {}, order = [];
  pf.forEach(function (p) {
    var key = p.set || ("ty:" + p.ty);
    if (!bySet[key]) { bySet[key] = {name: p.setName || p.label, items: []}; order.push(key); }
    bySet[key].items.push(p);
  });
  return {mps: mps, groups: order.map(function (k) { return bySet[k]; })};
};
TP.drawPlanMp = function (pts) {
  ["plan-mp", "plan-mp-x"].forEach(this.ov.remove, this.ov);
  if (!pts || !pts.length) return;
  var cores = chunked(pts, function (g, p) { addSphere(g, p.pos, 2.0, 10, 6); });
  this.ov.set("plan-mp", cores, {color: MP_COLOUR, pass: "opaque", emis: 0.7});
  this.ov.set("plan-mp-x", cores, {color: MP_COLOUR, pass: "xray", alpha: 0.6, emis: 0.8});
};
TP.renderPlanZone = function (r, zone) {
  var self = this, html = "";
  if (zone.groups.length) {
    html += '<p class="ncl-status" style="margin-top:6px"><b>Bundles / landmarks (origin, insertion, adjacent tissue)</b> -- click to jump to one:</p>';
    zone.groups.forEach(function (g) {
      html += '<p class="cite" style="margin:3px 0 1px">' + esc(g.name) + '</p>';
      g.items.forEach(function (it) {
        html += '<button type="button" class="ncl-zone-part" data-pid="' + esc(it.id) + '"' + (it.placed ? "" : " disabled") + '>' +
          esc(it.name) + ' <span class="ncl-status">(' + esc(it.label) + (it.unverified ? ", unverified" : "") + (it.placed ? "" : ", text only, no marker") + ')</span></button>';
      });
    });
  } else html += '<p class="ncl-status">No origin / insertion / adjacent-tissue part data for this structure (no parts sidecar, or none authored for it).</p>';
  if (zone.mps.length) {
    html += '<p class="ncl-status" style="margin-top:6px"><b>Neuromuscular junction' + (zone.mps.length > 1 ? " -- " + zone.mps.length + " documented points/bundles" : "") + '</b>: click to set it as the target.</p>';
    zone.mps.forEach(function (p, k) {
      var lbl = mpBundleLabel(p);
      html += '<button type="button" class="ncl-zone-mp" data-k="' + k + '">' + (lbl ? esc(lbl) + " belly/part" : "Point " + (k + 1) + " of " + zone.mps.length) +
        ' <span class="ncl-status">' + esc(p.nerve || "") + '</span></button>';
    });
  } else html += '<p class="ncl-status">No motor-point data for this structure.</p>';
  this.$("ncl-plan-zone").innerHTML = html;
  Array.prototype.forEach.call(this.$("ncl-plan-zone").querySelectorAll(".ncl-zone-part"), function (b) {
    b.onclick = function () { var p = self.api.parts ? self.api.parts() : null; if (p && p.focusById) p.focusById(b.dataset.pid); };
  });
  Array.prototype.forEach.call(this.$("ncl-plan-zone").querySelectorAll(".ncl-zone-mp"), function (b) {
    b.onclick = function () { self.useMotorPoint(zone.mps[+b.dataset.k]); };
  });
};
/* posture preset through the page's own pose rig (window-level Q241 controller handed over by the host as api.pose()) */
TP.applyPosture = function (key, side) {
  var pose = this.api.pose ? this.api.pose() : null, msg = this.$("ncl-plan-pose-msg"), self = this;
  if (!pose || !pose.ready || !pose.ready()) { msg.innerHTML = '<span class="warn">No pose rig is ready on this page: posture preview unavailable.</span>'; return null; }
  this.plan.posture = key; this.plan.side = side;
  if (key === "rest" || !POSTURES[key]) { pose.reset(); msg.textContent = "Pose reset to the model's rest pose."; this.scheduleCorridor(); return {applied: [], skipped: []}; }
  var pat = POSTURES[key], P = pose.restPose(), rig = pose.rig(), byId = {}, applied = [], skipped = [];
  rig.joints.forEach(function (j) { byId[j.id] = j; });
  Object.keys(pat.joints).forEach(function (jn) {
    var id = jn + "_" + side, j = byId[id];
    Object.keys(pat.joints[jn]).forEach(function (k) {
      var x = j && !j.driven ? j.dof.map(function (d) { return d.k; }).indexOf(k) : -1;
      if (x < 0) { skipped.push(id + "." + k); return; }
      P.j[id][x] = clamp(pat.joints[jn][k], j.dof[x].lo, j.dof[x].hi); applied.push(id + "." + k);
    });
  });
  pose.apply(P);
  msg.innerHTML = esc(pat.label) + ", " + side + ": " + applied.length + " joint angles applied within this page's normal ranges" +
    (skipped.length ? '; <span class="warn">' + skipped.length + " not in this page's rig (skipped, not invented): " + esc(skipped.join(", ")) + "</span>" : "") +
    '. The needle tool measures the posed meshes; the placed path rides the structures it was placed on.';
  setTimeout(function () { self.scheduleCorridor(); }, 50);
  return {applied: applied, skipped: skipped};
};

/* Q272: change hooks for the workspace-mode re-skin (viewer/modes/): called after every render that changes what a card shows */
TP.notify = function () { if (this.guide) this.renderPlanGuide(); var hs = this.hooks || []; for (var k = 0; k < hs.length; k++) { try { hs[k](); } catch (e) { console.error(e); } } };
/* Q272: a default target point at the structure's vertex centroid (the mode's "as automatic as possible" step: planPick() only arms
   target-first placement; a tap inside the structure replaces this point exactly as before) */
TP.setTargetAt = function (i) {
  /* Q381: a point INSIDE the structure, on the mesh as it is now (meshCentre: mid-thickness where the structure is thickest, nearest its
     centre of volume, never inside a bone). It was the mean of the REST vertices: outside the mesh for a curved or tendinous muscle
     (tibialis posterior: 19 mm outside, inside the tibia), and in a posed body the place the muscle had left. */
  var cc = this.centreOf(i); if (!cc) return null;
  var c = cc.p.slice();
  this.entry = null; this.target = {p: c, i: i, n: null}; this.risk.safer = null;
  this.update();
  return c;
};
/* ===================================================================== */
/* Q347: the INJECTION GUIDE (EURO-MUSCULUS/USPRM spasticity guide, Güvener et al., Eur J Phys Rehabil Med 2026;62(5):441-59,
   CC BY-NC-ND: facts with citation only) for the planned / targeted muscle -- from the private sibling clinical_injection_guide.json
   (scripts/clinical/build_injection_guide_q347.py, built at regen) and the PUBLIC sidecar innervation_q322.json (the IZ bands
   placed on this body). Shown as the json says it; nothing here measures twice:
   - "Use site N": the target is the band's inside centre (the sidecar's dot, rest coordinates) -- anchored on the rest mesh and
     ridden to the current pose (anchorPoint / ridePoint, as the motor points, Q328); unplaced bands are listed with the reason.
   - "Structures at risk": the named structures that exist on this body are marked (selection controller) and haloed
     (refreshHalos); their distances are the corridor's own items (computeCorridor -> corridorFor), never a second measurement.
   - "Start scan here": only where the scan start names a landmark of the band placement; the probe goes on the skin over it
     (the scan tool's own placeRay). "Show on the model": key frames on the page's pose rig, inside its range (an illustration).
   ===================================================================== */
var GUIDE_TXT = {
  he: {title: "מדריך ההזרקה", count: function (n) { return n == null ? "מספר הנקודות לא צוין" : n === 1 ? "נקודת הזרקה אחת" : n + " נקודות הזרקה"; },
       kPoints: "נקודות הזרקה", kSites: "אתרים", site: "אתר", along: "לאורך", placed: "מוקם על גוף זה", proj: "מוקם על גוף זה, מוקרן מקו על העור",
       rule: "מיקום לפי כלל", unplaced: "לא מוקם על גוף זה", qual: "אתר איכותני בלבד, ללא נקודה", noBand: "אין רצועה בנתונים לצד זה",
       use: "השתמש באתר", tIn: "המטרה בתוך השריר", tSurf: function (d) { return "המטרה על פני השריר (" + d + ' מ"מ מחוץ לו)'; },
       tOut: function (d) { return "המטרה מחוץ לשריר (" + d + ' מ"מ)'; }, kScan: "תחילת הסריקה", scanGo: "התחל סריקה כאן", scanRule: "הגשש מונח על העור מעל נקודת ציון שנמדדה בעצמות גוף זה",
       scanNo: "טקסט בלבד: נקודת ההתחלה אינה נקודת ציון בנתונים", scanFail: "לא ניתן להניח את הגשש כאן", scanOk: "הגשש הונח",
       kMan: "תמרון דינמי", show: "הצג על המודל (המחשה)", showRule: "המחשה על ריג התנוחה בתוך טווח התנועה; המדריך אינו מציין זוויות",
       kRisk: "מבנים בסיכון", riskOn: "הדגש על המודל", unmapped: "אין מבנה תואם בגוף זה", notMeasured: "לא נמדד: נמדדים רק כלי-דם ועצבים",
       beyond: function (R) { return "רחוק מ-" + R + ' מ"מ'; }, noTarget: "המרחק יופיע כשתוצב מטרה", none: "לא צוין במדריך",
       conflict: "הטבלה והטקסט במדריך אינם תואמים", adopted: "הוצג:", other: "הגרסה האחרת:", cite: "מקור מלא", unit: 'מ"מ',
       fromPath: "המרחקים מהמסלול", fromTarget: "המרחקים מנקודת המטרה", posed: "נמדד בתנוחה הנוכחית"},
  en: {title: "Injection guide", count: function (n) { return n == null ? "number of points not stated" : n + (n === 1 ? " injection point" : " injection points"); },
       kPoints: "Injection points", kSites: "Sites", site: "Site", along: "along", placed: "placed on this body", proj: "placed on this body, projected from a skin line",
       rule: "rule-based position", unplaced: "not placed on this body", qual: "qualitative site only, no point", noBand: "no band in the data for this side",
       use: "Use site", tIn: "the target is inside the muscle", tSurf: function (d) { return "the target is on the muscle surface (" + d + " mm outside)"; },
       tOut: function (d) { return "the target is outside the muscle (" + d + " mm)"; }, kScan: "Scan start", scanGo: "Start scan here", scanRule: "The probe goes on the skin over a landmark measured on this body's bones",
       scanNo: "Text only: the start is not a landmark in the data", scanFail: "The probe could not be placed here", scanOk: "Probe placed",
       kMan: "Dynamic manoeuvre", show: "Show on the model (illustration)", showRule: "An illustration on the pose rig, inside its range of motion; the guide gives no angles",
       kRisk: "Structures at risk", riskOn: "Highlight on the model", unmapped: "no matching structure on this body", notMeasured: "not measured: only vessels and nerves are",
       beyond: function (R) { return "farther than " + R + " mm"; }, noTarget: "the distance appears once a target is placed", none: "not stated in the guide",
       conflict: "The guide's table and text disagree", adopted: "shown:", other: "the other:", cite: "Full source", unit: "mm",
       fromPath: "distances from the path", fromTarget: "distances from the target point", posed: "measured in the current pose"}
};
function gEl(tag, a, kids) {
  var e = document.createElement(tag);
  if (a) Object.keys(a).forEach(function (k) {
    var v = a[k]; if (v == null) return;
    if (k === "text") e.textContent = v; else if (k === "class") e.className = v; else if (k.slice(0, 2) === "on") e[k] = v; else e.setAttribute(k, v);
  });
  (kids || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
  return e;
}
function gBdi(t) { return gEl("bdi", {dir: "ltr", text: String(t)}); }
function gPretty(s) { s = String(s || "").replace(/_/g, " "); return s.charAt(0).toUpperCase() + s.slice(1); }
TP.loadGuide = function () {
  var self = this;
  function get(url) { return fetch(url, {cache: "no-cache"}).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  if (typeof fetch !== "function") return;
  var pub = global.NMSKInnervation && global.NMSKInnervation.data ? global.NMSKInnervation.data() : null;
  Promise.all([get("clinical_injection_guide.json"), pub ? Promise.resolve(pub) : get("innervation_q322.json")]).then(function (res) {
    var g = res[0], s = res[1];
    if (!g || g.schema !== "nmsk.injection_guide.page.v1") return;
    self.guide.data = g;
    self.guide.side = s && s.schema === "nmsk.innervation.page.v1" ? s : null;
    var bm = {};
    if (self.guide.side) s.bands.forEach(function (b) { (bm[b.m + "|" + b.s] = bm[b.m + "|" + b.s] || []).push(b); });
    self.guide.bm = bm;
    self.notify();
  });
};
TP.guideKey = function (r) {   // the guide's muscle key of a structure: the public sidecar's own structure list, else the id without its side
  var G = this.guide, M = G.data && G.data.muscles, S = G.side && G.side.muscles; if (!r || !M) return null;
  if (S) for (var k in S) if (M[k] && S[k].structures.indexOf(r.id) >= 0) return k;
  var b = String(r.id).replace(/_[lr]$/, "");
  return M[b] ? b : null;
};
TP.guideView = function (i) {
  var r = i != null && i >= 0 ? this.recs[i] : null, k = this.guideKey(r); if (!k) return null;
  var G = this.guide, m = G.data.muscles[k], S = G.side, pm = S && S.muscles[k], self = this;
  var s = r.side === "l" || r.side === "left" || /_l$/.test(r.id) ? "l" : "r";
  var sites = pm ? pm.iz.map(function (iz, n) {
    var b = (G.bm[k + "|" + s] || []).filter(function (x) { return x.iz === n; })[0] || null, L = S.lines[iz.line] || {};
    return {n: n + 1, part: iz.part, pct: iz.pct, line: L.label || "", st: b ? b.st : "none", dot: b && b.st === "placed" && b.dot ? b.dot : null,
            reason: b ? (b.reason || "") : "", proj: !!(b && b.proj)};
  }) : [];
  var risk = (m.risk || []).map(function (rk) {
    var idx = [];
    rk.stems.forEach(function (st) { [st + "_" + s, st].forEach(function (id) { (self.byId[id] || []).forEach(function (j) { if (idx.indexOf(j) < 0) idx.push(j); }); }); });
    return {name: rk.name, idx: idx};
  });
  return {key: k, i: i, side: s, m: m, sites: sites, risk: risk, src: G.data.source};
};
TP.useGuideSite = function (view, site) {
  if (!view || !site || !site.dot) return false;
  var self = this, r = this.recs[view.i], ids = this.byId[r.id] || [view.i];
  var s = ids.filter(function (i) { var R = self.recs[i], B = self.restBox[i] || [R.bmin, R.bmax]; return site.dot.every(function (c, k) { return c >= B[0][k] - 1 && c <= B[1][k] + 1; }); })[0];
  if (s == null) s = view.i;
  var w = {p: site.dot.slice(), i: s, n: null};
  if (this.poseKey() !== "rest") { this.anchorPoint(w, s, true); if (!this.ridePoint(w)) return false; }   // the dot is given at rest: ride it to the current pose
  /* where the point lies: the band's dot is the section's inside centre, but on a thin muscle it can sit a fraction of a mm outside
     the decimated viewing mesh -- said as it is, never moved */
  var inside = this.insideMesh(s, w.p), g = inside ? null : this.geom(s), off = g ? poseAnchor(g.pos, g.idx, w.p, null).d : 0;
  this.target = {p: w.p, i: s, n: null, site: site.n, gk: view.key, where: {inside: inside, off: off}};
  this.mp.sel = null;
  if (this.mode === "dir" || (this.mode === "two" && !this.entry)) this.setMode("tfirst", true);
  if (this.mode === "tfirst") this.entry = null;
  this.clearSuggestions(); this.risk.safer = null;
  ["sp-g", "sp-a", "sp-r", "sp-best", "sp-best-x"].forEach(this.ov.remove, this.ov);
  var so = this.$("ncl-safer-out"); if (so) so.innerHTML = "";
  this.update();
  return true;
};
/* the at-risk rows: one per modelled structure name, its distance = the corridor's own item (the nearest piece), or none */
TP.guideRiskRows = function (view) {
  var self = this, by = {};
  this.corr.items.forEach(function (it) { if (!by[it.i] || it.d < by[it.i].d) by[it.i] = it; });
  return view.risk.map(function (rk) {
    var g = {}, order = [];
    rk.idx.forEach(function (j) {
      var nm = self.name(j), o = g[nm];
      if (!o) { o = g[nm] = {name: nm, ids: [], measured: false, d: null}; order.push(nm); }
      if (o.ids.indexOf(self.recs[j].id) < 0) o.ids.push(self.recs[j].id);
      if (self.isCorrStruct(j)) o.measured = true;
      var it = by[j]; if (it && (o.d == null || it.d < o.d)) o.d = it.d;
    });
    return {name: rk.name, mapped: rk.idx.length > 0, rows: order.map(function (n) { return g[n]; })};
  });
};
TP.guideHighlight = function (view, on) {
  var self = this, G = this.guide, api = this.api, sel = api.selection ? api.selection() : null;
  if (G.hl) {
    if (sel && sel.markIds && G.hl.added.length) sel.markIds(G.hl.added, false, false, true);
    Object.keys(G.hl.cats).forEach(function (c) { api.setCategoryOn(c, false); });
    G.hl = null;
  }
  if (on && view) {
    var idx = [], ids = [], before = {}, cats = {};
    view.risk.forEach(function (rk) { rk.idx.forEach(function (j) { if (idx.indexOf(j) < 0) idx.push(j); }); });
    idx.forEach(function (j) { var id = self.recs[j].id; if (ids.indexOf(id) < 0) ids.push(id); });
    if (sel && sel.state) { try { (sel.state().marks || []).forEach(function (id) { before[id] = 1; }); } catch (e) {} }
    idx.forEach(function (j) { var c = self.recs[j].cat; if (c && !cats[c] && !api.categoryOn(c)) { cats[c] = 1; api.setCategoryOn(c, true); } });   // switched on here, off again with the highlight
    var added = ids.filter(function (id) { return !before[id]; });
    if (sel && sel.markIds && added.length) sel.markIds(added, true, false, true);
    G.hl = {key: view.key, side: view.side, set: {}, added: added, cats: cats, n: idx.length};
    idx.forEach(function (j) { G.hl.set[j] = 1; });
  }
  this.refreshHalos(); api.redraw(); this.notify();
  return G.hl ? G.hl.n : 0;
};
/* "Start scan here": the landmark (rest coordinates, ridden on its bone when the body is posed), the scan tool's OWN skin (its
   geometry, after its own pose sync -- the same posed skin its probe rides), the skin vertex nearest to the landmark, and the
   scan tool's placeRay() from the landmark towards that vertex; the plane only when the guide states one. A scan start whose
   landmark or bone is not on this page offers no button (guideScanOk). */
TP.guideScanOk = function (view, sc) {
  var U = global.NMSKUltrasound;
  return !!(U && U.placeRay && U.geo && sc && (view.side === "l" ? sc.l : sc.r) && (this.byId[sc.bone + "_" + view.side] || []).length);
};
TP.guideScan = function (view, sc) {
  var U = global.NMSKUltrasound, self = this;
  if (!this.guideScanOk(view, sc)) return Promise.resolve(null);
  var p = (view.side === "l" ? sc.l : sc.r).slice();
  if (this.poseKey() !== "rest") {
    var bi = this.byId[sc.bone + "_" + view.side][0];
    var w = {p: p, i: bi, n: null}; this.anchorPoint(w, bi, true); if (!this.ridePoint(w)) return Promise.resolve(null); p = w.p;
  }
  if (U.open) U.open();
  return (U.ready ? U.ready() : Promise.resolve(true)).then(function () {
    if (U.set) U.set({});                                       // one pass of the scan tool's own pump: it takes the current pose first
    return new Promise(function (res) { setTimeout(res, 80); });
  }).then(function () {
    var geo = U.geo(); if (!geo || !geo.skinList || !geo.vStart) return null;
    var P = geo.pos, best = null, bd = 1e30;
    for (var si = 0; si < geo.skinList.length; si++) {
      var st = geo.skinList[si];
      for (var k = geo.vStart[st] * 3, e = geo.vStart[st + 1] * 3; k < e; k += 3) {
        var dx = P[k] - p[0], dy = P[k + 1] - p[1], dz = P[k + 2] - p[2], d = dx * dx + dy * dy + dz * dz;
        if (d < bd) { bd = d; best = [P[k], P[k + 1], P[k + 2]]; }
      }
    }
    if (!best || bd < 1e-6) return null;
    var h = U.placeRay(p, norm(sub(best, p))); if (!h) return null;
    if (sc.plane) U.set({refKey: sc.plane, rot: 0});
    return {P: h.P, N: h.N, landmark: p, skin_mm: Math.sqrt(bd)};
  }).catch(function () { return null; });
};
/* "Show on the model": the json's key frames on the target's side -- only the joint DOFs they name move (the rig's own set(),
   inside its range) -- then the user's pose exactly as it was: the rest pose itself when it started there (reset(); the rig's
   rest holds values outside its ROM that a set / apply would clamp), else each moved DOF set back to its value. It starts after
   the click's history commit has run and stops (restoring at once) on any user input, so the page-wide Undo never records a
   demo frame. */
TP.guideShow = function (view, done) {
  var pose = this.api.pose ? this.api.pose() : null, fr = view && view.m.show, self = this;
  if (!pose || !pose.ready || !pose.ready() || !pose.set || !fr || this.guide.busy) return false;
  var P0 = pose.pose(), rest0 = pose.isRest(), byId = {}, touched = [], seen = {};
  pose.rig().joints.forEach(function (j) { byId[j.id] = j; });
  var seq = fr.map(function (f) {
    var out = [];
    Object.keys(f).forEach(function (jn) {
      var id = jn + "_" + view.side, j = byId[id]; if (!j || j.driven || !P0.j[id]) return;
      Object.keys(f[jn]).forEach(function (k) {
        var x = j.dof.map(function (d) { return d.k; }).indexOf(k); if (x < 0) return;
        out.push([id, k, clamp(f[jn][k], j.dof[x].lo, j.dof[x].hi)]);
        if (!seen[id + "." + k]) { seen[id + "." + k] = 1; touched.push([id, k, P0.j[id][x], j.dof[x]]); }
      });
    });
    return out;
  }).filter(function (o) { return o.length; });
  if (!seq.length) return false;
  var timer = 0, k = 0, ended = false, EV = ["pointerdown", "keydown", "wheel", "touchstart"];
  function finish() {
    if (ended) return; ended = true; clearTimeout(timer);
    EV.forEach(function (t) { global.removeEventListener(t, stop, true); });
    if (rest0) pose.reset();
    else touched.forEach(function (t) {
      if (t[2] >= t[3].lo && t[2] <= t[3].hi) pose.set(t[0], t[1], t[2]);
      else { pose.reset(); pose.apply(P0); }      // a value outside the range can only be a rest value: as close as the rig allows
    });
    self.guide.busy = false; self.notify(); if (done) done();
  }
  function stop() { finish(); }
  function step() {
    if (ended) return;
    if (k >= seq.length) { finish(); return; }
    seq[k++].forEach(function (s) { pose.set(s[0], s[1], s[2]); });
    timer = setTimeout(step, 800);
  }
  this.guide.busy = true; this.notify();
  timer = setTimeout(function () {                                 // after the click's own history commit (320 ms)
    EV.forEach(function (t) { global.addEventListener(t, stop, true); });
    step();
  }, 450);
  return true;
};
/* the Guide section itself (Hebrew in the injection mode, English in the needle panel); opt: {btn: button class, phone, refresh} */
function guideDom(tool, view, lang, opt) {
  var T = GUIDE_TXT[lang], m = view.m, G = tool.guide, he = lang === "he", okey = lang + ":" + view.key + ":" + view.side;
  var open = G.open[okey] != null ? G.open[okey] : !opt.phone;
  var d = gEl("details", {class: he ? "mc-guide" : "ncl-guide", "data-guide": view.key, dir: he ? "rtl" : null});
  if (open) d.open = true;
  d.addEventListener("toggle", function () { G.open[okey] = d.open; });
  d.appendChild(gEl("summary", null, [T.title + " · " + T.count(m.injection_points)]));
  function row(k, kids, g) { var p = gEl("div", {class: "g-row", "data-g": g}, [gEl("span", {class: "g-k", text: k + ": "})].concat(kids)); d.appendChild(p); return p; }
  function txt(v) { return v == null ? gEl("span", {class: "g-sub", text: T.none}) : gBdi(v); }
  function btn(kids, fn, a) { var b = gEl("button", {type: "button", class: opt.btn || null}, kids); b.onclick = fn; if (a) Object.keys(a).forEach(function (x) { if (a[x] != null) b.setAttribute(x, a[x]); }); return b; }
  function note(t, cls) { return gEl("div", {class: cls || "g-sub", text: t}); }
  row(T.kPoints, [m.injection_points == null ? gEl("span", {class: "g-sub", text: T.none}) : gBdi(m.injection_points)], "points");
  row(T.kSites, [txt(m.sites)], "sites");
  view.sites.forEach(function (s) {
    var box = gEl("div", {class: "g-site", "data-g-site": String(s.n), "data-g-st": s.st});
    var head = [T.site + " " + s.n];
    if (s.part && s.part !== "main") head.push(" · ", gBdi(gPretty(s.part)));
    if (s.pct != null) head.push(" · ", gBdi(s.pct + "%"), " " + T.along + " ", gBdi(s.line));
    box.appendChild(gEl("div", null, head));
    var stl = gEl("div", {class: "g-sub"}, [s.st === "placed" ? (s.proj ? T.proj : T.placed) : s.st === "failed" ? T.unplaced : s.st === "qualitative" ? T.qual : T.noBand]);
    if (s.st === "placed") { stl.appendChild(document.createTextNode(" ")); stl.appendChild(gEl("span", {class: "g-badge", text: T.rule})); }
    if (s.st === "failed" && s.reason) { stl.appendChild(document.createTextNode(": ")); stl.appendChild(gBdi(s.reason)); }
    box.appendChild(stl);
    if (s.dot) {
      var cur = !!(tool.target && tool.target.gk === view.key && tool.target.site === s.n);
      box.appendChild(btn([T.use + " " + s.n], function () { tool.useGuideSite(view, s); opt.refresh(); }, {"data-g-use": String(s.n), "aria-pressed": String(cur)}));
      var wh = cur && tool.target.where;
      if (wh) box.appendChild(gEl("div", {class: "g-sub", "data-g-where": wh.inside ? "in" : wh.off <= 0.5 ? "surface" : "out", "data-g-off": String(wh.off)},
        [wh.inside ? T.tIn : wh.off <= 0.5 ? T.tSurf(fmt1(wh.off)) : T.tOut(fmt1(wh.off))]));
    }
    d.appendChild(box);
  });
  if (m.conflict) row(T.conflict, [T.adopted + " ", gBdi(m.conflict.adopted), "; " + T.other + " ", gBdi(m.conflict.other)], "conflict");
  row(T.kScan, [txt(m.scan_start)], "scan");
  var U = global.NMSKUltrasound, smsg = G.msg[okey + ":scan"];
  var scans = (m.scan || []).filter(function (sc) { return tool.guideScanOk(view, sc); });
  if (scans.length) {
    scans.forEach(function (sc, n) {
      d.appendChild(btn([T.scanGo + " · ", gBdi(sc.label)], function () {
        G.msg[okey + ":scan"] = "";
        tool.guideScan(view, sc).then(function (res) { G.msg[okey + ":scan"] = res ? T.scanOk + " · " : T.scanFail; G.msg[okey + ":scanlm"] = res ? sc.label : ""; opt.refresh(); });
      }, {"data-g-scan": String(n)}));
    });
    d.appendChild(note(T.scanRule));
    if (smsg) d.appendChild(gEl("div", {class: "g-sub", "data-g": "scan-msg"}, [smsg].concat(G.msg[okey + ":scanlm"] ? [gBdi(G.msg[okey + ":scanlm"])] : [])));
  } else if (m.scan_start != null) d.appendChild(note(T.scanNo));
  row(T.kMan, [txt(m.manoeuvre)], "manoeuvre");
  if (m.show) {
    d.appendChild(btn([T.show], function () { tool.guideShow(view, opt.refresh); opt.refresh(); }, {"data-g-show": "1", disabled: G.busy ? "true" : null}));
    d.appendChild(note(T.showRule));
  }
  row(T.kRisk, [txt(m.at_risk)], "risk");
  if (view.risk.length) {
    var hlOn = !!(G.hl && G.hl.key === view.key && G.hl.side === view.side), anyMapped = view.risk.some(function (rk) { return rk.idx.length > 0; });
    if (anyMapped) d.appendChild(btn([T.riskOn], function () { tool.guideHighlight(view, !hlOn); opt.refresh(); }, {"data-g-risk-on": "1", "aria-pressed": String(hlOn)}));
    var has = !!(tool.target || tool.entry), list = gEl("div", {class: "g-risk"});
    if (anyMapped && has) list.appendChild(note((tool.entry ? T.fromPath : T.fromTarget) + (tool.poseAway() ? " · " + T.posed : "")));
    tool.guideRiskRows(view).forEach(function (g) {
      if (!g.mapped) { list.appendChild(gEl("div", {class: "g-rrow", "data-g-unmapped": g.name}, [gBdi(g.name), ": " + T.unmapped])); return; }
      g.rows.forEach(function (o) {
        var dt = !has ? T.noTarget : !o.measured ? T.notMeasured : o.d == null ? T.beyond(tool.corr.R) : fmt1(o.d) + " " + T.unit;
        var band = has && o.measured && o.d != null ? tool.band(o.d) : "";
        list.appendChild(gEl("div", {class: "g-rrow" + (band ? " band-" + band : ""), "data-g-ids": o.ids.join(" "), "data-g-d": o.d == null ? "" : String(o.d)},
          [gBdi(o.name), (function () { var j = (tool.byId[o.ids[0]] || [])[0], l = j != null && tool.sizeLabel ? tool.sizeLabel(j, lang) : ""; return l ? gEl("span", {class: "g-cls", "data-g-cls": "1", text: " (" + l + ")"}) : null; })(),   // Q367: the size class
           " · ", gEl("span", {class: "g-d", text: dt})]));
      });
    });
    d.appendChild(list);
  }
  var cite = gEl("div", {class: "g-row g-cite", "data-g": "cite"}, [gBdi(view.src.label), " · ", gBdi(m.cite || "")]);
  var full = gEl("div", {class: "g-sub g-full", hidden: "hidden"}, [gBdi(view.src.journal), " · ",
    gEl("a", {href: "https://doi.org/" + view.src.doi, target: "_blank", rel: "noopener", dir: "ltr", text: "doi:" + view.src.doi})]);
  cite.appendChild(document.createTextNode(" "));
  cite.appendChild(btn(["ⓘ"], function () { full.hidden = !full.hidden; this.setAttribute("aria-expanded", String(!full.hidden)); }, {class: "g-i", "aria-label": T.cite, title: T.cite, "aria-expanded": "false"}));
  d.appendChild(cite); d.appendChild(full);
  return d;
}
function fmt1(d) { return (Math.round(d * 10) / 10).toFixed(1); }
TP.renderPlanGuide = function () {   // the needle panel's own copy (English), for the planned muscle
  var host = this.$ ? this.$("ncl-plan-guide") : null; if (!host) return;
  var view = this.plan.i != null && this.guide.data ? this.guideView(this.plan.i) : null;
  if (!view) { if (host.firstChild) host.innerHTML = ""; return; }
  if (!this.active || this.el.hidden || document.body.classList.contains("mode-inj")) return;
  var self = this, phone = global.matchMedia ? global.matchMedia("(max-width:900px)").matches : false;
  host.innerHTML = "";
  host.appendChild(guideDom(this, view, "en", {btn: "", phone: phone, refresh: function () { self.renderPlanGuide(); }}));
};
/* ===================================================================== */
/* Q367 (owner, 2026-11-17): PLAN-FIRST injection planning, one TIP / ENTRY marker pair, and the SAFETY panel.                */
/*  - the plan is assembled from elements in any order: the needle tip (a structure, refined where this body has the data:     */
/*    origin / insertion site, nerve-muscle junction, a PLANE between two structures, perineural, inside a bursa / sheath, the  */
/*    joint space, a free tapped point) and the skin entry (a tap, or one of the computed suggestions). Every element can be    */
/*    set, changed or cleared at any time; the path is drawn as soon as both exist. this.target / this.entry stay the ONE       */
/*    working pair every other part of the tool reads (path, clip, corridor, saved points).                                      */
/*  - markers: Okabe & Ito's colour-universal pair (Color Universal Design, J*Fly 2002/2008): SKY BLUE tip, ORANGE entry --     */
/*    the blue / orange axis stays apart in protan, deutan and tritan vision -- AND different shapes (tip: diamond, entry:     */
/*    ring), each with a dark rim so it reads on skin tones, on muscle red and on the dark scan image. 3-D shapes in the model,  */
/*    fixed-size 2-D pins over the canvas (readable on a phone at any zoom), the same drawing in the scan clip and in the chips.*/
/*  - safety: the USER's own minimum distances per class (nerves large / medium / small, arteries large / medium / small, veins  */
/*    large / medium); empty = rule off (no source the owner's books give states such a figure, so none is pre-filled). Halos   */
/*    of exactly the rule's radius around the structures within reach; the path checked against every rule that is on.        */
/* ===================================================================== */
var MK = {tip: {color: "#56B4E9", edge: "#0B2A3C", he: "קצה המחט", en: "needle tip", shape: "diamond"},
          entry: {color: "#E69F00", edge: "#2B1A00", he: "מעבר בעור", en: "skin entry", shape: "ring"}};
var PLAN_GAP0 = 5, PLAN_GAP_MAX = 20, PLAN_PERI0 = 2, PLAN_PATCH_DRAW = 700, PLAN_JOINT_GAP = 10, PLAN_ADJ = 6;
var SAFE_STORE = "nmsk-inj-safety-v1";
var SAFE_ROWS = [{k: "nL", kind: "n", c: "L"}, {k: "nM", kind: "n", c: "M"}, {k: "nS", kind: "n", c: "S"},
                 {k: "aL", kind: "a", c: "L"}, {k: "aM", kind: "a", c: "M"}, {k: "aS", kind: "a", c: "S"},
                 {k: "vL", kind: "v", c: "L"}, {k: "vM", kind: "v", c: "M"}];
/* size-class thresholds, mm of calibre: [large >=, medium >=]. A CONVENTION (editable on the panel), not a source figure: the
   owner's books state no size classes in mm; these are this project's own Q240 calibre levels (vessels: main >= 6, secondary
   3-6 mm; nerves: trunk >= 4, branches 2-4 mm), so a "large" vessel / nerve here is what the Labels panel already calls level 1. */
var SAFE_THR0 = {n: [4, 2], a: [6, 3], v: [6, 3]};
var SAFE_PAD = 15;                       // a structure is "within reach" when its surface lies within (its rule + 15 mm) of the path / tip
var SAFE_CAP = {desk: 24, phone: 12};    // halos drawn at most (violations first, then the nearest to their rule)
var SAFE_KIND = {nerve: "n", artery: "a", vein: "v"};
var SAFE_COL = {n: "#F2C230", a: "#E5483F", v: "#3D7BE8"};
var SAFE_HE = {n: "עצב", a: "עורק", v: "וריד", L: "גדול", M: "בינוני", S: "קטן"};
var VIOL_COL = "#D63A3A";

function addOcta(g, c, r) {   // a regular octahedron (the tip's diamond), flat-shaded; its vertex centroid is c
  var V = [[r, 0, 0], [-r, 0, 0], [0, r, 0], [0, -r, 0], [0, 0, r], [0, 0, -r]];
  [[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]].forEach(function (f) {
    var a = V[f[0]], b = V[f[1]], d = V[f[2]], n = norm(cross(sub(b, a), sub(d, a)));
    g.idx.push(g.v(add(c, a), n), g.v(add(c, b), n), g.v(add(c, d), n));
  });
  return g;
}
function addRing(g, c, ax, R, rr, seg, sides) {   // a torus around axis ax (the entry's ring), centred on c
  seg = seg || 36; sides = sides || 10;
  if (!(len(ax) > 1e-6)) ax = [0, 0, 1];
  var E = perpBasis(norm(ax)), e1 = E[0], e2 = E[1], u = norm(ax), base = g.count();
  for (var i = 0; i <= seg; i++) {
    var th = 2 * Math.PI * i / seg, dc = add(mul(e1, Math.cos(th)), mul(e2, Math.sin(th))), rc = addS(c, dc, R);
    for (var j = 0; j <= sides; j++) { var ph = 2 * Math.PI * j / sides, n = add(mul(dc, Math.cos(ph)), mul(u, Math.sin(ph))); g.v(addS(rc, n, rr), n); }
  }
  for (var a = 0; a < seg; a++) for (var b = 0; b < sides; b++) {
    var p0 = base + a * (sides + 1) + b, p1 = p0 + sides + 1;
    g.idx.push(p0, p1, p0 + 1, p0 + 1, p1, p1 + 1);
  }
  return g;
}
/* the 2-D drawing of a marker (canvas): the step-sheet chips use the same shapes as CSS; the scan clip calls this */
function drawMk2d(ctx, kind, x, y, s, dashed) {
  var m = MK[kind]; ctx.save(); ctx.lineJoin = "round";
  if (dashed) ctx.setLineDash([3, 2]);
  if (kind === "tip") {
    ctx.beginPath(); ctx.moveTo(x, y - s); ctx.lineTo(x + s, y); ctx.lineTo(x, y + s); ctx.lineTo(x - s, y); ctx.closePath();
    ctx.fillStyle = m.color; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = m.edge; ctx.stroke();
  } else {
    ctx.beginPath(); ctx.arc(x, y, s * 0.78, 0, 6.2832); ctx.lineWidth = s * 0.62; ctx.strokeStyle = m.edge; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, s * 0.78, 0, 6.2832); ctx.lineWidth = s * 0.36; ctx.strokeStyle = m.color; ctx.stroke();
  }
  ctx.restore();
}
function mkSvg(kind, px) {   // the 2-D pin over the 3-D canvas (fixed pixel size)
  var m = MK[kind], h = px / 2;
  if (kind === "tip") return '<svg xmlns="http://www.w3.org/2000/svg" width="' + px + '" height="' + px + '" viewBox="0 0 ' + px + " " + px + '"><path d="M' + h + " 2L" + (px - 2) + " " + h + "L" + h + " " + (px - 2) + "L2 " + h + 'Z" fill="' + m.color + '" stroke="' + m.edge + '" stroke-width="2.4" stroke-linejoin="round"/></svg>';
  return '<svg xmlns="http://www.w3.org/2000/svg" width="' + px + '" height="' + px + '" viewBox="0 0 ' + px + " " + px + '"><circle cx="' + h + '" cy="' + h + '" r="' + (h - 4.2) + '" fill="none" stroke="' + m.edge + '" stroke-width="7"/><circle cx="' + h + '" cy="' + h + '" r="' + (h - 4.2) + '" fill="none" stroke="' + m.color + '" stroke-width="3.6"/></svg>';
}
global.NMSKPlanMarkers = {MK: MK, draw2d: drawMk2d};   // the scan tool's clip draws the same pair (clinical/ultrasound_tool.js)

/* ---------- markers ---------- */
TP.drawMarkers = function () {
  var ov = this.ov, r = this.rDisp || 1;
  ["mk-tip", "mk-tip-x", "mk-entry", "mk-entry-rim", "mk-entry-x"].forEach(ov.remove, ov);
  if (this.target) {
    var gt = addOcta(new Geo(), this.target.p, 2.6 * r);
    ov.set("mk-tip", gt, {color: MK.tip.color, pass: "opaque", emis: 0.35, shin: 60});
    ov.set("mk-tip-x", gt, {color: MK.tip.color, pass: "xray", alpha: 0.55, emis: 0.5});
  }
  if (this.entry) {
    var ax = this.target && dist(this.entry.p, this.target.p) > 1e-3 ? sub(this.target.p, this.entry.p) : (this.entry.n || [0, 0, 1]);
    var R = 3.4 * r, gr = addRing(new Geo(), this.entry.p, ax, R, 0.8 * r);
    ov.set("mk-entry", gr, {color: MK.entry.color, pass: "opaque", emis: 0.3, shin: 50});
    ov.set("mk-entry-rim", addRing(new Geo(), this.entry.p, ax, R + 1.1 * r, 0.38 * r), {color: MK.entry.edge, pass: "opaque"});
    ov.set("mk-entry-x", gr, {color: MK.entry.color, pass: "xray", alpha: 0.5, emis: 0.45});
  }
  /* Q381: in the planning mode the tip's own structure shows through the body as a silhouette in the tip's colour, so a deep tip
     reads as lying inside THAT structure and not on the surface in front of it */
  var gi = this.target && this.injOn() ? this.ghostOf() : null;
  if (ov.setGhosts) ov.setGhosts(gi != null ? [{i: gi, color: MK.tip.color, alpha: GHOST_ALPHA}] : []);
  this.pinsPlace();
};
TP.ghostOf = function () {
  var t = this.target; if (!t) return null;
  if (t.kind === "peri" && t.nerve != null) return t.nerve;
  var i = t.i != null && t.i >= 0 ? t.i : (this.plan.i != null ? this.plan.i : null);
  return i != null && this.skinIdx().indexOf(i) < 0 ? i : null;
};
TP.pinsInit = function () {
  if (this.pins || typeof document === "undefined") return;
  var self = this, host = document.createElement("div"), mk = {};
  host.id = "q367-pins"; host.setAttribute("aria-hidden", "true");
  host.style.cssText = "position:fixed;left:0;top:0;width:0;height:0;pointer-events:none;z-index:80";
  if (!document.getElementById("q381-pin-css")) {   // Q381: the pin's depth tag, its "deep" look, the blocked entry's mark
    var st = document.createElement("style"); st.id = "q381-pin-css"; st.textContent =
      ".q367-pin .q381-tag{position:absolute;left:50%;top:100%;transform:translateX(-50%);margin-top:3px;white-space:nowrap;direction:rtl;font:600 11.5px/1.25 system-ui,-apple-system,'Segoe UI',Arial,sans-serif;" +
      "color:#fff;background:rgba(11,42,60,.88);border-radius:6px;padding:1px 6px;box-shadow:0 0 0 1px rgba(255,255,255,.55)}" +
      ".q367-pin .q381-tag:empty{display:none}" +
      ".q367-pin-tip.q381-deep svg path{fill-opacity:.42;stroke-dasharray:3.2 2.2}" +
      ".q367-pin .q381-x{position:absolute;right:-7px;top:-7px;width:15px;height:15px;border-radius:50%;background:#D63A3A;color:#fff;font:700 11px/15px system-ui,Arial,sans-serif;text-align:center;box-shadow:0 0 0 1.5px #fff;display:none}" +
      ".q367-pin.q381-blocked .q381-x{display:block}.q367-pin.q381-blocked svg{filter:grayscale(.85)}";
    document.head.appendChild(st);
  }
  ["entry", "tip"].forEach(function (k) {
    var px = k === "tip" ? 22 : 26, e = document.createElement("div");
    e.className = "q367-pin q367-pin-" + k; e.dataset.px = px; e.innerHTML = mkSvg(k, px);
    e.style.cssText = "position:fixed;left:0;top:0;width:" + px + "px;height:" + px + "px;display:none;filter:drop-shadow(0 0 1.5px rgba(255,255,255,.9))";
    var tag = document.createElement("span"); tag.className = "q381-tag"; e.appendChild(tag); e._tag = tag;
    if (k === "entry") { var x = document.createElement("span"); x.className = "q381-x"; x.textContent = "\u2715"; e.appendChild(x); }
    host.appendChild(e); mk[k] = e;
  });
  document.body.appendChild(host);
  this.pins = mk;
  if (this.api.webgl && this.api.webgl.onAfterDraw) this.api.webgl.onAfterDraw(function () { self.pinsPlace(); });
};
/* the pins show in the injection mode only (the needle panel keeps its 3-D markers); off-canvas or behind the eye: hidden */
TP.pinsPlace = function () {
  if (!this.pins) return;
  var on = this.active && document.body.classList.contains("mode-inj"), rc = on ? this.api.canvas.getBoundingClientRect() : null, self = this;
  [["tip", this.target], ["entry", this.entry]].forEach(function (x) {
    var e = self.pins[x[0]], s = on && x[1] ? self.api.toScreen(x[1].p) : null, px = +e.dataset.px;
    if (!s || !isFinite(s[0]) || s[0] < rc.left || s[0] > rc.right || s[1] < rc.top || s[1] > rc.bottom) { if (e.style.display !== "none") e.style.display = "none"; e._xy = null; return; }
    e.style.display = ""; e.style.transform = "translate(" + (s[0] - px / 2).toFixed(1) + "px," + (s[1] - px / 2).toFixed(1) + "px)"; e._xy = s;
    /* Q381: the tip's pin says how deep the tip lies under the skin along the line of sight (it changes as the model turns), and is
       drawn hollow and dashed while tissue lies in front of it; the entry's pin is struck out while its path crosses bone */
    if (x[0] === "tip") {
      var dep = self.viewDepth(x[1].p), deep = dep != null && dep > 2, txt = deep ? "בעומק " + dep.toFixed(0) + ' מ"מ' : "";
      e._depth = dep; if (e.classList.contains("q381-deep") !== deep) e.classList.toggle("q381-deep", deep);
      if (e._tag.textContent !== txt) e._tag.textContent = txt;
    } else {
      var blk = self.isBlocked(); if (e.classList.contains("q381-blocked") !== blk) e.classList.toggle("q381-blocked", blk);
    }
  });
};

/* ---------- the plan: tip and entry, in any order ---------- */
TP.plInit = function () { this.pl = {kind: null, gap: PLAN_GAP0, peri: PLAN_PERI0, plane: null, msg: ""}; };
TP.plKeep = function (fn) {   // run a tip setter of the older flows (they clear the entry) and keep the entry the user set
  var e = this.entry; fn.call(this);
  if (e && !this.entry) { this.entry = e; this.update(); }
};
TP.plTipSet = function (pt, kind, extra) {
  this.target = {p: pt.p.slice(), i: pt.i != null && pt.i >= 0 ? pt.i : null, n: null, kind: kind};
  if (extra) Object.keys(extra).forEach(function (k) { this.target[k] = extra[k]; }, this);
  if (pt.ride != null) this.anchorPoint(this.target, pt.ride);   // a tip beside (not in) a structure rides that structure
  this.mp.sel = null; this.pl.kind = kind;
  if (this.mode !== "tfirst") this.setMode("tfirst", true);
  this.clearSuggestions(); this.risk.safer = null;
  ["sp-g", "sp-a", "sp-r", "sp-best", "sp-best-x"].forEach(this.ov.remove, this.ov);
  this.update();
  return this.target;
};
TP.plTipClear = function () { this.target = null; this.pl.kind = null; this.plPlaneClear(); this.clearSuggestions(); this.update(); };
TP.plEntrySet = function (hit) {
  this.entry = {p: hit.p.slice(), i: hit.i != null && hit.i >= 0 ? hit.i : null, n: hit.n || null};
  if (this.mode !== "tfirst") this.setMode("tfirst", true);
  this.clearSuggestions();
  var t = this.target;
  if (t && t.kind === "peri" && !t.tapped) { this.plPeri(t.nerve, null, false); return this.entry; }   // the tip goes to the nerve's side the needle comes from
  this.update();
  return this.entry;
};
TP.plEntryClear = function () { this.entry = null; this.clearSuggestions(); this.update(); };
TP.plRest = function (xyz, s) {   // a point given in REST coordinates (attachment site), ridden to the current pose on structure s
  var w = {p: xyz.slice(), i: s, n: null};
  if (this.poseKey() !== "rest") { this.anchorPoint(w, s, true); if (!this.ridePoint(w)) return null; }
  return w;
};
function vCentroid(pos) { var c = [0, 0, 0], n = pos.length / 3; for (var k = 0; k < pos.length; k += 3) { c[0] += pos[k]; c[1] += pos[k + 1]; c[2] += pos[k + 2]; } return [c[0] / n, c[1] / n, c[2] / n]; }
TP.isNerveT = function (i) { var r = this.recs[i]; return !!r && this.cls[i] === "nerve" && r.cat === "nerve"; };
TP.isSacT = function (i) { var r = this.recs[i]; return !!r && (r.cat === "bursa" || /bursa|tendon_sheath|synovial_sheath|sheaths?_of/.test(r.id)) && !/fibrous_sheath|cruciform|annular/.test(r.id); };
TP.isCapsuleT = function (i) { var r = this.recs[i]; return !!r && /articular_capsule|joint_capsule|(^|_)capsule(_|$)/.test(r.id); };
TP.isMuscleT = function (i) { var r = this.recs[i]; return !!r && !!PLAN_CATS[r.cat]; };
/* origin / insertion sites of a muscle: the Insertions data (Q323) placed on this body -- parts.partsFor() names them, parts.anchors()
   gives their placed coordinates (rest frame) */
TP.plAttach = function (i, ty) {
  var parts = this.api.parts ? this.api.parts() : null, r = this.recs[i];
  if (!r || !parts || !parts.partsFor || !parts.anchors) return [];
  var want = ty === "origin" ? "origin_part" : "insertion_point", pf = parts.partsFor(r.id).filter(function (p) { return p.ty === want && p.placed; });
  if (!pf.length) return [];
  var st = pf[0].id.split(".")[0], side = r.side === "l" || r.side === "r" ? r.side : null, an = parts.anchors(st, side) || [], out = [];
  pf.forEach(function (p) { an.forEach(function (a) { if (a.id === p.id && a.xyz) out.push({id: p.id, name: p.name, xyz: a.xyz.slice(), side: a.side}); }); });
  return out;
};
TP.plUseAttach = function (i, ty, a) {
  var w = this.plRest(a.xyz, i); if (!w) return null;
  return this.plTipSet({p: w.p, i: i}, ty, {ref: a.id, rest: a.xyz.slice(), refName: a.name});
};
/* nerve-muscle junction: the muscle's motor point(s) (clinical_motor_points.json) and its placed IZ bands (innervation_q322.json,
   the same "Use site N" the guide offers); both through their existing setters, the entry kept */
TP.plNmj = function (i) {
  var r = this.recs[i], out = {mp: [], iz: []}; if (!r) return out;
  out.mp = this.planMotorPoints(r);
  var gv = this.guide && this.guide.data ? this.guideView(i) : null;
  if (gv) out.iz = gv.sites.filter(function (s) { return s.st === "placed" && s.dot; }).map(function (s) { return {view: gv, site: s}; });
  return out;
};
TP.plUseMp = function (p) { this.plKeep(function () { this.useMotorPoint(p); }); if (this.target) { this.target.kind = "mp"; this.pl.kind = "mp"; } this.notify(); return this.target; };
TP.plUseIz = function (o) { this.plKeep(function () { this.useGuideSite(o.view, o.site); }); if (this.target) { this.target.kind = "iz"; this.pl.kind = "iz"; } this.notify(); return this.target; };
TP.plCentre = function (i) { this.plKeep(function () { this.setTargetAt(i); }); if (this.target) { this.target.kind = "centre"; this.pl.kind = "centre"; } this.notify(); return this.target; };
/* PERINEURAL: the tip beside the nerve, `off` mm from its surface, never inside it: at the nerve's surface point nearest to the
   reference (a tap on the nerve, else the entry -- the side the needle comes from --, else the nerve's point nearest its own centre),
   pushed out along the direction to the reference (outside) or the outward face normal */
TP.plPeri = function (i, ref, tapped) {
  var g = this.geom(i); if (!g) return null;
  var off = clamp(+this.pl.peri || PLAN_PERI0, 0.5, 20);
  if (!ref && this.entry) ref = this.entry.p;
  if (!ref) ref = closestOnMesh(g.pos, g.idx, vCentroid(g.pos)).q;
  var cm = closestOnMesh(g.pos, g.idx, ref), q = cm.q, dir = null;
  if (cm.d > 0.05 && !this.insideMesh(i, ref)) dir = norm(sub(ref, q));
  else { var F = triFrame(g.pos, g.idx, cm.f); dir = F ? mul(F.n, this.orientSign(i)) : [0, 0, 1]; }
  var tip = addS(q, dir, off);
  if (this.insideMesh(i, tip)) tip = addS(q, dir, -off);
  var host = this.containing(tip, i);
  return this.plTipSet({p: tip, i: host != null && host >= 0 ? host : null, ride: i}, "peri", {nerve: i, off: off, tapped: !!tapped});
};
/* INSIDE A BURSA / TENDON SHEATH: the vertex centre when it lies inside the sac, else the midpoint between the sac's two walls
   at the wall point nearest that centre (a ray along the inward normal to the opposite wall) */
TP.plCavity = function (i) {
  var g = this.geom(i); if (!g) return null;
  var c = vCentroid(g.pos), p = c;
  if (!this.insideMesh(i, c)) {
    var cm = closestOnMesh(g.pos, g.idx, c), F = triFrame(g.pos, g.idx, cm.f), d = F ? mul(F.n, -this.orientSign(i)) : null;
    var hits = d ? this.rayAll(i, addS(cm.q, d, 0.02), d, 1e-4, 200).sort(function (x, y) { return x.t - y.t; }) : [];
    if (hits.length) p = addS(cm.q, d, 0.02 + hits[0].t / 2);
  }
  return this.plTipSet({p: p, i: i}, "cavity", {inside: this.insideMesh(i, p)});
};
/* JOINT SPACE (intra-articular): the two bones the capsule encloses (of the four bones with the most vertices inside the capsule's
   box, >= 20 each, the pair with the largest interface inside the box), the PLANE locus between them (gap <= 10 mm) kept inside the capsule's box, and the locus point nearest the
   capsule's centre. Cartilage is not modelled as a separate surface here, so the space is bone-to-bone: an approximation. */
TP.plJointBones = function (i) {
  var r = this.recs[i], self = this, lo = r.bmin.map(function (v) { return v - 2; }), hi = r.bmax.map(function (v) { return v + 2; }), c = [];
  this.recs.forEach(function (b, j) {
    if (b.cat !== "bone" || !boxOverlap(b.bmin, b.bmax, lo, hi)) return;
    var g = self.geom(j); if (!g) return;
    var n = 0, P = g.pos;
    for (var k = 0; k < P.length; k += 3) if (P[k] >= lo[0] && P[k] <= hi[0] && P[k + 1] >= lo[1] && P[k + 1] <= hi[1] && P[k + 2] >= lo[2] && P[k + 2] <= hi[2]) n++;
    if (n >= 20) c.push({j: j, n: n});
  });
  c.sort(function (x, y) { return y.n - x.n; });
  return c.slice(0, 4).map(function (x) { return x.j; });
};
TP.plIntra = function (i) {
  var cand = this.plJointBones(i); if (cand.length < 2) return null;
  var r = this.recs[i], lo = r.bmin, hi = r.bmax, self = this, res = null, bones = null;
  var inBox = function (m) { return m[0] >= lo[0] && m[0] <= hi[0] && m[1] >= lo[1] && m[1] <= hi[1] && m[2] >= lo[2] && m[2] <= hi[2]; };
  for (var x = 0; x < cand.length; x++) for (var y = x + 1; y < cand.length; y++) {   // the pair (of the 4 bones most inside the box) with the largest interface inside it
    var ga = self.geom(cand[x]), gb = self.geom(cand[y]), q = planeLocus(ga.pos, ga.idx, gb.pos, gb.idx, PLAN_JOINT_GAP, 4000, inBox);
    if (!res || q.pts.length > res.pts.length) { res = q; bones = [cand[x], cand[y]]; }
  }
  if (!res || !res.pts.length) return null;
  var c = [0, 1, 2].map(function (k) { return (lo[k] + hi[k]) / 2; }), best = null, bd = Infinity;
  res.pts.forEach(function (o) { var d = dist(o.m, c); if (d < bd) { bd = d; best = o; } });
  this.pl.plane = {a: bones[0], b: bones[1], gap: PLAN_JOINT_GAP, pts: res.pts, minGap: res.minGap, key: this.poseKey(), intra: i};
  this.drawPatch();
  return this.plTipSet({p: best.m, i: i}, "intra", {bones: bones.slice(), gapHere: best.g});
};
/* PLANE: see planeLocus(). The tip: the patch point nearest the entry when one exists (the side the needle comes from), else the
   point nearest the patch's centre; a tap on the model then snaps the tip to the nearest patch point. */
TP.plPlane = function (a, b, gap) {
  if (gap != null && isFinite(gap)) this.pl.gap = clamp(+gap, 1, PLAN_GAP_MAX);
  var ga = this.geom(a), gb = this.geom(b); if (!ga || !gb || a === b) return null;
  var res = planeLocus(ga.pos, ga.idx, gb.pos, gb.idx, this.pl.gap, 3000);
  this.pl.plane = {a: a, b: b, gap: this.pl.gap, pts: res.pts, minGap: res.minGap, key: this.poseKey()};
  this.drawPatch();
  if (!res.pts.length) { this.notify(); this.api.redraw(); return {n: 0, minGap: res.minGap}; }
  var ref = this.entry ? this.entry.p : vCentroid([].concat.apply([], res.pts.map(function (o) { return o.m; })));
  this.plPlaneSnap(ref);
  return {n: res.pts.length, minGap: res.minGap};
};
TP.plPlaneSnap = function (p) {
  var P = this.pl.plane; if (!P || !P.pts.length) return null;
  var best = null, bd = Infinity;
  P.pts.forEach(function (o) { var d = dist(o.m, p); if (d < bd) { bd = d; best = o; } });
  return this.plTipSet({p: best.m, i: P.a}, P.intra != null ? "intra" : "plane", {plane: {a: P.a, b: P.b}, gapHere: best.g});
};
TP.plPlaneClear = function () { if (this.pl && this.pl.plane) { this.pl.plane = null; this.drawPatch(); } };
TP.drawPatch = function () {
  var ov = this.ov; ov.remove("q367-patch"); ov.remove("q367-patch-x");
  var P = this.pl.plane; if (!P || !P.pts.length) { this.api.redraw(); return; }
  var pts = P.pts, step = Math.max(1, Math.ceil(pts.length / PLAN_PATCH_DRAW)), sel = pts.filter(function (o, k) { return k % step === 0; });
  var g = chunked(sel, function (gg, o) { addSphere(gg, o.m, 0.75, 6, 4); });
  ov.set("q367-patch", g, {color: "#B79CFF", pass: "trans", alpha: 0.6, emis: 0.5, order: 3});
  ov.set("q367-patch-x", g, {color: "#B79CFF", pass: "xray", alpha: 0.22, emis: 0.5});
  this.api.redraw();
};
TP.plPoseRefresh = function () {   // the patch follows the pose (the tip itself rides its structure)
  var P = this.pl && this.pl.plane; if (!P || P.key === this.poseKey()) return;
  var ga = this.geom(P.a), gb = this.geom(P.b); if (!ga || !gb) return;
  var lo = P.intra != null ? this.recs[P.intra].bmin : null, hi = P.intra != null ? this.recs[P.intra].bmax : null;
  var res = planeLocus(ga.pos, ga.idx, gb.pos, gb.idx, P.gap, P.intra != null ? 4000 : 3000, lo ? function (m) { return m[0] >= lo[0] && m[0] <= hi[0] && m[1] >= lo[1] && m[1] <= hi[1] && m[2] >= lo[2] && m[2] <= hi[2]; } : null);
  P.pts = res.pts; P.minGap = res.minGap; P.key = this.poseKey();
  this.drawPatch();
};
/* adjacent structures for the plane's second side: muscles / tendons / fascia / ligaments whose box overlaps A's box grown by the
   gap, largest overlap first (a hint list; any structure can be picked) */
TP.plAdjacent = function (a) {
  var r = this.recs[a], g = this.pl.gap, lo = r.bmin.map(function (v) { return v - g; }), hi = r.bmax.map(function (v) { return v + g; }), out = [], seen = {};
  this.recs.forEach(function (s, j) {
    if (j === a || seen[s.id] || !/^(muscle|insertion|tendon|fascia|ligament|joint)$/.test(s.cat) || !boxOverlap(s.bmin, s.bmax, lo, hi)) return;
    var v = 1; for (var k = 0; k < 3; k++) v *= Math.max(0, Math.min(hi[k], s.bmax[k]) - Math.max(lo[k], s.bmin[k]));
    out.push({j: j, v: v}); seen[s.id] = 1;
  });
  out.sort(function (x, y) { return y.v - x.v; });
  return out.slice(0, PLAN_ADJ).map(function (x) { return x.j; });
};
/* which refinements this target offers on THIS body (a refinement with no data here is not offered; `missing` names them) */
TP.plOffers = function (i) {
  var o = {centre: true, free: true, plane: true, origin: [], insertion: [], mp: [], iz: [], peri: false, cavity: false, intra: false, missing: []};
  if (i == null || !this.recs[i]) return o;
  if (this.isMuscleT(i)) {
    o.origin = this.plAttach(i, "origin"); o.insertion = this.plAttach(i, "insertion");
    var nm = this.plNmj(i); o.mp = nm.mp; o.iz = nm.iz;
    if (!o.origin.length) o.missing.push("origin");
    if (!o.insertion.length) o.missing.push("insertion");
    if (!o.mp.length && !o.iz.length) o.missing.push("nmj");
  }
  o.peri = this.isNerveT(i);
  o.cavity = this.isSacT(i);
  if (this.isCapsuleT(i)) { if (this.plIntraOk == null) this.plIntraOk = {}; if (this.plIntraOk[i] == null) this.plIntraOk[i] = this.plJointBones(i).length >= 2; o.intra = this.plIntraOk[i]; if (!o.intra) o.missing.push("intra"); }
  return o;
};

/* ---------- safety: the user's own distance rules ---------- */
TP.safeInit = function () {
  var S = this.safe = {rules: {}, thr: JSON.parse(JSON.stringify(SAFE_THR0)), rows: [], viol: [], halos: [], segs: [], unk: 0, nOn: 0, seq: 0, timer: 0, stored: false};
  try {
    var j = JSON.parse(global.localStorage.getItem(SAFE_STORE) || "null");
    if (j && j.r) SAFE_ROWS.forEach(function (row) { var v = +j.r[row.k]; if (v > 0 && isFinite(v)) S.rules[row.k] = clamp(v, 0.1, 100); });
    if (j && j.t) ["n", "a", "v"].forEach(function (k) { var t = j.t[k]; if (t && t.length === 2 && +t[0] >= +t[1] && +t[1] > 0) S.thr[k] = [+t[0], +t[1]]; });
    S.stored = !!j;
  } catch (e) {}
  this.sizeCache = {};
  this.vcal = null;
};
TP.safeSave = function () {
  try { global.localStorage.setItem(SAFE_STORE, JSON.stringify({r: this.safe.rules, t: this.safe.thr})); this.safe.stored = true; } catch (e) {}
};
TP.safeSet = function (o) {   // {rules: {nL: mm|null, ...}, thr: {n: [L, M], ...}} -- partial updates; null / empty / <= 0 = rule off
  var S = this.safe;
  if (o.rules) Object.keys(o.rules).forEach(function (k) { var v = o.rules[k]; if (v === "" || v == null || !(+v > 0)) delete S.rules[k]; else S.rules[k] = clamp(+v, 0.1, 100); });
  if (o.thr) { Object.keys(o.thr).forEach(function (k) { var t = o.thr[k]; if (t && +t[0] > 0 && +t[1] > 0) S.thr[k] = [Math.max(+t[0], +t[1]), Math.min(+t[0], +t[1])]; }); this.sizeCache = {}; }
  this.safeSave();
  this.safeRun();
};
TP.calNerves = function () {
  if (this._caln) return this._caln;
  var c = {};
  try { var e = document.getElementById("nmsk-calibre"); if (e && e.textContent.trim().length > 2) { var j = JSON.parse(e.textContent); if (j && j.c) c = j.c; } } catch (er) {}
  return (this._caln = c);
};
TP.sizeOf = function (i) {
  if (this.sizeCache[i] !== undefined) return this.sizeCache[i];
  var k = SAFE_KIND[this.cls[i]], out = null;
  if (k) {
    var id = this.recs[i].id, d = null, p = 0, src = null;
    if (k === "n") { var e = this.calNerves()[id]; if (e) { d = e[1]; p = e[3] ? 1 : 0; src = "nmsk-calibre"; } }
    else { var v = this.vcal && this.vcal[id]; if (v) { d = v[0]; p = v[1] ? 1 : 0; src = "mesh"; } }
    out = {k: k, d: d, p: p, c: sizeClass(d, p, this.safe.thr[k]), src: src};
  }
  if (this.vcal || k === "n") this.sizeCache[i] = out;   // vessels are cached once their calibre file has loaded
  return out;
};
TP.sizeLabel = function (i, lang) {
  var s = this.sizeOf(i); if (!s) return "";
  if (lang === "en") return ({n: "nerve", a: "artery", v: "vein"})[s.k] + ", " + (s.c ? ({L: "large", M: "medium", S: "small"})[s.c] : "calibre unknown");
  return SAFE_HE[s.k] + " " + (s.c ? SAFE_HE[s.c] : "· קוטר לא ידוע");
};
TP.safeSchedule = function () {
  var self = this, S = this.safe; if (!S) return;
  clearTimeout(S.timer); S.timer = setTimeout(function () { S.timer = 0; self.safeRun(); }, 90);
};
/* the check: every artery / vein / nerve with a rule ON for its class whose surface lies within (rule + 15 mm) of the planned
   segment (entry -> tip; the tip or the entry alone before both exist) -- exact distance to the page's own triangles (meshSegDist,
   the corridor's measurement) on the current (posed) meshes. The target's own structure (a perineural nerve) is not checked. */
TP.safeRun = function () {
  var S = this.safe, self = this; if (!S) return;
  clearTimeout(S.timer); S.timer = 0;
  var A = this.entry ? this.entry.p : null, B = this.target ? this.target.p : null, t0 = performance.now();
  S.seq++; S.rows = []; S.viol = []; S.halos = []; S.segs = []; S.unk = 0;
  S.nOn = SAFE_ROWS.filter(function (r) { return S.rules[r.k] > 0; }).length;
  if (S.nOn && (A || B)) {
    if (!A) A = B; if (!B) B = A;
    var maxR = 0; SAFE_ROWS.forEach(function (r) { if (S.rules[r.k] > maxR) maxR = S.rules[r.k]; });
    var skip = this.target ? [this.target.i, this.target.nerve] : [];
    this.recs.forEach(function (r, i) {
      if (!SAFE_KIND[self.cls[i]] || skip.indexOf(i) >= 0 || !boxHitsSegment(r.bmin, r.bmax, A, B, maxR + SAFE_PAD)) return;
      var sz = self.sizeOf(i); if (!sz) return;
      if (!sz.c) { if (S.rules[sz.k + "L"] > 0 || S.rules[sz.k + "M"] > 0 || S.rules[sz.k + "S"] > 0) S.unk++; return; }
      var rule = S.rules[sz.k + sz.c]; if (!(rule > 0) || !boxHitsSegment(r.bmin, r.bmax, A, B, rule + SAFE_PAD)) return;
      var g = self.geom(i); if (!g) return;
      var m = meshSegDist(g.pos, g.idx, A, B, rule + SAFE_PAD + 1e-6); if (!(m.d <= rule + SAFE_PAD)) return;
      S.rows.push({i: i, id: r.id, name: self.name(i), side: r.side, k: sz.k, c: sz.c, dia: sz.d, p: sz.p, d: m.d, rule: rule, viol: m.d < rule});
    });
    S.rows.sort(function (x, y) { return (y.viol - x.viol) || ((x.d - x.rule) - (y.d - y.rule)); });
    S.viol = S.rows.filter(function (x) { return x.viol; });
    var phone = global.matchMedia ? global.matchMedia("(max-width:760px)").matches : false, cap = phone ? SAFE_CAP.phone : SAFE_CAP.desk;
    S.cap = cap; S.halos = S.rows.slice(0, Math.max(cap, 0));
    /* the offending stretch of the path: 1 mm samples whose own distance to the structure is below its rule */
    var L = dist(A, B);
    S.viol.slice(0, 8).forEach(function (v) {
      var g = self.geom(v.i);
      if (L < 1e-3) { S.segs.push({a: A, b: A, i: v.i}); return; }
      var n = Math.max(2, Math.ceil(L)), run = null;
      for (var s = 0; s <= n; s++) {
        var P = [A[0] + (B[0] - A[0]) * s / n, A[1] + (B[1] - A[1]) * s / n, A[2] + (B[2] - A[2]) * s / n];
        var bad = meshSegDist(g.pos, g.idx, P, P, v.rule + 1e-6).d < v.rule;
        if (bad && !run) run = {a: P, b: P, i: v.i}; else if (bad) run.b = P;
        if ((!bad || s === n) && run) { S.segs.push(run); run = null; }
      }
    });
  }
  S.ms = performance.now() - t0;
  this.drawViolations();
  this.refreshHalos();
  this.notify();
};
TP.drawViolations = function () {
  var ov = this.ov, S = this.safe; ov.remove("q367-viol"); ov.remove("q367-viol-x");
  if (!S || !S.segs.length) return;
  var g = new Geo(), r = 1.15 * (this.rDisp || 1);
  S.segs.forEach(function (s) { if (dist(s.a, s.b) < 0.5) addSphere(g, s.a, 2.4 * r, 14, 10); else addTube(g, s.a, s.b, r * 1.25, r * 1.25, 18, {capA: true, capB: true}); });
  ov.set("q367-viol", g, {color: VIOL_COL, pass: "opaque", emis: 0.45});
  ov.set("q367-viol-x", g, {color: VIOL_COL, pass: "xray", alpha: 0.7, emis: 0.5});
};
/* the rule halos: the structure's own (posed) mesh inflated along its normals by exactly the rule (mm) -- the overlay's halo pass */
TP.safeHalos = function () {
  var self = this;
  return this.safe.halos.map(function (x) { return {i: x.i, r: x.rule * self.orientSign(x.i), color: SAFE_COL[x.k], alpha: x.viol ? 0.42 : 0.16, rule: x.rule, viol: x.viol, safe: true}; });
};
TP.loadSafety = function () {
  var self = this;
  fetch("clinical_vessel_calibre.json", {cache: "no-cache"}).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (j) {
    self.vcal = j && j.schema === "nmsk.vessel_calibre.v1" && j.c ? j.c : {};
    self.vcalMeta = j && j.c ? {n: j.n, method: j.method} : null;
    self.sizeCache = {};
    if (self.safe.nOn) self.safeRun(); else self.notify();
  });
};
/* test / harness view of the plan and the safety check */
TP.q367 = function () {
  var t = this.target, e = this.entry, S = this.safe, P = this.pl.plane, self = this;
  return {tip: t ? {p: t.p.slice(), i: t.i, kind: t.kind || null, ref: t.ref || null, nerve: t.nerve, off: t.off} : null, entry: e ? {p: e.p.slice(), i: e.i} : null,
          kind: this.pl.kind, plane: P ? {a: P.a, b: P.b, gap: P.gap, n: P.pts.length, minGap: P.minGap, intra: P.intra} : null,
          safe: {rules: JSON.parse(JSON.stringify(S.rules)), thr: JSON.parse(JSON.stringify(S.thr)), seq: S.seq, nOn: S.nOn, unk: S.unk, cap: S.cap, ms: S.ms,
                 rows: S.rows.map(function (x) { return {i: x.i, id: x.id, k: x.k, c: x.c, d: x.d, rule: x.rule, viol: x.viol, dia: x.dia}; }),
                 halos: S.halos.map(function (x) { return {i: x.i, id: x.id, r: x.rule, viol: x.viol}; }), segs: S.segs.length},
          pins: this.pins ? {tip: this.pins.tip._xy || null, entry: this.pins.entry._xy || null} : null, sizeOf: function (i) { return self.sizeOf(i); }};
};

/* ===================================================================== */
/* Q381 (owner, 2026-11-19, after testing the live Base·Male page)                                                              */
/*  A. "A needle cannot pass through bones": ONE geometric test of the straight path entry -> tip against the page's bone meshes   */
/*     and hyaline cartilage, in the CURRENT pose (boneCheck), run on every placement change (update(): a suggested entry, a      */
/*     tapped one, a tip moved afterwards, a pose change afterwards). A path that crosses is BLOCKED: the bone is named, the path */
/*     is drawn red from the first bone on, it is not played in the scan and not saved, and the nearest valid entry is computed    */
/*     and offered (entryNear). Suggestions / "shortest entry" / the safer pathways only ever propose bone-free paths (the region's */
/*     bone grid for the search; every candidate SHOWN is confirmed by boneCheck). When no straight bone-free path exists for a    */
/*     tip the panel says so. Ligaments, membranes, capsules, fibrocartilage: NO rule (no source at hand says a needle cannot pass */
/*     them) -- the ones a path crosses are listed on the distance card, nothing more.                                             */
/*  B. the tip's default point is INSIDE its structure (meshCentre), on the current (posed) mesh; what is true of the tip is       */
/*     measured and shown (inside / on / outside its structure, its depth below that surface, the nearest skin); the 2-D pin       */
/*     carries the depth below the skin along the line of sight and a "deep" look, and the target's own silhouette shows through.  */
/* ===================================================================== */
/* the cartilage layer's HYALINE pieces: articular and costal cartilage and the triradiate (growth) cartilage. Its intervertebral
   discs, menisci, labra and the pubic symphysis are fibrocartilage (standard histology, e.g. Gray's Anatomy for Students, ch. 1,
   "Cartilage"): not blocking. The owner's rule (Q381): bone and hyaline cartilage block. */
var HYALINE_RE = /articular_cartilage|costal_cartilage|triradiate_cartilage/;
var TIP_TOUCH_MM = 0.5;    // a tip resting on a bone surface (an attachment site) touches the bone; whatever the path meets earlier than this before the tip is a crossing
var BONE_CLEAR_MM = 1.0;   // an OFFERED entry keeps its path at least this far from bone until 3 mm before the tip (a convention: the needle's radius and a little)
var PASS_CATS = {joint: 1, ligament: 1, cartilage: 1};   // crossed -> listed, never blocking
var GHOST_ALPHA = 0.34;
TP.blockers = function () {
  if (!this.blk) {
    var self = this, b = this.blk = [], is = this.blkIs = {};
    this.recs.forEach(function (r, i) { if (self.cls[i] === "bone" || (r.cat === "cartilage" && HYALINE_RE.test(r.id))) { b.push(i); is[i] = 1; } });
  }
  return this.blk;
};
TP.isBlocker = function (i) { this.blockers(); return this.blkIs[i] === 1; };
/* THE test. A -> B (entry -> tip), current pose: {L, blocked, hits: [{i, id, name, side, t, n}] (first crossing of each blocking
   structure, mm from A, nearest first), first: {i, t, p}, touch: [i] (met only within TIP_TOUCH_MM of the tip: the tip rests on it)} */
TP.boneCheck = function (A, B) {
  var self = this, L = dist(A, B), out = {L: L, blocked: false, hits: [], first: null, touch: []};
  if (!(L > 1e-6)) return out;
  this.blockers().forEach(function (i) {
    var r = self.recs[i]; if (!boxHitsSegment(r.bmin, r.bmax, A, B, 0.05)) return;
    var g = self.geom(i); if (!g) return;
    var hs = segMeshHits(g.pos, g.idx, A, B); if (!hs.length) return;
    var ts = []; hs.forEach(function (h) { if (!ts.length || h.t - ts[ts.length - 1] > 0.02) ts.push(h.t); });   // a shared edge is one crossing
    var cr = ts.filter(function (t) { return t < L - TIP_TOUCH_MM; });
    if (cr.length) out.hits.push({i: i, id: r.id, name: self.name(i), side: r.side, t: cr[0], n: cr.length});
    else out.touch.push(i);
  });
  out.hits.sort(function (x, y) { return x.t - y.t; });
  if (out.hits.length) { var h0 = out.hits[0], u = mul(sub(B, A), 1 / L); out.blocked = true; out.first = {i: h0.i, t: h0.t, p: addS(A, u, h0.t)}; }
  return out;
};
/* the path's clearance from bone over its first L - 3 mm (the last 3 mm belong to the tip, which may rest on a bone) */
TP.boneClear = function (A, B) {
  var self = this, L = dist(A, B), best = Infinity; if (L < 3.5) return Infinity;
  var B2 = addS(A, mul(sub(B, A), 1 / L), L - 3);
  this.blockers().forEach(function (i) {
    var r = self.recs[i]; if (!boxHitsSegment(r.bmin, r.bmax, A, B2, BONE_CLEAR_MM + 0.05)) return;
    var g = self.geom(i); if (!g) return;
    var m = meshSegDist(g.pos, g.idx, A, B2, Math.min(best, BONE_CLEAR_MM + 0.05)); if (m.d < best) best = m.d;
  });
  return best;
};
/* a candidate direction's bone test on the region's grid (fast; the search only -- what is shown or offered is confirmed by boneCheck) */
TP.boneFreeRay = function (reg, T, u, L) { return !reg.bone.ntris || !reg.bone.ray(T, u, TIP_TOUCH_MM, Math.max(TIP_TOUCH_MM, L - 0.05)).length; };
TP.pathValid = function (E, T) { return !this.boneCheck(E, T).blocked && this.boneClear(E, T) >= BONE_CLEAR_MM; };
/* the valid entry nearest to E0 (the entry the user chose, whose path is blocked): every skin point reached by a straight bone-free
   path from the tip, over 1500 directions of the sphere and a 25-degree cone around the chosen direction, nearest to E0 first; the
   nearest that passes the exact test (boneCheck, >= BONE_CLEAR_MM from bone) is then walked back toward E0 along the arc between the
   two directions (6 bisections) to the last valid point. {E, entryI, u, L, d} or {none: true, tried, skin, free, reach}. */
TP.entryNear = function (E0) {
  var T = this.target.p, L0 = dist(E0, T), reach = Math.ceil(clamp(Math.max(this.len, L0 * 1.25 + 10), 20, 200)), reg = this.region(T, reach), self = this;
  var u0 = L0 > 1e-6 ? norm(sub(E0, T)) : [0, 0, 1], cands = [], nSkin = 0, nFree = 0, tried = 0;
  function tryDir(u) {
    tried++;
    var en = self.entryFor(reg, T, u, reach); if (!en.ok || en.obstructed) return null;
    nSkin++;
    if (!self.boneFreeRay(reg, T, u, en.L)) return null;
    nFree++;
    return {E: en.E, entryI: en.entryI, u: u, L: en.L, d: dist(en.E, E0)};
  }
  var dirs = fibonacciSphere(1500), k, c;
  for (k = 0; k < 1500; k++) { c = tryDir([dirs[3 * k], dirs[3 * k + 1], dirs[3 * k + 2]]); if (c) cands.push(c); }
  coneDirs(u0, 25 * Math.PI / 180, 300).forEach(function (u) { var c2 = tryDir(u); if (c2) cands.push(c2); });
  cands.sort(function (x, y) { return x.d - y.d; });
  var best = null;
  for (k = 0; k < cands.length && k < 60 && !best; k++) if (this.pathValid(cands[k].E, T)) best = cands[k];
  if (!best) return {none: true, tried: tried, skin: nSkin, free: nFree, reach: reach};
  var lo = 0, hi = 1;   // m = 0: the chosen (blocked) direction, m = 1: the valid one
  for (k = 0; k < 6; k++) {
    var m = (lo + hi) / 2, u = norm(add(mul(u0, 1 - m), mul(best.u, m))), en = this.entryFor(reg, T, u, reach);
    if (en.ok && !en.obstructed && this.boneFreeRay(reg, T, u, en.L) && this.pathValid(en.E, T)) { hi = m; best = {E: en.E, entryI: en.entryI, u: u, L: en.L, d: dist(en.E, E0)}; }
    else lo = m;
  }
  best.reach = reach;
  return best;
};
TP.blockRun = function () {
  var e = this.entry, t = this.target, B = this.block = {res: null, alt: undefined, seq: (this.blockSeq = (this.blockSeq || 0) + 1)}, self = this;
  clearTimeout(this.blockT); this.blockT = 0;
  if (!e || !t) return;
  B.res = this.boneCheck(e.p, t.p);
  if (!B.res.blocked || this.mode === "dir") return;
  this.blockT = setTimeout(function () {
    self.blockT = 0;
    if (self.block !== B || !self.entry || !self.target) return;
    B.alt = self.entryNear(self.entry.p);
    self.drawBlock(); self.api.redraw(); self.notify();
  }, 140);
};
TP.injOn = function () { return typeof document !== "undefined" && !!document.body && document.body.classList.contains("mode-inj"); };
TP.isBlocked = function () { return !!(this.block && this.block.res && this.block.res.blocked && this.entry && this.target); };
TP.useAltEntry = function () {
  var a = this.block && this.block.alt; if (!a || !a.E) return false;
  this.entry = {p: a.E.slice(), i: a.entryI, n: mul(a.u, -1)};
  this.clearSuggestions(); this.update();
  return true;
};
TP.drawBlock = function () {
  var ov = this.ov; ["q381-blk", "q381-blk-x", "q381-alt", "q381-alt-x"].forEach(ov.remove, ov);
  if (!this.isBlocked()) return;
  var B = this.block, T = this.target.p, f = B.res.first, r = this.rDisp || 1, g = new Geo();
  addSphere(g, f.p, 2.3 * r, 14, 10);
  if (dist(f.p, T) > 0.5) addTube(g, f.p, T, r * 1.3, r * 1.3, 14, {capA: true, capB: true});
  ov.set("q381-blk", g, {color: VIOL_COL, pass: "opaque", emis: 0.45});
  ov.set("q381-blk-x", g, {color: VIOL_COL, pass: "xray", alpha: 0.75, emis: 0.5});
  if (B.alt && B.alt.E) {
    var ga = addRing(new Geo(), B.alt.E, sub(T, B.alt.E), 3.4 * r, 0.6 * r), L = dist(B.alt.E, T), u = norm(sub(T, B.alt.E)), rr = 0.3 * r + 0.12;
    for (var s = 0; s < L; s += 4.5) addTube(ga, addS(B.alt.E, u, s), addS(B.alt.E, u, Math.min(L, s + 2.5)), rr, rr, 8, {});
    ov.set("q381-alt", ga, {color: ALT_COL, pass: "trans", alpha: 0.85, emis: 0.45, order: 5});
    ov.set("q381-alt-x", ga, {color: ALT_COL, pass: "xray", alpha: 0.4, emis: 0.45});
  }
};
var ALT_COL = "#2FA866";
/* the structures of the "passes through" list: ligaments / membranes / capsules / fibrocartilage a path crosses (not blocking) */
TP.passList = function (A, B) {
  var self = this, L = dist(A, B), out = [], skip = this.target ? this.target.i : null; if (!(L > 1e-6)) return out;
  this.recs.forEach(function (r, i) {
    if (!PASS_CATS[r.cat] || i === skip || self.isBlocker(i) || !boxHitsSegment(r.bmin, r.bmax, A, B, 0.05)) return;
    var g = self.geom(i); if (!g) return;
    var hs = segMeshHits(g.pos, g.idx, A, B).filter(function (h) { return h.t > 0.05 && h.t < L - 0.05; });
    if (hs.length) out.push({i: i, id: r.id, name: self.name(i), side: r.side, t: hs[0].t});
  });
  out.sort(function (x, y) { return x.t - y.t; });
  return out;
};
/* ---- B: a point inside the structure, on the mesh as it is now ---- */
TP.centreOf = function (i) {
  var key = this.poseKey(), store = key === "rest" ? this.cRest : this.cPose, c = store[i];
  if (c && c.key === key) return c;
  var g = this.geom(i); if (!g) return null;
  var self = this, r = this.recs[i], near = this.blockers().filter(function (j) { return j !== i && boxOverlap(self.recs[j].bmin, self.recs[j].bmax, r.bmin, r.bmax); });
  c = meshCentre(g.pos, g.idx, {reject: function (p) {
    return near.some(function (j) { var b = self.recs[j]; return p[0] >= b.bmin[0] && p[1] >= b.bmin[1] && p[2] >= b.bmin[2] && p[0] <= b.bmax[0] && p[1] <= b.bmax[1] && p[2] <= b.bmax[2] && self.insideMesh(j, p); });
  }});
  c.key = key; store[i] = c;
  return c;
};
TP.plCentreFollow = function () {   // after a pose change the centre is taken again on the posed mesh (it rode its anchor during the move)
  var t = this.target; if (!t || t.kind !== "centre" || t.i == null) return false;
  var c = this.centreOf(t.i); if (!c || dist(c.p, t.p) < 1e-6) return false;
  t.p = c.p.slice(); t._anc = null;
  return true;
};
TP.skinIdx = function () {
  if (!this.skinLayer) this.skinLayer = this.recs.filter(function (r) { return r.cat === "skin" || /^skin(_|$)/.test(r.id); }).map(function (r) { return r.i; });
  return this.skinLayer;
};
TP.raySkin = function (o, d, far) {   // every skin crossing of the ray o + t d, t in (0, far], nearest first: [{t, i, n}]
  var self = this, B = addS(o, d, far), out = [];
  this.skinIdx().forEach(function (i) {
    var r = self.recs[i]; if (!boxHitsSegment(r.bmin, r.bmax, o, B, 0.5)) return;
    self.rayAll(i, o, d, 1e-4, far).forEach(function (h) { out.push({t: h.t, i: i, n: h.n}); });
  });
  out.sort(function (x, y) { return x.t - y.t; });
  return out;
};
/* a tap for the SKIN ENTRY lands on the skin under the pointer -- whatever the skin's look (faded, translucent, hidden): the first
   skin surface the pointer's ray meets (not in the half a cut removed). null when no skin lies under the pointer. */
TP.pickSkin = function (e) {
  var R = this.api.ray(e), cut = this.api.cut(), hs = this.raySkin(R.o, R.d, 5000);
  for (var k = 0; k < hs.length; k++) {
    var p = addS(R.o, R.d, hs[k].t); if (cut && dot(cut, p) + cut[3] < -1e-6) continue;
    var n = hs[k].n; if (n && dot(n, R.d) < 0) n = mul(n, -1);
    return {i: hs[k].i, p: p, n: n, t: hs[k].t, ray: R.d, skin: true};
  }
  return null;
};
/* mm of body in front of p along the line of sight: from p toward the eye, the skin over p (skin surfaces within SKIN_STACK_MM of
   the first are one skin). null when no skin lies between p and the eye. */
TP.viewDepth = function (p) {
  var v = this.api.view(); if (!v || !v.eye) return null;
  var d = sub(v.eye, p), L = len(d); if (L < 1e-6) return null;
  var key = v.eye.map(function (x) { return x.toFixed(1); }).join(",") + "|" + p.map(function (x) { return x.toFixed(2); }).join(",") + "|" + this.poseKey();
  if (this.vdKey === key) return this.vdVal;
  var hs = this.raySkin(p, mul(d, 1 / L), Math.min(L, 3000)), out = null;
  if (hs.length) { var k0 = 0; while (k0 + 1 < hs.length && hs[k0 + 1].t <= hs[0].t + SKIN_STACK_MM) k0++; out = hs[k0].t; }
  this.vdKey = key; this.vdVal = out;
  return out;
};
/* what is true of the tip, measured on the current meshes: {host, rel: "in" | "on" | "out" | null, dOwn, dSkin}. rel is given for the
   kinds that claim a place IN a structure (its centre, a tapped point, a motor point, an IZ band); null for the others. */
var TIP_IN_KINDS = {centre: 1, free: 1, mp: 1, iz: 1};
TP.tipFacts = function () {
  var t = this.target; if (!t) return null;
  var self = this, p = t.p, f = {host: null, rel: null, dOwn: null, dSkin: null, kind: t.kind || null};
  var host = t.i != null && t.i >= 0 && (!t.kind || TIP_IN_KINDS[t.kind]) && !t.computed ? t.i : null;
  if (host != null && this.skinIdx().indexOf(host) < 0) {
    var g = this.geom(host);
    if (g) { var cm = closestOnMesh(g.pos, g.idx, p); f.host = host; f.dOwn = cm.d; f.rel = cm.d <= 0.3 ? "on" : (this.insideMesh(host, p) ? "in" : "out"); }
  }
  var best = Infinity;
  this.skinIdx().map(function (i) { var r = self.recs[i], d = 0; for (var k = 0; k < 3; k++) { var dk = Math.max(r.bmin[k] - p[k], 0, p[k] - r.bmax[k]); d += dk * dk; } return {i: i, d: Math.sqrt(d)}; })
    .sort(function (x, y) { return x.d - y.d; }).some(function (x) {
      if (x.d >= best) return true;
      var g2 = self.geom(x.i); if (!g2) return false;
      var m = meshSegDist(g2.pos, g2.idx, p, p, best); if (m.d < best) best = m.d;
      return false;
    });
  if (best < Infinity) f.dSkin = best;
  return f;
};
/* test / harness view */
TP.q381 = function () {
  var B = this.block, R = B && B.res, f = this.tipF, self = this;
  return {blocked: this.isBlocked(), block: R ? {blocked: R.blocked, L: R.L, first: R.first, touch: R.touch.map(function (i) { return self.recs[i].id; }),
                                                 hits: R.hits.map(function (h) { return {id: h.id, t: h.t, n: h.n}; })} : null,
          alt: B ? (B.alt === undefined ? "pending" : B.alt) : null, blockers: this.blockers().length,
          facts: f ? {host: f.host != null ? this.recs[f.host].id : null, rel: f.rel, dOwn: f.dOwn, dSkin: f.dSkin, kind: f.kind} : null,
          pass: (this.corr.pass || []).map(function (x) { return {id: x.id, t: x.t}; }),
          pin: this.pins && this.pins.tip ? {deep: this.pins.tip.classList.contains("q381-deep"), tag: this.pins.tip._tag ? this.pins.tip._tag.textContent : "", depth: this.pins.tip._depth == null ? null : this.pins.tip._depth,
                                             entryBlocked: this.pins.entry.classList.contains("q381-blocked")} : null,
          ghosts: this.ov.ghostsNow ? this.ov.ghostsNow() : null, sugg: {none: this.sugg.none || null, skin: this.sugg.nSkin, free: this.sugg.nFree, longer: this.sugg.longer || null}};
};

/* ---------- Q272: the "תכנון הזרקה" WORKSPACE MODE -- a re-skin of this tool's own Q268 logic (preset, live distance readout,
   suggested entries, halo, posture), hosted by the page's generic mode layer (viewer/modes/, window.NMSKModes). Nothing is
   re-implemented here: every button calls the same methods the needle panel's own buttons call. RTL Hebrew copy per the owner's
   approved mockups. ---------- */
/* Q273: the tool's own suggestion messages (English, shown in its own panel) rendered in Hebrew inside the mode's step card */
function heMsg(m) {
  var r;
  if (/^Set a target first/.test(m)) return "בחרו מטרה תחילה.";
  if ((r = /^No skin within the (\d+(?:\.\d+)?) mm needle length/.exec(m))) return "אין עור בטווח אורך המחט (" + r[1] + " מ\"מ): אין מועמדים.";
  if ((r = /^None of the (\d+) sampled candidates clears the far display threshold \((\d+(?:\.\d+)?) mm\)/.exec(m))) return "אף אחד מ-" + r[1] + " המועמדים שנדגמו לא עובר את סף התצוגה הרחוק (" + r[2] + " מ\"מ): לא מוצגים. אפשר לסמן ידנית על העור.";
  return m;
}
function injectionMode(tool, api) {
  var ctx = null, ui = {}, wasActive = false, posture = "off", partsOn = false, skinCat = null, popOpen = null, hookOn = false;
  function h(tag, a, k) { return ctx.el(tag, a, k); }
  function sideHe(r) { return ctx.side(r); }
  function recLabel(r) { return r ? r.name + (sideHe(r) ? " · " + sideHe(r) : "") : ""; }
  /* Q344: a structure's Latin name sits in its own bidi island (<bdi>) next to the Hebrew side word, so a mixed Hebrew / English row cannot scramble */
  function setRecLabel(node, r, none) {
    node.textContent = "";
    if (!r) { node.textContent = none; return; }
    node.appendChild(h("bdi", {dir: "ltr", text: r.name}));
    if (sideHe(r)) node.appendChild(document.createTextNode(" \u00B7 " + sideHe(r)));
  }
  function targetRec() { return tool.plan.i != null ? tool.recs[tool.plan.i] : (tool.target && tool.target.i != null && tool.target.i >= 0 ? tool.recs[tool.target.i] : null); }
  function fmt(d) { return (Math.round(d * 10) / 10).toFixed(1); }
  function closePop() { if (popOpen) { popOpen.remove(); popOpen = null; } }
  function pickTarget(i) {
    closePop(); disarm();
    var keepE = tool.entry;                // Q367: an entry set first stays (the order is the user's)
    tool.planPick(i);
    tool.setTargetAt(i);                 // a default target point at the structure's vertex centroid; a tap inside the structure replaces it
    if (tool.target) tool.target.kind = "centre";
    tool.pl.kind = "centre"; ui.rk = null; ui.planeMsg = "";
    if (keepE) tool.entry = keepE;
    /* Q367: a nerve is never a tip's inside: perineural by default; a bursa / sheath: inside the sac; a capsule: the joint space */
    if (tool.isNerveT(i)) { tool.plPeri(i, null, false); ui.rk = "peri"; }
    else if (tool.isSacT(i)) tool.plCavity(i);
    else if (tool.isCapsuleT(i) && offers(i).intra) tool.plIntra(i);
    else if (keepE) tool.update();
    liftOnPhone();
    var parts = api.parts ? api.parts() : null;
    if (parts && parts.setMode && parts.state && !partsOn && parts.state().mode !== "off") { parts.setMode("off"); if (parts.dirty) parts.dirty(); }
    refresh();
  }
  /* Q367: the picker is the plan's structure chooser -- the needle tip (any structure but the skin: muscle, nerve, joint, bursa,
     tendon sheath, fascia...; muscles and tendons listed first, an exact id first) or the plane's second side. Without an entry it
     also offers to start from the skin entry instead (the order is the user's). */
  function openPicker(role) {
    closePop();
    role = role === "planeB" ? "planeB" : "tip";
    var planeA = role === "planeB" ? tool.plan.i : null;
    var inp, res, card = h("div", {class: "mc mc-pick mi", "data-role": role}, [
      h("button", {type: "button", class: "mc-close", "aria-label": "סגור", onclick: closePop}, [xIcon()]),
      h("div", {class: "mc-title", text: role === "planeB" ? "מישור: המבנה השני" : "קצה המחט: בחירת מבנה (שריר, גיד, עצב, מפרק, בורסה…)"}),
      (inp = h("input", {type: "search", class: "mc-search", placeholder: "חיפוש מבנה…", autocomplete: "off"})),
      (res = h("div", {class: "mc-res"})),
      (role === "tip" && !tool.entry ? h("button", {type: "button", class: "mc-sec q367-start-entry", text: "או: התחילו ממעבר בעור", onclick: armEntry}) : null)
    ]);
    function render() {
      var q = inp.value.trim().toLowerCase(), pool = tool.recs.filter(function (r) { return r.cat !== "skin" && r.i !== planeA && (role === "planeB" || PLAN_CATS[r.cat] || q) && (!q || (r.name + " " + r.id).toLowerCase().indexOf(q) >= 0); });
      function rank(r) { return (r.id.toLowerCase() === q || r.id.toLowerCase() === q + "_r" ? 0 : 2) + (PLAN_CATS[r.cat] ? 0 : 1); }
      var hits = pool.map(function (r, n) { return {r: r, n: n, k: rank(r)}; }).sort(function (a, b) { return a.k - b.k || a.n - b.n; }).slice(0, 40).map(function (x) { return x.r; });
      res.innerHTML = "";
      if (!hits.length) { res.appendChild(h("p", {class: "mc-hint", text: q ? "אין מבנה תואם." : "הקלידו שם מבנה."})); return; }
      hits.forEach(function (r) { res.appendChild(h("button", {type: "button", dir: "rtl", title: recLabel(r), onclick: function () { if (role === "planeB") doPlane(planeA, r.i); else pickTarget(r.i); }}, [h("bdi", {class: "mc-nm", dir: "ltr", text: r.name}), (sideHe(r) ? h("span", {class: "mc-sd", text: sideHe(r)}) : null)])); });
    }
    inp.addEventListener("input", render); render();
    ctx.main.appendChild(card); popOpen = card; try { inp.focus(); } catch (e) {}
  }
  function xIcon() { var s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("width", "16"); s.setAttribute("height", "16"); s.setAttribute("aria-hidden", "true"); s.innerHTML = '<path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>'; return s; }
  function suggest() {
    if (!tool.target) { refresh(); return; }
    tool.suggest(); refresh();
    if (tool.sugg.shown.length && ui.cands) ui.cands.scrollIntoView({block: "nearest"});
  }
  function manualEntry() {
    tool.setMode("tfirst", true);
    if (tool.target) { tool.entry = null; tool.clearSuggestions(); tool.update(); }
    ui.manualHint = true; refresh();
  }
  function resetAll() { closePop(); tool.clearSuggestions(); tool.clear(); tool.planRelease(); if (posture !== "off") setPosture("off"); refresh(); }
  function cancelPath() { closePop(); tool.clearSuggestions(); tool.clear(); refresh(); }
  /* Q276: 2+ saved points in the same muscle -- "Add point" records the current entry/target (unchanged single working placement)
     instead of it being silently replaced by the next one; each keeps its own marker + distance readout (tool.addSavedPoint() reuses
     corridorFor() verbatim). Not a recommendation of count or spacing -- a recorder, same as the bare tool's own panel. */
  function showInScan() { var U = global.NMSKUltrasound; if (U && U.needleClip) U.needleClip.show({}); }
  function addPoint() { if (!tool.target) return; tool.addSavedPoint(); refresh(); }
  function removeSaved(id) { tool.removeSavedPoint(id); refresh(); }
  function clearSaved() { tool.clearSavedPoints(); refresh(); }
  function setPosture(key) {
    var r = targetRec(), side = r && r.side === "l" ? "l" : "r";
    var out = tool.applyPosture(key === "off" ? "rest" : key, side);
    if (out == null && key !== "off") { posture = "off"; ui.postureMsg = "אין ריג תנוחה בעמוד זה"; }
    else { posture = key; ui.postureMsg = key === "off" ? "" : (key === "ul" ? "דפוס כיפוף גפה עליונה (להמחשה)" : "דפוס יישור גפה תחתונה (להמחשה)"); }
    refresh();
  }
  function cyclePosture() { setPosture(posture === "off" ? "ul" : posture === "ul" ? "ll" : "off"); }
  function toggleHalo() { var b = tool.$("ncl-corr-halo"); if (b) b.click(); refresh(); }
  function toggleParts() {
    var parts = api.parts ? api.parts() : null; if (!parts || !parts.setMode) return;
    partsOn = !partsOn; var r = targetRec(); if (r && parts.select) parts.select(r.id);
    parts.setMode(partsOn ? "sel" : "off"); if (parts.dirty) parts.dirty(); refresh();
  }
  function toggleSkin() { if (!skinCat) return; api.setCategoryOn(skinCat, !api.categoryOn(skinCat)); refresh(); }
  function layersPop() {
    if (popOpen && popOpen.classList.contains("mp-pop")) { closePop(); return; }
    closePop();
    var seen = {}, cats = [];
    tool.recs.forEach(function (r) { if (r.cat && !seen[r.cat]) { seen[r.cat] = 1; cats.push(r.cat); } });
    var pop = h("div", {class: "mp-pop mi"}, cats.map(function (c) {
      return h("button", {type: "button", "aria-pressed": String(!!api.categoryOn(c)), text: c, onclick: function () { api.setCategoryOn(c, !api.categoryOn(c)); this.setAttribute("aria-pressed", String(!!api.categoryOn(c))); }});
    }));
    ctx.main.appendChild(pop); popOpen = pop;
  }
  function moreToggle() { document.body.classList.toggle("mode-more"); }
  /* ---------- Q367: the plan panel (the tip and the skin entry, in any order), the marker legend and the Safety card ---------- */
  var KIND_HE = {centre: "מרכז המבנה", free: "נקודה בהקשה", origin: "מקור (origin)", insertion: "אחיזה (insertion)", nmj: "צומת עצב-שריר",
                 mp: "צומת עצב-שריר · נקודה מוטורית", iz: "צומת עצב-שריר · רצועת IZ", plane: "מישור (plane block)", peri: "פרינוירלי (ליד העצב)",
                 cavity: "בתוך הבורסה / הנדן", intra: "תוך-מפרקי (מרווח המפרק)"};
  var MISSING_HE = {origin: "מקור", insertion: "אחיזה", nmj: "צומת עצב-שריר", intra: "מרווח מפרק"};
  var offersOf = {};
  function mkChip(kind) { return h("span", {class: "q367-mk q367-mk-" + kind, "aria-hidden": "true"}); }
  function qb(text, fn, a) { var b = h("button", {type: "button", class: "q367-btn", text: text, onclick: fn}); if (a) Object.keys(a).forEach(function (k) { if (a[k] != null) b.setAttribute(k, a[k]); }); return b; }
  function arm(kind, fn, hint, skip) { tool.armFn = fn; tool.armSkip = skip == null ? null : skip; ui.armKind = kind; ui.armText = hint; refresh(); }
  function disarm() { tool.armFn = null; tool.armSkip = null; ui.armKind = null; ui.armText = ""; }
  function armEntry() { closePop(); arm("entry", function (hit) { disarm(); tool.plEntrySet(hit); ui.manualHint = false; refresh(); }, "הקישו על העור במודל: שם תיכנס המחט."); }
  function armFree() { arm("free", function (hit) { disarm(); tool.plTipSet({p: hit.p, i: hit.i}, "free"); ui.rk = "free"; refresh(); }, "הקישו על נקודה במודל (או על פני החתך): שם יהיה קצה המחט."); }
  function armPeri(i) { arm("peri", function (hit) { disarm(); tool.plPeri(i, hit.p, true); refresh(); }, "הקישו על העצב במקום הרצוי: הקצה יונח לידו."); }
  function armPlaneB(a) { arm("planeB", function (hit) { if (hit.i == null || hit.i === a) return; disarm(); doPlane(a, hit.i); }, "הקישו על המבנה השני של המישור."); }
  function armSnap() { arm("snap", function (hit) { disarm(); tool.plPlaneSnap(hit.p); refresh(); }, "הקישו ליד המקום הרצוי: הקצה יעבור לנקודת המישור הקרובה."); }
  /* Q367: on a phone the step sheet covers the lower half of the model, so a newly chosen target is brought to the upper visible part
     (about 28 % down the model area) instead of the centre, where it sat at the sheet's edge */
  function liftOnPhone() {
    if (!ctx || !ctx.isPhone() || !tool.target) return;
    setTimeout(function () {
      try {
        var p = tool.target.p, v = api.view(), s0 = api.toScreen(p), s1 = api.toScreen([p[0], p[1] - 10, p[2]]); if (!s0 || !s1 || !v) return;
        var mm = ctx.main.getBoundingClientRect(), dy = s0[1] - (mm.top + mm.height * 0.28), ppm = (s1[1] - s0[1]) / 10;
        if (Math.abs(ppm) < 1e-3 || Math.abs(dy) < 8) return;
        api.focus([v.target[0], v.target[1] - dy / ppm, v.target[2]]); api.redraw();
      } catch (e) {}
    }, 120);
  }
  function doPlane(a, b) {
    closePop();
    var res = tool.plPlane(a, b);
    ui.rk = "plane";
    ui.planeMsg = !res ? "לא ניתן לחשב מישור בין המבנים האלה." : !res.n ? "המבנים אינם מתקרבים זה לזה עד " + tool.pl.gap + ' מ"מ: אין מישור. הגדילו את הפער המרבי או בחרו מבנה סמוך.' : "";
    refresh();
  }
  function tipRec() {
    var t = tool.target;
    if (t && t.kind === "peri" && t.nerve != null) return tool.recs[t.nerve];
    if (t && (t.kind === "plane" || t.kind === "intra") && tool.pl.plane) return tool.recs[t.kind === "intra" ? tool.pl.plane.intra : tool.pl.plane.a];
    return targetRec();
  }
  function offers(i) { var ps = api.parts ? api.parts() : null, k = i + "|" + (ps && ps.state && ps.state().loaded ? 1 : 0) + "|" + (tool.guide.data ? 1 : 0) + "|" + tool.mp.points.length; if (!offersOf[k]) offersOf[k] = tool.plOffers(i); return offersOf[k]; }
  function setKind(k, i, o) {
    ui.rk = k;
    if (k === "centre") tool.plCentre(i);
    else if (k === "free") armFree();
    else if ((k === "origin" || k === "insertion") && o[k].length === 1) tool.plUseAttach(i, k, o[k][0]);
    else if (k === "peri") tool.plPeri(i, null, false);
    else if (k === "cavity") tool.plCavity(i);
    else if (k === "intra") { if (!tool.plIntra(i)) ui.planeMsg = "לא נמצא מרווח מפרק בין שתי עצמות בתוך הקופסית."; }
    refresh();
  }
  function buildPlan() {
    ui.pTipVal = h("span", {class: "q367-val"}); ui.pEntVal = h("span", {class: "q367-val"});
    ui.pTipPick = qb("בחירה", function () { openPicker("tip"); });
    ui.pTipClr = qb("ניקוי", function () { disarm(); tool.plTipClear(); ui.rk = null; refresh(); }, {"aria-label": "ניקוי קצה המחט"});
    ui.pEntTap = qb("הקשה על העור", armEntry);
    ui.pEntSug = qb("הצעות", function () { disarm(); suggest(); });
    ui.pEntClr = qb("ניקוי", function () { disarm(); tool.plEntryClear(); refresh(); }, {"aria-label": "ניקוי מעבר בעור"});
    ui.refine = h("div", {class: "q367-ref"});
    ui.arm = h("div", {class: "q367-arm", hidden: true});
    ui.pSafeBtn = qb("בטיחות…", function () { toggleSafe(); });
    ui.pSafeTxt = h("span", {class: "q367-val"});
    ui.plan = h("div", {class: "q367-plan", "data-q367": "plan"}, [
      h("div", {class: "q367-h", text: "תכנון · בכל סדר"}),
      h("div", {class: "q367-leg"}, [mkChip("tip"), h("span", {text: "קצה המחט (תכלת, מעוין)"}), mkChip("entry"), h("span", {text: "מעבר בעור (כתום, טבעת)"})]),
      h("div", {class: "q367-row", "data-q367": "tip"}, [mkChip("tip"), h("span", {class: "q367-lab", text: "קצה המחט:"}), ui.pTipVal, ui.pTipPick, ui.pTipClr]),
      ui.refine,
      h("div", {class: "q367-row", "data-q367": "entry"}, [mkChip("entry"), h("span", {class: "q367-lab", text: "מעבר בעור:"}), ui.pEntVal, ui.pEntTap, ui.pEntSug, ui.pEntClr]),
      ui.arm,
      h("div", {class: "q367-row", "data-q367": "safety"}, [ui.pSafeBtn, ui.pSafeTxt])
    ]);
  }
  function renderPlan() {
    var t = tool.target, e = tool.entry, r = tipRec(), P = tool.pl.plane;
    ui.pTipVal.textContent = "";
    if (!t) ui.pTipVal.textContent = r ? "" : "לא נקבע";
    if (r && !(t && t.kind === "plane" && P)) ui.pTipVal.appendChild(h("bdi", {dir: "ltr", text: r.name}));
    if (t && t.kind === "plane" && P) { ui.pTipVal.appendChild(h("bdi", {dir: "ltr", text: tool.name(P.a)})); ui.pTipVal.appendChild(document.createTextNode(" | ")); ui.pTipVal.appendChild(h("bdi", {dir: "ltr", text: tool.name(P.b)})); }
    if (t && t.kind) ui.pTipVal.appendChild(document.createTextNode(" · " + KIND_HE[t.kind] + (t.kind === "peri" ? " " + fmt(t.off) + ' מ"מ' : "")));
    else if (r && !t) ui.pTipVal.appendChild(document.createTextNode(" · נקודה טרם נקבעה"));
    ui.pTipPick.textContent = r ? "שינוי" : "בחירה";
    ui.pTipClr.hidden = !t;
    ui.pEntVal.textContent = !e ? "לא נקבע" : (t ? "נקבע · אורך " + fmt(dist(e.p, t.p)) + ' מ"מ' : "נקבע · ממתין לקצה המחט");
    ui.pEntTap.textContent = e ? "הקשה חדשה" : "הקשה על העור";
    ui.pEntSug.disabled = !t; ui.pEntSug.title = t ? "נקודות כניסה מחושבות לקצה הזה" : "דרוש קצה מחט";
    ui.pEntClr.hidden = !e;
    ui.arm.hidden = !ui.armKind; ui.arm.innerHTML = "";
    if (ui.armKind) { ui.arm.appendChild(h("span", {text: ui.armText})); ui.arm.appendChild(qb("ביטול", function () { disarm(); refresh(); })); }
    ui.pTipPick.setAttribute("aria-pressed", "false"); ui.pEntTap.setAttribute("aria-pressed", String(ui.armKind === "entry"));
    renderRefine(r && r.i != null ? r.i : null);
    var S = tool.safe;
    ui.pSafeTxt.textContent = !S.nOn ? "אין כללים פעילים" : S.nOn + (S.nOn === 1 ? " כלל" : " כללים") + " · " + (!(t || e) ? "ממתין לתכנון" : S.viol.length ? S.viol.length + (S.viol.length === 1 ? " הפרה" : " הפרות") : "אין הפרה");
    ui.pSafeTxt.classList.toggle("q367-bad", !!S.viol.length);
    ui.pSafeBtn.setAttribute("aria-pressed", String(!!ui.safeOpen));
  }
  function renderRefine(i) {
    var R = ui.refine; R.innerHTML = "";
    if (i == null) { R.appendChild(h("p", {class: "mc-hint", text: "בחרו מבנה לקצה המחט (חיפוש או הקשה על המודל) או התחילו ממעבר בעור: הסדר שלכם."})); return; }
    var o = offers(i), cur = ui.rk || (tool.target && tool.target.kind) || null, ks = h("div", {class: "q367-ks", role: "group", "aria-label": "מיקום הקצה במבנה"});
    if (cur === "mp" || cur === "iz") cur = "nmj";
    function k(key, on) { if (on) ks.appendChild(qb(KIND_HE[key], function () { setKind(key, i, o); }, {"data-k": key, "aria-pressed": String(cur === key)})); }
    k("centre", true); k("free", true); k("origin", o.origin.length > 0); k("insertion", o.insertion.length > 0); k("nmj", o.mp.length + o.iz.length > 0);
    k("plane", true); k("peri", o.peri); k("cavity", o.cavity); k("intra", o.intra);
    R.appendChild(ks);
    var sub = h("div", {class: "q367-sub"}), any = false, t = tool.target;
    if ((cur === "origin" || cur === "insertion") && o[cur].length) {
      any = true;
      o[cur].forEach(function (a) { sub.appendChild(qb(a.name, function () { tool.plUseAttach(i, cur, a); refresh(); }, {"data-q367-att": a.id, "aria-pressed": String(!!(t && t.ref === a.id))})); });
    } else if (cur === "nmj") {
      any = true;
      o.mp.forEach(function (p, n) { var lbl = mpBundleLabel(p); sub.appendChild(qb(lbl ? "נקודה מוטורית · " + lbl : "נקודה מוטורית " + (n + 1) + "/" + o.mp.length, function () { tool.plUseMp(p); refresh(); }, {"data-q367-mp": String(n)})); });
      o.iz.forEach(function (z) { sub.appendChild(qb("רצועת IZ · אתר " + z.site.n, function () { tool.plUseIz(z); refresh(); }, {"data-q367-iz": String(z.site.n)})); });
    } else if (cur === "plane") {
      any = true;
      var P = tool.pl.plane && tool.pl.plane.intra == null && tool.pl.plane.a === i ? tool.pl.plane : null;
      var bName = h("span", {class: "q367-val"}); if (P) bName.appendChild(h("bdi", {dir: "ltr", text: tool.name(P.b)})); else bName.textContent = "טרם נבחר";
      sub.appendChild(h("div", {class: "q367-row"}, [h("span", {class: "q367-lab", text: "המבנה השני:"}), bName]));
      sub.appendChild(h("div", {class: "q367-ks"}, [qb("חיפוש", function () { openPicker("planeB"); }), qb("הקשה במודל", function () { armPlaneB(i); }, {"aria-pressed": String(ui.armKind === "planeB")})]));
      var adj = tool.plAdjacent(i);
      if (adj.length) { var al = h("div", {class: "q367-ks"}); adj.forEach(function (j) { al.appendChild(qb(tool.name(j), function () { doPlane(i, j); }, {"data-q367-adj": tool.recs[j].id, dir: "ltr"})); }); sub.appendChild(h("p", {class: "mc-hint", text: "סמוכים:"})); sub.appendChild(al); }
      var gin = h("input", {type: "number", class: "q367-in", min: "1", max: String(PLAN_GAP_MAX), step: "0.5", value: String(tool.pl.gap), "aria-label": "פער מרבי בין המבנים (מ\"מ)"});
      gin.addEventListener("change", function () { tool.pl.gap = clamp(+gin.value || PLAN_GAP0, 1, PLAN_GAP_MAX); if (P) doPlane(i, P.b); else refresh(); });
      sub.appendChild(h("div", {class: "q367-row"}, [h("span", {text: "פער מרבי:"}), gin, h("span", {text: 'מ"מ'})]));
      sub.appendChild(h("p", {class: "mc-hint", text: "המישור: נקודות האמצע בין שני פני השטח, בכל מקום שבו הם קרובים זה לזה עד הפער המרבי (סגול במודל). הקצה: נקודת המישור הקרובה למעבר בעור, או מרכז המישור."}));
      if (P) {
        sub.appendChild(h("p", {class: "mc-hint", "data-q367-plane": String(P.pts.length), text: P.pts.length ? P.pts.length + " נקודות במישור · הפער הקטן " + fmt(P.minGap) + ' מ"מ' + (t && t.gapHere != null ? " · כאן " + fmt(t.gapHere) + ' מ"מ, הקצה באמצע' : "") : (ui.planeMsg || "אין מישור.")}));
        if (P.pts.length) sub.appendChild(qb("הזזת הקצה בהקשה", armSnap, {"aria-pressed": String(ui.armKind === "snap")}));
      } else if (ui.planeMsg) sub.appendChild(h("p", {class: "mc-hint", text: ui.planeMsg}));
    } else if (cur === "peri" && o.peri) {
      any = true;
      var pin = h("input", {type: "number", class: "q367-in", min: "0.5", max: "20", step: "0.5", value: String(tool.pl.peri), "aria-label": "מרחק הקצה מפני העצב (מ\"מ)"});
      pin.addEventListener("change", function () { tool.pl.peri = clamp(+pin.value || PLAN_PERI0, 0.5, 20); tool.plPeri(i, null, false); refresh(); });
      sub.appendChild(h("div", {class: "q367-row"}, [h("span", {text: "מרחק מפני העצב:"}), pin, h("span", {text: 'מ"מ'})]));
      sub.appendChild(h("p", {class: "mc-hint", text: "הקצה ליד העצב, לעולם לא בתוכו: בצד שממנו באה המחט (או במקום שתקישו)."}));
      sub.appendChild(qb("הקשה על העצב", function () { armPeri(i); }, {"aria-pressed": String(ui.armKind === "peri")}));
    } else if (cur === "intra" && ui.planeMsg) { any = true; sub.appendChild(h("p", {class: "mc-hint", text: ui.planeMsg})); }
    else if (cur === "intra" && tool.pl.plane && tool.pl.plane.intra === i) {
      any = true; sub.appendChild(h("p", {class: "mc-hint", text: "מרווח המפרק: נקודות האמצע בין שתי העצמות שבתוך הקופסית (" + tool.name(tool.pl.plane.a) + " / " + tool.name(tool.pl.plane.b) + "); הקצה בנקודה הקרובה למרכז הקופסית."}));
    } else if (cur === "cavity" && t && t.kind === "cavity") { any = true; sub.appendChild(h("p", {class: "mc-hint", text: t.inside ? "הקצה בתוך השק: מרכזו, או באמצע בין שתי דפנותיו." : "הקצה ליד השק (הרשת אינה סגורה כאן)."})); }
    if (any) R.appendChild(sub);
    if (o.missing.length) R.appendChild(h("p", {class: "mc-hint", "data-q367-missing": o.missing.join(" "), text: "אין על גוף זה נתונים ל: " + o.missing.map(function (m) { return MISSING_HE[m]; }).join(", ") + "."}));
  }
  function buildSafe() {
    ui.safeIn = {}; ui.thrIn = {}; ui.thrTxt = {};
    var grid = h("div", {class: "q367-grid"});
    SAFE_ROWS.forEach(function (row) {
      var inp = h("input", {type: "number", class: "q367-in", min: "0", max: "100", step: "0.5", placeholder: "כבוי", "data-rule": row.k, "aria-label": SAFE_HE[row.kind] + " " + SAFE_HE[row.c] + ': מרחק מינימלי (מ"מ)'});
      inp.addEventListener("change", function () { var o = {}; o[row.k] = inp.value; tool.safeSet({rules: o}); refresh(); });
      ui.safeIn[row.k] = inp; ui.thrTxt[row.k] = h("span", {class: "q367-thr"});
      grid.appendChild(h("span", {class: "q367-cls"}, [h("span", {class: "q367-dot", style: "background:" + SAFE_COL[row.kind]}), SAFE_HE[row.kind] + " " + SAFE_HE[row.c] + " ", ui.thrTxt[row.k]]));
      grid.appendChild(inp); grid.appendChild(h("span", {text: 'מ"מ'}));
    });
    var tg = h("div", {class: "q367-grid q367-grid4"});
    [["n", "עצבים"], ["a", "עורקים"], ["v", "ורידים"]].forEach(function (x) {
      var a = h("input", {type: "number", class: "q367-in", min: "0.1", max: "50", step: "0.5", "data-thr": x[0] + "L", "aria-label": x[1] + ': גדול מ- (מ"מ)'}), b = h("input", {type: "number", class: "q367-in", min: "0.1", max: "50", step: "0.5", "data-thr": x[0] + "M", "aria-label": x[1] + ': בינוני מ- (מ"מ)'});
      function ch() { var o = {}; o[x[0]] = [+a.value, +b.value]; tool.safeSet({thr: o}); refresh(); }
      a.addEventListener("change", ch); b.addEventListener("change", ch);
      ui.thrIn[x[0]] = [a, b];
      tg.appendChild(h("span", {class: "q367-lab", text: x[1]})); tg.appendChild(h("span", {text: "גדול ≥"})); tg.appendChild(a); tg.appendChild(h("span", {text: "בינוני ≥"})); tg.appendChild(b);
    });
    ui.safeRes = h("div", {class: "q367-res", "aria-live": "polite"});
    ui.safeHalo = h("p", {class: "mc-hint"});
    ui.safe = h("div", {class: "mc mc-safe mi", dir: "rtl", hidden: true, "data-q367": "safety-card"}, [
      h("button", {type: "button", class: "mc-close", "aria-label": "סגור", onclick: function () { toggleSafe(false); }}, [xIcon()]),
      h("div", {class: "mc-title", text: "בטיחות · כללי מרחק"}),
      h("p", {class: "q367-own", text: "אלה הכללים שלכם, לא המלצה. שדה ריק = כלל כבוי."}),
      grid,
      h("details", {class: "q367-thrbox"}, [h("summary", {text: "ספי גודל לפי קוטר: מוסכמה, ניתנת לעריכה"}), tg,
        h("p", {class: "mc-hint", text: "לא ממקור: בספרים שבידינו אין ספי גודל במ\"מ. אלה רמות הקוטר של הפרויקט (Q240): כלי-דם ראשי ≥ 6, משני 3–6 מ\"מ; עצב גזע ≥ 4, ענפים 2–4 מ\"מ. גזע בעל שם נחשב גדול."}),
        h("p", {class: "mc-hint", text: "קוטר העצבים: טבלת הקליבר של העמוד. קוטר כלי-הדם: נמדד מהרשת של כל כלי (קוטר צינור חציוני)."})]),
      ui.safeRes, ui.safeHalo
    ]);
    ctx.main.appendChild(ui.safe);
  }
  function toggleSafe(on) {
    ui.safeOpen = on == null ? !ui.safeOpen : !!on;
    ui.safe.hidden = !ui.safeOpen; document.body.classList.toggle("inj-safe", ui.safeOpen);
    if (ui.safeOpen) closePop();
    refresh();
  }
  function renderSafe() {
    var S = tool.safe, t = tool.target, e = tool.entry;
    ui.pSafe.setAttribute("aria-pressed", String(!!ui.safeOpen));
    if (!ui.safeOpen) return;
    SAFE_ROWS.forEach(function (row) {
      var inp = ui.safeIn[row.k], thr = S.thr[row.kind];
      if (document.activeElement !== inp) inp.value = S.rules[row.k] > 0 ? String(S.rules[row.k]) : "";
      ui.thrTxt[row.k].textContent = row.c === "L" ? "(≥ " + thr[0] + ")" : row.c === "M" ? "(" + thr[1] + "–" + thr[0] + ")" : "(< " + thr[1] + ")";
    });
    ["n", "a", "v"].forEach(function (k) { var p = ui.thrIn[k]; if (document.activeElement !== p[0]) p[0].value = S.thr[k][0]; if (document.activeElement !== p[1]) p[1].value = S.thr[k][1]; });
    var R = ui.safeRes; R.innerHTML = "";
    if (!S.nOn) R.appendChild(h("p", {class: "mc-hint", text: "אין כללים פעילים: כל השדות ריקים."}));
    else if (!(t || e)) R.appendChild(h("p", {class: "mc-hint", text: "קבעו קצה מחט או מעבר בעור: המסלול ייבדק מול הכללים."}));
    else if (S.viol.length) {
      R.appendChild(h("p", {class: "q367-bad", text: (S.viol.length === 1 ? "הפרה אחת" : S.viol.length + " הפרות") + " (" + (t && e ? "המסלול" : t ? "קצה המחט" : "מעבר בעור") + "):"}));
      S.viol.forEach(function (v) {
        R.appendChild(h("div", {class: "q367-v", "data-q367-viol": v.id}, [h("span", {class: "q367-dot", style: "background:" + SAFE_COL[v.k]}), h("bdi", {dir: "ltr", text: v.name}),
          document.createTextNode(" · " + SAFE_HE[v.k] + " " + SAFE_HE[v.c] + " · " + fmt(v.d) + ' מ"מ < כלל ' + v.rule + ' מ"מ')]));
      });
    } else R.appendChild(h("p", {class: "q367-ok", text: "אין הפרה של הכללים שהוגדרו" + (S.rows.length ? " (" + S.rows.length + " מבנים בטווח נבדקו)." : ".")}));
    if (S.unk) R.appendChild(h("p", {class: "mc-hint", text: S.unk + " מבנים בטווח ללא קוטר ידוע: לא סווגו ולא נבדקו."}));
    var tg = t && (t.kind === "peri") ? " מבנה המטרה עצמו אינו נבדק." : "";
    ui.safeHalo.textContent = S.nOn ? "הילה ברדיוס הכלל סביב כל מבנה בטווח (כלל + " + SAFE_PAD + ' מ"מ מהמסלול או מהקצה): ' + S.halos.length + " מוצגות" + (S.rows.length > S.halos.length ? " מתוך " + S.rows.length + " (ההפרות והקרובים לכלל שלהם)" : "") + ", עד " + (S.cap || SAFE_CAP.desk) + "." + tg : "";
  }
  function build(c) {
    ctx = c;
    if (!document.getElementById("inj-mode-css")) {   // the tool's own panel stays alive (its state, its 3-D overlays) but is not shown in the mode: the cards re-skin it
      var st = document.createElement("style"); st.id = "inj-mode-css"; st.textContent = "body.mode-inj #needle-panel,body.mode-inj .ncl-tip{display:none!important}" +
        "body.mode-inj.nmsk-us.us-clip-on .mc-right,body.mode-inj.nmsk-us.us-clip-on .mc-pick{display:none!important}" +
        /* Q344: the target picker is opaque (the step cards behind it showed through); a row = the name, then the side as its own chip, no id */
        "body.mode-inj .mc-pick{background:#fff!important;z-index:6;box-shadow:0 14px 40px rgba(32,36,43,.28)}" +
        "body.mode-inj .mc-res button{display:flex;align-items:center;justify-content:space-between;gap:10px;color:#20242B}" +
        "body.mode-inj .mc-res .mc-nm{min-width:0;overflow-wrap:anywhere;text-align:left}" +
        "body.mode-inj .mc-res .mc-sd{flex:0 0 auto;font-size:12px;font-weight:600;color:#3F4752;background:#EEF0F2;border-radius:999px;padding:2px 10px}" +
        "body.mode-inj .mc-sec[aria-pressed=true]{color:#0A5F68}" +
        "body.mode-inj .mc-search{color:#20242B;background:#fff}body.mode-inj .mc-search::placeholder{color:#5B6472;opacity:1}" +
        "body.mode-inj .mc-step.off{opacity:1}body.mode-inj .mc-step.off .mc-num{background:#5B6472}body.mode-inj .mc-step.off .mc-lbl{color:#4A5361}" +
        "@media (max-width:900px){body.mode-inj.nmsk-us.us-clip-on .mc-left{display:none!important}}" +   // Q325: the scan's needle clip takes that side; its ✕ brings the card back
        /* Q347: on a phone the step sheet (target, zone, guide, steps) stops at half the screen and scrolls inside, so >= 50 % of the model stays visible */
        "@media (max-width:760px){body.mode-inj .mc-right{max-height:calc(50% - 32px);box-sizing:border-box}}" +
        /* Q347: the guide section -- sized to its content, one line (its summary) when closed; dark ink on the card's white */
        "body.mode-inj .mc-guide{border:1px solid #E4E1D8;border-radius:12px;padding:8px 10px;color:#20242B;font-size:13px;line-height:1.45;background:#fff}" +
        "body.mode-inj .mc-guide>summary{cursor:pointer;font-weight:700;font-size:14px;color:#20242B;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
        "body.mode-inj .mc-guide .g-row{margin:6px 0 0;overflow-wrap:anywhere}body.mode-inj .mc-guide .g-k{color:#3F4752;font-weight:700}" +
        "body.mode-inj .mc-guide .g-sub{color:#4A5361;font-size:12.5px;margin-top:2px;overflow-wrap:anywhere}" +
        "body.mode-inj .mc-guide .g-site{margin-top:6px;padding-top:6px;border-top:1px solid #EEF0F2;overflow-wrap:anywhere}" +
        "body.mode-inj .mc-guide .g-badge{display:inline-block;font-size:12px;font-weight:600;color:#5A3E00;background:#FFF1CC;border-radius:999px;padding:0 8px}" +
        "body.mode-inj .mc-guide .mc-sec{height:auto;min-height:36px;font-size:14px;margin-top:6px;padding:4px 10px}" +
        "body.mode-inj .mc-guide .g-rrow{font-size:13px;margin-top:3px;padding-inline-start:6px;border-inline-start:4px solid transparent}" +
        "body.mode-inj .mc-guide .g-rrow.band-n{border-inline-start-color:#C53030}body.mode-inj .mc-guide .g-rrow.band-m{border-inline-start-color:#C97A1A}body.mode-inj .mc-guide .g-rrow.band-f{border-inline-start-color:#2F855A}" +
        "body.mode-inj .mc-guide .g-i{display:inline-flex;width:28px;height:28px;min-height:0;margin:0;padding:0;border-radius:999px;font-size:15px;vertical-align:middle}" +
        "body.mode-inj .mc-guide a{color:#0A5F68}";
      document.head.appendChild(st);
    }
    if (!document.getElementById("inj-q367-css")) {   // Q367: the plan panel, the marker chips, the Safety card
      var s3 = document.createElement("style"); s3.id = "inj-q367-css"; s3.textContent =
        "body.mode-inj .q367-plan{border:1px solid #E4E1D8;border-radius:12px;padding:8px 10px;display:flex;flex-direction:column;gap:7px;color:#20242B;background:#fff;font-size:13px;line-height:1.4}" +
        "body.mode-inj .q367-h{font-weight:700;font-size:14px}" +
        "body.mode-inj .q367-leg{font-size:12.5px;color:#3F4752;display:flex;flex-wrap:wrap;gap:4px 8px;align-items:center}" +
        "body.mode-inj .q367-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-width:0}" +
        "body.mode-inj .q367-lab{font-weight:700;font-size:13.5px;color:#20242B}" +
        "body.mode-inj .q367-val{font-size:13px;color:#3F4752;min-width:0;overflow-wrap:anywhere;flex:1 1 110px}" +
        "body.mode-inj .q367-btn{height:auto;min-height:34px;padding:4px 10px;border-radius:10px;border:1px solid #C9CDD3;background:#fff;color:#20242B;font-size:13px;font-weight:600;line-height:1.25;overflow-wrap:anywhere;max-width:100%}" +
        "body.mode-inj .q367-btn[aria-pressed=true]{background:#E3F2F1;border-color:#0E7C86;color:#0A5F68}" +
        "body.mode-inj .q367-btn[disabled]{color:#5B6472;background:#F3F4F6}" +
        "body.mode-inj .q367-ks{display:flex;flex-wrap:wrap;gap:6px;min-width:0}" +
        "body.mode-inj .q367-sub{display:flex;flex-direction:column;gap:6px;padding:7px;border-radius:10px;background:#F6F7F8;min-width:0}" +
        "body.mode-inj .q367-sub .mc-hint{color:#4A5361}" +
        "body.mode-inj .q367-mk{display:inline-block;flex:0 0 auto;vertical-align:middle;box-sizing:border-box}" +
        "body.mode-inj .q367-mk-tip{width:13px;height:13px;margin:0 2px;background:" + MK.tip.color + ";border:2px solid " + MK.tip.edge + ";transform:rotate(45deg);border-radius:2px}" +
        "body.mode-inj .q367-mk-entry{width:17px;height:17px;border-radius:50%;border:4px solid " + MK.entry.color + ";box-shadow:0 0 0 1.5px " + MK.entry.edge + ",inset 0 0 0 1.5px " + MK.entry.edge + "}" +
        "body.mode-inj .q367-arm{font-size:12.5px;color:#5A3E00;background:#FFF1CC;border-radius:8px;padding:5px 8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}" +
        "body.mode-inj .q367-in{width:64px;height:34px;border:1px solid #8A929D;border-radius:8px;padding:0 6px;color:#20242B;background:#fff;font-size:14px;direction:ltr}" +
        "body.mode-inj .q367-in::placeholder{color:#5B6472;opacity:1}" +
        "body.mode-inj .q367-bad{color:#B42318;font-weight:700}body.mode-inj .q367-ok{color:#1E6B3E;font-weight:700;margin:0;font-size:13px}" +
        /* the card's background is NOT fully opaque: an opaque scrolling card over the WebGL canvas made Chromium draw an unpainted rectangle (white
           or black, the card's size) over the model on a phone -- an opaque-scroller compositing fault; .97 white (as the step sheet) avoids it */
        "body.mode-inj .mc-safe{left:20px;top:20px;width:330px;z-index:3;background:rgba(255,255,255,.97)!important;color:#20242B;gap:10px}" +
        "body.mode-inj.inj-safe .mc-left{visibility:hidden!important}" +
        "body.mode-inj .q367-own{margin:0;font-size:13px;color:#20242B;font-weight:600}" +
        "body.mode-inj .q367-grid{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:6px 8px;align-items:center;font-size:13px}" +
        "body.mode-inj .q367-grid4{grid-template-columns:auto auto auto auto auto;gap:6px 6px;font-size:12.5px}" +
        "body.mode-inj .q367-cls{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-width:0}body.mode-inj .q367-thr{color:#4A5361;font-size:12px;direction:ltr;unicode-bidi:isolate}" +
        "body.mode-inj .q367-dot{display:inline-block;width:10px;height:10px;border-radius:50%;flex:0 0 auto;border:1px solid rgba(0,0,0,.35)}" +
        "body.mode-inj .q367-thrbox>summary{cursor:pointer;font-weight:600;font-size:13px;color:#20242B}" +
        "body.mode-inj .q367-res{display:flex;flex-direction:column;gap:4px;font-size:13px}body.mode-inj .q367-v{display:flex;gap:6px;align-items:center;flex-wrap:wrap;overflow-wrap:anywhere}" +
        "body.mode-inj .mc-drow .q367-cl{display:block;font-size:11.5px;color:#4A5361;font-weight:500}" +
        "body.mode-inj .g-cls{color:#4A5361;font-size:12px}" +
        /* phone: the step sheet and the distance card together leave >= 50 % of the model visible while planning */
        "@media (max-width:760px){body.mode-inj .mc-right{max-height:36%}body.mode-inj .mc-left{max-height:24%;overflow:auto}}" +
        "@media (max-width:760px){body.mode-inj .mc-safe{left:0;right:0;top:auto;bottom:0;width:auto;max-height:calc(50% - 32px);overflow:auto;border-radius:20px 20px 0 0;padding:10px 14px 16px;box-sizing:border-box}" +
        "body.mode-inj.inj-safe .mc-right{visibility:hidden!important}body.mode-inj .q367-grid4{grid-template-columns:auto auto auto auto auto}}";
      document.head.appendChild(s3);
    }
    skinCat = tool.recs.some(function (r) { return r.cat === "skin"; }) ? "skin" : null;
    /* bar: the target chip + reset / cancel */
    ui.chipName = h("b", {text: "—"});
    c.bar.chips.appendChild(h("div", {class: "mb-chip mi"}, [h("span", {class: "mb-dim", text: "מטרה"}), ui.chipName, h("button", {type: "button", class: "mb-mini", text: "שנה", onclick: openPicker})]));
    ui.mobText = h("button", {type: "button", class: "mb-text mi", text: "", title: "שנה מטרה", onclick: openPicker}); c.bar.chips.appendChild(ui.mobText);
    var endRef = c.bar.end.firstChild;
    c.bar.end.insertBefore(h("button", {type: "button", class: "mb-btn mi", text: "איפוס", onclick: resetAll}), endRef);
    c.bar.end.insertBefore(h("button", {type: "button", class: "mb-btn mi", text: "בטל", onclick: cancelPath}), endRef);
    /* the model fills the whole main area */
    ui.slot = h("div", {class: "mslot mslot-fill"}); c.main.appendChild(ui.slot); c.modelDock(ui.slot);
    /* right: the step card (a bottom sheet on the phone) */
    ui.step1 = h("div", {class: "mc-step"}, [h("div", {class: "mc-num", text: "1"}), h("div", {class: "mc-lbl", text: "מטרה"}), (ui.s1ok = h("div", {class: "mc-ok", text: ""}))]);
    ui.step1Btn = h("button", {type: "button", class: "mc-sec mc-desk", text: "בחר מטרה", onclick: openPicker});
    /* Q281: "אזור ההזרקה הצפוי" -- once a target is chosen, its own bundles/heads (origin / insertion / adjacent-tissue
       parts, grouped exactly as structure_parts.json's own part_sets group them) and its own motor point(s) (NMJ),
       read from tool.plan.zone (computed once in planPick(), not recomputed here). */
    ui.zoneTitle = h("div", {class: "mc-lbl", style: "margin-top:4px", text: "אזור ההזרקה הצפוי"});
    ui.zone = h("div", {class: "mc-list"});
    ui.guide = h("div", {class: "mc-guide-host"});   // Q347: the injection guide for this target (private data), filled in refresh()
    ui.step2 = h("div", {class: "mc-step"}, [h("div", {class: "mc-num", text: "2"}), h("div", {class: "mc-lbl", text: "נקודת כניסה"}), (ui.s2sub = h("div", {class: "mc-sub mc-mob", text: "שלב 2 מתוך 3"}))]);
    ui.primary = h("button", {type: "button", class: "mc-primary", text: "הצע נקודות כניסה", onclick: suggest});
    ui.manual = h("button", {type: "button", class: "mc-sec mc-desk", text: "סמן ידנית על העור", onclick: manualEntry});
    ui.hint = h("p", {class: "mc-hint", text: ""});
    ui.cands = h("div", {class: "mc-list"});
    ui.mobRow = h("div", {class: "mc-row mc-mob"}, [
      h("button", {type: "button", class: "mc-sec", text: "סמן ידנית", onclick: manualEntry}),
      (ui.mobHalo = h("button", {type: "button", class: "mc-sec", text: "הילה", "aria-pressed": "true", onclick: toggleHalo})),
      h("button", {type: "button", class: "mc-sec", text: "עוד…", onclick: moreToggle})
    ]);
    ui.step3 = h("div", {class: "mc-step off"}, [h("div", {class: "mc-num", text: "3"}), h("div", {class: "mc-lbl", text: "בדיקת מסלול"})]);
    ui.report = h("div", {class: "mc-hint"});
    /* Q325: the planned path played in the probe image (the scan tool aligns its plane on the needle) */
    ui.scanBtn = h("button", {type: "button", class: "mc-sec", text: "הצג בסריקה", title: "Show in scan: the probe image aligned on this needle path, with a play control", onclick: showInScan});
    /* Q276: "הזרקה ל-2+ מקומות באותו שריר" -- save the current point, see every saved point of this session with its own distance readout */
    ui.addPoint = h("button", {type: "button", class: "mc-sec", text: "הוסף נקודה", title: "שמירת נקודת הכניסה/מטרה הנוכחית כאחת מכמה באותו שריר (לא מחליפה אותה)", onclick: addPoint});
    ui.savedTitle = h("div", {class: "mc-lbl", style: "margin-top:4px", text: "נקודות שמורות"});
    ui.saved = h("div", {class: "mc-list"});
    ui.savedClear = h("button", {type: "button", class: "mc-sec", text: "נקה את כל הנקודות השמורות", onclick: clearSaved});
    buildPlan();   // Q367
    c.main.appendChild(h("div", {class: "mc mc-right mi"}, [h("div", {class: "mc-handle"}), ui.plan, ui.step1, ui.step1Btn, ui.zoneTitle, ui.zone, ui.guide, ui.step2, ui.primary, ui.manual, ui.hint, ui.cands, ui.mobRow, ui.step3, ui.report, ui.scanBtn, ui.addPoint, ui.savedTitle, ui.saved, ui.savedClear]));
    /* left: the distance card */
    ui.rows = h("div", {class: "mc-list"});
    ui.near = h("input", {type: "number", min: "0", max: "100", step: "0.5", "aria-label": "סף קרוב (מ\"מ)"}); ui.far = h("input", {type: "number", min: "0", max: "200", step: "0.5", "aria-label": "סף רחוק (מ\"מ)"});
    ui.edit = h("div", {class: "mc-edit"}, ["קרוב", ui.near, "רחוק", ui.far, h("button", {type: "button", class: "mc-sec", style: "height:32px;flex:0 0 auto;padding:0 10px", text: "אישור", onclick: function () { tool.setCorr({near: +ui.near.value, far: +ui.far.value}); ui.edit.hidden = true; refresh(); }})]);
    ui.edit.hidden = true;
    ui.foot = h("div", {class: "mc-foot"});
    c.main.appendChild(h("div", {class: "mc mc-left mi"}, [h("div", {class: "mc-title", text: ctx.isPhone() ? "הקרובים ביותר" : "מרחק מהמסלול"}), (ui.dhint = h("p", {class: "mc-hint", text: ""})), ui.rows, ui.foot, ui.edit]));
    /* bottom pills */
    ui.pHalo = h("button", {type: "button", class: "mp", text: "הילה", "aria-pressed": "true", onclick: toggleHalo});
    ui.pPost = h("button", {type: "button", class: "mp", text: "תנוחה ספסטית", "aria-pressed": "false", onclick: cyclePosture});
    ui.pParts = h("button", {type: "button", class: "mp", text: "אחיזות (O/I)", "aria-pressed": "false", onclick: toggleParts});
    ui.pSkin = h("button", {type: "button", class: "mp", text: "עור", "aria-pressed": "false", onclick: toggleSkin});
    ui.pLayers = h("button", {type: "button", class: "mp", text: "שכבות…", onclick: layersPop});
    ui.pSafe = h("button", {type: "button", class: "mp", text: "בטיחות", "aria-pressed": "false", onclick: function () { toggleSafe(); }});   // Q367
    [ui.pSafe, ui.pHalo, ui.pPost, ui.pParts, ui.pSkin, ui.pLayers].forEach(function (b) { c.pills.appendChild(b); });
    buildSafe();
    c.pills.hidden = false;
    if (!(api.parts && api.parts())) ui.pParts.disabled = true;
    if (!skinCat) ui.pSkin.hidden = true;
  }
  function refresh() {
    if (!ctx) return;
    var r = targetRec(), hasT = !!tool.target, hasE = !!tool.entry, c = tool.corr;
    setRecLabel(ui.chipName, r, "בחר מטרה…"); setRecLabel(ui.mobText, r, "בחר מטרה…");
    ui.s1ok.textContent = r ? "נבחרה ✓" : ""; ui.step1Btn.hidden = !!r; ui.step1.classList.toggle("off", false);
    /* Q281: Hebrew rendering of the same tool.plan.zone object the bare tool's own #ncl-plan-zone shows -- origin /
       insertion / adjacent-tissue parts (grouped by bundle) and motor point(s), computed once in planPick(). */
    ui.zone.innerHTML = ""; ui.zoneTitle.hidden = !r;
    var zone = tool.plan.zone;
    if (r && zone) {
      /* Q355: only a landmark that is marked on this body is offered (a button that cannot do anything is not shown); the others are
         counted in one short line, so a muscle whose listed landmarks are not marked here no longer reads as a wall of disabled options */
      var unmarked = 0;
      if (zone.groups.length) zone.groups.forEach(function (g) {
        var ok = g.items.filter(function (it) { return it.placed; });
        unmarked += g.items.length - ok.length;
        if (!ok.length) return;
        ui.zone.appendChild(h("p", {class: "mc-hint", style: "margin:4px 0 1px", text: g.name}));
        ok.forEach(function (it) {
          ui.zone.appendChild(h("button", {type: "button", class: "mc-sec",
            onclick: function () { var p = api.parts ? api.parts() : null; if (p && p.focusById) p.focusById(it.id); },
            text: it.name}));
        });
      }); else ui.zone.appendChild(h("p", {class: "mc-hint", text: "אין נתוני מקור/אחיזה/רקמה סמוכה לשריר זה."}));
      if (unmarked) ui.zone.appendChild(h("p", {class: "mc-hint", text: unmarked === 1 ? "נקודה אחת נוספת מופיעה במקורות אך אינה מסומנת על גוף זה." : unmarked + " נקודות נוספות מופיעות במקורות אך אינן מסומנות על גוף זה."}));
      if (zone.mps.length) zone.mps.forEach(function (p, k) {
        var lbl = mpBundleLabel(p);
        ui.zone.appendChild(h("button", {type: "button", class: "mc-sec",
          onclick: function () { tool.useMotorPoint(p); refresh(); },
          text: (lbl ? lbl + " — צומת עצב-שריר" : "צומת עצב-שריר " + (k + 1) + "/" + zone.mps.length)}));
      }); else ui.zone.appendChild(h("p", {class: "mc-hint", text: "אין נתוני צומת עצב-שריר (NMJ) לשריר זה."}));
    }
    /* Q347: the guide's section (no section for a muscle the guide does not cover) */
    var gv = r && tool.guide.data ? tool.guideView(r.i) : null;
    ui.guide.innerHTML = ""; ui.guide.hidden = !gv;
    if (gv) ui.guide.appendChild(guideDom(tool, gv, "he", {btn: "mc-sec", phone: ctx.isPhone(), refresh: refresh}));
    ui.step2.classList.toggle("off", !hasT); ui.primary.disabled = !hasT; ui.manual.disabled = !hasT;
    ui.step3.classList.toggle("off", !(hasT && hasE));
    var hint = "";
    if (!r) hint = "בחר שריר או גיד: הכל מלבד המטרה וכלי-הדם / העצבים הסמוכים יועם.";
    else if (!hasT) hint = "הקש על נקודה בתוך המטרה.";
    else if (ui.manualHint && !hasE) hint = "הקש על העור במודל כדי לסמן את נקודת הכניסה.";
    else if (!hasE) hint = "נקודת המטרה: מרכז המבנה (הקשה בתוכו מזיזה אותה). הצע נקודות כניסה או סמן ידנית על העור.";
    else hint = "הקשה על העור מסמנת נקודת כניסה אחרת.";
    if (tool.sugg.msg) hint = heMsg(tool.sugg.msg);
    ui.hint.textContent = hint;
    ui.cands.innerHTML = "";
    tool.sugg.shown.forEach(function (cd, k) {
      ui.cands.appendChild(h("div", {class: "mc-cand"}, [h("b", {text: (k + 1) + "."}), h("span", {text: fmt(cd.L) + " מ\"מ · מרווח " + fmt(cd.minD) + " מ\"מ"}),
        h("button", {type: "button", text: "השתמש", onclick: function () { tool.adoptSuggestion(cd); ui.manualHint = false; refresh(); }})]));
    });
    var rep = hasT && hasE ? tool.report() : null;
    ui.scanBtn.hidden = !(hasT && hasE && global.NMSKUltrasound && global.NMSKUltrasound.needleClip);
    ui.report.textContent = rep ? "אורך " + fmt(rep.length_mm) + " מ\"מ · חוצה " + rep.crossings.length + " מבנים" + (rep.skin && rep.skin.depth != null ? " · עומק מהעור " + fmt(rep.skin.depth) + " מ\"מ" : "") : "";
    /* Q276: saved points list -- its own marker (drawn by tool.addSavedPoint()) and its own distance readout per row */
    ui.addPoint.disabled = !hasT;
    ui.saved.innerHTML = "";
    if (!tool.savedPts.length) ui.saved.appendChild(h("p", {class: "mc-hint", text: "אין נקודות שמורות עדיין. לתכנון 2+ מקומות באותו שריר: סמנו נקודה ולחצו הוסף נקודה."}));
    tool.savedPts.forEach(function (it, k) {
      var nearest = it.corr.items[0], band = nearest ? tool.band(nearest.d) : null;
      var bandCol = band === "n" ? "#C53030" : band === "m" ? "#C97A1A" : band === "f" ? "#2F855A" : "";
      ui.saved.appendChild(h("div", {class: "mc-cand"}, [
        h("b", {text: "נקודה " + (k + 1)}),
        h("span", {style: bandCol ? "color:" + bandCol : "", text: (it.entry ? fmt(it.L) + ' מ"מ' : "מטרה בלבד") + (nearest ? " · " + fmt(nearest.d) + ' מ"מ מ' + nearest.name : " · אין כלי-דם/עצב ברדיוס")}),
        h("button", {type: "button", text: "הסר", title: "הסרת נקודה " + (k + 1), onclick: function () { removeSaved(it.id); }})
      ]));
    });
    if (tool.savedPts.length) ui.saved.appendChild(h("p", {class: "mc-hint", text: tool.poseAway() ? "המרחקים נמדדו על המודל בתנוחה הנוכחית" : "המרחקים נמדדו בתנוחת המנוחה"}));   // Q332
    ui.savedClear.hidden = !tool.savedPts.length;
    /* distances */
    ui.rows.innerHTML = "";
    if (!hasT && !hasE) ui.dhint.textContent = "בחר מטרה: המרחקים יופיעו כאן ויתעדכנו בכל שינוי.";
    else if (!c.items.length) ui.dhint.textContent = "אין כלי-דם או עצב ברדיוס " + c.R + " מ\"מ.";
    else ui.dhint.textContent = hasE ? "מהמסלול (כניסה ← מטרה)" : "מנקודת המטרה";
    c.items.slice().sort(function (a, b) { return a.d - b.d; }).slice(0, 8).forEach(function (it) {
      var cl = tool.sizeLabel(it.i, "he");   // Q367: the size class (the Safety panel's) next to the name
      ui.rows.appendChild(h("div", {class: "mc-drow band-" + tool.band(it.d)}, [h("div", {class: "bar"}), h("div", {class: "nm"}, [it.name, cl ? h("span", {class: "q367-cl", text: cl}) : null]), h("div", {class: "mm", text: fmt(it.d)}), h("div", {class: "un", text: "מ\"מ"})]));
    });
    if (tool.poseAway && tool.poseAway()) ui.dhint.textContent += " · נמדד על המודל בתנוחה הנוכחית";
    ui.foot.innerHTML = ""; ui.foot.appendChild(document.createTextNode("מדידה בלבד · ספי צבע " + c.near + " / " + c.far + " מ\"מ · "));
    ui.foot.appendChild(h("button", {type: "button", text: "עריכה", onclick: function () { ui.near.value = c.near; ui.far.value = c.far; ui.edit.hidden = !ui.edit.hidden; }}));
    /* pills */
    var halo = !!c.halo; ui.pHalo.setAttribute("aria-pressed", String(halo)); ui.mobHalo.setAttribute("aria-pressed", String(halo));
    ui.pPost.setAttribute("aria-pressed", String(posture !== "off")); ui.pPost.textContent = "תנוחה ספסטית" + (ui.postureMsg ? " · " + ui.postureMsg : "");
    ui.pParts.setAttribute("aria-pressed", String(partsOn));
    if (skinCat) ui.pSkin.setAttribute("aria-pressed", String(!!api.categoryOn(skinCat)));
    renderPlan(); renderSafe();   // Q367
  }
  function enter(c) {
    wasActive = tool.active; partsOn = false; posture = "off"; ui.postureMsg = ""; ui.manualHint = false;
    if (!tool.active) tool.toggle(true);
    tool.setMode("tfirst", true);
    tool.clearSuggestions(); tool.clear();
    if (!hookOn) { tool.hooks.push(refresh); hookOn = true; }
    var sid = c.selectedId(), rec = sid ? tool.recs.filter(function (r) { return r.id === sid && PLAN_CATS[r.cat]; })[0] : null;
    disarm(); ui.rk = null; ui.planeMsg = "";
    if (rec) pickTarget(rec.i); else { refresh(); openPicker("tip"); }
    tool.pinsPlace();
  }
  function exit() {
    closePop(); disarm(); if (ui.safeOpen) toggleSafe(false);   // Q367
    setTimeout(function () { tool.pinsPlace(); }, 0);
    var k = tool.hooks.indexOf(refresh); if (k >= 0) tool.hooks.splice(k, 1); hookOn = false;
    if (posture !== "off") { try { tool.applyPosture("rest", "r"); } catch (e) {} posture = "off"; }
    tool.clearSuggestions(); tool.clear(); tool.planRelease();
    if (!wasActive && tool.active) tool.toggle(false);
    ctx = null;
  }
  /* Q294: Reset (the page-wide history's button) -- back to the start of this mode without leaving it: posture to rest, the path,
     the suggestions and the plan cleared, the target picker reopened (saved injection points are kept: they are the user's record) */
  function reset() {
    closePop(); disarm(); ui.rk = null; ui.planeMsg = "";   // Q367
    if (posture !== "off") { try { tool.applyPosture("rest", "r"); } catch (e) {} posture = "off"; }
    tool.clearSuggestions(); tool.clear(); tool.planRelease();
    try { refresh(); } catch (e2) {}
  }
  return {title: "תכנון הזרקה", short: "הזרקה", build: build, enter: enter, exit: exit, reset: reset};
}

/* ---------- facade for the host page and for test harnesses ---------- */
TP.corridor = function () {   // Q268 test / harness hook: the live readout as data
  var c = this.corr;
  return {near: c.near, far: c.far, R: c.R, n: c.n, ms: Math.round(c.ms * 10) / 10, what: c.what, seq: c.seq || 0,
          items: c.items.map(function (it) { return {id: it.id, name: it.name, cls: it.cls, d_mm: Math.round(it.d * 1000) / 1000}; })};
};
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
    if (global.NMSKModes && global.NMSKModes.register) { try { global.NMSKModes.register("inj", injectionMode(tool, api)); } catch (eM) { console.error("injection mode failed to register:", eM); } }   // Q272
    global.NeedlePath = {        // compatible with the pre-Q188 in-template tool's harness API
      toggle: function (on) { tool.toggle(on); }, clear: function () { tool.clear(); },
      setPoints: function (e, t, eid, tid) { tool.setPath(e, t, eid, tid); },
      report: function () { return tool.report(); },
      toScreen: function (p) { return api.toScreen(p); },
      /* Q268 hooks (items 1-3), used by scripts/anatomy/q268/verify_ui_q268.py and crosscheck_q268.py */
      corridor: function () { return tool.corridor(); }, setCorr: function (o) { tool.setCorr(o); },
      plan: function (id) { var ids = tool.byId[id] || []; if (ids.length) tool.planPick(ids[0]); return ids.length > 0; },
      releasePlan: function () { tool.planRelease(); },
      suggest: function () { return tool.suggest(); }, suggestions: function () { return tool.sugg.shown.map(function (c) { return {entry: c.E.slice(), length_mm: c.L, min_mm: c.minD}; }); },
      adoptSuggestion: function (k) { tool.adoptSuggestion(tool.sugg.shown[k]); },
      posture: function (key, side) { return tool.applyPosture(key, side); },
      /* Q276: 2+ saved injection points on the same target, used by scripts/anatomy/q276/verify_q276.py */
      addSavedPoint: function () { var it = tool.addSavedPoint(); return it ? {id: it.id, target: it.target.p.slice(), entry: it.entry ? it.entry.p.slice() : null, length_mm: it.L} : null; },
      removeSavedPoint: function (id) { return tool.removeSavedPoint(id); },
      clearSavedPoints: function () { tool.clearSavedPoints(); },
      savedPoints: function () {
        return tool.savedPts.map(function (it) {
          return {id: it.id, target_name: it.targetName, length_mm: it.L, nearest: it.corr.items.length ? {name: it.corr.items[0].name, d_mm: it.corr.items[0].d} : null,
                  /* Q332: the readout as now measured, the saved one, and the pose it was measured in; used by scripts/anatomy/q332 */
                  items: it.corr.items.map(function (x) { return {id: x.id, i: x.i, d_mm: x.d}; }), n: it.corr.n,
                  saved_items: it.corr0 ? it.corr0.items.map(function (x) { return {id: x.id, i: x.i, d_mm: x.d}; }) : null,
                  measured_in: it.corrKey, skip_id: it.skipId, R: it.R, entry: it.entry ? it.entry.p.slice() : null, target: it.target.p.slice()};
        });
      }
    };
    return {cursor: function () { return tool.cursor(); },
            setPath: function (e, t, eid, tid) { tool.setPath(e, t, eid, tid); }};
  }
};
})(typeof window !== "undefined" ? window : globalThis);
