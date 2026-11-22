/* Q303: four panes of the SAME model at once, each with its own camera.
   Owner (translated): "instead of setting a particular orientation repeatedly, allow a 4-up 3-D view, or alternatively a
   custom orientation ('facing me')." Both were built; this is the first.
   THE CONVENTIONAL SET. 3D Slicer's Four-Up is three orthogonal slice views (Red axial, Yellow sagittal, Green coronal)
   plus the 3-D view, and that is the reference the owner named. The surface-model equivalent of those three slice normals
   is looking ALONG each anatomical axis: anterior (the coronal normal), lateral (the sagittal normal) and superior (the
   axial normal), with the free 3-D view in the fourth quadrant. Visible Body's own preset list is the same set of
   directions as single views -- "1: Anterior, 2: Posterior, 3: Right, 4: Left, 5: Superior, 6: Inferior" -- but we found
   no documentation for a four-pane layout in any commercial anatomy atlas, so the GRID is Slicer's convention and is
   labelled as such; which quadrant holds which pane is ours, chosen to put the free view where Slicer puts the 3-D one.
   ONE MODEL, FOUR CAMERAS, AND THAT IS ALL. Selection, marking, hiding, the render style, the layers, the peel and the
   cut are the engine's own single state: the panes are four viewports over one scene, so they cannot disagree. Only the
   camera is per pane. Each pane is exactly half the canvas in each direction, so a pane is a scaled copy of the full
   canvas with the same projection -- which is why a pointer inside a pane can be mapped to the full-canvas pixel it
   corresponds to with one linear scale, and the engines' own picking, ray casting and dragging then work untouched.
     NMSKFourUp.start(E, {history, anchor})
   E = {camGet(), camSet(c), setPanes(list|null), redraw(), canvas}
     .enter()  .leave()  .expand(key)  .restore()  .layout()  .panes()  .state() */
var NMSKFourUp = (function(){
  "use strict";
  var E = null, hist = null, anchor = null, on = false, grid = null, cells = {}, btn = null;
  var lay = "one", shown = "free", active = "free", dragging = false, syncT = 0;
  var SPEC = [
    {key:"ant", label:"Anterior", az:0, el:0, cell:[0, 0]},
    {key:"lat", label:"Lateral", az:Math.PI / 2, el:0, cell:[1, 0]},
    {key:"sup", label:"Superior", az:0, el:Math.PI / 2 - 0.035, cell:[0, 1]},
    {key:"free", label:"3-D", az:null, el:null, cell:[1, 1]}
  ];
  var CAM = {};
  function spec(k){ var r = null; SPEC.forEach(function(s){ if (s.key === k) r = s; }); return r; }
  function num(x){ return Math.round(x * 1000) / 1000; }
  function cloneCam(c){ return {az:c.az, el:c.el, dist:c.dist, tgt:c.tgt.slice()}; }

  /* the fractional rect of a pane inside the canvas, y measured from the TOP */
  function rectOf(k){
    if (lay !== "four") return {x:0, y:0, w:1, h:1};
    var s = spec(k); if (!s) return {x:0, y:0, w:1, h:1};
    return {x:s.cell[0] * 0.5, y:s.cell[1] * 0.5, w:0.5, h:0.5};
  }
  /* Entering four-up: every pane frames whatever the single view was framing (the same target and the same distance, so
     the four pictures are one model at one scale), the three fixed panes take their canonical direction and the free
     pane keeps the camera the user had. Expanding and restoring do NOT come through here, so a pane the user has
     rotated keeps its rotation across an expand. */
  function initCams(){
    var c = E.camGet();
    SPEC.forEach(function(s){
      CAM[s.key] = {az:s.az == null ? c.az : s.az, el:s.el == null ? c.el : s.el, dist:c.dist, tgt:c.tgt.slice()};
    });
  }
  function paneList(){
    if (lay !== "four") return null;
    return SPEC.map(function(s){
      var r = rectOf(s.key), c = CAM[s.key];
      return {key:s.key, label:s.label, x:r.x, y:r.y, w:r.w, h:r.h,
              az:c.az, el:c.el, dist:c.dist, tgt:c.tgt.slice(), active:s.key === active};
    });
  }
  function push(){
    var L = paneList();
    lastSig = sig(L);
    try { E.setPanes(L); } catch (err){ if (window.console) console.error("q303 panes", err); }
    if (lay !== "four") { try { E.camSet(CAM[shown] || E.camGet()); } catch (e2){} }
    if (E.redraw) E.redraw();
    paint();
  }
  /* the pane the user is working in owns the engine's camera, so every drag, wheel and pinch the engines already
     implement acts on that pane and nothing else */
  function makeActive(k){
    if (!CAM[k]) return;
    if (active === k) return;
    CAM[active] = cloneCam(E.camGet());
    active = k;
    try { E.camSet(CAM[k]); } catch (err){}
    push();
  }
  /* The engine is told about the panes only when they have ACTUALLY changed. The first draft pushed the list every
     400 ms, and on the own engine setPanes() forces a draw -- so the page redrew the whole model four times a second
     for ever, never went idle, and the browser check sat at 350 % CPU waiting for a render-style change that could
     not finish. Measured, not guessed: the signature below is what stops it. */
  var lastSig = "";
  function sig(L){
    if (!L) return "one:" + lay + ":" + shown;
    return L.map(function(p){ return p.key + "," + num(p.az) + "," + num(p.el) + "," + num(p.dist) + "," +
      p.tgt.map(num).join(",") + "," + (p.active ? 1 : 0); }).join("|");
  }
  function syncActive(){
    if (!on || lay !== "four") return;
    try { CAM[active] = cloneCam(E.camGet()); } catch (err){ return; }
    var L = paneList(), q = sig(L);
    if (q === lastSig) return;
    lastSig = q;
    try { E.setPanes(L); } catch (e2){}
  }

  /* ---- the frame on the screen: a label and an expand button per pane, nothing else over the picture ---- */
  function ensureGrid(){
    if (grid) return grid;
    grid = document.createElement("div");
    grid.id = "q303-grid"; grid.className = "q3-grid"; grid.hidden = true;
    SPEC.forEach(function(s){
      var c = document.createElement("div");
      c.className = "q3-cell"; c.id = "q303-cell-" + s.key;
      var h = document.createElement("div"); h.className = "q3-ch";
      var t = document.createElement("span"); t.className = "q3-cl"; t.textContent = s.label; h.appendChild(t);
      var x = document.createElement("button");
      x.type = "button"; x.className = "q3-cx"; x.id = "q303-exp-" + s.key; x.textContent = "⬜";
      x.title = "Show only the " + s.label + " view"; x.setAttribute("aria-label", "Expand the " + s.label + " view");
      x.addEventListener("click", function(ev){ ev.stopPropagation(); ev.preventDefault(); api.expand(s.key); });
      x.addEventListener("pointerdown", function(ev){ ev.stopPropagation(); });
      h.appendChild(x);
      c.appendChild(h);
      grid.appendChild(c); cells[s.key] = {el:c, head:h, btn:x};
    });
    document.body.appendChild(grid);
    return grid;
  }
  function paint(){
    if (!grid) return;
    /* the projection overlays (labels, the axis gnomon, the scale bar, the cut outline, the part dots and the measure
       chips) are all drawn for ONE camera over the whole canvas, so they are stood down while four are on; the
       stylesheet hides what is DOM and the engines' draw skips what is canvas. Said on the screen and in the i. */
    document.body.classList.toggle("q303-four", lay === "four");
    grid.hidden = lay !== "four";
    /* Q301's group sheet unfolds over the LOWER part of the 3-D view -- exactly where the bottom row's two labels and
       their squares sit, and it is far above them in the stack. Rather than let it swallow them (measured with
       document.elementFromPoint, as Q301 learnt to), the labels step aside while a group is open: the sheet is the
       surface the user is working on at that moment, and closing it brings them straight back. */
    var sheetOpen = false;
    try { sheetOpen = !!(window.NMSKGroups && NMSKGroups.isOpen()); } catch (err){ sheetOpen = false; }
    grid.classList.toggle("q3-quiet", sheetOpen);
    if (grid.hidden) return;
    var r = anchor && anchor.getBoundingClientRect ? anchor.getBoundingClientRect() : null;
    if (!r || !(r.width > 40 && r.height > 40)) return;
    grid.style.left = Math.round(r.left) + "px"; grid.style.top = Math.round(r.top) + "px";
    grid.style.width = Math.round(r.width) + "px"; grid.style.height = Math.round(r.height) + "px";
    SPEC.forEach(function(s){
      var q = rectOf(s.key), c = cells[s.key];
      if (!c) return;
      c.el.style.left = (q.x * 100) + "%"; c.el.style.top = (q.y * 100) + "%";
      c.el.style.width = (q.w * 100) + "%"; c.el.style.height = (q.h * 100) + "%";
      c.el.classList.toggle("act", s.key === active);
    });
    if (btn){ btn.setAttribute("aria-pressed", String(lay === "four")); btn.textContent = lay === "four" ? "One view" : "Four views"; }
  }

  /* ---- input: one capture listener per kind on the window, so it runs BEFORE either engine's own canvas handlers and
     neither engine needs an edit. The pointer's pane is resolved, that pane is made active, and the coordinates are
     rewritten to the full-canvas pixel they correspond to -- exact, because a pane is the full canvas at half scale in
     both directions, with the same projection. ---- */
  function cvRect(){ var c = E.canvas; return c && c.getBoundingClientRect ? c.getBoundingClientRect() : null; }
  function paneAt(x, y){
    var r = cvRect(); if (!r) return null;
    var fx = (x - r.left) / Math.max(1, r.width), fy = (y - r.top) / Math.max(1, r.height);
    if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return null;
    var hit = null;
    SPEC.forEach(function(s){
      var q = rectOf(s.key);
      if (fx >= q.x && fx <= q.x + q.w && fy >= q.y && fy <= q.y + q.h) hit = s.key;
    });
    return hit;
  }
  function mapXY(x, y, k){
    var r = cvRect(), q = rectOf(k);
    if (!r) return [x, y];
    var px = r.left + q.x * r.width, py = r.top + q.y * r.height, pw = q.w * r.width, ph = q.h * r.height;
    var X = r.left + (x - px) / Math.max(1, pw) * r.width, Y = r.top + (y - py) / Math.max(1, ph) * r.height;
    return [Math.max(r.left, Math.min(r.left + r.width - 1, X)), Math.max(r.top, Math.min(r.top + r.height - 1, Y))];
  }
  function force(ev, x, y){
    try {
      Object.defineProperty(ev, "clientX", {value:x, configurable:true});
      Object.defineProperty(ev, "clientY", {value:y, configurable:true});
      Object.defineProperty(ev, "pageX", {value:x + (window.scrollX || 0), configurable:true});
      Object.defineProperty(ev, "pageY", {value:y + (window.scrollY || 0), configurable:true});
      return true;
    } catch (err){ return false; }
  }
  var remapped = 0, refused = 0;
  function remap(ev){
    if (!on || lay !== "four") return;
    var c = E.canvas;
    if (!c || !ev.target || !(ev.target === c || (c.contains && c.contains(ev.target)))) return;
    var k = dragging ? active : paneAt(ev.clientX, ev.clientY);
    if (!k) return;
    if (!dragging && k !== active) makeActive(k);
    var p = mapXY(ev.clientX, ev.clientY, k);
    if (force(ev, p[0], p[1])) remapped++; else refused++;
  }
  function wire(){
    ["pointerdown", "pointermove", "pointerup", "pointercancel", "click", "wheel", "contextmenu", "pointerover", "pointerout"]
      .forEach(function(t){ window.addEventListener(t, remap, true); });
    window.addEventListener("pointerdown", function(ev){ if (on && lay === "four" && E.canvas && E.canvas.contains && E.canvas.contains(ev.target)) dragging = true; }, true);
    window.addEventListener("pointerup", function(){ dragging = false; syncActive(); }, true);
    window.addEventListener("pointercancel", function(){ dragging = false; }, true);
  }

  /* ---- ONE undo step, through NMSKStep. The pane cameras must NOT be an ordinary provider: syncActive() writes the camera
     the user is dragging into CAM every 400 ms, so an ordinary provider would make an unrelated Undo jerk the panes
     back. The history watches a counter; the layout and the four cameras live in NMSKStep's side table. */
  var STEP = null;
  function readState(){
    var o = {lay:lay, shown:shown, active:active, cams:{}};
    SPEC.forEach(function(s){ var c = CAM[s.key]; if (c) o.cams[s.key] = [num(c.az), num(c.el), num(c.dist), num(c.tgt[0]), num(c.tgt[1]), num(c.tgt[2])]; });
    return o;
  }
  function writeState(v){
    if (!v) return;
    Object.keys(v.cams || {}).forEach(function(k){
      var a = v.cams[k]; if (!a || !CAM[k]) return;
      CAM[k] = {az:a[0], el:a[1], dist:a[2], tgt:[a[3], a[4], a[5]]};
    });
    lay = v.lay === "four" ? "four" : "one"; shown = v.shown || "free"; active = v.active || "free";
    push();
  }
  function step(fn){
    if (!STEP){ fn(); push(); return; }
    STEP.step(function(){ fn(); push(); });   /* the engine has to be told, not only the history */
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null;
      if (!E || typeof E.camGet !== "function" || typeof E.setPanes !== "function") return api;
      hist = opt.history || window.NMSKHistory || null;
      anchor = opt.anchor || E.canvas || null;
      initCams();
      ensureGrid(); wire();
      STEP = window.NMSKStep ? NMSKStep.make(hist, "q303fourup", readState, writeState) : null;
      on = true;
      syncT = setInterval(function(){ paint(); if (!dragging) syncActive(); }, 400);
      window.addEventListener("resize", paint);
      paint();
      return api;
    },
    button:function(cls){
      if (btn) return btn;
      btn = document.createElement("button");
      btn.type = "button"; btn.id = "q303-four"; btn.className = (cls || "") + " q3-b";
      btn.textContent = "Four views";
      btn.title = "Show the same model in four panes at once -- Anterior, Lateral, Superior and a free 3-D view -- each with its own camera. Selection, marking, hiding, the render style and the cut are shared: it is one model seen four ways. Tap a pane's square to show only that pane.";
      btn.setAttribute("aria-pressed", "false");
      btn.addEventListener("click", function(ev){ ev.stopPropagation(); if (lay === "four") api.leave(); else api.enter(); });
      return btn;
    },
    enter:function(){
      if (!on || lay === "four") return false;
      step(function(){ initCams(); lay = "four"; active = "free"; });
      return true;
    },
    leave:function(){
      if (!on || lay !== "four") return false;
      step(function(){ CAM[active] = cloneCam(E.camGet()); lay = "one"; shown = active; });
      return true;
    },
    expand:function(k){
      if (!on || !CAM[k]) return false;
      step(function(){ if (lay === "four") CAM[active] = cloneCam(E.camGet()); lay = "one"; shown = k; active = k; });
      return true;
    },
    restore:function(){
      if (!on || lay === "four") return false;
      step(function(){ CAM[shown] = cloneCam(E.camGet()); lay = "four"; active = shown; });
      return true;
    },
    layout:function(){ return lay; },
    shown:function(){ return shown; },
    panes:function(){ return paneList() || [{key:shown, label:(spec(shown) || {}).label, x:0, y:0, w:1, h:1}]; },
    cams:function(){ var o = {}; Object.keys(CAM).forEach(function(k){ o[k] = cloneCam(CAM[k]); }); return o; },
    makeActive:makeActive,
    /* verification: the rect of a pane in CSS pixels, and the pointer map, read from the module itself */
    paneRect:function(k){
      var r = cvRect(), q = rectOf(k);
      if (!r) return null;
      return {left:r.left + q.x * r.width, top:r.top + q.y * r.height, width:q.w * r.width, height:q.h * r.height};
    },
    mapXY:mapXY, paneAt:paneAt,
    state:function(){ return {on:on, layout:lay, shown:shown, active:active, panes:api.panes(), cams:api.cams(),
                              remapped:remapped, refused:refused, grid:!!(grid && !grid.hidden), step:STEP ? STEP.state() : null}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKFourUp;
