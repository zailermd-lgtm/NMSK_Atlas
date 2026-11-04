/* Q301: ONE control that peels the body inward, layer by layer, alongside the per-system controls that stay as they were.
   Owner: "the various sliders for body structures should also allow GRADUAL REVEAL BY LAYERS, not only by systems, plus
   whatever else is conventional -- check other sites and atlases."
   The benchmark (docs/research/Q301_controls_and_render_styles.md 4): Zygote Body has one control that "removes layers,
   beginning with the skin and continuing until all users see is a few nerves", "working inward towards the skeleton";
   Primal Pictures does it with "Layer up" / "Layer down" buttons "plus a layer number", in five layers "from deep to
   superficial". We take Primal's TAPS and visible layer number (the project's taps-over-sliders rule, and Q300's
   "a state that is not on the screen is a state you can hide by accident") and Zygote's skin-inward order.
   The order is derived from the page's OWN categories, and it is the owner's own order:
     1 skin  2 fat / superficial fascia  3 deep fascia / septa / aponeuroses + bursa  4 muscle + tendon + insertion
     5 ligament + joint  6 vessel + nerve + lymph  7 viscera + cns   -> what is left is bone + cartilage.
   Step 2 IS the superficial fascia, by the structures' own Latin names: 17 of Q295's 51 subcutaneous-fat meshes are
   labelled `Panniculus adiposus (tela subcutanea)`, which is the superficial fascia in the modern sense. What the atlas
   does NOT carry is a separate MEMBRANOUS (Scarpa's) layer, and the pages' own search data already says so in as many
   words: "No page ships it as a mesh: the abdominal wall on these pages carries `Investing abdominal fascia` and the
   subcutaneous fat, not a separate membranous layer." Step 3 holds the 61 investing-fascia sheets, septa and
   aponeuroses (fascia lata, brachial, crural, thoracolumbar, plantar and palmar aponeuroses, ...).
   One grouping IS ours: vessels, nerves and lymphatics come off together, because the data carries no depth rank per
   vessel and real vessels cross every layer.
   The engine supplies E: {cats() -> [key], count(key) -> n, off(keys) (hide exactly these, restoring the rest), redraw()}.
     NMSKPeel.start(E, {toolbar, history, showall})
     .step()  .set(i)  .deeper()  .shallower()  .steps()  .hidden()  .state() */
var NMSKPeel = (function(){
  "use strict";
  var E = null, hist = null, box = null, out = null, on = false, i0 = 0, idx = 0, upB = null, dnB = null, allB = null;
  var ORDER = [
    {key:"skin",    label:"Skin",            cats:["skin"]},
    {key:"fat",     label:"Fat / superficial fascia", cats:["fat"]},
    {key:"fascia",  label:"Deep fascia",     cats:["fascia", "bursa"]},
    {key:"muscle",  label:"Muscle",          cats:["muscle", "tendon", "insertion"]},
    {key:"ligament",label:"Ligament",        cats:["ligament", "joint"]},
    {key:"neurovas",label:"Vessels & nerves",cats:["vessel", "nerve", "lymph", "lymphatic"]},
    {key:"viscera", label:"Organs",          cats:["viscera", "organ", "cns"]}
  ];
  function present(){                                     /* only the steps this page really has something to peel */
    var cs = {}; (E && E.cats ? E.cats() : []).forEach(function(c){ cs[c] = true; });
    return ORDER.filter(function(s){ return s.cats.some(function(c){ return cs[c] && (!E.count || E.count(c) > 0); }); });
  }
  var P = [];
  function hidden(){                                      /* every category of every step up to and including idx */
    var out = [];
    P.slice(0, idx).forEach(function(s){ s.cats.forEach(function(c){ if (out.indexOf(c) < 0) out.push(c); }); });
    return out;
  }
  function push(){
    if (!E || !E.off) return;
    try { E.off(hidden()); } catch (e){ if (window.console) console.error("peel", e); }
    if (E.redraw){ try { E.redraw(); } catch (e2){} }
  }
  function label(){
    if (!idx) return "Whole body";
    var s = P[idx - 1];
    return "Peeled to " + (idx === P.length ? "the skeleton" : "below " + s.label.toLowerCase()) + " · " + idx + " / " + P.length;
  }
  function ui(){
    if (out) out.textContent = label();
    if (upB) upB.disabled = idx >= P.length;
    if (dnB) dnB.disabled = idx <= 0;
    if (allB) allB.hidden = idx === 0;
    if (box) box.setAttribute("data-step", String(idx));
  }
  function set(i, quiet){
    i = Math.max(0, Math.min(P.length, i | 0));
    if (i === idx){ ui(); return false; }
    idx = i; push(); ui();
    if (!quiet){
      if (hist && hist.schedule) hist.schedule();
      if (window.NMSKShowAll && NMSKShowAll.refresh) NMSKShowAll.refresh();
      if (window.NMSKCombos && NMSKCombos.refresh) NMSKCombos.refresh();
    }
    return true;
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null; if (!E || typeof E.off !== "function") return api;
      hist = opt.history || window.NMSKHistory || null;
      P = present();
      box = document.createElement("div");
      box.id = "pl-box"; box.className = "pl-box";
      box.setAttribute("role", "group"); box.setAttribute("aria-label", "Peel the body inward, layer by layer");
      var lab = document.createElement("span"); lab.className = "pl-l"; lab.textContent = "Depth";
      box.appendChild(lab);
      dnB = document.createElement("button");
      dnB.type = "button"; dnB.className = "pl-b q301-b"; dnB.id = "pl-up"; dnB.textContent = "▲ Out";
      dnB.title = "Put the layer above back on (one Undo step)";
      dnB.addEventListener("click", function(e){ e.stopPropagation(); set(idx - 1); });
      upB = document.createElement("button");
      upB.type = "button"; upB.className = "pl-b q301-b"; upB.id = "pl-down"; upB.textContent = "▼ In";
      upB.title = "Take the next layer off, from the skin inward (one Undo step)";
      upB.addEventListener("click", function(e){ e.stopPropagation(); set(idx + 1); });
      box.appendChild(dnB); box.appendChild(upB);
      allB = document.createElement("button");
      allB.type = "button"; allB.className = "pl-b pl-all q301-b"; allB.id = "pl-whole"; allB.textContent = "Whole body";
      allB.hidden = true; allB.title = "Put every peeled layer back (one Undo step)";
      allB.addEventListener("click", function(e){ e.stopPropagation(); set(0); });
      box.appendChild(allB);
      out = document.createElement("output"); out.id = "pl-state"; out.className = "pl-o"; out.setAttribute("aria-live", "polite");
      box.appendChild(out);
      var n = document.createElement("span"); n.className = "pl-note";
      n.innerHTML = '<p class="nmsk-tip">One control for <b>how deep</b>, in ' + P.length + ' taps, from the skin inward &mdash; next to the per-system controls, which stay as they are. ' +
        'The order comes from this page\'s own tissue categories: ' + P.map(function(s){ return s.label.toLowerCase(); }).join(" → ") + ' → <b>bone and cartilage</b>. ' +
        'The <b>fat step IS the superficial fascia</b>: 17 of its structures are labelled <i>Panniculus adiposus (tela subcutanea)</i> in the data itself. What this atlas does not carry is a separate <b>membranous (Scarpa\'s) layer</b> &mdash; the pages\' own search data says so in as many words &mdash; so the peel does not offer one. ' +
        'One grouping is <b>our convention, not anatomy</b>: <b>vessels, nerves and lymphatics come off together</b>, because the data holds no depth rank for a single vessel and real vessels cross every layer.</p>';
      box.appendChild(n);
      if (opt.toolbar) opt.toolbar.appendChild(box); else document.body.appendChild(box);
      if (hist && hist.register) hist.register("peel", {get:function(){ return idx; }, set:function(v){ set(v | 0, true); }, reset:function(){ set(i0, true); }});
      if (opt.showall && opt.showall.add) opt.showall.add(api.source());
      on = true; ui();
      return api;
    },
    /* Q300 registers this as one of the page's hiding paths, so "Show everything" brings the layers back */
    source:function(){
      return {key:"peel", label:function(){ return "peeled: " + idx + " layer" + (idx === 1 ? "" : "s"); },
        active:function(){ return on && idx > 0; }, clear:function(){ set(0, true); }, drive:function(){ set(1, true); }};
    },
    step:function(){ return idx; }, set:function(i){ return set(i); },
    deeper:function(){ return set(idx + 1); }, shallower:function(){ return set(idx - 1); },
    steps:function(){ return P.map(function(s){ return {key:s.key, label:s.label, cats:s.cats.slice()}; }); },
    hidden:hidden, label:label, refresh:ui,
    state:function(){ return {on:on, step:idx, max:P.length, hidden:hidden(), label:label()}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKPeel;
