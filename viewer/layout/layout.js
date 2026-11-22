/* Q382: what the owner asked for after testing the live page --
     "the dimensions window (the zoom chip) should be visible on every size change for 10 seconds and then disappear; in Settings it
      can be changed to permanent, or the delay changed"  and
     "allow moving the different boxes on the screen by dragging -- drag and save the state -- and also in SETTINGS".
   Moving boxes already exists (Q305 / Q335, viewer/q305/move.js: the six-dot handle, the three-dots menu, a per-page store). This module
   adds to it from the outside, by selector, and does not restructure any panel:
     - the floating cards the planning mode builds into its shell (#mode-main .mc-right / .mc-left / .mc-pick / .mc-safe) and its bottom
       dock (#mode-pills) become movable boxes: dragged by their title row (the dock: by its empty edge, mouse only), never by a button;
     - the title row of the boxes that already have a handle (name card, labels, legend, pose, slices, attachments) drags too;
     - a Settings section in the circled-i drawer (and a "Settings" button in the View group): zoom chip mode (seconds / always),
       "Lock panels" (dragging off), "Reset layout", "Show zoom chip", "Zoom 1:1".
   Positions are saved by NMSKMove per box and per screen class (desktop offsets / phone slots) in localStorage, in try / catch;
   moving a box is not an undo step. Docked sheets on a phone (the planning cards are bottom sheets there) stay where the page puts them.
     NMSKLayout.state()  .open()  .reset() */
var NMSKLayout = (function(){
  "use strict";
  var tries = 0, timer = 0, ready = false, sec = null;
  function q(sel){ return function(){ return document.querySelector(sel); }; }
  function ph(){ return !!(window.NMSKMove && NMSKMove.phone()); }
  var SPEC = [
    {key:"m-plan", label:"the planning panel",    el:q("#mode-main .mc-right"), nogrip:true, head:true, band:46, skip:ph},
    {key:"m-dist", label:"the distance card",     el:q("#mode-main .mc-left"),  nogrip:true, head:".mc-title", skip:ph},
    {key:"m-pick", label:"the structure picker",  el:q("#mode-main .mc-pick"),  nogrip:true, head:".mc-title", skip:ph},
    {key:"m-safe", label:"the safety card",       el:q("#mode-main .mc-safe"),  nogrip:true, head:".mc-title", skip:ph},
    {key:"m-dock", label:"the bottom dock",       el:q("#mode-pills"),          nogrip:true, head:function(e){ return e; }, mouseOnly:true}
  ];
  /* boxes that have their own handle already: their title row drags as well */
  var HEADS = {qcard:".qc-head", labels:".lb-head", legend:".lg-head", pose:".pz-head", slices:".xsp-head", attach:".pp-h", cut:".cp-head"};

  function mount(){
    var M = window.NMSKMove;
    if (!M || !M.state || !M.state().on) return false;
    SPEC.forEach(function(s){ M.add(s); });
    Object.keys(HEADS).forEach(function(k){ var b = M.box(k); if (b && !b.head) b.head = HEADS[k]; });
    var I = window.NMSKInfo;
    /* the circled i and the control bar are hidden while a mode is on, so the settings live in their own small panel; the i's section
       and the View group only open it, and the mode bar gets a gear (Hebrew label: that bar is Hebrew) */
    if (I && I.add){
      var st = document.createElement("div"); st.className = "q382-set";
      st.innerHTML = '<p>Zoom chip delay, locking the boxes, resetting the layout.</p><div class="q382-row"><button type="button" id="q382-open">Open the settings</button></div>';
      st.querySelector("button").addEventListener("click", function(){ api.open(); });
      I.add({key:"settings", title:"Settings: layout and zoom", order:44, el:st});
    }
    gear();
    var G = window.NMSKGroups;
    if (G && G.addTo) G.addTo("view", {label:"Settings", id:"q382-settings", title:"Zoom chip, lock the boxes, reset the layout",
      run:function(){ api.open(); }, label2:"Zoom chip delay, lock the boxes, reset the layout."});
    setInterval(gear, 1500);                                  /* the mode bar is built by the modes module, maybe later or again */
    ready = true; return true;
  }
  function gear(){
    var end = document.getElementById("mb-end"), old = document.getElementById("q382-gear");
    /* on a phone the mode bar has no room (the gear measurably cut the header name short): Settings are reached from the anatomy view there */
    if (window.innerWidth <= 560){ if (old && old.parentNode) old.parentNode.removeChild(old); return; }
    if (!end || old) return;
    var g = document.createElement("button"); g.type = "button"; g.id = "q382-gear"; g.className = "mb-x q382-gear";
    g.title = "הגדרות: פריסה וזום (Settings)"; g.setAttribute("aria-label", "הגדרות");
    g.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/></svg>';
    g.addEventListener("click", function(e){ e.stopPropagation(); if (pan && !pan.hidden) api.close(); else api.open(); });
    end.insertBefore(g, end.firstChild);
  }
  var pan = null;
  function panel(){
    if (pan) return pan;
    pan = document.createElement("div"); pan.id = "q382-panel"; pan.className = "q382-panel"; pan.hidden = true;
    pan.setAttribute("role", "dialog"); pan.setAttribute("aria-label", "Settings: layout and zoom");
    var h = document.createElement("div"); h.className = "q382-ph";
    h.innerHTML = '<b>Settings: layout and zoom</b><button type="button" id="q382-x" aria-label="Close" title="Close">&times;</button>';
    h.querySelector("button").addEventListener("click", function(){ api.close(); });
    pan.appendChild(h); pan.appendChild(section());
    document.body.appendChild(pan);
    window.addEventListener("keydown", function(e){ if (e.key === "Escape" && !pan.hidden){ api.close(); e.stopPropagation(); } }, true);
    return pan;
  }
  function section(){
    if (sec) return sec;
    sec = document.createElement("div"); sec.className = "q382-set"; sec.id = "q382-set";
    sec.innerHTML =
      '<h4>Zoom chip (the &ldquo;2.4&times; | 1:1&rdquo; label)</h4>' +
      '<label><input type="radio" name="q382-chip" value="timed" id="q382-timed"> Show it after each zoom for <input type="number" id="q382-secs" min="1" max="600" step="1" aria-label="seconds"> seconds</label>' +
      '<label><input type="radio" name="q382-chip" value="always" id="q382-always"> Always visible while zoomed</label>' +
      '<p>Hovering or touching the chip keeps it. Double-tap empty space (touch) or use <b>Zoom 1:1</b> below to return to 1:1 while it is hidden.</p>' +
      '<h4>Text size</h4>' +
      '<label>All boxes <select id="q386-g" aria-label="Text size of all boxes"></select></label>' +
      '<div class="q386-rows" id="q386-rows" role="group" aria-label="Text size of one box"></div>' +
      '<p>Each box can also have its own: the A&minus; / A+ buttons at its lower-right corner while the pointer is over it, or its three-dots menu. Text never goes under 10 px.</p>' +
      '<h4>Boxes</h4>' +
      '<label><input type="checkbox" id="q382-lock"> Lock panels (no dragging or resizing)</label>' +
      '<div class="q382-row"><button type="button" id="q382-reset">Reset layout</button><button type="button" id="q382-show">Show zoom chip</button><button type="button" id="q382-one">Zoom 1:1</button></div>' +
      '<p>Boxes move by their handle or by their title row, and change size by the grip at their lower-right corner (double-click it: back to the box&rsquo;s own size). Positions and sizes are kept in this browser, separately for a desktop-width and a phone-width window.</p>';
    function $(id){ return sec.querySelector("#" + id); }
    function paint(){
      var P = window.NMSKPinch ? NMSKPinch.prefs() : {always:false, secs:10};
      $("q382-always").checked = !!P.always; $("q382-timed").checked = !P.always; $("q382-secs").value = P.secs;
      $("q382-lock").checked = !!(window.NMSKMove && NMSKMove.locked());
      fonts();
    }
    /* Q386: the all-boxes text size and one row per box that is on the screen now (a row's value "" = the all-boxes size) */
    function opts(sel, withDefault, cur){
      var R = window.NMSKResize, h = withDefault ? '<option value="">Default</option>' : "";
      (R ? R.steps() : [100]).forEach(function(p){ h += '<option value="' + p + '"' + (cur === p ? " selected" : "") + ">" + p + " %</option>"; });
      return h;
    }
    function fonts(){
      var R = window.NMSKResize, g = $("q386-g"), rows = $("q386-rows"); if (!R || !g || !rows) return;
      if (document.activeElement !== g) g.innerHTML = opts(g, false, R.global());
      var bs = R.boxes().filter(function(b){ return b.present; }), sig = bs.map(function(b){ return b.key + ":" + (b.own ? b.pct : ""); }).join(",") + "|" + R.global();
      if (rows.getAttribute("data-sig") === sig) return;
      if (rows.contains(document.activeElement) && rows.getAttribute("data-sig") != null) return;
      rows.setAttribute("data-sig", sig);
      rows.innerHTML = "";
      bs.forEach(function(b){
        var l = document.createElement("label"), s = document.createElement("select");
        l.appendChild(document.createTextNode(b.label)); s.setAttribute("data-k", b.key); s.setAttribute("aria-label", "Text size of " + b.label);
        s.innerHTML = opts(s, true, b.own ? b.pct : -1); l.appendChild(s); rows.appendChild(l);
      });
    }
    sec.addEventListener("change", function(e){
      var P = window.NMSKPinch, t = e.target;
      if (t.id === "q382-lock"){ if (window.NMSKMove) NMSKMove.lock(t.checked); }
      else if (t.id === "q386-g"){ if (window.NMSKResize) NMSKResize.setGlobal(+t.value); }
      else if (t.getAttribute && t.getAttribute("data-k")){ if (window.NMSKResize) NMSKResize.setBox(t.getAttribute("data-k"), t.value === "" ? null : +t.value); }
      else if (P){
        if (t.name === "q382-chip") P.setPrefs({always:$("q382-always").checked});
        if (t.id === "q382-secs"){ var v = Math.round(+t.value); if (v > 0) P.setPrefs({secs:v, always:false}); }
      }
      paint();
    });
    sec.addEventListener("click", function(e){
      var t = e.target && e.target.closest ? e.target.closest("button") : null; if (!t) return;
      if (t.id === "q382-reset") api.reset();
      else if (t.id === "q382-show" && window.NMSKPinch) NMSKPinch.reveal();
      else if (t.id === "q382-one" && window.NMSKPinch) NMSKPinch.resetAll();
    });
    sec.addEventListener("pointerenter", paint); sec.addEventListener("focusin", paint);
    sec.paint = paint; paint();
    return sec;
  }
  function boot(){
    if (ready) return;
    if (mount()){ clearInterval(timer); timer = 0; return; }
    if (++tries > 400){ clearInterval(timer); timer = 0; }
  }
  var api = {
    start:function(){ if (ready || timer) return api; boot(); if (!ready) timer = setInterval(boot, 250); return api; },
    open:function(){ var p = panel(); p.hidden = false; if (window.NMSKInfo && NMSKInfo.close) NMSKInfo.close(); var s = section(); if (s.paint) s.paint(); },
    close:function(){ if (pan) pan.hidden = true; },
    reset:function(){
      var a = window.NMSKMove ? NMSKMove.restore() : false, b = window.NMSKResize ? NMSKResize.reset() : false;
      if (sec && sec.paint) sec.paint();
      return !!(a || b);
    },
    ready:function(){ return ready; },
    state:function(){ return {ready:ready, locked:!!(window.NMSKMove && NMSKMove.locked()), chip:window.NMSKPinch ? NMSKPinch.prefs() : null, boxes:SPEC.map(function(s){ return s.key; })}; }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function(){ api.start(); }); else api.start();
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKLayout;
