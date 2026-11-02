/* Q303: "what the user already chose" -- the one place that answers it, so every imaging-like mode centres on the same
   thing and nothing has to guess.
   Owner: "imaging should focus automatically on the area that was marked, or typed, earlier."
   The order is the owner's own, and nothing else is ever invented: marked set -> the selected structure / open card ->
   the structure the user picked out of a search result -> NOTHING (and then no mode ever moves the view).
   The engine is reached only through the adaptor E:
     boxOf(id) -> {min:[3], max:[3]} | null      marks() -> [id]        selectedId() -> id | null
     name(id) -> string                          has(id) -> bool
     NMSKTarget.start(E)
     .get()  -> null | {kind, ids, label, min, max, c, r, n, why}
     .noteSearchPick(id)   .forget()   .state() */
var NMSKTarget = (function(){
  "use strict";
  var E = null, on = false, pick = null, wired = false;
  var SEARCH_IDS = ["q", "search"];                 /* the own engine's box is #q, the Z engine's is #search */
  function searchText(){
    for (var i = 0; i < SEARCH_IDS.length; i++){
      var e = document.getElementById(SEARCH_IDS[i]);
      if (e && typeof e.value === "string" && e.value.trim()) return e.value.trim();
    }
    return "";
  }
  function box(ids){
    var mn = [1e30, 1e30, 1e30], mx = [-1e30, -1e30, -1e30], got = 0;
    ids.forEach(function(id){
      var b = null;
      try { b = E.boxOf(id); } catch (err){ b = null; }
      if (!b || !b.min || !b.max) return;
      got++;
      for (var i = 0; i < 3; i++){ if (b.min[i] < mn[i]) mn[i] = b.min[i]; if (b.max[i] > mx[i]) mx[i] = b.max[i]; }
    });
    if (!got) return null;
    var c = [0, 0, 0], r = 0;
    for (var k = 0; k < 3; k++){ c[k] = (mn[k] + mx[k]) / 2; r = Math.max(r, (mx[k] - mn[k]) / 2); }
    return {min:mn, max:mx, c:c, r:r, n:got};
  }
  function nameOf(id){ try { return E.name(id) || id; } catch (err){ return id; } }
  function has(id){ if (!id) return false; try { return !!E.has(id); } catch (err){ return false; } }
  /* The row the user taps in the result list is a real click on #list, which both engines own; a capture listener on the
     document sees it before either engine's own handler, so the pick is recorded even though the engines differ. It only
     counts as a SEARCH pick while the search box actually holds a query -- otherwise #list is just the structure list. */
  function wire(){
    if (wired) return;
    wired = true;
    document.addEventListener("click", function(ev){
      var box2 = document.getElementById("list");
      if (!box2 || !ev.target || !box2.contains(ev.target)) return;
      var q = searchText();
      if (!q) return;
      var el = ev.target, id = null, hops = 0;
      while (el && el !== box2 && hops++ < 8){
        if (el.getAttribute){
          id = el.getAttribute("data-id") || el.getAttribute("data-sid") || null;
          if (id) break;
        }
        el = el.parentNode;
      }
      if (!id){                                     /* a row without data-id: take whatever the engine selects next */
        var before = null;
        try { before = E.selectedId(); } catch (err){}
        setTimeout(function(){
          var now = null;
          try { now = E.selectedId(); } catch (err){}
          if (now && now !== before) pick = {id:now, q:searchText() || q, at:Date.now()};
        }, 60);
        return;
      }
      if (has(id)) pick = {id:id, q:q, at:Date.now()};
    }, true);
  }
  var api = {
    start:function(eng){
      if (on) return api;
      E = eng || null;
      if (!E || typeof E.boxOf !== "function") return api;
      wire();
      on = true;
      return api;
    },
    noteSearchPick:function(id, q){ if (has(id)) pick = {id:id, q:q || searchText(), at:Date.now()}; },
    forget:function(){ pick = null; },
    get:function(){
      if (!on) return null;
      var ms = [];
      try { ms = (E.marks() || []).filter(has); } catch (err){ ms = []; }
      if (ms.length){
        var b = box(ms);
        if (b) return {kind:"marked", ids:ms.slice(), n:b.n, label:ms.length === 1 ? nameOf(ms[0]) : (ms.length + " marked structures"),
                       min:b.min, max:b.max, c:b.c, r:b.r, why:"the marked set"};
      }
      var sid = null;
      try { sid = E.selectedId(); } catch (err2){ sid = null; }
      if (has(sid)){
        var b2 = box([sid]);
        if (b2) return {kind:"selected", ids:[sid], n:1, label:nameOf(sid), min:b2.min, max:b2.max, c:b2.c, r:b2.r,
                        why:"the structure whose card is open"};
      }
      if (pick && has(pick.id)){
        var b3 = box([pick.id]);
        if (b3) return {kind:"search", ids:[pick.id], n:1, label:nameOf(pick.id), min:b3.min, max:b3.max, c:b3.c, r:b3.r,
                        why:"the result you picked for “" + pick.q + "”"};
      }
      return null;
    },
    boxOfIds:box,
    state:function(){
      var t = api.get();
      return {on:on, search:pick ? {id:pick.id, q:pick.q} : null, query:searchText(),
              target:t ? {kind:t.kind, label:t.label, n:t.n, c:t.c.map(function(x){ return Math.round(x * 100) / 100; }),
                          r:Math.round(t.r * 100) / 100, ids:t.ids} : null};
    }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKTarget;
