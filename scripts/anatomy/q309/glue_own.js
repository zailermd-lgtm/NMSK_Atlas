  /* ---- Q309: the systems as on/off buttons, and the depth peel with a scope ----
     Same shape as the Z engine's glue, so the two behave identically. */
  NMSKQ309.start({
    anchor:A.canvas, history:NMSKHistory, showall:NMSKShowAll, peel:window.NMSKPeel,
    engine:{
      cats:function(){ return Object.keys(on); },
      all:function(){
        var seen = {}, out = [];
        meshes.forEach(function(m){
          var s = m.userData;
          if (!s.id || seen[s.id]) return;
          seen[s.id] = 1; out.push({id:s.id, cat:s.cat, name:(s.rec && s.rec.name) ? s.rec.name : s.id});
        });
        return out;
      },
      off:function(ids){
        q309Off = {};
        (ids || []).forEach(function(i){ q309Off[i] = 1; });
        apply();
      },
      drawn:function(){
        var seen = {}, n = 0;
        meshes.forEach(function(m){ var s = m.userData; if (!m.visible || seen[s.id]) return; seen[s.id] = 1; n++; });
        return n;
      },
      drawnIn:function(cats){
        var S = {}; (cats || []).forEach(function(c){ S[c] = true; });
        var seen = {}, n = 0;
        meshes.forEach(function(m){ var s = m.userData; if (!S[s.cat] || !m.visible || seen[s.id]) return; seen[s.id] = 1; n++; });
        return n;
      },
      redraw:draw
    }
  });
