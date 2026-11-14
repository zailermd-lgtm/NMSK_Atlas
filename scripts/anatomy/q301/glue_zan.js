      /* ---- Q301: the one control, the groups, the radiographic render styles, the depth peel, the fat default ----
         Everything shareable is in viewer/q301/; this is only what this engine draws with. Spliced by
         scripts/anatomy/q301/patch_engines_q301.py, which keeps it identical in shape to the own engine's. */
      NMSKQ301.start({
        anchor:A.canvas, history:NMSKHistory, showall:NMSKShowAll, modelreset:NMSKModelReset,
        /* X-ray step 0 (Soft) by default on THIS engine, by measurement rather than by symmetry: these pages carry
           3,252 meshes against the own engine's ~950, so a ray crosses three to four times as many shells and the same
           path length burns the highlights out (at 0.10 the luminance reached 206/255 with half the model in the top
           histogram bin). The own-engine pages default to Normal. Figures: data/derived/Q301_browser_report.json. */
        xrayStep:0,
        /* the model-wide render style. colOf() takes the grey, the fragment shader's DRR branch takes mu and d0. */
        render:{
          active:function(){ return q301.mode !== "colour"; },
          apply:function(sp){
            q301Grey.clear();
            if (!sp || sp.mode === "colour") q301 = {mode:"colour", grey:null, mu:null, d0:0.10, flatten:0};
            else q301 = {mode:sp.mode, d0:sp.d0 == null ? 0.10 : sp.d0, flatten:sp.flatten || 0,
              grey:function(o){ return sp.greyOf(o.layer, o.id, o.name, o.vt); },
              mu:sp.muOf ? function(o){ return sp.muOf(o.layer, o.id, o.name, o.vt); } : null};
            sync(); need = true;
          },
          redraw:function(){ need = true; },
          film:function(v){ document.documentElement.classList.toggle("q301-film", !!v); readColors(); need = true; }
        },
        /* the depth peel writes the same layer table the presets write -- which is why NMSKCombos calls them incompatible */
        peel:{
          cats:function(){ return LK.slice(); },
          count:function(k){ var n = 0; OBJ.forEach(function(o){ if (o.layer === k) n++; }); return n; },
          off:function(keys){
            var S = {}; keys.forEach(function(k){ S[k] = true; });
            LK.forEach(function(k){ on[k] = S[k] ? false : (k === "fat" ? (window.NMSKFat ? NMSKFat.on() : false) : true); });
            presetName = ""; sync(); need = true;
          },
          redraw:function(){ need = true; }
        },
        fat:{
          count:function(){ var n = 0; OBJ.forEach(function(o){ if (o.layer === "fat") n++; }); return n; },
          shown:function(){ return !!on.fat; },
          set:function(v){ on.fat = !!v; sync(); need = true; },
          redraw:function(){ need = true; }
        },
        /* one probe per action the compatibility matrix can name; nothing in NMSKCombos knows what any of them does */
        probes:[
          {key:"imaging", label:"Imaging style", active:function(){ return q301.mode !== "colour"; }},
          {key:"cut", label:"Cut", active:function(){ return !!(cutCtl && cutCtl.state().on); }},
          {key:"xsec", label:"Cross-section", active:function(){ return !!(xsecCtl && xsecCtl.isOn()); }},
          {key:"peel", label:"Depth peel", active:function(){ return !!(window.NMSKPeel && NMSKPeel.step() > 0); }},
          {key:"fat", label:"Fat shown", active:function(){ return !!on.fat; }},
          {key:"preset", label:"Tissue preset", active:function(){ return !!presetName && presetName !== "all"; }},
          {key:"solo", label:"Solo one layer", active:function(){ return !!soloLayer; }},
          {key:"boneread", label:"Bone through soft tissue", active:function(){ return !!(window.NMSKBoneRead && NMSKBoneRead.level() > 0); }},
          {key:"highlight", label:"Highlight the marked", active:function(){ return !!(selCtl && selCtl.active() && selCtl.state().sel === "hl"); }},
          {key:"measure", label:"Measure", active:function(){ return !!(window.NMSKMeasure && NMSKMeasure.state().open); }},
          {key:"spin", label:"Spin", active:function(){ var b = document.getElementById("btn-spin"); return !!(b && b.classList.contains("on")); }},
          {key:"marktap", label:"Mark by tapping", active:function(){ var b = document.getElementById("sel-markmode"); return !!(b && b.getAttribute("aria-pressed") === "true"); }},
          {key:"cutplace", label:"Place the cut on the model", active:function(){ var b = document.getElementById("cut-place"); return !!(b && b.getAttribute("aria-pressed") === "true"); }},
          {key:"srccolour", label:"Colour by source", active:function(){ var b = document.getElementById("src-colour"); return !!(b && b.getAttribute("aria-pressed") === "true"); }}
        ],
        /* the page-wide prose moves behind the circled i: the button that opens the licence sheet, and the per-structure
           source panel. The STRUCTURE CARD keeps saying where its own geometry comes from -- Q297 found cards that lied
           about that, so it does not move out of reach, it only stops taking the screen. */
        adopt:[{key:"sources", title:"Sources and licence", order:90, id:"about-btn"},
               {key:"srcpanel", title:"Where each structure's geometry comes from", order:92, id:"src-sec"}],
        /* verification hooks: a screenshot of this canvas is not reliable under software rendering (Q300) */
        shot:function(){ draw(); },
        gl:function(){ return gl; }
      });
      /* the cut face keeps its fat whatever the 3-D state is; this reports exactly the predicate the patched builder uses */
      window.__q301capFat = function(){
        var total = 0, filled = 0;
        OBJ.forEach(function(o){
          if (o.layer !== "fat") return;
          total++;
          if (vis(o) || (!on.fat && !hidden.has(o) && passClip(o) && passBox(o))) filled++;
        });
        return {total:total, filled:filled, shown:!!on.fat,
                capA:NMSKCapCore.capA({cat:"fat", alpha:Math.max(0.9, alphaFor.fat)})};
      };
