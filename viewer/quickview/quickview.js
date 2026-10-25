/* Quick view (Q282): one small panel that composes mechanisms this page already has -- search, camera focus
   (api.focus, the same primitive the clinical tool's own "Zoom" button and the Parts markers already use),
   mark + highlight (api.selection().mark()/preset("hlsel"), Q227/Q232, reused verbatim), a cross-section
   centred on the picked structure (api.setCut() + the Q281 multi-slice stack via api.crossSection(), reused
   verbatim), abbreviated labels (api.labels().setMode()/set(), Q236, reused verbatim) and, only when the
   clinical layer is present, that structure's motor point (window.NMSKClinicalTool.emphasize(), the same
   Q281 marked-filtered mechanism, reused verbatim -- this module never draws a marker or does geometry of
   its own). The point is fewer clicks and less panel-hopping for a combined request such as "axial slices
   through the right hand, abbreviated labels, highlight FPL, show its motor point" -- nothing here is
   specific to any one structure or region; it is the same four actions for whatever is searched.
   One controller for both viewers. The engine is reached only through api, the SAME anatomyApi() object the
   optional clinical add-on attaches to -- this module does not touch any engine-specific variable. */
function NMSKQuickView(api){
  "use strict";
  var $ = function(id){ return document.getElementById(id); };
  var panel, btn, cur = null;

  function mid(r){ return [0, 1, 2].map(function(k){ return (r.bmin[k] + r.bmax[k]) / 2; }); }
  function ext(r){ return Math.hypot(r.bmax[0] - r.bmin[0], r.bmax[1] - r.bmin[1], r.bmax[2] - r.bmin[2]); }
  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"}[c]; }); }
  function say(id, msg){ var e = $(id); if (e) e.textContent = msg || ""; }

  function renderSearch(){
    var q = $("qv-q").value.trim().toLowerCase(), box = $("qv-res");
    box.innerHTML = "";
    if (!q){ return; }
    var hits = api.list().filter(function(r){ return (r.name + " " + r.id).toLowerCase().indexOf(q) >= 0; }).slice(0, 20);
    if (!hits.length){ box.innerHTML = '<p class="qv-hint">No structure matches.</p>'; return; }
    hits.forEach(function(r){
      var b = document.createElement("button"); b.type = "button";
      b.innerHTML = esc(r.name) + (r.side ? " (" + esc(r.side) + ")" : "") + ' <span class="qv-hint mono">' + esc(r.id) + "</span>";
      b.onclick = function(){ pick(r); };
      box.appendChild(b);
    });
  }

  function hasMotorPoints(){
    return !!(window.NMSKClinicalTool && typeof window.NMSKClinicalTool.emphasize === "function" &&
              window.NMSKClinicalTool.mp && window.NMSKClinicalTool.mp.points && window.NMSKClinicalTool.mp.points.length);
  }
  function structureHasMp(id){
    var tool = window.NMSKClinicalTool;
    if (!tool || !tool.mp || !tool.mp.points) return false;
    return tool.mp.points.some(function(p){ return p.structure_id === id; });
  }

  function pick(r){
    cur = r;
    $("qv-q").value = r.name; $("qv-res").innerHTML = "";
    $("qv-sel").hidden = false;
    $("qv-name").textContent = r.name + (r.side ? " (" + r.side + ")" : "");
    var mpBtn = $("qv-mp"), hasTool = hasMotorPoints();
    mpBtn.hidden = !hasTool;
    if (hasTool) mpBtn.disabled = !structureHasMp(r.id);
    say("qv-mp-msg", hasTool ? (structureHasMp(r.id) ? "" : "No motor-point data for this structure.") : "No clinical layer on this page: motor points are not available.");
    say("qv-xs-msg", "");
    say("qv-msg", "");
  }

  function doFocus(){
    if (!cur) return;
    api.focus(mid(cur), Math.max(160, ext(cur) * 1.6));
    say("qv-msg", "Camera moved to " + cur.name + ".");
  }

  function doMark(){
    if (!cur) return;
    var sel = api.selection ? api.selection() : null;
    if (!sel || !sel.mark || !sel.preset){ say("qv-msg", "No selection controller on this page."); return; }
    sel.mark(cur.id, true);
    sel.preset("hlsel");
    say("qv-msg", cur.name + " marked and highlighted.");
  }

  function doMp(){
    if (!cur) return;
    var tool = window.NMSKClinicalTool;
    if (!tool || !tool.emphasize){ return; }
    var sel = api.selection ? api.selection() : null;
    if (sel && sel.mark) sel.mark(cur.id, true);      // Q281's NMJ filter shows only the marked set: make sure this one is in it
    tool.emphasize(true);
    say("qv-msg", structureHasMp(cur.id) ? "Motor point shown for " + cur.name + "." : "Emphasize motor points turned on, but this structure has none.");
  }

  var AX = {x:[1, 0, 0], y:[0, 1, 0], z:[0, 0, 1]}, AXNAME = {x:"sagittal", y:"axial", z:"coronal"};
  function doCrossSection(ax){
    if (!cur || !api.setCut) return;
    api.setCut({normal:AX[ax], point:mid(cur)});
    var xs = api.crossSection ? api.crossSection() : null;
    if (xs && xs.set) xs.set(true);
    say("qv-xs-msg", "Cut panel opened, " + AXNAME[ax] + " plane centred on " + cur.name + (xs ? " with the multi-slice stack on -- set the slice count / spacing / thickness there." : ". Turn on \"Multi-slice cross-section\" there for several slices at once."));
  }

  function doAbbr(on){
    var lab = api.labels ? api.labels() : null;
    if (!lab){ say("qv-msg", "No labels controller on this page."); return; }
    if (on){
      if (lab.state && lab.state().mode === "off") lab.setMode("sel");
      lab.set("text", "abbr");
    } else {
      lab.set("text", "full");
    }
  }

  function open(on){
    panel.hidden = !on;
    if (btn) btn.setAttribute("aria-pressed", String(on));
    if (on) $("qv-q").focus();
  }

  function mountToolbar(){
    var tb = api.toolbar; if (!tb) return;
    btn = document.createElement("button"); btn.type = "button"; btn.id = "t-quick"; btn.className = api.toolClass || "tool";
    btn.textContent = "Quick view"; btn.setAttribute("aria-pressed", "false");
    btn.title = "Search a structure, then focus / mark & highlight / cross-section through it / show its motor point, all in one panel";
    btn.addEventListener("click", function(){ open(panel.hidden); });
    var ref = $("t-cut") || $("t-labels") || null;
    if (ref && ref.parentNode === tb) tb.insertBefore(btn, ref.nextSibling); else tb.appendChild(btn);
  }

  panel = $("qv-panel");
  if (!panel) return {open:function(){}, pick:function(){}};
  mountToolbar();
  $("qv-close").addEventListener("click", function(){ open(false); });
  $("qv-q").addEventListener("input", renderSearch);
  $("qv-focus").addEventListener("click", doFocus);
  $("qv-mark").addEventListener("click", doMark);
  $("qv-mp").addEventListener("click", doMp);
  Array.prototype.forEach.call($("qv-ax").querySelectorAll("[data-ax]"), function(b){ b.addEventListener("click", function(){ doCrossSection(b.dataset.ax); }); });
  $("qv-abbr").addEventListener("change", function(){ doAbbr(this.checked); });

  return {
    open:open,
    pick:function(id){ var r = api.list().filter(function(x){ return x.id === id; })[0]; if (r) pick(r); return !!r; },
    current:function(){ return cur ? cur.id : null; },
    state:function(){ return {open:!panel.hidden, current:cur ? cur.id : null, hasClinical:hasMotorPoints()}; }
  };
}
