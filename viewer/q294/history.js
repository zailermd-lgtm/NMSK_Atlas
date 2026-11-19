/* Q294: one Undo / Redo history for every user state change on the page, plus Reset of the current module.
   Owner: "undo of at least 10 steps back, and redo" -- Q262's 20-entry undo covered the Marked-structures controller only.
   Model: state PROVIDERS (each a small {get, set, reset}) are registered by the engine and by the shared controllers; a
   snapshot is the JSON of every provider's get(). After any user input settles (click / change / key / wheel / touch,
   debounced) the snapshot is compared with the current history entry and pushed when it differs, so every action of every
   panel is covered without each panel calling in (a panel may still call commit() itself). Undo / Redo re-apply an entry
   through the providers' set(); a provider whose part of the state did not change is not touched. The camera is not part of
   the history (it is a view, not a state change; Reset view / the zoom chip restore it).
     NMSKHistory.register(key, {get, set, reset})   add a provider (get() must be JSON-able and stable)
     NMSKHistory.start(opt)                          opt {max, toolbars:[{el, cls}], floating (default true), anchor, resetView()}
     .commit()  .undo()  .redo()  .reset()  .canUndo()  .canRedo()  .snapshot()  .state()  .onReset(fn)  .onChange(fn)
     .restore(obj)  .onRegister(fn)                 (Q300: apply a snapshot without disturbing the history; hear about a late provider)
     .beginScope()  .endScope()                     (Q329: a workspace mode's session -- see below)
   Q329, mode sessions: a workspace mode (viewer/modes) sets display state of its own -- layers, marks, a faded rest, part
   views -- and puts the anatomy screen back when it is left. Entries recorded inside the mode still carry that state, so an
   Undo after leaving could bring the mode's look back onto the anatomy screen. NMSKModes calls beginScope() on entering (the
   state before the mode is remembered) and endScope() once the screen is restored: every top-level field of every provider
   that reads the SAME before entering and after leaving was owned by the mode (it was put back), so each entry recorded in
   the mode takes that field's before-the-mode value; entries that end up identical collapse. What the user did in the mode
   and kept (a structure hidden from the click card) stays, step by step; Undo inside the mode is untouched.
   Keys: Ctrl/Cmd+Z undo, Ctrl/Cmd+Shift+Z or Ctrl+Y redo (never while typing in a field). */
var NMSKHistory = (function(){
  "use strict";
  var scope = null;                                   // Q329: {base:snapObj() before the mode, lo:the last entry before it}
  var P = [], H = [], idx = -1, MAX = 60, timer = 0, applying = false, on = false, btns = [], resetHooks = [], changeHooks = [], regHooks = [], resetView = null, lastMsg = "";
  function snapObj(){                                   /* Q300: the keys come out in a fixed order, whatever order the
                                                           providers happened to register in -- a snapshot is compared as
                                                           a string, and a provider that joins late (measure, part slices,
                                                           the bone-through level) must not change how an older entry reads */
    var raw = {}; P.forEach(function(p){ try { raw[p.key] = p.get(); } catch (err){ raw[p.key] = null; } });
    var o = {}; Object.keys(raw).sort().forEach(function(k){ o[k] = raw[k]; }); return o;
  }
  function snap(){ return JSON.stringify(snapObj()); }
  function ui(){
    btns.forEach(function(b){
      if (b.k === "u") b.el.disabled = !(idx > 0);
      if (b.k === "r") b.el.disabled = !(idx < H.length - 1);
    });
    var su = document.getElementById("sel-undo"), sr = document.getElementById("sel-redo");
    if (su) su.disabled = !(idx > 0); if (sr) sr.disabled = !(idx < H.length - 1);
    changeHooks.forEach(function(f){ try { f(api.state()); } catch (err){} });
  }
  function commitNow(){
    if (timer){ clearTimeout(timer); timer = 0; }
    if (!on || applying) return false;
    var s = snap();
    if (idx >= 0 && H[idx] === s) return false;
    H = H.slice(0, idx + 1); H.push(s);
    if (scope && idx < scope.lo) scope.lo = idx;      // Q329: an undo below the mode's start, then a new step: the mode's entries begin here
    if (H.length > MAX){ var cut = H.length - MAX; H.splice(0, cut); if (scope) scope.lo = Math.max(-1, scope.lo - cut); }
    idx = H.length - 1; ui();
    return true;
  }
  function commit(delay){
    if (!on || applying) return;
    if (timer) clearTimeout(timer);
    timer = setTimeout(commitNow, delay == null ? 320 : delay);
  }
  function applyObj(o){                                 /* Q300: set every provider and NEVER touch H[idx]. The model
                                                           reset applies the load snapshot between two commits, so the
                                                           state it replaced has to stay in the history as its own entry. */
    applying = true;
    try {
      P.forEach(function(p){
        if (!(p.key in o)) return;
        var cur; try { cur = JSON.stringify(p.get()); } catch (err){ cur = null; }
        if (cur !== JSON.stringify(o[p.key])){ try { p.set(o[p.key]); } catch (err2){ if (window.console) console.error("history: " + p.key, err2); } }
      });
    } finally { applying = false; }
  }
  function applyEntry(s){
    var o; try { o = JSON.parse(s); } catch (err){ return; }
    applyObj(o);
    H[idx] = snap();                                   // normalised: what the providers really hold now (a later commit compares with this)
  }
  function undo(){
    commitNow();
    if (!(idx > 0)){ say("Nothing to undo."); ui(); return false; }
    idx--; applyEntry(H[idx]); say("Undone (" + idx + " more step" + (idx === 1 ? "" : "s") + " back)."); ui(); return true;
  }
  function redo(){
    commitNow();
    if (!(idx < H.length - 1)){ say("Nothing to redo."); ui(); return false; }
    idx++; applyEntry(H[idx]); say("Redone."); ui(); return true;
  }
  function reset(){
    commitNow();
    applying = true;
    try {
      P.forEach(function(p){ if (p.reset){ try { p.reset(); } catch (err){ if (window.console) console.error("reset: " + p.key, err); } } });
      resetHooks.forEach(function(f){ try { f(); } catch (err){ if (window.console) console.error("reset hook", err); } });
      try { if (window.NMSKModes && NMSKModes.resetCurrent) NMSKModes.resetCurrent(); } catch (err3){}
      if (resetView){ try { resetView(); } catch (err4){} }
    } finally { applying = false; }
    var changed = commitNow();
    say(changed ? "Everything in this module is back to its start (Undo brings it back)." : "Already at the start.");
    return changed;
  }
  /* Q329: the mode session (see the header) */
  function canon(v){                                    // key-order-free JSON, to compare entries whose fields were rewritten
    if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
    if (v && typeof v === "object") return "{" + Object.keys(v).sort().map(function(k){ return JSON.stringify(k) + ":" + canon(v[k]); }).join(",") + "}";
    return JSON.stringify(v === undefined ? null : v);
  }
  function plain(v){ return !!v && typeof v === "object" && !Array.isArray(v); }
  function beginScope(){
    commitNow();
    scope = {base:snapObj(), lo:on ? idx : -1};
    return true;
  }
  function endScope(){
    if (!scope) return 0;
    var b = scope.base, lo = scope.lo; scope = null;
    if (!on) return 0;
    commitNow();
    var ex = snapObj(), owned = {}, n = 0;
    Object.keys(ex).forEach(function(k){
      if (!(k in b)) return;                           // a provider that joined during the mode: nothing to compare with
      if (plain(ex[k]) && plain(b[k])){
        var f = {}; Object.keys(ex[k]).concat(Object.keys(b[k])).forEach(function(x){ if (canon(ex[k][x]) === canon(b[k][x])) f[x] = 1; });
        owned[k] = f;
      } else if (canon(ex[k]) === canon(b[k])) owned[k] = true;
    });
    for (var j = Math.max(0, lo + 1); j < H.length; j++){
      var o; try { o = JSON.parse(H[j]); } catch (err){ continue; }
      Object.keys(owned).forEach(function(k){
        if (!(k in o)) return;
        if (owned[k] === true){ o[k] = JSON.parse(JSON.stringify(b[k])); return; }
        if (!plain(o[k])) return;
        Object.keys(owned[k]).forEach(function(x){ if (x in b[k]) o[k][x] = JSON.parse(JSON.stringify(b[k][x])); else delete o[k][x]; });
      });
      H[j] = JSON.stringify(o); n++;
    }
    var keep = [], nIdx = 0;                            // collapse neighbours that now read the same
    H.forEach(function(e, i){
      if (keep.length && i > lo && canon(JSON.parse(e)) === canon(JSON.parse(keep[keep.length - 1]))){ if (i <= idx) nIdx = keep.length - 1; return; }
      keep.push(e); if (i <= idx) nIdx = keep.length - 1;
    });
    H = keep; idx = nIdx; H[idx] = snap();             // the current entry reads exactly what the providers hold (commitNow compares strings)
    ui();
    return n;
  }
  function say(m){ lastMsg = m; var e = document.getElementById("hist-msg"); if (e){ e.textContent = m; e.hidden = !m; clearTimeout(say.t); say.t = setTimeout(function(){ e.hidden = true; }, 2200); } }
  function typing(t){ var tag = t && t.tagName; return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable); }
  function onKey(e){
    if (!on || !(e.ctrlKey || e.metaKey) || e.altKey || e.repeat) return;
    var k = String(e.key || "").toLowerCase();
    if (k !== "z" && k !== "y") return;
    if (typing(e.target)) return;
    e.preventDefault(); e.stopImmediatePropagation();
    if (k === "y" || e.shiftKey) redo(); else undo();
  }
  if (typeof window !== "undefined" && window.addEventListener){
    window.addEventListener("keydown", onKey, true);
    ["click", "change", "keyup", "touchend"].forEach(function(t){ document.addEventListener(t, function(){ commit(); }, true); });
    document.addEventListener("pointerup", function(){ commit(); }, true);
    /* Q380: a press on ANOTHER control seals the step still waiting for its debounced commit (on a busy page that wait
       is over a second), so Undo takes back that control's action alone and not the click before it as well. Repeated
       presses on the same control (a stepper, the model) still merge into one step, as before. */
    var lastT = null;
    document.addEventListener("pointerdown", function(e){ if (timer && lastT && e.target !== lastT) commitNow(); lastT = e.target; }, true);
    document.addEventListener("wheel", function(){ commit(700); }, {capture:true, passive:true});
  }
  var ICON = {u:'<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M9 7L4 12l5 5M4 12h10a6 6 0 0 1 0 12h-2" transform="translate(0,-3)" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
              r:'<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M15 7l5 5-5 5M20 12H10a6 6 0 0 0 0 12h2" transform="translate(0,-3)" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
              x:'<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M4 12a8 8 0 1 0 2.4-5.7M4 4v4.5h4.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'};
  function mount(el, cls, prefix){
    if (!el) return;
    var ref = prefix === "mb-" ? null : el.firstChild;
    [["u", "Undo (Ctrl/Cmd+Z)", undo], ["r", "Redo (Ctrl/Cmd+Shift+Z or Ctrl+Y)", redo], ["x", "Reset this module: everything back to its start, without leaving it (undoable)", reset]].forEach(function(d, i){
      var b = document.createElement("button");
      b.type = "button"; b.className = (cls || "") + " hist-b"; b.id = prefix + ["undo", "redo", "reset"][i]; b.title = d[1];
      b.setAttribute("aria-label", d[1].replace(/ \(.*$/, "")); b.innerHTML = ICON[d[0]];
      b.addEventListener("click", function(e){ e.stopPropagation(); d[2](); });
      if (ref) el.insertBefore(b, ref); else el.appendChild(b);
      btns.push({k:d[0], el:b});
    });
  }
  var api = {
    register:function(key, p){
      if (!key || !p || typeof p.get !== "function") return;
      p.key = key; P = P.filter(function(q){ return q.key !== key; }); P.push(p);
      if (on){ H[idx] = snap(); }
      regHooks.forEach(function(f){ try { f(key, p); } catch (err){} });     // Q300: a provider that joins after start() is announced
    },
    onRegister:function(f){ if (typeof f === "function") regHooks.push(f); },
    start:function(opt){
      opt = opt || {}; if (on) return api;
      MAX = Math.max(20, opt.max || MAX); resetView = opt.resetView || null;
      (opt.toolbars || []).forEach(function(t){ mount(t.el, t.cls, t.prefix || "hist-"); });
      if (opt.floating !== false){                       // a small floating group (bottom right): the crowded toolbars stay as they were
        var fb = document.createElement("div"); fb.id = "hist-bar"; fb.className = "hist-bar"; fb.setAttribute("role", "group"); fb.setAttribute("aria-label", "Undo, redo, reset");
        document.body.appendChild(fb); mount(fb, "hist-fb", "h-");
        var anchor = opt.anchor || null;               // kept on the 3-D view's own bottom-right corner (it follows the docking of the workspace modes)
        var place = function(){
          if (!anchor || !anchor.getBoundingClientRect) return;
          var r = anchor.getBoundingClientRect(), w = fb.offsetWidth || 130, h = fb.offsetHeight || 46;
          if (!(r.width > 40 && r.height > 40)) return;
          fb.style.left = Math.max(4, Math.min(window.innerWidth - w - 4, r.right - w - 10)) + "px";
          fb.style.top = Math.max(4, Math.min(window.innerHeight - h - 4, r.bottom - h - 10)) + "px";
          fb.style.right = "auto"; fb.style.bottom = "auto";
        };
        window.addEventListener("resize", place); setInterval(place, 700); setTimeout(place, 0);
      }
      var m = document.createElement("div"); m.id = "hist-msg"; m.className = "hist-msg"; m.hidden = true; m.setAttribute("aria-live", "polite"); document.body.appendChild(m);
      on = true; H = [snap()]; idx = 0; ui();
      return api;
    },
    mountInto:function(el, cls, prefix){ mount(el, cls, prefix); ui(); },
    active:function(){ return on; }, commit:function(){ return commitNow(); }, schedule:commit, undo:undo, redo:redo, reset:reset,
    canUndo:function(){ return idx > 0; }, canRedo:function(){ return idx < H.length - 1; },
    snapshot:function(){ return snapObj(); }, restore:applyObj, keys:function(){ return P.map(function(p){ return p.key; }); },
    state:function(){ return {on:on, idx:idx, len:H.length, max:MAX, canUndo:idx > 0, canRedo:idx < H.length - 1, pending:!!timer, msg:lastMsg}; },
    onReset:function(f){ if (typeof f === "function") resetHooks.push(f); }, onChange:function(f){ if (typeof f === "function") changeHooks.push(f); },
    applying:function(){ return applying; },
    beginScope:beginScope, endScope:endScope, inScope:function(){ return !!scope; }
  };
  return api;
})();
