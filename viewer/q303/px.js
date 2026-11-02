/* Q303: the frame statistics, shared, so the two engines measure the SAME thing.
   page.screenshot of a WebGL canvas returns a stale frame in this container -- proven in Q300 and re-confirmed in Q301 --
   so every pixel figure of this round is read with gl.readPixels INSIDE the page, right after a synchronous draw. Each
   glue does only that: force one frame, read the buffer, hand it here. The arithmetic lives in one place.
   A NERVE IS RECOGNISED BY CHROMATICITY, not by RGB distance: the shading multiplies the brightness of a nerve's own
   colour over a wide range, while r:g:b stays put, so a chromaticity test finds the nerve whether it is lit or in
   shadow. The background is excluded from everything, taken from the frame's four corners -- one engine clears to
   transparent and the other to an opaque light grey, which would otherwise read as most of a bright picture (Q301).
     NMSKPx.stats(buf, w, h, step, chroma) -> {n, nerve, nerveFrac, lumNerve, lumOther, michelson}
     NMSKPx.quadrants(buf, w, h, step)     -> [fraction of each quadrant that is not background]  (four panes drew) */
var NMSKPx = (function(){
  "use strict";
  var TOL = 0.035, DARK = 10;
  function corners(buf, w, h){
    function at(x, y){ var o = ((y | 0) * w + (x | 0)) * 4; return [buf[o], buf[o+1], buf[o+2], buf[o+3]]; }
    return [at(1, 1), at(w - 2, 1), at(1, h - 2), at(w - 2, h - 2)];
  }
  function fielder(C){
    return function(r, g, b, a){
      if (a < 9) return true;
      for (var k = 0; k < C.length; k++){
        var c = C[k];
        if (Math.abs(r - c[0]) <= 6 && Math.abs(g - c[1]) <= 6 && Math.abs(b - c[2]) <= 6) return true;
      }
      return false;
    };
  }
  function chroma(c){ var s = (c[0] + c[1] + c[2]) || 1; return [c[0] / s, c[1] / s, c[2] / s]; }
  function stats(buf, w, h, step, col){
    var s = Math.max(1, (step | 0) || 2), C = corners(buf, w, h), isField = fielder(C), nch = chroma(col || [0.85, 0.71, 0.26]);
    var n = 0, nn = 0, lN = 0, lO = 0;
    for (var y = 0; y < h; y += s) for (var x = 0; x < w; x += s){
      var o = (y * w + x) * 4, r = buf[o], g = buf[o+1], b = buf[o+2], a = buf[o+3];
      if (isField(r, g, b, a)) continue;
      var l = 0.299*r + 0.587*g + 0.114*b;
      if (l < DARK) continue;
      n++;
      var t = (r + g + b) || 1, d = Math.abs(r/t - nch[0]) + Math.abs(g/t - nch[1]) + Math.abs(b/t - nch[2]);
      if (d < TOL){ nn++; lN += l; } else lO += l;
    }
    var mN = nn ? lN / nn : 0, mO = (n - nn) ? lO / (n - nn) : 0;
    return {n:n, nerve:nn, nerveFrac:n ? Math.round(nn / n * 1e6) / 1e6 : 0,
            lumNerve:Math.round(mN * 100) / 100, lumOther:Math.round(mO * 100) / 100,
            michelson:(mN + mO) ? Math.round(Math.abs(mN - mO) / (mN + mO) * 1e4) / 1e4 : 0,
            w:w, h:h, step:s, chroma:nch.map(function(v){ return Math.round(v * 1000) / 1000; })};
  }
  function quadrants(buf, w, h, step){
    var s = Math.max(1, (step | 0) || 2), C = corners(buf, w, h), isField = fielder(C);
    var tot = [0, 0, 0, 0], hit = [0, 0, 0, 0];
    for (var y = 0; y < h; y += s) for (var x = 0; x < w; x += s){
      var q = (x < w / 2 ? 0 : 1) + (y < h / 2 ? 2 : 0);          /* readPixels is bottom-up: 2,3 are the TOP row */
      tot[q]++;
      var o = (y * w + x) * 4;
      if (!isField(buf[o], buf[o+1], buf[o+2], buf[o+3])) hit[q]++;
    }
    return [2, 3, 0, 1].map(function(q){ return tot[q] ? Math.round(hit[q] / tot[q] * 1e5) / 1e5 : 0; });
  }
  return {stats:stats, quadrants:quadrants, tol:function(){ return TOL; }};
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKPx;
