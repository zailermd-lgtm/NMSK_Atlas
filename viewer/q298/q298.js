/* Q298 bootstrap: the one controller both engines start, so the search, the multi-select and the three expansions behave
   identically on the own-engine pages and on the Z pages.

   The engine hands over an adaptor E:
     box()        the engine's own search input (the own pages name it #q, the Z pages #search -- Q297 was bitten by this)
     list()       the element the engine renders its structure rows into
     items()      [{id, name, latin, cat, part, group, note}] one per list row, in the engine's own order
     sel()        the Q227 selection controller (NMSKSelect) or null
     selected()   the id of the structure the card is showing, or null
     pick(id)     select + reveal that structure (the engine's own row click path)
     rerender()   re-render the structure list (the engine's renderList)
     isPhone()
   and calls NMSKQ298.filter(q) from its own renderList, so the ranking is the shared one.

   Nothing here reaches into NMSKSelect's internals: marking always goes through its public markIds(ids, true, false),
   which takes ONE undo snapshot for the whole batch -- so "add all 14 results", "adjacent", "related" and "functional
   group" are each a single undo step, not one per structure (Q294's page-wide NMSKHistory sees one settled change too). */
var NMSKQ298 = (function(){
  "use strict";
  var E = null, IX = null, D = null, last = null, bar = null, multi = null, expand = null, started = false;

  function $(id){ return document.getElementById(id); }
  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"}[c]; }); }

  function data(){
    if (D) return D;
    var el = $("nmsk-q298");
    try { D = el ? JSON.parse(el.textContent || "{}") : {}; } catch (err){ D = {}; }
    /* Q306 ships a SUPERSET of this table in its own block (scripts/anatomy/q306/build_search_q306.py):
       every Q298 row unchanged, plus the names of the 93 functional groups the page carried but nobody
       could type, the 18 new cited groups, the concept layer and the new synonyms and explanations. It is
       a separate block so Q298's comes out of the regen byte-identical. The search / adjacency / relation
       payloads Q298 owns (`adj`, `rel`) are NOT in the Q306 block and are kept from this one. */
    var e6 = $("nmsk-q306"), d6 = null;
    try { d6 = e6 ? JSON.parse(e6.textContent || "null") : null; } catch (err2){ d6 = null; }
    if (d6 && d6.ids){
      ["ids", "sub", "alias", "groups", "ns", "concepts"].forEach(function(k){ if (d6[k]) D[k] = d6[k]; });
      D.q306 = 1;
    }
    return D;
  }

  function ready(){ return !!IX; }

  /* ---- what the engine's renderList calls: the ranked ids for this query (the whole set, not the truncated view) ---- */
  function filter(q){
    if (!IX) return null;
    last = IX.run(q || "");
    return last.ids;
  }
  function result(){ return last; }

  /* the "why it matched" suffix: `Iliotibial tract (ITB)`, so the user learns the canonical name */
  function whySuffix(id){
    if (!last || !last.why || !last.why[id]) return "";
    var w = last.why[id];
    return ' <span class="q8-why" data-kind="' + esc(w.k) + '" title="' + esc(whyTitle(w)) + '">(' + esc(w.d) + ')</span>';
  }
  function whyTitle(w){
    var t = w.k === "abbr" ? "abbreviation" : w.k === "he" ? "Hebrew name" : w.k === "name" ? "name" : "other name";
    return "matched the " + t + ' "' + w.d + '" of ' + w.c + (w.s ? " — " + w.s : "") + (w.n ? " — " + w.n : "") +
           (w.amb ? " — this abbreviation has more than one accepted expansion; all of them are offered." : "");
  }

  function say(m){ var e = $("q8-status"); if (e) e.textContent = m || ""; }

  function start(cfg){
    if (started) return;
    started = true;
    E = cfg;
    var d = data();
    if (!d || !d.ids){ return; }                       // a page built without the Q298 block: the engines fall back
    IX = NMSKSearchCore.build({items:E.items(), data:d});
    bar = NMSKQ298Bar(E, d, {say:say, esc:esc, result:result});
    multi = NMSKMulti(E, bar, {say:say});
    expand = NMSKExpand(E, bar, d, {say:say, esc:esc});
    bar.wire(multi, expand);
    E.rerender();
  }

  /* called by the engine right after it has rendered the list, with the ids of the rows actually in the DOM */
  function afterList(shownIds){
    if (!bar) return;
    bar.update(last, shownIds || []);
    if (multi) multi.wire(shownIds || []);
  }

  return {start:start, ready:ready, filter:filter, result:result, whySuffix:whySuffix, afterList:afterList,
          data:data, say:say,
          core:function(){ return IX; },
          state:function(){
            var d = data(), sc = E && E.sel ? E.sel() : null, ms = null;
            try { ms = sc ? sc.state() : null; } catch (err){ ms = null; }
            return {ready:!!IX,
                    /* the marked-structures count, read through the selection controller's own public state() -- both
                       engines keep selCtl as a local var, so a test (and anything else outside the engine) needs it here */
                    marked:ms ? ms.marks.length : -1, markMode:ms ? !!ms.markMode : false, structures:IX ? IX.count : 0, aliasForms:IX ? IX.aliasForms : 0,
                    groups:IX ? IX.groupCount : 0, adjacency:!!(d && d.adj), relations:!!(d && d.rel),
                    threshold_mm:d && d.adj ? d.adj.th : null, adjacentPairs:d && d.adj ? d.adj.n : 0,
                    relationLinks:d && d.rel ? d.rel.n : 0,
                    lastQuery:last ? last.q : "", lastCount:last ? last.ids.length : 0,
                    lastGroups:last ? last.groups.length : 0, lastNotes:last ? last.notes.length : 0,
                    lastStats:last ? last.stats : null,
                    expand:expand ? expand.state() : null, multi:multi ? multi.state() : null};
          }};
})();
