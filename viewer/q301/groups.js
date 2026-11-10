/* Q301: ONE control. A row of labelled groups that unfold, and Undo / Redo / the two resets always on the screen, named.
   Owner: "a clear, simple CONTROL is missing, including UNDO and REDO" / "imaging should live under ONE box that unfolds
   into several options. Same for other parts."
   The two patterns the market agrees on (docs/research/Q301_controls_and_render_styles.md 1): BioDigital moved "the
   exploration tools ... into a single menu" and moved "Undo and Redo ... to their own toolbar"; Visible Body puts the
   History button -- undo, redo and back-to-original in one place -- in the bottom menu bar. So:
     row 1  the groups: Search | Systems | Dissection | Imaging | Pose | Measure | Needle | Favorites
             (accordion: one open at a time -- Q318 renamed these to the owner's own words)
     row 2  the control itself: Undo  Redo  Reset module  Reset model  i      -- always there, with WORDS, never folded
             (a destructive action must not hide behind progressive disclosure), plus any group that asks
             for this row with row2 (Navigate, which is how the model is moved rather than what is done to it)
   It ADOPTS the engines' existing buttons by moving the real DOM nodes into the group sheet: same ids, same listeners,
   no second copy of any behaviour, and the old crowded bars empty themselves. A group shows a dot while anything in it
   is active, and each member is decorated from NMSKCombos: co-active members get a +, incompatible ones are disabled
   with their one-line reason shown underneath, not in a tooltip the phone never displays.
     NMSKGroups.start({anchor, history, modelreset, info, combos, groups:[{key,label,title,members:[...]}]})
   member := {adopt:"id"|["id",...]} | {el:node} | {label, run, active, combo, title}
     .open(key)  .close()  .isOpen()  .groups()  .members(key)  .state() */
var NMSKGroups = (function(){
  "use strict";
  var G = [], bar = null, gRow = null, hRow = null, sheet = null, sHead = null, sBody = null, sTitle = null;
  var hist = null, combos = null, cur = null, on = false, anchor = null, gBtns = {}, mEls = {}, park = null;
  var WORD = {"q301-undo":"Undo", "q301-redo":"Redo", "q301-reset":"Module", "q301-mr-model":"Model"};
  function el(tag, cls, txt){ var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  /* would this group render anything AT ALL right now? A member's node can come and go with the engine's own layout
     (the own engine's phone layout does not offer Measure), and a group button that opens an empty sheet is worse than
     no button, so it is hidden instead. Resolved at paint time, not once at start. */
  /* The nodes a member adopts. `adopt` names them by id; `adoptSel` is a CSS selector, which is how a
     member reaches a button the public page is not allowed to name by id -- the private add-ons put a class
     on theirs. Both are resolved when they are needed, never cached, because the add-ons mount late. */
  function nodesOf(m){
    var out = [];
    if (m.adopt) [].concat(m.adopt).forEach(function(id){ var e = document.getElementById(id); if (e && out.indexOf(e) < 0) out.push(e); });
    if (m.adoptSel) Array.prototype.forEach.call(document.querySelectorAll(m.adoptSel), function(e){ if (out.indexOf(e) < 0) out.push(e); });
    return out;
  }
  function anyMembers(g){
    return (g.members || []).some(function(m){
      if (m.el) return true;
      if (m.adopt || m.adoptSel) return nodesOf(m).length > 0;
      return !!m.label;
    });
  }
  /* Q318, owner: "the SEARCH, SYSTEMS and so on row is supposed to replace the whole top row of HUB, mode,
     SOURCES and so on." Adoption used to happen the first time a group was opened, so until then every adopted
     button was still sitting -- and still drawn -- in the engine's own bar. On the Z pages that bar is #topright,
     which the stylesheet hides; on the own-engine pages it is #tools, a full-width row that the control bar now
     lands on top of, so Imaging, Needle, Pose and Measure were drawn twice and overlapping.
     So every adopted node is moved into the hidden parking node AT ONCE, which is what empties the engine's bar,
     and the sheet takes it from there. It runs again on each paint because a button the engine creates later
     (the own engine builds its Measure button only on a wide layout) must be adopted the moment it appears.
     Whatever is left in the engine's own bar afterwards is, by construction, exactly what no group claims. */
  var emptied = [];                   /* the engine bars this control has taken buttons out of */
  function adoptAll(){
    if (!park) return;
    G.forEach(function(g){
      (g.members || []).forEach(function(m){
        if (!m.adopt && !m.adoptSel) return;
        nodesOf(m).forEach(function(e){
          if (park.contains(e) || (sheet && sheet.contains(e)) || (bar && bar.contains(e))) return;
          var par = e.parentNode;
          if (par && par.nodeType === 1 && par !== document.body && par !== park && emptied.indexOf(par) < 0) emptied.push(par);
          e.classList.add("qg-adopted");
          park.appendChild(e);
        });
      });
    });
    /* A bar with nothing left in it must not go on reserving a row of the screen -- on the own-engine pages
       #tools is a full-width strip the control bar would otherwise sit on top of. It is decided afresh every
       time rather than once, so a button the engine adds to that bar later, which no group claims, brings the
       bar back instead of being lost behind a hidden parent. */
    for (var i = 0; i < emptied.length; i++){
      var b = emptied[i];
      if (!b.isConnected) continue;
      b.hidden = b.children.length === 0;
    }
  }
  function anyActive(g){
    return (g.members || []).some(function(m){
      if (typeof m.active === "function"){ try { return !!m.active(); } catch (e){ return false; } }
      if (m.combo && combos){ try { return !!combos.verdict(m.combo).active; } catch (e2){ return false; } }
      return false;
    });
  }
  /* The sheet holds the engines' REAL buttons, moved in. Emptying it with innerHTML would destroy them, and the page
     would lose `#t-cut` the moment another group was opened -- so everything the sheet did not create itself is moved
     to a hidden parking node first, where it keeps its id and its listeners and can be moved back in. */
  function stash(){
    if (!sBody || !park) return;
    var keep = sBody.querySelectorAll(".qg-adopted, .qg-keep");
    for (var i = 0; i < keep.length; i++) park.appendChild(keep[i]);
    sBody.innerHTML = "";
  }
  function closeSheet(){
    cur = null;
    stash();
    if (sheet) sheet.hidden = true;
    Object.keys(gBtns).forEach(function(k){ gBtns[k].setAttribute("aria-expanded", "false"); gBtns[k].classList.remove("open"); });
    place(); paint();                 /* drop the chip bar's lift back to the bar's own height in the same frame */
  }
  /* Q318, owner: "if there is only one tile that opens, and it then opens the window that matters, do that
     at once and skip the pointless step in between." A group whose whole content is one adopted button IS
     that button, so pressing the group presses it. The node has already been moved into the sheet, and its
     own listeners came with it, so this reaches exactly what a tap on the sheet would have reached. */
  function soleButton(g){
    var ms = (g.members || []).filter(function(m){ return m.el || m.adopt || m.adoptSel; });
    if (ms.length !== 1 || !(ms[0].adopt || ms[0].adoptSel)) return null;
    var ns = nodesOf(ms[0]);
    if (ns.length !== 1) return null;
    var e = ns[0];
    return (e.tagName === "BUTTON" && !e.disabled) ? e : null;
  }
  function openSheet(key){
    var g = null;
    G.forEach(function(q){ if (q.key === key) g = q; });
    if (!g) return false;
    if (cur === key){ closeSheet(); return false; }
    var only = soleButton(g);
    if (only){ closeSheet(); try { only.click(); } catch (e){} return true; }
    cur = key;
    stash();
    sheetDragged = false;
    sheet.hidden = false;
    sTitle.textContent = g.label;
    (g.members || []).forEach(function(m){
      var row = el("div", "qg-m");
      if (m.el){ m.el.classList.add("qg-keep"); row.appendChild(m.el); }
      else if (m.adopt || m.adoptSel){
        var got = 0;
        nodesOf(m).forEach(function(e){
          e.classList.add("qg-adopted"); e.removeAttribute("hidden"); e.hidden = false;
          row.appendChild(e); got++;
        });
        if (!got) return;
      } else if (m.label){
        var b = el("button", "qg-b q301-b", m.label);
        b.type = "button"; if (m.id) b.id = m.id;
        if (m.title) b.title = m.title;
        b.addEventListener("click", function(ev){ ev.stopPropagation(); if (m.run) { try { m.run(); } catch (e2){} } paint(); });
        row.appendChild(b);
        m._btn = b;
      } else return;
      if (m.combo){
        var note = el("p", "qg-why"); note.hidden = true;
        row.appendChild(note); m._why = note;
      }
      if (m.label2){ var h = el("p", "qg-sub", m.label2); row.appendChild(h); }
      mEls[g.key + "/" + (m.combo || m.label || m.adopt)] = row;
      sBody.appendChild(row);
    });
    Object.keys(gBtns).forEach(function(k){
      var hot = k === key;
      gBtns[k].setAttribute("aria-expanded", String(hot));
      gBtns[k].classList.toggle("open", hot);
    });
    if (window.NMSKTips && NMSKTips.fold){ try { NMSKTips.fold(sheet); } catch (e3){} }   /* the sheet's own hint notes fold behind the small "i" at once, not on the observer's next tick */
    place(); paint();
    return true;
  }
  /* the combo decoration: a dot on the group, a + on a co-active member, disabled + reason on an incompatible one */
  function paint(){
    adoptAll();
    G.forEach(function(g){
      var b = gBtns[g.key]; if (!b) return;
      var has = anyMembers(g);
      b.hidden = !has;
      if (!has){ if (cur === g.key) closeSheet(); return; }
      var hot = anyActive(g);
      b.classList.toggle("live", hot);
      var d = b.querySelector(".qg-dot");
      if (d) d.hidden = !hot;
      b.setAttribute("aria-label", g.label + (hot ? " (something in this group is active)" : ""));
    });
    if (!cur || !combos) return;
    var g = null; G.forEach(function(q){ if (q.key === cur) g = q; });
    if (!g) return;
    (g.members || []).forEach(function(m){
      if (!m.combo || !m._why) return;
      var v;
      try { v = combos.verdict(m.combo); } catch (e){ return; }
      var tgt = m._btn || (m.adopt ? document.getElementById([].concat(m.adopt)[0]) : null);
      if (tgt){
        tgt.classList.toggle("qg-live", !!v.active);
        tgt.classList.toggle("qg-off", !!v.disabled);
        tgt.classList.toggle("qg-over", !!v.overridden);     /* allowed, but something else is in charge of it */
        if (v.disabled){ tgt.setAttribute("aria-disabled", "true"); tgt.disabled = true; }
        else { tgt.removeAttribute("aria-disabled"); if (!m.keepDisabled) tgt.disabled = false; }
      }
      m._why.hidden = !(v.reason && (v.disabled || v.with.length || v.overridden));
      m._why.className = "qg-why" + (v.disabled ? " qg-why-off" : v.overridden ? " qg-why-over" : " qg-why-on");
      m._why.textContent = (v.disabled ? "⊘ " : v.overridden ? "⇣ " : "+ ") + v.reason;
    });
  }
  /* Q316: the group sheet can be dragged by its head. Left alone on a narrow screen, where it is a bottom sheet and
     place() owns its rectangle, and never started from a control inside the head. */
  var sheetDragged = false;
  function initDrag(elm, handle){
    var sx = 0, sy = 0, ox = 0, oy = 0, dragging = false;
    handle.addEventListener("pointerdown", function(e){
      if (window.innerWidth <= 460) return;
      if (e.target.closest && e.target.closest("button,input,select,label,a")) return;
      dragging = true; sx = e.clientX; sy = e.clientY;
      var r = elm.getBoundingClientRect(); ox = r.left; oy = r.top;
      try { handle.setPointerCapture(e.pointerId); } catch (err){}
      e.preventDefault();
    });
    handle.addEventListener("pointermove", function(e){
      if (!dragging) return;
      var nx = Math.max(0, Math.min(window.innerWidth - 40, ox + e.clientX - sx));
      var ny = Math.max(0, Math.min(window.innerHeight - 40, oy + e.clientY - sy));
      elm.style.left = nx + "px"; elm.style.top = ny + "px"; elm.style.right = "auto"; elm.style.bottom = "auto";
      if (elm === sheet) sheetDragged = true;
    });
    function end(){ dragging = false; }
    handle.addEventListener("pointerup", end); handle.addEventListener("pointercancel", end);
  }
  function place(){
    if (!anchor || !anchor.getBoundingClientRect || !bar) return;
    var r = anchor.getBoundingClientRect();
    if (!(r.width > 40 && r.height > 40)) return;
    var w = Math.max(220, Math.min(r.width - 16, 760));
    bar.style.width = w + "px";
    bar.style.left = Math.round(r.left + (r.width - w) / 2) + "px";
    /* Q318: the top of the view. The owner asked for this row to BE the top row, in place of the hub /
       mode / sources corner it has now absorbed, so the sheet unfolds downward from under it. */
    var top = Math.round(Math.max(4, r.top + 6));
    bar.style.top = top + "px";
    if (sheet && !sheet.hidden && !sheetDragged){
      sheet.style.width = w + "px";
      sheet.style.left = bar.style.left;
      sheet.style.maxHeight = Math.round(Math.max(120, r.height * 0.55)) + "px";
      sheet.style.top = (top + (bar.offsetHeight || 0) + 4) + "px";
    }
    /* Q300's chip bar and Q294's notice are anchored to the BOTTOM, which the bar no longer occupies, so
       there is nothing left for them to clear. The variable stays, at zero, because the stylesheets of both
       engines read it. */
    document.documentElement.style.setProperty("--q301-bar-h", "0px");
  }
  function dressHistory(){            /* the icons the Q294 / Q300 modules mount get a WORD under them: that is the point */
    Object.keys(WORD).forEach(function(id){
      var b = document.getElementById(id);
      if (!b || b.querySelector(".qg-t")) return;
      var t = el("span", "qg-t", WORD[id]);
      b.appendChild(t);
      b.classList.add("qg-hb");
    });
  }
  var api = {
    start:function(opt){
      opt = opt || {};
      if (on) return api;
      hist = opt.history || window.NMSKHistory || null;
      combos = opt.combos || window.NMSKCombos || null;
      anchor = opt.anchor || null;
      G = (opt.groups || []).filter(function(g){
        if (!g || !g.key || !g.label) return false;
        g.members = (g.members || []).filter(function(m){
          if (!m) return false;
          if (m.el) return true;
          if (m.label) return true;
          return [].concat(m.adopt || []).some(function(id){ return !!document.getElementById(id); });
        });
        return g.members.length > 0;
      });
      bar = el("div", "qg-bar"); bar.id = "q301-bar";
      bar.setAttribute("role", "group"); bar.setAttribute("aria-label", "The controls: groups of tools, and undo / redo / reset");
      gRow = el("div", "qg-groups"); gRow.id = "q301-groups";
      bar.appendChild(gRow);
      hRow = el("div", "qg-hist"); hRow.id = "q301-hist";
      hRow.setAttribute("role", "group"); hRow.setAttribute("aria-label", "Undo, redo, the two resets, and how the model is moved");
      bar.appendChild(hRow);
      /* Q318: a group may ask for the SECOND row with row2, beside undo / redo / the resets. Navigate asks
         for it, because it is how you move the model rather than something you do to it; it opens the same
         sheet as any other group. Those buttons go in after the control itself has mounted, so the words
         the owner asked to leave in place stay first. */
      var row2 = [];
      G.forEach(function(g){
        var b = el("button", "qg-g");
        b.type = "button"; b.id = "qg-" + g.key;
        b.setAttribute("aria-expanded", "false");
        b.title = g.title || ("Open the " + g.label + " controls");
        var t = el("span", "qg-gl", g.label); b.appendChild(t);
        var d = el("span", "qg-dot"); d.hidden = true; d.setAttribute("aria-hidden", "true"); b.appendChild(d);
        b.addEventListener("click", function(ev){ ev.stopPropagation(); openSheet(g.key); });
        if (g.row2) row2.push(b); else gRow.appendChild(b);
        gBtns[g.key] = b;
      });
      document.body.appendChild(bar);
      park = el("div", "qg-park"); park.id = "q301-park"; park.hidden = true;
      document.body.appendChild(park);
      sheet = el("div", "qg-sheet"); sheet.id = "q301-sheet"; sheet.hidden = true;
      sheet.setAttribute("role", "group"); sheet.setAttribute("aria-label", "The open group's controls");
      sHead = el("div", "qg-shead");
      sTitle = el("b", "qg-stitle", ""); sHead.appendChild(sTitle);
      sHead.appendChild(el("span", "qg-ssp"));
      var sx = el("button", "qg-sx", "×");
      sx.type = "button"; sx.id = "qg-close"; sx.title = "Close this group"; sx.setAttribute("aria-label", "Close this group");
      sx.addEventListener("click", function(ev){ ev.stopPropagation(); closeSheet(); });
      sHead.appendChild(sx); sheet.appendChild(sHead);
      sBody = el("div", "qg-sbody"); sheet.appendChild(sBody);
      document.body.appendChild(sheet);
      initDrag(sheet, sHead);
      /* the control itself: the SAME undo / redo / module-reset the rest of the page uses, mounted here with words */
      if (hist && hist.mountInto) hist.mountInto(hRow, "qg-h", "q301-");
      if (opt.modelreset && opt.modelreset.mountInto) opt.modelreset.mountInto(hRow, "qg-h", "q301-");
      dressHistory();
      if (opt.info && opt.info.newButton){
        var ib = opt.info.newButton("qi-inbar"); ib.id = "q301-info-btn"; hRow.appendChild(ib);
      }
      row2.forEach(function(b){ hRow.appendChild(b); });                  /* Q318: after the words, never before */
      document.body.classList.add("q301-on");
      window.addEventListener("resize", place); setInterval(place, 700); setTimeout(place, 0);
      if (combos && combos.onChange) combos.onChange(paint);
      setInterval(paint, 500);
      adoptAll();                       /* Q318: empty the engine's own bar now, not at the first open */
      on = true; paint();
      return api;
    },
    /* Q303: a module that starts AFTER this bar was built cannot be in the table it was built from -- the same gap
       Q301 closed in Q300's NMSKShowAll with add(source). A member joins an EXISTING group here, in the same shape
       the table uses, so a later round adds to View instead of adding a new top-level button. */
    addTo:function(key, m){
      if (!m || !(m.el || m.adopt || m.label)) return false;
      var g = null; G.forEach(function(q){ if (q.key === key) g = q; });
      if (!g) return false;
      g.members.push(m);
      if (cur === key){ closeSheet(); openSheet(key); } else paint();
      return true;
    },
    open:openSheet, close:closeSheet, isOpen:function(){ return cur; }, refresh:paint,
    parked:function(){ return park ? park.children.length : 0; },
    groups:function(){ return G.map(function(g){ return {key:g.key, label:g.label, n:g.members.length, live:anyActive(g)}; }); },
    members:function(key){
      var g = null; G.forEach(function(q){ if (q.key === key) g = q; });
      return g ? g.members.map(function(m){ return {label:m.label || null, adopt:m.adopt || null, combo:m.combo || null}; }) : [];
    },
    state:function(){ return {on:on, open:cur, groups:api.groups(), bar:!!bar}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKGroups;
