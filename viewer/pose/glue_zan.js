/* Q241 Pose, WebGL engine. The posed geometry is BAKED into the batch vertex buffers (gl.bufferSubData of the moved structures only: positions and normals), so the shaders, the picking /
   depth passes, the CUT clipping (uClip / uClip2 work on the posed positions), selection and the Symmetric view (the shader mirrors the posed vertices) need no change. Rest positions /
   normals are decoded lazily from the quantised blob when a structure first moves (nothing is kept for a structure that never moves). After a pose change: bounding boxes / centres
   (cut, isolation box, label anchors, the mirrored copies), the cut-cap cache and the labels are refreshed. Part markers and the clinical add-on tools use the
   rest-pose data (reset the pose before using them). */
var poseCtl = null, poseRestZ = {}, poseLiveZ = {}, poseCapT = 0;
function poseRestOfZ(i){
  var r = poseRestZ[i];
  if (r) return r;
  var rec = MAN.meshes[i], vc = rec.vc, ic = rec.ic, mn = rec.min, sp = rec.span, v, t;
  var qv = new Uint16Array(BIN.buffer, BIN.byteOffset + rec.vo, vc * 3), ix = new Uint16Array(BIN.buffer, BIN.byteOffset + rec.io, ic * 3);
  var pos = new Float32Array(vc * 3), nrm = new Float32Array(vc * 3);
  for (v = 0; v < vc * 3; v += 3){ pos[v] = mn[0] + qv[v] / 65535 * sp[0]; pos[v+1] = mn[1] + qv[v+1] / 65535 * sp[1]; pos[v+2] = mn[2] + qv[v+2] / 65535 * sp[2]; }
  for (t = 0; t < ic; t++){
    var a = ix[3*t], b = ix[3*t+1], c = ix[3*t+2], ax = pos[3*a], ay = pos[3*a+1], az = pos[3*a+2];
    var e1x = pos[3*b] - ax, e1y = pos[3*b+1] - ay, e1z = pos[3*b+2] - az, e2x = pos[3*c] - ax, e2y = pos[3*c+1] - ay, e2z = pos[3*c+2] - az;
    var nx = e1y*e2z - e1z*e2y, ny = e1z*e2x - e1x*e2z, nz = e1x*e2y - e1y*e2x;
    nrm[3*a] += nx; nrm[3*a+1] += ny; nrm[3*a+2] += nz; nrm[3*b] += nx; nrm[3*b+1] += ny; nrm[3*b+2] += nz; nrm[3*c] += nx; nrm[3*c+1] += ny; nrm[3*c+2] += nz;
  }
  for (v = 0; v < vc; v++){ var L = Math.hypot(nrm[3*v], nrm[3*v+1], nrm[3*v+2]) || 1; nrm[3*v] /= L; nrm[3*v+1] /= L; nrm[3*v+2] /= L; }
  return poseRestZ[i] = {pos:pos, nrm:nrm};
}
window.__poseLive = function(i){ return poseLiveZ[i] ? poseLiveZ[i].pos : null; };
poseCtl = NMSKPose({
  page:function(){ return "zan:" + ((MAN && MAN.variant) || "base_male") + ":" + OBJ.length; },
  count:function(){ return OBJ.length; },
  nverts:function(i){ return OBJ[i].vc; },
  rest:poseRestOfZ,
  live:function(i){ var L = poseLiveZ[i]; if (!L){ var r = poseRestOfZ(i); L = poseLiveZ[i] = {pos:new Float32Array(r.pos), nrm:new Float32Array(r.nrm)}; } return L; },
  touch:function(i){
    var o = OBJ[i], L = poseLiveZ[i];
    gl.bindBuffer(gl.ARRAY_BUFFER, o.batch.pb); gl.bufferSubData(gl.ARRAY_BUFFER, o.vOff * 12, L.pos);
    gl.bindBuffer(gl.ARRAY_BUFFER, o.batch.nb); gl.bufferSubData(gl.ARRAY_BUFFER, o.vOff * 12, L.nrm);
  },
  commit:function(ids){
    for (var k = 0; k < ids.length; k++){
      var o = OBJ[ids[k]], p = poseLiveZ[ids[k]].pos, lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9], j;
      for (j = 0; j < p.length; j += 3){
        if (p[j] < lo[0]) lo[0] = p[j]; if (p[j] > hi[0]) hi[0] = p[j]; if (p[j+1] < lo[1]) lo[1] = p[j+1]; if (p[j+1] > hi[1]) hi[1] = p[j+1]; if (p[j+2] < lo[2]) lo[2] = p[j+2]; if (p[j+2] > hi[2]) hi[2] = p[j+2];
      }
      o.bmin = lo; o.bmax = hi; o.center = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2]; o.radius = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2;
    }
    capGeomCache = {};
    if (labelsCtl) labelsCtl.dirty();
    if (capCtl && capCtl.isOn()){ clearTimeout(poseCapT); poseCapT = setTimeout(function(){ if (capCtl.isOn()){ capCtl.set(false); capCtl.set(true); } }, 350); }
    need = true;
  },
  parts:function(){ return partsCtl; },
  toolbar:document.getElementById("topright"), toolClass:"pill",
  isPhone:function(){ return window.innerWidth <= 900; }
});
window.__poseApi = poseCtl;
window.__poseDebug = function(){      /* test hook: per structure how far it moved from its rest position (max |dx| in mm), only structures the pose has touched */
  var out = {touched:0, moved:{}, bad:0, untouched:[], overflow:[], glErr:0};
  OBJ.forEach(function(o, i){
    var L = poseLiveZ[i], R = poseRestZ[i]; if (!L){ out.untouched.push([o.id, o.layer, Math.round(o.center[1])]); return; }
    var d = 0, k; out.touched++;
    gl.bindBuffer(gl.ARRAY_BUFFER, o.batch.pb); if (o.vOff * 12 + L.pos.byteLength > gl.getBufferParameter(gl.ARRAY_BUFFER, gl.BUFFER_SIZE)) out.overflow.push([o.id, o.vOff, o.vc]);
    for (k = 0; k < L.pos.length; k++){ var e = Math.abs(L.pos[k] - R.pos[k]); if (e > d) d = e; if (L.pos[k] !== L.pos[k]) out.bad++; }
    out.moved[o.id] = Math.round(d * 10) / 10;
  });
  out.fascia = OBJ.filter(function(o){ return o.layer === "fascia"; }).map(function(o){ return [o.id, !!poseLiveZ[OBJ.indexOf(o)], Math.round(o.bmin[0]), Math.round(o.bmax[0]), Math.round(o.bmin[1]), Math.round(o.bmax[1]), Math.round(o.bmin[2]), Math.round(o.bmax[2])]; });
  out.glErr = gl.getError();
  return out;
};
