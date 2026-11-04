/* Q309: the boot. One call per page from each engine's glue; everything engine-specific is in the adaptor the glue
   passes in, so the two engines behave identically and this file is the only place the round's wiring lives.
   Owner (translated from Hebrew): "Also allow display by SYSTEMS with an on/off button, and by LAYERS -- for the whole
   body, per system, and for the displayed systems only."
   What this round adds, and what it deliberately does not:
     * NMSKSysToggle -- one plain on/off button per system, with its own structure count.   (request 1)
     * the whole-body peel is Q301's NMSKPeel, UNTOUCHED. This round drives it; it does not rebuild it.   (request 2)
     * NMSKSysPeel -- the same taps with a SCOPE: one system, or exactly the systems switched on.   (request 3)
   Both new controls go into Q301's EXISTING "Layers" group through NMSKGroups.addTo, not as new top-level buttons.
   The whole round is ONE history provider, so any change is ONE undo step; it registers two paths with Q300's
   "Show everything"; and the model reset returns it because the provider has a reset() of its own.
     NMSKQ309.start({engine:E, anchor, history, showall, peel})
     .ready()  .systems()  .state() */
var NMSKQ309 = (function(){
  "use strict";
  var on = false, E = null, O = null, hist = null, LASTN = 0;
  function esc(s){ return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  /* ONE write to the engine: the systems switched off and the scoped peel are two components of one veto set, so the
     engine never sees two writers and a structure vetoed by both comes back only when both release it. */
  function push(){
    if (!E || !E.off) return;
    var out = [], seen = {};
    [window.NMSKSysToggle, window.NMSKSysPeel].forEach(function(m){
      if (!m || !m.ids) return;
      try { m.ids().forEach(function(i){ if (!seen[i]){ seen[i] = 1; out.push(i); } }); } catch (e){}
    });
    LASTN = out.length;
    try { E.off(out); } catch (e2){ if (window.console) console.error("q309", e2); }
    if (E.redraw){ try { E.redraw(); } catch (e3){} }
  }
  function infoSection(){
    var I = window.NMSKInfo, M = window.NMSKSysMap;
    if (!I || !M || !M.ready()) return;
    I.add({key:"q309", title:"Systems, and what a layer means inside one", order:45, build:function(){
      var T = M.table() || {}, src = T.sources || {}, conv = T.conventions || [];
      var out = "<p>This page carries <b>" + M.systems().length + " systems</b>. Each has one <b>on / off</b> button " +
        "with its own structure count, and a system switched off is a veto of its own &mdash; it does not write the " +
        "tissue-layer table, so it combines with the layer rows, the presets and every depth peel.</p>" +
        "<p>The depth peel has <b>three scopes</b>: the whole body (Q301's own control, driven from the same taps), " +
        "one chosen system, or exactly the systems switched on. " + esc(T.rule_peel_offered || "") + "</p>" +
        "<table><tr><th>system</th><th>on this page</th><th>its layers, outside&nbsp;in</th><th>where the order comes from</th></tr>";
      M.systems().forEach(function(s){
        out += "<tr><td>" + esc(s.label) + "</td><td class=mono>" + s.n + "</td><td>" +
          (s.peel ? s.strata.map(function(t){ return esc(t.label) + " <span class=mono>" + t.n + "</span>"; }).join(" &rarr; ")
                  : "<i>" + esc(s.why) + "</i>") + "</td><td>" +
          (s.peel ? s.strata.map(function(t){
             return t.basis === "none" ? "<b>no source</b>"
               : t.basis === "data" ? "this project's own data"
               : t.basis === "mixed" ? "literature + this project's own groups" : "literature"; })
             .filter(function(v, i, a){ return a.indexOf(v) === i; }).join(", ") : "&mdash;") + "</td></tr>";
      });
      out += "</table><p><b>What in it is ours, not anatomy.</b></p><ul>" +
        conv.map(function(c){ return "<li>" + esc(c) + "</li>"; }).join("") + "</ul>" +
        "<p><b>Sources.</b></p><ul>" + Object.keys(src).sort().map(function(k){
          return "<li><b>" + esc(k) + "</b> &mdash; " + esc(src[k]) + "</li>"; }).join("") + "</ul>" +
        "<p>The whole table is <code>data/anatomy/system_layers_q309.json</code>, shipped in this page; nothing in the " +
        "viewer retypes a stratum or a count, and a stratum that matches nothing on this page is not offered.</p>";
      return out;
    }});
  }
  var api = {
    start:function(opt){
      opt = opt || {};
      if (on) return api;
      O = opt; E = opt.engine || null;
      if (!E || typeof E.off !== "function" || typeof E.all !== "function") return api;
      hist = opt.history || window.NMSKHistory || null;
      var sa = opt.showall || window.NMSKShowAll || null;
      if (!window.NMSKSysMap) return api;
      NMSKSysMap.start(E);
      if (!NMSKSysMap.ready()) return api;
      if (window.NMSKSysToggle) NMSKSysToggle.start(E, {map:NMSKSysMap, history:hist, push:push});
      if (window.NMSKSysPeel) NMSKSysPeel.start(E, {map:NMSKSysMap, toggle:window.NMSKSysToggle,
        peel:opt.peel || window.NMSKPeel, history:hist, push:push});
      /* ONE provider for the whole round: a change to a system switch or to the scoped peel is one undo step */
      if (hist && hist.register) hist.register("q309", {
        get:function(){
          return ((window.NMSKSysToggle && NMSKSysToggle.get) ? NMSKSysToggle.get() : "") + ";" +
                 ((window.NMSKSysPeel && NMSKSysPeel.get) ? NMSKSysPeel.get() : "");
        },
        set:function(v){
          var p = String(v == null ? ";" : v).split(";");
          if (window.NMSKSysToggle && NMSKSysToggle.put) NMSKSysToggle.put(p[0] || "");
          if (window.NMSKSysPeel && NMSKSysPeel.put) NMSKSysPeel.put(p[1] || "body||0");
        },
        reset:function(){
          if (window.NMSKSysToggle && NMSKSysToggle.put) NMSKSysToggle.put("");
          if (window.NMSKSysPeel && NMSKSysPeel.put) NMSKSysPeel.put("body||0");
        }
      });
      if (sa && sa.add){
        if (window.NMSKSysToggle && NMSKSysToggle.state().on) sa.add(NMSKSysToggle.source());
        if (window.NMSKSysPeel && NMSKSysPeel.state().on) sa.add(NMSKSysPeel.source());
      }
      var C = window.NMSKCombos;
      if (C && C.addPair){
        C.addPair({a:"System on / off", b:"Depth peel", ok:true, why:"a system switched off is its own veto; the peel decides how deep, the switch which systems"});
        C.addPair({a:"Depth peel", b:"Scoped depth peel", ok:false, why:"one depth control at a time -- the scope decides which, and changing the scope puts the other's layers back"});
      }
      /* into Q301's OWN "Layers" group: short menus, progressive disclosure, no new top-level button */
      var G = window.NMSKGroups;
      if (G && G.addTo){
        if (window.NMSKSysToggle && NMSKSysToggle.element()) G.addTo("layers", {el:NMSKSysToggle.element()});
        if (window.NMSKSysPeel && NMSKSysPeel.element()) G.addTo("layers", {el:NMSKSysPeel.element()});
      }
      infoSection();
      if (window.NMSKTips && NMSKTips.fold){ try { NMSKTips.fold(); } catch (err){} }
      if (window.NMSKInfo && NMSKInfo.refresh){ try { NMSKInfo.refresh(); } catch (e4){} }
      on = true;
      push();
      return api;
    },
    ready:function(){ return on; },
    push:push,
    systems:function(){ return window.NMSKSysMap ? NMSKSysMap.systems() : []; },
    /* verification only: the measured counts this round's claims rest on */
    measure:function(){
      var M = window.NMSKSysMap;
      if (!M || !M.ready() || !E) return null;
      return {drawn:E.drawn ? E.drawn() : -1,
        bySystem:M.systems().reduce(function(a, s){
          a[s.key] = {n:s.n, drawn:E.drawnIn ? E.drawnIn(s.cats) : -1,
            strata:s.strata.map(function(t, i){
              return {key:t.key, n:t.n, drawn:E.drawnOf ? E.drawnOf(M.stratumIds(s.key, i)) : -1};
            })};
          return a;
        }, {}),
        vetoed:LASTN};
    },
    state:function(){ return {on:on,
      map:window.NMSKSysMap ? NMSKSysMap.state() : null,
      toggle:window.NMSKSysToggle ? NMSKSysToggle.state() : null,
      peel:window.NMSKSysPeel ? NMSKSysPeel.state() : null,
      wholebody:window.NMSKPeel ? NMSKPeel.state() : null}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKQ309;
