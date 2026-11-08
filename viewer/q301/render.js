/* Q301: a MODEL-WIDE render style -- the colour picture is replaced by a radiographic one, and one tap brings the colour back.
   Owner: "the model itself must offer X-RAY / CT / MRI rendering resembling their real reconstructions -- replacing the
   colour image with the style the user asks for, and one tap returns."
   This is NOT the 2-D slice panes of the clinical add-ons: it re-skins the whole 3-D model. Three styles, all driven by
   NMSKTissue from the page's own clinical tissue reference (its real attenuation and relaxation values), each with three taps of its own:
     xray  -- a DRR. Each structure is drawn translucent with alpha = 1 - exp(-mu * d0). Ordinary alpha compositing over
              black accumulates 1 - PRODUCT(1 - alpha_i) = 1 - exp(-SUM mu_i d0), which IS Beer-Lambert's attenuation,
              and it is order independent, so no depth sort is needed. Both faces of every shell are drawn, because a ray
              really does cross a shell twice. Bone (mu 2.30) against fat (mu 0.89) separates by itself; this style does
              NOT use Q300's bone pass and says so.  Steps = d0: Soft / Normal / Hard.
     ct    -- each structure painted the grey its own HU maps to through a real CT window. Steps = the window: MSK / Soft / Bone.
     mri   -- each structure painted the grey its own spin-echo signal gives. Steps = the sequence: T1 / T2 / PD fat-sat.
   The engine does the drawing through E: {apply(spec), active(), redraw(), film(on)}; `spec` is
     {mode, greyOf(cat, id, name, vt) -> 0..1, alphaOf(...) -> 0..1, flat:bool}  (flat = no shading, for the DRR).
     NMSKRenderStyle.start(E, {toolbar, history, tissue, combos})
     .mode()  .set(mode)  .step()  .setStep(i)  .toColour()  .steps()  .spec()  .state() */
var NMSKRenderStyle = (function(){
  "use strict";
  var E = null, hist = null, T = null, box = null, on = false, mode = "colour", step = {xray:1, ct:0, mri:2}, btns = {}, stepRow = null, stepBtns = [], userContrast = 1.0, userBrightness = 1.0, userInvert = false, cbRow = null, cSl = null, bSl = null, invBtn = null, baseD0 = 1;
  /* The path length taken through each surface a ray crosses. THIS IS OUR CONVENTION, not a measurement: a surface
     atlas has no thickness along the ray. The three values were CHOSEN BY MEASURING the whole-body projection in a real
     browser (scripts/anatomy/q301/, and the table in docs/research/Q301_controls_and_render_styles.md 3.6): the
     picture's own contrast (the standard deviation of its luminance) peaks at 0.10 and the highlights start to burn out
     above 0.14, so 0.10 is Normal, 0.05 is a softer exposure and 0.20 a harder one for a thick region. */
  var D0 = [0.05, 0.10, 0.20];
  /* Q317: the X-ray step chooses a TISSUE WINDOW on the attenuation, not the exposure (the exposure is baseD0, set per
     engine from the measurement above). Each entry is [lo, hi, gain] in mu/mu_water: before the DRR takes a structure,
     its mu becomes max(0, (mu - lo) / (hi - lo)) * gain, so a tissue under lo stops contributing and the picture keeps
     only what the window admits -- which is what lets one film show only bone and another the soft tissue.
     THE WINDOW IS OUR DISPLAY CONVENTION, not a measurement: mu itself stays the real attenuation the page's clinical
     tissue reference gives (mu/mu_water = 1 + v/1000), and the window only decides what is drawn, the way a real film's
     kV and filtration decide the tissue contrast it records. The gain is what gives the picture its tissue contrast:
     mu spans only about 1.0 (fluid) to 2.3 (cortical bone), so a DRR taken straight off it separates bone from muscle by
     just 2.1x per shell -- which is why every tissue used to read as one fog. Through Combined that separation is 7.2x.
     Bone's lower bound sits between cancellous bone and cartilage, so a bone film keeps the trabecular bone and drops
     the soft tissue to the shader's 0.004 floor. Checked at both engines' exposures (d0 = 0.05 and 0.10). */
  var XW = [[0.88, 1.12, 2.2], [0.88, 2.30, 8.0], [1.13, 2.30, 18.0]];
  var XW_W = ["Soft tissue", "Combined", "Bone"];
  /* How far the shading is flattened in the CT and MRI styles. The grey IS the datum there -- it comes from the tissue's
     own HU or its own spin-echo signal -- and multiplying it by a diffuse term would mean the picture no longer shows
     what the table says. 0.6 keeps 60 % of the grey untouched and leaves 40 % to the shading as a depth cue. */
  var FLATTEN = 0.6;
  var MODES = [["colour", "Colour"], ["xray", "X-ray"], ["ct", "CT"], ["mri", "MRI"]];
  var CTW = ["msk", "soft", "bone"], CTW_W = ["MSK", "Soft", "Bone"];
  /* which three MR sequences, and their words: the private clinical layer names them (Q226 boundary -- this file may
     not), and each word is the sequence's own label from the reference, shortened to what fits a button. */
  function mrKeys(){ var k = T && T.mskSequences ? T.mskSequences() : []; return k.length ? k : []; }
  function mrWords(){
    var k = mrKeys(), by = {};
    (T && T.sequences ? T.sequences() : []).forEach(function(q){ by[q.key] = q.label || q.key; });
    return k.map(function(q){
      var l = by[q] || q;
      return l.replace(/\s*\(fast\)\s*/i, " ").replace(/\s*spin echo\s*$/i, "").replace(/fat-suppressed/i, "fat-sat").trim() || q;
    });
  }
  function stepsFor(m){ return m === "xray" ? XW_W : m === "ct" ? CTW_W : m === "mri" ? mrWords() : []; }
  function xrMu(mu){
    var w = XW[step.xray] || XW[1];
    return Math.max(0, (mu - w[0]) / (w[1] - w[0])) * w[2];
  }
  /* Q317: contrast / brightness / invert act on the FINISHED picture, through a filter on the 3-D canvas (q301.css).
     They cannot be applied per structure: the X-ray is a DRR, so its grey is built by compositing many translucent
     shells and no single shell's colour is the pixel. Q316 wrapped the per-structure alpha instead, which the DRR's
     fragment shader never reads -- it computes the alpha itself from mu and d0 -- so the sliders did nothing in X-ray. */
  function paintAdj(){
    var s = document.documentElement.style;
    if (mode === "colour"){ s.removeProperty("--q301-adj"); return; }
    s.setProperty("--q301-adj", "contrast(" + userContrast.toFixed(2) + ") brightness(" + userBrightness.toFixed(2) + ")" + (userInvert ? " invert(1)" : ""));
  }
  function setAdj(c, b, inv){
    userContrast = c; userBrightness = b; userInvert = !!inv;
    if (cSl){ cSl.rg.value = c; cSl.nm.textContent = c.toFixed(2); }
    if (bSl){ bSl.rg.value = b; bSl.nm.textContent = b.toFixed(2); }
    if (invBtn){ invBtn.setAttribute("aria-pressed", String(userInvert)); invBtn.classList.toggle("on", userInvert); }
    paintAdj();
  }
  function cls(cat, id, name, vt){ return T ? T.classOf(cat, id, name, vt) : "soft_unassigned"; }
  function spec(){
    if (mode === "colour" || !T || !T.ready()) return {mode:"colour"};
    if (mode === "xray"){
      var d0 = D0[baseD0] || D0[1];
      return {mode:"xray", flat:true, d0:d0,
        greyOf:function(){ return 1; },
        /* mu/mu_water = 1 + v/1000 -- the definition of the CT attenuation unit, so nothing there is a choice of ours.
           xrMu() then puts it through the step's tissue window, which IS ours (see XW). */
        muOf:function(cat, id, name, vt){ return xrMu(T.mu(cls(cat, id, name, vt))); },
        alphaOf:function(cat, id, name, vt){ return Math.max(0.004, Math.min(0.995, 1 - Math.exp(-xrMu(T.mu(cls(cat, id, name, vt))) * d0))); }};
    }
    if (mode === "ct"){
      var w = CTW[step.ct] || CTW[0];
      return {mode:"ct", flat:false, window:w, flatten:FLATTEN,
        greyOf:function(cat, id, name, vt){ return T.ctGrey(cls(cat, id, name, vt), w); },
        alphaOf:null};
    }
    var MK = mrKeys(), sq = MK[step.mri] || MK[0], mx = 0;
    T.keys().forEach(function(k){ var v = T.mrGrey(k, sq); if (v > mx) mx = v; });
    mx = mx > 0 ? mx : 1;
    return {mode:"mri", flat:false, sequence:sq, flatten:FLATTEN,
      greyOf:function(cat, id, name, vt){ return Math.max(0, Math.min(1, T.mrGrey(cls(cat, id, name, vt), sq) / mx)); },
      alphaOf:null};
  }
  function push(){
    paintAdj();
    if (!E || !E.apply) return;
    try { E.apply(spec()); } catch (e){ if (window.console) console.error("renderstyle", e); }
    if (E.film){ try { E.film(mode !== "colour"); } catch (e2){} }
    if (E.redraw){ try { E.redraw(); } catch (e3){} }
  }
  function say(m){
    var e = document.getElementById("hist-msg");
    if (!e || !m) return;
    e.textContent = m; e.hidden = false;
    clearTimeout(say.t); say.t = setTimeout(function(){ e.hidden = true; }, 3000);
  }
  function set(m, quiet){
    if (!MODES.some(function(x){ return x[0] === m; })) return false;
    if (m !== "colour" && (!T || !T.ready())) { say("The clinical tissue reference has not loaded yet, so the radiographic styles are not available."); return false; }
    if (m === mode){ ui(); return false; }
    mode = m; push(); ui();
    if (!quiet){
      if (hist && hist.schedule) hist.schedule();
      say(m === "colour" ? "Back to the colour model."
        : "Model drawn as " + wordFor(m) + " from this page's own clinical tissue reference. One tap on Colour returns. See the i for what is measured and what is our convention.");
      if (window.NMSKCombos && NMSKCombos.refresh) NMSKCombos.refresh();
      if (window.NMSKShowAll && NMSKShowAll.refresh) NMSKShowAll.refresh();
    }
    return true;
  }
  function wordFor(m){ var o = ""; MODES.forEach(function(x){ if (x[0] === m) o = x[1]; }); return o; }
  function setStep(i, quiet){
    if (mode === "colour") return false;
    var n = stepsFor(mode).length;
    i = Math.max(0, Math.min(n - 1, i | 0));
    if (step[mode] === i){ ui(); return false; }
    step[mode] = i; push(); ui();
    if (!quiet && hist && hist.schedule) hist.schedule();
    return true;
  }
  function ui(){
    var rdy = !!(T && T.ready());
    Object.keys(btns).forEach(function(k){
      var b = btns[k], hot = (k === mode);
      b.setAttribute("aria-pressed", String(hot)); b.classList.toggle("on", hot);
      if (k !== "colour"){                        /* the reference comes from the clinical layer: offered only once it is here */
        b.disabled = !rdy;
        b.title = rdy ? (b.getAttribute("data-t") || b.title)
                      : "Waiting for this page's clinical tissue reference, which the styles are computed from";
      }
    });
    if (cbRow) cbRow.hidden = mode === "colour";
    if (!stepRow) return;
    var w = stepsFor(mode);
    stepRow.hidden = !w.length;
    stepBtns.forEach(function(b, i){
      b.hidden = i >= w.length;
      if (i < w.length){
        b.textContent = w[i];
        var hot = step[mode] === i;
        b.setAttribute("aria-pressed", String(hot)); b.classList.toggle("on", hot);
        b.title = mode === "xray" ? "Which tissues the film records, as a window on each tissue's own attenuation (the window itself is our convention): " + w[i]
                : mode === "ct" ? "CT window " + w[i] : "MR sequence " + w[i];
      }
    });
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null; if (!E || typeof E.apply !== "function") return api;
      hist = opt.history || window.NMSKHistory || null;
      T = opt.tissue || window.NMSKTissue || null;
      if (opt.xrayStep != null) baseD0 = Math.max(0, Math.min(D0.length - 1, opt.xrayStep | 0));   /* the exposure, per engine by measurement; the step is now the tissue window */
      box = document.createElement("div");
      box.id = "rs-box"; box.className = "rs-box";
      box.setAttribute("role", "group"); box.setAttribute("aria-label", "How the model itself is drawn");
      var row = document.createElement("div"); row.className = "rs-row";
      MODES.forEach(function(x){
        var b = document.createElement("button");
        b.type = "button"; b.className = "rs-b q301-b"; b.id = "rs-" + x[0]; b.textContent = x[1];
        b.setAttribute("aria-pressed", String(x[0] === mode));
        b.title = x[0] === "colour" ? "The ordinary colour model (one tap, from any style)"
                : x[0] === "xray" ? "Greyscale radiograph: the beam's attenuation added up along the view ray, from each tissue's real CT attenuation"
                : x[0] === "ct" ? "CT look: every structure in the grey its own measured attenuation gives through a real CT window"
                : "MRI look: every structure in the grey its own T1 / T2 / proton density gives for the chosen sequence";
        b.setAttribute("data-t", b.title);        /* kept, so the "not loaded yet" title can be swapped back */
        b.addEventListener("click", function(e){ e.stopPropagation(); set(x[0]); });
        row.appendChild(b); btns[x[0]] = b;
      });
      box.appendChild(row);
      stepRow = document.createElement("div"); stepRow.className = "rs-row rs-steps"; stepRow.hidden = true;
      for (var i = 0; i < 3; i++){
        var sb = document.createElement("button");
        sb.type = "button"; sb.className = "rs-s q301-b"; sb.id = "rs-step-" + i;
        sb.addEventListener("click", (function(k){ return function(e){ e.stopPropagation(); setStep(k); }; })(i));
        stepRow.appendChild(sb); stepBtns.push(sb);
      }
      box.appendChild(stepRow);
      /* Q317: contrast, brightness, a negative, and the way back to the style's own exposure. Hidden in Colour. */
      cbRow = document.createElement("div"); cbRow.className = "rs-row rs-cb"; cbRow.hidden = true;
      function mkSl(label, mn, mx, stp, val, fn){
        var w = document.createElement("div"); w.className = "rs-sl";
        var lb = document.createElement("span"); lb.className = "rs-l"; lb.textContent = label;
        var rg = document.createElement("input"); rg.type = "range"; rg.min = mn; rg.max = mx; rg.step = stp; rg.value = val;
        var nm = document.createElement("span"); nm.className = "rs-v"; nm.textContent = (+val).toFixed(2);
        rg.addEventListener("input", function(){ nm.textContent = (+rg.value).toFixed(2); fn(+rg.value); paintAdj(); if (hist && hist.schedule) hist.schedule(); });
        w.appendChild(lb); w.appendChild(rg); w.appendChild(nm);
        return {w:w, rg:rg, nm:nm};
      }
      cSl = mkSl("Contrast", 0.4, 2.5, 0.05, 1.0, function(v){ userContrast = v; });
      bSl = mkSl("Brightness", 0.4, 2.0, 0.05, 1.0, function(v){ userBrightness = v; });
      cbRow.appendChild(cSl.w); cbRow.appendChild(bSl.w);
      invBtn = document.createElement("button");
      invBtn.type = "button"; invBtn.className = "rs-s q301-b"; invBtn.id = "rs-invert"; invBtn.textContent = "Invert";
      invBtn.title = "Show the picture as a negative, the whole view at once, the way a film is read";
      invBtn.setAttribute("aria-pressed", "false");
      invBtn.addEventListener("click", function(e){ e.stopPropagation(); setAdj(userContrast, userBrightness, !userInvert); if (hist && hist.schedule) hist.schedule(); });
      cbRow.appendChild(invBtn);
      var rsb = document.createElement("button");
      rsb.type = "button"; rsb.className = "rs-s q301-b"; rsb.id = "rs-reset"; rsb.textContent = "Reset";
      rsb.title = "Back to this style's own exposure: contrast and brightness neutral, the negative off";
      rsb.addEventListener("click", function(e){ e.stopPropagation(); api.resetAdj(); });
      cbRow.appendChild(rsb);
      box.appendChild(cbRow);
      if (opt.toolbar) opt.toolbar.appendChild(box); else document.body.appendChild(box);
      if (hist && hist.register){
        hist.register("renderstyle", {get:function(){ return {m:mode, s:JSON.parse(JSON.stringify(step)), c:userContrast, b:userBrightness, i:userInvert}; },
          set:function(v){ if (!v) return; step = v.s || step; setAdj(v.c != null ? v.c : 1.0, v.b != null ? v.b : 1.0, !!v.i); set(v.m || "colour", true); setStep(step[mode] == null ? 1 : step[mode], true); },
          reset:function(){ setAdj(1.0, 1.0, false); api.toColour(true); }});
      }
      if (opt.showall && opt.showall.add) opt.showall.add(api.source());
      on = true; ui();
      return api;
    },
    /* Q300 registers this as one of the page's ways out: a greyscale model is a state you must be able to leave in one tap */
    source:function(){
      return {key:"imaging", label:function(){ return "imaging: " + wordFor(mode); },
        active:function(){ return on && mode !== "colour"; },
        clear:function(){ set("colour", true); }, drive:function(){ set("xray", true); }};
    },
    mode:function(){ return mode; }, set:function(m){ return set(m); },
    step:function(){ return step[mode] == null ? 0 : step[mode]; }, setStep:function(i){ return setStep(i); },
    steps:function(){ return stepsFor(mode).slice(); },
    toColour:function(quiet){ return set("colour", quiet); },
    spec:spec, refresh:ui, words:function(){ return MODES.map(function(x){ return x[1]; }); },
    label:function(){ return mode === "colour" ? "" : wordFor(mode) + " / " + (stepsFor(mode)[step[mode]] || ""); },
    /* Q317: back to the style's own exposure -- neutral contrast and brightness, no negative, and the mode's default step */
    resetAdj:function(){
      setAdj(1.0, 1.0, false);
      if (mode !== "colour") setStep(mode === "xray" ? 1 : mode === "ct" ? 0 : 2, false);
      if (hist && hist.schedule) hist.schedule();
      return api;
    },
    state:function(){ return {on:on, mode:mode, step:step[mode] == null ? 0 : step[mode], stepWord:stepsFor(mode)[step[mode]] || null, tissue:!!(T && T.ready()), contrast:userContrast, brightness:userBrightness, invert:userInvert}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKRenderStyle;
