'use strict';
/* Q246 continuity suite (node).  node q246_run.js --tool clinical/imaging_tool.js --geo DIR --out out.json [--pgm DIR] [--sites thigh,knee,pelvis,shoulder] [--quick] [--ss N]
 * Series: CT soft / MRI T1 / T2 / PD at 1 mm steps (single slice and 5 mm avg / MIP slabs) in the three orthogonal directions through four sites. */
const fs = require('fs'), path = require('path'), H = require('./q246_lib.js');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i < 0 ? d : (process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[i + 1] : true); };
const TOOL = arg('tool', 'clinical/imaging_tool.js'), GEO = arg('geo'), OUT = arg('out', 'q246_out.json'), PGM = arg('pgm', null), QUICK = !!arg('quick', false);
const TABLE = path.resolve(__dirname, '../../clinical/data/imaging_tissues.json');
const env = H.makeEnv(TOOL, GEO, TABLE), L = env.L, g = env.geo;
if (arg('ssfix', null) && L.DEFAULTS) { L.DEFAULTS.ssBudget = 1e9; L.DEFAULTS.ssFinal = +arg('ssfix'); }   // experiments: force the same ss everywhere
const AIR = env.C.ids.air, FAT = env.C.ids.fat;

function structIdx(id) { return g.ids.indexOf(id); }
function bboxOf(i) { return [[g.bbox[6 * i], g.bbox[6 * i + 1], g.bbox[6 * i + 2]], [g.bbox[6 * i + 3], g.bbox[6 * i + 4], g.bbox[6 * i + 5]]]; }
function sites() {
  const s = {}, fem = bboxOf(structIdx('femur_r')), pat = bboxOf(structIdx('patella_r')), hip = bboxOf(structIdx('hip_bone_r')), hum = bboxOf(structIdx('humerus_r'));
  const mid = (b, a) => (b[0][a] + b[1][a]) / 2;
  s.thigh = {O: [mid(fem, 0), fem[0][1] + 0.5 * (fem[1][1] - fem[0][1]), mid(fem, 2)], fov: {ax: 300, co: 500, sa: 500}};
  s.knee = {O: [mid(pat, 0), mid(pat, 1) - 10, mid(pat, 2) - 15], fov: {ax: 250, co: 400, sa: 400}};
  s.pelvis = {O: [0, hip[0][1] + 0.55 * (hip[1][1] - hip[0][1]), mid(hip, 2)], fov: {ax: 450, co: 600, sa: 600}};
  s.shoulder = {O: [mid(hum, 0), hum[1][1] - 25, mid(hum, 2)], fov: {ax: 400, co: 400, sa: 400}};
  return s;
}
const AX = {ax: [0, -1, 0], co: [0, 0, 1], sa: [-1, 0, 0]};
const CT = {modality: 'ct', L: 40, Wd: 400}, MR = k => ({modality: 'mr', seq: k});

/* slab sub-slice offsets: the tool's rule (new tools export LIB.slabOffsets) */
function slabOffs(th, tier) {
  if (th <= 0.01) return [0];
  if (L.slabOffsets) return L.slabOffsets(-th / 2, th / 2, th, tier === 0 ? 5 : 25);
  const n = Math.max(2, Math.min(tier === 0 ? 5 : 25, Math.ceil(th / 1.0) + 1)), o = []; for (let k = 0; k < n; k++) o.push(-th / 2 + th * k / (n - 1)); return o;
}
function stack(site, dir, pos, opt) {            // images at absolute offsets pos[] (mm along the plane normal); caches the sub-slices by absolute position
  const S = site, n = AX[dir], cache = {}, W = opt.W || 320, ss = opt.ss || (L.chooseSS ? L.chooseSS(slabOffs(opt.thick || 0, 1).length, 1) : 1);
  const lab = (p) => { const key = p.toFixed(3); if (!cache[key]) { const O = [S.O[0] + n[0] * p, S.O[1] + n[1] * p, S.O[2] + n[2] * p]; cache[key] = H.runSlices(env, {n, O, center: S.O, W, fov: S.fov[dir], offsets: [0], ss}); } return cache[key]; };
  return {lab, ms: () => Object.values(cache).reduce((a, c) => a + c.ms, 0), parity: () => Object.values(cache).reduce((a, c) => a + c.parityBad, 0), holes: () => Object.values(cache).reduce((a, c) => a + (c.holes || 0), 0), count: () => Object.keys(cache).length, W, ss, n, S};
}
function imageAt(st, p, o) {                      // value + gray + dominant labels for one output slice at absolute offset p
  const th = o.thick || 0, offs = slabOffs(th, 1), subs = offs.map(d => st.lab(p + d)), r0 = subs[0];
  const res = {labels: subs.map(s => s.labels[0]), fine: subs.map(s => s.fine[0]), sid: subs[Math.floor((subs.length - 1) / 2)].sid, ss: r0.ss, W: r0.W, H: r0.H, px: r0.px, offs, mid: Math.floor((subs.length - 1) / 2),
    plane: {O: subs[Math.floor((subs.length - 1) / 2)].plane.O, u: r0.plane.u, v: r0.plane.v, n: r0.plane.n, u0: r0.plane.u0, v0: r0.plane.v0}, holes: subs.reduce((a, s) => a + (s.holes || 0), 0)};
  const val = H.values(env, res, Object.assign({thick: th, slab: o.slab || 'avg'}, o)), gray = H.toGray(val, o);
  return {val, gray, lab: res.fine && res.fine[res.mid] ? H.majority(res.fine[res.mid], res.ss, res.W, res.H) : res.labels[res.mid], W: res.W, H: res.H, res, holes: res.holes};
}

function seriesMetrics(st, o, n, label, ctx) {
  const pos = []; for (let k = -(n >> 1); k <= (n >> 1); k++) pos.push(k);
  const t0 = Date.now(), imgs = pos.map(p => imageAt(st, p, o)), W = imgs[0].W, Hh = imgs[0].H, air = o.modality === 'ct' ? -1000 : 0, lutSkin = (o.modality === 'ct' ? env.lutCT : env.lutMR(o.seq))[env.C.ids.skin];
  const m = {label, n: imgs.length, subslices: st.count(), kernel_ms_per_subslice: st.ms() / st.count()};
  const flip = {n: 0, iso: 0, body: 0}, nccs = [], madK = {1: [], 2: [], 4: [], 8: []}, chg = {body: 0, changed: 0, iso: 0}, pairs = {}, isl = {tot: 0, fat: 0, body: 0}, jags = [];
  for (let i = 0; i + 1 < imgs.length; i++) {
    const a = imgs[i], b = imgs[i + 1], mk = H.bodyMask(a.lab, AIR, b.lab);
    nccs.push(H.ncc(a.gray, b.gray, mk));
    { const f = H.valueFlips(a.gray, b.gray, mk, W, Hh, 60); flip.n += f.n; flip.iso += f.iso; flip.body += f.body; }
    const c = H.labChange(a.lab, b.lab, AIR, W, Hh, pairs); chg.body += c.body; chg.changed += c.changed; chg.iso += c.iso;
  }
  [1, 2, 4, 8].forEach(k => { for (let i = 0; i + k < imgs.length; i++) { const mk = H.bodyMask(imgs[i].lab, AIR, imgs[i + k].lab); madK[k].push(H.mad(imgs[i].gray, imgs[i + k].gray, mk) / 255); } });
  imgs.forEach(im => { const q = H.islands(im.lab, W, Hh, AIR, FAT); isl.tot += q.tot; isl.fat += q.fat; isl.body += q.body; const jg = H.jaggedness(im.val, W, Hh, air, lutSkin); if (isFinite(jg)) jags.push(jg); });
  m.ncc_adjacent = H.mean(nccs.filter(isFinite)); m.ncc_adjacent_min = Math.min(...nccs.filter(isFinite));
  m.mad_gray = {}; Object.keys(madK).forEach(k => m.mad_gray[k] = H.mean(madK[k]));
  m.label_change_frac = chg.changed / Math.max(1, chg.body); m.label_change_isolated_frac = chg.iso / Math.max(1, chg.changed);
  m.islands_per_100k_body_px = isl.tot / Math.max(1, isl.body) * 1e5; m.fat_islands_per_100k = isl.fat / Math.max(1, isl.body) * 1e5;
  m.edge_jaggedness_px = H.mean(jags);
  m.value_flip_frac = flip.n / Math.max(1, flip.body); m.value_flip_isolated_frac = flip.iso / Math.max(1, flip.n);
  m.odd_rows_per_subslice = st.parity() / st.count() / st.ss; m.holes_filled_px_per_subslice = st.holes() / st.count();
  const topPairs = Object.entries(pairs).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k, v]) => { const [x, y] = k.split(',').map(Number); return [env.className(x) + '|' + env.className(y), +(v / Math.max(1, chg.body) * 1e3).toFixed(3)]; });
  m.top_changing_pairs_permille = topPairs;
  const cs = {}; ['muscle', 'fat', 'bone_cortical'].forEach(c => { const ms = H.classStats(env, imgs.map(i => i.lab), imgs.map(i => i.val), W, Hh, c, 40); cs[c] = ms.length >= 3 ? {slices: ms.length, mean: H.mean(ms.map(x => x.m)), std_across_slices: H.std(ms.map(x => x.m)), mean_within_sd: H.mean(ms.map(x => x.sd))} : null; });
  m.class_intensity = cs;
  m.total_ms = Date.now() - t0;
  if (PGM && ctx) saveSet(imgs, ctx, [0, (imgs.length >> 1), imgs.length - 1].slice(1, 2));
  return m;
}
function saveSet(imgs, ctx, which) {
  fs.mkdirSync(PGM, { recursive: true });
  which.forEach(i => { const im = imgs[i], f = path.join(PGM, ctx + '.pgm'); fs.writeFileSync(f, Buffer.concat([Buffer.from('P5\n' + im.W + ' ' + im.H + '\n255\n'), Buffer.from(im.gray)])); });
}

/* noise: same plane re-rendered, shifted by whole pixels, next slice */
function noiseMetrics(site, dir, modality) {
  const st = stack(site, dir, [0], {}), o = Object.assign({}, modality === 'ct' ? CT : MR('t1_se'), {noise: modality === 'ct' ? 25 : 4});
  const clean = Object.assign({}, o, {noise: 0});
  function noiseOf(p, shiftPx) {
    const S2 = Object.assign({}, site, {O: site.O.slice()});
    if (shiftPx) { const b = L.basis(AX[dir]), px = site.fov[dir] / 320; for (let a = 0; a < 3; a++) S2.O[a] += b.u[a] * px * shiftPx; }
    const st2 = stack(S2, dir, [p], {}), im = imageAt(st2, p, o), im0 = imageAt(st2, p, clean), nz = new Float32Array(im.val.length);
    for (let k = 0; k < nz.length; k++) nz[k] = im.val[k] - im0.val[k];
    return {nz, lab: im.lab, W: im.W, H: im.H, sd: H.std(Array.from(nz.filter((x, k) => im.lab[k] !== AIR)))};
  }
  const a = noiseOf(0, 0), b = noiseOf(0, 0), c = noiseOf(1, 0), d = noiseOf(0, 10), e = noiseOf(0, 0.5);
  const mk = H.bodyMask(a.lab, AIR);
  // pan by 10 whole pixels: noise attached to the tissue means d(x) == a(x+10) where both exist
  const sh = new Float32Array(a.nz.length), shm = new Uint8Array(a.nz.length);
  for (let y = 0; y < a.H; y++) for (let x = 0; x < a.W - 10; x++) { sh[y * a.W + x] = d.nz[y * a.W + x]; shm[y * a.W + x] = mk[y * a.W + x + 10]; }
  const a10 = new Float32Array(a.nz.length); for (let y = 0; y < a.H; y++) for (let x = 0; x < a.W - 10; x++) a10[y * a.W + x] = a.nz[y * a.W + x + 10];
  return {noise_sd: a.sd, corr_same_plane_rerender: H.ncc(a.nz, b.nz, mk), corr_adjacent_1mm: H.ncc(a.nz, c.nz, mk), corr_pan_10px_tissue_attached: H.ncc(a10, sh, shm), corr_pan_half_px: H.ncc(a.nz, e.nz, mk)};
}
/* sub-pixel pan / sub-mm plane step.  A continuous image moves linearly between two nearby renders: r(q) ~ (r(0) + r(h)) / 2.  linRes = mean|r(q) - (r(0)+r(h))/2| / mean|r(0) - r(h)| over the body
 * (0 = perfectly smooth motion; label images flip pixels and give a large residual) */
function linRes(rs, mk) {
  let a = 0, b = 0, n = 0;
  for (let k = 0; k < rs[0].gray.length; k++) { if (!mk[k]) continue; const g0 = rs[0].gray[k], g1 = rs[1].gray[k], g2 = rs[2].gray[k]; a += Math.abs(g1 - (g0 + g2) / 2); b += Math.abs(g0 - g2); n++; }
  return b > 0 ? a / b : NaN;
}
function panMetrics(site, dir, o) {
  const b = L.basis(AX[dir]), px = site.fov[dir] / 320, out = {};
  function render(shift) {
    const S2 = Object.assign({}, site, {O: site.O.slice()}); for (let a = 0; a < 3; a++) S2.O[a] += b.u[a] * px * shift;
    const st = stack(S2, dir, [0], {thick: 0}); return imageAt(st, 0, Object.assign({}, o, {thick: 0}));
  }
  const r0 = render(0), r1 = render(0.25), r2 = render(0.5), r3 = render(0.75), r4 = render(1.0), mk = H.bodyMask(r0.lab, AIR);
  out.pan_lin_residual = (linRes([r0, r1, r2], mk) + linRes([r2, r3, r4], mk)) / 2;
  out.mad_quarter_px = H.mad(r0.gray, r1.gray, mk) / 255; out.mad_one_px = H.mad(r0.gray, r4.gray, mk) / 255;
  const st = stack(site, dir, [], {thick: 0}), zs = [0, 0.25, 0.5, 0.75, 1.0].map(p => imageAt(st, p, Object.assign({}, o, {thick: 0})));
  out.z_lin_residual = (linRes([zs[0], zs[1], zs[2]], mk) + linRes([zs[2], zs[3], zs[4]], mk)) / 2;
  return out;
}

/* coil bias (new tool only): per-slice mean of interior muscle pixels with / without the bias field; smoothness = largest slice-to-slice change of the field */
function biasMetrics(site) {
  if (!env.hasNew) return null;
  const st = stack(site, 'ax', [], {thick: 0}), o0 = Object.assign({thick: 0}, MR('t1_se')), o1 = Object.assign({}, o0, {bias: 0.2}), pos = []; for (let k = -20; k <= 20; k++) pos.push(k);
  const a = pos.map(p => imageAt(st, p, o0)), b = pos.map(p => imageAt(st, p, o1)), m0 = H.classStats(env, a.map(i => i.lab), a.map(i => i.val), a[0].W, a[0].H, 'muscle', 40), m1 = H.classStats(env, b.map(i => i.lab), b.map(i => i.val), b[0].W, b[0].H, 'muscle', 40);
  const f = m1.map((x, i) => x.m / m0[i].m), df = f.slice(1).map((x, i) => Math.abs(x - f[i]));
  return {slices: f.length, field_min: Math.min(...f), field_max: Math.max(...f), max_step_between_1mm_slices: Math.max(...df), within_slice_sd_muscle_unbiased: H.mean(m0.map(x => x.sd)), within_slice_sd_muscle_biased: H.mean(m1.map(x => x.sd))};
}
const R = {tool: TOOL, ss: env.SS, hasNew: env.hasNew, series: {}, noise: {}, pan: {}, bias: {}, perf: {}};
const siteDefs = sites(), want = (arg('sites', 'thigh,pelvis,knee,shoulder') + '').split(',');
const N = QUICK ? 15 : 41, PERFONLY = !!arg('perfonly', false);
for (const name of PERFONLY ? [] : want) {
  const S = siteDefs[name];
  for (const dir of ['ax', 'co', 'sa']) {
    const st = stack(S, dir, [], {thick: 0}), st5 = stack(S, dir, [], {thick: 5});
    R.series[`${name}.${dir}.ct_single`] = seriesMetrics(st, Object.assign({thick: 0}, CT), N, 'CT soft, single slice, 1 mm steps', `${name}_${dir}_ct`);
    R.series[`${name}.${dir}.ct_avg5`] = seriesMetrics(st5, Object.assign({thick: 5, slab: 'avg'}, CT), N, 'CT soft, 5 mm average slab', `${name}_${dir}_ct5`);
    if (dir === 'ax') R.series[`${name}.${dir}.ct_avg15`] = seriesMetrics(stack(S, dir, [], {thick: 15}), Object.assign({thick: 15, slab: 'avg'}, CT), QUICK ? N : 25, 'CT soft, 15 mm average slab', null);
    R.series[`${name}.${dir}.ct_mip5`] = seriesMetrics(st5, Object.assign({thick: 5, slab: 'mip'}, CT), N, 'CT soft, 5 mm MIP slab', null);
    ['t1_se', 't2_se', 'pd_se'].forEach(k => { if (env.T.mr_sequences.some(q => q.key === k)) R.series[`${name}.${dir}.mr_${k}`] = seriesMetrics(st, Object.assign({thick: 0}, MR(k)), N, 'MRI ' + k + ', single slice', `${name}_${dir}_${k}`); });
  }
  if (!QUICK) { R.noise[name] = {ct: noiseMetrics(S, 'ax', 'ct'), mr: noiseMetrics(S, 'ax', 'mr')}; R.pan[name] = panMetrics(S, 'ax', CT); R.bias[name] = biasMetrics(S); }
  console.error('site done', name);
}
/* performance: ms per image at the sizes the tool uses (kernel + combine), thigh axial */
{
  const S = siteDefs.thigh;
  [['preview224_5sub', 224, 5, 1], ['final320_single', 320, 0, 1], ['final320_slab5', 320, 5, 1], ['single384', 384, 0, 1], ['final320_slab25', 320, 25, 1]].forEach(([k, W, th, _t]) => {
    const ts = [], tk = [], tier = k.startsWith('preview') ? 0 : 1, offs = th === 0 ? [0] : slabOffs(th, tier);
    for (let rep = 0; rep < 6; rep++) {
      const st = stack(S, 'ax', [], {W, ss: L.chooseSS ? L.chooseSS(offs.length, tier) : 1}), t0 = process.hrtime.bigint();
      const subs = offs.map(d => st.lab(rep * 0.37 + d)); const tk0 = subs.reduce((a, s) => a + s.ms, 0);
      const res = {labels: subs.map(s => s.labels[0]), fine: subs.map(s => s.fine[0]), sid: subs[0].sid, ss: subs[0].ss, W, H: W, px: subs[0].px, offs, mid: Math.floor((offs.length - 1) / 2), plane: subs[0].plane};
      H.values(env, res, Object.assign({thick: th, slab: 'avg'}, CT)); ts.push(Number(process.hrtime.bigint() - t0) / 1e6); tk.push(tk0);
    }
    R.perf[k] = {total_ms: H.mean(ts.slice(2)), kernel_ms: H.mean(tk.slice(2)), subslices: th === 0 ? 1 : slabOffs(th, k.startsWith('preview') ? 0 : 1).length, ss: L.chooseSS ? L.chooseSS(offs.length, tier) : 1};
  });
  // dragging uses the preview tier (ss 1): measured with ss = 1 explicitly
  const st = stack(S, 'ax', [], {W: 224, ss: 1}); const t0 = process.hrtime.bigint(); const sub = st.lab(0.11); R.perf.drag_preview224_ss1_kernel_ms = Number(process.hrtime.bigint() - t0) / 1e6;
}
fs.writeFileSync(OUT, JSON.stringify(R, null, 1));
console.error('written', OUT);
