/* Q303: ONE undo step, for state Q294's history must not watch continuously.
   THE PROBLEM, found by this round's own harness before a template was touched. Q294's history snapshots every
   registered provider's get() whenever input settles, and compares snapshots as strings. Three things this round
   changes are deliberately NOT in that model: the camera (Q294 left it out on purpose -- "it is a view, not a state
   change"), the clinical tools' slice point and probe pose, and the four panes' cameras. Registering them as ordinary
   providers would make every unrelated Undo move the camera as well. The first draft instead published the BEFORE state
   and committed, then the AFTER state and committed -- which produced TWO entries, so a second Undo press did nothing
   visible. The harness caught it ("facing me: one undo step" failed) and this module is the fix.
   THE SHAPE. The provider's get() is a plain COUNTER, so it is stable between actions and nothing else can disturb it.
   The real values live in a side table keyed by that counter. An action files "where we are now" under the counter the
   history already holds, does its work, moves the counter on, files the new value, and commits ONCE. Undo restores the
   previous entry, whose counter names the BEFORE value; Redo names the AFTER one. One entry, one press, either way.
     NMSKStep.make(history, key, read, write) -> {step(fn), n(), filed(), value(n)}
     NMSKStep.hold(fn)                               run several modules' steps as ONE entry
   read() returns a JSON-able value; write(v) applies one. */
var NMSKStep = (function(){
  "use strict";
  var MAX = 120, HOLD = 0, HISTS = [];
  function make(hist, key, read, write){
    if (hist && HISTS.indexOf(hist) < 0) HISTS.push(hist);
    var n = 0, seq = 0, side = {}, order = [];
    function file(k){
      var v = null;
      try { v = read(); } catch (err){ v = null; }
      if (side[k] === undefined) order.push(k);
      side[k] = v;
      while (order.length > MAX){ var old = order.shift(); if (old !== n) delete side[old]; }
    }
    if (hist && hist.register) hist.register(key, {
      get:function(){ return {n:n}; },
      set:function(v){
        if (!v) return;
        n = v.n || 0;
        if (side[n] !== undefined && side[n] !== null){ try { write(side[n]); } catch (err){} }
      },
      reset:function(){}
    });
    return {
      step:function(fn){
        file(n);                                  /* where we are now, under the counter the history already holds */
        var r = null;
        try { r = fn(); } catch (err){ if (window.console) console.error("q303 step " + key, err); }
        n = ++seq;
        file(n);
        /* exactly ONE entry: get() moved only by the counter. Inside hold() the commit is deferred, so two modules
           that must move together (returning to a saved view changes the camera AND the pane layout) still make one. */
        if (!HOLD && hist && hist.commit) hist.commit();
        return r;
      },
      n:function(){ return n; },
      filed:function(){ return order.length; },
      value:function(k){ return side[k == null ? n : k]; },
      state:function(){ return {key:key, n:n, seq:seq, filed:order.length}; }
    };
  }
  /* Run several modules' steps as ONE history entry. Needed because returning to a saved view has to put back the
     camera (NMSKViews) and the pane layout (NMSKFourUp) together, and two nested steps would otherwise commit twice --
     which is the very defect this module exists to prevent. */
  function hold(fn){
    HOLD++;
    var r = null;
    try { r = fn(); }
    finally {
      HOLD--;
      if (!HOLD){
        for (var i = 0; i < HISTS.length; i++){ if (HISTS[i] && HISTS[i].commit){ HISTS[i].commit(); break; } }
      }
    }
    return r;
  }
  return {make:make, hold:hold, held:function(){ return HOLD > 0; }, max:function(){ return MAX; }};
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKStep;
