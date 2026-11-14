/* Q303: the boot. One call per page from each engine's own glue, exactly as Q301 does it -- everything engine specific
   is in the adaptors the glue passes in, so the two engines behave identically and this file is the only place the
   round's wiring lives. It adds its members to Q301's EXISTING "View" group (NMSKGroups.addTo) rather than putting new
   buttons at the top level, registers its compatibility rows with Q301's table (NMSKCombos.addPair), and writes its own
   sections of the circled i from the real numbers.
     NMSKQ303.start({anchor, history, modelreset, target:E, autofocus:E, fourup:E, views:E, nerves:E, nerveLevel})
     .ready()  .state() */
var NMSKQ303 = (function(){
  "use strict";
  var on = false, O = null, focusBox = null;
  function esc(s){ return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function el(tag, cls, txt){ var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }

  function focusElement(){
    if (focusBox) return focusBox;
    focusBox = el("div", "q3-focus");
    focusBox.id = "q303-focus-box";
    focusBox.setAttribute("role", "group"); focusBox.setAttribute("aria-label", "Centring on what you chose");
    if (window.NMSKAutoFocus){
      focusBox.appendChild(NMSKAutoFocus.button("q301-b"));
      focusBox.appendChild(NMSKAutoFocus.centreButton("q301-b"));
    }
    var tip = el("p", "nmsk-tip");
    tip.textContent = "On (the default): entering CT / MR, the probe, a cut, the cross-sections or a radiographic style centres that mode on what you have marked, on the structure whose card is open, or on the result you picked out of a search — in that order. With nothing chosen, nothing moves. Each centring is one Undo step and the two resets undo it.";
    focusBox.appendChild(tip);
    return focusBox;
  }

  function combos(){
    var C = window.NMSKCombos;
    if (!C || !C.add || !C.addPair) return;
    if (window.NMSKFourUp) C.add({key:"fourup", label:"Four views", active:function(){ return NMSKFourUp.layout() === "four"; }});
    if (window.NMSKNerves) C.add({key:"nerves", label:"Nerve emphasis", active:function(){ return NMSKNerves.level() > 0; }});
    [
      {a:"fourup", b:"measure", ok:false,
       why:"Measure draws on one view. Tap a pane's square to show only that pane, then measure there."},
      {a:"fourup", b:"imaging", ok:true,
       why:"All four panes take the radiographic style: it is one model drawn four times, not four models."},
      {a:"fourup", b:"cut", ok:true,
       why:"One cut, seen from four sides at once — which is what four panes are for."},
      {a:"fourup", b:"spin", ok:true,
       why:"Spin turns the pane you are working in; the other three stay where you put them."},
      {a:"nerves", b:"imaging", ok:false,
       why:"A greyscale radiographic picture has no highlight colour. Switch back to Colour to emphasise the nerves, or mark them and use the Marked list."},
      {a:"nerves", b:"peel", ok:true,
       why:"Peel to the bone and the nerves stay emphasised over it."},
      {a:"nerves", b:"cut", ok:true,
       why:"The emphasis is clipped by the cut, so a removed half stays removed."}
    ].forEach(function(r){ C.addPair(r); });
  }

  function infoSections(){
    var I = window.NMSKInfo; if (!I) return;
    I.add({key:"q303focus", title:"Centring imaging on what you already chose", order:22, build:function(){
      var A = window.NMSKAutoFocus;
      if (!A) return "<p>(not on this page)</p>";
      var st = A.state();
      return "<p>Entering an imaging-like mode centres it on what you already chose, instead of making you navigate " +
        "there again. The order is fixed: <b>the marked set</b> (their combined bounding box), then <b>the structure " +
        "whose card is open</b>, then <b>the result you picked out of a search</b>. With none of those, <b>nothing " +
        "moves</b> &mdash; it never jumps when there is nothing to jump to.</p>" +
        "<p>What “centred” means in each mode:</p><ul>" +
        "<li><b>CT / MR</b> &mdash; the slice point becomes the centre, and every pane's own in-plane centre is " +
        "released so it follows it: the slice LEVEL and the in-plane POSITION in one move. This is 3D Slicer's " +
        "<i>Jump slices &mdash; centered</i>, which its Markups module offers as a choice against <i>offset</i>.</li>" +
        "<li><b>The probe</b> &mdash; it is seated on the skin where a ray from the camera to the centre meets " +
        "it, so it comes in from the side you are looking from.</li>" +
        "<li><b>Cut</b> &mdash; the plane keeps the orientation you chose and only slides along its own normal until it " +
        "passes through the centre.</li>" +
        "<li><b>Cross-sections</b> &mdash; the stack is centred on the cut plane, so the same slide centres the stack; " +
        "in part mode the stack's part becomes the structures you chose.</li>" +
        "<li><b>A radiographic style</b> &mdash; the camera frames the chosen structures.</li></ul>" +
        "<p>It is <b>one Undo step</b> each time, both resets undo it, and the switch " +
        "(<i>Follow what I chose</i>, in View) is <b>" + (st.follow ? "on" : "off") + "</b> and remembered in this browser. " +
        "A line on the screen says what it centred on and why.</p>";
    }});
    I.add({key:"q303four", title:"Four views at once: whose convention, and what stands down", order:24, build:function(){
      var F = window.NMSKFourUp;
      if (!F) return "<p>(not on this page)</p>";
      var p = F.panes();
      return "<p><b>One model, four cameras.</b> Selection, marking, hiding, the layers, the peel, the radiographic " +
        "style and the cut are the engine's single state, and the panes are four viewports over that one scene &mdash; " +
        "so they cannot disagree. Only the camera is per pane. The pane you touch owns the camera, so dragging, the " +
        "wheel and pinch act on it alone.</p>" +
        "<p><b>The set is 3D Slicer's.</b> Its <i>Four-Up</i> layout is three orthogonal slice views (Red axial, Yellow " +
        "sagittal, Green coronal) plus the 3-D view. For a surface model the equivalent of those three slice normals is " +
        "looking along each anatomical axis, so the panes are " + p.map(function(q){ return "<b>" + esc(q.label) + "</b>"; }).join(", ") +
        ". Visible Body's own single-view presets are the same directions (“1: Anterior, 2: Posterior, 3: Right, " +
        "4: Left, 5: Superior, 6: Inferior”). <b>Our convention:</b> we found no documentation for a four-pane " +
        "layout in any commercial anatomy atlas, so the grid is Slicer's idea and which quadrant holds which pane is " +
        "ours &mdash; the free view sits where Slicer puts the 3-D one.</p>" +
        "<p><b>What stands down while four panes are on,</b> and why: the structure labels, the axis gnomon, the scale " +
        "bar, the cut outline, the part markers and the measuring chips are all drawn for <i>one</i> camera over the " +
        "whole canvas. Rather than draw them in the wrong place they are stood down; expand a pane (its square) and " +
        "they come straight back.</p>" +
        "<p>Entering four views, expanding a pane and restoring are <b>one Undo step</b> each, and the model reset puts " +
        "the page back to a single view.</p>";
    }});
    I.add({key:"q303facing", title:"“Facing me”: the rule, and the measurement behind it", order:26, build:function(){
      var V = window.NMSKViews;
      if (!V) return "<p>(not on this page)</p>";
      var L = V.last(), s = V.state();
      return "<p><b>The rule, in one line:</b> the camera looks along the structure's <b>axis of least spread</b> &mdash; " +
        "the minor principal axis of its own vertices.</p>" +
        "<p><b>Why one rule and not two.</b> The precedent is Blender's <i>View &gt; Align View to Active</i>, which " +
        "“orients the viewport along a local axis of the active object or bone” and, in Edit Mode, " +
        "“uses the normal of the active face instead” &mdash; an axis for a solid, a normal for a face. Our " +
        "structures are neither all rods nor all sheets, so the single rule was chosen because it becomes each of them: " +
        "for a <b>flat</b> structure the minor axis IS the surface normal, so the broad face turns toward you; for a " +
        "<b>tube</b> it lies across the shaft, so the long axis runs across the screen at full length instead of " +
        "pointing at you. It is also the largest picture of the structure there is: the silhouette's area goes as the " +
        "square root of the product of the other two eigenvalues, so looking along the smallest one wins by " +
        "&radic;(&lambda;&#8321;/&lambda;&#8323;). The per-structure numbers are measured on the real meshes, not asserted.</p>" +
        (L && L.ok && L.shape ? "<p><b>Last time you used it:</b> " + esc(L.label) + " &mdash; read as a <b>" + esc(L.shape) +
          "</b>, and the camera ended <b>" + L.angle_deg + "&deg;</b> off that axis (the limit is the az / el camera's own " +
          "pole, not the rule).</p>" : "") +
        "<p><b>Saved views.</b> Name the camera you are in and come back to it in one tap &mdash; the pattern Visible " +
        "Body documents as storing a view on a key and pressing that key again to return. Up to " + s.max +
        " of them, kept <b>in this browser only</b>, and neither reset touches them. There are " + s.saved.length +
        " saved on this page now. The standard views (front / side / back and the engine's own reset) are unchanged.</p>";
    }});
    I.add({key:"q303nerves", title:"Emphasising the nerves, including the small ones", order:28, build:function(){
      var N = window.NMSKNerves;
      if (!N) return "<p>(not on this page)</p>";
      var st = N.state(), c = st.census, ab = st.absent, sm = N.sample();
      return "<p><b>Why the small ones were invisible, measured and not guessed.</b> This page's own calibre table " +
        "(<code>nmsk-calibre</code>, Q240 &mdash; diameters measured off the meshes) gives every nerve a real diameter. " +
        "A whole-body view puts the body's full height into the height of the 3-D view, so at the moment " +
        "<b>1 pixel ≈ " + c.mmPerPx + " mm</b>: of the <b>" + c.n + "</b> nerve structures here, <b>" + c.subPixel +
        "</b> are drawn <b>under one pixel wide</b>. Nothing is wrong with the mesh, the decimation or the draw order &mdash; " +
        "the structure is simply sub-pixel, and no colour or opacity can rescue a line thinner than a pixel.</p>" +
        "<p><b>What the emphasis does.</b> An extra pass over the nerves' own vertices, drawn after everything, on the " +
        "camera-facing half of the model, each vertex a round dot whose width is " +
        "<code>max(the step's minimum, the nerve's true width in pixels)</code>. A nerve already wider than the minimum " +
        "is untouched. That is Q299's <i>minimum drawn width</i> for a thin section and Q300's <i>bone drawn once more " +
        "after the translucent pass</i>, applied to nerves &mdash; not a third invention. The steps are " +
        N.steps().map(function(s){ return "<b>" + esc(s.label) + "</b>" + (s.w ? " " + s.w + " px" : ""); }).join(" / ") + ".</p>" +
        "<p><b>The honesty rule.</b> No mesh is changed and no geometry is written. The <b>true calibre stays the " +
        "record</b> &mdash; it is what the structure's card and the vessel / nerve legend print, and " +
        (c.withDia ? "<b>" + c.withDia + "</b> of these nerves carry a measured diameter (" + c.diaMin + "–" + c.diaMax + " mm)" : "none of them carry one") +
        (c.noDia ? " while <b>" + c.noDia + "</b> have <b>no diameter on record</b> and take the step's minimum width flat" : "") +
        ". The emphasis is a <b>display aid</b> and is labelled as one wherever it appears.</p>" +
        (sm.length ? "<p><b>A large, a middling and a small one, at this zoom:</b> " + sm.map(function(r){
          return esc(r.name) + " &Oslash;&nbsp;" + r.dia_mm + "&nbsp;mm &rarr; " + r.truePx + "&nbsp;px drawn as " + r.drawnPx + "&nbsp;px";
        }).join("; ") + ".</p>" : "") +
        "<p><b>What it reaches, and whose answer that is.</b> Every structure this page's own calibre table records as a " +
        "<b>nerve</b> &mdash; <b>" + c.n + "</b> of them here, the trunks and every named branch, the small ones " +
        "included &mdash; chosen that way because the nerve <i>category</i> on these pages is wider than \u201ca " +
        "peripheral nerve\u201d: it also holds the spinal dura, the cord\u2019s tracts and its nuclei, and the " +
        "<code>cns</code> category holds the cord and the brain. None of those is a nerve anyone wants widened, and " +
        "together they are more than half the vertices in those categories, so " +
        (st.notCovered ? "<b>" + st.notCovered + "</b> structures are left exactly as they are" : "nothing else is touched") +
        ". The rule in force on this page is <b>" + esc(c.rule) + "</b>. The <b>motor points / NMJ markers</b> are the needle tool\u2019s " +
        "own overlay with its own <i>Emphasize motor points</i> toggle, which this control switches on with it rather " +
        "than drawing a second set that could fall out of step &mdash; that toggle is " +
        (st.motorPoints ? "on this page" : "not on the screen until the needle tool is open") + ".</p>" +
        (ab.missing.length ? "<p><b>What this page does not carry at all</b> (emphasis cannot show a nerve that is not " +
          "here, and Q299 found exactly this on the Imaging pages): " + ab.missing.map(esc).join(", ") + ". The control " +
          "says so on the screen too.</p>" : "<p>Every nerve on our conventional list of the major peripheral nerves is " +
          "present on this page.</p>");
    }});
  }

  var api = {
    start:function(opt){
      opt = opt || {};
      if (on) return api;
      O = opt;
      var hist = opt.history || window.NMSKHistory || null;
      if (opt.target && window.NMSKTarget) NMSKTarget.start(opt.target);
      if (opt.autofocus && window.NMSKAutoFocus) NMSKAutoFocus.start(opt.autofocus, {history:hist, target:window.NMSKTarget, anchor:opt.anchor});
      if (opt.fourup && window.NMSKFourUp) NMSKFourUp.start(opt.fourup, {history:hist, anchor:opt.anchor});
      if (opt.views && window.NMSKViews) NMSKViews.start(opt.views, {history:hist, target:window.NMSKTarget});
      if (opt.nerves && window.NMSKNerves) NMSKNerves.start(opt.nerves, {history:hist, level:opt.nerveLevel || 0});
      combos();
      infoSections();
      /* into Q301's OWN "View" group, not a new top-level button: progressive disclosure, short menus, one control bar */
      var G = window.NMSKGroups;
      if (G && G.addTo){
        if (window.NMSKFourUp) G.addTo("view", {el:NMSKFourUp.button("q301-b"), combo:"fourup"});
        if (window.NMSKViews) G.addTo("view", {el:NMSKViews.element()});
        if (window.NMSKAutoFocus) G.addTo("view", {el:focusElement()});
        if (window.NMSKNerves && NMSKNerves.element()) G.addTo("view", {el:NMSKNerves.element(), combo:"nerves"});
      }
      if (window.NMSKTips && NMSKTips.fold){ try { NMSKTips.fold(); } catch (err){} }
      if (window.NMSKInfo && NMSKInfo.refresh){ try { NMSKInfo.refresh(); } catch (e2){} }
      on = true;
      return api;
    },
    ready:function(){ return on; },
    state:function(){ return {on:on,
      target:window.NMSKTarget ? NMSKTarget.state() : null,
      autofocus:window.NMSKAutoFocus ? NMSKAutoFocus.state() : null,
      fourup:window.NMSKFourUp ? NMSKFourUp.state() : null,
      views:window.NMSKViews ? NMSKViews.state() : null,
      nerves:window.NMSKNerves ? NMSKNerves.state() : null}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKQ303;
