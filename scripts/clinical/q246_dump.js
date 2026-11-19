'use strict';
/* Q246: render ONE image of the harness (node) to a PGM for screenshots.
 * node q246_dump.js --tool T.js --geo DIR --site thigh|pelvis|knee|shoulder --dir ax|co|sa --pos 0 --kind ct|t1_se|t2_se|pd_se [--thick 0] [--slab avg|mip|min] [--ss N] [--noise X] [--fov mm] [--cx dx --cz dz] --out f.pgm */
const fs = require('fs'), path = require('path'), H = require('./q246_lib.js');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i < 0 ? d : process.argv[i + 1]; };
const env = H.makeEnv(arg('tool'), arg('geo'), path.resolve(__dirname, '../../clinical/data/imaging_tissues.json')), g = env.geo, L = env.L;
function bb(id) { const i = g.ids.indexOf(id); return [[g.bbox[6 * i], g.bbox[6 * i + 1], g.bbox[6 * i + 2]], [g.bbox[6 * i + 3], g.bbox[6 * i + 4], g.bbox[6 * i + 5]]]; }
const mid = (b, a) => (b[0][a] + b[1][a]) / 2, fem = bb('femur_r'), pat = bb('patella_r'), hip = bb('hip_bone_r'), hum = bb('humerus_r');
const SITES = {thigh: {O: [mid(fem, 0), fem[0][1] + 0.5 * (fem[1][1] - fem[0][1]), mid(fem, 2)], fov: {ax: 300, co: 500, sa: 500}}, knee: {O: [mid(pat, 0), mid(pat, 1) - 10, mid(pat, 2) - 15], fov: {ax: 250, co: 400, sa: 400}},
  pelvis: {O: [0, hip[0][1] + 0.55 * (hip[1][1] - hip[0][1]), mid(hip, 2)], fov: {ax: 450, co: 600, sa: 600}}, shoulder: {O: [mid(hum, 0), hum[1][1] - 25, mid(hum, 2)], fov: {ax: 400, co: 400, sa: 400}}};
const AX = {ax: [0, -1, 0], co: [0, 0, 1], sa: [-1, 0, 0]};
const S = SITES[arg('site', 'thigh')], dir = arg('dir', 'ax'), n = AX[dir], pos = +arg('pos', 0), th = +arg('thick', 0), kind = arg('kind', 'ct'), W = +arg('W', 320), ss = +arg('ss', env.SS);
const fov = +arg('fov', S.fov[dir]), b = L.basis(n);
const cen = [S.O[0] + b.u[0] * +arg('cx', 0) + b.v[0] * +arg('cy', 0), S.O[1] + b.u[1] * +arg('cx', 0) + b.v[1] * +arg('cy', 0), S.O[2] + b.u[2] * +arg('cx', 0) + b.v[2] * +arg('cy', 0)];
const offs = L.slabOffsets ? L.slabOffsets(-th / 2, th / 2, th, 25) : (th <= 0.01 ? [0] : Array.from({length: Math.max(2, Math.min(25, Math.ceil(th) + 1))}, (_, k, a) => -th / 2 + th * k / (a.length - 1)));
const O = [S.O[0] + n[0] * pos, S.O[1] + n[1] * pos, S.O[2] + n[2] * pos];
const res = H.runSlices(env, {n, O, center: cen, W, fov, offsets: offs, ss});
const o = kind === 'ct' ? {modality: 'ct', L: +arg('L', 40), Wd: +arg('Wd', 400)} : {modality: 'mr', seq: kind};
Object.assign(o, {thick: th, slab: arg('slab', 'avg'), noise: +arg('noise', 0)});
const val = H.values(env, res, o), gray = H.toGray(val, o);
fs.writeFileSync(arg('out'), Buffer.concat([Buffer.from('P5\n' + res.W + ' ' + res.H + '\n255\n'), Buffer.from(gray)]));
console.error('ms', res.ms.toFixed(1), 'holes', res.holes || 0, 'parityBad', res.parityBad);
