/* Q298: the three expansions of the selected structure. Each is one tap, each ADDS to the marked set through
   NMSKSelect.markIds (one undo step for the whole batch), and each says where it came from.

     Adjacent   MEASURED on this page's own meshes: scripts/anatomy/q298/adjacency_q298.py rasterises every structure's
                surface into a shared 2 mm voxel grid (samples at <= 1 mm spacing, so no triangle is missed -- 69 % of the
                triangles on a Z page are longer than 3 mm across, which is why a vertex-to-vertex test would not do) and
                calls two structures adjacent when their voxels touch in the 3x3x3 neighbourhood: a surface-to-surface
                separation of at most 6.93 mm = sqrt(3) * 2 * cell, which is the bound that CANNOT be exceeded. Q308
                corrected this: the figure printed until then was 3.46 mm = sqrt(3) * cell, which bounds the two voxel
                CENTRES and not the surface points, so it overstated the precision. Measured on 120 random adjacent
                pairs, the typical pair is far closer than either figure -- median 0.18 mm, p95 3.64, max 4.45. The
                status line always states the count and the threshold. It is a measurement of the geometry, not an
                anatomical claim.
     Related    the same muscle's other heads and parts, its tendon / aponeurosis / sheath, its bursae, its nerve supply,
                an artery whose own record says it supplies it, the bones it attaches to, the structures of the joints it
                crosses, and its antagonists at a shared joint -- built by scripts/anatomy/q298/relations_q298.py from the
                project's own cited data (Q283 actions and attachments, Q293 heads and audit, the plexus data, each card's
                own fields). Every kind carries its own source, and the kinds that are a rule of this project rather than a
                cited list (tendon / bursa by name, joint structures, antagonists) are shown as "inferred".
     Functional group  the named textbook groups of data/anatomy/muscle_groups_q283.json, the groups derived from the
                cited action data (every muscle whose own record gives this motion at this joint), and the few extra groups
                in data/anatomy/relations_q298.json (the tensors of the iliotibial tract, the contributors to the calcaneal
                and patellar tendons, the pes anserinus, the carpal tunnel contents). More than one group applying is the
                normal case, so the button opens a short menu; one group is marked with one tap.

   The adjacency and relation tables ride in the page's nmsk-q298 block, zlib-compressed and base64'd like the Q284
   moment-arm block, and are inflated once on first use. */
function NMSKExpand(E, BAR, D, H){
  "use strict";
  var say = H.say, esc = H.esc;
  var ADJ = null, REL = null, loading = {}, names = {};
  (E.items() || []).forEach(function(it){ if (!(it.id in names)) names[it.id] = it.name || it.id; });

  function nameOf(id){ return names[id] || id; }

  function inflate(b64){
    if (typeof DecompressionStream === "undefined") return Promise.reject(new Error("no DecompressionStream"));
    var bin = atob(b64), u8 = new Uint8Array(bin.length), i;
    for (i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return new Response(new Blob([u8]).stream().pipeThrough(new DecompressionStream("deflate"))).text().then(JSON.parse);
  }

  function load(which){
    var k = which === "adj" ? "adj" : "rel";
    if (loading[k]) return loading[k];
    var blk = D[k];
    if (!blk || !blk.z){ loading[k] = Promise.resolve(null); return loading[k]; }
    loading[k] = inflate(blk.z).then(function(j){
      if (k === "adj") ADJ = j; else REL = j;
      BAR.refresh();
      return j;
    }).catch(function(){ return null; });
    return loading[k];
  }
  load("adj"); load("rel");

  function idxOf(tbl, id){
    if (!tbl) return -1;
    if (!tbl._ix){ tbl._ix = {}; for (var i = 0; i < tbl.ids.length; i++) if (!(tbl.ids[i] in tbl._ix)) tbl._ix[tbl.ids[i]] = i; }
    var v = tbl._ix[id];
    return v === undefined ? -1 : v;
  }

  function adjIds(id){
    var i = idxOf(ADJ, id);
    if (i < 0) return [];
    return (ADJ.adj[i] || []).map(function(j){ return ADJ.ids[j]; });
  }
  function relRows(id){
    var i = idxOf(REL, id);
    if (i < 0 || !REL.rel) return [];
    return (REL.rel[String(i)] || []).map(function(r){ return {id:REL.ids[r[0]], kind:r[1]}; });
  }
  function groupsOf(id){
    var i = idxOf(REL, id);
    if (i < 0 || !REL.fg || !REL.fgroups) return [];
    return (REL.fg[String(i)] || []).map(function(g){
      var G = REL.fgroups[g];
      return {id:G.id, name:G.name, src:G.src, inferred:G.inferred, why:G.why,
              ids:G.i.map(function(j){ return REL.ids[j]; })};
    });
  }

  function counts(id){
    return {adj:ADJ ? adjIds(id).length : 0, rel:REL ? relRows(id).length : 0, grp:REL ? groupsOf(id).length : 0};
  }

  var KINDS = (D.rel && D.rel.kinds) || {};

  function run(which){
    var id = E.selected();
    if (!id){ say("Pick a structure first."); return; }
    BAR.closeMenu();
    if (which === "adj"){
      var ids = adjIds(id);
      if (!ids.length){ say("Nothing within " + (D.adj ? D.adj.th : "?") + " mm of " + nameOf(id) + " on this page."); return; }
      var s = E.sel();
      var n = s ? s.markIds(ids, true, false, true) : 0;
      E.rerender();
      say(ids.length + " structures neighbour " + nameOf(id) + " on this page's own geometry (" + n + " newly marked, " +
          "one undo step). MEASURED, not an anatomical claim: " + (D.adj ? D.adj.how : "") );
      return;
    }
    if (which === "rel"){
      var rows = relRows(id);
      if (!rows.length){ say("No related structure for " + nameOf(id) + " in this project's own data."); return; }
      var byk = {};
      rows.forEach(function(r){ (byk[r.kind] = byk[r.kind] || []).push(r.id); });
      var ks = Object.keys(byk).sort();
      var html = '<p class="q8-mh">Related to <b>' + esc(nameOf(id)) + "</b> — add:</p>" +
        '<button type="button" class="q8-b" data-k="*">All ' + rows.length + "</button>" +
        ks.map(function(k){
          var K = KINDS[k] || {};
          return '<button type="button" class="q8-b" data-k="' + esc(k) + '" title="' + esc((K.why || "") + (K.src ? " — " + K.src : "")) + '">' +
                 esc(K.label || k) + ' <span class="q8-n">' + byk[k].length + "</span>" +
                 (K.inferred ? ' <span class="q8-inf">inferred</span>' : "") + "</button>";
        }).join("");
      BAR.menu(html, function(m){
        Array.prototype.forEach.call(m.querySelectorAll("[data-k]"), function(b){
          b.addEventListener("click", function(){
            var k = b.getAttribute("data-k");
            var list = k === "*" ? rows.map(function(r){ return r.id; }) : byk[k];
            var K = KINDS[k] || {};
            BAR.closeMenu();
            var s2 = E.sel();
            var n2 = s2 ? s2.markIds(list, true, false, true) : 0;
            E.rerender();
            say(list.length + " related to " + nameOf(id) + (k === "*" ? "" : " (" + (K.label || k) + ")") +
                " offered, " + n2 + " newly marked, one undo step." +
                (k === "*" ? " Mixed sources — open the menu again to see each kind's own source."
                           : (K.src ? " Source: " + K.src + "." : "")) +
                (k !== "*" && K.inferred ? " INFERRED: " + K.why : ""));
          });
        });
      });
      return;
    }
    var gs = groupsOf(id);
    if (!gs.length){ say(nameOf(id) + " is not in a functional group in this project's data."); return; }
    if (gs.length === 1){ markGroup(gs[0], id); return; }
    BAR.menu('<p class="q8-mh">Functional groups of <b>' + esc(nameOf(id)) + "</b>:</p>" +
      gs.map(function(g, i){
        return '<button type="button" class="q8-b" data-g="' + i + '" title="' + esc((g.why || "") + (g.src ? " — " + g.src : "")) + '">' +
               esc(g.name) + ' <span class="q8-n">' + g.ids.length + "</span>" +
               (g.inferred ? ' <span class="q8-inf">inferred</span>' : "") + "</button>";
      }).join(""), function(m){
        Array.prototype.forEach.call(m.querySelectorAll("[data-g]"), function(b){
          b.addEventListener("click", function(){ BAR.closeMenu(); markGroup(gs[+b.getAttribute("data-g")], id); });
        });
      });
  }

  function markGroup(g, id){
    var s = E.sel();
    var n = s ? s.markIds(g.ids, true, false, true) : 0;
    E.rerender();
    say(g.ids.length + " in the functional group “" + g.name + "” of " + nameOf(id) + " (" + n +
        " newly marked, one undo step). " + (g.inferred ? "INFERRED: " + g.why : g.why) + (g.src ? " Source: " + g.src + "." : ""));
  }

  return {run:run, counts:counts, nameOf:nameOf,
          adjIds:adjIds, relRows:relRows, groupsOf:groupsOf,
          state:function(){
            var id = E.selected();
            return {adjReady:!!ADJ, relReady:!!REL, selected:id || null, counts:id ? counts(id) : null,
                    adjThresholdMm:D.adj ? D.adj.th : null};
          }};
}
