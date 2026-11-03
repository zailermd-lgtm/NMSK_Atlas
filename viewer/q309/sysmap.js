/* Q309: the map from this page's OWN tissue categories to anatomical SYSTEMS, and from each system to its depth strata.
   Owner (translated from Hebrew): "Also allow display by SYSTEMS with an on/off button, and by LAYERS -- for the whole
   body, per system, and for the displayed systems only."
   Nothing here is hard-coded: the table is `data/anatomy/system_layers_q309.json`, shipped in the page as
   <script id="nmsk-q309-layers">, and every system, every stratum and every count below is RESOLVED AGAINST THE PAGE.
   A system whose categories are absent is not offered; a stratum that matches nothing on this page is not offered; and
   a system fewer than half of whose structures land in a sourced stratum is offered NO peel at all -- the table's own
   `rule_peel_offered`, measured here rather than asserted there.
     NMSKSysMap.start({all:function(){ return [{id,cat,name}] }})
     .ready()  .systems()  .of(id)  .ids(sysKey)  .strata(sysKey)  .idsUpTo(sysKey, n)  .table()  .state() */
var NMSKSysMap = (function(){
  "use strict";
  var T = null, SYS = [], BY = {}, on = false, E = null;
  function read(){
    var el = document.getElementById("nmsk-q309-layers");
    if (!el) return null;
    try { var t = JSON.parse(el.textContent || "{}"); return (t && t.systems) ? t : null; } catch (e){ return null; }
  }
  function rx(s){ try { return s ? new RegExp(s, "i") : null; } catch (e){ return null; } }
  function hit(st, x){
    if (st.rest) return true;
    if (st.cats && st.cats.indexOf(x.cat) < 0) return false;
    if (st._r && !st._r.test(x.name || "")) return false;
    return true;
  }
  var api = {
    start:function(eng){
      if (on) return api;
      E = eng || null;
      T = read();
      if (!T || !E || typeof E.all !== "function") return api;
      var all = E.all() || [];
      T.systems.forEach(function(sp){
        var mine = all.filter(function(x){ return sp.cats.indexOf(x.cat) >= 0; });
        if (!mine.length) return;                                /* this page does not carry the system at all */
        var left = mine.slice(), strata = [], sourced = 0;
        (sp.strata || []).forEach(function(stp){
          var st = {key:stp.key, label:stp.label, he:stp.he, basis:stp.basis || "none", cite:stp.cite || "",
                    rest:!!stp.rest, cats:stp.cats || null, re:stp.re || "", _r:rx(stp.re)};
          var got = [], rest = [];
          left.forEach(function(x){ (hit(st, x) ? got : rest).push(x); });
          left = rest;
          if (!got.length) return;                               /* nothing on THIS page belongs to that stratum */
          st.ids = got.map(function(x){ return x.id; });
          st.n = got.length;
          if (st.basis !== "none") sourced += got.length;
          strata.push(st);
        });
        /* the table's own rule, applied to the measured counts of THIS page */
        var peel = strata.length > 1 && sourced * 2 >= mine.length;
        var S = {key:sp.key, label:sp.label, he:sp.he, cats:sp.cats.slice(),
                 ids:mine.map(function(x){ return x.id; }), n:mine.length,
                 strata:peel ? strata : [], sourced:sourced, peel:peel,
                 why:peel ? "" : (strata.length <= 1
                   ? "this system has no depth ordering we can source, so it offers on / off only"
                   : "fewer than half of this system's structures on this page land in a stratum we can source ("
                     + sourced + " of " + mine.length + "), so it offers on / off only")};
        SYS.push(S); BY[S.key] = S;
        mine.forEach(function(x){ if (!api._o) api._o = {}; api._o[x.id] = S.key; });
      });
      on = SYS.length > 0;
      return api;
    },
    ready:function(){ return on; },
    table:function(){ return T; },
    systems:function(){ return SYS.map(function(s){ return {key:s.key, label:s.label, he:s.he, cats:s.cats.slice(),
      n:s.n, peel:s.peel, sourced:s.sourced, why:s.why,
      strata:s.strata.map(function(t){ return {key:t.key, label:t.label, he:t.he, n:t.n, basis:t.basis, cite:t.cite}; })}; }); },
    get:function(k){ return BY[k] || null; },
    of:function(id){ return (api._o && api._o[id]) || null; },
    ids:function(k){ return BY[k] ? BY[k].ids.slice() : []; },
    strata:function(k){ return BY[k] ? BY[k].strata.map(function(t){ return {key:t.key, label:t.label, n:t.n, basis:t.basis}; }) : []; },
    /* the ids of the first n strata of one system -- what a per-system peel at step n must hide */
    idsUpTo:function(k, n){
      var S = BY[k]; if (!S) return [];
      var out = [];
      S.strata.slice(0, Math.max(0, n | 0)).forEach(function(t){ t.ids.forEach(function(i){ out.push(i); }); });
      return out;
    },
    depth:function(k){ var S = BY[k]; return S ? S.strata.length : 0; },
    state:function(){ return {on:on, systems:SYS.length,
      peelable:SYS.filter(function(s){ return s.peel; }).map(function(s){ return s.key; }),
      counts:SYS.reduce(function(a, s){ a[s.key] = s.n; return a; }, {})}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKSysMap;
