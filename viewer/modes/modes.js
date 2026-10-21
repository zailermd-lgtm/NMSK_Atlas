/* Q272 clinical WORKSPACE MODES -- the shared controller (viewer/modes/modes.js, synced into both templates).
   Generic by design: this public template never names a private clinical tool. A mode is a key ("inj" / "us" / "cmp") whose
   PROVIDER an optional add-on registers at attach time (NMSKModes.register(key, {title, short, build, enter, exit})); the add-on
   keeps its own logic and only re-skins it here. Entering a mode: snapshot the anatomy screen (camera, selection, marks, categories,
   parts markers, phone sheets), add body.mode-on + body.mode-<key> (CSS hides the chrome, nothing is destroyed), show the mode bar and
   let the provider build its cards into #mode-main / #mode-pills; the 3-D element and the tools' own panels are DOCKED onto a slot's
   rectangle (fixed positioning, re-placed on resize). Exiting: provider.exit(), undock everything, remove the classes, restore the
   snapshot. The switcher ("מה עושים היום?") shows on the first load of a session (sessionStorage), from the "מצב" toolbar button and
   from a #mode=<key> hash (or a ?mode=<key> query, Q273). */
var NMSKModes = (function(){
  var host = null, api = null, recsCache = null, providers = {}, cur = null, curP = null, ctx = null, snap = null, queued = null;
  var docks = [], tick = 0, pollReady = 0, KEY = "nmsk.mode.v1", MODES = ["inj", "us", "cmp"];
  function $(id){ return document.getElementById(id); }
  function el(tag, attrs, kids){
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function(k){
      if (k === "text") e.textContent = attrs[k]; else if (k === "html") e.innerHTML = attrs[k];
      else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), attrs[k]); else if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function(c){ if (c) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  function getApi(){ if (!api && host && host.api) { try { api = host.api(); } catch (err){ api = null; } } return api; }
  function recs(){ if (!recsCache){ var a = getApi(); recsCache = a && a.list ? a.list() : []; } return recsCache; }
  function remember(choice){ try { sessionStorage.setItem(KEY, JSON.stringify({choice:choice, at:Date.now()})); } catch (err){} }
  function remembered(){ try { var j = JSON.parse(sessionStorage.getItem(KEY) || "null"); return j && j.choice ? j.choice : null; } catch (err){ return null; } }
  function fireResize(){ try { window.dispatchEvent(new Event("resize")); } catch (err){} if (host && host.resized) { try { host.resized(); } catch (err2){} } }
  /* ---------- docking: a fixed-positioned element follows a slot's rectangle ---------- */
  function placeDock(d){
    var slot = d.slots.filter(function(s){ var r = s.getBoundingClientRect(); return r.width > 2 && r.height > 2; })[0], st = d.el.style;
    if (!slot || d.hidden){ st.visibility = "hidden"; st.width = "2px"; st.height = "2px"; st.left = "0px"; st.top = "0px"; return; }
    var r = slot.getBoundingClientRect(), imp = {position:"fixed", left:r.left + "px", top:r.top + "px", width:r.width + "px", height:r.height + "px", right:"auto", bottom:"auto",
      margin:"0", "min-width":"0", "min-height":"0", "max-width":"none", "max-height":"none", "z-index":String(d.z), overflow:"hidden", "border-radius":getComputedStyle(slot).borderRadius};
    Object.keys(imp).forEach(function(k){ st.setProperty(k, imp[k], "important"); });   // beats the engines' and the tools' own !important layout rules
    st.visibility = "";
    if (d.scale && d.scale !== 1){ st.transform = "scale(" + d.scale + ")"; st.transformOrigin = "50% 50%"; st.clipPath = d.scale > 1 ? "inset(" + ((1 - 1 / d.scale) / 2 * 100).toFixed(3) + "%)" : "none"; }
    else { st.transform = ""; st.clipPath = ""; }
  }
  function placeAll(){ docks.forEach(placeDock); }
  function dock(e, slots, z, opt){
    if (!e) return null;
    slots = Array.isArray(slots) ? slots : [slots];
    var d = docks.filter(function(x){ return x.el === e; })[0];
    if (!d){ d = {el:e, style:e.getAttribute("style"), cls:e.className, slots:slots, z:z || 70, hidden:false, scale:1, model:!!(opt && opt.model)}; docks.push(d); }
    else { d.slots = slots; d.z = z || d.z; }
    placeDock(d); if (d.model) fireResize();
    return d;
  }
  function undock(e){
    var i = docks.map(function(x){ return x.el; }).indexOf(e); if (i < 0) return;
    var d = docks.splice(i, 1)[0];
    if (d.style == null) d.el.removeAttribute("style"); else d.el.setAttribute("style", d.style);
    if (d.model) fireResize();
  }
  function undockAll(){ docks.slice().forEach(function(d){ undock(d.el); }); }
  /* ---------- the anatomy screen snapshot (public APIs only) ---------- */
  function takeSnapshot(){
    var s = {host:null, selection:null, cats:[], parts:null, lay:null}, a = getApi();
    try { s.host = host.snapshot(); } catch (err){}
    try { if (window.__panelLayoutState) s.lay = window.__panelLayoutState().state; } catch (err0){}   // the Q267 one-tap layout (Model-only / Split / Compare)
    try { var sel = a && a.selection ? a.selection() : null; if (sel && sel.state) s.selection = sel.state(); } catch (err2){}
    try { var seen = {}; recs().forEach(function(r){ if (r.cat && !seen[r.cat]){ seen[r.cat] = 1; s.cats.push([r.cat, !!a.categoryOn(r.cat)]); } }); } catch (err3){}
    try { var p = a && a.parts ? a.parts() : null; if (p && p.state) s.parts = p.state().mode; } catch (err4){}
    return s;
  }
  function restoreSnapshot(s){
    if (!s) return;
    var a = getApi();
    try { s.cats.forEach(function(c){ if (!!a.categoryOn(c[0]) !== c[1]) a.setCategoryOn(c[0], c[1]); }); } catch (err){}
    try {
      var sel = a && a.selection ? a.selection() : null, st = s.selection;
      if (sel && st){
        sel.clear();
        if (st.marks && st.marks.length){ sel.markIds(st.marks, true, true, true); if (st.sel && st.sel !== "show") sel.setGroup("sel", st.sel, true); if (st.oth && st.oth !== "show") sel.setGroup("oth", st.oth, true); }
      }
    } catch (err2){}
    try { var p = a && a.parts ? a.parts() : null; if (p && p.setMode && s.parts != null && p.state().mode !== s.parts){ p.setMode(s.parts); if (p.dirty) p.dirty(); } } catch (err3){}
    try { if (s.host) host.restore(s.host); } catch (err4){}
    /* the Q267 layout toggle: its own 500 ms poller reacts to the tools a mode opened / closed with a lag (and a tool closed by the mode
       can leave it on Split); put it back exactly through its own public button, never its internals */
    try {
      var b3 = $("t-lay3"), n = 0;
      while (s.lay && window.__panelLayoutState && b3 && window.__panelLayoutState().state !== s.lay && n++ < 3) b3.click();
      if (s.lay) setTimeout(function(){ var m = 0; while (window.__panelLayoutState && b3 && window.__panelLayoutState().state !== s.lay && m++ < 3) b3.click(); }, 1200);
    } catch (err5){}
  }
  /* ---------- the switcher ---------- */
  function switcher(){ return $("mode-switch"); }
  function syncTiles(){
    var sw = switcher(); if (!sw) return;
    Array.prototype.forEach.call(sw.querySelectorAll(".mw-tile"), function(t){
      var k = t.getAttribute("data-mode"), avail = k === "anat" || !!providers[k];
      if (avail) t.removeAttribute("disabled"); else t.setAttribute("disabled", "disabled");
      t.setAttribute("aria-pressed", String((cur || "anat") === k));
    });
    var title = document.title || "";
    Array.prototype.forEach.call(sw.querySelectorAll(".mw-models a"), function(a){ a.classList.toggle("cur", title.indexOf(a.getAttribute("data-page")) >= 0); });
  }
  function showSwitcher(){ var sw = switcher(); if (!sw) return; syncTiles(); sw.hidden = false; var f = sw.querySelector(".mw-tile:not([disabled])"); try { if (f) f.focus(); } catch (err){} }
  function hideSwitcher(){ var sw = switcher(); if (sw) sw.hidden = true; }
  function choose(k){
    if (k === "anat"){ if (cur) exit(); remember("anat"); hideSwitcher(); return; }
    hideSwitcher(); enter(k);
  }
  /* ---------- enter / exit ---------- */
  function makeCtx(key, p){
    var shell = $("mode-shell");
    return {
      key:key, host:host, api:getApi(), recs:recs, el:el, shell:shell, bar:{chips:$("mb-chips"), end:$("mb-end")}, main:$("mode-main"), pills:$("mode-pills"),
      dock:dock, undock:undock, relayout:placeAll, fireResize:fireResize,
      modelDock:function(slots, z){ return dock(host.model, slots, z || 70, {model:true}); },
      setDockHidden:function(e, hidden){ var d = docks.filter(function(x){ return x.el === e; })[0]; if (d){ d.hidden = !!hidden; placeDock(d); } },
      setDockScale:function(e, s){ var d = docks.filter(function(x){ return x.el === e; })[0]; if (d){ d.scale = s || 1; placeDock(d); } },
      isPhone:function(){ return host.isPhone ? host.isPhone() : window.innerWidth <= 760; },
      selectedId:function(){ try { return host.selectedId(); } catch (err){ return null; } },
      select:function(id){ try { host.select(id); } catch (err){} },
      recName:function(id){ var r = recs().filter(function(x){ return x.id === id; })[0]; return r ? r.name : (id || ""); },
      side:function(r){ var s = r && r.side; return s === "r" ? "ימין" : s === "l" ? "שמאל" : (s === "right" ? "ימין" : s === "left" ? "שמאל" : ""); },
      exit:function(){ exit(); }
    };
  }
  function enter(key){
    if (!host) return false;
    var p = providers[key];
    if (!p){ queued = key; remember(key); return false; }
    if (!host.ready()){ queued = key; remember(key); waitReady(); return false; }
    if (cur === key) return true;
    if (cur) exit(true);
    queued = null;
    snap = takeSnapshot();
    cur = key; curP = p; ctx = makeCtx(key, p);
    document.body.classList.add("mode-on", "mode-" + key);
    var shell = $("mode-shell"); shell.hidden = false;
    $("mb-pill").querySelector(".mb-long").textContent = p.title || key; $("mb-pill").querySelector(".mb-short").textContent = p.short || p.title || key;
    ctx.bar.chips.innerHTML = ""; ctx.main.innerHTML = ""; ctx.pills.innerHTML = ""; ctx.pills.hidden = true;
    Array.prototype.slice.call(ctx.bar.end.children).forEach(function(c){ if (c.id !== "mb-exit" && c.id !== "mb-exit-x") c.remove(); });
    try { p.build(ctx); } catch (err){ console.error("mode " + key + " failed to build:", err); }
    try { p.enter(ctx); } catch (err2){ console.error("mode " + key + " failed to enter:", err2); }
    placeAll(); fireResize();
    clearInterval(tick); tick = setInterval(function(){ placeAll(); if (curP && curP.refresh){ try { curP.refresh(ctx); } catch (err3){} } }, 300);
    remember(key); syncTiles();
    return true;
  }
  function exit(silent){
    if (!cur) return;
    clearInterval(tick); tick = 0;
    try { curP.exit(ctx); } catch (err){ console.error("mode exit:", err); }
    undockAll();
    document.body.classList.remove("mode-on", "mode-" + cur, "mode-more");
    var shell = $("mode-shell"); shell.hidden = true; $("mode-main").innerHTML = ""; $("mb-chips").innerHTML = ""; $("mode-pills").innerHTML = "";
    cur = null; curP = null; ctx = null;
    restoreSnapshot(snap); snap = null;
    fireResize();
    if (!silent) remember("anat");
    syncTiles();
  }
  function waitReady(){
    if (pollReady) return;
    var t0 = Date.now();
    pollReady = setInterval(function(){
      if (host.ready()){ clearInterval(pollReady); pollReady = 0; if (queued && providers[queued]) enter(queued); }
      else if (Date.now() - t0 > 120000){ clearInterval(pollReady); pollReady = 0; }
    }, 250);
  }
  /* ---------- wiring ---------- */
  function init(h){
    host = h;
    var sw = switcher(), shell = $("mode-shell");
    if (sw){
      sw.addEventListener("click", function(e){ var t = e.target.closest(".mw-tile"); if (t && !t.hasAttribute("disabled")) choose(t.getAttribute("data-mode")); });
      $("mw-close").addEventListener("click", function(){ remember(cur || "anat"); hideSwitcher(); });
      sw.addEventListener("keydown", function(e){ if (e.key === "Escape"){ remember(cur || "anat"); hideSwitcher(); } });
    }
    if (shell){
      $("mb-exit").addEventListener("click", function(){ exit(); });
      $("mb-exit-x").addEventListener("click", function(){ exit(); });
    }
    var tb = host.toolbar;
    if (tb){
      var b = el("button", {type:"button", id:"t-mode", class:host.toolClass, title:"מצב עבודה: אנטומיה / תכנון הזרקה / US אבחנתי / השוואת דימות", text:"מצב", onclick:function(){ showSwitcher(); }});
      var hub = $("t-hub"); if (hub && hub.parentNode === tb) tb.insertBefore(b, hub.nextSibling); else tb.insertBefore(b, tb.firstChild);
    }
    window.addEventListener("resize", placeAll);
    var m = /[#&]mode=(inj|us|cmp|anat)\b/.exec(location.hash || "") || /[?&]mode=(inj|us|cmp|anat)\b/.exec(location.search || ""), choice = m ? m[1] : remembered();   /* Q273: ?mode= as well as #mode= */
    if (!choice){ var t0 = Date.now(), w = setInterval(function(){ if (host.ready() || Date.now() - t0 > 90000){ clearInterval(w); if (!cur) showSwitcher(); } }, 200); }
    else if (choice !== "anat"){ queued = choice; waitReady(); }
    syncTiles();
  }
  function register(key, p){
    if (MODES.indexOf(key) < 0) return false;
    providers[key] = p; syncTiles();
    if (queued === key){ if (host && host.ready()) enter(key); else waitReady(); }
    return true;
  }
  return {init:init, register:register, enter:enter, exit:function(){ exit(); }, show:showSwitcher, hide:hideSwitcher, current:function(){ return cur; },
          state:function(){ var sid = null; try { sid = host ? host.selectedId() : null; } catch (err){} return {cur:cur, registered:Object.keys(providers), switcherOpen:!!(switcher() && !switcher().hidden), queued:queued, docks:docks.length, selected:sid}; },
          el:el};
})();

window.NMSKModes = NMSKModes;   /* the optional add-ons (separate files) register their providers through the window object */
