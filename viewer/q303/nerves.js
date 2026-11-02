/* Q303: emphasise the nerves, including the small ones.
   Owner (translated): "allow emphasis of the nerves including the small ones."
   WHY THE SMALL ONES DISAPPEAR, measured and not guessed. This page's own calibre table (#nmsk-calibre, Q240:
   {v:1,c:{id:[kind a|v|n, diameter_mm, level 1..4, promoted]}}, diameters measured off the meshes by
   scripts/anatomy/q240/calibre.py) gives every nerve a real diameter. A whole-body view puts roughly 1700 mm of body
   into the height of the 3-D view, so one millimetre is a fraction of a pixel: a 1 mm branch is drawn far under one
   pixel wide and a 0.15 mm twig is drawn at a hundredth of one. Nothing is wrong with the mesh, the decimation or the
   draw order -- the structure is simply SUB-PIXEL, and no colour or opacity can rescue a line thinner than a pixel.
   THE ANSWER IS THE ONE THIS PROJECT HAS ALREADY PROVEN TWICE, not a third invention:
     Q299 gave a cut-face section a MINIMUM DRAWN WIDTH (1/500 of the section's extent, capped at 2.5 mm) so a thin
          structure still reads on the section;
     Q300 drew the bone ONCE MORE after the translucent pass with the depth test off, so its share of the pixel does not
          depend on how many layers lie in front of it.
   So: an extra pass over the nerve structures' own vertices, drawn after everything, each vertex as a round screen-space
   dot whose diameter is max(the nerve's TRUE width in pixels, the minimum width of the chosen step). A nerve already
   wider than the minimum is not touched. Nothing is added to or taken from any mesh, and the true calibre keeps being
   what the card and the legend print -- this is a DISPLAY AID and says so on the screen, in the control and in the
   circled i.
     NMSKNerves.start(E, {toolbar, cls, history, showall})
   E = {list() -> [{id, cat, name}], apply(spec|null), mmPerPx(), redraw(), nervePixels?()}
     .level()  .set(i)  .steps()  .census()  .absent()  .state() */
var NMSKNerves = (function(){
  "use strict";
  var E = null, hist = null, on = false, lvl = 0, box = null, segBtns = [], note = null, CAL = {}, haveCal = false;
  var rows = [], dia = {}, mpTouched = false, left = 0;
  /* the three taps: the MINIMUM drawn width in CSS pixels, and how strongly the pass paints.
     0.0 px / 0 alpha is Off. The two live steps were chosen by measuring the drawn contrast on both engines. */
  var STEP = [{w:0, a:0, label:"Off"}, {w:2.2, a:0.55, label:"Clear"}, {w:3.6, a:0.85, label:"Strong"}];
  var NERVE_CATS = {nerve:1, cns:1};
  /* A conventional list of the major peripheral nerves, used ONLY to say on the screen which of them this page does not
     ship -- emphasis cannot show a nerve that is not there. Q299 found the two Imaging pages carry no fibular /
     peroneal nerve at all and are missing 71 lower-limb nerves, while each Z page carries 18 fibular meshes; this probe
     reports that from the page's own list rather than from a claim written here. */
  var MAJOR = [
    ["median", /\bmedian\b/i], ["ulnar", /\bulnar\b/i], ["radial", /\bradial\b/i], ["musculocutaneous", /musculocutaneous/i],
    ["axillary", /\baxillary\b/i], ["suprascapular", /suprascapular/i], ["long thoracic", /long[_ ]thoracic/i],
    ["phrenic", /phrenic/i], ["vagus", /\bvagus\b/i], ["sciatic", /sciatic/i], ["tibial", /\btibial\b/i],
    ["fibular (peroneal)", /fibular|peroneal/i], ["sural", /\bsural\b/i], ["saphenous", /saphenous/i],
    ["femoral", /\bfemoral_n|femoral nerve|\bfemoral\b/i], ["obturator", /obturator/i], ["pudendal", /pudendal/i],
    ["gluteal", /gluteal_n|gluteal nerve/i], ["iliohypogastric", /iliohypogastric/i], ["ilioinguinal", /ilioinguinal/i],
    ["lateral femoral cutaneous", /lateral[_ ]femoral[_ ]cutaneous|cutaneous[_ ]femoris[_ ]lateralis/i],
    ["intercostal", /intercostal_n|intercostal nerve/i], ["accessory", /accessory_n/i], ["facial", /facial_n/i]
  ];
  function readCal(){
    try {
      var e = document.getElementById("nmsk-calibre");
      if (!e || e.textContent.trim().length <= 2) return;
      var j = JSON.parse(e.textContent);
      if (j && j.c){ CAL = j.c; haveCal = true; }
    } catch (err){ CAL = {}; haveCal = false; }
  }
  /* WHICH STRUCTURES THE EMPHASIS COVERS, and why that is the page's own answer and not ours.
     The nerve CATEGORY on these pages is wider than "a peripheral nerve": on the four Z pages it also holds the spinal
     dura, the cord's own tracts and its nuclei (`Lateral fasciculus proprius`, `Lateral vestibulospinal tract`,
     `Intermediolateral nucleus`...), and the `cns` category holds the cord and the brain. None of those is a nerve you
     would want widened, and together they are more than half the vertices in the two categories (376,522 against
     179,874 on a Z page). So the set is taken from the page's OWN calibre table (Q240): every structure it records with
     kind `n`. That is 439 of the 552 nerve-category meshes on a Z page -- the trunks and every named branch, the small
     ones included, which is exactly what was asked -- and it halves the cost of the pass as well. A page with no
     calibre table falls back to the category, and the control says which rule it used and how many structures the
     other rule would have added. */
  function isNerve(r){
    if (!r) return false;
    var c = CAL[r.id];
    if (haveCal) return !!(c && c[0] === "n");
    return !!NERVE_CATS[r.cat];
  }
  function build(){
    readCal();
    var all = [];
    try { all = E.list() || []; } catch (err){ all = []; }
    rows = all.filter(isNerve).map(function(r){
      var c = CAL[r.id] || null;
      var d = c && typeof c[1] === "number" && c[1] > 0 ? c[1] : null;
      return {id:r.id, name:r.name || r.id, cat:r.cat, dia:d, level:c ? c[2] : null, promoted:c ? !!c[3] : false};
    });
    /* the structures the OTHER rule would have added, counted off the page so the note is never a number in the code */
    left = all.filter(function(r){ return !isNerve(r) && NERVE_CATS[r.cat]; }).length;
    dia = {};
    rows.forEach(function(r){ if (r.dia != null) dia[r.id] = r.dia; });
  }
  function mmPerPx(){ try { return E.mmPerPx() || 1; } catch (err){ return 1; } }
  /* the census the control prints and the verify reads: how many nerves, how many have a real diameter, and how many of
     them are drawn under one pixel wide AT THE VIEW ON THE SCREEN RIGHT NOW (which is what "invisible" means) */
  function census(){
    var m = mmPerPx(), st = STEP[lvl], out = {n:rows.length, withDia:0, noDia:0, subPixel:0, underStep:0,
      rule:haveCal ? "the page's own calibre table (kind n)" : "the nerve / cns categories (this page has no calibre table)",
      notCovered:left, mmPerPx:Math.round(m * 1e4) / 1e4, minWidthPx:st.w,
      levels:{1:0, 2:0, 3:0, 4:0}, diaMin:null, diaMax:null, widths:[]};
    rows.forEach(function(r){
      if (r.level) out.levels[r.level] = (out.levels[r.level] || 0) + 1;
      if (r.dia == null){ out.noDia++; return; }
      out.withDia++;
      if (out.diaMin == null || r.dia < out.diaMin) out.diaMin = r.dia;
      if (out.diaMax == null || r.dia > out.diaMax) out.diaMax = r.dia;
      var px = r.dia / m;
      if (px < 1) out.subPixel++;
      if (st.w > 0 && px < st.w) out.underStep++;
    });
    return out;
  }
  function widthOf(id){
    var m = mmPerPx(), d = dia[id], st = STEP[lvl];
    var truePx = d == null ? null : d / m;
    return {id:id, dia_mm:d == null ? null : d, truePx:truePx == null ? null : Math.round(truePx * 1e3) / 1e3,
            drawnPx:Math.round(Math.max(st.w, truePx == null ? st.w : truePx) * 1e3) / 1e3, minPx:st.w};
  }
  /* which of the conventional major nerves this page simply does not carry */
  function absent(){
    var have = [], miss = [];
    MAJOR.forEach(function(p){
      var hit = 0;
      rows.forEach(function(r){ if (p[1].test(r.id) || p[1].test(r.name)) hit++; });
      (hit ? have : miss).push({name:p[0], n:hit});
    });
    return {have:have, missing:miss.map(function(x){ return x.name; })};
  }
  function spec(){
    var st = STEP[lvl];
    if (!st.w) return null;
    return {on:true, wmin:st.w, alpha:st.a, step:lvl, ids:rows.map(function(r){ return r.id; }), dia:dia,
            /* the engine turns this into a device-pixel point size with exactly this formula, on both engines:
               sizeDev = max(wmin, dia_mm / mmPerPx) * devicePixelRatio, and a nerve with no diameter takes wmin */
            formula:"max(wmin_px, dia_mm / mmPerPx) * dpr"};
  }
  function push(){
    try { E.apply(spec()); } catch (err){ if (window.console) console.error("q303 nerves", err); }
    if (E.redraw){ try { E.redraw(); } catch (e2){} }
  }
  /* Q281's motor points / NMJ markers are the needle tool's own overlay with its own "Emphasize motor points" toggle;
     emphasis switches that on rather than drawing a second set of markers that could fall out of step with it. */
  function motorPoints(want){
    var b = document.getElementById("ncl-mp-on");
    if (!b) return false;
    var isOn = b.getAttribute("aria-pressed") === "true";
    if (want && !isOn){ b.click(); mpTouched = true; return true; }
    if (!want && isOn && mpTouched){ b.click(); mpTouched = false; return true; }
    return false;
  }
  function ui(){
    segBtns.forEach(function(b, k){ b.setAttribute("aria-pressed", String(k === lvl)); b.classList.toggle("on", k === lvl); });
    if (!note) return;
    var c = census(), ab = absent();
    var txt = c.n + " nerve structures on this page";
    if (c.withDia) txt += ", " + c.withDia + " with a measured diameter (" + c.diaMin + "–" + c.diaMax + " mm)";
    if (c.noDia) txt += ", " + c.noDia + " with none on record";
    txt += ". At this zoom " + c.subPixel + " of them are drawn under one pixel wide";
    if (lvl > 0) txt += "; " + c.underStep + " are widened to the " + STEP[lvl].w + " px minimum";
    txt += ". The true calibre is unchanged — this is a display aid.";
    if (c.notCovered) txt += " " + c.notCovered + " more structures sit in the nerve / CNS categories (the cord, its tracts and nuclei, the dura) and are not peripheral nerves, so they are left exactly as they are.";
    if (ab.missing.length) txt += " This page ships no " + ab.missing.slice(0, 4).join(", ") + (ab.missing.length > 4 ? " (and " + (ab.missing.length - 4) + " more)" : "") + ": emphasis cannot show a nerve that is not here.";
    note.textContent = txt;
  }
  function provider(){
    return {get:function(){ return {lvl:lvl, mp:mpTouched}; },
            set:function(v){ if (!v) return; lvl = Math.max(0, Math.min(STEP.length - 1, v.lvl | 0)); mpTouched = !!v.mp; push(); ui(); },
            reset:function(){ if (lvl !== 0){ lvl = 0; motorPoints(false); push(); ui(); } }};
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null;
      if (!E || typeof E.apply !== "function") return api;
      hist = opt.history || window.NMSKHistory || null;
      build();
      box = document.createElement("div");
      box.id = "nv-box"; box.className = "nv-box";
      box.setAttribute("role", "group"); box.setAttribute("aria-label", "How strongly the nerves are emphasised");
      var lab = document.createElement("span"); lab.className = "nv-l"; lab.textContent = "Nerves";
      box.appendChild(lab);
      var seg = document.createElement("span"); seg.className = "nv-seg";
      STEP.forEach(function(s, k){
        var b = document.createElement("button");
        b.type = "button"; b.className = "nv-b"; b.id = "nv-" + k; b.textContent = s.label;
        b.title = k === 0 ? "No emphasis: the nerves are drawn exactly as the model has them."
          : "Draw every nerve at least " + s.w + " px wide, over the tissue in front of it. The mesh and the recorded calibre do not change.";
        b.setAttribute("aria-pressed", "false");
        b.addEventListener("click", function(ev){ ev.stopPropagation(); api.set(k); });
        seg.appendChild(b); segBtns.push(b);
      });
      box.appendChild(seg);
      note = document.createElement("p"); note.className = "nv-note"; box.appendChild(note);
      var tip = document.createElement("p"); tip.className = "nmsk-tip";
      tip.textContent = "The emphasis is an extra pass over the nerves' own vertices, drawn after everything on the camera-facing half of the model, each vertex a round dot at least the step's width across. A nerve already wider than that is untouched. It is the same idea as Q299's minimum section width and Q300's bone-through pass. Motor points / NMJ markers follow the needle tool's own “Emphasize motor points”, which this control switches on with it.";
      box.appendChild(tip);
      if (opt.toolbar) opt.toolbar.appendChild(box);
      if (hist && hist.register) hist.register("q303nerves", provider());
      on = true;
      if (opt.level) api.set(opt.level | 0, true);
      ui();
      setInterval(ui, 900);                      /* the census depends on the zoom, so the line follows the camera */
      return api;
    },
    element:function(){ return box; },
    set:function(i, quiet){
      i = Math.max(0, Math.min(STEP.length - 1, i | 0));
      if (i === lvl){ ui(); return false; }
      if (!quiet && hist && hist.commit) hist.commit();
      lvl = i;
      if (lvl > 0 && E.show){ try { E.show(); } catch (err){} }     /* composes with the nerve system toggle: it switches it on */
      motorPoints(lvl > 0);
      push(); ui();
      if (!quiet && hist && hist.commit) hist.commit();
      return true;
    },
    level:function(){ return lvl; },
    steps:function(){ return STEP.map(function(s){ return {label:s.label, w:s.w, a:s.a}; }); },
    census:census, absent:absent, widthOf:widthOf, rows:function(){ return rows.slice(); },
    /* verification: the drawn width of a named sample of large / medium / small nerves, before and after */
    sample:function(k){
      var withD = rows.filter(function(r){ return r.dia != null; }).sort(function(a, b){ return b.dia - a.dia; });
      if (!withD.length) return [];
      var n = withD.length, idx = [0, Math.floor(n / 2), n - 1], out = [];
      if (k === "all") idx = withD.map(function(_, i){ return i; });
      idx.forEach(function(i){ var r = withD[i]; if (r) out.push(Object.assign({name:r.name, level:r.level}, widthOf(r.id))); });
      return out;
    },
    state:function(){ return {on:on, level:lvl, step:STEP[lvl], census:census(), absent:absent(), notCovered:left,
                              haveCalibre:haveCal, motorPoints:!!document.getElementById("ncl-mp-on"), mpTouched:mpTouched}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKNerves;
