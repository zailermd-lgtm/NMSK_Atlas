/* Q306: the three things the search still could not say.
 *
 * Measured in docs/research/Q306_search_coverage_audit.md against the live pages: of 419 terms a clinician
 * would type, 132 returned something. The owner's own three were all in the 287 that did not -- and one of
 * them was worse than silence. `psoas minor` returned `Psoas major` at RANK 1 with no note, and
 * `long head of biceps brachii` returned the long head of TRICEPS brachii, because Q298's fuzzy pass
 * answers a query that matched nothing and says nothing about it. The page stated something false with
 * confidence, which is the class of defect Q297 refused to allow for geometry.
 *
 * This module adds only what the matcher cannot: the words on the screen.
 *   1. APPROXIMATE  -- when every row came from the fuzzy pass (`res.approx`), say so above the rows.
 *   2. NOTE FIRST   -- when an explanation matched the query exactly and no structure did
 *                      (`res.note_first`), the explanation is the answer and the rows are near-misses.
 *   3. CONCEPTS     -- `pelvic tilt` is not a structure. A concept row offers the structures and the
 *                      groups the page really carries, with its own cited claims, and a button that marks
 *                      them in ONE undo step through the selection controller's own markIds().
 * It owns no state, reaches into no engine, and does nothing at all on a page built without the Q306
 * block -- the bar calls it only if it is there. */
var NMSKQ306 = (function(){
  "use strict";
  var API = null, HOST = null, CUR = null;

  function esc(s){
    return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){
      return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"}[c]; });
  }

  /* the concept table rides in the Q306 block; the matcher does not read it, because a concept is not a
     structure and must not compete with one for a rank */
  function conceptsFor(d, q){
    var out = [], i, j, rows = (d && d.concepts) || [];
    if (!q) return out;
    for (i = 0; i < rows.length; i++){
      var al = rows[i].al || [], hit = false;
      for (j = 0; j < al.length && !hit; j++){
        if (al[j] === q || (q.length >= 3 && al[j].indexOf(q) === 0)) hit = true;
      }
      if (hit) out.push(rows[i]);
    }
    return out;
  }

  function kindWord(k){
    return k === "region" ? "a named space, not a structure"
         : k === "diagnosis" ? "a diagnosis, not a structure"
         : k === "measure" ? "a measurement"
         : k === "posture" ? "an alignment descriptor"
         : "a concept, not a structure";
  }

  /* ---------------------------------------------------------------- render */
  function render(res, host, api){
    if (!host) return;
    API = api; HOST = host;
    var d = api.data(), q = res ? res.q : "";
    var cs = conceptsFor(d, q);
    CUR = cs;
    var html = "";

    /* 1 + 2: say when nothing actually matched */
    if (res && res.note_first){
      html += '<p class="q6-approx q6-exact">' +
              'That name is <b>not a structure on this page</b> — the explanation below is the answer. ' +
              'The rows under it are the closest names, not what you asked for.</p>';
    } else if (res && res.approx){
      html += '<p class="q6-approx">No exact match for <b>' + esc(res.approx_of || q) +
              '</b> — showing the closest names.</p>';
    }

    /* 3: the concept rows */
    for (var i = 0; i < cs.length; i++){
      var c = cs[i], n = (c.i || []).length, g = (c.g || []).length;
      html += '<div class="q6-con" data-c="' + i + '">' +
              '<p class="q6-h"><b>' + esc(c.label) + '</b>' +
              (c.he ? ' <span class="q6-he">' + esc(c.he) + '</span>' : "") +
              ' <span class="q6-k">' + esc(kindWord(c.kind)) + '</span></p>' +
              '<p class="q6-b">' + esc(c.body) + '</p>';
      if (c.note) html += '<p class="q6-n">' + esc(c.note) + '</p>';
      if (c.claims && c.claims.length){
        html += '<details class="q6-src"><summary>' + c.claims.length +
                (c.claims.length === 1 ? ' cited source' : ' cited sources') + '</summary><ul>';
        for (var j = 0; j < c.claims.length; j++){
          html += '<li>' + esc(c.claims[j].t) + ' <i>' + esc(c.claims[j].s) + '</i></li>';
        }
        html += "</ul></details>";
      }
      html += '<p class="q6-act">';
      if (n) html += '<button type="button" class="q6-btn" data-act="mark" data-c="' + i + '">Mark the ' +
                     n + ' structures</button>';
      for (var k = 0; k < (c.g || []).length; k++){
        html += '<button type="button" class="q6-btn q6-g" data-act="grp" data-c="' + i +
                '" data-g="' + k + '">' + esc(groupName(d, c.g[k])) + '</button>';
      }
      if (!n && !g) html += '<span class="q6-k">nothing on this page to offer</span>';
      html += "</p></div>";
    }
    host.innerHTML = html;
    host.hidden = !html;
    wire(host, d);
  }

  function groupName(d, gid){
    var gs = (d && d.groups) || [];
    for (var i = 0; i < gs.length; i++) if (gs[i].id === gid) return gs[i].name;
    return gid;
  }

  function wire(host, d){
    var bs = host.querySelectorAll(".q6-btn");
    for (var i = 0; i < bs.length; i++){
      bs[i].addEventListener("click", function(ev){
        var b = ev.currentTarget, c = CUR[+b.getAttribute("data-c")];
        if (!c) return;
        if (b.getAttribute("data-act") === "mark"){
          var ids = [], dd = API.data();
          for (var n = 0; n < (c.i || []).length; n++){ var s = dd.ids[c.i[n]]; if (s) ids.push(s); }
          API.markIds(ids, "the concept " + c.label, "Q306 / " + (c.claims && c.claims.length
                      ? c.claims.length + " cited sources" : "this project's own data"),
                      c.inferred, c.body);
        } else {
          var gid = c.g[+b.getAttribute("data-g")], gs = (API.data().groups || []), gi = null;
          for (var m = 0; m < gs.length; m++) if (gs[m].id === gid) gi = gs[m];
          if (!gi) return;
          var gids = [], dd2 = API.data();
          for (var p = 0; p < (gi.i || []).length; p++){ var s2 = dd2.ids[gi.i[p]]; if (s2) gids.push(s2); }
          API.markIds(gids, "the group " + gi.name, gi.src, gi.inferred, gi.why);
        }
      });
    }
  }

  return {render:render, concepts:conceptsFor,
          state:function(){
            var d = API ? API.data() : null;
            return {on:!!(d && d.q306), concepts:d && d.concepts ? d.concepts.length : 0,
                    groups:d && d.groups ? d.groups.length : 0,
                    shown:CUR ? CUR.length : 0};
          }};
})();
