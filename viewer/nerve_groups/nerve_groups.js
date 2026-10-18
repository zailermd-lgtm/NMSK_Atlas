/* Q256: "Nerve groups" -- mark/select nerves by a common plexus component (a root, a trunk, a division, a cord, or any named
   branch), so picking e.g. "Posterior cord" selects every nerve this project's own cited plexus lineage (data/nerves/{brachial,
   lumbosacral}_plexus.json, walked by scripts/anatomy/q256/plexus_groups.py) says is anatomically downstream of it, on THIS page's
   own actual nerve meshes (checked per page by scripts/anatomy/q256/build_plexus_sidecar.py's `plexus_groups.json` sidecar -- own
   pages typically have only the named terminal/muscular/cutaneous branches, Z pages often the fuller root/trunk/division/cord tree
   too; nothing here assumes a level exists, it is counted). This is deliberately NOT a parallel highlight system: selecting a group
   calls straight into the existing Q232 selection controller (E.mark(ids, replace) -> selCtl.markIds, E.clear() -> selCtl.clear(),
   E.highlight() -> selCtl.preset('hlsel')), so every Show/Fade/Hide/Ghost/X-ray/Highlight state the owner already has for a marked
   set keeps working on a nerve group exactly as it does on a hand-picked one.
   Data = the page's sidecar plexus_groups.json (public anatomy layer), fetched with a graceful fallback: absent or invalid = no
   button, nothing else changes. Engine adaptor E: url, toolbar + toolClass, isPhone(), mark(ids, replace) -> count actually marked,
   clear(), highlight() (optional), onLoaded().
   Known, honest limitation (stated in the panel itself, not hidden): the source lineage is single-parent, so a nerve fed by TWO
   plexus components in real anatomy (the median nerve's lateral root from the lateral cord and medial root from the medial cord)
   is only counted under the one cord this project's data lists as its parent (the lateral cord) -- see plexus_groups.py's docstring. */
function NMSKNerveGroups(E){
  "use strict";
  var D = null, btn = null, panel = null, panelBuilt = false;
  var plexus = null, side = "r", q = "", activeNode = null;
  var KEY = "nmsk.nervegroups.v1";
  try { var rs = JSON.parse(localStorage.getItem(KEY) || "null");
    if (rs && typeof rs === "object"){ if (rs.side === "r" || rs.side === "l") side = rs.side; if (typeof rs.plexus === "string") plexus = rs.plexus; } } catch (err){}
  function persist(){ try { localStorage.setItem(KEY, JSON.stringify({side:side, plexus:plexus})); } catch (err){} }
  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }
  var PLEXUS_LABEL = {brachial_plexus:"Brachial", lumbar_plexus:"Lumbar", sacral_plexus:"Sacral"};

  function panelOpen(){ return !!panel && !panel.hidden; }
  function $p(sel){ return panel ? panel.querySelector(sel) : null; }

  function build(){
    if (!D || !D.plexuses || !D.plexuses.length) return;
    if (!plexus || D.by_plexus[plexus] === undefined) plexus = D.plexuses[0];
    if (M.length && E.toolbar && !btn){
      btn = document.createElement("button");
      btn.type = "button"; btn.id = "t-nervegroups"; btn.className = E.toolClass || ""; btn.setAttribute("aria-pressed", "false"); btn.setAttribute("aria-haspopup", "true");
      btn.innerHTML = 'Nerve<span class="ng-more"> groups</span>';
      btn.title = "Nerve groups: select every nerve downstream of a plexus root / trunk / division / cord / branch";
      btn.addEventListener("click", function(){ openPanel(!panelOpen()); });
      E.toolbar.appendChild(btn);
    }
    buildPanel();
  }
  var M = [];   // placeholder list check (true once D loaded with >=1 node); keeps the same shape as NMSKParts's build() guard
  function buildPanel(){
    if (panelBuilt) return;
    panel = document.getElementById("ng-panel"); if (!panel) return;
    panelBuilt = true;
    panel.innerHTML = '<div class="ng-h"><b>Nerve groups</b><span class="ng-st" aria-live="polite"></span><button type="button" class="ng-x" aria-label="Close the nerve groups panel" title="Close">&times;</button></div>' +
      '<div class="ng-l">Plexus</div><div class="ng-seg ng-plx" role="group" aria-label="Which plexus"></div>' +
      '<div class="ng-l">Side</div><div class="ng-seg ng-side" role="group" aria-label="Which side">' +
        '<button type="button" data-v="r">Right</button><button type="button" data-v="l">Left</button></div>' +
      '<div class="ng-l">Group</div><input class="ng-search" type="search" placeholder="Search roots / trunks / cords / branches...">' +
      '<div class="ng-list" role="listbox" aria-label="Plexus components on this page"></div>' +
      '<p class="ng-hint" aria-live="polite"></p>' +
      '<div class="ng-actions"><button type="button" class="ng-clear">Clear selection</button><button type="button" class="ng-hl">Highlight</button></div>' +
      '<p class="ng-help">Picks every nerve this project’s own cited plexus lineage says is downstream of the chosen component, on THIS page’s own meshes (counted, not assumed — the number by each row). A ligament-free, single-parent lineage: a nerve fed by two cords in real anatomy (e.g. the median nerve) is only listed under one of them here.</p>';
    panel.querySelector(".ng-x").addEventListener("click", function(){ openPanel(false); });
    panel.querySelector(".ng-side").addEventListener("click", function(e){
      var b = e.target && e.target.closest ? e.target.closest("button") : null; if (!b) return;
      side = b.getAttribute("data-v"); persist(); renderList(); syncSeg();
    });
    panel.querySelector(".ng-search").addEventListener("input", function(){ q = this.value.toLowerCase(); renderList(); });
    panel.querySelector(".ng-clear").addEventListener("click", function(){ activeNode = null; if (E.clear) E.clear(); renderList(); say(""); });
    panel.querySelector(".ng-hl").addEventListener("click", function(){ if (E.highlight) E.highlight(); });
    var plx = panel.querySelector(".ng-plx");
    D.plexuses.forEach(function(p){
      var b = document.createElement("button"); b.type = "button"; b.setAttribute("data-v", p); b.textContent = PLEXUS_LABEL[p] || p;
      b.addEventListener("click", function(){ plexus = p; activeNode = null; persist(); renderList(); syncSeg(); });
      plx.appendChild(b);
    });
    syncSeg();
    renderList();
  }
  function syncSeg(){
    if (!panel) return;
    Array.prototype.forEach.call(panel.querySelectorAll(".ng-plx button"), function(b){ b.setAttribute("aria-pressed", String(b.getAttribute("data-v") === plexus)); });
    Array.prototype.forEach.call(panel.querySelectorAll(".ng-side button"), function(b){ b.setAttribute("aria-pressed", String(b.getAttribute("data-v") === side)); });
  }
  function say(m){ var st = $p(".ng-st"); if (st) st.textContent = m || ""; }
  function hint(m){ var h = $p(".ng-hint"); if (h) h.textContent = m || ""; }
  function renderList(){
    var list = $p(".ng-list"); if (!list || !D) return;
    list.innerHTML = "";
    var ids = (D.by_plexus[plexus] || []).filter(function(nid){
      var n = D.nodes[nid];
      return n && n.sides && n.sides[side] && (!q || n.display_name.toLowerCase().indexOf(q) >= 0 || (n.level_label || "").toLowerCase().indexOf(q) >= 0);
    });
    if (!ids.length){ list.innerHTML = '<div class="ng-empty">No ' + esc((PLEXUS_LABEL[plexus] || plexus).toLowerCase()) + ' plexus nerves on the ' + (side === "r" ? "right" : "left") + ' of this page' + (q ? " match that search" : "") + '.</div>'; return; }
    var lastLvl = null;
    ids.forEach(function(nid){
      var n = D.nodes[nid], s = n.sides[side];
      if (n.level_label !== lastLvl){ var h = document.createElement("div"); h.className = "ng-lvl"; h.textContent = n.level_label; list.appendChild(h); lastLvl = n.level_label; }
      var row = document.createElement("div"); row.className = "ng-row" + (activeNode === nid ? " ng-on" : ""); row.setAttribute("role", "option"); row.tabIndex = 0;
      row.setAttribute("aria-selected", String(activeNode === nid));
      row.innerHTML = '<span class="ng-nm">' + esc(n.display_name) + '</span><span class="ng-cnt">' + s.resolved_count + ' / ' + s.total + '</span>';
      row.addEventListener("click", function(){ pick(nid); });
      row.addEventListener("keydown", function(e){ if (e.key === "Enter" || e.key === " "){ e.preventDefault(); pick(nid); } });
      list.appendChild(row);
    });
  }
  function pick(nid){
    var n = D.nodes[nid], s = n.sides[side];
    activeNode = nid;
    var marked = E.mark ? E.mark(s.resolved_ids, true) : 0;
    var missing = s.total - s.resolved_count;
    say(marked + " nerve" + (marked === 1 ? "" : "s") + " selected (" + (side === "r" ? "right" : "left") + ").");
    hint(n.display_name + ": " + s.resolved_count + " of " + s.total + " downstream nerves present on this page" +
      (missing ? " (" + missing + " not modelled here" + (s.missing_sample.length ? ": " + s.missing_sample.slice(0, 6).join(", ") + (s.missing_count > 6 ? ", ..." : "") : "") + ")" : "") + ".");
    renderList();
  }
  function openPanel(on){
    if (!panel) return;
    panel.hidden = !on;
    if (on){ buildPanel(); syncSeg(); renderList(); }
    if (btn) btn.setAttribute("aria-pressed", String(on));
  }
  function load(){
    if (!E.url || !window.fetch) return;
    fetch(E.url).then(function(r){ if (!r.ok) throw new Error("no plexus_groups.json"); return r.json(); }).then(function(d){
      if (!d || String(d.schema).indexOf("nmsk.plexus_sidecar") !== 0 || !d.nodes || !d.plexuses || !d.plexuses.length) throw new Error("not a plexus sidecar");
      D = d; M = [1];      // non-empty sentinel: matches NMSKParts's "only add the button once there is something to show" convention
      build();
      if (E.onLoaded) E.onLoaded();
    }).catch(function(){ D = null; });
  }
  return {
    load:load, openPanel:openPanel,
    state:function(){ return {loaded:!!D, plexus:plexus, side:side, active:activeNode, panel:panelOpen(),
      plexuses:D ? D.plexuses.slice() : [], nodeCount:D ? Object.keys(D.nodes).length : 0}; }
  };
}
