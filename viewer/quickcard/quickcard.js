/* Q321: the quick card. Owner: "when clicking an organ or a region, the FIRST thing that must open is the name of what was
   clicked, with hide, fade, show only, or just select ... rows and boxes that open must have a length matching the number
   of buttons and the text in them ... place them around the model and not on top of it."
   Q335, owner (translated): "its position is not always logical and it cannot be moved. If the structure is marked in colour
   there is no need to draw a line. The window with the organ's name can sit permanently in the top-left corner. ... The
   assignment to functional groups / adjacent / related can open next to the organ's name or at the very bottom." And on
   the live card: "a line that crosses the whole body ... press More, then this window disappears and another one opens".
   So, by default: docked in the top-left of the view (below the fixed chrome, the same place on every click), moved by the
   same grip and three-dots menu as every other box (viewer/q305/move.js), no line when the picked structure is drawn in the
   selection tint, and More opens the details IN this window (Less folds them back). Settings live in its ⋮ menu:
     position  Top-left (default) | Beside the clicked point | Where I dragged it
     line      Auto (default: none while the structure is coloured) | Always (a short marker, never across the model) | Never
     groups    Under the name (default) | At the bottom of the screen
     buttons   Fade / Show only / Zoom to / More… on or off;  Compact / Normal size
   stored in localStorage (try/catch; the page works the same without it). The dragged offset is NMSKMove's own store.
   The engine reaches the module through one adaptor E:
     info(id) -> {name, sub}   state(id) -> {hidden, faded}   toggleHide(id)   toggleFade(id)   zoom(id)   more(id)
     marked(id) -> is it drawn in the selection tint now   details() -> the engine's full card element
     screenBox() -> {l,t,r,b} client box of everything drawn (null if unknown)   canvasRect()   obstacles() -> [elements]   canvas
   Marking (Select, Show only) goes through the selection controller's public API (window.NMSKSelectCtl), so the pressed state,
   the marks and the page-wide undo are the ones the Selection group already has. The engine calls open(id, clientX, clientY)
   after a click that no tool consumed, and sync(id) from its own select(). */
var NMSKQuickCard = (function(){
  "use strict";
  var GAP = 14, MARG = 8, STUB = 36, DOCKW = 560, live = null, KEY = "nmsk.q321.prefs";
  var POS = ["tl", "point", "drag"], LEAD = ["auto", "always", "never"], CHIPS = ["card", "bottom"], SHOW = ["fade", "only", "zoom", "more"];
  /* Q335, owner: the groups / adjacent / related row "becomes ONE button 'Related structures' on the name card that opens a
     small menu". The menu lists FAMILIES from this registry, in `order`. A family either runs at once (run(id), with a
     count(id)) or opens a sub-menu (items(id) -> [{label, n, run}]). Functional group / Adjacent / Related are built in;
     the room after them (order 40, 50) is kept for "Myofascial lines" and "Innervation", which register themselves later:
       NMSKQuickCard.family({key, label, order, count, run} | {key, label, order, items}) */
  var FAM = [];
  function family(f){
    if (!f || !f.key || !f.label) return false;
    FAM = FAM.filter(function(x){ return x.key !== f.key; }); FAM.push(f);
    FAM.sort(function(a, b){ return (a.order || 99) - (b.order || 99); });
    return true;
  }
  function q8(){ return window.NMSKQ298 || null; }
  function q8n(id, k){ var Q = q8(), c = null; try { c = Q && Q.counts ? Q.counts(id) : null; } catch (err){ c = null; } return c ? (c[k] || 0) : 0; }
  function q8run(k){ var Q = q8(); if (Q && Q.run) Q.run(k); }
  family({key:"grp", label:"Functional group", order:10, count:function(id){ return q8n(id, "grp"); }, run:function(){ q8run("grp"); }});
  family({key:"adj", label:"Adjacent", order:20, count:function(id){ return q8n(id, "adj"); }, run:function(){ q8run("adj"); }});
  family({key:"rel", label:"Related", order:30, count:function(id){ return q8n(id, "rel"); }, run:function(){ q8run("rel"); }});
  function prefs(){
    var p = {pos:"tl", lead:"auto", chips:"card", compact:false, show:{fade:true, only:true, zoom:true, more:true}};
    try {
      var j = JSON.parse(localStorage.getItem(KEY) || "null");
      if (j && typeof j === "object"){
        if (POS.indexOf(j.pos) >= 0) p.pos = j.pos;
        if (LEAD.indexOf(j.lead) >= 0) p.lead = j.lead;
        if (CHIPS.indexOf(j.chips) >= 0) p.chips = j.chips;
        p.compact = !!j.compact;
        if (j.show && typeof j.show === "object") SHOW.forEach(function(k){ if (k in j.show) p.show[k] = !!j.show[k]; });
      }
    } catch (err){}
    return p;
  }
  /* registered when this script loads, so it runs before the page's own Escape handlers (show-all, deselect): the first Escape
     only closes the card, a second one does what it always did */
  window.addEventListener("keydown", function(e){
    if (e.key !== "Escape" || !live || e.altKey || e.ctrlKey || e.metaKey) return;
    if (live.relClose && live.relClose(true)){ e.stopImmediatePropagation(); e.preventDefault(); return; }      /* an open menu takes the first Escape */
    if (live.current()){ live.close(); e.stopImmediatePropagation(); e.preventDefault(); }
  }, true);
  function start(E){
    var card = null, lead = null, cur = null, px = null, py = null, rowEl = null, chipsEl = null, detEl = null, btns = {};
    var P = prefs(), open1 = false, stale = false, home = null, QB = null;
    function save(){ try { localStorage.setItem(KEY, JSON.stringify(P)); } catch (err){} }
    function el(tag, cls, txt){ var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
    function ctl(){ return window.NMSKSelectCtl || null; }
    function M(){ return window.NMSKMove || null; }
    function hist(){ try { var H = window.NMSKHistory; if (H && H.active && H.active()) H.commit(); } catch (err){} }
    function build(){
      card = el("div", "qc"); card.hidden = true; card.setAttribute("role", "dialog"); card.setAttribute("aria-label", "Structure");
      var head = el("div", "qc-head"), t = el("div", "qc-t"), tools = el("div", "qc-tools"), x = el("button", "qc-x", "×");
      tools.id = "qc-tools";                     /* the grip and the ⋮ button sit here, in the head, never over the name */
      x.type = "button"; x.setAttribute("aria-label", "Close"); x.addEventListener("click", function(){ close(); });
      t.appendChild(el("span", "qc-name")); t.appendChild(el("span", "qc-sub")); head.appendChild(t); head.appendChild(tools); head.appendChild(x);
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
      var rb = b("rel", "Related structures \u25be", function(){ if (relEl) relClose(true); else relOpen(); }, "qc-relb");
      rb.setAttribute("aria-haspopup", "menu"); rb.setAttribute("aria-expanded", "false");
      b("zoom", "Zoom to", function(id){ if (P.pos === "point"){ close(); E.zoom(id); return; } E.zoom(id); stale = true; leader(); }, "qc-zoom");
      b("more", "More…", function(id){ if (open1) less(); else more(id); }, "qc-more");
      chipsEl = el("div", "qc-chips"); chipsEl.id = "qc-chips";
      detEl = el("div", "qc-det"); detEl.id = "qc-det"; detEl.setAttribute("data-nm-hosted", "");
      card.appendChild(head); card.appendChild(rowEl); card.appendChild(chipsEl); card.appendChild(detEl);
      lead = document.createElementNS("http://www.w3.org/2000/svg", "svg"); lead.setAttribute("class", "qc-lead"); lead.hidden = true; lead.setAttribute("aria-hidden", "true");
      lead.innerHTML = '<line x1="0" y1="0" x2="0" y2="0"></line><circle r="3.5" cx="0" cy="0"></circle>';
      document.body.appendChild(lead); document.body.appendChild(card);
      dress();
      register();
    }
    function dress(){
      if (!card) return;
      card.classList.toggle("qc-compact", !!P.compact);
      SHOW.forEach(function(k){ if (btns[k]) btns[k].hidden = !P.show[k]; });
      if (btns.rel) btns.rel.hidden = P.chips === "bottom";        /* at the bottom the strip carries them instead */
    }
    /* ---- the "Related structures" menu ---- */
    var relEl = null;
    function relClose(refocus){
      if (!relEl) return false;
      if (relEl.parentNode) relEl.parentNode.removeChild(relEl);
      relEl = null;
      if (btns.rel){ btns.rel.setAttribute("aria-expanded", "false"); if (refocus){ try { btns.rel.focus({preventScroll:true}); } catch (err){} } }
      return true;
    }
    function relOpen(){
      relClose(false);
      var id = cur; if (!id || !btns.rel) return null;
      var m = el("div", "qc-relmenu"); m.id = "qc-relmenu"; m.setAttribute("role", "menu"); m.setAttribute("aria-label", "Related structures");
      FAM.forEach(function(f){
        var subs = null, n = 0;
        try { subs = f.items ? (f.items(id) || []) : null; n = subs ? subs.length : (f.count ? +f.count(id) || 0 : 0); } catch (err){ subs = null; n = 0; }
        var x = el("button", "qc-rmi", f.label + (n ? " \u00b7 " + n : "") + (subs ? " \u25b8" : ""));
        x.type = "button"; x.setAttribute("role", "menuitem"); x.setAttribute("data-fam", f.key);
        if (!n){ x.setAttribute("aria-disabled", "true"); x.classList.add("qc-off"); x.title = "None for this structure in this project's data"; }
        var sub = null;
        x.addEventListener("click", function(e){
          e.stopPropagation(); if (!n) return;
          if (subs){
            if (sub){ sub.parentNode.removeChild(sub); sub = null; x.setAttribute("aria-expanded", "false"); return; }
            sub = el("div", "qc-rsub"); sub.setAttribute("role", "group");
            subs.forEach(function(it){
              var y = el("button", "qc-rmi qc-rsi", it.label + (it.n ? " \u00b7 " + it.n : "")); y.type = "button"; y.setAttribute("role", "menuitem");
              y.addEventListener("click", function(e2){ e2.stopPropagation(); relClose(false); try { it.run(id); } catch (err){} after(); });
              sub.appendChild(y);
            });
            x.parentNode.insertBefore(sub, x.nextSibling); x.setAttribute("aria-expanded", "true");
            return;
          }
          relClose(false); try { f.run(id); } catch (err){} after();
        });
        if (subs) x.setAttribute("aria-expanded", "false");
        m.appendChild(x);
      });
      m.addEventListener("keydown", function(e){
        var xs = [].slice.call(m.querySelectorAll(".qc-rmi")), i = xs.indexOf(document.activeElement);
        if (e.key === "ArrowDown" || e.key === "ArrowUp"){ var k = xs.length; if (!k) return; i = (i + (e.key === "ArrowDown" ? 1 : k - 1) + k) % k; xs[i].focus(); e.preventDefault(); }
        else if (e.key === "Tab") relClose(false);
      });
      document.body.appendChild(m); relEl = m; btns.rel.setAttribute("aria-expanded", "true");
      var r = btns.rel.getBoundingClientRect(), w = m.offsetWidth, h = m.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
      var x0 = Math.max(8, Math.min(vw - 8 - w, r.left)), y0 = r.bottom + 4;
      if (y0 + h > vh - 8) y0 = Math.max(8, r.top - 4 - h);
      m.style.left = Math.round(x0) + "px"; m.style.top = Math.round(y0) + "px";
      var first = m.querySelector(".qc-rmi:not(.qc-off)") || m.querySelector(".qc-rmi"); if (first){ try { first.focus({preventScroll:true}); } catch (err){} }
      return m;
    }
    function after(){ setTimeout(function(){ rehome(); fit(); leader(); }, 60); }
    document.addEventListener("pointerdown", function(e){
      if (!relEl) return;
      if (relEl.contains(e.target) || (btns.rel && btns.rel.contains(e.target))) return;
      relClose(false);
    }, true);
    /* ---- the window: one grip and one ⋮ like every other box (NMSKMove), the offset applied only in "Where I dragged it" ---- */
    function register(){
      var Mv = M(); if (!Mv || QB) return;
      QB = {key:"qcard", el:function(){ return card; }, into:"qc-tools", label:"the name card",
            use:function(){ return P.pos === "drag"; },
            /* a drag that starts from the corner or from beside the point keeps the card where it is and makes that the
               dragged place, so nothing jumps under the finger */
            grab:function(){ if (P.pos === "drag" || !card || card.hidden) return; var r0 = card.getBoundingClientRect();
              P.pos = "drag"; save(); QB.dx = 0; QB.dy = 0; place(); var r1 = card.getBoundingClientRect(); QB.dx = r0.left - r1.left; QB.dy = r0.top - r1.top; Mv.apply("qcard"); },
            moved:function(){ if (P.pos !== "drag"){ P.pos = "drag"; save(); } fit(); leader(); }};
      Mv.add(QB);
      Mv.menu("qcard", {
        items:function(){
          function radio(k, v, label){ return {label:label, key:k + "-" + v, radio:true, checked:P[k] === v, run:function(){ set(k, v); }}; }
          var out = [{head:"Name card position"}, radio("pos", "tl", "Top-left corner"), radio("pos", "point", "Beside the clicked point"), radio("pos", "drag", "Where I dragged it"),
                     {head:"Line to the clicked point"}, radio("lead", "auto", "Auto: none while it is coloured"), radio("lead", "always", "Always (short marker)"), radio("lead", "never", "Never"),
                     {head:"Groups / adjacent / related"}, radio("chips", "card", "Under the name"), radio("chips", "bottom", "At the bottom of the screen"),
                     {head:"Buttons on the card"}];
          [["fade", "Fade"], ["only", "Show only"], ["zoom", "Zoom to"], ["more", "More… (details)"]].forEach(function(q){
            out.push({label:q[1], key:"show-" + q[0], checked:!!P.show[q[0]], run:function(){ P.show[q[0]] = !P.show[q[0]]; save(); dress(); place(); }});
          });
          return out;
        },
        dock:function(at){
          if (at === "tl"){ set("pos", "tl"); return true; }
          if (P.pos !== "drag"){ P.pos = "drag"; save(); QB.dx = 0; QB.dy = 0; place(); }   /* the corners are offsets from the docked place */
          return false;
        },
        reset:function(){ set("pos", "tl"); },
        compact:function(v){ if (v === undefined) return !!P.compact; P.compact = !!v; save(); dress(); place(); return P.compact; },
        close:function(){ close(); }
      });
      /* the strip at the bottom gets the same choice in its own ⋮ */
      Mv.menu("expand", {items:function(){
        return [{head:"Groups / adjacent / related"},
                {label:"Under the name", key:"chips-card", radio:true, checked:P.chips === "card", run:function(){ set("chips", "card"); }},
                {label:"At the bottom of the screen", key:"chips-bottom", radio:true, checked:P.chips === "bottom", run:function(){ set("chips", "bottom"); }}];
      }});
    }
    function set(k, v){
      P[k] = v; save();
      if (k === "pos" && v === "tl" && QB){ var Mv = M(); if (Mv) Mv.apply("qcard"); }
      if (k === "chips") rehome();
      dress(); place();
    }
    function isOnly(id){ var c = ctl(), s = c && c.state(); return !!(s && s.mode === "only" && s.marks.length === 1 && s.marks[0] === id && !s.inverted); }
    function refresh(){
      if (!card || card.hidden || !cur) return;
      var s = E.state(cur) || {}, c = ctl(), st = c && c.state();
      function p(k, v, lab){ btns[k].setAttribute("aria-pressed", String(!!v)); if (lab) btns[k].textContent = lab; }
      p("hide", s.hidden, s.hidden ? "Unhide" : "Hide"); p("fade", s.faded, s.faded ? "Unfade" : "Fade");
      p("only", isOnly(cur)); p("sel", st && st.marks.indexOf(cur) >= 0);
      btns.only.disabled = btns.sel.disabled = !c;
      leader();
    }
    function rects(){
      var out = [], list = [];
      try { list = (E.obstacles ? E.obstacles() : []).concat([].slice.call(document.querySelectorAll(".qg-bar,.qg-sheet"))); } catch (err){}
      list.forEach(function(e){
        if (!e || e === card || (card && card.contains(e)) || !e.getClientRects || !e.getClientRects().length) return;
        var cs = getComputedStyle(e); if (cs.display === "none" || cs.visibility === "hidden") return;
        var r = e.getBoundingClientRect(); if (r.width > 2 && r.height > 2) out.push({l:r.left, t:r.top, r:r.right, b:r.bottom});
      });
      return out;
    }
    function hit(a, b, pad){ return a.l < b.r + pad && a.r > b.l - pad && a.t < b.b + pad && a.b > b.t - pad; }
    function view(){
      var cr = E.canvasRect(), vw = window.innerWidth, vh = window.innerHeight;
      return {l:Math.max(MARG, cr.left + MARG), t:Math.max(MARG, cr.top + MARG), r:Math.min(vw - MARG, cr.right - MARG), b:Math.min(vh - MARG, cr.bottom - MARG)};
    }
    /* height of the name and its buttons only: the details and the chips grow downward from a fixed corner */
    function headH(){ var r = card.getBoundingClientRect(), q = rowEl.getBoundingClientRect(); return Math.max(40, Math.round(q.bottom - r.top + 7)); }
    /* THE DOCK: the top-left of the view, below or beside every fixed control that lives there. Measured with a nominal
       width (the card's cap), so a long or a short name lands on the same corner on every click. */
    function dockTL(){
      var V = view(), w = Math.min(DOCKW, V.r - V.l), h = headH(), O = rects(), x, y;
      for (y = V.t; y <= V.b - h; y += 6){
        for (x = V.l; x <= Math.min(V.l + 240, V.r - w); x += 12){
          var r = {l:x, t:y, r:x + w, b:y + h}, ok = true;
          for (var i = 0; i < O.length && ok; i++) if (hit(r, O[i], 4)) ok = false;
          if (ok) return {x:x, y:y};
        }
      }
      return {x:V.l, y:V.t};
    }
    /* "Beside the clicked point" -- the Q321 rule: the free margin on the side of the model nearest the click, level with it;
       if that side has no room the other side, then above and below the model; if the model fills the view (phone, zoomed
       in), the edge of the canvas farthest from the click. It never covers the clicked point nor the fixed controls. */
    function besidePoint(){
      var V = view(), w = card.offsetWidth, h = open1 ? headH() : card.offsetHeight, B = E.screenBox ? E.screenBox() : null, O = rects(), P0 = {l:px, t:py, r:px, b:py};
      function fits(x, y){ var r = {l:x, t:y, r:x + w, b:y + h}; if (r.l < V.l || r.t < V.t || r.r > V.r || r.b > V.b) return false; if (hit(r, P0, 10)) return false; if (B && hit(r, B, 2)) return false; for (var i = 0; i < O.length; i++) if (hit(r, O[i], 4)) return false; return true; }
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
        var topB = V.t, botT = V.b, mY = (V.t + V.b) / 2;
        O.forEach(function(o){ if (o.b < mY) topB = Math.max(topB, o.b + 4); else if (o.t > mY) botT = Math.min(botT, o.t - 4); });
        [V.l, V.r - w, (V.l + V.r - w) / 2].forEach(function(x){ cand.push({x:x, y:topB}); cand.push({x:x, y:botT - h}); });
        cand.sort(function(a, b){ return Math.hypot(b.x + w / 2 - px, b.y + h / 2 - py) - Math.hypot(a.x + w / 2 - px, a.y + h / 2 - py); });
        for (var k2 = 0; k2 < cand.length && !pos; k2++){ var r = {l:cand[k2].x, t:cand[k2].y, r:cand[k2].x + w, b:cand[k2].y + h}; if (!hit(r, P0, 10)){ var clear = true; for (var q = 0; q < O.length; q++) if (hit(r, O[q], 4)) clear = false; if (clear) pos = cand[k2]; } }
        if (!pos){ for (var k3 = 0; k3 < cand.length && !pos; k3++){ var r3 = {l:cand[k3].x, t:cand[k3].y, r:cand[k3].x + w, b:cand[k3].y + h}; if (!hit(r3, P0, 10)) pos = cand[k3]; } }
        if (!pos) pos = cand[0];
      }
      return pos;
    }
    function place(){
      if (!card || card.hidden) return null;
      var pos = (P.pos === "point" && px != null) ? besidePoint() : dockTL();
      card.style.left = Math.round(pos.x) + "px"; card.style.top = Math.round(pos.y) + "px";
      var Mv = M(); if (Mv && QB){ Mv.apply("qcard"); if (Mv.refresh) Mv.refresh(); }
      fit();
      leader();
      var r = card.getBoundingClientRect();
      return {x:r.left, y:r.top, w:r.width, h:r.height};
    }
    /* the details scroll inside the card, which never runs past the bottom of the view */
    function fit(){
      if (!open1 || !detEl) return;
      var t = detEl.getBoundingClientRect().top;
      /* at most half the view, so an open window still has room to be moved down */
      detEl.style.maxHeight = Math.max(120, Math.round(Math.min(window.innerHeight - t - 12, window.innerHeight * 0.5))) + "px";
    }
    /* THE LINE. The selection tint already says which structure the card is about, so in "auto" there is no line while the
       structure is drawn in it; when a line is drawn it is a SHORT marker at the clicked point (at most STUB px, pointing
       towards the card), never a stroke across the model. A drag of the model makes the point stale: the marker goes. */
    function leader(){
      if (!lead) return;
      var want = !!cur && px != null && !stale && P.lead !== "never" && (P.lead === "always" || !(E.marked && E.marked(cur)));
      if (!want || card.hidden){ lead.hidden = true; return; }
      var r = card.getBoundingClientRect();
      var ax = Math.max(r.left, Math.min(px, r.right)), ay = Math.max(r.top, Math.min(py, r.bottom));
      var dx = ax - px, dy = ay - py, L = Math.hypot(dx, dy), k = L > STUB ? STUB / L : 1;
      var ln = lead.querySelector("line"), dt = lead.querySelector("circle");
      ln.setAttribute("x1", px + dx * k); ln.setAttribute("y1", py + dy * k); ln.setAttribute("x2", px); ln.setAttribute("y2", py);
      dt.setAttribute("cx", px); dt.setAttribute("cy", py);
      lead.hidden = false;
    }
    /* ---- More / Less: the details open IN this window. The engine's own full card is taken into the card's details slot
       (and given back on Less / close), so position, grip, ⋮ and drag are the one window's. ---- */
    function details(){ return (E.details ? E.details() : null) || document.getElementById("info"); }
    function more(id){
      var inf = details();
      E.more(id);
      if (inf && inf.parentNode !== detEl){ home = {p:inf.parentNode, n:inf.nextSibling}; detEl.appendChild(inf); }
      open1 = true; card.classList.add("qc-open"); document.body.classList.add("qc-more");
      btns.more.textContent = "Less"; btns.more.setAttribute("aria-expanded", "true");
      fit(); leader();
    }
    function less(){
      var inf = details();
      if (inf && home && inf.parentNode === detEl){ try { home.p.insertBefore(inf, home.n && home.n.parentNode === home.p ? home.n : null); } catch (err){ home.p.appendChild(inf); } }
      home = null; open1 = false;
      if (card){ card.classList.remove("qc-open"); detEl.style.maxHeight = ""; }
      document.body.classList.remove("qc-more");
      if (btns.more){ btns.more.textContent = "More…"; btns.more.setAttribute("aria-expanded", "false"); }
    }
    /* ---- the groups / adjacent / related row: under the name (in this card) or at the bottom of the screen ---- */
    window.NMSKQ8Host = function(){
      if (P.chips === "bottom") return "bottom";
      return card && !card.hidden && cur ? chipsEl : null;
    };
    function rehome(){ try { if (window.NMSKQ298 && NMSKQ298.refresh) NMSKQ298.refresh(); } catch (err){} }
    function show(id){
      var inf = E.info(id); if (!inf){ close(); return false; }
      cur = id;
      card.querySelector(".qc-name").textContent = inf.name; card.querySelector(".qc-sub").textContent = inf.sub || "";
      if (card.hidden){ card.hidden = false; card.style.left = "0px"; card.style.top = "0px"; }
      refresh();
      return true;
    }
    function open(id, cx, cy){
      if (!card) build();
      register();
      document.body.classList.add("qc-on");
      if (!id){ close(); return; }
      px = cx; py = cy; stale = false; relClose(false);
      if (!show(id)) return;
      rehome(); place();          /* the row comes in first, so the card is placed at its real height */
    }
    function close(){
      relClose(false); less();
      cur = null; if (card) card.hidden = true; if (lead) lead.hidden = true;
      rehome();
    }
    /* the engine's select(): the docked card stays and follows the selection; "beside the point" closes as before */
    function sync(id){
      if (!card || card.hidden){ if (!id) less(); return; }
      if (!id){ close(); return; }
      if (id === cur) return;
      if (P.pos === "point"){ close(); return; }
      relClose(false); px = null; show(id); rehome(); place();
    }
    if (E.canvas){
      /* a drag or pinch moves the model: beside the point the anchor would be stale, so the card goes; docked it stays,
         and only the marker at the old point goes */
      E.canvas.addEventListener("pointerdown", function(){ if (!card || card.hidden) return; if (P.pos === "point") close(); else { stale = true; leader(); } }, true);
      E.canvas.addEventListener("wheel", function(){ if (!card || card.hidden) return; if (P.pos === "point") close(); else { stale = true; leader(); } }, {passive:true});
    }
    window.addEventListener("resize", function(){ if (!card || card.hidden) return; if (P.pos === "point") close(); else { stale = true; place(); } });
    try { if (window.NMSKHistory && NMSKHistory.onChange) NMSKHistory.onChange(function(){ refresh(); }); } catch (err){}
    var api = {open:open, close:close, sync:sync, refresh:refresh, place:place, box:function(){ return E.screenBox ? E.screenBox() : null; },
               current:function(){ return card && !card.hidden ? cur : null; },
               expanded:function(){ return open1; }, more:function(){ if (cur && !open1) more(cur); return open1; }, less:less,
               prefs:function(){ return JSON.parse(JSON.stringify(P)); },
               set:function(k, v){ if (k === "show" || k === "compact"){ if (k === "compact"){ P.compact = !!v; } else { P.show = v; } save(); dress(); place(); } else set(k, v); return api.prefs(); },
               lead:function(){ if (!lead || lead.hidden) return null; var n = lead.querySelector("line"); var a = ["x1", "y1", "x2", "y2"].map(function(k){ return +n.getAttribute(k); });
                 return {x1:a[0], y1:a[1], x2:a[2], y2:a[3], len:Math.hypot(a[2] - a[0], a[3] - a[1])}; },
               relOpen:function(){ return relOpen(); }, relClose:relClose, relMenu:function(){ return relEl; },
               rect:function(){ if (!card || card.hidden) return null; var r = card.getBoundingClientRect(); return {l:r.left, t:r.top, r:r.right, b:r.bottom, w:r.width, h:r.height}; }};
    live = api;
    return api;
  }
  return {start:start, family:family, families:function(){ return FAM.map(function(f){ return f.key; }); }};
})();
