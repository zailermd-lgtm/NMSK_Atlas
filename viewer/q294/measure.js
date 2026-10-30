/* Q294: measurement tools -- point-to-point distance, 3-point angle, angle between two lines, Cobb angle -- on the 3-D model of
   either engine and on any 2-D image pane an optional add-on registers (CT / MR / echo panes: NMSKMeasure.surface(el, adaptor)).
   Pure math in NMSKMeasureCore (no DOM, runs under node). Points are kept in each surface's own millimetre frame (3-D: the
   model frame; a 2-D pane: its image plane), so a value never depends on the zoom, the pan or the window size.
     NMSKMeasure.surface(el, {name, toMM(ev) -> [x, y] | null, fromMM([x, y]) -> [clientX, clientY] | null})   a 2-D pane
     NMSKMeasure.start(api, {toolbar, cls})   the 3-D model through the generic add-on API (pick / ray / toScreen / geometry)
     ctl.consumeClick(ev)   the engine's tap handler asks first: true = the tap placed (or tried to place) a measurement point
     ctl.arm(kind) kind = dist | ang3 | ang2 | cobb | null    ctl.add(kind, surfaceId, pts)   ctl.clear()   ctl.remove(id)   ctl.state()
   Cobb: two lines along the two endplates; the Cobb angle is the angle between them (= the angle between their perpendiculars),
   0-90 deg. On the 3-D model the angle between the two 3-D lines is given, plus the angle in the current view plane (what a
   radiograph taken along the view direction would show). Results: one small chip per measurement on the image and in the bar. */
var NMSKMeasureCore = (function(){
  "use strict";
  var D = 180 / Math.PI;
  function sub(a, b){ return a.map(function(x, i){ return x - b[i]; }); }
  function dot(a, b){ var s = 0; for (var i = 0; i < a.length; i++) s += a[i] * b[i]; return s; }
  function len(a){ return Math.sqrt(dot(a, a)); }
  function dist(a, b){ return len(sub(a, b)); }
  function angleBetween(u, v){ var l = len(u) * len(v); if (!(l > 1e-12)) return NaN; return Math.acos(Math.max(-1, Math.min(1, dot(u, v) / l))) * D; }
  function angle3(a, b, c){ return angleBetween(sub(a, b), sub(c, b)); }                     // the angle at b
  function lineAngle(a1, a2, b1, b2){ var t = angleBetween(sub(a2, a1), sub(b2, b1)); return t > 90 ? 180 - t : t; }   // 0..90 (lines have no direction)
  function project(p, n){ var k = dot(p, n) / dot(n, n); return p.map(function(x, i){ return x - k * n[i]; }); }
  function cobb(a1, a2, b1, b2, viewN){
    var r = {deg:lineAngle(a1, a2, b1, b2)};
    r.perp = r.deg;                                                                          // perpendiculars of two lines in one plane meet at the same angle
    if (viewN && a1.length === 3) r.view = lineAngle(project(a1, viewN), project(a2, viewN), project(b1, viewN), project(b2, viewN));
    return r;
  }
  var NEED = {dist:2, ang3:3, ang2:4, cobb:4}, NAME = {dist:"Distance", ang3:"Angle (3 points)", ang2:"Angle between 2 lines", cobb:"Cobb angle"};
  function value(kind, p, viewN){
    if (!p || p.length < NEED[kind]) return null;
    if (kind === "dist") return {v:dist(p[0], p[1]), unit:"mm"};
    if (kind === "ang3") return {v:angle3(p[0], p[1], p[2]), unit:"deg"};
    if (kind === "ang2") return {v:lineAngle(p[0], p[1], p[2], p[3]), unit:"deg"};
    if (kind === "cobb"){ var c = cobb(p[0], p[1], p[2], p[3], viewN); return {v:c.deg, unit:"deg", view:c.view}; }
    return null;
  }
  function label(kind, r){
    if (!r || !isFinite(r.v)) return "";
    var s = r.unit === "mm" ? r.v.toFixed(1) + " mm" : r.v.toFixed(1) + "°";
    if (kind === "cobb") s = "Cobb " + s + (r.view != null && isFinite(r.view) && Math.abs(r.view - r.v) >= 0.1 ? " (view " + r.view.toFixed(1) + "°)" : "");
    return s;
  }
  /* ray (o, d) x triangle mesh (pos Float32 xyz, idx) -> nearest t > 0 or null (Moller-Trumbore) */
  function rayMesh(o, d, pos, idx){
    var best = null, nt = idx.length / 3;
    for (var k = 0; k < nt; k++){
      var a = idx[3*k] * 3, b = idx[3*k+1] * 3, c = idx[3*k+2] * 3;
      var e1x = pos[b] - pos[a], e1y = pos[b+1] - pos[a+1], e1z = pos[b+2] - pos[a+2], e2x = pos[c] - pos[a], e2y = pos[c+1] - pos[a+1], e2z = pos[c+2] - pos[a+2];
      var px = d[1]*e2z - d[2]*e2y, py = d[2]*e2x - d[0]*e2z, pz = d[0]*e2y - d[1]*e2x, det = e1x*px + e1y*py + e1z*pz;
      if (Math.abs(det) < 1e-12) continue;
      var inv = 1 / det, tx = o[0] - pos[a], ty = o[1] - pos[a+1], tz = o[2] - pos[a+2], u = (tx*px + ty*py + tz*pz) * inv;
      if (u < 0 || u > 1) continue;
      var qx = ty*e1z - tz*e1y, qy = tz*e1x - tx*e1z, qz = tx*e1y - ty*e1x, v = (d[0]*qx + d[1]*qy + d[2]*qz) * inv;
      if (v < 0 || u + v > 1) continue;
      var t = (e2x*qx + e2y*qy + e2z*qz) * inv;
      if (t > 1e-6 && (best == null || t < best)) best = t;
    }
    return best;
  }
  return {dist:dist, angle3:angle3, lineAngle:lineAngle, cobb:cobb, value:value, label:label, rayMesh:rayMesh, NEED:NEED, NAME:NAME};
})();
var NMSKMeasure = (function(){
  "use strict";
  var tbEl = null, C = NMSKMeasureCore, surf = {}, sid = 0, api = null, tool = null, pend = null, list = [], seq = 0, raf = 0, svg = null, bar = null, tb = null, geoCache = [], msg = "";
  var SVGNS = "http://www.w3.org/2000/svg";
  function $(id){ return document.getElementById(id); }
  function r1(v){ return Math.round(v * 100) / 100; }
  function surface(el, ad){
    if (!el || !ad) return null;
    var id = el.getAttribute("data-ms-id"); if (!id){ id = "p" + (++sid); el.setAttribute("data-ms-id", id); }
    surf[id] = {id:id, el:el, name:ad.name || "image", toMM:ad.toMM, fromMM:ad.fromMM, two:true};
    var down = null;
    function armedHere(){ return tool && (!pend || pend.s === id); }
    function onBtn(e){ return !!(e.target && e.target.closest && e.target.closest(".ms-pane-b")); }
    if (!el.querySelector(".ms-pane-b")){                 // a small ruler on the pane itself: measuring works even when a panel covers the toolbar
      var pb = document.createElement("button"); pb.type = "button"; pb.className = "ms-pane-b"; pb.title = "Measure on this image (distance, angles, Cobb)"; pb.setAttribute("aria-label", "Measure on this image");
      pb.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M3 17L17 3l4 4L7 21zM7 13l2 2M10 10l2 2M13 7l2 2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
      ["pointerdown", "pointerup"].forEach(function(t){ pb.addEventListener(t, function(e){ e.stopPropagation(); }); });   // the pane's own handlers (crosshair, pointer capture) never see a tap on the button
      pb.addEventListener("click", function(e){ e.stopPropagation(); if (bar && bar.hidden){ open(true); if (!tool) arm("dist"); } else open(false); });
      el.appendChild(pb);
    }
    el.addEventListener("pointerdown", function(e){ if (onBtn(e)) return; if (!armedHere() || (e.pointerType === "mouse" && e.button !== 0)) return; if (down && down.id !== e.pointerId){ down = null; return; } down = {id:e.pointerId, x:e.clientX, y:e.clientY}; e.stopPropagation(); }, true);
    el.addEventListener("pointermove", function(e){ if (down && down.id === e.pointerId) e.stopPropagation(); }, true);
    el.addEventListener("pointerup", function(e){
      if (!down || down.id !== e.pointerId) return;
      var d0 = down; down = null; e.stopPropagation();
      if (Math.hypot(e.clientX - d0.x, e.clientY - d0.y) > 8 || !armedHere()) return;
      var p = surf[id].toMM(e); if (!p){ say("Tap inside the image."); return; }
      addPoint(id, p.slice(0, 2));
    }, true);
    el.addEventListener("click", function(e){ if (tool && !onBtn(e)) { e.stopPropagation(); e.preventDefault(); } }, true);
    return id;
  }
  /* ---- the 3-D model ---- */
  function geom(i){
    for (var k = 0; k < geoCache.length; k++) if (geoCache[k].i === i) return geoCache[k].g;
    var g = null; try { g = api.geometry ? api.geometry(i) : null; } catch (err){ g = null; }
    geoCache.push({i:i, g:g}); if (geoCache.length > 6) geoCache.shift();
    return g;
  }
  function point3(e){
    var h = null; try { h = api.pick(e); } catch (err){ h = null; }
    if (!h) return null;
    if (h.point) return h.point.slice();
    var g = h.i != null ? geom(h.i) : null, r = api.ray(e);
    if (!g || !r) return null;
    var t = C.rayMesh(r.o, r.d, g.pos, g.idx);
    return t == null ? null : [r.o[0] + r.d[0] * t, r.o[1] + r.d[1] * t, r.o[2] + r.d[2] * t];
  }
  function viewN(){ try { var v = api.view(); return v && v.dir ? v.dir : null; } catch (err){ return null; } }
  function consumeClick(e){
    if (!tool || !api) return false;
    if (pend && pend.s !== "3d"){ say("Finish this measurement on the same image first."); return true; }
    var p = point3(e);
    if (!p){ say("Nothing under the pointer: tap on the model."); return true; }
    addPoint("3d", p.map(r1));
    return true;
  }
  function addPoint(s, p){
    if (!pend) pend = {s:s, p:[]};
    pend.p.push(p);
    if (pend.p.length >= C.NEED[tool]){
      var m = {id:"m" + (++seq), k:tool, s:pend.s, p:pend.p.map(function(q){ return q.map(r1); })};
      list.push(m); pend = null;
      say(C.NAME[m.k] + ": " + C.label(m.k, valueOf(m)) + ". Tap again for another, or pick another tool.");
      if (window.NMSKHistory && NMSKHistory.active()) NMSKHistory.commit();
    } else say(C.NAME[tool] + ": point " + (pend.p.length + 1) + " of " + C.NEED[tool] + (tool === "cobb" ? (pend.p.length < 2 ? " (first endplate line)" : " (second endplate line)") : "") + ".");
    render(); kick();
  }
  function valueOf(m){ return C.value(m.k, m.p, m.s === "3d" ? viewN() : null); }
  /* ---- drawing: one fixed SVG over the page; each surface gets a nested <svg> on its own rectangle (it clips to it) ---- */
  function ensureSvg(){
    if (svg) return svg;
    svg = document.createElementNS(SVGNS, "svg"); svg.setAttribute("id", "ms-svg"); svg.setAttribute("class", "ms-svg"); svg.setAttribute("aria-hidden", "true");
    document.body.appendChild(svg); return svg;
  }
  function toClient(s, p){
    if (s === "3d") return api ? api.toScreen(p) : null;
    var S = surf[s]; if (!S) return null;
    try { return S.fromMM(p); } catch (err){ return null; }
  }
  function rectOf(s){
    var e = s === "3d" ? (api && api.canvas) : (surf[s] && surf[s].el);
    if (!e || !e.getBoundingClientRect) return null;
    var r = e.getBoundingClientRect(); if (!(r.width > 2 && r.height > 2)) return null;
    if (e.offsetParent === null && getComputedStyle(e).position !== "fixed") return null;
    return r;
  }
  function draw(){
    raf = 0; ensureSvg();
    var groups = {}, h = "";
    list.concat(pend ? [{id:"pend", k:tool, s:pend.s, p:pend.p, pend:true}] : []).forEach(function(m){ (groups[m.s] = groups[m.s] || []).push(m); });
    Object.keys(groups).forEach(function(s){
      var R = rectOf(s); if (!R) return;
      var g = "";
      groups[s].forEach(function(m){
        var q = m.p.map(function(p){ var c = toClient(s, p); return c ? [c[0] - R.left, c[1] - R.top] : null; });
        if (q.some(function(x){ return !x; })) return;
        var cls = "ms-l" + (m.pend ? " ms-pend" : "");
        function ln(a, b){ return '<line class="' + cls + '" x1="' + a[0].toFixed(1) + '" y1="' + a[1].toFixed(1) + '" x2="' + b[0].toFixed(1) + '" y2="' + b[1].toFixed(1) + '"/>'; }
        if (m.k === "dist" && q.length >= 2) g += ln(q[0], q[1]);
        if (m.k === "ang3"){ if (q.length >= 2) g += ln(q[0], q[1]); if (q.length >= 3) g += ln(q[1], q[2]); }
        if ((m.k === "ang2" || m.k === "cobb")){ if (q.length >= 2) g += ln(q[0], q[1]); if (q.length >= 4) g += ln(q[2], q[3]); }
        if (m.k === "cobb" && q.length >= 4){                       // the perpendiculars, faint, from each line's midpoint
          [[q[0], q[1]], [q[2], q[3]]].forEach(function(L){ var mx = (L[0][0] + L[1][0]) / 2, my = (L[0][1] + L[1][1]) / 2, dx = L[1][0] - L[0][0], dy = L[1][1] - L[0][1], l = Math.hypot(dx, dy) || 1;
            g += '<line class="ms-perp" x1="' + mx.toFixed(1) + '" y1="' + my.toFixed(1) + '" x2="' + (mx - dy / l * 40).toFixed(1) + '" y2="' + (my + dx / l * 40).toFixed(1) + '"/>'; });
        }
        q.forEach(function(c){ g += '<circle class="ms-pt' + (m.pend ? " ms-pend" : "") + '" cx="' + c[0].toFixed(1) + '" cy="' + c[1].toFixed(1) + '" r="4"/>'; });
        if (!m.pend){
          var t = C.label(m.k, valueOf(m)), at = m.k === "ang3" ? q[1] : m.k === "dist" ? [(q[0][0] + q[1][0]) / 2, (q[0][1] + q[1][1]) / 2] : [(q[0][0] + q[1][0] + q[2][0] + q[3][0]) / 4, (q[0][1] + q[1][1] + q[2][1] + q[3][1]) / 4];
          var w = 7 * t.length + 12;
          g += '<g class="ms-chip" data-mid="' + m.id + '"><rect x="' + (at[0] + 8).toFixed(1) + '" y="' + (at[1] - 22).toFixed(1) + '" width="' + w + '" height="18" rx="9"/><text x="' + (at[0] + 14).toFixed(1) + '" y="' + (at[1] - 9).toFixed(1) + '">' + t + '</text></g>';
        }
      });
      h += '<svg x="' + R.left.toFixed(1) + '" y="' + R.top.toFixed(1) + '" width="' + R.width.toFixed(1) + '" height="' + R.height.toFixed(1) + '">' + g + '</svg>';
    });
    svg.innerHTML = h;
    svg.style.display = h ? "block" : "none";
    if (list.length || pend) kick();
  }
  function kick(){ if (!raf && typeof requestAnimationFrame !== "undefined") raf = requestAnimationFrame(function(){ raf = setTimeout(draw, 40); }); }
  /* ---- the bar ---- */
  function say(m){ msg = m || ""; var e = $("ms-msg"); if (e) e.textContent = msg; }
  function render(){
    if (!bar) return;
    Array.prototype.forEach.call(bar.querySelectorAll("[data-ms]"), function(b){ b.setAttribute("aria-pressed", String(b.getAttribute("data-ms") === tool)); });
    var ch = $("ms-res"), h = "";
    list.forEach(function(m){ h += '<span class="ms-r" data-mid="' + m.id + '"><span>' + C.label(m.k, valueOf(m)) + '</span><button type="button" data-del="' + m.id + '" aria-label="Remove this measurement" title="Remove">&times;</button></span>'; });
    if (ch) ch.innerHTML = h;
    var cl = $("ms-clear"); if (cl) cl.disabled = !list.length && !pend;
    if (tb){ tb.setAttribute("aria-pressed", String(!bar.hidden)); tb.textContent = list.length ? "Measure · " + list.length : "Measure"; }
    document.body.classList.toggle("ms-armed", !!tool);
  }
  function arm(k){
    tool = k && C.NEED[k] ? k : null; pend = null;
    say(tool ? C.NAME[tool] + ": tap point 1 of " + C.NEED[tool] + " on the model or on an image pane." : "");
    render(); kick();
  }
  function remove(id){ var n = list.length; list = list.filter(function(m){ return m.id !== id; }); if (list.length !== n && window.NMSKHistory && NMSKHistory.active()) NMSKHistory.commit(); render(); kick(); }
  function clear(){ list = []; pend = null; render(); kick(); if (window.NMSKHistory && NMSKHistory.active()) NMSKHistory.commit(); say("Measurements cleared (Undo brings them back)."); }
  function place(){                                     // right under the toolbar (phones: the bottom belongs to the structure card / sheets)
    if (!bar || bar.hidden) return;
    var t = tbEl && tbEl.getBoundingClientRect ? tbEl.getBoundingClientRect() : null;
    if (t && t.height > 0){ bar.style.top = Math.round(Math.min(window.innerHeight * 0.5, t.bottom + 6)) + "px"; bar.style.bottom = "auto"; }   // never over the toolbar
    else { bar.style.top = ""; bar.style.bottom = ""; }
    var c = api && api.canvas && api.canvas.getBoundingClientRect ? api.canvas.getBoundingClientRect() : null;   // desktop: at the 3-D view's left edge, so an image pane beside it stays clear
    if (window.innerWidth > 560 && c && c.width > 200){ bar.style.left = Math.round(Math.max(8, c.left + 8)) + "px"; bar.style.transform = "none"; bar.style.maxWidth = Math.round(Math.max(260, c.width - 16)) + "px"; }
    else { bar.style.left = ""; bar.style.transform = ""; bar.style.maxWidth = ""; }
  }
  function open(v){
    if (!bar) return; bar.hidden = !v; if (!v) arm(null); render(); place();
  }
  function buildBar(){
    bar = document.createElement("div"); bar.id = "ms-bar"; bar.className = "ms-bar"; bar.hidden = true; bar.setAttribute("role", "toolbar"); bar.setAttribute("aria-label", "Measure");
    bar.innerHTML = '<div class="ms-row">' +
      '<button type="button" data-ms="dist" aria-pressed="false" title="Distance between two points (mm)"><b>&#8596;</b> mm</button>' +
      '<button type="button" data-ms="ang3" aria-pressed="false" title="Angle at the middle one of three points"><b>&ang;</b> 3 pts</button>' +
      '<button type="button" data-ms="ang2" aria-pressed="false" title="Angle between two lines (two points each)"><b>&ang;</b> 2 lines</button>' +
      '<button type="button" data-ms="cobb" aria-pressed="false" title="Cobb angle: draw one line along each endplate; the angle between them = between their perpendiculars"><b>&ang;</b> Cobb</button>' +
      '<button type="button" id="ms-clear" title="Remove every measurement (undoable)">Clear</button>' +
      '<button type="button" id="ms-close" aria-label="Close the measure bar" title="Close">&times;</button></div>' +
      '<p id="ms-msg" class="ms-msg" aria-live="polite"></p><div id="ms-res" class="ms-res"></div>';
    document.body.appendChild(bar);
    Array.prototype.forEach.call(bar.querySelectorAll("[data-ms]"), function(b){ b.addEventListener("click", function(){ var k = b.getAttribute("data-ms"); arm(tool === k ? null : k); }); });
    $("ms-clear").addEventListener("click", clear);
    $("ms-close").addEventListener("click", function(){ open(false); });
    $("ms-res").addEventListener("click", function(e){ var b = e.target.closest ? e.target.closest("[data-del]") : null; if (b) remove(b.getAttribute("data-del")); });
  }
  function start(a, opt){
    api = a; opt = opt || {}; tbEl = opt.toolbar || null;
    buildBar(); window.addEventListener("resize", place);
    if (opt.toolbar){
      tb = document.createElement("button"); tb.type = "button"; tb.id = "t-measure"; tb.className = (opt.cls || "") + " ms-tb"; tb.textContent = "Measure";
      tb.title = "Measure: distance, 3-point angle, angle between two lines, Cobb angle -- on the model and on the image panes";
      tb.setAttribute("aria-pressed", "false"); tb.addEventListener("click", function(){ open(bar.hidden); });
      opt.toolbar.appendChild(tb);
    }
    surf["3d"] = {id:"3d", el:a.canvas, name:"3-D model", two:false};
    if (window.NMSKHistory) NMSKHistory.register("measure", {
      get:function(){ return list.map(function(m){ return {k:m.k, s:m.s, p:m.p}; }); },
      set:function(v){ seq = 0; list = (v || []).map(function(m){ return {id:"m" + (++seq), k:m.k, s:m.s, p:m.p.map(function(q){ return q.slice(); })}; }); pend = null; render(); kick(); },
      reset:function(){ list = []; pend = null; tool = null; if (bar) bar.hidden = true; render(); kick(); }
    });
    render();
    return ctl;
  }
  var ctl = {
    consumeClick:consumeClick, arm:arm, open:open, clear:clear, remove:remove,
    add:function(kind, s, pts){ if (!C.NEED[kind] || !pts || pts.length !== C.NEED[kind]) return null; tool = kind; pend = null; pts.forEach(function(p){ addPoint(s || "3d", p); }); tool = null; render(); return list[list.length - 1]; },
    surfaces:function(){ return Object.keys(surf).map(function(k){ return {id:k, name:surf[k].name, two:!!surf[k].two}; }); },
    state:function(){ return {tool:tool, open:!!(bar && !bar.hidden), pending:pend ? {s:pend.s, n:pend.p.length} : null, msg:msg,
      list:list.map(function(m){ var r = valueOf(m); return {id:m.id, kind:m.k, surface:m.s, pts:m.p, value:r ? r.v : null, view:r && r.view != null ? r.view : null, unit:r ? r.unit : null, label:C.label(m.k, r)}; })}; },
    redraw:kick
  };
  return {surface:surface, start:start, ctl:ctl, core:C};
})();
