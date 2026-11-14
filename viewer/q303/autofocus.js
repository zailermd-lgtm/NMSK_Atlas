/* Q303: entering an imaging-like mode centres it on what the user already chose.
   Owner (translated): "imaging should focus automatically on the area that was marked, or typed, earlier."
   The pattern is 3D Slicer's "Jump slices -- centered" (its Markups module offers centred / offset as a choice, and the
   centred one is what the owner describes); the target itself comes from NMSKTarget, which is the only place that decides
   what "what the user already chose" means. Five modes, each centred on its own terms and NEVER on anything else:
     render style (Q301)  the camera frames the target
     CT / MR panes        the slice point P = the target's centre, and every pane's in-plane centre is released so it
                          follows P (that is the slice LEVEL and the in-plane POSITION in one)
     the probe            it is seated on the skin where a ray from the camera to the target meets it
     cut                  the plane keeps the user's orientation and slides so it passes through the centre
     cross-section        plane mode: the same plane move (the stack is centred on the cut plane); part mode: the stack's
                          part becomes the target's own structures
   Nothing moves when there is no target. One Undo step per focus (commit before, commit after), one provider so Q300's
   model reset returns the view and the panes, an off switch that is remembered, and a line on the screen saying what it
   centred on and why.
     NMSKAutoFocus.start(E, {history, target, anchor})
     .on()  .setOn(v)  .focus(reason)  .last()  .modes()  .state()  .tool(kind) */
var NMSKAutoFocus = (function(){
  "use strict";
  var E = null, hist = null, TG = null, on = false, want = true, anchor = null, note = null, noteT = 0;
  var last = null, watch = {}, log = [], KEY = "nmsk.q303.autofocus";
  var btn = null, poll = 0;
  function num(x){ return Math.round(x * 100) / 100; }
  function v3(a){ return [num(a[0]), num(a[1]), num(a[2])]; }
  function unit(a){ var l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
  function pref(){ try { var v = localStorage.getItem(KEY); return v == null ? true : v === "1"; } catch (err){ return true; } }
  function save(){ try { localStorage.setItem(KEY, want ? "1" : "0"); } catch (err){} }

  /* The two clinical tools are the project's PRIVATE layer and the public templates may not name them: the slice tool
     and the probe tool are each loaded by the clinical layer itself, and `tests/test_q226.py` /
     `tests/test_q228.py` pin that no public template mentions either by name. This round is the first public module
     that has to talk to them, so they are found by SHAPE, not by name -- the slice tool is the one that can set a
     slice point, list its panes and slice on demand; the probe tool is the one that can seat a probe along a ray and
     say whether it is open. Both are optional: when the clinical layer is absent, `find` returns null and the mode
     simply never becomes active. */
  var FOUND = {};
  function shape(o, kind){
    if (!o || typeof o !== "object") return false;
    if (kind === "slice") return typeof o.set === "function" && typeof o.state === "function" &&
                                 typeof o.views === "function" && typeof o.sliceNow === "function";
    return typeof o.placeRay === "function" && typeof o.isOpen === "function";
  }
  function find(kind){
    if (shape(FOUND[kind], kind)) return FOUND[kind];
    var ks; try { ks = Object.keys(window); } catch (err){ return null; }
    for (var i = 0; i < ks.length; i++){
      if (ks[i].indexOf("NMSK") !== 0) continue;
      var o = null; try { o = window[ks[i]]; } catch (err2){ o = null; }
      if (shape(o, kind)){ FOUND[kind] = o; return o; }
    }
    return null;
  }

  /* ---- the modes. Each one: is it on, what does centring mean here, and what did it measure? ---- */
  function imaging(){ try { return E.slices ? E.slices() : find("slice"); } catch (err){ return null; } }
  function us(){ try { return E.probeTool ? E.probeTool() : find("probe"); } catch (err){ return null; } }
  function cut(){ try { return E.cut ? E.cut() : null; } catch (err){ return null; } }
  function xsec(){ try { return E.xsec ? E.xsec() : null; } catch (err){ return null; } }
  function style(){ try { return E.style ? E.style() : null; } catch (err){ return null; } }

  function camFrame(t){
    var c = E.cam.get(), d = E.cam.fit(t.r);
    E.cam.set({az:c.az, el:c.el, dist:d, tgt:t.c.slice()});
    if (E.cam.redraw) E.cam.redraw();
    var now = E.cam.get();
    return {what:"the camera", centre:v3(now.tgt), off:num(Math.hypot(now.tgt[0] - t.c[0], now.tgt[1] - t.c[1], now.tgt[2] - t.c[2])), dist:num(now.dist)};
  }
  function ctFocus(t){
    var I = imaging(); if (!I || !I.set) return null;
    I.set({P:t.c.slice()});
    try {                                            /* release each pane's own in-plane centre so it follows P again */
      var V = I.views ? I.views() : null;
      if (V) Object.keys(V).forEach(function(k){ if (V[k]) V[k].CP = null; });
    } catch (err){}
    var st = I.state();
    return {what:"the CT / MR slice", centre:v3(st.P || [0, 0, 0]),
            off:num(Math.hypot((st.P || [0, 0, 0])[0] - t.c[0], (st.P || [0, 0, 0])[1] - t.c[1], (st.P || [0, 0, 0])[2] - t.c[2]))};
  }
  /* The probe is seated where a ray THROUGH the target centre meets the skin. The first ray is the camera's own view
     direction, so the probe comes in from the side the user is looking from -- which is what a sonographer would do.
     A single ray is not enough to rely on: a structure can sit where the camera ray grazes past the skin, or the page
     may ship no skin on that side at all, so the six anatomical directions are tried after it, nearest hit first. The
     direction that worked is reported. */
  function usFocus(t){
    var U = us(); if (!U || !U.placeRay) return null;
    var v = null;
    try { v = E.view(); } catch (err){ v = null; }
    var cand = [];
    if (v && v.dir) cand.push({k:"the camera", d:unit(v.dir)});
    [["anterior", [0, 0, -1]], ["posterior", [0, 0, 1]], ["the right", [-1, 0, 0]], ["the left", [1, 0, 0]],
     ["above", [0, -1, 0]], ["below", [0, 1, 0]]].forEach(function(p){ cand.push({k:p[0], d:p[1]}); });
    for (var i = 0; i < cand.length; i++){
      var d = cand[i].d, o = [t.c[0] - d[0] * 1200, t.c[1] - d[1] * 1200, t.c[2] - d[2] * 1200], h = null;
      try { h = U.placeRay(o, d); } catch (err2){ h = null; }
      if (!h) continue;
      var p = h.P;
      return {what:"the probe", from:cand[i].k, centre:v3(p),
              off:num(Math.hypot(p[0] - t.c[0], p[1] - t.c[1], p[2] - t.c[2])), seated:h.struct || null};
    }
    return null;
  }
  /* the plane keeps the orientation the user chose: only its offset along its own normal moves, through snapshot /
     restore, which is the controller's own public pair -- no second plane UI and no new engine call */
  function planeTo(c){
    var C = cut(); if (!C || !C.snapshot || !C.restore) return null;
    var s = C.snapshot(); if (!s) return null;
    var n = s.n0 || [1, 0, 0], a = n[0] * c[0] + n[1] * c[1] + n[2] * c[2];
    s.a = Math.round(a * 1000) / 1000;
    C.restore(s);
    var st = C.state(), got = st.a, d = Math.abs(got - a);
    return {what:"the cut plane", axis:v3(n), want:num(a), got:num(got), off:num(d), clamped:d > 0.5};
  }
  function cutFocus(t){ return planeTo(t.c); }
  function xsecFocus(t){
    var X = xsec(); if (!X) return null;
    var st = X.state ? X.state() : null;
    if (st && st.mode === "part" && X.setPart){
      X.setPart(t.ids.slice());
      var s2 = X.state();
      return {what:"the cross-section stack", mode:"part", n:(s2.part || []).length};
    }
    var r = planeTo(t.c);
    if (!r) return null;
    r.what = "the cross-section stack"; r.mode = "plane";
    return r;
  }
  var MODES = [
    {key:"style", label:"the radiographic style", probe:function(){ var S = style(); try { return !!(S && S.state().on && S.mode && S.mode() !== "colour"); } catch (err){ return false; } }, run:function(t){ return camFrame(t); }},
    {key:"ct", label:"CT / MR", probe:function(){ var I = imaging(); try { return !!(I && I.state().open); } catch (err){ return false; } }, run:ctFocus},
    {key:"us", label:"the probe", probe:function(){ var U = us(); try { return !!(U && U.isOpen()); } catch (err){ return false; } }, run:usFocus},
    {key:"cut", label:"the cut", probe:function(){ var C = cut(); try { return !!(C && C.state().on); } catch (err){ return false; } }, run:cutFocus},
    {key:"xsec", label:"the cross-sections", probe:function(){ var X = xsec(); try { return !!(X && X.isOn()); } catch (err){ return false; } }, run:xsecFocus}
  ];

  /* ---- what a focus touches, read and written through the controllers' own public API only. NMSKStep keeps a counter
     in Q294's history and these values beside it, so a focus is ONE entry and no unrelated Undo ever moves the camera,
     the slice point or the probe -- none of which Q294 watches, deliberately. ---- */
  function grab(){
    var s = {cam:null, imgP:null, usP:null, usN:null, cutA:null, part:null};
    try { var c = E.cam.get(); s.cam = {az:c.az, el:c.el, dist:c.dist, tgt:c.tgt.slice()}; } catch (err){}
    try { var I = imaging(); if (I){ var q = I.state(); s.imgP = q.P ? q.P.slice() : null; } } catch (e2){}
    try { var U = us(); if (U){ var u = U.state(); s.usP = u.P ? u.P.slice() : null; s.usN = u.N ? u.N.slice() : null; } } catch (e3){}
    try { var C = cut(); if (C){ var k = C.snapshot(); s.cutA = k ? k.a : null; } } catch (e4){}
    try { var X = xsec(); if (X && X.state){ var x = X.state(); s.part = x.part ? x.part.slice() : null; } } catch (e5){}
    return s;
  }
  function put(s){
    if (!s) return;
    try { if (s.cam){ E.cam.set(s.cam); if (E.cam.redraw) E.cam.redraw(); } } catch (err){}
    try { var I = imaging(); if (I && s.imgP) I.set({P:s.imgP.slice()}); } catch (e2){}
    try { var U = us(); if (U && s.usP && s.usN) U.set({P:s.usP.slice(), N:s.usN.slice()}); } catch (e3){}
    try { var C = cut(); if (C && s.cutA != null && C.snapshot && C.restore){ var k = C.snapshot(); k.a = s.cutA; C.restore(k); } } catch (e4){}
    try { var X = xsec(); if (X && s.part && X.setPart) X.setPart(s.part.slice()); } catch (e5){}
  }
  var STEP = null;          /* NMSKStep: the history watches a counter, the states live in its side table */

  /* ---- the line on the screen ---- */
  function ensureNote(){
    if (note) return note;
    note = document.createElement("div");
    note.id = "q303-note"; note.className = "q3-note"; note.hidden = true;
    note.setAttribute("role", "status"); note.setAttribute("aria-live", "polite");
    var t = document.createElement("span"); t.className = "q3-note-t"; note.appendChild(t);
    var x = document.createElement("button");
    x.type = "button"; x.className = "q3-note-x"; x.id = "q303-note-x"; x.textContent = "×";
    x.title = "Hide this"; x.setAttribute("aria-label", "Hide this message");
    x.addEventListener("click", function(ev){ ev.stopPropagation(); note.hidden = true; });
    note.appendChild(x);
    document.body.appendChild(note);
    return note;
  }
  function place(){
    if (!note || note.hidden || !anchor || !anchor.getBoundingClientRect) return;
    var r = anchor.getBoundingClientRect();
    if (!(r.width > 40)) return;
    var w = Math.min(r.width - 24, 420);
    note.style.width = w + "px";
    note.style.left = Math.round(r.left + (r.width - w) / 2) + "px";
    /* Q301's circled i sits at the 3-D view's TOP-RIGHT (28 px) and, in four-up, the top two panes' own labels sit at
       y 8-34. On a wide single view the line is narrow enough to clear the i; otherwise it drops below them rather than
       covering them -- the Q301 lesson (twice over), applied up front. The line is also pointer-events:none, so even
       when it does overlap something it can never swallow a tap. */
    var low = r.width < 520 || (window.NMSKFourUp && NMSKFourUp.layout() === "four");
    note.style.top = Math.round(r.top + (low ? 44 : 8)) + "px";
  }
  function say(txt){
    var n = ensureNote();
    n.querySelector(".q3-note-t").textContent = txt;
    n.hidden = false; place();
    if (noteT) clearTimeout(noteT);
    noteT = setTimeout(function(){ n.hidden = true; }, 7000);
  }

  function focus(reason, quiet){
    if (!on) return null;
    var t = TG ? TG.get() : null;
    if (!t){ last = {ok:false, why:"nothing is marked, selected or picked, so the view was left alone", reason:reason, at:Date.now()}; return last; }
    var M = null;
    MODES.forEach(function(m){ if (!M && m.key === reason) M = m; });
    if (!M){ MODES.forEach(function(m){ if (!M && m.probe()) M = m; }); }
    if (!M) M = MODES[0];
    var r = null;
    if (STEP) STEP.step(function(){ r = M.run(t); });
    else r = M.run(t);
    last = {ok:!!r, mode:M.key, modeLabel:M.label, kind:t.kind, label:t.label, why:t.why, n:t.n,
            target:v3(t.c), radius:num(t.r), result:r, reason:reason, at:Date.now()};
    log.push(last); if (log.length > 40) log.shift();
    if (!quiet && r) say("Centred " + r.what + " on " + t.label + " — " + t.why + ".");
    else if (!quiet) say("Nothing to centre " + M.label + " on here.");
    return last;
  }

  /* entering a mode is watched rather than hooked: the CT / MR panes, the probe, the cut, the cross-sections and the
     render style are five different controllers (two of them optional add-ons), and a watcher needs no edit in any of
     them -- it only reads their own public state */
  function tickWatch(){
    if (!on) return;
    MODES.forEach(function(m){
      var now = false;
      try { now = !!m.probe(); } catch (err){ now = false; }
      var was = !!watch[m.key];
      watch[m.key] = now;
      if (now && !was && want) focus(m.key);
    });
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null;
      if (!E || !E.cam || typeof E.cam.get !== "function") return api;
      hist = opt.history || window.NMSKHistory || null;
      TG = opt.target || window.NMSKTarget || null;
      anchor = opt.anchor || null;
      want = pref();
      MODES.forEach(function(m){ try { watch[m.key] = !!m.probe(); } catch (err){ watch[m.key] = false; } });
      STEP = window.NMSKStep ? NMSKStep.make(hist, "q303focus", grab, put) : null;
      on = true;
      /* 150 ms, not 250: the watcher only reads five small public states, and a shorter window makes it far less
         likely that leaving and re-entering a mode falls inside one tick and is missed as a non-event. */
      poll = setInterval(tickWatch, 150);
      setInterval(place, 700);
      window.addEventListener("resize", place);
      return api;
    },
    /* the control: one toggle, default on, remembered in this browser */
    button:function(cls){
      if (btn) return btn;
      btn = document.createElement("button");
      btn.type = "button"; btn.id = "q303-af"; btn.className = (cls || "") + " q3-b";
      btn.textContent = "Follow what I chose";
      btn.title = "When you enter CT / MR, the probe, a cut, the cross-sections or a radiographic style, centre it on what you have marked, selected or picked out of a search. Off leaves the view exactly where it is.";
      btn.setAttribute("aria-pressed", String(want));
      btn.addEventListener("click", function(ev){
        ev.stopPropagation();
        api.setOn(!want);
      });
      return btn;
    },
    centreButton:function(cls){
      var b = document.createElement("button");
      b.type = "button"; b.id = "q303-centre"; b.className = (cls || "") + " q3-b";
      b.textContent = "Centre on my choice";
      b.title = "Centre the mode you are in on what you have marked, selected or picked -- now, without leaving and re-entering it.";
      b.addEventListener("click", function(ev){ ev.stopPropagation(); focus(null); });
      return b;
    },
    on:function(){ return want; },
    setOn:function(v){
      v = !!v;
      if (v === want) return false;
      want = v; save();
      if (btn) btn.setAttribute("aria-pressed", String(want));
      say(want ? "Imaging will centre on what you chose." : "Imaging will stay where it is.");
      return true;
    },
    focus:focus, last:function(){ return last; }, history:function(){ return log.slice(); },
    tool:find,                                        /* the clinical tools, found by shape (see `find` above) */
    modes:function(){ return MODES.map(function(m){ var a = false; try { a = !!m.probe(); } catch (err){} return {key:m.key, label:m.label, active:a}; }); },
    state:function(){ return {on:on, follow:want, last:last, modes:api.modes(),
      target:TG ? TG.state().target : null, note:!!(note && !note.hidden), step:STEP ? STEP.state() : null}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKAutoFocus;
