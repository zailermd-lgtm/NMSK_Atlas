/* Q305: move a box where you want it, and find it there again next time.
   Owner (translated from Hebrew): "let the various boxes on the screen be moved around."

   WHY AN OFFSET AND NOT A POSITION. Six rounds already place these boxes, and they keep placing them: Q301's
   `place()` rewrites the control bar's `left` / `top` every time a group opens or the window resizes, Q300 rewrites its
   chip bar's `top` on a timer, the labels module re-places its panels on every resize, and the engines' own stylesheets
   place everything else through media queries. Q301 learned this the hard way (H2 iv): "a CSS `top` of ours would
   lose". So this module never sets a position. It sets the box's `translate` -- the independent CSS property, which
   composes with whatever `transform` the stylesheet has and which nothing else on these pages writes -- so the offset
   rides on top of each box's own placement and no existing code has to change. Where `translate` is unsupported the
   fallback composes into `transform` with the author value read once and cached (see `setOff`).

     NMSKMove.start({key, history, boxes:[...], protect:[...], guard, note})
     NMSKMove.add(box)                box := {key, el:"id"|fn, at:"tl"|"tr"|"bl"|"br", label, light, with:[ids], axis}
     NMSKMove.restore()               every box back where it started -- ONE undo step
     NMSKMove.off(key) / .rect(key) / .moved() / .slots(key) / .state() / .refresh()
   The store is per page, in localStorage, every read and write in try / catch: it can throw (a private window, blocked
   site data) and it can come back empty, and the page must be exactly as usable either way. */
var NMSKMove = (function(){
  "use strict";
  var B = [], byKey = {}, on = false, hist = null, KEY = "nmsk.q305.layout", PH = null, note = null, guard = null;
  var drag = null, poll = 0, restores = 0, drops = 0, reverts = 0, PAD = 12, THRESH = 4, STEP = 16;
  var GRIP = '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">' +
             '<circle cx="5.2" cy="4" r="1.35" fill="currentColor"/><circle cx="10.8" cy="4" r="1.35" fill="currentColor"/>' +
             '<circle cx="5.2" cy="8" r="1.35" fill="currentColor"/><circle cx="10.8" cy="8" r="1.35" fill="currentColor"/>' +
             '<circle cx="5.2" cy="12" r="1.35" fill="currentColor"/><circle cx="10.8" cy="12" r="1.35" fill="currentColor"/></svg>';

  function vw(){ return Math.max(1, window.innerWidth || document.documentElement.clientWidth || 1); }
  function vh(){ return Math.max(1, window.innerHeight || document.documentElement.clientHeight || 1); }
  /* A phone by the same test the rest of the project uses for its 390x844 measurements, plus the pointer, so a narrow
     desktop window is not treated as a phone and a wide tablet is. */
  function phone(){
    if (PH !== null) return PH;
    var coarse = false;
    try { coarse = !!(window.matchMedia && window.matchMedia("(pointer:coarse)").matches); } catch (err){ coarse = false; }
    return vw() <= 560 && (coarse || vw() <= 430);
  }
  var CAN_T = (function(){ try { return !!(window.CSS && CSS.supports && CSS.supports("translate", "1px 1px")); } catch (err){ return false; } })();

  /* ---- the store ---- */
  function load(){
    var o = {};
    try { var t = localStorage.getItem(KEY); if (t){ var j = JSON.parse(t); if (j && typeof j === "object") o = j; } } catch (err){ o = {}; }
    return o;
  }
  function save(){
    var o = {};
    B.forEach(function(b){ if (b.dx || b.dy || b.slot) o[b.key] = b.slot ? {s:b.slot} : {x:Math.round(b.dx), y:Math.round(b.dy)}; });
    try { localStorage.setItem(KEY, JSON.stringify(o)); } catch (err){}
  }

  /* ---- the offset, applied ---- */
  function el(b){
    if (b._el && b._el.isConnected) return b._el;
    b._el = typeof b.el === "function" ? b.el() : document.getElementById(b.el);
    return b._el;
  }
  /* A box counts as on the screen only if it OVERLAPS the viewport. The engines park a closed bottom sheet just below
     the bottom edge (`transform: translateY(100% + 4px)` on the Z rail, `translateY(120%)` on the own engine's phone
     panels), and the first draft of the clamp, which clamped every box whether it had been moved or not, DRAGGED THAT
     CLOSED SHEET BACK ON SCREEN -- 538 px up on a 390x844 phone, over the model, where it then swallowed the orbit.
     The harness reported it as "the model no longer orbits", which is what that defect would have looked like to the
     owner. Two rules came out of it: a box off the screen is not ours to touch, and a box with no offset of ours is
     never clamped at all. */
  function shown(e){
    if (!e || !e.getBoundingClientRect) return false;
    var r = e.getBoundingClientRect();
    if (!(r.width > 8 && r.height > 8)) return false;
    return r.right > 0 && r.bottom > 0 && r.left < vw() && r.top < vh();
  }
  function setOff(e, dx, dy){
    if (!e) return;
    if (CAN_T){ e.style.translate = (dx || dy) ? (Math.round(dx) + "px " + Math.round(dy) + "px") : ""; return; }
    /* fallback: compose into `transform`, with the AUTHOR value read once -- reading it again would read our own */
    if (e._nmBase === undefined){
      var t = "";
      try { t = getComputedStyle(e).transform; } catch (err){ t = ""; }
      e._nmBase = (!t || t === "none") ? "" : t;
    }
    e.style.transform = (dx || dy) ? (e._nmBase + " translate(" + Math.round(dx) + "px," + Math.round(dy) + "px)").trim() : e._nmBase;
  }
  /* The applied offset is CLAMPED; the stored one is not. So a box pushed to the edge of a small window comes back to
     where the user actually put it when the window is big again, which is what "remembered" has to mean. */
  function clamped(b, dx, dy){
    var e = el(b); if (!e) return [0, 0];
    if (!dx && !dy) return [0, 0];                   /* an untouched box is left exactly where the page puts it */
    setOff(e, 0, 0);
    var r = e.getBoundingClientRect();
    /* a box the PAGE itself keeps off the screen (a closed sheet) is not pulled back on by our clamp */
    if (!(r.right > 0 && r.bottom > 0 && r.left < vw() && r.top < vh())) return [dx, dy];
    var lo = {x:PAD - r.left, y:PAD - r.top}, hi = {x:vw() - PAD - r.right, y:vh() - PAD - r.bottom};
    /* a box as wide (or as tall) as the viewport has no freedom on that axis: lock it rather than let it drift off */
    var ox = (r.width > vw() - 2 * PAD) ? 0 : Math.max(lo.x, Math.min(hi.x, dx));
    var oy = (r.height > vh() - 2 * PAD) ? 0 : Math.max(lo.y, Math.min(hi.y, dy));
    if (b.axis === "y") ox = 0;
    if (b.axis === "x") oy = 0;
    return [ox, oy];
  }
  function base(b){                                   /* the box's rectangle with no offset of ours */
    var e = el(b); if (!e) return null;
    var keep = [b._ax, b._ay];
    setOff(e, 0, 0);
    var r = e.getBoundingClientRect();
    setOff(e, keep[0] || 0, keep[1] || 0);
    return r;
  }
  /* DOES THE PAGE PUT THIS BOX ON THE SCREEN -- not "is it on the screen right now", which includes our own offset.
     That distinction is a measured fix, not a nicety. A slot is a position relative to the box's own BASE rectangle,
     and the other rounds move that base after we have resolved it: Q301's `place()` rewrites the control bar's
     `left` / `top` when a group opens, on every resize, and -- at boot -- AFTER our first pass. Resolved against a
     base that then moves, a slot's offset puts the box off the screen; and `shown()` was then false, so the 600 ms
     self-healing pass that would have re-resolved it skipped the box FOR EVER. Measured on the Base page at
     390x844: after a reload with a stored `mc` slot the control bar came back at top **936** of an 844 px viewport
     and stayed there, which took Undo, Redo and the whole bar with it. Asking the question about the base instead,
     the pass re-resolves the slot from the bar's real place on the next tick. A bottom sheet the page itself keeps
     off the screen still answers no -- that is the case this guard exists for, and it is why `clamped()` already
     asks the same thing of the base rather than of the box. */
  function shownBase(b){
    var e = el(b); if (!e) return false;
    if (!(b._ax || b._ay)) return shown(e);           /* nothing of ours applied: the two questions are the same */
    var r = base(b); if (!r) return false;
    if (!(r.width > 8 && r.height > 8)) return false;
    return r.right > 0 && r.bottom > 0 && r.left < vw() && r.top < vh();
  }
  /* ---- the phone's slots. Measured, not assumed: a box whose free travel on an axis is under one thumb (48 px) gets
     slots on that axis instead of free drag, because 16 px of travel is not a feature. A wide box therefore gets three
     bands (top / middle / bottom) and a small one the four corners. ---- */
  function slotsOf(b){
    var r = base(b); if (!r) return [];
    var freeX = vw() - 2 * PAD - r.width, freeY = vh() - 2 * PAD - r.height;
    var wide = freeX < 48, tall = freeY < 48;
    var xs = wide ? [{k:"c", x:PAD - r.left + (vw() - 2 * PAD - r.width) / 2}]
                  : [{k:"l", x:PAD - r.left}, {k:"r", x:vw() - PAD - r.right}];
    var ys = tall ? [{k:"m", y:PAD - r.top + (vh() - 2 * PAD - r.height) / 2}]
                  : [{k:"t", y:PAD - r.top}, {k:"m", y:PAD - r.top + (vh() - 2 * PAD - r.height) / 2}, {k:"b", y:vh() - PAD - r.bottom}];
    var out = [];
    ys.forEach(function(q){ xs.forEach(function(p){ out.push({key:q.k + p.k, dx:p.x, dy:q.y, w:r.width, h:r.height, left:r.left + p.x, top:r.top + q.y}); }); });
    return out;
  }
  function slotOff(b){
    var s = slotsOf(b), i;
    for (i = 0; i < s.length; i++) if (s[i].key === b.slot) return [s[i].dx, s[i].dy];
    return [0, 0];
  }
  function apply(b, write){
    var e = el(b); if (!e) return;
    var o;
    if (phone() && b.slot) o = slotOff(b);
    else o = clamped(b, b.dx || 0, b.dy || 0);
    b._ax = o[0]; b._ay = o[1];
    setOff(e, o[0], o[1]);
    /* a box that another round positions FROM this one travels with it: Q301's open group sheet is placed relative to
       the control bar, so it takes the bar's offset and the two keep their 4 px gap */
    (b["with"] || []).forEach(function(id){ var w = document.getElementById(id); if (w) setOff(w, o[0], o[1]); });
    if (b._grip) b._grip.classList.toggle("nm-on", !!(b.dx || b.dy || b.slot));
    if (write) save();
  }
  function applyAll(write){ B.forEach(function(b){ if (shownBase(b)) apply(b, false); }); if (write) save(); }

  /* ---- the grip ---- */
  function grip(b){
    var e = el(b);
    if (!e || b._grip) return b._grip || null;
    var g = document.createElement("button");
    g.type = "button"; g.className = "nm-grip" + (b.light ? " nm-light" : ""); g.id = "nm-g-" + b.key;
    g.setAttribute("data-nm", b.key);
    g.title = "Drag this handle to move " + (b.label || "this box") + " (arrow keys move it, Home puts it back)";
    g.setAttribute("aria-label", "Move " + (b.label || "this box"));
    g.innerHTML = GRIP;
    /* Where the grip goes, decided from the box itself rather than per page. `into` puts it in a row of the box's own
       controls as one more button -- the control bar's lower row, beside Undo and Redo, which is the only place on
       that bar where a handle covers nothing. Every other box gets it inside one of its own corners (see below). */
    var into = b.into ? document.getElementById(b.into) : null;
    if (into){
      g.classList.add("nm-inline"); g.style.position = "relative"; g.style.flex = "0 0 auto";
      into.appendChild(g);
    } else {
      /* FULLY INSIDE the box, never hanging over its edge. The first draft hung the grip half out of the corner so it
         covered none of the box's own content; the harness showed what that really does -- the overhang lands on
         WHATEVER BOX IS BEHIND, and a grip under another box cannot be grabbed, so the box could never be moved back.
         (It is also simply invisible on the boxes that clip their overflow: the Z rail, the group sheet, the needle
         panel.) Inside, a grip can only be covered when another box genuinely covers that corner -- which is a real
         overlap, and the guard reports it. */
      corner(g, b.at || "tl");
      /* the box must be a positioning context, or an absolute grip escapes to the page. Only set it when it is static. */
      try { if (getComputedStyle(e).position === "static") e.style.position = "relative"; } catch (err2){}
      e.appendChild(g);
    }
    b._grip = g;
    bind(g, b);
    return g;
  }

  var CORNERS = ["tl", "tr", "br", "bl"];
  function corner(g, at){
    var st = g.style;
    st.top = st.bottom = st.left = st.right = "";
    if (at.charAt(0) === "t") st.top = "3px"; else st.bottom = "3px";
    if (at.charAt(1) === "l") st.left = "3px"; else st.right = "3px";
    g.setAttribute("data-nm-at", at);
  }
  /* WHICH CORNER, decided by measurement and re-decided whenever the page changes. A grip is useless under another box,
     and on a 390 px phone the control bar really does sit over the bottom-right card. So the grip tries the four
     corners in turn and keeps the first one whose own centre belongs to it -- the same `elementFromPoint` test the
     guard uses, and the same instrument that caught Q301's two collisions. */
  function reseat(b){
    var g = b._grip, e = el(b);
    if (!g || !e) return;
    var start = CORNERS.indexOf(g.getAttribute("data-nm-at") || "tl"), i, j, r, t;
    for (i = 0; i < CORNERS.length; i++){
      j = (start + i) % CORNERS.length;
      corner(g, CORNERS[j]);
      r = g.getBoundingClientRect();
      if (!(r.width > 0)) continue;
      try { t = document.elementFromPoint(Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)); } catch (err){ t = null; }
      if (t === g || g.contains(t)) return;
    }
    corner(g, CORNERS[start < 0 ? 0 : start]);          /* every corner is covered: leave it where it was and say so */
  }

  /* ---- the drag itself ----
     ONE pointer only, and a 4 px threshold. That is what keeps it clear of every gesture this page already has: a
     second pointer on the grip CANCELS the move and puts the box back, so a pinch that happens to start on a grip is a
     pinch and not a move; the threshold means a tap on the grip does nothing at all; and the grip is 26-34 px of
     chrome, never the canvas, never a list row, so the orbit, the probe and the long-press ranges are not touched. */
  /* THE POINTER COUNT IS KEPT FOR THE WHOLE DOCUMENT, and this is the defect the harness found before a template was
     touched. A pinch whose FIRST finger lands on the handle puts its SECOND finger beside the handle, where the handle
     never gets a pointerdown of its own -- so a count kept on the handle stays at one and the pinch dragged the box
     about 100 px. Counted on the document it is a second pointer wherever it lands, and the drag is cancelled. */
  var LIVE = {};
  (function(){
    function down(e){
      /* A primary pointerdown with no drag running is the start of a new gesture, so the table is rebuilt from it.
         That is what makes the count self-healing: a pointerup that never arrives (a cancelled touch, a window that
         loses focus mid-gesture) would otherwise leave a phantom finger behind and refuse every later move. */
      if (!drag && e.isPrimary !== false) LIVE = {};
      LIVE[e.pointerId] = 1;
      if (drag && Object.keys(LIVE).length > 1) cancel();
    }
    function up(e){ delete LIVE[e.pointerId]; }
    document.addEventListener("pointerdown", down, true);
    document.addEventListener("pointerup", up, true);
    document.addEventListener("pointercancel", up, true);
  })();
  function bind(g, b){
    g.addEventListener("pointerdown", function(e){
      if (Object.keys(LIVE).length > 1){ cancel(); return; }    /* a second finger: this is a pinch, not a move */
      if (e.button != null && e.button !== 0) return;
      var r = el(b).getBoundingClientRect();
      drag = {b:b, g:g, done:done, id:e.pointerId, x:e.clientX, y:e.clientY, dx:b.dx || 0, dy:b.dy || 0, slot:b.slot || "",
              moved:false, bad0:badNow(), ghosts:null, r0:{left:r.left, top:r.top}};
      try { g.setPointerCapture(e.pointerId); } catch (err){}
      e.preventDefault(); e.stopPropagation();
    });
    g.addEventListener("pointermove", function(e){
      if (!drag || drag.id !== e.pointerId) return;
      var mx = e.clientX - drag.x, my = e.clientY - drag.y;
      if (!drag.moved){
        if (Math.abs(mx) < THRESH && Math.abs(my) < THRESH) return;
        drag.moved = true;
        el(b).classList.add("nm-box-drag");
        if (phone()) drag.ghosts = ghosts(b);
      }
      b.slot = ""; b.dx = drag.dx + mx; b.dy = drag.dy + my;
      apply(b, false);
      if (drag.ghosts) near(b, drag.ghosts);
      e.preventDefault(); e.stopPropagation();
    });
    function done(e){
      if (!drag || (e && drag.id !== e.pointerId)) return;
      var d = drag, bb = d.b;
      drag = null;
      release(d);
      el(bb).classList.remove("nm-box-drag");
      if (d.ghosts) d.ghosts.forEach(function(x){ if (x.node && x.node.parentNode) x.node.parentNode.removeChild(x.node); });
      if (!d.moved) return;                                     /* a tap on the grip is not a move */
      if (phone()){ var s = nearest(bb); if (s){ bb.slot = s.key; bb.dx = 0; bb.dy = 0; } }
      apply(bb, true);
      drops++;
      /* THE COLLISION CHECK, as a product rule and not only as a test. Q301 hit this twice: its own info drawer ate
         Undo on a phone, and Q300's chip bar sat on Redo. A drop that leaves any protected control unreachable is
         refused and the box goes back to where it was, with one line saying so. */
      var bad = badNow();
      if (bad.length > d.bad0.length){
        bb.dx = d.dx; bb.dy = d.dy; bb.slot = d.slot;
        apply(bb, true); reverts++;
        say("Not there -- it would cover " + bad[0].label + ". The box is back where it was.");
      } else if (hist && hist.commit){ hist.commit(); }
      if (window.NMSKGroups && NMSKGroups.state) { try { NMSKGroups.state(); } catch (err){} }
    }
    g.addEventListener("pointerup", done);
    g.addEventListener("pointercancel", done);
    /* A SAFETY NET, and it is not theoretical. A pointerup that is delivered somewhere else -- or not delivered at all,
       which is what happens when the window loses focus or the gesture is cancelled by the system -- would leave the
       drag running AND the handle holding an implicit pointer capture, and a capturing handle keeps every later
       pointer event: the model would simply stop orbiting and nothing would say why. So the document ends it too. */
    document.addEventListener("pointerup", function(e){ if (drag && drag.id === e.pointerId && drag.g === g) done(e); }, true);
    document.addEventListener("pointercancel", function(e){ if (drag && drag.id === e.pointerId && drag.g === g) done(e); }, true);
    g.addEventListener("lostpointercapture", function(e){ if (drag && drag.id === e.pointerId) done(e); });
    g.addEventListener("click", function(e){ e.preventDefault(); e.stopPropagation(); });
    g.addEventListener("keydown", function(e){
      var k = e.key, d = {ArrowLeft:[-STEP, 0], ArrowRight:[STEP, 0], ArrowUp:[0, -STEP], ArrowDown:[0, STEP]}[k];
      if (k === "Home"){ b.dx = 0; b.dy = 0; b.slot = ""; apply(b, true); if (hist && hist.commit) hist.commit(); e.preventDefault(); return; }
      if (!d) return;
      if (phone()){
        var s = slotsOf(b), i = 0, j;
        for (j = 0; j < s.length; j++) if (s[j].key === b.slot) i = j;
        b.slot = s.length ? s[(i + (d[0] + d[1] > 0 ? 1 : s.length - 1)) % s.length].key : "";
      } else { b.dx = (b.dx || 0) + d[0]; b.dy = (b.dy || 0) + d[1]; }
      var keep = [b.dx, b.dy, b.slot];
      apply(b, true);
      var bad = badNow();
      if (bad.length){ b.dx = keep[0] - d[0]; b.dy = keep[1] - d[1]; apply(b, true); say("Not there -- it would cover " + bad[0].label + "."); }
      else if (hist && hist.commit) hist.commit();
      e.preventDefault();
    });
  }
  function release(d){
    /* An implicit pointer capture is released by the browser on pointerup -- but if the gesture is cancelled, or the
       pointerup never arrives, a capturing handle keeps EVERY later pointer event, which looks exactly like "the model
       stopped orbiting". Released by hand, always. */
    try { if (d && d.g && d.g.releasePointerCapture) d.g.releasePointerCapture(d.id); } catch (err){}
  }
  function cancel(){
    if (!drag) return;
    var d = drag; drag = null;
    release(d);
    d.b.dx = d.dx; d.b.dy = d.dy; d.b.slot = d.slot;
    var e = el(d.b); if (e) e.classList.remove("nm-box-drag");
    if (d.ghosts) d.ghosts.forEach(function(x){ if (x.node && x.node.parentNode) x.node.parentNode.removeChild(x.node); });
    apply(d.b, false);
  }

  /* ---- the slot ghosts, drawn only while a phone drag is running ---- */
  function ghosts(b){
    var s = slotsOf(b);
    return s.map(function(q){
      var n = document.createElement("div");
      n.className = "nm-slot";
      n.style.left = Math.round(q.left) + "px"; n.style.top = Math.round(q.top) + "px";
      n.style.width = Math.round(q.w) + "px"; n.style.height = Math.round(q.h) + "px";
      document.body.appendChild(n);
      q.node = n; return q;
    });
  }
  function nearest(b){
    var e = el(b); if (!e) return null;
    var r = e.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    var s = slotsOf(b), best = null, bd = Infinity;
    s.forEach(function(q){
      var d = Math.hypot(q.left + q.w / 2 - cx, q.top + q.h / 2 - cy);
      if (d < bd){ bd = d; best = q; }
    });
    return best;
  }
  function near(b, gs){
    var n = nearest(b);
    gs.forEach(function(q){ if (q.node) q.node.classList.toggle("nm-near", !!n && q.key === n.key); });
  }

  /* ---- what must stay reachable ---- */
  function badNow(){ try { return guard && guard.hard ? guard.hard() : []; } catch (err){ return []; } }
  function say(m){
    if (!m) return;
    if (!note){ note = document.createElement("div"); note.className = "nm-note"; document.body.appendChild(note); }
    note.textContent = m;
    note.style.bottom = "calc(" + (getComputedStyle(document.documentElement).getPropertyValue("--q301-bar-h") || "100px").trim() + " + 10px)";
    note.hidden = false;
    clearTimeout(say.t); say.t = setTimeout(function(){ note.hidden = true; }, 3400);
  }

  /* ---- restore the layout: every box back where it started, as ONE undo step ---- */
  function restore(){
    var any = B.some(function(b){ return b.dx || b.dy || b.slot; });
    B.forEach(function(b){ b.dx = 0; b.dy = 0; b.slot = ""; });
    applyAll(true); restores++;
    if (hist && hist.commit) hist.commit();
    say(any ? "Every box is back where it started." : "Every box is already where it started.");
    return any;
  }

  var api = {
    start:function(opt){
      opt = opt || {};
      if (on) return api;
      hist = opt.history || window.NMSKHistory || null;
      guard = opt.guard || window.NMSKGuard || null;
      if (opt.key) KEY = "nmsk.q305.layout." + opt.key;
      PAD = opt.pad || PAD;
      (opt.boxes || []).forEach(api.add);
      var saved = load();
      B.forEach(function(b){
        var v = saved[b.key];
        if (!v) return;
        if (v.s) b.slot = String(v.s); else { b.dx = +v.x || 0; b.dy = +v.y || 0; }
      });
      /* an ordinary history provider, so the layout is in Q294's Undo / Redo and in Q300's model reset for free: the
         model reset restores the history's own load snapshot, and this key is in it. `reset` is deliberately a no-op --
         Q294's Reset is "the module you are in", and the boxes are the page's chrome, not a module's state. */
      if (hist && hist.register) hist.register("q305layout", {
        get:function(){ var o = {}; B.forEach(function(b){ o[b.key] = b.slot ? b.slot : [Math.round(b.dx || 0), Math.round(b.dy || 0)]; }); return o; },
        set:function(v){
          if (!v) return;
          B.forEach(function(b){
            var x = v[b.key];
            if (typeof x === "string"){ b.slot = x; b.dx = 0; b.dy = 0; }
            else if (x && x.length === 2){ b.slot = ""; b.dx = +x[0] || 0; b.dy = +x[1] || 0; }
            else { b.slot = ""; b.dx = 0; b.dy = 0; }
          });
          applyAll(true);
        },
        reset:function(){}
      });
      on = true;
      api.refresh();
      /* The boxes come and go with the engines' own code (the cut panel, the i drawer, the chip bar are built or shown
         later) and every other round re-places them, so the grips are attached and the offsets re-applied on a slow
         poll as well as on resize -- the same shape as Q300's and Q301's own timers. */
      poll = setInterval(api.refresh, 600);
      window.addEventListener("blur", function(){ cancel(); });
      window.addEventListener("resize", function(){ PH = null; api.refresh(); });
      window.addEventListener("orientationchange", function(){ PH = null; setTimeout(api.refresh, 60); setTimeout(api.refresh, 400); });
      return api;
    },
    add:function(b){
      if (!b || !b.key || byKey[b.key]) return false;
      b.dx = b.dx || 0; b.dy = b.dy || 0; b.slot = b.slot || "";
      B.push(b); byKey[b.key] = b;
      return true;
    },
    refresh:function(){
      if (!on || drag) return;
      B.forEach(function(b){
        var e = el(b);
        if (!shownBase(b)){ if (b._grip && !e) b._grip = null; return; }
        var fresh = !b._grip || !b._grip.isConnected;
        if (fresh){ b._grip = null; grip(b); }
        apply(b, false);
        if (!b.into) reseat(b);
      });
    },
    restore:restore,
    off:function(k){ var b = byKey[k]; return b ? {dx:Math.round(b.dx || 0), dy:Math.round(b.dy || 0), slot:b.slot || "", ax:Math.round(b._ax || 0), ay:Math.round(b._ay || 0)} : null; },
    rect:function(k){
      var b = byKey[k]; if (!b) return null;
      var e = el(b); if (!shown(e)) return null;
      var r = e.getBoundingClientRect();
      return {left:Math.round(r.left), top:Math.round(r.top), width:Math.round(r.width), height:Math.round(r.height)};
    },
    slots:function(k){ var b = typeof k === "string" ? byKey[k] : k; return b ? slotsOf(b) : []; },
    dragging:function(){ return !!drag; },
    moved:function(){ return B.filter(function(b){ return b.dx || b.dy || b.slot; }).map(function(b){ return b.key; }); },
    keys:function(){ return B.map(function(b){ return b.key; }); },
    present:function(){ return B.filter(function(b){ return shown(el(b)); }).map(function(b){ return b.key; }); },
    phone:function(){ return phone(); },
    state:function(){
      return {on:on, phone:phone(), translate:CAN_T, key:KEY, drops:drops, reverts:reverts, restores:restores,
              boxes:B.map(function(b){
                var r = api.rect(b.key);
                return {key:b.key, label:b.label || b.key, present:!!r, rect:r, off:api.off(b.key), grip:!!(b._grip && b._grip.isConnected),
                        slots:(r && phone()) ? slotsOf(b).map(function(s){ return s.key; }) : []};
              })};
    }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKMove;
