/* Q305: nothing may end up unreachable.
   Q301 hit this twice in one round and the second time twice over: its own info drawer's header sat over the control
   bar and SWALLOWED Undo on a 390 px phone, Q300's "what is hidden" chip bar sat on Redo, and then the lift that fixed
   the chip bar put it on an open group's sheet, where it ate the fat toggle and two of six taps on the depth peel.
   Each time the symptom read as a broken product and the cause was one box on top of another. Each time the instrument
   that found it was `document.elementFromPoint` at the control's own centre -- so that instrument is a module now, it
   runs after every drop (a drop that covers a control is refused), and `verify_q305.py` fails on it.
     NMSKGuard.watch({id|sel, label})      add a control that must stay reachable
     NMSKGuard.bad()                       the watched controls whose centre belongs to something else, each with the
                                           tag / id / class of whatever is on top instead
     NMSKGuard.all()  .top(el)  .state() */
var NMSKGuard = (function(){
  "use strict";
  var W = [], checks = 0;
  function sig(e){
    if (!e) return "(nothing)";
    var s = e.tagName ? e.tagName.toLowerCase() : "?";
    if (e.id) s += "#" + e.id;
    var c = e.className && typeof e.className === "string" ? e.className.trim().split(/\s+/)[0] : "";
    if (c) s += "." + c;
    return s;
  }
  /* A control that is merely SCROLLED OUT of the panel it lives in is not covered -- the user scrolls to it, and
     every one of these panels scrolls. The first real-page run of verify_q305.py reported three such controls as
     unreachable (`t-lay3` and `btn-pose` "covered by canvas#view", and Restore layout itself): all three were simply
     below the fold of the open group's own scrolling body, whose scrollHeight was 441 against a 362 px viewport. So
     the test walks up to the nearest clipping ancestor and asks whether the control is inside ITS window. */
  function clipped(e){
    var r = e.getBoundingClientRect(), n = e.parentElement, cs;
    while (n && n !== document.body && n !== document.documentElement){
      try { cs = getComputedStyle(n); } catch (err){ return false; }
      if (cs.overflow !== "visible" || cs.overflowY !== "visible" || cs.overflowX !== "visible"){
        var q = n.getBoundingClientRect();
        if (r.bottom <= q.top + 1 || r.top >= q.bottom - 1 || r.right <= q.left + 1 || r.left >= q.right - 1) return true;
      }
      n = n.parentElement;
    }
    return false;
  }
  function visible(e){
    if (!e || !e.getBoundingClientRect) return false;
    var r = e.getBoundingClientRect();
    if (!(r.width >= 2 && r.height >= 2)) return false;
    if (r.right <= 0 || r.bottom <= 0 || r.left >= (window.innerWidth || 1) || r.top >= (window.innerHeight || 1)) return false;
    var cs = null;
    try { cs = getComputedStyle(e); } catch (err){ return true; }
    if (cs.visibility === "hidden" || cs.display === "none" || +cs.opacity === 0) return false;
    return !clipped(e);
  }
  /* reachable := the element at the control's centre IS the control, or lies inside it (an icon, a label, a span), or
     the control lies inside IT (a button inside the row that was measured). Anything else is something on top. */
  function reach(e){
    var r = e.getBoundingClientRect();
    var x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
    var t = null;
    try { t = document.elementFromPoint(x, y); } catch (err){ t = null; }
    if (!t) return {ok:false, top:"(nothing)", x:x, y:y};
    var ok = t === e || e.contains(t) || t.contains(e);
    return {ok:ok, top:sig(t), x:x, y:y};
  }
  var api = {
    watch:function(w){
      if (!w || (!w.id && !w.sel)) return false;
      W.push({id:w.id || "", sel:w.sel || "", label:w.label || w.id || w.sel, soft:!!w.soft});
      return true;
    },
    nodes:function(){
      var out = [];
      W.forEach(function(w){
        var list = [];
        if (w.id){ var e = document.getElementById(w.id); if (e) list = [e]; }
        else { try { list = [].slice.call(document.querySelectorAll(w.sel)); } catch (err){ list = []; } }
        list.forEach(function(e){ if (visible(e)) out.push({el:e, label:w.label, w:w}); });
      });
      return out;
    },
    hard:function(){ return api.bad().filter(function(b){ return !b.soft; }); },
    bad:function(){
      checks++;
      var out = [];
      api.nodes().forEach(function(n){
        var r = reach(n.el);
        if (!r.ok) out.push({label:n.label, id:n.el.id || sig(n.el), top:r.top, x:r.x, y:r.y, soft:!!n.w.soft});
      });
      return out;
    },
    all:function(){
      return api.nodes().map(function(n){ var r = reach(n.el); return {label:n.label, id:n.el.id || sig(n.el), ok:r.ok, top:r.top, x:r.x, y:r.y}; });
    },
    top:function(e){ return e ? reach(e) : null; },
    clipped:function(e){ return !!e && clipped(e); },
    watched:function(){ return W.map(function(w){ return w.label; }); },
    state:function(){ var b = api.bad(); return {watched:W.length, visible:api.nodes().length, checks:checks, bad:b}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKGuard;
