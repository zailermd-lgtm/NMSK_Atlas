/* Q321: the quick card. Owner: "when clicking an organ or a region, the FIRST thing that must open is the name of what was
   clicked, with hide, fade, show only, or just select ... rows and boxes that open must have a length matching the number
   of buttons and the text in them ... place them around the model and not on top of it."
   The module owns the DOM, the sizing and the placement; the engine reaches it through one adaptor E:
     info(id) -> {name, sub}   state(id) -> {hidden, faded}   toggleHide(id)   toggleFade(id)   zoom(id)   more(id)
     screenBox() -> {l,t,r,b} client box of everything drawn (null if unknown)   canvasRect()   obstacles() -> [elements]   canvas
   Marking (Select, Show only) goes through the selection controller's public API (window.NMSKSelectCtl), so the pressed state,
   the marks and the page-wide undo are the ones the Selection group already has. The engine calls open(id, clientX, clientY)
   after a click that no tool consumed, and sync(id) from its own select(). */
var NMSKQuickCard = (function(){
  "use strict";
  var GAP = 14, MARG = 8, live = null;
  /* registered when this script loads, so it runs before the page's own Escape handlers (show-all, deselect): the first Escape
     only closes the card, a second one does what it always did */
  window.addEventListener("keydown", function(e){
    if (e.key === "Escape" && live && live.current() && !e.altKey && !e.ctrlKey && !e.metaKey){ live.close(); e.stopImmediatePropagation(); e.preventDefault(); }
  }, true);
  function start(E){
    var card = null, lead = null, cur = null, px = 0, py = 0, rowEl = null, btns = {};
    function el(tag, cls, txt){ var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
    function ctl(){ return window.NMSKSelectCtl || null; }
    function hist(){ try { var H = window.NMSKHistory; if (H && H.active && H.active()) H.commit(); } catch (err){} }
    function build(){
      card = el("div", "qc"); card.hidden = true; card.setAttribute("role", "dialog"); card.setAttribute("aria-label", "Quick actions");
      var head = el("div", "qc-head"), t = el("div", "qc-t"), x = el("button", "qc-x", "×");
      x.type = "button"; x.setAttribute("aria-label", "Close"); x.addEventListener("click", function(){ close(); });
      t.appendChild(el("span", "qc-name")); t.appendChild(el("span", "qc-sub")); head.appendChild(t); head.appendChild(x);
      rowEl = el("div", "qc-row");
      function b(key, label, f, cls){ var e = el("button", "qc-b" + (cls ? " " + cls : ""), label); e.type = "button"; e.setAttribute("data-qc", key);
        e.addEventListener("click", function(ev){ ev.stopPropagation(); if (cur) f(cur); }); btns[key] = e; rowEl.appendChild(e); return e; }
      b("hide", "Hide", function(id){ E.toggleHide(id); hist(); refresh(); });
      b("fade", "Fade", function(id){ E.toggleFade(id); hist(); refresh(); });
      b("only", "Show only", function(id){
        var c = ctl(); if (!c) return;
        if (isOnly(id)) c.setMode("all"); else { c.markIds([id], true, true, true); c.setMode("only"); }
        hist(); refresh();
      });
      b("sel", "Select", function(id){ var c = ctl(); if (!c) return; c.toggle(id, true); hist(); refresh(); });
      b("zoom", "Zoom to", function(id){ var i = id; close(); E.zoom(i); }, "qc-zoom");
      b("more", "More…", function(id){ var i = id; close(true); E.more(i); }, "qc-more");
      card.appendChild(head); card.appendChild(rowEl);
      lead = document.createElementNS("http://www.w3.org/2000/svg", "svg"); lead.setAttribute("class", "qc-lead"); lead.hidden = true; lead.setAttribute("aria-hidden", "true");
      lead.innerHTML = '<line x1="0" y1="0" x2="0" y2="0"></line><circle r="3.5" cx="0" cy="0"></circle>';
      document.body.appendChild(lead); document.body.appendChild(card);
    }
    function isOnly(id){ var c = ctl(), s = c && c.state(); return !!(s && s.mode === "only" && s.marks.length === 1 && s.marks[0] === id && !s.inverted); }
    function refresh(){
      if (!card || card.hidden || !cur) return;
      var s = E.state(cur) || {}, c = ctl(), st = c && c.state();
      function p(k, v, lab){ btns[k].setAttribute("aria-pressed", String(!!v)); if (lab) btns[k].textContent = lab; }
      p("hide", s.hidden, s.hidden ? "Unhide" : "Hide"); p("fade", s.faded, s.faded ? "Unfade" : "Fade");
      p("only", isOnly(cur)); p("sel", st && st.marks.indexOf(cur) >= 0);
      btns.only.disabled = btns.sel.disabled = !c;
    }
    function rects(){
      var out = [], list = [];
      try { list = (E.obstacles ? E.obstacles() : []).concat([].slice.call(document.querySelectorAll(".qg-bar,.qg-sheet"))); } catch (err){}
      list.forEach(function(e){
        if (!e || e === card || !e.getClientRects || !e.getClientRects().length) return;
        var cs = getComputedStyle(e); if (cs.display === "none" || cs.visibility === "hidden") return;
        var r = e.getBoundingClientRect(); if (r.width > 2 && r.height > 2) out.push({l:r.left, t:r.top, r:r.right, b:r.bottom});
      });
      return out;
    }
    function hit(a, b, pad){ return a.l < b.r + pad && a.r > b.l - pad && a.t < b.b + pad && a.b > b.t - pad; }
    /* The rule: the card sits in the free margin on the side of the model nearest the click, level with it (sliding up or down
       past anything in the way); if that side has no room it tries the other side, then above and below the model; if the
       model fills the view (phone, zoomed in) it goes to the edge of the canvas farthest from the click. It never covers the
       clicked point and never sits on the fixed controls. */
    function place(){
      var cr = E.canvasRect(), vw = window.innerWidth, vh = window.innerHeight;
      var V = {l:Math.max(MARG, cr.left + MARG), t:Math.max(MARG, cr.top + MARG), r:Math.min(vw - MARG, cr.right - MARG), b:Math.min(vh - MARG, cr.bottom - MARG)};
      var w = card.offsetWidth, h = card.offsetHeight, B = E.screenBox ? E.screenBox() : null, O = rects(), P = {l:px, t:py, r:px, b:py};
      function fits(x, y){ var r = {l:x, t:y, r:x + w, b:y + h}; if (r.l < V.l || r.t < V.t || r.r > V.r || r.b > V.b) return false; if (hit(r, P, 10)) return false; if (B && hit(r, B, 2)) return false; for (var i = 0; i < O.length; i++) if (hit(r, O[i], 4)) return false; return true; }
      function slide(x, y0){ var ys = [y0], k; for (k = 1; k < 40; k++){ ys.push(y0 - k * 24, y0 + k * 24); } for (var i = 0; i < ys.length; i++){ var y = Math.max(V.t, Math.min(V.b - h, ys[i])); if (fits(x, y)) return {x:x, y:y}; } return null; }
      function slideX(y, x0){ var xs = [x0], k; for (k = 1; k < 40; k++){ xs.push(x0 - k * 24, x0 + k * 24); } for (var i = 0; i < xs.length; i++){ var x = Math.max(V.l, Math.min(V.r - w, xs[i])); if (fits(x, y)) return {x:x, y:y}; } return null; }
      var pos = null, y0 = py - h / 2;
      if (B){
        var left = {x:B.l - GAP - w}, right = {x:B.r + GAP}, mid = (B.l + B.r) / 2, order = px < mid ? [left, right] : [right, left];
        for (var i = 0; i < order.length && !pos; i++) pos = slide(order[i].x, y0);
        if (!pos){ var above = B.t - GAP - h, below = B.b + GAP, x0 = px - w / 2, ord2 = py < (B.t + B.b) / 2 ? [above, below] : [below, above];
          for (var j = 0; j < ord2.length && !pos; j++) pos = slideX(ord2[j], x0); }
      }
      if (!pos){            // no free margin: the canvas edge farthest from the click
        var cand = [{x:V.l, y:V.t}, {x:V.r - w, y:V.t}, {x:V.l, y:V.b - h}, {x:V.r - w, y:V.b - h}, {x:(V.l + V.r - w) / 2, y:V.t}, {x:(V.l + V.r - w) / 2, y:V.b - h}];
        /* phone: the top bar and the bottom title/foot fill the canvas edges, so also try just below everything that hangs from
           the top and just above everything that stands on the bottom */
        var topB = V.t, botT = V.b, mY = (V.t + V.b) / 2;
        O.forEach(function(o){ if (o.b < mY) topB = Math.max(topB, o.b + 4); else if (o.t > mY) botT = Math.min(botT, o.t - 4); });
        [V.l, V.r - w, (V.l + V.r - w) / 2].forEach(function(x){ cand.push({x:x, y:topB}); cand.push({x:x, y:botT - h}); });
        cand.sort(function(a, b){ return Math.hypot(b.x + w / 2 - px, b.y + h / 2 - py) - Math.hypot(a.x + w / 2 - px, a.y + h / 2 - py); });
        for (var k2 = 0; k2 < cand.length && !pos; k2++){ var r = {l:cand[k2].x, t:cand[k2].y, r:cand[k2].x + w, b:cand[k2].y + h}; if (!hit(r, P, 10)){ var clear = true; for (var q = 0; q < O.length; q++) if (hit(r, O[q], 4)) clear = false; if (clear) pos = cand[k2]; } }
        if (!pos){ for (var k3 = 0; k3 < cand.length && !pos; k3++){ var r3 = {l:cand[k3].x, t:cand[k3].y, r:cand[k3].x + w, b:cand[k3].y + h}; if (!hit(r3, P, 10)) pos = cand[k3]; } }
        if (!pos) pos = cand[0];
      }
      card.style.left = Math.round(pos.x) + "px"; card.style.top = Math.round(pos.y) + "px";
      /* the leader: from the card's nearest edge point to the clicked point */
      var ax = Math.max(pos.x, Math.min(px, pos.x + w)), ay = Math.max(pos.y, Math.min(py, pos.y + h));
      var ln = lead.querySelector("line"), dt = lead.querySelector("circle");
      ln.setAttribute("x1", ax); ln.setAttribute("y1", ay); ln.setAttribute("x2", px); ln.setAttribute("y2", py); dt.setAttribute("cx", px); dt.setAttribute("cy", py);
      lead.hidden = false;
      return {x:pos.x, y:pos.y, w:w, h:h};
    }
    function open(id, cx, cy){
      if (!card) build();
      document.body.classList.add("qc-on"); document.body.classList.remove("qc-more");
      if (!id){ close(); return; }
      var inf = E.info(id); if (!inf){ close(); return; }
      cur = id; px = cx; py = cy;
      card.querySelector(".qc-name").textContent = inf.name; card.querySelector(".qc-sub").textContent = inf.sub || "";
      card.hidden = false; card.style.left = "0px"; card.style.top = "0px"; refresh(); place();
    }
    function close(keepInfo){
      cur = null; if (card) card.hidden = true; if (lead) lead.hidden = true;
      if (!keepInfo) document.body.classList.remove("qc-more"); else document.body.classList.add("qc-more");
    }
    function sync(id){ if (card && !card.hidden && id !== cur) close(); if (!id) document.body.classList.remove("qc-more"); }
    if (E.canvas){
      E.canvas.addEventListener("pointerdown", function(){ if (card && !card.hidden) close(); }, true);   // a drag or pinch moves the model: the anchor would be stale
      E.canvas.addEventListener("wheel", function(){ if (card && !card.hidden) close(); }, {passive:true});
    }
    window.addEventListener("resize", function(){ if (card && !card.hidden) close(); });
    try { if (window.NMSKHistory && NMSKHistory.onChange) NMSKHistory.onChange(function(){ refresh(); }); } catch (err){}
    var api = {open:open, close:close, sync:sync, refresh:refresh, box:function(){ return E.screenBox ? E.screenBox() : null; }, current:function(){ return card && !card.hidden ? cur : null; },
               rect:function(){ if (!card || card.hidden) return null; var r = card.getBoundingClientRect(); return {l:r.left, t:r.top, r:r.right, b:r.bottom, w:r.width, h:r.height}; }};
    live = api;
    return api;
  }
  return {start:start};
})();
