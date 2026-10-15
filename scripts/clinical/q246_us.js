'use strict';
/* Q246 ultrasound continuity harness (node): replicates the frame pipeline of clinical/ultrasound_tool.js (poseOf -> kernel slice -> simulate) on an exported geometry.
 * node q246_us.js --itool imaging_tool.js --utool ultrasound_tool.js --geo DIR --out out.json [--pgm DIR] [--scenes thigh,abdomen] [--quick]
 * `refMode` (auto): the Q246 tool passes `ref` (body-fixed speckle lattice), the pre-Q246 tool does not (plane-fixed pattern, a new seed per star frame). */
const fs = require('fs'), path = require('path'), H = require('./q246_lib.js');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i < 0 ? d : (process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[i + 1] : true); };
const ITOOL = arg('itool'), UTOOL = arg('utool'), GEO = arg('geo'), OUT = arg('out', 'q246_us.json'), PGM = arg('pgm', null), QUICK = !!arg('quick', false);
const TABLE = path.resolve(__dirname, '../../clinical/data/imaging_tissues.json'), UST = path.resolve(__dirname, '../../clinical/data/ultrasound_tissues.json');
const env = H.makeEnv(ITOOL, GEO, TABLE), g = env.geo;
delete globalThis.NMSKUltrasoundLib; delete require.cache[require.resolve(path.resolve(UTOOL))]; require(path.resolve(UTOOL));
const U = globalThis.NMSKUltrasoundLib, US = JSON.parse(fs.readFileSync(UST, 'utf8')), AC = U.compileAcoustics(US, env.C), NEW = typeof U.hash3 === 'function';
const AIR = env.C.ids.air;
const axisCache = {}; function axisOf(sid) { if (sid < 0 || sid >= g.n) return null; if (axisCache[sid] === undefined) axisCache[sid] = U.pcaAxis(g.pos, g.vStart[sid], g.vStart[sid + 1]); return axisCache[sid]; }
const geo = {pos: g.pos, idx: g.idx, tStart: g.tStart, bbox: g.bbox, skinList: g.skinList};
function bb(id) { const i = g.ids.indexOf(id); return [[g.bbox[6 * i], g.bbox[6 * i + 1], g.bbox[6 * i + 2]], [g.bbox[6 * i + 3], g.bbox[6 * i + 4], g.bbox[6 * i + 5]]]; }
const mid = (b, a) => (b[0][a] + b[1][a]) / 2;

function place(o, d) { const h = U.skinHit(geo, o, U.unit(d), null); if (!h) throw new Error('no skin'); let N = U.smoothNormal(geo, h.point, 15, null, h.struct); if (U.dot(N, d) > 0) N = [-N[0], -N[1], -N[2]]; return {P: h.point, N}; }
const fem = bb('femur_r'), bodyBox = g.bodyBox;
const SCENES = {
  thigh: () => Object.assign(place([mid(fem, 0), fem[0][1] + 0.5 * (fem[1][1] - fem[0][1]), bodyBox.hi[2] + 600], [0, 0, -1]), {probe: 'linear', refKey: 'long', freq: 7.5, depthCm: 5}),
  abdomen: () => Object.assign(place([(bodyBox.lo[0] + bodyBox.hi[0]) / 2 + 20, bodyBox.lo[1] + 0.62 * (bodyBox.hi[1] - bodyBox.lo[1]), bodyBox.hi[2] + 600], [0, 0, -1]), {probe: 'convex', refKey: 'long', freq: 3.5, depthCm: 12})
};
function makeS(scene, over) {
  const p = US.probes[scene.probe];
  return Object.assign({probe: scene.probe, width: p.width_default, freq: scene.freq, depthCm: scene.depthCm, gain: 0, tgc: 0, focusCm: scene.depthCm * 0.5, dr: 60, refKey: scene.refKey, rot: 0, speckle: true, textures: true, reverb: true, noise: false, seed: 11, P: scene.P, N: scene.N, mode: 'star', maxDim: 320, maxLines: 192}, over || {});
}
function poseOf(S, spec) {
  const rot = spec.rotOverride != null ? spec.rotOverride : S.rot, pf = U.probeFrame(S.N, U.REF[S.refKey], rot, spec.tilt, spec.dir);
  let O = [S.P[0] + pf.e[0] * spec.off, S.P[1] + pf.e[1] * spec.off, S.P[2] + pf.e[2] * spec.off], shift = 0;
  if (spec.off !== 0) { const o2 = [O[0] + pf.N[0] * 60, O[1] + pf.N[1] * 60, O[2] + pf.N[2] * 60], h = U.skinHit(geo, o2, pf.b, null); if (h && h.t < 140) { shift = h.t - 60; O = h.point; } }
  return {pf, O, shift};
}
function frame(S, spec, uniform) {
  const pose = poseOf(S, spec), p = US.probes[S.probe], geom = U.fanGeom(S.probe, S.width, p.radius_mm, p.fan_deg, S.depthCm * 10), plan = U.planRaster(geom, S.maxDim, {maxLines: S.maxLines});
  const u = pose.pf.u, v = pose.pf.N, n = U.cross(u, v);
  const R = {key: 'us' + (++env.seq) + Math.random(), W: plan.W, H: plan.H, O: pose.O, u, v, n, u0: plan.xr0, v0: -plan.yr0, px: plan.px, smin: 0, smax: 0, s: 0, wantSid: true, skinMm: env.T.bone_model.skin_thickness_mm, ids: env.C.ids, bone: env.bone, extTop: NEW};
  const t0 = process.hrtime.bigint(), r = env.K.slice(R), tk = Number(process.hrtime.bigint() - t0) / 1e6;
  if (uniform) { r.lab = new Uint8Array(r.lab.length).fill(env.cls('liver')); r.sid = null; }          // homogeneous liver: only the speckle remains
  const o = {AC, geom, plan, lab: r.lab, sid: r.sid, freq: S.freq, depthMm: S.depthCm * 10, gainDb: S.gain, tgcDb: S.tgc, focusMm: S.focusCm * 10, speckle: S.speckle, textures: S.textures, reverb: S.reverb, noise: S.noise,
    seed: NEW ? S.seed : (S.mode === 'star' ? S.seed + 131 * (spec.id || 0) : S.seed), elevMm: S.mode === 'star' ? 0 : spec.off, frame: {O: pose.O, u: pose.pf.u, b: pose.pf.b, e: pose.pf.e, zoff: 0}, axisOf};
  if (NEW) { const rot = spec.rotOverride != null ? spec.rotOverride : S.rot, rp = U.probeFrame(S.N, U.REF[S.refKey], rot, S.mode === 'star' ? 0 : spec.tilt, S.mode === 'star' ? 0 : spec.dir); o.ref = {O: S.P, u: rp.u, b: rp.b, e: rp.e}; }
  const t1 = process.hrtime.bigint(), sim = U.simulate(o), ts = Number(process.hrtime.bigint() - t1) / 1e6;
  const gray = U.toGray(sim.db, US.global.display_ref_fraction, S.gain, S.dr);
  return {kr: {parityBad: r.parityBad, repaired: r.repairedRows, holes: r.holesFilled, nCand: r.nCand}, sim, gray, db: sim.db, lab: r.lab, W: sim.Wo, H: sim.Ho, plan, pose, kernel_ms: tk, sim_ms: ts, spec, lw: plan.W, lh: plan.H};
}
const fanCache = {};
function fanPixels(S, f) {                                                      // pixels inside the fan geometry (from a homogeneous reference frame of the same probe / depth)
  const key = S.probe + S.depthCm; if (!fanCache[key]) { const g0 = frame(Object.assign({}, S, {mode: 'star'}), {id: 0, tilt: 0, dir: 0, off: 0}, true); fanCache[key] = g0.db.reduce((a, v) => a + (v > -150 ? 1 : 0), 0); }
  return fanCache[key];
}
const inFan = f => { const m = new Uint8Array(f.db.length); for (let k = 0; k < m.length; k++) m[k] = f.db[k] > -150 ? 1 : 0; return m; };
function nccDb(a, b) { const m = inFan(a), m2 = inFan(b); for (let k = 0; k < m.length; k++) m[k] = m[k] & m2[k]; return H.ncc(a.gray, b.gray, m); }
function madDb(a, b) { const m = inFan(a), m2 = inFan(b); for (let k = 0; k < m.length; k++) m[k] = m[k] & m2[k]; return H.mad(a.gray, b.gray, m) / 255; }
function highpass(gr, W, Hh, r) {                                              // texture residual: gray minus a box blur
  const out = new Float32Array(gr.length), t = new Float32Array(gr.length);
  for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) { let s = 0, n = 0; for (let i = -r; i <= r; i++) { const xx = x + i; if (xx >= 0 && xx < W) { s += gr[y * W + xx]; n++; } } t[y * W + x] = s / n; }
  for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) { let s = 0, n = 0; for (let i = -r; i <= r; i++) { const yy = y + i; if (yy >= 0 && yy < Hh) { s += t[yy * W + x]; n++; } } out[y * W + x] = gr[y * W + x] - s / n; }
  return out;
}
function texNcc(a, b) { const m = inFan(a), m2 = inFan(b); for (let k = 0; k < m.length; k++) m[k] = m[k] & m2[k]; return H.ncc(highpass(a.gray, a.W, a.H, 4), highpass(b.gray, b.W, b.H, 4), m); }
function labChangeFrac(a, b) { let n = 0, c = 0; for (let k = 0; k < a.lab.length && k < b.lab.length; k++) { if (a.lab[k] === AIR && b.lab[k] === AIR) continue; n++; if (a.lab[k] !== b.lab[k]) c++; } return c / Math.max(1, n); }
function depthRoughness(f) {                                                   // centre band of the dB image averaged laterally, RMS of the 2nd difference per row (dB) below the skin line
  const W = f.W, Hh = f.H, c0 = Math.floor(W * 0.45), c1 = Math.ceil(W * 0.55), prof = [];
  for (let y = 0; y < Hh; y++) { let s = 0, n = 0; for (let x = c0; x < c1; x++) { const v = f.db[y * W + x]; if (v > -150) { s += v; n++; } } prof.push(n ? s / n : NaN); }
  let a = 0, n = 0; for (let y = 1; y < Hh - 1; y++) { if (isFinite(prof[y - 1]) && isFinite(prof[y]) && isFinite(prof[y + 1])) { const d2 = prof[y - 1] - 2 * prof[y] + prof[y + 1]; a += d2 * d2; n++; } }
  return n ? Math.sqrt(a / n) : NaN;
}
function savePgm(f, name) { if (!PGM) return; fs.mkdirSync(PGM, {recursive: true}); fs.writeFileSync(path.join(PGM, name + '.pgm'), Buffer.concat([Buffer.from('P5\n' + f.W + ' ' + f.H + '\n255\n'), Buffer.from(f.gray)])); }

if (process.env.Q246_DEBUG_SCENE) { for (const sc of (arg('scenes', 'thigh,abdomen') + '').split(',')) { const q = SCENES[sc](), S = makeS(q), f = frame(S, {id: 0, tilt: 0, dir: 0, off: 0}); console.error(sc, 'P', q.P.map(x => +x.toFixed(1)), 'N', q.N.map(x => +x.toFixed(3)), 'contact', f.sim.contact, 'ysk', f.sim.ysk, 'kernel', JSON.stringify(f.kr), 'finite px', f.db.filter(v => v > -150).length, 'of', f.db.length, 'stats', JSON.stringify(f.sim.stats)); if (process.env.Q246_DEBUG_SCENE === '2') { const pl = f.plan, ix = Math.round((0 - pl.xr0) / pl.px); let run = '', prev = -1, cnt = 0; for (let iy = 0; iy < pl.H; iy++) { const c = f.lab[iy * pl.W + ix]; if (c !== prev) { if (prev >= 0) run += env.className(prev) + ':' + (cnt * pl.px).toFixed(1) + ' '; prev = c; cnt = 0; } cnt++; } console.error('centre line classes (mm):', run); const out = Buffer.alloc(pl.W * pl.H); for (let k = 0; k < out.length; k++) out[k] = f.lab[k] === AIR ? 0 : Math.min(255, 40 + f.lab[k] * 6); fs.writeFileSync(process.env.Q246_LAB_PGM || '/tmp/lab.pgm', Buffer.concat([Buffer.from('P5\n' + pl.W + ' ' + pl.H + '\n255\n'), out])); } } process.exit(0); }
const R = {itool: ITOOL, utool: UTOOL, newSpeckle: NEW, scenes: {}};
const want = (arg('scenes', 'thigh,abdomen') + '').split(',');
for (const sc of want) {
  const scene = SCENES[sc](), out = R.scenes[sc] = {probe: scene.probe, freq: scene.freq, depth_cm: scene.depthCm};
  // ---- star: tilt 0..20 deg, 1 deg steps, in-plane rocking (dir 0) and fanning (dir 90)
  const nT = QUICK ? 8 : 21;
  for (const dir of [0, 90]) {
    const S = makeS(scene, {mode: 'star'}), fr = [];
    for (let t = 0; t < nT; t++) fr.push(frame(S, {id: t, tilt: t, dir, off: 0}));
    const nc = [], tx = [], mad1 = [], mad4 = [], lc = [];
    for (let i = 0; i + 1 < fr.length; i++) { nc.push(nccDb(fr[i], fr[i + 1])); tx.push(texNcc(fr[i], fr[i + 1])); mad1.push(madDb(fr[i], fr[i + 1])); lc.push(labChangeFrac(fr[i], fr[i + 1])); }
    for (let i = 0; i + 4 < fr.length; i++) mad4.push(madDb(fr[i], fr[i + 4]));
    out['star_dir' + dir] = {signal_frac: H.mean(fr.map(f => f.db.reduce((a, v) => a + (v > -150 ? 1 : 0), 0) / fanPixels(S, f))), signal_frac_min: Math.min(...fr.map(f => f.db.reduce((a, v) => a + (v > -150 ? 1 : 0), 0) / fanPixels(S, f))), frames: fr.length, ncc_1deg: H.mean(nc.filter(isFinite)), ncc_1deg_min: Math.min(...nc.filter(isFinite)), texture_ncc_1deg: H.mean(tx.filter(isFinite)), mad_1deg: H.mean(mad1), mad_4deg: H.mean(mad4), label_change_1deg: H.mean(lc), depth_roughness_db: H.mean(fr.map(depthRoughness).filter(isFinite)),
      ms_per_frame: H.mean(fr.map(f => f.kernel_ms + f.sim_ms)), kernel_ms: H.mean(fr.map(f => f.kernel_ms)), sim_ms: H.mean(fr.map(f => f.sim_ms))};
    if (PGM) { savePgm(fr[0], `us_${sc}_star${dir}_t0`); savePgm(fr[Math.min(1, fr.length - 1)], `us_${sc}_star${dir}_t1`); savePgm(fr[Math.min(2, fr.length - 1)], `us_${sc}_star${dir}_t2`); }
  }
  // ---- sweeps: n frames, spacing mm
  const sweeps = QUICK ? [[5, 10]] : [[9, 3], [9, 5], [6, 10], [5, 10], [3, 25], [3, 50]];
  out.sweeps = {};
  for (const [n, sp] of sweeps) {
    const S = makeS(scene, {mode: 'sweep', maxDim: n <= 4 ? 440 : n <= 6 ? 380 : 320}), fr = [], offs = U.sweepOffsets(n, sp, true, 1);
    offs.forEach((o, i) => fr.push(frame(S, {id: i, tilt: 0, dir: 0, off: o})));
    const nc = [], tx = [], lc = [], mad = [];
    for (let i = 0; i + 1 < fr.length; i++) { nc.push(nccDb(fr[i], fr[i + 1])); tx.push(texNcc(fr[i], fr[i + 1])); lc.push(labChangeFrac(fr[i], fr[i + 1])); mad.push(madDb(fr[i], fr[i + 1])); }
    const pe = []; for (let i = 0; i < fr.length; i++) { const d = fr[i].pose.O.map((x, a) => x - S.P[a]), e = fr[i].pose.pf.e; pe.push(d[0] * e[0] + d[1] * e[1] + d[2] * e[2]); }
    const steps = pe.slice(1).map((x, i) => x - pe[i]);
    out.sweeps[`n${n}_sp${sp}`] = {signal_frac: H.mean(fr.map(f => f.db.reduce((a, v) => a + (v > -150 ? 1 : 0), 0) / fanPixels(S, f))), ncc_adjacent: H.mean(nc.filter(isFinite)), ncc_min: Math.min(...nc.filter(isFinite)), texture_ncc_adjacent: H.mean(tx.filter(isFinite)), mad_adjacent: H.mean(mad), label_change_adjacent: H.mean(lc), plane_step_mm_mean: H.mean(steps), plane_step_mm_sd: H.std(steps),
      reseat_shift_mm_range: [Math.min(...fr.map(f => f.pose.shift)), Math.max(...fr.map(f => f.pose.shift))], ms_per_frame: H.mean(fr.map(f => f.kernel_ms + f.sim_ms)), frames: n};
    if (PGM && sp === 3 && n === 9) fr.forEach((f, i) => { if (i < 4) savePgm(f, `us_${sc}_sweep_n9_sp3_${i}`); });
  }
  // ---- speckle in a HOMOGENEOUS liver block (anatomy removed): does the grain belong to the body?
  {
    const sp = out.speckle = {};
    const S = makeS(scene, {mode: 'star'}), ph = U.probeFrame(S.N, U.REF[S.refKey], 0, 0, 0);
    const A = frame(S, {id: 0, tilt: 0, dir: 0, off: 0}, true), P2 = S.P.map((x, a) => x + ph.u[a] * 2.5), B = frame(Object.assign({}, S, {P: P2}), {id: 0, tilt: 0, dir: 0, off: 0}, true);
    const px = A.plan.px, sh = Math.round(2.5 / px), mk = inFan(A), mk2 = inFan(B), a = new Float32Array(A.gray.length), b = new Float32Array(A.gray.length), m = new Uint8Array(mk.length), m0 = new Uint8Array(mk.length);
    for (let y = 0; y < A.H; y++) for (let x = 0; x < A.W - sh; x++) { const k = y * A.W + x; a[k] = A.gray[y * A.W + x + sh]; b[k] = B.gray[k]; m[k] = mk[y * A.W + x + sh] & mk2[k]; m0[k] = mk[k] & mk2[k]; }
    sp.pan_2p5mm_ncc_moves_with_tissue = H.ncc(a, b, m); sp.pan_2p5mm_ncc_stuck_to_screen = H.ncc(A.gray, B.gray, m0);   // NB: the tool places the probe in discrete clicks; the lattice origin is the contact point of the placement
    const st = [], sd = [];
    const fr0 = [], fr90 = []; for (let t = 0; t < 6; t++) { fr0.push(frame(Object.assign({}, S, {mode: 'star'}), {id: t, tilt: t, dir: 0, off: 0}, true)); fr90.push(frame(Object.assign({}, S, {mode: 'star'}), {id: t, tilt: t, dir: 90, off: 0}, true)); }
    sp.star_rock_ncc_1deg = H.mean(fr0.slice(1).map((f, i) => nccDb(fr0[i], f))); sp.star_fan_ncc_1deg = H.mean(fr90.slice(1).map((f, i) => nccDb(fr90[i], f))); sp.star_fan_ncc_5deg = nccDb(fr90[0], fr90[5]);
    { // synthetic system noise on/off: its component (dB difference) between neighbouring tilts
      const Sn = makeS(scene, {mode: 'star', noise: true}), comp = (t) => { const a1 = frame(Sn, {id: t, tilt: t, dir: 90, off: 0}, true), a0 = frame(Object.assign({}, Sn, {noise: false}), {id: t, tilt: t, dir: 90, off: 0}, true), z = new Float32Array(a1.db.length), mk = inFan(a1); for (let k = 0; k < z.length; k++) z[k] = mk[k] ? Math.pow(10, a1.db[k] / 10) - Math.pow(10, a0.db[k] / 10) : 0; return {z, mk}; };
      const n0 = comp(0), n1 = comp(1), n5 = comp(5), mm = n0.mk.map((x, k) => x & n1.mk[k]); sp.system_noise_ncc_1deg_fan = H.ncc(n0.z, n1.z, mm); sp.system_noise_ncc_5deg_fan = H.ncc(n0.z, n5.z, n0.mk.map((x, k) => x & n5.mk[k]));
    }
    const Ssw = makeS(scene, {mode: 'sweep'}); sp.sweep_ncc_by_spacing_mm = {};
    [1, 3, 5, 10, 25].forEach(d => { const f0 = frame(Ssw, {id: 0, tilt: 0, dir: 0, off: 0}, true), f1 = frame(Ssw, {id: 1, tilt: 0, dir: 0, off: d}, true); sp.sweep_ncc_by_spacing_mm[d] = nccDb(f0, f1); });
    // gain stays the same in every frame: mean dB of a homogeneous block at the same depth across the star
    const mdb = f => { let s2 = 0, n = 0; for (let y = Math.floor(f.H * 0.4); y < Math.floor(f.H * 0.6); y++) for (let x = Math.floor(f.W * 0.4); x < Math.floor(f.W * 0.6); x++) { const v = f.db[y * f.W + x]; if (v > -150) { s2 += v; n++; } } return n ? s2 / n : NaN; };
    sp.mean_db_sd_across_star = H.std(fr90.map(mdb)); 
    if (PGM) { savePgm(A, `us_${sc}_spk_a`); savePgm(B, `us_${sc}_spk_b`); savePgm(fr90[0], `us_${sc}_spk_t0`); savePgm(fr90[1], `us_${sc}_spk_t1`); }
  }
  console.error('scene done', sc);
}
fs.writeFileSync(OUT, JSON.stringify(R, null, 1)); console.error('written', OUT);
