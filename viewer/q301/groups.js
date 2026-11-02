/* Q301: ONE control. A row of labelled groups that unfold, and Undo / Redo / the two resets always on the screen, named.
   Owner: "a clear, simple CONTROL is missing, including UNDO and REDO" / "imaging should live under ONE box that unfolds
   into several options. Same for other parts."
   The two patterns the market agrees on (docs/research/Q301_controls_and_render_styles.md 1): BioDigital moved "the
   exploration tools ... into a single menu" and moved "Undo and Redo ... to their own toolbar"; Visible Body puts the
   History button -- undo, redo and back-to-original in one place -- in the bottom menu bar. So:
     row 1  the groups: View | Layers | Imaging | Cut | Mark | Learn | Measure | Needle  (accordion: one open at a time)
     row 2  the control itself: Undo  Redo  Reset module  Reset model  i      -- always there, with WORDS, never folded
             (a destructive action must not hide behind progressive disclosure)
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
  function anyMembers(g){
    return (g.members || []).some(function(m){
      if (m.el) return true;
      if (m.adopt) return [].concat(m.adopt).some(function(id){ return !!document.getElementById(id); });
      return !!m.label;
    });
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
  function openSheet(key){
    var g = null;
    G.forEach(function(q){ if (q.key === key) g = q; });
    if (!g) return false;
    if (cur === key){ closeSheet(); return false; }
    cur = key;
    stash();
    sheet.hidden = false;
    sTitle.textContent = g.label;
    (g.members || []).forEach(function(m){
      var row = el("div", "qg-m");
      if (m.el){ m.el.classList.add("qg-keep"); row.appendChild(m.el); }
      else if (m.adopt){
        var ids = [].concat(m.adopt), got = 0;
        ids.forEach(function(id){
          var e = document.getElementById(id);
          if (!e) return;
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
  function place(){
    if (!anchor || !anchor.getBoundingClientRect || !bar) return;
    var r = anchor.getBoundingClientRect();
    if (!(r.width > 40 && r.height > 40)) return;
    var w = Math.max(220, Math.min(r.width - 16, 760));
    bar.style.width = w + "px";
    bar.style.left = Math.round(r.left + (r.width - w) / 2) + "px";
    bar.style.top = Math.round(Math.max(4, r.bottom - bar.offsetHeight - 6)) + "px";
    var open = 0;
    if (sheet && !sheet.hidden){
      sheet.style.width = w + "px";
      sheet.style.left = bar.style.left;
      sheet.style.maxHeight = Math.round(Math.max(120, r.height * 0.45)) + "px";
      sheet.style.top = Math.round(Math.max(4, r.bottom - bar.offsetHeight - 10 - sheet.offsetHeight)) + "px";
      open = (sheet.offsetHeight || 0) + 6;
    }
    /* Q300's chip bar and Q294's notice share this corner and sit above us in the stack: tell the stylesheet how far
       to lift them so they never cover Undo / Redo -- NOR an open group's buttons. Both happened on a 390 px phone:
       first the chip bar sat on Redo, then, once it was lifted by the bar's height alone, it sat on the open sheet and
       swallowed the fat toggle and two of six taps on the depth peel. The lift is the whole occluded height. */
    document.documentElement.style.setProperty("--q301-bar-h", (bar.offsetHeight || 96) + 4 + open + "px");
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
      G.forEach(function(g){
        var b = el("button", "qg-g");
        b.type = "button"; b.id = "qg-" + g.key;
        b.setAttribute("aria-expanded", "false");
        b.title = g.title || ("Open the " + g.label + " controls");
        var t = el("span", "qg-gl", g.label); b.appendChild(t);
        var d = el("span", "qg-dot"); d.hidden = true; d.setAttribute("aria-hidden", "true"); b.appendChild(d);
        b.addEventListener("click", function(ev){ ev.stopPropagation(); openSheet(g.key); });
        gRow.appendChild(b); gBtns[g.key] = b;
      });
      bar.appendChild(gRow);
      hRow = el("div", "qg-hist"); hRow.id = "q301-hist";
      hRow.setAttribute("role", "group"); hRow.setAttribute("aria-label", "Undo, redo and the two resets");
      bar.appendChild(hRow);
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
      /* the control itself: the SAME undo / redo / module-reset the rest of the page uses, mounted here with words */
      if (hist && hist.mountInto) hist.mountInto(hRow, "qg-h", "q301-");
      if (opt.modelreset && opt.modelreset.mountInto) opt.modelreset.mountInto(hRow, "qg-h", "q301-");
      dressHistory();
      if (opt.info && opt.info.newButton){
        var ib = opt.info.newButton("qi-inbar"); ib.id = "q301-info-btn"; hRow.appendChild(ib);
      }
      document.body.classList.add("q301-on");
      window.addEventListener("resize", place); setInterval(place, 700); setTimeout(place, 0);
      if (combos && combos.onChange) combos.onChange(paint);
      setInterval(paint, 500);
      on = true; paint();
      return api;
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
