/* Q303: a custom orientation -- "facing me" -- and camera views the user can name, save and come back to in one tap.
   Owner (translated): "instead of setting a particular orientation repeatedly, allow a 4-up 3-D view, or alternatively a
   custom orientation ('facing me')." The standard views (front / side / back / superior, and each engine's reset) are
   untouched; this is added beside them.
   "FACING ME" -- THE RULE, AND WHY IT IS THIS ONE. The precedent is Blender's View > Align View to Active, which "orients
   the viewport along a local axis of the active object or bone" and, in Edit Mode, "uses the normal of the active face
   instead" -- i.e. an axis for a solid, a normal for a face. Our structures are neither uniformly rods nor uniformly
   sheets, so instead of two rules there is ONE, chosen because it degenerates into each of them:
       look along the structure's axis of LEAST spread (the minor principal axis of its own vertices).
   For a sheet (two large eigenvalues and one small) the minor axis IS the surface normal, so the broad face turns toward
   the camera. For a rod (one large eigenvalue) the minor axis is across the shaft, so the long axis lies across the
   screen at full length instead of pointing at the viewer. It is also the direction that maximises the structure's drawn
   silhouette: projected on the plane normal to axis k the silhouette's area goes as sqrt of the product of the other two
   eigenvalues, so looking along the smallest one is the largest picture, by sqrt(lambda1/lambda3). The per-structure
   numbers are measured on the real meshes and reported, not asserted.
   The camera is parameterised identically in both engines -- eye = target + dist * (cos(el) sin(az), sin(el), cos(el) cos(az))
   -- so az = atan2(u.x, u.z) and el = asin(u.y) for u = -(view direction) is the same arithmetic on both.
     NMSKViews.start(E, {history, target, anchor})
   E = {cam:{get, set, fit, redraw}, axesOf(ids), modelId()}
     .facing()  .save(name)  .apply(name)  .del(name)  .list()  .report(ids)  .state() */
var NMSKViews = (function(){
  "use strict";
  var E = null, hist = null, TG = null, on = false, box = null, chips = null, nameEl = null;
  var saved = [], last = null, MAX = 8;
  function key(){ var m = "page"; try { m = E.modelId() || "page"; } catch (err){} return "nmsk.q303.views." + m; }
  function num(x){ return Math.round(x * 1e4) / 1e4; }
  function load(){
    try {
      var j = JSON.parse(localStorage.getItem(key()) || "[]");
      saved = Array.isArray(j) ? j.filter(function(v){ return v && v.name && v.cam; }).slice(0, MAX) : [];
    } catch (err){ saved = []; }
  }
  function store(){ try { localStorage.setItem(key(), JSON.stringify(saved)); } catch (err){} }
  function camNow(){ var c = E.cam.get(); return {az:num(c.az), el:num(c.el), dist:num(c.dist), tgt:c.tgt.map(num)}; }

  /* ONE undo step, through NMSKStep: the history watches a counter, the cameras live in its side table. Registering the
     camera as an ordinary provider would make every unrelated Undo move it, and committing a "before" value of its own
     produced two entries -- both found by this round's harness. */
  var STEP = null;
  function step(apply){ return STEP ? STEP.step(apply) : apply(); }

  /* ---- the orientation itself ---- */
  function dirToAzEl(u){
    var l = Math.hypot(u[0], u[1], u[2]) || 1, x = u[0] / l, y = u[1] / l, z = u[2] / l;
    y = Math.max(-0.9994, Math.min(0.9994, y));                 /* el = +-90 deg is the degenerate pole of this parameterisation */
    return {az:Math.atan2(x, z), el:Math.asin(y)};
  }
  function eyeDir(c){                                            /* the unit vector from the target to the eye */
    var ce = Math.cos(c.el);
    return [ce * Math.sin(c.az), Math.sin(c.el), ce * Math.cos(c.az)];
  }
  function dot(a, b){ return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function shapeOf(lam){
    var l1 = lam[0], l2 = lam[1], l3 = lam[2];
    if (l1 <= 0) return "point";
    if (l3 / Math.max(1e-12, l2) < 0.25) return "sheet";          /* one small axis: a flat structure, the minor axis is its normal */
    if (l2 / Math.max(1e-12, l1) < 0.25) return "rod";            /* one big axis: a tube, the minor axis is across it */
    return "blob";
  }
  function report(ids){
    var A = null;
    try { A = E.axesOf(ids); } catch (err){ A = null; }
    if (!A || !A.lam) return null;
    var lam = A.lam, sh = shapeOf(lam);
    var aMinor = Math.sqrt(Math.max(0, lam[0] * lam[1])), aMajor = Math.sqrt(Math.max(0, lam[1] * lam[2]));
    return {n:A.n, c:A.c.map(num), lam:lam.map(function(x){ return Math.round(x * 1e3) / 1e3; }),
            e1:A.e[0].map(num), e2:A.e[1].map(num), e3:A.e[2].map(num), shape:sh,
            silhouetteAlongMinor:Math.round(aMinor * 1e3) / 1e3, silhouetteAlongMajor:Math.round(aMajor * 1e3) / 1e3,
            gain:aMajor > 0 ? Math.round(aMinor / aMajor * 1e3) / 1e3 : null,
            extent:A.ext ? A.ext.map(num) : null};
  }
  function facing(){
    if (!on) return null;
    var t = TG ? TG.get() : null, ids = t ? t.ids : null;
    if (!ids || !ids.length){ last = {ok:false, why:"nothing is selected or marked, so there is nothing to face"}; return last; }
    var R = report(ids);
    if (!R){ last = {ok:false, why:"this structure's vertices are not readable on this page"}; return last; }
    var u = R.e3.slice(), c0 = E.cam.get(), e0 = eyeDir(c0);
    if (dot(u, e0) < 0){ u = [-u[0], -u[1], -u[2]]; }             /* keep the camera on the side it is already on: never swing round the body */
    var ae = dirToAzEl(u);
    /* how far the structure reaches ACROSS the new view, so the framing matches the picture we just chose */
    var across = Math.max(R.extent ? R.extent[0] : t.r, R.extent ? R.extent[1] : t.r) / 2 || t.r;
    var d = E.cam.fit(Math.max(across, t.r * 0.35));
    step(function(){ E.cam.set({az:ae.az, el:ae.el, dist:d, tgt:R.c.slice()}); if (E.cam.redraw) E.cam.redraw(); });
    var c1 = E.cam.get(), e1 = eyeDir(c1), cosang = Math.max(-1, Math.min(1, dot(e1, u)));
    last = {ok:true, label:t.label, ids:ids.slice(), shape:R.shape, axis:u.map(num),
            angle_deg:Math.round(Math.acos(cosang) * 180 / Math.PI * 1000) / 1000,
            rule:"look along the minor principal axis (= the surface normal of a sheet, across the shaft of a rod)",
            report:R, cam:camNow()};
    ui();
    return last;
  }

  /* ---- named views ---- */
  function autoName(){
    for (var i = 1; i <= MAX; i++){
      var n = "View " + i, used = false;
      saved.forEach(function(v){ if (v.name === n) used = true; });
      if (!used) return n;
    }
    return "View " + Date.now();
  }
  function save(name){
    if (!on) return null;
    name = String(name == null ? "" : name).trim().slice(0, 24) || autoName();
    var cam = camNow(), lay = window.NMSKFourUp ? NMSKFourUp.layout() : "one", sh = window.NMSKFourUp ? NMSKFourUp.shown() : "free";
    var i = -1;
    saved.forEach(function(v, k){ if (v.name === name) i = k; });
    var rec = {name:name, cam:cam, lay:lay, shown:sh, at:Date.now()};
    if (i >= 0) saved[i] = rec; else { saved.push(rec); if (saved.length > MAX) saved.shift(); }
    store(); ui();
    return rec;
  }
  function apply(name){
    if (!on) return null;
    var rec = null;
    saved.forEach(function(v){ if (v.name === name) rec = v; });
    if (!rec) return null;
    /* the camera FIRST, then the layout: entering four-up frames every pane on whatever the single view was framing,
       so the restored camera is what the four panes take. Both moves are held into ONE history entry -- two nested
       steps would commit twice, which is exactly the defect NMSKStep exists to prevent. */
    function run(){
      step(function(){
        E.cam.set({az:rec.cam.az, el:rec.cam.el, dist:rec.cam.dist, tgt:rec.cam.tgt.slice()});
        if (E.cam.redraw) E.cam.redraw();
      });
      if (window.NMSKFourUp && rec.lay && NMSKFourUp.layout() !== rec.lay){
        if (rec.lay === "four") NMSKFourUp.enter(); else NMSKFourUp.leave();
      }
    }
    if (window.NMSKStep && NMSKStep.hold) NMSKStep.hold(run); else run();
    last = {ok:true, applied:rec.name, cam:camNow()};
    return last;
  }
  function del(name){
    var before = saved.length;
    saved = saved.filter(function(v){ return v.name !== name; });
    if (saved.length === before) return false;
    store(); ui();
    return true;
  }

  /* ---- the control: one row, taps only; the name is optional and one tap saves without it ---- */
  function ui(){
    if (!chips) return;
    chips.innerHTML = "";
    if (!saved.length){
      var p = document.createElement("span");
      p.className = "q3-none"; p.textContent = "no saved views yet";
      chips.appendChild(p);
      return;
    }
    saved.forEach(function(v){
      var c = document.createElement("span");
      c.className = "q3-vchip";
      var b = document.createElement("button");
      b.type = "button"; b.className = "q3-vb"; b.textContent = v.name;
      b.setAttribute("data-view", "q303:" + v.name);
      b.title = "Go back to “" + v.name + "” (one tap, one Undo step)";
      b.addEventListener("click", function(ev){ ev.stopPropagation(); apply(v.name); });
      var x = document.createElement("button");
      x.type = "button"; x.className = "q3-vx"; x.textContent = "×";
      x.title = "Forget “" + v.name + "”"; x.setAttribute("aria-label", "Forget the view " + v.name);
      x.addEventListener("click", function(ev){ ev.stopPropagation(); del(v.name); });
      c.appendChild(b); c.appendChild(x);
      chips.appendChild(c);
    });
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null;
      if (!E || !E.cam || typeof E.cam.get !== "function" || typeof E.axesOf !== "function") return api;
      hist = opt.history || window.NMSKHistory || null;
      TG = opt.target || window.NMSKTarget || null;
      load();
      STEP = window.NMSKStep ? NMSKStep.make(hist, "q303cam", camNow, function(c){
        try { E.cam.set({az:c.az, el:c.el, dist:c.dist, tgt:c.tgt.slice()}); if (E.cam.redraw) E.cam.redraw(); } catch (err){}
      }) : null;
      on = true;
      return api;
    },
    /* the box the View group adopts: Facing me + Save this view + the saved chips */
    element:function(){
      if (box) return box;
      box = document.createElement("div");
      box.id = "q303-views"; box.className = "q3-views";
      box.setAttribute("role", "group"); box.setAttribute("aria-label", "Custom orientation and saved views");
      var f = document.createElement("button");
      f.type = "button"; f.id = "q303-facing"; f.className = "q3-b"; f.textContent = "Facing me";
      f.title = "Turn the selected structure to face you: the camera looks along the structure's own axis of least spread, which is the surface normal of a flat structure and across the shaft of a tube -- the largest view of it there is. Mark or select something first.";
      f.addEventListener("click", function(ev){ ev.stopPropagation(); facing(); });
      box.appendChild(f);
      var row = document.createElement("span"); row.className = "q3-vsave";
      nameEl = document.createElement("input");
      nameEl.type = "text"; nameEl.id = "q303-vname"; nameEl.className = "q3-vname";
      nameEl.placeholder = "name (optional)"; nameEl.maxLength = 24;
      nameEl.setAttribute("aria-label", "A name for this view");
      row.appendChild(nameEl);
      var s = document.createElement("button");
      s.type = "button"; s.id = "q303-vsave"; s.className = "q3-b"; s.textContent = "Save this view";
      s.title = "Remember where the camera is now, under a name, and come back to it in one tap. Kept in this browser only.";
      s.addEventListener("click", function(ev){ ev.stopPropagation(); save(nameEl ? nameEl.value : ""); if (nameEl) nameEl.value = ""; });
      row.appendChild(s);
      box.appendChild(row);
      chips = document.createElement("div"); chips.className = "q3-vchips"; chips.id = "q303-vchips";
      box.appendChild(chips);
      var tip = document.createElement("p");
      tip.className = "nmsk-tip";
      tip.textContent = "The standard views (front / side / back, and the reset) are unchanged. “Facing me” uses the structure's own minor principal axis -- the rule is in the circled i, with the measured numbers. Saved views live in this browser, up to " + MAX + "; the two resets do not touch them.";
      box.appendChild(tip);
      ui();
      return box;
    },
    facing:facing, save:save, apply:apply, del:del, report:report,
    list:function(){ return saved.map(function(v){ return {name:v.name, cam:v.cam, lay:v.lay, shown:v.shown}; }); },
    last:function(){ return last; },
    state:function(){ return {on:on, saved:api.list(), last:last, max:MAX, step:STEP ? STEP.state() : null}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKViews;
