  /* ---- Q301: the one control, the groups, the radiographic render styles, the depth peel, the fat default ----
     Same shape as the Z engine's glue, so the two behave identically; only the drawing differs. */
  NMSKQ301.start({
    anchor:A.canvas, history:NMSKHistory, showall:NMSKShowAll, modelreset:NMSKModelReset,
    /* X-ray step 1 (Normal) by default on THIS engine: with ~950 meshes the measured contrast of the whole-body
       projection peaks at this path length (luminance sd 56.6 against 44.9 at Soft and 54.7 at Hard, and only 7 % of
       the model in the top histogram bin). The Z pages default to Soft, for the reason written beside their own call. */
    xrayStep:1,
    render:{
      active:function(){ return !!q301spec; },
      apply:function(sp){ q301spec = (sp && sp.mode !== "colour") ? sp : null; apply(); draw(); },
      redraw:draw,
      film:function(v){ document.documentElement.classList.toggle("q301-film", !!v); draw(); }
    },
    peel:{
      cats:function(){ return Object.keys(on); },
      count:function(k){ var n = 0; meshes.forEach(function(m){ if (m.userData.cat === k) n++; }); return n; },
      off:function(keys){
        var S = {}; keys.forEach(function(k){ S[k] = true; });
        Object.keys(on).forEach(function(k){ on[k] = S[k] ? false : (k === "fat" ? (window.NMSKFat ? NMSKFat.on() : false) : true); });
        apply();
      },
      redraw:draw
    },
    fat:{
      count:function(){ var n = 0; meshes.forEach(function(m){ if (m.userData.cat === "fat") n++; }); return n; },
      shown:function(){ return !!on.fat; },
      set:function(v){ on.fat = !!v; apply(); },
      redraw:draw
    },
    probes:[
      {key:"imaging", label:"Imaging style", active:function(){ return !!q301spec; }},
      {key:"cut", label:"Cut", active:function(){ return !!(cutCtl && cutCtl.state().on); }},
      {key:"xsec", label:"Cross-section", active:function(){ return !!(xsecCtl && xsecCtl.isOn()); }},
      {key:"peel", label:"Depth peel", active:function(){ return !!(window.NMSKPeel && NMSKPeel.step() > 0); }},
      {key:"fat", label:"Fat shown", active:function(){ return !!on.fat; }},
      {key:"preset", label:"Tissue preset", active:function(){ return !!xray; }},
      {key:"solo", label:"Isolate", active:function(){ return !!iso; }},
      {key:"boneread", label:"Bone through soft tissue", active:function(){ return !!(window.NMSKBoneRead && NMSKBoneRead.level() > 0); }},
      {key:"highlight", label:"Highlight the marked", active:function(){ return !!(selCtl && selCtl.active() && selCtl.state().sel === "hl"); }},
      {key:"measure", label:"Measure", active:function(){ return !!(window.NMSKMeasure && NMSKMeasure.state().open); }},
      {key:"marktap", label:"Mark by tapping", active:function(){ var b = document.getElementById("sel-markmode"); return !!(b && b.getAttribute("aria-pressed") === "true"); }},
      {key:"cutplace", label:"Place the cut on the model", active:function(){ var b = document.getElementById("cut-place"); return !!(b && b.getAttribute("aria-pressed") === "true"); }},
      {key:"srccolour", label:"Colour by source", active:function(){ var b = document.getElementById("src-colour"); return !!(b && b.getAttribute("aria-pressed") === "true"); }}
    ],
    adopt:[{key:"sources", title:"Sources and licence", order:90, id:"about-btn"},
           {key:"srcpanel", title:"Where each structure's geometry comes from", order:92, id:"src-sec"}],
    shot:draw,
    gl:function(){ return renderer.getContext(); }
  });
  window.__q301capFat = function(){
    var total = 0, filled = 0;
    meshes.forEach(function(m){
      var s = m.userData;
      if (s.cat !== "fat") return;
      total++;
      if (m.visible || (!on.fat && !hideOverride[s.id] && (!s.hidden_default || !!hdShown[s.id]))) filled++;
    });
    return {total:total, filled:filled, shown:!!on.fat,
            capA:NMSKCapCore.capA({cat:"fat", alpha:Math.max(0.9, sysAlpha.fat == null ? 0.12 : sysAlpha.fat)})};
  };
