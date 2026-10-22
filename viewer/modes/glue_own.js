/* Q272 clinical workspace modes, three.js engine: the host object hands the shared controller (viewer/modes/modes.js) the page's own
   public things only -- the 3-D container to dock, the toolbar for the "מצב" button, the generic add-on API (anatomyApi(), the same
   object the optional add-ons get), the current selection, the camera and the phone sheets for the exit snapshot / restore. */
NMSKModes.init({
  engine:"own", model:document.getElementById("app"), toolbar:document.getElementById("tools"), toolClass:"tool",
  ready:function(){ return !!(selCtl && meshes && meshes.length); },
  api:function(){ return anatomyApi(); },
  selectedId:function(){ return selected || null; },
  select:function(id){ select(id || null); },
  snapshot:function(){
    return {sel:selected || null, cam:{az:az, el:el, dist:dist, t:target.toArray()},
            sheet:asideEl.classList.contains("open") ? "list" : (inspEl.classList.contains("open") ? "info" : null)};
  },
  restore:function(s){
    az = s.cam.az; el = s.cam.el; dist = s.cam.dist; target.fromArray(s.cam.t); place();
    if ((selected || null) !== s.sel) select(s.sel);
    if (app.classList.contains("phone")) openSheet(s.sheet);
    draw();
  },
  resized:function(){ resize(); draw(); },
  isPhone:function(){ return window.innerWidth <= 760; }
});
window.__modesState = function(){ return NMSKModes.state(); };
