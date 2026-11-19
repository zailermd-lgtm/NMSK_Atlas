/* Q290: two-finger zoom on every surface. Owner: "in all modules, also on mobile, allow zooming the screen like in a browser,
   so you can focus on specific places without playing with the menus".
   Each surface (the 3-D canvas of either engine, and the 2-D image panes of the optional add-ons) keeps
   its own content zoom -- a pinch zooms toward the point between the fingers and a two-finger drag pans; the menus are not
   part of any surface, so they never move or scale. This file holds only what the surfaces share:
     NMSKPinch.pair(pts)                  midpoint + spread of two pointers {x, y, d}
     NMSKPinch.track(el, h)               two touch / pen pointers on el -> h.start(), h.move(f, x, y, dx, dy) (el-local x, y;
                                          f = spread ratio since the last move; dx, dy = midpoint travel), h.end(); .busy()
                                          is true during a pinch and for 400 ms after it (so the lifted fingers are not a tap)
     NMSKPinch.view()                     a 2-D view transform {k, tx, ty} (screen = k * base + t): about(x, y, f) zooms about
                                          a point, pan(dx, dy), clamp(w, h) keeps the zoomed content covering the frame, reset()
     NMSKPinch.chip(anchor, onReset, o)   the tiny "2.4x | 1:1" chip on the anchor's rectangle: shown for a few seconds on every
                                          zoom / size change while zoomed, then faded (Q382; hovering or touching it keeps it, and
                                          prefs() can make it permanent); a tap calls onReset (o.pos = "tc" | "tl" | "tr" | "bc" |
                                          "bl" | "br", o.dy extra offset). It moves to the nearest free spot instead of lying on
                                          another control.
     NMSKPinch.prefs() / .setPrefs({always, secs})   the chip's show mode (default: 10 s) -- kept in localStorage, try / catch
     NMSKPinch.reveal() / .resetAll()     show every zoomed chip again / put every zoomed surface back to 1:1
     NMSKPinch.dbl()                      returns fn(e): true on the second of two quick taps at one place (touch / pen only,
                                          so a desktop double-click keeps its old meaning)
   Native page zoom: the viewport allows it (no user-scalable=no); the canvases keep touch-action:none, so a pinch on them is
   the surface's own zoom, and a pinch on a panel is the browser's. While the browser zoom is on (visualViewport.scale > 1,
   a top-level page only -- inside an embedding frame the browser zooms the embedding page and this page cannot see it), the
   main toolbars are drawn at 1:1 on the visible part of the page and a chip offers the way back. */
(function () {
  "use strict";
  if (window.NMSKPinch) return;

  function pair(pts) {
    var a = pts[0], b = pts[1];
    return {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, d: Math.max(1, Math.hypot(a.x - b.x, a.y - b.y))};
  }

  function track(el, h) {
    var pts = new Map(), g = null, endT = 0;
    function two() { var v = []; pts.forEach(function (p) { if (v.length < 2) v.push(p); }); return pair(v); }
    el.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse") return;
      pts.set(e.pointerId, {x: e.clientX, y: e.clientY});
      if (pts.size === 2) { g = two(); if (h.start) h.start(); }
    }, true);
    el.addEventListener("pointermove", function (e) {
      if (!pts.has(e.pointerId)) return;
      pts.set(e.pointerId, {x: e.clientX, y: e.clientY});
      if (!g || pts.size < 2) return;
      var n = two(), r = el.getBoundingClientRect();
      h.move(n.d / g.d, n.x - r.left, n.y - r.top, n.x - g.x, n.y - g.y);
      g = n; e.stopPropagation();
    }, true);
    function up(e) {
      if (!pts.delete(e.pointerId)) return;
      if (g && pts.size < 2) { g = null; endT = Date.now(); if (h.end) h.end(); }
    }
    el.addEventListener("pointerup", up, true);
    el.addEventListener("pointercancel", up, true);
    return {busy: function () { return !!g || Date.now() - endT < 400; }, active: function () { return !!g; }};
  }

  function view(kmin, kmax) {
    var z = {k: 1, tx: 0, ty: 0, kmin: kmin || 1, kmax: kmax || 8};
    z.about = function (x, y, f) {
      var k1 = Math.max(z.kmin, Math.min(z.kmax, z.k * f)); f = k1 / z.k;
      z.tx = x - (x - z.tx) * f; z.ty = y - (y - z.ty) * f; z.k = k1; return z;
    };
    z.pan = function (dx, dy) { z.tx += dx; z.ty += dy; return z; };
    z.clamp = function (w, h) {                                   // the zoomed frame never uncovers its own edges
      z.tx = Math.min(0, Math.max(w * (1 - z.k), z.tx)); z.ty = Math.min(0, Math.max(h * (1 - z.k), z.ty)); return z;
    };
    z.reset = function () { z.k = 1; z.tx = 0; z.ty = 0; return z; };
    z.zoomed = function () { return Math.abs(z.k - 1) > 0.02 || Math.abs(z.tx) > 1 || Math.abs(z.ty) > 1; };
    z.map = function (x, y) { return [z.k * x + z.tx, z.k * y + z.ty]; };
    return z;
  }

  /* Q382: how long the chip stays. Owner: "the dimensions window should be visible on every size change for 10 seconds and then
     disappear; in Settings it can be changed to permanent, or the delay changed". */
  var PKEY = "nmsk.q382.chip", prefs = {always: false, secs: 10}, chips = [];
  (function () {
    try { var j = JSON.parse(localStorage.getItem(PKEY) || "null"); if (j && typeof j === "object") { prefs.always = !!j.always; if (j.secs > 0) prefs.secs = Math.min(600, +j.secs); } } catch (e) {}
  })();
  function getPrefs() { return {always: prefs.always, secs: prefs.secs}; }
  function setPrefs(o) {
    if (o && o.always != null) prefs.always = !!o.always;
    if (o && o.secs != null && +o.secs > 0) prefs.secs = Math.min(600, Math.max(0.2, +o.secs));
    try { localStorage.setItem(PKEY, JSON.stringify(prefs)); } catch (e) {}
    chips.forEach(function (c) { c.refade(); });
    return getPrefs();
  }
  /* the show / fade timer shared by both kinds of chip: poke() = "something changed, show it", the fade starts after the delay unless
     the pointer is on the chip (or it has focus), or the mode is "always" */
  function fader(b) {
    var tm = 0, held = false, off = false;
    function arm() {
      clearTimeout(tm); tm = 0;
      if (prefs.always || held || off) return;
      tm = setTimeout(function () { tm = 0; if (held) return; off = true; b.classList.add("pz-off"); }, prefs.secs * 1000);
    }
    function on() { off = false; b.classList.remove("pz-off"); arm(); }
    ["pointerenter", "focus"].forEach(function (n) { b.addEventListener(n, function () { held = true; clearTimeout(tm); tm = 0; }); });
    ["pointerleave", "blur"].forEach(function (n) { b.addEventListener(n, function () { held = false; if (!off) arm(); }); });
    b.addEventListener("pointerup", function (e) { if (e.pointerType !== "mouse") { held = false; arm(); } });
    b.addEventListener("pointercancel", function () { held = false; arm(); });
    return {
      poke: on,
      refade: function () { if (prefs.always) on(); else if (!off) arm(); },
      reset: function () { clearTimeout(tm); tm = 0; off = false; held = false; b.classList.remove("pz-off"); },
      faded: function () { return off; }
    };
  }

  function fmt(k) { return (k >= 10 ? Math.round(k) : Math.round(k * 10) / 10) + "×"; }

  /* Q382: is the box x, y, w, h lying on another control? Sampled with elementsFromPoint (a corner, the middle of each side and the
     centre): anything that is not the chip, the anchor surface (or what it contains) or the page itself is in the way. */
  function blocked(chipEl, anchorEl, x, y, w, h) {
    var xs = [x + 2, x + w / 2, x + w - 2], ys = [y + 2, y + h / 2, y + h - 2];
    if (x < 0 || y < 0 || x + w > window.innerWidth || y + h > window.innerHeight) return true;
    for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) {
      var L = document.elementsFromPoint(xs[i], ys[j]);
      for (var k = 0; k < L.length; k++) {
        var e = L[k];
        if (e === chipEl || e.classList && e.classList.contains("pz-chip")) continue;
        if (e === document.documentElement || e === document.body || e === anchorEl || (anchorEl && anchorEl.contains(e)) || (e.contains && anchorEl && e.contains(anchorEl))) break;
        if (e.tagName === "CANVAS") break;
        var cs = getComputedStyle(e);
        if (cs.pointerEvents === "none" || cs.visibility === "hidden" || +cs.opacity === 0) continue;
        if (e.classList && (e.classList.contains("nm-note"))) continue;
        return true;
      }
    }
    return false;
  }
  /* the nearest free spot: the asked-for place first, then upwards in steps, then sideways along the asked-for row */
  function freeSpot(b, a, x, y, w, hh) {
    if (!blocked(b, a, x, y, w, hh)) return [x, y];
    var step = hh + 6, i, s;
    for (i = 1; i <= 14; i++) if (!blocked(b, a, x, y - i * step * 0.6, w, hh)) return [x, y - i * step * 0.6];
    for (i = 1; i <= 8; i++) for (s = -1; s <= 1; s += 2) if (!blocked(b, a, x + s * i * (w + 8), y, w, hh)) return [x + s * i * (w + 8), y];
    for (i = 1; i <= 8; i++) for (s = -1; s <= 1; s += 2) if (!blocked(b, a, x + s * i * (w + 8), y - 2 * step, w, hh)) return [x + s * i * (w + 8), y - 2 * step];
    return [x, y];
  }

  function chip(anchor, onReset, o) {
    o = o || {};
    var b = document.createElement("button"), t = 0, last = "", fd = fader(b), kShown = null, spot = null, spotKey = "";
    b.type = "button"; b.className = "pz-chip"; b.hidden = true;
    b.setAttribute("aria-label", "Reset zoom to 1:1"); b.title = "Back to 1:1 (or double-tap empty space)";
    b.innerHTML = '<span class="pz-k"></span><span class="pz-r">1:1</span>';
    b.addEventListener("pointerdown", function (e) { e.stopPropagation(); });
    b.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); onReset(); });
    function el() { return typeof anchor === "function" ? anchor() : anchor; }
    function place() {
      t = 0; if (b.hidden) return;
      if (!b.parentNode) (document.body || document.documentElement).appendChild(b);
      var a = el(), r = a && a.isConnected ? a.getBoundingClientRect() : null;
      if (!r || r.width < 8 || r.height < 8) b.style.visibility = "hidden";
      else {
        var w = b.offsetWidth || 70, hh = b.offsetHeight || 26, pos = o.pos || "tc", m = o.margin == null ? 8 : o.margin;
        var x = pos.charAt(1) === "l" ? r.left + m : pos.charAt(1) === "r" ? r.right - w - m : r.left + (r.width - w) / 2;
        var y = pos.charAt(0) === "t" ? r.top + m + (o.dy || 0) : r.bottom - hh - m - (o.dy || 0);
        if (!fd.faded()) {                                      // a faded chip is not in anyone's way; it is placed when it comes back
          var ak = Math.round(x) + "," + Math.round(y) + "," + w;
          if (spot && ak === spotKey && !blocked(b, a, spot[0], spot[1], w, hh)) { x = spot[0]; y = spot[1]; }
          else { spot = freeSpot(b, a, x, y, w, hh); spotKey = ak; x = spot[0]; y = spot[1]; }
        }
        var key = Math.round(x) + "," + Math.round(y);
        if (key !== last) { last = key; b.style.left = Math.round(x) + "px"; b.style.top = Math.round(y) + "px"; }
        b.style.visibility = "";
      }
      t = setTimeout(place, 250);                              // follow the anchor while shown (docking, panel scroll, rotation)
    }
    var api = {
      el: b,
      set: function (k, zoomed) {
        if (!zoomed) return this.hide();
        var txt = fmt(k);
        b.firstChild.textContent = txt;
        if (b.hidden) { b.hidden = false; clearTimeout(t); spot = null; fd.poke(); place(); }
        else if (txt !== kShown) { if (fd.faded()) spot = null; fd.poke(); if (!t) place(); }
        kShown = txt;
      },
      hide: function () { b.hidden = true; clearTimeout(t); t = 0; kShown = null; fd.reset(); },
      shown: function () { return !b.hidden && !fd.faded(); },
      refade: fd.refade,
      reveal: function () { if (!b.hidden) { spot = null; fd.poke(); if (!t) place(); } },
      reset: function () { if (!b.hidden) onReset(); }
    };
    chips.push(api);
    return api;
  }

  function dbl() {
    var last = null;
    return function (e) {
      if (!e || e.pointerType === "mouse") return false;
      var now = e.timeStamp || Date.now();                      // the input's own time: a busy page handles queued taps late, not apart
      if (last && now - last.t >= 0 && now - last.t < 380 && Math.hypot(e.clientX - last.x, e.clientY - last.y) < 32) { last = null; return true; }
      last = {t: now, x: e.clientX, y: e.clientY}; return false;
    };
  }

  /* ---- native page zoom: keep the main toolbars at 1:1 on the visible part of the page ---- */
  var PIN = ["#tools", "#topright", "#mode-bar"], nat = null, natF = null, natK = null;
  function natChip() {
    if (nat) return nat;
    nat = document.createElement("button"); nat.type = "button"; nat.className = "pz-chip pz-native"; nat.hidden = true;
    nat.setAttribute("aria-label", "Reset the page zoom to 1:1"); nat.title = "Back to 1:1";
    nat.innerHTML = '<span class="pz-k"></span><span class="pz-r">1:1</span>';
    natF = fader(nat); chips.push({refade: natF.refade});
    nat.addEventListener("click", function () {                  // honoured by Chromium / Android; iOS ignores it (pinch out there)
      var m = document.querySelectorAll('meta[name="viewport"]'), mm = m[m.length - 1]; if (!mm) return;
      var c = mm.getAttribute("content"); mm.setAttribute("content", c + ", maximum-scale=1");
      setTimeout(function () { mm.setAttribute("content", c); }, 350);
    });
    (document.body || document.documentElement).appendChild(nat);
    return nat;
  }
  function pinTo(el, s, ox, oy) {
    if (!el.__pz) el.__pz = {t: el.style.transform, o: el.style.transformOrigin};
    el.style.transform = el.__pz.t; el.style.transformOrigin = "0 0";
    var r = el.getBoundingClientRect();
    el.style.transform = "translate(" + (ox + r.left / s - r.left) + "px," + (oy + r.top / s - r.top) + "px) scale(" + (1 / s) + ")" + (el.__pz.t ? " " + el.__pz.t : "");
  }
  function unpin(el) { if (!el.__pz) return; el.style.transform = el.__pz.t; el.style.transformOrigin = el.__pz.o; el.__pz = null; }
  function vvSync() {
    var vv = window.visualViewport; if (!vv) return;
    var s = vv.scale || 1, on = s > 1.01;
    document.documentElement.classList.toggle("pz-native-on", on);
    PIN.forEach(function (sel) { var el = document.querySelector(sel); if (el) { if (on) pinTo(el, s, vv.offsetLeft, vv.offsetTop); else unpin(el); } });
    if (!on) { natK = null; if (nat) { nat.hidden = true; unpin(nat); if (natF) natF.reset(); } return; }
    var c = natChip(); c.hidden = false; c.firstChild.textContent = fmt(s);
    if (natK !== fmt(s)) { natK = fmt(s); natF.poke(); }
    c.style.left = "0px"; c.style.top = "0px"; c.style.transformOrigin = "0 0";
    var w = c.offsetWidth || 70;
    c.style.transform = "translate(" + (vv.offsetLeft + (vv.width - w / s) / 2) + "px," + (vv.offsetTop + 56 / s) + "px) scale(" + (1 / s) + ")";
  }
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", vvSync);
    window.visualViewport.addEventListener("scroll", vvSync);
  }

  window.NMSKPinch = {pair: pair, track: track, view: view, chip: chip, dbl: dbl, nativeSync: vvSync, PIN: PIN, prefs: getPrefs, setPrefs: setPrefs,
    reveal: function () { chips.forEach(function (c) { if (c.reveal) c.reveal(); }); },
    resetAll: function () { chips.forEach(function (c) { if (c.reset) c.reset(); }); }};
})();
