/* Q322: the MUSCLE INNERVATION mode (viewer/innervation/, synced into both templates by scripts/sync_innervation_q322.py).
   A provider of the shared workspace-modes controller (viewer/modes/modes.js): it registers as "inn" once the page's sidecar
   innervation_q322.json has loaded (public anatomy layer, built by scripts/anatomy/q322/build_sidecar_q322.py from
   data/anatomy/innervation_q322.json + this page's rule-based band placement); no sidecar = no mode on that page.
   - Colour by nerve trunk or by root level: the selection controller's own per-structure colours (window.NMSKSelectCtl
     snapshot / restore), put back exactly on exit.
   - A nerve (clicked on the model), a trunk chip or a root chip MARKS its muscles through the same controller (markIds, the
     rest faded): no parallel selection state.
   - The panel follows the page's selection (the quick card still opens on every click; this mode never touches it).
   - IZ bands are RULE-BASED markers (ring = the muscle's section at the stated level, dot = its inside centre), drawn from the
     sidecar through the engine's after-draw hook; nothing is measured in the browser. */
var NMSKInnervation = (function(){
  "use strict";
  var URL = "innervation_q322.json", D = null, ctx = null, api = null, on = false, IX = null, hooked = false;
  var st = {by:"nerve", iz:"sel", pick:null, view:null, lastSel:undefined, saved:null};
  var ui = {}, GL = null, drawn = {bands:0, rings:0, dots:0}, mk = [], mkBox = null;
  var GREY = "#9aa3ab", KEEP = {bone:1, cartilage:1, muscle:1, insertion:1, nerve:1};
  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"}[c]; }); }
  function sel(){ try { return (api && api.selection && api.selection()) || window.NMSKSelectCtl || null; } catch (e){ return window.NMSKSelectCtl || null; } }
  function sideOf(id){ var m = /_([lr])$/.exec(id || ""); return m ? m[1] : null; }
  function base(id){ return String(id || "").replace(/_[lr]$/, ""); }
  function pretty(s){ s = String(s || "").replace(/_/g, " "); return s.charAt(0).toUpperCase() + s.slice(1); }
  function pctText(p){ return Array.isArray(p) ? p[0] + "–" + p[1] + " %" : p == null ? "site only" : p + " %"; }
  /* ---------- indexes over the sidecar and this page's structures ---------- */
  function index(){
    if (IX) return IX;
    var byId = {}, s2m = {}, nerveIds = {}, chainSet = {}, lab = {}, bm = {}, tk = {}, rc = {};
    (api.list() || []).forEach(function(r){ byId[r.id] = r; });
    Object.keys(D.muscles).forEach(function(k){
      var m = D.muscles[k];
      m.structures.forEach(function(id){ s2m[id] = k; });
      m.nerve_structures.forEach(function(id){ nerveIds[id] = 1; });
      m.nerve.forEach(function(n){ lab[n.id] = n.label; });
      m.chain.forEach(function(c){ (chainSet[c] = chainSet[c] || []).push(k); });
    });
    D.bands.forEach(function(b, i){ b.i = i; var key = b.m + "|" + b.s; (bm[key] = bm[key] || []).push(b); });
    D.trunks.forEach(function(t){ tk[t.key] = t; });
    D.roots.forEach(function(r){ rc[r.level] = r.colour; });
    IX = {byId:byId, s2m:s2m, nerveIds:nerveIds, chainSet:chainSet, lab:lab, bm:bm, tk:tk, rc:rc};
    return IX;
  }
  function present(ids){ return ids.filter(function(id){ return !!IX.byId[id]; }); }
  function onSide(ids, s){ return s ? ids.filter(function(id){ return sideOf(id) === s; }) : ids; }
  function midRoot(lv){ return lv && lv.length ? lv[(lv.length - 1) >> 1] : null; }
  function srcLabel(k){ var s = D.sources[k]; return s ? s.label : k; }
  function srcLink(k){
    var s = D.sources[k]; if (!s) return esc(k);
    var href = s.doi ? "https://doi.org/" + s.doi : s.pmid ? "https://pubmed.ncbi.nlm.nih.gov/" + s.pmid + "/" : null;
    return href ? '<a href="' + esc(href) + '" target="_blank" rel="noopener">' + esc(s.label) + "</a>" : esc(s.label);
  }
  function trunkMuscles(key){ return Object.keys(D.muscles).filter(function(k){ return D.muscles[k].trunks.indexOf(key) >= 0; }); }
  function rootMuscles(lv){ return Object.keys(D.muscles).filter(function(k){ return D.muscles[k].roots.adopted.indexOf(lv) >= 0; }); }
  function nerveMuscles(id){
    var out = {}, b = base(id);
    Object.keys(D.muscles).forEach(function(k){ if (D.muscles[k].nerve_structures.indexOf(id) >= 0) out[k] = 1; });
    (IX.chainSet[b] || []).forEach(function(k){ out[k] = 1; });
    return Object.keys(out);
  }
  /* ---------- colour (the controller's own per-structure colours) ---------- */
  function colourMap(){
    var map = {};
    Object.keys(IX.byId).forEach(function(id){ if (IX.byId[id].cat === "muscle") map[id] = GREY; });
    Object.keys(D.muscles).forEach(function(k){
      var m = D.muscles[k], hex = st.by === "nerve" ? (IX.tk[m.trunks[0]] || {}).colour : IX.rc[midRoot(m.roots.adopted)];
      if (hex) present(m.structures).forEach(function(id){ map[id] = hex.toLowerCase(); });
    });
    return map;
  }
  function applyColours(){ var c = sel(); if (!c || !c.snapshot) return; var s = c.snapshot(); s.ucol = colourMap(); s.ucolNext = null; c.restore(s); }
  /* ---------- marking (the controller's marks, the rest faded) ---------- */
  function markMuscles(keys, side, extra, pick){
    var c = sel(); if (!c) return 0;
    var ids = [];
    keys.forEach(function(k){ ids = ids.concat(onSide(present(D.muscles[k].structures), side)); });
    ids = ids.concat(present(extra || []));
    var n = c.markIds(ids, true, true, true);
    if (n) c.setGroup("oth", "fade", true);
    st.pick = n ? pick : null;
    return n;
  }
  function clearPick(){ var c = sel(); if (c && st.pick) c.markIds([], true, true, true); st.pick = null; }
  function pickTrunk(key){
    if (st.pick && st.pick.kind === "trunk" && st.pick.key === key){ clearPick(); render(); return; }
    var ms = trunkMuscles(key), t = IX.tk[key], nerves = [];
    ms.forEach(function(k){
      var m = D.muscles[k];
      m.nerve_structures.forEach(function(id){
        var b = base(id), mine = m.trunks.length === 1 || t.nerves.indexOf(b) >= 0 || b.indexOf(key) >= 0;
        if (mine && nerves.indexOf(id) < 0) nerves.push(id);
      });
    });
    markMuscles(ms, null, nerves, {kind:"trunk", key:key, muscles:ms});
    st.view = st.view && st.view.kind === "muscle" ? st.view : null; render();
  }
  function pickRoot(lv){
    if (st.pick && st.pick.kind === "root" && st.pick.key === lv){ clearPick(); render(); return; }
    var ms = rootMuscles(lv);
    markMuscles(ms, null, [], {kind:"root", key:lv, muscles:ms});
    st.view = st.view && st.view.kind === "muscle" ? st.view : null; render();
  }
  function pickNerve(id){
    var ms = nerveMuscles(id);
    markMuscles(ms, sideOf(id), [id], {kind:"nerve", key:id, muscles:ms});
    st.view = {kind:"nerve", id:id, muscles:ms};
  }
  /* ---------- the page's selection drives the panel ---------- */
  function follow(){
    var id = null; try { id = ctx.selectedId(); } catch (e){ id = null; }
    if (id === st.lastSel) return;
    st.lastSel = id;
    if (!id){ render(); return; }
    if (IX.s2m[id]) st.view = {kind:"muscle", key:IX.s2m[id], id:id, side:sideOf(id)};
    else if (IX.nerveIds[id] || IX.chainSet[base(id)]) pickNerve(id);
    else st.view = {kind:"other", id:id};
    render();
    if (api && api.redraw) api.redraw();
  }
  /* ---------- the panel ---------- */
  function lineText(lineId){
    var L = D.lines[lineId]; if (!L) return lineId;
    var px = [L.from, L.to].filter(function(k){ return D.landmarks[k] && D.landmarks[k].kind === "soft_tissue"; });
    return esc(L.label) + (px.length ? ' <span class="inn-badge q" title="' + esc(px.map(function(k){ return D.landmarks[k].label + ": " + D.landmarks[k].proxy; }).join(" | ")) + '">proxy</span>' : "");
  }
  function badgeText(m, iz, b){
    var L = D.lines[iz.line] || {}, src = (iz.src || []).map(srcLabel).join(", ");
    var t = "Innervation zone — rule-based. Level = " + pctText(iz.pct) + " of " + (L.label || iz.line) + " (" + src + (iz.cite ? ", " + iz.cite : "") +
            "), measured on this body's own bones.";
    if (b && b.proxy) t += " Proxy landmark: " + b.proxy.map(function(k){ return (D.landmarks[k] || {}).label + " (" + ((D.landmarks[k] || {}).proxy || "") + ")"; }).join("; ") + ".";
    if (iz.note) t += " Note: " + iz.note + ".";
    return t;
  }
  function bandOf(key, i, s){ return (IX.bm[key + "|" + s] || []).filter(function(b){ return b.iz === i; })[0] || null; }
  function rootTags(lv){ return lv.map(function(r){ return '<span class="inn-tag lv" style="background:' + esc(IX.rc[r] || "#888") + '">' + esc(r) + "</span>"; }).join(""); }
  function muscleHtml(v){
    var k = v.key, m = D.muscles[k], s = v.side, R = m.roots, h = [];
    var tcol = m.trunks.map(function(t){ var T = IX.tk[t]; return T ? '<span class="inn-tag"><i style="display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;background:' + esc(T.colour) + '"></i>' + esc(T.label) + "</span>" : ""; }).join("");
    h.push('<h3 data-inn="muscle-name">' + esc(m.name) + (s ? ' <span class="inn-sub">(' + (s === "r" ? "right" : "left") + ")</span>" : "") + "</h3>");
    if (v.id && (IX.byId[v.id] || {}).name && IX.byId[v.id].name !== m.name) h.push('<div class="inn-sub">' + esc(IX.byId[v.id].name) + "</div>");
    h.push('<dl class="inn-kv"><dt>Nerve</dt><dd data-inn="nerve">' + esc(m.nerve.map(function(n){ return n.label; }).join(" + ")) + "</dd>");
    if (m.branch) h.push("<dt>Branch</dt><dd>" + esc(m.branch) + "</dd>");
    var pn = m.parts.filter(function(p){ return p.nerve; });
    if (pn.length) h.push('<dt>Part nerves</dt><dd data-inn="parts">' + pn.map(function(p){ return esc(pretty(p.id)) + ": " + esc(IX.lab[p.nerve] || pretty(p.nerve)); }).join("<br>") + "</dd>");
    h.push('<dt>Trunk</dt><dd class="inn-tags">' + tcol + "</dd>");
    h.push('<dt>Roots</dt><dd><span class="inn-tags" data-inn="roots">' + rootTags(R.adopted) + '</span><div class="inn-sub" data-inn="range">adopted ' + esc(R.text || R.adopted.join("-")) +
           " · range across sources " + esc(R.range || "") + "</div></dd></dl>");
    if (R.per_source && R.per_source.length) h.push("<details><summary>Roots by source (" + R.per_source.length + ")</summary><ul class=\"inn-list\">" + R.per_source.map(function(p){
      return '<li title="' + esc(p.note) + '">' + srcLink(p.src) + ": " + esc(p.levels.join(", ")) + (p.note ? ' <span class="inn-sub">— ' + esc(p.note) + "</span>" : "") + "</li>"; }).join("") + "</ul>" +
      (R.rule ? '<p class="inn-rule">' + esc(R.rule) + "</p>" : "") + "</details>");
    if (R.conflict && R.conflict.length) h.push('<ul class="inn-conf">' + R.conflict.map(function(c){ return "<li>" + esc(typeof c === "string" ? c : JSON.stringify(c)) + "</li>"; }).join("") + "</ul>");
    h.push("<h4>Innervation zones (" + m.iz.length + ")</h4>");
    if (!m.iz.length) h.push('<p class="inn-hint">' + esc(m.iz_decision || "No innervation-zone level in the sources used.") + "</p>");
    m.iz.forEach(function(iz, i){
      var b = s ? bandOf(k, i, s) : null, stt = b ? b.st : "";
      var badge = stt === "placed" ? '<span class="inn-badge" title="' + esc(badgeText(m, iz, b)) + '">rule-based</span>' :
                  stt === "failed" ? '<span class="inn-badge fail" title="' + esc(b.reason || "") + '">not placed</span>' :
                  stt === "qualitative" ? '<span class="inn-badge q">site only</span>' : "";
      h.push('<div class="inn-band" data-inn-band="' + i + '"><div><span class="t">' + esc(pretty(iz.part)) + "</span> · " + esc(pctText(iz.pct)) + " " + badge + "</div>" +
             '<div class="inn-sub">' + lineText(iz.line) + "</div>" +
             (stt === "failed" ? '<div class="inn-sub">Not placed on this body: ' + esc(b.reason) + "</div>" : "") +
             (b && b.note ? '<div class="inn-sub">' + esc(b.note) + "</div>" : "") +
             (iz.note ? '<div class="inn-sub">' + esc(iz.note) + "</div>" : "") +
             '<div class="inn-cite">' + (iz.src || []).map(srcLink).join(", ") + (iz.cite ? " · " + esc(iz.cite) : "") + "</div></div>");
    });
    var same = m.iz_other.filter(function(o){ return o.agreement !== "not_comparable"; }), diff = m.iz_other.filter(function(o){ return o.agreement === "not_comparable"; });
    function oRow(o){ return "<li>" + srcLink(o.src) + ": " + esc(pctText(o.pct)) + (o.line ? " of " + esc((D.lines[o.line] || {}).label || o.line) : "") + " · " + esc(o.kind || "") +
      (o.part ? " (" + esc(pretty(o.part)) + ")" : "") + ' <span class="inn-ag ' + esc(o.agreement) + '">' + esc(pretty(o.agreement)) + "</span>" + (o.note ? '<br><span class="inn-sub">' + esc(o.note) + "</span>" : "") + "</li>"; }
    if (same.length) h.push('<h4>Other sources, same line</h4><ul class="inn-list" data-inn="agree">' + same.map(oRow).join("") + "</ul>");
    if (diff.length) h.push("<details><summary>Other sources, different lines (" + diff.length + ")</summary><ul class=\"inn-list\">" + diff.map(oRow).join("") + "</ul></details>");
    if (m.iz_decision && m.iz.length) h.push('<p class="inn-rule">' + esc(m.iz_decision) + "</p>");
    if (m.conflicts && m.conflicts.length) h.push('<h4>Conflicts</h4><ul class="inn-conf" data-inn="conflicts">' + m.conflicts.map(function(c){ return "<li>" + esc(c) + "</li>"; }).join("") + "</ul>");
    if (window.__poseAtRest === false) h.push('<p class="inn-hint">The IZ markers are drawn on the rest pose only.</p>');
    return h.join("");
  }
  function listHtml(title, keys, side){
    var h = ["<h3>" + title + "</h3>"];
    if (!keys.length){ h.push('<p class="inn-hint">None of the ' + Object.keys(D.muscles).length + " muscles in this mode is supplied by it.</p>"); return h.join(""); }
    h.push('<div class="inn-sub">' + keys.length + " muscle" + (keys.length === 1 ? "" : "s") + " marked, the rest faded. Pick one:</div>");
    h.push('<ul class="inn-list" data-inn="mlist">' + keys.map(function(k){
      var id = onSide(present(D.muscles[k].structures), side || "r")[0] || present(D.muscles[k].structures)[0];
      return id ? '<li><button type="button" data-sel="' + esc(id) + '">' + esc(D.muscles[k].name) + "</button></li>" : "";
    }).join("") + "</ul>");
    return h.join("");
  }
  function render(){
    if (!on || !ui.panel) return;
    var v = st.view, p = st.pick, h;
    if (v && v.kind === "muscle") h = muscleHtml(v);
    else if (v && v.kind === "nerve") h = listHtml(esc((IX.byId[v.id] || {}).name || pretty(base(v.id))) + ' <span class="inn-sub">(nerve)</span>', v.muscles, sideOf(v.id));
    else if (p && p.kind === "trunk") h = listHtml(esc(IX.tk[p.key].label), p.muscles);
    else if (p && p.kind === "root") h = listHtml("Root " + esc(p.key), p.muscles);
    else h = (v && v.kind === "other" ? "<h3>" + esc((IX.byId[v.id] || {}).name || v.id) + '</h3><p class="inn-hint">Not one of the ' + Object.keys(D.muscles).length + " limb muscles with an innervation record.</p>" : "") +
             '<p class="inn-hint">Click a muscle for its nerve, roots and innervation zones. Click a nerve on the model, or a chip above, to mark the muscles it supplies.</p>';
    ui.panel.innerHTML = h;
    syncCtl();
    /* the panel follows the selection: if its top is out of the side column's view (phone: the column sits under the model), bring it in */
    var sd = ui.side;
    var top = ui.panel.offsetTop - sd.offsetTop;     // both measured from the same offset parent
    var phone = ctx && ctx.isPhone && ctx.isPhone();
    if (sd && (v || p) && top > sd.scrollTop + (phone ? 8 : sd.clientHeight - 48)) sd.scrollTop = top - 6;
  }
  function syncCtl(){
    if (!ui.ctl) return;
    Array.prototype.forEach.call(ui.ctl.querySelectorAll("[data-by]"), function(b){ b.setAttribute("aria-pressed", String(b.getAttribute("data-by") === st.by)); });
    Array.prototype.forEach.call(ui.ctl.querySelectorAll("[data-iz]"), function(b){ b.setAttribute("aria-pressed", String(b.getAttribute("data-iz") === st.iz)); });
    Array.prototype.forEach.call(ui.legend.querySelectorAll(".inn-chip"), function(b){
      var k = b.getAttribute("data-key"), kind = b.getAttribute("data-kind");
      b.setAttribute("aria-pressed", String(!!(st.pick && st.pick.kind === kind && st.pick.key === k)));
    });
  }
  function legend(){
    var h = [];
    if (st.by === "nerve"){
      D.trunks.forEach(function(t){ var n = trunkMuscles(t.key).length; if (!n) return;
        h.push('<button type="button" class="inn-chip" data-kind="trunk" data-key="' + esc(t.key) + '" title="Mark the ' + n + " muscles of the " + esc(t.label) + '"><i style="background:' + esc(t.colour) + '"></i><b>' + esc(t.label) + "</b><small>" + n + "</small></button>"); });
      h.push('<span class="inn-chip" style="border-style:dashed" title="Muscles without an innervation record in this mode"><i style="background:' + GREY + '"></i><b>no record</b></span>');
    } else {
      D.roots.forEach(function(r){ var n = rootMuscles(r.level).length;
        h.push('<button type="button" class="inn-chip" data-kind="root" data-key="' + esc(r.level) + '" title="Mark the ' + n + " muscles that " + esc(r.level) + ' supplies"><i style="background:' + esc(r.colour) + '"></i><b>' + esc(r.level) + "</b><small>" + n + "</small></button>"); });
    }
    ui.legend.innerHTML = h.join("");
    ui.rule.textContent = D.colour_rules[st.by] + " IZ markers are rule-based (hover a marker for its rule and source).";
    ui.rule.title = D.rule;
    syncCtl();
  }
  function setBy(by){ if (by !== "nerve" && by !== "root") return; if (st.by !== by){ st.by = by; clearPick(); applyColours(); } legend(); render(); }
  function setIz(v){ st.iz = v; syncCtl(); if (api && api.redraw) api.redraw(); }
  /* ---------- the IZ markers (rule-based), WebGL after-draw pass ---------- */
  var VS = "attribute vec3 aP;uniform mat4 uM;uniform vec3 uEye;uniform float uPt;varying vec3 vW;" +
           "void main(){vW=aP;vec3 d=uEye-aP;float l=length(d);vec3 p=aP+(l>0.0?d/l*1.5:vec3(0.0));gl_Position=uM*vec4(p,1.0);gl_PointSize=uPt;}";
  var FS = "precision mediump float;uniform vec4 uC;uniform vec4 uClip;uniform vec4 uClip2;uniform float uRound;varying vec3 vW;" +
           "void main(){if(dot(vW,uClip.xyz)+uClip.w>0.0||dot(vW,uClip2.xyz)+uClip2.w>0.0)discard;" +
           "if(uRound>0.5){vec2 q=gl_PointCoord-0.5;if(dot(q,q)>0.25)discard;}gl_FragColor=uC;}";
  function glInit(gl){
    if (GL && GL.gl === gl) return GL;
    function sh(t, s){ var o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o); if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; }
    var p = gl.createProgram(); gl.attachShader(p, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, FS));
    gl.bindAttribLocation(p, 0, "aP"); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    var U = {}; ["uM", "uEye", "uPt", "uC", "uClip", "uClip2", "uRound"].forEach(function(n){ U[n] = gl.getUniformLocation(p, n); });
    GL = {gl:gl, p:p, U:U, buf:gl.createBuffer(), sig:"", rings:[], dots:[], lines:[], nv:0};
    return GL;
  }
  function wanted(){
    var out = [];
    if (!on || st.iz === "off" || window.__poseAtRest === false) return out;
    var vis = {}, recs = api.list() || [];
    function visible(k, s){
      var key = k + "|" + s; if (key in vis) return vis[key];
      var ok = false; onSide(present(D.muscles[k].structures), s).forEach(function(id){ var r = IX.byId[id]; if (r && api.visible(r.i)) ok = true; });
      return (vis[key] = ok);
    }
    var v = st.view;
    D.bands.forEach(function(b){
      if ((b.st !== "placed" && b.st !== "qualitative") || b.same_as != null) return;
      var mine = v && v.kind === "muscle" && v.key === b.m && (!v.side || v.side === b.s);
      if (st.iz === "sel" && !mine) return;
      if (visible(b.m, b.s)) out.push(b);
    });
    return out;
  }
  function fill(G, bands){
    var sig = bands.map(function(b){ return b.i; }).join(",");
    if (sig === G.sig) return;
    var arr = [], rings = [], dots = [], lines = [];
    function push(p){ arr.push(p[0], p[1], p[2]); return arr.length / 3 - 1; }
    bands.forEach(function(b){
      if (b.st === "qualitative"){
        var a = b.from_pt, c = b.to_pt, i0 = push(a); push(c); lines.push([i0, 2]);
        var t0 = arr.length / 3; [1 / 3, 2 / 3].forEach(function(f){ push([a[0] + (c[0] - a[0]) * f, a[1] + (c[1] - a[1]) * f, a[2] + (c[2] - a[2]) * f]); });
        dots.push([t0, 2, "tick"]); return;
      }
      (b.rings || []).forEach(function(r){ var s0 = arr.length / 3; r.forEach(push); rings.push([s0, r.length]); });
      dots.push([push(b.dot), 1, "dot"]);
    });
    var gl = G.gl; gl.bindBuffer(gl.ARRAY_BUFFER, G.buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(arr), gl.DYNAMIC_DRAW);
    G.sig = sig; G.rings = rings; G.dots = dots; G.lines = lines; G.nv = arr.length / 3;
  }
  function draw(g){
    drawn = {bands:0, rings:0, dots:0};
    if (!on){ tags([]); return; }
    var bands = wanted();
    if (!bands.length){ tags([]); return; }
    var gl = g.gl, G = glInit(gl), U = G.U, dpr = window.devicePixelRatio || 1;
    fill(G, bands);
    gl.useProgram(G.p);
    gl.bindBuffer(gl.ARRAY_BUFFER, G.buf); gl.enableVertexAttribArray(0); gl.disableVertexAttribArray(1); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
    gl.uniformMatrix4fv(U.uM, false, g.mvp); gl.uniform3f(U.uEye, g.eye[0], g.eye[1], g.eye[2]);
    var c1 = g.clip || [0, 0, 0, -1], c2 = g.clip2 || [0, 0, 0, -1];
    gl.uniform4f(U.uClip, c1[0], c1[1], c1[2], c1[3]); gl.uniform4f(U.uClip2, c2[0], c2[1], c2[2], c2[3]);
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false);
    function rings(pt, col){
      gl.uniform4f(U.uC, col[0], col[1], col[2], col[3]);
      G.rings.forEach(function(r){ gl.uniform1f(U.uRound, 0); gl.drawArrays(gl.LINE_LOOP, r[0], r[1]); gl.uniform1f(U.uPt, pt * dpr); gl.uniform1f(U.uRound, 1); gl.drawArrays(gl.POINTS, r[0], r[1]); });
      G.lines.forEach(function(l){ gl.uniform1f(U.uRound, 0); gl.drawArrays(gl.LINES, l[0], l[1]); });
    }
    gl.disable(gl.DEPTH_TEST); rings(2.5, [1, 0.88, 0.3, 0.35]);                 // the part of a ring behind the muscle, faint
    gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); rings(3.5, [1, 0.85, 0.2, 1]);   // the visible part
    gl.disable(gl.DEPTH_TEST); gl.uniform1f(U.uRound, 1);
    G.dots.forEach(function(d){                                                    // the dot (inside the muscle) is always on top
      gl.uniform1f(U.uPt, (d[2] === "dot" ? 12 : 8) * dpr); gl.uniform4f(U.uC, 0.08, 0.08, 0.1, 0.9); gl.drawArrays(gl.POINTS, d[0], d[1]);
      gl.uniform1f(U.uPt, (d[2] === "dot" ? 7 : 4.5) * dpr); gl.uniform4f(U.uC, 1, 0.92, 0.35, 1); gl.drawArrays(gl.POINTS, d[0], d[1]);
    });
    gl.depthMask(true);
    drawn = {bands:bands.length, rings:G.rings.length, dots:G.dots.length};
    tags(bands);
  }
  /* the on-model badge: "IZ · rule-based" beside each dot of the selected muscle, the citation in its tooltip */
  function tags(bands){
    if (!mkBox){ mkBox = document.createElement("div"); mkBox.className = "inn-mks"; document.body.appendChild(mkBox); }
    var list = st.iz === "all" && bands.length > 8 ? [] : bands.filter(function(b){ return b.st === "placed"; });
    while (mk.length < list.length){ var e = document.createElement("div"); e.className = "inn-mk"; mkBox.appendChild(e); mk.push(e); }
    var placed = [];
    mk.forEach(function(e, i){
      var b = list[i], p = b && api && api.toScreen ? api.toScreen(b.dot) : null;
      if (!b || !p){ e.hidden = true; e.style.display = "none"; return; }
      var m = D.muscles[b.m], iz = m.iz[b.iz], x = Math.round(p[0]), y = Math.round(p[1]);
      placed.forEach(function(q){ if (Math.abs(q[0] - x) < 130 && Math.abs(q[1] - y) < 19) y = q[1] + 19; });   // two dots close together: stack the badges
      placed.push([x, y]);
      e.hidden = false; e.style.display = ""; e.style.left = x + "px"; e.style.top = y + "px";
      e.textContent = "IZ " + pctText(iz.pct) + " · rule-based"; e.title = badgeText(m, iz, b);
    });
  }
  /* ---------- the provider ---------- */
  function build(c){
    ctx = c; api = c.api; index();
    var fill = c.el("div", {class:"inn-fill"}), stage = c.el("div", {class:"inn-stage"}), slot = c.el("div", {class:"mslot inn-slot"});
    var side = c.el("aside", {class:"inn-side mi", dir:"ltr", "aria-label":"Muscle innervation"});
    stage.appendChild(slot);
    var ctl = c.el("section", {class:"inn-card inn-ctl"});
    ctl.innerHTML = '<div class="inn-row"><span class="inn-lb">Colour by</span><div class="inn-seg" role="group"><button type="button" data-by="nerve">Nerve</button><button type="button" data-by="root">Root level</button></div></div>' +
      '<div class="inn-legend"></div><div class="inn-row"><span class="inn-lb">IZ markers</span><div class="inn-seg" role="group"><button type="button" data-iz="sel">Selected</button><button type="button" data-iz="all">All</button><button type="button" data-iz="off">Off</button></div></div>' +
      '<p class="inn-rule"></p>';
    var panel = c.el("section", {class:"inn-card inn-panel", "aria-live":"polite"});
    side.appendChild(ctl); side.appendChild(panel); fill.appendChild(stage); fill.appendChild(side); c.main.appendChild(fill);
    ui = {fill:fill, slot:slot, side:side, ctl:ctl, panel:panel, legend:ctl.querySelector(".inn-legend"), rule:ctl.querySelector(".inn-rule")};
    ctl.addEventListener("click", function(e){
      var b = e.target.closest("button"); if (!b) return;
      if (b.hasAttribute("data-by")) setBy(b.getAttribute("data-by"));
      else if (b.hasAttribute("data-iz")) setIz(b.getAttribute("data-iz"));
      else if (b.getAttribute("data-kind") === "trunk") pickTrunk(b.getAttribute("data-key"));
      else if (b.getAttribute("data-kind") === "root") pickRoot(b.getAttribute("data-key"));
    });
    panel.addEventListener("click", function(e){ var b = e.target.closest("button[data-sel]"); if (b) ctx.select(b.getAttribute("data-sel")); });
  }
  function enter(c){
    on = true;
    c.modelDock([ui.slot], 62);              // below the quick card (z 64), which still opens on a click
    var C = sel();
    st.saved = C && C.snapshot ? C.snapshot() : null;
    try { var seen = {}; (api.list() || []).forEach(function(r){ if (r.cat && !seen[r.cat]){ seen[r.cat] = 1; var want = !!KEEP[r.cat]; if (!!api.categoryOn(r.cat) !== want) api.setCategoryOn(r.cat, want); } }); } catch (e){}
    if (C){ C.markIds([], true, true, true); }
    st.pick = null; st.view = null; st.lastSel = undefined;
    applyColours(); legend(); render(); follow();
    if (!hooked && api.webgl && api.webgl.onAfterDraw){ api.webgl.onAfterDraw(function(g){ try { draw(g); } catch (e){ on = false; console.error("innervation markers:", e); } }); hooked = true; }
    if (api.redraw) api.redraw();
  }
  function exit(){
    on = false; tags([]);
    var C = sel();
    if (C && st.saved) C.restore(st.saved);   // the user's own colours and marks back (the controller then restores the rest)
    st.saved = null; st.pick = null; st.view = null; ui = {};
    if (api && api.redraw) api.redraw();
  }
  function reset(){ st.by = "nerve"; st.iz = "sel"; clearPick(); st.view = null; applyColours(); legend(); render(); }
  var provider = {title:"Muscle innervation", short:"Innervation", build:build, enter:enter, exit:exit, refresh:function(){ if (on) follow(); }, reset:reset};
  function boot(){
    if (!window.NMSKModes || !window.fetch) { if (window.fetch) setTimeout(boot, 300); return; }
    fetch(URL).then(function(r){ if (!r.ok) throw new Error("no " + URL); return r.json(); }).then(function(j){
      if (!j || j.schema !== "nmsk.innervation.page.v1") return;
      D = j; NMSKModes.register("inn", provider);
    }).catch(function(){});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else setTimeout(boot, 0);
  window.__innState = function(){
    return {loaded:!!D, on:on, by:st.by, iz:st.iz, pick:st.pick ? {kind:st.pick.kind, key:st.pick.key, n:st.pick.muscles.length} : null,
            view:st.view ? {kind:st.view.kind, key:st.view.key || st.view.id, side:st.view.side || null} : null, drawn:drawn,
            tags:mk.filter(function(e){ return !e.hidden; }).length, counts:D ? D.counts : null};
  };
  /* test / harness hooks: the screen point of a structure (its mesh centre, projected) and the page's own select (as the panel's list uses) */
  function screenOf(id){
    if (!api || !IX || !IX.byId[id]) return null;
    var r = IX.byId[id], g = null, p;
    try { g = api.geometry ? api.geometry(r.i) : null; } catch (e){ g = null; }
    if (g && g.pos && g.pos.length){ var n = g.pos.length / 3, s = [0, 0, 0]; for (var i = 0; i < g.pos.length; i += 3){ s[0] += g.pos[i]; s[1] += g.pos[i + 1]; s[2] += g.pos[i + 2]; } p = [s[0] / n, s[1] / n, s[2] / n]; }
    else p = [(r.bmin[0] + r.bmax[0]) / 2, (r.bmin[1] + r.bmax[1]) / 2, (r.bmin[2] + r.bmax[2]) / 2];
    return api.toScreen ? api.toScreen(p) : null;
  }
  return {data:function(){ return D; }, pickTrunk:pickTrunk, pickRoot:pickRoot, setBy:setBy, setIz:setIz, screenOf:screenOf,
          select:function(id){ if (on && ctx) ctx.select(id); }};
})();
