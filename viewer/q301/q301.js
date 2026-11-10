/* Q301: the boot. One call per page, from each engine's own glue -- everything engine specific is in the adaptors the
   glue passes in, so the two engines behave identically and this file is the only place the round's wiring lives.
   It also writes the i panel's own sections, because they are generated from the real data (NMSKTissue's status counts,
   NMSKCombos' table, NMSKPeel's order) and must never be prose anyone can let fall out of date.
     NMSKQ301.start({anchor, history, modelreset, showall, tissueUrl, render:E, peel:E, fat:E, groups:[...], adopt:{...}})
     .ready()  .state() */
var NMSKQ301 = (function(){
  "use strict";
  var on = false, O = null, loaded = false;
  function esc(s){ return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function infoSections(){
    var I = window.NMSKInfo; if (!I) return;
    I.add({key:"what", title:"What this page is, and what it is not", order:10, openFirst:true, build:function(){
      var h = (window.NMSKTissue && NMSKTissue.ready()) ? NMSKTissue.honesty() : [];
      return "<p>Every mesh on this page is a <b>segmented anatomical surface</b>, not an image. The radiographic styles " +
        "(X-ray, CT, MRI) are a <b>simulation computed from those surfaces</b> and from this page's own clinical tissue reference. " +
        "They contain no patient image and no scan.</p>" +
        (h.length ? "<p>The reference's own words:</p><ul>" + h.slice(0, 3).map(function(x){ return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>" : "");
    }});
    I.add({key:"styles", title:"X-ray / CT / MRI: what is measured, what is our convention", order:20, build:function(){
      var T = window.NMSKTissue;
      if (!T || !T.ready()) return "<p>The clinical tissue reference has not loaded on this page, so the radiographic styles are unavailable.</p>";
      var p = T.provenance(), by = p.byStatus || {};
      var wins = T.windows(), seqs = T.sequences(), MK = T.mskSequences ? T.mskSequences() : [];
      var out = "<p><b>Where the numbers come from.</b> " + esc(p.title || "the project's clinical tissue reference") +
        " &mdash; " + p.classes + " tissue classes, re-checked on " + esc(p.verifiedOn || "?") + ", shipped with this page by its clinical layer. " +
        "Nothing is retyped in the viewer.</p><p><b>How honest each number is</b>, in the table's own words: " +
        Object.keys(by).sort().map(function(k){ return "<b>" + by[k] + "</b> " + esc(k.replace(/_/g, " ")); }).join(", ") + ".</p>" +
        "<p><b>X-ray</b> is a digitally reconstructed radiograph: I/I&#8320; = exp(&minus;&Sigma;&mu;&#7522;d), with " +
        "&mu;/&mu;<sub>water</sub> = 1 + v/1000 &mdash; the definition of the CT attenuation unit, so no choice of ours. " +
        "Ordinary alpha compositing over black accumulates exactly that product, and because the product does not care " +
        "about the order, nothing has to be depth sorted. Each closed surface is crossed twice, front and back, as a real beam does. " +
        "<b>Our convention:</b> <i>d</i>, the path length taken through each crossing &mdash; a surface atlas has no " +
        "thickness along the ray, so the three steps (Soft / Normal / Hard) are a scale we chose, not millimetres we measured. " +
        "This style does not use Q300's extra bone pass: the bone separates by its own attenuation.</p>" +
        "<p><b>CT</b> paints each structure the grey its own HU gives through a real window, " +
        "grey = (HU &minus; (L &minus; W/2)) / W, clipped: " +
        wins.map(function(w){ return "<b>" + esc(w.label) + "</b> W" + w.width + " / L" + w.level + (w.note ? " (" + esc(w.note) + ")" : ""); }).join("; ") +
        ". The MSK window is <b>our own convention</b> and the data file says so itself.</p>" +
        "<p><b>MRI</b> paints each structure its spin-echo signal, S = PD&middot;(1&minus;e<sup>&minus;TR/T1</sup>)&middot;e<sup>&minus;TE/T2</sup>, " +
        "summed over the class's water and fat pools, with the fat pool scaled down when the sequence suppresses fat: " +
        seqs.filter(function(s){ return MK.indexOf(s.key) >= 0; })
            .map(function(s){ return "<b>" + esc(s.label) + "</b> TR " + s.tr + " / TE " + s.te; }).join("; ") +
        ". The numbers are for <b>1.5 T</b>. <b>Our convention:</b> the greys are normalised across the classes on this " +
        "page so the picture uses its full range &mdash; an MRI's absolute signal is arbitrary anyway.</p>" +
        "<p><b>What a surface atlas cannot do.</b> A bone is one shell, so it is drawn throughout as cortical bone: " +
        "there is no cortex-versus-marrow difference, because the mesh has no inside.</p>";
      return out;
    }});
    I.add({key:"combine", title:"Which actions can be combined, and which cannot", order:30, build:function(){
      var C = window.NMSKCombos;
      if (!C) return "<p>(not available)</p>";
      var m = C.matrix();
      if (!m.length) return "<p>Nothing on this page needs the warning.</p>";
      return "<p>Checked in a real browser, not assumed. A pair that is not listed simply works.</p><table><tr><th>and</th><th>with</th><th></th><th>why</th></tr>" +
        m.map(function(r){
          var v = r.ok === "over" ? "yes, one leads" : r.ok ? "yes" : "no";
          return "<tr><td>" + esc(r.a) + "</td><td>" + esc(r.b) + "</td><td>" + v + "</td><td>" + esc(r.why) + "</td></tr>";
        }).join("") + "</table>";
    }});
    I.add({key:"layers", title:"The depth control: the order, and what in it is ours", order:40, build:function(){
      var P = window.NMSKPeel;
      if (!P || !P.state().on) return "<p>(not on this page)</p>";
      var st = P.steps();
      return "<p>One control for how deep, in " + st.length + " taps, from the skin inward &mdash; next to the per-system " +
        "controls, which are unchanged. The order is this page's own tissue categories:</p><ol>" +
        st.map(function(s){ return "<li><b>" + esc(s.label) + "</b> &mdash; <code>" + s.cats.join(", ") + "</code></li>"; }).join("") +
        "</ol><p>What is left at the end is <b>bone and cartilage</b>.</p>" +
        "<p>The <b>fat step is the superficial fascia</b>, by the structures' own Latin names: 17 of the 51 subcutaneous-fat " +
        "meshes are labelled <i>Panniculus adiposus (tela subcutanea)</i>. What this atlas does not carry is a separate " +
        "<b>membranous (Scarpa's) layer</b>, and the pages' own search data already says so: &ldquo;No page ships it as a mesh: " +
        "the abdominal wall on these pages carries <code>Investing abdominal fascia</code> and the subcutaneous fat, not a " +
        "separate membranous layer.&rdquo; The deep-fascia step holds the 61 investing sheets, septa and aponeuroses.</p>" +
        "<p><b>Our convention, not anatomy:</b> <b>vessels, nerves and lymphatics come off together</b>, because the data " +
        "holds no depth rank for a single vessel and real vessels cross every layer.</p>";
    }});
    I.add({key:"resets", title:"The two resets, and what each one touches", order:50, build:function(){
      var M = window.NMSKModelReset;
      var s = M && M.scope ? M.scope() : null;
      return "<p><b>Module</b> puts the tool you are in back to its own defaults. <b>Model</b> puts the model back to how " +
        "this page loaded. Both are a single Undo step.</p>" +
        (s ? "<p><b>Model touches:</b> " + esc(s.touches) + ".</p><p><b>Model leaves alone:</b> " + esc(s.keeps) + ".</p>" : "");
    }});
    I.add({key:"fat", title:"Fat: off at load, and still filling every cut face", order:60, build:function(){
      var F = window.NMSKFat, st = F && F.state ? F.state() : null;
      return "<p>Fat and unlabelled soft tissue (Q295) is built from each body's <b>own imaging</b>, in the space no " +
        "segmented structure covers. It is <b>off when the page loads</b>, as asked, and one tap in the Layers group shows it. " +
        "Either way it <b>keeps filling the cut faces and the cross-sections</b>, because a section drawn without it reads " +
        "as hollow &mdash; which is the whole reason Q295 built it.</p>" +
        (st ? "<p>This page carries <b>" + st.count + "</b> such structures.</p>" : "");
    }});
  }
  /* The group list is the SAME on both engines, by id. NMSKGroups drops a member whose ids are not on this page and a
     group that ends up empty, so one list serves six pages and two engines -- that is what keeps them behaving alike.
     `el` members are the boxes the Q301 modules build; everything else is an EXISTING button, moved here with its id
     and its listeners intact, which is why no behaviour is duplicated and the old crowded bars empty themselves.
     Long tables (the tissue-layer rows with their own sliders and solo buttons) are NOT moved in: the project's rule is
     short menus, so the group offers the button that opens that panel instead. */
  function defaultGroups(){
    var R = window.NMSKRenderStyle, P = window.NMSKPeel, F = window.NMSKFat;
    return [
      /* Q318: the order is the owner's own list. Search first, because finding a structure is where
         almost every session starts, and the colour of what is selected belongs with it. */
      {key:"mark", label:"Search", title:"Find a structure by any of its names, mark it, isolate it, and label it", members:[
        {adopt:["t-iso", "t-only", "t-invert", "t-mark"]},
        {combo:"marktap", adopt:["sel-markmode"]},
        {adopt:["sel-markcur", "sel-clear", "ss-q-all", "sel-p-isolate", "sel-p-fadeoth", "sel-p-hidesel"]},
        {combo:"highlight", adopt:["sel-p-hlsel"]},
        {adopt:["box-clear"]},
        /* Q318, owner's choice: Learn folds in here. Labels, the quick view and the legend all say something
           about the structure you have just found, so they belong with finding it. */
        {adopt:["t-learn", "t-labels", "t-quick", "t-nervegroups", "t-parts", "lab-legend-btn"]}
      ]},
      {key:"systems", label:"Systems", title:"Which systems are shown, how deep to peel into them, and the fat", members:[
        {el:P && P.state().on ? document.getElementById("pl-box") : null, combo:"peel"},
        {el:F && F.state().on ? document.getElementById("ft-box") : null, combo:"fat"},
        {adopt:["btn-panel"], label2:"The full tissue-layer table, with its own opacity and solo controls, opens in the side panel."},
        {combo:"preset", adopt:["btn-solid", "btn-bones", "btn-neuro", "btn-vasc", "btn-organs", "btn-insert"]},
        {adopt:"sides"},
        {combo:"srccolour", adopt:["src-colour"]}       /* the toggle lives here; its per-structure list stays in the i */
      ]},
      {key:"cut", label:"Dissection", title:"Dissect the model, and the cross-sections", members:[
        {combo:"cut", adopt:["t-cut"]},
        {adopt:["cut-exit", "cut-place", "cut-reset", "cut-flip"]},
        {adopt:["t-slices", "lab-cutfill"]}
      ]},
      /* Q318: the older X-ray left this entry. It was a transparency preset sitting beside the real
         radiographic styles, and its own note had to say so -- exactly the kind of button the owner
         meant. It stays on the page where it was defined; it is simply no longer offered here. */
      {key:"imaging", label:"Imaging", title:"How the model itself is drawn: colour, X-ray, CT, MRI", members:[
        {el:R && R.state().on ? document.getElementById("rs-box") : null, combo:"imaging"},
        {combo:"boneread", adopt:"br-box"}
      ]},
      {key:"pose", label:"Pose", title:"Move the joints, each only through its own normal range", members:[
        {adopt:["btn-pose"]}
      ]},
      {key:"measure", label:"Measure", title:"Measure on the model", members:[
        {combo:"measure", adopt:["t-measure"]}
      ]},
      /* adopted once the private add-on has put its button on the page; the sheet is painted again
         after that, and a member whose id is not there yet is simply not shown */
      {key:"needle", label:"Needle", title:"Plan an injection: entry, target, direction, and what the path crosses", members:[
        {adopt:["t-needle"]}
      ]},
      {key:"favorites", label:"Favorites", title:"Keep the way the model is set up now, under a name, and come back to it", members:[
        {el:window.NMSKFavorites ? NMSKFavorites.element() : null}
      ]},
      /* Q318: the second row, with undo / redo / the resets -- moving the model is not one of the eight
         things you DO to it, and this is the row that will also carry the navigation-tool picker. */
      /* Q318: the corner this row replaces. Adopting them empties #topright, the same way every other
         adoption empties the bar it came from, so nothing is drawn twice. */
      {key:"page", label:"Page", row2:true, title:"The other models, this one's sources, and which workspace is open", members:[
        {adopt:["t-mode"]},
        {adopt:["t-hub", "about-btn"]}
      ]},
      {key:"view", label:"Navigate", row2:true, title:"Where you look from, and how the screen is laid out", members:[
        {adopt:"foot"},                                  /* the Z engine's front / side / back / move / spin / reset row */
        {adopt:["t-reset", "t-lay3", "t-layout", "sym-select"]},
        {combo:"spin", adopt:"btn-spin"}
      ]}
    ].map(function(g){ g.members = g.members.filter(function(m){ return m.el || m.adopt || m.label; }); return g; });
  }
  var api = {
    start:function(opt){
      opt = opt || {};
      if (on) return api;
      O = opt;
      var hist = opt.history || window.NMSKHistory || null, sa = opt.showall || window.NMSKShowAll || null;
      if (window.NMSKCombos) NMSKCombos.start({probes:opt.probes || []});
      if (window.NMSKInfo) NMSKInfo.start({anchor:opt.anchor});
      infoSections();
      (opt.adopt || []).forEach(function(a){
        var e = document.getElementById(a.id);
        if (e && window.NMSKInfo) NMSKInfo.adoptEl(a.key, a.title, e, a.order);
      });
      if (opt.fat && window.NMSKFat) NMSKFat.start(opt.fat, {history:hist, showall:sa});
      if (opt.peel && window.NMSKPeel) NMSKPeel.start(opt.peel, {history:hist, showall:sa});
      if (window.NMSKFavorites) NMSKFavorites.start({history:hist});          /* Q318: named set-ups, before the bar is built */
      if (opt.render && window.NMSKRenderStyle) NMSKRenderStyle.start(opt.render, {history:hist, showall:sa, xrayStep:opt.xrayStep,
        sample:function(st){ return api.pixels(st); }});      /* Q318: AUTO measures the frame, it does not guess it */
      if (window.NMSKGroups) NMSKGroups.start({anchor:opt.anchor, history:hist, modelreset:opt.modelreset || window.NMSKModelReset,
        info:window.NMSKInfo, combos:window.NMSKCombos, groups:(opt.groups || defaultGroups()).concat(opt.extraGroups || [])});
      if (window.NMSKTips && NMSKTips.fold) { try { NMSKTips.fold(); } catch (e){} }   /* the modules' own nmsk-tip notes get folded behind the small "i", as every panel's do */
      on = true;
      /* the clinical layer owns the reference and its file name: ask for it, then let the styles light up */
      if (window.NMSKTissue){
        NMSKTissue.load().then(function(){
          loaded = true;
          if (window.NMSKRenderStyle) NMSKRenderStyle.refresh();
          if (window.NMSKInfo) NMSKInfo.refresh();
          if (window.NMSKGroups) NMSKGroups.refresh();
        }).catch(function(){ loaded = false; });
      }
      return api;
    },
    groupSpec:defaultGroups,
    ready:function(){ return on && loaded; },
    /* Verification only. page.screenshot returns a stale frame in this environment (Q300's finding), so the frame is
       forced and read back here, inside the page: O.shot() draws exactly one frame, O.gl() hands over the context.
       Returns what proves a style really changed -- how grey the picture is and where its brightness sits. */
    pixels:function(step){
      if (!O || typeof O.shot !== "function" || typeof O.gl !== "function") return null;
      try { O.shot(); } catch (e){ return null; }
      var gl = O.gl(); if (!gl) return null;
      var w = gl.drawingBufferWidth | 0, h = gl.drawingBufferHeight | 0;
      if (!(w > 0 && h > 0)) return null;
      var buf = new Uint8Array(w * h * 4);
      try { gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf); } catch (e2){ return null; }
      /* The background has to be excluded or it swamps the statistics: one engine clears to transparent, the other to an
         OPAQUE light grey, which would read as 90 % of a bright picture. The four corners of these views are always
         field, so the field colour is taken from them and pixels within 6/255 of it are skipped. */
      function at(x, y){ var o = ((y | 0) * w + (x | 0)) * 4; return [buf[o], buf[o+1], buf[o+2], buf[o+3]]; }
      var C = [at(1, 1), at(w - 2, 1), at(1, h - 2), at(w - 2, h - 2)];
      function isField(r, g, bl, a){
        if (a < 9) return true;
        for (var k = 0; k < 4; k++){
          var c = C[k];
          if (Math.abs(r - c[0]) <= 6 && Math.abs(g - c[1]) <= 6 && Math.abs(bl - c[2]) <= 6 && Math.abs(a - c[3]) <= 8) return true;
        }
        return false;
      }
      var s = Math.max(1, step | 0 || 2), n = 0, lum = 0, sat = 0, grey = 0, hist = [0,0,0,0,0,0,0,0], lum2 = 0;
      var h64 = new Float64Array(64), k64;                 /* Q318: finer bins, for AUTO's percentiles. The eight-bin
                                                              hist above is untouched -- the verify scripts read it. */
      for (var y = 0; y < h; y += s) for (var x = 0; x < w; x += s){
        var o = (y * w + x) * 4, r = buf[o], g = buf[o+1], b = buf[o+2], a = buf[o+3];
        if (isField(r, g, b, a)) continue;
        var mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = 0.299*r + 0.587*g + 0.114*b;
        n++; lum += l; lum2 += l * l; sat += (mx - mn);
        if (mx - mn <= 6) grey++;
        hist[Math.min(7, Math.floor(l / 32))]++;
        h64[Math.min(63, Math.floor(l / 4))]++;
      }
      if (!n) return {n:0};
      for (k64 = 0; k64 < 64; k64++) h64[k64] /= n;
      return {n:n, w:w, h:h, field:C[0], lum:lum / n, sd:Math.sqrt(Math.max(0, lum2 / n - (lum / n) * (lum / n))),
        sat:sat / n, greyFrac:grey / n, hist:hist.map(function(v){ return v / n; }), h64:h64};
    },
    state:function(){ return {on:on, tissue:loaded,
      groups:window.NMSKGroups ? NMSKGroups.state() : null,
      render:window.NMSKRenderStyle ? NMSKRenderStyle.state() : null,
      peel:window.NMSKPeel ? NMSKPeel.state() : null,
      fat:window.NMSKFat ? NMSKFat.state() : null,
      combos:window.NMSKCombos ? NMSKCombos.state() : null,
      info:window.NMSKInfo ? NMSKInfo.state() : null}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKQ301;
