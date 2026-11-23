/* Q309: the map from this page's OWN tissue categories to anatomical SYSTEMS, and from each system to its depth strata.
   Owner (translated from Hebrew): "Also allow display by SYSTEMS with an on/off button, and by LAYERS -- for the whole
   body, per system, and for the displayed systems only."
   Nothing here is hard-coded: the table is `data/anatomy/system_layers_q309.json`, shipped in the page as
   <script id="nmsk-q309-layers">, and every system, every stratum and every count below is RESOLVED AGAINST THE PAGE.
   A system whose categories are absent is not offered; a stratum that matches nothing on this page is not offered; and
   a system fewer than half of whose structures land in a sourced stratum is offered NO peel at all -- the table's own
   `rule_peel_offered`, measured here rather than asserted there.
     NMSKSysMap.start({all:function(){ return [{id,cat,name}] }})
     .ready()  .systems()  .of(id)  .ids(sysKey)  .strata(sysKey)  .idsUpTo(sysKey, n)  .table()  .state()
     .layerOf(id)  .regions(sysKey)   (Q391: a system layered region by region) */
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
  /* Q391, owner (translated from Hebrew): "The division into levels in one system does not necessarily match the levels
     of another system. For the muscles, for example, it is a MUST to work by the known layers." A system with `regions`
     is layered BY REGION: each region lists its textbook layers outermost first, each layer one or more groups (a regex
     over the displayed name, its basis and its page). A structure takes the first group it matches; stratum n of the
     system is layer n of every region, and what no group reaches is one last stratum with no source, named so. */
  var LAY = {}, REG = {};
  function byRegion(sp, mine, addSourced){
    var regs = [], maxL = 0;
    sp.regions.forEach(function(r){
      var R = {key:r.key, label:r.label, he:r.he, layers:[]};
      (r.layers || []).forEach(function(l){
        R.layers.push({label:l.label, he:l.he, ids:[], groups:(l.groups || []).map(function(g){
          return {_r:rx(g.re), cats:g.cats || null, basis:g.basis || "none", cite:g.cite || "", note:g.note || ""}; })});
      });
      maxL = Math.max(maxL, R.layers.length);
      regs.push(R);
    });
    var per = [], rest = [], conv = [];
    for (var i = 0; i < maxL; i++){ per.push([]); conv.push(0); }
    mine.forEach(function(x){
      for (var a = 0; a < regs.length; a++){
        for (var b = 0; b < regs[a].layers.length; b++){
          var L = regs[a].layers[b];
          for (var c = 0; c < L.groups.length; c++){
            var G = L.groups[c];
            if (G.cats && G.cats.indexOf(x.cat) < 0) continue;
            if (!G._r || !G._r.test(x.name || "")) continue;
            L.ids.push(x.id); per[b].push(x.id);
            if (G.basis === "literature") addSourced(1); else conv[b]++;
            LAY[x.id] = {system:sp.key, region:regs[a].key, regionLabel:regs[a].label, layer:b + 1, of:regs[a].layers.length,
              layerLabel:L.label, basis:G.basis, cite:G.cite, note:G.note};
            return;
          }
        }
      }
      rest.push(x.id);
    });
    REG[sp.key] = regs.map(function(R){
      return {key:R.key, label:R.label, he:R.he, n:R.layers.reduce(function(s, l){ return s + l.ids.length; }, 0),
        layers:R.layers.map(function(l, i){ return {n:i + 1, label:l.label, he:l.he, ids:l.ids.slice()}; })};
    }).filter(function(R){ return R.n > 0; });
    var out = [];
    per.forEach(function(ids, i){
      if (!ids.length) return;
      out.push({key:"L" + (i + 1), label:i ? "Layer " + (i + 1) + " of its region" : "Outermost layer of its region",
        he:i ? "שכבה " + (i + 1) + " באזורה" : "השכבה החיצונית באזורה",
        basis:conv[i] ? "mixed" : "literature", cite:"by region", ids:ids, n:ids.length});
    });
    if (rest.length) out.push({key:"rest", label:"No sourced layer", he:"ללא שכבה ממוקרת",
      basis:"none", cite:"", ids:rest, n:rest.length});
    return out;
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
        if (sp.regions){ strata = byRegion(sp, mine, function(n){ sourced += n; }); left = []; }
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
    /* Q391: where one structure sits in its system's regional layers -- {system, region, regionLabel, layer, of,
       layerLabel, basis, cite, note}, or null when no sourced group reaches it */
    layerOf:function(id){ return LAY[id] || null; },
    /* Q391: the regions of a system layered by region, in the table's order, each with its layers outermost first */
    regions:function(k){ return (REG[k] || []).map(function(R){ return {key:R.key, label:R.label, he:R.he, n:R.n,
      layers:R.layers.map(function(l){ return {n:l.n, label:l.label, he:l.he, ids:l.ids.slice()}; })}; }); },
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
    /* the ids of ONE stratum, by index -- verification reads it so the check can measure what a step removes */
    stratumIds:function(k, i){
      var S = BY[k]; if (!S || !S.strata[i | 0]) return [];
      return S.strata[i | 0].ids.slice();
    },
    state:function(){ return {on:on, systems:SYS.length,
      peelable:SYS.filter(function(s){ return s.peel; }).map(function(s){ return s.key; }),
      counts:SYS.reduce(function(a, s){ a[s.key] = s.n; return a; }, {})}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKSysMap;
