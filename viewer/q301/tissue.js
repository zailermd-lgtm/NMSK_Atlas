/* Q301: the tissue reference, taken from the page's OWN clinical layer -- no number is retyped here, and this file
   names none of them. The clinical layer (private, clinical/LICENSE_PRIVATE.md) already loads the reference the page
   ships beside it and, since this round, hands it over on the generic global the public page is allowed to know:
   `window.NMSKClinical.tissues()` resolves with it, and `NMSKClinical.mskSequences` says which three of its sequences
   are the MSK set. That keeps the numbers, the file name and the sequence names on the private side of the Q226
   boundary (tests/test_q226.py::test_public_templates_carry_only_the_generic_hook) and costs one fetch instead of two.
   What arrives is 33 tissue classes, each with a CT attenuation and MRI pools (PD / T1 / T2 at 1.5 T), each value
   carrying its own status ("verified" / "derived" / "secondary_checked" / "assumption" / "recalled_unverified"), plus
   the CT windows, the sequences and the rules that map a structure to a class. This module walks the rules and turns
   the real numbers into the three render styles' greys. The physics is standard and cited in
   docs/research/Q301_controls_and_render_styles.md 3:
     X-ray  : Beer-Lambert  I/I0 = exp(-SUM mu_i d_i), with mu/mu_water = 1 + CT/1000 (the definition of the unit).
     CT     : the window map  grey = clamp((v - (L - W/2)) / W, 0, 1)  with W / L from the reference's own windows.
     MRI    : spin echo  S = PD * (1 - exp(-TR/T1)) * exp(-TE/T2), summed over the class's pools, with TR / TE from the
              reference's own sequences and a fat pool scaled by its fat-suppression residual when the sequence is fatsat.
   The ONE number that is ours and not measured is d0, the path length per surface crossing (the 3-step strength): a
   surface atlas has no thickness along the ray. That is said in the info panel, not hidden.
     NMSKTissue.load(url)  -> Promise      .ready()  .classOf(cat, id, name, vt)  .mu(cls)  .ctGrey(cls, win)
     .mrGrey(cls, seq)     .windows()      .sequences()  .status(cls)  .provenance()  .state() */
var NMSKTissue = (function(){
  "use strict";
  var D = null, C = {}, RULES = [], W = {}, S = {}, G = {}, memo = {}, loading = null, err = null;
  function lc(s){ return String(s == null ? "" : s).toLowerCase().replace(/_/g, " "); }
  function build(j){
    D = j; C = {}; RULES = (j.mapping_rules && j.mapping_rules.rules) || [];
    (j.classes || []).forEach(function(c){ C[c.key] = c; });
    W = {}; (j.ct_windows || []).forEach(function(w){ W[w.key] = w; });
    S = {}; (j.mr_sequences || []).forEach(function(s){ S[s.key] = s; });
    G = j.mr_global || {};
    memo = {};
  }
  /* first matching rule wins -- the file's own note. cat / id / name are the viewer's, vt = Z-Anatomy's vein flag. */
  function classOf(cat, id, name, vt){
    if (!D) return "soft_unassigned";
    var k = cat + "\u0001" + id;
    if (memo[k]) return memo[k];
    var hay = lc(id) + " " + lc(name), out = "soft_unassigned";
    for (var i = 0; i < RULES.length; i++){
      var r = RULES[i];
      if (r.cat && r.cat.indexOf(cat) < 0) continue;
      if (r.vt && r.vt !== vt) continue;
      if (r.re){ var re; try { re = new RegExp(r.re); } catch (e){ continue; } if (!re.test(hay)) continue; }
      if (r.cls && C[r.cls]){ out = r.cls; break; }
    }
    memo[k] = out;
    return out;
  }
  function hu(cls){ var c = C[cls]; return c && c.ct && typeof c.ct.hu === "number" ? c.ct.hu : 40; }
  function mu(cls){ return Math.max(0.02, 1 + hu(cls) / 1000); }          /* relative to water: the HU definition */
  function ctGrey(cls, wk){
    var w = W[wk] || W.msk || W.soft; if (!w) return 0.5;
    var lo = w.level - w.width / 2;
    return Math.max(0, Math.min(1, (hu(cls) - lo) / w.width));
  }
  function mrGrey(cls, sk){
    var c = C[cls], s = S[sk]; if (!c || !c.mri || !s) return 0;
    var res = G.fat_suppression_residual == null ? 0.05 : G.fat_suppression_residual, tot = 0;
    (c.mri.pools || []).forEach(function(p){
      var f = p.frac == null ? 1 : p.frac;
      if (p.fat && s.fatsat) f *= res;
      var sig = p.pd == null ? 0 : p.pd;
      if (s.kind === "se" && p.t1 > 0 && p.t2 > 0) sig *= (1 - Math.exp(-s.tr / p.t1)) * Math.exp(-s.te / p.t2);
      tot += f * sig;
    });
    return Math.max(0, tot);
  }
  function status(cls){
    var c = C[cls]; if (!c) return "unknown";
    return (c.ct && c.ct.status) || "unknown";
  }
  var SEQ = [];
  var api = {
    /* the clinical layer owns the reference and its file name; this module only asks for it. It may not have
       attached yet when the control bar starts, so wait for the accessor rather than deciding it is absent. */
    load:function(){
      if (loading) return loading;
      loading = new Promise(function(res, rej){
        var t0 = Date.now();
        (function poll(){
          var cl = typeof window !== "undefined" ? window.NMSKClinical : null;
          if (cl && typeof cl.tissues === "function") return res(cl);
          if (Date.now() - t0 > 60000) return rej(new Error("no clinical layer on this page, so no tissue reference"));
          setTimeout(poll, 200);
        })();
      }).then(function(cl){
        SEQ = (cl.mskSequences || []).slice();
        return cl.tissues();
      }).then(function(j){ build(j); return api; }).catch(function(e){ err = String(e && e.message || e); throw e; });
      return loading;
    },
    /* which three sequences the private layer calls the MSK set, in its order */
    mskSequences:function(){ return SEQ.slice(); },
    adopt:build,                                       /* a page that already holds the object (tests, node) */
    ready:function(){ return !!D; }, error:function(){ return err; },
    classOf:classOf, mu:mu, hu:hu, ctGrey:ctGrey, mrGrey:mrGrey, status:status,
    keys:function(){ return Object.keys(C).sort(); },
    label:function(cls){ var c = C[cls]; return (c && c.label) || cls; },
    windows:function(){ return (D && D.ct_windows ? D.ct_windows : []).map(function(w){ return {key:w.key, label:w.label, width:w.width, level:w.level, note:w.note}; }); },
    sequences:function(){ return (D && D.mr_sequences ? D.mr_sequences : []).map(function(s){ return {key:s.key, label:s.label, tr:s.tr, te:s.te, fatsat:!!s.fatsat, note:s.note}; }); },
    honesty:function(){ return (D && D.honesty) || []; },
    /* how many classes sit at each verification status: the info panel states this instead of claiming "measured" */
    provenance:function(){
      var n = {}, ks = Object.keys(C);
      ks.forEach(function(k){ var s = status(k); n[s] = (n[s] || 0) + 1; });
      return {classes:ks.length, byStatus:n, verifiedOn:(D && D.verified_on) || null, title:(D && D.title) || null};
    },
    state:function(){ return {ready:!!D, classes:Object.keys(C).length, rules:RULES.length, windows:Object.keys(W).length, sequences:Object.keys(S).length, error:err}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKTissue;
