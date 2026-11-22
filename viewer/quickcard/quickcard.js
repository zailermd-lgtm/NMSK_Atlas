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
  var GAP = 14, MARG = 8, STUB = 36, DOCKW = 560, CAP = 0.6, live = null, KEY = "nmsk.q321.prefs";   /* Q354: CAP = the open card's share of the view */
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
  /* Q343: ADD-ONS draw a small block on the card between its buttons and the related-structures line (the Parts chooser of a
     muscle with named parts). render(id, host, card) runs on every structure the card shows; card.setScope(ids, label) makes
     Hide / Fade / Show only / Select act on those ids (a whole muscle, one part) instead of the clicked mesh alone, until
     the card shows another structure:  NMSKQuickCard.addon({key, order, render}) */
  var ADD = [];
  function addon(a){
    if (!a || !a.key || typeof a.render !== "function") return false;
    ADD = ADD.filter(function(x){ return x.key !== a.key; }); ADD.push(a);
    ADD.sort(function(x, y){ return (x.order || 99) - (y.order || 99); });
    return true;
  }
  /* Q378: a card action is its OWN undo step. The page history commits a click about 320 ms later (debounced), and on a
     busy page the overdue timer runs after the next press. An action pressed before that commit was folded into the click's
     entry, so one Undo took the selection back together with the action: the engine selected nothing (or the structure
     before) and the card closed or changed -- any structure, either page. So: seal what is pending, act, commit. */
  function step(H, f){
    var live = false; try { live = !!(H && H.active && H.active()); } catch (err){}
    if (live){ try { H.commit(); } catch (err1){} }
    var r = f();
    if (live){ try { H.commit(); } catch (err2){} }
    return r;
  }
  /* Q354: a bursa / tendon sheath carries no muscle's record any more; the page data names the muscle it belongs with
     (manifest mesh "rel"), and the card shows it as a link -- "Related: Obturator internus" -- never its attachments */
  var REL = null;
  function relOf(id){
    if (!REL){ REL = {}; try { ((window.__ANATOMY_MANIFEST__ || {}).meshes || []).forEach(function(m){ if (m && m.rel) REL[m.id] = m.rel; }); } catch (err){} }
    return REL[id] || null;
  }
  addon({key:"rel354", order:5, render:function(id, host, card){
    var rid = relOf(id); if (!rid || !card.engine) return;
    var E = card.engine(), inf = E && E.info ? E.info(rid) : null; if (!inf) return;
    var row = document.createElement("div"); row.className = "qc-relto";
    var lab = document.createElement("span"); lab.textContent = "Related: ";
    var b = document.createElement("button"); b.type = "button"; b.className = "qc-rellink"; b.setAttribute("data-rel", rid);
    var sd = / \u00b7 (left|right)$/.exec(inf.sub || "");
    b.textContent = inf.name + (sd && !/\((?:left|right)\)\s*$/.test(inf.name) ? " (" + sd[1] + ")" : "");
    b.title = "Open " + inf.name;
    b.addEventListener("click", function(ev){ ev.stopPropagation(); card.go(rid); });
    row.appendChild(lab); row.appendChild(b); host.appendChild(row);
  }});
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
    if (live.relBack && live.relBack()){ e.stopImmediatePropagation(); e.preventDefault(); return; }             /* Q343: a sub-menu sheet goes back first */
    if (live.relClose && live.relClose(true)){ e.stopImmediatePropagation(); e.preventDefault(); return; }      /* an open menu takes the first Escape */
    if (live.current()){ live.close(); e.stopImmediatePropagation(); e.preventDefault(); }
  }, true);
  function start(E){
    var card = null, lead = null, cur = null, px = null, py = null, rowEl = null, chipsEl = null, detEl = null, btns = {};
    var P = prefs(), open1 = false, stale = false, home = null, QB = null, addEl = null, scope = null;
    function S(){ return scope && scope.ids.length ? scope.ids : (cur ? [cur] : []); }
    function every(ids, f){ for (var i = 0; i < ids.length; i++) if (!f(ids[i])) return false; return ids.length > 0; }
    function setScope(ids, label){
      var v = (ids || []).filter(function(x){ return !!x; });
      scope = v.length && !(v.length === 1 && v[0] === cur) ? {ids:v, label:label || ""} : null;
      refresh(); return S().slice();
    }
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
      t.appendChild(el("span", "qc-name")); t.appendChild(el("span", "qc-sub")); head.appendChild(t);
      /* Q368: the swatch and ADD sit on the name row, beside the name (visually small, each with a >= 32 px touch target) */
      var acts = el("div", "qc-acts");
      swEl = el("button", "qc-sw"); swEl.type = "button"; swEl.setAttribute("data-qc", "swatch"); swEl.setAttribute("aria-haspopup", "dialog"); swEl.setAttribute("aria-expanded", "false");
      swEl.appendChild(el("span", "qc-swc")); swEl.hidden = true;
      swEl.addEventListener("click", function(ev){ ev.stopPropagation(); if (popKind === "pal") relClose(true); else palOpen(); });
      addB = el("button", "qc-addb", "ADD"); addB.type = "button"; addB.setAttribute("data-qc", "add"); addB.setAttribute("aria-haspopup", "menu"); addB.setAttribute("aria-expanded", "false");
      addB.setAttribute("aria-label", "ADD (\u05d4\u05d5\u05e1\u05e3) to the marked set: functional group, antagonist group, adjacent tissues");
      addB.title = "ADD / \u05d4\u05d5\u05e1\u05e3 \u2014 functional group, antagonist group, adjacent tissues";
      addB.addEventListener("click", function(ev){ ev.stopPropagation(); if (popKind === "add") relClose(true); else addOpen(); });
      acts.appendChild(swEl); acts.appendChild(addB); head.appendChild(acts);
      head.appendChild(tools); head.appendChild(x);
      rowEl = el("div", "qc-row");
      function b(key, label, f, cls){ var e = el("button", "qc-b" + (cls ? " " + cls : ""), label); e.type = "button"; e.setAttribute("data-qc", key);
        e.addEventListener("click", function(ev){ ev.stopPropagation(); if (cur) step(window.NMSKHistory, function(){ f(cur); }); }); btns[key] = e;   /* Q378 */ rowEl.appendChild(e); return e; }
      /* Q343: each acts on the card's scope -- the clicked mesh, or the whole muscle / part chosen in the Parts chooser */
      function each(k){ var ids = S(), on = !every(ids, function(i){ return !!(E.state(i) || {})[k === "hide" ? "hidden" : "faded"]; });
        ids.forEach(function(i){ if (!!(E.state(i) || {})[k === "hide" ? "hidden" : "faded"] !== on){ if (k === "hide") E.toggleHide(i); else E.toggleFade(i); } }); }
      b("hide", "Hide", function(){ each("hide"); hist(); refresh(); });
      b("fade", "Fade", function(){ each("fade"); hist(); refresh(); });
      b("only", "Show only", function(){
        var c = ctl(), ids = S(); if (!c) return;
        if (isOnly(ids)) c.setMode("all"); else { c.markIds(ids, true, true, true); c.setMode("only"); }
        hist(); refresh();
      });
      b("sel", "Select", function(id){ var c = ctl(), ids = S(); if (!c) return;
        if (ids.length === 1) c.toggle(ids[0], true);
        else { var st = c.state(); c.markIds(ids, !every(ids, function(i){ return st.marks.indexOf(i) >= 0; }), false, false); }
        hist(); refresh(); });
      var rb = b("rel", "Related structures \u25be", function(){ if (relEl) relClose(true); else relOpen(); }, "qc-relb");
      rb.setAttribute("aria-haspopup", "menu"); rb.setAttribute("aria-expanded", "false");
      b("zoom", "Zoom to", function(id){ if (P.pos === "point"){ close(); E.zoom(id); return; } E.zoom(id); stale = true; leader(); }, "qc-zoom");
      b("more", "More…", function(id){ if (open1) less(); else more(id); }, "qc-more");
      chipsEl = el("div", "qc-chips"); chipsEl.id = "qc-chips";
      detEl = el("div", "qc-det"); detEl.id = "qc-det"; detEl.setAttribute("data-nm-hosted", "");
      try { new MutationObserver(function(){ if (open1) tidyDet(); }).observe(detEl, {childList:true, subtree:true}); } catch (err){}
      addEl = el("div", "qc-add"); addEl.id = "qc-add";
      card.appendChild(head); card.appendChild(rowEl); card.appendChild(addEl); card.appendChild(chipsEl); card.appendChild(detEl);
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
    /* ---- the card's pop-up menus: "Related structures", ADD (Q368) and the colour palette (Q368). One is open at a time; the
       Escape handler, the outside-press close and the keyboard are shared. ---- */
    var relEl = null, popKind = null, popBtn = null;
    function relClose(refocus){
      if (!relEl) return false;
      if (relEl.parentNode) relEl.parentNode.removeChild(relEl);
      var b = popBtn; relEl = null; relBack = null; popKind = null; popBtn = null;
      if (b){ b.setAttribute("aria-expanded", "false"); if (refocus){ try { b.focus({preventScroll:true}); } catch (err){} } }
      return true;
    }
    /* Q343: a family's sub-menu opens as a SHEET stacked in the same menu (a "\u2039 back" row on top), at every size: so the menu
       stays as wide as its own items and a phone gets one readable list at a time. An item is
         {label, n, run} | {label, items:[...]} (a further sheet) | {head:true, label} (a heading) |
         {label, off:true, why} (shown greyed; a tap or Enter shows why) ; optional badge (short text) and here (true: it
       concerns the structure on the card). Escape or \u2190 goes back one sheet, then closes. */
    var relBack = null;
    function relOpen(){
      var id = cur; if (!id || !btns.rel) return null;
      return menu("rel", btns.rel, "qc-relmenu", "Related structures", function(c){ fams(c, id); });
    }
    function fams(c, id){
      var m = c.m;
      FAM.forEach(function(f){
        var subs = null, n = 0, k = 0;
        try { subs = f.items ? (f.items(id) || []) : null; n = subs ? subs.length : (f.count ? +f.count(id) || 0 : 0);
              k = subs ? (f.count ? +f.count(id) || 0 : n) : n; } catch (err){ subs = null; n = 0; k = 0; }
        var x = c.item(f.label + (k ? " \u00b7 " + k : "") + (subs ? " \u25b8" : ""));
        x.setAttribute("data-fam", f.key);
        if (!n){ x.setAttribute("aria-disabled", "true"); x.classList.add("qc-off"); x.title = "None for this structure in this project's data";
                 x.textContent = f.label + " \u00b7 none"; }
        if (subs) x.setAttribute("aria-haspopup", "menu");
        var why = null;
        x.addEventListener("click", function(e){
          e.stopPropagation();
          if (!n){              /* Q354: an empty family says why on a tap (it used to do nothing) */
            if (why){ why.parentNode.removeChild(why); why = null; x.setAttribute("aria-expanded", "false"); return; }
            why = el("p", "qc-rwhy", "None for this structure in this project's data."); why.setAttribute("role", "note");
            x.parentNode.insertBefore(why, x.nextSibling); x.setAttribute("aria-expanded", "true"); c.pos(); return;
          }
          if (subs){ c.push({label:f.label, items:subs, key:f.key}); return; }
          relClose(false); try { f.run(id); } catch (err){} after();
        });
        m.appendChild(x);
      });
    }
    /* the shared menu: kind names it, btn anchors it, root(c) fills its first level (c = {m, item, rows, push, pos, id}) */
    function menu(kind, btn, mid, label, root){
      relClose(false);
      var id = cur; if (!id || !btn) return null;
      var m = el("div", "qc-relmenu" + (kind !== "rel" ? " qc-" + kind + "menu" : "")); m.id = mid; m.setAttribute("role", "menu"); m.setAttribute("aria-label", label);
      var stack = [];
      function item(lab, cls){ var x = el("button", "qc-rmi" + (cls ? " " + cls : ""), lab); x.type = "button"; x.setAttribute("role", "menuitem"); return x; }
      function rows(items){
        items.forEach(function(it){
          if (it.head){ var hd = el("div", "qc-rhead", it.label); hd.setAttribute("role", "presentation"); m.appendChild(hd); return; }
          var y = item(it.label + (it.n ? " \u00b7 " + it.n : "") + (it.items ? " \u25b8" : ""), "qc-rsi" + (it.here ? " qc-here" : ""));
          if (it.key) y.setAttribute("data-key", it.key);
          if (it.badge){ var bd = el("span", "qc-rbadge" + (it.bcls ? " " + it.bcls : ""), it.badge); y.appendChild(document.createTextNode(" ")); y.appendChild(bd); }
          if (it.title) y.title = it.title;
          if (it.off){
            y.setAttribute("aria-disabled", "true"); y.classList.add("qc-off"); if (it.why) y.title = it.why;
            var why = null;
            y.addEventListener("click", function(e){
              e.stopPropagation(); if (!it.why) return;
              if (why){ why.parentNode.removeChild(why); why = null; y.setAttribute("aria-expanded", "false"); return; }
              why = el("p", "qc-rwhy", it.why); why.setAttribute("role", "note"); y.parentNode.insertBefore(why, y.nextSibling); y.setAttribute("aria-expanded", "true"); pos();
            });
          } else if (it.items){
            y.setAttribute("aria-haspopup", "menu");
            y.addEventListener("click", function(e){ e.stopPropagation(); stack.push({label:it.sheet || it.label, items:it.items, key:it.key}); paint(); });
          } else {
            y.addEventListener("click", function(e2){ e2.stopPropagation(); relClose(!!it.refocus); try { it.run(id); } catch (err){} after(); });
          }
          m.appendChild(y);
        });
      }
      function sheet(S){
        var bk = item("\u2039 " + S.label, "qc-rback"); bk.setAttribute("aria-label", "Back from " + S.label);
        bk.addEventListener("click", function(e){ e.stopPropagation(); back(); });
        m.appendChild(bk); m.setAttribute("data-sheet", S.key || "");
        rows(S.items);
      }
      function pos(){
        var r = btn.getBoundingClientRect(), w = m.offsetWidth, h = m.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
        var x0 = Math.max(8, Math.min(vw - 8 - w, r.left)), y0 = r.bottom + 4;
        if (y0 + h > vh - 8) y0 = Math.max(8, Math.min(r.top - 4 - h, vh - 8 - h));
        m.style.left = Math.round(x0) + "px"; m.style.top = Math.round(y0) + "px";
      }
      var C = {m:m, item:item, rows:rows, pos:pos, id:id, push:function(S){ stack.push(S); paint(); }};
      function paint(){
        while (m.firstChild) m.removeChild(m.firstChild);
        m.removeAttribute("data-sheet");
        if (stack.length) sheet(stack[stack.length - 1]); else root(C);
        m.scrollTop = 0; pos();
        var first = m.querySelector(".qc-rmi:not(.qc-off):not(.qc-rback)") || m.querySelector(".qc-rmi"); if (first){ try { first.focus({preventScroll:true}); } catch (err){} }
      }
      function back(){ if (!stack.length) return false; stack.pop(); paint(); return true; }
      relBack = back;
      m.addEventListener("keydown", function(e){
        var xs = [].slice.call(m.querySelectorAll(".qc-rmi")), i = xs.indexOf(document.activeElement);
        if (e.key === "ArrowDown" || e.key === "ArrowUp" || (kind === "pal" && (e.key === "ArrowRight" || e.key === "ArrowLeft"))){
          var k = xs.length; if (!k) return; i = (i + ((e.key === "ArrowDown" || e.key === "ArrowRight") ? 1 : k - 1) + k) % k; xs[i].focus(); e.preventDefault(); }
        else if ((e.key === "ArrowLeft" || e.key === "Backspace") && stack.length){ back(); e.preventDefault(); }
        else if (e.key === "Tab") relClose(false);
      });
      document.body.appendChild(m); relEl = m; popKind = kind; popBtn = btn; btn.setAttribute("aria-expanded", "true");
      paint();
      return m;
    }
    function after(){ setTimeout(function(){ rehome(); fit(); leader(); }, 60); }
    document.addEventListener("pointerdown", function(e){
      if (!relEl) return;
      if (relEl.contains(e.target) || (popBtn && popBtn.contains(e.target))) return;
      relClose(false);
    }, true);
    /* ---- Q368, owner (translated): "next to the name a small button in the colour the organ is marked with; pressing it lets
       the colour be changed. Adjacent to it an 'ADD' / '\u05d4\u05d5\u05e1\u05e3' button ... functional group, opposing (antagonist) functional
       group, adjacent tissues."
       SWATCH: filled with the colour the engine draws this structure in NOW (E.colour -> the engine's own colour function:
       the user's colour if it has one, else the mark tint if marked, else its per-structure or layer colour). Its palette
       is the selection controller's (the same colours as "Colour of the selected", a free colour and "Own colour"), and a
       choice goes through NMSKSelectCtl.setUserColour(hex, "ids", ...) -- the one store of user colours, which the page's
       undo, the saved sets and the share link already carry. It colours the card's scope (the clicked structure, or the
       whole muscle / part picked in the Parts chooser); no left/right twin, as the existing control has none.
       ADD: adds to what is marked (never replaces), one undo step per add, "+n marked" on the button. Functional groups and
       adjacency are the Related menu's own tables (NMSKQ298); the antagonist groups come from the page's groups sidecar
       (`ant`, data/anatomy/antagonist_groups_q368.json), every pair with its book page. ---- */
    var swEl = null, addB = null, flashT = null;
    function colourOf(id){ try { return E.colour ? E.colour(id) : null; } catch (err){ return null; } }
    var SRC = {user:"your colour", mark:"marked", own:"its own colour", highlight:"highlight", grey:"radiographic grey"};
    function paintSwatch(){
      if (!swEl) return;
      var c = cur ? colourOf(cur) : null;
      swEl.hidden = !c || !ctl() || !ctl().setUserColour;
      if (swEl.hidden) return;
      swEl.firstChild.style.background = c.hex;
      swEl.setAttribute("data-hex", c.hex); swEl.setAttribute("data-src", c.src);
      var nm = (E.info(cur) || {}).name || cur;
      swEl.setAttribute("aria-label", "Colour of " + nm + ": " + c.hex + " (" + (SRC[c.src] || c.src) + "). Change the colour");
      swEl.title = "Colour: " + c.hex + " \u00b7 " + (SRC[c.src] || c.src) + " \u2014 press to change";
    }
    function palOpen(){
      if (!cur || !swEl) return null;
      var c = ctl(); if (!c || !c.setUserColour) return null;
      var pal = c.palette ? c.palette() : [];
      return menu("pal", swEl, "qc-palmenu", "Colour of this structure", function(C){
        var m = C.m, grid = el("div", "qc-pgrid"), now = (colourOf(cur) || {}).hex, user = (c.colourState().user || {})[cur] || null;
        m.setAttribute("role", "dialog");
        m.appendChild(el("div", "qc-rhead", "Colour"));
        function apply(hex){
          var ids = S(); relClose(true);
          hist(); c.setUserColour(hex, "ids", ids); hist(); refresh();   /* Q378: sealed first */
        }
        pal.forEach(function(p){
          var b = C.item("", "qc-pc"); b.setAttribute("data-hex", p[1]); b.setAttribute("aria-label", p[0]); b.title = p[0]; b.style.background = p[1];
          if (user && user === p[1]) b.setAttribute("aria-pressed", "true");
          b.addEventListener("click", function(e){ e.stopPropagation(); apply(p[1]); });
          grid.appendChild(b);
        });
        m.appendChild(grid);
        var row = el("div", "qc-prow");
        var lab = el("label", "qc-rmi qc-pcust"); lab.setAttribute("tabindex", "-1");
        var cu = document.createElement("input"); cu.type = "color"; cu.value = now || "#d64545"; cu.className = "qc-pin"; cu.setAttribute("aria-label", "Any other colour");
        cu.addEventListener("change", function(){ apply(cu.value); });
        lab.appendChild(cu); lab.appendChild(document.createTextNode(" Other\u2026"));
        var own = C.item("Own colour", "qc-pown"); own.setAttribute("data-hex", ""); own.title = "Put the structure's own colour back (reset to default)";
        if (!user){ own.setAttribute("aria-disabled", "true"); own.classList.add("qc-off"); own.title = "It already has its own colour"; }
        own.addEventListener("click", function(e){ e.stopPropagation(); if (user) apply(null); });
        row.appendChild(lab); row.appendChild(own); m.appendChild(row);
      });
    }
    function antData(){
      var G = window.NMSKGroups342, d = null;
      try { d = G && G.data ? G.data() : null; } catch (err){ d = null; }
      if (!d && G && G.load){ var pr = G.load(); if (pr && pr.then) pr.then(function(){ if (popKind === "add") addOpen(); }); }
      return d ? (d.ant || {p:[], none:{}, add:{}, l:{}, bk:{}}) : null;
    }
    function nm(id){ var i = E.info(id); return i ? i.name : id; }
    function marksNow(){ var c = ctl(), s = c && c.state(); return s ? s.marks : []; }
    function addItems(id){
      var Q = q8(), A = antData(), gs = Q && Q.groups ? Q.groups(id) : null, adj = Q && Q.adjacent ? Q.adjacent(id) : null;
      var inf = E.info(id) || {}, bone = /^bone\b/i.test(inf.sub || ""), mk = marksNow(), MK = {};
      mk.forEach(function(x){ MK[x] = 1; });
      function fresh(ids){ return ids.filter(function(x){ return !MK[x]; }).length; }
      function lab(g){ return (A && A.l && A.l[g.id]) || g.name; }
      function src(rs){ return (rs || []).map(function(r){ var b = A && A.bk && A.bk[r[0]]; return (b ? b.s : r[0]) + " p. " + r[1]; }).join("; "); }
      function row(label, ids, what, title){  /* badge "+k" = how many it would newly mark */
        var k = fresh(ids);
        if (!k) return {label:label, off:true, why:"All " + ids.length + " already marked \u2014 nothing to add.", badge:String(ids.length)};
        return {label:label, badge:"+" + k, bcls:"qc-new", title:title || "", run:function(){ addIds(ids, what); }};
      }
      var mine = (gs || []).slice();
      if (A && A.add) Object.keys(A.add).forEach(function(k){ var g = A.add[k]; if (g.ids.indexOf(id) >= 0) mine.push({id:k, name:g.n, ids:g.ids, r:g.r}); });
      var out = [];
      /* 1. functional group */
      if (!gs) out.push({label:"Functional group", off:true, why:"The group tables are still loading \u2014 try again in a moment.", key:"grp"});
      else if (!mine.length) out.push({label:"Functional group", off:true, key:"grp",
        why:bone ? "A bone has no functional group (functional groups are groups of muscles)." : "Not in a functional group in this project's data."});
      else if (mine.length === 1){ var g1 = mine[0], r1 = row("Functional group: " + lab(g1), g1.ids, "functional group \u201c" + lab(g1) + "\u201d"); r1.key = "grp"; out.push(r1); }
      else out.push({label:"Functional group", key:"grp", n:mine.length, sheet:"Functional groups of " + inf.name,
                     items:mine.map(function(g){ var r = row(lab(g), g.ids, "functional group \u201c" + lab(g) + "\u201d"); r.key = g.id; return r; })});
      /* 2. antagonist functional group */
      if (!mine.length){
        out.push({label:"Antagonist group", off:true, key:"ant", why:bone ? "A bone has no functional group, so no antagonist group." : "No functional group in this project's data, so no antagonist group."});
      } else if (!A){
        out.push({label:"Antagonist group", off:true, key:"ant", why:"The antagonist table is still loading (or this page has none) \u2014 try again in a moment."});
      } else {
        var opp = [], seen = {}, reasons = [];
        mine.forEach(function(g){
          var here = [];
          (A.p || []).forEach(function(pr){
            var o = pr.a === g.id ? pr.b : pr.b === g.id ? pr.a : null; if (!o || seen[o]) return;
            var G2 = A.add && A.add[o] ? {id:o, name:A.add[o].n, ids:A.add[o].ids} : (Q && Q.group ? Q.group(o) : null);
            if (!G2 || !G2.ids || !G2.ids.length) return;
            seen[o] = 1; here.push({g:G2, pr:pr});
          });
          if (here.length) opp.push({own:g, list:here});
          else if (A.none && A.none[g.id]) reasons.push(lab(g) + ": " + A.none[g.id]);
        });
        var n = opp.reduce(function(s, x){ return s + x.list.length; }, 0);
        if (!n) out.push({label:"Antagonist group", off:true, key:"ant", why:reasons.length ? reasons[0] : "No antagonist group in this project's table for its groups."});
        else if (n === 1){ var o1 = opp[0].list[0], ra = row("Antagonist group: " + lab(o1.g), o1.g.ids, "antagonist group \u201c" + lab(o1.g) + "\u201d", o1.pr.mv + " \u2014 " + src(o1.pr.r));
          ra.key = "ant"; ra.akey = o1.g.id; out.push(ra); }
        else {
          var its = [];
          opp.forEach(function(x){
            its.push({head:true, label:"Opposes " + lab(x.own)});
            x.list.forEach(function(o){ var r = row(lab(o.g), o.g.ids, "antagonist group \u201c" + lab(o.g) + "\u201d", o.pr.mv + " \u2014 " + src(o.pr.r)); r.key = o.g.id; its.push(r); });
          });
          out.push({label:"Antagonist group", key:"ant", n:n, sheet:"Antagonist groups", items:its});
        }
      }
      /* 3. adjacent tissues: the same measured adjacency as Related structures -> Adjacent */
      var th = Q && Q.adjThreshold ? Q.adjThreshold() : null;
      if (!adj) out.push({label:"Adjacent tissues", off:true, key:"adj", why:"The adjacency table is still loading \u2014 try again in a moment."});
      else if (!adj.length) out.push({label:"Adjacent tissues", off:true, key:"adj", why:"Nothing" + (th ? " within " + th + " mm" : "") + " of this structure on this page."});
      else {
        var all = row("All " + adj.length + " adjacent", adj, "adjacent tissues"); all.key = "adj-all";
        var items = [all, {head:true, label:"Or one of them"}].concat(adj.map(function(x){
          var r = row(nm(x), [x], "adjacent \u201c" + nm(x) + "\u201d"); r.key = x; r.badge = r.off ? "\u2713" : "+"; return r; }));
        out.push({label:"Adjacent tissues", key:"adj", n:adj.length, sheet:"Adjacent tissues" + (th ? " (within " + th + " mm)" : ""), items:items});
      }
      return out;
    }
    var lastAdd = null;
    function addIds(ids, what){
      var c = ctl(); if (!c) return 0;
      hist();                                    /* Q378: sealed first, so Undo takes back the addition alone */
      var n = c.markIds(ids, true, false, true);
      hist(); refresh();
      lastAdd = {n:n, of:ids.length, what:what};
      if (addB){ addB.textContent = "+" + n + " marked"; addB.classList.add("qc-flash"); clearTimeout(flashT);
        flashT = setTimeout(function(){ if (addB){ addB.textContent = "ADD"; addB.classList.remove("qc-flash"); } }, 2600); }
      try { var Q = q8(); if (Q && Q.say) Q.say("+" + n + " marked \u00b7 " + what, n + " of " + ids.length + " newly marked (the rest were marked already); added to what was marked, one undo step."); } catch (err){}
      return n;
    }
    function addOpen(){
      if (!cur || !addB) return null;
      return menu("add", addB, "qc-addmenu", "Add to the marked set", function(C){ C.rows(addItems(C.id)); });
    }
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
    function isOnly(ids){ var c = ctl(), s = c && c.state(); if (typeof ids === "string") ids = [ids];
      return !!(s && s.mode === "only" && !s.inverted && s.marks.length === ids.length && every(ids, function(i){ return s.marks.indexOf(i) >= 0; })); }
    function refresh(){
      if (!card || card.hidden || !cur) return;
      var ids = S(), c = ctl(), st = c && c.state();
      var hd = every(ids, function(i){ return !!(E.state(i) || {}).hidden; }), fd = every(ids, function(i){ return !!(E.state(i) || {}).faded; });
      function p(k, v, lab){ btns[k].setAttribute("aria-pressed", String(!!v)); if (lab) btns[k].textContent = lab; }
      p("hide", hd, hd ? "Unhide" : "Hide"); p("fade", fd, fd ? "Unfade" : "Fade");
      p("only", isOnly(ids)); p("sel", !!st && every(ids, function(i){ return st.marks.indexOf(i) >= 0; }));
      card.setAttribute("data-scope", String(ids.length));
      btns.only.disabled = btns.sel.disabled = !c;
      if (addB) addB.disabled = !c;
      paintSwatch();
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
      tidyDet();
      var vh = window.innerHeight, top = card.getBoundingClientRect().top, t = detEl.getBoundingClientRect().top, cap = Math.round(vh * CAP);
      /* Q354: the whole open window takes at most ~60% of the view (a phone showed 81%); the details scroll inside it, and if what
         sits above them is already that tall the window itself scrolls */
      var room = cap - (t - top) - 10;
      detEl.style.maxHeight = Math.max(96, Math.round(Math.min(vh - t - 12, room))) + "px";
      card.style.maxHeight = cap + "px";
      card.style.overflowY = room < 96 ? "auto" : "";
    }
    /* Q354: the triangle count is not anatomy; the engine's full card prints it first ("1,200 tris \u00b7 left"). Inside this
       window the count goes, and the line with it when the side is all that is left (the head already says the side). */
    function tidyDet(){
      if (!detEl) return;
      [].forEach.call(detEl.querySelectorAll("#info p.sub2"), function(p){
        var t = p.textContent || "";
        if (!/^\s*[\d,.\u00a0\u202f\s]+tris\b/.test(t)) return;
        var rest = t.replace(/^\s*[\d,.\u00a0\u202f\s]+tris\s*\u00b7?\s*/, "").replace(/^(?:left|right|midline)\s*(?:\u00b7\s*)?/, "").trim();
        if (rest){ p.textContent = rest; } else { p.textContent = ""; p.hidden = true; p.style.display = "none"; }
      });
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
      if (card){ card.classList.remove("qc-open"); detEl.style.maxHeight = ""; card.style.maxHeight = ""; card.style.overflowY = ""; }
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
      cur = id; scope = null;
      card.querySelector(".qc-name").textContent = inf.name; card.querySelector(".qc-sub").textContent = inf.sub || "";
      if (card.hidden){ card.hidden = false; card.style.left = "0px"; card.style.top = "0px"; }
      addons(id);
      refresh();
      return true;
    }
    function addons(id){
      if (!addEl) return;
      while (addEl.firstChild) addEl.removeChild(addEl.firstChild);
      ADD.forEach(function(a){
        var h = el("div", "qc-addon"); h.setAttribute("data-addon", a.key);
        try { a.render(id, h, cardApi); } catch (err){}
        if (h.childNodes.length) addEl.appendChild(h);
      });
    }
    /* what an add-on may do with the card */
    var cardApi = {setScope:setScope, scope:function(){ return S().slice(); }, current:function(){ return cur; },
                   engine:function(){ return E; },
                   go:function(rid){ if (!rid) return; try { E.zoom(rid); } catch (err){} if (!card || card.hidden || cur !== rid) open(rid, null, null); },
                   refresh:function(){ refresh(); }, place:function(){ place(); },
                   redraw:function(){ if (cur && card && !card.hidden){ addons(cur); refresh(); fit(); } }};
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
               relOpen:function(){ return relOpen(); }, relClose:relClose, relMenu:function(){ return popKind === "rel" ? relEl : null; },
               /* Q368 */
               addOpen:function(){ return addOpen(); }, addMenu:function(){ return popKind === "add" ? relEl : null; },
               palOpen:function(){ return palOpen(); }, palMenu:function(){ return popKind === "pal" ? relEl : null; },
               swatch:function(){ return cur && swEl && !swEl.hidden ? {hex:swEl.getAttribute("data-hex"), src:swEl.getAttribute("data-src")} : null; },
               addItems:function(){ return cur ? addItems(cur).map(function(r){ return {key:r.key, label:r.label, off:!!r.off, why:r.why || null, n:r.n || 0, badge:r.badge || null,
                 items:r.items ? r.items.filter(function(i){ return !i.head; }).map(function(i){ return {key:i.key, label:i.label, off:!!i.off, badge:i.badge || null}; }) : null}; }) : null; },
               lastAdd:function(){ return lastAdd ? JSON.parse(JSON.stringify(lastAdd)) : null; },
               relBack:function(){ return relEl && relBack ? relBack() : false; },
               scope:function(){ return S().slice(); }, setScope:setScope,
               rect:function(){ if (!card || card.hidden) return null; var r = card.getBoundingClientRect(); return {l:r.left, t:r.top, r:r.right, b:r.bottom, w:r.width, h:r.height}; }};
    live = api;
    return api;
  }
  return {start:start, family:family, addon:addon, step:step, families:function(){ return FAM.map(function(f){ return f.key; }); },
          addons:function(){ return ADD.map(function(a){ return a.key; }); }};
})();
