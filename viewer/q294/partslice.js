/* Q294: the "Slices" panel -- the cross-section stack restricted to one part (a structure, the marked structures, the open card,
   or a segment found by name on this page: a finger's three phalanges, the forearm's radius + ulna), with a slice thickness,
   an interval along the part's long axis and a display-only spread. The stack itself is NMSKCrossSection's part mode (cut_cap.js);
   this file only builds the part list and opens the panel. Short menus, taps over sliders (the owner's mobile rule). */
var NMSKPartSlices = (function(){
  "use strict";
  var api = null, xs = null, panel = null, sel = null, tb = null, segs = [];
  var ORD = {first:1, second:2, third:3, fourth:4, fifth:5}, DIG = {1:"Thumb", 2:"Index finger", 3:"Middle finger", 4:"Ring finger", 5:"Little finger"};
  function $(id){ return document.getElementById(id); }
  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"}[c]; }); }
  function sideOf(r){ var s = String(r.side || "").charAt(0).toLowerCase(); if (!s){ var m = /_(l|r)$/i.exec(r.id || "") || /\((L|R)\)\s*$/.exec(r.name || ""); s = m ? m[1].toLowerCase() : ""; } return s === "l" || s === "r" ? s : ""; }
  function findSegments(){
    var recs = api.list(), by = {}, out = [];
    recs.forEach(function(r){
      var nm = String(r.name || r.id), m = /(proximal|middle|distal) phalanx of (first|second|third|fourth|fifth) finger of hand/i.exec(nm), s = sideOf(r);
      if (m){ var o = ORD[m[2].toLowerCase()], k = "f" + o + s; (by[k] = by[k] || {label:DIG[o] + (s ? " (" + s.toUpperCase() + ")" : ""), ids:[], ord:o, s:s}).ids.push(r.id); return; }
      var f = /^(radius|ulna)\b/i.exec(nm);
      if (f && /bone/i.test(String(r.cat))){ var k2 = "fa" + s; (by[k2] = by[k2] || {label:"Forearm" + (s ? " (" + s.toUpperCase() + ")" : "") + " (radius + ulna)", ids:[], ord:9, s:s}).ids.push(r.id); }
    });
    Object.keys(by).forEach(function(k){ if (by[k].ids.length < 2) return; out.push(by[k]); });
    out.sort(function(a, b){ return a.s.localeCompare(b.s) || a.ord - b.ord; });
    return out;
  }
  function fill(){
    if (!sel) return;
    var s = api.selection ? api.selection() : null, marks = s ? s.state().marks : [], cur = api.selectedId ? api.selectedId() : null, h = '<option value="">Choose a part…</option>';
    var name = function(id){ var r = api.list().filter(function(x){ return x.id === id; })[0]; return r ? r.name + (sideOf(r) ? " (" + sideOf(r).toUpperCase() + ")" : "") : id; };
    if (cur) h += '<option value="card">Open card: ' + esc(name(cur)) + '</option>';
    if (marks.length) h += '<option value="marks">Marked structures (' + marks.length + ')</option>';
    segs = findSegments();
    segs.forEach(function(g, i){ h += '<option value="seg' + i + '">' + esc(g.label) + '</option>'; });
    var v = sel.value; sel.innerHTML = h; if (v && sel.querySelector('option[value="' + v + '"]')) sel.value = v;
  }
  function choose(v){
    var ids = null, label = "";
    if (v === "card"){ var c = api.selectedId && api.selectedId(); if (c){ ids = [c]; label = "open card"; } }
    else if (v === "marks"){ var s = api.selection && api.selection(); if (s){ ids = s.state().marks.slice(); label = "marked"; } }
    else if (/^seg\d+$/.test(v)){ var g = segs[+v.slice(3)]; if (g){ ids = g.ids.slice(); label = g.label; } }
    if (!ids || !ids.length) return false;
    var ok = xs.setPart(ids, label);
    setTimeout(function(){ if (xs.state().planes.length) xs.frame(); }, 60);
    return ok;
  }
  function place(){                                   // right under the toolbar, never under the structure card / sheets at the bottom
    if (!panel || panel.hidden) return;
    var bar = api && api.toolbar, t = bar && bar.getBoundingClientRect ? bar.getBoundingClientRect() : null;
    if (t && t.height > 0){ var top = Math.round(Math.min(window.innerHeight * 0.45, t.bottom + 6)); panel.style.top = top + "px"; panel.style.bottom = "auto"; panel.style.maxHeight = "calc(100vh - " + (top + 10) + "px)"; panel.style.overflowY = "auto"; }
    else { panel.style.top = ""; panel.style.bottom = ""; panel.style.maxHeight = ""; }
  }
  function open(v){ if (!panel) return; panel.hidden = !v; if (v) fill(); place(); if (tb) tb.setAttribute("aria-pressed", String(!panel.hidden)); }
  function start(a, x, opt){
    api = a; xs = x; opt = opt || {}; panel = $("xsp-panel"); sel = $("xsp-part");
    if (!panel || !xs) return null;
    if (opt.toolbar){
      tb = document.createElement("button"); tb.type = "button"; tb.id = "t-slices"; tb.className = (opt.cls || "") + " xsp-tb"; tb.textContent = "Slices";
      tb.title = "Slices of one part: only a finger, the forearm, the marked structures... -- slice thickness, interval along the part, spread apart in the display";
      tb.setAttribute("aria-pressed", "false"); tb.addEventListener("click", function(){ open(panel.hidden); });
      opt.toolbar.appendChild(tb);
    }
    window.addEventListener("resize", place);
    sel.addEventListener("focus", fill); sel.addEventListener("pointerdown", fill);
    sel.addEventListener("change", function(){ choose(sel.value); });
    var cl = $("xsp-close"); if (cl) cl.addEventListener("click", function(){ open(false); });
    return {open:open, fill:fill, choose:choose, segments:function(){ fill(); return segs.map(function(g){ return {label:g.label, ids:g.ids.slice()}; }); }};
  }
  return {start:start};
})();
