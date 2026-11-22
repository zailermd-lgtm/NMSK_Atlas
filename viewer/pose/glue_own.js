/* Q241 Pose, three.js engine. The posed geometry is BAKED into each mesh's own position / normal attributes (rest copies are made lazily the first time a structure moves), so everything that
   reads the geometry follows the pose with no extra code: picking (raycast), the Cut mode clipping, the filled cut face, the label anchors, the Symmetric view copies (they share the geometry).
   After a pose change the bounding boxes / spheres are recomputed, the labels are told, and the filled cut face is rebuilt (debounced). Part markers use the rest-pose data; add-ons can follow the pose through window.__poseRev / __poseLive / __poseRestPos (Q320). */
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
  /* Q318: where a point of the model lands on the screen, for the rings (model frame, as everything here is) */
  toScreen:function(p){
    var v = root.localToWorld(new THREE.Vector3(p[0], p[1], p[2])).project(camera);
    if (v.z > 1) return null;
    var r = renderer.domElement.getBoundingClientRect();
    return [r.left + (v.x + 1) / 2 * r.width, r.top + (1 - v.y) / 2 * r.height];
  },
  canvasRect:function(){ return renderer.domElement.getBoundingClientRect(); },
  toolbar:document.getElementById("tools"), toolClass:"tool",
  isPhone:function(){ return !!app && app.classList.contains("phone"); }
});
window.__poseApi = poseCtl;
/* Q320: the posed / rest vertices of a structure the pose has touched (null for one it never moved), same contract as the WebGL engine */
window.__poseLive = function(i){ return poseRestG[i] ? meshes[i].geometry.attributes.position.array : null; };
window.__poseRestPos = function(i){ return poseRestG[i] ? poseRestG[i].pos : null; };
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
