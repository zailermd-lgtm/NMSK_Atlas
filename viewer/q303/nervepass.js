/* Q303: the nerve-emphasis pass's SHADER, shared verbatim by both engines.
   Q301 D3(7) recorded a case where a real piece of physics was deliberately NOT shipped because one engine would have
   needed a patch to three.js's own shader and "the two engines would then be computing different mathematics". This pass
   avoids that trap completely: the GLSL below is one string, byte-identical in both templates, compiled by the Z engine
   into a tiny program of its own and by the own engine into a THREE.RawShaderMaterial. Both engines therefore run the
   SAME arithmetic; a test asserts the two templates carry the same bytes.
   The three matrices are named as three.js names them (projectionMatrix / viewMatrix / modelMatrix) and the Z engine
   simply supplies its combined MVP as projectionMatrix with the other two set to the identity -- the product is the same.
   What the vertex stage does, in order:
     1. the cut. Keep where dot(world position, plane) >= 0, for both the near face and the far face of a slice. The Z
        engine's own shader uses the OPPOSITE sign, so its glue negates its planes before handing them over; the own
        engine's three.js planes already use this sign. Default [0,0,0,1] keeps everything.
     2. the far half of the body. A pass with the depth test off reads through overlying tissue -- that is the whole point,
        and it is Q300's bone-pass pattern -- but with no guard it would also paint the nerves on the FAR side of the body
        over the near ones. Points behind the plane through the camera's own target, normal to the view, are dropped.
     3. the MINIMUM DRAWN WIDTH, which is the round's actual idea: uPt is set per structure by the caller to
        max(the step's minimum in pixels, the nerve's TRUE diameter in pixels) * devicePixelRatio, so a nerve already
        wider than the minimum is drawn at its own width and nothing is ever made to look thinner than it is.
   The fragment stage paints a round dot (a square point reads as a chain of blocks on a thin nerve) in the colour and at
   the opacity the step chose. */
var NMSKNervePass = (function(){
  "use strict";
  var VS =
    "precision highp float;\n" +
    "attribute vec3 position;\n" +
    "uniform mat4 projectionMatrix;\n" +
    "uniform mat4 viewMatrix;\n" +
    "uniform mat4 modelMatrix;\n" +
    "uniform vec4 uC1;\n" +
    "uniform vec4 uC2;\n" +
    "uniform vec3 uCtr;\n" +
    "uniform vec3 uFwd;\n" +
    "uniform float uPt;\n" +
    "void main(){\n" +
    "  vec4 wp = modelMatrix * vec4(position, 1.0);\n" +
    "  vec3 wv = wp.xyz;\n" +
    "  if (dot(wv, uC1.xyz) + uC1.w < 0.0 || dot(wv, uC2.xyz) + uC2.w < 0.0){ gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 0.0; return; }\n" +
    "  if (dot(wv - uCtr, uFwd) > 0.0){ gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 0.0; return; }\n" +
    "  gl_Position = projectionMatrix * viewMatrix * wp;\n" +
    "  gl_PointSize = uPt;\n" +
    "}\n";
  var FS =
    "precision highp float;\n" +
    "uniform vec3 uColor;\n" +
    "uniform float uAlpha;\n" +
    "void main(){\n" +
    "  vec2 d = gl_PointCoord - vec2(0.5, 0.5);\n" +
    "  if (dot(d, d) > 0.25) discard;\n" +
    "  gl_FragColor = vec4(uColor, uAlpha);\n" +
    "}\n";
  var api = {
    vs:function(){ return VS; },
    fs:function(){ return FS; },
    /* the one formula, used by both glues: the drawn width of a nerve in DEVICE pixels */
    width:function(dia_mm, mmPerPx, wmin_px, dpr){
      var truePx = (dia_mm != null && mmPerPx > 0) ? dia_mm / mmPerPx : 0;
      return Math.max(wmin_px || 0, truePx) * (dpr || 1);
    },
    /* the near/far split and the two clip planes, in the shader's own sign convention */
    frame:function(eye, tgt, c1, c2){
      var f = [tgt[0] - eye[0], tgt[1] - eye[1], tgt[2] - eye[2]], l = Math.hypot(f[0], f[1], f[2]) || 1;
      return {ctr:tgt.slice(), fwd:[f[0] / l, f[1] / l, f[2] / l],
              c1:c1 || [0, 0, 0, 1], c2:c2 || [0, 0, 0, 1]};
    },
    hash:function(){ return VS.length + ":" + FS.length; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKNervePass;
