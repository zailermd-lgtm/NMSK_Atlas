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
   Keys: Ctrl/Cmd+Z undo, Ctrl/Cmd+Shift+Z or Ctrl+Y redo (never while typing in a field). */
var NMSKHistory = (function(){
  "use strict";
  var P = [], H = [], idx = -1, MAX = 60, timer = 0, applying = false, on = false, btns = [], resetHooks = [], changeHooks = [], resetView = null, lastMsg = "";
  function snapObj(){ var o = {}; P.forEach(function(p){ try { o[p.key] = p.get(); } catch (err){ o[p.key] = null; } }); return o; }
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
    if (H.length > MAX) H.splice(0, H.length - MAX);
    idx = H.length - 1; ui();
    return true;
  }
  function commit(delay){
    if (!on || applying) return;
    if (timer) clearTimeout(timer);
    timer = setTimeout(commitNow, delay == null ? 320 : delay);
  }
  function applyEntry(s){
    var o; try { o = JSON.parse(s); } catch (err){ return; }
    applying = true;
    try {
      P.forEach(function(p){
        if (!(p.key in o)) return;
        var cur; try { cur = JSON.stringify(p.get()); } catch (err){ cur = null; }
        if (cur !== JSON.stringify(o[p.key])){ try { p.set(o[p.key]); } catch (err2){ if (window.console) console.error("history: " + p.key, err2); } }
      });
    } finally { applying = false; }
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
    register:function(key, p){ if (!key || !p || typeof p.get !== "function") return; p.key = key; P = P.filter(function(q){ return q.key !== key; }); P.push(p); if (on){ H[idx] = snap(); } },
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
    snapshot:function(){ return snapObj(); }, keys:function(){ return P.map(function(p){ return p.key; }); },
    state:function(){ return {on:on, idx:idx, len:H.length, max:MAX, canUndo:idx > 0, canRedo:idx < H.length - 1, pending:!!timer, msg:lastMsg}; },
    onReset:function(f){ if (typeof f === "function") resetHooks.push(f); }, onChange:function(f){ if (typeof f === "function") changeHooks.push(f); },
    applying:function(){ return applying; }
  };
  return api;
})();
