/* Q241 Pose, three.js engine. The posed geometry is BAKED into each mesh's own position / normal attributes (rest copies are made lazily the first time a structure moves), so everything that
   reads the geometry follows the pose with no extra code: picking (raycast), the Cut mode clipping, the filled cut face, the label anchors, the Symmetric view copies (they share the geometry).
   After a pose change the bounding boxes / spheres are recomputed, the labels are told, and the filled cut face is rebuilt (debounced). Part markers and the clinical add-on tools use the rest-pose data (reset the pose before using them). */
var poseCtl = null, poseRestG = {}, poseCapT = 0;
function poseRestOf(i){
  var r = poseRestG[i];
  if (!r){ var g = meshes[i].geometry; r = poseRestG[i] = {pos:new Float32Array(g.attributes.position.array), nrm:new Float32Array(g.attributes.normal.array)}; }
  return r;
}
poseCtl = NMSKPose({
  page:function(){ return "own:" + document.title; },
  count:function(){ return meshes.length; },
  nverts:function(i){ return meshes[i].geometry.attributes.position.count; },
  rest:poseRestOf,
  live:function(i){ var g = meshes[i].geometry; return {pos:g.attributes.position.array, nrm:g.attributes.normal.array}; },
  touch:function(i){ var g = meshes[i].geometry; g.attributes.position.needsUpdate = true; g.attributes.normal.needsUpdate = true; },
  commit:function(ids){
    for (var k = 0; k < ids.length; k++){ var g = meshes[ids[k]].geometry; g.computeBoundingBox(); g.computeBoundingSphere(); }
    if (labelsCtl) labelsCtl.dirty();
    if (capCtl && capCtl.isOn()){ clearTimeout(poseCapT); poseCapT = setTimeout(function(){ if (capCtl.isOn()){ capCtl.set(false); capCtl.set(true); } }, 350); }
    draw();
  },
  parts:function(){ return partsCtl; },
  toolbar:document.getElementById("tools"), toolClass:"tool",
  isPhone:function(){ return !!app && app.classList.contains("phone"); }
});
window.__poseApi = poseCtl;
window.__poseDebug = function(){      /* test hook: per structure how far it moved from its rest position (max |dx| in mm), only structures the pose has touched */
  var out = {touched:0, moved:{}, bad:0};
  meshes.forEach(function(m, i){
    var R = poseRestG[i]; if (!R) return;
    var a = m.geometry.attributes.position.array, d = 0, k; out.touched++;
    for (k = 0; k < a.length; k++){ var e = Math.abs(a[k] - R.pos[k]); if (e > d) d = e; if (a[k] !== a[k]) out.bad++; }
    out.moved[m.userData.id + "#" + i] = Math.round(d * 10) / 10;
  });
  return out;
};
