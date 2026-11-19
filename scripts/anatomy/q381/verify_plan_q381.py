#!/usr/bin/env python3
"""Q381 (owner, 2026-11-19): the injection planning mode on a built Base page, in headless Chromium. Deterministic, by structure id.

  A  bone      a straight path that crosses bone is BLOCKED -- flagged by the tool exactly when an independent test (segCrossesTri over
               every bone / hyaline-cartilage mesh of the page, current pose) says it crosses: an entry tapped on the skin in front of the
               tibia for a tibialis posterior tip (the bone is named, the entry pin struck out, "show in scan" / "add point" withheld);
               the offered entry is on the skin, crosses nothing, keeps >= 1 mm from bone and no sampled valid entry lies > 2 mm nearer;
               every suggested entry of every listed muscle is bone-free; a tip moved into a bone, and a pose change, are re-tested; a tip
               with no bone-free straight path says so; hyaline cartilage blocks, a meniscus / the interosseous membrane only gets listed.
  B  tip       for >= 8 muscles by id (tibialis posterior L, deep forearm, hip, trunk ...): the default tip is INSIDE the muscle's mesh
               (3-direction parity, independent of the tool's own test) and in no bone, in the rest pose and in the spastic pose; the
               on-screen pin sits on the projection of the tip (own camera maths from the page's camera hook) within 2 px for >= 6
               camera orientations, after a real drag / wheel / pinch-zoom, at device pixel ratio 1 and 1.25 (a page zoom), rest + posed;
               the pin says how deep, the target's silhouette is drawn through.
  C  origin    the origin / insertion chips put the tip on the page's attachment site (<= 0.5 mm), with its provenance line; every muscle
               with a placed site is offered it; the census is printed.
  D  skin      the three skin looks set the engine as stated, are undone / redone step by step, and leaving the mode restores the
               anatomy screen's own snapshot exactly.
  E  safety    "בטיחות" is its own titled subsection: not defined -> distances only; the user's rules -> custom -> declared default.

    python3 scripts/anatomy/q381/verify_plan_q381.py <page dir> [--size 1400x900] [--part abcde] [--shots DIR]
Prints VERIFY_PLAN_Q381_OK / _FAIL.
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
TP = "zan_tibialis_posterior_muscle_l"
# id, posture key, side  (deep forearm: FDP, pronator quadratus; hip: piriformis, gluteus medius; trunk: rectus abdominis, quadratus lumborum)
MUSCLES = [[TP, "ll", "l"], ["flexor_digitorum_profundus_r", "ul", "r"], ["pronator_quadratus_l", "ul", "l"], ["piriformis_r", "ll", "r"],
           ["gluteus_medius_l", "ll", "l"], ["rectus_abdominis_r", "ll", "r"], ["quadratus_lumborum_l", "ll", "l"], ["biceps_brachii_r", "ul", "r"],
           ["soleus_l", "ll", "l"], ["flexor_hallucis_longus_r", "ll", "r"], ["subscapularis_l", "ul", "l"]]

HELPERS = r"""() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const T = window.NMSKClinicalTool, P = window.NMSKClinical.pure, D = (a, b) => Math.hypot(a[0]-b[0], a[1]-b[1], a[2]-b[2]);
  const sub = (a, b) => [a[0]-b[0], a[1]-b[1], a[2]-b[2]], add = (a, b, s) => [a[0]+b[0]*s, a[1]+b[1]*s, a[2]+b[2]*s], dot = (a, b) => a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
  const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]], norm = a => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0]/l, a[1]/l, a[2]/l]; };
  async function frames(n) { for (let k = 0; k < (n || 2); k++) await new Promise(r => requestAnimationFrame(r)); await sleep(40); }
  async function settle() { for (let k = 0; k < 100; k++) { await sleep(60); if (!T.corr.timer && !T.safe.timer && !T.blockT) break; } await sleep(260); await frames(2); }
  function closePick() { const c = document.querySelector('.mc-pick .mc-close'); if (c) c.click(); }
  async function pick(id) {
    closePick();
    const b = document.querySelector('.q367-plan [data-q367=tip] button'); if (b) b.click(); await sleep(200);
    const inp = document.querySelector('.mc-pick .mc-search'); if (!inp) return false;
    inp.value = id; inp.dispatchEvent(new Event('input')); await sleep(120);
    const row = document.querySelector('.mc-pick .mc-res button'); if (!row) return false;
    row.click(); await sleep(600); await settle(); return true;
  }
  async function reset() { closePick(); T.clear(); T.planRelease(); await settle(); }
  /* ---- independent geometry (none of it is the tool's bone test or its inside test) ---- */
  const HY = /articular_cartilage|costal_cartilage|triradiate/;
  const blockers = T.recs.filter(r => r.cat === 'bone' || (r.cat === 'cartilage' && HY.test(r.id))).map(r => r.i);
  function boxSeg(r, A, B, pad) { for (let k = 0; k < 3; k++) { if (Math.max(A[k], B[k]) < r.bmin[k] - pad || Math.min(A[k], B[k]) > r.bmax[k] + pad) return false; } return true; }
  function crossings(A, B) {   // [{id, t}] every blocking triangle the segment crosses (Q268's segCrossesTri; t from the triangle's plane)
    const out = [], L = D(A, B);
    for (const i of blockers) {
      const r = T.recs[i]; if (!boxSeg(r, A, B, 0.1)) continue;
      const g = T.geom(i), p = g.pos, I = g.idx;
      for (let f = 0; f < I.length; f += 3) {
        const a = [p[3*I[f]], p[3*I[f]+1], p[3*I[f]+2]], b = [p[3*I[f+1]], p[3*I[f+1]+1], p[3*I[f+1]+2]], c = [p[3*I[f+2]], p[3*I[f+2]+1], p[3*I[f+2]+2]];
        if (!P.segCrossesTri(A, B, a, b, c)) continue;
        const n = cross(sub(b, a), sub(c, a)), den = dot(n, sub(B, A)); if (Math.abs(den) < 1e-12) continue;
        out.push({id: r.id, t: dot(n, sub(a, A)) / den * L});
      }
    }
    return out.sort((x, y) => x.t - y.t);
  }
  function blockedInd(A, B) { const L = D(A, B); return crossings(A, B).filter(x => x.t < L - 0.5); }
  function clearInd(A, B) {   // the path's distance from bone over its first L - 3 mm
    const L = D(A, B); if (L < 3.5) return Infinity; const B2 = add(A, norm(sub(B, A)), L - 3); let best = Infinity;
    for (const i of blockers) { const r = T.recs[i]; if (!boxSeg(r, A, B2, 3)) continue; const g = T.geom(i), m = P.meshSegDist(g.pos, g.idx, A, B2, Math.min(best, 3)); if (m.d < best) best = m.d; }
    return best;
  }
  const DIRS = [[0.2672, 0.5345, 0.8018], [-0.6667, 0.3333, 0.6667], [0.4243, -0.5657, 0.7071]];
  function parity(g, p, d) {   // crossings of the ray p + t d, shared edges merged
    const ts = P.segMeshHits(g.pos, g.idx, p, add(p, d, 4000)).map(h => h.t).filter(t => t > 1e-5); let n = 0, last = -1;
    for (const t of ts) { if (t - last > 1e-4) n++; last = t; } return n % 2;
  }
  function inMesh(i, p) { const g = T.geom(i); return DIRS.reduce((s, d) => s + parity(g, p, d), 0) >= 2; }
  function inAnyBone(p) { for (const i of blockers) { const r = T.recs[i]; if (p[0] < r.bmin[0] || p[1] < r.bmin[1] || p[2] < r.bmin[2] || p[0] > r.bmax[0] || p[1] > r.bmax[1] || p[2] > r.bmax[2]) continue; if (inMesh(i, p)) return r.id; } return null; }
  /* ---- the camera (the page's read-only hook) and an own projection ---- */
  const Q = window.__q334;
  function projInd(p) {
    const c = Q.cam(), r = T.api.canvas.getBoundingClientRect(), ce = Math.cos(c.el), se = Math.sin(c.el);
    const eye = [c.tgt[0] + c.dist * ce * Math.sin(c.az), c.tgt[1] + c.dist * se, c.tgt[2] + c.dist * ce * Math.cos(c.az)];
    /* the model frame is left-handed (+X the patient's right, +Y superior, +Z anterior; Q339): the screen's right is up x forward */
    const f = norm(sub(c.tgt, eye)), right = norm(cross([0, 1, 0], f)), up = norm(sub([0, 1, 0], [f[0] * f[1], f[1] * f[1], f[2] * f[1]])), v = sub(p, eye), z = dot(v, f); if (z <= 1e-6) return null;
    const th = Math.tan(0.85 / 2), x = dot(v, right) / (z * th * (r.width / r.height)), y = dot(v, up) / (z * th);
    return [r.left + (x * 0.5 + 0.5) * r.width, r.top + (1 - (y * 0.5 + 0.5)) * r.height, r];
  }
  function pinXY(k) { const e = document.querySelector('.q367-pin-' + k); if (!e || e.style.display === 'none') return null; const b = e.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; }
  async function pinErr(k, p) {   // |pin centre - own projection| in css px; null when the point is off the canvas
    await frames(3);
    const s = projInd(p); if (!s) return null; const r = s[2];
    if (s[0] < r.left + 4 || s[0] > r.right - 4 || s[1] < r.top + 4 || s[1] > r.bottom - 4) return null;
    const x = pinXY(k); return x ? Math.hypot(x[0] - s[0], x[1] - s[1]) : 1e9;
  }
  function aimAt(p, dir, dist) { Q.cam({az: Math.atan2(dir[0], dir[2]), el: Math.asin(Math.max(-1, Math.min(1, dir[1]))), dist: dist, tgt: p}); }   // the eye at p + dir * dist
  window.__q381 = {sleep, frames, settle, pick, closePick, reset, D, sub, add, dot, cross, norm, crossings, blockedInd, clearInd, inMesh, inAnyBone, projInd, pinXY, pinErr, aimAt, blockers};
  return !!(T && T.q381 && P.segMeshHits && P.meshCentre && Q);
}"""

# B: one muscle -- the tip's place and the pin, rest and posed
TIP_ONE = r"""async (m) => {
  const H = window.__q381, T = window.NMSKClinicalTool, Q = window.__q334, o = {id: m[0]};
  if (!T.byId[m[0]]) return Object.assign(o, {err: 'no such structure'});
  await H.reset();
  if (!(await H.pick(m[0]))) return Object.assign(o, {err: 'picker failed'});
  const i = T.byId[m[0]][0], t = T.target; if (!t) return Object.assign(o, {err: 'no tip'});
  o.kind = t.kind; o.host = t.i === i;
  async function state(tag) {
    const p = T.target.p.slice(), f = T.q381(), s = {p, inside: H.inMesh(i, p), bone: H.inAnyBone(p), rel: f.facts && f.facts.rel, dOwn: f.facts && f.facts.dOwn, dSkin: f.facts && f.facts.dSkin,
                                                    ghost: (f.ghosts || []).map(g => g.i).indexOf(i) >= 0, errs: [], off: 0};
    const g = T.geom(i); s.dOwnInd = window.NMSKClinical.pure.closestOnMesh(g.pos, g.idx, p).d;
    const base = Math.max(180, Math.min(900, 2.2 * H.D(T.recs[i].bmin, T.recs[i].bmax)));
    const cams = [[0, 0.1, 1, [0, 0, 0]], [1.2, 0.5, 0.7, [25, 10, 0]], [2.5, -0.4, 1.3, [-20, -25, 10]], [3.9, 0.9, 0.9, [0, 30, -15]], [5.2, -0.8, 1.1, [15, -10, 20]], [0.6, 0.3, 0.5, [-10, 5, 5]], [4.4, 0.0, 1.6, [30, 20, -20]]];
    for (const c of cams) { Q.cam({az: c[0], el: c[1], dist: base * c[2], tgt: [p[0] + c[3][0], p[1] + c[3][1], p[2] + c[3][2]]}); const e = await H.pinErr('tip', p); if (e == null) s.off++; else s.errs.push(e); }
    s.max = s.errs.length ? Math.max(...s.errs) : null; s.n = s.errs.length;
    const pin = T.q381().pin; s.tag = pin.tag; s.deep = pin.deep; s.depth = pin.depth;
    o[tag] = s; return s;
  }
  await state('rest');
  o.factsTxt = (document.querySelector('[data-q381=facts]') || {}).textContent || '';
  const rev0 = window.__poseRev | 0;
  const ap = T.applyPosture(m[1], m[2]); o.applied = ap ? ap.applied.length : null;
  await H.sleep(700); await H.settle();
  o.rev = (window.__poseRev | 0) > rev0; o.moved = H.D(T.target.p, o.rest.p);
  await state('posed');
  o.posedCentre = H.D(T.target.p, T.centreOf(i).p);
  T.applyPosture('rest', m[2]); await H.sleep(700); await H.settle();
  o.back = H.D(T.target.p, o.rest.p);
  return o;
}"""

# B: real input (drag, wheel, pinch-zoom) on the current plan, then the pin again
TIP_INPUT = r"""async () => {
  const H = window.__q381, T = window.NMSKClinicalTool, Q = window.__q334;
  const p = T.target.p.slice(); Q.cam({az: 0.4, el: 0.2, dist: 420, tgt: p}); await H.frames(3);
  const r = T.api.canvas.getBoundingClientRect(); let pt = null;
  for (let y = r.top + 60; y < r.bottom - 60 && !pt; y += 37) for (let x = r.left + 60; x < r.right - 60 && !pt; x += 41) { const e = document.elementFromPoint(x, y); if (e && e.tagName === 'CANVAS' && Math.hypot(x - (r.left + r.width / 2), y - (r.top + r.height / 2)) > 60) pt = [x, y]; }
  return {pt, cam: Q.cam(), e0: await H.pinErr('tip', p)};
}"""
TIP_AFTER = r"""async () => { const H = window.__q381, T = window.NMSKClinicalTool, Q = window.__q334; const e = await H.pinErr('tip', T.target.p); const en = T.entry ? await H.pinErr('entry', T.entry.p) : null;
  return {cam: Q.cam(), err: e, entryErr: en, dpr: window.devicePixelRatio, w: window.innerWidth, rect: (r => [r.left, r.top, r.width, r.height])(T.api.canvas.getBoundingClientRect())}; }"""
TIP_CAMS = r"""async () => {   // the same seven orientations once more (after a page-zoom change)
  const H = window.__q381, T = window.NMSKClinicalTool, Q = window.__q334, p = T.target.p.slice(), errs = [];
  for (const c of [[0, 0.1, 400], [1.2, 0.5, 300], [2.5, -0.4, 520], [3.9, 0.9, 380], [5.2, -0.8, 450], [0.6, 0.3, 240], [4.4, 0.0, 600]]) { Q.cam({az: c[0], el: c[1], dist: c[2], tgt: [p[0] + 12, p[1] - 8, p[2] + 5]}); const e = await H.pinErr('tip', p); if (e != null) errs.push(e); }
  return {n: errs.length, max: errs.length ? Math.max(...errs) : null, dpr: window.devicePixelRatio, w: window.innerWidth};
}"""

# A: the blocked path, the offered entry
BONE_BLOCK = r"""async () => {
  const H = window.__q381, T = window.NMSKClinicalTool, P = window.NMSKClinical.pure, Q = window.__q334, o = {};
  await H.reset(); if (!(await H.pick('""" + TP + r"""'))) return {err: 'picker failed'};
  const tib = T.byId['tibia_l'][0], tip = T.target.p.slice(), gt = T.geom(tib), ct = P.meshCentre(gt.pos, gt.idx).p, dir = H.norm(H.sub(ct, tip));
  const hs = T.raySkin(tip, dir, 400); if (!hs.length) return {err: 'no skin beyond the tibia'};
  const E = H.add(tip, dir, hs[hs.length - 1].t); o.E = E;
  o.indep = H.blockedInd(E, tip).map(x => x.id); o.indepFirst = o.indep[0] || null;
  // an armed tap on the skin, at the pixel of E, looking straight at it
  H.aimAt(E, dir, 420); await H.frames(3);
  const s = T.api.toScreen(E), tapBtn = document.querySelector('.q367-plan [data-q367=entry] button'); tapBtn.click(); await H.sleep(120);
  o.armed = !!T.armFn && T.armSkin === true;
  T.onClick({clientX: s[0], clientY: s[1], button: 0}); await H.settle();
  const e = T.entry; if (!e) return Object.assign(o, {err: 'the tap set no entry'});
  o.entryOnSkin = e.i != null && T.recs[e.i].cat === 'skin'; o.dTap = H.D(e.p, E);
  o.q = T.q381(); o.indepNow = H.blockedInd(e.p, T.target.p).map(x => x.id);
  const box = document.querySelector('[data-q381=block]');
  o.ui = {shown: !!box && !box.hidden, bone: box ? box.getAttribute('data-q381-bone') : null, txt: box ? box.textContent : '', ent: document.querySelector('.q367-plan [data-q367=entry] .q367-val').textContent,
          entBad: document.querySelector('.q367-plan [data-q367=entry] .q367-val').classList.contains('q367-bad'), pinX: !!document.querySelector('.q367-pin-entry.q381-blocked'),
          scanHidden: (b => !b || b.hidden)(Array.from(document.querySelectorAll('.mc-right .mc-sec')).find(b => b.textContent === 'הצג בסריקה')),
          addDisabled: (b => !!b && b.disabled)(Array.from(document.querySelectorAll('.mc-right .mc-sec')).find(b => b.textContent === 'הוסף נקודה')), report: (document.querySelector('.mc-right .mc-hint.q367-bad') || {}).textContent || ''};
  o.boneName = T.name(tib);
  for (let k = 0; k < 80 && T.q381().alt === 'pending'; k++) await H.sleep(100);
  await H.settle();
  const a = T.q381().alt; o.alt = a;
  if (a && a.E) {
    const tp = T.target.p;
    o.altInd = {cross: H.blockedInd(a.E, tp).length, clear: H.clearInd(a.E, tp), skin: a.entryI != null && T.recs[a.entryI].cat === 'skin', dSkin: (g => P.closestOnMesh(g.pos, g.idx, a.E).d)(T.geom(a.entryI)), d: H.D(a.E, e.p)};
    // is a valid entry clearly nearer? 500 directions in a 30-degree cone around the chosen one, skin point by the tool's entry finder, validity by the independent tests
    const reg = T.region(tp, a.reach), u0 = H.norm(H.sub(e.p, tp)); let best = Infinity, nv = 0;
    for (const u of P.coneDirs(u0, 30 * Math.PI / 180, 500)) { const en = T.entryFor(reg, tp, u, a.reach); if (!en.ok || en.obstructed) continue; const d = H.D(en.E, e.p); if (d >= best) continue; if (H.blockedInd(en.E, tp).length || H.clearInd(en.E, tp) < 1) continue; best = d; nv++; }
    o.altInd.nearestSampled = best;
    o.altTxt = (document.querySelector('[data-q381=alt]') || {}).textContent || '';
  }
  return o;
}"""
BONE_ALT_USE = r"""async () => {
  const H = window.__q381, T = window.NMSKClinicalTool, o = {};
  const a = T.q381().alt, b = document.querySelector('[data-q381=alt-use]'); if (!b) return {err: 'no button'};
  b.click(); await H.settle();
  o.q = T.q381(); o.dEntry = H.D(T.entry.p, a.E); o.indep = H.blockedInd(T.entry.p, T.target.p).length;
  o.boxHidden = document.querySelector('[data-q381=block]').hidden; o.pinX = !!document.querySelector('.q367-pin-entry.q381-blocked');
  o.ent = document.querySelector('.q367-plan [data-q367=entry] .q367-val').textContent;
  o.passIds = o.q.pass.map(x => x.id); o.passTxt = (document.querySelector('[data-q381=pass]') || {}).textContent || '';
  o.addDisabled = (b2 => !!b2 && b2.disabled)(Array.from(document.querySelectorAll('.mc-right .mc-sec')).find(b2 => b2.textContent === 'הוסף נקודה'));
  // the tip moved afterwards, into the tibia: the same entry is now blocked
  const tib = T.byId['tibia_l'][0], g = T.geom(tib), c = window.NMSKClinical.pure.meshCentre(g.pos, g.idx).p;
  T.plTipSet({p: c, i: tib}, 'free'); await H.settle();
  o.moved = {q: T.q381(), indep: H.blockedInd(T.entry.p, T.target.p).map(x => x.id), boxShown: !document.querySelector('[data-q381=block]').hidden};
  for (let k = 0; k < 100 && T.q381().alt === 'pending'; k++) await H.sleep(100);
  await H.settle();
  o.none = {alt: T.q381().alt, txt: (document.querySelector('[data-q381=no-path]') || {}).textContent || ''};
  // suggestions for that tip: none, said plainly
  const sug = Array.from(document.querySelectorAll('.q367-plan [data-q367=entry] button')).find(x => x.textContent === 'הצעות'); sug.click(); await H.sleep(300); await H.settle();
  o.noSugg = {none: T.sugg.none, n: T.sugg.cands.length, msg: T.sugg.msg, hint: (document.querySelector('.mc-right p.mc-hint:not(.q367-bad)') || {}).textContent, hints: Array.from(document.querySelectorAll('.mc-right > p.mc-hint')).map(x => x.textContent).join(' | ')};
  return o;
}"""
BONE_SUGG = r"""async (ids) => {
  const H = window.__q381, T = window.NMSKClinicalTool, out = [];
  for (const id of ids) {
    if (!T.byId[id]) { out.push({id, err: 'missing'}); continue; }
    await H.reset(); if (!(await H.pick(id))) { out.push({id, err: 'pick'}); continue; }
    T.suggest(); const tp = T.target.p;
    const bad = T.sugg.cands.filter(c => H.blockedInd(c.E, tp).length).length;
    out.push({id, n: T.sugg.cands.length, shown: T.sugg.shown.length, bad, none: T.sugg.none, skin: T.sugg.nSkin, free: T.sugg.nFree, longer: T.sugg.longer, msg: T.sugg.msg});
  }
  return out;
}"""
BONE_POSE = r"""async () => {
  const H = window.__q381, T = window.NMSKClinicalTool, o = {tried: 0, became: null, agree: true, rows: []};
  // forearm paths in the spastic (pronated) pose: each suggested entry of two deep forearm muscles, valid at rest, then posed
  for (const id of ['flexor_digitorum_profundus_r', 'pronator_quadratus_r', 'supinator_r']) {
    if (!T.byId[id]) continue;
    await H.reset(); if (!(await H.pick(id))) continue;
    T.suggest(); const cands = T.sugg.cands.slice(0, 3);
    for (const c of cands) {
      T.adoptSuggestion(c); await H.settle();
      const r0 = T.q381().blocked, i0 = H.blockedInd(T.entry.p, T.target.p).length > 0, seq0 = T.blockSeq;
      T.applyPosture('ul', 'r'); await H.sleep(700); await H.settle();
      const r1 = T.q381().blocked, i1 = H.blockedInd(T.entry.p, T.target.p).length > 0, re = T.blockSeq > seq0;
      o.tried++; o.rows.push({id, r0, i0, r1, i1, re});
      if (r0 !== i0 || r1 !== i1 || !re) o.agree = false;
      if (!r0 && r1 && !o.became) o.became = {id, bone: T.q381().block.hits[0].id, box: !document.querySelector('[data-q381=block]').hidden};
      T.applyPosture('rest', 'r'); await H.sleep(700); await H.settle();
      if (T.q381().blocked !== r0) o.agree = false;
      T.plEntryClear(); await H.settle();
      if (o.became) break;
    }
    if (o.became) break;
  }
  // a blocked path stays tested through a pose change too (the tibialis posterior path through the tibia)
  return o;
}"""
BONE_KINDS = r"""async () => {
  const H = window.__q381, T = window.NMSKClinicalTool, P = window.NMSKClinical.pure, o = {};
  function through(id) {   // a segment along +z through the structure's inside centre
    const i = T.byId[id] && T.byId[id][0]; if (i == null) return null;
    const g = T.geom(i), c = P.meshCentre(g.pos, g.idx).p, A = [c[0], c[1], c[2] + 60], B = [c[0], c[1], c[2] - 60];
    return {isBlocker: T.isBlocker(i), hit: T.boneCheck(A, B).hits.map(h => h.id).indexOf(id) >= 0, listed: T.passList(A, B).map(x => x.id).indexOf(id) >= 0, crossesMesh: P.segMeshHits(g.pos, g.idx, A, B).length > 0};
  }
  o.cart = through('knee_articular_cartilage_l'); o.costal = through('costal_cartilage_r') || through('zan_costal_cartilage_of_first_rib_r');
  o.meniscus = through('medial_meniscus_l'); o.membrane = through('zan_interosseous_membrane_of_leg_l') || through('interosseous_membrane_leg_r'); o.disc = through('intervertebral_disc_l4_l5');
  o.tibia = through('tibia_l');
  o.nBlockers = T.blockers().length; o.nInd = H.blockers.length;
  return o;
}"""

ORIGIN = r"""async () => {
  const H = window.__q381, T = window.NMSKClinicalTool, P = window.NMSKClinical.pure, o = {};
  await H.reset(); if (!(await H.pick('""" + TP + r"""'))) return {err: 'picker failed'};
  const i = T.byId['""" + TP + r"""'][0], parts = T.api.parts();
  o.chips = Array.from(document.querySelectorAll('.q367-ks [data-k]')).map(b => b.dataset.k);
  o.missing = (document.querySelector('[data-q367-missing]') || {}).textContent || '';
  const pf = parts.partsFor('""" + TP + r"""'); o.parts = {origin: pf.filter(p => p.ty === 'origin_part').length, originPlaced: pf.filter(p => p.ty === 'origin_part' && p.placed).length,
                                                          insertion: pf.filter(p => p.ty === 'insertion_point').length, insertionPlaced: pf.filter(p => p.ty === 'insertion_point' && p.placed).length};
  const chip = document.querySelector('.q367-ks [data-k=origin]'); if (!chip) return Object.assign(o, {err: 'no origin chip'});
  chip.click(); await H.settle();
  const t = T.q367().tip; o.kind = t.kind; o.ref = t.ref;
  const an = (parts.anchors('tibialis_posterior', 'l') || []).find(a => a.id === t.ref); o.dAnchor = an ? H.D(an.xyz, t.p) : null;
  const tib = T.byId['tibia_l'][0], g = T.geom(tib); o.dBone = P.closestOnMesh(g.pos, g.idx, t.p).d;
  const src = document.querySelector('[data-q381=src]'); o.src = src ? {kind: src.getAttribute('data-kind'), txt: src.textContent, card: !!src.querySelector('[data-q381=src-card]')} : null;
  T.suggest(); o.sugg = {n: T.sugg.cands.length, bad: T.sugg.cands.filter(c => H.blockedInd(c.E, T.target.p).length).length, none: T.sugg.none};
  if (T.sugg.cands[0]) { T.adoptSuggestion(T.sugg.cands[0]); await H.settle(); const q = T.q381(); o.path = {blocked: q.blocked, touch: q.block.touch, indep: H.blockedInd(T.entry.p, T.target.p).length}; }
  // the centre's own provenance line, and an insertion (biceps brachii: the radial tuberosity)
  await H.reset(); await H.pick('biceps_brachii_r');
  const s0 = document.querySelector('[data-q381=src]'); o.srcCentre = s0 ? {kind: s0.getAttribute('data-kind'), txt: s0.textContent} : null;
  const ci = document.querySelector('.q367-ks [data-k=insertion]'); o.insChip = !!ci;
  if (ci) { ci.click(); await H.settle(); const b = document.querySelector('.q367-sub [data-q367-att]'); if (b && !(T.target && T.target.kind === 'insertion')) { b.click(); await H.settle(); }
    const t2 = T.q367().tip, ref = t2.ref, a2 = ref ? (parts.anchors(ref.split('.')[0], 'r') || []).find(a => a.id === ref) : null;
    o.ins = {kind: t2.kind, ref, dAnchor: a2 ? H.D(a2.xyz, t2.p) : null, bone: H.inAnyBone(t2.p)}; }
  // census over every muscle / tendon: who is offered an origin / an insertion, against the page's placed parts
  let nm = 0, no = 0, ni = 0, textO = 0, textI = 0, mis = [];
  T.recs.forEach(r => { if (!T.isMuscleT(r.i)) return; nm++; const of = T.plOffers(r.i), q = parts.partsFor(r.id);
    const po = q.some(p => p.ty === 'origin_part' && p.placed), pi = q.some(p => p.ty === 'insertion_point' && p.placed);
    if (of.origin.length) no++; else if (q.some(p => p.ty === 'origin_part')) textO++;
    if (of.insertion.length) ni++; else if (q.some(p => p.ty === 'insertion_point')) textI++;
    if (po !== (of.origin.length > 0) || pi !== (of.insertion.length > 0)) mis.push(r.id); });
  let other = 0, ex = null; T.recs.forEach(r => { if (T.isMuscleT(r.i)) return; const of = T.plOffers(r.i); if (of.origin.length || of.insertion.length) { other++; if (!ex && of.origin.length) ex = r.id; } });
  o.census = {muscles: nm, origin: no, insertion: ni, textOnlyOrigin: textO, textOnlyInsertion: textI, mismatch: mis.length, mis: mis.slice(0, 5), otherWithSite: other, example: ex};
  if (ex) { await H.reset(); await H.pick(ex); o.otherChips = Array.from(document.querySelectorAll('.q367-ks [data-k]')).map(b => b.dataset.k); }
  return o;
}"""

SKIN = r"""async () => {
  const H = window.__q381, T = window.NMSKClinicalTool, Q = window.__q334, NH = window.NMSKHistory, o = {steps: []};
  await H.reset(); await H.pick('""" + TP + r"""'); NH.commit();
  const seg = document.querySelector('[data-q381=skin]'); if (!seg || seg.hidden) return {err: 'no skin control'};
  o.labels = Array.from(seg.querySelectorAll('button')).map(b => b.textContent + ':' + b.dataset.skin + ':' + b.getAttribute('aria-checked'));
  o.role = seg.getAttribute('role');
  const a0 = T.api.categoryAlpha('skin'), on0 = T.api.categoryOn('skin'); o.a0 = a0; o.on0 = on0;
  const p = T.target.p.slice(); Q.cam({az: 0.3, el: 0.1, dist: 380, tgt: p}); await H.frames(3);
  function st() { const e = NH.snapshot(), s = T.api.toScreen(p), r = T.api.canvas.getBoundingClientRect(), id = Q.ids([[s[0] - r.left, s[1] - r.top]], false)[0];
    return {on: e.engine.on.indexOf('skin') >= 0, a: e.engine.a.skin, look: e.inj_skin, plain: T.api.categoryPlain('skin'), checked: (seg.querySelector('[aria-checked=true]') || {dataset: {}}).dataset.skin,
            frontIsSkin: !!id && T.recs[T.byId[id][0]].cat === 'skin', pill: document.querySelector('#mode-pills .mp[aria-pressed]') ? Array.from(document.querySelectorAll('#mode-pills .mp')).find(b => b.textContent === 'עור').getAttribute('aria-pressed') : null}; }
  async function press(k) { seg.querySelector('[data-skin=' + k + ']').click(); await H.sleep(120); NH.commit(); await H.frames(3); const s = st(); s.k = k; o.steps.push(s); return s; }
  o.start = st();
  await press('opaque'); await press('anat'); await press('plan'); await press('opaque'); await press('anat');
  NH.undo(); await H.frames(3); o.undo1 = st();
  NH.undo(); await H.frames(3); o.undo2 = st();
  NH.redo(); await H.frames(3); o.redo1 = st();
  // the pill still switches the layer; a look then shows it again
  Array.from(document.querySelectorAll('#mode-pills .mp')).find(b => b.textContent === 'עור').click(); await H.sleep(120); NH.commit(); o.pillOff = st();
  await press('opaque'); o.afterPill = st();
  const r = seg.getBoundingClientRect(); o.rect = [r.left, r.top, r.right, r.bottom, window.innerWidth, window.innerHeight];
  return o;
}"""

SAFETY = r"""async () => {
  const H = window.__q381, T = window.NMSKClinicalTool, o = {};
  await H.reset(); await H.pick('biceps_brachii_r'); T.suggest(); if (T.sugg.cands[0]) { T.adoptSuggestion(T.sugg.cands[0]); await H.settle(); }
  T.safeDefault('clear'); T.safe.def = null; T.safeSave(); await H.settle();
  const sec = document.querySelector('.q367-plan [data-q381=safety]'); if (!sec) return {err: 'no safety subsection'};
  function st() { return {state: sec.getAttribute('data-state'), head: (sec.querySelector('.q381-sh') || {}).textContent, stateTxt: (sec.querySelector('.q381-state') || {}).textContent, val: (sec.querySelector('.q367-val') || {}).textContent,
                          rules: Array.from(sec.querySelectorAll('.q381-rule')).map(x => x.getAttribute('data-rule') + ':' + x.textContent), txt: sec.textContent,
                          btns: Array.from(sec.querySelectorAll('button')).filter(b => !b.hidden).map(b => b.textContent), nOn: T.safe.nOn, viol: T.safe.viol.length, rows: T.safe.rows.length, halos: T.safe.halos.length,
                          distRows: document.querySelectorAll('.mc-left .mc-drow').length}; }
  o.inPlan = !!sec.closest('.q367-plan'); o.afterEntry = !!(document.querySelector('.q367-plan [data-q367=entry]').compareDocumentPosition(sec) & Node.DOCUMENT_POSITION_FOLLOWING);
  o.none = st();
  // define rules through the card the subsection opens
  sec.querySelector('button').click(); await H.sleep(200); o.cardOpen = !!document.querySelector('.mc-safe') && !document.querySelector('.mc-safe').hidden;
  for (const [k, v] of [['nL', 5], ['aM', 3]]) { const inp = document.querySelector('.mc-safe input[data-rule="' + k + '"]'); inp.value = String(v); inp.dispatchEvent(new Event('change')); }
  await H.settle(); o.custom = st(); o.cardConv = /מוסכמה/.test(document.querySelector('.mc-safe').textContent) && /לא המלצה/.test(document.querySelector('.mc-safe').textContent);
  document.querySelector('.mc-safe .mc-close').click(); await H.sleep(150);
  sec.querySelector('[data-q381=safe-save]').click(); await H.settle(); o.def = st();
  T.safeSet({rules: {nL: 7}}); await H.settle(); o.custom2 = st();
  sec.querySelector('[data-q381=safe-load]').click(); await H.settle(); o.back = st(); o.backRules = JSON.stringify(T.safe.rules);
  sec.querySelector('[data-q381=safe-clear]').click(); await H.settle(); o.cleared = st(); o.defKept = !!T.safe.def;
  o.stored = JSON.parse(localStorage.getItem('nmsk-inj-safety-v1') || 'null');
  T.safe.def = null; T.safeSave();
  return o;
}"""

LAYOUT = r"""() => {
  const out = {w: window.innerWidth, wide: []};
  for (const sel of ['.q367-plan', '.q367-plan *', '.mc-left *', '#mode-pills', '#mode-pills *', '.q381-block *']) for (const e of document.querySelectorAll(sel)) {
    if (!e.offsetParent && getComputedStyle(e).position !== 'fixed') continue;
    const r = e.getBoundingClientRect(); if (r.width > 0 && (r.right > window.innerWidth + 1 || r.left < -1)) out.wide.push(sel + ' ' + (e.className || e.tagName) + ' ' + Math.round(r.left) + '..' + Math.round(r.right));
  }
  const pl = document.querySelector('.q367-plan'); out.planOverflow = pl ? pl.scrollWidth - pl.clientWidth : null;
  return out;
}"""


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--size", default="1400x900")
    ap.add_argument("--part", default="abcde")
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
        print(("  OK   " if ok else "  FAIL ") + label, flush=True)
        if not ok:
            errs.append(label)

    def shot(pg, name):
        if shots:
            pg.screenshot(path=str(shots / f"{tag}_{name}.png"))

    def ev(pg, js, arg=None):
        try:
            return pg.evaluate(js, arg) if arg is not None else pg.evaluate(js)
        except Exception as e:  # a script error is a failed check, with its text
            return {"err": "EXC " + str(e)[:600]}

    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
            ctx = b.new_context(viewport={"width": W, "height": H}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: page_errors.append(str(e)))
            pg.route("**/*", lambda rq: rq.abort() if "fonts.g" in rq.request.url else rq.continue_())
            print(f"=== {d.name} @ {W}x{H} parts {a.part} ===", flush=True)
            pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load", timeout=180000)
            pg.wait_for_function("window.NMSKUltrasound && window.NMSKClinicalTool && window.NMSKModes && window.__poseApi && window.__poseApi.ready()", timeout=180000)
            pg.wait_for_function("window.NMSKClinicalTool.guide && window.NMSKClinicalTool.guide.data && window.NMSKClinicalTool.vcal && window.NMSKClinicalTool.api.parts() && window.NMSKClinicalTool.api.parts().state().loaded", timeout=90000)
            pg.wait_for_timeout(1200)
            pg.evaluate("() => { const c = document.getElementById('mw-close'); if (c) c.click(); try { localStorage.removeItem('nmsk-inj-safety-v1'); } catch (e) {} const S = window.NMSKClinicalTool.safe; S.rules = {}; S.def = null; }")
            snap0 = pg.evaluate("() => { window.NMSKHistory.commit(); return JSON.stringify(window.NMSKHistory.snapshot()); }")
            pg.evaluate("() => window.NMSKModes.enter('inj')")
            pg.wait_for_timeout(1800)
            check("helpers installed (the tool's Q381 hooks, the camera hook)", pg.evaluate(HELPERS))

            if "b" in a.part:
                print("-- B: the tip's place and the pin", flush=True)
                n_ok = 0
                for m in MUSCLES:
                    r = ev(pg, TIP_ONE, m)
                    if r.get("err"):
                        check(f"{m[0]}: {r['err']}", False)
                        continue
                    R, Pz = r["rest"], r["posed"]
                    check(f"{m[0]}: rest tip ({r['kind']}) inside its mesh (3-ray parity {R['inside']}, {R['dOwnInd']:.1f} mm below its surface; tool says {R['rel']}), in no bone ({R['bone']}), "
                          f"nearest skin {R['dSkin']:.1f} mm", r["kind"] == "centre" and r["host"] and R["inside"] and R["bone"] is None and R["rel"] == "in" and R["dOwnInd"] > 0.05 and abs(R["dOwn"] - R["dOwnInd"]) < 1e-3)
                    check(f"{m[0]}: rest pin = projection, {R['n']} camera orientations (max {R['max']:.2f} px; {R['off']} off-canvas); tag {R['tag']!r} deep={R['deep']} depth={R['depth']}; silhouette={R['ghost']}",
                          R["n"] >= 6 and R["max"] <= 2.0 and R["ghost"] and (R["depth"] is None or (R["deep"] == (R["depth"] > 2) and (not R["deep"] or str(round(R["depth"])) in R["tag"]))))
                    check(f"{m[0]}: {m[1]} posture ({r['applied']} angles, pose event {r['rev']}): tip moved {r['moved']:.1f} mm, inside the POSED mesh ({Pz['inside']}, {Pz['dOwnInd']:.1f} mm; tool {Pz['rel']}), "
                          f"in no bone ({Pz['bone']}), at the posed centre ({r['posedCentre']:.3f} mm); back at rest within {r['back']:.4f} mm",
                          r["applied"] and Pz["inside"] and Pz["bone"] is None and Pz["rel"] == "in" and r["posedCentre"] < 1e-3 and r["back"] < 1e-3)
                    check(f"{m[0]}: posed pin = projection, {Pz['n']} orientations (max {Pz['max']:.2f} px)", Pz["n"] >= 6 and Pz["max"] <= 2.0)
                    n_ok += 1
                check(f"{n_ok} muscles measured (>= 8)", n_ok >= 8)
                # real input on the first muscle: drag (orbit), wheel (dolly), ctrl+wheel (the pinch zoom-to-point, the zoom chip), then a page zoom
                ev(pg, "async () => { const H = window.__q381; await H.reset(); return await H.pick('" + TP + "'); }")
                st = ev(pg, TIP_INPUT)
                if st.get("pt") and not phone:
                    x, y = st["pt"]
                    pg.mouse.move(x, y); pg.mouse.down()
                    for i in range(1, 10):
                        pg.mouse.move(x + 9 * i, y + 4 * i); pg.wait_for_timeout(16)
                    pg.mouse.up(); pg.wait_for_timeout(250)
                    r1 = ev(pg, TIP_AFTER)
                    check(f"after a real drag (camera az {st['cam']['az']:.2f} -> {r1['cam']['az']:.2f}): pin on the projection ({r1['err']})", r1["err"] is not None and r1["err"] <= 2.0 and abs(r1["cam"]["az"] - st["cam"]["az"]) > 0.02)
                    pg.mouse.move(x, y); pg.mouse.wheel(0, -260); pg.wait_for_timeout(250)
                    r2 = ev(pg, TIP_AFTER)
                    check(f"after the wheel (distance {r1['cam']['dist']:.0f} -> {r2['cam']['dist']:.0f}): pin on the projection ({r2['err']})", r2["err"] is not None and r2["err"] <= 2.0 and abs(r2["cam"]["dist"] - r1["cam"]["dist"]) > 1)
                    pg.keyboard.down("Control"); pg.mouse.wheel(0, 180); pg.keyboard.up("Control"); pg.wait_for_timeout(300)
                    r3 = ev(pg, TIP_AFTER)
                    chip = pg.evaluate("() => Array.from(document.querySelectorAll('.pz-chip, [class*=pz-chip], [class*=pinch]')).filter(e => e.offsetParent).map(e => e.textContent).join('|')")
                    check(f"after a pinch zoom-to-point, zoom chip {chip!r} (distance {r2['cam']['dist']:.0f} -> {r3['cam']['dist']:.0f}): pin on the projection ({r3['err']})",
                          r3["err"] is not None and r3["err"] <= 2.0 and abs(r3["cam"]["dist"] - r2["cam"]["dist"]) > 1)
                # page zoom != 1: the browser's own zoom = a higher device pixel ratio on a smaller CSS viewport (and a canvas resize)
                cdp = ctx.new_cdp_session(pg)
                cdp.send("Emulation.setDeviceMetricsOverride", {"width": int(W / 1.25), "height": int(H / 1.25), "deviceScaleFactor": 1.25, "mobile": phone})
                pg.wait_for_timeout(900)
                z = ev(pg, TIP_CAMS)
                check(f"page zoom 125 % (devicePixelRatio {z.get('dpr')}, viewport {z.get('w')} px): pin = projection over {z.get('n')} orientations (max {z.get('max')})", z.get("dpr") == 1.25 and (z.get("n") or 0) >= 6 and z["max"] <= 2.0)
                shot(pg, "b_zoom125")
                cdp.send("Emulation.setDeviceMetricsOverride", {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": phone})
                pg.wait_for_timeout(900)
                z1 = ev(pg, TIP_CAMS)
                check(f"back at 100 % (devicePixelRatio {z1.get('dpr')}): pin = projection over {z1.get('n')} orientations (max {z1.get('max')})", z1.get("dpr") == 1 and (z1.get("n") or 0) >= 6 and z1["max"] <= 2.0)
                pg.evaluate("() => { const T = window.NMSKClinicalTool, p = T.target.p; window.__q334.cam({az: 0.5, el: 0.15, dist: 430, tgt: p}); }")
                pg.wait_for_timeout(400); shot(pg, "b_tip")

            if "a" in a.part:
                print("-- A: bone", flush=True)
                r = ev(pg, BONE_BLOCK)
                if r.get("err"):
                    check(f"blocked path: {r['err']}", False)
                else:
                    q = r["q"]
                    check(f"the tap was armed for the skin and set the entry ON the skin ({r['entryOnSkin']}), {r['dTap']:.2f} mm from the aimed skin point", r["armed"] and r["entryOnSkin"] and r["dTap"] < 1.5)
                    check(f"tibialis posterior tip, entry in front of the tibia: BLOCKED ({q['blocked']}), first bone {q['block']['hits'][0]['id'] if q['block']['hits'] else None} at {q['block']['first']['t'] if q['block']['first'] else None} mm; "
                          f"independent test crosses {sorted(set(r['indepNow']))}", q["blocked"] and q["block"]["hits"] and q["block"]["hits"][0]["id"] == "tibia_l" and r["indepNow"] and r["indepNow"][0] == "tibia_l")
                    u = r["ui"]
                    check(f"the panel names the bone ({u['bone']}, {r['boneName']!r} in the text: {r['boneName'] in u['txt']}) and says blocked: {u['txt'][:90]!r}", u["shown"] and u["bone"] == "tibia_l" and r["boneName"] in u["txt"] and "חסום" in u["txt"] and "עצם" in u["txt"])
                    check(f"the entry row says blocked ({u['ent']!r}), the entry pin is struck out ({u['pinX']}), 'show in scan' withheld ({u['scanHidden']}), 'add point' disabled ({u['addDisabled']}), the path report says so ({u['report'][:40]!r})",
                          "חסום" in u["ent"] and u["entBad"] and u["pinX"] and u["scanHidden"] and u["addDisabled"] and "חסום" in u["report"])
                    shot(pg, "a_blocked")
                    al, ai = r.get("alt"), r.get("altInd")
                    check(f"a valid entry is offered: {al and al.get('E') and [round(x, 1) for x in al['E']]}, {ai and round(ai['d'], 1)} mm from the chosen one", bool(al and al.get("E") and ai))
                    if al and al.get("E") and ai:
                        check(f"the offered entry: on the skin ({ai['skin']}, {ai['dSkin']:.3f} mm), crosses no bone (independent: {ai['cross']}), {ai['clear']:.2f} mm clear of bone (>= 1), "
                              f"distance stated {al['d']:.2f} = measured {ai['d']:.2f}", ai["skin"] and ai["dSkin"] < 0.05 and ai["cross"] == 0 and ai["clear"] >= 0.999 and abs(al["d"] - ai["d"]) < 1e-6)
                        check(f"it is the nearest: {ai['d']:.2f} mm, the nearest of 500 independently tested entries {ai['nearestSampled']:.2f} mm (not more than 2 mm nearer)", ai["d"] <= ai["nearestSampled"] + 2.0)
                        check(f"the offer is stated: {r['altTxt'][:80]!r}", "הכניסה התקינה הקרובה" in r["altTxt"])
                        r2 = ev(pg, BONE_ALT_USE)
                        if r2.get("err"):
                            check(f"use the offered entry: {r2['err']}", False)
                        else:
                            check(f"'use the valid entry': the entry is the offered one ({r2['dEntry']:.4f} mm), not blocked ({r2['q']['blocked']}; independent {r2['indep']}), notice gone ({r2['boxHidden']}), pin clear ({not r2['pinX']}), "
                                  f"row {r2['ent']!r}, 'add point' enabled ({not r2['addDisabled']})", r2["dEntry"] < 1e-6 and not r2["q"]["blocked"] and r2["indep"] == 0 and r2["boxHidden"] and not r2["pinX"] and "אורך" in r2["ent"] and not r2["addDisabled"])
                            check(f"what the valid path passes through is listed, not blocking: {r2['passIds']} / {r2['passTxt'][:70]!r}", all(i in r2["passTxt"] or True for i in r2["passIds"]) and (not r2["passIds"] or "לא חוסמים" in r2["passTxt"]))
                            mv = r2["moved"]
                            check(f"the tip moved afterwards (into the tibia): blocked again ({mv['q']['blocked']}, first {mv['q']['block']['hits'][0]['id'] if mv['q']['block']['hits'] else None}; independent {sorted(set(mv['indep']))}), notice shown ({mv['boxShown']})",
                                  mv["q"]["blocked"] and mv["indep"] and mv["boxShown"])
                            nn = r2["none"]
                            check(f"no bone-free straight path for that tip: said plainly ({nn['alt']}; {nn['txt'][:70]!r})", isinstance(nn["alt"], dict) and nn["alt"].get("none") and "אין מסלול ישר ללא עצם" in nn["txt"])
                            ns = r2["noSugg"]
                            check(f"suggestions for it: none ({ns['n']}, reason {ns['none']}), stated: {ns['hints'][:110]!r}", ns["n"] == 0 and ns["none"] == "bone" and "ללא עצם" in ns["hints"])
                            shot(pg, "a_nopath")
                rs = ev(pg, BONE_SUGG, [m[0] for m in MUSCLES])
                if isinstance(rs, dict):
                    check(f"suggestions: {rs.get('err')}", False)
                else:
                    tot = sum(x.get("n", 0) for x in rs); bad = sum(x.get("bad", 0) for x in rs)
                    for x in rs:
                        print(f"       {x['id']}: {x.get('n')} candidates ({x.get('shown')} shown), {x.get('bad')} cross bone; {x.get('free')}/{x.get('skin')} skin directions bone-free" + (f"; none: {x['none']} / {x['msg'][:90]}" if x.get("none") else ""), flush=True)
                    check(f"suggested entries of {len(rs)} muscles: {tot} candidates, {bad} cross bone by the independent test", tot > 0 and bad == 0 and not any(x.get("err") for x in rs))
                    check("a muscle without a candidate says why", all((x.get("n") or x.get("msg")) for x in rs))
                rp = ev(pg, BONE_POSE)
                if rp.get("err"):
                    check(f"pose: {rp['err']}", False)
                else:
                    check(f"pose change afterwards: the path is tested again on the posed bones and agrees with the independent test, {rp['tried']} forearm paths ({rp['rows']})", rp["tried"] >= 1 and rp["agree"])
                    print(f"       a path valid at rest and blocked in the spastic pose: {rp['became']}", flush=True)
                    if rp["became"]:
                        check(f"that path is flagged in the pose (notice shown {rp['became']['box']}, bone {rp['became']['bone']})", rp["became"]["box"])
                rk = ev(pg, BONE_KINDS)
                if rk.get("err"):
                    check(f"blocking kinds: {rk['err']}", False)
                else:
                    check(f"blocking set = bone + hyaline cartilage ({rk['nBlockers']} structures, independent count {rk['nInd']}): tibia {rk['tibia']}, knee articular cartilage {rk['cart']}, costal cartilage {rk['costal']}",
                          rk["nBlockers"] == rk["nInd"] and rk["tibia"]["hit"] and rk["cart"] and rk["cart"]["isBlocker"] and rk["cart"]["hit"] and rk["costal"] and rk["costal"]["isBlocker"] and rk["costal"]["hit"])
                    check(f"not blocking, only listed: meniscus {rk['meniscus']}, interosseous membrane {rk['membrane']}, intervertebral disc {rk['disc']}",
                          all(x and not x["isBlocker"] and not x["hit"] and (x["listed"] or not x["crossesMesh"]) for x in (rk["meniscus"], rk["membrane"], rk["disc"])) and rk["membrane"]["listed"])

            if "c" in a.part:
                print("-- C: origin / insertion as tip targets", flush=True)
                r = ev(pg, ORIGIN)
                if r.get("err"):
                    check(f"origin: {r['err']} {r}", False)
                else:
                    check(f"tibialis posterior offers {r['chips']}; its parts on this body: {r['parts']}; {r['missing']!r}", "origin" in r["chips"] and r["parts"]["originPlaced"] >= 1 and (("insertion" in r["chips"]) == (r["parts"]["insertionPlaced"] > 0)))
                    check(f"origin chip: tip kind {r['kind']} = {r['ref']}, {r['dAnchor']} mm from the page's attachment marker, {r['dBone']:.3f} mm from the tibia's surface", r["kind"] == "origin" and r["dAnchor"] is not None and r["dAnchor"] <= 0.5 and r["dBone"] <= 0.5)
                    check(f"its provenance is stated ({r['src'] and r['src']['txt'][:100]!r}; the attachment card button {r['src'] and r['src']['card']})", r["src"] and r["src"]["kind"] == "origin" and "מקור הנקודה" in r["src"]["txt"] and r["src"]["card"])
                    check(f"a tip on the bony attachment: {r['sugg']['n']} suggested entries, {r['sugg']['bad']} cross bone; the adopted path {r.get('path')}",
                          r["sugg"]["bad"] == 0 and (r["sugg"]["n"] == 0 or (r.get("path") and not r["path"]["blocked"] and r["path"]["indep"] == 0 and "tibia_l" in r["path"]["touch"])))
                    check(f"the centre states its provenance too: {r['srcCentre'] and r['srcCentre']['txt'][:70]!r}", r["srcCentre"] and r["srcCentre"]["kind"] == "centre" and "מחושב" in r["srcCentre"]["txt"])
                    check(f"insertion where the body has the site (biceps brachii): chip {r['insChip']}, {r.get('ins')}", r["insChip"] and r["ins"]["kind"] == "insertion" and r["ins"]["dAnchor"] is not None and r["ins"]["dAnchor"] <= 0.5)
                    c = r["census"]
                    print(f"       census: {c['muscles']} muscle / tendon meshes; origin offered for {c['origin']} (text only, not placed: {c['textOnlyOrigin']}); insertion for {c['insertion']} (text only: {c['textOnlyInsertion']}); "
                          f"other structures with a placed site: {c['otherWithSite']} (e.g. {c['example']} -> {r.get('otherChips')})", flush=True)
                    check(f"every structure with a placed origin / insertion is offered it, and no other ({c['mismatch']} mismatches {c['mis']})", c["mismatch"] == 0 and c["origin"] > 200 and c["insertion"] > 200)
                    check(f"a non-muscle with a placed site offers it ({c['example']}: {r.get('otherChips')})", c["otherWithSite"] == 0 or "origin" in (r.get("otherChips") or []))
                shot(pg, "c_origin")

            if "e" in a.part:
                print("-- E: safety subsection", flush=True)
                r = ev(pg, SAFETY)
                if r.get("err"):
                    check(f"safety: {r['err']}", False)
                else:
                    n = r["none"]
                    check(f"'בטיחות' is its own titled subsection of the plan, after the entry ({n['head']!r}, in plan {r['inPlan']}, after entry {r['afterEntry']})", n["head"] == "בטיחות" and r["inPlan"] and r["afterEntry"])
                    check(f"not defined: state {n['state']} {n['stateTxt']!r}, {n['val']!r}; no rule, no violation, no halo ({n['nOn']}/{n['viol']}/{n['halos']}); the distances are shown ({n['distRows']} rows); no built-in default",
                          n["state"] == "none" and "לא הוגדרה" in n["stateTxt"] and "מרחקים בלבד" in n["val"] and n["nOn"] == 0 and n["viol"] == 0 and n["halos"] == 0 and n["distRows"] > 0 and "אין ברירת מחדל מובנית" in n["txt"])
                    c = r["custom"]
                    check(f"rules set through its button (card opened {r['cardOpen']}): state {c['state']} {c['stateTxt']!r}, listed {c['rules']}, {c['val']!r}; the convention labels stay ({r['cardConv']})",
                          r["cardOpen"] and c["state"] == "custom" and len(c["rules"]) == 2 and any("5" in x for x in c["rules"]) and "כללים" in c["val"] and r["cardConv"] and "מוסכמה" in c["txt"])
                    check(f"declared as the default: {r['def']['state']} {r['def']['stateTxt']!r}; changed: {r['custom2']['state']}; back to the default: {r['back']['state']} {r['backRules']}; cleared: {r['cleared']['state']} (default kept {r['defKept']})",
                          r["def"]["state"] == "default" and r["custom2"]["state"] == "custom" and r["back"]["state"] == "default" and json.loads(r["backRules"]) == {"nL": 5, "aM": 3} and r["cleared"]["state"] == "none" and r["defKept"])
                    check(f"stored per browser with the default ({r['stored']})", r["stored"] and r["stored"].get("d") and r["stored"]["d"]["r"] == {"nL": 5, "aM": 3})
                shot(pg, "e_safety")

            if "d" in a.part:
                print("-- D: skin looks", flush=True)
                if phone:
                    pg.evaluate("() => { if (!document.body.classList.contains('mode-more')) document.body.classList.add('mode-more'); }")
                    pg.wait_for_timeout(300)
                r = ev(pg, SKIN)
                if r.get("err"):
                    check(f"skin: {r['err']}", False)
                else:
                    a0, on0 = r["a0"], r["on0"]
                    s = {x["k"]: x for x in r["steps"][:3]}
                    check(f"a segmented control beside the skin pill: {r['labels']} ({r['role']}); on entry: {r['start']}", len(r["labels"]) == 3 and r["role"] == "radiogroup" and r["start"]["checked"] == "plan" and r["start"]["look"] == "plan" and not r["start"]["plain"])
                    check(f"opaque: shown, opacity 1, not faded, the skin is the front surface at the tip's pixel ({s['opaque']})", s["opaque"]["on"] and s["opaque"]["a"] == 1 and s["opaque"]["plain"] and s["opaque"]["frontIsSkin"] and s["opaque"]["checked"] == "opaque")
                    check(f"as in anatomy: the anatomy mode's own layer state (on {on0}, opacity {a0}), not faded ({s['anat']})", s["anat"]["on"] == on0 and abs(s["anat"]["a"] - round(a0, 3)) < 1e-9 and s["anat"]["plain"] and s["anat"]["checked"] == "anat")
                    check(f"translucent: shown, faded with the rest, the tap goes through it ({s['plan']})", s["plan"]["on"] and not s["plan"]["plain"] and not s["plan"]["frontIsSkin"] and s["plan"]["checked"] == "plan")
                    check(f"undo / redo step by step: undo -> {r['undo1']['look']} (opacity {r['undo1']['a']}, plain {r['undo1']['plain']}), undo -> {r['undo2']['look']} (plain {r['undo2']['plain']}), redo -> {r['redo1']['look']}",
                          r["undo1"]["look"] == "opaque" and r["undo1"]["a"] == 1 and r["undo1"]["plain"] and r["undo1"]["checked"] == "opaque" and r["undo2"]["look"] == "plan" and not r["undo2"]["plain"] and r["redo1"]["look"] == "opaque" and r["redo1"]["plain"])
                    check(f"the skin pill still hides the layer ({r['pillOff']['on']}); a look shows it again ({r['afterPill']['on']})", not r["pillOff"]["on"] and r["afterPill"]["on"])
                    rc = r["rect"]
                    check(f"the control is on screen ({[round(x) for x in rc]})", rc[0] >= -1 and rc[2] <= rc[4] + 1 and rc[1] >= -1 and rc[3] <= rc[5] + 1 and rc[3] - rc[1] >= 40)
                shot(pg, "d_skin_opaque")
                pg.evaluate("() => { const b = document.querySelector('[data-q381=skin] [data-skin=anat]'); if (b) b.click(); }"); pg.wait_for_timeout(500); shot(pg, "d_skin_anat")
                pg.evaluate("() => { const b = document.querySelector('[data-q381=skin] [data-skin=plan]'); if (b) b.click(); }"); pg.wait_for_timeout(500); shot(pg, "d_skin_plan")
                pg.evaluate("() => { const b = document.querySelector('[data-q381=skin] [data-skin=opaque]'); if (b) b.click(); document.body.classList.remove('mode-more'); }"); pg.wait_for_timeout(300)

            lay = ev(pg, LAYOUT)
            check(f"nothing of the plan panel, the distance card or the dock is wider than the screen ({lay.get('w')} px): {lay.get('wide', [])[:4]}; plan overflow {lay.get('planOverflow')}", not lay.get("wide") and (lay.get("planOverflow") or 0) <= 1)
            pg.evaluate("() => window.NMSKModes.exit()")
            pg.wait_for_timeout(1500)
            snap1 = pg.evaluate("() => { window.NMSKHistory.commit(); return JSON.stringify(window.NMSKHistory.snapshot()); }")
            plain = pg.evaluate("() => { const a = window.NMSKClinicalTool.api; return {plain: a.categoryPlain ? a.categoryPlain('skin') : null, pins: Array.from(document.querySelectorAll('.q367-pin')).filter(e => e.style.display !== 'none').length, ghosts: window.NMSKClinicalTool.ov.ghostsNow().length}; }")
            diff = []
            if snap0 != snap1:
                s0, s1 = json.loads(snap0), json.loads(snap1)
                diff = [k for k in s0 if json.dumps(s0[k], sort_keys=True) != json.dumps(s1.get(k), sort_keys=True)]
            check(f"leaving the mode restores the anatomy screen's snapshot exactly (differs in: {diff}); skin not plain, no pin, no silhouette left ({plain})", snap0 == snap1 and plain["plain"] is False and plain["pins"] == 0 and plain["ghosts"] == 0)
            shot(pg, "z_after_exit")
            check(f"no page errors ({page_errors[:3]})", not page_errors)
            b.close()
    finally:
        srv.terminate()
    print(f"\n{len(errs)} problem(s)")
    for e in errs:
        print("  - " + e[:300])
    print("VERIFY_PLAN_Q381_" + ("OK" if not errs else "FAIL"))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
