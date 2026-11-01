/* Q300: make the skeleton read through soft tissue in X-ray and in Fade, on both engines.
   Owner: "in xray and in fade view - the skeleton should appear better than now that it can not be seen almost at all."
   WHY IT WAS INVISIBLE (measured in the code before anything was changed, see docs/research/Q300_interface_benchmark.md §3):
     - own engine: bone was opaque and drawn first, every soft tissue drawn over it at 0.5 (muscle 0.34). What survives of
       the bone is the PRODUCT of (1 - alpha) over everything in front of it: skin x fat x muscle x fascia ~ 0.08.
     - Z engine: its per-layer X-ray table is well tuned, but the translucent pass runs with CULL_FACE disabled, so every
       closed shell blends TWICE (front face and back face) and the product becomes (1 - alpha)^2 per shell: ~0.085 with
       five overlapping muscles.
     - both: the Fade state used ONE flat alpha (0.15) for every class, so bone faded exactly as hard as skin.
   Lowering the per-class alphas alone cannot fix this, because the number of layers in front of a bone changes with the
   region and with the camera. The fix that does not depend on it is an extra pass: after the translucent pass, the bone is
   painted again, over whatever covered it, at a controlled strength. The bone's share of the pixel is then the strength,
   full stop. This module owns that strength (3 taps, not a slider -- the project's mobile rule), shows the control only
   while X-ray or Fade is engaged, and registers it with the history so it undoes like everything else.
   The engine supplies the pass itself through E: {active(), setLevel(alpha), redraw()}.
     NMSKBoneRead.start(E, {toolbar, cls, history, level})
     .level()  .alpha()  .set(i)  .steps()  .state() */
var NMSKBoneRead = (function(){
  "use strict";
  var E = null, hist = null, box = null, segBtns = [], i0 = 1, lvl = 1, on = false;
  var A = [0, 0.45, 0.80], W = ["Off", "Clear", "Strong"];
  var TIP = "In X-ray and in Fade the bone is painted once more on top of the soft tissue, so the skeleton stays readable however many layers lie in front of it. Off is the old look; Clear is the default; Strong is for a thick region like the pelvis or the shoulder.";
  function alpha(){ return A[lvl] || 0; }
  function push(){
    if (!E || !E.setLevel) return;
    try { E.setLevel(alpha()); } catch (err){ if (window.console) console.error("boneread", err); }
    if (E.redraw){ try { E.redraw(); } catch (err){} }
  }
  function set(i, quiet){
    i = Math.max(0, Math.min(A.length - 1, i | 0));
    if (i === lvl){ ui(); return false; }
    lvl = i; push(); ui();
    if (!quiet && hist && hist.schedule) hist.schedule();
    return true;
  }
  function ui(){
    segBtns.forEach(function(b, k){ b.setAttribute("aria-pressed", String(k === lvl)); b.classList.toggle("on", k === lvl); });
    if (box){
      var live = false;
      if (E && E.active){ try { live = !!E.active(); } catch (err){ live = false; } }
      box.hidden = !live;                      // zero chrome until X-ray or Fade is actually engaged
    }
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null;
      if (!E || typeof E.setLevel !== "function") return api;
      hist = opt.history || window.NMSKHistory || null;
      if (opt.level != null) lvl = Math.max(0, Math.min(A.length - 1, opt.level | 0));
      i0 = lvl;
      box = document.createElement("span");
      box.id = "br-box"; box.className = "br-box"; box.hidden = true;
      box.setAttribute("role", "group"); box.setAttribute("aria-label", "How strongly the bone shows through");
      var lab = document.createElement("span"); lab.className = "br-l"; lab.textContent = "Bone";
      box.appendChild(lab);
      var seg = document.createElement("span"); seg.className = "br-seg";
      W.forEach(function(w, k){
        var b = document.createElement("button");
        b.type = "button"; b.className = "br-b"; b.id = "br-" + k; b.textContent = w;
        b.title = "Bone through soft tissue: " + w + (k === 1 ? " (default)" : "");
        b.setAttribute("aria-pressed", String(k === lvl));
        b.addEventListener("click", function(e){ e.stopPropagation(); set(k); });
        seg.appendChild(b); segBtns.push(b);
      });
      box.appendChild(seg);
      var n = document.createElement("span"); n.className = "br-note";
      n.innerHTML = '<p class="nmsk-tip">' + TIP + "</p>";
      box.appendChild(n);
      if (opt.toolbar) opt.toolbar.appendChild(box); else document.body.appendChild(box);
      if (hist && hist.register){
        hist.register("boneread", {get:function(){ return lvl; }, set:function(v){ set(v, true); }, reset:function(){ set(i0, true); }});
      }
      on = true; push(); ui();
      setInterval(ui, 450);                    // the engines flip X-ray / Fade without an event of their own
      return api;
    },
    level:function(){ return lvl; }, alpha:alpha, set:function(i){ return set(i); },
    steps:function(){ return A.slice(); }, words:function(){ return W.slice(); },
    refresh:ui,
    state:function(){ var live = false; if (E && E.active){ try { live = !!E.active(); } catch (err){} } return {on:on, level:lvl, alpha:alpha(), shown:live}; }
  };
  return api;
})();
