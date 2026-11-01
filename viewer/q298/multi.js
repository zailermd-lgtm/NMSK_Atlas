/* Q298 multi-select. The per-row tick (NMSKSelect.markButton) and the model-side Shift/Ctrl-click, long press and Mark
   mode have existed since Q227 -- what was missing is marking MANY at once in one action, and any sign that the model-side
   modifier exists at all. This module adds:
     "Mark all N"      every structure the current search matched, in ONE undo step (not the 260 / 400 the list truncates to)
     "Range"           tap the first row then the last: the whole run between them is marked in one step.
                       On a desktop Shift-click on a row's tick does the same without arming anything; on a phone a long
                       press on a row arms the range and the next tap closes it.
     "On model"        drives the engine's own Mark-mode button (#t-mark), so the model-side multi-pick is discoverable.
   Every batch goes through NMSKSelect.markIds(ids, true, false), which takes one undo snapshot for the whole batch. */
function NMSKMulti(E, BAR, H){
  "use strict";
  var say = H.say, rangeArmed = false, anchor = null, LP_MS = 520, lp = null, rows = [];

  function sel(){ return E.sel(); }

  function markIds(ids, what, src, inferred, why){
    var s = sel();
    if (!s){ say("The marked-structures panel is not available on this page."); return 0; }
    var n = s.markIds(ids, true, false, true);
    say(n + (n === 1 ? " structure" : " structures") + " added from " + what + " — " + ids.length +
        " offered, " + n + " newly marked. One undo step (Ctrl/Cmd+Z)." +
        (src ? " Source: " + src + "." : "") + (inferred ? " INFERRED: " + (why || "a rule of this project, not a cited list.") : ""));
    E.rerender();
    return n;
  }

  function markAllResults(res){
    if (!res || !res.ids.length) return;
    markIds(res.ids, 'the search "' + res.q + '"', null, 0, null);
  }

  function toggleRange(){
    rangeArmed = !rangeArmed; anchor = null;
    BAR.pressed("q8-range", rangeArmed);
    say(rangeArmed ? "Range: tap the first row, then the last one." : "Range off.");
  }
  function toggleOnModel(){
    var b = document.getElementById("t-mark") || document.getElementById("sel-markmode");
    if (!b){ say("This page has no Mark-mode button."); return; }
    b.click();
    var on = b.getAttribute("aria-pressed") === "true";
    BAR.pressed("q8-onmodel", on);
    say(on ? "On model: every click or tap on a structure adds it to the marked set. Shift / Ctrl-click and a long press do the same at any time."
           : "On model off. Shift / Ctrl-click, or a long press on a phone, still adds on the model.");
  }

  function range(a, b){
    var i = rows.indexOf(a), j = rows.indexOf(b);
    if (i < 0 || j < 0) return null;
    if (i > j){ var t = i; i = j; j = t; }
    return rows.slice(i, j + 1);
  }

  function closeRange(id){
    var ids = range(anchor, id);
    anchor = null;
    if (rangeArmed){ rangeArmed = false; BAR.pressed("q8-range", false); }
    if (!ids){ say("Those rows are not both in the list any more."); return; }
    markIds(ids, "the range of " + ids.length + " rows", null, 0, null);
  }

  /* called after every list render with the ids of the rows now in the DOM, in order */
  function wire(shownIds){
    rows = shownIds.slice();
    var list = E.list();
    if (!list) return;
    var kids = list.querySelectorAll(".ss-lrow");
    Array.prototype.forEach.call(kids, function(w, n){
      if (w.getAttribute("data-q8") === "1") return;
      w.setAttribute("data-q8", "1");
      var id = rows[n];
      if (id == null) return;
      w.setAttribute("data-q8id", id);
      var tick = w.querySelector(".ss-mk");
      if (tick){
        tick.addEventListener("click", function(ev){
          if (ev.shiftKey && anchor != null && anchor !== id){ ev.preventDefault(); ev.stopImmediatePropagation(); closeRange(id); return; }
          anchor = id;
        }, true);
      }
      w.addEventListener("click", function(){
        if (rangeArmed){
          if (anchor == null){ anchor = id; say("Range start: " + id + ". Now tap the last row."); }
          else closeRange(id);
        } else anchor = id;
      });
      w.addEventListener("pointerdown", function(ev){
        if (ev.pointerType === "mouse") return;
        if (lp){ clearTimeout(lp.t); lp = null; return; }
        lp = {x:ev.clientX, y:ev.clientY, t:setTimeout(function(){
          lp = null; rangeArmed = true; anchor = id; BAR.pressed("q8-range", true);
          say("Range armed on this row — tap another row to mark everything between them.");
          try { if (navigator.vibrate) navigator.vibrate(18); } catch (err){}
        }, LP_MS)};
      });
      w.addEventListener("pointermove", function(ev){ if (lp && Math.abs(ev.clientX - lp.x) + Math.abs(ev.clientY - lp.y) > 9){ clearTimeout(lp.t); lp = null; } });
      w.addEventListener("pointerup", function(){ if (lp){ clearTimeout(lp.t); lp = null; } });
    });
  }

  return {wire:wire, markIds:markIds, markAllResults:markAllResults, toggleRange:toggleRange, toggleOnModel:toggleOnModel,
          state:function(){ return {rangeArmed:rangeArmed, anchor:anchor, rows:rows.length}; }};
}
