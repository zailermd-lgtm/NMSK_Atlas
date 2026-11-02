/* Q300: one guard against "something is hidden and I cannot find the way back".
   Owner: "i selected an organ, isolate its environment, and then had difficulty to redo it to see everything."
   The benchmark's answer (BioDigital Human: "The Reset button is hidden by default but appears when one of the
   Explore Tools -- Hide, Isolate, or Fade -- has been used") is the model here, widened to EVERY path on our pages
   that can make a structure vanish. The page registers one descriptor per such path; this module then
     - draws a persistent chip per ACTIVE path at the 3-D view's bottom-left corner, each with its own  x  that
       exits only that path ("isolated: Femur  x", "solo: muscle  x", "hidden: 23  x", "cut  x", "side: right  x");
     - shows ONE "Show everything" button, and only while at least one path is active -- zero chrome otherwise;
     - binds Escape (desktop) to the same "show everything", BEFORE the engines' own Escape-deselects, so the key
       that gets you unstuck is always the first thing Escape does; a second Escape then deselects as before;
     - makes every exit, single or all, exactly ONE undo step (commit before, commit after).
   A descriptor is {key, label(), active(), clear(), drive()} -- label() is only read while active() is true, and the
   optional drive() puts that one path into its active state, which is how verify_q300.py walks every path on the page
   and proves each one has a way out (one place per path, not a second list that could fall behind this one).
     NMSKShowAll.start({sources:[...], anchor, history, busy, phone})
     .refresh()  .active()  .chips()  .clearAll()  .clearOne(key)  .drive(key)  .state() */
var NMSKShowAll = (function(){
  "use strict";
  var S = [], bar = null, allBtn = null, anchor = null, hist = null, busy = null, on = false, sig = "", tmr = 0;
  function okActive(s){ try { return !!s.active(); } catch (err){ return false; } }
  function okLabel(s){ try { return String(s.label() == null ? s.key : s.label()); } catch (err){ return s.key; } }
  function live(){ return S.filter(okActive); }
  function anyActive(){ return S.some(okActive); }
  function step(fn){                                     // one undo step: settle what came before, act, settle again
    if (hist && hist.commit) hist.commit();
    try { fn(); } catch (err){ if (window.console) console.error("showall", err); }
    if (hist && hist.commit) hist.commit();
    render();
  }
  function clearOne(key){
    var s = null;
    S.forEach(function(q){ if (q.key === key) s = q; });
    if (!s || !okActive(s)) return false;
    step(function(){ s.clear(); });
    return true;
  }
  function clearAll(){
    if (!anyActive()) return false;
    step(function(){ live().forEach(function(s){ try { s.clear(); } catch (err){} }); });
    var left = live();
    say(left.length ? "Still hidden: " + left.map(okLabel).join(", ") + "." : "Everything is shown again (Undo brings it back).");
    return true;
  }
  function say(m){
    var e = document.getElementById("hist-msg");           // the Q294 history's own one-line notice: one place for these, never two
    if (!e || !m) return;
    e.textContent = m; e.hidden = false;
    clearTimeout(say.t); say.t = setTimeout(function(){ e.hidden = true; }, 2600);
  }
  var XSVG = '<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>';
  function render(){
    if (!on || !bar) return;
    var L = live(), s = L.map(function(x){ return x.key + "\u0001" + okLabel(x); }).join("\u0002");
    if (s === sig) return;                                 // nothing visible changed: no DOM churn (this runs on a timer)
    sig = s;
    bar.innerHTML = "";
    bar.hidden = !L.length;
    if (!L.length){ if (allBtn) allBtn.hidden = true; return; }
    L.forEach(function(x){
      var c = document.createElement("span");
      c.className = "sa-chip"; c.setAttribute("data-sa", x.key);
      var t = document.createElement("span"); t.className = "sa-t"; t.textContent = okLabel(x); c.appendChild(t);
      var b = document.createElement("button");
      b.type = "button"; b.className = "sa-x"; b.innerHTML = XSVG;
      b.title = "Undo this one: " + okLabel(x); b.setAttribute("aria-label", b.title);
      b.addEventListener("click", function(e){ e.stopPropagation(); clearOne(x.key); });
      c.appendChild(b); bar.appendChild(c);
    });
    if (allBtn){
      allBtn.hidden = false;
      allBtn.title = "Show everything again: " + L.map(okLabel).join(", ") + " (one Undo step; Esc)";
      bar.appendChild(allBtn);
    }
  }
  function typing(t){ var g = t && t.tagName; return g === "INPUT" || g === "TEXTAREA" || g === "SELECT" || (t && t.isContentEditable); }
  function blocked(t){
    if (typing(t)) return true;
    if (busy){ try { if (busy()) return true; } catch (err){} }
    var m = document.querySelector(".modal.open, [role=dialog][open]");
    return !!m;
  }
  function onKey(e){
    if (!on || e.key !== "Escape" || e.altKey || e.ctrlKey || e.metaKey) return;
    if (blocked(e.target)) return;
    if (!anyActive()) return;                              // nothing is hidden: leave Escape to the page's own deselect
    clearAll();
    e.preventDefault(); e.stopImmediatePropagation();      // a SECOND Escape then reaches the deselect, as before
  }
  var api = {
    start:function(opt){
      opt = opt || {};
      if (on) return api;
      S = (opt.sources || []).filter(function(s){ return s && s.key && typeof s.active === "function" && typeof s.clear === "function"; });
      hist = opt.history || window.NMSKHistory || null; busy = opt.busy || null; anchor = opt.anchor || null;
      bar = document.createElement("div");
      bar.id = "sa-bar"; bar.className = "sa-bar"; bar.hidden = true;
      bar.setAttribute("role", "group"); bar.setAttribute("aria-label", "What is hidden now, and how to get it back");
      bar.setAttribute("aria-live", "polite");
      allBtn = document.createElement("button");
      allBtn.type = "button"; allBtn.id = "sa-all"; allBtn.className = "sa-all"; allBtn.hidden = true;
      allBtn.textContent = "Show everything";
      allBtn.addEventListener("click", function(e){ e.stopPropagation(); clearAll(); });
      document.body.appendChild(bar);
      window.addEventListener("keydown", onKey, true);
      var place = function(){
        if (!anchor || !anchor.getBoundingClientRect) return;
        var r = anchor.getBoundingClientRect(), h = bar.offsetHeight || 34;
        if (!(r.width > 40 && r.height > 40)) return;
        bar.style.left = Math.max(4, r.left + 8) + "px";
        bar.style.top = Math.max(4, Math.min(window.innerHeight - h - 4, r.bottom - h - 8)) + "px";
        bar.style.maxWidth = Math.max(120, r.width - 150) + "px";   // never runs under the Q294 undo / redo / reset group at the other corner
      };
      window.addEventListener("resize", place);
      setInterval(place, 700); setTimeout(place, 0);
      if (hist && hist.onChange) hist.onChange(function(){ render(); });
      tmr = setInterval(render, 450);                      // the engines change these flags without an event of their own
      on = true; render();
      return api;
    },
    /* Q301: a path owned by a MODULE rather than by the engine's glue (the render style, the depth peel, the fat)
       cannot be in a list built before it started, so it registers itself here, with the same descriptor. */
    add:function(s){
      if (!s || !s.key || typeof s.active !== "function" || typeof s.clear !== "function") return false;
      S = S.filter(function(q){ return q.key !== s.key; });
      S.push(s); sig = ""; render();
      return true;
    },
    refresh:render,
    active:anyActive,
    chips:function(){ return live().map(function(x){ return {key:x.key, label:okLabel(x)}; }); },
    clearAll:clearAll, clearOne:clearOne,
    drive:function(key){                                   // verification only: put one path into its active state
      var s = null;
      S.forEach(function(q){ if (q.key === key) s = q; });
      if (!s || typeof s.drive !== "function") return false;
      step(function(){ s.drive(); });
      return okActive(s);
    },
    keys:function(){ return S.map(function(s){ return s.key; }); },
    state:function(){ return {on:on, n:S.length, chips:api.chips()}; }
  };
  return api;
})();
