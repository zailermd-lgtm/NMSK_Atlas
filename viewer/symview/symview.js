/* Symmetric view (Q237): DISPLAY ONLY, no data change. For the structures classified as paired (data/derived/Q237_pairing.json, sidecar symmetry_q237.json next to the page: the
   model's midsagittal plane + the left/right twins; lateralised organs and one-sided structures are not in it) it draws the MIRROR IMAGE of the chosen side about the model's
   midsagittal plane and hides the original of the other side while it is on. Choices: Off / Mirror right onto left / Mirror left onto right. A banner says it is not measured data.
   The engine (three.js meshes with a reflection matrix, or the WebGL vertex-shader reflection) is reached only through the adaptor E:
   url (sidecar)   toolbar + toolClass (where the control goes)   has(id) -> bool   apply(spec) (spec = null to leave; else {src:"r"|"l", matrix:[16 row-major], plane:{n,d}, srcIds, hideIds, srcSet, hideSet})
   The engine owns the clipping (Cut mode): the mirrored copy is clipped by the same cut planes as everything else. */
function NMSKSymView(E){
  "use strict";
  var $ = function(id){ return document.getElementById(id); };
  var data = null, mode = "off", sel = null, banner = $("sym-banner"), btxt = $("sym-banner-txt"), bOff = $("sym-off"), lists = {r: null, l: null}, plane = null;
  function nonEmpty(a){ return a && a.length; }
  function build(d){
    if (!d || !d.plane || !d.plane.n || !d.pairs) return false;
    var n = d.plane.n, dd = d.plane.d;
    var M = [1 - 2*n[0]*n[0], -2*n[0]*n[1], -2*n[0]*n[2], 2*dd*n[0],
             -2*n[1]*n[0], 1 - 2*n[1]*n[1], -2*n[1]*n[2], 2*dd*n[1],
             -2*n[2]*n[0], -2*n[2]*n[1], 1 - 2*n[2]*n[2], 2*dd*n[2],
             0, 0, 0, 1];
    plane = {n: n, d: dd, matrix: M, tilt: d.plane.tilt_deg};
    lists = {r: {src: [], hide: []}, l: {src: [], hide: []}};
    d.pairs.forEach(function(p){
      var R = (p[0] || []).filter(E.has), L = (p[1] || []).filter(E.has);
      if (!R.length || !L.length) return;
      R.forEach(function(i){ lists.r.src.push(i); lists.l.hide.push(i); });      // "right onto left": draw the mirrored right, hide the left original
      L.forEach(function(i){ lists.l.src.push(i); lists.r.hide.push(i); });
    });
    return lists.r.src.length > 0;
  }
  function set(m){
    if (m !== "r" && m !== "l") m = "off";
    mode = m;
    if (sel){ sel.value = m; sel.classList.toggle("sv-on", m !== "off"); }
    if (m === "off"){
      if (banner) banner.hidden = true;
      E.apply(null);
      return;
    }
    var src = m, hideSide = m === "r" ? "l" : "r", set1 = {}, set2 = {};
    lists[src].src.forEach(function(i){ set1[i] = 1; });
    lists[src].hide.forEach(function(i){ set2[i] = 1; });
    E.apply({src: src, matrix: plane.matrix, plane: {n: plane.n, d: plane.d}, srcIds: lists[src].src, hideIds: lists[src].hide, srcSet: set1, hideSet: set2});
    if (banner){
      banner.hidden = false;
      btxt.textContent = (m === "r" ? "Right side mirrored onto the left" : "Left side mirrored onto the right") + " about this model's midsagittal plane (" + (plane.tilt != null ? "tilt " + Number(plane.tilt).toFixed(1) + "°, " : "") +
        lists[src].src.length + " paired structures); the " + (hideSide === "l" ? "left" : "right") + " originals are hidden. Lateralised organs are not mirrored.";
    }
  }
  function ui(){
    if (!E.toolbar) return;
    sel = document.createElement("select");
    sel.id = "sym-select"; sel.className = (E.toolClass || "") + " sv-sel";
    sel.title = "Symmetric view (display only): mirror one side of the paired structures onto the other. Not measured data."; sel.setAttribute("aria-label", "Symmetric view");
    [["off", "Symmetric view: off"], ["r", "Mirror right onto left"], ["l", "Mirror left onto right"]].forEach(function(o){
      var op = document.createElement("option"); op.value = o[0]; op.textContent = o[1]; sel.appendChild(op);
    });
    sel.addEventListener("change", function(){ set(sel.value); });
    E.toolbar.appendChild(sel);
    if (bOff) bOff.addEventListener("click", function(){ set("off"); });
  }
  var ready = false;
  try {
    fetch(E.url).then(function(r){ if (!r.ok) throw new Error("no symmetry sidecar"); return r.json(); }).then(function(d){
      data = d; if (build(d)){ ready = true; ui(); }
    }).catch(function(){});
  } catch (err){}
  return {
    set: set, mode: function(){ return mode; }, ready: function(){ return ready; }, data: function(){ return data; },
    state: function(){ return {mode: mode, ready: ready, pairs: data ? data.pairs.length : 0, src: mode === "off" ? 0 : lists[mode].src.length, hidden: mode === "off" ? 0 : lists[mode].hide.length}; }
  };
}
