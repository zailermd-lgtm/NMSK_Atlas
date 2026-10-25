/* Learn (Q283): pick a muscle, one of its parts, a named muscle group or a motion (by text, or by clicking the model) and
   the page highlights it and fades everything else (the Q227/Q232 selection controller's own "highlight" / "fade" display
   states and fade-opacity setter, reused as-is), turns the camera to it (api.focus), rotates the figure a half or full turn
   either way (api.orbit, a plain camera azimuth step on each engine), and simulates its cited action by driving the Q241
   pose rig (api.pose().apply(), the rig's own joints and normal ranges of motion -- no second kinematics path).
   Everything shown is read from the page's nmsk-learn block, built by scripts/anatomy/q283/build_learn.py from the
   project's cited data: names, attachments, innervation and actions verbatim from data/muscles, the action -> joint
   derivation table data/anatomy/muscle_actions_q283.json (every row quotes its source) and the named groups table
   data/anatomy/muscle_groups_q283.json. A motion is animated only where a cited action maps onto a joint of the rig; any
   other case says why. One controller for both viewers; the engine is reached only through api (anatomyApi()). */
function NMSKLearn(api){
  "use strict";
  var $ = function(id){ return document.getElementById(id); };
  var STUB = {open:function(){}, openFor:function(){ return false; }, state:function(){ return {ready:false}; }};
  var D = null;
  try { var tb = $("nmsk-learn"); D = tb ? JSON.parse(tb.textContent) : null; } catch (err){ D = null; }
  var panel = $("ln-panel");
  if (!panel || !D || !D.m) return STUB;
  var M = D.m, recs = api.list(), btn = null;
  var SPINE = {lumbar:1, thoracic:1, cervical:1};

  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"}[c]; }); }
  function say(id, msg){ var e = $(id); if (e) e.textContent = msg || ""; }
  function cap(s){ s = String(s || ""); return s.charAt(0).toUpperCase() + s.slice(1); }
  function prettyBone(b){ return String(b || "").replace(/_(r|l)$/, "").replace(/_/g, " "); }

  /* ---------- page structure -> muscle / part ---------- */
  var CIX = {};
  Object.keys(M).forEach(function(b){ (M[b].cp || []).forEach(function(c){ (CIX[c.c] = CIX[c.c] || []).push([b, c.c]); }); });
  function hasPart(b, c){ return (M[b].cp || []).some(function(x){ return x.c === c; }); }
  function resolve(id){
    var s = String(id || "").replace(/^zan_/, "");
    if (M[s]) return {b:s, side:null, c:null};
    var mm = /^(.*?)_(r|l)(?:_(.+))?$/.exec(s); if (!mm) return null;
    var b = mm[1], side = mm[2], rest = mm[3] || null;
    if (M[b]){
      if (rest && hasPart(b, rest)) return {b:b, side:side, c:rest};
      if (rest && /tendon|fascia|bursa|branch|sheath|aponeur/.test(rest)) return null;
      return {b:b, side:side, c:null};
    }
    var hit = CIX[b];
    if (hit && hit.length === 1 && !rest) return {b:hit[0][0], side:side, c:hit[0][1]};
    return null;
  }
  var IDX = [], BYB = {};
  recs.forEach(function(r){
    if (r.cat && r.cat !== "muscle") return;
    var x = resolve(r.id); if (!x) return;
    IDX[r.i] = x; (BYB[x.b] = BYB[x.b] || []).push(r);
  });
  function recsFor(b, side, c){
    var all = (BYB[b] || []).filter(function(r){ var x = IDX[r.i]; return !side || !x.side || x.side === side; });
    if (!c) return all;
    var part = all.filter(function(r){ return IDX[r.i].c === c; });
    return part.length ? part : all;
  }
  function sidesOf(b){ var s = {}; (BYB[b] || []).forEach(function(r){ s[IDX[r.i].side || "m"] = 1; }); return Object.keys(s).sort(function(a, z){ return a === "r" ? -1 : z === "r" ? 1 : 0; }); }

  /* ---------- motion labels ---------- */
  var JN = {hip:"Hip", knee:"Knee", ankle:"Ankle", subtalar:"Foot (subtalar)", shoulder:"Shoulder", elbow:"Elbow", forearm:"Forearm", wrist:"Wrist",
            thumb_cmc:"Thumb CMC", thumb_mcp:"Thumb MCP", thumb_ip:"Thumb IP", t1_mtp:"Great toe MTP", t1_ip:"Great toe IP",
            lumbar:"Lumbar spine", thoracic:"Thoracic spine", cervical:"Head and neck"};
  var DN = {flex:["flexion", "extension"], abd:["abduction", "adduction"], rot:["internal rotation", "external rotation"], sup:["supination", "pronation"],
            dev:["radial deviation", "ulnar deviation"], dp:["dorsiflexion", "plantarflexion"], inv:["inversion", "eversion"]};
  function jointName(js){
    var j0 = js[0], m = /^([ft])(\d)_(mcp|pip|dip|mtp)$/.exec(j0);
    if (!m || JN[j0]) return JN[j0] || j0;
    var digits = js.map(function(j){ return +j.charAt(1); }), dtxt = digits.length > 1 && digits[digits.length - 1] - digits[0] === digits.length - 1 ? digits[0] + "-" + digits[digits.length - 1] : digits.join(", ");
    return (m[1] === "f" ? "Finger " : "Toe ") + m[3].toUpperCase() + " (digit" + (digits.length > 1 ? "s " : " ") + dtxt + ")";
  }
  function mvLabel(mv){
    var js = Array.isArray(mv[0]) ? mv[0] : [mv[0]], k = mv[1], pos = mv[2] > 0, w;
    if (SPINE[js[0]] && k === "lat") w = pos ? "lateral flexion to its own side" : "lateral flexion to the other side";
    else if (SPINE[js[0]] && k === "rot") w = pos ? "rotation to its own side" : "rotation to the other side";
    else if (js[0] === "thumb_cmc" && k === "abd") w = pos ? "palmar abduction" : "adduction";
    else w = (DN[k] || [k + " +", k + " -"])[pos ? 0 : 1];
    return jointName(js) + " " + w;
  }
  function mvKey(mv){ return (Array.isArray(mv[0]) ? mv[0].join(",") : mv[0]) + "|" + mv[1] + "|" + mv[2]; }
  function rowLabel(row){ return cap(row.mv.map(mvLabel).join(" + ").toLowerCase()); }
  /* motions (for "hip flexion"-style searches): every distinct mapped motion and the muscles whose cited actions include it */
  var MOT = {};
  Object.keys(M).forEach(function(b){
    (M[b].mv || []).forEach(function(row){ row.mv.forEach(function(mv){ var k = mvKey(mv); (MOT[k] = MOT[k] || {mv:mv, label:mvLabel(mv), b:{}}).b[b] = 1; }); });
  });

  /* ---------- state ---------- */
  var cur = null, lastSid = null, poll = 0, anim = null, rot = null;
  function opac(){ return (+$("ln-op").value || 0) / 100; }

  /* ---------- search ---------- */
  function renderSearch(){
    var q = $("ln-q").value.trim().toLowerCase(), box = $("ln-res"), out = [];
    box.innerHTML = "";
    if (!q) return;
    Object.keys(BYB).forEach(function(b){
      var m = M[b], hay = (m.n + " " + m.ta + " " + b.replace(/_/g, " ")).toLowerCase();
      if (hay.indexOf(q) >= 0) sidesOf(b).forEach(function(s){ out.push({k:"m", b:b, side:s === "m" ? null : s, c:null, t:m.n + (s !== "m" ? " (" + s + ")" : ""), kind:"muscle"}); });
      (m.cp || []).forEach(function(c){
        if (c.n.toLowerCase().indexOf(q) >= 0 && hay.indexOf(q) < 0) sidesOf(b).forEach(function(s){ out.push({k:"m", b:b, side:s === "m" ? null : s, c:c.c, t:c.n + " -- part of " + m.n + (s !== "m" ? " (" + s + ")" : ""), kind:"part"}); });
      });
    });
    (D.groups || []).forEach(function(g){
      if ((g.name + " " + (g.ta || "") + " " + g.id.replace(/_/g, " ")).toLowerCase().indexOf(q) >= 0 && g.members.some(function(b){ return BYB[b]; }))
        out.push({k:"g", g:g, t:g.name, kind:"group"});
    });
    Object.keys(MOT).forEach(function(k){
      var mo = MOT[k], present = Object.keys(mo.b).filter(function(b){ return BYB[b]; });
      if (present.length && mo.label.toLowerCase().indexOf(q) >= 0) out.push({k:"f", key:k, t:mo.label + " -- muscles with this cited action", kind:"motion"});
    });
    if (!out.length){ box.innerHTML = '<p class="ln-hint">Nothing on this page matches.</p>'; return; }
    out.slice(0, 30).forEach(function(it){
      var b = document.createElement("button"); b.type = "button";
      b.innerHTML = esc(it.t) + '<span class="ln-kind">' + esc(it.kind) + "</span>";
      b.onclick = function(){ choose(it); };
      box.appendChild(b);
    });
  }

  /* ---------- highlight + camera ---------- */
  function highlight(list, quiet){
    var sel = api.selection ? api.selection() : null;
    if (!list.length){ say("ln-msg", "Not modelled on this page."); return 0; }
    if (sel && sel.markIds && sel.setGroup){
      var ids = []; list.forEach(function(r){ if (ids.indexOf(r.id) < 0) ids.push(r.id); });
      sel.markIds(ids, true, true, true);
      sel.setGroup("sel", "hl", true); sel.setGroup("oth", "fade", true);
      if (sel.setFade) sel.setFade(opac(), true);
    } else if (!quiet) say("ln-msg", "This page has no selection controller: nothing can be highlighted.");
    var lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
    list.forEach(function(r){ for (var k = 0; k < 3; k++){ lo[k] = Math.min(lo[k], r.bmin[k]); hi[k] = Math.max(hi[k], r.bmax[k]); } });
    var mid = [0, 1, 2].map(function(k){ return (lo[k] + hi[k]) / 2; }), ext = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
    if (api.focus) api.focus(mid, Math.max(160, ext * 1.6));
    return list.length;
  }

  /* ---------- choosing ---------- */
  function choose(it){
    stopAnim();
    $("ln-res").innerHTML = "";
    cur = it;
    $("ln-card").hidden = false;
    var list;
    if (it.k === "m"){ $("ln-q").value = M[it.b].n; list = recsFor(it.b, it.side, it.c); }
    else if (it.k === "g"){ $("ln-q").value = it.g.name; list = []; it.g.members.forEach(function(b){ list = list.concat(recsFor(b, null, null)); }); }
    else { var mo = MOT[it.key]; $("ln-q").value = mo.label; list = []; Object.keys(mo.b).forEach(function(b){ list = list.concat(recsFor(b, null, null)); }); }
    var n = highlight(list);
    say("ln-msg", n ? n + " structure" + (n === 1 ? "" : "s") + " highlighted, everything else at " + Math.round(opac() * 100) + " %." : "Not modelled on this page.");
    render();
  }
  function choosePart(c){ choose({k:"m", b:cur.b, side:cur.side, c:c}); }

  /* ---------- the card ---------- */
  function render(){
    var it = cur, title = $("ln-title"), parts = $("ln-parts"), info = $("ln-info");
    parts.innerHTML = ""; $("ln-acts").innerHTML = ""; say("ln-act-msg", "");
    if (it.k === "m"){
      var m = M[it.b], part = it.c ? (m.cp || []).filter(function(x){ return x.c === it.c; })[0] : null;
      title.innerHTML = esc(part ? part.n : m.n) + (it.side ? " <small>(" + esc(it.side) + ")</small>" : "") + (part ? " <small>part of " + esc(m.n) + "</small>" : m.ta ? " <small>" + esc(m.ta) + "</small>" : "");
      if ((m.cp || []).length){
        var all = document.createElement("button"); all.type = "button"; all.textContent = "Whole muscle"; all.setAttribute("aria-pressed", String(!it.c)); all.onclick = function(){ choosePart(null); }; parts.appendChild(all);
        m.cp.forEach(function(c){ var b = document.createElement("button"); b.type = "button"; b.textContent = c.n; b.setAttribute("aria-pressed", String(it.c === c.c)); b.onclick = function(){ choosePart(c.c); }; parts.appendChild(b); });
      }
      renderActsMuscle(m, it); info.innerHTML = infoMuscle(m, part);
    } else if (it.k === "g"){
      title.innerHTML = esc(it.g.name) + (it.g.ta ? " <small>" + esc(it.g.ta) + "</small>" : "");
      it.g.members.forEach(function(b){
        if (!BYB[b]) return;
        var x = document.createElement("button"); x.type = "button"; x.textContent = M[b].n; x.onclick = function(){ var s = sidesOf(b)[0]; choose({k:"m", b:b, side:s === "m" ? null : s, c:null}); }; parts.appendChild(x);
      });
      renderActsSet(it.g.members); info.innerHTML = infoGroup(it.g);
    } else {
      var mo = MOT[it.key];
      title.textContent = mo.label;
      Object.keys(mo.b).forEach(function(b){ if (!BYB[b]) return; var x = document.createElement("button"); x.type = "button"; x.textContent = M[b].n; x.onclick = function(){ var s = sidesOf(b)[0]; choose({k:"m", b:b, side:s === "m" ? null : s, c:null}); }; parts.appendChild(x); });
      renderActsList([{label:mo.label, mv:[mo.mv], quotes:Object.keys(mo.b).map(function(b){ return M[b].n; })}], "r");
      info.innerHTML = '<p>Every muscle on this page whose cited action (data/muscles, quoted in data/anatomy/muscle_actions_q283.json) includes <b>' + esc(mo.label.toLowerCase()) + "</b>. Pick one above for its own card.</p>";
    }
  }
  function partName(m, c){ var p = (m.cp || []).filter(function(x){ return x.c === c; })[0]; return p ? p.n : c; }
  function renderActsMuscle(m, it){
    var rows = (m.mv || []).filter(function(r){ return !it.c || !r.c || r.c === it.c; }), side = it.side || "r", box = $("ln-acts");
    if (!rows.length){
      box.innerHTML = '<p class="ln-hint">No motion to simulate: ' + esc((D.none_reasons || {})[m.nr] || "no cited action maps onto a joint of the pose rig") + ".</p>";
    } else {
      var items = rows.map(function(r){
        var cite = r.src && r.src.indexOf("cite:") === 0 ? (D.cites || {})[r.src.slice(5)] : null;
        return {label:rowLabel(r) + (r.c ? " -- " + partName(m, r.c) : ""), mv:r.mv, back:!!r.back, quote:r.q, note:r.note, cite:cite};
      });
      var whole = rows.filter(function(r){ return !r.c || r.c === it.c; });
      if (whole.length > 1) items.unshift({label:"All together" + (it.c ? " (" + partName(m, it.c) + ")" : ""), mv:merge(whole), all:true});
      renderActsList(items, side);
    }
    (m.na || []).forEach(function(x){
      if (it.c && x.c && x.c !== it.c) return;
      var p = document.createElement("p"); p.className = "ln-na";
      p.textContent = "Not animated" + (x.c ? " for " + partName(m, x.c) : "") + ": " + x.what + ". " + x.why;
      box.appendChild(p);
    });
  }
  function merge(rows){
    var seen = {}, out = [];
    rows.forEach(function(r){ r.mv.forEach(function(mv){
      var k = (Array.isArray(mv[0]) ? mv[0].join(",") : mv[0]) + "|" + mv[1];
      if (seen[k] === undefined){ seen[k] = mv[2]; out.push(mv); } else if (seen[k] !== mv[2]) out = out.filter(function(x){ return (Array.isArray(x[0]) ? x[0].join(",") : x[0]) + "|" + x[1] !== k; });
    }); });
    return out;
  }
  function renderActsSet(members){
    var agg = {}, order = [];
    members.forEach(function(b){ if (!BYB[b]) return; (M[b].mv || []).forEach(function(r){ r.mv.forEach(function(mv){ var k = mvKey(mv); if (!agg[k]){ agg[k] = {mv:mv, b:[]}; order.push(k); } if (agg[k].b.indexOf(M[b].n) < 0) agg[k].b.push(M[b].n); }); }); });
    if (!order.length){ $("ln-acts").innerHTML = '<p class="ln-hint">None of these muscles has a cited action that maps onto a joint of the pose rig.</p>'; return; }
    order.sort(function(a, z){ return agg[z].b.length - agg[a].b.length; });
    renderActsList(order.map(function(k){ return {label:mvLabel(agg[k].mv) + " -- " + agg[k].b.length + " muscle" + (agg[k].b.length === 1 ? "" : "s"), mv:[agg[k].mv], quotes:agg[k].b}; }), "r");
  }
  function renderActsList(items, side){
    var box = $("ln-acts");
    items.forEach(function(it, i){
      var w = document.createElement("div"); w.className = "ln-act";
      var b = document.createElement("button"); b.type = "button"; b.textContent = "▶ " + it.label; b.dataset.i = i;
      b.onclick = function(){ if (anim && anim.btn === b){ stopAnim(); return; } simulate(it.mv, side, it.back, b); };
      w.appendChild(b);
      if (it.quote){ var q = document.createElement("q"); q.textContent = it.quote + (it.cite ? " -- " + it.cite.citation + (it.cite.doi ? ", doi:" + it.cite.doi : "") : ""); w.appendChild(q); }
      if (it.quotes){ var qs = document.createElement("span"); qs.className = "ln-why"; qs.textContent = it.quotes.join(", "); w.appendChild(qs); }
      if (it.note){ var n = document.createElement("span"); n.className = "ln-why"; n.textContent = it.note; w.appendChild(n); }
      box.appendChild(w);
    });
    if (cur.k !== "m"){ var p = document.createElement("p"); p.className = "ln-hint"; p.textContent = "Shown on the right side."; box.appendChild(p); }
  }
  function infoMuscle(m, part){
    var h = "<dl>";
    if (m.ta) h += "<dt>Latin</dt><dd>" + esc(m.ta) + "</dd>";
    if (m.o && (m.o[0] || m.o[1])) h += "<dt>Origin</dt><dd>" + esc([prettyBone(m.o[0]), m.o[1]].filter(Boolean).join(": ")) + "</dd>";
    if (m["in"] && (m["in"][0] || m["in"][1])) h += "<dt>Insertion</dt><dd>" + esc([prettyBone(m["in"][0]), m["in"][1]].filter(Boolean).join(": ")) + "</dd>";
    if ((m.nv || []).length || m.rt) h += "<dt>Nerve</dt><dd>" + esc((m.nv || []).join(", ")) + (m.rt ? " (" + esc(m.rt) + ")" : "") + "</dd>";
    if (part){ h += "<dt>This part</dt><dd>" + esc(part.f || "") + (part.i ? "<br><i>Nerve:</i> " + esc(part.i) : "") + "</dd>"; }
    h += "</dl>";
    if ((m.a || []).length) h += "<b>Actions</b><ul>" + m.a.map(function(a){ return "<li>" + esc(a) + "</li>"; }).join("") + "</ul>";
    var cites = {}; (m.mv || []).forEach(function(r){ if (r.src && r.src.indexOf("cite:") === 0) cites[r.src.slice(5)] = 1; });
    h += '<p class="ln-src">Source: ' + esc(m.s || "data/muscles") + Object.keys(cites).map(function(k){ var c = (D.cites || {})[k]; return c ? "; " + esc(c.citation) + (c.doi ? ", doi:" + esc(c.doi) : "") : ""; }).join("") + "</p>";
    return h;
  }
  function infoGroup(g){
    var h = "<p><b>Members</b>: " + g.members.map(function(b){ return esc(M[b] ? M[b].n : b) + (BYB[b] ? "" : " <i>(not modelled on this page)</i>"); }).join(", ") + "</p>";
    return h + '<p class="ln-src">Source: ' + esc(D.groups_source || "") + "</p>";
  }

  /* ---------- simulate: drive the Q241 pose rig ---------- */
  var STEP = 350;
  function ease(t){ return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }
  function stopAnim(){
    if (!anim) return;
    var a = anim; anim = null; cancelAnimationFrame(a.raf);
    if (a.btn) a.btn.classList.remove("ln-on");
    try { a.pc.apply(a.p0); } catch (err){}
  }
  function simulate(mvs, side, back, button){
    stopAnim();
    var pc = api.pose ? api.pose() : null;
    if (!pc || !pc.ready || !pc.ready()){ say("ln-act-msg", "The pose rig of this page is not ready (or the page has none)."); return false; }
    var rig = pc.rig(), p0 = pc.pose(), tracks = [], missing = [];
    mvs.forEach(function(mv){
      (Array.isArray(mv[0]) ? mv[0] : [mv[0]]).forEach(function(jn){
        var spine = !!SPINE[jn], sign = mv[2], id, d, x, v0, holder;
        if (spine && mv[3] && side === "l") sign = -sign;
        if (spine){
          var rg = rig.regions.filter(function(r){ return r.id === jn; })[0]; if (!rg){ missing.push(jn); return; }
          x = rg.dof.map(function(q){ return q.k; }).indexOf(mv[1]); if (x < 0){ missing.push(jn); return; }
          d = rg.dof[x]; v0 = p0.r[jn][x]; holder = ["r", jn, x];
        } else {
          id = jn + "_" + (side || "r");
          var jj = rig.joints.filter(function(j){ return j.id === id; })[0]; if (!jj || jj.driven){ missing.push(id); return; }
          x = jj.dof.map(function(q){ return q.k; }).indexOf(mv[1]); if (x < 0){ missing.push(id); return; }
          d = jj.dof[x]; v0 = p0.j[id][x]; holder = ["j", id, x];
        }
        var lim = sign > 0 ? d.hi : d.lo, opp = sign > 0 ? d.lo : d.hi, from = v0, to;
        if (back){ from = v0 + 0.6 * (opp - v0); to = v0; }
        else {
          to = v0 + 0.7 * (lim - v0);
          if (Math.abs(to - from) < 8){ from = v0 + 0.5 * (opp - v0); if (Math.abs(lim - from) < 8) from = opp; to = lim; }
        }
        tracks.push({h:holder, v0:v0, from:from, to:to});
      });
    });
    if (!tracks.length){ say("ln-act-msg", "This page's pose rig has no " + missing.join(", ") + " joint: nothing to animate here."); return false; }
    var A = tracks.some(function(t){ return Math.abs(t.from - t.v0) > 0.5; }) ? 600 : 0, B = 1500, H = 500, C = 1200, T = A + B + H + C;
    var vt = 0, last = performance.now();      // virtual clock: a slow frame (software rendering, a weak phone) advances it by at most STEP, so every phase is shown
    anim = {pc:pc, p0:p0, btn:button || null, raf:0, tracks:tracks};
    if (button) button.classList.add("ln-on");
    say("ln-act-msg", "Simulating within the rig's normal range of motion (kinematic preview, soft tissue follows by skinning)" + (missing.length ? "; not on this page's rig: " + missing.join(", ") : "") + ".");
    function at(tr, t){
      if (t < A) return tr.v0 + (tr.from - tr.v0) * ease(t / A);
      t -= A; if (t < B) return tr.from + (tr.to - tr.from) * ease(t / B);
      t -= B; if (t < H) return tr.to;
      t -= H; return tr.to + (tr.v0 - tr.to) * ease(Math.min(1, t / C));
    }
    function frame(now){
      if (!anim || anim.tracks !== tracks) return;
      vt += Math.min(STEP, Math.max(0, now - last)); last = now;
      var t = vt, d = JSON.parse(JSON.stringify(p0));
      tracks.forEach(function(tr){ d[tr.h[0]][tr.h[1]][tr.h[2]] = at(tr, Math.min(t, T)); });
      pc.apply(d);
      if (t >= T){ var a = anim; anim = null; if (a.btn) a.btn.classList.remove("ln-on"); pc.apply(p0); return; }
      anim.raf = requestAnimationFrame(frame);
    }
    anim.raf = requestAnimationFrame(frame);
    return true;
  }

  /* ---------- rotate: camera azimuth steps ---------- */
  function rotate(deg, dir){
    if (rot){ cancelAnimationFrame(rot.raf); rot = null; return false; }
    if (!api.orbit){ say("ln-msg", "This page cannot rotate the camera."); return false; }
    if (api.stopMotion) try { api.stopMotion(); } catch (err){}
    var total = dir * deg * Math.PI / 180, dur = deg >= 360 ? 6000 : 3000, done = 0, vt = 0, last = performance.now();
    rot = {raf:0};
    function frame(now){
      if (!rot) return;
      vt += Math.min(STEP, Math.max(0, now - last)); last = now;
      var t = Math.min(1, vt / dur), want = total * ease(t);
      api.orbit(want - done); done = want;
      if (t < 1) rot.raf = requestAnimationFrame(frame); else rot = null;
    }
    rot.raf = requestAnimationFrame(frame);
    return true;
  }

  /* ---------- follow clicks on the model ---------- */
  function follow(){
    if (panel.hidden || !$("ln-follow").checked || !api.selectedId) return;
    var sid = null; try { sid = api.selectedId(); } catch (err){}
    if (sid === lastSid) return; lastSid = sid;
    if (!sid) return;
    var x = resolve(sid);
    if (x && BYB[x.b]) choose({k:"m", b:x.b, side:x.side, c:x.c});
  }

  /* ---------- wiring ---------- */
  function open(on){
    panel.hidden = !on;
    if (btn) btn.setAttribute("aria-pressed", String(on));
    panel.classList.toggle("ln-phone", !!(api.canvas && window.innerWidth <= 760));
    clearInterval(poll); poll = 0;
    if (on){ try { lastSid = api.selectedId ? api.selectedId() : null; } catch (err){} poll = setInterval(follow, 350); }
    else { stopAnim(); if (rot){ cancelAnimationFrame(rot.raf); rot = null; } }
  }
  function mountToolbar(){
    var tb = api.toolbar; if (!tb) return;
    btn = document.createElement("button"); btn.type = "button"; btn.id = "t-learn"; btn.className = api.toolClass || "tool";
    btn.textContent = "Learn"; btn.setAttribute("aria-pressed", "false");
    btn.title = "Learn a muscle, a part of one, a muscle group or a motion: highlight it, rotate the figure, simulate its cited action";
    btn.addEventListener("click", function(){ open(panel.hidden); if (!panel.hidden) $("ln-q").focus(); });
    var ref = $("t-quick") || $("t-cut") || null;
    if (ref && ref.parentNode === tb) tb.insertBefore(btn, ref.nextSibling); else tb.appendChild(btn);
  }
  mountToolbar();
  $("ln-close").addEventListener("click", function(){ open(false); });
  $("ln-q").addEventListener("input", renderSearch);
  $("ln-op").addEventListener("input", function(){
    say("ln-op-v", this.value + "%");
    var sel = api.selection ? api.selection() : null; if (sel && sel.setFade && cur) sel.setFade(opac(), true);
  });
  $("ln-showall").addEventListener("click", function(){ stopAnim(); var sel = api.selection ? api.selection() : null; if (sel && sel.clear) sel.clear(); say("ln-msg", "Everything shown normally again."); });
  Array.prototype.forEach.call($("ln-rot").querySelectorAll("[data-turn]"), function(b){ b.addEventListener("click", function(){ rotate(+b.dataset.turn, +b.dataset.dir); }); });

  return {
    open:open,
    openFor:function(id){ var x = resolve(id); open(true); if (x && BYB[x.b]){ choose({k:"m", b:x.b, side:x.side, c:x.c}); return true; } say("ln-msg", "No cited muscle data for this structure."); return false; },
    pickMuscle:function(b, side, c){ if (!BYB[b]) return false; choose({k:"m", b:b, side:side || null, c:c || null}); return true; },
    pickGroup:function(gid){ var g = (D.groups || []).filter(function(x){ return x.id === gid; })[0]; if (!g) return false; choose({k:"g", g:g}); return true; },
    simulateRow:function(i){ var b = $("ln-acts").querySelectorAll(".ln-act button")[i]; if (!b) return false; b.click(); return !!anim; },
    rotate:rotate, resolve:resolve, recsFor:function(b, side, c){ return recsFor(b, side, c).map(function(r){ return r.id; }); },
    state:function(){ return {ready:true, open:!panel.hidden, cur:cur ? {k:cur.k, b:cur.b || null, side:cur.side || null, c:cur.c || null, g:cur.g ? cur.g.id : null, key:cur.key || null} : null,
      animating:!!anim, rotating:!!rot, muscles:Object.keys(BYB).length, acts:Array.prototype.map.call($("ln-acts").querySelectorAll(".ln-act button"), function(b){ return {label:b.textContent, disabled:b.disabled}; })}; }
  };
}
