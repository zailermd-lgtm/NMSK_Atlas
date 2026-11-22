/* Q386: owner (translated from Hebrew): "All the windows must also be allowed to shrink or grow in screen area, and scroll as needed,
   and control of the font size."
   Added from the outside, on top of the box machinery of Q305 / Q382 (viewer/q305/move.js knows every box; this module reads its list):
     - SIZE: a grip at the lower-right corner of every box (a small fixed overlay that follows the box, so it is never clipped or scrolled
       away with the box's content) drags the box's width and height, within a minimum and the viewport. A box that has been resized
       (or has a text size) scrolls inside (overflow:auto) -- nothing is cut off without a way to reach it. Double-click the grip: back to
       the box's own size. Desktop only: on a phone the boxes are docked sheets.
     - TEXT SIZE: the pages' text is px-based, so a size is a CSS `zoom` on the box's direct children (text, padding and icons together, the
       layout inside keeps its proportions; the engine canvas is never touched). A box takes the GLOBAL size (Settings) unless it has its own
       (A- / A+ beside the grip, the box's three-dots menu, or Settings). Steps of 10 %, 80-160 %. Nothing is shown under the 10 px floor
       of Q344: a box whose smallest text is already near it cannot shrink below the factor that keeps it at 10 px.
     - a box that would reach past the screen at its size / text size is held to the viewport (--q386-mh / --q386-mw), and scrolls.
   Saved per screen class in localStorage (try / catch; the page works without it). Lock (NMSKMove.lock) stops resizing as well; Reset layout
   (NMSKLayout.reset) puts sizes and the per-box text sizes back. Nothing here names a clinical box: the list comes from NMSKMove.
     NMSKResize.global()  .setGlobal(p)  .box(k)  .setBox(k, p|null)  .boxes()  .resetSizes()  .reset()  .state() */
var NMSKResize = (function(){
  "use strict";
  var SKEY = "nmsk.q386.size", FKEY = "nmsk.q386.font", STEPS = [80, 90, 100, 110, 120, 130, 140, 150, 160];
  var FLOOR = 10, MINW = 150, MINH = 90, PADV = 12;
  /* bars and rows are not windows: they keep their own size and text */
  var NOT = {control:1, hidden:1, pills:1, "m-dock":1};
  /* windows the box registry does not list: the open group sheet (it travels with the control bar, so it only gets a text size) */
  var EXTRA = [{key:"sheet", label:"the open group sheet", sel:"#q301-sheet", fontOnly:true}];
  function extra(k){ for (var i = 0; i < EXTRA.length; i++) if (EXTRA[i].key === k) return EXTRA[i]; return null; }
  var sizes = {}, fonts = {g:100, b:{}}, ov = {}, drag = null, ready = false, timer = 0, ptr = null, lastCls = null;

  function M(){ return window.NMSKMove && NMSKMove.state && NMSKMove.state().on ? window.NMSKMove : null; }
  function vw(){ return Math.max(1, window.innerWidth || document.documentElement.clientWidth || 1); }
  function vh(){ return Math.max(1, window.innerHeight || document.documentElement.clientHeight || 1); }
  function phone(){ var m = M(); return !!(m && m.phone()); }
  function sKey(){ return phone() ? SKEY + ".phone" : SKEY; }
  function rd(k){ try { var t = localStorage.getItem(k); if (t){ var j = JSON.parse(t); if (j && typeof j === "object") return j; } } catch (e){} return null; }
  function wr(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch (e){} }
  function loadSizes(){ sizes = rd(sKey()) || {}; }
  function loadFonts(){
    var j = rd(FKEY) || {}; fonts = {g:100, b:{}};
    if (STEPS.indexOf(+j.g) >= 0) fonts.g = +j.g;
    if (j.b && typeof j.b === "object") Object.keys(j.b).forEach(function(k){ if (STEPS.indexOf(+j.b[k]) >= 0) fonts.b[k] = +j.b[k]; });
  }
  function saveSizes(){ wr(sKey(), sizes); }
  function saveFonts(){ wr(FKEY, fonts); }

  function elOf(k){
    var x = extra(k); if (x) return document.querySelector(x.sel);
    var m = M(), b = m && m.box(k); if (!b) return null;
    return typeof b.el === "function" ? b.el() : document.getElementById(b.el);
  }
  function labelOf(k){ var x = extra(k); if (x) return x.label; var m = M(), b = m && m.box(k); return b ? (b.label || k) : k; }
  function keys(){ var m = M(); return m ? m.keys().filter(function(k){ return !NOT[k]; }).concat(EXTRA.map(function(x){ return x.key; })) : []; }
  function sizable(k){ var x = extra(k); return !(x && x.fontOnly); }
  function shown(e){
    if (!e || !e.getBoundingClientRect) return false;
    var r = e.getBoundingClientRect();
    return r.width > 8 && r.height > 8 && r.right > 0 && r.bottom > 0 && r.left < vw() && r.top < vh();
  }
  function pctOf(k){ return fonts.b[k] || fonts.g; }

  /* the smallest text in a box at factor 1, so the 10 px floor can be kept at any factor */
  function minText(e){
    if (e._q386m && Date.now() - e._q386m.t < 2500) return e._q386m.v;
    var m = 99, all = e.querySelectorAll("*"), n = 0, i, x, f;
    for (i = 0; i < all.length && n < 3000; i++, n++){
      x = all[i];
      if (x.children.length > 0 && !x.firstChild) continue;
      if (!/\S/.test(x.textContent || "") || /^(SCRIPT|STYLE|SVG|PATH|CANVAS)$/i.test(x.tagName)) continue;
      f = parseFloat(getComputedStyle(x).fontSize);
      if (f && f < m) m = f;
    }
    if (m === 99) m = 12;
    e._q386m = {t:Date.now(), v:m};
    return m;
  }
  function factorOf(k, e){
    var f = pctOf(k) / 100;
    if (f < 1){ var m = Math.max(FLOOR, minText(e)); f = Math.max(f, FLOOR / m); if (f > 1) f = 1; }
    return f;
  }

  /* hold the box to the screen: clear our limit, measure, tighten */
  function fit(e){
    e.style.removeProperty("--q386-mh"); e.style.removeProperty("--q386-mw");
    /* larger text makes the box as much wider as the text is larger (so what wrapped at 100 % wraps the same), up to the screen */
    if (e._q386want) e.style.setProperty("--q386-w0", Math.round(Math.min(e._q386want, vw() - 2 * PADV)) + "px"); else e.style.removeProperty("--q386-w0");
    var r = e.getBoundingClientRect();
    if (!(r.width > 0)) return;
    var pd = phone() ? 0 : PADV;                               /* docked sheets are full-bleed on a phone: held to the edge, not inset from it */
    var ex = r.bottom - (vh() - pd), ey = pd - r.top;
    if (ex > 0 && r.top < vh()) e.style.setProperty("--q386-mh", Math.max(MINH, Math.round(r.height - ex)) + "px");
    else if (ey > 0) e.style.setProperty("--q386-mh", Math.max(MINH, Math.round(r.height - ey)) + "px");
    var rx = r.right - (vw() - pd), lx = pd - r.left, ex2 = Math.max(rx, lx), nw;
    if (!(ex2 > 0)) return;
    nw = Math.max(MINW, Math.round(r.width - ex2));
    e.style.setProperty("--q386-mw", nw + "px");
    if (e._q386want) e.style.setProperty("--q386-w0", Math.min(Math.round(e._q386want), nw) + "px");
  }

  function applyBox(k, nofit){
    var e = elOf(k); if (!e) return;
    var s = (phone() || !sizable(k)) ? null : sizes[k], f = factorOf(k, e), z = Math.abs(f - 1) > 0.001;
    var key = (s ? s.w + "x" + s.h : "-") + "|" + (z ? f.toFixed(3) : "-") + "|" + vw() + "x" + vh();
    var was = e._q386k, needW = false;
    if (was === key && !(z || s)) return;
    if (s){
      e.classList.add("q386-s");
      e.style.setProperty("--q386-w", Math.round(s.w) + "px"); e.style.setProperty("--q386-h", Math.round(s.h) + "px");
    } else {
      e.classList.remove("q386-s"); e.style.removeProperty("--q386-w"); e.style.removeProperty("--q386-h");
    }
    if (was !== key){
      /* the box's width at 100 % text, measured with the scaling off */
      var w0 = 0; needW = z && f > 1 && !s && !phone();
      if (needW){
        e.classList.remove("q386-f"); e.style.removeProperty("--q386-w0"); e.style.removeProperty("--q386-mw");
        w0 = e.getBoundingClientRect().width * f;
      }
      e._q386want = w0 > 0 ? w0 : 0;
    }
    if (z){ e.classList.add("q386-f"); e.style.setProperty("--q386-z", f.toFixed(3)); }
    else { e.classList.remove("q386-f"); e.style.removeProperty("--q386-z"); }
    if (nofit){}
    else if (s || z){ if (was !== key || (shown(e) && !drag)) fit(e); }
    else { e.style.removeProperty("--q386-mh"); e.style.removeProperty("--q386-mw"); }
    e._q386k = (needW && !e._q386want) ? undefined : key;      /* a box that is not on the screen yet is measured when it comes */
  }
  function applyAll(){ keys().forEach(function(k){ applyBox(k); }); }

  /* ---- the overlay: text size buttons and the resize grip, lower-right ---- */
  var GRIPSVG = '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M11 3L3 11M11 7L7 11M11 10.5L10.5 11" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" fill="none"/></svg>';
  function overlay(k){
    if (ov[k] && ov[k].isConnected) return ov[k];
    var d = document.createElement("div"); d.className = "q386-ov"; d.setAttribute("data-q386", k); d.hidden = true;
    var lab = labelOf(k);
    d.innerHTML = '<button type="button" class="q386-fa" aria-label="Smaller text in ' + lab + '" title="Smaller text">A&minus;</button>' +
                  '<button type="button" class="q386-fb" aria-label="Larger text in ' + lab + '" title="Larger text">A+</button>' +
                  '<div class="q386-rz" role="separator" aria-label="Resize ' + lab + '" title="Drag to resize ' + lab + ' (double-click: its own size)">' + GRIPSVG + '</div>';
    d.querySelector(".q386-fa").addEventListener("click", function(ev){ ev.stopPropagation(); step(k, -1); });
    d.querySelector(".q386-fb").addEventListener("click", function(ev){ ev.stopPropagation(); step(k, 1); });
    var g = d.querySelector(".q386-rz");
    g.addEventListener("pointerdown", function(ev){ down(k, g, ev); });
    g.addEventListener("pointermove", move);
    g.addEventListener("pointerup", up); g.addEventListener("pointercancel", up);
    g.addEventListener("lostpointercapture", up);
    g.addEventListener("dblclick", function(ev){ ev.preventDefault(); resetSize(k); });
    document.body.appendChild(d); ov[k] = d;
    return d;
  }
  function placeOverlays(){
    var m = M(); if (!m) return;
    var ph = phone(), lk = m.locked(), live = keys().filter(sizable);
    live.forEach(function(k){
      var e = elOf(k), d = ov[k];
      var ok = e && !ph && shown(e) && !(e.parentNode && e.parentNode.closest && e.parentNode.closest("[data-nm-hosted]"));
      if (!ok){ if (d) d.hidden = true; return; }
      d = overlay(k);
      var r = e.getBoundingClientRect();
      /* hidden when another box lies over this corner */
      var x = Math.min(vw() - 4, Math.max(2, r.right - 8)), y = Math.min(vh() - 4, Math.max(2, r.bottom - 8)), top = null, i, l;
      try { l = document.elementsFromPoint(x, y); } catch (er){ l = []; }
      for (i = 0; i < l.length; i++){ if (l[i].classList && l[i].classList.contains("q386-ov") || (l[i].closest && l[i].closest(".q386-ov"))) continue; top = l[i]; break; }
      var covered = !(top && (top === e || e.contains(top)));
      d.hidden = covered;
      if (covered) return;
      var rz = d.querySelector(".q386-rz"); rz.style.display = lk ? "none" : "";
      /* anchored by its lower-right corner, so the grip stays on the box's corner whether the A- / A+ buttons are showing or not */
      var zi = 30, n = e, q;                                     /* above the whole stacking context the box lives in */
      while (n && n.nodeType === 1){ q = parseInt(getComputedStyle(n).zIndex, 10); if (!isNaN(q) && q > zi) zi = q; n = n.parentNode; }
      d.style.zIndex = String(Math.min(2147483000, zi + 1));
      var hot = !!(ptr && ptr.x >= r.left - 4 && ptr.x <= r.right + 4 && ptr.y >= r.top - 4 && ptr.y <= r.bottom + 4) || (drag && drag.k === k);
      d.classList.toggle("q386-hot", hot);
      d.style.left = "auto"; d.style.top = "auto";
      d.style.right = Math.round(vw() - Math.min(vw() - 2, r.right - 3)) + "px";
      d.style.bottom = Math.round(vh() - Math.min(vh() - 2, r.bottom - 3)) + "px";
    });
    Object.keys(ov).forEach(function(k){ if (live.indexOf(k) < 0 && ov[k]) ov[k].hidden = true; });
  }

  /* ---- the resize drag ---- */
  function down(k, g, ev){
    var m = M(); if (!m || m.locked() || phone()) return;
    if (ev.button != null && ev.button !== 0) return;
    var e = elOf(k); if (!e) return;
    var r = e.getBoundingClientRect();
    drag = {k:k, g:g, id:ev.pointerId, x:ev.clientX, y:ev.clientY, w0:r.width, h0:r.height, l0:r.left, t0:r.top, moved:false};
    try { g.setPointerCapture(ev.pointerId); } catch (er){}
    document.documentElement.classList.add("q386-resizing");
    ev.preventDefault(); ev.stopPropagation();
  }
  function move(ev){
    if (!drag || drag.id !== ev.pointerId) return;
    var dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
    if (!drag.moved && Math.abs(dx) < 3 && Math.abs(dy) < 3) return;
    drag.moved = true;
    var w = Math.max(MINW, Math.min(vw() - 2 * PADV, drag.w0 + dx)), h = Math.max(MINH, Math.min(vh() - 2 * PADV, drag.h0 + dy));
    var o = sizes[drag.k] || {};
    sizes[drag.k] = {w:Math.round(w), h:Math.round(h), sx:o.sx || 0, sy:o.sy || 0};
    var e = elOf(drag.k); if (!e) return;
    applyBox(drag.k, true);
    /* keep the top-left corner where the user had it (a box the page anchors from the right or the bottom would otherwise grow the other way),
       and the whole box on the screen */
    var m = M(), r = e.getBoundingClientRect();
    var tl = Math.max(PADV, Math.min(drag.l0, vw() - PADV - r.width)), tt = Math.max(PADV, Math.min(drag.t0, vh() - PADV - r.height));
    if (m && (Math.abs(tl - r.left) > 0.5 || Math.abs(tt - r.top) > 0.5) && m.shift(drag.k, tl - r.left, tt - r.top)){
      /* what the box was shifted by to keep its corner, kept with the size so "its own size" can undo it */
      sizes[drag.k].sx += tl - r.left; sizes[drag.k].sy += tt - r.top;
    }
    fit(e);
    ev.preventDefault(); ev.stopPropagation();
    placeOverlays();
  }
  function up(ev){
    if (!drag || (ev && drag.id !== ev.pointerId)) return;
    var d = drag; drag = null;
    document.documentElement.classList.remove("q386-resizing");
    try { d.g.releasePointerCapture(d.id); } catch (er){}
    if (d.moved){ saveSizes(); var m = M(); if (m && m.keep) m.keep(); }
    placeOverlays();
  }
  document.addEventListener("pointerup", function(ev){ if (drag && drag.id === ev.pointerId) up(ev); }, true);
  document.addEventListener("pointercancel", function(ev){ if (drag && drag.id === ev.pointerId) up(ev); }, true);
  window.addEventListener("blur", function(){ if (drag) up(null); });

  /* ---- text size ---- */
  function step(k, dir){
    var i = STEPS.indexOf(pctOf(k)); if (i < 0) i = STEPS.indexOf(100);
    i = Math.max(0, Math.min(STEPS.length - 1, i + dir));
    api.setBox(k, STEPS[i]);
  }
  function resetSize(k){
    var s = sizes[k], m = M();
    if (s && m && (s.sx || s.sy)) m.shift(k, -s.sx, -s.sy);
    if (m && m.keep) m.keep();
    delete sizes[k]; saveSizes();
    var e = elOf(k); if (e){ delete e._q386k; applyBox(k); }
    var m = M(); if (m && m.apply) m.apply(k);
    placeOverlays();
  }
  function menuItems(k){
    if (phone() && false) return [];
    var cur = pctOf(k), own = fonts.b[k] != null;
    var out = [{head:"Text size: " + cur + " %" + (own ? "" : " (all boxes)")},
      {label:"Larger text", key:"font-up", run:function(){ step(k, 1); }},
      {label:"Smaller text", key:"font-down", run:function(){ step(k, -1); }}];
    if (own) out.push({label:"Use the all-boxes text size", key:"font-default", run:function(){ api.setBox(k, null); }});
    if (!phone() && sizes[k]) out.push({label:"Reset size", key:"size-reset", run:function(){ resetSize(k); }});
    return out;
  }

  function tick(){
    var m = M(); if (!m) return;
    var c = phone();
    if (lastCls !== c){ lastCls = c; loadSizes(); keys().forEach(function(k){ var e = elOf(k); if (e) delete e._q386k; }); }
    if (!drag) applyAll();
    placeOverlays();
  }
  function boot(){
    var m = M(); if (!m) return false;
    loadSizes(); loadFonts(); lastCls = phone();
    if (m.extraItems) m.extraItems(menuItems);
    applyAll();
    document.addEventListener("pointermove", function(ev){ ptr = {x:ev.clientX, y:ev.clientY, t:Date.now()}; }, {passive:true, capture:true});
    window.addEventListener("resize", function(){ keys().forEach(function(k){ var e = elOf(k); if (e) delete e._q386k; }); setTimeout(tick, 30); });
    timer = setInterval(tick, 400);
    ready = true; return true;
  }

  var api = {
    start:function(){
      if (ready) return api;
      var tries = 0, t = setInterval(function(){ if (boot() || ++tries > 600) clearInterval(t); }, 250);
      if (boot()) clearInterval(t);
      return api;
    },
    steps:function(){ return STEPS.slice(); },
    global:function(){ return fonts.g; },
    setGlobal:function(p){
      p = +p; if (STEPS.indexOf(p) < 0) return false;
      fonts.g = p; saveFonts();
      keys().forEach(function(k){ var e = elOf(k); if (e) delete e._q386k; });
      applyAll(); placeOverlays(); return true;
    },
    box:function(k){ return pctOf(k); },
    setBox:function(k, p){
      if (p == null){ delete fonts.b[k]; }
      else { p = +p; if (STEPS.indexOf(p) < 0) return false; fonts.b[k] = p; }
      saveFonts();
      var e = elOf(k); if (e) delete e._q386k;
      applyBox(k); placeOverlays(); return true;
    },
    factor:function(k){ var e = elOf(k); return e ? factorOf(k, e) : 1; },
    own:function(k){ return fonts.b[k] != null; },
    size:function(k){ return sizes[k] ? {w:sizes[k].w, h:sizes[k].h} : null; },
    sizedKeys:function(){ return Object.keys(sizes); },
    boxes:function(){
      return keys().map(function(k){ var e = elOf(k); return {key:k, label:labelOf(k), present:shown(e), pct:pctOf(k), own:fonts.b[k] != null, sized:!!sizes[k]}; });
    },
    resetSizes:function(){
      sizes = {}; saveSizes();
      keys().forEach(function(k){ var e = elOf(k); if (e) delete e._q386k; });
      applyAll(); placeOverlays(); return true;
    },
    /* Reset layout: sizes and the per-box text sizes (the all-boxes text size is a setting of its own and stays) */
    reset:function(){
      var any = Object.keys(sizes).length || Object.keys(fonts.b).length;
      sizes = {}; fonts.b = {}; saveSizes(); saveFonts();
      keys().forEach(function(k){ var e = elOf(k); if (e) delete e._q386k; });
      applyAll(); placeOverlays(); return !!any;
    },
    tick:tick,
    ready:function(){ return ready; },
    state:function(){ return {ready:ready, phone:phone(), global:fonts.g, own:JSON.parse(JSON.stringify(fonts.b)), sizes:JSON.parse(JSON.stringify(sizes)), resizing:!!drag}; }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function(){ api.start(); }); else api.start();
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKResize;
