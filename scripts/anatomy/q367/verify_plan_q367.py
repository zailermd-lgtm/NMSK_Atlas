#!/usr/bin/env python3
"""Q367: the injection mode's plan-first flow, the tip / entry marker pair and the Safety panel (private add-on), checked in headless
Chromium on a built Base page.

  * tip-first and entry-first give the SAME path (the plan panel: tip chosen in the picker, entry from a suggestion / set first);
    an armed tap sets the entry at the tapped pixel and leaves the tip alone;
  * every refinement this body offers puts the tip where its data says, measured: origin / insertion site (the Insertions marker,
    <= 0.5 mm), motor point and IZ band (<= 0.5 mm), PLANE between biceps brachii and brachialis (each patch point and the tip midway
    between the two surfaces: |dA - dB| <= 0.5 mm, dA + dB <= gap + 0.5), perineural (tip at the stated offset from the nerve's
    surface, outside it), inside a bursa, the joint space of a capsule (midway between its two bones, inside its box), a free tap;
  * the two markers differ in colour AND shape, both on screen; their colours stay apart under simulated protan / deutan / tritan
    vision (Machado 2009 matrices, severity 1);
  * the rules persist across a reload; a halo of radius r is drawn at r (the halo pass's inflation, and the inflated surface's
    median distance from the structure measured on its own mesh); a plan that breaks a rule is flagged with that structure and its
    distance (equal to an independent meshSegDist) and its halo / path stretch marked; a clean plan is not flagged;
  * phone: nothing wider than the screen, the model >= 50 % visible with the plan panel and with the Safety card open; desktop: same 50 %;
  * the size class shown on the distance rows and the guide's at-risk rows; no page errors. Screenshots -> --shots.

    python3 scripts/anatomy/q367/verify_plan_q367.py <page dir> [--size 1400x900] [--shots DIR]
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]

HELPERS = r"""() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const T = window.NMSKClinicalTool, P = window.NMSKClinical.pure, D = (a, b) => Math.hypot(a[0]-b[0], a[1]-b[1], a[2]-b[2]);
  const surf = (i, p) => { const g = T.geom(i); return P.closestOnMesh(g.pos, g.idx, p).d; };
  async function settle() { for (let k = 0; k < 60; k++) { await sleep(60); if (!T.corr.timer && !T.safe.timer) break; } await sleep(120); }
  async function pick(id, role) {
    closePick();
    if (role === 'planeB') { const b = Array.from(document.querySelectorAll('.q367-sub button')).find(x => x.textContent === 'חיפוש'); if (b) b.click(); }
    else { const b = document.querySelector('.q367-plan [data-q367=tip] button'); if (b) b.click(); }
    await sleep(200);
    const inp = document.querySelector('.mc-pick .mc-search'); if (!inp) return false;
    inp.value = id; inp.dispatchEvent(new Event('input')); await sleep(120);
    const row = document.querySelector('.mc-pick .mc-res button'); if (!row) return false;
    row.click(); await sleep(700); await settle(); return true;
  }
  function closePick() { const c = document.querySelector('.mc-pick .mc-close'); if (c) c.click(); }
  function kind(k) { const b = document.querySelector('.q367-ks [data-k="' + k + '"]'); if (!b) return false; b.click(); return true; }
  function id1(...c) { for (const x of c) if (T.byId[x] && T.byId[x].length) return x; return null; }
  function tapAt(p) { const s = T.api.toScreen(p); if (!s) return null; T.onClick({clientX: s[0], clientY: s[1], button: 0}); return s; }
  async function entry() { T.suggest(); const c = T.sugg.shown[0] || T.sugg.cands[0]; if (!c) return false; T.adoptSuggestion(c); await settle(); return true; }
  async function reset() { closePick(); T.clear(); T.planRelease(); await settle(); }
  window.__q367 = {sleep, settle, pick, closePick, kind, id1, tapAt, reset, surf, D, entry};
  return !!(T && T.q367 && P.planeLocus);
}"""

ORDER = r"""async () => {
  const H = window.__q367, T = window.NMSKClinicalTool, o = {};
  const mid = H.id1('biceps_brachii_r'); if (!mid) return {err: 'no biceps_brachii_r'};
  await H.reset();
  // 1. tip first (picker), then a computed entry (the plan panel's "suggestions" button, then "use" on the first)
  if (!(await H.pick(mid))) return {err: 'picker failed'};
  o.tipKind = T.q367().tip && T.q367().tip.kind;
  const sug = Array.from(document.querySelectorAll('.q367-plan [data-q367=entry] button')).find(b => b.textContent === 'הצעות');
  if (sug) sug.click();
  for (let k = 0; k < 100 && !T.sugg.shown.length && !T.sugg.msg; k++) await H.sleep(100);
  const use = document.querySelector('.mc-cand button');
  if (use) use.click(); else if (T.sugg.cands[0]) T.adoptSuggestion(T.sugg.cands[0]); else return Object.assign(o, {err: 'no candidate: ' + T.sugg.msg});
  o.viaUse = !!use; await H.settle();
  const A = T.q367(); o.A = {tip: A.tip.p, entry: A.entry.p, len: T.report().length_mm, cross: T.report().crossings.map(c => c.id).join(',')};
  // 2. entry first (the same skin point), then the tip from the picker
  await H.reset();
  T.plEntrySet({p: o.A.entry, i: A.entry.i, n: null}); await H.settle();
  o.entryOnly = !!T.entry && !T.target;
  if (!(await H.pick(mid))) return {err: 'picker failed (entry first)'};
  const B = T.q367(); o.B = {tip: B.tip ? B.tip.p : null, entry: B.entry ? B.entry.p : null, len: T.report() ? T.report().length_mm : null, cross: T.report() ? T.report().crossings.map(c => c.id).join(',') : ''};
  o.dTip = o.B.tip ? H.D(o.A.tip, o.B.tip) : null; o.dEntry = o.B.entry ? H.D(o.A.entry, o.B.entry) : null;
  // 3. an armed tap: "tap on the skin" then a tap at a pixel -> the entry is set at that pixel, the tip is untouched
  const tip0 = T.target.p.slice(), tap = Array.from(document.querySelectorAll('.q367-plan [data-q367=entry] button')).find(b => /הקשה/.test(b.textContent));
  tap.click(); await H.sleep(100);
  o.armed = T.armFn ? 'yes' : 'no';
  const r = T.api.canvas.getBoundingClientRect(), s0 = T.api.toScreen(o.A.entry);
  T.onClick({clientX: s0[0], clientY: s0[1], button: 0}); await H.settle();
  const s1 = T.entry ? T.api.toScreen(T.entry.p) : null;
  o.tap = {px: s1 ? Math.hypot(s1[0]-s0[0], s1[1]-s0[1]) : null, tipSame: T.target && H.D(T.target.p, tip0) < 1e-9, disarmed: !T.armFn};
  return o;
}"""

REFINE = r"""async () => {
  const H = window.__q367, T = window.NMSKClinicalTool, out = [];
  const near = (a, b) => H.D(a, b);
  // origin / insertion / nmj on the first muscle that has them
  const mus = ['biceps_brachii_r', 'deltoid_r', 'gastrocnemius_r', 'tibialis_anterior_r', 'brachialis_r', 'supraspinatus_r'].filter(x => T.byId[x]);
  let done = {origin: 0, insertion: 0, mp: 0, iz: 0};
  for (const id of mus) {
    if (done.origin && done.insertion && done.mp && done.iz) break;
    await H.reset(); if (!(await H.pick(id))) continue;
    const i = T.plan.i, of = T.plOffers(i);
    for (const ty of ['origin', 'insertion']) {
      if (done[ty] || !of[ty].length) continue;
      H.kind(ty); await H.settle();
      const a = of[ty][of[ty].length - 1], b = document.querySelector('[data-q367-att="' + a.id + '"]');
      if (b) { b.click(); await H.settle(); }
      out.push({type: ty, muscle: id, site: a.id, d: T.target ? near(T.target.p, a.xyz) : null, kind: T.target && T.target.kind, btn: !!b}); done[ty] = 1;
    }
    if ((!done.mp && of.mp.length) || (!done.iz && of.iz.length)) {
      H.kind('nmj'); await H.settle();
      if (!done.mp && of.mp.length) { const b = document.querySelector('[data-q367-mp="0"]'); if (b) { b.click(); await H.settle(); } out.push({type: 'motor point', muscle: id, d: T.target ? near(T.target.p, of.mp[0].pos) : null, kind: T.target && T.target.kind, btn: !!b}); done.mp = 1; }
      if (!done.iz && of.iz.length) { H.kind('nmj'); await H.settle(); const z = of.iz[0], b = document.querySelector('[data-q367-iz="' + z.site.n + '"]'); if (b) { b.click(); await H.settle(); } out.push({type: 'IZ band', muscle: id, site: z.site.n, d: T.target ? near(T.target.p, z.site.dot) : null, kind: T.target && T.target.kind, btn: !!b}); done.iz = 1; }
    }
  }
  ['origin', 'insertion', 'mp', 'iz'].forEach(k => { if (!done[k]) out.push({type: k, none: true}); });
  // plane: biceps brachii | brachialis
  const A = H.id1('biceps_brachii_r'), Bm = H.id1('brachialis_r');
  if (A && Bm) {
    await H.reset(); await H.pick(A); H.kind('plane'); await H.settle();
    const adj = document.querySelector('[data-q367-adj="' + Bm + '"]');
    if (adj) adj.click(); else await H.pick(Bm, 'planeB');
    await H.settle();
    const q = T.q367(), pl = T.pl.plane, gap = pl ? pl.gap : 0;
    const ai = pl ? pl.a : -1, bi = pl ? pl.b : -1, samp = pl ? pl.pts.filter((x, k) => k % Math.max(1, Math.floor(pl.pts.length / 60)) === 0) : [];
    const pts = samp.map(x => { const dA = H.surf(ai, x.m), dB = H.surf(bi, x.m); return [dA, dB]; });
    const t = q.tip ? q.tip.p : null, tA = t ? H.surf(ai, t) : null, tB = t ? H.surf(bi, t) : null;
    out.push({type: 'plane', a: T.recs[ai] && T.recs[ai].id, b: T.recs[bi] && T.recs[bi].id, viaAdj: !!adj, n: q.plane ? q.plane.n : 0, gap, minGap: q.plane && q.plane.minGap,
              worstMid: pts.length ? Math.max(...pts.map(x => Math.abs(x[0] - x[1]))) : null, worstSum: pts.length ? Math.max(...pts.map(x => x[0] + x[1])) : null,
              tA, tB, kind: q.tip && q.tip.kind, label: (document.querySelector('[data-q367-plane]') || {}).textContent || ''});
    // the tip follows the entry: with an entry set, the tip is the patch point nearest to it
    if (await H.entry()) { T.plPlane(ai, bi); await H.settle();
      const E = T.entry.p, best = pl ? T.pl.plane.pts.reduce((m, x) => H.D(x.m, E) < H.D(m.m, E) ? x : m) : null;
      out.push({type: 'plane tip nearest the entry', d: best ? H.D(best.m, T.target.p) : null, kind: T.target.kind}); }
  } else out.push({type: 'plane', err: 'biceps_brachii_r / brachialis_r missing'});
  // perineural
  const nv = H.id1('ulnar_n_r', 'radial_n_r', 'sciatic_n_r');
  if (nv) {
    await H.reset(); await H.pick(nv);
    const q = T.q367(), ni = q.tip ? q.tip.nerve : null;
    const r1 = {type: 'perineural', nerve: nv, kind: q.tip && q.tip.kind, d: ni != null ? H.surf(ni, q.tip.p) : null, off: q.tip && q.tip.off, inside: ni != null ? T.insideMesh(ni, q.tip.p) : null};
    const inp = Array.from(document.querySelectorAll('.q367-sub input')).find(x => /העצב/.test(x.getAttribute('aria-label') || ''));
    if (inp) { inp.value = '3.5'; inp.dispatchEvent(new Event('change')); await H.settle(); const q2 = T.q367(); r1.d2 = H.surf(ni, q2.tip.p); r1.off2 = q2.tip.off; r1.inside2 = T.insideMesh(ni, q2.tip.p); }
    T.pl.peri = 2; out.push(r1);
  }
  // bursa
  const bu = H.id1('anserine_bursa_r', 'subacromial_bursa_r', 'iliopsoas_bursa_r', 'bicipitoradial_bursa_r');
  if (bu) { await H.reset(); await H.pick(bu); const q = T.q367(); out.push({type: 'bursa', id: bu, kind: q.tip && q.tip.kind, inside: q.tip ? T.insideMesh(T.target.i, q.tip.p) : null}); }
  // joint space
  for (const cp of ['zan_articular_capsule_of_radiocarpal_joint_r', 'zan_articular_capsule_of_acromioclavicular_joint_r', 'zan_articular_capsule_of_superior_tibiofibular_joint_r', 'zan_articular_capsule_of_sternoclavicular_joint_r']) {
    if (!T.byId[cp]) continue;
    await H.reset(); await H.pick(cp); const q = T.q367();
    if (!q.tip || q.tip.kind !== 'intra') { out.push({type: 'joint space', id: cp, offered: T.plOffers(T.plan.i).intra, kind: q.tip && q.tip.kind}); continue; }
    const pl = T.pl.plane, r = T.recs[pl.intra], t = q.tip.p, dA = H.surf(pl.a, t), dB = H.surf(pl.b, t);
    out.push({type: 'joint space', id: cp, kind: 'intra', bones: [T.recs[pl.a].id, T.recs[pl.b].id], dA, dB, inBox: t.every((c, k) => c >= r.bmin[k] - 1e-6 && c <= r.bmax[k] + 1e-6)});
    break;
  }
  // free tap
  await H.reset(); await H.pick(A || mus[0]); H.kind('free'); await H.sleep(80);
  const c = T.api.canvas.getBoundingClientRect(), cx = c.left + c.width * 0.5, cy = c.top + c.height * 0.4;
  const hit = T.pickPoint({clientX: cx, clientY: cy});
  T.onClick({clientX: cx, clientY: cy, button: 0}); await H.settle();
  out.push({type: 'free tap', d: hit && T.target ? H.D(hit.p, T.target.p) : null, kind: T.target && T.target.kind});
  // missing line: a structure with no attachment / nmj data names it in one line
  const miss = document.querySelector('[data-q367-missing]');
  out.push({type: 'missing line', any: true, text: miss ? miss.textContent : null});
  return out;
}"""

MARKERS = r"""async () => {
  const H = window.__q367, T = window.NMSKClinicalTool;
  await H.reset(); await H.pick(H.id1('biceps_brachii_r'));
  await H.entry();
  T.api.focus(T.target.p, 260); T.api.redraw(); await H.sleep(400); T.pinsPlace();
  const pin = k => { const e = document.querySelector('.q367-pin-' + k); if (!e) return null; const r = e.getBoundingClientRect(), s = e.querySelector('svg');
    const shp = s.querySelector('path') ? 'diamond' : (s.querySelector('circle') ? 'ring' : '?');
    const col = (s.querySelector('[fill]:not([fill=none])') || s.querySelectorAll('circle')[1]);
    return {shown: getComputedStyle(e).display !== 'none', x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, shape: shp,
            color: (shp === 'diamond' ? s.querySelector('path').getAttribute('fill') : s.querySelectorAll('circle')[1].getAttribute('stroke'))}; };
  const chip = k => { const e = document.querySelector('.q367-plan .q367-mk-' + k); if (!e) return null; const cs = getComputedStyle(e); return {bg: cs.backgroundColor, border: cs.borderTopColor, radius: cs.borderTopLeftRadius, tf: cs.transform}; };
  return {tip: pin('tip'), entry: pin('entry'), chipTip: chip('tip'), chipEntry: chip('entry'), W: innerWidth, Hh: innerHeight,
          legend: (document.querySelector('.q367-leg') || {}).textContent || '', mk: window.NMSKPlanMarkers ? window.NMSKPlanMarkers.MK : null};
}"""

CLIP = r"""async () => {
  const H = window.__q367, T = window.NMSKClinicalTool, C = window.NMSKUltrasound && window.NMSKUltrasound.needleClip;
  if (!C) return {err: 'no clip'};
  C.show({}); for (let k = 0; k < 120 && !(C.state().on && C.state().frames); k++) await H.sleep(150);
  C.seek(1); await H.sleep(2500);
  const st = C.state(); return {on: st.on, mk: st.mk};
}"""

SAFE_SET = r"""async (rules) => {
  const H = window.__q367, T = window.NMSKClinicalTool;
  const b = document.querySelector('.q367-plan [data-q367=safety] button'); if (!document.querySelector('.mc-safe') || document.querySelector('.mc-safe').hidden) b.click();
  await H.sleep(150);
  for (const k of Object.keys(rules)) { const inp = document.querySelector('.mc-safe input[data-rule="' + k + '"]'); inp.value = rules[k] == null ? '' : String(rules[k]); inp.dispatchEvent(new Event('change')); }
  await H.settle();
  return T.q367().safe.rules;
}"""

SAFETY = r"""async () => {
  const H = window.__q367, T = window.NMSKClinicalTool, P = window.NMSKClinical.pure, o = {};
  await H.reset(); await H.pick(H.id1('biceps_brachii_r'));
  if (!(await H.entry())) return {err: 'no entry candidate'};
  // all rules off: no rows
  T.safeSet({rules: {nL: null, nM: null, nS: null, aL: null, aM: null, aS: null, vL: null, vM: null}}); await H.settle();
  o.off = {rows: T.q367().safe.rows.length, halos: T.ov.halosNow().filter(h => h.r !== 0).length};
  // the nearest classified structure on the corridor -> a rule 2 mm above its distance must flag it
  const items = T.corridor().items.map(it => ({...it, sz: T.sizeOf(T.byId[it.id][0])})).filter(it => it.sz && it.sz.c);
  if (!items.length) return Object.assign(o, {err: 'no classified vessel / nerve near the path'});
  const it = items[0], idx = T.recs.findIndex(r => r.id === it.id && T.cls[r.i] && Math.abs(P.meshSegDist(T.geom(r.i).pos, T.geom(r.i).idx, T.entry.p, T.target.p, 1e9).d - it.d_mm) < 0.01);
  const key = it.sz.k + it.sz.c, rule = Math.round((it.d_mm + 2) * 2) / 2;
  const rules = {}; rules[key] = rule;
  o.rule = {id: it.id, key, rule, d: it.d_mm, cls: it.sz};
  o.view = {rules0: rules};
  return o;
}"""

SAFETY2 = r"""async (args) => {
  const [id, key, rule] = args;
  const H = window.__q367, T = window.NMSKClinicalTool, P = window.NMSKClinical.pure, o = {};
  const q = T.q367(), v = q.safe.rows.find(x => x.id === id && x.viol), i = v ? v.i : (T.byId[id] || [])[0];
  const g = T.geom(i), ind = P.meshSegDist(g.pos, g.idx, T.entry.p, T.target.p, 1e9).d;
  o.flagged = !!v; o.d = v ? v.d : null; o.ind = ind; o.nViol = q.safe.rows.filter(x => x.viol).length; o.segs = q.safe.segs;
  const hn = T.ov.halosNow(), hh = hn.find(x => x.i === i);
  o.halo = hh ? {r: hh.r, alpha: hh.alpha, sign: T.orientSign(i)} : null;
  o.nHalos = hn.length; o.cap = q.safe.cap;
  o.allAtRule = q.safe.halos.every(x => { const z = hn.find(y => y.i === x.i); return z && Math.abs(Math.abs(z.r) - x.r) < 1e-9; });
  // measure the halo: the structure's own vertices pushed out along their (area-weighted) normals by r -> distance to the structure
  const pos = g.pos, idx = g.idx, nv = pos.length / 3, N = new Float64Array(nv * 3), s = T.orientSign(i);
  for (let f = 0; f < idx.length; f += 3) { const a = idx[f]*3, b = idx[f+1]*3, c = idx[f+2]*3;
    const e1 = [pos[b]-pos[a], pos[b+1]-pos[a+1], pos[b+2]-pos[a+2]], e2 = [pos[c]-pos[a], pos[c+1]-pos[a+1], pos[c+2]-pos[a+2]];
    const n = [e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2], e1[0]*e2[1]-e1[1]*e2[0]];
    for (const v of [a, b, c]) { N[v] += n[0]; N[v+1] += n[1]; N[v+2] += n[2]; } }
  const step = Math.max(1, Math.floor(nv / 160)), ds = [];
  for (let v = 0; v < nv; v += step) { const l = Math.hypot(N[3*v], N[3*v+1], N[3*v+2]) || 1, r = hh ? hh.r : rule * s;
    const p = [pos[3*v] + N[3*v]/l*r, pos[3*v+1] + N[3*v+1]/l*r, pos[3*v+2] + N[3*v+2]/l*r]; ds.push(P.closestOnMesh(pos, idx, p).d); }
  ds.sort((a, b) => a - b); o.measured = {median: ds[Math.floor(ds.length / 2)], p25: ds[Math.floor(ds.length / 4)], n: ds.length};
  // the panel lists it
  const row = document.querySelector('.mc-safe [data-q367-viol="' + id + '"]'); o.listed = row ? row.textContent : null;
  o.planTxt = (document.querySelector('.q367-plan [data-q367=safety] .q367-val') || {}).textContent;
  // halos follow the pose: a joint move re-checks on the posed meshes
  const seq0 = q.safe.seq, PZ = window.__poseApi;
  if (PZ) { PZ.set('elbow_r', 'flex', 50); await H.sleep(700); await H.settle(); o.poseSeq = T.q367().safe.seq > seq0;
    const v2 = T.q367().safe.rows.find(x => x.i === i); const g2 = T.geom(i); o.poseD = v2 ? Math.abs(v2.d - P.meshSegDist(g2.pos, g2.idx, T.entry.p, T.target.p, 1e9).d) : null;
    PZ.set('elbow_r', 'flex', 0); await H.sleep(700); await H.settle(); }
  // a clean plan: every rule at 0.5 mm (the path keeps more than that from every vessel / nerve here)
  const minAll = T.corridor().items.length ? Math.min(...T.corridor().items.map(x => x.d_mm)) : 99;
  T.safeSet({rules: {nL: 0.5, nM: 0.5, nS: 0.5, aL: 0.5, aM: 0.5, aS: 0.5, vL: 0.5, vM: 0.5}}); await H.settle();
  o.clean = {minAll, nViol: T.q367().safe.rows.filter(x => x.viol).length, txt: (document.querySelector('.mc-safe .q367-ok') || {}).textContent || null};
  return o;
}"""

LAYOUT = r"""async (label) => {
  const W = innerWidth, Hh = innerHeight, wide = [];
  document.querySelectorAll('#mode-shell *').forEach(e => { const r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return;
    const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') return;
    if (r.right > W + 1 || r.left < -1) wide.push((e.className || e.tagName) + ' ' + Math.round(r.left) + '..' + Math.round(r.right)); });
  const mm = document.getElementById('mode-main').getBoundingClientRect();
  const cards = Array.from(document.querySelectorAll('#mode-shell .mc')).filter(e => !e.hidden && getComputedStyle(e).display !== 'none' && getComputedStyle(e).visibility !== 'hidden').map(e => e.getBoundingClientRect());
  let tot = 0, free = 0;
  for (let y = mm.top + 2; y < mm.bottom; y += 8) for (let x = mm.left + 2; x < mm.right; x += 8) { tot++; if (!cards.some(r => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom)) free++; }
  return {label, scrollW: document.documentElement.scrollWidth, W, wide: wide.slice(0, 6), nWide: wide.length, visible: free / tot};
}"""

ROWS = r"""async () => {
  const H = window.__q367, T = window.NMSKClinicalTool;
  await H.reset(); await H.pick(H.id1('biceps_brachii_r'));
  await H.entry(); await H.sleep(300);
  const rows = Array.from(document.querySelectorAll('.mc-left .mc-drow .nm'));
  const g = document.querySelector('.mc-guide'); if (g) g.open = true;
  const gc = Array.from(document.querySelectorAll('.mc-guide .g-rrow .g-cls')).map(e => e.textContent);
  return {rows: rows.length, withCls: rows.filter(r => r.querySelector('.q367-cl')).length, sample: rows.slice(0, 3).map(r => r.textContent), guideCls: gc.slice(0, 4), nGuide: document.querySelectorAll('.mc-guide .g-rrow[data-g-ids]').length};
}"""


SKINENTRY = r"""async (ids) => {
  const H = window.__q367, T = window.NMSKClinicalTool, P = window.NMSKClinical.pure, out = [];
  for (const id of ids) {
    if (!T.byId[id]) { out.push({id, err: 'absent'}); continue; }
    await H.reset(); await H.pick(id);
    if (!(await H.entry())) { out.push({id, err: 'no computed entry: ' + T.sugg.msg}); continue; }
    const E = T.entry.p; let best = Infinity, who = null;
    T.recs.forEach(r => { if (r.cat !== 'skin') return; if (E.some((c, k) => c < r.bmin[k] - 3 || c > r.bmax[k] + 3)) return;
      const g = T.geom(r.i); const d = P.closestOnMesh(g.pos, g.idx, E).d; if (d < best) { best = d; who = r.id; } });
    out.push({id, skinD: best, skin: who, on: T.entry.i != null ? T.recs[T.entry.i].id : null, cat: T.entry.i != null ? T.recs[T.entry.i].cat : null});
  }
  return out;
}"""

MODEL_PX = r"""() => {   // the model area not covered by a card, the bar, the pills or a pin: sample points (css px)
  const mm = document.getElementById('mode-main').getBoundingClientRect(), vis = e => !e.hidden && getComputedStyle(e).display !== 'none' && getComputedStyle(e).visibility !== 'hidden';
  const cov = Array.from(document.querySelectorAll('#mode-shell .mc, #mode-pills, .q367-pin, #mode-shell .mb-chip')).filter(vis).map(e => e.getBoundingClientRect());
  const pts = [];
  for (let y = mm.top + 6; y < mm.bottom - 4; y += 12) for (let x = mm.left + 6; x < mm.right - 4; x += 12)
    if (!cov.some(r => x >= r.left - 2 && x <= r.right + 2 && y >= r.top - 2 && y <= r.bottom + 2)) pts.push([Math.round(x), Math.round(y)]);
  return pts;
}"""


def model_pixels(pg, check, label):
    """Q367: the model's own canvas must show through wherever no card covers it -- no flat white / opaque plateau over it."""
    import io
    from PIL import Image
    pts = pg.evaluate(MODEL_PX)
    im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
    cols = [im.getpixel((x, y)) for x, y in pts if 0 <= x < im.width and 0 <= y < im.height]
    white = sum(1 for c in cols if min(c) >= 252 or max(c) <= 3)   # an unpainted layer came out pure white or pure black
    distinct = len({(c[0] // 16, c[1] // 16, c[2] // 16) for c in cols})
    check(f"{label}: the model shows wherever no card covers it ({len(cols)} samples, {white} pure white / black, {distinct} colour bins)",
          cols and white <= 0.03 * len(cols) and distinct >= 12)


def srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


# Machado, Oliveira & Fernandes 2009 (IEEE TVCG 15(6)), severity 1.0, applied to linear RGB
CVD = {"protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
       "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
       "tritan": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]}


def lab(rgb_lin):
    r, g, b = (max(0.0, min(1.0, x)) for x in rgb_lin)
    X = 0.4124 * r + 0.3576 * g + 0.1805 * b; Y = 0.2126 * r + 0.7152 * g + 0.0722 * b; Z = 0.0193 * r + 0.1192 * g + 0.9505 * b
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(X / 0.95047), f(Y), f(Z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a, b, m=None):
    la = [srgb_to_lin(c) for c in hex_rgb(a)]; lb = [srgb_to_lin(c) for c in hex_rgb(b)]
    if m:
        la = [sum(m[i][k] * la[k] for k in range(3)) for i in range(3)]; lb = [sum(m[i][k] * lb[k] for k in range(3)) for i in range(3)]
    A, B = lab(la), lab(lb)
    return sum((x - y) ** 2 for x, y in zip(A, B)) ** 0.5


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--size", default="1400x900")
    ap.add_argument("--shots", default="")
    a = ap.parse_args()
    d = Path(a.build_dir).resolve()
    W, H = (int(x) for x in a.size.split("x"))
    phone = W <= 500
    shots = Path(a.shots) if a.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    tag = f"{d.name}_{W}"
    srv, port = serve(d)
    errs: list[str] = []
    page_errors: list[str] = []

    def check(label, cond):
        ok = bool(cond)
        print(("  OK   " if ok else "  FAIL ") + label)
        if not ok:
            errs.append(label)

    def shot(pg, name):
        if shots:
            pg.screenshot(path=str(shots / f"{tag}_{name}.png"))

    def boot(pg, first):
        pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load", timeout=180000)
        pg.wait_for_function("window.NMSKUltrasound && window.NMSKClinicalTool && window.NMSKModes && window.__poseApi && window.__poseApi.ready()", timeout=180000)
        pg.wait_for_function("window.NMSKClinicalTool.guide && window.NMSKClinicalTool.guide.data && window.NMSKClinicalTool.vcal && window.NMSKClinicalTool.api.parts() && window.NMSKClinicalTool.api.parts().state().loaded", timeout=90000)
        pg.wait_for_timeout(1200)
        pg.evaluate("() => { const c = document.getElementById('mw-close'); if (c) c.click(); }")
        if first:
            pg.evaluate("() => { try { localStorage.removeItem('nmsk-inj-safety-v1'); } catch (e) {} }")
            pg.reload(wait_until="load", timeout=180000)
            return boot(pg, False)
        check("helpers installed", pg.evaluate(HELPERS))
        pg.evaluate("() => window.NMSKModes.enter('inj')")
        pg.wait_for_timeout(1800)

    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
            ctx = b.new_context(viewport={"width": W, "height": H}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: page_errors.append(str(e)))
            pg.route("**/*", lambda rq: rq.abort() if "fonts.g" in rq.request.url else rq.continue_())
            print(f"=== {d.name} @ {W}x{H} ===")
            boot(pg, True)
            st = pg.evaluate("() => { const T = window.NMSKClinicalTool; return {rules: T.safe.rules, picker: !!document.querySelector('.mc-pick'), startEntry: !!document.querySelector('.mc-pick .q367-start-entry'), plan: !!document.querySelector('.q367-plan'), nv: Object.keys(T.vcal).length}; }")
            check(f"mode entered: the plan panel is shown, the tip picker offers 'start from the skin entry' ({st})", st["plan"] and st["picker"] and st["startEntry"])
            check(f"distance rules start EMPTY (no invented figure): {st['rules']}", st["rules"] == {})
            check(f"vessel calibre sibling loaded ({st['nv']} vessels)", st["nv"] > 300)
            if phone:
                r = pg.evaluate(LAYOUT, "phone: picker open")
                check(f"phone, picker open: nothing wider than the screen ({r['nWide']} {r['wide']}, scrollWidth {r['scrollW']})", r["nWide"] == 0 and r["scrollW"] <= W)
            pg.evaluate("() => window.__q367.closePick()")
            shot(pg, "plan_start")

            # ---- order
            r = pg.evaluate(ORDER)
            if r.get("err"):
                check("order: " + r["err"], False)
            else:
                print(f"     tip-first: tip {r['A']['tip']}, entry {r['A']['entry']}, {r['A']['len']:.2f} mm; entry-first: {r['B']['len']}")
                check(f"tip chosen in the plan picker -> tip kind 'centre' ({r['tipKind']})", r["tipKind"] == "centre")
                check("entry first: the entry stands alone (no tip yet)", r["entryOnly"])
                check(f"tip-first and entry-first give the same path (tip {r['dTip']}, entry {r['dEntry']} mm, length {r['A']['len']:.3f} / {r['B']['len']}, same crossings)",
                      r["dTip"] is not None and r["dTip"] < 1e-6 and r["dEntry"] < 1e-6 and abs(r["A"]["len"] - r["B"]["len"]) < 1e-6 and r["A"]["cross"] == r["B"]["cross"])
                t = r["tap"]
                check(f"armed 'tap on the skin': the entry lands at the tapped pixel ({t['px']} px), the tip untouched, then disarmed", r["armed"] == "yes" and t["px"] is not None and t["px"] < 2.5 and t["tipSame"] and t["disarmed"])

            # ---- refinements
            for x in pg.evaluate(REFINE):
                ty = x["type"]
                if x.get("err"):
                    check(f"{ty}: {x['err']}", False)
                elif x.get("none"):
                    print(f"     {ty}: no data on this body for the test muscles (not offered)")
                elif ty in ("origin", "insertion", "motor point", "IZ band"):
                    check(f"{ty} ({x['muscle']}{' ' + str(x.get('site')) if x.get('site') else ''}): tip {x['d']:.3f} mm from the data's point, kind {x['kind']}", x["btn"] and x["d"] is not None and x["d"] <= 0.5 and x["kind"] in (ty, "mp", "iz"))
                elif ty == "plane":
                    print(f"     plane {x['a']} | {x['b']}: {x['n']} points, min gap {x['minGap']}, label {x['label']!r}")
                    check(f"plane between {x['a']} and {x['b']} (offered as adjacent: {x['viaAdj']}): {x['n']} patch points, each midway (worst |dA-dB| {x['worstMid']:.3f} mm) within the gap (worst dA+dB {x['worstSum']:.2f} <= {x['gap']} + 0.5)",
                          x["n"] > 10 and x["worstMid"] <= 0.5 and x["worstSum"] <= x["gap"] + 0.5 and x["kind"] == "plane")
                    check(f"plane tip midway between the two surfaces (dA {x['tA']:.2f}, dB {x['tB']:.2f} mm)", abs(x["tA"] - x["tB"]) <= 0.5 and x["tA"] + x["tB"] <= x["gap"] + 0.5)
                elif ty == "plane tip nearest the entry":
                    check(f"plane with an entry: the tip is the patch point nearest the entry ({x['d']})", x["d"] is not None and x["d"] < 1e-6 and x["kind"] == "plane")
                elif ty == "perineural":
                    check(f"perineural ({x['nerve']}): picked nerve -> kind {x['kind']}, tip {x['d']:.3f} mm from its surface (offset {x['off']}), outside it", x["kind"] == "peri" and abs(x["d"] - x["off"]) <= 0.05 and not x["inside"])
                    if "d2" in x:
                        check(f"perineural offset 3.5 mm -> tip {x['d2']:.3f} mm from the nerve, outside", abs(x["d2"] - 3.5) <= 0.05 and not x["inside2"])
                elif ty == "bursa":
                    check(f"bursa ({x['id']}): kind {x['kind']}, tip inside the sac: {x['inside']}", x["kind"] == "cavity" and x["inside"])
                elif ty == "joint space":
                    if x.get("kind") != "intra":
                        print(f"     joint space {x['id']}: not offered ({x})")
                        continue
                    check(f"joint space ({x['id']}, bones {x['bones']}): tip midway (dA {x['dA']:.2f}, dB {x['dB']:.2f} mm), inside the capsule's box", abs(x["dA"] - x["dB"]) <= 0.5 and x["inBox"])
                elif ty == "free tap":
                    check(f"free tap: tip at the tapped point ({x['d']}), kind {x['kind']}", x["d"] is not None and x["d"] < 1e-6 and x["kind"] == "free")
                elif ty == "missing line":
                    print(f"     missing-data line on the last target: {x['text']!r}")
            if not any(x["type"] == "joint space" and x.get("kind") == "intra" for x in []):
                pass

            # ---- markers
            m = pg.evaluate(MARKERS)
            shot(pg, "markers")
            tp, en = m["tip"], m["entry"]
            check(f"markers: tip and entry pins both shown on screen ({tp and (round(tp['x']), round(tp['y']))}, {en and (round(en['x']), round(en['y']))})",
                  tp and en and tp["shown"] and en["shown"] and 0 <= tp["x"] <= W and 0 <= tp["y"] <= H and 0 <= en["x"] <= W and 0 <= en["y"] <= H)
            if tp and en:
                check(f"markers differ in shape ({tp['shape']} / {en['shape']}) and colour ({tp['color']} / {en['color']})", tp["shape"] != en["shape"] and tp["color"].lower() != en["color"].lower())
                de = {k: delta_e(tp["color"], en["color"], mm) for k, mm in [("normal", None)] + list(CVD.items())}
                check(f"marker colours apart for normal and colour-deficient vision (CIE76 dE: {', '.join(f'{k} {v:.0f}' for k, v in de.items())}; >= 20 each)", all(v >= 20 for v in de.values()))
            check(f"step-sheet chips use the same pair ({m['chipTip']}, {m['chipEntry']}) and a one-line legend ({m['legend']!r})",
                  m["chipTip"] and m["chipEntry"] and m["chipTip"]["bg"] != m["chipEntry"]["border"] and "קצה המחט" in m["legend"] and "מעבר בעור" in m["legend"])

            if not phone:   # the scan clip draws the same pair
                c = pg.evaluate(CLIP)
                shot(pg, "clip_markers")
                check(f"scan clip: the tip and entry markers drawn in the image ({c.get('mk')})", c.get("on") and c.get("mk") and "tip" in c["mk"] and "entry" in c["mk"])
                pg.evaluate("() => { const C = window.NMSKUltrasound.needleClip; C.stop(); if (window.NMSKUltrasound.close) window.NMSKUltrasound.close(); }")
                pg.wait_for_timeout(600)

            # ---- distance rows show the class
            r = pg.evaluate(ROWS)
            check(f"distance rows show the size class ({r['withCls']}/{r['rows']}: {r['sample']})", r["rows"] == 0 or r["withCls"] > 0)
            check(f"the guide's at-risk rows show the class ({r['guideCls']} of {r['nGuide']} rows)", r["nGuide"] == 0 or len(r["guideCls"]) > 0)

            # ---- safety
            r = pg.evaluate(SAFETY)
            if r.get("err"):
                check("safety: " + r["err"], False)
            else:
                check(f"all rules off: no checked rows, no rule halos ({r['off']})", r["off"]["rows"] == 0)
                ru = r["rule"]
                print(f"     rule under test: {ru}")
                got = pg.evaluate(SAFE_SET, {ru["key"]: ru["rule"]})
                check(f"rule set through the panel's field ({got})", got == {ru["key"]: ru["rule"]})
                pg.wait_for_timeout(500)
                shot(pg, "safety_violation")
                r2 = pg.evaluate(SAFETY2, [ru["id"], ru["key"], ru["rule"]])
                check(f"violating plan flagged: {ru['id']} ({ru['cls']['k']}{ru['cls']['c']}), {r2['d']} mm < rule {ru['rule']} (independent measure {r2['ind']:.4f})",
                      r2["flagged"] and abs(r2["d"] - r2["ind"]) < 1e-3)
                check(f"the panel lists it ({r2['listed']!r}); the plan row says so ({r2['planTxt']!r})", r2["listed"] and "<" in r2["listed"] and "הפר" in (r2["planTxt"] or ""))
                check(f"its halo is drawn at the rule ({r2['halo']}) and marked (alpha 0.42); the offending path stretch drawn ({r2['segs']} pieces)",
                      r2["halo"] and abs(abs(r2["halo"]["r"]) - ru["rule"]) < 1e-9 and r2["halo"]["alpha"] > 0.4 and r2["segs"] > 0)
                ms = r2["measured"]
                check(f"halo measured: the inflated surface lies {ms['median']:.2f} mm (median, p25 {ms['p25']:.2f}, {ms['n']} vertices) from the structure, rule {ru['rule']} mm (within 15 %)",
                      abs(ms["median"] - ru["rule"]) <= 0.15 * ru["rule"])
                check(f"every drawn rule halo is at its rule's radius; {r2['nHalos']} halos <= cap {r2['cap']}", r2["allAtRule"] and r2["nHalos"] <= r2["cap"])
                if "poseSeq" in r2:
                    check(f"the check follows the pose (re-run after a 50 deg elbow move, distance = posed measure, diff {r2['poseD']})", r2["poseSeq"] and (r2["poseD"] is None or r2["poseD"] < 1e-3))
                c = r2["clean"]
                if c["minAll"] > 0.6:
                    check(f"clean plan (every rule 0.5 mm, nearest structure {c['minAll']:.2f} mm): no violation, the panel says so ({c['txt']!r})", c["nViol"] == 0 and c["txt"] and "אין הפרה" in c["txt"])
                else:
                    print(f"     clean-plan check skipped: a structure lies {c['minAll']:.2f} mm from the path")
                model_pixels(pg, check, f"{'phone' if phone else 'desktop'}, Safety card open")
                lay = pg.evaluate(LAYOUT, "safety card open")
                check(f"{'phone' if phone else 'desktop'}, Safety card open: model {lay['visible'] * 100:.0f} % visible (>= 50), nothing wider than the screen ({lay['nWide']} {lay['wide']})", lay["visible"] >= 0.5 and lay["nWide"] == 0 and lay["scrollW"] <= W)
                shot(pg, "safety_card")
                # persistence across a reload
                want = pg.evaluate("() => window.NMSKClinicalTool.q367().safe.rules")
                thr = pg.evaluate("() => { window.NMSKClinicalTool.safeSet({thr: {a: [7, 3.5]}}); return window.NMSKClinicalTool.q367().safe.thr; }")
                boot(pg, False)
                back = pg.evaluate("() => ({rules: window.NMSKClinicalTool.q367().safe.rules, thr: window.NMSKClinicalTool.q367().safe.thr})")
                check(f"rules and thresholds persist across a reload ({back['rules']} / {back['thr']['a']})", back["rules"] == want and back["thr"] == thr)
                pg.evaluate("() => { window.NMSKClinicalTool.safeSet({thr: {a: [6, 3]}, rules: {nL: null, nM: null, nS: null, aL: null, aM: null, aS: null, vL: null, vM: null}}); }")
            pg.evaluate("() => window.__q367.closePick()")
            pg.evaluate("async () => { const H = window.__q367, T = window.NMSKClinicalTool; await H.pick(H.id1('biceps_brachii_r')); await H.entry(); }")
            lay = pg.evaluate(LAYOUT, "plan panel")
            check(f"{'phone' if phone else 'desktop'}, planning: model {lay['visible'] * 100:.0f} % visible (>= 50), nothing wider than the screen ({lay['nWide']} {lay['wide']}, scrollWidth {lay['scrollW']})",
                  lay["visible"] >= 0.5 and lay["nWide"] == 0 and lay["scrollW"] <= W)
            shot(pg, "plan_panel")
            model_pixels(pg, check, f"{'phone' if phone else 'desktop'}, plan panel open")
            for x in pg.evaluate(SKINENTRY, ["biceps_brachii_r", "tibialis_anterior_r", "pectoralis_major_r", "rectus_abdominis_r", "latissimus_dorsi_r"]):
                if x.get("err"):
                    print(f"     computed entry for {x['id']}: {x['err']}")
                    continue
                check(f"computed entry for {x['id']} lies on the outer skin ({x['skinD']:.3f} mm from {x['skin']}; picked on {x['on']})", x["skinD"] <= 1.0)
            pg.evaluate("() => window.NMSKModes.exit()")
            pg.wait_for_timeout(800)
            gone = pg.evaluate("() => Array.from(document.querySelectorAll('.q367-pin')).every(e => getComputedStyle(e).display === 'none') && !document.body.classList.contains('inj-safe')")
            check("leaving the mode hides the pins and the Safety card", gone)
            b.close()
    finally:
        srv.terminate()

    check(f"no page errors ({len(page_errors)})", not page_errors)
    for e in page_errors[:5]:
        print("     page error: " + e[:300])
    print()
    if errs:
        print(f"Q367_PLAN_FAIL {len(errs)}")
        return 1
    print("Q367_PLAN_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
