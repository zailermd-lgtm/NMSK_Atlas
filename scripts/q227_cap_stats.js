#!/usr/bin/env node
/* Q227: leak statistics of the cut-face fill (viewer/cut_cap/cut_cap.js, the code the pages run) on the REAL meshes of one built viewer page.
 *
 *   node scripts/q227_cap_stats.js PAGE.html own|zan PAGE_NAME OUT.json [--quick]
 *
 * Decodes the page's own geometry (own: bundle-json + the base64 geo files, Z: manifest + the base64 geo files), shows EVERY structure (worst case: nothing
 * hidden), and cuts it with a set of planes: axial planes through the femoral shaft, the thigh, the forearm and the thorax (landmarks from the page's own
 * femur_r / radius_r / sternum), the median sagittal plane and a coronal plane through the middle. Per plane: structures cut, filled, outline-only (failed the
 * parity sanity test), rows with an odd number of crossings (= leaks) before / after the gap closing and the row repair, open contour ends before / after the
 * 1 mm gap closing, build time. Totals + per-category numbers go into OUT.json (data/derived/Q227_cap_stats_<page>.json). */
"use strict";
const fs = require("fs"), path = require("path");
const [html, kind, pageName, outPath] = process.argv.slice(2, 6);
const quick = process.argv.includes("--quick");
const src = fs.readFileSync(path.join(__dirname, "..", "viewer", "cut_cap", "cut_cap.js"), "utf8");
const C = new Function(src + ";return NMSKCapCore;")();
const dir = path.dirname(html), text = fs.readFileSync(html, "utf8");

function b64file(f){ return fs.readFileSync(path.join(dir, f), "utf8").trim(); }
const items = [];
if (kind === "own"){
  const i = text.indexOf('id="bundle-json" type="application/json">') + 'id="bundle-json" type="application/json">'.length;
  const B = JSON.parse(text.slice(i, text.indexOf("</script>", i)));
  const m = /var BIN_FILES = (\[.*?\]);/s.exec(text);
  const files = JSON.parse(m[1]);
  let b64 = "";
  if (files.length) files.forEach(f => { b64 += b64file(f.path); });
  else { const j = text.indexOf('id="bundle-b64" type="text/plain">') + 'id="bundle-b64" type="text/plain">'.length; b64 = text.slice(j, text.indexOf("</script>", j)).trim(); }
  const buf = Buffer.from(b64, "base64"), ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length);
  let off = 0; const q = B.quantum_mm;
  B.structures.forEach(s => {
    const pos16 = new Int16Array(ab, off, s.nv * 3); off += s.nv * 6;
    const idx = new Uint16Array(ab, off, s.nf * 3); off += s.nf * 6;
    const pos = new Float32Array(s.nv * 3); for (let k = 0; k < pos.length; k++) pos[k] = pos16[k] * q;
    const mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
    for (let v = 0; v < pos.length; v += 3) for (let k = 0; k < 3; k++){ if (pos[v+k] < mn[k]) mn[k] = pos[v+k]; if (pos[v+k] > mx[k]) mx[k] = pos[v+k]; }
    items.push({key: s.id, name: s.id, cat: s.cat, rgb: [0.6, 0.3, 0.3], alpha: 1, geom: () => ({pos, idx, bmin: mn, bmax: mx})});
  });
} else {
  const grab = (name) => { const a = text.indexOf(name + "="); const b = text.indexOf("\n", a); return text.slice(a + name.length + 1, b).replace(/;\s*$/, ""); };
  const MAN = JSON.parse(grab("window.__ANATOMY_MANIFEST__"));
  const files = JSON.parse(grab("window.__ANATOMY_BIN_FILES__"));
  const parts = files.map(f => f.enc === "base64" ? Buffer.from(b64file(f.path), "base64") : fs.readFileSync(path.join(dir, f.path)));
  const BIN = Buffer.concat(parts), ab = BIN.buffer.slice(BIN.byteOffset, BIN.byteOffset + BIN.length);
  MAN.meshes.forEach(r => {
    const qv = new Uint16Array(ab, r.vo, r.vc * 3), pos = new Float32Array(r.vc * 3), mn = r.min, sp = r.span;
    const lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
    for (let v = 0; v < r.vc * 3; v += 3) for (let k = 0; k < 3; k++){ const x = mn[k] + qv[v+k] / 65535 * sp[k]; pos[v+k] = x; if (x < lo[k]) lo[k] = x; if (x > hi[k]) hi[k] = x; }
    const idx = new Uint16Array(ab, r.io, r.ic * 3);
    items.push({key: r.id, name: r.id, cat: r.sys || "bone", rgb: [0.6, 0.3, 0.3], alpha: 1, geom: () => ({pos, idx, bmin: lo, bmax: hi})});
  });
}
const by = {}; items.forEach(it => { by[it.key] = it; });
function centre(id){ const it = by[id]; if (!it) return null; const g = it.geom(); return [0, 1, 2].map(k => (g.bmin[k] + g.bmax[k]) / 2).concat([g.bmin[1], g.bmax[1]]); }
const all = items.map(it => it.geom()), bb = [[1e9, 1e9, 1e9], [-1e9, -1e9, -1e9]];
all.forEach(g => { for (let k = 0; k < 3; k++){ bb[0][k] = Math.min(bb[0][k], g.bmin[k]); bb[1][k] = Math.max(bb[1][k], g.bmax[k]); } });
const fem = centre("femur_r"), rad = centre("radius_r"), ste = centre("sternum");
const planes = [];
if (fem){ planes.push(["femoral_shaft_axial", [0, 1, 0], fem[1]]); planes.push(["thigh_axial", [0, 1, 0], fem[4] - 0.3 * (fem[4] - fem[3])]); }
if (rad) planes.push(["forearm_axial", [0, 1, 0], rad[1]]);
if (ste) planes.push(["thorax_axial", [0, 1, 0], ste[1]]);
planes.push(["median_sagittal", [1, 0, 0], (bb[0][0] + bb[1][0]) / 2]);
planes.push(["coronal_mid", [0, 0, 1], (bb[0][2] + bb[1][2]) / 2]);
if (!quick){
  [0.1, 0.2, 0.5, 0.8, 0.9].forEach(f => planes.push(["axial_" + Math.round(f * 100) + "pct", [0, 1, 0], bb[0][1] + f * (bb[1][1] - bb[0][1])]));
  [-60, 60].forEach(d => planes.push(["sagittal_" + d, [1, 0, 0], (bb[0][0] + bb[1][0]) / 2 + d]));
}
if (process.env.Q227_PLANE_Y){ planes.length = 0; planes.push(["debug_axial", [0, 1, 0], +process.env.Q227_PLANE_Y]); }     // debugging: one axial plane
const out = {page: pageName, kind, structures_in_page: items.length, planes: [], totals: {}, by_cat: {}, worst_outline_only: {}, params: {gap_mm: 1.0, min_px_mm: 0.4, max_dim: 2048, max_odd_row_fraction: 0.12, max_odd_run_rows: 30}};
const tot = {planes: planes.length, structures_cut: 0, filled: 0, outline_only: 0, thin: 0, rows: 0, odd_rows_after_closing: 0, odd_rows_in_filled: 0, odd_rows_in_outline_only: 0, rows_in_filled: 0, filled_with_repair: 0, rows_repaired: 0, open_ends_before: 0, open_ends_after: 0, joined_pairs: 0, duplicate_segments: 0, ms_sum: 0, ms_max: 0};
planes.forEach(([name, n, d]) => {
  const r = C.build(items, {n, d});
  const s = r.stats;
  out.planes.push({name, normal: n, offset_mm: +d.toFixed(2), raster: [r.w, r.h], px_mm: +r.px.toFixed(3), structures_cut: s.structures_cut, filled: s.filled, outline_only: s.outline_only, thin: s.thin,
    rows: s.rows, odd_rows: s.odd_rows, odd_rows_in_filled: s.odd_rows_in_filled, odd_rows_in_outline_only: s.odd_rows_in_outline_only, rows_in_filled: s.rows_in_filled, filled_with_repair: s.filled_with_repair, odd_row_fraction: s.odd_row_fraction, rows_repaired: s.repaired_rows, open_ends_before: s.open_ends_before, open_ends_after: s.open_ends_after,
    joined_pairs: s.joined, segments: s.segments, ms: r.ms});
  tot.structures_cut += s.structures_cut; tot.filled += s.filled; tot.outline_only += s.outline_only; tot.thin += s.thin; tot.rows += s.rows; tot.odd_rows_after_closing += s.odd_rows; tot.odd_rows_in_filled += s.odd_rows_in_filled; tot.odd_rows_in_outline_only += s.odd_rows_in_outline_only; tot.rows_in_filled += s.rows_in_filled; tot.filled_with_repair += s.filled_with_repair;
  tot.rows_repaired += s.repaired_rows; tot.open_ends_before += s.open_ends_before; tot.open_ends_after += s.open_ends_after; tot.joined_pairs += s.joined; tot.duplicate_segments += s.duplicate_segments;
  tot.ms_sum += r.ms; tot.ms_max = Math.max(tot.ms_max, r.ms);
  Object.keys(s.by_cat).forEach(c => {
    const t = out.by_cat[c] || (out.by_cat[c] = {cut: 0, filled: 0, outline_only: 0, thin: 0, rows: 0, odd_rows: 0}), v = s.by_cat[c];
    ["cut", "filled", "outline_only", "thin", "rows", "odd_rows"].forEach(k => { t[k] += v[k]; });
  });
  (r._cut || []).forEach(c => { if (c.status === "outline"){ const k = c.it.key; out.worst_outline_only[k] = (out.worst_outline_only[k] || 0) + 1; } });
  process.stderr.write(`${pageName} ${name}: cut ${s.structures_cut} filled ${s.filled} outline ${s.outline_only} odd ${s.odd_rows}/${s.rows} ${r.ms} ms\n`);
});
tot.odd_row_fraction = tot.rows ? +(tot.odd_rows_after_closing / tot.rows).toFixed(5) : 0;
tot.odd_row_fraction_in_filled = tot.rows_in_filled ? +(tot.odd_rows_in_filled / tot.rows_in_filled).toFixed(5) : 0;
tot.outline_only_fraction = tot.structures_cut ? +(tot.outline_only / tot.structures_cut).toFixed(4) : 0;
tot.ms_mean = +(tot.ms_sum / planes.length).toFixed(1);
Object.values(out.by_cat).forEach(v => { v.odd_row_fraction = v.rows ? +(v.odd_rows / v.rows).toFixed(5) : 0; });
out.totals = tot;
const wo = Object.entries(out.worst_outline_only).sort((a, b) => b[1] - a[1]); out.worst_outline_only = wo.slice(0, 40).map(([k, v]) => ({id: k, planes_outline_only: v}));
fs.writeFileSync(outPath, JSON.stringify(out, null, 1));
console.log(JSON.stringify(tot));
