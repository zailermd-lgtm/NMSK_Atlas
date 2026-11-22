/* Q272 clinical workspace modes, WebGL engine: the host object hands the shared controller (viewer/modes/modes.js) the page's own
   public things only -- the canvas to dock, the pill toolbar for the "מצב" button, the generic add-on API (anatomyApi(), the same
   object the optional add-ons get), the current selection, the camera and the phone layer sheet for the exit snapshot / restore. */
NMSKModes.init({
  engine:"zan", model:document.getElementById("view"), toolbar:document.getElementById("topright"), toolClass:"pill",
  ready:function(){ var b = document.getElementById("boot"); return !!(selCtl && OBJ.length && (!b || b.classList.contains("done"))); },
  api:function(){ return anatomyApi(); },
  selectedId:function(){ return selected ? (selected.id || selected.name) : null; },
  select:function(id){ select(id && objsById[id] ? objsById[id][0] : null, false); },
  snapshot:function(){
    return {sel:selected ? (selected.id || selected.name) : null, cam:{az:cam.az, el:cam.el, dist:cam.dist, tgt:cam.tgt.slice()}, sheet:!!sheetOpen};
  },
  restore:function(s){
    cam.az = s.cam.az; cam.el = s.cam.el; cam.dist = s.cam.dist; cam.tgt = s.cam.tgt.slice();
    var cur = selected ? (selected.id || selected.name) : null;
    if (cur !== s.sel) select(s.sel && objsById[s.sel] ? objsById[s.sel][0] : null, false);
    if (!!sheetOpen !== s.sheet){ var sb = document.getElementById("btn-panel"); if (sb) sb.click(); }
    need = true;
  },
  resized:function(){ resize(); },
  isPhone:function(){ return window.innerWidth <= 760; }
});
window.__modesState = function(){ return NMSKModes.state(); };
