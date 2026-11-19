#!/usr/bin/env node
/* Q299 Part C: cross-section coverage audit of the cut-face fill (viewer/cut_cap/cut_cap.js -- the code the pages run)
 * on the REAL meshes of one built page.
 *
 *   node scripts/anatomy/q299/xsec299.js PAGE.html own|zan PAGE_KEY OUT.json [--levels N] [--only id1,id2] [--y Y] [--probe]
 *
 * For every axial level it separates two questions:
 *   SHOULD appear  = the plane actually cuts the structure (triangles straddle it -> contour segments exist)
 *   DOES appear    = cut_cap gives the structure status "filled", i.e. at least one pixel of the cut face carries its colour
 *                    ("thin"  = cut but 0 px painted -> only a 1 px outline;  "outline" = failed the parity test -> outline only)
 * Both the page's default visibility (the manifest / bundle `hd` flag) and "everything shown" are reported, because a structure
 * hidden by default is not in the cut at all. */
"use strict";
const fs = require("fs"), path = require("path");
const args = process.argv.slice(2);
const [html, kind, pageKey, outPath] = args;
function opt(n, d){ const i = args.indexOf(n); return i < 0 ? d : args[i + 1]; }
const nLevels = +opt("--levels", 30);
const only = opt("--only", "") ? opt("--only", "").split(",") : null;
const yOne = opt("--y", null);
const REPO = path.resolve(__dirname, "../../..");
const corePath = opt("--core", path.join(REPO, "viewer", "cut_cap", "cut_cap.js"));
const bandFrac = +opt("--band-frac", 0), bandMax = +opt("--band-max", 2.5);
const BOPT = bandFrac > 0 ? {bandFrac: bandFrac, bandMax: bandMax} : {};
const src = fs.readFileSync(corePath, "utf8");
const C = new Function(src + ";return NMSKCapCore;")();
const dir = path.dirname(html), text = fs.readFileSync(html, "utf8");
function b64file(f){ return fs.readFileSync(path.join(dir, f), "utf8").trim(); }

const items = [];
if (kind === "own"){
  const tag = 'id="bundle-json" type="application/json">';
  const i = text.indexOf(tag) + tag.length;
  const B = JSON.parse(text.slice(i, text.indexOf("</script>", i)));
  const files = JSON.parse(/var BIN_FILES = (\[.*?\]);/s.exec(text)[1]);
  let b64 = "";
  if (files.length) files.forEach(f => { b64 += b64file(f.path); });
  else { const t2 = 'id="bundle-b64" type="text/plain">'; const j = text.indexOf(t2) + t2.length; b64 = text.slice(j, text.indexOf("</script>", j)).trim(); }
  const buf = Buffer.from(b64, "base64"), ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length);
  let off = 0; const q = B.quantum_mm;
  B.structures.forEach(s => {
    const pos16 = new Int16Array(ab, off, s.nv * 3); off += s.nv * 6;
    const idx = new Uint16Array(ab, off, s.nf * 3); off += s.nf * 6;
    const pos = new Float32Array(s.nv * 3); for (let k = 0; k < pos.length; k++) pos[k] = pos16[k] * q;
    const mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
    for (let v = 0; v < pos.length; v += 3) for (let k = 0; k < 3; k++){ if (pos[v+k] < mn[k]) mn[k] = pos[v+k]; if (pos[v+k] > mx[k]) mx[k] = pos[v+k]; }
    items.push({key: s.id, name: s.id, cat: s.cat, hd: !!s.hd, nv: s.nv, nf: s.nf, rgb: [0.6, 0.3, 0.3], alpha: 1, geom: () => ({pos, idx, bmin: mn, bmax: mx})});
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
    items.push({key: r.id, name: r.id, cat: r.sys || "bone", hd: !!r.hd, nv: r.vc, nf: r.ic, rgb: [0.6, 0.3, 0.3], alpha: 1, geom: () => ({pos, idx, bmin: lo, bmax: hi})});
  });
}
const by = {}; items.forEach(it => { by[it.key] = it; });
function bbox(id){ const it = by[id]; if (!it) return null; const g = it.geom(); return {min: g.bmin.slice(), max: g.bmax.slice()}; }

/* ---------------- axial levels: ~N per region, from the page's own landmarks ---------------- */
const all = items.map(it => it.geom()), BB = [[1e9,1e9,1e9],[-1e9,-1e9,-1e9]];
all.forEach(g => { for (let k = 0; k < 3; k++){ BB[0][k] = Math.min(BB[0][k], g.bmin[k]); BB[1][k] = Math.max(BB[1][k], g.bmax[k]); } });
function span(ids){
  let lo = 1e9, hi = -1e9;
  ids.forEach(id => { const b = bbox(id); if (b){ lo = Math.min(lo, b.min[1]); hi = Math.max(hi, b.max[1]); } });
  return lo < hi ? [lo, hi] : null;
}
const REGIONS = {
  thigh:   span(["femur_r", "femur_l"]),
  leg:     span(["tibia_r", "tibia_l", "fibula_r", "fibula_l"]),
  arm:     span(["humerus_r", "humerus_l"]),
  forearm: span(["radius_r", "radius_l", "ulna_r", "ulna_l"]),
  thorax:  span(["sternum"]),
  abdomen: null, pelvis: span(["hip_bone_r", "hip_bone_l"]),
};
if (REGIONS.thorax && REGIONS.pelvis) REGIONS.abdomen = [REGIONS.pelvis[1], REGIONS.thorax[0]];
const levels = [];
if (yOne != null){ levels.push({region: "probe", y: +yOne}); }
else Object.keys(REGIONS).forEach(r => {
  const s = REGIONS[r]; if (!s) return;
  for (let i = 0; i < nLevels; i++){ const f = (i + 0.5) / nLevels; levels.push({region: r, y: s[0] + f * (s[1] - s[0])}); }
});

/* ---------------- run ---------------- */
const CLASSES = ["nerve", "vessel", "tendon", "ligament", "fascia", "bursa", "muscle", "bone", "skin", "fat", "viscera", "organ", "joint", "cartilage", "lymph", "cns", "insertion", "other"];
function emptyTally(){ const t = {}; CLASSES.forEach(c => { t[c] = {should: 0, filled: 0, band: 0, thin: 0, outline: 0, visible: 0, invisible: 0, hidden_by_default: 0}; }); return t; }
const STATUS = s => (s === "filled" ? "filled" : s === "band" ? "band" : s === "outline" ? "outline" : "thin");
const visibleSets = {all: items, default: items.filter(it => !it.hd)};
const out = {page: pageKey, kind, structures_in_page: items.length, hidden_by_default: items.filter(it => it.hd).length,
             regions: REGIONS, n_levels: levels.length, params: JSON.parse(JSON.stringify({gap_mm: 1.0, min_px_mm: 0.4, max_dim: 2048})),
             by_visibility: {}, levels: [], misses: []};
Object.keys(visibleSets).forEach(vis => {
  const set = visibleSets[vis], tally = emptyTally();
  const perLevel = [];
  levels.forEach(L => {
    const plane = {n: [0, 1, 0], d: L.y};
    const r = C.build(set, plane, BOPT);
    /* DOES appear = pixels of the FINAL raster that still carry this structure's code after every later structure has
     * painted over it. A status of "filled"/"band" only says the structure painted something at its own turn. */
    const seen = new Int32Array(r.items.length + 1);
    if (r.ids) for (let i = 0; i < r.ids.length; i++) seen[r.ids[i]]++;
    r.items.forEach(x => { x.visible_px = seen[x.code]; });
    const stat = {}; r.items.forEach(x => { stat[x.key] = x.status + (x.visible_px ? "" : "/0px"); });
    // SHOULD = cut by the plane (cut_cap already filters to those with segments)
    const rec = {region: L.region, y: +L.y.toFixed(1), cut: r.items.length, filled: 0, band: 0, thin: 0, outline: 0, visible: 0, invisible: 0, px_mm: +r.px.toFixed(3), band_mm: r.stats.band_mm || 0};
    r.items.forEach(x => {
      const c = CLASSES.indexOf(x.cat) >= 0 ? x.cat : "other";
      tally[c].should++; tally[c][STATUS(x.status)]++;
      tally[c][x.visible_px ? "visible" : "invisible"]++;
      rec[STATUS(x.status)]++; rec[x.visible_px ? "visible" : "invisible"]++;
      if (!x.visible_px && out.misses.length < 4000 && vis === "all")
        out.misses.push({region: L.region, y: +L.y.toFixed(1), id: x.key, cat: x.cat, status: x.status, nv: by[x.key].nv, width_mm: x.width_mm, band_mm: x.band_mm});
    });
    if (vis === "all") out.levels.push(rec); else perLevel.push(rec);
    if (only) only.forEach(id => { if (by[id]) { const b = bbox(id); if (b && b.min[1] <= L.y && L.y <= b.max[1]) console.log(`${vis} y=${L.y.toFixed(1)} ${id} -> ${stat[id] || "NOT CUT"} ${by[id].hd ? "(hidden by default)" : ""}`); } });
  });
  // hidden-by-default count per class
  items.filter(it => it.hd).forEach(it => { const c = CLASSES.indexOf(it.cat) >= 0 ? it.cat : "other"; tally[c].hidden_by_default++; });
  out.by_visibility[vis] = {visible_structures: set.length, by_class: tally,
    totals: CLASSES.reduce((a, c) => { a.should += tally[c].should; a.filled += tally[c].filled; a.band += tally[c].band; a.thin += tally[c].thin; a.outline += tally[c].outline; a.visible += tally[c].visible; a.invisible += tally[c].invisible; return a; }, {should: 0, filled: 0, band: 0, thin: 0, outline: 0, visible: 0, invisible: 0})};
  if (vis === "default") out.by_visibility.default.levels = perLevel;
});
if (outPath) fs.writeFileSync(outPath, JSON.stringify(out, null, 1));
console.log(pageKey, "levels", levels.length, JSON.stringify(out.by_visibility.all.totals), "| default", JSON.stringify(out.by_visibility.default.totals));
CLASSES.forEach(c => { const t = out.by_visibility.all.by_class[c]; if (t.should) console.log("  ", c.padEnd(10), "should", String(t.should).padStart(6), "filled", String(t.filled).padStart(6), "band", String(t.band).padStart(5), "thin", String(t.thin).padStart(5), "outline", String(t.outline).padStart(5), "| VISIBLE", String(t.visible).padStart(6), "invisible", String(t.invisible).padStart(5)); });
out.band = {frac: bandFrac, max_mm: bandMax, core: path.relative(REPO, corePath)};
if (outPath) fs.writeFileSync(outPath, JSON.stringify(out, null, 1));
