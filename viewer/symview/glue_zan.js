/* Q237 Symmetric view, WebGL engine: the main shader reflects the vertex about the midsagittal plane when uSymOn is set (position AND normal; the clip / box tests in the fragment
   shader use the reflected position, so uClip / uClip2 cut the mirrored copy like everything else); draw() paints the scene a second time for the source side with
   frontFace CW (the reflection reverses the winding); the other side's originals are vetoed in vis(). Nothing is written to the data. */
var symCtl = null, sym = null, symPass = false, symIds = null;
function symApply(spec){ sym = spec || null; need = true; if (capCtl && capCtl.itemsChanged) capCtl.itemsChanged(); }
function symHide(o){ return !!(sym && sym.hideSet[o.id]); }
function symIsSrc(o){ return !!(sym && sym.srcSet[o.id]); }
function symSideOK(o){ return sideFilter === "both" || o.side === "m" || sideFilter === (o.side === "r" ? "l" : "r"); }     // the mirrored copy sits on the OPPOSITE side
function symBox(o){          /* axis-aligned box of the reflected box (for the cut / isolation AABB tests of the mirrored pass) */
  var n = sym.plane.n, d = sym.plane.d, lo = [1e18, 1e18, 1e18], hi = [-1e18, -1e18, -1e18], i, k;
  for (i = 0; i < 8; i++){
    var p = [(i & 1) ? o.bmax[0] : o.bmin[0], (i & 2) ? o.bmax[1] : o.bmin[1], (i & 4) ? o.bmax[2] : o.bmin[2]], t = 2 * (p[0]*n[0] + p[1]*n[1] + p[2]*n[2] - d);
    for (k = 0; k < 3; k++){ var v = p[k] - t * n[k]; if (v < lo[k]) lo[k] = v; if (v > hi[k]) hi[k] = v; }
  }
  return [lo, hi];
}
function symCap(out){          /* the filled cut face also takes the mirrored copies */
  if (!sym) return;
  var n = sym.plane.n, d = sym.plane.d;
  symPass = true;
  try {
    OBJ.forEach(function(o, i){
      if (!symIsSrc(o) || !vis(o)) return;
      var lk = selLook(o), a = faded.has(o) ? Math.min(0.18, alphaFor[o.layer]) : (lk === "ghost" || lk === "fade" || lk === "xray" ? selAlpha(lk, o.layer, lk === "ghost" ? alphaFor[o.layer] : layerAlpha(o.layer)) : (lk === "hl" ? 1 : layerAlpha(o.layer))), c = colOf(o);
      out.push({key:o.id, name:o.name + " (mirror image)", cat:o.layer, rgb:c, alpha:a, geom:function(){
        var g = capGeom(i, o), p = g.pos, q = new Float32Array(p.length), k, j, b = symBox(o);
        for (j = 0; j < p.length; j += 3){
          var t = 2 * (p[j]*n[0] + p[j+1]*n[1] + p[j+2]*n[2] - d);
          for (k = 0; k < 3; k++) q[j+k] = p[j+k] - t * n[k];
        }
        return {pos:q, idx:g.idx, bmin:b[0], bmax:b[1]};
      }});
    });
  } finally { symPass = false; }
}
symCtl = NMSKSymView({url:"symmetry_q237.json", toolbar:document.getElementById("topright"), toolClass:"pill",
  has:function(id){ if (!symIds){ symIds = {}; OBJ.forEach(function(o){ symIds[o.id] = 1; }); } return symIds[id] === 1; }, apply:symApply});
window.__symState = function(){ return symCtl.state(); };
window.__symDebug = function(){ return {on: !!sym, clipOn: !!clip.on, srcObjects: sym ? OBJ.filter(symIsSrc).length : 0, hiddenObjects: sym ? OBJ.filter(symHide).length : 0}; };
