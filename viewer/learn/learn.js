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

  /* ---------- Q284: moment arms computed from THIS page's meshes (scripts/anatomy/q284/build_moments.py), injected per page as a
     zlib-compressed nmsk-moments block; absent / empty on a page that was not built with it (then nothing is shown) ---------- */
  var MOM = null;
  (function loadMoments(){
    var el = $("nmsk-moments"); if (!el) return;
    var raw = null; try { raw = JSON.parse(el.textContent || "{}"); } catch (err){ return; }
    if (!raw || !raw.z || typeof DecompressionStream === "undefined") return;
    try {
      var bin = atob(raw.z), u8 = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      new Response(new Blob([u8]).stream().pipeThrough(new DecompressionStream("deflate"))).text()
        .then(function(t){ MOM = JSON.parse(t); reindex(); if (cur && cur.k === "m"){ renderMoments(cur); } })
        .catch(function(){ MOM = null; });
    } catch (err){ MOM = null; }
  })();

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
    var b = mm[1], side = mm[2], rest = mm[3] || null, b2 = b.replace(/_muscle$/, "");     // Z-Anatomy names: 'iliacus_muscle', 'tibialis_posterior_muscle'
    if (!M[b] && M[b2]) b = b2;
    if (M[b]){
      if (rest && hasPart(b, rest)) return {b:b, side:side, c:rest};
      if (rest && /tendon|fascia|bursa|branch|sheath|aponeur/.test(rest)) return null;
      return {b:b, side:side, c:null};
    }
    var hit = CIX[b] || CIX[b2];
    if (hit && hit.length === 1 && !rest) return {b:hit[0][0], side:side, c:hit[0][1]};
    return null;
  }
  var IDX = [], BYB = {};
  recs.forEach(function(r){
    if (r.cat && r.cat !== "muscle") return;
    var x = resolve(r.id); if (!x) return;
    IDX[r.i] = x; (BYB[x.b] = BYB[x.b] || []).push(r);
  });
  /* Q284: a page structure the name rule above cannot place (e.g. Z-Anatomy 'clavicular_part_of_deltoid_muscle_r') but that the moment-arm
     build resolved with the same rule plus a containment fallback (scripts/anatomy/q284/build_moments.py resolve()) joins its muscle here */
  function reindex(){
    if (!MOM || !MOM.s) return;
    recs.forEach(function(r){
      if (IDX[r.i] || (r.cat && r.cat !== "muscle")) return;
      var s = MOM.s[r.id]; if (!s || !s.b || !M[s.b]) return;
      var x = {b:s.b, side:(s.side === "r" || s.side === "l") ? s.side : null, c:(s.c && hasPart(s.b, s.c)) ? s.c : null};
      IDX[r.i] = x; (BYB[x.b] = BYB[x.b] || []).push(r);
    });
  }
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
    $("ln-ma-wrap").hidden = true; $("ln-ma").innerHTML = ""; $("ln-sec-l").hidden = true;
    if (it.k === "m"){
      var m = M[it.b], part = it.c ? (m.cp || []).filter(function(x){ return x.c === it.c; })[0] : null;
      title.innerHTML = esc(part ? part.n : m.n) + (it.side ? " <small>(" + esc(it.side) + ")</small>" : "") + (part ? " <small>part of " + esc(m.n) + "</small>" : m.ta ? " <small>" + esc(m.ta) + "</small>" : "");
      if ((m.cp || []).length){
        var all = document.createElement("button"); all.type = "button"; all.textContent = "Whole muscle"; all.setAttribute("aria-pressed", String(!it.c)); all.onclick = function(){ choosePart(null); }; parts.appendChild(all);
        m.cp.forEach(function(c){ var b = document.createElement("button"); b.type = "button"; b.textContent = c.n; b.setAttribute("aria-pressed", String(it.c === c.c)); b.onclick = function(){ choosePart(c.c); }; parts.appendChild(b); });
      }
      renderActsMuscle(m, it); info.innerHTML = infoMuscle(m, part);
      renderMoments(it);
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
  /* ---------- Q284: the computed moment arms of the structures on the card ---------- */
  var MAW = {flex:["flex", "ext"], abd:["abd", "add"], rot:["int rot", "ext rot"], sup:["sup", "pron"], dev:["rad dev", "uln dev"], dp:["dorsi", "plantar"], inv:["inv", "ev"]};
  var MAW_SPINE = {flex:["flex", "ext"], lat:["lat flex R", "lat flex L"], rot:["rot R", "rot L"]};
  function jointLabel(jid){
    var m = /^(.*)_(r|l)$/.exec(jid), base = m ? m[1] : jid, side = m ? (m[2] === "r" ? " (right)" : " (left)") : "";
    return jointName([base]) + side;
  }
  function momentsFor(it){
    if (!MOM || !MOM.s || !it || it.k !== "m") return [];
    var out = [], seen = {};
    recsFor(it.b, it.side, it.c).forEach(function(r){ var s = MOM.s[r.id]; if (s && !seen[r.id]){ seen[r.id] = 1; out.push({rec:r, s:s}); } });
    return out;
  }
  function fmt(v){ var a = Math.abs(v); return a >= 9.95 ? a.toFixed(0) : a.toFixed(1); }
  function cell(v, k, spine){
    var w = (spine ? MAW_SPINE : MAW)[k] || [k + "+", k + "-"];
    if (Math.abs(v) < 0.5) return '<td title="' + v + ' mm">0</td>';
    return '<td class="' + (v > 0 ? "ln-v-pos" : "ln-v-neg") + '" title="' + (v > 0 ? "+" : "") + v + ' mm">' + fmt(v) + " " + esc(w[v > 0 ? 0 : 1]) + "</td>";
  }
  function renderMoments(it){
    var box = $("ln-ma"), wrap = $("ln-ma-wrap"), list = momentsFor(it);
    box.innerHTML = "";
    if (!list.length){ wrap.hidden = true; $("ln-sec-l").hidden = true; return; }
    wrap.hidden = false;
    var anyJ = false;
    var h = '<span class="ln-badge">Computed from this body\'s geometry (moment arm, mm) -- not a textbook statement. ' + esc((MOM.method && MOM.method.text) || "") + "</span>";
    list.forEach(function(x){
      var s = x.s, js = Object.keys(s.j || {});
      if (list.length > 1 || (s.c && !it.c)) h += "<h4>" + esc(x.rec.name || x.rec.id) + "</h4>";
      js.forEach(function(jid){
        anyJ = true;
        var e = s.j[jid], dofs = e[0], angs = e[2], r = e[3], spine = !!SPINE[jid];
        var head = spine ? "per degree of regional motion" : (e[1] ? jointName([jid.replace(/_(r|l)$/, "")]) + " " + ((DN[e[1]] || [e[1]])[0]) + " " + angs.map(function(a){ return a + "°"; }).join(" / ") : "");
        h += "<table><tr><th>" + esc(jointLabel(jid)) + "</th>" + angs.map(function(a){ return "<th>" + (spine ? "" : esc(a + "°")) + "</th>"; }).join("") + "</tr>";
        dofs.forEach(function(k){ h += "<tr><td>" + esc(k) + "</td>" + (r[k] || []).map(function(v){ return cell(v, k, spine); }).join("") + "</tr>"; });
        h += "</table>";
        if (head && !spine) h += '<div class="ln-flag">columns: ' + esc(head) + "; the joint's other motions at 0" + (s.w && s.w[jid] ? "; wrap radius " + s.w[jid] + " mm (where this muscle sits over the joint at rest)" : "") + "</div>";
        if (s.lo && s.lo[jid] != null) h += '<div class="ln-flag">the path stops touching the hip wrap at ' + s.lo[jid] + "° of flexion</div>";
      });
      Object.keys(s.x || {}).forEach(function(jid){ h += '<div class="ln-flag">' + esc(jointLabel(jid)) + ": " + esc(s.x[jid]) + "</div>"; });
      (s.cv || []).forEach(function(c){
        h += '<div class="ln-chk-l">Cited action <b>' + esc(c[4]) + "</b> (" + esc(jointLabel(c[0])) + " " + esc(c[1]) + "): computed sign <b>" + esc(c[3]) + "</b></div>";
      });
      (s.lv || []).forEach(function(l){
        var ref = (MOM.lit || {})[l[0]] || {};
        h += '<div class="ln-chk-l">Literature (' + esc(jointLabel(l[1])) + " " + esc(l[2]) + "): <b>" + esc(l[3]) + "</b> -- " + esc(l[4]) +
             "<q>" + esc(ref.quote || "") + "</q>" + '<span class="ln-flag">' + esc(ref.cite || "") + (ref.doi ? ' <a href="https://doi.org/' + esc(ref.doi) + '" target="_blank" rel="noopener">doi:' + esc(ref.doi) + "</a>" : "") + (ref.note ? " -- " + esc(ref.note) : "") + "</span></div>";
      });
      (s.f || []).forEach(function(f){ h += '<div class="ln-flag">Note: ' + esc(f) + "</div>"; });
    });
    if (!anyJ) h += '<p class="ln-hint">This structure\'s path on this body crosses no joint of the pose rig, so no moment arm is computed.</p>';
    box.innerHTML = h;
    $("ln-sec-l").hidden = !anyJ;
  }
  /* secondary components for a primary motion of joint jid / dof k0: r_k / r_k0 of the card's structures, interpolated at the primary angle */
  function secondaryFor(jid, k0, sign){
    var list = momentsFor(cur), rows = [];
    list.forEach(function(x){ var e = x.s.j && x.s.j[jid]; if (e && e[1] === k0) rows.push(e); });
    if (!rows.length) return null;
    var angs = rows[0][2], dofs = rows[0][0];
    function sumAt(k, a){
      var tot = 0;
      rows.forEach(function(e){
        var v = e[3][k] || [], A = e[2];
        if (a <= A[0]) tot += v[0]; else if (a >= A[A.length - 1]) tot += v[v.length - 1];
        else for (var i = 0; i < A.length - 1; i++) if (a >= A[i] && a <= A[i + 1]){ var t = (a - A[i]) / (A[i + 1] - A[i]); tot += v[i] + t * (v[i + 1] - v[i]); break; }
      });
      return tot;
    }
    var p0 = sumAt(k0, 0);
    if (!(p0 * sign > 0)) return {bad:true};          // computed primary sign disagrees with the cited motion: no secondary added
    return {dofs:dofs.filter(function(k){ return k !== k0; }), ratio:function(k, a){ var p = sumAt(k0, a); return Math.abs(p) < 0.5 ? 0 : sumAt(k, a) / p; }};
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
        tracks.push({h:holder, v0:v0, from:from, to:to, sg:sign});
      });
    });
    if (!tracks.length){ say("ln-act-msg", "This page's pose rig has no " + missing.join(", ") + " joint: nothing to animate here."); return false; }
    /* Q284: optional secondary components -- every other dof of the same joint follows the primary one at the rate r_k / r_k0 of this
       body's computed moment arms (interpolated at the current primary angle), within the rig's range of motion */
    var extra = [], secNote = [];
    if ($("ln-sec") && $("ln-sec").checked && cur && cur.k === "m"){
      tracks.forEach(function(tr){
        if (tr.h[0] !== "j") return;
        var jid = tr.h[1], jj = rig.joints.filter(function(j){ return j.id === jid; })[0]; if (!jj) return;
        var k0 = jj.dof[tr.h[2]].k, sf = secondaryFor(jid, k0, tr.sg);
        if (!sf) return;
        if (sf.bad){ secNote.push(jointLabel(jid) + ": the computed " + k0 + " moment arm has the opposite sign to the cited motion, no secondary component added"); return; }
        var lo = Math.floor(Math.min(tr.from, tr.to, tr.v0)), hi = Math.ceil(Math.max(tr.from, tr.to, tr.v0));
        sf.dofs.forEach(function(k){
          var xk = jj.dof.map(function(q){ return q.k; }).indexOf(k); if (xk < 0) return;
          var I = [], acc = 0;
          for (var a = lo; a <= hi; a++){ I.push(acc); acc += sf.ratio(k, a + 0.5); }
          var integ = function(p){ var f = Math.max(0, Math.min(I.length - 1.000001, p - lo)), i0 = Math.floor(f); return I[i0] + (f - i0) * ((I[i0 + 1] !== undefined ? I[i0 + 1] : I[i0]) - I[i0]); };
          var d2 = jj.dof[xk], base = p0.j[jid][xk], off = integ(tr.v0);
          extra.push({h:["j", jid, xk], prim:tr, f:function(p){ return Math.max(d2.lo, Math.min(d2.hi, base + integ(p) - off)); }});
          secNote.push(jointLabel(jid) + " " + k + " x" + sf.ratio(k, 0).toFixed(2) + " per degree of " + k0 + " at 0°");
        });
      });
    }
    var A = tracks.some(function(t){ return Math.abs(t.from - t.v0) > 0.5; }) ? 600 : 0, B = 1500, H = 500, C = 1200, T = A + B + H + C;
    var vt = 0, last = performance.now();      // virtual clock: a slow frame (software rendering, a weak phone) advances it by at most STEP, so every phase is shown
    anim = {pc:pc, p0:p0, btn:button || null, raf:0, tracks:tracks};
    if (button) button.classList.add("ln-on");
    anim.extra = extra;
    say("ln-act-msg", "Simulating within the rig's normal range of motion (kinematic preview, soft tissue follows by skinning)" + (missing.length ? "; not on this page's rig: " + missing.join(", ") : "") +
        (secNote.length ? ". With the computed secondary components (this body's moment arms): " + secNote.join("; ") : "") + ".");
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
      extra.forEach(function(e){ d[e.h[0]][e.h[1]][e.h[2]] = e.f(at(e.prim, Math.min(t, T))); });
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
    moments:function(){ return {loaded:!!MOM, key:MOM ? MOM.key : null, card:momentsFor(cur).map(function(x){ return {id:x.rec.id, j:x.s.j, lv:x.s.lv, cv:x.s.cv, x:x.s.x}; })}; },
    setSecondary:function(on){ var c = $("ln-sec"); if (c) c.checked = !!on; return !!(c && c.checked); },
    animState:function(){ return anim ? {extra:(anim.extra || []).map(function(e){ return e.h; }), tracks:anim.tracks.map(function(t){ return t.h; })} : null; },
    state:function(){ return {ready:true, open:!panel.hidden, cur:cur ? {k:cur.k, b:cur.b || null, side:cur.side || null, c:cur.c || null, g:cur.g ? cur.g.id : null, key:cur.key || null} : null,
      animating:!!anim, rotating:!!rot, muscles:Object.keys(BYB).length, acts:Array.prototype.map.call($("ln-acts").querySelectorAll(".ln-act button"), function(b){ return {label:b.textContent, disabled:b.disabled}; })}; }
  };
}
