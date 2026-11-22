    /* Q334: the wall faces moved out of the drawn range (see the weld block) go into one extra index buffer per batch,
       over the batch's own vertex buffers, in per-neighbour runs: q334Walls() draws a run only while its neighbour is not drawn */
    BATCHES.forEach(function(B){
      var tot = 0;
      B.objs.forEach(function(o){ (o.q334w || []).forEach(function(g){ tot += g.idx.length; }); });
      if (!tot) return;
      var ib = new Uint16Array(tot), at = 0;
      B.objs.forEach(function(o){ (o.q334w || []).forEach(function(g){
        g.s = at; g.c = g.idx.length;
        for (var z = 0; z < g.idx.length; z++) ib[at + z] = g.idx[z] + o.vOff;
        at += g.idx.length; g.idx = null;
      }); });
      B.q334ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, B.q334ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, ib, gl.STATIC_DRAW);
    });
