    /* read-only test hook (verify_skin_seams_q334.py): camera, projection, picking and the seam state */
    var q334A0 = {}, q334On0 = {}; LK.forEach(function(k){ q334A0[k] = alphaFor[k]; q334On0[k] = on[k]; });
    window.__q334 = {
      defaults:function(){ LK.forEach(function(k){ alphaFor[k] = q334A0[k]; on[k] = q334On0[k]; }); soloLayer = null; presetName = ""; need = true; },
      cam:function(c){ if(c){ if(c.az!=null) cam.az=c.az; if(c.el!=null) cam.el=c.el; if(c.dist!=null) cam.dist=c.dist; if(c.tgt) cam.tgt=c.tgt.slice(); stopSpin(); need=true; }
        return {az:cam.az, el:cam.el, dist:cam.dist, tgt:cam.tgt.slice(), H:HGT}; },
      toScreen:function(p){ var s=proj(p); return s ? [s.x/dpr, s.y/dpr, s.w] : null; },
      pickAt:function(x, y){ var o=pick(x*dpr, y*dpr); return o ? (o.id || o.name) : null; },
      index:function(id){ for (var i=0;i<OBJ.length;i++) if ((OBJ[i].id||OBJ[i].name)===id) return i; return -1; },
      hide:function(id, v){ var i=this.index(id); if(i<0) return false; if(v===false) hidden.delete(OBJ[i]); else hidden.add(OBJ[i]); need=true; return true; },
      select:function(id){ var i=id==null?-1:this.index(id); select(i<0?null:OBJ[i], false); need=true; return i>=0; },
      hover:function(id){ var i=id==null?-1:this.index(id); hovered=i<0?null:OBJ[i]; need=true; return i>=0; },
      layer:function(k, a, solo){ if(a!=null){ on[k]=a>0.01; alphaFor[k]=a; } if(solo!==undefined) soloLayer=solo; need=true; return {on:on[k], a:alphaFor[k], solo:soloLayer}; },
      draws:function(){ return drawCount; },
      /* the canvas as just drawn: luminance (0..255) at each css-pixel point [x, y]; ids(): the ID pass at the same points */
      sample:function(pts, rgb){
        draw(); need = false;
        var buf = new Uint8Array(W * H * 4); gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, buf);
        return pts.map(function(p){ var x = Math.round(p[0] * dpr), y = H - 1 - Math.round(p[1] * dpr); if (x < 0 || y < 0 || x >= W || y >= H) return -1;
          var k = 4 * (y * W + x); return rgb ? [buf[k], buf[k+1], buf[k+2]] : 0.299 * buf[k] + 0.587 * buf[k+1] + 0.114 * buf[k+2]; });
      },
      ids:function(pts, all){
        draw(); need = false; renderIds(!!all); pickKey = null;
        var buf = new Uint8Array(W * H * 4); gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, buf);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, W, H);
        return pts.map(function(p){ var x = Math.round(p[0] * dpr), y = H - 1 - Math.round(p[1] * dpr); if (x < 0 || y < 0 || x >= W || y >= H) return null;
          var k = 4 * (y * W + x), id = buf[k] | (buf[k+1] << 8) | (buf[k+2] << 16); return id > 0 && id <= OBJ.length ? (OBJ[id-1].id || OBJ[id-1].name) : null; });
      },
      sortOff:function(v){ q334NoSort = !!v; need = true; },
      bench:function(n){ var px = new Uint8Array(4), t0 = performance.now(); for (var i = 0; i < n; i++){ draw(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); } need = false; return (performance.now() - t0) / n; },
      cut:function(spec){ cutCtl.setFromSpec(spec ? {normal:spec.normal, point:spec.point} : null); need = true; return !!clip.on; },
      preset:function(id){ var b = document.getElementById(id); if (b) b.click(); need = true; return !!b; },
      seams:function(){ if (typeof q334W === "undefined") return null; var ks = Object.keys(q334W), pw = null;
        if (ks.length){ var i0 = +ks[0], r = poseRestOfZ(i0), w = q334W[i0].nrm, d = 0; for (var z = 0; z < w.length; z++) d = Math.max(d, Math.abs(w[z] - r.nrm[z])); pw = d; }
        return {ms:q334Stat.ms, cls:q334Stat.cls, wallRunsDrawn:q334Drawn, poseRestNrmDiff:pw}; }
    };
