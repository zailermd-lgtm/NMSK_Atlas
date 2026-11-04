/* Q301: all the general prose behind one small circled i.
   Owner: "general informative material -- like the sources used for the model -- can be just a small circled i at the
   side, small and unobtrusive."
   So: a small circled i at the top-right of the 3-D view and a second one in the control bar (same drawer), and the
   drawer holds the prose that used to sit on the screen. The per-structure provenance is NOT moved out of reach --
   Q297 found cards that once lied about it, so the structure card keeps saying where its own geometry comes from; what
   moves here is the PAGE-wide prose: the licence, the citations, the conventions, the compatibility table.
   Sections register themselves, so a later round adds one without touching this file; `adopt` moves an existing element
   (the source panel, the licence sheet) into the drawer instead of copying its text, so there is never a second copy
   that can fall out of date.
     NMSKInfo.start({anchor, adopt:[id], openers:[el]})
     .add({key, title, html|build, order})  .open(key)  .close()  .toggle()  .isOpen()  .sections()  .state() */
var NMSKInfo = (function(){
  "use strict";
  var S = [], wrap = null, body = null, on = false, open = false, built = false, adopts = [];
  var ISVG = '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><circle cx="12" cy="12" r="9.3" fill="none" stroke="currentColor" stroke-width="1.9"/>' +
             '<circle cx="12" cy="7.4" r="1.25" fill="currentColor"/><path d="M12 10.6v6.6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  function sorted(){ return S.slice().sort(function(a, b){ return (a.order || 50) - (b.order || 50); }); }
  function render(){
    if (!body) return;
    body.innerHTML = "";
    sorted().forEach(function(s){
      var d = document.createElement("details");
      d.className = "qi-sec"; d.id = "qi-" + s.key;
      if (s.openFirst) d.open = true;
      var sum = document.createElement("summary"); sum.textContent = s.title; d.appendChild(sum);
      var inner = document.createElement("div"); inner.className = "qi-body";
      if (s.el) inner.appendChild(s.el);
      else {
        var h = "";
        try { h = s.build ? s.build() : (s.html || ""); } catch (e){ h = "<p>(not available)</p>"; }
        inner.innerHTML = h;
      }
      d.appendChild(inner); body.appendChild(d);
    });
    built = true;
  }
  function setOpen(v){
    open = !!v;
    if (wrap){ wrap.hidden = !open; wrap.classList.toggle("qi-open", open); }
    if (open && !built) render();
    document.querySelectorAll(".qi-btn").forEach(function(b){ b.setAttribute("aria-expanded", String(open)); });
    return open;
  }
  function mkBtn(cls){
    var b = document.createElement("button");
    b.type = "button"; b.className = "qi-btn " + (cls || "");
    b.innerHTML = ISVG;
    b.title = "About this page: sources and licence, what is measured and what is our convention, which actions combine";
    b.setAttribute("aria-label", b.title); b.setAttribute("aria-expanded", "false");
    b.addEventListener("click", function(e){ e.stopPropagation(); setOpen(!open); });
    return b;
  }
  var api = {
    start:function(opt){
      opt = opt || {};
      if (on) return api;
      wrap = document.createElement("aside");
      wrap.id = "q301-info"; wrap.className = "qi-wrap"; wrap.hidden = true;
      wrap.setAttribute("role", "dialog"); wrap.setAttribute("aria-label", "About this page");
      var head = document.createElement("div"); head.className = "qi-head";
      var t = document.createElement("b"); t.textContent = "About this page"; head.appendChild(t);
      var sp = document.createElement("span"); sp.className = "qi-sp"; head.appendChild(sp);
      var x = document.createElement("button");
      x.type = "button"; x.className = "qi-x"; x.id = "qi-close"; x.innerHTML = "&times;";
      x.title = "Close"; x.setAttribute("aria-label", "Close");
      x.addEventListener("click", function(e){ e.stopPropagation(); setOpen(false); });
      head.appendChild(x); wrap.appendChild(head);
      body = document.createElement("div"); body.className = "qi-list"; wrap.appendChild(body);
      document.body.appendChild(wrap);
      /* the small circled i at the side of the 3-D view */
      var corner = mkBtn("qi-corner"); corner.id = "qi-corner";
      document.body.appendChild(corner);
      var place = function(){
        var a = opt.anchor;
        if (!a || !a.getBoundingClientRect) return;
        var r = a.getBoundingClientRect();
        if (!(r.width > 40 && r.height > 40)) return;
        corner.style.left = Math.max(4, r.right - 34) + "px";
        corner.style.top = Math.max(4, r.top + 8) + "px";
        /* leave the corner i uncovered: the button that opens the drawer is also the one that closes it */
        var room = Math.max(60, r.bottom - (r.top + 44));
        wrap.style.maxHeight = Math.max(170, Math.min(room, window.innerHeight - 120)) + "px";
      };
      window.addEventListener("resize", place); setInterval(place, 700); setTimeout(place, 0);
      (opt.openers || []).forEach(function(el){ if (el && el.appendChild) el.appendChild(mkBtn("qi-inbar")); });
      adopts = (opt.adopt || []).slice();
      window.addEventListener("keydown", function(e){
        if (e.key === "Escape" && open){ setOpen(false); e.stopImmediatePropagation(); e.preventDefault(); }
      }, true);
      on = true;
      return api;
    },
    /* move an existing on-screen panel in here: one copy, never two */
    adoptEl:function(key, title, el, order){
      if (!el) return api;
      /* a panel the engine keeps hidden until it has something to say stays hidden here too: the i must not grow an empty row */
      if (String(el.textContent || "").replace(/\s+/g, " ").trim().length > 40){ el.hidden = false; el.removeAttribute("hidden"); }
      el.classList.add("qi-adopted");
      S = S.filter(function(s){ return s.key !== key; });
      S.push({key:key, title:title, el:el, order:order == null ? 80 : order});
      built = false; if (open) render();
      return api;
    },
    add:function(s){
      if (!s || !s.key) return api;
      S = S.filter(function(q){ return q.key !== s.key; });
      S.push(s); built = false; if (open) render();
      return api;
    },
    newButton:mkBtn,
    open:function(key){ setOpen(true); if (key){ var d = document.getElementById("qi-" + key); if (d) d.open = true; } return true; },
    close:function(){ return setOpen(false); }, toggle:function(){ return setOpen(!open); },
    isOpen:function(){ return open; }, refresh:function(){ built = false; if (open) render(); },
    sections:function(){ return sorted().map(function(s){ return s.key; }); },
    state:function(){ return {on:on, open:open, sections:api.sections(), adopted:S.filter(function(s){ return !!s.el; }).length}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKInfo;
