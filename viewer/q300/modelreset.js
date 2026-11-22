/* Q300: Reset of the MODEL, as distinct from Q294's Reset of the current module.
   Owner: "also, a button for reset the specific model."
   Q294's circular arrow resets the module you are in (its own defaults + the work mode + the view). This one puts the
   model back to the state the PAGE LOADED IN -- pose, camera, visibility, isolation, opacity, marks, cuts and
   cross-sections, part slices, measurements, labels -- in one tap, without leaving the module, and as a single Undo step.
   How it is exact rather than approximate: NMSKHistory already takes a snapshot of every registered provider; this module
   keeps the FIRST one forever (the history itself discards it once 60 entries have gone by) and restores that object.
   Nothing here knows what a provider holds, so a page that registers a new provider gets it reset for free.
   The camera is deliberately outside the history (it is a view, not a state), so it is restored through resetView().
     NMSKModelReset.start({history, resetView, bars:[{el, cls, prefix}], extras:[{label, run}], label})
     .run()  .loaded()  .state()  .scope() */
var NMSKModelReset = (function(){
  "use strict";
  var hist = null, LOAD = null, resetView = null, extras = [], btns = [], on = false, runs = 0;
  var ICON = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">' +
             '<path d="M12 4.5a7.5 7.5 0 1 0 7.1 5.1" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>' +
             '<path d="M12 1.6v5.8M9.2 4.5h5.6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>' +
             '<circle cx="12" cy="13.6" r="2.1" fill="currentColor"/></svg>';
  var TOUCHES = "pose, camera, which structures are shown, isolation and solo, every opacity and fade, the marked structures, the cut and the cross-sections, part slices, measurements and labels";
  var KEEPS = "the module you are in (it does not take you out of it), the work mode, anything you saved in this browser (saved poses, saved mark sets), the page's browser zoom, and the structure cards' own text";
  function sorted(o){                                /* same key order as the history's own snapshot, so the two compare */
    var out = {};
    Object.keys(o || {}).sort().forEach(function(k){ out[k] = o[k]; });
    return out;
  }
  function say(m){
    var e = document.getElementById("hist-msg");
    if (!e || !m) return;
    e.textContent = m; e.hidden = false;
    clearTimeout(say.t); say.t = setTimeout(function(){ e.hidden = true; }, 3200);
  }
  function run(){
    if (!on || !hist || !LOAD) return false;
    hist.commit();                                  // the state you are leaving becomes its own history entry
    try { if (hist.restore) hist.restore(LOAD); } catch (err){ if (window.console) console.error("model reset", err); }
    extras.forEach(function(x){ try { x.run(); } catch (err){} });
    if (resetView){ try { resetView(); } catch (err){} }
    var changed = hist.commit();                    // ... and the load state becomes the next one: ONE Ctrl+Z goes back
    runs++;
    if (window.NMSKShowAll && NMSKShowAll.refresh) NMSKShowAll.refresh();
    say(changed ? "The model is back to how this page loaded. Undo brings your work back."
                : "The model is already how this page loaded.");
    return changed;
  }
  function mount(el, cls, prefix){
    if (!el) return;
    var b = document.createElement("button");
    b.type = "button"; b.className = (cls || "") + " mr-b"; b.id = (prefix || "") + "mr-model";
    b.title = "Reset the model: back to how this page loaded (" + TOUCHES + ") -- one tap, you stay in this module, and Undo brings it back";
    b.setAttribute("aria-label", "Reset the model to how the page loaded");
    b.innerHTML = ICON;
    b.addEventListener("click", function(e){ e.stopPropagation(); run(); });
    el.appendChild(b);
    btns.push(b);
    if (!document.getElementById("mr-note")){        // the long version lives behind the "i" that NMSKTips folds this into
      var n = document.createElement("span");
      n.id = "mr-note"; n.className = "mr-note";
      n.innerHTML = '<p class="nmsk-tip">Two different resets. The circular arrow resets <b>the module you are in</b> to its own defaults. The one with the dot resets <b>the model</b>: ' +
                    TOUCHES + ' all go back to how this page loaded. It leaves alone ' + KEEPS + '. Both are a single Undo step.</p>';
      el.appendChild(n);
    }
  }
  var api = {
    start:function(opt){
      opt = opt || {};
      if (on) return api;
      hist = opt.history || window.NMSKHistory || null;
      if (!hist || !hist.snapshot) return api;
      resetView = opt.resetView || null;
      extras = (opt.extras || []).filter(function(x){ return x && typeof x.run === "function"; });
      try { LOAD = sorted(JSON.parse(JSON.stringify(hist.snapshot()))); } catch (err){ LOAD = null; }
      if (!LOAD) return api;
      if (hist.onRegister){                           // a provider may join after this (measure, part slices, boneread):
        hist.onRegister(function(key, p){             // its value AT REGISTRATION is its load value, so record it then
          if (!LOAD || (key in LOAD)) return;
          try { LOAD[key] = JSON.parse(JSON.stringify(p.get())); LOAD = sorted(LOAD); } catch (err){}
        });
      }
      (opt.bars || []).forEach(function(t){ mount(t.el, t.cls, t.prefix); });
      on = true;
      return api;
    },
    mountInto:function(el, cls, prefix){ if (on) mount(el, cls, prefix); },
    run:run,
    loaded:function(){ return LOAD ? sorted(JSON.parse(JSON.stringify(LOAD))) : null; },
    scope:function(){ return {touches:TOUCHES, keeps:KEEPS}; },
    state:function(){ return {on:on, runs:runs, keys:LOAD ? Object.keys(LOAD).sort() : [], buttons:btns.length}; }
  };
  return api;
})();
