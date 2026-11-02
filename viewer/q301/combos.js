/* Q301: which actions can be combined, which cannot -- and both made visible.
   Owner: "actions that CAN be combined, like CUT and IMAGING, must be visibly combinable; and the ones that cannot must
   be visibly not."
   One table, one place. The rule behind it: two actions are COMPATIBLE when each writes a different piece of state and
   both can be seen at once; they are INCOMPATIBLE when they write the same piece of state, or when one empties the
   other's input. Every row was checked in a real browser by scripts/anatomy/q301/verify_q301.py -- the matrix is not a
   guess, and the row's `why` is what the user is shown, in one line, next to the control that is switched off.
   A page registers one probe per action: {key, label, active()}. Nothing here knows what an action does.
     NMSKCombos.start({probes:[...]})  .verdict(key)  .matrix()  .pairs()  .refresh()  .onChange(fn)  .state() */
var NMSKCombos = (function(){
  "use strict";
  var P = {}, hooks = [], on = false, sig = "";
  /* Three kinds of row. ok:false = cannot be combined, and `why` is the one line the user sees next to the control that
     is switched off. ok:true = worth SAYING they combine (the owner's cut + imaging among them). ok:"over" = both are
     allowed and one quietly takes precedence over the other, which must be said rather than silently disabling either:
     Q300 ships its bone pass ON (Clear) on the Imaging pages, so treating it as incompatible would have left the X-ray
     style disabled the moment those pages loaded. A pair not in the table is simply compatible, and silent. */
  var PAIRS = [
    {a:"cut",      b:"imaging",  ok:true,  why:"Cut and the radiographic styles work together: the cut face is drawn in the style's own grey."},
    {a:"xsec",     b:"imaging",  ok:true,  why:"A cross-section takes the radiographic style too."},
    {a:"cut",      b:"measure",  ok:true,  why:"Measure works on a cut model."},
    {a:"cut",      b:"peel",     ok:true,  why:"Peeling layers and cutting are independent."},
    {a:"imaging",  b:"peel",     ok:true,  why:"Peeling decides what is left; the style decides how it is drawn."},
    {a:"imaging",  b:"fat",      ok:true,  why:"Fat takes the style like every other tissue."},
    {a:"imaging",  b:"srccolour",ok:false, why:"A radiographic style replaces the colour, so colour-by-source has nothing left to colour."},
    {a:"imaging",  b:"highlight",ok:false, why:"A highlight colour does not exist in a greyscale picture — use Fade others instead."},
    {a:"imaging",  b:"boneread", ok:"over", over:"imaging",
     why:"A radiographic style sets the bone's brightness from its own attenuation, so Q300's extra bone pass is paused while a style is on \u2014 it comes back with the colour."},
    {a:"peel",     b:"preset",   ok:false, why:"Both write the same layer table — turning one on turns the other off."},
    {a:"peel",     b:"solo",     ok:false, why:"Both write the same layer table — turning one on turns the other off."},
    {a:"spin",     b:"measure",  ok:false, why:"Stop the spin first, or the model moves while you are placing the point."},
    {a:"spin",     b:"cutplace", ok:false, why:"Stop the spin first, or the model moves while you are placing the plane."},
    {a:"marktap",  b:"cutplace", ok:false, why:"Both take over the next tap on the model — only one can have it."}
  ];
  function live(k){ var p = P[k]; if (!p) return false; try { return !!p.active(); } catch (e){ return false; } }
  function lab(k){ var p = P[k]; return (p && p.label) || k; }
  function verdict(key){
    var out = {key:key, active:live(key), disabled:false, reason:"", with:[], blockedBy:null};
    var over = null;
    PAIRS.forEach(function(r){
      var other = r.a === key ? r.b : (r.b === key ? r.a : null);
      if (!other || !P[other] || !live(other)) return;
      if (r.ok === "over"){
        if (out.active || live(other)) over = r;                 /* say which of the two is in charge, disable neither */
        if (out.active) out.with.push(lab(other));
      } else if (r.ok){ if (out.active) out.with.push(lab(other)); }
      else if (!out.active){ out.disabled = true; out.reason = r.why; out.blockedBy = other; }
    });
    if (out.active && out.with.length) out.reason = "Active together with " + out.with.join(", ") + ".";
    if (over && (out.active || live(over.a === key ? over.b : over.a))){
      out.overridden = (over.over !== key);                      /* this one is the one giving way */
      out.reason = over.why;                                     /* the row's own words, not the generic line */
    }
    return out;
  }
  function stamp(){ return Object.keys(P).sort().map(function(k){ return k + (live(k) ? "1" : "0"); }).join(","); }
  function refresh(){
    var s = stamp();
    if (s === sig) return false;
    sig = s;
    hooks.forEach(function(f){ try { f(); } catch (e){} });
    return true;
  }
  var api = {
    start:function(opt){
      opt = opt || {};
      if (on) return api;
      (opt.probes || []).forEach(function(p){ if (p && p.key && typeof p.active === "function") P[p.key] = p; });
      on = true; sig = ""; setInterval(refresh, 450); refresh();
      return api;
    },
    add:function(p){ if (p && p.key && typeof p.active === "function"){ P[p.key] = p; sig = ""; refresh(); } },
    verdict:verdict, refresh:refresh,
    keys:function(){ return Object.keys(P).sort(); },
    pairs:function(){ return PAIRS.map(function(r){ return {a:r.a, b:r.b, ok:r.ok, why:r.why}; }); },
    /* the table for the info panel and for the tests: only the pairs whose BOTH sides exist on this page */
    matrix:function(){
      return PAIRS.filter(function(r){ return P[r.a] && P[r.b]; })
        .map(function(r){ return {a:lab(r.a), b:lab(r.b), ok:r.ok, over:r.over || null, why:r.why, aKey:r.a, bKey:r.b}; });
    },
    onChange:function(f){ if (typeof f === "function") hooks.push(f); },
    active:function(){ return Object.keys(P).filter(live).sort(); },
    state:function(){ return {on:on, probes:Object.keys(P).length, pairs:PAIRS.length, onPage:api.matrix().length, active:api.active()}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKCombos;
