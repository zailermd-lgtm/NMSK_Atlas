/* Q237 Symmetric view, three.js engine: a mirrored copy of every source-side mesh (the same geometry under a reflection matrix; three.js flips the winding by itself for a
   negative determinant), a clone of the source material that follows its colour / opacity / visibility and takes the SAME clipping planes as the originals (Cut mode); the
   hidden side's originals are switched off after every apply(). Nothing is written to the data. */
var symCtl = null, symSpec = null, symCopies = [], symNormal = null;
function symClear(){ symCopies.forEach(function(c){ root.remove(c); c.material.dispose(); }); symCopies = []; }
function symSet(spec){
  symClear(); symSpec = spec || null;
  if (spec){
    var M = new THREE.Matrix4(); M.set.apply(M, spec.matrix);          // row-major, in the model's millimetre frame (the children of root)
    meshes.forEach(function(m){
      if (!spec.srcSet[m.userData.id]) return;
      var c = new THREE.Mesh(m.geometry, m.material.clone());
      c.matrixAutoUpdate = false; c.matrix.copy(M); c.matrixWorldNeedsUpdate = true;
      c.renderOrder = m.renderOrder; c.userData = {symSrc: m};
      root.add(c); symCopies.push(c);
    });
  }
  apply();
}
function symSync(){
  if (!symSpec) return;
  meshes.forEach(function(m){ if (symSpec.hideSet[m.userData.id]) m.visible = false; });
  symCopies.forEach(function(c){
    var m = c.userData.symSrc, a = c.material, b = m.material;
    c.visible = m.visible; a.color.copy(b.color); a.emissive.copy(b.emissive); a.opacity = b.opacity; a.transparent = b.transparent; a.depthWrite = b.depthWrite;
    a.clippingPlanes = cut.on ? cutPlanes : null;
  });
}
function symCap(out){          /* the filled cut face also takes the mirrored copies (reflected positions; the fill is parity based, so the reversed winding does not matter) */
  if (!symSpec) return;
  var n = symSpec.plane.n, d = symSpec.plane.d;
  symCopies.forEach(function(c){
    if (!c.visible) return;
    var m = c.userData.symSrc, s = m.userData, col = c.material.color, g = m.geometry;
    out.push({key:s.id, name:((s.rec && s.rec.name) || s.id) + " (mirror image)", cat:s.cat, rgb:[col.r, col.g, col.b], alpha:c.material.opacity,
              geom:function(){
                var p = g.attributes.position.array, q = new Float32Array(p.length), lo = [1e18, 1e18, 1e18], hi = [-1e18, -1e18, -1e18], i, k;
                for (i = 0; i < p.length; i += 3){
                  var t = 2 * (p[i]*n[0] + p[i+1]*n[1] + p[i+2]*n[2] - d);
                  for (k = 0; k < 3; k++){ var v = p[i+k] - t * n[k]; q[i+k] = v; if (v < lo[k]) lo[k] = v; if (v > hi[k]) hi[k] = v; }
                }
                return {pos:q, idx:g.index.array, bmin:lo, bmax:hi};
              }});
  });
}
changeHooks.push(symSync);
symCtl = NMSKSymView({url:"symmetry_q237.json", toolbar:document.getElementById("tools"), toolClass:"tool", has:function(id){ return !!byId[id]; }, apply:symSet});
window.__symState = function(){ return symCtl.state(); };
window.__symDebug = function(){ var h = 0; if (symSpec) meshes.forEach(function(m){ if (symSpec.hideSet[m.userData.id] && !m.visible) h++; });
  return {copies: symCopies.length, copiesVisible: symCopies.filter(function(c){ return c.visible; }).length, clipped: symCopies.filter(function(c){ return c.material.clippingPlanes && c.material.clippingPlanes.length; }).length,
          originalsHidden: h, cutOn: !!cut.on, mirrorDet: symSpec ? new THREE.Matrix4().set.apply(new THREE.Matrix4(), symSpec.matrix).determinant() : null}; };
