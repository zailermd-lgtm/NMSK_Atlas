// Q377: run the engine's load-time skin weld (scripts/anatomy/q334/seams_weld_q334.js, unchanged) on exported skin meshes, outside a browser.
//   node weld_roots_q377.js <prefix> <weld js> <out.json>
// <prefix>.json: [{id, vc, ic, po, io}] and <prefix>.bin: float32 positions / uint16 triangles (written by skin_q377.export_skin).
// out.json: per piece {r: weld root of every vertex (global index), s: 1 where the root is a seam vertex (welded, rim-joined or attached to a
// neighbour's border edge)}, and the engine's own counters.
'use strict';
const fs = require('fs');
const [pre, weldPath, outPath] = process.argv.slice(2);
const H = JSON.parse(fs.readFileSync(pre + '.json')), B = fs.readFileSync(pre + '.bin');
const buf = B.buffer.slice(B.byteOffset, B.byteOffset + B.length);
global.window = {}; global.OBJ = [];
H.forEach(function (h) {
  const pos = new Float32Array(buf.slice(h.po, h.po + h.vc * 12)), idx = new Uint16Array(buf.slice(h.io, h.io + h.ic * 6));
  const nrm = new Float32Array(h.vc * 3);      // the page's own vertex normals: area weighted over the piece's faces
  for (let t = 0; t < h.ic; t++) {
    const a = idx[3 * t], b = idx[3 * t + 1], c = idx[3 * t + 2];
    const e1x = pos[b * 3] - pos[a * 3], e1y = pos[b * 3 + 1] - pos[a * 3 + 1], e1z = pos[b * 3 + 2] - pos[a * 3 + 2];
    const e2x = pos[c * 3] - pos[a * 3], e2y = pos[c * 3 + 1] - pos[a * 3 + 1], e2z = pos[c * 3 + 2] - pos[a * 3 + 2];
    const nx = e1y * e2z - e1z * e2y, ny = e1z * e2x - e1x * e2z, nz = e1x * e2y - e1y * e2x;
    for (const v of [a, b, c]) { nrm[v * 3] += nx; nrm[v * 3 + 1] += ny; nrm[v * 3 + 2] += nz; }
  }
  for (let q = 0; q < h.vc; q++) { const L = Math.hypot(nrm[q * 3], nrm[q * 3 + 1], nrm[q * 3 + 2]) || 1; nrm[q * 3] /= L; nrm[q * 3 + 1] /= L; nrm[q * 3 + 2] /= L; }
  OBJ.push({name: h.name || h.id, id: h.id, layer: 'skin', pos, nrm, idx, vc: h.vc});
});
let out = null;
let src = fs.readFileSync(weldPath, 'utf8');
const hook = '        var st = q334Stat.cls[cls]';
if (src.indexOf(hook) < 0) throw new Error('weld source changed: hook line not found');
src = src.replace(hook, '        if (window.__q377) window.__q377({R:R, seam:seam, L:L, base:base});\n' + hook);
window.__q377 = function (D) {
  const o = {};
  D.L.forEach(function (p, mi) { const b = D.base[mi]; o[p.id] = {r: Array.from(D.R.subarray(b, b + p.vc)), s: Array.from(D.R.subarray(b, b + p.vc), r => D.seam[r])}; });
  out = o;
};
global.poseRestOfZ = function () {};
eval(src + '\n;global.q334Stat = q334Stat;');
fs.writeFileSync(outPath, JSON.stringify({pieces: out, stat: global.q334Stat.cls.skin}));
