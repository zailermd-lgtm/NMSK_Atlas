/* Q309: the depth peel, with a SCOPE. Three of them, and two are new.
   Owner (translated from Hebrew): "... and by LAYERS -- for the whole body, per system, and for the displayed systems only."
     Whole body     -> Q301's NMSKPeel, unchanged and not rebuilt: this control drives it, it does not replace it.
     One system     -> the strata of ONE chosen system, every other system left exactly as it was.
     Systems shown  -> the strata of EXACTLY the systems switched on right now, the rest ignored.
   Both new scopes are documented market patterns, quoted in docs/research/Q301_controls_and_render_styles.md 9:
   Complete Anatomy -- "Tapping an icon reveals plus and minus buttons for adding or removing layers WITHIN THAT
   SYSTEM", "Plus adds deeper layers first, and minus strips the superficial layers first"; Primal Pictures -- "The
   Contents layer controls split each system into five layers - from deep to superficial", and its controls "enable
   users to quickly build up different systems to their desired depth of view"; Visible Body 2026 -- the Systems Tray
   "now has plus and minus icons to add or remove layers ACROSS ALL BODY SYSTEMS".
   What a "layer" means inside one system is `data/anatomy/system_layers_q309.json`, resolved against the page by
   NMSKSysMap: sourced where a textbook or this project's own group data settles it, named as our convention where it
   is ours, and ABSENT where neither does -- such a system is offered on / off and nothing else, in as many words.
   Taps, not a slider, with the layer's name and number always on the screen (Q301's rule, from Primal's "Layer up" /
   "Layer down" buttons "plus a layer number").
     NMSKSysPeel.start(E, {map, toggle, peel, history, showall, push})
     .scope()  .setScope(s)  .setSystem(k)  .step()  .set(i)  .deeper()  .shallower()  .ids()  .element()  .state() */
var NMSKSysPeel = (function(){
  "use strict";
  var E = null, M = null, TG = null, WB = null, hist = null, push = null, on = false;
  var box = null, scRow = null, syRow = null, outEl = null, upB = null, dnB = null, allB = null, whyEl = null;
  var scope = "body", sysKey = "", step = 0, scBtns = {}, syBtns = {};
  var SCOPES = [{k:"body", l:"Whole body"}, {k:"one", l:"One system"}, {k:"shown", l:"Systems shown"}];
  function peelable(){ return M.systems().filter(function(s){ return s.peel; }); }
  function shownPeelable(){ return peelable().filter(function(s){ return !TG || TG.isOn(s.key); }); }
  function maxStep(){
    if (scope === "body") return WB ? WB.steps().length : 0;
    if (scope === "one"){ return sysKey ? M.depth(sysKey) : 0; }
    return shownPeelable().reduce(function(a, s){ return Math.max(a, s.strata.length); }, 0);
  }
  function ids(){
    if (!on || scope === "body" || step <= 0) return [];
    var out = [], seen = {};
    var L = scope === "one" ? (sysKey ? [M.get(sysKey)] : []) : shownPeelable();
    L.forEach(function(s){
      if (!s) return;
      M.idsUpTo(s.key, step).forEach(function(i){ if (!seen[i]){ seen[i] = 1; out.push(i); } });
    });
    return out;
  }
  function label(){
    var m = maxStep();
    if (scope === "body") return WB ? WB.label() : "Whole body";
    if (scope === "one" && !sysKey) return "pick a system";
    if (!step) return (scope === "one" ? (M.get(sysKey) || {}).label : "the " + shownPeelable().length + " systems shown") + " — nothing peeled";
    var s = scope === "one" ? M.get(sysKey) : null;
    var nm = s ? s.strata[Math.min(step, s.strata.length) - 1].label : "";
    return (scope === "one" ? s.label + ": off to " + nm.toLowerCase() : "peeled in " + shownPeelable().length + " systems") +
      " · " + step + " / " + m + " · " + ids().length + " structures";
  }
  function why(){
    if (scope === "body") return "";
    var bad = (scope === "one" ? (sysKey ? [M.get(sysKey)] : []) : M.systems().filter(function(s){ return !s.peel && (!TG || TG.isOn(s.key)); }))
      .filter(function(s){ return s && !s.peel; });
    if (!bad.length) return "";
    return bad.map(function(s){ return s.label + ": " + s.why + "."; }).join(" ");
  }
  function ui(){
    var m = maxStep();
    SCOPES.forEach(function(s){ var b = scBtns[s.k]; if (b) b.setAttribute("aria-pressed", String(scope === s.k)); });
    if (syRow) syRow.hidden = scope !== "one";
    peelable().forEach(function(s){ var b = syBtns[s.key]; if (b) b.setAttribute("aria-pressed", String(sysKey === s.key)); });
    if (outEl) outEl.textContent = label();
    if (upB) upB.disabled = step >= m || (scope === "one" && !sysKey);
    if (dnB) dnB.disabled = step <= 0;
    if (allB) allB.hidden = step === 0;
    if (whyEl){ var w = why(); whyEl.textContent = w; whyEl.hidden = !w; }
    if (box) box.setAttribute("data-scope", scope), box.setAttribute("data-step", String(step));
  }
  function apply(){
    if (scope === "body"){ if (push) push(); }                 /* NMSKPeel owns the category table; we add nothing */
    else if (push) push();
    else if (E && E.off){ E.off(ids()); if (E.redraw) E.redraw(); }
    ui();
  }
  function commit(quiet){
    if (quiet) return;
    if (hist && hist.schedule) hist.schedule();
    if (window.NMSKShowAll && NMSKShowAll.refresh) NMSKShowAll.refresh();
    if (window.NMSKCombos && NMSKCombos.refresh) NMSKCombos.refresh();
  }
  function set(i, quiet){
    var m = maxStep();
    i = Math.max(0, Math.min(m, i | 0));
    if (scope === "body"){
      if (!WB) return false;
      var moved = WB.set(i);                                   /* Q301's own module does the work and its own history */
      step = WB.step(); ui();
      return moved;
    }
    if (i === step){ ui(); return false; }
    step = i; apply(); commit(quiet);
    return true;
  }
  function setScope(s, quiet){
    if (s !== "body" && s !== "one" && s !== "shown") return false;
    if (s === scope){ ui(); return false; }
    /* one depth control at a time: leaving a scope puts its own layers back, so the three can never overlap */
    if (scope === "body" && WB) WB.set(0, true);
    step = 0;
    scope = s;
    if (scope === "one" && !sysKey){ var p = peelable()[0]; sysKey = p ? p.key : ""; }
    if (scope === "body" && WB) step = WB.step();
    apply(); commit(quiet);
    return true;
  }
  function setSystem(k, quiet){
    if (!M.get(k) || !M.get(k).peel) return false;
    if (k === sysKey && scope === "one"){ ui(); return false; }
    sysKey = k; step = 0; scope = "one"; apply(); commit(quiet);
    return true;
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null; M = opt.map || window.NMSKSysMap || null; TG = opt.toggle || window.NMSKSysToggle || null;
      WB = opt.peel || window.NMSKPeel || null; push = opt.push || null;
      if (!E || !M || !M.ready()) return api;
      hist = opt.history || window.NMSKHistory || null;
      box = document.createElement("div");
      box.id = "sp-box"; box.className = "sp-box";
      box.setAttribute("role", "group"); box.setAttribute("aria-label", "Peel layers, and choose what the peel applies to");
      var lab = document.createElement("span"); lab.className = "sp-l"; lab.textContent = "Depth by";
      box.appendChild(lab);
      scRow = document.createElement("div"); scRow.className = "sp-sc"; scRow.setAttribute("role", "group");
      scRow.setAttribute("aria-label", "What the depth peel applies to");
      SCOPES.forEach(function(s){
        var b = document.createElement("button");
        b.type = "button"; b.className = "sp-b q301-b"; b.id = "sp-sc-" + s.k; b.textContent = s.l;
        b.setAttribute("aria-pressed", String(scope === s.k));
        b.title = s.k === "body" ? "Peel the whole body, exactly as it always did (Q301's own control)"
          : s.k === "one" ? "Peel one chosen system only; every other system is left as it is"
          : "Peel across exactly the systems switched on right now";
        b.addEventListener("click", function(e){ e.stopPropagation(); setScope(s.k); });
        scRow.appendChild(b); scBtns[s.k] = b;
      });
      box.appendChild(scRow);
      syRow = document.createElement("div"); syRow.className = "sp-sy"; syRow.hidden = true;
      syRow.setAttribute("role", "group"); syRow.setAttribute("aria-label", "Which system to peel");
      peelable().forEach(function(s){
        var b = document.createElement("button");
        b.type = "button"; b.className = "sp-s q301-b"; b.id = "sp-sy-" + s.key;
        b.setAttribute("aria-pressed", "false");
        b.textContent = s.label + " (" + s.strata.length + ")";
        b.title = s.label + ": " + s.strata.map(function(t){ return t.label + " " + t.n; }).join(" → ");
        b.addEventListener("click", function(e){ e.stopPropagation(); setSystem(s.key); });
        syRow.appendChild(b); syBtns[s.key] = b;
      });
      box.appendChild(syRow);
      dnB = document.createElement("button");
      dnB.type = "button"; dnB.className = "sp-b q301-b"; dnB.id = "sp-out"; dnB.textContent = "▲ Out";
      dnB.title = "Put the layer above back on (one Undo step)";
      dnB.addEventListener("click", function(e){ e.stopPropagation(); set(step - 1); });
      upB = document.createElement("button");
      upB.type = "button"; upB.className = "sp-b q301-b"; upB.id = "sp-in"; upB.textContent = "▼ In";
      upB.title = "Take the next layer off, from the surface inward (one Undo step)";
      upB.addEventListener("click", function(e){ e.stopPropagation(); set(step + 1); });
      box.appendChild(dnB); box.appendChild(upB);
      allB = document.createElement("button");
      allB.type = "button"; allB.className = "sp-b sp-all q301-b"; allB.id = "sp-whole"; allB.textContent = "Put it all back";
      allB.hidden = true; allB.title = "Put every peeled layer of this scope back (one Undo step)";
      allB.addEventListener("click", function(e){ e.stopPropagation(); set(0); });
      box.appendChild(allB);
      outEl = document.createElement("output"); outEl.id = "sp-state"; outEl.className = "sp-o";
      outEl.setAttribute("aria-live", "polite"); box.appendChild(outEl);
      whyEl = document.createElement("p"); whyEl.id = "sp-why"; whyEl.className = "sp-why"; whyEl.hidden = true;
      box.appendChild(whyEl);
      var n = document.createElement("span"); n.className = "sp-note";
      n.innerHTML = '<p class="nmsk-tip">The same taps, three <b>scopes</b>. <b>Whole body</b> is Q301’s own control, driven from here, not rebuilt. ' +
        '<b>One system</b> peels one system’s own depth strata and leaves every other system alone. <b>Systems shown</b> peels across exactly the systems switched on. ' +
        'What a layer means inside a system comes from <code>data/anatomy/system_layers_q309.json</code>, resolved against this page: ' +
        peelable().map(function(s){ return "<b>" + s.label + "</b> " + s.strata.map(function(t){ return t.label.toLowerCase() + " (" + t.n + ")"; }).join(" → "); }).join("; ") +
        '. A system with no depth ordering we can source offers <b>on / off only</b>, and says so. One tap is <b>one Undo step</b>.</p>';
      box.appendChild(n);
      if (opt.toolbar) opt.toolbar.appendChild(box);
      on = true; ui();
      return api;
    },
    source:function(){
      return {key:"q309peel",
        label:function(){ return "peeled (" + (scope === "one" ? ((M.get(sysKey) || {}).label || "one system") : "systems shown") + "): " + step; },
        /* Q300's rule: zero chrome until something really is hidden -- a peel in a scope whose systems have
           nothing to take off must not raise a chip, which is what a step counter alone would have done. */
        active:function(){ return on && scope !== "body" && step > 0 && ids().length > 0; },
        clear:function(){ step = 0; apply(); },
        drive:function(){ if (scope === "body") setScope("shown", true); step = 1; apply(); }};
    },
    scope:function(){ return scope; }, setScope:setScope,
    system:function(){ return sysKey; }, setSystem:setSystem,
    step:function(){ return step; }, set:set,
    deeper:function(){ return set(step + 1); }, shallower:function(){ return set(step - 1); },
    max:maxStep, ids:ids, label:label, element:function(){ return box; }, refresh:ui,
    peelable:function(){ return peelable().map(function(s){ return s.key; }); },
    get:function(){ return scope + "|" + sysKey + "|" + step; },
    put:function(v){
      var p = String(v || "body||0").split("|");
      scope = (p[0] === "one" || p[0] === "shown") ? p[0] : "body";
      sysKey = p[1] || ""; step = parseInt(p[2], 10) || 0;
      if (scope === "body" && WB) step = WB.step();
      apply();
    },
    state:function(){ return {on:on, scope:scope, system:sysKey, step:step, max:maxStep(),
      hidden:ids().length, label:label(), peelable:api.peelable()}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKSysPeel;
