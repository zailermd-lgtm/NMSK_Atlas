/* One Cut mode for every page (Q197). The plane is {x : n0.x = a}; the removed side is the one where
   rs * (n0.x - a) > 0 (rs = +1 or -1); everything here is in the model's own millimetre frame. The engine
   (three.js clipping planes, or the WebGL fragment-shader discard) is reached only through the adaptor E:
   bounds() target() forward() apply(kn,c,on) project(p) canvasRect() pickPoint(ev) isPhone() [words].
   apply() receives the KEPT half as kn.x + c >= 0 (the convention of the add-on hook's cut()/setCut()). */
function NMSKCutMode(E){
  "use strict";
  var $ = function(id){ return document.getElementById(id); };
  var panel = $("cut-panel"), svg = $("cut-svg"), btn = $("t-cut"), slider = $("cut-pos");
  var WORDS = E.words || {x:["right","left"], y:["upper","lower"], z:["front","back"], view:["far","near"]};   // [rs = +1 side, rs = -1 side]
  var AX = {x:[1,0,0], y:[0,1,0], z:[0,0,1]}, AXN = {x:"X", y:"Y", z:"Z"};
  var NAMES = {x:"sagittal", y:"axial", z:"coronal", view:"facing the camera"};
  var S = {on:false, ori:"x", n0:[1,0,0], rs:1, anchor:[0,0,0], placed:false, a0:0, a:0, lo:0, hi:0, armed:false, hint:""};
  function dot(a, b){ return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }
  function cross(a, b){ return [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]]; }
  function unit(a){ var l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0]/l, a[1]/l, a[2]/l]; }
  function axpy(p, d, t){ return [p[0] + d[0]*t, p[1] + d[1]*t, p[2] + d[2]*t]; }
  function corners(){
    var b = E.bounds(), mn = b.min, mx = b.max, c = [];
    for (var i = 0; i < 8; i++) c.push([(i & 1) ? mx[0] : mn[0], (i & 2) ? mx[1] : mn[1], (i & 4) ? mx[2] : mn[2]]);
    return c;
  }
  function centre(){ var b = E.bounds(); return [(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2, (b.min[2] + b.max[2]) / 2]; }
  function basis(n){ var up = Math.abs(n[1]) < 0.99 ? [0,1,0] : [1,0,0], u = unit(cross(up, n)); return [u, cross(n, u)]; }
  function defRs(ori){ return ori === "view" ? -1 : 1; }          // default: the +axis side (superior / anterior / +X); facing me: the near side
  function range(){
    var lo = 1e18, hi = -1e18;
    corners().forEach(function(c){ var d = dot(S.n0, c); if (d < lo) lo = d; if (d > hi) hi = d; });
    S.lo = Math.min(lo, S.a0); S.hi = Math.max(hi, S.a0);
  }
  function clamp(a){ return Math.max(S.lo, Math.min(S.hi, a)); }
  /* orient: set the plane's orientation (and default side) through `point` (a clicked point, the earlier clicked
     point, the screen centre for facing me, or the model centre) with the offset back at 0 */
  function orient(ori, point){
    S.ori = ori;
    if (ori === "view"){ S.n0 = unit(E.forward()); }
    else S.n0 = AX[ori].slice();
    S.rs = defRs(ori);
    S.anchor = (point || (S.placed ? S.anchor : (ori === "view" ? E.target() : centre()))).slice();
    S.a0 = dot(S.n0, S.anchor); S.a = S.a0; range();
  }
  function planeKept(){ return {kn: [-S.rs * S.n0[0], -S.rs * S.n0[1], -S.rs * S.n0[2]], c: S.rs * S.a}; }
  function mm(v){ return (v < 0 ? "−" : "+") + Math.abs(v).toFixed(1) + " mm"; }
  function ui(){
    if (!panel) return;
    panel.hidden = !S.on;
    if (btn){ btn.setAttribute("aria-pressed", String(S.on)); btn.classList.toggle("on", S.on); }
    document.body.classList.toggle("cut-armed", S.armed && S.on);
    panel.classList.toggle("cp-phone", !!(E.isPhone && E.isPhone()));
    Array.prototype.forEach.call(panel.querySelectorAll("#cut-axis button"), function(b){ b.setAttribute("aria-pressed", String(b.dataset.axis === S.ori)); });
    var w = WORDS[S.ori], a = $("cut-side-a"), b = $("cut-side-b");
    a.textContent = "remove " + w[0]; b.textContent = "remove " + w[1];
    a.setAttribute("aria-pressed", String(S.rs === 1)); b.setAttribute("aria-pressed", String(S.rs === -1));
    $("cut-flip").setAttribute("aria-pressed", String(S.rs !== defRs(S.ori)));
    slider.min = String(Math.floor((S.lo - S.a0) * 2) / 2); slider.max = String(Math.ceil((S.hi - S.a0) * 2) / 2);
    slider.value = String(S.a - S.a0);
    $("cut-mm").textContent = mm(S.a - S.a0);
    $("cut-state").textContent = NAMES[S.ori] + (S.ori === "view" ? "" : ", " + AXN[S.ori] + " = " + S.a.toFixed(1) + " mm");
    $("cut-place").setAttribute("aria-pressed", String(S.armed));
    $("cut-hint").textContent = S.armed ? "Click or tap the model: the plane will pass through that point." : S.hint;
  }
  function push(){
    var p = planeKept();
    E.apply(p.kn, p.c, S.on);
    ui(); overlay();
  }
  /* ---- the plane drawn over the canvas: translucent rectangle, edge, arrow toward the removed side ---- */
  function nearClip(poly){
    var out = [], n = poly.length;
    for (var i = 0; i < n; i++){
      var a = poly[i], b = poly[(i + 1) % n], da = a[2] + a[3], db = b[2] + b[3];
      if (da >= 0) out.push(a);
      if ((da >= 0) !== (db >= 0)){ var t = da / (da - db); out.push([a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t, a[2] + (b[2]-a[2])*t, a[3] + (b[3]-a[3])*t]); }
    }
    return out;
  }
  function scr(q, r){ return [r.left + (q[0]/q[3] * 0.5 + 0.5) * r.width, r.top + (0.5 - 0.5 * q[1]/q[3]) * r.height]; }
  function overlay(){
    if (!svg) return;
    if (!S.on){ svg.style.display = "none"; return; }
    var r = E.canvasRect(), uv = basis(S.n0), U = uv[0], V = uv[1], ua = 1e18, ub = -1e18, va = 1e18, vb = -1e18;
    corners().forEach(function(c){ var x = dot(U, c), y = dot(V, c); ua = Math.min(ua, x); ub = Math.max(ub, x); va = Math.min(va, y); vb = Math.max(vb, y); });
    var pad = 0.03 * Math.max(ub - ua, vb - va); ua -= pad; ub += pad; va -= pad; vb += pad;
    var O = axpy([0,0,0], S.n0, S.a);
    function at(x, y){ return axpy(axpy(O, U, x), V, y); }
    var poly = nearClip([at(ua, va), at(ub, va), at(ub, vb), at(ua, vb)].map(E.project));
    var s = "";
    if (poly.length >= 3) s += '<polygon class="cut-fill" points="' + poly.map(function(q){ return scr(q, r).map(function(v){ return v.toFixed(1); }).join(","); }).join(" ") + '"/>';
    var c0 = (S.placed || S.ori === "view") ? axpy(S.anchor, S.n0, S.a - dot(S.n0, S.anchor)) : at((ua + ub) / 2, (va + vb) / 2);
    var L = 0.11 * Math.max(ub - ua, vb - va), tip = axpy(c0, S.n0, S.rs * L), q0 = E.project(c0), q1 = E.project(tip);
    if (q0[2] + q0[3] > 0 && q1[2] + q1[3] > 0){
      var p0 = scr(q0, r), p1 = scr(q1, r), dx = p1[0] - p0[0], dy = p1[1] - p0[1], len = Math.hypot(dx, dy);
      if (len >= 14){
        var ux = dx / len, uy = dy / len;
        s += '<line class="cut-arrow" x1="' + p0[0].toFixed(1) + '" y1="' + p0[1].toFixed(1) + '" x2="' + (p1[0] - ux*6).toFixed(1) + '" y2="' + (p1[1] - uy*6).toFixed(1) + '"/>' +
             '<polygon class="cut-head" points="' + [p1[0], p1[1], p1[0] - ux*11 - uy*5.5, p1[1] - uy*11 + ux*5.5, p1[0] - ux*11 + uy*5.5, p1[1] - uy*11 - ux*5.5].map(function(v){ return v.toFixed(1); }).join(",") + '"/>';
      } else {                                           // arrow along the view axis: a dot (toward you) or a cross (away)
        var toward = q1[3] < q0[3], g = '<circle class="cut-pt" cx="' + p0[0].toFixed(1) + '" cy="' + p0[1].toFixed(1) + '" r="9"/>';
        g += toward ? '<circle class="cut-head" cx="' + p0[0].toFixed(1) + '" cy="' + p0[1].toFixed(1) + '" r="3"/>'
                    : '<path class="cut-arrow" d="M' + (p0[0]-5).toFixed(1) + ' ' + (p0[1]-5).toFixed(1) + 'l10 10m0-10l-10 10"/>';
        s += g;
      }
      s += '<text x="' + (p1[0] + 9).toFixed(1) + '" y="' + (p1[1] - 7).toFixed(1) + '">removed</text>';
      if (S.placed) s += '<circle class="cut-pt" cx="' + p0[0].toFixed(1) + '" cy="' + p0[1].toFixed(1) + '" r="5"/>';
    }
    svg.style.clipPath = "inset(" + Math.max(0, r.top) + "px " + Math.max(0, document.documentElement.clientWidth - r.right) + "px " +
                         Math.max(0, document.documentElement.clientHeight - r.bottom) + "px " + Math.max(0, r.left) + "px)";
    svg.innerHTML = s; svg.style.display = "block";
  }
  /* ---- actions ---- */
  function move(d){ S.a = clamp(S.a + d); push(); }
  function setOri(o){ S.armed = false; S.hint = ""; orient(o, null); push(); }
  function exit(reset){ S.on = false; S.armed = false; S.hint = ""; if (reset){ S.placed = false; orient("x", null); } push(); }
  function enter(){ S.on = true; push(); }
  orient("x", null);
  if (btn) btn.addEventListener("click", function(){ if (S.on) exit(false); else enter(); });
  Array.prototype.forEach.call(panel.querySelectorAll("#cut-axis button"), function(b){ b.addEventListener("click", function(){ setOri(b.dataset.axis); }); });
  $("cut-place").addEventListener("click", function(){ S.armed = !S.armed; S.hint = ""; ui(); });
  $("cut-side-a").addEventListener("click", function(){ S.rs = 1; push(); });
  $("cut-side-b").addEventListener("click", function(){ S.rs = -1; push(); });
  $("cut-flip").addEventListener("click", function(){ S.rs = -S.rs; push(); });
  slider.addEventListener("input", function(){ S.a = clamp(S.a0 + parseFloat(slider.value)); push(); });
  slider.addEventListener("wheel", function(e){ e.preventDefault(); var d = e.deltaY || e.deltaX; if (d) move((d < 0 ? 1 : -1) * (e.shiftKey ? 10 : 1)); }, {passive:false});
  Array.prototype.forEach.call(panel.querySelectorAll("#cut-steps button"), function(b){ b.addEventListener("click", function(){ move(parseFloat(b.dataset.step)); }); });
  $("cut-reset").addEventListener("click", function(){ S.placed = false; S.armed = false; S.hint = ""; orient("x", null); push(); });
  $("cut-exit").addEventListener("click", function(){ exit(false); });
  $("cut-min").addEventListener("click", function(){ var m = !panel.classList.contains("cp-min"); panel.classList.toggle("cp-min", m); this.setAttribute("aria-expanded", String(!m)); });
  window.addEventListener("keydown", function(e){
    if (!S.on || e.altKey || e.ctrlKey || e.metaKey) return;
    var t = e.target, tag = t && t.tagName;
    if ((tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") && t.id !== "cut-pos") return;
    var k = e.key, d = 0;
    if (k === "ArrowRight" || k === "ArrowUp") d = 1; else if (k === "ArrowLeft" || k === "ArrowDown") d = -1;
    else if (k === "PageUp") d = 10; else if (k === "PageDown") d = -10; else return;
    if (e.shiftKey && Math.abs(d) === 1) d *= 10;
    e.preventDefault(); move(d);
  });
  window.addEventListener("resize", function(){ ui(); overlay(); });
  return {
    /* the engine's pointer-up calls this first: while "Place on model" is armed the click puts the plane through the hit point */
    consumeClick: function(e){
      if (!S.on || !S.armed) return false;
      var p = E.pickPoint(e);
      if (p){ S.placed = true; S.armed = false; S.hint = "Plane placed through the clicked point."; orient(S.ori, p); push(); }
      else { S.hint = "Nothing under the pointer: click on the model."; ui(); }
      return true;
    },
    overlay: overlay,
    /* add-on hook: a plane facing `spec.normal` (into the kept half) through `spec.point`; null leaves cut mode */
    setFromSpec: function(spec){
      if (!spec){ exit(false); return; }
      S.ori = "view"; S.n0 = unit(spec.normal); S.rs = -1; S.anchor = spec.point.slice(); S.placed = true; S.armed = false; S.hint = "";
      S.a0 = dot(S.n0, S.anchor); S.a = S.a0; range(); S.on = true; push();
    },
    exit: exit, enter: enter, move: move, setOrientation: setOri,
    state: function(){ var p = planeKept(); return {on:S.on, ori:S.ori, rs:S.rs, offset:S.a - S.a0, a:S.a, n0:S.n0.slice(), anchor:S.anchor.slice(), placed:S.placed, armed:S.armed, kn:p.kn, c:p.c}; }
  };
}
