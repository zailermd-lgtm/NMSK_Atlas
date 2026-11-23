/* Q389 display covering ("underwear"), WebGL engine. The module (viewer/cover/cover.js) owns the state, the control and the maths; this is
   only the GL side: one small dynamic vertex / normal buffer per garment plus two index buffers (body, rim), drawn with the scene's own
   program right after the opaque pass -- so it takes the cut plane, the isolation box and the Symmetric mirror like every structure, writes
   depth (the translucent skin behind it is hidden, translucent structures in front of it still blend over it) and is opaque whatever the
   skin's opacity. It is NOT in the ID / depth / label passes: a pick passes through it. Its vertices are recomputed from the posed skin
   (poseLiveZ, else the welded rest geometry) when the pose moved one of its skin pieces. Not drawn in the projection-radiograph style
   (a covering casts no such shadow) or while one layer other than the skin is soloed. */
var coverZ = null;
(function(){
  if (typeof NMSKCover === "undefined") return;
  var H = {}, drawn = 0, BODY = [0.86, 0.89, 0.93], RIM = [0.47, 0.55, 0.68], GREY = [0.66, 0.66, 0.66], GREY2 = [0.45, 0.45, 0.45];
  function buf(target, data, usage){ var b = gl.createBuffer(); gl.bindBuffer(target, b); gl.bufferData(target, data, usage); return b; }
  NMSKCover.start({
    page:"zan:" + ((MAN && MAN.variant) || "base_male") + ":" + OBJ.length,
    count:OBJ.length,
    id:function(i){ return OBJ[i].id; },
    nverts:function(i){ return OBJ[i].vc; },
    geo:function(i){ return poseLiveZ[i] || poseRestOfZ(i); },
    make:function(key, g){
      H[key] = {pb:buf(gl.ARRAY_BUFFER, g.pos, gl.DYNAMIC_DRAW), nb:buf(gl.ARRAY_BUFFER, g.nrm, gl.DYNAMIC_DRAW),
                body:buf(gl.ELEMENT_ARRAY_BUFFER, g.body, gl.STATIC_DRAW), rim:buf(gl.ELEMENT_ARRAY_BUFFER, g.rim, gl.STATIC_DRAW), rev:-1};
    },
    redraw:function(){ need = true; }
  });
  window.addEventListener("nmsk-pose-rev", function(e){ if (NMSKCover.moved(e && e.detail ? e.detail.ids : null)) need = true; });
  coverZ = {
    draw:function(){
      if (!NMSKCover.ready() || q301.mode === "xray" || (soloLayer && soloLayer !== "skin")) return 0;
      var n = 0, plain = q301.mode === "colour";
      NMSKCover.keys().forEach(function(k){
        if (!NMSKCover.isOn(k)) return;
        var g = NMSKCover.refresh(k), h = H[k]; if (!g || !h) return;
        gl.bindBuffer(gl.ARRAY_BUFFER, h.pb); if (h.rev !== g.rev) gl.bufferSubData(gl.ARRAY_BUFFER, 0, g.pos);
        gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, h.nb); if (h.rev !== g.rev) gl.bufferSubData(gl.ARRAY_BUFFER, 0, g.nrm);
        gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);
        h.rev = g.rev;
        gl.uniform1f(U.uAlpha, 1); gl.uniform1f(U.uHL, 0);
        var c = plain ? BODY : GREY; gl.uniform3f(U.uColor, c[0], c[1], c[2]);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, h.body); gl.drawElements(gl.TRIANGLES, g.body.length, gl.UNSIGNED_SHORT, 0);
        c = plain ? RIM : GREY2; gl.uniform3f(U.uColor, c[0], c[1], c[2]);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, h.rim); gl.drawElements(gl.TRIANGLES, g.rim.length, gl.UNSIGNED_SHORT, 0);
        n++;
      });
      drawn = n;
      return n;
    }
  };
  /* test hook (verify_cover_q389.py): what was drawn last, and a garment's current vertices */
  window.__coverDebug = function(key){
    var s = NMSKCover.state(); s.drawn = drawn; s.clip = clip.on ? clipPlane() : null; s.style = q301.mode; s.solo = soloLayer;
    if (key && NMSKCover.garment(key)){
      var g = NMSKCover.refresh(key), lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9], i, j, bad = 0;
      for (i = 0; i < g.pos.length; i += 3) for (j = 0; j < 3; j++){ var v = g.pos[i + j]; if (v !== v) bad++; if (v < lo[j]) lo[j] = v; if (v > hi[j]) hi[j] = v; }
      s.box = [lo, hi]; s.nan = bad; s.n = g.n; s.nb = g.nb;
      s.at = function(v){ return [g.pos[3 * v], g.pos[3 * v + 1], g.pos[3 * v + 2]]; };
      s.bindOf = function(v){ return Array.prototype.slice.call(g.bind, 7 * v, 7 * v + 7); };
      s.srcIndex = g.srcIdx.slice();
    }
    return s;
  };
})();
