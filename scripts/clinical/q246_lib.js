'use strict';
/* Q246 continuity harness (node): loads an exported geometry package (scripts/clinical/q246_export_geo.py) and a copy of clinical/imaging_tool.js (--tool), runs the real
 * kernel on plane stacks and measures how continuous the resulting CT / MRI images are.  Works with the pre-Q246 tool (legacy renderer replicated here, 1 label per pixel)
 * and with the Q246 tool (area-weighted partial volume, 3-D coherent noise: LIB.renderValues). */
const fs = require('fs'), path = require('path');

function loadGeo(dir) {
  const meta = JSON.parse(fs.readFileSync(path.join(dir, 'meta.json'), 'utf8')), T = {f4: Float32Array, u4: Uint32Array, u1: Uint8Array}, g = {};
  Object.keys(meta.dtype).forEach(k => { const b = fs.readFileSync(path.join(dir, k + '.bin')); const ab = b.buffer.slice(b.byteOffset, b.byteOffset + b.length); g[k] = new T[meta.dtype[k]](ab); });
  g.n = meta.n; g.names = meta.names; g.ids = meta.ids; g.bodyBox = meta.bodyBox; g.nv = meta.nv; g.nt = meta.nt;
  return g;
}

function makeEnv(toolPath, geoDir, tablePath) {
  delete globalThis.NMSKImagingLib; delete require.cache[require.resolve(path.resolve(toolPath))];
  require(path.resolve(toolPath));
  const L = globalThis.NMSKImagingLib, T = JSON.parse(fs.readFileSync(tablePath, 'utf8')), C = L.compileTable(T), geo = loadGeo(geoDir);
  const K = L.KERNEL_FACTORY(); K.setGeometry({n: geo.n, pos: geo.pos, idx: geo.idx, vStart: geo.vStart, tStart: geo.tStart, bbox: geo.bbox, cls: geo.cls, kind: geo.kind, skin: geo.skin, render: geo.render, order: geo.order, skinList: geo.skinList});
  const bone = {}; Object.keys(C.kinds).forEach(k => { const p = C.kinds[k]; bone[p.id] = {axial: !!p.axial, tthin: p.tthin, tmax: p.tmax, frac: p.frac, canal: !!p.canal, z0: p.z0 || 0.2, z1: p.z1 || 0.8, ramp: p.ramp || 0.08}; });
  const env = {L, T, C, geo, K, bone, seq: 0, SS: (L.DEFAULTS && L.DEFAULTS.ssFinal) || 1, hasNew: !!L.renderValues};
  env.cls = k => C.by[k]._i; env.className = i => T.classes[i].key;
  env.lutCT = L.ctTable(C);
  env.lutMR = key => { const sp = JSON.parse(JSON.stringify(T.mr_sequences.filter(q => q.key === key)[0])); return L.mrTable(C, sp).sig; };
  return env;
}

/* planes: {n, O, center, W, fov, offsets[], ss} -> {labels[], fine[]|null, sid, ss, W, H, px, plane:{O,u,v,n,u0,v0}, ms, parityBad} */
function runSlices(env, spec) {
  const L = env.L, b = L.basis(spec.n), W = spec.W || 320, H = spec.H || W, px = (spec.fov || 400) / W, cen = spec.center || spec.O, ss = spec.ss || 1;
  const dot = (a, c) => a[0] * c[0] + a[1] * c[1] + a[2] * c[2];
  const rel = [cen[0] - spec.O[0], cen[1] - spec.O[1], cen[2] - spec.O[2]], cu = dot(b.u, rel), cv = dot(b.v, rel), u0 = cu - W * px / 2, v0 = cv + H * px / 2, offs = spec.offsets || [0];
  const out = {labels: [], fine: [], sid: null, ss, W, H, px, offs, plane: {O: spec.O, u: b.u, v: b.v, n: b.n, u0, v0}, ms: 0, parityBad: 0, mid: Math.floor((offs.length - 1) / 2)};
  const base = {key: 'k' + (++env.seq) + '|' + Math.random(), W, H, O: spec.O, u: b.u, v: b.v, n: b.n, u0, v0, px, smin: Math.min(...offs), smax: Math.max(...offs), skinMm: env.T.bone_model.skin_thickness_mm, ids: env.C.ids, bone: env.bone};
  if (ss > 1) base.ss = ss;
  offs.forEach((s, k) => {
    const R = Object.assign({}, base, {s, wantSid: k === out.mid}), t0 = process.hrtime.bigint(), r = env.K.slice(R);
    out.ms += Number(process.hrtime.bigint() - t0) / 1e6; out.parityBad += r.parityBad; out.holes = (out.holes || 0) + (r.holesFilled || 0);
    out.labels.push(r.lab); out.fine.push(r.fine || null); if (k === out.mid) out.sid = r.sid;
  });
  return out;
}

/* ---- value image from a slice result (legacy = pre-Q246 combine; new = LIB.renderValues) ---- */
let legacySeed = 12345;
function lrnd() { legacySeed ^= legacySeed << 13; legacySeed ^= legacySeed >>> 17; legacySeed ^= legacySeed << 5; return ((legacySeed >>> 0) + 0.5) / 4294967296; }
function lgauss() { return Math.sqrt(-2 * Math.log(lrnd())) * Math.cos(6.283185307 * lrnd()); }
function legacyValues(res, lut, o) {
  const N = res.W * res.H, nS = res.labels.length, out = new Float32Array(N); let s, k;
  if (nS === 1 || o.thick <= 0.01) { const L0 = res.labels[Math.min(res.mid, nS - 1)]; for (k = 0; k < N; k++) out[k] = lut[L0[k]]; }
  else if (o.slab === 'avg') { for (s = 0; s < nS; s++) { const Ls = res.labels[s]; for (k = 0; k < N; k++) out[k] += lut[Ls[k]]; } for (k = 0; k < N; k++) out[k] /= nS; }
  else if (o.slab === 'mip') { out.fill(-1e9); for (s = 0; s < nS; s++) { const Lm = res.labels[s]; for (k = 0; k < N; k++) { const a = lut[Lm[k]]; if (a > out[k]) out[k] = a; } } }
  else { out.fill(1e9); for (s = 0; s < nS; s++) { const Ln = res.labels[s]; for (k = 0; k < N; k++) { const a = lut[Ln[k]]; if (a < out[k]) out[k] = a; } } }
  if (o.noise > 0) { const sg = o.modality === 'ct' ? o.noise : o.noise / 100; for (k = 0; k < N; k++) { if (o.modality === 'ct') out[k] += sg * lgauss(); else { const n1 = sg * lgauss(), n2 = sg * lgauss(); out[k] = Math.sqrt((out[k] + n1) * (out[k] + n1) + n2 * n2); } } }
  return out;
}
function values(env, res, o) {
  const lut = o.modality === 'ct' ? env.lutCT : env.lutMR(o.seq || 't1_se');
  o = Object.assign({modality: 'ct', slab: 'avg', thick: 0, noise: 0}, o);
  if (env.hasNew) return env.L.renderValues(res, lut, Object.assign({px: res.px, plane: res.plane, offs: res.offs, mid: res.mid}, o));
  return legacyValues(res, lut, o);
}
function toGray(val, o) {
  const lo = o.modality === 'ct' ? (o.L == null ? 40 : o.L) - (o.Wd || 400) / 2 : 0, sc = o.modality === 'ct' ? 255 / (o.Wd || 400) : 255, g = new Uint8Array(val.length);
  for (let k = 0; k < val.length; k++) { const q = (val[k] - lo) * sc; g[k] = q < 0 ? 0 : q > 255 ? 255 : q; }
  return g;
}

/* dominant (majority) class of each pixel's ss x ss samples: the label the AREA-weighted image is dominated by (the centre sample of the result is what the readout shows) */
function majority(fine, ss, W, H) {
  if (!fine || ss <= 1) return fine;
  const out = new Uint8Array(W * H), Wf = W * ss, cnt = new Uint16Array(256), seen = [];
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    seen.length = 0; let best = 0, bc = 0;
    for (let b = 0; b < ss; b++) for (let a = 0; a < ss; a++) { const c = fine[(y * ss + b) * Wf + x * ss + a]; if (!cnt[c]) seen.push(c); cnt[c]++; if (cnt[c] > bc || (cnt[c] === bc && c === fine[(y * ss + (ss >> 1)) * Wf + x * ss + (ss >> 1)])) { bc = cnt[c]; best = c; } }
    out[y * W + x] = best; for (const c of seen) cnt[c] = 0;
  }
  return out;
}
/* ---- metrics ---- */
function ncc(a, b, mask) {
  let n = 0, sa = 0, sb = 0, saa = 0, sbb = 0, sab = 0;
  for (let k = 0; k < a.length; k++) { if (mask && !mask[k]) continue; const x = a[k], y = b[k]; n++; sa += x; sb += y; saa += x * x; sbb += y * y; sab += x * y; }
  if (n < 10) return NaN;
  const ma = sa / n, mb = sb / n, va = saa / n - ma * ma, vb = sbb / n - mb * mb;
  if (va < 1e-12 || vb < 1e-12) return NaN;
  return (sab / n - ma * mb) / Math.sqrt(va * vb);
}
function mad(a, b, mask) { let n = 0, s = 0; for (let k = 0; k < a.length; k++) { if (mask && !mask[k]) continue; n++; s += Math.abs(a[k] - b[k]); } return n ? s / n : NaN; }
function bodyMask(lab, air, ...more) { const m = new Uint8Array(lab.length); for (let k = 0; k < lab.length; k++) m[k] = lab[k] !== air ? 1 : 0; for (const o of more) for (let k = 0; k < lab.length; k++) if (o[k] !== air) m[k] = 1; return m; }
function labChange(A, B, air, W, H, pairs) {
  const ch = new Uint8Array(A.length); let body = 0, changed = 0, iso = 0;
  for (let k = 0; k < A.length; k++) { if (A[k] === air && B[k] === air) continue; body++; if (A[k] !== B[k]) { ch[k] = 1; changed++; if (pairs) { const key = Math.min(A[k], B[k]) + ',' + Math.max(A[k], B[k]); pairs[key] = (pairs[key] || 0) + 1; } } }
  for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) { const k = y * W + x; if (ch[k] && !ch[k - 1] && !ch[k + 1] && !ch[k - W] && !ch[k + W]) iso++; }
  return {body, changed, iso};
}
function valueFlips(ga, gb, mask, W, H, thr) {                                 // pixels whose display value jumps by more than thr grey levels between neighbouring slices; isolated = no flipping 4-neighbour
  const f = new Uint8Array(ga.length); let n = 0, body = 0, iso = 0;
  for (let k = 0; k < ga.length; k++) { if (!mask[k]) continue; body++; if (Math.abs(ga[k] - gb[k]) > thr) { f[k] = 1; n++; } }
  for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) { const k = y * W + x; if (f[k] && !f[k - 1] && !f[k + 1] && !f[k - W] && !f[k + W]) iso++; }
  return {n, iso, body};
}
function islands(lab, W, H, air, fatId) {
  let tot = 0, fat = 0, body = 0;
  for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) {
    const k = y * W + x, c = lab[k]; if (c === air) continue; body++;
    const nb = [lab[k - 1], lab[k + 1], lab[k - W], lab[k + W], lab[k - W - 1], lab[k - W + 1], lab[k + W - 1], lab[k + W + 1]];
    let same = 0, cnt = {}, best = -1, bc = 0; for (const q of nb) { if (q === c) same++; cnt[q] = (cnt[q] || 0) + 1; if (cnt[q] > bc) { bc = cnt[q]; best = q; } }
    if (same === 0 && bc >= 6 && best !== air) { tot++; if (c === fatId) fat++; }
  }
  return {tot, fat, body};
}
/* sub-pixel outline position of the body from a value image: first crossing of 50 % between the air value and the skin value; returns {rows:[{L,R}], cols:[{T,B}]} */
function edgeSeries(val, W, H, air, skin) {
  const thr = air + 0.5 * (skin - air), up = skin > air;
  function cross(get, n, fwd) {
    for (let t = 0; t < n; t++) {
      const i = fwd ? t : n - 1 - t, v = get(i), pv = (fwd ? i - 1 : i + 1), a = pv >= 0 && pv < n ? get(pv) : air;
      if (up ? v < thr : v > thr) continue;
      const f = (thr - a) / (v - a);                                           // 0..1 between the previous pixel centre and this one
      return fwd ? (i - 1 + f) + 0.5 : (i + 1 - f) + 0.5;
    }
    return NaN;
  }
  const rows = [], cols = [];
  for (let y = 0; y < H; y++) rows.push([cross(x => val[y * W + x], W, true), cross(x => val[y * W + x], W, false)]);
  for (let x = 0; x < W; x++) cols.push([cross(y => val[y * W + x], H, true), cross(y => val[y * W + x], H, false)]);
  return {rows, cols};
}
function jag(series) {                                                         // RMS of the second difference / sqrt(6), only where the edge is steep enough in that direction
  let s = 0, n = 0;
  for (const side of [0, 1]) for (let i = 1; i < series.length - 1; i++) {
    const a = series[i - 1][side], b = series[i][side], c = series[i + 1][side]; if (!(isFinite(a) && isFinite(b) && isFinite(c))) continue;
    if (Math.abs(c - a) > 2.5) continue;
    const d2 = a - 2 * b + c; s += d2 * d2; n++;
  }
  return n ? Math.sqrt(s / n / 6) : NaN;
}
function jaggedness(val, W, H, air, skin) {
  const e = edgeSeries(val, W, H, air, skin), jr = jag(e.rows), jc = jag(e.cols);
  const v = [jr, jc].filter(isFinite); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : NaN;
}
function classStats(env, labs, vals, W, H, cname, minCount) {                    // per-slice mean of interior pixels of one class
  const c = env.cls(cname), means = [];
  for (let s = 0; s < labs.length; s++) {
    const lab = labs[s], val = vals[s]; let n = 0, sum = 0, sq = 0;
    for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) {
      const k = y * W + x; if (lab[k] !== c) continue;
      if (lab[k - 1] !== c || lab[k + 1] !== c || lab[k - W] !== c || lab[k + W] !== c || lab[k - W - 1] !== c || lab[k - W + 1] !== c || lab[k + W - 1] !== c || lab[k + W + 1] !== c) continue;
      n++; sum += val[k]; sq += val[k] * val[k];
    }
    if (n >= (minCount || 40)) means.push({m: sum / n, sd: Math.sqrt(Math.max(0, sq / n - (sum / n) * (sum / n))), n});
  }
  return means;
}
function mean(a) { return a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN; }
function std(a) { if (a.length < 2) return NaN; const m = mean(a); return Math.sqrt(a.reduce((s, x) => s + (x - m) * (x - m), 0) / a.length); }

module.exports = {majority, valueFlips, loadGeo, makeEnv, runSlices, values, toGray, ncc, mad, bodyMask, labChange, islands, edgeSeries, jaggedness, classStats, mean, std, legacyValues};
