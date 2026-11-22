    /* Q338 read-only test hook (verify_hand_q338.py, render_hand_q338.py; test copies only): camera, layers, visibility, picking */
    var q338A0 = {}, q338On0 = {}; LK.forEach(function(k){ q338A0[k] = alphaFor[k]; q338On0[k] = on[k]; });
    window.__q338 = {
      defaults:function(){ LK.forEach(function(k){ alphaFor[k] = q338A0[k]; on[k] = q338On0[k]; }); soloLayer = null; hidden.clear(); need = true; },
      cam:function(c){ if(c){ if(c.az!=null) cam.az=c.az; if(c.el!=null) cam.el=c.el; if(c.dist!=null) cam.dist=c.dist; if(c.tgt) cam.tgt=c.tgt.slice(); stopSpin(); need=true; }
        return {az:cam.az, el:cam.el, dist:cam.dist, tgt:cam.tgt.slice()}; },
      toScreen:function(p){ var s=proj(p); return s ? [s.x/dpr, s.y/dpr, s.w] : null; },
      pickAt:function(x, y){ var o=pick(x*dpr, y*dpr); return o ? (o.id || o.name) : null; },
      index:function(id){ for (var i=0;i<OBJ.length;i++) if ((OBJ[i].id||OBJ[i].name)===id) return i; return -1; },
      has:function(id){ return this.index(id) >= 0; },
      hide:function(id, v){ var i=this.index(id); if(i<0) return false; if(v===false) hidden.delete(OBJ[i]); else hidden.add(OBJ[i]); need=true; return true; },
      only:function(ids){ var s = {}; ids.forEach(function(x){ s[x] = 1; }); hidden.clear();
        OBJ.forEach(function(o){ if(!s[o.id || o.name]) hidden.add(o); }); need = true; return ids.length; },
      showAllIn:function(){ hidden.clear(); need = true; },
      layer:function(k, a, solo){ if(a!=null){ on[k]=a>0.01; alphaFor[k]=a; } if(solo!==undefined) soloLayer=solo; need=true; return {on:on[k], a:alphaFor[k], solo:soloLayer}; },
      layers:function(){ var r = {}; LK.forEach(function(k){ r[k] = [on[k], alphaFor[k]]; }); return r; },
      preset:function(id){ var b = document.getElementById(id); if (b) b.click(); need = true; return !!b; },
      ids:function(pts, all){
        draw(); need = false; renderIds(!!all); pickKey = null;
        var buf = new Uint8Array(W * H * 4); gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, buf);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, W, H);
        return pts.map(function(p){ var x = Math.round(p[0] * dpr), y = H - 1 - Math.round(p[1] * dpr); if (x < 0 || y < 0 || x >= W || y >= H) return null;
          var k = 4 * (y * W + x), id = buf[k] | (buf[k+1] << 8) | (buf[k+2] << 16); return id > 0 && id <= OBJ.length ? (OBJ[id-1].id || OBJ[id-1].name) : null; });
      },
      draw:function(){ draw(); need = false; return true; }
    };
    window.__q338.bbox = function(id){ var i = this.index(id); if (i < 0) return null; var o = OBJ[i]; return {min:o.bmin.slice(), max:o.bmax.slice()}; };
