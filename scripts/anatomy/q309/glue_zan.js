      /* ---- Q309: the systems as on/off buttons, and the depth peel with a scope ----
         Everything shareable is in viewer/q309/; this is only what this engine knows about its own objects.
         Spliced by scripts/anatomy/q309/patch_engines_q309.py, identical in shape to the own engine's. */
      NMSKQ309.start({
        anchor:A.canvas, history:NMSKHistory, showall:NMSKShowAll, peel:window.NMSKPeel,
        engine:{
          cats:function(){ return LK.slice(); },
          /* one row per DISTINCT structure id, which is what every count in this round is measured in */
          all:function(){
            var seen = {}, out = [];
            OBJ.forEach(function(o){
              var id = o.id || o.name;
              if (!id || seen[id]) return;
              seen[id] = 1; out.push({id:id, cat:o.layer, name:o.name || id});
            });
            return out;
          },
          /* Q309's own veto set: exactly these ids hidden, everything else released. It is deliberately NOT the
             per-layer `on` table (the whole-body peel and the presets write that one) and NOT `hidden` (the card's
             own hide and Q300's "hidden: N" path own that one), so the three never overwrite each other. */
          off:function(ids){
            q309Off = new Set(ids || []);
            sync(); need = true;
          },
          drawn:function(){
            var seen = {}, n = 0;
            OBJ.forEach(function(o){ var id = o.id || o.name; if (seen[id] || !vis(o)) return; seen[id] = 1; n++; });
            return n;
          },
          drawnIn:function(cats){
            var S = {}; (cats || []).forEach(function(c){ S[c] = true; });
            var seen = {}, n = 0;
            OBJ.forEach(function(o){ var id = o.id || o.name; if (!S[o.layer] || seen[id] || !vis(o)) return; seen[id] = 1; n++; });
            return n;
          },
          redraw:function(){ need = true; }
        }
      });
